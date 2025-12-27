"""
API-based Embeddings Wrapper
Provides fallback embedding generation using OpenAI or Google Gemini APIs
"""

import os
import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)


class APiEmbeddingsWrapper:
    """
    Wrapper for API-based embeddings (OpenAI or Google Gemini)
    Falls back to API when local SentenceTransformer fails
    """
    
    def __init__(self):
        """Initialize API embeddings provider"""
        self.provider = os.getenv("EMB_PROVIDER", "gemini").lower()
        self.api_key = None
        self.client = None
        
        # Try to get API key
        if self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            if self.api_key:
                try:
                    import openai
                    self.client = openai.OpenAI(api_key=self.api_key)
                    logger.info("Initialized OpenAI embeddings client")
                except ImportError:
                    logger.warning("openai package not installed. Install with: pip install openai")
                    self.api_key = None
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.api_key = None
        elif self.provider == "gemini":
            self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if self.api_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=self.api_key)
                    self.client = genai
                    logger.info("Initialized Google Gemini embeddings client")
                except ImportError:
                    logger.warning("google-generativeai package not installed. Install with: pip install google-generativeai")
                    self.api_key = None
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini client: {e}")
                    self.api_key = None
        
        if not self.api_key:
            logger.warning(
                f"No API key found for {self.provider} embeddings. "
                f"Set OPENAI_API_KEY or GOOGLE_API_KEY environment variable. "
                f"Embedding calls will raise RuntimeError."
            )
    
    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings using API provider
        
        Args:
            texts: Single string or list of strings to embed
            
        Returns:
            List of embedding vectors (lists of floats)
        """
        if not self.api_key or not self.client:
            raise RuntimeError(
                f"API embedding backend not configured. "
                f"Set {self.provider.upper()}_API_KEY environment variable or set EMBEDDING_BACKEND=local to use local model."
            )
        
        # Normalize input to list
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            if self.provider == "openai":
                return self._embed_openai(texts)
            elif self.provider == "gemini":
                return self._embed_gemini(texts)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            logger.exception(f"Error generating embeddings via API: {e}")
            raise RuntimeError(f"Failed to generate embeddings via {self.provider} API: {e}") from e
    
    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",  # or text-embedding-ada-002
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI embedding API error: {e}")
            raise
    
    def _embed_gemini(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Google Gemini API (models/embedding-001)"""
        try:
            # Use the dedicated embedding model
            result = self.client.embed_content(
                model="models/embedding-001",
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            raise

