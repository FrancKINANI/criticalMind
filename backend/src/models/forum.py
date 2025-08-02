import uuid
from datetime import datetime
from src.models import db

class ForumCategory(db.Model):
    __tablename__ = 'forum_categories'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7))  # code couleur hex
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    topics = db.relationship('ForumTopic', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<ForumCategory {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'topics_count': len(self.topics) if self.topics else 0
        }

class ForumTopic(db.Model):
    __tablename__ = 'forum_topics'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = db.Column(db.String(36), db.ForeignKey('forum_categories.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    views_count = db.Column(db.Integer, default=0)
    replies_count = db.Column(db.Integer, default=0)
    last_reply_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    replies = db.relationship('ForumReply', backref='topic', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ForumTopic {self.title}>'
    
    def increment_views(self):
        """Increment the view count for this topic"""
        self.views_count += 1
        db.session.commit()
    
    def update_reply_stats(self):
        """Update reply count and last reply time"""
        self.replies_count = len(self.replies)
        if self.replies:
            self.last_reply_at = max(reply.created_at for reply in self.replies)
        db.session.commit()
    
    def to_dict(self, include_replies=False):
        data = {
            'id': self.id,
            'category_id': self.category_id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'is_pinned': self.is_pinned,
            'is_locked': self.is_locked,
            'views_count': self.views_count,
            'replies_count': self.replies_count,
            'last_reply_at': self.last_reply_at.isoformat() if self.last_reply_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_replies:
            data['replies'] = [reply.to_dict() for reply in self.replies]
            
        return data

class ForumReply(db.Model):
    __tablename__ = 'forum_replies'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id = db.Column(db.String(36), db.ForeignKey('forum_topics.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_solution = db.Column(db.Boolean, default=False)
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ForumReply {self.topic_id}>'
    
    def mark_as_solution(self):
        """Mark this reply as the solution for the topic"""
        # First, unmark any existing solutions for this topic
        ForumReply.query.filter_by(topic_id=self.topic_id, is_solution=True).update({'is_solution': False})
        # Then mark this reply as the solution
        self.is_solution = True
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic_id': self.topic_id,
            'user_id': self.user_id,
            'content': self.content,
            'is_solution': self.is_solution,
            'likes_count': self.likes_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

