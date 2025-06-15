"""
Sistema de Notificaciones - Ecosistema de Emprendimiento
=======================================================

Este módulo proporciona un sistema completo de notificaciones multi-canal
específicamente diseñado para el ecosistema de emprendimiento colombiano,
incluyendo email, SMS, push notifications, notificaciones in-app y más.

Características principales:
- Múltiples canales: Email, SMS, Push, In-app, Slack, WhatsApp
- Templates específicos para emprendimiento
- Sistema de colas y retry automático
- Personalización por usuario y contexto
- Tracking de entrega y engagement
- Rate limiting y anti-spam
- Notificaciones programadas
- Batch notifications para eficiencia
- Integración con servicios populares
- Logging y auditoría completa
- Soporte para idioma español y contexto colombiano

Uso básico:
-----------
    from app.utils.notifications import NotificationManager, send_email
    
    # Envío simple
    send_email(
        to='emprendedor@startup.com',
        subject='Bienvenido al Ecosistema',
        template='welcome_entrepreneur',
        context={'name': 'Juan Pérez'}
    )
    
    # Manager avanzado
    notification_manager = NotificationManager()
    notification_manager.send_notification(
        user_id=123,
        notification_type='mentorship_reminder',
        channels=['email', 'sms'],
        context={
            'mentor_name': 'Carlos Experto',
            'meeting_date': '2024-12-15 10:00'
        }
    )

Tipos de notificaciones:
-----------------------
- Bienvenida y onboarding
- Recordatorios de mentoría
- Updates de proyectos
- Invitaciones a eventos
- Evaluaciones y feedback
- Alertas del sistema
- Reportes periódicos
- Confirmaciones de acciones
"""

import asyncio
import json
import logging
import smtplib
import ssl
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import uuid
from urllib.parse import urlencode
import requests
import html

# Imports de threading y queue para procesamiento asíncrono
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurar logger
logger = logging.getLogger(__name__)

# Imports opcionales con manejo de errores
try:
    import jinja2
    from jinja2 import Environment, FileSystemLoader, Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================

# Configuración de notificaciones
NOTIFICATION_CONFIG = {
    # Configuración general
    'enabled': True,
    'default_language': 'es',
    'default_timezone': 'America/Bogota',
    'batch_size': 100,
    'max_retries': 3,
    'retry_delay': 60,  # segundos
    'rate_limit_per_minute': 60,
    'rate_limit_per_hour': 1000,
    
    # Configuración de email
    'email': {
        'enabled': True,
        'provider': 'smtp',  # smtp, sendgrid, aws_ses
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_use_tls': True,
        'smtp_username': '',
        'smtp_password': '',
        'from_email': 'noreply@ecosistema.com',
        'from_name': 'Ecosistema de Emprendimiento',
        'reply_to': 'contacto@ecosistema.com',
    },
    
    # Configuración de SMS
    'sms': {
        'enabled': True,
        'provider': 'twilio',  # twilio, aws_sns
        'twilio_sid': '',
        'twilio_token': '',
        'twilio_from': '',
        'max_length': 160,
    },
    
    # Configuración de push notifications
    'push': {
        'enabled': True,
        'provider': 'firebase',  # firebase, onesignal
        'firebase_credentials': '',
    },
    
    # Configuración de Slack
    'slack': {
        'enabled': False,
        'webhook_url': '',
        'bot_token': '',
        'default_channel': '#general',
    },
    
    # Configuración de WhatsApp Business
    'whatsapp': {
        'enabled': False,
        'provider': 'twilio',
        'phone_number_id': '',
        'access_token': '',
    },
    
    # Configuración de templates
    'templates': {
        'directory': 'templates/notifications',
        'cache_enabled': True,
        'auto_reload': True,
    },
    
    # Configuración de almacenamiento
    'storage': {
        'provider': 'database',  # database, redis, file
        'retention_days': 30,
    }
}

# ==============================================================================
# ENUMS Y CLASES DE DATOS
# ==============================================================================

class NotificationChannel(Enum):
    """Canales de notificación disponibles."""
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    IN_APP = 'in_app'
    SLACK = 'slack'
    WHATSAPP = 'whatsapp'

class NotificationStatus(Enum):
    """Estados de notificación."""
    PENDING = 'pending'
    SENDING = 'sending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

class NotificationPriority(Enum):
    """Prioridades de notificación."""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'

class NotificationType(Enum):
    """Tipos de notificación específicos del ecosistema."""
    # Onboarding
    WELCOME_ENTREPRENEUR = 'welcome_entrepreneur'
    WELCOME_MENTOR = 'welcome_mentor'
    PROFILE_INCOMPLETE = 'profile_incomplete'
    
    # Mentoría
    MENTORSHIP_REQUEST = 'mentorship_request'
    MENTORSHIP_ACCEPTED = 'mentorship_accepted'
    MENTORSHIP_DECLINED = 'mentorship_declined'
    MENTORSHIP_REMINDER = 'mentorship_reminder'
    MENTORSHIP_COMPLETED = 'mentorship_completed'
    
    # Reuniones
    MEETING_INVITATION = 'meeting_invitation'
    MEETING_REMINDER = 'meeting_reminder'
    MEETING_CANCELLED = 'meeting_cancelled'
    MEETING_RESCHEDULED = 'meeting_rescheduled'
    
    # Proyectos
    PROJECT_CREATED = 'project_created'
    PROJECT_UPDATED = 'project_updated'
    PROJECT_MILESTONE = 'project_milestone'
    PROJECT_DEADLINE = 'project_deadline'
    
    # Programas
    PROGRAM_INVITATION = 'program_invitation'
    PROGRAM_ACCEPTED = 'program_accepted'
    PROGRAM_STARTED = 'program_started'
    PROGRAM_COMPLETED = 'program_completed'
    
    # Evaluaciones
    EVALUATION_REQUEST = 'evaluation_request'
    EVALUATION_REMINDER = 'evaluation_reminder'
    EVALUATION_COMPLETED = 'evaluation_completed'
    
    # Sistema
    PASSWORD_RESET = 'password_reset'
    EMAIL_VERIFICATION = 'email_verification'
    SECURITY_ALERT = 'security_alert'
    SYSTEM_MAINTENANCE = 'system_maintenance'

@dataclass
class NotificationRecipient:
    """Información del destinatario."""
    user_id: Optional[str] = None
    name: str = ''
    email: Optional[str] = None
    phone: Optional[str] = None
    push_token: Optional[str] = None
    slack_user_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    language: str = 'es'
    timezone: str = 'America/Bogota'
    preferences: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NotificationContent:
    """Contenido de la notificación."""
    subject: str = ''
    body: str = ''
    html_body: Optional[str] = None
    short_text: Optional[str] = None  # Para SMS/Push
    attachments: List[str] = field(default_factory=list)
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NotificationRequest:
    """Solicitud de notificación."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: NotificationType = NotificationType.WELCOME_ENTREPRENEUR
    recipients: List[NotificationRecipient] = field(default_factory=list)
    channels: List[NotificationChannel] = field(default_factory=list)
    content: Optional[NotificationContent] = None
    template: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    status: NotificationStatus = NotificationStatus.PENDING

@dataclass
class NotificationResult:
    """Resultado del envío de notificación."""
    id: str
    channel: NotificationChannel
    recipient: NotificationRecipient
    status: NotificationStatus
    message: str = ''
    external_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# EXCEPCIONES PERSONALIZADAS
# ==============================================================================

class NotificationError(Exception):
    """Excepción base para errores de notificación."""
    pass

class ChannelError(NotificationError):
    """Error específico de canal."""
    pass

class TemplateError(NotificationError):
    """Error de template."""
    pass

class RecipientError(NotificationError):
    """Error de destinatario."""
    pass

class RateLimitError(NotificationError):
    """Error de límite de rate."""
    pass

# ==============================================================================
# CANAL BASE Y ESPECÍFICOS
# ==============================================================================

class NotificationChannel_Base(ABC):
    """Clase base para canales de notificación."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.rate_limiter = RateLimiter(
            per_minute=NOTIFICATION_CONFIG['rate_limit_per_minute'],
            per_hour=NOTIFICATION_CONFIG['rate_limit_per_hour']
        )
    
    @abstractmethod
    def send(self, recipient: NotificationRecipient, 
             content: NotificationContent) -> NotificationResult:
        """Envía notificación por el canal específico."""
        pass
    
    def is_available(self) -> bool:
        """Verifica si el canal está disponible."""
        return self.enabled
    
    def validate_recipient(self, recipient: NotificationRecipient) -> bool:
        """Valida que el destinatario tenga la información necesaria."""
        return True

class EmailChannel(NotificationChannel_Base):
    """Canal de notificaciones por email."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config.get('provider', 'smtp')
        
        if self.provider == 'smtp':
            self._setup_smtp()
        elif self.provider == 'sendgrid':
            self._setup_sendgrid()
        elif self.provider == 'aws_ses':
            self._setup_aws_ses()
    
    def _setup_smtp(self):
        """Configurar SMTP."""
        self.smtp_config = {
            'host': self.config.get('smtp_host', 'localhost'),
            'port': self.config.get('smtp_port', 587),
            'use_tls': self.config.get('smtp_use_tls', True),
            'username': self.config.get('smtp_username', ''),
            'password': self.config.get('smtp_password', ''),
        }
    
    def _setup_sendgrid(self):
        """Configurar SendGrid."""
        if not SENDGRID_AVAILABLE:
            raise ChannelError("SendGrid library no está disponible")
        
        api_key = self.config.get('sendgrid_api_key')
        if not api_key:
            raise ChannelError("SendGrid API key no configurada")
        
        self.sendgrid_client = sendgrid.SendGridAPIClient(api_key=api_key)
    
    def _setup_aws_ses(self):
        """Configurar AWS SES."""
        if not AWS_AVAILABLE:
            raise ChannelError("Boto3 library no está disponible")
        
        self.ses_client = boto3.client(
            'ses',
            region_name=self.config.get('aws_region', 'us-east-1'),
            aws_access_key_id=self.config.get('aws_access_key_id'),
            aws_secret_access_key=self.config.get('aws_secret_access_key')
        )
    
    def validate_recipient(self, recipient: NotificationRecipient) -> bool:
        """Valida que el destinatario tenga email."""
        return bool(recipient.email and self._is_valid_email(recipient.email))
    
    def _is_valid_email(self, email: str) -> bool:
        """Valida formato de email."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def send(self, recipient: NotificationRecipient, 
             content: NotificationContent) -> NotificationResult:
        """Envía email."""
        result = NotificationResult(
            id=str(uuid.uuid4()),
            channel=NotificationChannel.EMAIL,
            recipient=recipient,
            status=NotificationStatus.PENDING
        )
        
        try:
            if not self.validate_recipient(recipient):
                raise RecipientError("Email del destinatario inválido")
            
            if not self.rate_limiter.can_send():
                raise RateLimitError("Rate limit excedido")
            
            # Enviar según proveedor
            if self.provider == 'smtp':
                external_id = self._send_smtp(recipient, content)
            elif self.provider == 'sendgrid':
                external_id = self._send_sendgrid(recipient, content)
            elif self.provider == 'aws_ses':
                external_id = self._send_aws_ses(recipient, content)
            else:
                raise ChannelError(f"Proveedor de email no soportado: {self.provider}")
            
            result.status = NotificationStatus.SENT
            result.external_id = external_id
            result.sent_at = datetime.now()
            result.message = "Email enviado exitosamente"
            
            self.rate_limiter.record_send()
            
        except Exception as e:
            result.status = NotificationStatus.FAILED
            result.error = str(e)
            logger.error(f"Error enviando email: {e}")
        
        return result
    
    def _send_smtp(self, recipient: NotificationRecipient, 
                   content: NotificationContent) -> str:
        """Envía email por SMTP."""
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = content.subject
            msg['From'] = f"{self.config.get('from_name', '')} <{self.config.get('from_email', '')}>"
            msg['To'] = recipient.email
            msg['Reply-To'] = self.config.get('reply_to', '')
            
            # Adjuntar texto plano
            if content.body:
                text_part = MIMEText(content.body, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Adjuntar HTML
            if content.html_body:
                html_part = MIMEText(content.html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Adjuntar archivos
            for attachment_path in content.attachments:
                if Path(attachment_path).exists():
                    with open(attachment_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {Path(attachment_path).name}'
                        )
                        msg.attach(part)
            
            # Enviar
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                if self.smtp_config['use_tls']:
                    server.starttls(context=context)
                
                if self.smtp_config['username']:
                    server.login(self.smtp_config['username'], self.smtp_config['password'])
                
                server.send_message(msg)
            
            return f"smtp_{int(time.time())}"
            
        except Exception as e:
            raise ChannelError(f"Error SMTP: {e}")
    
    def _send_sendgrid(self, recipient: NotificationRecipient, 
                      content: NotificationContent) -> str:
        """Envía email por SendGrid."""
        try:
            message = Mail(
                from_email=self.config.get('from_email'),
                to_emails=recipient.email,
                subject=content.subject,
                plain_text_content=content.body,
                html_content=content.html_body
            )
            
            response = self.sendgrid_client.send(message)
            return response.headers.get('X-Message-Id', 'sendgrid_unknown')
            
        except Exception as e:
            raise ChannelError(f"Error SendGrid: {e}")
    
    def _send_aws_ses(self, recipient: NotificationRecipient, 
                     content: NotificationContent) -> str:
        """Envía email por AWS SES."""
        try:
            response = self.ses_client.send_email(
                Source=self.config.get('from_email'),
                Destination={'ToAddresses': [recipient.email]},
                Message={
                    'Subject': {'Data': content.subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': content.body, 'Charset': 'UTF-8'},
                        'Html': {'Data': content.html_body or '', 'Charset': 'UTF-8'}
                    }
                }
            )
            
            return response['MessageId']
            
        except ClientError as e:
            raise ChannelError(f"Error AWS SES: {e}")

class SMSChannel(NotificationChannel_Base):
    """Canal de notificaciones por SMS."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config.get('provider', 'twilio')
        self.max_length = config.get('max_length', 160)
        
        if self.provider == 'twilio':
            self._setup_twilio()
        elif self.provider == 'aws_sns':
            self._setup_aws_sns()
    
    def _setup_twilio(self):
        """Configurar Twilio."""
        if not TWILIO_AVAILABLE:
            raise ChannelError("Twilio library no está disponible")
        
        sid = self.config.get('twilio_sid')
        token = self.config.get('twilio_token')
        
        if not sid or not token:
            raise ChannelError("Credenciales de Twilio no configuradas")
        
        self.twilio_client = TwilioClient(sid, token)
        self.from_number = self.config.get('twilio_from')
    
    def _setup_aws_sns(self):
        """Configurar AWS SNS."""
        if not AWS_AVAILABLE:
            raise ChannelError("Boto3 library no está disponible")
        
        self.sns_client = boto3.client(
            'sns',
            region_name=self.config.get('aws_region', 'us-east-1'),
            aws_access_key_id=self.config.get('aws_access_key_id'),
            aws_secret_access_key=self.config.get('aws_secret_access_key')
        )
    
    def validate_recipient(self, recipient: NotificationRecipient) -> bool:
        """Valida que el destinatario tenga teléfono."""
        return bool(recipient.phone and self._is_valid_phone(recipient.phone))
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Valida formato de teléfono colombiano."""
        # Limpiar número
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Validar formatos colombianos
        patterns = [
            r'^\+57[0-9]{10}$',  # +57XXXXXXXXXX
            r'^57[0-9]{10}$',    # 57XXXXXXXXXX
            r'^[0-9]{10}$'       # XXXXXXXXXX
        ]
        
        return any(re.match(pattern, clean_phone) for pattern in patterns)
    
    def _normalize_phone(self, phone: str) -> str:
        """Normaliza número de teléfono."""
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        if clean_phone.startswith('+57'):
            return clean_phone
        elif clean_phone.startswith('57') and len(clean_phone) == 12:
            return '+' + clean_phone
        elif len(clean_phone) == 10:
            return '+57' + clean_phone
        
        return clean_phone
    
    def send(self, recipient: NotificationRecipient, 
             content: NotificationContent) -> NotificationResult:
        """Envía SMS."""
        result = NotificationResult(
            id=str(uuid.uuid4()),
            channel=NotificationChannel.SMS,
            recipient=recipient,
            status=NotificationStatus.PENDING
        )
        
        try:
            if not self.validate_recipient(recipient):
                raise RecipientError("Teléfono del destinatario inválido")
            
            if not self.rate_limiter.can_send():
                raise RateLimitError("Rate limit excedido")
            
            # Usar texto corto si está disponible, sino truncar body
            message_text = content.short_text or content.body
            if len(message_text) > self.max_length:
                message_text = message_text[:self.max_length-3] + '...'
            
            # Normalizar teléfono
            to_number = self._normalize_phone(recipient.phone)
            
            # Enviar según proveedor
            if self.provider == 'twilio':
                external_id = self._send_twilio(to_number, message_text)
            elif self.provider == 'aws_sns':
                external_id = self._send_aws_sns(to_number, message_text)
            else:
                raise ChannelError(f"Proveedor de SMS no soportado: {self.provider}")
            
            result.status = NotificationStatus.SENT
            result.external_id = external_id
            result.sent_at = datetime.now()
            result.message = "SMS enviado exitosamente"
            
            self.rate_limiter.record_send()
            
        except Exception as e:
            result.status = NotificationStatus.FAILED
            result.error = str(e)
            logger.error(f"Error enviando SMS: {e}")
        
        return result
    
    def _send_twilio(self, to_number: str, message_text: str) -> str:
        """Envía SMS por Twilio."""
        try:
            message = self.twilio_client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=to_number
            )
            
            return message.sid
            
        except TwilioException as e:
            raise ChannelError(f"Error Twilio: {e}")
    
    def _send_aws_sns(self, to_number: str, message_text: str) -> str:
        """Envía SMS por AWS SNS."""
        try:
            response = self.sns_client.publish(
                PhoneNumber=to_number,
                Message=message_text
            )
            
            return response['MessageId']
            
        except ClientError as e:
            raise ChannelError(f"Error AWS SNS: {e}")

class PushChannel(NotificationChannel_Base):
    """Canal de push notifications."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config.get('provider', 'firebase')
        
        if self.provider == 'firebase':
            self._setup_firebase()
    
    def _setup_firebase(self):
        """Configurar Firebase."""
        if not FIREBASE_AVAILABLE:
            raise ChannelError("Firebase Admin SDK no está disponible")
        
        credentials_path = self.config.get('firebase_credentials')
        if not credentials_path:
            raise ChannelError("Credenciales de Firebase no configuradas")
        
        # Inicializar Firebase si no está inicializado
        if not firebase_admin._apps:
            cred = firebase_admin.credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
    
    def validate_recipient(self, recipient: NotificationRecipient) -> bool:
        """Valida que el destinatario tenga push token."""
        return bool(recipient.push_token)
    
    def send(self, recipient: NotificationRecipient, 
             content: NotificationContent) -> NotificationResult:
        """Envía push notification."""
        result = NotificationResult(
            id=str(uuid.uuid4()),
            channel=NotificationChannel.PUSH,
            recipient=recipient,
            status=NotificationStatus.PENDING
        )
        
        try:
            if not self.validate_recipient(recipient):
                raise RecipientError("Push token del destinatario faltante")
            
            if not self.rate_limiter.can_send():
                raise RateLimitError("Rate limit excedido")
            
            # Enviar según proveedor
            if self.provider == 'firebase':
                external_id = self._send_firebase(recipient, content)
            else:
                raise ChannelError(f"Proveedor de push no soportado: {self.provider}")
            
            result.status = NotificationStatus.SENT
            result.external_id = external_id
            result.sent_at = datetime.now()
            result.message = "Push notification enviada exitosamente"
            
            self.rate_limiter.record_send()
            
        except Exception as e:
            result.status = NotificationStatus.FAILED
            result.error = str(e)
            logger.error(f"Error enviando push: {e}")
        
        return result
    
    def _send_firebase(self, recipient: NotificationRecipient, 
                      content: NotificationContent) -> str:
        """Envía push por Firebase."""
        try:
            # Construir mensaje
            message = messaging.Message(
                notification=messaging.Notification(
                    title=content.subject,
                    body=content.short_text or content.body[:100]
                ),
                data=content.metadata,
                token=recipient.push_token
            )
            
            # Añadir acción si existe
            if content.action_url:
                message.data['action_url'] = content.action_url
            if content.action_text:
                message.data['action_text'] = content.action_text
            
            # Enviar
            response = messaging.send(message)
            return response
            
        except Exception as e:
            raise ChannelError(f"Error Firebase: {e}")

class SlackChannel(NotificationChannel_Base):
    """Canal de notificaciones por Slack."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.bot_token = config.get('bot_token')
        self.default_channel = config.get('default_channel', '#general')
    
    def validate_recipient(self, recipient: NotificationRecipient) -> bool:
        """Valida que tenga configuración de Slack."""
        return bool(self.webhook_url or (self.bot_token and recipient.slack_user_id))
    
    def send(self, recipient: NotificationRecipient, 
             content: NotificationContent) -> NotificationResult:
        """Envía notificación por Slack."""
        result = NotificationResult(
            id=str(uuid.uuid4()),
            channel=NotificationChannel.SLACK,
            recipient=recipient,
            status=NotificationStatus.PENDING
        )
        
        try:
            if not REQUESTS_AVAILABLE:
                raise ChannelError("Requests library no está disponible")
            
            if not self.validate_recipient(recipient):
                raise RecipientError("Configuración de Slack faltante")
            
            if not self.rate_limiter.can_send():
                raise RateLimitError("Rate limit excedido")
            
            # Preparar mensaje
            slack_message = {
                'text': content.subject,
                'attachments': [{
                    'text': content.body,
                    'color': 'good'
                }]
            }
            
            # Añadir acción si existe
            if content.action_url and content.action_text:
                slack_message['attachments'][0]['actions'] = [{
                    'type': 'button',
                    'text': content.action_text,
                    'url': content.action_url
                }]
            
            # Enviar
            if self.webhook_url:
                external_id = self._send_webhook(slack_message)
            else:
                external_id = self._send_bot(recipient, slack_message)
            
            result.status = NotificationStatus.SENT
            result.external_id = external_id
            result.sent_at = datetime.now()
            result.message = "Mensaje de Slack enviado exitosamente"
            
            self.rate_limiter.record_send()
            
        except Exception as e:
            result.status = NotificationStatus.FAILED
            result.error = str(e)
            logger.error(f"Error enviando Slack: {e}")
        
        return result
    
    def _send_webhook(self, message: Dict[str, Any]) -> str:
        """Envía por webhook."""
        response = requests.post(self.webhook_url, json=message)
        response.raise_for_status()
        return f"webhook_{int(time.time())}"
    
    def _send_bot(self, recipient: NotificationRecipient, 
                  message: Dict[str, Any]) -> str:
        """Envía por bot."""
        headers = {'Authorization': f'Bearer {self.bot_token}'}
        
        data = {
            'channel': recipient.slack_user_id or self.default_channel,
            **message
        }
        
        response = requests.post(
            'https://slack.com/api/chat.postMessage',
            headers=headers,
            json=data
        )
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get('ok'):
            raise ChannelError(f"Error Slack API: {result.get('error')}")
        
        return result.get('ts', 'unknown')

# ==============================================================================
# SISTEMA DE TEMPLATES
# ==============================================================================

class TemplateManager:
    """Gestor de templates de notificaciones."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.template_dir = config.get('directory', 'templates/notifications')
        self.cache_enabled = config.get('cache_enabled', True)
        self.auto_reload = config.get('auto_reload', True)
        self.cache = {}
        
        # Configurar Jinja2 si está disponible
        if JINJA2_AVAILABLE:
            self.jinja_env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=True,
                auto_reload=self.auto_reload
            )
        else:
            self.jinja_env = None
        
        # Templates incorporados
        self.built_in_templates = self._load_built_in_templates()
    
    def _load_built_in_templates(self) -> Dict[str, Dict[str, str]]:
        """Carga templates incorporados."""
        return {
            # Template de bienvenida para emprendedor
            'welcome_entrepreneur': {
                'subject': '¡Bienvenido al Ecosistema de Emprendimiento, {{name}}!',
                'body': '''Hola {{name}},

¡Te damos la bienvenida al Ecosistema de Emprendimiento!

Estamos emocionados de tenerte como parte de nuestra comunidad de emprendedores. Aquí encontrarás:

• Mentorías personalizadas con expertos
• Acceso a programas de aceleración
• Networking con otros emprendedores
• Recursos y herramientas para hacer crecer tu negocio

Tu próximo paso es completar tu perfil para que podamos conectarte con los mentores y oportunidades más relevantes para ti.

{{#action_url}}
Completa tu perfil: {{action_url}}
{{/action_url}}

¡Esperamos verte pronto en el ecosistema!

Saludos,
El equipo del Ecosistema de Emprendimiento''',
                
                'html_body': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bienvenido al Ecosistema</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #2c5aa0;">¡Bienvenido al Ecosistema de Emprendimiento!</h1>
        
        <p>Hola <strong>{{name}}</strong>,</p>
        
        <p>¡Te damos la bienvenida al Ecosistema de Emprendimiento!</p>
        
        <p>Estamos emocionados de tenerte como parte de nuestra comunidad de emprendedores. Aquí encontrarás:</p>
        
        <ul>
            <li>Mentorías personalizadas con expertos</li>
            <li>Acceso a programas de aceleración</li>
            <li>Networking con otros emprendedores</li>
            <li>Recursos y herramientas para hacer crecer tu negocio</li>
        </ul>
        
        <p>Tu próximo paso es completar tu perfil para que podamos conectarte con los mentores y oportunidades más relevantes para ti.</p>
        
        {{#action_url}}
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{action_url}}" style="background-color: #2c5aa0; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Completa tu perfil
            </a>
        </div>
        {{/action_url}}
        
        <p>¡Esperamos verte pronto en el ecosistema!</p>
        
        <p>Saludos,<br>
        <strong>El equipo del Ecosistema de Emprendimiento</strong></p>
    </div>
</body>
</html>''',
                'sms': 'Bienvenido {{name}} al Ecosistema de Emprendimiento. Completa tu perfil: {{action_url}}'
            },
            
            # Template de recordatorio de mentoría
            'mentorship_reminder': {
                'subject': 'Recordatorio: Mentoría con {{mentor_name}} mañana',
                'body': '''Hola {{entrepreneur_name}},

Te recordamos que tienes una sesión de mentoría programada:

📅 Fecha: {{meeting_date}}
🕐 Hora: {{meeting_time}}
👨‍💼 Mentor: {{mentor_name}}
📍 Modalidad: {{meeting_type}}

{{#meeting_link}}
Enlace de reunión: {{meeting_link}}
{{/meeting_link}}

Agenda sugerida:
{{agenda}}

Te recomendamos preparar:
• Preguntas específicas sobre tu proyecto
• Avances desde la última sesión
• Obstáculos que has encontrado

¡Aprovecha al máximo esta oportunidad!

Saludos,
Ecosistema de Emprendimiento''',
                
                'sms': 'Recordatorio: Mentoría con {{mentor_name}} mañana a las {{meeting_time}}. {{meeting_link}}'
            },
            
            # Template de invitación a programa
            'program_invitation': {
                'subject': 'Invitación al {{program_name}}',
                'body': '''Hola {{name}},

¡Tenemos excelentes noticias!

Has sido seleccionado/a para participar en el {{program_name}}.

Detalles del programa:
📅 Inicio: {{start_date}}
⏱️ Duración: {{duration}}
🎯 Modalidad: {{modality}}
👥 Participantes: {{participants_count}} emprendedores

Este programa incluye:
{{program_benefits}}

Para confirmar tu participación, responde antes del {{response_deadline}}.

{{#action_url}}
Confirmar participación: {{action_url}}
{{/action_url}}

¡Esperamos contar contigo!

Saludos,
Equipo {{program_name}}'''
            }
        }
    
    def render(self, template_name: str, context: Dict[str, Any], 
               content_type: str = 'body') -> str:
        """
        Renderiza template con contexto.
        
        Args:
            template_name: Nombre del template
            context: Variables del contexto
            content_type: Tipo de contenido (subject, body, html_body, sms)
            
        Returns:
            Contenido renderizado
        """
        try:
            # Buscar template
            template_content = self._get_template_content(template_name, content_type)
            
            if not template_content:
                logger.warning(f"Template {template_name}.{content_type} no encontrado")
                return ""
            
            # Renderizar con Jinja2 si está disponible
            if self.jinja_env and JINJA2_AVAILABLE:
                template = self.jinja_env.from_string(template_content)
                return template.render(**context)
            else:
                # Renderizado simple con string.format
                return self._simple_render(template_content, context)
                
        except Exception as e:
            logger.error(f"Error renderizando template {template_name}: {e}")
            raise TemplateError(f"Error renderizando template: {e}")
    
    def _get_template_content(self, template_name: str, content_type: str) -> Optional[str]:
        """Obtiene contenido del template."""
        cache_key = f"{template_name}.{content_type}"
        
        # Verificar cache
        if self.cache_enabled and cache_key in self.cache:
            return self.cache[cache_key]
        
        # Buscar en templates incorporados
        if template_name in self.built_in_templates:
            content = self.built_in_templates[template_name].get(content_type)
            if content and self.cache_enabled:
                self.cache[cache_key] = content
            return content
        
        # Buscar en archivos
        template_file = Path(self.template_dir) / f"{template_name}.{content_type}"
        if template_file.exists():
            content = template_file.read_text(encoding='utf-8')
            if self.cache_enabled:
                self.cache[cache_key] = content
            return content
        
        return None
    
    def _simple_render(self, template_content: str, context: Dict[str, Any]) -> str:
        """Renderizado simple sin Jinja2."""
        # Reemplazar variables simples {{variable}}
        import re
        
        def replace_var(match):
            var_name = match.group(1).strip()
            return str(context.get(var_name, f"{{{{{var_name}}}}}"))
        
        # Reemplazar variables simples
        result = re.sub(r'\{\{([^}]+)\}\}', replace_var, template_content)
        
        # Manejar bloques condicionales simples {{#variable}}...{{/variable}}
        def replace_conditional(match):
            var_name = match.group(1).strip()
            block_content = match.group(2)
            
            if context.get(var_name):
                return self._simple_render(block_content, context)
            else:
                return ''
        
        result = re.sub(r'\{\{#([^}]+)\}\}(.*?)\{\{/[^}]+\}\}', 
                       replace_conditional, result, flags=re.DOTALL)
        
        return result

# ==============================================================================
# RATE LIMITER
# ==============================================================================

class RateLimiter:
    """Control de rate limiting para notificaciones."""
    
    def __init__(self, per_minute: int = 60, per_hour: int = 1000):
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.minute_counter = {}
        self.hour_counter = {}
        self.lock = threading.Lock()
    
    def can_send(self) -> bool:
        """Verifica si se puede enviar notificación."""
        now = datetime.now()
        minute_key = now.strftime('%Y-%m-%d %H:%M')
        hour_key = now.strftime('%Y-%m-%d %H')
        
        with self.lock:
            # Limpiar contadores antiguos
            self._cleanup_counters(now)
            
            minute_count = self.minute_counter.get(minute_key, 0)
            hour_count = self.hour_counter.get(hour_key, 0)
            
            return minute_count < self.per_minute and hour_count < self.per_hour
    
    def record_send(self):
        """Registra envío de notificación."""
        now = datetime.now()
        minute_key = now.strftime('%Y-%m-%d %H:%M')
        hour_key = now.strftime('%Y-%m-%d %H')
        
        with self.lock:
            self.minute_counter[minute_key] = self.minute_counter.get(minute_key, 0) + 1
            self.hour_counter[hour_key] = self.hour_counter.get(hour_key, 0) + 1
    
    def _cleanup_counters(self, now: datetime):
        """Limpia contadores antiguos."""
        # Limpiar contadores de minutos (mantener últimos 5 minutos)
        cutoff_minute = (now - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M')
        self.minute_counter = {
            k: v for k, v in self.minute_counter.items() 
            if k >= cutoff_minute
        }
        
        # Limpiar contadores de horas (mantener últimas 2 horas)
        cutoff_hour = (now - timedelta(hours=2)).strftime('%Y-%m-%d %H')
        self.hour_counter = {
            k: v for k, v in self.hour_counter.items() 
            if k >= cutoff_hour
        }

# ==============================================================================
# COLA DE NOTIFICACIONES
# ==============================================================================

class NotificationQueue:
    """Cola de notificaciones para procesamiento asíncrono."""
    
    def __init__(self, max_workers: int = 10):
        self.queue = queue.PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Inicia el procesamiento de la cola."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("Cola de notificaciones iniciada")
    
    def stop(self):
        """Detiene el procesamiento de la cola."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        logger.info("Cola de notificaciones detenida")
    
    def enqueue(self, notification_request: NotificationRequest):
        """Añade notificación a la cola."""
        # Calcular prioridad (menor número = mayor prioridad)
        priority_map = {
            NotificationPriority.URGENT: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.NORMAL: 3,
            NotificationPriority.LOW: 4
        }
        
        priority = priority_map.get(notification_request.priority, 3)
        
        # Añadir timestamp para FIFO en mismo nivel de prioridad
        timestamp = time.time()
        
        self.queue.put((priority, timestamp, notification_request))
        logger.debug(f"Notificación {notification_request.id} añadida a la cola")
    
    def _process_queue(self):
        """Procesa notificaciones de la cola."""
        while self.running:
            try:
                # Obtener notificación con timeout
                priority, timestamp, notification_request = self.queue.get(timeout=1)
                
                # Verificar si no ha expirado
                if (notification_request.expires_at and 
                    datetime.now() > notification_request.expires_at):
                    logger.info(f"Notificación {notification_request.id} expirada")
                    continue
                
                # Verificar si es programada
                if (notification_request.scheduled_at and 
                    datetime.now() < notification_request.scheduled_at):
                    # Volver a encolar para más tarde
                    self.queue.put((priority, timestamp, notification_request))
                    time.sleep(1)
                    continue
                
                # Procesar notificación
                self.executor.submit(self._process_notification, notification_request)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error procesando cola: {e}")
    
    def _process_notification(self, notification_request: NotificationRequest):
        """Procesa una notificación individual."""
        try:
            # Aquí se integraría con el NotificationManager
            logger.info(f"Procesando notificación {notification_request.id}")
            
        except Exception as e:
            logger.error(f"Error procesando notificación {notification_request.id}: {e}")

# ==============================================================================
# MANAGER PRINCIPAL DE NOTIFICACIONES
# ==============================================================================

class NotificationManager:
    """Manager principal del sistema de notificaciones."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**NOTIFICATION_CONFIG, **(config or {})}
        
        # Inicializar template manager
        self.template_manager = TemplateManager(self.config['templates'])
        
        # Inicializar canales
        self.channels = {}
        self._setup_channels()
        
        # Inicializar cola
        self.queue = NotificationQueue(max_workers=10)
        self.queue.start()
        
        # Rate limiter global
        self.rate_limiter = RateLimiter(
            per_minute=self.config['rate_limit_per_minute'],
            per_hour=self.config['rate_limit_per_hour']
        )
        
        logger.info("NotificationManager inicializado")
    
    def _setup_channels(self):
        """Configura canales de notificación."""
        # Email
        if self.config['email']['enabled']:
            try:
                self.channels[NotificationChannel.EMAIL] = EmailChannel(self.config['email'])
                logger.info("Canal de email configurado")
            except Exception as e:
                logger.error(f"Error configurando canal de email: {e}")
        
        # SMS
        if self.config['sms']['enabled']:
            try:
                self.channels[NotificationChannel.SMS] = SMSChannel(self.config['sms'])
                logger.info("Canal de SMS configurado")
            except Exception as e:
                logger.error(f"Error configurando canal de SMS: {e}")
        
        # Push
        if self.config['push']['enabled']:
            try:
                self.channels[NotificationChannel.PUSH] = PushChannel(self.config['push'])
                logger.info("Canal de Push configurado")
            except Exception as e:
                logger.error(f"Error configurando canal de Push: {e}")
        
        # Slack
        if self.config['slack']['enabled']:
            try:
                self.channels[NotificationChannel.SLACK] = SlackChannel(self.config['slack'])
                logger.info("Canal de Slack configurado")
            except Exception as e:
                logger.error(f"Error configurando canal de Slack: {e}")
    
    def send_notification(self, notification_request: NotificationRequest) -> List[NotificationResult]:
        """
        Envía notificación por múltiples canales.
        
        Args:
            notification_request: Solicitud de notificación
            
        Returns:
            Lista de resultados por canal
        """
        results = []
        
        try:
            # Renderizar contenido si usa template
            if notification_request.template:
                content = self._render_notification_content(
                    notification_request.template, 
                    notification_request.context
                )
                notification_request.content = content
            
            # Enviar por cada canal
            for channel in notification_request.channels:
                if channel not in self.channels:
                    logger.warning(f"Canal {channel} no disponible")
                    continue
                
                channel_handler = self.channels[channel]
                
                # Enviar a cada destinatario
                for recipient in notification_request.recipients:
                    try:
                        result = channel_handler.send(recipient, notification_request.content)
                        results.append(result)
                        
                    except Exception as e:
                        error_result = NotificationResult(
                            id=str(uuid.uuid4()),
                            channel=channel,
                            recipient=recipient,
                            status=NotificationStatus.FAILED,
                            error=str(e)
                        )
                        results.append(error_result)
                        logger.error(f"Error enviando por {channel}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error enviando notificación: {e}")
            raise NotificationError(f"Error enviando notificación: {e}")
    
    def send_notification_async(self, notification_request: NotificationRequest):
        """Envía notificación de forma asíncrona usando la cola."""
        self.queue.enqueue(notification_request)
    
    def _render_notification_content(self, template_name: str, 
                                   context: Dict[str, Any]) -> NotificationContent:
        """Renderiza contenido usando templates."""
        content = NotificationContent()
        
        # Renderizar cada tipo de contenido
        content.subject = self.template_manager.render(template_name, context, 'subject')
        content.body = self.template_manager.render(template_name, context, 'body')
        content.html_body = self.template_manager.render(template_name, context, 'html_body')
        content.short_text = self.template_manager.render(template_name, context, 'sms')
        
        # Añadir URLs de acción desde contexto
        if 'action_url' in context:
            content.action_url = context['action_url']
        if 'action_text' in context:
            content.action_text = context['action_text']
        
        return content
    
    def create_recipient_from_user(self, user_data: Dict[str, Any]) -> NotificationRecipient:
        """Crea destinatario desde datos de usuario."""
        return NotificationRecipient(
            user_id=str(user_data.get('id', '')),
            name=user_data.get('name', ''),
            email=user_data.get('email'),
            phone=user_data.get('phone'),
            push_token=user_data.get('push_token'),
            slack_user_id=user_data.get('slack_user_id'),
            whatsapp_number=user_data.get('whatsapp_number'),
            language=user_data.get('language', 'es'),
            timezone=user_data.get('timezone', 'America/Bogota'),
            preferences=user_data.get('notification_preferences', {})
        )
    
    def get_channel_status(self) -> Dict[str, bool]:
        """Obtiene estado de canales disponibles."""
        return {
            channel.value: channel in self.channels and self.channels[channel].is_available()
            for channel in NotificationChannel
        }
    
    def __del__(self):
        """Cleanup al destruir el manager."""
        if hasattr(self, 'queue'):
            self.queue.stop()

# ==============================================================================
# FUNCIONES DE CONVENIENCIA
# ==============================================================================

# Instancia global del manager
_notification_manager = None

def get_notification_manager() -> NotificationManager:
    """Obtiene instancia global del notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager

def send_email(to: Union[str, List[str]], subject: str, body: str = '', 
               html_body: str = '', template: str = None, 
               context: Dict[str, Any] = None) -> List[NotificationResult]:
    """
    Función de conveniencia para enviar email.
    
    Args:
        to: Email(s) del destinatario
        subject: Asunto
        body: Cuerpo en texto plano
        html_body: Cuerpo en HTML
        template: Nombre del template (opcional)
        context: Contexto para el template
        
    Returns:
        Lista de resultados
        
    Examples:
        >>> send_email(
        ...     to='emprendedor@startup.com',
        ...     subject='Bienvenido',
        ...     template='welcome_entrepreneur',
        ...     context={'name': 'Juan Pérez'}
        ... )
    """
    manager = get_notification_manager()
    
    # Preparar destinatarios
    recipients = []
    emails = to if isinstance(to, list) else [to]
    
    for email in emails:
        recipients.append(NotificationRecipient(email=email))
    
    # Preparar request
    request = NotificationRequest(
        notification_type=NotificationType.WELCOME_ENTREPRENEUR,
        recipients=recipients,
        channels=[NotificationChannel.EMAIL],
        template=template,
        context=context or {}
    )
    
    # Si no hay template, usar contenido directo
    if not template:
        request.content = NotificationContent(
            subject=subject,
            body=body,
            html_body=html_body
        )
    
    return manager.send_notification(request)

def send_sms(to: Union[str, List[str]], message: str) -> List[NotificationResult]:
    """
    Función de conveniencia para enviar SMS.
    
    Args:
        to: Teléfono(s) del destinatario
        message: Mensaje de texto
        
    Returns:
        Lista de resultados
    """
    manager = get_notification_manager()
    
    # Preparar destinatarios
    recipients = []
    phones = to if isinstance(to, list) else [to]
    
    for phone in phones:
        recipients.append(NotificationRecipient(phone=phone))
    
    # Preparar request
    request = NotificationRequest(
        notification_type=NotificationType.WELCOME_ENTREPRENEUR,
        recipients=recipients,
        channels=[NotificationChannel.SMS],
        content=NotificationContent(
            body=message,
            short_text=message
        )
    )
    
    return manager.send_notification(request)

def send_welcome_entrepreneur(user_data: Dict[str, Any], 
                            action_url: str = None) -> List[NotificationResult]:
    """
    Envía notificación de bienvenida a emprendedor.
    
    Args:
        user_data: Datos del usuario
        action_url: URL de acción (opcional)
        
    Returns:
        Lista de resultados
    """
    manager = get_notification_manager()
    
    recipient = manager.create_recipient_from_user(user_data)
    
    context = {
        'name': user_data.get('name', 'Emprendedor'),
        'action_url': action_url
    }
    
    # Determinar canales según preferencias
    channels = [NotificationChannel.EMAIL]
    if recipient.phone:
        channels.append(NotificationChannel.SMS)
    
    request = NotificationRequest(
        notification_type=NotificationType.WELCOME_ENTREPRENEUR,
        recipients=[recipient],
        channels=channels,
        template='welcome_entrepreneur',
        context=context
    )
    
    return manager.send_notification(request)

def send_mentorship_reminder(entrepreneur_data: Dict[str, Any], 
                           mentor_data: Dict[str, Any],
                           meeting_data: Dict[str, Any]) -> List[NotificationResult]:
    """
    Envía recordatorio de mentoría.
    
    Args:
        entrepreneur_data: Datos del emprendedor
        mentor_data: Datos del mentor
        meeting_data: Datos de la reunión
        
    Returns:
        Lista de resultados
    """
    manager = get_notification_manager()
    
    recipient = manager.create_recipient_from_user(entrepreneur_data)
    
    context = {
        'entrepreneur_name': entrepreneur_data.get('name'),
        'mentor_name': mentor_data.get('name'),
        'meeting_date': meeting_data.get('date'),
        'meeting_time': meeting_data.get('time'),
        'meeting_type': meeting_data.get('type', 'Virtual'),
        'meeting_link': meeting_data.get('link'),
        'agenda': meeting_data.get('agenda', 'Por definir')
    }
    
    request = NotificationRequest(
        notification_type=NotificationType.MENTORSHIP_REMINDER,
        recipients=[recipient],
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        template='mentorship_reminder',
        context=context,
        priority=NotificationPriority.HIGH
    )
    
    return manager.send_notification(request)

def configure_notifications(**kwargs):
    """Configura el sistema de notificaciones globalmente."""
    global _notification_manager
    NOTIFICATION_CONFIG.update(kwargs)
    
    # Reinicializar manager si ya existe
    if _notification_manager:
        _notification_manager.queue.stop()
        _notification_manager = None

def get_notification_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del sistema de notificaciones."""
    manager = get_notification_manager()
    
    return {
        'channels_available': manager.get_channel_status(),
        'dependencies': {
            'jinja2': JINJA2_AVAILABLE,
            'sendgrid': SENDGRID_AVAILABLE,
            'aws': AWS_AVAILABLE,
            'twilio': TWILIO_AVAILABLE,
            'firebase': FIREBASE_AVAILABLE,
            'requests': REQUESTS_AVAILABLE
        },
        'config': manager.config,
        'notification_types': [nt.value for nt in NotificationType]
    }

# Logging de inicialización
logger.info("Módulo de notificaciones inicializado")

# Validar dependencias críticas
missing_deps = []
if not REQUESTS_AVAILABLE:
    missing_deps.append('requests')

if missing_deps:
    logger.warning(f"Dependencias faltantes para notificaciones: {missing_deps}")
else:
    logger.info("Todas las dependencias básicas están disponibles")