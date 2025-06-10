"""
Portal del Emprendedor - Inicialización
=======================================

Este módulo inicializa y configura todo el portal del emprendedor,
registrando blueprints, configurando middleware, y estableciendo
las configuraciones específicas para la experiencia del emprendedor.

Estructura del Portal:
- Dashboard: Visión general y métricas
- Profile: Gestión de perfil y datos personales  
- Projects: Gestión de proyectos y emprendimientos
- Mentorship: Sesiones de mentoría y seguimiento
- Calendar: Gestión de calendario y reuniones
- Documents: Repositorio de documentos
- Tasks: Gestión de tareas y objetivos
- Messages: Centro de mensajería
- Progress: Seguimiento de progreso y logros

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

from flask import Blueprint, current_app, session, request, g
from flask_login import current_user, login_required
from functools import wraps
import logging
from datetime import datetime, timedelta

# Importaciones del core del sistema
from app.core.permissions import entrepreneur_required, check_profile_completion
from app.core.exceptions import ValidationError, AuthorizationError
from app.core.constants import USER_ROLES, BUSINESS_STAGES, NOTIFICATION_TYPES

# Importaciones de modelos
from app.models import Entrepreneur, User, ActivityLog, Notification

# Importaciones de servicios
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.entrepreneur_service import EntrepreneurService

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result
from app.utils.formatters import format_currency, format_percentage

# Configurar logging específico para el portal del emprendedor
entrepreneur_logger = logging.getLogger('entrepreneur_portal')

# ============================================================================
# CONFIGURACIÓN DEL BLUEPRINT PRINCIPAL
# ============================================================================

# Crear blueprint principal del portal del emprendedor
entrepreneur_bp = Blueprint(
    'entrepreneur', 
    __name__, 
    url_prefix='/entrepreneur',
    template_folder='templates/entrepreneur',
    static_folder='static/entrepreneur',
    static_url_path='/static/entrepreneur'
)

# ============================================================================
# MIDDLEWARE Y DECORADORES ESPECÍFICOS
# ============================================================================

@entrepreneur_bp.before_app_request
def load_entrepreneur_context():
    """
    Carga contexto específico del emprendedor en cada request.
    Establece datos globales necesarios para el portal.
    """
    if request.endpoint and request.endpoint.startswith('entrepreneur.'):
        # Verificar si el usuario actual es emprendedor
        if current_user.is_authenticated and current_user.role == 'entrepreneur':
            # Cargar datos del emprendedor en el contexto global
            g.entrepreneur = current_user.entrepreneur
            g.entrepreneur_notifications = _get_entrepreneur_notifications()
            g.entrepreneur_progress = _calculate_entrepreneur_progress()
            g.recent_activities = _get_recent_entrepreneur_activities()
            
            # Verificar completitud del perfil
            g.profile_completion = _calculate_profile_completion()
            
            # Cargar configuraciones específicas del emprendedor
            g.entrepreneur_settings = _load_entrepreneur_settings()
            
            # Estadísticas rápidas
            g.quick_stats = _get_entrepreneur_quick_stats()

@entrepreneur_bp.before_request
def check_entrepreneur_access():
    """
    Verifica acceso y permisos específicos del emprendedor.
    """
    # Verificar que el usuario esté autenticado
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    
    # Verificar que el usuario sea emprendedor
    if current_user.role != 'entrepreneur':
        raise AuthorizationError("Acceso restringido al portal del emprendedor")
    
    # Verificar que el perfil de emprendedor exista y esté activo
    if not current_user.entrepreneur or not current_user.is_active:
        raise AuthorizationError("Perfil de emprendedor inactivo o inexistente")
    
    # Verificar estado del emprendedor
    if hasattr(current_user.entrepreneur, 'status') and current_user.entrepreneur.status == 'suspended':
        raise AuthorizationError("Cuenta de emprendedor suspendida")
    
    # Registrar actividad del usuario
    _track_entrepreneur_activity()

@entrepreneur_bp.after_request
def log_entrepreneur_activity(response):
    """
    Registra actividad específica del emprendedor después de cada request.
    """
    if current_user.is_authenticated and current_user.role == 'entrepreneur':
        # Actualizar último acceso
        current_user.entrepreneur.last_activity_at = datetime.utcnow()
        
        # Log específico para analytics
        if response.status_code == 200:
            entrepreneur_logger.info(
                f"Entrepreneur activity: {current_user.email} - "
                f"{request.endpoint} - {request.method}"
            )
    
    return response

@entrepreneur_bp.context_processor
def inject_entrepreneur_context():
    """
    Inyecta contexto específico del emprendedor en todos los templates.
    """
    if current_user.is_authenticated and current_user.role == 'entrepreneur':
        return {
            'entrepreneur': current_user.entrepreneur,
            'business_stages': BUSINESS_STAGES,
            'current_stage': current_user.entrepreneur.business_stage,
            'profile_completion': g.get('profile_completion', 0),
            'unread_notifications': len([n for n in g.get('entrepreneur_notifications', []) if not n.read]),
            'entrepreneur_progress': g.get('entrepreneur_progress', {}),
            'quick_stats': g.get('quick_stats', {}),
            'entrepreneur_settings': g.get('entrepreneur_settings', {})
        }
    return {}

# ============================================================================
# DECORADORES ESPECÍFICOS DEL PORTAL
# ============================================================================

def profile_completion_required(min_completion=50):
    """
    Decorador que requiere un mínimo de completitud del perfil.
    
    Args:
        min_completion (int): Porcentaje mínimo requerido (0-100)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'entrepreneur':
                raise AuthorizationError("Acceso restringido")
            
            completion = _calculate_profile_completion()
            if completion < min_completion:
                from flask import flash, redirect, url_for
                flash(f'Debes completar al menos {min_completion}% de tu perfil para acceder a esta función.', 'warning')
                return redirect(url_for('entrepreneur.profile'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def business_stage_required(required_stages):
    """
    Decorador que requiere estar en ciertas etapas de negocio.
    
    Args:
        required_stages (list): Lista de etapas requeridas
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'entrepreneur':
                raise AuthorizationError("Acceso restringido")
            
            current_stage = current_user.entrepreneur.business_stage
            if current_stage not in required_stages:
                from flask import flash, redirect, url_for
                flash(f'Esta función requiere estar en las etapas: {", ".join(required_stages)}', 'info')
                return redirect(url_for('entrepreneur.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def track_feature_usage(feature_name):
    """
    Decorador para trackear uso de features específicas.
    
    Args:
        feature_name (str): Nombre de la feature a trackear
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Registrar uso de la feature
            _log_feature_usage(feature_name)
            
            # Ejecutar función original
            result = f(*args, **kwargs)
            
            # Analytics de engagement
            _track_engagement_metric(feature_name)
            
            return result
        return decorated_function
    return decorator

# ============================================================================
# IMPORTACIÓN DE SUBMÓDULOS
# ============================================================================

# Importar todos los blueprints específicos del emprendedor
from .dashboard import entrepreneur_dashboard
from .profile import entrepreneur_profile  
from .projects import entrepreneur_projects
from .mentorship import entrepreneur_mentorship
from .calendar import entrepreneur_calendar
from .documents import entrepreneur_documents
from .tasks import entrepreneur_tasks
from .messages import entrepreneur_messages
from .progress import entrepreneur_progress

# ============================================================================
# REGISTRO DE BLUEPRINTS
# ============================================================================

def register_entrepreneur_blueprints(app):
    """
    Registra todos los blueprints del portal del emprendedor.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    try:
        # Registrar blueprint principal
        app.register_blueprint(entrepreneur_bp)
        
        # Registrar blueprints específicos
        app.register_blueprint(entrepreneur_dashboard)
        app.register_blueprint(entrepreneur_profile)
        app.register_blueprint(entrepreneur_projects)
        app.register_blueprint(entrepreneur_mentorship)
        app.register_blueprint(entrepreneur_calendar)
        app.register_blueprint(entrepreneur_documents)
        app.register_blueprint(entrepreneur_tasks)
        app.register_blueprint(entrepreneur_messages)
        app.register_blueprint(entrepreneur_progress)
        
        # Log de registro exitoso
        app.logger.info("Entrepreneur portal blueprints registered successfully")
        
    except Exception as e:
        app.logger.error(f"Error registering entrepreneur blueprints: {str(e)}")
        raise

# ============================================================================
# CONFIGURACIÓN DE ERRORES ESPECÍFICOS
# ============================================================================

@entrepreneur_bp.errorhandler(AuthorizationError)
def handle_authorization_error(error):
    """Maneja errores de autorización específicos del emprendedor."""
    from flask import render_template, flash, redirect, url_for
    
    entrepreneur_logger.warning(f"Authorization error for user {current_user.email if current_user.is_authenticated else 'anonymous'}: {str(error)}")
    flash('No tienes permisos para acceder a esta sección.', 'error')
    return redirect(url_for('auth.login'))

@entrepreneur_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Maneja errores de validación en el portal."""
    from flask import render_template, flash, request
    
    entrepreneur_logger.warning(f"Validation error: {str(error)}")
    flash(f'Error de validación: {str(error)}', 'error')
    
    # Redirigir a la página anterior o dashboard
    return redirect(request.referrer or url_for('entrepreneur.dashboard'))

@entrepreneur_bp.errorhandler(404)
def handle_not_found(error):
    """Maneja errores 404 específicos del portal."""
    from flask import render_template
    
    return render_template('entrepreneur/errors/404.html'), 404

@entrepreneur_bp.errorhandler(500)
def handle_internal_error(error):
    """Maneja errores internos del portal."""
    from flask import render_template
    from app.extensions import db
    
    db.session.rollback()
    entrepreneur_logger.error(f"Internal error in entrepreneur portal: {str(error)}")
    return render_template('entrepreneur/errors/500.html'), 500

# ============================================================================
# RUTAS PRINCIPALES DEL PORTAL
# ============================================================================

@entrepreneur_bp.route('/')
@login_required
@entrepreneur_required
@handle_exceptions
def index():
    """
    Ruta principal del portal del emprendedor.
    Redirige al dashboard.
    """
    from flask import redirect, url_for
    return redirect(url_for('entrepreneur.dashboard.index'))

@entrepreneur_bp.route('/welcome')
@login_required
@entrepreneur_required
@handle_exceptions
def welcome():
    """
    Página de bienvenida para nuevos emprendedores.
    """
    from flask import render_template
    
    # Verificar si es primera visita
    if not _is_first_visit():
        from flask import redirect, url_for
        return redirect(url_for('entrepreneur.dashboard.index'))
    
    # Datos para la página de bienvenida
    welcome_data = {
        'setup_checklist': _get_setup_checklist(),
        'recommended_actions': _get_recommended_initial_actions(),
        'available_programs': _get_available_programs(),
        'mentor_suggestions': _get_potential_mentors()
    }
    
    # Marcar como visitado
    _mark_welcome_as_seen()
    
    return render_template('entrepreneur/welcome.html', **welcome_data)

@entrepreneur_bp.route('/onboarding')
@login_required
@entrepreneur_required
@handle_exceptions
def onboarding():
    """
    Proceso de onboarding guiado para nuevos emprendedores.
    """
    from flask import render_template
    
    onboarding_data = {
        'current_step': _get_current_onboarding_step(),
        'total_steps': 5,
        'profile_completion': _calculate_profile_completion(),
        'next_actions': _get_next_onboarding_actions()
    }
    
    return render_template('entrepreneur/onboarding.html', **onboarding_data)

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_entrepreneur_notifications():
    """Obtiene notificaciones específicas del emprendedor."""
    if not current_user.is_authenticated or current_user.role != 'entrepreneur':
        return []
    
    return Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.created_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(Notification.created_at.desc()).limit(10).all()

def _calculate_entrepreneur_progress():
    """Calcula el progreso general del emprendedor."""
    if not current_user.entrepreneur:
        return {}
    
    entrepreneur = current_user.entrepreneur
    
    # Métricas de progreso
    progress = {
        'profile_completion': _calculate_profile_completion(),
        'projects_active': len([p for p in entrepreneur.projects if p.status == 'active']),
        'projects_completed': len([p for p in entrepreneur.projects if p.status == 'completed']),
        'mentorship_sessions': len(entrepreneur.mentorships),
        'documents_uploaded': len(entrepreneur.documents),
        'stage_progress': _calculate_stage_progress(),
        'overall_score': entrepreneur.evaluation_score or 0
    }
    
    return progress

def _get_recent_entrepreneur_activities():
    """Obtiene actividades recientes del emprendedor."""
    if not current_user.is_authenticated:
        return []
    
    return ActivityLog.query.filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.created_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(ActivityLog.created_at.desc()).limit(5).all()

def _calculate_profile_completion():
    """Calcula el porcentaje de completitud del perfil."""
    if not current_user.entrepreneur:
        return 0
    
    entrepreneur = current_user.entrepreneur
    user = current_user
    
    # Campos básicos requeridos
    required_fields = [
        user.first_name, user.last_name, user.email, user.phone,
        entrepreneur.business_name, entrepreneur.business_description,
        entrepreneur.business_stage, entrepreneur.industry
    ]
    
    # Campos opcionales que suman puntos
    optional_fields = [
        entrepreneur.target_market, entrepreneur.revenue_model,
        entrepreneur.team_size, entrepreneur.funding_goal,
        entrepreneur.website, entrepreneur.linkedin_profile
    ]
    
    # Calcular completitud
    basic_completion = len([f for f in required_fields if f]) / len(required_fields) * 70
    optional_completion = len([f for f in optional_fields if f]) / len(optional_fields) * 30
    
    return int(basic_completion + optional_completion)

def _load_entrepreneur_settings():
    """Carga configuraciones específicas del emprendedor."""
    default_settings = {
        'notifications_enabled': True,
        'email_notifications': True,
        'mentor_notifications': True,
        'project_reminders': True,
        'weekly_digest': True,
        'public_profile': False,
        'show_in_directory': True,
        'preferred_communication': 'email',
        'timezone': 'UTC'
    }
    
    # En un sistema real, esto vendría de una tabla de configuraciones
    return default_settings

def _get_entrepreneur_quick_stats():
    """Obtiene estadísticas rápidas del emprendedor."""
    if not current_user.entrepreneur:
        return {}
    
    entrepreneur = current_user.entrepreneur
    
    return {
        'active_projects': len([p for p in entrepreneur.projects if p.status == 'active']),
        'completed_tasks': len([t for t in entrepreneur.tasks if t.status == 'completed']),
        'upcoming_meetings': _count_upcoming_meetings(),
        'unread_messages': _count_unread_messages(),
        'mentorship_hours': _calculate_total_mentorship_hours(),
        'funding_progress': _calculate_funding_progress(),
        'network_connections': _count_network_connections()
    }

def _track_entrepreneur_activity():
    """Registra actividad específica del emprendedor."""
    if current_user.is_authenticated and current_user.role == 'entrepreneur':
        # Actualizar última actividad
        current_user.entrepreneur.last_activity_at = datetime.utcnow()
        
        # Registrar en analytics si es una página importante
        important_endpoints = [
            'entrepreneur.dashboard', 'entrepreneur.projects', 
            'entrepreneur.profile', 'entrepreneur.mentorship'
        ]
        
        if request.endpoint in important_endpoints:
            _log_page_view(request.endpoint)

def _log_feature_usage(feature_name):
    """Registra uso de features específicas."""
    try:
        analytics_service = AnalyticsService()
        analytics_service.track_feature_usage(
            user_id=current_user.id,
            feature=feature_name,
            context='entrepreneur_portal'
        )
    except Exception as e:
        entrepreneur_logger.error(f"Error logging feature usage: {str(e)}")

def _track_engagement_metric(feature_name):
    """Trackea métricas de engagement."""
    try:
        analytics_service = AnalyticsService()
        analytics_service.track_engagement(
            user_id=current_user.id,
            action=f'used_{feature_name}',
            category='entrepreneur_engagement'
        )
    except Exception as e:
        entrepreneur_logger.error(f"Error tracking engagement: {str(e)}")

def _is_first_visit():
    """Verifica si es la primera visita del emprendedor."""
    if not current_user.entrepreneur:
        return True
    
    # Verificar si hay actividad previa
    has_activity = ActivityLog.query.filter_by(user_id=current_user.id).first()
    return not has_activity

def _get_setup_checklist():
    """Obtiene checklist de configuración inicial."""
    entrepreneur = current_user.entrepreneur
    user = current_user
    
    checklist = [
        {
            'task': 'Completar perfil básico',
            'completed': bool(user.first_name and user.last_name and entrepreneur.business_name),
            'url': 'entrepreneur.profile.basic_info'
        },
        {
            'task': 'Describir tu emprendimiento',
            'completed': bool(entrepreneur.business_description),
            'url': 'entrepreneur.profile.business_info'
        },
        {
            'task': 'Definir etapa de negocio',
            'completed': bool(entrepreneur.business_stage),
            'url': 'entrepreneur.profile.business_stage'
        },
        {
            'task': 'Subir foto de perfil',
            'completed': bool(user.avatar_url),
            'url': 'entrepreneur.profile.photo'
        },
        {
            'task': 'Crear primer proyecto',
            'completed': len(entrepreneur.projects) > 0,
            'url': 'entrepreneur.projects.create'
        }
    ]
    
    return checklist

def _get_recommended_initial_actions():
    """Obtiene acciones recomendadas para nuevos emprendedores."""
    return [
        {
            'title': 'Explora programas disponibles',
            'description': 'Encuentra incubadoras y aceleradoras que se ajusten a tu emprendimiento',
            'url': 'entrepreneur.programs.browse',
            'priority': 'high'
        },
        {
            'title': 'Conecta con mentores',
            'description': 'Busca mentores con experiencia en tu industria',
            'url': 'entrepreneur.mentorship.find_mentors',
            'priority': 'high'
        },
        {
            'title': 'Únete a la comunidad',
            'description': 'Participa en eventos y conecta con otros emprendedores',
            'url': 'entrepreneur.community.events',
            'priority': 'medium'
        }
    ]

def _get_available_programs():
    """Obtiene programas disponibles para el emprendedor."""
    from app.models import Program
    
    # Filtrar programas activos y apropiados para la etapa actual
    stage = current_user.entrepreneur.business_stage
    industry = current_user.entrepreneur.industry
    
    programs = Program.query.filter(
        Program.status == 'active',
        Program.business_stages.any(stage) if stage else True,
        Program.industry_focus.any(industry) if industry else True
    ).limit(3).all()
    
    return programs

def _get_potential_mentors():
    """Obtiene mentores potenciales para el emprendedor."""
    from app.models import Ally
    
    # Filtrar mentores disponibles por industria/expertise
    industry = current_user.entrepreneur.industry
    
    mentors = Ally.query.join(User).filter(
        User.is_active == True,
        Ally.is_available == True,
        Ally.expertise_areas.any(industry) if industry else True
    ).limit(3).all()
    
    return mentors

def _mark_welcome_as_seen():
    """Marca la página de bienvenida como vista."""
    # En un sistema real, esto se guardaría en la base de datos
    session['welcome_seen'] = True

def _get_current_onboarding_step():
    """Obtiene el paso actual del onboarding."""
    completion = _calculate_profile_completion()
    
    if completion < 20:
        return 1  # Información básica
    elif completion < 40:
        return 2  # Información del negocio
    elif completion < 60:
        return 3  # Objetivos y metas
    elif completion < 80:
        return 4  # Configuración de perfil
    else:
        return 5  # Finalización

def _get_next_onboarding_actions():
    """Obtiene siguientes acciones del onboarding."""
    step = _get_current_onboarding_step()
    
    actions = {
        1: ['Completar nombre y email', 'Verificar número de teléfono'],
        2: ['Describir tu emprendimiento', 'Seleccionar industria'],
        3: ['Definir objetivos de funding', 'Establecer metas de crecimiento'],
        4: ['Subir foto de perfil', 'Completar redes sociales'],
        5: ['Crear primer proyecto', 'Buscar mentor']
    }
    
    return actions.get(step, [])

def _calculate_stage_progress():
    """Calcula progreso dentro de la etapa actual."""
    stage = current_user.entrepreneur.business_stage
    
    # Definir criterios de progreso por etapa
    stage_criteria = {
        'idea': ['business_description', 'target_market', 'revenue_model'],
        'validation': ['mvp_completed', 'customer_feedback', 'market_research'],
        'mvp': ['product_launched', 'initial_users', 'metrics_tracking'],
        'growth': ['revenue_generated', 'team_expansion', 'scaling_plan'],
        'scale': ['market_expansion', 'funding_secured', 'strategic_partnerships']
    }
    
    criteria = stage_criteria.get(stage, [])
    if not criteria:
        return 0
    
    # En un sistema real, verificaríamos estos criterios
    # Por ahora retornamos un valor simulado
    return 65

def _count_upcoming_meetings():
    """Cuenta reuniones próximas del emprendedor."""
    from app.models import Meeting
    
    return Meeting.query.filter(
        Meeting.participants.any(User.id == current_user.id),
        Meeting.scheduled_for >= datetime.utcnow(),
        Meeting.scheduled_for <= datetime.utcnow() + timedelta(days=7)
    ).count()

def _count_unread_messages():
    """Cuenta mensajes no leídos."""
    from app.models import Message
    
    return Message.query.filter(
        Message.recipient_id == current_user.id,
        Message.read_at.is_(None)
    ).count()

def _calculate_total_mentorship_hours():
    """Calcula total de horas de mentoría."""
    if not current_user.entrepreneur.mentorships:
        return 0
    
    return sum([m.total_hours for m in current_user.entrepreneur.mentorships if m.total_hours])

def _calculate_funding_progress():
    """Calcula progreso de funding."""
    entrepreneur = current_user.entrepreneur
    
    if not entrepreneur.funding_goal:
        return 0
    
    current_funding = entrepreneur.funding_raised or 0
    return (current_funding / entrepreneur.funding_goal * 100) if entrepreneur.funding_goal > 0 else 0

def _count_network_connections():
    """Cuenta conexiones en la red."""
    # En un sistema real, esto vendría de una tabla de conexiones
    return len(current_user.entrepreneur.mentorships) + len(current_user.entrepreneur.projects)

def _log_page_view(endpoint):
    """Registra vista de página en analytics."""
    try:
        analytics_service = AnalyticsService()
        analytics_service.track_page_view(
            user_id=current_user.id,
            page=endpoint,
            user_agent=request.headers.get('User-Agent'),
            ip_address=request.remote_addr
        )
    except Exception as e:
        entrepreneur_logger.error(f"Error logging page view: {str(e)}")

# ============================================================================
# INICIALIZACIÓN DEL MÓDULO
# ============================================================================

def init_entrepreneur_portal(app):
    """
    Inicializa completamente el portal del emprendedor.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    try:
        # Registrar blueprints
        register_entrepreneur_blueprints(app)
        
        # Configurar logging específico
        entrepreneur_logger.setLevel(logging.INFO)
        
        # Configurar analytics específicos del portal
        _setup_entrepreneur_analytics(app)
        
        # Configurar cache específico
        _setup_entrepreneur_cache(app)
        
        app.logger.info("Entrepreneur portal initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Error initializing entrepreneur portal: {str(e)}")
        raise

def _setup_entrepreneur_analytics(app):
    """Configura analytics específicos del portal del emprendedor."""
    # Configuración específica de analytics para emprendedores
    pass

def _setup_entrepreneur_cache(app):
    """Configura cache específico del portal del emprendedor."""
    # Configuración de cache específica para datos de emprendedores
    pass

# ============================================================================
# EXPORTAR FUNCIONES PRINCIPALES
# ============================================================================

__all__ = [
    'entrepreneur_bp',
    'register_entrepreneur_blueprints', 
    'init_entrepreneur_portal',
    'profile_completion_required',
    'business_stage_required',
    'track_feature_usage'
]