"""
Gestión de Tareas del Emprendedor - Vista completa para productividad y seguimiento.

Este módulo contiene todas las vistas relacionadas con la gestión de tareas
del emprendedor, incluyendo creación, seguimiento, priorización, organización,
colaboración, analytics de productividad y gamificación.
"""

import json
from datetime import datetime, timedelta, date, time, timezone
from collections import defaultdict
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, g, send_file
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, case, extract
from sqlalchemy.orm import joinedload, selectinload
from dateutil.relativedelta import relativedelta

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, ResourceNotFoundError
from app.models.entrepreneur import Entrepreneur
from app.models.task import (
    Task, TaskStatus, TaskPriority, TaskCategory, TaskDependency,
    TaskComment, TaskAttachment, TaskTimeEntry, TaskRecurrence
)
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.models.ally import Ally
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.models.meeting import Meeting
from app.forms.task import (
    TaskForm, TaskEditForm, TaskSearchForm, TaskCommentForm,
    TaskTimeEntryForm, BulkActionForm, TaskTemplateForm,
    TaskDependencyForm, TaskRecurrenceForm, TaskFilterForm
)
from app.services.entrepreneur_service import EntrepreneurService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.google_calendar import GoogleCalendarService
from app.utils.decorators import cache_response, rate_limit, validate_json
from app.utils.validators import validate_future_date, validate_time_estimate
from app.utils.formatters import (
    format_duration, format_percentage, format_relative_time,
    format_currency, format_date_short
)
from app.utils.date_utils import (
    get_business_days_between, calculate_deadline_urgency,
    get_next_business_day, format_time_spent
)
from app.utils.string_utils import sanitize_input, generate_slug, extract_keywords
from app.utils.export_utils import export_to_excel, export_to_csv
from app.utils.pagination import get_pagination_params

# Crear blueprint para tareas del emprendedor
entrepreneur_tasks = Blueprint(
    'entrepreneur_tasks', 
    __name__, 
    url_prefix='/entrepreneur/tasks'
)

# Configuraciones
TASKS_PER_PAGE = 25
MAX_TASK_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
DEFAULT_POMODORO_DURATION = 25  # minutos
MAX_TIME_ENTRY_HOURS = 12  # horas por entrada

# Configuración de gamificación
POINTS_CONFIG = {
    'task_completed': 10,
    'high_priority_completed': 25,
    'urgent_completed': 50,
    'overdue_completed': 15,
    'streak_bonus': 5,  # por día consecutivo
    'early_completion': 20  # completar antes de fecha límite
}

# Colores por prioridad
PRIORITY_COLORS = {
    TaskPriority.LOW: '#28a745',      # Verde
    TaskPriority.MEDIUM: '#ffc107',   # Amarillo
    TaskPriority.HIGH: '#fd7e14',     # Naranja
    TaskPriority.URGENT: '#dc3545'    # Rojo
}

# Iconos por categoría
CATEGORY_ICONS = {
    TaskCategory.ADMINISTRATIVE: 'fa-clipboard-list',
    TaskCategory.MARKETING: 'fa-bullhorn',
    TaskCategory.SALES: 'fa-handshake',
    TaskCategory.FINANCIAL: 'fa-dollar-sign',
    TaskCategory.OPERATIONS: 'fa-cogs',
    TaskCategory.STRATEGY: 'fa-chess',
    TaskCategory.LEARNING: 'fa-graduation-cap',
    TaskCategory.NETWORKING: 'fa-users',
    TaskCategory.PERSONAL: 'fa-user'
}


@entrepreneur_tasks.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
        g.calendar_service = GoogleCalendarService(current_user)
    else:
        g.entrepreneur = None
        g.entrepreneur_service = None
        g.calendar_service = None


@entrepreneur_tasks.route('/')
@entrepreneur_tasks.route('/dashboard')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=180)  # Cache por 3 minutos
def dashboard():
    """
    Dashboard principal de tareas del emprendedor.
    
    Incluye:
    - Resumen de tareas por estado y prioridad
    - Tareas de hoy y próximas
    - Métricas de productividad
    - Progreso de objetivos
    - Timeline de actividades
    - Gamificación y logros
    """
    try:
        # Fechas de referencia
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_start = today.replace(day=1)
        
        # === TAREAS DE HOY ===
        todays_tasks = _get_todays_tasks(g.entrepreneur.id)
        
        # === TAREAS PRÓXIMAS (7 días) ===
        upcoming_tasks = _get_upcoming_tasks(g.entrepreneur.id, days=7)
        
        # === TAREAS VENCIDAS ===
        overdue_tasks = _get_overdue_tasks(g.entrepreneur.id)
        
        # === MÉTRICAS PRINCIPALES ===
        task_metrics = _get_task_metrics(g.entrepreneur.id)
        
        # === PRODUCTIVIDAD SEMANAL ===
        weekly_productivity = _get_weekly_productivity(g.entrepreneur.id, week_start, week_end)
        
        # === PROGRESO POR PROYECTOS ===
        project_progress = _get_project_task_progress(g.entrepreneur.id)
        
        # === DISTRIBUCIÓN POR CATEGORÍAS ===
        category_distribution = _get_category_distribution(g.entrepreneur.id)
        
        # === GAMIFICACIÓN ===
        gamification_data = _get_gamification_data(g.entrepreneur.id)
        
        # === ACTIVIDAD RECIENTE ===
        recent_activity = _get_recent_task_activity(g.entrepreneur.id, limit=10)
        
        # === ANÁLISIS DE TIEMPO ===
        time_analysis = _get_time_analysis(g.entrepreneur.id, week_start, week_end)
        
        # === RECOMENDACIONES ===
        productivity_suggestions = _get_productivity_suggestions(
            task_metrics, weekly_productivity, overdue_tasks
        )
        
        dashboard_data = {
            'todays_tasks': todays_tasks,
            'upcoming_tasks': upcoming_tasks,
            'overdue_tasks': overdue_tasks,
            'task_metrics': task_metrics,
            'weekly_productivity': weekly_productivity,
            'project_progress': project_progress,
            'category_distribution': category_distribution,
            'gamification_data': gamification_data,
            'recent_activity': recent_activity,
            'time_analysis': time_analysis,
            'productivity_suggestions': productivity_suggestions,
            'today': today,
            'week_range': (week_start, week_end),
            'priority_colors': PRIORITY_COLORS,
            'category_icons': CATEGORY_ICONS
        }

        return render_template(
            'entrepreneur/tasks/dashboard.html',
            **dashboard_data
        )

    except Exception as e:
        current_app.logger.error(f"Error en dashboard de tareas: {str(e)}")
        flash('Error cargando el dashboard de tareas', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_tasks.route('/list')
@login_required
@require_role('entrepreneur')
def list_tasks():
    """
    Vista de lista completa de tareas con filtros avanzados.
    """
    try:
        # Parámetros de filtrado y paginación
        page, per_page = get_pagination_params(request, default_per_page=TASKS_PER_PAGE)
        search_form = TaskSearchForm(request.args)
        
        # Vista seleccionada
        view_type = request.args.get('view', 'list')  # list, kanban, calendar
        
        # Construir query base
        query = Task.query.filter_by(entrepreneur_id=g.entrepreneur.id)
        
        # Aplicar filtros
        query = _apply_task_filters(query, search_form)
        
        # Ordenamiento
        sort_by = request.args.get('sort_by', 'priority_due_date')
        sort_order = request.args.get('sort_order', 'desc')
        query = _apply_task_sorting(query, sort_by, sort_order)
        
        # Optimizar consultas
        query = query.options(
            joinedload(Task.project),
            joinedload(Task.assigned_to),
            selectinload(Task.comments),
            selectinload(Task.time_entries),
            selectinload(Task.dependencies)
        )
        
        # Paginación
        tasks_pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Datos adicionales según la vista
        additional_data = {}
        
        if view_type == 'kanban':
            # Organizar tareas por estado para vista Kanban
            additional_data['kanban_columns'] = _organize_tasks_for_kanban(tasks_pagination.items)
        elif view_type == 'calendar':
            # Datos del calendario
            additional_data['calendar_events'] = _format_tasks_for_calendar(tasks_pagination.items)
        
        # Métricas de la lista actual
        list_metrics = _calculate_list_metrics(tasks_pagination.items)
        
        # Filtros disponibles
        filter_options = _get_filter_options(g.entrepreneur.id)
        
        # Plantillas guardadas
        saved_templates = _get_task_templates(g.entrepreneur.id)
        
        return render_template(
            'entrepreneur/tasks/list.html',
            tasks=tasks_pagination.items,
            pagination=tasks_pagination,
            search_form=search_form,
            list_metrics=list_metrics,
            filter_options=filter_options,
            saved_templates=saved_templates,
            view_type=view_type,
            current_sort=f"{sort_by}_{sort_order}",
            TaskStatus=TaskStatus,
            TaskPriority=TaskPriority,
            TaskCategory=TaskCategory,
            priority_colors=PRIORITY_COLORS,
            category_icons=CATEGORY_ICONS,
            **additional_data
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando lista de tareas: {str(e)}")
        flash('Error cargando las tareas', 'error')
        return redirect(url_for('entrepreneur_tasks.dashboard'))


@entrepreneur_tasks.route('/create', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def create():
    """
    Crear nueva tarea.
    """
    form = TaskForm()
    
    if request.method == 'GET':
        # Pre-llenar con datos sugeridos
        project_id = request.args.get('project_id', type=int)
        template_id = request.args.get('template_id', type=int)
        
        if template_id:
            template = _get_task_template(template_id, g.entrepreneur.id)
            if template:
                _populate_form_from_template(form, template)
        
        if project_id:
            form.project_id.data = project_id
        
        # Cargar opciones del formulario
        _populate_task_form_choices(form)
        
        return render_template(
            'entrepreneur/tasks/create.html',
            form=form,
            priority_colors=PRIORITY_COLORS,
            category_icons=CATEGORY_ICONS
        )
    
    try:
        if not form.validate_on_submit():
            _populate_task_form_choices(form)
            return render_template(
                'entrepreneur/tasks/create.html',
                form=form,
                priority_colors=PRIORITY_COLORS
            )
        
        # Validaciones adicionales
        validation_result = _validate_task_data(form)
        if not validation_result['valid']:
            for error in validation_result['errors']:
                flash(error, 'error')
            _populate_task_form_choices(form)
            return render_template('entrepreneur/tasks/create.html', form=form)
        
        # Crear tarea
        task_data = {
            'title': sanitize_input(form.title.data),
            'description': sanitize_input(form.description.data) if form.description.data else None,
            'priority': form.priority.data,
            'category': form.category.data if form.category.data else None,
            'status': TaskStatus.PENDING,
            'due_date': form.due_date.data,
            'estimated_hours': form.estimated_hours.data,
            'project_id': form.project_id.data if form.project_id.data else None,
            'assigned_to_id': form.assigned_to_id.data if form.assigned_to_id.data else None,
            'entrepreneur_id': g.entrepreneur.id,
            'created_by': current_user.id
        }
        
        task = Task.create(**task_data)
        
        # Crear dependencias si se especificaron
        if hasattr(form, 'dependencies') and form.dependencies.data:
            _create_task_dependencies(task, form.dependencies.data)
        
        # Crear recurrencia si se especificó
        if hasattr(form, 'is_recurring') and form.is_recurring.data:
            _create_task_recurrence(task, form)
        
        # Crear evento en calendario si tiene fecha límite
        if task.due_date and g.entrepreneur.google_calendar_enabled:
            try:
                _create_calendar_event_for_task(task)
            except Exception as e:
                current_app.logger.warning(f"Error creando evento de calendario: {str(e)}")
        
        # Enviar notificaciones
        _send_task_notifications(task, 'created')
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='task_created',
            resource_type='task',
            resource_id=task.id,
            details={
                'task_title': task.title,
                'priority': task.priority.value,
                'project': task.project.name if task.project else None
            }
        )
        
        # Calcular puntos de gamificación
        if task.priority == TaskPriority.HIGH:
            _award_points(g.entrepreneur.id, 5, 'high_priority_task_created')
        
        flash('Tarea creada exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Tarea creada exitosamente',
                'task_id': task.id,
                'redirect_url': url_for('entrepreneur_tasks.view', task_id=task.id)
            })
        else:
            return redirect(url_for('entrepreneur_tasks.view', task_id=task.id))

    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            _populate_task_form_choices(form)
            return render_template('entrepreneur/tasks/create.html', form=form)
    
    except Exception as e:
        current_app.logger.error(f"Error creando tarea: {str(e)}")
        error_msg = 'Error creando la tarea'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            _populate_task_form_choices(form)
            return render_template('entrepreneur/tasks/create.html', form=form)


@entrepreneur_tasks.route('/<int:task_id>')
@entrepreneur_tasks.route('/<int:task_id>/view')
@login_required
@require_role('entrepreneur')
def view(task_id):
    """
    Ver detalles completos de una tarea.
    """
    try:
        # Obtener tarea con validación
        task = _get_task_or_404(task_id)
        
        # Obtener comentarios
        comments = TaskComment.query.filter_by(
            task_id=task.id
        ).options(
            joinedload(TaskComment.author)
        ).order_by(TaskComment.created_at).all()
        
        # Obtener entradas de tiempo
        time_entries = TaskTimeEntry.query.filter_by(
            task_id=task.id
        ).order_by(desc(TaskTimeEntry.created_at)).all()
        
        # Obtener adjuntos
        attachments = TaskAttachment.query.filter_by(
            task_id=task.id
        ).order_by(desc(TaskAttachment.created_at)).all()
        
        # Obtener dependencias
        dependencies = _get_task_dependencies(task.id)
        dependent_tasks = _get_dependent_tasks(task.id)
        
        # Historial de actividad
        activity_history = ActivityLog.query.filter_by(
            resource_type='task',
            resource_id=task.id
        ).order_by(desc(ActivityLog.created_at)).limit(20).all()
        
        # Tareas relacionadas
        related_tasks = _get_related_tasks(task, limit=5)
        
        # Verificar permisos
        can_edit = _can_edit_task(task, current_user.id)
        can_delete = _can_delete_task(task, current_user.id)
        can_assign = _can_assign_task(task, current_user.id)
        
        # Métricas de la tarea
        task_metrics = _calculate_task_metrics(task, time_entries)
        
        # Progreso estimado vs real
        progress_analysis = _analyze_task_progress(task, time_entries)
        
        # Siguiente acción sugerida
        next_action = _suggest_next_action(task)
        
        return render_template(
            'entrepreneur/tasks/view.html',
            task=task,
            comments=comments,
            time_entries=time_entries,
            attachments=attachments,
            dependencies=dependencies,
            dependent_tasks=dependent_tasks,
            activity_history=activity_history,
            related_tasks=related_tasks,
            can_edit=can_edit,
            can_delete=can_delete,
            can_assign=can_assign,
            task_metrics=task_metrics,
            progress_analysis=progress_analysis,
            next_action=next_action,
            TaskStatus=TaskStatus,
            TaskPriority=TaskPriority,
            priority_colors=PRIORITY_COLORS,
            category_icons=CATEGORY_ICONS
        )

    except ResourceNotFoundError:
        flash('Tarea no encontrada', 'error')
        return redirect(url_for('entrepreneur_tasks.list_tasks'))
    except Exception as e:
        current_app.logger.error(f"Error mostrando tarea {task_id}: {str(e)}")
        flash('Error cargando la tarea', 'error')
        return redirect(url_for('entrepreneur_tasks.list_tasks'))


@entrepreneur_tasks.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def edit(task_id):
    """
    Editar tarea existente.
    """
    try:
        task = _get_task_or_404(task_id)
        
        # Verificar permisos
        if not _can_edit_task(task, current_user.id):
            flash('No tienes permisos para editar esta tarea', 'error')
            return redirect(url_for('entrepreneur_tasks.view', task_id=task_id))
        
        form = TaskEditForm(obj=task)
        
        if request.method == 'GET':
            _populate_task_form_choices(form)
            _populate_edit_form_with_task_data(form, task)
            
            return render_template(
                'entrepreneur/tasks/edit.html',
                form=form,
                task=task,
                priority_colors=PRIORITY_COLORS
            )
        
        if not form.validate_on_submit():
            _populate_task_form_choices(form)
            return render_template(
                'entrepreneur/tasks/edit.html',
                form=form,
                task=task
            )
        
        # Guardar datos originales para auditoria
        original_data = _extract_task_data(task)
        
        # Validar cambios
        validation_result = _validate_task_changes(task, form)
        if not validation_result['valid']:
            for error in validation_result['errors']:
                flash(error, 'error')
            _populate_task_form_choices(form)
            return render_template('entrepreneur/tasks/edit.html', form=form, task=task)
        
        # Actualizar tarea
        task.title = sanitize_input(form.title.data)
        task.description = sanitize_input(form.description.data) if form.description.data else None
        task.priority = form.priority.data
        task.category = form.category.data if form.category.data else None
        task.due_date = form.due_date.data
        task.estimated_hours = form.estimated_hours.data
        task.project_id = form.project_id.data if form.project_id.data else None
        task.assigned_to_id = form.assigned_to_id.data if form.assigned_to_id.data else None
        task.updated_at = datetime.now(timezone.utc)
        task.save()
        
        # Detectar cambios significativos
        changes = _detect_task_changes(original_data, task)
        
        if changes:
            # Actualizar evento de calendario si es necesario
            if 'due_date' in changes and g.entrepreneur.google_calendar_enabled:
                try:
                    _update_calendar_event_for_task(task)
                except Exception as e:
                    current_app.logger.warning(f"Error actualizando evento de calendario: {str(e)}")
            
            # Enviar notificaciones de cambios
            if any(key in changes for key in ['priority', 'due_date', 'assigned_to_id']):
                _send_task_notifications(task, 'updated', changes)
            
            # Registrar actividad
            ActivityLog.create(
                user_id=current_user.id,
                action='task_updated',
                resource_type='task',
                resource_id=task.id,
                details={
                    'changes': changes,
                    'task_title': task.title
                }
            )
        
        flash('Tarea actualizada exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Tarea actualizada exitosamente',
                'redirect_url': url_for('entrepreneur_tasks.view', task_id=task_id)
            })
        else:
            return redirect(url_for('entrepreneur_tasks.view', task_id=task_id))

    except ResourceNotFoundError:
        flash('Tarea no encontrada', 'error')
        return redirect(url_for('entrepreneur_tasks.list_tasks'))
    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            return redirect(url_for('entrepreneur_tasks.view', task_id=task_id))
    except Exception as e:
        current_app.logger.error(f"Error editando tarea {task_id}: {str(e)}")
        error_msg = 'Error actualizando la tarea'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            return redirect(url_for('entrepreneur_tasks.view', task_id=task_id))


@entrepreneur_tasks.route('/<int:task_id>/status', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=60, window=60)  # 60 cambios de estado por minuto
def change_status(task_id):
    """
    Cambiar estado de una tarea.
    """
    try:
        task = _get_task_or_404(task_id)
        
        # Verificar permisos
        if not _can_edit_task(task, current_user.id):
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para cambiar el estado'
            }), 403
        
        new_status = request.json.get('status')
        if not new_status or new_status not in [status.value for status in TaskStatus]:
            return jsonify({
                'success': False,
                'error': 'Estado no válido'
            }), 400
        
        old_status = task.status
        new_status_enum = TaskStatus(new_status)
        
        # Validar transición de estado
        if not _is_valid_status_transition(old_status, new_status_enum):
            return jsonify({
                'success': False,
                'error': 'Transición de estado no válida'
            }), 400
        
        # Actualizar estado
        task.status = new_status_enum
        task.updated_at = datetime.now(timezone.utc)
        
        # Lógica específica por estado
        if new_status_enum == TaskStatus.IN_PROGRESS:
            task.started_at = datetime.now(timezone.utc)
        elif new_status_enum == TaskStatus.COMPLETED:
            task.completed_at = datetime.now(timezone.utc)
            task.actual_hours = _calculate_actual_hours(task)
            
            # Calcular puntos de gamificación
            points = _calculate_completion_points(task)
            if points > 0:
                _award_points(g.entrepreneur.id, points, 'task_completed')
        elif new_status_enum == TaskStatus.CANCELLED:
            task.cancelled_at = datetime.now(timezone.utc)
        
        task.save()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='task_status_changed',
            resource_type='task',
            resource_id=task.id,
            details={
                'old_status': old_status.value,
                'new_status': new_status,
                'task_title': task.title
            }
        )
        
        # Enviar notificaciones
        if new_status_enum in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            _send_task_notifications(task, f'status_{new_status}')
        
        # Actualizar tareas dependientes si se completó
        if new_status_enum == TaskStatus.COMPLETED:
            _update_dependent_tasks(task.id)
        
        return jsonify({
            'success': True,
            'message': f'Estado cambiado a {new_status_enum.value}',
            'new_status': new_status,
            'points_awarded': _calculate_completion_points(task) if new_status_enum == TaskStatus.COMPLETED else 0
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error cambiando estado de tarea {task_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error cambiando el estado'
        }), 500


@entrepreneur_tasks.route('/<int:task_id>/time-entry', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=30, window=300)  # 30 entradas de tiempo por 5 minutos
def add_time_entry(task_id):
    """
    Agregar entrada de tiempo a una tarea.
    """
    try:
        task = _get_task_or_404(task_id)
        
        form = TaskTimeEntryForm()
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        # Validar horas
        hours = form.hours.data
        if hours <= 0 or hours > MAX_TIME_ENTRY_HOURS:
            return jsonify({
                'success': False,
                'error': f'Las horas deben estar entre 0.1 y {MAX_TIME_ENTRY_HOURS}'
            }), 400
        
        # Crear entrada de tiempo
        time_entry_data = {
            'task_id': task.id,
            'user_id': current_user.id,
            'hours': hours,
            'description': sanitize_input(form.description.data) if form.description.data else None,
            'date': form.date.data or date.today()
        }
        
        time_entry = TaskTimeEntry.create(**time_entry_data)
        
        # Actualizar tiempo total de la tarea
        total_time = TaskTimeEntry.query.filter_by(
            task_id=task.id
        ).with_entities(func.sum(TaskTimeEntry.hours)).scalar() or 0
        
        task.actual_hours = total_time
        task.save()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='time_entry_added',
            resource_type='task',
            resource_id=task.id,
            details={
                'hours': hours,
                'task_title': task.title,
                'total_time': total_time
            }
        )
        
        # Calcular progreso si hay estimación
        progress_info = {}
        if task.estimated_hours:
            progress_percentage = min((total_time / task.estimated_hours) * 100, 100)
            progress_info = {
                'progress_percentage': round(progress_percentage, 1),
                'estimated_hours': task.estimated_hours,
                'actual_hours': total_time
            }
        
        return jsonify({
            'success': True,
            'message': f'{hours} hora(s) agregada(s) exitosamente',
            'time_entry_id': time_entry.id,
            'total_time': total_time,
            'formatted_time': format_time_spent(total_time),
            'progress_info': progress_info
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error agregando tiempo a tarea {task_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error agregando el tiempo'
        }), 500


@entrepreneur_tasks.route('/<int:task_id>/comment', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=20, window=300)  # 20 comentarios por 5 minutos
def add_comment(task_id):
    """
    Agregar comentario a una tarea.
    """
    try:
        task = _get_task_or_404(task_id)
        
        form = TaskCommentForm()
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        # Crear comentario
        comment_data = {
            'task_id': task.id,
            'author_id': current_user.id,
            'content': sanitize_input(form.content.data)
        }
        
        comment = TaskComment.create(**comment_data)
        
        # Notificar a usuarios involucrados
        _notify_task_participants(task, comment)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='task_comment_added',
            resource_type='task',
            resource_id=task.id,
            details={
                'comment_id': comment.id,
                'task_title': task.title
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Comentario agregado exitosamente',
            'comment_id': comment.id,
            'comment_html': render_template(
                'entrepreneur/tasks/_comment.html',
                comment=comment
            )
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error agregando comentario a tarea {task_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error agregando el comentario'
        }), 500


@entrepreneur_tasks.route('/<int:task_id>/delete', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 eliminaciones por 5 minutos
def delete(task_id):
    """
    Eliminar tarea.
    """
    try:
        task = _get_task_or_404(task_id)
        
        # Verificar permisos
        if not _can_delete_task(task, current_user.id):
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para eliminar esta tarea'
            }), 403
        
        # Verificar confirmación
        confirmation = request.json.get('confirmation')
        if confirmation != task.title:
            return jsonify({
                'success': False,
                'error': 'Confirmación incorrecta'
            }), 400
        
        # Verificar dependencias
        dependent_tasks = _get_dependent_tasks(task.id)
        if dependent_tasks:
            return jsonify({
                'success': False,
                'error': f'No se puede eliminar. {len(dependent_tasks)} tarea(s) dependen de esta.'
            }), 400
        
        # Eliminar tarea (soft delete)
        task_title = task.title
        task.is_deleted = True
        task.deleted_at = datetime.now(timezone.utc)
        task.save()
        
        # Eliminar evento de calendario
        if task.calendar_event_id and g.entrepreneur.google_calendar_enabled:
            try:
                g.calendar_service.delete_event(task.calendar_event_id)
            except Exception as e:
                current_app.logger.warning(f"Error eliminando evento de calendario: {str(e)}")
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='task_deleted',
            resource_type='task',
            resource_id=task.id,
            details={
                'task_title': task_title,
                'project': task.project.name if task.project else None
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Tarea "{task_title}" eliminada exitosamente',
            'redirect_url': url_for('entrepreneur_tasks.list_tasks')
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error eliminando tarea {task_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error eliminando la tarea'
        }), 500


@entrepreneur_tasks.route('/bulk-actions', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 acciones masivas por 5 minutos
def bulk_actions():
    """
    Realizar acciones masivas en tareas.
    """
    try:
        form = BulkActionForm()
        
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        action = form.action.data
        task_ids = form.task_ids.data
        
        if not task_ids:
            return jsonify({
                'success': False,
                'error': 'No se seleccionaron tareas'
            }), 400
        
        # Obtener tareas verificando permisos
        tasks = []
        for task_id in task_ids:
            try:
                task = _get_task_or_404(task_id)
                if _can_edit_task(task, current_user.id):
                    tasks.append(task)
            except ResourceNotFoundError:
                continue
        
        if not tasks:
            return jsonify({
                'success': False,
                'error': 'No se encontraron tareas válidas'
            }), 404
        
        # Ejecutar acción
        if action == 'complete':
            result = _bulk_complete_tasks(tasks)
        elif action == 'delete':
            result = _bulk_delete_tasks(tasks)
        elif action == 'change_priority':
            new_priority = TaskPriority(form.target_value.data)
            result = _bulk_change_priority(tasks, new_priority)
        elif action == 'assign':
            assignee_id = form.target_value.data
            result = _bulk_assign_tasks(tasks, assignee_id)
        elif action == 'move_project':
            project_id = form.target_value.data
            result = _bulk_move_to_project(tasks, project_id)
        else:
            return jsonify({
                'success': False,
                'error': 'Acción no válida'
            }), 400
        
        # Registrar actividad masiva
        ActivityLog.create(
            user_id=current_user.id,
            action=f'bulk_{action}',
            resource_type='task',
            details={
                'action': action,
                'task_count': len(tasks),
                'task_ids': task_ids,
                'result': result
            }
        )
        
        return jsonify({
            'success': True,
            'message': result.get('message', 'Acción ejecutada correctamente'),
            'result': result
        })

    except Exception as e:
        current_app.logger.error(f"Error en acciones masivas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error ejecutando la acción'
        }), 500


@entrepreneur_tasks.route('/analytics')
@login_required
@require_role('entrepreneur')
def analytics():
    """
    Analytics y métricas detalladas de tareas.
    """
    try:
        # Rango de fechas para análisis
        date_range = request.args.get('range', '30')  # días
        end_date = date.today()
        start_date = end_date - timedelta(days=int(date_range))
        
        # Análisis de productividad
        productivity_analytics = _get_productivity_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Análisis de tiempo
        time_analytics = _get_time_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Análisis de prioridades
        priority_analytics = _get_priority_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Análisis de categorías
        category_analytics = _get_category_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Tendencias temporales
        temporal_trends = _get_temporal_trends(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Análisis de proyectos
        project_analytics = _get_project_task_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Métricas de gamificación
        gamification_analytics = _get_gamification_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Recomendaciones de mejora
        improvement_recommendations = _get_improvement_recommendations(
            productivity_analytics, time_analytics, priority_analytics
        )
        
        return render_template(
            'entrepreneur/tasks/analytics.html',
            productivity_analytics=productivity_analytics,
            time_analytics=time_analytics,
            priority_analytics=priority_analytics,
            category_analytics=category_analytics,
            temporal_trends=temporal_trends,
            project_analytics=project_analytics,
            gamification_analytics=gamification_analytics,
            improvement_recommendations=improvement_recommendations,
            start_date=start_date,
            end_date=end_date,
            current_range=date_range,
            priority_colors=PRIORITY_COLORS,
            category_icons=CATEGORY_ICONS
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando analytics de tareas: {str(e)}")
        flash('Error cargando las métricas', 'error')
        return redirect(url_for('entrepreneur_tasks.dashboard'))


@entrepreneur_tasks.route('/export')
@login_required
@require_role('entrepreneur')
@rate_limit(requests=5, window=300)  # 5 exportaciones por 5 minutos
def export_tasks():
    """
    Exportar tareas en diferentes formatos.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_completed = request.args.get('include_completed', 'false').lower() == 'true'
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Construir query de exportación
        query = Task.query.filter_by(
            entrepreneur_id=g.entrepreneur.id,
            is_deleted=False
        )
        
        if not include_completed:
            query = query.filter(Task.status != TaskStatus.COMPLETED)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Task.created_at >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Task.created_at <= to_date)
            except ValueError:
                pass
        
        tasks = query.options(
            joinedload(Task.project),
            joinedload(Task.assigned_to)
        ).order_by(desc(Task.created_at)).all()
        
        # Preparar datos para exportación
        export_data = _prepare_tasks_export_data(tasks)
        
        # Generar archivo según formato
        if export_format == 'excel':
            file_path = export_to_excel(export_data, f"tareas_{g.entrepreneur.id}")
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            extension = 'xlsx'
        elif export_format == 'csv':
            file_path = export_to_csv(export_data, f"tareas_{g.entrepreneur.id}")
            mimetype = 'text/csv'
            extension = 'csv'
        else:
            return jsonify({'success': False, 'error': 'Formato no soportado'}), 400
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='tasks_exported',
            resource_type='task',
            details={
                'format': export_format,
                'task_count': len(tasks),
                'include_completed': include_completed
            }
        )
        
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"tareas_{datetime.now().strftime('%Y%m%d')}.{extension}"
        )

    except Exception as e:
        current_app.logger.error(f"Error exportando tareas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error generando la exportación'
        }), 500


@entrepreneur_tasks.route('/pomodoro/<int:task_id>')
@login_required
@require_role('entrepreneur')
def pomodoro_timer(task_id):
    """
    Temporizador Pomodoro para una tarea específica.
    """
    try:
        task = _get_task_or_404(task_id)
        
        # Configuración del pomodoro
        pomodoro_config = {
            'work_duration': DEFAULT_POMODORO_DURATION,
            'short_break': 5,
            'long_break': 15,
            'sessions_until_long_break': 4
        }
        
        # Historial de pomodoros para esta tarea
        pomodoro_history = _get_task_pomodoro_history(task.id)
        
        return render_template(
            'entrepreneur/tasks/pomodoro.html',
            task=task,
            pomodoro_config=pomodoro_config,
            pomodoro_history=pomodoro_history
        )

    except ResourceNotFoundError:
        flash('Tarea no encontrada', 'error')
        return redirect(url_for('entrepreneur_tasks.list_tasks'))
    except Exception as e:
        current_app.logger.error(f"Error cargando pomodoro para tarea {task_id}: {str(e)}")
        flash('Error cargando el temporizador', 'error')
        return redirect(url_for('entrepreneur_tasks.view', task_id=task_id))


# === FUNCIONES AUXILIARES ===

def _get_task_or_404(task_id):
    """Obtener tarea validando pertenencia al emprendedor."""
    task = Task.query.filter_by(
        id=task_id,
        entrepreneur_id=g.entrepreneur.id,
        is_deleted=False
    ).first()
    
    if not task:
        raise ResourceNotFoundError("Tarea no encontrada")
    
    return task


def _get_todays_tasks(entrepreneur_id):
    """Obtener tareas programadas para hoy."""
    today = date.today()
    
    return Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            or_(
                Task.due_date == today,
                and_(
                    Task.status == TaskStatus.IN_PROGRESS,
                    Task.due_date.is_(None)
                )
            ),
            Task.is_deleted == False,
            Task.status != TaskStatus.COMPLETED
        )
    ).options(
        joinedload(Task.project)
    ).order_by(
        Task.priority.desc(),
        Task.due_date.asc()
    ).all()


def _get_upcoming_tasks(entrepreneur_id, days=7):
    """Obtener tareas próximas."""
    start_date = date.today() + timedelta(days=1)
    end_date = start_date + timedelta(days=days-1)
    
    return Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.due_date >= start_date,
            Task.due_date <= end_date,
            Task.is_deleted == False,
            Task.status != TaskStatus.COMPLETED
        )
    ).options(
        joinedload(Task.project)
    ).order_by(
        Task.due_date.asc(),
        Task.priority.desc()
    ).limit(10).all()


def _get_overdue_tasks(entrepreneur_id):
    """Obtener tareas vencidas."""
    today = date.today()
    
    return Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.due_date < today,
            Task.is_deleted == False,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
        )
    ).options(
        joinedload(Task.project)
    ).order_by(
        Task.due_date.asc(),
        Task.priority.desc()
    ).all()


def _get_task_metrics(entrepreneur_id):
    """Obtener métricas principales de tareas."""
    # Total de tareas
    total_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        is_deleted=False
    ).count()
    
    # Por estado
    pending_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=TaskStatus.PENDING,
        is_deleted=False
    ).count()
    
    in_progress_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=TaskStatus.IN_PROGRESS,
        is_deleted=False
    ).count()
    
    completed_tasks = Task.query.filter_by(
        entrepreneur_id=entrepreneur_id,
        status=TaskStatus.COMPLETED,
        is_deleted=False
    ).count()
    
    # Tareas vencidas
    today = date.today()
    overdue_tasks = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.due_date < today,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.is_deleted == False
        )
    ).count()
    
    # Tasa de completitud
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tiempo promedio de completitud
    avg_completion_time = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.isnot(None),
            Task.created_at.isnot(None),
            Task.is_deleted == False
        )
    ).with_entities(
        func.avg(
            func.julianday(Task.completed_at) - func.julianday(Task.created_at)
        )
    ).scalar() or 0
    
    return {
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_rate': round(completion_rate, 1),
        'avg_completion_days': round(avg_completion_time, 1)
    }


def _get_weekly_productivity(entrepreneur_id, week_start, week_end):
    """Obtener productividad de la semana."""
    # Tareas completadas esta semana
    completed_this_week = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.completed_at >= datetime.combine(week_start, time.min),
            Task.completed_at <= datetime.combine(week_end, time.max),
            Task.is_deleted == False
        )
    ).count()
    
    # Tiempo trabajado esta semana
    time_this_week = TaskTimeEntry.query.join(Task).filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            TaskTimeEntry.date >= week_start,
            TaskTimeEntry.date <= week_end
        )
    ).with_entities(func.sum(TaskTimeEntry.hours)).scalar() or 0
    
    # Productividad por día
    daily_productivity = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_completed = Task.query.filter(
            and_(
                Task.entrepreneur_id == entrepreneur_id,
                func.date(Task.completed_at) == day,
                Task.is_deleted == False
            )
        ).count()
        
        day_time = TaskTimeEntry.query.join(Task).filter(
            and_(
                Task.entrepreneur_id == entrepreneur_id,
                TaskTimeEntry.date == day
            )
        ).with_entities(func.sum(TaskTimeEntry.hours)).scalar() or 0
        
        daily_productivity.append({
            'date': day,
            'day_name': day.strftime('%A'),
            'completed_tasks': day_completed,
            'hours_worked': round(day_time, 1)
        })
    
    return {
        'completed_this_week': completed_this_week,
        'time_this_week': round(time_this_week, 1),
        'daily_productivity': daily_productivity
    }


def _get_project_task_progress(entrepreneur_id):
    """Obtener progreso de tareas por proyecto."""
    projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur_id
    ).options(
        selectinload(Project.tasks)
    ).all()
    
    project_progress = []
    for project in projects:
        active_tasks = [t for t in project.tasks if not t.is_deleted]
        completed_tasks = [t for t in active_tasks if t.status == TaskStatus.COMPLETED]
        
        if active_tasks:
            completion_percentage = len(completed_tasks) / len(active_tasks) * 100
        else:
            completion_percentage = 0
        
        project_progress.append({
            'project': project,
            'total_tasks': len(active_tasks),
            'completed_tasks': len(completed_tasks),
            'completion_percentage': round(completion_percentage, 1)
        })
    
    # Ordenar por porcentaje de completitud (descendente)
    project_progress.sort(key=lambda x: x['completion_percentage'], reverse=True)
    
    return project_progress[:10]  # Top 10 proyectos


def _get_category_distribution(entrepreneur_id):
    """Obtener distribución de tareas por categoría."""
    distribution = {}
    
    for category in TaskCategory:
        count = Task.query.filter_by(
            entrepreneur_id=entrepreneur_id,
            category=category,
            is_deleted=False
        ).count()
        
        if count > 0:
            distribution[category.value] = {
                'count': count,
                'icon': CATEGORY_ICONS.get(category, 'fa-tasks')
            }
    
    return distribution


def _get_gamification_data(entrepreneur_id):
    """Obtener datos de gamificación."""
    # Esto requeriría un modelo separado para puntos/logros
    # Por ahora retornamos datos mock
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    
    # Tareas completadas esta semana
    completed_this_week = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.completed_at >= datetime.combine(week_start, time.min),
            Task.status == TaskStatus.COMPLETED,
            Task.is_deleted == False
        )
    ).count()
    
    # Racha de días consecutivos
    current_streak = _calculate_completion_streak(entrepreneur_id)
    
    # Puntos estimados (simplificado)
    estimated_points = completed_this_week * POINTS_CONFIG['task_completed']
    
    return {
        'level': min(completed_this_week // 5 + 1, 10),  # Nivel basado en tareas
        'points_this_week': estimated_points,
        'current_streak': current_streak,
        'completed_this_week': completed_this_week,
        'next_level_tasks': 5 - (completed_this_week % 5),
        'badges': []  # Implementar sistema de badges
    }


def _get_recent_task_activity(entrepreneur_id, limit=10):
    """Obtener actividad reciente de tareas."""
    return ActivityLog.query.filter(
        and_(
            ActivityLog.user_id == entrepreneur_id,
            ActivityLog.resource_type == 'task'
        )
    ).order_by(desc(ActivityLog.created_at)).limit(limit).all()


def _get_time_analysis(entrepreneur_id, week_start, week_end):
    """Obtener análisis de tiempo de la semana."""
    # Tiempo estimado vs real
    tasks_with_estimates = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.estimated_hours.isnot(None),
            Task.actual_hours.isnot(None),
            Task.is_deleted == False
        )
    ).all()
    
    if tasks_with_estimates:
        total_estimated = sum(t.estimated_hours for t in tasks_with_estimates)
        total_actual = sum(t.actual_hours for t in tasks_with_estimates)
        accuracy = (total_estimated / total_actual * 100) if total_actual > 0 else 0
    else:
        total_estimated = 0
        total_actual = 0
        accuracy = 0
    
    # Distribución de tiempo por categoría
    time_by_category = {}
    for category in TaskCategory:
        category_time = TaskTimeEntry.query.join(Task).filter(
            and_(
                Task.entrepreneur_id == entrepreneur_id,
                Task.category == category,
                TaskTimeEntry.date >= week_start,
                TaskTimeEntry.date <= week_end
            )
        ).with_entities(func.sum(TaskTimeEntry.hours)).scalar() or 0
        
        if category_time > 0:
            time_by_category[category.value] = {
                'hours': round(category_time, 1),
                'icon': CATEGORY_ICONS.get(category, 'fa-tasks')
            }
    
    return {
        'total_estimated': round(total_estimated, 1),
        'total_actual': round(total_actual, 1),
        'estimation_accuracy': round(accuracy, 1),
        'time_by_category': time_by_category
    }


def _get_productivity_suggestions(task_metrics, weekly_productivity, overdue_tasks):
    """Obtener sugerencias de productividad."""
    suggestions = []
    
    # Sugerir priorización si hay muchas tareas vencidas
    if len(overdue_tasks) > 5:
        suggestions.append({
            'type': 'priority',
            'message': f'Tienes {len(overdue_tasks)} tareas vencidas. Considera repriorizarlas.',
            'action_url': url_for('entrepreneur_tasks.list_tasks', status='overdue'),
            'priority': 'high'
        })
    
    # Sugerir estimación de tiempo
    if task_metrics['total_tasks'] > 0:
        tasks_without_estimates = Task.query.filter(
            and_(
                Task.entrepreneur_id == g.entrepreneur.id,
                Task.estimated_hours.is_(None),
                Task.status != TaskStatus.COMPLETED,
                Task.is_deleted == False
            )
        ).count()
        
        if tasks_without_estimates > task_metrics['total_tasks'] * 0.5:
            suggestions.append({
                'type': 'estimation',
                'message': 'Muchas tareas no tienen estimación de tiempo. Esto ayuda a planificar mejor.',
                'action_url': url_for('entrepreneur_tasks.list_tasks', filter='no_estimate'),
                'priority': 'medium'
            })
    
    # Sugerir descansos si trabajó muchas horas
    if weekly_productivity['time_this_week'] > 40:
        suggestions.append({
            'type': 'break',
            'message': f'Has trabajado {weekly_productivity["time_this_week"]} horas esta semana. Recuerda tomar descansos.',
            'priority': 'low'
        })
    
    return suggestions


def _apply_task_filters(query, search_form):
    """Aplicar filtros de búsqueda a la consulta."""
    if search_form.search.data:
        search_term = f"%{search_form.search.data}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_term),
                Task.description.ilike(search_term)
            )
        )
    
    if search_form.status.data and search_form.status.data != 'all':
        if search_form.status.data == 'overdue':
            query = query.filter(
                and_(
                    Task.due_date < date.today(),
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
                )
            )
        else:
            query = query.filter_by(status=TaskStatus(search_form.status.data))
    
    if search_form.priority.data and search_form.priority.data != 'all':
        query = query.filter_by(priority=TaskPriority(search_form.priority.data))
    
    if search_form.category.data and search_form.category.data != 'all':
        query = query.filter_by(category=TaskCategory(search_form.category.data))
    
    if search_form.project_id.data:
        query = query.filter_by(project_id=search_form.project_id.data)
    
    if search_form.due_date_from.data:
        query = query.filter(Task.due_date >= search_form.due_date_from.data)
    
    if search_form.due_date_to.data:
        query = query.filter(Task.due_date <= search_form.due_date_to.data)
    
    return query


def _apply_task_sorting(query, sort_by, sort_order):
    """Aplicar ordenamiento a la consulta."""
    valid_sort_fields = {
        'title': Task.title,
        'created_at': Task.created_at,
        'updated_at': Task.updated_at,
        'due_date': Task.due_date,
        'priority': Task.priority,
        'status': Task.status
    }
    
    if sort_by == 'priority_due_date':
        # Ordenamiento especial: prioridad descendente, luego fecha límite ascendente
        query = query.order_by(Task.priority.desc(), Task.due_date.asc())
    elif sort_by in valid_sort_fields:
        sort_field = valid_sort_fields[sort_by]
        if sort_order == 'asc':
            query = query.order_by(asc(sort_field))
        else:
            query = query.order_by(desc(sort_field))
    else:
        # Ordenamiento por defecto
        query = query.order_by(Task.priority.desc(), Task.due_date.asc())
    
    return query


def _organize_tasks_for_kanban(tasks):
    """Organizar tareas para vista Kanban."""
    columns = {
        'pending': [],
        'in_progress': [],
        'completed': [],
        'cancelled': []
    }
    
    for task in tasks:
        if task.status == TaskStatus.PENDING:
            columns['pending'].append(task)
        elif task.status == TaskStatus.IN_PROGRESS:
            columns['in_progress'].append(task)
        elif task.status == TaskStatus.COMPLETED:
            columns['completed'].append(task)
        elif task.status == TaskStatus.CANCELLED:
            columns['cancelled'].append(task)
    
    return columns


def _format_tasks_for_calendar(tasks):
    """Formatear tareas para vista de calendario."""
    events = []
    
    for task in tasks:
        if task.due_date:
            event = {
                'id': f"task_{task.id}",
                'title': task.title,
                'start': task.due_date.isoformat(),
                'allDay': True,
                'backgroundColor': PRIORITY_COLORS.get(task.priority, '#6c757d'),
                'url': url_for('entrepreneur_tasks.view', task_id=task.id),
                'extendedProps': {
                    'type': 'task',
                    'priority': task.priority.value,
                    'status': task.status.value
                }
            }
            events.append(event)
    
    return events


def _calculate_list_metrics(tasks):
    """Calcular métricas de la lista actual."""
    if not tasks:
        return {
            'total': 0,
            'by_status': {},
            'by_priority': {},
            'avg_progress': 0
        }
    
    total = len(tasks)
    
    # Por estado
    by_status = {}
    for status in TaskStatus:
        count = len([t for t in tasks if t.status == status])
        if count > 0:
            by_status[status.value] = count
    
    # Por prioridad
    by_priority = {}
    for priority in TaskPriority:
        count = len([t for t in tasks if t.priority == priority])
        if count > 0:
            by_priority[priority.value] = count
    
    # Progreso promedio (simplificado)
    completed_count = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    avg_progress = (completed_count / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'by_status': by_status,
        'by_priority': by_priority,
        'avg_progress': round(avg_progress, 1)
    }


def _get_filter_options(entrepreneur_id):
    """Obtener opciones disponibles para filtros."""
    # Proyectos
    projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur_id
    ).order_by(Project.name).all()
    
    # Usuarios asignables (simplificado)
    assignable_users = []
    if g.entrepreneur.assigned_ally:
        assignable_users.append(g.entrepreneur.assigned_ally.user)
    
    return {
        'projects': projects,
        'assignable_users': assignable_users,
        'statuses': list(TaskStatus),
        'priorities': list(TaskPriority),
        'categories': list(TaskCategory)
    }


def _get_task_templates(entrepreneur_id):
    """Obtener plantillas de tareas guardadas."""
    # Esto requeriría un modelo TaskTemplate
    # Por ahora retorna lista vacía
    return []


def _populate_task_form_choices(form):
    """Poblar opciones del formulario de tarea."""
    # Prioridades
    form.priority.choices = [(p.value, p.value.title()) for p in TaskPriority]
    
    # Categorías
    form.category.choices = [('', 'Sin categoría')] + [(c.value, c.value.replace('_', ' ').title()) for c in TaskCategory]
    
    # Proyectos
    projects = Project.query.filter_by(
        entrepreneur_id=g.entrepreneur.id
    ).order_by(Project.name).all()
    form.project_id.choices = [('', 'Sin proyecto')] + [(p.id, p.name) for p in projects]
    
    # Usuarios asignables
    assignable_users = [('', 'Sin asignar')]
    if g.entrepreneur.assigned_ally:
        assignable_users.append((
            g.entrepreneur.assigned_ally.user.id,
            g.entrepreneur.assigned_ally.user.full_name
        ))
    form.assigned_to_id.choices = assignable_users


def _validate_task_data(form):
    """Validar datos de la tarea."""
    errors = []
    
    # Validar longitud del título
    if len(form.title.data) > MAX_TASK_TITLE_LENGTH:
        errors.append(f'El título no puede exceder {MAX_TASK_TITLE_LENGTH} caracteres')
    
    # Validar descripción
    if form.description.data and len(form.description.data) > MAX_DESCRIPTION_LENGTH:
        errors.append(f'La descripción no puede exceder {MAX_DESCRIPTION_LENGTH} caracteres')
    
    # Validar fecha límite
    if form.due_date.data and form.due_date.data < date.today():
        errors.append('La fecha límite no puede ser en el pasado')
    
    # Validar horas estimadas
    if form.estimated_hours.data and (form.estimated_hours.data <= 0 or form.estimated_hours.data > 1000):
        errors.append('Las horas estimadas deben estar entre 0.1 y 1000')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def _create_task_dependencies(task, dependencies_data):
    """Crear dependencias de tarea."""
    # Implementar creación de dependencias
    pass


def _create_task_recurrence(task, form):
    """Crear configuración de recurrencia."""
    # Implementar recurrencia de tareas
    pass


def _create_calendar_event_for_task(task):
    """Crear evento de calendario para la tarea."""
    if not g.calendar_service:
        return
    
    try:
        event_data = {
            'summary': f'Tarea: {task.title}',
            'description': task.description or '',
            'start': datetime.combine(task.due_date, time(9, 0)),
            'end': datetime.combine(task.due_date, time(10, 0)),
            'all_day': True
        }
        
        event_id = g.calendar_service.create_event(event_data)
        task.calendar_event_id = event_id
        task.save()
        
    except Exception as e:
        current_app.logger.error(f"Error creando evento de calendario: {str(e)}")
        raise


def _send_task_notifications(task, action, changes=None):
    """Enviar notificaciones relacionadas con la tarea."""
    # Notificar al asignado si no es el creador
    if task.assigned_to_id and task.assigned_to_id != current_user.id:
        message = f'Tarea "{task.title}" {action}'
        if changes:
            message += f' con cambios: {", ".join(changes.keys())}'
        
        NotificationService.send_notification(
            user_id=task.assigned_to_id,
            title=f'Tarea {action}',
            message=message,
            notification_type=f'task_{action}',
            related_id=task.id
        )
    
    # Notificar al mentor si la tarea es de alta prioridad
    if (task.priority == TaskPriority.URGENT and 
        g.entrepreneur.assigned_ally and 
        action == 'created'):
        
        NotificationService.send_notification(
            user_id=g.entrepreneur.assigned_ally.user_id,
            title='Tarea urgente creada',
            message=f'{current_user.full_name} creó una tarea urgente: "{task.title}"',
            notification_type='urgent_task_created',
            related_id=task.id
        )


def _award_points(entrepreneur_id, points, reason):
    """Otorgar puntos de gamificación."""
    # Esto requeriría un modelo UserPoints o similar
    # Por ahora solo lo registramos en el log
    ActivityLog.create(
        user_id=entrepreneur_id,
        action='points_awarded',
        resource_type='gamification',
        details={
            'points': points,
            'reason': reason
        }
    )


def _can_edit_task(task, user_id):
    """Verificar si el usuario puede editar la tarea."""
    # Es el creador o el asignado
    return (task.created_by == user_id or 
            task.assigned_to_id == user_id or
            task.entrepreneur_id == user_id)


def _can_delete_task(task, user_id):
    """Verificar si el usuario puede eliminar la tarea."""
    # Solo el creador puede eliminar
    return task.created_by == user_id


def _can_assign_task(task, user_id):
    """Verificar si el usuario puede asignar la tarea."""
    # Solo el creador o el emprendedor dueño
    return task.created_by == user_id or task.entrepreneur_id == user_id


def _is_valid_status_transition(old_status, new_status):
    """Validar transición de estado."""
    valid_transitions = {
        TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED],
        TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.PENDING],
        TaskStatus.COMPLETED: [TaskStatus.PENDING],  # Reabrir tarea
        TaskStatus.CANCELLED: [TaskStatus.PENDING]   # Reactivar tarea
    }
    
    return new_status in valid_transitions.get(old_status, [])


def _calculate_actual_hours(task):
    """Calcular horas reales trabajadas en la tarea."""
    total_hours = TaskTimeEntry.query.filter_by(
        task_id=task.id
    ).with_entities(func.sum(TaskTimeEntry.hours)).scalar()
    
    return total_hours or 0


def _calculate_completion_points(task):
    """Calcular puntos por completar la tarea."""
    points = POINTS_CONFIG['task_completed']
    
    # Bonus por prioridad
    if task.priority == TaskPriority.HIGH:
        points += POINTS_CONFIG['high_priority_completed'] - POINTS_CONFIG['task_completed']
    elif task.priority == TaskPriority.URGENT:
        points += POINTS_CONFIG['urgent_completed'] - POINTS_CONFIG['task_completed']
    
    # Bonus por completar antes de fecha límite
    if task.due_date and task.completed_at:
        if task.completed_at.date() < task.due_date:
            points += POINTS_CONFIG['early_completion']
    
    # Penalty/bonus por tareas vencidas
    if task.due_date and task.completed_at:
        if task.completed_at.date() > task.due_date:
            points = POINTS_CONFIG['overdue_completed']
    
    return points


def _update_dependent_tasks(task_id):
    """Actualizar tareas que dependen de esta."""
    # Implementar lógica de dependencias
    pass


def _calculate_completion_streak(entrepreneur_id):
    """Calcular racha de días consecutivos completando tareas."""
    # Implementar cálculo de racha
    return 0


# Funciones auxiliares adicionales (implementación simplificada por espacio)

def _get_task_template(template_id, entrepreneur_id):
    """Obtener plantilla de tarea."""
    return None

def _populate_form_from_template(form, template):
    """Poblar formulario desde plantilla."""
    pass

def _populate_edit_form_with_task_data(form, task):
    """Poblar formulario de edición con datos de la tarea."""
    pass

def _extract_task_data(task):
    """Extraer datos de la tarea para auditoria."""
    return {
        'title': task.title,
        'description': task.description,
        'priority': task.priority.value,
        'status': task.status.value,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'estimated_hours': task.estimated_hours,
        'assigned_to_id': task.assigned_to_id
    }

def _validate_task_changes(task, form):
    """Validar cambios en la tarea."""
    return {'valid': True, 'errors': []}

def _detect_task_changes(original_data, task):
    """Detectar cambios en la tarea."""
    changes = {}
    current_data = _extract_task_data(task)
    
    for key, new_value in current_data.items():
        old_value = original_data.get(key)
        if old_value != new_value:
            changes[key] = {
                'old': old_value,
                'new': new_value
            }
    
    return changes

def _update_calendar_event_for_task(task):
    """Actualizar evento de calendario de la tarea."""
    pass

def _notify_task_participants(task, comment):
    """Notificar participantes sobre nuevo comentario."""
    pass

def _get_task_dependencies(task_id):
    """Obtener dependencias de la tarea."""
    return []

def _get_dependent_tasks(task_id):
    """Obtener tareas que dependen de esta."""
    return []

def _get_related_tasks(task, limit=5):
    """Obtener tareas relacionadas."""
    related = []
    
    # Tareas del mismo proyecto
    if task.project_id:
        project_tasks = Task.query.filter(
            and_(
                Task.project_id == task.project_id,
                Task.id != task.id,
                Task.is_deleted == False
            )
        ).limit(limit).all()
        related.extend(project_tasks)
    
    return related[:limit]

def _calculate_task_metrics(task, time_entries):
    """Calcular métricas de la tarea."""
    total_time = sum(entry.hours for entry in time_entries)
    
    metrics = {
        'total_time_logged': total_time,
        'time_entries_count': len(time_entries),
        'estimated_vs_actual': None,
        'efficiency': None
    }
    
    if task.estimated_hours and total_time > 0:
        metrics['estimated_vs_actual'] = {
            'estimated': task.estimated_hours,
            'actual': total_time,
            'variance': total_time - task.estimated_hours,
            'variance_percentage': ((total_time - task.estimated_hours) / task.estimated_hours) * 100
        }
        
        metrics['efficiency'] = min((task.estimated_hours / total_time) * 100, 100)
    
    return metrics

def _analyze_task_progress(task, time_entries):
    """Analizar progreso de la tarea."""
    analysis = {
        'status': task.status.value,
        'is_overdue': False,
        'days_until_due': None,
        'time_utilization': None
    }
    
    if task.due_date:
        days_until = (task.due_date - date.today()).days
        analysis['days_until_due'] = days_until
        analysis['is_overdue'] = days_until < 0
    
    if task.estimated_hours and time_entries:
        total_logged = sum(entry.hours for entry in time_entries)
        analysis['time_utilization'] = (total_logged / task.estimated_hours) * 100
    
    return analysis

def _suggest_next_action(task):
    """Sugerir próxima acción para la tarea."""
    suggestions = []
    
    if task.status == TaskStatus.PENDING:
        suggestions.append("Comenzar a trabajar en esta tarea")
    elif task.status == TaskStatus.IN_PROGRESS:
        if not task.estimated_hours:
            suggestions.append("Agregar estimación de tiempo")
        else:
            suggestions.append("Registrar tiempo trabajado")
    
    if task.due_date and (task.due_date - date.today()).days <= 1:
        suggestions.append("Esta tarea vence pronto - priorizarla")
    
    return suggestions[0] if suggestions else None

# Funciones de analytics y bulk operations (implementación simplificada)

def _bulk_complete_tasks(tasks):
    """Completar tareas en masa."""
    count = 0
    for task in tasks:
        if task.status != TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.save()
            count += 1
    
    return {'message': f'{count} tarea(s) completada(s)', 'count': count}

def _bulk_delete_tasks(tasks):
    """Eliminar tareas en masa."""
    count = 0
    for task in tasks:
        task.is_deleted = True
        task.deleted_at = datetime.now(timezone.utc)
        task.save()
        count += 1
    
    return {'message': f'{count} tarea(s) eliminada(s)', 'count': count}

def _bulk_change_priority(tasks, new_priority):
    """Cambiar prioridad en masa."""
    count = 0
    for task in tasks:
        task.priority = new_priority
        task.save()
        count += 1
    
    return {'message': f'Prioridad cambiada en {count} tarea(s)', 'count': count}

def _bulk_assign_tasks(tasks, assignee_id):
    """Asignar tareas en masa."""
    count = 0
    for task in tasks:
        task.assigned_to_id = assignee_id
        task.save()
        count += 1
    
    return {'message': f'{count} tarea(s) asignada(s)', 'count': count}

def _bulk_move_to_project(tasks, project_id):
    """Mover tareas a proyecto en masa."""
    count = 0
    for task in tasks:
        task.project_id = project_id
        task.save()
        count += 1
    
    return {'message': f'{count} tarea(s) movida(s) al proyecto', 'count': count}

def _prepare_tasks_export_data(tasks):
    """Preparar datos para exportación."""
    export_data = []
    
    for task in tasks:
        export_data.append({
            'ID': task.id,
            'Título': task.title,
            'Descripción': task.description or '',
            'Estado': task.status.value,
            'Prioridad': task.priority.value,
            'Categoría': task.category.value if task.category else '',
            'Proyecto': task.project.name if task.project else '',
            'Asignado a': task.assigned_to.full_name if task.assigned_to else '',
            'Fecha límite': task.due_date.strftime('%d/%m/%Y') if task.due_date else '',
            'Horas estimadas': task.estimated_hours or 0,
            'Horas reales': task.actual_hours or 0,
            'Fecha creación': task.created_at.strftime('%d/%m/%Y %H:%M'),
            'Fecha completado': task.completed_at.strftime('%d/%m/%Y %H:%M') if task.completed_at else ''
        })
    
    return export_data

def _get_task_pomodoro_history(task_id):
    """Obtener historial de pomodoros de la tarea."""
    # Implementar historial de pomodoros
    return []

# Funciones de analytics (implementación simplificada)
def _get_productivity_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_time_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_priority_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_category_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_temporal_trends(entrepreneur_id, start_date, end_date):
    return {}

def _get_project_task_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_gamification_analytics(entrepreneur_id, start_date, end_date):
    return {}

def _get_improvement_recommendations(productivity, time_analytics, priority):
    return []


# === MANEJADORES DE ERRORES ===

@entrepreneur_tasks.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_tasks.dashboard'))


@entrepreneur_tasks.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_tasks.dashboard'))


@entrepreneur_tasks.errorhandler(ResourceNotFoundError)
def handle_not_found_error(error):
    """Manejar errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 404
    else:
        flash(str(error), 'error')
        return redirect(url_for('entrepreneur_tasks.dashboard'))


# === CONTEXT PROCESSORS ===

@entrepreneur_tasks.context_processor
def inject_task_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_relative_time': format_relative_time,
        'format_duration': format_duration,
        'format_time_spent': format_time_spent,
        'format_percentage': format_percentage,
        'TaskStatus': TaskStatus,
        'TaskPriority': TaskPriority,
        'TaskCategory': TaskCategory,
        'priority_colors': PRIORITY_COLORS,
        'category_icons': CATEGORY_ICONS,
        'points_config': POINTS_CONFIG
    }