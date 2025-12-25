# AI Study Assistant · Multi-Agent Copilot

[![Streamlit](https://img.shields.io/badge/Streamlit-%23FF4B4B.svg?style=flat&logo=Streamlit&logoColor=white)](https://streamlit.io/) [![LangChain](https://img.shields.io/badge/LangChain-1E4169?style=flat&logo=chainlink&logoColor=white)](https://www.langchain.com/) [![ChromaDB](https://img.shields.io/badge/ChromaDB-181818?style=flat&logo=amazondynamodb&logoColor=white)](https://www.trychroma.com/)

> Hack Infinity finalist that turns unstructured study material into flashcards, quizzes, revision plans, and chat responses—all orchestrated by resilient AI agents.

**🌐 Live demo:** [the-bug-slayers-hack-infinity-final.streamlit.app](https://the-bug-slayers-hack-infinity-final.streamlit.app/)  
**🧠 Pitch deck / video:** _coming soon_ · grab the [assets folder](documents/) to see sample PDFs we use during judging.

---

## 🔍 Why This Matters
- Students lose time rewriting notes—this copilot ingests PDFs and produces study artefacts in minutes.
- Multi-agent coordination (Reader → Flashcards → Quiz → Planner → Chat) keeps context in sync without hallucinations.
- A vector store watchdog clears stale chunks per session so judges can’t break the demo with repeated uploads.

---

## ✨ Feature Highlights
- **Document Intelligence**
  - PDF/DOCX/TXT ingestion with chunk level metrics and topic extraction
  - On-the-fly API key discovery (Streamlit Secrets → env vars → `.env`)
- **Autonomous Agents**
  - `ReaderAgent` cleans + chunks content and logs chunk counts
  - `FlashcardAgent`, `QuizAgent`, `PlannerAgent`, and `ChatAgent` share the same memory namespace through `AgentController`
- **Learning Workflow**
  - Flashcard carousel with spaced-repetition tags
  - Adaptive quizzes that store answer history
  - Revision planner that prioritizes weak topics and adds daily streak targets
  - Chat assistant with RAG + semantic reranking to quote original pages
- **Resilience**
  - Embedding backend falls back between local `SentenceTransformer` and Gemini/OpenAI APIs (`EMBEDDING_BACKEND=auto`)
  - Vector store gets wiped per session to avoid stale embeddings
  - Graceful error blocks with actionable fixes (Torch install, API keys, etc.)

---

## 🧱 Architecture at a Glance
```
┌─────────────┐       ┌─────────────┐     ┌────────────────┐     ┌──────────────┐
│ Streamlit UI├──────▶│AgentController├───▶│VectorStore/LLMs├────▶│ChromaDB store│
└─────▲───────┘       └──────┬──────┘     └────────┬───────┘     └──────▲───────┘
      │ Documents            │ Agents: Reader, Flashcard, Quiz, Planner, Chat │
      └──────────────────────┴─────────────────────────────────────────────────┘
```
- UI events dispatch intents to the controller.
- Controller requests embeddings via `vector_store.py` (local ST or API).
- LangChain pipelines (Gemini Flash 2.0) create flashcards/quizzes/plans.
- ChromaDB holds semantic chunks; controller clears/refreshes per upload.

---

## 🧑‍💻 Agents & Modules
- `agents/reader_agent.py` – PDF parsing, chunking, topic extraction
- `agents/flashcard_agent.py` – generates QA pairs + difficulty tagging
- `agents/quiz_agent.py` – adaptive MCQs with answer tracking
- `agents/planner_agent.py` – multi-day revision plans using workload heuristics
- `agents/chat_agent.py` – RAG chat grounded in the latest vector store
- `vector_store.py` – local/API embedding backend, cache, and cleanup helpers
- `alerts_manager.py` – surfaces Streamlit toasts from deep calls

---

## ⚙️ Getting Started
1. **Clone & install**
   ```bash
   git clone https://github.com/vjain5375/the-bug-slayers-final.git
   cd the-bug-slayers-final
   python -m venv .venv && .\.venv\Scripts\activate  # or source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure keys (`.env`)**
   ```
   GOOGLE_API_KEY=your_gemini_key
   # optional fallbacks
   OPENAI_API_KEY=sk-...
   EMBEDDING_BACKEND=auto   # local | api | auto
   ```
3. **(Optional) force API embeddings**
   ```
   EMBEDDING_BACKEND=api
   ```

---

## 🏃 Run Locally
```bash
streamlit run app.py
```

### CLI flags you might need
- `STREAMLIT_SERVER_ADDRESS=0.0.0.0` for LAN demos
- `EMBEDDING_BACKEND=local` to keep everything offline (installs `torch` CPU wheel)

---

## 🧩 Troubleshooting Cheatsheet
| Symptom | Fix |
| --- | --- |
| “Vector store failed to initialize” | Install Torch CPU `pip install torch --index-url https://download.pytorch.org/whl/cpu` or switch to `EMBEDDING_BACKEND=api`. |
| Streamlit spinner never shows progress | Spinners are intentionally disabled for accessibility; watch the static status banners at the top. |
| Nothing happens after uploading | Check `documents/` directory permissions; the app cleans older files on session reset. |

---

## 📌 Roadmap
- [x] Export flashcards/quizzes as Anki decks & CSV.
- [ ] Shared study rooms with invite links.
- [ ] Automated grading for custom answers.
- [ ] Voice interface for mobile learners.

---

## 🤝 Contributors
Built by **The Bug Slayers** for Hack Infinity 2025. Reach out via issues or discussions if you’d like to collaborate!

