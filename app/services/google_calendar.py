"""
Google Calendar Service - Ecosistema de Emprendimiento
Servicio completo de integración con Google Calendar API

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
import pytz

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.auth.exceptions

from flask import current_app, request, url_for, session
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
    CALENDAR_PROVIDERS
)
from app.models.user import User
from app.models.meeting import Meeting
from app.models.mentorship import Mentorship
from app.models.calendar_integration import CalendarIntegration
from app.models.calendar_sync import CalendarSync
from app.models.oauth_token import OAuthToken
from app.services.base import BaseService
from app.services.notification_service import NotificationService
from app.utils.decorators import log_activity, retry_on_failure, rate_limit
from app.utils.validators import validate_email, validate_datetime
from app.utils.formatters import format_datetime, format_duration
from app.utils.date_utils import (
    convert_timezone, 
    get_user_timezone,
    parse_datetime,
    is_business_hours
)
from app.utils.crypto_utils import encrypt_data, decrypt_data


logger = logging.getLogger(__name__)


class CalendarEventStatus(Enum):
    """Estados de eventos de calendario"""
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class CalendarVisibility(Enum):
    """Visibilidad de eventos"""
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class RecurrenceFrequency(Enum):
    """Frecuencia de recurrencia"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class AttendeeResponseStatus(Enum):
    """Estado de respuesta de asistentes"""
    NEEDS_ACTION = "needsAction"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"


@dataclass
class CalendarCredentials:
    """Credenciales de Google Calendar"""
    access_token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    expiry: Optional[datetime] = None


@dataclass
class CalendarEvent:
    """Evento de calendario"""
    id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: str = 'UTC'
    location: Optional[str] = None
    attendees: Optional[List[Dict[str, str]]] = None
    recurrence: Optional[List[str]] = None
    reminders: Optional[Dict[str, Any]] = None
    visibility: str = CalendarVisibility.DEFAULT.value
    status: str = CalendarEventStatus.CONFIRMED.value
    calendar_id: str = 'primary'
    meeting_url: Optional[str] = None
    creator_email: Optional[str] = None
    organizer_email: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CalendarBatch:
    """Lote de operaciones de calendario"""
    events_to_create: List[CalendarEvent]
    events_to_update: List[CalendarEvent]
    events_to_delete: List[str]
    calendar_id: str = 'primary'


@dataclass
class AvailabilitySlot:
    """Slot de disponibilidad"""
    start_time: datetime
    end_time: datetime
    is_available: bool
    event_id: Optional[str] = None
    event_summary: Optional[str] = None


@dataclass
class CalendarSyncResult:
    """Resultado de sincronización"""
    success: bool
    events_synced: int = 0
    events_created: int = 0
    events_updated: int = 0
    events_deleted: int = 0
    errors: List[str] = None
    last_sync_token: Optional[str] = None


class GoogleCalendarService(BaseService):
    """
    Servicio completo de integración con Google Calendar
    
    Funcionalidades:
    - OAuth 2.0 completo con refresh automático
    - CRUD de eventos con validación robusta
    - Sincronización bidireccional en tiempo real
    - Gestión de múltiples calendarios
    - Webhooks para cambios remotos
    - Búsqueda de disponibilidad inteligente
    - Manejo de recurrencias complejas
    - Gestión de zonas horarias
    - Rate limiting y manejo de cuotas
    - Fallback y recuperación de errores
    - Integration con ecosystem de emprendimiento
    """
    
    def __init__(self):
        super().__init__()
        self.notification_service = NotificationService()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._setup_oauth_config()
        self._setup_scopes()
    
    def _setup_oauth_config(self):
        """Configurar OAuth para Google Calendar"""
        self.client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        self.client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI')
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            logger.error("Configuración de Google OAuth incompleta")
    
    def _setup_scopes(self):
        """Configurar scopes necesarios"""
        self.scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
    
    def get_authorization_url(self, user_id: int, state: Optional[str] = None) -> str:
        """
        Obtener URL de autorización OAuth
        
        Args:
            user_id: ID del usuario
            state: Estado personalizado para seguridad
            
        Returns:
            str: URL de autorización
        """
        try:
            if not self.client_id:
                raise ExternalServiceError("Google OAuth no configurado")
            
            # Crear flow de OAuth
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            
            flow.redirect_uri = self.redirect_uri
            
            # Generar estado con información del usuario
            oauth_state = {
                'user_id': user_id,
                'custom_state': state,
                'timestamp': datetime.utcnow().timestamp()
            }
            
            encoded_state = base64.urlsafe_b64encode(
                json.dumps(oauth_state).encode()
            ).decode()
            
            # Generar URL de autorización
            authorization_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=encoded_state,
                prompt='consent'  # Forzar consent para obtener refresh token
            )
            
            logger.info(f"URL de autorización generada para usuario {user_id}")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error generando URL de autorización: {str(e)}")
            raise ExternalServiceError(f"Error en OAuth: {str(e)}")
    
    @log_activity("google_calendar_connected")
    def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """
        Manejar callback de OAuth
        
        Args:
            code: Código de autorización
            state: Estado de la solicitud
            
        Returns:
            Dict[str, Any]: Resultado de la conexión
        """
        try:
            # Decodificar estado
            oauth_state = json.loads(
                base64.urlsafe_b64decode(state.encode()).decode()
            )
            
            user_id = oauth_state['user_id']
            
            # Verificar que el usuario existe
            user = User.query.get(user_id)
            if not user:
                raise NotFoundError(f"Usuario {user_id} no encontrado")
            
            # Intercambiar código por tokens
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            
            flow.redirect_uri = self.redirect_uri
            flow.fetch_token(code=code)
            
            credentials = flow.credentials
            
            # Obtener información del usuario de Google
            user_info = self._get_google_user_info(credentials)
            
            # Almacenar credenciales
            self._store_credentials(user_id, credentials, user_info)
            
            # Crear webhook para sincronización
            self._setup_calendar_webhook(user_id, credentials)
            
            # Sincronización inicial
            sync_result = self._initial_sync(user_id, credentials)
            
            return {
                'success': True,
                'user_id': user_id,
                'google_email': user_info.get('email'),
                'sync_result': sync_result,
                'message': 'Google Calendar conectado exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error en callback OAuth: {str(e)}")
            raise AuthenticationError(f"Error conectando Google Calendar: {str(e)}")
    
    @rate_limit(max_requests=60, window=60)  # 60 requests per minute
    def create_event(
        self,
        user_id: int,
        event: CalendarEvent,
        send_notifications: bool = True
    ) -> CalendarEvent:
        """
        Crear evento en Google Calendar
        
        Args:
            user_id: ID del usuario
            event: Datos del evento
            send_notifications: Enviar notificaciones a asistentes
            
        Returns:
            CalendarEvent: Evento creado con ID de Google
        """
        try:
            # Obtener credenciales del usuario
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            # Validar evento
            self._validate_event(event)
            
            # Construir servicio de Calendar
            service = self._build_calendar_service(credentials)
            
            # Preparar evento para Google Calendar API
            google_event = self._prepare_google_event(event)
            
            # Crear evento
            created_event = service.events().insert(
                calendarId=event.calendar_id,
                body=google_event,
                sendNotifications=send_notifications
            ).execute()
            
            # Actualizar evento con información de Google
            event.id = created_event['id']
            event.creator_email = created_event.get('creator', {}).get('email')
            event.organizer_email = created_event.get('organizer', {}).get('email')
            
            # Registrar en base de datos local
            self._store_event_locally(user_id, event, created_event)
            
            # Enviar notificaciones internas
            if send_notifications:
                self._send_event_notifications(user_id, event, 'created')
            
            logger.info(f"Evento creado en Google Calendar: {event.id}")
            return event
            
        except HttpError as e:
            error_content = json.loads(e.content.decode())
            logger.error(f"Error de Google Calendar API: {error_content}")
            raise ExternalServiceError(f"Error de Google Calendar: {error_content.get('error', {}).get('message', str(e))}")
        except Exception as e:
            logger.error(f"Error creando evento: {str(e)}")
            raise BusinessLogicError(f"Error creando evento: {str(e)}")
    
    @rate_limit(max_requests=60, window=60)
    def update_event(
        self,
        user_id: int,
        event_id: str,
        event_updates: CalendarEvent,
        send_notifications: bool = True
    ) -> CalendarEvent:
        """
        Actualizar evento en Google Calendar
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento en Google
            event_updates: Datos actualizados
            send_notifications: Enviar notificaciones
            
        Returns:
            CalendarEvent: Evento actualizado
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            # Obtener evento actual
            current_event = service.events().get(
                calendarId=event_updates.calendar_id,
                eventId=event_id
            ).execute()
            
            # Preparar actualizaciones
            google_event_updates = self._prepare_google_event_updates(
                current_event, 
                event_updates
            )
            
            # Actualizar evento
            updated_event = service.events().update(
                calendarId=event_updates.calendar_id,
                eventId=event_id,
                body=google_event_updates,
                sendNotifications=send_notifications
            ).execute()
            
            # Convertir respuesta a CalendarEvent
            updated_calendar_event = self._convert_google_to_calendar_event(updated_event)
            
            # Actualizar en base de datos local
            self._update_event_locally(user_id, updated_calendar_event)
            
            # Enviar notificaciones
            if send_notifications:
                self._send_event_notifications(user_id, updated_calendar_event, 'updated')
            
            return updated_calendar_event
            
        except HttpError as e:
            logger.error(f"Error actualizando evento en Google: {str(e)}")
            raise ExternalServiceError(f"Error actualizando evento: {str(e)}")
    
    @rate_limit(max_requests=60, window=60)
    def delete_event(
        self,
        user_id: int,
        event_id: str,
        calendar_id: str = 'primary',
        send_notifications: bool = True
    ) -> bool:
        """
        Eliminar evento de Google Calendar
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento
            calendar_id: ID del calendario
            send_notifications: Enviar notificaciones
            
        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            # Obtener evento antes de eliminarlo para notificaciones
            try:
                event_data = service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                
                event = self._convert_google_to_calendar_event(event_data)
            except HttpError:
                event = None
            
            # Eliminar evento
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendNotifications=send_notifications
            ).execute()
            
            # Eliminar de base de datos local
            self._delete_event_locally(user_id, event_id)
            
            # Enviar notificaciones
            if send_notifications and event:
                self._send_event_notifications(user_id, event, 'deleted')
            
            logger.info(f"Evento eliminado: {event_id}")
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                # Evento ya no existe, considerarlo como eliminado exitosamente
                self._delete_event_locally(user_id, event_id)
                return True
            
            logger.error(f"Error eliminando evento: {str(e)}")
            raise ExternalServiceError(f"Error eliminando evento: {str(e)}")
    
    def get_events(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        calendar_id: str = 'primary',
        max_results: int = 250
    ) -> List[CalendarEvent]:
        """
        Obtener eventos de Google Calendar
        
        Args:
            user_id: ID del usuario
            start_date: Fecha de inicio
            end_date: Fecha de fin
            calendar_id: ID del calendario
            max_results: Máximo número de resultados
            
        Returns:
            List[CalendarEvent]: Lista de eventos
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            # Convertir fechas a formato RFC3339
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            # Obtener eventos
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Convertir a CalendarEvent objects
            calendar_events = []
            for event in events:
                calendar_event = self._convert_google_to_calendar_event(event)
                calendar_events.append(calendar_event)
            
            logger.info(f"Obtenidos {len(calendar_events)} eventos para usuario {user_id}")
            return calendar_events
            
        except HttpError as e:
            logger.error(f"Error obteniendo eventos: {str(e)}")
            raise ExternalServiceError(f"Error obteniendo eventos: {str(e)}")
    
    def check_availability(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        calendars: Optional[List[str]] = None
    ) -> List[AvailabilitySlot]:
        """
        Verificar disponibilidad en calendarios
        
        Args:
            user_id: ID del usuario
            start_time: Hora de inicio a verificar
            end_time: Hora de fin a verificar
            calendars: IDs de calendarios a verificar
            
        Returns:
            List[AvailabilitySlot]: Slots de disponibilidad
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            if not calendars:
                calendars = ['primary']
            
            # Usar FreeBusy API para verificar disponibilidad
            body = {
                'timeMin': start_time.isoformat() + 'Z',
                'timeMax': end_time.isoformat() + 'Z',
                'items': [{'id': cal_id} for cal_id in calendars]
            }
            
            freebusy_result = service.freebusy().query(body=body).execute()
            
            # Procesar resultados
            availability_slots = []
            
            for calendar_id in calendars:
                calendar_data = freebusy_result['calendars'].get(calendar_id, {})
                busy_times = calendar_data.get('busy', [])
                
                # Crear slots de disponibilidad
                current_time = start_time
                
                for busy_period in busy_times:
                    busy_start = parse_datetime(busy_period['start'])
                    busy_end = parse_datetime(busy_period['end'])
                    
                    # Slot disponible antes del período ocupado
                    if current_time < busy_start:
                        availability_slots.append(AvailabilitySlot(
                            start_time=current_time,
                            end_time=busy_start,
                            is_available=True
                        ))
                    
                    # Slot ocupado
                    availability_slots.append(AvailabilitySlot(
                        start_time=busy_start,
                        end_time=busy_end,
                        is_available=False
                    ))
                    
                    current_time = busy_end
                
                # Slot disponible después del último período ocupado
                if current_time < end_time:
                    availability_slots.append(AvailabilitySlot(
                        start_time=current_time,
                        end_time=end_time,
                        is_available=True
                    ))
            
            return availability_slots
            
        except HttpError as e:
            logger.error(f"Error verificando disponibilidad: {str(e)}")
            raise ExternalServiceError(f"Error verificando disponibilidad: {str(e)}")
    
    def find_available_slots(
        self,
        user_ids: List[int],
        duration_minutes: int,
        preferred_start: datetime,
        preferred_end: datetime,
        max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Encontrar slots disponibles para múltiples usuarios
        
        Args:
            user_ids: IDs de usuarios participantes
            duration_minutes: Duración requerida en minutos
            preferred_start: Hora preferida de inicio
            preferred_end: Hora preferida de fin
            max_suggestions: Máximo número de sugerencias
            
        Returns:
            List[Dict[str, Any]]: Slots disponibles sugeridos
        """
        try:
            suggestions = []
            duration = timedelta(minutes=duration_minutes)
            
            # Obtener disponibilidad de todos los usuarios
            all_availability = {}
            for user_id in user_ids:
                try:
                    availability = self.check_availability(
                        user_id, preferred_start, preferred_end
                    )
                    all_availability[user_id] = availability
                except Exception as e:
                    logger.warning(f"No se pudo obtener disponibilidad de usuario {user_id}: {str(e)}")
                    # Asumir no disponible si hay error
                    all_availability[user_id] = [
                        AvailabilitySlot(
                            start_time=preferred_start,
                            end_time=preferred_end,
                            is_available=False
                        )
                    ]
            
            # Encontrar intersecciones de disponibilidad
            current_time = preferred_start
            slot_increment = timedelta(minutes=30)  # Verificar cada 30 minutos
            
            while current_time + duration <= preferred_end and len(suggestions) < max_suggestions:
                slot_end = current_time + duration
                
                # Verificar si todos los usuarios están disponibles
                all_available = True
                
                for user_id in user_ids:
                    user_available = False
                    
                    for slot in all_availability[user_id]:
                        if (slot.is_available and 
                            slot.start_time <= current_time and 
                            slot.end_time >= slot_end):
                            user_available = True
                            break
                    
                    if not user_available:
                        all_available = False
                        break
                
                if all_available:
                    # Verificar horario de trabajo
                    if self._is_business_hours(current_time, slot_end):
                        suggestions.append({
                            'start_time': current_time,
                            'end_time': slot_end,
                            'duration_minutes': duration_minutes,
                            'available_users': user_ids,
                            'confidence_score': self._calculate_confidence_score(
                                current_time, preferred_start, preferred_end
                            )
                        })
                
                current_time += slot_increment
            
            # Ordenar por score de confianza
            suggestions.sort(key=lambda x: x['confidence_score'], reverse=True)
            
            return suggestions[:max_suggestions]
            
        except Exception as e:
            logger.error(f"Error encontrando slots disponibles: {str(e)}")
            raise BusinessLogicError(f"Error buscando disponibilidad: {str(e)}")
    
    @retry_on_failure(max_retries=3, delay=60)
    def sync_calendars(self, user_id: int) -> CalendarSyncResult:
        """
        Sincronizar calendarios del usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            CalendarSyncResult: Resultado de la sincronización
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            # Obtener último token de sincronización
            last_sync = CalendarSync.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            sync_token = last_sync.sync_token if last_sync else None
            
            # Obtener cambios desde la última sincronización
            events_result = service.events().list(
                calendarId='primary',
                syncToken=sync_token,
                showDeleted=True
            ).execute() if sync_token else service.events().list(
                calendarId='primary',
                timeMin=datetime.utcnow().isoformat() + 'Z',
                maxResults=1000,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            new_sync_token = events_result.get('nextSyncToken')
            
            # Procesar cambios
            events_created = 0
            events_updated = 0
            events_deleted = 0
            errors = []
            
            for event in events:
                try:
                    if event.get('status') == 'cancelled':
                        self._delete_event_locally(user_id, event['id'])
                        events_deleted += 1
                    else:
                        calendar_event = self._convert_google_to_calendar_event(event)
                        
                        # Verificar si existe localmente
                        local_event = self._get_local_event(user_id, event['id'])
                        
                        if local_event:
                            self._update_event_locally(user_id, calendar_event)
                            events_updated += 1
                        else:
                            self._store_event_locally(user_id, calendar_event, event)
                            events_created += 1
                            
                except Exception as e:
                    errors.append(f"Error procesando evento {event.get('id', 'unknown')}: {str(e)}")
            
            # Actualizar token de sincronización
            if new_sync_token:
                self._update_sync_token(user_id, new_sync_token)
            
            result = CalendarSyncResult(
                success=True,
                events_synced=len(events),
                events_created=events_created,
                events_updated=events_updated,
                events_deleted=events_deleted,
                errors=errors,
                last_sync_token=new_sync_token
            )
            
            logger.info(f"Sincronización completada para usuario {user_id}: {result}")
            return result
            
        except HttpError as e:
            if 'Sync token is no longer valid' in str(e):
                # Token inválido, hacer sincronización completa
                logger.warning(f"Sync token inválido para usuario {user_id}, haciendo sync completo")
                self._reset_sync_token(user_id)
                return self.sync_calendars(user_id)
            
            logger.error(f"Error en sincronización: {str(e)}")
            return CalendarSyncResult(
                success=False,
                errors=[str(e)]
            )
    
    def schedule_mentorship_session(
        self,
        mentorship_id: int,
        start_time: datetime,
        duration_minutes: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> CalendarEvent:
        """
        Agendar sesión de mentoría en Google Calendar
        
        Args:
            mentorship_id: ID de la mentoría
            start_time: Hora de inicio
            duration_minutes: Duración en minutos
            title: Título personalizado
            description: Descripción personalizada
            location: Ubicación (física o virtual)
            
        Returns:
            CalendarEvent: Evento creado
        """
        try:
            # Obtener datos de mentoría
            mentorship = Mentorship.query.get(mentorship_id)
            if not mentorship:
                raise NotFoundError(f"Mentoría {mentorship_id} no encontrada")
            
            entrepreneur = mentorship.entrepreneur
            ally = mentorship.ally
            
            # Preparar evento
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            event = CalendarEvent(
                summary=title or f"Mentoría: {entrepreneur.user.full_name} - {ally.user.full_name}",
                description=description or self._generate_mentorship_description(mentorship),
                start_time=start_time,
                end_time=end_time,
                location=location,
                attendees=[
                    {'email': entrepreneur.user.email, 'responseStatus': 'accepted'},
                    {'email': ally.user.email, 'responseStatus': 'accepted'}
                ],
                reminders={
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 1440},  # 24 horas antes
                        {'method': 'popup', 'minutes': 30}     # 30 minutos antes
                    ]
                },
                metadata={
                    'mentorship_id': mentorship_id,
                    'event_type': 'mentorship_session',
                    'entrepreneur_id': entrepreneur.id,
                    'ally_id': ally.id
                }
            )
            
            # Crear evento en calendario del mentor
            created_event = self.create_event(ally.user_id, event)
            
            # Registrar en base de datos local
            meeting = Meeting(
                mentorship_id=mentorship_id,
                title=created_event.summary,
                description=created_event.description,
                start_time=created_event.start_time,
                end_time=created_event.end_time,
                location=created_event.location,
                google_event_id=created_event.id,
                status='scheduled',
                created_by_id=ally.user_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(meeting)
            db.session.commit()
            
            # Enviar notificaciones
            self._send_mentorship_session_notifications(mentorship, meeting)
            
            return created_event
            
        except Exception as e:
            logger.error(f"Error agendando sesión de mentoría: {str(e)}")
            raise BusinessLogicError(f"Error agendando sesión: {str(e)}")
    
    def setup_webhook(self, user_id: int) -> Dict[str, Any]:
        """
        Configurar webhook para cambios de calendario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Dict[str, Any]: Información del webhook
        """
        try:
            credentials = self._get_user_credentials(user_id)
            if not credentials:
                raise AuthenticationError("Usuario no tiene Google Calendar conectado")
            
            service = self._build_calendar_service(credentials)
            
            # Configurar webhook
            webhook_url = url_for(
                'api.google_calendar_webhook',
                user_id=user_id,
                _external=True
            )
            
            channel_id = f"calendar_sync_{user_id}_{datetime.utcnow().timestamp()}"
            
            watch_request = {
                'id': channel_id,
                'type': 'web_hook',
                'address': webhook_url,
                'expiration': int((datetime.utcnow() + timedelta(days=7)).timestamp() * 1000)
            }
            
            watch_response = service.events().watch(
                calendarId='primary',
                body=watch_request
            ).execute()
            
            # Almacenar información del webhook
            self._store_webhook_info(user_id, watch_response)
            
            return {
                'channel_id': channel_id,
                'resource_id': watch_response.get('resourceId'),
                'expiration': watch_response.get('expiration'),
                'webhook_url': webhook_url
            }
            
        except HttpError as e:
            logger.error(f"Error configurando webhook: {str(e)}")
            raise ExternalServiceError(f"Error configurando webhook: {str(e)}")
    
    def handle_webhook_notification(
        self,
        user_id: int,
        channel_id: str,
        resource_id: str,
        resource_state: str
    ) -> bool:
        """
        Manejar notificación de webhook
        
        Args:
            user_id: ID del usuario
            channel_id: ID del canal
            resource_id: ID del recurso
            resource_state: Estado del recurso
            
        Returns:
            bool: True si se procesó correctamente
        """
        try:
            if resource_state in ['exists', 'not_exists']:
                # Trigger sincronización asíncrona
                self._queue_calendar_sync(user_id)
                
                logger.info(f"Webhook procesado para usuario {user_id}: {resource_state}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error procesando webhook: {str(e)}")
            return False
    
    def disconnect_calendar(self, user_id: int) -> bool:
        """
        Desconectar Google Calendar del usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            bool: True si se desconectó correctamente
        """
        try:
            # Revocar tokens
            credentials = self._get_user_credentials(user_id)
            if credentials:
                try:
                    credentials.revoke(Request())
                except Exception as e:
                    logger.warning(f"Error revocando credenciales: {str(e)}")
            
            # Eliminar datos locales
            CalendarIntegration.query.filter_by(
                user_id=user_id,
                provider='google'
            ).delete()
            
            CalendarSync.query.filter_by(
                user_id=user_id,
                provider='google'
            ).delete()
            
            OAuthToken.query.filter_by(
                user_id=user_id,
                provider='google'
            ).delete()
            
            db.session.commit()
            
            # Limpiar cache
            cache.delete(f"google_credentials:{user_id}")
            
            logger.info(f"Google Calendar desconectado para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error desconectando calendar: {str(e)}")
            return False
    
    # Métodos privados
    def _get_user_credentials(self, user_id: int) -> Optional[Credentials]:
        """Obtener credenciales del usuario"""
        # Intentar desde cache primero
        cache_key = f"google_credentials:{user_id}"
        cached_creds = cache.get(cache_key)
        
        if cached_creds:
            return Credentials.from_authorized_user_info(cached_creds)
        
        # Obtener desde base de datos
        token = OAuthToken.query.filter_by(
            user_id=user_id,
            provider='google',
            is_active=True
        ).first()
        
        if not token:
            return None
        
        try:
            # Desencriptar token
            decrypted_data = decrypt_data(token.encrypted_token)
            creds_data = json.loads(decrypted_data)
            
            credentials = Credentials.from_authorized_user_info(creds_data)
            
            # Verificar si necesita refresh
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
                # Actualizar token en base de datos
                updated_creds_data = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
                
                token.encrypted_token = encrypt_data(json.dumps(updated_creds_data))
                token.expires_at = credentials.expiry
                db.session.commit()
            
            # Cachear credenciales
            cache.set(cache_key, creds_data, timeout=1800)  # 30 minutos
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error obteniendo credenciales para usuario {user_id}: {str(e)}")
            return None
    
    def _build_calendar_service(self, credentials: Credentials):
        """Construir servicio de Google Calendar"""
        return build('calendar', 'v3', credentials=credentials)
    
    def _prepare_google_event(self, event: CalendarEvent) -> Dict[str, Any]:
        """Preparar evento para Google Calendar API"""
        google_event = {
            'summary': event.summary,
            'description': event.description,
            'start': {
                'dateTime': event.start_time.isoformat(),
                'timeZone': event.timezone
            },
            'end': {
                'dateTime': event.end_time.isoformat(),
                'timeZone': event.timezone
            },
            'visibility': event.visibility,
            'status': event.status
        }
        
        if event.location:
            google_event['location'] = event.location
        
        if event.attendees:
            google_event['attendees'] = event.attendees
        
        if event.recurrence:
            google_event['recurrence'] = event.recurrence
        
        if event.reminders:
            google_event['reminders'] = event.reminders
        
        # Agregar metadata como extended properties
        if event.metadata:
            google_event['extendedProperties'] = {
                'private': event.metadata
            }
        
        return google_event
    
    def _convert_google_to_calendar_event(self, google_event: Dict[str, Any]) -> CalendarEvent:
        """Convertir evento de Google a CalendarEvent"""
        start = google_event.get('start', {})
        end = google_event.get('end', {})
        
        # Manejar diferentes formatos de fecha/hora
        start_time = self._parse_google_datetime(start)
        end_time = self._parse_google_datetime(end)
        
        attendees = google_event.get('attendees', [])
        
        # Extraer metadata de extended properties
        extended_props = google_event.get('extendedProperties', {})
        metadata = extended_props.get('private', {})
        
        return CalendarEvent(
            id=google_event.get('id'),
            summary=google_event.get('summary'),
            description=google_event.get('description'),
            start_time=start_time,
            end_time=end_time,
            timezone=start.get('timeZone', 'UTC'),
            location=google_event.get('location'),
            attendees=attendees,
            recurrence=google_event.get('recurrence'),
            visibility=google_event.get('visibility', 'default'),
            status=google_event.get('status', 'confirmed'),
            creator_email=google_event.get('creator', {}).get('email'),
            organizer_email=google_event.get('organizer', {}).get('email'),
            metadata=metadata
        )
    
    def _parse_google_datetime(self, datetime_obj: Dict[str, Any]) -> datetime:
        """Parsear fecha/hora de Google Calendar"""
        if 'dateTime' in datetime_obj:
            return parse_datetime(datetime_obj['dateTime'])
        elif 'date' in datetime_obj:
            # Evento de todo el día
            date_str = datetime_obj['date']
            return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
        else:
            return datetime.utcnow()
    
    def _validate_event(self, event: CalendarEvent):
        """Validar datos del evento"""
        if not event.summary:
            raise ValidationError("El evento debe tener un título")
        
        if not event.start_time or not event.end_time:
            raise ValidationError("El evento debe tener fecha y hora de inicio y fin")
        
        if event.start_time >= event.end_time:
            raise ValidationError("La hora de inicio debe ser anterior a la hora de fin")
        
        # Validar duración máxima (ej: 8 horas)
        max_duration = timedelta(hours=8)
        if event.end_time - event.start_time > max_duration:
            raise ValidationError("La duración del evento no puede exceder 8 horas")
        
        # Validar emails de asistentes
        if event.attendees:
            for attendee in event.attendees:
                email = attendee.get('email')
                if email and not validate_email(email):
                    raise ValidationError(f"Email de asistente inválido: {email}")
    
    def _store_credentials(
        self,
        user_id: int,
        credentials: Credentials,
        user_info: Dict[str, Any]
    ):
        """Almacenar credenciales en base de datos"""
        try:
            # Preparar datos de credenciales
            creds_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Encriptar y almacenar
            encrypted_token = encrypt_data(json.dumps(creds_data))
            
            # Buscar token existente
            existing_token = OAuthToken.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if existing_token:
                existing_token.encrypted_token = encrypted_token
                existing_token.expires_at = credentials.expiry
                existing_token.updated_at = datetime.utcnow()
                existing_token.is_active = True
            else:
                new_token = OAuthToken(
                    user_id=user_id,
                    provider='google',
                    encrypted_token=encrypted_token,
                    expires_at=credentials.expiry,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(new_token)
            
            # Crear/actualizar integración de calendario
            integration = CalendarIntegration.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if integration:
                integration.is_active = True
                integration.google_email = user_info.get('email')
                integration.updated_at = datetime.utcnow()
            else:
                integration = CalendarIntegration(
                    user_id=user_id,
                    provider='google',
                    google_email=user_info.get('email'),
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(integration)
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error almacenando credenciales: {str(e)}")
            raise
    
    def _get_google_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Obtener información del usuario de Google"""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            logger.error(f"Error obteniendo info de usuario: {str(e)}")
            return {}
    
    def _is_business_hours(self, start_time: datetime, end_time: datetime) -> bool:
        """Verificar si está en horario de trabajo"""
        # Horario de trabajo: 8 AM - 6 PM, Lunes a Viernes
        for dt in [start_time, end_time]:
            if dt.weekday() >= 5:  # Sábado o Domingo
                return False
            
            hour = dt.hour
            if hour < 8 or hour >= 18:
                return False
        
        return True
    
    def _calculate_confidence_score(
        self,
        suggested_time: datetime,
        preferred_start: datetime,
        preferred_end: datetime
    ) -> float:
        """Calcular score de confianza para sugerencia"""
        # Score base
        score = 1.0
        
        # Penalizar si está fuera del rango preferido
        if suggested_time < preferred_start or suggested_time > preferred_end:
            score *= 0.5
        
        # Bonificar horarios de trabajo
        if self._is_business_hours(suggested_time, suggested_time + timedelta(hours=1)):
            score *= 1.2
        
        # Penalizar horarios muy temprano o muy tarde
        hour = suggested_time.hour
        if hour < 9 or hour > 17:
            score *= 0.8
        
        return min(score, 1.0)
    
    def _send_event_notifications(
        self,
        user_id: int,
        event: CalendarEvent,
        action: str
    ):
        """Enviar notificaciones de eventos"""
        try:
            # Notificar a asistentes si es apropiado
            if event.attendees and action in ['created', 'updated']:
                for attendee in event.attendees:
                    attendee_email = attendee.get('email')
                    if attendee_email:
                        self.notification_service.send_notification(
                            user_id=user_id,  # Podríamos buscar el user_id por email
                            type=f'calendar_event_{action}',
                            title=f'Evento {action}: {event.summary}',
                            message=f'Evento "{event.summary}" programado para {format_datetime(event.start_time)}',
                            data={
                                'event_id': event.id,
                                'start_time': event.start_time.isoformat(),
                                'action': action
                            }
                        )
        except Exception as e:
            logger.error(f"Error enviando notificaciones de evento: {str(e)}")
    
    def _setup_calendar_webhook(self, user_id: int, credentials: Credentials):
        """Configurar webhook inicial para sincronización"""
        try:
            webhook_info = self.setup_webhook(user_id)
            logger.info(f"Webhook configurado para usuario {user_id}: {webhook_info.get('channel_id')}")
        except Exception as e:
            logger.warning(f"No se pudo configurar webhook para usuario {user_id}: {str(e)}")
    
    def _initial_sync(self, user_id: int, credentials: Credentials) -> CalendarSyncResult:
        """Realizar sincronización inicial después de conectar"""
        try:
            return self.sync_calendars(user_id)
        except Exception as e:
            logger.error(f"Error en sincronización inicial: {str(e)}")
            return CalendarSyncResult(
                success=False,
                errors=[str(e)]
            )
    
    def _store_event_locally(self, user_id: int, event: CalendarEvent, google_event: Dict[str, Any]):
        """Almacenar evento en base de datos local"""
        try:
            # Verificar si ya existe
            existing = Meeting.query.filter_by(
                google_event_id=event.id
            ).first()
            
            if existing:
                return  # Ya existe, no duplicar
            
            # Crear nuevo registro
            meeting = Meeting(
                title=event.summary,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                location=event.location,
                google_event_id=event.id,
                google_calendar_id=event.calendar_id,
                status='scheduled',
                attendees=json.dumps(event.attendees) if event.attendees else None,
                metadata=json.dumps(event.metadata) if event.metadata else None,
                created_at=datetime.utcnow(),
                synced_from_google=True
            )
            
            # Intentar asociar con mentoría si es posible
            if event.metadata and event.metadata.get('mentorship_id'):
                meeting.mentorship_id = event.metadata['mentorship_id']
            
            db.session.add(meeting)
            db.session.commit()
            
            logger.debug(f"Evento almacenado localmente: {event.id}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error almacenando evento localmente: {str(e)}")
    
    def _prepare_google_event_updates(
        self, 
        current_event: Dict[str, Any], 
        updates: CalendarEvent
    ) -> Dict[str, Any]:
        """Preparar actualizaciones para evento existente"""
        # Empezar con el evento actual
        updated_event = current_event.copy()
        
        # Aplicar actualizaciones
        if updates.summary is not None:
            updated_event['summary'] = updates.summary
        
        if updates.description is not None:
            updated_event['description'] = updates.description
        
        if updates.start_time is not None:
            updated_event['start'] = {
                'dateTime': updates.start_time.isoformat(),
                'timeZone': updates.timezone
            }
        
        if updates.end_time is not None:
            updated_event['end'] = {
                'dateTime': updates.end_time.isoformat(),
                'timeZone': updates.timezone
            }
        
        if updates.location is not None:
            updated_event['location'] = updates.location
        
        if updates.attendees is not None:
            updated_event['attendees'] = updates.attendees
        
        if updates.recurrence is not None:
            updated_event['recurrence'] = updates.recurrence
        
        if updates.reminders is not None:
            updated_event['reminders'] = updates.reminders
        
        if updates.visibility is not None:
            updated_event['visibility'] = updates.visibility
        
        if updates.status is not None:
            updated_event['status'] = updates.status
        
        # Actualizar metadata
        if updates.metadata:
            extended_props = updated_event.get('extendedProperties', {})
            private_props = extended_props.get('private', {})
            private_props.update(updates.metadata)
            
            updated_event['extendedProperties'] = {
                'private': private_props
            }
        
        return updated_event
    
    def _update_event_locally(self, user_id: int, event: CalendarEvent):
        """Actualizar evento en base de datos local"""
        try:
            meeting = Meeting.query.filter_by(
                google_event_id=event.id
            ).first()
            
            if meeting:
                meeting.title = event.summary
                meeting.description = event.description
                meeting.start_time = event.start_time
                meeting.end_time = event.end_time
                meeting.location = event.location
                meeting.attendees = json.dumps(event.attendees) if event.attendees else None
                meeting.metadata = json.dumps(event.metadata) if event.metadata else None
                meeting.updated_at = datetime.utcnow()
                
                db.session.commit()
                logger.debug(f"Evento actualizado localmente: {event.id}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando evento localmente: {str(e)}")
    
    def _delete_event_locally(self, user_id: int, event_id: str):
        """Eliminar evento de base de datos local"""
        try:
            meeting = Meeting.query.filter_by(
                google_event_id=event_id
            ).first()
            
            if meeting:
                meeting.status = 'cancelled'
                meeting.updated_at = datetime.utcnow()
                # No eliminar físicamente, solo marcar como cancelado
                db.session.commit()
                logger.debug(f"Evento marcado como cancelado localmente: {event_id}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error eliminando evento localmente: {str(e)}")
    
    def _get_local_event(self, user_id: int, event_id: str) -> Optional[Meeting]:
        """Obtener evento desde base de datos local"""
        try:
            return Meeting.query.filter_by(
                google_event_id=event_id
            ).first()
        except Exception as e:
            logger.error(f"Error obteniendo evento local: {str(e)}")
            return None
    
    def _update_sync_token(self, user_id: int, sync_token: str):
        """Actualizar token de sincronización"""
        try:
            calendar_sync = CalendarSync.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if calendar_sync:
                calendar_sync.sync_token = sync_token
                calendar_sync.last_sync_at = datetime.utcnow()
            else:
                calendar_sync = CalendarSync(
                    user_id=user_id,
                    provider='google',
                    sync_token=sync_token,
                    last_sync_at=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                db.session.add(calendar_sync)
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando sync token: {str(e)}")
    
    def _reset_sync_token(self, user_id: int):
        """Resetear token de sincronización"""
        try:
            CalendarSync.query.filter_by(
                user_id=user_id,
                provider='google'
            ).delete()
            
            db.session.commit()
            logger.info(f"Sync token reseteado para usuario {user_id}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error reseteando sync token: {str(e)}")
    
    def _generate_mentorship_description(self, mentorship: Mentorship) -> str:
        """Generar descripción para sesión de mentoría"""
        description_parts = [
            f"Sesión de mentoría entre {mentorship.entrepreneur.user.full_name} y {mentorship.ally.user.full_name}",
            "",
            f"Emprendedor: {mentorship.entrepreneur.user.full_name}",
            f"Email: {mentorship.entrepreneur.user.email}",
            "",
            f"Mentor: {mentorship.ally.user.full_name}",
            f"Email: {mentorship.ally.user.email}",
            f"Especialidad: {mentorship.ally.expertise or 'No especificada'}",
            "",
            f"Proyecto: {mentorship.project.title if mentorship.project else 'No especificado'}",
            "",
            "Esta reunión ha sido generada automáticamente por el Sistema de Emprendimiento.",
            "",
            "Para más información, accede a la plataforma: " + url_for('main.index', _external=True)
        ]
        
        return "\n".join(description_parts)
    
    def _send_mentorship_session_notifications(self, mentorship: Mentorship, meeting: Meeting):
        """Enviar notificaciones para sesión de mentoría"""
        try:
            # Notificar al emprendedor
            self.notification_service.send_notification(
                user_id=mentorship.entrepreneur.user_id,
                type='mentorship_session_scheduled',
                title='Sesión de mentoría agendada',
                message=f'Tu sesión de mentoría con {mentorship.ally.user.full_name} ha sido agendada para {format_datetime(meeting.start_time)}',
                data={
                    'meeting_id': meeting.id,
                    'mentorship_id': mentorship.id,
                    'start_time': meeting.start_time.isoformat(),
                    'google_event_id': meeting.google_event_id
                }
            )
            
            # Notificar al mentor
            self.notification_service.send_notification(
                user_id=mentorship.ally.user_id,
                type='mentorship_session_scheduled',
                title='Sesión de mentoría agendada',
                message=f'Tu sesión de mentoría con {mentorship.entrepreneur.user.full_name} ha sido agendada para {format_datetime(meeting.start_time)}',
                data={
                    'meeting_id': meeting.id,
                    'mentorship_id': mentorship.id,
                    'start_time': meeting.start_time.isoformat(),
                    'google_event_id': meeting.google_event_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificaciones de mentoría: {str(e)}")
    
    def _store_webhook_info(self, user_id: int, watch_response: Dict[str, Any]):
        """Almacenar información del webhook"""
        try:
            # Buscar integración existente
            integration = CalendarIntegration.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if integration:
                integration.webhook_channel_id = watch_response.get('id')
                integration.webhook_resource_id = watch_response.get('resourceId')
                integration.webhook_expiration = datetime.fromtimestamp(
                    int(watch_response.get('expiration', 0)) / 1000
                ) if watch_response.get('expiration') else None
                integration.updated_at = datetime.utcnow()
                
                db.session.commit()
                
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error almacenando info de webhook: {str(e)}")
    
    def _queue_calendar_sync(self, user_id: int):
        """Encolar sincronización de calendario"""
        try:
            from app.tasks.calendar_tasks import sync_user_calendar
            
            # Encolar tarea de sincronización con delay de 30 segundos
            # para evitar múltiples sincronizaciones simultáneas
            sync_user_calendar.apply_async(
                args=[user_id],
                countdown=30,
                task_id=f"calendar_sync_{user_id}_{datetime.utcnow().timestamp()}"
            )
            
            logger.info(f"Sincronización encolada para usuario {user_id}")
            
        except Exception as e:
            logger.error(f"Error encolando sincronización: {str(e)}")
            # Fallback: sincronización síncrona
            try:
                self.sync_calendars(user_id)
            except Exception as sync_error:
                logger.error(f"Error en fallback sync: {str(sync_error)}")
    
    def get_calendar_status(self, user_id: int) -> Dict[str, Any]:
        """Obtener estado de la integración de calendario"""
        try:
            integration = CalendarIntegration.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if not integration:
                return {
                    'connected': False,
                    'status': 'not_connected'
                }
            
            # Verificar estado de credenciales
            credentials = self._get_user_credentials(user_id)
            
            if not credentials:
                return {
                    'connected': False,
                    'status': 'credentials_expired',
                    'google_email': integration.google_email
                }
            
            # Verificar webhook
            webhook_active = bool(
                integration.webhook_channel_id and 
                integration.webhook_expiration and
                integration.webhook_expiration > datetime.utcnow()
            )
            
            # Obtener información de última sincronización
            last_sync = CalendarSync.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            return {
                'connected': True,
                'status': 'active',
                'google_email': integration.google_email,
                'webhook_active': webhook_active,
                'webhook_expires_at': integration.webhook_expiration,
                'last_sync_at': last_sync.last_sync_at if last_sync else None,
                'created_at': integration.created_at
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de calendario: {str(e)}")
            return {
                'connected': False,
                'status': 'error',
                'error': str(e)
            }
    
    def renew_webhook(self, user_id: int) -> bool:
        """Renovar webhook que está por expirar"""
        try:
            integration = CalendarIntegration.query.filter_by(
                user_id=user_id,
                provider='google'
            ).first()
            
            if not integration or not integration.webhook_channel_id:
                return False
            
            # Verificar si necesita renovación (menos de 24 horas)
            if (integration.webhook_expiration and 
                integration.webhook_expiration > datetime.utcnow() + timedelta(hours=24)):
                return True  # No necesita renovación aún
            
            # Configurar nuevo webhook
            webhook_info = self.setup_webhook(user_id)
            
            logger.info(f"Webhook renovado para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error renovando webhook: {str(e)}")
            return False
    
    def bulk_sync_calendars(self, user_ids: List[int]) -> Dict[str, Any]:
        """Sincronizar múltiples calendarios en lote"""
        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for user_id in user_ids:
            try:
                sync_result = self.sync_calendars(user_id)
                if sync_result.success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].extend(sync_result.errors or [])
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Usuario {user_id}: {str(e)}")
        
        return results


# Instancia del servicio para uso global
google_calendar_service = GoogleCalendarService()


# Funciones de conveniencia
def schedule_meeting(
    organizer_id: int,
    attendee_emails: List[str],
    title: str,
    start_time: datetime,
    duration_minutes: int,
    description: str = None,
    location: str = None
) -> CalendarEvent:
    """Agendar reunión rápidamente"""
    
    attendees = [{'email': email} for email in attendee_emails]
    
    event = CalendarEvent(
        summary=title,
        description=description,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=duration_minutes),
        location=location,
        attendees=attendees,
        reminders={
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 30},
                {'method': 'popup', 'minutes': 10}
            ]
        }
    )
    
    return google_calendar_service.create_event(organizer_id, event)


def find_meeting_time(
    participant_ids: List[int],
    duration_minutes: int,
    preferred_date: datetime,
    max_suggestions: int = 3
) -> List[Dict[str, Any]]:
    """Encontrar horario para reunión"""
    
    start_of_day = preferred_date.replace(hour=8, minute=0, second=0, microsecond=0)
    end_of_day = preferred_date.replace(hour=18, minute=0, second=0, microsecond=0)
    
    return google_calendar_service.find_available_slots(
        user_ids=participant_ids,
        duration_minutes=duration_minutes,
        preferred_start=start_of_day,
        preferred_end=end_of_day,
        max_suggestions=max_suggestions
    )