"""
Document Processing Pipeline
Handles ingestion, cleaning, and chunking of college documents
"""

import os
import re
from typing import List, Dict
from pathlib import Path
import PyPDF2
from docx import Document

# Optional OCR imports (for image-based / scanned PDFs)
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image  # noqa: F401  # imported for type / backend
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


class DocumentProcessor:
    """Processes various document formats and splits them into chunks"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def _extract_text_from_pdf_ocr(self, file_path: str) -> str:
        """
        Fallback OCR-based text extraction for image-only / scanned PDFs.

        This requires:
          - Tesseract installed on the system
          - pytesseract, pdf2image, Pillow installed in the environment
        """
        if not OCR_AVAILABLE:
            return ""

        # Optional: allow user to specify tesseract path via env var (especially useful on Windows)
        tess_cmd = os.getenv("TESSERACT_CMD")
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd

        ocr_text = ""
        try:
            images = convert_from_path(file_path)
            for img in images:
                ocr_text += pytesseract.image_to_string(img) + "\n"
        except Exception as e:
            print(f"OCR fallback failed for {file_path}: {e}")
        return ocr_text

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file, with OCR fallback for scanned documents."""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    try:
                        page_text = page.extract_text() or ""
                    except Exception as e:
                        print(f"Error extracting text from page in {file_path}: {e}")
                        page_text = ""
                    text += page_text + ("\n" if page_text else "")

            # If no text was extracted at all, try OCR as a fallback
            if not text.strip():
                if OCR_AVAILABLE:
                    print(f"No selectable text found in {file_path}. Trying OCR fallback...")
                    text = self._extract_text_from_pdf_ocr(file_path)
                else:
                    print(
                        f"No selectable text found in {file_path}, and OCR dependencies are missing.\n"
                        "Install Tesseract on your system and `pytesseract`, `pdf2image`, `Pillow` "
                        "in your Python environment to enable OCR for scanned PDFs."
                    )
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
        return text
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error reading DOCX {file_path}: {e}")
        return text
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading TXT {file_path}: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', '', text)
        # Trim
        text = text.strip()
        return text
    
    def split_into_chunks(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Split text into overlapping chunks"""
        chunks = []
        words = text.split()
        
        if not words:
            return chunks
        
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            
            if current_length + word_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunk_text = self.clean_text(chunk_text)
                
                if chunk_text:
                    chunk_data = {
                        'text': chunk_text,
                        'metadata': metadata or {}
                    }
                    chunks.append(chunk_data)
                
                # Start new chunk with overlap
                overlap_words = int(self.chunk_overlap / 10)  # Approximate word count
                current_chunk = current_chunk[-overlap_words:] if overlap_words < len(current_chunk) else []
                current_length = sum(len(w) + 1 for w in current_chunk)
            
            current_chunk.append(word)
            current_length += word_length
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_text = self.clean_text(chunk_text)
            if chunk_text:
                chunk_data = {
                    'text': chunk_text,
                    'metadata': metadata or {}
                }
                chunks.append(chunk_data)
        
        return chunks
    
    def process_document(self, file_path: str) -> List[Dict]:
        """Process a single document and return chunks"""
        file_path = Path(file_path)
        file_name = file_path.name
        file_ext = file_path.suffix.lower()
        
        # Extract text based on file type
        if file_ext == '.pdf':
            text = self.extract_text_from_pdf(str(file_path))
        elif file_ext in ['.docx', '.doc']:
            text = self.extract_text_from_docx(str(file_path))
        elif file_ext == '.txt':
            text = self.extract_text_from_txt(str(file_path))
        else:
            print(f"Unsupported file type: {file_ext}")
            return []
        
        if not text:
            return []
        
        # Clean text
        text = self.clean_text(text)
        
        # Create metadata
        metadata = {
            'source': file_name,
            'file_path': str(file_path),
            'file_type': file_ext
        }
        
        # Split into chunks
        chunks = self.split_into_chunks(text, metadata)
        
        # Add chunk index to metadata
        for i, chunk in enumerate(chunks):
            chunk['metadata']['chunk_index'] = i
            chunk['metadata']['total_chunks'] = len(chunks)
        
        return chunks
    
    def process_directory(self, directory_path: str) -> List[Dict]:
        """Process all supported documents in a directory (root level only)"""
        all_chunks = []
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"Directory not found: {directory_path}")
            return all_chunks
        
        # Supported file extensions
        supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
        
        # Process all files in root directory only (not subdirectories)
        # This matches the behavior of get_document_files()
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                print(f"Processing: {file_path.name}")
                try:
                    chunks = self.process_document(str(file_path))
                    all_chunks.extend(chunks)
                    print(f"  → Created {len(chunks)} chunks from {file_path.name}")
                except Exception as e:
                    print(f"  → Error processing {file_path.name}: {e}")
                    continue
        
        print(f"Total chunks created from {len([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions])} document(s): {len(all_chunks)}")
        return all_chunks


