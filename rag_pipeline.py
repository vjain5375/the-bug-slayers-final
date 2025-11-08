"""
RAG Pipeline
Implements Retrieval-Augmented Generation for question answering
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)
# Also try loading from current directory
load_dotenv()


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for answering questions"""
    
    def __init__(self, vector_store, model_name: str = "gemini-2.0-flash", temperature: float = 0.1):
        """
        Initialize RAG pipeline
        
        Args:
            vector_store: VectorStore instance
            model_name: Google Gemini model name (default: gemini-pro)
            temperature: LLM temperature
        """
        self.vector_store = vector_store
        
        # Try multiple methods to load API key
        api_key = None
        
        # Method 1: Try environment variable (already set, works for Streamlit Cloud)
        api_key = os.getenv("GOOGLE_API_KEY")
        
        # Method 2: Try from current directory .env file
        if not api_key:
            env_path_current = Path('.env')
            if env_path_current.exists():
                load_dotenv(dotenv_path=env_path_current, override=True)
                api_key = os.getenv("GOOGLE_API_KEY")
        
        # Method 3: Try from script's parent directory .env file
        if not api_key:
            env_path_script = Path(__file__).parent / '.env'
            if env_path_script.exists():
                load_dotenv(dotenv_path=env_path_script, override=True)
                api_key = os.getenv("GOOGLE_API_KEY")
        
        # Method 4: Read directly from file (most reliable fallback)
        if not api_key:
            for env_path in [env_path_current, Path(__file__).parent / '.env']:
                try:
                    if env_path.exists():
                        # Try different encodings
                        for encoding in ['utf-8', 'utf-8-sig', 'latin-1']:
                            try:
                                with open(env_path, 'r', encoding=encoding) as f:
                                    for line in f:
                                        line_clean = line.strip()
                                        if line_clean and not line_clean.startswith('#') and 'GOOGLE_API_KEY' in line_clean:
                                            if '=' in line_clean:
                                                api_key = line_clean.split('=', 1)[1].strip()
                                                # Remove quotes if present
                                                api_key = api_key.strip('"').strip("'")
                                                break
                                    if api_key:
                                        break
                            except Exception:
                                continue
                        if api_key:
                            break
                except Exception as e:
                    continue
        
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found in environment variables. "
                "Please set it in .env file in the project root directory. "
                "Format: GOOGLE_API_KEY=your_api_key_here"
            )
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key
        )
    
    def _format_context(self, retrieved_chunks: List[Dict]) -> str:
        """Format retrieved chunks into context string"""
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            source = chunk['metadata'].get('source', 'Unknown')
            chunk_idx = chunk['metadata'].get('chunk_index', 0)
            text = chunk['text']
            context_parts.append(f"[Source {i}: {source}, Chunk {chunk_idx}]\n{text}\n")
        return "\n---\n".join(context_parts)
    
    def _create_prompt(self, question: str, context: str, summarize: bool = False, allow_general: bool = True) -> str:
        """Create prompt for LLM"""
        if summarize:
            system_prompt = """You are a helpful assistant that provides concise summaries of college policies and documents. 
Your task is to summarize the provided context in a clear, bulleted format. Focus on key points and actionable information.
Always cite your sources when providing information."""
        else:
            if allow_general:
                system_prompt = """You are Campus Compass, an AI assistant that helps students find information about their college.
Your primary goal is to answer questions based on the provided context from official college documents.
IMPORTANT: The context may contain information from multiple documents. Make sure to use information from ALL relevant documents when answering.
If information is available in multiple documents, synthesize it and cite all relevant sources (e.g., "According to [Document Name 1] and [Document Name 2]...").
If the answer is clearly available in the context, prioritize that information and cite your sources (e.g., "According to [Document Name]..." or "As stated in [Document Name]...").
If the answer is not fully available in the context but you can provide helpful general information, you may do so while clearly stating:
1. What information comes from the documents (if any)
2. What information is general knowledge
Use this format: "Based on the available documents: [document-based answer]. Additionally, in general: [general knowledge answer]."
Be concise, accurate, and helpful. When multiple documents are available, use information from all of them."""
            else:
                system_prompt = """You are Campus Compass, an AI assistant that helps students find information about their college.
Your answers must be based ONLY on the provided context from official college documents. 
If the answer is not in the context, say "I don't have that information in the available documents."
Always cite your sources clearly (e.g., "According to [Document Name], page X..." or "As stated in [Document Name]...").
Be concise, accurate, and helpful."""
        
        user_prompt = f"""Context from college documents:
{context}

Question: {question}

Please provide a helpful answer based on the context above."""
        
        return system_prompt, user_prompt
    
    def answer_question(self, question: str, n_chunks: int = 5, summarize: bool = False, allow_general: bool = True) -> Dict:
        """
        Answer a question using RAG
        
        Args:
            question: User's question
            n_chunks: Number of chunks to retrieve
            summarize: Whether to provide a summary format
            allow_general: Whether to allow general answers when documents don't have info
            
        Returns:
            Dict with 'answer', 'sources', and 'chunks' keys
        """
        # Retrieve relevant chunks
        retrieved_chunks = self.vector_store.search(question, n_results=n_chunks)
        
        # Format context (even if empty, we'll handle it)
        if retrieved_chunks:
            context = self._format_context(retrieved_chunks)
        else:
            context = "No relevant information found in the available documents."
        
        # Create prompt
        system_prompt, user_prompt = self._create_prompt(question, context, summarize, allow_general)
        
        # If no chunks and general answers not allowed, return early
        if not retrieved_chunks and not allow_general:
            return {
                'answer': "I couldn't find any relevant information in the available documents. Please try rephrasing your question or ensure documents have been processed.",
                'sources': [],
                'chunks': []
            }
        
        # Generate answer
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            answer = response.content
        except Exception as e:
            answer = f"Error generating answer: {str(e)}. Please check your API key and ensure it's valid."
        
        # Extract unique sources
        sources = list(set([chunk['metadata'].get('source', 'Unknown') for chunk in retrieved_chunks])) if retrieved_chunks else []
        
        return {
            'answer': answer,
            'sources': sources,
            'chunks': retrieved_chunks
        }
    
    def answer_multi_document_question(self, question: str, n_chunks: int = 8, allow_general: bool = True) -> Dict:
        """
        Answer questions that may require information from multiple documents
        
        Args:
            question: User's question
            n_chunks: Number of chunks to retrieve (increased for multi-doc)
            allow_general: Whether to allow general answers when documents don't have info
            
        Returns:
            Dict with 'answer', 'sources', and 'chunks' keys
        """
        # Retrieve more chunks for multi-document synthesis
        retrieved_chunks = self.vector_store.search(question, n_results=n_chunks)
        
        # Group chunks by source
        chunks_by_source = {}
        for chunk in retrieved_chunks:
            source = chunk['metadata'].get('source', 'Unknown')
            if source not in chunks_by_source:
                chunks_by_source[source] = []
            chunks_by_source[source].append(chunk)
        
        # Format context with source grouping
        if chunks_by_source:
            context_parts = []
            for source, chunks in chunks_by_source.items():
                source_text = "\n\n".join([chunk['text'] for chunk in chunks])
                context_parts.append(f"[Source: {source}]\n{source_text}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant information found in the available documents."
        
        # Create prompt for multi-document synthesis
        if allow_general:
            system_prompt = """You are Campus Compass, an AI assistant that synthesizes information from multiple college documents.
Your task is to combine information from different sources to provide a comprehensive answer.
Always cite which document each piece of information comes from.
If information from multiple sources conflicts, mention this in your answer.
If the answer is not fully available in the documents but you can provide helpful general information, you may do so while clearly stating what comes from documents vs. general knowledge.
Be thorough but concise."""
        else:
            system_prompt = """You are Campus Compass, an AI assistant that synthesizes information from multiple college documents.
Your task is to combine information from different sources to provide a comprehensive answer.
Always cite which document each piece of information comes from.
If information from multiple sources conflicts, mention this in your answer.
If the answer is not in the documents, say so clearly.
Be thorough but concise."""
        
        user_prompt = f"""Context from multiple college documents:
{context}

Question: {question}

Please provide a comprehensive answer by synthesizing information from the relevant documents above."""
        
        # If no chunks and general answers not allowed, return early
        if not retrieved_chunks and not allow_general:
            return {
                'answer': "I couldn't find any relevant information in the available documents.",
                'sources': [],
                'chunks': []
            }
        
        # Generate answer
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            answer = response.content
        except Exception as e:
            answer = f"Error generating answer: {str(e)}. Please check your API key and ensure it's valid."
        
        # Extract unique sources
        sources = list(set([chunk['metadata'].get('source', 'Unknown') for chunk in retrieved_chunks])) if retrieved_chunks else []
        
        return {
            'answer': answer,
            'sources': sources,
            'chunks': retrieved_chunks
        }


