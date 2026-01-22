import streamlit as st
import os
import time
from pathlib import Path
import logging
from typing import List, Dict

# --- AGENT IMPORTS ---
from agents.controller import AgentController
from vector_store import VectorStore
from agents.planner_agent import PlannerAgent

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Campus Compass",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UTILS ---
def ensure_documents_directory():
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    return docs_dir

def get_document_files():
    return list(ensure_documents_directory().glob("*"))

def cleanup_session():
    for folder in ["documents", "outputs"]:
        p = Path(folder)
        if p.exists():
            for f in p.glob("*"):
                try: f.unlink()
                except: pass
    if 'vector_store' in st.session_state and st.session_state.vector_store:
        try:
            st.session_state.vector_store.client.delete_collection("campus_compass")
            st.session_state.vector_store = VectorStore()
        except: pass

def _compute_docs_signature(doc_files):
    if not doc_files: return None
    return "|".join([f"{d.name}_{d.stat().st_size}" for d in sorted(doc_files, key=lambda x: x.name) if d.exists()])

# --- SESSION STATE ---
if 'initialized' not in st.session_state:
    cleanup_session()
    st.session_state.initialized = True
    st.session_state.current_page = "home"
    st.session_state.vector_store = VectorStore()
    try:
        if st.session_state.vector_store.collection:
            ids = st.session_state.vector_store.collection.get()['ids']
            if ids: st.session_state.vector_store.collection.delete(ids=ids)
    except: pass
    st.session_state.agent_controller = AgentController(st.session_state.vector_store)
    st.session_state.documents_processed = False
    st.session_state.flashcards = []
    st.session_state.quizzes = []
    st.session_state.quiz_answers = {}
    st.session_state.chat_history = []
    st.session_state.num_flashcards = 10
    st.session_state.document_upload_order = []
    st.session_state.last_signature = None

# --- CSS: OPINIONATED, MATTE, FUNCTIONAL ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #0a0a0b;
    --surface: #141416;
    --surface-2: #1c1c1f;
    --border: #2a2a2d;
    --text: #e4e4e7;
    --text-dim: #71717a;
    --blue: #3b82f6;
    --blue-dim: #1e3a5f;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
}

.stApp {
    background: var(--bg);
}

/* SIDEBAR: Heavy, grounded, not floating */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}

/* Remove default streamlit padding bloat */
.block-container {
    padding: 2rem 3rem !important;
    max-width: 100% !important;
}

/* Headers: No gradient nonsense */
h1, h2, h3 {
    color: var(--text) !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

h1 { font-size: 1.75rem !important; margin-bottom: 0.5rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1rem !important; }

/* Buttons: Blue = action, nothing else */
div.stButton > button {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-dim) !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.15s ease !important;
}

div.stButton > button:hover {
    border-color: var(--blue) !important;
    color: var(--blue) !important;
    background: var(--blue-dim) !important;
}

div.stButton > button[kind="primary"] {
    background: var(--blue) !important;
    border: none !important;
    color: white !important;
}

div.stButton > button[kind="primary"]:hover {
    background: #2563eb !important;
}

/* Status boxes */
.status-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
}

.status-box.ready {
    border-left: 3px solid var(--green);
}

.status-box.empty {
    border-left: 3px solid var(--text-dim);
}

.status-box.processing {
    border-left: 3px solid var(--yellow);
}

/* Metric: Monospace numbers */
.metric {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1;
}

.metric-label {
    font-size: 0.75rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.25rem;
}

/* Cards: Dense, functional */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
}

.card:hover {
    border-color: var(--blue);
}

/* Nav item */
.nav-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.625rem 0.875rem;
    border-radius: 6px;
    color: var(--text-dim);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    margin-bottom: 0.25rem;
}

.nav-item:hover {
    background: var(--surface-2);
    color: var(--text);
}

.nav-item.active {
    background: var(--blue-dim);
    color: var(--blue);
}

/* Upload zone: Functional, not decorative */
.upload-zone {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2rem;
    text-align: left;
}

.upload-zone:hover {
    border-color: var(--text-dim);
}

/* Chat */
.msg {
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    line-height: 1.5;
    max-width: 85%;
}

.msg-user {
    background: var(--blue);
    color: white;
    margin-left: auto;
    border-bottom-right-radius: 2px;
}

.msg-ai {
    background: var(--surface-2);
    border: 1px solid var(--border);
    margin-right: auto;
    border-bottom-left-radius: 2px;
}

/* Hide streamlit branding */
#MainMenu, footer, header {visibility: hidden;}

/* Expander */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}

/* File uploader: remove default styling */
div[data-testid="stFileUploader"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

div[data-testid="stFileUploader"] label {
    color: var(--text-dim) !important;
}

/* Metrics override */
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.5rem !important;
    color: var(--text) !important;
}

div[data-testid="stMetricLabel"] {
    color: var(--text-dim) !important;
    font-size: 0.75rem !important;
}

</style>
""", unsafe_allow_html=True)

# --- PROCESS DOCUMENTS ---
def process_documents():
    docs_dir = ensure_documents_directory()
    doc_files = get_document_files()
    
    if not doc_files:
        st.error("Nothing to process.")
        return False
    
    sig = _compute_docs_signature(doc_files)
    if sig and st.session_state.documents_processed and st.session_state.get('last_signature') == sig:
        return True
    
    with st.spinner("Reading..."):
        try:
            result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
            if result['total_chunks'] > 0:
                st.session_state.documents_processed = True
                st.session_state.processing_results = result
                st.session_state.last_signature = sig
                return True
        except Exception as e:
            st.error(f"Failed: {e}")
    return False

# --- MAIN ---
def main():
    # === SIDEBAR ===
    with st.sidebar:
        # Logo/Title: Simple, not fancy
        st.markdown("""
        <div style="padding: 0.5rem 0 1.5rem 0;">
            <div style="font-size: 1.1rem; font-weight: 600; color: var(--text);">📚 Campus Compass</div>
            <div style="font-size: 0.75rem; color: var(--text-dim);">your notes, less chaos</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation: Dense, keyboard-style
        pages = [
            ("home", "Home", "⌂"),
            ("flashcards", "Flashcards", "⚡"),
            ("quizzes", "Quizzes", "?"),
            ("planner", "Planner", "📅"),
            ("chat", "Chat", "💬"),
            ("stats", "Stats", "◉"),
        ]
        
        for key, label, icon in pages:
            is_active = st.session_state.current_page == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.current_page = key
                st.rerun()
        
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        
        # Quick status in sidebar
        doc_count = len(get_document_files())
        chunk_count = st.session_state.processing_results.get('total_chunks', 0) if st.session_state.documents_processed else 0
        
        st.markdown(f"""
        <div style="padding: 1rem; background: var(--surface-2); border-radius: 6px; font-size: 0.8rem;">
            <div style="color: var(--text-dim); margin-bottom: 0.5rem;">STATUS</div>
            <div style="color: var(--text);">{doc_count} docs → {chunk_count} chunks</div>
        </div>
        """, unsafe_allow_html=True)

    # === ROUTING ===
    page = st.session_state.current_page
    if page == "home": render_home()
    elif page == "flashcards": render_flashcards()
    elif page == "quizzes": render_quizzes()
    elif page == "planner": render_planner()
    elif page == "chat": render_chat()
    elif page == "stats": render_stats()

# === HOME: Workspace, not poster ===
def render_home():
    # No hero. Just state.
    
    if not st.session_state.documents_processed:
        # EMPTY STATE: Honest, direct
        st.markdown("## Your notes are a mess.")
        st.markdown("<p style='color: var(--text-dim); margin-bottom: 2rem;'>Drop the PDFs. We'll handle the chaos.</p>", unsafe_allow_html=True)
        
        # Upload: Left-aligned, not centered
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            <div class="upload-zone">
                <div style="font-size: 0.875rem; color: var(--text-dim); margin-bottom: 0.5rem;">UPLOAD</div>
                <div style="font-size: 0.875rem; color: var(--text);">PDF, DOCX, TXT accepted</div>
            </div>
            """, unsafe_allow_html=True)
            
            uploaded = st.file_uploader(
                "Drop files",
                type=['pdf', 'docx', 'doc', 'txt'],
                accept_multiple_files=True,
                key="home_upload",
                label_visibility="collapsed"
            )
            
            if uploaded:
                st.markdown(f"<div style='color: var(--green); font-size: 0.875rem; margin: 0.5rem 0;'>{len(uploaded)} files ready</div>", unsafe_allow_html=True)
                
                if st.button("Process now", type="primary"):
                    docs_dir = ensure_documents_directory()
                    for f in uploaded:
                        with open(docs_dir / f.name, "wb") as pf:
                            pf.write(f.getbuffer())
                        if f.name not in st.session_state.document_upload_order:
                            st.session_state.document_upload_order.append(f.name)
                    
                    if process_documents():
                        st.rerun()
        
        with col2:
            st.markdown("""
            <div style="padding: 1rem; font-size: 0.8rem; color: var(--text-dim);">
                <div style="margin-bottom: 1rem;"><strong style="color: var(--text);">What happens:</strong></div>
                <div style="margin-bottom: 0.5rem;">1. We extract every concept</div>
                <div style="margin-bottom: 0.5rem;">2. Build a knowledge graph</div>
                <div style="margin-bottom: 0.5rem;">3. Generate study tools</div>
            </div>
            """, unsafe_allow_html=True)
    
    else:
        # ACTIVE STATE: Show what's ready
        result = st.session_state.processing_results
        
        # Top: Quick metrics (dense, left-aligned)
        st.markdown("## Ready to study")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="status-box ready">
                <div class="metric">{result['total_chunks']}</div>
                <div class="metric-label">chunks</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="status-box ready">
                <div class="metric">{result['total_topics']}</div>
                <div class="metric-label">topics</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            fc = len(st.session_state.flashcards)
            st.markdown(f"""
            <div class="status-box {'ready' if fc else 'empty'}">
                <div class="metric">{fc}</div>
                <div class="metric-label">cards</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            qz = len(st.session_state.quizzes)
            st.markdown(f"""
            <div class="status-box {'ready' if qz else 'empty'}">
                <div class="metric">{qz}</div>
                <div class="metric-label">questions</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        
        # Quick actions: Not cards, just buttons
        st.markdown("### Do something")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("<div style='color: var(--text-dim); font-size: 0.8rem; margin-bottom: 0.5rem;'>FLASHCARDS</div>", unsafe_allow_html=True)
            if st.button("Generate 10 cards", key="quick_flash"):
                st.session_state.current_page = "flashcards"
                st.rerun()
        with c2:
            st.markdown("<div style='color: var(--text-dim); font-size: 0.8rem; margin-bottom: 0.5rem;'>QUIZ</div>", unsafe_allow_html=True)
            if st.button("Test yourself", key="quick_quiz"):
                st.session_state.current_page = "quizzes"
                st.rerun()
        with c3:
            st.markdown("<div style='color: var(--text-dim); font-size: 0.8rem; margin-bottom: 0.5rem;'>CHAT</div>", unsafe_allow_html=True)
            if st.button("Ask a question", key="quick_chat"):
                st.session_state.current_page = "chat"
                st.rerun()
        
        # Topics found (collapsed by default)
        if result.get('topics'):
            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
            with st.expander(f"Topics found ({len(result['topics'])})"):
                for t in result['topics'][:10]:
                    st.markdown(f"• {t.get('topic', 'General')}")

# === FLASHCARDS ===
def render_flashcards():
    st.markdown("## Flashcards")
    
    if not st.session_state.documents_processed:
        st.markdown("<p style='color: var(--text-dim);'>Upload docs first.</p>", unsafe_allow_html=True)
        return
    
    # Generator
    if not st.session_state.flashcards:
        c1, c2 = st.columns([1, 2])
        with c1:
            num = st.slider("How many?", 5, 30, 10, label_visibility="collapsed")
            st.caption(f"{num} cards")
        with c2:
            if st.button("Generate", type="primary"):
                with st.spinner("Creating cards..."):
                    st.session_state.flashcards = st.session_state.agent_controller.generate_flashcards(num)
                    st.rerun()
    
    # Display cards
    if st.session_state.flashcards:
        st.markdown(f"<p style='color: var(--text-dim); margin-bottom: 1rem;'>{len(st.session_state.flashcards)} cards ready</p>", unsafe_allow_html=True)
        
        csv = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button("Export CSV", csv, "flashcards.csv", "text/csv")
        
        for i, card in enumerate(st.session_state.flashcards):
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 0.75rem; color: var(--text-dim); margin-bottom: 0.75rem;">{i+1} / {len(st.session_state.flashcards)}</div>
                <div style="font-size: 1rem; font-weight: 500; margin-bottom: 1rem;">{card['question']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Answer"):
                st.write(card['answer'])

# === QUIZZES ===
def render_quizzes():
    st.markdown("## Quiz")
    
    if not st.session_state.documents_processed:
        st.markdown("<p style='color: var(--text-dim);'>Upload docs first.</p>", unsafe_allow_html=True)
        return
    
    # Start new quiz
    if not st.session_state.quizzes:
        c1, c2 = st.columns([1, 2])
        with c1:
            num = st.slider("Questions", 3, 15, 5, label_visibility="collapsed")
            diff = st.selectbox("Difficulty", ["easy", "medium", "hard"], label_visibility="collapsed")
        with c2:
            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
            if st.button("Start quiz", type="primary"):
                st.session_state.quizzes = st.session_state.agent_controller.generate_quiz(diff, num)
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_result = None
                st.rerun()
    else:
        # Quiz in progress
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 0.75rem; color: var(--text-dim);">Q{i+1}</div>
                <div style="font-weight: 500; margin: 0.5rem 0 1rem 0;">{q['question']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            ans = st.radio(f"q{i}", q['options'], key=f"quiz_{i}", label_visibility="collapsed")
            if ans in q['options']:
                st.session_state.quiz_answers[i] = q['options'].index(ans)
        
        if not st.session_state.get('quiz_submitted'):
            if st.button("Submit", type="primary"):
                res = st.session_state.agent_controller.evaluate_quiz(st.session_state.quizzes, st.session_state.quiz_answers)
                st.session_state.quiz_result = res
                st.session_state.quiz_submitted = True
                st.rerun()
        
        # Results
        if st.session_state.get('quiz_submitted') and st.session_state.quiz_result:
            res = st.session_state.quiz_result
            pct = res['accuracy'] * 100
            
            st.markdown(f"""
            <div style="padding: 1.5rem; background: var(--surface); border-radius: 8px; border-left: 3px solid {'var(--green)' if pct >= 70 else 'var(--yellow)' if pct >= 50 else 'var(--red)'}; margin: 1rem 0;">
                <div style="font-family: 'JetBrains Mono'; font-size: 2rem; font-weight: 600;">{res['score']}/{res['total']}</div>
                <div style="color: var(--text-dim); font-size: 0.875rem;">{pct:.0f}% correct</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("New quiz"):
                st.session_state.quizzes = []
                st.session_state.quiz_submitted = False
                st.rerun()

# === PLANNER ===
def render_planner():
    st.markdown("## Planner")
    
    if not st.session_state.documents_processed:
        st.markdown("<p style='color: var(--text-dim);'>Upload docs first.</p>", unsafe_allow_html=True)
        return
    
    c1, c2 = st.columns(2)
    with c1:
        date = st.date_input("Exam date", label_visibility="collapsed")
    with c2:
        days = st.slider("Days/week", 1, 7, 5, label_visibility="collapsed")
    
    if st.button("Generate plan", type="primary"):
        st.session_state.agent_controller.create_revision_plan(date.strftime('%Y-%m-%d') if date else None, days)
        st.rerun()
    
    plan = st.session_state.agent_controller.planner_agent.load_plan()
    if plan:
        st.markdown(f"<p style='color: var(--text-dim); margin: 1rem 0;'>{len(plan)} sessions</p>", unsafe_allow_html=True)
        for item in plan:
            status = item.get('status', 'pending')
            color = 'var(--green)' if status == 'completed' else 'var(--text-dim)'
            st.markdown(f"""
            <div class="card" style="border-left: 3px solid {color};">
                <div style="font-size: 0.75rem; color: var(--text-dim);">{item['date']}</div>
                <div style="font-weight: 500;">{item['topic']}</div>
            </div>
            """, unsafe_allow_html=True)

# === CHAT ===
def render_chat():
    st.markdown("## Chat")
    
    if not st.session_state.documents_processed:
        st.markdown("<p style='color: var(--text-dim);'>Upload docs first.</p>", unsafe_allow_html=True)
        return
    
    # History
    for msg in st.session_state.chat_history:
        st.markdown(f"<div class='msg msg-user'>{msg['question']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='msg msg-ai'>{msg['answer']}</div>", unsafe_allow_html=True)
    
    # Input
    if prompt := st.chat_input("Ask something..."):
        st.markdown(f"<div class='msg msg-user'>{prompt}</div>", unsafe_allow_html=True)
        with st.spinner("..."):
            res = st.session_state.agent_controller.answer_question(prompt)
            if res:
                st.session_state.chat_history.append({'question': prompt, 'answer': res['answer']})
                st.rerun()

# === STATS ===
def render_stats():
    st.markdown("## Stats")
    
    if not st.session_state.agent_controller:
        return
    
    stats = st.session_state.agent_controller.get_statistics()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="status-box">
            <div style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.5rem;">CONTENT</div>
            <div class="metric">{stats['total_chunks']}</div>
            <div class="metric-label">chunks indexed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        perf = stats.get('performance', {})
        avg = perf.get('average_score', 0) * 100
        st.markdown(f"""
        <div class="status-box">
            <div style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.5rem;">PERFORMANCE</div>
            <div class="metric">{avg:.0f}%</div>
            <div class="metric-label">avg quiz score</div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
