"""
Campus Compass - Main Streamlit Application
The AI Oracle for Your College
"""

import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_pipeline import RAGPipeline
from alerts_manager import AlertsManager
from utils import ensure_documents_directory, get_document_files, format_sources

# Load .env file at the start - try multiple methods
def load_api_key():
    """Load API key from .env file or Streamlit secrets (supports Google API key)"""
    api_key = None
    
    # Method 1: Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and st.secrets:
            api_key = st.secrets.get("GOOGLE_API_KEY") or st.secrets.get("OPENAI_API_KEY")
            if api_key:
                os.environ['GOOGLE_API_KEY'] = api_key
                return api_key
    except Exception:
        pass
    
    # Method 2: Try environment variables (already set)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # Method 3: Try .env file (for local development)
    possible_paths = [
        Path(__file__).parent / '.env',  # Same directory as app.py
        Path('.env'),  # Current working directory
        Path.cwd() / '.env',  # Explicit current directory
    ]
    
    # Try load_dotenv
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            # Try Google API key first, then OpenAI for backward compatibility
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
            if api_key:
                break
    
    # Method 4: Read directly from file (most reliable fallback)
    if not api_key:
        for env_path in possible_paths:
            if env_path.exists():
                try:
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line_clean = line.strip()
                            # Check for Google API key first, then OpenAI
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

# Page configuration (must be first Streamlit command)
st.set_page_config(
    page_title="Campus Compass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load API key after Streamlit is initialized (so secrets are available)
load_api_key()

# Initialize session state
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
if 'rag_pipeline' not in st.session_state:
    st.session_state.rag_pipeline = None
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'alerts_manager' not in st.session_state:
    st.session_state.alerts_manager = AlertsManager()
if 'alerts_enabled' not in st.session_state:
    st.session_state.alerts_enabled = True


def initialize_components():
    """Initialize vector store and RAG pipeline"""
    # Reload API key to ensure it's available
    api_key = load_api_key()
    
    if st.session_state.vector_store is None:
        with st.spinner("Initializing vector store..."):
            st.session_state.vector_store = VectorStore()
    if st.session_state.rag_pipeline is None:
        with st.spinner("Initializing RAG pipeline..."):
            # Check API key before initializing
            if not api_key:
                st.error("⚠️ API key not found! Please check your .env file.")
                st.info("Make sure the .env file is in the same folder as app.py")
                st.info("Add either: GOOGLE_API_KEY=your_key or OPENAI_API_KEY=your_key")
                st.stop()
            st.session_state.rag_pipeline = RAGPipeline(st.session_state.vector_store)


def process_documents():
    """Process all documents in the documents directory"""
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    
    if not doc_files:
        st.error("No documents found in the 'documents' folder. Please add PDF, DOCX, or TXT files.")
        return False
    
    with st.spinner(f"Processing {len(doc_files)} document(s)..."):
        processor = DocumentProcessor()
        all_chunks = processor.process_directory(str(docs_dir))
        
        if not all_chunks:
            st.error("No text could be extracted from the documents.")
            return False
        
        # Clear existing data and add new chunks
        st.session_state.vector_store.clear_collection()
        st.session_state.vector_store.add_documents(all_chunks)
        
        # Extract deadlines from documents for alerts
        try:
            st.session_state.alerts_manager.add_deadlines_from_documents(all_chunks)
        except Exception as e:
            st.warning(f"Could not extract deadlines: {e}")
        
        st.session_state.documents_processed = True
        st.success(f"✅ Successfully processed {len(all_chunks)} chunks from {len(doc_files)} document(s)!")
        return True


def main():
    """Main application"""
    # Header
    st.title("🧭 Campus Compass")
    st.markdown("### The AI Oracle for Your College")
    st.markdown("Ask any question about college policies, rules, and information. Get accurate answers with source citations.")
    
    # Sidebar
    with st.sidebar:
        # Check for API key (silently, only show error if missing)
        api_key = load_api_key() or os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("⚠️ API key not found! Please configure your API key in the .env file.")
            st.stop()
        
        # Document processing section
        st.subheader("📚 Document Management")
        
        # File uploader for new documents
        st.markdown("### 📤 Upload Documents")
        uploaded_file = st.file_uploader(
            "Upload college document (PDF, DOCX, or TXT)",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=False,
            help="Upload a single document. Previous documents will be automatically deleted."
        )
        
        if uploaded_file:
            if st.button("💾 Save Uploaded Document", type="primary", use_container_width=True):
                docs_dir = ensure_documents_directory()
                
                with st.spinner("Saving document..."):
                    try:
                        # Delete all existing documents first
                        existing_docs = get_document_files()
                        deleted_count = 0
                        for doc_path in existing_docs:
                            try:
                                Path(doc_path).unlink()
                                deleted_count += 1
                            except Exception as e:
                                st.warning(f"Could not delete {Path(doc_path).name}: {e}")
                        
                        # Determine file extension
                        file_ext = Path(uploaded_file.name).suffix.lower()
                        if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
                            st.error(f"Unsupported format: {file_ext}. Please upload PDF, DOCX, or TXT files.")
                        else:
                            # Save new file
                            file_path = docs_dir / uploaded_file.name
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            # Clear vector store and reset processing status
                            if st.session_state.vector_store:
                                st.session_state.vector_store.clear_collection()
                            st.session_state.documents_processed = False
                            st.session_state.chat_history = []
                            st.session_state.alerts_manager.clear_deadlines()
                            
                            if deleted_count > 0:
                                st.success(f"✅ Replaced {deleted_count} old document(s) with '{uploaded_file.name}'")
                            else:
                                st.success(f"✅ Saved '{uploaded_file.name}' to documents folder!")
                            st.info("Click 'Process Documents' below to index it.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error saving {uploaded_file.name}: {str(e)}")
        
        st.divider()
        
        # Show existing documents
        st.markdown("### 📁 Existing Documents")
        doc_files = get_document_files()
        st.info(f"Found {len(doc_files)} document(s) in 'documents/' folder")
        
        if doc_files:
            with st.expander("View Documents"):
                for idx, doc in enumerate(doc_files):
                    doc_path = Path(doc)
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.text(doc_path.name)
                    with col2:
                        # Use full path hash or index to ensure unique key
                        unique_key = f"delete_{hash(str(doc_path))}_{idx}"
                        if st.button("🗑️", key=unique_key, help="Delete this document"):
                            try:
                                doc_path.unlink()
                                st.success(f"Deleted {doc_path.name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting: {e}")
        
        st.divider()
        
        # Process documents button
        if st.button("🔄 Process Documents", type="primary", use_container_width=True):
            initialize_components()
            if process_documents():
                st.session_state.chat_history = []  # Clear chat history
        
        # Show vector store status
        if st.session_state.vector_store:
            count = st.session_state.vector_store.get_collection_count()
            st.metric("Indexed Chunks", count)
        
        st.divider()
        
        # Personalized Alerts Section
        st.subheader("🔔 Personalized Alerts")
        
        # Opt-in toggle
        alerts_enabled = st.checkbox(
            "Enable Alerts & Reminders",
            value=st.session_state.alerts_enabled,
            help="Get reminders for deadlines, fee payments, and important dates"
        )
        st.session_state.alerts_enabled = alerts_enabled
        st.session_state.alerts_manager.opt_in_user("default", alerts_enabled)
        
        # Show upcoming alerts
        if alerts_enabled:
            upcoming = st.session_state.alerts_manager.get_upcoming_deadlines(days_ahead=30)
            if upcoming:
                st.info(f"📅 {len(upcoming)} upcoming deadline(s) in the next 30 days")
                with st.expander("View Upcoming Deadlines"):
                    for alert in upcoming[:10]:  # Show top 10
                        days = alert.get('days_until', 0)
                        date_str = alert.get('date', '')
                        event = alert.get('event', 'Deadline')
                        source = alert.get('source', 'Unknown')
                        
                        # Format date
                        try:
                            from datetime import datetime as dt
                            date_obj = dt.fromisoformat(date_str)
                            date_formatted = date_obj.strftime("%B %d, %Y")
                        except:
                            date_formatted = date_str
                        
                        # Color code by urgency
                        if days <= 7:
                            st.warning(f"⚠️ **{date_formatted}** ({days} days) - {event}")
                        elif days <= 14:
                            st.info(f"📌 **{date_formatted}** ({days} days) - {event}")
                        else:
                            st.text(f"📅 **{date_formatted}** ({days} days) - {event}")
                        
                        st.caption(f"Source: {source}")
                        st.divider()
            else:
                st.info("No upcoming deadlines found. Process documents with calendar information to see alerts.")
        else:
            st.caption("Alerts are disabled. Enable above to see reminders.")
        
        st.divider()
        
        # Clear data button
        if st.button("🗑️ Clear All Data", use_container_width=True):
            if st.session_state.vector_store:
                st.session_state.vector_store.clear_collection()
                st.session_state.documents_processed = False
                st.session_state.chat_history = []
                st.session_state.alerts_manager.clear_deadlines()
                st.success("Data cleared!")
                st.rerun()
        
        st.divider()
        
        # Instructions
        with st.expander("📖 How to Use"):
            st.markdown("""
            **For New Users:**
            1. **Upload Document**: Use the file uploader above to add your college document
            2. **Save Document**: Click "Save Uploaded Document" (this will replace any previous documents)
            3. **Process**: Click "Process Documents" to index it
            4. **Ask Questions**: Type your question in the chat below
            5. **Get Answers**: Receive accurate answers with source citations
            
            **Note**: Uploading a new document automatically deletes previous documents to keep your knowledge base clean.
            
            **Alternative**: You can also manually place PDF, DOCX, or TXT files in the `documents/` folder
            
            **Bonus Features**:
            - Use "Multi-Document" mode for complex questions
            - Use "Summarize" for policy summaries
            - **Enable Alerts** to get reminders for deadlines and important dates
            - Delete individual documents using the 🗑️ button
            """)
    
    # Initialize components
    initialize_components()
    
    # Check if documents are processed
    if not st.session_state.documents_processed:
        if st.session_state.vector_store:
            count = st.session_state.vector_store.get_collection_count()
            if count > 0:
                st.session_state.documents_processed = True
            else:
                st.info("👆 Please process documents using the sidebar before asking questions.")
                return
    
    # Show alerts banner if enabled and there are urgent deadlines
    if st.session_state.alerts_enabled:
        upcoming = st.session_state.alerts_manager.get_upcoming_deadlines(days_ahead=7)
        urgent = [a for a in upcoming if a.get('days_until', 999) <= 7]
        if urgent:
            st.warning(f"🔔 **Urgent Alert:** {len(urgent)} deadline(s) in the next 7 days! Check the sidebar for details.")
    
    # Main chat interface
    st.divider()
    st.subheader("💬 Ask Your Question")
    
    # Question type selector
    col1, col2, col3 = st.columns(3)
    with col1:
        question_mode = st.radio(
            "Question Mode",
            ["Standard", "Multi-Document", "Summarize"],
            horizontal=True,
            help="Standard: Single answer (with general info if needed)\nMulti-Document: Synthesize from multiple sources\nSummarize: Bulleted summary"
        )
    
    # Chat history display
    if st.session_state.chat_history:
        st.subheader("📜 Chat History")
        for i, (question, answer, sources) in enumerate(st.session_state.chat_history):
            with st.expander(f"Q: {question}", expanded=False):
                st.markdown(f"**Answer:**\n{answer}")
                if sources:
                    st.caption(f"📎 {format_sources(sources)}")
        st.divider()
    
    # Question input
    question = st.text_input(
        "Enter your question:",
        placeholder="e.g., What's the fine for a late library book?",
        key="question_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)
    
    # Process question
    if ask_button and question:
        if not st.session_state.rag_pipeline:
            st.error("RAG pipeline not initialized. Please process documents first.")
            return
        
        with st.spinner("Searching documents and generating answer..."):
            # Select appropriate method based on mode (allow_general=True by default)
            if question_mode == "Multi-Document":
                result = st.session_state.rag_pipeline.answer_multi_document_question(question, n_chunks=8, allow_general=True)
            elif question_mode == "Summarize":
                result = st.session_state.rag_pipeline.answer_question(question, n_chunks=5, summarize=True, allow_general=True)
            else:
                result = st.session_state.rag_pipeline.answer_question(question, n_chunks=5, allow_general=True)
            
            # Display answer
            st.markdown("### 💡 Answer")
            st.markdown(result['answer'])
            
            # Display sources
            if result['sources']:
                st.markdown("### 📎 Sources")
                for source in result['sources']:
                    st.caption(f"• {source}")
            
            # Add to chat history
            st.session_state.chat_history.append((
                question,
                result['answer'],
                result['sources']
            ))
            
            # Show retrieved chunks (expandable)
            with st.expander("🔍 View Retrieved Context"):
                for i, chunk in enumerate(result['chunks'][:3], 1):  # Show top 3
                    st.markdown(f"**Chunk {i}** (from {chunk['metadata'].get('source', 'Unknown')}):")
                    st.text(chunk['text'][:300] + "..." if len(chunk['text']) > 300 else chunk['text'])
                    st.caption(f"Distance: {chunk.get('distance', 'N/A'):.4f}" if chunk.get('distance') else "")
    
    # Footer
    st.divider()
    st.caption("Campus Compass - Built with RAG (Retrieval-Augmented Generation) | Powered by OpenAI & ChromaDB")


if __name__ == "__main__":
    main()

