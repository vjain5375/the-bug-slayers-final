"""
AI Study Assistant - Multi-Agent System
Personalized study assistant with flashcards, quizzes, and revision planning
"""

import streamlit as st
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from vector_store import VectorStore
from agents.controller import AgentController
from utils import ensure_documents_directory, get_document_files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(page_title="Deadpool Study Hub", page_icon="💀", layout="wide")

# Initialize session state
if 'session_initialized' not in st.session_state:
    st.session_state.session_initialized = True
    st.session_state.current_page = "Home"
    st.session_state.documents_processed = False
    st.session_state.agent_controller = None
    st.session_state.vector_store = None

# --- PREMIUM RED, BLACK & WHITE THEME CSS (EXACT MATCH TO PHOTO) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@400;700&family=Inter:wght@400;700&display=swap');

    :root {
        --deadpool-red: #E62429;
        --bg-black: #05070A;
        --card-bg: #161B22;
        --white: #FFFFFF;
        --gray: #8B949E;
    }

    /* Global */
    .stApp {
        background-color: var(--bg-black);
        color: var(--white);
        font-family: 'Inter', sans-serif;
    }

    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }

    /* --- HEADER --- */
    .header-nav {
        background: var(--bg-black);
        padding: 1.2rem 8%;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid var(--deadpool-red);
    }
    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        color: var(--deadpool-red);
        font-family: 'Bangers', cursive;
        font-size: 2rem;
        letter-spacing: 1px;
    }
    .menu-links {
        display: flex;
        gap: 25px;
    }
    .menu-links a {
        color: var(--white);
        text-decoration: none;
        font-size: 0.9rem;
        text-transform: uppercase;
        font-weight: 500;
    }
    .menu-links a:hover { color: var(--deadpool-red); }

    /* --- HERO --- */
    .hero-box {
        background: linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.85)), url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg');
        background-size: cover;
        background-position: center;
        padding: 8rem 10%;
        text-align: center;
        border-bottom: 4px solid var(--deadpool-red);
    }
    .hero-h1 {
        font-family: 'Oswald', sans-serif;
        color: var(--white);
        font-size: 5.5rem;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 1.5rem;
    }
    .hero-p {
        font-size: 1.5rem;
        color: var(--white);
        opacity: 0.8;
        margin-bottom: 3rem;
    }

    /* --- DASHBOARD --- */
    .dashboard-wrap {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
        padding: 4rem 8%;
    }
    .comic-panel {
        background-color: var(--card-bg);
        border: 2px solid var(--deadpool-red);
        border-radius: 20px;
        padding: 2.5rem;
        min-height: 450px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }
    .panel-title {
        display: flex;
        align-items: center;
        gap: 12px;
        color: var(--deadpool-red);
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 2rem;
    }

    /* --- UPLOAD SECTION --- */
    .upload-box-style {
        border: 2px dashed #30363D;
        border-radius: 15px;
        padding: 4rem 2rem;
        text-align: center;
        background-color: #0D1117;
        margin-bottom: 20px;
    }
    
    /* --- BUTTONS --- */
    .stButton > button {
        background-color: var(--deadpool-red) !important;
        color: white !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        text-transform: none !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.8rem 2.5rem !important;
        transition: transform 0.1s !important;
    }
    .stButton > button:hover {
        transform: scale(1.02) !important;
        background-color: #FF3B3F !important;
    }

    /* --- TABS --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #21262D !important;
        color: var(--white) !important;
        border-radius: 10px !important;
        padding: 12px 30px !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--deadpool-red) !important;
    }

    /* --- FLASHCARD PREVIEW --- */
    .flashcard-hero {
        background: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)), url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg');
        background-size: cover;
        background-position: center;
        border-radius: 15px;
        padding: 2rem;
        min-height: 250px;
        position: relative;
        margin-top: 1.5rem;
    }
    .flashcard-inner {
        background: rgba(13, 17, 23, 0.9);
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 6px solid var(--deadpool-red);
    }
    .effort-label {
        position: absolute;
        bottom: 15px;
        right: 15px;
        background: white;
        color: black;
        padding: 5px 15px;
        border-radius: 50px;
        font-family: 'Bangers', cursive;
        font-size: 1.1rem;
        transform: rotate(-3deg);
    }

    /* Hide Sidebar */
    [data-testid="stSidebar"] { display: none !important; }

    /* Footer */
    .footer-comic {
        text-align: center;
        padding: 3rem;
        color: #444;
        border-top: 1px solid #111;
    }
</style>
""", unsafe_allow_html=True)

def initialize_components():
    if st.session_state.vector_store is None:
        try:
            st.session_state.vector_store = VectorStore()
            st.session_state.agent_controller = AgentController(st.session_state.vector_store)
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

def main():
    initialize_components()

    # --- NAVBAR ---
    st.markdown("""
    <div class="header-nav">
        <div class="brand">
            <span style="font-size: 1.8rem;">⚡</span> DEADPOOL'S STUDY HUB
        </div>
        <div class="menu-links">
            <a href="#">Home</a>
            <a href="#">Upload</a>
            <a href="#">Flashcards</a>
            <a href="#">Quizzes</a>
            <a href="#">Planner</a>
            <a href="#">Profile</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- HERO ---
    st.markdown("""
    <div class="hero-box">
        <h1 class="hero-h1">Turn Your Docs into<br><span style="color:var(--deadpool-red)">Weaponized Knowledge!</span></h1>
        <p class="hero-p">Upload, Analyze, Conquer with Flashcards, Quizzes & Smart Planners.</p>
    </div>
    """, unsafe_allow_html=True)

    # Hero Action
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("📤 Upload Document", use_container_width=True):
            st.toast("Ready for extraction!")

    # --- DASHBOARD ---
    st.markdown("<div class='dashboard-wrap'>", unsafe_allow_html=True)
    l_col, r_col = st.columns(2)

    with l_col:
        st.markdown("""
        <div class="comic-panel">
            <div class="panel-title">📄 Upload & Analyze</div>
            <div class="upload-box-style">
                <div style="font-size: 3rem; color: #444; margin-bottom: 10px;">📤</div>
                <p style="color: #8b949e; margin-bottom: 1.5rem;">Drag & drop PDF or DOCX here</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Real uploader (styled buttons in Streamlit are tricky, so we use the standard one below)
        files = st.file_uploader("Intel Input", type=['pdf','docx','txt'], accept_multiple_files=True, label_visibility="collapsed")
        if files:
            if st.button("🚀 Process Now", use_container_width=True):
                d_dir = ensure_documents_directory()
                for f in files:
                    with open(d_dir / f.name, "wb") as file: file.write(f.getbuffer())
                st.session_state.agent_controller.process_study_materials(str(d_dir))
                st.session_state.documents_processed = True
                st.balloons()

    with r_col:
        st.markdown("""
        <div class="comic-panel">
            <div class="panel-title">🧠 Generated Study Aids</div>
        </div>
        """, unsafe_allow_html=True)
        
        tabs = st.tabs(["Flashcards", "Quizzes", "Planner"])
        
        with tabs[0]:
            if st.session_state.documents_processed:
                st.success("Intel processed. Cards ready!")
            else:
                st.markdown("""
                <div class="flashcard-hero">
                    <div class="flashcard-inner">
                        <p style="color: var(--deadpool-red); font-weight: 700; font-size: 0.9rem; text-transform: uppercase;">Sample Flashcard</p>
                        <h4 style="margin: 10px 0; font-weight: 700; font-size: 1.4rem;">Q: What is the capital of France?</h4>
                        <p style="color: #8b949e; margin: 0;">A: Paris</p>
                    </div>
                    <div class="effort-label">MAXIMUM EFFORT!</div>
                </div>
                """, unsafe_allow_html=True)
        
        with tabs[1]:
            st.info("Interactive Quizzes will generate here.")
        with tabs[2]:
            st.info("Your Tactical Planner is waiting.")

    st.markdown("</div>", unsafe_allow_html=True)

    # --- FOOTER ---
    st.markdown("""
    <div class="footer-comic">
        © 2025 Deadpool's Study Hub. No regenerating degenerates allowed.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
