from flask import Blueprint, render_template, current_app
from flask_login import login_required
from sqlalchemy import func, desc, case, extract
from datetime import datetime, timedelta
import calendar

from app.utils.decorators import admin_required
from app.extensions import db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.message import Message

# Crear Blueprint para las rutas del dashboard de administrador
admin_dashboard = Blueprint('admin_dashboard', __name__)

@admin_dashboard.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    """Vista principal del dashboard de administración."""
    # Obtener fecha actual y cálculo de períodos
    today = datetime.utcnow().date()
    start_of_month = datetime(today.year, today.month, 1).date()
    end_of_month = datetime(today.year, today.month, 
                           calendar.monthrange(today.year, today.month)[1]).date()
    start_of_prev_month = (start_of_month - timedelta(days=1)).replace(day=1)
    
    # Estadísticas de usuarios
    user_stats = {
        'total': User.query.count(),
        'active': User.query.filter_by(is_active=True).count(),
        'inactive': User.query.filter_by(is_active=False).count(),
        'admins': User.query.filter_by(role='admin', is_active=True).count(),
        'entrepreneurs': User.query.filter_by(role='entrepreneur', is_active=True).count(),
        'allies': User.query.filter_by(role='ally', is_active=True).count(),
        'clients': User.query.filter_by(role='client', is_active=True).count(),
        'new_this_month': User.query.filter(
            User.created_at >= start_of_month,
            User.created_at <= end_of_month
        ).count(),
    }
    
    # Estadísticas de emprendedores
    entrepreneur_stats = {
        'total': Entrepreneur.query.count(),
        'active': Entrepreneur.query.join(User).filter(User.is_active == True).count(),
        'with_ally': db.session.query(func.count(Entrepreneur.id.distinct()))
            .join(Relationship, Relationship.entrepreneur_id == Entrepreneur.id)
            .filter(Relationship.is_active == True).scalar() or 0,
        'without_ally': db.session.query(func.count(Entrepreneur.id))
            .outerjoin(
                Relationship, 
                (Relationship.entrepreneur_id == Entrepreneur.id) & (Relationship.is_active == True)
            )
            .filter(Relationship.id == None)
            .scalar() or 0,
        'new_this_month': Entrepreneur.query.filter(
            Entrepreneur.created_at >= start_of_month,
            Entrepreneur.created_at <= end_of_month
        ).count(),
    }
    
    # Estadísticas de aliados
    ally_stats = {
        'total': Ally.query.count(),
        'active': Ally.query.join(User).filter(User.is_active == True).count(),
        'with_entrepreneurs': db.session.query(func.count(Ally.id.distinct()))
            .join(Relationship, Relationship.ally_id == Ally.id)
            .filter(Relationship.is_active == True).scalar() or 0,
        'new_this_month': Ally.query.filter(
            Ally.created_at >= start_of_month,
            Ally.created_at <= end_of_month
        ).count(),
    }
    
    # Estadísticas de relaciones activas
    relationship_stats = {
        'total_active': Relationship.query.filter_by(is_active=True).count(),
        'ended_this_month': Relationship.query.filter(
            Relationship.is_active == False,
            Relationship.end_date >= start_of_month,
            Relationship.end_date <= end_of_month
        ).count(),
        'new_this_month': Relationship.query.filter(
            Relationship.start_date >= start_of_month,
            Relationship.start_date <= end_of_month
        ).count(),
        'avg_duration': db.session.query(
            func.avg(
                case(
                    [(Relationship.is_active == True, 
                      func.julianday(func.current_date()) - func.julianday(Relationship.start_date))],
                    else_=func.julianday(Relationship.end_date) - func.julianday(Relationship.start_date)
                )
            )
        ).scalar() or 0,
    }
    
    # Convertir duración promedio de días a meses (aproximado)
    relationship_stats['avg_duration_months'] = round(relationship_stats['avg_duration'] / 30, 1)
    
    # Estadísticas de actividad
    activity_stats = {
        'meetings_this_month': Meeting.query.filter(
            Meeting.start_time >= start_of_month,
            Meeting.start_time <= end_of_month
        ).count(),
        'tasks_completed_this_month': Task.query.filter(
            Task.completed_at >= start_of_month,
            Task.completed_at <= end_of_month
        ).count(),
        'tasks_pending': Task.query.filter_by(completed_at=None).count(),
        'messages_this_month': Message.query.filter(
            Message.created_at >= start_of_month,
            Message.created_at <= end_of_month
        ).count(),
    }
    
    # Datos para gráficos
    
    # Nuevos usuarios por mes (últimos 6 meses)
    six_months_ago = today.replace(day=1) - timedelta(days=1)
    six_months_ago = six_months_ago.replace(day=1) - timedelta(days=180)
    
    user_growth = db.session.query(
        func.strftime('%Y-%m', User.created_at).label('month'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= six_months_ago
    ).group_by(
        'month'
    ).order_by(
        'month'
    ).all()
    
    user_growth_data = {
        'labels': [item[0] for item in user_growth],
        'data': [item[1] for item in user_growth],
    }
    
    # Distribución de emprendedores por sector
    sector_distribution = db.session.query(
        Entrepreneur.sector,
        func.count(Entrepreneur.id).label('count')
    ).group_by(
        Entrepreneur.sector
    ).order_by(
        desc('count')
    ).all()
    
    sector_data = {
        'labels': [item[0] for item in sector_distribution],
        'data': [item[1] for item in sector_distribution],
    }
    
    # Distribución de emprendedores por fase
    phase_distribution = db.session.query(
        Entrepreneur.phase,
        func.count(Entrepreneur.id).label('count')
    ).group_by(
        Entrepreneur.phase
    ).order_by(
        desc('count')
    ).all()
    
    phase_data = {
        'labels': [item[0] for item in phase_distribution],
        'data': [item[1] for item in phase_distribution],
    }
    
    # Actividad de reuniones por mes
    meeting_activity = db.session.query(
        func.strftime('%Y-%m', Meeting.start_time).label('month'),
        func.count(Meeting.id).label('count')
    ).filter(
        Meeting.start_time >= six_months_ago
    ).group_by(
        'month'
    ).order_by(
        'month'
    ).all()
    
    meeting_activity_data = {
        'labels': [item[0] for item in meeting_activity],
        'data': [item[1] for item in meeting_activity],
    }
    
    # Aliados más activos (por número de reuniones)
    top_allies = db.session.query(
        User.first_name, 
        User.last_name,
        func.count(Meeting.id).label('meeting_count')
    ).join(
        Ally, Ally.user_id == User.id
    ).join(
        Meeting, Meeting.ally_id == Ally.id
    ).filter(
        Meeting.start_time >= start_of_month,
        Meeting.start_time <= end_of_month
    ).group_by(
        User.id
    ).order_by(
        desc('meeting_count')
    ).limit(5).all()
    
    # Emprendedores sin actividad reciente (sin reuniones en el último mes)
    inactive_entrepreneurs = db.session.query(
        Entrepreneur.id,
        Entrepreneur.company_name,
        User.first_name,
        User.last_name,
        User.email,
        func.max(Meeting.start_time).label('last_activity')
    ).join(
        User, User.id == Entrepreneur.user_id
    ).outerjoin(
        Meeting, Meeting.entrepreneur_id == Entrepreneur.id
    ).group_by(
        Entrepreneur.id
    ).having(
        (func.max(Meeting.start_time) < start_of_month) | 
        (func.max(Meeting.start_time).is_(None))
    ).order_by(
        func.max(Meeting.start_time).asc().nullslast()
    ).limit(10).all()
    
    # Emprendedores por ubicación
    location_distribution = db.session.query(
        Entrepreneur.location,
        func.count(Entrepreneur.id).label('count')
    ).group_by(
        Entrepreneur.location
    ).order_by(
        desc('count')
    ).limit(10).all()
    
    location_data = {
        'labels': [item[0] for item in location_distribution],
        'data': [item[1] for item in location_distribution],
    }
    
    return render_template(
        'admin/dashboard.html',
        user_stats=user_stats,
        entrepreneur_stats=entrepreneur_stats,
        ally_stats=ally_stats,
        relationship_stats=relationship_stats,
        activity_stats=activity_stats,
        user_growth_data=user_growth_data,
        sector_data=sector_data,
        phase_data=phase_data,
        meeting_activity_data=meeting_activity_data,
        top_allies=top_allies,
        inactive_entrepreneurs=inactive_entrepreneurs,
        location_data=location_data,
        today=today,
        start_of_month=start_of_month,
        end_of_month=end_of_month
    )


@admin_dashboard.route('/admin/dashboard/activity')
@login_required
@admin_required
def activity_dashboard():
    """Dashboard secundario enfocado en actividad reciente."""
    # Obtener fecha actual y cálculo de períodos
    today = datetime.utcnow().date()
    last_30_days = today - timedelta(days=30)
    
    # Reuniones recientes
    recent_meetings = Meeting.query.filter(
        Meeting.start_time >= last_30_days
    ).order_by(
        Meeting.start_time.desc()
    ).limit(10).all()
    
    # Tareas completadas recientemente
    recent_completed_tasks = Task.query.filter(
        Task.completed_at >= last_30_days
    ).order_by(
        Task.completed_at.desc()
    ).limit(10).all()
    
    # Tareas próximas a vencer
    upcoming_tasks = Task.query.filter(
        Task.completed_at.is_(None),
        Task.due_date >= today,
        Task.due_date <= today + timedelta(days=7)
    ).order_by(
        Task.due_date.asc()
    ).limit(10).all()
    
    # Relaciones recientemente iniciadas
    new_relationships = Relationship.query.filter(
        Relationship.start_date >= last_30_days
    ).order_by(
        Relationship.start_date.desc()
    ).limit(10).all()
    
    # Relaciones recientemente finalizadas
    ended_relationships = Relationship.query.filter(
        Relationship.is_active == False,
        Relationship.end_date >= last_30_days
    ).order_by(
        Relationship.end_date.desc()
    ).limit(10).all()
    
    # Nuevos usuarios registrados
    new_users = User.query.filter(
        User.created_at >= last_30_days
    ).order_by(
        User.created_at.desc()
    ).limit(10).all()
    
    # Estadísticas de actividad diaria (últimos 30 días)
    daily_activity = db.session.query(
        func.date(Meeting.start_time).label('date'),
        func.count(Meeting.id).label('meeting_count')
    ).filter(
        Meeting.start_time >= last_30_days
    ).group_by(
        'date'
    ).order_by(
        'date'
    ).all()
    
    daily_activity_data = {
        'labels': [str(item[0]) for item in daily_activity],
        'data': [item[1] for item in daily_activity],
    }
    
    # Distribución de actividad por día de la semana
    weekday_activity = db.session.query(
        extract('dow', Meeting.start_time).label('weekday'),
        func.count(Meeting.id).label('count')
    ).filter(
        Meeting.start_time >= last_30_days
    ).group_by(
        'weekday'
    ).order_by(
        'weekday'
    ).all()
    
    # Convertir números de día de la semana (0-6) a nombres
    weekday_names = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
    weekday_data = {
        'labels': [weekday_names[item[0]] for item in weekday_activity],
        'data': [item[1] for item in weekday_activity],
    }
    
    return render_template(
        'admin/activity_dashboard.html',
        recent_meetings=recent_meetings,
        recent_completed_tasks=recent_completed_tasks,
        upcoming_tasks=upcoming_tasks,
        new_relationships=new_relationships,
        ended_relationships=ended_relationships,
        new_users=new_users,
        daily_activity_data=daily_activity_data,
        weekday_data=weekday_data,
        today=today,
        last_30_days=last_30_days
    )


@admin_dashboard.route('/admin/dashboard/metrics')
@login_required
@admin_required
def metrics_dashboard():
    """Dashboard terciario enfocado en métricas y KPIs."""
    # Obtener fecha actual y cálculo de períodos
    today = datetime.utcnow().date()
    start_of_month = datetime(today.year, today.month, 1).date()
    start_of_prev_month = (start_of_month - timedelta(days=1)).replace(day=1)
    start_of_year = datetime(today.year, 1, 1).date()
    
    # KPI: Retención de emprendedores (% que siguen activos después de 3 meses)
    three_months_ago = today - timedelta(days=90)
    entrepreneurs_3m_ago = Entrepreneur.query.filter(
        Entrepreneur.created_at <= three_months_ago
    ).count()
    
    if entrepreneurs_3m_ago > 0:
        still_active = Entrepreneur.query.join(User).filter(
            Entrepreneur.created_at <= three_months_ago,
            User.is_active == True
        ).count()
        retention_rate = round((still_active / entrepreneurs_3m_ago) * 100, 1)
    else:
        retention_rate = 0
    
    # KPI: Promedio de reuniones por relación/mes
    avg_meetings = db.session.query(
        func.avg(func.count(Meeting.id))
    ).filter(
        Meeting.start_time >= start_of_prev_month,
        Meeting.start_time < start_of_month
    ).join(
        Relationship, Relationship.id == Meeting.relationship_id
    ).group_by(
        Relationship.id
    ).scalar() or 0
    
    # KPI: Tasa de completado de tareas (% de tareas completadas a tiempo)
    tasks_due_last_month = Task.query.filter(
        Task.due_date >= start_of_prev_month,
        Task.due_date < start_of_month
    ).count()
    
    if tasks_due_last_month > 0:
        tasks_completed_on_time = Task.query.filter(
            Task.due_date >= start_of_prev_month,
            Task.due_date < start_of_month,
            Task.completed_at <= Task.due_date
        ).count()
        task_completion_rate = round((tasks_completed_on_time / tasks_due_last_month) * 100, 1)
    else:
        task_completion_rate = 0
    
    # KPI: Tiempo promedio de respuesta en mensajes (horas)
    avg_response_time = db.session.query(
        func.avg(
            func.julianday(Message.created_at) - func.julianday(
                db.session.query(Message.created_at)
                .filter(Message.conversation_id == Message.conversation_id)
                .filter(Message.sender_id != Message.sender_id)
                .filter(Message.created_at < Message.created_at)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ) * 24  # Convertir de días a horas
    ).filter(
        Message.created_at >= start_of_month
    ).scalar() or 0
    
    # KPI: Satisfacción de emprendedores (promedio de evaluaciones)
    # Suponiendo que hay un modelo de evaluación que los emprendedores completan
    # Esta es una implementación de ejemplo
    entrepreneur_satisfaction = 4.2  # De 1 a 5, ejemplo
    
    # KPI: Crecimiento mes a mes
    prev_month_entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.created_at < start_of_month
    ).count()
    
    current_entrepreneurs = Entrepreneur.query.count()
    
    if prev_month_entrepreneurs > 0:
        growth_rate = round(((current_entrepreneurs - prev_month_entrepreneurs) / prev_month_entrepreneurs) * 100, 1)
    else:
        growth_rate = 100  # Si no había emprendedores el mes anterior
    
    # KPIs adicionales
    kpis = {
        'retention_rate': retention_rate,
        'avg_meetings_per_relationship': round(avg_meetings, 1),
        'task_completion_rate': task_completion_rate,
        'avg_response_time': round(avg_response_time, 1),
        'entrepreneur_satisfaction': entrepreneur_satisfaction,
        'growth_rate': growth_rate
    }
    
    # Datos para gráficos de tendencias
    
    # Tendencia de retención (últimos 6 meses)
    retention_trend = []
    for i in range(6, 0, -1):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        three_months_before = month_date - timedelta(days=90)
        
        count_before = Entrepreneur.query.filter(
            Entrepreneur.created_at <= three_months_before
        ).count()
        
        if count_before > 0:
            still_active_count = Entrepreneur.query.join(User).filter(
                Entrepreneur.created_at <= three_months_before,
                User.is_active == True
            ).filter(
                Entrepreneur.created_at >= three_months_before - timedelta(days=30)
            ).count()
            
            month_retention = round((still_active_count / count_before) * 100, 1)
        else:
            month_retention = 0
            
        retention_trend.append({
            'month': month_date.strftime('%Y-%m'),
            'rate': month_retention
        })
    
    retention_trend_data = {
        'labels': [item['month'] for item in retention_trend],
        'data': [item['rate'] for item in retention_trend],
    }
    
    # Tendencia de satisfacción (datos simulados)
    # En una implementación real, estos datos vendrían de una tabla de encuestas
    satisfaction_trend = [
        {'month': '2023-01', 'score': 4.0},
        {'month': '2023-02', 'score': 4.1},
        {'month': '2023-03', 'score': 4.0},
        {'month': '2023-04', 'score': 4.2},
        {'month': '2023-05', 'score': 4.3},
        {'month': '2023-06', 'score': 4.2},
    ]
    
    satisfaction_trend_data = {
        'labels': [item['month'] for item in satisfaction_trend],
        'data': [item['score'] for item in satisfaction_trend],
    }
    
    return render_template(
        'admin/metrics_dashboard.html',
        kpis=kpis,
        retention_trend_data=retention_trend_data,
        satisfaction_trend_data=satisfaction_trend_data,
        today=today
    )