"""
Google Meet Service - Ecosistema de Emprendimiento
Servicio completo de integración con Google Meet API

Author: jusga
Version: 1.0.0
"""

import logging
import json
import asyncio
import base64
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, asdict
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import re
import uuid

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.auth.exceptions

from flask import current_app, request, url_for
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, cache, redis_client
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ExternalServiceError,
    AuthenticationError
)
from app.core.constants import (
    USER_ROLES,
    MEETING_TYPES,
    MEETING_STATUS,
    RECORDING_STATUS
)
from app.models.user import User
from app.models.meeting import Meeting
from app.models.mentorship import Mentorship
from app.models.project import Project
from app.models.meet_room import MeetRoom
from app.models.meet_recording import MeetRecording
from app.models.meet_participant import MeetParticipant
from app.models.meet_transcript import MeetTranscript
from app.models.meet_analytics import MeetAnalytics
from app.services.base import BaseService
from app.services.google_calendar import GoogleCalendarService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.utils.decorators import log_activity, retry_on_failure, rate_limit
from app.utils.validators import validate_email, validate_url
from app.utils.formatters import format_datetime, format_duration
from app.utils.date_utils import (
    convert_timezone, 
    get_user_timezone,
    parse_datetime,
    is_business_hours
)
from app.utils.crypto_utils import encrypt_data, decrypt_data, generate_hash


logger = logging.getLogger(__name__)


class MeetingType(Enum):
    """Tipos de reunión"""
    MENTORSHIP = "mentorship"
    PROJECT_REVIEW = "project_review"
    TEAM_MEETING = "team_meeting"
    INVESTOR_PITCH = "investor_pitch"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    ONE_ON_ONE = "one_on_one"
    GROUP_SESSION = "group_session"


class MeetingStatus(Enum):
    """Estados de reunión"""
    SCHEDULED = "scheduled"
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ParticipantStatus(Enum):
    """Estado de participantes"""
    INVITED = "invited"
    JOINED = "joined"
    LEFT = "left"
    REMOVED = "removed"
    DECLINED = "declined"


class RecordingStatus(Enum):
    """Estado de grabación"""
    NOT_STARTED = "not_started"
    RECORDING = "recording"
    STOPPED = "stopped"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MeetingQuality(Enum):
    """Calidad de la reunión"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class MeetParticipant:
    """Participante de reunión"""
    user_id: Optional[int] = None
    email: str = ""
    name: str = ""
    role: str = "attendee"  # organizer, presenter, attendee
    status: str = ParticipantStatus.INVITED.value
    join_time: Optional[datetime] = None
    leave_time: Optional[datetime] = None
    duration_minutes: int = 0
    is_external: bool = False
    permissions: Optional[Dict[str, bool]] = None


@dataclass
class MeetConfiguration:
    """Configuración de reunión"""
    auto_admit_policy: str = "anyone_in_organization"  # anyone, anyone_in_organization, organizer_only
    enable_recording: bool = False
    auto_start_recording: bool = False
    enable_transcription: bool = False
    enable_live_captions: bool = True
    enable_chat: bool = True
    enable_screen_sharing: bool = True
    enable_breakout_rooms: bool = False
    max_participants: int = 100
    waiting_room_enabled: bool = False
    require_authentication: bool = False
    allow_anonymous_users: bool = True
    mute_on_entry: bool = False
    video_on_entry: bool = True
    recording_layout: str = "gallery"  # gallery, speaker, presentation


@dataclass
class MeetRoom:
    """Sala de reunión virtual"""
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    meet_url: Optional[str] = None
    phone_number: Optional[str] = None
    pin: Optional[str] = None
    organizer_email: str = ""
    participants: List[MeetParticipant] = None
    configuration: Optional[MeetConfiguration] = None
    created_at: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: str = MeetingStatus.SCHEDULED.value
    recording_enabled: bool = False
    recording_url: Optional[str] = None
    transcript_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MeetingMetrics:
    """Métricas de reunión"""
    total_participants: int = 0
    max_concurrent_participants: int = 0
    total_duration_minutes: int = 0
    average_participant_duration: float = 0.0
    join_success_rate: float = 100.0
    audio_quality_score: float = 0.0
    video_quality_score: float = 0.0
    overall_quality: str = MeetingQuality.GOOD.value
    recording_duration_minutes: int = 0
    chat_messages_count: int = 0
    screen_sharing_duration_minutes: int = 0
    network_issues_count: int = 0


@dataclass
class MeetingAnalytics:
    """Analytics detallados de reunión"""
    meeting_id: str
    metrics: MeetingMetrics
    participant_analytics: List[Dict[str, Any]]
    engagement_score: float
    sentiment_analysis: Optional[Dict[str, Any]] = None
    key_topics: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    follow_up_suggestions: Optional[List[str]] = None


class GoogleMeetService(BaseService):
    """
    Servicio completo de integración con Google Meet
    
    Funcionalidades:
    - Creación y gestión de salas Meet
    - Integración con Google Calendar
    - Gestión de participantes y permisos
    - Grabación automática con transcripción
    - Analytics y métricas detalladas
    - Integración con ecosistema de emprendimiento
    - Webhooks para eventos en tiempo real
    - Gestión de salas recurrentes
    - Breakout rooms automáticos
    - Live streaming para webinars
    - API de administración completa
    - Compliance y seguridad empresarial
    """
    
    def __init__(self):
        super().__init__()
        self.calendar_service = GoogleCalendarService()
        self.notification_service = NotificationService()
        self.analytics_service = AnalyticsService()
        self.executor = ThreadPoolExecutor(max_workers=8)
        self._setup_meet_scopes()
    
    def _setup_meet_scopes(self):
        """Configurar scopes adicionales para Google Meet"""
        self.meet_scopes = [
            'https://www.googleapis.com/auth/meetings',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/admin.directory.user.readonly'
        ]
    
    @log_activity("meet_room_created")
    def create_meeting(
        self,
        organizer_id: int,
        title: str,
        start_time: datetime,
        duration_minutes: int,
        participants: List[Dict[str, Any]],
        meeting_type: str = MeetingType.TEAM_MEETING.value,
        description: Optional[str] = None,
        configuration: Optional[MeetConfiguration] = None,
        calendar_event_id: Optional[str] = None
    ) -> MeetRoom:
        """
        Crear nueva reunión de Google Meet
        
        Args:
            organizer_id: ID del organizador
            title: Título de la reunión
            start_time: Hora de inicio
            duration_minutes: Duración en minutos
            participants: Lista de participantes
            meeting_type: Tipo de reunión
            description: Descripción opcional
            configuration: Configuración personalizada
            calendar_event_id: ID de evento de calendario asociado
            
        Returns:
            MeetRoom: Sala de reunión creada
        """
        try:
            # Validar organizador
            organizer = User.query.get(organizer_id)
            if not organizer:
                raise NotFoundError(f"Organizador {organizer_id} no encontrado")
            
            # Obtener credenciales
            credentials = self.calendar_service._get_user_credentials(organizer_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            # Configuración por defecto
            if not configuration:
                configuration = self._get_default_configuration(meeting_type)
            
            # Crear evento en Calendar si no existe
            if not calendar_event_id:
                calendar_event = self._create_calendar_event(
                    organizer_id, title, start_time, duration_minutes, 
                    participants, description
                )
                calendar_event_id = calendar_event.id
            
            # Crear sala Meet
            meet_room = self._create_meet_room_via_calendar(
                credentials, calendar_event_id, configuration
            )
            
            # Preparar participantes
            formatted_participants = self._format_participants(participants)
            
            # Crear registro en base de datos
            meet_room_obj = MeetRoom(
                name=title,
                description=description,
                meet_url=meet_room['hangoutLink'],
                organizer_email=organizer.email,
                participants=formatted_participants,
                configuration=configuration,
                scheduled_start=start_time,
                scheduled_end=start_time + timedelta(minutes=duration_minutes),
                status=MeetingStatus.SCHEDULED.value,
                recording_enabled=configuration.enable_recording,
                metadata={
                    'meeting_type': meeting_type,
                    'organizer_id': organizer_id,
                    'calendar_event_id': calendar_event_id,
                    'created_via': 'api'
                }
            )
            
            # Almacenar en base de datos
            room_id = self._store_meet_room(meet_room_obj)
            meet_room_obj.id = room_id
            
            # Configurar webhooks para la reunión
            self._setup_meeting_webhooks(room_id, credentials)
            
            # Enviar invitaciones
            self._send_meeting_invitations(meet_room_obj, formatted_participants)
            
            # Programar recordatorios
            self._schedule_meeting_reminders(meet_room_obj)
            
            # Configurar grabación automática si está habilitada
            if configuration.enable_recording and configuration.auto_start_recording:
                self._schedule_auto_recording(room_id, start_time)
            
            logger.info(f"Reunión Meet creada: {room_id} por usuario {organizer_id}")
            return meet_room_obj
            
        except Exception as e:
            logger.error(f"Error creando reunión Meet: {str(e)}")
            raise BusinessLogicError(f"Error creando reunión: {str(e)}")
    
    @rate_limit(max_requests=30, window=60)
    def get_meeting(self, meeting_id: str, user_id: int) -> MeetRoom:
        """
        Obtener información de reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que solicita
            
        Returns:
            MeetRoom: Información de la reunión
        """
        try:
            # Obtener desde base de datos
            meeting = Meeting.query.filter_by(
                google_meet_room_id=meeting_id
            ).first()
            
            if not meeting:
                raise NotFoundError(f"Reunión {meeting_id} no encontrada")
            
            # Verificar permisos
            if not self._can_access_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para acceder a esta reunión")
            
            # Obtener participantes actuales
            participants = self._get_meeting_participants(meeting_id)
            
            # Obtener métricas en tiempo real
            metrics = self._get_real_time_metrics(meeting_id)
            
            # Construir objeto MeetRoom
            meet_room = MeetRoom(
                id=meeting_id,
                name=meeting.title,
                description=meeting.description,
                meet_url=meeting.google_meet_url,
                organizer_email=meeting.organizer_email,
                participants=participants,
                scheduled_start=meeting.start_time,
                scheduled_end=meeting.end_time,
                actual_start=meeting.actual_start_time,
                actual_end=meeting.actual_end_time,
                status=meeting.status,
                recording_enabled=meeting.recording_enabled,
                recording_url=meeting.recording_url,
                transcript_url=meeting.transcript_url,
                metadata=json.loads(meeting.metadata) if meeting.metadata else {}
            )
            
            return meet_room
            
        except Exception as e:
            logger.error(f"Error obteniendo reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo reunión: {str(e)}")
    
    @rate_limit(max_requests=20, window=60)
    def update_meeting(
        self,
        meeting_id: str,
        user_id: int,
        updates: Dict[str, Any]
    ) -> MeetRoom:
        """
        Actualizar configuración de reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que actualiza
            updates: Datos a actualizar
            
        Returns:
            MeetRoom: Reunión actualizada
        """
        try:
            # Obtener reunión actual
            meeting = self.get_meeting(meeting_id, user_id)
            
            # Verificar permisos de edición
            if not self._can_edit_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para editar esta reunión")
            
            # Validar actualizaciones
            self._validate_meeting_updates(updates)
            
            # Aplicar actualizaciones
            if 'name' in updates:
                meeting.name = updates['name']
            
            if 'description' in updates:
                meeting.description = updates['description']
            
            if 'scheduled_start' in updates:
                meeting.scheduled_start = parse_datetime(updates['scheduled_start'])
            
            if 'scheduled_end' in updates:
                meeting.scheduled_end = parse_datetime(updates['scheduled_end'])
            
            if 'configuration' in updates:
                meeting.configuration = MeetConfiguration(**updates['configuration'])
            
            # Actualizar en base de datos
            self._update_meeting_record(meeting_id, updates)
            
            # Actualizar evento de calendario si es necesario
            if any(k in updates for k in ['name', 'scheduled_start', 'scheduled_end']):
                self._update_calendar_event(meeting, updates)
            
            # Notificar cambios a participantes
            self._notify_meeting_changes(meeting, updates)
            
            logger.info(f"Reunión {meeting_id} actualizada por usuario {user_id}")
            return meeting
            
        except Exception as e:
            logger.error(f"Error actualizando reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error actualizando reunión: {str(e)}")
    
    def cancel_meeting(
        self,
        meeting_id: str,
        user_id: int,
        reason: Optional[str] = None,
        notify_participants: bool = True
    ) -> bool:
        """
        Cancelar reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que cancela
            reason: Razón de cancelación
            notify_participants: Notificar a participantes
            
        Returns:
            bool: True si se canceló correctamente
        """
        try:
            # Obtener reunión
            meeting = self.get_meeting(meeting_id, user_id)
            
            # Verificar permisos
            if not self._can_cancel_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para cancelar esta reunión")
            
            # Verificar que no esté en progreso
            if meeting.status == MeetingStatus.IN_PROGRESS.value:
                # Terminar reunión en progreso
                self.end_meeting(meeting_id, user_id)
            
            # Actualizar estado
            meeting.status = MeetingStatus.CANCELLED.value
            
            # Actualizar en base de datos
            self._update_meeting_status(meeting_id, MeetingStatus.CANCELLED.value, {
                'cancelled_by': user_id,
                'cancelled_at': datetime.utcnow(),
                'cancellation_reason': reason
            })
            
            # Cancelar evento de calendario
            if meeting.metadata and meeting.metadata.get('calendar_event_id'):
                self._cancel_calendar_event(meeting.metadata['calendar_event_id'], user_id)
            
            # Notificar a participantes
            if notify_participants:
                self._notify_meeting_cancellation(meeting, reason)
            
            # Cancelar recordatorios programados
            self._cancel_meeting_reminders(meeting_id)
            
            logger.info(f"Reunión {meeting_id} cancelada por usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelando reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error cancelando reunión: {str(e)}")
    
    def start_meeting(
        self,
        meeting_id: str,
        user_id: int,
        auto_record: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Iniciar reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que inicia
            auto_record: Iniciar grabación automáticamente
            
        Returns:
            Dict[str, Any]: Información de inicio de reunión
        """
        try:
            # Obtener reunión
            meeting = self.get_meeting(meeting_id, user_id)
            
            # Verificar permisos
            if not self._can_start_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para iniciar esta reunión")
            
            # Verificar estado
            if meeting.status not in [MeetingStatus.SCHEDULED.value, MeetingStatus.STARTING.value]:
                raise ValidationError(f"No se puede iniciar reunión en estado: {meeting.status}")
            
            # Actualizar estado
            actual_start = datetime.utcnow()
            self._update_meeting_status(meeting_id, MeetingStatus.IN_PROGRESS.value, {
                'actual_start_time': actual_start,
                'started_by': user_id
            })
            
            # Iniciar grabación si está configurada
            recording_started = False
            if (auto_record is True or 
                (auto_record is None and meeting.configuration and meeting.configuration.auto_start_recording)):
                recording_started = self.start_recording(meeting_id, user_id)
            
            # Iniciar transcripción si está habilitada
            transcription_started = False
            if meeting.configuration and meeting.configuration.enable_transcription:
                transcription_started = self._start_transcription(meeting_id)
            
            # Registrar analytics
            self.analytics_service.track_event(
                event_type='meeting_started',
                user_id=user_id,
                properties={
                    'meeting_id': meeting_id,
                    'meeting_type': meeting.metadata.get('meeting_type'),
                    'participant_count': len(meeting.participants),
                    'recording_enabled': recording_started,
                    'transcription_enabled': transcription_started
                }
            )
            
            # Notificar inicio a participantes
            self._notify_meeting_started(meeting)
            
            result = {
                'meeting_id': meeting_id,
                'meet_url': meeting.meet_url,
                'status': MeetingStatus.IN_PROGRESS.value,
                'started_at': actual_start,
                'recording_started': recording_started,
                'transcription_started': transcription_started,
                'participant_count': len(meeting.participants)
            }
            
            logger.info(f"Reunión {meeting_id} iniciada por usuario {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error iniciando reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error iniciando reunión: {str(e)}")
    
    def end_meeting(
        self,
        meeting_id: str,
        user_id: int,
        save_recording: bool = True
    ) -> Dict[str, Any]:
        """
        Finalizar reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que finaliza
            save_recording: Guardar grabación automáticamente
            
        Returns:
            Dict[str, Any]: Resumen de la reunión finalizada
        """
        try:
            # Obtener reunión
            meeting = self.get_meeting(meeting_id, user_id)
            
            # Verificar permisos
            if not self._can_end_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para finalizar esta reunión")
            
            # Verificar estado
            if meeting.status != MeetingStatus.IN_PROGRESS.value:
                raise ValidationError(f"No se puede finalizar reunión en estado: {meeting.status}")
            
            actual_end = datetime.utcnow()
            
            # Obtener métricas finales
            final_metrics = self._collect_final_metrics(meeting_id)
            
            # Finalizar grabación si está activa
            recording_info = None
            if meeting.recording_enabled:
                recording_info = self.stop_recording(meeting_id, user_id, save_recording)
            
            # Finalizar transcripción
            transcript_info = None
            if meeting.configuration and meeting.configuration.enable_transcription:
                transcript_info = self._stop_transcription(meeting_id)
            
            # Actualizar estado
            self._update_meeting_status(meeting_id, MeetingStatus.ENDED.value, {
                'actual_end_time': actual_end,
                'ended_by': user_id,
                'final_metrics': final_metrics,
                'total_duration_minutes': int((actual_end - meeting.actual_start).total_seconds() / 60)
            })
            
            # Generar analytics automáticos
            analytics = self._generate_meeting_analytics(meeting_id, final_metrics)
            
            # Guardar participantes finales
            self._save_final_participants(meeting_id)
            
            # Registrar en analytics generales
            self.analytics_service.track_event(
                event_type='meeting_ended',
                user_id=user_id,
                properties={
                    'meeting_id': meeting_id,
                    'duration_minutes': final_metrics.total_duration_minutes,
                    'participant_count': final_metrics.total_participants,
                    'recording_saved': recording_info is not None,
                    'transcript_generated': transcript_info is not None
                }
            )
            
            # Programar tareas post-reunión
            self._schedule_post_meeting_tasks(meeting_id)
            
            # Notificar finalización
            self._notify_meeting_ended(meeting, final_metrics)
            
            result = {
                'meeting_id': meeting_id,
                'status': MeetingStatus.ENDED.value,
                'ended_at': actual_end,
                'duration_minutes': final_metrics.total_duration_minutes,
                'participant_count': final_metrics.total_participants,
                'recording_info': recording_info,
                'transcript_info': transcript_info,
                'analytics': analytics,
                'summary_url': url_for('api.meeting_summary', meeting_id=meeting_id, _external=True)
            }
            
            logger.info(f"Reunión {meeting_id} finalizada por usuario {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error finalizando reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error finalizando reunión: {str(e)}")
    
    def start_recording(
        self,
        meeting_id: str,
        user_id: int,
        layout: str = "gallery"
    ) -> bool:
        """
        Iniciar grabación de reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario
            layout: Layout de grabación (gallery, speaker, presentation)
            
        Returns:
            bool: True si se inició correctamente
        """
        try:
            # Verificar permisos
            meeting = self.get_meeting(meeting_id, user_id)
            
            if not self._can_record_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para grabar esta reunión")
            
            # Verificar estado de la reunión
            if meeting.status != MeetingStatus.IN_PROGRESS.value:
                raise ValidationError("Solo se puede grabar reuniones en progreso")
            
            # Iniciar grabación via Google Meet API
            recording_started = self._start_meet_recording(meeting_id, layout)
            
            if recording_started:
                # Actualizar estado en base de datos
                self._update_recording_status(meeting_id, RecordingStatus.RECORDING.value, {
                    'recording_started_by': user_id,
                    'recording_started_at': datetime.utcnow(),
                    'recording_layout': layout
                })
                
                # Notificar a participantes
                self._notify_recording_started(meeting)
                
                # Registrar evento
                self.analytics_service.track_event(
                    event_type='recording_started',
                    user_id=user_id,
                    properties={
                        'meeting_id': meeting_id,
                        'layout': layout
                    }
                )
            
            return recording_started
            
        except Exception as e:
            logger.error(f"Error iniciando grabación {meeting_id}: {str(e)}")
            return False
    
    def stop_recording(
        self,
        meeting_id: str,
        user_id: int,
        save_to_drive: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Detener grabación de reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario
            save_to_drive: Guardar en Google Drive
            
        Returns:
            Optional[Dict[str, Any]]: Información de la grabación
        """
        try:
            # Verificar permisos
            meeting = self.get_meeting(meeting_id, user_id)
            
            if not self._can_record_meeting(meeting, user_id):
                raise PermissionError("No tiene permisos para controlar grabación")
            
            # Detener grabación
            recording_info = self._stop_meet_recording(meeting_id)
            
            if recording_info:
                # Actualizar estado
                self._update_recording_status(meeting_id, RecordingStatus.PROCESSING.value, {
                    'recording_stopped_by': user_id,
                    'recording_stopped_at': datetime.utcnow(),
                    'recording_duration_minutes': recording_info.get('duration_minutes', 0)
                })
                
                # Programar procesamiento
                if save_to_drive:
                    self._schedule_recording_processing(meeting_id, recording_info)
                
                # Notificar a participantes
                self._notify_recording_stopped(meeting, recording_info)
                
                return recording_info
            
            return None
            
        except Exception as e:
            logger.error(f"Error deteniendo grabación {meeting_id}: {str(e)}")
            return None
    
    def create_mentorship_meeting(
        self,
        mentorship_id: int,
        start_time: datetime,
        duration_minutes: int = 60,
        title: Optional[str] = None,
        agenda: Optional[str] = None,
        auto_record: bool = False
    ) -> MeetRoom:
        """
        Crear reunión específica para mentoría
        
        Args:
            mentorship_id: ID de la mentoría
            start_time: Hora de inicio
            duration_minutes: Duración en minutos
            title: Título personalizado
            agenda: Agenda de la sesión
            auto_record: Grabar automáticamente
            
        Returns:
            MeetRoom: Sala de reunión creada
        """
        try:
            # Obtener datos de mentoría
            mentorship = Mentorship.query.get(mentorship_id)
            if not mentorship:
                raise NotFoundError(f"Mentoría {mentorship_id} no encontrada")
            
            entrepreneur = mentorship.entrepreneur
            ally = mentorship.ally
            
            # Configuración específica para mentoría
            config = MeetConfiguration(
                auto_admit_policy="anyone_in_organization",
                enable_recording=auto_record,
                auto_start_recording=auto_record,
                enable_transcription=True,
                enable_live_captions=True,
                enable_chat=True,
                enable_screen_sharing=True,
                max_participants=10,
                waiting_room_enabled=False,
                mute_on_entry=False,
                video_on_entry=True
            )
            
            # Preparar participantes
            participants = [
                {
                    'email': entrepreneur.user.email,
                    'name': entrepreneur.user.full_name,
                    'role': 'attendee',
                    'user_id': entrepreneur.user_id
                },
                {
                    'email': ally.user.email,
                    'name': ally.user.full_name,
                    'role': 'presenter',
                    'user_id': ally.user_id
                }
            ]
            
            # Título automático si no se proporciona
            if not title:
                title = f"Mentoría: {entrepreneur.user.full_name} - {ally.user.full_name}"
            
            # Descripción con agenda
            description_parts = [
                f"Sesión de mentoría entre {entrepreneur.user.full_name} y {ally.user.full_name}",
                "",
                f"Proyecto: {mentorship.project.title if mentorship.project else 'General'}",
                f"Especialidad del mentor: {ally.expertise or 'No especificada'}",
                ""
            ]
            
            if agenda:
                description_parts.extend([
                    "Agenda:",
                    agenda,
                    ""
                ])
            
            description_parts.extend([
                "Esta reunión ha sido generada automáticamente por el Sistema de Emprendimiento.",
                f"ID de Mentoría: {mentorship_id}"
            ])
            
            description = "\n".join(description_parts)
            
            # Crear reunión
            meet_room = self.create_meeting(
                organizer_id=ally.user_id,
                title=title,
                start_time=start_time,
                duration_minutes=duration_minutes,
                participants=participants,
                meeting_type=MeetingType.MENTORSHIP.value,
                description=description,
                configuration=config
            )
            
            # Asociar con mentoría en base de datos
            self._associate_meeting_with_mentorship(meet_room.id, mentorship_id)
            
            # Crear registro en tabla de reuniones
            meeting = Meeting(
                mentorship_id=mentorship_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=duration_minutes),
                google_meet_url=meet_room.meet_url,
                google_meet_room_id=meet_room.id,
                organizer_email=ally.user.email,
                status=MeetingStatus.SCHEDULED.value,
                recording_enabled=auto_record,
                created_by_id=ally.user_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(meeting)
            db.session.commit()
            
            # Enviar notificaciones específicas de mentoría
            self._send_mentorship_meeting_notifications(mentorship, meet_room)
            
            logger.info(f"Reunión de mentoría creada: {meet_room.id} para mentoría {mentorship_id}")
            return meet_room
            
        except Exception as e:
            logger.error(f"Error creando reunión de mentoría: {str(e)}")
            raise BusinessLogicError(f"Error creando reunión de mentoría: {str(e)}")
    
    def get_user_meetings(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status_filter: Optional[List[str]] = None,
        meeting_type_filter: Optional[str] = None,
        include_past: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Obtener reuniones de un usuario
        
        Args:
            user_id: ID del usuario
            start_date: Fecha de inicio del filtro
            end_date: Fecha de fin del filtro
            status_filter: Filtro por estados
            meeting_type_filter: Filtro por tipo de reunión
            include_past: Incluir reuniones pasadas
            
        Returns:
            List[Dict[str, Any]]: Lista de reuniones
        """
        try:
            user = User.query.get(user_id)
            if not user:
                raise NotFoundError(f"Usuario {user_id} no encontrado")
            
            # Construir query base
            query = Meeting.query.filter(
                or_(
                    Meeting.organizer_email == user.email,
                    Meeting.participants.contains(user.email)
                )
            )
            
            # Aplicar filtros de fecha
            if start_date:
                query = query.filter(Meeting.start_time >= start_date)
            
            if end_date:
                query = query.filter(Meeting.start_time <= end_date)
            
            if not include_past:
                query = query.filter(Meeting.start_time >= datetime.utcnow())
            
            # Aplicar filtros de estado
            if status_filter:
                query = query.filter(Meeting.status.in_(status_filter))
            
            # Aplicar filtro de tipo
            if meeting_type_filter:
                query = query.filter(Meeting.metadata.contains(f'"meeting_type": "{meeting_type_filter}"'))
            
            # Ordenar por fecha
            meetings = query.order_by(Meeting.start_time.desc()).all()
            
            # Formatear resultados
            results = []
            for meeting in meetings:
                meeting_data = {
                    'id': meeting.google_meet_room_id,
                    'title': meeting.title,
                    'description': meeting.description,
                    'start_time': meeting.start_time,
                    'end_time': meeting.end_time,
                    'meet_url': meeting.google_meet_url,
                    'status': meeting.status,
                    'organizer_email': meeting.organizer_email,
                    'recording_enabled': meeting.recording_enabled,
                    'recording_url': meeting.recording_url,
                    'participant_count': len(json.loads(meeting.participants)) if meeting.participants else 0,
                    'duration_minutes': int((meeting.end_time - meeting.start_time).total_seconds() / 60) if meeting.end_time and meeting.start_time else 0,
                    'metadata': json.loads(meeting.metadata) if meeting.metadata else {},
                    'can_join': self._can_join_meeting(meeting, user_id),
                    'can_manage': self._can_manage_meeting(meeting, user_id)
                }
                
                # Agregar información específica de mentoría si aplica
                if meeting.mentorship_id:
                    mentorship = Mentorship.query.get(meeting.mentorship_id)
                    if mentorship:
                        meeting_data['mentorship'] = {
                            'id': mentorship.id,
                            'entrepreneur_name': mentorship.entrepreneur.user.full_name,
                            'ally_name': mentorship.ally.user.full_name,
                            'project_title': mentorship.project.title if mentorship.project else None
                        }
                
                results.append(meeting_data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error obteniendo reuniones de usuario {user_id}: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo reuniones: {str(e)}")
    
    def get_meeting_analytics(
        self,
        meeting_id: str,
        user_id: int,
        include_detailed: bool = False
    ) -> MeetingAnalytics:
        """
        Obtener analytics detallados de reunión
        
        Args:
            meeting_id: ID de la reunión
            user_id: ID del usuario que solicita
            include_detailed: Incluir análisis detallado
            
        Returns:
            MeetingAnalytics: Analytics de la reunión
        """
        try:
            # Verificar acceso
            meeting = self.get_meeting(meeting_id, user_id)
            
            # Obtener métricas básicas
            metrics = self._get_stored_metrics(meeting_id)
            
            # Obtener analytics de participantes
            participant_analytics = self._get_participant_analytics(meeting_id)
            
            # Calcular engagement score
            engagement_score = self._calculate_engagement_score(metrics, participant_analytics)
            
            analytics = MeetingAnalytics(
                meeting_id=meeting_id,
                metrics=metrics,
                participant_analytics=participant_analytics,
                engagement_score=engagement_score
            )
            
            if include_detailed:
                # Análisis de sentimientos (si hay transcripción)
                analytics.sentiment_analysis = self._analyze_meeting_sentiment(meeting_id)
                
                # Extracción de temas clave
                analytics.key_topics = self._extract_key_topics(meeting_id)
                
                # Detección de action items
                analytics.action_items = self._extract_action_items(meeting_id)
                
                # Sugerencias de seguimiento
                analytics.follow_up_suggestions = self._generate_follow_up_suggestions(meeting_id)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error obteniendo analytics de reunión {meeting_id}: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo analytics: {str(e)}")
    
    # Métodos privados para funcionalidades específicas
    def _get_default_configuration(self, meeting_type: str) -> MeetConfiguration:
        """Obtener configuración por defecto según tipo de reunión"""
        configs = {
            MeetingType.MENTORSHIP.value: MeetConfiguration(
                enable_recording=True,
                auto_start_recording=False,
                enable_transcription=True,
                max_participants=5,
                waiting_room_enabled=False
            ),
            MeetingType.INVESTOR_PITCH.value: MeetConfiguration(
                enable_recording=True,
                auto_start_recording=True,
                enable_transcription=True,
                max_participants=20,
                waiting_room_enabled=True,
                require_authentication=True
            ),
            MeetingType.WEBINAR.value: MeetConfiguration(
                enable_recording=True,
                auto_start_recording=True,
                enable_transcription=False,
                max_participants=500,
                waiting_room_enabled=False,
                mute_on_entry=True,
                video_on_entry=False
            )
        }
        
        return configs.get(meeting_type, MeetConfiguration())
    
    def _create_calendar_event(
        self,
        organizer_id: int,
        title: str,
        start_time: datetime,
        duration_minutes: int,
        participants: List[Dict[str, Any]],
        description: Optional[str]
    ):
        """Crear evento de calendario para la reunión"""
        from app.services.google_calendar import CalendarEvent
        
        # Formatear asistentes
        attendees = []
        for participant in participants:
            attendees.append({
                'email': participant['email'],
                'responseStatus': 'needsAction'
            })
        
        # Crear evento
        calendar_event = CalendarEvent(
            summary=title,
            description=description,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=duration_minutes),
            attendees=attendees,
            conference_solution={
                'conferenceType': 'hangoutsMeet'
            }
        )
        
        return self.calendar_service.create_event(organizer_id, calendar_event)
    
    def _create_meet_room_via_calendar(
        self,
        credentials: Credentials,
        calendar_event_id: str,
        configuration: MeetConfiguration
    ) -> Dict[str, Any]:
        """Crear sala Meet a través del evento de calendario"""
        try:
            calendar_service = build('calendar', 'v3', credentials=credentials)
            
            # Obtener evento para extraer Meet URL
            event = calendar_service.events().get(
                calendarId='primary',
                eventId=calendar_event_id
            ).execute()
            
            # Extraer información de Meet
            meet_info = {
                'eventId': calendar_event_id,
                'hangoutLink': event.get('hangoutLink'),
                'conferenceData': event.get('conferenceData', {})
            }
            
            if not meet_info['hangoutLink']:
                raise ExternalServiceError("No se pudo crear la sala de Meet")
            
            return meet_info
            
        except HttpError as e:
            logger.error(f"Error creando sala Meet: {str(e)}")
            raise ExternalServiceError(f"Error creando sala Meet: {str(e)}")
    
    def _format_participants(self, participants: List[Dict[str, Any]]) -> List[MeetParticipant]:
        """Formatear lista de participantes"""
        formatted = []
        
        for participant in participants:
            meet_participant = MeetParticipant(
                user_id=participant.get('user_id'),
                email=participant['email'],
                name=participant.get('name', participant['email']),
                role=participant.get('role', 'attendee'),
                status=ParticipantStatus.INVITED.value,
                is_external=participant.get('is_external', False),
                permissions=participant.get('permissions', {
                    'can_share_screen': True,
                    'can_use_chat': True,
                    'can_record': False
                })
            )
            formatted.append(meet_participant)
        
        return formatted
    
    def _store_meet_room(self, meet_room: MeetRoom) -> str:
        """Almacenar sala de reunión en base de datos"""
        try:
            # Generar ID único
            room_id = str(uuid.uuid4())
            
            # Crear registro en tabla meet_rooms
            db_room = MeetRoom(
                id=room_id,
                name=meet_room.name,
                description=meet_room.description,
                meet_url=meet_room.meet_url,
                organizer_email=meet_room.organizer_email,
                scheduled_start=meet_room.scheduled_start,
                scheduled_end=meet_room.scheduled_end,
                status=meet_room.status,
                recording_enabled=meet_room.recording_enabled,
                configuration=json.dumps(asdict(meet_room.configuration)) if meet_room.configuration else None,
                participants=json.dumps([asdict(p) for p in meet_room.participants]) if meet_room.participants else None,
                metadata=json.dumps(meet_room.metadata) if meet_room.metadata else None,
                created_at=datetime.utcnow()
            )
            
            db.session.add(db_room)
            db.session.commit()
            
            return room_id
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error almacenando sala Meet: {str(e)}")
            raise BusinessLogicError("Error almacenando sala de reunión")
    
    def _can_access_meeting(self, meeting: Meeting, user_id: int) -> bool:
        """Verificar si el usuario puede acceder a la reunión"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Administradores pueden acceder a todo
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # Organizador puede acceder
        if meeting.organizer_email == user.email:
            return True
        
        # Participante puede acceder
        if meeting.participants:
            participants_data = json.loads(meeting.participants)
            participant_emails = [p.get('email') for p in participants_data]
            if user.email in participant_emails:
                return True
        
        # Si está asociado con mentoría, verificar acceso
        if meeting.mentorship_id:
            mentorship = Mentorship.query.get(meeting.mentorship_id)
            if mentorship:
                if (mentorship.entrepreneur.user_id == user_id or 
                    mentorship.ally.user_id == user_id):
                    return True
        
        return False
    
    def _send_meeting_invitations(self, meet_room: MeetRoom, participants: List[MeetParticipant]):
        """Enviar invitaciones de reunión"""
        try:
            for participant in participants:
                # Determinar si es usuario interno
                internal_user = None
                if participant.user_id:
                    internal_user = User.query.get(participant.user_id)
                
                if internal_user:
                    # Notificación interna
                    self.notification_service.send_notification(
                        user_id=internal_user.id,
                        type='meeting_invitation',
                        title=f'Invitación a reunión: {meet_room.name}',
                        message=f'Has sido invitado a la reunión "{meet_room.name}" programada para {format_datetime(meet_room.scheduled_start)}',
                        data={
                            'meeting_id': meet_room.id,
                            'meet_url': meet_room.meet_url,
                            'start_time': meet_room.scheduled_start.isoformat(),
                            'role': participant.role
                        }
                    )
                else:
                    # Email externo (implementar envío de email)
                    self._send_external_meeting_invitation(meet_room, participant)
                    
        except Exception as e:
            logger.error(f"Error enviando invitaciones: {str(e)}")
    
    def _send_external_meeting_invitation(self, meet_room: MeetRoom, participant: MeetParticipant):
        """Enviar invitación por email a participante externo"""
        try:
            from app.services.email import email_service
            
            email_service.send_template_email(
                to=participant.email,
                template_name='meeting_invitation',
                template_data={
                    'participant_name': participant.name,
                    'meeting_title': meet_room.name,
                    'meeting_description': meet_room.description,
                    'start_time': meet_room.scheduled_start,
                    'duration_minutes': int((meet_room.scheduled_end - meet_room.scheduled_start).total_seconds() / 60),
                    'meet_url': meet_room.meet_url,
                    'organizer_email': meet_room.organizer_email
                }
            )
        except Exception as e:
            logger.error(f"Error enviando invitación externa: {str(e)}")
    
    def _setup_meeting_webhooks(self, room_id: str, credentials: Credentials):
        """Configurar webhooks para la reunión"""
        try:
            # Implementar webhooks específicos para Google Meet
            # Esto dependería de la disponibilidad de webhooks en Google Meet API
            logger.info(f"Webhooks configurados para reunión {room_id}")
        except Exception as e:
            logger.warning(f"No se pudieron configurar webhooks: {str(e)}")
    
    def _schedule_meeting_reminders(self, meet_room: MeetRoom):
        """Programar recordatorios automáticos"""
        try:
            from app.tasks.meeting_tasks import send_meeting_reminder
            
            # Recordatorio 24 horas antes
            reminder_24h = meet_room.scheduled_start - timedelta(hours=24)
            if reminder_24h > datetime.utcnow():
                send_meeting_reminder.apply_async(
                    args=[meet_room.id, '24_hours'],
                    eta=reminder_24h
                )
            
            # Recordatorio 30 minutos antes
            reminder_30m = meet_room.scheduled_start - timedelta(minutes=30)
            if reminder_30m > datetime.utcnow():
                send_meeting_reminder.apply_async(
                    args=[meet_room.id, '30_minutes'],
                    eta=reminder_30m
                )
            
        except Exception as e:
            logger.error(f"Error programando recordatorios: {str(e)}")
    
    def _schedule_auto_recording(self, room_id: str, start_time: datetime):
        """Programar inicio automático de grabación"""
        try:
            from app.tasks.meeting_tasks import auto_start_recording
            
            # Iniciar grabación 1 minuto después del inicio programado
            auto_start_time = start_time + timedelta(minutes=1)
            
            auto_start_recording.apply_async(
                args=[room_id],
                eta=auto_start_time
            )
            
        except Exception as e:
            logger.error(f"Error programando auto-grabación: {str(e)}")
    
    def _can_edit_meeting(self, meeting: MeetRoom, user_id: int) -> bool:
        """Verificar si el usuario puede editar la reunión"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Administradores pueden editar
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # Organizador puede editar
        if meeting.organizer_email == user.email:
            return True
        
        # Presentadores pueden editar configuración básica
        if meeting.participants:
            for participant in meeting.participants:
                if (participant.email == user.email and 
                    participant.role in ['organizer', 'presenter']):
                    return True
        
        return False
    
    def _validate_meeting_updates(self, updates: Dict[str, Any]):
        """Validar actualizaciones de reunión"""
        if 'scheduled_start' in updates and 'scheduled_end' in updates:
            start = parse_datetime(updates['scheduled_start'])
            end = parse_datetime(updates['scheduled_end'])
            
            if start >= end:
                raise ValidationError("La hora de inicio debe ser anterior a la hora de fin")
            
            if end - start > timedelta(hours=8):
                raise ValidationError("La duración máxima es de 8 horas")
        
        if 'name' in updates and len(updates['name']) < 3:
            raise ValidationError("El título debe tener al menos 3 caracteres")
    
    def _update_meeting_record(self, meeting_id: str, updates: Dict[str, Any]):
        """Actualizar registro de reunión en base de datos"""
        try:
            meeting = Meeting.query.filter_by(
                google_meet_room_id=meeting_id
            ).first()
            
            if meeting:
                if 'name' in updates:
                    meeting.title = updates['name']
                if 'description' in updates:
                    meeting.description = updates['description']
                if 'scheduled_start' in updates:
                    meeting.start_time = parse_datetime(updates['scheduled_start'])
                if 'scheduled_end' in updates:
                    meeting.end_time = parse_datetime(updates['scheduled_end'])
                
                meeting.updated_at = datetime.utcnow()
                db.session.commit()
                
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando reunión: {str(e)}")
    
    def _update_calendar_event(self, meeting: MeetRoom, updates: Dict[str, Any]):
        """Actualizar evento de calendario asociado"""
        try:
            if meeting.metadata and meeting.metadata.get('calendar_event_id'):
                calendar_event_id = meeting.metadata['calendar_event_id']
                organizer_id = meeting.metadata.get('organizer_id')
                
                if organizer_id:
                    from app.services.google_calendar import CalendarEvent
                    
                    calendar_updates = CalendarEvent()
                    
                    if 'name' in updates:
                        calendar_updates.summary = updates['name']
                    if 'description' in updates:
                        calendar_updates.description = updates['description']
                    if 'scheduled_start' in updates:
                        calendar_updates.start_time = parse_datetime(updates['scheduled_start'])
                    if 'scheduled_end' in updates:
                        calendar_updates.end_time = parse_datetime(updates['scheduled_end'])
                    
                    self.calendar_service.update_event(
                        organizer_id, calendar_event_id, calendar_updates
                    )
                    
        except Exception as e:
            logger.error(f"Error actualizando evento de calendario: {str(e)}")
    
    def _notify_meeting_changes(self, meeting: MeetRoom, updates: Dict[str, Any]):
        """Notificar cambios a los participantes"""
        try:
            change_summary = []
            
            if 'name' in updates:
                change_summary.append(f"Título cambiado a: {updates['name']}")
            if 'scheduled_start' in updates:
                new_start = parse_datetime(updates['scheduled_start'])
                change_summary.append(f"Nueva hora de inicio: {format_datetime(new_start)}")
            if 'scheduled_end' in updates:
                new_end = parse_datetime(updates['scheduled_end'])
                change_summary.append(f"Nueva hora de fin: {format_datetime(new_end)}")
            
            if change_summary:
                message = f"La reunión '{meeting.name}' ha sido actualizada:\n" + "\n".join(change_summary)
                
                for participant in meeting.participants:
                    if participant.user_id:
                        self.notification_service.send_notification(
                            user_id=participant.user_id,
                            type='meeting_updated',
                            title='Reunión actualizada',
                            message=message,
                            data={
                                'meeting_id': meeting.id,
                                'changes': updates
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error notificando cambios: {str(e)}")
    
    def _can_cancel_meeting(self, meeting: MeetRoom, user_id: int) -> bool:
        """Verificar si el usuario puede cancelar la reunión"""
        return self._can_edit_meeting(meeting, user_id)
    
    def _update_meeting_status(self, meeting_id: str, status: str, metadata: Dict[str, Any] = None):
        """Actualizar estado de reunión"""
        try:
            meeting = Meeting.query.filter_by(
                google_meet_room_id=meeting_id
            ).first()
            
            if meeting:
                meeting.status = status
                
                if metadata:
                    current_metadata = json.loads(meeting.metadata) if meeting.metadata else {}
                    current_metadata.update(metadata)
                    meeting.metadata = json.dumps(current_metadata)
                
                meeting.updated_at = datetime.utcnow()
                db.session.commit()
                
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando estado: {str(e)}")
    
    def _cancel_calendar_event(self, calendar_event_id: str, user_id: int):
        """Cancelar evento de calendario"""
        try:
            self.calendar_service.delete_event(
                user_id=user_id,
                event_id=calendar_event_id
            )
        except Exception as e:
            logger.error(f"Error cancelando evento de calendario: {str(e)}")
    
    def _notify_meeting_cancellation(self, meeting: MeetRoom, reason: Optional[str]):
        """Notificar cancelación de reunión"""
        try:
            message = f"La reunión '{meeting.name}' ha sido cancelada."
            if reason:
                message += f"\nRazón: {reason}"
            
            for participant in meeting.participants:
                if participant.user_id:
                    self.notification_service.send_notification(
                        user_id=participant.user_id,
                        type='meeting_cancelled',
                        title='Reunión cancelada',
                        message=message,
                        data={
                            'meeting_id': meeting.id,
                            'reason': reason
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error notificando cancelación: {str(e)}")
    
    def _cancel_meeting_reminders(self, meeting_id: str):
        """Cancelar recordatorios programados"""
        try:
            from app.tasks.meeting_tasks import cancel_meeting_reminders
            cancel_meeting_reminders.delay(meeting_id)
        except Exception as e:
            logger.error(f"Error cancelando recordatorios: {str(e)}")
    
    def _can_start_meeting(self, meeting: MeetRoom, user_id: int) -> bool:
        """Verificar si el usuario puede iniciar la reunión"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        # El organizador siempre puede iniciar
        if meeting.organizer_email == user.email:
            return True
        
        # Presentadores pueden iniciar
        if meeting.participants:
            for participant in meeting.participants:
                if (participant.email == user.email and 
                    participant.role in ['organizer', 'presenter']):
                    return True
        
        return False
    
    def _notify_meeting_started(self, meeting: MeetRoom):
        """Notificar inicio de reunión"""
        try:
            for participant in meeting.participants:
                if participant.user_id:
                    self.notification_service.send_notification(
                        user_id=participant.user_id,
                        type='meeting_started',
                        title='Reunión iniciada',
                        message=f"La reunión '{meeting.name}' ha comenzado. ¡Únete ahora!",
                        data={
                            'meeting_id': meeting.id,
                            'meet_url': meeting.meet_url
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error notificando inicio: {str(e)}")
    
    def _can_end_meeting(self, meeting: MeetRoom, user_id: int) -> bool:
        """Verificar si el usuario puede finalizar la reunión"""
        return self._can_start_meeting(meeting, user_id)
    
    def _collect_final_metrics(self, meeting_id: str) -> MeetingMetrics:
        """Recopilar métricas finales de la reunión"""
        try:
            # Obtener datos de participantes
            participants = self._get_meeting_participants(meeting_id)
            
            # Calcular métricas básicas
            total_participants = len(participants)
            max_concurrent = self._get_max_concurrent_participants(meeting_id)
            
            # Obtener duración total
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            total_duration = 0
            if meeting and meeting.actual_start_time:
                end_time = datetime.utcnow()
                total_duration = int((end_time - meeting.actual_start_time).total_seconds() / 60)
            
            # Calcular promedio de duración por participante
            avg_duration = 0
            if participants:
                total_participant_time = sum(p.duration_minutes for p in participants)
                avg_duration = total_participant_time / len(participants)
            
            return MeetingMetrics(
                total_participants=total_participants,
                max_concurrent_participants=max_concurrent,
                total_duration_minutes=total_duration,
                average_participant_duration=avg_duration,
                join_success_rate=100.0,  # Esto se calcularía con datos reales
                audio_quality_score=4.0,   # Esto vendría de la API de Meet
                video_quality_score=4.0,   # Esto vendría de la API de Meet
                overall_quality=MeetingQuality.GOOD.value
            )
            
        except Exception as e:
            logger.error(f"Error recopilando métricas: {str(e)}")
            return MeetingMetrics()
    
    def _get_meeting_participants(self, meeting_id: str) -> List[MeetParticipant]:
        """Obtener participantes actuales de la reunión"""
        try:
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            if meeting and meeting.participants:
                participants_data = json.loads(meeting.participants)
                return [MeetParticipant(**p) for p in participants_data]
            return []
        except Exception as e:
            logger.error(f"Error obteniendo participantes: {str(e)}")
            return []
    
    def _get_real_time_metrics(self, meeting_id: str) -> MeetingMetrics:
        """Obtener métricas en tiempo real"""
        # En una implementación real, esto consultaría la API de Google Meet
        # Por ahora retornamos métricas básicas
        return MeetingMetrics()
    
    def _generate_meeting_analytics(self, meeting_id: str, metrics: MeetingMetrics) -> Dict[str, Any]:
        """Generar analytics automáticos de la reunión"""
        try:
            analytics = {
                'meeting_id': meeting_id,
                'completion_rate': 100.0 if metrics.total_duration_minutes > 0 else 0.0,
                'engagement_score': self._calculate_basic_engagement_score(metrics),
                'quality_assessment': {
                    'audio': metrics.audio_quality_score,
                    'video': metrics.video_quality_score,
                    'overall': metrics.overall_quality
                },
                'participation_stats': {
                    'total_participants': metrics.total_participants,
                    'average_duration': metrics.average_participant_duration,
                    'join_success_rate': metrics.join_success_rate
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error generando analytics: {str(e)}")
            return {}
    
    def _calculate_basic_engagement_score(self, metrics: MeetingMetrics) -> float:
        """Calcular score básico de engagement"""
        if metrics.total_duration_minutes == 0:
            return 0.0
        
        # Score basado en duración promedio vs duración total
        engagement_ratio = min(metrics.average_participant_duration / metrics.total_duration_minutes, 1.0)
        
        # Ajustar por número de participantes
        participation_factor = min(metrics.total_participants / 5.0, 1.0)  # Óptimo: 5 participantes
        
        return (engagement_ratio * 0.7 + participation_factor * 0.3) * 100
    
    def _save_final_participants(self, meeting_id: str):
        """Guardar estado final de participantes"""
        try:
            participants = self._get_meeting_participants(meeting_id)
            
            for participant in participants:
                # Guardar en tabla de participantes si existe
                participant_record = MeetParticipant(
                    meeting_id=meeting_id,
                    user_id=participant.user_id,
                    email=participant.email,
                    name=participant.name,
                    role=participant.role,
                    join_time=participant.join_time,
                    leave_time=participant.leave_time or datetime.utcnow(),
                    duration_minutes=participant.duration_minutes,
                    status=ParticipantStatus.LEFT.value
                )
                
                # Aquí se guardaría en la base de datos
                
        except Exception as e:
            logger.error(f"Error guardando participantes finales: {str(e)}")
    
    def _schedule_post_meeting_tasks(self, meeting_id: str):
        """Programar tareas post-reunión"""
        try:
            from app.tasks.meeting_tasks import process_meeting_recording, generate_meeting_summary
            
            # Procesar grabación después de 5 minutos
            process_meeting_recording.apply_async(
                args=[meeting_id],
                countdown=300
            )
            
            # Generar resumen después de 10 minutos
            generate_meeting_summary.apply_async(
                args=[meeting_id],
                countdown=600
            )
            
        except Exception as e:
            logger.error(f"Error programando tareas post-reunión: {str(e)}")
    
    def _notify_meeting_ended(self, meeting: MeetRoom, metrics: MeetingMetrics):
        """Notificar finalización de reunión"""
        try:
            summary = f"""
            Reunión finalizada: {meeting.name}
            Duración: {metrics.total_duration_minutes} minutos
            Participantes: {metrics.total_participants}
            """
            
            for participant in meeting.participants:
                if participant.user_id:
                    self.notification_service.send_notification(
                        user_id=participant.user_id,
                        type='meeting_ended',
                        title='Reunión finalizada',
                        message=summary,
                        data={
                            'meeting_id': meeting.id,
                            'duration_minutes': metrics.total_duration_minutes
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error notificando finalización: {str(e)}")
    
    # Métodos stub para funcionalidades que requerirían APIs específicas
    def _start_meet_recording(self, meeting_id: str, layout: str) -> bool:
        """Iniciar grabación (requiere Google Meet API específica)"""
        # En implementación real, esto usaría la API de Google Meet
        return True
    
    def _stop_meet_recording(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Detener grabación (requiere Google Meet API específica)"""
        # En implementación real, esto usaría la API de Google Meet
        return {
            'recording_id': f"rec_{meeting_id}",
            'duration_minutes': 60,
            'file_size_mb': 120
        }
    
    def _update_recording_status(self, meeting_id: str, status: str, metadata: Dict[str, Any]):
        """Actualizar estado de grabación"""
        try:
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            if meeting:
                meeting.recording_status = status
                current_metadata = json.loads(meeting.metadata) if meeting.metadata else {}
                current_metadata.update(metadata)
                meeting.metadata = json.dumps(current_metadata)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error actualizando estado de grabación: {str(e)}")
    
    def _notify_recording_started(self, meeting: MeetRoom):
        """Notificar inicio de grabación"""
        try:
            for participant in meeting.participants:
                if participant.user_id:
                    self.notification_service.send_notification(
                        user_id=participant.user_id,
                        type='recording_started',
                        title='Grabación iniciada',
                        message=f"La grabación de '{meeting.name}' ha comenzado",
                        data={'meeting_id': meeting.id}
                    )
        except Exception as e:
            logger.error(f"Error notificando inicio de grabación: {str(e)}")
    
    def _notify_recording_stopped(self, meeting: MeetRoom, recording_info: Dict[str, Any]):
        """Notificar fin de grabación"""
        try:
            for participant in meeting.participants:
                if participant.user_id:
                    self.notification_service.send_notification(
                        user_id=participant.user_id,
                        type='recording_stopped',
                        title='Grabación finalizada',
                        message=f"La grabación de '{meeting.name}' ha finalizado y será procesada",
                        data={
                            'meeting_id': meeting.id,
                            'recording_info': recording_info
                        }
                    )
        except Exception as e:
            logger.error(f"Error notificando fin de grabación: {str(e)}")
    
    def _can_record_meeting(self, meeting: MeetRoom, user_id: int) -> bool:
        """Verificar si el usuario puede grabar la reunión"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Administradores pueden grabar
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # Organizador puede grabar
        if meeting.organizer_email == user.email:
            return True
        
        # Verificar permisos específicos del participante
        if meeting.participants:
            for participant in meeting.participants:
                if (participant.email == user.email and 
                    participant.permissions and 
                    participant.permissions.get('can_record', False)):
                    return True
        
        return False
    
    def _schedule_recording_processing(self, meeting_id: str, recording_info: Dict[str, Any]):
        """Programar procesamiento de grabación"""
        try:
            from app.tasks.meeting_tasks import process_meeting_recording
            
            process_meeting_recording.apply_async(
                args=[meeting_id, recording_info],
                countdown=60  # Procesar después de 1 minuto
            )
            
        except Exception as e:
            logger.error(f"Error programando procesamiento: {str(e)}")
    
    def _start_transcription(self, meeting_id: str) -> bool:
        """Iniciar transcripción automática"""
        try:
            # En implementación real, esto configuraría la transcripción de Google Meet
            logger.info(f"Transcripción iniciada para reunión {meeting_id}")
            return True
        except Exception as e:
            logger.error(f"Error iniciando transcripción: {str(e)}")
            return False
    
    def _stop_transcription(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Detener transcripción"""
        try:
            # En implementación real, esto detendría la transcripción
            return {
                'transcript_id': f"trans_{meeting_id}",
                'word_count': 1500,
                'confidence_score': 0.92
            }
        except Exception as e:
            logger.error(f"Error deteniendo transcripción: {str(e)}")
            return None
    
    def _associate_meeting_with_mentorship(self, meeting_id: str, mentorship_id: int):
        """Asociar reunión con mentoría"""
        try:
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            if meeting:
                meeting.mentorship_id = mentorship_id
                db.session.commit()
        except Exception as e:
            logger.error(f"Error asociando con mentoría: {str(e)}")
    
    def _send_mentorship_meeting_notifications(self, mentorship: Mentorship, meet_room: MeetRoom):
        """Enviar notificaciones específicas de mentoría"""
        try:
            # Notificar al emprendedor
            self.notification_service.send_notification(
                user_id=mentorship.entrepreneur.user_id,
                type='mentorship_meeting_scheduled',
                title='Sesión de mentoría agendada',
                message=f'Tu sesión de mentoría con {mentorship.ally.user.full_name} ha sido agendada para {format_datetime(meet_room.scheduled_start)}',
                data={
                    'meeting_id': meet_room.id,
                    'meet_url': meet_room.meet_url,
                    'mentorship_id': mentorship.id,
                    'ally_name': mentorship.ally.user.full_name
                }
            )
            
            # Notificar al mentor
            self.notification_service.send_notification(
                user_id=mentorship.ally.user_id,
                type='mentorship_meeting_scheduled',
                title='Sesión de mentoría agendada',
                message=f'Tu sesión de mentoría con {mentorship.entrepreneur.user.full_name} ha sido agendada para {format_datetime(meet_room.scheduled_start)}',
                data={
                    'meeting_id': meet_room.id,
                    'meet_url': meet_room.meet_url,
                    'mentorship_id': mentorship.id,
                    'entrepreneur_name': mentorship.entrepreneur.user.full_name
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificaciones de mentoría: {str(e)}")
    
    def _can_join_meeting(self, meeting: Meeting, user_id: int) -> bool:
        """Verificar si el usuario puede unirse a la reunión"""
        # Verificar horario de la reunión
        if meeting.start_time > datetime.utcnow() + timedelta(minutes=15):
            return False  # Muy temprano para unirse
        
        if meeting.end_time < datetime.utcnow() - timedelta(hours=1):
            return False  # Reunión terminó hace más de 1 hora
        
        # Verificar acceso básico
        return self._can_access_meeting(meeting, user_id)
    
    def _can_manage_meeting(self, meeting: Meeting, user_id: int) -> bool:
        """Verificar si el usuario puede gestionar la reunión"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Administradores pueden gestionar
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # Organizador puede gestionar
        if meeting.organizer_email == user.email:
            return True
        
        return False
    
    def _get_max_concurrent_participants(self, meeting_id: str) -> int:
        """Obtener máximo de participantes concurrentes"""
        # En implementación real, esto vendría de analytics de Google Meet
        return len(self._get_meeting_participants(meeting_id))
    
    def _get_stored_metrics(self, meeting_id: str) -> MeetingMetrics:
        """Obtener métricas almacenadas"""
        try:
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            if meeting and meeting.metadata:
                metadata = json.loads(meeting.metadata)
                if 'final_metrics' in metadata:
                    return MeetingMetrics(**metadata['final_metrics'])
            
            return MeetingMetrics()
        except Exception as e:
            logger.error(f"Error obteniendo métricas almacenadas: {str(e)}")
            return MeetingMetrics()
    
    def _get_participant_analytics(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Obtener analytics de participantes"""
        try:
            participants = self._get_meeting_participants(meeting_id)
            analytics = []
            
            for participant in participants:
                participant_data = {
                    'user_id': participant.user_id,
                    'email': participant.email,
                    'name': participant.name,
                    'role': participant.role,
                    'duration_minutes': participant.duration_minutes,
                    'join_time': participant.join_time.isoformat() if participant.join_time else None,
                    'leave_time': participant.leave_time.isoformat() if participant.leave_time else None,
                    'engagement_score': self._calculate_participant_engagement(participant)
                }
                analytics.append(participant_data)
            
            return analytics
        except Exception as e:
            logger.error(f"Error obteniendo analytics de participantes: {str(e)}")
            return []
    
    def _calculate_participant_engagement(self, participant: MeetParticipant) -> float:
        """Calcular engagement de participante individual"""
        if not participant.join_time or participant.duration_minutes == 0:
            return 0.0
        
        # Score básico basado en duración
        base_score = min(participant.duration_minutes / 60.0, 1.0) * 100
        
        # Ajustar por rol
        role_multiplier = {
            'organizer': 1.0,
            'presenter': 1.0,
            'attendee': 0.9
        }.get(participant.role, 0.8)
        
        return base_score * role_multiplier
    
    def _calculate_engagement_score(self, metrics: MeetingMetrics, participant_analytics: List[Dict[str, Any]]) -> float:
        """Calcular score de engagement general"""
        if not participant_analytics:
            return 0.0
        
        # Promedio de engagement de participantes
        participant_scores = [p.get('engagement_score', 0.0) for p in participant_analytics]
        avg_participant_engagement = sum(participant_scores) / len(participant_scores)
        
        # Factor de duración vs planificado
        duration_factor = min(metrics.total_duration_minutes / 60.0, 1.0)
        
        # Factor de participación
        participation_factor = min(metrics.total_participants / 5.0, 1.0)
        
        # Score combinado
        combined_score = (
            avg_participant_engagement * 0.5 +
            duration_factor * 30 +
            participation_factor * 20
        )
        
        return min(combined_score, 100.0)
    
    def _analyze_meeting_sentiment(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Analizar sentimientos de la reunión (requiere transcripción)"""
        try:
            # En implementación real, esto analizaría la transcripción
            return {
                'overall_sentiment': 'positive',
                'sentiment_score': 0.7,
                'emotions': {
                    'positive': 0.6,
                    'neutral': 0.3,
                    'negative': 0.1
                },
                'confidence': 0.85
            }
        except Exception as e:
            logger.error(f"Error analizando sentimientos: {str(e)}")
            return None
    
    def _extract_key_topics(self, meeting_id: str) -> Optional[List[str]]:
        """Extraer temas clave de la reunión"""
        try:
            # En implementación real, esto usaría NLP en la transcripción
            return [
                'estrategia de marketing',
                'presupuesto',
                'timeline del proyecto',
                'próximos pasos'
            ]
        except Exception as e:
            logger.error(f"Error extrayendo temas: {str(e)}")
            return None
    
    def _extract_action_items(self, meeting_id: str) -> Optional[List[str]]:
        """Extraer action items de la reunión"""
        try:
            # En implementación real, esto usaría NLP para detectar tareas
            return [
                'Revisar propuesta de marketing para el viernes',
                'Contactar con proveedores la próxima semana',
                'Preparar presentación para inversores'
            ]
        except Exception as e:
            logger.error(f"Error extrayendo action items: {str(e)}")
            return None
    
    def _generate_follow_up_suggestions(self, meeting_id: str) -> Optional[List[str]]:
        """Generar sugerencias de seguimiento"""
        try:
            meeting = Meeting.query.filter_by(google_meet_room_id=meeting_id).first()
            suggestions = []
            
            if meeting:
                # Sugerencias basadas en tipo de reunión
                if meeting.mentorship_id:
                    suggestions.extend([
                        'Programar siguiente sesión de mentoría en 2 semanas',
                        'Enviar resumen de avances al mentor',
                        'Definir objetivos para próxima reunión'
                    ])
                else:
                    suggestions.extend([
                        'Enviar resumen de la reunión a todos los participantes',
                        'Programar reunión de seguimiento',
                        'Actualizar estado del proyecto'
                    ])
            
            return suggestions
        except Exception as e:
            logger.error(f"Error generando sugerencias: {str(e)}")
            return None
    
    def get_meeting_summary(self, meeting_id: str, user_id: int) -> Dict[str, Any]:
        """Obtener resumen completo de reunión finalizada"""
        try:
            # Verificar acceso
            meeting = self.get_meeting(meeting_id, user_id)
            
            if meeting.status != MeetingStatus.ENDED.value:
                raise ValidationError("Solo se puede obtener resumen de reuniones finalizadas")
            
            # Obtener analytics completos
            analytics = self.get_meeting_analytics(meeting_id, user_id, include_detailed=True)
            
            # Construir resumen
            summary = {
                'meeting_info': {
                    'id': meeting_id,
                    'title': meeting.name,
                    'start_time': meeting.actual_start,
                    'end_time': meeting.actual_end,
                    'duration_minutes': analytics.metrics.total_duration_minutes,
                    'organizer': meeting.organizer_email
                },
                'participants': {
                    'total': analytics.metrics.total_participants,
                    'details': analytics.participant_analytics
                },
                'engagement': {
                    'overall_score': analytics.engagement_score,
                    'quality_assessment': {
                        'audio': analytics.metrics.audio_quality_score,
                        'video': analytics.metrics.video_quality_score,
                        'overall': analytics.metrics.overall_quality
                    }
                },
                'content_analysis': {
                    'key_topics': analytics.key_topics,
                    'action_items': analytics.action_items,
                    'sentiment_analysis': analytics.sentiment_analysis
                },
                'resources': {
                    'recording_url': meeting.recording_url,
                    'transcript_url': meeting.transcript_url
                },
                'follow_up': {
                    'suggestions': analytics.follow_up_suggestions
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generando resumen: {str(e)}")
            raise BusinessLogicError(f"Error generando resumen: {str(e)}")
    
    def bulk_create_meetings(
        self,
        meetings_data: List[Dict[str, Any]],
        organizer_id: int
    ) -> List[Dict[str, Any]]:
        """Crear múltiples reuniones en lote"""
        results = []
        
        for meeting_data in meetings_data:
            try:
                meet_room = self.create_meeting(
                    organizer_id=organizer_id,
                    **meeting_data
                )
                
                results.append({
                    'success': True,
                    'meeting_id': meet_room.id,
                    'meet_url': meet_room.meet_url
                })
                
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e),
                    'meeting_data': meeting_data
                })
        
        return results


# Instancia del servicio para uso global
google_meet_service = GoogleMeetService()


# Funciones de conveniencia
def create_quick_meeting(
    organizer_id: int,
    title: str,
    start_time: datetime,
    participant_emails: List[str],
    duration_minutes: int = 60,
    auto_record: bool = False
) -> MeetRoom:
    """Crear reunión rápida"""
    
    participants = [
        {'email': email, 'role': 'attendee'} 
        for email in participant_emails
    ]
    
    config = MeetConfiguration(
        enable_recording=auto_record,
        auto_start_recording=auto_record,
        enable_transcription=True
    )
    
    return google_meet_service.create_meeting(
        organizer_id=organizer_id,
        title=title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        participants=participants,
        configuration=config
    )


def schedule_mentorship_session(
    mentorship_id: int,
    start_time: datetime,
    duration_minutes: int = 90,
    agenda: str = None
) -> MeetRoom:
    """Agendar sesión de mentoría"""
    
    return google_meet_service.create_mentorship_meeting(
        mentorship_id=mentorship_id,
        start_time=start_time,
        duration_minutes=duration_minutes,
        agenda=agenda,
        auto_record=True
    )


def get_upcoming_meetings(user_id: int, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Obtener próximas reuniones"""
    
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=days_ahead)
    
    return google_meet_service.get_user_meetings(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status_filter=[MeetingStatus.SCHEDULED.value],
        include_past=False
    )