"""
AI Study Assistant - Multi-Agent System
Personalized study assistant with flashcards, quizzes, and revision planning
"""

import streamlit as st
import os
import logging
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

# Load CSS (simplified version - can be expanded)
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    .main .block-container {
        background: transparent;
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #e0e0e0 !important;
    }
</style>
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

def process_documents():
    """Process all documents using Reader Agent"""
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    
    if not doc_files:
        st.error("No documents found. Please upload PDF, DOCX, or TXT files.")
        return False
    
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
        
        return True
    else:
        st.error("No content could be extracted from documents.")
        return False

def main():
    """Main application"""
    initialize_components()
    
    # Enhanced UI Styling - No Transitions or Animations
    st.markdown("""
    <style>
        /* Enhanced Buttons - No Transitions */
        .stButton > button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            padding: 0.75rem 1.5rem !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1) !important;
            border: none !important;
        }
        
        /* Primary Buttons */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4) !important;
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
    
    # Header
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 3rem 2rem; border-radius: 20px; margin-bottom: 2rem; text-align: center; box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);">
        <h1 style="color: white; font-size: 4rem; margin: 0; font-weight: 900;">📚 AI Study Assistant</h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.8rem; margin-top: 0.5rem;">Your Personalized Multi-Agent Learning Companion</p>
        <p style="color: rgba(255,255,255,0.9); font-size: 1.2rem; margin-top: 1rem;">✨ Upload study materials, generate flashcards, take quizzes, and plan your revision</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Upload Section First, then Navigation
    with st.sidebar:
        # Document Management - Upload Section (Moved to top)
        st.markdown("### 📚 Document Management")
        st.markdown("""
        <div style="background: rgba(102, 126, 234, 0.1); padding: 1rem; border-radius: 10px; margin-bottom: 1rem; border: 2px dashed rgba(102, 126, 234, 0.3);">
            <p style="color: #667eea; margin: 0; text-align: center; font-weight: 600;">📤 Quick Upload</p>
        </div>
        """, unsafe_allow_html=True)
        
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
        
        # Navigation Section (Moved below Upload)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; margin-bottom: 1rem; text-align: center;">
            <h2 style="color: white; margin: 0; font-size: 1.5rem;">🎯 Navigation</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Make navigation buttons more visible
        nav_options = {
            "Home": "🏠",
            "Flashcards": "📇",
            "Quizzes": "📝",
            "Revision Planner": "📅",
            "Chat Assistant": "💬",
            "Analytics": "📊"
        }
        
        # Get current index for radio button
        current_index = 0
        if st.session_state.current_page in nav_options:
            current_index = list(nav_options.keys()).index(st.session_state.current_page)
        
        page = st.radio(
            "Select Page",
            list(nav_options.keys()),
            format_func=lambda x: f"{nav_options[x]} {x}",
            index=current_index
        )
        
        # Sync with main page navigation
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()
        
        st.markdown("---")
        st.markdown("**💡 Tip:** Use the buttons above to quickly access Flashcards and Quizzes!")
        
        st.divider()
        
        # Workflow Guide
        with st.expander("📖 How It Works - Step by Step", expanded=False):
            st.markdown("""
            ### 🔄 AI Study Assistant Workflow
            
            **1️⃣ Upload Documents**
            - Upload PDF, DOCX, or TXT files
            - Multiple files can be uploaded at once
            
            **2️⃣ Text Extraction**
            - System extracts text from PDFs
            - Supports OCR for image-based documents
            
            **3️⃣ Chunking**
            - Text is divided into manageable pieces
            - Maintains context across chunks
            
            **4️⃣ Topic Classification**
            - AI identifies topics and subtopics
            - Organizes content for better learning
            
            **5️⃣ Embeddings**
            - Creates semantic search vectors
            - Enables intelligent content retrieval
            
            **6️⃣ Generate Content**
            - **Flashcards**: Auto-generated Q/A pairs
            - **Quizzes**: Adaptive practice tests
            - **Planner**: Smart revision schedules
            
            **7️⃣ Chat & Learn**
            - Ask questions about your materials
            - Get answers with source citations
            - Understand concepts better
            
            ---
            **Quick Start:**
            1. Upload → 2. Save → 3. Process → 4. Generate/Ask
            """)
        
        st.divider()
    
    # Upload Section in Main Dashboard - Moved Above Navigation
    st.markdown("### 📤 Upload Your Study Materials")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 20px; margin: 1rem 0; text-align: center; box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);">
        <h2 style="color: white; margin: 0 0 1rem 0; font-size: 2rem;">📤 Upload Your Study Materials</h2>
        <p style="color: rgba(255,255,255,0.9); margin: 0; font-size: 1.1rem;">Upload PDF, DOCX, or TXT files to get started</p>
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
            help="Select one or more study material files (PDF, DOCX, TXT)"
        )
        # Sync with sidebar
        if uploaded_files_main:
            st.session_state.uploaded_files_shared = uploaded_files_main
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
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
            if st.button("💾 Save Files", use_container_width=True, type="primary", key="save_main_files"):
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
            if st.button("🔄 Process & Index", use_container_width=True, type="primary", key="process_main_files"):
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
        st.markdown("### 📁 Your Documents")
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
    
    st.markdown("---")
    
    # Navigation Buttons - Below Upload Section
    st.markdown("### 🎯 Navigation")
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
            nav_button = st.button(f"{icon}\n{page_name}", use_container_width=True, key=f"main_nav_{page_name}", type=button_type)
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

def show_home_page():
    """Home page with overview"""
    st.markdown("### 🏠 Welcome to Your Study Assistant")
    
    # Workflow Guide Section on Main Page
    with st.expander("📖 How It Works - Complete Workflow", expanded=True):
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 2rem; border-radius: 15px; border: 1px solid rgba(102, 126, 234, 0.3);">
            <h3 style="color: #667eea; margin-top: 0;">🔄 AI Study Assistant Workflow</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Visual workflow steps
        workflow_steps = [
            ("📤 Upload", "PDF/Image/Text Upload", "Upload your study materials (PDF, DOCX, TXT)"),
            ("📄 Extract", "Text Extraction", "System extracts text from PDFs or uses OCR for images"),
            ("✂️ Chunk", "Text Chunking", "Text is divided into manageable pieces while preserving context"),
            ("🏷️ Classify", "Topic Classification", "AI identifies topics and subtopics using LLM"),
            ("🔍 Embed", "Create Embeddings", "Generates semantic search vectors for intelligent retrieval"),
            ("✨ Generate", "Flashcards, Quiz, Planner", "Auto-generate study materials based on your content"),
            ("💬 Chat", "Ask Questions", "Get answers with source citations for better understanding")
        ]
        
        for i, (icon, title, desc) in enumerate(workflow_steps, 1):
            col1, col2 = st.columns([1, 10])
            with col1:
                st.markdown(f"### {icon}")
            with col2:
                st.markdown(f"**{i}. {title}** - {desc}")
                if i < len(workflow_steps):
                    st.markdown("⬇️")
        
        st.markdown("---")
        st.markdown("""
        ### 🚀 Quick Start Guide
        
        1. **Upload** your study materials (PDF, DOCX, or TXT files)
        2. **Save** the files to your document library
        3. **Process** to extract, chunk, and index the content
        4. **Generate** flashcards, quizzes, or create a revision plan
        5. **Chat** to ask questions and get instant answers
        
        **💡 Pro Tip:** The most recently uploaded document gets priority in searches!
        """)
    
    # Show processing results if available
    if st.session_state.documents_processed and 'processing_results' in st.session_state:
        result = st.session_state.processing_results
        
        # Display Topics with Key Points
        if result.get('topics'):
            st.markdown("### 📚 Extracted Topics & Key Points")
            topics = result['topics']
            
            for idx, topic_data in enumerate(topics[:10], 1):  # Show first 10 topics
                topic_name = topic_data.get('topic', f'Topic {idx}')
                subtopics = topic_data.get('subtopics', [])
                key_points = topic_data.get('key_points', [])
                
                with st.expander(f"📖 {idx}. {topic_name}", expanded=(idx == 1)):
                    if subtopics:
                        st.markdown("**Subtopics:**")
                        for subtopic in subtopics[:5]:  # Show first 5 subtopics
                            st.markdown(f"  • {subtopic}")
                    
                    if key_points:
                        st.markdown("**Key Points:**")
                        for point in key_points[:5]:  # Show first 5 key points
                            st.markdown(f"  ✓ {point}")
                    else:
                        # If no key points from LLM, show sample chunks from this topic
                        topic_chunks = [
                            chunk for chunk in result.get('chunks', [])
                            if chunk.get('metadata', {}).get('topic', '') == topic_name
                        ]
                        if topic_chunks:
                            st.markdown("**Sample Content:**")
                            for chunk in topic_chunks[:2]:  # Show first 2 chunks
                                chunk_text = chunk.get('text', '')[:200]  # First 200 chars
                                if chunk_text:
                                    st.markdown(f"  • {chunk_text}...")
            
            if len(topics) > 10:
                st.info(f"📊 Showing first 10 of {len(topics)} topics. More topics available in the processed content.")
        
        # Display Sample Extracted Text/Chunks
        if result.get('chunks'):
            st.markdown("### 📄 Sample Extracted Text Chunks")
            st.markdown(f"**Total Chunks:** {len(result['chunks'])}")
            
            with st.expander("View Sample Chunks", expanded=False):
                # Group chunks by topic
                chunks_by_topic = {}
                for chunk in result['chunks'][:20]:  # Show first 20 chunks
                    topic = chunk.get('metadata', {}).get('topic', 'General')
                    if topic not in chunks_by_topic:
                        chunks_by_topic[topic] = []
                    chunks_by_topic[topic].append(chunk)
                
                for topic_name, topic_chunks in list(chunks_by_topic.items())[:5]:  # Show first 5 topics
                    st.markdown(f"**📌 Topic: {topic_name}** ({len(topic_chunks)} chunks)")
                    for i, chunk in enumerate(topic_chunks[:3], 1):  # Show first 3 chunks per topic
                        chunk_text = chunk.get('text', '')
                        source = chunk.get('metadata', {}).get('source', 'Unknown')
                        st.markdown(f"  **Chunk {i}** (from {source}):")
                        st.text(chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text)
                        st.markdown("---")
        
        st.markdown("---")
    
    if not st.session_state.documents_processed:
        if not st.session_state.get('uploaded_files_shared'):
            st.info("👆 Upload your study materials above to get started!")
        return
    
    # Quick Access Buttons - Make Flashcards and Quizzes more prominent
    st.markdown("### 🚀 Quick Access")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📇 **Flashcards**\n\nGenerate Q/A Cards", use_container_width=True, type="primary", key="quick_flashcards_home"):
            st.session_state.current_page = "Flashcards"
            st.rerun()
    
    with col2:
        if st.button("📝 **Quizzes**\n\nTake Practice Tests", use_container_width=True, type="primary", key="quick_quizzes_home"):
            st.session_state.current_page = "Quizzes"
            st.rerun()
    
    with col3:
        if st.button("📅 **Planner**\n\nRevision Schedule", use_container_width=True, type="primary", key="quick_planner_home"):
            st.session_state.current_page = "Revision Planner"
            st.rerun()
    
    with col4:
        if st.button("💬 **Chat**\n\nAsk Questions", use_container_width=True, type="primary", key="quick_chat_home"):
            st.session_state.current_page = "Chat Assistant"
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Feature cards with more details
    st.markdown("### ✨ Features")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 2rem; border-radius: 15px; border: 1px solid rgba(102, 126, 234, 0.3); cursor: pointer;" onclick="window.location.href='#flashcards'">
            <h3 style="color: #667eea; margin: 0;">📇 Flashcards</h3>
            <p style="color: #b0b0b0; margin-top: 0.5rem;">Auto-generated Q/A pairs for quick revision</p>
            <p style="color: #667eea; font-size: 0.9rem; margin-top: 1rem;">👉 Click "Flashcards" in sidebar to start</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 2rem; border-radius: 15px; border: 1px solid rgba(102, 126, 234, 0.3);">
            <h3 style="color: #667eea; margin: 0;">📝 Quizzes</h3>
            <p style="color: #b0b0b0; margin-top: 0.5rem;">Adaptive quizzes with multiple difficulty levels</p>
            <p style="color: #667eea; font-size: 0.9rem; margin-top: 1rem;">👉 Click "Quizzes" in sidebar to start</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 2rem; border-radius: 15px; border: 1px solid rgba(102, 126, 234, 0.3);">
            <h3 style="color: #667eea; margin: 0;">📅 Planner</h3>
            <p style="color: #b0b0b0; margin-top: 0.5rem;">Smart revision schedules based on your progress</p>
            <p style="color: #667eea; font-size: 0.9rem; margin-top: 1rem;">👉 Click "Revision Planner" in sidebar</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Statistics
    if st.session_state.agent_controller:
        stats = st.session_state.agent_controller.get_statistics()
        st.markdown("### 📊 Your Progress")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Topics", stats['total_topics'])
        with col2:
            st.metric("Flashcards", stats['total_flashcards'])
        with col3:
            st.metric("Quizzes", stats['total_quizzes'])
        with col4:
            st.metric("Completion", f"{stats['revision_stats']['completion_rate']:.1f}%")

def show_flashcards_page():
    """Flashcards page"""
    st.markdown("### 📇 Flashcards")
    
    if not st.session_state.documents_processed:
        st.warning("Please process documents first!")
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        num_flashcards = st.slider("Number of flashcards", 5, 30, value=st.session_state.num_flashcards, key="flashcard_slider")
    with col2:
        if st.button("🔄 Generate Flashcards", use_container_width=True, type="primary"):
            # Show static processing message
            processing_msg = st.info("Processing... Generating flashcards...")
            flashcards = st.session_state.agent_controller.generate_flashcards(num_flashcards)
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
            st.session_state.quizzes = questions
            st.session_state.quiz_answers = {}
            st.session_state.num_questions = 10  # Reset to default
            st.success(f"✅ Generated {len(questions)} questions!")
            st.rerun()
    
    # Display quiz
    if st.session_state.quizzes:
        st.markdown(f"### 📋 Quiz ({len(st.session_state.quizzes)} questions)")
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
                    st.markdown(f"Your answer: {detail['user_answer']} | Correct: {detail['correct_answer']}")
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
            upcoming = st.session_state.agent_controller.planner_agent.get_upcoming_revisions(7)
            if upcoming:
                st.markdown("### 🔜 Upcoming (Next 7 Days)")
                for item in upcoming[:10]:
                    status_icon = "✅" if item['status'] == 'completed' else "⏳"
                    st.markdown(f"{status_icon} **{item['date']}** - {item['topic']}")
                    if st.button(f"Mark Complete", key=f"complete_{item['date']}_{item['topic']}"):
                        st.session_state.agent_controller.planner_agent.mark_completed(
                            item['date'], item['topic']
                        )
                        st.rerun()
        else:
            st.info("Click 'Create Revision Plan' to generate your schedule!")
    except Exception as e:
        st.info("Create a revision plan to get started!")

def show_chat_page():
    """Chat assistant page"""
    st.markdown("### 💬 Chat Assistant")
    st.markdown("Ask questions about your study materials and get instant answers with source citations.")
    
    # Check if documents are processed
    if not st.session_state.documents_processed:
        st.warning("⚠️ Please upload and process documents first to use the chat assistant!")
        return
    
    # Check if vector store has content
    try:
        count = st.session_state.vector_store.get_collection_count()
        if count == 0:
            st.warning("⚠️ No documents indexed yet. Please process your documents first!")
            return
    except:
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
        st.metric("Quizzes Taken", stats['total_quizzes'])
    
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

