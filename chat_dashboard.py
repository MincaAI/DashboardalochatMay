import os
import streamlit as st
from pinecone import Pinecone
from dotenv import load_dotenv
import openai
import asyncio
import socket
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# Set page config for wider sidebar - MUST be first Streamlit command
st.set_page_config(
    page_title="Whatsapp bot from May",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load .env
load_dotenv()

# Add custom CSS for wider sidebar and reduced spacing
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        min-width: 600px;
        max-width: 800px;
    }
    .stMetric {
        margin-bottom: 0.5rem;
    }
    .element-container {
        margin-bottom: 0.5rem;
    }
    h1, h2, h3 {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }
    /* Remove space before first header in sidebar */
    [data-testid="stSidebar"] .element-container:first-child h1 {
        margin-top: 0;
        padding-top: 0;
    }
    </style>
    """, unsafe_allow_html=True)

def format_timestamp(timestamp_str):
    try:
        # Convert timestamp to datetime object
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # Format as: Day, Month Date, Year, Time
        return dt.strftime("%A, %B %d, %Y, %I:%M %p")
    except:
        return timestamp_str  # Return original if parsing fails

def calculate_metrics(query_result):
    # Initialize counters
    total_messages = len(query_result)
    user_rooms = defaultdict(set)  # user -> set of rooms
    user_messages = defaultdict(int)  # user -> total number of messages
    user_message_count = 0
    agent_message_count = 0
    single_message_users = 0  # Count users with only one message
    multiple_message_users = 0  # Count users with 2 or more messages
    multiple_message_total = 0  # Total messages from users with multiple messages
    
    # Original response tracking
    single_ya_users = 0  # Users with single "ya" message
    single_tidak_users = 0  # Users with single "tidak" message
    
    # New response tracking
    single_iya_mau_dong_users = 0  # Users with single "Iya, mau dong" message
    single_nanti_aja_deh_users = 0  # Users with single "Nanti aja deh" message
    
    other_single_messages = []  # List of other single messages
    
    # Process all messages
    for match in query_result:
        if match.metadata and match.metadata.get("timestamp"):  # Only process messages with a metadata timestamp
            user_name = match.metadata.get("user_name")
            room_id = match.metadata.get("room_id")
            sender_type = match.metadata.get("sender_type", "user")
            text = match.metadata.get("text", "").strip()
            
            if user_name and room_id:
                user_rooms[user_name].add(room_id)
                user_messages[user_name] += 1
                
                # Count user vs agent messages
                if sender_type == "user":
                    user_message_count += 1
                else:
                    agent_message_count += 1
    
    # Calculate single and multiple message users
    for user, count in user_messages.items():
        if count == 1:
            single_message_users += 1
            # Find the single message for this user
            for match in query_result:
                if (match.metadata and 
                    match.metadata.get("user_name") == user and 
                    match.metadata.get("sender_type") == "user"):
                    text = match.metadata.get("text", "").strip().lower()
                    
                    # Check original responses
                    if text == "ya":
                        single_ya_users += 1
                    elif text == "tidak":
                        single_tidak_users += 1
                    # Check new responses
                    elif text == "iya, mau dong":
                        single_iya_mau_dong_users += 1
                    elif text == "nanti aja deh":
                        single_nanti_aja_deh_users += 1
                    else:
                        other_single_messages.append({
                            "user": user,
                            "message": match.metadata.get("text", "").strip()
                        })
                    break
        elif count >= 2:
            multiple_message_users += 1
            multiple_message_total += count
    
    # Calculate metrics
    total_users = len(user_rooms)
    total_rooms = len(set(room for rooms in user_rooms.values() for room in rooms))
    avg_messages_per_user = sum(user_messages.values()) / total_users if total_users > 0 else 0
    single_message_percentage = (single_message_users / total_users * 100) if total_users > 0 else 0
    multiple_message_percentage = (multiple_message_users / total_users * 100) if total_users > 0 else 0
    avg_messages_multiple_users = multiple_message_total / multiple_message_users if multiple_message_users > 0 else 0
    
    # Original response percentages
    single_ya_percentage = (single_ya_users / single_message_users * 100) if single_message_users > 0 else 0
    single_tidak_percentage = (single_tidak_users / single_message_users * 100) if single_message_users > 0 else 0
    
    # New response percentages
    single_iya_mau_dong_percentage = (single_iya_mau_dong_users / single_message_users * 100) if single_message_users > 0 else 0
    single_nanti_aja_deh_percentage = (single_nanti_aja_deh_users / single_message_users * 100) if single_message_users > 0 else 0
    
    return {
        "total_users": total_users,
        "total_rooms": total_rooms,
        "avg_messages_per_user": round(avg_messages_per_user, 2),
        "total_messages": total_messages,
        "user_messages": user_message_count,
        "agent_messages": agent_message_count,
        "single_message_users": single_message_users,
        "single_message_percentage": round(single_message_percentage, 1),
        "multiple_message_users": multiple_message_users,
        "multiple_message_percentage": round(multiple_message_percentage, 1),
        "avg_messages_multiple_users": round(avg_messages_multiple_users, 2),
        # Original response metrics
        "single_ya_users": single_ya_users,
        "single_ya_percentage": round(single_ya_percentage, 1),
        "single_tidak_users": single_tidak_users,
        "single_tidak_percentage": round(single_tidak_percentage, 1),
        # New response metrics
        "single_iya_mau_dong_users": single_iya_mau_dong_users,
        "single_iya_mau_dong_percentage": round(single_iya_mau_dong_percentage, 1),
        "single_nanti_aja_deh_users": single_nanti_aja_deh_users,
        "single_nanti_aja_deh_percentage": round(single_nanti_aja_deh_percentage, 1),
        "other_single_messages": other_single_messages,
        "multiple_message_total": multiple_message_total
    }

try:
    # Environment setup
    openai.api_key = os.getenv("OPENAI_API_KEY")
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_index_name = os.getenv("PINECONE_INDEX")

    # Init Pinecone
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(pinecone_index_name)

    # Get all unique user names
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("Fetching user list...")
        # Query to get all unique user names
        query_result = index.query(
            vector=[0.0]*1536,
            namespace="messages",
            top_k=2000,
            include_metadata=True
        )
        
        progress_bar.progress(50)
        status_text.text("Processing user list...")
        
        # Ensure query_result is handled correctly
        if isinstance(query_result, list):
            messages = query_result
        else:
            messages = query_result.matches

        # --- 1. Add Date Range Picker to Sidebar (before metrics calculation) ---
        with st.sidebar:
            # Display date at the top
            current_date = datetime.now().strftime("%d/%m/%Y")
            st.header(f" {current_date}")

            # Date range picker
            st.header("🗓️ Filter by Date Range")
            default_start = datetime(2025, 5, 1).date()  # Start from May 1, 2025
            default_end = datetime.now().date()
            start_date, end_date = st.date_input(
                "Select date range",
                [default_start, default_end]
            )
            # Ensure start_date and end_date are always set
            if isinstance(start_date, list) or isinstance(start_date, tuple):
                start_date, end_date = start_date

        # --- 2. Helper function to filter messages by date range ---
        def is_in_range(ts, start, end):
            try:
                ts_dt = datetime.fromisoformat(ts)
                return start <= ts_dt.date() <= end
            except Exception:
                return False

        # --- 3. Filter messages by date range ---
        filtered_messages = [
            m for m in messages
            if m.metadata and m.metadata.get("timestamp") and is_in_range(m.metadata.get("timestamp"), start_date, end_date)
        ]

        # --- 4. Calculate metrics from filtered messages ---
        metrics = calculate_metrics(filtered_messages)
        
        # Display metrics in sidebar
        with st.sidebar:
            # Overview Metrics Section
            st.header("📊 Overview Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Users", metrics["total_users"])
                st.metric("Total Rooms", metrics["total_rooms"])
            with col2:
                st.metric("Total Messages", metrics["total_messages"])
                st.metric("Avg Messages per User", metrics["avg_messages_per_user"])
            
            # User Analysis Section
            st.header("👤 User Analysis")
            
            # Single Message Users Section
            st.subheader("Single Message Users")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Single Message Users", 
                    metrics["single_message_users"],
                    f"{metrics['single_message_percentage']}%"
                )

            # Create two columns for the original and new metrics
            st.subheader("Response Analysis")
            left_col, right_col = st.columns(2)

            # Left column - Original responses
            with left_col:
                st.markdown("**Original Responses**")
                st.metric(
                    "Users saying 'Ya'", 
                    metrics["single_ya_users"],
                    f"{metrics['single_ya_percentage']}%"
                )
                st.metric(
                    "Users saying 'Tidak'", 
                    metrics["single_tidak_users"],
                    f"{metrics['single_tidak_percentage']}%"
                )

            # Right column - New responses
            with right_col:
                st.markdown("**Alternative Responses**")
                st.metric(
                    "Users saying 'Iya, mau dong'", 
                    metrics["single_iya_mau_dong_users"],
                    f"{metrics['single_iya_mau_dong_percentage']}%"
                )
                st.metric(
                    "Users saying 'Nanti aja deh'", 
                    metrics["single_nanti_aja_deh_users"],
                    f"{metrics['single_nanti_aja_deh_percentage']}%"
                )
            
            # Show other single messages if any
            if metrics["other_single_messages"]:
                with st.expander("Other Single Messages"):
                    for msg in metrics["other_single_messages"]:
                        st.write(f"**{msg['user']}**: {msg['message']}")
            
            # Multiple Message Users Section
            st.subheader("Multiple Message Users")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Multiple Message Users", 
                    metrics["multiple_message_users"],
                    f"{metrics['multiple_message_percentage']}%"
                )
            with col2:
                st.metric(
                    "Total Messages", 
                    metrics["multiple_message_total"]
                )
            with col3:
                st.metric(
                    "Avg Messages per User", 
                    round(metrics["avg_messages_multiple_users"], 2)
                )
            
            # Message Metrics Section
            st.header("📝 Message Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("User Messages", metrics["user_messages"])
            with col2:
                st.metric("Agent Messages", metrics["agent_messages"])

        progress_bar.progress(100)
        status_text.text("Ready!")
        
    except Exception as e:
        st.error(f"Error fetching user list: {str(e)}")
    finally:
        progress_bar.empty()
        status_text.empty()

except Exception as e:
    st.error(f"Error initializing Pinecone: {str(e)}")