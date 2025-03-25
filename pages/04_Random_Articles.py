# pages/02_Random_Articles.py
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from Login import (
    client, 
    db, 
    rankings_collection, 
    satisfaction_collection, 
    highlight_feedback_collection, 
    users_collection, 
    format_article, 
    load_random_articles, 
    load_css, 
    update_user_embedding
)
import streamlit_analytics

# Load CSS
load_css()
streamlit_analytics.start_tracking()
st.title("Random Articles")

# --- Load Random Articles ---
if "random_articles" not in st.session_state:
    st.session_state.random_articles = load_random_articles(limit=5)
    st.session_state.random_article_contents = [format_article(article) for article in st.session_state.random_articles]

# Function to clear all user inputs for random articles
def clear_random_article_inputs():
    # Get number of articles currently loaded
    num_articles = len(st.session_state.random_articles)
    
    # Clear scores and feedback for all articles
    for i in range(num_articles):
        # Reset scores to default value (0)
        if f'random_score_{i}_article' in st.session_state:
            st.session_state[f'random_score_{i}_article'] = 0
            
        # Clear any feedback text
        if f'random_feedback_{i}_article' in st.session_state:
            st.session_state[f'random_feedback_{i}_article'] = ""

# Button to load new random articles
if st.sidebar.button("Load New Random Articles"):
    clear_random_article_inputs()

    st.session_state.random_articles = load_random_articles(limit=5)
    st.session_state.random_article_contents = [format_article(article) for article in st.session_state.random_articles]

st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")

for i, article in enumerate(st.session_state.random_articles):
    # Create three columns: article, highlights, and scoring
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.markdown(st.session_state.random_article_contents[i], unsafe_allow_html=True)
    
    with col2:
        # Get the highlights data; expect a list of strings.
        highlights = article.get("highlights", [])
        if isinstance(highlights, list) and len(highlights) > 0:
            total_highlights = len(highlights)
            # Set a unique key for the current article's highlight index in session state
            highlight_key = f'random_highlight_index_{i}'
            if highlight_key not in st.session_state:
                st.session_state[highlight_key] = 0
            current_index = st.session_state[highlight_key]
            # Get the current highlight and truncate if needed
            current_highlight = highlights[current_index]
            if len(current_highlight) > 250:
                current_highlight = current_highlight[:250] + '...'
            highlight_count_text = f"Highlight {current_index + 1} of {total_highlights}"
        else:
            current_highlight = "no highlights available"
            highlight_count_text = ""
        
        # Get the article URL from the article
        url = article.get("link", "#")
        # Display the highlight card with "Highlights:" label, the count, and the highlight text.
        st.markdown(f"""
            <a href="{url}" target="_blank">
                <div class="article-card">
                    <strong style="font-size: 18px;">Highlights:</strong>
                    <p style="font-size: 14px; margin-top: 5px; color: #888;">{highlight_count_text}</p>
                    <p style="font-size: 16px; font-weight: normal; text-align: left; word-wrap: break-word; margin-top: 10px;">
                        {current_highlight}
                    </p>
                </div>
            </a>
        """, unsafe_allow_html=True)
    
    with col3:
        # Article scoring
        score = st.number_input('Article Score', min_value=-1, max_value=1, value=0, key=f'random_score_{i}_article')

        # If score is -1, allow feedback
        if score == -1:
            feedback = st.text_area(f"Feedback for article", key=f'random_feedback_{i}_article', height=80)
        
        # Add highlight feedback in the same column
        if isinstance(highlights, list) and len(highlights) > 0:
            current_index = st.session_state.get(f'random_highlight_index_{i}', 0)
            
            # Score for current highlight
            highlight_score = st.number_input(
                'Highlight Score', 
                min_value=-1, 
                max_value=1, 
                value=0, 
                key=f'random_score_{i}_highlight_{current_index}'
            )
            
            # Feedback text area for highlight (shorter height to save space)
            if highlight_score == -1:
                highlight_feedback = st.text_area(
                    "Feedback for highlight", 
                    key=f'random_feedback_{i}_highlight_{current_index}',
                    height=80
                )
            else:
                highlight_feedback = ""
            
            # Submit button for highlight feedback
            if st.button("Submit Highlight Score", key=f'random_submit_highlight_{i}_{current_index}'):
                if not st.session_state.get("user_name"):
                    st.error("Please validate your name on the Login page before submitting feedback.")
                else:
                    try:
                        current_highlight = highlights[current_index]
                        if len(current_highlight) > 250:
                            current_highlight = current_highlight[:250] + '...'
                            
                        highlight_feedback_data = {
                            "article_id": str(article.get("_id")),
                            "article_title": article.get("title"),
                            "highlight_index": current_index,
                            "highlight_text": current_highlight,
                            "score": highlight_score,
                            "feedback": highlight_feedback,
                            "user_name": st.session_state.user_name,
                            "submission_id": str(uuid.uuid4()),
                            "timestamp": datetime.now(),
                            "page": "random_articles"
                        }
                        highlight_feedback_collection.insert_one(highlight_feedback_data)
                        st.success("Highlight score saved!")
                    except Exception as e:
                        st.error(f"Error saving highlight score: {e}")

            # If there are multiple highlights, show the "Next Highlight" button.
            if isinstance(highlights, list) and len(highlights) > 1:
                if st.button("Next Highlight", key=f'random_next_highlight_{i}'):
                    st.session_state[highlight_key] = (st.session_state[highlight_key] + 1) % total_highlights
                    st.rerun()

# --- Submit Rankings Button ---
if st.button("Submit Article Scores", key="random_articles_submit"):
    if not st.session_state.get("user_name"):
        st.error("Please validate your name on the Login page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        rankings = []
        for i, article in enumerate(st.session_state.random_articles):
            score = st.session_state.get(f'random_score_{i}_article')
            ranking_data = {
                "title": article.get("title"),
                "rank": score,
                "submission_id": submission_id,
                "user_name": st.session_state.user_name,
                "page": "random_articles"
            }
            if score == -1:
                feedback = st.session_state.get(f'random_feedback_{i}_article', '')
                ranking_data["feedback"] = feedback
            rankings.append(ranking_data)

            # Check if article has a response_array for embedding update
            if article.get('response_array'):
                try:
                    updated_embedding = update_user_embedding(
                        users_collection, 
                        st.session_state.user_name, 
                        article['response_array'],
                        score
                    )
                except Exception as e:
                    st.error(f"Error updating user embedding for article {i+1}: {e}")
        
        try:
            if rankings:
                rankings_collection.insert_many(rankings)
            st.success("Your article scores have been saved!")
        except Exception as e:
            st.error(f"Error saving article scores: {e}")

# --- Satisfaction Survey (Integrated) ---
st.markdown("---")
st.subheader("Satisfaction Survey")
st.write("Please rate your experience with these article recommendations.")

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="random_satisfaction")
comments = st.text_area("Additional comments (optional):", key="random_comments")

if st.button("Submit Satisfaction Score", key="random_satisfaction_button"):
    if not st.session_state.get("user_name"):
        st.error("Please validate your name on the Login page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        try:
            satisfaction_data = {
                "submission_id": submission_id,
                "user_name": st.session_state.user_name,
                "satisfaction_score": satisfaction_score,
                "comments": comments,
                "page": "random_articles"
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Thank you! Your satisfaction score and comments have been saved.")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")

streamlit_analytics.stop_tracking()