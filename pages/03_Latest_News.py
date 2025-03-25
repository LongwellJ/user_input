import streamlit as st
import pandas as pd
from datetime import datetime
from Login import client, db, format_article, load_css, rankings_collection, satisfaction_collection, highlight_feedback_collection, users_collection, update_user_embedding, load_latest_articles
import streamlit_analytics
import uuid

# Load CSS
load_css()
streamlit_analytics.start_tracking()
st.title("Latest News")
    
# Initialize session state for latest articles if not exists
if "latest_articles" not in st.session_state:
    st.session_state.latest_articles = load_latest_articles()
    st.session_state.latest_article_contents = [format_article(article) for article in st.session_state.latest_articles]

# Button to refresh latest articles
if st.sidebar.button("Refresh Latest News"):
    st.session_state.latest_articles = load_latest_articles()
    st.session_state.latest_article_contents = [format_article(article) for article in st.session_state.latest_articles]

# Display latest articles with dates
if not st.session_state.latest_articles:
    st.error("No articles available to display.")
else:
    st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")

    # Display articles with score input
    for i, article in enumerate(st.session_state.latest_articles):
        # Create three columns:
        # col1 for the article card, col2 for the highlights card, col3 for the score input.
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(st.session_state.latest_article_contents[i], unsafe_allow_html=True)
        
        with col2:
            # Get the highlights data; expect a list of strings.
            highlights = article.get("highlights", [])
            if isinstance(highlights, list) and len(highlights) > 0:
                total_highlights = len(highlights)
                # Set a unique key for the current article's highlight index in session state
                highlight_key = f'highlight_index_{i}'
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
            # st.markdown("##### Article Score")
            score = st.number_input('Article Score', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')

            # If score is -1, allow feedback
            if score == -1:
                feedback = st.text_area(f"Feedback for article", key=f'feedback_{i}_article', height=80)
            
            # Add highlight feedback in the same column
            if isinstance(highlights, list) and len(highlights) > 0:
                # st.markdown("---")
                # st.markdown("##### Highlight Score")
                current_index = st.session_state.get(f'highlight_index_{i}', 0)
                
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
                if st.button("Submit Highlight Score", key=f'submit_highlight_{i}_{current_index}'):
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
                                "page": "latest_news"
                            }
                            highlight_feedback_collection.insert_one(highlight_feedback_data)
                            st.success("Highlight score saved!")
                        except Exception as e:
                            st.error(f"Error saving highlight score: {e}")

                # If there are multiple highlights, show the "Next Highlight" button.
                if isinstance(highlights, list) and len(highlights) > 1:
                    if st.button("Next Highlight", key=f'next_highlight_{i}'):
                        st.session_state[highlight_key] = (st.session_state[highlight_key] + 1) % total_highlights
                        st.rerun()

# --- Submit Rankings Button ---
if st.button("Submit Article Scores"):
    if not st.session_state.get("user_name"):
        st.error("Please validate your name on the Login page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        rankings = []
        for i, article in enumerate(st.session_state.latest_articles):
            score = st.session_state.get(f'score_{i}_article')
            ranking_data = {
                "title": article.get("title"),
                "rank": score,
                "submission_id": submission_id,
                "user_name": st.session_state.user_name,
                "page": "latest_news"
            }
            if score == -1:
                feedback = st.session_state.get(f'feedback_{i}_article', '')
                ranking_data["feedback"] = feedback
            rankings.append(ranking_data)

        # Check if article has a response_array
            if article.get('response_array'):
                try:
                    updated_embedding = update_user_embedding(
                        users_collection, 
                        st.session_state.user_name, 
                        article['response_array'],
                        score
                    )
                    # if updated_embedding:
                    #     st.success(f"User embedding updated for article {i+1}")
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

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="latest_news_satisfaction")
comments = st.text_area("Additional comments (optional):", key="latest_news_comments")

if st.button("Submit Satisfaction Score", key="latest_news_satisfaction_button"):
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
                "page": "latest_news"
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Thank you! Your satisfaction score and comments have been saved.")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")

# --- Pagination for Articles ---
st.sidebar.markdown("---")
articles_per_page = st.sidebar.slider("Articles per load:", 5, 20, 10)

if st.sidebar.button("Load More Articles"):
    current_count = len(st.session_state.latest_articles)
    new_articles = load_latest_articles(current_count + articles_per_page)
    
    if len(new_articles) > current_count:
        st.session_state.latest_articles = new_articles
        st.session_state.latest_article_contents = [format_article(article) for article in new_articles]
        st.rerun()
    else:
        st.sidebar.warning("No more articles available.")
        
streamlit_analytics.stop_tracking()