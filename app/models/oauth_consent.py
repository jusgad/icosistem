"""
OAuth Consent Models Module - Stub for compatibility
"""

from app.extensions import db
from app.models.base import BaseModel

class OAuthConsent(BaseModel, db.Model):
    """OAuth Consent model stub"""
    __tablename__ = 'oauth_consents'
    pass

__all__ = ['OAuthConsent']