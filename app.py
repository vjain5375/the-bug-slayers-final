import streamlit as st
import os
import pandas as pd
from pathlib import Path
from agents.controller import AgentController
from utils.embeddings_api import get_embeddings_model
from rag_pipeline import VectorStore
import logging
import traceback
import time
import base64
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Deadpool's Study Hub",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Deadpool Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@400;700&display=swap');

    :root {
        --deadpool-red: #A80000;
        --deadpool-dark-red: #700000;
        --deadpool-black: #000000;
        --deadpool-grey: #222222;
        --deadpool-white: #FFFFFF;
    }

    /* Main Container Padding */
    .main .block-container {
        padding: 0rem !important;
        max-width: 100% !important;
    }

    /* App Border Frame */
    .stApp {
        background-color: #000 !important;
        border: 20px solid var(--deadpool-red) !important;
        outline: 4px solid #fff !important;
        outline-offset: -12px !important;
    }

    /* Halftone Pattern Overlay */
    .halftone {
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-image: radial-gradient(var(--deadpool-red) 1px, transparent 1px);
        background-size: 20px 20px;
        opacity: 0.05;
        pointer-events: none;
        z-index: 1;
    }

    /* Global Typography */
    h1, h2, h3, h4, h5, h6, .designer-header, .stButton > button, .stDownloadButton > button {
        font-family: 'Bangers', cursive !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
    }

    p, li, label, div, span {
        font-family: 'Oswald', sans-serif !important;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 12px;
        background: #000;
    }
    ::-webkit-scrollbar-thumb {
        background: var(--deadpool-red);
        border: 3px solid #000;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #000 !important;
        border-right: 5px solid var(--deadpool-red) !important;
    }

    /* Uniform Comic Buttons - OVERHAULED FOR MAXIMUM BEAUTY */
    .stButton > button, .stDownloadButton > button {
        font-family: 'Bangers', cursive !important;
        background-color: var(--deadpool-red) !important;
        background-image: radial-gradient(circle at 20% 20%, rgba(255,255,255,0.2) 0%, transparent 40%) !important;
        color: white !important;
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        font-style: italic !important;
        border: 6px solid #FFF !important; /* Thicker white border */
        border-radius: 0px !important;
        padding: 1rem 2rem !important;
        box-shadow: 15px 15px 0px #000 !important; /* Heavier black shadow */
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        width: 100% !important;
        min-height: 90px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1 !important;
        margin-bottom: 15px !important;
        transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        transform: skew(-2deg);
        position: relative !important;
        overflow: hidden !important;
        text-shadow: 4px 4px 0px #000 !important;
    }

    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #fff !important;
        color: var(--deadpool-red) !important;
        transform: skew(-2deg) translate(-5px, -5px) scale(1.02) !important;
        box-shadow: 18px 18px 0px #000 !important;
        border-color: #000 !important;
        text-shadow: none !important;
    }
    
    .stButton > button:active {
        transform: skew(-3deg) translate(2px, 2px) !important;
        box-shadow: 2px 2px 0px #000 !important;
    }

    /* Navigation Grid Specifics - THE "NON-DABBA" LOOK */
    [data-testid="stHorizontalBlock"] div div div .stButton > button {
        height: 140px !important; 
        background-color: var(--deadpool-red) !important;
        border-width: 6px !important;
        font-size: 1.8rem !important;
        font-weight: 900 !important;
        font-style: italic !important;
        letter-spacing: 1px !important;
        line-height: 1.1 !important;
    }
    
    /* Active Navigation Button - NO MORE WHITE "DABBA" */
    [data-testid="stHorizontalBlock"] div div div .stButton > button[kind="primary"] {
        background-color: var(--deadpool-red) !important;
        color: white !important;
        border-color: white !important;
        transform: skew(-3deg) scale(1.05) !important;
        box-shadow: 0 0 15px rgba(255,255,255,0.3), 10px 10px 0px #000 !important;
        z-index: 10 !important;
    }
    
    [data-testid="stHorizontalBlock"] div div div .stButton > button[kind="primary"]::before {
        border-color: rgba(255,255,255,0.6);
    }

    /* Sidebar Fancy Navigation Buttons - SYNCED WITH BROWSE BUTTON */
    [data-testid="stSidebar"] .stButton > button {
        text-align: center !important;
        justify-content: center !important;
        padding: 0.5rem 1rem !important;
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        font-style: italic !important;
        letter-spacing: 1.5px !important;
        text-shadow: 4px 4px 0px #000 !important;
        min-height: 95px !important;
        margin-bottom: 15px !important;
        background-color: var(--deadpool-red) !important;
        background-image: none !important;
        border: 6px solid #FFF !important;
        box-shadow: 12px 12px 0px #000 !important;
        color: white !important;
        transform: none !important;
        border-radius: 0px !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: var(--deadpool-red) !important;
        color: white !important;
        border-color: #FFF !important;
        transform: translate(-5px, -5px) !important;
        box-shadow: 15px 15px 0px #000 !important;
    }

    [data-testid="stSidebar"] .stButton > button:focus, 
    [data-testid="stSidebar"] .stButton > button:active {
        background-color: var(--deadpool-red) !important;
        color: white !important;
        border-color: #FFF !important;
        box-shadow: 10px 10px 0px #000 !important;
    }

    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background-color: var(--deadpool-red) !important;
        color: white !important;
        border-color: #FFF !important;
        box-shadow: 12px 12px 0px #000 !important;
        transform: scale(1.05) !important;
        z-index: 10 !important;
    }

    /* Input Labels and Fonts */
    label, .stMarkdown p, .stMarkdown li {
        font-family: 'Oswald', sans-serif !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        color: #fff !important;
    }

    /* Selectbox, Slider, Radio Styling */
    .stSelectbox div[data-baseweb="select"] {
        background-color: #000 !important;
        border: 3px solid var(--deadpool-red) !important;
        border-radius: 0px !important;
    }
    .stSelectbox div[data-baseweb="select"] div {
        color: white !important;
        font-family: 'Oswald', sans-serif !important;
    }
    
    div[data-testid="stThumbValue"] {
        font-family: 'Bangers' !important;
        color: var(--deadpool-red) !important;
        font-size: 1.5rem !important;
    }
    
    .stSlider [data-testid="stTickBar"] {
        display: none;
    }

    /* Radio buttons */
    [data-testid="stWidgetLabel"] p {
        font-family: 'Bangers', cursive !important;
        font-size: 1.2rem !important;
        color: var(--deadpool-red) !important;
    }
    
    [data-testid="stRadio"] label {
        background: #111 !important;
        border: 2px solid #333 !important;
        padding: 10px 15px !important;
        margin-bottom: 5px !important;
        width: 100% !important;
        transition: all 0.2s !important;
    }
    
    [data-testid="stRadio"] label:hover {
        border-color: var(--deadpool-red) !important;
        background: #1a1a1a !important;
    }
    
    [data-testid="stRadio"] div[role="radiogroup"] {
        gap: 0px !important;
    }

    /* Primary Actions */
    .stButton > button[kind="primary"] {
        background-color: var(--deadpool-red) !important;
        border-color: #FFF !important;
        color: #fff !important;
    }
    
    .stButton > button[kind="secondary"] {
        background-color: var(--deadpool-red) !important;
        border-color: #FFF !important;
        color: #fff !important;
        opacity: 0.8; /* Slight dimming for secondary action, but still red/white */
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #000 !important;
        border: 4px solid #FFF !important; /* White border */
        padding: 1.5rem !important;
        box-shadow: 8px 8px 0px #A80000 !important; /* Red shadow */
    }

    [data-testid="stMetricLabel"] {
        color: var(--deadpool-red) !important;
        font-family: 'Bangers', cursive !important;
        font-size: 1.5rem !important;
        text-shadow: 2px 2px 0px #000;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        background-color: #111 !important;
        border: 4px solid #FFF !important;
        color: #fff !important;
        font-size: 1.2rem !important;
        border-radius: 0px !important;
        font-family: 'Oswald', sans-serif !important;
        box-shadow: 5px 5px 0px var(--deadpool-red) !important;
    }

    /* Surgical uploader fix */
    [data-testid="stFileUploader"] {
        border: 3px dashed var(--deadpool-red) !important;
        background-color: #080808 !important;
        padding: 1rem !important;
        border-radius: 0px !important;
        box-shadow: inset 0 0 10px rgba(168,0,0,0.2) !important;
    }
    
    [data-testid="stFileUploader"] section {
        padding: 0 !important;
    }
    
    [data-testid="stFileUploader"] label {
        color: var(--deadpool-red) !important;
        font-family: 'Bangers' !important;
        font-size: 1.5rem !important;
    }

    /* Markdown Text */
    h1, h2, h3 {
        font-family: 'Bangers', cursive !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
        margin-top: 0px !important;
        margin-bottom: 0.5rem !important;
    }

    h1 { color: var(--deadpool-red) !important; font-size: 3.5rem !important; text-shadow: 3px 3px 0px #000 !important; }
    h2 { color: #fff !important; font-size: 2rem !important; border-bottom: 3px solid var(--deadpool-red); display: inline-block; }
    h3 { color: var(--deadpool-red) !important; font-size: 1.5rem !important; }
    
    /* Better spacing for main content */
    .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        max-width: 1200px !important;
    }

    /* Designer Comic Card with Flair */
    .designer-card {
        background: #000 !important;
        border: 5px solid #FFF !important; /* Thick white border like screenshot */
        padding: 2rem !important;
        box-shadow: 15px 15px 0px #000 !important;
        margin-bottom: 2rem !important;
        position: relative;
        overflow: visible !important;
        z-index: 1;
    }
    .designer-card::before {
        content: "";
        position: absolute;
        top: -50%; left: -50%; width: 200%; height: 200%;
        background-image: radial-gradient(circle, rgba(168,0,0,0.1) 1px, transparent 1px);
        background-size: 15px 15px;
        z-index: -1;
        pointer-events: none;
    }
    .designer-header {
        font-family: 'Bangers', cursive !important;
        color: var(--deadpool-red) !important;
        text-shadow: 2px 2px 0px #000;
        text-transform: uppercase;
        transform: rotate(-1deg);
        display: inline-block;
        margin-bottom: 1rem !important;
    }

    /* Chat Bubbles */
    .chat-bubble {
        padding: 1rem 1.5rem !important;
        border-radius: 0px !important;
        margin-bottom: 1rem !important;
        font-family: 'Oswald', sans-serif !important;
        position: relative !important;
        border: 3px solid #000 !important;
        box-shadow: 5px 5px 0px #000 !important;
        max-width: 85% !important;
    }
    .user-bubble {
        background-color: #333 !important;
        color: #fff !important;
        margin-left: auto !important;
        border-right: 8px solid var(--deadpool-red) !important;
    }
    .assistant-bubble {
        background-color: var(--deadpool-red) !important;
        color: #fff !important;
        margin-right: auto !important;
        border-left: 8px solid #fff !important;
    }
    
    /* Custom Deadpool Balloons */
    @keyframes floatUp {
        0% { transform: translateY(100vh) rotate(0deg); opacity: 1; }
        100% { transform: translateY(-100vh) rotate(360deg); opacity: 0; }
    }
    .deadpool-balloon {
        position: fixed;
        bottom: -100px;
        width: 40px;
        height: 55px;
        border-radius: 50% 50% 50% 50% / 40% 40% 60% 60%;
        z-index: 99999;
        pointer-events: none;
    }
    .balloon-red { background: #A80000; border: 3px solid #000; }
    .balloon-black { background: #000; border: 3px solid #A80000; }
    .balloon-white { background: #fff; border: 3px solid #000; }
    
    /* Global spacing reduction */
    [data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
    }

    /* Remove streamlit default top padding */
    .st-emotion-cache-1y4p8pa, .st-emotion-cache-z5fcl4, .st-emotion-cache-uf99v8 { 
        padding-top: 0px !important; 
        padding-bottom: 0px !important; 
    }
    
    /* Remove gaps from columns */
    [data-testid="stHorizontalBlock"] {
        gap: 0.3rem !important;
    }

    /* Surgical spacing for cards */
    .designer-card {
        margin-top: 0px !important;
        margin-bottom: 0.5rem !important;
        padding: 1.2rem !important;
    }
    /* Compact Success/Info/Error Messages */
    .stSuccess, .stInfo, .stError, .stWarning {
        padding: 0.5rem 1rem !important;
        border-radius: 0px !important;
        font-size: 0.9rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
<div class="halftone"></div>
""", unsafe_allow_html=True)

def initialize_components():
    """Initialize vector store and agent controller with robust error handling"""
    api_key = load_api_key()
    
    if st.session_state.vector_store is None:
        # Show static loading message
        loading_msg = st.info("Initializing vector store...")
        try:
            st.session_state.vector_store = VectorStore()
            loading_msg.empty()
            # Log successful initialization
            backend = st.session_state.vector_store.embedding_backend
            st.success(f"✅ Vector store initialized using {backend} backend")
        except Exception:
            loading_msg.empty()
            tb = traceback.format_exc()
            logger.exception("VectorStore init failed: %s", tb)
            
            # Show user-friendly error message
            st.error("""
            ⚠️ **Failed to initialize vector store / embeddings**
            
            **Possible solutions:**
            1. Set `EMBEDDING_BACKEND=api` in your environment variables and provide API keys:
               - `OPENAI_API_KEY` for OpenAI embeddings, or
               - `GOOGLE_API_KEY` for Gemini (if supported)
            
            2. For local embeddings, ensure `torch>=2.0.0` is installed:
               ```bash
               pip install torch --index-url https://download.pytorch.org/whl/cpu
               ```
            
            3. Check the logs for detailed error information.
            """)
            
    if st.session_state.agent_controller is None:
        st.session_state.agent_controller = AgentController(api_key)

def load_api_key():
    """Load API key from environment"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("GOOGLE_API_KEY")

def ensure_documents_directory():
    """Ensure the documents directory exists"""
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    return docs_dir

def get_document_files():
    """Get list of files in documents directory"""
    docs_dir = ensure_documents_directory()
    return list(docs_dir.glob("*"))

def _compute_docs_signature(doc_files):
    """Compute a signature based on file names and modification times"""
    import hashlib
    if not doc_files:
        return ""
    
    files_info = []
    for f in doc_files:
        if f.exists():
            files_info.append(f"{f.name}_{f.stat().st_mtime}")
    
    files_info.sort()
    return hashlib.md5("".join(files_info).encode()).hexdigest()

# Initialize Session State
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"
if 'vector_store' not in st.session_state:
            st.session_state.vector_store = None
if 'agent_controller' not in st.session_state:
    st.session_state.agent_controller = None
if 'flashcards' not in st.session_state:
    st.session_state.flashcards = []
if 'quizzes' not in st.session_state:
    st.session_state.quizzes = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'num_flashcards' not in st.session_state:
    st.session_state.num_flashcards = 10
if 'num_questions' not in st.session_state:
    st.session_state.num_questions = 5
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'uploaded_files_shared' not in st.session_state:
    st.session_state.uploaded_files_shared = None
if 'document_upload_order' not in st.session_state:
    st.session_state.document_upload_order = []
if 'latest_document' not in st.session_state:
    st.session_state.latest_document = None
if 'balloons_queued' not in st.session_state:
    st.session_state.balloons_queued = False

def trigger_deadpool_balloons(queued=False):
    """Trigger custom red, black, and white balloons. If queued=True, sets a flag for next render."""
    if queued:
        st.session_state.balloons_queued = True
        return

    import random
    balloons_html = ""
    # Strictly Red, Black, White
    colors = ["#A80000", "#000000", "#FFFFFF"] 
    border_colors = ["#000000", "#A80000", "#000000"]
    
    for i in range(50): # Even more balloons!
        idx = random.randint(0, 2)
        color = colors[idx]
        border = border_colors[idx]
        left = random.randint(0, 95)
        duration = random.uniform(2.0, 4.0) # Faster and punchier
        delay = random.uniform(0, 1.2) # Spread them out more
        size = random.randint(80, 120) # MASSIVE BALLOONS as requested
        
        balloons_html += f"""
        <div class="deadpool-balloon-instance" style="
            left: {left}vw; 
            animation: floatUpAnim {duration}s cubic-bezier(0.25, 0.46, 0.45, 0.94) {delay}s forwards;
            background: {color};
            border: 5px solid {border};
            width: {size}px;
            height: {size*1.3}px;
            box-shadow: inset -10px -10px 20px rgba(0,0,0,0.4), 10px 10px 0px rgba(0,0,0,0.2);
        ">
            <div style="position: absolute; top: 15%; left: 15%; width: 25%; height: 20%; background: rgba(255,255,255,0.3); border-radius: 50%;"></div>
        </div>"""
    
    st.markdown(f"""
        <style>
            @keyframes floatUpAnim {{
                0% {{ transform: translateY(0) rotate(0deg); opacity: 1; }}
                100% {{ transform: translateY(-120vh) rotate(360deg); opacity: 0; }}
            }}
            .deadpool-balloon-instance {{
                position: fixed;
                bottom: -150px;
                border-radius: 50% 50% 50% 50% / 40% 40% 60% 60%;
                z-index: 999999;
                pointer-events: none;
                box-shadow: inset -5px -5px 10px rgba(0,0,0,0.3);
            }}
            /* Add a string to the balloon */
            .deadpool-balloon-instance::after {{
                content: "";
                position: absolute;
                bottom: -20px;
                left: 50%;
                width: 2px;
                height: 20px;
                background: #666;
            }}
        </style>
        <div id="balloon-container" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 999999;">
            {balloons_html}
        </div>
        <script>
            setTimeout(() => {{
                const container = document.getElementById("balloon-container");
                if (container) container.remove();
            }}, 6000);
        </script>
    """, unsafe_allow_html=True)

def process_documents():
    """Process all documents using Reader Agent"""
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    
    if not doc_files:
        st.error("No documents found. Please upload PDF, DOCX, or TXT files.")
        return False
    
    # Skip reprocessing if nothing has changed
    signature = _compute_docs_signature(doc_files)
    if (
        signature
        and st.session_state.documents_processed
        and st.session_state.get('processing_results')
        and st.session_state.get('last_processed_signature') == signature
    ):
        st.info("Documents unchanged. Skipping reprocessing.")
        return True
    
    # Update latest document based on upload order (most recent is last)
    if st.session_state.document_upload_order:
        st.session_state.latest_document = st.session_state.document_upload_order[-1]
    else:
        # Fallback: use most recently modified file
        doc_files_with_time = [(Path(doc).stat().st_mtime, doc) for doc in doc_files if Path(doc).exists()]
        if doc_files_with_time:
            doc_files_with_time.sort(reverse=True)
            st.session_state.latest_document = Path(doc_files_with_time[0][1]).name
    
    # Show static processing message
    processing_msg = st.info("Processing documents with Reader Agent...")
    result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
    
    if result and result.get('total_chunks', 0) > 0:
        st.session_state.documents_processed = True
        st.session_state.processing_results = result
        st.session_state.last_processed_signature = signature
        processing_msg.empty()
        trigger_deadpool_balloons(queued=True)
        return True
    else:
        processing_msg.empty()
        st.error("No content could be extracted from documents.")
        return False

def main():
    """Main application"""
    # Trigger any queued balloons first
    if st.session_state.get('balloons_queued', False):
        trigger_deadpool_balloons()
        st.session_state.balloons_queued = False
    
    # Deadpool Branding Header - NOW AT THE VERY TOP
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem; margin-top: -4.5rem; position: relative; z-index: 100;">
        <div style="display: flex; align-items: center; justify-content: center; gap: 25px;">
            <div style="background: #A80000; padding: 15px 40px; border: 6px solid #fff; transform: rotate(-2deg); box-shadow: 12px 12px 0px #000; display: flex; align-items: center; gap: 30px;">
                <span style="font-family: 'Bangers', cursive !important; font-size: 5.5rem; color: #ffffff !important; text-shadow: 5px 5px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic; letter-spacing: 2px;">⚔️ THE ARSENAL</span>
                <span style="font-family: 'Bangers', cursive !important; font-size: 5.5rem; color: #ffffff !important; text-shadow: 5px 5px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic; letter-spacing: 2px;">STUDY HUB</span>
            </div>
        </div>
        <div style="background: #A80000; color: #ffffff !important; font-family: 'Bangers', cursive !important; font-size: 2rem; padding: 10px 40px; display: inline-block; transform: skew(-10deg); border: 4px solid #fff; margin-top: 25px; box-shadow: 10px 10px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic;">
            MAXIMUM EFFORT ONLY! NO ROOKIES ALLOWED!
        </div>
    </div>
    """, unsafe_allow_html=True)

    initialize_components()
    
    # Sidebar - Navigation and Document Management
    with st.sidebar:
        # MISSION PROTOCOL FLOWCHART - Top of Sidebar
        st.markdown("""
        <div class="designer-card" style="padding: 1.2rem; border-width: 5px; margin-bottom: 2rem;">
            <h2 class="designer-header" style="font-size: 1.8rem; text-align: center; display: block; margin-bottom: 1.5rem;">⚔️ MISSION FLOW</h2>
            <div style="position: relative;">
                <div style="display: flex; align-items: center; margin-bottom: 1rem; background: rgba(168,0,0,0.1); padding: 8px; border-left: 4px solid var(--deadpool-red);">
                    <div style="background: #000; color: white; width: 30px; height: 30px; border-radius: 0; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid var(--deadpool-red); font-family: 'Bangers'; transform: rotate(-5deg);">1</div>
                    <div style="margin-left: 15px; font-size: 1.1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">📤 LOAD UP</div>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem; background: rgba(168,0,0,0.1); padding: 8px; border-left: 4px solid var(--deadpool-red);">
                    <div style="background: #000; color: white; width: 30px; height: 30px; border-radius: 0; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid var(--deadpool-red); font-family: 'Bangers'; transform: rotate(5deg);">2</div>
                    <div style="margin-left: 15px; font-size: 1.1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">💾 LOCK IT</div>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem; background: rgba(168,0,0,0.1); padding: 8px; border-left: 4px solid var(--deadpool-red);">
                    <div style="background: #000; color: white; width: 30px; height: 30px; border-radius: 0; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid var(--deadpool-red); font-family: 'Bangers'; transform: rotate(-3deg);">3</div>
                    <div style="margin-left: 15px; font-size: 1.1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">🔄 SLICE IT</div>
                </div>
                <div style="display: flex; align-items: center; background: var(--deadpool-red); padding: 8px; border: 2px solid #000; box-shadow: 4px 4px 0px #000;">
                    <div style="background: #000; color: white; width: 30px; height: 30px; border-radius: 0; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #fff; font-family: 'Bangers'; transform: rotate(10deg);">4</div>
                    <div style="margin-left: 15px; font-size: 1.1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1.5px;">🛡️ DOMINATE</div>
                </div>
            </div>
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
            
            # Sidebar Active Marker (Premium Comic Arrow) - Height Matched to Buttons
            col_marker, col_btn = st.columns([2, 8])
            with col_marker:
                if is_active:
                    st.markdown("""
                    <div style='height: 95px; display: flex; align-items: center; justify-content: center; margin-right: -10px;'>
                        <div style="font-size: 3.5rem; color: white; filter: drop-shadow(4px 4px 0px #000);">▶</div>
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
        
    # Upload Section in Main Dashboard - SEXY EDITION
    st.markdown("""
<style>
@keyframes tactical-glow {
    0% { box-shadow: 0 0 10px rgba(168,0,0,0.4), inset 0 0 10px rgba(168,0,0,0.2); }
    50% { box-shadow: 0 0 30px rgba(168,0,0,0.8), inset 0 0 20px rgba(168,0,0,0.4); }
    100% { box-shadow: 0 0 10px rgba(168,0,0,0.4), inset 0 0 10px rgba(168,0,0,0.2); }
}
@keyframes stripes-move {
    from { background-position: 0 0; }
    to { background-position: 40px 0; }
}
.sexy-drop-zone {
    position: relative;
    margin-bottom: 3rem;
    overflow: visible;
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.sexy-drop-zone:hover {
    transform: scale(1.02) rotate(-0.5deg);
}
.tactical-border {
    position: absolute;
    top: -15px; left: -15px; right: -15px; bottom: -15px;
    background-color: #A80000;
    background-image: radial-gradient(#000 20%, transparent 20%);
    background-size: 8px 8px;
    z-index: 0;
    border: 4px solid #000;
    box-shadow: 15px 15px 0px #000;
}
.command-center {
    position: relative;
    z-index: 1;
    padding: 3rem;
    text-align: center;
    background: #000;
    border: 6px solid #fff;
    animation: tactical-glow 3s infinite;
}
.moving-danger-stripes {
    height: 25px;
    width: 100%;
    background: repeating-linear-gradient(45deg, #A80000, #A80000 20px, #000 20px, #000 40px);
    background-size: 40px 100%;
    animation: stripes-move 1s linear infinite;
    border: 3px solid #fff;
    margin: 1.5rem 0;
}
.pop-art-label {
    font-family: 'Bangers';
    font-size: 1.5rem;
    color: #fff;
    background: #A80000;
    padding: 5px 15px;
    border: 3px solid #000;
    display: inline-block;
    transform: rotate(-3deg);
    position: absolute;
    top: -20px;
    left: 20px;
    box-shadow: 5px 5px 0px #000;
    z-index: 5;
}
</style>

<div class="sexy-drop-zone">
<div class="tactical-border"></div>
<div class="command-center">
<div class="pop-art-label">CLASSIFIED ARCHIVES</div>

<!-- Tactical Header -->
<div style="display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 1rem;">
    <div style="background: #A80000; padding: 15px 40px; border: 6px solid #fff; transform: rotate(-4deg); box-shadow: 12px 12px 0px #000; display: flex; align-items: center; gap: 30px;">
        <span style="font-family: 'Bangers', cursive !important; font-size: 4rem; color: #ffffff !important; text-shadow: 4px 4px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic; letter-spacing: 2px;">⚔️ ARSENAL</span>
        <span style="font-family: 'Bangers', cursive !important; font-size: 5.5rem; color: #ffffff !important; text-shadow: 6px 6px 0px #000; -webkit-text-fill-color: #ffffff !important; font-style: italic; letter-spacing: 3px;">PORTAL</span>
    </div>
</div>

<!-- Deadpool Interactive Sticker -->
<div style="position: absolute; right: -50px; bottom: -40px; z-index: 10; transform: rotate(-10deg); transition: all 0.3s;">
<img src="https://i.pinimg.com/originals/e0/61/8c/e0618c66e92b34a413d90708573138b7.png" style="width: 150px; filter: drop-shadow(8px 8px 0px #000);">
</div>

<p style="font-family: 'Bangers'; font-size: 2rem; color: #fff; letter-spacing: 3px; margin: 1.5rem 0;">
DROP YOUR <span style="color: #ffffff !important; font-size: 2.5rem; text-shadow: 3px 3px 0px #A80000; -webkit-text-fill-color: #ffffff !important;">BRAIN JUICE</span> HERE!
</p>

    <div class="moving-danger-stripes"></div>
</div>
</div>
""", unsafe_allow_html=True)

    # Custom styling for the file uploader to make it look like part of the portal
    st.markdown("""
    <style>
        [data-testid="stFileUploader"] {
            background-color: #000 !important;
            border: 5px solid #FFF !important;
            padding: 2.5rem !important;
            box-shadow: 12px 12px 0px #000 !important;
            position: relative !important;
            margin-top: -2rem !important;
        }
        /* Surgical precision: Hide only the boring parts, KEEP THE BUTTON */
        [data-testid="stFileUploader"] section > div:first-child {
            display: none !important;
        }
        [data-testid="stFileUploader"] section {
            padding: 0 !important;
            border: none !important;
            background: transparent !important;
        }
        [data-testid="stFileUploader"] label {
            display: none !important;
        }
        [data-testid="stFileUploader"] button {
            width: 100% !important;
            height: 110px !important;
            background: #A80000 !important;
            color: white !important;
            font-size: 3.5rem !important;
            font-family: 'Bangers' !important;
            font-weight: 900 !important;
            font-style: italic !important;
            border: 6px solid #fff !important;
            box-shadow: 15px 15px 0px #000 !important;
            border-radius: 0px !important;
            text-transform: uppercase !important;
            transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            cursor: pointer !important;
            text-shadow: 4px 4px 0px #000 !important;
        }
        [data-testid="stFileUploader"] button:hover {
            transform: scale(1.05) translateY(-5px) !important;
            background: #fff !important;
            color: #A80000 !important;
            box-shadow: 18px 18px 0px #000 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Upload area in main section - Synced with sidebar
    if 'uploaded_files_shared' not in st.session_state:
        st.session_state.uploaded_files_shared = None
    
        uploaded_files_main = st.file_uploader(
            "📎 Choose files to upload",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=True,
            key="main_uploader",
        help="Select one or more study material files (PDF, DOCX, TXT)",
        label_visibility="collapsed"
        )
    
        # Sync with sidebar
        if uploaded_files_main:
            st.session_state.uploaded_files_shared = uploaded_files_main

    # Visual status badges
    if uploaded_files_main or st.session_state.uploaded_files_shared:
        f_count = len(uploaded_files_main) if uploaded_files_main else len(st.session_state.uploaded_files_shared)
        st.markdown(f"""
        <div style="background: #A80000; color: white; padding: 10px; border: 3px solid #000; text-align: center; font-family: 'Bangers'; transform: rotate(2deg); box-shadow: 5px 5px 0px #000; margin-bottom: 1rem;">
            ✅ {f_count} TARGETS LOCKED! READY FOR SLICING!
        </div>
        """, unsafe_allow_html=True)
    
    # Use shared uploaded files if main uploader is empty but sidebar has files
    files_to_process = uploaded_files_main if uploaded_files_main else st.session_state.uploaded_files_shared
    
    # Save and Process buttons
    if files_to_process:
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 SAVE", use_container_width=True, type="primary", key="save_main_files"):
                docs_dir = ensure_documents_directory()
                saved = 0
                saved_files = []
                for uploaded_file in files_to_process:
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
                        st.session_state.latest_document = saved_files[-1]  # Most recently saved
                    st.success(f"✅ Saved {saved} document(s)!")
                    st.session_state.documents_processed = False
                    st.session_state.uploaded_files_shared = None  # Clear after saving
                    st.rerun()
                else:
                    st.info("Files already exist or no new files to save.")
        
        with col2:
            if st.button("🔄 PROCESS", use_container_width=True, type="primary", key="process_main_files"):
                # First save files if not saved
                docs_dir = ensure_documents_directory()
                saved_files = []
                for uploaded_file in files_to_process:
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
                
                # Then process
                if process_documents():
                    st.session_state.uploaded_files_shared = None  # Clear after processing
                    st.rerun()
    
    # Show existing documents
    doc_files = get_document_files()
    if doc_files:
        st.markdown("### 📁 YOUR DOCUMENTS")
        with st.expander(f"View {len(doc_files)} uploaded document(s)", expanded=False):
            for doc in doc_files:
                doc_name = Path(doc).name
                st.markdown(f"📄 **{doc_name}**")
    
    # Top Navigation Grid - Designer Edition
    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
    st.markdown("<p style='font-family: \"Bangers\"; font-size: 1.4rem; color: var(--deadpool-red); margin-bottom: 0.2rem; text-shadow: 2px 2px 0px #000;'>🎯 NAVIGATION</p>", unsafe_allow_html=True)
    
    nav_options = {
        "Home": "🏠",
        "Flashcards": "📇",
        "Quizzes": "📝",
        "Revision Planner": "📅",
        "Chat Assistant": "💬",
        "Analytics": "📊"
    }
    
    nav_cols = st.columns(6)
    for idx, (page_name, icon) in enumerate(nav_options.items()):
        with nav_cols[idx]:
            is_active = st.session_state.current_page == page_name
            button_type = "primary" if is_active else "secondary"
            # Format text: Icon and Name on separate lines, but don't split words
            button_label = f"{icon}\n{page_name}"
            
            # Active Page Indicator (Comic Arrow Style) - Height Matched to Buttons
            if is_active:
                st.markdown("""
                <div style="text-align: center; margin-bottom: -20px; position: relative; z-index: 100;">
                    <div style="font-size: 2.5rem; color: white; filter: drop-shadow(0px 4px 2px rgba(0,0,0,0.5)); transform: rotate(90deg) translateX(-5px); display: inline-block;">▶</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                
            nav_button = st.button(button_label, use_container_width=True, key=f"main_nav_{page_name}", type=button_type)
            if nav_button:
                st.session_state.current_page = page_name
                st.rerun()
    
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
    <div style="background: url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg') center/cover; padding: 4rem 1rem; border: 6px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); text-align: center; margin-bottom: 2rem; position: relative;">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65);"></div>
        <div style="position: relative; z-index: 2;">
            <h1 class="designer-header" style="font-size: 3.5rem; text-shadow: 4px 4px 0px #000; margin: 0;">Turn Your Docs into Weaponized Knowledge!</h1>
            <p style="font-family: 'Bangers', cursive; color: #fff; font-size: 1.6rem; background: #000; display: inline-block; padding: 0.5rem 2rem; transform: skew(-10deg); margin-top: 1.5rem; border: 3px solid var(--deadpool-red); box-shadow: 5px 5px 0px #000;">Upload, Analyze, Conquer with AI-Powered Intelligence.</p>
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
            <div class="designer-card" style="transform: rotate(-0.5deg);">
                <h3 class="designer-header" style="font-size: 2rem;">1️⃣ LOAD UP</h3>
                <p style="color: #fff; font-size: 1.2rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Drop your PDFs, DOCX, or Text notes into the side-feed.</p>
            </div>
            <div class="designer-card" style="transform: rotate(0.5deg);">
                <h3 class="designer-header" style="font-size: 2rem;">3️⃣ EXTRACT</h3>
                <p style="color: #fff; font-size: 1.2rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'PROCESS'</b>. My agents will slice and dice your text into pure semantic gold.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="designer-card" style="transform: rotate(0.5deg);">
                <h3 class="designer-header" style="font-size: 2rem;">2️⃣ LOCK & LOAD</h3>
                <p style="color: #fff; font-size: 1.2rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'SAVE'</b> to commit those files to my infinite memory banks.</p>
            </div>
            <div class="designer-card" style="transform: rotate(-0.5deg);">
                <h3 class="designer-header" style="font-size: 2rem;">4️⃣ DOMINATE</h3>
                <p style="color: #fff; font-size: 1.2rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Maximum Effort! 💥 Flashcards, Quizzes, and Chat are now operational.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # Add the thumbs up Deadpool image
        st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", width=350)
        
        return
    
    # CASE 2: RETURNING USER (Pro Dashboard)
    st.markdown("<h2 class='designer-header' style='font-size: 2.5rem;'>⚡ COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    # 1. High-Impact Quick Access
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📇 CARDS", use_container_width=True, key="dash_flash"):
            st.session_state.current_page = "Flashcards"; st.rerun()
    with col2:
        if st.button("📝 QUIZ", use_container_width=True, key="dash_quiz"):
            st.session_state.current_page = "Quizzes"; st.rerun()
    with col3:
        if st.button("📅 PLAN", use_container_width=True, key="dash_plan"):
            st.session_state.current_page = "Revision Planner"; st.rerun()
    with col4:
        if st.button("💬 CHAT", use_container_width=True, key="dash_chat"):
            st.session_state.current_page = "Chat Assistant"; st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Performance Stats
    if st.session_state.agent_controller:
        stats = st.session_state.agent_controller.get_statistics()
        st.markdown("<h3 class='designer-header'>📊 MISSION INTEL</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: 
            st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">TOPICS</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0;">{stats["total_topics"]}</p></div>', unsafe_allow_html=True)
        with c2: 
            st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">CARDS</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0;">{stats["total_flashcards"]}</p></div>', unsafe_allow_html=True)
        with c3: 
            st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">QUIZZES</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff; margin: 0;">{stats["total_quizzes"]}</p></div>', unsafe_allow_html=True)
        with c4: 
            st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">WIN RATE</h4><p style="font-size: 2rem; font-family: Bangers; color: #28a745; margin: 0;">{stats["revision_stats"]["completion_rate"]:.1f}%</p></div>', unsafe_allow_html=True)

    st.divider()

    # 3. Content Intelligence
    if 'processing_results' in st.session_state:
        p_result = st.session_state.processing_results
        col_topics, col_samples = st.columns([2, 1])
        
        with col_topics:
            if p_result.get('topics'):
                st.markdown("<h3 class='designer-header'>📚 WEAPONIZED TOPICS</h3>", unsafe_allow_html=True)
                for idx, topic_data in enumerate(p_result['topics'][:5], 1):
                    with st.expander(f"🔴 {topic_data.get('topic', 'Topic').upper()}", expanded=(idx == 1)):
                        if topic_data.get('key_points'):
                            for p in topic_data['key_points'][:3]: st.markdown(f"⚔️ {p}")
        
        with col_samples:
            st.markdown("<h3 class='designer-header'>📄 INTEL SNAPS</h3>", unsafe_allow_html=True)
            if p_result.get('flashcard_samples'):
                with st.expander("📇 SAMPLE CARDS", expanded=True):
                    for fs in p_result['flashcard_samples'][:2]:
                        st.markdown(f"""
                        <div style="background: #111; padding: 1rem; border-left: 4px solid var(--deadpool-red); margin-bottom: 10px; border-radius: 0px;">
                            <p style="color: #fff; font-size: 0.9rem;"><b>Q:</b> {fs['question']}</p>
                            <hr style="margin: 5px 0; border-color: #333;">
                            <p style="color: #aaa; font-size: 0.85rem;"><b>A:</b> {fs['answer']}</p>
        </div>
        """, unsafe_allow_html=True)
            
            if p_result.get('quiz_samples'):
                with st.expander("📝 SAMPLE CHALLENGES", expanded=False):
                    for qs in p_result['quiz_samples'][:2]:
                        st.markdown(f"""
                        <div style="background: #111; padding: 1rem; border-left: 4px solid #fff; margin-bottom: 10px; border-radius: 0px;">
                            <p style="color: #fff; font-size: 0.9rem;">{qs['question']}</p>
        </div>
        """, unsafe_allow_html=True)

    # 4. Pro Tips with Deadpool Flavor
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
        <div class="designer-card" style="background: rgba(168,0,0,0.05) !important;">
            <h3 class="designer-header">💀 PRO TIPS FROM THE MERC</h3>
            <ul style="color: #fff; font-family: 'Oswald', sans-serif;">
                <li><b>RELOAD:</b> Put new files in the side-slot and hit 'Process' to reload your arsenal.</li>
                <li><b>EXTRACT:</b> Anki and CSV buttons are in the Cards/Quiz zones. Use 'em.</li>
                <li><b>EFFORT:</b> If the AI is slow, it's probably thinking about tacos. Give it a sec.</li>
            </ul>
            <p style="text-align: right; font-style: italic; color: var(--deadpool-red); font-family: 'Bangers', cursive; font-size: 1.5rem; margin-top: 20px;">- Deadpool Out.</p>
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
                trigger_deadpool_balloons(queued=True)
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
        st.markdown(f'<h3 class="designer-header">📚 {len(st.session_state.flashcards)} CARDS IN YOUR ARSENAL</h3>', unsafe_allow_html=True)
        
        csv_data = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button(
            label="📥 EXPORT TO ANKI (CSV)",
            data=csv_data,
            file_name="flashcards_anki.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        for i, card in enumerate(st.session_state.flashcards):
            with st.container():
                st.markdown(f"""
                <div class="designer-card" style="border-left: 12px solid var(--deadpool-red); transform: rotate({(i%2)*0.5 - 0.25}deg);">
                    <div style="position: relative; z-index: 1;">
                        <h4 class="designer-header" style="font-size: 1.5rem; margin: 0;">CARD #{i+1} — {card.get('difficulty', 'medium').upper()}</h4>
                        <p style="font-size: 1.3rem; font-weight: bold; margin: 15px 0; color: #fff; line-height: 1.4;">Q: {card['question']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("👀 REVEAL CLASSIFIED INTEL (ANSWER)"):
                    st.markdown(f"""
                    <div style="padding: 1.5rem; background: #111; border: 3px dashed var(--deadpool-red); box-shadow: 5px 5px 0px #000;">
                        <p style="font-size: 1.2rem; color: #fff; font-family: 'Oswald', sans-serif;">{card['answer']}</p>
                    </div>
                    """, unsafe_allow_html=True)
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
                    trigger_deadpool_balloons(queued=True)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display quiz
    if st.session_state.quizzes:
        st.markdown(f'<h3 class="designer-header">📋 {len(st.session_state.quizzes)} CHALLENGES STANDING BETWEEN YOU AND VICTORY</h3>', unsafe_allow_html=True)
        
        csv_data = st.session_state.agent_controller.quiz_agent.export_to_csv(st.session_state.quizzes)
        st.download_button(label="📥 DOWNLOAD MISSION DEBRIEF (CSV)", data=csv_data, file_name="quiz_questions.csv", mime="text/csv", use_container_width=True)
        
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"""
            <div class="designer-card" style="margin-bottom: 0px; border-bottom: none; transform: rotate({(i%2)*-0.3}deg);">
                <h4 class="designer-header" style="font-size: 1.5rem; margin: 0;">QUESTION #{i+1}</h4>
                <p style="font-size: 1.2rem; font-weight: bold; margin-top: 15px; color: #fff; line-height: 1.4;">{q['question']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Options in a sub-container
            st.markdown('<div class="designer-card" style="margin-top: 0px; border-top: 2px dashed var(--deadpool-red); background: #080808 !important; padding: 1rem !important;">', unsafe_allow_html=True)
            selected = st.radio(
                f"Options for Q{i+1}:",
                q['options'],
                key=f"quiz_q{i}",
                label_visibility="collapsed"
            )
            st.session_state.quiz_answers[i] = q['options'].index(selected) if selected in q['options'] else -1
            st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("✅ SUBMIT MISSION INTEL", type="primary", use_container_width=True):
            q_result = st.session_state.agent_controller.evaluate_quiz(st.session_state.quizzes, st.session_state.quiz_answers)
            st.session_state.quiz_result = q_result
            
            st.markdown("""
            <div class="designer-card" style="text-align: center; border-width: 6px;">
                <h1 class="designer-header" style="font-size: 3rem; border: none; margin: 0;">📊 MISSION RESULTS</h1>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1: 
                st.markdown(f"""
                <div class="designer-card" style="text-align: center;">
                    <h4 class="designer-header" style="font-size: 1.5rem;">SCORE</h4>
                    <h1 style="font-size: 4rem; color: #28a745; margin: 0;">{q_result['score']}/{q_result['total']}</h1>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                accuracy = (q_result['score']/q_result['total']) * 100
                st.markdown(f"""
                <div class="designer-card" style="text-align: center;">
                    <h4 class="designer-header" style="font-size: 1.5rem;">ACCURACY</h4>
                    <h1 style="font-size: 4rem; color: #fff; margin: 0;">{accuracy:.1f}%</h1>
                </div>
                """, unsafe_allow_html=True)
            
            if accuracy >= 50:
                st.success("🔥 MAXIMUM EFFORT! YOU'RE NOT AS DUMB AS YOU LOOK!")
                trigger_deadpool_balloons(queued=True)
                st.rerun()
            else:
                st.error("💀 PATHETIC. MY CHIMICHANGA HAS MORE BRAIN CELLS THAN YOU. TRY AGAIN!")
            
            with st.expander("📝 REVIEW MISSION ERRORS"):
                for i, q in enumerate(st.session_state.quizzes):
                    ans_idx = st.session_state.quiz_answers.get(i, -1)
                    correct_idx = q['correct_option']
                    is_correct = ans_idx == correct_idx
                    
                    color = "#28a745" if is_correct else "#A80000"
                    correct_intel_html = f"<p style='color: #28a745;'>Correct Intel: {q['options'][correct_idx]}</p>" if not is_correct else ""
                    st.markdown(f"""
                    <div style="background: #111; padding: 1.5rem; border-left: 8px solid {color}; margin-bottom: 15px; border-radius: 0px;">
                        <p style="color: #fff; font-weight: bold;">Q{i+1}: {q['question']}</p>
                        <p style="color: {'#28a745' if is_correct else '#ffc107'};">Your Intel: {q['options'][ans_idx] if ans_idx != -1 else 'N/A'}</p>
                        {correct_intel_html}
                        <p style="color: #aaa; font-style: italic; margin-top: 10px;">{q['explanation']}</p>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("Click 'INITIATE QUIZ' to create a quiz from your arsenal!")

def show_planner_page():
    """Revision planner page with Designer Comic Style"""
    st.markdown('<h1 class="designer-header" style="font-size: 3.5rem;">📅 STRATEGIC BATTLE PLAN</h1>', unsafe_allow_html=True)
    
    if not st.session_state.documents_processed:
        st.markdown("""
        <div class="designer-card">
            <h2 class="designer-header">⚠️ NO INTEL FOUND</h2>
            <p style="font-size: 1.2rem; color: #fff;">Upload some documents and hit 'PROCESS' first, rookie! I can't plan your world domination without data.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Initialize planner-specific study state
    if 'planner_study_mode' not in st.session_state:
        st.session_state.planner_study_mode = None
    if 'planner_study_topic' not in st.session_state:
        st.session_state.planner_study_topic = None
    
    with st.container():
        st.markdown('<div class="designer-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="designer-header">MISSION TIMELINE CONFIG</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            exam_date = st.date_input("MISSION DEADLINE (EXAM DATE)", value=None)
        with col2:
            study_days = st.slider("TRAINING INTENSITY (DAYS/WEEK)", 3, 7, 5)
        
        if st.button("📅 INITIATE STRATEGIC BATTLE PLAN", type="primary", use_container_width=True):
            processing_msg = st.info("Calculating optimal learning trajectories... trying not to get distracted by tacos...")
            plan = st.session_state.agent_controller.create_revision_plan(
                exam_date.strftime('%Y-%m-%d') if exam_date else None,
                study_days
            )
            processing_msg.empty()
            trigger_deadpool_balloons(queued=True)
            st.success(f"✅ Strategic Battle Plan ready with {len(plan)} targets identified!")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Load and display plan
    try:
        st.session_state.agent_controller.planner_agent.load_plan()
        plan = st.session_state.agent_controller.planner_agent.revision_plan
        
        if plan:
            st.markdown(f'<h3 class="designer-header">📋 TARGET LIST ({len(plan)} MISSION ITEMS)</h3>', unsafe_allow_html=True)
            
            stats = st.session_state.agent_controller.planner_agent.get_statistics()
            c1, c2, c3, c4 = st.columns(4)
            
            with c1: 
                st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">TOTAL</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff;">{stats["total_topics"]}</p></div>', unsafe_allow_html=True)
            with c2: 
                st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">DONE</h4><p style="font-size: 2rem; font-family: Bangers; color: #28a745;">{stats["completed"]}</p></div>', unsafe_allow_html=True)
            with c3: 
                st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">PENDING</h4><p style="font-size: 2rem; font-family: Bangers; color: var(--deadpool-red);">{stats["pending"]}</p></div>', unsafe_allow_html=True)
            with c4: 
                st.markdown(f'<div class="designer-card" style="text-align: center; padding: 1rem !important;"><h4 class="designer-header" style="font-size: 1rem;">WIN RATE</h4><p style="font-size: 2rem; font-family: Bangers; color: #fff;">{stats["completion_rate"]:.1f}%</p></div>', unsafe_allow_html=True)
            
            upcoming = st.session_state.agent_controller.planner_agent.get_upcoming_revisions(14)
            if upcoming:
                st.markdown("<br>", unsafe_allow_html=True)
                for i, item in enumerate(upcoming):
                    item_topic = item['topic']
                    item_date = item['date']
                    status = item['status']
                    
                    status_color = "#28a745" if status == 'completed' else "#A80000" if status == 'in_progress' else "#333333"
                    status_icon = "✅" if status == 'completed' else "⚔️" if status == 'in_progress' else "📅"
                    
                    st.markdown(f"""
                    <div style="background: #000; padding: 1.2rem; border: 4px solid var(--deadpool-red); border-left: 15px solid {status_color}; margin-top: 1.5rem; box-shadow: 8px 8px 0px #000; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 class="designer-header" style="margin: 0; color: white; font-size: 1.4rem;">{status_icon} {item_date} — {item_topic}</h4>
                            <span style="background: {status_color}; color: white; padding: 0.3rem 1rem; border: 2px solid #000; font-family: 'Bangers'; font-size: 1rem;">{status.upper()}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="designer-card" style="margin-top: 0px; border-top: none; padding-top: 10px; border-width: 4px; box-shadow: 8px 8px 0px #000;">', unsafe_allow_html=True)
                    col_info, col_actions = st.columns([3, 2])
                    
                    with col_info:
                        if item.get('subtopics'):
                            st.markdown(f"<p style='color: #fff; font-size: 1.1rem;'><strong>FOCUS SECTORS:</strong> {', '.join(item['subtopics'])}</p>", unsafe_allow_html=True)
                        with st.expander("📝 VIEW MISSION INTEL POINTS"):
                            for point in item.get('key_points', []):
                                st.markdown(f"⚔️ <span style='color: #eee;'>{point}</span>", unsafe_allow_html=True)
                    
                    with col_actions:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🚧 ENGAGE", key=f"prog_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, 'in_progress')
                                st.rerun()
                        with c2:
                            if st.button("🏁 DONE", key=f"comp_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, 'completed')
                                trigger_deadpool_balloons(queued=True)
                                st.rerun()
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("📇 CARDS", key=f"study_flash_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.planner_study_mode = 'flashcards'
                                st.session_state.planner_study_topic = item_topic
                        with cc2:
                            if st.button("📝 QUIZ", key=f"study_quiz_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.planner_study_mode = 'quiz'
                                st.session_state.planner_study_topic = item_topic
                    
                    # Study Area
                    if st.session_state.planner_study_topic == item_topic:
                        st.markdown('<div style="background: #080808; padding: 1.5rem; border: 3px dashed var(--deadpool-red); margin-top: 15px; box-shadow: inset 0 0 10px rgba(168,0,0,0.3);">', unsafe_allow_html=True)
                        st.markdown(f'<h4 class="designer-header">TRAINING ZONE: {st.session_state.planner_study_mode.upper()}</h4>', unsafe_allow_html=True)
                        
                        if st.session_state.planner_study_mode == 'flashcards':
                            cards = st.session_state.agent_controller.generate_flashcards(5, topic=item_topic)
                            for j, card in enumerate(cards):
                                with st.expander(f"CARD #{j+1}"):
                                    st.markdown(f"<p style='color:#fff;'><strong>Q:</strong> {card['question']}</p><hr style='border-color:#444;'><p style='color:#fff;'><strong>A:</strong> {card['answer']}</p>", unsafe_allow_html=True)
                        else:
                            questions = st.session_state.agent_controller.generate_quiz('medium', 3, topic=item_topic)
                            for j, q in enumerate(questions):
                                st.markdown(f"<p style='color:#fff; font-weight:bold;'>Q{j+1}: {q['question']}</p>", unsafe_allow_html=True)
                                sel = st.radio(f"Select answer for Q{j+1}:", q['options'], key=f"plan_quiz_{item_topic}_{j}", label_visibility="collapsed")
                                if st.button(f"VERIFY INTEL Q{j+1}", key=f"plan_quiz_btn_{item_topic}_{j}"):
                                    if q['options'].index(sel) == q['correct_option']:
                                        st.success("✅ BULLSEYE!")
                                    else:
                                        st.error(f"❌ MISSED! Correct Intel: {q['options'][q['correct_option']]}")
                                    st.info(f"ℹ️ {q['explanation']}")
                        
                        if st.button("❌ CLOSE TRAINING ZONE", key=f"close_study_{item_date}_{item_topic}"):
                            st.session_state.planner_study_mode = None
                            st.session_state.planner_study_topic = None
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
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
        st.markdown('<div class="designer-card" style="border-width: 6px;">', unsafe_allow_html=True)
        q_input = st.text_input("💭 INTERROGATE THE SYSTEM (ASK ANYTHING):", placeholder="e.g., Explain the primary directives of the mission...")
        if st.button("🔍 INITIATE INTERROGATION", type="primary", use_container_width=True):
            if q_input:
                with st.spinner("Searching through the sematic archives... stay frosty..."):
                    res = st.session_state.agent_controller.answer_question(q_input, st.session_state.latest_document)
                    st.session_state.chat_history.append({'question': q_input, 'answer': res['answer'], 'sources': res.get('sources', [])})
                    st.rerun()
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
