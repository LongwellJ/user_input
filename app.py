import streamlit as st
import pandas as pd
import uuid
from bs4 import BeautifulSoup
import pymongo

# --- MongoDB Setup ---
MONGO_URI = st.secrets["MONGO"]["uri"]
if not MONGO_URI:
    st.error("MongoDB URI is not set in the environment variables.")
    st.stop()  # Stop the app if MongoDB URI is missing
client = pymongo.MongoClient(MONGO_URI)
db = client["techcrunch_db"]  # Your MongoDB database
collection = db["Critical Thinker"]  # Your MongoDB collection
rankings_collection = db["rankings"]  # MongoDB collection for rankings
satisfaction_collection = db["satisfaction"]  # MongoDB collection for satisfaction

# --- Load Data from MongoDB with offset ---
def load_articles_from_mongodb(offset=0, limit=5):
    try:
        articles = collection.find().skip(offset).limit(limit)  # Retrieve articles using offset and limit
        return list(articles)
    except Exception as e:
        st.error(f"Error loading articles from MongoDB: {e}")
        return []
# --- Load random articles from MongoDB ---
def load_random_articles(limit=5):
    try:
        random_articles = list(collection.aggregate([{"$sample": {"size": limit}}]))
        return random_articles
    except Exception as e:
        st.error(f"Error loading random articles from MongoDB: {e}")
        return []
# --- Function to clean HTML tags and ensure plain text ---
def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text()

# --- Function to remove unwanted text from the summary if a footer exists ---
def remove_footer_text(summary):
    index = summary.find("©")
    if index != -1:
        return summary[:index].rstrip()  # Remove footer and trailing whitespace
    return summary  # Return unchanged

# --- Helper function to process an article and return the formatted HTML ---
def format_article(article):
    title = str(article.get("title", "Unknown Title"))
    raw_content = str(article.get("summary", "No summary available"))
    
    # Clean the full text
    cleaned = clean_html(raw_content)
    # Create the truncated version (first 150 characters)
    truncated = cleaned[:150]
    was_truncated = len(cleaned) > 150
    
    # Check if a footer appears in the truncated part
    if "©" in truncated:
        content = remove_footer_text(truncated)
    else:
        content = truncated.rstrip()
        if was_truncated:
            content += "..."
    
    url = article.get("link", "#")
    raw_published_date = article.get("published", None)
    if raw_published_date:
        formatted_date = raw_published_date[:16]
    else:
        formatted_date = "No publication date available"

    authors = article.get("authors", [])
    authors_text = ", ".join(authors) if authors else "No author information available"
    duration = article.get("duration", None)

    article_html = f"""
        <a href="{url}" target="_blank">
            <div class="article-card">
                <h3 style="font-size: 20px; font-weight: bold;">{title}</h3>
                <p style="font-size: 16px; color: inherit;">{content}</p>
                <p class="inline-info"><span>Published:</span> {formatted_date},</p>
                <p class="inline-info"><span>Author(s):</span> {authors_text},</p>
                <p class="inline-info"><span>Duration:</span> {duration}</p>
            </div>
        </a>
    """
    return article_html

# --- Streamlit App UI Setup ---
st.title("Read My Sources - TechCrunch")
st.markdown("""
    <style>
        .article-card {
            background-color: #333333 !important;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            color: white;
            transition: transform 0.2s ease-in-out;
        }
        .inline-info span {
            color: #ffffff;
        }
        .article-card:hover {
            transform: scale(1.03);
        }
        a {
            text-decoration: none !important;
            color: inherit;
        }
        a:hover {
            text-decoration: underline !important;
            text-decoration-color: blue !important;
            text-underline-offset: 3px;
        }
        .inline-info {
            font-size: 14px;
            color: #dddddd;
            display: inline-block;
            margin-right: 15px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- User Name Input ---
user_name = st.text_input("Please enter your name:")

# --- Validate Username ---
if user_name == "":
    # If the username is empty, do nothing
    pass
elif user_name in ["Josh", "Josh Dorsey"]:
    # Initialize session state variables for articles if not already done
    if "articles_data" not in st.session_state:
        st.session_state.articles_data = load_articles_from_mongodb(offset=0, limit=5)
    if "article_content" not in st.session_state:
        st.session_state.article_content = [format_article(article) for article in st.session_state.articles_data]
    if "articles_offset" not in st.session_state:
        st.session_state.articles_offset = 5

    # --- Sidebar: Load More Button (always accessible) ---
    if st.sidebar.button("Load More"):
        new_articles = load_articles_from_mongodb(offset=st.session_state.articles_offset, limit=5)
        if new_articles:
            # Append the new articles and their formatted content
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
        st.title("Articles")
        st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")
    
    for i, article_html in enumerate(st.session_state.article_content):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(article_html, unsafe_allow_html=True)
        with col2:
            score = st.number_input('Score', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')
        # If the score is -1, show a text area for additional feedback.
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
                "user_name": user_name
            }
            # If the score is -1, check for additional feedback.
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
    
    # --- Satisfaction Survey ---
    st.subheader("Satisfaction Survey")
    satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5)
    if st.button("Submit Satisfaction Score", key="satisfaction_button"):
        submission_id = str(uuid.uuid4())
        try:
            satisfaction_data = {
                "submission_id": submission_id,
                "user_name": user_name,
                "satisfaction_score": satisfaction_score
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Satisfaction score saved!")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")
    
    # --- Display Submitted Rankings ---
    if st.checkbox("Show submitted rankings"):
        try:
            rankings_data = list(rankings_collection.find())
            df = pd.DataFrame(rankings_data)
            st.dataframe(df[['submission_id', 'user_name', 'title', 'rank']])
        except Exception as e:
            st.error(f"Error loading rankings: {e}")
else:
    # --- Invalid Username Branch ---
    st.error("Invalid username")
    st.write("Displaying 5 random articles for exploration:")

    # Persist random articles in session state to prevent them from refreshing on every rerun
    if "random_articles" not in st.session_state:
        st.session_state["random_articles"] = load_random_articles(limit=5)
    random_articles = st.session_state["random_articles"]

    random_article_contents = [format_article(article) for article in random_articles]

    st.title("Articles")
    st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")
    for i, article_html in enumerate(random_article_contents):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(article_html, unsafe_allow_html=True)
        with col2:
            score = st.number_input('Score', min_value=-1, max_value=1, value=0, key=f'random_score_{i}_article')
        if score == -1:
            st.text_area("Additional Feedback:", key=f'random_feedback_{i}_article')

    if st.button("Submit Scores", key="random_submit_scores"):
        submission_id = str(uuid.uuid4())
        rankings = []
        for i, article in enumerate(random_articles):
            score = st.session_state.get(f'random_score_{i}_article')
            ranking_data = {
                "title": article.get("title"),
                "rank": score,
                "submission_id": submission_id,
                "user_name": user_name
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

    st.subheader("Satisfaction Survey")
    satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5)
    if st.button("Submit Satisfaction Score", key="random_satisfaction_button"):
        submission_id = str(uuid.uuid4())
        try:
            satisfaction_data = {
                "submission_id": submission_id,
                "user_name": user_name,
                "satisfaction_score": satisfaction_score
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Satisfaction score saved!")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")

    if st.checkbox("Show submitted rankings", key="random_show_submitted"):
        try:
            rankings_data = list(rankings_collection.find())
            df = pd.DataFrame(rankings_data)
            st.dataframe(df[['submission_id', 'user_name', 'title', 'rank']])
        except Exception as e:
            st.error(f"Error loading rankings: {e}")