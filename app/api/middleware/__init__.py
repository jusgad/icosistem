"""
Middleware package para el ecosistema de emprendimiento.
Coordina y configura todos los middlewares de la API REST.

Este módulo proporciona:
- Configuración centralizada de middlewares
- Registro automático de middlewares en Flask
- Utilidades comunes para todos los middlewares
- Sistema de métricas y logging unificado
- Manejo de excepciones a nivel de middleware

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, request, g, current_app
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union
import time
import json
import logging
import uuid
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum

# Importaciones locales de middlewares específicos
from .auth import AuthMiddleware, JWTAuthMiddleware, APIKeyMiddleware
from .cors import CORSMiddleware, CustomCORS
from .rate_limiting import (
    RateLimitMiddleware, 
    AdaptiveRateLimiter,
    IPBasedLimiter,
    UserBasedLimiter
)

# Utilidades y excepciones
from app.core.exceptions import (
    ValidationException,
    AuthorizationException,
    RateLimitException,
    SecurityException
)
from app.utils.string_utils import sanitize_input, mask_sensitive_data
from app.utils.date_utils import get_utc_now
from app.services.analytics_service import AnalyticsService

# Configuración de logging
logger = logging.getLogger(__name__)

class MiddlewareType(Enum):
    """Tipos de middleware disponibles."""
    SECURITY = "security"
    AUTH = "authentication"
    CORS = "cors"
    RATE_LIMIT = "rate_limiting"
    LOGGING = "logging"
    COMPRESSION = "compression"
    CACHING = "caching"
    METRICS = "metrics"
    VALIDATION = "validation"
    ERROR_HANDLING = "error_handling"

class MiddlewarePriority(Enum):
    """Prioridades de ejecución de middlewares."""
    HIGHEST = 10
    HIGH = 20
    NORMAL = 30
    LOW = 40
    LOWEST = 50

@dataclass
class MiddlewareConfig:
    """Configuración base para middlewares."""
    enabled: bool = True
    priority: MiddlewarePriority = MiddlewarePriority.NORMAL
    environments: List[str] = None
    exclude_paths: List[str] = None
    include_paths: List[str] = None
    config: Dict[str, Any] = None

@dataclass
class RequestMetrics:
    """Métricas de request para análisis."""
    request_id: str
    method: str
    path: str
    user_agent: str
    ip_address: str
    user_id: Optional[int]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    errors: List[str] = None

class MiddlewareRegistry:
    """Registro centralizado de middlewares."""
    
    def __init__(self):
        self.middlewares: Dict[str, Dict] = {}
        self.execution_order: List[str] = []
        self.metrics: Dict[str, Any] = {}
        
    def register(
        self, 
        name: str, 
        middleware_class: type, 
        config: MiddlewareConfig,
        middleware_type: MiddlewareType
    ):
        """Registra un middleware en el sistema."""
        self.middlewares[name] = {
            'class': middleware_class,
            'config': config,
            'type': middleware_type,
            'instance': None
        }
        
        # Actualizar orden de ejecución basado en prioridad
        self._update_execution_order()
        
    def _update_execution_order(self):
        """Actualiza el orden de ejecución basado en prioridades."""
        sorted_middlewares = sorted(
            self.middlewares.items(),
            key=lambda x: x[1]['config'].priority.value
        )
        self.execution_order = [name for name, _ in sorted_middlewares]
        
    def get_middleware(self, name: str):
        """Obtiene una instancia de middleware."""
        if name not in self.middlewares:
            return None
            
        middleware_info = self.middlewares[name]
        if middleware_info['instance'] is None:
            middleware_info['instance'] = middleware_info['class'](
                middleware_info['config']
            )
            
        return middleware_info['instance']
    
    def list_enabled(self, environment: str = None) -> List[str]:
        """Lista middlewares habilitados para un entorno."""
        enabled = []
        for name, info in self.middlewares.items():
            config = info['config']
            if not config.enabled:
                continue
                
            if environment and config.environments:
                if environment not in config.environments:
                    continue
                    
            enabled.append(name)
            
        return enabled

# Instancia global del registro
middleware_registry = MiddlewareRegistry()

class SecurityMiddleware:
    """Middleware de seguridad general."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'",
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
        }
        
    def process_request(self):
        """Procesa request entrante."""
        # Validar tamaño del request
        if request.content_length:
            max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
            if request.content_length > max_size:
                raise SecurityException("Request demasiado grande")
        
        # Validar headers sospechosos
        suspicious_headers = ['X-Forwarded-Host', 'X-Originating-IP']
        for header in suspicious_headers:
            if header in request.headers:
                logger.warning(f"Header sospechoso detectado: {header}")
        
        # Sanitizar query parameters
        if request.args:
            for key, value in request.args.items():
                sanitized = sanitize_input(value)
                if sanitized != value:
                    logger.warning(f"Query parameter sanitizado: {key}")
    
    def process_response(self, response):
        """Procesa response saliente."""
        # Agregar headers de seguridad
        for header, value in self.security_headers.items():
            response.headers[header] = value
            
        # Remover headers sensibles
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        
        return response

class LoggingMiddleware:
    """Middleware de logging y auditoría."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.exclude_paths = config.exclude_paths or ['/health', '/metrics']
        
    def process_request(self):
        """Registra información del request."""
        if request.path in self.exclude_paths:
            return
            
        g.request_start_time = time.time()
        g.request_id = str(uuid.uuid4())
        
        # Log básico del request
        logger.info(
            f"REQUEST {g.request_id}: {request.method} {request.path} "
            f"from {request.remote_addr} [{request.user_agent.string[:100]}]"
        )
        
        # Log de payload si es necesario (sin datos sensibles)
        if request.is_json and current_app.debug:
            payload = mask_sensitive_data(request.get_json() or {})
            logger.debug(f"REQUEST {g.request_id} payload: {json.dumps(payload)}")
    
    def process_response(self, response):
        """Registra información del response."""
        if request.path in self.exclude_paths:
            return response
            
        duration = (time.time() - g.get('request_start_time', time.time())) * 1000
        
        logger.info(
            f"RESPONSE {g.get('request_id', 'unknown')}: "
            f"{response.status_code} in {duration:.2f}ms "
            f"({response.content_length or 0} bytes)"
        )
        
        # Log de errores detallado
        if response.status_code >= 400:
            logger.warning(
                f"ERROR RESPONSE {g.get('request_id', 'unknown')}: "
                f"Status {response.status_code} for {request.method} {request.path}"
            )
            
        return response

class CompressionMiddleware:
    """Middleware de compresión de responses."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.min_size = config.config.get('min_size', 1024) if config.config else 1024
        self.compressible_types = [
            'application/json',
            'application/javascript',
            'text/css',
            'text/html',
            'text/plain'
        ]
    
    def should_compress(self, response) -> bool:
        """Determina si el response debe ser comprimido."""
        if not response.data or len(response.data) < self.min_size:
            return False
            
        content_type = response.headers.get('Content-Type', '')
        return any(ct in content_type for ct in self.compressible_types)
    
    def process_response(self, response):
        """Comprime el response si es necesario."""
        if not self.should_compress(response):
            return response
            
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if 'gzip' in accept_encoding:
            try:
                import gzip
                compressed_data = gzip.compress(response.data)
                
                if len(compressed_data) < len(response.data):
                    response.data = compressed_data
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed_data)
                    response.headers['Vary'] = 'Accept-Encoding'
                    
            except Exception as e:
                logger.error(f"Error comprimiendo response: {str(e)}")
                
        return response

class MetricsMiddleware:
    """Middleware de métricas y monitoreo."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.analytics_service = None
        
    def _get_analytics_service(self):
        """Obtiene el servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def process_request(self):
        """Inicia el tracking de métricas."""
        g.metrics = RequestMetrics(
            request_id=g.get('request_id', str(uuid.uuid4())),
            method=request.method,
            path=request.path,
            user_agent=request.user_agent.string,
            ip_address=request.remote_addr,
            user_id=g.get('current_user_id'),
            start_time=get_utc_now()
        )
    
    def process_response(self, response):
        """Finaliza el tracking y envía métricas."""
        if not hasattr(g, 'metrics'):
            return response
            
        g.metrics.end_time = get_utc_now()
        g.metrics.duration_ms = (
            g.metrics.end_time - g.metrics.start_time
        ).total_seconds() * 1000
        g.metrics.status_code = response.status_code
        g.metrics.response_size = response.content_length
        
        # Enviar métricas de forma asíncrona
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_request_metrics(asdict(g.metrics))
        except Exception as e:
            logger.error(f"Error enviando métricas: {str(e)}")
            
        return response

class ValidationMiddleware:
    """Middleware de validación de requests."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.max_json_size = config.config.get('max_json_size', 1024 * 1024) if config.config else 1024 * 1024
        
    def process_request(self):
        """Valida el request entrante."""
        # Validar Content-Type para requests con payload
        if request.method in ['POST', 'PUT', 'PATCH'] and request.data:
            content_type = request.headers.get('Content-Type', '')
            
            if request.is_json:
                # Validar tamaño del JSON
                if len(request.data) > self.max_json_size:
                    raise ValidationException("JSON demasiado grande")
                    
                # Validar que sea JSON válido
                try:
                    request.get_json(force=True)
                except Exception:
                    raise ValidationException("JSON inválido")
            
            elif not content_type:
                raise ValidationException("Content-Type requerido")
        
        # Validar parámetros de query
        for key, value in request.args.items():
            if len(key) > 100 or len(value) > 1000:
                raise ValidationException(f"Parámetro demasiado largo: {key}")

class ErrorHandlingMiddleware:
    """Middleware de manejo de errores."""
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        
    def handle_exception(self, error):
        """Maneja excepciones de forma centralizada."""
        error_id = str(uuid.uuid4())
        
        # Log del error
        logger.error(
            f"ERROR {error_id}: {type(error).__name__}: {str(error)} "
            f"in {request.method} {request.path}",
            exc_info=True
        )
        
        # Respuesta según tipo de error
        if isinstance(error, ValidationException):
            return {
                'error': str(error),
                'error_id': error_id,
                'type': 'validation_error'
            }, 400
        elif isinstance(error, AuthorizationException):
            return {
                'error': 'No autorizado',
                'error_id': error_id,
                'type': 'authorization_error'
            }, 403
        elif isinstance(error, RateLimitException):
            return {
                'error': 'Límite de rate excedido',
                'error_id': error_id,
                'type': 'rate_limit_error'
            }, 429
        elif isinstance(error, HTTPException):
            return {
                'error': error.description,
                'error_id': error_id,
                'type': 'http_error'
            }, error.code
        else:
            # Error interno del servidor
            return {
                'error': 'Error interno del servidor',
                'error_id': error_id,
                'type': 'internal_error'
            }, 500

def create_middleware_pipeline(app: Flask, config: Dict[str, Any] = None) -> None:
    """
    Crea y configura el pipeline completo de middlewares.
    
    Args:
        app: Instancia de Flask
        config: Configuración específica de middlewares
    """
    config = config or {}
    environment = app.config.get('ENVIRONMENT', 'development')
    
    # Registrar middlewares disponibles
    _register_default_middlewares(config, environment)
    
    # Configurar middlewares habilitados
    enabled_middlewares = middleware_registry.list_enabled(environment)
    
    logger.info(f"Configurando middlewares para entorno {environment}: {enabled_middlewares}")
    
    # Configurar CORS
    if 'cors' in enabled_middlewares:
        cors_middleware = middleware_registry.get_middleware('cors')
        cors_middleware.init_app(app)
    
    # Configurar Rate Limiting
    if 'rate_limiting' in enabled_middlewares:
        rate_limit_middleware = middleware_registry.get_middleware('rate_limiting')
        rate_limit_middleware.init_app(app)
    
    # Configurar middlewares de request/response
    @app.before_request
    def before_request_handler():
        """Maneja todos los middlewares before_request."""
        for name in middleware_registry.execution_order:
            if name not in enabled_middlewares:
                continue
                
            middleware = middleware_registry.get_middleware(name)
            if hasattr(middleware, 'process_request'):
                try:
                    result = middleware.process_request()
                    if result:  # Si retorna algo, es una respuesta temprana
                        return result
                except Exception as e:
                    error_middleware = middleware_registry.get_middleware('error_handling')
                    if error_middleware:
                        return error_middleware.handle_exception(e)
                    raise
    
    @app.after_request
    def after_request_handler(response):
        """Maneja todos los middlewares after_request."""
        for name in reversed(middleware_registry.execution_order):
            if name not in enabled_middlewares:
                continue
                
            middleware = middleware_registry.get_middleware(name)
            if hasattr(middleware, 'process_response'):
                try:
                    response = middleware.process_response(response)
                except Exception as e:
                    logger.error(f"Error en middleware {name}: {str(e)}")
                    
        return response
    
    @app.errorhandler(Exception)
    def global_error_handler(error):
        """Manejador global de errores."""
        error_middleware = middleware_registry.get_middleware('error_handling')
        if error_middleware:
            return error_middleware.handle_exception(error)
        
        # Fallback básico
        logger.error(f"Error no manejado: {str(error)}", exc_info=True)
        return {'error': 'Error interno del servidor'}, 500

def _register_default_middlewares(config: Dict[str, Any], environment: str):
    """Registra los middlewares por defecto del sistema."""
    
    # Security Middleware
    middleware_registry.register(
        'security',
        SecurityMiddleware,
        MiddlewareConfig(
            enabled=config.get('security', {}).get('enabled', True),
            priority=MiddlewarePriority.HIGHEST,
            environments=['production', 'staging'],
            config=config.get('security', {})
        ),
        MiddlewareType.SECURITY
    )
    
    # Logging Middleware
    middleware_registry.register(
        'logging',
        LoggingMiddleware,
        MiddlewareConfig(
            enabled=config.get('logging', {}).get('enabled', True),
            priority=MiddlewarePriority.HIGH,
            exclude_paths=['/health', '/metrics', '/static'],
            config=config.get('logging', {})
        ),
        MiddlewareType.LOGGING
    )
    
    # CORS Middleware
    middleware_registry.register(
        'cors',
        CORSMiddleware,
        MiddlewareConfig(
            enabled=config.get('cors', {}).get('enabled', True),
            priority=MiddlewarePriority.HIGH,
            config=config.get('cors', {})
        ),
        MiddlewareType.CORS
    )
    
    # Rate Limiting Middleware
    middleware_registry.register(
        'rate_limiting',
        RateLimitMiddleware,
        MiddlewareConfig(
            enabled=config.get('rate_limiting', {}).get('enabled', True),
            priority=MiddlewarePriority.HIGH,
            config=config.get('rate_limiting', {})
        ),
        MiddlewareType.RATE_LIMIT
    )
    
    # Validation Middleware
    middleware_registry.register(
        'validation',
        ValidationMiddleware,
        MiddlewareConfig(
            enabled=config.get('validation', {}).get('enabled', True),
            priority=MiddlewarePriority.NORMAL,
            config=config.get('validation', {})
        ),
        MiddlewareType.VALIDATION
    )
    
    # Compression Middleware
    middleware_registry.register(
        'compression',
        CompressionMiddleware,
        MiddlewareConfig(
            enabled=config.get('compression', {}).get('enabled', environment == 'production'),
            priority=MiddlewarePriority.LOW,
            config=config.get('compression', {})
        ),
        MiddlewareType.COMPRESSION
    )
    
    # Metrics Middleware
    middleware_registry.register(
        'metrics',
        MetricsMiddleware,
        MiddlewareConfig(
            enabled=config.get('metrics', {}).get('enabled', True),
            priority=MiddlewarePriority.NORMAL,
            exclude_paths=['/health', '/metrics'],
            config=config.get('metrics', {})
        ),
        MiddlewareType.METRICS
    )
    
    # Error Handling Middleware
    middleware_registry.register(
        'error_handling',
        ErrorHandlingMiddleware,
        MiddlewareConfig(
            enabled=True,  # Siempre habilitado
            priority=MiddlewarePriority.LOWEST,
            config=config.get('error_handling', {})
        ),
        MiddlewareType.ERROR_HANDLING
    )

def get_middleware_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de los middlewares."""
    return {
        'total_registered': len(middleware_registry.middlewares),
        'enabled_count': len(middleware_registry.list_enabled()),
        'execution_order': middleware_registry.execution_order,
        'metrics': middleware_registry.metrics
    }

def configure_development_middlewares(app: Flask):
    """Configuración específica para desarrollo."""
    config = {
        'cors': {
            'enabled': True,
            'origins': ['http://localhost:3000', 'http://localhost:8080'],
            'credentials': True
        },
        'security': {
            'enabled': False  # Relajar seguridad en desarrollo
        },
        'compression': {
            'enabled': False  # No comprimir en desarrollo
        }
    }
    
    create_middleware_pipeline(app, config)

def configure_production_middlewares(app: Flask):
    """Configuración específica para producción."""
    config = {
        'cors': {
            'enabled': True,
            'origins': app.config.get('ALLOWED_ORIGINS', []),
            'credentials': True
        },
        'security': {
            'enabled': True
        },
        'compression': {
            'enabled': True,
            'min_size': 1024
        },
        'rate_limiting': {
            'enabled': True,
            'default_limits': ['1000/hour', '100/minute']
        }
    }
    
    create_middleware_pipeline(app, config)

# Funciones de utilidad exportadas
__all__ = [
    'MiddlewareRegistry',
    'MiddlewareConfig',
    'MiddlewareType',
    'MiddlewarePriority',
    'RequestMetrics',
    'create_middleware_pipeline',
    'configure_development_middlewares',
    'configure_production_middlewares',
    'get_middleware_stats',
    'middleware_registry',
    'SecurityMiddleware',
    'LoggingMiddleware',
    'CompressionMiddleware',
    'MetricsMiddleware',
    'ValidationMiddleware',
    'ErrorHandlingMiddleware'
]