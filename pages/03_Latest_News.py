# pages/03_Latest_News.py
import streamlit as st
import pandas as pd
from datetime import datetime
from Login import client, db, format_article, load_css
from google_analytics import inject_ga

# Inject Google Analytics
inject_ga()
# Load CSS
load_css()

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
    st.write("Browse the latest news articles:")
    
    # Create a date filter
    all_dates = []
    for article in st.session_state.latest_articles:
        if article.get("published"):
            # Extract just the date part (first 10 characters: YYYY-MM-DD)
            date_str = article.get("published")[:10]
            all_dates.append(date_str)
    
    # Get unique dates
    unique_dates = sorted(set(all_dates), reverse=True)
    
    
    # Display articles
    articles_displayed = 0
    for i, article in enumerate(st.session_state.latest_articles):
        # Check if article should be displayed based on date filter
        show_article = True
        if show_article:
            st.markdown(st.session_state.latest_article_contents[i], unsafe_allow_html=True)
            articles_displayed += 1
    
    if articles_displayed == 0:
        st.info("No articles to display.")

# Add pagination controls
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