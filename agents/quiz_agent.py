"""
Quiz Agent
Generates adaptive quizzes with multiple difficulty levels
"""

import json
import re
import random
from typing import List, Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


class QuizAgent:
    """Generates adaptive quizzes from study material"""
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.4,
                google_api_key=api_key
            )
        else:
            self.llm = None
    
    def generate_quiz(self, text_chunks: List[Dict], difficulty: str = "medium", num_questions: int = 5) -> List[Dict]:
        """
        Generate quiz questions from text chunks
        
        Args:
            text_chunks: List of text chunks with metadata
            difficulty: "easy", "medium", or "hard"
            num_questions: Number of questions to generate
            
        Returns:
            List of quiz question dictionaries
        """
        if not text_chunks:
            return []

        if not self.llm:
            return self._simple_quiz_generation(text_chunks, difficulty, num_questions)
        
        # Combine a limited number of chunks into context to keep prompts fast
        context_parts = []
        for chunk in text_chunks[:8]:  # Use more chunks to improve coverage
            topic = chunk.get('metadata', {}).get('topic', 'General')
            text = chunk.get('text', '')
            context_parts.append(f"[Topic: {topic}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        difficulty_guidance = {
            "easy": "Simple recall questions with straightforward answers",
            "medium": "Questions requiring understanding and application",
            "hard": "Complex questions requiring analysis and synthesis"
        }
        
        try:
            prompt = f"""You are a quiz generator for study materials. Create multiple-choice questions.

Study Material:
{context[:2500]}

Create exactly {num_questions} multiple-choice questions with {difficulty} difficulty.
{difficulty_guidance.get(difficulty, '')}

Each question must have:
- A clear question statement
- Exactly 4 options (A, B, C, D)
- One correct answer
- 3 plausible distractors (wrong but reasonable answers)

Return ONLY a valid JSON array in this format:
[
  {{
    "question": "Question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option A",
    "correct_index": 0,
    "topic": "Topic name",
    "difficulty": "{difficulty}",
    "explanation": "Brief explanation of why the answer is correct"
  }},
  ...
]

Only return the JSON array, no additional text."""
            
            messages = [
                SystemMessage(content="You are an expert at creating educational quizzes. Generate clear, well-structured multiple-choice questions."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            result = response.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group(0))
                # Validate and clean questions
                validated = []
                for q in questions:
                    cleaned = self._validate_question_dict(q, difficulty)
                    if cleaned:
                        validated.append(cleaned)

                # If the LLM returned fewer questions than requested, top up using the
                # simple deterministic generator so the user still gets approximately
                # the number they selected (as long as there is enough content).
                if len(validated) < num_questions:
                    simple_questions = self._simple_quiz_generation(text_chunks, difficulty, num_questions)
                    for q in simple_questions:
                        if len(validated) >= num_questions:
                            break
                        validated.append(q)

                return validated[:num_questions]
        except Exception as e:
            print(f"Error generating quiz: {e}")
        
        # Fallback to simple generation
        return self._simple_quiz_generation(text_chunks, difficulty, num_questions)
    
    def _validate_question_dict(self, q: Dict, default_difficulty: str) -> Optional[Dict]:
        """Normalize and validate a single question dict to avoid index/option mismatch"""
        if not q or 'question' not in q:
            return None
        
        # Normalize options
        raw_options = q.get('options', []) or []
        options: List[str] = []
        seen = set()
        for opt in raw_options:
            if not opt:
                continue
            clean = str(opt).strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            options.append(clean)
        # Ensure we have 4 options by adding generic distractors if needed
        generic_distractors = [
            "Partially correct but incomplete.",
            "Related concept but not the right answer.",
            "Common misconception about this topic.",
            "Unrelated detail to the question."
        ]
        for gd in generic_distractors:
            if len(options) >= 4:
                break
            if gd.lower() not in seen:
                options.append(gd)
                seen.add(gd.lower())
        options = options[:4]
        if len(options) < 2:
            return None
        
        # Resolve correct answer/index
        correct_answer = str(q.get('correct_answer', '')).strip()
        correct_index = q.get('correct_index', None)
        # Try to locate correct answer in options (case-insensitive)
        idx = None
        if correct_answer:
            for i, opt in enumerate(options):
                if opt.lower() == correct_answer.lower():
                    idx = i
                    break
        if idx is None and isinstance(correct_index, int) and 0 <= correct_index < len(options):
            idx = correct_index
            correct_answer = options[idx]
        if idx is None:
            return None  # cannot trust correctness
        correct_index = idx
        correct_answer = options[correct_index]
        
        explanation = str(q.get('explanation', '') or "").strip()
        if not explanation:
            explanation = f"The correct choice is: {correct_answer}"
        
        return {
            'question': str(q.get('question', '')).strip(),
            'options': options,
            'correct_answer': correct_answer,
            'correct_index': correct_index,
            'topic': q.get('topic', 'General'),
            'difficulty': q.get('difficulty', default_difficulty),
            'explanation': explanation
        }
    
    def _simple_quiz_generation(self, text_chunks: List[Dict], difficulty: str, num_questions: int) -> List[Dict]:
        """Simple fallback quiz generation that can produce up to the requested count even with few chunks"""
        questions: List[Dict] = []
        if not text_chunks:
            return questions

        # Pre-processed chunks with sentences to reuse
        processed_chunks = []
        for chunk in text_chunks:
            text = chunk.get('text', '')
            topic = chunk.get('metadata', {}).get('topic', 'General')
            # Split on ., ?, ! to get more sentence-like fragments
            sentences = [s.strip() for s in re.split(r'[\.!\?]', text) if len(s.strip()) > 10]
            if sentences:
                processed_chunks.append((topic, sentences))

        if not processed_chunks:
            return questions

        generic_distractors = [
            "This statement does not accurately describe the concept.",
            "This is only partially related to the topic.",
            "This is a common misconception about the topic.",
            "This detail is unrelated to the described process."
        ]

        # Round-robin through chunks, generating multiple questions per chunk if possible
        chunk_index = 0
        safety_limit = num_questions * 3  # avoid infinite loops on very small content
        attempts = 0

        while len(questions) < num_questions and attempts < safety_limit:
            attempts += 1
            topic, sentences = processed_chunks[chunk_index % len(processed_chunks)]
            chunk_index += 1

            if len(sentences) < 2:
                continue

            # Use pairs of adjacent sentences to build Q/A
            for i in range(len(sentences) - 1):
                if len(questions) >= num_questions:
                    break

                stem = sentences[i][:120]
                correct_answer = sentences[i + 1][:200]

                # Distractors from other sentences in the same chunk
                distractor_pool = sentences[:i] + sentences[i + 2:]
                distractors = [d for d in distractor_pool if len(d) > 12][:3]

                for gd in generic_distractors:
                    if len(distractors) >= 3:
                        break
                    distractors.append(gd)

                if len(distractors) < 3:
                    continue

                options = [correct_answer] + distractors[:3]
                random.shuffle(options)
                correct_index = options.index(correct_answer)

                questions.append({
                    'question': f"Which of the following is true about {stem}?",
                    'options': options,
                    'correct_answer': correct_answer,
                    'correct_index': correct_index,
                    'topic': topic,
                    'difficulty': difficulty,
                    'explanation': f"The statement that best fits is: {correct_answer}"
                })

        return questions
    
    def generate_adaptive_quiz(
        self,
        text_chunks: List[Dict],
        user_performance: Optional[Dict] = None,
        num_questions: int = 5,
    ) -> List[Dict]:
        """
        Generate adaptive quiz based on user performance
        
        Args:
            text_chunks: List of text chunks
            user_performance: Dict with 'accuracy' and 'weak_topics' keys
            num_questions: Number of questions to generate
            
        Returns:
            List of quiz questions with adjusted difficulty
        """
        if not user_performance:
            # Default to medium difficulty
            return self.generate_quiz(text_chunks, "medium", num_questions)
        
        accuracy = user_performance.get('accuracy', 0.5)
        weak_topics = user_performance.get('weak_topics', [])
        
        # Adjust difficulty based on accuracy
        if accuracy > 0.8:
            difficulty = "hard"
        elif accuracy > 0.6:
            difficulty = "medium"
        else:
            difficulty = "easy"
        
        # Prioritize weak topics if specified
        if weak_topics:
            topic_chunks = [
                chunk for chunk in text_chunks
                if chunk.get('metadata', {}).get('topic', '').lower() in [t.lower() for t in weak_topics]
            ]
            if topic_chunks:
                text_chunks = topic_chunks + text_chunks[:3]  # Add some general chunks
        
        return self.generate_quiz(text_chunks, difficulty, num_questions)
    
    def evaluate_quiz(self, questions: List[Dict], user_answers: Dict[int, int]) -> Dict:
        """
        Evaluate quiz answers and return performance metrics
        
        Args:
            questions: List of quiz questions
            user_answers: Dict mapping question index to selected option index
            
        Returns:
            Dict with 'score', 'accuracy', 'correct', 'total', and 'details'
        """
        correct = 0
        total = len(questions)
        details = []
        
        for i, question in enumerate(questions):
            user_answer_idx = user_answers.get(i, -1)
            options = question.get('options', [])
            correct_index = question.get('correct_index', 0)
            correct_index = correct_index if isinstance(correct_index, int) else 0

            # Clamp indices to available options
            if options:
                if correct_index < 0 or correct_index >= len(options):
                    correct_index = 0

            is_correct = user_answer_idx == correct_index
            if is_correct:
                correct += 1

            user_answer_text = options[user_answer_idx] if options and 0 <= user_answer_idx < len(options) else "Not answered"
            correct_answer_text = options[correct_index] if options and 0 <= correct_index < len(options) else question.get('correct_answer', '')
            
            details.append({
                'question_index': i,
                'question': question['question'],
                'user_answer_index': user_answer_idx,
                'correct_answer_index': correct_index,
                'user_answer': user_answer_text,
                'correct_answer': correct_answer_text,
                'is_correct': is_correct,
                'explanation': question.get('explanation', '')
            })
        
        accuracy = correct / total if total > 0 else 0
        
        return {
            'score': correct,
            'total': total,
            'accuracy': accuracy,
            'correct': correct,
            'details': details
        }
    
    def save_quiz(self, questions: List[Dict], file_path: str = "outputs/quizzes.json"):
        """Save quiz to JSON file"""
        output_dir = Path(file_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
    
    def load_quiz(self, file_path: str = "outputs/quizzes.json") -> List[Dict]:
        """Load quiz from JSON file"""
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

