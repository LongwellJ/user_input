import streamlit as st
import pandas as pd
import uuid
from bs4 import BeautifulSoup
import pymongo
# import streamlit_analytics
from datetime import datetime
from bson.objectid import ObjectId
import numpy as np
import math
# --- MongoDB Setup ---
MONGO_URI = st.secrets["MONGO"]["uri"]
if not MONGO_URI:
    st.error("MongoDB URI is not set in the environment variables.")
    st.stop()  # Stop the app if MongoDB URI is missing
client = pymongo.MongoClient(MONGO_URI)
db = client["techcrunch_db"]
top_stories = db["top_stories"]
rankings_collection = db["rankings"]  # MongoDB collection for rankings
satisfaction_collection = db["satisfaction"]  # MongoDB collection for satisfaction
users_collection = db["users"]  # MongoDB collection for users
highlight_feedback_collection = db["highlight_feedback"]
user_article_feedback_collection = db["user_article_feedback"]
initial_centroids = np.array([
    [1, 1, 3, 3, 4, 1, 3, 3, 1, 1, 3],  # DATA-DRIVEN Analyst
    [4, 4, 3, 4, 4, 4, 3, 3, 4, 4, 3],  # engaging storyteller
    [2, 2, 3, 3, 4, 2, 3, 3, 2, 2, 3],  # critical thinker
    [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]   # Balanced Evaluator
])
persona_index = {
    "DATA-DRIVEN Analyst": 0,
    "Engaging Storyteller": 1,
    "Critical Thinker": 2,
    "Balanced Evaluator": 3
}
def clear_article_session_data():
    session_keys = ["articles_data", "article_content", "articles_offset", "latest_articles", "latest_articles_offset", "random_article_contents", "random_articles", "popular_articles", "popular_article_contents"]
    for key in session_keys:
        if key in st.session_state:
            del st.session_state[key]

# --- User Authentication Function ---
def authenticate_user(username):
    """Check if the username exists in the users collection"""
    user = users_collection.find_one({"username": username})
    return user is not None

def check_user_initialized(username):
    """Check if the user has completed initialization (has a persona)"""
    user = users_collection.find_one({"username": username})
    return user is not None #and "persona" in user

def get_user_publishers(username):
    """Get the user's publishers data from MongoDB"""
    user = users_collection.find_one({"username": username})
    if user and "user_interests" in user and "publishers" in user["user_interests"]:
        return user["user_interests"]["publishers"]
    # Return empty default publishers dictionary if not found
    return {"TC": [], "W": [], "MG": []}

def update_session_with_user_data(username):
    """Update session state with all necessary user data after login"""
    user = users_collection.find_one({"username": username})
    if user:
        # Store user's persona in session state if it exists
        if "persona" in user:
            st.session_state.user_persona = user["persona"]
        
        # Store user's embedding in session state if it exists
        if "user_embedding" in user:
            st.session_state.user_embedding = user["user_embedding"]
        
        # Store user's publishers data in session state if it exists
        if "user_interests" in user:
            # Store the entire user_interests object
            st.session_state.user_interests = user["user_interests"]
            
            # Also store publishers separately for easy access
            if "publishers" in user["user_interests"]:
                st.session_state.publishers = user["user_interests"]["publishers"]
            else:
                st.session_state.publishers = {"TC": [], "W": [], "MG": []}
        else:
            st.session_state.publishers = {"TC": [], "W": [], "MG": []}
            st.session_state.user_interests = {}
        
        return True
    return False

# --- Common Functions ---
def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text()

def remove_footer_text(summary):
    index = summary.find("©")
    if index != -1:
        return summary[:index].rstrip()  # Remove footer and trailing whitespace
    return summary  # Return unchanged

def load_articles_vector_search(user_name, user_embedding, offset=0, limit=5):
    """
    Load articles using a vector search query on the top_stories collection,
    excluding articles the user has already provided feedback on.
    
    Args:
    - user_name (str): Username to filter out previously rated articles
    - user_embedding (list): Embedding vector for similarity search
    - offset (int): Number of documents to skip
    - limit (int): Number of documents to retrieve
    
    Returns:
    - List of articles
    """
    try:
        # Get IDs of articles user has already provided feedback on
        feedback_article_ids = get_user_feedback_article_ids(user_name)
        
        # Convert feedback article IDs to ObjectId
        feedback_article_ids = [ObjectId(article_id) for article_id in feedback_article_ids]
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "response_array",
                    "queryVector": user_embedding,
                    "numCandidates": 300,
                    # Get enough candidates so that we can later skip 'offset' and limit to 'limit'
                    "limit": offset + limit + len(feedback_article_ids)  # Increase to account for filtered out articles
                }
            },
            {
                "$match": {
                    "_id": {"$nin": feedback_article_ids}  # Exclude articles with feedback
                }
            },
            {
                "$setWindowFields": {
                    "sortBy": { "_id": 1 },
                    "output": {
                        "row_number": { "$documentNumber": {} }
                    }
                }
            },
            {
                "$match": { "row_number": { "$gt": offset } }
            },
            {
                "$limit": limit
            }
        ]
        
        results = list(db.top_stories.aggregate(pipeline))
        return results
    
    except Exception as e:
        st.error(f"Error loading articles with vector search: {e}")
        return []

def track_user_article_feedback(user_name, article_id, feedback_type):
    """
    Track user's feedback on a specific article.
    
    Args:
    - user_name (str): Username of the user
    - article_id (str): Unique identifier of the article
    - feedback_type (str): Type of feedback (e.g., 'ranking', 'highlight')
    """
    try:
        # Check if feedback already exists
        existing_feedback = user_article_feedback_collection.find_one({
            "user_name": user_name,
            "article_id": str(article_id),
            "feedback_type": feedback_type
        })
        
        if not existing_feedback:
            # If no existing feedback, insert a new document
            feedback_record = {
                "user_name": user_name,
                "article_id": str(article_id),
                "feedback_type": feedback_type,
                "timestamp": datetime.now()
            }
            user_article_feedback_collection.insert_one(feedback_record)
    except Exception as e:
        st.error(f"Error tracking user article feedback: {e}")

def get_user_feedback_article_ids(user_name, feedback_type=None):
    """
    Retrieve article IDs that the user has already provided feedback on.
    
    Args:
    - user_name (str): Username of the user
    - feedback_type (str, optional): Specific type of feedback to filter
    
    Returns:
    - List of article IDs
    """
    try:
        query = {"user_name": user_name}
        if feedback_type:
            query["feedback_type"] = feedback_type
        
        # Retrieve all article IDs with feedback
        feedback_records = user_article_feedback_collection.find(query)
        return [record["article_id"] for record in feedback_records]
    except Exception as e:
        st.error(f"Error retrieving user feedback article IDs: {e}")
        return []

def load_latest_articles_excluding_feedback(user_name, limit=5):
    """
    Load articles excluding those the user has already given feedback on.
    
    Args:
    - user_name (str): Username of the user
    - limit (int): Number of articles to retrieve
    
    Returns:
    - List of articles
    """
    try:
        # Get IDs of articles user has already provided feedback on
        feedback_article_ids = get_user_feedback_article_ids(user_name)
        
        # Construct a query to exclude these articles
        query = {"_id": {"$nin": [ObjectId(article_id) for article_id in feedback_article_ids]}}
        
        # Retrieve new articles
        new_articles = list(top_stories.find(query).sort("published", -1).limit(limit))
        
        return new_articles
    except Exception as e:
        st.error(f"Error loading articles excluding feedback: {e}")
        return []
    

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
        formatted_date = raw_published_date
    else:
        formatted_date = "No publication date available"

    authors = article.get("authors", [])
    authors_text = ", ".join(authors) if authors else "No author information available"
    duration = article.get("duration", None)
    distance = article.get("distance", "N/A")
    if distance == "N/A":
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
    else:
            article_html = f"""
        <a href="{url}" target="_blank">
            <div class="article-card">
                <h3 style="font-size: 20px; font-weight: bold;">{title}</h3>
                <p style="font-size: 16px; color: inherit;">{content}</p>
                <p class="inline-info"><span>Published:</span> {formatted_date},</p>
                <p class="inline-info"><span>Author(s):</span> {authors_text},</p>
                <p class="inline-info"><span>Duration:</span> {duration},</p>
                <p class="inline-info"><span>Distance:</span> {distance}</p>
            </div>
        </a>
    """
    return article_html

def update_negative_embedding_combined(current_embedding, article_response_array, global_embedding_centroid):
    """
    Combine multiple strategies for more robust negative feedback update.
    
    Args:
    - current_embedding: Current user embedding
    - article_response_array: Embedding of the current article
    - global_embedding_centroid: Average embedding of all articles
    
    Returns:
    - Updated embedding
    """
    # Calculate Euclidean distance
    distance = math.sqrt(
        sum((current_embedding[i] - article_response_array[i])**2 for i in range(len(current_embedding)))
    )
    
    # Randomized perturbation
    perturbation = np.random.normal(
        loc=0, 
        scale=0.3,  # Controlled randomness
        size=len(current_embedding)
    )
    
    # Combine multiple strategies
    updated_embedding = [
        current_embedding[i] + 
        0.4 * (global_embedding_centroid[i] - article_response_array[i]) +  # Global centroid push
        0.3 * (current_embedding[i] - article_response_array[i]) * (1 / (1 + distance)) +  # Distance-scaled push
        0.3 * perturbation[i]  # Random perturbation
        for i in range(len(current_embedding))
    ]
    
    return updated_embedding

def update_user_embedding(users_collection, user_name, article_response_array, feedback_score):
    """
    Update the user's embedding with sophisticated handling of negative feedback.
    
    Args:
    - users_collection: MongoDB collection for users
    - user_name: Username of the current user
    - article_response_array: Response array from the current article
    - feedback_score: Score given to the article (-1, 0, or 1)
    
    Returns:
    - Updated user embedding as a list of 11 floats
    """
    # Find the current user
    user_data = users_collection.find_one({"username": user_name})
    persona_index_value = persona_index.get(user_data.get("persona", None), 3)
    if not user_data:
        st.error(f"User {user_name} not found.")
        return None
    
    # Get the current user embedding or initialize if not exists
    current_embedding = user_data.get('user_embedding', None)
    
    # Get the current number of feedback submissions
    feedback_count = user_data.get('feedback_count', 0)
    
    # Calculate new embedding based on feedback score
    if current_embedding is None:
        # First feedback submission
        new_embedding = article_response_array
        feedback_count = 1
    else:
        if feedback_score == -1:
            new_embedding = update_negative_embedding_combined(current_embedding=current_embedding, article_response_array=article_response_array, global_embedding_centroid=initial_centroids[persona_index_value])
            print("Negative feedback received. Updated embedding:", new_embedding)
            feedback_count += 1
        elif feedback_score == 1:
            # Positive feedback: double the weight
            new_embedding = [
                ((current_embedding[i] * feedback_count) + (article_response_array[i] * 2)) 
                / (feedback_count + 2)
                for i in range(len(current_embedding))
            ]
            feedback_count += 2
        else:  # feedback_score == 0
            # Neutral feedback: standard update method
            new_embedding = [
                ((current_embedding[i] * feedback_count) + article_response_array[i]) 
                / (feedback_count + 1)
                for i in range(len(current_embedding))
            ]
            feedback_count += 1
    
    # Update user document
    users_collection.update_one(
        {"username": user_name},
        {
            "$set": {
                "user_embedding": new_embedding,
                "feedback_count": feedback_count
            }
        }
    )
    
    # Also update session state with the new embedding
    st.session_state.user_embedding = new_embedding
    
    return new_embedding

def load_random_articles(limit=5):
    try:
        random_articles = list(top_stories.aggregate([{"$sample": {"size": limit}}]))
        return random_articles
    except Exception as e:
        st.error(f"Error loading random articles from MongoDB: {e}")
        return []

# article loading function
def load_latest_articles(user_name=None, limit=5):
    if user_name:
        # Use the new function that excludes previously rated articles
        return load_latest_articles_excluding_feedback(user_name, limit)
    else:
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

def load_articles_from_mongodb(user_name=None, offset=0, limit=5, collection=None):
    """
    Load articles from a MongoDB collection, optionally excluding previously rated articles.
    
    Args:
    - user_name (str, optional): Username to filter out previously rated articles
    - offset (int): Number of documents to skip
    - limit (int): Number of documents to retrieve
    - collection (MongoDB collection, optional): Collection to query
    
    Returns:
    - List of articles
    """
    try:
        # If no collection is provided, default to "Critical Thinker"
        if collection is None:
            collection = db["Critical Thinker"]
        
        # If a username is provided, exclude articles already rated
        if user_name:
            # Get IDs of articles user has already provided feedback on
            feedback_article_ids = get_user_feedback_article_ids(user_name)
            
            # Construct a query to exclude these articles
            query = {"_id": {"$nin": [ObjectId(article_id) for article_id in feedback_article_ids]}}
            print(query)
            # Retrieve new articles
            articles = list(collection.find(query).skip(offset).limit(limit))
            
            return articles
        else:
            # If no username, just return articles normally
            articles = list(collection.find().skip(offset).limit(limit))
            return articles
    
    except Exception as e:
        st.error(f"Error loading articles from MongoDB: {e}")
        return []
    
# --- Common CSS Styles ---
def load_css():
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

# --- Initialize Session State ---
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "needs_initialization" not in st.session_state:
    st.session_state.needs_initialization = False
if "publishers" not in st.session_state:
    st.session_state.publishers = {"TC": [], "W": [], "MG": []}

# --- Home Page (User Form) ---
def main():
    st.set_page_config(page_title="Login", layout="wide")
    st.title("Read My Sources")
    load_css()
    
    user_name = st.text_input("Enter your username:", value=st.session_state.user_name)
    
    # Create two columns
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            if not user_name.strip():
                st.error("Please enter a username to login.")
            else:
                st.session_state.user_name = user_name
                clear_article_session_data()
                
                # Check if user exists in the MongoDB collection
                existing_user = users_collection.find_one({"username": user_name})
                
                if existing_user:
                    # User exists
                    st.session_state.is_valid_user = True
                    
                    # Update session with all necessary user data including publishers
                    update_session_with_user_data(user_name)
            
                    # Check if the user has a persona
                    if check_user_initialized(user_name):
                        st.success(f"Welcome back, {user_name}! You can now access the curated articles.")
                        # Display the publishers data that's now available in session state
                        st.write("Your publisher preferences are loaded and ready to use.")
                        st.write("Please use the navigation to view articles.")
                    else:
                        st.session_state.needs_initialization = True
                        st.warning(f"Welcome, {user_name}! You need to complete a quick initialization process.")
                        st.write("Please go to the Initialization page in the navigation menu.")
                else:
                    # User doesn't exist - create new account
                    users_collection.insert_one({
                        "username": user_name, 
                        "created_at": datetime.now()
                    })
                    st.session_state.is_valid_user = True
                    st.session_state.needs_initialization = True
                    st.success(f"New account created for {user_name}!")
                    st.warning("Please complete the initialization process.")
                    st.write("Go to the Initialization page in the navigation menu.")

    with col2:
        if st.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.warning("Logged out")

if __name__ == "__main__":
    main()