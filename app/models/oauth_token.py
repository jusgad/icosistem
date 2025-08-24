"""
OAuth Token Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthToken(BaseModel, db.Model):
    """OAuth Token model stub"""
    __tablename__ = 'oauth_tokens'
    pass

__all__ = ['OAuthToken']