"""
Gestión de Proyectos del Emprendedor - Vista completa para CRUD y seguimiento de proyectos.

Este módulo contiene todas las vistas relacionadas con la gestión de proyectos
del emprendedor, incluyendo creación, edición, seguimiento, tareas, documentos,
colaboradores, métricas y análisis de progreso.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, g, send_file
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, case
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, ResourceNotFoundError
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project, ProjectStatus, ProjectPriority, ProjectCategory
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.document import Document, DocumentType
from app.models.meeting import Meeting, MeetingStatus
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.models.user import User
from app.forms.project import (
    ProjectForm, ProjectEditForm, TaskForm, ProjectSearchForm,
    ProjectCollaboratorForm, ProjectSettingsForm, ProjectExportForm,
    BulkActionForm, ProjectTemplateForm
)
from app.services.project_service import ProjectService
from app.services.entrepreneur_service import EntrepreneurService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.file_storage import FileStorageService
from app.services.email import EmailService
from app.utils.decorators import cache_response, rate_limit, validate_json
from app.utils.validators import validate_url, validate_date_range
from app.utils.formatters import format_currency, format_percentage, format_file_size
from app.utils.date_utils import format_relative_time, get_date_range_filter
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.string_utils import sanitize_input, generate_slug, truncate_text
from app.utils.pagination import get_pagination_params, create_pagination_object

# Crear blueprint para proyectos del emprendedor
entrepreneur_projects = Blueprint(
    'entrepreneur_projects', 
    __name__, 
    url_prefix='/entrepreneur/projects'
)

# Configuraciones
ITEMS_PER_PAGE = 12
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_DOC_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
    'txt', 'png', 'jpg', 'jpeg', 'gif', 'zip'
}


@entrepreneur_projects.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.project_service = ProjectService(g.entrepreneur)
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
    else:
        g.entrepreneur = None
        g.project_service = None
        g.entrepreneur_service = None


@entrepreneur_projects.route('/')
@entrepreneur_projects.route('/list')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=180)  # Cache por 3 minutos
def index():
    """
    Vista principal de proyectos del emprendedor.
    
    Incluye:
    - Listado paginado de proyectos
    - Filtros por estado, prioridad, categoría
    - Búsqueda por nombre/descripción
    - Métricas generales
    - Acciones masivas
    """
    try:
        # Obtener parámetros de filtrado y paginación
        page, per_page = get_pagination_params(request, default_per_page=ITEMS_PER_PAGE)
        search_form = ProjectSearchForm(request.args)
        
        # Construir query base
        query = Project.query.filter_by(entrepreneur_id=g.entrepreneur.id)
        
        # Aplicar filtros
        query = _apply_project_filters(query, search_form)
        
        # Aplicar ordenamiento
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')
        query = _apply_sorting(query, sort_by, sort_order)
        
        # Optimizar consultas con eager loading
        query = query.options(
            selectinload(Project.tasks),
            selectinload(Project.documents),
            joinedload(Project.assigned_ally)
        )
        
        # Paginación
        projects_pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Métricas generales
        project_metrics = _get_project_metrics(g.entrepreneur.id)
        
        # Proyectos recientes para dashboard
        recent_projects = _get_recent_projects(g.entrepreneur.id, limit=5)
        
        # Datos para gráficos
        chart_data = _get_projects_chart_data(g.entrepreneur.id)
        
        return render_template(
            'entrepreneur/projects/index.html',
            projects=projects_pagination.items,
            pagination=projects_pagination,
            search_form=search_form,
            metrics=project_metrics,
            recent_projects=recent_projects,
            chart_data=chart_data,
            current_sort=f"{sort_by}_{sort_order}",
            ProjectStatus=ProjectStatus,
            ProjectPriority=ProjectPriority,
            ProjectCategory=ProjectCategory
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando proyectos: {str(e)}")
        flash('Error cargando los proyectos', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_projects.route('/create', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def create():
    """
    Crear nuevo proyecto.
    """
    form = ProjectForm()
    
    if request.method == 'GET':
        # Cargar datos para formulario
        _populate_form_choices(form)
        return render_template(
            'entrepreneur/projects/create.html',
            form=form,
            entrepreneur=g.entrepreneur
        )
    
    try:
        if not form.validate_on_submit():
            _populate_form_choices(form)
            return render_template(
                'entrepreneur/projects/create.html',
                form=form,
                entrepreneur=g.entrepreneur
            )
        
        # Crear proyecto usando servicio
        project_data = {
            'name': sanitize_input(form.name.data),
            'description': sanitize_input(form.description.data),
            'category': form.category.data,
            'priority': form.priority.data,
            'status': ProjectStatus.PLANNING,
            'start_date': form.start_date.data,
            'end_date': form.end_date.data,
            'budget': form.budget.data,
            'is_public': form.is_public.data,
            'tags': form.tags.data
        }
        
        # Validar fechas
        if project_data['end_date'] and project_data['start_date']:
            if project_data['end_date'] <= project_data['start_date']:
                form.end_date.errors.append('La fecha de fin debe ser posterior a la fecha de inicio')
                _populate_form_choices(form)
                return render_template('entrepreneur/projects/create.html', form=form)
        
        # Crear proyecto
        project = g.project_service.create_project(project_data)
        
        # Crear tareas iniciales si se proporcionaron
        if form.initial_tasks.data:
            _create_initial_tasks(project, form.initial_tasks.data)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='project_created',
            resource_type='project',
            resource_id=project.id,
            details={
                'project_name': project.name,
                'category': project.category.value if project.category else None
            }
        )
        
        # Enviar notificación si hay aliado asignado
        if g.entrepreneur.assigned_ally:
            NotificationService.send_notification(
                user_id=g.entrepreneur.assigned_ally.user_id,
                title='Nuevo proyecto creado',
                message=f'{current_user.full_name} ha creado el proyecto "{project.name}"',
                notification_type='project_created',
                related_id=project.id
            )
        
        flash(f'Proyecto "{project.name}" creado exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Proyecto creado exitosamente',
                'project_id': project.id,
                'redirect_url': url_for('entrepreneur_projects.view', project_id=project.id)
            })
        else:
            return redirect(url_for('entrepreneur_projects.view', project_id=project.id))

    except ValidationError as e:
        error_msg = str(e)
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        else:
            flash(error_msg, 'error')
            _populate_form_choices(form)
            return render_template('entrepreneur/projects/create.html', form=form)

    except Exception as e:
        current_app.logger.error(f"Error creando proyecto: {str(e)}")
        error_msg = 'Error creando el proyecto'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            _populate_form_choices(form)
            return render_template('entrepreneur/projects/create.html', form=form)


@entrepreneur_projects.route('/<int:project_id>')
@entrepreneur_projects.route('/<int:project_id>/view')
@login_required
@require_role('entrepreneur')
def view(project_id):
    """
    Ver detalles completos de un proyecto.
    """
    try:
        # Obtener proyecto con validación de pertenencia
        project = _get_project_or_404(project_id)
        
        # Obtener tareas del proyecto
        tasks = Task.query.filter_by(project_id=project.id).options(
            joinedload(Task.assigned_to)
        ).order_by(Task.priority.desc(), Task.created_at.desc()).all()
        
        # Obtener documentos del proyecto
        documents = Document.query.filter_by(
            project_id=project.id
        ).order_by(desc(Document.created_at)).limit(20).all()
        
        # Obtener reuniones relacionadas
        meetings = Meeting.query.filter_by(
            project_id=project.id
        ).order_by(desc(Meeting.scheduled_at)).limit(10).all()
        
        # Obtener actividad reciente
        recent_activity = ActivityLog.query.filter_by(
            resource_type='project',
            resource_id=project.id
        ).order_by(desc(ActivityLog.created_at)).limit(15).all()
        
        # Métricas del proyecto
        project_metrics = _get_single_project_metrics(project)
        
        # Progreso por categorías
        progress_data = _get_project_progress_data(project)
        
        # Timeline del proyecto
        timeline_data = _get_project_timeline(project)
        
        # Verificar si puede editar
        can_edit = _can_edit_project(project)
        
        return render_template(
            'entrepreneur/projects/view.html',
            project=project,
            tasks=tasks,
            documents=documents,
            meetings=meetings,
            recent_activity=recent_activity,
            metrics=project_metrics,
            progress_data=progress_data,
            timeline_data=timeline_data,
            can_edit=can_edit,
            ProjectStatus=ProjectStatus,
            TaskStatus=TaskStatus,
            TaskPriority=TaskPriority
        )

    except ResourceNotFoundError:
        flash('Proyecto no encontrado', 'error')
        return redirect(url_for('entrepreneur_projects.index'))
    except Exception as e:
        current_app.logger.error(f"Error mostrando proyecto {project_id}: {str(e)}")
        flash('Error cargando el proyecto', 'error')
        return redirect(url_for('entrepreneur_projects.index'))


@entrepreneur_projects.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def edit(project_id):
    """
    Editar proyecto existente.
    """
    try:
        project = _get_project_or_404(project_id)
        
        # Verificar permisos de edición
        if not _can_edit_project(project):
            flash('No tienes permisos para editar este proyecto', 'error')
            return redirect(url_for('entrepreneur_projects.view', project_id=project_id))
        
        form = ProjectEditForm(obj=project)
        
        if request.method == 'GET':
            _populate_form_choices(form)
            _populate_edit_form(form, project)
            return render_template(
                'entrepreneur/projects/edit.html',
                form=form,
                project=project
            )
        
        if not form.validate_on_submit():
            _populate_form_choices(form)
            return render_template(
                'entrepreneur/projects/edit.html',
                form=form,
                project=project
            )
        
        # Guardar datos originales para auditoria
        original_data = {
            'name': project.name,
            'description': project.description,
            'status': project.status,
            'priority': project.priority,
            'budget': project.budget
        }
        
        # Actualizar proyecto
        updated_data = {
            'name': sanitize_input(form.name.data),
            'description': sanitize_input(form.description.data),
            'category': form.category.data,
            'priority': form.priority.data,
            'start_date': form.start_date.data,
            'end_date': form.end_date.data,
            'budget': form.budget.data,
            'is_public': form.is_public.data,
            'tags': form.tags.data
        }
        
        # Validar fechas
        if updated_data['end_date'] and updated_data['start_date']:
            if updated_data['end_date'] <= updated_data['start_date']:
                form.end_date.errors.append('La fecha de fin debe ser posterior a la fecha de inicio')
                _populate_form_choices(form)
                return render_template('entrepreneur/projects/edit.html', form=form, project=project)
        
        # Actualizar usando servicio
        updated_project = g.project_service.update_project(project.id, updated_data)
        
        # Registrar cambios en actividad
        changes = _detect_project_changes(original_data, updated_data)
        if changes:
            ActivityLog.create(
                user_id=current_user.id,
                action='project_updated',
                resource_type='project',
                resource_id=project.id,
                details={
                    'changes': changes,
                    'project_name': updated_project.name
                }
            )
        
        flash('Proyecto actualizado exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Proyecto actualizado exitosamente',
                'redirect_url': url_for('entrepreneur_projects.view', project_id=project.id)
            })
        else:
            return redirect(url_for('entrepreneur_projects.view', project_id=project.id))

    except ResourceNotFoundError:
        flash('Proyecto no encontrado', 'error')
        return redirect(url_for('entrepreneur_projects.index'))
    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            _populate_form_choices(form)
            return render_template('entrepreneur/projects/edit.html', form=form, project=project)
    except Exception as e:
        current_app.logger.error(f"Error editando proyecto {project_id}: {str(e)}")
        error_msg = 'Error actualizando el proyecto'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            return redirect(url_for('entrepreneur_projects.view', project_id=project_id))


@entrepreneur_projects.route('/<int:project_id>/status', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=30, window=60)
def change_status(project_id):
    """
    Cambiar estado de un proyecto.
    """
    try:
        project = _get_project_or_404(project_id)
        
        new_status = request.json.get('status')
        if not new_status or new_status not in [status.value for status in ProjectStatus]:
            return jsonify({
                'success': False,
                'error': 'Estado no válido'
            }), 400
        
        old_status = project.status
        new_status_enum = ProjectStatus(new_status)
        
        # Validar transición de estado
        if not _is_valid_status_transition(old_status, new_status_enum):
            return jsonify({
                'success': False,
                'error': 'Transición de estado no válida'
            }), 400
        
        # Actualizar estado
        project.status = new_status_enum
        project.updated_at = datetime.now(timezone.utc)
        
        # Lógica específica por estado
        if new_status_enum == ProjectStatus.COMPLETED:
            project.completed_at = datetime.now(timezone.utc)
            project.progress_percentage = 100.0
        elif new_status_enum == ProjectStatus.ACTIVE and old_status == ProjectStatus.PAUSED:
            project.resumed_at = datetime.now(timezone.utc)
        elif new_status_enum == ProjectStatus.PAUSED:
            project.paused_at = datetime.now(timezone.utc)
        elif new_status_enum == ProjectStatus.CANCELLED:
            project.cancelled_at = datetime.now(timezone.utc)
        
        project.save()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='project_status_changed',
            resource_type='project',
            resource_id=project.id,
            details={
                'old_status': old_status.value,
                'new_status': new_status,
                'project_name': project.name
            }
        )
        
        # Enviar notificaciones si es necesario
        if new_status_enum in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]:
            _send_project_status_notifications(project, old_status, new_status_enum)
        
        return jsonify({
            'success': True,
            'message': f'Estado del proyecto cambiado a {new_status_enum.value}',
            'new_status': new_status,
            'status_label': _get_status_label(new_status_enum)
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Proyecto no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error cambiando estado del proyecto {project_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error cambiando el estado'
        }), 500


@entrepreneur_projects.route('/<int:project_id>/tasks', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def manage_tasks(project_id):
    """
    Gestionar tareas de un proyecto.
    """
    try:
        project = _get_project_or_404(project_id)
        
        if request.method == 'GET':
            # Obtener tareas con filtros
            status_filter = request.args.get('status')
            priority_filter = request.args.get('priority')
            
            query = Task.query.filter_by(project_id=project.id)
            
            if status_filter and status_filter != 'all':
                query = query.filter_by(status=TaskStatus(status_filter))
            
            if priority_filter and priority_filter != 'all':
                query = query.filter_by(priority=TaskPriority(priority_filter))
            
            tasks = query.options(
                joinedload(Task.assigned_to)
            ).order_by(
                Task.priority.desc(),
                Task.due_date.asc(),
                Task.created_at.desc()
            ).all()
            
            # Métricas de tareas
            task_metrics = _get_project_task_metrics(project.id)
            
            return render_template(
                'entrepreneur/projects/tasks.html',
                project=project,
                tasks=tasks,
                task_metrics=task_metrics,
                TaskStatus=TaskStatus,
                TaskPriority=TaskPriority,
                current_filters={
                    'status': status_filter or 'all',
                    'priority': priority_filter or 'all'
                }
            )
        
        # POST: Crear nueva tarea
        form = TaskForm()
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        # Crear tarea
        task_data = {
            'title': sanitize_input(form.title.data),
            'description': sanitize_input(form.description.data),
            'priority': form.priority.data,
            'due_date': form.due_date.data,
            'estimated_hours': form.estimated_hours.data,
            'project_id': project.id,
            'entrepreneur_id': g.entrepreneur.id
        }
        
        task = Task.create(**task_data)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='task_created',
            resource_type='task',
            resource_id=task.id,
            details={
                'task_title': task.title,
                'project_name': project.name
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Tarea creada exitosamente',
            'task_id': task.id
        })

    except ResourceNotFoundError:
        if request.method == 'GET':
            flash('Proyecto no encontrado', 'error')
            return redirect(url_for('entrepreneur_projects.index'))
        else:
            return jsonify({'success': False, 'error': 'Proyecto no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error gestionando tareas del proyecto {project_id}: {str(e)}")
        if request.method == 'GET':
            flash('Error cargando las tareas', 'error')
            return redirect(url_for('entrepreneur_projects.view', project_id=project_id))
        else:
            return jsonify({'success': False, 'error': 'Error procesando solicitud'}), 500


@entrepreneur_projects.route('/<int:project_id>/documents')
@login_required
@require_role('entrepreneur')
def documents(project_id):
    """
    Gestionar documentos de un proyecto.
    """
    try:
        project = _get_project_or_404(project_id)
        
        # Obtener documentos con paginación
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        documents_query = Document.query.filter_by(project_id=project.id)
        
        # Filtro por tipo
        doc_type = request.args.get('type')
        if doc_type and doc_type != 'all':
            documents_query = documents_query.filter_by(document_type=DocumentType(doc_type))
        
        documents_pagination = documents_query.order_by(
            desc(Document.created_at)
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Métricas de documentos
        doc_metrics = _get_project_document_metrics(project.id)
        
        return render_template(
            'entrepreneur/projects/documents.html',
            project=project,
            documents=documents_pagination.items,
            pagination=documents_pagination,
            doc_metrics=doc_metrics,
            DocumentType=DocumentType,
            current_type_filter=doc_type or 'all'
        )

    except ResourceNotFoundError:
        flash('Proyecto no encontrado', 'error')
        return redirect(url_for('entrepreneur_projects.index'))
    except Exception as e:
        current_app.logger.error(f"Error cargando documentos del proyecto {project_id}: {str(e)}")
        flash('Error cargando los documentos', 'error')
        return redirect(url_for('entrepreneur_projects.view', project_id=project_id))


@entrepreneur_projects.route('/<int:project_id>/upload-document', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 uploads por 5 minutos
def upload_document(project_id):
    """
    Subir documento a un proyecto.
    """
    try:
        project = _get_project_or_404(project_id)
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se seleccionó archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó archivo'}), 400
        
        # Validar archivo
        if not _is_allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Tipo de archivo no permitido'
            }), 400
        
        # Validar tamaño
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_UPLOAD_SIZE:
            return jsonify({
                'success': False,
                'error': f'Archivo muy grande (máximo {format_file_size(MAX_UPLOAD_SIZE)})'
            }), 400
        
        # Obtener metadatos
        document_type = request.form.get('document_type', 'other')
        description = sanitize_input(request.form.get('description', ''))
        
        # Guardar archivo
        storage_service = FileStorageService()
        file_path = storage_service.save_project_document(
            file, 
            project.id, 
            current_user.id
        )
        
        # Crear registro en BD
        document = Document.create(
            filename=secure_filename(file.filename),
            original_filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type,
            document_type=DocumentType(document_type),
            description=description,
            project_id=project.id,
            uploaded_by=current_user.id
        )
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='document_uploaded',
            resource_type='document',
            resource_id=document.id,
            details={
                'filename': file.filename,
                'project_name': project.name,
                'file_size': file_size
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Documento subido exitosamente',
            'document_id': document.id,
            'filename': document.filename,
            'file_size': format_file_size(document.file_size),
            'upload_date': document.created_at.strftime('%d/%m/%Y %H:%M')
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Proyecto no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error subiendo documento al proyecto {project_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error subiendo el documento'
        }), 500


@entrepreneur_projects.route('/<int:project_id>/analytics')
@login_required
@require_role('entrepreneur')
def analytics(project_id):
    """
    Analytics y métricas detalladas del proyecto.
    """
    try:
        project = _get_project_or_404(project_id)
        
        # Obtener rango de fechas
        date_range = request.args.get('range', '30')  # días
        start_date, end_date = get_date_range_filter(date_range)
        
        # Obtener analytics del servicio
        analytics_service = AnalyticsService()
        
        # Métricas principales
        project_analytics = analytics_service.get_project_analytics(
            project.id, start_date, end_date
        )
        
        # Progreso histórico
        progress_history = analytics_service.get_project_progress_history(
            project.id, start_date, end_date
        )
        
        # Análisis de tareas
        task_analytics = analytics_service.get_project_task_analytics(
            project.id, start_date, end_date
        )
        
        # Tiempo invertido
        time_analytics = analytics_service.get_project_time_analytics(
            project.id, start_date, end_date
        )
        
        # Comparación con otros proyectos
        comparative_data = analytics_service.get_project_comparative_analytics(
            project.id, g.entrepreneur.id
        )
        
        return render_template(
            'entrepreneur/projects/analytics.html',
            project=project,
            analytics=project_analytics,
            progress_history=progress_history,
            task_analytics=task_analytics,
            time_analytics=time_analytics,
            comparative_data=comparative_data,
            current_range=date_range,
            start_date=start_date,
            end_date=end_date
        )

    except ResourceNotFoundError:
        flash('Proyecto no encontrado', 'error')
        return redirect(url_for('entrepreneur_projects.index'))
    except Exception as e:
        current_app.logger.error(f"Error cargando analytics del proyecto {project_id}: {str(e)}")
        flash('Error cargando las métricas', 'error')
        return redirect(url_for('entrepreneur_projects.view', project_id=project_id))


@entrepreneur_projects.route('/<int:project_id>/export')
@login_required
@require_role('entrepreneur')
@rate_limit(requests=5, window=300)  # 5 exports por 5 minutos
def export_project(project_id):
    """
    Exportar datos del proyecto en diferentes formatos.
    """
    try:
        project = _get_project_or_404(project_id)
        
        export_format = request.args.get('format', 'excel')
        include_tasks = request.args.get('include_tasks', 'true').lower() == 'true'
        include_documents = request.args.get('include_documents', 'false').lower() == 'true'
        include_analytics = request.args.get('include_analytics', 'true').lower() == 'true'
        
        # Preparar datos para exportación
        export_data = g.project_service.prepare_export_data(
            project.id,
            include_tasks=include_tasks,
            include_documents=include_documents,
            include_analytics=include_analytics
        )
        
        # Generar archivo según formato
        if export_format == 'excel':
            file_path = export_to_excel(export_data, f"proyecto_{project.id}")
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif export_format == 'pdf':
            file_path = export_to_pdf(export_data, f"proyecto_{project.id}")
            mimetype = 'application/pdf'
        elif export_format == 'csv':
            file_path = export_to_csv(export_data, f"proyecto_{project.id}")
            mimetype = 'text/csv'
        else:
            return jsonify({'success': False, 'error': 'Formato no soportado'}), 400
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='project_exported',
            resource_type='project',
            resource_id=project.id,
            details={
                'format': export_format,
                'project_name': project.name,
                'include_tasks': include_tasks,
                'include_documents': include_documents
            }
        )
        
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{generate_slug(project.name)}_{datetime.now().strftime('%Y%m%d')}.{export_format}"
        )

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Proyecto no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error exportando proyecto {project_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error generando la exportación'
        }), 500


@entrepreneur_projects.route('/<int:project_id>/delete', methods=['POST'])
@login_required
@require_role('entrepreneur')
def delete(project_id):
    """
    Eliminar proyecto (soft delete).
    """
    try:
        project = _get_project_or_404(project_id)
        
        # Verificar permisos
        if not _can_delete_project(project):
            return jsonify({
                'success': False,
                'error': 'No se puede eliminar este proyecto'
            }), 403
        
        # Verificar confirmación
        confirmation = request.json.get('confirmation')
        if confirmation != project.name:
            return jsonify({
                'success': False,
                'error': 'Confirmación incorrecta'
            }), 400
        
        # Soft delete
        project_name = project.name
        g.project_service.delete_project(project.id)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='project_deleted',
            resource_type='project',
            resource_id=project.id,
            details={
                'project_name': project_name,
                'deletion_reason': 'user_requested'
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Proyecto "{project_name}" eliminado exitosamente',
            'redirect_url': url_for('entrepreneur_projects.index')
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Proyecto no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error eliminando proyecto {project_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error eliminando el proyecto'
        }), 500


@entrepreneur_projects.route('/bulk-actions', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)
def bulk_actions():
    """
    Realizar acciones masivas en proyectos.
    """
    try:
        form = BulkActionForm()
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        action = form.action.data
        project_ids = form.project_ids.data
        
        if not project_ids:
            return jsonify({
                'success': False,
                'error': 'No se seleccionaron proyectos'
            }), 400
        
        # Verificar que todos los proyectos pertenezcan al emprendedor
        projects = Project.query.filter(
            and_(
                Project.id.in_(project_ids),
                Project.entrepreneur_id == g.entrepreneur.id
            )
        ).all()
        
        if len(projects) != len(project_ids):
            return jsonify({
                'success': False,
                'error': 'Algunos proyectos no fueron encontrados'
            }), 404
        
        # Ejecutar acción
        results = g.project_service.execute_bulk_action(action, project_ids)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action=f'bulk_{action}',
            resource_type='project',
            details={
                'project_count': len(project_ids),
                'project_ids': project_ids,
                'results': results
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Acción "{action}" ejecutada en {len(projects)} proyectos',
            'results': results
        })

    except Exception as e:
        current_app.logger.error(f"Error en acciones masivas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error ejecutando la acción'
        }), 500


# === FUNCIONES AUXILIARES ===

def _get_project_or_404(project_id):
    """Obtener proyecto validando pertenencia al emprendedor."""
    project = Project.query.filter_by(
        id=project_id,
        entrepreneur_id=g.entrepreneur.id
    ).first()
    
    if not project:
        raise ResourceNotFoundError("Proyecto no encontrado")
    
    return project


def _apply_project_filters(query, search_form):
    """Aplicar filtros de búsqueda a la consulta."""
    if search_form.search.data:
        search_term = f"%{search_form.search.data}%"
        query = query.filter(
            or_(
                Project.name.ilike(search_term),
                Project.description.ilike(search_term)
            )
        )
    
    if search_form.status.data and search_form.status.data != 'all':
        query = query.filter_by(status=ProjectStatus(search_form.status.data))
    
    if search_form.priority.data and search_form.priority.data != 'all':
        query = query.filter_by(priority=ProjectPriority(search_form.priority.data))
    
    if search_form.category.data and search_form.category.data != 'all':
        query = query.filter_by(category=ProjectCategory(search_form.category.data))
    
    if search_form.date_from.data:
        query = query.filter(Project.created_at >= search_form.date_from.data)
    
    if search_form.date_to.data:
        query = query.filter(Project.created_at <= search_form.date_to.data)
    
    return query


def _apply_sorting(query, sort_by, sort_order):
    """Aplicar ordenamiento a la consulta."""
    valid_sort_fields = {
        'name': Project.name,
        'created_at': Project.created_at,
        'updated_at': Project.updated_at,
        'status': Project.status,
        'priority': Project.priority,
        'progress': Project.progress_percentage
    }
    
    if sort_by not in valid_sort_fields:
        sort_by = 'updated_at'
    
    sort_field = valid_sort_fields[sort_by]
    
    if sort_order == 'asc':
        query = query.order_by(asc(sort_field))
    else:
        query = query.order_by(desc(sort_field))
    
    return query


def _get_project_metrics(entrepreneur_id):
    """Obtener métricas generales de proyectos."""
    projects = Project.query.filter_by(entrepreneur_id=entrepreneur_id).all()
    
    if not projects:
        return {
            'total': 0,
            'active': 0,
            'completed': 0,
            'paused': 0,
            'cancelled': 0,
            'avg_progress': 0,
            'total_budget': 0,
            'completion_rate': 0
        }
    
    total = len(projects)
    active = len([p for p in projects if p.status == ProjectStatus.ACTIVE])
    completed = len([p for p in projects if p.status == ProjectStatus.COMPLETED])
    paused = len([p for p in projects if p.status == ProjectStatus.PAUSED])
    cancelled = len([p for p in projects if p.status == ProjectStatus.CANCELLED])
    
    avg_progress = sum([p.progress_percentage or 0 for p in projects]) / total
    total_budget = sum([p.budget or 0 for p in projects])
    completion_rate = (completed / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'active': active,
        'completed': completed,
        'paused': paused,
        'cancelled': cancelled,
        'avg_progress': round(avg_progress, 1),
        'total_budget': total_budget,
        'completion_rate': round(completion_rate, 1)
    }


def _get_recent_projects(entrepreneur_id, limit=5):
    """Obtener proyectos recientes."""
    return Project.query.filter_by(
        entrepreneur_id=entrepreneur_id
    ).order_by(desc(Project.updated_at)).limit(limit).all()


def _get_projects_chart_data(entrepreneur_id):
    """Obtener datos para gráficos."""
    # Por estado
    status_data = {}
    for status in ProjectStatus:
        count = Project.query.filter_by(
            entrepreneur_id=entrepreneur_id,
            status=status
        ).count()
        status_data[status.value] = count
    
    # Progreso por mes (últimos 6 meses)
    from dateutil.relativedelta import relativedelta
    
    monthly_data = []
    for i in range(6):
        month_start = datetime.now().replace(day=1) - relativedelta(months=i)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)
        
        projects_count = Project.query.filter(
            and_(
                Project.entrepreneur_id == entrepreneur_id,
                Project.created_at >= month_start,
                Project.created_at <= month_end
            )
        ).count()
        
        monthly_data.append({
            'month': month_start.strftime('%B %Y'),
            'count': projects_count
        })
    
    monthly_data.reverse()
    
    return {
        'status_distribution': status_data,
        'monthly_progress': monthly_data
    }


def _get_single_project_metrics(project):
    """Obtener métricas de un proyecto específico."""
    tasks = Task.query.filter_by(project_id=project.id).all()
    documents = Document.query.filter_by(project_id=project.id).all()
    
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    pending_tasks = len([t for t in tasks if t.status == TaskStatus.PENDING])
    
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    total_documents = len(documents)
    total_file_size = sum([d.file_size for d in documents])
    
    # Tiempo estimado vs real
    estimated_hours = sum([t.estimated_hours or 0 for t in tasks])
    actual_hours = sum([t.actual_hours or 0 for t in tasks])
    
    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'task_completion_rate': round(task_completion_rate, 1),
        'total_documents': total_documents,
        'total_file_size': total_file_size,
        'estimated_hours': estimated_hours,
        'actual_hours': actual_hours,
        'time_efficiency': (estimated_hours / actual_hours * 100) if actual_hours > 0 else 0
    }


def _get_project_progress_data(project):
    """Obtener datos de progreso del proyecto."""
    tasks = Task.query.filter_by(project_id=project.id).all()
    
    if not tasks:
        return {
            'by_status': {},
            'by_priority': {},
            'timeline': []
        }
    
    # Por estado
    status_data = {}
    for status in TaskStatus:
        count = len([t for t in tasks if t.status == status])
        status_data[status.value] = count
    
    # Por prioridad
    priority_data = {}
    for priority in TaskPriority:
        count = len([t for t in tasks if t.priority == priority])
        priority_data[priority.value] = count
    
    # Timeline (próximas 4 semanas)
    timeline = []
    for i in range(4):
        week_start = datetime.now() + timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        
        week_tasks = [
            t for t in tasks 
            if t.due_date and week_start.date() <= t.due_date <= week_end.date()
        ]
        
        timeline.append({
            'week': f"Semana {i+1}",
            'tasks': len(week_tasks),
            'start_date': week_start.strftime('%d/%m'),
            'end_date': week_end.strftime('%d/%m')
        })
    
    return {
        'by_status': status_data,
        'by_priority': priority_data,
        'timeline': timeline
    }


def _get_project_timeline(project):
    """Obtener timeline del proyecto."""
    # Obtener actividades del proyecto
    activities = ActivityLog.query.filter_by(
        resource_type='project',
        resource_id=project.id
    ).order_by(desc(ActivityLog.created_at)).limit(20).all()
    
    timeline_events = []
    for activity in activities:
        timeline_events.append({
            'date': activity.created_at,
            'event': activity.action,
            'description': _format_activity_description(activity),
            'user': activity.user.full_name if activity.user else 'Sistema'
        })
    
    return timeline_events


def _get_project_task_metrics(project_id):
    """Obtener métricas de tareas del proyecto."""
    tasks = Task.query.filter_by(project_id=project_id).all()
    
    if not tasks:
        return {
            'total': 0,
            'completed': 0,
            'pending': 0,
            'in_progress': 0,
            'overdue': 0,
            'completion_rate': 0
        }
    
    total = len(tasks)
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
    in_progress = len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
    
    # Tareas vencidas
    today = datetime.now().date()
    overdue = len([
        t for t in tasks 
        if t.due_date and t.due_date < today and t.status != TaskStatus.COMPLETED
    ])
    
    completion_rate = (completed / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'in_progress': in_progress,
        'overdue': overdue,
        'completion_rate': round(completion_rate, 1)
    }


def _get_project_document_metrics(project_id):
    """Obtener métricas de documentos del proyecto."""
    documents = Document.query.filter_by(project_id=project_id).all()
    
    if not documents:
        return {
            'total': 0,
            'total_size': 0,
            'by_type': {},
            'recent_uploads': 0
        }
    
    total = len(documents)
    total_size = sum([d.file_size for d in documents])
    
    # Por tipo
    type_data = {}
    for doc_type in DocumentType:
        count = len([d for d in documents if d.document_type == doc_type])
        type_data[doc_type.value] = count
    
    # Uploads recientes (última semana)
    week_ago = datetime.now() - timedelta(weeks=1)
    recent_uploads = len([
        d for d in documents 
        if d.created_at >= week_ago
    ])
    
    return {
        'total': total,
        'total_size': total_size,
        'by_type': type_data,
        'recent_uploads': recent_uploads
    }


def _populate_form_choices(form):
    """Poblar opciones de formularios."""
    if hasattr(form, 'category'):
        form.category.choices = [(c.value, c.value.title()) for c in ProjectCategory]
    
    if hasattr(form, 'priority'):
        form.priority.choices = [(p.value, p.value.title()) for p in ProjectPriority]
    
    if hasattr(form, 'status'):
        form.status.choices = [(s.value, s.value.title()) for s in ProjectStatus]


def _populate_edit_form(form, project):
    """Poblar formulario de edición con datos del proyecto."""
    if hasattr(form, 'tags') and project.tags:
        form.tags.data = ', '.join(project.tags)


def _create_initial_tasks(project, tasks_text):
    """Crear tareas iniciales del proyecto."""
    if not tasks_text:
        return
    
    task_lines = tasks_text.strip().split('\n')
    for line in task_lines:
        line = line.strip()
        if line:
            Task.create(
                title=sanitize_input(line),
                project_id=project.id,
                entrepreneur_id=g.entrepreneur.id,
                status=TaskStatus.PENDING,
                priority=TaskPriority.MEDIUM
            )


def _detect_project_changes(original_data, updated_data):
    """Detectar cambios en los datos del proyecto."""
    changes = {}
    
    for key, new_value in updated_data.items():
        if key in original_data:
            old_value = original_data[key]
            if old_value != new_value:
                changes[key] = {
                    'old': str(old_value) if old_value else None,
                    'new': str(new_value) if new_value else None
                }
    
    return changes


def _can_edit_project(project):
    """Verificar si el usuario puede editar el proyecto."""
    # Solo el dueño puede editar
    return project.entrepreneur_id == g.entrepreneur.id


def _can_delete_project(project):
    """Verificar si el usuario puede eliminar el proyecto."""
    # Solo el dueño puede eliminar y solo si no está completado
    return (
        project.entrepreneur_id == g.entrepreneur.id and 
        project.status != ProjectStatus.COMPLETED
    )


def _is_valid_status_transition(old_status, new_status):
    """Validar transición de estado."""
    # Definir transiciones válidas
    valid_transitions = {
        ProjectStatus.PLANNING: [ProjectStatus.ACTIVE, ProjectStatus.CANCELLED],
        ProjectStatus.ACTIVE: [ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED],
        ProjectStatus.PAUSED: [ProjectStatus.ACTIVE, ProjectStatus.CANCELLED],
        ProjectStatus.COMPLETED: [],  # No se puede cambiar desde completado
        ProjectStatus.CANCELLED: []   # No se puede cambiar desde cancelado
    }
    
    return new_status in valid_transitions.get(old_status, [])


def _send_project_status_notifications(project, old_status, new_status):
    """Enviar notificaciones por cambio de estado."""
    if g.entrepreneur.assigned_ally:
        message = f'El proyecto "{project.name}" cambió de estado de {old_status.value} a {new_status.value}'
        
        NotificationService.send_notification(
            user_id=g.entrepreneur.assigned_ally.user_id,
            title='Cambio de estado de proyecto',
            message=message,
            notification_type='project_status_changed',
            related_id=project.id
        )


def _get_status_label(status):
    """Obtener etiqueta amigable del estado."""
    labels = {
        ProjectStatus.PLANNING: 'Planificación',
        ProjectStatus.ACTIVE: 'Activo',
        ProjectStatus.PAUSED: 'Pausado',
        ProjectStatus.COMPLETED: 'Completado',
        ProjectStatus.CANCELLED: 'Cancelado'
    }
    return labels.get(status, status.value)


def _is_allowed_file(filename):
    """Verificar si el archivo está permitido."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS


def _format_activity_description(activity):
    """Formatear descripción de actividad para timeline."""
    action_descriptions = {
        'project_created': 'Proyecto creado',
        'project_updated': 'Proyecto actualizado',
        'project_status_changed': 'Estado del proyecto cambiado',
        'task_created': 'Nueva tarea creada',
        'task_completed': 'Tarea completada',
        'document_uploaded': 'Documento subido'
    }
    
    base_description = action_descriptions.get(activity.action, activity.action)
    
    if activity.details:
        if 'project_name' in activity.details:
            return f"{base_description}: {activity.details['project_name']}"
        elif 'task_title' in activity.details:
            return f"{base_description}: {activity.details['task_title']}"
        elif 'filename' in activity.details:
            return f"{base_description}: {activity.details['filename']}"
    
    return base_description


# === MANEJADORES DE ERRORES ===

@entrepreneur_projects.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_projects.index'))


@entrepreneur_projects.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_projects.index'))


@entrepreneur_projects.errorhandler(ResourceNotFoundError)
def handle_not_found_error(error):
    """Manejar errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 404
    else:
        flash(str(error), 'error')
        return redirect(url_for('entrepreneur_projects.index'))


# === CONTEXT PROCESSORS ===

@entrepreneur_projects.context_processor
def inject_project_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_relative_time': format_relative_time,
        'format_currency': format_currency,
        'format_percentage': format_percentage,
        'format_file_size': format_file_size,
        'truncate_text': truncate_text,
        'ProjectStatus': ProjectStatus,
        'ProjectPriority': ProjectPriority,
        'ProjectCategory': ProjectCategory,
        'TaskStatus': TaskStatus,
        'TaskPriority': TaskPriority,
        'DocumentType': DocumentType
    }