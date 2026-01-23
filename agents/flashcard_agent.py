# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Flashcard Agent
Automatically generates Q/A flashcards from study material
"""

import json
import re
import logging
from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    load_dotenv()
except UnicodeDecodeError:
    pass
except Exception:
    pass


class FlashcardAgent:
    """Generates concise Q/A flashcards for quick revision"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
                temperature=0.3,
                google_api_key=api_key
            )
            self.logger.info("FlashcardAgent initialized with LLM")
        else:
            self.llm = None
            self.logger.warning("FlashcardAgent initialized WITHOUT LLM - will use fallback generation")
    
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
        self.logger.info(f"generate_flashcards called: chunks={len(text_chunks) if text_chunks else 0}, num={num_flashcards}, mix={difficulty_mix}")
        
        if not text_chunks:
            self.logger.warning("generate_flashcards: No text chunks provided - returning empty list")
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
        """Simple fallback flashcard generation honoring target difficulties with unique questions"""
        flashcards = []
        if not cleaned_chunks:
            return flashcards
        
        # Build a global pool of unique, high-quality sentences from all chunks
        sentence_pool = []  # (sentence, topic, chunk_idx)
        used_sentences = set()
        
        for chunk_idx, chunk in enumerate(cleaned_chunks):
            sentences = chunk.get('sentences', [])
            topic = chunk.get('metadata', {}).get('topic', 'General')
            
            for sent in sentences:
                sent_clean = sent.strip()
                sent_lower = sent_clean.lower()
                
                # Skip if too short or too long
                if len(sent_clean) < 20 or len(sent_clean) > 200:
                    continue
                
                # Skip header-like sentences
                if re.match(r"^(lab|experiment|practical|assignment|project|ques|q\d|ans|a\d)", sent_lower):
                    continue
                
                # Skip sentences with roll numbers
                if re.search(r"\b\d{2}[A-Z]{2,4}\d{3,5}\b", sent_clean, re.IGNORECASE):
                    continue
                
                # Skip if mostly numbers or special chars
                alpha_ratio = sum(c.isalpha() for c in sent_clean) / max(len(sent_clean), 1)
                if alpha_ratio < 0.5:
                    continue
                
                # Skip duplicates (case-insensitive)
                if sent_lower in used_sentences:
                    continue
                
                used_sentences.add(sent_lower)
                sentence_pool.append((sent_clean, topic, chunk_idx))
        
        # Question templates for variety
        question_templates = [
            "What is {}?",
            "Explain {}.",
            "Define {}.",
            "Describe {}.",
            "What do you understand by {}?",
        ]
        
        # Generate flashcards using different sentences
        used_question_seeds = set()
        template_idx = 0
        
        for idx, difficulty in enumerate(target_difficulties):
            if not sentence_pool:
                break
            
            # Find an unused sentence for the question
            question_sent = None
            answer_parts = []
            
            for pool_idx, (sent, topic, chunk_idx) in enumerate(sentence_pool):
                sent_key = sent.lower()[:50]
                if sent_key not in used_question_seeds:
                    question_sent = sent
                    question_topic = topic
                    used_question_seeds.add(sent_key)
                    
                    # Get neighboring sentences from same chunk for answer
                    chunk = cleaned_chunks[chunk_idx]
                    chunk_sentences = chunk.get('sentences', [])
                    sent_idx = -1
                    for si, s in enumerate(chunk_sentences):
                        if s.strip() == sent:
                            sent_idx = si
                            break
                    
                    # Use next 1-2 sentences as answer context
                    if sent_idx >= 0 and sent_idx + 1 < len(chunk_sentences):
                        answer_parts = chunk_sentences[sent_idx+1:sent_idx+3]
                    
                    # Remove used sentence from pool
                    sentence_pool.pop(pool_idx)
                    break
            
            if not question_sent:
                continue
            
            # Create question with varied template
            template = question_templates[template_idx % len(question_templates)]
            template_idx += 1
            
            # Truncate question seed if too long
            q_seed = question_sent[:100]
            # Remove trailing punctuation for cleaner template insertion
            q_seed = q_seed.rstrip('.,!?:;')
            
            question_text = template.format(q_seed)
            
            # Build answer
            if answer_parts:
                answer_seed = ' '.join(p.strip() for p in answer_parts if p.strip())
            else:
                answer_seed = question_sent  # Use the sentence itself as answer context
            
            if len(answer_seed) > 240:
                answer_seed = answer_seed[:240]
            if not answer_seed.endswith('.'):
                answer_seed = answer_seed + '.'
            
            if len(question_text) < 16 or len(answer_seed) < 20:
                continue
            
            flashcards.append({
                'question': question_text,
                'answer': answer_seed,
                'topic': question_topic,
                'difficulty': difficulty
            })
        
        # If still short, create concept-based cards from remaining pool
        while len(flashcards) < len(target_difficulties) and sentence_pool:
            difficulty = target_difficulties[len(flashcards)]
            sent, topic, _ = sentence_pool.pop(0)
            
            # Use a different approach - ask to explain the concept
            flashcards.append({
                'question': f"Explain the concept: {sent[:80]}",
                'answer': f"{sent}. Review this topic for deeper understanding.",
                'topic': topic,
                'difficulty': difficulty
            })
        
        # Final padding if still short
        while len(flashcards) < len(target_difficulties):
            difficulty = target_difficulties[len(flashcards)]
            flashcards.append({
                'question': f"Review key concept #{len(flashcards)+1}?",
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
        """Remove boilerplate like copyright/ISBN/dates/headers and trim length."""
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            l = line.strip()
            l_lower = l.lower()
            
            # Skip common boilerplate keywords
            if any(keyword in l_lower for keyword in [
                "copyright", "isbn", "rights reserved", "revision history", "first release", "typo updates",
                "all rights reserved", "page ", "chapter ", "assignment", "submitted", "roll no", "enrollment"
            ]):
                continue
            
            # Skip date patterns
            if re.match(r"^\d{4}-\d{2}-\d{2}", l):
                continue
            
            # Skip all-caps headers
            if re.match(r"^[A-Z0-9 ,:-]{15,}$", l):
                continue
            
            # Skip lab/assignment headers like "LAB-2", "Lab 1:", "Experiment 3"
            if re.match(r"^(lab|experiment|practical|assignment|project)\s*[-:#]?\s*\d+", l_lower):
                continue
            
            # Skip lines with student roll numbers (patterns like 24CD3049, 21BCE1234, etc.)
            if re.search(r"\b\d{2}[A-Z]{2,4}\d{3,5}\b", l, re.IGNORECASE):
                continue
            
            # Skip lines that are just names with roll numbers
            if re.match(r"^[A-Za-z\s]+\d{2}[A-Z]{2,4}\d{3,5}", l, re.IGNORECASE):
                continue
            
            # Skip very short lines that might be headers (e.g., "Ques:", "Q1:", "Ans:")
            if re.match(r"^(ques|q\d*|ans|a\d*|question|answer)\s*[:.-]?\s*$", l_lower):
                continue
            
            # Skip lines starting with "Ques" or just containing question markers
            if re.match(r"^ques(tion)?\s*[:.-]?\s*\d*\s*$", l_lower):
                continue
            
            lines.append(l)
        
        cleaned = " ".join(lines)
        # Collapse whitespace and truncate
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:400]
    
    def _clean_and_split_sentences(self, text: str) -> List[str]:
        """Split text into reasonable sentences, filtering headers and short fragments."""
        if not text:
            return []
        
        raw_sentences = re.split(r'[.!?]', text)
        clean_sentences = []
        
        for s in raw_sentences:
            s = s.strip()
            s_lower = s.lower()
            
            # Skip too short
            if len(s) < 15:
                continue
            
            # Skip header patterns
            if re.match(r"^(lab|experiment|practical|assignment|project)\s*[-:#]?\s*\d*", s_lower):
                continue
            
            # Skip question/answer markers
            if re.match(r"^(ques|q\d*|ans|a\d*|question|answer)\s*[:.-]?", s_lower):
                continue
            
            # Skip lines with roll numbers
            if re.search(r"\b\d{2}[A-Z]{2,4}\d{3,5}\b", s, re.IGNORECASE):
                continue
            
            # Skip lines that are mostly just names
            words = s.split()
            if len(words) <= 3 and all(w[0].isupper() for w in words if w):
                continue
            
            clean_sentences.append(s)
        
        return clean_sentences
    
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

