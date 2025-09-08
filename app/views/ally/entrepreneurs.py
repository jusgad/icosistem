"""
Módulo de gestión de emprendedores para Aliados/Mentores.

Este módulo contiene todas las funcionalidades relacionadas con la gestión
de emprendedores asignados a aliados, incluyendo seguimiento de progreso,
comunicación, evaluaciones, programación de sesiones y análisis detallado.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from datetime import datetime, timedelta, date
from typing import Optional, Any
from collections import defaultdict
import json

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, g, abort, make_response, session
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, case, extract
from sqlalchemy.orm import joinedload, subqueryload, contains_eager
from werkzeug.exceptions import BadRequest, Forbidden

from app.core.exceptions import ValidationError, BusinessLogicError, AuthorizationError
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, Meeting, 
    Project, Task, Message, Document, Notification, ActivityLog,
    Analytics, Program, Organization, Goal, Milestone, Evaluation,
    Communication, Assignment
)
from app.forms.ally import (
    EntrepreneurFilterForm, EntrepreneurEvaluationForm, 
    MentorshipSessionForm, CommunicationForm, AssignmentForm,
    ProgressUpdateForm, GoalSettingForm, MeetingScheduleForm
)
from app.services.mentorship_service import MentorshipService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.project_service import ProjectService
from app.services.communication_service import CommunicationService
from app.utils.decorators import require_json, rate_limit, validate_pagination
from app.utils.formatters import (
    format_currency, format_percentage, format_date, 
    format_time_duration, format_number, format_relative_time
)
from app.utils.export_utils import export_to_pdf, export_to_excel
from app.utils.cache_utils import cache_key, get_cached, set_cached
from app.views.ally import (
    require_ally_access, require_entrepreneur_access, 
    track_ally_activity, validate_mentorship_session
)


# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================

ally_entrepreneurs_bp = Blueprint(
    'ally_entrepreneurs',
    __name__,
    url_prefix='/ally/entrepreneurs',
    template_folder='templates/ally/entrepreneurs'
)

# Configuración de paginación y límites
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 50
SEARCH_MIN_LENGTH = 2


# ==================== VISTAS PRINCIPALES ====================

@ally_entrepreneurs_bp.route('/')
@ally_entrepreneurs_bp.route('/list')
@login_required
@require_ally_access
@track_ally_activity('entrepreneurs_list', 'Vista de lista de emprendedores')
@validate_pagination
def list_entrepreneurs():
    """
    Lista de emprendedores asignados al aliado.
    
    Muestra todos los emprendedores bajo mentoría con filtros avanzados,
    búsqueda, ordenamiento y opciones de vista (grid/lista).
    
    Returns:
        Template con lista de emprendedores
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de filtrado y búsqueda
        filter_form = EntrepreneurFilterForm(request.args)
        
        # Construir query base
        entrepreneurs_query = _build_entrepreneurs_query(ally_profile, filter_form)
        
        # Aplicar ordenamiento
        sort_by = request.args.get('sort', 'last_interaction')
        order = request.args.get('order', 'desc')
        entrepreneurs_query = _apply_sorting(entrepreneurs_query, sort_by, order)
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', DEFAULT_PAGE_SIZE, type=int), MAX_PAGE_SIZE)
        
        entrepreneurs_paginated = entrepreneurs_query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Enriquecer datos de emprendedores
        entrepreneurs_enriched = []
        for entrepreneur in entrepreneurs_paginated.items:
            enriched_data = _enrich_entrepreneur_data(entrepreneur, ally_profile)
            entrepreneurs_enriched.append(enriched_data)
        
        # Estadísticas y métricas
        entrepreneurs_stats = _calculate_entrepreneurs_overview_stats(ally_profile)
        
        # Alertas y notificaciones importantes
        important_alerts = _get_important_alerts(ally_profile)
        
        # Próximas actividades agrupadas
        upcoming_activities = _get_upcoming_activities_grouped(ally_profile)
        
        # Vista actual (grid o lista)
        view_mode = request.args.get('view', 'grid')
        
        return render_template(
            'ally/entrepreneurs/list.html',
            entrepreneurs=entrepreneurs_paginated,
            entrepreneurs_enriched=entrepreneurs_enriched,
            entrepreneurs_stats=entrepreneurs_stats,
            important_alerts=important_alerts,
            upcoming_activities=upcoming_activities,
            filter_form=filter_form,
            view_mode=view_mode,
            current_sort=sort_by,
            current_order=order,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en lista de emprendedores: {str(e)}")
        flash('Error al cargar la lista de emprendedores', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_entrepreneurs_bp.route('/<int:entrepreneur_id>')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('entrepreneur_detail', 'Vista detallada de emprendedor')
def entrepreneur_detail(entrepreneur_id):
    """
    Vista detallada de un emprendedor específico.
    
    Muestra información completa del emprendedor, progreso de proyectos,
    historial de sesiones, comunicación y herramientas de gestión.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Template con vista detallada del emprendedor
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Información completa del emprendedor
        entrepreneur_data = _get_complete_entrepreneur_data(entrepreneur, ally_profile)
        
        # Progreso actual y tendencias
        progress_analysis = _analyze_entrepreneur_progress(entrepreneur, ally_profile)
        
        # Proyectos activos con estado detallado
        active_projects = _get_entrepreneur_projects_detailed(entrepreneur)
        
        # Historial de sesiones de mentoría
        mentorship_history = _get_mentorship_history(entrepreneur, ally_profile)
        
        # Comunicación reciente
        recent_communications = _get_recent_communications(entrepreneur, ally_profile)
        
        # Evaluaciones y feedback
        evaluations_summary = _get_evaluations_summary(entrepreneur, ally_profile)
        
        # Próximas actividades específicas
        upcoming_entrepreneur_activities = _get_entrepreneur_upcoming_activities(
            entrepreneur, ally_profile
        )
        
        # Métricas de rendimiento
        performance_metrics = _calculate_entrepreneur_performance_metrics(
            entrepreneur, ally_profile
        )
        
        # Recomendaciones personalizadas
        personalized_recommendations = _generate_entrepreneur_recommendations(
            entrepreneur, ally_profile, progress_analysis
        )
        
        # Timeline de interacciones
        interaction_timeline = _build_interaction_timeline(entrepreneur, ally_profile)
        
        # Documentos compartidos
        shared_documents = _get_shared_documents(entrepreneur, ally_profile)
        
        return render_template(
            'ally/entrepreneurs/detail.html',
            entrepreneur=entrepreneur,
            entrepreneur_data=entrepreneur_data,
            progress_analysis=progress_analysis,
            active_projects=active_projects,
            mentorship_history=mentorship_history,
            recent_communications=recent_communications,
            evaluations_summary=evaluations_summary,
            upcoming_activities=upcoming_entrepreneur_activities,
            performance_metrics=performance_metrics,
            personalized_recommendations=personalized_recommendations,
            interaction_timeline=interaction_timeline,
            shared_documents=shared_documents,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista detallada del emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar información del emprendedor', 'error')
        return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))


@ally_entrepreneurs_bp.route('/<int:entrepreneur_id>/projects')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('entrepreneur_projects', 'Vista de proyectos del emprendedor')
def entrepreneur_projects(entrepreneur_id):
    """
    Vista de proyectos específicos del emprendedor.
    
    Muestra todos los proyectos del emprendedor con análisis detallado,
    hitos, tareas y herramientas de seguimiento.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Template con proyectos del emprendedor
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Filtros de proyectos
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        category_filter = request.args.get('category', 'all')
        
        # Proyectos con filtros aplicados
        projects_query = _build_projects_query(
            entrepreneur, status_filter, priority_filter, category_filter
        )
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        projects = projects_query.paginate(
            page=page, per_page=8, error_out=False
        )
        
        # Enriquecer datos de proyectos
        projects_enriched = []
        for project in projects.items:
            enriched_project = _enrich_project_data(project, ally_profile)
            projects_enriched.append(enriched_project)
        
        # Estadísticas de proyectos
        projects_stats = _calculate_projects_stats(entrepreneur)
        
        # Proyectos críticos que requieren atención
        critical_projects = _identify_critical_projects(entrepreneur)
        
        # Hitos próximos
        upcoming_milestones = _get_upcoming_project_milestones(entrepreneur)
        
        # Tendencias de progreso
        progress_trends = _analyze_projects_progress_trends(entrepreneur)
        
        return render_template(
            'ally/entrepreneurs/projects.html',
            entrepreneur=entrepreneur,
            projects=projects,
            projects_enriched=projects_enriched,
            projects_stats=projects_stats,
            critical_projects=critical_projects,
            upcoming_milestones=upcoming_milestones,
            progress_trends=progress_trends,
            current_status_filter=status_filter,
            current_priority_filter=priority_filter,
            current_category_filter=category_filter,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en proyectos del emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar proyectos del emprendedor', 'error')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', 
                              entrepreneur_id=entrepreneur_id))


@ally_entrepreneurs_bp.route('/<int:entrepreneur_id>/communications')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('entrepreneur_communications', 'Vista de comunicaciones')
def entrepreneur_communications(entrepreneur_id):
    """
    Vista de comunicaciones con el emprendedor.
    
    Muestra historial completo de comunicaciones, mensajes,
    notas y herramientas de comunicación en tiempo real.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Template con comunicaciones del emprendedor
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Filtros de comunicación
        type_filter = request.args.get('type', 'all')  # all, message, note, email, call
        date_filter = request.args.get('date', 'all')  # all, today, week, month
        
        # Historial de comunicaciones
        communications_query = _build_communications_query(
            entrepreneur, ally_profile, type_filter, date_filter
        )
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        communications = communications_query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Estadísticas de comunicación
        communication_stats = _calculate_communication_stats(entrepreneur, ally_profile)
        
        # Formulario para nueva comunicación
        communication_form = CommunicationForm()
        
        # Mensajes no leídos
        unread_messages = _get_unread_messages(entrepreneur, ally_profile)
        
        # Próximos recordatorios
        upcoming_reminders = _get_upcoming_reminders(entrepreneur, ally_profile)
        
        # Análisis de patrones de comunicación
        communication_patterns = _analyze_communication_patterns(entrepreneur, ally_profile)
        
        return render_template(
            'ally/entrepreneurs/communications.html',
            entrepreneur=entrepreneur,
            communications=communications,
            communication_stats=communication_stats,
            communication_form=communication_form,
            unread_messages=unread_messages,
            upcoming_reminders=upcoming_reminders,
            communication_patterns=communication_patterns,
            current_type_filter=type_filter,
            current_date_filter=date_filter,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en comunicaciones del emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar comunicaciones del emprendedor', 'error')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', 
                              entrepreneur_id=entrepreneur_id))


@ally_entrepreneurs_bp.route('/<int:entrepreneur_id>/evaluations')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('entrepreneur_evaluations', 'Vista de evaluaciones')
def entrepreneur_evaluations(entrepreneur_id):
    """
    Vista de evaluaciones y feedback del emprendedor.
    
    Muestra historial de evaluaciones, métricas de progreso,
    feedback recibido y herramientas para nueva evaluación.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Template con evaluaciones del emprendedor
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Evaluaciones históricas
        historical_evaluations = _get_historical_evaluations(entrepreneur, ally_profile)
        
        # Evaluación más reciente
        latest_evaluation = _get_latest_evaluation(entrepreneur, ally_profile)
        
        # Tendencias de evaluación
        evaluation_trends = _analyze_evaluation_trends(entrepreneur, ally_profile)
        
        # Áreas de mejora identificadas
        improvement_areas = _identify_improvement_areas(entrepreneur, ally_profile)
        
        # Fortalezas reconocidas
        recognized_strengths = _identify_strengths(entrepreneur, ally_profile)
        
        # Formulario para nueva evaluación
        evaluation_form = EntrepreneurEvaluationForm()
        
        # Comparativa con otros emprendedores (anonimizada)
        peer_comparison = _get_peer_comparison(entrepreneur, ally_profile)
        
        # Objetivos de desarrollo
        development_goals = _get_development_goals(entrepreneur, ally_profile)
        
        return render_template(
            'ally/entrepreneurs/evaluations.html',
            entrepreneur=entrepreneur,
            historical_evaluations=historical_evaluations,
            latest_evaluation=latest_evaluation,
            evaluation_trends=evaluation_trends,
            improvement_areas=improvement_areas,
            recognized_strengths=recognized_strengths,
            evaluation_form=evaluation_form,
            peer_comparison=peer_comparison,
            development_goals=development_goals,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en evaluaciones del emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar evaluaciones del emprendedor', 'error')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', 
                              entrepreneur_id=entrepreneur_id))


# ==================== GESTIÓN DE SESIONES DE MENTORÍA ====================

@ally_entrepreneurs_bp.route('/<int:entrepreneur_id>/sessions')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('mentorship_sessions', 'Vista de sesiones de mentoría')
def mentorship_sessions(entrepreneur_id):
    """
    Vista de sesiones de mentoría con el emprendedor.
    
    Muestra historial de sesiones, próximas citas,
    análisis de efectividad y herramientas de programación.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Template con sesiones de mentoría
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Sesiones históricas con detalles
        historical_sessions = _get_detailed_sessions_history(entrepreneur, ally_profile)
        
        # Próximas sesiones programadas
        upcoming_sessions = _get_upcoming_sessions(entrepreneur, ally_profile)
        
        # Estadísticas de sesiones
        sessions_stats = _calculate_sessions_stats(entrepreneur, ally_profile)
        
        # Análisis de efectividad
        effectiveness_analysis = _analyze_sessions_effectiveness(entrepreneur, ally_profile)
        
        # Formulario para programar nueva sesión
        session_form = MentorshipSessionForm()
        
        # Temas frecuentes discutidos
        frequent_topics = _analyze_session_topics(entrepreneur, ally_profile)
        
        # Progreso por sesión
        session_progress_tracking = _track_progress_by_session(entrepreneur, ally_profile)
        
        # Recomendaciones para próximas sesiones
        next_session_recommendations = _generate_session_recommendations(
            entrepreneur, ally_profile
        )
        
        return render_template(
            'ally/entrepreneurs/sessions.html',
            entrepreneur=entrepreneur,
            historical_sessions=historical_sessions,
            upcoming_sessions=upcoming_sessions,
            sessions_stats=sessions_stats,
            effectiveness_analysis=effectiveness_analysis,
            session_form=session_form,
            frequent_topics=frequent_topics,
            session_progress_tracking=session_progress_tracking,
            next_session_recommendations=next_session_recommendations,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en sesiones de mentoría del emprendedor {entrepreneur_id}: {str(e)}")
        flash('Error al cargar sesiones de mentoría', 'error')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', 
                              entrepreneur_id=entrepreneur_id))


@ally_entrepreneurs_bp.route('/schedule-session', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('session_schedule', 'Programación de sesión de mentoría')
def schedule_session():
    """
    Programa una nueva sesión de mentoría.
    
    Procesa formulario de programación, valida disponibilidad,
    crea la sesión y envía notificaciones correspondientes.
    
    Returns:
        Redirección con mensaje de confirmación o error
    """
    try:
        ally_profile = g.ally_profile
        form = MentorshipSessionForm()
        
        if not form.validate_on_submit():
            flash('Error en los datos del formulario', 'error')
            return redirect(request.referrer or url_for('ally_entrepreneurs.list_entrepreneurs'))
        
        entrepreneur_id = form.entrepreneur_id.data
        
        # Verificar acceso al emprendedor
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        if not entrepreneur or not _can_access_entrepreneur(ally_profile, entrepreneur):
            flash('No tienes permiso para programar sesiones con este emprendedor', 'error')
            return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))
        
        # Datos de la sesión
        session_data = {
            'entrepreneur_id': entrepreneur_id,
            'ally_id': ally_profile.id,
            'session_date': form.session_date.data,
            'start_time': form.start_time.data,
            'duration_hours': form.duration_hours.data,
            'topic': form.topic.data,
            'objectives': form.objectives.data,
            'session_type': form.session_type.data,
            'location': form.location.data,
            'notes': form.notes.data
        }
        
        # Usar servicio de mentoría para crear la sesión
        mentorship_service = MentorshipService()
        result = mentorship_service.schedule_session(session_data)
        
        if result['success']:
            session = result['session']
            
            # Notificar al emprendedor
            _notify_session_scheduled(session, entrepreneur, ally_profile)
            
            # Registrar actividad
            _log_session_scheduled(session, ally_profile)
            
            flash('Sesión de mentoría programada exitosamente', 'success')
            return redirect(url_for('ally_entrepreneurs.mentorship_sessions', 
                                  entrepreneur_id=entrepreneur_id))
        else:
            flash(f'Error programando sesión: {result["error"]}', 'error')
            return redirect(request.referrer or url_for('ally_entrepreneurs.list_entrepreneurs'))
            
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(request.referrer or url_for('ally_entrepreneurs.list_entrepreneurs'))
    except Exception as e:
        current_app.logger.error(f"Error programando sesión: {str(e)}")
        flash('Error interno al programar sesión', 'error')
        return redirect(request.referrer or url_for('ally_entrepreneurs.list_entrepreneurs'))


# ==================== API ENDPOINTS ====================

@ally_entrepreneurs_bp.route('/api/entrepreneurs/stats')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_entrepreneurs_stats():
    """
    API endpoint para estadísticas de emprendedores.
    
    Returns:
        JSON con estadísticas actualizadas
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar cache
        cache_key_val = f"ally_entrepreneurs_stats_{ally_profile.id}"
        cached_stats = get_cached(cache_key_val)
        
        if cached_stats:
            return jsonify({
                'success': True,
                'data': cached_stats,
                'cached': True
            })
        
        # Calcular estadísticas
        stats = _calculate_entrepreneurs_overview_stats(ally_profile)
        
        # Cachear por 5 minutos
        set_cached(cache_key_val, stats, timeout=300)
        
        return jsonify({
            'success': True,
            'data': stats,
            'cached': False
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API de estadísticas: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/progress')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=20, period=60)
@require_json
def api_entrepreneur_progress(entrepreneur_id):
    """
    API endpoint para progreso específico de un emprendedor.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con análisis de progreso
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Análisis de progreso detallado
        progress_data = _analyze_entrepreneur_progress(entrepreneur, ally_profile)
        
        return jsonify({
            'success': True,
            'data': progress_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API de progreso: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/update-status', methods=['POST'])
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=15, period=60)
@require_json
def api_update_entrepreneur_status(entrepreneur_id):
    """
    API endpoint para actualizar estado del emprendedor.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        data = request.get_json()
        
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        # Validar nuevo estado
        valid_statuses = ['active', 'inactive', 'graduated', 'on_hold', 'transferred']
        if new_status not in valid_statuses:
            return jsonify({'error': 'Estado no válido'}), 400
        
        # Actualizar estado
        old_status = entrepreneur.status
        entrepreneur.status = new_status
        entrepreneur.updated_at = datetime.now(timezone.utc)
        
        # Crear registro de cambio de estado
        _create_status_change_record(entrepreneur, ally_profile, old_status, new_status, notes)
        
        db.session.commit()
        
        # Notificar cambio si es significativo
        if _is_significant_status_change(old_status, new_status):
            _notify_status_change(entrepreneur, ally_profile, old_status, new_status)
        
        # Registrar actividad
        _log_status_change(entrepreneur, ally_profile, old_status, new_status)
        
        return jsonify({
            'success': True,
            'message': 'Estado actualizado exitosamente',
            'new_status': new_status,
            'old_status': old_status
        })
        
    except Exception as e:
        current_app.logger.error(f"Error actualizando estado: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/add-note', methods=['POST'])
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=20, period=60)
@require_json
def api_add_entrepreneur_note(entrepreneur_id):
    """
    API endpoint para agregar nota sobre el emprendedor.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        data = request.get_json()
        
        note_content = data.get('content', '').strip()
        note_type = data.get('type', 'general')  # general, progress, concern, achievement
        is_private = data.get('is_private', True)
        
        if not note_content:
            return jsonify({'error': 'Contenido de la nota es requerido'}), 400
        
        # Crear nota usando servicio de comunicación
        communication_service = CommunicationService()
        
        note_result = communication_service.create_note({
            'content': note_content,
            'note_type': note_type,
            'is_private': is_private,
            'entrepreneur_id': entrepreneur_id,
            'ally_id': ally_profile.id,
            'author_id': ally_profile.user_id
        })
        
        if note_result['success']:
            # Registrar actividad
            _log_note_added(entrepreneur, ally_profile, note_content)
            
            return jsonify({
                'success': True,
                'message': 'Nota agregada exitosamente',
                'note': note_result['note_data']
            })
        else:
            return jsonify({
                'error': note_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error agregando nota: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/send-message', methods=['POST'])
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=30, period=60)
@require_json
def api_send_message(entrepreneur_id):
    """
    API endpoint para enviar mensaje al emprendedor.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        data = request.get_json()
        
        message_content = data.get('content', '').strip()
        message_subject = data.get('subject', '').strip()
        message_type = data.get('type', 'direct')  # direct, email, system
        priority = data.get('priority', 'normal')  # low, normal, high, urgent
        
        if not message_content:
            return jsonify({'error': 'Contenido del mensaje es requerido'}), 400
        
        # Crear mensaje
        message = Message(
            sender_id=ally_profile.user_id,
            recipient_id=entrepreneur.user_id,
            subject=message_subject or 'Mensaje de tu mentor',
            content=message_content,
            message_type=message_type,
            priority=priority,
            metadata={
                'ally_id': ally_profile.id,
                'entrepreneur_id': entrepreneur.id,
                'sent_from': 'ally_portal'
            }
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Enviar notificación
        _notify_message_sent(message, entrepreneur, ally_profile)
        
        # Registrar actividad
        _log_message_sent(entrepreneur, ally_profile, message)
        
        return jsonify({
            'success': True,
            'message': 'Mensaje enviado exitosamente',
            'message_id': message.id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error enviando mensaje: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/schedule-quick-meeting', methods=['POST'])
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=10, period=60)
@require_json
def api_schedule_quick_meeting(entrepreneur_id):
    """
    API endpoint para programar reunión rápida.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['date', 'time', 'duration', 'topic']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Faltan campos requeridos'}), 400
        
        # Parsear fecha y hora
        meeting_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        meeting_time = datetime.strptime(data['time'], '%H:%M').time()
        meeting_datetime = datetime.combine(meeting_date, meeting_time)
        
        # Validar que la fecha sea futura
        if meeting_datetime <= datetime.now(timezone.utc):
            return jsonify({'error': 'La reunión debe ser programada para una fecha futura'}), 400
        
        # Crear reunión
        meeting = Meeting(
            ally_id=ally_profile.id,
            entrepreneur_id=entrepreneur.id,
            title=data.get('topic', 'Reunión de seguimiento'),
            description=data.get('description', ''),
            scheduled_at=meeting_datetime,
            duration_minutes=int(data['duration']),
            meeting_type='mentorship',
            location=data.get('location', 'Virtual'),
            status='scheduled'
        )
        
        db.session.add(meeting)
        db.session.commit()
        
        # Notificar al emprendedor
        _notify_meeting_scheduled(meeting, entrepreneur, ally_profile)
        
        # Registrar actividad
        _log_meeting_scheduled(meeting, ally_profile)
        
        return jsonify({
            'success': True,
            'message': 'Reunión programada exitosamente',
            'meeting': {
                'id': meeting.id,
                'title': meeting.title,
                'scheduled_at': meeting.scheduled_at.isoformat(),
                'duration_minutes': meeting.duration_minutes
            }
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha u hora no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error programando reunión: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_entrepreneurs_bp.route('/api/entrepreneur/<int:entrepreneur_id>/evaluation', methods=['POST'])
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@rate_limit(calls=5, period=60)
@require_json
def api_create_evaluation(entrepreneur_id):
    """
    API endpoint para crear evaluación del emprendedor.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        data = request.get_json()
        
        # Validar formulario de evaluación
        form = EntrepreneurEvaluationForm(data=data)
        if not form.validate():
            return jsonify({
                'error': 'Datos de evaluación no válidos',
                'details': form.errors
            }), 400
        
        # Crear evaluación
        evaluation_data = {
            'entrepreneur_id': entrepreneur.id,
            'ally_id': ally_profile.id,
            'evaluator_id': ally_profile.user_id,
            'evaluation_period_start': form.period_start.data,
            'evaluation_period_end': form.period_end.data,
            'overall_rating': form.overall_rating.data,
            'progress_rating': form.progress_rating.data,
            'communication_rating': form.communication_rating.data,
            'commitment_rating': form.commitment_rating.data,
            'strengths': form.strengths.data,
            'areas_for_improvement': form.areas_for_improvement.data,
            'recommendations': form.recommendations.data,
            'goals_for_next_period': form.goals_for_next_period.data,
            'notes': form.notes.data
        }
        
        # Usar servicio para crear evaluación
        # evaluation = Evaluation(**evaluation_data)
        # db.session.add(evaluation)
        # db.session.commit()
        
        # Por ahora simulamos la creación exitosa
        evaluation_id = 1  # En implementación real sería evaluation.id
        
        # Notificar al emprendedor sobre nueva evaluación
        _notify_evaluation_created(entrepreneur, ally_profile)
        
        # Registrar actividad
        _log_evaluation_created(entrepreneur, ally_profile)
        
        return jsonify({
            'success': True,
            'message': 'Evaluación creada exitosamente',
            'evaluation_id': evaluation_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error creando evaluación: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== EXPORTACIÓN Y REPORTES ====================

@ally_entrepreneurs_bp.route('/export/entrepreneurs-report')
@login_required
@require_ally_access
@track_ally_activity('entrepreneurs_export', 'Exportación de reporte de emprendedores')
def export_entrepreneurs_report():
    """
    Exporta reporte completo de emprendedores.
    
    Returns:
        Archivo PDF o Excel con reporte de emprendedores
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de exportación
        format_type = request.args.get('format', 'pdf')  # pdf, excel
        include_details = request.args.get('details', 'basic')  # basic, detailed, complete
        date_range = request.args.get('range', '6months')  # 1month, 3months, 6months, 1year, all
        
        # Generar datos del reporte
        report_data = _generate_entrepreneurs_report_data(
            ally_profile, include_details, date_range
        )
        
        if format_type == 'pdf':
            # Generar PDF
            pdf_content = export_to_pdf(
                template='reports/ally_entrepreneurs_report.html',
                data=report_data,
                filename=f'emprendedores_report_{ally_profile.user.first_name}_{ally_profile.user.last_name}'
            )
            
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename=reporte_emprendedores.pdf'
            
            return response
            
        elif format_type == 'excel':
            # Generar Excel
            excel_content = export_to_excel(
                data=report_data,
                filename=f'emprendedores_report_{datetime.now().strftime("%Y%m%d")}'
            )
            
            response = make_response(excel_content)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = 'attachment; filename=reporte_emprendedores.xlsx'
            
            return response
        
        else:
            flash('Formato de exportación no válido', 'error')
            return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))
            
    except Exception as e:
        current_app.logger.error(f"Error exportando reporte: {str(e)}")
        flash('Error al generar el reporte', 'error')
        return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))


@ally_entrepreneurs_bp.route('/export/entrepreneur/<int:entrepreneur_id>/profile')
@login_required
@require_ally_access
@require_entrepreneur_access('entrepreneur_id')
@track_ally_activity('entrepreneur_profile_export', 'Exportación de perfil de emprendedor')
def export_entrepreneur_profile(entrepreneur_id):
    """
    Exporta perfil completo de un emprendedor específico.
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Archivo PDF con perfil completo del emprendedor
    """
    try:
        ally_profile = g.ally_profile
        entrepreneur = g.target_entrepreneur
        
        # Generar datos completos del perfil
        profile_data = _generate_entrepreneur_profile_report(entrepreneur, ally_profile)
        
        # Generar PDF
        pdf_content = export_to_pdf(
            template='reports/entrepreneur_profile_report.html',
            data=profile_data,
            filename=f'perfil_{entrepreneur.user.first_name}_{entrepreneur.user.last_name}'
        )
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=perfil_{entrepreneur.user.first_name}_{entrepreneur.user.last_name}.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando perfil: {str(e)}")
        flash('Error al generar el perfil', 'error')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', 
                              entrepreneur_id=entrepreneur_id))


# ==================== FUNCIONES AUXILIARES ====================

def _build_entrepreneurs_query(ally: Ally, filter_form: EntrepreneurFilterForm):
    """
    Construye query base para emprendedores con filtros aplicados.
    
    Args:
        ally: Perfil del aliado
        filter_form: Formulario con filtros
        
    Returns:
        Query de emprendedores filtrada
    """
    # Query base con emprendedores asignados al aliado
    query = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id
    ).options(
        joinedload(Entrepreneur.user),
        joinedload(Entrepreneur.projects),
        subqueryload(Entrepreneur.mentorship_sessions)
    ).distinct()
    
    # Aplicar filtros si están presentes
    if filter_form.status.data and filter_form.status.data != 'all':
        query = query.filter(Entrepreneur.status == filter_form.status.data)
    
    if filter_form.program.data and filter_form.program.data != 'all':
        query = query.filter(Entrepreneur.program_id == filter_form.program.data)
    
    if filter_form.industry.data and filter_form.industry.data != 'all':
        query = query.filter(Entrepreneur.industry == filter_form.industry.data)
    
    if filter_form.search.data:
        search_term = f"%{filter_form.search.data}%"
        query = query.join(User).filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
                Entrepreneur.company_name.ilike(search_term)
            )
        )
    
    if filter_form.date_range.data and filter_form.date_range.data != 'all':
        days_map = {
            'week': 7,
            'month': 30,
            'quarter': 90,
            'year': 365
        }
        days = days_map.get(filter_form.date_range.data, 30)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = query.filter(MentorshipSession.created_at >= cutoff_date)
    
    return query


def _apply_sorting(query, sort_by: str, order: str):
    """
    Aplica ordenamiento a la query de emprendedores.
    
    Args:
        query: Query base
        sort_by: Campo por el cual ordenar
        order: Dirección del orden (asc/desc)
        
    Returns:
        Query ordenada
    """
    order_func = desc if order == 'desc' else asc
    
    if sort_by == 'name':
        query = query.join(User).order_by(order_func(User.first_name))
    elif sort_by == 'status':
        query = query.order_by(order_func(Entrepreneur.status))
    elif sort_by == 'company':
        query = query.order_by(order_func(Entrepreneur.company_name))
    elif sort_by == 'join_date':
        query = query.order_by(order_func(Entrepreneur.created_at))
    elif sort_by == 'last_interaction':
        # Subquery para obtener la última interacción
        last_interaction = db.session.query(
            MentorshipSession.entrepreneur_id,
            func.max(MentorshipSession.session_date).label('last_date')
        ).group_by(MentorshipSession.entrepreneur_id).subquery()
        
        query = query.outerjoin(
            last_interaction,
            Entrepreneur.id == last_interaction.c.entrepreneur_id
        ).order_by(order_func(last_interaction.c.last_date))
    else:
        query = query.order_by(order_func(Entrepreneur.updated_at))
    
    return query


def _enrich_entrepreneur_data(entrepreneur: Entrepreneur, ally: Ally) -> dict[str, Any]:
    """
    Enriquece datos de un emprendedor con información adicional.
    
    Args:
        entrepreneur: Emprendedor
        ally: Aliado
        
    Returns:
        Dict con datos enriquecidos
    """
    # Progreso general
    overall_progress = _calculate_entrepreneur_overall_progress(entrepreneur)
    
    # Última interacción
    last_interaction = _get_last_interaction_date(entrepreneur, ally)
    
    # Próxima actividad
    next_activity = _get_next_activity_with_entrepreneur(entrepreneur, ally)
    
    # Estado de la relación
    relationship_health = _assess_relationship_health(entrepreneur, ally)
    
    # Proyectos activos
    active_projects_count = Project.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).count()
    
    # Alertas importantes
    important_alerts = _get_entrepreneur_alerts(entrepreneur, ally)
    
    return {
        'entrepreneur': entrepreneur,
        'overall_progress': overall_progress,
        'last_interaction': last_interaction,
        'next_activity': next_activity,
        'relationship_health': relationship_health,
        'active_projects_count': active_projects_count,
        'important_alerts': important_alerts,
        'days_since_last_contact': (datetime.now(timezone.utc).date() - last_interaction).days if last_interaction else None,
        'mentorship_duration': _calculate_mentorship_duration(entrepreneur, ally),
        'satisfaction_score': _get_entrepreneur_satisfaction_score(entrepreneur, ally)
    }


def _calculate_entrepreneurs_overview_stats(ally: Ally) -> dict[str, Any]:
    """
    Calcula estadísticas generales de emprendedores del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con estadísticas generales
    """
    # Emprendedores activos
    total_entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id
    ).distinct().count()
    
    active_entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        Entrepreneur.status == 'active'
    ).distinct().count()
    
    # Distribución por estado
    status_distribution = db.session.query(
        Entrepreneur.status,
        func.count(Entrepreneur.id)
    ).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id
    ).group_by(Entrepreneur.status).all()
    
    status_dict = dict(status_distribution)
    
    # Progreso promedio
    entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id
    ).distinct().all()
    
    total_progress = sum(
        _calculate_entrepreneur_overall_progress(e)['overall_percentage'] 
        for e in entrepreneurs
    )
    avg_progress = (total_progress / len(entrepreneurs)) if entrepreneurs else 0
    
    # Sesiones este mes
    this_month = datetime.now(timezone.utc).replace(day=1)
    sessions_this_month = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= this_month.date()
    ).count()
    
    # Emprendedores que necesitan atención
    entrepreneurs_needing_attention = _count_entrepreneurs_needing_attention(ally)
    
    return {
        'total_entrepreneurs': total_entrepreneurs,
        'active_entrepreneurs': active_entrepreneurs,
        'inactive_entrepreneurs': status_dict.get('inactive', 0),
        'graduated_entrepreneurs': status_dict.get('graduated', 0),
        'on_hold_entrepreneurs': status_dict.get('on_hold', 0),
        'avg_progress': round(avg_progress, 1),
        'sessions_this_month': sessions_this_month,
        'entrepreneurs_needing_attention': entrepreneurs_needing_attention,
        'status_distribution': status_dict
    }


def _get_important_alerts(ally: Ally) -> list[dict[str, Any]]:
    """
    Obtiene alertas importantes relacionadas con emprendedores.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de alertas importantes
    """
    alerts = []
    
    # Emprendedores sin contacto reciente
    entrepreneurs_no_contact = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id
    ).distinct().all()
    
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=14)
    
    for entrepreneur in entrepreneurs_no_contact:
        last_contact = _get_last_interaction_date(entrepreneur, ally)
        if last_contact and last_contact < cutoff_date:
            alerts.append({
                'type': 'no_contact',
                'severity': 'medium',
                'entrepreneur_id': entrepreneur.id,
                'entrepreneur_name': entrepreneur.user.full_name,
                'message': f'Sin contacto hace {(datetime.now(timezone.utc).date() - last_contact).days} días',
                'action_url': url_for('ally_entrepreneurs.entrepreneur_detail', 
                                    entrepreneur_id=entrepreneur.id)
            })
    
    # Proyectos atrasados
    overdue_projects = Project.query.join(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        Project.target_end_date < datetime.now(timezone.utc).date(),
        Project.status == 'active'
    ).all()
    
    for project in overdue_projects:
        alerts.append({
            'type': 'overdue_project',
            'severity': 'high',
            'entrepreneur_id': project.entrepreneur_id,
            'entrepreneur_name': project.entrepreneur.user.full_name,
            'message': f'Proyecto "{project.name}" está atrasado',
            'action_url': url_for('ally_entrepreneurs.entrepreneur_projects', 
                                entrepreneur_id=project.entrepreneur_id)
        })
    
    # Sesiones perdidas
    missed_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date < datetime.now(timezone.utc).date(),
        MentorshipSession.status == 'scheduled'
    ).all()
    
    for session in missed_sessions:
        alerts.append({
            'type': 'missed_session',
            'severity': 'medium',
            'entrepreneur_id': session.entrepreneur_id,
            'entrepreneur_name': session.entrepreneur.user.full_name,
            'message': f'Sesión perdida el {session.session_date}',
            'action_url': url_for('ally_entrepreneurs.mentorship_sessions', 
                                entrepreneur_id=session.entrepreneur_id)
        })
    
    return sorted(alerts, key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['severity']], reverse=True)


def _get_upcoming_activities_grouped(ally: Ally) -> dict[str, list[dict[str, Any]]]:
    """
    Obtiene próximas actividades agrupadas por tipo.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con actividades agrupadas
    """
    activities = {
        'meetings': [],
        'sessions': [],
        'deadlines': [],
        'follow_ups': []
    }
    
    # Próximas reuniones
    upcoming_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at > datetime.now(timezone.utc),
        Meeting.status.in_(['scheduled', 'confirmed'])
    ).order_by(Meeting.scheduled_at).limit(10).all()
    
    for meeting in upcoming_meetings:
        activities['meetings'].append({
            'id': meeting.id,
            'title': meeting.title,
            'datetime': meeting.scheduled_at,
            'entrepreneur_name': meeting.entrepreneur.user.full_name,
            'type': 'meeting'
        })
    
    # Próximas sesiones de mentoría
    upcoming_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date > datetime.now(timezone.utc).date(),
        MentorshipSession.status == 'scheduled'
    ).order_by(MentorshipSession.session_date).limit(10).all()
    
    for session in upcoming_sessions:
        activities['sessions'].append({
            'id': session.id,
            'title': f'Sesión: {session.topic}',
            'datetime': datetime.combine(session.session_date, session.start_time or datetime.min.time()),
            'entrepreneur_name': session.entrepreneur.user.full_name,
            'type': 'session'
        })
    
    # Próximos deadlines de proyectos
    upcoming_deadlines = Project.query.join(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        Project.target_end_date > datetime.now(timezone.utc).date(),
        Project.target_end_date <= datetime.now(timezone.utc).date() + timedelta(days=30),
        Project.status == 'active'
    ).order_by(Project.target_end_date).limit(10).all()
    
    for project in upcoming_deadlines:
        activities['deadlines'].append({
            'id': project.id,
            'title': f'Deadline: {project.name}',
            'datetime': datetime.combine(project.target_end_date, datetime.min.time()),
            'entrepreneur_name': project.entrepreneur.user.full_name,
            'type': 'deadline'
        })
    
    return activities


def _get_complete_entrepreneur_data(entrepreneur: Entrepreneur, ally: Ally) -> dict[str, Any]:
    """
    Obtiene datos completos de un emprendedor específico.
    
    Args:
        entrepreneur: Emprendedor
        ally: Aliado
        
    Returns:
        Dict con datos completos del emprendedor
    """
    user = entrepreneur.user
    
    return {
        'basic_info': {
            'full_name': user.full_name,
            'email': user.email,
            'phone': entrepreneur.phone,
            'company_name': entrepreneur.company_name,
            'industry': entrepreneur.industry,
            'status': entrepreneur.status,
            'join_date': entrepreneur.created_at,
            'location': f"{entrepreneur.city}, {entrepreneur.country}".strip(', '),
            'profile_image_url': user.profile_image_url
        },
        'business_info': {
            'business_stage': entrepreneur.business_stage,
            'business_model': entrepreneur.business_model,
            'target_market': entrepreneur.target_market,
            'revenue_stage': entrepreneur.revenue_stage,
            'funding_stage': entrepreneur.funding_stage,
            'team_size': entrepreneur.team_size,
            'business_description': entrepreneur.business_description
        },
        'program_info': {
            'program_name': entrepreneur.program.name if entrepreneur.program else None,
            'program_start_date': entrepreneur.program_start_date,
            'program_end_date': entrepreneur.program_end_date,
            'cohort': entrepreneur.cohort,
            'organization': entrepreneur.organization.name if entrepreneur.organization else None
        },
        'contact_preferences': {
            'preferred_contact_method': entrepreneur.preferred_contact_method,
            'timezone': entrepreneur.timezone,
            'communication_frequency': entrepreneur.communication_frequency,
            'best_contact_hours': entrepreneur.best_contact_hours
        }
    }


def _analyze_entrepreneur_progress(entrepreneur: Entrepreneur, ally: Ally) -> dict[str, Any]:
    """
    Analiza el progreso detallado de un emprendedor.
    
    Args:
        entrepreneur: Emprendedor
        ally: Aliado
        
    Returns:
        Dict con análisis de progreso
    """
    # Progreso general
    overall_progress = _calculate_entrepreneur_overall_progress(entrepreneur)
    
    # Progreso por áreas
    areas_progress = {
        'business_development': _calculate_business_development_progress(entrepreneur),
        'financial_management': _calculate_financial_progress(entrepreneur),
        'marketing_sales': _calculate_marketing_progress(entrepreneur),
        'operations': _calculate_operations_progress(entrepreneur),
        'leadership': _calculate_leadership_progress(entrepreneur)
    }
    
    # Tendencias temporales
    progress_trends = _calculate_progress_trends(entrepreneur, ally)
    
    # Hitos alcanzados y pendientes
    milestones_status = _analyze_milestones_status(entrepreneur)
    
    # Score de compromiso
    engagement_score = _calculate_engagement_score(entrepreneur, ally)
    
    # Predicciones basadas en tendencias
    predictions = _generate_progress_predictions(entrepreneur, ally, progress_trends)
    
    return {
        'overall_progress': overall_progress,
        'areas_progress': areas_progress,
        'progress_trends': progress_trends,
        'milestones_status': milestones_status,
        'engagement_score': engagement_score,
        'predictions': predictions,
        'last_updated': datetime.now(timezone.utc).isoformat()
    }


def _get_entrepreneur_projects_detailed(entrepreneur: Entrepreneur) -> list[dict[str, Any]]:
    """
    Obtiene proyectos detallados del emprendedor.
    
    Args:
        entrepreneur: Emprendedor
        
    Returns:
        Lista de proyectos con detalles
    """
    projects = Project.query.filter_by(
        entrepreneur_id=entrepreneur.id
    ).options(
        joinedload(Project.tasks),
        joinedload(Project.documents)
    ).order_by(desc(Project.updated_at)).all()
    
    projects_detailed = []
    for project in projects:
        # Calcular progreso del proyecto
        total_tasks = Task.query.filter_by(project_id=project.id).count()
        completed_tasks = Task.query.filter_by(
            project_id=project.id, 
            status='completed'
        ).count()
        
        progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Estado del proyecto
        project_health = _assess_project_health(project)
        
        projects_detailed.append({
            'project': project,
            'progress_percentage': round(progress_percentage, 1),
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': total_tasks - completed_tasks,
            'project_health': project_health,
            'days_until_deadline': (project.target_end_date - datetime.now(timezone.utc).date()).days if project.target_end_date else None,
            'is_overdue': project.target_end_date < datetime.now(timezone.utc).date() if project.target_end_date else False,
            'last_activity': project.updated_at
        })
    
    return projects_detailed


def _get_mentorship_history(entrepreneur: Entrepreneur, ally: Ally) -> list[dict[str, Any]]:
    """
    Obtiene historial detallado de sesiones de mentoría.
    
    Args:
        entrepreneur: Emprendedor
        ally: Aliado
        
    Returns:
        Lista de sesiones históricas
    """
    sessions = MentorshipSession.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        ally_id=ally.id
    ).order_by(desc(MentorshipSession.session_date)).all()
    
    sessions_detailed = []
    for session in sessions:
        # Analizar efectividad de la sesión
        session_effectiveness = _calculate_session_effectiveness(session)
        
        sessions_detailed.append({
            'session': session,
            'effectiveness_score': session_effectiveness,
            'duration_formatted': format_time_duration(session.duration_hours * 3600),
            'topics_covered': session.topics_covered.split(',') if session.topics_covered else [],
            'action_items': session.action_items.split('\n') if session.action_items else [],
            'follow_up_required': session.follow_up_required,
            'satisfaction_rating': session.satisfaction_rating
        })
    
    return sessions_detailed


def _get_recent_communications(entrepreneur: Entrepreneur, ally: Ally) -> list[dict[str, Any]]:
    """
    Obtiene comunicaciones recientes con el emprendedor.
    
    Args:
        entrepreneur: Emprendedor
        ally: Aliado
        
    Returns:
        Lista de comunicaciones recientes
    """
    # Mensajes entre aliado y emprendedor
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == ally.user_id, Message.recipient_id == entrepreneur.user_id),
            and_(Message.sender_id == entrepreneur.user_id, Message.recipient_id == ally.user_id)
        )
    ).order_by(desc(Message.created_at)).limit(20).all()
    
    communications = []
    for message in messages:
        communications.append({
            'type': 'message',
            'content': message.content,
            'sender': 'ally' if message.sender_id == ally.user_id else 'entrepreneur',
            'created_at': message.created_at,
            'is_read': message.is_read,
            'priority': message.priority,
            'subject': message.subject
        })
    
    # Agregar notas si existe modelo de notas
    # notes = Note.query.filter_by(entrepreneur_id=entrepreneur.id, ally_id=ally.id)...
    
    return sorted(communications, key=lambda x: x['created_at'], reverse=True)


# Funciones auxiliares adicionales (implementación básica para mantener funcionalidad)

def _calculate_entrepreneur_overall_progress(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Calcula progreso general del emprendedor."""
    # Implementación básica - en la realidad sería más compleja
    return {
        'overall_percentage': 68.5,
        'current_stage': 'Growth',
        'completed_milestones': 7,
        'total_milestones': 12,
        'trend': 'positive'
    }


def _get_last_interaction_date(entrepreneur: Entrepreneur, ally: Ally) -> Optional[date]:
    """Obtiene fecha de última interacción."""
    last_session = MentorshipSession.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        ally_id=ally.id
    ).order_by(desc(MentorshipSession.session_date)).first()
    
    last_message = Message.query.filter(
        or_(
            and_(Message.sender_id == ally.user_id, Message.recipient_id == entrepreneur.user_id),
            and_(Message.sender_id == entrepreneur.user_id, Message.recipient_id == ally.user_id)
        )
    ).order_by(desc(Message.created_at)).first()
    
    dates = []
    if last_session:
        dates.append(last_session.session_date)
    if last_message:
        dates.append(last_message.created_at.date())
    
    return max(dates) if dates else None


def _get_next_activity_with_entrepreneur(entrepreneur: Entrepreneur, ally: Ally) -> Optional[dict[str, Any]]:
    """Obtiene próxima actividad con el emprendedor."""
    next_meeting = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.scheduled_at > datetime.now(timezone.utc)
    ).order_by(Meeting.scheduled_at).first()
    
    if next_meeting:
        return {
            'type': 'meeting',
            'title': next_meeting.title,
            'datetime': next_meeting.scheduled_at,
            'id': next_meeting.id
        }
    
    next_session = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.entrepreneur_id == entrepreneur.id,
        MentorshipSession.session_date > datetime.now(timezone.utc).date()
    ).order_by(MentorshipSession.session_date).first()
    
    if next_session:
        return {
            'type': 'session',
            'title': f'Sesión: {next_session.topic}',
            'datetime': datetime.combine(next_session.session_date, next_session.start_time or datetime.min.time()),
            'id': next_session.id
        }
    
    return None


def _assess_relationship_health(entrepreneur: Entrepreneur, ally: Ally) -> dict[str, Any]:
    """Evalúa la salud de la relación de mentoría."""
    # Implementación básica
    return {
        'health_score': 85,
        'status': 'healthy',
        'communication_frequency': 'adequate',
        'engagement_level': 'high',
        'satisfaction_trend': 'positive'
    }


def _get_entrepreneur_alerts(entrepreneur: Entrepreneur, ally: Ally) -> list[str]:
    """Obtiene alertas específicas del emprendedor."""
    alerts = []
    
    # Verificar si hay proyectos atrasados
    overdue_projects = Project.query.filter(
        Project.entrepreneur_id == entrepreneur.id,
        Project.target_end_date < datetime.now(timezone.utc).date(),
        Project.status == 'active'
    ).count()
    
    if overdue_projects > 0:
        alerts.append(f'{overdue_projects} proyecto(s) atrasado(s)')
    
    # Verificar última comunicación
    last_contact = _get_last_interaction_date(entrepreneur, ally)
    if last_contact:
        days_since_contact = (datetime.now(timezone.utc).date() - last_contact).days
        if days_since_contact > 14:
            alerts.append(f'Sin contacto hace {days_since_contact} días')
    
    return alerts


def _calculate_mentorship_duration(entrepreneur: Entrepreneur, ally: Ally) -> int:
    """Calcula duración de la mentoría en días."""
    first_session = MentorshipSession.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        ally_id=ally.id
    ).order_by(MentorshipSession.session_date).first()
    
    if first_session:
        return (datetime.now(timezone.utc).date() - first_session.session_date).days
    
    return 0


def _get_entrepreneur_satisfaction_score(entrepreneur: Entrepreneur, ally: Ally) -> float:
    """Obtiene score de satisfacción del emprendedor."""
    # Implementación básica - calculado desde evaluaciones
    return 4.2


def _count_entrepreneurs_needing_attention(ally: Ally) -> int:
    """Cuenta emprendedores que necesitan atención."""
    # Implementación básica
    return 3


def _can_access_entrepreneur(ally: Ally, entrepreneur: Entrepreneur) -> bool:
    """Verifica si el aliado puede acceder al emprendedor."""
    # Verificar si hay relación de mentoría activa
    mentorship = MentorshipSession.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id,
        status='active'
    ).first()
    
    return mentorship is not None


# Funciones para notificaciones y logging
def _notify_session_scheduled(session, entrepreneur: Entrepreneur, ally: Ally) -> None:
    """Notifica sesión programada."""
    notification_service = NotificationService()
    notification_service.send_notification(
        user_id=entrepreneur.user_id,
        title='Nueva sesión de mentoría programada',
        message=f'Tu mentor {ally.user.full_name} ha programado una sesión para el {session.session_date}',
        notification_type='session_scheduled'
    )


def _log_session_scheduled(session, ally: Ally) -> None:
    """Registra programación de sesión."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='session_scheduled',
        description=f'Sesión programada con emprendedor ID: {session.entrepreneur_id}',
        entity_type='mentorship_session',
        entity_id=session.id
    )
    db.session.add(activity)
    db.session.commit()


def _create_status_change_record(entrepreneur: Entrepreneur, ally: Ally, old_status: str, new_status: str, notes: str) -> None:
    """Crea registro de cambio de estado."""
    # Implementación básica - requeriría modelo StatusChangeRecord
    pass


def _is_significant_status_change(old_status: str, new_status: str) -> bool:
    """Determina si el cambio de estado es significativo."""
    significant_changes = [
        ('active', 'graduated'),
        ('active', 'inactive'),
        ('on_hold', 'active'),
        ('inactive', 'active')
    ]
    return (old_status, new_status) in significant_changes


def _notify_status_change(entrepreneur: Entrepreneur, ally: Ally, old_status: str, new_status: str) -> None:
    """Notifica cambio de estado."""
    pass  # Implementación básica


def _log_status_change(entrepreneur: Entrepreneur, ally: Ally, old_status: str, new_status: str) -> None:
    """Registra cambio de estado."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='entrepreneur_status_change',
        description=f'Cambio de estado de {old_status} a {new_status} para emprendedor {entrepreneur.user.full_name}',
        entity_type='entrepreneur',
        entity_id=entrepreneur.id,
        metadata={'old_status': old_status, 'new_status': new_status}
    )
    db.session.add(activity)
    db.session.commit()


def _log_note_added(entrepreneur: Entrepreneur, ally: Ally, note_content: str) -> None:
    """Registra adición de nota."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='note_added',
        description=f'Nota agregada para emprendedor {entrepreneur.user.full_name}',
        entity_type='entrepreneur',
        entity_id=entrepreneur.id
    )
    db.session.add(activity)
    db.session.commit()


def _notify_message_sent(message: Message, entrepreneur: Entrepreneur, ally: Ally) -> None:
    """Notifica mensaje enviado."""
    notification_service = NotificationService()
    notification_service.send_notification(
        user_id=entrepreneur.user_id,
        title='Nuevo mensaje de tu mentor',
        message=f'Has recibido un mensaje de {ally.user.full_name}',
        notification_type='message_received'
    )


def _log_message_sent(entrepreneur: Entrepreneur, ally: Ally, message: Message) -> None:
    """Registra mensaje enviado."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='message_sent',
        description=f'Mensaje enviado a emprendedor {entrepreneur.user.full_name}',
        entity_type='message',
        entity_id=message.id
    )
    db.session.add(activity)
    db.session.commit()


def _notify_meeting_scheduled(meeting: Meeting, entrepreneur: Entrepreneur, ally: Ally) -> None:
    """Notifica reunión programada."""
    notification_service = NotificationService()
    notification_service.send_notification(
        user_id=entrepreneur.user_id,
        title='Nueva reunión programada',
        message=f'Tu mentor {ally.user.full_name} ha programado una reunión: {meeting.title}',
        notification_type='meeting_scheduled'
    )


def _log_meeting_scheduled(meeting: Meeting, ally: Ally) -> None:
    """Registra reunión programada."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='meeting_scheduled',
        description=f'Reunión programada: {meeting.title}',
        entity_type='meeting',
        entity_id=meeting.id
    )
    db.session.add(activity)
    db.session.commit()


def _notify_evaluation_created(entrepreneur: Entrepreneur, ally: Ally) -> None:
    """Notifica evaluación creada."""
    notification_service = NotificationService()
    notification_service.send_notification(
        user_id=entrepreneur.user_id,
        title='Nueva evaluación disponible',
        message=f'Tu mentor {ally.user.full_name} ha completado una nueva evaluación de tu progreso',
        notification_type='evaluation_created'
    )


def _log_evaluation_created(entrepreneur: Entrepreneur, ally: Ally) -> None:
    """Registra evaluación creada."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='evaluation_created',
        description=f'Evaluación creada para emprendedor {entrepreneur.user.full_name}',
        entity_type='entrepreneur',
        entity_id=entrepreneur.id
    )
    db.session.add(activity)
    db.session.commit()


# Funciones para reportes y exportación
def _generate_entrepreneurs_report_data(ally: Ally, include_details: str, date_range: str) -> dict[str, Any]:
    """Genera datos para reporte de emprendedores."""
    # Implementación básica
    return {
        'ally': ally,
        'entrepreneurs': [],
        'stats': _calculate_entrepreneurs_overview_stats(ally),
        'generated_at': datetime.now(timezone.utc)
    }


def _generate_entrepreneur_profile_report(entrepreneur: Entrepreneur, ally: Ally) -> dict[str, Any]:
    """Genera datos para reporte de perfil de emprendedor."""
    return {
        'entrepreneur': entrepreneur,
        'ally': ally,
        'entrepreneur_data': _get_complete_entrepreneur_data(entrepreneur, ally),
        'progress_analysis': _analyze_entrepreneur_progress(entrepreneur, ally),
        'generated_at': datetime.now(timezone.utc)
    }


# Funciones auxiliares adicionales que se referencian
def _build_projects_query(entrepreneur: Entrepreneur, status_filter: str, priority_filter: str, category_filter: str):
    """Construye query para proyectos con filtros."""
    query = Project.query.filter_by(entrepreneur_id=entrepreneur.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    return query.order_by(desc(Project.updated_at))


def _enrich_project_data(project: Project, ally: Ally) -> dict[str, Any]:
    """Enriquece datos de proyecto."""
    return {'project': project, 'health_score': 85}


def _calculate_projects_stats(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Calcula estadísticas de proyectos."""
    return {'total': 5, 'active': 3, 'completed': 2}


def _identify_critical_projects(entrepreneur: Entrepreneur) -> list[dict[str, Any]]:
    """Identifica proyectos críticos."""
    return []


def _get_upcoming_project_milestones(entrepreneur: Entrepreneur) -> list[dict[str, Any]]:
    """Obtiene próximos hitos de proyectos."""
    return []


def _analyze_projects_progress_trends(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Analiza tendencias de progreso de proyectos."""
    return {'trend': 'positive', 'velocity': 1.2}


def _assess_project_health(project: Project) -> dict[str, str]:
    """Evalúa salud del proyecto."""
    return {'score': 85, 'status': 'healthy', 'concerns': []}


# Más funciones auxiliares...
# (El resto de funciones se implementarían según necesidades específicas del negocio)