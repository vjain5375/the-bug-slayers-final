"""
Quiz Agent
Generates adaptive quizzes with multiple difficulty levels
"""

import json
import re
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
        if not self.llm:
            return self._simple_quiz_generation(text_chunks, difficulty, num_questions)
        
        # Combine a limited number of chunks into context to keep prompts fast
        context_parts = []
        for chunk in text_chunks[:3]:  # Use top 3 chunks for faster LLM calls
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
                    if 'question' in q and 'options' in q and 'correct_answer' in q:
                        # Ensure correct_index is set
                        if 'correct_index' not in q:
                            try:
                                correct_idx = q['options'].index(q['correct_answer'])
                                q['correct_index'] = correct_idx
                            except ValueError:
                                continue
                        
                        validated.append({
                            'question': q['question'].strip(),
                            'options': [opt.strip() for opt in q['options']],
                            'correct_answer': q['correct_answer'].strip(),
                            'correct_index': q.get('correct_index', 0),
                            'topic': q.get('topic', 'General'),
                            'difficulty': q.get('difficulty', difficulty),
                            'explanation': q.get('explanation', '')
                        })
                return validated[:num_questions]
        except Exception as e:
            print(f"Error generating quiz: {e}")
        
        # Fallback to simple generation
        return self._simple_quiz_generation(text_chunks, difficulty, num_questions)
    
    def _simple_quiz_generation(self, text_chunks: List[Dict], difficulty: str, num_questions: int) -> List[Dict]:
        """Simple fallback quiz generation"""
        questions = []
        
        for chunk in text_chunks[:num_questions]:
            text = chunk.get('text', '')
            topic = chunk.get('metadata', {}).get('topic', 'General')
            
            # Simple extraction: create a basic question
            sentences = text.split('.')
            if len(sentences) >= 2:
                question = f"Which of the following is true about {sentences[0][:50]}?"
                correct_answer = sentences[1].strip()[:100]
                
                questions.append({
                    'question': question,
                    'options': [
                        correct_answer,
                        "Option B (incorrect)",
                        "Option C (incorrect)",
                        "Option D (incorrect)"
                    ],
                    'correct_answer': correct_answer,
                    'correct_index': 0,
                    'topic': topic,
                    'difficulty': difficulty,
                    'explanation': ''
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
            user_answer = user_answers.get(i, -1)
            correct_index = question.get('correct_index', 0)
            is_correct = user_answer == correct_index
            
            if is_correct:
                correct += 1
            
            details.append({
                'question_index': i,
                'question': question['question'],
                'user_answer': user_answer,
                'correct_answer': correct_index,
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

