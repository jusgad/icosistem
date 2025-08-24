"""
Email log model for the entrepreneurship ecosystem.
Tracks all email sending activities, delivery status, and metadata.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from app.extensions import db
from .base import CompleteBaseModel


class EmailLog(CompleteBaseModel):
    """
    Model for logging all email activities in the ecosystem.
    
    This model tracks:
    - Email sending attempts and results
    - Provider information and responses
    - Delivery status and error tracking
    - Campaign and template associations
    - Recipient and sender information
    """
    
    __tablename__ = 'email_logs'
    
    # Email identification
    message_id = Column(String(255), nullable=True, index=True, 
                       doc="Unique message ID from email provider")
    tracking_id = Column(String(255), nullable=True, index=True,
                        doc="Internal tracking ID for analytics")
    
    # Provider information
    provider = Column(String(50), nullable=True, 
                     doc="Email provider used (sendgrid, ses, smtp)")
    provider_response = Column(Text, nullable=True,
                              doc="Full response from email provider")
    
    # Email addresses
    to_email = Column(String(255), nullable=False, index=True,
                     doc="Primary recipient email address")
    from_email = Column(String(255), nullable=True,
                       doc="Sender email address")
    reply_to_email = Column(String(255), nullable=True,
                           doc="Reply-to email address")
    
    # Email content
    subject = Column(String(500), nullable=True,
                    doc="Email subject line")
    email_type = Column(String(100), nullable=True,
                       doc="Type of email (welcome, notification, campaign, etc.)")
    
    # Status and delivery
    status = Column(String(50), nullable=False, default='queued', index=True,
                   doc="Current status (queued, sending, sent, delivered, opened, clicked, bounced, failed)")
    delivery_status = Column(String(50), nullable=True,
                            doc="Detailed delivery status from provider")
    
    # Error handling
    error_message = Column(Text, nullable=True,
                          doc="Error message if sending failed")
    retry_count = Column(Integer, default=0,
                        doc="Number of retry attempts")
    
    # Associations
    template_id = Column(db.String(36), nullable=True, index=True,
                        doc="Associated email template ID")
    campaign_id = Column(db.String(36), nullable=True, index=True,
                        doc="Associated email campaign ID")
    user_id = Column(db.String(36), nullable=True, index=True,
                    doc="Associated user ID (recipient)")
    
    # Metadata and tracking
    tags = Column(db.JSON, default=list,
                 doc="Tags for categorization and filtering")
    email_metadata = Column(db.JSON, default=dict,
                           doc="Additional metadata and custom fields")
    
    # Timing
    sent_at = Column(DateTime, nullable=True,
                    doc="Timestamp when email was sent")
    delivered_at = Column(DateTime, nullable=True,
                         doc="Timestamp when email was delivered")
    
    # Analytics flags
    is_test = Column(Boolean, default=False,
                    doc="Whether this is a test email")
    is_transactional = Column(Boolean, default=True,
                             doc="Whether this is a transactional email")
    
    def __repr__(self):
        return f"<EmailLog(to='{self.to_email}', status='{self.status}', provider='{self.provider}')>"
    
    def __str__(self):
        return f"Email to {self.to_email} - {self.status}"
    
    @property
    def is_successful(self):
        """Check if email was successfully sent."""
        return self.status in ['sent', 'delivered', 'opened', 'clicked']
    
    @property
    def is_failed(self):
        """Check if email sending failed."""
        return self.status in ['failed', 'bounced']
    
    @property
    def has_engagement(self):
        """Check if email has any engagement (opened or clicked)."""
        return self.status in ['opened', 'clicked']
    
    @classmethod
    def get_by_message_id(cls, message_id):
        """Get email log by message ID."""
        return cls.query.filter_by(message_id=message_id).first()
    
    @classmethod
    def get_by_tracking_id(cls, tracking_id):
        """Get email log by tracking ID."""
        return cls.query.filter_by(tracking_id=tracking_id).first()
    
    @classmethod
    def get_campaign_stats(cls, campaign_id):
        """Get statistics for a specific campaign."""
        from sqlalchemy import func
        
        stats = cls.query.filter_by(campaign_id=campaign_id).with_entities(
            func.count(cls.id).label('total'),
            func.sum(func.case([(cls.status == 'sent', 1)], else_=0)).label('sent'),
            func.sum(func.case([(cls.status == 'delivered', 1)], else_=0)).label('delivered'),
            func.sum(func.case([(cls.status == 'opened', 1)], else_=0)).label('opened'),
            func.sum(func.case([(cls.status == 'clicked', 1)], else_=0)).label('clicked'),
            func.sum(func.case([(cls.status == 'failed', 1)], else_=0)).label('failed'),
            func.sum(func.case([(cls.status == 'bounced', 1)], else_=0)).label('bounced')
        ).first()
        
        return {
            'total': stats.total or 0,
            'sent': stats.sent or 0,
            'delivered': stats.delivered or 0,
            'opened': stats.opened or 0,
            'clicked': stats.clicked or 0,
            'failed': stats.failed or 0,
            'bounced': stats.bounced or 0
        }


# Export
__all__ = ['EmailLog']