"""Utility modules for the application"""

import os
from pathlib import Path
from typing import List, Optional


def ensure_documents_directory() -> Path:
    """Ensure documents directory exists"""
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    return docs_dir


def get_document_files() -> List[str]:
    """Get list of all document files in documents directory (root only, no subdirectories)"""
    docs_dir = ensure_documents_directory()
    supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
    
    # Only look in root directory, not subdirectories (since we only allow single file uploads)
    files = []
    seen_paths = set()  # Track seen files to avoid duplicates
    
    # Get all files in root directory only
    for file_path in docs_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            # Use absolute resolved path for deduplication
            normalized_path = str(file_path.resolve())
            if normalized_path not in seen_paths:
                seen_paths.add(normalized_path)
                files.append(str(file_path))
    
    return files


def format_sources(sources: List[str]) -> str:
    """Format source list for display"""
    if not sources:
        return "No sources"
    
    if len(sources) == 1:
        return f"Source: {sources[0]}"
    
    return f"Sources: {', '.join(sources)}"


def get_latest_document() -> Optional[str]:
    """Get the most recently uploaded/modified document file path"""
    doc_files = get_document_files()
    if not doc_files:
        return None
    
    # Get file modification times and return the most recent
    files_with_time = []
    for doc_path_str in doc_files:
        doc_path = Path(doc_path_str)
        if doc_path.exists():
            try:
                mtime = doc_path.stat().st_mtime
                files_with_time.append((mtime, doc_path_str))
            except Exception:
                continue
    
    if not files_with_time:
        return None
    
    # Sort by modification time (most recent first) and return the latest
    files_with_time.sort(reverse=True)
    return files_with_time[0][1]


def detect_multi_document_intent(question: str) -> bool:
    """Detect if the question indicates a need for multi-document synthesis"""
    question_lower = question.lower()
    
    # Keywords that suggest multi-document needs
    multi_doc_keywords = [
        'all documents', 'multiple documents', 'both documents', 'across documents',
        'compare', 'difference between', 'both', 'all sources', 'multiple sources',
        'synthesize', 'combine', 'together', 'from all', 'from multiple',
        'across all', 'in all', 'every document'
    ]
    
    # Check if question contains multi-document keywords
    for keyword in multi_doc_keywords:
        if keyword in question_lower:
            return True
    
    return False


__all__ = [
    'ensure_documents_directory',
    'get_document_files',
    'format_sources',
    'get_latest_document',
    'detect_multi_document_intent'
]
