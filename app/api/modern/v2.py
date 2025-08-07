"""
Modern API v2 using Flask-RESTX with automatic OpenAPI documentation.
"""

from flask import Blueprint
from flask_restx import Api

# Create API v2 blueprint
api_v2_bp = Blueprint('api_v2', __name__, url_prefix='/api/v2')

# Create Flask-RESTX API instance
api = Api(
    api_v2_bp,
    version='2.0',
    title='Ecosistema Emprendimiento API',
    description='''
    Modern REST API for the Entrepreneurship Ecosystem Platform.
    
    ## Features
    - Modern authentication with JWT
    - Comprehensive user management
    - Project and mentorship tracking
    - Real-time analytics
    - File upload and management
    - Notification system
    
    ## Authentication
    Most endpoints require authentication. Use the `/auth/login` endpoint to obtain an access token,
    then include it in the `Authorization` header as `Bearer <token>`.
    
    ## Rate Limiting
    API requests are rate limited. Check response headers for current limits.
    
    ## Pagination
    List endpoints support pagination with `page` and `per_page` parameters.
    
    ## Error Handling
    All errors follow a consistent format with appropriate HTTP status codes.
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
            'description': 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"'
        },
        'API Key': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
            'description': 'API Key for service-to-service authentication'
        }
    },
    # Custom Swagger UI configuration
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

# Custom error handlers for the API
@api.errorhandler(ValueError)
def handle_validation_error(error):
    """Handle validation errors."""
    return {
        'success': False,
        'error_type': 'validation_error',
        'message': str(error),
        'timestamp': api.datetime.utcnow().isoformat()
    }, 400

@api.errorhandler(PermissionError)
def handle_permission_error(error):
    """Handle permission errors."""
    return {
        'success': False,
        'error_type': 'permission_error',
        'message': 'Insufficient permissions to access this resource',
        'timestamp': api.datetime.utcnow().isoformat()
    }, 403

@api.errorhandler(FileNotFoundError)
def handle_not_found_error(error):
    """Handle not found errors."""
    return {
        'success': False,
        'error_type': 'not_found_error',
        'message': 'Resource not found',
        'timestamp': api.datetime.utcnow().isoformat()
    }, 404

@api.errorhandler(Exception)
def handle_generic_error(error):
    """Handle generic errors."""
    return {
        'success': False,
        'error_type': 'internal_error',
        'message': 'An internal server error occurred',
        'timestamp': api.datetime.utcnow().isoformat()
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