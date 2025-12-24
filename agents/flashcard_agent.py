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
    
    def generate_flashcards(
        self,
        text_chunks: List[Dict],
        num_flashcards: int = 10,
        difficulty_mix: str = "easy_medium_hard",
    ) -> List[Dict]:
        """
        Generate flashcards from text chunks
        
        Args:
            text_chunks: List of text chunks with metadata
            num_flashcards: Number of flashcards to generate
            difficulty_mix: one of ["easy_medium", "medium_hard", "easy_medium_hard"]
            
        Returns:
            List of flashcard dictionaries with 'question' and 'answer' keys
        """
        if not text_chunks:
            return []
        
        target_counts = self._build_target_counts(num_flashcards, difficulty_mix)
        target_difficulties = [
            diff for diff, count in target_counts.items() for _ in range(count)
        ]
        if not target_difficulties:
            target_difficulties = ["medium"] * num_flashcards

        if not self.llm:
            return self._simple_flashcard_generation(text_chunks, target_difficulties)
        
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
5. Difficulty mix: {target_counts} (use these counts as closely as possible)

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
                            'difficulty': card.get('difficulty', 'medium').lower()
                        })

                # Ensure count and difficulty mix by topping up with deterministic cards
                if len(validated) < num_flashcards:
                    simple_cards = self._simple_flashcard_generation(
                        text_chunks,
                        target_difficulties[len(validated):]
                    )
                    validated.extend(simple_cards)

                # If still short, duplicate best available to meet count
                while len(validated) < num_flashcards and validated:
                    validated.append(validated[len(validated) % len(validated)])
                # If nothing validated, fall back entirely
                if not validated:
                    validated = self._simple_flashcard_generation(text_chunks, target_difficulties[:num_flashcards])

                # Trim and align difficulties to target list
                validated = validated[:num_flashcards]
                for idx, card in enumerate(validated):
                    if idx < len(target_difficulties):
                        card['difficulty'] = target_difficulties[idx]

                return validated
        except Exception as e:
            print(f"Error generating flashcards: {e}")
        
        # Fallback to simple generation
        return self._simple_flashcard_generation(text_chunks, target_difficulties)
    
    def _simple_flashcard_generation(self, text_chunks: List[Dict], target_difficulties: List[str]) -> List[Dict]:
        """Simple fallback flashcard generation honoring target difficulties"""
        flashcards = []
        if not text_chunks:
            return flashcards

        # Cycle through chunks and difficulties
        for idx, difficulty in enumerate(target_difficulties):
            chunk = text_chunks[idx % len(text_chunks)]
            text = chunk.get('text', '')
            topic = chunk.get('metadata', {}).get('topic', 'General')
            
            # Simple extraction: use first sentence as question seed, next sentences as answer
            sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
            question_seed = sentences[0] if sentences else text[:80] or "this topic"
            answer_seed = ' '.join(sentences[1:3]).strip() if len(sentences) > 1 else text[:200]
            if not answer_seed:
                answer_seed = "Review this concept."
            if not answer_seed.endswith('.'):
                answer_seed = answer_seed + '.'
            
            flashcards.append({
                'question': f"What is {question_seed}?",
                'answer': answer_seed,
                'topic': topic,
                'difficulty': difficulty
            })
        
        # If still short, pad with generic reminders to reach target count
        while len(flashcards) < len(target_difficulties):
            difficulty = target_difficulties[len(flashcards)]
            flashcards.append({
                'question': "Review key concept?",
                'answer': "Focus on the most important definition or process in this topic.",
                'topic': "General",
                'difficulty': difficulty
            })

        return flashcards
    
    def _build_target_counts(self, total: int, mix: str) -> Dict[str, int]:
        """Compute how many cards per difficulty based on mix selection."""
        mix_map = {
            "easy_medium": ["easy", "medium"],
            "medium_hard": ["medium", "hard"],
            "easy_medium_hard": ["easy", "medium", "hard"],
        }
        levels = mix_map.get((mix or "easy_medium_hard").lower(), ["easy", "medium", "hard"])
        counts = {k: 0 for k in ["easy", "medium", "hard"]}
        for i in range(total):
            level = levels[i % len(levels)]
            counts[level] += 1
        return counts
    
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

