"""
OAuth Provider Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthProvider(BaseModel, db.Model):
    """OAuth Provider model stub"""
    __tablename__ = 'oauth_providers'
    pass

__all__ = ['OAuthProvider']