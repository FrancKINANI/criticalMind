from datetime import datetime

from src.models import db


class Setting(db.Model):
    """Global application settings (single row).

    Used to drive the LLM provider switch (cloud/edge):
    ``provider`` (openai | ollama), ``base_url`` and ``model_name``.
    Manageable via ``GET/PUT /api/admin/llm-settings`` (admin role).
    """

    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, default='openai')
    base_url = db.Column(db.String(500))
    model_name = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting provider={self.provider} model={self.model_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'provider': self.provider,
            'base_url': self.base_url,
            'model_name': self.model_name,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
