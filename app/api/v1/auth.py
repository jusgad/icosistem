"""
API v1 Authentication Endpoints
==============================

Este módulo implementa todos los endpoints de autenticación y autorización
para la API v1, incluyendo login, registro, recuperación de contraseña,
verificación de email y gestión de tokens.

Funcionalidades:
- Login y logout con JWT
- Registro de usuarios
- Verificación de email
- Recuperación y reset de contraseña
- Refresh de tokens
- Cambio de contraseña
- Autenticación con 2FA
- OAuth con Google/Microsoft
- API Keys para servicios
"""

from flask import Blueprint, request, jsonify, current_app, g
from flask_restful import Resource, Api
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import jwt
import secrets
import pyotp
import qrcode
import io
import base64
from typing import Dict, Any, Optional, Tuple
import re
from email_validator import validate_email, EmailNotValidError

from app.extensions import db, limiter
from app.models.user import User
from app.models.admin import Admin
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError,
    BusinessLogicError
)
from app.services.email import EmailService
from app.services.sms import SMSService
from app.services.oauth import OAuthService
from app.utils.decorators import validate_json, log_activity
from app.api.middleware.auth import api_auth_required, get_current_user
from app.api.middleware.rate_limiting import auth_rate_limit


# Crear blueprint para auth
auth_bp = Blueprint('auth', __name__)
api = Api(auth_bp)


class AuthConfig:
    """Configuración de autenticación"""
    
    # JWT Configuration
    JWT_ALGORITHM = 'HS256'
    ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    PASSWORD_PATTERN = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]'
    
    # Account verification
    EMAIL_VERIFICATION_EXPIRES = timedelta(hours=24)
    PASSWORD_RESET_EXPIRES = timedelta(hours=2)
    
    # 2FA Configuration
    TOTP_ISSUER = 'Ecosistema Emprendimiento'
    
    # Rate limiting
    LOGIN_RATE_LIMIT = "5 per minute"
    REGISTER_RATE_LIMIT = "3 per minute"
    PASSWORD_RESET_RATE_LIMIT = "2 per minute"


class LoginResource(Resource):
    """Endpoint de login"""
    
    decorators = [limiter.limit(AuthConfig.LOGIN_RATE_LIMIT)]
    
    @validate_json
    @log_activity(ActivityType.LOGIN, "User login attempt")
    def post(self):
        """
        Autenticar usuario y generar tokens JWT
        
        Body:
            email: Email del usuario
            password: Contraseña
            remember_me: Si mantener sesión activa (opcional)
            totp_code: Código 2FA si está habilitado (opcional)
        
        Returns:
            Tokens JWT y información del usuario
        """
        data = request.get_json()
        
        # Validar campos requeridos
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        totp_code = data.get('totp_code', '')
        
        if not email or not password:
            raise ValidationError("Email y contraseña son requeridos")
        
        # Validar formato de email
        try:
            validate_email(email)
        except EmailNotValidError:
            raise ValidationError("Formato de email inválido")
        
        # Buscar usuario
        user = User.query.filter_by(email=email, is_active=True).first()
        if not user or not user.check_password(password):
            # Log intento fallido
            ActivityLog.log_activity(
                activity_type=ActivityType.LOGIN,
                description=f"Failed login attempt for {email}",
                severity=ActivitySeverity.MEDIUM,
                metadata={'email': email, 'reason': 'invalid_credentials'},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            raise AuthenticationError("Credenciales inválidas")
        
        # Verificar si la cuenta está verificada
        if not user.email_verified:
            raise AuthenticationError("Debe verificar su email antes de iniciar sesión")
        
        # Verificar 2FA si está habilitado
        if user.two_factor_enabled:
            if not totp_code:
                return {
                    'requires_2fa': True,
                    'message': 'Se requiere código de autenticación de dos factores'
                }, 200
            
            if not self._verify_totp(user, totp_code):
                ActivityLog.log_activity(
                    activity_type=ActivityType.LOGIN,
                    description=f"Failed 2FA verification for {email}",
                    user_id=user.id,
                    severity=ActivitySeverity.HIGH,
                    metadata={'email': email, 'reason': 'invalid_2fa'},
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                raise AuthenticationError("Código de autenticación inválido")
        
        # Generar tokens
        access_token = self._generate_access_token(user)
        refresh_token = self._generate_refresh_token(user)
        
        # Actualizar información de login
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1
        
        # Guardar refresh token
        user.refresh_token = refresh_token
        user.refresh_token_expires = datetime.utcnow() + AuthConfig.REFRESH_TOKEN_EXPIRES
        
        db.session.commit()
        
        # Log login exitoso
        ActivityLog.log_activity(
            activity_type=ActivityType.LOGIN,
            description=f"Successful login for {email}",
            user_id=user.id,
            severity=ActivitySeverity.LOW,
            metadata={
                'email': email,
                'user_type': user.user_type,
                'remember_me': remember_me
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': int(AuthConfig.ACCESS_TOKEN_EXPIRES.total_seconds()),
            'user': user.to_dict(include_sensitive=False),
            'permissions': user.get_permissions()
        }, 200
    
    def _verify_totp(self, user: User, code: str) -> bool:
        """Verifica código TOTP"""
        if not user.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(user.two_factor_secret)
        return totp.verify(code, valid_window=1)
    
    def _generate_access_token(self, user: User) -> str:
        """Genera token de acceso JWT"""
        payload = {
            'user_id': user.id,
            'email': user.email,
            'user_type': user.user_type,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + AuthConfig.ACCESS_TOKEN_EXPIRES,
            'type': 'access'
        }
        
        return jwt.encode(
            payload, 
            current_app.config['SECRET_KEY'], 
            algorithm=AuthConfig.JWT_ALGORITHM
        )
    
    def _generate_refresh_token(self, user: User) -> str:
        """Genera token de refresh JWT"""
        payload = {
            'user_id': user.id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + AuthConfig.REFRESH_TOKEN_EXPIRES,
            'type': 'refresh',
            'jti': secrets.token_urlsafe(32)  # Unique token ID
        }
        
        return jwt.encode(
            payload, 
            current_app.config['SECRET_KEY'], 
            algorithm=AuthConfig.JWT_ALGORITHM
        )


class RegisterResource(Resource):
    """Endpoint de registro"""
    
    decorators = [limiter.limit(AuthConfig.REGISTER_RATE_LIMIT)]
    
    @validate_json
    @log_activity(ActivityType.USER_CREATE, "User registration attempt")
    def post(self):
        """
        Registrar nuevo usuario
        
        Body:
            email: Email del usuario
            password: Contraseña
            first_name: Nombre
            last_name: Apellido
            user_type: Tipo de usuario (entrepreneur, ally, client)
            phone: Teléfono (opcional)
            organization_name: Nombre de organización (opcional)
        
        Returns:
            Usuario creado y token de verificación
        """
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['email', 'password', 'first_name', 'last_name', 'user_type']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        email = data['email'].strip().lower()
        password = data['password']
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        user_type = data['user_type'].lower()
        phone = data.get('phone', '').strip()
        organization_name = data.get('organization_name', '').strip()
        
        # Validar email
        try:
            validate_email(email)
        except EmailNotValidError:
            raise ValidationError("Formato de email inválido")
        
        # Verificar si el usuario ya existe
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise BusinessLogicError("Ya existe un usuario con este email")
        
        # Validar contraseña
        self._validate_password(password)
        
        # Validar tipo de usuario
        valid_user_types = ['entrepreneur', 'ally', 'client', 'admin']
        if user_type not in valid_user_types:
            raise ValidationError(f"Tipo de usuario inválido. Válidos: {', '.join(valid_user_types)}")
        
        # Crear usuario base
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type,
            phone=phone,
            is_active=True,
            email_verified=False
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Para obtener el ID
        
        # Crear perfil específico según tipo de usuario
        specific_user = self._create_specific_user_profile(
            user, user_type, organization_name, data
        )
        
        # Generar token de verificación de email
        verification_token = self._generate_email_verification_token(user)
        
        db.session.commit()
        
        # Enviar email de verificación
        try:
            EmailService.send_email_verification(user, verification_token)
        except Exception as e:
            current_app.logger.error(f"Failed to send verification email: {e}")
        
        # Log registro exitoso
        ActivityLog.log_activity(
            activity_type=ActivityType.USER_CREATE,
            description=f"New user registered: {email}",
            user_id=user.id,
            severity=ActivitySeverity.LOW,
            metadata={
                'email': email,
                'user_type': user_type,
                'has_organization': bool(organization_name)
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'message': 'Usuario registrado exitosamente',
            'user': user.to_dict(include_sensitive=False),
            'verification_required': True,
            'verification_email_sent': True
        }, 201
    
    def _validate_password(self, password: str):
        """Valida la fortaleza de la contraseña"""
        if len(password) < AuthConfig.MIN_PASSWORD_LENGTH:
            raise ValidationError(f"La contraseña debe tener al menos {AuthConfig.MIN_PASSWORD_LENGTH} caracteres")
        
        if not re.match(AuthConfig.PASSWORD_PATTERN, password):
            raise ValidationError(
                "La contraseña debe contener al menos: "
                "una minúscula, una mayúscula, un número y un carácter especial"
            )
    
    def _create_specific_user_profile(self, user: User, user_type: str, organization_name: str, data: Dict) -> Any:
        """Crea el perfil específico según el tipo de usuario"""
        if user_type == 'entrepreneur':
            entrepreneur = Entrepreneur(
                user_id=user.id,
                business_stage=data.get('business_stage', 'idea'),
                industry=data.get('industry', ''),
                company_name=organization_name
            )
            db.session.add(entrepreneur)
            return entrepreneur
            
        elif user_type == 'ally':
            ally = Ally(
                user_id=user.id,
                expertise_areas=data.get('expertise_areas', []),
                years_experience=data.get('years_experience', 0),
                organization=organization_name,
                available_for_mentorship=data.get('available_for_mentorship', True)
            )
            db.session.add(ally)
            return ally
            
        elif user_type == 'client':
            client = Client(
                user_id=user.id,
                organization=organization_name,
                role=data.get('role', ''),
                interest_areas=data.get('interest_areas', [])
            )
            db.session.add(client)
            return client
            
        elif user_type == 'admin':
            admin = Admin(
                user_id=user.id,
                permissions=data.get('permissions', []),
                department=data.get('department', '')
            )
            db.session.add(admin)
            return admin
        
        return None
    
    def _generate_email_verification_token(self, user: User) -> str:
        """Genera token de verificación de email"""
        payload = {
            'user_id': user.id,
            'email': user.email,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + AuthConfig.EMAIL_VERIFICATION_EXPIRES,
            'type': 'email_verification'
        }
        
        return jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm=AuthConfig.JWT_ALGORITHM
        )


class LogoutResource(Resource):
    """Endpoint de logout"""
    
    @api_auth_required
    @log_activity(ActivityType.LOGOUT, "User logout")
    def post(self):
        """
        Cerrar sesión del usuario actual
        
        Headers:
            Authorization: Bearer <access_token>
        
        Returns:
            Confirmación de logout
        """
        user = get_current_user()
        
        # Invalidar refresh token
        user.refresh_token = None
        user.refresh_token_expires = None
        db.session.commit()
        
        # Log logout
        ActivityLog.log_activity(
            activity_type=ActivityType.LOGOUT,
            description=f"User logout: {user.email}",
            user_id=user.id,
            severity=ActivitySeverity.LOW,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'message': 'Sesión cerrada exitosamente'
        }, 200


class RefreshTokenResource(Resource):
    """Endpoint para refresh de tokens"""
    
    @validate_json
    def post(self):
        """
        Renovar access token usando refresh token
        
        Body:
            refresh_token: Token de refresh válido
        
        Returns:
            Nuevo access token
        """
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            raise ValidationError("Refresh token es requerido")
        
        try:
            # Decodificar refresh token
            payload = jwt.decode(
                refresh_token,
                current_app.config['SECRET_KEY'],
                algorithms=[AuthConfig.JWT_ALGORITHM]
            )
            
            if payload.get('type') != 'refresh':
                raise AuthenticationError("Token inválido")
            
            user_id = payload.get('user_id')
            user = User.query.get(user_id)
            
            if not user or not user.is_active:
                raise AuthenticationError("Usuario no válido")
            
            # Verificar que el refresh token coincida
            if user.refresh_token != refresh_token:
                raise AuthenticationError("Refresh token inválido")
            
            # Verificar expiración
            if user.refresh_token_expires and user.refresh_token_expires < datetime.utcnow():
                raise AuthenticationError("Refresh token expirado")
            
            # Generar nuevo access token
            new_access_token = LoginResource()._generate_access_token(user)
            
            return {
                'access_token': new_access_token,
                'token_type': 'Bearer',
                'expires_in': int(AuthConfig.ACCESS_TOKEN_EXPIRES.total_seconds())
            }, 200
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token expirado")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Refresh token inválido")


class EmailVerificationResource(Resource):
    """Endpoint para verificación de email"""
    
    def get(self, token):
        """
        Verificar email usando token
        
        Args:
            token: Token de verificación de email
        
        Returns:
            Confirmación de verificación
        """
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=[AuthConfig.JWT_ALGORITHM]
            )
            
            if payload.get('type') != 'email_verification':
                raise ValidationError("Token inválido")
            
            user_id = payload.get('user_id')
            user = User.query.get(user_id)
            
            if not user:
                raise ValidationError("Usuario no encontrado")
            
            if user.email_verified:
                return {
                    'message': 'Email ya verificado anteriormente'
                }, 200
            
            # Marcar email como verificado
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
            db.session.commit()
            
            # Log verificación
            ActivityLog.log_activity(
                activity_type=ActivityType.EMAIL_VERIFICATION,
                description=f"Email verified for {user.email}",
                user_id=user.id,
                severity=ActivitySeverity.LOW,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            return {
                'message': 'Email verificado exitosamente',
                'user': user.to_dict(include_sensitive=False)
            }, 200
            
        except jwt.ExpiredSignatureError:
            raise ValidationError("Token de verificación expirado")
        except jwt.InvalidTokenError:
            raise ValidationError("Token de verificación inválido")


class ResendVerificationResource(Resource):
    """Endpoint para reenviar verificación de email"""
    
    decorators = [limiter.limit("3 per hour")]
    
    @validate_json
    def post(self):
        """
        Reenviar email de verificación
        
        Body:
            email: Email del usuario
        
        Returns:
            Confirmación de envío
        """
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            raise ValidationError("Email es requerido")
        
        user = User.query.filter_by(email=email).first()
        if not user:
            # No revelar si el usuario existe o no
            return {
                'message': 'Si el email existe, se enviará un enlace de verificación'
            }, 200
        
        if user.email_verified:
            return {
                'message': 'El email ya está verificado'
            }, 200
        
        # Generar nuevo token
        verification_token = RegisterResource()._generate_email_verification_token(user)
        
        # Enviar email
        try:
            EmailService.send_email_verification(user, verification_token)
        except Exception as e:
            current_app.logger.error(f"Failed to resend verification email: {e}")
            raise BusinessLogicError("Error al enviar email de verificación")
        
        return {
            'message': 'Email de verificación enviado'
        }, 200


class ForgotPasswordResource(Resource):
    """Endpoint para solicitar reset de contraseña"""
    
    decorators = [limiter.limit(AuthConfig.PASSWORD_RESET_RATE_LIMIT)]
    
    @validate_json
    def post(self):
        """
        Solicitar reset de contraseña
        
        Body:
            email: Email del usuario
        
        Returns:
            Confirmación de envío
        """
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            raise ValidationError("Email es requerido")
        
        user = User.query.filter_by(email=email, is_active=True).first()
        if not user:
            # No revelar si el usuario existe o no
            return {
                'message': 'Si el email existe, se enviará un enlace de recuperación'
            }, 200
        
        # Generar token de reset
        reset_token = self._generate_password_reset_token(user)
        
        # Enviar email
        try:
            EmailService.send_password_reset(user, reset_token)
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {e}")
            raise BusinessLogicError("Error al enviar email de recuperación")
        
        # Log solicitud
        ActivityLog.log_activity(
            activity_type=ActivityType.PASSWORD_RESET,
            description=f"Password reset requested for {email}",
            user_id=user.id,
            severity=ActivitySeverity.MEDIUM,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'message': 'Enlace de recuperación enviado al email'
        }, 200
    
    def _generate_password_reset_token(self, user: User) -> str:
        """Genera token de reset de contraseña"""
        payload = {
            'user_id': user.id,
            'email': user.email,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + AuthConfig.PASSWORD_RESET_EXPIRES,
            'type': 'password_reset'
        }
        
        return jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm=AuthConfig.JWT_ALGORITHM
        )


class ResetPasswordResource(Resource):
    """Endpoint para reset de contraseña"""
    
    @validate_json
    def post(self):
        """
        Resetear contraseña usando token
        
        Body:
            token: Token de reset
            new_password: Nueva contraseña
        
        Returns:
            Confirmación de cambio
        """
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('new_password')
        
        if not token or not new_password:
            raise ValidationError("Token y nueva contraseña son requeridos")
        
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=[AuthConfig.JWT_ALGORITHM]
            )
            
            if payload.get('type') != 'password_reset':
                raise ValidationError("Token inválido")
            
            user_id = payload.get('user_id')
            user = User.query.get(user_id)
            
            if not user or not user.is_active:
                raise ValidationError("Usuario no válido")
            
            # Validar nueva contraseña
            RegisterResource()._validate_password(new_password)
            
            # Cambiar contraseña
            user.set_password(new_password)
            
            # Invalidar refresh tokens existentes
            user.refresh_token = None
            user.refresh_token_expires = None
            
            db.session.commit()
            
            # Log cambio de contraseña
            ActivityLog.log_activity(
                activity_type=ActivityType.PASSWORD_CHANGE,
                description=f"Password reset completed for {user.email}",
                user_id=user.id,
                severity=ActivitySeverity.MEDIUM,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            return {
                'message': 'Contraseña cambiada exitosamente'
            }, 200
            
        except jwt.ExpiredSignatureError:
            raise ValidationError("Token de reset expirado")
        except jwt.InvalidTokenError:
            raise ValidationError("Token de reset inválido")


class ChangePasswordResource(Resource):
    """Endpoint para cambio de contraseña autenticado"""
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.PASSWORD_CHANGE, "Password change")
    def post(self):
        """
        Cambiar contraseña del usuario autenticado
        
        Headers:
            Authorization: Bearer <access_token>
        
        Body:
            current_password: Contraseña actual
            new_password: Nueva contraseña
        
        Returns:
            Confirmación de cambio
        """
        user = get_current_user()
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            raise ValidationError("Contraseña actual y nueva son requeridas")
        
        # Verificar contraseña actual
        if not user.check_password(current_password):
            raise AuthenticationError("Contraseña actual incorrecta")
        
        # Validar nueva contraseña
        RegisterResource()._validate_password(new_password)
        
        # Verificar que no sea la misma contraseña
        if user.check_password(new_password):
            raise ValidationError("La nueva contraseña debe ser diferente a la actual")
        
        # Cambiar contraseña
        user.set_password(new_password)
        
        # Invalidar refresh tokens existentes (forzar re-login)
        user.refresh_token = None
        user.refresh_token_expires = None
        
        db.session.commit()
        
        return {
            'message': 'Contraseña cambiada exitosamente'
        }, 200


class TwoFactorSetupResource(Resource):
    """Endpoint para configurar 2FA"""
    
    @api_auth_required
    def get(self):
        """
        Obtener QR code para configurar 2FA
        
        Headers:
            Authorization: Bearer <access_token>
        
        Returns:
            URL y QR code para configurar 2FA
        """
        user = get_current_user()
        
        if user.two_factor_enabled:
            return {
                'message': '2FA ya está habilitado'
            }, 200
        
        # Generar secret si no existe
        if not user.two_factor_secret:
            user.two_factor_secret = pyotp.random_base32()
            db.session.commit()
        
        # Generar URL para el QR
        totp = pyotp.TOTP(user.two_factor_secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=AuthConfig.TOTP_ISSUER
        )
        
        # Generar QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            'secret': user.two_factor_secret,
            'qr_code': f"data:image/png;base64,{img_str}",
            'provisioning_uri': provisioning_uri
        }, 200
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Habilitar 2FA con código de verificación
        
        Headers:
            Authorization: Bearer <access_token>
        
        Body:
            totp_code: Código TOTP para verificar
        
        Returns:
            Confirmación de habilitación
        """
        user = get_current_user()
        data = request.get_json()
        
        totp_code = data.get('totp_code')
        if not totp_code:
            raise ValidationError("Código TOTP es requerido")
        
        if not user.two_factor_secret:
            raise ValidationError("Debe configurar 2FA primero")
        
        # Verificar código
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise ValidationError("Código TOTP inválido")
        
        # Habilitar 2FA
        user.two_factor_enabled = True
        db.session.commit()
        
        # Log habilitación de 2FA
        ActivityLog.log_activity(
            activity_type=ActivityType.USER_UPDATE,
            description="2FA enabled",
            user_id=user.id,
            severity=ActivitySeverity.MEDIUM,
            metadata={'action': '2fa_enabled'},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'message': '2FA habilitado exitosamente'
        }, 200


class TwoFactorDisableResource(Resource):
    """Endpoint para deshabilitar 2FA"""
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Deshabilitar 2FA
        
        Headers:
            Authorization: Bearer <access_token>
        
        Body:
            password: Contraseña actual para confirmar
            totp_code: Código TOTP actual
        
        Returns:
            Confirmación de deshabilitación
        """
        user = get_current_user()
        data = request.get_json()
        
        password = data.get('password')
        totp_code = data.get('totp_code')
        
        if not password or not totp_code:
            raise ValidationError("Contraseña y código TOTP son requeridos")
        
        if not user.two_factor_enabled:
            return {
                'message': '2FA ya está deshabilitado'
            }, 200
        
        # Verificar contraseña
        if not user.check_password(password):
            raise AuthenticationError("Contraseña incorrecta")
        
        # Verificar código TOTP
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise ValidationError("Código TOTP inválido")
        
        # Deshabilitar 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        db.session.commit()
        
        # Log deshabilitación de 2FA
        ActivityLog.log_activity(
            activity_type=ActivityType.USER_UPDATE,
            description="2FA disabled",
            user_id=user.id,
            severity=ActivitySeverity.MEDIUM,
            metadata={'action': '2fa_disabled'},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'message': '2FA deshabilitado exitosamente'
        }, 200


class UserProfileResource(Resource):
    """Endpoint para obtener perfil del usuario autenticado"""
    
    @api_auth_required
    def get(self):
        """
        Obtener perfil del usuario autenticado
        
        Headers:
            Authorization: Bearer <access_token>
        
        Returns:
            Información completa del usuario
        """
        user = get_current_user()
        
        # Obtener perfil específico según tipo de usuario
        profile_data = user.to_dict(include_sensitive=False)
        
        if user.user_type == 'entrepreneur':
            entrepreneur = Entrepreneur.query.filter_by(user_id=user.id).first()
            if entrepreneur:
                profile_data['entrepreneur_profile'] = entrepreneur.to_dict()
        
        elif user.user_type == 'ally':
            ally = Ally.query.filter_by(user_id=user.id).first()
            if ally:
                profile_data['ally_profile'] = ally.to_dict()
        
        elif user.user_type == 'client':
            client = Client.query.filter_by(user_id=user.id).first()
            if client:
                profile_data['client_profile'] = client.to_dict()
        
        elif user.user_type == 'admin':
            admin = Admin.query.filter_by(user_id=user.id).first()
            if admin:
                profile_data['admin_profile'] = admin.to_dict()
        
        # Agregar información adicional
        profile_data['permissions'] = user.get_permissions()
        profile_data['two_factor_enabled'] = user.two_factor_enabled
        profile_data['last_login'] = user.last_login.isoformat() if user.last_login else None
        
        return profile_data, 200


class OAuthLoginResource(Resource):
    """Endpoint para login con OAuth"""
    
    @validate_json
    def post(self):
        """
        Login con proveedor OAuth (Google, Microsoft, etc.)
        
        Body:
            provider: Proveedor OAuth (google, microsoft)
            code: Código de autorización OAuth
            redirect_uri: URI de redirección usado
        
        Returns:
            Tokens JWT y información del usuario
        """
        data = request.get_json()
        
        provider = data.get('provider')
        code = data.get('code')
        redirect_uri = data.get('redirect_uri')
        
        if not all([provider, code, redirect_uri]):
            raise ValidationError("Provider, code y redirect_uri son requeridos")
        
        valid_providers = ['google', 'microsoft']
        if provider not in valid_providers:
            raise ValidationError(f"Proveedor no válido. Válidos: {', '.join(valid_providers)}")
        
        try:
            # Obtener información del usuario desde OAuth
            oauth_service = OAuthService()
            user_info = oauth_service.get_user_info(provider, code, redirect_uri)
            
            email = user_info.get('email')
            if not email:
                raise BusinessLogicError("No se pudo obtener email del proveedor OAuth")
            
            # Buscar usuario existente
            user = User.query.filter_by(email=email).first()
            
            if user:
                # Usuario existente - actualizar información OAuth
                if provider == 'google':
                    user.google_id = user_info.get('id')
                elif provider == 'microsoft':
                    user.microsoft_id = user_info.get('id')
                
                # Marcar email como verificado si viene de OAuth
                if not user.email_verified:
                    user.email_verified = True
                    user.email_verified_at = datetime.utcnow()
                
            else:
                # Crear nuevo usuario desde OAuth
                user = self._create_oauth_user(user_info, provider)
            
            # Actualizar último login
            user.last_login = datetime.utcnow()
            user.login_count = (user.login_count or 0) + 1
            
            db.session.commit()
            
            # Generar tokens
            access_token = LoginResource()._generate_access_token(user)
            refresh_token = LoginResource()._generate_refresh_token(user)
            
            # Guardar refresh token
            user.refresh_token = refresh_token
            user.refresh_token_expires = datetime.utcnow() + AuthConfig.REFRESH_TOKEN_EXPIRES
            db.session.commit()
            
            # Log login OAuth
            ActivityLog.log_activity(
                activity_type=ActivityType.LOGIN,
                description=f"OAuth login with {provider}",
                user_id=user.id,
                severity=ActivitySeverity.LOW,
                metadata={
                    'provider': provider,
                    'email': email,
                    'oauth_id': user_info.get('id')
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(AuthConfig.ACCESS_TOKEN_EXPIRES.total_seconds()),
                'user': user.to_dict(include_sensitive=False),
                'permissions': user.get_permissions(),
                'oauth_provider': provider
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"OAuth login error: {e}")
            raise BusinessLogicError("Error en autenticación OAuth")
    
    def _create_oauth_user(self, user_info: Dict, provider: str) -> User:
        """Crea usuario desde información OAuth"""
        email = user_info['email']
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type='entrepreneur',  # Tipo por defecto
            is_active=True,
            email_verified=True,  # OAuth emails están verificados
            email_verified_at=datetime.utcnow()
        )
        
        if provider == 'google':
            user.google_id = user_info.get('id')
        elif provider == 'microsoft':
            user.microsoft_id = user_info.get('id')
        
        db.session.add(user)
        db.session.flush()
        
        # Crear perfil de emprendedor por defecto
        entrepreneur = Entrepreneur(
            user_id=user.id,
            business_stage='idea'
        )
        db.session.add(entrepreneur)
        
        return user


class APIKeyResource(Resource):
    """Endpoint para gestión de API Keys"""
    
    @api_auth_required
    def get(self):
        """
        Obtener API keys del usuario
        
        Headers:
            Authorization: Bearer <access_token>
        
        Returns:
            Lista de API keys (sin mostrar el key completo)
        """
        user = get_current_user()
        
        # Solo usuarios con permisos específicos pueden tener API keys
        if not user.can_generate_api_keys():
            raise AuthorizationError("No tiene permisos para generar API keys")
        
        api_keys = user.api_keys
        
        return {
            'api_keys': [
                {
                    'id': key.id,
                    'name': key.name,
                    'key_preview': f"{key.key[:8]}...{key.key[-4:]}",
                    'permissions': key.permissions,
                    'created_at': key.created_at.isoformat(),
                    'last_used': key.last_used.isoformat() if key.last_used else None,
                    'is_active': key.is_active
                }
                for key in api_keys
            ]
        }, 200
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Generar nueva API key
        
        Headers:
            Authorization: Bearer <access_token>
        
        Body:
            name: Nombre descriptivo para la API key
            permissions: Lista de permisos (opcional)
        
        Returns:
            Nueva API key generada
        """
        user = get_current_user()
        
        if not user.can_generate_api_keys():
            raise AuthorizationError("No tiene permisos para generar API keys")
        
        data = request.get_json()
        name = data.get('name', '').strip()
        permissions = data.get('permissions', [])
        
        if not name:
            raise ValidationError("Nombre de API key es requerido")
        
        # Verificar límite de API keys por usuario
        if len(user.api_keys) >= 5:  # Límite de 5 API keys por usuario
            raise BusinessLogicError("Límite de API keys alcanzado (máximo 5)")
        
        # Generar API key
        api_key = secrets.token_urlsafe(32)
        
        # Crear registro de API key
        from app.models.api_key import APIKey
        key_record = APIKey(
            user_id=user.id,
            name=name,
            key=api_key,
            permissions=permissions,
            is_active=True
        )
        
        db.session.add(key_record)
        db.session.commit()
        
        # Log creación de API key
        ActivityLog.log_activity(
            activity_type=ActivityType.API_ACCESS,
            description=f"API key created: {name}",
            user_id=user.id,
            severity=ActivitySeverity.MEDIUM,
            metadata={
                'api_key_name': name,
                'permissions': permissions
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return {
            'id': key_record.id,
            'name': name,
            'api_key': api_key,  # Solo se muestra una vez
            'permissions': permissions,
            'message': 'Guarde esta API key en un lugar seguro. No se mostrará nuevamente.'
        }, 201


class ValidationResource(Resource):
    """Endpoint para validar tokens y sesiones"""
    
    @api_auth_required
    def get(self):
        """
        Validar token actual
        
        Headers:
            Authorization: Bearer <access_token>
        
        Returns:
            Información de validación del token
        """
        user = get_current_user()
        
        return {
            'valid': True,
            'user_id': user.id,
            'email': user.email,
            'user_type': user.user_type,
            'permissions': user.get_permissions(),
            'exp': g.token_exp.isoformat() if hasattr(g, 'token_exp') else None
        }, 200


# Registrar recursos en la API
api.add_resource(LoginResource, '/login')
api.add_resource(RegisterResource, '/register')
api.add_resource(LogoutResource, '/logout')
api.add_resource(RefreshTokenResource, '/refresh')
api.add_resource(EmailVerificationResource, '/verify-email/<string:token>')
api.add_resource(ResendVerificationResource, '/resend-verification')
api.add_resource(ForgotPasswordResource, '/forgot-password')
api.add_resource(ResetPasswordResource, '/reset-password')
api.add_resource(ChangePasswordResource, '/change-password')
api.add_resource(TwoFactorSetupResource, '/2fa/setup')
api.add_resource(TwoFactorDisableResource, '/2fa/disable')
api.add_resource(UserProfileResource, '/me')
api.add_resource(OAuthLoginResource, '/oauth/login')
api.add_resource(APIKeyResource, '/api-keys')
api.add_resource(ValidationResource, '/validate')


# Endpoints adicionales fuera de Flask-RESTful para casos especiales
@auth_bp.route('/health', methods=['GET'])
def auth_health():
    """Health check específico del módulo de auth"""
    return jsonify({
        'status': 'healthy',
        'module': 'auth',
        'endpoints': len(api.resources),
        'timestamp': datetime.utcnow().isoformat()
    })


@auth_bp.route('/providers', methods=['GET'])
def get_oauth_providers():
    """Obtener proveedores OAuth disponibles"""
    providers = {
        'google': {
            'name': 'Google',
            'client_id': current_app.config.get('GOOGLE_CLIENT_ID'),
            'enabled': bool(current_app.config.get('GOOGLE_CLIENT_ID'))
        },
        'microsoft': {
            'name': 'Microsoft',
            'client_id': current_app.config.get('MICROSOFT_CLIENT_ID'),
            'enabled': bool(current_app.config.get('MICROSOFT_CLIENT_ID'))
        }
    }
    
    return jsonify({
        'providers': providers,
        'timestamp': datetime.utcnow().isoformat()
    })


@auth_bp.route('/session/extend', methods=['POST'])
@api_auth_required
def extend_session():
    """Extender sesión actual"""
    user = get_current_user()
    
    # Generar nuevo token con tiempo extendido
    extended_token = LoginResource()._generate_access_token(user)
    
    return jsonify({
        'access_token': extended_token,
        'expires_in': int(AuthConfig.ACCESS_TOKEN_EXPIRES.total_seconds()),
        'message': 'Sesión extendida exitosamente'
    })


# Manejadores de errores específicos del módulo auth
@auth_bp.errorhandler(AuthenticationError)
def handle_auth_error(error):
    """Maneja errores de autenticación específicos"""
    return jsonify({
        'error': 'Authentication Failed',
        'message': str(error),
        'code': 'AUTH_FAILED',
        'timestamp': datetime.utcnow().isoformat()
    }), 401


@auth_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Maneja errores de validación específicos de auth"""
    return jsonify({
        'error': 'Validation Error',
        'message': str(error),
        'code': 'VALIDATION_FAILED',
        'timestamp': datetime.utcnow().isoformat()
    }), 400


# Funciones auxiliares para otros módulos
def get_user_from_token(token: str) -> Optional[User]:
    """
    Obtiene usuario desde un token JWT
    
    Args:
        token: Token JWT
        
    Returns:
        Usuario si el token es válido, None en caso contrario
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=[AuthConfig.JWT_ALGORITHM]
        )
        
        if payload.get('type') != 'access':
            return None
        
        user_id = payload.get('user_id')
        return User.query.filter_by(id=user_id, is_active=True).first()
        
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def generate_api_token(user: User, permissions: List[str] = None) -> str:
    """
    Genera token de API para servicios
    
    Args:
        user: Usuario para el token
        permissions: Permisos específicos
        
    Returns:
        Token de API
    """
    payload = {
        'user_id': user.id,
        'email': user.email,
        'user_type': user.user_type,
        'permissions': permissions or user.get_permissions(),
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=365),  # Token de larga duración
        'type': 'api'
    }
    
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm=AuthConfig.JWT_ALGORITHM
    )


# Exportaciones para otros módulos
__all__ = [
    'auth_bp',
    'AuthConfig',
    'get_user_from_token',
    'generate_api_token'
]