# app/views/ally/dashboard.py

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from app import db

from app.views.ally import ally_bp
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.message import Message
from app.utils.decorators import ally_required

@ally_bp.route('/dashboard')
@login_required
@ally_required
def index():
    """
    Muestra el dashboard principal del aliado con información resumida.
    """
    # Obtener los emprendedores asignados al aliado actual
    assigned_entrepreneurs = Entrepreneur.query.join(
        Relationship, Relationship.entrepreneur_id == Entrepreneur.id
    ).filter(
        Relationship.ally_id == current_user.ally.id,
        Relationship.is_active == True
    ).all()
    
    # Contar el número de emprendedores asignados
    entrepreneur_count = len(assigned_entrepreneurs)
    
    # Obtener las próximas reuniones del aliado
    upcoming_meetings = Meeting.query.filter(
        Meeting.ally_id == current_user.ally.id,
        Meeting.start_time > datetime.now()
    ).order_by(Meeting.start_time).limit(5).all()
    
    # Obtener las tareas pendientes del aliado
    pending_tasks = Task.query.filter(
        Task.ally_id == current_user.ally.id,
        Task.completed == False
    ).order_by(Task.due_date).limit(10).all()
    
    # Calcular horas de acompañamiento acumuladas
    total_hours = Relationship.query.with_entities(
        func.sum(Relationship.hours_logged)
    ).filter(
        Relationship.ally_id == current_user.ally.id
    ).scalar() or 0
    
    # Obtener estadísticas de mensajes no leídos
    unread_messages_count = get_unread_messages_count(current_user.id)
    
    return render_template(
        'ally/dashboard.html',
        entrepreneur_count=entrepreneur_count,
        assigned_entrepreneurs=assigned_entrepreneurs,
        upcoming_meetings=upcoming_meetings,
        pending_tasks=pending_tasks,
        total_hours=total_hours,
        unread_messages_count=unread_messages_count
    )

@ally_bp.route('/dashboard/stats')
@login_required
@ally_required
def get_stats():
    """
    Endpoint API para obtener estadísticas del dashboard en formato JSON.
    Útil para actualizaciones dinámicas con AJAX.
    """
    # Obtener la fecha actual para calcular estadísticas específicas de tiempo
    now = datetime.now()
    
    # Obtener emprendedores más activos (con más interacciones recientes)
    active_entrepreneurs = Entrepreneur.query.join(
        Relationship, Relationship.entrepreneur_id == Entrepreneur.id
    ).filter(
        Relationship.ally_id == current_user.ally.id,
        Relationship.is_active == True
    ).order_by(
        Relationship.last_meeting_date.desc()
    ).limit(3).all()
    
    # Formatear lista de emprendedores activos para JSON
    active_entrepreneurs_list = [{
        'id': e.id,
        'name': f"{e.user.first_name} {e.user.last_name}",
        'last_activity': e.last_activity.strftime('%Y-%m-%d') if e.last_activity else None,
        'profile_url': url_for('ally.entrepreneurs.detail', entrepreneur_id=e.id)
    } for e in active_entrepreneurs]
    
    # Obtener estadísticas de reuniones recientes por tipo
    meeting_stats = db.session.query(
        Meeting.meeting_type, 
        func.count(Meeting.id)
    ).filter(
        Meeting.ally_id == current_user.ally.id,
        Meeting.start_time >= now - timedelta(days=30)
    ).group_by(
        Meeting.meeting_type
    ).all()
    
    # Formatear estadísticas de reuniones para JSON
    meeting_types = {
        meeting_type: count for meeting_type, count in meeting_stats
    }
    
    stats = {
        'entrepreneur_count': get_entrepreneur_count(),
        'hours_this_month': get_hours_this_month(),
        'pending_tasks': get_pending_tasks_count(),
        'upcoming_meetings': get_upcoming_meetings_count(),
        'unread_messages': get_unread_messages_count(current_user.id),
        'active_entrepreneurs': active_entrepreneurs_list,
        'meeting_types': meeting_types,
        'completion_rate': calculate_task_completion_rate(),
        'last_updated': now.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return jsonify(stats)

# Funciones auxiliares para obtener estadísticas específicas
def get_unread_messages_count(user_id):
    """
    Cuenta el número de mensajes no leídos para un usuario específico
    """
    return Message.query.filter(
        Message.recipient_id == user_id,
        Message.read == False
    ).count()

def get_entrepreneur_count():
    """
    Cuenta el número de emprendedores asignados al aliado actual
    """
    return Relationship.query.filter(
        Relationship.ally_id == current_user.ally.id,
        Relationship.is_active == True
    ).count()

def get_hours_this_month():
    """
    Calcula el total de horas registradas por el aliado en el mes actual
    """
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    
    return Relationship.query.with_entities(
        func.sum(Relationship.hours_logged)
    ).filter(
        Relationship.ally_id == current_user.ally.id,
        Relationship.last_meeting_date >= start_of_month,
        Relationship.last_meeting_date <= end_of_month
    ).scalar() or 0

def get_pending_tasks_count():
    """
    Cuenta el número de tareas pendientes asignadas al aliado actual
    """
    return Task.query.filter(
        Task.ally_id == current_user.ally.id,
        Task.completed == False,
        Task.due_date >= datetime.now()
    ).count()

def get_upcoming_meetings_count():
    """
    Cuenta el número de reuniones programadas para el aliado en los próximos 7 días
    """
    now = datetime.now()
    one_week_later = now + timedelta(days=7)
    
    return Meeting.query.filter(
        Meeting.ally_id == current_user.ally.id,
        Meeting.start_time >= now,
        Meeting.start_time <= one_week_later
    ).count()

# Función auxiliar para calcular tasa de finalización de tareas
def calculate_task_completion_rate():
    """
    Calcula el porcentaje de tareas completadas en los últimos 30 días
    """
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    total_tasks = Task.query.filter(
        Task.ally_id == current_user.ally.id,
        Task.created_at >= thirty_days_ago
    ).count()
    
    if total_tasks == 0:
        return 100  # Si no hay tareas, la tasa de finalización es 100%
    
    completed_tasks = Task.query.filter(
        Task.ally_id == current_user.ally.id,
        Task.created_at >= thirty_days_ago,
        Task.completed == True
    ).count()
    
    return round((completed_tasks / total_tasks) * 100, 1)