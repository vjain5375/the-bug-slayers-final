"""
Vector Store Management
Handles embedding generation and vector database operations
"""

import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from pathlib import Path
import hashlib


class VectorStore:
    """Manages vector embeddings and semantic search"""
    
    def __init__(self, persist_directory: str = "./vector_db", model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize vector store
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            model_name: Sentence transformer model name
        """
        self.persist_directory = persist_directory
        self.model_name = model_name
        
        # Initialize embedding model
        print(f"Loading embedding model: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        
        # Initialize ChromaDB client
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="campus_compass",
            metadata={"hnsw:space": "cosine"}
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
        
        # Generate embeddings
        print(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        
        # Add to ChromaDB
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"Added {len(texts)} chunks to vector store")
    
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
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Search in ChromaDB - retrieve more results if we need to prioritize
        search_n = n_results * 2 if prioritize_source else n_results
        
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
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
            print("Vector store cleared")
        except Exception as e:
            print(f"Error clearing collection: {e}")
    
    def get_collection_count(self) -> int:
        """Get the number of documents in the collection"""
        try:
            # Check if collection exists
            if self.collection is None:
                return 0
            return self.collection.count()
        except Exception as e:
            # If collection doesn't exist or any error occurs, return 0
            print(f"Error getting collection count: {e}")
            # Try to recreate collection if it was deleted
            try:
                self.collection = self.client.get_or_create_collection(
                    name="campus_compass",
                    metadata={"hnsw:space": "cosine"}
                )
                return self.collection.count()
            except:
                return 0


