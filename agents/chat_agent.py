# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Chat/Doubt Agent
Answers contextual questions about uploaded study materials
"""

from typing import List, Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
import logging
from dotenv import load_dotenv

try:
    load_dotenv()
except UnicodeDecodeError:
    pass
except Exception:
    pass
logger = logging.getLogger(__name__)

# Try importing google-generativeai as fallback
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class DirectGenAIChat:
    """Direct wrapper for google-generativeai when langchain fails"""
    def __init__(self, api_key: str):
        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai not available")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def invoke(self, messages):
        # Convert langchain messages to simple text
        text_content = ""
        for msg in messages:
            if hasattr(msg, 'content'):
                text_content += msg.content + "\n"
        
        response = self.model.generate_content(text_content)
        
        class Response:
            def __init__(self, content):
                self.content = content
        
        return Response(response.text if response.text else "No response generated")


class ChatAgent:
    """Answers questions using content extracted from study materials"""
    
    def __init__(self, vector_store=None):
        self.vector_store = vector_store
        
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.llm = None
        
        if api_key:
            # Configure API key for direct google-generativeai if available
            if GENAI_AVAILABLE:
                try:
                    genai.configure(api_key=api_key)
                except Exception:
                    pass
            
            # Try multiple model names in order of preference
            model_names = [
                "gemini-1.5-pro",
                "gemini-pro", 
                "gemini-1.5-flash",
                "models/gemini-1.5-pro",
                "models/gemini-pro"
            ]
            
            for model_name in model_names:
                try:
                    self.llm = ChatGoogleGenerativeAI(
                        model=model_name,
                        temperature=0.2,
                        google_api_key=api_key
                    )
                    logger.info(f"Successfully initialized Gemini model: {model_name}")
                    break  # Model initialized successfully
                except Exception as e:
                    logger.debug(f"Failed to initialize {model_name}: {str(e)}")
                    self.llm = None
                    continue  # Try next model
            
            # If langchain fails, try direct google-generativeai as last resort
            if not self.llm and GENAI_AVAILABLE:
                try:
                    # Create a wrapper that uses google-generativeai directly
                    self.llm = DirectGenAIChat(api_key)
                    logger.info("Using direct google-generativeai as fallback")
                except Exception as e:
                    logger.warning(f"Failed to initialize direct GenAI: {str(e)}")
            
            if not self.llm:
                logger.warning(f"Failed to initialize any Gemini model. Please check your API key and model availability.")
    
    def answer_question(self, question: str, n_chunks: int = 5, prioritize_source: Optional[str] = None) -> Dict:
        """
        Answer a question using RAG from study materials
        
        Args:
            question: User's question
            n_chunks: Number of relevant chunks to retrieve
            prioritize_source: Optional filename to prioritize in search
            
        Returns:
            Dict with 'answer', 'sources', and 'chunks' keys
        """
        if not self.vector_store or not self.llm:
            return {
                'answer': "Chat agent not properly initialized. Please ensure vector store and API key are configured.",
                'sources': [],
                'chunks': []
            }
        
        # Retrieve relevant chunks (prioritize latest document if specified)
        retrieved_chunks = self.vector_store.search(question, n_results=n_chunks, prioritize_source=prioritize_source)
        
        # Filter by relevance
        relevant_chunks = []
        for chunk in retrieved_chunks:
            distance = chunk.get('distance', 1.0)
            if distance is not None and distance < 0.8:
                relevant_chunks.append(chunk)
        
        if not relevant_chunks and retrieved_chunks:
            relevant_chunks = retrieved_chunks[:3]
        
        # Format context
        if relevant_chunks:
            context_parts = []
            for i, chunk in enumerate(relevant_chunks, 1):
                source = chunk['metadata'].get('source', 'Unknown')
                topic = chunk['metadata'].get('topic', 'General')
                text = chunk['text']
                context_parts.append(f"[Source {i}: {source}, Topic: {topic}]\n{text}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant information found in the study materials."
        
        # Create prompt
        system_prompt = """You are a helpful study assistant that answers questions based on uploaded study materials.

CRITICAL RULES:
1. Your answers MUST be based ONLY on the provided context from study materials.
2. If the context does NOT contain information relevant to the question, you MUST say: "I don't have that information in the uploaded materials."
3. DO NOT make up information or use general knowledge if it's not in the context.
4. Provide clear explanations with examples when possible.
5. Cite which document/topic the information comes from.

When answering:
- Be clear and concise
- Use examples from the context when helpful
- Reference specific topics or sections
- If information is from multiple sources, mention all relevant sources"""
        
        user_prompt = f"""Context from study materials:
{context}

Question: {question}

Please provide a helpful answer based ONLY on the context above, or state that the information is not available."""
        
        try:
            if not self.llm:
                return {
                    'answer': "⚠️ Chat agent not initialized. Please check your GOOGLE_API_KEY in the .env file.",
                    'sources': [],
                    'chunks': []
                }
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            answer = response.content
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "NOT_FOUND" in error_msg:
                answer = "⚠️ Model not found. Please check your API key and ensure you have access to Gemini models. If the issue persists, try updating your langchain-google-genai package."
            elif "API key" in error_msg.lower() or "authentication" in error_msg.lower():
                answer = "⚠️ API key error. Please check your GOOGLE_API_KEY in the .env file and ensure it's valid."
            else:
                answer = f"⚠️ Error generating answer: {error_msg}. Please check your API configuration."
        
        # Extract unique sources
        sources = list(set([
            chunk['metadata'].get('source', 'Unknown')
            for chunk in relevant_chunks
        ])) if relevant_chunks else []
        
        return {
            'answer': answer,
            'sources': sources,
            'chunks': relevant_chunks
        }
    
    def explain_concept(self, concept: str, n_chunks: int = 5) -> Dict:
        """Provide detailed explanation of a concept"""
        question = f"Explain {concept} in detail with examples"
        return self.answer_question(question, n_chunks)
    
    def get_topic_summary(self, topic: str, n_chunks: int = 5) -> Dict:
        """Get a summary of a specific topic"""
        question = f"Provide a comprehensive summary of {topic}"
        return self.answer_question(question, n_chunks)

