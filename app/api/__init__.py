"""
API Package Initialization
=========================

Este módulo inicializa y configura la API REST del sistema de emprendimiento,
incluyendo blueprints, middleware, validación y documentación automática.

Funcionalidades:
- Registro de blueprints versionados
- Configuración de middleware común
- Manejo centralizado de errores
- Documentación automática con OpenAPI/Swagger
- Rate limiting y autenticación
- CORS y headers de seguridad
- Logging y monitoreo
"""

from flask import Blueprint, jsonify, request, g, current_app
from flask_restful import Api
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException, BadRequest, Unauthorized, Forbidden, NotFound, InternalServerError
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import functools
import jwt

from app.extensions import db
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError, 
    ResourceNotFoundError,
    BusinessLogicError,
    RateLimitError
)
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.api.middleware.auth import api_auth_required, get_current_user
from app.api.middleware.rate_limiting import api_rate_limiter
from app.utils.decorators import log_api_access


# Configuración del logger para API
api_logger = logging.getLogger('api')


class APIConfig:
    """Configuración centralizada de la API"""
    
    # Versiones soportadas
    SUPPORTED_VERSIONS = ['v1']
    DEFAULT_VERSION = 'v1'
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = "1000 per hour"
    AUTH_RATE_LIMIT = "100 per hour"
    UPLOAD_RATE_LIMIT = "50 per hour"
    
    # Paginación
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Headers de respuesta
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'X-API-Version': None,  # Se establecerá dinámicamente
        'X-Rate-Limit-Remaining': None,  # Se establecerá dinámicamente
        'X-Response-Time': None  # Se establecerá dinámicamente
    }


def create_api_blueprint() -> Blueprint:
    """
    Crea y configura el blueprint principal de la API
    
    Returns:
        Blueprint configurado para la API
    """
    # Crear blueprint principal
    api_bp = Blueprint('api', __name__, url_prefix='/api')
    
    # Configurar CORS
    CORS(api_bp, 
         origins=current_app.config.get('CORS_ORIGINS', ['http://localhost:3000']),
         methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization', 'X-API-Key', 'X-Requested-With'],
         expose_headers=['X-API-Version', 'X-Rate-Limit-Remaining', 'X-Total-Count'])
    
    # Registrar middleware
    register_middleware(api_bp)
    
    # Registrar manejadores de errores
    register_error_handlers(api_bp)
    
    # Registrar blueprints versionados
    register_versioned_blueprints(api_bp)
    
    # Registrar endpoints de utilidad
    register_utility_endpoints(api_bp)
    
    return api_bp


def register_middleware(api_bp: Blueprint):
    """
    Registra middleware común para toda la API
    
    Args:
        api_bp: Blueprint de la API
    """
    
    @api_bp.before_request
    def before_api_request():
        """Middleware ejecutado antes de cada request de API"""
        # Marcar inicio de tiempo para métricas
        g.start_time = time.time()
        
        # Establecer version de API
        api_version = extract_api_version()
        g.api_version = api_version
        
        # Validar versión de API
        if api_version not in APIConfig.SUPPORTED_VERSIONS:
            return jsonify({
                'error': 'Unsupported API version',
                'supported_versions': APIConfig.SUPPORTED_VERSIONS,
                'message': f'API version {api_version} is not supported'
            }), 400
        
        # Log de acceso a API (solo para endpoints importantes)
        if should_log_request():
            api_logger.info(f"API Request: {request.method} {request.path} - IP: {request.remote_addr}")
        
        # Validar Content-Type para requests con body
        if request.method in ['POST', 'PUT', 'PATCH'] and request.content_length:
            if not request.is_json and 'multipart/form-data' not in request.content_type:
                return jsonify({
                    'error': 'Invalid Content-Type',
                    'message': 'Content-Type must be application/json or multipart/form-data'
                }), 400
    
    @api_bp.after_request
    def after_api_request(response):
        """Middleware ejecutado después de cada response de API"""
        # Calcular tiempo de respuesta
        if hasattr(g, 'start_time'):
            response_time = time.time() - g.start_time
            response.headers['X-Response-Time'] = f"{response_time:.3f}s"
        
        # Agregar headers de seguridad
        for header, value in APIConfig.SECURITY_HEADERS.items():
            if value is not None:
                response.headers[header] = value
        
        # Agregar versión de API
        if hasattr(g, 'api_version'):
            response.headers['X-API-Version'] = g.api_version
        
        # Log de respuestas con errores
        if response.status_code >= 400:
            api_logger.warning(
                f"API Error Response: {request.method} {request.path} - "
                f"Status: {response.status_code} - IP: {request.remote_addr}"
            )
        
        # Registrar actividad para endpoints críticos
        if should_log_activity() and hasattr(g, 'current_user'):
            try:
                log_api_activity(response.status_code)
            except Exception as e:
                api_logger.error(f"Failed to log API activity: {e}")
        
        return response


def register_error_handlers(api_bp: Blueprint):
    """
    Registra manejadores de errores personalizados para la API
    
    Args:
        api_bp: Blueprint de la API
    """
    
    @api_bp.errorhandler(ValidationError)
    def handle_validation_error(error):
        """Maneja errores de validación"""
        return jsonify({
            'error': 'Validation Error',
            'message': str(error),
            'details': getattr(error, 'details', None),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 400
    
    @api_bp.errorhandler(AuthenticationError)
    def handle_authentication_error(error):
        """Maneja errores de autenticación"""
        return jsonify({
            'error': 'Authentication Required',
            'message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 401
    
    @api_bp.errorhandler(AuthorizationError)
    def handle_authorization_error(error):
        """Maneja errores de autorización"""
        return jsonify({
            'error': 'Access Forbidden',
            'message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 403
    
    @api_bp.errorhandler(ResourceNotFoundError)
    def handle_not_found_error(error):
        """Maneja errores de recurso no encontrado"""
        return jsonify({
            'error': 'Resource Not Found',
            'message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 404
    
    @api_bp.errorhandler(BusinessLogicError)
    def handle_business_logic_error(error):
        """Maneja errores de lógica de negocio"""
        return jsonify({
            'error': 'Business Logic Error',
            'message': str(error),
            'details': getattr(error, 'details', None),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 422
    
    @api_bp.errorhandler(RateLimitError)
    def handle_rate_limit_error(error):
        """Maneja errores de rate limiting"""
        return jsonify({
            'error': 'Rate Limit Exceeded',
            'message': str(error),
            'retry_after': getattr(error, 'retry_after', None),
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 429
    
    @api_bp.errorhandler(400)
    def handle_bad_request(error):
        """Maneja requests malformados"""
        return jsonify({
            'error': 'Bad Request',
            'message': 'The request could not be understood by the server',
            'details': str(error.description) if hasattr(error, 'description') else None,
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 400
    
    @api_bp.errorhandler(401)
    def handle_unauthorized(error):
        """Maneja errores de autenticación HTTP"""
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication credentials were not provided or are invalid',
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 401
    
    @api_bp.errorhandler(403)
    def handle_forbidden(error):
        """Maneja errores de acceso prohibido HTTP"""
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 403
    
    @api_bp.errorhandler(404)
    def handle_not_found(error):
        """Maneja recursos no encontrados HTTP"""
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 404
    
    @api_bp.errorhandler(405)
    def handle_method_not_allowed(error):
        """Maneja métodos HTTP no permitidos"""
        return jsonify({
            'error': 'Method Not Allowed',
            'message': f'The {request.method} method is not allowed for this endpoint',
            'allowed_methods': list(error.valid_methods) if hasattr(error, 'valid_methods') else None,
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 405
    
    @api_bp.errorhandler(422)
    def handle_unprocessable_entity(error):
        """Maneja entidades no procesables"""
        return jsonify({
            'error': 'Unprocessable Entity',
            'message': 'The request was well-formed but contains semantic errors',
            'details': str(error.description) if hasattr(error, 'description') else None,
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 422
    
    @api_bp.errorhandler(500)
    def handle_internal_server_error(error):
        """Maneja errores internos del servidor"""
        # Log del error completo para debugging
        api_logger.error(f"Internal Server Error: {error}", exc_info=True)
        
        # En producción, no exponer detalles internos
        if current_app.config.get('ENV') == 'production':
            message = 'An internal server error occurred'
            details = None
        else:
            message = str(error)
            details = str(error.description) if hasattr(error, 'description') else None
        
        return jsonify({
            'error': 'Internal Server Error',
            'message': message,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 500
    
    @api_bp.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Maneja errores no capturados"""
        # Log del error completo
        api_logger.error(f"Unexpected error: {error}", exc_info=True)
        
        # Rollback de transacción si está activa
        try:
            db.session.rollback()
        except:
            pass
        
        return jsonify({
            'error': 'Unexpected Error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }), 500


def register_versioned_blueprints(api_bp: Blueprint):
    """
    Registra los blueprints de diferentes versiones de la API
    
    Args:
        api_bp: Blueprint principal de la API
    """
    # Importar blueprints de v1
    try:
        from app.api.v1 import create_v1_blueprint
        v1_bp = create_v1_blueprint()
        api_bp.register_blueprint(v1_bp, url_prefix='/v1')
        api_logger.info("Registered API v1 blueprint")
    except ImportError as e:
        api_logger.error(f"Failed to import API v1 blueprint: {e}")
    
    # Registrar versiones futuras aquí
    # from app.api.v2 import create_v2_blueprint
    # v2_bp = create_v2_blueprint()
    # api_bp.register_blueprint(v2_bp, url_prefix='/v2')


def register_utility_endpoints(api_bp: Blueprint):
    """
    Registra endpoints de utilidad de la API
    
    Args:
        api_bp: Blueprint de la API
    """
    
    @api_bp.route('/health')
    def health_check():
        """Endpoint de health check"""
        try:
            # Verificar conexión a base de datos
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except Exception as e:
            db_status = 'unhealthy'
            api_logger.error(f"Database health check failed: {e}")
        
        status_code = 200 if db_status == 'healthy' else 503
        
        return jsonify({
            'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': APIConfig.DEFAULT_VERSION,
            'services': {
                'database': db_status,
                'api': 'healthy'
            }
        }), status_code
    
    @api_bp.route('/info')
    def api_info():
        """Información general de la API"""
        return jsonify({
            'name': 'Ecosistema de Emprendimiento API',
            'version': APIConfig.DEFAULT_VERSION,
            'supported_versions': APIConfig.SUPPORTED_VERSIONS,
            'timestamp': datetime.utcnow().isoformat(),
            'documentation': {
                'swagger_ui': '/api/docs',
                'openapi_spec': '/api/openapi.json'
            },
            'rate_limits': {
                'default': APIConfig.DEFAULT_RATE_LIMIT,
                'authenticated': APIConfig.AUTH_RATE_LIMIT
            },
            'pagination': {
                'default_page_size': APIConfig.DEFAULT_PAGE_SIZE,
                'max_page_size': APIConfig.MAX_PAGE_SIZE
            }
        })
    
    @api_bp.route('/docs')
    def api_documentation():
        """Redirect a la documentación Swagger UI"""
        from flask import redirect, url_for
        return redirect('/swagger-ui/')
    
    @api_bp.route('/openapi.json')
    def openapi_spec():
        """Especificación OpenAPI/Swagger"""
        # Aquí se podría generar dinámicamente o servir un archivo estático
        return jsonify({
            'openapi': '3.0.0',
            'info': {
                'title': 'Ecosistema de Emprendimiento API',
                'version': APIConfig.DEFAULT_VERSION,
                'description': 'API REST para la plataforma de emprendimiento'
            },
            'servers': [
                {'url': '/api/v1', 'description': 'API v1'}
            ],
            'paths': {},  # Se completaría con la especificación completa
            'components': {
                'securitySchemes': {
                    'BearerAuth': {
                        'type': 'http',
                        'scheme': 'bearer',
                        'bearerFormat': 'JWT'
                    },
                    'ApiKeyAuth': {
                        'type': 'apiKey',
                        'in': 'header',
                        'name': 'X-API-Key'
                    }
                }
            }
        })


# Funciones auxiliares
def extract_api_version() -> str:
    """
    Extrae la versión de la API del request
    
    Returns:
        Versión de la API (por defecto v1)
    """
    # Intentar extraer de la URL
    path_parts = request.path.strip('/').split('/')
    if len(path_parts) >= 2 and path_parts[1].startswith('v'):
        return path_parts[1]
    
    # Intentar extraer del header
    version_header = request.headers.get('X-API-Version')
    if version_header:
        return version_header
    
    # Valor por defecto
    return APIConfig.DEFAULT_VERSION


def should_log_request() -> bool:
    """
    Determina si se debe registrar el request
    
    Returns:
        True si se debe registrar
    """
    # No registrar health checks y endpoints de utilidad
    skip_paths = ['/api/health', '/api/info', '/api/docs', '/api/openapi.json']
    return request.path not in skip_paths


def should_log_activity() -> bool:
    """
    Determina si se debe registrar la actividad en el log de actividades
    
    Returns:
        True si se debe registrar
    """
    # Solo registrar para endpoints de escritura y críticos
    write_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
    critical_paths = ['/auth/', '/users/', '/projects/', '/mentorship/']
    
    is_write_operation = request.method in write_methods
    is_critical_path = any(path in request.path for path in critical_paths)
    
    return is_write_operation or is_critical_path


def log_api_activity(status_code: int):
    """
    Registra actividad de API en el sistema de auditoría
    
    Args:
        status_code: Código de estado HTTP de la respuesta
    """
    if not hasattr(g, 'current_user') or not g.current_user:
        return
    
    # Determinar tipo de actividad
    if '/auth/' in request.path:
        activity_type = ActivityType.API_ACCESS
        description = f"API Authentication: {request.method} {request.path}"
    elif request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        activity_type = ActivityType.API_ACCESS
        description = f"API Modification: {request.method} {request.path}"
    else:
        activity_type = ActivityType.API_ACCESS
        description = f"API Access: {request.method} {request.path}"
    
    # Determinar severidad basada en status code
    if status_code >= 500:
        severity = ActivitySeverity.HIGH
    elif status_code >= 400:
        severity = ActivitySeverity.MEDIUM
    else:
        severity = ActivitySeverity.LOW
    
    # Registrar actividad
    try:
        ActivityLog.log_activity(
            activity_type=activity_type,
            description=description,
            user_id=g.current_user.id if g.current_user else None,
            severity=severity,
            metadata={
                'method': request.method,
                'path': request.path,
                'status_code': status_code,
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', ''),
                'api_version': g.api_version
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
    except Exception as e:
        api_logger.error(f"Failed to log API activity: {e}")


# Decoradores útiles para endpoints de API
def api_response(func: Callable) -> Callable:
    """
    Decorador para estandarizar respuestas de API
    
    Args:
        func: Función del endpoint
        
    Returns:
        Función decorada con respuesta estandarizada
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            
            # Si ya es una Response, devolverla tal como está
            if hasattr(result, 'status_code'):
                return result
            
            # Si es un tuple (data, status_code)
            if isinstance(result, tuple) and len(result) == 2:
                data, status_code = result
                return jsonify({
                    'success': True,
                    'data': data,
                    'timestamp': datetime.utcnow().isoformat()
                }), status_code
            
            # Si es solo data
            return jsonify({
                'success': True,
                'data': result,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
        except Exception as e:
            api_logger.error(f"API endpoint error: {e}", exc_info=True)
            raise
    
    return wrapper


def paginated_response(query, page: int, per_page: int, **kwargs) -> Dict[str, Any]:
    """
    Crea una respuesta paginada estandarizada
    
    Args:
        query: Query de SQLAlchemy
        page: Número de página
        per_page: Elementos por página
        **kwargs: Argumentos adicionales
        
    Returns:
        Diccionario con datos paginados
    """
    # Validar parámetros de paginación
    page = max(1, page)
    per_page = min(max(1, per_page), APIConfig.MAX_PAGE_SIZE)
    
    # Ejecutar paginación
    paginated = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return {
        'items': [item.to_dict() if hasattr(item, 'to_dict') else item 
                 for item in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next,
            'prev_page': paginated.prev_num if paginated.has_prev else None,
            'next_page': paginated.next_num if paginated.has_next else None
        },
        'meta': kwargs
    }


# Constantes útiles para la API
class HTTPStatus:
    """Códigos de estado HTTP comunes"""
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


class APIHeaders:
    """Headers comunes de la API"""
    CONTENT_TYPE = 'Content-Type'
    AUTHORIZATION = 'Authorization'
    API_KEY = 'X-API-Key'
    API_VERSION = 'X-API-Version'
    REQUEST_ID = 'X-Request-ID'
    RATE_LIMIT_REMAINING = 'X-Rate-Limit-Remaining'
    RATE_LIMIT_RESET = 'X-Rate-Limit-Reset'
    TOTAL_COUNT = 'X-Total-Count'


# Exportaciones principales
__all__ = [
    'create_api_blueprint',
    'APIConfig',
    'api_response',
    'paginated_response',
    'HTTPStatus',
    'APIHeaders',
    'api_logger'
]