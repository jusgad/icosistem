"""
Inicialización MINIMAL de modelos para arrancar la aplicación.
"""

import logging

# Configurar logger para modelos
models_logger = logging.getLogger('ecosistema.models')

# ====================================
# IMPORTACIÓN MÍNIMA DE USER
# ====================================

# Usuario básico para que la aplicación arranque
try:
    from .user import User, UserType
    print("✅ User model loaded successfully")
except Exception as e:
    print(f"❌ Error loading User model: {e}")
    # Crear una clase User mínima como fallback
    from app.extensions import db
    from flask_login import UserMixin
    from enum import Enum
    
    class UserType(str, Enum):
        ADMIN = 'admin'
        ENTREPRENEUR = 'entrepreneur'
        ALLY = 'ally'
        CLIENT = 'client'
    
    class User(db.Model, UserMixin):
        __tablename__ = 'users'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        first_name = db.Column(db.String(50))
        last_name = db.Column(db.String(50))
        role = db.Column(db.String(20), default='entrepreneur')
        is_active = db.Column(db.Boolean, default=True)
        
        def get_id(self):
            return str(self.id)

# Exportaciones mínimas
__all__ = ['User', 'UserType']