import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from Login import (
    client, 
    db, 
    users_collection, 
    rankings_collection, 
    highlight_feedback_collection, 
    satisfaction_collection,
    top_stories, 
    format_article, 
    load_articles_from_mongodb, 
    load_css, 
    authenticate_user,
    update_user_embedding,
    load_articles_vector_search,
    track_user_article_feedback,
    get_user_feedback_article_ids
)
import streamlit_analytics

# Load CSS and start analytics tracking
load_css()
streamlit_analytics.start_tracking()
st.title("Curated Articles")

# Check if user is valid using MongoDB authentication
if not st.session_state.get("is_valid_user", False) or not authenticate_user(st.session_state.get("user_name", "")):
    st.error("You need to be logged in as a valid user to view this page.")
    st.write("Please go back to the home page and enter a valid username.")
    st.stop()

# --- Get User Profile ---
user_data = users_collection.find_one({"username": st.session_state.user_name})

# Check if user has completed the initialization process with publishers data
if not user_data or "user_interests" not in user_data or "publishers" not in user_data.get("user_interests", {}):
    st.error("You need to complete the initialization process first.")
    st.info("Please go to the Initialization page to set your preferences.")
    st.stop()

feedback_count = user_data.get("feedback_count", 0)
user_embedding = user_data.get("user_embedding", [])
# For non-vector search queries, show the latest news from the top_stories collection
selected_collection = db["top_stories"]

# --- Add Date Filter UI ---
col1, col2 = st.columns([2, 1])
with col1:
    # Date input for filtering articles
    selected_date = st.date_input(
        "Filter articles by date:",
        datetime.today(),
        help="Show articles published on this date"
    )

with col2:
    date_range = st.selectbox(
        "Date range:",
        ["Single day", "Last 3 days", "Last week", "Last month", "All time"],
        index=0,
        help="Select time period for articles"
    )

# Calculate date range based on selection
end_date = datetime.combine(selected_date, datetime.max.time())
if date_range == "Single day":
    start_date = datetime.combine(selected_date, datetime.min.time())
elif date_range == "Last 3 days":
    start_date = datetime.combine(selected_date - timedelta(days=2), datetime.min.time())
elif date_range == "Last week":
    start_date = datetime.combine(selected_date - timedelta(days=6), datetime.min.time())
elif date_range == "Last month":
    start_date = datetime.combine(selected_date - timedelta(days=29), datetime.min.time())
else:  # All time
    start_date = datetime(1970, 1, 1)  # Very old date to get all articles

def load_articles_with_date_filter(user_name, user_embedding, offset, limit, start_date, end_date, feedback_count, selected_collection):
    """Load articles with date filtering and publisher preferences"""
    try:
        # Get IDs of articles user has already provided feedback on
        feedback_article_ids = get_user_feedback_article_ids(user_name)
        
        # Convert feedback article IDs to ObjectId
        feedback_article_ids = [ObjectId(article_id) for article_id in feedback_article_ids]
        
        # Get user's publisher preferences
        user_data = users_collection.find_one({"username": user_name})
        user_interests = user_data.get("user_interests", {})
        
        # # Get TC, W, and MG preferences
        # tc_tags = user_interests.get("TC", [])
        # w_tags = user_interests.get("W", [])
        # mg_tags = user_interests.get("MG", [])
        
        # Create tags condition for TC and MG publishers
        # combined_tags = tc_tags + w_tags
        # tags_condition = {"tags": {"$in": combined_tags}} if combined_tags else {}
        
        # Create link condition for MG publisher
        # Convert MG tags to URL-friendly format (lowercase, hyphenated)
        # mg_url_patterns = []
        # for tag in mg_tags:
        #     # Convert spaces to hyphens and make lowercase
        #     url_pattern = tag.lower().replace(" ", "-")
        #     mg_url_patterns.append(url_pattern)
        
        # link_condition = {"true_link": {"$regex": "|".join(mg_url_patterns)}} if mg_url_patterns else {}
        
        # # Combine conditions with $or if both are present
        # publisher_filter = {}
        # if tags_condition and link_condition:
        #     publisher_filter = {"$or": [tags_condition, link_condition]}
        # elif tags_condition:
        #     publisher_filter = tags_condition
        # elif link_condition:
        #     publisher_filter = link_condition
        
        # Choose loading method based on feedback count and embedding
        if feedback_count >= 5 and isinstance(user_embedding, list) and len(user_embedding) > 0:
            # Vector search with date filter and publisher preferences
            match_condition = {
                "_id": {"$nin": feedback_article_ids},
                "published": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
            
            # # Add publisher filter if available
            # if publisher_filter:
            #     if "$or" in publisher_filter:
            #         match_condition["$or"] = publisher_filter["$or"]
            #     else:
            #         match_condition.update(publisher_filter)
            
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "response_array",
                        "queryVector": user_embedding,
                        "numCandidates": 500,
                        "limit": 500  # Get more candidates to allow for filtering
                    }
                },
                {
                    "$match": match_condition
                },
                {
                    "$skip": offset
                },
                {
                    "$limit": limit
                }
            ]
            
            results = list(db.top_stories.aggregate(pipeline))

            count = db.top_stories.count_documents({
                "published": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            })
            print(f"Total articles in date range: {count}")

            excluded_count = db.top_stories.count_documents({
                "published": {
                    "$gte": start_date,
                    "$lte": end_date
                },
                "_id": {"$in": feedback_article_ids}
            })
            print(f"Articles excluded due to feedback: {excluded_count}")
            print(offset, limit, start_date, end_date, feedback_count, selected_collection)
            return results
        else:
            # Regular collection query with date filter and publisher preferences
            query = {
                "_id": {"$nin": feedback_article_ids},
                "published": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
            
            # # Add publisher filter if available
            # if publisher_filter:
            #     if "$or" in publisher_filter:
            #         query["$or"] = publisher_filter["$or"]
            #     else:
            #         query.update(publisher_filter)
            
            articles = list(selected_collection.find(query).skip(offset).limit(limit))
            return articles
    except Exception as e:
        st.error(f"Error loading articles with date filter: {e}")
        return []

# --- Initialize session state variables for articles ---
# Reset article data if date filter has changed
if "last_date_filter" not in st.session_state:
    st.session_state.last_date_filter = (start_date, end_date)

if st.session_state.last_date_filter != (start_date, end_date) or "articles_data" not in st.session_state:
    # Load articles with date filter
    articles_data = load_articles_with_date_filter(
        user_name=st.session_state.user_name,
        user_embedding=user_embedding,
        offset=0,
        limit=5,
        start_date=start_date,
        end_date=end_date,
        feedback_count=feedback_count,
        selected_collection=selected_collection
    )
    
    # Update session state
    st.session_state.articles_data = articles_data
    st.session_state.article_content = [format_article(article) for article in articles_data]
    st.session_state.articles_offset = 5
    st.session_state.last_date_filter = (start_date, end_date)
    
    # Initialize article rankings (1 to N)
    if "article_rankings" not in st.session_state or len(st.session_state.articles_data) != len(st.session_state.article_rankings):
        st.session_state.article_rankings = list(range(1, len(articles_data) + 1))
    
    # Initialize the order of display
    if "display_order" not in st.session_state or len(st.session_state.display_order) != len(articles_data):
        st.session_state.display_order = list(range(len(articles_data)))
    
    if feedback_count >= 5 and isinstance(user_embedding, list) and len(user_embedding) > 0:
        st.markdown("*These articles are tailored to your interests using advanced matching*")
    else:
        st.markdown("*Latest news from top stories*")

# Display date range information
st.info(f"Showing articles from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}")

# Button to refresh latest articles
if st.sidebar.button("Refresh Curated Articles"):
    # Get the updated user embedding
    user_embedding = users_collection.find_one({"username": st.session_state.user_name}).get("user_embedding", [])
    print("This is the user_embedding", user_embedding)
    # Reset the articles data and content
    st.session_state.articles_data = []
    st.session_state.article_content = []
    # Reset the offset for loading more articles
    st.session_state.articles_offset = 5
    # Reset article rankings
    if "article_rankings" in st.session_state:
        del st.session_state.article_rankings
    # Reset display order
    if "display_order" in st.session_state:
        del st.session_state.display_order
    # Load articles with date filter
    articles_data = load_articles_with_date_filter(
        user_name=st.session_state.user_name,
        user_embedding=user_embedding,
        offset=0,
        limit=5,
        start_date=start_date,
        end_date=end_date,
        feedback_count=feedback_count,
        selected_collection=selected_collection
    )
    st.session_state.articles_data = articles_data
    st.session_state.article_content = [format_article(article) for article in articles_data]
    # Initialize article rankings (1 to N)
    st.session_state.article_rankings = list(range(1, len(articles_data) + 1))
    # Initialize display order
    st.session_state.display_order = list(range(len(articles_data)))
    st.rerun()

# --- Sidebar: Load More Button ---
if st.sidebar.button("Load More"):
    offset = st.session_state.articles_offset
    new_articles = load_articles_with_date_filter(
        user_name=st.session_state.user_name,
        user_embedding=user_embedding,
        offset=offset,
        limit=5,
        start_date=start_date,
        end_date=end_date,
        feedback_count=feedback_count,
        selected_collection=selected_collection
    )
        
    if new_articles:
        st.session_state.articles_data.extend(new_articles)
        for article in new_articles:
            st.session_state.article_content.append(format_article(article))
        
        # Extend article rankings for new articles
        current_max_rank = max(st.session_state.article_rankings) if st.session_state.article_rankings else 0
        new_ranks = list(range(current_max_rank + 1, current_max_rank + 1 + len(new_articles)))
        st.session_state.article_rankings.extend(new_ranks)
        
        # Extend display order for new articles
        current_max_display = max(st.session_state.display_order) if len(st.session_state.display_order) > 0 else -1
        new_display_indices = list(range(current_max_display + 1, current_max_display + 1 + len(new_articles)))
        st.session_state.display_order.extend(new_display_indices)
        
        st.session_state.articles_offset += len(new_articles)
    else:
        st.sidebar.warning("No more articles available for this date range.")

# Function to update rankings and reorder display when one is changed
def update_rankings(changed_index, new_rank):
    current_rank = st.session_state.article_rankings[changed_index]
    
    # Don't do anything if the rank hasn't changed
    if current_rank == new_rank:
        return
    
    # Make a copy of current rankings
    rankings = st.session_state.article_rankings.copy()
    
    # If the new rank is already assigned to another article,
    # shift all articles in between
    if new_rank in rankings:
        # Determine direction of shift
        if new_rank > current_rank:  # Moving down in rank (higher number)
            for i in range(len(rankings)):
                if current_rank < rankings[i] <= new_rank:
                    rankings[i] -= 1
        else:  # Moving up in rank (lower number)
            for i in range(len(rankings)):
                if new_rank <= rankings[i] < current_rank:
                    rankings[i] += 1
    
    # Set the new rank for the changed article
    rankings[changed_index] = new_rank
    
    # Update session state rankings
    st.session_state.article_rankings = rankings
    
    # Update the display order based on rankings
    articles_with_ranks = [(i, rank) for i, rank in enumerate(st.session_state.article_rankings)]
    articles_with_ranks.sort(key=lambda x: x[1])
    st.session_state.display_order = [idx for idx, _ in articles_with_ranks]

# --- Display Articles in Rank Order ---
if not st.session_state.articles_data:
    st.warning("No articles available for the selected date range.")
else:
    st.write("Assign a score to each item (1 = Strong Accept, 0 = Weak Accept, -1 = Reject) and rank them in order of importance:")
    
    if "display_order" not in st.session_state or len(st.session_state.display_order) != len(st.session_state.articles_data):
        st.session_state.display_order = list(range(len(st.session_state.articles_data)))
    
    if st.button("Sort Articles by Rank"):
        articles_with_ranks = [(i, rank) for i, rank in enumerate(st.session_state.article_rankings)]
        articles_with_ranks.sort(key=lambda x: x[1])
        st.session_state.display_order = [idx for idx, _ in articles_with_ranks]
        st.success("Articles sorted by rank")
    
    for display_idx, article_idx in enumerate(st.session_state.display_order):
        if article_idx >= len(st.session_state.articles_data):
            continue
            
        article = st.session_state.articles_data[article_idx]
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
    
        with col1:
            st.markdown(st.session_state.article_content[article_idx], unsafe_allow_html=True)
        
        with col2:
            highlights = article.get("highlights", [])
            if isinstance(highlights, list) and len(highlights) > 0:
                total_highlights = len(highlights)
                highlight_key = f'curated_highlight_index_{article_idx}'
                if highlight_key not in st.session_state:
                    st.session_state[highlight_key] = 0
                current_index = st.session_state[highlight_key]
                current_highlight = highlights[current_index]
                if len(current_highlight) > 250:
                    current_highlight = current_highlight[:250] + '...'
                highlight_count_text = f"Highlight {current_index + 1} of {total_highlights}"
            else:
                current_highlight = "no highlights available"
                highlight_count_text = ""
            
            url = article.get("link", "#")
            st.markdown(f"""
                <a href="{url}" target="_blank">
                    <div class="article-card">
                        <strong style="font-size: 18px;">Highlights:</strong>
                        <p style="font-size: 14px; margin-top: 5px; color: #888;">{highlight_count_text}</p>
                        <p style="font-size: 16px; font-weight: normal; text-align: left; word-wrap: break-word; margin-top: 10px;">
                            {current_highlight}
                        </p>
                    </div>
                </a>
            """, unsafe_allow_html=True)
        
        with col3:
            score = st.number_input('Article Score', min_value=-1, max_value=1, value=0, key=f'score_{article_idx}_article')
            if score == -1:
                feedback = st.text_area(f"Feedback for article", key=f'feedback_{article_idx}_article', height=80)
            
            if isinstance(highlights, list) and len(highlights) > 0:
                current_index = st.session_state.get(f'curated_highlight_index_{article_idx}', 0)
                highlight_score = st.number_input(
                    'Highlight Score', 
                    min_value=-1, 
                    max_value=1, 
                    value=0, 
                    key=f'score_{article_idx}_highlight_{current_index}'
                )
                
                if highlight_score == -1:
                    highlight_feedback = st.text_area(
                        "Feedback for highlight", 
                        key=f'feedback_{article_idx}_highlight_{current_index}',
                        height=80
                    )
                else:
                    highlight_feedback = ""
                
                if st.button("Submit Highlight Score", key=f'curated_submit_highlight_{article_idx}_{current_index}'):
                    if not st.session_state.get("user_name"):
                        st.error("Please validate your name on the Login page before submitting feedback.")
                    else:
                        try:
                            current_highlight = highlights[current_index]
                            if len(current_highlight) > 250:
                                current_highlight = current_highlight[:250] + '...'
                                
                            highlight_feedback_data = {
                                "article_id": str(article.get("_id")),
                                "article_title": article.get("title"),
                                "highlight_index": current_index,
                                "highlight_text": current_highlight,
                                "score": highlight_score,
                                "feedback": highlight_feedback,
                                "user_name": st.session_state.user_name,
                                "submission_id": str(uuid.uuid4()),
                                "timestamp": datetime.now(),
                                "page": "curated_articles"
                            }
                            highlight_feedback_collection.insert_one(highlight_feedback_data)
                            st.success("Highlight score saved!")
                        except Exception as e:
                            st.error(f"Error saving highlight score: {e}")

                if isinstance(highlights, list) and len(highlights) > 1:
                    if st.button("Next Highlight", key=f'curated_next_highlight_{article_idx}'):
                        st.session_state[highlight_key] = (st.session_state[highlight_key] + 1) % total_highlights
                        st.rerun()
        
        with col4:
            if article_idx < len(st.session_state.article_rankings):
                current_rank = st.session_state.article_rankings[article_idx]
            else:
                current_rank = article_idx + 1
                if len(st.session_state.article_rankings) == article_idx:
                    st.session_state.article_rankings.append(current_rank)
            
            st.markdown("### Rank")
            article_count = len(st.session_state.articles_data)
            new_rank = st.number_input(
                "Position", 
                min_value=1, 
                max_value=article_count,
                value=current_rank,
                key=f'rank_{article_idx}_article'
            )
            
            if new_rank != current_rank:
                update_rankings(article_idx, new_rank)
                st.rerun()
            
            st.markdown(f"**Current Rank: {current_rank}**")
            display_position = st.session_state.display_order.index(article_idx) + 1 if article_idx in st.session_state.display_order else "Unknown"
            st.markdown(f"**Display Position: {display_position}**")

# --- Submit Rankings Button ---
if st.button("Submit Article Scores and Rankings"):
    if not st.session_state.get("user_name"):
        st.error("Please validate your name on the Login page before submitting scores.")
    else:
        submission_id = str(uuid.uuid4())
        submission_timestamp = datetime.now()
        rankings = []
        for i, article in enumerate(st.session_state.articles_data):
            score = st.session_state.get(f'score_{i}_article')
            rank_position = st.session_state.article_rankings[i] if i < len(st.session_state.article_rankings) else i + 1

            track_user_article_feedback(
                st.session_state.user_name, 
                article.get("_id"), 
                "curated_articles",
            )

            ranking_data = {
                "title": article.get("title"),
                "score": score,
                "rank_position": rank_position,
                "submission_id": submission_id,
                "submission_timestamp": submission_timestamp,
                "batch_index": i,
                "batch_size": len(st.session_state.articles_data),
                "user_name": st.session_state.user_name,
                "page": "curated_articles"
            }
            if score == -1:
                feedback = st.session_state.get(f'feedback_{i}_article', '')
                ranking_data["feedback"] = feedback
            rankings.append(ranking_data)

            if article.get('response_array'):
                try:
                    updated_embedding = update_user_embedding(
                        users_collection, 
                        st.session_state.user_name, 
                        article['response_array'],
                        score
                    )
                except Exception as e:
                    st.error(f"Error updating user embedding for article {i+1}: {e}")
        
        try:
            if rankings:
                rankings_collection.insert_many(rankings)
            st.success("Your article scores and rankings have been saved!")
        except Exception as e:
            st.error(f"Error saving article scores and rankings: {e}")

# --- Satisfaction Survey (Integrated) ---
st.markdown("---")
st.subheader("Satisfaction Survey")
st.write("Please rate your experience with these article recommendations.")

satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5, key="curated_satisfaction")
comments = st.text_area("Additional comments (optional):", key="curated_comments")

if st.button("Submit Satisfaction Score", key="curated_satisfaction_button"):
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
                "page": "curated_articles"
            }
            satisfaction_collection.insert_one(satisfaction_data)
            st.success("Thank you! Your satisfaction score and comments have been saved.")
        except Exception as e:
            st.error(f"Error saving satisfaction score: {e}")

streamlit_analytics.stop_tracking()
