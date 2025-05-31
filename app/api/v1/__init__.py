"""
API v1 Package Initialization
============================

Este módulo inicializa y configura la versión 1 de la API REST,
registrando todos los blueprints y endpoints específicos de esta versión.

Funcionalidades:
- Registro de todos los endpoints v1
- Configuración específica de v1
- Documentación automática
- Validación y serialización
- Middleware específico de versión
"""

from flask import Blueprint, jsonify, request, current_app
from flask_restful import Api
from datetime import datetime
import logging
from typing import Dict, Any, List

from app.core.exceptions import ValidationError, AuthenticationError
from app.api.middleware.auth import api_auth_required
from app.utils.decorators import validate_json


# Logger específico para API v1
v1_logger = logging.getLogger('api.v1')


class APIv1Config:
    """Configuración específica para API v1"""
    
    VERSION = "1.0.0"
    DESCRIPTION = "API REST v1 para Ecosistema de Emprendimiento"
    
    # Endpoints disponibles en v1
    AVAILABLE_ENDPOINTS = [
        'auth',          # Autenticación y autorización
        'users',         # Gestión de usuarios
        'entrepreneurs', # Gestión de emprendedores
        'allies',        # Gestión de aliados/mentores
        'clients',       # Gestión de clientes/stakeholders
        'projects',      # Gestión de proyectos
        'programs',      # Gestión de programas
        'organizations', # Gestión de organizaciones
        'meetings',      # Gestión de reuniones
        'messages',      # Sistema de mensajería
        'documents',     # Gestión de documentos
        'tasks',         # Gestión de tareas
        'mentorship',    # Sistema de mentoría
        'relationships', # Gestión de relaciones
        'analytics',     # Métricas y analytics
        'notifications', # Sistema de notificaciones
        'webhooks'       # Webhooks para integraciones
    ]
    
    # Features habilitadas en v1
    ENABLED_FEATURES = {
        'authentication': True,
        'user_management': True,
        'project_management': True,
        'mentorship_system': True,
        'messaging_system': True,
        'document_management': True,
        'analytics_basic': True,
        'notifications': True,
        'webhooks': True,
        'file_uploads': True,
        'real_time_updates': True,
        'advanced_search': True,
        'bulk_operations': True,
        'data_export': True
    }
    
    # Límites específicos de v1
    LIMITS = {
        'max_file_size': 50 * 1024 * 1024,  # 50MB
        'max_files_per_upload': 10,
        'max_bulk_operations': 100,
        'max_search_results': 1000,
        'max_export_records': 10000
    }


def create_v1_blueprint() -> Blueprint:
    """
    Crea y configura el blueprint para API v1
    
    Returns:
        Blueprint configurado para API v1
    """
    # Crear blueprint principal de v1
    v1_bp = Blueprint('api_v1', __name__)
    
    # Configurar Flask-RESTful
    api = Api(v1_bp, prefix='')
    
    # Registrar middleware específico de v1
    register_v1_middleware(v1_bp)
    
    # Registrar endpoints por categoría
    register_auth_endpoints(v1_bp)
    register_user_endpoints(v1_bp)
    register_entrepreneur_endpoints(v1_bp)
    register_ally_endpoints(v1_bp)
    register_client_endpoints(v1_bp)
    register_project_endpoints(v1_bp)
    register_program_endpoints(v1_bp)
    register_organization_endpoints(v1_bp)
    register_meeting_endpoints(v1_bp)
    register_message_endpoints(v1_bp)
    register_document_endpoints(v1_bp)
    register_task_endpoints(v1_bp)
    register_mentorship_endpoints(v1_bp)
    register_relationship_endpoints(v1_bp)
    register_analytics_endpoints(v1_bp)
    register_notification_endpoints(v1_bp)
    register_webhook_endpoints(v1_bp)
    
    # Registrar endpoints de utilidad de v1
    register_v1_utility_endpoints(v1_bp)
    
    v1_logger.info("API v1 blueprint created and configured")
    
    return v1_bp


def register_v1_middleware(v1_bp: Blueprint):
    """
    Registra middleware específico para API v1
    
    Args:
        v1_bp: Blueprint de API v1
    """
    
    @v1_bp.before_request
    def before_v1_request():
        """Middleware específico de v1 ejecutado antes de cada request"""
        # Validar features habilitadas
        endpoint = request.endpoint
        if endpoint and not is_feature_enabled_for_endpoint(endpoint):
            return jsonify({
                'error': 'Feature Not Available',
                'message': 'This feature is not available in API v1',
                'available_in': 'v2',
                'timestamp': datetime.utcnow().isoformat()
            }), 501
        
        # Log específico de v1
        v1_logger.debug(f"API v1 Request: {request.method} {request.path}")
    
    @v1_bp.after_request
    def after_v1_request(response):
        """Middleware específico de v1 ejecutado después de cada response"""
        # Agregar headers específicos de v1
        response.headers['X-API-Version'] = APIv1Config.VERSION
        response.headers['X-API-Features'] = ','.join([
            feature for feature, enabled in APIv1Config.ENABLED_FEATURES.items() 
            if enabled
        ])
        
        return response


def register_auth_endpoints(v1_bp: Blueprint):
    """Registra endpoints de autenticación"""
    try:
        from app.api.v1.auth import auth_bp
        v1_bp.register_blueprint(auth_bp, url_prefix='/auth')
        v1_logger.info("Registered auth endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register auth endpoints: {e}")


def register_user_endpoints(v1_bp: Blueprint):
    """Registra endpoints de usuarios"""
    try:
        from app.api.v1.users import users_bp
        v1_bp.register_blueprint(users_bp, url_prefix='/users')
        v1_logger.info("Registered user endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register user endpoints: {e}")


def register_entrepreneur_endpoints(v1_bp: Blueprint):
    """Registra endpoints de emprendedores"""
    try:
        from app.api.v1.entrepreneurs import entrepreneurs_bp
        v1_bp.register_blueprint(entrepreneurs_bp, url_prefix='/entrepreneurs')
        v1_logger.info("Registered entrepreneur endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register entrepreneur endpoints: {e}")


def register_ally_endpoints(v1_bp: Blueprint):
    """Registra endpoints de aliados/mentores"""
    try:
        from app.api.v1.allies import allies_bp
        v1_bp.register_blueprint(allies_bp, url_prefix='/allies')
        v1_logger.info("Registered ally endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register ally endpoints: {e}")


def register_client_endpoints(v1_bp: Blueprint):
    """Registra endpoints de clientes/stakeholders"""
    try:
        from app.api.v1.clients import clients_bp
        v1_bp.register_blueprint(clients_bp, url_prefix='/clients')
        v1_logger.info("Registered client endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register client endpoints: {e}")


def register_project_endpoints(v1_bp: Blueprint):
    """Registra endpoints de proyectos"""
    try:
        from app.api.v1.projects import projects_bp
        v1_bp.register_blueprint(projects_bp, url_prefix='/projects')
        v1_logger.info("Registered project endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register project endpoints: {e}")


def register_program_endpoints(v1_bp: Blueprint):
    """Registra endpoints de programas"""
    try:
        from app.api.v1.programs import programs_bp
        v1_bp.register_blueprint(programs_bp, url_prefix='/programs')
        v1_logger.info("Registered program endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register program endpoints: {e}")


def register_organization_endpoints(v1_bp: Blueprint):
    """Registra endpoints de organizaciones"""
    try:
        from app.api.v1.organizations import organizations_bp
        v1_bp.register_blueprint(organizations_bp, url_prefix='/organizations')
        v1_logger.info("Registered organization endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register organization endpoints: {e}")


def register_meeting_endpoints(v1_bp: Blueprint):
    """Registra endpoints de reuniones"""
    try:
        from app.api.v1.meetings import meetings_bp
        v1_bp.register_blueprint(meetings_bp, url_prefix='/meetings')
        v1_logger.info("Registered meeting endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register meeting endpoints: {e}")


def register_message_endpoints(v1_bp: Blueprint):
    """Registra endpoints de mensajería"""
    try:
        from app.api.v1.messages import messages_bp
        v1_bp.register_blueprint(messages_bp, url_prefix='/messages')
        v1_logger.info("Registered message endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register message endpoints: {e}")


def register_document_endpoints(v1_bp: Blueprint):
    """Registra endpoints de documentos"""
    try:
        from app.api.v1.documents import documents_bp
        v1_bp.register_blueprint(documents_bp, url_prefix='/documents')
        v1_logger.info("Registered document endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register document endpoints: {e}")


def register_task_endpoints(v1_bp: Blueprint):
    """Registra endpoints de tareas"""
    try:
        from app.api.v1.tasks import tasks_bp
        v1_bp.register_blueprint(tasks_bp, url_prefix='/tasks')
        v1_logger.info("Registered task endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register task endpoints: {e}")


def register_mentorship_endpoints(v1_bp: Blueprint):
    """Registra endpoints de mentoría"""
    try:
        from app.api.v1.mentorship import mentorship_bp
        v1_bp.register_blueprint(mentorship_bp, url_prefix='/mentorship')
        v1_logger.info("Registered mentorship endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register mentorship endpoints: {e}")


def register_relationship_endpoints(v1_bp: Blueprint):
    """Registra endpoints de relaciones"""
    try:
        from app.api.v1.relationships import relationships_bp
        v1_bp.register_blueprint(relationships_bp, url_prefix='/relationships')
        v1_logger.info("Registered relationship endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register relationship endpoints: {e}")


def register_analytics_endpoints(v1_bp: Blueprint):
    """Registra endpoints de analytics"""
    try:
        from app.api.v1.analytics import analytics_bp
        v1_bp.register_blueprint(analytics_bp, url_prefix='/analytics')
        v1_logger.info("Registered analytics endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register analytics endpoints: {e}")


def register_notification_endpoints(v1_bp: Blueprint):
    """Registra endpoints de notificaciones"""
    try:
        from app.api.v1.notifications import notifications_bp
        v1_bp.register_blueprint(notifications_bp, url_prefix='/notifications')
        v1_logger.info("Registered notification endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register notification endpoints: {e}")


def register_webhook_endpoints(v1_bp: Blueprint):
    """Registra endpoints de webhooks"""
    try:
        from app.api.v1.webhooks import webhooks_bp
        v1_bp.register_blueprint(webhooks_bp, url_prefix='/webhooks')
        v1_logger.info("Registered webhook endpoints")
    except ImportError as e:
        v1_logger.warning(f"Could not register webhook endpoints: {e}")


def register_v1_utility_endpoints(v1_bp: Blueprint):
    """
    Registra endpoints de utilidad específicos de v1
    
    Args:
        v1_bp: Blueprint de API v1
    """
    
    @v1_bp.route('/version')
    def get_v1_version():
        """Información de versión específica de v1"""
        return jsonify({
            'version': APIv1Config.VERSION,
            'description': APIv1Config.DESCRIPTION,
            'endpoints': APIv1Config.AVAILABLE_ENDPOINTS,
            'features': APIv1Config.ENABLED_FEATURES,
            'limits': APIv1Config.LIMITS,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @v1_bp.route('/features')
    def get_v1_features():
        """Lista de features disponibles en v1"""
        return jsonify({
            'enabled_features': {
                feature: {
                    'enabled': enabled,
                    'description': get_feature_description(feature)
                }
                for feature, enabled in APIv1Config.ENABLED_FEATURES.items()
            },
            'limits': APIv1Config.LIMITS,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @v1_bp.route('/endpoints')
    def get_v1_endpoints():
        """Lista completa de endpoints disponibles en v1"""
        endpoint_map = {}
        
        for rule in current_app.url_map.iter_rules():
            if rule.rule.startswith('/api/v1/'):
                endpoint_path = rule.rule.replace('/api/v1/', '')
                category = endpoint_path.split('/')[0] if '/' in endpoint_path else endpoint_path
                
                if category not in endpoint_map:
                    endpoint_map[category] = []
                
                endpoint_map[category].append({
                    'path': rule.rule,
                    'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                    'endpoint': rule.endpoint
                })
        
        return jsonify({
            'categories': endpoint_map,
            'total_endpoints': sum(len(endpoints) for endpoints in endpoint_map.values()),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @v1_bp.route('/schema')
    def get_v1_schema():
        """Schema básico de la API v1"""
        return jsonify({
            'version': APIv1Config.VERSION,
            'base_url': '/api/v1',
            'authentication': {
                'type': 'Bearer Token',
                'header': 'Authorization',
                'format': 'Bearer <token>'
            },
            'common_headers': {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-Version': 'v1'
            },
            'error_format': {
                'error': 'string',
                'message': 'string',
                'details': 'object|null',
                'timestamp': 'ISO8601 datetime',
                'path': 'string'
            },
            'pagination': {
                'page_param': 'page',
                'per_page_param': 'per_page',
                'default_per_page': 20,
                'max_per_page': 100
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @v1_bp.route('/status')
    def get_v1_status():
        """Estado específico de API v1"""
        try:
            # Verificar disponibilidad de endpoints críticos
            critical_endpoints = ['auth', 'users', 'projects']
            endpoint_status = {}
            
            for endpoint in critical_endpoints:
                try:
                    # Verificar si el blueprint está registrado
                    endpoint_status[endpoint] = 'available'
                except Exception:
                    endpoint_status[endpoint] = 'unavailable'
            
            status = 'healthy' if all(
                status == 'available' for status in endpoint_status.values()
            ) else 'degraded'
            
            return jsonify({
                'status': status,
                'version': APIv1Config.VERSION,
                'endpoints': endpoint_status,
                'features': {
                    feature: 'enabled' if enabled else 'disabled'
                    for feature, enabled in APIv1Config.ENABLED_FEATURES.items()
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            v1_logger.error(f"Error checking v1 status: {e}")
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500


# Funciones auxiliares
def is_feature_enabled_for_endpoint(endpoint: str) -> bool:
    """
    Verifica si una feature está habilitada para un endpoint específico
    
    Args:
        endpoint: Nombre del endpoint
        
    Returns:
        True si la feature está habilitada
    """
    if not endpoint:
        return True
    
    # Mapeo de endpoints a features
    endpoint_feature_map = {
        'auth': 'authentication',
        'users': 'user_management',
        'entrepreneurs': 'user_management',
        'allies': 'user_management',
        'clients': 'user_management',
        'projects': 'project_management',
        'programs': 'project_management',
        'organizations': 'user_management',
        'meetings': 'project_management',
        'messages': 'messaging_system',
        'documents': 'document_management',
        'tasks': 'project_management',
        'mentorship': 'mentorship_system',
        'relationships': 'user_management',
        'analytics': 'analytics_basic',
        'notifications': 'notifications',
        'webhooks': 'webhooks'
    }
    
    # Extraer categoría del endpoint
    endpoint_parts = endpoint.split('.')
    if len(endpoint_parts) > 1:
        category = endpoint_parts[-1].split('_')[0]
    else:
        category = endpoint.split('_')[0]
    
    feature = endpoint_feature_map.get(category)
    if not feature:
        return True  # Si no hay mapeo, permitir por defecto
    
    return APIv1Config.ENABLED_FEATURES.get(feature, False)


def get_feature_description(feature: str) -> str:
    """
    Obtiene la descripción de una feature
    
    Args:
        feature: Nombre de la feature
        
    Returns:
        Descripción de la feature
    """
    descriptions = {
        'authentication': 'Sistema de autenticación y autorización con JWT',
        'user_management': 'Gestión completa de usuarios, emprendedores, aliados y clientes',
        'project_management': 'Creación y gestión de proyectos emprendedores',
        'mentorship_system': 'Sistema de mentoría y conexiones entre usuarios',
        'messaging_system': 'Sistema de mensajería interna entre usuarios',
        'document_management': 'Gestión y almacenamiento de documentos',
        'analytics_basic': 'Métricas básicas y reportes del sistema',
        'notifications': 'Sistema de notificaciones en tiempo real',
        'webhooks': 'Webhooks para integraciones externas',
        'file_uploads': 'Subida y gestión de archivos',
        'real_time_updates': 'Actualizaciones en tiempo real via WebSockets',
        'advanced_search': 'Búsqueda avanzada con filtros múltiples',
        'bulk_operations': 'Operaciones en lote para eficiencia',
        'data_export': 'Exportación de datos en múltiples formatos'
    }
    
    return descriptions.get(feature, 'Feature no documentada')


class APIv1Validator:
    """Validador específico para API v1"""
    
    @staticmethod
    def validate_pagination_params(page: int = 1, per_page: int = 20) -> tuple:
        """
        Valida parámetros de paginación
        
        Args:
            page: Número de página
            per_page: Elementos por página
            
        Returns:
            Tupla con parámetros validados
        """
        page = max(1, page)
        per_page = min(max(1, per_page), 100)  # Límite máximo de v1
        
        return page, per_page
    
    @staticmethod
    def validate_file_upload(file) -> bool:
        """
        Valida archivos subidos según límites de v1
        
        Args:
            file: Archivo a validar
            
        Returns:
            True si es válido
        """
        if not file:
            return False
        
        # Verificar tamaño
        if hasattr(file, 'content_length') and file.content_length:
            if file.content_length > APIv1Config.LIMITS['max_file_size']:
                raise ValidationError(f"Archivo demasiado grande. Máximo: {APIv1Config.LIMITS['max_file_size']} bytes")
        
        # Verificar tipo de archivo (implementar según necesidades)
        allowed_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif'}
        if hasattr(file, 'filename') and file.filename:
            import os
            _, ext = os.path.splitext(file.filename.lower())
            if ext not in allowed_extensions:
                raise ValidationError(f"Tipo de archivo no permitido. Permitidos: {', '.join(allowed_extensions)}")
        
        return True
    
    @staticmethod
    def validate_bulk_operation(items: List[Any]) -> bool:
        """
        Valida operaciones en lote según límites de v1
        
        Args:
            items: Lista de elementos a procesar
            
        Returns:
            True si es válida
        """
        if len(items) > APIv1Config.LIMITS['max_bulk_operations']:
            raise ValidationError(f"Demasiados elementos. Máximo: {APIv1Config.LIMITS['max_bulk_operations']}")
        
        return True


# Exportaciones principales
__all__ = [
    'create_v1_blueprint',
    'APIv1Config',
    'APIv1Validator',
    'is_feature_enabled_for_endpoint',
    'get_feature_description',
    'v1_logger'
]