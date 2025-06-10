"""
Módulo de gestión de calendario para Aliados/Mentores.

Este módulo contiene todas las funcionalidades relacionadas con la gestión
del calendario del aliado, incluyendo disponibilidad, programación de citas,
integración con calendarios externos, gestión de conflictos y analytics de tiempo.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import json
from enum import Enum
import calendar as cal
import pytz
from dateutil import rrule, parser

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, g, abort, make_response, session
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, case, extract, text
from sqlalchemy.orm import joinedload, subqueryload
from werkzeug.exceptions import BadRequest, Forbidden

from app.core.exceptions import ValidationError, BusinessLogicError, AuthorizationError
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, Meeting, 
    AvailabilitySlot, CalendarEvent, CalendarSync, TimeBlock,
    Notification, ActivityLog, RecurringAvailability, CalendarIntegration
)
from app.forms.ally import (
    CalendarViewForm, AvailabilityForm, QuickEventForm, 
    BulkAvailabilityForm, CalendarSettingsForm, TimeBlockForm,
    RecurringAvailabilityForm, CalendarIntegrationForm
)
from app.services.calendar_service import CalendarService
from app.services.google_calendar import GoogleCalendarService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.utils.decorators import require_json, rate_limit, validate_pagination
from app.utils.formatters import (
    format_currency, format_percentage, format_date, 
    format_time_duration, format_number, format_relative_time
)
from app.utils.export_utils import export_to_ical, export_to_pdf
from app.utils.date_utils import (
    get_week_bounds, get_month_bounds, get_timezone_offset,
    parse_datetime_with_timezone, format_datetime_for_timezone
)
from app.utils.cache_utils import cache_key, get_cached, set_cached
from app.views.ally import require_ally_access, track_ally_activity


# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================

ally_calendar_bp = Blueprint(
    'ally_calendar',
    __name__,
    url_prefix='/ally/calendar',
    template_folder='templates/ally/calendar'
)

# Configuración de calendario
DEFAULT_VIEW = 'month'
SUPPORTED_VIEWS = ['month', 'week', 'day', 'agenda']
DEFAULT_TIMEZONE = 'UTC'
SLOT_DURATION_OPTIONS = [15, 30, 45, 60, 90, 120]  # minutos
MAX_ADVANCE_BOOKING_DAYS = 90
CALENDAR_COLORS = {
    'available': '#28a745',
    'busy': '#dc3545',
    'tentative': '#ffc107',
    'mentorship': '#007bff',
    'meeting': '#6f42c1',
    'blocked': '#6c757d'
}

# Tipos de eventos
class EventType(Enum):
    AVAILABILITY = 'availability'
    MENTORSHIP_SESSION = 'mentorship_session'
    MEETING = 'meeting'
    BLOCKED_TIME = 'blocked_time'
    PERSONAL = 'personal'
    EXTERNAL = 'external'


# ==================== VISTAS PRINCIPALES ====================

@ally_calendar_bp.route('/')
@ally_calendar_bp.route('/view/<view_type>')
@login_required
@require_ally_access
@track_ally_activity('calendar_view', 'Vista de calendario')
def calendar_view(view_type=None):
    """
    Vista principal del calendario del aliado.
    
    Muestra el calendario en diferentes formatos (mes, semana, día, agenda)
    con todos los eventos, disponibilidad y herramientas de gestión.
    
    Args:
        view_type: Tipo de vista (month, week, day, agenda)
        
    Returns:
        Template con vista del calendario
    """
    try:
        ally_profile = g.ally_profile
        
        # Validar y establecer tipo de vista
        if view_type not in SUPPORTED_VIEWS:
            view_type = DEFAULT_VIEW
        
        # Parámetros de fecha
        target_date_str = request.args.get('date')
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = date.today()
        else:
            target_date = date.today()
        
        # Configuraciones del calendario
        calendar_settings = _get_calendar_settings(ally_profile)
        
        # Calcular rango de fechas según la vista
        date_range = _calculate_view_date_range(target_date, view_type)
        
        # Obtener eventos del período
        calendar_events = _get_calendar_events(
            ally_profile, 
            date_range['start'], 
            date_range['end'],
            include_availability=True
        )
        
        # Obtener disponibilidad del período
        availability_slots = _get_availability_slots(
            ally_profile,
            date_range['start'],
            date_range['end']
        )
        
        # Detectar conflictos
        conflicts = _detect_calendar_conflicts(calendar_events)
        
        # Estadísticas del período
        period_stats = _calculate_period_statistics(
            ally_profile,
            date_range['start'],
            date_range['end']
        )
        
        # Próximos eventos importantes
        upcoming_important_events = _get_upcoming_important_events(ally_profile)
        
        # Sugerencias de optimización
        time_optimization_suggestions = _generate_time_optimization_suggestions(
            ally_profile, calendar_events, availability_slots
        )
        
        # Formularios auxiliares
        quick_event_form = QuickEventForm()
        availability_form = AvailabilityForm()
        
        # Navegación de fechas
        navigation_dates = _calculate_navigation_dates(target_date, view_type)
        
        # Datos para el calendario interactivo
        calendar_data = _prepare_calendar_data(
            calendar_events, availability_slots, view_type, calendar_settings
        )
        
        # Integraciones activas
        active_integrations = _get_active_calendar_integrations(ally_profile)
        
        return render_template(
            'ally/calendar/view.html',
            view_type=view_type,
            target_date=target_date,
            date_range=date_range,
            calendar_events=calendar_events,
            availability_slots=availability_slots,
            conflicts=conflicts,
            period_stats=period_stats,
            upcoming_important_events=upcoming_important_events,
            time_optimization_suggestions=time_optimization_suggestions,
            quick_event_form=quick_event_form,
            availability_form=availability_form,
            navigation_dates=navigation_dates,
            calendar_data=calendar_data,
            calendar_settings=calendar_settings,
            active_integrations=active_integrations,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de calendario: {str(e)}")
        flash('Error al cargar el calendario', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_calendar_bp.route('/availability')
@login_required
@require_ally_access
@track_ally_activity('availability_management', 'Gestión de disponibilidad')
def availability_management():
    """
    Vista de gestión de disponibilidad del aliado.
    
    Permite configurar horarios disponibles, crear bloques recurrentes,
    gestionar excepciones y establecer reglas de disponibilidad.
    
    Returns:
        Template con gestión de disponibilidad
    """
    try:
        ally_profile = g.ally_profile
        
        # Formularios de disponibilidad
        availability_form = AvailabilityForm()
        bulk_availability_form = BulkAvailabilityForm()
        recurring_form = RecurringAvailabilityForm()
        
        # Disponibilidad actual organizada
        current_availability = _get_organized_availability(ally_profile)
        
        # Plantillas de disponibilidad
        availability_templates = _get_availability_templates(ally_profile)
        
        # Estadísticas de utilización
        utilization_stats = _calculate_availability_utilization(ally_profile)
        
        # Próximas reservas
        upcoming_bookings = _get_upcoming_availability_bookings(ally_profile)
        
        # Análisis de patrones
        availability_patterns = _analyze_availability_patterns(ally_profile)
        
        # Configuraciones de disponibilidad
        availability_settings = _get_availability_settings(ally_profile)
        
        # Conflictos detectados
        availability_conflicts = _detect_availability_conflicts(ally_profile)
        
        # Sugerencias de optimización
        optimization_suggestions = _generate_availability_optimization_suggestions(
            ally_profile, utilization_stats
        )
        
        return render_template(
            'ally/calendar/availability.html',
            availability_form=availability_form,
            bulk_availability_form=bulk_availability_form,
            recurring_form=recurring_form,
            current_availability=current_availability,
            availability_templates=availability_templates,
            utilization_stats=utilization_stats,
            upcoming_bookings=upcoming_bookings,
            availability_patterns=availability_patterns,
            availability_settings=availability_settings,
            availability_conflicts=availability_conflicts,
            optimization_suggestions=optimization_suggestions,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en gestión de disponibilidad: {str(e)}")
        flash('Error al cargar la gestión de disponibilidad', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


@ally_calendar_bp.route('/integrations')
@login_required
@require_ally_access
@track_ally_activity('calendar_integrations', 'Integraciones de calendario')
def calendar_integrations():
    """
    Vista de gestión de integraciones de calendario externo.
    
    Permite conectar con Google Calendar, Outlook, y otros servicios
    para sincronización bidireccional de eventos.
    
    Returns:
        Template con gestión de integraciones
    """
    try:
        ally_profile = g.ally_profile
        
        # Integraciones configuradas
        configured_integrations = _get_configured_integrations(ally_profile)
        
        # Integraciones disponibles
        available_integrations = _get_available_integrations()
        
        # Estado de sincronización
        sync_status = _get_sync_status(ally_profile)
        
        # Historial de sincronización
        sync_history = _get_sync_history(ally_profile)
        
        # Configuraciones de sincronización
        sync_settings = _get_sync_settings(ally_profile)
        
        # Estadísticas de uso
        integration_stats = _calculate_integration_statistics(ally_profile)
        
        # Formulario de configuración
        integration_form = CalendarIntegrationForm()
        
        # Errores recientes de sincronización
        recent_sync_errors = _get_recent_sync_errors(ally_profile)
        
        return render_template(
            'ally/calendar/integrations.html',
            configured_integrations=configured_integrations,
            available_integrations=available_integrations,
            sync_status=sync_status,
            sync_history=sync_history,
            sync_settings=sync_settings,
            integration_stats=integration_stats,
            integration_form=integration_form,
            recent_sync_errors=recent_sync_errors,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en integraciones de calendario: {str(e)}")
        flash('Error al cargar las integraciones', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


@ally_calendar_bp.route('/analytics')
@login_required
@require_ally_access
@track_ally_activity('calendar_analytics', 'Analytics de calendario')
def calendar_analytics():
    """
    Vista de analytics avanzados del calendario.
    
    Muestra métricas de uso del tiempo, patrones de disponibilidad,
    eficiencia de programación y insights de optimización.
    
    Returns:
        Template con analytics del calendario
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
        
        # Métricas de uso del tiempo
        time_usage_metrics = analytics_service.get_time_usage_metrics(
            ally_profile.id, start_date, end_date
        )
        
        # Análisis de disponibilidad
        availability_analysis = _analyze_availability_effectiveness(
            ally_profile, start_date, end_date
        )
        
        # Patrones temporales
        temporal_patterns = _identify_temporal_patterns(
            ally_profile, start_date, end_date
        )
        
        # Eficiencia de programación
        scheduling_efficiency = _calculate_scheduling_efficiency(
            ally_profile, start_date, end_date
        )
        
        # Análisis de conflictos
        conflict_analysis = _analyze_calendar_conflicts_trends(
            ally_profile, start_date, end_date
        )
        
        # ROI de tiempo disponible
        availability_roi = _calculate_availability_roi(
            ally_profile, start_date, end_date
        )
        
        # Comparativas con benchmarks
        benchmark_comparison = _get_calendar_benchmarks(
            ally_profile, start_date, end_date
        )
        
        # Recomendaciones de optimización
        optimization_insights = _generate_calendar_optimization_insights(
            ally_profile, time_usage_metrics, availability_analysis
        )
        
        # Datos para gráficos
        charts_data = _prepare_calendar_charts_data(
            ally_profile, start_date, end_date
        )
        
        # Predicciones de demanda
        demand_predictions = _predict_availability_demand(
            ally_profile, start_date, end_date
        )
        
        return render_template(
            'ally/calendar/analytics.html',
            time_usage_metrics=time_usage_metrics,
            availability_analysis=availability_analysis,
            temporal_patterns=temporal_patterns,
            scheduling_efficiency=scheduling_efficiency,
            conflict_analysis=conflict_analysis,
            availability_roi=availability_roi,
            benchmark_comparison=benchmark_comparison,
            optimization_insights=optimization_insights,
            charts_data=charts_data,
            demand_predictions=demand_predictions,
            current_period=period,
            analysis_type=analysis_type,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics de calendario: {str(e)}")
        flash('Error al cargar analytics del calendario', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


@ally_calendar_bp.route('/settings')
@login_required
@require_ally_access
@track_ally_activity('calendar_settings', 'Configuraciones de calendario')
def calendar_settings():
    """
    Vista de configuraciones del calendario.
    
    Permite personalizar preferencias del calendario, zonas horarias,
    notificaciones y comportamientos del sistema.
    
    Returns:
        Template con configuraciones del calendario
    """
    try:
        ally_profile = g.ally_profile
        
        # Formulario de configuraciones
        settings_form = CalendarSettingsForm(obj=ally_profile)
        
        # Configuraciones actuales
        current_settings = _get_current_calendar_settings(ally_profile)
        
        # Opciones de configuración
        settings_options = _get_calendar_settings_options()
        
        # Plantillas de disponibilidad
        availability_templates = _get_availability_templates(ally_profile)
        
        # Configuraciones de notificaciones
        notification_settings = _get_calendar_notification_settings(ally_profile)
        
        # Zonas horarias disponibles
        available_timezones = _get_available_timezones()
        
        return render_template(
            'ally/calendar/settings.html',
            settings_form=settings_form,
            current_settings=current_settings,
            settings_options=settings_options,
            availability_templates=availability_templates,
            notification_settings=notification_settings,
            available_timezones=available_timezones,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en configuraciones de calendario: {str(e)}")
        flash('Error al cargar las configuraciones', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


# ==================== GESTIÓN DE DISPONIBILIDAD ====================

@ally_calendar_bp.route('/availability/add', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('availability_add', 'Adición de disponibilidad')
def add_availability():
    """
    Añade nuevo slot de disponibilidad.
    
    Returns:
        Redirección con confirmación o error
    """
    try:
        ally_profile = g.ally_profile
        form = AvailabilityForm()
        
        if form.validate_on_submit():
            # Crear slot de disponibilidad
            availability_data = {
                'ally_id': ally_profile.id,
                'date': form.date.data,
                'start_time': form.start_time.data,
                'end_time': form.end_time.data,
                'slot_duration': form.slot_duration.data,
                'max_bookings': form.max_bookings.data,
                'is_recurring': form.is_recurring.data,
                'recurrence_pattern': form.recurrence_pattern.data if form.is_recurring.data else None,
                'notes': form.notes.data
            }
            
            # Usar servicio de calendario
            calendar_service = CalendarService()
            result = calendar_service.add_availability(availability_data)
            
            if result['success']:
                # Sincronizar con calendarios externos si está habilitado
                _sync_availability_to_external_calendars(ally_profile, result['slots'])
                
                # Registrar actividad
                _log_availability_added(ally_profile, availability_data)
                
                flash('Disponibilidad añadida exitosamente', 'success')
                return redirect(url_for('ally_calendar.availability_management'))
            else:
                flash(f'Error añadiendo disponibilidad: {result["error"]}', 'error')
        else:
            flash('Error en los datos del formulario', 'error')
        
        return redirect(url_for('ally_calendar.availability_management'))
        
    except Exception as e:
        current_app.logger.error(f"Error añadiendo disponibilidad: {str(e)}")
        flash('Error interno al añadir disponibilidad', 'error')
        return redirect(url_for('ally_calendar.availability_management'))


@ally_calendar_bp.route('/availability/bulk', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('availability_bulk_add', 'Adición masiva de disponibilidad')
def add_bulk_availability():
    """
    Añade disponibilidad de forma masiva.
    
    Returns:
        Redirección con confirmación o error
    """
    try:
        ally_profile = g.ally_profile
        form = BulkAvailabilityForm()
        
        if form.validate_on_submit():
            # Datos de disponibilidad masiva
            bulk_data = {
                'ally_id': ally_profile.id,
                'start_date': form.start_date.data,
                'end_date': form.end_date.data,
                'days_of_week': form.days_of_week.data,
                'start_time': form.start_time.data,
                'end_time': form.end_time.data,
                'slot_duration': form.slot_duration.data,
                'break_duration': form.break_duration.data,
                'exclude_dates': form.exclude_dates.data.split(',') if form.exclude_dates.data else []
            }
            
            # Usar servicio de calendario
            calendar_service = CalendarService()
            result = calendar_service.add_bulk_availability(bulk_data)
            
            if result['success']:
                slots_created = result['slots_created']
                
                # Sincronizar con calendarios externos
                _sync_bulk_availability_to_external_calendars(ally_profile, result['slots'])
                
                # Registrar actividad
                _log_bulk_availability_added(ally_profile, bulk_data, slots_created)
                
                flash(f'Se crearon {slots_created} slots de disponibilidad exitosamente', 'success')
                return redirect(url_for('ally_calendar.availability_management'))
            else:
                flash(f'Error en creación masiva: {result["error"]}', 'error')
        else:
            flash('Error en los datos del formulario', 'error')
        
        return redirect(url_for('ally_calendar.availability_management'))
        
    except Exception as e:
        current_app.logger.error(f"Error en adición masiva: {str(e)}")
        flash('Error interno en adición masiva', 'error')
        return redirect(url_for('ally_calendar.availability_management'))


@ally_calendar_bp.route('/availability/<int:slot_id>/delete', methods=['DELETE'])
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
def delete_availability_slot(slot_id):
    """
    Elimina un slot de disponibilidad específico.
    
    Args:
        slot_id: ID del slot a eliminar
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar que el slot pertenece al aliado
        slot = AvailabilitySlot.query.filter_by(
            id=slot_id,
            ally_id=ally_profile.id
        ).first()
        
        if not slot:
            return jsonify({'error': 'Slot de disponibilidad no encontrado'}), 404
        
        # Verificar si hay reservas confirmadas
        if _has_confirmed_bookings(slot):
            return jsonify({
                'error': 'No se puede eliminar un slot con reservas confirmadas'
            }), 400
        
        # Eliminar slot
        db.session.delete(slot)
        db.session.commit()
        
        # Sincronizar eliminación con calendarios externos
        _sync_availability_deletion_to_external_calendars(ally_profile, slot)
        
        # Registrar actividad
        _log_availability_deleted(ally_profile, slot)
        
        return jsonify({
            'success': True,
            'message': 'Slot de disponibilidad eliminado exitosamente'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando slot: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== API ENDPOINTS ====================

@ally_calendar_bp.route('/api/events')
@login_required
@require_ally_access
@rate_limit(calls=60, period=60)
@require_json
def api_get_calendar_events():
    """
    API endpoint para obtener eventos del calendario.
    
    Returns:
        JSON con eventos del calendario
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros
        start_date_str = request.args.get('start')
        end_date_str = request.args.get('end')
        event_types = request.args.getlist('types')
        include_availability = request.args.get('include_availability', 'true').lower() == 'true'
        
        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Fechas de inicio y fin son requeridas'}), 400
        
        # Parsear fechas
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Verificar cache
        cache_key_val = f"ally_calendar_events_{ally_profile.id}_{start_date.date()}_{end_date.date()}"
        cached_events = get_cached(cache_key_val)
        
        if cached_events:
            return jsonify({
                'success': True,
                'events': cached_events,
                'cached': True
            })
        
        # Obtener eventos
        events = _get_calendar_events_api_format(
            ally_profile, start_date, end_date, event_types, include_availability
        )
        
        # Cachear por 5 minutos
        set_cached(cache_key_val, events, timeout=300)
        
        return jsonify({
            'success': True,
            'events': events,
            'cached': False
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error obteniendo eventos de calendario: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_calendar_bp.route('/api/availability/check', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_check_availability():
    """
    API endpoint para verificar disponibilidad en una fecha/hora específica.
    
    Returns:
        JSON con estado de disponibilidad
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        date_str = data.get('date')
        time_str = data.get('time')
        duration = data.get('duration', 60)  # minutos
        
        if not date_str or not time_str:
            return jsonify({'error': 'Fecha y hora son requeridas'}), 400
        
        # Parsear fecha y hora
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        check_time = datetime.strptime(time_str, '%H:%M').time()
        check_datetime = datetime.combine(check_date, check_time)
        
        # Verificar disponibilidad
        availability_result = _check_specific_availability(
            ally_profile, check_datetime, duration
        )
        
        return jsonify({
            'success': True,
            'available': availability_result['available'],
            'conflicts': availability_result['conflicts'],
            'alternative_slots': availability_result['alternatives'],
            'details': availability_result['details']
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha u hora no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error verificando disponibilidad: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_calendar_bp.route('/api/event/quick-create', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
@require_json
def api_quick_create_event():
    """
    API endpoint para crear evento rápido en el calendario.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['title', 'start_datetime', 'duration']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Faltan campos requeridos'}), 400
        
        # Datos del evento
        event_data = {
            'ally_id': ally_profile.id,
            'title': data['title'],
            'description': data.get('description', ''),
            'start_datetime': datetime.fromisoformat(data['start_datetime']),
            'duration_minutes': data['duration'],
            'event_type': data.get('type', 'personal'),
            'location': data.get('location', ''),
            'is_public': data.get('is_public', False)
        }
        
        # Verificar conflictos
        conflicts = _check_event_conflicts(ally_profile, event_data)
        if conflicts and not data.get('force_create', False):
            return jsonify({
                'success': False,
                'conflicts': conflicts,
                'message': 'Se detectaron conflictos. ¿Deseas crear el evento de todas formas?'
            }), 409
        
        # Crear evento
        calendar_service = CalendarService()
        result = calendar_service.create_quick_event(event_data)
        
        if result['success']:
            event = result['event']
            
            # Sincronizar con calendarios externos
            _sync_event_to_external_calendars(ally_profile, event)
            
            # Registrar actividad
            _log_event_created(ally_profile, event)
            
            return jsonify({
                'success': True,
                'message': 'Evento creado exitosamente',
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'start_datetime': event.start_datetime.isoformat(),
                    'end_datetime': event.end_datetime.isoformat()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error creando evento rápido: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_calendar_bp.route('/api/event/<int:event_id>/move', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=15, period=60)
@require_json
def api_move_event(event_id):
    """
    API endpoint para mover evento (drag & drop).
    
    Args:
        event_id: ID del evento
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        # Verificar que el evento pertenece al aliado
        event = CalendarEvent.query.filter_by(
            id=event_id,
            ally_id=ally_profile.id
        ).first()
        
        if not event:
            return jsonify({'error': 'Evento no encontrado'}), 404
        
        # Nueva fecha y hora
        new_start_str = data.get('new_start')
        if not new_start_str:
            return jsonify({'error': 'Nueva fecha de inicio es requerida'}), 400
        
        new_start = datetime.fromisoformat(new_start_str)
        duration_delta = event.end_datetime - event.start_datetime
        new_end = new_start + duration_delta
        
        # Verificar conflictos en la nueva posición
        conflicts = _check_event_move_conflicts(ally_profile, event, new_start, new_end)
        if conflicts and not data.get('force_move', False):
            return jsonify({
                'success': False,
                'conflicts': conflicts,
                'message': 'Se detectaron conflictos en la nueva posición'
            }), 409
        
        # Mover evento
        old_start = event.start_datetime
        old_end = event.end_datetime
        
        event.start_datetime = new_start
        event.end_datetime = new_end
        event.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Sincronizar movimiento con calendarios externos
        _sync_event_move_to_external_calendars(ally_profile, event, old_start, old_end)
        
        # Registrar actividad
        _log_event_moved(ally_profile, event, old_start, new_start)
        
        return jsonify({
            'success': True,
            'message': 'Evento movido exitosamente',
            'new_start': new_start.isoformat(),
            'new_end': new_end.isoformat()
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error moviendo evento: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_calendar_bp.route('/api/sync/external', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=5, period=60)
@require_json
def api_sync_external_calendar():
    """
    API endpoint para sincronizar con calendario externo.
    
    Returns:
        JSON con resultado de la sincronización
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        provider = data.get('provider')  # google, outlook, etc.
        sync_direction = data.get('direction', 'bidirectional')  # import, export, bidirectional
        
        if not provider:
            return jsonify({'error': 'Proveedor de calendario es requerido'}), 400
        
        # Usar servicio de calendario
        calendar_service = CalendarService()
        result = calendar_service.sync_external_calendar(
            ally_profile.id, provider, sync_direction
        )
        
        if result['success']:
            # Registrar sincronización
            _log_calendar_sync(ally_profile, provider, result)
            
            return jsonify({
                'success': True,
                'message': 'Sincronización completada exitosamente',
                'stats': result['stats']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error en sincronización: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_calendar_bp.route('/api/time-blocks')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_get_time_blocks():
    """
    API endpoint para obtener bloques de tiempo del aliado.
    
    Returns:
        JSON con bloques de tiempo
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': 'Fecha es requerida'}), 400
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Obtener bloques de tiempo
        time_blocks = _get_time_blocks_for_date(ally_profile, target_date)
        
        return jsonify({
            'success': True,
            'time_blocks': time_blocks,
            'date': target_date.isoformat()
        })
        
    except ValueError as e:
        return jsonify({'error': 'Formato de fecha no válido'}), 400
    except Exception as e:
        current_app.logger.error(f"Error obteniendo bloques de tiempo: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== INTEGRACIONES EXTERNAS ====================

@ally_calendar_bp.route('/integration/<provider>/connect')
@login_required
@require_ally_access
@track_ally_activity('calendar_integration_connect', 'Conexión de integración')
def connect_calendar_integration(provider):
    """
    Inicia conexión con proveedor de calendario externo.
    
    Args:
        provider: Proveedor de calendario (google, outlook, etc.)
        
    Returns:
        Redirección a proceso de autorización
    """
    try:
        ally_profile = g.ally_profile
        
        # Validar proveedor
        if provider not in ['google', 'outlook', 'apple']:
            flash('Proveedor de calendario no soportado', 'error')
            return redirect(url_for('ally_calendar.calendar_integrations'))
        
        # Usar servicio específico del proveedor
        if provider == 'google':
            google_service = GoogleCalendarService()
            auth_url = google_service.get_authorization_url(ally_profile.user_id)
            
            # Guardar estado de autorización
            session[f'calendar_auth_state_{provider}'] = {
                'user_id': ally_profile.user_id,
                'provider': provider,
                'initiated_at': datetime.utcnow().isoformat()
            }
            
            return redirect(auth_url)
        
        else:
            flash(f'Integración con {provider} en desarrollo', 'info')
            return redirect(url_for('ally_calendar.calendar_integrations'))
            
    except Exception as e:
        current_app.logger.error(f"Error conectando integración {provider}: {str(e)}")
        flash('Error al conectar integración', 'error')
        return redirect(url_for('ally_calendar.calendar_integrations'))


@ally_calendar_bp.route('/integration/<provider>/callback')
@login_required
@require_ally_access
def calendar_integration_callback(provider):
    """
    Callback para autorización de calendario externo.
    
    Args:
        provider: Proveedor de calendario
        
    Returns:
        Redirección con resultado de la autorización
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar estado de autorización
        auth_state = session.get(f'calendar_auth_state_{provider}')
        if not auth_state or auth_state['user_id'] != ally_profile.user_id:
            flash('Estado de autorización inválido', 'error')
            return redirect(url_for('ally_calendar.calendar_integrations'))
        
        # Procesar callback según el proveedor
        if provider == 'google':
            google_service = GoogleCalendarService()
            
            # Obtener código de autorización
            auth_code = request.args.get('code')
            if not auth_code:
                flash('Autorización cancelada o fallida', 'error')
                return redirect(url_for('ally_calendar.calendar_integrations'))
            
            # Intercambiar código por tokens
            result = google_service.exchange_code_for_tokens(auth_code, ally_profile.user_id)
            
            if result['success']:
                # Crear integración
                integration = CalendarIntegration(
                    ally_id=ally_profile.id,
                    provider=provider,
                    provider_account_id=result['account_id'],
                    access_token=result['access_token'],
                    refresh_token=result['refresh_token'],
                    token_expires_at=result['expires_at'],
                    is_active=True,
                    sync_settings={
                        'sync_direction': 'bidirectional',
                        'auto_sync': True,
                        'sync_frequency': 'real_time'
                    }
                )
                
                db.session.add(integration)
                db.session.commit()
                
                # Realizar sincronización inicial
                _perform_initial_sync(ally_profile, integration)
                
                # Limpiar estado de sesión
                session.pop(f'calendar_auth_state_{provider}', None)
                
                # Registrar conexión
                _log_integration_connected(ally_profile, provider)
                
                flash(f'Integración con {provider.title()} conectada exitosamente', 'success')
            else:
                flash(f'Error conectando con {provider}: {result["error"]}', 'error')
        
        return redirect(url_for('ally_calendar.calendar_integrations'))
        
    except Exception as e:
        current_app.logger.error(f"Error en callback de {provider}: {str(e)}")
        flash('Error procesando autorización', 'error')
        return redirect(url_for('ally_calendar.calendar_integrations'))


@ally_calendar_bp.route('/integration/<int:integration_id>/disconnect', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('calendar_integration_disconnect', 'Desconexión de integración')
def disconnect_calendar_integration(integration_id):
    """
    Desconecta una integración de calendario.
    
    Args:
        integration_id: ID de la integración
        
    Returns:
        Redirección con confirmación
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar que la integración pertenece al aliado
        integration = CalendarIntegration.query.filter_by(
            id=integration_id,
            ally_id=ally_profile.id
        ).first()
        
        if not integration:
            flash('Integración no encontrada', 'error')
            return redirect(url_for('ally_calendar.calendar_integrations'))
        
        # Revocar tokens si es necesario
        if integration.provider == 'google':
            google_service = GoogleCalendarService()
            google_service.revoke_tokens(integration.access_token)
        
        # Desactivar integración
        integration.is_active = False
        integration.disconnected_at = datetime.utcnow()
        
        db.session.commit()
        
        # Registrar desconexión
        _log_integration_disconnected(ally_profile, integration.provider)
        
        flash(f'Integración con {integration.provider.title()} desconectada', 'success')
        return redirect(url_for('ally_calendar.calendar_integrations'))
        
    except Exception as e:
        current_app.logger.error(f"Error desconectando integración: {str(e)}")
        flash('Error al desconectar integración', 'error')
        return redirect(url_for('ally_calendar.calendar_integrations'))


# ==================== EXPORTACIÓN ====================

@ally_calendar_bp.route('/export/ical')
@login_required
@require_ally_access
@track_ally_activity('calendar_export_ical', 'Exportación de calendario a iCal')
def export_calendar_ical():
    """
    Exporta calendario en formato iCal (.ics).
    
    Returns:
        Archivo iCal con eventos del calendario
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de exportación
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        include_availability = request.args.get('include_availability', 'false').lower() == 'true'
        
        # Establecer rango de fechas (por defecto 6 meses)
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
            end_date = datetime.utcnow() + timedelta(days=180)
        
        # Obtener eventos para exportación
        events = _get_events_for_export(ally_profile, start_date, end_date, include_availability)
        
        # Generar iCal
        ical_content = export_to_ical(events, ally_profile.user.full_name)
        
        response = make_response(ical_content)
        response.headers['Content-Type'] = 'text/calendar'
        response.headers['Content-Disposition'] = 'attachment; filename=calendario_aliado.ics'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando iCal: {str(e)}")
        flash('Error al exportar calendario', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


@ally_calendar_bp.route('/export/pdf')
@login_required
@require_ally_access
@track_ally_activity('calendar_export_pdf', 'Exportación de calendario a PDF')
def export_calendar_pdf():
    """
    Exporta vista del calendario en formato PDF.
    
    Returns:
        Archivo PDF con vista del calendario
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de exportación
        view_type = request.args.get('view', 'month')
        target_date_str = request.args.get('date')
        
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today()
        
        # Calcular rango según la vista
        date_range = _calculate_view_date_range(target_date, view_type)
        
        # Obtener datos para el PDF
        pdf_data = _generate_calendar_pdf_data(
            ally_profile, date_range, view_type
        )
        
        # Generar PDF
        pdf_content = export_to_pdf(
            template='reports/calendar_view_report.html',
            data=pdf_data,
            filename=f'calendario_{view_type}_{target_date}'
        )
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=calendario_{view_type}_{target_date}.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando PDF: {str(e)}")
        flash('Error al exportar calendario', 'error')
        return redirect(url_for('ally_calendar.calendar_view'))


# ==================== FUNCIONES AUXILIARES ====================

def _get_calendar_settings(ally: Ally) -> Dict[str, Any]:
    """
    Obtiene configuraciones del calendario del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con configuraciones del calendario
    """
    return {
        'timezone': ally.timezone or DEFAULT_TIMEZONE,
        'default_view': getattr(ally, 'calendar_default_view', DEFAULT_VIEW),
        'work_hours_start': getattr(ally, 'work_hours_start', time(9, 0)),
        'work_hours_end': getattr(ally, 'work_hours_end', time(17, 0)),
        'work_days': getattr(ally, 'work_days', [1, 2, 3, 4, 5]),  # Monday to Friday
        'slot_duration': getattr(ally, 'default_slot_duration', 60),
        'buffer_time': getattr(ally, 'buffer_time_minutes', 15),
        'advance_booking_days': getattr(ally, 'advance_booking_days', 30),
        'colors': CALENDAR_COLORS,
        'notifications_enabled': getattr(ally, 'calendar_notifications', True)
    }


def _calculate_view_date_range(target_date: date, view_type: str) -> Dict[str, date]:
    """
    Calcula el rango de fechas para una vista específica.
    
    Args:
        target_date: Fecha objetivo
        view_type: Tipo de vista
        
    Returns:
        Dict con fechas de inicio y fin
    """
    if view_type == 'month':
        start_date = target_date.replace(day=1)
        if target_date.month == 12:
            end_date = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)
    
    elif view_type == 'week':
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
    
    elif view_type == 'day':
        start_date = target_date
        end_date = target_date
    
    elif view_type == 'agenda':
        start_date = target_date
        end_date = target_date + timedelta(days=30)
    
    else:
        # Default to month view
        start_date = target_date.replace(day=1)
        if target_date.month == 12:
            end_date = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)
    
    return {
        'start': start_date,
        'end': end_date
    }


def _get_calendar_events(ally: Ally, start_date: date, end_date: date, include_availability: bool = False) -> List[Dict[str, Any]]:
    """
    Obtiene eventos del calendario para un rango de fechas.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        include_availability: Si incluir slots de disponibilidad
        
    Returns:
        Lista de eventos del calendario
    """
    events = []
    
    # Sesiones de mentoría
    mentorship_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).options(joinedload(MentorshipSession.entrepreneur).joinedload(Entrepreneur.user)).all()
    
    for session in mentorship_sessions:
        start_datetime = datetime.combine(session.session_date, session.start_time or time(9, 0))
        end_datetime = start_datetime + timedelta(hours=session.duration_hours or 1)
        
        events.append({
            'id': f'session_{session.id}',
            'title': f'Mentoría: {session.topic or session.entrepreneur.user.full_name}',
            'start': start_datetime,
            'end': end_datetime,
            'type': EventType.MENTORSHIP_SESSION.value,
            'status': session.status,
            'entrepreneur_name': session.entrepreneur.user.full_name,
            'color': CALENDAR_COLORS['mentorship'],
            'url': url_for('ally_mentorship.session_detail', session_id=session.id)
        })
    
    # Reuniones
    meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at).between(start_date, end_date)
    ).options(joinedload(Meeting.entrepreneur).joinedload(Entrepreneur.user)).all()
    
    for meeting in meetings:
        end_datetime = meeting.scheduled_at + timedelta(minutes=meeting.duration_minutes or 60)
        
        events.append({
            'id': f'meeting_{meeting.id}',
            'title': f'Reunión: {meeting.title}',
            'start': meeting.scheduled_at,
            'end': end_datetime,
            'type': EventType.MEETING.value,
            'status': meeting.status,
            'participant': meeting.entrepreneur.user.full_name if meeting.entrepreneur else 'N/A',
            'color': CALENDAR_COLORS['meeting'],
            'url': url_for('ally.meetings.detail', meeting_id=meeting.id)
        })
    
    # Eventos de calendario personalizados
    calendar_events = CalendarEvent.query.filter(
        CalendarEvent.ally_id == ally.id,
        func.date(CalendarEvent.start_datetime).between(start_date, end_date)
    ).all()
    
    for event in calendar_events:
        events.append({
            'id': f'event_{event.id}',
            'title': event.title,
            'start': event.start_datetime,
            'end': event.end_datetime,
            'type': event.event_type,
            'description': event.description,
            'location': event.location,
            'color': CALENDAR_COLORS.get(event.event_type, CALENDAR_COLORS['personal'])
        })
    
    # Slots de disponibilidad si se solicitan
    if include_availability:
        availability_slots = AvailabilitySlot.query.filter(
            AvailabilitySlot.ally_id == ally.id,
            AvailabilitySlot.date.between(start_date, end_date),
            AvailabilitySlot.is_active == True
        ).all()
        
        for slot in availability_slots:
            start_datetime = datetime.combine(slot.date, slot.start_time)
            end_datetime = datetime.combine(slot.date, slot.end_time)
            
            events.append({
                'id': f'availability_{slot.id}',
                'title': 'Disponible',
                'start': start_datetime,
                'end': end_datetime,
                'type': EventType.AVAILABILITY.value,
                'slots_available': slot.slots_available,
                'slots_booked': slot.slots_booked,
                'color': CALENDAR_COLORS['available'],
                'display': 'background'  # Para mostrar como fondo
            })
    
    return sorted(events, key=lambda x: x['start'])


def _get_availability_slots(ally: Ally, start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Obtiene slots de disponibilidad para un rango de fechas.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Lista de slots de disponibilidad
    """
    slots = AvailabilitySlot.query.filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date, end_date),
        AvailabilitySlot.is_active == True
    ).order_by(AvailabilitySlot.date, AvailabilitySlot.start_time).all()
    
    slots_data = []
    for slot in slots:
        slots_data.append({
            'id': slot.id,
            'date': slot.date,
            'start_time': slot.start_time,
            'end_time': slot.end_time,
            'duration_minutes': slot.duration_minutes,
            'slots_total': slot.slots_total,
            'slots_available': slot.slots_available,
            'slots_booked': slot.slots_booked,
            'is_recurring': slot.is_recurring,
            'booking_url': url_for('public.book_session', ally_id=ally.id, slot_id=slot.id) if slot.is_bookable else None
        })
    
    return slots_data


def _detect_calendar_conflicts(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detecta conflictos entre eventos del calendario.
    
    Args:
        events: Lista de eventos
        
    Returns:
        Lista de conflictos detectados
    """
    conflicts = []
    
    # Filtrar solo eventos que pueden tener conflictos (no de disponibilidad)
    conflictable_events = [
        e for e in events 
        if e['type'] not in [EventType.AVAILABILITY.value]
    ]
    
    for i, event1 in enumerate(conflictable_events):
        for event2 in conflictable_events[i+1:]:
            # Verificar solapamiento
            if (event1['start'] < event2['end'] and event2['start'] < event1['end']):
                conflicts.append({
                    'event1': event1,
                    'event2': event2,
                    'severity': 'high' if event1['start'] == event2['start'] else 'medium',
                    'overlap_duration': min(event1['end'], event2['end']) - max(event1['start'], event2['start'])
                })
    
    return conflicts


def _calculate_period_statistics(ally: Ally, start_date: date, end_date: date) -> Dict[str, Any]:
    """
    Calcula estadísticas del período para el calendario.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con estadísticas del período
    """
    # Total de días en el período
    total_days = (end_date - start_date).days + 1
    
    # Sesiones programadas
    total_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).count()
    
    # Reuniones programadas
    total_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at).between(start_date, end_date)
    ).count()
    
    # Horas totales comprometidas
    sessions_hours = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).scalar() or 0
    
    meetings_hours = db.session.query(
        func.sum(Meeting.duration_minutes)
    ).filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at).between(start_date, end_date)
    ).scalar() or 0
    
    total_committed_hours = float(sessions_hours) + float(meetings_hours / 60)
    
    # Disponibilidad total ofrecida
    availability_hours = db.session.query(
        func.sum(
            func.extract('epoch', AvailabilitySlot.end_time) - 
            func.extract('epoch', AvailabilitySlot.start_time)
        ) / 3600
    ).filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date, end_date)
    ).scalar() or 0
    
    # Tasa de utilización
    utilization_rate = (total_committed_hours / float(availability_hours) * 100) if availability_hours > 0 else 0
    
    return {
        'total_days': total_days,
        'total_sessions': total_sessions,
        'total_meetings': total_meetings,
        'total_events': total_sessions + total_meetings,
        'total_committed_hours': round(total_committed_hours, 2),
        'availability_hours': round(float(availability_hours), 2),
        'utilization_rate': round(utilization_rate, 1),
        'avg_events_per_day': round((total_sessions + total_meetings) / total_days, 2),
        'busy_days': _count_busy_days(ally, start_date, end_date)
    }


def _get_upcoming_important_events(ally: Ally, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtiene próximos eventos importantes del aliado.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de eventos
        
    Returns:
        Lista de próximos eventos importantes
    """
    upcoming_events = []
    
    # Próximas sesiones de mentoría
    upcoming_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= date.today(),
        MentorshipSession.status.in_(['scheduled', 'confirmed'])
    ).order_by(MentorshipSession.session_date, MentorshipSession.start_time).limit(limit).all()
    
    for session in upcoming_sessions:
        session_datetime = datetime.combine(session.session_date, session.start_time or time(9, 0))
        time_until = session_datetime - datetime.utcnow()
        
        upcoming_events.append({
            'title': f'Mentoría: {session.entrepreneur.user.full_name}',
            'datetime': session_datetime,
            'time_until': time_until,
            'type': 'mentorship_session',
            'is_urgent': time_until.total_seconds() < 3600,  # Menos de 1 hora
            'url': url_for('ally_mentorship.session_detail', session_id=session.id)
        })
    
    # Próximas reuniones
    upcoming_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at >= datetime.utcnow(),
        Meeting.status.in_(['scheduled', 'confirmed'])
    ).order_by(Meeting.scheduled_at).limit(limit).all()
    
    for meeting in upcoming_meetings:
        time_until = meeting.scheduled_at - datetime.utcnow()
        
        upcoming_events.append({
            'title': f'Reunión: {meeting.title}',
            'datetime': meeting.scheduled_at,
            'time_until': time_until,
            'type': 'meeting',
            'is_urgent': time_until.total_seconds() < 3600,
            'url': url_for('ally.meetings.detail', meeting_id=meeting.id)
        })
    
    # Ordenar por fecha y limitar
    upcoming_events.sort(key=lambda x: x['datetime'])
    return upcoming_events[:limit]


def _generate_time_optimization_suggestions(ally: Ally, events: List[Dict[str, Any]], availability: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Genera sugerencias para optimizar el uso del tiempo.
    
    Args:
        ally: Perfil del aliado
        events: Lista de eventos
        availability: Lista de disponibilidad
        
    Returns:
        Lista de sugerencias de optimización
    """
    suggestions = []
    
    # Analizar fragmentación del tiempo
    if _detect_time_fragmentation(events):
        suggestions.append({
            'type': 'fragmentation',
            'title': 'Tiempo fragmentado detectado',
            'description': 'Considera agrupar reuniones para crear bloques de tiempo más largos',
            'priority': 'medium'
        })
    
    # Analizar disponibilidad no utilizada
    unused_availability = _calculate_unused_availability(availability, events)
    if unused_availability > 50:  # Más del 50% sin usar
        suggestions.append({
            'type': 'underutilization',
            'title': 'Baja utilización de disponibilidad',
            'description': f'{unused_availability:.1f}% de tu disponibilidad no está siendo utilizada',
            'priority': 'low'
        })
    
    # Detectar sobrecarga
    if _detect_schedule_overload(events):
        suggestions.append({
            'type': 'overload',
            'title': 'Horario sobrecargado',
            'description': 'Considera redistribuir algunos eventos para un mejor balance',
            'priority': 'high'
        })
    
    return suggestions


def _prepare_calendar_data(events: List[Dict[str, Any]], availability: List[Dict[str, Any]], view_type: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara datos para el calendario interactivo.
    
    Args:
        events: Lista de eventos
        availability: Lista de disponibilidad
        view_type: Tipo de vista
        settings: Configuraciones del calendario
        
    Returns:
        Dict con datos preparados para el calendario
    """
    # Convertir eventos al formato requerido por el frontend
    calendar_events = []
    
    for event in events:
        calendar_events.append({
            'id': event['id'],
            'title': event['title'],
            'start': event['start'].isoformat(),
            'end': event['end'].isoformat(),
            'backgroundColor': event.get('color', CALENDAR_COLORS['personal']),
            'borderColor': event.get('color', CALENDAR_COLORS['personal']),
            'textColor': '#ffffff',
            'extendedProps': {
                'type': event['type'],
                'status': event.get('status'),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'url': event.get('url')
            }
        })
    
    # Agregar disponibilidad como eventos de fondo
    for slot in availability:
        start_datetime = datetime.combine(slot['date'], slot['start_time'])
        end_datetime = datetime.combine(slot['date'], slot['end_time'])
        
        calendar_events.append({
            'id': f"availability_{slot['id']}",
            'title': f"Disponible ({slot['slots_available']}/{slot['slots_total']})",
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'display': 'background',
            'backgroundColor': CALENDAR_COLORS['available'],
            'extendedProps': {
                'type': 'availability',
                'slots_available': slot['slots_available'],
                'slots_total': slot['slots_total']
            }
        })
    
    return {
        'events': calendar_events,
        'defaultView': view_type,
        'timezone': settings['timezone'],
        'businessHours': {
            'startTime': settings['work_hours_start'].strftime('%H:%M'),
            'endTime': settings['work_hours_end'].strftime('%H:%M'),
            'daysOfWeek': settings['work_days']
        },
        'slotDuration': f"00:{settings['slot_duration']:02d}:00",
        'colors': settings['colors']
    }


def _get_active_calendar_integrations(ally: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene integraciones de calendario activas.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de integraciones activas
    """
    integrations = CalendarIntegration.query.filter_by(
        ally_id=ally.id,
        is_active=True
    ).all()
    
    integrations_data = []
    for integration in integrations:
        last_sync = CalendarSync.query.filter_by(
            integration_id=integration.id
        ).order_by(desc(CalendarSync.created_at)).first()
        
        integrations_data.append({
            'provider': integration.provider,
            'account_id': integration.provider_account_id,
            'connected_at': integration.created_at,
            'last_sync': last_sync.created_at if last_sync else None,
            'sync_status': last_sync.status if last_sync else 'never',
            'auto_sync': integration.sync_settings.get('auto_sync', False)
        })
    
    return integrations_data


def _calculate_navigation_dates(target_date: date, view_type: str) -> Dict[str, date]:
    """
    Calcula fechas de navegación para el calendario.
    
    Args:
        target_date: Fecha objetivo
        view_type: Tipo de vista
        
    Returns:
        Dict con fechas de navegación
    """
    if view_type == 'month':
        if target_date.month == 1:
            prev_date = target_date.replace(year=target_date.year - 1, month=12)
        else:
            prev_date = target_date.replace(month=target_date.month - 1)
        
        if target_date.month == 12:
            next_date = target_date.replace(year=target_date.year + 1, month=1)
        else:
            next_date = target_date.replace(month=target_date.month + 1)
    
    elif view_type == 'week':
        prev_date = target_date - timedelta(days=7)
        next_date = target_date + timedelta(days=7)
    
    elif view_type == 'day':
        prev_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)
    
    else:
        prev_date = target_date - timedelta(days=30)
        next_date = target_date + timedelta(days=30)
    
    return {
        'previous': prev_date,
        'next': next_date,
        'today': date.today()
    }


# Funciones auxiliares adicionales (implementación básica)

def _get_organized_availability(ally: Ally) -> Dict[str, List[Dict[str, Any]]]:
    """Obtiene disponibilidad organizada por días de la semana."""
    # Implementación básica
    return {
        'monday': [],
        'tuesday': [],
        'wednesday': [],
        'thursday': [],
        'friday': [],
        'saturday': [],
        'sunday': []
    }


def _get_availability_templates(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene plantillas de disponibilidad del aliado."""
    # Implementación básica
    return []


def _calculate_availability_utilization(ally: Ally) -> Dict[str, Any]:
    """Calcula estadísticas de utilización de disponibilidad."""
    return {
        'utilization_rate': 65.5,
        'total_slots': 120,
        'booked_slots': 78,
        'available_slots': 42
    }


def _get_upcoming_availability_bookings(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene próximas reservas de disponibilidad."""
    return []


def _analyze_availability_patterns(ally: Ally) -> Dict[str, Any]:
    """Analiza patrones de disponibilidad y uso."""
    return {
        'peak_hours': ['14:00', '16:00'],
        'peak_days': ['Tuesday', 'Thursday'],
        'low_demand_periods': []
    }


def _get_availability_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones de disponibilidad."""
    return {
        'default_duration': 60,
        'buffer_time': 15,
        'advance_booking': 30,
        'cancellation_policy': '24h'
    }


def _detect_availability_conflicts(ally: Ally) -> List[Dict[str, Any]]:
    """Detecta conflictos en la disponibilidad."""
    return []


def _generate_availability_optimization_suggestions(ally: Ally, utilization_stats: Dict[str, Any]) -> List[Dict[str, str]]:
    """Genera sugerencias para optimizar disponibilidad."""
    suggestions = []
    
    if utilization_stats['utilization_rate'] < 50:
        suggestions.append({
            'type': 'underutilization',
            'title': 'Baja utilización detectada',
            'description': 'Considera ajustar tus horarios de disponibilidad',
            'priority': 'medium'
        })
    
    return suggestions


# Funciones para análisis y métricas

def _count_busy_days(ally: Ally, start_date: date, end_date: date) -> int:
    """Cuenta días con al menos un evento programado."""
    busy_days = db.session.query(
        func.count(func.distinct(MentorshipSession.session_date))
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).scalar()
    
    busy_meeting_days = db.session.query(
        func.count(func.distinct(func.date(Meeting.scheduled_at)))
    ).filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at).between(start_date, end_date)
    ).scalar()
    
    return busy_days + busy_meeting_days


def _detect_time_fragmentation(events: List[Dict[str, Any]]) -> bool:
    """Detecta si hay fragmentación excesiva en el horario."""
    # Implementación básica - verificar gaps pequeños entre eventos
    return False


def _calculate_unused_availability(availability: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> float:
    """Calcula porcentaje de disponibilidad no utilizada."""
    if not availability:
        return 0
    
    total_slots = sum(slot['slots_total'] for slot in availability)
    booked_slots = sum(slot['slots_booked'] for slot in availability)
    
    if total_slots == 0:
        return 0
    
    return ((total_slots - booked_slots) / total_slots) * 100


def _detect_schedule_overload(events: List[Dict[str, Any]]) -> bool:
    """Detecta si el horario está sobrecargado."""
    # Implementación básica - más de 8 horas de eventos por día
    daily_hours = defaultdict(float)
    
    for event in events:
        event_date = event['start'].date()
        duration = (event['end'] - event['start']).total_seconds() / 3600
        daily_hours[event_date] += duration
    
    return any(hours > 8 for hours in daily_hours.values())


# Funciones para APIs

def _get_calendar_events_api_format(ally: Ally, start_date: datetime, end_date: datetime, event_types: List[str], include_availability: bool) -> List[Dict[str, Any]]:
    """Obtiene eventos en formato para API."""
    events = _get_calendar_events(
        ally, start_date.date(), end_date.date(), include_availability
    )
    
    # Filtrar por tipos si se especifican
    if event_types:
        events = [e for e in events if e['type'] in event_types]
    
    # Convertir a formato API
    api_events = []
    for event in events:
        api_events.append({
            'id': event['id'],
            'title': event['title'],
            'start': event['start'].isoformat(),
            'end': event['end'].isoformat(),
            'type': event['type'],
            'status': event.get('status'),
            'color': event.get('color'),
            'url': event.get('url'),
            'metadata': {
                'description': event.get('description'),
                'location': event.get('location'),
                'participant': event.get('participant') or event.get('entrepreneur_name')
            }
        })
    
    return api_events


def _check_specific_availability(ally: Ally, check_datetime: datetime, duration: int) -> Dict[str, Any]:
    """Verifica disponibilidad específica para una fecha/hora."""
    check_date = check_datetime.date()
    check_time = check_datetime.time()
    
    # Buscar slot de disponibilidad
    availability_slot = AvailabilitySlot.query.filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date == check_date,
        AvailabilitySlot.start_time <= check_time,
        AvailabilitySlot.end_time >= check_time,
        AvailabilitySlot.is_active == True
    ).first()
    
    if not availability_slot:
        return {
            'available': False,
            'conflicts': ['No hay disponibilidad en este horario'],
            'alternatives': _find_alternative_slots(ally, check_datetime, duration),
            'details': {'reason': 'no_availability_slot'}
        }
    
    # Verificar conflictos con eventos existentes
    end_datetime = check_datetime + timedelta(minutes=duration)
    
    conflicts = []
    
    # Verificar sesiones de mentoría
    conflicting_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date == check_date
    ).all()
    
    for session in conflicting_sessions:
        session_start = datetime.combine(check_date, session.start_time or time(9, 0))
        session_end = session_start + timedelta(hours=session.duration_hours or 1)
        
        if (check_datetime < session_end and end_datetime > session_start):
            conflicts.append(f'Conflicto con sesión de mentoría: {session.topic}')
    
    # Verificar reuniones
    conflicting_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at) == check_date
    ).all()
    
    for meeting in conflicting_meetings:
        meeting_end = meeting.scheduled_at + timedelta(minutes=meeting.duration_minutes or 60)
        
        if (check_datetime < meeting_end and end_datetime > meeting.scheduled_at):
            conflicts.append(f'Conflicto con reunión: {meeting.title}')
    
    return {
        'available': len(conflicts) == 0 and availability_slot.slots_available > 0,
        'conflicts': conflicts,
        'alternatives': _find_alternative_slots(ally, check_datetime, duration) if conflicts else [],
        'details': {
            'slot_id': availability_slot.id,
            'slots_available': availability_slot.slots_available,
            'slots_total': availability_slot.slots_total
        }
    }


def _find_alternative_slots(ally: Ally, preferred_datetime: datetime, duration: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Encuentra slots alternativos cercanos a la fecha preferida."""
    alternatives = []
    search_date = preferred_datetime.date()
    
    # Buscar en los próximos 7 días
    for i in range(7):
        check_date = search_date + timedelta(days=i)
        
        # Obtener slots de disponibilidad para este día
        day_slots = AvailabilitySlot.query.filter(
            AvailabilitySlot.ally_id == ally.id,
            AvailabilitySlot.date == check_date,
            AvailabilitySlot.is_active == True,
            AvailabilitySlot.slots_available > 0
        ).all()
        
        for slot in day_slots:
            slot_datetime = datetime.combine(check_date, slot.start_time)
            
            # Verificar si no hay conflictos
            availability_check = _check_specific_availability(ally, slot_datetime, duration)
            
            if availability_check['available']:
                alternatives.append({
                    'datetime': slot_datetime.isoformat(),
                    'date': check_date.isoformat(),
                    'time': slot.start_time.strftime('%H:%M'),
                    'slots_available': slot.slots_available,
                    'days_from_preferred': i
                })
                
                if len(alternatives) >= limit:
                    return alternatives
    
    return alternatives


def _check_event_conflicts(ally: Ally, event_data: Dict[str, Any]) -> List[str]:
    """Verifica conflictos para un nuevo evento."""
    conflicts = []
    
    start_datetime = event_data['start_datetime']
    end_datetime = start_datetime + timedelta(minutes=event_data['duration_minutes'])
    event_date = start_datetime.date()
    
    # Verificar conflictos con sesiones existentes
    existing_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date == event_date
    ).all()
    
    for session in existing_sessions:
        session_start = datetime.combine(event_date, session.start_time or time(9, 0))
        session_end = session_start + timedelta(hours=session.duration_hours or 1)
        
        if start_datetime < session_end and end_datetime > session_start:
            conflicts.append(f'Conflicto con sesión: {session.topic}')
    
    # Verificar conflictos con reuniones
    existing_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at) == event_date
    ).all()
    
    for meeting in existing_meetings:
        meeting_end = meeting.scheduled_at + timedelta(minutes=meeting.duration_minutes or 60)
        
        if start_datetime < meeting_end and end_datetime > meeting.scheduled_at:
            conflicts.append(f'Conflicto con reunión: {meeting.title}')
    
    return conflicts


def _check_event_move_conflicts(ally: Ally, event: CalendarEvent, new_start: datetime, new_end: datetime) -> List[str]:
    """Verifica conflictos al mover un evento."""
    conflicts = []
    new_date = new_start.date()
    
    # Excluir el evento actual de la verificación
    existing_events = CalendarEvent.query.filter(
        CalendarEvent.ally_id == ally.id,
        CalendarEvent.id != event.id,
        func.date(CalendarEvent.start_datetime) == new_date
    ).all()
    
    for existing_event in existing_events:
        if new_start < existing_event.end_datetime and new_end > existing_event.start_datetime:
            conflicts.append(f'Conflicto con evento: {existing_event.title}')
    
    return conflicts


def _get_time_blocks_for_date(ally: Ally, target_date: date) -> List[Dict[str, Any]]:
    """Obtiene bloques de tiempo para una fecha específica."""
    # Esto requeriría un modelo TimeBlock
    return []


# Funciones para sincronización

def _sync_availability_to_external_calendars(ally: Ally, slots: List[Any]) -> None:
    """Sincroniza disponibilidad con calendarios externos."""
    # Implementación de sincronización
    pass


def _sync_bulk_availability_to_external_calendars(ally: Ally, slots: List[Any]) -> None:
    """Sincroniza disponibilidad masiva con calendarios externos."""
    pass


def _sync_availability_deletion_to_external_calendars(ally: Ally, slot: Any) -> None:
    """Sincroniza eliminación de disponibilidad con calendarios externos."""
    pass


def _sync_event_to_external_calendars(ally: Ally, event: Any) -> None:
    """Sincroniza evento con calendarios externos."""
    pass


def _sync_event_move_to_external_calendars(ally: Ally, event: Any, old_start: datetime, old_end: datetime) -> None:
    """Sincroniza movimiento de evento con calendarios externos."""
    pass


# Funciones para logging

def _log_availability_added(ally: Ally, availability_data: Dict[str, Any]) -> None:
    """Registra adición de disponibilidad."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='availability_added',
        description=f'Disponibilidad agregada para {availability_data["date"]}',
        entity_type='availability_slot',
        metadata=availability_data
    )
    db.session.add(activity)
    db.session.commit()


def _log_bulk_availability_added(ally: Ally, bulk_data: Dict[str, Any], slots_created: int) -> None:
    """Registra adición masiva de disponibilidad."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='bulk_availability_added',
        description=f'Creados {slots_created} slots de disponibilidad masivamente',
        entity_type='availability_bulk',
        metadata={**bulk_data, 'slots_created': slots_created}
    )
    db.session.add(activity)
    db.session.commit()


def _log_availability_deleted(ally: Ally, slot: Any) -> None:
    """Registra eliminación de disponibilidad."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='availability_deleted',
        description=f'Slot de disponibilidad eliminado para {slot.date}',
        entity_type='availability_slot',
        entity_id=slot.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_event_created(ally: Ally, event: Any) -> None:
    """Registra creación de evento."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='calendar_event_created',
        description=f'Evento creado: {event.title}',
        entity_type='calendar_event',
        entity_id=event.id
    )
    db.session.add(activity)
    db.session.commit()


def _log_event_moved(ally: Ally, event: Any, old_start: datetime, new_start: datetime) -> None:
    """Registra movimiento de evento."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='calendar_event_moved',
        description=f'Evento movido: {event.title}',
        entity_type='calendar_event',
        entity_id=event.id,
        metadata={
            'old_start': old_start.isoformat(),
            'new_start': new_start.isoformat()
        }
    )
    db.session.add(activity)
    db.session.commit()


def _log_calendar_sync(ally: Ally, provider: str, result: Dict[str, Any]) -> None:
    """Registra sincronización de calendario."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='calendar_sync',
        description=f'Sincronización con {provider}',
        entity_type='calendar_sync',
        metadata={'provider': provider, 'result': result}
    )
    db.session.add(activity)
    db.session.commit()


def _log_integration_connected(ally: Ally, provider: str) -> None:
    """Registra conexión de integración."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='calendar_integration_connected',
        description=f'Integración conectada: {provider}',
        entity_type='calendar_integration',
        metadata={'provider': provider}
    )
    db.session.add(activity)
    db.session.commit()


def _log_integration_disconnected(ally: Ally, provider: str) -> None:
    """Registra desconexión de integración."""
    activity = ActivityLog(
        user_id=ally.user_id,
        action='calendar_integration_disconnected',
        description=f'Integración desconectada: {provider}',
        entity_type='calendar_integration',
        metadata={'provider': provider}
    )
    db.session.add(activity)
    db.session.commit()


# Funciones auxiliares para validaciones

def _has_confirmed_bookings(slot: AvailabilitySlot) -> bool:
    """Verifica si un slot tiene reservas confirmadas."""
    return slot.slots_booked > 0


# Funciones para integraciones específicas

def _get_configured_integrations(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene integraciones configuradas."""
    return []


def _get_available_integrations() -> List[Dict[str, str]]:
    """Obtiene integraciones disponibles."""
    return [
        {'provider': 'google', 'name': 'Google Calendar', 'status': 'available'},
        {'provider': 'outlook', 'name': 'Outlook Calendar', 'status': 'coming_soon'},
        {'provider': 'apple', 'name': 'Apple Calendar', 'status': 'coming_soon'}
    ]


def _get_sync_status(ally: Ally) -> Dict[str, Any]:
    """Obtiene estado de sincronización."""
    return {'last_sync': None, 'status': 'never', 'next_sync': None}


def _get_sync_history(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene historial de sincronización."""
    return []


def _get_sync_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones de sincronización."""
    return {'auto_sync': False, 'sync_frequency': 'manual'}


def _calculate_integration_statistics(ally: Ally) -> Dict[str, Any]:
    """Calcula estadísticas de integración."""
    return {'events_synced': 0, 'last_sync': None}


def _get_recent_sync_errors(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene errores recientes de sincronización."""
    return []


def _perform_initial_sync(ally: Ally, integration: CalendarIntegration) -> None:
    """Realiza sincronización inicial después de conectar integración."""
    pass


# Funciones para configuraciones

def _get_current_calendar_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones actuales del calendario."""
    return _get_calendar_settings(ally)


def _get_calendar_settings_options() -> Dict[str, List[Tuple[str, str]]]:
    """Obtiene opciones para configuraciones del calendario."""
    return {
        'timezones': [
            ('America/Bogota', 'Colombia (UTC-5)'),
            ('America/Mexico_City', 'México (UTC-6)'),
            ('America/New_York', 'Nueva York (UTC-5)'),
            ('Europe/Madrid', 'España (UTC+1)'),
            ('UTC', 'UTC')
        ],
        'default_views': [
            ('month', 'Vista Mensual'),
            ('week', 'Vista Semanal'),
            ('day', 'Vista Diaria'),
            ('agenda', 'Vista Agenda')
        ],
        'slot_durations': [
            (15, '15 minutos'),
            (30, '30 minutos'),
            (45, '45 minutos'),
            (60, '1 hora'),
            (90, '1.5 horas'),
            (120, '2 horas')
        ],
        'buffer_times': [
            (0, 'Sin tiempo de buffer'),
            (5, '5 minutos'),
            (10, '10 minutos'),
            (15, '15 minutos'),
            (30, '30 minutos')
        ],
        'advance_booking_days': [
            (7, '1 semana'),
            (14, '2 semanas'),
            (30, '1 mes'),
            (60, '2 meses'),
            (90, '3 meses')
        ]
    }


def _get_calendar_notification_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones de notificaciones del calendario."""
    return {
        'email_reminders': getattr(ally, 'email_reminders_enabled', True),
        'sms_reminders': getattr(ally, 'sms_reminders_enabled', False),
        'browser_notifications': getattr(ally, 'browser_notifications_enabled', True),
        'reminder_times': getattr(ally, 'reminder_times', [15, 60]),  # minutos antes
        'daily_digest': getattr(ally, 'daily_digest_enabled', True),
        'weekly_summary': getattr(ally, 'weekly_summary_enabled', True)
    }


def _get_available_timezones() -> List[Tuple[str, str]]:
    """Obtiene lista de zonas horarias disponibles."""
    return [
        ('America/Bogota', 'Bogotá (UTC-5)'),
        ('America/Mexico_City', 'Ciudad de México (UTC-6)'),
        ('America/Lima', 'Lima (UTC-5)'),
        ('America/Santiago', 'Santiago (UTC-3)'),
        ('America/Buenos_Aires', 'Buenos Aires (UTC-3)'),
        ('America/Sao_Paulo', 'São Paulo (UTC-3)'),
        ('America/New_York', 'Nueva York (UTC-5)'),
        ('America/Los_Angeles', 'Los Ángeles (UTC-8)'),
        ('Europe/Madrid', 'Madrid (UTC+1)'),
        ('Europe/London', 'Londres (UTC+0)'),
        ('UTC', 'UTC')
    ]


# ==================== ANALYTICS AVANZADOS ====================

def _analyze_availability_effectiveness(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Analiza la efectividad de la disponibilidad ofrecida.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con análisis de efectividad
    """
    # Disponibilidad total ofrecida
    total_availability_hours = db.session.query(
        func.sum(
            func.extract('epoch', AvailabilitySlot.end_time) - 
            func.extract('epoch', AvailabilitySlot.start_time)
        ) / 3600
    ).filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date.date(), end_date.date())
    ).scalar() or 0
    
    # Horas efectivamente utilizadas
    utilized_hours = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).scalar() or 0
    
    # Tasa de utilización
    utilization_rate = (float(utilized_hours) / float(total_availability_hours) * 100) if total_availability_hours > 0 else 0
    
    # Análisis por día de la semana
    weekday_utilization = {}
    for weekday in range(7):  # 0 = Monday, 6 = Sunday
        weekday_availability = db.session.query(
            func.sum(
                func.extract('epoch', AvailabilitySlot.end_time) - 
                func.extract('epoch', AvailabilitySlot.start_time)
            ) / 3600
        ).filter(
            AvailabilitySlot.ally_id == ally.id,
            AvailabilitySlot.date.between(start_date.date(), end_date.date()),
            func.extract('dow', AvailabilitySlot.date) == weekday
        ).scalar() or 0
        
        weekday_utilized = db.session.query(
            func.sum(MentorshipSession.duration_hours)
        ).filter(
            MentorshipSession.ally_id == ally.id,
            MentorshipSession.session_date.between(start_date.date(), end_date.date()),
            func.extract('dow', MentorshipSession.session_date) == weekday,
            MentorshipSession.status == 'completed'
        ).scalar() or 0
        
        weekday_rate = (float(weekday_utilized) / float(weekday_availability) * 100) if weekday_availability > 0 else 0
        weekday_utilization[cal.day_name[weekday]] = round(weekday_rate, 1)
    
    # Horarios más y menos efectivos
    peak_hours = _identify_peak_utilization_hours(ally, start_date, end_date)
    low_hours = _identify_low_utilization_hours(ally, start_date, end_date)
    
    return {
        'total_availability_hours': round(float(total_availability_hours), 2),
        'utilized_hours': round(float(utilized_hours), 2),
        'utilization_rate': round(utilization_rate, 1),
        'weekday_utilization': weekday_utilization,
        'peak_hours': peak_hours,
        'low_hours': low_hours,
        'efficiency_score': _calculate_availability_efficiency_score(utilization_rate, weekday_utilization)
    }


def _identify_temporal_patterns(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Identifica patrones temporales en el uso del calendario.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con patrones identificados
    """
    # Patrones por hora del día
    hourly_patterns = defaultdict(int)
    sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).all()
    
    for session in sessions:
        if session.actual_start_time:
            hour = session.actual_start_time.hour
            hourly_patterns[hour] += 1
    
    # Patrones por día de la semana
    daily_patterns = defaultdict(int)
    for session in sessions:
        weekday = session.session_date.weekday()
        daily_patterns[cal.day_name[weekday]] += 1
    
    # Patrones mensuales
    monthly_patterns = defaultdict(int)
    for session in sessions:
        month = session.session_date.strftime('%B')
        monthly_patterns[month] += 1
    
    # Identificar tendencias
    trends = _identify_usage_trends(sessions, start_date, end_date)
    
    return {
        'hourly_patterns': dict(hourly_patterns),
        'daily_patterns': dict(daily_patterns),
        'monthly_patterns': dict(monthly_patterns),
        'peak_hour': max(hourly_patterns.items(), key=lambda x: x[1])[0] if hourly_patterns else None,
        'peak_day': max(daily_patterns.items(), key=lambda x: x[1])[0] if daily_patterns else None,
        'trends': trends,
        'sessions_analyzed': len(sessions)
    }


def _calculate_scheduling_efficiency(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Calcula eficiencia en la programación y gestión del tiempo.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con métricas de eficiencia
    """
    sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).all()
    
    if not sessions:
        return {
            'on_time_rate': 0,
            'duration_accuracy': 0,
            'cancellation_rate': 0,
            'no_show_rate': 0,
            'overall_efficiency': 0
        }
    
    # Tasa de puntualidad
    on_time_sessions = len([s for s in sessions if s.status == 'completed' and s.actual_start_time])
    on_time_rate = (on_time_sessions / len(sessions)) * 100
    
    # Precisión en duración
    duration_accurate_sessions = 0
    for session in sessions:
        if session.actual_duration and session.duration_hours:
            variance = abs(session.actual_duration - session.duration_hours) / session.duration_hours
            if variance <= 0.1:  # Menos del 10% de variación
                duration_accurate_sessions += 1
    
    duration_accuracy = (duration_accurate_sessions / len(sessions)) * 100
    
    # Tasa de cancelación
    cancelled_sessions = len([s for s in sessions if s.status == 'cancelled'])
    cancellation_rate = (cancelled_sessions / len(sessions)) * 100
    
    # Tasa de no presentación
    no_show_sessions = len([s for s in sessions if s.status == 'no_show'])
    no_show_rate = (no_show_sessions / len(sessions)) * 100
    
    # Score general de eficiencia
    overall_efficiency = (on_time_rate + duration_accuracy + (100 - cancellation_rate) + (100 - no_show_rate)) / 4
    
    return {
        'on_time_rate': round(on_time_rate, 1),
        'duration_accuracy': round(duration_accuracy, 1),
        'cancellation_rate': round(cancellation_rate, 1),
        'no_show_rate': round(no_show_rate, 1),
        'overall_efficiency': round(overall_efficiency, 1),
        'total_sessions_analyzed': len(sessions)
    }


def _analyze_calendar_conflicts_trends(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Analiza tendencias en conflictos del calendario.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con análisis de conflictos
    """
    # Obtener eventos del período
    events = _get_calendar_events(ally, start_date.date(), end_date.date())
    
    # Detectar conflictos
    conflicts = _detect_calendar_conflicts(events)
    
    # Análizar tipos de conflictos
    conflict_types = defaultdict(int)
    for conflict in conflicts:
        event1_type = conflict['event1']['type']
        event2_type = conflict['event2']['type']
        conflict_type = f"{event1_type}_vs_{event2_type}"
        conflict_types[conflict_type] += 1
    
    # Frecuencia de conflictos por día
    daily_conflicts = defaultdict(int)
    for conflict in conflicts:
        conflict_date = conflict['event1']['start'].date()
        daily_conflicts[conflict_date] += 1
    
    # Tendencia temporal
    conflict_trend = _calculate_conflict_trend(conflicts, start_date, end_date)
    
    return {
        'total_conflicts': len(conflicts),
        'conflict_types': dict(conflict_types),
        'daily_conflicts': len(daily_conflicts),
        'avg_conflicts_per_day': len(conflicts) / ((end_date - start_date).days + 1),
        'conflict_trend': conflict_trend,
        'most_problematic_type': max(conflict_types.items(), key=lambda x: x[1])[0] if conflict_types else None
    }


def _calculate_availability_roi(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Calcula ROI del tiempo de disponibilidad ofrecido.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con análisis de ROI
    """
    # Tiempo total invertido en crear disponibilidad (estimado)
    total_slots = AvailabilitySlot.query.filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date.date(), end_date.date())
    ).count()
    
    # Estimación: 2 minutos por slot para crear disponibilidad
    time_invested_hours = (total_slots * 2) / 60
    
    # Sesiones efectivamente realizadas
    completed_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).count()
    
    # Horas de mentoría efectivas
    effective_hours = db.session.query(
        func.sum(MentorshipSession.actual_duration)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).scalar() or 0
    
    # ROI = (Valor generado - Inversión) / Inversión * 100
    # Valor generado = horas efectivas de mentoría
    # Inversión = tiempo invertido en gestión
    
    roi_percentage = ((float(effective_hours) - time_invested_hours) / time_invested_hours * 100) if time_invested_hours > 0 else 0
    
    return {
        'time_invested_hours': round(time_invested_hours, 2),
        'effective_mentorship_hours': round(float(effective_hours), 2),
        'completed_sessions': completed_sessions,
        'roi_percentage': round(roi_percentage, 1),
        'efficiency_ratio': round(float(effective_hours) / time_invested_hours, 2) if time_invested_hours > 0 else 0,
        'sessions_per_hour_invested': round(completed_sessions / time_invested_hours, 2) if time_invested_hours > 0 else 0
    }


def _get_calendar_benchmarks(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Obtiene benchmarks del calendario comparado con otros aliados.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con comparativas benchmark
    """
    # Calcular métricas del aliado
    ally_utilization = _calculate_utilization_rate(ally, start_date, end_date)
    ally_sessions_per_week = _calculate_avg_sessions_per_week(ally, start_date, end_date)
    ally_cancellation_rate = _calculate_cancellation_rate(ally, start_date, end_date)
    
    # Calcular promedios del sistema (otros aliados)
    system_avg_utilization = _calculate_system_avg_utilization(start_date, end_date)
    system_avg_sessions = _calculate_system_avg_sessions_per_week(start_date, end_date)
    system_avg_cancellation = _calculate_system_avg_cancellation_rate(start_date, end_date)
    
    return {
        'utilization_rate': {
            'ally_value': ally_utilization,
            'system_average': system_avg_utilization,
            'percentile': _calculate_percentile(ally_utilization, 'utilization_rate'),
            'status': 'above_average' if ally_utilization > system_avg_utilization else 'below_average'
        },
        'sessions_per_week': {
            'ally_value': ally_sessions_per_week,
            'system_average': system_avg_sessions,
            'percentile': _calculate_percentile(ally_sessions_per_week, 'sessions_per_week'),
            'status': 'above_average' if ally_sessions_per_week > system_avg_sessions else 'below_average'
        },
        'cancellation_rate': {
            'ally_value': ally_cancellation_rate,
            'system_average': system_avg_cancellation,
            'percentile': _calculate_percentile(ally_cancellation_rate, 'cancellation_rate'),
            'status': 'better' if ally_cancellation_rate < system_avg_cancellation else 'worse'
        }
    }


def _generate_calendar_optimization_insights(ally: Ally, time_usage: Dict[str, Any], availability: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Genera insights de optimización para el calendario.
    
    Args:
        ally: Perfil del aliado
        time_usage: Métricas de uso del tiempo
        availability: Análisis de disponibilidad
        
    Returns:
        Lista de insights de optimización
    """
    insights = []
    
    # Analizar utilización baja
    if availability.get('utilization_rate', 0) < 40:
        insights.append({
            'type': 'optimization',
            'title': 'Disponibilidad subutilizada',
            'description': f'Tu tasa de utilización es {availability["utilization_rate"]:.1f}%. Considera ajustar tus horarios de disponibilidad.',
            'priority': 'high',
            'action': 'Revisar patrones de demanda y ajustar horarios'
        })
    
    # Analizar fragmentación
    if time_usage.get('fragmentation_score', 0) > 0.7:
        insights.append({
            'type': 'efficiency',
            'title': 'Tiempo fragmentado',
            'description': 'Detectamos mucha fragmentación en tu horario. Agrupar sesiones puede mejorar tu productividad.',
            'priority': 'medium',
            'action': 'Crear bloques de tiempo más largos'
        })
    
    # Analizar días con baja actividad
    low_activity_days = [day for day, rate in availability.get('weekday_utilization', {}).items() if rate < 20]
    if low_activity_days:
        insights.append({
            'type': 'rebalancing',
            'title': 'Días con poca actividad',
            'description': f'Los días {", ".join(low_activity_days)} tienen poca actividad. Considera redistribuir tu disponibilidad.',
            'priority': 'medium',
            'action': 'Redistribuir disponibilidad hacia días más demandados'
        })
    
    # Analizar horarios poco efectivos
    if availability.get('peak_hours') and availability.get('low_hours'):
        insights.append({
            'type': 'timing',
            'title': 'Optimizar horarios',
            'description': 'Algunos horarios son más efectivos que otros. Enfocar en horarios pico puede mejorar resultados.',
            'priority': 'low',
            'action': 'Priorizar horarios de alta demanda'
        })
    
    return insights


def _prepare_calendar_charts_data(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Prepara datos para gráficos del calendario.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con datos para gráficos
    """
    charts_data = {}
    
    # Gráfico de utilización por día de la semana
    weekday_utilization = {}
    for weekday in range(7):
        weekday_name = cal.day_name[weekday]
        utilization = _calculate_weekday_utilization(ally, weekday, start_date, end_date)
        weekday_utilization[weekday_name] = utilization
    
    charts_data['weekday_utilization'] = {
        'type': 'bar',
        'data': weekday_utilization,
        'title': 'Utilización por Día de la Semana',
        'y_axis': 'Porcentaje de Utilización'
    }
    
    # Gráfico de tendencia temporal
    daily_sessions = _get_daily_sessions_count(ally, start_date, end_date)
    charts_data['temporal_trend'] = {
        'type': 'line',
        'data': daily_sessions,
        'title': 'Tendencia de Sesiones por Día',
        'y_axis': 'Número de Sesiones'
    }
    
    # Gráfico de distribución por tipo de evento
    event_distribution = _get_event_type_distribution(ally, start_date, end_date)
    charts_data['event_distribution'] = {
        'type': 'pie',
        'data': event_distribution,
        'title': 'Distribución de Tipos de Eventos'
    }
    
    # Gráfico de eficiencia semanal
    weekly_efficiency = _get_weekly_efficiency_data(ally, start_date, end_date)
    charts_data['weekly_efficiency'] = {
        'type': 'line',
        'data': weekly_efficiency,
        'title': 'Eficiencia Semanal',
        'y_axis': 'Score de Eficiencia'
    }
    
    return charts_data


def _predict_availability_demand(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Predice demanda futura de disponibilidad basada en patrones históricos.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio
        end_date: Fecha fin
        
    Returns:
        Dict con predicciones de demanda
    """
    # Análisis histórico de patrones
    historical_patterns = _analyze_historical_booking_patterns(ally)
    
    # Predicciones por día de la semana
    weekday_predictions = {}
    for weekday in range(7):
        weekday_name = cal.day_name[weekday]
        prediction = _predict_weekday_demand(ally, weekday, historical_patterns)
        weekday_predictions[weekday_name] = prediction
    
    # Predicciones por hora del día
    hourly_predictions = {}
    for hour in range(8, 20):  # Horario laboral típico
        prediction = _predict_hourly_demand(ally, hour, historical_patterns)
        hourly_predictions[f"{hour:02d}:00"] = prediction
    
    # Predicción general de crecimiento
    growth_prediction = _predict_demand_growth(ally, historical_patterns)
    
    return {
        'weekday_predictions': weekday_predictions,
        'hourly_predictions': hourly_predictions,
        'growth_prediction': growth_prediction,
        'confidence_score': _calculate_prediction_confidence(historical_patterns),
        'next_month_forecast': _forecast_next_month_demand(ally, historical_patterns)
    }


# ==================== FUNCIONES AUXILIARES ESPECÍFICAS ====================

def _identify_peak_utilization_hours(ally: Ally, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """Identifica horas de mayor utilización."""
    hourly_sessions = defaultdict(int)
    
    sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).all()
    
    for session in sessions:
        if session.actual_start_time:
            hour = session.actual_start_time.hour
            hourly_sessions[hour] += 1
    
    # Obtener top 3 horas
    top_hours = sorted(hourly_sessions.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return [{'hour': f"{hour:02d}:00", 'sessions': count} for hour, count in top_hours]


def _identify_low_utilization_hours(ally: Ally, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """Identifica horas de menor utilización."""
    # Obtener todas las horas con disponibilidad
    availability_hours = set()
    slots = AvailabilitySlot.query.filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date.date(), end_date.date())
    ).all()
    
    for slot in slots:
        current_time = slot.start_time
        while current_time < slot.end_time:
            availability_hours.add(current_time.hour)
            current_time = (datetime.combine(date.today(), current_time) + timedelta(hours=1)).time()
    
    # Contar sesiones por hora
    hourly_sessions = defaultdict(int)
    sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'completed'
    ).all()
    
    for session in sessions:
        if session.actual_start_time:
            hourly_sessions[session.actual_start_time.hour] += 1
    
    # Identificar horas con poca utilización
    low_hours = []
    for hour in availability_hours:
        if hourly_sessions[hour] <= 1:  # 1 o menos sesiones
            low_hours.append({'hour': f"{hour:02d}:00", 'sessions': hourly_sessions[hour]})
    
    return sorted(low_hours, key=lambda x: x['sessions'])[:3]


def _calculate_availability_efficiency_score(utilization_rate: float, weekday_utilization: Dict[str, float]) -> float:
    """Calcula score de eficiencia de disponibilidad."""
    # Score base de utilización
    utilization_score = min(utilization_rate / 80 * 100, 100)  # 80% es considerado óptimo
    
    # Score de balance entre días
    utilization_values = list(weekday_utilization.values())
    if utilization_values:
        std_dev = _calculate_standard_deviation(utilization_values)
        balance_score = max(0, 100 - (std_dev * 2))  # Penalizar alta variabilidad
    else:
        balance_score = 0
    
    # Score combinado
    efficiency_score = (utilization_score * 0.7) + (balance_score * 0.3)
    
    return round(efficiency_score, 1)


def _identify_usage_trends(sessions: List[MentorshipSession], start_date: datetime, end_date: datetime) -> Dict[str, str]:
    """Identifica tendencias en el uso del calendario."""
    if len(sessions) < 4:  # Necesitamos datos suficientes
        return {'overall': 'insufficient_data'}
    
    # Dividir período en dos mitades
    mid_date = start_date + (end_date - start_date) / 2
    
    first_half_sessions = [s for s in sessions if datetime.combine(s.session_date, time()) < mid_date]
    second_half_sessions = [s for s in sessions if datetime.combine(s.session_date, time()) >= mid_date]
    
    first_half_avg = len(first_half_sessions) / ((mid_date - start_date).days + 1)
    second_half_avg = len(second_half_sessions) / ((end_date - mid_date).days + 1)
    
    if second_half_avg > first_half_avg * 1.2:
        overall_trend = 'increasing'
    elif second_half_avg < first_half_avg * 0.8:
        overall_trend = 'decreasing'
    else:
        overall_trend = 'stable'
    
    return {
        'overall': overall_trend,
        'first_half_avg': round(first_half_avg, 2),
        'second_half_avg': round(second_half_avg, 2)
    }


def _calculate_conflict_trend(conflicts: List[Dict[str, Any]], start_date: datetime, end_date: datetime) -> str:
    """Calcula tendencia en conflictos del calendario."""
    if len(conflicts) < 2:
        return 'stable'
    
    # Agrupar conflictos por semana
    weekly_conflicts = defaultdict(int)
    for conflict in conflicts:
        week = conflict['event1']['start'].isocalendar()[1]
        weekly_conflicts[week] += 1
    
    weeks = sorted(weekly_conflicts.keys())
    if len(weeks) < 2:
        return 'stable'
    
    first_week_avg = sum(weekly_conflicts[w] for w in weeks[:len(weeks)//2]) / (len(weeks)//2)
    second_week_avg = sum(weekly_conflicts[w] for w in weeks[len(weeks)//2:]) / (len(weeks) - len(weeks)//2)
    
    if second_week_avg > first_week_avg * 1.3:
        return 'increasing'
    elif second_week_avg < first_week_avg * 0.7:
        return 'decreasing'
    else:
        return 'stable'


# Funciones para cálculos de benchmarks
def _calculate_utilization_rate(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula tasa de utilización del aliado."""
    availability_analysis = _analyze_availability_effectiveness(ally, start_date, end_date)
    return availability_analysis.get('utilization_rate', 0)


def _calculate_avg_sessions_per_week(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula promedio de sesiones por semana."""
    total_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).count()
    
    total_weeks = ((end_date - start_date).days + 1) / 7
    return total_sessions / total_weeks if total_weeks > 0 else 0


def _calculate_cancellation_rate(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula tasa de cancelación del aliado."""
    total_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).count()
    
    cancelled_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        MentorshipSession.status == 'cancelled'
    ).count()
    
    return (cancelled_sessions / total_sessions * 100) if total_sessions > 0 else 0


def _calculate_system_avg_utilization(start_date: datetime, end_date: datetime) -> float:
    """Calcula utilización promedio del sistema."""
    # Implementación simplificada
    return 55.2  # Valor simulado


def _calculate_system_avg_sessions_per_week(start_date: datetime, end_date: datetime) -> float:
    """Calcula promedio de sesiones por semana del sistema."""
    return 8.5  # Valor simulado


def _calculate_system_avg_cancellation_rate(start_date: datetime, end_date: datetime) -> float:
    """Calcula tasa de cancelación promedio del sistema."""
    return 12.3  # Valor simulado


def _calculate_percentile(value: float, metric_type: str) -> int:
    """Calcula percentil del valor dentro del sistema."""
    # Implementación simplificada
    if value > 70:
        return 85
    elif value > 50:
        return 65
    elif value > 30:
        return 40
    else:
        return 20


# Funciones para preparación de datos de gráficos
def _calculate_weekday_utilization(ally: Ally, weekday: int, start_date: datetime, end_date: datetime) -> float:
    """Calcula utilización para un día específico de la semana."""
    weekday_availability = db.session.query(
        func.sum(
            func.extract('epoch', AvailabilitySlot.end_time) - 
            func.extract('epoch', AvailabilitySlot.start_time)
        ) / 3600
    ).filter(
        AvailabilitySlot.ally_id == ally.id,
        AvailabilitySlot.date.between(start_date.date(), end_date.date()),
        func.extract('dow', AvailabilitySlot.date) == weekday
    ).scalar() or 0
    
    weekday_utilized = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date()),
        func.extract('dow', MentorshipSession.session_date) == weekday,
        MentorshipSession.status == 'completed'
    ).scalar() or 0
    
    return (float(weekday_utilized) / float(weekday_availability) * 100) if weekday_availability > 0 else 0


def _get_daily_sessions_count(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, int]:
    """Obtiene conteo de sesiones por día."""
    daily_counts = {}
    
    sessions = db.session.query(
        MentorshipSession.session_date,
        func.count(MentorshipSession.id)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).group_by(MentorshipSession.session_date).all()
    
    for session_date, count in sessions:
        daily_counts[session_date.isoformat()] = count
    
    return daily_counts


def _get_event_type_distribution(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, int]:
    """Obtiene distribución de tipos de eventos."""
    distribution = {
        'Sesiones de Mentoría': 0,
        'Reuniones': 0,
        'Eventos Personales': 0
    }
    
    # Contar sesiones de mentoría
    mentorship_count = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date.date(), end_date.date())
    ).count()
    distribution['Sesiones de Mentoría'] = mentorship_count
    
    # Contar reuniones
    meetings_count = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at).between(start_date.date(), end_date.date())
    ).count()
    distribution['Reuniones'] = meetings_count
    
    # Contar eventos personales
    personal_events_count = CalendarEvent.query.filter(
        CalendarEvent.ally_id == ally.id,
        func.date(CalendarEvent.start_datetime).between(start_date.date(), end_date.date()),
        CalendarEvent.event_type == 'personal'
    ).count()
    distribution['Eventos Personales'] = personal_events_count
    
    return distribution


def _get_weekly_efficiency_data(ally: Ally, start_date: datetime, end_date: datetime) -> Dict[str, float]:
    """Obtiene datos de eficiencia semanal."""
    weekly_data = {}
    
    current_date = start_date
    while current_date <= end_date:
        week_start = current_date - timedelta(days=current_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        week_efficiency = _calculate_scheduling_efficiency(ally, week_start, week_end)
        week_key = f"Semana {week_start.strftime('%d/%m')}"
        weekly_data[week_key] = week_efficiency.get('overall_efficiency', 0)
        
        current_date = week_end + timedelta(days=1)
    
    return weekly_data


# Funciones para predicciones de demanda
def _analyze_historical_booking_patterns(ally: Ally) -> Dict[str, Any]:
    """Analiza patrones históricos de reservas."""
    # Obtener datos de los últimos 6 meses
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    
    sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= six_months_ago.date()
    ).all()
    
    patterns = {
        'total_sessions': len(sessions),
        'monthly_growth': _calculate_monthly_growth(sessions),
        'seasonal_patterns': _identify_seasonal_patterns(sessions),
        'weekday_preferences': _analyze_weekday_preferences(sessions),
        'hourly_preferences': _analyze_hourly_preferences(sessions)
    }
    
    return patterns


def _predict_weekday_demand(ally: Ally, weekday: int, patterns: Dict[str, Any]) -> Dict[str, Any]:
    """Predice demanda para un día específico de la semana."""
    historical_weekday_rate = patterns.get('weekday_preferences', {}).get(weekday, 0)
    growth_rate = patterns.get('monthly_growth', 0)
    
    # Predicción simple basada en tendencia histórica
    predicted_demand = historical_weekday_rate * (1 + growth_rate / 100)
    
    return {
        'predicted_sessions': round(predicted_demand, 1),
        'confidence': 'medium' if patterns['total_sessions'] > 20 else 'low',
        'trend': 'increasing' if growth_rate > 5 else 'stable'
    }


def _predict_hourly_demand(ally: Ally, hour: int, patterns: Dict[str, Any]) -> Dict[str, Any]:
    """Predice demanda para una hora específica."""
    historical_hourly_rate = patterns.get('hourly_preferences', {}).get(hour, 0)
    
    return {
        'predicted_sessions': round(historical_hourly_rate, 1),
        'confidence': 'medium',
        'popularity': 'high' if historical_hourly_rate > 2 else 'low'
    }


def _predict_demand_growth(ally: Ally, patterns: Dict[str, Any]) -> Dict[str, Any]:
    """Predice crecimiento general de demanda."""
    monthly_growth = patterns.get('monthly_growth', 0)
    
    if monthly_growth > 10:
        growth_prediction = 'high_growth'
    elif monthly_growth > 0:
        growth_prediction = 'moderate_growth'
    elif monthly_growth > -5:
        growth_prediction = 'stable'
    else:
        growth_prediction = 'declining'
    
    return {
        'prediction': growth_prediction,
        'monthly_rate': monthly_growth,
        'next_quarter_change': monthly_growth * 3
    }


def _calculate_prediction_confidence(patterns: Dict[str, Any]) -> float:
    """Calcula score de confianza para las predicciones."""
    total_sessions = patterns.get('total_sessions', 0)
    
    if total_sessions >= 50:
        return 0.85
    elif total_sessions >= 20:
        return 0.70
    elif total_sessions >= 10:
        return 0.55
    else:
        return 0.30


def _forecast_next_month_demand(ally: Ally, patterns: Dict[str, Any]) -> Dict[str, Any]:
    """Hace forecast de demanda para el próximo mes."""
    avg_monthly_sessions = patterns.get('total_sessions', 0) / 6  # Últimos 6 meses
    growth_rate = patterns.get('monthly_growth', 0)
    
    forecasted_sessions = avg_monthly_sessions * (1 + growth_rate / 100)
    
    return {
        'forecasted_sessions': round(forecasted_sessions),
        'range_low': round(forecasted_sessions * 0.8),
        'range_high': round(forecasted_sessions * 1.2),
        'confidence_level': _calculate_prediction_confidence(patterns)
    }


# Funciones auxiliares para análisis de patrones
def _calculate_monthly_growth(sessions: List[MentorshipSession]) -> float:
    """Calcula tasa de crecimiento mensual."""
    if len(sessions) < 2:
        return 0
    
    # Agrupar por mes
    monthly_counts = defaultdict(int)
    for session in sessions:
        month_key = session.session_date.strftime('%Y-%m')
        monthly_counts[month_key] += 1
    
    months = sorted(monthly_counts.keys())
    if len(months) < 2:
        return 0
    
    # Calcular crecimiento entre primer y último mes
    first_month_count = monthly_counts[months[0]]
    last_month_count = monthly_counts[months[-1]]
    
    if first_month_count == 0:
        return 0
    
    total_months = len(months) - 1
    growth_rate = ((last_month_count / first_month_count) ** (1 / total_months) - 1) * 100
    
    return round(growth_rate, 2)


def _identify_seasonal_patterns(sessions: List[MentorshipSession]) -> Dict[str, Any]:
    """Identifica patrones estacionales."""
    quarterly_counts = defaultdict(int)
    
    for session in sessions:
        quarter = (session.session_date.month - 1) // 3 + 1
        quarterly_counts[f"Q{quarter}"] += 1
    
    return dict(quarterly_counts)


def _analyze_weekday_preferences(sessions: List[MentorshipSession]) -> Dict[int, float]:
    """Analiza preferencias por día de la semana."""
    weekday_counts = defaultdict(int)
    
    for session in sessions:
        weekday = session.session_date.weekday()
        weekday_counts[weekday] += 1
    
    total_sessions = len(sessions)
    if total_sessions == 0:
        return {}
    
    # Convertir a promedio por día
    weekday_averages = {}
    for weekday, count in weekday_counts.items():
        weekday_averages[weekday] = count / (total_sessions / 7)  # Normalizar por semana
    
    return weekday_averages


def _analyze_hourly_preferences(sessions: List[MentorshipSession]) -> Dict[int, float]:
    """Analiza preferencias por hora del día."""
    hourly_counts = defaultdict(int)
    
    for session in sessions:
        if session.start_time:
            hour = session.start_time.hour
            hourly_counts[hour] += 1
    
    return dict(hourly_counts)


def _calculate_standard_deviation(values: List[float]) -> float:
    """Calcula desviación estándar de una lista de valores."""
    if len(values) < 2:
        return 0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


# Funciones para exportación
def _get_events_for_export(ally: Ally, start_date: datetime, end_date: datetime, include_availability: bool) -> List[Dict[str, Any]]:
    """Obtiene eventos formateados para exportación."""
    events = _get_calendar_events(ally, start_date.date(), end_date.date(), include_availability)
    
    export_events = []
    for event in events:
        export_events.append({
            'summary': event['title'],
            'dtstart': event['start'],
            'dtend': event['end'],
            'description': event.get('description', ''),
            'location': event.get('location', ''),
            'status': event.get('status', 'CONFIRMED'),
            'categories': [event.get('type', 'MEETING')]
        })
    
    return export_events


def _generate_calendar_pdf_data(ally: Ally, date_range: Dict[str, date], view_type: str) -> Dict[str, Any]:
    """Genera datos para exportación PDF del calendario."""
    events = _get_calendar_events(ally, date_range['start'], date_range['end'])
    availability = _get_availability_slots(ally, date_range['start'], date_range['end'])
    
    return {
        'ally': ally,
        'date_range': date_range,
        'view_type': view_type,
        'events': events,
        'availability': availability,
        'total_events': len(events),
        'total_availability_hours': sum(
            (datetime.combine(date.today(), slot['end_time']) - 
             datetime.combine(date.today(), slot['start_time'])).total_seconds() / 3600
            for slot in availability
        ),
        'generated_at': datetime.utcnow()
    }


# ==================== CONFIGURACIÓN DE EXPORTACIONES ====================

__all__ = [
    'ally_calendar_bp',
    'calendar_view',
    'availability_management',
    'calendar_integrations',
    'calendar_analytics',
    'calendar_settings'
]