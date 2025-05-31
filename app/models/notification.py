"""
Modelo Notificación del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de notificaciones y alertas,
incluyendo notificaciones push, email, SMS, y notificaciones en tiempo real.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
import json

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    NOTIFICATION_TYPES,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_PRIORITIES,
    DELIVERY_STATUS,
    TRIGGER_TYPES,
    FREQUENCY_TYPES
)
from ..core.exceptions import ValidationError


class NotificationType(Enum):
    """Tipos de notificación"""
    SYSTEM = "system"
    TASK_REMINDER = "task_reminder"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_OVERDUE = "task_overdue"
    MEETING_REMINDER = "meeting_reminder"
    MEETING_INVITED = "meeting_invited"
    MEETING_CANCELLED = "meeting_cancelled"
    PROJECT_UPDATE = "project_update"
    PROJECT_MILESTONE = "project_milestone"
    MENTORSHIP_SESSION = "mentorship_session"
    MENTORSHIP_REQUEST = "mentorship_request"
    PROGRAM_APPLICATION = "program_application"
    PROGRAM_ACCEPTED = "program_accepted"
    PROGRAM_DEADLINE = "program_deadline"
    DOCUMENT_SHARED = "document_shared"
    DOCUMENT_COMMENT = "document_comment"
    MESSAGE_RECEIVED = "message_received"
    MENTION = "mention"
    FOLLOW_UP = "follow_up"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    FUNDING_OPPORTUNITY = "funding_opportunity"
    PARTNERSHIP_REQUEST = "partnership_request"
    EVENT_INVITATION = "event_invitation"
    DEADLINE_APPROACHING = "deadline_approaching"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    SECURITY_ALERT = "security_alert"
    PAYMENT_DUE = "payment_due"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    NEWSLETTER = "newsletter"
    PROMOTIONAL = "promotional"
    EMERGENCY = "emergency"


class NotificationChannel(Enum):
    """Canales de notificación"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class NotificationPriority(Enum):
    """Prioridades de notificación"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class DeliveryStatus(Enum):
    """Estados de entrega"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TriggerType(Enum):
    """Tipos de disparador"""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"
    EVENT_BASED = "event_based"
    CONDITION_BASED = "condition_based"


class FrequencyType(Enum):
    """Tipos de frecuencia"""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


# Tabla de asociación para destinatarios de notificación
notification_recipients = Table(
    'notification_recipients',
    Column('notification_id', Integer, ForeignKey('notifications.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('channel', String(50)),
    Column('delivery_status', String(50), default='pending'),
    Column('sent_at', DateTime),
    Column('delivered_at', DateTime),
    Column('read_at', DateTime),
    Column('failed_reason', String(500)),
    Column('retry_count', Integer, default=0),
    Column('external_id', String(200)),  # ID del proveedor externo
    Column('metadata', JSON),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Notification(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Notificación
    
    Representa notificaciones en el ecosistema de emprendimiento
    con soporte para múltiples canales y configuraciones avanzadas.
    """
    
    __tablename__ = 'notifications'
    
    # Información básica
    title = Column(String(300), nullable=False, index=True)
    message = Column(Text, nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL, index=True)
    
    # Remitente (puede ser nulo para notificaciones del sistema)
    sender_id = Column(Integer, ForeignKey('users.id'), index=True)
    sender = relationship("User", foreign_keys=[sender_id])
    
    # Canales de entrega
    channels = Column(JSON, nullable=False)  # Lista de canales a usar
    
    # Programación y disparadores
    trigger_type = Column(SQLEnum(TriggerType), default=TriggerType.IMMEDIATE)
    scheduled_at = Column(DateTime, index=True)
    expires_at = Column(DateTime)
    
    # Configuración de recurrencia
    is_recurring = Column(Boolean, default=False, index=True)
    frequency_type = Column(SQLEnum(FrequencyType))
    frequency_settings = Column(JSON)  # Configuración detallada de frecuencia
    parent_notification_id = Column(Integer, ForeignKey('notifications.id'))
    next_occurrence_at = Column(DateTime)
    
    # Contenido enriquecido
    content_html = Column(Text)  # Versión HTML del mensaje
    content_data = Column(JSON)  # Datos estructurados para templates
    template_name = Column(String(100))  # Nombre del template a usar
    
    # Enlaces y acciones
    action_url = Column(String(1000))  # URL de acción principal
    action_text = Column(String(100))  # Texto del botón de acción
    deep_link = Column(String(1000))  # Deep link para apps móviles
    actions = Column(JSON)  # Acciones adicionales (botones, links)
    
    # Personalización
    image_url = Column(String(1000))  # Imagen de la notificación
    icon = Column(String(100))  # Icono de la notificación
    color = Column(String(7))  # Color hex
    sound = Column(String(100))  # Sonido personalizado
    
    # Segmentación y targeting
    target_criteria = Column(JSON)  # Criterios de segmentación
    target_count = Column(Integer, default=0)  # Número de destinatarios objetivo
    
    # Estado de la campaña
    status = Column(String(50), default='draft', index=True)  # draft, scheduled, sending, sent, completed, cancelled
    
    # Estadísticas de entrega
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_read = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    delivery_rate = Column(Float, default=0.0)
    read_rate = Column(Float, default=0.0)
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    
    task_id = Column(Integer, ForeignKey('tasks.id'))
    task = relationship("Task")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship("Client")
    
    document_id = Column(Integer, ForeignKey('documents.id'))
    document = relationship("Document")
    
    # Configuración A/B Testing
    ab_test_group = Column(String(50))  # Grupo de prueba A/B
    ab_test_variant = Column(String(50))  # Variante específica
    
    # Configuración de privacidad
    is_confidential = Column(Boolean, default=False)
    requires_read_receipt = Column(Boolean, default=False)
    auto_delete_after_days = Column(Integer)
    
    # Metadatos y contexto
    context_data = Column(JSON)  # Datos de contexto adicionales
    tracking_data = Column(JSON)  # Datos para tracking y analytics
    external_reference = Column(String(200))  # Referencia externa
    
    # Relaciones
    
    # Destinatarios
    recipients = relationship("User",
                            secondary=notification_recipients,
                            back_populates="notifications_received")
    
    # Actividades relacionadas
    activities = relationship("ActivityLog", back_populates="notification")
    
    def __init__(self, **kwargs):
        """Inicialización de la notificación"""
        super().__init__(**kwargs)
        
        # Configurar canales por defecto si no se especifican
        if not self.channels:
            self.channels = ['in_app']
        
        # Configurar programación por defecto
        if self.trigger_type == TriggerType.IMMEDIATE and not self.scheduled_at:
            self.scheduled_at = datetime.utcnow()
        
        # Configurar expiración por defecto (30 días)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=30)
    
    def __repr__(self):
        return f'<Notification {self.title} ({self.notification_type.value})>'
    
    def __str__(self):
        return f'{self.title} - {self.notification_type.value} ({self.priority.value})'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título de la notificación"""
        if not title or len(title.strip()) < 1:
            raise ValidationError("El título es requerido")
        if len(title) > 300:
            raise ValidationError("El título no puede exceder 300 caracteres")
        return title.strip()
    
    @validates('message')
    def validate_message(self, key, message):
        """Validar mensaje de la notificación"""
        if not message or len(message.strip()) < 1:
            raise ValidationError("El mensaje es requerido")
        if len(message) > 10000:
            raise ValidationError("El mensaje no puede exceder 10,000 caracteres")
        return message.strip()
    
    @validates('channels')
    def validate_channels(self, key, channels):
        """Validar canales de notificación"""
        if not channels or len(channels) == 0:
            raise ValidationError("Al menos un canal es requerido")
        
        if not isinstance(channels, list):
            raise ValidationError("Los canales deben ser una lista")
        
        valid_channels = [channel.value for channel in NotificationChannel]
        for channel in channels:
            if channel not in valid_channels:
                raise ValidationError(f"Canal inválido: {channel}")
        
        return channels
    
    @validates('action_url', 'deep_link')
    def validate_urls(self, key, url):
        """Validar URLs"""
        if url:
            # Validación básica de URL
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            # Para deep links, permitir esquemas personalizados
            if key == 'deep_link':
                deep_link_pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://\S+$')
                if not url_pattern.match(url) and not deep_link_pattern.match(url):
                    raise ValidationError("Deep link inválido")
            else:
                if not url_pattern.match(url):
                    raise ValidationError("URL inválida")
        
        return url
    
    @validates('color')
    def validate_color(self, key, color):
        """Validar color hex"""
        if color:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                raise ValidationError("Color debe ser un valor hex válido (#RRGGBB)")
        return color
    
    @validates('auto_delete_after_days')
    def validate_auto_delete(self, key, days):
        """Validar días de auto-eliminación"""
        if days is not None:
            if days < 1 or days > 365:
                raise ValidationError("Los días de auto-eliminación deben estar entre 1 y 365")
        return days
    
    # Propiedades híbridas
    @hybrid_property
    def is_scheduled(self):
        """Verificar si está programada"""
        return self.scheduled_at and self.scheduled_at > datetime.utcnow()
    
    @hybrid_property
    def is_expired(self):
        """Verificar si está vencida"""
        return self.expires_at and self.expires_at < datetime.utcnow()
    
    @hybrid_property
    def is_sent(self):
        """Verificar si ya fue enviada"""
        return self.status in ['sent', 'completed']
    
    @hybrid_property
    def is_ready_to_send(self):
        """Verificar si está lista para enviar"""
        return (self.status in ['draft', 'scheduled'] and 
                not self.is_expired and
                self.scheduled_at <= datetime.utcnow())
    
    @hybrid_property
    def recipient_count(self):
        """Número de destinatarios"""
        return len(self.recipients)
    
    @hybrid_property
    def engagement_rate(self):
        """Tasa de engagement (clicks/opens)"""
        if self.total_delivered == 0:
            return 0.0
        # En una implementación real, tendríamos métricas de clicks
        return (self.total_read / self.total_delivered) * 100
    
    @hybrid_property
    def time_until_send(self):
        """Tiempo hasta el envío (en segundos)"""
        if self.scheduled_at:
            return (self.scheduled_at - datetime.utcnow()).total_seconds()
        return 0
    
    @hybrid_property
    def days_until_expire(self):
        """Días hasta expiración"""
        if self.expires_at:
            return (self.expires_at.date() - date.today()).days
        return None
    
    # Métodos de negocio
    def add_recipient(self, user, channels: List[str] = None) -> bool:
        """Agregar destinatario a la notificación"""
        if user in self.recipients:
            return False  # Ya es destinatario
        
        # Verificar canales del usuario
        user_channels = channels or self._get_user_preferred_channels(user)
        
        from .. import db
        
        # Agregar destinatario para cada canal
        for channel in user_channels:
            if channel in self.channels:
                recipient_data = {
                    'notification_id': self.id,
                    'user_id': user.id,
                    'channel': channel,
                    'delivery_status': DeliveryStatus.PENDING.value
                }
                
                db.session.execute(notification_recipients.insert().values(recipient_data))
        
        self.target_count += 1
        return True
    
    def add_recipients_by_criteria(self, criteria: Dict[str, Any]) -> int:
        """Agregar destinatarios basado en criterios"""
        from .user import User
        
        query = User.query.filter(User.is_deleted == False)
        
        # Aplicar criterios de segmentación
        if criteria.get('organization_id'):
            query = query.filter(User.organization_id == criteria['organization_id'])
        
        if criteria.get('user_type'):
            query = query.filter(User.user_type == criteria['user_type'])
        
        if criteria.get('program_id'):
            # Usuarios en un programa específico
            query = query.join(ProgramEnrollment).filter(
                ProgramEnrollment.program_id == criteria['program_id'],
                ProgramEnrollment.status == 'active'
            )
        
        if criteria.get('project_id'):
            # Usuarios relacionados a un proyecto
            query = query.filter(
                (User.id == Project.entrepreneur_id) |
                (User.id.in_(Project.collaborators))
            ).filter(Project.id == criteria['project_id'])
        
        if criteria.get('active_since'):
            query = query.filter(User.last_login_at >= criteria['active_since'])
        
        if criteria.get('notification_preferences'):
            # Filtrar por preferencias de notificación
            pref_key = criteria['notification_preferences']
            query = query.filter(
                User.notification_preferences[pref_key].astext.cast(Boolean) == True
            )
        
        users = query.all()
        added_count = 0
        
        for user in users:
            if self.add_recipient(user):
                added_count += 1
        
        # Guardar criterios para referencia
        self.target_criteria = criteria
        
        return added_count
    
    def _get_user_preferred_channels(self, user) -> List[str]:
        """Obtener canales preferidos del usuario"""
        user_prefs = getattr(user, 'notification_preferences', {}) or {}
        
        preferred_channels = []
        
        # Verificar preferencias por tipo de notificación
        notification_settings = user_prefs.get(self.notification_type.value, {})
        
        if notification_settings.get('in_app', True):
            preferred_channels.append('in_app')
        
        if notification_settings.get('email', True) and user.email:
            preferred_channels.append('email')
        
        if notification_settings.get('sms', False) and user.phone:
            preferred_channels.append('sms')
        
        if notification_settings.get('push', True):
            preferred_channels.append('push')
        
        # Si no hay preferencias específicas, usar configuración general
        if not preferred_channels:
            if user_prefs.get('email_notifications', True):
                preferred_channels.append('email')
            preferred_channels.append('in_app')  # Siempre incluir in-app como fallback
        
        return preferred_channels
    
    def schedule_notification(self, send_at: datetime):
        """Programar notificación para envío futuro"""
        if send_at <= datetime.utcnow():
            raise ValidationError("La fecha de programación debe ser futura")
        
        self.scheduled_at = send_at
        self.trigger_type = TriggerType.SCHEDULED
        self.status = 'scheduled'
        
        self._log_activity('notification_scheduled', f"Programada para {send_at.isoformat()}")
    
    def send_notification(self, force: bool = False) -> Dict[str, Any]:
        """Enviar notificación"""
        if not force and not self.is_ready_to_send:
            raise ValidationError("La notificación no está lista para enviar")
        
        if self.is_expired:
            raise ValidationError("La notificación ha expirado")
        
        self.status = 'sending'
        results = {
            'total_attempted': 0,
            'total_sent': 0,
            'total_failed': 0,
            'errors': []
        }
        
        # Obtener destinatarios pendientes
        from .. import db
        
        pending_recipients = db.session.execute(
            notification_recipients.select().where(
                notification_recipients.c.notification_id == self.id,
                notification_recipients.c.delivery_status == DeliveryStatus.PENDING.value
            )
        ).fetchall()
        
        for recipient_data in pending_recipients:
            try:
                success = self._send_to_recipient(
                    recipient_data.user_id,
                    recipient_data.channel
                )
                
                if success:
                    results['total_sent'] += 1
                    # Actualizar estado del destinatario
                    db.session.execute(
                        notification_recipients.update().where(
                            notification_recipients.c.notification_id == self.id,
                            notification_recipients.c.user_id == recipient_data.user_id,
                            notification_recipients.c.channel == recipient_data.channel
                        ).values(
                            delivery_status=DeliveryStatus.SENT.value,
                            sent_at=datetime.utcnow()
                        )
                    )
                else:
                    results['total_failed'] += 1
                    db.session.execute(
                        notification_recipients.update().where(
                            notification_recipients.c.notification_id == self.id,
                            notification_recipients.c.user_id == recipient_data.user_id,
                            notification_recipients.c.channel == recipient_data.channel
                        ).values(
                            delivery_status=DeliveryStatus.FAILED.value,
                            failed_reason="Error de envío",
                            retry_count=recipient_data.retry_count + 1
                        )
                    )
                
                results['total_attempted'] += 1
                
            except Exception as e:
                results['total_failed'] += 1
                results['errors'].append(f"Error enviando a usuario {recipient_data.user_id}: {str(e)}")
        
        # Actualizar estadísticas
        self.total_sent = results['total_sent']
        self.total_failed = results['total_failed']
        self.delivery_rate = (self.total_sent / results['total_attempted'] * 100) if results['total_attempted'] > 0 else 0
        
        # Actualizar estado
        if results['total_failed'] == 0:
            self.status = 'sent'
        elif results['total_sent'] > 0:
            self.status = 'partially_sent'
        else:
            self.status = 'failed'
        
        self._log_activity('notification_sent', f"Enviada a {results['total_sent']} destinatarios")
        
        return results
    
    def _send_to_recipient(self, user_id: int, channel: str) -> bool:
        """Enviar notificación a un destinatario específico por un canal"""
        from .user import User
        
        user = User.query.get(user_id)
        if not user:
            return False
        
        try:
            if channel == 'in_app':
                return self._send_in_app_notification(user)
            elif channel == 'email':
                return self._send_email_notification(user)
            elif channel == 'sms':
                return self._send_sms_notification(user)
            elif channel == 'push':
                return self._send_push_notification(user)
            elif channel == 'webhook':
                return self._send_webhook_notification(user)
            else:
                return False
                
        except Exception as e:
            print(f"Error enviando notificación {self.id} a usuario {user_id} por {channel}: {e}")
            return False
    
    def _send_in_app_notification(self, user) -> bool:
        """Enviar notificación in-app"""
        # Crear entrada en la bandeja de entrada del usuario
        # En una implementación real, esto se almacenaría en una tabla separada
        user_notification = {
            'notification_id': self.id,
            'user_id': user.id,
            'title': self.title,
            'message': self.message,
            'action_url': self.action_url,
            'is_read': False,
            'created_at': datetime.utcnow()
        }
        
        # También emitir evento en tiempo real vía WebSocket
        self._emit_realtime_notification(user.id, user_notification)
        
        return True
    
    def _send_email_notification(self, user) -> bool:
        """Enviar notificación por email"""
        if not user.email:
            return False
        
        # Preparar datos del email
        email_data = {
            'to': user.email,
            'subject': self.title,
            'html_content': self.content_html or self._generate_email_html(),
            'text_content': self.message,
            'template_name': self.template_name,
            'template_data': self._prepare_template_data(user)
        }
        
        # En producción, usar servicio de email (SendGrid, AWS SES, etc.)
        return self._send_via_email_service(email_data)
    
    def _send_sms_notification(self, user) -> bool:
        """Enviar notificación por SMS"""
        if not user.phone:
            return False
        
        # Preparar mensaje SMS (máximo 160 caracteres)
        sms_message = self.message[:157] + "..." if len(self.message) > 160 else self.message
        
        sms_data = {
            'to': user.phone,
            'message': sms_message
        }
        
        # En producción, usar servicio SMS (Twilio, AWS SNS, etc.)
        return self._send_via_sms_service(sms_data)
    
    def _send_push_notification(self, user) -> bool:
        """Enviar notificación push"""
        # Obtener tokens de dispositivos del usuario
        device_tokens = self._get_user_device_tokens(user.id)
        
        if not device_tokens:
            return False
        
        push_data = {
            'title': self.title,
            'body': self.message,
            'icon': self.icon,
            'image': self.image_url,
            'click_action': self.action_url,
            'sound': self.sound or 'default',
            'data': {
                'notification_id': self.id,
                'type': self.notification_type.value,
                'deep_link': self.deep_link
            }
        }
        
        # En producción, usar servicio push (FCM, APNs, etc.)
        return self._send_via_push_service(device_tokens, push_data)
    
    def _send_webhook_notification(self, user) -> bool:
        """Enviar notificación vía webhook"""
        webhook_url = self._get_user_webhook_url(user.id)
        
        if not webhook_url:
            return False
        
        webhook_data = {
            'notification_id': self.id,
            'user_id': user.id,
            'type': self.notification_type.value,
            'title': self.title,
            'message': self.message,
            'priority': self.priority.value,
            'action_url': self.action_url,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': self.context_data
        }
        
        return self._send_via_webhook(webhook_url, webhook_data)
    
    def _emit_realtime_notification(self, user_id: int, notification_data: Dict[str, Any]):
        """Emitir notificación en tiempo real vía WebSocket"""
        try:
            # En producción, usar Socket.IO, Redis Pub/Sub, etc.
            from ..sockets import socketio
            
            socketio.emit('new_notification', notification_data, room=f'user_{user_id}')
            return True
            
        except Exception as e:
            print(f"Error emitiendo notificación en tiempo real: {e}")
            return False
    
    def _generate_email_html(self) -> str:
        """Generar HTML para email"""
        # Template básico de email
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{self.title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h1 style="color: #333;">{self.title}</h1>
                <p style="color: #666; line-height: 1.6;">{self.message}</p>
                {f'<a href="{self.action_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{self.action_text or "Ver más"}</a>' if self.action_url else ''}
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _prepare_template_data(self, user) -> Dict[str, Any]:
        """Preparar datos para template"""
        return {
            'user_name': user.full_name,
            'user_email': user.email,
            'notification_title': self.title,
            'notification_message': self.message,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'organization_name': self.organization.name if self.organization else 'Ecosistema Emprendimiento',
            'project_name': self.project.name if self.project else None,
            'task_title': self.task.title if self.task else None,
            'meeting_title': self.meeting.title if self.meeting else None,
            'timestamp': datetime.utcnow().strftime('%d/%m/%Y %H:%M'),
            'custom_data': self.content_data or {}
        }
    
    def _send_via_email_service(self, email_data: Dict[str, Any]) -> bool:
        """Enviar email usando servicio externo"""
        try:
            # En producción, integrar con SendGrid, AWS SES, etc.
            # Por ahora, simular envío exitoso
            print(f"Email enviado a {email_data['to']}: {email_data['subject']}")
            return True
            
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False
    
    def _send_via_sms_service(self, sms_data: Dict[str, Any]) -> bool:
        """Enviar SMS usando servicio externo"""
        try:
            # En producción, integrar con Twilio, AWS SNS, etc.
            print(f"SMS enviado a {sms_data['to']}: {sms_data['message']}")
            return True
            
        except Exception as e:
            print(f"Error enviando SMS: {e}")
            return False
    
    def _send_via_push_service(self, device_tokens: List[str], push_data: Dict[str, Any]) -> bool:
        """Enviar push notification usando servicio externo"""
        try:
            # En producción, integrar con FCM, APNs, etc.
            print(f"Push notification enviada a {len(device_tokens)} dispositivos")
            return True
            
        except Exception as e:
            print(f"Error enviando push notification: {e}")
            return False
    
    def _send_via_webhook(self, webhook_url: str, data: Dict[str, Any]) -> bool:
        """Enviar notificación vía webhook"""
        try:
            import requests
            
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error enviando webhook: {e}")
            return False
    
    def _get_user_device_tokens(self, user_id: int) -> List[str]:
        """Obtener tokens de dispositivos del usuario"""
        # En producción, consultar tabla de dispositivos registrados
        return []  # Placeholder
    
    def _get_user_webhook_url(self, user_id: int) -> Optional[str]:
        """Obtener URL de webhook del usuario"""
        # En producción, consultar configuración del usuario
        return None  # Placeholder
    
    def mark_as_read(self, user_id: int, read_at: datetime = None):
        """Marcar notificación como leída por un usuario"""
        from .. import db
        
        read_time = read_at or datetime.utcnow()
        
        # Actualizar todos los canales del usuario para esta notificación
        result = db.session.execute(
            notification_recipients.update().where(
                notification_recipients.c.notification_id == self.id,
                notification_recipients.c.user_id == user_id
            ).values(
                delivery_status=DeliveryStatus.READ.value,
                read_at=read_time
            )
        )
        
        if result.rowcount > 0:
            # Actualizar contador total de leídas
            self.total_read += 1
            self.read_rate = (self.total_read / self.total_sent * 100) if self.total_sent > 0 else 0
            
            self._log_activity('notification_read', f"Leída por usuario {user_id}")
            return True
        
        return False
    
    def cancel_notification(self, cancelled_by_user_id: int, reason: str = None):
        """Cancelar notificación"""
        if self.status in ['sent', 'completed']:
            raise ValidationError("No se puede cancelar una notificación ya enviada")
        
        self.status = 'cancelled'
        
        # Cancelar destinatarios pendientes
        from .. import db
        
        db.session.execute(
            notification_recipients.update().where(
                notification_recipients.c.notification_id == self.id,
                notification_recipients.c.delivery_status == DeliveryStatus.PENDING.value
            ).values(delivery_status=DeliveryStatus.EXPIRED.value)
        )
        
        cancel_note = f"Notificación cancelada"
        if reason:
            cancel_note += f": {reason}"
        
        self._log_activity('notification_cancelled', cancel_note, cancelled_by_user_id)
    
    def create_recurring_instances(self, end_date: date, max_instances: int = 12) -> List['Notification']:
        """Crear instancias de notificación recurrente"""
        if not self.is_recurring or self.frequency_type == FrequencyType.ONCE:
            return []
        
        instances = []
        current_date = self.next_occurrence_at or self.scheduled_at or datetime.utcnow()
        instance_count = 0
        
        while (current_date.date() <= end_date and 
               instance_count < max_instances):
            
            # Calcular próxima fecha
            next_date = self._calculate_next_occurrence(current_date)
            if not next_date or next_date.date() > end_date:
                break
            
            # Crear nueva instancia
            new_instance = Notification(
                title=self.title,
                message=self.message,
                notification_type=self.notification_type,
                priority=self.priority,
                sender_id=self.sender_id,
                channels=self.channels.copy(),
                trigger_type=TriggerType.SCHEDULED,
                scheduled_at=next_date,
                expires_at=next_date + timedelta(days=7),  # Expira en una semana
                content_html=self.content_html,
                content_data=self.content_data.copy() if self.content_data else None,
                template_name=self.template_name,
                action_url=self.action_url,
                action_text=self.action_text,
                parent_notification_id=self.id,
                project_id=self.project_id,
                organization_id=self.organization_id,
                target_criteria=self.target_criteria.copy() if self.target_criteria else None
            )
            
            from .. import db
            db.session.add(new_instance)
            db.session.flush()  # Para obtener ID
            
            # Copiar destinatarios si no hay criterios de targeting
            if not self.target_criteria:
                for recipient in self.recipients:
                    new_instance.add_recipient(recipient)
            else:
                # Aplicar criterios de targeting nuevamente
                new_instance.add_recipients_by_criteria(self.target_criteria)
            
            instances.append(new_instance)
            current_date = next_date
            instance_count += 1
        
        # Actualizar próxima ocurrencia
        self.next_occurrence_at = current_date if instance_count < max_instances else None
        
        return instances
    
    def _calculate_next_occurrence(self, current_date: datetime) -> Optional[datetime]:
        """Calcular próxima ocurrencia basada en frecuencia"""
        if self.frequency_type == FrequencyType.DAILY:
            return current_date + timedelta(days=1)
        
        elif self.frequency_type == FrequencyType.WEEKLY:
            return current_date + timedelta(weeks=1)
        
        elif self.frequency_type == FrequencyType.MONTHLY:
            # Mismo día del siguiente mes
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1)
            return next_month
        
        elif self.frequency_type == FrequencyType.QUARTERLY:
            months_to_add = 3
            new_month = current_date.month + months_to_add
            new_year = current_date.year
            
            if new_month > 12:
                new_year += 1
                new_month -= 12
            
            return current_date.replace(year=new_year, month=new_month)
        
        elif self.frequency_type == FrequencyType.YEARLY:
            return current_date.replace(year=current_date.year + 1)
        
        elif self.frequency_type == FrequencyType.CUSTOM:
            # Lógica personalizada basada en frequency_settings
            settings = self.frequency_settings or {}
            interval = settings.get('interval', 1)
            unit = settings.get('unit', 'days')
            
            if unit == 'days':
                return current_date + timedelta(days=interval)
            elif unit == 'weeks':
                return current_date + timedelta(weeks=interval)
            elif unit == 'months':
                new_month = current_date.month + interval
                new_year = current_date.year
                while new_month > 12:
                    new_year += 1
                    new_month -= 12
                return current_date.replace(year=new_year, month=new_month)
        
        return None
    
    def duplicate_notification(self, duplicated_by_user_id: int, 
                             new_title: str = None, 
                             new_scheduled_at: datetime = None) -> 'Notification':
        """Duplicar notificación"""
        new_notification = Notification(
            title=new_title or f"Copia de {self.title}",
            message=self.message,
            notification_type=self.notification_type,
            priority=self.priority,
            sender_id=duplicated_by_user_id,
            channels=self.channels.copy(),
            trigger_type=self.trigger_type,
            scheduled_at=new_scheduled_at,
            expires_at=self.expires_at,
            content_html=self.content_html,
            content_data=self.content_data.copy() if self.content_data else None,
            template_name=self.template_name,
            action_url=self.action_url,
            action_text=self.action_text,
            deep_link=self.deep_link,
            image_url=self.image_url,
            icon=self.icon,
            color=self.color,
            project_id=self.project_id,
            organization_id=self.organization_id,
            target_criteria=self.target_criteria.copy() if self.target_criteria else None
        )
        
        from .. import db
        db.session.add(new_notification)
        db.session.flush()
        
        # Copiar destinatarios
        for recipient in self.recipients:
            new_notification.add_recipient(recipient)
        
        self._log_activity('notification_duplicated', 
                          f"Notificación duplicada como: {new_notification.title}", 
                          duplicated_by_user_id)
        
        return new_notification
    
    def get_delivery_report(self) -> Dict[str, Any]:
        """Obtener reporte de entrega detallado"""
        from .. import db
        
        # Obtener estadísticas por canal
        channel_stats = {}
        
        for channel in self.channels:
            channel_recipients = db.session.execute(
                notification_recipients.select().where(
                    notification_recipients.c.notification_id == self.id,
                    notification_recipients.c.channel == channel
                )
            ).fetchall()
            
            if channel_recipients:
                total = len(channel_recipients)
                sent = len([r for r in channel_recipients if r.delivery_status in ['sent', 'delivered', 'read']])
                delivered = len([r for r in channel_recipients if r.delivery_status in ['delivered', 'read']])
                read = len([r for r in channel_recipients if r.delivery_status == 'read'])
                failed = len([r for r in channel_recipients if r.delivery_status == 'failed'])
                
                channel_stats[channel] = {
                    'total_recipients': total,
                    'sent': sent,
                    'delivered': delivered,
                    'read': read,
                    'failed': failed,
                    'delivery_rate': (delivered / total * 100) if total > 0 else 0,
                    'read_rate': (read / delivered * 100) if delivered > 0 else 0
                }
        
        # Análisis temporal
        delivery_timeline = db.session.execute(
            f"""
            SELECT DATE(sent_at) as date, COUNT(*) as count
            FROM notification_recipients 
            WHERE notification_id = {self.id} AND sent_at IS NOT NULL
            GROUP BY DATE(sent_at)
            ORDER BY date
            """
        ).fetchall()
        
        return {
            'notification_id': self.id,
            'title': self.title,
            'type': self.notification_type.value,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.updated_at.isoformat() if self.status in ['sent', 'completed'] else None,
            'overall_stats': {
                'total_recipients': self.target_count,
                'total_sent': self.total_sent,
                'total_delivered': self.total_delivered,
                'total_read': self.total_read,
                'total_failed': self.total_failed,
                'delivery_rate': self.delivery_rate,
                'read_rate': self.read_rate,
                'engagement_rate': self.engagement_rate
            },
            'channel_breakdown': channel_stats,
            'delivery_timeline': [
                {
                    'date': row.date.isoformat() if row.date else None,
                    'count': row.count
                }
                for row in delivery_timeline
            ],
            'performance_metrics': {
                'time_to_delivery': self._calculate_average_delivery_time(),
                'bounce_rate': (self.total_failed / self.total_sent * 100) if self.total_sent > 0 else 0,
                'engagement_score': self._calculate_engagement_score()
            }
        }
    
    def _calculate_average_delivery_time(self) -> float:
        """Calcular tiempo promedio de entrega"""
        from .. import db
        
        delivery_times = db.session.execute(
            f"""
            SELECT EXTRACT(EPOCH FROM (delivered_at - sent_at)) as delivery_time_seconds
            FROM notification_recipients 
            WHERE notification_id = {self.id} 
            AND sent_at IS NOT NULL 
            AND delivered_at IS NOT NULL
            """
        ).fetchall()
        
        if delivery_times:
            total_time = sum(row.delivery_time_seconds for row in delivery_times)
            return total_time / len(delivery_times)
        
        return 0.0
    
    def _calculate_engagement_score(self) -> float:
        """Calcular puntuación de engagement"""
        score = 0.0
        
        # Delivery rate (40%)
        score += (self.delivery_rate / 100) * 40
        
        # Read rate (40%)
        score += (self.read_rate / 100) * 40
        
        # Click rate (20%) - placeholder, en producción se trackearían clicks
        click_rate = min(self.read_rate * 0.3, 100)  # Estimación: 30% de los que leen hacen click
        score += (click_rate / 100) * 20
        
        return round(score, 1)
    
    def _log_activity(self, activity_type: str, description: str, 
                     user_id: int = None, metadata: Dict[str, Any] = None):
        """Registrar actividad de la notificación"""
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type=activity_type,
            description=description,
            notification_id=self.id,
            user_id=user_id or self.sender_id,
            metadata=metadata or {}
        )
        
        db.session.add(activity)
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def search_notifications(cls, query: str = None, filters: Dict[str, Any] = None,
                           user_id: int = None, limit: int = 50, offset: int = 0):
        """Buscar notificaciones"""
        search = cls.query.filter(cls.is_deleted == False)
        
        # Filtrar por usuario si se especifica
        if user_id:
            if filters and filters.get('scope') == 'sent':
                # Solo notificaciones enviadas por el usuario
                search = search.filter(cls.sender_id == user_id)
            elif filters and filters.get('scope') == 'received':
                # Solo notificaciones recibidas por el usuario
                search = search.filter(cls.recipients.any(id=user_id))
            else:
                # Notificaciones relacionadas al usuario
                search = search.filter(
                    (cls.sender_id == user_id) |
                    (cls.recipients.any(id=user_id))
                )
        
        # Búsqueda por texto
        if query:
            search_term = f"%{query}%"
            search = search.filter(
                cls.title.ilike(search_term) |
                cls.message.ilike(search_term)
            )
        
        # Aplicar filtros
        if filters:
            if filters.get('type'):
                if isinstance(filters['type'], list):
                    search = search.filter(cls.notification_type.in_(filters['type']))
                else:
                    search = search.filter(cls.notification_type == filters['type'])
            
            if filters.get('priority'):
                if isinstance(filters['priority'], list):
                    search = search.filter(cls.priority.in_(filters['priority']))
                else:
                    search = search.filter(cls.priority == filters['priority'])
            
            if filters.get('status'):
                if isinstance(filters['status'], list):
                    search = search.filter(cls.status.in_(filters['status']))
                else:
                    search = search.filter(cls.status == filters['status'])
            
            if filters.get('channel'):
                search = search.filter(cls.channels.contains([filters['channel']]))
            
            if filters.get('organization_id'):
                search = search.filter(cls.organization_id == filters['organization_id'])
            
            if filters.get('project_id'):
                search = search.filter(cls.project_id == filters['project_id'])
            
            if filters.get('sender_id'):
                search = search.filter(cls.sender_id == filters['sender_id'])
            
            if filters.get('scheduled_after'):
                search = search.filter(cls.scheduled_at >= filters['scheduled_after'])
            
            if filters.get('scheduled_before'):
                search = search.filter(cls.scheduled_at <= filters['scheduled_before'])
            
            if filters.get('is_recurring'):
                search = search.filter(cls.is_recurring == filters['is_recurring'])
            
            if filters.get('read_status') and user_id:
                if filters['read_status'] == 'read':
                    search = search.join(notification_recipients).filter(
                        notification_recipients.c.user_id == user_id,
                        notification_recipients.c.delivery_status == DeliveryStatus.READ.value
                    )
                elif filters['read_status'] == 'unread':
                    search = search.join(notification_recipients).filter(
                        notification_recipients.c.user_id == user_id,
                        notification_recipients.c.delivery_status != DeliveryStatus.READ.value
                    )
        
        # Ordenamiento
        sort_by = filters.get('sort_by', 'created_at') if filters else 'created_at'
        sort_order = filters.get('sort_order', 'desc') if filters else 'desc'
        
        if sort_by == 'title':
            order_column = cls.title
        elif sort_by == 'scheduled_at':
            order_column = cls.scheduled_at
        elif sort_by == 'priority':
            order_column = cls.priority
        elif sort_by == 'delivery_rate':
            order_column = cls.delivery_rate
        else:
            order_column = cls.created_at
        
        if sort_order == 'desc':
            search = search.order_by(order_column.desc())
        else:
            search = search.order_by(order_column.asc())
        
        return search.offset(offset).limit(limit).all()
    
    @classmethod
    def get_pending_notifications(cls):
        """Obtener notificaciones pendientes de envío"""
        return cls.query.filter(
            cls.status.in_(['draft', 'scheduled']),
            cls.scheduled_at <= datetime.utcnow(),
            cls.expires_at > datetime.utcnow(),
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def get_user_notifications(cls, user_id: int, unread_only: bool = False, 
                             limit: int = 20) -> List[Dict[str, Any]]:
        """Obtener notificaciones de un usuario"""
        from .. import db
        
        query = f"""
        SELECT n.*, nr.delivery_status, nr.read_at, nr.channel
        FROM notifications n
        JOIN notification_recipients nr ON n.id = nr.notification_id
        WHERE nr.user_id = {user_id}
        AND n.is_deleted = FALSE
        """
        
        if unread_only:
            query += " AND nr.delivery_status != 'read'"
        
        query += " ORDER BY n.created_at DESC LIMIT %s" % limit
        
        results = db.session.execute(query).fetchall()
        
        notifications = []
        for row in results:
            notification_data = {
                'id': row.id,
                'title': row.title,
                'message': row.message,
                'type': row.notification_type,
                'priority': row.priority,
                'action_url': row.action_url,
                'action_text': row.action_text,
                'image_url': row.image_url,
                'icon': row.icon,
                'is_read': row.delivery_status == 'read',
                'read_at': row.read_at.isoformat() if row.read_at else None,
                'channel': row.channel,
                'created_at': row.created_at.isoformat() if row.created_at else None
            }
            notifications.append(notification_data)
        
        return notifications
    
    def to_dict(self, include_recipients=False, include_stats=True) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type.value,
            'priority': self.priority.value,
            'channels': self.channels,
            'trigger_type': self.trigger_type.value,
            'status': self.status,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_recurring': self.is_recurring,
            'frequency_type': self.frequency_type.value if self.frequency_type else None,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'deep_link': self.deep_link,
            'image_url': self.image_url,
            'icon': self.icon,
            'color': self.color,
            'is_scheduled': self.is_scheduled,
            'is_expired': self.is_expired,
            'is_sent': self.is_sent,
            'is_ready_to_send': self.is_ready_to_send,
            'time_until_send': self.time_until_send,
            'days_until_expire': self.days_until_expire,
            'sender_id': self.sender_id,
            'sender_name': self.sender.full_name if self.sender else 'Sistema',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Información de contexto
        if self.project_id:
            data['project'] = {
                'id': self.project_id,
                'name': self.project.name if self.project else None
            }
        
        if self.organization_id:
            data['organization'] = {
                'id': self.organization_id,
                'name': self.organization.name if self.organization else None
            }
        
        # Estadísticas
        if include_stats:
            data['stats'] = {
                'target_count': self.target_count,
                'recipient_count': self.recipient_count,
                'total_sent': self.total_sent,
                'total_delivered': self.total_delivered,
                'total_read': self.total_read,
                'total_failed': self.total_failed,
                'delivery_rate': self.delivery_rate,
                'read_rate': self.read_rate,
                'engagement_rate': self.engagement_rate
            }
        
        # Destinatarios
        if include_recipients:
            data['recipients'] = [
                {
                    'id': recipient.id,
                    'name': recipient.full_name,
                    'email': recipient.email
                }
                for recipient in self.recipients
            ]
        
        return data


# Funciones de utilidad para el módulo
def get_notification_statistics(organization_id: int = None, user_id: int = None,
                               date_from: date = None, date_to: date = None) -> Dict[str, Any]:
    """Obtener estadísticas de notificaciones"""
    query = Notification.query.filter(Notification.is_deleted == False)
    
    if organization_id:
        query = query.filter(Notification.organization_id == organization_id)
    
    if user_id:
        query = query.filter(
            (Notification.sender_id == user_id) |
            (Notification.recipients.any(id=user_id))
        )
    
    if date_from:
        date_from_dt = datetime.combine(date_from, datetime.min.time())
        query = query.filter(Notification.created_at >= date_from_dt)
    
    if date_to:
        date_to_dt = datetime.combine(date_to, datetime.max.time())
        query = query.filter(Notification.created_at <= date_to_dt)
    
    notifications = query.all()
    
    if not notifications:
        return {
            'total_notifications': 0,
            'total_sent': 0,
            'average_delivery_rate': 0,
            'average_read_rate': 0,
            'most_used_channel': None
        }
    
    # Estadísticas básicas
    total_notifications = len(notifications)
    sent_notifications = [n for n in notifications if n.is_sent]
    total_sent = sum(n.total_sent for n in notifications)
    total_delivered = sum(n.total_delivered for n in notifications)
    total_read = sum(n.total_read for n in notifications)
    
    # Tasas promedio
    avg_delivery_rate = sum(n.delivery_rate for n in sent_notifications) / len(sent_notifications) if sent_notifications else 0
    avg_read_rate = sum(n.read_rate for n in sent_notifications) / len(sent_notifications) if sent_notifications else 0
    
    # Distribución por tipo
    type_distribution = {}
    for notification in notifications:
        notif_type = notification.notification_type.value
        type_distribution[notif_type] = type_distribution.get(notif_type, 0) + 1
    
    # Distribución por canal
    channel_usage = {}
    for notification in notifications:
        for channel in notification.channels:
            channel_usage[channel] = channel_usage.get(channel, 0) + 1
    
    most_used_channel = max(channel_usage.items(), key=lambda x: x[1])[0] if channel_usage else None
    
    # Distribución por prioridad
    priority_distribution = {}
    for notification in notifications:
        priority = notification.priority.value
        priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
    
    return {
        'total_notifications': total_notifications,
        'sent_notifications': len(sent_notifications),
        'total_recipients_reached': total_sent,
        'total_delivered': total_delivered,
        'total_read': total_read,
        'average_delivery_rate': round(avg_delivery_rate, 1),
        'average_read_rate': round(avg_read_rate, 1),
        'type_distribution': type_distribution,
        'channel_usage': channel_usage,
        'most_used_channel': most_used_channel,
        'priority_distribution': priority_distribution,
        'engagement_metrics': {
            'notifications_per_day': round(total_notifications / 30, 1) if total_notifications > 0 else 0,
            'average_recipients_per_notification': round(total_sent / total_notifications, 1) if total_notifications > 0 else 0,
            'high_priority_percentage': round(
                (priority_distribution.get('high', 0) + priority_distribution.get('urgent', 0) + priority_distribution.get('critical', 0)) /
                total_notifications * 100, 1
            ) if total_notifications > 0 else 0
        }
    }


def process_scheduled_notifications():
    """Procesar notificaciones programadas listas para envío"""
    pending_notifications = Notification.get_pending_notifications()
    processed_count = 0
    
    for notification in pending_notifications:
        try:
            result = notification.send_notification()
            if result['total_sent'] > 0:
                processed_count += 1
        except Exception as e:
            print(f"Error enviando notificación {notification.id}: {e}")
    
    return processed_count


def process_recurring_notifications():
    """Procesar notificaciones recurrentes y crear nuevas instancias"""
    recurring_notifications = Notification.query.filter(
        Notification.is_recurring == True,
        Notification.next_occurrence_at <= datetime.utcnow(),
        Notification.is_deleted == False
    ).all()
    
    created_instances = 0
    
    for notification in recurring_notifications:
        try:
            # Crear próximas instancias
            end_date = date.today() + timedelta(days=90)  # 3 meses adelante
            instances = notification.create_recurring_instances(end_date, max_instances=5)
            created_instances += len(instances)
            
        except Exception as e:
            print(f"Error creando instancias recurrentes para notificación {notification.id}: {e}")
    
    return created_instances


def cleanup_expired_notifications():
    """Limpiar notificaciones vencidas"""
    expired_notifications = Notification.query.filter(
        Notification.expires_at < datetime.utcnow(),
        Notification.status.in_(['draft', 'scheduled']),
        Notification.is_deleted == False
    ).all()
    
    cleaned_count = 0
    
    for notification in expired_notifications:
        try:
            notification.status = 'expired'
            
            # Marcar destinatarios como expirados
            from .. import db
            db.session.execute(
                notification_recipients.update().where(
                    notification_recipients.c.notification_id == notification.id,
                    notification_recipients.c.delivery_status == DeliveryStatus.PENDING.value
                ).values(delivery_status=DeliveryStatus.EXPIRED.value)
            )
            
            cleaned_count += 1
            
        except Exception as e:
            print(f"Error limpiando notificación vencida {notification.id}: {e}")
    
    return cleaned_count


def auto_delete_old_notifications(days_old: int = 90):
    """Auto-eliminar notificaciones antiguas según configuración"""
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    old_notifications = Notification.query.filter(
        Notification.created_at < cutoff_date,
        Notification.auto_delete_after_days.isnot(None),
        Notification.is_deleted == False
    ).all()
    
    deleted_count = 0
    
    for notification in old_notifications:
        try:
            # Verificar si debe eliminarse según su configuración específica
            delete_after = notification.created_at + timedelta(days=notification.auto_delete_after_days)
            
            if datetime.utcnow() >= delete_after:
                notification.is_deleted = True
                deleted_count += 1
                
        except Exception as e:
            print(f"Error auto-eliminando notificación {notification.id}: {e}")
    
    return deleted_count


def send_digest_notifications(user_ids: List[int] = None, digest_type: str = 'daily'):
    """Enviar notificaciones de resumen (digest)"""
    from .user import User
    
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
    else:
        # Obtener usuarios que tienen habilitadas las notificaciones digest
        users = User.query.filter(
            User.notification_preferences['digest_notifications'].astext.cast(Boolean) == True,
            User.is_deleted == False
        ).all()
    
    digest_notifications_sent = 0
    
    for user in users:
        try:
            # Verificar frecuencia preferida del usuario
            user_digest_frequency = user.notification_preferences.get('digest_frequency', 'daily')
            
            if user_digest_frequency != digest_type:
                continue
            
            # Obtener actividades recientes del usuario
            digest_data = _generate_user_digest_data(user, digest_type)
            
            if not digest_data['has_content']:
                continue  # No enviar digest vacío
            
            # Crear notificación digest
            digest_notification = Notification(
                title=f"Resumen {digest_type.title()} - {digest_data['period']}",
                message=digest_data['summary'],
                notification_type=NotificationType.NEWSLETTER,
                priority=NotificationPriority.LOW,
                channels=['email', 'in_app'],
                trigger_type=TriggerType.IMMEDIATE,
                template_name='user_digest',
                content_data=digest_data,
                organization_id=user.organization_id
            )
            
            from .. import db
            db.session.add(digest_notification)
            db.session.flush()
            
            # Agregar usuario como destinatario
            digest_notification.add_recipient(user)
            
            # Enviar inmediatamente
            digest_notification.send_notification()
            digest_notifications_sent += 1
            
        except Exception as e:
            print(f"Error enviando digest a usuario {user.id}: {e}")
    
    return digest_notifications_sent


def _generate_user_digest_data(user, digest_type: str) -> Dict[str, Any]:
    """Generar datos de resumen para un usuario"""
    from .task import Task
    from .meeting import Meeting
    from .project import Project
    
    # Determinar período
    if digest_type == 'daily':
        start_date = datetime.utcnow() - timedelta(days=1)
        period = "últimas 24 horas"
    elif digest_type == 'weekly':
        start_date = datetime.utcnow() - timedelta(days=7)
        period = "última semana"
    else:  # monthly
        start_date = datetime.utcnow() - timedelta(days=30)
        period = "último mes"
    
    # Obtener actividades del usuario en el período
    user_tasks = Task.query.filter(
        (Task.assignee_id == user.id) | (Task.assignees.any(id=user.id)),
        Task.updated_at >= start_date,
        Task.is_deleted == False
    ).all()
    
    user_meetings = Meeting.query.filter(
        (Meeting.organizer_id == user.id) | (Meeting.participants.any(id=user.id)),
        Meeting.scheduled_start >= start_date,
        Meeting.is_deleted == False
    ).all()
    
    # Tareas completadas
    completed_tasks = [t for t in user_tasks if t.status.value == 'completed']
    
    # Reuniones próximas
    upcoming_meetings = [m for m in user_meetings if m.scheduled_start > datetime.utcnow()]
    
    # Tareas vencidas
    overdue_tasks = [t for t in user_tasks if t.is_overdue]
    
    # Verificar si hay contenido suficiente
    has_content = (len(completed_tasks) > 0 or 
                  len(upcoming_meetings) > 0 or 
                  len(overdue_tasks) > 0)
    
    # Generar resumen textual
    summary_parts = []
    
    if completed_tasks:
        summary_parts.append(f"Has completado {len(completed_tasks)} tarea(s)")
    
    if upcoming_meetings:
        summary_parts.append(f"Tienes {len(upcoming_meetings)} reunión(es) próxima(s)")
    
    if overdue_tasks:
        summary_parts.append(f"Tienes {len(overdue_tasks)} tarea(s) vencida(s)")
    
    summary = f"En las {period}: {', '.join(summary_parts)}." if summary_parts else f"No hay actividades nuevas en las {period}."
    
    return {
        'period': period,
        'summary': summary,
        'has_content': has_content,
        'completed_tasks': [
            {
                'id': task.id,
                'title': task.title,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            }
            for task in completed_tasks[:5]  # Máximo 5
        ],
        'upcoming_meetings': [
            {
                'id': meeting.id,
                'title': meeting.title,
                'scheduled_start': meeting.scheduled_start.isoformat()
            }
            for meeting in upcoming_meetings[:5]  # Máximo 5
        ],
        'overdue_tasks': [
            {
                'id': task.id,
                'title': task.title,
                'due_date': task.due_date.isoformat() if task.due_date else None
            }
            for task in overdue_tasks[:5]  # Máximo 5
        ],
        'user_name': user.full_name,
        'digest_type': digest_type
    }


def create_system_notification(title: str, message: str, 
                             notification_type: NotificationType = NotificationType.SYSTEM,
                             priority: NotificationPriority = NotificationPriority.NORMAL,
                             channels: List[str] = None,
                             target_criteria: Dict[str, Any] = None,
                             action_url: str = None,
                             expires_in_hours: int = 24) -> Notification:
    """Crear notificación del sistema"""
    
    notification = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        channels=channels or ['in_app', 'email'],
        trigger_type=TriggerType.IMMEDIATE,
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
        action_url=action_url,
        sender_id=1  # Usuario del sistema
    )
    
    from .. import db
    db.session.add(notification)
    db.session.flush()
    
    # Agregar destinatarios según criterios
    if target_criteria:
        notification.add_recipients_by_criteria(target_criteria)
    else:
        # Por defecto, enviar a todos los usuarios activos
        notification.add_recipients_by_criteria({
            'active_since': datetime.utcnow() - timedelta(days=30)
        })
    
    return notification


def create_task_reminder_notification(task, reminder_hours_before: int = 24) -> Optional[Notification]:
    """Crear notificación recordatorio de tarea"""
    if not task.due_date or not task.assignee:
        return None
    
    reminder_time = task.due_date - timedelta(hours=reminder_hours_before)
    
    # No crear recordatorio si ya pasó la fecha
    if reminder_time <= datetime.utcnow():
        return None
    
    notification = Notification(
        title=f"Recordatorio: {task.title}",
        message=f"La tarea '{task.title}' vence el {task.due_date.strftime('%d/%m/%Y a las %H:%M')}.",
        notification_type=NotificationType.TASK_REMINDER,
        priority=NotificationPriority.HIGH if task.priority.value in ['high', 'urgent', 'critical'] else NotificationPriority.NORMAL,
        channels=['in_app', 'email'],
        trigger_type=TriggerType.SCHEDULED,
        scheduled_at=reminder_time,
        action_url=f"/tasks/{task.id}",
        action_text="Ver Tarea",
        task_id=task.id,
        project_id=task.project_id,
        organization_id=task.organization_id
    )
    
    from .. import db
    db.session.add(notification)
    db.session.flush()
    
    # Agregar asignado principal
    notification.add_recipient(task.assignee)
    
    # Agregar otros asignados si existen
    for assignee in task.assignees:
        if assignee.id != task.assignee_id:
            notification.add_recipient(assignee)
    
    return notification


def create_meeting_reminder_notification(meeting, reminder_hours_before: int = 1) -> Optional[Notification]:
    """Crear notificación recordatorio de reunión"""
    if not meeting.scheduled_start:
        return None
    
    reminder_time = meeting.scheduled_start - timedelta(hours=reminder_hours_before)
    
    if reminder_time <= datetime.utcnow():
        return None
    
    notification = Notification(
        title=f"Recordatorio: {meeting.title}",
        message=f"La reunión '{meeting.title}' comienza el {meeting.scheduled_start.strftime('%d/%m/%Y a las %H:%M')}.",
        notification_type=NotificationType.MEETING_REMINDER,
        priority=NotificationPriority.HIGH,
        channels=['in_app', 'email', 'push'],
        trigger_type=TriggerType.SCHEDULED,
        scheduled_at=reminder_time,
        action_url=meeting.meeting_url or f"/meetings/{meeting.id}",
        action_text="Unirse a la Reunión",
        deep_link=f"app://meetings/{meeting.id}",
        meeting_id=meeting.id,
        organization_id=meeting.organization_id
    )
    
    from .. import db
    db.session.add(notification)
    db.session.flush()
    
    # Agregar organizador
    if meeting.organizer:
        notification.add_recipient(meeting.organizer)
    
    # Agregar participantes
    for participant in meeting.participants:
        if not meeting.organizer or participant.id != meeting.organizer.id:
            notification.add_recipient(participant)
    
    return notification


def get_user_notification_preferences(user_id: int) -> Dict[str, Any]:
    """Obtener preferencias de notificación de un usuario"""
    from .user import User
    
    user = User.query.get(user_id)
    if not user:
        return {}
    
    # Preferencias por defecto
    default_preferences = {
        'email_notifications': True,
        'push_notifications': True,
        'sms_notifications': False,
        'digest_notifications': True,
        'digest_frequency': 'daily',
        'notification_types': {
            'task_reminders': True,
            'task_assignments': True,
            'meeting_reminders': True,
            'meeting_invitations': True,
            'project_updates': True,
            'mentorship_sessions': True,
            'program_updates': True,
            'document_shares': True,
            'messages': True,
            'mentions': True,
            'system_announcements': True,
            'marketing_communications': False
        },
        'quiet_hours': {
            'enabled': False,
            'start_time': '22:00',
            'end_time': '08:00',
            'timezone': user.timezone or 'UTC'
        }
    }
    
    # Combinar con preferencias del usuario
    user_preferences = getattr(user, 'notification_preferences', {}) or {}
    
    # Merge recursivo
    def merge_preferences(default, user_prefs):
        result = default.copy()
        for key, value in user_prefs.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_preferences(result[key], value)
            else:
                result[key] = value
        return result
    
    return merge_preferences(default_preferences, user_preferences)


def update_user_notification_preferences(user_id: int, preferences: Dict[str, Any]) -> bool:
    """Actualizar preferencias de notificación de un usuario"""
    from .user import User
    from .. import db
    
    user = User.query.get(user_id)
    if not user:
        return False
    
    try:
        # Obtener preferencias actuales
        current_preferences = getattr(user, 'notification_preferences', {}) or {}
        
        # Actualizar con nuevas preferencias
        def update_nested_dict(current, updates):
            for key, value in updates.items():
                if key in current and isinstance(current[key], dict) and isinstance(value, dict):
                    update_nested_dict(current[key], value)
                else:
                    current[key] = value
        
        update_nested_dict(current_preferences, preferences)
        
        # Guardar preferencias actualizadas
        user.notification_preferences = current_preferences
        db.session.commit()
        
        return True
        
    except Exception as e:
        print(f"Error actualizando preferencias de notificación para usuario {user_id}: {e}")
        db.session.rollback()
        return False"""
Modelo Notificación del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de notificaciones y alertas,
incluyendo notificaciones push, email, SMS, y notificaciones en tiempo real.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
import json

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    NOTIFICATION_TYPES,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_PRIORITIES,
    DELIVERY_STATUS,
    TRIGGER_TYPES,
    FREQUENCY_TYPES
)
from ..core.exceptions import ValidationError


class NotificationType(Enum):
    """Tipos de notificación"""
    SYSTEM = "system"
    TASK_REMINDER = "task_reminder"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_OVERDUE = "task_overdue"
    MEETING_REMINDER = "meeting_reminder"
    MEETING_INVITED = "meeting_invited"
    MEETING_CANCELLED = "meeting_cancelled"
    PROJECT_UPDATE = "project_update"
    PROJECT_MILESTONE = "project_milestone"
    MENTORSHIP_SESSION = "mentorship_session"
    MENTORSHIP_REQUEST = "mentorship_request"
    PROGRAM_APPLICATION = "program_application"
    PROGRAM_ACCEPTED = "program_accepted"
    PROGRAM_DEADLINE = "program_deadline"
    DOCUMENT_SHARED = "document_shared"
    DOCUMENT_COMMENT = "document_comment"
    MESSAGE_RECEIVED = "message_received"
    MENTION = "mention"
    FOLLOW_UP = "follow_up"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    FUNDING_OPPORTUNITY = "funding_opportunity"
    PARTNERSHIP_REQUEST = "partnership_request"
    EVENT_INVITATION = "event_invitation"
    DEADLINE_APPROACHING = "deadline_approaching"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    SECURITY_ALERT = "security_alert"
    PAYMENT_DUE = "payment_due"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    NEWSLETTER = "newsletter"
    PROMOTIONAL = "promotional"
    EMERGENCY = "emergency"


class NotificationChannel(Enum):
    """Canales de notificación"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class NotificationPriority(Enum):
    """Prioridades de notificación"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class DeliveryStatus(Enum):
    """Estados de entrega"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TriggerType(Enum):
    """Tipos de disparador"""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"
    EVENT_BASED = "event_based"
    CONDITION_BASED = "condition_based"


class FrequencyType(Enum):
    """Tipos de frecuencia"""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


# Tabla de asociación para destinatarios de notificación
notification_recipients = Table(
    'notification_recipients',
    Column('notification_id', Integer, ForeignKey('notifications.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('channel', String(50)),
    Column('delivery_status', String(50), default='pending'),
    Column('sent_at', DateTime),
    Column('delivered_at', DateTime),
    Column('read_at', DateTime),
    Column('failed_reason', String(500)),
    Column('retry_count', Integer, default=0),
    Column('external_id', String(200)),  # ID del proveedor externo
    Column('metadata', JSON),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Notification(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Notificación
    
    Representa notificaciones en el ecosistema de emprendimiento
    con soporte para múltiples canales y configuraciones avanzadas.
    """
    
    __tablename__ = 'notifications'
    
    # Información básica
    title = Column(String(300), nullable=False, index=True)
    message = Column(Text, nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL, index=True)
    
    # Remitente (puede ser nulo para notificaciones del sistema)
    sender_id = Column(Integer, ForeignKey('users.id'), index=True)
    sender = relationship("User", foreign_keys=[sender_id])
    
    # Canales de entrega
    channels = Column(JSON, nullable=False)  # Lista de canales a usar
    
    # Programación y disparadores
    trigger_type = Column(SQLEnum(TriggerType), default=TriggerType.IMMEDIATE)
    scheduled_at = Column(DateTime, index=True)
    expires_at = Column(DateTime)
    
    # Configuración de recurrencia
    is_recurring = Column(Boolean, default=False, index=True)
    frequency_type = Column(SQLEnum(FrequencyType))
    frequency_settings = Column(JSON)  # Configuración detallada de frecuencia
    parent_notification_id = Column(Integer, ForeignKey('notifications.id'))
    next_occurrence_at = Column(DateTime)
    
    # Contenido enriquecido
    content_html = Column(Text)  # Versión HTML del mensaje
    content_data = Column(JSON)  # Datos estructurados para templates
    template_name = Column(String(100))  # Nombre del template a usar
    
    # Enlaces y acciones
    action_url = Column(String(1000))  # URL de acción principal
    action_text = Column(String(100))  # Texto del botón de acción
    deep_link = Column(String(1000))  # Deep link para apps móviles
    actions = Column(JSON)  # Acciones adicionales (botones, links)
    
    # Personalización
    image_url = Column(String(1000))  # Imagen de la notificación
    icon = Column(String(100))  # Icono de la notificación
    color = Column(String(7))  # Color hex
    sound = Column(String(100))  # Sonido personalizado
    
    # Segmentación y targeting
    target_criteria = Column(JSON)  # Criterios de segmentación
    target_count = Column(Integer, default=0)  # Número de destinatarios objetivo
    
    # Estado de la campaña
    status = Column(String(50), default='draft', index=True)  # draft, scheduled, sending, sent, completed, cancelled
    
    # Estadísticas de entrega
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_read = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    delivery_rate = Column(Float, default=0.0)
    read_rate = Column(Float, default=0.0)
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    
    task_id = Column(Integer, ForeignKey('tasks.id'))
    task = relationship("Task")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship("Client")
    
    document_id = Column(Integer, ForeignKey('documents.id'))
    document = relationship("Document")
    
    # Configuración A/B Testing
    ab_test_group = Column(String(50))  # Grupo de prueba A/B
    ab_test_variant = Column(String(50))  # Variante específica
    
    # Configuración de privacidad
    is_confidential = Column(Boolean, default=False)
    requires_read_receipt = Column(Boolean, default=False)
    auto_delete_after_days = Column(Integer)
    
    # Metadatos y contexto
    context_data = Column(JSON)  # Datos de contexto adicionales
    tracking_data = Column(JSON)  # Datos para tracking y analytics
    external_reference = Column(String(200))  # Referencia externa
    
    # Relaciones
    
    # Destinatarios
    recipients = relationship("User",
                            secondary=notification_recipients,
                            back_populates="notifications_received")
    
    # Actividades relacionadas
    activities = relationship("ActivityLog", back_populates="notification")
    
    def __init__(self, **kwargs):
        """Inicialización de la notificación"""
        super().__init__(**kwargs)
        
        # Configurar canales por defecto si no se especifican
        if not self.channels:
            self.channels = ['in_app']
        
        # Configurar programación por defecto
        if self.trigger_type == TriggerType.IMMEDIATE and not self.scheduled_at:
            self.scheduled_at = datetime.utcnow()
        
        # Configurar expiración por defecto (30 días)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=30)
    
    def __repr__(self):
        return f'<Notification {self.title} ({self.notification_type.value})>'
    
    def __str__(self):
        return f'{self.title} - {self.notification_type.value} ({self.priority.value})'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título de la notificación"""
        if not title or len(title.strip()) < 1:
            raise ValidationError("El título es requerido")
        if len(title) > 300:
            raise ValidationError("El título no puede exceder 300 caracteres")
        return title.strip()
    
    @validates('message')
    def validate_message(self, key, message):
        """Validar mensaje de la notificación"""
        if not message or len(message.strip()) < 1:
            raise ValidationError("El mensaje es requerido")
        if len(message) > 10000:
            raise ValidationError("El mensaje no puede exceder 10,000 caracteres")
        return message.strip()
    
    @validates('channels')
    def validate_channels(self, key, channels):
        """Validar canales de notificación"""
        if not channels or len(channels) == 0:
            raise ValidationError("Al menos un canal es requerido")
        
        if not isinstance(channels, list):
            raise ValidationError("Los canales deben ser una lista")
        
        valid_channels = [channel.value for channel in NotificationChannel]
        for channel in channels:
            if channel not in valid_channels:
                raise ValidationError(f"Canal inválido: {channel}")
        
        return channels
    
    @validates('action_url', 'deep_link')
    def validate_urls(self, key, url):
        """Validar URLs"""
        if url:
            # Validación básica de URL
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            # Para deep links, permitir esquemas personalizados
            if key == 'deep_link':
                deep_link_pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://\S+$')
                if not url_pattern.match(url) and not deep_link_pattern.match(url):
                    raise ValidationError("Deep link inválido")
            else:
                if not url_pattern.match(url):
                    raise ValidationError("URL inválida")
        
        return url
    
    @validates('color')
    def validate_color(self, key, color):
        """Validar color hex"""
        if color:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                raise ValidationError("Color debe ser un valor hex válido (#RRGGBB)")
        return color
    
    @validates('auto_delete_after_days')
    def validate_auto_delete(self, key, days):
        """Validar días de auto-eliminación"""
        if days is not None:
            if days < 1 or days > 365:
                raise ValidationError("Los días de auto-eliminación deben estar entre 1 y 365")
        return days
    
    # Propiedades híbridas
    @hybrid_property
    def is_scheduled(self):
        """Verificar si está programada"""
        return self.scheduled_at and self.scheduled_at > datetime.utcnow()
    
    @hybrid_property
    def is_expired(self):
        """Verificar si está vencida"""
        return self.expires_at and self.expires_at < datetime.utcnow()
    
    @hybrid_property
    def is_sent(self):
        """Verificar si ya fue enviada"""
        return self.status in ['sent', 'completed']
    
    @hybrid_property
    def is_ready_to_send(self):
        """Verificar si está lista para enviar"""
        return (self.status in ['draft', 'scheduled'] and 
                not self.is_expired and
                self.scheduled_at <= datetime.utcnow())
    
    @hybrid_property
    def recipient_count(self):
        """Número de destinatarios"""
        return len(self.recipients)
    
    @hybrid_property
    def engagement_rate(self):
        """Tasa de engagement (clicks/opens)"""
        if self.total_delivered == 0:
            return 0.0
        # En una implementación real, tendríamos métricas de clicks
        return (self.total_read / self.total_delivered) * 100
    
    @hybrid_property
    def time_until_send(self):
        """Tiempo hasta el envío (en segundos)"""
        if self.scheduled_at:
            return (self.scheduled_at - datetime.utcnow()).total_seconds()
        return 0
    
    @hybrid_property
    def days_until_expire(self):
        """Días hasta expiración"""
        if self.expires_at:
            return (self.expires_at.date() - date.today()).days
        return None
    
    # Métodos de negocio
    def add_recipient(self, user, channels: List[str] = None) -> bool:
        """Agregar destinatario a la notificación"""
        if user in self.recipients:
            return False  # Ya es destinatario
        
        # Verificar canales del usuario
        user_channels = channels or self._get_user_preferred_channels(user)
        
        from .. import db
        
        # Agregar destinatario para cada canal
        for channel in user_channels:
            if channel in self.channels:
                recipient_data = {
                    'notification_id': self.id,
                    'user_id': user.id,
                    'channel': channel,
                    'delivery_status': DeliveryStatus.PENDING.value
                }
                
                db.session.execute(notification_recipients.insert().values(recipient_data))
        
        self.target_count += 1
        return True
    
    def add_recipients_by_criteria(self, criteria: Dict[str, Any]) -> int:
        """Agregar destinatarios basado en criterios"""
        from .user import User
        
        query = User.query.filter(User.is_deleted == False)
        
        # Aplicar criterios de segmentación
        if criteria.get('organization_id'):
            query = query.filter(User.organization_id == criteria['organization_id'])
        
        if criteria.get('user_type'):
            query = query.filter(User.user_type == criteria['user_type'])
        
        if criteria.get('program_id'):
            # Usuarios en un programa específico
            query = query.join(ProgramEnrollment).filter(
                ProgramEnrollment.program_id == criteria['program_id'],
                ProgramEnrollment.status == 'active'
            )
        
        if criteria.get('project_id'):
            # Usuarios relacionados a un proyecto
            query = query.filter(
                (User.id == Project.entrepreneur_id) |
                (User.id.in_(Project.collaborators))
            ).filter(Project.id == criteria['project_id'])
        
        if criteria.get('active_since'):
            query = query.filter(User.last_login_at >= criteria['active_since'])
        
        if criteria.get('notification_preferences'):
            # Filtrar por preferencias de notificación
            pref_key = criteria['notification_preferences']
            query = query.filter(
                User.notification_preferences[pref_key].astext.cast(Boolean) == True
            )
        
        users = query.all()
        added_count = 0
        
        for user in users:
            if self.add_recipient(user):
                added_count += 1
        
        # Guardar criterios para referencia
        self.target_criteria = criteria
        
        return added_count
    
    def _get_user_preferred_channels(self, user) -> List[str]:
        """Obtener canales preferidos del usuario"""
        user_prefs = getattr(user, 'notification_preferences', {}) or {}
        
        preferred_channels = []
        
        # Verificar preferencias por tipo de notificación
        notification_settings = user_prefs.get(self.notification_type.value, {})
        
        if notification_settings.get('in_app', True):
            preferred_channels.append('in_app')
        
        if notification_settings.get('email', True) and user.email:
            preferred_channels.append('email')
        
        if notification_settings.get('sms', False) and user.phone:
            preferred_channels.append('sms')
        
        if notification_settings.get('push', True):
            preferred_channels.append('push')
        
        # Si no hay preferencias específicas, usar configuración general
        if not preferred_channels:
            if user_prefs.get('email_notifications', True):
                preferred_channels.append('email')
            preferred_channels.append('in_app')  # Siempre incluir in-app como fallback
        
        return preferred_channels
    
    def schedule_notification(self, send_at: datetime):
        """Programar notificación para envío futuro"""
        if send_at <= datetime.utcnow():
            raise ValidationError("La fecha de programación debe ser futura")
        
        self.scheduled_at = send_at
        self.trigger_type = TriggerType.SCHEDULED
        self.status = 'scheduled'
        
        self._log_activity('notification_scheduled', f"Programada para {send_at.isoformat()}")
    
    def send_notification(self, force: bool = False) -> Dict[str, Any]:
        """Enviar notificación"""
        if not force and not self.is_ready_to_send:
            raise ValidationError("La notificación no está lista para enviar")
        
        if self.is_expired:
            raise ValidationError("La notificación ha expirado")
        
        self.status = 'sending'
        results = {
            'total_attempted': 0,
            'total_sent': 0,
            'total_failed': 0,
            'errors': []
        }
        
        # Obtener destinatarios pendientes
        from .. import db
        
        pending_recipients = db.session.execute(
            notification_recipients.select().where(
                notification_recipients.c.notification_id == self.id,
                notification_recipients.c.delivery_status == DeliveryStatus.PENDING.value
            )
        ).fetchall()
        
        for recipient_data in pending_recipients:
            try:
                success = self._send_to_recipient(
                    recipient_data.user_id,
                    recipient_data.channel
                )
                
                if success:
                    results['total_sent'] += 1
                    # Actualizar estado del destinatario
                    db.session.execute(
                        notification_recipients.update().where(
                            notification_recipients.c.notification_id == self.id,
                            notification_recipients.c.user_id == recipient_data.user_id,
                            notification_recipients.c.channel == recipient_data.channel
                        ).values(
                            delivery_status=DeliveryStatus.SENT.value,
                            sent_at=datetime.utcnow()
                        )
                    )
                else:
                    results['total_failed'] += 1
                    db.session.execute(
                        notification_recipients.update().where(
                            notification_recipients.c.notification_id == self.id,
                            notification_recipients.c.user_id == recipient_data.user_id,
                            notification_recipients.c.channel == recipient_data.channel
                        ).values(
                            delivery_status=DeliveryStatus.FAILED.value,
                            failed_reason="Error de envío",
                            retry_count=recipient_data.retry_count + 1
                        )
                    )
                
                results['total_attempted'] += 1
                
            except Exception as e:
                results['total_failed'] += 1
                results['errors'].append(f"Error enviando a usuario {recipient_data.user_id}: {str(e)}")
        
        # Actualizar estadísticas
        self.total_sent = results['total_sent']
        self.total_failed = results['total_failed']
        self.delivery_rate = (self.total_sent / results['total_attempted'] * 100) if results['total_attempted'] > 0 else 0
        
        # Actualizar estado
        if results['total_failed'] == 0:
            self.status = 'sent'
        elif results['total_sent'] > 0:
            self.status = 'partially_sent'
        else:
            self.status = 'failed'
        
        self._log_activity('notification_sent', f"Enviada a {results['total_sent']} destinatarios")
        
        return results
    
    def _send_to_recipient(self, user_id: int, channel: str) -> bool:
        """Enviar notificación a un destinatario específico por un canal"""
        from .user import User
        
        user = User.query.get(user_id)
        if not user:
            return False
        
        try:
            if channel == 'in_app':
                return self._send_in_app_notification(user)
            elif channel == 'email':
                return self._send_email_notification(user)
            elif channel == 'sms':
                return self._send_sms_notification(user)
            elif channel == 'push':
                return self._send_push_notification(user)
            elif channel == 'webhook':
                return self._send_webhook_notification(user)
            else:
                return False
                
        except Exception as e:
            print(f"Error enviando notificación {self.id} a usuario {user_id} por {channel}: {e}")
            return False
    
    def _send_in_app_notification(self, user) -> bool:
        """Enviar notificación in-app"""
        # Crear entrada en la bandeja de entrada del usuario
        # En una implementación real, esto se almacenaría en una tabla separada
        user_notification = {
            'notification_id': self.id,
            'user_id': user.id,
            'title': self.title,
            'message': self.message,
            'action_url': self.action_url,
            'is_read': False,
            'created_at': datetime.utcnow()
        }
        
        # También emitir evento en tiempo real vía WebSocket
        self._emit_realtime_notification(user.id, user_notification)
        
        return True
    
    def _send_email_notification(self, user) -> bool:
        """Enviar notificación por email"""
        if not user.email:
            return False
        
        # Preparar datos del email
        email_data = {
            'to': user.email,
            'subject': self.title,
            'html_content': self.content_html or self._generate_email_html(),
            'text_content': self.message,
            'template_name': self.template_name,
            'template_data': self._prepare_template_data(user)
        }
        
        # En producción, usar servicio de email (SendGrid, AWS SES, etc.)
        return self._send_via_email_service(email_data)
    
    def _send_sms_notification(self, user) -> bool:
        """Enviar notificación por SMS"""
        if not user.phone:
            return False
        
        # Preparar mensaje SMS (máximo 160 caracteres)
        sms_message = self.message[:157] + "..." if len(self.message) > 160 else self.message
        
        sms_data = {
            'to': user.phone,
            'message': sms_message
        }
        
        # En producción, usar servicio SMS (Twilio, AWS SNS, etc.)
        return self._send_via_sms_service(sms_data)
    
    def _send_push_notification(self, user) -> bool:
        """Enviar notificación push"""
        # Obtener tokens de dispositivos del usuario
        device_tokens = self._get_user_device_tokens(user.id)
        
        if not device_tokens:
            return False
        
        push_data = {
            'title': self.title,
            'body': self.message,
            'icon': self.icon,
            'image': self.image_url,
            'click_action': self.action_url,
            'sound': self.sound or 'default',
            'data': {
                'notification_id': self.id,
                'type': self.notification_type.value,
                'deep_link': self.deep_link
            }
        }
        
        # En producción, usar servicio push (FCM, APNs, etc.)
        return self._send_via_push_service(device_tokens, push_data)
    
    def _send_webhook_notification(self, user) -> bool:
        """Enviar notificación vía webhook"""
        webhook_url = self._get_user_webhook_url(user.id)
        
        if not webhook_url:
            return False
        
        webhook_data = {
            'notification_id': self.id,
            'user_id': user.id,
            'type': self.notification_type.value,
            'title': self.title,
            'message': self.message,
            'priority': self.priority.value,
            'action_url': self.action_url,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': self.context_data
        }
        
        return self._send_via_webhook(webhook_url, webhook_data)
    
    def _emit_realtime_notification(self, user_id: int, notification_data: Dict[str, Any]):
        """Emitir notificación en tiempo real vía WebSocket"""
        try:
            # En producción, usar Socket.IO, Redis Pub/Sub, etc.
            from ..sockets import socketio
            
            socketio.emit('new_notification', notification_data, room=f'user_{user_id}')
            return True
            
        except Exception as e:
            print(f"Error emitiendo notificación en tiempo real: {e}")
            return False
    
    def _generate_email_html(self) -> str:
        """Generar HTML para email"""
        # Template básico de email
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{self.title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h1 style="color: #333;">{self.title}</h1>
                <p style="color: #666; line-height: 1.6;">{self.message}</p>
                {f'<a href="{self.action_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{self.action_text or "Ver más"}</a>' if self.action_url else ''}
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    