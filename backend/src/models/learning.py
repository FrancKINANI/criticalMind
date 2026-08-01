import uuid
from datetime import datetime
from src.models import db

class LearningModule(db.Model):
    __tablename__ = 'learning_modules'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.JSON, nullable=False)
    difficulty_level = db.Column(db.Integer, default=1)
    estimated_duration = db.Column(db.Integer)  # in minutes
    is_premium = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exercises = db.relationship('Exercise', backref='module', lazy=True, cascade='all, delete-orphan')
    user_progress = db.relationship('UserProgress', backref='module', lazy=True)
    
    def __repr__(self):
        return f'<LearningModule {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'title': self.title,
            'description': self.description,
            'content': self.content,
            'difficulty_level': self.difficulty_level,
            'estimated_duration': self.estimated_duration,
            'is_premium': self.is_premium,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'exercises_count': len(self.exercises) if self.exercises else 0
        }

class Exercise(db.Model):
    __tablename__ = 'exercises'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id = db.Column(db.String(36), db.ForeignKey('learning_modules.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    question = db.Column(db.Text, nullable=False)
    exercise_type = db.Column(db.String(50), nullable=False)  # 'multiple_choice', 'essay', 'scenario'
    options = db.Column(db.JSON)  # for multiple choice questions
    correct_answer = db.Column(db.JSON)
    explanation = db.Column(db.Text)
    points = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user_responses = db.relationship('UserResponse', backref='exercise', lazy=True)
    
    def __repr__(self):
        return f'<Exercise {self.title}>'
    
    def to_dict(self, include_answers=False):
        data = {
            'id': self.id,
            'module_id': self.module_id,
            'title': self.title,
            'question': self.question,
            'exercise_type': self.exercise_type,
            'options': self.options,
            'explanation': self.explanation,
            'points': self.points,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_answers:
            data['correct_answer'] = self.correct_answer
            
        return data

class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    module_id = db.Column(db.String(36), db.ForeignKey('learning_modules.id'), nullable=False)
    completion_percentage = db.Column(db.Numeric(5, 2), default=0)
    score = db.Column(db.Integer, default=0)
    time_spent = db.Column(db.Integer, default=0)  # in minutes
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate progress records
    __table_args__ = (db.UniqueConstraint('user_id', 'module_id', name='unique_user_module_progress'),)
    
    def __repr__(self):
        return f'<UserProgress {self.user_id} - {self.module_id}>'
    
    def is_completed(self):
        """Check if the module is completed"""
        return self.completion_percentage >= 100
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'module_id': self.module_id,
            'completion_percentage': float(self.completion_percentage) if self.completion_percentage else 0,
            'score': self.score,
            'time_spent': self.time_spent,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'is_completed': self.is_completed()
        }

class UserResponse(db.Model):
    __tablename__ = 'user_responses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.String(36), db.ForeignKey('exercises.id'), nullable=False)
    response = db.Column(db.JSON, nullable=False)
    is_correct = db.Column(db.Boolean)
    points_earned = db.Column(db.Integer, default=0)
    ai_feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserResponse {self.user_id} - {self.exercise_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'exercise_id': self.exercise_id,
            'response': self.response,
            'is_correct': self.is_correct,
            'points_earned': self.points_earned,
            'ai_feedback': self.ai_feedback,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None
        }

