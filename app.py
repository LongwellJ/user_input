import streamlit as st
import sqlite3
import pandas as pd
import uuid

# --- Database Setup (SQLAlchemy) ---
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker

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

# --- Streamlit App ---
st.title("Ranked Item Input Form")

# --- User Name Input ---
user_name = st.text_input("Please enter your name:")

if user_name:
    st.write(f"Welcome, {user_name}! Please rank the following items from most to least preferred.")

    predefined_items = [
        "https://www.nytimes.com/live/2024/05/30/nyregion/trump-trial-verdict",
        "https://www.nytimes.com/2020/04/10/smarter-living/the-fine-line-between-helpful-and-harmful-authenticity.html",
        "https://www.nytimes.com/2011/06/26/arts/television/nadia-g-of-bitchin-kitchen-on-cooking-channel.html",
        "https://www.nytimes.com/2022/12/21/technology/ai-chatgpt-google-search.html",
        "https://www.nytimes.com/2023/05/30/technology/elizabeth-holmes-theranos-prison.html?campaign_id=190&emc=edit_ufn_20230530&instance_id=93825&nl=from-the-times&regi_id=95525290&segment_id=134276&te=1&user_id=421aaac52261bf3318334a61aaa178ef"
    ]

    items = []
    ranks = []

    # --- Item and Ranking Input (Side-by-Side) ---
    st.write("Assign a unique rank to each item (1 = highest rank):")
    for i, url in enumerate(predefined_items):
        col1, col2 = st.columns([3, 1])  # Create two columns: 3:1 width ratio
        with col1:
            st.markdown(f"Item {i+1}: [{url}]({url})")  # Display link in the first column
            items.append(url) # Store URL
        with col2:
            rank = st.number_input(f"Rank", min_value=1, max_value=len(predefined_items), key=f"rank_{i}")
            ranks.append(rank)

    # --- Submit Button & Data Handling ---
    if st.button("Submit Rankings"):
        submission_id = str(uuid.uuid4())

        # Input Validation
        valid = True
        if any(rank is None for rank in ranks):
            st.error("Please provide a rank for each item.")
            valid = False
        if len(set(ranks)) != len(items) and None not in ranks:
            st.error("All ranks must be unique.")
            valid = False

        # Database Insertion
        if valid:
            session = Session()
            try:
                for item_name, rank_value in zip(items, ranks):
                    new_ranking = rankings_table.insert().values(
                        item=item_name,
                        rank=rank_value,
                        submission_id=submission_id,
                        user_name=user_name
                    )
                    session.execute(new_ranking)
                session.commit()
                st.success("Your rankings have been saved!")
            except Exception as e:
                session.rollback()
                st.error(f"An error occurred: {e}")
            finally:
                session.close()

    # --- Satisfaction Survey ---
    st.subheader("Satisfaction Survey")
    satisfaction_score = st.slider("How satisfied are you with these recommendations? (1 = Not satisfied, 10 = Very satisfied)", 1, 10, 5)
    if st.button("Submit Satisfaction Score"):
        session = Session()
        try:
            new_satisfaction = satisfaction_table.insert().values(
                submission_id=submission_id,
                user_name=user_name,
                satisfaction_score=satisfaction_score
            )
            session.execute(new_satisfaction)
            session.commit()
            st.success("Your satisfaction score has been recorded!")
        except Exception as e:
            session.rollback()
            st.error(f"An error occurred: {e}")
        finally:
            session.close()

    # --- Data Display (Optional) ---
    if st.checkbox("Show submitted rankings"):
        conn = sqlite3.connect('rankings.db')
        try:
            df = pd.read_sql_query("SELECT * from rankings", conn)
            if not df.empty:
                st.dataframe(df[['submission_id', 'user_name', 'item', 'rank']])
            else:
                st.write("No rankings have been submitted yet.")
        except Exception as e:
            st.error(f"Error reading from database: {e}")
        finally:
            conn.close()

elif user_name == "":
    pass
else:
    st.error("Please enter a valid name before proceeding.")
