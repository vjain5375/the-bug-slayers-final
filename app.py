import streamlit as st
import os
import time
import random
import pandas as pd
from pathlib import Path
import logging
from typing import List, Dict, Optional

# --- AGENT IMPORTS ---
from agents.controller import AgentController
from vector_store import VectorStore
from agents.planner_agent import PlannerAgent

# --- LOGGING CONFIG ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="DEADPOOL'S ARSENAL STUDY HUB",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DIRECTORY SETUP ---
def ensure_documents_directory():
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    return docs_dir

def ensure_outputs_directory():
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    return outputs_dir

def get_document_files():
    docs_dir = ensure_documents_directory()
    return list(docs_dir.glob("*"))

# --- CLEANUP LOGIC ---
def cleanup_session():
    """Wipe everything for a fresh mission start."""
    # 1. Delete files in documents/
    docs_dir = Path("documents")
    if docs_dir.exists():
        for f in docs_dir.glob("*"):
            try: f.unlink()
            except: pass
    
    # 2. Delete files in outputs/
    outputs_dir = Path("outputs")
    if outputs_dir.exists():
        for f in outputs_dir.glob("*"):
            try: f.unlink()
            except: pass
            
    # 3. Reset Vector Store
    if 'vector_store' in st.session_state and st.session_state.vector_store:
        try:
            # Delete the correct collection name
            st.session_state.vector_store.client.delete_collection("campus_compass")
            st.session_state.vector_store = VectorStore() # Re-init
        except Exception as e:
            logger.warning(f"Error deleting collection: {e}")
            # Force re-init anyway
            try:
                st.session_state.vector_store = VectorStore()
            except: pass

# --- SESSION STATE INITIALIZATION ---
if 'initialized' not in st.session_state:
    # FRESH SESSION CLEANUP
    cleanup_session()
    
    st.session_state.initialized = True
    st.session_state.current_page = "Home"
    st.session_state.vector_store = VectorStore()
    # Clear any existing data in the collection
    try:
        if st.session_state.vector_store.collection:
            # Delete all existing data
            all_ids = st.session_state.vector_store.collection.get()['ids']
            if all_ids:
                st.session_state.vector_store.collection.delete(ids=all_ids)
                logger.info(f"Cleared {len(all_ids)} existing chunks from vector store")
    except Exception as e:
        logger.warning(f"Error clearing vector store on init: {e}")
    
    st.session_state.agent_controller = AgentController(st.session_state.vector_store)
    st.session_state.documents_processed = False
    st.session_state.flashcards = []
    st.session_state.quizzes = []
    st.session_state.quiz_answers = {}
    st.session_state.chat_history = []
    st.session_state.latest_document = None
    st.session_state.num_flashcards = 10
    st.session_state.num_questions = 10
    st.session_state.document_upload_order = []
    st.session_state.planner_study_mode = None
    st.session_state.planner_study_topic = None

# --- CUSTOM CSS (THE DEADPOOL EXPERIENCE) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@400;700&display=swap');

    :root {
        --deadpool-red: #A80000;
        --deadpool-black: #1A1A1A;
        --deadpool-white: #FFFFFF;
    }

    /* GLOBAL THEME OVERRIDE */
    .stApp {
        background: #0a0a0a;
        color: #ffffff;
        border: 20px solid var(--deadpool-red);
        background-image: radial-gradient(rgba(168,0,0,0.1) 2px, transparent 2px);
        background-size: 30px 30px;
    }
    
    /* Internal Frame */
    .stApp::before {
        content: "";
        position: fixed;
        top: 4px; left: 4px; right: 4px; bottom: 4px;
        border: 4px solid #fff;
        pointer-events: none;
        z-index: 9999;
    }

    /* BANGERS FONT FOR HEADERS */
    h1, h2, h3, .designer-header {
        font-family: 'Bangers', cursive !important;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #fff !important;
        text-shadow: 4px 4px 0px #000;
    }

    /* DESIGNER CARD STYLE (RED HALFTONE) */
    .designer-card-red {
        background: var(--deadpool-red);
        background-image: radial-gradient(#000 10%, transparent 10%);
        background-size: 15px 15px;
        padding: 2.5rem;
        border: 8px solid #000;
        box-shadow: 15px 15px 0px #000;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }

    /* Force white text in red cards */
    .designer-card-red h1, .designer-card-red h2, .designer-card-red h3, .designer-card-red h4,
    .designer-card-red p, .designer-card-red span, .designer-card-red div {
        color: #ffffff !important;
    }

    /* DESIGNER CARD STYLE (BLACK) */
    .designer-card {
        background: var(--deadpool-black);
        padding: 2.5rem;
        border: 8px solid var(--deadpool-red);
        box-shadow: 15px 15px 0px #000;
        margin-bottom: 2rem;
        position: relative;
    }

    /* COMIC BUTTONS */
    div.stButton > button {
        background: var(--deadpool-red) !important;
        color: white !important;
        font-family: 'Bangers' !important;
        font-size: 1.8rem !important;
        padding: 0.8rem 2rem !important;
        border: 5px solid #000 !important;
        box-shadow: 8px 8px 0px #000 !important;
        transform: skew(-10deg);
        transition: all 0.2s ease;
        width: 100% !important;
        margin-bottom: 10px;
        text-transform: uppercase;
    }

    div.stButton > button:hover {
        transform: skew(-10deg) translate(-4px, -4px);
        box-shadow: 12px 12px 0px #000 !important;
        background: #ff0000 !important;
    }

    div.stButton > button:active {
        transform: skew(-10deg) translate(2px, 2px);
        box-shadow: 2px 2px 0px #000 !important;
    }

    /* COMMAND CENTER CARD BUTTONS - Invisible overlay behind cards */
    div[data-testid="column"] button[kind="secondary"][key*="dash_"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        position: relative !important;
        z-index: 1 !important;
        cursor: pointer !important;
        opacity: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
    }
    
    /* Make cards appear above buttons and clickable */
    div[data-testid="column"]:has(button[key*="dash_"]) .designer-card-red {
        position: relative !important;
        z-index: 2 !important;
        cursor: pointer !important;
    }

    /* Make card hover effect */
    .designer-card-red:hover {
        transform: rotate(-1deg) translate(-4px, -4px) !important;
        box-shadow: 20px 20px 0px #000 !important;
    }
    
    /* Ensure titles are visible above button */
    .designer-card-red > div:first-child {
        position: relative !important;
        z-index: 20 !important;
        pointer-events: none !important;
    }
    
    .designer-card-red p {
        position: relative !important;
        z-index: 20 !important;
        pointer-events: none !important;
    }

    /* SIDEBAR STYLING */
    section[data-testid="stSidebar"] {
        background-color: #000000 !important;
        border-right: 8px solid var(--deadpool-red);
    }
    
    section[data-testid="stSidebar"]::after {
        content: "";
        position: absolute;
        top: 0; right: 4px; bottom: 0; left: 0;
        border-right: 3px solid #fff;
        pointer-events: none;
    }

    /* FANCY RADIO BUTTONS FOR QUIZ */
    div[data-testid="stRadio"] > label {
        display: none !important;
    }
    
    div[data-testid="stRadio"] div[role="radiogroup"] {
        background: #ffffff !important;
        padding: 2.5rem !important;
        border: 10px solid #000 !important;
        outline: 5px solid var(--deadpool-red) !important;
        box-shadow: 20px 20px 0px #000 !important;
        margin-top: -10px !important;
        margin-bottom: 50px !important;
        border-radius: 0px !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background: transparent !important;
        color: #000 !important;
        font-family: 'Oswald', sans-serif !important;
        font-size: 1.6rem !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
        padding: 10px 0 !important;
        margin-bottom: 15px !important;
        border-bottom: 3px solid rgba(0,0,0,0.1) !important;
        width: 100% !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] label:last-child {
        border-bottom: none !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        font-size: 1.6rem !important;
        color: #000 !important;
        line-height: 1.2 !important;
    }

    /* Style the actual radio circle */
    div[data-testid="stRadio"] div[role="radiogroup"] label div[data-sidemeasure="true"] {
        border-color: var(--deadpool-red) !important;
    }
    
    div[data-testid="stRadio"] div[role="radiogroup"] label div[data-sidemeasure="true"] > div {
        background-color: var(--deadpool-red) !important;
    }

    /* CHAT BUBBLES */
    .chat-bubble {
        padding: 1.5rem;
        border-radius: 0;
        margin-bottom: 1.5rem;
        font-family: 'Oswald', sans-serif;
        font-size: 1.2rem;
        border: 5px solid #000;
        position: relative;
        box-shadow: 10px 10px 0px rgba(0,0,0,0.5);
    }
    
    .user-bubble {
        background: #fff;
        color: #000;
        transform: rotate(-1deg);
        margin-left: 10%;
    }
    
    .assistant-bubble {
        background: var(--deadpool-red);
        color: #fff;
        transform: rotate(1deg);
        margin-right: 10%;
    }

    /* TACTICAL HEADER */
    .designer-header {
        background: var(--deadpool-red);
        display: inline-block;
        padding: 10px 30px;
        border: 5px solid #fff;
        box-shadow: 8px 8px 0px #000;
        transform: rotate(-1.5deg);
        margin-bottom: 2rem;
    }

    /* CUSTOM RADIO/SELECTOR STYLE */
    .stRadio [data-testid="stWidgetLabel"] p {
        font-family: 'Bangers' !important;
        font-size: 1.5rem !important;
        color: var(--deadpool-red) !important;
    }
    
    /* MODERN SKEWED EXPANDER */
    .streamlit-expanderHeader {
        background: #000 !important;
        border: 3px solid var(--deadpool-red) !important;
        color: #fff !important;
        font-family: 'Bangers' !important;
    }

    /* ARSENAL PORTAL STYLE (UPLOADER) */
    .sexy-drop-zone {
        background: #000;
        border: 8px solid #fff;
        padding: 3rem;
        text-align: center;
        position: relative;
        margin-bottom: 2rem;
        box-shadow: 20px 20px 0px var(--deadpool-red);
    }
    
    .moving-danger-stripes {
        height: 20px;
        background: repeating-linear-gradient(45deg, #000, #000 10px, var(--deadpool-red) 10px, var(--deadpool-red) 20px);
        width: 100%;
        position: absolute;
        bottom: 0; left: 0;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def process_documents():
    """Trigger the RAG pipeline."""
    docs = get_document_files()
    if not docs:
        st.warning("No documents to process, rookie!")
        return False
        
    with st.spinner("⚔️ DEADPOOL IS SLICING THROUGH YOUR TEXT..."):
        try:
            results = st.session_state.agent_controller.process_study_materials("documents")
            st.session_state.processing_results = results
            st.session_state.documents_processed = True
            st.session_state.latest_document = docs[-1].name
            
            # TRIGGER MAXIMUM EFFORT STRIKE EFFECT
            trigger_maximum_effort_strike()
            return True
        except Exception as e:
            st.error(f"⚠️ Combat Error: {e}")
            logger.exception("Processing failed")
            return False

def trigger_maximum_effort_strike():
    """Custom high-impact comic-style animation."""
    st.markdown("""
    <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 10000; overflow: hidden;">
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #fff; font-family: 'Bangers'; font-size: 8rem; text-shadow: 10px 10px 0px #A80000, 20px 20px 0px #000; animation: impact 1s ease-out forwards;">MAXIMUM EFFORT!</div>
        <div class="comic-burst" style="top: 20%; left: 20%; animation-delay: 0.1s;">BANG!</div>
        <div class="comic-burst" style="top: 70%; left: 80%; animation-delay: 0.3s;">POW!</div>
        <div class="comic-burst" style="top: 40%; left: 70%; animation-delay: 0.5s;">KABOOM!</div>
    </div>
    <style>
        @keyframes impact {
            0% { transform: translate(-50%, -50%) scale(0); opacity: 0; }
            50% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
            100% { transform: translate(-50%, -50%) scale(1); opacity: 0; }
        }
        .comic-burst {
            position: absolute;
            background: yellow;
            color: black;
            padding: 10px 20px;
            font-family: 'Bangers';
            font-size: 3rem;
            border: 5px solid black;
            transform: rotate(-15deg);
            opacity: 0;
            animation: burst 0.8s ease-out forwards;
        }
        @keyframes burst {
            0% { transform: scale(0) rotate(0deg); opacity: 0; }
            50% { transform: scale(1.5) rotate(-20deg); opacity: 1; }
            100% { transform: scale(1) rotate(-15deg); opacity: 0; }
        }
    </style>
    """, unsafe_allow_html=True)
    time.sleep(1.5) # Let animation play

# --- MAIN APP FLOW ---
def main():
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem; background: var(--deadpool-red); border: 5px solid #fff; box-shadow: 5px 5px 0px #000; margin-bottom: 2rem; transform: rotate(-2deg);">
            <h1 style="font-family: 'Bangers'; color: #fff; font-size: 2.5rem; margin: 0; text-shadow: 3px 3px 0px #000;">⚔️ ARSENAL HUB</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # FANCY NAVIGATION MENU
        st.markdown("<p style='font-family: \"Bangers\"; font-size: 1.4rem; color: var(--deadpool-red); margin-bottom: 2rem; text-shadow: 2px 2px 0px #000;'>🎯 DESTINATIONS</p>", unsafe_allow_html=True)
        
        nav_options = {
            "Home": "🏠",
            "Flashcards": "📇",
            "Quizzes": "📝",
            "Revision Planner": "📅",
            "Chat Assistant": "💬",
            "Analytics": "📊"
        }
        
        for page_name, icon in nav_options.items():
            is_active = st.session_state.current_page == page_name
            
            # Sidebar Active Marker (Premium Comic Arrow) - Improved Positioning
            col_marker, col_btn = st.columns([1.5, 8.5])
            with col_marker:
                if is_active:
                    st.markdown("""
                        <div style='height: 95px; display: flex; align-items: center; justify-content: flex-end; margin-right: 5px;'>
                            <div style="font-size: 3.5rem; color: white; filter: drop-shadow(4px 4px 0px #000); line-height: 1;">▶</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height: 95px;'></div>", unsafe_allow_html=True)
            
            with col_btn:
                # Create a stylized button-like container
                if st.button(f"{icon} {page_name.upper()}", key=f"side_nav_{page_name}", use_container_width=True, type="secondary" if not is_active else "primary"):
                    st.session_state.current_page = page_name
                    st.rerun()

        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
        
        uploaded_files = st.file_uploader(
            "📎 Upload Study Materials",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=True,
            key="sidebar_uploader",
            help="Upload PDF, DOCX, or TXT files"
        )
        
        # Sync with main page upload
        if uploaded_files:
            st.session_state.uploaded_files_shared = uploaded_files
            st.info(f"📁 {len(uploaded_files)} file(s) selected")
        elif st.session_state.get('uploaded_files_shared'):
            st.info(f"📁 {len(st.session_state.uploaded_files_shared)} file(s) from main page")
        
        # Use shared files
        files_to_process_sidebar = uploaded_files if uploaded_files else st.session_state.get('uploaded_files_shared')
        
        if files_to_process_sidebar:
            docs_dir = ensure_documents_directory()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 SAVE", use_container_width=True, key="sidebar_save", type="primary"):
                    saved = 0
                    saved_files = []
                    for uploaded_file in files_to_process_sidebar:
                        file_path = docs_dir / uploaded_file.name
                        if not file_path.exists():
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            saved += 1
                            saved_files.append(uploaded_file.name)
                            # Track upload order
                            if uploaded_file.name not in st.session_state.document_upload_order:
                                st.session_state.document_upload_order.append(uploaded_file.name)
                            else:
                                # Move to end if already exists (re-upload)
                                st.session_state.document_upload_order.remove(uploaded_file.name)
                                st.session_state.document_upload_order.append(uploaded_file.name)
                    
                    if saved > 0:
                        # Update latest document
                        if saved_files:
                            st.session_state.latest_document = saved_files[-1]
                        st.success(f"✅ Saved {saved} file(s)!")
                        st.session_state.documents_processed = False
                        st.session_state.uploaded_files_shared = None  # Clear after saving
                        st.rerun()
                    else:
                        st.info("Files already exist.")
            with col2:
                if st.button("🔄 PROCESS", use_container_width=True, type="primary", key="sidebar_process"):
                    # Save first if needed
                    saved_files = []
                    for uploaded_file in files_to_process_sidebar:
                        file_path = docs_dir / uploaded_file.name
                        if not file_path.exists():
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            saved_files.append(uploaded_file.name)
                            # Track upload order
                            if uploaded_file.name not in st.session_state.document_upload_order:
                                st.session_state.document_upload_order.append(uploaded_file.name)
                            else:
                                # Move to end if already exists (re-upload)
                                st.session_state.document_upload_order.remove(uploaded_file.name)
                                st.session_state.document_upload_order.append(uploaded_file.name)
                    
                    # Update latest document before processing
                    if saved_files:
                        st.session_state.latest_document = saved_files[-1]
                    
                    if process_documents():
                        st.session_state.uploaded_files_shared = None  # Clear after processing
                        # Show summary in sidebar
                        if 'processing_results' in st.session_state:
                            result = st.session_state.processing_results
                            st.success(f"✅ {result['total_chunks']} chunks, {result['total_topics']} topics!")
                        st.rerun()
        
        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
        
        doc_files = get_document_files()
        if doc_files:
            st.info(f"📁 {len(doc_files)} document(s) in arsenal")
        
        if st.session_state.vector_store:
            count = st.session_state.vector_store.get_collection_count()
            st.metric("INDEXED CHUNKS", count)
        
        st.divider()
        
    # Main Content Area
    if st.session_state.current_page == "Home":
        show_home_page()
    elif st.session_state.current_page == "Flashcards":
        show_flashcards_page()
    elif st.session_state.current_page == "Quizzes":
        show_quizzes_page()
    elif st.session_state.current_page == "Revision Planner":
        show_planner_page()
    elif st.session_state.current_page == "Chat Assistant":
        show_chat_page()
    elif st.session_state.current_page == "Analytics":
        show_analytics_page()

    # Footer - Removed extra space
    st.markdown("""
    <div style="text-align: center; margin-top: 0rem; padding: 1rem; border-top: 4px solid var(--deadpool-red); background: #000;">
        <p style="color: #fff; font-family: 'Oswald', sans-serif; font-size: 0.85rem; margin: 0;">© 2025 Deadpool's Study Hub. No regenerating degenerates allowed.</p>
    </div>
    """, unsafe_allow_html=True)
        
def show_home_page():
    """Deadpool-themed Home page with Designer Visuals"""
    
    # Hero Section with Deadpool Action Grid Style - RED/BLACK/WHITE
    st.markdown("""
    <div style="background: url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg') center/cover; padding: 6rem 2rem; border: 10px solid #000; box-shadow: 20px 20px 0px var(--deadpool-red), 30px 30px 0px #000; text-align: center; margin-bottom: 4rem; position: relative; transform: rotate(-1deg) skew(-1deg);">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); border: 4px solid #fff; margin: 10px;"></div>
        <div style="position: relative; z-index: 2;">
            <h1 style="font-family: 'Bangers'; font-size: 5rem; color: #fff; text-shadow: 8px 8px 0px var(--deadpool-red), 12px 12px 0px #000; margin: 0; letter-spacing: 5px; transform: rotate(1deg);">WEAPONIZED KNOWLEDGE!</h1>
            <p style="font-family: 'Bangers', cursive; color: #fff; font-size: 2.2rem; background: var(--deadpool-red); display: inline-block; padding: 1rem 3rem; transform: skew(-15deg); margin-top: 2.5rem; border: 5px solid #fff; box-shadow: 10px 10px 0px #000; text-shadow: 3px 3px 0px #000;">MAXIMUM EFFORT. MINIMUM STUDYING.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
        
    # CASE 1: NEW USER EXPERIENCE (High-Impact Onboarding)
    if not st.session_state.documents_processed:
        st.markdown("<h2 class='designer-header' style='text-align: center; display: block; font-size: 2.5rem;'>⚔️ MISSION OBJECTIVES</h2>", unsafe_allow_html=True)
        
        # Journey Cards with Designer Style
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            <div class="designer-card-red" style="transform: rotate(-2deg) skew(-2deg);">
                <h3 class="designer-header" style="font-size: 2.5rem; background: #000; color: #fff; border: 4px solid #fff;">1️⃣ LOAD UP</h3>
                <p style="color: #fff; font-size: 1.4rem; font-weight: 900; font-family: 'Oswald', sans-serif; text-shadow: 2px 2px 0px #000; line-height: 1.2;">Drop your PDFs, DOCX, or Text notes into the side-feed. Don't worry, I won't read your diary... maybe.</p>
            </div>
            <div class="designer-card-red" style="transform: rotate(1deg) skew(1deg); margin-top: 2rem;">
                <h3 class="designer-header" style="font-size: 2.5rem; background: #000; color: #fff; border: 4px solid #fff;">3️⃣ EXTRACT</h3>
                <p style="color: #fff; font-size: 1.4rem; font-weight: 900; font-family: 'Oswald', sans-serif; text-shadow: 2px 2px 0px #000; line-height: 1.2;">Hit <b>'PROCESS'</b>. My agents will slice and dice your text into pure semantic gold faster than I can slice a chimichanga.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="designer-card-red" style="transform: rotate(2deg) skew(2deg);">
                <h3 class="designer-header" style="font-size: 2.5rem; background: #000; color: #fff; border: 4px solid #fff;">2️⃣ LOCK & LOAD</h3>
                <p style="color: #fff; font-size: 1.4rem; font-weight: 900; font-family: 'Oswald', sans-serif; text-shadow: 2px 2px 0px #000; line-height: 1.2;">Hit <b>'SAVE'</b> to commit those files to my infinite memory banks. No take-backs!</p>
            </div>
            <div class="designer-card-red" style="transform: rotate(-1.5deg) skew(-1.5deg); margin-top: 2rem;">
                <h3 class="designer-header" style="font-size: 2.5rem; background: #000; color: #fff; border: 4px solid #fff;">4️⃣ DOMINATE</h3>
                <p style="color: #fff; font-size: 1.4rem; font-weight: 900; font-family: 'Oswald', sans-serif; text-shadow: 2px 2px 0px #000; line-height: 1.2;">Maximum Effort! 💥 Flashcards, Quizzes, and Chat are now operational. Go be a hero... or whatever.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # Add the thumbs up Deadpool image
        st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", width=350)
        
        # Arsenal Portal (Upload Zone)
        st.markdown("""
            <div class="sexy-drop-zone">
                <div class="tactical-border"></div>
                <div class="command-center">
                    <div class="pop-art-label">CLASSIFIED ARCHIVES</div>
                    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 2rem; margin-top: 1rem;">
                        <div style="background: #A80000; padding: 10px 30px; border: 6px solid #fff; transform: rotate(-1.5deg); box-shadow: 12px 12px 0px #000; display: inline-block; max-width: 90%;">
                            <span style="font-family: 'Bangers', cursive !important; font-size: 3.0rem; color: #ffffff !important; text-shadow: 5px 5px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic; font-weight: 900; letter-spacing: 1.5px;">⚔️ ARSENAL PORTAL</span>
                        </div>
                    </div>
                    <p style="font-family: 'Bangers'; font-size: 2.2rem; color: #fff; letter-spacing: 3px; margin: 1.5rem 0; text-shadow: 3px 3px 0px #A80000;">DROP YOUR BRAIN JUICE HERE!</p>
                    <div class="moving-danger-stripes"></div>
                </div>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_files_main = st.file_uploader(
            "📎 Choose files to upload",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=True,
            key="main_uploader_onboarding",
            label_visibility="collapsed"
        )
        
        # Save and Process logic for onboarding
        if uploaded_files_main:
            st.session_state.uploaded_files_shared = uploaded_files_main
            
            f_count = len(uploaded_files_main)
            st.markdown(f"""
            <div style="background: #A80000; color: white; padding: 10px; border: 3px solid #000; text-align: center; font-family: 'Bangers'; transform: rotate(2deg); box-shadow: 5px 5px 0px #000; margin-bottom: 1rem;">
                ✅ {f_count} TARGETS LOCKED! READY FOR SLICING!
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 SAVE TARGETS", use_container_width=True, type="primary", key="save_main_onboard"):
                    docs_dir = ensure_documents_directory()
                    saved = 0
                    for f in uploaded_files_main:
                        file_path = docs_dir / f.name
                        if not file_path.exists():
                            with open(file_path, "wb") as pf:
                                pf.write(f.getbuffer())
                            saved += 1
                    if saved > 0:
                        st.success(f"✅ Saved {saved} files!")
                    st.session_state.documents_processed = False
                    st.rerun()
            with col2:
                if st.button("🔄 PROCESS MISSION", use_container_width=True, type="primary", key="process_main_onboard"):
                    # Save first
                    docs_dir = ensure_documents_directory()
                    for f in uploaded_files_main:
                        file_path = docs_dir / f.name
                        if not file_path.exists():
                            with open(file_path, "wb") as pf:
                                pf.write(f.getbuffer())
                    if process_documents():
                        st.session_state.uploaded_files_shared = None
                        st.rerun()
        return

    # CASE 2: RETURNING USER (Pro Dashboard)
    st.markdown("<h2 class='designer-header' style='font-size: 3rem; background: var(--deadpool-red); border-color: #fff;'>⚡ COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    # 1. High-Impact Quick Access Grid - Cards as Buttons
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="designer-card-red" style="transform: rotate(-1deg); padding: 2rem !important; position: relative; cursor: pointer;" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'flashcards'}, '*')">
            <div style="background: #fff; color: #000; padding: 5px 20px; border: 4px solid #000; box-shadow: 5px 5px 0px #000; display: inline-block; margin-bottom: 1rem; font-family: 'Bangers'; font-size: 1.8rem;">
                📇 FLASHCARDS
            </div>
            <p style="color: #fff; font-family: 'Oswald'; font-size: 1.1rem; margin: 1rem 0; text-transform: uppercase;">WEAPONIZED FLASHCARDS FOR RAPID INTEL RETENTION.</p>
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.2rem; margin-top: 1.5rem; text-align: center;">CLICK TO ACCESS →</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📇 FLASHCARDS", key="dash_flash", use_container_width=True, type="primary"):
            st.session_state.current_page = "Flashcards"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="designer-card-red" style="transform: rotate(1deg); padding: 2rem !important; position: relative; cursor: pointer;" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'quizzes'}, '*')">
            <div style="background: #fff; color: #000; padding: 5px 20px; border: 4px solid #000; box-shadow: 5px 5px 0px #000; display: inline-block; margin-bottom: 1rem; font-family: 'Bangers'; font-size: 1.8rem;">
                📝 QUIZ
            </div>
            <p style="color: #fff; font-family: 'Oswald'; font-size: 1.1rem; margin: 1rem 0; text-transform: uppercase;">TEST YOUR COMBAT READINESS WITH CUSTOMIZED CHALLENGES.</p>
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.2rem; margin-top: 1.5rem; text-align: center;">CLICK TO INITIATE →</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📝 QUIZ", key="dash_quiz", use_container_width=True, type="primary"):
            st.session_state.current_page = "Quizzes"
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("""
        <div class="designer-card-red" style="transform: rotate(0.5deg); padding: 2rem !important; position: relative; cursor: pointer;">
            <div style="background: #fff; color: #000; padding: 5px 20px; border: 4px solid #000; box-shadow: 5px 5px 0px #000; display: inline-block; margin-bottom: 1rem; font-family: 'Bangers'; font-size: 1.8rem;">
                💬 CHAT ASSISTANT
            </div>
            <p style="color: #fff; font-family: 'Oswald'; font-size: 1.1rem; margin: 1rem 0; text-transform: uppercase;">INTERROGATE THE AI FOR DEEP SEMANTIC INSIGHTS.</p>
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.2rem; margin-top: 1.5rem; text-align: center;">CLICK TO INTERROGATE →</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("💬 CHAT ASSISTANT", key="dash_chat", use_container_width=True, type="primary"):
            st.session_state.current_page = "Chat Assistant"
            st.rerun()

    with col4:
        st.markdown("""
        <div class="designer-card-red" style="transform: rotate(-0.5deg); padding: 2rem !important; position: relative; cursor: pointer;">
            <div style="background: #fff; color: #000; padding: 5px 20px; border: 4px solid #000; box-shadow: 5px 5px 0px #000; display: inline-block; margin-bottom: 1rem; font-family: 'Bangers'; font-size: 1.8rem;">
                📅 REVISION PLANNER
            </div>
            <p style="color: #fff; font-family: 'Oswald'; font-size: 1.1rem; margin: 1rem 0; text-transform: uppercase;">STRATEGIZE YOUR LEARNING JOURNEY WITH A TIMELINE.</p>
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.2rem; margin-top: 1.5rem; text-align: center;">CLICK TO VIEW →</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📅 REVISION PLANNER", key="dash_plan", use_container_width=True, type="primary"):
            st.session_state.current_page = "Revision Planner"
            st.rerun()

    col5, _ = st.columns([1, 1])
    with col5:
        st.markdown("""
        <div class="designer-card-red" style="transform: rotate(1.5deg); padding: 2rem !important; position: relative; cursor: pointer;">
            <div style="background: #fff; color: #000; padding: 5px 20px; border: 4px solid #000; box-shadow: 5px 5px 0px #000; display: inline-block; margin-bottom: 1rem; font-family: 'Bangers'; font-size: 2rem;">
                📊 ANALYTICS
            </div>
            <p style="color: #fff; font-family: 'Oswald'; font-size: 1.1rem; margin: 1rem 0; text-transform: uppercase;">TRACK YOUR STUDY EFFICIENCY AND VICTORY RATES.</p>
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.2rem; margin-top: 1.5rem; text-align: center;">CLICK TO ANALYZE →</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📊 ANALYTICS", key="dash_analytics", use_container_width=True, type="primary"):
            st.session_state.current_page = "Analytics"
            st.rerun()
    
    # Add Mission Portal to Command Center for completeness
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🛠️ ARSENAL PORTAL (UPLOAD & MANAGE INTEL)", expanded=False):
        st.markdown("""
        <div style="background: #000; padding: 2rem; border: 5px dashed var(--deadpool-red); transform: rotate(-0.5deg);">
            <p style="color: #fff; font-family: 'Bangers'; font-size: 1.8rem; text-align: center; margin-bottom: 1.5rem;">NEED MORE AMMO? DROP IT HERE!</p>
        </div>
        """, unsafe_allow_html=True)
        uploaded_files_dash = st.file_uploader(
            "📎 Add more intel to your arsenal",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=True,
            key="dash_uploader",
            label_visibility="collapsed"
        )
        if uploaded_files_dash:
            st.session_state.uploaded_files_shared = uploaded_files_dash
            f_count = len(uploaded_files_dash)
            st.markdown(f"""
            <div style="background: var(--deadpool-red); color: white; padding: 15px; border: 4px solid #fff; text-align: center; font-family: 'Bangers'; transform: rotate(1deg); box-shadow: 8px 8px 0px #000; margin: 1rem 0;">
                ✅ {f_count} NEW TARGETS DETECTED! PREPARE TO SLICE!
        </div>
        """, unsafe_allow_html=True)
        
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 LOCK & LOAD", use_container_width=True, type="primary", key="save_dash"):
                    docs_dir = ensure_documents_directory()
                    saved = 0
                    for f in uploaded_files_dash:
                        file_path = docs_dir / f.name
                        if not file_path.exists():
                            with open(file_path, "wb") as pf:
                                pf.write(f.getbuffer())
                            saved += 1
                    if saved > 0:
                        st.success(f"✅ Saved {saved} files!")
                        st.session_state.documents_processed = False
                        st.rerun()
            with c2:
                if st.button("🔄 MAXIMUM EFFORT (PROCESS)", use_container_width=True, type="primary", key="process_dash"):
                    docs_dir = ensure_documents_directory()
                    for f in uploaded_files_dash:
                        file_path = docs_dir / f.name
                        if not file_path.exists():
                            with open(file_path, "wb") as pf:
                                pf.write(f.getbuffer())
                    if process_documents():
                        st.session_state.uploaded_files_shared = None
                        st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Performance Stats
    if st.session_state.agent_controller:
        stats = st.session_state.agent_controller.get_statistics()
        st.markdown("<h3 class='designer-header'>📊 MISSION INTEL</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: 
            st.markdown(f'<div class="designer-card-red" style="text-align: center; padding: 1.5rem !important; border-width: 6px !important; margin-bottom: 1rem !important;"><h4 class="designer-header" style="font-size: 1.2rem !important; padding: 5px 10px !important;">TOPICS</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0; text-shadow: 2px 2px 0px #000;">{stats["total_topics"]}</p></div>', unsafe_allow_html=True)
        with c2: 
            st.markdown(f'<div class="designer-card-red" style="text-align: center; padding: 1.5rem !important; border-width: 6px !important; margin-bottom: 1rem !important;"><h4 class="designer-header" style="font-size: 1.2rem !important; padding: 5px 10px !important;">CARDS</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0; text-shadow: 2px 2px 0px #000;">{stats["total_flashcards"]}</p></div>', unsafe_allow_html=True)
        with c3: 
            st.markdown(f'<div class="designer-card-red" style="text-align: center; padding: 1.5rem !important; border-width: 6px !important; margin-bottom: 1rem !important;"><h4 class="designer-header" style="font-size: 1.2rem !important; padding: 5px 10px !important;">QUIZZES</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0; text-shadow: 2px 2px 0px #000;">{stats["total_quizzes"]}</p></div>', unsafe_allow_html=True)
        with c4: 
            st.markdown(f'<div class="designer-card-red" style="text-align: center; padding: 1.5rem !important; border-width: 6px !important; margin-bottom: 1rem !important;"><h4 class="designer-header" style="font-size: 1.2rem !important; padding: 5px 10px !important;">WIN RATE</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0; text-shadow: 2px 2px 0px #000;">{stats["revision_stats"]["completion_rate"]:.1f}%</p></div>', unsafe_allow_html=True)

    st.divider()

    # 3. Content Intelligence
    if 'processing_results' in st.session_state:
        p_result = st.session_state.processing_results
        col_topics, col_samples = st.columns([2, 1])
        
        with col_topics:
            if p_result.get('topics'):
                st.markdown("<h3 class='designer-header' style='font-size: 2.5rem;'>📚 WEAPONIZED TOPICS</h3>", unsafe_allow_html=True)
                for idx, topic_data in enumerate(p_result['topics'][:5], 1):
                    with st.expander(f"🔴 {topic_data.get('topic', 'Topic').upper()}", expanded=(idx == 1)):
                        st.markdown(f"""
                        <div style="background: #111; padding: 1.5rem; border-left: 8px solid var(--deadpool-red); margin-bottom: 10px; box-shadow: 5px 5px 0px #000;">
                            {''.join([f"<p style='color: #eee; font-family: Oswald; margin-bottom: 8px;'>⚔️ {p}</p>" for p in topic_data.get('key_points', [])[:3]])}
                        </div>
                        """, unsafe_allow_html=True)
        
        with col_samples:
            st.markdown("<h3 class='designer-header' style='font-size: 2.5rem;'>📄 INTEL SNAPS</h3>", unsafe_allow_html=True)
            if p_result.get('flashcard_samples'):
                with st.expander("📇 SAMPLE CARDS", expanded=True):
                    for fs in p_result['flashcard_samples'][:2]:
                        st.markdown(f"""
                        <div style="background: #fff; padding: 1.5rem; border: 4px solid #000; margin-bottom: 15px; transform: rotate({random.uniform(-1.5, 1.5)}deg); box-shadow: 8px 8px 0px var(--deadpool-red);">
                            <p style="color: #000; font-size: 1.1rem; font-family: Oswald; font-weight: bold; margin-bottom: 8px;"><b>Q:</b> {fs['question']}</p>
                            <hr style="margin: 8px 0; border-color: #000; border-width: 2px;">
                            <p style="color: #333; font-size: 1rem; font-family: Oswald;"><b>A:</b> {fs['answer']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            
            if p_result.get('quiz_samples'):
                with st.expander("📝 SAMPLE CHALLENGES", expanded=False):
                    for qs in p_result['quiz_samples'][:2]:
                        st.markdown(f"""
                        <div style="background: var(--deadpool-red); padding: 1.5rem; border: 4px solid #fff; margin-bottom: 15px; transform: rotate({random.uniform(-1.5, 1.5)}deg); box-shadow: 8px 8px 0px #000;">
                            <p style="color: #fff; font-size: 1.1rem; font-family: Oswald; font-weight: bold; text-shadow: 1px 1px 0px #000;">{qs['question']}</p>
                        </div>
                        """, unsafe_allow_html=True)

        # 4. Detailed Extracted Intel (Chunks)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h3 class='designer-header'>🧬 DETAILED EXTRACTED INTEL</h3>", unsafe_allow_html=True)
        if p_result.get('chunks'):
            with st.expander(f"VIEW {len(p_result['chunks'])} KNOWLEDGE CHUNKS IN DETAIL"):
                for i, chunk in enumerate(p_result['chunks']):
                    st.markdown(f"""
                    <div class="designer-card" style="padding: 1.5rem !important; border-left: 10px solid var(--deadpool-red); margin-bottom: 1.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="background: var(--deadpool-red); color: white; padding: 2px 10px; font-family: 'Bangers'; font-size: 0.9rem;">CHUNK #{i+1}</span>
                            <span style="color: #aaa; font-size: 0.8rem; font-family: 'Oswald';">TOPIC: {chunk.get('metadata', {}).get('topic', 'General').upper()}</span>
                        </div>
                        <p style="color: #fff; font-family: 'Oswald'; font-size: 1rem; line-height: 1.5; white-space: pre-wrap;">{chunk.get('text', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No detailed chunks found. Processing might have failed.")

    # 5. Pro Tips with Deadpool Flavor
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="designer-card-red" style="background: var(--deadpool-black) !important; border: 8px solid var(--deadpool-red) !important; transform: rotate(0.5deg) skew(0.5deg); box-shadow: 25px 25px 0px #000 !important;">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <div style="background: var(--deadpool-red); width: 60px; height: 60px; border-radius: 50%; border: 4px solid #fff; display: flex; align-items: center; justify-content: center; margin-right: 20px; box-shadow: 5px 5px 0px #000;">
                    <span style="font-size: 2.5rem;">💀</span>
        </div>
                <h3 class="designer-header" style="margin: 0; font-size: 2.5rem; background: var(--deadpool-red); border-color: #fff; box-shadow: 8px 8px 0px #000;">PRO TIPS FROM THE MERC</h3>
        </div>
            <ul style="color: #fff; font-family: 'Oswald', sans-serif; font-size: 1.3rem; line-height: 1.6; list-style-type: '⚔️ ';">
                <li style="margin-bottom: 15px;"><b>RELOAD:</b> Put new files in the side-slot and hit 'Process' to reload your arsenal. More files = more boom!</li>
                <li style="margin-bottom: 15px;"><b>EXTRACT:</b> Anki and CSV buttons are in the Cards/Quiz zones. Use 'em to take your intel on the go.</li>
                <li style="margin-bottom: 15px;"><b>EFFORT:</b> If the AI is slow, it's probably thinking about tacos. Or world peace. Probably tacos. Give it a sec.</li>
            </ul>
            <p style="text-align: right; font-style: italic; color: var(--deadpool-red); font-family: 'Bangers', cursive; font-size: 2.2rem; margin-top: 30px; text-shadow: 2px 2px 0px #000;">- Deadpool Out. (Mic Drop) 🎤💥</p>
        </div>
        """, unsafe_allow_html=True)

def show_flashcards_page():
    """Flashcards page with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">📇 WEAPONIZED FLASHCARDS</h1>', unsafe_allow_html=True)
    
    if not st.session_state.documents_processed:
        st.markdown("""
        <div class="designer-card">
            <h2 class="designer-header">⚠️ NO INTEL FOUND</h2>
            <p style="font-size: 1.2rem; color: #fff;">Upload some documents and hit 'PROCESS' first, rookie! I can't pull knowledge out of thin air... yet.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    with st.container():
        st.markdown('<div class="designer-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="designer-header">ARSENAL CONFIGURATION</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            num_flashcards = st.slider("CARD QUANTITY", 5, 30, value=st.session_state.num_flashcards, key="flashcard_slider")
        with col2:
            difficulty_mix_label = st.selectbox(
                "DIFFICULTY MIX",
                ["Easy + Medium", "Medium + Hard", "Easy + Medium + Hard"],
                index=2
            )
            mix_map = {"Easy + Medium": "easy_medium", "Medium + Hard": "medium_hard", "Easy + Medium + Hard": "easy_medium_hard"}
            difficulty_mix = mix_map.get(difficulty_mix_label, "easy_medium_hard")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 GENERATE ARSENAL", use_container_width=True, type="primary"):
                processing_msg = st.info("Deadpool is thinking (mostly about tacos and world peace... nah, just tacos)...")
                flashcards = st.session_state.agent_controller.generate_flashcards(num_flashcards, difficulty_mix=difficulty_mix)
                processing_msg.empty()
                st.session_state.flashcards = flashcards
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Load existing flashcards
    if not st.session_state.flashcards:
        try:
            flashcards = st.session_state.agent_controller.flashcard_agent.load_flashcards()
            st.session_state.flashcards = flashcards
        except Exception: pass
    
    # Display flashcards
    if st.session_state.flashcards:
        st.markdown(f'<h3 class="designer-header" style="font-size: 2.5rem;">📚 {len(st.session_state.flashcards)} CARDS IN YOUR ARSENAL</h3>', unsafe_allow_html=True)
        
        csv_data = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button(
            label="📥 EXPORT MISSION INTEL (CSV)",
            data=csv_data,
            file_name="flashcards_anki.csv",
            mime="text/csv",
            use_container_width=True,
            key="export_flash_csv"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        for i, card in enumerate(st.session_state.flashcards):
            st.markdown(f"""
            <div class="designer-card-red" style="transform: rotate({(i%2)*0.8 - 0.4}deg); border-width: 10px !important; padding: 2.5rem !important; margin-bottom: 0px !important; box-shadow: 15px 15px 0px #000 !important;">
                <div style="position: relative; z-index: 10;">
                    <h4 class="designer-header" style="font-size: 1.8rem !important; padding: 5px 20px !important; background: #000; border: 4px solid #fff;">CARD #{i+1} — {card.get('difficulty', 'medium').upper()}</h4>
                    <p style="font-size: 2.2rem; font-weight: 900; margin: 25px 0; color: #fff; line-height: 1.2; font-family: 'Bangers', cursive !important; text-shadow: 4px 4px 0px #000; letter-spacing: 1.5px;">Q: {card['question']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("👀 REVEAL CLASSIFIED INTEL (ANSWER)", expanded=False):
                st.markdown(f"""
                <div style="background: #fff; padding: 2.5rem; border: 10px solid #000; outline: 5px solid var(--deadpool-red); margin-top: -10px; box-shadow: 20px 20px 0px #000 !important; transform: rotate({(i%2)*-0.5 + 0.25}deg);">
                    <p style="font-size: 1.6rem; color: #000; font-family: 'Oswald', sans-serif; line-height: 1.5; font-weight: 900; text-transform: uppercase;">{card['answer']}</p>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('<div style="height: 50px;"></div>', unsafe_allow_html=True)
    else:
        st.info("Click 'GENERATE' to create flashcards from your study materials!")

def show_quizzes_page():
    """Quizzes page with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">📝 MAXIMUM EFFORT QUIZ</h1>', unsafe_allow_html=True)
    
    if not st.session_state.documents_processed:
        st.markdown("""
        <div class="designer-card">
            <h2 class="designer-header">⚠️ NO INTEL FOUND</h2>
            <p style="font-size: 1.2rem; color: #fff;">Upload some documents and hit 'PROCESS' first, rookie! No documents = No questions = No glory.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    with st.container():
        st.markdown('<div class="designer-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="designer-header">MISSION BRIEFING CONFIG</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            difficulty = st.selectbox("INTEL DIFFICULTY", ["easy", "medium", "hard"], index=1)
        with col2:
            num_questions = st.slider("TARGET QUESTIONS", 3, 30, value=st.session_state.num_questions, key="quiz_slider")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🎯 INITIATE QUIZ", use_container_width=True, type="primary"):
                processing_msg = st.info("Drafting questions... mostly about you failing... and maybe some tacos...")
                questions = st.session_state.agent_controller.generate_quiz(difficulty, num_questions, True)
                processing_msg.empty()
                if questions:
                    st.session_state.quizzes = questions
                    st.session_state.quiz_answers = {}
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display quiz
    if st.session_state.quizzes:
        st.markdown(f'<h3 class="designer-header" style="font-size: 2.5rem;">📋 {len(st.session_state.quizzes)} CHALLENGES STANDING BETWEEN YOU AND VICTORY</h3>', unsafe_allow_html=True)
        
        csv_data = st.session_state.agent_controller.quiz_agent.export_to_csv(st.session_state.quizzes)
        st.download_button(label="📥 DOWNLOAD MISSION DEBRIEF (CSV)", data=csv_data, file_name="quiz_questions.csv", mime="text/csv", use_container_width=True, key="download_quiz_csv")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"""
            <div class="designer-card-red" style="transform: rotate({(i%2)*0.8 - 0.4}deg); border-width: 10px !important; padding: 2.5rem !important; margin-bottom: 0px !important; box-shadow: 15px 15px 0px #000 !important;">
                <div style="position: relative; z-index: 10;">
                    <h4 class="designer-header" style="font-size: 1.8rem !important; padding: 5px 20px !important; background: #000; border: 4px solid #fff;">QUESTION #{i+1}</h4>
                    <p style="font-size: 2.2rem; font-weight: 900; margin: 25px 0; color: #fff; line-height: 1.2; font-family: 'Bangers', cursive !important; text-shadow: 4px 4px 0px #000; letter-spacing: 1.5px;">Q: {q['question']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Options using styled st.radio
            selected = st.radio(
                f"Options for Q{i+1}:",
                q['options'],
                key=f"quiz_q{i}",
                label_visibility="collapsed"
            )
            st.session_state.quiz_answers[i] = q['options'].index(selected) if selected in q['options'] else -1
            st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)

        # Persistence for quiz results
        if 'quiz_submitted' not in st.session_state:
            st.session_state.quiz_submitted = False
        if 'quiz_result' not in st.session_state:
            st.session_state.quiz_result = None

        if not st.session_state.quiz_submitted:
            if st.button("✅ SUBMIT MISSION INTEL", type="primary", use_container_width=True):
                with st.spinner("Analyzing your answers... trying not to laugh..."):
                    try:
                        q_result = st.session_state.agent_controller.evaluate_quiz(st.session_state.quizzes, st.session_state.quiz_answers)
                        st.session_state.quiz_result = q_result
                        st.session_state.quiz_submitted = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Tactical Error during evaluation: {e}")
                        logger.exception("Quiz evaluation failed")
        
        if st.session_state.quiz_submitted and st.session_state.quiz_result:
            q_result = st.session_state.quiz_result
            
            # Result Card
            accuracy = q_result.get('accuracy', 0)
            score_color = "#28a745" if accuracy >= 0.7 else "#dc3545"
            st.markdown(f"""
            <div class="designer-card" style="border-color: {score_color} !important; border-width: 15px !important; text-align: center;">
                <h1 style="font-size: 5rem; color: {score_color}; margin: 0;">{q_result['score']}/{q_result['total']}</h1>
                <h2 class="designer-header" style="background: {score_color};">MISSION SCORE: {accuracy*100:.1f}%</h2>
                <p style="font-family: 'Bangers'; font-size: 2rem; color: #fff; margin-top: 1rem;">{q_result.get('feedback', 'MISSION COMPLETE!')}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 RETAKE MISSION (RESET)", use_container_width=True):
                st.session_state.quiz_submitted = False
                st.session_state.quiz_result = None
                st.session_state.quiz_answers = {}
                st.rerun()

            # Detailed Review
            st.markdown("<h3 class='designer-header' style='font-size: 2.5rem;'>📋 AFTER-ACTION REPORT</h3>", unsafe_allow_html=True)
            for i, rev in enumerate(q_result.get('details', [])):
                is_correct = rev['is_correct']
                border_color = "#28a745" if is_correct else "#dc3545"
                icon = "✅" if is_correct else "❌"
                
                st.markdown(f"""
                <div style="background: #1a1a1a; padding: 2rem; border-left: 15px solid {border_color}; margin-bottom: 2rem; box-shadow: 10px 10px 0px #000;">
                    <h4 style="color: #fff; font-family: 'Bangers'; font-size: 1.5rem; margin-bottom: 1rem;">{icon} CHALLENGE #{i+1}</h4>
                    <p style="color: #eee; font-family: 'Oswald'; font-size: 1.2rem;"><strong>QUESTION:</strong> {rev['question']}</p>
                    <p style="color: {score_color if is_correct else '#dc3545'}; font-family: 'Oswald';"><strong>YOUR INTEL:</strong> {rev['user_answer']}</p>
                    <p style="color: #28a745; font-family: 'Oswald';"><strong>CORRECT INTEL:</strong> {rev['correct_answer']}</p>
                    <div style="background: rgba(255,255,255,0.05); padding: 1rem; margin-top: 1rem; border: 1px dashed #444;">
                        <p style="color: #aaa; font-style: italic; margin: 0; font-family: 'Oswald';"><strong>DEADPOOL'S TAKE:</strong> {rev['explanation']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

def show_planner_page():
    """Revision Planner page with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">📅 STRATEGIC BATTLE PLAN</h1>', unsafe_allow_html=True)
    
    if not st.session_state.documents_processed:
        st.markdown("""
        <div class="designer-card">
            <h2 class="designer-header">⚠️ NO INTEL FOUND</h2>
            <p style="font-size: 1.2rem; color: #fff;">Upload some documents to plan your world domination... I mean, study schedule.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown('<div class="designer-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="designer-header">MISSION TIMELINE CONFIG</h3>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        exam_date = st.date_input("MISSION DEADLINE (EXAM DATE)", value=None)
    with col2:
        study_days = st.slider("TRAINING INTENSITY (DAYS/WEEK)", 3, 7, 5)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("📅 INITIATE STRATEGIC BATTLE PLAN", type="primary", use_container_width=True, key="initiate_plan"):
        if not exam_date:
            st.error("⚠️ Please select an exam date first!")
        elif not st.session_state.agent_controller:
            st.error("⚠️ Agent controller not initialized. Please process documents first!")
        elif not st.session_state.vector_store or st.session_state.vector_store.get_collection_count() == 0:
            st.error("⚠️ No documents processed. Upload and process documents first!")
        else:
            try:
                with st.spinner("Calculating optimal learning trajectories... trying not to get distracted by tacos..."):
                    plan = st.session_state.agent_controller.create_revision_plan(
                        exam_date.strftime('%Y-%m-%d') if exam_date else None,
                        study_days
                    )
                if plan and len(plan) > 0:
                    st.success(f"✅ Strategic Battle Plan ready with {len(plan)} targets identified!")
                    st.rerun()
                else:
                    st.warning("⚠️ No topics found to create a plan. Please process documents first!")
            except Exception as e:
                st.error(f"⚠️ Error creating battle plan: {str(e)}")
                logger.exception("Battle plan creation failed")
    
    try:
        plan = st.session_state.agent_controller.planner_agent.load_plan()
        if plan:
            st.markdown(f'<h3 class="designer-header" style="font-size: 2.5rem;">⚔️ {len(plan)} TARGET MISSIONS IDENTIFIED</h3>', unsafe_allow_html=True)
            
            for i, item in enumerate(plan):
                item_date = item.get('date', 'TBD')
                item_topic = item.get('topic', 'General Study')
                status = item.get('status', 'pending')
                
                status_color = "#ffc107" if status == "pending" else "#28a745" if status == "completed" else "#17a2b8"
                
                st.markdown(f"""
                <div class="designer-card-red" style="transform: rotate({(i%2)*0.5 - 0.25}deg); border-width: 8px !important; padding: 2rem !important; margin-bottom: 1rem !important;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="background: #000; color: #fff; padding: 5px 15px; font-family: 'Bangers'; font-size: 1.2rem; border: 2px solid #fff;">{item_date}</span>
                            <h3 style="margin: 15px 0 5px 0; font-family: 'Bangers'; font-size: 2.2rem; color: #fff; text-shadow: 3px 3px 0px #000;">{item_topic.upper()}</h3>
                        </div>
                        <div style="text-align: right;">
                            <span style="background: {status_color}; color: #fff; padding: 8px 20px; font-family: 'Bangers'; border: 4px solid #000; font-size: 1.2rem;">{status.upper()}</span>
                        </div>
                    </div>
                    <div style="margin-top: 1.5rem; display: flex; gap: 10px;">
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button(f"🎯 COMMENCE", key=f"start_{i}"):
                        st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, "in_progress")
                        st.session_state.planner_study_mode = True
                        st.session_state.planner_study_topic = item_topic
                        st.rerun()
                with c2:
                    if st.button(f"✅ MISSION COMPLETE", key=f"comp_{i}"):
                        st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, "completed")
                        st.rerun()
                with c3:
                    if st.button(f"💤 REGROUP", key=f"pend_{i}"):
                        st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, "pending")
                        st.rerun()
                
                st.markdown('</div></div>', unsafe_allow_html=True)

                # Study Zone for Topic
                if st.session_state.get('planner_study_mode') and st.session_state.get('planner_study_topic') == item_topic:
                    st.markdown(f"""
                    <div style="background: #000; padding: 2.5rem; border: 10px dashed var(--deadpool-red); margin: 2rem 0; position: relative;">
                        <div style="position: absolute; top: -20px; left: 50%; transform: translateX(-50%); background: var(--deadpool-red); color: white; padding: 5px 30px; font-family: 'Bangers'; font-size: 1.5rem; border: 4px solid #fff;">ACTIVE TRAINING ZONE</div>
                        <h2 class='designer-header' style="font-size: 2.5rem;">TOPIC: {item_topic.upper()}</h2>
                    """, unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown('<div style="background: #1a1a1a; padding: 1.5rem; border-left: 10px solid var(--deadpool-red);">', unsafe_allow_html=True)
                        st.markdown(f"**OBJECTIVE:** Master {item_topic} using all available assets.")
                        st.markdown("---")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("📇 LOAD TOPIC CARDS", key=f"load_cards_{i}"):
                                st.session_state.current_page = "Flashcards"
                                st.rerun()
                        with col_b:
                            if st.button("💬 INTERROGATE AI", key=f"load_chat_{i}"):
                                st.session_state.current_page = "Chat Assistant"
                                st.rerun()
                        
                        if st.button("❌ CLOSE TRAINING ZONE", key=f"close_study_{item_date}_{item_topic}"):
                            st.session_state.planner_study_mode = None
                            st.session_state.planner_study_topic = None
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
    except Exception:
        logger.error("Error in planner")
        st.info("Initiate a Strategic Battle Plan to track your mission progress!")

def show_chat_page():
    """Chat assistant page with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">💬 INTEL CHAT (AI ASSISTANT)</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.latest_document:
            st.markdown(f'<div style="background: rgba(168,0,0,0.1); padding: 0.5rem 1rem; border-left: 5px solid var(--deadpool-red); color: #fff;">📄 <strong>PRIORITY ARSENAL SOURCE:</strong> {st.session_state.latest_document}</div>', unsafe_allow_html=True)
    with col2:
        if st.button("🗑️ WIPE CHAT HISTORY", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # History with Custom Bubbles
    for chat in st.session_state.chat_history:
        if isinstance(chat, tuple):
            q, a = chat
            s = []
        else:
            q = chat.get('question', '')
            a = chat.get('answer', '')
            s = chat.get('sources', [])
        
        st.markdown(f'<div class="chat-bubble user-bubble"><strong>YOU:</strong><br>{q}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble assistant-bubble"><strong>DEADPOOL:</strong><br>{a}</div>', unsafe_allow_html=True)
        
        if s:
            with st.expander("📚 MISSION SOURCE CITATIONS"):
                for src in s: st.markdown(f"• <span style='color:#aaa;'>{src}</span>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Input area
    with st.container():
        st.markdown('<div class="designer-card-red" style="border-width: 6px; padding: 2rem !important;">', unsafe_allow_html=True)
        q_input = st.text_input("💭 INTERROGATE THE SYSTEM (ASK ANYTHING):", placeholder="e.g., Explain the primary directives of the mission...")
        if st.button("🔍 INITIATE INTERROGATION", type="primary", use_container_width=True):
            if q_input:
                if not st.session_state.agent_controller:
                    st.error("⚠️ Agent controller not initialized. Please process documents first!")
                elif not st.session_state.vector_store or st.session_state.vector_store.get_collection_count() == 0:
                    st.error("⚠️ No documents processed. Upload and process documents first!")
                else:
                    try:
                        with st.spinner("Searching through the sematic archives... stay frosty..."):
                            res = st.session_state.agent_controller.answer_question(
                                q_input, 
                                prioritize_source=st.session_state.get('latest_document')
                            )
                            if res and 'answer' in res:
                                st.session_state.chat_history.append({
                                    'question': q_input, 
                                    'answer': res['answer'], 
                                    'sources': res.get('sources', [])
                                })
                                st.rerun()
                            else:
                                st.error("⚠️ Failed to get answer from agent. Please try again.")
                    except Exception as e:
                        st.error(f"⚠️ Error: {str(e)}")
                        logger.exception("Error in chat page")
        st.markdown('</div>', unsafe_allow_html=True)

def show_analytics_page():
    """Analytics and progress tracking with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">📊 MISSION INTEL DASHBOARD</h1>', unsafe_allow_html=True)
    
    if not st.session_state.agent_controller:
        st.markdown("""
        <div class="designer-card">
            <h2 class="designer-header">⚠️ NO INTEL DATA</h2>
            <p style="font-size: 1.2rem; color: #fff;">Process some documents to see your mission progress, rookie!</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    stats = st.session_state.agent_controller.get_statistics()
    
    st.markdown('<div class="designer-card" style="border-width: 6px;">', unsafe_allow_html=True)
    st.markdown('<h2 class="designer-header">📈 STUDY PROGRESS METRICS</h2>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div style="text-align:center;"><h4 class="designer-header" style="font-size:1rem;">TOPICS</h4><p style="font-size:2.5rem; font-family:Bangers; color:#fff; margin:0;">{stats["total_topics"]}</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div style="text-align:center;"><h4 class="designer-header" style="font-size:1rem;">CHUNKS</h4><p style="font-size:2.5rem; font-family:Bangers; color:#fff; margin:0;">{stats["total_chunks"]}</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div style="text-align:center;"><h4 class="designer-header" style="font-size:1rem;">FLASHCARDS</h4><p style="font-size:2.5rem; font-family:Bangers; color:#fff; margin:0;">{stats["total_flashcards"]}</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div style="text-align:center;"><h4 class="designer-header" style="font-size:1rem;">QUIZZES</h4><p style="font-size:2.5rem; font-family:Bangers; color:#fff; margin:0;">{stats["total_quizzes"]}</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="designer-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown('<h3 class="designer-header">🎯 PERFORMANCE INTEL</h3>', unsafe_allow_html=True)
        if stats['performance']['total_quizzes_taken'] > 0:
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 150px;">
                <h1 style="font-size: 4rem; font-family: 'Bangers'; color: #28a745; margin: 0;">{stats['performance']['average_score']*100:.1f}%</h1>
                <p style="font-family: 'Bangers'; font-size: 1.2rem; color: #fff;">AVERAGE MISSION ACCURACY</p>
                <p style="color: #aaa; margin-top: 10px;">TOTAL MISSIONS (QUIZZES) COMPLETED: {stats['performance']['total_quizzes_taken']}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Take some quizzes to see performance metrics, rookie!")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        if st.session_state.agent_controller.planner_agent:
            rev_stats = st.session_state.agent_controller.planner_agent.get_statistics()
            st.markdown('<div class="designer-card" style="height: 100%; border-left: 15px solid #28a745;">', unsafe_allow_html=True)
            st.markdown('<h3 class="designer-header">📅 REVISION STRATEGY PROGRESS</h3>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 150px;">
                <h1 style="font-size: 4rem; font-family: 'Bangers'; color: #fff; margin: 0;">{rev_stats['completion_rate']:.1f}%</h1>
                <p style="font-family: 'Bangers'; font-size: 1.2rem; color: #fff;">BATTLE PLAN COMPLETION</p>
                <div style="display: flex; gap: 20px; margin-top: 10px; color: #eee;">
                    <span>DONE: <strong>{rev_stats['completed']}</strong></span>
                    <span>ACTIVE: <strong>{rev_stats['in_progress']}</strong></span>
                    <span>PENDING: <strong>{rev_stats['pending']}</strong></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
