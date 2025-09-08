"""
Servicio para el Dashboard de Cliente.
Encapsula la lógica de negocio para obtener y procesar los datos
que se muestran en el panel principal del usuario.

Versión: 1.0
Autor: Gemini Code Assist
"""

from flask_login import current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Project, Meeting, Task, ActivityLog
from app.models.user import User

class DashboardService:
    """
    Servicio para manejar la lógica del dashboard del cliente.
    """

    def get_user_dashboard_data(self, user: User) -> dict:
        """
        Obtiene todos los datos necesarios para el dashboard de un usuario.

        :param user: El objeto de usuario para el que se obtienen los datos.
        :return: Un diccionario con los datos del dashboard.
        """
        if not user or not user.is_authenticated:
            return {}

        # Métricas clave usando las propiedades del modelo User
        key_metrics = {
            'projects_count': user.projects_count,
            'meetings_count': user.meetings_count,
            'tasks_count': user.tasks_count,
            'progress_percentage': self._calculate_overall_progress(user)
        }

        # Actividades recientes
        recent_activities = ActivityLog.query.filter_by(
            user_id=user.id
        ).order_by(desc(ActivityLog.created_at)).limit(5).all()

        # Próximas reuniones
        upcoming_meetings = Meeting.query.filter(
            Meeting.organizer_id == user.id,
            Meeting.scheduled_for >= datetime.utcnow()
        ).order_by(Meeting.scheduled_for.asc()).limit(3).all()

        # Tareas pendientes
        pending_tasks = Task.query.filter(
            Task.assigned_to == user.id,
            Task.status.in_(['pending', 'in_progress'])
        ).order_by(Task.due_date.asc()).limit(3).all()

        # Estado de los proyectos
        projects_status = db.session.query(
            Project.status, func.count(Project.id)
        ).filter(
            Project.entrepreneur_id == user.id
        ).group_by(Project.status).all()

        return {
            'user': user,
            'key_metrics': key_metrics,
            'recent_activities': recent_activities,
            'upcoming_meetings': upcoming_meetings,
            'pending_tasks': pending_tasks,
            'projects_status': dict(projects_status)
        }

    def _calculate_overall_progress(self, user: User) -> int:
        """
        Calcula el progreso general del usuario basado en sus proyectos.
        """
        projects = Project.query.filter_by(entrepreneur_id=user.id).all()
        if not projects:
            return 0
        
        total_progress = sum(p.progress for p in projects)
        return int(total_progress / len(projects))
