import uuid
from datetime import datetime
from src.models import db

class Badge(db.Model):
    __tablename__ = 'badges'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon_url = db.Column(db.String(255))
    criteria = db.Column(db.JSON, nullable=False)  # conditions pour obtenir le badge
    points_value = db.Column(db.Integer, default=0)
    rarity = db.Column(db.String(20), default='common')  # 'common', 'rare', 'epic', 'legendary'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user_badges = db.relationship('UserBadge', backref='badge', lazy=True)
    
    def __repr__(self):
        return f'<Badge {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'description': self.description,
            'icon_url': self.icon_url,
            'criteria': self.criteria,
            'points_value': self.points_value,
            'rarity': self.rarity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'earned_count': len(self.user_badges) if self.user_badges else 0
        }

class UserBadge(db.Model):
    __tablename__ = 'user_badges'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    badge_id = db.Column(db.String(36), db.ForeignKey('badges.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate badges
    __table_args__ = (db.UniqueConstraint('user_id', 'badge_id', name='unique_user_badge'),)
    
    def __repr__(self):
        return f'<UserBadge {self.user_id} - {self.badge_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'badge_id': self.badge_id,
            'earned_at': self.earned_at.isoformat() if self.earned_at else None
        }

class UserPoints(db.Model):
    __tablename__ = 'user_points'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(100), nullable=False)  # 'exercise_completion', 'badge_earned', 'daily_login'
    description = db.Column(db.Text)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserPoints {self.user_id} - {self.points}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'points': self.points,
            'source': self.source,
            'description': self.description,
            'earned_at': self.earned_at.isoformat() if self.earned_at else None
        }

class Leaderboard(db.Model):
    __tablename__ = 'leaderboards'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'weekly', 'monthly', 'all_time'
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Leaderboard {self.name}>'
    
    def get_rankings(self, limit=10):
        """Get the top users for this leaderboard"""
        from src.models.user import User
        
        # Base query to get user points
        query = db.session.query(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            db.func.sum(UserPoints.points).label('total_points')
        ).join(UserPoints).filter(User.organization_id == self.organization_id)
        
        # Filter by date range if specified
        if self.start_date:
            query = query.filter(UserPoints.earned_at >= self.start_date)
        if self.end_date:
            query = query.filter(UserPoints.earned_at <= self.end_date)
        
        # Group by user and order by total points
        rankings = query.group_by(User.id).order_by(
            db.func.sum(UserPoints.points).desc()
        ).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'user_id': user.id,
                'user_name': f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.email,
                'total_points': int(user.total_points) if user.total_points else 0
            }
            for idx, user in enumerate(rankings)
        ]
    
    def to_dict(self, include_rankings=False):
        data = {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'type': self.type,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_rankings:
            data['rankings'] = self.get_rankings()
            
        return data

