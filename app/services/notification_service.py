"""
Notification Service - Ecosistema de Emprendimiento
Servicio completo de notificaciones multi-canal con plantillas, colas y tracking

Author: jusga
Version: 1.0.0
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from flask import current_app, render_template_string
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
from celery import Celery

from app.extensions import db, cache, socketio, redis_client
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ExternalServiceError
)
from app.core.constants import (
    NOTIFICATION_TYPES,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_PRIORITIES,
    USER_ROLES
)
from app.models.user import User
from app.models.notification import Notification, NotificationTemplate, NotificationPreference
from app.models.activity_log import ActivityLog
from app.services.base import BaseService
from app.services.email import EmailService
from app.services.sms import SMSService
from app.utils.decorators import log_activity, retry_on_failure
from app.utils.validators import validate_email, validate_phone
from app.utils.formatters import format_datetime, truncate_text
from app.utils.crypto_utils import encrypt_data, decrypt_data


logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Canales de notificación"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationPriority(Enum):
    """Prioridades de notificación"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class NotificationStatus(Enum):
    """Estados de notificación"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(Enum):
    """Tipos de notificación del sistema"""
    # Autenticación y seguridad
    WELCOME = "welcome"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    LOGIN_ALERT = "login_alert"
    SECURITY_ALERT = "security_alert"
    
    # Proyectos
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_APPROVED = "project_approved"
    PROJECT_REJECTED = "project_rejected"
    PROJECT_COMPLETED = "project_completed"
    PROJECT_REVIEW_NEEDED = "project_review_needed"
    
    # Mentoría
    MENTORSHIP_REQUEST = "mentorship_request"
    MENTORSHIP_ACCEPTED = "mentorship_accepted"
    MENTORSHIP_DECLINED = "mentorship_declined"
    MENTORSHIP_SESSION_SCHEDULED = "mentorship_session_scheduled"
    MENTORSHIP_SESSION_REMINDER = "mentorship_session_reminder"
    
    # Reuniones
    MEETING_SCHEDULED = "meeting_scheduled"
    MEETING_REMINDER = "meeting_reminder"
    MEETING_CANCELLED = "meeting_cancelled"
    MEETING_UPDATED = "meeting_updated"
    
    # Tareas
    TASK_ASSIGNED = "task_assigned"
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"
    TASK_COMPLETED = "task_completed"
    
    # Sistema
    SYSTEM_MAINTENANCE = "system_maintenance"
    FEATURE_ANNOUNCEMENT = "feature_announcement"
    PAYMENT_REMINDER = "payment_reminder"
    PAYMENT_FAILED = "payment_failed"


@dataclass
class NotificationData:
    """Datos de notificación"""
    recipient_id: int
    type: str
    title: str
    message: str
    channel: str = NotificationChannel.IN_APP.value
    priority: str = NotificationPriority.MEDIUM.value
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


@dataclass
class NotificationResult:
    """Resultado de envío de notificación"""
    success: bool
    notification_id: Optional[int] = None
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    channel_results: Optional[Dict[str, bool]] = None


@dataclass
class BulkNotificationResult:
    """Resultado de envío masivo"""
    total_sent: int
    successful: int
    failed: int
    errors: List[str]
    notification_ids: List[int]


class NotificationProvider(ABC):
    """Proveedor abstracto de notificaciones"""
    
    @abstractmethod
    async def send(self, notification: Notification) -> NotificationResult:
        """Enviar notificación"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validar configuración del proveedor"""
        pass


class EmailNotificationProvider(NotificationProvider):
    """Proveedor de notificaciones por email"""
    
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Enviar notificación por email"""
        try:
            user = notification.recipient
            
            if not validate_email(user.email):
                return NotificationResult(
                    success=False,
                    error_message="Email inválido"
                )
            
            # Renderizar plantilla si existe
            if notification.template:
                subject = self._render_template(
                    notification.template.subject_template,
                    notification.data or {}
                )
                body = self._render_template(
                    notification.template.body_template,
                    notification.data or {}
                )
            else:
                subject = notification.title
                body = notification.message
            
            # Enviar email
            result = await self.email_service.send_async(
                to=user.email,
                subject=subject,
                body=body,
                template_data=notification.data
            )
            
            return NotificationResult(
                success=result.success,
                external_id=result.message_id,
                error_message=result.error if not result.success else None
            )
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_config(self) -> bool:
        """Validar configuración del email"""
        return self.email_service.is_configured()
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Renderizar plantilla con datos"""
        try:
            return render_template_string(template, **data)
        except Exception as e:
            logger.error(f"Error renderizando plantilla: {str(e)}")
            return template


class SMSNotificationProvider(NotificationProvider):
    """Proveedor de notificaciones por SMS"""
    
    def __init__(self, sms_service: SMSService):
        self.sms_service = sms_service
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Enviar notificación por SMS"""
        try:
            user = notification.recipient
            
            if not user.phone or not validate_phone(user.phone):
                return NotificationResult(
                    success=False,
                    error_message="Teléfono inválido"
                )
            
            # Limitar mensaje para SMS
            message = truncate_text(notification.message, 160)
            
            result = await self.sms_service.send_async(
                to=user.phone,
                message=message
            )
            
            return NotificationResult(
                success=result.success,
                external_id=result.message_id,
                error_message=result.error if not result.success else None
            )
            
        except Exception as e:
            logger.error(f"Error enviando SMS: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_config(self) -> bool:
        """Validar configuración del SMS"""
        return self.sms_service.is_configured()


class PushNotificationProvider(NotificationProvider):
    """Proveedor de notificaciones push"""
    
    def __init__(self):
        self.fcm_key = current_app.config.get('FCM_SERVER_KEY')
        self.vapid_keys = current_app.config.get('VAPID_KEYS')
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Enviar notificación push"""
        try:
            # Implementar envío de push notification
            # Esto se integraría con Firebase Cloud Messaging o similar
            
            push_tokens = self._get_user_push_tokens(notification.recipient_id)
            
            if not push_tokens:
                return NotificationResult(
                    success=False,
                    error_message="No hay tokens de push disponibles"
                )
            
            payload = {
                'title': notification.title,
                'body': notification.message,
                'data': notification.data or {},
                'icon': '/static/img/notification-icon.png',
                'badge': '/static/img/badge-icon.png'
            }
            
            # Enviar a todos los tokens del usuario
            results = []
            for token in push_tokens:
                result = await self._send_to_token(token, payload)
                results.append(result)
            
            success = any(results)
            
            return NotificationResult(
                success=success,
                error_message=None if success else "Falló el envío a todos los tokens"
            )
            
        except Exception as e:
            logger.error(f"Error enviando push: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_config(self) -> bool:
        """Validar configuración push"""
        return bool(self.fcm_key or self.vapid_keys)
    
    def _get_user_push_tokens(self, user_id: int) -> List[str]:
        """Obtener tokens de push del usuario"""
        # Implementar obtención de tokens desde base de datos
        return []
    
    async def _send_to_token(self, token: str, payload: Dict[str, Any]) -> bool:
        """Enviar notificación a un token específico"""
        # Implementar envío real a FCM/APNS
        return True


class WebSocketNotificationProvider(NotificationProvider):
    """Proveedor de notificaciones en tiempo real via WebSocket"""
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Enviar notificación via WebSocket"""
        try:
            # Emitir notificación al usuario específico
            socketio.emit(
                'notification',
                {
                    'id': notification.id,
                    'type': notification.type,
                    'title': notification.title,
                    'message': notification.message,
                    'priority': notification.priority,
                    'data': notification.data,
                    'created_at': notification.created_at.isoformat()
                },
                room=f"user_{notification.recipient_id}"
            )
            
            return NotificationResult(success=True)
            
        except Exception as e:
            logger.error(f"Error enviando WebSocket: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_config(self) -> bool:
        """Validar configuración WebSocket"""
        return socketio is not None


class NotificationService(BaseService):
    """
    Servicio completo de notificaciones multi-canal
    
    Funcionalidades:
    - Envío multi-canal (email, SMS, push, WebSocket)
    - Sistema de plantillas dinámicas
    - Colas asíncronas con Celery
    - Preferencias de usuario
    - Retry automático para fallos
    - Tracking de entrega y lectura
    - Notificaciones programadas
    - Envío masivo optimizado
    - Analytics de notificaciones
    """
    
    def __init__(self):
        super().__init__()
        self.model = Notification
        self._providers = None
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    @property
    def providers(self) -> Dict[str, NotificationProvider]:
        """Lazy initialization of providers"""
        if self._providers is None:
            self._providers = self._initialize_providers()
        return self._providers
    
    def _initialize_providers(self) -> Dict[str, NotificationProvider]:
        """Inicializar proveedores de notificación"""
        from app.services.email import EmailService
        from app.services.sms import SMSService
        
        providers = {
            NotificationChannel.EMAIL.value: EmailNotificationProvider(EmailService()),
            NotificationChannel.SMS.value: SMSNotificationProvider(SMSService()),
            NotificationChannel.PUSH.value: PushNotificationProvider(),
            NotificationChannel.IN_APP.value: WebSocketNotificationProvider()
        }
        
        # Validar configuraciones
        for channel, provider in providers.items():
            if not provider.validate_config():
                logger.warning(f"Proveedor {channel} no está configurado correctamente")
        
        return providers
    
    @log_activity("notification_sent", "Notification sent to user")
    def send_notification(
        self,
        user_id: int,
        type: str,
        title: str,
        message: str,
        channel: str = NotificationChannel.IN_APP.value,
        priority: str = NotificationPriority.MEDIUM.value,
        data: Optional[Dict[str, Any]] = None,
        template_id: Optional[int] = None,
        scheduled_for: Optional[datetime] = None,
        auto_channels: bool = True
    ) -> NotificationResult:
        """
        Enviar notificación a un usuario
        
        Args:
            user_id: ID del usuario destinatario
            type: Tipo de notificación
            title: Título de la notificación
            message: Mensaje de la notificación
            channel: Canal específico (opcional si auto_channels=True)
            priority: Prioridad de la notificación
            data: Datos adicionales
            template_id: ID de plantilla a usar
            scheduled_for: Fecha/hora programada
            auto_channels: Usar preferencias del usuario para elegir canales
            
        Returns:
            NotificationResult: Resultado del envío
        """
        try:
            # Validar usuario
            user = User.query.filter_by(id=user_id, is_active=True).first()
            if not user:
                raise NotFoundError(f"Usuario {user_id} no encontrado")
            
            # Determinar canales a usar
            channels = self._determine_channels(user_id, type, channel, auto_channels)
            
            # Crear notificación en base de datos
            notification = self._create_notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                priority=priority,
                data=data,
                template_id=template_id,
                scheduled_for=scheduled_for
            )
            
            # Si es programada, encolar para más tarde
            if scheduled_for and scheduled_for > datetime.utcnow():
                self._schedule_notification(notification, channels)
                return NotificationResult(
                    success=True,
                    notification_id=notification.id
                )
            
            # Enviar inmediatamente
            return self._send_to_channels(notification, channels)
            
        except Exception as e:
            logger.error(f"Error enviando notificación: {str(e)}")
            raise BusinessLogicError(f"Error enviando notificación: {str(e)}")
    
    def send_bulk_notification(
        self,
        user_ids: List[int],
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        template_id: Optional[int] = None,
        batch_size: int = 100
    ) -> BulkNotificationResult:
        """
        Enviar notificaciones masivas de forma optimizada
        
        Args:
            user_ids: Lista de IDs de usuarios
            type: Tipo de notificación
            title: Título
            message: Mensaje
            data: Datos adicionales
            template_id: ID de plantilla
            batch_size: Tamaño del lote para procesamiento
            
        Returns:
            BulkNotificationResult: Resultado del envío masivo
        """
        total_sent = 0
        successful = 0
        failed = 0
        errors = []
        notification_ids = []
        
        try:
            # Procesar en lotes para evitar sobrecarga
            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i:i + batch_size]
                
                # Crear notificaciones en lote
                notifications = self._create_bulk_notifications(
                    user_ids=batch,
                    type=type,
                    title=title,
                    message=message,
                    data=data,
                    template_id=template_id
                )
                
                # Encolar para envío asíncrono
                for notification in notifications:
                    try:
                        self._queue_notification_async(notification.id)
                        successful += 1
                        notification_ids.append(notification.id)
                    except Exception as e:
                        failed += 1
                        errors.append(f"Usuario {notification.recipient_id}: {str(e)}")
                
                total_sent += len(batch)
            
            logger.info(f"Envío masivo completado: {successful}/{total_sent} exitosos")
            
            return BulkNotificationResult(
                total_sent=total_sent,
                successful=successful,
                failed=failed,
                errors=errors,
                notification_ids=notification_ids
            )
            
        except Exception as e:
            logger.error(f"Error en envío masivo: {str(e)}")
            raise BusinessLogicError(f"Error en envío masivo: {str(e)}")
    
    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        types: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Notification], int]:
        """
        Obtener notificaciones de un usuario
        
        Args:
            user_id: ID del usuario
            unread_only: Solo notificaciones no leídas
            types: Filtrar por tipos específicos
            page: Número de página
            per_page: Notificaciones por página
            
        Returns:
            Tuple[List[Notification], int]: Notificaciones y total
        """
        query = Notification.query.filter_by(recipient_id=user_id)
        
        if unread_only:
            query = query.filter_by(read_at=None)
        
        if types:
            query = query.filter(Notification.type.in_(types))
        
        query = query.order_by(desc(Notification.created_at))
        
        total = query.count()
        notifications = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return notifications, total
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """
        Marcar notificación como leída
        
        Args:
            notification_id: ID de la notificación
            user_id: ID del usuario (verificación de permisos)
            
        Returns:
            bool: True si se marcó correctamente
        """
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                recipient_id=user_id
            ).first()
            
            if not notification:
                raise NotFoundError("Notificación no encontrada")
            
            if notification.read_at is None:
                notification.read_at = datetime.utcnow()
                notification.status = NotificationStatus.READ.value
                
                db.session.commit()
                
                # Emitir evento en tiempo real
                socketio.emit(
                    'notification_read',
                    {'notification_id': notification_id},
                    room=f"user_{user_id}"
                )
            
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error marcando notificación como leída: {str(e)}")
            return False
    
    def mark_all_as_read(self, user_id: int) -> int:
        """
        Marcar todas las notificaciones como leídas
        
        Args:
            user_id: ID del usuario
            
        Returns:
            int: Número de notificaciones marcadas
        """
        try:
            count = Notification.query.filter_by(
                recipient_id=user_id,
                read_at=None
            ).update({
                'read_at': datetime.utcnow(),
                'status': NotificationStatus.READ.value
            })
            
            db.session.commit()
            
            # Emitir evento en tiempo real
            socketio.emit(
                'all_notifications_read',
                {'count': count},
                room=f"user_{user_id}"
            )
            
            return count
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error marcando todas como leídas: {str(e)}")
            return 0
    
    def get_unread_count(self, user_id: int) -> int:
        """
        Obtener cantidad de notificaciones no leídas
        
        Args:
            user_id: ID del usuario
            
        Returns:
            int: Cantidad de notificaciones no leídas
        """
        return Notification.query.filter_by(
            recipient_id=user_id,
            read_at=None
        ).count()
    
    def create_template(
        self,
        name: str,
        type: str,
        subject_template: str,
        body_template: str,
        channels: List[str],
        variables: Optional[List[str]] = None,
        is_active: bool = True
    ) -> NotificationTemplate:
        """
        Crear plantilla de notificación
        
        Args:
            name: Nombre de la plantilla
            type: Tipo de notificación
            subject_template: Plantilla del asunto
            body_template: Plantilla del cuerpo
            channels: Canales soportados
            variables: Variables disponibles
            is_active: Si está activa
            
        Returns:
            NotificationTemplate: Plantilla creada
        """
        try:
            template = NotificationTemplate(
                name=name,
                type=type,
                subject_template=subject_template,
                body_template=body_template,
                channels=channels,
                variables=variables or [],
                is_active=is_active,
                created_at=datetime.utcnow()
            )
            
            db.session.add(template)
            db.session.commit()
            
            logger.info(f"Plantilla creada: {template.id}")
            return template
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error creando plantilla: {str(e)}")
            raise BusinessLogicError("Error creando plantilla")
    
    def update_user_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Any]
    ) -> NotificationPreference:
        """
        Actualizar preferencias de notificación del usuario
        
        Args:
            user_id: ID del usuario
            preferences: Preferencias de notificación
            
        Returns:
            NotificationPreference: Preferencias actualizadas
        """
        try:
            pref = NotificationPreference.query.filter_by(
                user_id=user_id
            ).first()
            
            if not pref:
                pref = NotificationPreference(user_id=user_id)
                db.session.add(pref)
            
            # Actualizar preferencias
            for key, value in preferences.items():
                if hasattr(pref, key):
                    setattr(pref, key, value)
            
            pref.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Limpiar cache de preferencias
            cache.delete(f"notification_preferences:{user_id}")
            
            return pref
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando preferencias: {str(e)}")
            raise BusinessLogicError("Error actualizando preferencias")
    
    @cache.memoize(timeout=300)
    def get_user_preferences(self, user_id: int) -> NotificationPreference:
        """
        Obtener preferencias de notificación del usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            NotificationPreference: Preferencias del usuario
        """
        pref = NotificationPreference.query.filter_by(user_id=user_id).first()
        
        if not pref:
            # Crear preferencias por defecto
            pref = self._create_default_preferences(user_id)
        
        return pref
    
    def get_notification_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None,
        type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtener analytics de notificaciones
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            user_id: Filtrar por usuario específico
            type: Filtrar por tipo específico
            
        Returns:
            Dict[str, Any]: Datos de analytics
        """
        query = Notification.query.filter(
            Notification.created_at.between(start_date, end_date)
        )
        
        if user_id:
            query = query.filter_by(recipient_id=user_id)
        
        if type:
            query = query.filter_by(type=type)
        
        # Métricas básicas
        total_sent = query.count()
        total_read = query.filter(Notification.read_at.isnot(None)).count()
        total_failed = query.filter_by(status=NotificationStatus.FAILED.value).count()
        
        # Métricas por canal
        channel_stats = db.session.query(
            Notification.channel,
            func.count(Notification.id).label('count')
        ).filter(
            Notification.created_at.between(start_date, end_date)
        ).group_by(Notification.channel).all()
        
        # Métricas por tipo
        type_stats = db.session.query(
            Notification.type,
            func.count(Notification.id).label('count')
        ).filter(
            Notification.created_at.between(start_date, end_date)
        ).group_by(Notification.type).all()
        
        # Tasa de lectura
        read_rate = (total_read / total_sent * 100) if total_sent > 0 else 0
        
        return {
            'summary': {
                'total_sent': total_sent,
                'total_read': total_read,
                'total_failed': total_failed,
                'read_rate': round(read_rate, 2)
            },
            'by_channel': {stat.channel: stat.count for stat in channel_stats},
            'by_type': {stat.type: stat.count for stat in type_stats},
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    # Métodos privados
    def _create_notification(
        self,
        user_id: int,
        type: str,
        title: str,
        message: str,
        priority: str,
        data: Optional[Dict[str, Any]],
        template_id: Optional[int],
        scheduled_for: Optional[datetime]
    ) -> Notification:
        """Crear notificación en base de datos"""
        notification = Notification(
            recipient_id=user_id,
            type=type,
            title=title,
            message=message,
            priority=priority,
            data=data,
            template_id=template_id,
            scheduled_for=scheduled_for,
            status=NotificationStatus.PENDING.value,
            created_at=datetime.utcnow()
        )
        
        db.session.add(notification)
        db.session.flush()  # Para obtener el ID
        
        return notification
    
    def _determine_channels(
        self,
        user_id: int,
        type: str,
        default_channel: str,
        auto_channels: bool
    ) -> List[str]:
        """Determinar canales a usar basado en preferencias"""
        if not auto_channels:
            return [default_channel]
        
        preferences = self.get_user_preferences(user_id)
        
        # Lógica para determinar canales basado en:
        # - Preferencias del usuario
        # - Tipo de notificación
        # - Prioridad
        # - Horario (no molestar)
        
        channels = [NotificationChannel.IN_APP.value]  # Siempre incluir in-app
        
        # Email para notificaciones importantes
        if preferences.email_enabled and type in [
            NotificationType.PROJECT_APPROVED.value,
            NotificationType.MENTORSHIP_SESSION_SCHEDULED.value,
            NotificationType.PASSWORD_RESET.value
        ]:
            channels.append(NotificationChannel.EMAIL.value)
        
        # SMS para notificaciones críticas
        if preferences.sms_enabled and type in [
            NotificationType.SECURITY_ALERT.value,
            NotificationType.EMERGENCY.value
        ]:
            channels.append(NotificationChannel.SMS.value)
        
        # Push para recordatorios
        if preferences.push_enabled and type in [
            NotificationType.MEETING_REMINDER.value,
            NotificationType.TASK_DUE_SOON.value
        ]:
            channels.append(NotificationChannel.PUSH.value)
        
        return list(set(channels))  # Eliminar duplicados
    
    def _send_to_channels(
        self,
        notification: Notification,
        channels: List[str]
    ) -> NotificationResult:
        """Enviar notificación a múltiples canales"""
        results = {}
        overall_success = False
        
        for channel in channels:
            if channel in self.providers:
                try:
                    # Crear copia de notificación para el canal específico
                    channel_notification = self._clone_notification_for_channel(
                        notification, channel
                    )
                    
                    result = asyncio.run(
                        self.providers[channel].send(channel_notification)
                    )
                    
                    results[channel] = result.success
                    
                    if result.success:
                        overall_success = True
                        
                    # Actualizar estado en base de datos
                    self._update_notification_status(
                        channel_notification.id,
                        NotificationStatus.SENT.value if result.success else NotificationStatus.FAILED.value,
                        result.external_id,
                        result.error_message
                    )
                    
                except Exception as e:
                    logger.error(f"Error enviando por {channel}: {str(e)}")
                    results[channel] = False
        
        db.session.commit()
        
        return NotificationResult(
            success=overall_success,
            notification_id=notification.id,
            channel_results=results
        )
    
    def _clone_notification_for_channel(
        self,
        notification: Notification,
        channel: str
    ) -> Notification:
        """Crear copia de notificación para canal específico"""
        channel_notification = Notification(
            recipient_id=notification.recipient_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            channel=channel,
            priority=notification.priority,
            data=notification.data,
            template_id=notification.template_id,
            parent_id=notification.id,
            status=NotificationStatus.SENDING.value,
            created_at=datetime.utcnow()
        )
        
        db.session.add(channel_notification)
        db.session.flush()
        
        return channel_notification
    
    def _update_notification_status(
        self,
        notification_id: int,
        status: str,
        external_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Actualizar estado de notificación"""
        notification = Notification.query.get(notification_id)
        if notification:
            notification.status = status
            notification.external_id = external_id
            notification.error_message = error_message
            
            if status == NotificationStatus.SENT.value:
                notification.sent_at = datetime.utcnow()
            elif status == NotificationStatus.DELIVERED.value:
                notification.delivered_at = datetime.utcnow()
    
    def _create_default_preferences(self, user_id: int) -> NotificationPreference:
        """Crear preferencias por defecto para usuario"""
        pref = NotificationPreference(
            user_id=user_id,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=True,
            in_app_enabled=True,
            quiet_hours_start=22,  # 10 PM
            quiet_hours_end=8,     # 8 AM
            timezone='America/Bogota',
            frequency_limit=10,    # Máximo 10 notificaciones por hora
            created_at=datetime.utcnow()
        )
        
        db.session.add(pref)
        db.session.commit()
        
        return pref
    
    @retry_on_failure(max_retries=3, delay=60)
    def _queue_notification_async(self, notification_id: int) -> None:
        """Encolar notificación para envío asíncrono"""
        from app.tasks.notification_tasks import send_notification_task
        
        send_notification_task.delay(notification_id)
    
    def _schedule_notification(
        self,
        notification: Notification,
        channels: List[str]
    ) -> None:
        """Programar notificación para envío futuro"""
        from app.tasks.notification_tasks import send_scheduled_notification_task
        
        # Calcular delay hasta la fecha programada
        delay = (notification.scheduled_for - datetime.utcnow()).total_seconds()
        
        send_scheduled_notification_task.apply_async(
            args=[notification.id, channels],
            countdown=delay
        )
        
        notification.status = NotificationStatus.QUEUED.value
        db.session.commit()
    
    def _create_bulk_notifications(
        self,
        user_ids: List[int],
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]],
        template_id: Optional[int]
    ) -> List[Notification]:
        """Crear notificaciones en lote"""
        notifications = []
        
        for user_id in user_ids:
            notification = Notification(
                recipient_id=user_id,
                type=type,
                title=title,
                message=message,
                data=data,
                template_id=template_id,
                status=NotificationStatus.PENDING.value,
                created_at=datetime.utcnow()
            )
            notifications.append(notification)
        
        db.session.add_all(notifications)
        db.session.commit()
        
        return notifications

    def _perform_initialization(self) -> bool:
        """Initialize the notification service."""
        try:
            # Initialize providers
            self.providers = self._initialize_providers()
            logger.info("Notification service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing notification service: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """Check health of notification service."""
        return {
            'service': 'notification_service',
            'status': 'healthy',
            'providers': len(self.providers),
            'timestamp': datetime.utcnow().isoformat()
        }


# Instancia del servicio para uso global (initialized within app context)
notification_service = None

def get_notification_service():
    """Get notification service instance, initializing if needed."""
    global notification_service
    if notification_service is None:
        notification_service = NotificationService()
    return notification_service


# Funciones de conveniencia para uso rápido
def send_welcome_notification(user_id: int) -> NotificationResult:
    """Enviar notificación de bienvenida"""
    return get_notification_service().send_notification(
        user_id=user_id,
        type=NotificationType.WELCOME.value,
        title="¡Bienvenido al Ecosistema de Emprendimiento!",
        message="Gracias por unirte a nuestra plataforma. Comienza explorando las oportunidades disponibles.",
        auto_channels=True
    )


def send_project_update_notification(
    project_id: int,
    users_ids: List[int],
    changes: List[str]
) -> BulkNotificationResult:
    """Enviar notificación de actualización de proyecto"""
    return get_notification_service().send_bulk_notification(
        user_ids=users_ids,
        type=NotificationType.PROJECT_UPDATED.value,
        title="Proyecto actualizado",
        message=f"El proyecto ha sido actualizado. Cambios: {', '.join(changes)}",
        data={'project_id': project_id, 'changes': changes}
    )


def send_meeting_reminder(meeting_id: int, user_id: int, meeting_title: str, start_time: datetime) -> NotificationResult:
    """Enviar recordatorio de reunión"""
    return get_notification_service().send_notification(
        user_id=user_id,
        type=NotificationType.MEETING_REMINDER.value,
        title="Recordatorio de reunión",
        message=f"Tu reunión '{meeting_title}' comienza en 15 minutos",
        data={
            'meeting_id': meeting_id,
            'start_time': start_time.isoformat()
        },
        priority=NotificationPriority.HIGH.value,
        auto_channels=True
    )