"""
OAuth Audit Log Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthAuditLog(BaseModel, db.Model):
    """OAuth Audit Log model stub"""
    __tablename__ = 'oauth_audit_logs'
    pass

__all__ = ['OAuthAuditLog']