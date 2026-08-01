from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models here to ensure they are registered with SQLAlchemy
from .user import User
from .organization import Organization
from .subscription import Subscription, SubscriptionPlan, Invoice, PaymentMethod
from .learning import LearningModule, Exercise, UserProgress, UserResponse
from .gamification import Badge, UserBadge, UserPoints, Leaderboard
from .forum import ForumCategory, ForumTopic, ForumReply
from .notification import Notification
from .setting import Setting
from .analytics import AnalyticsEvent, AnalyticsMetric

__all__ = [
    'db',
    'User',
    'Organization', 
    'Subscription',
    'SubscriptionPlan',
    'Invoice',
    'PaymentMethod',
    'LearningModule',
    'Exercise',
    'UserProgress',
    'UserResponse',
    'Badge',
    'UserBadge',
    'UserPoints',
    'Leaderboard',
    'ForumCategory',
    'ForumTopic',
    'ForumReply',
    'Notification',
    'Setting',
    'AnalyticsEvent',
    'AnalyticsMetric'
]

