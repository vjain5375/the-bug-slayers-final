"""
AI Study Assistant - Multi-Agent System
Personalized study assistant with flashcards, quizzes, and revision planning
"""

import streamlit as st
import os
import logging
import hashlib
import traceback
from pathlib import Path
from dotenv import load_dotenv
from vector_store import VectorStore
from agents.controller import AgentController
from utils import ensure_documents_directory, get_document_files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env file
def load_api_key():
    """Load API key from .env file or Streamlit secrets"""
    api_key = None
    
    # Try Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and st.secrets:
            api_key = st.secrets.get("GOOGLE_API_KEY") or st.secrets.get("OPENAI_API_KEY")
            if api_key:
                os.environ['GOOGLE_API_KEY'] = api_key
                return api_key
    except Exception:
        pass
    
    # Try environment variables
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # Try .env file
    possible_paths = [
        Path(__file__).parent / '.env',
        Path('.env'),
        Path.cwd() / '.env',
    ]
    
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
            if api_key:
                break
    
    # Read directly from file
    if not api_key:
        for env_path in possible_paths:
            if env_path.exists():
                try:
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line_clean = line.strip()
                            if line_clean and '=' in line_clean:
                                if 'GOOGLE_API_KEY' in line_clean:
                                    api_key = line_clean.split('=', 1)[1].strip()
                                    api_key = api_key.strip('"').strip("'")
                                    os.environ['GOOGLE_API_KEY'] = api_key
                                    break
                                elif 'OPENAI_API_KEY' in line_clean:
                                    api_key = line_clean.split('=', 1)[1].strip()
                                    api_key = api_key.strip('"').strip("'")
                                    os.environ['OPENAI_API_KEY'] = api_key
                                    break
                        if api_key:
                            break
                except Exception:
                    continue
    
    return api_key

# Page configuration
st.set_page_config(
    page_title="AI Study Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load API key
load_api_key()

# Initialize session state
if 'session_initialized' not in st.session_state:
    # Clear documents on new session/refresh
    st.session_state.session_initialized = True
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    for doc_path in doc_files:
        try:
            Path(doc_path).unlink()
        except Exception:
            pass
    # Clear vector store (only if it can be initialized)
    try:
        temp_vs = VectorStore()
        temp_vs.clear_collection()
    except Exception as e:
        logger.warning(f"Could not clear vector store on session init: {e}")
        pass
    st.session_state.documents_processed = False
    st.session_state.uploaded_files_shared = None
    st.session_state.latest_document = None
    st.session_state.document_upload_order = []  # Track upload order
    st.session_state.num_flashcards = 10  # Reset to default
    st.session_state.num_questions = 10  # Reset to default

if 'agent_controller' not in st.session_state:
    st.session_state.agent_controller = None
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"
if 'flashcards' not in st.session_state:
    st.session_state.flashcards = []
if 'quizzes' not in st.session_state:
    st.session_state.quizzes = []
if 'quiz_answers' not in st.session_state:
    st.session_state.quiz_answers = {}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'uploaded_files_shared' not in st.session_state:
    st.session_state.uploaded_files_shared = None
if 'latest_document' not in st.session_state:
    st.session_state.latest_document = None
if 'document_upload_order' not in st.session_state:
    st.session_state.document_upload_order = []
if 'num_flashcards' not in st.session_state:
    st.session_state.num_flashcards = 10
if 'num_questions' not in st.session_state:
    st.session_state.num_questions = 10
if 'last_processed_signature' not in st.session_state:
    st.session_state.last_processed_signature = None

# Load CSS (Premium Deadpool Comic Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@400;700&display=swap');

    :root {
        --deadpool-red: #A80000;
        --deadpool-black: #000000;
        --deadpool-dark-red: #700000;
        --comic-white: #FFFFFF;
        --comic-border: 4px solid #000000;
    }

    /* Global Overrides */
    .stApp {
        background-color: var(--deadpool-black);
        color: var(--comic-white);
        font-family: 'Oswald', sans-serif;
    }

    /* Comic Grid Background */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-image: 
            linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)),
            url('https://www.transparenttextures.com/patterns/carbon-fibre.png');
        background-attachment: fixed;
        z-index: -1;
    }

    /* Header Styling */
    header[data-testid="stHeader"] {
        background-color: var(--deadpool-red) !important;
        border-bottom: 5px solid #000 !important;
        height: 60px !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #000 !important;
        border-right: 5px solid var(--deadpool-red) !important;
    }

    /* Uniform Comic Buttons */
    .stButton > button {
        font-family: 'Bangers', cursive !important;
        background-color: var(--deadpool-red) !important;
        color: white !important;
        font-size: 1.2rem !important;
        border: 4px solid #000 !important;
        border-radius: 0px !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 4px 4px 0px #000 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        width: 100% !important;
        min-height: 60px !important;
        height: 60px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1 !important;
        margin-bottom: 5px !important;
    }

    /* Navigation Buttons Specific Style - Uniform Icon and Text */
    [data-testid="stHorizontalBlock"] div div div .stButton > button {
        height: 100px !important; 
        font-size: 0.95rem !important;
        flex-direction: column !important;
        line-height: 1.1 !important;
        gap: 5px !important;
        padding: 5px !important;
    }

    /* Prevent text wrapping in navigation buttons */
    [data-testid="stHorizontalBlock"] div div div .stButton > button div p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .stButton > button:hover {
        background-color: var(--deadpool-dark-red) !important;
        transform: translate(-2px, -2px) !important;
        box-shadow: 6px 6px 0px #000 !important;
    }

    /* Primary Actions */
    .stButton > button[kind="primary"] {
        background-color: var(--deadpool-red) !important;
        border-color: #000 !important;
        color: #fff !important;
    }
    
    .stButton > button[kind="secondary"] {
        background-color: #333 !important;
        border-color: #000 !important;
        color: #fff !important;
    }

    /* Comic Panels (Cards) */
    .stVerticalBlock > div > div {
        background: #000 !important;
        border: 4px solid var(--deadpool-red) !important;
        border-radius: 0px !important;
        padding: 1.5rem !important;
        box-shadow: 8px 8px 0px #000 !important;
        margin-bottom: 1rem !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #000 !important;
        border: 3px solid var(--deadpool-red) !important;
        padding: 1rem !important;
        box-shadow: 5px 5px 0px #000 !important;
    }

    [data-testid="stMetricLabel"] {
        color: var(--deadpool-red) !important;
        font-family: 'Bangers', cursive !important;
        font-size: 1.2rem !important;
    }

    [data-testid="stMetricValue"] {
        color: #fff !important;
        font-family: 'Bangers', cursive !important;
        font-size: 2.5rem !important;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stFileUploader {
        background-color: #111 !important;
        border: 3px solid var(--deadpool-red) !important;
        color: #fff !important;
        font-size: 1rem !important;
        border-radius: 0px !important;
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

    /* Remove transitions and animations globally */
    *, *::before, *::after {
        transition: none !important;
        animation: none !important;
    }
    
    /* Better spacing for main content */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 1200px !important;
    }
    
    /* Remove streamlit padding */
    .st-emotion-cache-1y4p8pa { padding-top: 0px !important; }
    div[data-testid="stVerticalBlock"] > div:has(div.element-container) { margin-bottom: 0px !important; }
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
        except Exception as e:
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
            
            # Set a dummy object to prevent crashes in UI
            st.session_state.vector_store = None
            st.stop()
    
    if st.session_state.agent_controller is None:
        # Show static loading message
        loading_msg = st.info("Initializing AI agents...")
        if not api_key:
            loading_msg.empty()
            st.error("⚠️ API key not found! Please check your .env file.")
            st.stop()
        try:
            st.session_state.agent_controller = AgentController(st.session_state.vector_store)
            loading_msg.empty()
        except Exception as e:
            loading_msg.empty()
            logger.exception("AgentController init failed: %s", e)
            st.error(f"⚠️ Failed to initialize AI agents: {e}")
            st.stop()

def _compute_docs_signature(doc_files):
    """Create a quick signature of documents based on name, size, and mtime"""
    entries = []
    for doc in doc_files:
        p = Path(doc)
        if p.exists():
            stat = p.stat()
            entries.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
    if not entries:
        return ""
    entries.sort()
    return hashlib.md5("|".join(entries).encode()).hexdigest()

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
    processing_msg.empty()
    
    if result['total_chunks'] > 0:
        st.session_state.documents_processed = True
        latest_info = f" (Latest: {st.session_state.latest_document})" if st.session_state.latest_document else ""
        st.success(f"✅ Processed {result['total_chunks']} chunks from {result['total_topics']} topics!{latest_info}")
        
        # Store processing results for display
        st.session_state.processing_results = result
        st.session_state.last_processed_signature = signature
        st.session_state.last_index_count = result.get('total_chunks', 0)
        
        return True
    else:
        st.error("No content could be extracted from documents.")
        return False

def main():
    """Main application"""
    # Deadpool Branding Header - NOW AT THE VERY TOP
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem; margin-top: -3rem;">
        <h1 style="font-family: 'Bangers', cursive; font-size: 4rem; color: var(--deadpool-red); text-shadow: 4px 4px 0px #000; margin: 0;">⚡ DEADPOOL'S STUDY HUB</h1>
        <div style="background: var(--deadpool-red); height: 6px; width: 200px; margin: 0.5rem auto; border: 3px solid #000; box-shadow: 3px 3px 0px #000;"></div>
        <p style="font-family: 'Bangers', cursive; font-size: 1.4rem; color: #fff; letter-spacing: 1px; margin-top: 5px;">WEAPONIZING YOUR DOCUMENTS FOR MAXIMUM LEARNING EFFORT!</p>
    </div>
    """, unsafe_allow_html=True)

    initialize_components()
    
    # Sidebar - Navigation and Document Management
    with st.sidebar:
        # MISSION PROTOCOL FLOWCHART - Top of Sidebar
        st.markdown("""
        <div style="background: #000; padding: 1rem; border: 3px solid var(--deadpool-red); margin-bottom: 1.5rem; box-shadow: 6px 6px 0px #000; border-radius: 0px;">
            <h2 style="color: var(--deadpool-red); margin: 0 0 1rem 0; font-size: 1.6rem; border: none; text-align: center; font-family: 'Bangers'; text-shadow: 2px 2px 0px #000;">⚔️ MISSION FLOW</h2>
            <div style="padding-left: 5px;">
                <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                    <div style="background: var(--deadpool-red); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #000; font-family: 'Bangers';">1</div>
                    <div style="margin-left: 12px; font-size: 1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">📤 UPLOAD DOCS</div>
                </div>
                <div style="border-left: 3px solid var(--deadpool-red); height: 15px; margin-left: 12px; margin-top: -5px; margin-bottom: -5px;"></div>
                <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                    <div style="background: var(--deadpool-red); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #000; font-family: 'Bangers';">2</div>
                    <div style="margin-left: 12px; font-size: 1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">💾 HIT SAVE</div>
                </div>
                <div style="border-left: 3px solid var(--deadpool-red); height: 15px; margin-left: 12px; margin-top: -5px; margin-bottom: -5px;"></div>
                <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                    <div style="background: var(--deadpool-red); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #000; font-family: 'Bangers';">3</div>
                    <div style="margin-left: 12px; font-size: 1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">🔄 PROCESS NOW</div>
                </div>
                <div style="border-left: 3px solid var(--deadpool-red); height: 15px; margin-left: 12px; margin-top: -5px; margin-bottom: -5px;"></div>
                <div style="display: flex; align-items: center;">
                    <div style="background: var(--deadpool-red); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #000; font-family: 'Bangers';">4</div>
                    <div style="margin-left: 12px; font-size: 1rem; font-weight: bold; color: #fff; font-family: 'Bangers'; letter-spacing: 1px;">🛡️ DOMINATE</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # NAVIGATION SECTION
        st.markdown("""
        <div style="background: #000; padding: 0.5rem; border: 2px solid var(--deadpool-red); margin-bottom: 0.5rem; text-align: center; box-shadow: 3px 3px 0px #000;">
            <p style="color: white; margin: 0; font-size: 1.1rem; font-family: 'Bangers'; letter-spacing: 1px;">🎯 DESTINATIONS</p>
        </div>
        """, unsafe_allow_html=True)

        nav_options = {
            "Home": "🏠",
            "Flashcards": "📇",
            "Quizzes": "📝",
            "Revision Planner": "📅",
            "Chat Assistant": "💬",
            "Analytics": "📊"
        }
        
        current_index = 0
        if st.session_state.current_page in nav_options:
            current_index = list(nav_options.keys()).index(st.session_state.current_page)
        
        page = st.radio(
            "Select Page",
            list(nav_options.keys()),
            format_func=lambda x: f"{nav_options[x]} {x}",
            index=current_index,
            label_visibility="collapsed",
            key="sidebar_nav_radio"
        )
        
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()

        st.divider()
        
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
                if st.button("💾 Save", use_container_width=True, key="sidebar_save"):
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
                if st.button("🔄 Process", use_container_width=True, type="primary", key="sidebar_process"):
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
        
        doc_files = get_document_files()
        if doc_files:
            st.info(f"📁 {len(doc_files)} document(s) ready")
        
        if st.button("🔄 Process Documents", use_container_width=True, type="primary"):
            if process_documents():
                # Show summary in sidebar
                if 'processing_results' in st.session_state:
                    result = st.session_state.processing_results
                    st.success(f"✅ {result['total_chunks']} chunks, {result['total_topics']} topics extracted!")
        
        if st.session_state.vector_store:
            count = st.session_state.vector_store.get_collection_count()
            st.metric("Indexed Chunks", count)
        
        st.divider()
    
    # Upload Section in Main Dashboard - Moved Above Navigation
    st.markdown("### 📤 UPLOAD MATERIALS")
    st.markdown("""
    <div style="background: #000; padding: 1.5rem; border: 4px solid var(--deadpool-red); margin: 0.5rem 0; text-align: center; box-shadow: 6px 6px 0px #000;">
        <h2 style="color: white; margin: 0 0 0.5rem 0; font-size: 1.8rem; border: none;">📤 UPLOAD YOUR STUDY MATERIALS</h2>
        <p style="color: #fff; margin: 0; font-size: 1rem;">Upload PDF, DOCX, or TXT files to get started</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Upload area in main section - Synced with sidebar
    if 'uploaded_files_shared' not in st.session_state:
        st.session_state.uploaded_files_shared = None
    
    col1, col2 = st.columns([2, 1])
    with col1:
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
    with col2:
        if uploaded_files_main:
            st.success(f"✅ {len(uploaded_files_main)} file(s) selected")
        elif st.session_state.uploaded_files_shared:
            st.info(f"📁 {len(st.session_state.uploaded_files_shared)} file(s) from sidebar")
    
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
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"📄 **{doc_name}**")
                with col2:
                    if st.button("🗑️", key=f"delete_{doc_name}", help=f"Delete {doc_name}"):
                        try:
                            Path(doc).unlink()
                            st.success(f"Deleted {doc_name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
    
    st.divider()
    
    # Navigation Buttons - Below Upload Section
    st.markdown("### 🎯 NAVIGATION")
    nav_options = {
        "Home": "🏠",
        "Flashcards": "📇",
        "Quizzes": "📝",
        "Revision Planner": "📅",
        "Chat Assistant": "💬",
        "Analytics": "📊"
    }
    
    # Create navigation buttons in a grid - Always visible
    nav_cols = st.columns(6)
    for idx, (page_name, icon) in enumerate(nav_options.items()):
        with nav_cols[idx]:
            button_type = "primary" if st.session_state.current_page == page_name else "secondary"
            # Format text: Icon and Name on separate lines, but don't split words
            button_label = f"{icon}\n{page_name}"
            nav_button = st.button(button_label, use_container_width=True, key=f"main_nav_{page_name}", type=button_type)
            if nav_button:
                st.session_state.current_page = page_name
                st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
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
    """Deadpool-themed Home page with high-impact visuals"""
    
    # Hero Section with Deadpool Action Grid Style - RED/BLACK/WHITE
    st.markdown("""
    <div style="background: url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg') center/cover; padding: 4rem 1rem; border: 6px solid #000; box-shadow: 10px 10px 0px var(--deadpool-red); text-align: center; margin-bottom: 2rem; position: relative;">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65);"></div>
        <div style="position: relative; z-index: 2;">
            <h1 style="font-family: 'Bangers', cursive; color: var(--deadpool-red); font-size: 3rem; text-shadow: 4px 4px 0px #000; margin: 0;">Turn Your Docs into Weaponized Knowledge!</h1>
            <p style="font-family: 'Bangers', cursive; color: #fff; font-size: 1.4rem; background: #000; display: inline-block; padding: 0.3rem 1.5rem; transform: skew(-10deg); margin-top: 1rem; border: 2px solid var(--deadpool-red);">Upload, Analyze, Conquer with Flashcards, Quizzes & Smart Planners.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # CASE 1: NEW USER EXPERIENCE (High-Impact Onboarding)
    if not st.session_state.documents_processed:
        st.markdown("<h2 style='text-align: center;'>⚔️ MISSION OBJECTIVES</h2>", unsafe_allow_html=True)
        
        # Journey Cards with Comic Borders
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            <div style="background: #000; padding: 1.5rem; border: 4px solid var(--deadpool-red); box-shadow: 6px 6px 0px #000; margin-bottom: 1rem;">
                <h3 style="font-size: 1.8rem; border: none;">1️⃣ LOAD UP</h3>
                <p style="color: #fff; font-size: 1.1rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Drop your PDFs, DOCX, or Text notes into the feed.</p>
            </div>
            <div style="background: #000; padding: 1.5rem; border: 4px solid var(--deadpool-red); box-shadow: 6px 6px 0px #000; margin-bottom: 1rem;">
                <h3 style="font-size: 1.8rem; border: none;">3️⃣ EXTRACT</h3>
                <p style="color: #fff; font-size: 1.1rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'PROCESS'</b>. My agents will slice and dice your text into pure semantic gold.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div style="background: #000; padding: 1.5rem; border: 4px solid var(--deadpool-red); box-shadow: 6px 6px 0px #000; margin-bottom: 1rem;">
                <h3 style="font-size: 1.8rem; border: none;">2️⃣ LOCK & LOAD</h3>
                <p style="color: #fff; font-size: 1.1rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'SAVE'</b> to commit those files to my infinite memory banks.</p>
            </div>
            <div style="background: #000; padding: 1.5rem; border: 4px solid var(--deadpool-red); box-shadow: 6px 6px 0px #000; margin-bottom: 1rem;">
                <h3 style="font-size: 1.8rem; border: none;">4️⃣ DOMINATE</h3>
                <p style="color: #fff; font-size: 1.1rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Maximum Effort! 💥 Flashcards, Quizzes, and Chat are now ready.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # Add the thumbs up Deadpool image
        st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", width=300)
        
        return

    # CASE 2: RETURNING USER (Pro Dashboard)
    st.markdown("<h2>⚡ COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    # 1. High-Impact Quick Access - ALREADY UNIFORM VIA CSS
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
        st.markdown("<h3 style='color: #fff;'>📊 MISSION INTEL</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("TOPICS", stats['total_topics'])
        with c2: st.metric("FLASHCARDS", stats['total_flashcards'])
        with c3: st.metric("QUIZZES", stats['total_quizzes'])
        with c4: st.metric("CONQUERED", f"{stats['revision_stats']['completion_rate']:.1f}%")

    st.divider()

    # 3. Content Intelligence
    if 'processing_results' in st.session_state:
        result = st.session_state.processing_results
        col_topics, col_samples = st.columns([2, 1])
        
        with col_topics:
            if result.get('topics'):
                st.markdown("<h3>📚 WEAPONIZED TOPICS</h3>", unsafe_allow_html=True)
                for idx, topic_data in enumerate(result['topics'][:5], 1):
                    with st.expander(f"🔴 {topic_data.get('topic', 'Topic').upper()}", expanded=(idx == 1)):
                        if topic_data.get('key_points'):
                            for p in topic_data['key_points'][:3]: st.markdown(f"⚔️ {p}")
        
        with col_samples:
            st.markdown("<h3 style='color: #fff;'>📄 INTEL SNAPS</h3>", unsafe_allow_html=True)
            if result.get('chunks'):
                for chunk in result['chunks'][:2]:
                    st.markdown(f"""
                    <div style="background: #111; padding: 1rem; border: 2px solid var(--deadpool-red); border-radius: 0px; font-size: 0.9rem; margin-bottom: 0.5rem; color: #eee; font-style: italic; box-shadow: 4px 4px 0px #000;">
                        "{chunk['text'][:120]}..."
                    </div>
                    """, unsafe_allow_html=True)

    # Thumbs up Deadpool at the bottom for returning users too
    st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", width=250)

    # 4. Deadpool Footer EXPANDER
    with st.expander("💀 THE CHIMICHANGA MANUAL (HELP)", expanded=False):
        st.markdown("""
        <div style="padding: 1.5rem; background: #000; border: 4px solid var(--deadpool-red); border-radius: 0px; box-shadow: 8px 8px 0px #000;">
            <h4 style="font-family: 'Bangers', cursive; color: var(--deadpool-red); font-size: 2rem; margin-top: 0;">DON'T BE A DEGENERATE:</h4>
            <ul style="color: #fff; font-size: 1.1rem; font-family: 'Oswald', sans-serif;">
                <li><b>RELOAD:</b> Put new files in the side-slot and hit 'Process' to reload your arsenal.</li>
                <li><b>EXTRACT:</b> Anki and CSV buttons are in the Cards/Quiz zones. Use 'em.</li>
                <li><b>EFFORT:</b> If the AI is slow, it's probably thinking about tacos. Give it a sec.</li>
            </ul>
            <p style="text-align: right; font-style: italic; color: var(--deadpool-red); font-family: 'Bangers', cursive; font-size: 1.2rem;">- Deadpool Out.</p>
        </div>
        """, unsafe_allow_html=True)

def show_flashcards_page():
    """Flashcards page"""
    st.markdown("### 📇 Flashcards")
    
    if not st.session_state.documents_processed:
        st.warning("Please process documents first!")
        return
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        num_flashcards = st.slider("Number of flashcards", 5, 30, value=st.session_state.num_flashcards, key="flashcard_slider")
    with col2:
        difficulty_mix_label = st.selectbox(
            "Difficulty mix",
            [
                "Easy + Medium",
                "Medium + Hard",
                "Easy + Medium + Hard"
            ],
            index=2,
            help="Choose how difficulties are distributed across the generated flashcards."
        )
        mix_map = {
            "Easy + Medium": "easy_medium",
            "Medium + Hard": "medium_hard",
            "Easy + Medium + Hard": "easy_medium_hard",
        }
        difficulty_mix = mix_map.get(difficulty_mix_label, "easy_medium_hard")
    with col3:
        if st.button("🔄 Generate Flashcards", use_container_width=True, type="primary"):
            # Show static processing message
            processing_msg = st.info("Processing... Generating flashcards...")
            flashcards = st.session_state.agent_controller.generate_flashcards(
                num_flashcards,
                difficulty_mix=difficulty_mix
            )
            processing_msg.empty()
            st.session_state.flashcards = flashcards
            st.session_state.num_flashcards = 10  # Reset to default
            st.success(f"✅ Generated {len(flashcards)} flashcards!")
            st.rerun()
    
    # Load existing flashcards
    if not st.session_state.flashcards:
        try:
            flashcards = st.session_state.agent_controller.flashcard_agent.load_flashcards()
            st.session_state.flashcards = flashcards
        except:
            pass
    
    # Display flashcards
    if st.session_state.flashcards:
        st.markdown(f"### 📚 {len(st.session_state.flashcards)} Flashcards")
        
        # Add Export Button
        csv_data = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button(
            label="📥 Export to Anki (CSV)",
            data=csv_data,
            file_name="flashcards_anki.csv",
            mime="text/csv",
            help="Download flashcards in a format compatible with Anki import"
        )
        
        for i, card in enumerate(st.session_state.flashcards):
            with st.expander(f"Card {i+1}: {card.get('topic', 'General')} - {card.get('difficulty', 'medium').upper()}"):
                st.markdown(f"**Q:** {card['question']}")
                st.markdown(f"**A:** {card['answer']}")
    else:
        st.info("Click 'Generate Flashcards' to create flashcards from your study materials!")

def show_quizzes_page():
    """Quizzes page"""
    st.markdown("### 📝 Quizzes")
    
    if not st.session_state.documents_processed:
        st.warning("Please process documents first!")
        return
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"], index=1)
    with col2:
        # Allow a wider range of questions while still using session state default
        num_questions = st.slider(
            "Questions",
            min_value=3,
            max_value=30,
            value=st.session_state.num_questions,
            key="quiz_slider",
        )
    with col3:
        adaptive = st.checkbox("Adaptive", value=True)
        if st.button("🎯 Generate Quiz", use_container_width=True, type="primary"):
            # Show static processing message
            processing_msg = st.info("Processing... Generating quiz...")
            questions = st.session_state.agent_controller.generate_quiz(
                difficulty, num_questions, adaptive
            )
            processing_msg.empty()
            if not questions:
                st.error("No quiz could be generated. Please ensure documents are processed and contain enough text.")
            else:
                st.session_state.quizzes = questions
                st.session_state.quiz_answers = {}
                st.session_state.num_questions = 10  # Reset to default
                st.success(f"✅ Generated {len(questions)} questions!")
                st.rerun()
    
    # Display quiz
    if st.session_state.quizzes:
        st.markdown(f"### 📋 Quiz ({len(st.session_state.quizzes)} questions)")
        
        # Add Export Button
        csv_data = st.session_state.agent_controller.quiz_agent.export_to_csv(st.session_state.quizzes)
        st.download_button(
            label="📥 Export Quiz to CSV",
            data=csv_data,
            file_name="quiz_questions.csv",
            mime="text/csv",
            help="Download quiz questions and answers as a CSV file"
        )
        
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"**Q{i+1}:** {q['question']}")
            selected = st.radio(
                "Options:",
                q['options'],
                key=f"quiz_q{i}",
                label_visibility="collapsed"
            )
            st.session_state.quiz_answers[i] = q['options'].index(selected) if selected in q['options'] else -1
        
        if st.button("✅ Submit Quiz", type="primary", use_container_width=True):
            result = st.session_state.agent_controller.evaluate_quiz(
                st.session_state.quizzes,
                st.session_state.quiz_answers
            )
            st.session_state.quiz_result = result
            
            st.markdown("### 📊 Results")
            st.metric("Score", f"{result['score']}/{result['total']}")
            st.metric("Accuracy", f"{result['accuracy']*100:.1f}%")
            
            with st.expander("View Details"):
                for detail in result['details']:
                    is_correct = detail['is_correct']
                    icon = "✅" if is_correct else "❌"
                    st.markdown(f"{icon} **Q{detail['question_index']+1}**")
                    st.markdown(f"Your answer: {detail.get('user_answer', 'Not answered')}")
                    st.markdown(f"Correct answer: {detail.get('correct_answer', '')}")
                    if detail.get('explanation'):
                        st.info(detail['explanation'])
    else:
        st.info("Click 'Generate Quiz' to create a quiz from your study materials!")

def show_planner_page():
    """Revision planner page"""
    st.markdown("### 📅 Revision Planner")
    
    if not st.session_state.documents_processed:
        st.warning("Please process documents first!")
        return
    
    # Initialize planner-specific study state
    if 'planner_study_mode' not in st.session_state:
        st.session_state.planner_study_mode = None  # None, 'flashcards', 'quiz'
    if 'planner_study_topic' not in st.session_state:
        st.session_state.planner_study_topic = None
    
    col1, col2 = st.columns(2)
    with col1:
        exam_date = st.date_input("Exam Date", value=None)
    with col2:
        study_days = st.slider("Study Days/Week", 3, 7, 5)
    
    if st.button("📅 Create Revision Plan", type="primary", use_container_width=True):
        # Show static processing message
        processing_msg = st.info("Processing... Creating revision plan...")
        plan = st.session_state.agent_controller.create_revision_plan(
            exam_date.strftime('%Y-%m-%d') if exam_date else None,
            study_days
        )
        processing_msg.empty()
        st.success(f"✅ Created revision plan with {len(plan)} items!")
    
    # Load and display plan
    try:
        st.session_state.agent_controller.planner_agent.load_plan()
        plan = st.session_state.agent_controller.planner_agent.revision_plan
        
        if plan:
            st.markdown(f"### 📋 Revision Schedule ({len(plan)} items)")
            
            # Statistics
            stats = st.session_state.agent_controller.planner_agent.get_statistics()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", stats['total_topics'])
            with col2:
                st.metric("Completed", stats['completed'])
            with col3:
                st.metric("Pending", stats['pending'])
            with col4:
                st.metric("Progress", f"{stats['completion_rate']:.1f}%")
            
            # Upcoming revisions
            upcoming = st.session_state.agent_controller.planner_agent.get_upcoming_revisions(14)
            if upcoming:
                st.markdown("---")
                st.markdown("### 🗓️ Daily Focus Areas")
                
                for item in upcoming:
                    item_topic = item['topic']
                    item_date = item['date']
                    
                    # Study Area Logic - If this topic is being studied, show it here
                    is_studying = (st.session_state.planner_study_topic == item_topic and 
                                  st.session_state.planner_study_mode is not None)
                    
                    # Card Header
                    status = item['status']
                    status_color = "#28a745" if status == 'completed' else "#A80000" if status == 'in_progress' else "#333333"
                    status_icon = "✅" if status == 'completed' else "⚔️" if status == 'in_progress' else "📅"
                    
                    st.markdown(f"""
                    <div style="background: #000; padding: 1.2rem; border: 3px solid var(--deadpool-red); border-left: 10px solid {status_color}; margin-top: 1rem; box-shadow: 4px 4px 0px #000;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 style="margin: 0; color: white;">{status_icon} {item_date} — {item_topic}</h4>
                            <span style="background: {status_color}; color: white; padding: 0.2rem 0.8rem; border-radius: 0px; font-size: 0.7rem; font-weight: 700; border: 2px solid #000;">{status.upper()}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_info, col_actions = st.columns([3, 2])
                    
                    with col_info:
                        if item.get('subtopics'):
                            st.markdown(f"<p style='margin-top:10px;'><b>Focus:</b> {', '.join(item['subtopics'])}</p>", unsafe_allow_html=True)
                        with st.expander("📝 Study Points"):
                            for point in item.get('key_points', []):
                                st.markdown(f"- {point}")
                    
                    with col_actions:
                        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🚧 Active", key=f"prog_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, 'in_progress')
                                st.rerun()
                        with c2:
                            if st.button("✅ Done", key=f"comp_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, 'completed')
                                st.rerun()
                        
                        # In-place study trigger buttons
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("📇 Flashcards", key=f"fbtn_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.planner_study_topic = item_topic
                                st.session_state.planner_study_mode = 'flashcards'
                                with st.spinner(f"Generating flashcards for {item_topic}..."):
                                    st.session_state.planner_temp_data = st.session_state.agent_controller.generate_flashcards(num_flashcards=5, topic=item_topic)
                                    if not st.session_state.planner_temp_data:
                                        st.error("Could not find content for this topic. Please try processing documents again.")
                                st.rerun()
                        with cc2:
                            if st.button("📝 Quiz", key=f"qbtn_{item_date}_{item_topic}", use_container_width=True):
                                st.session_state.planner_study_topic = item_topic
                                st.session_state.planner_study_mode = 'quiz'
                                with st.spinner(f"Generating quiz for {item_topic}..."):
                                    st.session_state.planner_temp_data = st.session_state.agent_controller.generate_quiz(difficulty="medium", num_questions=3, topic=item_topic)
                                    st.session_state.planner_quiz_answers = {}
                                    if not st.session_state.planner_temp_data:
                                        st.error("Could not find content for this topic. Please try processing documents again.")
                                st.rerun()

                    # SHOW STUDY CONTENT RIGHT HERE
                    if is_studying:
                        st.markdown(f"<div style='background: #000; padding: 1.5rem; border-radius: 0px; border: 3px solid var(--deadpool-red); margin: 1rem 0; box-shadow: 6px 6px 0px #000;'>", unsafe_allow_html=True)
                        st.markdown(f"#### 🎓 Studying: {item_topic}")
                        
                        study_data = st.session_state.get('planner_temp_data', [])
                        
                        if not study_data:
                            st.warning("⚠️ No study material found for this specific topic in the documents. Try another topic or check your documents.")
                        else:
                            if st.session_state.planner_study_mode == 'flashcards':
                                for i, card in enumerate(study_data):
                                    with st.expander(f"📇 Card {i+1}: {card.get('question', 'Q')[:60]}..."):
                                        st.markdown(f"**Q:** {card.get('question', 'No question')}")
                                        st.markdown(f"**A:** {card.get('answer', 'No answer')}")
                            
                            elif st.session_state.planner_study_mode == 'quiz':
                                questions = study_data
                                for i, q in enumerate(questions):
                                    st.markdown(f"**Q{i+1}:** {q.get('question', 'Question')}")
                                    options = q.get('options', ["Option A", "Option B", "Option C", "Option D"])
                                    # Use a safer key and ensure unique
                                    selected = st.radio(f"Select answer for Q{i+1}:", options, key=f"pquiz_q{i}_{item_topic[:10]}_{item_date}", label_visibility="collapsed")
                                    if i not in st.session_state.planner_quiz_answers:
                                        st.session_state.planner_quiz_answers[i] = options.index(selected)
                                    else:
                                        st.session_state.planner_quiz_answers[i] = options.index(selected)
                                
                                if st.button("Submit Mini-Quiz", key=f"sub_mini_{item_topic[:10]}_{item_date}", type="primary", use_container_width=True):
                                    res = st.session_state.agent_controller.evaluate_quiz(questions, st.session_state.planner_quiz_answers)
                                    st.success(f"🎯 Score: {res['score']}/{res['total']} ({res['accuracy']*100:.1f}%)")
                                    # Also update progress if they did well
                                    if res['accuracy'] >= 0.7:
                                        st.session_state.agent_controller.planner_agent.mark_status(item_date, item_topic, 'completed')
                                        st.balloons()
                                        st.info("Great job! This topic has been marked as completed.")
                        
                        if st.button("Close Study Area", key=f"close_{item_topic[:10]}_{item_date}", use_container_width=True):
                            st.session_state.planner_study_mode = None
                            st.session_state.planner_study_topic = None
                            st.session_state.planner_temp_data = []
                            st.rerun()
                        
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("---")
        else:
            st.info("Click 'Create Revision Plan' to generate your schedule!")
    except Exception as e:
        st.info("Create a revision plan to get started!")

def show_chat_page():
    """Chat assistant page - Real-time AI study help"""
    st.markdown("### 💬 Chat Assistant")
    st.markdown("Ask questions about your study materials and get instant answers with source citations.")
    
    # Check if documents are processed
    if not st.session_state.documents_processed:
        st.warning("⚠️ Please upload and process documents first to use the chat assistant!")
        return
    
    # Check if vector store has content
    try:
        count = st.session_state.vector_store.get_collection_count()
        # If index is empty but we have chunks in memory, reindex on the fly
        if count == 0 and st.session_state.agent_controller and st.session_state.agent_controller.memory.chunks:
            st.info("Re-indexing your processed content...")
            st.session_state.vector_store.add_documents(st.session_state.agent_controller.memory.chunks)
            count = st.session_state.vector_store.get_collection_count()
        if count == 0:
            st.warning("⚠️ No documents indexed yet. Please process your documents first!")
            return
    except Exception:
        st.warning("⚠️ Vector store not initialized. Please process documents first!")
        return
    
    # Show latest document info
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.latest_document:
            st.info(f"📄 **Prioritizing:** {st.session_state.latest_document} (most recently uploaded)")
    with col2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Chat history with better formatting
    if st.session_state.chat_history:
        for i, chat_item in enumerate(st.session_state.chat_history):
            # Chat item can be tuple (question, answer) or dict with more info
            if isinstance(chat_item, tuple):
                question, answer = chat_item
                sources = []
            else:
                question = chat_item.get('question', '')
                answer = chat_item.get('answer', '')
                sources = chat_item.get('sources', [])
            
            # User question bubble
            st.markdown(f"""
            <div class="chat-message user-message">
                <div class="chat-bubble user-bubble">
                    <strong>You:</strong><br>{question}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Assistant answer bubble
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <div class="chat-bubble assistant-bubble">
                    <strong>Assistant:</strong><br>{answer}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show sources if available
            if sources:
                with st.expander(f"📚 Sources ({len(sources)})", expanded=False):
                    for source in sources:
                        st.markdown(f"• {source}")
            
            if i < len(st.session_state.chat_history) - 1:
                st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
    else:
        st.info("👋 Start a conversation! Ask a question about your study materials below.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Question input with better UI
    question = st.text_input(
        "💭 Ask a question about your study materials:",
        placeholder="e.g., What is machine learning? Explain the concept of recursion...",
        key="chat_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)
    
    # Check if question was already processed to prevent regeneration on scroll
    if ask_button:
        if question and question.strip():
            question_stripped = question.strip()
            # Check if this question was already answered
            already_answered = False
            for chat_item in st.session_state.chat_history:
                if isinstance(chat_item, dict):
                    if chat_item.get('question', '').strip() == question_stripped:
                        already_answered = True
                        break
                elif isinstance(chat_item, tuple):
                    if chat_item[0].strip() == question_stripped:
                        already_answered = True
                        break
            
            if not already_answered:
                # Show static loading message
                loading_placeholder = st.empty()
                loading_placeholder.info("Loading... Searching through your study materials...")
                
                try:
                    # Use latest document for prioritization
                    latest_doc = st.session_state.latest_document if st.session_state.latest_document else None
                    result = st.session_state.agent_controller.answer_question(
                        question_stripped, 
                        prioritize_source=latest_doc
                    )
                    
                    # Store with sources for better display
                    chat_item = {
                        'question': question_stripped,
                        'answer': result.get('answer', 'No answer generated.'),
                        'sources': result.get('sources', [])
                    }
                    st.session_state.chat_history.append(chat_item)
                    loading_placeholder.empty()
                    st.success("✅ Answer generated!")
                    st.rerun()
                except Exception as e:
                    loading_placeholder.empty()
                    st.error(f"❌ Error: {str(e)}. Please check your API key and try again.")
            else:
                st.info("This question was already answered. Scroll up to see the response.")
        else:
            st.warning("Please enter a question!")

def show_analytics_page():
    """Analytics and progress tracking"""
    st.markdown("### 📊 Analytics Dashboard")
    
    if not st.session_state.agent_controller:
        st.info("Process documents to see analytics!")
        return
    
    stats = st.session_state.agent_controller.get_statistics()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📈 Study Progress")
        st.metric("Total Topics", stats['total_topics'])
        st.metric("Total Chunks", stats['total_chunks'])
        st.metric("Flashcards Created", stats['total_flashcards'])
        st.metric("Quizzes Generated", stats['total_quizzes'])
    
    with col2:
        st.markdown("### 🎯 Performance")
        if stats['performance']['total_quizzes_taken'] > 0:
            st.metric("Average Score", f"{stats['performance']['average_score']*100:.1f}%")
            st.metric("Quizzes Completed", stats['performance']['total_quizzes_taken'])
        else:
            st.info("Take quizzes to see performance metrics!")
    
    if st.session_state.agent_controller.planner_agent:
        rev_stats = st.session_state.agent_controller.planner_agent.get_statistics()
        st.markdown("### 📅 Revision Progress")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Items", rev_stats['total_topics'])
        with col2:
            st.metric("Completed", rev_stats['completed'])
        with col3:
            st.metric("In Progress", rev_stats['in_progress'])
        with col4:
            st.metric("Completion Rate", f"{rev_stats['completion_rate']:.1f}%")

if __name__ == "__main__":
    main()

