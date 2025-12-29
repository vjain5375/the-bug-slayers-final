# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Vector Store Management
Handles embedding generation and vector database operations
"""

# CRITICAL: Set environment variables BEFORE any torch-related imports
import os
import logging

# Prevent torch from attempting to use CUDA/MPS when not available
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TORCH_USE_CUDA_DSA", "0")
os.environ.setdefault("TORCH_DEVICE", "cpu")
# Optionally force MPS off (mac specific)
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "0")

logger = logging.getLogger(__name__)

# Import torch FIRST and force CPU mode
import torch
# Force CPU mode - compatible with all torch versions
if hasattr(torch, 'cuda'):
    # Monkey patch to always return False for CUDA availability
    original_is_available = torch.cuda.is_available
    torch.cuda.is_available = lambda: False
    # Also disable CUDA device count
    if hasattr(torch.cuda, 'device_count'):
        original_device_count = torch.cuda.device_count
        torch.cuda.device_count = lambda: 0

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Union
from pathlib import Path
import hashlib
import numpy as np


class VectorStore:
    """
    Manages vector embeddings and semantic search
    
    Robust initialization:
    - Prefers local SentenceTransformer on CPU
    - Falls back to API-based embeddings (OpenAI/Gemini) if local model fails
    - Configurable via EMBEDDING_BACKEND environment variable
    """
    
    def __init__(
        self, 
        persist_directory: str = "./vector_db", 
        model_name: str = "all-MiniLM-L6-v2",
        embedding_backend: Optional[str] = None
    ):
        """
        Initialize vector store with robust embedding backend
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            model_name: Sentence transformer model name (for local backend)
            embedding_backend: Backend type ('local', 'api', or 'auto'). 
                              Can be overridden by EMBEDDING_BACKEND env var.
        """
        self.persist_directory = persist_directory
        self.model_name = model_name
        
        # Allow override by env/config
        self.embedding_backend = embedding_backend or os.getenv("EMBEDDING_BACKEND", "auto").lower()
        self.embedding_model = None
        
        # Fast-path: prefer API only when an OpenAI key is present (Gemini embeddings are unsupported here)
        if self.embedding_backend == "auto":
            if os.getenv("OPENAI_API_KEY"):
                self.embedding_backend = "api"
                logger.info("Embedding backend auto-switched to 'api' because OPENAI_API_KEY is set (faster startup).")
            else:
                self.embedding_backend = "local"
        
        # If explicitly set to 'api', skip local model
        if self.embedding_backend == "api":
            logger.info("Embedding backend set to 'api' - skipping SentenceTransformer init")
            try:
                self._init_api_backend()
                if self.embedding_backend == "api_unavailable":
                    raise RuntimeError("API backend unavailable or not configured")
                self._init_chromadb()
                return
            except Exception as e:
                logger.warning("API embedding backend unavailable, falling back to local: %s", e)
                self.embedding_backend = "local"
        
        # Try to initialize local SentenceTransformer on CPU
        try:
            # Import locally here after setting env vars to avoid device auto-selection issues
            from sentence_transformers import SentenceTransformer
            
            device = torch.device("cpu")
            logger.info("Attempting to load SentenceTransformer on device=%s, model=%s", device, self.model_name)
            
            # Strategy 1: Load with explicit CPU device
            try:
                self.embedding_model = SentenceTransformer(self.model_name, device=str(device))
                logger.info("SentenceTransformer loaded successfully on CPU.")
                self.embedding_backend = "local"
            except (NotImplementedError, Exception) as e1:
                logger.warning(f"Strategy 1 failed: {e1}")
                
                # Strategy 2: Patch torch.nn.Module.to to prevent device conversion errors
                try:
                    # Save original methods
                    original_to = torch.nn.Module.to
                    original_apply = torch.nn.Module._apply
                    
                    # Create a safe wrapper that prevents NotImplementedError
                    def safe_to(self, device=None, *args, **kwargs):
                        """Safe wrapper that prevents device conversion errors"""
                        if device is None:
                            return self
                        # Always convert to CPU to avoid device errors
                        if str(device).startswith('cuda') or str(device).startswith('gpu'):
                            device = 'cpu'
                        try:
                            return original_to(self, device, *args, **kwargs)
                        except NotImplementedError:
                            # If conversion fails, just return self (already on CPU)
                            return self
                    
                    def safe_apply(self, fn):
                        """Safe _apply that handles device conversion gracefully"""
                        try:
                            return original_apply(self, fn)
                        except NotImplementedError:
                            # If device conversion fails, the model is likely already on CPU
                            # Just return self to continue initialization
                            return self
                    
                    # Apply patches
                    torch.nn.Module.to = safe_to
                    torch.nn.Module._apply = safe_apply
                    
                    # Now try loading the model
                    self.embedding_model = SentenceTransformer(self.model_name)
                    
                    # Restore original methods
                    torch.nn.Module.to = original_to
                    torch.nn.Module._apply = original_apply
                    
                    logger.info("Model loaded successfully with patched device handling")
                    self.embedding_backend = "local"
                except (NotImplementedError, Exception) as e2:
                    logger.warning(f"Strategy 2 failed: {e2}")
                    
                    # Strategy 3: Load with minimal device interaction using model_kwargs
                    try:
                        self.embedding_model = SentenceTransformer(
                            self.model_name,
                            model_kwargs={'torch_dtype': torch.float32}
                        )
                        logger.info("Model loaded successfully with model_kwargs")
                        self.embedding_backend = "local"
                    except (NotImplementedError, Exception) as e3:
                        logger.exception("All local initialization strategies failed. Last error: %s", e3)
                        raise
                        
        except NotImplementedError as nie:
            logger.exception("NotImplementedError initializing SentenceTransformer: %s", nie)
            logger.warning("Falling back to API-based embeddings backend.")
            self._init_api_backend()
        except Exception as e:
            # Catch any other initialization errors (torch device, import errors, resource issues)
            logger.exception("Error initializing SentenceTransformer: %s", e)
            logger.warning("Falling back to API-based embeddings backend.")
            self._init_api_backend()
        
        # Initialize ChromaDB
        self._init_chromadb()
    
    def _init_api_backend(self):
        """
        Initialize an API-based embeddings backend (OpenAI / Gemini / configured provider).
        This method sets attributes so the rest of the app can call embed_text().
        """
        try:
            # Try to import the API embeddings wrapper
            from utils.embeddings_api import APiEmbeddingsWrapper
            self.embedding_model = APiEmbeddingsWrapper()
            self.embedding_backend = "api"
            logger.info("Using API-based embeddings backend: %s", type(self.embedding_model).__name__)
        except ImportError as ie:
            logger.exception("Failed to import API embedding wrapper: %s", ie)
            # Last-resort: provide a minimal stub that raises a helpful error later
            logger.error("API embedding wrapper not available. Embedding calls will raise.")
            self.embedding_model = None
            self.embedding_backend = "api_unavailable"
        except Exception as e:
            logger.exception("Failed to initialize API embedding wrapper: %s", e)
            self.embedding_model = None
            self.embedding_backend = "api_unavailable"
    
    def _init_chromadb(self):
        """Initialize ChromaDB client and collection"""
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="campus_compass",
            metadata={"hnsw:space": "cosine"}
        )
    
    def embed_text(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Unified embedding function used by the rest of the code.
        Accepts single string or list[str], returns list[vector].
        
        Args:
            texts: Single string or list of strings to embed
            
        Returns:
            List of embedding vectors (lists of floats)
        """
        if self.embedding_backend == "local" and self.embedding_model is not None:
            # Normalize input to list
            if isinstance(texts, str):
                texts = [texts]
            # sentence_transformers returns numpy arrays
            embeddings = self.embedding_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
            # Convert to list of lists
            if isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            return embeddings
        elif self.embedding_backend.startswith("api"):
            # Use API wrapper
            if self.embedding_model is None:
                raise RuntimeError(
                    "API embedding backend not configured. "
                    "Set EMBEDDING_BACKEND=api and provide API keys (OPENAI_API_KEY or GOOGLE_API_KEY)."
                )
            return self.embedding_model.embed(texts)
        else:
            raise RuntimeError(
                f"No valid embedding backend available. Backend: {self.embedding_backend}. "
                f"Set EMBEDDING_BACKEND=local or EMBEDDING_BACKEND=api"
            )
    
    def _generate_id(self, text: str, metadata: Dict) -> str:
        """Generate unique ID for a chunk"""
        content = f"{text}_{metadata.get('source', '')}_{metadata.get('chunk_index', 0)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def add_documents(self, chunks: List[Dict]):
        """
        Add document chunks to vector store
        
        Args:
            chunks: List of dicts with 'text' and 'metadata' keys
        """
        if not chunks:
            return
        
        texts = [chunk['text'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        ids = [self._generate_id(chunk['text'], chunk['metadata']) for chunk in chunks]
        
        # Generate embeddings using unified interface
        logger.info(f"Generating embeddings for {len(texts)} chunks using backend: {self.embedding_backend}")
        embeddings = self.embed_text(texts)
        
        # Add to ChromaDB
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(texts)} chunks to vector store")
    
    def search(self, query: str, n_results: int = 5, prioritize_source: Optional[str] = None) -> List[Dict]:
        """
        Search for similar chunks
        
        Args:
            query: Search query
            n_results: Number of results to return
            prioritize_source: If provided, prioritize chunks from this source (filename)
            
        Returns:
            List of dicts with 'text', 'metadata', and 'distance' keys
        """
        # Generate query embedding using unified interface
        query_embeddings = self.embed_text([query])
        query_embedding = query_embeddings[0]
        
        # Search in ChromaDB - retrieve more results if we need to prioritize
        search_n = n_results * 2 if prioritize_source else n_results
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=search_n
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        # If prioritizing a source, reorder to put that source first
        if prioritize_source and formatted_results:
            prioritized = []
            others = []
            source_name = Path(prioritize_source).name if prioritize_source else None
            
            for chunk in formatted_results:
                chunk_source = chunk['metadata'].get('source', '')
                if source_name and chunk_source == source_name:
                    prioritized.append(chunk)
                else:
                    others.append(chunk)
            
            # Combine: prioritized chunks first, then others, limit to n_results
            formatted_results = (prioritized + others)[:n_results]
        
        return formatted_results
    
    def clear_collection(self):
        """Clear all documents from the collection"""
        try:
            self.client.delete_collection(name="campus_compass")
            self.collection = self.client.get_or_create_collection(
                name="campus_compass",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Vector store cleared")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
    
    def get_collection_count(self) -> int:
        """Get the number of documents in the collection"""
        try:
            # Check if collection exists
            if self.collection is None:
                return 0
            return self.collection.count()
        except Exception as e:
            # If collection doesn't exist or any error occurs, return 0
            logger.warning(f"Error getting collection count: {e}")
            # Try to recreate collection if it was deleted
            try:
                self.collection = self.client.get_or_create_collection(
                    name="campus_compass",
                    metadata={"hnsw:space": "cosine"}
                )
                return self.collection.count()
            except:
                return 0
