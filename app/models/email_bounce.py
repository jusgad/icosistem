"""
Email bounce model for the entrepreneurship ecosystem.
Tracks email bounces, delivery failures, and related provider responses.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from app.extensions import db
from .base import CompleteBaseModel


class EmailBounce(CompleteBaseModel):
    """
    Model for tracking email bounces and delivery failures.
    
    This model handles:
    - Hard bounces (permanent delivery failures)
    - Soft bounces (temporary delivery failures)
    - Spam complaints and unsubscribe requests
    - Provider-specific bounce data
    - Bounce categorization and automated handling
    """
    
    __tablename__ = 'email_bounces'
    
    # Email identification
    email = Column(String(255), nullable=False, index=True,
                  doc="Email address that bounced")
    message_id = Column(String(255), nullable=True, index=True,
                       doc="Message ID from email provider")
    
    # Bounce classification
    bounce_type = Column(String(50), nullable=False, index=True,
                        doc="Type of bounce (hard, soft, complaint, unsubscribe)")
    bounce_subtype = Column(String(100), nullable=True,
                           doc="Specific bounce subtype from provider")
    severity = Column(String(20), default='medium',
                     doc="Severity level (low, medium, high, critical)")
    
    # Bounce details
    reason = Column(Text, nullable=True,
                   doc="Human-readable bounce reason")
    diagnostic_code = Column(String(10), nullable=True,
                            doc="SMTP diagnostic code (e.g., 5.1.1)")
    status_code = Column(String(10), nullable=True,
                        doc="SMTP status code")
    
    # Provider information
    provider = Column(String(50), nullable=True,
                     doc="Email provider that reported the bounce")
    provider_data = Column(db.JSON, default=dict,
                          doc="Raw provider response data")
    
    # Email associations
    email_log_id = Column(db.String(36), nullable=True, index=True,
                         doc="Associated email log record")
    campaign_id = Column(db.String(36), nullable=True, index=True,
                        doc="Associated campaign ID")
    user_id = Column(db.String(36), nullable=True, index=True,
                    doc="Associated user ID")
    
    # Bounce handling
    is_processed = Column(Boolean, default=False,
                         doc="Whether bounce has been processed")
    action_taken = Column(String(100), nullable=True,
                         doc="Action taken in response to bounce")
    suppression_added = Column(Boolean, default=False,
                              doc="Whether email was added to suppression list")
    
    # Timing and attempts
    bounce_date = Column(DateTime, nullable=True,
                        doc="Date when bounce occurred")
    attempt_count = Column(Integer, default=1,
                          doc="Number of delivery attempts before bounce")
    
    # Additional metadata
    recipient_data = Column(db.JSON, default=dict,
                           doc="Additional recipient information")
    processing_notes = Column(Text, nullable=True,
                             doc="Notes from bounce processing")
    
    def __repr__(self):
        return f"<EmailBounce(email='{self.email}', type='{self.bounce_type}', reason='{self.reason[:50]}')>"
    
    def __str__(self):
        return f"Bounce: {self.email} - {self.bounce_type}"
    
    @property
    def is_hard_bounce(self):
        """Check if this is a hard bounce."""
        return self.bounce_type == 'hard'
    
    @property
    def is_soft_bounce(self):
        """Check if this is a soft bounce."""
        return self.bounce_type == 'soft'
    
    @property
    def is_complaint(self):
        """Check if this is a spam complaint."""
        return self.bounce_type == 'complaint'
    
    @property
    def requires_suppression(self):
        """Check if this bounce requires adding to suppression list."""
        return self.is_hard_bounce or self.is_complaint
    
    @property
    def is_permanent_failure(self):
        """Check if this represents a permanent delivery failure."""
        permanent_codes = ['5.1.1', '5.1.2', '5.1.3', '5.1.10', '5.2.1', '5.7.1']
        return (self.is_hard_bounce or 
                self.diagnostic_code in permanent_codes or
                (self.status_code and self.status_code.startswith('5')))
    
    @property
    def bounce_category(self):
        """Get user-friendly bounce category."""
        if self.is_hard_bounce:
            if self.diagnostic_code in ['5.1.1', '5.1.2']:
                return 'Invalid Email Address'
            elif self.diagnostic_code == '5.2.1':
                return 'Mailbox Full'
            elif self.diagnostic_code in ['5.7.1', '5.7.12']:
                return 'Blocked by Recipient'
            else:
                return 'Permanent Failure'
        elif self.is_soft_bounce:
            if self.diagnostic_code == '4.2.2':
                return 'Mailbox Full (Temporary)'
            elif self.diagnostic_code in ['4.3.2', '4.4.2']:
                return 'Server Temporarily Unavailable'
            else:
                return 'Temporary Failure'
        elif self.is_complaint:
            return 'Spam Complaint'
        else:
            return 'Unknown'
    
    def process_bounce(self, auto_suppress=True):
        """Process the bounce and take appropriate actions."""
        if self.is_processed:
            return
        
        actions_taken = []
        
        # Add to suppression list for permanent failures
        if auto_suppress and self.requires_suppression and not self.suppression_added:
            from .email_suppression import EmailSuppression
            
            suppression = EmailSuppression(
                email=self.email,
                reason=f"{self.bounce_type.title()} bounce: {self.reason}",
                source='bounce_handler',
                bounce_id=str(self.id),
                is_active=True
            )
            
            try:
                db.session.add(suppression)
                self.suppression_added = True
                actions_taken.append('added_to_suppression')
            except Exception as e:
                db.session.rollback()
                self.processing_notes = f"Failed to add to suppression: {str(e)}"
        
        # Update user status if applicable
        if self.user_id and self.is_hard_bounce:
            actions_taken.append('user_email_invalidated')
        
        # Mark as processed
        self.is_processed = True
        self.action_taken = ', '.join(actions_taken) if actions_taken else 'no_action'
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise
    
    @classmethod
    def get_bounce_stats(cls, days=30):
        """Get bounce statistics for the last N days."""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        stats = cls.query.filter(cls.created_at >= cutoff_date).with_entities(
            func.count(cls.id).label('total_bounces'),
            func.count(func.case([(cls.bounce_type == 'hard', 1)], else_=None)).label('hard_bounces'),
            func.count(func.case([(cls.bounce_type == 'soft', 1)], else_=None)).label('soft_bounces'),
            func.count(func.case([(cls.bounce_type == 'complaint', 1)], else_=None)).label('complaints'),
            func.count(func.distinct(cls.email)).label('unique_bounced_emails')
        ).first()
        
        return {
            'period_days': days,
            'total_bounces': stats.total_bounces or 0,
            'hard_bounces': stats.hard_bounces or 0,
            'soft_bounces': stats.soft_bounces or 0,
            'complaints': stats.complaints or 0,
            'unique_bounced_emails': stats.unique_bounced_emails or 0
        }
    
    @classmethod
    def get_top_bounce_reasons(cls, limit=10, days=30):
        """Get the most common bounce reasons."""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        reasons = cls.query.filter(
            cls.created_at >= cutoff_date,
            cls.reason.isnot(None)
        ).with_entities(
            cls.reason,
            func.count(cls.id).label('count')
        ).group_by(cls.reason).order_by(
            func.count(cls.id).desc()
        ).limit(limit).all()
        
        return [{'reason': r.reason, 'count': r.count} for r in reasons]
    
    @classmethod
    def get_email_bounce_history(cls, email):
        """Get bounce history for a specific email address."""
        return cls.query.filter_by(email=email).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def is_email_bouncing(cls, email, days=30):
        """Check if an email has bounced recently."""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_bounce = cls.query.filter(
            cls.email == email,
            cls.created_at >= cutoff_date
        ).first()
        
        return recent_bounce is not None


# Export
__all__ = ['EmailBounce']