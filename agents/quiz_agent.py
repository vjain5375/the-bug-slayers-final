# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
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

try:
    load_dotenv()
except UnicodeDecodeError:
    pass
except Exception:
    pass


class QuizAgent:
    """Generates adaptive quizzes from study material"""
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
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
        
        # Select chunks more intelligently - sample across the document if many chunks
        selected_chunks = []
        # Use more chunks if more questions are requested (approx 2 chunks per question)
        num_chunks_needed = min(max(15, int(num_questions * 2.0)), 40)
        
        if len(text_chunks) <= num_chunks_needed:
            selected_chunks = text_chunks
        else:
            # Sample across the document
            indices = sorted(random.sample(range(len(text_chunks)), num_chunks_needed))
            selected_chunks = [text_chunks[i] for i in indices]

        context_parts = []
        for chunk in selected_chunks:
            topic = chunk.get('metadata', {}).get('topic', 'General')
            text = chunk.get('text', '')
            context_parts.append(f"[Topic: {topic}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        difficulty_guidance = {
            "easy": "Focus on basic terminology, definitions, and direct facts. Questions should be straightforward.",
            "medium": "Focus on understanding relationships between concepts, application of principles, and explaining processes.",
            "hard": "Focus on complex scenarios, critical analysis of methods, identifying subtle differences, and synthesis of multiple ideas."
        }
        
        try:
            prompt = f"""You are a high-quality educational quiz generator. Your goal is to create exactly {num_questions} diverse, challenging, and meaningful multiple-choice questions based on the provided study material.

Study Material Context:
{context[:15000]}

Instructions:
1. Create EXACTLY {num_questions} multiple-choice questions with {difficulty} difficulty. This is a strict requirement. If the context is limited, generate multiple distinct questions from the same sections but focusing on different details.
2. {difficulty_guidance.get(difficulty, '')}
3. VARIETY IS CRITICAL: Do NOT use the same question pattern (like "Which of the following is true...") for every question. 
4. DO NOT use section headers or repetitive phrases as options. Each option must be a meaningful, distinct statement or value.
5. DISTRACTORS MUST BE PLAUSIBLE: Distractors should look like possible correct answers but be factually incorrect or inappropriate based on the context. Avoid "None of the above" or obviously silly options.
6. CONTENT FOCUS: Ensure questions cover different topics and subtopics from the provided context.
7. STRUCTURE:
   - A clear, specific question.
   - 4 distinct, meaningful options (A, B, C, D).
   - One clearly correct answer (must be a string matching one of the options).
   - The index of the correct answer (0-3).
   - An explanation that clarifies why the answer is correct and why others are not.

Return ONLY a valid JSON array in this format:
[
  {{
    "question": "A specific, well-formulated question?",
    "options": ["Option 0", "Option 1", "Option 2", "Option 3"],
    "correct_answer": "The string value of the correct option",
    "correct_index": 0,
    "topic": "Relevant topic from context",
    "difficulty": "{difficulty}",
    "explanation": "A detailed explanation."
  }},
  ...
]

Only return the JSON array, no additional text or markdown formatting."""
            
            messages = [
                SystemMessage(content=f"You are a strict educational content generator. You MUST generate exactly {num_questions} questions. Do not stop until you have reached the quota. Format everything as a JSON array."),
                HumanMessage(content=prompt)
            ]
            
            for _ in range(3): # Maximum Effort Retry Loop
                try:
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
                                normalized = self._normalize_question(cleaned, difficulty)
                                if normalized:
                                    validated.append(normalized)

                        # Deduplicate questions by text to avoid repeated items
                        deduped = []
                        seen_questions = set()
                        for item in validated:
                            qtext = item['question'].strip().lower()
                            if qtext in seen_questions:
                                continue
                            seen_questions.add(qtext)
                            deduped.append(item)

                        if len(deduped) >= num_questions * 0.7: # High quality quota
                            # Ensure count and difficulty mix by topping up with deterministic cards
                            if len(deduped) < num_questions:
                                remaining_count = num_questions - len(deduped)
                                fallbacks = self._simple_quiz_generation(text_chunks, difficulty, remaining_count)
                                deduped.extend(fallbacks)
                            return deduped[:num_questions]
                        else:
                            print(f"  → LLM generated too few questions ({len(deduped)}/{num_questions}). Retrying...")
                except Exception as e:
                    print(f"Error during LLM generation attempt: {e}")
        except Exception as e:
            print(f"Error preparing quiz generation: {e}")
        
        # Fallback to simple generation if all retries fail
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
            # Basic validation
            if not clean or len(clean) < 2 or len(clean) > 250:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            options.append(clean)
        
        # Ensure we have 4 options by adding varied distractors if needed
        generic_distractors = [
            "Partially correct but incomplete description.",
            "A related concept but incorrect in this specific context.",
            "A common misconception often associated with this topic.",
            "An unrelated detail that doesn't answer the core question.",
            "A secondary factor that is not the primary focus here.",
            "Information mentioned elsewhere but not applicable to this question."
        ]
        random.shuffle(generic_distractors)
        
        for gd in generic_distractors:
            if len(options) >= 4:
                break
            if gd.lower() not in seen:
                options.append(gd)
                seen.add(gd.lower())
        
        options = options[:4]
        if len(options) < 3:
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
        
        # If still not found, default to a random option to avoid bias towards first option
        if idx is None and options:
            idx = random.randint(0, len(options)-1)
            correct_answer = options[idx]
        
        if idx is None:
            return None
        
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

    def _normalize_question(self, q: Dict, default_difficulty: str) -> Optional[Dict]:
        """Final pass to ensure options are randomized and structure is correct."""
        question = q.get('question', '').strip()
        options = q.get('options', [])
        correct_answer = q.get('correct_answer', '')
        
        if not options:
            return None
            
        # FORCE RANDOMIZATION: Shuffle all options
        shuffled = list(options)
        random.shuffle(shuffled)
        
        # Re-locate correct answer index after shuffle
        try:
            # Try exact match first
            new_correct_index = shuffled.index(correct_answer)
        except ValueError:
            # Try case-insensitive if exact match fails
            new_correct_index = 0
            for i, opt in enumerate(shuffled):
                if opt.lower() == correct_answer.lower():
                    new_correct_index = i
                    correct_answer = shuffled[i]
                    break
            
        return {
            'question': question,
            'options': shuffled,
            'correct_answer': correct_answer,
            'correct_index': new_correct_index,
            'topic': q.get('topic', 'General'),
            'difficulty': q.get('difficulty', default_difficulty),
            'explanation': q.get('explanation', '')
        }

    def _simple_quiz_generation(self, text_chunks: List[Dict], difficulty: str, num_questions: int) -> List[Dict]:
        """Simple fallback quiz generation with unique questions and distinct options"""
        questions = []
        if not text_chunks:
            return []

        # Build a global pool of unique sentences from ALL chunks
        all_sentences = []
        for chunk in text_chunks:
            text = chunk.get('text', '')
            topic = chunk.get('metadata', {}).get('topic', 'General')
            # Split into sentences, filter short/boilerplate
            sentences = [s.strip() for s in re.split(r'[\.!\?]', text) if len(s.strip()) > 20]
            for sent in sentences:
                # Skip boilerplate
                lower = sent.lower()
                if any(skip in lower for skip in ['copyright', 'isbn', 'http', 'www.', 'all rights', 'published']):
                    continue
                # Clean and add
                clean = re.sub(r'\s+', ' ', sent).strip()
                if len(clean) > 20 and len(clean) < 300:
                    all_sentences.append({'text': clean, 'topic': topic})

        if len(all_sentences) < 4:
            return questions

        # Dedupe sentences
        seen = set()
        unique_sentences = []
        for item in all_sentences:
            key = item['text'].lower()[:50]
            if key not in seen:
                seen.add(key)
                unique_sentences.append(item)

        # Shuffle for variety
        random.shuffle(unique_sentences)

        # Track used sentences to avoid repetition
        used_indices = set()

        for q_num in range(num_questions):
            if len(used_indices) >= len(unique_sentences) - 4:
                break  # Not enough unique content left

            # Find an unused sentence for the question stem
            stem_idx = None
            for i, item in enumerate(unique_sentences):
                if i not in used_indices:
                    stem_idx = i
                    break
            if stem_idx is None:
                break

            stem_item = unique_sentences[stem_idx]
            used_indices.add(stem_idx)

            # Find an unused sentence for the correct answer
            answer_idx = None
            for i, item in enumerate(unique_sentences):
                if i not in used_indices and i != stem_idx:
                    answer_idx = i
                    break
            if answer_idx is None:
                break

            answer_item = unique_sentences[answer_idx]
            used_indices.add(answer_idx)

            # Find 3 distinct distractors from unused sentences
            distractors = []
            for i, item in enumerate(unique_sentences):
                if i not in used_indices and i != stem_idx and i != answer_idx:
                    distractors.append(item['text'][:160])
                    used_indices.add(i)
                    if len(distractors) >= 3:
                        break

            # If not enough distractors, use generic ones
            generic = [
                "This concept is unrelated to the question.",
                "This statement describes a different process.",
                "This is a common misunderstanding of the topic."
            ]
            for g in generic:
                if len(distractors) >= 3:
                    break
                distractors.append(g)

            # Build question
            stem = stem_item['text'][:100]
            correct_answer = answer_item['text'][:160]
            topic = stem_item['topic']

            options = [correct_answer] + distractors[:3]
            random.shuffle(options)
            correct_index = options.index(correct_answer)

            questions.append({
                'question': f"Based on the study material, which statement relates to: {stem}?",
                'options': options,
                'correct_answer': correct_answer,
                'correct_index': correct_index,
                'topic': topic,
                'difficulty': difficulty,
                'explanation': f"The correct statement is: {correct_answer}"
            })

        return questions
    
    def generate_adaptive_quiz(self, text_chunks: List[Dict], user_performance: Optional[Dict] = None, num_questions: int = 5) -> List[Dict]:
        """Generate adaptive quiz based on user performance"""
        if not user_performance:
            return self.generate_quiz(text_chunks, "medium", num_questions)
        
        accuracy = user_performance.get('accuracy', 0.5)
        weak_topics = user_performance.get('weak_topics', [])
        
        if accuracy > 0.8:
            difficulty = "hard"
        elif accuracy > 0.6:
            difficulty = "medium"
        else:
            difficulty = "easy"
        
        if weak_topics:
            topic_chunks = [
                chunk for chunk in text_chunks
                if chunk.get('metadata', {}).get('topic', '').lower() in [t.lower() for t in weak_topics]
            ]
            if topic_chunks:
                text_chunks = topic_chunks + text_chunks[:3]
        
        return self.generate_quiz(text_chunks, difficulty, num_questions)
    
    def evaluate_quiz(self, questions: List[Dict], user_answers: Dict[int, int]) -> Dict:
        """Evaluate quiz answers"""
        correct = 0
        total = len(questions)
        details = []
        
        for i, question in enumerate(questions):
            user_answer_idx = user_answers.get(i, -1)
            options = question.get('options', [])
            correct_index = question.get('correct_index', 0)
            
            is_correct = user_answer_idx == correct_index
            if is_correct:
                correct += 1
            
            user_answer_text = options[user_answer_idx] if 0 <= user_answer_idx < len(options) else "Not answered"
            correct_answer_text = options[correct_index] if 0 <= correct_index < len(options) else ""
            
            details.append({
                'question_index': i,
                'question': question['question'],
                'user_answer': user_answer_text,
                'correct_answer': correct_answer_text,
                'is_correct': is_correct,
                'explanation': question.get('explanation', '')
            })
        
        accuracy = correct / total if total > 0 else 0
        
        feedback = "MAXIMUM EFFORT! PERFECTION!" if accuracy == 1.0 else \
                   "NOT BAD, HERO. BUT YOU CAN DO BETTER!" if accuracy >= 0.7 else \
                   "ROOKIE NUMBERS! GET BACK TO TRAINING!"
        
        return {
            'score': correct,
            'total': total,
            'accuracy': accuracy,
            'correct': correct,
            'details': details,
            'feedback': feedback
        }
    
    def save_quiz(self, questions: List[Dict], file_path: str = "outputs/quizzes.json"):
        """Save quiz to JSON file"""
        output_dir = Path(file_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
    
    def export_to_csv(self, questions: List[Dict]) -> str:
        """Export quiz questions to CSV string"""
        if not questions:
            return ""
        
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow(['Question', 'Option A', 'Option B', 'Option C', 'Option D', 'Correct Answer', 'Explanation'])
        
        for q in questions:
            options = q.get('options', ['', '', '', ''])
            while len(options) < 4:
                options.append('')
                
            writer.writerow([
                q.get('question', ''),
                options[0],
                options[1],
                options[2],
                options[3],
                q.get('correct_answer', ''),
                q.get('explanation', '')
            ])
            
        return output.getvalue()
