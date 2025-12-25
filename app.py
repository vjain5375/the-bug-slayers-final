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

# Load API key
def load_api_key():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key: return api_key
    load_dotenv()
    return os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")

# Page configuration
st.set_page_config(page_title="Deadpool Hub", page_icon="💀", layout="wide")

# Initialize session state
if 'session_initialized' not in st.session_state:
    st.session_state.session_initialized = True
    st.session_state.current_page = "Home"
    st.session_state.documents_processed = False
    st.session_state.chat_history = []
    st.session_state.flashcards = []
    st.session_state.quizzes = []
    st.session_state.quiz_answers = {}
    st.session_state.num_flashcards = 10
    st.session_state.num_questions = 10
    st.session_state.agent_controller = None
    st.session_state.vector_store = None

# Premium Deadpool Theme CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@400;700&display=swap');

    :root {
        --deadpool-red: #E62429;
        --deadpool-black: #000000;
        --comic-white: #FFFFFF;
    }

    /* Global */
    .stApp {
        background-color: var(--deadpool-black);
        color: var(--comic-white);
        font-family: 'Oswald', sans-serif;
    }

    /* Clean Streamlit Blocks */
    [data-testid="stVerticalBlock"] > div { background: none !important; border: none !important; padding: 0 !important; }

    /* Custom Comic Card */
    .comic-card {
        background: #1A1A1A;
        border: 4px solid #000;
        box-shadow: 8px 8px 0px var(--deadpool-red);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    /* Buttons */
    .stButton > button {
        font-family: 'Bangers', cursive !important;
        background-color: var(--deadpool-red) !important;
        color: white !important;
        border: 3px solid #000 !important;
        border-radius: 0px !important;
        box-shadow: 4px 4px 0px #000 !important;
        min-height: 55px !important;
        width: 100% !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }
    .stButton > button:hover {
        transform: translate(-2px, -2px);
        box-shadow: 6px 6px 0px #000 !important;
        background-color: #FF3B3F !important;
    }

    /* Typography */
    h1, h2, h3 { font-family: 'Bangers', cursive !important; text-transform: uppercase; margin: 0 !important; }
    h1 { color: var(--deadpool-red); font-size: 3.5rem; text-shadow: 4px 4px 0px #000; }
    h2 { color: #fff; font-size: 2.2rem; }
    
    /* Header & Sidebar */
    header[data-testid="stHeader"] { background-color: var(--deadpool-red) !important; border-bottom: 4px solid #000 !important; }
    [data-testid="stSidebar"] { background-color: #111 !important; border-right: 5px solid var(--deadpool-red) !important; }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #000 !important;
        border: 3px solid var(--deadpool-red) !important;
        padding: 1rem !important;
        box-shadow: 5px 5px 0px #000 !important;
    }

    /* Tighten spacing */
    .block-container { padding-top: 1rem !important; max-width: 1300px !important; }
</style>
""", unsafe_allow_html=True)

def initialize_components():
    if st.session_state.vector_store is None:
        try:
            st.session_state.vector_store = VectorStore()
            st.session_state.agent_controller = AgentController(st.session_state.vector_store)
        except Exception as e:
            st.error(f"Initialization Error: {e}")
            st.stop()

def process_documents():
    docs_dir = ensure_documents_directory()
    result = st.session_state.agent_controller.process_study_materials(str(docs_dir))
    if result['total_chunks'] > 0:
        st.session_state.documents_processed = True
        st.session_state.processing_results = result
        st.success(f"✅ Weaponized {result['total_chunks']} chunks!")
        return True
    return False

def show_flashcards_page():
    st.markdown("## 📇 FLASHCARDS")
    if not st.session_state.documents_processed:
        st.warning("Feed me documents first!")
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        num = st.slider("Quantity", 5, 30, st.session_state.num_flashcards)
    with col2:
        if st.button("🔥 GENERATE"):
            with st.spinner("Slicing info..."):
                cards = st.session_state.agent_controller.generate_flashcards(num)
                st.session_state.flashcards = cards
                st.rerun()
    
    if st.session_state.flashcards:
        csv_data = st.session_state.agent_controller.flashcard_agent.export_to_csv(st.session_state.flashcards)
        st.download_button("📥 EXPORT TO ANKI", csv_data, "flashcards.csv", "text/csv")
        for i, card in enumerate(st.session_state.flashcards):
            with st.expander(f"CARD {i+1}: {card.get('topic', 'General').upper()}"):
                st.markdown(f"**Q:** {card['question']}")
                st.markdown(f"**A:** {card['answer']}")

def show_quizzes_page():
    st.markdown("## 📝 QUIZZES")
    if not st.session_state.documents_processed:
        st.warning("Feed me documents first!")
        return
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1: diff = st.selectbox("DIFFICULTY", ["easy", "medium", "hard"], index=1)
    with col2: num = st.slider("QUESTIONS", 3, 20, st.session_state.num_questions)
    with col3:
        if st.button("🎯 START"):
            with st.spinner("Generating pain..."):
                st.session_state.quizzes = st.session_state.agent_controller.generate_quiz(diff, num)
                st.session_state.quiz_answers = {}
                st.rerun()
    
    if st.session_state.quizzes:
        for i, q in enumerate(st.session_state.quizzes):
            st.markdown(f"**Q{i+1}:** {q['question']}")
            st.session_state.quiz_answers[i] = st.radio("Options:", q['options'], key=f"q{i}", label_visibility="collapsed")
        
        if st.button("✅ SUBMIT"):
            res = st.session_state.agent_controller.evaluate_quiz(st.session_state.quizzes, st.session_state.quiz_answers)
            st.metric("SCORE", f"{res['score']}/{res['total']}")
            with st.expander("REVIEW DETAILS"):
                for d in res['details']:
                    icon = "✅" if d['is_correct'] else "❌"
                    st.markdown(f"{icon} Q{d['question_index']+1}: {d['correct_answer']}")

def show_planner_page():
    st.markdown("## 📅 REVISION PLANNER")
    if not st.session_state.documents_processed:
        st.warning("Feed me documents first!")
        return
    
    col1, col2 = st.columns(2)
    with col1: date = st.date_input("Exam Date")
    with col2: days = st.slider("Days/Week", 1, 7, 5)
    
    if st.button("📅 CREATE PLAN"):
        plan = st.session_state.agent_controller.create_revision_plan(date.strftime('%Y-%m-%d'), days)
        st.success(f"Plan created with {len(plan)} items!")
    
    st.session_state.agent_controller.planner_agent.load_plan()
    plan = st.session_state.agent_controller.planner_agent.revision_plan
    if plan:
        for item in plan:
            st.markdown(f"""
            <div class="comic-card" style="border-left: 5px solid var(--deadpool-red);">
                <h4 style="margin:0;">{item['date']} — {item['topic']}</h4>
                <p style="margin:0; opacity:0.8;">Status: {item['status'].upper()}</p>
            </div>
            """, unsafe_allow_html=True)

def show_chat_page():
    st.markdown("## 💬 CHAT ASSISTANT")
    if not st.session_state.documents_processed:
        st.warning("Feed me documents first!")
        return
    
    for chat in st.session_state.chat_history:
        with st.chat_message("user"): st.write(chat['question'])
        with st.chat_message("assistant"): st.write(chat['answer'])
    
    query = st.chat_input("Ask about your notes...")
    if query:
        with st.chat_message("user"): st.write(query)
        res = st.session_state.agent_controller.answer_question(query)
        with st.chat_message("assistant"): st.write(res['answer'])
        st.session_state.chat_history.append({"question": query, "answer": res['answer']})

def show_analytics_page():
    st.markdown("## 📊 ANALYTICS")
    if not st.session_state.agent_controller:
        st.info("No stats yet.")
        return
    stats = st.session_state.agent_controller.get_statistics()
    c1, c2 = st.columns(2)
    with c1: st.metric("TOPICS", stats['total_topics'])
    with c2: st.metric("CONQUERED", f"{stats['revision_stats']['completion_rate']:.1f}%")

def main():
    initialize_components()

    # --- TOP BRANDING (ONLY ONCE) ---
    st.markdown("<p style='text-align:center; color: var(--deadpool-red); font-family: Bangers; letter-spacing: 3px; font-size: 1.4rem; margin-top: -40px; text-shadow: 2px 2px 0px #000;'>AI-ASSISTANT POWERED BY - DEADPOOL</p>", unsafe_allow_html=True)
    
    col_h1, col_h2 = st.columns([4, 1])
    with col_h1:
        st.markdown("<h1>⚡ DEADPOOL'S STUDY HUB</h1>", unsafe_allow_html=True)
        st.markdown("<div style='background: var(--deadpool-red); height: 6px; width: 280px; margin-top: 5px; border: 2px solid #000;'></div>", unsafe_allow_html=True)
    with col_h2:
        st.image("https://pngimg.com/uploads/deadpool/deadpool_PNG10.png", width=110)

    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://pngimg.com/uploads/deadpool/deadpool_PNG43.png", width=180)
        st.markdown("<h2 style='text-align:center; color:var(--deadpool-red); border:none;'>💀 MENU</h2>", unsafe_allow_html=True)
        
        pages = ["Home", "Flashcards", "Quizzes", "Revision Planner", "Chat Assistant", "Analytics"]
        icons = ["🏠", "📇", "📝", "📅", "💬", "📊"]
        
        for i, p in enumerate(pages):
            if st.button(f"{icons[i]} {p.upper()}", key=f"side_{p}", use_container_width=True):
                st.session_state.current_page = p
                st.rerun()
        
        st.divider()
        st.markdown("### 📚 UPLOAD INTEL")
        files = st.file_uploader("Upload", type=['pdf','docx','txt'], accept_multiple_files=True, label_visibility="collapsed")
        if files:
            if st.button("💾 SAVE & PROCESS", type="primary"):
                docs_dir = ensure_documents_directory()
                for f in files:
                    with open(docs_dir / f.name, "wb") as file: file.write(f.getbuffer())
                if process_documents(): st.balloons(); st.rerun()
        
        st.divider()
        st.image("https://www.pngkit.com/png/full/11-110511_deadpool-png-transparent-deadpool-reading-comic.png", width=160)

    # --- ROUTING ---
    if st.session_state.current_page == "Home":
        st.markdown("""
        <div class="comic-card" style="border-left: 12px solid var(--deadpool-red);">
            <h2 style="color: var(--deadpool-red); margin-bottom: 5px;">📜 MISSION BRIEFING</h2>
            <p style="font-size: 1.2rem; line-height: 1.4;">
                1. <b>Upload</b> your notes in the sidebar.<br>
                2. Click <b>Save & Process</b> to weaponize them.<br>
                3. Use the <b>Quick Actions</b> grid to start dominating!
            </p>
        </div>
        """, unsafe_allow_html=True)

        if not st.session_state.documents_processed:
            cols = st.columns(4)
            imgs = [
                "https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-1.png",
                "https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-2.png",
                "https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-3.png",
                "https://clipart-library.com/images_k/deadpool-transparent-background/deadpool-transparent-background-4.png"
            ]
            titles = ["1️⃣ UPLOAD", "2️⃣ LOCK IT", "3️⃣ PROCESS", "4️⃣ WIN"]
            for i in range(4):
                with cols[i]:
                    st.markdown(f"""
                    <div style="background: #111; padding: 1.2rem; border: 4px solid #000; box-shadow: 6px 6px 0px var(--deadpool-red); text-align: center; min-height: 260px;">
                        <img src="{imgs[i]}" width="110">
                        <h3 style="font-size: 1.6rem; color:var(--deadpool-red); margin-top:10px;">{titles[i]}</h3>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("<h2>📊 STUDY DASHBOARD</h2>", unsafe_allow_html=True)
            stats = st.session_state.agent_controller.get_statistics()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("TOPICS", stats['total_topics'])
            c2.metric("CARDS", stats['total_flashcards'])
            c3.metric("QUIZZES", stats['total_quizzes'])
            c4.metric("PROGRESS", f"{stats['revision_stats']['completion_rate']:.1f}%")

    elif st.session_state.current_page == "Flashcards": show_flashcards_page()
    elif st.session_state.current_page == "Quizzes": show_quizzes_page()
    elif st.session_state.current_page == "Revision Planner": show_planner_page()
    elif st.session_state.current_page == "Chat Assistant": show_chat_page()
    elif st.session_state.current_page == "Analytics": show_analytics_page()

    # FOOTER
    st.markdown("""
    <div style="text-align: center; margin-top: 4rem; padding: 2rem; border-top: 4px solid var(--deadpool-red); background: #000;">
        <img src="https://images.squarespace-cdn.com/content/v1/51b3dc1ee4b051b96ceb10de/1455225017006-2S9L7S9L7S9L7S9L7S9L/image-asset.png" width="180">
        <h2 style="color: var(--deadpool-red); margin-top: 10px;">💀 MAXIMUM EFFORT! ⚔️</h2>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
