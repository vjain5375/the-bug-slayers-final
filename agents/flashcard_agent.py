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
                model="gemini-2.5-flash",
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
        
        # Pre-clean chunks and drop low-signal ones
        cleaned_chunks = []
        for chunk in text_chunks:
            raw_text = chunk.get('text', '')
            cleaned_text = self._strip_boilerplate(raw_text)
            sentences = self._clean_and_split_sentences(cleaned_text)
            if len(cleaned_text) < 80 or len(sentences) < 2:
                continue
            cleaned_chunks.append({
                "text": cleaned_text,
                "sentences": sentences,
                "metadata": chunk.get('metadata', {})
            })
        
        if not cleaned_chunks:
            return []
        
        target_counts = self._build_target_counts(num_flashcards, difficulty_mix)
        target_difficulties = [
            diff for diff, count in target_counts.items() for _ in range(count)
        ]
        if not target_difficulties:
            target_difficulties = ["medium"] * num_flashcards

        if not self.llm:
            return self._simple_flashcard_generation(cleaned_chunks, target_difficulties)
        
        # Combine chunks into context
        context_parts = []
        for chunk in cleaned_chunks[:6]:  # Use top 6 cleaned chunks
            topic = chunk.get('metadata', {}).get('topic', 'General')
            text = chunk.get('text', '')
            context_parts.append(f"[Topic: {topic}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        try:
            prompt = f"""You are a flashcard generator for study materials. Create concise, effective flashcards that avoid boilerplate and placeholders.

Study Material:
{context[:1200]}  # Limit context size

Create exactly {num_flashcards} question-answer pairs that:
1. Cover key concepts and definitions
2. Are concise (answers should be 1-3 sentences)
3. Test understanding, not just memorization
4. Cover different topics from the material
5. Difficulty mix: {target_counts} (use these counts as closely as possible)
6. Do NOT include copyright/ISBN/legal text. Do NOT return empty or placeholder questions.

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
                seen_questions = set()
                min_q_len = 16
                min_a_len = 24
                max_len = 240
                for card in flashcards:
                    if 'question' in card and 'answer' in card:
                        question = self._strip_boilerplate(card['question'].strip())[:max_len]
                        answer = self._strip_boilerplate(card['answer'].strip())[:max_len]
                        if len(question) < min_q_len or len(answer) < min_a_len:
                            continue
                        if question.lower() in seen_questions:
                            continue
                        seen_questions.add(question.lower())
                        validated.append({
                            'question': question,
                            'answer': answer,
                            'topic': card.get('topic', 'General'),
                            'difficulty': card.get('difficulty', 'medium').lower()
                        })

                # Ensure count and difficulty mix by topping up with deterministic cards
                if len(validated) < num_flashcards:
                    simple_cards = self._simple_flashcard_generation(
                        cleaned_chunks,
                        target_difficulties[len(validated):]
                    )
                    validated.extend(simple_cards)

                # Trim and align difficulties to target list
                validated = validated[:num_flashcards]
                for idx, card in enumerate(validated):
                    if idx < len(target_difficulties):
                        card['difficulty'] = target_difficulties[idx]

                return validated
        except Exception as e:
            print(f"Error generating flashcards: {e}")
        
        # Fallback to simple generation
        return self._simple_flashcard_generation(cleaned_chunks, target_difficulties)
    
    def _simple_flashcard_generation(self, cleaned_chunks: List[Dict], target_difficulties: List[str]) -> List[Dict]:
        """Simple fallback flashcard generation honoring target difficulties"""
        flashcards = []
        if not cleaned_chunks:
            return flashcards
        
        # Cycle through chunks and difficulties
        for idx, difficulty in enumerate(target_difficulties):
            chunk = cleaned_chunks[idx % len(cleaned_chunks)]
            text = chunk.get('text', '')
            sentences = chunk.get('sentences', [])
            topic = chunk.get('metadata', {}).get('topic', 'General')
            if len(sentences) < 2:
                continue
            
            question_seed = sentences[0][:140]
            answer_seed = ' '.join(sentences[1:3]).strip() if len(sentences) > 1 else text[:220]
            if not answer_seed:
                answer_seed = "Review this concept."
            if len(answer_seed) > 240:
                answer_seed = answer_seed[:240]
            if not answer_seed.endswith('.'):
                answer_seed = answer_seed + '.'
            
            question_text = f"What is {question_seed}?".strip()
            if len(question_text) < 16 or len(answer_seed) < 24:
                continue
            
            flashcards.append({
                'question': question_text,
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
    
    def _strip_boilerplate(self, text: str) -> str:
        """Remove boilerplate like copyright/ISBN/dates and trim length."""
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            l = line.strip()
            l_lower = l.lower()
            if any(keyword in l_lower for keyword in [
                "copyright", "isbn", "rights reserved", "revision history", "first release", "typo updates",
                "all rights reserved", "page ", "chapter "
            ]):
                continue
            if re.match(r"^\d{4}-\d{2}-\d{2}", l):
                continue
            if re.match(r"^[A-Z0-9 ,:-]{15,}$", l):
                continue
            lines.append(l)
        cleaned = " ".join(lines)
        # Collapse whitespace and truncate
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:400]
    
    def _clean_and_split_sentences(self, text: str) -> List[str]:
        """Split text into reasonable sentences, filtering very short fragments."""
        if not text:
            return []
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 4]
        return sentences
    
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
    
    def export_to_csv(self, flashcards: List[Dict]) -> str:
        """Export flashcards to Anki-compatible CSV string"""
        if not flashcards:
            return ""
        
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Anki format: Front, Back, Tags
        writer.writerow(['Front', 'Back', 'Tags'])
        
        for card in flashcards:
            topic = card.get('topic', 'General').replace(' ', '_')
            difficulty = card.get('difficulty', 'medium')
            tags = f"study_assistant {topic} {difficulty}"
            writer.writerow([card['question'], card['answer'], tags])
            
        return output.getvalue()

