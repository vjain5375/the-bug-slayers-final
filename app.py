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
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DIRECTORY SETUP ---
def ensure_documents_directory():
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    return docs_dir

def get_document_files():
    docs_dir = ensure_documents_directory()
    return list(docs_dir.glob("*"))

# --- CLEANUP LOGIC ---
def cleanup_session():
    """Wipe everything for a fresh start."""
    docs_dir = Path("documents")
    if docs_dir.exists():
        for f in docs_dir.glob("*"):
            try: f.unlink()
            except: pass
    
    outputs_dir = Path("outputs")
    if outputs_dir.exists():
        for f in outputs_dir.glob("*"):
            try: f.unlink()
            except: pass
            
    if 'vector_store' in st.session_state and st.session_state.vector_store:
        try:
            st.session_state.vector_store.client.delete_collection("campus_compass")
            st.session_state.vector_store = VectorStore() 
        except Exception:
            try: st.session_state.vector_store = VectorStore()
            except: pass

# --- HELPER: DOCS SIGNATURE ---
def _compute_docs_signature(doc_files):
    if not doc_files: return None
    sig = []
    for d in sorted(doc_files, key=lambda x: x.name):
        try:
            stat = d.stat()
            sig.append(f"{d.name}_{stat.st_size}_{stat.st_mtime}")
        except: pass
    return "|".join(sig)

# --- SESSION STATE INITIALIZATION ---
if 'initialized' not in st.session_state:
    cleanup_session()
    st.session_state.initialized = True
    st.session_state.current_page = "Home"
    st.session_state.vector_store = VectorStore()
    try:
        if st.session_state.vector_store.collection:
            all_ids = st.session_state.vector_store.collection.get()['ids']
            if all_ids: st.session_state.vector_store.collection.delete(ids=all_ids)
    except: pass
    
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
    st.session_state.last_processed_signature = None

# --- PREMIUM UI/UX CSS ---
st.markdown("""
<style>
    /* 1. TYPOGRAPHY & RESET */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');
    
    :root {
        --bg-deep: #0B0F1A;
        --bg-card: #111827;
        --bg-card-hover: #1F2937;
        --accent-primary: #3B82F6; /* Electric Blue */
        --accent-glow: #22D3EE; /* Cyan */
        --text-primary: #F3F4F6;
        --text-secondary: #9CA3AF;
        --border-glass: rgba(255, 255, 255, 0.08);
        --shadow-glow: 0 0 20px rgba(59, 130, 246, 0.15);
        --success: #10B981;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: var(--text-primary);
        background-color: var(--bg-deep);
    }

    /* 2. BACKGROUND & APP CONTAINER */
    .stApp {
        background-color: var(--bg-deep);
        background-image: 
            radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(34, 211, 238, 0.08) 0%, transparent 40%);
        background-attachment: fixed;
    }

    /* 3. SIDEBAR (Floating Glass) */
    section[data-testid="stSidebar"] {
        background: rgba(17, 24, 39, 0.7);
        backdrop-filter: blur(12px);
        border-right: 1px solid var(--border-glass);
        box-shadow: 10px 0 30px rgba(0,0,0,0.3);
    }
    
    div[data-testid="stSidebarNav"] {
        padding-top: 1rem;
    }

    /* 4. HEADERS */
    h1 {
        background: linear-gradient(135deg, #FFF 0%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -0.03em;
        font-size: 3.5rem !important;
        margin-bottom: 0.5rem !important;
    }

    h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    /* 5. MODERN CARDS */
    .feature-card {
        background: var(--bg-card);
        border: 1px solid var(--border-glass);
        border-radius: 16px;
        padding: 1.5rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .feature-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: var(--shadow-glow);
        border-color: rgba(59, 130, 246, 0.3);
        background: var(--bg-card-hover);
    }

    .feature-card:hover::before {
        opacity: 1;
    }

    /* 6. BUTTONS (Glowing & Interactive) */
    div.stButton > button {
        background: rgba(59, 130, 246, 0.1) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        color: var(--accent-primary) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }

    div.stButton > button:hover {
        background: var(--accent-primary) !important;
        color: white !important;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.4) !important;
        transform: scale(1.02);
        border-color: var(--accent-primary) !important;
    }
    
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-primary) 0%, #2563EB 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
    }

    /* 7. UPLOAD ZONE */
    div[data-testid="stFileUploader"] {
        background: rgba(255,255,255,0.02);
        border: 2px dashed var(--border-glass);
        border-radius: 16px;
        padding: 2rem;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stFileUploader"]:hover {
        border-color: var(--accent-primary);
        background: rgba(59, 130, 246, 0.05);
    }
    
    div[data-testid="stFileUploader"] label {
        color: var(--text-secondary) !important;
        font-family: 'Plus Jakarta Sans';
    }

    /* 8. CHAT BUBBLES */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    
    .chat-bubble {
        max-width: 80%;
        padding: 1rem 1.25rem;
        border-radius: 16px;
        font-size: 0.95rem;
        line-height: 1.6;
        position: relative;
    }
    
    .user-bubble {
        align-self: flex-end;
        background: linear-gradient(135deg, var(--accent-primary), #2563EB);
        color: white;
        border-bottom-right-radius: 4px;
        margin-left: auto;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    
    .ai-bubble {
        align-self: flex-start;
        background: var(--bg-card);
        border: 1px solid var(--border-glass);
        color: var(--text-primary);
        border-bottom-left-radius: 4px;
        margin-right: auto;
    }

    /* 9. METRICS */
    div[data-testid="stMetricValue"] {
        background: linear-gradient(135deg, #FFF 0%, #9CA3AF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem !important;
        font-weight: 700 !important;
    }
    
    div[data-testid="stMetricLabel"] {
        color: var(--accent-glow) !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 0.05em;
    }

    /* 10. TOAST */
    div[data-testid="stToast"] {
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: 12px !important;
    }
    
    /* UTILS */
    .hero-sub {
        color: var(--text-secondary);
        font-size: 1.2rem;
        font-weight: 400;
        max-width: 600px;
        margin: 0 auto 2rem auto;
        line-height: 1.6;
    }
    
    .glass-panel {
        background: rgba(17, 24, 39, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid var(--border-glass);
        border-radius: 20px;
        padding: 2rem;
    }

</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def process_documents():
    """Trigger the RAG pipeline."""
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    
    if not doc_files:
        st.toast("⚠️ Please upload documents first.", icon="📂")
        return False
    
    signature = _compute_docs_signature(doc_files)
    if (
        signature
        and st.session_state.documents_processed
        and st.session_state.get('processing_results')
        and st.session_state.get('last_processed_signature') == signature
    ):
        st.toast("⚡ Documents are already up to date.", icon="✨")
        return True
    
    if st.session_state.document_upload_order:
        st.session_state.latest_document = st.session_state.document_upload_order[-1]
    
    with st.status("🧠 Analyzing knowledge base...", expanded=True) as status:
        try:
            st.write("Extracting semantic concepts...")
            time.sleep(0.5)
            st.write("Generating neural embeddings...")
            
            result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
            
            if result['total_chunks'] > 0:
                st.session_state.documents_processed = True
                status.update(label="✅ Knowledge Base Updated!", state="complete", expanded=False)
                st.toast(f"Ready! Processed {result['total_topics']} topics.", icon="🚀")
                
                st.session_state.processing_results = result
                st.session_state.last_processed_signature = signature
                return True
            else:
                status.update(label="❌ Extraction Failed", state="error")
                return False
                
        except Exception as e:
            status.update(label="❌ Error", state="error")
            st.error(f"Processing failed: {e}")
            return False

# --- MAIN APP ---
def main():
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <div style="
                width: 60px; height: 60px; 
                background: linear-gradient(135deg, #3B82F6, #22D3EE); 
                border-radius: 16px; 
                margin: 0 auto 1rem; 
                display: flex; align-items: center; justify-content: center;
                box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
            ">
                <span style="font-size: 30px;">🧭</span>
            </div>
            <h2 style="font-size: 1.5rem; margin: 0; background: linear-gradient(to right, #fff, #9ca3af); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Campus Compass</h2>
            <p style="color: #6B7280; font-size: 0.85rem; letter-spacing: 0.05em; font-weight: 500;">AI STUDY COMPANION</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        pages = {
            "Home": "🏠",
            "Flashcards": "⚡",
            "Quizzes": "📝",
            "Revision Planner": "📅",
            "Chat Assistant": "💬",
            "Analytics": "📊"
        }
        
        st.markdown("<div style='display: flex; flex-direction: column; gap: 0.5rem;'>", unsafe_allow_html=True)
        for page, icon in pages.items():
            # Active state logic handling for button styles
            is_active = st.session_state.current_page == page
            if st.button(f"{icon} {page}", key=f"nav_{page}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state.current_page = page
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Mini Upload (Quick Add)
        if st.session_state.documents_processed:
            st.caption("QUICK ADD")
            uploaded_files = st.file_uploader("", type=['pdf', 'docx', 'txt'], accept_multiple_files=True, key="mini_uploader", label_visibility="collapsed")
            if uploaded_files:
                st.session_state.uploaded_files_shared = uploaded_files
                if st.button("Process New", use_container_width=True):
                    process_and_rerun(uploaded_files)

    # --- ROUTING ---
    if st.session_state.current_page == "Home":
        render_home()
    elif st.session_state.current_page == "Flashcards":
        render_flashcards()
    elif st.session_state.current_page == "Quizzes":
        render_quizzes()
    elif st.session_state.current_page == "Revision Planner":
        render_planner()
    elif st.session_state.current_page == "Chat Assistant":
        render_chat()
    elif st.session_state.current_page == "Analytics":
        render_analytics()

def process_and_rerun(files):
    docs_dir = ensure_documents_directory()
    for f in files:
        with open(docs_dir / f.name, "wb") as pf:
            pf.write(f.getbuffer())
        if f.name not in st.session_state.document_upload_order:
            st.session_state.document_upload_order.append(f.name)
    
    if process_documents():
        st.session_state.uploaded_files_shared = None
        st.rerun()

# --- PAGE: HOME ---
def render_home():
    # HERO SECTION
    st.markdown("""
    <div style="text-align: center; padding: 4rem 0;">
        <h1>Study smarter.<br>Revise faster. Stress less.</h1>
        <p class="hero-sub">
            Stop drowning in PDFs. Turn your lecture notes into interactive flashcards, 
            adaptive quizzes, and personalized revision plans in seconds.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ONBOARDING / UPLOAD
    if not st.session_state.documents_processed:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("""
            <div class="glass-panel" style="text-align: center; border: 1px dashed var(--accent-primary);">
                <div style="font-size: 3rem; margin-bottom: 1rem;">📂</div>
                <h3 style="margin-bottom: 0.5rem;">Drop your brain dump here</h3>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem;">
                    Supports PDF, DOCX, TXT. Max 200MB.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            uploaded_files = st.file_uploader("Upload Documents", type=['pdf', 'docx', 'doc', 'txt'], accept_multiple_files=True, key="home_uploader", label_visibility="collapsed")
            
            if uploaded_files:
                if st.button("🚀 Ignite Engine", type="primary", use_container_width=True):
                    process_and_rerun(uploaded_files)
    
    else:
        # DASHBOARD GRID
        st.markdown("<h3 style='margin-bottom: 1.5rem;'>Your Command Center</h3>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("""
            <div class="feature-card">
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem;">⚡</div>
                    <h3>Flashcards</h3>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">
                        Active recall engine. Convert notes into bite-sized memory cards.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Flashcards", key="btn_flash", use_container_width=True):
                st.session_state.current_page = "Flashcards"
                st.rerun()
                
        with c2:
            st.markdown("""
            <div class="feature-card">
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem;">📝</div>
                    <h3>Quizzes</h3>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">
                        Test your knowledge. Adaptive difficulty based on your performance.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Start Quiz", key="btn_quiz", use_container_width=True):
                st.session_state.current_page = "Quizzes"
                st.rerun()

        with c3:
            st.markdown("""
            <div class="feature-card">
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem;">💬</div>
                    <h3>AI Assistant</h3>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">
                        Chat with your notes. Ask for summaries, explanations, or examples.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Start Chat", key="btn_chat", use_container_width=True):
                st.session_state.current_page = "Chat Assistant"
                st.rerun()

        # METRICS ROW
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        if 'processing_results' in st.session_state:
            res = st.session_state.processing_results
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Knowledge Chunks", res['total_chunks'])
            with c2: st.metric("Topics Found", res['total_topics'])
            with c3: st.metric("Cards Created", len(st.session_state.flashcards) if st.session_state.flashcards else 0)
            with c4: st.metric("Quizzes Aced", len(st.session_state.quiz_answers) if st.session_state.quiz_answers else 0)

# --- PAGE: FLASHCARDS ---
def render_flashcards():
    st.markdown("## ⚡ Flashcards")
    
    if not st.session_state.documents_processed:
        st.warning("Upload documents to generate cards.")
        return

    # SETTINGS
    with st.expander("⚙️ Generator Config", expanded=not bool(st.session_state.flashcards)):
        c1, c2 = st.columns(2)
        with c1: num = st.slider("Quantity", 5, 50, 10)
        with c2: diff = st.selectbox("Difficulty", ["Mixed", "Hard Mode", "Easy Review"])
        
        diff_map = {"Mixed": "easy_medium_hard", "Hard Mode": "medium_hard", "Easy Review": "easy_medium"}
        
        if st.button("Generate Deck", type="primary"):
            with st.spinner("Forging cards..."):
                st.session_state.flashcards = st.session_state.agent_controller.generate_flashcards(num, diff_map[diff])
                st.rerun()

    if st.session_state.flashcards:
        for i, card in enumerate(st.session_state.flashcards):
            st.markdown(f"""
            <div class="feature-card" style="margin-bottom: 1rem;">
                <div style="display:flex; justify-content:space-between; color: var(--accent-primary); font-size: 0.8rem; font-weight: 700; margin-bottom: 1rem;">
                    <span>CARD {i+1}</span>
                    <span>{card.get('difficulty', 'GENERAL').upper()}</span>
                </div>
                <h3 style="font-size: 1.4rem; margin-bottom: 1.5rem;">{card['question']}</h3>
                <details>
                    <summary style="cursor: pointer; color: var(--accent-glow); font-weight: 600;">Reveal Answer</summary>
                    <p style="margin-top: 1rem; color: var(--text-secondary); line-height: 1.6;">{card['answer']}</p>
                </details>
            </div>
            """, unsafe_allow_html=True)
        
        st.download_button("📥 Download Anki Deck", st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards), "deck.csv", "text/csv")

# --- PAGE: QUIZZES ---
def render_quizzes():
    st.markdown("## 📝 Adaptive Quiz")
    
    if not st.session_state.documents_processed:
        st.warning("Upload documents first.")
        return

    if not st.session_state.quizzes:
        c1, c2 = st.columns([1, 2])
        with c1:
            diff = st.select_slider("Difficulty", options=["easy", "medium", "hard"])
            num = st.number_input("Questions", 3, 20, 5)
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Start Challenge", type="primary"):
                st.session_state.quizzes = st.session_state.agent_controller.generate_quiz(diff, num)
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_result = None
                st.rerun()

    else:
        # QUIZ INTERFACE
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"""
            <div style="background: var(--bg-card); padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border: 1px solid var(--border-glass);">
                <p style="font-weight: 600; color: var(--accent-glow); margin-bottom: 0.5rem;">QUESTION {i+1}</p>
                <h4 style="margin-bottom: 1.5rem;">{q['question']}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            sel = st.radio(f"Select answer for Q{i+1}", q['options'], key=f"q_{i}", label_visibility="collapsed")
            if sel in q['options']:
                st.session_state.quiz_answers[i] = q['options'].index(sel)
        
        if not st.session_state.quiz_submitted:
            if st.button("Submit Answers", type="primary"):
                res = st.session_state.agent_controller.evaluate_quiz(st.session_state.quizzes, st.session_state.quiz_answers)
                st.session_state.quiz_result = res
                st.session_state.quiz_submitted = True
                st.rerun()
        
        # RESULTS
        if st.session_state.quiz_submitted and st.session_state.quiz_result:
            res = st.session_state.quiz_result
            score = res['score']
            total = res['total']
            perc = res['accuracy'] * 100
            
            color = "#10B981" if perc > 70 else "#F59E0B" if perc > 40 else "#EF4444"
            
            st.markdown(f"""
            <div style="background: {color}20; border: 1px solid {color}; padding: 2rem; border-radius: 16px; text-align: center; margin: 2rem 0;">
                <h1 style="color: {color} !important; margin: 0 !important;">{score}/{total}</h1>
                <p style="color: {color}; font-weight: 600;">{res.get('feedback', 'Mission Complete')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("New Quiz"):
                st.session_state.quizzes = []
                st.session_state.quiz_submitted = False
                st.rerun()

# --- PAGE: PLANNER ---
def render_planner():
    st.markdown("## 📅 Revision Planner")
    
    if not st.session_state.documents_processed:
        st.warning("Upload documents first.")
        return

    c1, c2 = st.columns(2)
    with c1: date = st.date_input("Exam Date")
    with c2: days = st.slider("Study Days/Week", 1, 7, 5)
    
    if st.button("Generate Plan", type="primary"):
        st.session_state.agent_controller.create_revision_plan(date.strftime('%Y-%m-%d') if date else None, days)
        st.rerun()
        
    plan = st.session_state.agent_controller.planner_agent.load_plan()
    if plan:
        for item in plan:
            status_col = "#10B981" if item.get('status') == 'completed' else "#3B82F6"
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid {status_col};">
                <div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">{item['date']}</div>
                    <div style="font-size: 1.1rem; font-weight: 600;">{item['topic']}</div>
                </div>
                <div style="background: {status_col}20; color: {status_col}; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">
                    {item.get('status', 'PENDING').upper()}
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- PAGE: CHAT ---
def render_chat():
    st.markdown("## 💬 AI Assistant")
    
    if not st.session_state.documents_processed:
        st.warning("Upload documents first.")
        return

    # Chat Container
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        q = msg['question']
        a = msg['answer']
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem;">
            <div class="chat-bubble user-bubble">{q}</div>
            <div class="chat-bubble ai-bubble">{a}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if prompt := st.chat_input("Ask about your notes..."):
        st.markdown(f'<div class="chat-bubble user-bubble" style="margin-bottom: 1rem;">{prompt}</div>', unsafe_allow_html=True)
        with st.spinner("Thinking..."):
            res = st.session_state.agent_controller.answer_question(prompt)
            if res:
                st.session_state.chat_history.append({'question': prompt, 'answer': res['answer'], 'sources': res.get('sources', [])})
                st.rerun()

# --- PAGE: ANALYTICS ---
def render_analytics():
    st.markdown("## 📊 Analytics")
    if not st.session_state.agent_controller: return
    
    stats = st.session_state.agent_controller.get_statistics()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="glass-panel">
            <h3>Content</h3>
            <div style="font-size: 3rem; font-weight: 700; color: var(--accent-primary);">{stats['total_chunks']}</div>
            <div style="color: var(--text-secondary);">Knowledge Chunks</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        perf = stats.get('performance', {})
        score = perf.get('average_score', 0) * 100
        st.markdown(f"""
        <div class="glass-panel">
            <h3>Performance</h3>
            <div style="font-size: 3rem; font-weight: 700; color: var(--success);">{score:.0f}%</div>
            <div style="color: var(--text-secondary);">Average Quiz Score</div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
