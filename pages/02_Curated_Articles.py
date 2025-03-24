import streamlit as st
import pandas as pd
import uuid
from Login import client, db, users_collection, rankings_collection, satisfaction_collection, format_article, load_articles_from_mongodb, load_css, authenticate_user
import streamlit_analytics

# Load CSS
load_css()
streamlit_analytics.start_tracking()
st.title("Curated Articles")
# st.set_page_config(page_title="Curated Articles", layout="wide")
# Check if user is valid using MongoDB authentication
if not st.session_state.get("is_valid_user", False) or not authenticate_user(st.session_state.get("user_name", "")):
    st.error("You need to be logged in as a valid user to view this page.")
    st.write("Please go back to the home page and enter a valid username.")
    st.stop()

# --- Determine the Collection Based on User's Persona ---
# Get the user's profile from the users collection
user_data = users_collection.find_one({"username": st.session_state.user_name})
# print(st.session_state)
# Default to "Critical Thinker" if no persona is found
persona = user_data.get("persona", "Critical Thinker")

# Map persona to the corresponding collection
if persona == "Data-Driven Analyst":
    selected_collection = db["Data-Driven Analyst"]
elif persona == "Engaging Storyteller":
    selected_collection = db["Engaging Storyteller"]
elif persona == "Critical Thinker":
    selected_collection = db["Critical Thinker"]
elif persona == "Balanced Evaluator":
    selected_collection = db["Balanced Evaluator"]
elif persona == "Other":
    selected_collection = db["Other"]
else: 
    selected_collection = db["Engaging Storyteller"]

# print(selected_collection)
# --- Initialize session state variables for articles if not already done ---
if "articles_data" not in st.session_state:
    st.session_state.articles_data = load_articles_from_mongodb(offset=0, limit=5, collection=selected_collection)
if "article_content" not in st.session_state:
    st.session_state.article_content = [format_article(article) for article in st.session_state.articles_data]
if "articles_offset" not in st.session_state:
    st.session_state.articles_offset = 5

# --- Sidebar: Load More Button ---
if st.sidebar.button("Load More"):
    new_articles = load_articles_from_mongodb(offset=st.session_state.articles_offset, limit=5, collection=selected_collection)
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

for i, article_html in enumerate(st.session_state.article_content):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(article_html, unsafe_allow_html=True)
    with col2:
        score = st.number_input('Score', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')
    if score == -1:
        st.text_area("Additional Feedback:", key=f'feedback_{i}_article')

# --- Submit Rankings Button ---
if st.button("Submit Scores"):
    submission_id = str(uuid.uuid4())
    rankings = []
    for i, article in enumerate(st.session_state.articles_data):
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

# --- Display Submitted Rankings ---
if st.checkbox("Show submitted rankings"):
    try:
        rankings_data = list(rankings_collection.find())
        df = pd.DataFrame(rankings_data)
        if not df.empty:
            st.dataframe(df[['submission_id', 'user_name', 'title', 'rank']])
        else:
            st.info("No rankings data found.")
    except Exception as e:
        st.error(f"Error loading rankings: {e}")

# --- Satisfaction Survey (Integrated) ---
st.markdown("---")
st.subheader("Satisfaction Survey")
st.write("Please rate your experience with these article recommendations.")

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="curated_satisfaction")
comments = st.text_area("Additional comments (optional):", key="curated_comments")

if st.button("Submit Satisfaction Score", key="curated_satisfaction_button"):
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