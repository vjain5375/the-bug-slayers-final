"""
Central Controller
Orchestrates multi-agent workflow and manages inter-agent communication
"""

from typing import List, Dict, Optional
from .reader_agent import ReaderAgent
from .flashcard_agent import FlashcardAgent
from .quiz_agent import QuizAgent
from .planner_agent import PlannerAgent
from .chat_agent import ChatAgent
import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from vector_store import VectorStore


class KnowledgeMemory:
    """Centralized knowledge memory module for sharing context between agents"""
    
    def __init__(self):
        self.topics = []
        self.chunks = []
        self.flashcards = []
        self.quizzes = []
        self.revision_plan = []
        self.user_performance = {
            'quiz_scores': [],
            'weak_topics': [],
            'strong_topics': []
        }
    
    def add_topics(self, topics: List[Dict]):
        """Add topics to memory"""
        self.topics.extend(topics)
    
    def add_chunks(self, chunks: List[Dict]):
        """Add chunks to memory"""
        self.chunks.extend(chunks)
    
    def add_flashcards(self, flashcards: List[Dict]):
        """Add flashcards to memory"""
        self.flashcards.extend(flashcards)
    
    def add_quizzes(self, quizzes: List[Dict]):
        """Add quizzes to memory"""
        self.quizzes.extend(quizzes)
    
    def update_performance(self, quiz_result: Dict):
        """Update user performance metrics"""
        accuracy = quiz_result.get('accuracy', 0)
        self.user_performance['quiz_scores'].append(accuracy)
        
        # Identify weak topics (accuracy < 0.6)
        if accuracy < 0.6:
            # Extract topics from quiz questions
            details = quiz_result.get('details', [])
            for detail in details:
                # This would need topic info from questions
                pass
    
    def get_all_topics(self) -> List[str]:
        """Get list of all unique topics"""
        topics = set()
        for chunk in self.chunks:
            topic = chunk.get('metadata', {}).get('topic', '')
            if topic:
                topics.add(topic)
        return list(topics)


class AgentController:
    """Central controller for orchestrating multi-agent workflow"""
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        # Initialize agents
        self.reader_agent = ReaderAgent()
        self.flashcard_agent = FlashcardAgent()
        self.quiz_agent = QuizAgent()
        self.planner_agent = PlannerAgent()
        self.chat_agent = ChatAgent(vector_store)
        
        # Initialize knowledge memory
        self.memory = KnowledgeMemory()
        
        # Vector store for semantic search
        self.vector_store = vector_store
    
    def get_topic_chunks(self, topic: str) -> List[Dict]:
        """Get all chunks for a specific topic, with robust fallback to semantic search"""
        # 1. Try memory first (exact match)
        chunks = [
            chunk for chunk in self.memory.chunks
            if chunk.get('metadata', {}).get('topic', '').lower() == topic.lower()
        ]
        
        # 2. If memory is empty, try exact metadata match in Vector Store
        if not chunks and self.vector_store:
            try:
                results = self.vector_store.collection.get(
                    where={"topic": topic}
                )
                if results and results['documents']:
                    for i in range(len(results['documents'])):
                        chunks.append({
                            'text': results['documents'][i],
                            'metadata': results['metadatas'][i]
                        })
            except Exception as e:
                print(f"Error fetching exact topic chunks: {e}")

        # 3. ROBUST FALLBACK: If still no chunks, perform a SEMANTIC SEARCH for the topic name
        # This handles cases where the topic name in the plan differs slightly from metadata
        if not chunks and self.vector_store:
            try:
                print(f"  → Falling back to semantic search for topic: {topic}")
                search_results = self.vector_store.search(topic, n_results=8)
                if search_results:
                    for res in search_results:
                        chunks.append({
                            'text': res['text'],
                            'metadata': res['metadata']
                        })
            except Exception as e:
                print(f"Error in semantic topic fallback: {e}")
                
        return chunks
    
    def process_study_materials(self, directory_path: str) -> Dict:
        """
        Complete workflow: Read → Extract → Structure
        
        Args:
            directory_path: Path to directory containing study materials
            
        Returns:
            Dict with processing results
        """
        # Step 1: Reader Agent processes documents
        result = self.reader_agent.process_directory(directory_path)
        
        chunks = result.get('chunks', [])
        topics = result.get('topics', [])
        
        # Store in memory
        self.memory.add_chunks(chunks)
        self.memory.add_topics(topics)
        
        # Add to vector store if available
        if self.vector_store:
            self.vector_store.clear_collection()
            self.vector_store.add_documents(chunks)
            self.chat_agent.vector_store = self.vector_store
        
        # Generate samples for the dashboard
        flashcard_samples = []
        if chunks:
            try:
                flashcard_samples = self.flashcard_agent.generate_flashcards(chunks[:3], num_flashcards=2)
            except: pass
            
        quiz_samples = []
        if chunks:
            try:
                quiz_samples = self.quiz_agent.generate_quiz(chunks[:3], num_questions=2)
            except: pass

        return {
            'chunks': chunks,
            'topics': topics,
            'total_chunks': len(chunks),
            'total_topics': len(topics),
            'flashcard_samples': flashcard_samples,
            'quiz_samples': quiz_samples
        }
    
    def generate_flashcards(
        self,
        num_flashcards: int = 10,
        topic: Optional[str] = None,
        difficulty_mix: str = "easy_medium_hard",
    ) -> List[Dict]:
        """
        Generate flashcards from processed materials
        
        Args:
            num_flashcards: Number of flashcards to generate
            topic: Optional specific topic to focus on
            difficulty_mix: Difficulty distribution preset
            
        Returns:
            List of flashcards
        """
        chunks = self.memory.chunks
        
        if topic:
            chunks = self.get_topic_chunks(topic)
        
        flashcards = self.flashcard_agent.generate_flashcards(
            chunks,
            num_flashcards,
            difficulty_mix=difficulty_mix,
        )
        
        # Store in memory
        self.memory.add_flashcards(flashcards)
        
        # Save to file
        self.flashcard_agent.save_flashcards(flashcards)
        
        return flashcards
    
    def generate_quiz(
        self, 
        difficulty: str = "medium", 
        num_questions: int = 5, 
        adaptive: bool = True,
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate quiz from processed materials
        
        Args:
            difficulty: "easy", "medium", or "hard"
            num_questions: Number of questions
            adaptive: Whether to adapt based on user performance
            topic: Optional specific topic to focus on
            
        Returns:
            List of quiz questions
        """
        chunks = self.memory.chunks
        
        if topic:
            chunks = self.get_topic_chunks(topic)
        elif not chunks:
            # If no topic and no chunks in memory, nothing to do
            return []
        
        if adaptive and not topic and self.memory.user_performance.get('quiz_scores'):
            # Use adaptive quiz generation (only if no specific topic requested)
            user_perf = {
                'accuracy': sum(self.memory.user_performance['quiz_scores']) / len(self.memory.user_performance['quiz_scores']),
                'weak_topics': self.memory.user_performance.get('weak_topics', [])
            }
            questions = self.quiz_agent.generate_adaptive_quiz(
                text_chunks=chunks,
                user_performance=user_perf,
                num_questions=num_questions,
            )
        else:
            questions = self.quiz_agent.generate_quiz(chunks, difficulty, num_questions)
        
        # Store in memory
        self.memory.add_quizzes(questions)
        
        # Save to file
        self.quiz_agent.save_quiz(questions)
        
        return questions
    
    def create_revision_plan(self, exam_date: Optional[str] = None, study_days_per_week: int = 5) -> List[Dict]:
        """
        Create revision schedule
        
        Args:
            exam_date: Exam date in YYYY-MM-DD format
            study_days_per_week: Number of study days per week
            
        Returns:
            List of revision plan items
        """
        topics = self.memory.topics
        
        exam_datetime = None
        if exam_date:
            from datetime import datetime
            try:
                exam_datetime = datetime.strptime(exam_date, '%Y-%m-%d')
            except ValueError:
                pass
        
        plan = self.planner_agent.create_revision_plan(
            topics,
            exam_date=exam_datetime,
            study_days_per_week=study_days_per_week
        )
        
        # Store in memory
        self.planner_agent.revision_plan = plan
        
        # Save to file
        self.planner_agent.save_plan()
        
        return plan
    
    def answer_question(self, question: str, prioritize_source: Optional[str] = None) -> Dict:
        """
        Answer a question using Chat Agent
        
        Args:
            question: User's question
            prioritize_source: Optional filename to prioritize in search
            
        Returns:
            Dict with answer, sources, and chunks
        """
        return self.chat_agent.answer_question(question, prioritize_source=prioritize_source)
    
    def evaluate_quiz(self, questions: List[Dict], user_answers: Dict[int, int]) -> Dict:
        """
        Evaluate quiz and update performance
        
        Args:
            questions: List of quiz questions
            user_answers: Dict mapping question index to selected option index
            
        Returns:
            Evaluation results
        """
        result = self.quiz_agent.evaluate_quiz(questions, user_answers)
        
        # Update memory with performance
        self.memory.update_performance(result)
        
        return result
    
    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        stats = {
            'total_chunks': len(self.memory.chunks),
            'total_topics': len(self.memory.topics),
            'total_flashcards': len(self.memory.flashcards),
            'total_quizzes': len(self.memory.quizzes),
            'revision_stats': self.planner_agent.get_statistics(),
            'performance': {
                'average_score': (
                    sum(self.memory.user_performance['quiz_scores']) / len(self.memory.user_performance['quiz_scores'])
                    if self.memory.user_performance['quiz_scores'] else 0
                ),
                'total_quizzes_taken': len(self.memory.user_performance['quiz_scores'])
            }
        }
        return stats

