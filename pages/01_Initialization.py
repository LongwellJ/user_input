import streamlit as st
import pandas as pd
from Login import (
    client, db, users_collection, format_article, load_css, 
    authenticate_user
)

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
    st.success(f"Your profile is already initialized with persona: {user['persona']}")
    st.write("You can now proceed to the Curated Articles or Random Articles pages.")
    st.stop()

def load_documents(start_index, num_documents=1):
    try:
        init_collection = db["initiate_old"]
        documents = list(init_collection.find().skip(start_index).limit(num_documents))
        return documents
    except Exception as e:
        st.error(f"Error loading documents: {e}")
        return []

# Initialize session state variables if not already set
if "doc1_index" not in st.session_state:
    st.session_state.doc1_index = 0  # Document 1 starts at index 0
if "doc2_index" not in st.session_state:
    st.session_state.doc2_index = 1  # Document 2 starts at index 1
if "next_doc_index" not in st.session_state:
    st.session_state.next_doc_index = 2  # Next available document index
if "last_button" not in st.session_state:
    st.session_state.last_button = None  # Records the last pressed button ("A" or "B")
if "initialization_complete" not in st.session_state:
    st.session_state.initialization_complete = False

# If initialization is marked complete, determine the surviving document and update the profile
if st.session_state.initialization_complete:
    # Determine which document survived based on the last button pressed.
    # Button A (Select Document 1) replaces Document 2, leaving Document 1 intact.
    # Button B (Select Document 2) replaces Document 1, leaving Document 2 intact.
    if st.session_state.last_button == "A":
        final_index = st.session_state.doc1_index
    elif st.session_state.last_button == "B":
        final_index = st.session_state.doc2_index
    else:
        final_index = None

    # Map document index to persona
    persona_map = {
        0: "Data-Driven Analyst",
        1: "Engaging Storyteller",
        2: "Critical Thinker",
        3: "Balanced Evaluator"#,
        # 4: "Other"
    }
    persona = persona_map.get(final_index, "Unknown Persona")
    users_collection.update_one(
        {"username": st.session_state.user_name},
        {"$set": {"persona": persona}}
    )
    st.success(f"Initialization complete! Your profile has been updated with persona: {persona}")
    st.stop()

# Load the documents based on their indices
doc1_list = load_documents(st.session_state.doc1_index, 1)
if not doc1_list:
    st.error("No document available for Document 1. Please contact the administrator.")
    st.stop()
document_1 = doc1_list[0]

doc2_list = load_documents(st.session_state.doc2_index, 1)
if not doc2_list:
    st.error("No document available for Document 2. Please contact the administrator.")
    st.stop()
document_2 = doc2_list[0]

st.write("To personalize your experience, please review the following articles and select your preference.")

# Display the two documents side by side
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Document 1")
    st.markdown(format_article(document_1), unsafe_allow_html=True)
with col2:
    st.markdown("#### Document 2")
    st.markdown(format_article(document_2), unsafe_allow_html=True)

st.write("Which article do you prefer?")
col_btn1, col_btn2 = st.columns([1, 1])

# Callback for Button A ("Select Document 1"): replaces Document 2
def update_doc2_callback():
    st.session_state.last_button = "A"
    # If we haven't yet shown the 4th document, update Document 2
    if st.session_state.next_doc_index < 4:
        st.session_state.doc2_index = st.session_state.next_doc_index
        st.session_state.next_doc_index += 1
    else:
        # Otherwise, mark initialization complete
        st.session_state.initialization_complete = True

# Callback for Button B ("Select Document 2"): replaces Document 1
def update_doc1_callback():
    st.session_state.last_button = "B"
    if st.session_state.next_doc_index < 4:
        st.session_state.doc1_index = st.session_state.next_doc_index
        st.session_state.next_doc_index += 1
    else:
        st.session_state.initialization_complete = True

with col_btn1:
    st.button("Select Document 1", use_container_width=True, on_click=update_doc2_callback)
with col_btn2:
    st.button("Select Document 2", use_container_width=True, on_click=update_doc1_callback)
