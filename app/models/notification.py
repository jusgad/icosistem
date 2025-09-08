"""
Notification model for the ecosystem.
"""

from app.extensions import db
from .base import CompleteBaseModel
from enum import Enum

class NotificationStatus(Enum):
    UNREAD = 'unread'
    READ = 'read'
    ARCHIVED = 'archived'

class NotificationPriority(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'

class Notification(CompleteBaseModel):
    """Model for notifications."""
    
    __tablename__ = 'notifications'
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(NotificationStatus), default=NotificationStatus.UNREAD)
    priority = db.Column(db.Enum(NotificationPriority), default=NotificationPriority.MEDIUM)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.JSON, default=dict)
    read_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    
    def __repr__(self):
        return f"<Notification(title='{self.title}', status='{self.status}')>"
    
    def mark_as_read(self):
        """Mark notification as read."""
        from datetime import datetime, timezone
        self.status = NotificationStatus.READ
        self.read_at = datetime.now(timezone.utc)

class NotificationTemplate(CompleteBaseModel):
    """Model for notification templates."""
    
    __tablename__ = 'notification_templates'
    
    name = db.Column(db.String(100), nullable=False, unique=True)
    title_template = db.Column(db.String(200), nullable=False)
    message_template = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    default_priority = db.Column(db.Enum(NotificationPriority), default=NotificationPriority.MEDIUM)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f"<NotificationTemplate(name='{self.name}', type='{self.notification_type}')>"

class NotificationPreference(CompleteBaseModel):
    """Model for user notification preferences."""
    
    __tablename__ = 'notification_preferences'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    email_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=False)
    in_app_enabled = db.Column(db.Boolean, default=True)
    
    # Relationships
    user = db.relationship('User', backref='notification_preferences')
    
    def __repr__(self):
        return f"<NotificationPreference(user_id={self.user_id}, type='{self.notification_type}')>"

# Export
__all__ = ['Notification', 'NotificationTemplate', 'NotificationPreference', 'NotificationStatus', 'NotificationPriority']