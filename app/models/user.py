from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
import enum

from app.extensions import db

class UserRole(enum.Enum):
    ADMIN = "admin"
    ENTREPRENEUR = "entrepreneur"
    ALLY = "ally"
    CLIENT = "client"

class User(UserMixin, db.Model):
    """Modelo base para todos los usuarios de la aplicación."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    _password = Column("password", String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    
    # Información adicional
    phone = Column(String(20), nullable=True)
    profile_image = Column(String(255), nullable=True, default="default-profile.png")
    bio = Column(String(500), nullable=True)
    
    # Estado de la cuenta
    is_active = Column(Boolean, default=True)
    email_confirmed = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones - estas serían definidas en cada modelo específico
    # utilizando el patrón backref en los modelos hijos
    
    def __init__(self, email, username, password, first_name, last_name, role, **kwargs):
        self.email = email.lower()
        self.username = username
        self.password = password  # Esto activará el setter
        self.first_name = first_name
        self.last_name = last_name
        self.role = role
        
        # Procesar argumentos adicionales
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def password(self):
        """Prevenir acceso directo a la contraseña."""
        raise AttributeError('password no es un atributo legible')
    
    @password.setter
    def password(self, password):
        """Hash y establece la contraseña."""
        self._password = generate_password_hash(password)
    
    def verify_password(self, password):
        """Verifica si la contraseña proporcionada coincide con el hash almacenado."""
        return check_password_hash(self._password, password)
    
    @property
    def full_name(self):
        """Devuelve el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}"
    
    def update_last_login(self):
        """Actualiza la fecha del último inicio de sesión."""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def is_admin(self):
        """Comprueba si el usuario es un administrador."""
        return self.role == UserRole.ADMIN
    
    def is_entrepreneur(self):
        """Comprueba si el usuario es un emprendedor."""
        return self.role == UserRole.ENTREPRENEUR
    
    def is_ally(self):
        """Comprueba si el usuario es un aliado."""
        return self.role == UserRole.ALLY
    
    def is_client(self):
        """Comprueba si el usuario es un cliente."""
        return self.role == UserRole.CLIENT
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs."""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'role': self.role.value,
            'profile_image': self.profile_image,
            'bio': self.bio,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"