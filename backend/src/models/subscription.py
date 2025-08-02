import uuid
from datetime import datetime
from decimal import Decimal
from src.models import db

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    billing_cycle = db.Column(db.String(20), nullable=False)  # 'monthly', 'yearly'
    features = db.Column(db.JSON, nullable=False, default={})
    max_users = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    stripe_price_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan', lazy=True)
    
    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else None,
            'currency': self.currency,
            'billing_cycle': self.billing_cycle,
            'features': self.features,
            'max_users': self.max_users,
            'is_active': self.is_active,
            'stripe_price_id': self.stripe_price_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=False)
    plan_id = db.Column(db.String(36), db.ForeignKey('subscription_plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(255), unique=True)
    status = db.Column(db.String(50), nullable=False)  # 'active', 'canceled', 'past_due', 'unpaid'
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoices = db.relationship('Invoice', backref='subscription', lazy=True)
    
    def __repr__(self):
        return f'<Subscription {self.organization_id}>'
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active' and (
            not self.current_period_end or 
            datetime.utcnow() <= self.current_period_end
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'plan_id': self.plan_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'status': self.status,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'cancel_at_period_end': self.cancel_at_period_end,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=False)
    subscription_id = db.Column(db.String(36), db.ForeignKey('subscriptions.id'), nullable=False)
    stripe_invoice_id = db.Column(db.String(255), unique=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    status = db.Column(db.String(50), nullable=False)  # 'paid', 'pending', 'failed'
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Invoice {self.id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'subscription_id': self.subscription_id,
            'stripe_invoice_id': self.stripe_invoice_id,
            'amount': float(self.amount) if self.amount else None,
            'currency': self.currency,
            'status': self.status,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey('organizations.id'), nullable=False)
    stripe_payment_method_id = db.Column(db.String(255), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'card', 'bank_account'
    card_brand = db.Column(db.String(50))
    card_last4 = db.Column(db.String(4))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentMethod {self.organization_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'stripe_payment_method_id': self.stripe_payment_method_id,
            'type': self.type,
            'card_brand': self.card_brand,
            'card_last4': self.card_last4,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

