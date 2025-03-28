import streamlit as st
import pandas as pd
from datetime import datetime
from Login import client, db, format_article, load_css, rankings_collection, top_stories, users_collection, satisfaction_collection
import uuid

# Load CSS
load_css()
st.title("Most Popular Articles")

def get_popular_articles(limit=10):
    """
    Retrieve the most popular articles based on ranking scores.
    
    Args:
    - limit (int): Number of top articles to retrieve
    
    Returns:
    - List of most popular articles from top_stories collection
    """
    try:
        # Aggregate rankings to calculate total scores for each article
        ranking_pipeline = [
            {
                "$group": {
                    "_id": "$title",
                    "total_score": {"$sum": "$rank"}
                }
            },
            {
                "$sort": {"total_score": -1}
            },
            {
                "$limit": limit
            }
        ]
        
        popular_rankings = list(rankings_collection.aggregate(ranking_pipeline))
        
        # Retrieve full article details for popular articles
        popular_articles = []
        for ranking in popular_rankings:
            article = top_stories.find_one({"title": ranking['_id']})
            if article:
                # Add total score to the article dictionary
                article['total_score'] = ranking['total_score']
                popular_articles.append(article)
        
        return popular_articles
    
    except Exception as e:
        st.error(f"Error retrieving popular articles: {e}")
        return []

# Initialize session state for popular articles
if "popular_articles" not in st.session_state:
    st.session_state.popular_articles = get_popular_articles()
    st.session_state.popular_article_contents = [format_article(article) for article in st.session_state.popular_articles]

# Refresh button
if st.sidebar.button("Refresh Popular News"):
    st.session_state.popular_articles = get_popular_articles()
    st.session_state.popular_article_contents = [format_article(article) for article in st.session_state.popular_articles]

# Display popular articles
if not st.session_state.popular_articles:
    st.error("No popular articles available to display.")
else:
    st.write("Most Popular Articles Based on User Rankings:")
    st.session_state.popular_article_contents = [format_article(article) for article in st.session_state.popular_articles]
    for i, article in enumerate(st.session_state.popular_articles):
        # Create two columns: one for article, one for details
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(st.session_state.popular_article_contents[i], unsafe_allow_html=True)
        
        with col2:
            # Display popularity metrics
            st.markdown(f"""
                <div class="article-card" style="background-color: #444444 !important;">
                    <h4>Popularity Metrics</h4>
                    <p><strong>Total Score:</strong> {article.get('total_score', 'N/A')}</p>
                    <p><strong>Ranking Trend:</strong> {'Positive' if article.get('total_score', 0) > 0 else 'Neutral/Negative'}</p>
                </div>
            """, unsafe_allow_html=True)

# Sidebar controls for customization
st.sidebar.markdown("---")
popular_articles_count = st.sidebar.slider("Number of Popular Articles:", 5, 20, 10)

if st.sidebar.button("Update Popular Articles"):
    st.session_state.popular_articles = get_popular_articles(popular_articles_count)
    st.session_state.popular_article_contents = [format_article(article) for article in st.session_state.popular_articles]
    st.rerun()

# Satisfaction Survey (Similar to Latest News page)
st.markdown("---")
st.subheader("Satisfaction Survey")
st.write("Please rate your experience with these popular article recommendations.")

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="popular_news_satisfaction")
comments = st.text_area("Additional comments (optional):", key="popular_news_comments")

if st.button("Submit Satisfaction Score", key="popular_news_satisfaction_button"):
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
                "page": "popular_news"
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Thank you! Your satisfaction score and comments have been saved.")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")