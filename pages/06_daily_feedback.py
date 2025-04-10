import streamlit as st
from datetime import datetime
from Login import (
    format_article,
    load_css,
    top_stories,
    highlight_feedback_collection,
    track_user_article_feedback,
    update_user_embedding,
    users_collection,
    rankings_collection
)
import uuid
import streamlit_analytics

streamlit_analytics.start_tracking()
load_css()
st.title("News by Date")

username = st.session_state.get("user_name")
selected_date = st.date_input("Choose a date to see news from that day:", datetime.today())
start_of_day = datetime.combine(selected_date, datetime.min.time())
end_of_day = datetime.combine(selected_date, datetime.max.time())

# Query articles from MongoDB
articles = list(top_stories.find({
    "published": {
        "$gte": start_of_day,
        "$lte": end_of_day
    }
}).sort("published", -1))

submit_scores_clicked = st.sidebar.button("📤 Submit All Rankings")
total_articles = len(articles)

if articles:
    st.success(f"Found {total_articles} article(s) from {selected_date.strftime('%Y-%m-%d')}.")

    # Initialize rank session state
    for i, article in enumerate(articles):
        rank_key = f'article_rank_{i}'
        if rank_key not in st.session_state:
            st.session_state[rank_key] = i + 1  # Default rank

    # Build a list of articles with ranks
    ranked_articles = []
    for i, article in enumerate(articles):
        rank = st.session_state.get(f'article_rank_{i}', i + 1)
        ranked_articles.append((rank, i, article))  # (rank, original_index, article)

    # Sort articles by rank
    ranked_articles.sort(key=lambda x: x[0])

    # Display sorted articles
    for display_index, (rank, i, article) in enumerate(ranked_articles):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(format_article(article), unsafe_allow_html=True)

        with col2:
            highlights = article.get("highlights", [])
            if highlights:
                highlight_key = f'highlight_index_by_date_{i}'
                if highlight_key not in st.session_state:
                    st.session_state[highlight_key] = 0
                current_index = st.session_state[highlight_key]
                total_highlights = len(highlights)
                current_highlight = highlights[current_index][:250] + "..." if len(highlights[current_index]) > 250 else highlights[current_index]
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
            rank_key = f'article_rank_{i}'
            current_rank = st.session_state.get(rank_key, i + 1)
            used_ranks = [
                st.session_state.get(f'article_rank_{j}')
                for j in range(total_articles) if j != i
            ]
            possible_ranks = [r for r in range(1, total_articles + 1) if r not in used_ranks or current_rank == r]

            # Corrected: no assignment to session_state here
            selected_rank = st.selectbox(
                "Rank",
                options=possible_ranks,
                index=possible_ranks.index(current_rank),
                key=rank_key
            )

            score = st.number_input("Score", -1, 1, 0, key=f'article_score_{i}')
            feedback = ""
            if score == -1:
                feedback = st.text_area("Feedback", key=f'article_feedback_{i}', height=80)

            st.session_state[f'article_data_{i}'] = {
                "article": article,
                "rank": st.session_state[f'article_rank_{i}'],
                "score": score,
                "feedback": feedback
            }

            # Highlight scoring
            if highlights:
                highlight_score = st.number_input(
                    'Highlight Score', -1, 1, 0, key=f'date_score_highlight_{i}_{current_index}'
                )
                highlight_feedback = ""
                if highlight_score == -1:
                    highlight_feedback = st.text_area("Highlight Feedback", key=f'date_feedback_highlight_{i}_{current_index}', height=80)

                if st.button("Submit Highlight Score", key=f'submit_date_highlight_{i}_{current_index}'):
                    if not username:
                        st.error("Please log in to submit feedback.")
                    else:
                        try:
                            highlight_feedback_collection.insert_one({
                                "article_id": str(article.get("_id")),
                                "article_title": article.get("title"),
                                "highlight_index": current_index,
                                "highlight_text": current_highlight,
                                "score": highlight_score,
                                "feedback": highlight_feedback,
                                "user_name": username,
                                "submission_id": str(uuid.uuid4()),
                                "timestamp": datetime.now(),
                                "page": "news_by_date"
                            })
                            st.success("Highlight feedback submitted.")
                        except Exception as e:
                            st.error(f"Error: {e}")

                if len(highlights) > 1:
                    if st.button("Next Highlight", key=f'next_highlight_by_date_{i}'):
                        st.session_state[highlight_key] = (st.session_state[highlight_key] + 1) % total_highlights
                        st.rerun()

    # Sidebar submission
    if submit_scores_clicked:
        if not username:
            st.sidebar.error("Please log in to submit rankings.")
        else:
            all_ranks = [st.session_state.get(f'article_rank_{i}') for i in range(total_articles)]
            if len(all_ranks) != len(set(all_ranks)):
                st.sidebar.error("Ranks must be unique (no ties).")
            elif None in all_ranks:
                st.sidebar.error("Please rank all articles.")
            else:
                try:
                    submission_id = str(uuid.uuid4())
                    for i in range(total_articles):
                        data = st.session_state.get(f'article_data_{i}', {})
                        article = data.get("article")
                        ranking_data = {
                            "article_id": str(article.get("_id")),
                            "article_title": article.get("title"),
                            "user_name": username,
                            "rank": data.get("rank"),
                            "score": data.get("score"),
                            "feedback": data.get("feedback") if data.get("score") == -1 else "",
                            "submission_id": submission_id,
                            "timestamp": datetime.now(),
                            "page": "news_by_date"
                        }
                        track_user_article_feedback(username, article.get("_id"), "news_by_date")
                        if article.get("response_array"):
                            try:
                                update_user_embedding(users_collection, username, article["response_array"], data.get("score"))
                            except Exception as embed_error:
                                st.sidebar.warning(f"Embedding update failed: {embed_error}")
                        rankings_collection.insert_one(ranking_data)

                    st.sidebar.success("✅ All rankings submitted successfully!")
                except Exception as e:
                    st.sidebar.error(f"Error submitting rankings: {e}")
else:
    st.warning("No articles found for the selected date.")

streamlit_analytics.stop_tracking()
