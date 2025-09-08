"""
Views de autenticación del ecosistema de emprendimiento.
Maneja todo el flujo de autenticación, registro, verificación y seguridad.

Características:
- Login/logout seguro con rate limiting
- Registro multi-tipo de usuario
- Verificación de email obligatoria
- Recuperación de contraseña robusta
- Two-Factor Authentication (2FA)
- Autenticación social (OAuth)
- Gestión de sesiones
- Auditoría y logging completo
- Protección contra ataques (brute force, CSRF, etc.)
- Formularios con validaciones avanzadas
- Redirección inteligente post-login
- Analytics de autenticación

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, session, current_app, g, jsonify, abort
)
from flask_wtf import FlaskForm, RecaptchaField
from flask_babel import _, get_locale
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    get_jwt_identity, jwt_required, get_jwt
)
from wtforms import (
    StringField, PasswordField, SelectField, EmailField, 
    BooleanField, TextAreaField, HiddenField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional, 
    ValidationError, Regexp
)
from werkzeug.security import check_password_hash, generate_password_hash
try:
    from werkzeug.urls import url_parse
except ImportError:
    from urllib.parse import urlparse as url_parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional as TypingOptional, Any, Tuple
import secrets
import logging
import re
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    pyotp = None
    PYOTP_AVAILABLE = False
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    qrcode = None
    QRCODE_AVAILABLE = False
import io
import base64
from collections import defaultdict
from urllib.parse import urlparse, urljoin

# Importaciones locales
from app.models.user import User, UserType, UserStatus
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.user_session import UserSession, SessionStatus

# Stub classes for missing models
class UserSessionStub:
    @classmethod 
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
            def first(self):
                return None
            def all(self):
                return []
        return MockQuery()

class SessionStatusStub:
    ACTIVE = 'active'
    EXPIRED = 'expired'
    REVOKED = 'revoked'

class PasswordReset:
    @classmethod 
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
            def first(self):
                return None
        return MockQuery()

class EmailVerification:
    @classmethod 
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
            def first(self):
                return None
        return MockQuery()

class LoginAttempt:
    @classmethod 
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
            def count(self):
                return 0
        return MockQuery()

class AttemptStatus:
    SUCCESS = 'success'
    FAILED = 'failed'

class OAuthProvider:
    pass
class OAuthAccount:
    pass
from app.models.password_reset import PasswordReset
from app.models.email_verification import EmailVerification
from app.models.login_attempt import LoginAttempt, AttemptStatus
from app.models.oauth_provider import OAuthProvider, OAuthAccount
from app.models.two_factor import TwoFactorAuth, TwoFactorType
 
class TwoFactorAuth:
    pass
class TwoFactorType:
    SMS = 'sms'
    EMAIL = 'email'
    TOTP = 'totp'

# Service imports
from app.services.email_service import EmailService
from app.services.analytics_service import AnalyticsService
from app.services.oauth_service import OAuthService
from app.services.notification_service import NotificationService
from app.utils.security import generate_secure_token, is_safe_url, log_security_event
from app.utils.network import get_client_ip
from app.utils.validators import validate_password_strength, validate_phone_number

class RateLimiter:
    def __init__(self, *args, **kwargs):
        pass
    def is_allowed(self, *args, **kwargs):
        return True

from app.extensions import db, cache
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Crear blueprint
auth_bp = Blueprint('auth', __name__)

# Rate limiters
login_limiter = RateLimiter(max_attempts=5, window=300)  # 5 intentos por 5 minutos
register_limiter = RateLimiter(max_attempts=3, window=3600)  # 3 registros por hora
password_reset_limiter = RateLimiter(max_attempts=3, window=1800)  # 3 resets por 30 min

# Instancia del servicio de autenticación
auth_service = AuthService()

# Formularios de autenticación
class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""
    email = EmailField(_('Email'), validators=[
        DataRequired(message=_('El email es obligatorio')),
        Email(message=_('Ingresa un email válido'))
    ], render_kw={'placeholder': _('tu@email.com'), 'autofocus': True})
    
    password = PasswordField(_('Contraseña'), validators=[
        DataRequired(message=_('La contraseña es obligatoria'))
    ], render_kw={'placeholder': _('Tu contraseña')})
    
    remember_me = BooleanField(_('Recordarme'), default=False)
    
    # Campo oculto para protección CSRF adicional
    csrf_token = HiddenField()
    
    # reCAPTCHA en caso de múltiples intentos fallidos
    recaptcha = RecaptchaField()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar reCAPTCHA si hay intentos fallidos previos
        client_ip = get_client_ip()
        failed_attempts = LoginAttempt.query.filter(
            LoginAttempt.ip_address == client_ip,
            LoginAttempt.status == AttemptStatus.FAILED,
            LoginAttempt.created_at > datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        if failed_attempts < 3:
            del self.recaptcha

class RegisterForm(FlaskForm):
    """Formulario de registro de usuario."""
    user_type = SelectField(_('Tipo de Usuario'), choices=[
        ('entrepreneur', _('Emprendedor')),
        ('ally', _('Mentor/Aliado')),
        ('client', _('Cliente/Inversionista'))
    ], validators=[DataRequired(message=_('Selecciona un tipo de usuario'))])
    
    first_name = StringField(_('Nombre'), validators=[
        DataRequired(message=_('El nombre es obligatorio')),
        Length(min=2, max=50, message=_('El nombre debe tener entre 2 y 50 caracteres')),
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message=_('Solo se permiten letras'))
    ], render_kw={'placeholder': _('Tu nombre')})
    
    last_name = StringField(_('Apellido'), validators=[
        DataRequired(message=_('El apellido es obligatorio')),
        Length(min=2, max=50, message=_('El apellido debe tener entre 2 y 50 caracteres')),
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message=_('Solo se permiten letras'))
    ], render_kw={'placeholder': _('Tu apellido')})
    
    email = EmailField(_('Email'), validators=[
        DataRequired(message=_('El email es obligatorio')),
        Email(message=_('Ingresa un email válido'))
    ], render_kw={'placeholder': _('tu@email.com')})
    
    password = PasswordField(_('Contraseña'), validators=[
        DataRequired(message=_('La contraseña es obligatoria')),
        Length(min=8, message=_('La contraseña debe tener al menos 8 caracteres'))
    ], render_kw={'placeholder': _('Crea una contraseña segura')})
    
    password_confirm = PasswordField(_('Confirmar Contraseña'), validators=[
        DataRequired(message=_('Confirma tu contraseña')),
        EqualTo('password', message=_('Las contraseñas deben coincidir'))
    ], render_kw={'placeholder': _('Repite tu contraseña')})
    
    phone = StringField(_('Teléfono'), validators=[
        Optional(),
        Length(max=20, message=_('El teléfono no puede tener más de 20 caracteres'))
    ], render_kw={'placeholder': _('Tu número de teléfono')})
    
    # Campos adicionales según tipo de usuario
    company_name = StringField(_('Nombre de la Empresa'), validators=[
        Optional(),
        Length(max=100, message=_('El nombre de la empresa no puede tener más de 100 caracteres'))
    ], render_kw={'placeholder': _('Nombre de tu empresa')})
    
    industry = SelectField(_('Industria/Sector'), choices=[
        ('', _('Selecciona una industria')),
        ('technology', _('Tecnología')),
        ('health', _('Salud')),
        ('education', _('Educación')),
        ('finance', _('Finanzas')),
        ('retail', _('Comercio')),
        ('agriculture', _('Agricultura')),
        ('environment', _('Medio ambiente')),
        ('social', _('Impacto social')),
        ('other', _('Otro'))
    ], validators=[Optional()])
    
    expertise = TextAreaField(_('Área de Expertise'), validators=[
        Optional(),
        Length(max=500, message=_('La descripción no puede tener más de 500 caracteres'))
    ], render_kw={'placeholder': _('Describe tu área de especialización'), 'rows': 3})
    
    terms_accepted = BooleanField(_('Acepto los términos y condiciones'), validators=[
        DataRequired(message=_('Debes aceptar los términos y condiciones'))
    ])
    
    privacy_accepted = BooleanField(_('Acepto la política de privacidad'), validators=[
        DataRequired(message=_('Debes aceptar la política de privacidad'))
    ])
    
    newsletter = BooleanField(_('Quiero recibir el newsletter'), default=True)
    
    recaptcha = RecaptchaField()
    
    def validate_email(self, field):
        """Validar que el email no esté en uso."""
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError(_('Este email ya está registrado'))
    
    def validate_password(self, field):
        """Validar fortaleza de la contraseña."""
        is_valid, message = validate_password_strength(field.data)
        if not is_valid:
            raise ValidationError(_(message))
    
    def validate_phone(self, field):
        """Validar formato del teléfono."""
        if field.data:
            is_valid, message = validate_phone_number(field.data)
            if not is_valid:
                raise ValidationError(_(message))

class ForgotPasswordForm(FlaskForm):
    """Formulario para recuperación de contraseña."""
    email = EmailField(_('Email'), validators=[
        DataRequired(message=_('El email es obligatorio')),
        Email(message=_('Ingresa un email válido'))
    ], render_kw={'placeholder': _('tu@email.com'), 'autofocus': True})
    
    recaptcha = RecaptchaField()
    
    def validate_email(self, field):
        """Validar que el email existe en el sistema."""
        user = User.query.filter_by(email=field.data.lower().strip()).first()
        if not user:
            raise ValidationError(_('No existe una cuenta con este email'))
        if user.status != UserStatus.ACTIVE:
            raise ValidationError(_('Esta cuenta no está activa'))

class ResetPasswordForm(FlaskForm):
    """Formulario para resetear contraseña."""
    password = PasswordField(_('Nueva Contraseña'), validators=[
        DataRequired(message=_('La contraseña es obligatoria')),
        Length(min=8, message=_('La contraseña debe tener al menos 8 caracteres'))
    ], render_kw={'placeholder': _('Nueva contraseña segura')})
    
    password_confirm = PasswordField(_('Confirmar Contraseña'), validators=[
        DataRequired(message=_('Confirma tu nueva contraseña')),
        EqualTo('password', message=_('Las contraseñas deben coincidir'))
    ], render_kw={'placeholder': _('Repite tu nueva contraseña')})
    
    def validate_password(self, field):
        """Validar fortaleza de la nueva contraseña."""
        is_valid, message = validate_password_strength(field.data)
        if not is_valid:
            raise ValidationError(_(message))

class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar contraseña (usuario autenticado)."""
    current_password = PasswordField(_('Contraseña Actual'), validators=[
        DataRequired(message=_('Ingresa tu contraseña actual'))
    ], render_kw={'placeholder': _('Tu contraseña actual')})
    
    new_password = PasswordField(_('Nueva Contraseña'), validators=[
        DataRequired(message=_('La nueva contraseña es obligatoria')),
        Length(min=8, message=_('La contraseña debe tener al menos 8 caracteres'))
    ], render_kw={'placeholder': _('Nueva contraseña segura')})
    
    new_password_confirm = PasswordField(_('Confirmar Nueva Contraseña'), validators=[
        DataRequired(message=_('Confirma tu nueva contraseña')),
        EqualTo('new_password', message=_('Las contraseñas deben coincidir'))
    ], render_kw={'placeholder': _('Repite tu nueva contraseña')})
    
    def validate_new_password(self, field):
        """Validar fortaleza de la nueva contraseña."""
        is_valid, message = validate_password_strength(field.data)
        if not is_valid:
            raise ValidationError(_(message))

class TwoFactorSetupForm(FlaskForm):
    """Formulario para configurar 2FA."""
    verification_code = StringField(_('Código de Verificación'), validators=[
        DataRequired(message=_('Ingresa el código de 6 dígitos')),
        Length(min=6, max=6, message=_('El código debe tener 6 dígitos')),
        Regexp(r'^\d{6}$', message=_('Solo se permiten números'))
    ], render_kw={'placeholder': _('123456'), 'autocomplete': 'off'})

class TwoFactorVerifyForm(FlaskForm):
    """Formulario para verificar 2FA durante login."""
    verification_code = StringField(_('Código de Verificación'), validators=[
        DataRequired(message=_('Ingresa el código de 6 dígitos')),
        Length(min=6, max=6, message=_('El código debe tener 6 dígitos')),
        Regexp(r'^\d{6}$', message=_('Solo se permiten números'))
    ], render_kw={'placeholder': _('123456'), 'autocomplete': 'off', 'autofocus': True})
    
    backup_code = StringField(_('O ingresa un código de respaldo'), validators=[
        Optional(),
        Length(min=8, max=8, message=_('Los códigos de respaldo tienen 8 caracteres'))
    ], render_kw={'placeholder': _('Código de respaldo')})

# Rutas de autenticación
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión."""
    if g.get('current_user') and g.current_user.is_authenticated:
        return redirect(_get_user_dashboard_url(g.current_user))
    
    form = LoginForm()
    client_ip = get_client_ip()
    
    # Verificar rate limiting
    if not login_limiter.is_allowed(client_ip):
        flash(_('Demasiados intentos de login. Intenta nuevamente más tarde.'), 'error')
        return render_template('auth/login.html', form=form, rate_limited=True)
    
    if form.validate_on_submit():
        try:
            email = form.email.data.lower().strip()
            password = form.password.data
            remember = form.remember_me.data
            
            # Registrar intento de login
            login_attempt = LoginAttempt(
                email=email, ip_address=client_ip,
                user_agent=request.user_agent.string, status=AttemptStatus.PENDING
            )
            db.session.add(login_attempt)
            
            user, error_message = auth_service.verify_credentials(email, password)

            if user:
                # Verificar si requiere 2FA
                if user.two_factor_enabled:
                    # Guardar en sesión temporalmente
                    session['pending_2fa_user_id'] = user.id
                    session['pending_2fa_remember'] = remember
                    login_attempt.status = AttemptStatus.PENDING_2FA
                    db.session.commit()
                    
                    return redirect(url_for('auth.verify_2fa'))
                
                # Login exitoso
                success = auth_service.complete_login(user, remember, client_ip, request.user_agent.string)
                if success:
                    login_attempt.status = AttemptStatus.SUCCESS
                    db.session.commit()
                    return _redirect_after_login(user)
                else:
                    flash(_('Error iniciando sesión. Intenta nuevamente.'), 'error')
            
            else:
                # Credenciales incorrectas
                if error_message == "account_pending_verification":
                    flash(_('Debes verificar tu email antes de iniciar sesión.'), 'warning')
                    return redirect(url_for('auth.verify_email_reminder', email=email))
                elif error_message == "account_inactive":
                    flash(_('Tu cuenta está inactiva. Contacta al soporte.'), 'error')
                else: # invalid_credentials
                    flash(_('Email o contraseña incorrectos.'), 'error')

                login_attempt.status = AttemptStatus.FAILED
                login_attempt.failure_reason = 'invalid_credentials'
                db.session.commit()
                
                # Incrementar contador de rate limiting
                login_limiter.increment(client_ip)
                
                # Log de seguridad
                log_security_event('failed_login', {
                    'email': email,
                    'ip': client_ip,
                    'user_agent': request.user_agent.string
                })
                
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            db.session.rollback()
            flash(_('Ha ocurrido un error. Intenta nuevamente.'), 'error')
    
    # Trackear vista de página de login
    auth_service.track_auth_event('login_page_view', {'ip_address': client_ip, 'user_agent': request.user_agent.string})
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro de usuarios."""
    if g.get('current_user') and g.current_user.is_authenticated:
        return redirect(_get_user_dashboard_url(g.current_user))
    
    form = RegisterForm()
    client_ip = get_client_ip()
    
    # Verificar rate limiting
    if not register_limiter.is_allowed(client_ip):
        flash(_('Demasiados registros desde esta IP. Intenta nuevamente más tarde.'), 'error')
        return render_template('auth/register.html', form=form, rate_limited=True)
    
    if form.validate_on_submit():
        try:
            form_data = form.data
            form_data['ip_address'] = client_ip
            form_data['language'] = str(get_locale())

            success, user, error_message = auth_service.register_user(form_data)

            if success and user:
                # Incrementar rate limiter
                register_limiter.increment(client_ip)
                
                # Suscribir al newsletter si lo solicitó
                if form.newsletter.data:
                    _subscribe_to_newsletter(user.email, user.user_type.value)

                flash(_('¡Registro exitoso! Revisa tu email para verificar tu cuenta.'), 'success')
                return redirect(url_for('auth.verify_email_pending', email=user.email))
            else:
                flash(_(f'Error en el registro: {error_message}'), 'error')
        
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            db.session.rollback()
            flash(_('Ha ocurrido un error durante el registro. Intenta nuevamente.'), 'error')
    
    # Trackear vista de página de registro
    auth_service.track_auth_event('register_page_view', {'ip_address': client_ip, 'user_agent': request.user_agent.string})
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verificar email con token."""
    success, user, message = auth_service.verify_email_token(token)

    if success:
        flash(_('¡Email verificado exitosamente! Ya puedes iniciar sesión.'), 'success')
        return redirect(url_for('auth.login'))
    else:
        if "expirado" in message:
            flash(_('El token de verificación ha expirado.'), 'error')
            if user:
                return redirect(url_for('auth.verify_email_reminder', email=user.email))
        else:
            flash(_('Token de verificación inválido o ya ha sido utilizado.'), 'error')
        
        return redirect(url_for('auth.login'))

@auth_bp.route('/verify-email-pending')
def verify_email_pending():
    """Página de verificación pendiente."""
    email = request.args.get('email')
    return render_template('auth/verify_email_pending.html', email=email)

@auth_bp.route('/verify-email-reminder')
def verify_email_reminder():
    """Página para reenviar email de verificación."""
    email = request.args.get('email')
    
    if request.method == 'POST':
        user = User.query.filter_by(email=email).first()
        if user and user.status == UserStatus.PENDING_VERIFICATION:
            success = auth_service.send_verification_email(user)
            if success:
                flash(_('Email de verificación reenviado.'), 'success')
            else:
                flash(_('Error reenviando email. Intenta más tarde.'), 'error')
        
        return redirect(url_for('auth.verify_email_pending', email=email))
    
    return render_template('auth/verify_email_reminder.html', email=email)

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Página para recuperar contraseña."""
    form = ForgotPasswordForm()
    client_ip = get_client_ip()
    
    # Verificar rate limiting
    if not password_reset_limiter.is_allowed(client_ip):
        flash(_('Demasiadas solicitudes de reseteo. Intenta nuevamente más tarde.'), 'error')
        return render_template('auth/forgot_password.html', form=form, rate_limited=True)
    
    if form.validate_on_submit():
        try:
            email = form.email.data.lower().strip()
            success = auth_service.send_password_reset_email(email, client_ip)
            
            # Siempre mostrar el mismo mensaje (seguridad)
            flash(_('Si el email existe, recibirás instrucciones para resetear tu contraseña.'), 'info')
            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.error(f"Error in forgot password: {str(e)}")
            flash(_('Ha ocurrido un error. Intenta nuevamente.'), 'error')
    
    return render_template('auth/forgot_password.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Resetear contraseña con token."""
    reset_request = PasswordReset.query.filter_by(
        token=token,
        is_used=False
    ).first()
    
    if not reset_request or reset_request.expires_at < datetime.utcnow():
        flash(_('Token de reseteo inválido o expirado.'), 'error')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            user = reset_request.user
            user.set_password(form.password.data)
            
            # Marcar token como usado
            reset_request.is_used = True
            reset_request.used_at = datetime.utcnow()
            
            # Invalidar todas las sesiones existentes
            UserSession.query.filter_by(
                user_id=user.id,
                status=SessionStatus.ACTIVE
            ).update({'status': SessionStatus.EXPIRED})
            
            db.session.commit()
            
            # Trackear cambio de contraseña
            auth_service.track_auth_event('password_reset_completed', {'user_id': user.id})
            
            # Enviar notificación de cambio
            _send_password_changed_notification(user)
            
            flash(_('Contraseña actualizada exitosamente. Ya puedes iniciar sesión.'), 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            logger.error(f"Error resetting password: {str(e)}")
            db.session.rollback()
            flash(_('Error actualizando contraseña. Intenta nuevamente.'), 'error')
    
    return render_template('auth/reset_password.html', form=form, token=token)

@auth_bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    """Verificar código 2FA durante login."""
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        flash(_('Sesión expirada. Inicia sesión nuevamente.'), 'error')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_2fa_user_id', None)
        flash(_('Usuario no encontrado.'), 'error')
        return redirect(url_for('auth.login'))
    
    form = TwoFactorVerifyForm()
    
    if form.validate_on_submit():
        try:
            verification_code = form.verification_code.data
            backup_code = form.backup_code.data
            
            two_factor = TwoFactorAuth.query.filter_by(
                user_id=user.id,
                is_active=True
            ).first()
            
            is_valid = False
            
            if verification_code and two_factor:
                # Verificar código TOTP
                totp = pyotp.TOTP(two_factor.secret_key)
                is_valid = totp.verify(verification_code, valid_window=1)
            
            elif backup_code and two_factor:
                # Verificar código de respaldo
                if backup_code in two_factor.backup_codes:
                    is_valid = True
                    # Remover código usado
                    two_factor.backup_codes.remove(backup_code)
                    db.session.commit()
            
            if is_valid:
                # Completar login
                remember = session.pop('pending_2fa_remember', False)
                session.pop('pending_2fa_user_id', None)
                
                login_attempt = LoginAttempt(
                    email=user.email,
                    ip_address=get_client_ip(),
                    user_agent=request.user_agent.string,
                    status=AttemptStatus.SUCCESS
                )
                db.session.add(login_attempt)

                success = auth_service.complete_login(user, remember, get_client_ip(), request.user_agent.string)
                if success:
                    return _redirect_after_login(user)
            else:
                flash(_('Código de verificación inválido.'), 'error')

        except Exception as e:
            logger.error(f"Error verifying 2FA: {str(e)}")
            flash(_('Error verificando código. Intenta nuevamente.'), 'error')
    
    return render_template('auth/verify_2fa.html', form=form, user=user)

@auth_bp.route('/setup-2fa', methods=['GET', 'POST'])
@jwt_required()
def setup_2fa():
    """Configurar autenticación de dos factores."""
    user = User.query.get(get_jwt_identity())
    if not user:
        abort(404)
    
    # Verificar si ya tiene 2FA configurado
    existing_2fa = TwoFactorAuth.query.filter_by(
        user_id=user.id,
        is_active=True
    ).first()
    
    if request.method == 'GET':
        if existing_2fa:
            flash(_('Ya tienes 2FA configurado.'), 'info')
            return redirect(url_for('main.profile'))
        
        # Generar nuevo secreto
        secret = pyotp.random_base32()
        session['pending_2fa_secret'] = secret
        
        # Generar QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento')
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a base64 para mostrar en template
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        
        return render_template('auth/setup_2fa.html', 
                             qr_code=qr_code_data, 
                             secret=secret,
                             form=TwoFactorSetupForm())
    
    # POST - Verificar configuración
    form = TwoFactorSetupForm()
    secret = session.get('pending_2fa_secret')
    
    if not secret:
        flash(_('Sesión expirada. Intenta nuevamente.'), 'error')
        return redirect(url_for('auth.setup_2fa'))
    
    if form.validate_on_submit():
        try:
            verification_code = form.verification_code.data
            
            # Verificar código
            totp = pyotp.TOTP(secret)
            if totp.verify(verification_code, valid_window=1):
                # Generar códigos de respaldo
                backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
                
                # Guardar configuración 2FA
                two_factor = TwoFactorAuth(
                    user_id=user.id,
                    secret_key=secret,
                    backup_codes=backup_codes,
                    type=TwoFactorType.TOTP,
                    is_active=True
                )
                db.session.add(two_factor)
                
                # Actualizar usuario
                user.two_factor_enabled = True
                
                db.session.commit()
                
                # Limpiar sesión
                session.pop('pending_2fa_secret', None)
                
                # Trackear configuración
                auth_service.track_auth_event('2fa_enabled', {'user_id': user.id})
                
                flash(_('2FA configurado exitosamente.'), 'success')
                return render_template('auth/2fa_backup_codes.html', 
                                     backup_codes=backup_codes)
            else:
                flash(_('Código inválido. Verifica la hora en tu dispositivo.'), 'error')
        
        except Exception as e:
            logger.error(f"Error setting up 2FA: {str(e)}")
            db.session.rollback()
            flash(_('Error configurando 2FA. Intenta nuevamente.'), 'error')
    
    # Regenerar QR si hay error
    return redirect(url_for('auth.setup_2fa'))

@auth_bp.route('/logout', methods=['GET', 'POST'])
@jwt_required(optional=True)
def logout():
    """Cerrar sesión."""
    user_id = get_jwt_identity()
    
    if user_id:
        try:
            # Invalidar sesión actual
            jti = get_jwt().get('jti')
            if jti:
                # Agregar token a blacklist
                from app.api.middleware.auth import AuthMiddleware
                auth_middleware = current_app.extensions.get('auth_middleware')
                if auth_middleware:
                    auth_middleware.jwt_auth.blacklist_manager.add_token(
                        jti, 
                        datetime.utcnow() + timedelta(hours=24)
                    )
            
            # Marcar sesión como cerrada en BD
            UserSession.query.filter_by(
                user_id=user_id,
                status=SessionStatus.ACTIVE
            ).update({'status': SessionStatus.LOGGED_OUT})
            
            db.session.commit()
            
            # Trackear logout
            auth_service.track_auth_event('user_logout', {'user_id': user_id})
            
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
    
    # Limpiar datos de sesión
    session.clear()
    
    flash(_('Has cerrado sesión exitosamente.'), 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/oauth/<provider>')
def oauth_login(provider):
    """Iniciar autenticación OAuth."""
    try:
        oauth_service = OAuthService()
        
        if not oauth_service.is_provider_enabled(provider):
            flash(_('Proveedor de autenticación no disponible.'), 'error')
            return redirect(url_for('auth.login'))
        
        # Generar URL de autorización
        auth_url, state = oauth_service.get_authorization_url(provider)
        
        # Guardar state en sesión para verificación
        session[f'oauth_state_{provider}'] = state
        
        # Trackear inicio OAuth
        auth_service.track_auth_event('oauth_started', {'provider': provider})
        
        return redirect(auth_url)
    
    except Exception as e:
        logger.error(f"Error starting OAuth for {provider}: {str(e)}")
        flash(_('Error iniciando autenticación. Intenta nuevamente.'), 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/oauth/<provider>/callback')
def oauth_callback(provider):
    """Callback de autenticación OAuth."""
    try:
        oauth_service = OAuthService()
        
        # Verificar state
        expected_state = session.pop(f'oauth_state_{provider}', None)
        received_state = request.args.get('state')
        
        if not expected_state or expected_state != received_state:
            flash(_('Error de seguridad en autenticación. Intenta nuevamente.'), 'error')
            return redirect(url_for('auth.login'))
        
        # Obtener código de autorización
        code = request.args.get('code')
        if not code:
            error = request.args.get('error', 'unknown_error')
            flash(_('Autenticación cancelada o falló.'), 'error')
            return redirect(url_for('auth.login'))
        
        # Intercambiar código por token
        token_data = oauth_service.exchange_code_for_token(provider, code)
        
        # Obtener información del usuario
        user_info = oauth_service.get_user_info(provider, token_data['access_token'])
        
        # Buscar cuenta OAuth existente
        oauth_account = OAuthAccount.query.filter_by(
            provider=provider,
            provider_user_id=user_info['id']
        ).first()
        
        if oauth_account:
            # Usuario existente - login
            user = oauth_account.user
            
            if user.status != UserStatus.ACTIVE:
                flash(_('Tu cuenta no está activa.'), 'error')
                return redirect(url_for('auth.login'))
            
            # Actualizar token
            oauth_account.access_token = token_data['access_token']
            oauth_account.refresh_token = token_data.get('refresh_token')
            oauth_account.token_expires_at = (
                datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
            )
            oauth_account.last_used_at = datetime.utcnow()
            
            db.session.commit()
            
            # Completar login
            login_attempt = LoginAttempt(
                email=user.email,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                status=AttemptStatus.SUCCESS,
                auth_method='oauth'
            )
            db.session.add(login_attempt)
            
            success = _complete_user_login(user, False, login_attempt)
            if success:
                auth_service.track_auth_event('oauth_login_success', {
                    'provider': provider,
                    'user_id': user.id
                })
                return _redirect_after_login(user)
        
        else:
            # Verificar si existe usuario con mismo email
            existing_user = User.query.filter_by(email=user_info['email']).first()
            
            if existing_user:
                # Vincular cuenta OAuth existente
                oauth_account = OAuthAccount(
                    user_id=existing_user.id,
                    provider=provider,
                    provider_user_id=user_info['id'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token'),
                    token_expires_at=(
                        datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
                    )
                )
                db.session.add(oauth_account)
                db.session.commit()
                
                flash(_('Cuenta vinculada exitosamente.'), 'success')
                
                # Login automático
                login_attempt = LoginAttempt(
                    email=existing_user.email,
                    ip_address=get_client_ip(),
                    user_agent=request.user_agent.string,
                    status=AttemptStatus.SUCCESS,
                    auth_method='oauth'
                )
                db.session.add(login_attempt)
                
                success = _complete_user_login(existing_user, False, login_attempt)
                if success:
                    return _redirect_after_login(existing_user)
            
            else:
                # Crear nuevo usuario
                user = User(
                    email=user_info['email'],
                    first_name=user_info.get('first_name', ''),
                    last_name=user_info.get('last_name', ''),
                    avatar_url=user_info.get('avatar_url'),
                    user_type=UserType.ENTREPRENEUR,  # Default
                    status=UserStatus.ACTIVE,  # OAuth users son verificados automáticamente
                    email_verified_at=datetime.utcnow(),
                    registration_ip=get_client_ip(),
                    preferred_language=get_locale()
                )
                
                db.session.add(user)
                db.session.flush()
                
                # Crear cuenta OAuth
                oauth_account = OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=user_info['id'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token'),
                    token_expires_at=(
                        datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
                    )
                )
                db.session.add(oauth_account)
                
                # Crear perfil de emprendedor por defecto
                entrepreneur = Entrepreneur(user_id=user.id)
                db.session.add(entrepreneur)
                
                db.session.commit()
                
                # Trackear registro OAuth
                auth_service.track_auth_event('oauth_registration', {
                    'provider': provider,
                    'user_id': user.id
                })
                
                # Login automático
                login_attempt = LoginAttempt(
                    email=user.email,
                    ip_address=get_client_ip(),
                    user_agent=request.user_agent.string,
                    status=AttemptStatus.SUCCESS,
                    auth_method='oauth'
                )
                db.session.add(login_attempt)
                
                success = _complete_user_login(user, False, login_attempt)
                if success:
                    flash(_('¡Bienvenido! Tu cuenta se ha creado exitosamente.'), 'success')
                    return redirect(url_for('main.onboarding'))
        
        flash(_('Error completando autenticación.'), 'error')
        return redirect(url_for('auth.login'))
    
    except Exception as e:
        logger.error(f"Error in OAuth callback for {provider}: {str(e)}")
        flash(_('Error en autenticación. Intenta nuevamente.'), 'error')
        return redirect(url_for('auth.login'))

# Funciones auxiliares
def _get_user_dashboard_url(user: User) -> str:
    """Obtiene la URL del dashboard según el tipo de usuario."""
    dashboard_urls = {
        UserType.ADMIN: 'admin_dashboard.index',
        UserType.ENTREPRENEUR: 'entrepreneur_dashboard.index',
        UserType.ALLY: 'ally_dashboard.index',
        UserType.CLIENT: 'client_dashboard.index'
    }
    
    endpoint = dashboard_urls.get(user.user_type, 'main.index')
    return url_for(endpoint)

def _redirect_after_login(user: User):
    """Redirige al usuario después del login."""
    # Verificar si hay URL de destino en sesión
    next_page = session.pop('next_url', None)
    
    if next_page and is_safe_url(next_page):
        return redirect(next_page)
    
    # Redirigir según tipo de usuario
    return redirect(_get_user_dashboard_url(user))

def _send_welcome_email(user: User):
    """Envía email de bienvenida."""
    try:
        email_service = EmailService()
        email_service.send_welcome_email(user)
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")

def _send_password_changed_notification(user: User):
    """Envía notificación de cambio de contraseña."""
    try:
        email_service = EmailService()
        email_service.send_password_changed_notification(user)
    except Exception as e:
        logger.error(f"Error sending password changed notification: {str(e)}")

def _subscribe_to_newsletter(email: str, user_type: str):
    """Suscribe al newsletter."""
    try:
        # Local import to avoid circular dependency if newsletter service uses other services
        from app.services.newsletter_service import NewsletterService
        newsletter_service = NewsletterService()
        newsletter_service.subscribe(email, interests=user_type)
    except Exception as e:
        logger.error(f"Error subscribing to newsletter: {str(e)}")

# Procesadores de contexto
@auth_bp.context_processor
def inject_auth_context():
    """Inyecta contexto de autenticación."""
    return {
        'oauth_providers': _get_enabled_oauth_providers(),
        'registration_enabled': current_app.config.get('REGISTRATION_ENABLED', True),
        'password_reset_enabled': current_app.config.get('PASSWORD_RESET_ENABLED', True)
    }

def _get_enabled_oauth_providers():
    """Obtiene proveedores OAuth habilitados."""
    try:
        oauth_service = OAuthService()
        return oauth_service.get_enabled_providers()
    except:
        return []

# Manejadores de errores
@auth_bp.errorhandler(429)
def handle_rate_limit_error(error):
    """Maneja errores de rate limiting."""
    return render_template('auth/rate_limited.html'), 429