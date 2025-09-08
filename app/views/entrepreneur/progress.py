"""
Módulo de vistas para el seguimiento de progreso de emprendedores.

Este módulo contiene todas las rutas y funcionalidades relacionadas con
el monitoreo y seguimiento del progreso de los emprendedores en sus proyectos,
objetivos, tareas y desarrollo general dentro del ecosistema.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, extract
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import Forbidden

from app.core.exceptions import ValidationError, BusinessLogicError
from app.core.permissions import require_entrepreneur, require_active_user
from app.models import (
    db, User, Entrepreneur, Project, Task, Meeting, 
    MentorshipSession, Document, Notification, ActivityLog, 
    Analytics, Program, Organization
)
from app.forms.entrepreneur import (
    ProgressUpdateForm, GoalSettingForm, MilestoneForm,
    ProgressFilterForm, ObjectiveForm
)
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.project_service import ProjectService
from app.utils.decorators import require_json, validate_pagination
from app.utils.formatters import format_currency, format_percentage, format_date
from app.utils.export_utils import export_to_pdf, export_to_excel
from app.utils.cache_utils import cache_key, invalidate_cache


# Crear blueprint para las rutas de progreso
progress_bp = Blueprint(
    'entrepreneur_progress', 
    __name__, 
    url_prefix='/entrepreneur/progress'
)


@progress_bp.before_request
@login_required
@require_active_user
@require_entrepreneur
def before_request():
    """
    Middleware que se ejecuta antes de cada request.
    Valida que el usuario sea un emprendedor activo.
    """
    pass


# ==================== RUTAS PRINCIPALES ====================

@progress_bp.route('/')
@progress_bp.route('/dashboard')
def dashboard():
    """
    Dashboard principal de progreso del emprendedor.
    
    Muestra una vista general del progreso en proyectos, objetivos,
    tareas completadas, sesiones de mentoría y métricas clave.
    
    Returns:
        Template renderizado con datos de progreso
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Obtener período de tiempo para análisis (último mes por defecto)
        period = request.args.get('period', '30')
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Datos principales del dashboard
        dashboard_data = _get_dashboard_data(entrepreneur, start_date, end_date)
        
        # Métricas de rendimiento
        performance_metrics = _calculate_performance_metrics(
            entrepreneur, start_date, end_date
        )
        
        # Próximos hitos y objetivos
        upcoming_milestones = _get_upcoming_milestones(entrepreneur)
        
        # Actividad reciente
        recent_activities = _get_recent_activities(entrepreneur, limit=10)
        
        # Recomendaciones basadas en progreso
        recommendations = _generate_progress_recommendations(entrepreneur)
        
        return render_template(
            'entrepreneur/progress/dashboard.html',
            dashboard_data=dashboard_data,
            performance_metrics=performance_metrics,
            upcoming_milestones=upcoming_milestones,
            recent_activities=recent_activities,
            recommendations=recommendations,
            current_period=period
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de progreso: {str(e)}")
        flash('Error al cargar el dashboard de progreso', 'error')
        return redirect(url_for('entrepreneur.dashboard'))


@progress_bp.route('/projects')
def projects_progress():
    """
    Vista detallada del progreso en proyectos.
    
    Muestra el avance de todos los proyectos del emprendedor
    con métricas específicas, hitos y estado actual.
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Filtros de búsqueda
        filter_form = ProgressFilterForm(request.args)
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort', 'updated_at')
        order = request.args.get('order', 'desc')
        
        # Query base para proyectos
        projects_query = Project.query.filter_by(
            entrepreneur_id=entrepreneur.id
        ).options(
            joinedload(Project.tasks),
            joinedload(Project.documents),
            joinedload(Project.meetings)
        )
        
        # Aplicar filtros
        if status_filter != 'all':
            projects_query = projects_query.filter_by(status=status_filter)
        
        # Aplicar ordenamiento
        if hasattr(Project, sort_by):
            order_func = desc if order == 'desc' else asc
            projects_query = projects_query.order_by(order_func(getattr(Project, sort_by)))
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        projects = projects_query.paginate(
            page=page, per_page=10, error_out=False
        )
        
        # Calcular progreso para cada proyecto
        projects_with_progress = []
        for project in projects.items:
            progress_data = _calculate_project_progress(project)
            projects_with_progress.append({
                'project': project,
                'progress': progress_data
            })
        
        # Estadísticas generales
        total_projects = Project.query.filter_by(entrepreneur_id=entrepreneur.id).count()
        active_projects = Project.query.filter_by(
            entrepreneur_id=entrepreneur.id, status='active'
        ).count()
        completed_projects = Project.query.filter_by(
            entrepreneur_id=entrepreneur.id, status='completed'
        ).count()
        
        stats = {
            'total': total_projects,
            'active': active_projects,
            'completed': completed_projects,
            'completion_rate': (completed_projects / total_projects * 100) if total_projects > 0 else 0
        }
        
        return render_template(
            'entrepreneur/progress/projects.html',
            projects=projects,
            projects_with_progress=projects_with_progress,
            filter_form=filter_form,
            stats=stats,
            current_status=status_filter,
            current_sort=sort_by,
            current_order=order
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en progreso de proyectos: {str(e)}")
        flash('Error al cargar el progreso de proyectos', 'error')
        return redirect(url_for('entrepreneur_progress.dashboard'))


@progress_bp.route('/goals')
def goals_overview():
    """
    Vista general de objetivos y metas del emprendedor.
    
    Muestra objetivos a corto, medio y largo plazo con
    su progreso actual y fechas límite.
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Obtener objetivos por categoría temporal
        short_term_goals = _get_goals_by_timeframe(entrepreneur, 'short_term')
        medium_term_goals = _get_goals_by_timeframe(entrepreneur, 'medium_term')
        long_term_goals = _get_goals_by_timeframe(entrepreneur, 'long_term')
        
        # Calcular progreso general de objetivos
        goals_progress = _calculate_overall_goals_progress(entrepreneur)
        
        # Objetivos próximos a vencer
        urgent_goals = _get_urgent_goals(entrepreneur)
        
        # Historial de objetivos completados
        completed_goals = _get_completed_goals(entrepreneur, limit=5)
        
        return render_template(
            'entrepreneur/progress/goals.html',
            short_term_goals=short_term_goals,
            medium_term_goals=medium_term_goals,
            long_term_goals=long_term_goals,
            goals_progress=goals_progress,
            urgent_goals=urgent_goals,
            completed_goals=completed_goals
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de objetivos: {str(e)}")
        flash('Error al cargar los objetivos', 'error')
        return redirect(url_for('entrepreneur_progress.dashboard'))


@progress_bp.route('/analytics')
def analytics_detail():
    """
    Vista detallada de analytics y métricas de progreso.
    
    Proporciona análisis profundo del rendimiento del emprendedor
    con gráficos, tendencias y comparativas.
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Período de análisis
        period = request.args.get('period', '90')
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Generar analytics usando el servicio
        analytics_service = AnalyticsService()
        
        # Métricas de productividad
        productivity_metrics = analytics_service.get_productivity_metrics(
            entrepreneur.id, start_date, end_date
        )
        
        # Tendencias temporales
        time_trends = analytics_service.get_time_based_trends(
            entrepreneur.id, start_date, end_date
        )
        
        # Análisis comparativo (vs otros emprendedores)
        comparative_analysis = analytics_service.get_comparative_analysis(
            entrepreneur.id, start_date, end_date
        )
        
        # Predicciones basadas en tendencias actuales
        predictions = analytics_service.generate_predictions(
            entrepreneur.id, start_date, end_date
        )
        
        # Métricas de engagement con mentores
        mentorship_metrics = _get_mentorship_engagement_metrics(entrepreneur)
        
        return render_template(
            'entrepreneur/progress/analytics.html',
            productivity_metrics=productivity_metrics,
            time_trends=time_trends,
            comparative_analysis=comparative_analysis,
            predictions=predictions,
            mentorship_metrics=mentorship_metrics,
            current_period=period
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics detallado: {str(e)}")
        flash('Error al generar analytics', 'error')
        return redirect(url_for('entrepreneur_progress.dashboard'))


# ==================== RUTAS DE ACCIÓN ====================

@progress_bp.route('/update', methods=['GET', 'POST'])
def update_progress():
    """
    Actualización manual del progreso en proyectos y objetivos.
    
    Permite al emprendedor actualizar manualmente el estado
    de sus proyectos, tareas y objetivos.
    """
    form = ProgressUpdateForm()
    entrepreneur = current_user.entrepreneur_profile
    
    if form.validate_on_submit():
        try:
            # Procesar actualizaciones
            updates_data = {
                'project_id': form.project_id.data,
                'progress_percentage': form.progress_percentage.data,
                'status_update': form.status_update.data,
                'challenges': form.challenges.data,
                'achievements': form.achievements.data,
                'next_steps': form.next_steps.data
            }
            
            # Guardar actualización usando el servicio
            project_service = ProjectService()
            result = project_service.update_project_progress(
                updates_data, entrepreneur.id
            )
            
            if result['success']:
                # Registrar actividad
                _log_progress_update(entrepreneur, updates_data)
                
                # Enviar notificaciones a mentores si es necesario
                _notify_mentors_of_progress(entrepreneur, updates_data)
                
                flash('Progreso actualizado exitosamente', 'success')
                return redirect(url_for('entrepreneur_progress.dashboard'))
            else:
                flash(f'Error al actualizar progreso: {result["message"]}', 'error')
                
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            current_app.logger.error(f"Error actualizando progreso: {str(e)}")
            flash('Error interno al actualizar progreso', 'error')
    
    # Cargar datos para el formulario
    projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).all()
    
    return render_template(
        'entrepreneur/progress/update.html',
        form=form,
        projects=projects
    )


@progress_bp.route('/goal/create', methods=['GET', 'POST'])
def create_goal():
    """
    Creación de nuevos objetivos y metas.
    
    Permite al emprendedor establecer nuevos objetivos
    con fechas límite, métricas y categorías.
    """
    form = GoalSettingForm()
    
    if form.validate_on_submit():
        try:
            # Crear nuevo objetivo
            goal_data = {
                'title': form.title.data,
                'description': form.description.data,
                'category': form.category.data,
                'timeframe': form.timeframe.data,
                'target_date': form.target_date.data,
                'metrics': form.metrics.data,
                'priority': form.priority.data,
                'entrepreneur_id': current_user.entrepreneur_profile.id
            }
            
            # Guardar objetivo (esto requeriría un modelo Goal)
            # goal = Goal(**goal_data)
            # db.session.add(goal)
            # db.session.commit()
            
            # Registrar actividad
            _log_goal_creation(current_user.entrepreneur_profile, goal_data)
            
            flash('Objetivo creado exitosamente', 'success')
            return redirect(url_for('entrepreneur_progress.goals_overview'))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            current_app.logger.error(f"Error creando objetivo: {str(e)}")
            flash('Error al crear objetivo', 'error')
    
    return render_template(
        'entrepreneur/progress/create_goal.html',
        form=form
    )


@progress_bp.route('/milestone/create', methods=['GET', 'POST'])
def create_milestone():
    """
    Creación de hitos para proyectos.
    
    Permite establecer hitos específicos dentro de proyectos
    con fechas y métricas de éxito.
    """
    form = MilestoneForm()
    entrepreneur = current_user.entrepreneur_profile
    
    if form.validate_on_submit():
        try:
            milestone_data = {
                'project_id': form.project_id.data,
                'title': form.title.data,
                'description': form.description.data,
                'target_date': form.target_date.data,
                'success_criteria': form.success_criteria.data,
                'priority': form.priority.data
            }
            
            # Validar que el proyecto pertenece al emprendedor
            project = Project.query.filter_by(
                id=milestone_data['project_id'],
                entrepreneur_id=entrepreneur.id
            ).first()
            
            if not project:
                flash('Proyecto no válido', 'error')
                return redirect(url_for('entrepreneur_progress.create_milestone'))
            
            # Crear hito (requeriría modelo Milestone)
            # milestone = Milestone(**milestone_data)
            # db.session.add(milestone)
            # db.session.commit()
            
            flash('Hito creado exitosamente', 'success')
            return redirect(url_for('entrepreneur_progress.projects_progress'))
            
        except Exception as e:
            current_app.logger.error(f"Error creando hito: {str(e)}")
            flash('Error al crear hito', 'error')
    
    # Cargar proyectos activos para el formulario
    projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).all()
    
    return render_template(
        'entrepreneur/progress/create_milestone.html',
        form=form,
        projects=projects
    )


# ==================== API ENDPOINTS ====================

@progress_bp.route('/api/metrics/<period>')
@require_json
def api_get_metrics(period):
    """
    API endpoint para obtener métricas de progreso.
    
    Args:
        period: Período de tiempo (7, 30, 90, 365 días)
        
    Returns:
        JSON con métricas de progreso
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Validar período
        if period not in ['7', '30', '90', '365']:
            return jsonify({'error': 'Período no válido'}), 400
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        metrics = _calculate_performance_metrics(entrepreneur, start_date, end_date)
        
        return jsonify({
            'success': True,
            'data': metrics,
            'period': period
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API metrics: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@progress_bp.route('/api/projects/<int:project_id>/progress')
@require_json
def api_get_project_progress(project_id):
    """
    API endpoint para obtener progreso específico de un proyecto.
    
    Args:
        project_id: ID del proyecto
        
    Returns:
        JSON con datos de progreso del proyecto
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        project = Project.query.filter_by(
            id=project_id,
            entrepreneur_id=entrepreneur.id
        ).first()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        progress_data = _calculate_project_progress(project)
        
        return jsonify({
            'success': True,
            'data': progress_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API project progress: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@progress_bp.route('/api/update-task-status', methods=['POST'])
@require_json
def api_update_task_status():
    """
    API endpoint para actualizar estado de tareas vía AJAX.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        new_status = data.get('status')
        
        if not task_id or not new_status:
            return jsonify({'error': 'Datos incompletos'}), 400
        
        entrepreneur = current_user.entrepreneur_profile
        
        # Validar que la tarea pertenece al emprendedor
        task = Task.query.join(Project).filter(
            Task.id == task_id,
            Project.entrepreneur_id == entrepreneur.id
        ).first()
        
        if not task:
            return jsonify({'error': 'Tarea no encontrada'}), 404
        
        # Actualizar estado
        task.status = new_status
        task.updated_at = datetime.now(timezone.utc)
        
        if new_status == 'completed':
            task.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Recalcular progreso del proyecto
        project_progress = _calculate_project_progress(task.project)
        
        return jsonify({
            'success': True,
            'message': 'Estado actualizado exitosamente',
            'project_progress': project_progress['completion_percentage']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error actualizando estado de tarea: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== EXPORTACIÓN ====================

@progress_bp.route('/export/pdf')
def export_progress_pdf():
    """
    Exportar reporte de progreso en formato PDF.
    
    Genera un reporte completo del progreso del emprendedor
    en formato PDF para descargar.
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Datos para el reporte
        report_data = _generate_progress_report_data(entrepreneur)
        
        # Generar PDF
        pdf_content = export_to_pdf(
            template='reports/progress_report.html',
            data=report_data,
            filename=f'progreso_{entrepreneur.user.first_name}_{entrepreneur.user.last_name}'
        )
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=progreso_emprendedor.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando PDF: {str(e)}")
        flash('Error al generar reporte PDF', 'error')
        return redirect(url_for('entrepreneur_progress.dashboard'))


@progress_bp.route('/export/excel')
def export_progress_excel():
    """
    Exportar datos de progreso en formato Excel.
    
    Genera un archivo Excel con múltiples hojas conteniendo
    datos detallados de progreso, proyectos, tareas y métricas.
    """
    try:
        entrepreneur = current_user.entrepreneur_profile
        
        # Datos para exportación
        excel_data = _generate_excel_export_data(entrepreneur)
        
        # Generar Excel
        excel_content = export_to_excel(
            data=excel_data,
            filename=f'progreso_emprendedor_{datetime.now().strftime("%Y%m%d")}'
        )
        
        response = make_response(excel_content)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = 'attachment; filename=progreso_emprendedor.xlsx'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando Excel: {str(e)}")
        flash('Error al generar archivo Excel', 'error')
        return redirect(url_for('entrepreneur_progress.dashboard'))


# ==================== FUNCIONES AUXILIARES ====================

def _get_dashboard_data(entrepreneur: Entrepreneur, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """
    Obtiene todos los datos necesarios para el dashboard de progreso.
    
    Args:
        entrepreneur: Instancia del emprendedor
        start_date: Fecha inicio del período
        end_date: Fecha fin del período
        
    Returns:
        Diccionario con datos del dashboard
    """
    # Proyectos activos
    active_projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).count()
    
    # Tareas completadas en el período
    completed_tasks = Task.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.status == 'completed',
        Task.completed_at.between(start_date, end_date)
    ).count()
    
    # Reuniones en el período
    meetings_count = Meeting.query.filter(
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.scheduled_at.between(start_date, end_date)
    ).count()
    
    # Sesiones de mentoría
    mentorship_sessions = MentorshipSession.query.filter(
        MentorshipSession.entrepreneur_id == entrepreneur.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).count()
    
    # Documentos subidos
    documents_uploaded = Document.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Document.created_at.between(start_date, end_date)
    ).count()
    
    return {
        'active_projects': active_projects,
        'completed_tasks': completed_tasks,
        'meetings_count': meetings_count,
        'mentorship_sessions': mentorship_sessions,
        'documents_uploaded': documents_uploaded,
        'period_days': (end_date - start_date).days
    }


def _calculate_performance_metrics(entrepreneur: Entrepreneur, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """
    Calcula métricas de rendimiento del emprendedor.
    
    Args:
        entrepreneur: Instancia del emprendedor
        start_date: Fecha inicio del período
        end_date: Fecha fin del período
        
    Returns:
        Diccionario con métricas de rendimiento
    """
    # Tasa de completitud de tareas
    total_tasks = Task.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.created_at.between(start_date, end_date)
    ).count()
    
    completed_tasks = Task.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.status == 'completed',
        Task.created_at.between(start_date, end_date)
    ).count()
    
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tiempo promedio de completitud de tareas
    avg_completion_time = db.session.query(
        func.avg(
            func.extract('epoch', Task.completed_at) - func.extract('epoch', Task.created_at)
        )
    ).join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.status == 'completed',
        Task.completed_at.between(start_date, end_date)
    ).scalar() or 0
    
    # Convertir a días
    avg_completion_days = avg_completion_time / 86400 if avg_completion_time > 0 else 0
    
    # Progreso promedio de proyectos
    projects = Project.query.filter_by(entrepreneur_id=entrepreneur.id).all()
    total_progress = sum(_calculate_project_progress(p)['completion_percentage'] for p in projects)
    avg_project_progress = (total_progress / len(projects)) if projects else 0
    
    # Engagement con mentores
    mentorship_hours = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.entrepreneur_id == entrepreneur.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).scalar() or 0
    
    return {
        'task_completion_rate': round(task_completion_rate, 2),
        'avg_completion_days': round(avg_completion_days, 1),
        'avg_project_progress': round(avg_project_progress, 2),
        'mentorship_hours': float(mentorship_hours),
        'productivity_score': _calculate_productivity_score(
            task_completion_rate, avg_completion_days, mentorship_hours
        )
    }


def _calculate_project_progress(project: Project) -> dict[str, Any]:
    """
    Calcula el progreso detallado de un proyecto específico.
    
    Args:
        project: Instancia del proyecto
        
    Returns:
        Diccionario con datos de progreso del proyecto
    """
    # Progreso basado en tareas
    total_tasks = Task.query.filter_by(project_id=project.id).count()
    completed_tasks = Task.query.filter_by(
        project_id=project.id, 
        status='completed'
    ).count()
    
    task_completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Progreso basado en hitos (si existe modelo Milestone)
    # milestone_progress = _calculate_milestone_progress(project)
    
    # Progreso temporal
    if project.start_date and project.target_end_date:
        total_duration = (project.target_end_date - project.start_date).days
        elapsed_duration = (datetime.now(timezone.utc).date() - project.start_date).days
        time_progress = min((elapsed_duration / total_duration * 100), 100) if total_duration > 0 else 0
    else:
        time_progress = 0
    
    # Progreso ponderado
    completion_percentage = (task_completion_percentage * 0.7) + (time_progress * 0.3)
    
    # Estado del proyecto basado en progreso
    if completion_percentage >= 100:
        status_label = 'Completado'
        status_class = 'success'
    elif completion_percentage >= 75:
        status_label = 'Casi terminado'
        status_class = 'info'
    elif completion_percentage >= 50:
        status_label = 'En progreso'
        status_class = 'warning'
    elif completion_percentage >= 25:
        status_label = 'Iniciado'
        status_class = 'primary'
    else:
        status_label = 'Planificación'
        status_class = 'secondary'
    
    return {
        'completion_percentage': round(completion_percentage, 2),
        'task_completion_percentage': round(task_completion_percentage, 2),
        'time_progress': round(time_progress, 2),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': total_tasks - completed_tasks,
        'status_label': status_label,
        'status_class': status_class,
        'is_on_track': completion_percentage >= time_progress,
        'days_remaining': (project.target_end_date - datetime.now(timezone.utc).date()).days if project.target_end_date else None
    }


def _get_upcoming_milestones(entrepreneur: Entrepreneur, limit: int = 5) -> list[dict[str, Any]]:
    """
    Obtiene los próximos hitos del emprendedor.
    
    Args:
        entrepreneur: Instancia del emprendedor
        limit: Número máximo de hitos a retornar
        
    Returns:
        Lista de hitos próximos
    """
    # Esto requeriría un modelo Milestone
    # Por ahora retornamos tareas próximas como hitos
    upcoming_tasks = Task.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.status != 'completed',
        Task.due_date.isnot(None),
        Task.due_date >= datetime.now(timezone.utc).date()
    ).order_by(Task.due_date.asc()).limit(limit).all()
    
    milestones = []
    for task in upcoming_tasks:
        days_until_due = (task.due_date - datetime.now(timezone.utc).date()).days
        
        milestones.append({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'due_date': task.due_date,
            'days_until_due': days_until_due,
            'project_name': task.project.name,
            'priority': task.priority,
            'is_urgent': days_until_due <= 7
        })
    
    return milestones


def _get_recent_activities(entrepreneur: Entrepreneur, limit: int = 10) -> list[dict[str, Any]]:
    """
    Obtiene las actividades recientes del emprendedor.
    
    Args:
        entrepreneur: Instancia del emprendedor
        limit: Número máximo de actividades a retornar
        
    Returns:
        Lista de actividades recientes
    """
    activities = ActivityLog.query.filter_by(
        user_id=entrepreneur.user_id
    ).order_by(desc(ActivityLog.created_at)).limit(limit).all()
    
    return [
        {
            'id': activity.id,
            'action': activity.action,
            'description': activity.description,
            'created_at': activity.created_at,
            'entity_type': activity.entity_type,
            'entity_id': activity.entity_id
        }
        for activity in activities
    ]


def _generate_progress_recommendations(entrepreneur: Entrepreneur) -> list[dict[str, str]]:
    """
    Genera recomendaciones basadas en el progreso del emprendedor.
    
    Args:
        entrepreneur: Instancia del emprendedor
        
    Returns:
        Lista de recomendaciones
    """
    recommendations = []
    
    # Analizar proyectos atrasados
    delayed_projects = Project.query.filter(
        Project.entrepreneur_id == entrepreneur.id,
        Project.target_end_date < datetime.now(timezone.utc).date(),
        Project.status == 'active'
    ).count()
    
    if delayed_projects > 0:
        recommendations.append({
            'type': 'warning',
            'title': 'Proyectos atrasados',
            'message': f'Tienes {delayed_projects} proyecto(s) con fechas vencidas. Considera revisar los plazos o solicitar una extensión.',
            'action': 'Revisar proyectos'
        })
    
    # Analizar tareas pendientes
    overdue_tasks = Task.query.join(Project).filter(
        Project.entrepreneur_id == entrepreneur.id,
        Task.due_date < datetime.now(timezone.utc).date(),
        Task.status != 'completed'
    ).count()
    
    if overdue_tasks > 0:
        recommendations.append({
            'type': 'danger',
            'title': 'Tareas vencidas',
            'message': f'Tienes {overdue_tasks} tarea(s) vencida(s). Prioriza completarlas lo antes posible.',
            'action': 'Ver tareas pendientes'
        })
    
    # Analizar frecuencia de mentoría
    last_mentorship = MentorshipSession.query.filter_by(
        entrepreneur_id=entrepreneur.id
    ).order_by(desc(MentorshipSession.session_date)).first()
    
    if last_mentorship:
        days_since_mentorship = (datetime.now(timezone.utc).date() - last_mentorship.session_date).days
        if days_since_mentorship > 30:
            recommendations.append({
                'type': 'info',
                'title': 'Sesión de mentoría',
                'message': f'Han pasado {days_since_mentorship} días desde tu última sesión de mentoría. Considera programar una nueva.',
                'action': 'Programar mentoría'
            })
    
    # Si no hay recomendaciones, agregar mensaje positivo
    if not recommendations:
        recommendations.append({
            'type': 'success',
            'title': '¡Excelente trabajo!',
            'message': 'Estás al día con todos tus proyectos y tareas. Mantén el buen ritmo.',
            'action': 'Continuar así'
        })
    
    return recommendations


def _calculate_productivity_score(task_completion_rate: float, avg_completion_days: float, mentorship_hours: float) -> float:
    """
    Calcula un puntaje de productividad basado en múltiples métricas.
    
    Args:
        task_completion_rate: Tasa de completitud de tareas
        avg_completion_days: Días promedio de completitud
        mentorship_hours: Horas de mentoría
        
    Returns:
        Puntaje de productividad (0-100)
    """
    # Normalizar métricas a escala 0-100
    task_score = min(task_completion_rate, 100)
    
    # Tiempo ideal: 5 días o menos
    time_score = max(0, 100 - (avg_completion_days * 10)) if avg_completion_days > 0 else 50
    
    # Horas ideales: 4+ horas por mes
    mentorship_score = min(mentorship_hours * 25, 100)
    
    # Promedio ponderado
    productivity_score = (task_score * 0.5) + (time_score * 0.3) + (mentorship_score * 0.2)
    
    return round(productivity_score, 2)


def _log_progress_update(entrepreneur: Entrepreneur, update_data: dict[str, Any]) -> None:
    """
    Registra una actualización de progreso en el log de actividades.
    
    Args:
        entrepreneur: Instancia del emprendedor
        update_data: Datos de la actualización
    """
    try:
        activity = ActivityLog(
            user_id=entrepreneur.user_id,
            action='progress_update',
            description=f'Actualización de progreso en proyecto ID: {update_data["project_id"]}',
            entity_type='project',
            entity_id=update_data['project_id'],
            metadata={
                'progress_percentage': update_data['progress_percentage'],
                'status_update': update_data['status_update']
            }
        )
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando actividad: {str(e)}")
        db.session.rollback()


def _notify_mentors_of_progress(entrepreneur: Entrepreneur, update_data: dict[str, Any]) -> None:
    """
    Notifica a los mentores sobre actualizaciones importantes de progreso.
    
    Args:
        entrepreneur: Instancia del emprendedor
        update_data: Datos de la actualización
    """
    try:
        # Obtener mentores activos
        mentors = db.session.query(User).join(MentorshipSession).filter(
            MentorshipSession.entrepreneur_id == entrepreneur.id,
            MentorshipSession.status == 'active'
        ).distinct().all()
        
        # Enviar notificaciones usando el servicio
        notification_service = NotificationService()
        
        for mentor in mentors:
            notification_service.send_notification(
                user_id=mentor.id,
                title='Actualización de progreso',
                message=f'{entrepreneur.user.first_name} ha actualizado el progreso de su proyecto',
                notification_type='progress_update',
                metadata=update_data
            )
            
    except Exception as e:
        current_app.logger.error(f"Error enviando notificaciones: {str(e)}")


# Funciones adicionales que se referencian pero no están implementadas
def _get_goals_by_timeframe(entrepreneur: Entrepreneur, timeframe: str) -> list[dict[str, Any]]:
    """Obtiene objetivos por marco temporal."""
    # Implementación pendiente - requiere modelo Goal
    return []


def _calculate_overall_goals_progress(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Calcula progreso general de objetivos."""
    # Implementación pendiente - requiere modelo Goal
    return {'overall_progress': 0, 'completed_goals': 0, 'total_goals': 0}


def _get_urgent_goals(entrepreneur: Entrepreneur) -> list[dict[str, Any]]:
    """Obtiene objetivos urgentes."""
    # Implementación pendiente - requiere modelo Goal
    return []


def _get_completed_goals(entrepreneur: Entrepreneur, limit: int = 5) -> list[dict[str, Any]]:
    """Obtiene objetivos completados."""
    # Implementación pendiente - requiere modelo Goal
    return []


def _get_mentorship_engagement_metrics(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Obtiene métricas de engagement con mentores."""
    # Implementación pendiente
    return {}


def _log_goal_creation(entrepreneur: Entrepreneur, goal_data: dict[str, Any]) -> None:
    """Registra creación de objetivo."""
    # Implementación pendiente
    pass


def _generate_progress_report_data(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Genera datos para reporte de progreso."""
    # Implementación pendiente
    return {}


def _generate_excel_export_data(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Genera datos para exportación Excel."""
    # Implementación pendiente
    return {}