import streamlit as st
import pandas as pd
from streamlit_extras.switch_page_button import switch_page

from Login import (
    client, db, users_collection, format_article, load_css,
    authenticate_user
)


db = client["techcrunch_db"]
new_init_db = db["new_init"]

# Load CSS and set title
load_css()
st.title("Topic Preferences")

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
if user and "user_interests" in user:
    st.success(f"Your preferences are already set")
    
    # Display current preferences
    if "user_interests" in user:
        interests = user["user_interests"]
        # st.write("Your current preferences:")
        
        # if "categories" in interests:
        #     st.write("**Selected Categories:**")
        #     for category in interests["categories"]:
        #         st.write(f"- {category}")
        
        # # Add edit button
        # if st.button("Edit My Preferences"):
        #     # Load previous selections into session state
        #     st.session_state.edit_mode = True
        #     if "user_selections" not in st.session_state:
        #         st.session_state.user_selections = {}
                
        #         # Try to reconstruct selections from saved interests
        #         if "selection_keys" in interests:
        #             for key in interests["selection_keys"]:
        #                 parts = key.split("|")
        #                 if len(parts) == 2:
        #                     category = parts[0]
        #                     subcategory = parts[1]
        #                     sources = []
        #                     # Find the sources for this selection
        #                     if subcategory == "general" and category in interests["sources_by_selection"]:
        #                         sources = interests["sources_by_selection"][category]
        #                     elif f"{category}|{subcategory}" in interests["sources_by_selection"]:
        #                         sources = interests["sources_by_selection"][f"{category}|{subcategory}"]
                                
        #                     st.session_state.user_selections[key] = {
        #                         "category": category,
        #                         "subcategory": subcategory,
        #                         "sources": sources
        #                     }
        #     st.rerun()
        # else:
        st.write("You can now proceed to the Curated Articles or Random Articles pages.")
        st.stop()

# Load category information from the new_init collection
def load_category_info():
    try:
        category_data = new_init_db.find_one({})
        if category_data:
            # Remove the MongoDB _id field
            if "_id" in category_data:
                del category_data["_id"]
            return category_data
        return {}
    except Exception as e:
        st.error(f"Error loading category information: {e}")
        return {}

# Initialize session state for selected categories if not already set
if "user_selections" not in st.session_state:
    st.session_state.user_selections = {}

# Initialize expanded categories in session state if not already set
if "expanded_categories" not in st.session_state:
    st.session_state.expanded_categories = set()

# Get category information
categories = load_category_info()
# Do NOT pre-check everything — we will only initialize visible ones later
if "user_selections" not in st.session_state:
    st.session_state.user_selections = {}

if "visible_topics" not in st.session_state:
    st.session_state.visible_topics = set()

st.write("Please select topics you're interested in. Click on a topic to view subtopics.")

# Inject custom CSS for the cards and inline checkboxes
st.markdown("""
<style>
    .category-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        height: 100%;
    }
    .category-title {
        font-size: 20px;
        font-weight: bold;
        color: white;
        margin-bottom: 15px;
        padding: 8px 0;
        text-align: center;
        border-bottom: 1px solid #333;
        cursor: pointer;
    }
    .category-title:hover {
        background-color: #333;
    }
    .stCheckbox {
        display: inline-block !important;
        margin-right: 20px !important;
        min-width: 150px !important;
        margin-bottom: 5px !important;
    }
    .stCheckbox > label {
        display: inline-flex !important;
        align-items: center !important;
    }
    .element-container {
        margin-bottom: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    .checkbox-grid {
        display: flex;
        flex-wrap: wrap;
    }
    .checkbox-grid > div {
        min-width: 200px;
        flex: 1 0 auto;
    }
    .subtopics-container {
        margin-top: 0px;
        padding: 10px;
        background-color: transparent;
        border-radius: 0px;
    }
    .category-button {
        width: 100%;
        text-align: left;
        padding: 10px;
        background-color: #1E1E1E;
        border: 1px solid #333;
        color: white;
        font-weight: bold;
        cursor: pointer;
        border-radius: 5px;
        margin-bottom: 10px;
        transition: background-color 0.3s;
    }
    .category-button:hover {
        background-color: #333;
    }
</style>
""", unsafe_allow_html=True)


# Display categories in a grid
cols = st.columns(2)
col_idx = 0

# Helper function to toggle category expansion
def toggle_category(category_name):
    if category_name in st.session_state.expanded_categories:
        st.session_state.expanded_categories.remove(category_name)
    else:
        st.session_state.expanded_categories.add(category_name)

# Process categories
for category_name, category_data in categories.items():
    with cols[col_idx]:
        # Create button for each category
        if st.button(f"{category_name}", key=f"btn_{category_name}", use_container_width=True):
            toggle_category(category_name)
            st.rerun()
        
        # Display subcategories if this category is expanded
        if category_name in st.session_state.expanded_categories:
            st.markdown("<div class='subtopics-container'>", unsafe_allow_html=True)
            # Add to visible topics
            if isinstance(category_data, dict):
                for subcat in category_data:
                    st.session_state.visible_topics.add(f"{category_name}|{subcat}")
            else:
                st.session_state.visible_topics.add(f"{category_name}|general")
            
            # Create a container for all checkboxes
            checkbox_container = st.container()
            
            with checkbox_container:
                if isinstance(category_data, dict):
                    # Determine how many subcategories we have
                    num_subcategories = len(category_data)
                    # Determine optimal number of columns (up to 3)
                    num_cols = min(3, num_subcategories)
                    
                    # Create columns for the checkboxes
                    checkbox_cols = st.columns(num_cols)
                    
                    # Distribute subcategories across columns
                    subcategory_items = list(category_data.items())
                    items_per_col = -(-num_subcategories // num_cols)  # Ceiling division
                    
                    for i, (subcategory_name, sources) in enumerate(subcategory_items):
                        col_index = i // items_per_col
                        if col_index >= num_cols:  # Safety check
                            col_index = num_cols - 1
                        
                        checkbox_key = f"{category_name}|{subcategory_name}"
                        with checkbox_cols[col_index]:
                            
                            # Create the checkbox
                            is_checked = st.checkbox(
                                subcategory_name, 
                                key=checkbox_key,
                                value=True  
                            )
                        
                         # Only update if visible and checked
                        if is_checked:
                            st.session_state.user_selections[checkbox_key] = {
                                "category": category_name,
                                "subcategory": subcategory_name,
                                "sources": sources
                            }
                        elif checkbox_key in st.session_state.user_selections:
                            del st.session_state.user_selections[checkbox_key]

                else:
                    # Handle categories that are just lists of sources
                    checkbox_key = f"{category_name}|general"
                    
                    
                    is_checked = st.checkbox(
                        f"{category_name} (General)", 
                        key=checkbox_key,
                        value=True
                    )
                    
                    # Update user selections
                    if is_checked:
                        st.session_state.user_selections[checkbox_key] = {
                            "category": category_name,
                            "subcategory": "general",
                            "sources": category_data
                        }
                    elif checkbox_key in st.session_state.user_selections:
                        del st.session_state.user_selections[checkbox_key]
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Toggle column index for next category
        col_idx = (col_idx + 1) % 2

# # Display a summary of selected topics
# if st.session_state.user_selections:
#     st.subheader("Your Selected Topics:")
#     for key, selection in st.session_state.user_selections.items():
#         if selection["subcategory"] == "general":
#             st.write(f"- {selection['category']} (General)")
#         else:
#             st.write(f"- {selection['category']}: {selection['subcategory']}")

if st.button("Save My Preferences", type="primary"):
    # Filter selections to include only visible and checked topics
    visible_checked_selections = {
        key: val for key, val in st.session_state.user_selections.items()
        if key in st.session_state.visible_topics
    }

    if not visible_checked_selections:
        st.error("Please select at least one topic or subtopic.")
    else:
        user_interests = {
            "categories": list(set([item["category"] for item in visible_checked_selections.values()])),
            "subcategories": list(set([f"{item['category']}: {item['subcategory']}" for item in visible_checked_selections.values()
                                       if item["subcategory"] != "general"])),
            "sources": list(set([source for item in visible_checked_selections.values()
                                 for source in item["sources"]])),
            "selection_keys": list(visible_checked_selections.keys()),
            "sources_by_selection": {key: item["sources"] for key, item in visible_checked_selections.items()}
        }

        users_collection.update_one(
            {"username": st.session_state.user_name},
            {"$set": {
                "user_interests": user_interests,
                "initialized": True
            }}
        )

        st.session_state.needs_initialization = False
        st.success("Your preferences have been saved successfully!")
        st.write("You can now proceed to the Curated Articles, Latest News or Random Articles pages using the side bar.")
        st.rerun()
        # if st.button("Start Exploring Articles"):
        #     # st.session_state.needs_initialization = False
        #     switch_page("02_Curated_Articles")