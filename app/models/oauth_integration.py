"""
OAuth Integration Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthIntegration(BaseModel, db.Model):
    """OAuth Integration model stub"""
    __tablename__ = 'oauth_integrations'
    pass

__all__ = ['OAuthIntegration']