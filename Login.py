import streamlit as st
import pandas as pd
import uuid
from bs4 import BeautifulSoup
import pymongo
import streamlit_analytics

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


# --- User Authentication Function ---
def authenticate_user(username):
    """Check if the username exists in the users collection"""
    user = users_collection.find_one({"username": username})
    return user is not None

def check_user_initialized(username):
    """Check if the user has completed initialization (has a persona)"""
    user = users_collection.find_one({"username": username})
    return user is not None and "persona" in user
# Helper function to get persona collection
def _get_persona_collection(persona):
    persona_collections = {
        "Data-Driven Analyst": db["Data-Driven Analyst"],
        "Engaging Storyteller": db["Engaging Storyteller"],
        "Critical Thinker": db["Critical Thinker"],
        "Balanced Evaluator": db["Balanced Evaluator"],
        "Other": db["Other"]
    }
    return persona_collections.get(persona, db["Engaging Storyteller"])
# --- Common Functions ---
def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text()

def remove_footer_text(summary):
    index = summary.find("©")
    if index != -1:
        return summary[:index].rstrip()  # Remove footer and trailing whitespace
    return summary  # Return unchanged

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

def load_articles_from_mongodb(offset=0, limit=5, collection=None):
    try:
        if collection is None:
            # Default to "Critical Thinker" collection if none provided.
            collection = db["Critical Thinker"]
        articles = collection.find().skip(offset).limit(limit)
        return list(articles)
    except Exception as e:
        st.error(f"Error loading articles from MongoDB: {e}")
        return []


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
            # Negative feedback: push the embedding away from the current article's embedding
            # Use a negative learning rate to move in the opposite direction
            negative_learning_rate = -0.5  # Adjust this value as needed
            new_embedding = [
                current_embedding[i] + (negative_learning_rate * (current_embedding[i] - article_response_array[i]))
                for i in range(len(current_embedding))
            ]
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
    
    return new_embedding

def load_random_articles(limit=5):
    try:

        random_articles = list(top_stories.aggregate([{"$sample": {"size": limit}}]))
        return random_articles
    except Exception as e:
        st.error(f"Error loading random articles from MongoDB: {e}")
        return []

def load_latest_articles(limit=5):
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
# if "random_article_contents" in st.session_state:
#     st.session_state.random_article_contents = []
# if "articles_data" in st.session_state:
#     st.session_state.articles_data = []
        
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
            st.session_state.user_name = user_name
            # Check if user exists in the MongoDB collection
            if authenticate_user(user_name):
                st.session_state.is_valid_user = True
        
                # Check if the user has a persona
                if check_user_initialized(user_name):
                    st.success(f"Welcome back, {user_name}! You can now access the curated articles.")
                    st.write("Please use the navigation to view articles.")
                else:
                    st.session_state.needs_initialization = True
                    st.warning(f"Welcome, {user_name}! You need to complete a quick initialization process.")
                    st.write("Please go to the Initialization page in the navigation menu.")
            else:
                st.session_state.is_valid_user = False
                st.warning("Invalid username. You can still view random articles.")
                st.write("Please use the navigation to view random articles.")

    with col2:
        if st.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.warning("Logged out")
            
    # Admin panel for user management
    with st.expander("Admin Panel"):
        st.write("Add a new user to the system:")
        new_username = st.text_input("New username:")
        if st.button("Add User"):
            if new_username:
                # Check if the user already exists
                existing_user = users_collection.find_one({"username": new_username})
                if existing_user:
                    st.error(f"Username '{new_username}' already exists!")
                else:
                    # Add the new user to the MongoDB collection without a persona
                    users_collection.insert_one({
                        "username": new_username, 
                        "created_at": pd.Timestamp.now()
                    })
                    st.success(f"User '{new_username}' added successfully! The user will need to complete initialization.")
            else:
                st.error("Please enter a username.")
        
        st.write("Current registered users:")
        try:
            users = list(users_collection.find({}, {"username": 1, "persona": 1, "_id": 0}))
            if users:
                user_df = pd.DataFrame(users)
                st.dataframe(user_df)
            else:
                st.info("No users registered yet.")
        except Exception as e:
            st.error(f"Error loading users: {e}")
        
        st.write("Delete a user:")
        delete_username = st.text_input("Enter username to delete:")
        if st.button("Delete User"):
            if delete_username:
                # Check if user exists
                existing_user = users_collection.find_one({"username": delete_username})
                if existing_user:
                    users_collection.delete_one({"username": delete_username})
                    st.success(f"User '{delete_username}' deleted successfully!")
                else:
                    st.error(f"Username '{delete_username}' does not exist!")
            else:
                st.error("Please enter a username to delete.")
       

if __name__ == "__main__":
    main()
