"""
Gestión de Emprendedores - Panel Administrativo
===============================================

Este módulo gestiona todas las funcionalidades relacionadas con emprendedores
desde el panel administrativo, incluyendo evaluación, mentorías, proyectos y progreso.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, case, cast, Float
from sqlalchemy.orm import joinedload, selectinload, contains_eager
from werkzeug.utils import secure_filename

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required
from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.constants import (
    USER_ROLES, PROJECT_STATUS, BUSINESS_STAGES, INDUSTRIES, 
    MENTORSHIP_STATUS, EVALUATION_CRITERIA, PRIORITY_LEVELS
)

# Importaciones de modelos
from app.models import (
    User, Entrepreneur, Ally, Project, Program, Organization,
    Mentorship, Meeting, Document, Task, ActivityLog, Analytics,
    Notification
)

# Importaciones de servicios
from app.services.entrepreneur_service import EntrepreneurService
from app.services.mentorship_service import MentorshipService
from app.services.project_service import ProjectService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService

# Importaciones de formularios
from app.forms.admin import (
    EntrepreneurFilterForm, AssignMentorForm, EvaluateEntrepreneurForm,
    BulkEntrepreneurActionForm, EntrepreneurProfileForm, CreateProjectForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range, format_date_range
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.file_utils import allowed_file, get_file_extension

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_entrepreneurs = Blueprint('admin_entrepreneurs', __name__, url_prefix='/admin/entrepreneurs')

# ============================================================================
# VISTAS PRINCIPALES - LISTADO Y GESTIÓN
# ============================================================================

@admin_entrepreneurs.route('/')
@admin_entrepreneurs.route('/list')
@login_required
@admin_required
@handle_exceptions
def list_entrepreneurs():
    """
    Lista todos los emprendedores con filtros avanzados, métricas y acciones.
    Incluye información de proyectos, mentorías y progreso.
    """
    try:
        # Parámetros de consulta
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        stage_filter = request.args.get('stage', 'all')
        industry_filter = request.args.get('industry', 'all')
        program_filter = request.args.get('program', 'all')
        mentor_status = request.args.get('mentor_status', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Query base con optimizaciones
        query = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.program),
            selectinload(Entrepreneur.projects),
            selectinload(Entrepreneur.mentorships)
        ).join(User)
        
        # Aplicar filtros de búsqueda
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                Entrepreneur.business_name.ilike(f'%{search}%'),
                Entrepreneur.business_description.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtros específicos
        if stage_filter != 'all':
            query = query.filter(Entrepreneur.business_stage == stage_filter)
            
        if industry_filter != 'all':
            query = query.filter(Entrepreneur.industry == industry_filter)
            
        if program_filter != 'all':
            query = query.filter(Entrepreneur.program_id == int(program_filter))
            
        if mentor_status == 'assigned':
            query = query.filter(Entrepreneur.assigned_mentor_id.isnot(None))
        elif mentor_status == 'unassigned':
            query = query.filter(Entrepreneur.assigned_mentor_id.is_(None))
        elif mentor_status == 'active_mentorship':
            query = query.join(Mentorship).filter(
                Mentorship.status == 'active'
            )
        
        # Filtros de fecha
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(User.created_at >= from_date)
            except ValueError:
                flash('Fecha de inicio inválida.', 'warning')
                
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(User.created_at <= to_date)
            except ValueError:
                flash('Fecha de fin inválida.', 'warning')
        
        # Solo usuarios activos por defecto
        query = query.filter(User.is_active == True)
        
        # Aplicar ordenamiento
        if sort_by == 'name':
            order_field = User.first_name
        elif sort_by == 'business_name':
            order_field = Entrepreneur.business_name
        elif sort_by == 'stage':
            order_field = Entrepreneur.business_stage
        elif sort_by == 'score':
            order_field = Entrepreneur.evaluation_score
        elif sort_by == 'last_activity':
            order_field = Entrepreneur.last_activity_at
        else:  # created_at por defecto
            order_field = User.created_at
            
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
        
        # Paginación
        entrepreneurs = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
            max_per_page=50
        )
        
        # Estadísticas para el dashboard
        stats = _get_entrepreneur_statistics()
        
        # Programas disponibles para filtros
        programs = Program.query.filter_by(is_active=True).all()
        
        # Formularios
        filter_form = EntrepreneurFilterForm(request.args)
        bulk_action_form = BulkEntrepreneurActionForm()
        
        return render_template(
            'admin/entrepreneurs/list.html',
            entrepreneurs=entrepreneurs,
            stats=stats,
            programs=programs,
            filter_form=filter_form,
            bulk_action_form=bulk_action_form,
            current_filters={
                'search': search,
                'stage': stage_filter,
                'industry': industry_filter,
                'program': program_filter,
                'mentor_status': mentor_status,
                'sort': sort_by,
                'order': sort_order
            },
            business_stages=BUSINESS_STAGES,
            industries=INDUSTRIES
        )
        
    except Exception as e:
        current_app.logger.error(f"Error listando emprendedores: {str(e)}")
        flash('Error al cargar la lista de emprendedores.', 'error')
        return redirect(url_for('admin_dashboard.index'))

@admin_entrepreneurs.route('/<int:entrepreneur_id>')
@login_required
@admin_required
@handle_exceptions
def view_entrepreneur(entrepreneur_id):
    """
    Vista detallada de un emprendedor específico.
    Incluye proyectos, mentorías, evaluaciones, documentos y métricas.
    """
    try:
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.program),
            joinedload(Entrepreneur.assigned_mentor),
            joinedload(Entrepreneur.assigned_mentor).joinedload(Ally.user),
            selectinload(Entrepreneur.projects),
            selectinload(Entrepreneur.mentorships),
            selectinload(Entrepreneur.documents)
        ).get_or_404(entrepreneur_id)
        
        # Verificar acceso
        if not entrepreneur.user.is_active:
            flash('Este emprendedor está inactivo.', 'warning')
        
        # Métricas del emprendedor
        metrics = _get_entrepreneur_detailed_metrics(entrepreneur)
        
        # Proyectos con estadísticas
        projects_data = _get_entrepreneur_projects_data(entrepreneur)
        
        # Historial de mentorías
        mentorship_history = _get_mentorship_history(entrepreneur)
        
        # Actividad reciente
        recent_activities = ActivityLog.query.filter_by(
            user_id=entrepreneur.user_id
        ).options(joinedload(ActivityLog.user)).order_by(
            desc(ActivityLog.created_at)
        ).limit(15).all()
        
        # Documentos categorizados
        documents_by_category = _categorize_documents(entrepreneur.documents)
        
        # Evaluaciones históricas
        evaluations = _get_evaluation_history(entrepreneur)
        
        # Reuniones programadas y pasadas
        meetings_data = _get_entrepreneur_meetings_data(entrepreneur)
        
        # Tareas pendientes
        pending_tasks = Task.query.filter(
            and_(
                Task.assigned_to == entrepreneur.user_id,
                Task.status.in_(['pending', 'in_progress'])
            )
        ).order_by(Task.due_date.asc()).limit(10).all()
        
        # Recomendaciones del sistema
        recommendations = _generate_entrepreneur_recommendations(entrepreneur)
        
        return render_template(
            'admin/entrepreneurs/view.html',
            entrepreneur=entrepreneur,
            metrics=metrics,
            projects_data=projects_data,
            mentorship_history=mentorship_history,
            recent_activities=recent_activities,
            documents_by_category=documents_by_category,
            evaluations=evaluations,
            meetings_data=meetings_data,
            pending_tasks=pending_tasks,
            recommendations=recommendations
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viendo emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar los datos del emprendedor.', 'error')
        return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))

@admin_entrepreneurs.route('/<int:entrepreneur_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('edit_entrepreneur')
@handle_exceptions
def edit_entrepreneur(entrepreneur_id):
    """
    Edita el perfil de un emprendedor.
    Permite modificar información de negocio, etapa, industria y configuraciones.
    """
    entrepreneur = Entrepreneur.query.options(
        joinedload(Entrepreneur.user),
        joinedload(Entrepreneur.program)
    ).get_or_404(entrepreneur_id)
    
    form = EntrepreneurProfileForm(obj=entrepreneur)
    
    # Poblar choices dinámicos
    form.program_id.choices = [
        (p.id, p.name) for p in Program.query.filter_by(is_active=True).all()
    ]
    
    if form.validate_on_submit():
        try:
            # Almacenar valores anteriores para auditoría
            old_values = {
                'business_name': entrepreneur.business_name,
                'business_stage': entrepreneur.business_stage,
                'industry': entrepreneur.industry,
                'program_id': entrepreneur.program_id,
                'target_market': entrepreneur.target_market,
                'revenue_model': entrepreneur.revenue_model
            }
            
            # Actualizar información del emprendedor
            entrepreneur.business_name = form.business_name.data.strip()
            entrepreneur.business_description = form.business_description.data.strip()
            entrepreneur.business_stage = form.business_stage.data
            entrepreneur.industry = form.industry.data
            entrepreneur.target_market = form.target_market.data.strip() if form.target_market.data else None
            entrepreneur.revenue_model = form.revenue_model.data.strip() if form.revenue_model.data else None
            entrepreneur.founding_date = form.founding_date.data
            entrepreneur.team_size = form.team_size.data
            entrepreneur.funding_raised = form.funding_raised.data
            entrepreneur.funding_goal = form.funding_goal.data
            entrepreneur.website = form.website.data.strip() if form.website.data else None
            entrepreneur.linkedin_profile = form.linkedin_profile.data.strip() if form.linkedin_profile.data else None
            entrepreneur.updated_at = datetime.utcnow()
            
            # Cambio de programa si es necesario
            if form.program_id.data != entrepreneur.program_id:
                old_program = entrepreneur.program.name if entrepreneur.program else 'Ninguno'
                entrepreneur.program_id = form.program_id.data if form.program_id.data else None
                new_program = entrepreneur.program.name if entrepreneur.program else 'Ninguno'
                
                # Notificar cambio de programa
                notification_service = NotificationService()
                notification_service.send_notification(
                    user_id=entrepreneur.user_id,
                    type='program_change',
                    title='Cambio de Programa',
                    message=f'Tu programa ha cambiado de "{old_program}" a "{new_program}"',
                    priority='medium'
                )
            
            db.session.commit()
            
            # Registrar cambios en auditoría
            changes = []
            for field, old_value in old_values.items():
                new_value = getattr(entrepreneur, field)
                if old_value != new_value:
                    changes.append(f'{field}: {old_value} → {new_value}')
            
            if changes:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_entrepreneur_profile',
                    resource_type='Entrepreneur',
                    resource_id=entrepreneur.id,
                    details=f'Perfil actualizado: {", ".join(changes)}'
                )
                db.session.add(activity)
                db.session.commit()
            
            flash(f'Perfil de {entrepreneur.business_name} actualizado exitosamente.', 'success')
            return redirect(url_for('admin_entrepreneurs.view_entrepreneur', entrepreneur_id=entrepreneur.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando emprendedor {entrepreneur_id}: {str(e)}")
            flash('Error al actualizar el perfil del emprendedor.', 'error')
    
    return render_template('admin/entrepreneurs/edit.html', form=form, entrepreneur=entrepreneur)

# ============================================================================
# GESTIÓN DE MENTORÍAS
# ============================================================================

@admin_entrepreneurs.route('/<int:entrepreneur_id>/assign-mentor', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('assign_mentor')
@handle_exceptions
def assign_mentor(entrepreneur_id):
    """
    Asigna un mentor a un emprendedor.
    Considera experiencia, disponibilidad y compatibilidad.
    """
    entrepreneur = Entrepreneur.query.options(
        joinedload(Entrepreneur.user)
    ).get_or_404(entrepreneur_id)
    
    form = AssignMentorForm()
    
    # Obtener mentores disponibles con criterios inteligentes
    available_mentors = _get_available_mentors(entrepreneur)
    form.mentor_id.choices = [
        (mentor.id, f"{mentor.user.full_name} - {mentor.expertise_areas_display}")
        for mentor in available_mentors
    ]
    
    if form.validate_on_submit():
        try:
            mentor = Ally.query.get(form.mentor_id.data)
            if not mentor:
                flash('Mentor seleccionado no válido.', 'error')
                return render_template('admin/entrepreneurs/assign_mentor.html', 
                                     form=form, entrepreneur=entrepreneur)
            
            # Verificar disponibilidad del mentor
            if not _check_mentor_availability(mentor):
                flash('El mentor seleccionado no tiene disponibilidad actualmente.', 'warning')
                return render_template('admin/entrepreneurs/assign_mentor.html', 
                                     form=form, entrepreneur=entrepreneur)
            
            mentorship_service = MentorshipService()
            
            # Crear sesión de mentoría
            mentorship = mentorship_service.create_mentorship(
                entrepreneur_id=entrepreneur.id,
                mentor_id=mentor.id,
                program_id=entrepreneur.program_id,
                objectives=form.objectives.data.strip() if form.objectives.data else None,
                expected_duration=form.expected_duration.data,
                notes=f'Asignado por admin: {current_user.full_name}'
            )
            
            # Actualizar asignación en el perfil del emprendedor
            entrepreneur.assigned_mentor_id = mentor.id
            entrepreneur.mentor_assigned_at = datetime.utcnow()
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='assign_mentor',
                resource_type='Mentorship',
                resource_id=mentorship.id,
                details=f'Mentor {mentor.user.full_name} asignado a {entrepreneur.business_name}'
            )
            db.session.add(activity)
            
            # Notificar a ambas partes
            notification_service = NotificationService()
            
            # Notificar al emprendedor
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='mentor_assigned',
                title='Mentor Asignado',
                message=f'Se te ha asignado como mentor a {mentor.user.full_name}',
                priority='medium'
            )
            
            # Notificar al mentor
            notification_service.send_notification(
                user_id=mentor.user_id,
                type='entrepreneur_assigned',
                title='Nuevo Emprendedor Asignado',
                message=f'Se te ha asignado como emprendedor a {entrepreneur.user.full_name}',
                priority='medium'
            )
            
            # Enviar emails de notificación
            try:
                email_service = EmailService()
                email_service.send_mentor_assignment_notification(entrepreneur, mentor)
            except Exception as e:
                current_app.logger.warning(f"Error enviando email de asignación: {str(e)}")
            
            db.session.commit()
            
            flash(f'Mentor {mentor.user.full_name} asignado exitosamente a {entrepreneur.business_name}.', 'success')
            return redirect(url_for('admin_entrepreneurs.view_entrepreneur', entrepreneur_id=entrepreneur.id))
            
        except BusinessLogicError as e:
            flash(f'Error de lógica de negocio: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error asignando mentor: {str(e)}")
            flash('Error al asignar el mentor.', 'error')
    
    return render_template('admin/entrepreneurs/assign_mentor.html', 
                         form=form, entrepreneur=entrepreneur, available_mentors=available_mentors)

@admin_entrepreneurs.route('/<int:entrepreneur_id>/mentorship-history')
@login_required
@admin_required
@handle_exceptions
def mentorship_history(entrepreneur_id):
    """
    Muestra el historial completo de mentorías de un emprendedor.
    Incluye sesiones, evaluaciones y progreso.
    """
    try:
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user)
        ).get_or_404(entrepreneur_id)
        
        # Obtener todas las mentorías
        mentorships = Mentorship.query.filter_by(
            entrepreneur_id=entrepreneur.id
        ).options(
            joinedload(Mentorship.mentor),
            joinedload(Mentorship.mentor).joinedload(Ally.user),
            selectinload(Mentorship.sessions)
        ).order_by(desc(Mentorship.created_at)).all()
        
        # Estadísticas de mentorías
        mentorship_stats = {
            'total_mentorships': len(mentorships),
            'active_mentorships': len([m for m in mentorships if m.status == 'active']),
            'completed_mentorships': len([m for m in mentorships if m.status == 'completed']),
            'total_sessions': sum([len(m.sessions) for m in mentorships]),
            'total_hours': sum([m.total_hours for m in mentorships if m.total_hours])
        }
        
        return render_template(
            'admin/entrepreneurs/mentorship_history.html',
            entrepreneur=entrepreneur,
            mentorships=mentorships,
            mentorship_stats=mentorship_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando historial de mentorías: {str(e)}")
        flash('Error al cargar el historial de mentorías.', 'error')
        return redirect(url_for('admin_entrepreneurs.view_entrepreneur', entrepreneur_id=entrepreneur_id))

# ============================================================================
# EVALUACIÓN Y SCORING
# ============================================================================

@admin_entrepreneurs.route('/<int:entrepreneur_id>/evaluate', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('evaluate_entrepreneur')
@handle_exceptions
def evaluate_entrepreneur(entrepreneur_id):
    """
    Evalúa a un emprendedor usando criterios predefinidos.
    Genera score automático y recomendaciones.
    """
    entrepreneur = Entrepreneur.query.options(
        joinedload(Entrepreneur.user)
    ).get_or_404(entrepreneur_id)
    
    form = EvaluateEntrepreneurForm()
    
    if form.validate_on_submit():
        try:
            entrepreneur_service = EntrepreneurService()
            
            # Preparar datos de evaluación
            evaluation_data = {
                'business_viability': form.business_viability.data,
                'market_potential': form.market_potential.data,
                'team_quality': form.team_quality.data,
                'execution_ability': form.execution_ability.data,
                'innovation_level': form.innovation_level.data,
                'scalability': form.scalability.data,
                'financial_health': form.financial_health.data,
                'social_impact': form.social_impact.data,
                'notes': form.notes.data.strip() if form.notes.data else None,
                'recommendations': form.recommendations.data.strip() if form.recommendations.data else None,
                'evaluator_id': current_user.id
            }
            
            # Calcular score automático
            total_score = entrepreneur_service.calculate_evaluation_score(evaluation_data)
            
            # Actualizar emprendedor
            entrepreneur.evaluation_score = total_score
            entrepreneur.last_evaluation_at = datetime.utcnow()
            entrepreneur.evaluation_data = evaluation_data  # JSON field
            
            # Determinar nivel de riesgo
            if total_score >= 80:
                risk_level = 'low'
                priority = 'high'
            elif total_score >= 60:
                risk_level = 'medium'
                priority = 'medium'
            else:
                risk_level = 'high'
                priority = 'low'
            
            entrepreneur.risk_level = risk_level
            entrepreneur.priority_level = priority
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='evaluate_entrepreneur',
                resource_type='Entrepreneur',
                resource_id=entrepreneur.id,
                details=f'Evaluación completada. Score: {total_score}/100, Riesgo: {risk_level}'
            )
            db.session.add(activity)
            
            # Generar recomendaciones automáticas
            auto_recommendations = entrepreneur_service.generate_recommendations(entrepreneur)
            
            # Notificar al emprendedor si el score es bajo
            if total_score < 50:
                notification_service = NotificationService()
                notification_service.send_notification(
                    user_id=entrepreneur.user_id,
                    type='low_evaluation_score',
                    title='Evaluación Requerida',
                    message='Tu evaluación indica áreas de mejora. Revisa las recomendaciones.',
                    priority='high'
                )
            
            db.session.commit()
            
            flash(f'Evaluación completada. Score: {total_score}/100 ({risk_level} risk)', 'success')
            return redirect(url_for('admin_entrepreneurs.view_entrepreneur', entrepreneur_id=entrepreneur.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error evaluando emprendedor: {str(e)}")
            flash('Error al guardar la evaluación.', 'error')
    
    return render_template('admin/entrepreneurs/evaluate.html', 
                         form=form, entrepreneur=entrepreneur, 
                         evaluation_criteria=EVALUATION_CRITERIA)

# ============================================================================
# GESTIÓN DE PROYECTOS
# ============================================================================

@admin_entrepreneurs.route('/<int:entrepreneur_id>/projects')
@login_required
@admin_required
@handle_exceptions
def projects(entrepreneur_id):
    """
    Muestra todos los proyectos de un emprendedor con gestión avanzada.
    """
    try:
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user)
        ).get_or_404(entrepreneur_id)
        
        # Obtener proyectos con estadísticas
        projects = Project.query.filter_by(
            entrepreneur_id=entrepreneur.id
        ).options(
            selectinload(Project.tasks),
            selectinload(Project.documents),
            selectinload(Project.milestones)
        ).order_by(desc(Project.updated_at)).all()
        
        # Estadísticas de proyectos
        project_stats = {
            'total': len(projects),
            'active': len([p for p in projects if p.status == 'active']),
            'completed': len([p for p in projects if p.status == 'completed']),
            'on_hold': len([p for p in projects if p.status == 'on_hold']),
            'avg_progress': sum([p.progress for p in projects]) / len(projects) if projects else 0
        }
        
        return render_template(
            'admin/entrepreneurs/projects.html',
            entrepreneur=entrepreneur,
            projects=projects,
            project_stats=project_stats,
            project_status=PROJECT_STATUS
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando proyectos: {str(e)}")
        flash('Error al cargar los proyectos.', 'error')
        return redirect(url_for('admin_entrepreneurs.view_entrepreneur', entrepreneur_id=entrepreneur_id))

@admin_entrepreneurs.route('/<int:entrepreneur_id>/create-project', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_project')
@handle_exceptions
def create_project(entrepreneur_id):
    """
    Crea un nuevo proyecto para un emprendedor.
    """
    entrepreneur = Entrepreneur.query.options(
        joinedload(Entrepreneur.user)
    ).get_or_404(entrepreneur_id)
    
    form = CreateProjectForm()
    
    if form.validate_on_submit():
        try:
            project_service = ProjectService()
            
            project_data = {
                'name': form.name.data.strip(),
                'description': form.description.data.strip(),
                'category': form.category.data,
                'status': form.status.data,
                'priority': form.priority.data,
                'start_date': form.start_date.data,
                'target_date': form.target_date.data,
                'budget': form.budget.data,
                'goals': form.goals.data.strip() if form.goals.data else None,
                'success_metrics': form.success_metrics.data.strip() if form.success_metrics.data else None,
                'entrepreneur_id': entrepreneur.id,
                'created_by_admin': True
            }
            
            project = project_service.create_project(project_data)
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_project',
                resource_type='Project',
                resource_id=project.id,
                details=f'Proyecto "{project.name}" creado para {entrepreneur.business_name}'
            )
            db.session.add(activity)
            
            # Notificar al emprendedor
            notification_service = NotificationService()
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='new_project',
                title='Nuevo Proyecto Creado',
                message=f'Se ha creado el proyecto "{project.name}" para tu emprendimiento',
                priority='medium'
            )
            
            db.session.commit()
            
            flash(f'Proyecto "{project.name}" creado exitosamente.', 'success')
            return redirect(url_for('admin_entrepreneurs.projects', entrepreneur_id=entrepreneur.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando proyecto: {str(e)}")
            flash('Error al crear el proyecto.', 'error')
    
    return render_template('admin/entrepreneurs/create_project.html', 
                         form=form, entrepreneur=entrepreneur)

# ============================================================================
# ANALYTICS Y ESTADÍSTICAS
# ============================================================================

@admin_entrepreneurs.route('/analytics')
@login_required
@admin_required
@cache_result(timeout=300)
def analytics():
    """
    Dashboard de analytics para emprendedores.
    Métricas avanzadas, tendencias y comparativas.
    """
    try:
        analytics_service = AnalyticsService()
        
        # Métricas generales
        general_metrics = _get_comprehensive_entrepreneur_metrics()
        
        # Datos para gráficos
        charts_data = {
            'entrepreneurs_by_stage': analytics_service.get_entrepreneurs_by_stage(),
            'entrepreneurs_by_industry': analytics_service.get_entrepreneurs_by_industry(),
            'success_rate_by_program': analytics_service.get_success_rate_by_program(),
            'mentorship_effectiveness': analytics_service.get_mentorship_effectiveness(),
            'project_completion_trends': analytics_service.get_project_completion_trends(days=90),
            'funding_distribution': analytics_service.get_funding_distribution(),
            'geographic_distribution': analytics_service.get_entrepreneurs_geographic_data()
        }
        
        # Top performers
        top_performers = _get_top_performing_entrepreneurs(limit=10)
        
        # Emprendedores que necesitan atención
        needs_attention = _get_entrepreneurs_needing_attention(limit=10)
        
        # Tendencias de crecimiento
        growth_trends = analytics_service.get_entrepreneur_growth_trends(days=365)
        
        return render_template(
            'admin/entrepreneurs/analytics.html',
            general_metrics=general_metrics,
            charts_data=charts_data,
            top_performers=top_performers,
            needs_attention=needs_attention,
            growth_trends=growth_trends
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando analytics: {str(e)}")
        flash('Error al cargar los analytics.', 'error')
        return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))

# ============================================================================
# ACCIONES EN LOTE
# ============================================================================

@admin_entrepreneurs.route('/bulk-actions', methods=['POST'])
@login_required
@admin_required
@permission_required('bulk_entrepreneur_actions')
@handle_exceptions
def bulk_actions():
    """
    Ejecuta acciones en lote sobre múltiples emprendedores.
    """
    form = BulkEntrepreneurActionForm()
    
    if form.validate_on_submit():
        try:
            entrepreneur_ids = [int(id) for id in form.entrepreneur_ids.data.split(',') if id.strip()]
            action = form.action.data
            
            if not entrepreneur_ids:
                flash('No se seleccionaron emprendedores.', 'warning')
                return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))
            
            entrepreneurs = Entrepreneur.query.filter(
                Entrepreneur.id.in_(entrepreneur_ids)
            ).options(joinedload(Entrepreneur.user)).all()
            
            success_count = 0
            entrepreneur_service = EntrepreneurService()
            
            for entrepreneur in entrepreneurs:
                try:
                    if action == 'change_stage':
                        entrepreneur.business_stage = form.new_stage.data
                        success_count += 1
                        
                    elif action == 'assign_program':
                        entrepreneur.program_id = form.program_id.data
                        success_count += 1
                        
                    elif action == 'mark_priority':
                        entrepreneur.priority_level = form.priority_level.data
                        success_count += 1
                        
                    elif action == 'bulk_evaluate':
                        # Evaluación básica automática
                        entrepreneur_service.auto_evaluate(entrepreneur)
                        success_count += 1
                        
                    elif action == 'send_notification':
                        notification_service = NotificationService()
                        notification_service.send_notification(
                            user_id=entrepreneur.user_id,
                            type='admin_message',
                            title=form.notification_title.data,
                            message=form.notification_message.data,
                            priority='medium'
                        )
                        success_count += 1
                        
                except Exception as e:
                    current_app.logger.warning(f"Error procesando emprendedor {entrepreneur.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='bulk_entrepreneur_action',
                resource_type='Entrepreneur',
                details=f'Acción en lote: {action} aplicada a {success_count} emprendedores'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Acción aplicada exitosamente a {success_count} emprendedor(es).', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error en acción en lote: {str(e)}")
            flash('Error al ejecutar la acción en lote.', 'error')
    else:
        flash('Datos de formulario inválidos.', 'error')
    
    return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))

# ============================================================================
# EXPORTACIÓN E IMPORTACIÓN
# ============================================================================

@admin_entrepreneurs.route('/export')
@login_required
@admin_required
@permission_required('export_entrepreneurs')
@handle_exceptions
def export_entrepreneurs():
    """
    Exporta datos de emprendedores en diferentes formatos.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_projects = request.args.get('include_projects', 'false') == 'true'
        include_mentorships = request.args.get('include_mentorships', 'false') == 'true'
        stage_filter = request.args.get('stage', 'all')
        
        # Construir query
        query = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.program),
            joinedload(Entrepreneur.assigned_mentor),
            joinedload(Entrepreneur.assigned_mentor).joinedload(Ally.user)
        ).join(User).filter(User.is_active == True)
        
        if stage_filter != 'all':
            query = query.filter(Entrepreneur.business_stage == stage_filter)
        
        entrepreneurs = query.order_by(Entrepreneur.created_at.desc()).all()
        
        # Preparar datos de exportación
        export_data = []
        for entrepreneur in entrepreneurs:
            row = {
                'ID': entrepreneur.id,
                'Nombre del Fundador': entrepreneur.user.full_name,
                'Email': entrepreneur.user.email,
                'Nombre del Negocio': entrepreneur.business_name or 'N/A',
                'Descripción': entrepreneur.business_description or 'N/A',
                'Etapa': entrepreneur.business_stage or 'N/A',
                'Industria': entrepreneur.industry or 'N/A',
                'Mercado Objetivo': entrepreneur.target_market or 'N/A',
                'Modelo de Ingresos': entrepreneur.revenue_model or 'N/A',
                'Programa': entrepreneur.program.name if entrepreneur.program else 'N/A',
                'Mentor Asignado': entrepreneur.assigned_mentor.user.full_name if entrepreneur.assigned_mentor else 'N/A',
                'Score de Evaluación': entrepreneur.evaluation_score or 'N/A',
                'Nivel de Riesgo': entrepreneur.risk_level or 'N/A',
                'Prioridad': entrepreneur.priority_level or 'N/A',
                'Tamaño del Equipo': entrepreneur.team_size or 'N/A',
                'Fondos Recaudados': f"${entrepreneur.funding_raised:,.2f}" if entrepreneur.funding_raised else 'N/A',
                'Meta de Fondos': f"${entrepreneur.funding_goal:,.2f}" if entrepreneur.funding_goal else 'N/A',
                'Website': entrepreneur.website or 'N/A',
                'LinkedIn': entrepreneur.linkedin_profile or 'N/A',
                'Fecha de Fundación': entrepreneur.founding_date.strftime('%Y-%m-%d') if entrepreneur.founding_date else 'N/A',
                'Fecha de Registro': entrepreneur.user.created_at.strftime('%Y-%m-%d'),
                'Última Actividad': entrepreneur.last_activity_at.strftime('%Y-%m-%d %H:%M') if entrepreneur.last_activity_at else 'N/A'
            }
            
            # Incluir datos de proyectos si se solicita
            if include_projects:
                active_projects = [p for p in entrepreneur.projects if p.status == 'active']
                row['Proyectos Activos'] = len(active_projects)
                row['Proyectos Completados'] = len([p for p in entrepreneur.projects if p.status == 'completed'])
                
            # Incluir datos de mentorías si se solicita
            if include_mentorships:
                active_mentorships = [m for m in entrepreneur.mentorships if m.status == 'active']
                row['Mentorías Activas'] = len(active_mentorships)
                row['Total Horas de Mentoría'] = sum([m.total_hours for m in entrepreneur.mentorships if m.total_hours])
            
            export_data.append(row)
        
        # Generar archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            filename = f'emprendedores_{timestamp}.xlsx'
            return export_to_excel(export_data, filename, 'Emprendedores')
        elif export_format == 'csv':
            filename = f'emprendedores_{timestamp}.csv'
            return export_to_csv(export_data, filename)
        elif export_format == 'pdf':
            filename = f'emprendedores_{timestamp}.pdf'
            return export_to_pdf(export_data, filename, 'Reporte de Emprendedores')
        
    except Exception as e:
        current_app.logger.error(f"Error exportando emprendedores: {str(e)}")
        flash('Error al exportar los datos.', 'error')
        return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_entrepreneurs.route('/api/search')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_search_entrepreneurs():
    """API para búsqueda de emprendedores en tiempo real."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        
        if len(query) < 2:
            return jsonify({'entrepreneurs': []})
        
        entrepreneurs = Entrepreneur.query.join(User).filter(
            and_(
                User.is_active == True,
                or_(
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%'),
                    Entrepreneur.business_name.ilike(f'%{query}%')
                )
            )
        ).options(joinedload(Entrepreneur.user)).limit(limit).all()
        
        return jsonify({
            'entrepreneurs': [
                {
                    'id': entrepreneur.id,
                    'name': entrepreneur.user.full_name,
                    'business_name': entrepreneur.business_name,
                    'email': entrepreneur.user.email,
                    'stage': entrepreneur.business_stage,
                    'industry': entrepreneur.industry,
                    'score': entrepreneur.evaluation_score
                }
                for entrepreneur in entrepreneurs
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_entrepreneurs.route('/api/<int:entrepreneur_id>/quick-stats')
@login_required
@admin_required
def api_entrepreneur_quick_stats(entrepreneur_id):
    """API para estadísticas rápidas de un emprendedor."""
    try:
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            selectinload(Entrepreneur.projects),
            selectinload(Entrepreneur.mentorships)
        ).get_or_404(entrepreneur_id)
        
        stats = {
            'projects_count': len(entrepreneur.projects),
            'active_projects': len([p for p in entrepreneur.projects if p.status == 'active']),
            'mentorships_count': len(entrepreneur.mentorships),
            'evaluation_score': entrepreneur.evaluation_score,
            'last_activity': entrepreneur.last_activity_at.isoformat() if entrepreneur.last_activity_at else None,
            'risk_level': entrepreneur.risk_level,
            'priority_level': entrepreneur.priority_level
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_entrepreneur_statistics():
    """Obtiene estadísticas básicas de emprendedores."""
    total_entrepreneurs = Entrepreneur.query.join(User).filter(User.is_active == True).count()
    
    return {
        'total': total_entrepreneurs,
        'by_stage': {
            stage: Entrepreneur.query.join(User).filter(
                and_(User.is_active == True, Entrepreneur.business_stage == stage)
            ).count()
            for stage in BUSINESS_STAGES
        },
        'with_mentor': Entrepreneur.query.join(User).filter(
            and_(User.is_active == True, Entrepreneur.assigned_mentor_id.isnot(None))
        ).count(),
        'without_mentor': Entrepreneur.query.join(User).filter(
            and_(User.is_active == True, Entrepreneur.assigned_mentor_id.is_(None))
        ).count(),
        'high_score': Entrepreneur.query.join(User).filter(
            and_(User.is_active == True, Entrepreneur.evaluation_score >= 80)
        ).count(),
        'needs_attention': Entrepreneur.query.join(User).filter(
            and_(User.is_active == True, Entrepreneur.evaluation_score < 50)
        ).count(),
        'this_month': Entrepreneur.query.join(User).filter(
            and_(
                User.is_active == True,
                User.created_at >= datetime.utcnow().replace(day=1)
            )
        ).count()
    }

def _get_entrepreneur_detailed_metrics(entrepreneur):
    """Obtiene métricas detalladas de un emprendedor específico."""
    metrics = {
        'account_age_days': (datetime.utcnow() - entrepreneur.user.created_at).days,
        'last_login_days_ago': (datetime.utcnow() - entrepreneur.user.last_login).days if entrepreneur.user.last_login else None,
        'projects_count': len(entrepreneur.projects),
        'active_projects': len([p for p in entrepreneur.projects if p.status == 'active']),
        'completed_projects': len([p for p in entrepreneur.projects if p.status == 'completed']),
        'avg_project_progress': sum([p.progress for p in entrepreneur.projects]) / len(entrepreneur.projects) if entrepreneur.projects else 0,
        'mentorships_count': len(entrepreneur.mentorships),
        'active_mentorships': len([m for m in entrepreneur.mentorships if m.status == 'active']),
        'total_mentorship_hours': sum([m.total_hours for m in entrepreneur.mentorships if m.total_hours]),
        'documents_uploaded': len(entrepreneur.documents),
        'evaluation_score': entrepreneur.evaluation_score or 0,
        'risk_level': entrepreneur.risk_level,
        'priority_level': entrepreneur.priority_level
    }
    
    # Calcular tendencia de progreso
    if entrepreneur.projects:
        recent_projects = [p for p in entrepreneur.projects if p.updated_at >= datetime.utcnow() - timedelta(days=30)]
        metrics['projects_updated_recently'] = len(recent_projects)
        metrics['avg_recent_progress'] = sum([p.progress for p in recent_projects]) / len(recent_projects) if recent_projects else 0
    
    return metrics

def _get_entrepreneur_projects_data(entrepreneur):
    """Obtiene datos estructurados de proyectos del emprendedor."""
    projects = entrepreneur.projects
    
    return {
        'total': len(projects),
        'by_status': {
            status: len([p for p in projects if p.status == status])
            for status in PROJECT_STATUS
        },
        'avg_progress': sum([p.progress for p in projects]) / len(projects) if projects else 0,
        'overdue': len([p for p in projects if p.target_date and p.target_date < datetime.utcnow().date() and p.status != 'completed']),
        'due_soon': len([p for p in projects if p.target_date and p.target_date <= datetime.utcnow().date() + timedelta(days=7) and p.status != 'completed'])
    }

def _get_mentorship_history(entrepreneur):
    """Obtiene historial de mentorías con detalles."""
    mentorships = Mentorship.query.filter_by(
        entrepreneur_id=entrepreneur.id
    ).options(
        joinedload(Mentorship.mentor),
        joinedload(Mentorship.mentor).joinedload(Ally.user)
    ).order_by(desc(Mentorship.created_at)).all()
    
    return mentorships

def _categorize_documents(documents):
    """Categoriza documentos por tipo."""
    categories = {
        'business_plan': [],
        'financial': [],
        'legal': [],
        'presentations': [],
        'other': []
    }
    
    for doc in documents:
        if 'business' in doc.name.lower() or 'plan' in doc.name.lower():
            categories['business_plan'].append(doc)
        elif 'financial' in doc.name.lower() or 'budget' in doc.name.lower():
            categories['financial'].append(doc)
        elif 'legal' in doc.name.lower() or 'contract' in doc.name.lower():
            categories['legal'].append(doc)
        elif 'presentation' in doc.name.lower() or 'pitch' in doc.name.lower():
            categories['presentations'].append(doc)
        else:
            categories['other'].append(doc)
    
    return categories

def _get_evaluation_history(entrepreneur):
    """Obtiene historial de evaluaciones."""
    # Esto debería venir de una tabla de evaluaciones si existe
    # Por ahora retornamos datos simulados basados en el modelo actual
    evaluations = []
    
    if entrepreneur.evaluation_data and entrepreneur.last_evaluation_at:
        evaluations.append({
            'date': entrepreneur.last_evaluation_at,
            'score': entrepreneur.evaluation_score,
            'evaluator': 'Sistema',  # Esto debería venir de evaluation_data
            'notes': entrepreneur.evaluation_data.get('notes', '') if isinstance(entrepreneur.evaluation_data, dict) else ''
        })
    
    return evaluations

def _get_entrepreneur_meetings_data(entrepreneur):
    """Obtiene datos de reuniones del emprendedor."""
    meetings = Meeting.query.filter(
        or_(
            Meeting.organizer_id == entrepreneur.user_id,
            Meeting.participants.any(User.id == entrepreneur.user_id)
        )
    ).order_by(desc(Meeting.scheduled_for)).limit(10).all()
    
    upcoming = [m for m in meetings if m.scheduled_for >= datetime.utcnow()]
    past = [m for m in meetings if m.scheduled_for < datetime.utcnow()]
    
    return {
        'upcoming': upcoming,
        'past': past,
        'total_this_month': len([m for m in meetings if m.scheduled_for >= datetime.utcnow().replace(day=1)])
    }

def _generate_entrepreneur_recommendations(entrepreneur):
    """Genera recomendaciones automáticas para el emprendedor."""
    recommendations = []
    
    # Recomendaciones basadas en score
    if entrepreneur.evaluation_score and entrepreneur.evaluation_score < 60:
        recommendations.append({
            'type': 'improvement',
            'priority': 'high',
            'title': 'Mejorar Evaluación',
            'description': 'El score de evaluación es bajo. Considera revisar las áreas de mejora.',
            'action': 'Programar sesión de mentoría'
        })
    
    # Recomendaciones basadas en actividad
    if entrepreneur.last_activity_at and entrepreneur.last_activity_at < datetime.utcnow() - timedelta(days=30):
        recommendations.append({
            'type': 'engagement',
            'priority': 'medium',
            'title': 'Incrementar Actividad',
            'description': 'No ha habido actividad reciente en la plataforma.',
            'action': 'Contactar al emprendedor'
        })
    
    # Recomendaciones basadas en proyectos
    if not entrepreneur.projects:
        recommendations.append({
            'type': 'project',
            'priority': 'medium',
            'title': 'Crear Primer Proyecto',
            'description': 'No tiene proyectos registrados aún.',
            'action': 'Ayudar a crear proyecto inicial'
        })
    
    # Recomendaciones basadas en mentoría
    if not entrepreneur.assigned_mentor_id:
        recommendations.append({
            'type': 'mentorship',
            'priority': 'high',
            'title': 'Asignar Mentor',
            'description': 'No tiene mentor asignado.',
            'action': 'Buscar mentor compatible'
        })
    
    return recommendations

def _get_available_mentors(entrepreneur):
    """Obtiene mentores disponibles para un emprendedor específico."""
    # Mentores activos con disponibilidad
    mentors = Ally.query.join(User).filter(
        and_(
            User.is_active == True,
            Ally.is_available == True,
            Ally.max_entrepreneurs > func.coalesce(Ally.current_entrepreneurs, 0)
        )
    ).options(joinedload(Ally.user)).all()
    
    # Filtrar por expertise compatible si hay industria definida
    if entrepreneur.industry:
        compatible_mentors = []
        for mentor in mentors:
            if (mentor.expertise_areas and 
                any(area.lower() in entrepreneur.industry.lower() for area in mentor.expertise_areas)):
                compatible_mentors.append(mentor)
        
        # Si hay mentores compatibles, usarlos; sino, usar todos
        if compatible_mentors:
            mentors = compatible_mentors
    
    return mentors

def _check_mentor_availability(mentor):
    """Verifica la disponibilidad actual de un mentor."""
    current_entrepreneurs = Entrepreneur.query.filter_by(
        assigned_mentor_id=mentor.id
    ).join(User).filter(User.is_active == True).count()
    
    return current_entrepreneurs < (mentor.max_entrepreneurs or 5)

def _get_comprehensive_entrepreneur_metrics():
    """Obtiene métricas comprehensivas para analytics."""
    total = Entrepreneur.query.join(User).filter(User.is_active == True).count()
    
    return {
        'total_entrepreneurs': total,
        'avg_evaluation_score': db.session.query(
            func.avg(Entrepreneur.evaluation_score)
        ).filter(Entrepreneur.evaluation_score.isnot(None)).scalar() or 0,
        'success_rate': _calculate_success_rate(),
        'mentorship_coverage': _calculate_mentorship_coverage(),
        'project_completion_rate': _calculate_project_completion_rate(),
        'funding_success_rate': _calculate_funding_success_rate()
    }

def _calculate_success_rate():
    """Calcula tasa de éxito basada en proyectos completados y scores."""
    total = Entrepreneur.query.join(User).filter(User.is_active == True).count()
    if total == 0:
        return 0
    
    successful = Entrepreneur.query.join(User).filter(
        and_(
            User.is_active == True,
            or_(
                Entrepreneur.evaluation_score >= 80,
                Entrepreneur.projects.any(Project.status == 'completed')
            )
        )
    ).count()
    
    return (successful / total) * 100

def _calculate_mentorship_coverage():
    """Calcula cobertura de mentoría."""
    total = Entrepreneur.query.join(User).filter(User.is_active == True).count()
    if total == 0:
        return 0
    
    with_mentor = Entrepreneur.query.join(User).filter(
        and_(User.is_active == True, Entrepreneur.assigned_mentor_id.isnot(None))
    ).count()
    
    return (with_mentor / total) * 100

def _calculate_project_completion_rate():
    """Calcula tasa de finalización de proyectos."""
    total_projects = Project.query.count()
    if total_projects == 0:
        return 0
    
    completed_projects = Project.query.filter_by(status='completed').count()
    return (completed_projects / total_projects) * 100

def _calculate_funding_success_rate():
    """Calcula tasa de éxito en fondeo."""
    total_with_goal = Entrepreneur.query.filter(
        Entrepreneur.funding_goal.isnot(None)
    ).count()
    
    if total_with_goal == 0:
        return 0
    
    successful_funding = Entrepreneur.query.filter(
        and_(
            Entrepreneur.funding_goal.isnot(None),
            Entrepreneur.funding_raised >= Entrepreneur.funding_goal
        )
    ).count()
    
    return (successful_funding / total_with_goal) * 100

def _get_top_performing_entrepreneurs(limit=10):
    """Obtiene emprendedores con mejor desempeño."""
    return Entrepreneur.query.join(User).filter(
        User.is_active == True
    ).options(
        joinedload(Entrepreneur.user)
    ).order_by(
        desc(Entrepreneur.evaluation_score),
        desc(Entrepreneur.last_activity_at)
    ).limit(limit).all()

def _get_entrepreneurs_needing_attention(limit=10):
    """Obtiene emprendedores que necesitan atención."""
    return Entrepreneur.query.join(User).filter(
        and_(
            User.is_active == True,
            or_(
                Entrepreneur.evaluation_score < 50,
                Entrepreneur.last_activity_at < datetime.utcnow() - timedelta(days=30),
                Entrepreneur.assigned_mentor_id.is_(None)
            )
        )
    ).options(
        joinedload(Entrepreneur.user)
    ).order_by(
        Entrepreneur.evaluation_score.asc(),
        Entrepreneur.last_activity_at.asc()
    ).limit(limit).all()