"""
Authentication Forms

Formularios de autenticación para el ecosistema de emprendimiento.
Incluye login, registro, recuperación de contraseña y verificación 2FA.

Author: jusga
Date: 2025
"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from flask import current_app, request, session, g, flash
from flask_wtf import FlaskForm, RecaptchaField
from wtforms import (
    StringField, PasswordField, EmailField, BooleanField, 
    SelectField, HiddenField, SubmitField, TelField,
    TextAreaField, DateField, RadioField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional as WTFOptional,
    Regexp, ValidationError
)
from wtforms.widgets import PasswordInput, TextInput
import pyotp
import qrcode
from io import BytesIO
import base64

from app.forms.base import BaseForm, AuditMixin
from app.forms.validators import (
    SecurePassword, InternationalPhone, UniqueEmail, UniqueUsername,
    ColombianNIT, BusinessEmail, BaseValidator
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.admin import Admin
from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager
from app.services.email import EmailService


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES ESPECÍFICOS DE AUTENTICACIÓN
# =============================================================================

class LoginRateLimit(BaseValidator):
    """Validador de rate limiting específico para login"""
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15,
                 lockout_minutes: int = 30, message: str = None):
        super().__init__(message)
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.lockout_minutes = lockout_minutes
    
    def validate(self, form, field):
        if not field.data:
            return
        
        identifier = field.data.lower()
        client_ip = self._get_client_ip()
        
        # Verificar intentos por email/username
        email_key = f"login_attempts_email_{identifier}"
        email_attempts = self.cache.get(email_key) or []
        
        # Verificar intentos por IP
        ip_key = f"login_attempts_ip_{client_ip}"
        ip_attempts = self.cache.get(ip_key) or []
        
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        # Filtrar intentos recientes
        recent_email_attempts = [
            attempt for attempt in email_attempts 
            if datetime.fromisoformat(attempt) > window_start
        ]
        recent_ip_attempts = [
            attempt for attempt in ip_attempts 
            if datetime.fromisoformat(attempt) > window_start
        ]
        
        # Verificar límites
        if len(recent_email_attempts) >= self.max_attempts:
            raise ValidationError(
                f'Demasiados intentos para esta cuenta. '
                f'Intente en {self.lockout_minutes} minutos.'
            )
        
        if len(recent_ip_attempts) >= self.max_attempts * 3:  # Límite más alto por IP
            raise ValidationError(
                f'Demasiados intentos desde esta ubicación. '
                f'Intente en {self.lockout_minutes} minutos.'
            )
    
    def record_attempt(self, identifier: str, success: bool = False):
        """Registra intento de login"""
        identifier = identifier.lower()
        client_ip = self._get_client_ip()
        now = datetime.utcnow()
        
        if not success:
            # Registrar intento fallido
            email_key = f"login_attempts_email_{identifier}"
            ip_key = f"login_attempts_ip_{client_ip}"
            
            email_attempts = self.cache.get(email_key) or []
            ip_attempts = self.cache.get(ip_key) or []
            
            email_attempts.append(now.isoformat())
            ip_attempts.append(now.isoformat())
            
            # Mantener solo intentos recientes
            window_start = now - timedelta(minutes=self.window_minutes * 2)
            email_attempts = [
                attempt for attempt in email_attempts 
                if datetime.fromisoformat(attempt) > window_start
            ]
            ip_attempts = [
                attempt for attempt in ip_attempts 
                if datetime.fromisoformat(attempt) > window_start
            ]
            
            # Guardar en cache
            self.cache.set(email_key, email_attempts, timeout=self.lockout_minutes * 60)
            self.cache.set(ip_key, ip_attempts, timeout=self.lockout_minutes * 60)
        else:
            # Limpiar intentos exitosos
            email_key = f"login_attempts_email_{identifier}"
            self.cache.delete(email_key)
    
    def _get_client_ip(self) -> str:
        """Obtiene IP del cliente"""
        if request:
            forwarded_for = request.headers.get('X-Forwarded-For')
            if forwarded_for:
                return forwarded_for.split(',')[0].strip()
            return request.remote_addr or '127.0.0.1'
        return '127.0.0.1'


class PasswordHistory(BaseValidator):
    """Validador para prevenir reutilización de contraseñas"""
    
    def __init__(self, user_field: str = 'email', history_count: int = 5,
                 message: str = None):
        super().__init__(message)
        self.user_field = user_field
        self.history_count = history_count
    
    def validate(self, form, field):
        if not field.data:
            return
        
        user_field = getattr(form, self.user_field, None)
        if not user_field or not user_field.data:
            return
        
        # Buscar usuario
        user = User.query.filter(
            (User.email == user_field.data) | 
            (User.username == user_field.data)
        ).first()
        
        if not user:
            return
        
        # Verificar historial de contraseñas
        if hasattr(user, 'password_history') and user.password_history:
            from werkzeug.security import check_password_hash
            
            for old_password_hash in user.password_history[-self.history_count:]:
                if check_password_hash(old_password_hash, field.data):
                    raise ValidationError(
                        self.message or 
                        f'No puede reutilizar las últimas {self.history_count} contraseñas'
                    )


class TwoFactorCode(BaseValidator):
    """Validador para códigos de autenticación de dos factores"""
    
    def __init__(self, user_field: str = 'email', message: str = None):
        super().__init__(message)
        self.user_field = user_field
    
    def validate(self, form, field):
        if not field.data:
            return
        
        code = field.data.replace(' ', '').replace('-', '')
        
        # Verificar formato del código
        if not code.isdigit() or len(code) != 6:
            raise ValidationError('Código debe tener 6 dígitos')
        
        user_field = getattr(form, self.user_field, None)
        if not user_field or not user_field.data:
            return
        
        # Buscar usuario
        user = User.query.filter(
            (User.email == user_field.data) | 
            (User.username == user_field.data)
        ).first()
        
        if not user or not user.two_factor_secret:
            raise ValidationError('Usuario no configurado para 2FA')
        
        # Verificar código TOTP
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code, valid_window=1):  # Ventana de 30 segundos
            raise ValidationError('Código de autenticación inválido')


class UserExists(BaseValidator):
    """Validador para verificar que un usuario existe"""
    
    def __init__(self, field: str = 'email', message: str = None):
        super().__init__(message)
        self.field = field
    
    def validate(self, form, field):
        if not field.data:
            return
        
        if self.field == 'email':
            user = User.query.filter(User.email == field.data).first()
        elif self.field == 'username':
            user = User.query.filter(User.username == field.data).first()
        else:
            user = User.query.filter(
                (User.email == field.data) | 
                (User.username == field.data)
            ).first()
        
        if not user:
            raise ValidationError(
                self.message or 'Usuario no encontrado'
            )


# =============================================================================
# WIDGETS PERSONALIZADOS
# =============================================================================

class PasswordStrengthInput(PasswordInput):
    """Widget de contraseña con indicador de fortaleza"""
    
    def __call__(self, field, **kwargs):
        kwargs.setdefault('data-password-strength', 'true')
        kwargs.setdefault('autocomplete', 'new-password')
        return super().__call__(field, **kwargs)


class TOTPInput(TextInput):
    """Widget para códigos TOTP"""
    
    def __call__(self, field, **kwargs):
        kwargs.setdefault('maxlength', '6')
        kwargs.setdefault('pattern', '[0-9]*')
        kwargs.setdefault('inputmode', 'numeric')
        kwargs.setdefault('autocomplete', 'one-time-code')
        kwargs.setdefault('data-totp', 'true')
        return super().__call__(field, **kwargs)


# =============================================================================
# FORMULARIOS DE AUTENTICACIÓN BÁSICOS
# =============================================================================

class LoginForm(BaseForm, AuditMixin):
    """Formulario de inicio de sesión"""
    
    # Campos principales
    email_or_username = StringField(
        'Email o Usuario',
        validators=[
            DataRequired(message='Email o nombre de usuario requerido'),
            Length(min=3, max=255),
            LoginRateLimit()
        ],
        render_kw={
            'placeholder': 'email@ejemplo.com o usuario',
            'autocomplete': 'username',
            'autofocus': True
        }
    )
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='Contraseña requerida'),
            Length(min=1, max=128)
        ],
        render_kw={
            'placeholder': 'Su contraseña',
            'autocomplete': 'current-password'
        }
    )
    
    remember_me = BooleanField(
        'Recordarme',
        default=False,
        render_kw={'title': 'Mantener sesión iniciada'}
    )
    
    # Campo oculto para capturar timezone del cliente
    timezone = HiddenField('Timezone')
    
    # Botón de envío
    submit = SubmitField('Iniciar Sesión')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.rate_limiter = LoginRateLimit()
    
    def validate(self, **kwargs):
        """Validación personalizada con autenticación"""
        valid = super().validate(**kwargs)
        
        if not valid:
            return False
        
        # Buscar usuario
        identifier = self.email_or_username.data.strip()
        self.user = User.query.filter(
            (User.email == identifier) | 
            (User.username == identifier)
        ).first()
        
        if not self.user:
            self.email_or_username.errors.append('Usuario no encontrado')
            self.rate_limiter.record_attempt(identifier, success=False)
            return False
        
        # Verificar si el usuario está activo
        if not self.user.is_active:
            self.email_or_username.errors.append('Cuenta desactivada')
            return False
        
        # Verificar contraseña
        if not self.user.check_password(self.password.data):
            self.password.errors.append('Contraseña incorrecta')
            self.rate_limiter.record_attempt(identifier, success=False)
            return False
        
        # Verificar si requiere verificación de email
        if not self.user.email_verified:
            self.email_or_username.errors.append(
                'Debe verificar su email antes de iniciar sesión'
            )
            return False
        
        # Login exitoso
        self.rate_limiter.record_attempt(identifier, success=True)
        
        # Actualizar último login
        self.user.last_login = datetime.utcnow()
        self.user.login_count = (self.user.login_count or 0) + 1
        
        # Actualizar timezone si se proporcionó
        if self.timezone.data:
            self.user.timezone = self.timezone.data
        
        return True
    
    def get_user(self) -> Optional[User]:
        """Retorna el usuario autenticado"""
        return self.user


class RegisterForm(BaseForm, AuditMixin):
    """Formulario de registro de usuario"""
    
    # Información básica
    user_type = RadioField(
        'Tipo de Usuario',
        choices=[
            ('entrepreneur', 'Emprendedor'),
            ('ally', 'Mentor/Aliado'),
            ('client', 'Cliente/Stakeholder')
        ],
        validators=[DataRequired(message='Seleccione tipo de usuario')],
        default='entrepreneur'
    )
    
    first_name = StringField(
        'Nombre',
        validators=[
            DataRequired(message='Nombre requerido'),
            Length(min=2, max=50, message='Nombre debe tener entre 2 y 50 caracteres'),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='Solo letras y espacios')
        ],
        render_kw={'placeholder': 'Su nombre'}
    )
    
    last_name = StringField(
        'Apellido',
        validators=[
            DataRequired(message='Apellido requerido'),
            Length(min=2, max=50, message='Apellido debe tener entre 2 y 50 caracteres'),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='Solo letras y espacios')
        ],
        render_kw={'placeholder': 'Su apellido'}
    )
    
    # Credenciales
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email requerido'),
            Email(message='Email inválido'),
            UniqueEmail(message='Este email ya está registrado')
        ],
        render_kw={
            'placeholder': 'email@ejemplo.com',
            'autocomplete': 'email'
        }
    )
    
    username = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(message='Nombre de usuario requerido'),
            Length(min=3, max=30, message='Entre 3 y 30 caracteres'),
            Regexp(r'^[a-zA-Z0-9_.-]+$', message='Solo letras, números, guión, punto y guión bajo'),
            UniqueUsername(message='Nombre de usuario no disponible')
        ],
        render_kw={
            'placeholder': 'usuario_unico',
            'autocomplete': 'username'
        }
    )
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='Contraseña requerida'),
            SecurePassword(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            )
        ],
        widget=PasswordStrengthInput(),
        render_kw={
            'placeholder': 'Mínimo 8 caracteres',
            'autocomplete': 'new-password'
        }
    )
    
    confirm_password = PasswordField(
        'Confirmar Contraseña',
        validators=[
            DataRequired(message='Confirmación de contraseña requerida'),
            EqualTo('password', message='Las contraseñas no coinciden')
        ],
        render_kw={
            'placeholder': 'Repita su contraseña',
            'autocomplete': 'new-password'
        }
    )
    
    # Información de contacto
    phone = TelField(
        'Teléfono',
        validators=[
            DataRequired(message='Teléfono requerido'),
            InternationalPhone(regions=['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL'])
        ],
        render_kw={'placeholder': '+57 300 123 4567'}
    )
    
    # Campos específicos por tipo de usuario
    organization = StringField(
        'Organización',
        validators=[
            Length(max=100, message='Máximo 100 caracteres')
        ],
        render_kw={'placeholder': 'Empresa u organización'}
    )
    
    # Campos opcionales adicionales
    linkedin_url = StringField(
        'LinkedIn',
        validators=[
            WTFOptional(),
            Length(max=255),
            Regexp(
                r'^https?://(www\.)?linkedin\.com/in/[a-zA-Z0-9-]+/?$',
                message='URL de LinkedIn inválida'
            )
        ],
        render_kw={'placeholder': 'https://linkedin.com/in/usuario'}
    )
    
    # Términos y condiciones
    accept_terms = BooleanField(
        'Acepto los términos y condiciones',
        validators=[
            DataRequired(message='Debe aceptar los términos y condiciones')
        ]
    )
    
    accept_privacy = BooleanField(
        'Acepto la política de privacidad',
        validators=[
            DataRequired(message='Debe aceptar la política de privacidad')
        ]
    )
    
    # Marketing
    accept_marketing = BooleanField(
        'Acepto recibir comunicaciones de marketing',
        default=False
    )
    
    # reCAPTCHA (si está configurado) - se inicializará en __init__ cuando haya contexto
    recaptcha = None
    
    # Campos ocultos
    timezone = HiddenField('Timezone')
    referral_code = HiddenField('Código de Referido')
    
    submit = SubmitField('Crear Cuenta')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar campos dinámicos según disponibilidad
        try:
            from flask import has_app_context
            if has_app_context() and current_app.config.get('RECAPTCHA_PUBLIC_KEY'):
                from flask_wtf import RecaptchaField
                self.recaptcha = RecaptchaField()
            elif hasattr(self, 'recaptcha'):
                delattr(self, 'recaptcha')
        except Exception:
            # Si hay algún problema, simplemente no incluir recaptcha
            if hasattr(self, 'recaptcha'):
                delattr(self, 'recaptcha')
    
    def validate_linkedin_url(self, field):
        """Validación adicional para LinkedIn"""
        if field.data:
            # Verificar que no esté ya registrado
            existing = User.query.filter(User.linkedin_url == field.data).first()
            if existing:
                raise ValidationError('Esta URL de LinkedIn ya está registrada')
    
    def save_user(self) -> User:
        """Crea y guarda el nuevo usuario"""
        from app.extensions import db
        
        try:
            # Crear usuario base
            user = User(
                email=self.email.data,
                username=self.username.data,
                first_name=self.first_name.data,
                last_name=self.last_name.data,
                phone=self.phone.data,
                user_type=self.user_type.data,
                organization=self.organization.data,
                linkedin_url=self.linkedin_url.data,
                timezone=self.timezone.data or 'America/Bogota',
                accept_marketing=self.accept_marketing.data,
                email_verified=False,
                is_active=True
            )
            
            # Establecer contraseña
            user.set_password(self.password.data)
            
            # Generar token de verificación de email
            user.email_verification_token = secrets.token_urlsafe(32)
            user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
            
            # Procesar código de referido si existe
            if self.referral_code.data:
                referrer = User.query.filter(
                    User.referral_code == self.referral_code.data
                ).first()
                if referrer:
                    user.referred_by = referrer.id
            
            db.session.add(user)
            db.session.flush()  # Para obtener el ID
            
            # Crear perfil específico según tipo de usuario
            if self.user_type.data == 'entrepreneur':
                entrepreneur = Entrepreneur(user_id=user.id)
                db.session.add(entrepreneur)
            elif self.user_type.data == 'ally':
                ally = Ally(user_id=user.id)
                db.session.add(ally)
            
            db.session.commit()
            
            # Enviar email de verificación
            self._send_verification_email(user)
            
            logger.info(f"New user registered: {user.email} ({user.user_type})")
            return user
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating user: {e}")
            raise
    
    def _send_verification_email(self, user: User):
        """Envía email de verificación"""
        try:
            email_service = EmailService()
            
            verification_url = url_for(
                'auth.verify_email',
                token=user.email_verification_token,
                _external=True
            )
            
            email_service.send_verification_email(
                to_email=user.email,
                user_name=user.first_name,
                verification_url=verification_url
            )
            
        except Exception as e:
            logger.error(f"Error sending verification email: {e}")


class ForgotPasswordForm(BaseForm):
    """Formulario para recuperación de contraseña"""
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email requerido'),
            Email(message='Email inválido'),
            UserExists(field='email', message='Email no encontrado')
        ],
        render_kw={
            'placeholder': 'email@ejemplo.com',
            'autocomplete': 'email',
            'autofocus': True
        }
    )
    
    submit = SubmitField('Enviar Instrucciones')
    
    def send_reset_email(self):
        """Envía email de recuperación de contraseña"""
        user = User.query.filter(User.email == self.email.data).first()
        if not user:
            return False
        
        try:
            # Generar token de reset
            user.password_reset_token = secrets.token_urlsafe(32)
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
            
            from app.extensions import db
            db.session.commit()
            
            # Enviar email
            email_service = EmailService()
            
            reset_url = url_for(
                'auth.reset_password',
                token=user.password_reset_token,
                _external=True
            )
            
            email_service.send_password_reset_email(
                to_email=user.email,
                user_name=user.first_name,
                reset_url=reset_url
            )
            
            logger.info(f"Password reset email sent to: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {e}")
            return False


class ResetPasswordForm(BaseForm):
    """Formulario para restablecer contraseña"""
    
    token = HiddenField('Token', validators=[DataRequired()])
    
    password = PasswordField(
        'Nueva Contraseña',
        validators=[
            DataRequired(message='Contraseña requerida'),
            SecurePassword(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            ),
            PasswordHistory(user_field='email')
        ],
        widget=PasswordStrengthInput(),
        render_kw={
            'placeholder': 'Nueva contraseña segura',
            'autocomplete': 'new-password'
        }
    )
    
    confirm_password = PasswordField(
        'Confirmar Contraseña',
        validators=[
            DataRequired(message='Confirmación requerida'),
            EqualTo('password', message='Las contraseñas no coinciden')
        ],
        render_kw={
            'placeholder': 'Repita la nueva contraseña',
            'autocomplete': 'new-password'
        }
    )
    
    submit = SubmitField('Restablecer Contraseña')
    
    def __init__(self, token=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if token:
            self.token.data = token
        self.user = None
    
    def validate_token(self, field):
        """Valida el token de reset"""
        if not field.data:
            raise ValidationError('Token requerido')
        
        self.user = User.query.filter(
            User.password_reset_token == field.data,
            User.password_reset_expires > datetime.utcnow()
        ).first()
        
        if not self.user:
            raise ValidationError('Token inválido o expirado')
    
    def reset_password(self) -> bool:
        """Restablece la contraseña del usuario"""
        if not self.user:
            return False
        
        try:
            from app.extensions import db
            
            # Guardar contraseña anterior en historial
            if not self.user.password_history:
                self.user.password_history = []
            
            self.user.password_history.append(self.user.password_hash)
            
            # Mantener solo las últimas 5 contraseñas
            if len(self.user.password_history) > 5:
                self.user.password_history = self.user.password_history[-5:]
            
            # Establecer nueva contraseña
            self.user.set_password(self.password.data)
            
            # Limpiar tokens de reset
            self.user.password_reset_token = None
            self.user.password_reset_expires = None
            
            # Actualizar timestamp de cambio de contraseña
            self.user.password_changed_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Password reset completed for user: {self.user.email}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resetting password: {e}")
            return False


# =============================================================================
# FORMULARIOS DE AUTENTICACIÓN AVANZADOS
# =============================================================================

class ChangePasswordForm(BaseForm):
    """Formulario para cambio de contraseña (usuario autenticado)"""
    
    current_password = PasswordField(
        'Contraseña Actual',
        validators=[
            DataRequired(message='Contraseña actual requerida')
        ],
        render_kw={
            'placeholder': 'Su contraseña actual',
            'autocomplete': 'current-password'
        }
    )
    
    new_password = PasswordField(
        'Nueva Contraseña',
        validators=[
            DataRequired(message='Nueva contraseña requerida'),
            SecurePassword(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            )
        ],
        widget=PasswordStrengthInput(),
        render_kw={
            'placeholder': 'Nueva contraseña segura',
            'autocomplete': 'new-password'
        }
    )
    
    confirm_password = PasswordField(
        'Confirmar Nueva Contraseña',
        validators=[
            DataRequired(message='Confirmación requerida'),
            EqualTo('new_password', message='Las contraseñas no coinciden')
        ],
        render_kw={
            'placeholder': 'Repita la nueva contraseña',
            'autocomplete': 'new-password'
        }
    )
    
    logout_all_devices = BooleanField(
        'Cerrar sesión en todos los dispositivos',
        default=True,
        render_kw={'title': 'Recomendado por seguridad'}
    )
    
    submit = SubmitField('Cambiar Contraseña')
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user or g.current_user
    
    def validate_current_password(self, field):
        """Valida la contraseña actual"""
        if not self.user.check_password(field.data):
            raise ValidationError('Contraseña actual incorrecta')
    
    def validate_new_password(self, field):
        """Valida que la nueva contraseña sea diferente"""
        if self.user.check_password(field.data):
            raise ValidationError('La nueva contraseña debe ser diferente a la actual')
        
        # Verificar historial de contraseñas
        if hasattr(self.user, 'password_history') and self.user.password_history:
            from werkzeug.security import check_password_hash
            
            for old_password_hash in self.user.password_history[-5:]:
                if check_password_hash(old_password_hash, field.data):
                    raise ValidationError('No puede reutilizar contraseñas recientes')
    
    def change_password(self) -> bool:
        """Cambia la contraseña del usuario"""
        try:
            from app.extensions import db
            
            # Guardar contraseña actual en historial
            if not self.user.password_history:
                self.user.password_history = []
            
            self.user.password_history.append(self.user.password_hash)
            
            # Mantener solo las últimas 5 contraseñas
            if len(self.user.password_history) > 5:
                self.user.password_history = self.user.password_history[-5:]
            
            # Establecer nueva contraseña
            self.user.set_password(self.new_password.data)
            self.user.password_changed_at = datetime.utcnow()
            
            # Invalidar sesiones si se solicitó
            if self.logout_all_devices.data:
                self.user.session_token = secrets.token_urlsafe(32)
            
            db.session.commit()
            
            logger.info(f"Password changed for user: {self.user.email}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error changing password: {e}")
            return False


class TwoFactorSetupForm(BaseForm):
    """Formulario para configurar autenticación de dos factores"""
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='Contraseña requerida para configurar 2FA')
        ],
        render_kw={
            'placeholder': 'Su contraseña actual',
            'autocomplete': 'current-password'
        }
    )
    
    submit = SubmitField('Generar Código QR')
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user or g.current_user
        self.secret = None
        self.qr_code = None
    
    def validate_password(self, field):
        """Valida la contraseña del usuario"""
        if not self.user.check_password(field.data):
            raise ValidationError('Contraseña incorrecta')
    
    def generate_secret(self) -> str:
        """Genera secreto para 2FA"""
        self.secret = pyotp.random_base32()
        return self.secret
    
    def get_qr_code(self) -> str:
        """Genera código QR para configurar 2FA"""
        if not self.secret:
            self.generate_secret()
        
        # Crear URI para el authenticator
        totp = pyotp.TOTP(self.secret)
        provisioning_uri = totp.provisioning_uri(
            name=self.user.email,
            issuer_name=current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento')
        )
        
        # Generar código QR
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        qr_code = base64.b64encode(buffer.getvalue()).decode()
        self.qr_code = f"data:image/png;base64,{qr_code}"
        
        return self.qr_code


class TwoFactorVerifyForm(BaseForm):
    """Formulario para verificar configuración de 2FA"""
    
    secret = HiddenField('Secret', validators=[DataRequired()])
    
    code = StringField(
        'Código de Verificación',
        validators=[
            DataRequired(message='Código de verificación requerido'),
            Length(min=6, max=6, message='El código debe tener 6 dígitos')
        ],
        widget=TOTPInput(),
        render_kw={
            'placeholder': '123456',
            'maxlength': '6',
            'autocomplete': 'one-time-code',
            'autofocus': True
        }
    )
    
    submit = SubmitField('Verificar y Activar 2FA')
    
    def __init__(self, secret=None, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if secret:
            self.secret.data = secret
        self.user = user or g.current_user
    
    def validate_code(self, field):
        """Valida el código TOTP"""
        if not self.secret.data:
            raise ValidationError('Secreto requerido')
        
        code = field.data.replace(' ', '').replace('-', '')
        
        totp = pyotp.TOTP(self.secret.data)
        if not totp.verify(code, valid_window=1):
            raise ValidationError('Código inválido')
    
    def enable_2fa(self) -> bool:
        """Activa 2FA para el usuario"""
        try:
            from app.extensions import db
            
            self.user.two_factor_secret = self.secret.data
            self.user.two_factor_enabled = True
            self.user.two_factor_enabled_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"2FA enabled for user: {self.user.email}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error enabling 2FA: {e}")
            return False


class TwoFactorForm(BaseForm):
    """Formulario para login con 2FA"""
    
    email_or_username = HiddenField('User', validators=[DataRequired()])
    
    code = StringField(
        'Código de Autenticación',
        validators=[
            DataRequired(message='Código requerido'),
            TwoFactorCode(user_field='email_or_username')
        ],
        widget=TOTPInput(),
        render_kw={
            'placeholder': '123456',
            'autocomplete': 'one-time-code',
            'autofocus': True
        }
    )
    
    trust_device = BooleanField(
        'Confiar en este dispositivo por 30 días',
        default=False
    )
    
    submit = SubmitField('Verificar')
    
    def __init__(self, user_identifier=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user_identifier:
            self.email_or_username.data = user_identifier
        self.user = None
    
    def validate(self, **kwargs):
        """Validación con búsqueda de usuario"""
        valid = super().validate(**kwargs)
        
        if valid:
            identifier = self.email_or_username.data
            self.user = User.query.filter(
                (User.email == identifier) | 
                (User.username == identifier)
            ).first()
        
        return valid
    
    def get_user(self) -> Optional[User]:
        """Retorna el usuario autenticado"""
        return self.user


class EmailVerificationForm(BaseForm):
    """Formulario para verificación de email"""
    
    token = HiddenField('Token', validators=[DataRequired()])
    
    submit = SubmitField('Verificar Email')
    
    def __init__(self, token=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if token:
            self.token.data = token
        self.user = None
    
    def validate_token(self, field):
        """Valida el token de verificación"""
        self.user = User.query.filter(
            User.email_verification_token == field.data,
            User.email_verification_expires > datetime.utcnow()
        ).first()
        
        if not self.user:
            raise ValidationError('Token de verificación inválido o expirado')
    
    def verify_email(self) -> bool:
        """Verifica el email del usuario"""
        if not self.user:
            return False
        
        try:
            from app.extensions import db
            
            self.user.email_verified = True
            self.user.email_verified_at = datetime.utcnow()
            self.user.email_verification_token = None
            self.user.email_verification_expires = None
            
            db.session.commit()
            
            logger.info(f"Email verified for user: {self.user.email}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error verifying email: {e}")
            return False


class ResendVerificationForm(BaseForm):
    """Formulario para reenviar verificación de email"""
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email requerido'),
            Email(message='Email inválido')
        ],
        render_kw={
            'placeholder': 'email@ejemplo.com',
            'autocomplete': 'email'
        }
    )
    
    submit = SubmitField('Reenviar Verificación')
    
    def send_verification(self) -> bool:
        """Reenvía email de verificación"""
        user = User.query.filter(
            User.email == self.email.data,
            User.email_verified == False
        ).first()
        
        if not user:
            # No revelar si el email existe o no por seguridad
            return True
        
        try:
            from app.extensions import db
            
            # Generar nuevo token
            user.email_verification_token = secrets.token_urlsafe(32)
            user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
            
            db.session.commit()
            
            # Enviar email
            email_service = EmailService()
            
            verification_url = url_for(
                'auth.verify_email',
                token=user.email_verification_token,
                _external=True
            )
            
            email_service.send_verification_email(
                to_email=user.email,
                user_name=user.first_name,
                verification_url=verification_url
            )
            
            logger.info(f"Verification email resent to: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error resending verification email: {e}")
            return False


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Formularios básicos
    'LoginForm',
    'RegisterForm', 
    'ForgotPasswordForm',
    'ResetPasswordForm',
    
    # Formularios avanzados
    'ChangePasswordForm',
    'TwoFactorSetupForm',
    'TwoFactorVerifyForm',
    'TwoFactorForm',
    'EmailVerificationForm',
    'ResendVerificationForm',
    
    # Validadores
    'LoginRateLimit',
    'PasswordHistory',
    'TwoFactorCode',
    'UserExists',
    
    # Widgets
    'PasswordStrengthInput',
    'TOTPInput'
]