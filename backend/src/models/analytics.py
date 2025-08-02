import uuid
from datetime import datetime
from src.models import db

class AnalyticsEvent(db.Model):
    __tablename__ = 'analytics_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    event_type = db.Column(db.String(100), nullable=False)
    event_data = db.Column(db.JSON, nullable=False, default={})
    session_id = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalyticsEvent {self.event_type}>'
    
    @staticmethod
    def track_event(event_type, organization_id=None, user_id=None, event_data=None, 
                   session_id=None, ip_address=None, user_agent=None):
        """Track a new analytics event"""
        event = AnalyticsEvent(
            event_type=event_type,
            organization_id=organization_id,
            user_id=user_id,
            event_data=event_data or {},
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(event)
        db.session.commit()
        return event
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'event_data': self.event_data,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class AnalyticsMetric(db.Model):
    __tablename__ = 'analytics_metrics'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=True)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Numeric(15, 4), nullable=False)
    dimensions = db.Column(db.JSON, default={})
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalyticsMetric {self.metric_name}>'
    
    @staticmethod
    def record_metric(metric_name, metric_value, organization_id=None, dimensions=None,
                     period_start=None, period_end=None):
        """Record a new analytics metric"""
        metric = AnalyticsMetric(
            metric_name=metric_name,
            metric_value=metric_value,
            organization_id=organization_id,
            dimensions=dimensions or {},
            period_start=period_start or datetime.utcnow(),
            period_end=period_end or datetime.utcnow()
        )
        db.session.add(metric)
        db.session.commit()
        return metric
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'metric_name': self.metric_name,
            'metric_value': float(self.metric_value) if self.metric_value else None,
            'dimensions': self.dimensions,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

