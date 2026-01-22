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
    page_title="Campus Compass",
    page_icon="🎓",
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
    """Wipe everything for a fresh start."""
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

# --- HELPER: DOCS SIGNATURE ---
def _compute_docs_signature(doc_files):
    if not doc_files:
        return None
    sig = []
    for d in sorted(doc_files, key=lambda x: x.name):
        try:
            stat = d.stat()
            sig.append(f"{d.name}_{stat.st_size}_{stat.st_mtime}")
        except:
            pass
    return "|".join(sig)

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
    st.session_state.last_processed_signature = None

# --- MODERN CLEAN CSS ---
st.markdown("""
<style>
    /* Global Font & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    :root {
        --primary-color: #4F46E5; /* Indigo-600 */
        --secondary-color: #6366F1; /* Indigo-500 */
        --bg-color: #F9FAFB; /* Gray-50 */
        --card-bg: #FFFFFF;
        --text-color: #111827; /* Gray-900 */
        --text-muted: #6B7280; /* Gray-500 */
        --border-color: #E5E7EB; /* Gray-200 */
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: var(--bg-color);
        color: var(--text-color);
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid var(--border-color);
    }

    /* Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: var(--text-color) !important;
        letter-spacing: -0.025em;
    }
    
    h1 { font-size: 2.25rem !important; }
    h2 { font-size: 1.875rem !important; }
    h3 { font-size: 1.5rem !important; }

    /* Modern Cards */
    .modern-card {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        margin-bottom: 1.5rem;
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    
    .modern-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
        transform: translateY(-2px);
    }
    
    /* Metrics */
    .metric-card {
        text-align: center;
        padding: 1rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--primary-color);
    }
    .metric-label {
        color: var(--text-muted);
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.5rem;
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06) !important;
        transition: all 0.2s !important;
    }

    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
    }

    /* Chat Bubbles */
    .chat-bubble {
        padding: 1rem 1.25rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        max-width: 85%;
        line-height: 1.5;
        font-size: 1rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
    
    .user-bubble {
        background-color: #EFF6FF; /* Blue-50 */
        color: #1E40AF; /* Blue-800 */
        margin-left: auto;
        border-bottom-right-radius: 4px;
        border: 1px solid #DBEAFE;
    }
    
    .assistant-bubble {
        background-color: #FFFFFF;
        color: var(--text-color);
        margin-right: auto;
        border-bottom-left-radius: 4px;
        border: 1px solid var(--border-color);
    }
    
    /* Custom Elements */
    .section-header {
        color: var(--primary-color);
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.875rem;
        margin-bottom: 1rem;
        letter-spacing: 0.05em;
    }

</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def process_documents():
    """Trigger the RAG pipeline."""
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
    
    # Update latest document
    if st.session_state.document_upload_order:
        st.session_state.latest_document = st.session_state.document_upload_order[-1]
    else:
        doc_files_with_time = [(Path(doc).stat().st_mtime, doc) for doc in doc_files if Path(doc).exists()]
        if doc_files_with_time:
            doc_files_with_time.sort(reverse=True)
            st.session_state.latest_document = Path(doc_files_with_time[0][1]).name
    
    # Processing UI
    processing_msg = st.info("Processing documents... Please wait.")
    try:
        result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
        processing_msg.empty()
        
        if result['total_chunks'] > 0:
            st.session_state.documents_processed = True
            latest_info = f" (Latest: {st.session_state.latest_document})" if st.session_state.latest_document else ""
            st.success(f"✅ Successfully processed {result['total_chunks']} chunks from {result['total_topics']} topics!{latest_info}")
            
            st.session_state.processing_results = result
            st.session_state.last_processed_signature = signature
            return True
        else:
            st.error("No content could be extracted from documents.")
            return False
            
    except Exception as e:
        st.error(f"Error processing documents: {e}")
        logger.exception("Processing failed")
        return False

# --- MAIN APP FLOW ---
def main():
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="padding: 1rem 0;">
            <h1 style="font-size: 1.5rem; margin: 0; color: #4F46E5;">🎓 Campus Compass</h1>
            <p style="color: #6B7280; font-size: 0.875rem; margin-top: 0.25rem;">Your AI Study Companion</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Navigation
        nav_options = {
            "Home": "🏠",
            "Flashcards": "📇",
            "Quizzes": "📝",
            "Revision Planner": "📅",
            "Chat Assistant": "💬",
            "Analytics": "📊"
        }
        
        st.markdown("<p style='font-size: 0.75rem; font-weight: 600; color: #9CA3AF; margin-bottom: 0.5rem; text-transform: uppercase;'>Menu</p>", unsafe_allow_html=True)
        
        for page_name, icon in nav_options.items():
            if st.button(f"{icon}  {page_name}", key=f"nav_{page_name}", use_container_width=True, type="primary" if st.session_state.current_page == page_name else "secondary"):
                st.session_state.current_page = page_name
                st.rerun()

        st.divider()
        
        # Upload Section
        st.markdown("<p style='font-size: 0.75rem; font-weight: 600; color: #9CA3AF; margin-bottom: 0.5rem; text-transform: uppercase;'>Library</p>", unsafe_allow_html=True)
        
        uploaded_files = st.file_uploader(
            "Upload Materials",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=True,
            key="sidebar_uploader",
            label_visibility="collapsed"
        )
        
        # Shared upload handling
        files_to_process = uploaded_files if uploaded_files else st.session_state.get('uploaded_files_shared')
        
        if files_to_process:
            st.info(f"{len(files_to_process)} file(s) selected")
            docs_dir = ensure_documents_directory()
            
            if st.button("Process Documents", use_container_width=True, type="primary", key="sidebar_process"):
                # Save files first
                saved_files = []
                for f in files_to_process:
                    file_path = docs_dir / f.name
                    with open(file_path, "wb") as pf:
                        pf.write(f.getbuffer())
                    saved_files.append(f.name)
                    
                    if f.name not in st.session_state.document_upload_order:
                        st.session_state.document_upload_order.append(f.name)
                
                if process_documents():
                    st.session_state.uploaded_files_shared = None
                    st.rerun()

        # Status
        doc_files = get_document_files()
        if doc_files:
            st.success(f"📚 {len(doc_files)} documents indexed")
        
        st.divider()
        st.caption("v2.0.0 • AI Powered")

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
    st.title("Welcome to Campus Compass")
    st.markdown("Your intelligent study partner. Upload documents to generate flashcards, quizzes, and revision plans automatically.")
    
    if not st.session_state.documents_processed:
        # Onboarding View
        st.info("👋 To get started, upload your study materials (PDF, DOCX, TXT) in the sidebar or below.")
        
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        uploaded_files = st.file_uploader("Upload Documents", type=['pdf', 'docx', 'doc', 'txt'], accept_multiple_files=True, key="home_uploader")
        
        if uploaded_files:
            st.session_state.uploaded_files_shared = uploaded_files
            if st.button("Start Processing", type="primary"):
                docs_dir = ensure_documents_directory()
                for f in uploaded_files:
                    file_path = docs_dir / f.name
                    with open(file_path, "wb") as pf:
                        pf.write(f.getbuffer())
                    if f.name not in st.session_state.document_upload_order:
                        st.session_state.document_upload_order.append(f.name)
                
                if process_documents():
                    st.session_state.uploaded_files_shared = None
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Features Grid
        st.markdown("### Why use Campus Compass?")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            **🧠 Smart Extraction**
            Automatically extracts key concepts, definitions, and topics from your lecture notes and textbooks.
            """)
        with c2:
            st.markdown("""
            **⚡ Active Recall**
            Generates intelligent flashcards and quizzes to help you memorize and understand faster.
            """)
        
    else:
        # Dashboard View
        st.markdown("### ⚡ Quick Access")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="modern-card" style="height: 100%;">', unsafe_allow_html=True)
            st.subheader("📇 Flashcards")
            st.caption("Review key concepts")
            if st.button("Open Flashcards", use_container_width=True):
                st.session_state.current_page = "Flashcards"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            st.markdown('<div class="modern-card" style="height: 100%;">', unsafe_allow_html=True)
            st.subheader("📝 Quizzes")
            st.caption("Test your knowledge")
            if st.button("Start Quiz", use_container_width=True):
                st.session_state.current_page = "Quizzes"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c3:
            st.markdown('<div class="modern-card" style="height: 100%;">', unsafe_allow_html=True)
            st.subheader("💬 AI Assistant")
            st.caption("Ask questions")
            if st.button("Chat Now", use_container_width=True):
                st.session_state.current_page = "Chat Assistant"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Recent Activity / Stats
        if 'processing_results' in st.session_state:
            result = st.session_state.processing_results
            st.markdown("### 📊 Overview")
            
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Topics Found", result['total_topics'])
            with sc2:
                st.metric("Knowledge Chunks", result['total_chunks'])
            with sc3:
                st.metric("Generated Cards", len(st.session_state.flashcards) if st.session_state.flashcards else 0)
            with sc4:
                st.metric("Quizzes Taken", len(st.session_state.quiz_answers) if st.session_state.quiz_answers else 0)

            # Topics Preview
            if result.get('topics'):
                with st.expander("📚 View Extracted Topics", expanded=True):
                    for topic in result['topics'][:5]:
                        st.markdown(f"**{topic.get('topic', 'General')}**")
                        for point in topic.get('key_points', [])[:2]:
                            st.markdown(f"- {point}")

def show_flashcards_page():
    st.title("📇 Flashcards")
    
    if not st.session_state.documents_processed:
        st.warning("Please upload and process documents first.")
        return

    # Configuration
    with st.expander("⚙️ Generator Settings", expanded=not bool(st.session_state.flashcards)):
        c1, c2 = st.columns(2)
        with c1:
            num_cards = st.slider("Number of cards", 5, 50, st.session_state.num_flashcards)
        with c2:
            difficulty = st.selectbox("Difficulty Mix", ["Easy + Medium", "Medium + Hard", "All Levels"])
            diff_map = {"Easy + Medium": "easy_medium", "Medium + Hard": "medium_hard", "All Levels": "easy_medium_hard"}
            
        if st.button("Generate Flashcards", type="primary"):
            with st.spinner("Generating flashcards..."):
                st.session_state.flashcards = st.session_state.agent_controller.generate_flashcards(
                    num_cards, 
                    difficulty_mix=diff_map[difficulty]
                )
                st.rerun()

    if st.session_state.flashcards:
        # Export
        csv = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button("📥 Export to Anki (CSV)", csv, "flashcards.csv", "text/csv")
        
        st.markdown("---")
        
        # Display Cards
        for i, card in enumerate(st.session_state.flashcards):
            st.markdown(f"""
            <div class="modern-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:1rem;">
                    <span style="background:#EEF2FF; color:#4F46E5; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:600;">Card #{i+1}</span>
                    <span style="color:#6B7280; font-size:0.8rem; text-transform:uppercase;">{card.get('difficulty', 'General')}</span>
                </div>
                <h3 style="margin-bottom:1rem;">{card['question']}</h3>
                <details>
                    <summary style="cursor:pointer; color:#4F46E5; font-weight:600;">Show Answer</summary>
                    <p style="margin-top:1rem; padding-left:1rem; border-left:3px solid #E5E7EB; color:#374151;">{card['answer']}</p>
                </details>
            </div>
            """, unsafe_allow_html=True)

def show_quizzes_page():
    st.title("📝 Quizzes")
    
    if not st.session_state.documents_processed:
        st.warning("Please upload and process documents first.")
        return

    with st.expander("⚙️ Quiz Settings", expanded=not bool(st.session_state.quizzes)):
        c1, c2 = st.columns(2)
        with c1:
            q_diff = st.selectbox("Difficulty", ["easy", "medium", "hard"])
        with c2:
            q_num = st.slider("Number of questions", 3, 20, 5)
            
        if st.button("Start New Quiz", type="primary"):
            with st.spinner("Creating quiz..."):
                st.session_state.quizzes = st.session_state.agent_controller.generate_quiz(q_diff, q_num)
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_result = None
                st.rerun()

    if st.session_state.quizzes:
        st.markdown(f"### Quiz ({len(st.session_state.quizzes)} questions)")
        
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"**{i+1}. {q['question']}**")
            
            selected = st.radio(
                f"Select answer for Q{i+1}",
                q['options'],
                key=f"q_{i}",
                label_visibility="collapsed"
            )
            
            # Save answer index
            if selected in q['options']:
                st.session_state.quiz_answers[i] = q['options'].index(selected)
            
            st.markdown("---")

        if not st.session_state.get('quiz_submitted'):
            if st.button("Submit Quiz", type="primary"):
                result = st.session_state.agent_controller.evaluate_quiz(
                    st.session_state.quizzes, 
                    st.session_state.quiz_answers
                )
                st.session_state.quiz_result = result
                st.session_state.quiz_submitted = True
                st.rerun()

        # Results
        if st.session_state.get('quiz_submitted') and st.session_state.quiz_result:
            res = st.session_state.quiz_result
            score = res['score']
            total = res['total']
            
            st.markdown(f"""
            <div class="modern-card" style="border-left: 5px solid {'#10B981' if score/total > 0.6 else '#EF4444'};">
                <h2>Score: {score}/{total} ({res['accuracy']*100:.0f}%)</h2>
                <p>{res.get('feedback', '')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.subheader("Review")
            for det in res['details']:
                color = "#10B981" if det['is_correct'] else "#EF4444"
                icon = "✅" if det['is_correct'] else "❌"
                
                with st.expander(f"{icon} Q{det['question_index']+1}: {det['question']}"):
                    st.markdown(f"""
                    - **Your Answer:** {det['user_answer']}
                    - **Correct Answer:** {det['correct_answer']}
                    - **Explanation:** {det['explanation']}
                    """)
            
            if st.button("Retake Quiz"):
                st.session_state.quizzes = []
                st.session_state.quiz_submitted = False
                st.rerun()

def show_planner_page():
    st.title("📅 Revision Planner")
    
    if not st.session_state.documents_processed:
        st.warning("Please upload and process documents first.")
        return

    c1, c2 = st.columns(2)
    with c1:
        exam_date = st.date_input("Exam Date")
    with c2:
        days = st.slider("Study Days per Week", 1, 7, 5)

    if st.button("Create Plan", type="primary"):
        with st.spinner("Generating schedule..."):
            st.session_state.agent_controller.create_revision_plan(
                exam_date.strftime('%Y-%m-%d') if exam_date else None, 
                days
            )
            st.rerun()

    # Display Plan
    plan = st.session_state.agent_controller.planner_agent.load_plan()
    if plan:
        st.markdown("### Your Schedule")
        for item in plan:
            status_icon = "⚪"
            if item.get('status') == 'completed': status_icon = "✅"
            if item.get('status') == 'in_progress': status_icon = "⏳"
            
            st.markdown(f"""
            <div class="modern-card" style="padding: 1rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-weight:bold; color:#4F46E5;">{item['date']}</span>
                        <h4 style="margin:0.25rem 0;">{item['topic']}</h4>
                    </div>
                    <div style="font-size:1.5rem;">{status_icon}</div>
                </div>
                <div style="margin-top:1rem; display:flex; gap:0.5rem;">
                    <button style="background:none; border:1px solid #E5E7EB; border-radius:4px; padding:4px 8px; cursor:pointer;">Start Study</button>
                    <button style="background:none; border:1px solid #E5E7EB; border-radius:4px; padding:4px 8px; cursor:pointer;">Mark Done</button>
                </div>
            </div>
            """, unsafe_allow_html=True)

def show_chat_page():
    st.title("💬 AI Assistant")
    
    if not st.session_state.documents_processed:
        st.warning("Please upload and process documents first.")
        return

    # Chat History
    for msg in st.session_state.chat_history:
        q = msg['question']
        a = msg['answer']
        
        st.markdown(f'<div class="chat-bubble user-bubble">{q}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble assistant-bubble">{a}</div>', unsafe_allow_html=True)

    # Input
    if prompt := st.chat_input("Ask a question about your documents..."):
        st.markdown(f'<div class="chat-bubble user-bubble">{prompt}</div>', unsafe_allow_html=True)
        
        with st.spinner("Thinking..."):
            res = st.session_state.agent_controller.answer_question(prompt)
            if res:
                answer = res['answer']
                st.markdown(f'<div class="chat-bubble assistant-bubble">{answer}</div>', unsafe_allow_html=True)
                
                st.session_state.chat_history.append({
                    'question': prompt,
                    'answer': answer,
                    'sources': res.get('sources', [])
                })
                st.rerun()

def show_analytics_page():
    st.title("📊 Analytics")
    
    if not st.session_state.agent_controller:
        st.warning("No data available.")
        return
        
    stats = st.session_state.agent_controller.get_statistics()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        st.subheader("Content Stats")
        st.write(f"**Topics:** {stats['total_topics']}")
        st.write(f"**Chunks:** {stats['total_chunks']}")
        st.write(f"**Flashcards:** {stats['total_flashcards']}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c2:
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        st.subheader("Performance")
        perf = stats.get('performance', {})
        st.write(f"**Quizzes Taken:** {perf.get('total_quizzes_taken', 0)}")
        st.write(f"**Average Score:** {perf.get('average_score', 0)*100:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
