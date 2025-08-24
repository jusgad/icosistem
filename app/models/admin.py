"""
Modelo para administradores del sistema.
"""

from .user import User
from .base import CompleteBaseModel
from app.extensions import db

class Admin(CompleteBaseModel):
    """
    Modelo para administradores del sistema.
    Extiende User con funcionalidades administrativas.
    """
    
    __tablename__ = 'admins'
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Admin specific fields
    permissions = db.Column(db.JSON, default=list)
    is_super_admin = db.Column(db.Boolean, default=False)
    last_admin_action = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('admin_profile', uselist=False))
    
    def __repr__(self):
        return f"<Admin(user_id={self.user_id}, super_admin={self.is_super_admin})>"

# Export
__all__ = ['Admin']