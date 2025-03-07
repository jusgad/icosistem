from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.models.task import Task
from app.models.meeting import Meeting
from app.utils.decorators import entrepreneur_required
from app.extensions import db

# Crear el Blueprint para el dashboard del emprendedor
entrepreneur_dashboard = Blueprint('entrepreneur_dashboard', __name__)

@entrepreneur_dashboard.route('/dashboard')
@login_required
@entrepreneur_required
def dashboard():
    """Vista principal del dashboard para emprendedores"""
    # Obtener el perfil del emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener las relaciones y aliados asignados
    relationships = Relationship.query.filter_by(entrepreneur_id=entrepreneur.id, status='active').all()
    ally_ids = [rel.ally_id for rel in relationships]
    allies = Ally.query.filter(Ally.id.in_(ally_ids)).all()
    
    # Obtener tareas pendientes
    pending_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='pending'
    ).order_by(Task.due_date.asc()).limit(5).all()
    
    # Obtener próximas reuniones
    from datetime import datetime
    upcoming_meetings = Meeting.query.filter(
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.start_time > datetime.now()
    ).order_by(Meeting.start_time.asc()).limit(3).all()
    
    # Obtener estadísticas de progreso
    completed_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='completed'
    ).count()
    
    total_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur.id
    ).count()
    
    if total_tasks > 0:
        progress_percentage = (completed_tasks / total_tasks) * 100
    else:
        progress_percentage = 0
    
    # Obtener horas de mentoría utilizadas vs asignadas
    from sqlalchemy.sql import func
    total_hours_used = db.session.query(func.sum(Meeting.duration)).filter(
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.status == 'completed'
    ).scalar() or 0
    
    total_hours_assigned = sum([rel.hours_assigned for rel in relationships])
    
    # Renderizar la plantilla con todos los datos
    return render_template(
        'entrepreneur/dashboard.html',
        entrepreneur=entrepreneur,
        relationships=relationships,
        allies=allies,
        pending_tasks=pending_tasks,
        upcoming_meetings=upcoming_meetings,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
        progress_percentage=progress_percentage,
        total_hours_used=total_hours_used,
        total_hours_assigned=total_hours_assigned
    )

@entrepreneur_dashboard.route('/dashboard/chart-data')
@login_required
@entrepreneur_required
def get_chart_data():
    """Endpoint para obtener datos para los gráficos del dashboard"""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    chart_type = request.args.get('type', 'tasks')
    
    if chart_type == 'tasks':
        # Datos para el gráfico de tareas por estado
        from sqlalchemy import func
        task_stats = db.session.query(
            Task.status, func.count(Task.id)
        ).filter(
            Task.entrepreneur_id == entrepreneur.id
        ).group_by(Task.status).all()
        
        # Formatear datos para el gráfico
        labels = [status for status, _ in task_stats]
        data = [count for _, count in task_stats]
        colors = ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0']
        
        return jsonify({
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': colors[:len(data)]
            }]
        })
    
    elif chart_type == 'meetings':
        # Datos para el gráfico de reuniones por mes
        from sqlalchemy import func, extract
        from datetime import datetime, timedelta
        
        # Obtener los últimos 6 meses
        today = datetime.now()
        months = []
        for i in range(5, -1, -1):
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            months.append((year, month))
        
        # Consultar reuniones por mes
        meeting_counts = []
        month_labels = []
        
        for year, month in months:
            count = Meeting.query.filter(
                Meeting.entrepreneur_id == entrepreneur.id,
                extract('year', Meeting.start_time) == year,
                extract('month', Meeting.start_time) == month
            ).count()
            
            meeting_counts.append(count)
            month_labels.append(f"{year}-{month:02d}")
        
        return jsonify({
            'labels': month_labels,
            'datasets': [{
                'label': 'Reuniones por mes',
                'data': meeting_counts,
                'fill': False,
                'borderColor': '#36a2eb',
                'tension': 0.1
            }]
        })
    
    elif chart_type == 'hours':
        # Datos para el gráfico de horas de mentoría por aliado
        from sqlalchemy import func
        
        # Obtener relaciones activas
        relationships = Relationship.query.filter_by(
            entrepreneur_id=entrepreneur.id, 
            status='active'
        ).all()
        
        data = []
        labels = []
        
        for relationship in relationships:
            ally = Ally.query.get(relationship.ally_id)
            
            # Calcular horas utilizadas con este aliado
            hours_used = db.session.query(func.sum(Meeting.duration)).filter(
                Meeting.entrepreneur_id == entrepreneur.id,
                Meeting.ally_id == ally.id,
                Meeting.status == 'completed'
            ).scalar() or 0
            
            data.append(hours_used)
            
            # Obtener el nombre del aliado
            user = db.session.query(db.models.User).get(ally.user_id)
            labels.append(user.name)
        
        return jsonify({
            'labels': labels,
            'datasets': [{
                'label': 'Horas utilizadas por aliado',
                'data': data,
                'backgroundColor': ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0'][:len(data)]
            }]
        })
    
    # Tipo de gráfico no reconocido
    return jsonify({'error': 'Tipo de gráfico no válido'}), 400

@entrepreneur_dashboard.route('/dashboard/activity')
@login_required
@entrepreneur_required
def recent_activity():
    """Endpoint para obtener actividad reciente del emprendedor"""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Combinar diferentes tipos de actividades
    from datetime import datetime, timedelta
    last_week = datetime.now() - timedelta(days=7)
    
    # Tareas recientes
    recent_tasks = Task.query.filter(
        Task.entrepreneur_id == entrepreneur.id,
        Task.created_at > last_week
    ).order_by(Task.created_at.desc()).all()
    
    # Reuniones recientes
    recent_meetings = Meeting.query.filter(
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.created_at > last_week
    ).order_by(Meeting.created_at.desc()).all()
    
    # Combinar y ordenar por fecha (las más recientes primero)
    activities = []
    
    for task in recent_tasks:
        activities.append({
            'type': 'task',
            'date': task.created_at,
            'title': f"Tarea: {task.title}",
            'description': task.description[:100] + "..." if len(task.description) > 100 else task.description,
            'status': task.status
        })
    
    for meeting in recent_meetings:
        activities.append({
            'type': 'meeting',
            'date': meeting.created_at,
            'title': f"Reunión: {meeting.title}",
            'description': f"Fecha: {meeting.start_time.strftime('%d/%m/%Y %H:%M')}",
            'status': meeting.status
        })
    
    # Ordenar por fecha (las más recientes primero)
    activities.sort(key=lambda x: x['date'], reverse=True)
    
    # Limitar a 10 actividades
    activities = activities[:10]
    
    return jsonify({
        'activities': activities
    })