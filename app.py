import streamlit as st
import pandas as pd
import uuid
import random
from bs4 import BeautifulSoup
import pymongo
import random
import uuid
from bs4 import BeautifulSoup

# --- MongoDB Setup ---
MONGO_URI = st.secrets["MONGO"]["uri"]
if not MONGO_URI:
    st.error("MongoDB URI is not set in the environment variables.")
    st.stop()  # Stop the app if MongoDB URI is missing
client = pymongo.MongoClient(MONGO_URI)
db = client["techcrunch_db"]  # Your MongoDB database
collection = db["top_stories"]  # Your MongoDB collection
rankings_collection = db["rankings"]  # MongoDB collection for rankings
satisfaction_collection = db["satisfaction"]  # MongoDB collection for satisfaction

# --- Load Data from MongoDB randomly---
def load_articles_from_mongodb(limit=5):
    try:
        articles = collection.aggregate([{"$sample": {"size": limit}}])  # Randomly select 'limit' articles
        return list(articles)
    except Exception as e:
        st.error(f"Error loading articles from MongoDB: {e}")
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


# --- Streamlit App ---
st.title("Read My Sources - TechCrunch")

# --- Inject Custom CSS ---
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
        .article-card:hover {
            transform: scale(1.03);
        }
        a {
            text-decoration: none !important; /* Remove underline by default */
            color: inherit;
        }
        a:hover {
            text-decoration: underline !important; /* Add underline on hover */
            text-decoration-color: blue !important; /* Make the underline blue */
            text-underline-offset: 3px; /* Adjust spacing between text and underline */
        }
    </style>
""", unsafe_allow_html=True)

# --- User Name Input ---
user_name = st.text_input("Please enter your name:")

if "article_content" in st.session_state:
    del st.session_state["article_content"]

# Load articles from MongoDB
articles_data = load_articles_from_mongodb()

# --- Select a subset of articles ---
num_articles_to_show = min(5, len(articles_data))
random_articles = random.sample(articles_data, num_articles_to_show) if articles_data else []

# Store article content in session state if not already stored
if "article_content" not in st.session_state:
    # Clean and format the articles only once
    st.session_state.article_content = []
    # Loop through each article and store formatted content

    for article in random_articles:
        
        
        title = str(article.get("title", "Unknown Title"))
        raw_content = str(article.get("summary", "No summary available"))
        ###

        # All of this should be done before storing the data in the database

        # Clean the full text
        cleaned = clean_html(raw_content)
        # Create the truncated version (first 150 characters)
        truncated = cleaned[:150]
        # Determine if truncation happened (full text longer than 150)
        was_truncated = len(cleaned) > 150
        
        # Check if a footer appears in the truncated part
        if "©" in truncated:
            # Remove footer if present
            content = remove_footer_text(truncated)
            # Since footer text is removed, assume the content is complete (do not add ellipsis)
        else:
            # Remove any trailing whitespace
            content = truncated.rstrip()
            # If truncation occurred, append ellipsis
            if was_truncated:
                content += "..."
        ###    
        
        url = article.get("link", "#")
        raw_published_date = article.get("published", None)
        if raw_published_date:
            formatted_date = raw_published_date[:16]
        else:
            formatted_date = "No publication date available"

        authors = article.get("authors", [])
        authors_text = ", ".join(authors) if authors else "No author information available"

        article_content = f"""
        <a href="{url}" target="_blank">
            <div class="article-card">
                <h3 style="font-size: 20px; font-weight: bold;">{title}</h3>
                <p style="font-size: 16px; color: inherit;">{content}</p>
                <p style="font-size: 14px; color: #bbbbbb;">Published: {formatted_date}</p>
                <p style="font-size: 14px; color: #bbbbbb;">Authors: {authors_text}</p>
            </div>
        </a>
        """
        
        st.session_state.article_content.append(article_content)


if user_name:
    if not random_articles:
        st.error("No articles available to display.")
    else:
        st.title("Articles")
        st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject):")
        ranks = []

    for i, article_content in enumerate(st.session_state.article_content):
        # Create two columns: one for the content and another for the score input
        col1, col2 = st.columns([3, 1])

        with col1:
            # Display the article content using Markdown (which is already stored in session state)
            st.markdown(article_content, unsafe_allow_html=True)

        with col2:
            # Add the score input form in the second column with the label "Score"
            score = st.number_input('Score', min_value=-1, max_value=1, value=0, key=f'score_{i}_article')



    # --- Submit Rankings Button ---
    if st.button("Submit Scores"):
        submission_id = str(uuid.uuid4())

        # Collect all rankings
        rankings = []
        for i, article in enumerate(random_articles):
            score = st.session_state.get(f'score_{i}_article')
            if score is not None:
                rankings.append({
                    "title": article.get('title'),
                    "rank": score,
                    "submission_id": submission_id,
                    "user_name": user_name
                })

        try:
            # Insert rankings into MongoDB
            if rankings:
                rankings_collection.insert_many(rankings)
            st.success("Your rankings have been saved!")
        except Exception as e:
            st.error(f"Error saving rankings: {e}")


    # Satisfaction Survey
    st.subheader("Satisfaction Survey")
    satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5)

    if st.button("Submit Satisfaction Score", key="satisfaction_button"):
        submission_id = str(uuid.uuid4())
        try:
            # Insert satisfaction score into MongoDB
            satisfaction_data = {
                "submission_id": submission_id,
                "user_name": user_name,
                "satisfaction_score": satisfaction_score
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Satisfaction score saved!")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")


    # Display Submitted Rankings
    if st.checkbox("Show submitted rankings"):
        try:
            # Fetch the rankings from MongoDB
            rankings_data = list(rankings_collection.find())
            df = pd.DataFrame(rankings_data)
            st.dataframe(df[['submission_id', 'user_name', 'title', 'rank']])
        except Exception as e:
            st.error(f"Error loading rankings: {e}")

elif user_name == "":
    pass
else:
    st.error("Please enter a valid name before proceeding.")