"""
Flashcard Agent
Automatically generates Q/A flashcards from study material
"""

import json
import re
from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


class FlashcardAgent:
    """Generates concise Q/A flashcards for quick revision"""
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.3,
                google_api_key=api_key
            )
        else:
            self.llm = None
    
    def generate_flashcards(self, text_chunks: List[Dict], num_flashcards: int = 10) -> List[Dict]:
        """
        Generate flashcards from text chunks
        
        Args:
            text_chunks: List of text chunks with metadata
            num_flashcards: Number of flashcards to generate
            
        Returns:
            List of flashcard dictionaries with 'question' and 'answer' keys
        """
        if not self.llm:
            return self._simple_flashcard_generation(text_chunks, num_flashcards)
        
        # Combine chunks into context
        context_parts = []
        for chunk in text_chunks[:5]:  # Use top 5 chunks
            topic = chunk.get('metadata', {}).get('topic', 'General')
            text = chunk.get('text', '')
            context_parts.append(f"[Topic: {topic}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        try:
            prompt = f"""You are a flashcard generator for study materials. Create concise, effective flashcards.

Study Material:
{context[:4000]}  # Limit context size

Create exactly {num_flashcards} question-answer pairs that:
1. Cover key concepts and definitions
2. Are concise (answers should be 1-3 sentences)
3. Test understanding, not just memorization
4. Cover different topics from the material

Return ONLY a valid JSON array in this format:
[
  {{
    "question": "What is...?",
    "answer": "Brief, clear answer.",
    "topic": "Topic name",
    "difficulty": "easy|medium|hard"
  }},
  ...
]

Only return the JSON array, no additional text or explanation."""
            
            messages = [
                SystemMessage(content="You are an expert at creating educational flashcards. Generate clear, concise Q/A pairs."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            result = response.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                flashcards = json.loads(json_match.group(0))
                # Validate and clean flashcards
                validated = []
                for card in flashcards:
                    if 'question' in card and 'answer' in card:
                        validated.append({
                            'question': card['question'].strip(),
                            'answer': card['answer'].strip(),
                            'topic': card.get('topic', 'General'),
                            'difficulty': card.get('difficulty', 'medium')
                        })

                # If the LLM returned fewer cards than requested, top up using the
                # simple deterministic generator so the user still gets approximately
                # the number they selected (as long as there is enough content).
                if len(validated) < num_flashcards:
                    needed = num_flashcards - len(validated)
                    simple_cards = self._simple_flashcard_generation(text_chunks, num_flashcards)
                    for card in simple_cards:
                        if len(validated) >= num_flashcards:
                            break
                        validated.append(card)

                return validated[:num_flashcards]
        except Exception as e:
            print(f"Error generating flashcards: {e}")
        
        # Fallback to simple generation
        return self._simple_flashcard_generation(text_chunks, num_flashcards)
    
    def _simple_flashcard_generation(self, text_chunks: List[Dict], num_flashcards: int) -> List[Dict]:
        """Simple fallback flashcard generation"""
        flashcards = []
        
        for chunk in text_chunks[:num_flashcards]:
            text = chunk.get('text', '')
            topic = chunk.get('metadata', {}).get('topic', 'General')
            
            # Simple extraction: first sentence as question, rest as answer
            sentences = text.split('.')
            if len(sentences) >= 2:
                question = f"What is {sentences[0].strip()}?"
                answer = '. '.join(sentences[1:3]).strip() + '.'
                
                flashcards.append({
                    'question': question,
                    'answer': answer,
                    'topic': topic,
                    'difficulty': 'medium'
                })
        
        return flashcards
    
    def save_flashcards(self, flashcards: List[Dict], file_path: str = "outputs/flashcards.json"):
        """Save flashcards to JSON file"""
        output_dir = Path(file_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(flashcards, f, indent=2, ensure_ascii=False)
    
    def load_flashcards(self, file_path: str = "outputs/flashcards.json") -> List[Dict]:
        """Load flashcards from JSON file"""
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def generate_topic_flashcards(self, topic: str, chunks: List[Dict], num_flashcards: int = 5) -> List[Dict]:
        """Generate flashcards for a specific topic"""
        # Filter chunks by topic
        topic_chunks = [
            chunk for chunk in chunks
            if chunk.get('metadata', {}).get('topic', '').lower() == topic.lower()
        ]
        
        if not topic_chunks:
            return []
        
        return self.generate_flashcards(topic_chunks, num_flashcards)

