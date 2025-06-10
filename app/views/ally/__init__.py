"""
Módulo de inicialización para las vistas de Aliados/Mentores.

Este módulo centraliza todas las rutas, blueprints y funcionalidades
relacionadas con los aliados y mentores del ecosistema de emprendimiento.
Incluye registro de blueprints, decoradores comunes, middleware específico
y utilidades compartidas para el portal de aliados.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Blueprint, current_app, request, redirect, url_for, 
    flash, g, session, abort, jsonify
)
from flask_login import current_user, login_required
from werkzeug.exceptions import Forbidden, NotFound

from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.permissions import require_ally, require_active_user, check_permissions
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, 
    Meeting, Message, Document, ActivityLog, Notification
)
from app.services.notification_service import NotificationService
from app.utils.decorators import rate_limit, cache_response
from app.utils.formatters import format_time_duration, format_currency, format_date


# ==================== CONFIGURACIÓN DEL BLUEPRINT PRINCIPAL ====================

# Blueprint principal para aliados
ally_bp = Blueprint(
    'ally', 
    __name__, 
    url_prefix='/ally',
    template_folder='templates/ally',
    static_folder='static/ally'
)


# ==================== IMPORTACIÓN DE BLUEPRINTS ====================

def _import_ally_blueprints():
    """
    Importa todos los blueprints del módulo ally de forma lazy.
    
    Esta función permite importar los blueprints solo cuando se necesitan,
    evitando problemas de importación circular y mejorando el tiempo de inicio.
    
    Returns:
        Dict con todos los blueprints importados
    """
    blueprints = {}
    
    try:
        # Dashboard principal
        from .dashboard import ally_dashboard_bp
        blueprints['dashboard'] = ally_dashboard_bp
        
        # Perfil del aliado
        from .profile import ally_profile_bp
        blueprints['profile'] = ally_profile_bp
        
        # Gestión de emprendedores
        from .entrepreneurs import ally_entrepreneurs_bp
        blueprints['entrepreneurs'] = ally_entrepreneurs_bp
        
        # Sistema de mentoría
        from .mentorship import ally_mentorship_bp
        blueprints['mentorship'] = ally_mentorship_bp
        
        # Calendario y citas
        from .calendar import ally_calendar_bp
        blueprints['calendar'] = ally_calendar_bp
        
        # Registro de horas
        from .hours import ally_hours_bp
        blueprints['hours'] = ally_hours_bp
        
        # Sistema de mensajería
        from .messages import ally_messages_bp
        blueprints['messages'] = ally_messages_bp
        
        # Reportes y analytics
        from .reports import ally_reports_bp
        blueprints['reports'] = ally_reports_bp
        
        current_app.logger.info(f"Blueprints de ally importados exitosamente: {list(blueprints.keys())}")
        
    except ImportError as e:
        current_app.logger.error(f"Error importando blueprints de ally: {str(e)}")
        # Continuar con los blueprints que sí se pudieron importar
    
    return blueprints


# ==================== DECORADORES ESPECÍFICOS PARA ALIADOS ====================

def require_ally_access(f: Callable) -> Callable:
    """
    Decorador que requiere acceso de aliado y valida permisos específicos.
    
    Este decorador extiende la funcionalidad básica de require_ally
    añadiendo validaciones adicionales específicas para el portal de aliados.
    
    Args:
        f: Función a decorar
        
    Returns:
        Función decorada con validaciones de aliado
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta área', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        # Verificar que sea un aliado
        if not hasattr(current_user, 'ally_profile') or not current_user.ally_profile:
            current_app.logger.warning(f"Usuario {current_user.id} intentó acceder al portal de aliados sin perfil")
            abort(403)
        
        # Verificar que el perfil de aliado esté activo
        ally_profile = current_user.ally_profile
        if not ally_profile.is_active:
            flash('Tu perfil de aliado está desactivado. Contacta al administrador.', 'error')
            return redirect(url_for('main.index'))
        
        # Verificar estado de verificación
        if ally_profile.verification_status != 'approved':
            flash('Tu perfil de aliado está pendiente de aprobación.', 'info')
            return redirect(url_for('ally.profile.verification_pending'))
        
        # Agregar perfil de aliado al contexto global
        g.ally_profile = ally_profile
        g.user_type = 'ally'
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_entrepreneur_access(entrepreneur_id_param: str = 'entrepreneur_id'):
    """
    Decorador que valida el acceso a un emprendedor específico.
    
    Verifica que el aliado tenga permisos para acceder a la información
    del emprendedor especificado.
    
    Args:
        entrepreneur_id_param: Nombre del parámetro que contiene el ID del emprendedor
        
    Returns:
        Decorador configurado
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ally_profile = g.get('ally_profile')
            if not ally_profile:
                abort(403)
            
            # Obtener ID del emprendedor desde los argumentos
            entrepreneur_id = kwargs.get(entrepreneur_id_param) or request.view_args.get(entrepreneur_id_param)
            
            if not entrepreneur_id:
                abort(400)  # Bad Request
            
            # Verificar que el emprendedor existe
            entrepreneur = Entrepreneur.query.get(entrepreneur_id)
            if not entrepreneur:
                abort(404)
            
            # Verificar permisos de acceso
            if not _can_access_entrepreneur(ally_profile, entrepreneur):
                current_app.logger.warning(
                    f"Aliado {ally_profile.id} intentó acceder a emprendedor {entrepreneur_id} sin permisos"
                )
                abort(403)
            
            # Agregar emprendedor al contexto
            g.target_entrepreneur = entrepreneur
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def track_ally_activity(activity_type: str, description: Optional[str] = None):
    """
    Decorador para registrar actividades del aliado.
    
    Args:
        activity_type: Tipo de actividad realizada
        description: Descripción opcional de la actividad
        
    Returns:
        Decorador para tracking de actividad
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = f(*args, **kwargs)
                
                # Registrar actividad exitosa
                _log_ally_activity(
                    activity_type=activity_type,
                    description=description or f"Ejecutó {f.__name__}",
                    success=True,
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )
                
                return result
                
            except Exception as e:
                # Registrar actividad fallida
                _log_ally_activity(
                    activity_type=activity_type,
                    description=f"Error en {f.__name__}: {str(e)}",
                    success=False,
                    duration=(datetime.utcnow() - start_time).total_seconds(),
                    error=str(e)
                )
                raise
        
        return decorated_function
    return decorator


def validate_mentorship_session(session_id_param: str = 'session_id'):
    """
    Decorador que valida el acceso a una sesión de mentoría.
    
    Args:
        session_id_param: Nombre del parámetro que contiene el ID de la sesión
        
    Returns:
        Decorador configurado
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ally_profile = g.get('ally_profile')
            if not ally_profile:
                abort(403)
            
            session_id = kwargs.get(session_id_param) or request.view_args.get(session_id_param)
            if not session_id:
                abort(400)
            
            # Obtener sesión de mentoría
            session = MentorshipSession.query.filter_by(
                id=session_id,
                ally_id=ally_profile.id
            ).first()
            
            if not session:
                abort(404)
            
            # Agregar sesión al contexto
            g.mentorship_session = session
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# ==================== MIDDLEWARE Y HOOKS ====================

@ally_bp.before_request
def before_ally_request():
    """
    Middleware que se ejecuta antes de cada request en el módulo ally.
    
    Configura el contexto específico para aliados y realiza
    validaciones globales necesarias.
    """
    # Saltar para rutas públicas o de autenticación
    if request.endpoint and any(
        request.endpoint.startswith(prefix) 
        for prefix in ['auth.', 'static', 'main.']
    ):
        return
    
    # Aplicar validaciones de aliado para todas las rutas
    if current_user.is_authenticated and hasattr(current_user, 'ally_profile'):
        ally_profile = current_user.ally_profile
        
        if ally_profile:
            # Actualizar última actividad
            ally_profile.last_activity = datetime.utcnow()
            
            # Verificar notificaciones pendientes
            pending_notifications = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
            
            # Agregar al contexto global
            g.ally_profile = ally_profile
            g.pending_notifications = pending_notifications
            g.user_type = 'ally'
            
            try:
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error actualizando actividad del aliado: {str(e)}")
                db.session.rollback()


@ally_bp.after_request
def after_ally_request(response):
    """
    Middleware que se ejecuta después de cada request en el módulo ally.
    
    Args:
        response: Respuesta HTTP
        
    Returns:
        Respuesta modificada si es necesario
    """
    # Agregar headers de seguridad específicos para aliados
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Log de métricas de respuesta
    if hasattr(g, 'ally_profile') and g.ally_profile:
        _log_response_metrics(response)
    
    return response


@ally_bp.errorhandler(403)
def handle_forbidden(error):
    """
    Manejador de errores 403 específico para aliados.
    
    Args:
        error: Error de autorización
        
    Returns:
        Respuesta de error personalizada
    """
    if request.is_json:
        return jsonify({
            'error': 'Acceso denegado',
            'message': 'No tienes permisos para realizar esta acción',
            'code': 403
        }), 403
    
    flash('No tienes permisos para acceder a esta área', 'error')
    return redirect(url_for('ally.dashboard.index'))


@ally_bp.errorhandler(404)
def handle_not_found(error):
    """
    Manejador de errores 404 específico para aliados.
    
    Args:
        error: Error de recurso no encontrado
        
    Returns:
        Respuesta de error personalizada
    """
    if request.is_json:
        return jsonify({
            'error': 'Recurso no encontrado',
            'message': 'El recurso solicitado no existe',
            'code': 404
        }), 404
    
    flash('El recurso solicitado no fue encontrado', 'error')
    return redirect(url_for('ally.dashboard.index'))


# ==================== CONTEXT PROCESSORS ====================

@ally_bp.context_processor
def inject_ally_context():
    """
    Inyecta variables de contexto específicas para las vistas de aliados.
    
    Returns:
        Dict con variables de contexto
    """
    context = {}
    
    if hasattr(g, 'ally_profile') and g.ally_profile:
        ally_profile = g.ally_profile
        
        # Estadísticas rápidas del aliado
        context.update({
            'ally_stats': _get_ally_quick_stats(ally_profile),
            'ally_profile': ally_profile,
            'pending_notifications': g.get('pending_notifications', 0),
            'current_mentorships': _get_current_mentorships_count(ally_profile),
            'next_meeting': _get_next_meeting(ally_profile),
            'monthly_hours': _get_monthly_hours(ally_profile),
        })
        
        # Navegación específica para aliados
        context['ally_navigation'] = _get_ally_navigation_items(ally_profile)
        
        # Configuraciones y preferencias
        context['ally_preferences'] = _get_ally_preferences(ally_profile)
    
    # Utilidades de formateo para templates
    context.update({
        'format_time_duration': format_time_duration,
        'format_currency': format_currency,
        'format_date': format_date,
    })
    
    return context


# ==================== RUTAS PRINCIPALES DEL MÓDULO ====================

@ally_bp.route('/')
@login_required
@require_ally_access
def index():
    """
    Ruta principal del módulo ally - redirige al dashboard.
    
    Returns:
        Redirección al dashboard del aliado
    """
    return redirect(url_for('ally.dashboard.index'))


@ally_bp.route('/api/quick-stats')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)  # 30 calls per minute
def api_quick_stats():
    """
    API endpoint para obtener estadísticas rápidas del aliado.
    
    Returns:
        JSON con estadísticas actualizadas
    """
    try:
        ally_profile = g.ally_profile
        stats = _get_ally_quick_stats(ally_profile)
        
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo stats rápidas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


@ally_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=10, period=60)
def api_mark_notifications_read():
    """
    API endpoint para marcar notificaciones como leídas.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        notification_ids = request.json.get('notification_ids', [])
        
        if notification_ids:
            Notification.query.filter(
                Notification.id.in_(notification_ids),
                Notification.user_id == current_user.id
            ).update({
                'is_read': True,
                'read_at': datetime.utcnow()
            }, synchronize_session=False)
        else:
            # Marcar todas como leídas
            Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).update({
                'is_read': True,
                'read_at': datetime.utcnow()
            }, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Notificaciones marcadas como leídas'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error marcando notificaciones: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


# ==================== FUNCIONES AUXILIARES ====================

def _can_access_entrepreneur(ally: Ally, entrepreneur: Entrepreneur) -> bool:
    """
    Verifica si un aliado puede acceder a la información de un emprendedor.
    
    Args:
        ally: Perfil del aliado
        entrepreneur: Perfil del emprendedor
        
    Returns:
        True si tiene acceso, False en caso contrario
    """
    # Verificar si hay una relación de mentoría activa
    active_mentorship = MentorshipSession.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).first()
    
    if active_mentorship:
        return True
    
    # Verificar si está asignado al emprendedor
    if hasattr(entrepreneur, 'assigned_allies'):
        return ally in entrepreneur.assigned_allies
    
    # Verificar permisos especiales (admin, supervisor, etc.)
    if ally.role in ['admin', 'supervisor', 'coordinator']:
        return True
    
    # Verificar si pertenecen a la misma organización
    if ally.organization_id and entrepreneur.organization_id:
        return ally.organization_id == entrepreneur.organization_id
    
    return False


def _log_ally_activity(
    activity_type: str, 
    description: str, 
    success: bool = True,
    duration: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Registra una actividad del aliado en el log.
    
    Args:
        activity_type: Tipo de actividad
        description: Descripción de la actividad
        success: Si la actividad fue exitosa
        duration: Duración en segundos
        error: Mensaje de error si aplica
    """
    try:
        ally_profile = g.get('ally_profile')
        if not ally_profile:
            return
        
        activity = ActivityLog(
            user_id=ally_profile.user_id,
            action=activity_type,
            description=description,
            entity_type='ally_action',
            metadata={
                'success': success,
                'duration': duration,
                'error': error,
                'user_agent': request.headers.get('User-Agent'),
                'ip_address': request.remote_addr,
                'ally_id': ally_profile.id
            }
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando actividad del aliado: {str(e)}")
        db.session.rollback()


def _log_response_metrics(response) -> None:
    """
    Registra métricas de respuesta para análisis de rendimiento.
    
    Args:
        response: Objeto de respuesta HTTP
    """
    try:
        # Registrar métricas básicas
        metrics = {
            'status_code': response.status_code,
            'content_length': response.content_length,
            'endpoint': request.endpoint,
            'method': request.method,
            'ally_id': g.ally_profile.id if hasattr(g, 'ally_profile') else None
        }
        
        # Log solo errores o requests lentos
        if response.status_code >= 400:
            current_app.logger.warning(f"Respuesta de error para aliado: {metrics}")
        
    except Exception as e:
        current_app.logger.error(f"Error registrando métricas: {str(e)}")


def _get_ally_quick_stats(ally_profile: Ally) -> Dict[str, Any]:
    """
    Obtiene estadísticas rápidas del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Dict con estadísticas
    """
    today = datetime.utcnow().date()
    this_month = datetime.utcnow().replace(day=1).date()
    
    return {
        'active_mentorships': MentorshipSession.query.filter_by(
            ally_id=ally_profile.id,
            status='active'
        ).count(),
        
        'meetings_today': Meeting.query.filter(
            Meeting.ally_id == ally_profile.id,
            Meeting.scheduled_at >= today,
            Meeting.scheduled_at < today + timedelta(days=1)
        ).count(),
        
        'hours_this_month': db.session.query(
            db.func.sum(MentorshipSession.duration_hours)
        ).filter(
            MentorshipSession.ally_id == ally_profile.id,
            MentorshipSession.session_date >= this_month
        ).scalar() or 0,
        
        'unread_messages': Message.query.filter_by(
            recipient_id=ally_profile.user_id,
            is_read=False
        ).count(),
        
        'pending_reports': 0,  # Implementar según lógica de negocio
        
        'completion_rate': _calculate_ally_completion_rate(ally_profile)
    }


def _get_current_mentorships_count(ally_profile: Ally) -> int:
    """
    Obtiene el número de mentorías activas del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Número de mentorías activas
    """
    return MentorshipSession.query.filter_by(
        ally_id=ally_profile.id,
        status='active'
    ).count()


def _get_next_meeting(ally_profile: Ally) -> Optional[Dict[str, Any]]:
    """
    Obtiene la próxima reunión del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Datos de la próxima reunión o None
    """
    next_meeting = Meeting.query.filter(
        Meeting.ally_id == ally_profile.id,
        Meeting.scheduled_at > datetime.utcnow(),
        Meeting.status.in_(['scheduled', 'confirmed'])
    ).order_by(Meeting.scheduled_at.asc()).first()
    
    if next_meeting:
        return {
            'id': next_meeting.id,
            'title': next_meeting.title,
            'scheduled_at': next_meeting.scheduled_at,
            'entrepreneur_name': next_meeting.entrepreneur.user.full_name if next_meeting.entrepreneur else 'N/A',
            'duration': next_meeting.duration_minutes
        }
    
    return None


def _get_monthly_hours(ally_profile: Ally) -> float:
    """
    Obtiene las horas trabajadas en el mes actual.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Horas trabajadas este mes
    """
    this_month = datetime.utcnow().replace(day=1).date()
    
    return db.session.query(
        db.func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally_profile.id,
        MentorshipSession.session_date >= this_month
    ).scalar() or 0


def _get_ally_navigation_items(ally_profile: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene los elementos de navegación específicos del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Lista con elementos de navegación
    """
    navigation = [
        {
            'name': 'Dashboard',
            'url': 'ally.dashboard.index',
            'icon': 'dashboard',
            'active': request.endpoint == 'ally.dashboard.index'
        },
        {
            'name': 'Emprendedores',
            'url': 'ally.entrepreneurs.list',
            'icon': 'people',
            'active': request.endpoint and request.endpoint.startswith('ally.entrepreneurs')
        },
        {
            'name': 'Mentoría',
            'url': 'ally.mentorship.sessions',
            'icon': 'school',
            'active': request.endpoint and request.endpoint.startswith('ally.mentorship')
        },
        {
            'name': 'Calendario',
            'url': 'ally.calendar.index',
            'icon': 'calendar_today',
            'active': request.endpoint and request.endpoint.startswith('ally.calendar')
        },
        {
            'name': 'Mensajes',
            'url': 'ally.messages.inbox',
            'icon': 'message',
            'active': request.endpoint and request.endpoint.startswith('ally.messages'),
            'badge': _get_unread_messages_count(ally_profile)
        },
        {
            'name': 'Horas',
            'url': 'ally.hours.tracking',
            'icon': 'schedule',
            'active': request.endpoint and request.endpoint.startswith('ally.hours')
        },
        {
            'name': 'Reportes',
            'url': 'ally.reports.overview',
            'icon': 'assessment',
            'active': request.endpoint and request.endpoint.startswith('ally.reports')
        },
        {
            'name': 'Perfil',
            'url': 'ally.profile.view',
            'icon': 'person',
            'active': request.endpoint and request.endpoint.startswith('ally.profile')
        }
    ]
    
    # Filtrar navegación basada en permisos del aliado
    return [item for item in navigation if _ally_has_access_to(ally_profile, item['url'])]


def _get_ally_preferences(ally_profile: Ally) -> Dict[str, Any]:
    """
    Obtiene las preferencias del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Dict con preferencias
    """
    return {
        'timezone': ally_profile.timezone or 'UTC',
        'language': ally_profile.language or 'es',
        'notifications_enabled': ally_profile.notifications_enabled,
        'email_notifications': ally_profile.email_notifications,
        'theme': ally_profile.theme or 'light'
    }


def _calculate_ally_completion_rate(ally_profile: Ally) -> float:
    """
    Calcula la tasa de completitud del aliado.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Tasa de completitud como porcentaje
    """
    # Implementar lógica específica de completitud
    # Por ejemplo: sesiones completadas vs programadas
    total_sessions = MentorshipSession.query.filter_by(
        ally_id=ally_profile.id
    ).count()
    
    completed_sessions = MentorshipSession.query.filter_by(
        ally_id=ally_profile.id,
        status='completed'
    ).count()
    
    if total_sessions == 0:
        return 0.0
    
    return round((completed_sessions / total_sessions) * 100, 2)


def _get_unread_messages_count(ally_profile: Ally) -> int:
    """
    Obtiene el número de mensajes no leídos.
    
    Args:
        ally_profile: Perfil del aliado
        
    Returns:
        Número de mensajes no leídos
    """
    return Message.query.filter_by(
        recipient_id=ally_profile.user_id,
        is_read=False
    ).count()


def _ally_has_access_to(ally_profile: Ally, endpoint: str) -> bool:
    """
    Verifica si el aliado tiene acceso a un endpoint específico.
    
    Args:
        ally_profile: Perfil del aliado
        endpoint: Endpoint a verificar
        
    Returns:
        True si tiene acceso, False en caso contrario
    """
    # Implementar lógica de permisos específica
    # Por ejemplo, algunos endpoints pueden requerir roles específicos
    
    restricted_endpoints = {
        'ally.reports.admin': ['admin', 'supervisor'],
        'ally.entrepreneurs.assign': ['admin', 'coordinator'],
    }
    
    if endpoint in restricted_endpoints:
        required_roles = restricted_endpoints[endpoint]
        return ally_profile.role in required_roles
    
    return True


# ==================== REGISTRO DE BLUEPRINTS ====================

def register_ally_blueprints(app):
    """
    Registra todos los blueprints del módulo ally en la aplicación.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    try:
        # Importar blueprints
        blueprints = _import_ally_blueprints()
        
        # Registrar blueprint principal
        app.register_blueprint(ally_bp)
        
        # Registrar blueprints específicos
        for name, blueprint in blueprints.items():
            if blueprint:
                app.register_blueprint(blueprint)
                app.logger.info(f"Blueprint '{name}' registrado exitosamente")
        
        app.logger.info(f"Todos los blueprints de ally registrados: {len(blueprints)} módulos")
        
    except Exception as e:
        app.logger.error(f"Error registrando blueprints de ally: {str(e)}")
        raise


# ==================== EXPORTACIONES ====================

# Exportar elementos principales para uso externo
__all__ = [
    'ally_bp',
    'require_ally_access',
    'require_entrepreneur_access',
    'validate_mentorship_session',
    'track_ally_activity',
    'register_ally_blueprints'
]


# ==================== INICIALIZACIÓN DEL MÓDULO ====================

# Configuración automática cuando se importa el módulo
def init_ally_module():
    """
    Inicializa el módulo ally con configuraciones específicas.
    """
    current_app.logger.info("Módulo ally inicializado correctamente")


# Auto-inicialización si se ejecuta directamente
if __name__ == '__main__':
    init_ally_module()