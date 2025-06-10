"""
Módulo de vistas para clientes/stakeholders del ecosistema de emprendimiento.

Este módulo inicializa y configura todas las vistas relacionadas con el portal
de clientes, incluyendo dashboard, directorio de emprendimientos, métricas de impacto,
reportes y analytics.

Los clientes son stakeholders externos que tienen acceso limitado para:
- Ver el directorio público de emprendimientos
- Acceder a métricas de impacto del ecosistema
- Generar reportes específicos de su interés
- Visualizar analytics públicos del programa

Autor: Sistema de Emprendimiento
Versión: 2.0
"""

import logging
from functools import wraps
from flask import Blueprint, current_app, request, session, redirect, url_for, flash, g
from flask_login import current_user, login_required

# Configurar logger específico para el módulo client
logger = logging.getLogger(__name__)

# Crear blueprint principal del módulo client
client_bp = Blueprint(
    'client', 
    __name__, 
    url_prefix='/client',
    template_folder='templates/client',
    static_folder='static/client'
)

# Importar todos los sub-blueprints del módulo client
try:
    from .dashboard import client_dashboard_bp
    from .directory import client_directory_bp  
    from .impact import client_impact_bp
    from .reports import client_reports_bp
    from .analytics import client_analytics_bp
    
    # Registrar sub-blueprints en el blueprint principal
    client_bp.register_blueprint(client_dashboard_bp)
    client_bp.register_blueprint(client_directory_bp)
    client_bp.register_blueprint(client_impact_bp)
    client_bp.register_blueprint(client_reports_bp)
    client_bp.register_blueprint(client_analytics_bp)
    
    logger.info("Todos los sub-blueprints de client fueron registrados exitosamente")
    
except ImportError as e:
    logger.error(f"Error al importar sub-blueprints de client: {str(e)}")
    # Continuar sin el sub-blueprint problemático para evitar fallos en desarrollo
    pass

# Configuraciones específicas del módulo client
CLIENT_CONFIG = {
    'SESSION_TIMEOUT': 7200,  # 2 horas de sesión para clientes
    'MAX_EXPORT_RECORDS': 10000,  # Límite de registros en exportaciones
    'CACHE_TIMEOUT': 300,  # 5 minutos de cache para vistas públicas
    'RATE_LIMIT_PER_HOUR': 200,  # Límite de requests por hora
    'ALLOWED_EXPORT_FORMATS': ['pdf', 'excel', 'csv'],
    'DEFAULT_PAGINATION': 20,
    'MAX_SEARCH_RESULTS': 100
}

# Permisos específicos para diferentes tipos de clientes
CLIENT_PERMISSIONS = {
    'public': {
        'can_view_directory': True,
        'can_view_public_metrics': True,
        'can_export_basic_reports': False,
        'can_access_detailed_analytics': False
    },
    'stakeholder': {
        'can_view_directory': True,
        'can_view_public_metrics': True,
        'can_export_basic_reports': True,
        'can_access_detailed_analytics': True,
        'can_view_impact_reports': True
    },
    'investor': {
        'can_view_directory': True,
        'can_view_public_metrics': True,
        'can_export_basic_reports': True,
        'can_access_detailed_analytics': True,
        'can_view_impact_reports': True,
        'can_view_financial_metrics': True
    },
    'partner': {
        'can_view_directory': True,
        'can_view_public_metrics': True,
        'can_export_basic_reports': True,
        'can_access_detailed_analytics': True,
        'can_view_impact_reports': True,
        'can_view_partnership_metrics': True
    }
}


def get_client_type(user=None):
    """
    Determina el tipo de cliente basado en el usuario o contexto.
    
    Args:
        user: Usuario actual o None para cliente público
        
    Returns:
        str: Tipo de cliente ('public', 'stakeholder', 'investor', 'partner')
    """
    if not user or not user.is_authenticated:
        return 'public'
    
    if hasattr(user, 'client') and user.client:
        return user.client.client_type or 'stakeholder'
    
    # Si es un usuario registrado pero sin perfil de cliente específico
    if user.role == 'client':
        return 'stakeholder'
    
    return 'public'


def get_client_permissions(client_type=None):
    """
    Obtiene los permisos para un tipo específico de cliente.
    
    Args:
        client_type: Tipo de cliente, si no se especifica usa el actual
        
    Returns:
        dict: Diccionario con permisos del cliente
    """
    if not client_type:
        client_type = get_client_type(current_user)
    
    return CLIENT_PERMISSIONS.get(client_type, CLIENT_PERMISSIONS['public'])


def require_client_permission(permission):
    """
    Decorador para verificar permisos específicos de cliente.
    
    Args:
        permission: Nombre del permiso requerido
        
    Returns:
        function: Función decoradora
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_type = get_client_type(current_user)
            permissions = get_client_permissions(client_type)
            
            if not permissions.get(permission, False):
                flash('No tienes permisos para acceder a esta funcionalidad.', 'error')
                return redirect(url_for('client.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_authenticated_client(f):
    """
    Decorador que requiere que el cliente esté autenticado.
    
    Diferente a @login_required porque permite acceso a clientes
    con diferentes niveles de autenticación.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_type = get_client_type(current_user)
        
        if client_type == 'public' and request.endpoint not in get_public_endpoints():
            flash('Debes iniciar sesión para acceder a esta funcionalidad.', 'info')
            return redirect(url_for('auth.login', next=request.url))
        
        return f(*args, **kwargs)
    return decorated_function


def get_public_endpoints():
    """
    Retorna lista de endpoints públicos que no requieren autenticación.
    
    Returns:
        list: Lista de endpoints públicos
    """
    return [
        'client.dashboard',
        'client_directory.index',
        'client_directory.search',
        'client_directory.view_entrepreneur',
        'client_impact.public_metrics',
        'client_analytics.public_dashboard'
    ]


def track_client_activity(activity_type, details=None):
    """
    Registra actividad del cliente para analytics y auditoría.
    
    Args:
        activity_type: Tipo de actividad realizada
        details: Detalles adicionales de la actividad
    """
    try:
        from app.services.analytics_service import AnalyticsService
        
        client_type = get_client_type(current_user)
        user_id = current_user.id if current_user.is_authenticated else None
        
        AnalyticsService.track_client_activity(
            client_type=client_type,
            user_id=user_id,
            activity_type=activity_type,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            endpoint=request.endpoint
        )
        
    except Exception as e:
        logger.error(f"Error registrando actividad del cliente: {str(e)}")


def apply_client_rate_limiting():
    """
    Aplica rate limiting específico para clientes.
    
    Returns:
        bool: True si se permite la request, False si se debe bloquear
    """
    try:
        from app.utils.decorators import check_rate_limit
        
        client_type = get_client_type(current_user)
        
        # Rate limits diferentes según tipo de cliente
        limits = {
            'public': '50 per hour',
            'stakeholder': '200 per hour',
            'investor': '500 per hour',
            'partner': '1000 per hour'
        }
        
        limit = limits.get(client_type, '50 per hour')
        return check_rate_limit(limit, current_user.id if current_user.is_authenticated else request.remote_addr)
        
    except Exception as e:
        logger.error(f"Error aplicando rate limiting: {str(e)}")
        return True  # Permitir en caso de error


# Hooks y middleware del blueprint principal

@client_bp.before_request
def before_client_request():
    """
    Se ejecuta antes de cada request al módulo client.
    
    Configura contexto específico para clientes y aplica validaciones.
    """
    # Verificar rate limiting
    if not apply_client_rate_limiting():
        from flask import abort
        abort(429)  # Too Many Requests
    
    # Establecer contexto del cliente
    g.client_type = get_client_type(current_user)
    g.client_permissions = get_client_permissions(g.client_type)
    g.client_config = CLIENT_CONFIG
    
    # Registrar actividad de la request
    if request.endpoint and not request.endpoint.startswith('static'):
        track_client_activity('page_view', {
            'endpoint': request.endpoint,
            'method': request.method
        })
    
    # Configurar variables de sesión específicas para clientes
    if current_user.is_authenticated and current_user.role == 'client':
        session.permanent = True
        current_app.permanent_session_lifetime = CLIENT_CONFIG['SESSION_TIMEOUT']


@client_bp.after_request
def after_client_request(response):
    """
    Se ejecuta después de cada request al módulo client.
    
    Aplica headers de seguridad y configuraciones específicas.
    """
    # Headers de seguridad específicos para clientes
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Cache headers según el tipo de contenido
    if request.endpoint in get_public_endpoints():
        # Cache más agresivo para contenido público
        response.headers['Cache-Control'] = f'public, max-age={CLIENT_CONFIG["CACHE_TIMEOUT"]}'
    else:
        # Sin cache para contenido privado
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response


@client_bp.context_processor
def inject_client_context():
    """
    Inyecta variables de contexto específicas para todas las templates de client.
    
    Returns:
        dict: Variables de contexto disponibles en templates
    """
    return {
        'client_type': getattr(g, 'client_type', 'public'),
        'client_permissions': getattr(g, 'client_permissions', CLIENT_PERMISSIONS['public']),
        'client_config': CLIENT_CONFIG,
        'current_module': 'client'
    }


# Rutas principales del módulo client

@client_bp.route('/')
def index():
    """
    Ruta raíz del módulo client.
    
    Redirige al dashboard apropiado según el tipo de cliente.
    """
    client_type = get_client_type(current_user)
    
    if client_type == 'public':
        return redirect(url_for('client_directory.index'))
    else:
        return redirect(url_for('client_dashboard.index'))


@client_bp.route('/health')
def health_check():
    """
    Endpoint de health check para monitoreo del módulo client.
    
    Returns:
        dict: Estado del módulo y sus componentes
    """
    from flask import jsonify
    
    try:
        # Verificar conectividad a base de datos
        from app.extensions import db
        db.session.execute('SELECT 1')
        
        # Verificar cache si está disponible
        cache_status = True
        try:
            from app.extensions import cache
            cache.get('health_check')
        except:
            cache_status = False
        
        health_status = {
            'status': 'healthy',
            'module': 'client',
            'database': 'connected',
            'cache': 'available' if cache_status else 'unavailable',
            'sub_modules': {
                'dashboard': 'loaded',
                'directory': 'loaded', 
                'impact': 'loaded',
                'reports': 'loaded',
                'analytics': 'loaded'
            },
            'timestamp': current_app.config.get('SERVER_START_TIME')
        }
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'module': 'client'
        }), 500


# Manejo de errores específico del módulo client

@client_bp.errorhandler(403)
def client_forbidden(error):
    """Maneja errores de permisos insuficientes en el módulo client."""
    from flask import render_template
    
    track_client_activity('access_denied', {
        'error': '403',
        'endpoint': request.endpoint
    })
    
    return render_template(
        'client/errors/403.html',
        error=error,
        client_type=get_client_type(current_user)
    ), 403


@client_bp.errorhandler(404)
def client_not_found(error):
    """Maneja errores de recurso no encontrado en el módulo client."""
    from flask import render_template
    
    track_client_activity('page_not_found', {
        'error': '404',
        'endpoint': request.endpoint,
        'url': request.url
    })
    
    return render_template(
        'client/errors/404.html',
        error=error,
        client_type=get_client_type(current_user)
    ), 404


@client_bp.errorhandler(429)
def client_rate_limit_exceeded(error):
    """Maneja errores de rate limiting en el módulo client."""
    from flask import render_template
    
    track_client_activity('rate_limit_exceeded', {
        'error': '429',
        'client_type': get_client_type(current_user)
    })
    
    return render_template(
        'client/errors/429.html',
        error=error
    ), 429


@client_bp.errorhandler(500)
def client_internal_error(error):
    """Maneja errores internos del servidor en el módulo client."""
    from flask import render_template
    from app.extensions import db
    
    # Rollback en caso de error de DB
    try:
        db.session.rollback()
    except:
        pass
    
    logger.error(f"Error interno en módulo client: {str(error)}")
    
    track_client_activity('internal_error', {
        'error': '500',
        'endpoint': request.endpoint,
        'error_details': str(error)
    })
    
    return render_template(
        'client/errors/500.html',
        error=error
    ), 500


# Funciones de utilidad específicas para el módulo client

def get_client_dashboard_data(client_type='public'):
    """
    Obtiene datos específicos para el dashboard de un tipo de cliente.
    
    Args:
        client_type: Tipo de cliente
        
    Returns:
        dict: Datos del dashboard según permisos del cliente
    """
    try:
        from app.services.analytics_service import AnalyticsService
        from app.models.entrepreneur import Entrepreneur
        from app.models.project import Project
        
        permissions = get_client_permissions(client_type)
        dashboard_data = {}
        
        # Métricas básicas públicas
        if permissions.get('can_view_public_metrics'):
            dashboard_data.update({
                'total_entrepreneurs': Entrepreneur.query.filter_by(is_public=True).count(),
                'active_projects': Project.query.filter_by(status='active', is_public=True).count(),
                'ecosystem_highlights': AnalyticsService.get_public_highlights()
            })
        
        # Métricas detalladas para stakeholders autenticados
        if permissions.get('can_access_detailed_analytics'):
            dashboard_data.update({
                'detailed_metrics': AnalyticsService.get_stakeholder_metrics(),
                'success_stories': AnalyticsService.get_success_stories(),
                'impact_metrics': AnalyticsService.get_impact_metrics()
            })
        
        # Métricas financieras para inversores
        if permissions.get('can_view_financial_metrics'):
            dashboard_data.update({
                'financial_overview': AnalyticsService.get_financial_overview(),
                'roi_metrics': AnalyticsService.get_roi_metrics()
            })
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error obteniendo datos del dashboard: {str(e)}")
        return {}


def get_client_navigation_menu(client_type='public'):
    """
    Genera menú de navegación basado en permisos del cliente.
    
    Args:
        client_type: Tipo de cliente
        
    Returns:
        list: Lista de elementos del menú
    """
    permissions = get_client_permissions(client_type)
    menu_items = []
    
    # Dashboard (siempre disponible)
    menu_items.append({
        'name': 'Dashboard',
        'url': 'client.dashboard',
        'icon': 'fas fa-tachometer-alt',
        'active': True
    })
    
    # Directorio (siempre disponible)
    if permissions.get('can_view_directory'):
        menu_items.append({
            'name': 'Directorio',
            'url': 'client_directory.index',
            'icon': 'fas fa-users',
            'active': True
        })
    
    # Métricas de impacto
    if permissions.get('can_view_impact_reports'):
        menu_items.append({
            'name': 'Impacto',
            'url': 'client_impact.index',
            'icon': 'fas fa-chart-line',
            'active': True
        })
    
    # Reportes
    if permissions.get('can_export_basic_reports'):
        menu_items.append({
            'name': 'Reportes',
            'url': 'client_reports.index',
            'icon': 'fas fa-file-alt',
            'active': True
        })
    
    # Analytics avanzados
    if permissions.get('can_access_detailed_analytics'):
        menu_items.append({
            'name': 'Analytics',
            'url': 'client_analytics.index',
            'icon': 'fas fa-analytics',
            'active': True
        })
    
    return menu_items


def cache_key_for_client(base_key, client_type=None):
    """
    Genera clave de cache específica para tipo de cliente.
    
    Args:
        base_key: Clave base del cache
        client_type: Tipo de cliente
        
    Returns:
        str: Clave de cache específica
    """
    if not client_type:
        client_type = get_client_type(current_user)
    
    return f"client:{client_type}:{base_key}"


# Exportar componentes principales del módulo
__all__ = [
    'client_bp',
    'CLIENT_CONFIG',
    'CLIENT_PERMISSIONS',
    'get_client_type',
    'get_client_permissions',
    'require_client_permission',
    'require_authenticated_client',
    'track_client_activity',
    'get_client_dashboard_data',
    'get_client_navigation_menu',
    'cache_key_for_client'
]


# Logging de inicialización del módulo
logger.info(f"Módulo client inicializado correctamente")
logger.info(f"Configuración: {CLIENT_CONFIG}")
logger.info(f"Tipos de cliente soportados: {list(CLIENT_PERMISSIONS.keys())}")