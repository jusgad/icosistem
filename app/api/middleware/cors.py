"""
CORS Middleware para el ecosistema de emprendimiento.
Proporciona control avanzado de Cross-Origin Resource Sharing con configuraciones 
dinámicas, seguridad robusta y políticas flexibles por endpoint.

Características:
- Configuración dinámica por endpoint y método
- Validación estricta de orígenes con whitelist/blacklist
- Manejo inteligente de preflight requests
- Configuraciones específicas por tipo de usuario
- Políticas de seguridad configurables
- Integración con métricas y logging
- Soporte para subdominios y wildcards
- Configuración por entorno (dev/staging/prod)

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, request, g, current_app, jsonify
from flask_cors import CORS as FlaskCORS
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.exceptions import Forbidden
from urllib.parse import urlparse
from typing import Optional, Union, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging
import time
from functools import wraps
from collections import defaultdict

# Importaciones locales
from app.core.exceptions import SecurityException, ValidationException
from app.models.user import User, UserType
from app.utils.string_utils import get_client_ip
from app.utils.date_utils import get_utc_now
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class CORSPolicy(Enum):
    """Políticas de CORS predefinidas."""
    STRICT = "strict"           # Muy restrictivo, solo dominios específicos
    MODERATE = "moderate"       # Balanceado, algunos wildcards permitidos
    PERMISSIVE = "permissive"   # Más abierto para desarrollo
    CUSTOM = "custom"           # Configuración completamente personalizada

class CORSSecurityLevel(Enum):
    """Niveles de seguridad CORS."""
    MAXIMUM = "maximum"         # Máxima seguridad
    HIGH = "high"              # Alta seguridad  
    MEDIUM = "medium"          # Seguridad moderada
    LOW = "low"                # Baja seguridad (desarrollo)

@dataclass
class CORSOriginPattern:
    """Patrón de origen para validación."""
    pattern: str
    is_regex: bool = False
    allow_subdomains: bool = False
    secure_only: bool = True
    description: str = ""
    
    def matches(self, origin: str) -> bool:
        """Verifica si un origen coincide con este patrón."""
        if not origin:
            return False
            
        # Verificar HTTPS si es requerido
        if self.secure_only and not origin.startswith('https://'):
            if not (origin.startswith('http://localhost') or 
                   origin.startswith('http://127.0.0.1')):
                return False
        
        if self.is_regex:
            return bool(re.match(self.pattern, origin))
        
        if self.allow_subdomains:
            # Permitir subdominios
            domain = self.pattern.replace('https://', '').replace('http://', '')
            origin_domain = origin.replace('https://', '').replace('http://', '')
            return origin_domain == domain or origin_domain.endswith('.' + domain)
        
        return origin == self.pattern

@dataclass 
class CORSConfiguration:
    """Configuración completa de CORS."""
    # Orígenes permitidos
    allowed_origins: list[CORSOriginPattern] = field(default_factory=list)
    allowed_origin_regex: list[str] = field(default_factory=list)
    
    # Métodos HTTP permitidos
    allowed_methods: set[str] = field(default_factory=lambda: {
        'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD', 'PATCH'
    })
    
    # Headers permitidos
    allowed_headers: set[str] = field(default_factory=lambda: {
        'Accept', 'Authorization', 'Content-Type', 'X-Requested-With',
        'X-CSRF-Token', 'X-Request-ID', 'Cache-Control'
    })
    
    # Headers expuestos al cliente
    exposed_headers: set[str] = field(default_factory=lambda: {
        'X-Total-Count', 'X-Rate-Limit-Limit', 'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset', 'Location', 'Content-Length'
    })
    
    # Configuración de credenciales
    supports_credentials: bool = False
    
    # Configuración de preflight
    preflight_max_age: int = 86400  # 24 horas
    
    # Configuraciones específicas por endpoint
    endpoint_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Configuraciones por método HTTP
    method_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Configuraciones por tipo de usuario
    user_type_configs: dict[UserType, dict[str, Any]] = field(default_factory=dict)
    
    # Lista negra de orígenes
    blocked_origins: set[str] = field(default_factory=set)
    
    # Configuración de seguridad
    security_level: CORSSecurityLevel = CORSSecurityLevel.HIGH
    validate_origin_header: bool = True
    check_referer_header: bool = True
    
    # Configuración de logging
    log_cors_requests: bool = True
    log_blocked_requests: bool = True

class CORSValidator:
    """Validador de orígenes y configuraciones CORS."""
    
    def __init__(self, config: CORSConfiguration):
        self.config = config
        self._compiled_regexes = {}
        self._compile_regex_patterns()
    
    def _compile_regex_patterns(self):
        """Precompila patrones regex para mejor performance."""
        for pattern in self.config.allowed_origin_regex:
            try:
                self._compiled_regexes[pattern] = re.compile(pattern)
            except re.error as e:
                logger.error(f"Patrón regex CORS inválido: {pattern} - {e}")
    
    def is_origin_allowed(self, origin: str, user_type: Optional[UserType] = None) -> bool:
        """Verifica si un origen está permitido."""
        if not origin:
            return False
        
        # Verificar lista negra primero
        if origin in self.config.blocked_origins:
            return False
        
        # Verificar configuración específica por tipo de usuario
        if user_type and user_type in self.config.user_type_configs:
            user_config = self.config.user_type_configs[user_type]
            user_origins = user_config.get('allowed_origins', [])
            if user_origins:
                return any(
                    pattern.matches(origin) if isinstance(pattern, CORSOriginPattern) 
                    else origin == pattern 
                    for pattern in user_origins
                )
        
        # Verificar patrones de origen estándar
        for pattern in self.config.allowed_origins:
            if pattern.matches(origin):
                return True
        
        # Verificar patrones regex
        for regex in self._compiled_regexes.values():
            if regex.match(origin):
                return True
        
        return False
    
    def validate_request_origin(self, origin: str, referer: str = None) -> tuple[bool, str]:
        """Valida el origen de un request con verificaciones adicionales."""
        if not origin:
            return False, "Missing origin header"
        
        # Validar formato de URL
        try:
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid origin format"
        except Exception:
            return False, "Malformed origin URL"
        
        # Verificar origen permitido
        if not self.is_origin_allowed(origin):
            return False, f"Origin not allowed: {origin}"
        
        # Verificar referer si está configurado
        if self.config.check_referer_header and referer:
            if not referer.startswith(origin):
                return False, "Referer mismatch"
        
        return True, "Origin validated"
    
    def get_allowed_methods_for_endpoint(self, endpoint: str) -> set[str]:
        """Obtiene métodos permitidos para un endpoint específico."""
        if endpoint in self.config.endpoint_configs:
            endpoint_methods = self.config.endpoint_configs[endpoint].get('methods')
            if endpoint_methods:
                return set(endpoint_methods)
        
        return self.config.allowed_methods
    
    def get_allowed_headers_for_request(self, method: str, endpoint: str) -> set[str]:
        """Obtiene headers permitidos para un request específico."""
        headers = self.config.allowed_headers.copy()
        
        # Headers específicos por método
        if method in self.config.method_configs:
            method_headers = self.config.method_configs[method].get('headers', [])
            headers.update(method_headers)
        
        # Headers específicos por endpoint
        if endpoint in self.config.endpoint_configs:
            endpoint_headers = self.config.endpoint_configs[endpoint].get('headers', [])
            headers.update(endpoint_headers)
        
        return headers

class CORSMiddleware:
    """Middleware principal de CORS."""
    
    def __init__(self, config: CORSConfiguration = None):
        self.config = config or CORSConfiguration()
        self.validator = CORSValidator(self.config)
        self.analytics_service = None
        self.request_stats = defaultdict(int)
        
    def init_app(self, app: Flask):
        """Inicializa el middleware con Flask."""
        self.app = app
        
        # Registrar manejadores de errores CORS
        app.errorhandler(SecurityException)(self._handle_cors_error)
        
        # Configurar Flask-CORS como fallback si es necesario
        if app.config.get('USE_FLASK_CORS_FALLBACK', False):
            self._init_flask_cors_fallback(app)
    
    def _init_flask_cors_fallback(self, app: Flask):
        """Configura Flask-CORS como fallback."""
        FlaskCORS(app, 
                 origins=self._get_flask_cors_origins(),
                 methods=list(self.config.allowed_methods),
                 allow_headers=list(self.config.allowed_headers),
                 expose_headers=list(self.config.exposed_headers),
                 supports_credentials=self.config.supports_credentials,
                 max_age=self.config.preflight_max_age)
    
    def _get_flask_cors_origins(self) -> list[str]:
        """Convierte configuración a formato Flask-CORS."""
        origins = []
        for pattern in self.config.allowed_origins:
            if not pattern.is_regex and not pattern.allow_subdomains:
                origins.append(pattern.pattern)
        return origins
    
    def _get_user_type(self) -> Optional[UserType]:
        """Obtiene el tipo de usuario actual."""
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                user = User.query.get(user_id)
                return user.user_type if user else None
        except Exception:
            pass
        return None
    
    def _get_analytics_service(self):
        """Obtiene servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def _log_cors_request(self, origin: str, method: str, allowed: bool, reason: str = ""):
        """Registra request CORS para análisis."""
        if not self.config.log_cors_requests:
            return
        
        try:
            log_data = {
                'origin': origin,
                'method': method,
                'endpoint': request.endpoint or request.path,
                'allowed': allowed,
                'reason': reason,
                'ip': get_client_ip(),
                'user_agent': request.user_agent.string,
                'timestamp': get_utc_now().isoformat()
            }
            
            if allowed:
                logger.info(f"CORS request allowed: {origin} -> {method} {request.path}")
            else:
                logger.warning(f"CORS request blocked: {origin} -> {method} {request.path} - {reason}")
                
            # Enviar a analytics
            analytics_service = self._get_analytics_service()
            analytics_service.track_cors_event(log_data)
            
        except Exception as e:
            logger.error(f"Error logging CORS request: {e}")
    
    def _handle_preflight_request(self, origin: str) -> tuple[bool, dict[str, str]]:
        """Maneja request de preflight OPTIONS."""
        headers = {}
        
        # Validar origen
        user_type = self._get_user_type()
        is_valid, reason = self.validator.validate_request_origin(
            origin, 
            request.headers.get('Referer')
        )
        
        if not is_valid:
            self._log_cors_request(origin, 'OPTIONS', False, reason)
            return False, {}
        
        # Headers de preflight
        headers['Access-Control-Allow-Origin'] = origin
        
        # Métodos permitidos
        allowed_methods = self.validator.get_allowed_methods_for_endpoint(
            request.endpoint or request.path
        )
        headers['Access-Control-Allow-Methods'] = ', '.join(sorted(allowed_methods))
        
        # Headers permitidos
        requested_headers = request.headers.get('Access-Control-Request-Headers', '')
        if requested_headers:
            requested_set = {h.strip() for h in requested_headers.split(',')}
            allowed_headers = self.validator.get_allowed_headers_for_request(
                'OPTIONS',
                request.endpoint or request.path
            )
            
            # Verificar que todos los headers solicitados están permitidos
            if requested_set.issubset(allowed_headers):
                headers['Access-Control-Allow-Headers'] = requested_headers
            else:
                forbidden_headers = requested_set - allowed_headers
                self._log_cors_request(
                    origin, 'OPTIONS', False, 
                    f"Forbidden headers: {forbidden_headers}"
                )
                return False, {}
        
        # Credenciales
        if self.config.supports_credentials:
            headers['Access-Control-Allow-Credentials'] = 'true'
        
        # Max age para preflight
        headers['Access-Control-Max-Age'] = str(self.config.preflight_max_age)
        
        # Headers adicionales de seguridad
        headers['Vary'] = 'Origin, Access-Control-Request-Method, Access-Control-Request-Headers'
        
        self._log_cors_request(origin, 'OPTIONS', True, "Preflight allowed")
        return True, headers
    
    def _handle_actual_request(self, origin: str) -> tuple[bool, dict[str, str]]:
        """Maneja request real (no preflight)."""
        headers = {}
        
        # Validar origen
        user_type = self._get_user_type()
        if not self.validator.is_origin_allowed(origin, user_type):
            self._log_cors_request(origin, request.method, False, "Origin not allowed")
            return False, {}
        
        # Validar método
        allowed_methods = self.validator.get_allowed_methods_for_endpoint(
            request.endpoint or request.path
        )
        if request.method not in allowed_methods:
            self._log_cors_request(
                origin, request.method, False, 
                f"Method not allowed: {request.method}"
            )
            return False, {}
        
        # Headers de respuesta
        headers['Access-Control-Allow-Origin'] = origin
        
        # Headers expuestos
        if self.config.exposed_headers:
            headers['Access-Control-Expose-Headers'] = ', '.join(
                sorted(self.config.exposed_headers)
            )
        
        # Credenciales
        if self.config.supports_credentials:
            headers['Access-Control-Allow-Credentials'] = 'true'
        
        # Vary header para caching
        headers['Vary'] = 'Origin'
        
        self._log_cors_request(origin, request.method, True, "Request allowed")
        return True, headers
    
    def process_request(self):
        """Procesa request entrante para CORS."""
        origin = request.headers.get('Origin')
        
        # Si no hay Origin header, no es un request CORS
        if not origin:
            return
        
        # Verificar si el origen está bloqueado
        if origin in self.config.blocked_origins:
            self._log_cors_request(origin, request.method, False, "Origin blocked")
            raise SecurityException(f"Origin blocked: {origin}")
        
        # Manejar preflight request
        if request.method == 'OPTIONS':
            allowed, headers = self._handle_preflight_request(origin)
            
            if not allowed:
                raise SecurityException("CORS preflight request denied")
            
            # Crear respuesta preflight
            response = jsonify({'status': 'preflight_ok'})
            for key, value in headers.items():
                response.headers[key] = value
            
            return response
        
        # Manejar request actual
        allowed, headers = self._handle_actual_request(origin)
        
        if not allowed:
            raise SecurityException("CORS request denied")
        
        # Guardar headers para process_response
        g.cors_headers = headers
        
        # Actualizar estadísticas
        self.request_stats[f"{origin}:{request.method}"] += 1
    
    def process_response(self, response):
        """Procesa response para agregar headers CORS."""
        # Agregar headers CORS si están disponibles
        if hasattr(g, 'cors_headers'):
            for key, value in g.cors_headers.items():
                response.headers[key] = value
        
        return response
    
    def _handle_cors_error(self, error):
        """Maneja errores de CORS."""
        return jsonify({
            'error': 'CORS Error',
            'message': str(error),
            'type': 'cors_error'
        }), 403

class CustomCORS:
    """Clase de utilidad para configuraciones CORS específicas."""
    
    @staticmethod
    def create_development_config() -> CORSConfiguration:
        """Configuración permisiva para desarrollo."""
        return CORSConfiguration(
            allowed_origins=[
                CORSOriginPattern("http://localhost:3000", secure_only=False),
                CORSOriginPattern("http://localhost:8080", secure_only=False),
                CORSOriginPattern("http://127.0.0.1:3000", secure_only=False),
                CORSOriginPattern("http://127.0.0.1:8080", secure_only=False),
            ],
            supports_credentials=True,
            security_level=CORSSecurityLevel.LOW,
            validate_origin_header=False,
            check_referer_header=False,
            log_cors_requests=True
        )
    
    @staticmethod
    def create_production_config(allowed_domains: list[str]) -> CORSConfiguration:
        """Configuración estricta para producción."""
        origins = []
        for domain in allowed_domains:
            # Agregar versión HTTPS
            origins.append(CORSOriginPattern(
                f"https://{domain}",
                secure_only=True,
                allow_subdomains=True
            ))
            # Agregar versión con www
            if not domain.startswith('www.'):
                origins.append(CORSOriginPattern(
                    f"https://www.{domain}",
                    secure_only=True
                ))
        
        return CORSConfiguration(
            allowed_origins=origins,
            allowed_methods={'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'},
            supports_credentials=True,
            security_level=CORSSecurityLevel.MAXIMUM,
            validate_origin_header=True,
            check_referer_header=True,
            preflight_max_age=3600,  # 1 hora
            log_cors_requests=True,
            log_blocked_requests=True
        )
    
    @staticmethod
    def create_api_only_config(api_domains: list[str]) -> CORSConfiguration:
        """Configuración específica para APIs."""
        origins = [
            CORSOriginPattern(domain, secure_only=True)
            for domain in api_domains
        ]
        
        return CORSConfiguration(
            allowed_origins=origins,
            allowed_methods={'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'},
            allowed_headers={
                'Accept', 'Authorization', 'Content-Type', 
                'X-Requested-With', 'X-API-Key', 'X-Client-Version'
            },
            exposed_headers={
                'X-Total-Count', 'X-Rate-Limit-Limit', 
                'X-Rate-Limit-Remaining', 'X-API-Version'
            },
            supports_credentials=False,  # APIs típicamente no usan cookies
            security_level=CORSSecurityLevel.HIGH,
            preflight_max_age=86400  # 24 horas
        )
    
    @staticmethod
    def create_webhook_config() -> CORSConfiguration:
        """Configuración para webhooks (muy permisiva)."""
        return CORSConfiguration(
            allowed_origins=[
                CORSOriginPattern(".*", is_regex=True, secure_only=False)
            ],
            allowed_methods={'GET', 'POST', 'OPTIONS'},
            supports_credentials=False,
            security_level=CORSSecurityLevel.LOW,
            validate_origin_header=False,
            log_cors_requests=False  # Webhooks pueden generar mucho ruido
        )

# Configuraciones específicas por entorno
def configure_development_cors(app: Flask) -> CORSMiddleware:
    """Configura CORS para desarrollo."""
    config = CustomCORS.create_development_config()
    middleware = CORSMiddleware(config)
    middleware.init_app(app)
    return middleware

def configure_staging_cors(app: Flask, staging_domains: list[str]) -> CORSMiddleware:
    """Configura CORS para staging."""
    config = CustomCORS.create_production_config(staging_domains)
    config.security_level = CORSSecurityLevel.HIGH
    config.log_cors_requests = True
    
    middleware = CORSMiddleware(config)
    middleware.init_app(app)
    return middleware

def configure_production_cors(app: Flask, production_domains: list[str]) -> CORSMiddleware:
    """Configura CORS para producción."""
    config = CustomCORS.create_production_config(production_domains)
    
    # Configuraciones específicas por tipo de usuario
    config.user_type_configs = {
        UserType.ADMIN: {
            'allowed_origins': [
                CORSOriginPattern("https://admin.tudominio.com", secure_only=True)
            ]
        },
        UserType.ENTREPRENEUR: {
            'allowed_origins': [
                CORSOriginPattern("https://app.tudominio.com", secure_only=True)
            ]
        },
        UserType.ALLY: {
            'allowed_origins': [
                CORSOriginPattern("https://mentors.tudominio.com", secure_only=True)
            ]
        }
    }
    
    # Configuraciones específicas por endpoint
    config.endpoint_configs = {
        '/api/v1/auth/login': {
            'methods': ['POST', 'OPTIONS'],
            'headers': ['Content-Type', 'Authorization']
        },
        '/api/v1/webhooks/*': {
            'methods': ['POST', 'OPTIONS'],
            'headers': ['Content-Type', 'X-Webhook-Signature']
        }
    }
    
    middleware = CORSMiddleware(config)
    middleware.init_app(app)
    return middleware

# Decorador para configuraciones CORS específicas
def cors_config(origins: list[str] = None, methods: list[str] = None, 
                headers: list[str] = None, credentials: bool = None):
    """
    Decorador para aplicar configuración CORS específica a endpoints.
    
    Args:
        origins: Lista de orígenes permitidos
        methods: Lista de métodos HTTP permitidos
        headers: Lista de headers permitidos
        credentials: Si soporta credenciales
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Esta funcionalidad se implementaría integrando con el middleware
            # Por ahora, solo ejecutamos la función original
            return f(*args, **kwargs)
        
        # Marcar función con metadatos CORS
        f._cors_origins = origins or []
        f._cors_methods = methods or []
        f._cors_headers = headers or []
        f._cors_credentials = credentials
        
        return decorated_function
    return decorator

# Funciones de utilidad para gestión de configuración
def add_cors_origin(middleware: CORSMiddleware, origin: str, 
                   allow_subdomains: bool = False, secure_only: bool = True):
    """Agrega un origen permitido dinámicamente."""
    pattern = CORSOriginPattern(
        pattern=origin,
        allow_subdomains=allow_subdomains,
        secure_only=secure_only
    )
    middleware.config.allowed_origins.append(pattern)
    middleware.validator = CORSValidator(middleware.config)

def block_cors_origin(middleware: CORSMiddleware, origin: str):
    """Bloquea un origen específico."""
    middleware.config.blocked_origins.add(origin)

def get_cors_stats(middleware: CORSMiddleware) -> dict[str, Any]:
    """Obtiene estadísticas de requests CORS."""
    return {
        'total_requests': sum(middleware.request_stats.values()),
        'unique_origins': len(middleware.request_stats),
        'top_origins': dict(
            sorted(middleware.request_stats.items(), 
                  key=lambda x: x[1], reverse=True)[:10]
        ),
        'blocked_origins': list(middleware.config.blocked_origins),
        'allowed_patterns': len(middleware.config.allowed_origins)
    }

# Funciones exportadas
__all__ = [
    'CORSMiddleware',
    'CORSConfiguration', 
    'CORSOriginPattern',
    'CORSPolicy',
    'CORSSecurityLevel',
    'CustomCORS',
    'configure_development_cors',
    'configure_staging_cors', 
    'configure_production_cors',
    'cors_config',
    'add_cors_origin',
    'block_cors_origin',
    'get_cors_stats'
]