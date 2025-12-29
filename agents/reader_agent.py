# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Reader Agent
Extracts and structures study material from PDFs, slides, and notes
"""

import re
import base64
import io
from typing import List, Dict, Optional
from pathlib import Path
import PyPDF2
from docx import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

# Optional OCR imports (for image-based / scanned PDFs)
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageOps  # type: ignore
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

load_dotenv()


class ReaderAgent:
    """Extracts text, segments into topics, and structures study material"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize LLM for topic classification
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.1,
                google_api_key=api_key
            )
        else:
            self.llm = None

    def _extract_text_using_gemini_vision(self, images: List) -> str:
        """Use Gemini Vision to transcribe handwritten or difficult text from images."""
        if not self.llm:
            return ""
        
        transcribed_text = ""
        try:
            for i, img in enumerate(images):
                # Convert PIL image to base64
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                prompt = "Please transcribe the text from this image exactly. If it is handwritten, do your best to read it accurately. Return only the transcribed text."
                
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/jpeg;base64,{img_str}",
                        },
                    ]
                )
                
                print(f"  → Sending page {i+1} to Gemini Vision...")
                response = self.llm.invoke([message])
                transcribed_text += response.content + "\n\n"
        except Exception as e:
            print(f"Gemini Vision extraction failed: {e}")
        
        return transcribed_text

    def _extract_text_from_pdf_ocr(self, file_path: str) -> str:
        """
        Fallback OCR-based text extraction for image-only / scanned PDFs.
        """
        # On Windows, pdf2image needs poppler. Allow configuring its path via POPPLER_PATH env var.
        poppler_path = os.getenv("POPPLER_PATH") or None
        # Use a slightly lower DPI for faster conversion; allow override via OCR_DPI env var.
        dpi = int(os.getenv("OCR_DPI", "150"))
        
        try:
            if poppler_path:
                images = convert_from_path(file_path, poppler_path=poppler_path, dpi=dpi)
            else:
                images = convert_from_path(file_path, dpi=dpi)
        except Exception as e:
            print(f"Failed to convert PDF to images: {e}")
            return ""

        ocr_mode = os.getenv("OCR_MODE", "printed").lower()
        
        # PRO SOLUTION: Fallback to Gemini Vision for handwriting or if OCR mode is set to handwritten
        if ocr_mode == "handwritten":
            print("  → Handwritten mode detected. Using Gemini Vision for superior extraction...")
            return self._extract_text_using_gemini_vision(images)

        if not OCR_AVAILABLE:
            print("  → Tesseract not found. Falling back to Gemini Vision...")
            return self._extract_text_using_gemini_vision(images)

        # Try Tesseract first for printed text
        ocr_text = ""
        # Optional: allow user to specify tesseract path via env var (especially useful on Windows)
        tess_cmd = os.getenv("TESSERACT_CMD")
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd

        custom_config = os.getenv("OCR_CONFIG")
        if not custom_config:
            custom_config = "--oem 3 --psm 3"

        for img in images:
            # ENHANCED PRE-PROCESSING
            try:
                pil_img = img.convert("L")
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(pil_img)
                pil_img = enhancer.enhance(2.0) 
                pil_img = ImageOps.autocontrast(pil_img)
                threshold = int(os.getenv("OCR_THRESHOLD", "128"))
                pil_img = pil_img.point(lambda x: 255 if x > threshold else 0, mode="1")
            except Exception:
                pil_img = img

            ocr_text += pytesseract.image_to_string(pil_img, config=custom_config) + "\n"
        
        # If Tesseract produced very little or low-quality text, fallback to Gemini Vision
        if len(ocr_text.strip()) < 50:
            print("  → Tesseract output too short. Retrying with Gemini Vision...")
            return self._extract_text_using_gemini_vision(images)
            
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
    
    def classify_topics(self, text: str) -> List[Dict]:
        """Classify text into topics and subtopics using LLM"""
        if not self.llm:
            # Fallback: simple paragraph-based segmentation
            return self._simple_topic_segmentation(text)
        
        try:
            # Keep prompt context shorter for faster LLM response
            trimmed_text = text[:2500]
            prompt = f"""Analyze the following study material and identify distinct topics and subtopics.

Text:
{trimmed_text}

Return a JSON array of topics, each with:
- "topic": main topic name
- "subtopics": list of subtopic names
- "key_points": list of 3-5 key points
- "start_index": approximate position in text (character index)

Format:
[
  {{
    "topic": "Topic Name",
    "subtopics": ["Subtopic 1", "Subtopic 2"],
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "start_index": 0
  }}
]

Only return valid JSON, no additional text."""
            
            messages = [
                SystemMessage(content="You are a study material analyzer. Extract topics and structure from educational content."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            result = response.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                import json
                topics = json.loads(json_match.group(0))
                return topics
        except Exception as e:
            print(f"Error in topic classification: {e}")
        
        # Fallback to simple segmentation
        return self._simple_topic_segmentation(text)
    
    def _simple_topic_segmentation(self, text: str) -> List[Dict]:
        """Simple fallback topic segmentation"""
        # Split by paragraphs and identify potential topics
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        
        topics = []
        current_index = 0
        
        for i, para in enumerate(paragraphs[:10]):  # Limit to first 10 paragraphs
            # Look for topic indicators (headings, capitalized lines, etc.)
            if len(para) < 200 and para.isupper() or para.endswith(':'):
                topic_name = para.strip(':').strip()
                topics.append({
                    "topic": topic_name if topic_name else f"Topic {i+1}",
                    "subtopics": [],
                    "key_points": [],
                    "start_index": current_index
                })
            current_index += len(para) + 2
        
        if not topics:
            topics.append({
                "topic": "Main Content",
                "subtopics": [],
                "key_points": [],
                "start_index": 0
            })
        
        return topics
    
    def split_into_chunks(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Split text into overlapping chunks with topic information"""
        chunks = []
        words = text.split()
        
        if not words:
            return chunks
        
        # Classify topics first
        topics = self.classify_topics(text)
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            
            if current_length + word_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunk_text = self.clean_text(chunk_text)
                
                if chunk_text:
                    # Find relevant topic for this chunk
                    topic_info = self._find_topic_for_chunk(chunk_index * self.chunk_size, topics)
                    
                    chunk_data = {
                        'text': chunk_text,
                        'metadata': {
                            **(metadata or {}),
                            'chunk_index': chunk_index,
                            'topic': topic_info.get('topic', 'General'),
                            'subtopic': topic_info.get('subtopic', ''),
                        }
                    }
                    chunks.append(chunk_data)
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_words = int(self.chunk_overlap / 10)
                current_chunk = current_chunk[-overlap_words:] if overlap_words < len(current_chunk) else []
                current_length = sum(len(w) + 1 for w in current_chunk)
            
            current_chunk.append(word)
            current_length += word_length
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_text = self.clean_text(chunk_text)
            if chunk_text:
                topic_info = self._find_topic_for_chunk(chunk_index * self.chunk_size, topics)
                chunk_data = {
                    'text': chunk_text,
                    'metadata': {
                        **(metadata or {}),
                        'chunk_index': chunk_index,
                        'topic': topic_info.get('topic', 'General'),
                        'subtopic': topic_info.get('subtopic', ''),
                    }
                }
                chunks.append(chunk_data)
        
        return chunks
    
    def _find_topic_for_chunk(self, position: int, topics: List[Dict]) -> Dict:
        """Find the most relevant topic for a chunk based on position"""
        if not topics:
            return {'topic': 'General', 'subtopic': ''}
        
        # Find topic with closest start_index
        closest_topic = topics[0]
        min_distance = abs(topics[0].get('start_index', 0) - position)
        
        for topic in topics[1:]:
            distance = abs(topic.get('start_index', 0) - position)
            if distance < min_distance:
                min_distance = distance
                closest_topic = topic
        
        return {
            'topic': closest_topic.get('topic', 'General'),
            'subtopic': closest_topic.get('subtopics', [None])[0] if closest_topic.get('subtopics') else ''
        }
    
    def process_document(self, file_path: str) -> Dict:
        """Process a single document and return structured data"""
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
            return {'chunks': [], 'topics': [], 'metadata': {}}
        
        if not text:
            return {'chunks': [], 'topics': [], 'metadata': {}}
        
        # Clean text
        text = self.clean_text(text)
        
        # Classify topics
        topics = self.classify_topics(text)
        
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
        
        return {
            'chunks': chunks,
            'topics': topics,
            'metadata': metadata
        }
    
    def process_directory(self, directory_path: str) -> Dict:
        """Process all supported documents in a directory"""
        all_chunks = []
        all_topics = []
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"Directory not found: {directory_path}")
            return {'chunks': [], 'topics': []}
        
        supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                print(f"Processing: {file_path.name}")
                try:
                    result = self.process_document(str(file_path))
                    all_chunks.extend(result['chunks'])
                    all_topics.extend(result['topics'])
                    print(f"  → Created {len(result['chunks'])} chunks from {file_path.name}")
                except Exception as e:
                    print(f"  → Error processing {file_path.name}: {e}")
                    continue
        
        return {
            'chunks': all_chunks,
            'topics': all_topics
        }

