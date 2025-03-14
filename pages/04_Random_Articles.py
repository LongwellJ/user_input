# pages/02_Random_Articles.py
import streamlit as st
import pandas as pd
import uuid
from Login import client, rankings_collection, satisfaction_collection, format_article, load_random_articles, load_css
from google_analytics import inject_ga

# Inject Google Analytics
inject_ga()
# Load CSS
load_css()

st.title("Random Articles")

# --- Load Random Articles ---
if "random_articles" not in st.session_state:
    st.session_state.random_articles = load_random_articles(limit=5)
    st.session_state.random_article_contents = [format_article(article) for article in st.session_state.random_articles]

# Button to load new random articles
if st.sidebar.button("Load New Random Articles"):
    st.session_state.random_articles = load_random_articles(limit=5)
    st.session_state.random_article_contents = [format_article(article) for article in st.session_state.random_articles]

st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")
for i, article_html in enumerate(st.session_state.random_article_contents):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(article_html, unsafe_allow_html=True)
    with col2:
        score = st.number_input('Score', min_value=-1, max_value=1, value=0, key=f'random_score_{i}_article')
    if score == -1:
        st.text_area("Additional Feedback:", key=f'random_feedback_{i}_article')

if st.button("Submit Scores", key="random_submit_scores"):
    if not st.session_state.get("user_name"):
        st.error("Please enter your name on the home page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        rankings = []
        for i, article in enumerate(st.session_state.random_articles):
            score = st.session_state.get(f'random_score_{i}_article')
            ranking_data = {
                "title": article.get("title"),
                "rank": score,
                "submission_id": submission_id,
                "user_name": st.session_state.user_name
            }
            if score == -1:
                feedback = st.session_state.get(f'random_feedback_{i}_article', '')
                ranking_data["feedback"] = feedback
            rankings.append(ranking_data)
        try:
            if rankings:
                rankings_collection.insert_many(rankings)
            st.success("Your rankings have been saved!")
        except Exception as e:
            st.error(f"Error saving rankings: {e}")

# --- Display Submitted Rankings ---
if st.checkbox("Show submitted rankings", key="random_show_submitted"):
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

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="random_satisfaction")
comments = st.text_area("Additional comments (optional):", key="random_comments")

if st.button("Submit Satisfaction Score", key="random_satisfaction_button"):
    if not st.session_state.get("user_name"):
        st.error("Please enter your name on the home page before submitting a satisfaction score.")
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