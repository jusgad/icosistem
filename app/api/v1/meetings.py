"""
API V1 - Endpoints para gestión de reuniones del ecosistema de emprendimiento
Autor: Sistema de Ecosistema de Emprendimiento
Versión: 1.0
"""

from flask import Blueprint, request, jsonify, current_app, url_for
from flask_login import login_required, current_user
from marshmallow import Schema, fields, validate, ValidationError, post_load
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import uuid
from werkzeug.exceptions import BadRequest, NotFound, Forbidden, Conflict
from dateutil import parser as date_parser
import pytz

# Imports internos
from app.models.meeting import Meeting, MeetingType, MeetingStatus, MeetingRecurrence
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.project import Project
from app.models.mentorship import MentorshipSession
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.services.google_calendar import GoogleCalendarService
from app.services.google_meet import GoogleMeetService
from app.services.email import EmailService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.core.permissions import require_permission, check_meeting_access
from app.core.exceptions import ValidationException, BusinessException, IntegrationException
from app.utils.decorators import api_response, rate_limit, log_activity
from app.utils.validators import validate_uuid, validate_datetime_range, validate_timezone
from app.utils.date_utils import convert_timezone, get_user_timezone
from app.extensions import db, cache

# Blueprint configuration
meetings_bp = Blueprint('meetings_api', __name__, url_prefix='/api/v1/meetings')

# Schemas para validación y serialización
class AttendeeSchema(Schema):
    """Schema para asistentes de reunión"""
    user_id = fields.UUID(required=True)
    role = fields.Str(validate=validate.OneOf(['organizer', 'participant', 'optional']))
    response_status = fields.Str(
        validate=validate.OneOf(['pending', 'accepted', 'declined', 'tentative']),
        missing='pending'
    )

class RecurrenceSchema(Schema):
    """Schema para recurrencia de reuniones"""
    frequency = fields.Str(required=True, validate=validate.OneOf([
        'daily', 'weekly', 'monthly', 'yearly'
    ]))
    interval = fields.Int(validate=validate.Range(min=1, max=100), missing=1)
    days_of_week = fields.List(fields.Int(validate=validate.Range(min=0, max=6)))
    end_type = fields.Str(validate=validate.OneOf(['never', 'date', 'count']), missing='never')
    end_date = fields.DateTime(allow_none=True)
    occurrence_count = fields.Int(validate=validate.Range(min=1, max=365), allow_none=True)

class MeetingCreateSchema(Schema):
    """Schema para creación de reuniones"""
    title = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    description = fields.Str(validate=validate.Length(max=2000))
    meeting_type = fields.Str(required=True, validate=validate.OneOf([
        'one_on_one', 'group_mentoring', 'project_review', 'training',
        'workshop', 'networking', 'presentation', 'consultation', 'other'
    ]))
    start_time = fields.DateTime(required=True)
    end_time = fields.DateTime(required=True)
    timezone = fields.Str(required=True)
    location = fields.Str(validate=validate.Length(max=500))
    is_virtual = fields.Bool(missing=True)
    platform = fields.Str(validate=validate.OneOf([
        'google_meet', 'zoom', 'teams', 'webex', 'other'
    ]), missing='google_meet')
    attendees = fields.List(fields.Nested(AttendeeSchema), required=True)
    project_id = fields.UUID(allow_none=True)
    mentorship_session_id = fields.UUID(allow_none=True)
    agenda = fields.List(fields.Dict(), missing=[])
    max_attendees = fields.Int(validate=validate.Range(min=2, max=1000))
    is_public = fields.Bool(missing=False)
    allow_recording = fields.Bool(missing=False)
    send_reminders = fields.Bool(missing=True)
    reminder_times = fields.List(fields.Int(), missing=[15, 60])  # minutos antes
    recurrence = fields.Nested(RecurrenceSchema, allow_none=True)
    tags = fields.List(fields.Str(), missing=[])
    
    @post_load
    def validate_times(self, data, **kwargs):
        """Validar que end_time sea después de start_time"""
        start = data['start_time']
        end = data['end_time']
        
        if end <= start:
            raise ValidationException("La hora de fin debe ser posterior a la hora de inicio")
        
        # Validar duración máxima (8 horas)
        duration = end - start
        if duration > timedelta(hours=8):
            raise ValidationException("La duración de la reunión no puede exceder 8 horas")
        
        # Validar que la reunión sea en el futuro (al menos 5 minutos)
        now = datetime.utcnow()
        if start < now + timedelta(minutes=5):
            raise ValidationException("La reunión debe programarse al menos 5 minutos en el futuro")
        
        return data

class MeetingUpdateSchema(Schema):
    """Schema para actualización de reuniones"""
    title = fields.Str(validate=validate.Length(min=3, max=200))
    description = fields.Str(validate=validate.Length(max=2000))
    start_time = fields.DateTime()
    end_time = fields.DateTime()
    timezone = fields.Str()
    location = fields.Str(validate=validate.Length(max=500))
    platform = fields.Str(validate=validate.OneOf([
        'google_meet', 'zoom', 'teams', 'webex', 'other'
    ]))
    agenda = fields.List(fields.Dict())
    max_attendees = fields.Int(validate=validate.Range(min=2, max=1000))
    is_public = fields.Bool()
    allow_recording = fields.Bool()
    send_reminders = fields.Bool()
    reminder_times = fields.List(fields.Int())
    tags = fields.List(fields.Str())
    
    @post_load
    def validate_update_times(self, data, **kwargs):
        """Validar tiempos en actualización"""
        if 'start_time' in data and 'end_time' in data:
            if data['end_time'] <= data['start_time']:
                raise ValidationException("La hora de fin debe ser posterior a la hora de inicio")
        return data

class MeetingFilterSchema(Schema):
    """Schema para filtros de búsqueda"""
    page = fields.Int(missing=1, validate=validate.Range(min=1))
    per_page = fields.Int(missing=20, validate=validate.Range(min=1, max=100))
    search = fields.Str()
    meeting_type = fields.Str()
    status = fields.Str(validate=validate.OneOf([
        'scheduled', 'in_progress', 'completed', 'cancelled', 'no_show'
    ]))
    start_date = fields.Date()
    end_date = fields.Date()
    timezone = fields.Str(missing='UTC')
    organizer_id = fields.UUID()
    attendee_id = fields.UUID()
    project_id = fields.UUID()
    is_virtual = fields.Bool()
    platform = fields.Str()
    is_public = fields.Bool()
    tags = fields.List(fields.Str())
    sort_by = fields.Str(missing='start_time', validate=validate.OneOf([
        'start_time', 'created_at', 'title', 'meeting_type'
    ]))
    sort_order = fields.Str(missing='asc', validate=validate.OneOf(['asc', 'desc']))

class MeetingResponseSchema(Schema):
    """Schema para respuesta de reunión"""
    id = fields.UUID()
    title = fields.Str()
    description = fields.Str()
    meeting_type = fields.Str()
    status = fields.Str()
    start_time = fields.DateTime()
    end_time = fields.DateTime()
    timezone = fields.Str()
    duration_minutes = fields.Int()
    location = fields.Str()
    is_virtual = fields.Bool()
    platform = fields.Str()
    meeting_url = fields.URL()
    meeting_id = fields.Str()
    password = fields.Str()
    agenda = fields.List(fields.Dict())
    max_attendees = fields.Int()
    current_attendees_count = fields.Int()
    is_public = fields.Bool()
    allow_recording = fields.Bool()
    recording_url = fields.URL()
    send_reminders = fields.Bool()
    reminder_times = fields.List(fields.Int())
    organizer = fields.Nested('UserBasicSchema')
    attendees = fields.List(fields.Nested('AttendeeResponseSchema'))
    project = fields.Nested('ProjectBasicSchema', allow_none=True)
    mentorship_session = fields.Nested('MentorshipSessionBasicSchema', allow_none=True)
    recurrence = fields.Nested(RecurrenceSchema, allow_none=True)
    tags = fields.List(fields.Str())
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    calendar_event_id = fields.Str()

class AttendeeResponseSchema(Schema):
    """Schema para respuesta de asistente"""
    user = fields.Nested('UserBasicSchema')
    role = fields.Str()
    response_status = fields.Str()
    joined_at = fields.DateTime(allow_none=True)
    left_at = fields.DateTime(allow_none=True)
    attendance_duration_minutes = fields.Int(allow_none=True)

# Servicios
google_calendar_service = GoogleCalendarService()
google_meet_service = GoogleMeetService()
email_service = EmailService()
notification_service = NotificationService()
analytics_service = AnalyticsService()

# Schema instances
meeting_create_schema = MeetingCreateSchema()
meeting_update_schema = MeetingUpdateSchema()
meeting_filter_schema = MeetingFilterSchema()
meeting_response_schema = MeetingResponseSchema()


@meetings_bp.route('', methods=['GET'])
@login_required
@rate_limit(requests=200, window=3600)  # 200 requests per hour
@api_response
def get_meetings():
    """
    Obtener lista de reuniones con filtros y paginación
    
    Returns:
        JSON: Lista paginada de reuniones
    """
    try:
        # Validar parámetros de consulta
        filter_data = meeting_filter_schema.load(request.args)
        
        # Construir filtros basados en permisos del usuario
        filters = _build_meeting_filters(filter_data)
        
        # Obtener zona horaria del usuario
        user_timezone = get_user_timezone(current_user)
        
        # Construir query de reuniones
        meetings_query = Meeting.query
        
        # Aplicar filtros
        if 'search' in filters and filters['search']:
            search_term = f"%{filters['search']}%"
            meetings_query = meetings_query.filter(
                Meeting.title.ilike(search_term) |
                Meeting.description.ilike(search_term)
            )
        
        if 'meeting_type' in filters:
            meetings_query = meetings_query.filter(Meeting.meeting_type == filters['meeting_type'])
        
        if 'status' in filters:
            meetings_query = meetings_query.filter(Meeting.status == filters['status'])
        
        if 'start_date' in filters:
            start_date = datetime.combine(filters['start_date'], datetime.min.time())
            meetings_query = meetings_query.filter(Meeting.start_time >= start_date)
        
        if 'end_date' in filters:
            end_date = datetime.combine(filters['end_date'], datetime.max.time())
            meetings_query = meetings_query.filter(Meeting.start_time <= end_date)
        
        if 'organizer_id' in filters:
            meetings_query = meetings_query.filter(Meeting.organizer_id == filters['organizer_id'])
        
        if 'attendee_id' in filters:
            meetings_query = meetings_query.join(Meeting.attendees).filter(
                User.id == filters['attendee_id']
            )
        
        if 'project_id' in filters:
            meetings_query = meetings_query.filter(Meeting.project_id == filters['project_id'])
        
        if 'is_virtual' in filters:
            meetings_query = meetings_query.filter(Meeting.is_virtual == filters['is_virtual'])
        
        if 'platform' in filters:
            meetings_query = meetings_query.filter(Meeting.platform == filters['platform'])
        
        if 'is_public' in filters:
            meetings_query = meetings_query.filter(Meeting.is_public == filters['is_public'])
        
        # Aplicar filtros de permisos
        if not current_user.has_permission('view_all_meetings'):
            # Solo reuniones donde el usuario es organizador o asistente
            meetings_query = meetings_query.filter(
                (Meeting.organizer_id == current_user.id) |
                (Meeting.attendees.any(User.id == current_user.id)) |
                (Meeting.is_public == True)
            )
        
        # Ordenamiento
        sort_field = getattr(Meeting, filters['sort_by'])
        if filters['sort_order'] == 'desc':
            sort_field = sort_field.desc()
        meetings_query = meetings_query.order_by(sort_field)
        
        # Paginación
        page = filters['page']
        per_page = filters['per_page']
        meetings_paginated = meetings_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Serializar resultados
        meetings_data = []
        for meeting in meetings_paginated.items:
            meeting_dict = meeting_response_schema.dump(meeting)
            # Convertir horarios a zona horaria del usuario
            meeting_dict['start_time'] = convert_timezone(
                meeting.start_time, user_timezone
            ).isoformat()
            meeting_dict['end_time'] = convert_timezone(
                meeting.end_time, user_timezone
            ).isoformat()
            meetings_data.append(meeting_dict)
        
        return {
            'meetings': meetings_data,
            'pagination': {
                'page': meetings_paginated.page,
                'pages': meetings_paginated.pages,
                'per_page': meetings_paginated.per_page,
                'total': meetings_paginated.total,
                'has_next': meetings_paginated.has_next,
                'has_prev': meetings_paginated.has_prev
            },
            'filters_applied': filter_data,
            'user_timezone': user_timezone
        }, 200
        
    except ValidationError as e:
        raise BadRequest(f"Parámetros de consulta inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error al obtener reuniones: {str(e)}")
        raise


@meetings_bp.route('/<uuid:meeting_id>', methods=['GET'])
@login_required
@rate_limit(requests=300, window=3600)
@api_response
def get_meeting(meeting_id: uuid.UUID):
    """
    Obtener detalles de una reunión específica
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Detalles completos de la reunión
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos de acceso
        if not check_meeting_access(current_user, meeting, 'read'):
            raise Forbidden("No tienes permisos para ver esta reunión")
        
        # Serializar reunión
        user_timezone = get_user_timezone(current_user)
        meeting_data = meeting_response_schema.dump(meeting)
        
        # Convertir horarios a zona horaria del usuario
        meeting_data['start_time'] = convert_timezone(
            meeting.start_time, user_timezone
        ).isoformat()
        meeting_data['end_time'] = convert_timezone(
            meeting.end_time, user_timezone
        ).isoformat()
        
        # Agregar información adicional según permisos
        if check_meeting_access(current_user, meeting, 'read_details'):
            # Agregar minutos de reunión si existen
            meeting_data['minutes'] = meeting.get_meeting_minutes()
            # Agregar archivos adjuntos
            meeting_data['attachments'] = meeting.get_attachments()
            # Agregar métricas de asistencia
            meeting_data['attendance_metrics'] = meeting.get_attendance_metrics()
        
        # Registrar actividad
        ActivityLog.log_activity(
            user_id=current_user.id,
            action='view_meeting',
            resource_type='meeting',
            resource_id=meeting_id,
            metadata={'meeting_title': meeting.title}
        )
        
        return meeting_data, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener reunión {meeting_id}: {str(e)}")
        raise


@meetings_bp.route('', methods=['POST'])
@login_required
@require_permission('create_meeting')
@rate_limit(requests=20, window=3600)
@log_activity('create_meeting')
@api_response
def create_meeting():
    """
    Crear una nueva reunión
    
    Returns:
        JSON: Reunión creada
    """
    try:
        # Validar datos de entrada
        meeting_data = meeting_create_schema.load(request.get_json())
        
        # Verificar disponibilidad del organizador
        if not _check_organizer_availability(
            current_user.id, 
            meeting_data['start_time'], 
            meeting_data['end_time']
        ):
            raise Conflict("El organizador no está disponible en el horario solicitado")
        
        # Verificar disponibilidad de asistentes
        unavailable_attendees = _check_attendees_availability(
            meeting_data['attendees'],
            meeting_data['start_time'],
            meeting_data['end_time']
        )
        
        if unavailable_attendees:
            return {
                'warning': 'Algunos asistentes no están disponibles',
                'unavailable_attendees': unavailable_attendees,
                'proceed_anyway': False
            }, 409
        
        # Crear reunión en la base de datos
        meeting = Meeting(
            title=meeting_data['title'],
            description=meeting_data.get('description'),
            meeting_type=meeting_data['meeting_type'],
            start_time=meeting_data['start_time'],
            end_time=meeting_data['end_time'],
            timezone=meeting_data['timezone'],
            location=meeting_data.get('location'),
            is_virtual=meeting_data['is_virtual'],
            platform=meeting_data['platform'],
            organizer_id=current_user.id,
            project_id=meeting_data.get('project_id'),
            mentorship_session_id=meeting_data.get('mentorship_session_id'),
            agenda=meeting_data.get('agenda', []),
            max_attendees=meeting_data.get('max_attendees'),
            is_public=meeting_data['is_public'],
            allow_recording=meeting_data['allow_recording'],
            send_reminders=meeting_data['send_reminders'],
            reminder_times=meeting_data['reminder_times'],
            tags=meeting_data.get('tags', [])
        )
        
        db.session.add(meeting)
        db.session.flush()  # Para obtener el ID
        
        # Agregar asistentes
        for attendee_data in meeting_data['attendees']:
            attendee = User.query.get(attendee_data['user_id'])
            if attendee:
                meeting.attendees.append(attendee)
                # Crear registro de asistencia
                meeting.set_attendee_role(attendee.id, attendee_data.get('role', 'participant'))
        
        # Crear evento en Google Calendar si está habilitado
        calendar_event_id = None
        if meeting.is_virtual and meeting.platform == 'google_meet':
            try:
                calendar_event = google_calendar_service.create_event(
                    title=meeting.title,
                    description=meeting.description,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    timezone=meeting.timezone,
                    attendees=[user.email for user in meeting.attendees],
                    location=meeting.location
                )
                calendar_event_id = calendar_event['id']
                meeting.calendar_event_id = calendar_event_id
                
                # Crear Google Meet si es necesario
                if 'hangoutLink' in calendar_event:
                    meeting.meeting_url = calendar_event['hangoutLink']
                
            except IntegrationException as e:
                current_app.logger.warning(f"Error al crear evento de calendario: {str(e)}")
        
        # Manejar recurrencia
        if meeting_data.get('recurrence'):
            _create_recurring_meetings(meeting, meeting_data['recurrence'])
        
        db.session.commit()
        
        # Enviar notificaciones e invitaciones
        if meeting.send_reminders:
            notification_service.send_meeting_invitation(
                meeting_id=meeting.id,
                attendee_ids=[user.id for user in meeting.attendees]
            )
        
        # Enviar emails de invitación
        _send_meeting_invitations(meeting)
        
        # Programar recordatorios
        if meeting.send_reminders:
            _schedule_meeting_reminders(meeting)
        
        # Registrar en analytics
        analytics_service.track_meeting_creation(meeting.id, current_user.id)
        
        # Serializar respuesta
        meeting_response = meeting_response_schema.dump(meeting)
        
        return {
            'message': 'Reunión creada exitosamente',
            'meeting': meeting_response
        }, 201
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except Conflict as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al crear reunión: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>', methods=['PUT'])
@login_required
@rate_limit(requests=30, window=3600)
@log_activity('update_meeting')
@api_response
def update_meeting(meeting_id: uuid.UUID):
    """
    Actualizar una reunión existente
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Reunión actualizada
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos
        if not check_meeting_access(current_user, meeting, 'update'):
            raise Forbidden("No tienes permisos para actualizar esta reunión")
        
        # Verificar que la reunión no haya comenzado
        if meeting.status == 'in_progress':
            raise BadRequest("No se puede actualizar una reunión en progreso")
        
        if meeting.status == 'completed':
            raise BadRequest("No se puede actualizar una reunión completada")
        
        # Validar datos de actualización
        update_data = meeting_update_schema.load(request.get_json())
        
        # Verificar disponibilidad si se cambian horarios
        if 'start_time' in update_data or 'end_time' in update_data:
            new_start = update_data.get('start_time', meeting.start_time)
            new_end = update_data.get('end_time', meeting.end_time)
            
            # Verificar disponibilidad del organizador
            if not _check_organizer_availability(
                meeting.organizer_id, new_start, new_end, exclude_meeting_id=meeting_id
            ):
                raise Conflict("El organizador no está disponible en el nuevo horario")
        
        # Actualizar campos
        for field, value in update_data.items():
            if hasattr(meeting, field):
                setattr(meeting, field, value)
        
        meeting.updated_at = datetime.utcnow()
        
        # Actualizar evento de calendario si existe
        if meeting.calendar_event_id:
            try:
                google_calendar_service.update_event(
                    event_id=meeting.calendar_event_id,
                    title=meeting.title,
                    description=meeting.description,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    timezone=meeting.timezone,
                    location=meeting.location
                )
            except IntegrationException as e:
                current_app.logger.warning(f"Error al actualizar evento de calendario: {str(e)}")
        
        db.session.commit()
        
        # Enviar notificaciones de cambio
        if _has_significant_changes(update_data):
            notification_service.send_meeting_updated_notification(
                meeting_id=meeting_id,
                changes=update_data,
                updated_by=current_user.id
            )
        
        # Registrar en analytics
        analytics_service.track_meeting_update(meeting_id, current_user.id, update_data)
        
        # Serializar respuesta
        meeting_response = meeting_response_schema.dump(meeting)
        
        return {
            'message': 'Reunión actualizada exitosamente',
            'meeting': meeting_response
        }, 200
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden, Conflict) as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al actualizar reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>', methods=['DELETE'])
@login_required
@rate_limit(requests=10, window=3600)
@log_activity('cancel_meeting')
@api_response
def cancel_meeting(meeting_id: uuid.UUID):
    """
    Cancelar una reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Confirmación de cancelación
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos
        if not check_meeting_access(current_user, meeting, 'cancel'):
            raise Forbidden("No tienes permisos para cancelar esta reunión")
        
        # Verificar que se pueda cancelar
        if meeting.status in ['completed', 'cancelled']:
            raise BadRequest(f"No se puede cancelar una reunión con estado {meeting.status}")
        
        # Obtener motivo de cancelación
        cancel_data = request.get_json() or {}
        reason = cancel_data.get('reason', 'Cancelada por el organizador')
        notify_attendees = cancel_data.get('notify_attendees', True)
        
        # Cancelar reunión
        meeting.status = 'cancelled'
        meeting.cancellation_reason = reason
        meeting.cancelled_by = current_user.id
        meeting.cancelled_at = datetime.utcnow()
        
        # Cancelar evento de calendario
        if meeting.calendar_event_id:
            try:
                google_calendar_service.cancel_event(meeting.calendar_event_id)
            except IntegrationException as e:
                current_app.logger.warning(f"Error al cancelar evento de calendario: {str(e)}")
        
        db.session.commit()
        
        # Enviar notificaciones de cancelación
        if notify_attendees:
            notification_service.send_meeting_cancelled_notification(
                meeting_id=meeting_id,
                reason=reason,
                cancelled_by=current_user.id
            )
        
        # Registrar en analytics
        analytics_service.track_meeting_cancellation(meeting_id, current_user.id, reason)
        
        return {
            'message': 'Reunión cancelada exitosamente',
            'reason': reason
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al cancelar reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>/join', methods=['POST'])
@login_required
@rate_limit(requests=50, window=3600)
@log_activity('join_meeting')
@api_response
def join_meeting(meeting_id: uuid.UUID):
    """
    Unirse a una reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Información de acceso a la reunión
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos para unirse
        if not check_meeting_access(current_user, meeting, 'join'):
            raise Forbidden("No tienes permisos para unirte a esta reunión")
        
        # Verificar estado de la reunión
        if meeting.status == 'cancelled':
            raise BadRequest("La reunión ha sido cancelada")
        
        if meeting.status == 'completed':
            raise BadRequest("La reunión ya ha terminado")
        
        # Verificar tiempo de la reunión
        now = datetime.utcnow()
        if now < meeting.start_time - timedelta(minutes=15):
            raise BadRequest("La reunión aún no está disponible para unirse")
        
        if now > meeting.end_time + timedelta(minutes=30):
            raise BadRequest("La reunión ya ha terminado")
        
        # Verificar límite de asistentes
        if meeting.max_attendees and len(meeting.current_attendees) >= meeting.max_attendees:
            raise Conflict("La reunión ha alcanzado el límite máximo de asistentes")
        
        # Registrar asistencia
        meeting.record_attendance(current_user.id, 'joined')
        
        # Actualizar estado de la reunión si es necesario
        if meeting.status == 'scheduled' and now >= meeting.start_time:
            meeting.status = 'in_progress'
        
        db.session.commit()
        
        # Preparar información de acceso
        access_info = {
            'meeting_id': meeting_id,
            'meeting_url': meeting.meeting_url,
            'meeting_password': meeting.password,
            'platform': meeting.platform,
            'joined_at': datetime.utcnow().isoformat(),
            'attendees_count': len(meeting.current_attendees)
        }
        
        # Agregar información específica de la plataforma
        if meeting.platform == 'google_meet' and meeting.meeting_url:
            access_info['google_meet_url'] = meeting.meeting_url
        
        # Registrar en analytics
        analytics_service.track_meeting_join(meeting_id, current_user.id)
        
        # Notificar a otros asistentes (opcional)
        notification_service.send_attendee_joined_notification(
            meeting_id=meeting_id,
            attendee_id=current_user.id
        )
        
        return {
            'message': 'Te has unido a la reunión exitosamente',
            'access_info': access_info
        }, 200
        
    except (NotFound, Forbidden, BadRequest, Conflict) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al unirse a reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>/leave', methods=['POST'])
@login_required
@rate_limit(requests=50, window=3600)
@log_activity('leave_meeting')
@api_response
def leave_meeting(meeting_id: uuid.UUID):
    """
    Salir de una reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Confirmación de salida
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar que el usuario esté en la reunión
        if not meeting.is_user_attending(current_user.id):
            raise BadRequest("No estás participando en esta reunión")
        
        # Registrar salida
        meeting.record_attendance(current_user.id, 'left')
        
        # Si es el organizador y es la única persona, finalizar reunión
        if (meeting.organizer_id == current_user.id and 
            len(meeting.current_attendees) <= 1 and 
            meeting.status == 'in_progress'):
            meeting.status = 'completed'
            meeting.ended_at = datetime.utcnow()
        
        db.session.commit()
        
        # Registrar en analytics
        analytics_service.track_meeting_leave(meeting_id, current_user.id)
        
        return {
            'message': 'Has salido de la reunión',
            'left_at': datetime.utcnow().isoformat()
        }, 200
        
    except (NotFound, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al salir de reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>/attendees', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)
@api_response
def get_meeting_attendees(meeting_id: uuid.UUID):
    """
    Obtener lista de asistentes de una reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Lista de asistentes con sus estados
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos
        if not check_meeting_access(current_user, meeting, 'read_attendees'):
            raise Forbidden("No tienes permisos para ver los asistentes de esta reunión")
        
        # Obtener asistentes con detalles
        attendees_data = []
        for attendee in meeting.attendees:
            attendee_info = {
                'user': {
                    'id': attendee.id,
                    'name': attendee.full_name,
                    'email': attendee.email,
                    'avatar_url': attendee.avatar_url
                },
                'role': meeting.get_attendee_role(attendee.id),
                'response_status': meeting.get_attendee_response_status(attendee.id),
                'attendance_status': meeting.get_attendance_status(attendee.id),
                'joined_at': meeting.get_attendee_join_time(attendee.id),
                'left_at': meeting.get_attendee_leave_time(attendee.id),
                'total_duration_minutes': meeting.get_attendee_duration(attendee.id)
            }
            attendees_data.append(attendee_info)
        
        return {
            'meeting_id': meeting_id,
            'total_attendees': len(attendees_data),
            'current_attendees': len(meeting.current_attendees),
            'attendees': attendees_data
        }, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener asistentes de reunión {meeting_id}: {str(e)}")
        raise


@meetings_bp.route('/<uuid:meeting_id>/attendees', methods=['POST'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('add_meeting_attendee')
@api_response
def add_meeting_attendee(meeting_id: uuid.UUID):
    """
    Agregar asistente a una reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Confirmación de asistente agregado
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos
        if not check_meeting_access(current_user, meeting, 'manage_attendees'):
            raise Forbidden("No tienes permisos para agregar asistentes a esta reunión")
        
        # Validar datos
        data = request.get_json()
        if not data or 'user_id' not in data:
            raise BadRequest("user_id es requerido")
        
        user_id = data['user_id']
        role = data.get('role', 'participant')
        
        # Verificar que el usuario existe
        user = User.query.get(user_id)
        if not user:
            raise NotFound("Usuario no encontrado")
        
        # Verificar que no esté ya agregado
        if user in meeting.attendees:
            raise Conflict("El usuario ya es asistente de esta reunión")
        
        # Verificar límite de asistentes
        if meeting.max_attendees and len(meeting.attendees) >= meeting.max_attendees:
            raise Conflict("La reunión ha alcanzado el límite máximo de asistentes")
        
        # Verificar disponibilidad del usuario
        if not _check_user_availability(user_id, meeting.start_time, meeting.end_time):
            return {
                'warning': 'El usuario no está disponible en el horario de la reunión',
                'user_id': user_id,
                'conflicts': _get_user_conflicts(user_id, meeting.start_time, meeting.end_time)
            }, 409
        
        # Agregar asistente
        meeting.attendees.append(user)
        meeting.set_attendee_role(user_id, role)
        
        # Actualizar evento de calendario
        if meeting.calendar_event_id:
            try:
                google_calendar_service.add_attendee_to_event(
                    event_id=meeting.calendar_event_id,
                    attendee_email=user.email
                )
            except IntegrationException as e:
                current_app.logger.warning(f"Error al agregar asistente al calendario: {str(e)}")
        
        db.session.commit()
        
        # Enviar invitación al nuevo asistente
        notification_service.send_meeting_invitation(
            meeting_id=meeting_id,
            attendee_ids=[user_id]
        )
        
        # Enviar email de invitación
        email_service.send_meeting_invitation_email(
            meeting=meeting,
            attendee=user,
            invited_by=current_user
        )
        
        return {
            'message': 'Asistente agregado exitosamente',
            'attendee': {
                'user_id': user_id,
                'name': user.full_name,
                'email': user.email,
                'role': role
            }
        }, 201
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden, BadRequest, Conflict) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al agregar asistente a reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>/attendees/<uuid:user_id>', methods=['DELETE'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('remove_meeting_attendee')
@api_response
def remove_meeting_attendee(meeting_id: uuid.UUID, user_id: uuid.UUID):
    """
    Remover asistente de una reunión
    
    Args:
        meeting_id: UUID de la reunión
        user_id: UUID del usuario a remover
        
    Returns:
        JSON: Confirmación de remoción
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar permisos
        if not check_meeting_access(current_user, meeting, 'manage_attendees'):
            raise Forbidden("No tienes permisos para remover asistentes de esta reunión")
        
        # Verificar que el usuario es asistente
        user = User.query.get(user_id)
        if not user or user not in meeting.attendees:
            raise NotFound("El usuario no es asistente de esta reunión")
        
        # No permitir remover al organizador
        if user_id == meeting.organizer_id:
            raise BadRequest("No se puede remover al organizador de la reunión")
        
        # Remover asistente
        meeting.attendees.remove(user)
        
        # Actualizar evento de calendario
        if meeting.calendar_event_id:
            try:
                google_calendar_service.remove_attendee_from_event(
                    event_id=meeting.calendar_event_id,
                    attendee_email=user.email
                )
            except IntegrationException as e:
                current_app.logger.warning(f"Error al remover asistente del calendario: {str(e)}")
        
        db.session.commit()
        
        # Notificar al usuario removido
        notification_service.send_meeting_removal_notification(
            meeting_id=meeting_id,
            removed_user_id=user_id,
            removed_by=current_user.id
        )
        
        return {
            'message': 'Asistente removido exitosamente'
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al remover asistente de reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/<uuid:meeting_id>/respond', methods=['POST'])
@login_required
@rate_limit(requests=50, window=3600)
@log_activity('respond_meeting_invitation')
@api_response
def respond_to_meeting(meeting_id: uuid.UUID):
    """
    Responder a una invitación de reunión
    
    Args:
        meeting_id: UUID de la reunión
        
    Returns:
        JSON: Confirmación de respuesta
    """
    try:
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            raise NotFound("Reunión no encontrada")
        
        # Verificar que el usuario es asistente
        if current_user not in meeting.attendees:
            raise Forbidden("No eres asistente de esta reunión")
        
        # Validar datos
        data = request.get_json()
        if not data or 'response' not in data:
            raise BadRequest("Respuesta requerida")
        
        response = data['response']
        if response not in ['accepted', 'declined', 'tentative']:
            raise BadRequest("Respuesta inválida")
        
        comment = data.get('comment', '')
        
        # Actualizar respuesta
        meeting.set_attendee_response(current_user.id, response, comment)
        
        # Actualizar evento de calendario
        if meeting.calendar_event_id:
            try:
                google_calendar_service.respond_to_event(
                    event_id=meeting.calendar_event_id,
                    attendee_email=current_user.email,
                    response=response
                )
            except IntegrationException as e:
                current_app.logger.warning(f"Error al responder en calendario: {str(e)}")
        
        db.session.commit()
        
        # Notificar al organizador
        notification_service.send_meeting_response_notification(
            meeting_id=meeting_id,
            respondent_id=current_user.id,
            response=response,
            comment=comment
        )
        
        # Registrar en analytics
        analytics_service.track_meeting_response(meeting_id, current_user.id, response)
        
        return {
            'message': f'Respuesta registrada: {response}',
            'response': response,
            'comment': comment
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al responder a reunión {meeting_id}: {str(e)}")
        db.session.rollback()
        raise


@meetings_bp.route('/calendar', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)
@api_response
def get_calendar_view():
    """
    Obtener vista de calendario de reuniones
    
    Returns:
        JSON: Reuniones organizadas por fecha para vista de calendario
    """
    try:
        # Validar parámetros
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        view_type = request.args.get('view', 'month')  # month, week, day
        timezone = request.args.get('timezone', get_user_timezone(current_user))
        
        if not start_date or not end_date:
            raise BadRequest("start_date y end_date son requeridos")
        
        try:
            start_dt = date_parser.parse(start_date)
            end_dt = date_parser.parse(end_date)
        except ValueError:
            raise BadRequest("Formato de fecha inválido")
        
        # Obtener reuniones del período
        meetings_query = Meeting.query.filter(
            Meeting.start_time >= start_dt,
            Meeting.start_time <= end_dt
        )
        
        # Filtrar por permisos
        if not current_user.has_permission('view_all_meetings'):
            meetings_query = meetings_query.filter(
                (Meeting.organizer_id == current_user.id) |
                (Meeting.attendees.any(User.id == current_user.id)) |
                (Meeting.is_public == True)
            )
        
        meetings = meetings_query.order_by(Meeting.start_time).all()
        
        # Organizar por fecha
        calendar_data = {}
        for meeting in meetings:
            # Convertir a zona horaria del usuario
            local_start = convert_timezone(meeting.start_time, timezone)
            date_key = local_start.date().isoformat()
            
            if date_key not in calendar_data:
                calendar_data[date_key] = []
            
            meeting_data = {
                'id': meeting.id,
                'title': meeting.title,
                'start_time': local_start.isoformat(),
                'end_time': convert_timezone(meeting.end_time, timezone).isoformat(),
                'duration_minutes': meeting.duration_minutes,
                'meeting_type': meeting.meeting_type,
                'status': meeting.status,
                'is_virtual': meeting.is_virtual,
                'platform': meeting.platform,
                'organizer': {
                    'id': meeting.organizer.id,
                    'name': meeting.organizer.full_name
                },
                'attendees_count': len(meeting.attendees),
                'user_role': meeting.get_attendee_role(current_user.id) if current_user in meeting.attendees else 'viewer',
                'user_response': meeting.get_attendee_response_status(current_user.id) if current_user in meeting.attendees else None
            }
            
            calendar_data[date_key].append(meeting_data)
        
        return {
            'calendar': calendar_data,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'view_type': view_type,
                'timezone': timezone
            },
            'total_meetings': len(meetings)
        }, 200
        
    except (BadRequest,) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener vista de calendario: {str(e)}")
        raise


@meetings_bp.route('/upcoming', methods=['GET'])
@login_required
@rate_limit(requests=200, window=3600)
@cache.cached(timeout=300)  # Cache for 5 minutes
@api_response
def get_upcoming_meetings():
    """
    Obtener próximas reuniones del usuario
    
    Returns:
        JSON: Lista de próximas reuniones
    """
    try:
        limit = int(request.args.get('limit', 10))
        days_ahead = int(request.args.get('days', 7))
        
        # Calcular rango de fechas
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)
        
        # Obtener reuniones próximas del usuario
        meetings_query = Meeting.query.filter(
            Meeting.start_time >= now,
            Meeting.start_time <= end_date,
            Meeting.status.in_(['scheduled', 'in_progress'])
        ).filter(
            (Meeting.organizer_id == current_user.id) |
            (Meeting.attendees.any(User.id == current_user.id))
        ).order_by(Meeting.start_time).limit(limit)
        
        meetings = meetings_query.all()
        
        # Serializar reuniones
        user_timezone = get_user_timezone(current_user)
        meetings_data = []
        
        for meeting in meetings:
            meeting_data = {
                'id': meeting.id,
                'title': meeting.title,
                'start_time': convert_timezone(meeting.start_time, user_timezone).isoformat(),
                'end_time': convert_timezone(meeting.end_time, user_timezone).isoformat(),
                'meeting_type': meeting.meeting_type,
                'status': meeting.status,
                'is_virtual': meeting.is_virtual,
                'platform': meeting.platform,
                'meeting_url': meeting.meeting_url if meeting.is_virtual else None,
                'organizer': {
                    'id': meeting.organizer.id,
                    'name': meeting.organizer.full_name
                },
                'attendees_count': len(meeting.attendees),
                'user_role': meeting.get_attendee_role(current_user.id),
                'user_response': meeting.get_attendee_response_status(current_user.id),
                'time_until_start': _calculate_time_until_start(meeting.start_time),
                'can_join': _can_join_meeting(meeting, current_user)
            }
            meetings_data.append(meeting_data)
        
        return {
            'upcoming_meetings': meetings_data,
            'count': len(meetings_data),
            'period': f'next {days_ahead} days',
            'user_timezone': user_timezone
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener próximas reuniones: {str(e)}")
        raise


@meetings_bp.route('/statistics', methods=['GET'])
@login_required
@require_permission('view_meeting_stats')
@rate_limit(requests=20, window=3600)
@cache.cached(timeout=600)  # Cache for 10 minutes
@api_response
def get_meeting_statistics():
    """
    Obtener estadísticas de reuniones
    
    Returns:
        JSON: Estadísticas detalladas de reuniones
    """
    try:
        period = request.args.get('period', 'month')  # week, month, quarter, year
        
        # Obtener estadísticas
        stats = analytics_service.get_meeting_statistics(
            user=current_user,
            period=period
        )
        
        return {
            'statistics': stats,
            'period': period,
            'generated_at': datetime.utcnow().isoformat()
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas de reuniones: {str(e)}")
        raise


# Funciones auxiliares privadas

def _build_meeting_filters(filter_data: Dict) -> Dict:
    """Construir filtros de reunión"""
    return filter_data


def _check_organizer_availability(
    organizer_id: uuid.UUID, 
    start_time: datetime, 
    end_time: datetime,
    exclude_meeting_id: Optional[uuid.UUID] = None
) -> bool:
    """Verificar disponibilidad del organizador"""
    query = Meeting.query.filter(
        Meeting.organizer_id == organizer_id,
        Meeting.status.in_(['scheduled', 'in_progress']),
        Meeting.start_time < end_time,
        Meeting.end_time > start_time
    )
    
    if exclude_meeting_id:
        query = query.filter(Meeting.id != exclude_meeting_id)
    
    return query.count() == 0


def _check_attendees_availability(
    attendees: List[Dict], 
    start_time: datetime, 
    end_time: datetime
) -> List[Dict]:
    """Verificar disponibilidad de asistentes"""
    unavailable = []
    
    for attendee_data in attendees:
        user_id = attendee_data['user_id']
        if not _check_user_availability(user_id, start_time, end_time):
            user = User.query.get(user_id)
            if user:
                unavailable.append({
                    'user_id': user_id,
                    'name': user.full_name,
                    'conflicts': _get_user_conflicts(user_id, start_time, end_time)
                })
    
    return unavailable


def _check_user_availability(
    user_id: uuid.UUID, 
    start_time: datetime, 
    end_time: datetime
) -> bool:
    """Verificar disponibilidad de un usuario"""
    conflicts = Meeting.query.filter(
        Meeting.attendees.any(User.id == user_id),
        Meeting.status.in_(['scheduled', 'in_progress']),
        Meeting.start_time < end_time,
        Meeting.end_time > start_time
    ).count()
    
    return conflicts == 0


def _get_user_conflicts(
    user_id: uuid.UUID, 
    start_time: datetime, 
    end_time: datetime
) -> List[Dict]:
    """Obtener conflictos de horario de un usuario"""
    conflicts = Meeting.query.filter(
        Meeting.attendees.any(User.id == user_id),
        Meeting.status.in_(['scheduled', 'in_progress']),
        Meeting.start_time < end_time,
        Meeting.end_time > start_time
    ).all()
    
    return [
        {
            'meeting_id': meeting.id,
            'title': meeting.title,
            'start_time': meeting.start_time.isoformat(),
            'end_time': meeting.end_time.isoformat()
        }
        for meeting in conflicts
    ]


def _create_recurring_meetings(meeting: Meeting, recurrence_data: Dict):
    """Crear reuniones recurrentes"""
    # Implementar lógica de recurrencia
    # Esta función creará las instancias futuras basadas en la configuración
    pass


def _send_meeting_invitations(meeting: Meeting):
    """Enviar invitaciones por email"""
    for attendee in meeting.attendees:
        email_service.send_meeting_invitation_email(
            meeting=meeting,
            attendee=attendee,
            invited_by=meeting.organizer
        )


def _schedule_meeting_reminders(meeting: Meeting):
    """Programar recordatorios de reunión"""
    for reminder_minutes in meeting.reminder_times:
        reminder_time = meeting.start_time - timedelta(minutes=reminder_minutes)
        # Programar tarea de recordatorio con Celery
        # schedule_meeting_reminder.apply_async(
        #     args=[meeting.id, reminder_minutes],
        #     eta=reminder_time
        # )


def _has_significant_changes(update_data: Dict) -> bool:
    """Verificar si hay cambios significativos"""
    significant_fields = ['start_time', 'end_time', 'location', 'platform', 'title']
    return any(field in update_data for field in significant_fields)


def _calculate_time_until_start(start_time: datetime) -> Dict:
    """Calcular tiempo hasta el inicio de la reunión"""
    now = datetime.utcnow()
    delta = start_time - now
    
    if delta.total_seconds() < 0:
        return {'status': 'started'}
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return {
        'status': 'upcoming',
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'total_minutes': int(delta.total_seconds() / 60)
    }


def _can_join_meeting(meeting: Meeting, user: User) -> bool:
    """Verificar si el usuario puede unirse a la reunión"""
    now = datetime.utcnow()
    
    # Verificar tiempo (15 minutos antes hasta 30 minutos después)
    start_buffer = meeting.start_time - timedelta(minutes=15)
    end_buffer = meeting.end_time + timedelta(minutes=30)
    
    if not (start_buffer <= now <= end_buffer):
        return False
    
    # Verificar estado
    if meeting.status not in ['scheduled', 'in_progress']:
        return False
    
    # Verificar permisos
    return check_meeting_access(user, meeting, 'join')


# Manejo de errores específicos del blueprint
@meetings_bp.errorhandler(ValidationException)
def handle_validation_exception(e):
    return jsonify({
        'error': 'Validation Error',
        'message': str(e),
        'status_code': 400
    }), 400


@meetings_bp.errorhandler(BusinessException)
def handle_business_exception(e):
    return jsonify({
        'error': 'Business Logic Error',
        'message': str(e),
        'status_code': 400
    }), 400


@meetings_bp.errorhandler(IntegrationException)
def handle_integration_exception(e):
    return jsonify({
        'error': 'Integration Error',
        'message': str(e),
        'status_code': 503
    }), 503


# Registro de hooks del blueprint
@meetings_bp.before_request
def before_request():
    """Ejecutar antes de cada request"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Log de request para audit
    current_app.logger.info(
        f"Meetings API Request: {request.method} {request.path} by user {current_user.id}"
    )


@meetings_bp.after_request
def after_request(response):
    """Ejecutar después de cada request"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-API-Version'] = '1.0'
    
    return response