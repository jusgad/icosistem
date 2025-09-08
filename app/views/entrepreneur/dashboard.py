"""
Dashboard del Emprendedor - Vista principal con métricas, tareas y resumen de actividades.

Este módulo contiene las vistas del dashboard principal para emprendedores,
incluyendo métricas de proyectos, próximas reuniones, tareas pendientes,
progreso de mentoría y notificaciones.
"""

from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, jsonify, g, current_app
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import joinedload

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project, ProjectStatus, PriorityLevel as ProjectPriority
from app.models.meeting import Meeting, MeetingStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.mentorship import MentorshipSession, SessionStatus
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.document import Document
from app.models.message import Message
from app.services.entrepreneur_service import EntrepreneurService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.utils.decorators import cache_response, rate_limit
from app.utils.date_utils import format_relative_time, get_week_range, get_month_range
from app.utils.formatters import format_currency, format_percentage

# Crear blueprint para el dashboard del emprendedor
entrepreneur_dashboard = Blueprint(
    'entrepreneur_dashboard', 
    __name__, 
    url_prefix='/entrepreneur'
)


@entrepreneur_dashboard.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
    else:
        g.entrepreneur = None
        g.entrepreneur_service = None


@entrepreneur_dashboard.route('/dashboard')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=300)  # Cache por 5 minutos
def index():
    """
    Vista principal del dashboard del emprendedor.
    
    Muestra un resumen completo de:
    - Métricas de proyectos
    - Próximas reuniones y citas
    - Tareas pendientes y en progreso
    - Progreso de mentoría
    - Actividad reciente
    - Notificaciones importantes
    """
    try:
        # Obtener datos básicos del emprendedor
        entrepreneur = g.entrepreneur
        if not entrepreneur:
            raise PermissionError("Perfil de emprendedor no encontrado")

        # Fechas para filtros
        today = datetime.now(timezone.utc).date()
        week_start, week_end = get_week_range(today)
        month_start, month_end = get_month_range(today)

        # === MÉTRICAS DE PROYECTOS ===
        projects_data = _get_projects_metrics(entrepreneur.id)
        
        # === PRÓXIMAS REUNIONES ===
        upcoming_meetings = _get_upcoming_meetings(entrepreneur.id, limit=5)
        
        # === TAREAS PENDIENTES ===
        pending_tasks = _get_pending_tasks(entrepreneur.id, limit=10)
        
        # === PROGRESO DE MENTORÍA ===
        mentorship_data = _get_mentorship_progress(entrepreneur.id)
        
        # === ACTIVIDAD RECIENTE ===
        recent_activity = _get_recent_activity(entrepreneur.id, limit=10)
        
        # === NOTIFICACIONES IMPORTANTES ===
        important_notifications = _get_important_notifications(entrepreneur.id, limit=5)
        
        # === DOCUMENTOS RECIENTES ===
        recent_documents = _get_recent_documents(entrepreneur.id, limit=5)
        
        # === MENSAJES NO LEÍDOS ===
        unread_messages_count = _get_unread_messages_count(entrepreneur.id)
        
        # === ANÁLISIS DE PROGRESO ===
        progress_analytics = _get_progress_analytics(entrepreneur.id)

        # Datos para el template
        dashboard_data = {
            'entrepreneur': entrepreneur,
            'projects': projects_data,
            'upcoming_meetings': upcoming_meetings,
            'pending_tasks': pending_tasks,
            'mentorship': mentorship_data,
            'recent_activity': recent_activity,
            'notifications': important_notifications,
            'recent_documents': recent_documents,
            'unread_messages_count': unread_messages_count,
            'progress_analytics': progress_analytics,
            'current_date': today,
            'week_range': (week_start, week_end),
            'month_range': (month_start, month_end)
        }

        return render_template(
            'entrepreneur/dashboard.html',
            **dashboard_data
        )

    except Exception as e:
        current_app.logger.error(f"Error en dashboard emprendedor: {str(e)}")
        return render_template('errors/500.html'), 500


@entrepreneur_dashboard.route('/dashboard/quick-stats')
@login_required
@require_role('entrepreneur')
@rate_limit("60/minute")  # 60 requests por minuto
def quick_stats():
    """
    API endpoint para obtener estadísticas rápidas del dashboard.
    Utilizado para actualizaciones en tiempo real via AJAX.
    """
    try:
        entrepreneur_id = g.entrepreneur.id
        
        # Estadísticas rápidas
        stats = {
            'active_projects': Project.query.filter_by(
                entrepreneur_id=entrepreneur_id,
                status=ProjectStatus.ACTIVE
            ).count(),
            
            'pending_tasks': Task.query.filter_by(
                entrepreneur_id=entrepreneur_id,
                status=TaskStatus.PENDING
            ).count(),
            
            'meetings_today': Meeting.query.filter(
                and_(
                    Meeting.entrepreneur_id == entrepreneur_id,
                    func.date(Meeting.scheduled_at) == datetime.now(timezone.utc).date(),
                    Meeting.status != MeetingStatus.CANCELLED
                )
            ).count(),
            
            'unread_notifications': Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count(),
            
            'completion_rate': _calculate_completion_rate(entrepreneur_id),
            
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estadísticas rápidas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error obteniendo estadísticas'
        }), 500


@entrepreneur_dashboard.route('/dashboard/tasks/toggle/<int:task_id>')
@login_required
@require_role('entrepreneur')
def toggle_task_status(task_id):
    """
    Cambiar el estado de una tarea (completada/pendiente).
    """
    try:
        task = Task.query.filter_by(
            id=task_id,
            entrepreneur_id=g.entrepreneur.id
        ).first()
        
        if not task:
            return jsonify({
                'success': False,
                'error': 'Tarea no encontrada'
            }), 404
        
        # Cambiar estado
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
        else:
            task.status = TaskStatus.PENDING
            task.completed_at = None
        
        task.updated_at = datetime.now(timezone.utc)
        task.save()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action=f"task_{'completed' if task.status == TaskStatus.COMPLETED else 'reopened'}",
            resource_type='task',
            resource_id=task.id,
            details={'task_title': task.title}
        )
        
        return jsonify({
            'success': True,
            'new_status': task.status.value,
            'message': f'Tarea {"completada" if task.status == TaskStatus.COMPLETED else "reabierta"}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error cambiando estado de tarea: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error procesando solicitud'
        }), 500


@entrepreneur_dashboard.route('/dashboard/notifications/mark-read/<int:notification_id>')
@login_required
@require_role('entrepreneur')
def mark_notification_read(notification_id):
    """
    Marcar una notificación como leída.
    """
    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if not notification:
            return jsonify({
                'success': False,
                'error': 'Notificación no encontrada'
            }), 404
        
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        notification.save()
        
        return jsonify({
            'success': True,
            'message': 'Notificación marcada como leída'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error marcando notificación: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error procesando solicitud'
        }), 500


# === FUNCIONES AUXILIARES ===

def _get_projects_metrics(entrepreneur_id):
    """Obtener métricas de proyectos del emprendedor."""
    projects = Project.query.filter_by(entrepreneur_id=entrepreneur_id).all()
    
    total_projects = len(projects)
    active_projects = len([p for p in projects if p.status == ProjectStatus.ACTIVE])
    completed_projects = len([p for p in projects if p.status == ProjectStatus.COMPLETED])
    paused_projects = len([p for p in projects if p.status == ProjectStatus.PAUSED])
    
    # Calcular progreso promedio
    if active_projects > 0:
        avg_progress = sum([p.progress_percentage for p in projects 
                          if p.status == ProjectStatus.ACTIVE]) / active_projects
    else:
        avg_progress = 0
    
    # Proyectos por prioridad
    high_priority = len([p for p in projects if p.priority == ProjectPriority.HIGH])
    medium_priority = len([p for p in projects if p.priority == ProjectPriority.MEDIUM])
    low_priority = len([p for p in projects if p.priority == ProjectPriority.LOW])
    
    return {
        'total': total_projects,
        'active': active_projects,
        'completed': completed_projects,
        'paused': paused_projects,
        'avg_progress': round(avg_progress, 1),
        'by_priority': {
            'high': high_priority,
            'medium': medium_priority,
            'low': low_priority
        },
        'projects_list': projects[:5]  # Últimos 5 proyectos
    }


def _get_upcoming_meetings(entrepreneur_id, limit=5):
    """Obtener próximas reuniones del emprendedor."""
    now = datetime.now(timezone.utc)
    
    meetings = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            Meeting.scheduled_at >= now,
            Meeting.status != MeetingStatus.CANCELLED
        )
    ).options(
        joinedload(Meeting.ally),
        joinedload(Meeting.client)
    ).order_by(Meeting.scheduled_at).limit(limit).all()
    
    return meetings


def _get_pending_tasks(entrepreneur_id, limit=10):
    """Obtener tareas pendientes del emprendedor."""
    tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=TaskStatus.PENDING
    ).order_by(
        Task.priority.desc(),
        Task.due_date.asc(),
        Task.created_at.desc()
    ).limit(limit).all()
    
    return tasks


def _get_mentorship_progress(entrepreneur_id):
    """Obtener progreso de mentoría del emprendedor."""
    # Sesiones del mes actual
    month_start, month_end = get_month_range(datetime.now(timezone.utc).date())
    
    sessions_this_month = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.scheduled_at >= month_start,
            MentorshipSession.scheduled_at <= month_end
        )
    ).count()
    
    # Total de sesiones completadas
    completed_sessions = MentorshipSession.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=SessionStatus.COMPLETED
    ).count()
    
    # Próxima sesión
    next_session = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.scheduled_at >= datetime.now(timezone.utc),
            MentorshipSession.status == SessionStatus.SCHEDULED
        )
    ).order_by(MentorshipSession.scheduled_at).first()
    
    # Horas de mentoría este mes
    monthly_hours = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.scheduled_at >= month_start,
            MentorshipSession.scheduled_at <= month_end,
            MentorshipSession.status == SessionStatus.COMPLETED
        )
    ).with_entities(func.sum(MentorshipSession.duration_minutes)).scalar() or 0
    
    return {
        'sessions_this_month': sessions_this_month,
        'total_completed': completed_sessions,
        'next_session': next_session,
        'monthly_hours': round(monthly_hours / 60, 1)  # Convertir a horas
    }


def _get_recent_activity(entrepreneur_id, limit=10):
    """Obtener actividad reciente del emprendedor."""
    activities = ActivityLog.query.filter_by(
        user_id=entrepreneur_id
    ).order_by(desc(ActivityLog.created_at)).limit(limit).all()
    
    return activities


def _get_important_notifications(entrepreneur_id, limit=5):
    """Obtener notificaciones importantes no leídas."""
    notifications = Notification.query.filter_by(
        user_id=entrepreneur_id,
        is_read=False
    ).filter(
        Notification.priority.in_(['high', 'urgent'])
    ).order_by(desc(Notification.created_at)).limit(limit).all()
    
    return notifications


def _get_recent_documents(entrepreneur_id, limit=5):
    """Obtener documentos recientes del emprendedor."""
    documents = Document.query.filter_by(
        uploaded_by=entrepreneur_id
    ).order_by(desc(Document.created_at)).limit(limit).all()
    
    return documents


def _get_unread_messages_count(entrepreneur_id):
    """Obtener cantidad de mensajes no leídos."""
    count = Message.query.filter_by(
        recipient_id=entrepreneur_id,
        is_read=False
    ).count()
    
    return count


def _get_progress_analytics(entrepreneur_id):
    """Obtener analytics de progreso del emprendedor."""
    analytics_service = AnalyticsService()
    
    # Progreso semanal
    week_progress = analytics_service.get_weekly_progress(entrepreneur_id)
    
    # Métricas de productividad
    productivity_metrics = analytics_service.get_productivity_metrics(entrepreneur_id)
    
    # Comparación con objetivos
    goals_comparison = analytics_service.get_goals_comparison(entrepreneur_id)
    
    return {
        'week_progress': week_progress,
        'productivity': productivity_metrics,
        'goals': goals_comparison
    }


def _calculate_completion_rate(entrepreneur_id):
    """Calcular tasa de finalización de tareas."""
    total_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur_id).count()
    if total_tasks == 0:
        return 0
    
    completed_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=TaskStatus.COMPLETED
    ).count()
    
    return round((completed_tasks / total_tasks) * 100, 1)


# === MANEJADORES DE ERRORES ===

@entrepreneur_dashboard.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    return jsonify({
        'success': False,
        'error': str(error)
    }), 400


@entrepreneur_dashboard.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    return jsonify({
        'success': False,
        'error': 'No tienes permisos para realizar esta acción'
    }), 403


# === CONTEXT PROCESSORS ===

@entrepreneur_dashboard.context_processor
def inject_dashboard_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_relative_time': format_relative_time,
        'format_currency': format_currency,
        'format_percentage': format_percentage,
        'ProjectStatus': ProjectStatus,
        'TaskStatus': TaskStatus,
        'TaskPriority': TaskPriority,
        'MeetingStatus': MeetingStatus
    }