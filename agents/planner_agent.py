# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Planner Agent
Creates adaptive revision schedules based on topics and performance
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Builds smart revision schedules based on topic weightage and progress"""
    
    def __init__(self):
        self.revision_plan = []
        self.progress = {}
    
    def create_revision_plan(
        self,
        topics: List[Dict],
        start_date: Optional[datetime] = None,
        exam_date: Optional[datetime] = None,
        study_days_per_week: int = 5
    ) -> List[Dict]:
        """
        Create a revision schedule
        
        Args:
            topics: List of topics with metadata
            start_date: When to start revision (default: today)
            exam_date: Exam date (default: 30 days from start)
            study_days_per_week: Number of study days per week
            
        Returns:
            List of revision schedule items
        """
        logger.info(f"create_revision_plan called: topics={len(topics) if topics else 0}, exam_date={exam_date}, study_days={study_days_per_week}")
        
        if not topics or len(topics) == 0:
            logger.warning("No topics provided for revision plan - returning empty plan")
            return []
        
        if not start_date:
            start_date = datetime.now()
        
        if not exam_date:
            exam_date = start_date + timedelta(days=30)
        
        total_days = (exam_date - start_date).days
        if total_days <= 0:
            total_days = 30  # Default to 30 days
        
        logger.info(f"Plan parameters: total_days={total_days}, start={start_date.strftime('%Y-%m-%d')}, exam={exam_date.strftime('%Y-%m-%d')}")
        
        # Calculate study days
        weeks = total_days / 7
        total_study_days = int(weeks * study_days_per_week)
        
        if total_study_days == 0:
            total_study_days = min(len(topics), 5)  # At least cover some topics
        
        # Prioritize topics (can be based on difficulty, importance, etc.)
        prioritized_topics = self._prioritize_topics(topics)
        logger.info(f"Prioritized {len(prioritized_topics)} topics for {total_study_days} study days")
        
        # Distribute topics across study days
        plan = []
        current_date = start_date
        topic_index = 0
        
        for day in range(total_study_days):
            if topic_index >= len(prioritized_topics):
                # Review phase - repeat topics
                topic_index = 0
            
            topic = prioritized_topics[topic_index]
            
            # Skip weekends if study_days_per_week < 7
            while current_date.weekday() >= 5 and study_days_per_week < 7:
                current_date += timedelta(days=1)
            
            plan_item = {
                'date': current_date.strftime('%Y-%m-%d'),
                'day': day + 1,
                'topic': topic.get('topic', f'Topic {topic_index + 1}'),
                'subtopics': topic.get('subtopics', []),
                'key_points': topic.get('key_points', []),
                'status': 'pending',
                'estimated_time': '1-2 hours',
                'priority': 'high' if day < total_study_days * 0.3 else 'medium'
            }
            
            plan.append(plan_item)
            current_date += timedelta(days=1)
            topic_index += 1
        
        self.revision_plan = plan
        logger.info(f"Created revision plan with {len(plan)} items")
        return plan
    
    def _prioritize_topics(self, topics: List[Dict]) -> List[Dict]:
        """Prioritize topics based on various factors"""
        # Simple prioritization: sort by number of key points (more points = more important)
        prioritized = sorted(
            topics,
            key=lambda t: len(t.get('key_points', [])),
            reverse=True
        )
        return prioritized
    
    def update_progress(self, topic: str, status: str = 'completed', score: Optional[float] = None):
        """
        Update progress for a topic
        
        Args:
            topic: Topic name
            status: 'completed', 'in_progress', 'pending', 'difficult'
            score: Optional quiz/assessment score
        """
        if topic not in self.progress:
            self.progress[topic] = {
                'status': status,
                'last_revised': datetime.now().isoformat(),
                'revision_count': 0,
                'scores': []
            }
        
        self.progress[topic]['status'] = status
        self.progress[topic]['last_revised'] = datetime.now().isoformat()
        self.progress[topic]['revision_count'] += 1
        
        if score is not None:
            self.progress[topic]['scores'].append(score)
    
    def get_pending_topics(self) -> List[Dict]:
        """Get list of topics that need revision"""
        pending = []
        for item in self.revision_plan:
            if item['status'] == 'pending':
                pending.append(item)
        return pending
    
    def get_difficult_topics(self) -> List[str]:
        """Get list of topics marked as difficult"""
        difficult = []
        for topic, data in self.progress.items():
            if data.get('status') == 'difficult':
                difficult.append(topic)
        return difficult
    
    def get_upcoming_revisions(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming revision items"""
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)
        
        upcoming = []
        for item in self.revision_plan:
            try:
                item_date = datetime.strptime(item['date'], '%Y-%m-%d').date()
                if today <= item_date <= end_date:
                    upcoming.append(item)
            except Exception:
                continue
        
        return sorted(upcoming, key=lambda x: x['date'])
    
    def mark_status(self, date: str, topic: str, status: str):
        """Mark a revision item with a specific status ('completed', 'in_progress', 'pending')"""
        for item in self.revision_plan:
            if item['date'] == date and item['topic'] == topic:
                item['status'] = status
                self.update_progress(topic, status)
                # Auto-save after status change
                self.save_plan()
                break
    
    def get_statistics(self) -> Dict:
        """Get revision statistics"""
        total = len(self.revision_plan) if self.revision_plan else 0
        completed = sum(1 for item in self.revision_plan if item.get('status') == 'completed') if self.revision_plan else 0
        pending = sum(1 for item in self.revision_plan if item.get('status') == 'pending') if self.revision_plan else 0
        in_progress = sum(1 for item in self.revision_plan if item.get('status') == 'in_progress') if self.revision_plan else 0
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        logger.debug(f"Planner stats: total={total}, completed={completed}, pending={pending}, in_progress={in_progress}")
        
        return {
            'total_topics': total,
            'completed': completed,
            'pending': pending,
            'in_progress': in_progress,
            'completion_rate': round(completion_rate, 2)
        }
    
    def save_plan(self, file_path: str = "outputs/planner.json"):
        """Save revision plan to JSON file"""
        logger.info(f"Saving plan with {len(self.revision_plan)} items to {file_path}")
        try:
            output_dir = Path(file_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                'revision_plan': self.revision_plan,
                'progress': self.progress,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Plan saved successfully")
        except Exception as e:
            logger.error(f"Error saving plan: {e}")
    
    def load_plan(self, file_path: str = "outputs/planner.json") -> List[Dict]:
        """Load revision plan from JSON file and return it"""
        logger.info(f"Loading plan from {file_path}")
        try:
            if Path(file_path).exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.revision_plan = data.get('revision_plan', [])
                    self.progress = data.get('progress', {})
                    logger.info(f"Loaded plan with {len(self.revision_plan)} items")
            else:
                logger.info("Plan file does not exist, returning empty plan")
                self.revision_plan = []
                self.progress = {}
        except Exception as e:
            logger.error(f"Error loading plan: {e}")
            self.revision_plan = []
            self.progress = {}
        
        # Return the plan for convenience
        return self.revision_plan

