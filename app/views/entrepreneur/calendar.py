"""
Calendario del Emprendedor - Gestión completa de eventos, reuniones y disponibilidad.

Este módulo contiene todas las vistas relacionadas con la gestión del calendario
del emprendedor, incluyendo eventos, reuniones, sesiones de mentoría, disponibilidad,
integración con Google Calendar, recordatorios y analytics de tiempo.
"""

import json
from datetime import datetime, timedelta, time, date
from calendar import monthrange, Calendar
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, g
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, extract, text
from sqlalchemy.orm import joinedload, selectinload
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import pytz

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, ResourceNotFoundError
from app.models.entrepreneur import Entrepreneur
from app.models.meeting import Meeting, MeetingStatus, MeetingType, MeetingPriority
from app.models.mentorship import MentorshipSession, SessionStatus, SessionType
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.project import Project, ProjectStatus
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.models.ally import Ally
from app.models.client import Client
from app.forms.meeting import (
    MeetingForm, QuickMeetingForm, MeetingEditForm,
    AvailabilityForm, BulkActionForm, MeetingSearchForm,
    RecurrenceForm, ReminderForm
)
from app.services.entrepreneur_service import EntrepreneurService
from app.services.google_calendar import GoogleCalendarService
from app.services.google_meet import GoogleMeetService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.sms import SMSService
from app.utils.decorators import cache_response, rate_limit, validate_json
from app.utils.validators import validate_time_slot, validate_future_datetime, validate_timezone
from app.utils.formatters import format_duration, format_time_12h, format_date_short
from app.utils.date_utils import (
    format_relative_time, get_week_range, get_month_range,
    get_timezone_offset, convert_to_timezone, get_business_hours,
    calculate_duration, get_next_business_day
)
from app.utils.string_utils import sanitize_input, generate_slug
from app.utils.notifications import send_calendar_notification

# Crear blueprint para calendario del emprendedor
entrepreneur_calendar = Blueprint(
    'entrepreneur_calendar', 
    __name__, 
    url_prefix='/entrepreneur/calendar'
)

# Configuraciones
EVENTS_PER_PAGE = 50
MIN_MEETING_DURATION = 15  # minutos
MAX_MEETING_DURATION = 480  # 8 horas
DEFAULT_MEETING_DURATION = 60  # 1 hora
ADVANCE_BOOKING_DAYS = 90  # días máximos de anticipación
MIN_ADVANCE_MINUTES = 30  # minutos mínimos de anticipación
BUSINESS_START_HOUR = 8
BUSINESS_END_HOUR = 18

# Tipos de eventos en el calendario
EVENT_TYPES = {
    'meeting': 'Reunión',
    'mentorship': 'Mentoría',
    'task': 'Tarea',
    'project_milestone': 'Hito de Proyecto',
    'personal': 'Personal',
    'break': 'Descanso',
    'travel': 'Viaje'
}

# Colores por tipo de evento
EVENT_COLORS = {
    'meeting': '#3498db',         # Azul
    'mentorship': '#2ecc71',      # Verde
    'task': '#f39c12',           # Naranja
    'project_milestone': '#9b59b6', # Púrpura
    'personal': '#95a5a6',       # Gris
    'break': '#1abc9c',          # Turquesa
    'travel': '#e74c3c'          # Rojo
}


@entrepreneur_calendar.before_request
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


@entrepreneur_calendar.route('/')
@entrepreneur_calendar.route('/month')
@entrepreneur_calendar.route('/month/<int:year>/<int:month>')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=300)  # Cache por 5 minutos
def month_view(year=None, month=None):
    """
    Vista de calendario mensual del emprendedor.
    
    Incluye:
    - Calendario visual con todos los eventos
    - Reuniones, sesiones de mentoría, tareas
    - Navegación entre meses
    - Filtros por tipo de evento
    - Vista resumida de disponibilidad
    """
    try:
        # Fecha actual o específica
        if year and month:
            try:
                target_date = date(year, month, 1)
            except ValueError:
                target_date = date.today()
        else:
            target_date = date.today()
        
        # Calcular rango del mes
        start_date = target_date.replace(day=1)
        end_date = start_date.replace(day=monthrange(start_date.year, start_date.month)[1])
        
        # Expandir para mostrar semanas completas
        calendar_start = start_date - timedelta(days=start_date.weekday())
        calendar_end = end_date + timedelta(days=6 - end_date.weekday())
        
        # Obtener filtros
        event_types = request.args.getlist('types') or list(EVENT_TYPES.keys())
        show_completed = request.args.get('show_completed', 'false').lower() == 'true'
        
        # Obtener eventos del mes
        events = _get_month_events(
            g.entrepreneur.id, 
            calendar_start, 
            calendar_end, 
            event_types, 
            show_completed
        )
        
        # Organizar eventos por día
        events_by_day = _organize_events_by_day(events)
        
        # Generar estructura del calendario
        calendar_weeks = _generate_calendar_weeks(
            calendar_start, 
            calendar_end, 
            events_by_day
        )
        
        # Métricas del mes
        month_metrics = _get_month_metrics(g.entrepreneur.id, start_date, end_date)
        
        # Próximos eventos importantes
        upcoming_events = _get_upcoming_important_events(g.entrepreneur.id, limit=5)
        
        # Disponibilidad general del mes
        availability_summary = _get_availability_summary(
            g.entrepreneur.id, 
            start_date, 
            end_date
        )
        
        # Navegación de meses
        prev_month = start_date - relativedelta(months=1)
        next_month = start_date + relativedelta(months=1)
        
        return render_template(
            'entrepreneur/calendar/month_view.html',
            current_date=target_date,
            calendar_weeks=calendar_weeks,
            events_by_day=events_by_day,
            month_metrics=month_metrics,
            upcoming_events=upcoming_events,
            availability_summary=availability_summary,
            prev_month=prev_month,
            next_month=next_month,
            current_filters={
                'types': event_types,
                'show_completed': show_completed
            },
            event_types=EVENT_TYPES,
            event_colors=EVENT_COLORS,
            start_date=start_date,
            end_date=end_date
        )

    except Exception as e:
        current_app.logger.error(f"Error en vista mensual del calendario: {str(e)}")
        flash('Error cargando el calendario', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_calendar.route('/week')
@entrepreneur_calendar.route('/week/<int:year>/<int:week>')
@login_required
@require_role('entrepreneur')
def week_view(year=None, week=None):
    """
    Vista de calendario semanal con horarios detallados.
    """
    try:
        # Calcular semana objetivo
        if year and week:
            target_date = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%U-%w').date()
        else:
            target_date = date.today()
        
        # Obtener rango de la semana
        week_start, week_end = get_week_range(target_date)
        
        # Obtener filtros
        event_types = request.args.getlist('types') or list(EVENT_TYPES.keys())
        show_details = request.args.get('show_details', 'true').lower() == 'true'
        
        # Obtener eventos de la semana
        events = _get_week_events(
            g.entrepreneur.id, 
            week_start, 
            week_end, 
            event_types
        )
        
        # Organizar eventos por día y hora
        daily_schedules = _generate_daily_schedules(
            week_start, 
            week_end, 
            events
        )
        
        # Detectar conflictos de horario
        conflicts = _detect_schedule_conflicts(events)
        
        # Métricas de la semana
        week_metrics = _get_week_metrics(g.entrepreneur.id, week_start, week_end)
        
        # Análisis de tiempo
        time_analysis = _get_week_time_analysis(events)
        
        # Disponibilidad por días
        daily_availability = _get_daily_availability(
            g.entrepreneur.id, 
            week_start, 
            week_end
        )
        
        # Navegación de semanas
        prev_week = week_start - timedelta(weeks=1)
        next_week = week_start + timedelta(weeks=1)
        
        return render_template(
            'entrepreneur/calendar/week_view.html',
            week_start=week_start,
            week_end=week_end,
            daily_schedules=daily_schedules,
            conflicts=conflicts,
            week_metrics=week_metrics,
            time_analysis=time_analysis,
            daily_availability=daily_availability,
            prev_week=prev_week,
            next_week=next_week,
            current_filters={
                'types': event_types,
                'show_details': show_details
            },
            event_types=EVENT_TYPES,
            event_colors=EVENT_COLORS,
            business_hours=(BUSINESS_START_HOUR, BUSINESS_END_HOUR)
        )

    except Exception as e:
        current_app.logger.error(f"Error en vista semanal del calendario: {str(e)}")
        flash('Error cargando la vista semanal', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.route('/day')
@entrepreneur_calendar.route('/day/<date_str>')
@login_required
@require_role('entrepreneur')
def day_view(date_str=None):
    """
    Vista detallada de un día específico.
    """
    try:
        # Fecha objetivo
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = date.today()
        else:
            target_date = date.today()
        
        # Obtener eventos del día
        events = _get_day_events(g.entrepreneur.id, target_date)
        
        # Organizar cronológicamente
        events_timeline = _create_events_timeline(events, target_date)
        
        # Detectar gaps de tiempo libre
        free_slots = _calculate_free_time_slots(events, target_date)
        
        # Métricas del día
        day_metrics = _get_day_metrics(events)
        
        # Sugerencias de optimización
        optimization_suggestions = _get_schedule_optimization_suggestions(
            events, 
            free_slots
        )
        
        # Tareas pendientes para el día
        pending_tasks = _get_day_pending_tasks(g.entrepreneur.id, target_date)
        
        # Clima/contexto del día (si está disponible)
        day_context = _get_day_context(target_date)
        
        # Navegación de días
        prev_day = target_date - timedelta(days=1)
        next_day = target_date + timedelta(days=1)
        
        return render_template(
            'entrepreneur/calendar/day_view.html',
            target_date=target_date,
            events_timeline=events_timeline,
            free_slots=free_slots,
            day_metrics=day_metrics,
            optimization_suggestions=optimization_suggestions,
            pending_tasks=pending_tasks,
            day_context=day_context,
            prev_day=prev_day,
            next_day=next_day,
            event_types=EVENT_TYPES,
            event_colors=EVENT_COLORS,
            business_hours=(BUSINESS_START_HOUR, BUSINESS_END_HOUR)
        )

    except Exception as e:
        current_app.logger.error(f"Error en vista diaria del calendario: {str(e)}")
        flash('Error cargando la vista del día', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.route('/agenda')
@login_required
@require_role('entrepreneur')
def agenda_view():
    """
    Vista de agenda - lista cronológica de eventos próximos.
    """
    try:
        # Parámetros de filtrado
        days_ahead = request.args.get('days', 14, type=int)  # Próximos 14 días por defecto
        event_types = request.args.getlist('types') or list(EVENT_TYPES.keys())
        include_completed = request.args.get('include_completed', 'false').lower() == 'true'
        
        # Rango de fechas
        start_date = date.today()
        end_date = start_date + timedelta(days=days_ahead)
        
        # Obtener eventos
        events = _get_agenda_events(
            g.entrepreneur.id,
            start_date,
            end_date,
            event_types,
            include_completed
        )
        
        # Agrupar por día
        events_by_day = _group_events_by_day(events)
        
        # Estadísticas de la agenda
        agenda_stats = _get_agenda_statistics(events)
        
        # Próximas fechas importantes
        important_dates = _get_important_upcoming_dates(
            g.entrepreneur.id, 
            start_date, 
            end_date
        )
        
        # Recomendaciones de programación
        scheduling_recommendations = _get_scheduling_recommendations(
            g.entrepreneur.id,
            events
        )
        
        return render_template(
            'entrepreneur/calendar/agenda_view.html',
            events_by_day=events_by_day,
            agenda_stats=agenda_stats,
            important_dates=important_dates,
            scheduling_recommendations=scheduling_recommendations,
            start_date=start_date,
            end_date=end_date,
            current_filters={
                'days': days_ahead,
                'types': event_types,
                'include_completed': include_completed
            },
            event_types=EVENT_TYPES,
            event_colors=EVENT_COLORS
        )

    except Exception as e:
        current_app.logger.error(f"Error en vista de agenda: {str(e)}")
        flash('Error cargando la agenda', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.route('/events/create', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def create_event():
    """
    Crear nuevo evento en el calendario.
    """
    form = MeetingForm()
    
    if request.method == 'GET':
        # Pre-llenar con fecha/hora si se pasa por parámetro
        suggested_date = request.args.get('date')
        suggested_time = request.args.get('time')
        event_type = request.args.get('type', 'meeting')
        
        if suggested_date:
            try:
                form.date.data = datetime.strptime(suggested_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if suggested_time:
            try:
                form.time.data = datetime.strptime(suggested_time, '%H:%M').time()
            except ValueError:
                pass
        
        # Cargar opciones del formulario
        _populate_meeting_form_choices(form)
        
        # Obtener disponibilidad para el día sugerido
        availability_data = None
        if suggested_date:
            try:
                target_date = datetime.strptime(suggested_date, '%Y-%m-%d').date()
                availability_data = _get_day_availability_data(
                    g.entrepreneur.id, 
                    target_date
                )
            except ValueError:
                pass
        
        return render_template(
            'entrepreneur/calendar/create_event.html',
            form=form,
            event_type=event_type,
            availability_data=availability_data,
            event_types=EVENT_TYPES,
            min_duration=MIN_MEETING_DURATION,
            max_duration=MAX_MEETING_DURATION,
            default_duration=DEFAULT_MEETING_DURATION
        )
    
    try:
        if not form.validate_on_submit():
            _populate_meeting_form_choices(form)
            return render_template(
                'entrepreneur/calendar/create_event.html',
                form=form,
                event_types=EVENT_TYPES
            )
        
        # Validar fecha y hora
        event_datetime = datetime.combine(form.date.data, form.time.data)
        
        if not _validate_event_datetime(event_datetime):
            form.date.errors.append('Fecha y hora no válidas')
            _populate_meeting_form_choices(form)
            return render_template('entrepreneur/calendar/create_event.html', form=form)
        
        # Verificar conflictos
        conflicts = _check_time_conflicts(
            g.entrepreneur.id,
            event_datetime,
            form.duration.data
        )
        
        if conflicts and not form.allow_conflicts.data:
            form.time.errors.append('Hay conflictos de horario en este momento')
            _populate_meeting_form_choices(form)
            return render_template(
                'entrepreneur/calendar/create_event.html',
                form=form,
                conflicts=conflicts
            )
        
        # Crear evento según el tipo
        event_type = form.event_type.data
        
        if event_type == 'meeting':
            event = _create_meeting_event(form)
        elif event_type == 'mentorship':
            event = _create_mentorship_event(form)
        elif event_type == 'task':
            event = _create_task_event(form)
        else:
            event = _create_generic_event(form)
        
        # Sincronizar con Google Calendar si está habilitado
        if g.entrepreneur.google_calendar_enabled:
            try:
                _sync_to_google_calendar(event)
            except Exception as e:
                current_app.logger.warning(f"Error sincronizando con Google Calendar: {str(e)}")
        
        # Enviar notificaciones
        _send_event_notifications(event, 'created')
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='calendar_event_created',
            resource_type='meeting' if event_type == 'meeting' else 'calendar_event',
            resource_id=event.id,
            details={
                'event_type': event_type,
                'title': event.title if hasattr(event, 'title') else event.subject,
                'datetime': event_datetime.isoformat()
            }
        )
        
        flash('Evento creado exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Evento creado exitosamente',
                'event_id': event.id,
                'redirect_url': url_for('entrepreneur_calendar.view_event', 
                                      event_type=event_type, 
                                      event_id=event.id)
            })
        else:
            return redirect(url_for('entrepreneur_calendar.day_view', 
                                  date_str=event_datetime.strftime('%Y-%m-%d')))

    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            _populate_meeting_form_choices(form)
            return render_template('entrepreneur/calendar/create_event.html', form=form)
    
    except Exception as e:
        current_app.logger.error(f"Error creando evento: {str(e)}")
        error_msg = 'Error creando el evento'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            _populate_meeting_form_choices(form)
            return render_template('entrepreneur/calendar/create_event.html', form=form)


@entrepreneur_calendar.route('/events/<event_type>/<int:event_id>')
@login_required
@require_role('entrepreneur')
def view_event(event_type, event_id):
    """
    Ver detalles de un evento específico.
    """
    try:
        # Obtener evento según el tipo
        event = _get_event_by_type_and_id(event_type, event_id, g.entrepreneur.id)
        
        if not event:
            flash('Evento no encontrado', 'error')
            return redirect(url_for('entrepreneur_calendar.month_view'))
        
        # Obtener participantes/asistentes
        participants = _get_event_participants(event, event_type)
        
        # Obtener eventos relacionados
        related_events = _get_related_events(event, event_type, g.entrepreneur.id)
        
        # Verificar permisos de edición
        can_edit = _can_edit_event(event, event_type, current_user.id)
        can_cancel = _can_cancel_event(event, event_type, current_user.id)
        
        # Obtener historial de cambios
        change_history = _get_event_change_history(event, event_type)
        
        # Obtener archivos adjuntos/recursos
        attachments = _get_event_attachments(event, event_type)
        
        # Calcular tiempo hasta el evento
        time_until_event = _calculate_time_until_event(event)
        
        return render_template(
            'entrepreneur/calendar/view_event.html',
            event=event,
            event_type=event_type,
            participants=participants,
            related_events=related_events,
            can_edit=can_edit,
            can_cancel=can_cancel,
            change_history=change_history,
            attachments=attachments,
            time_until_event=time_until_event,
            event_colors=EVENT_COLORS
        )

    except Exception as e:
        current_app.logger.error(f"Error mostrando evento {event_type}/{event_id}: {str(e)}")
        flash('Error cargando el evento', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.route('/events/<event_type>/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def edit_event(event_type, event_id):
    """
    Editar evento existente.
    """
    try:
        event = _get_event_by_type_and_id(event_type, event_id, g.entrepreneur.id)
        
        if not event:
            flash('Evento no encontrado', 'error')
            return redirect(url_for('entrepreneur_calendar.month_view'))
        
        if not _can_edit_event(event, event_type, current_user.id):
            flash('No tienes permisos para editar este evento', 'error')
            return redirect(url_for('entrepreneur_calendar.view_event', 
                                  event_type=event_type, 
                                  event_id=event_id))
        
        form = MeetingEditForm(obj=event)
        
        if request.method == 'GET':
            _populate_meeting_form_choices(form)
            _populate_edit_form_with_event_data(form, event, event_type)
            
            return render_template(
                'entrepreneur/calendar/edit_event.html',
                form=form,
                event=event,
                event_type=event_type,
                event_types=EVENT_TYPES
            )
        
        if not form.validate_on_submit():
            _populate_meeting_form_choices(form)
            return render_template(
                'entrepreneur/calendar/edit_event.html',
                form=form,
                event=event,
                event_type=event_type
            )
        
        # Guardar datos originales para auditoria
        original_data = _extract_event_data(event, event_type)
        
        # Validar nueva fecha y hora
        new_datetime = datetime.combine(form.date.data, form.time.data)
        
        if not _validate_event_datetime(new_datetime, exclude_event=(event_type, event_id)):
            form.date.errors.append('Fecha y hora no válidas')
            _populate_meeting_form_choices(form)
            return render_template('entrepreneur/calendar/edit_event.html', form=form, event=event)
        
        # Verificar conflictos (excluyendo el evento actual)
        conflicts = _check_time_conflicts(
            g.entrepreneur.id,
            new_datetime,
            form.duration.data,
            exclude_event=(event_type, event_id)
        )
        
        if conflicts and not form.allow_conflicts.data:
            form.time.errors.append('Hay conflictos de horario en este momento')
            _populate_meeting_form_choices(form)
            return render_template(
                'entrepreneur/calendar/edit_event.html',
                form=form,
                event=event,
                conflicts=conflicts
            )
        
        # Actualizar evento
        updated_event = _update_event_with_form_data(event, event_type, form)
        
        # Sincronizar cambios con Google Calendar
        if g.entrepreneur.google_calendar_enabled:
            try:
                _update_google_calendar_event(updated_event, event_type)
            except Exception as e:
                current_app.logger.warning(f"Error sincronizando cambios con Google Calendar: {str(e)}")
        
        # Detectar cambios significativos
        changes = _detect_event_changes(original_data, updated_event, event_type)
        
        if changes:
            # Enviar notificaciones de cambios
            _send_event_change_notifications(updated_event, event_type, changes)
            
            # Registrar cambios en actividad
            ActivityLog.create(
                user_id=current_user.id,
                action='calendar_event_updated',
                resource_type='meeting' if event_type == 'meeting' else 'calendar_event',
                resource_id=updated_event.id,
                details={
                    'event_type': event_type,
                    'changes': changes
                }
            )
        
        flash('Evento actualizado exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Evento actualizado exitosamente',
                'redirect_url': url_for('entrepreneur_calendar.view_event', 
                                      event_type=event_type, 
                                      event_id=event_id)
            })
        else:
            return redirect(url_for('entrepreneur_calendar.view_event', 
                                  event_type=event_type, 
                                  event_id=event_id))

    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            return redirect(url_for('entrepreneur_calendar.view_event', 
                                  event_type=event_type, 
                                  event_id=event_id))
    
    except Exception as e:
        current_app.logger.error(f"Error editando evento {event_type}/{event_id}: {str(e)}")
        error_msg = 'Error actualizando el evento'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            return redirect(url_for('entrepreneur_calendar.view_event', 
                                  event_type=event_type, 
                                  event_id=event_id))


@entrepreneur_calendar.route('/events/<event_type>/<int:event_id>/cancel', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 cancelaciones por 5 minutos
def cancel_event(event_type, event_id):
    """
    Cancelar evento del calendario.
    """
    try:
        event = _get_event_by_type_and_id(event_type, event_id, g.entrepreneur.id)
        
        if not event:
            return jsonify({'success': False, 'error': 'Evento no encontrado'}), 404
        
        if not _can_cancel_event(event, event_type, current_user.id):
            return jsonify({
                'success': False, 
                'error': 'No puedes cancelar este evento'
            }), 403
        
        # Obtener razón de cancelación
        cancel_reason = request.json.get('reason', '')
        notify_participants = request.json.get('notify_participants', True)
        
        # Cancelar según el tipo de evento
        result = _cancel_event_by_type(event, event_type, cancel_reason)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        # Cancelar en Google Calendar
        if g.entrepreneur.google_calendar_enabled:
            try:
                _cancel_google_calendar_event(event, event_type)
            except Exception as e:
                current_app.logger.warning(f"Error cancelando en Google Calendar: {str(e)}")
        
        # Enviar notificaciones
        if notify_participants:
            _send_event_cancellation_notifications(event, event_type, cancel_reason)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='calendar_event_cancelled',
            resource_type='meeting' if event_type == 'meeting' else 'calendar_event',
            resource_id=event.id,
            details={
                'event_type': event_type,
                'cancel_reason': cancel_reason,
                'original_datetime': _get_event_datetime(event, event_type).isoformat()
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Evento cancelado exitosamente',
            'redirect_url': url_for('entrepreneur_calendar.month_view')
        })

    except Exception as e:
        current_app.logger.error(f"Error cancelando evento {event_type}/{event_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error cancelando el evento'
        }), 500


@entrepreneur_calendar.route('/availability')
@login_required
@require_role('entrepreneur')
def availability():
    """
    Gestión de disponibilidad del emprendedor.
    """
    try:
        # Obtener configuración actual de disponibilidad
        availability_settings = _get_availability_settings(g.entrepreneur.id)
        
        # Próximos 30 días de disponibilidad
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
        
        availability_calendar = _generate_availability_calendar(
            g.entrepreneur.id,
            start_date,
            end_date,
            availability_settings
        )
        
        # Estadísticas de disponibilidad
        availability_stats = _get_availability_statistics(
            g.entrepreneur.id,
            start_date,
            end_date
        )
        
        # Sugerencias de optimización
        optimization_suggestions = _get_availability_optimization_suggestions(
            availability_calendar,
            availability_stats
        )
        
        return render_template(
            'entrepreneur/calendar/availability.html',
            availability_settings=availability_settings,
            availability_calendar=availability_calendar,
            availability_stats=availability_stats,
            optimization_suggestions=optimization_suggestions,
            start_date=start_date,
            end_date=end_date
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando disponibilidad: {str(e)}")
        flash('Error cargando la disponibilidad', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.route('/availability/update', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=20, window=300)  # 20 actualizaciones por 5 minutos
def update_availability():
    """
    Actualizar configuración de disponibilidad.
    """
    try:
        form = AvailabilityForm()
        
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        # Actualizar configuración de disponibilidad
        availability_data = {
            'business_hours_start': form.business_hours_start.data,
            'business_hours_end': form.business_hours_end.data,
            'working_days': form.working_days.data,
            'break_times': form.break_times.data,
            'buffer_time': form.buffer_time.data,
            'max_meetings_per_day': form.max_meetings_per_day.data,
            'advance_booking_days': form.advance_booking_days.data,
            'min_advance_notice': form.min_advance_notice.data
        }
        
        # Guardar configuración
        _save_availability_settings(g.entrepreneur.id, availability_data)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='availability_updated',
            resource_type='entrepreneur',
            resource_id=g.entrepreneur.id,
            details=availability_data
        )
        
        return jsonify({
            'success': True,
            'message': 'Disponibilidad actualizada correctamente'
        })

    except Exception as e:
        current_app.logger.error(f"Error actualizando disponibilidad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error actualizando la disponibilidad'
        }), 500


@entrepreneur_calendar.route('/sync/google-calendar', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=5, window=300)  # 5 sincronizaciones por 5 minutos
def sync_google_calendar():
    """
    Sincronizar calendario con Google Calendar.
    """
    try:
        sync_direction = request.json.get('direction', 'both')  # import, export, both
        date_range = request.json.get('date_range', 30)  # días
        
        if not g.entrepreneur.google_calendar_enabled:
            return jsonify({
                'success': False,
                'error': 'Google Calendar no está habilitado'
            }), 400
        
        # Ejecutar sincronización
        sync_result = g.calendar_service.sync_calendar(
            sync_direction=sync_direction,
            date_range=date_range
        )
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='google_calendar_synced',
            resource_type='entrepreneur',
            resource_id=g.entrepreneur.id,
            details={
                'direction': sync_direction,
                'date_range': date_range,
                'result': sync_result
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Sincronización completada',
            'result': sync_result
        })

    except Exception as e:
        current_app.logger.error(f"Error sincronizando Google Calendar: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error en la sincronización'
        }), 500


@entrepreneur_calendar.route('/api/events')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=180)  # Cache por 3 minutos
def api_events():
    """
    API endpoint para obtener eventos del calendario (para FullCalendar.js).
    """
    try:
        # Parámetros de la consulta
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        event_types = request.args.getlist('types') or list(EVENT_TYPES.keys())
        
        if not start_date or not end_date:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        try:
            start = parse_date(start_date).date()
            end = parse_date(end_date).date()
        except:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
        
        # Obtener eventos
        events = _get_calendar_api_events(
            g.entrepreneur.id,
            start,
            end,
            event_types
        )
        
        # Formatear para FullCalendar
        formatted_events = []
        for event in events:
            formatted_event = _format_event_for_fullcalendar(event)
            if formatted_event:
                formatted_events.append(formatted_event)
        
        return jsonify(formatted_events)

    except Exception as e:
        current_app.logger.error(f"Error en API de eventos: {str(e)}")
        return jsonify({'error': 'Error obteniendo eventos'}), 500


@entrepreneur_calendar.route('/api/availability/<date_str>')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=300)  # Cache por 5 minutos
def api_day_availability(date_str):
    """
    API endpoint para obtener disponibilidad de un día específico.
    """
    try:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
        
        # Obtener disponibilidad del día
        availability_data = _get_day_availability_data(
            g.entrepreneur.id,
            target_date
        )
        
        return jsonify({
            'success': True,
            'date': date_str,
            'availability': availability_data
        })

    except Exception as e:
        current_app.logger.error(f"Error obteniendo disponibilidad para {date_str}: {str(e)}")
        return jsonify({'error': 'Error obteniendo disponibilidad'}), 500


@entrepreneur_calendar.route('/analytics')
@login_required
@require_role('entrepreneur')
def analytics():
    """
    Analytics y métricas del uso del calendario.
    """
    try:
        # Rango de fechas para análisis
        date_range = request.args.get('range', '90')  # días
        end_date = date.today()
        start_date = end_date - timedelta(days=int(date_range))
        
        # Métricas de tiempo
        time_metrics = _get_calendar_time_metrics(
            g.entrepreneur.id,
            start_date,
            end_date
        )
        
        # Análisis de productividad
        productivity_analysis = _get_productivity_analysis(
            g.entrepreneur.id,
            start_date,
            end_date
        )
        
        # Patrones de programación
        scheduling_patterns = _get_scheduling_patterns(
            g.entrepreneur.id,
            start_date,
            end_date
        )
        
        # Eficiencia del calendario
        calendar_efficiency = _get_calendar_efficiency_metrics(
            g.entrepreneur.id,
            start_date,
            end_date
        )
        
        # Recomendaciones
        optimization_recommendations = _get_calendar_optimization_recommendations(
            time_metrics,
            productivity_analysis,
            scheduling_patterns
        )
        
        return render_template(
            'entrepreneur/calendar/analytics.html',
            time_metrics=time_metrics,
            productivity_analysis=productivity_analysis,
            scheduling_patterns=scheduling_patterns,
            calendar_efficiency=calendar_efficiency,
            optimization_recommendations=optimization_recommendations,
            start_date=start_date,
            end_date=end_date,
            current_range=date_range
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando analytics del calendario: {str(e)}")
        flash('Error cargando las métricas', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


# === FUNCIONES AUXILIARES ===

def _get_month_events(entrepreneur_id, start_date, end_date, event_types, show_completed):
    """Obtener todos los eventos del mes."""
    events = []
    
    # Reuniones
    if 'meeting' in event_types:
        query = Meeting.query.filter(
            and_(
                Meeting.entrepreneur_id == entrepreneur_id,
                func.date(Meeting.scheduled_at) >= start_date,
                func.date(Meeting.scheduled_at) <= end_date
            )
        )
        
        if not show_completed:
            query = query.filter(Meeting.status != MeetingStatus.COMPLETED)
        
        meetings = query.options(
            joinedload(Meeting.ally),
            joinedload(Meeting.client)
        ).all()
        
        events.extend([('meeting', m) for m in meetings])
    
    # Sesiones de mentoría
    if 'mentorship' in event_types:
        query = MentorshipSession.query.filter(
            and_(
                MentorshipSession.entrepreneur_id == entrepreneur_id,
                func.date(MentorshipSession.scheduled_at) >= start_date,
                func.date(MentorshipSession.scheduled_at) <= end_date
            )
        )
        
        if not show_completed:
            query = query.filter(MentorshipSession.status != SessionStatus.COMPLETED)
        
        sessions = query.options(
            joinedload(MentorshipSession.mentor)
        ).all()
        
        events.extend([('mentorship', s) for s in sessions])
    
    # Tareas con fecha límite
    if 'task' in event_types:
        tasks = Task.query.filter(
            and_(
                Task.entrepreneur_id == entrepreneur_id,
                Task.due_date >= start_date,
                Task.due_date <= end_date,
                Task.status != TaskStatus.COMPLETED if not show_completed else True
            )
        ).options(
            joinedload(Task.project)
        ).all()
        
        events.extend([('task', t) for t in tasks])
    
    return events


def _organize_events_by_day(events):
    """Organizar eventos por día."""
    events_by_day = {}
    
    for event_type, event in events:
        # Obtener fecha del evento
        if event_type == 'meeting':
            event_date = event.scheduled_at.date()
        elif event_type == 'mentorship':
            event_date = event.scheduled_at.date()
        elif event_type == 'task':
            event_date = event.due_date
        else:
            continue
        
        if event_date not in events_by_day:
            events_by_day[event_date] = []
        
        events_by_day[event_date].append((event_type, event))
    
    # Ordenar eventos por hora dentro de cada día
    for day_events in events_by_day.values():
        day_events.sort(key=lambda x: _get_event_sort_time(x[1], x[0]))
    
    return events_by_day


def _generate_calendar_weeks(start_date, end_date, events_by_day):
    """Generar estructura de semanas para el calendario."""
    weeks = []
    current_date = start_date
    
    while current_date <= end_date:
        week = []
        
        # Generar 7 días de la semana
        for _ in range(7):
            day_data = {
                'date': current_date,
                'events': events_by_day.get(current_date, []),
                'is_today': current_date == date.today(),
                'is_weekend': current_date.weekday() >= 5,
                'is_current_month': start_date.month == current_date.month
            }
            week.append(day_data)
            current_date += timedelta(days=1)
        
        weeks.append(week)
        
        if current_date > end_date:
            break
    
    return weeks


def _get_month_metrics(entrepreneur_id, start_date, end_date):
    """Obtener métricas del mes."""
    # Total de eventos
    total_meetings = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            func.date(Meeting.scheduled_at) >= start_date,
            func.date(Meeting.scheduled_at) <= end_date
        )
    ).count()
    
    total_sessions = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            func.date(MentorshipSession.scheduled_at) >= start_date,
            func.date(MentorshipSession.scheduled_at) <= end_date
        )
    ).count()
    
    # Horas programadas
    meeting_minutes = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            func.date(Meeting.scheduled_at) >= start_date,
            func.date(Meeting.scheduled_at) <= end_date
        )
    ).with_entities(func.sum(Meeting.duration_minutes)).scalar() or 0
    
    session_minutes = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            func.date(MentorshipSession.scheduled_at) >= start_date,
            func.date(MentorshipSession.scheduled_at) <= end_date
        )
    ).with_entities(func.sum(MentorshipSession.duration_minutes)).scalar() or 0
    
    total_hours = round((meeting_minutes + session_minutes) / 60, 1)
    
    # Días ocupados
    busy_days = len(set([
        meeting.scheduled_at.date() 
        for meeting in Meeting.query.filter(
            and_(
                Meeting.entrepreneur_id == entrepreneur_id,
                func.date(Meeting.scheduled_at) >= start_date,
                func.date(Meeting.scheduled_at) <= end_date
            )
        ).all()
    ] + [
        session.scheduled_at.date() 
        for session in MentorshipSession.query.filter(
            and_(
                MentorshipSession.entrepreneur_id == entrepreneur_id,
                func.date(MentorshipSession.scheduled_at) >= start_date,
                func.date(MentorshipSession.scheduled_at) <= end_date
            )
        ).all()
    ]))
    
    return {
        'total_meetings': total_meetings,
        'total_sessions': total_sessions,
        'total_hours': total_hours,
        'busy_days': busy_days,
        'month_name': start_date.strftime('%B %Y')
    }


def _get_upcoming_important_events(entrepreneur_id, limit=5):
    """Obtener próximos eventos importantes."""
    now = datetime.utcnow()
    
    # Reuniones importantes
    important_meetings = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            Meeting.scheduled_at >= now,
            Meeting.priority == MeetingPriority.HIGH,
            Meeting.status != MeetingStatus.CANCELLED
        )
    ).order_by(Meeting.scheduled_at).limit(limit).all()
    
    # Sesiones de mentoría próximas
    upcoming_sessions = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.scheduled_at >= now,
            MentorshipSession.status.in_([SessionStatus.SCHEDULED, SessionStatus.PENDING])
        )
    ).order_by(MentorshipSession.scheduled_at).limit(limit).all()
    
    # Combinar y ordenar
    all_events = []
    all_events.extend([('meeting', m) for m in important_meetings])
    all_events.extend([('mentorship', s) for s in upcoming_sessions])
    
    # Ordenar por fecha
    all_events.sort(key=lambda x: _get_event_datetime(x[1], x[0]))
    
    return all_events[:limit]


def _get_availability_summary(entrepreneur_id, start_date, end_date):
    """Obtener resumen de disponibilidad del mes."""
    total_days = (end_date - start_date).days + 1
    business_days = sum(1 for i in range(total_days) 
                       if (start_date + timedelta(days=i)).weekday() < 5)
    
    # Días con eventos
    busy_days = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            func.date(Meeting.scheduled_at) >= start_date,
            func.date(Meeting.scheduled_at) <= end_date
        )
    ).distinct(func.date(Meeting.scheduled_at)).count()
    
    busy_days += MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            func.date(MentorshipSession.scheduled_at) >= start_date,
            func.date(MentorshipSession.scheduled_at) <= end_date
        )
    ).distinct(func.date(MentorshipSession.scheduled_at)).count()
    
    # Evitar conteo duplicado
    busy_days = min(busy_days, business_days)
    
    free_days = business_days - busy_days
    utilization_rate = (busy_days / business_days * 100) if business_days > 0 else 0
    
    return {
        'total_days': total_days,
        'business_days': business_days,
        'busy_days': busy_days,
        'free_days': free_days,
        'utilization_rate': round(utilization_rate, 1)
    }


def _get_week_events(entrepreneur_id, week_start, week_end, event_types):
    """Obtener eventos de la semana."""
    events = []
    
    # Reuniones
    if 'meeting' in event_types:
        meetings = Meeting.query.filter(
            and_(
                Meeting.entrepreneur_id == entrepreneur_id,
                Meeting.scheduled_at >= datetime.combine(week_start, time.min),
                Meeting.scheduled_at <= datetime.combine(week_end, time.max)
            )
        ).options(
            joinedload(Meeting.ally),
            joinedload(Meeting.client)
        ).all()
        
        events.extend([('meeting', m) for m in meetings])
    
    # Sesiones de mentoría
    if 'mentorship' in event_types:
        sessions = MentorshipSession.query.filter(
            and_(
                MentorshipSession.entrepreneur_id == entrepreneur_id,
                MentorshipSession.scheduled_at >= datetime.combine(week_start, time.min),
                MentorshipSession.scheduled_at <= datetime.combine(week_end, time.max)
            )
        ).options(
            joinedload(MentorshipSession.mentor)
        ).all()
        
        events.extend([('mentorship', s) for s in sessions])
    
    return events


def _generate_daily_schedules(week_start, week_end, events):
    """Generar horarios diarios para la vista semanal."""
    daily_schedules = {}
    current_date = week_start
    
    # Organizar eventos por día
    events_by_day = {}
    for event_type, event in events:
        event_date = _get_event_datetime(event, event_type).date()
        if event_date not in events_by_day:
            events_by_day[event_date] = []
        events_by_day[event_date].append((event_type, event))
    
    # Generar horario para cada día
    while current_date <= week_end:
        day_events = events_by_day.get(current_date, [])
        
        # Crear slots de tiempo (cada 30 minutos de 8 AM a 6 PM)
        time_slots = []
        for hour in range(BUSINESS_START_HOUR, BUSINESS_END_HOUR):
            for minute in [0, 30]:
                slot_time = time(hour, minute)
                slot_events = _get_events_for_time_slot(day_events, slot_time)
                
                time_slots.append({
                    'time': slot_time,
                    'events': slot_events,
                    'is_free': len(slot_events) == 0
                })
        
        daily_schedules[current_date] = {
            'date': current_date,
            'time_slots': time_slots,
            'total_events': len(day_events),
            'is_weekend': current_date.weekday() >= 5
        }
        
        current_date += timedelta(days=1)
    
    return daily_schedules


def _detect_schedule_conflicts(events):
    """Detectar conflictos de horario en eventos."""
    conflicts = []
    
    # Ordenar eventos por fecha/hora
    sorted_events = sorted(events, key=lambda x: _get_event_datetime(x[1], x[0]))
    
    for i in range(len(sorted_events) - 1):
        current_type, current_event = sorted_events[i]
        next_type, next_event = sorted_events[i + 1]
        
        current_end = _get_event_end_datetime(current_event, current_type)
        next_start = _get_event_datetime(next_event, next_type)
        
        # Verificar solapamiento
        if current_end > next_start:
            conflicts.append({
                'event1': (current_type, current_event),
                'event2': (next_type, next_event),
                'overlap_minutes': (current_end - next_start).total_seconds() / 60
            })
    
    return conflicts


def _get_week_metrics(entrepreneur_id, week_start, week_end):
    """Obtener métricas de la semana."""
    # Similar a _get_month_metrics pero para una semana
    start_datetime = datetime.combine(week_start, time.min)
    end_datetime = datetime.combine(week_end, time.max)
    
    meetings_count = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            Meeting.scheduled_at >= start_datetime,
            Meeting.scheduled_at <= end_datetime
        )
    ).count()
    
    sessions_count = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.scheduled_at >= start_datetime,
            MentorshipSession.scheduled_at <= end_datetime
        )
    ).count()
    
    return {
        'meetings_count': meetings_count,
        'sessions_count': sessions_count,
        'total_events': meetings_count + sessions_count,
        'week_start': week_start,
        'week_end': week_end
    }


def _get_week_time_analysis(events):
    """Analizar distribución de tiempo en la semana."""
    time_by_type = {event_type: 0 for event_type in EVENT_TYPES.keys()}
    
    for event_type, event in events:
        duration = _get_event_duration(event, event_type)
        if event_type in time_by_type:
            time_by_type[event_type] += duration
    
    total_time = sum(time_by_type.values())
    
    # Convertir a horas y calcular porcentajes
    analysis = {}
    for event_type, minutes in time_by_type.items():
        hours = round(minutes / 60, 1)
        percentage = (minutes / total_time * 100) if total_time > 0 else 0
        
        analysis[event_type] = {
            'hours': hours,
            'percentage': round(percentage, 1),
            'minutes': minutes
        }
    
    return analysis


def _get_daily_availability(entrepreneur_id, week_start, week_end):
    """Obtener disponibilidad diaria para la semana."""
    availability = {}
    current_date = week_start
    
    while current_date <= week_end:
        # Obtener eventos del día
        day_events = Meeting.query.filter(
            and_(
                Meeting.entrepreneur_id == entrepreneur_id,
                func.date(Meeting.scheduled_at) == current_date
            )
        ).count()
        
        day_events += MentorshipSession.query.filter(
            and_(
                MentorshipSession.entrepreneur_id == entrepreneur_id,
                func.date(MentorshipSession.scheduled_at) == current_date
            )
        ).count()
        
        # Calcular disponibilidad (simplificado)
        if current_date.weekday() >= 5:  # Fin de semana
            availability_status = 'weekend'
        elif day_events == 0:
            availability_status = 'free'
        elif day_events <= 3:
            availability_status = 'partial'
        else:
            availability_status = 'busy'
        
        availability[current_date] = {
            'status': availability_status,
            'events_count': day_events,
            'is_weekend': current_date.weekday() >= 5
        }
        
        current_date += timedelta(days=1)
    
    return availability


def _get_day_events(entrepreneur_id, target_date):
    """Obtener eventos de un día específico."""
    events = []
    
    # Reuniones
    meetings = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            func.date(Meeting.scheduled_at) == target_date
        )
    ).options(
        joinedload(Meeting.ally),
        joinedload(Meeting.client)
    ).all()
    
    events.extend([('meeting', m) for m in meetings])
    
    # Sesiones de mentoría
    sessions = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            func.date(MentorshipSession.scheduled_at) == target_date
        )
    ).options(
        joinedload(MentorshipSession.mentor)
    ).all()
    
    events.extend([('mentorship', s) for s in sessions])
    
    # Tareas con fecha límite
    tasks = Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            Task.due_date == target_date,
            Task.status != TaskStatus.COMPLETED
        )
    ).options(
        joinedload(Task.project)
    ).all()
    
    events.extend([('task', t) for t in tasks])
    
    return events


def _create_events_timeline(events, target_date):
    """Crear timeline cronológico de eventos del día."""
    # Ordenar eventos por hora
    timed_events = []
    all_day_events = []
    
    for event_type, event in events:
        if event_type == 'task':
            all_day_events.append((event_type, event))
        else:
            timed_events.append((event_type, event))
    
    # Ordenar eventos con hora
    timed_events.sort(key=lambda x: _get_event_datetime(x[1], x[0]).time())
    
    timeline = {
        'timed_events': timed_events,
        'all_day_events': all_day_events,
        'total_events': len(events)
    }
    
    return timeline


def _calculate_free_time_slots(events, target_date):
    """Calcular slots de tiempo libre en el día."""
    # Obtener eventos con horario
    timed_events = [
        (event_type, event) for event_type, event in events 
        if event_type in ['meeting', 'mentorship']
    ]
    
    if not timed_events:
        return [{
            'start': time(BUSINESS_START_HOUR, 0),
            'end': time(BUSINESS_END_HOUR, 0),
            'duration_hours': BUSINESS_END_HOUR - BUSINESS_START_HOUR
        }]
    
    # Ordenar por hora de inicio
    timed_events.sort(key=lambda x: _get_event_datetime(x[1], x[0]).time())
    
    free_slots = []
    business_start = time(BUSINESS_START_HOUR, 0)
    business_end = time(BUSINESS_END_HOUR, 0)
    
    # Slot antes del primer evento
    first_event_time = _get_event_datetime(timed_events[0][1], timed_events[0][0]).time()
    if first_event_time > business_start:
        duration = datetime.combine(target_date, first_event_time) - datetime.combine(target_date, business_start)
        free_slots.append({
            'start': business_start,
            'end': first_event_time,
            'duration_hours': duration.total_seconds() / 3600
        })
    
    # Slots entre eventos
    for i in range(len(timed_events) - 1):
        current_end = _get_event_end_datetime(timed_events[i][1], timed_events[i][0]).time()
        next_start = _get_event_datetime(timed_events[i + 1][1], timed_events[i + 1][0]).time()
        
        if next_start > current_end:
            duration = datetime.combine(target_date, next_start) - datetime.combine(target_date, current_end)
            free_slots.append({
                'start': current_end,
                'end': next_start,
                'duration_hours': duration.total_seconds() / 3600
            })
    
    # Slot después del último evento
    last_event_end = _get_event_end_datetime(timed_events[-1][1], timed_events[-1][0]).time()
    if last_event_end < business_end:
        duration = datetime.combine(target_date, business_end) - datetime.combine(target_date, last_event_end)
        free_slots.append({
            'start': last_event_end,
            'end': business_end,
            'duration_hours': duration.total_seconds() / 3600
        })
    
    return free_slots


def _get_day_metrics(events):
    """Obtener métricas del día."""
    total_events = len(events)
    
    # Tiempo total programado
    total_minutes = sum(_get_event_duration(event, event_type) for event_type, event in events)
    total_hours = round(total_minutes / 60, 1)
    
    # Eventos por tipo
    events_by_type = {}
    for event_type, event in events:
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    
    return {
        'total_events': total_events,
        'total_hours': total_hours,
        'total_minutes': total_minutes,
        'events_by_type': events_by_type
    }


def _get_schedule_optimization_suggestions(events, free_slots):
    """Obtener sugerencias de optimización del horario."""
    suggestions = []
    
    # Sugerir consolidar reuniones
    meeting_count = len([e for e in events if e[0] == 'meeting'])
    if meeting_count > 3:
        suggestions.append({
            'type': 'consolidate_meetings',
            'message': f'Tienes {meeting_count} reuniones. Considera consolidar algunas.',
            'priority': 'medium'
        })
    
    # Sugerir bloques de tiempo libre
    long_free_slots = [slot for slot in free_slots if slot['duration_hours'] >= 2]
    if long_free_slots:
        suggestions.append({
            'type': 'focus_time',
            'message': f'Tienes {len(long_free_slots)} bloques de 2+ horas libres para trabajo concentrado.',
            'priority': 'low'
        })
    
    # Detectar días muy ocupados
    if len(events) > 6:
        suggestions.append({
            'type': 'overloaded_day',
            'message': 'Este día está muy cargado. Considera reprogramar algunos eventos.',
            'priority': 'high'
        })
    
    return suggestions


def _get_day_pending_tasks(entrepreneur_id, target_date):
    """Obtener tareas pendientes para el día."""
    return Task.query.filter(
        and_(
            Task.entrepreneur_id == entrepreneur_id,
            or_(
                Task.due_date == target_date,
                and_(Task.due_date < target_date, Task.status != TaskStatus.COMPLETED)
            )
        )
    ).options(
        joinedload(Task.project)
    ).order_by(Task.priority.desc(), Task.due_date).all()


def _get_day_context(target_date):
    """Obtener contexto del día (festivos, eventos especiales, etc.)."""
    # Esta función se puede expandir para incluir:
    # - Días festivos
    # - Eventos especiales de la empresa
    # - Información meteorológica
    # - Etc.
    
    context = {
        'is_holiday': False,
        'holiday_name': None,
        'day_of_week': target_date.strftime('%A'),
        'is_weekend': target_date.weekday() >= 5
    }
    
    return context


def _populate_meeting_form_choices(form):
    """Poblar opciones de formularios."""
    if hasattr(form, 'event_type'):
        form.event_type.choices = [(k, v) for k, v in EVENT_TYPES.items()]
    
    if hasattr(form, 'priority'):
        form.priority.choices = [
            ('low', 'Baja'),
            ('medium', 'Media'),
            ('high', 'Alta'),
            ('urgent', 'Urgente')
        ]
    
    if hasattr(form, 'duration'):
        form.duration.choices = [
            (15, '15 minutos'),
            (30, '30 minutos'),
            (60, '1 hora'),
            (90, '1.5 horas'),
            (120, '2 horas'),
            (180, '3 horas')
        ]


def _validate_event_datetime(event_datetime, exclude_event=None):
    """Validar fecha y hora del evento."""
    now = datetime.utcnow()
    
    # No puede ser en el pasado (con margen de MIN_ADVANCE_MINUTES)
    if event_datetime <= now + timedelta(minutes=MIN_ADVANCE_MINUTES):
        return False
    
    # No puede ser más de ADVANCE_BOOKING_DAYS días en el futuro
    if event_datetime >= now + timedelta(days=ADVANCE_BOOKING_DAYS):
        return False
    
    # Solo en horario laboral
    hour = event_datetime.hour
    if hour < BUSINESS_START_HOUR or hour >= BUSINESS_END_HOUR:
        return False
    
    # No en fines de semana (configurable)
    if event_datetime.weekday() >= 5:
        return False
    
    return True


def _check_time_conflicts(entrepreneur_id, event_datetime, duration_minutes, exclude_event=None):
    """Verificar conflictos de horario."""
    event_end = event_datetime + timedelta(minutes=duration_minutes)
    
    conflicts = []
    
    # Verificar reuniones
    meetings_query = Meeting.query.filter(
        and_(
            Meeting.entrepreneur_id == entrepreneur_id,
            Meeting.status != MeetingStatus.CANCELLED,
            or_(
                # El nuevo evento empieza durante una reunión existente
                and_(
                    Meeting.scheduled_at <= event_datetime,
                    func.datetime(Meeting.scheduled_at, f'+{Meeting.duration_minutes} minutes') > event_datetime
                ),
                # El nuevo evento termina durante una reunión existente
                and_(
                    Meeting.scheduled_at < event_end,
                    func.datetime(Meeting.scheduled_at, f'+{Meeting.duration_minutes} minutes') >= event_end
                ),
                # Una reunión existente está completamente dentro del nuevo evento
                and_(
                    Meeting.scheduled_at >= event_datetime,
                    func.datetime(Meeting.scheduled_at, f'+{Meeting.duration_minutes} minutes') <= event_end
                )
            )
        )
    )
    
    if exclude_event and exclude_event[0] == 'meeting':
        meetings_query = meetings_query.filter(Meeting.id != exclude_event[1])
    
    conflicting_meetings = meetings_query.all()
    conflicts.extend([('meeting', m) for m in conflicting_meetings])
    
    # Verificar sesiones de mentoría (similar lógica)
    sessions_query = MentorshipSession.query.filter(
        and_(
            MentorshipSession.entrepreneur_id == entrepreneur_id,
            MentorshipSession.status != SessionStatus.CANCELLED,
            or_(
                and_(
                    MentorshipSession.scheduled_at <= event_datetime,
                    func.datetime(MentorshipSession.scheduled_at, f'+{MentorshipSession.duration_minutes} minutes') > event_datetime
                ),
                and_(
                    MentorshipSession.scheduled_at < event_end,
                    func.datetime(MentorshipSession.scheduled_at, f'+{MentorshipSession.duration_minutes} minutes') >= event_end
                ),
                and_(
                    MentorshipSession.scheduled_at >= event_datetime,
                    func.datetime(MentorshipSession.scheduled_at, f'+{MentorshipSession.duration_minutes} minutes') <= event_end
                )
            )
        )
    )
    
    if exclude_event and exclude_event[0] == 'mentorship':
        sessions_query = sessions_query.filter(MentorshipSession.id != exclude_event[1])
    
    conflicting_sessions = sessions_query.all()
    conflicts.extend([('mentorship', s) for s in conflicting_sessions])
    
    return conflicts


def _create_meeting_event(form):
    """Crear evento de reunión."""
    meeting_data = {
        'title': sanitize_input(form.title.data),
        'description': sanitize_input(form.description.data),
        'scheduled_at': datetime.combine(form.date.data, form.time.data),
        'duration_minutes': form.duration.data,
        'meeting_type': MeetingType.BUSINESS,  # O basado en form
        'priority': MeetingPriority.MEDIUM,    # O basado en form
        'entrepreneur_id': g.entrepreneur.id,
        'location': sanitize_input(form.location.data) if hasattr(form, 'location') else None
    }
    
    return Meeting.create(**meeting_data)


def _create_mentorship_event(form):
    """Crear evento de sesión de mentoría."""
    session_data = {
        'topic': sanitize_input(form.title.data),
        'description': sanitize_input(form.description.data),
        'scheduled_at': datetime.combine(form.date.data, form.time.data),
        'duration_minutes': form.duration.data,
        'session_type': SessionType.GENERAL,   # O basado en form
        'entrepreneur_id': g.entrepreneur.id,
        'mentor_id': g.entrepreneur.assigned_ally.id if g.entrepreneur.assigned_ally else None
    }
    
    return MentorshipSession.create(**session_data)


def _create_task_event(form):
    """Crear evento de tarea."""
    task_data = {
        'title': sanitize_input(form.title.data),
        'description': sanitize_input(form.description.data),
        'due_date': form.date.data,
        'estimated_hours': form.duration.data / 60,  # Convertir a horas
        'priority': TaskPriority.MEDIUM,  # O basado en form
        'entrepreneur_id': g.entrepreneur.id
    }
    
    return Task.create(**task_data)


def _create_generic_event(form):
    """Crear evento genérico (usar modelo Meeting como base)."""
    return _create_meeting_event(form)


def _sync_to_google_calendar(event):
    """Sincronizar evento con Google Calendar."""
    if not g.calendar_service:
        return
    
    try:
        g.calendar_service.create_event_from_local(event)
    except Exception as e:
        current_app.logger.error(f"Error sincronizando con Google Calendar: {str(e)}")
        raise


def _send_event_notifications(event, action):
    """Enviar notificaciones de evento."""
    # Implementar lógica de notificaciones
    pass


def _get_event_by_type_and_id(event_type, event_id, entrepreneur_id):
    """Obtener evento por tipo y ID."""
    if event_type == 'meeting':
        return Meeting.query.filter_by(
            id=event_id,
            entrepreneur_id=entrepreneur_id
        ).first()
    elif event_type == 'mentorship':
        return MentorshipSession.query.filter_by(
            id=event_id,
            entrepreneur_id=entrepreneur_id
        ).first()
    elif event_type == 'task':
        return Task.query.filter_by(
            id=event_id,
            entrepreneur_id=entrepreneur_id
        ).first()
    
    return None


def _get_event_participants(event, event_type):
    """Obtener participantes del evento."""
    participants = []
    
    if event_type == 'meeting':
        if event.ally:
            participants.append(('ally', event.ally))
        if event.client:
            participants.append(('client', event.client))
    elif event_type == 'mentorship':
        if event.mentor:
            participants.append(('mentor', event.mentor))
    
    return participants


def _get_related_events(event, event_type, entrepreneur_id):
    """Obtener eventos relacionados."""
    # Lógica para encontrar eventos relacionados
    # Por proyecto, participantes, etc.
    return []


def _can_edit_event(event, event_type, user_id):
    """Verificar si el usuario puede editar el evento."""
    # Solo el creador puede editar
    return True  # Simplificado por ahora


def _can_cancel_event(event, event_type, user_id):
    """Verificar si el usuario puede cancelar el evento."""
    # Solo eventos futuros pueden cancelarse
    event_datetime = _get_event_datetime(event, event_type)
    return event_datetime > datetime.utcnow()


def _get_event_change_history(event, event_type):
    """Obtener historial de cambios del evento."""
    return ActivityLog.query.filter_by(
        resource_type='meeting' if event_type == 'meeting' else 'calendar_event',
        resource_id=event.id
    ).order_by(desc(ActivityLog.created_at)).limit(10).all()


def _get_event_attachments(event, event_type):
    """Obtener archivos adjuntos del evento."""
    # Implementar según modelo de documentos
    return []


def _calculate_time_until_event(event):
    """Calcular tiempo hasta el evento."""
    event_datetime = _get_event_datetime(event, 'meeting')  # Asumir meeting por simplicidad
    now = datetime.utcnow()
    
    if event_datetime > now:
        delta = event_datetime - now
        return {
            'is_future': True,
            'days': delta.days,
            'hours': delta.seconds // 3600,
            'minutes': (delta.seconds % 3600) // 60
        }
    else:
        delta = now - event_datetime
        return {
            'is_future': False,
            'days': delta.days,
            'hours': delta.seconds // 3600,
            'minutes': (delta.seconds % 3600) // 60
        }


def _get_event_datetime(event, event_type):
    """Obtener fecha/hora del evento."""
    if event_type == 'meeting':
        return event.scheduled_at
    elif event_type == 'mentorship':
        return event.scheduled_at
    elif event_type == 'task':
        return datetime.combine(event.due_date, time(9, 0))  # Default time
    
    return datetime.utcnow()


def _get_event_end_datetime(event, event_type):
    """Obtener fecha/hora de fin del evento."""
    start_datetime = _get_event_datetime(event, event_type)
    duration = _get_event_duration(event, event_type)
    return start_datetime + timedelta(minutes=duration)


def _get_event_duration(event, event_type):
    """Obtener duración del evento en minutos."""
    if event_type == 'meeting':
        return event.duration_minutes or DEFAULT_MEETING_DURATION
    elif event_type == 'mentorship':
        return event.duration_minutes or DEFAULT_MEETING_DURATION
    elif event_type == 'task':
        return (event.estimated_hours or 1) * 60
    
    return DEFAULT_MEETING_DURATION


def _get_event_sort_time(event, event_type):
    """Obtener tiempo para ordenar eventos."""
    if event_type in ['meeting', 'mentorship']:
        return _get_event_datetime(event, event_type).time()
    else:
        return time(9, 0)  # Default para tareas


def _get_events_for_time_slot(day_events, slot_time):
    """Obtener eventos que ocurren en un slot de tiempo específico."""
    slot_events = []
    
    for event_type, event in day_events:
        event_start = _get_event_datetime(event, event_type).time()
        event_end = _get_event_end_datetime(event, event_type).time()
        
        # Verificar si el slot está dentro del evento
        if event_start <= slot_time < event_end:
            slot_events.append((event_type, event))
    
    return slot_events


def _get_availability_settings(entrepreneur_id):
    """Obtener configuración de disponibilidad."""
    # Esta función debería obtener la configuración desde la BD
    # Por ahora retorna configuración por defecto
    return {
        'business_hours_start': time(8, 0),
        'business_hours_end': time(18, 0),
        'working_days': [0, 1, 2, 3, 4],  # Lunes a Viernes
        'break_times': [time(12, 0), time(13, 0)],  # Almuerzo
        'buffer_time': 15,  # minutos entre reuniones
        'max_meetings_per_day': 6,
        'advance_booking_days': 30,
        'min_advance_notice': 24  # horas
    }


def _get_day_availability_data(entrepreneur_id, target_date):
    """Obtener datos de disponibilidad para un día específico."""
    # Obtener eventos existentes
    events = _get_day_events(entrepreneur_id, target_date)
    
    # Calcular slots libres
    free_slots = _calculate_free_time_slots(events, target_date)
    
    # Formatear para API
    availability_data = {
        'date': target_date.isoformat(),
        'is_weekend': target_date.weekday() >= 5,
        'total_events': len(events),
        'free_slots': [
            {
                'start': slot['start'].strftime('%H:%M'),
                'end': slot['end'].strftime('%H:%M'),
                'duration_hours': slot['duration_hours']
            }
            for slot in free_slots
        ],
        'busy_slots': [
            {
                'start': _get_event_datetime(event, event_type).strftime('%H:%M'),
                'end': _get_event_end_datetime(event, event_type).strftime('%H:%M'),
                'type': event_type,
                'title': _get_event_title(event, event_type)
            }
            for event_type, event in events
            if event_type in ['meeting', 'mentorship']
        ]
    }
    
    return availability_data


def _get_event_title(event, event_type):
    """Obtener título del evento."""
    if event_type == 'meeting':
        return event.title or event.subject
    elif event_type == 'mentorship':
        return event.topic
    elif event_type == 'task':
        return event.title
    
    return 'Evento'


def _format_event_for_fullcalendar(event_info):
    """Formatear evento para FullCalendar.js."""
    event_type, event = event_info
    
    # Obtener datos básicos
    title = _get_event_title(event, event_type)
    start_datetime = _get_event_datetime(event, event_type)
    
    formatted_event = {
        'id': f"{event_type}_{event.id}",
        'title': title,
        'start': start_datetime.isoformat(),
        'backgroundColor': EVENT_COLORS.get(event_type, '#3498db'),
        'borderColor': EVENT_COLORS.get(event_type, '#3498db'),
        'textColor': '#ffffff',
        'extendedProps': {
            'type': event_type,
            'eventId': event.id,
            'description': getattr(event, 'description', ''),
        }
    }
    
    # Agregar fecha de fin para eventos con duración
    if event_type in ['meeting', 'mentorship']:
        end_datetime = _get_event_end_datetime(event, event_type)
        formatted_event['end'] = end_datetime.isoformat()
    
    return formatted_event


def _get_calendar_api_events(entrepreneur_id, start_date, end_date, event_types):
    """Obtener eventos para la API del calendario."""
    return _get_month_events(entrepreneur_id, start_date, end_date, event_types, True)


# Funciones auxiliares adicionales que se referencian pero no están implementadas...
# (Se pueden implementar según necesidades específicas)

def _generate_availability_calendar(entrepreneur_id, start_date, end_date, settings):
    """Generar calendario de disponibilidad."""
    # Implementar generación de calendario de disponibilidad
    return {}

def _get_availability_statistics(entrepreneur_id, start_date, end_date):
    """Obtener estadísticas de disponibilidad."""
    # Implementar cálculo de estadísticas
    return {}

def _get_availability_optimization_suggestions(calendar, stats):
    """Obtener sugerencias de optimización de disponibilidad."""
    # Implementar sugerencias
    return []

def _save_availability_settings(entrepreneur_id, data):
    """Guardar configuración de disponibilidad."""
    # Implementar guardado en BD
    pass

def _get_agenda_events(entrepreneur_id, start_date, end_date, event_types, include_completed):
    """Obtener eventos para la vista de agenda."""
    return _get_month_events(entrepreneur_id, start_date, end_date, event_types, include_completed)

def _group_events_by_day(events):
    """Agrupar eventos por día para la agenda."""
    return _organize_events_by_day(events)

def _get_agenda_statistics(events):
    """Obtener estadísticas de la agenda."""
    return {'total': len(events)}

def _get_important_upcoming_dates(entrepreneur_id, start_date, end_date):
    """Obtener fechas importantes próximas."""
    return []

def _get_scheduling_recommendations(entrepreneur_id, events):
    """Obtener recomendaciones de programación."""
    return []

def _populate_edit_form_with_event_data(form, event, event_type):
    """Poblar formulario de edición con datos del evento."""
    pass

def _extract_event_data(event, event_type):
    """Extraer datos del evento para auditoria."""
    return {}

def _update_event_with_form_data(event, event_type, form):
    """Actualizar evento con datos del formulario."""
    return event

def _update_google_calendar_event(event, event_type):
    """Actualizar evento en Google Calendar."""
    pass

def _detect_event_changes(original_data, updated_event, event_type):
    """Detectar cambios en el evento."""
    return []

def _send_event_change_notifications(event, event_type, changes):
    """Enviar notificaciones de cambios."""
    pass

def _cancel_event_by_type(event, event_type, reason):
    """Cancelar evento según su tipo."""
    return {'success': True}

def _cancel_google_calendar_event(event, event_type):
    """Cancelar evento en Google Calendar."""
    pass

def _send_event_cancellation_notifications(event, event_type, reason):
    """Enviar notificaciones de cancelación."""
    pass

def _get_calendar_time_metrics(entrepreneur_id, start_date, end_date):
    """Obtener métricas de tiempo del calendario."""
    return {}

def _get_productivity_analysis(entrepreneur_id, start_date, end_date):
    """Obtener análisis de productividad."""
    return {}

def _get_scheduling_patterns(entrepreneur_id, start_date, end_date):
    """Obtener patrones de programación."""
    return {}

def _get_calendar_efficiency_metrics(entrepreneur_id, start_date, end_date):
    """Obtener métricas de eficiencia del calendario."""
    return {}

def _get_calendar_optimization_recommendations(time_metrics, productivity, patterns):
    """Obtener recomendaciones de optimización del calendario."""
    return []


# === MANEJADORES DE ERRORES ===

@entrepreneur_calendar.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


@entrepreneur_calendar.errorhandler(ResourceNotFoundError)
def handle_not_found_error(error):
    """Manejar errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 404
    else:
        flash(str(error), 'error')
        return redirect(url_for('entrepreneur_calendar.month_view'))


# === CONTEXT PROCESSORS ===

@entrepreneur_calendar.context_processor
def inject_calendar_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_relative_time': format_relative_time,
        'format_duration': format_duration,
        'format_time_12h': format_time_12h,
        'format_date_short': format_date_short,
        'event_types': EVENT_TYPES,
        'event_colors': EVENT_COLORS,
        'business_hours': (BUSINESS_START_HOUR, BUSINESS_END_HOUR)
    }