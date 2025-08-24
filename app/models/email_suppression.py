"""
Email suppression model for the entrepreneurship ecosystem.
Manages suppression lists to comply with regulations and handle unsubscribes.
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, Index
from app.extensions import db
from .base import CompleteBaseModel


class EmailSuppression(CompleteBaseModel):
    """
    Model for managing email suppression lists.
    
    This model handles:
    - Unsubscribe requests from recipients
    - Bounced email addresses (hard bounces)
    - Spam complaints and abuse reports
    - Manual suppressions by admins
    - Compliance with CAN-SPAM and GDPR
    - Global and category-specific suppressions
    """
    
    __tablename__ = 'email_suppressions'
    
    # Email identification
    email = Column(String(255), nullable=False, index=True,
                  doc="Email address to suppress")
    email_domain = Column(String(255), nullable=True, index=True,
                         doc="Domain part of the email for domain-level analysis")
    
    # Suppression details
    reason = Column(Text, nullable=False,
                   doc="Reason for suppression")
    source = Column(String(100), nullable=False,
                   doc="Source of suppression (manual, bounce, complaint, unsubscribe)")
    suppression_type = Column(String(50), default='global',
                             doc="Type of suppression (global, category, campaign)")
    
    # Status and activity
    is_active = Column(Boolean, default=True, index=True,
                      doc="Whether suppression is currently active")
    is_permanent = Column(Boolean, default=False,
                         doc="Whether this is a permanent suppression")
    
    # Categorization
    categories = Column(db.JSON, default=list,
                       doc="Email categories to suppress (empty = all)")
    tags = Column(db.JSON, default=list,
                 doc="Tags for organization and filtering")
    
    # Associated records
    bounce_id = Column(db.String(36), nullable=True,
                      doc="Associated bounce record ID")
    user_id = Column(db.String(36), nullable=True, index=True,
                    doc="Associated user ID if known")
    campaign_id = Column(db.String(36), nullable=True,
                        doc="Campaign that triggered suppression")
    
    # Timing and lifecycle
    suppressed_at = Column(DateTime, nullable=True,
                          doc="When suppression became active")
    expires_at = Column(DateTime, nullable=True,
                       doc="When suppression expires (if temporary)")
    last_attempt = Column(DateTime, nullable=True,
                         doc="Last time we attempted to send to this email")
    
    # Admin and audit
    added_by_id = Column(db.String(36), nullable=True,
                        doc="Admin user who added the suppression")
    removal_reason = Column(Text, nullable=True,
                           doc="Reason for removal if deactivated")
    
    # Additional metadata
    suppression_metadata = Column(db.JSON, default=dict,
                                 doc="Additional suppression metadata")
    
    # Create compound indexes for better query performance
    __table_args__ = (
        Index('ix_email_suppression_email_active', 'email', 'is_active'),
        Index('ix_email_suppression_domain_active', 'email_domain', 'is_active'),
        Index('ix_email_suppression_source_active', 'source', 'is_active'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Extract domain from email
        if self.email and '@' in self.email:
            self.email_domain = self.email.split('@')[1].lower()
        
        # Set suppressed_at if not provided
        if self.is_active and not self.suppressed_at:
            from datetime import datetime
            self.suppressed_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<EmailSuppression(email='{self.email}', source='{self.source}', active={self.is_active})>"
    
    def __str__(self):
        return f"Suppressed: {self.email} ({self.source})"
    
    @property
    def is_expired(self):
        """Check if suppression has expired."""
        if not self.expires_at:
            return False
        
        from datetime import datetime
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_global_suppression(self):
        """Check if this is a global suppression (all email types)."""
        return self.suppression_type == 'global' or not self.categories
    
    @property
    def suppression_category_names(self):
        """Get human-readable category names."""
        category_map = {
            'marketing': 'Marketing Emails',
            'newsletter': 'Newsletter',
            'transactional': 'Transactional Emails',
            'notification': 'Notifications',
            'campaign': 'Email Campaigns',
            'welcome': 'Welcome Emails',
            'reminder': 'Reminders'
        }
        
        if not self.categories:
            return ['All Email Types']
        
        return [category_map.get(cat, cat.title()) for cat in self.categories]
    
    def is_suppressed_for_category(self, category):
        """Check if email is suppressed for a specific category."""
        if not self.is_active or self.is_expired:
            return False
        
        # Global suppression affects all categories
        if self.is_global_suppression:
            return True
        
        # Category-specific suppression
        return category in (self.categories or [])
    
    def add_category(self, category):
        """Add a category to the suppression."""
        if not self.categories:
            self.categories = []
        
        if category not in self.categories:
            self.categories.append(category)
            
            # Mark as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(self, 'categories')
    
    def remove_category(self, category):
        """Remove a category from the suppression."""
        if self.categories and category in self.categories:
            self.categories.remove(category)
            
            # Mark as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(self, 'categories')
    
    def deactivate(self, reason=None):
        """Deactivate the suppression."""
        self.is_active = False
        self.removal_reason = reason
        
        from datetime import datetime
        self.updated_at = datetime.utcnow()
    
    def reactivate(self):
        """Reactivate the suppression."""
        self.is_active = True
        self.removal_reason = None
        
        from datetime import datetime
        self.suppressed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def record_send_attempt(self):
        """Record that we attempted to send to this email."""
        from datetime import datetime
        self.last_attempt = datetime.utcnow()
    
    @classmethod
    def is_email_suppressed(cls, email, category=None):
        """
        Check if an email address is suppressed.
        
        Args:
            email: Email address to check
            category: Specific category to check (optional)
            
        Returns:
            bool: True if email is suppressed
        """
        email = email.lower()
        
        # Check for active suppressions
        query = cls.query.filter(
            cls.email == email,
            cls.is_active == True
        )
        
        suppressions = query.all()
        
        for suppression in suppressions:
            # Skip expired suppressions
            if suppression.is_expired:
                continue
            
            # Check category-specific suppression
            if category:
                if suppression.is_suppressed_for_category(category):
                    return True
            else:
                # No category specified, check for any active suppression
                return True
        
        return False
    
    @classmethod
    def get_suppressed_emails(cls, category=None, active_only=True):
        """Get list of suppressed email addresses."""
        query = cls.query
        
        if active_only:
            query = query.filter(cls.is_active == True)
        
        suppressions = query.all()
        
        if not category:
            return [s.email for s in suppressions if not s.is_expired]
        
        return [
            s.email for s in suppressions 
            if not s.is_expired and s.is_suppressed_for_category(category)
        ]
    
    @classmethod
    def add_suppression(cls, email, reason, source='manual', **kwargs):
        """
        Add an email to the suppression list.
        
        Args:
            email: Email address to suppress
            reason: Reason for suppression
            source: Source of suppression
            **kwargs: Additional fields
            
        Returns:
            EmailSuppression: The created or updated suppression record
        """
        email = email.lower()
        
        # Check if suppression already exists
        existing = cls.query.filter_by(email=email).first()
        
        if existing:
            # Reactivate if inactive
            if not existing.is_active:
                existing.reactivate()
                existing.reason = reason
                existing.source = source
            return existing
        
        # Create new suppression
        suppression = cls(
            email=email,
            reason=reason,
            source=source,
            is_active=True,
            **kwargs
        )
        
        db.session.add(suppression)
        return suppression
    
    @classmethod
    def remove_suppression(cls, email, reason=None):
        """Remove an email from the suppression list."""
        email = email.lower()
        
        suppression = cls.query.filter_by(
            email=email,
            is_active=True
        ).first()
        
        if suppression:
            suppression.deactivate(reason)
            return True
        
        return False
    
    @classmethod
    def get_suppression_stats(cls, days=30):
        """Get suppression statistics."""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total active suppressions
        total_active = cls.query.filter_by(is_active=True).count()
        
        # Recent suppressions
        recent = cls.query.filter(cls.created_at >= cutoff_date).count()
        
        # Suppressions by source
        by_source = cls.query.filter_by(is_active=True).with_entities(
            cls.source,
            func.count(cls.id).label('count')
        ).group_by(cls.source).all()
        
        return {
            'total_active': total_active,
            'recent_additions': recent,
            'by_source': {s.source: s.count for s in by_source}
        }
    
    @classmethod
    def cleanup_expired(cls):
        """Deactivate expired suppressions."""
        from datetime import datetime
        
        now = datetime.utcnow()
        
        expired_count = cls.query.filter(
            cls.is_active == True,
            cls.expires_at <= now
        ).update({
            'is_active': False,
            'removal_reason': 'Automatically expired',
            'updated_at': now
        })
        
        if expired_count > 0:
            db.session.commit()
        
        return expired_count


# Export
__all__ = ['EmailSuppression']