"""
Módulo de gestión de sesiones de mentoría para Aliados/Mentores.

Este módulo contiene todas las funcionalidades relacionadas con la gestión
integral de sesiones de mentoría, incluyendo programación, conducción, 
seguimiento, evaluación y análisis de efectividad de las sesiones.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import json
from enum import Enum

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, g, abort, make_response, session
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, case, extract, text
from sqlalchemy.orm import joinedload, subqueryload, contains_eager
from werkzeug.exceptions import BadRequest, Forbidden

from app.core.exceptions import ValidationError, BusinessLogicError, AuthorizationError
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, Meeting, 
    Project, Task, Message, Document, Notification, ActivityLog,
    Analytics, SessionObjective, SessionNote, SessionTemplate,
    SessionFeedback, MethodologyFramework, ActionItem
)
from app.forms.ally import (
    MentorshipSessionForm, SessionPreparationForm, SessionFeedbackForm,
    SessionObjectiveForm, SessionTemplateForm, SessionEvaluationForm,
    SessionSearchForm, ActionItemForm, MethodologySelectionForm
)
from app.services.mentorship_service import MentorshipService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.calendar_service import CalendarService
from app.services.google_meet import GoogleMeetService
from app.utils.decorators import require_json, rate_limit, validate_pagination
from app.utils.formatters import (
    format_currency, format_percentage, format_date, 
    format_time_duration, format_number, format_relative_time
)
from app.utils.export_utils import export_to_pdf, export_to_excel
from app.utils.cache_utils import cache_key, get_cached, set_cached
from app.utils.date_utils import parse_time, format_time_slot, get_timezone_offset
from app.views.ally import (
    require_ally_access, require_entrepreneur_access, 
    track_ally_activity, validate_mentorship_session
)


# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================

ally_mentorship_bp = Blueprint(
    'ally_mentorship',
    __name__,
    url_prefix='/ally/mentorship',
    template_folder='templates/ally/mentorship'
)

# Configuración de sesiones
DEFAULT_SESSION_DURATION = 60  # minutos
MIN_SESSION_DURATION = 30
MAX_SESSION_DURATION = 180
PREPARATION_TIME_BUFFER = 15  # minutos antes de la sesión

# Estados de sesión
class SessionStatus(Enum):
    SCHEDULED = 'scheduled'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    NO_SHOW = 'no_show'
    RESCHEDULED = 'rescheduled'


# ==================== VISTAS PRINCIPALES ====================

@ally_mentorship_bp.route('/')
@ally_mentorship_bp.route('/sessions')
@login_required
@require_ally_access
@track_ally_activity('mentorship_overview', 'Vista general de sesiones de mentoría')
@validate_pagination
def sessions_overview():
    """
    Vista general de sesiones de mentoría del aliado.
    
    Muestra dashboard con sesiones programadas, historial,
    métricas de efectividad y herramientas de gestión.
    
    Returns:
        Template con vista general de sesiones
    """
    try:
        ally_profile = g.ally_profile
        
        # Filtros y parámetros
        search_form = SessionSearchForm(request.args)
        view_mode = request.args.get('view', 'calendar')  # calendar, list, analytics
        period = request.args.get('period', '30')  # días
        
        # Calcular período
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=int(period))
        
        # Sesiones del período
        sessions_query = _build_sessions_query(ally_profile, search_form, start_date, end_date)
        
        # Paginación para vista de lista
        page = request.args.get('page', 1, type=int)
        sessions_paginated = sessions_query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Estadísticas generales
        mentorship_stats = _calculate_mentorship_overview_stats(ally_profile, start_date, end_date)
        
        # Próximas sesiones (siguientes 7 días)
        upcoming_sessions = _get_upcoming_sessions_detailed(ally_profile)
        
        # Sesiones que requieren acción
        sessions_requiring_action = _get_sessions_requiring_action(ally_profile)
        
        # Análisis de efectividad
        effectiveness_analysis = _analyze_mentorship_effectiveness(ally_profile, start_date, end_date)
        
        # Templates de sesiones más utilizados
        popular_templates = _get_popular_session_templates(ally_profile)
        
        # Métricas de tiempo y productividad
        time_analytics = _calculate_time_analytics(ally_profile, start_date, end_date)
        
        # Feedback reciente de emprendedores
        recent_feedback = _get_recent_session_feedback(ally_profile)
        
        # Calendario de disponibilidad
        availability_calendar = _generate_availability_calendar(ally_profile)
        
        # Recomendaciones para optimizar sesiones
        optimization_recommendations = _generate_session_optimization_recommendations(
            ally_profile, effectiveness_analysis
        )
        
        return render_template(
            'ally/mentorship/sessions_overview.html',
            sessions=sessions_paginated,
            mentorship_stats=mentorship_stats,
            upcoming_sessions=upcoming_sessions,
            sessions_requiring_action=sessions_requiring_action,
            effectiveness_analysis=effectiveness_analysis,
            popular_templates=popular_templates,
            time_analytics=time_analytics,
            recent_feedback=recent_feedback,
            availability_calendar=availability_calendar,
            optimization_recommendations=optimization_recommendations,
            search_form=search_form,
            view_mode=view_mode,
            current_period=period,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista general de mentoría: {str(e)}")
        flash('Error al cargar las sesiones de mentoría', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_mentorship_bp.route('/session/<int:session_id>')
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_detail', 'Vista detallada de sesión')
def session_detail(session_id):
    """
    Vista detallada de una sesión específica de mentoría.
    
    Muestra información completa de la sesión, objetivos,
    progreso, notas, feedback y herramientas de gestión.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Template con vista detallada de la sesión
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Información completa de la sesión
        session_data = _get_complete_session_data(session, ally_profile)
        
        # Objetivos de la sesión
        session_objectives = _get_session_objectives(session)
        
        # Notas y observaciones
        session_notes = _get_session_notes(session)
        
        # Items de acción derivados
        action_items = _get_session_action_items(session)
        
        # Feedback del emprendedor
        entrepreneur_feedback = _get_entrepreneur_session_feedback(session)
        
        # Métricas de la sesión
        session_metrics = _calculate_session_metrics(session)
        
        # Documentos compartidos en la sesión
        shared_documents = _get_session_documents(session)
        
        # Progreso hacia objetivos del emprendedor
        progress_tracking = _track_objective_progress(session)
        
        # Sesiones relacionadas (anteriores y siguientes)
        related_sessions = _get_related_sessions(session)
        
        # Recomendaciones para próxima sesión
        next_session_recommendations = _generate_next_session_recommendations(session)
        
        # Herramientas disponibles
        available_tools = _get_available_session_tools(session)
        
        # Análisis de efectividad específica
        session_effectiveness = _analyze_session_effectiveness(session)
        
        return render_template(
            'ally/mentorship/session_detail.html',
            session=session,
            session_data=session_data,
            session_objectives=session_objectives,
            session_notes=session_notes,
            action_items=action_items,
            entrepreneur_feedback=entrepreneur_feedback,
            session_metrics=session_metrics,
            shared_documents=shared_documents,
            progress_tracking=progress_tracking,
            related_sessions=related_sessions,
            next_session_recommendations=next_session_recommendations,
            available_tools=available_tools,
            session_effectiveness=session_effectiveness,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista detallada de sesión {session_id}: {str(e)}")
        flash('Error al cargar los detalles de la sesión', 'error')
        return redirect(url_for('ally_mentorship.sessions_overview'))


@ally_mentorship_bp.route('/schedule')
@login_required
@require_ally_access
@track_ally_activity('session_scheduling', 'Programación de sesión')
def schedule_session():
    """
    Vista para programar nueva sesión de mentoría.
    
    Proporciona formulario completo para programar sesiones
    con selección de emprendedor, fechas, objetivos y metodología.
    
    Returns:
        Template con formulario de programación
    """
    try:
        ally_profile = g.ally_profile
        
        # Formulario de programación
        scheduling_form = MentorshipSessionForm()
        
        # Emprendedores asignados disponibles
        available_entrepreneurs = _get_available_entrepreneurs(ally_profile)
        
        # Templates de sesiones disponibles
        session_templates = _get_session_templates(ally_profile)
        
        # Metodologías de mentoría disponibles
        available_methodologies = _get_available_methodologies()
        
        # Disponibilidad del aliado (próximos 30 días)
        availability_slots = _get_ally_availability_slots(ally_profile)
        
        # Configuraciones predeterminadas
        default_settings = _get_default_session_settings(ally_profile)
        
        # Próximas sesiones para evitar conflictos
        upcoming_sessions = _get_upcoming_sessions_calendar(ally_profile)
        
        return render_template(
            'ally/mentorship/schedule_session.html',
            scheduling_form=scheduling_form,
            available_entrepreneurs=available_entrepreneurs,
            session_templates=session_templates,
            available_methodologies=available_methodologies,
            availability_slots=availability_slots,
            default_settings=default_settings,
            upcoming_sessions=upcoming_sessions,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en programación de sesión: {str(e)}")
        flash('Error al cargar el formulario de programación', 'error')
        return redirect(url_for('ally_mentorship.sessions_overview'))


@ally_mentorship_bp.route('/session/<int:session_id>/prepare')
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_preparation', 'Preparación de sesión')
def prepare_session(session_id):
    """
    Vista de preparación para una sesión específica.
    
    Permite revisar información del emprendedor, establecer objetivos,
    seleccionar metodología y preparar materiales.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Template con herramientas de preparación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Validar que la sesión aún no ha comenzado
        if session.status not in ['scheduled', 'confirmed']:
            flash('Esta sesión ya no puede ser modificada', 'warning')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))
        
        # Formulario de preparación
        preparation_form = SessionPreparationForm(obj=session)
        
        # Información del emprendedor
        entrepreneur_context = _get_entrepreneur_context_for_session(session)
        
        # Historial de sesiones anteriores
        previous_sessions_summary = _get_previous_sessions_summary(session)
        
        # Progreso actual del emprendedor
        current_progress = _get_entrepreneur_current_progress(session.entrepreneur)
        
        # Objetivos sugeridos basados en contexto
        suggested_objectives = _generate_suggested_objectives(session, entrepreneur_context)
        
        # Recursos y materiales disponibles
        available_resources = _get_available_session_resources(session)
        
        # Metodologías recomendadas
        recommended_methodologies = _recommend_methodologies_for_session(session)
        
        # Checklist de preparación
        preparation_checklist = _generate_preparation_checklist(session)
        
        return render_template(
            'ally/mentorship/prepare_session.html',
            session=session,
            preparation_form=preparation_form,
            entrepreneur_context=entrepreneur_context,
            previous_sessions_summary=previous_sessions_summary,
            current_progress=current_progress,
            suggested_objectives=suggested_objectives,
            available_resources=available_resources,
            recommended_methodologies=recommended_methodologies,
            preparation_checklist=preparation_checklist,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en preparación de sesión {session_id}: {str(e)}")
        flash('Error al cargar la preparación de sesión', 'error')
        return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))


@ally_mentorship_bp.route('/session/<int:session_id>/conduct')
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_conduct', 'Conducción de sesión')
def conduct_session(session_id):
    """
    Vista para conducir una sesión de mentoría en tiempo real.
    
    Proporciona herramientas para tomar notas, marcar objetivos,
    crear items de acción y gestionar la sesión en vivo.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Template con herramientas de conducción en vivo
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Validar que la sesión puede ser conducida
        if session.status not in ['confirmed', 'in_progress']:
            flash('Esta sesión no está disponible para conducir', 'warning')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))
        
        # Marcar sesión como en progreso si no lo está
        if session.status == 'confirmed':
            session.status = 'in_progress'
            session.actual_start_time = datetime.utcnow()
            db.session.commit()
        
        # Objetivos de la sesión
        session_objectives = _get_session_objectives_for_conduct(session)
        
        # Notas en tiempo real
        live_notes = _get_live_session_notes(session)
        
        # Herramientas de conducción
        conduct_tools = _get_session_conduct_tools(session)
        
        # Información rápida del emprendedor
        entrepreneur_quick_info = _get_entrepreneur_quick_info(session.entrepreneur)
        
        # Timer y gestión de tiempo
        time_management = _get_session_time_management(session)
        
        # Templates de notas rápidas
        quick_note_templates = _get_quick_note_templates()
        
        # Metodología seleccionada
        selected_methodology = _get_session_methodology(session)
        
        # Enlaces de reunión (Google Meet, Zoom, etc.)
        meeting_links = _get_session_meeting_links(session)
        
        return render_template(
            'ally/mentorship/conduct_session.html',
            session=session,
            session_objectives=session_objectives,
            live_notes=live_notes,
            conduct_tools=conduct_tools,
            entrepreneur_quick_info=entrepreneur_quick_info,
            time_management=time_management,
            quick_note_templates=quick_note_templates,
            selected_methodology=selected_methodology,
            meeting_links=meeting_links,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en conducción de sesión {session_id}: {str(e)}")
        flash('Error al iniciar la conducción de sesión', 'error')
        return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))


@ally_mentorship_bp.route('/session/<int:session_id>/complete')
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_completion', 'Finalización de sesión')
def complete_session(session_id):
    """
    Vista para completar y evaluar una sesión de mentoría.
    
    Permite cerrar la sesión, evaluar efectividad,
    crear resumen y planificar seguimiento.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Template con herramientas de finalización
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Validar que la sesión puede ser completada
        if session.status not in ['in_progress', 'confirmed']:
            flash('Esta sesión no puede ser completada en este momento', 'warning')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))
        
        # Formulario de evaluación
        evaluation_form = SessionEvaluationForm()
        
        # Formulario de feedback
        feedback_form = SessionFeedbackForm()
        
        # Resumen de la sesión
        session_summary = _generate_session_summary(session)
        
        # Objetivos alcanzados vs planificados
        objectives_assessment = _assess_session_objectives(session)
        
        # Items de acción pendientes
        pending_action_items = _get_pending_action_items(session)
        
        # Métricas preliminares
        preliminary_metrics = _calculate_preliminary_session_metrics(session)
        
        # Sugerencias para próxima sesión
        next_session_suggestions = _generate_next_session_suggestions(session)
        
        # Template de follow-up
        followup_templates = _get_followup_templates()
        
        return render_template(
            'ally/mentorship/complete_session.html',
            session=session,
            evaluation_form=evaluation_form,
            feedback_form=feedback_form,
            session_summary=session_summary,
            objectives_assessment=objectives_assessment,
            pending_action_items=pending_action_items,
            preliminary_metrics=preliminary_metrics,
            next_session_suggestions=next_session_suggestions,
            followup_templates=followup_templates,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en finalización de sesión {session_id}: {str(e)}")
        flash('Error al cargar la finalización de sesión', 'error')
        return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))


@ally_mentorship_bp.route('/analytics')
@login_required
@require_ally_access
@track_ally_activity('mentorship_analytics', 'Analytics de mentoría')
def mentorship_analytics():
    """
    Vista de analytics avanzados de mentoría.
    
    Muestra métricas detalladas, tendencias, efectividad
    y insights para optimizar las sesiones de mentoría.
    
    Returns:
        Template con analytics de mentoría
    """
    try:
        ally_profile = g.ally_profile
        
        # Período de análisis
        period = request.args.get('period', '90')
        analysis_type = request.args.get('type', 'overview')
        
        # Calcular fechas
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=int(period))
        
        # Usar servicio de analytics
        analytics_service = AnalyticsService()
        
        # Métricas generales de mentoría
        general_metrics = analytics_service.get_mentorship_metrics(
            ally_profile.id, start_date, end_date
        )
        
        # Análisis de efectividad
        effectiveness_analysis = analytics_service.analyze_mentorship_effectiveness(
            ally_profile.id, start_date, end_date
        )
        
        # Tendencias temporales
        temporal_trends = analytics_service.get_mentorship_trends(
            ally_profile.id, start_date, end_date
        )
        
        # Análisis por emprendedor
        entrepreneur_analysis = _analyze_mentorship_by_entrepreneur(ally_profile, start_date, end_date)
        
        # Análisis de metodologías
        methodology_effectiveness = _analyze_methodology_effectiveness(ally_profile, start_date, end_date)
        
        # Patrones de sesiones exitosas
        success_patterns = _identify_success_patterns(ally_profile, start_date, end_date)
        
        # ROI de tiempo invertido
        time_investment_roi = _calculate_time_investment_roi(ally_profile, start_date, end_date)
        
        # Benchmarks y comparativas
        benchmarks = _get_mentorship_benchmarks(ally_profile, start_date, end_date)
        
        # Recomendaciones de optimización
        optimization_insights = _generate_optimization_insights(
            ally_profile, general_metrics, effectiveness_analysis
        )
        
        # Datos para gráficos
        charts_data = _prepare_mentorship_charts_data(ally_profile, start_date, end_date)
        
        return render_template(
            'ally/mentorship/analytics.html',
            general_metrics=general_metrics,
            effectiveness_analysis=effectiveness_analysis,
            temporal_trends=temporal_trends,
            entrepreneur_analysis=entrepreneur_analysis,
            methodology_effectiveness=methodology_effectiveness,
            success_patterns=success_patterns,
            time_investment_roi=time_investment_roi,
            benchmarks=benchmarks,
            optimization_insights=optimization_insights,
            charts_data=charts_data,
            current_period=period,
            analysis_type=analysis_type,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics de mentoría: {str(e)}")
        flash('Error al cargar analytics de mentoría', 'error')
        return redirect(url_for('ally_mentorship.sessions_overview'))


@ally_mentorship_bp.route('/templates')
@login_required
@require_ally_access
@track_ally_activity('session_templates', 'Gestión de templates de sesión')
def session_templates():
    """
    Vista de gestión de templates de sesiones.
    
    Permite crear, editar y gestionar templates reutilizables
    para diferentes tipos de sesiones de mentoría.
    
    Returns:
        Template con gestión de templates
    """
    try:
        ally_profile = g.ally_profile
        
        # Templates personalizados del aliado
        custom_templates = _get_custom_session_templates(ally_profile)
        
        # Templates públicos disponibles
        public_templates = _get_public_session_templates()
        
        # Estadísticas de uso de templates
        template_usage_stats = _calculate_template_usage_stats(ally_profile)
        
        # Formulario para nuevo template
        template_form = SessionTemplateForm()
        
        # Categorías de templates
        template_categories = _get_template_categories()
        
        return render_template(
            'ally/mentorship/templates.html',
            custom_templates=custom_templates,
            public_templates=public_templates,
            template_usage_stats=template_usage_stats,
            template_form=template_form,
            template_categories=template_categories,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en templates de sesión: {str(e)}")
        flash('Error al cargar templates de sesión', 'error')
        return redirect(url_for('ally_mentorship.sessions_overview'))


# ==================== PROCESAMIENTO DE FORMULARIOS ====================

@ally_mentorship_bp.route('/schedule', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('session_create', 'Creación de sesión de mentoría')
def create_session():
    """
    Procesa la creación de una nueva sesión de mentoría.
    
    Valida datos, verifica disponibilidad, crea la sesión
    y envía notificaciones correspondientes.
    
    Returns:
        Redirección con mensaje de confirmación o error
    """
    try:
        ally_profile = g.ally_profile
        form = MentorshipSessionForm()
        
        if not form.validate_on_submit():
            flash('Error en los datos del formulario', 'error')
            return redirect(url_for('ally_mentorship.schedule_session'))
        
        # Datos de la sesión
        session_data = {
            'entrepreneur_id': form.entrepreneur_id.data,
            'ally_id': ally_profile.id,
            'session_date': form.session_date.data,
            'start_time': form.start_time.data,
            'duration_hours': form.duration_hours.data,
            'topic': form.topic.data,
            'objectives': form.objectives.data.split('\n') if form.objectives.data else [],
            'session_type': form.session_type.data,
            'methodology': form.methodology.data,
            'location': form.location.data,
            'preparation_notes': form.preparation_notes.data,
            'resources_needed': form.resources_needed.data.split('\n') if form.resources_needed.data else [],
            'is_recurring': form.is_recurring.data,
            'recurrence_pattern': form.recurrence_pattern.data if form.is_recurring.data else None
        }
        
        # Usar servicio de mentoría
        mentorship_service = MentorshipService()
        result = mentorship_service.create_session(session_data)
        
        if result['success']:
            session = result['session']
            
            # Crear enlace de reunión si es virtual
            if session_data['location'] == 'virtual':
                _create_meeting_link(session)
            
            # Enviar notificaciones
            _send_session_notifications(session, 'created')
            
            # Crear recordatorios automáticos
            _schedule_session_reminders(session)
            
            # Registrar actividad
            _log_session_created(session, ally_profile)
            
            flash('Sesión de mentoría creada exitosamente', 'success')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session.id))
        else:
            flash(f'Error creando sesión: {result["error"]}', 'error')
            return redirect(url_for('ally_mentorship.schedule_session'))
            
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(url_for('ally_mentorship.schedule_session'))
    except Exception as e:
        current_app.logger.error(f"Error creando sesión: {str(e)}")
        flash('Error interno al crear sesión', 'error')
        return redirect(url_for('ally_mentorship.schedule_session'))


@ally_mentorship_bp.route('/session/<int:session_id>/prepare', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_prepare', 'Preparación completada')
def save_session_preparation(session_id):
    """
    Guarda la preparación de una sesión específica.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Redirección con confirmación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        form = SessionPreparationForm()
        
        if form.validate_on_submit():
            # Actualizar datos de preparación
            session.prepared_objectives = form.objectives.data
            session.selected_methodology = form.methodology.data
            session.preparation_notes = form.preparation_notes.data
            session.resources_prepared = form.resources.data
            session.estimated_duration = form.estimated_duration.data
            session.preparation_completed = True
            session.prepared_at = datetime.utcnow()
            session.prepared_by = ally_profile.user_id
            
            # Crear objetivos específicos si se proporcionan
            if form.specific_objectives.data:
                _create_session_objectives(session, form.specific_objectives.data)
            
            db.session.commit()
            
            # Registrar preparación completada
            _log_session_preparation(session, ally_profile)
            
            flash('Preparación de sesión guardada exitosamente', 'success')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))
        else:
            flash('Error en los datos de preparación', 'error')
            return redirect(url_for('ally_mentorship.prepare_session', session_id=session_id))
            
    except Exception as e:
        current_app.logger.error(f"Error guardando preparación: {str(e)}")
        db.session.rollback()
        flash('Error al guardar preparación', 'error')
        return redirect(url_for('ally_mentorship.prepare_session', session_id=session_id))


@ally_mentorship_bp.route('/session/<int:session_id>/complete', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_complete', 'Sesión completada')
def finalize_session(session_id):
    """
    Finaliza una sesión de mentoría con evaluación.
    
    Args:
        session_id: ID de la sesión de mentoría
        
    Returns:
        Redirección con confirmación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        evaluation_form = SessionEvaluationForm()
        feedback_form = SessionFeedbackForm()
        
        if evaluation_form.validate_on_submit():
            # Completar sesión
            session.status = 'completed'
            session.actual_end_time = datetime.utcnow()
            session.actual_duration = (session.actual_end_time - session.actual_start_time).total_seconds() / 3600
            
            # Guardar evaluación
            session.ally_rating = evaluation_form.ally_rating.data
            session.session_effectiveness = evaluation_form.effectiveness_rating.data
            session.objectives_achieved = evaluation_form.objectives_achieved.data
            session.key_insights = evaluation_form.key_insights.data
            session.challenges_faced = evaluation_form.challenges_faced.data
            session.session_summary = evaluation_form.session_summary.data
            session.next_steps = evaluation_form.next_steps.data
            session.follow_up_required = evaluation_form.follow_up_required.data
            session.follow_up_date = evaluation_form.follow_up_date.data
            
            # Crear items de acción si se especifican
            if evaluation_form.action_items.data:
                _create_action_items(session, evaluation_form.action_items.data)
            
            # Programar próxima sesión si se indica
            if evaluation_form.schedule_next_session.data:
                _schedule_next_session(session, evaluation_form.next_session_date.data)
            
            db.session.commit()
            
            # Enviar notificaciones de finalización
            _send_session_notifications(session, 'completed')
            
            # Solicitar feedback al emprendedor
            _request_entrepreneur_feedback(session)
            
            # Registrar finalización
            _log_session_completed(session, ally_profile)
            
            flash('Sesión completada y evaluada exitosamente', 'success')
            return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))
        else:
            flash('Error en la evaluación de la sesión', 'error')
            return redirect(url_for('ally_mentorship.complete_session', session_id=session_id))
            
    except Exception as e:
        current_app.logger.error(f"Error finalizando sesión: {str(e)}")
        db.session.rollback()
        flash('Error al finalizar sesión', 'error')
        return redirect(url_for('ally_mentorship.complete_session', session_id=session_id))


# ==================== API ENDPOINTS ====================

@ally_mentorship_bp.route('/api/sessions/stats')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_sessions_stats():
    """
    API endpoint para estadísticas de sesiones en tiempo real.
    
    Returns:
        JSON con estadísticas actualizadas
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar cache
        cache_key_val = f"ally_sessions_stats_{ally_profile.id}"
        cached_stats = get_cached(cache_key_val)
        
        if cached_stats:
            return jsonify({
                'success': True,
                'data': cached_stats,
                'cached': True
            })
        
        # Calcular estadísticas
        period = request.args.get('period', '30')
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=int(period))
        
        stats = _calculate_mentorship_overview_stats(ally_profile, start_date, end_date)
        
        # Cachear por 5 minutos
        set_cached(cache_key_val, stats, timeout=300)
        
        return jsonify({
            'success': True,
            'data': stats,
            'cached': False
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API de estadísticas de sesiones: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/session/<int:session_id>/start', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@rate_limit(calls=10, period=60)
@require_json
def api_start_session(session_id):
    """
    API endpoint para iniciar una sesión de mentoría.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Validar que la sesión puede iniciarse
        if session.status not in ['scheduled', 'confirmed']:
            return jsonify({'error': 'La sesión no puede ser iniciada en este momento'}), 400
        
        # Iniciar sesión
        session.status = 'in_progress'
        session.actual_start_time = datetime.utcnow()
        
        db.session.commit()
        
        # Notificar inicio
        _send_session_notifications(session, 'started')
        
        # Registrar inicio
        _log_session_started(session, ally_profile)
        
        return jsonify({
            'success': True,
            'message': 'Sesión iniciada exitosamente',
            'session_status': session.status,
            'start_time': session.actual_start_time.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error iniciando sesión: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/session/<int:session_id>/add-note', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@rate_limit(calls=30, period=60)
@require_json
def api_add_session_note(session_id):
    """
    API endpoint para agregar nota durante la sesión.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        data = request.get_json()
        
        note_content = data.get('content', '').strip()
        note_type = data.get('type', 'general')  # general, insight, concern, action
        timestamp = data.get('timestamp', datetime.utcnow().isoformat())
        
        if not note_content:
            return jsonify({'error': 'Contenido de la nota es requerido'}), 400
        
        # Crear nota de sesión
        note = SessionNote(
            session_id=session.id,
            author_id=ally_profile.user_id,
            content=note_content,
            note_type=note_type,
            timestamp=datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
            is_private=data.get('is_private', False)
        )
        
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Nota agregada exitosamente',
            'note': {
                'id': note.id,
                'content': note.content,
                'type': note.note_type,
                'timestamp': note.timestamp.isoformat(),
                'author': ally_profile.user.full_name
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error agregando nota: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/session/<int:session_id>/update-objective', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@rate_limit(calls=20, period=60)
@require_json
def api_update_session_objective(session_id):
    """
    API endpoint para actualizar estado de objetivo de sesión.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        data = request.get_json()
        
        objective_id = data.get('objective_id')
        new_status = data.get('status')  # pending, in_progress, completed, deferred
        progress_percentage = data.get('progress', 0)
        notes = data.get('notes', '')
        
        # Validar objetivo
        objective = SessionObjective.query.filter_by(
            id=objective_id,
            session_id=session.id
        ).first()
        
        if not objective:
            return jsonify({'error': 'Objetivo no encontrado'}), 404
        
        # Actualizar objetivo
        objective.status = new_status
        objective.progress_percentage = progress_percentage
        objective.notes = notes
        objective.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Objetivo actualizado exitosamente',
            'objective': {
                'id': objective.id,
                'status': objective.status,
                'progress': objective.progress_percentage
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error actualizando objetivo: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/session/<int:session_id>/add-action-item', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@rate_limit(calls=15, period=60)
@require_json
def api_add_action_item(session_id):
    """
    API endpoint para agregar item de acción durante la sesión.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        data = request.get_json()
        
        description = data.get('description', '').strip()
        assigned_to = data.get('assigned_to', 'entrepreneur')  # entrepreneur, ally, both
        due_date = data.get('due_date')
        priority = data.get('priority', 'medium')  # low, medium, high
        
        if not description:
            return jsonify({'error': 'Descripción del item es requerida'}), 400
        
        # Crear item de acción
        action_item = ActionItem(
            session_id=session.id,
            description=description,
            assigned_to=assigned_to,
            due_date=datetime.fromisoformat(due_date) if due_date else None,
            priority=priority,
            status='pending',
            created_by=ally_profile.user_id
        )
        
        db.session.add(action_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item de acción agregado exitosamente',
            'action_item': {
                'id': action_item.id,
                'description': action_item.description,
                'assigned_to': action_item.assigned_to,
                'due_date': action_item.due_date.isoformat() if action_item.due_date else None,
                'priority': action_item.priority
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error agregando item de acción: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/availability')
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
@require_json
def api_get_availability():
    """
    API endpoint para obtener disponibilidad del aliado.
    
    Returns:
        JSON con slots de disponibilidad
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        duration = request.args.get('duration', 60, type=int)  # minutos
        
        if not start_date or not end_date:
            return jsonify({'error': 'Fechas de inicio y fin son requeridas'}), 400
        
        # Parsear fechas
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        # Obtener disponibilidad
        availability_slots = _calculate_availability_slots(ally_profile, start, end, duration)
        
        return jsonify({
            'success': True,
            'data': {
                'slots': availability_slots,
                'total_slots': len(availability_slots),
                'duration_minutes': duration
            }
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error obteniendo disponibilidad: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_mentorship_bp.route('/api/session/<int:session_id>/reschedule', methods=['POST'])
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@rate_limit(calls=5, period=60)
@require_json
def api_reschedule_session(session_id):
    """
    API endpoint para reprogramar una sesión.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        data = request.get_json()
        
        # Validar que la sesión puede reprogramarse
        if session.status not in ['scheduled', 'confirmed']:
            return jsonify({'error': 'Esta sesión no puede ser reprogramada'}), 400
        
        new_date = data.get('new_date')
        new_time = data.get('new_time')
        reason = data.get('reason', '').strip()
        
        if not new_date or not new_time:
            return jsonify({'error': 'Nueva fecha y hora son requeridas'}), 400
        
        # Parsear nueva fecha y hora
        new_session_date = datetime.strptime(new_date, '%Y-%m-%d').date()
        new_start_time = datetime.strptime(new_time, '%H:%M').time()
        new_datetime = datetime.combine(new_session_date, new_start_time)
        
        # Validar disponibilidad
        if not _check_availability_for_reschedule(ally_profile, new_datetime, session.duration_hours):
            return jsonify({'error': 'No hay disponibilidad en la nueva fecha/hora'}), 400
        
        # Guardar datos anteriores
        old_date = session.session_date
        old_time = session.start_time
        
        # Reprogramar
        session.session_date = new_session_date
        session.start_time = new_start_time
        session.status = 'rescheduled'
        session.reschedule_reason = reason
        session.rescheduled_at = datetime.utcnow()
        session.rescheduled_by = ally_profile.user_id
        
        db.session.commit()
        
        # Notificar reprogramación
        _send_session_notifications(session, 'rescheduled', {
            'old_date': old_date,
            'old_time': old_time,
            'new_date': new_session_date,
            'new_time': new_start_time,
            'reason': reason
        })
        
        # Registrar reprogramación
        _log_session_rescheduled(session, ally_profile, reason)
        
        return jsonify({
            'success': True,
            'message': 'Sesión reprogramada exitosamente',
            'new_datetime': new_datetime.isoformat(),
            'old_datetime': datetime.combine(old_date, old_time).isoformat()
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha u hora no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error reprogramando sesión: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== EXPORTACIÓN Y REPORTES ====================

@ally_mentorship_bp.route('/export/sessions-report')
@login_required
@require_ally_access
@track_ally_activity('sessions_export', 'Exportación de reporte de sesiones')
def export_sessions_report():
    """
    Exporta reporte completo de sesiones de mentoría.
    
    Returns:
        Archivo PDF o Excel con reporte de sesiones
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de exportación
        format_type = request.args.get('format', 'pdf')  # pdf, excel
        period = request.args.get('period', '90')  # días
        include_details = request.args.get('details', 'summary')  # summary, detailed, complete
        
        # Calcular período
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=int(period))
        
        # Generar datos del reporte
        report_data = _generate_sessions_report_data(
            ally_profile, start_date, end_date, include_details
        )
        
        if format_type == 'pdf':
            # Generar PDF
            pdf_content = export_to_pdf(
                template='reports/ally_sessions_report.html',
                data=report_data,
                filename=f'sesiones_mentoria_{ally_profile.user.first_name}_{ally_profile.user.last_name}'
            )
            
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename=reporte_sesiones_mentoria.pdf'
            
            return response
            
        elif format_type == 'excel':
            # Generar Excel
            excel_content = export_to_excel(
                data=report_data,
                filename=f'sesiones_mentoria_{datetime.now().strftime("%Y%m%d")}'
            )
            
            response = make_response(excel_content)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = 'attachment; filename=reporte_sesiones_mentoria.xlsx'
            
            return response
        
        else:
            flash('Formato de exportación no válido', 'error')
            return redirect(url_for('ally_mentorship.sessions_overview'))
            
    except Exception as e:
        current_app.logger.error(f"Error exportando reporte: {str(e)}")
        flash('Error al generar el reporte', 'error')
        return redirect(url_for('ally_mentorship.sessions_overview'))


@ally_mentorship_bp.route('/export/session/<int:session_id>/summary')
@login_required
@require_ally_access
@validate_mentorship_session('session_id')
@track_ally_activity('session_summary_export', 'Exportación de resumen de sesión')
def export_session_summary(session_id):
    """
    Exporta resumen detallado de una sesión específica.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        Archivo PDF con resumen de la sesión
    """
    try:
        ally_profile = g.ally_profile
        session = g.mentorship_session
        
        # Generar datos del resumen
        summary_data = _generate_session_summary_report(session, ally_profile)
        
        # Generar PDF
        pdf_content = export_to_pdf(
            template='reports/session_summary_report.html',
            data=summary_data,
            filename=f'resumen_sesion_{session.id}_{session.session_date}'
        )
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=resumen_sesion_{session.id}.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando resumen: {str(e)}")
        flash('Error al generar el resumen', 'error')
        return redirect(url_for('ally_mentorship.session_detail', session_id=session_id))


# ==================== FUNCIONES AUXILIARES ====================

def _build_sessions_query(ally: Ally, search_form: SessionSearchForm, start_date: datetime, end_date: datetime):
    """
    Construye query base para sesiones con filtros aplicados.
    
    Args:
        ally: Perfil del aliado
        search_form: Formulario con filtros
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Query de sesiones filtrada
    """
    query = MentorshipSession.query.filter_by(ally_id=ally.id).options(
        joinedload(MentorshipSession.entrepreneur).joinedload(Entrepreneur.user),
        joinedload(MentorshipSession.objectives),
        joinedload(MentorshipSession.notes)
    )
    
    # Filtro por período
    query = query.filter(
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    )
    
    # Aplicar filtros del formulario
    if search_form.status.data and search_form.status.data != 'all':
        query = query.filter(MentorshipSession.status == search_form.status.data)
    
    if search_form.entrepreneur.data and search_form.entrepreneur.data != 'all':
        query = query.filter(MentorshipSession.entrepreneur_id == search_form.entrepreneur.data)
    
    if search_form.session_type.data and search_form.session_type.data != 'all':
        query = query.filter(MentorshipSession.session_type == search_form.session_type.data)
    
    if search_form.methodology.data and search_form.methodology.data != 'all':
        query = query.filter(MentorshipSession.methodology == search_form.methodology.data)
    
    if search_form.search_term.data:
        search_term = f"%{search_form.search_term.data}%"
        query = query.filter(
            or_(
                MentorshipSession.topic.ilike(search_term),
                MentorshipSession.session_summary.ilike(search_term),
                MentorshipSession.key_insights.ilike(search_term)
            )
        )
    
    return query.order_by(desc(MentorshipSession.session_date))


def _calculate_mentorship_overview_stats(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Calcula estadísticas generales de mentoría del aliado.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con estadísticas generales
    """
    # Sesiones totales en el período
    total_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).count()
    
    # Sesiones completadas
    completed_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).count()
    
    # Horas totales de mentoría
    total_hours = db.session.query(
        func.sum(MentorshipSession.actual_duration)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).scalar() or 0
    
    # Promedio de efectividad
    avg_effectiveness = db.session.query(
        func.avg(MentorshipSession.session_effectiveness)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.session_effectiveness.isnot(None)
    ).scalar() or 0
    
    # Tasa de completitud
    completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Distribución por estado
    status_distribution = db.session.query(
        MentorshipSession.status,
        func.count(MentorshipSession.id)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).group_by(MentorshipSession.status).all()
    
    # Emprendedores únicos atendidos
    unique_entrepreneurs = db.session.query(
        MentorshipSession.entrepreneur_id
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).distinct().count()
    
    # Próximas sesiones programadas
    upcoming_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date > datetime.utcnow().date(),
        MentorshipSession.status.in_(['scheduled', 'confirmed'])
    ).count()
    
    return {
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'cancelled_sessions': dict(status_distribution).get('cancelled', 0),
        'upcoming_sessions': upcoming_sessions,
        'total_hours': float(total_hours),
        'avg_session_duration': float(total_hours / completed_sessions) if completed_sessions > 0 else 0,
        'completion_rate': round(completion_rate, 1),
        'avg_effectiveness': round(float(avg_effectiveness), 1),
        'unique_entrepreneurs': unique_entrepreneurs,
        'status_distribution': dict(status_distribution),
        'period_days': (end_date - start_date).days
    }


def _get_upcoming_sessions_detailed(ally: Ally, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obtiene próximas sesiones con información detallada.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de sesiones
        
    Returns:
        Lista de próximas sesiones detalladas
    """
    upcoming_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= datetime.utcnow().date(),
        MentorshipSession.status.in_(['scheduled', 'confirmed'])
    ).options(
        joinedload(MentorshipSession.entrepreneur).joinedload(Entrepreneur.user)
    ).order_by(MentorshipSession.session_date, MentorshipSession.start_time).limit(limit).all()
    
    sessions_detailed = []
    for session in upcoming_sessions:
        # Tiempo hasta la sesión
        session_datetime = datetime.combine(session.session_date, session.start_time or datetime.min.time())
        time_until_session = session_datetime - datetime.utcnow()
        
        # Estado de preparación
        preparation_status = _get_session_preparation_status(session)
        
        sessions_detailed.append({
            'session': session,
            'entrepreneur_name': session.entrepreneur.user.full_name,
            'time_until_session': time_until_session,
            'time_until_formatted': format_relative_time(session_datetime),
            'preparation_status': preparation_status,
            'is_today': session.session_date == datetime.utcnow().date(),
            'is_urgent': time_until_session.total_seconds() < 3600,  # menos de 1 hora
            'meeting_link': _get_session_meeting_link(session)
        })
    
    return sessions_detailed


def _get_sessions_requiring_action(ally: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene sesiones que requieren alguna acción del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de sesiones que requieren acción
    """
    sessions_requiring_action = []
    
    # Sesiones sin preparar próximas a ocurrir (dentro de 24 horas)
    tomorrow = datetime.utcnow().date() + timedelta(days=1)
    unprepared_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date <= tomorrow,
        MentorshipSession.status.in_(['scheduled', 'confirmed']),
        MentorshipSession.preparation_completed == False
    ).all()
    
    for session in unprepared_sessions:
        sessions_requiring_action.append({
            'session': session,
            'action_type': 'prepare',
            'urgency': 'high',
            'message': 'Sesión requiere preparación',
            'action_url': url_for('ally_mentorship.prepare_session', session_id=session.id)
        })
    
    # Sesiones completadas sin feedback
    completed_sessions_no_feedback = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.status == 'completed',
        MentorshipSession.session_effectiveness.is_(None),
        MentorshipSession.actual_end_time >= datetime.utcnow() - timedelta(days=7)
    ).all()
    
    for session in completed_sessions_no_feedback:
        sessions_requiring_action.append({
            'session': session,
            'action_type': 'evaluate',
            'urgency': 'medium',
            'message': 'Sesión pendiente de evaluación',
            'action_url': url_for('ally_mentorship.complete_session', session_id=session.id)
        })
    
    # Sesiones que requieren seguimiento
    sessions_needing_followup = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.follow_up_required == True,
        MentorshipSession.follow_up_completed == False,
        MentorshipSession.follow_up_date <= datetime.utcnow().date()
    ).all()
    
    for session in sessions_needing_followup:
        sessions_requiring_action.append({
            'session': session,
            'action_type': 'follow_up',
            'urgency': 'medium',
            'message': 'Seguimiento pendiente',
            'action_url': url_for('ally_mentorship.session_detail', session_id=session.id)
        })
    
    return sorted(sessions_requiring_action, key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['urgency']], reverse=True)


def _analyze_mentorship_effectiveness(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Analiza la efectividad general de la mentoría del aliado.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con análisis de efectividad
    """
    # Sesiones completadas con rating de efectividad
    completed_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed',
        MentorshipSession.session_effectiveness.isnot(None)
    ).all()
    
    if not completed_sessions:
        return {
            'overall_effectiveness': 0,
            'trend': 'neutral',
            'effectiveness_distribution': {},
            'top_performing_areas': [],
            'improvement_areas': [],
            'satisfaction_correlation': 0
        }
    
    # Promedio de efectividad
    effectiveness_scores = [s.session_effectiveness for s in completed_sessions]
    overall_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)
    
    # Distribución de scores
    effectiveness_distribution = {
        'excellent': len([s for s in effectiveness_scores if s >= 4.5]),
        'good': len([s for s in effectiveness_scores if 3.5 <= s < 4.5]),
        'fair': len([s for s in effectiveness_scores if 2.5 <= s < 3.5]),
        'poor': len([s for s in effectiveness_scores if s < 2.5])
    }
    
    # Tendencia (comparar primera mitad vs segunda mitad del período)
    mid_date = start_date + (end_date - start_date) / 2
    first_half_avg = _calculate_period_effectiveness(ally, start_date, mid_date)
    second_half_avg = _calculate_period_effectiveness(ally, mid_date, end_date)
    
    if second_half_avg > first_half_avg * 1.1:
        trend = 'improving'
    elif second_half_avg < first_half_avg * 0.9:
        trend = 'declining'
    else:
        trend = 'stable'
    
    # Áreas de mejor rendimiento (por tipo de sesión)
    top_performing_areas = _identify_top_performing_session_types(ally, start_date, end_date)
    
    # Áreas de mejora
    improvement_areas = _identify_improvement_areas_sessions(ally, start_date, end_date)
    
    return {
        'overall_effectiveness': round(overall_effectiveness, 2),
        'trend': trend,
        'effectiveness_distribution': effectiveness_distribution,
        'total_evaluated_sessions': len(completed_sessions),
        'top_performing_areas': top_performing_areas,
        'improvement_areas': improvement_areas,
        'first_half_avg': round(first_half_avg, 2),
        'second_half_avg': round(second_half_avg, 2)
    }


def _get_popular_session_templates(ally: Ally, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtiene templates de sesiones más utilizados por el aliado.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de templates
        
    Returns:
        Lista de templates populares
    """
    # Esto requeriría un modelo SessionTemplate y tracking de uso
    # Por ahora retornamos datos simulados
    return [
        {
            'id': 1,
            'name': 'Sesión de Diagnóstico Inicial',
            'usage_count': 15,
            'avg_effectiveness': 4.2,
            'category': 'onboarding'
        },
        {
            'id': 2,
            'name': 'Revisión de Progreso Mensual',
            'usage_count': 12,
            'avg_effectiveness': 4.0,
            'category': 'follow_up'
        },
        {
            'id': 3,
            'name': 'Planificación Estratégica',
            'usage_count': 8,
            'avg_effectiveness': 4.3,
            'category': 'planning'
        }
    ]


def _calculate_time_analytics(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Calcula analytics de tiempo y productividad.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con analytics de tiempo
    """
    completed_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).all()
    
    if not completed_sessions:
        return {
            'total_time_invested': 0,
            'avg_session_duration': 0,
            'time_efficiency': 0,
            'peak_hours': [],
            'peak_days': []
        }
    
    # Tiempo total invertido
    total_time = sum(s.actual_duration or 0 for s in completed_sessions)
    
    # Duración promedio
    avg_duration = total_time / len(completed_sessions)
    
    # Eficiencia de tiempo (duración real vs planificada)
    planned_durations = [s.duration_hours for s in completed_sessions if s.duration_hours]
    actual_durations = [s.actual_duration for s in completed_sessions if s.actual_duration]
    
    if planned_durations and actual_durations:
        efficiency = (sum(planned_durations) / sum(actual_durations)) * 100
    else:
        efficiency = 100
    
    # Análisis de horarios pico
    hour_distribution = defaultdict(int)
    day_distribution = defaultdict(int)
    
    for session in completed_sessions:
        if session.actual_start_time:
            hour_distribution[session.actual_start_time.hour] += 1
            day_distribution[session.session_date.strftime('%A')] += 1
    
    # Obtener horas y días más productivos
    peak_hours = sorted(hour_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_days = sorted(day_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        'total_time_invested': round(total_time, 2),
        'avg_session_duration': round(avg_duration, 2),
        'time_efficiency': round(efficiency, 1),
        'peak_hours': [{'hour': h, 'count': c} for h, c in peak_hours],
        'peak_days': [{'day': d, 'count': c} for d, c in peak_days],
        'sessions_analyzed': len(completed_sessions)
    }


def _get_recent_session_feedback(ally: Ally, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtiene feedback reciente de emprendedores sobre sesiones.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de feedback
        
    Returns:
        Lista de feedback reciente
    """
    # Esto requeriría un modelo SessionFeedback
    # Por ahora retornamos datos simulados
    return [
        {
            'session_id': 1,
            'entrepreneur_name': 'Ana García',
            'rating': 5,
            'comment': 'Excelente sesión, muy útil para clarificar mi estrategia de marketing',
            'created_at': datetime.utcnow() - timedelta(days=2)
        },
        {
            'session_id': 2,
            'entrepreneur_name': 'Carlos López',
            'rating': 4,
            'comment': 'Buena orientación sobre finanzas, me ayudó mucho',
            'created_at': datetime.utcnow() - timedelta(days=5)
        }
    ]


def _generate_availability_calendar(ally: Ally) -> Dict[str, Any]:
    """
    Genera calendario de disponibilidad del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con calendario de disponibilidad
    """
    # Implementación básica - requiere modelo de disponibilidad
    return {
        'next_30_days': [],
        'recurring_slots': [],
        'blocked_dates': [],
        'preferred_times': ['09:00', '14:00', '16:00']
    }


def _generate_session_optimization_recommendations(ally: Ally, effectiveness_analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Genera recomendaciones para optimizar sesiones.
    
    Args:
        ally: Perfil del aliado
        effectiveness_analysis: Análisis de efectividad
        
    Returns:
        Lista de recomendaciones
    """
    recommendations = []
    
    if effectiveness_analysis['overall_effectiveness'] < 3.5:
        recommendations.append({
            'type': 'improvement',
            'title': 'Mejorar preparación de sesiones',
            'description': 'Considera dedicar más tiempo a la preparación previa de cada sesión',
            'priority': 'high'
        })
    
    if effectiveness_analysis['trend'] == 'declining':
        recommendations.append({
            'type': 'attention',
            'title': 'Tendencia descendente detectada',
            'description': 'La efectividad ha disminuido recientemente. Revisa metodologías y ajusta el enfoque',
            'priority': 'medium'
        })
    
    return recommendations


# Funciones auxiliares adicionales (implementación básica)

def _get_complete_session_data(session: MentorshipSession, ally: Ally) -> Dict[str, Any]:
    """Obtiene datos completos de una sesión."""
    return {
        'basic_info': {
            'topic': session.topic,
            'session_type': session.session_type,
            'methodology': session.methodology,
            'duration_planned': session.duration_hours,
            'duration_actual': session.actual_duration,
            'location': session.location
        },
        'timing': {
            'session_date': session.session_date,
            'start_time': session.start_time,
            'actual_start': session.actual_start_time,
            'actual_end': session.actual_end_time
        },
        'preparation': {
            'is_prepared': session.preparation_completed,
            'prepared_at': session.prepared_at,
            'preparation_notes': session.preparation_notes
        },
        'evaluation': {
            'effectiveness_rating': session.session_effectiveness,
            'ally_rating': session.ally_rating,
            'entrepreneur_rating': getattr(session, 'entrepreneur_rating', None)
        }
    }


def _get_session_objectives(session: MentorshipSession) -> List[Dict[str, Any]]:
    """Obtiene objetivos de la sesión."""
    # Implementación requiere modelo SessionObjective
    return []


def _get_session_notes(session: MentorshipSession) -> List[Dict[str, Any]]:
    """Obtiene notas de la sesión."""
    # Implementación requiere modelo SessionNote
    return []


def _get_session_action_items(session: MentorshipSession) -> List[Dict[str, Any]]:
    """Obtiene items de acción de la sesión."""
    # Implementación requiere modelo ActionItem
    return []


def _get_entrepreneur_session_feedback(session: MentorshipSession) -> Optional[Dict[str, Any]]:
    """Obtiene feedback del emprendedor sobre la sesión."""
    # Implementación requiere modelo SessionFeedback
    return None


def _calculate_session_metrics(session: MentorshipSession) -> Dict[str, Any]:
    """Calcula métricas específicas de la sesión."""
    return {
        'duration_variance': 0,
        'objectives_completion_rate': 0,
        'effectiveness_score': session.session_effectiveness or 0,
        'engagement_score': 0
    }


def _get_session_documents(session: MentorshipSession) -> List[Dict[str, Any]]:
    """Obtiene documentos compartidos en la sesión."""
    return []


def _track_objective_progress(session: MentorshipSession) -> Dict[str, Any]:
    """Hace seguimiento del progreso hacia objetivos."""
    return {'progress_percentage': 0, 'objectives_met': 0, 'total_objectives': 0}


def _get_related_sessions(session: MentorshipSession) -> Dict[str, Any]:
    """Obtiene sesiones relacionadas (anteriores y siguientes)."""
    return {'previous_sessions': [], 'next_sessions': []}


def _generate_next_session_recommendations(session: MentorshipSession) -> List[str]:
    """Genera recomendaciones para la próxima sesión."""
    return []


def _get_available_session_tools(session: MentorshipSession) -> List[Dict[str, Any]]:
    """Obtiene herramientas disponibles para la sesión."""
    return []


def _analyze_session_effectiveness(session: MentorshipSession) -> Dict[str, Any]:
    """Analiza la efectividad específica de una sesión."""
    return {'effectiveness_score': session.session_effectiveness or 0, 'factors': []}


# Más funciones auxiliares para completar la funcionalidad...
# (Implementaciones específicas según necesidades del negocio)

def _get_available_entrepreneurs(ally: Ally) -> List[Tuple[int, str]]:
    """Obtiene lista de emprendedores disponibles para programar sesión."""
    entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        Entrepreneur.status == 'active'
    ).distinct().all()
    
    return [(e.id, e.user.full_name) for e in entrepreneurs]


def _get_session_templates(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene templates de sesiones disponibles."""
    # Implementación básica
    return []


def _get_available_methodologies() -> List[Tuple[str, str]]:
    """Obtiene metodologías de mentoría disponibles."""
    return [
        ('coaching', 'Coaching'),
        ('consulting', 'Consultoría'),
        ('teaching', 'Enseñanza'),
        ('facilitating', 'Facilitación'),
        ('problem_solving', 'Resolución de problemas')
    ]


def _get_ally_availability_slots(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene slots de disponibilidad del aliado."""
    # Implementación básica
    return []


def _get_default_session_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones predeterminadas de sesión."""
    return {
        'default_duration': DEFAULT_SESSION_DURATION,
        'default_location': 'virtual',
        'preferred_methodology': 'coaching',
        'preparation_buffer': PREPARATION_TIME_BUFFER
    }


def _get_upcoming_sessions_calendar(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene próximas sesiones para el calendario."""
    return []


# Funciones de notificación y logging

def _send_session_notifications(session: MentorshipSession, event_type: str, extra_data: Optional[Dict] = None) -> None:
    """Envía notificaciones relacionadas con la sesión."""
    notification_service = NotificationService()
    
    if event_type == 'created':
        notification_service.send_notification(
            user_id=session.entrepreneur.user_id,
            title='Nueva sesión de mentoría programada',
            message=f'Se ha programado una sesión de mentoría para el {session.session_date}',
            notification_type='session_scheduled'
        )
    elif event_type == 'started':
        notification_service.send_notification(
            user_id=session.entrepreneur.user_id,
            title='Sesión de mentoría iniciada',
            message='Tu sesión de mentoría ha comenzado',
            notification_type='session_started'
        )
    elif event_type == 'completed':
        notification_service.send_notification(
            user_id=session.entrepreneur.user_id,
            title='Sesión de mentoría completada',
            message='Tu sesión de mentoría ha sido completada. Pronto recibirás un resumen.',
            notification_type='session_completed'
        )
    elif event_type == 'rescheduled':
        notification_service.send_notification(
            user_id=session.entrepreneur.user_id,
            title='Sesión de mentoría reprogramada',
            message=f'Tu sesión ha sido reprogramada para el {session.session_date}',
            notification_type='session_rescheduled'
        )


def _log_session_created(session: MentorshipSession, ally: Ally) -> None:
    """Registra creación de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_created',
        description=f'Sesión creada con {session.entrepreneur.user.full_name}',
        entity_type='mentorship_session',
        entity_id=session.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_session_preparation(session: MentorshipSession, ally: Ally) -> None:
    """Registra preparación de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_prepared',
        description=f'Sesión preparada: {session.topic}',
        entity_type='mentorship_session',
        entity_id=session.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_session_started(session: MentorshipSession, ally: Ally) -> None:
    """Registra inicio de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_started',
        description=f'Sesión iniciada con {session.entrepreneur.user.full_name}',
        entity_type='mentorship_session',
        entity_id=session.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_session_completed(session: MentorshipSession, ally: Ally) -> None:
    """Registra finalización de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_completed',
        description=f'Sesión completada con {session.entrepreneur.user.full_name}',
        entity_type='mentorship_session',
        entity_id=session.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_session_rescheduled(session: MentorshipSession, ally: Ally, reason: str) -> None:
    """Registra reprogramación de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_rescheduled',
        description=f'Sesión reprogramada: {reason}',
        entity_type='mentorship_session',
        entity_id=session.id,
        metadata={'reason': reason}
    )
    db.session.add(activity)
    db.session.commit()


# Funciones auxiliares para funcionalidades específicas

def _create_meeting_link(session: MentorshipSession) -> None:
    """Crea enlace de reunión virtual para la sesión."""
    if session.location == 'virtual':
        google_meet_service = GoogleMeetService()
        meeting_link = google_meet_service.create_meeting({
            'summary': f'Sesión de mentoría - {session.topic}',
            'start_time': datetime.combine(session.session_date, session.start_time),
            'duration_minutes': int(session.duration_hours * 60),
            'attendees': [session.entrepreneur.user.email]
        })
        session.meeting_link = meeting_link
        db.session.commit()


def _schedule_session_reminders(session: MentorshipSession) -> None:
    """Programa recordatorios automáticos para la sesión."""
    # Implementación de recordatorios automáticos
    pass


def _create_session_objectives(session: MentorshipSession, objectives_text: str) -> None:
    """Crea objetivos específicos para la sesión."""
    # Implementación requiere modelo SessionObjective
    pass


def _create_action_items(session: MentorshipSession, action_items_text: str) -> None:
    """Crea items de acción derivados de la sesión."""
    # Implementación requiere modelo ActionItem
    pass


def _schedule_next_session(session: MentorshipSession, next_date: date) -> None:
    """Programa automáticamente la próxima sesión."""
    # Implementación de programación automática
    pass


def _request_entrepreneur_feedback(session: MentorshipSession) -> None:
    """Solicita feedback al emprendedor sobre la sesión."""
    notification_service = NotificationService()
    notification_service.send_notification(
        user_id=session.entrepreneur.user_id,
        title='Comparte tu feedback sobre la sesión',
        message='Por favor, comparte tu experiencia sobre la sesión de mentoría recién completada',
        notification_type='feedback_request'
    )


# Funciones auxiliares para cálculos y análisis

def _get_session_preparation_status(session: MentorshipSession) -> Dict[str, Any]:
    """Obtiene estado de preparación de la sesión."""
    return {
        'is_prepared': session.preparation_completed or False,
        'preparation_score': 85 if session.preparation_completed else 0,
        'missing_items': [] if session.preparation_completed else ['objectives', 'methodology']
    }


def _get_session_meeting_link(session: MentorshipSession) -> Optional[str]:
    """Obtiene enlace de reunión de la sesión."""
    return getattr(session, 'meeting_link', None)


def _calculate_period_effectiveness(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula efectividad promedio para un período específico."""
    avg_effectiveness = db.session.query(
        func.avg(MentorshipSession.session_effectiveness)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.session_effectiveness.isnot(None)
    ).scalar()
    
    return float(avg_effectiveness) if avg_effectiveness else 0


def _identify_top_performing_session_types(ally: Ally, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """Identifica tipos de sesiones con mejor rendimiento."""
    # Implementación básica
    return []


def _identify_improvement_areas_sessions(ally: Ally, start_date: datetime, end_date: datetime) -> List[str]:
    """Identifica áreas de mejora en las sesiones."""
    return []


def _calculate_availability_slots(ally: Ally, start: datetime, end: datetime, duration: int) -> List[Dict[str, Any]]:
    """Calcula slots de disponibilidad para un período."""
    # Implementación básica
    return []


def _check_availability_for_reschedule(ally: Ally, new_datetime: datetime, duration_hours: float) -> bool:
    """Verifica disponibilidad para reprogramar sesión."""
    # Implementación básica - verificar conflictos
    return True


# Funciones para reportes y exportación

def _generate_sessions_report_data(ally: Ally, start_date: datetime, end_date: datetime, include_details: str) -> Dict[str, Any]:
    """Genera datos para reporte de sesiones."""
    return {
        'ally': ally,
        'period': {'start': start_date, 'end': end_date},
        'stats': _calculate_mentorship_overview_stats(ally, start_date, end_date),
        'sessions': [],
        'generated_at': datetime.utcnow()
    }


def _generate_session_summary_report(session: MentorshipSession, ally: Ally) -> Dict[str, Any]:
    """Genera datos para resumen de sesión específica."""
    return {
        'session': session,
        'ally': ally,
        'session_data': _get_complete_session_data(session, ally),
        'generated_at': datetime.utcnow()
    }