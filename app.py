"""
AI Study Assistant - Multi-Agent System
Personalized study assistant with flashcards, quizzes, and revision planning
"""

import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv
from vector_store import VectorStore
from agents.controller import AgentController
from utils import ensure_documents_directory, get_document_files

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
    # Clear vector store
    try:
        temp_vs = VectorStore()
        temp_vs.clear_collection()
    except Exception:
        pass
    st.session_state.documents_processed = False
    st.session_state.uploaded_files_shared = None
    st.session_state.latest_document = None
    st.session_state.document_upload_order = []  # Track upload order

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
    """Initialize vector store and agent controller"""
    api_key = load_api_key()
    
    if st.session_state.vector_store is None:
        with st.spinner("Initializing vector store..."):
            st.session_state.vector_store = VectorStore()
    
    if st.session_state.agent_controller is None:
        with st.spinner("Initializing AI agents..."):
            if not api_key:
                st.error("⚠️ API key not found! Please check your .env file.")
                st.stop()
            st.session_state.agent_controller = AgentController(st.session_state.vector_store)

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
    
    with st.spinner("Processing documents with Reader Agent..."):
        result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
        
        if result['total_chunks'] > 0:
            st.session_state.documents_processed = True
            latest_info = f" (Latest: {st.session_state.latest_document})" if st.session_state.latest_document else ""
            st.success(f"✅ Processed {result['total_chunks']} chunks from {result['total_topics']} topics!{latest_info}")
            
            # Store processing results for display
            st.session_state.processing_results = result
            
            # Celebration effect - Balloons animation
            st.balloons()
            
            return True
        else:
            st.error("No content could be extracted from documents.")
            return False

def main():
    """Main application"""
    initialize_components()
    
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
                        # Balloons already shown in process_documents()
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
                # Balloons already shown in process_documents()
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
            key="page_selector",
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
        
        # Document Management - Sidebar (kept as is)
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
                        # Balloons already shown in process_documents()
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
                # Balloons already shown in process_documents()
                # Show summary in sidebar
                if 'processing_results' in st.session_state:
                    result = st.session_state.processing_results
                    st.success(f"✅ {result['total_chunks']} chunks, {result['total_topics']} topics extracted!")
        
        if st.session_state.vector_store:
            count = st.session_state.vector_store.get_collection_count()
            st.metric("Indexed Chunks", count)
    
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
                    # Balloons already shown in process_documents()
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
        if not uploaded_files_main:
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
        num_flashcards = st.slider("Number of flashcards", 5, 30, 10)
    with col2:
        if st.button("🔄 Generate Flashcards", use_container_width=True, type="primary"):
            with st.spinner("Generating flashcards..."):
                flashcards = st.session_state.agent_controller.generate_flashcards(num_flashcards)
                st.session_state.flashcards = flashcards
                st.success(f"✅ Generated {len(flashcards)} flashcards!")
    
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
        num_questions = st.slider("Questions", 3, 10, 5)
    with col3:
        adaptive = st.checkbox("Adaptive", value=True)
        if st.button("🎯 Generate Quiz", use_container_width=True, type="primary"):
            with st.spinner("Generating quiz..."):
                questions = st.session_state.agent_controller.generate_quiz(
                    difficulty, num_questions, adaptive
                )
                st.session_state.quizzes = questions
                st.session_state.quiz_answers = {}
                st.success(f"✅ Generated {len(questions)} questions!")
    
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
        with st.spinner("Creating revision plan..."):
            plan = st.session_state.agent_controller.create_revision_plan(
                exam_date.strftime('%Y-%m-%d') if exam_date else None,
                study_days
            )
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
    
    if not st.session_state.documents_processed:
        st.warning("Please process documents first!")
        return
    
    # Show latest document info
    if st.session_state.latest_document:
        st.info(f"📄 Prioritizing: **{st.session_state.latest_document}** (most recently uploaded)")
    
    # Chat history
    for i, (question, answer) in enumerate(st.session_state.chat_history):
        st.markdown(f"**Q:** {question}")
        st.markdown(f"**A:** {answer}")
        st.divider()
    
    # Question input
    question = st.text_input("Ask a question about your study materials:")
    if st.button("🔍 Ask", type="primary"):
        if question:
            with st.spinner("Thinking..."):
                # Use latest document for prioritization
                latest_doc = st.session_state.latest_document if st.session_state.latest_document else None
                result = st.session_state.agent_controller.answer_question(question, prioritize_source=latest_doc)
                st.session_state.chat_history.append((question, result['answer']))
                st.rerun()

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

