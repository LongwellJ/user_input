# pages/03_Latest_News.py
import streamlit as st
import pandas as pd
from datetime import datetime
from Login import client, db, format_article, load_css, rankings_collection, satisfaction_collection
import streamlit_analytics
import uuid

# Load CSS
load_css()
streamlit_analytics.start_tracking()
st.title("Latest News")

# --- Load Latest Articles from top_stories collection ---
def load_latest_articles(limit=10):
    try:
        # Get the top_stories collection
        top_stories = db["top_stories"]
        
        # Query articles sorted by published date in descending order (newest first)
        latest_articles = list(
            top_stories.find().sort("published", -1).limit(limit)
        )
        
        return latest_articles
    except Exception as e:
        st.error(f"Error loading latest articles: {e}")
        return []

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
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(st.session_state.latest_article_contents[i], unsafe_allow_html=True)
        
        # Add score input for each article
        with col2:
            score = st.number_input('Score this article', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')

        # If score is -1, allow feedback
        if score == -1:
            feedback = st.text_area(f"Additional Feedback for '{article['title']}'", key=f'feedback_{i}_article')

# --- Submit Rankings Button ---
if st.button("Submit Scores"):
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
                "user_name": st.session_state.user_name
            }
            if score == -1:
                feedback = st.session_state.get(f'feedback_{i}_article', '')
                ranking_data["feedback"] = feedback
            rankings.append(ranking_data)
        
        try:
            if rankings:
                rankings_collection.insert_many(rankings)
            st.success("Your rankings have been saved!")
        except Exception as e:
            st.error(f"Error saving rankings: {e}")

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
