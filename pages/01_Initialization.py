#05_init_test.py
import streamlit as st
import pandas as pd
import json
import numpy as np
import html  # For unescaping HTML if it's stored with entities
from Login import (
    client, db, users_collection, format_article, load_css,
    authenticate_user
)

# Optional: Set a wide page layout so columns have more space
# st.set_page_config(page_title="User Initialization", layout="wide")

db = client["techcrunch_db"]
init_db = db["initiate_new"]

initial_centroids = np.array([
    [1, 1, 3, 3, 4, 1, 3, 3, 1, 1, 3],  # DATA-DRIVEN Analyst
    [4, 4, 3, 4, 4, 4, 3, 3, 4, 4, 3],  # engaging storyteller
    [2, 2, 3, 3, 4, 2, 3, 3, 2, 2, 3],  # critical thinker
    [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]   # Balanced Evaluator
])

# Load CSS and set title
load_css()
st.title("User Initialization")

# Ensure the user is logged in
if not st.session_state.get("user_name"):
    st.error("Please log in on the home page before continuing.")
    st.stop()

# Ensure the user is valid (authenticated)
if not authenticate_user(st.session_state.get("user_name", "")):
    st.error("Your account is not valid. Please log in with a valid account.")
    st.stop()

# Check if user is already initialized
user = users_collection.find_one({"username": st.session_state.user_name})
if user and "persona" in user:
    st.success(f"Your profile is initialized")
    st.write("You can now proceed to the Curated Articles or Random Articles pages.")
    st.stop()

# Load persona information from the database
def load_persona_info():
    try:
        persona_data = init_db.find_one({})
        return persona_data.get("personas", []) if persona_data else []
    except Exception as e:
        st.error(f"Error loading persona information: {e}")
        return []

# Initialize session state for persona selection if not already set
if "selected_persona" not in st.session_state:
    st.session_state.selected_persona = None

# Get persona information
personas = load_persona_info()

st.write("Please select your preferred topic focus for news and articles:")

# Inject custom CSS for the cards
st.markdown("""
<style>
    .persona-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        height: 100%;
        text-align: center; /* Center align text */
    }
    .persona-title {
        font-size: 18px;
        font-weight: bold;
        color: white;
        margin-bottom: 10px;
        padding: 8px 0;
    }
    .topic-row {
        background-color: #2A2A2A;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
        text-align: center; /* Ensure topics are centered too */
    }
    .topic-text {
        font-size: 14px;
        color: white;
        font-weight: normal;
        padding: 8px 0;
    }
    .keywords-text {
        font-size: 14px;
        color: #CCCCCC;
        font-weight: normal;
        padding: 5px 0;
    }
    .keyword {
        color: #CCCCCC;
    }
    .select-button {
        background-color: #333333;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 8px 10px;
        cursor: pointer;
        width: 100%;
        text-align: center;
        margin-top: 10px;
    }
    .select-button:hover {
        background-color: #444444;
    }
</style>
""", unsafe_allow_html=True)

# Display personas in a grid with styling similar to the reference
cols = st.columns(4)

for idx, persona in enumerate(personas):
    with cols[idx % 4]:
        # Unescape persona title
        persona_title = html.unescape(persona.get('persona', 'Unknown Persona'))
        
        # Add topic content
        for topic in persona.get('topics', []):
            summary = html.unescape(topic.get('summary', 'No summary available'))
            keywords_list = topic.get('keywords', [])
            
            st.markdown(f"""
            <div class="topic-row">
                <div class="persona-title">Topic:</div>
                <div class="topic-text">{summary}</div>
                <div class="keywords-text">
                    <div class="topic-text">Keywords:</div>
                    <span class="keyword">{', '.join(keywords_list[:10])}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Close the card container - no custom select button here
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Persona selection button
        if st.button(f"Select this persona", key=f"button-{idx}"):
            # Map document index to persona
            persona_map = {
                0: "Data-Driven Analyst",
                1: "Engaging Storyteller",
                2: "Critical Thinker",
                3: "Balanced Evaluator"
            }
            persona = persona_map.get(idx, "Unknown Persona")
            
            # Determine the user embedding based on the selected persona
            embedding_index = list(persona_map.keys())[list(persona_map.values()).index(persona)]
            user_embedding = [float(x) for x in initial_centroids[embedding_index].tolist()]
            
            # Update the user's profile with persona and embedding
            users_collection.update_one(
                {"username": st.session_state.user_name},
                {"$set": {
                    "persona": persona,
                    "user_embedding": user_embedding
                }}
            )
            
            # Update session state
            st.session_state.selected_persona = persona
            st.session_state.needs_initialization = False
            
            # Show success message
            st.success(f"Initialization complete! Your profile has been updated with persona: {persona}")
            st.rerun()

if st.session_state.selected_persona:
    st.write(f"You have selected: **{st.session_state.selected_persona}**")
    st.write("You can now proceed to the Curated Articles, Latest News or Random Articles pages using the side bar.")
    
    if st.button("Start Exploring Articles"):
        st.session_state.needs_initialization = False
        st.rerun()