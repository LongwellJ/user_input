import streamlit as st
import sqlite3
import pandas as pd
import uuid
import random
import json
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
import re

# --- Database Setup ---
engine = create_engine('sqlite:///rankings.db', echo=False)
metadata = MetaData()

rankings_table = Table('rankings', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('item', String),
    Column('rank', Integer),
    Column('submission_id', String),
    Column('user_name', String, nullable=True)
)

satisfaction_table = Table('satisfaction', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('submission_id', String),
    Column('user_name', String, nullable=True),
    Column('satisfaction_score', Integer)
)

metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# --- Load JSON Data ---
try:
    with open("techcrunch_top_stories.json", "r", encoding="utf-8") as json_file:
        articles_data = json.load(json_file)
except Exception as e:
    st.error(f"Failed to load JSON data: {e}")
    articles_data = []

# --- Select a subset of articles ---
num_articles_to_show = min(5, len(articles_data))
random_articles = random.sample(articles_data, num_articles_to_show) if articles_data else []

# Function to clean HTML tags and ensure plain text
def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text()

# Function to remove unwanted text from the summary
def remove_footer_text(summary):
    # Updated regular expression to remove "© 2024 TechCrunch. All rights reserved. For personal use only" and anything after it
    footer_text = r"© \d{4} TechCrunch.*"
    return re.sub(footer_text, '', summary).strip()

# Function to escape $ symbols for proper display
def escape_dollars(text):
    return text.replace('$', '\\$')

# --- Streamlit App ---
st.title("Read My Sources - TechCrunch")

# --- User Name Input ---
user_name = st.text_input("Please enter your name:")

# Store article content in session state if not already stored
if "article_content" not in st.session_state:
    # Clean and format the articles only once
    st.session_state.article_content = []
    for article in random_articles:
        title = str(article.get("title", "Unknown Title"))  # Ensure title is a plain string
        raw_content = str(article.get("summary", "No summary available"))  # Ensure summary is a plain string
        content = clean_html(raw_content)[:150]  # Remove HTML tags and trim

        # Remove footer text from the summary
        content = remove_footer_text(content)

        # Escape $ symbols in title and content
        title = escape_dollars(title)
        content = escape_dollars(content)

        # Get the URL of the article
        url = article.get("link", "#")  # Fallback to '#' if no URL is available

        # Store the formatted article content in session state with a link to the article
        article_content = f"""
        <a href="{url}" target="_blank" style="text-decoration: none;">
            <div style="background-color: #333333; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); color: white;">
                <h3 style="font-size: 20px; font-weight: bold;">{title}</h3>
                <p style="font-size: 16px;">{content}...</p>
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
                rankings.append((article.get('title'), score))

        if len(set(rank for _, rank in rankings)) != len(rankings):
            st.error("All ranks must be unique.")
        else:
            session = Session()
            try:
                for title, rank_value in rankings:
                    new_ranking = rankings_table.insert().values(
                        item=title, rank=rank_value, submission_id=submission_id, user_name=user_name
                    )
                    session.execute(new_ranking)
                session.commit()
                st.success("Your rankings have been saved!")
            except Exception as e:
                session.rollback()
                st.error(f"Error saving rankings: {e}")
            finally:
                session.close()

    # Satisfaction Survey
    st.subheader("Satisfaction Survey")
    satisfaction_score = st.slider("Rate recommendations (1-10):", 1, 10, 5)
    
    if st.button("Submit Satisfaction Score", key="satisfaction_button"):
        submission_id = str(uuid.uuid4())
        session = Session()
        try:
            new_satisfaction = satisfaction_table.insert().values(
                submission_id=submission_id, user_name=user_name, satisfaction_score=satisfaction_score
            )
            session.execute(new_satisfaction)
            session.commit()
            st.success("Satisfaction score saved!")
        except Exception as e:
            session.rollback()
            st.error(f"Error saving score: {e}")
        finally:
            session.close()

    # Display Submitted Rankings
    if st.checkbox("Show submitted rankings"):
        conn = sqlite3.connect('rankings.db')
        try:
            df = pd.read_sql_query("SELECT * from rankings", conn)
            st.dataframe(df[['submission_id', 'user_name', 'item', 'rank']])
        except Exception as e:
            st.error(f"Error loading rankings: {e}")
        finally:
            conn.close()

elif user_name == "":
    pass
else:
    st.error("Please enter a valid name before proceeding.") 
