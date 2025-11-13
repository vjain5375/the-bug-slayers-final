# AI Study Assistant - Multi-Agent System

A personalized study assistant with flashcards, quizzes, and revision planning powered by AI.

## 🌐 Live Application

**👉 [Access the Application](https://the-bug-slayers-hack-infinity-final.streamlit.app/)**

## Features

- 📚 **Document Processing**: Upload and process PDF, DOCX, and TXT files
- 🎯 **Flashcard Generation**: Automatically generate Q/A flashcards from study materials
- 📝 **Quiz Generation**: Create adaptive quizzes to test your knowledge
- 📅 **Revision Planner**: Get personalized revision schedules
- 💬 **Chat Assistant**: Ask questions about your study materials with RAG-based answers
- 🔍 **Semantic Search**: Find relevant information using vector embeddings

## Technology Stack

- **Frontend**: Streamlit
- **AI/ML**: 
  - Google Gemini 2.0 Flash (LLM)
  - Sentence Transformers (Embeddings)
  - LangChain (LLM Framework)
- **Vector Database**: ChromaDB
- **Backend**: Python

## Installation

1. Clone the repository:
```bash
git clone https://github.com/vjain5375/the-bug-slayers-final.git
cd the-bug-slayers-final
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file with your API key:
```
GOOGLE_API_KEY=your_api_key_here
```

4. Run the application:
```bash
streamlit run app.py
```

## Embedding Backend Configuration

The application supports both local and API-based embeddings:

- **Local (Default)**: Uses SentenceTransformers on CPU
- **API Fallback**: Automatically falls back to OpenAI/Gemini embeddings if local model fails

To force API embeddings, set:
```bash
EMBEDDING_BACKEND=api
OPENAI_API_KEY=your_openai_key
```

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── vector_store.py        # Vector database and embeddings management
├── agents/               # AI agent modules
│   ├── reader_agent.py   # Document reading and processing
│   ├── flashcard_agent.py # Flashcard generation
│   ├── quiz_agent.py     # Quiz generation
│   ├── planner_agent.py  # Revision planning
│   ├── chat_agent.py     # RAG-based Q&A
│   └── controller.py     # Central agent orchestrator
├── utils/                # Utility modules
│   └── embeddings_api.py # API-based embeddings wrapper
└── requirements.txt      # Python dependencies
```

## License

This project is part of Hack Infinity 2025.

## Contributors

The Bug Slayers Team

