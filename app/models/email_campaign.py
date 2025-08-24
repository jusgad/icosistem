"""
Email campaign model for the ecosystem.
"""

from app.extensions import db
from .base import CompleteBaseModel

class EmailCampaign(CompleteBaseModel):
    """Model for email campaigns."""
    
    __tablename__ = 'email_campaigns'
    
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='draft')
    send_date = db.Column(db.DateTime)
    recipients_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    opened_count = db.Column(db.Integer, default=0)
    clicked_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f"<EmailCampaign(name='{self.name}', status='{self.status}')>"

# Export
__all__ = ['EmailCampaign']