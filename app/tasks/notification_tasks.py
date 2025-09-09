"""
Sistema de Tareas de Notificaciones - Ecosistema de Emprendimiento
================================================================

Este módulo maneja todas las tareas asíncronas relacionadas con notificaciones
para el ecosistema de emprendimiento. Incluye notificaciones push, in-app, SMS,
WebSocket, digest y integración con servicios externos.

Funcionalidades principales:
- Notificaciones push (Firebase/FCM)
- Notificaciones in-app y WebSocket
- SMS para eventos críticos
- Digest de notificaciones
- Notificaciones de reuniones y mentorías
- Alertas del sistema
- Integración con Slack/Teams
- Gestión de preferencias de usuario
- Analytics y tracking de notificaciones
- Procesamiento de colas con prioridades
"""

import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from celery import group, chain, chord
import requests
from firebase_admin import messaging
import firebase_admin
from firebase_admin import credentials
from twilio.rest import Client as TwilioClient
from slack_sdk import WebClient as SlackClient

from app.tasks.celery_app import celery_app
from app.core.exceptions import (
    NotificationError, 
    PushNotificationError, 
    SMSError,
    WebSocketError
)
from app.core.constants import (
    NOTIFICATION_TYPES, 
    NOTIFICATION_PRIORITIES, 
    NOTIFICATION_CHANNELS,
    USER_ROLES
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.meeting import Meeting
from app.models.mentorship import MentorshipSession
from app.models.project import Project
from app.models.notification import (
    Notification, 
    NotificationStatus, 
    NotificationType,
    NotificationChannel,
    NotificationPriority
)
from app.models.notification_preference import NotificationPreference
from app.models.device_token import DeviceToken
from app.models.activity_log import ActivityLog, ActivityType
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.services.analytics_service import AnalyticsService
from app.utils.formatters import format_datetime, format_user_name, truncate_text
from app.utils.string_utils import sanitize_input, generate_unique_id
from app.utils.cache_utils import cache_get, cache_set, cache_delete
from app.utils.crypto_utils import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

# Configuración de servicios externos
FIREBASE_CREDENTIALS_PATH = 'config/firebase-service-account.json'
TWILIO_ACCOUNT_SID = 'config/TWILIO_ACCOUNT_SID'
TWILIO_AUTH_TOKEN = 'config/TWILIO_AUTH_TOKEN'
TWILIO_PHONE_NUMBER = 'config/TWILIO_PHONE_NUMBER'
SLACK_BOT_TOKEN = 'config/SLACK_BOT_TOKEN'

# Inicialización de servicios
try:
    # Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    
    # Twilio
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    # Slack
    slack_client = SlackClient(token=SLACK_BOT_TOKEN)
    
except Exception as e:
    logger.warning(f"Error inicializando servicios externos: {str(e)}")
    twilio_client = None
    slack_client = None


class NotificationTemplate(Enum):
    """Templates de notificaciones"""
    MEETING_REMINDER = "meeting_reminder"
    MEETING_CANCELLED = "meeting_cancelled"
    MENTORSHIP_SCHEDULED = "mentorship_scheduled"
    MENTORSHIP_COMPLETED = "mentorship_completed"
    PROJECT_UPDATE = "project_update"
    PROJECT_MILESTONE = "project_milestone"
    SYSTEM_ALERT = "system_alert"
    WELCOME = "welcome"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_SUMMARY = "weekly_summary"
    ACHIEVEMENT = "achievement"
    DEADLINE_APPROACHING = "deadline_approaching"
    NEW_CONNECTION = "new_connection"
    FEEDBACK_REQUEST = "feedback_request"


@dataclass
class NotificationPayload:
    """Payload para notificaciones"""
    title: str
    body: str
    data: dict[str, Any] = None
    icon: str = "default"
    sound: str = "default"
    badge: int = 1
    click_action: str = None
    image_url: str = None
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NotificationContext:
    """Contexto para generar notificaciones"""
    user: dict[str, Any]
    trigger_user: dict[str, Any] = None
    entity: dict[str, Any] = None
    metadata: dict[str, Any] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = format_datetime(datetime.now(timezone.utc))


# === TAREAS DE NOTIFICACIONES INMEDIATAS ===

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue='notifications',
    priority=NotificationPriority.HIGH.value
)
def send_push_notification(self, user_id: int, payload: dict[str, Any], channels: list[str] = None):
    """
    Envía notificación push a un usuario específico
    
    Args:
        user_id: ID del usuario destinatario
        payload: Datos de la notificación
        channels: Canales específicos (fcm, apns, web)
    """
    try:
        logger.info(f"Enviando notificación push a usuario {user_id}")
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            logger.error(f"Usuario {user_id} no encontrado")
            return {'success': False, 'error': 'User not found'}
        
        # Verificar preferencias de notificación
        if not _should_send_notification(user, NotificationChannel.PUSH):
            logger.info(f"Usuario {user_id} tiene notificaciones push deshabilitadas")
            return {'success': True, 'message': 'Notifications disabled', 'sent': False}
        
        # Obtener tokens de dispositivos activos
        device_tokens = DeviceToken.query.filter(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True
        ).all()
        
        if not device_tokens:
            logger.warning(f"No hay tokens de dispositivo para usuario {user_id}")
            return {'success': False, 'error': 'No device tokens found'}
        
        # Crear payload de notificación
        notification_payload = NotificationPayload(**payload)
        
        # Enviar a cada dispositivo
        results = []
        for token in device_tokens:
            try:
                if channels and token.platform not in channels:
                    continue
                
                result = _send_firebase_notification(token, notification_payload)
                results.append({
                    'token_id': token.id,
                    'platform': token.platform,
                    'success': result.get('success', False),
                    'message_id': result.get('message_id'),
                    'error': result.get('error')
                })
                
                # Marcar token como inválido si hay error persistente
                if not result.get('success') and 'invalid' in result.get('error', '').lower():
                    token.is_active = False
                    
            except Exception as e:
                logger.error(f"Error enviando a token {token.id}: {str(e)}")
                results.append({
                    'token_id': token.id,
                    'platform': token.platform,
                    'success': False,
                    'error': str(e)
                })
        
        # Guardar cambios de tokens
        from app import db
        db.session.commit()
        
        # Registrar notificación en base de datos
        _save_notification_log(
            user_id=user_id,
            channel=NotificationChannel.PUSH,
            payload=payload,
            results=results,
            status=NotificationStatus.SENT if any(r['success'] for r in results) else NotificationStatus.FAILED
        )
        
        # Resumir resultados
        successful_sends = sum(1 for r in results if r['success'])
        total_tokens = len(results)
        
        logger.info(f"Push notification enviada: {successful_sends}/{total_tokens} exitosos")
        
        return {
            'success': successful_sends > 0,
            'total_tokens': total_tokens,
            'successful_sends': successful_sends,
            'failed_sends': total_tokens - successful_sends,
            'results': results
        }
        
    except Exception as exc:
        logger.error(f"Error enviando notificación push: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='notifications',
    priority=NotificationPriority.HIGH.value
)
def send_websocket_notification(self, user_id: int, event_type: str, data: dict[str, Any]):
    """
    Envía notificación en tiempo real vía WebSocket
    
    Args:
        user_id: ID del usuario destinatario
        event_type: Tipo de evento WebSocket
        data: Datos del evento
    """
    try:
        logger.info(f"Enviando notificación WebSocket a usuario {user_id}")
        
        # Verificar que el usuario existe y está activo
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return {'success': False, 'error': 'User not found or inactive'}
        
        # Verificar preferencias
        if not _should_send_notification(user, NotificationChannel.WEBSOCKET):
            return {'success': True, 'message': 'WebSocket notifications disabled', 'sent': False}
        
        # Importar socketio después para evitar imports circulares
        from app.sockets import socketio, socket_manager
        
        if not socketio or not socket_manager:
            logger.error("WebSocket no está disponible")
            return {'success': False, 'error': 'WebSocket not available'}
        
        # Preparar payload de notificación
        notification_data = {
            'type': event_type,
            'data': data,
            'timestamp': format_datetime(datetime.now(timezone.utc)),
            'user_id': user_id
        }
        
        # Enviar notificación vía WebSocket
        result = socket_manager.emit_to_user(
            user_id=str(user_id),
            event='notification',
            data=notification_data,
            namespace='/notifications'
        )
        
        if result:
            logger.info(f"Notificación WebSocket enviada exitosamente a usuario {user_id}")
            
            # Registrar en base de datos
            _save_notification_log(
                user_id=user_id,
                channel=NotificationChannel.WEBSOCKET,
                payload={'event_type': event_type, **data},
                results=[{'success': True, 'channel': 'websocket'}],
                status=NotificationStatus.DELIVERED
            )
            
            return {'success': True, 'delivered': True}
        else:
            logger.warning(f"Usuario {user_id} no está conectado vía WebSocket")
            
            # Guardar para entregar cuando se conecte
            _save_pending_websocket_notification(user_id, notification_data)
            
            return {'success': True, 'delivered': False, 'queued': True}
        
    except Exception as exc:
        logger.error(f"Error enviando notificación WebSocket: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue='notifications',
    priority=NotificationPriority.URGENT.value
)
def send_sms_notification(self, user_id: int, message: str, urgent: bool = False):
    """
    Envía notificación SMS para eventos críticos
    
    Args:
        user_id: ID del usuario destinatario
        message: Mensaje SMS
        urgent: Si es urgente (omite algunas verificaciones)
    """
    try:
        logger.info(f"Enviando SMS a usuario {user_id}, urgente: {urgent}")
        
        if not twilio_client:
            logger.error("Cliente Twilio no está configurado")
            return {'success': False, 'error': 'SMS service not configured'}
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Verificar que tiene número de teléfono
        if not user.phone_number:
            logger.warning(f"Usuario {user_id} no tiene número de teléfono")
            return {'success': False, 'error': 'No phone number'}
        
        # Verificar preferencias (excepto para urgentes)
        if not urgent and not _should_send_notification(user, NotificationChannel.SMS):
            return {'success': True, 'message': 'SMS notifications disabled', 'sent': False}
        
        # Verificar rate limiting para SMS
        if not urgent and not _check_sms_rate_limit(user_id):
            logger.warning(f"Rate limit excedido para SMS a usuario {user_id}")
            return {'success': False, 'error': 'SMS rate limit exceeded'}
        
        # Truncar mensaje si es muy largo
        truncated_message = truncate_text(message, 160)
        if len(message) > 160:
            truncated_message += "..."
        
        try:
            # Enviar SMS
            sms_message = twilio_client.messages.create(
                body=truncated_message,
                from_=TWILIO_PHONE_NUMBER,
                to=user.phone_number
            )
            
            logger.info(f"SMS enviado exitosamente a {user.phone_number}: {sms_message.sid}")
            
            # Registrar en base de datos
            _save_notification_log(
                user_id=user_id,
                channel=NotificationChannel.SMS,
                payload={'message': message, 'urgent': urgent},
                results=[{
                    'success': True, 
                    'message_sid': sms_message.sid,
                    'to': user.phone_number
                }],
                status=NotificationStatus.SENT
            )
            
            # Actualizar rate limiting
            _update_sms_rate_limit(user_id)
            
            return {
                'success': True,
                'message_sid': sms_message.sid,
                'to': user.phone_number,
                'message_length': len(truncated_message)
            }
            
        except Exception as sms_error:
            logger.error(f"Error de Twilio enviando SMS: {str(sms_error)}")
            
            # Registrar fallo
            _save_notification_log(
                user_id=user_id,
                channel=NotificationChannel.SMS,
                payload={'message': message, 'urgent': urgent},
                results=[{'success': False, 'error': str(sms_error)}],
                status=NotificationStatus.FAILED
            )
            
            return {'success': False, 'error': f'Twilio error: {str(sms_error)}'}
        
    except Exception as exc:
        logger.error(f"Error enviando SMS: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='notifications',
    priority=NotificationPriority.NORMAL.value
)
def send_in_app_notification(self, user_id: int, notification_data: dict[str, Any]):
    """
    Crea notificación in-app en la base de datos
    
    Args:
        user_id: ID del usuario destinatario
        notification_data: Datos de la notificación
    """
    try:
        logger.info(f"Creando notificación in-app para usuario {user_id}")
        
        # Verificar usuario
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Verificar preferencias
        if not _should_send_notification(user, NotificationChannel.IN_APP):
            return {'success': True, 'message': 'In-app notifications disabled', 'created': False}
        
        # Crear notificación in-app
        notification = Notification(
            user_id=user_id,
            title=notification_data.get('title', ''),
            message=notification_data.get('message', ''),
            notification_type=notification_data.get('type', NotificationType.INFO),
            priority=notification_data.get('priority', NotificationPriority.NORMAL),
            channel=NotificationChannel.IN_APP,
            data=notification_data.get('data', {}),
            action_url=notification_data.get('action_url'),
            expires_at=notification_data.get('expires_at'),
            status=NotificationStatus.UNREAD
        )
        
        from app import db
        db.session.add(notification)
        db.session.commit()
        
        # Enviar también vía WebSocket si el usuario está conectado
        if notification_data.get('send_websocket', True):
            send_websocket_notification.apply_async(
                args=[user_id, 'new_notification', {
                    'notification_id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'type': notification.notification_type.value,
                    'action_url': notification.action_url
                }],
                countdown=1
            )
        
        logger.info(f"Notificación in-app creada con ID {notification.id}")
        
        return {
            'success': True,
            'notification_id': notification.id,
            'created': True
        }
        
    except Exception as exc:
        logger.error(f"Error creando notificación in-app: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE NOTIFICACIONES ESPECÍFICAS DEL ECOSISTEMA ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='notifications',
    priority=NotificationPriority.HIGH.value
)
def send_meeting_notification(self, meeting_id: int, notification_type: str, users: list[int] = None):
    """
    Envía notificaciones relacionadas con reuniones
    
    Args:
        meeting_id: ID de la reunión
        notification_type: Tipo (scheduled, reminder_24h, reminder_1h, cancelled, updated)
        users: Lista específica de usuarios (opcional)
    """
    try:
        logger.info(f"Enviando notificación de reunión {meeting_id} tipo {notification_type}")
        
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            return {'success': False, 'error': 'Meeting not found'}
        
        # Determinar destinatarios
        if users:
            recipients = User.query.filter(User.id.in_(users)).all()
        else:
            recipients = meeting.participants
        
        # Preparar contexto
        context = NotificationContext(
            user={},  # Se completa para cada usuario
            entity={
                'type': 'meeting',
                'id': meeting.id,
                'title': meeting.title,
                'start_time': format_datetime(meeting.start_time),
                'location': meeting.location,
                'meeting_url': meeting.meeting_url
            },
            metadata={'notification_type': notification_type}
        )
        
        # Configuración por tipo de notificación
        notification_configs = {
            'scheduled': {
                'title': 'Reunión programada',
                'template': '📅 Tienes una nueva reunión: {title}',
                'priority': NotificationPriority.HIGH,
                'channels': [NotificationChannel.PUSH, NotificationChannel.IN_APP]
            },
            'reminder_24h': {
                'title': 'Recordatorio de reunión',
                'template': '⏰ Reunión mañana: {title}',
                'priority': NotificationPriority.HIGH,
                'channels': [NotificationChannel.PUSH, NotificationChannel.IN_APP]
            },
            'reminder_1h': {
                'title': 'Reunión próxima',
                'template': '🔔 Reunión en 1 hora: {title}',
                'priority': NotificationPriority.URGENT,
                'channels': [NotificationChannel.PUSH, NotificationChannel.IN_APP, NotificationChannel.SMS]
            },
            'cancelled': {
                'title': 'Reunión cancelada',
                'template': '❌ Reunión cancelada: {title}',
                'priority': NotificationPriority.HIGH,
                'channels': [NotificationChannel.PUSH, NotificationChannel.IN_APP, NotificationChannel.SMS]
            },
            'updated': {
                'title': 'Reunión actualizada',
                'template': '✏️ Cambios en reunión: {title}',
                'priority': NotificationPriority.NORMAL,
                'channels': [NotificationChannel.PUSH, NotificationChannel.IN_APP]
            }
        }
        
        config = notification_configs.get(notification_type)
        if not config:
            return {'success': False, 'error': f'Unknown notification type: {notification_type}'}
        
        # Enviar a cada participante
        results = []
        for recipient in recipients:
            # Personalizar contexto para cada usuario
            context.user = {
                'id': recipient.id,
                'name': recipient.get_full_name(),
                'email': recipient.email
            }
            
            # Preparar payload
            message = config['template'].format(title=meeting.title)
            payload = {
                'title': config['title'],
                'message': message,
                'type': NotificationType.MEETING,
                'priority': config['priority'],
                'data': {
                    'meeting_id': meeting.id,
                    'notification_type': notification_type,
                    'action_url': f'/meetings/{meeting.id}'
                }
            }
            
            # Enviar por cada canal configurado
            for channel in config['channels']:
                try:
                    if channel == NotificationChannel.PUSH:
                        result = send_push_notification.apply_async(
                            args=[recipient.id, payload],
                            countdown=1
                        )
                    elif channel == NotificationChannel.IN_APP:
                        result = send_in_app_notification.apply_async(
                            args=[recipient.id, payload],
                            countdown=1
                        )
                    elif channel == NotificationChannel.SMS and notification_type in ['reminder_1h', 'cancelled']:
                        result = send_sms_notification.apply_async(
                            args=[recipient.id, message, True],
                            countdown=1
                        )
                    
                    results.append({
                        'user_id': recipient.id,
                        'channel': channel.value,
                        'task_id': result.id if hasattr(result, 'id') else None
                    })
                    
                except Exception as e:
                    logger.error(f"Error enviando notificación a {recipient.id} por {channel.value}: {str(e)}")
                    results.append({
                        'user_id': recipient.id,
                        'channel': channel.value,
                        'error': str(e)
                    })
        
        logger.info(f"Notificaciones de reunión enviadas: {len(results)} total")
        
        return {
            'success': True,
            'meeting_id': meeting_id,
            'notification_type': notification_type,
            'total_notifications': len(results),
            'recipients': len(recipients),
            'results': results
        }
        
    except Exception as exc:
        logger.error(f"Error enviando notificaciones de reunión: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=90,
    queue='notifications',
    priority=NotificationPriority.NORMAL.value
)
def send_mentorship_notification(self, session_id: int, notification_type: str):
    """
    Envía notificaciones de sesiones de mentoría
    
    Args:
        session_id: ID de la sesión de mentoría
        notification_type: Tipo (scheduled, reminder, completed, feedback_request)
    """
    try:
        logger.info(f"Enviando notificación de mentoría {session_id} tipo {notification_type}")
        
        # Obtener sesión
        session = MentorshipSession.query.get(session_id)
        if not session:
            return {'success': False, 'error': 'Session not found'}
        
        # Configuración por tipo
        notification_configs = {
            'scheduled': {
                'title': 'Sesión de mentoría programada',
                'entrepreneur_msg': '🎯 Tienes una nueva sesión de mentoría con {mentor_name}',
                'mentor_msg': '👥 Nueva sesión de mentoría con {entrepreneur_name}',
                'priority': NotificationPriority.HIGH
            },
            'reminder': {
                'title': 'Recordatorio de mentoría',
                'entrepreneur_msg': '⏰ Sesión de mentoría en 1 hora con {mentor_name}',
                'mentor_msg': '⏰ Sesión de mentoría en 1 hora con {entrepreneur_name}',
                'priority': NotificationPriority.URGENT
            },
            'completed': {
                'title': 'Sesión completada',
                'entrepreneur_msg': '✅ Sesión de mentoría completada con {mentor_name}',
                'mentor_msg': '✅ Sesión de mentoría completada con {entrepreneur_name}',
                'priority': NotificationPriority.NORMAL
            },
            'feedback_request': {
                'title': 'Feedback pendiente',
                'entrepreneur_msg': '💭 Comparte tu feedback sobre la sesión con {mentor_name}',
                'mentor_msg': '💭 Comparte tu feedback sobre la sesión con {entrepreneur_name}',
                'priority': NotificationPriority.NORMAL
            }
        }
        
        config = notification_configs.get(notification_type)
        if not config:
            return {'success': False, 'error': f'Unknown notification type: {notification_type}'}
        
        results = []
        
        # Notificar al emprendedor
        entrepreneur_msg = config['entrepreneur_msg'].format(
            mentor_name=session.mentor.get_full_name()
        )
        entrepreneur_payload = {
            'title': config['title'],
            'message': entrepreneur_msg,
            'type': NotificationType.MENTORSHIP,
            'priority': config['priority'],
            'data': {
                'session_id': session.id,
                'notification_type': notification_type,
                'action_url': f'/mentorship/sessions/{session.id}'
            }
        }
        
        # Enviar al emprendedor
        entrepreneur_results = _send_multi_channel_notification(
            session.entrepreneur_id, 
            entrepreneur_payload,
            [NotificationChannel.PUSH, NotificationChannel.IN_APP]
        )
        results.extend(entrepreneur_results)
        
        # Notificar al mentor
        mentor_msg = config['mentor_msg'].format(
            entrepreneur_name=session.entrepreneur.get_full_name()
        )
        mentor_payload = {
            'title': config['title'],
            'message': mentor_msg,
            'type': NotificationType.MENTORSHIP,
            'priority': config['priority'],
            'data': {
                'session_id': session.id,
                'notification_type': notification_type,
                'action_url': f'/mentorship/sessions/{session.id}'
            }
        }
        
        # Enviar al mentor
        mentor_results = _send_multi_channel_notification(
            session.mentor_id,
            mentor_payload,
            [NotificationChannel.PUSH, NotificationChannel.IN_APP]
        )
        results.extend(mentor_results)
        
        logger.info(f"Notificaciones de mentoría enviadas: {len(results)} total")
        
        return {
            'success': True,
            'session_id': session_id,
            'notification_type': notification_type,
            'total_notifications': len(results),
            'results': results
        }
        
    except Exception as exc:
        logger.error(f"Error enviando notificaciones de mentoría: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=90 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='notifications',
    priority=NotificationPriority.NORMAL.value
)
def send_project_notification(self, project_id: int, notification_type: str, metadata: dict[str, Any] = None):
    """
    Envía notificaciones relacionadas con proyectos
    
    Args:
        project_id: ID del proyecto
        notification_type: Tipo (created, updated, milestone, deadline)
        metadata: Metadatos adicionales
    """
    try:
        logger.info(f"Enviando notificación de proyecto {project_id} tipo {notification_type}")
        
        # Obtener proyecto
        project = Project.query.get(project_id)
        if not project:
            return {'success': False, 'error': 'Project not found'}
        
        # Determinar destinatarios
        recipients = [project.entrepreneur]
        if project.mentors:
            recipients.extend(project.mentors)
        
        # Configuración por tipo
        notification_configs = {
            'created': {
                'title': 'Nuevo proyecto creado',
                'template': '🚀 Proyecto "{project_name}" ha sido creado',
                'priority': NotificationPriority.NORMAL
            },
            'updated': {
                'title': 'Proyecto actualizado',
                'template': '📝 Proyecto "{project_name}" ha sido actualizado',
                'priority': NotificationPriority.LOW
            },
            'milestone': {
                'title': 'Hito alcanzado',
                'template': '🎯 Hito completado en proyecto "{project_name}"',
                'priority': NotificationPriority.HIGH
            },
            'deadline': {
                'title': 'Fecha límite próxima',
                'template': '⏰ Fecha límite próxima en proyecto "{project_name}"',
                'priority': NotificationPriority.HIGH
            }
        }
        
        config = notification_configs.get(notification_type)
        if not config:
            return {'success': False, 'error': f'Unknown notification type: {notification_type}'}
        
        # Preparar mensaje
        message = config['template'].format(project_name=project.name)
        
        # Enviar a cada destinatario
        results = []
        for recipient in recipients:
            payload = {
                'title': config['title'],
                'message': message,
                'type': NotificationType.PROJECT,
                'priority': config['priority'],
                'data': {
                    'project_id': project.id,
                    'notification_type': notification_type,
                    'action_url': f'/projects/{project.id}',
                    **(metadata if metadata else {})
                }
            }
            
            # Enviar por múltiples canales
            recipient_results = _send_multi_channel_notification(
                recipient.id,
                payload,
                [NotificationChannel.PUSH, NotificationChannel.IN_APP]
            )
            results.extend(recipient_results)
        
        logger.info(f"Notificaciones de proyecto enviadas: {len(results)} total")
        
        return {
            'success': True,
            'project_id': project_id,
            'notification_type': notification_type,
            'total_notifications': len(results),
            'recipients': len(recipients),
            'results': results
        }
        
    except Exception as exc:
        logger.error(f"Error enviando notificaciones de proyecto: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE DIGEST Y RESÚMENES ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='notifications',
    priority=NotificationPriority.LOW.value
)
def send_daily_notification_digest(self, user_id: int = None):
    """
    Envía digest diario de notificaciones
    
    Args:
        user_id: ID específico de usuario, si None envía a todos
    """
    try:
        logger.info(f"Generando digest diario de notificaciones para usuario {user_id or 'todos'}")
        
        if user_id:
            users = [User.query.get(user_id)]
        else:
            # Obtener usuarios activos con digest habilitado
            users = User.query.filter(
                User.is_active == True,
                User.notification_preferences.contains('"daily_digest": true')
            ).all()
        
        results = []
        
        for user in users:
            if not user:
                continue
            
            # Obtener notificaciones del día
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            notifications = Notification.query.filter(
                Notification.user_id == user.id,
                Notification.created_at >= today_start,
                Notification.status != NotificationStatus.DELETED
            ).order_by(Notification.created_at.desc()).limit(20).all()
            
            if not notifications:
                logger.debug(f"Sin notificaciones para digest de {user.email}")
                continue
            
            # Agrupar notificaciones por tipo
            grouped_notifications = _group_notifications_for_digest(notifications)
            
            # Preparar payload del digest
            digest_payload = {
                'title': f'Tu resumen diario - {datetime.now().strftime("%d/%m/%Y")}',
                'message': f'Tienes {len(notifications)} notificaciones de hoy',
                'type': NotificationType.DIGEST,
                'priority': NotificationPriority.LOW,
                'data': {
                    'digest_type': 'daily',
                    'notification_count': len(notifications),
                    'grouped_notifications': grouped_notifications,
                    'action_url': '/notifications'
                }
            }
            
            # Enviar digest
            result = send_in_app_notification.apply_async(
                args=[user.id, digest_payload],
                countdown=1
            )
            
            results.append({
                'user_id': user.id,
                'notification_count': len(notifications),
                'task_id': result.id if hasattr(result, 'id') else None
            })
        
        logger.info(f"Digest diario enviado a {len(results)} usuarios")
        
        return {
            'success': True,
            'total_users': len(results),
            'results': results,
            'date': datetime.now().date().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Error enviando digest diario: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='notifications',
    priority=NotificationPriority.LOW.value
)
def send_weekly_notification_summary(self, user_id: int = None):
    """
    Envía resumen semanal de actividad y notificaciones
    
    Args:
        user_id: ID específico de usuario, si None envía a todos
    """
    try:
        logger.info(f"Generando resumen semanal para usuario {user_id or 'todos'}")
        
        if user_id:
            users = [User.query.get(user_id)]
        else:
            users = User.query.filter(
                User.is_active == True,
                User.notification_preferences.contains('"weekly_summary": true')
            ).all()
        
        results = []
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        
        for user in users:
            if not user:
                continue
            
            # Obtener estadísticas de la semana
            weekly_stats = _get_weekly_user_stats(user.id, week_start)
            
            # Solo enviar si hay actividad significativa
            if not _has_significant_weekly_activity(weekly_stats):
                continue
            
            # Preparar payload del resumen
            summary_payload = {
                'title': f'Tu resumen semanal - Semana {datetime.now().isocalendar()[1]}',
                'message': _generate_weekly_summary_message(weekly_stats),
                'type': NotificationType.SUMMARY,
                'priority': NotificationPriority.LOW,
                'data': {
                    'summary_type': 'weekly',
                    'week': datetime.now().isocalendar()[1],
                    'year': datetime.now().year,
                    'stats': weekly_stats,
                    'action_url': f'/{user.role.value}/dashboard'
                }
            }
            
            # Enviar resumen
            result = send_in_app_notification.apply_async(
                args=[user.id, summary_payload],
                countdown=1
            )
            
            results.append({
                'user_id': user.id,
                'stats': weekly_stats,
                'task_id': result.id if hasattr(result, 'id') else None
            })
        
        logger.info(f"Resumen semanal enviado a {len(results)} usuarios")
        
        return {
            'success': True,
            'total_users': len(results),
            'results': results,
            'week': datetime.now().isocalendar()[1]
        }
        
    except Exception as exc:
        logger.error(f"Error enviando resumen semanal: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE PROCESAMIENTO Y MANTENIMIENTO ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='notifications',
    priority=NotificationPriority.LOW.value
)
def process_notification_queue(self):
    """
    Procesa la cola de notificaciones pendientes
    """
    try:
        logger.info("Procesando cola de notificaciones pendientes")
        
        # Obtener notificaciones pendientes de los últimos 3 días
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=3)
        pending_notifications = Notification.query.filter(
            Notification.status == NotificationStatus.PENDING,
            Notification.created_at >= cutoff_date
        ).order_by(Notification.priority.desc(), Notification.created_at.asc()).limit(200).all()
        
        if not pending_notifications:
            logger.info("No hay notificaciones pendientes para procesar")
            return {'success': True, 'processed': 0}
        
        logger.info(f"Procesando {len(pending_notifications)} notificaciones pendientes")
        
        processed = 0
        failed = 0
        
        for notification in pending_notifications:
            try:
                # Determinar canal preferido del usuario
                preferred_channels = _get_user_preferred_channels(notification.user_id)
                
                success = False
                for channel in preferred_channels:
                    try:
                        if channel == NotificationChannel.PUSH:
                            result = _send_firebase_notification_for_pending(notification)
                        elif channel == NotificationChannel.WEBSOCKET:
                            result = _send_websocket_notification_for_pending(notification)
                        elif channel == NotificationChannel.SMS:
                            result = _send_sms_notification_for_pending(notification)
                        else:
                            continue
                        
                        if result.get('success'):
                            success = True
                            break
                            
                    except Exception as e:
                        logger.error(f"Error enviando notificación {notification.id} por {channel.value}: {str(e)}")
                        continue
                
                # Actualizar estado
                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.now(timezone.utc)
                    processed += 1
                else:
                    notification.retry_count += 1
                    if notification.retry_count >= 3:
                        notification.status = NotificationStatus.FAILED
                    failed += 1
                
                from app import db
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Error procesando notificación {notification.id}: {str(e)}")
                failed += 1
        
        logger.info(f"Procesamiento completado: {processed} exitosos, {failed} fallidos")
        
        return {
            'success': True,
            'total_processed': len(pending_notifications),
            'successful': processed,
            'failed': failed
        }
        
    except Exception as exc:
        logger.error(f"Error procesando cola de notificaciones: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    queue='notifications',
    priority=NotificationPriority.LOW.value
)
def cleanup_old_notifications(self):
    """
    Limpia notificaciones antiguas y caducadas
    """
    try:
        logger.info("Iniciando limpieza de notificaciones antiguas")
        
        # Limpiar notificaciones leídas mayores a 30 días
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        old_read_notifications = Notification.query.filter(
            Notification.status == NotificationStatus.READ,
            Notification.created_at < thirty_days_ago
        )
        
        old_read_count = old_read_notifications.count()
        old_read_notifications.delete(synchronize_session=False)
        
        # Limpiar notificaciones caducadas
        expired_notifications = Notification.query.filter(
            Notification.expires_at.isnot(None),
            Notification.expires_at < datetime.now(timezone.utc),
            Notification.status != NotificationStatus.DELETED
        )
        
        expired_count = expired_notifications.count()
        expired_notifications.update(
            {Notification.status: NotificationStatus.DELETED},
            synchronize_session=False
        )
        
        # Limpiar notificaciones fallidas mayores a 7 días
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        failed_notifications = Notification.query.filter(
            Notification.status == NotificationStatus.FAILED,
            Notification.created_at < seven_days_ago
        )
        
        failed_count = failed_notifications.count()
        failed_notifications.delete(synchronize_session=False)
        
        # Limpiar tokens de dispositivo inactivos
        inactive_tokens = DeviceToken.query.filter(
            DeviceToken.is_active == False,
            DeviceToken.updated_at < thirty_days_ago
        )
        
        inactive_tokens_count = inactive_tokens.count()
        inactive_tokens.delete(synchronize_session=False)
        
        from app import db
        db.session.commit()
        
        logger.info(f"Limpieza completada: {old_read_count} leídas, {expired_count} caducadas, {failed_count} fallidas, {inactive_tokens_count} tokens")
        
        return {
            'success': True,
            'old_read_deleted': old_read_count,
            'expired_marked': expired_count,
            'failed_deleted': failed_count,
            'inactive_tokens_deleted': inactive_tokens_count
        }
        
    except Exception as exc:
        logger.error(f"Error en limpieza de notificaciones: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=600)
        return {'success': False, 'error': str(exc)}


# === TAREAS DE INTEGRACIÓN EXTERNA ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    queue='notifications',
    priority=NotificationPriority.NORMAL.value
)
def send_slack_notification(self, channel: str, message: str, attachments: list[Dict] = None):
    """
    Envía notificación a Slack
    
    Args:
        channel: Canal de Slack (#general, #alerts, etc.)
        message: Mensaje a enviar
        attachments: Attachments de Slack (opcional)
    """
    try:
        logger.info(f"Enviando notificación a Slack canal {channel}")
        
        if not slack_client:
            logger.error("Cliente Slack no está configurado")
            return {'success': False, 'error': 'Slack client not configured'}
        
        try:
            # Enviar mensaje a Slack
            response = slack_client.chat_postMessage(
                channel=channel,
                text=message,
                attachments=attachments or []
            )
            
            if response['ok']:
                logger.info(f"Mensaje enviado exitosamente a Slack: {response['ts']}")
                return {
                    'success': True,
                    'channel': channel,
                    'timestamp': response['ts'],
                    'message': message
                }
            else:
                logger.error(f"Error de Slack: {response['error']}")
                return {'success': False, 'error': response['error']}
                
        except Exception as slack_error:
            logger.error(f"Error enviando a Slack: {str(slack_error)}")
            return {'success': False, 'error': f'Slack error: {str(slack_error)}'}
        
    except Exception as exc:
        logger.error(f"Error en notificación Slack: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === FUNCIONES AUXILIARES PRIVADAS ===

def _send_firebase_notification(token: DeviceToken, payload: NotificationPayload) -> dict[str, Any]:
    """Envía notificación push vía Firebase"""
    try:
        # Preparar mensaje FCM
        message = messaging.Message(
            notification=messaging.Notification(
                title=payload.title,
                body=payload.body,
                image=payload.image_url
            ),
            data=payload.data or {},
            token=token.token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon=payload.icon,
                    sound=payload.sound,
                    click_action=payload.click_action
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        badge=payload.badge,
                        sound=payload.sound,
                        alert=messaging.ApsAlert(
                            title=payload.title,
                            body=payload.body
                        )
                    )
                )
            )
        )
        
        # Enviar mensaje
        response = messaging.send(message)
        
        logger.debug(f"FCM enviado exitosamente: {response}")
        
        return {
            'success': True,
            'message_id': response,
            'platform': token.platform
        }
        
    except messaging.UnregisteredError:
        logger.warning(f"Token no registrado: {token.id}")
        return {'success': False, 'error': 'invalid token - unregistered'}
    except messaging.SenderIdMismatchError:
        logger.warning(f"Sender ID mismatch para token: {token.id}")
        return {'success': False, 'error': 'invalid token - sender mismatch'}
    except Exception as e:
        logger.error(f"Error FCM: {str(e)}")
        return {'success': False, 'error': str(e)}


def _should_send_notification(user: User, channel: NotificationChannel) -> bool:
    """Verifica si se debe enviar notificación según preferencias del usuario"""
    try:
        # Obtener preferencias del usuario
        preferences = user.notification_preferences or {}
        
        # Mapeo de canales a configuración
        channel_mapping = {
            NotificationChannel.PUSH: 'push_notifications',
            NotificationChannel.IN_APP: 'in_app_notifications',
            NotificationChannel.SMS: 'sms_notifications',
            NotificationChannel.EMAIL: 'email_notifications',
            NotificationChannel.WEBSOCKET: 'websocket_notifications'
        }
        
        pref_key = channel_mapping.get(channel)
        if not pref_key:
            return True  # Por defecto permitir si no hay mapeo
        
        return preferences.get(pref_key, True)  # Por defecto True
        
    except Exception as e:
        logger.error(f"Error verificando preferencias: {str(e)}")
        return True  # En caso de error, permitir notificación


def _save_notification_log(
    user_id: int,
    channel: NotificationChannel,
    payload: dict[str, Any],
    results: list[dict[str, Any]],
    status: NotificationStatus
):
    """Guarda log de notificación en base de datos"""
    try:
        from app.models.notification_log import NotificationLog
        from app import db
        
        log = NotificationLog(
            user_id=user_id,
            channel=channel,
            payload=payload,
            results=results,
            status=status,
            sent_at=datetime.now(timezone.utc) if status == NotificationStatus.SENT else None
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error guardando log de notificación: {str(e)}")


def _save_pending_websocket_notification(user_id: int, notification_data: dict[str, Any]):
    """Guarda notificación WebSocket para entrega posterior"""
    try:
        cache_key = f"pending_websocket_{user_id}"
        pending_notifications = cache_get(cache_key) or []
        
        pending_notifications.append({
            **notification_data,
            'queued_at': datetime.now(timezone.utc).isoformat()
        })
        
        # Mantener solo las últimas 10 notificaciones pendientes
        if len(pending_notifications) > 10:
            pending_notifications = pending_notifications[-10:]
        
        cache_set(cache_key, pending_notifications, timeout=86400)  # 24 horas
        
    except Exception as e:
        logger.error(f"Error guardando notificación WebSocket pendiente: {str(e)}")


def _check_sms_rate_limit(user_id: int) -> bool:
    """Verifica rate limiting para SMS"""
    try:
        cache_key = f"sms_rate_limit_{user_id}"
        sent_count = cache_get(cache_key) or 0
        
        # Límite: 5 SMS por hora
        return sent_count < 5
        
    except Exception as e:
        logger.error(f"Error verificando rate limit SMS: {str(e)}")
        return True


def _update_sms_rate_limit(user_id: int):
    """Actualiza contador de rate limiting para SMS"""
    try:
        cache_key = f"sms_rate_limit_{user_id}"
        sent_count = cache_get(cache_key) or 0
        cache_set(cache_key, sent_count + 1, timeout=3600)  # 1 hora
        
    except Exception as e:
        logger.error(f"Error actualizando rate limit SMS: {str(e)}")


def _send_multi_channel_notification(user_id: int, payload: dict[str, Any], channels: list[NotificationChannel]) -> list[dict[str, Any]]:
    """Envía notificación por múltiples canales"""
    results = []
    
    for channel in channels:
        try:
            if channel == NotificationChannel.PUSH:
                result = send_push_notification.apply_async(
                    args=[user_id, payload],
                    countdown=1
                )
            elif channel == NotificationChannel.IN_APP:
                result = send_in_app_notification.apply_async(
                    args=[user_id, payload],
                    countdown=1
                )
            elif channel == NotificationChannel.WEBSOCKET:
                result = send_websocket_notification.apply_async(
                    args=[user_id, 'notification', payload],
                    countdown=1
                )
            
            results.append({
                'user_id': user_id,
                'channel': channel.value,
                'task_id': result.id if hasattr(result, 'id') else None
            })
            
        except Exception as e:
            logger.error(f"Error enviando por {channel.value}: {str(e)}")
            results.append({
                'user_id': user_id,
                'channel': channel.value,
                'error': str(e)
            })
    
    return results


def _group_notifications_for_digest(notifications: list[Notification]) -> dict[str, list[dict[str, Any]]]:
    """Agrupa notificaciones para digest"""
    grouped = {}
    
    for notification in notifications:
        notification_type = notification.notification_type.value
        if notification_type not in grouped:
            grouped[notification_type] = []
        
        grouped[notification_type].append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'created_at': format_datetime(notification.created_at),
            'action_url': notification.action_url
        })
    
    return grouped


def _get_weekly_user_stats(user_id: int, week_start: datetime) -> dict[str, Any]:
    """Obtiene estadísticas semanales del usuario"""
    # Implementar lógica para obtener estadísticas
    return {
        'meetings_attended': 0,
        'mentorship_sessions': 0,
        'projects_updated': 0,
        'notifications_received': 0,
        'messages_sent': 0
    }


def _has_significant_weekly_activity(stats: dict[str, Any]) -> bool:
    """Verifica si hay actividad significativa en la semana"""
    total_activity = sum(stats.values())
    return total_activity > 2  # Umbral mínimo de actividad


def _generate_weekly_summary_message(stats: dict[str, Any]) -> str:
    """Genera mensaje de resumen semanal"""
    activities = []
    
    if stats['meetings_attended'] > 0:
        activities.append(f"{stats['meetings_attended']} reuniones")
    if stats['mentorship_sessions'] > 0:
        activities.append(f"{stats['mentorship_sessions']} sesiones de mentoría")
    if stats['projects_updated'] > 0:
        activities.append(f"{stats['projects_updated']} proyectos actualizados")
    
    if activities:
        return f"Esta semana tuviste: {', '.join(activities)}"
    else:
        return "Semana tranquila. ¡La próxima será más activa!"


def _get_user_preferred_channels(user_id: int) -> list[NotificationChannel]:
    """Obtiene canales preferidos del usuario en orden de prioridad"""
    user = User.query.get(user_id)
    if not user:
        return [NotificationChannel.IN_APP]
    
    preferences = user.notification_preferences or {}
    channels = []
    
    if preferences.get('push_notifications', True):
        channels.append(NotificationChannel.PUSH)
    if preferences.get('websocket_notifications', True):
        channels.append(NotificationChannel.WEBSOCKET)
    if preferences.get('in_app_notifications', True):
        channels.append(NotificationChannel.IN_APP)
    
    return channels or [NotificationChannel.IN_APP]


# Funciones auxiliares para notificaciones pendientes
def _send_firebase_notification_for_pending(notification: Notification) -> dict[str, Any]:
    """Envía notificación Firebase para notificación pendiente"""
    # Implementar lógica específica
    return {'success': False, 'error': 'Not implemented'}


def _send_websocket_notification_for_pending(notification: Notification) -> dict[str, Any]:
    """Envía notificación WebSocket para notificación pendiente"""
    # Implementar lógica específica
    return {'success': False, 'error': 'Not implemented'}


def _send_sms_notification_for_pending(notification: Notification) -> dict[str, Any]:
    """Envía notificación SMS para notificación pendiente"""
    # Implementar lógica específica
    return {'success': False, 'error': 'Not implemented'}


# Exportar tareas principales
__all__ = [
    'send_push_notification',
    'send_websocket_notification',
    'send_sms_notification',
    'send_in_app_notification',
    'send_meeting_notification',
    'send_mentorship_notification',
    'send_project_notification',
    'send_daily_notification_digest',
    'send_weekly_notification_summary',
    'process_notification_queue',
    'cleanup_old_notifications',
    'send_slack_notification',
    'NotificationTemplate',
    'NotificationPayload',
    'NotificationContext'
]