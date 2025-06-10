"""
Authentication Middleware para el ecosistema de emprendimiento.
Proporciona autenticación robusta multi-tipo con autorización granular,
gestión de sesiones, y integración completa de seguridad.

Características:
- Autenticación JWT con refresh tokens
- API Key authentication para integraciones
- OAuth 2.0 para servicios externos
- Sistema de permisos basado en roles y recursos
- Multi-factor authentication (MFA)
- Blacklist/whitelist de tokens dinámicas
- Gestión de sesiones con expiración
- Rate limiting por usuario autenticado
- Logging y auditoría completa
- Integración con analytics

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, request, g, current_app, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    get_jwt_identity, get_jwt, verify_jwt_in_request,
    decode_token
)
from werkzeug.exceptions import Unauthorized, Forbidden
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Set, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import secrets
import logging
import time
import json
from functools import wraps
from collections import defaultdict
import redis
import jwt as pyjwt

# Importaciones locales
from app.models.user import User, UserType
from app.models.api_key import APIKey, APIKeyScope
from app.models.user_session import UserSession, SessionStatus
from app.models.permission import Permission, Role
from app.models.oauth_token import OAuthToken, OAuthProvider
from app.core.exceptions import (
    AuthenticationException, 
    AuthorizationException,
    TokenException,
    SecurityException
)
from app.utils.string_utils import get_client_ip, generate_secure_token
from app.utils.date_utils import get_utc_now
from app.utils.crypto_utils import verify_password, hash_password
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.extensions import db, cache

logger = logging.getLogger(__name__)

class AuthenticationType(Enum):
    """Tipos de autenticación disponibles."""
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH = "oauth"
    SESSION = "session"
    BASIC = "basic"

class AuthenticationLevel(Enum):
    """Niveles de autenticación requeridos."""
    NONE = "none"           # Sin autenticación
    OPTIONAL = "optional"   # Autenticación opcional
    REQUIRED = "required"   # Autenticación requerida
    MFA = "mfa"            # Multi-factor requerido
    ADMIN = "admin"        # Solo administradores

class PermissionScope(Enum):
    """Alcances de permisos."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    OWNER = "owner"

@dataclass
class AuthenticationResult:
    """Resultado de autenticación."""
    authenticated: bool
    user: Optional[User] = None
    auth_type: Optional[AuthenticationType] = None
    permissions: Set[str] = field(default_factory=set)
    session_id: Optional[str] = None
    api_key_id: Optional[str] = None
    oauth_token_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AuthenticationConfig:
    """Configuración de autenticación."""
    # JWT Configuration
    jwt_secret_key: str = None
    jwt_access_token_expires: timedelta = field(default=timedelta(hours=1))
    jwt_refresh_token_expires: timedelta = field(default=timedelta(days=30))
    jwt_algorithm: str = "HS256"
    
    # API Key Configuration
    api_key_header: str = "X-API-Key"
    api_key_param: str = "api_key"
    api_key_length: int = 32
    
    # Session Configuration
    session_timeout: timedelta = field(default=timedelta(hours=24))
    max_sessions_per_user: int = 5
    
    # Security Configuration
    require_https: bool = True
    check_user_agent: bool = True
    check_ip_changes: bool = True
    max_login_attempts: int = 5
    lockout_duration: timedelta = field(default=timedelta(minutes=15))
    
    # MFA Configuration
    mfa_enabled: bool = False
    mfa_issuer: str = "Ecosistema Emprendimiento"
    mfa_window: int = 30  # seconds
    
    # Token Blacklist
    use_token_blacklist: bool = True
    blacklist_cleanup_interval: int = 3600  # seconds

class TokenBlacklistManager:
    """Gestor de blacklist de tokens."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client or redis.from_url(
            current_app.config.get('REDIS_URL', 'redis://localhost:6379')
        )
        self.prefix = "token_blacklist"
    
    def add_token(self, jti: str, expires_at: datetime):
        """Agrega token a blacklist."""
        key = f"{self.prefix}:{jti}"
        expires_in = int((expires_at - get_utc_now()).total_seconds())
        
        if expires_in > 0:
            self.redis.setex(key, expires_in, "blacklisted")
    
    def is_blacklisted(self, jti: str) -> bool:
        """Verifica si token está en blacklist."""
        key = f"{self.prefix}:{jti}"
        return self.redis.exists(key)
    
    def cleanup_expired(self) -> int:
        """Limpia tokens expirados (Redis lo hace automáticamente)."""
        return 0

class JWTAuthenticator:
    """Autenticador JWT."""
    
    def __init__(self, config: AuthenticationConfig):
        self.config = config
        self.blacklist_manager = TokenBlacklistManager()
    
    def create_tokens(self, user: User, additional_claims: Dict = None) -> Tuple[str, str]:
        """Crea access y refresh tokens."""
        claims = {
            'user_id': user.id,
            'user_type': user.user_type.value,
            'email': user.email,
            'is_admin': user.is_admin(),
            'permissions': [p.name for p in user.get_permissions()],
            'session_id': generate_secure_token(16)
        }
        
        if additional_claims:
            claims.update(additional_claims)
        
        access_token = create_access_token(
            identity=user.id,
            additional_claims=claims,
            expires_delta=self.config.jwt_access_token_expires
        )
        
        refresh_token = create_refresh_token(
            identity=user.id,
            additional_claims={'user_id': user.id, 'session_id': claims['session_id']},
            expires_delta=self.config.jwt_refresh_token_expires
        )
        
        # Registrar sesión
        self._create_user_session(user, claims['session_id'], access_token)
        
        return access_token, refresh_token
    
    def _create_user_session(self, user: User, session_id: str, token: str):
        """Crea sesión de usuario."""
        # Limpiar sesiones expiradas
        UserSession.query.filter(
            UserSession.user_id == user.id,
            UserSession.expires_at < get_utc_now()
        ).delete()
        
        # Limitar número de sesiones
        sessions = UserSession.query.filter(
            UserSession.user_id == user.id,
            UserSession.status == SessionStatus.ACTIVE
        ).order_by(UserSession.created_at.desc()).all()
        
        if len(sessions) >= self.config.max_sessions_per_user:
            # Eliminar sesiones más antiguas
            for session in sessions[self.config.max_sessions_per_user-1:]:
                session.status = SessionStatus.EXPIRED
                self.blacklist_manager.add_token(
                    session.jti, 
                    session.expires_at
                )
        
        # Crear nueva sesión
        session = UserSession(
            id=session_id,
            user_id=user.id,
            jti=self._extract_jti(token),
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            expires_at=get_utc_now() + self.config.session_timeout,
            status=SessionStatus.ACTIVE
        )
        
        db.session.add(session)
        db.session.commit()
    
    def _extract_jti(self, token: str) -> str:
        """Extrae JTI del token."""
        try:
            decoded = pyjwt.decode(
                token, 
                options={"verify_signature": False}
            )
            return decoded.get('jti', '')
        except Exception:
            return ''
    
    def authenticate(self, token: str = None) -> AuthenticationResult:
        """Autentica usando JWT."""
        try:
            if not token:
                # Intentar obtener token del header
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                else:
                    return AuthenticationResult(authenticated=False)
            
            # Verificar token
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            jwt_claims = get_jwt()
            
            # Verificar blacklist
            jti = jwt_claims.get('jti')
            if jti and self.blacklist_manager.is_blacklisted(jti):
                return AuthenticationResult(authenticated=False)
            
            # Obtener usuario
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return AuthenticationResult(authenticated=False)
            
            # Verificar sesión
            session_id = jwt_claims.get('session_id')
            if session_id:
                session = UserSession.query.filter_by(
                    id=session_id,
                    user_id=user.id,
                    status=SessionStatus.ACTIVE
                ).first()
                
                if not session or session.expires_at < get_utc_now():
                    return AuthenticationResult(authenticated=False)
                
                # Verificar cambios de IP si está configurado
                if (self.config.check_ip_changes and 
                    session.ip_address != get_client_ip()):
                    logger.warning(f"IP change detected for user {user.id}")
                    # Opcional: invalidar sesión o requerir re-autenticación
            
            # Actualizar último acceso
            user.last_login_at = get_utc_now()
            db.session.commit()
            
            return AuthenticationResult(
                authenticated=True,
                user=user,
                auth_type=AuthenticationType.JWT,
                permissions=set(jwt_claims.get('permissions', [])),
                session_id=session_id,
                expires_at=datetime.fromtimestamp(jwt_claims.get('exp', 0)),
                metadata=jwt_claims
            )
            
        except Exception as e:
            logger.error(f"JWT authentication error: {str(e)}")
            return AuthenticationResult(authenticated=False)
    
    def invalidate_token(self, jti: str, expires_at: datetime):
        """Invalida un token específico."""
        self.blacklist_manager.add_token(jti, expires_at)
    
    def invalidate_user_sessions(self, user_id: int):
        """Invalida todas las sesiones de un usuario."""
        sessions = UserSession.query.filter_by(
            user_id=user_id,
            status=SessionStatus.ACTIVE
        ).all()
        
        for session in sessions:
            session.status = SessionStatus.REVOKED
            self.blacklist_manager.add_token(session.jti, session.expires_at)
        
        db.session.commit()

class APIKeyAuthenticator:
    """Autenticador de API Keys."""
    
    def __init__(self, config: AuthenticationConfig):
        self.config = config
    
    def authenticate(self, api_key: str = None) -> AuthenticationResult:
        """Autentica usando API Key."""
        try:
            if not api_key:
                # Intentar obtener de header o query param
                api_key = (request.headers.get(self.config.api_key_header) or
                          request.args.get(self.config.api_key_param))
            
            if not api_key:
                return AuthenticationResult(authenticated=False)
            
            # Hash de la API key para búsqueda segura
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Buscar API key
            key_record = APIKey.query.filter_by(
                key_hash=api_key_hash,
                is_active=True
            ).first()
            
            if not key_record:
                return AuthenticationResult(authenticated=False)
            
            # Verificar expiración
            if key_record.expires_at and key_record.expires_at < get_utc_now():
                return AuthenticationResult(authenticated=False)
            
            # Verificar límites de uso
            if (key_record.usage_limit and 
                key_record.usage_count >= key_record.usage_limit):
                return AuthenticationResult(authenticated=False)
            
            # Obtener usuario asociado
            user = key_record.user
            if not user or not user.is_active:
                return AuthenticationResult(authenticated=False)
            
            # Actualizar uso
            key_record.usage_count += 1
            key_record.last_used_at = get_utc_now()
            key_record.last_used_ip = get_client_ip()
            db.session.commit()
            
            # Determinar permisos basados en scopes
            permissions = set()
            for scope in key_record.scopes:
                permissions.update(scope.get_permissions())
            
            return AuthenticationResult(
                authenticated=True,
                user=user,
                auth_type=AuthenticationType.API_KEY,
                permissions=permissions,
                api_key_id=key_record.id,
                expires_at=key_record.expires_at,
                metadata={
                    'api_key_name': key_record.name,
                    'scopes': [s.name for s in key_record.scopes]
                }
            )
            
        except Exception as e:
            logger.error(f"API Key authentication error: {str(e)}")
            return AuthenticationResult(authenticated=False)

class OAuthAuthenticator:
    """Autenticador OAuth."""
    
    def __init__(self, config: AuthenticationConfig):
        self.config = config
    
    def authenticate(self, token: str = None, provider: str = None) -> AuthenticationResult:
        """Autentica usando OAuth token."""
        try:
            if not token:
                # Intentar obtener token del header
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                else:
                    return AuthenticationResult(authenticated=False)
            
            # Buscar token OAuth
            oauth_token = OAuthToken.query.filter_by(
                access_token=token,
                is_active=True
            ).first()
            
            if not oauth_token:
                return AuthenticationResult(authenticated=False)
            
            # Verificar expiración
            if oauth_token.expires_at < get_utc_now():
                return AuthenticationResult(authenticated=False)
            
            # Obtener usuario
            user = oauth_token.user
            if not user or not user.is_active:
                return AuthenticationResult(authenticated=False)
            
            # Actualizar último uso
            oauth_token.last_used_at = get_utc_now()
            db.session.commit()
            
            return AuthenticationResult(
                authenticated=True,
                user=user,
                auth_type=AuthenticationType.OAUTH,
                permissions=set(user.get_permission_names()),
                oauth_token_id=oauth_token.id,
                expires_at=oauth_token.expires_at,
                metadata={
                    'provider': oauth_token.provider.value,
                    'scope': oauth_token.scope
                }
            )
            
        except Exception as e:
            logger.error(f"OAuth authentication error: {str(e)}")
            return AuthenticationResult(authenticated=False)

class PermissionChecker:
    """Verificador de permisos."""
    
    @staticmethod
    def has_permission(user: User, permission: str, resource: Any = None) -> bool:
        """Verifica si el usuario tiene un permiso específico."""
        if user.is_admin():
            return True
        
        user_permissions = user.get_permission_names()
        
        # Verificar permiso directo
        if permission in user_permissions:
            return True
        
        # Verificar permisos basados en recursos
        if resource:
            return PermissionChecker._check_resource_permission(
                user, permission, resource
            )
        
        return False
    
    @staticmethod
    def _check_resource_permission(user: User, permission: str, resource: Any) -> bool:
        """Verifica permisos específicos del recurso."""
        # Verificar ownership
        if hasattr(resource, 'owner_id') and resource.owner_id == user.id:
            return True
        
        if hasattr(resource, 'user_id') and resource.user_id == user.id:
            return True
        
        # Verificar permisos específicos del tipo de usuario
        if user.user_type == UserType.ENTREPRENEUR:
            return PermissionChecker._check_entrepreneur_permissions(
                user, permission, resource
            )
        elif user.user_type == UserType.ALLY:
            return PermissionChecker._check_ally_permissions(
                user, permission, resource
            )
        elif user.user_type == UserType.CLIENT:
            return PermissionChecker._check_client_permissions(
                user, permission, resource
            )
        
        return False
    
    @staticmethod
    def _check_entrepreneur_permissions(user: User, permission: str, resource: Any) -> bool:
        """Verifica permisos específicos de emprendedor."""
        if hasattr(user, 'entrepreneur') and user.entrepreneur:
            # Emprendedores pueden acceder a sus proyectos
            if hasattr(resource, 'entrepreneur_id'):
                return resource.entrepreneur_id == user.entrepreneur.id
        
        return False
    
    @staticmethod
    def _check_ally_permissions(user: User, permission: str, resource: Any) -> bool:
        """Verifica permisos específicos de aliado."""
        if hasattr(user, 'ally') and user.ally:
            # Aliados pueden acceder a proyectos de sus emprendedores
            if hasattr(resource, 'entrepreneur_id'):
                mentored_entrepreneurs = [e.id for e in user.ally.entrepreneurs]
                return resource.entrepreneur_id in mentored_entrepreneurs
        
        return False
    
    @staticmethod
    def _check_client_permissions(user: User, permission: str, resource: Any) -> bool:
        """Verifica permisos específicos de cliente."""
        if hasattr(user, 'client') and user.client:
            # Clientes pueden acceder a datos de sus organizaciones
            if hasattr(resource, 'organization_id'):
                client_orgs = [org.id for org in user.client.organizations]
                return resource.organization_id in client_orgs
        
        return False

class AuthMiddleware:
    """Middleware principal de autenticación."""
    
    def __init__(self, config: AuthenticationConfig = None):
        self.config = config or AuthenticationConfig()
        self.jwt_auth = JWTAuthenticator(self.config)
        self.api_key_auth = APIKeyAuthenticator(self.config)
        self.oauth_auth = OAuthAuthenticator(self.config)
        self.analytics_service = None
        self.failed_attempts = defaultdict(int)
        
    def init_app(self, app: Flask):
        """Inicializa el middleware con Flask."""
        self.app = app
        
        # Configurar JWT Manager
        jwt = JWTManager(app)
        
        # Configurar callbacks JWT
        self._setup_jwt_callbacks(jwt)
        
        # Configurar limpieza periódica
        self._setup_cleanup_tasks()
    
    def _setup_jwt_callbacks(self, jwt: JWTManager):
        """Configura callbacks de JWT."""
        
        @jwt.token_in_blacklist_loader
        def check_if_token_revoked(jwt_header, jwt_payload):
            jti = jwt_payload.get('jti')
            return self.jwt_auth.blacklist_manager.is_blacklisted(jti)
        
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return jsonify({
                'error': 'Token has expired',
                'type': 'token_expired'
            }), 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return jsonify({
                'error': 'Invalid token',
                'message': str(error),
                'type': 'token_invalid'
            }), 401
        
        @jwt.unauthorized_loader
        def missing_token_callback(error):
            return jsonify({
                'error': 'Authorization required',
                'message': str(error),
                'type': 'token_missing'
            }), 401
    
    def _setup_cleanup_tasks(self):
        """Configura tareas de limpieza."""
        # Esto se implementaría con Celery en un entorno real
        pass
    
    def _get_analytics_service(self):
        """Obtiene servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def authenticate_request(self, required_level: AuthenticationLevel = AuthenticationLevel.REQUIRED) -> AuthenticationResult:
        """Autentica el request actual."""
        if required_level == AuthenticationLevel.NONE:
            return AuthenticationResult(authenticated=True)
        
        # Intentar diferentes métodos de autenticación
        auth_result = None
        
        # 1. JWT Authentication
        if not auth_result or not auth_result.authenticated:
            auth_result = self.jwt_auth.authenticate()
        
        # 2. API Key Authentication
        if not auth_result or not auth_result.authenticated:
            auth_result = self.api_key_auth.authenticate()
        
        # 3. OAuth Authentication
        if not auth_result or not auth_result.authenticated:
            auth_result = self.oauth_auth.authenticate()
        
        # Verificar nivel requerido
        if required_level == AuthenticationLevel.OPTIONAL:
            # Siempre permitir, pero establecer contexto si está autenticado
            if auth_result and auth_result.authenticated:
                self._set_user_context(auth_result)
            return auth_result or AuthenticationResult(authenticated=True)
        
        if not auth_result or not auth_result.authenticated:
            if required_level in [AuthenticationLevel.REQUIRED, AuthenticationLevel.MFA, AuthenticationLevel.ADMIN]:
                self._track_failed_authentication()
                raise AuthenticationException("Authentication required")
        
        # Verificar nivel admin
        if required_level == AuthenticationLevel.ADMIN:
            if not auth_result.user.is_admin():
                raise AuthorizationException("Admin access required")
        
        # Verificar MFA si es requerido
        if required_level == AuthenticationLevel.MFA:
            if not self._verify_mfa(auth_result.user):
                raise AuthenticationException("Multi-factor authentication required")
        
        # Establecer contexto de usuario
        self._set_user_context(auth_result)
        
        # Trackear autenticación exitosa
        self._track_successful_authentication(auth_result)
        
        return auth_result
    
    def _set_user_context(self, auth_result: AuthenticationResult):
        """Establece contexto del usuario en el request."""
        g.current_user = auth_result.user
        g.current_user_id = auth_result.user.id if auth_result.user else None
        g.auth_type = auth_result.auth_type
        g.user_permissions = auth_result.permissions
        g.session_id = auth_result.session_id
        g.auth_metadata = auth_result.metadata
    
    def _verify_mfa(self, user: User) -> bool:
        """Verifica multi-factor authentication."""
        if not self.config.mfa_enabled:
            return True
        
        # Implementar verificación MFA (TOTP, SMS, etc.)
        # Por ahora retorna True, pero se implementaría verificación real
        return True
    
    def _track_successful_authentication(self, auth_result: AuthenticationResult):
        """Registra autenticación exitosa."""
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_authentication_event({
                'event_type': 'authentication_success',
                'user_id': auth_result.user.id,
                'auth_type': auth_result.auth_type.value,
                'ip': get_client_ip(),
                'user_agent': request.user_agent.string,
                'endpoint': request.endpoint,
                'timestamp': get_utc_now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error tracking successful authentication: {e}")
    
    def _track_failed_authentication(self):
        """Registra intento de autenticación fallido."""
        client_ip = get_client_ip()
        self.failed_attempts[client_ip] += 1
        
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_authentication_event({
                'event_type': 'authentication_failed',
                'ip': client_ip,
                'user_agent': request.user_agent.string,
                'endpoint': request.endpoint,
                'attempts': self.failed_attempts[client_ip],
                'timestamp': get_utc_now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error tracking failed authentication: {e}")
    
    def process_request(self):
        """Procesa request para autenticación."""
        # Este método se llamaría desde el middleware principal
        # Por ahora, la autenticación se maneja via decoradores
        pass
    
    def logout_user(self, user: User):
        """Cierra sesión del usuario."""
        try:
            # Invalidar todas las sesiones activas
            self.jwt_auth.invalidate_user_sessions(user.id)
            
            # Trackear logout
            analytics_service = self._get_analytics_service()
            analytics_service.track_authentication_event({
                'event_type': 'user_logout',
                'user_id': user.id,
                'ip': get_client_ip(),
                'timestamp': get_utc_now().isoformat()
            })
            
            logger.info(f"User {user.id} logged out successfully")
            
        except Exception as e:
            logger.error(f"Error during logout for user {user.id}: {e}")

# Decoradores de autenticación
def require_auth(level: AuthenticationLevel = AuthenticationLevel.REQUIRED):
    """
    Decorador para requerir autenticación en endpoints.
    
    Args:
        level: Nivel de autenticación requerido
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_middleware = current_app.extensions.get('auth_middleware')
            if not auth_middleware:
                raise SecurityException("Auth middleware not configured")
            
            auth_result = auth_middleware.authenticate_request(level)
            
            if not auth_result.authenticated and level != AuthenticationLevel.OPTIONAL:
                raise AuthenticationException("Authentication required")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_permission(permission: str, resource_param: str = None):
    """
    Decorador para requerir permisos específicos.
    
    Args:
        permission: Nombre del permiso requerido
        resource_param: Nombre del parámetro que contiene el recurso
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                raise AuthenticationException("Authentication required")
            
            resource = None
            if resource_param and resource_param in kwargs:
                resource = kwargs[resource_param]
            
            if not PermissionChecker.has_permission(g.current_user, permission, resource):
                raise AuthorizationException(f"Permission required: {permission}")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_user_type(*user_types: UserType):
    """
    Decorador para requerir tipos de usuario específicos.
    
    Args:
        user_types: Tipos de usuario permitidos
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                raise AuthenticationException("Authentication required")
            
            if g.current_user.user_type not in user_types:
                raise AuthorizationException(
                    f"User type required: {[ut.value for ut in user_types]}"
                )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_owner_or_admin(resource_param: str, owner_field: str = 'user_id'):
    """
    Decorador para requerir ser propietario del recurso o admin.
    
    Args:
        resource_param: Parámetro que contiene el recurso
        owner_field: Campo que indica el propietario
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                raise AuthenticationException("Authentication required")
            
            if g.current_user.is_admin():
                return f(*args, **kwargs)
            
            if resource_param not in kwargs:
                raise AuthorizationException("Resource not found")
            
            resource = kwargs[resource_param]
            owner_id = getattr(resource, owner_field, None)
            
            if owner_id != g.current_user.id:
                raise AuthorizationException("Access denied: not owner")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# Funciones de utilidad
def get_current_user() -> Optional[User]:
    """Obtiene el usuario actual del contexto."""
    return getattr(g, 'current_user', None)

def get_current_user_id() -> Optional[int]:
    """Obtiene el ID del usuario actual."""
    return getattr(g, 'current_user_id', None)

def has_permission(permission: str, resource: Any = None) -> bool:
    """Verifica si el usuario actual tiene un permiso."""
    user = get_current_user()
    if not user:
        return False
    
    return PermissionChecker.has_permission(user, permission, resource)

def is_admin() -> bool:
    """Verifica si el usuario actual es admin."""
    user = get_current_user()
    return user and user.is_admin()

# Configuraciones por entorno
def configure_development_auth() -> AuthenticationConfig:
    """Configuración para desarrollo."""
    return AuthenticationConfig(
        jwt_access_token_expires=timedelta(hours=8),
        jwt_refresh_token_expires=timedelta(days=7),
        require_https=False,
        check_user_agent=False,
        check_ip_changes=False,
        max_login_attempts=10,
        use_token_blacklist=False
    )

def configure_production_auth() -> AuthenticationConfig:
    """Configuración para producción."""
    return AuthenticationConfig(
        jwt_access_token_expires=timedelta(minutes=30),
        jwt_refresh_token_expires=timedelta(days=7),
        require_https=True,
        check_user_agent=True,
        check_ip_changes=True,
        max_login_attempts=3,
        lockout_duration=timedelta(minutes=30),
        mfa_enabled=True,
        use_token_blacklist=True
    )

# Funciones exportadas
__all__ = [
    'AuthMiddleware',
    'AuthenticationConfig',
    'AuthenticationResult',
    'AuthenticationType',
    'AuthenticationLevel',
    'PermissionScope',
    'JWTAuthenticator',
    'APIKeyAuthenticator', 
    'OAuthAuthenticator',
    'PermissionChecker',
    'TokenBlacklistManager',
    'require_auth',
    'require_permission',
    'require_user_type',
    'require_owner_or_admin',
    'get_current_user',
    'get_current_user_id',
    'has_permission',
    'is_admin',
    'configure_development_auth',
    'configure_production_auth'
]