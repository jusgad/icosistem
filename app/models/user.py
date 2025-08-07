"""
Modelo de usuario base para el ecosistema de emprendimiento.
Este módulo define la clase User que sirve como base para todos los tipos de usuarios.
"""

import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from flask import current_app, url_for
from flask_login import UserMixin
from flask_principal import Identity, AnonymousIdentity, identity_changed
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Index, event
from sqlalchemy.orm import validates, relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.dialects.postgresql import JSONB
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, login_manager
from app.core.constants import (
    USER_ROLES, VALID_ROLES, ADMIN_ROLE, ENTREPRENEUR_ROLE, 
    ALLY_ROLE, CLIENT_ROLE, TIMEZONE_BOGOTA
)
from app.core.security import validate_password_strength, validate_email_format
from .base import CompleteBaseModel, JSONType
from .mixins import SearchableMixin, CacheableMixin, NotifiableMixin, ValidatableMixin

# Configurar logger
user_logger = logging.getLogger('ecosistema.models.user')


# ====================================
# MODELO USUARIO BASE
# ====================================

class User(CompleteBaseModel, UserMixin, SearchableMixin, CacheableMixin, 
           NotifiableMixin, ValidatableMixin):
    """
    Modelo de usuario base que implementa autenticación, autorización y perfil básico.
    Sirve como clase padre para todos los tipos específicos de usuarios.
    """
    
    __tablename__ = 'users'
    __searchable__ = ['first_name', 'last_name', 'email', 'company', 'bio']
    
    # ====================================
    # CAMPOS BÁSICOS DE AUTENTICACIÓN
    # ====================================
    
    email = Column(String(120), unique=True, nullable=False, index=True,
                  doc="Email único del usuario")
    
    password_hash = Column(String(255), nullable=False,
                          doc="Hash de la contraseña")
    
    is_active = Column(Boolean, default=True, nullable=False, index=True,
                      doc="Indica si el usuario está activo")
    
    email_verified = Column(Boolean, default=False, nullable=False,
                           doc="Indica si el email ha sido verificado")
    
    email_verification_token = Column(String(255), nullable=True,
                                     doc="Token para verificación de email")
    
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True,
                                       doc="Fecha de envío del token de verificación")
    
    # ====================================
    # INFORMACIÓN PERSONAL
    # ====================================
    
    first_name = Column(String(80), nullable=False,
                       doc="Nombre del usuario")
    
    last_name = Column(String(80), nullable=False,
                      doc="Apellido del usuario")
    
    phone = Column(String(20), nullable=True,
                  doc="Número de teléfono")
    
    date_of_birth = Column(DateTime(timezone=True), nullable=True,
                          doc="Fecha de nacimiento")
    
    gender = Column(String(20), nullable=True,
                   doc="Género del usuario")
    
    country = Column(String(100), default='Colombia', nullable=True,
                    doc="País de residencia")
    
    city = Column(String(100), nullable=True,
                 doc="Ciudad de residencia")
    
    address = Column(Text, nullable=True,
                    doc="Dirección completa")
    
    bio = Column(Text, nullable=True,
                doc="Biografía o descripción personal")
    
    # ====================================
    # INFORMACIÓN PROFESIONAL
    # ====================================
    
    role = Column(String(50), nullable=False, index=True,
                 doc="Rol del usuario en el sistema")
    
    company = Column(String(150), nullable=True,
                    doc="Empresa actual")
    
    job_title = Column(String(150), nullable=True,
                      doc="Cargo o título profesional")
    
    industry = Column(String(100), nullable=True,
                     doc="Industria o sector")
    
    experience_years = Column(Integer, nullable=True,
                             doc="Años de experiencia profesional")
    
    education_level = Column(String(100), nullable=True,
                            doc="Nivel educativo")
    
    skills = Column(JSONType, default=list,
                   doc="Lista de habilidades")
    
    interests = Column(JSONType, default=list,
                      doc="Lista de intereses")
    
    languages = Column(JSONType, default=lambda: ['Spanish'],
                      doc="Idiomas que habla")
    
    # ====================================
    # CONFIGURACIONES Y PREFERENCIAS
    # ====================================
    
    timezone = Column(String(50), default='America/Bogota',
                     doc="Zona horaria del usuario")
    
    language = Column(String(10), default='es',
                     doc="Idioma preferido")
    
    theme = Column(String(20), default='light',
                  doc="Tema visual preferido")
    
    email_notifications = Column(Boolean, default=True,
                                doc="Recibir notificaciones por email")
    
    sms_notifications = Column(Boolean, default=False,
                              doc="Recibir notificaciones por SMS")
    
    push_notifications = Column(Boolean, default=True,
                               doc="Recibir notificaciones push")
    
    newsletter_subscription = Column(Boolean, default=True,
                                    doc="Suscripción al newsletter")
    
    privacy_settings = Column(JSONType, default=dict,
                             doc="Configuraciones de privacidad")
    
    # ====================================
    # CAMPOS DE SEGURIDAD
    # ====================================
    
    last_login_at = Column(DateTime(timezone=True), nullable=True,
                          doc="Fecha del último login")
    
    last_login_ip = Column(String(45), nullable=True,
                          doc="IP del último login")
    
    failed_login_attempts = Column(Integer, default=0,
                                  doc="Intentos fallidos de login")
    
    locked_until = Column(DateTime(timezone=True), nullable=True,
                         doc="Fecha hasta la cual está bloqueado")
    
    password_reset_token = Column(String(255), nullable=True,
                                 doc="Token para reseteo de contraseña")
    
    password_reset_sent_at = Column(DateTime(timezone=True), nullable=True,
                                   doc="Fecha de envío del token de reset")
    
    two_factor_enabled = Column(Boolean, default=False,
                               doc="Autenticación de dos factores habilitada")
    
    two_factor_secret = Column(String(255), nullable=True,
                              doc="Secreto para 2FA")
    
    backup_codes = Column(JSONType, default=list,
                         doc="Códigos de respaldo para 2FA")
    
    # ====================================
    # CAMPOS DE ACTIVIDAD
    # ====================================
    
    profile_completion = Column(Integer, default=0,
                               doc="Porcentaje de completitud del perfil")
    
    last_activity_at = Column(DateTime(timezone=True), nullable=True,
                             doc="Fecha de última actividad")
    
    total_logins = Column(Integer, default=0,
                         doc="Total de logins realizados")
    
    # ====================================
    # CAMPOS SOCIALES Y REDES
    # ====================================
    
    website = Column(String(200), nullable=True,
                    doc="Sitio web personal o profesional")
    
    linkedin_url = Column(String(200), nullable=True,
                         doc="URL de LinkedIn")
    
    twitter_url = Column(String(200), nullable=True,
                        doc="URL de Twitter")
    
    github_url = Column(String(200), nullable=True,
                       doc="URL de GitHub")
    
    social_links = Column(JSONType, default=dict,
                         doc="Enlaces a redes sociales adicionales")
    
    # ====================================
    # IMAGEN DE PERFIL
    # ====================================
    
    avatar_filename = Column(String(255), nullable=True,
                            doc="Nombre del archivo de avatar")
    
    avatar_url = Column(String(500), nullable=True,
                       doc="URL del avatar (externa)")
    
    # ====================================
    # CONFIGURACIÓN DE NOTIFICACIONES
    # ====================================
    
    # Configurar notificaciones automáticas
    _notification_events = {
        'created': {'template': 'user_welcome', 'enabled': True},
        'profile_updated': {'template': 'profile_updated', 'enabled': False},
        'password_changed': {'template': 'password_changed', 'enabled': True},
        'login_from_new_device': {'template': 'new_device_login', 'enabled': True}
    }
    
    # ====================================
    # PROPIEDADES Y MÉTODOS
    # ====================================
    
    @hybrid_property
    def full_name(self):
        """Nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()
    
    @full_name.expression
    def full_name(cls):
        from sqlalchemy import func
        return func.concat(cls.first_name, ' ', cls.last_name)
    
    @hybrid_property
    def display_name(self):
        """Nombre para mostrar (prioriza nombre completo, luego email)."""
        if self.first_name and self.last_name:
            return self.full_name
        elif self.first_name:
            return self.first_name
        else:
            return self.email.split('@')[0]
    
    @property
    def initials(self):
        """Iniciales del usuario."""
        initials = ""
        if self.first_name:
            initials += self.first_name[0].upper()
        if self.last_name:
            initials += self.last_name[0].upper()
        return initials or self.email[0].upper()
    
    @property
    def age(self):
        """Edad del usuario."""
        if self.date_of_birth:
            today = datetime.now().date()
            birth_date = self.date_of_birth.date()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return None
    
    @property
    def is_admin(self):
        """Verificar si el usuario es administrador."""
        return self.role == ADMIN_ROLE
    
    @property
    def is_entrepreneur(self):
        """Verificar si el usuario es emprendedor."""
        return self.role == ENTREPRENEUR_ROLE
    
    @property
    def is_ally(self):
        """Verificar si el usuario es aliado/mentor."""
        return self.role == ALLY_ROLE
    
    @property
    def is_client(self):
        """Verificar si el usuario es cliente."""
        return self.role == CLIENT_ROLE
    
    @property
    def role_display_name(self):
        """Nombre legible del rol."""
        return USER_ROLES.get(self.role, {}).get('name', self.role.title())
    
    @property
    def avatar_url_or_default(self):
        """URL del avatar o avatar por defecto."""
        if self.avatar_url:
            return self.avatar_url
        elif self.avatar_filename:
            return url_for('static', filename=f'uploads/avatars/{self.avatar_filename}')
        else:
            # Avatar por defecto usando iniciales
            return f"https://ui-avatars.com/api/?name={self.initials}&background=0D8ABC&color=fff&size=200"
    
    @property
    def is_profile_complete(self):
        """Verificar si el perfil está completo."""
        return self.profile_completion >= 80
    
    @property
    def is_email_verified(self):
        """Verificar si el email está verificado."""
        return self.email_verified
    
    @property
    def is_locked(self):
        """Verificar si la cuenta está bloqueada."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False
    
    @property
    def can_login(self):
        """Verificar si el usuario puede hacer login."""
        return self.is_active and not self.is_locked
    
    # ====================================
    # MÉTODOS DE CONTRASEÑA
    # ====================================
    
    def set_password(self, password: str, validate: bool = True):
        """
        Establecer contraseña con validación opcional.
        
        Args:
            password: Nueva contraseña
            validate: Si validar fortaleza de la contraseña
        """
        if validate:
            validation_result = validate_password_strength(password)
            if not validation_result['is_valid']:
                raise ValueError(f"Contraseña inválida: {', '.join(validation_result['errors'])}")
        
        self.password_hash = generate_password_hash(password)
        
        # Resetear intentos fallidos
        self.failed_login_attempts = 0
        self.locked_until = None
        
        user_logger.info(f"Password changed for user: {self.email}")
    
    def check_password(self, password: str) -> bool:
        """
        Verificar contraseña.
        
        Args:
            password: Contraseña a verificar
            
        Returns:
            True si la contraseña es correcta
        """
        if not self.password_hash:
            return False
        
        return check_password_hash(self.password_hash, password)
    
    def generate_password_reset_token(self) -> str:
        """Generar token para reseteo de contraseña."""
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_sent_at = datetime.utcnow()
        
        db.session.commit()
        user_logger.info(f"Password reset token generated for user: {self.email}")
        
        return token
    
    def verify_password_reset_token(self, token: str, max_age_hours: int = 24) -> bool:
        """
        Verificar token de reseteo de contraseña.
        
        Args:
            token: Token a verificar
            max_age_hours: Máximo tiempo de validez en horas
            
        Returns:
            True si el token es válido
        """
        if not self.password_reset_token or self.password_reset_token != token:
            return False
        
        if not self.password_reset_sent_at:
            return False
        
        # Verificar expiración
        expiry_time = self.password_reset_sent_at + timedelta(hours=max_age_hours)
        if datetime.utcnow() > expiry_time:
            return False
        
        return True
    
    def clear_password_reset_token(self):
        """Limpiar token de reseteo de contraseña."""
        self.password_reset_token = None
        self.password_reset_sent_at = None
        db.session.commit()
    
    # ====================================
    # MÉTODOS DE VERIFICACIÓN DE EMAIL
    # ====================================
    
    def generate_email_verification_token(self) -> str:
        """Generar token para verificación de email."""
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        self.email_verification_sent_at = datetime.utcnow()
        
        db.session.commit()
        user_logger.info(f"Email verification token generated for user: {self.email}")
        
        return token
    
    def verify_email_token(self, token: str, max_age_hours: int = 48) -> bool:
        """
        Verificar token de verificación de email.
        
        Args:
            token: Token a verificar
            max_age_hours: Máximo tiempo de validez en horas
            
        Returns:
            True si el token es válido
        """
        if not self.email_verification_token or self.email_verification_token != token:
            return False
        
        if not self.email_verification_sent_at:
            return False
        
        # Verificar expiración
        expiry_time = self.email_verification_sent_at + timedelta(hours=max_age_hours)
        if datetime.utcnow() > expiry_time:
            return False
        
        return True
    
    def confirm_email(self, token: str = None) -> bool:
        """
        Confirmar email del usuario.
        
        Args:
            token: Token de verificación (opcional)
            
        Returns:
            True si se confirmó exitosamente
        """
        if token and not self.verify_email_token(token):
            return False
        
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None
        
        db.session.commit()
        user_logger.info(f"Email verified for user: {self.email}")
        
        return True
    
    # ====================================
    # MÉTODOS DE AUTENTICACIÓN
    # ====================================
    
    def record_login(self, ip_address: str = None):
        """
        Registrar login exitoso.
        
        Args:
            ip_address: Dirección IP del login
        """
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.total_logins += 1
        self.failed_login_attempts = 0
        self.locked_until = None
        
        db.session.commit()
        user_logger.info(f"Successful login for user: {self.email} from IP: {ip_address}")
    
    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 15):
        """
        Registrar intento fallido de login.
        
        Args:
            max_attempts: Máximo número de intentos antes de bloqueo
            lockout_minutes: Minutos de bloqueo
        """
        self.failed_login_attempts += 1
        
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
            user_logger.warning(f"User locked due to failed attempts: {self.email}")
        
        db.session.commit()
        user_logger.warning(f"Failed login attempt for user: {self.email} (attempts: {self.failed_login_attempts})")
    
    def unlock_account(self):
        """Desbloquear cuenta manualmente."""
        self.failed_login_attempts = 0
        self.locked_until = None
        db.session.commit()
        user_logger.info(f"Account unlocked for user: {self.email}")
    
    # ====================================
    # MÉTODOS DE PERFIL
    # ====================================
    
    def calculate_profile_completion(self) -> int:
        """
        Calcular porcentaje de completitud del perfil.
        
        Returns:
            Porcentaje de completitud (0-100)
        """
        fields_to_check = [
            'first_name', 'last_name', 'phone', 'bio', 'company',
            'job_title', 'industry', 'city', 'date_of_birth'
        ]
        
        completed_fields = 0
        total_fields = len(fields_to_check)
        
        for field in fields_to_check:
            value = getattr(self, field, None)
            if value and (not isinstance(value, str) or value.strip()):
                completed_fields += 1
        
        # Campos adicionales
        if self.skills and len(self.skills) > 0:
            completed_fields += 1
            total_fields += 1
        
        if self.avatar_filename or self.avatar_url:
            completed_fields += 1
            total_fields += 1
        
        if self.email_verified:
            completed_fields += 1
            total_fields += 1
        
        completion_percentage = int((completed_fields / total_fields) * 100)
        self.profile_completion = completion_percentage
        
        return completion_percentage
    
    def update_profile(self, data: Dict[str, Any], calculate_completion: bool = True):
        """
        Actualizar perfil del usuario.
        
        Args:
            data: Datos a actualizar
            calculate_completion: Si recalcular completitud del perfil
        """
        # Campos que se pueden actualizar directamente
        updatable_fields = [
            'first_name', 'last_name', 'phone', 'date_of_birth', 'gender',
            'country', 'city', 'address', 'bio', 'company', 'job_title',
            'industry', 'experience_years', 'education_level', 'skills',
            'interests', 'languages', 'website', 'linkedin_url', 'twitter_url',
            'github_url', 'social_links'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(self, field, data[field])
        
        if calculate_completion:
            self.calculate_profile_completion()
        
        db.session.commit()
        user_logger.info(f"Profile updated for user: {self.email}")
    
    def update_preferences(self, preferences: Dict[str, Any]):
        """
        Actualizar preferencias del usuario.
        
        Args:
            preferences: Diccionario con preferencias
        """
        preference_fields = [
            'timezone', 'language', 'theme', 'email_notifications',
            'sms_notifications', 'push_notifications', 'newsletter_subscription'
        ]
        
        for field in preference_fields:
            if field in preferences:
                setattr(self, field, preferences[field])
        
        if 'privacy_settings' in preferences:
            self.privacy_settings.update(preferences['privacy_settings'])
        
        db.session.commit()
        user_logger.info(f"Preferences updated for user: {self.email}")
    
    # ====================================
    # MÉTODOS DE ACTIVIDAD
    # ====================================
    
    def update_last_activity(self):
        """Actualizar timestamp de última actividad."""
        self.last_activity_at = datetime.utcnow()
        db.session.commit()
    
    def is_online(self, minutes_threshold: int = 15) -> bool:
        """
        Verificar si el usuario está en línea.
        
        Args:
            minutes_threshold: Minutos para considerar en línea
            
        Returns:
            True si está en línea
        """
        if not self.last_activity_at:
            return False
        
        threshold_time = datetime.utcnow() - timedelta(minutes=minutes_threshold)
        return self.last_activity_at > threshold_time
    
    # ====================================
    # MÉTODOS FLASK-LOGIN
    # ====================================
    
    def get_id(self):
        """Método requerido por Flask-Login."""
        return str(self.id)
    
    @property
    def is_authenticated(self):
        """Usuario está autenticado."""
        return True
    
    @property
    def is_anonymous(self):
        """Usuario no es anónimo."""
        return False
    
    def is_active_user(self):
        """Usuario está activo (para Flask-Login)."""
        return self.is_active and not self.is_locked
    
    # ====================================
    # VALIDADORES
    # ====================================
    
    @validates('email')
    def validate_email(self, key, email):
        """Validar formato de email."""
        if not email:
            raise ValueError("Email es requerido")
        
        validation_result = validate_email_format(email)
        if not validation_result['is_valid']:
            raise ValueError(f"Email inválido: {validation_result.get('error', 'Formato incorrecto')}")
        
        return validation_result['normalized_email']
    
    @validates('role')
    def validate_role(self, key, role):
        """Validar rol del usuario."""
        if role not in VALID_ROLES:
            raise ValueError(f"Rol inválido: {role}. Roles válidos: {', '.join(VALID_ROLES)}")
        return role
    
    @validates('phone')
    def validate_phone(self, key, phone):
        """Validar formato de teléfono."""
        if phone:
            # Limpiar número
            clean_phone = re.sub(r'[^\d+]', '', phone)
            
            # Patrones válidos para Colombia
            patterns = [
                r'^\+57[13][0-9]{9}$',  # +57 + código área + número
                r'^[13][0-9]{9}$',       # Sin código país
                r'^3[0-9]{9}$'           # Celular
            ]
            
            if not any(re.match(pattern, clean_phone) for pattern in patterns):
                raise ValueError("Formato de teléfono inválido")
            
            return clean_phone
        return phone
    
    # ====================================
    # MÉTODOS DE SERIALIZACIÓN
    # ====================================
    
    def to_dict(self, include_sensitive: bool = False, include_relationships: bool = False, 
                exclude_fields: List[str] = None) -> Dict[str, Any]:
        """
        Convertir usuario a diccionario con opciones de seguridad.
        
        Args:
            include_sensitive: Incluir campos sensibles
            include_relationships: Incluir relaciones
            exclude_fields: Campos a excluir
            
        Returns:
            Diccionario con datos del usuario
        """
        # Campos sensibles que solo se incluyen si se solicita explícitamente
        sensitive_fields = [
            'password_hash', 'password_reset_token', 'email_verification_token',
            'two_factor_secret', 'backup_codes', 'failed_login_attempts',
            'locked_until', 'last_login_ip'
        ]
        
        # Campos por defecto a excluir
        default_exclude = sensitive_fields if not include_sensitive else []
        exclude_fields = (exclude_fields or []) + default_exclude
        
        # Obtener diccionario base
        data = super().to_dict(include_relationships=include_relationships, 
                              exclude_fields=exclude_fields)
        
        # Añadir campos calculados
        data.update({
            'full_name': self.full_name,
            'display_name': self.display_name,
            'initials': self.initials,
            'role_display_name': self.role_display_name,
            'avatar_url': self.avatar_url_or_default,
            'is_profile_complete': self.is_profile_complete,
            'is_online': self.is_online(),
            'age': self.age
        })
        
        return data
    
    def to_public_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario con solo información pública."""
        return {
            'id': str(self.id),
            'display_name': self.display_name,
            'role': self.role,
            'role_display_name': self.role_display_name,
            'company': self.company,
            'job_title': self.job_title,
            'city': self.city,
            'country': self.country,
            'avatar_url': self.avatar_url_or_default,
            'bio': self.bio,
            'skills': self.skills,
            'interests': self.interests,
            'website': self.website,
            'social_links': self.social_links,
            'is_online': self.is_online()
        }
    
    # ====================================
    # MÉTODOS DE CONSULTA ESTÁTICOS
    # ====================================
    
    @classmethod
    def find_by_email(cls, email: str):
        """Buscar usuario por email."""
        return cls.query.filter_by(email=email.lower()).first()
    
    @classmethod
    def find_by_role(cls, role: str):
        """Buscar usuarios por rol."""
        return cls.query.filter_by(role=role, is_active=True).all()
    
    @classmethod
    def get_active_users(cls, limit: int = None):
        """Obtener usuarios activos."""
        query = cls.query.filter_by(is_active=True)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @classmethod
    def get_recent_users(cls, days: int = 7, limit: int = 10):
        """Obtener usuarios registrados recientemente."""
        threshold_date = datetime.utcnow() - timedelta(days=days)
        return cls.query.filter(
            cls.created_at >= threshold_date,
            cls.is_active == True
        ).order_by(cls.created_at.desc()).limit(limit).all()
    
    # ====================================
    # REPRESENTACIÓN
    # ====================================
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
    
    def __str__(self):
        return f"{self.display_name} ({self.email})"


# ====================================
# ÍNDICES DE BASE DE DATOS
# ====================================

# Índices compuestos para consultas comunes
Index('idx_user_role_active', User.role, User.is_active)
Index('idx_user_email_verified', User.email, User.email_verified)
Index('idx_user_created_active', User.created_at, User.is_active)


# ====================================
# EVENTOS DEL MODELO
# ====================================

@event.listens_for(User, 'before_insert')
def set_user_defaults(mapper, connection, target):
    """Establecer valores por defecto antes de insertar."""
    # Normalizar email
    if target.email:
        target.email = target.email.lower()
    
    # Calcular completitud del perfil inicial
    target.calculate_profile_completion()


@event.listens_for(User, 'before_update')
def update_user_fields(mapper, connection, target):
    """Actualizar campos antes de actualizar."""
    # Normalizar email si cambió
    if target.email:
        target.email = target.email.lower()
    
    # Recalcular completitud del perfil si cambió información relevante
    profile_fields = ['first_name', 'last_name', 'phone', 'bio', 'company', 'job_title']
    
    # Verificar si algún campo del perfil cambió
    session = db.session
    if session.is_modified(target):
        for field in profile_fields:
            if session.is_modified(target, field):
                target.calculate_profile_completion()
                break


@event.listens_for(User, 'after_insert')
def user_created_actions(mapper, connection, target):
    """Acciones después de crear usuario."""
    user_logger.info(f"New user created: {target.email} with role: {target.role}")
    
    # Programar envío de email de bienvenida
    @event.listens_for(db.session, 'after_commit', once=True)
    def send_welcome_email(session):
        try:
            if hasattr(target, 'send_notification'):
                target.send_notification('created')
        except Exception as e:
            user_logger.error(f"Error sending welcome email: {str(e)}")


# ====================================
# CONFIGURACIÓN FLASK-LOGIN
# ====================================

@login_manager.user_loader
def load_user(user_id):
    """Cargar usuario para Flask-Login."""
    try:
        return User.get_by_id(user_id)
    except Exception as e:
        user_logger.error(f"Error loading user {user_id}: {str(e)}")
        return None


@login_manager.unauthorized_handler
def unauthorized():
    """Manejar usuarios no autorizados."""
    from flask import request, jsonify, redirect, url_for, flash
    
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Authentication required'}), 401
    
    flash('Debes iniciar sesión para acceder a esta página.', 'warning')
    return redirect(url_for('auth.login'))


# ====================================
# UTILIDADES ADICIONALES
# ====================================

def get_user_stats() -> Dict[str, Any]:
    """Obtener estadísticas de usuarios."""
    try:
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        verified_users = User.query.filter_by(email_verified=True).count()
        
        # Usuarios por rol
        users_by_role = {}
        for role in VALID_ROLES:
            count = User.query.filter_by(role=role, is_active=True).count()
            users_by_role[role] = count
        
        # Usuarios recientes (últimos 30 días)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_users = User.query.filter(
            User.created_at >= thirty_days_ago,
            User.is_active == True
        ).count()
        
        # Usuarios en línea (últimos 15 minutos)
        fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
        online_users = User.query.filter(
            User.last_activity_at >= fifteen_minutes_ago,
            User.is_active == True
        ).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'verified_users': verified_users,
            'users_by_role': users_by_role,
            'recent_users': recent_users,
            'online_users': online_users,
            'verification_rate': round((verified_users / total_users * 100), 2) if total_users > 0 else 0
        }
        
    except Exception as e:
        user_logger.error(f"Error getting user stats: {str(e)}")
        return {}


def cleanup_unverified_users(days_old: int = 30) -> int:
    """
    Eliminar usuarios no verificados antiguos.
    
    Args:
        days_old: Días de antigüedad para considerar eliminación
        
    Returns:
        Número de usuarios eliminados
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Buscar usuarios no verificados antiguos
        unverified_users = User.query.filter(
            User.email_verified == False,
            User.created_at < cutoff_date,
            User.is_active == True
        ).all()
        
        deleted_count = 0
        for user in unverified_users:
            try:
                # Soft delete en lugar de eliminación física
                if hasattr(user, 'soft_delete'):
                    user.soft_delete()
                else:
                    user.is_active = False
                    db.session.commit()
                
                deleted_count += 1
                user_logger.info(f"Cleaned up unverified user: {user.email}")
                
            except Exception as e:
                user_logger.error(f"Error cleaning up user {user.email}: {str(e)}")
                db.session.rollback()
        
        user_logger.info(f"Cleaned up {deleted_count} unverified users")
        return deleted_count
        
    except Exception as e:
        user_logger.error(f"Error in cleanup_unverified_users: {str(e)}")
        return 0


def generate_user_report(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """
    Generar reporte de usuarios.
    
    Args:
        start_date: Fecha de inicio
        end_date: Fecha de fin
        
    Returns:
        Diccionario con datos del reporte
    """
    try:
        # Fechas por defecto (último mes)
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Consulta base
        base_query = User.query.filter(
            User.created_at >= start_date,
            User.created_at <= end_date
        )
        
        # Métricas básicas
        total_registrations = base_query.count()
        active_registrations = base_query.filter_by(is_active=True).count()
        verified_registrations = base_query.filter_by(email_verified=True).count()
        
        # Registros por día
        from sqlalchemy import func
        daily_registrations = db.session.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date,
            User.created_at <= end_date
        ).group_by(func.date(User.created_at)).all()
        
        # Registros por rol
        role_registrations = db.session.query(
            User.role,
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date,
            User.created_at <= end_date,
            User.is_active == True
        ).group_by(User.role).all()
        
        # Top ciudades
        top_cities = db.session.query(
            User.city,
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date,
            User.created_at <= end_date,
            User.city.isnot(None),
            User.is_active == True
        ).group_by(User.city).order_by(func.count(User.id).desc()).limit(10).all()
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'totals': {
                'registrations': total_registrations,
                'active': active_registrations,
                'verified': verified_registrations,
                'verification_rate': round((verified_registrations / total_registrations * 100), 2) if total_registrations > 0 else 0
            },
            'daily_registrations': [
                {'date': item.date.isoformat(), 'count': item.count}
                for item in daily_registrations
            ],
            'by_role': [
                {'role': item.role, 'count': item.count}
                for item in role_registrations
            ],
            'top_cities': [
                {'city': item.city, 'count': item.count}
                for item in top_cities
            ]
        }
        
    except Exception as e:
        user_logger.error(f"Error generating user report: {str(e)}")
        return {'error': str(e)}


# ====================================
# CONFIGURACIÓN DE VALIDACIÓN AVANZADA
# ====================================

# Configurar reglas de validación personalizadas (comentadas por compatibilidad)
# User.add_validation_rule('email', {
#     'type': 'regex',
#     'params': {'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'},
#     'message': 'Formato de email inválido'
# })

# User.add_validation_rule('first_name', {
#     'type': 'min_length',
#     'params': {'length': 2},
#     'message': 'El nombre debe tener al menos 2 caracteres'
# })

# User.add_validation_rule('last_name', {
#     'type': 'min_length', 
#     'params': {'length': 2},
#     'message': 'El apellido debe tener al menos 2 caracteres'
# })

# User.add_validation_rule('role', {
#     'type': 'in_choices',
#     'params': {'choices': VALID_ROLES},
#     'message': 'Rol inválido'
# })


# ====================================
# MÉTODOS DE NOTIFICACIÓN PERSONALIZADOS
# ====================================

def _get_default_recipients(self, event_type: str) -> List[str]:
    """Obtener destinatarios por defecto según el evento."""
    if event_type == 'created':
        return [self.email]
    elif event_type in ['password_changed', 'login_from_new_device']:
        return [self.email]
    elif event_type == 'profile_updated':
        # Solo si el usuario tiene habilitadas las notificaciones
        return [self.email] if self.email_notifications else []
    
    return []

# Monkey patch para añadir el método a la clase User
User._get_default_recipients = _get_default_recipients


# ====================================
# FUNCIONES DE MIGRACIÓN Y MANTENIMIENTO
# ====================================

def migrate_user_data(migration_type: str) -> bool:
    """
    Ejecutar migraciones de datos de usuarios.
    
    Args:
        migration_type: Tipo de migración a ejecutar
        
    Returns:
        True si la migración fue exitosa
    """
    try:
        if migration_type == 'normalize_emails':
            # Normalizar todos los emails existentes
            users = User.query.all()
            for user in users:
                if user.email:
                    user.email = user.email.lower().strip()
            
            db.session.commit()
            user_logger.info(f"Normalized emails for {len(users)} users")
            
        elif migration_type == 'calculate_profile_completion':
            # Recalcular completitud de perfiles
            users = User.query.all()
            for user in users:
                user.calculate_profile_completion()
            
            db.session.commit()
            user_logger.info(f"Recalculated profile completion for {len(users)} users")
            
        elif migration_type == 'set_default_preferences':
            # Establecer preferencias por defecto
            users = User.query.filter_by(timezone=None).all()
            for user in users:
                user.timezone = 'America/Bogota'
                user.language = 'es'
                user.theme = 'light'
            
            db.session.commit()
            user_logger.info(f"Set default preferences for {len(users)} users")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        user_logger.error(f"Error in user data migration {migration_type}: {str(e)}")
        return False


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    'User',
    'get_user_stats',
    'cleanup_unverified_users', 
    'generate_user_report',
    'migrate_user_data'
]