"""
API moderna v2 usando Flask-RESTX con documentación OpenAPI automática.
"""

from flask import Blueprint
from flask_restx import Api

# Crear blueprint de API v2
api_v2_bp = Blueprint('api_v2', __name__, url_prefix='/api/v2')

# Crear instancia de Flask-RESTX API
api = Api(
    api_v2_bp,
    version='2.0',
    title='Ecosistema Emprendimiento API',
    description='''
    API REST moderna para la Plataforma del Ecosistema de Emprendimiento.
    
    ## Características
    - Autenticación moderna con JWT
    - Gestión integral de usuarios
    - Seguimiento de proyectos y mentoría
    - Analíticas en tiempo real
    - Carga y gestión de archivos
    - Sistema de notificaciones
    
    ## Autenticación
    La mayoría de endpoints requieren autenticación. Usa el endpoint `/auth/login` para obtener un token de acceso,
    luego inclúyelo en el header `Authorization` como `Bearer <token>`.
    
    ## Limitación de Velocidad
    Las solicitudes de API tienen limitación de velocidad. Verifica los headers de respuesta para límites actuales.
    
    ## Paginación
    Los endpoints de lista soportan paginación con parámetros `page` y `per_page`.
    
    ## Manejo de Errores
    Todos los errores siguen un formato consistente con códigos de estado HTTP apropiados.
    ''',
    doc='/docs/',
    prefix='/api/v2',
    ordered=True,
    contact='dev@ecosistema-emprendimiento.com',
    contact_email='dev@ecosistema-emprendimiento.com',
    license='MIT',
    security='Bearer Auth',
    authorizations={
        'Bearer Auth': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Header de autorización JWT usando el esquema Bearer. Ejemplo: "Authorization: Bearer {token}"'
        },
        'API Key': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
            'description': 'Clave API para autenticación servicio-a-servicio'
        }
    },
    # Configuración personalizada de Swagger UI
    swagger_ui_config={
        'supportedSubmitMethods': ['get', 'post', 'put', 'delete', 'patch'],
        'tryItOutEnabled': True,
        'displayRequestDuration': True,
        'filter': True,
        'displayOperationId': False,
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
        'docExpansion': 'list',
        'validatorUrl': None,
    }
)

# Manejadores de errores personalizados para la API
@api.errorhandler(ValueError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    return {
        'success': False,
        'error_type': 'validation_error',
        'message': str(error),
        'timestamp': api.datetime.now(timezone.utc).isoformat()
    }, 400

@api.errorhandler(PermissionError)
def handle_permission_error(error):
    """Handle permission errors."""
    return {
        'success': False,
        'error_type': 'permission_error',
        'message': 'Permisos insuficientes para acceder a este recurso',
        'timestamp': api.datetime.now(timezone.utc).isoformat()
    }, 403

@api.errorhandler(FileNotFoundError)
def handle_not_found_error(error):
    """Handle not found errors."""
    return {
        'success': False,
        'error_type': 'not_found_error',
        'message': 'Resource not found',
        'timestamp': api.datetime.now(timezone.utc).isoformat()
    }, 404

@api.errorhandler(Exception)
def handle_generic_error(error):
    """Handle generic errors."""
    return {
        'success': False,
        'error_type': 'internal_error',
        'message': 'An internal server error occurred',
        'timestamp': api.datetime.now(timezone.utc).isoformat()
    }, 500

# Import and register namespaces
from .auth import auth_ns
from .users import users_ns  
from .entrepreneurs import entrepreneurs_ns
from .projects import projects_ns
from .health import health_ns
from .analytics import analytics_ns

# Register namespaces with the API
api.add_namespace(health_ns, path='/health')
api.add_namespace(auth_ns, path='/auth')
api.add_namespace(users_ns, path='/users')
api.add_namespace(entrepreneurs_ns, path='/entrepreneurs')
api.add_namespace(projects_ns, path='/projects')
api.add_namespace(analytics_ns, path='/analytics')

# Add API metadata
@api.documentation
def custom_ui():
    """Custom Swagger UI configuration."""
    return {
        'info': {
            'x-logo': {
                'url': '/static/images/api-logo.png',
                'altText': 'Ecosistema API Logo'
            }
        },
        'externalDocs': {
            'description': 'Full Documentation',
            'url': '/docs/api'
        }
    }