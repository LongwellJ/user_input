import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from Login import (
    client, 
    db, 
    users_collection, 
    rankings_collection, 
    highlight_feedback_collection, 
    satisfaction_collection,
    top_stories, 
    format_article, 
    load_articles_from_mongodb, 
    load_css, 
    authenticate_user,
    update_user_embedding,
    load_articles_vector_search,
    track_user_article_feedback
)
import streamlit_analytics

# Load CSS and start analytics tracking
load_css()
streamlit_analytics.start_tracking()
st.title("Curated Articles")

# Check if user is valid using MongoDB authentication
if not st.session_state.get("is_valid_user", False) or not authenticate_user(st.session_state.get("user_name", "")):
    st.error("You need to be logged in as a valid user to view this page.")
    st.write("Please go back to the home page and enter a valid username.")
    st.stop()

# --- Determine the Collection Based on User's Persona ---
# Get the user's profile from the users collection
user_data = users_collection.find_one({"username": st.session_state.user_name})

# Default to "Critical Thinker" if no persona is found
persona = user_data.get("persona", None)
if persona is None:
    st.error("No persona found for the user. Please go to the initialization page or provide article feedback on the other pages.")
    st.stop()
feedback_count = user_data.get("feedback_count", 0)
user_embedding = user_data.get("user_embedding", [])

# Map persona to the corresponding collection (for non-vector search)
if persona == "Data-Driven Analyst":
    selected_collection = db["Data-Driven Analyst"]
elif persona == "Engaging Storyteller":
    selected_collection = db["Engaging Storyteller"]
elif persona == "Critical Thinker":
    selected_collection = db["Critical Thinker"]
elif persona == "Balanced Evaluator":
    selected_collection = db["Balanced Evaluator"]

# --- Initialize session state variables for articles ---
# Determine which loading method to use based on feedback_count and user_embedding
if "articles_data" not in st.session_state:
    if feedback_count >= 5 and isinstance(user_embedding, list) and len(user_embedding) > 0:
        st.session_state.articles_data = load_articles_vector_search(user_name=st.session_state.user_name, user_embedding=user_embedding, offset=0, limit=5)
        st.markdown("*These articles are tailored to your interests using advanced matching*")
    else:
        st.session_state.articles_data = load_articles_from_mongodb(user_name=st.session_state.user_name, offset=0, limit=5, collection=selected_collection)
        st.markdown(f"*Recommendations matched to your persona*")
if "article_content" not in st.session_state:
    st.session_state.article_content = [format_article(article) for article in st.session_state.articles_data]

if "articles_offset" not in st.session_state:
    st.session_state.articles_offset = 5


# Button to refresh latest articles
if st.sidebar.button("Refresh Curated Articles"):
    # Get the updated user embedding
    user_embedding = users_collection.find_one({"username": st.session_state.user_name}).get("user_embedding", [])
    print("This is the user_embedding", user_embedding)
    # Reset the articles data and content
    st.session_state.articles_data = []
    st.session_state.article_content = []
    # Reset the offset for loading more articles
    st.session_state.articles_offset = 5
    if feedback_count >= 5 and isinstance(user_embedding, list) and len(user_embedding) > 0:
        st.session_state.articles_data = load_articles_vector_search(user_name=st.session_state.user_name, user_embedding=user_embedding, offset=0, limit=5)
    else:
        st.session_state.articles_data = load_articles_from_mongodb(user_name=st.session_state.user_name, offset=0, limit=5, collection=selected_collection)
    st.session_state.article_content = [format_article(article) for article in st.session_state.articles_data]

# --- Sidebar: Load More Button ---
if st.sidebar.button("Load More"):
    offset = st.session_state.articles_offset
    if feedback_count >= 5 and isinstance(user_embedding, list) and len(user_embedding) > 0:
        new_articles = load_articles_vector_search(user_name=st.session_state.user_name, user_embedding=user_embedding, offset=offset, limit=5)
    else:
        new_articles = load_articles_from_mongodb(user_name=st.session_state.user_name, offset=offset, limit=5, collection=selected_collection)
        
    if new_articles:
        st.session_state.articles_data.extend(new_articles)
        for article in new_articles:
            st.session_state.article_content.append(format_article(article))
        st.session_state.articles_offset += len(new_articles)
    else:
        st.sidebar.warning("No more articles available.")

# --- Display Articles and Score Input ---
if not st.session_state.articles_data:
    st.error("No articles available to display.")
else:
    st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")

for i, article in enumerate(st.session_state.articles_data):
    
    # Create three columns: article, highlights, and scoring
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.markdown(st.session_state.article_content[i], unsafe_allow_html=True)
    
    with col2:
        # Get the highlights data; expect a list of strings.
        highlights = article.get("highlights", [])
        if isinstance(highlights, list) and len(highlights) > 0:
            total_highlights = len(highlights)
            # Set a unique key for the current article's highlight index in session state
            highlight_key = f'curated_highlight_index_{i}'
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
        score = st.number_input('Article Score', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')

        # If score is -1, allow feedback
        if score == -1:
            feedback = st.text_area(f"Feedback for article", key=f'feedback_{i}_article', height=80)
        
        # Add highlight feedback in the same column
        if isinstance(highlights, list) and len(highlights) > 0:
            current_index = st.session_state.get(f'curated_highlight_index_{i}', 0)
            
            # Score for current highlight
            highlight_score = st.number_input(
                'Highlight Score', 
                min_value=-1, 
                max_value=1, 
                value=0, 
                key=f'score_{i}_highlight_{current_index}'
            )
            
            # Feedback text area for highlight (shorter height to save space)
            if highlight_score == -1:
                highlight_feedback = st.text_area(
                    "Feedback for highlight", 
                    key=f'feedback_{i}_highlight_{current_index}',
                    height=80
                )
            else:
                highlight_feedback = ""
            
            # Submit button for highlight feedback
            if st.button("Submit Highlight Score", key=f'curated_submit_highlight_{i}_{current_index}'):
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
                            "page": "curated_articles"
                        }
                        highlight_feedback_collection.insert_one(highlight_feedback_data)
                        st.success("Highlight score saved!")
                    except Exception as e:
                        st.error(f"Error saving highlight score: {e}")

            # If there are multiple highlights, show the "Next Highlight" button.
            if isinstance(highlights, list) and len(highlights) > 1:
                if st.button("Next Highlight", key=f'curated_next_highlight_{i}'):
                    st.session_state[highlight_key] = (st.session_state[highlight_key] + 1) % total_highlights
                    st.rerun()


# --- Submit Rankings Button ---
if st.button("Submit Article Scores"):
    if not st.session_state.get("user_name"):
        st.error("Please validate your name on the Login page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        rankings = []
        for i, article in enumerate(st.session_state.articles_data):
            score = st.session_state.get(f'score_{i}_article')

            # Track article ranking feedback
            track_user_article_feedback(
                st.session_state.user_name, 
                article.get("_id"), 
                "curated_articles",
            )

            ranking_data = {
                "title": article.get("title"),
                "rank": score,
                "submission_id": submission_id,
                "user_name": st.session_state.user_name,
                "page": "curated_articles"
            }
            if score == -1:
                feedback = st.session_state.get(f'feedback_{i}_article', '')
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
                    # st.session_state.user_embedding = updated_embedding
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

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="curated_satisfaction")
comments = st.text_area("Additional comments (optional):", key="curated_comments")

if st.button("Submit Satisfaction Score", key="curated_satisfaction_button"):
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
                "page": "curated_articles"
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Thank you! Your satisfaction score and comments have been saved.")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")

streamlit_analytics.stop_tracking()
