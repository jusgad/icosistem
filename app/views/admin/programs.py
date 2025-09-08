"""
Gestión de Programas - Panel Administrativo
===========================================

Este módulo gestiona todas las funcionalidades relacionadas con programas
del ecosistema de emprendimiento: incubadoras, aceleradoras, bootcamps,
mentorías, y programas corporativos.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, case, cast, Float, text
from sqlalchemy.orm import joinedload, selectinload, contains_eager
from werkzeug.utils import secure_filename

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required
from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.constants import (
    PROGRAM_TYPES, PROGRAM_STATUS, PROGRAM_MODES, INDUSTRY_FOCUS,
    BUSINESS_STAGES, DURATION_TYPES, CURRENCY_TYPES, PRIORITY_LEVELS
)

# Importaciones de modelos
from app.models import (
    Program, Organization, Entrepreneur, User, Ally, Project,
    Cohort, Milestone, Resource, Document, ActivityLog, Analytics,
    Notification, Meeting
)

# Importaciones de servicios
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.curriculum_service import CurriculumService
from app.services.cohort_service import CohortService

# Importaciones de formularios
from app.forms.admin import (
    ProgramForm, ProgramFilterForm, CohortForm, MilestoneForm,
    BulkProgramActionForm, EvaluateProgramForm, ResourceForm,
    ProgramApplicationForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number, format_duration
from app.utils.date_utils import get_date_range, format_date_range, calculate_duration
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.validators import validate_program_dates, validate_budget, validate_capacity

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_programs = Blueprint('admin_programs', __name__, url_prefix='/admin/programs')

# ============================================================================
# VISTAS PRINCIPALES - LISTADO Y GESTIÓN
# ============================================================================

@admin_programs.route('/')
@admin_programs.route('/list')
@login_required
@admin_required
@handle_exceptions
def list_programs():
    """
    Lista todos los programas con filtros avanzados y métricas.
    Incluye información de cohortes, emprendedores, outcomes y performance.
    """
    try:
        # Parámetros de consulta
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        type_filter = request.args.get('type', 'all')
        status_filter = request.args.get('status', 'all')
        organization_filter = request.args.get('organization', 'all')
        mode_filter = request.args.get('mode', 'all')
        industry_filter = request.args.get('industry', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        
        # Query base con optimizaciones
        query = Program.query.options(
            joinedload(Program.organization),
            selectinload(Program.cohorts),
            selectinload(Program.entrepreneurs),
            selectinload(Program.milestones)
        )
        
        # Aplicar filtros de búsqueda
        if search:
            search_filter = or_(
                Program.name.ilike(f'%{search}%'),
                Program.description.ilike(f'%{search}%'),
                Program.objectives.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtros específicos
        if type_filter != 'all':
            query = query.filter(Program.type == type_filter)
            
        if status_filter != 'all':
            query = query.filter(Program.status == status_filter)
            
        if organization_filter != 'all':
            query = query.filter(Program.organization_id == int(organization_filter))
            
        if mode_filter != 'all':
            query = query.filter(Program.mode == mode_filter)
            
        if industry_filter != 'all':
            query = query.filter(Program.industry_focus.any(industry_filter))
        
        # Aplicar ordenamiento
        if sort_by == 'name':
            order_field = Program.name
        elif sort_by == 'organization':
            order_field = Organization.name
            query = query.join(Organization)
        elif sort_by == 'entrepreneurs_count':
            order_field = func.count(Entrepreneur.id)
            query = query.outerjoin(Program.entrepreneurs).group_by(Program.id)
        elif sort_by == 'graduation_rate':
            order_field = Program.graduation_rate
        elif sort_by == 'success_rate':
            order_field = Program.success_rate
        elif sort_by == 'start_date':
            order_field = Program.start_date
        elif sort_by == 'budget':
            order_field = Program.budget
        else:  # created_at por defecto
            order_field = Program.created_at
            
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc().nulls_last())
        
        # Paginación
        programs = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
            max_per_page=50
        )
        
        # Estadísticas para el dashboard
        stats = _get_program_statistics()
        
        # Organizaciones para filtros
        organizations = Organization.query.filter_by(status='active').order_by(Organization.name).all()
        
        # Formularios
        filter_form = ProgramFilterForm(request.args)
        bulk_action_form = BulkProgramActionForm()
        
        return render_template(
            'admin/programs/list.html',
            programs=programs,
            stats=stats,
            organizations=organizations,
            filter_form=filter_form,
            bulk_action_form=bulk_action_form,
            current_filters={
                'search': search,
                'type': type_filter,
                'status': status_filter,
                'organization': organization_filter,
                'mode': mode_filter,
                'industry': industry_filter,
                'sort': sort_by,
                'order': sort_order
            },
            program_types=PROGRAM_TYPES,
            program_status=PROGRAM_STATUS,
            program_modes=PROGRAM_MODES,
            industry_focus=INDUSTRY_FOCUS
        )
        
    except Exception as e:
        current_app.logger.error(f"Error listando programas: {str(e)}")
        flash('Error al cargar la lista de programas.', 'error')
        return redirect(url_for('admin_dashboard.index'))

@admin_programs.route('/<int:program_id>')
@login_required
@admin_required
@handle_exceptions
def view_program(program_id):
    """
    Vista detallada de un programa específico.
    Incluye cohortes, emprendedores, métricas, curriculum y outcomes.
    """
    try:
        program = Program.query.options(
            joinedload(Program.organization),
            selectinload(Program.cohorts),
            selectinload(Program.entrepreneurs),
            selectinload(Program.milestones),
            selectinload(Program.resources),
            selectinload(Program.mentors)
        ).get_or_404(program_id)
        
        # Métricas del programa
        metrics = _get_program_detailed_metrics(program)
        
        # Cohortes con estadísticas
        cohorts_data = _get_program_cohorts_data(program)
        
        # Emprendedores participantes
        entrepreneurs_data = _get_program_entrepreneurs_data(program)
        
        # Curriculum y milestones
        curriculum_data = _get_program_curriculum_data(program)
        
        # Mentores asignados
        mentors_data = _get_program_mentors_data(program)
        
        # Recursos del programa
        resources_data = _get_program_resources_data(program)
        
        # Performance histórico
        performance_trends = _get_program_performance_trends(program)
        
        # Outcomes y graduados
        outcomes_data = _get_program_outcomes_data(program)
        
        # Financials y ROI
        financial_analysis = _get_program_financial_analysis(program)
        
        # Actividad reciente
        recent_activities = _get_program_recent_activities(program)
        
        # Success stories
        success_stories = _get_program_success_stories(program)
        
        # Comparación con benchmarks
        benchmark_comparison = _get_program_benchmark_comparison(program)
        
        # Recomendaciones del sistema
        recommendations = _generate_program_recommendations(program)
        
        return render_template(
            'admin/programs/view.html',
            program=program,
            metrics=metrics,
            cohorts_data=cohorts_data,
            entrepreneurs_data=entrepreneurs_data,
            curriculum_data=curriculum_data,
            mentors_data=mentors_data,
            resources_data=resources_data,
            performance_trends=performance_trends,
            outcomes_data=outcomes_data,
            financial_analysis=financial_analysis,
            recent_activities=recent_activities,
            success_stories=success_stories,
            benchmark_comparison=benchmark_comparison,
            recommendations=recommendations
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viendo programa {program_id}: {str(e)}")
        flash('Error al cargar los datos del programa.', 'error')
        return redirect(url_for('admin_programs.list_programs'))

@admin_programs.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_program')
@handle_exceptions
def create_program():
    """
    Crea un nuevo programa en el ecosistema.
    Configura información básica, curriculum, recursos y equipo.
    """
    form = ProgramForm()
    
    # Poblar choices dinámicos
    form.organization_id.choices = [
        (org.id, org.name) for org in Organization.query.filter_by(status='active').order_by(Organization.name).all()
    ]
    
    if form.validate_on_submit():
        try:
            # Validaciones adicionales
            if Program.query.filter_by(name=form.name.data.strip()).first():
                flash('Ya existe un programa con este nombre.', 'error')
                return render_template('admin/programs/create.html', form=form)
            
            # Validar fechas
            is_valid, message = validate_program_dates(
                form.start_date.data, 
                form.end_date.data, 
                form.application_deadline.data
            )
            if not is_valid:
                flash(f'Fechas inválidas: {message}', 'error')
                return render_template('admin/programs/create.html', form=form)
            
            # Validar presupuesto
            if form.budget.data:
                is_valid, message = validate_budget(form.budget.data)
                if not is_valid:
                    flash(f'Presupuesto inválido: {message}', 'error')
                    return render_template('admin/programs/create.html', form=form)
            
            # Crear programa
            program = Program(
                name=form.name.data.strip(),
                organization_id=form.organization_id.data,
                type=form.type.data,
                status=form.status.data or 'draft',
                mode=form.mode.data or 'hybrid',
                description=form.description.data.strip() if form.description.data else None,
                objectives=form.objectives.data.strip() if form.objectives.data else None,
                target_audience=form.target_audience.data.strip() if form.target_audience.data else None,
                industry_focus=form.industry_focus.data or [],
                business_stages=form.business_stages.data or [],
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                application_deadline=form.application_deadline.data,
                duration_weeks=form.duration_weeks.data,
                max_participants=form.max_participants.data or 20,
                min_participants=form.min_participants.data or 5,
                budget=form.budget.data,
                currency=form.currency.data or 'USD',
                funding_source=form.funding_source.data.strip() if form.funding_source.data else None,
                selection_criteria=form.selection_criteria.data.strip() if form.selection_criteria.data else None,
                success_metrics=form.success_metrics.data.strip() if form.success_metrics.data else None,
                graduation_requirements=form.graduation_requirements.data.strip() if form.graduation_requirements.data else None,
                certificate_offered=form.certificate_offered.data,
                equity_requirement=form.equity_requirement.data,
                equity_percentage=form.equity_percentage.data,
                is_paid=form.is_paid.data,
                program_fee=form.program_fee.data,
                scholarship_available=form.scholarship_available.data,
                remote_friendly=form.remote_friendly.data,
                location=form.location.data.strip() if form.location.data else None,
                website_url=form.website_url.data.strip() if form.website_url.data else None,
                application_url=form.application_url.data.strip() if form.application_url.data else None,
                is_featured=form.is_featured.data,
                is_public=form.is_public.data,
                created_by=current_user.id
            )
            
            db.session.add(program)
            db.session.flush()  # Para obtener el ID
            
            # Crear milestones iniciales si se proporcionan
            if form.initial_milestones.data:
                curriculum_service = CurriculumService()
                curriculum_service.create_default_milestones(program, form.initial_milestones.data)
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_program',
                resource_type='Program',
                resource_id=program.id,
                details=f'Programa creado: {program.name} ({program.type}) - {program.organization.name}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Programa {program.name} creado exitosamente.', 'success')
            return redirect(url_for('admin_programs.view_program', program_id=program.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando programa: {str(e)}")
            flash('Error al crear el programa.', 'error')
    
    return render_template('admin/programs/create.html', form=form)

@admin_programs.route('/<int:program_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('edit_program')
@handle_exceptions
def edit_program(program_id):
    """
    Edita la información de un programa existente.
    Permite modificar configuración, fechas, curriculum y recursos.
    """
    program = Program.query.options(
        joinedload(Program.organization)
    ).get_or_404(program_id)
    
    form = ProgramForm(obj=program)
    
    # Poblar choices dinámicos
    form.organization_id.choices = [
        (org.id, org.name) for org in Organization.query.filter_by(status='active').order_by(Organization.name).all()
    ]
    
    if form.validate_on_submit():
        try:
            # Verificar nombre único (excluyendo el programa actual)
            existing = Program.query.filter(
                and_(
                    Program.name == form.name.data.strip(),
                    Program.id != program.id
                )
            ).first()
            
            if existing:
                flash('Ya existe otro programa con este nombre.', 'error')
                return render_template('admin/programs/edit.html', form=form, program=program)
            
            # Validar fechas
            is_valid, message = validate_program_dates(
                form.start_date.data, 
                form.end_date.data, 
                form.application_deadline.data
            )
            if not is_valid:
                flash(f'Fechas inválidas: {message}', 'error')
                return render_template('admin/programs/edit.html', form=form, program=program)
            
            # Almacenar valores anteriores para auditoría
            old_values = {
                'name': program.name,
                'status': program.status,
                'start_date': program.start_date,
                'end_date': program.end_date,
                'max_participants': program.max_participants,
                'budget': program.budget
            }
            
            # Actualizar programa
            program.name = form.name.data.strip()
            program.organization_id = form.organization_id.data
            program.type = form.type.data
            program.status = form.status.data
            program.mode = form.mode.data
            program.description = form.description.data.strip() if form.description.data else None
            program.objectives = form.objectives.data.strip() if form.objectives.data else None
            program.target_audience = form.target_audience.data.strip() if form.target_audience.data else None
            program.industry_focus = form.industry_focus.data or []
            program.business_stages = form.business_stages.data or []
            program.start_date = form.start_date.data
            program.end_date = form.end_date.data
            program.application_deadline = form.application_deadline.data
            program.duration_weeks = form.duration_weeks.data
            program.max_participants = form.max_participants.data
            program.min_participants = form.min_participants.data
            program.budget = form.budget.data
            program.currency = form.currency.data
            program.funding_source = form.funding_source.data.strip() if form.funding_source.data else None
            program.selection_criteria = form.selection_criteria.data.strip() if form.selection_criteria.data else None
            program.success_metrics = form.success_metrics.data.strip() if form.success_metrics.data else None
            program.graduation_requirements = form.graduation_requirements.data.strip() if form.graduation_requirements.data else None
            program.certificate_offered = form.certificate_offered.data
            program.equity_requirement = form.equity_requirement.data
            program.equity_percentage = form.equity_percentage.data
            program.is_paid = form.is_paid.data
            program.program_fee = form.program_fee.data
            program.scholarship_available = form.scholarship_available.data
            program.remote_friendly = form.remote_friendly.data
            program.location = form.location.data.strip() if form.location.data else None
            program.website_url = form.website_url.data.strip() if form.website_url.data else None
            program.application_url = form.application_url.data.strip() if form.application_url.data else None
            program.is_featured = form.is_featured.data
            program.is_public = form.is_public.data
            program.updated_at = datetime.now(timezone.utc)
            
            # Recalcular métricas si cambió el status
            if old_values['status'] != program.status:
                _recalculate_program_metrics(program)
            
            db.session.commit()
            
            # Registrar cambios en auditoría
            changes = []
            for field, old_value in old_values.items():
                new_value = getattr(program, field)
                if old_value != new_value:
                    changes.append(f'{field}: {old_value} → {new_value}')
            
            if changes:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_program',
                    resource_type='Program',
                    resource_id=program.id,
                    details=f'Programa actualizado: {", ".join(changes)}'
                )
                db.session.add(activity)
                
                # Notificar cambios importantes a participantes
                if 'start_date' in changes or 'status' in changes:
                    _notify_program_participants_of_changes(program, changes)
                
                db.session.commit()
            
            flash(f'Programa {program.name} actualizado exitosamente.', 'success')
            return redirect(url_for('admin_programs.view_program', program_id=program.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando programa {program_id}: {str(e)}")
            flash('Error al actualizar el programa.', 'error')
    
    return render_template('admin/programs/edit.html', form=form, program=program)

# ============================================================================
# GESTIÓN DE COHORTES
# ============================================================================

@admin_programs.route('/<int:program_id>/cohorts')
@login_required
@admin_required
@handle_exceptions
def cohorts(program_id):
    """
    Muestra todas las cohortes de un programa.
    """
    try:
        program = Program.query.options(
            joinedload(Program.organization)
        ).get_or_404(program_id)
        
        # Obtener cohortes con estadísticas
        cohorts = Cohort.query.filter_by(
            program_id=program.id
        ).options(
            selectinload(Cohort.entrepreneurs),
            selectinload(Cohort.mentors)
        ).order_by(desc(Cohort.start_date)).all()
        
        # Estadísticas de cohortes
        cohort_stats = {
            'total': len(cohorts),
            'active': len([c for c in cohorts if c.status == 'active']),
            'completed': len([c for c in cohorts if c.status == 'completed']),
            'upcoming': len([c for c in cohorts if c.status == 'upcoming']),
            'total_participants': sum([len(c.entrepreneurs) for c in cohorts]),
            'avg_participants': sum([len(c.entrepreneurs) for c in cohorts]) / len(cohorts) if cohorts else 0,
            'graduation_rate': _calculate_overall_graduation_rate(cohorts)
        }
        
        return render_template(
            'admin/programs/cohorts.html',
            program=program,
            cohorts=cohorts,
            cohort_stats=cohort_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando cohortes: {str(e)}")
        flash('Error al cargar las cohortes.', 'error')
        return redirect(url_for('admin_programs.view_program', program_id=program_id))

@admin_programs.route('/<int:program_id>/create-cohort', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_cohort')
@handle_exceptions
def create_cohort(program_id):
    """
    Crea una nueva cohorte para el programa.
    """
    program = Program.query.get_or_404(program_id)
    form = CohortForm()
    
    if form.validate_on_submit():
        try:
            # Validar capacidad
            is_valid, message = validate_capacity(
                form.max_participants.data, 
                program.max_participants
            )
            if not is_valid:
                flash(f'Capacidad inválida: {message}', 'error')
                return render_template('admin/programs/create_cohort.html', 
                                     form=form, program=program)
            
            # Crear cohorte
            cohort = Cohort(
                program_id=program.id,
                name=form.name.data.strip(),
                cohort_number=form.cohort_number.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                max_participants=form.max_participants.data or program.max_participants,
                status=form.status.data or 'upcoming',
                description=form.description.data.strip() if form.description.data else None,
                goals=form.goals.data.strip() if form.goals.data else None,
                created_by=current_user.id
            )
            
            db.session.add(cohort)
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_cohort',
                resource_type='Cohort',
                resource_id=cohort.id,
                details=f'Cohorte creada: {cohort.name} - {program.name}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Cohorte {cohort.name} creada exitosamente.', 'success')
            return redirect(url_for('admin_programs.cohorts', program_id=program.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando cohorte: {str(e)}")
            flash('Error al crear la cohorte.', 'error')
    
    return render_template('admin/programs/create_cohort.html', 
                         form=form, program=program)

# ============================================================================
# GESTIÓN DE CURRICULUM Y MILESTONES
# ============================================================================

@admin_programs.route('/<int:program_id>/curriculum')
@login_required
@admin_required
@handle_exceptions
def curriculum(program_id):
    """
    Gestiona el curriculum y milestones del programa.
    """
    try:
        program = Program.query.options(
            joinedload(Program.organization),
            selectinload(Program.milestones)
        ).get_or_404(program_id)
        
        # Obtener milestones ordenados
        milestones = Milestone.query.filter_by(
            program_id=program.id
        ).order_by(Milestone.week_number, Milestone.order).all()
        
        # Agrupar por semana
        milestones_by_week = {}
        for milestone in milestones:
            week = milestone.week_number or 0
            if week not in milestones_by_week:
                milestones_by_week[week] = []
            milestones_by_week[week].append(milestone)
        
        # Estadísticas del curriculum
        curriculum_stats = {
            'total_milestones': len(milestones),
            'weeks_covered': len(milestones_by_week),
            'completion_rate': _calculate_curriculum_completion_rate(program),
            'avg_milestone_duration': _calculate_avg_milestone_duration(milestones)
        }
        
        return render_template(
            'admin/programs/curriculum.html',
            program=program,
            milestones=milestones,
            milestones_by_week=milestones_by_week,
            curriculum_stats=curriculum_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando curriculum: {str(e)}")
        flash('Error al cargar el curriculum.', 'error')
        return redirect(url_for('admin_programs.view_program', program_id=program_id))

@admin_programs.route('/<int:program_id>/add-milestone', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_program_curriculum')
@handle_exceptions
def add_milestone(program_id):
    """
    Añade un nuevo milestone al curriculum del programa.
    """
    program = Program.query.get_or_404(program_id)
    form = MilestoneForm()
    
    if form.validate_on_submit():
        try:
            # Crear milestone
            milestone = Milestone(
                program_id=program.id,
                name=form.name.data.strip(),
                description=form.description.data.strip() if form.description.data else None,
                week_number=form.week_number.data,
                order=form.order.data or 1,
                type=form.type.data or 'learning',
                is_required=form.is_required.data,
                deliverables=form.deliverables.data.strip() if form.deliverables.data else None,
                resources_needed=form.resources_needed.data.strip() if form.resources_needed.data else None,
                estimated_hours=form.estimated_hours.data,
                due_date_offset=form.due_date_offset.data,
                weight=form.weight.data or 1.0,
                created_by=current_user.id
            )
            
            db.session.add(milestone)
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='add_program_milestone',
                resource_type='Milestone',
                resource_id=milestone.id,
                details=f'Milestone añadido: {milestone.name} - Semana {milestone.week_number}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Milestone {milestone.name} añadido exitosamente.', 'success')
            return redirect(url_for('admin_programs.curriculum', program_id=program.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error añadiendo milestone: {str(e)}")
            flash('Error al añadir el milestone.', 'error')
    
    return render_template('admin/programs/add_milestone.html', 
                         form=form, program=program)

# ============================================================================
# GESTIÓN DE PARTICIPANTES
# ============================================================================

@admin_programs.route('/<int:program_id>/participants')
@login_required
@admin_required
@handle_exceptions
def participants(program_id):
    """
    Gestiona los participantes del programa.
    """
    try:
        program = Program.query.options(
            joinedload(Program.organization),
            selectinload(Program.entrepreneurs),
            selectinload(Program.entrepreneurs).joinedload(Entrepreneur.user)
        ).get_or_404(program_id)
        
        # Obtener participantes con datos adicionales
        participants = program.entrepreneurs
        
        # Estadísticas de participantes
        participant_stats = {
            'total': len(participants),
            'active': len([p for p in participants if p.user.is_active]),
            'graduated': len([p for p in participants if getattr(p, 'graduation_status', None) == 'graduated']),
            'in_progress': len([p for p in participants if getattr(p, 'program_status', None) == 'in_progress']),
            'dropout_rate': _calculate_dropout_rate(participants),
            'avg_progress': _calculate_avg_participant_progress(participants)
        }
        
        # Agrupar por cohorte
        participants_by_cohort = {}
        for participant in participants:
            cohort_id = getattr(participant, 'cohort_id', 'no_cohort')
            if cohort_id not in participants_by_cohort:
                participants_by_cohort[cohort_id] = []
            participants_by_cohort[cohort_id].append(participant)
        
        return render_template(
            'admin/programs/participants.html',
            program=program,
            participants=participants,
            participant_stats=participant_stats,
            participants_by_cohort=participants_by_cohort
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando participantes: {str(e)}")
        flash('Error al cargar los participantes.', 'error')
        return redirect(url_for('admin_programs.view_program', program_id=program_id))

# ============================================================================
# EVALUACIÓN Y PERFORMANCE
# ============================================================================

@admin_programs.route('/<int:program_id>/evaluate', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('evaluate_program')
@handle_exceptions
def evaluate_program(program_id):
    """
    Evalúa el rendimiento e impacto de un programa.
    """
    program = Program.query.get_or_404(program_id)
    form = EvaluateProgramForm()
    
    if form.validate_on_submit():
        try:
            # Preparar datos de evaluación
            evaluation_data = {
                'curriculum_quality': form.curriculum_quality.data,
                'mentor_effectiveness': form.mentor_effectiveness.data,
                'participant_satisfaction': form.participant_satisfaction.data,
                'learning_outcomes': form.learning_outcomes.data,
                'business_outcomes': form.business_outcomes.data,
                'network_value': form.network_value.data,
                'resource_adequacy': form.resource_adequacy.data,
                'program_management': form.program_management.data,
                'notes': form.notes.data.strip() if form.notes.data else None,
                'recommendations': form.recommendations.data.strip() if form.recommendations.data else None,
                'evaluator_id': current_user.id,
                'evaluation_date': datetime.now(timezone.utc)
            }
            
            # Calcular score promedio
            rating_fields = [
                'curriculum_quality', 'mentor_effectiveness', 'participant_satisfaction',
                'learning_outcomes', 'business_outcomes', 'network_value',
                'resource_adequacy', 'program_management'
            ]
            total_score = sum([evaluation_data[field] for field in rating_fields]) / len(rating_fields)
            
            # Actualizar programa
            program.evaluation_data = evaluation_data  # JSON field
            program.last_evaluation_at = datetime.now(timezone.utc)
            program.quality_score = total_score
            
            # Determinar nivel de calidad
            if total_score >= 4.5:
                quality_level = 'excellent'
            elif total_score >= 3.5:
                quality_level = 'good'
            elif total_score >= 2.5:
                quality_level = 'fair'
            else:
                quality_level = 'needs_improvement'
            
            program.quality_level = quality_level
            
            # Recalcular métricas del programa
            _recalculate_program_metrics(program)
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='evaluate_program',
                resource_type='Program',
                resource_id=program.id,
                details=f'Evaluación completada. Score: {total_score:.1f}/5.0, Calidad: {quality_level}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Evaluación completada. Score: {total_score:.1f}/5.0 ({quality_level})', 'success')
            return redirect(url_for('admin_programs.view_program', program_id=program.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error evaluando programa: {str(e)}")
            flash('Error al guardar la evaluación.', 'error')
    
    return render_template('admin/programs/evaluate.html', 
                         form=form, program=program)

# ============================================================================
# ANALYTICS Y ESTADÍSTICAS
# ============================================================================

@admin_programs.route('/analytics')
@login_required
@admin_required
@cache_result(timeout=300)
def analytics():
    """
    Dashboard de analytics para programas del ecosistema.
    """
    try:
        analytics_service = AnalyticsService()
        
        # Métricas generales
        general_metrics = _get_comprehensive_program_metrics()
        
        # Datos para gráficos
        charts_data = {
            'programs_by_type': analytics_service.get_programs_by_type(),
            'completion_rates_by_type': analytics_service.get_completion_rates_by_type(),
            'participant_growth': analytics_service.get_program_participant_growth(days=365),
            'success_outcomes': analytics_service.get_program_success_outcomes(),
            'geographic_reach': analytics_service.get_program_geographic_reach(),
            'roi_analysis': analytics_service.get_program_roi_analysis(),
            'mentor_effectiveness': analytics_service.get_mentor_effectiveness_by_program()
        }
        
        # Top performing programs
        top_performers = _get_top_performing_programs(limit=10)
        
        # Programas que necesitan atención
        needs_attention = _get_programs_needing_attention(limit=10)
        
        # Benchmarks de la industria
        industry_benchmarks = _get_industry_benchmarks()
        
        # Trends y proyecciones
        future_projections = _get_program_projections()
        
        return render_template(
            'admin/programs/analytics.html',
            general_metrics=general_metrics,
            charts_data=charts_data,
            top_performers=top_performers,
            needs_attention=needs_attention,
            industry_benchmarks=industry_benchmarks,
            future_projections=future_projections
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando analytics: {str(e)}")
        flash('Error al cargar los analytics.', 'error')
        return redirect(url_for('admin_programs.list_programs'))

# ============================================================================
# ACCIONES EN LOTE
# ============================================================================

@admin_programs.route('/bulk-actions', methods=['POST'])
@login_required
@admin_required
@permission_required('bulk_program_actions')
@handle_exceptions
def bulk_actions():
    """
    Ejecuta acciones en lote sobre múltiples programas.
    """
    form = BulkProgramActionForm()
    
    if form.validate_on_submit():
        try:
            program_ids = [int(id) for id in form.program_ids.data.split(',') if id.strip()]
            action = form.action.data
            
            if not program_ids:
                flash('No se seleccionaron programas.', 'warning')
                return redirect(url_for('admin_programs.list_programs'))
            
            programs = Program.query.filter(
                Program.id.in_(program_ids)
            ).options(joinedload(Program.organization)).all()
            
            success_count = 0
            
            for program in programs:
                try:
                    if action == 'activate':
                        program.status = 'active'
                        success_count += 1
                        
                    elif action == 'pause':
                        program.status = 'paused'
                        success_count += 1
                        
                    elif action == 'complete':
                        program.status = 'completed'
                        _finalize_program(program)
                        success_count += 1
                        
                    elif action == 'mark_featured':
                        program.is_featured = True
                        success_count += 1
                        
                    elif action == 'unmark_featured':
                        program.is_featured = False
                        success_count += 1
                        
                    elif action == 'update_currency':
                        if form.new_currency.data:
                            program.currency = form.new_currency.data
                            success_count += 1
                            
                    elif action == 'recalculate_metrics':
                        _recalculate_program_metrics(program)
                        success_count += 1
                        
                    elif action == 'send_notification':
                        _send_program_notification(
                            program,
                            form.notification_title.data,
                            form.notification_message.data
                        )
                        success_count += 1
                        
                except Exception as e:
                    current_app.logger.warning(f"Error procesando programa {program.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='bulk_program_action',
                resource_type='Program',
                details=f'Acción en lote: {action} aplicada a {success_count} programas'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Acción aplicada exitosamente a {success_count} programa(s).', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error en acción en lote: {str(e)}")
            flash('Error al ejecutar la acción en lote.', 'error')
    else:
        flash('Datos de formulario inválidos.', 'error')
    
    return redirect(url_for('admin_programs.list_programs'))

# ============================================================================
# EXPORTACIÓN
# ============================================================================

@admin_programs.route('/export')
@login_required
@admin_required
@permission_required('export_programs')
@handle_exceptions
def export_programs():
    """
    Exporta datos de programas en diferentes formatos.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_participants = request.args.get('include_participants', 'false') == 'true'
        include_outcomes = request.args.get('include_outcomes', 'false') == 'true'
        type_filter = request.args.get('type', 'all')
        
        # Construir query
        query = Program.query.options(
            joinedload(Program.organization),
            selectinload(Program.entrepreneurs),
            selectinload(Program.cohorts)
        )
        
        if type_filter != 'all':
            query = query.filter(Program.type == type_filter)
        
        programs = query.order_by(Program.created_at.desc()).all()
        
        # Preparar datos de exportación
        export_data = []
        for program in programs:
            row = {
                'ID': program.id,
                'Nombre': program.name,
                'Organización': program.organization.name,
                'Tipo': program.type,
                'Estado': program.status,
                'Modalidad': program.mode,
                'Industrias Foco': ', '.join(program.industry_focus) if program.industry_focus else 'N/A',
                'Etapas de Negocio': ', '.join(program.business_stages) if program.business_stages else 'N/A',
                'Fecha Inicio': program.start_date.strftime('%Y-%m-%d') if program.start_date else 'N/A',
                'Fecha Fin': program.end_date.strftime('%Y-%m-%d') if program.end_date else 'N/A',
                'Duración (semanas)': program.duration_weeks or 'N/A',
                'Max Participantes': program.max_participants or 'N/A',
                'Participantes Actuales': len(program.entrepreneurs),
                'Presupuesto': f"${program.budget:,.2f} {program.currency}" if program.budget else 'N/A',
                'Es Pagado': 'Sí' if program.is_paid else 'No',
                'Tarifa Programa': f"${program.program_fee:,.2f}" if program.program_fee else 'N/A',
                'Requiere Equity': 'Sí' if program.equity_requirement else 'No',
                'Porcentaje Equity': f"{program.equity_percentage}%" if program.equity_percentage else 'N/A',
                'Certificado': 'Sí' if program.certificate_offered else 'No',
                'Remoto': 'Sí' if program.remote_friendly else 'No',
                'Ubicación': program.location or 'N/A',
                'Score de Calidad': f"{program.quality_score:.1f}" if program.quality_score else 'N/A',
                'Nivel de Calidad': program.quality_level or 'N/A',
                'Tasa Graduación': f"{program.graduation_rate:.1f}%" if program.graduation_rate else 'N/A',
                'Tasa Éxito': f"{program.success_rate:.1f}%" if program.success_rate else 'N/A',
                'Es Destacado': 'Sí' if program.is_featured else 'No',
                'Es Público': 'Sí' if program.is_public else 'No',
                'Website': program.website_url or 'N/A',
                'URL Aplicación': program.application_url or 'N/A',
                'Fecha Creación': program.created_at.strftime('%Y-%m-%d'),
                'Última Actualización': program.updated_at.strftime('%Y-%m-%d %H:%M') if program.updated_at else 'N/A'
            }
            
            # Incluir datos de participantes si se solicita
            if include_participants:
                active_participants = len([e for e in program.entrepreneurs if e.user.is_active])
                graduated_participants = len([e for e in program.entrepreneurs if getattr(e, 'graduation_status', None) == 'graduated'])
                row['Participantes Activos'] = active_participants
                row['Participantes Graduados'] = graduated_participants
                
            # Incluir datos de outcomes si se solicita
            if include_outcomes:
                successful_startups = len([e for e in program.entrepreneurs if getattr(e, 'startup_status', None) == 'successful'])
                row['Startups Exitosas'] = successful_startups
                row['ROI Estimado'] = f"{_calculate_program_roi(program):.1f}%" if program.budget else 'N/A'
            
            export_data.append(row)
        
        # Generar archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            filename = f'programas_{timestamp}.xlsx'
            return export_to_excel(export_data, filename, 'Programas')
        elif export_format == 'csv':
            filename = f'programas_{timestamp}.csv'
            return export_to_csv(export_data, filename)
        elif export_format == 'pdf':
            filename = f'programas_{timestamp}.pdf'
            return export_to_pdf(export_data, filename, 'Reporte de Programas')
        
    except Exception as e:
        current_app.logger.error(f"Error exportando programas: {str(e)}")
        flash('Error al exportar los datos.', 'error')
        return redirect(url_for('admin_programs.list_programs'))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_programs.route('/api/search')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_search_programs():
    """API para búsqueda de programas en tiempo real."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        program_type = request.args.get('type', '')
        
        if len(query) < 2:
            return jsonify({'programs': []})
        
        search_query = Program.query.filter(
            or_(
                Program.name.ilike(f'%{query}%'),
                Program.description.ilike(f'%{query}%'),
                Program.objectives.ilike(f'%{query}%')
            )
        ).options(joinedload(Program.organization))
        
        if program_type:
            search_query = search_query.filter(Program.type == program_type)
        
        programs = search_query.limit(limit).all()
        
        return jsonify({
            'programs': [
                {
                    'id': program.id,
                    'name': program.name,
                    'organization': program.organization.name,
                    'type': program.type,
                    'status': program.status,
                    'mode': program.mode,
                    'participants_count': len(program.entrepreneurs),
                    'max_participants': program.max_participants,
                    'start_date': program.start_date.isoformat() if program.start_date else None,
                    'graduation_rate': program.graduation_rate,
                    'quality_score': program.quality_score
                }
                for program in programs
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_program_statistics():
    """Obtiene estadísticas básicas de programas."""
    return {
        'total': Program.query.count(),
        'active': Program.query.filter_by(status='active').count(),
        'completed': Program.query.filter_by(status='completed').count(),
        'upcoming': Program.query.filter_by(status='upcoming').count(),
        'by_type': {
            ptype: Program.query.filter_by(type=ptype).count()
            for ptype in PROGRAM_TYPES
        },
        'total_participants': db.session.query(
            func.count(Entrepreneur.id)
        ).join(Program.entrepreneurs).scalar() or 0,
        'avg_graduation_rate': db.session.query(
            func.avg(Program.graduation_rate)
        ).filter(Program.graduation_rate.isnot(None)).scalar() or 0,
        'featured_programs': Program.query.filter_by(is_featured=True).count()
    }

def _get_program_detailed_metrics(program):
    """Obtiene métricas detalladas de un programa."""
    entrepreneurs = program.entrepreneurs
    
    return {
        'age_days': (datetime.now(timezone.utc) - program.created_at).days,
        'participants_count': len(entrepreneurs),
        'capacity_utilization': (len(entrepreneurs) / program.max_participants * 100) if program.max_participants else 0,
        'cohorts_count': len(program.cohorts),
        'active_cohorts': len([c for c in program.cohorts if c.status == 'active']),
        'milestones_count': len(program.milestones),
        'resources_count': len(program.resources),
        'mentors_count': len(program.mentors) if hasattr(program, 'mentors') else 0,
        'graduation_rate': program.graduation_rate or 0,
        'success_rate': program.success_rate or 0,
        'quality_score': program.quality_score or 0,
        'budget_utilization': _calculate_budget_utilization(program),
        'avg_participant_progress': _calculate_avg_participant_progress(entrepreneurs)
    }

def _get_program_cohorts_data(program):
    """Obtiene datos de cohortes del programa."""
    cohorts = program.cohorts
    
    return {
        'total': len(cohorts),
        'by_status': {
            'active': len([c for c in cohorts if c.status == 'active']),
            'completed': len([c for c in cohorts if c.status == 'completed']),
            'upcoming': len([c for c in cohorts if c.status == 'upcoming'])
        },
        'total_participants': sum([len(c.entrepreneurs) for c in cohorts]),
        'avg_size': sum([len(c.entrepreneurs) for c in cohorts]) / len(cohorts) if cohorts else 0
    }

def _get_program_entrepreneurs_data(program):
    """Obtiene datos de emprendedores del programa."""
    entrepreneurs = program.entrepreneurs
    
    return {
        'total': len(entrepreneurs),
        'active': len([e for e in entrepreneurs if e.user.is_active]),
        'by_stage': {
            stage: len([e for e in entrepreneurs if e.business_stage == stage])
            for stage in BUSINESS_STAGES
        },
        'graduated': len([e for e in entrepreneurs if getattr(e, 'graduation_status', None) == 'graduated']),
        'in_progress': len([e for e in entrepreneurs if getattr(e, 'program_status', None) == 'in_progress']),
        'dropout_rate': _calculate_dropout_rate(entrepreneurs)
    }

def _get_program_curriculum_data(program):
    """Obtiene datos del curriculum del programa."""
    milestones = program.milestones
    
    return {
        'total_milestones': len(milestones),
        'required_milestones': len([m for m in milestones if m.is_required]),
        'optional_milestones': len([m for m in milestones if not m.is_required]),
        'weeks_covered': len(set([m.week_number for m in milestones if m.week_number])),
        'total_estimated_hours': sum([m.estimated_hours for m in milestones if m.estimated_hours]),
        'completion_rate': _calculate_curriculum_completion_rate(program)
    }

def _get_program_mentors_data(program):
    """Obtiene datos de mentores del programa."""
    # Esto requeriría una relación many-to-many entre Program y Ally
    # Por ahora simularemos con datos básicos
    return {
        'total_mentors': 0,  # len(program.mentors) cuando se implemente
        'active_mentors': 0,
        'mentor_entrepreneur_ratio': 0,
        'avg_mentor_rating': 0
    }

def _get_program_resources_data(program):
    """Obtiene datos de recursos del programa."""
    resources = program.resources if hasattr(program, 'resources') else []
    
    return {
        'total': len(resources),
        'by_type': {},  # Categorizar cuando se implemente el modelo Resource
        'avg_utilization': 0
    }

def _get_program_performance_trends(program):
    """Obtiene tendencias de rendimiento del programa."""
    # Esto requeriría datos históricos más detallados
    return {
        'participation_trend': 'stable',
        'graduation_trend': 'improving',
        'satisfaction_trend': 'stable'
    }

def _get_program_outcomes_data(program):
    """Obtiene datos de outcomes del programa."""
    entrepreneurs = program.entrepreneurs
    
    # Simulamos outcomes basándonos en datos disponibles
    successful_startups = len([e for e in entrepreneurs if e.evaluation_score and e.evaluation_score >= 80])
    funded_startups = len([e for e in entrepreneurs if e.funding_raised and e.funding_raised > 0])
    
    return {
        'total_graduates': len([e for e in entrepreneurs if getattr(e, 'graduation_status', None) == 'graduated']),
        'successful_startups': successful_startups,
        'funded_startups': funded_startups,
        'jobs_created': len(entrepreneurs) * 2,  # Estimación
        'total_funding_raised': sum([e.funding_raised for e in entrepreneurs if e.funding_raised]) or 0,
        'follow_up_rate': 85.0  # Simulado
    }

def _get_program_financial_analysis(program):
    """Obtiene análisis financiero del programa."""
    budget = program.budget or 0
    participants = len(program.entrepreneurs)
    
    cost_per_participant = budget / participants if participants > 0 else 0
    
    return {
        'total_budget': budget,
        'cost_per_participant': cost_per_participant,
        'revenue': program.program_fee * participants if program.program_fee else 0,
        'roi': _calculate_program_roi(program),
        'budget_utilization': _calculate_budget_utilization(program)
    }

def _get_program_recent_activities(program):
    """Obtiene actividad reciente del programa."""
    return ActivityLog.query.filter(
        or_(
            and_(
                ActivityLog.resource_type == 'Program',
                ActivityLog.resource_id == program.id
            ),
            ActivityLog.details.ilike(f'%{program.name}%')
        )
    ).options(
        joinedload(ActivityLog.user)
    ).order_by(desc(ActivityLog.created_at)).limit(10).all()

def _get_program_success_stories(program):
    """Obtiene historias de éxito del programa."""
    # Simulamos success stories basándonos en emprendedores exitosos
    entrepreneurs = program.entrepreneurs
    success_stories = []
    
    for entrepreneur in entrepreneurs:
        if entrepreneur.evaluation_score and entrepreneur.evaluation_score >= 85:
            success_stories.append({
                'entrepreneur': entrepreneur,
                'achievement': 'High evaluation score',
                'impact': f'Score: {entrepreneur.evaluation_score}'
            })
    
    return success_stories[:5]  # Top 5

def _get_program_benchmark_comparison(program):
    """Obtiene comparación con benchmarks de la industria."""
    # Simulamos benchmarks basándonos en tipo de programa
    industry_benchmarks = {
        'incubator': {'graduation_rate': 75, 'success_rate': 25},
        'accelerator': {'graduation_rate': 85, 'success_rate': 35},
        'bootcamp': {'graduation_rate': 90, 'success_rate': 60}
    }
    
    benchmark = industry_benchmarks.get(program.type, {'graduation_rate': 80, 'success_rate': 30})
    
    return {
        'industry_graduation_rate': benchmark['graduation_rate'],
        'program_graduation_rate': program.graduation_rate or 0,
        'industry_success_rate': benchmark['success_rate'],
        'program_success_rate': program.success_rate or 0,
        'performance_vs_industry': 'above' if (program.graduation_rate or 0) > benchmark['graduation_rate'] else 'below'
    }

def _generate_program_recommendations(program):
    """Genera recomendaciones automáticas para el programa."""
    recommendations = []
    
    # Recomendaciones basadas en utilización de capacidad
    capacity_utilization = (len(program.entrepreneurs) / program.max_participants * 100) if program.max_participants else 0
    
    if capacity_utilization < 50:
        recommendations.append({
            'type': 'capacity',
            'priority': 'medium',
            'title': 'Baja Utilización de Capacidad',
            'description': f'Solo {capacity_utilization:.1f}% de capacidad utilizada.',
            'action': 'Aumentar marketing y outreach'
        })
    
    # Recomendaciones basadas en graduation rate
    if program.graduation_rate and program.graduation_rate < 70:
        recommendations.append({
            'type': 'retention',
            'priority': 'high',
            'title': 'Baja Tasa de Graduación',
            'description': f'Tasa de graduación de {program.graduation_rate:.1f}% está por debajo del estándar.',
            'action': 'Revisar curriculum y soporte a participantes'
        })
    
    # Recomendaciones basadas en fechas
    if program.start_date and program.start_date < datetime.now(timezone.utc).date() and program.status == 'upcoming':
        recommendations.append({
            'type': 'status',
            'priority': 'high',
            'title': 'Actualizar Estado',
            'description': 'El programa ya inició pero el estado sigue como "upcoming".',
            'action': 'Cambiar estado a "active"'
        })
    
    return recommendations

def _calculate_overall_graduation_rate(cohorts):
    """Calcula la tasa de graduación general de las cohortes."""
    if not cohorts:
        return 0
    
    total_participants = sum([len(c.entrepreneurs) for c in cohorts])
    total_graduates = sum([len([e for e in c.entrepreneurs if getattr(e, 'graduation_status', None) == 'graduated']) for c in cohorts])
    
    return (total_graduates / total_participants * 100) if total_participants > 0 else 0

def _calculate_curriculum_completion_rate(program):
    """Calcula la tasa de completación del curriculum."""
    # Esto requeriría tracking detallado de progreso por milestone
    # Por ahora retornamos un valor simulado
    return 75.0

def _calculate_avg_milestone_duration(milestones):
    """Calcula la duración promedio de milestones."""
    durations = [m.estimated_hours for m in milestones if m.estimated_hours]
    return sum(durations) / len(durations) if durations else 0

def _calculate_dropout_rate(participants):
    """Calcula la tasa de deserción de participantes."""
    if not participants:
        return 0
    
    dropouts = len([p for p in participants if getattr(p, 'program_status', None) == 'dropped_out'])
    return (dropouts / len(participants) * 100)

def _calculate_avg_participant_progress(participants):
    """Calcula el progreso promedio de participantes."""
    if not participants:
        return 0
    
    # Simulamos progreso basado en evaluation_score
    progress_scores = [p.evaluation_score for p in participants if p.evaluation_score]
    return sum(progress_scores) / len(progress_scores) if progress_scores else 0

def _calculate_budget_utilization(program):
    """Calcula la utilización del presupuesto."""
    # Esto requeriría tracking detallado de gastos
    # Por ahora retornamos un valor simulado
    return 80.0

def _calculate_program_roi(program):
    """Calcula el ROI del programa."""
    if not program.budget or program.budget == 0:
        return 0
    
    # ROI simulado basado en outcomes
    participants = len(program.entrepreneurs)
    successful_participants = len([e for e in program.entrepreneurs if e.evaluation_score and e.evaluation_score >= 80])
    
    # Valor estimado generado por participante exitoso
    value_per_success = 100000  # $100k estimado
    total_value = successful_participants * value_per_success
    
    return ((total_value - program.budget) / program.budget * 100)

def _recalculate_program_metrics(program):
    """Recalcula todas las métricas del programa."""
    entrepreneurs = program.entrepreneurs
    
    if entrepreneurs:
        # Calcular graduation rate
        graduates = len([e for e in entrepreneurs if getattr(e, 'graduation_status', None) == 'graduated'])
        program.graduation_rate = (graduates / len(entrepreneurs) * 100)
        
        # Calcular success rate
        successful = len([e for e in entrepreneurs if e.evaluation_score and e.evaluation_score >= 80])
        program.success_rate = (successful / len(entrepreneurs) * 100)
        
        # Actualizar contadores
        program.current_participants = len([e for e in entrepreneurs if e.user.is_active])

def _finalize_program(program):
    """Finaliza un programa calculando métricas finales."""
    _recalculate_program_metrics(program)
    program.completion_date = datetime.now(timezone.utc)
    
    # Generar certificados si aplica
    if program.certificate_offered:
        _generate_program_certificates(program)

def _generate_program_certificates(program):
    """Genera certificados para graduados del programa."""
    # Implementar lógica de generación de certificados
    pass

def _send_program_notification(program, title, message):
    """Envía notificación a todos los participantes del programa."""
    notification_service = NotificationService()
    
    for entrepreneur in program.entrepreneurs:
        if entrepreneur.user.is_active:
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='program_update',
                title=title,
                message=message,
                priority='medium'
            )

def _notify_program_participants_of_changes(program, changes):
    """Notifica a participantes sobre cambios importantes."""
    notification_service = NotificationService()
    
    message = f"Se han realizado cambios importantes en el programa {program.name}: {', '.join(changes)}"
    
    for entrepreneur in program.entrepreneurs:
        if entrepreneur.user.is_active:
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='program_change',
                title='Cambios en el Programa',
                message=message,
                priority='high'
            )

def _get_comprehensive_program_metrics():
    """Obtiene métricas comprehensivas para analytics."""
    return {
        'total_programs': Program.query.count(),
        'active_programs': Program.query.filter_by(status='active').count(),
        'total_participants': db.session.query(func.count(Entrepreneur.id)).join(Program.entrepreneurs).scalar() or 0,
        'avg_graduation_rate': db.session.query(func.avg(Program.graduation_rate)).filter(
            Program.graduation_rate.isnot(None)
        ).scalar() or 0,
        'avg_success_rate': db.session.query(func.avg(Program.success_rate)).filter(
            Program.success_rate.isnot(None)
        ).scalar() or 0,
        'total_investment': db.session.query(func.sum(Program.budget)).scalar() or 0
    }

def _get_top_performing_programs(limit=10):
    """Obtiene programas con mejor desempeño."""
    return Program.query.filter(
        and_(
            Program.graduation_rate.isnot(None),
            Program.success_rate.isnot(None)
        )
    ).order_by(
        desc(Program.success_rate),
        desc(Program.graduation_rate)
    ).limit(limit).all()

def _get_programs_needing_attention(limit=10):
    """Obtiene programas que necesitan atención."""
    return Program.query.filter(
        or_(
            Program.graduation_rate < 60,
            Program.success_rate < 20,
            and_(
                Program.status == 'active',
                Program.current_participants < (Program.max_participants * 0.5)
            )
        )
    ).order_by(
        Program.graduation_rate.asc(),
        Program.success_rate.asc()
    ).limit(limit).all()

def _get_industry_benchmarks():
    """Obtiene benchmarks de la industria."""
    return {
        'incubator': {'graduation_rate': 75, 'success_rate': 25, 'duration_weeks': 24},
        'accelerator': {'graduation_rate': 85, 'success_rate': 35, 'duration_weeks': 12},
        'bootcamp': {'graduation_rate': 90, 'success_rate': 60, 'duration_weeks': 8},
        'mentorship': {'graduation_rate': 80, 'success_rate': 40, 'duration_weeks': 16}
    }

def _get_program_projections():
    """Obtiene proyecciones futuras de programas."""
    # Esto requeriría análisis más avanzado con ML
    return {
        'projected_growth': '15% anual',
        'emerging_trends': ['Remote-first programs', 'Industry-specific tracks', 'AI-enhanced learning'],
        'market_opportunities': ['Corporate innovation programs', 'Government partnerships']
    }