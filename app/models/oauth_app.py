"""
OAuth App Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthApp(BaseModel, db.Model):
    """OAuth App model stub"""
    __tablename__ = 'oauth_apps'
    pass

__all__ = ['OAuthApp']