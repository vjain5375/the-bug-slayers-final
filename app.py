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
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    :root {
        --primary-color: #6366f1; /* Indigo */
        --primary-hover: #4f46e5;
        --bg-color: #f8fafc;
        --card-bg: #ffffff;
        --text-primary: #0f172a;
        --text-secondary: #64748b;
        --border-color: #e2e8f0;
        --gradient-primary: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: var(--bg-color);
        color: var(--text-primary);
    }

    /* Gradient Background for App */
    .stApp {
        background-color: var(--bg-color);
        background-image: 
            radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%), 
            radial-gradient(at 50% 0%, hsla(225,39%,30%,1) 0, transparent 50%), 
            radial-gradient(at 100% 0%, hsla(339,49%,30%,1) 0, transparent 50%);
        background-attachment: fixed;
        background-size: cover;
    }
    
    /* Light Mode Override for Background */
    @media (prefers-color-scheme: light) {
        .stApp {
            background-color: #f8fafc;
            background-image: none;
        }
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: var(--card-bg);
        border-right: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
    }

    /* Typography */
    h1, h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.025em;
    }
    
    h1 { background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5rem !important; margin-bottom: 1rem !important; }
    
    /* Modern Cards */
    .modern-card {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .modern-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 4px;
        background: var(--gradient-primary);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .modern-card:hover {
        transform: translateY(-5px);
        box-shadow: var(--shadow-lg);
    }
    
    .modern-card:hover::before {
        opacity: 1;
    }
    
    /* Flashcard Style */
    .flashcard {
        background: white;
        border-radius: 16px;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-color);
        padding: 2rem;
        text-align: center;
        transition: transform 0.6s;
        transform-style: preserve-3d;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    /* Buttons */
    div.stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s !important;
    }
    
    div.stButton > button[kind="primary"] {
        background: var(--gradient-primary) !important;
        color: white !important;
        box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.4);
    }

    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.1) !important;
    }

    /* Chat Bubbles */
    .chat-bubble {
        padding: 1rem 1.5rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        max-width: 80%;
        line-height: 1.6;
        font-size: 0.95rem;
        position: relative;
    }
    
    .user-bubble {
        background: var(--gradient-primary);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        box-shadow: var(--shadow-md);
    }
    
    .assistant-bubble {
        background: white;
        color: var(--text-primary);
        margin-right: auto;
        border-bottom-left-radius: 4px;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
    }
    
    /* Custom Elements */
    .hero-section {
        text-align: center;
        padding: 3rem 1rem;
        margin-bottom: 2rem;
    }
    
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--primary-color);
        color: white;
        font-weight: bold;
        margin-right: 0.5rem;
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
        st.toast("Documents unchanged. Skipping reprocessing.", icon="ℹ️")
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
    with st.spinner("🚀 Analyzing documents and extracting knowledge..."):
        try:
            result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
            
            if result['total_chunks'] > 0:
                st.session_state.documents_processed = True
                st.toast(f"Success! Processed {result['total_chunks']} chunks.", icon="✅")
                
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
        <div style="padding: 1rem 0; text-align: center;">
            <div style="width: 60px; height: 60px; background: linear-gradient(135deg, #6366f1, #a855f7); border-radius: 12px; margin: 0 auto 1rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 30px;">🎓</div>
            <h2 style="font-size: 1.25rem; margin: 0; color: #1e293b;">Campus Compass</h2>
            <p style="color: #64748b; font-size: 0.8rem;">AI-Powered Study Assistant</p>
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
        
        st.markdown("<p style='font-size: 0.75rem; font-weight: 700; color: #94a3b8; margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;'>Navigation</p>", unsafe_allow_html=True)
        
        for page_name, icon in nav_options.items():
            if st.button(f"{icon}  {page_name}", key=f"nav_{page_name}", use_container_width=True, type="primary" if st.session_state.current_page == page_name else "secondary"):
                st.session_state.current_page = page_name
                st.rerun()

        st.divider()
        
        # Upload Section
        st.markdown("<p style='font-size: 0.75rem; font-weight: 700; color: #94a3b8; margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;'>Your Library</p>", unsafe_allow_html=True)
        
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
            st.info(f"📄 {len(files_to_process)} file(s) pending")
            docs_dir = ensure_documents_directory()
            
            if st.button("🚀 Process Now", use_container_width=True, type="primary", key="sidebar_process"):
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
            st.markdown(f"""
            <div style="background: #f1f5f9; padding: 0.75rem; border-radius: 8px; margin-top: 1rem; font-size: 0.85rem; color: #475569;">
                📚 <b>{len(doc_files)}</b> documents indexed
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: auto; padding-top: 2rem; text-align: center; font-size: 0.75rem; color: #cbd5e1;'>v2.0 • Campus Compass</div>", unsafe_allow_html=True)

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
    # Hero Section
    st.markdown("""
    <div class="hero-section">
        <h1>Welcome to Campus Compass</h1>
        <p style="font-size: 1.25rem; color: #64748b; max-width: 600px; margin: 0 auto;">
            Transform your study materials into interactive learning experiences.
            Upload your notes and let AI create flashcards, quizzes, and revision plans.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.documents_processed:
        # Onboarding View
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("""
            <div class="modern-card" style="text-align: center;">
                <h3 style="margin-bottom: 1rem;">🚀 Get Started</h3>
                <p style="color: #64748b; margin-bottom: 1.5rem;">Upload your PDFs, DOCX, or TXT files to begin.</p>
            </div>
            """, unsafe_allow_html=True)
            
            uploaded_files = st.file_uploader("Upload Documents", type=['pdf', 'docx', 'doc', 'txt'], accept_multiple_files=True, key="home_uploader")
            
            if uploaded_files:
                st.session_state.uploaded_files_shared = uploaded_files
                if st.button("✨ Start Processing", type="primary", use_container_width=True):
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
        
        # Features Grid
        st.markdown("### ✨ Features")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            <div class="modern-card">
                <h3>🧠 Smart Extraction</h3>
                <p style="color: #64748b;">Automatically identifies key topics and concepts from your documents using advanced NLP.</p>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
            <div class="modern-card">
                <h3>⚡ Active Recall</h3>
                <p style="color: #64748b;">Generates tailored flashcards and quizzes to boost memory retention and understanding.</p>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown("""
            <div class="modern-card">
                <h3>📅 Study Planning</h3>
                <p style="color: #64748b;">Creates personalized revision schedules based on your exam dates and content volume.</p>
            </div>
            """, unsafe_allow_html=True)
        
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
            st.markdown("### 📊 Your Content")
            
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.markdown(f"""<div class="modern-card" style="text-align: center; padding: 1rem;"><h2 style="margin:0; color: #6366f1;">{result['total_topics']}</h2><p style="margin:0; color:#64748b; font-size:0.9rem;">Topics</p></div>""", unsafe_allow_html=True)
            with sc2:
                st.markdown(f"""<div class="modern-card" style="text-align: center; padding: 1rem;"><h2 style="margin:0; color: #8b5cf6;">{result['total_chunks']}</h2><p style="margin:0; color:#64748b; font-size:0.9rem;">Chunks</p></div>""", unsafe_allow_html=True)
            with sc3:
                fc_count = len(st.session_state.flashcards) if st.session_state.flashcards else 0
                st.markdown(f"""<div class="modern-card" style="text-align: center; padding: 1rem;"><h2 style="margin:0; color: #ec4899;">{fc_count}</h2><p style="margin:0; color:#64748b; font-size:0.9rem;">Cards</p></div>""", unsafe_allow_html=True)
            with sc4:
                qz_count = len(st.session_state.quiz_answers) if st.session_state.quiz_answers else 0
                st.markdown(f"""<div class="modern-card" style="text-align: center; padding: 1rem;"><h2 style="margin:0; color: #10b981;">{qz_count}</h2><p style="margin:0; color:#64748b; font-size:0.9rem;">Quizzes</p></div>""", unsafe_allow_html=True)

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
            
        if st.button("✨ Generate Flashcards", type="primary"):
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
                    <span style="background:#EEF2FF; color:#4F46E5; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">Card #{i+1}</span>
                    <span style="color:#94a3b8; font-size:0.75rem; font-weight:600; text-transform:uppercase;">{card.get('difficulty', 'General')}</span>
                </div>
                <h3 style="margin-bottom:1.5rem; color:#1e293b; font-size:1.25rem;">{card['question']}</h3>
                <details>
                    <summary style="cursor:pointer; color:#6366f1; font-weight:600; padding: 0.5rem 0;">Reveal Answer</summary>
                    <div style="margin-top:1rem; padding:1rem; background:#f8fafc; border-radius:8px; color:#334155; line-height:1.6;">
                        {card['answer']}
                    </div>
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
            
        if st.button("✨ Start New Quiz", type="primary"):
            with st.spinner("Creating quiz..."):
                st.session_state.quizzes = st.session_state.agent_controller.generate_quiz(q_diff, q_num)
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_result = None
                st.rerun()

    if st.session_state.quizzes:
        st.markdown(f"### Quiz ({len(st.session_state.quizzes)} questions)")
        
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"""
            <div class="modern-card" style="padding: 1.5rem;">
                <h4 style="margin-top:0;">{i+1}. {q['question']}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            selected = st.radio(
                f"Select answer for Q{i+1}",
                q['options'],
                key=f"q_{i}",
                label_visibility="collapsed"
            )
            
            # Save answer index
            if selected in q['options']:
                st.session_state.quiz_answers[i] = q['options'].index(selected)
            
            st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

        if not st.session_state.get('quiz_submitted'):
            if st.button("🚀 Submit Quiz", type="primary"):
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
            percent = res['accuracy']*100
            
            color = "#10B981" if percent > 60 else "#EF4444"
            
            st.markdown(f"""
            <div class="modern-card" style="border-left: 5px solid {color}; background: #f8fafc;">
                <h2 style="color: {color}; margin-bottom: 0.5rem;">Score: {score}/{total} ({percent:.0f}%)</h2>
                <p style="font-size: 1.1rem;">{res.get('feedback', '')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.subheader("Detailed Review")
            for det in res['details']:
                is_correct = det['is_correct']
                icon = "✅" if is_correct else "❌"
                border_col = "#10B981" if is_correct else "#EF4444"
                
                with st.expander(f"{icon} Q{det['question_index']+1}: {det['question']}"):
                    st.markdown(f"""
                    <div style="border-left: 3px solid {border_col}; padding-left: 1rem;">
                        <p><b>Your Answer:</b> {det['user_answer']}</p>
                        <p><b>Correct Answer:</b> {det['correct_answer']}</p>
                        <p style="color: #64748b; margin-top: 0.5rem;"><i>{det['explanation']}</i></p>
                    </div>
                    """, unsafe_allow_html=True)
            
            if st.button("🔄 Retake Quiz"):
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

    if st.button("✨ Create Plan", type="primary"):
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
            <div class="modern-card" style="padding: 1.25rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-weight:600; color:#6366f1; font-size: 0.9rem; text-transform: uppercase;">{item['date']}</span>
                        <h4 style="margin:0.25rem 0; font-size: 1.1rem;">{item['topic']}</h4>
                    </div>
                    <div style="font-size:1.5rem;">{status_icon}</div>
                </div>
                <div style="margin-top:1rem; display:flex; gap:0.5rem;">
                    <button style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:6px 12px; cursor:pointer; color: #475569; font-size: 0.85rem;">Start Study</button>
                    <button style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:6px 12px; cursor:pointer; color: #475569; font-size: 0.85rem;">Mark Done</button>
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
