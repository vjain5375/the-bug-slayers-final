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
        --deadpool-red: #E62429;
        --deadpool-black: #000000;
        --deadpool-dark-red: #8B0000;
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
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111 !important;
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
        box-shadow: 5px 5px 0px #000 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        width: 100% !important;
        min-height: 60px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.1 !important;
        margin-bottom: 10px !important;
    }

    /* Navigation Buttons Specific Style - Fix for uniformity */
    [data-testid="stHorizontalBlock"] div div div .stButton > button {
        height: 80px !important; 
        font-size: 1.1rem !important;
        white-space: normal !important; /* Allow break for longer names but keep height */
    }

    .stButton > button:hover {
        background-color: #FF3B3F !important;
        transform: translate(-3px, -3px) !important;
        box-shadow: 8px 8px 0px #000 !important;
        border-color: #000 !important;
    }

    .stButton > button:active {
        transform: translate(2px, 2px) !important;
        box-shadow: 2px 2px 0px #000 !important;
    }

    /* Comic Panels (Cards) */
    .stVerticalBlock > div > div {
        background: #1A1A1A !important;
        border: 5px solid #000 !important;
        border-radius: 0px !important;
        padding: 1.5rem !important;
        box-shadow: 10px 10px 0px var(--deadpool-red) !important;
        margin-bottom: 2rem !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #000 !important;
        border: 4px solid var(--deadpool-red) !important;
        padding: 1rem !important;
        box-shadow: 6px 6px 0px #000 !important;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stFileUploader {
        background-color: #222 !important;
        border: 4px solid #000 !important;
        color: #fff !important;
        font-size: 1rem !important;
        border-radius: 0px !important;
    }

    /* Markdown Text */
    h1, h2, h3 {
        font-family: 'Bangers', cursive !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
    }

    h1 { color: var(--deadpool-red) !important; font-size: 3.5rem !important; text-shadow: 4px 4px 0px #000 !important; }
    h2 { color: #fff !important; font-size: 2.2rem !important; border-bottom: 5px solid var(--deadpool-red); display: inline-block; margin-bottom: 1.2rem !important; }
    h3 { color: var(--deadpool-red) !important; font-size: 1.8rem !important; }

    /* Custom Halftone Overlay */
    .halftone {
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-image: radial-gradient(circle, #000 1px, transparent 1px);
        background-size: 6px 6px;
        opacity: 0.15;
        pointer-events: none;
        z-index: 1000;
    }
    
    /* Better spacing for main content */
    .main .block-container {
        padding-top: 2rem !important;
        max-width: 1200px !important;
    }

    /* Fixed height for info/success boxes to prevent vertical stretch */
    .stAlert {
        padding: 0.75rem 1rem !important;
        min-height: auto !important;
    }
    
    /* Sticker images */
    .sticker {
        transition: transform 0.3s ease;
    }
    .sticker:hover {
        transform: scale(1.1) rotate(5deg);
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
        st.success(f"✅ Weaponized {result['total_chunks']} chunks from {result['total_topics']} topics!{latest_info}")
        
        # Trigger Deadpool Balloons
        st.markdown("<script>window.launchDeadpoolBalloons();</script>", unsafe_allow_html=True)
        
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
    initialize_components()
    
    # Custom Red/White/Black Balloons Script
    st.markdown("""
    <script>
    function createBalloon() {
        const colors = ['#E62429', '#FFFFFF', '#000000'];
        const balloon = document.createElement('div');
        balloon.style.position = 'fixed';
        balloon.style.bottom = '-50px';
        balloon.style.left = Math.random() * 100 + 'vw';
        balloon.style.width = '30px';
        balloon.style.height = '40px';
        balloon.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        balloon.style.borderRadius = '50%';
        balloon.style.zIndex = '9999';
        balloon.style.pointerEvents = 'none';
        balloon.style.transition = 'transform 3s ease-out, opacity 3s ease-out';
        document.body.appendChild(balloon);
        
        setTimeout(() => {
            balloon.style.transform = `translateY(-110vh) translateX(${Math.random() * 100 - 50}px) scale(${Math.random() + 0.5})`;
            balloon.style.opacity = '0';
        }, 100);
        
        setTimeout(() => balloon.remove(), 4000);
    }
    window.launchDeadpoolBalloons = function() {
        for(let i=0; i<50; i++) {
            setTimeout(createBalloon, i * 50);
        }
    }
    </script>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
        /* Primary Buttons */
        .stButton > button[kind="primary"] {
            background-color: var(--deadpool-black) !important;
            color: var(--deadpool-red) !important;
            border-color: var(--deadpool-red) !important;
        }
        
        .stButton > button[kind="primary"]:hover {
            background-color: var(--deadpool-red) !important;
            color: #fff !important;
        }
        
        /* Secondary Buttons */
        .stButton > button[kind="secondary"] {
            background: rgba(102, 126, 234, 0.1) !important;
            color: #667eea !important;
            border: 2px solid rgba(102, 126, 234, 0.3) !important;
        }
        
        /* Enhanced Input Fields - No Transitions */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            border-radius: 12px !important;
            border: 2px solid rgba(102, 126, 234, 0.2) !important;
            padding: 0.75rem 1rem !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #667eea !important;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15), 0 4px 15px rgba(102, 126, 234, 0.2) !important;
        }
        
        /* Enhanced File Uploader */
        .stFileUploader {
            border-radius: 12px !important;
            padding: 1rem !important;
            border: 2px dashed rgba(102, 126, 234, 0.3) !important;
        }
        
        /* Enhanced Expanders */
        .streamlit-expanderHeader {
            border-radius: 10px !important;
            padding: 0.75rem 1rem !important;
        }
        
        /* Enhanced Metrics */
        [data-testid="stMetricValue"] {
            font-weight: 700 !important;
        }
        
        /* Enhanced Radio Buttons */
        .stRadio > div {
            gap: 0.5rem !important;
        }
        
        .stRadio > div > label {
            padding: 0.75rem 1rem !important;
            border-radius: 10px !important;
            border: 2px solid transparent !important;
        }
        
        /* Enhanced Success/Info/Error Messages - No Animations */
        .stSuccess, .stInfo, .stError, .stWarning {
            border-radius: 12px !important;
            padding: 1rem !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1) !important;
        }
        
        /* Enhanced Spacing */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 3rem !important;
        }
        
        /* Enhanced Dividers */
        hr {
            margin: 2rem 0 !important;
            border: none !important;
            height: 2px !important;
            background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.3), transparent) !important;
        }
        
        /* Smooth Scrollbar - No Transitions */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.05);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        
        /* Enhanced Selectbox */
        .stSelectbox > div > div {
            border-radius: 12px !important;
        }
        
        /* Enhanced Spinner - Completely Disable All Animations and Rotation */
        [data-testid="stSpinner"],
        [data-testid="stSpinner"] *,
        [data-testid="stSpinner"] *::before,
        [data-testid="stSpinner"] *::after {
            animation: none !important;
            transition: none !important;
            transform: none !important;
            -webkit-animation: none !important;
            -moz-animation: none !important;
            -o-animation: none !important;
        }
        
        /* Hide the rotating spinner circle completely */
        [data-testid="stSpinner"] > div {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            background: none !important;
        }
        
        /* Hide any pseudo-elements */
        [data-testid="stSpinner"] > div::before,
        [data-testid="stSpinner"] > div::after {
            display: none !important;
            content: none !important;
        }
        
        /* Stop any text rotation */
        [data-testid="stSpinner"] + div,
        [data-testid="stSpinner"] ~ div,
        [data-testid="stSpinner"] + div *,
        [data-testid="stSpinner"] ~ div * {
            animation: none !important;
            transform: none !important;
            rotate: none !important;
        }
        
        [data-testid="stSpinner"] + div::after,
        [data-testid="stSpinner"] ~ div::after {
            display: none !important;
            content: '' !important;
        }
        
        /* Target Streamlit's spinner container */
        .stSpinner,
        .stSpinner *,
        .stSpinner *::before,
        .stSpinner *::after {
            animation: none !important;
            transition: none !important;
            transform: none !important;
        }
        
        .stSpinner > div {
            display: none !important;
        }
        
        /* Better Focus States */
        button:focus,
        input:focus,
        textarea:focus,
        select:focus {
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2) !important;
        }
        
        /* Smooth Text Selection */
        ::selection {
            background: rgba(102, 126, 234, 0.3);
            color: inherit;
        }
        
        /* Disable all transitions and animations globally */
        *, *::before, *::after {
            transition: none !important;
            animation: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <script>
        // Disable all animations and transitions
        function disableAllAnimations() {
            // Remove all transitions and animations from all elements
            const style = document.createElement('style');
            style.id = 'no-animations-style';
            style.textContent = `
                *, *::before, *::after {
                    transition: none !important;
                    animation: none !important;
                    transform: none !important;
                    -webkit-animation: none !important;
                    -moz-animation: none !important;
                    -o-animation: none !important;
                }
                [data-testid="stSpinner"],
                [data-testid="stSpinner"] *,
                .stSpinner,
                .stSpinner * {
                    animation: none !important;
                    transition: none !important;
                    transform: none !important;
                    display: none !important;
                }
            `;
            // Remove old style if exists
            const oldStyle = document.getElementById('no-animations-style');
            if (oldStyle) oldStyle.remove();
            document.head.appendChild(style);
            
            // Stop all animations on existing elements
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                el.style.transition = 'none';
                el.style.animation = 'none';
                el.style.transform = 'none';
                el.style.webkitAnimation = 'none';
                el.style.mozAnimation = 'none';
                el.style.oAnimation = 'none';
            });
            
            // Specifically target and hide spinners
            const spinners = document.querySelectorAll('[data-testid="stSpinner"], .stSpinner');
            spinners.forEach(spinner => {
                spinner.style.display = 'none';
                spinner.style.visibility = 'hidden';
                const spinnerDiv = spinner.querySelector('div');
                if (spinnerDiv) {
                    spinnerDiv.style.display = 'none';
                    spinnerDiv.style.animation = 'none';
                    spinnerDiv.style.transform = 'none';
                }
            });
        }
        
        // Run immediately
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', disableAllAnimations);
        } else {
            disableAllAnimations();
        }
        
        // Also run after a delay to catch any late-rendered elements
        setTimeout(disableAllAnimations, 100);
        setTimeout(disableAllAnimations, 500);
        setTimeout(disableAllAnimations, 1000);
        setTimeout(disableAllAnimations, 2000);
        
        // Watch for any new spinners being added to the DOM and immediately disable them
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Element node
                        // Check if it's a spinner or contains a spinner
                        if (node.matches && (node.matches('[data-testid="stSpinner"]') || node.matches('.stSpinner'))) {
                            disableAllAnimations();
                        }
                        // Check children
                        const spinners = node.querySelectorAll ? node.querySelectorAll('[data-testid="stSpinner"], .stSpinner') : [];
                        if (spinners.length > 0) {
                            disableAllAnimations();
                        }
                    }
                });
            });
        });
        
        // Start observing
        if (document.body) {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
        
        // Also run continuously to catch any missed spinners
        setInterval(function() {
            const spinners = document.querySelectorAll('[data-testid="stSpinner"], .stSpinner');
            if (spinners.length > 0) {
                spinners.forEach(spinner => {
                    spinner.style.display = 'none';
                    spinner.style.visibility = 'hidden';
                    spinner.style.animation = 'none';
                    spinner.style.transform = 'none';
                    const spinnerDiv = spinner.querySelector('div');
                    if (spinnerDiv) {
                        spinnerDiv.style.display = 'none';
                        spinnerDiv.style.animation = 'none';
                        spinnerDiv.style.transform = 'none';
                    }
                });
            }
        }, 100);
    </script>
    """, unsafe_allow_html=True)
    
    # Deadpool Branding Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="font-family: 'Bangers', cursive; font-size: 5.5rem; color: var(--deadpool-red); text-shadow: 8px 8px 0px #000; margin: 0;">⚡ DEADPOOL'S STUDY HUB</h1>
        <div style="background: var(--deadpool-red); height: 12px; width: 400px; margin: 1rem auto; border: 4px solid #000; box-shadow: 6px 6px 0px #000;"></div>
        <p style="font-family: 'Bangers', cursive; font-size: 2rem; color: #fff; letter-spacing: 2px; text-transform: uppercase;">WEAPONIZING YOUR DOCUMENTS FOR MAXIMUM LEARNING EFFORT!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Mission Control
    with st.sidebar:
        st.image("https://pngimg.com/uploads/deadpool/deadpool_PNG10.png", width=120)
        st.markdown("<h2 class='sidebar-title'>💀 MISSION CONTROL</h2>", unsafe_allow_html=True)
        
        nav_options = {"Home":"🏠","Flashcards":"📇","Quizzes":"📝","Revision Planner":"📅","Chat Assistant":"💬","Analytics":"📊"}
        current_index = list(nav_options.keys()).index(st.session_state.current_page) if st.session_state.current_page in nav_options else 0
        
        page = st.radio("Select Your Objective", list(nav_options.keys()), format_func=lambda x: f"{nav_options[x]} {x}", index=current_index)
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()
            
        st.divider()
        st.markdown("### 📚 ARSENAL (DOCS)")
        uploaded_files = st.file_uploader("Load intel", type=['pdf','docx','txt'], accept_multiple_files=True, key="sidebar_uploader_final", label_visibility="collapsed")
        
        if uploaded_files:
            st.session_state.uploaded_files_shared = uploaded_files
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 LOCK", use_container_width=True, key="side_lock_final"):
                    docs_dir = ensure_documents_directory()
                    for f in uploaded_files:
                        with open(docs_dir / f.name, "wb") as file: file.write(f.getbuffer())
                    st.success("Locked!")
                    st.session_state.documents_processed = False
                    st.rerun()
            with c2:
                if st.button("🔄 ANALYZE", use_container_width=True, type="primary", key="side_analyze_final"):
                    if process_documents(): st.balloons(); st.rerun()
        
        st.divider()
        st.image("https://pngimg.com/uploads/deadpool/deadpool_PNG43.png", width=150)
        st.markdown("<p style='text-align:center; font-style:italic; color:#666;'>- Maximum Effort! -</p>", unsafe_allow_html=True)
    
    # Hero / Banner logic
    st.markdown("## 📤 ARSENAL UPLOAD")
    st.markdown("""
    <div style="background: #111; padding: 2.5rem; border: 6px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); margin-bottom: 2rem; text-align: center; position: relative; overflow: hidden;">
        <img src="https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-1.png" width="100" style="position: absolute; left: -20px; top: -20px; opacity: 0.3; transform: rotate(-20deg);">
        <h2 style="color: var(--deadpool-red); border: none; margin:0; font-size: 2.5rem;">📤 FEED THE MERCENARY</h2>
        <p style="font-family: 'Oswald', sans-serif; font-size: 1.3rem; color: #fff; margin-top: 10px;">Upload your study materials here or in the sidebar. I'll turn them into gold... semantically speaking.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_up, col_img = st.columns([3, 1])
    with col_up:
        uploaded_files_main = st.file_uploader("Choose intel files", type=['pdf','docx','txt'], accept_multiple_files=True, key="main_uploader", label_visibility="collapsed")
        if uploaded_files_main: st.session_state.uploaded_files_shared = uploaded_files_main
    
    with col_img:
        st.image("https://pngimg.com/uploads/deadpool/deadpool_PNG10.png", width=120)

    files_to_process = uploaded_files_main if uploaded_files_main else st.session_state.get('uploaded_files_shared')
    
    if files_to_process:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 LOCK INTEL", use_container_width=True, key="save_main_files"):
                docs_dir = ensure_documents_directory()
                for f in files_to_process:
                    with open(docs_dir / f.name, "wb") as file: file.write(f.getbuffer())
                st.success("✅ Intel locked!")
                st.session_state.documents_processed = False
                st.rerun()
        with c2:
            if st.button("🔄 WEAPONIZE NOW", use_container_width=True, type="primary", key="process_main_files"):
                if process_documents(): st.balloons(); st.rerun()
    
    # Existing Documents
    doc_files = get_document_files()
    if doc_files:
        st.markdown("### 📁 CURRENT ARSENAL")
        with st.expander(f"Inspect {len(doc_files)} intel files", expanded=False):
            for doc in doc_files:
                doc_name = Path(doc).name
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"🗡️ **{doc_name}**")
                if c2.button("🗑️", key=f"delete_{doc_name}"):
                    Path(doc).unlink(); st.rerun()
    
    st.divider()
    
    # Navigation Buttons Grid
    st.markdown("## 🎯 MISSION OBJECTIVES")
    nav_cols = st.columns(6)
    pages = list(nav_options.keys())
    for i in range(6):
        with nav_cols[i]:
            p_name = pages[i]
            is_active = st.session_state.current_page == p_name
            if st.button(f"{nav_options[p_name]}\n{p_name.upper()}", key=f"main_nav_{p_name}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state.current_page = p_name
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

    # Footer with Sticker
    st.markdown("""
    <div style="text-align: center; margin-top: 5rem; padding: 2rem; border-top: 4px solid var(--deadpool-red); background: #000;">
        <img src="https://pngimg.com/uploads/deadpool/deadpool_PNG43.png" width="200" style="margin-bottom: 1rem;">
        <p style="color: #fff; font-family: 'Oswald', sans-serif; font-size: 0.9rem; margin: 0;">© 2025 Deadpool's Study Hub. No regenerating degenerates allowed.</p>
        <h3 style="color: var(--deadpool-red); margin-top: 1rem;">💀 MAXIMUM EFFORT! ⚔️</h3>
    </div>
    """, unsafe_allow_html=True)

def show_home_page():
    """Deadpool-themed Home page with high-impact visuals and introduction"""
    
    # Hero Section with Deadpool Action Grid Style
    st.markdown("""
    <div style="background: url('https://w0.peakpx.com/wallpaper/744/403/HD-wallpaper-deadpool-marvel-comic.jpg') center/cover; padding: 7rem 2rem; border: 8px solid #000; box-shadow: 15px 15px 0px var(--deadpool-red); text-align: center; margin-bottom: 4rem; position: relative;">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6);"></div>
        <div style="position: relative; z-index: 2;">
            <h1 style="font-family: 'Bangers', cursive; color: var(--deadpool-red); font-size: 4.5rem; text-shadow: 8px 8px 0px #000; margin: 0;">STOP STUDYING LIKE A DEGENERATE!</h1>
            <p style="font-family: 'Bangers', cursive; color: #fff; font-size: 2rem; background: #000; display: inline-block; padding: 0.8rem 2.5rem; transform: skew(-10deg); margin-top: 2rem; border: 4px solid var(--deadpool-red);">I'll turn your boring PDFs into semantic weapons of mass learning.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # NEW: MISSION BRIEFING (Introduction for Audience)
    st.markdown("""
    <div style="background: #1A1A1A; padding: 3rem; border: 5px solid #000; box-shadow: 10px 10px 0px var(--deadpool-red); margin-bottom: 4rem; border-left: 15px solid var(--deadpool-red);">
        <h2 style="color: var(--deadpool-red); border: none; font-size: 3rem; margin-bottom: 1rem;">📜 MISSION BRIEFING</h2>
        <p style="font-family: 'Oswald', sans-serif; font-size: 1.4rem; color: #fff; line-height: 1.6;">
            Welcome to the <b>Deadpool Study Hub</b>. This isn't just another website; it's a high-tech Multi-Agent system designed to 
            <b>Weaponize your Knowledge</b>. 
            <br><br>
            Instead of reading page after page of dry text, you feed your documents to my specialized agents. They slice, dice, 
            and categorize your info into semantic chunks, allowing you to generate <b>Flashcards</b>, <b>Adaptive Quizzes</b>, 
            and <b>Smart Revision Plans</b> instantly. 
            <br><br>
            Need a specific answer? My <b>Chat Assistant</b> has read your docs and is ready to spill the beans. 
            <b>Maximum Effort, Minimum Boredom.</b>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # CASE 1: NEW USER EXPERIENCE (High-Impact Onboarding)
    if not st.session_state.documents_processed:
        st.markdown("<h2 style='text-align: center; font-size: 3.5rem; margin-bottom: 3rem;'>⚔️ HOW IT WORKS (STEP-BY-STEP)</h2>", unsafe_allow_html=True)
        
        # Journey Cards with Comic Borders
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            <div style="background: #111; padding: 2.5rem; border: 5px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); margin-bottom: 3rem; transform: rotate(-1deg); min-height: 220px;">
                <img src="https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-1.png" width="90" style="float: right; margin-left: 15px;">
                <h3 style="font-size: 2.5rem; color: var(--deadpool-red);">1️⃣ LOAD INTEL</h3>
                <p style="color: #fff; font-size: 1.3rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Upload your PDFs, DOCX, or Text notes in the 'Arsenal' section. Don't worry, I won't bite... much.</p>
            </div>
            <div style="background: #111; padding: 2.5rem; border: 5px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); margin-bottom: 3rem; transform: rotate(1deg); min-height: 220px;">
                <img src="https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-3.png" width="90" style="float: right; margin-left: 15px;">
                <h3 style="font-size: 2.5rem; color: var(--deadpool-red);">3️⃣ EXTRACT Semantics</h3>
                <p style="color: #fff; font-size: 1.3rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'Weaponize Now'</b>. My agents will slice and dice your text into semantic chunks ready for the brain-vault.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div style="background: #111; padding: 2.5rem; border: 5px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); margin-bottom: 3rem; transform: rotate(1deg); min-height: 220px;">
                <img src="https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-2.png" width="90" style="float: right; margin-left: 15px;">
                <h3 style="font-size: 2.5rem; color: var(--deadpool-red);">2️⃣ LOCK IT IN</h3>
                <p style="color: #fff; font-size: 1.3rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Hit <b>'Lock Intel'</b> to commit those files to my infinite memory banks. No turning back now!</p>
            </div>
            <div style="background: #111; padding: 2.5rem; border: 5px solid #000; box-shadow: 12px 12px 0px var(--deadpool-red); margin-bottom: 3rem; transform: rotate(-1deg); min-height: 220px;">
                <img src="https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-4.png" width="90" style="float: right; margin-left: 15px;">
                <h3 style="font-size: 2.5rem; color: var(--deadpool-red);">4️⃣ DOMINATE Exams</h3>
                <p style="color: #fff; font-size: 1.3rem; font-weight: 600; font-family: 'Oswald', sans-serif;">Boom! 💥 Flashcards, Quizzes, and Revision Plans are now live. Time to show those documents who's boss.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # Large centered thumbs up
        col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
        with col_c2:
            st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", use_container_width=True)
        
        return


    # CASE 2: RETURNING USER (Pro Dashboard)
    st.markdown("<h2>⚡ COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    # 1. High-Impact Quick Access
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📇 **CARDS**\n\nMAX EFFORT", use_container_width=True, key="dash_flash"):
            st.session_state.current_page = "Flashcards"; st.rerun()
    with col2:
        if st.button("📝 **QUIZ**\n\nNO MERCY", use_container_width=True, key="dash_quiz"):
            st.session_state.current_page = "Quizzes"; st.rerun()
    with col3:
        if st.button("📅 **PLAN**\n\nTACTICAL", use_container_width=True, key="dash_plan"):
            st.session_state.current_page = "Revision Planner"; st.rerun()
    with col4:
        if st.button("💬 **CHAT**\n\nINTEL", use_container_width=True, key="dash_chat"):
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
                    <div style="background: #222; padding: 1.5rem; border: 3px solid var(--deadpool-red); border-radius: 0px; font-size: 1rem; margin-bottom: 1rem; color: #eee; font-style: italic; box-shadow: 5px 5px 0px #000;">
                        "{chunk['text'][:150]}..."
                    </div>
                    """, unsafe_allow_html=True)

    # Thumbs up Deadpool at the bottom for returning users too
    st.markdown("<br>", unsafe_allow_html=True)
    st.image("https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png", width=300)

    # 4. Deadpool Footer EXPANDER
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.expander("💀 THE CHIMICHANGA MANUAL (HELP)", expanded=False):
        st.markdown("""
        <div style="padding: 2rem; background: #111; border: 5px solid var(--deadpool-red); border-radius: 0px; box-shadow: 10px 10px 0px #000;">
            <h4 style="font-family: 'Bangers', cursive; color: var(--deadpool-red); font-size: 2.5rem; margin-top: 0;">DON'T BE A DEGENERATE:</h4>
            <ul style="color: #fff; font-size: 1.3rem; font-family: 'Oswald', sans-serif;">
                <li><b>RELOAD:</b> Put new files in the side-slot and hit 'Process' to reload your arsenal.</li>
                <li><b>EXTRACT:</b> Anki and CSV buttons are in the Cards/Quiz zones. Use 'em.</li>
                <li><b>EFFORT:</b> If the AI is slow, it's probably thinking about tacos. Give it a sec.</li>
            </ul>
            <p style="text-align: right; font-style: italic; color: var(--deadpool-red); font-family: 'Bangers', cursive; font-size: 1.5rem;">- Deadpool Out.</p>
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
                    status_color = "#28a745" if status == 'completed' else "#ffc107" if status == 'in_progress' else "#667eea"
                    status_icon = "✅" if status == 'completed' else "⏳" if status == 'in_progress' else "📅"
                    
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.05); padding: 1.2rem; border-radius: 15px; border-left: 5px solid {status_color}; margin-top: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 style="margin: 0; color: white;">{status_icon} {item_date} — {item_topic}</h4>
                            <span style="background: {status_color}; color: white; padding: 0.2rem 0.8rem; border-radius: 20px; font-size: 0.7rem; font-weight: 700;">{status.upper()}</span>
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

