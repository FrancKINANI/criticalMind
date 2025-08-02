import uuid
from datetime import datetime
from src.models import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'badge_earned', 'reply_received', 'payment_failed'
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text)
    data = db.Column(db.JSON)  # Additional data for the notification
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.user_id} - {self.type}>'
    
    def mark_as_read(self):
        """Mark this notification as read"""
        self.is_read = True
        db.session.commit()
    
    @staticmethod
    def create_notification(user_id, notification_type, title, message=None, data=None):
        """Create a new notification for a user"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            data=data or {}
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def get_unread_count(user_id):
        """Get the count of unread notifications for a user"""
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

