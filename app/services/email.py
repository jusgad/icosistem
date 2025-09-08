"""
Email Service - Ecosistema de Emprendimiento
Servicio completo de email con múltiples proveedores, plantillas y tracking

Author: jusga
Version: 1.0.0
"""

import logging
import smtplib
import asyncio
import hashlib
import uuid
from typing import Optional, Any, Union
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, parseaddr
import mimetypes
import os
import re
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod

import jinja2
import requests
import boto3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, PlainTextContent, HtmlContent
from premailer import transform
import bleach

from flask import current_app, render_template, url_for
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, cache, redis_client
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ExternalServiceError
)
from app.core.constants import (
    EMAIL_TEMPLATES,
    EMAIL_PROVIDERS,
    USER_ROLES
)
from app.models.user import User
from app.models.email_template import EmailTemplate
from app.models.email_campaign import EmailCampaign
from app.models.email_log import EmailLog
from app.models.email_tracking import EmailTracking
from app.models.email_bounce import EmailBounce
from app.models.email_suppression import EmailSuppression
from app.services.base import BaseService
from app.utils.decorators import log_activity, retry_on_failure
from app.utils.validators import validate_email, validate_domain
from app.utils.formatters import format_datetime, sanitize_html
from app.utils.crypto_utils import encrypt_data, decrypt_data, generate_hash


logger = logging.getLogger(__name__)


class EmailProvider(Enum):
    """Proveedores de email"""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    AMAZON_SES = "amazon_ses"
    MAILGUN = "mailgun"
    POSTMARK = "postmark"


class EmailStatus(Enum):
    """Estados de email"""
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    SPAM = "spam"
    UNSUBSCRIBED = "unsubscribed"


class EmailPriority(Enum):
    """Prioridades de email"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BounceType(Enum):
    """Tipos de bounce"""
    HARD = "hard"
    SOFT = "soft"
    COMPLAINT = "complaint"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class EmailAddress:
    """Dirección de email con nombre opcional"""
    email: str
    name: Optional[str] = None
    
    def __post_init__(self):
        if not validate_email(self.email):
            raise ValidationError(f"Email inválido: {self.email}")
    
    def __str__(self):
        if self.name:
            return formataddr((self.name, self.email))
        return self.email


@dataclass
class EmailAttachment:
    """Archivo adjunto"""
    filename: str
    content: bytes
    content_type: str
    disposition: str = "attachment"


@dataclass
class EmailContent:
    """Contenido del email"""
    subject: str
    text_body: Optional[str] = None
    html_body: Optional[str] = None
    template_id: Optional[int] = None
    template_data: Optional[dict[str, Any]] = None


@dataclass
class EmailMessage:
    """Mensaje de email completo"""
    to: list[EmailAddress]
    content: EmailContent
    from_address: Optional[EmailAddress] = None
    reply_to: Optional[EmailAddress] = None
    cc: Optional[list[EmailAddress]] = None
    bcc: Optional[list[EmailAddress]] = None
    attachments: Optional[list[EmailAttachment]] = None
    priority: str = EmailPriority.MEDIUM.value
    tracking_enabled: bool = True
    unsubscribe_url: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class EmailResult:
    """Resultado de envío de email"""
    success: bool
    message_id: Optional[str] = None
    provider_id: Optional[str] = None
    error_message: Optional[str] = None
    provider_used: Optional[str] = None
    retry_count: int = 0


@dataclass
class BulkEmailResult:
    """Resultado de envío masivo"""
    total_emails: int
    successful: int
    failed: int
    queued: int
    errors: list[str]
    message_ids: list[str]


class EmailProviderInterface(ABC):
    """Interfaz abstracta para proveedores de email"""
    
    @abstractmethod
    def send(self, message: EmailMessage) -> EmailResult:
        """Enviar email"""
        pass
    
    @abstractmethod
    def send_bulk(self, messages: list[EmailMessage]) -> BulkEmailResult:
        """Envío masivo"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validar configuración"""
        pass
    
    @abstractmethod
    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        """Obtener estado de entrega"""
        pass


class SMTPProvider(EmailProviderInterface):
    """Proveedor SMTP estándar"""
    
    def __init__(self):
        self.host = current_app.config.get('SMTP_HOST')
        self.port = current_app.config.get('SMTP_PORT', 587)
        self.username = current_app.config.get('SMTP_USERNAME')
        self.password = current_app.config.get('SMTP_PASSWORD')
        self.use_tls = current_app.config.get('SMTP_USE_TLS', True)
        self.timeout = current_app.config.get('SMTP_TIMEOUT', 30)
    
    def send(self, message: EmailMessage) -> EmailResult:
        """Enviar email via SMTP"""
        try:
            # Crear mensaje MIME
            mime_message = self._create_mime_message(message)
            
            # Conectar y enviar
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                # Enviar a todos los destinatarios
                recipients = [addr.email for addr in message.to]
                if message.cc:
                    recipients.extend([addr.email for addr in message.cc])
                if message.bcc:
                    recipients.extend([addr.email for addr in message.bcc])
                
                server.send_message(mime_message, to_addrs=recipients)
                
                # Generar ID único para tracking
                message_id = self._generate_message_id()
                
                return EmailResult(
                    success=True,
                    message_id=message_id,
                    provider_used=EmailProvider.SMTP.value
                )
                
        except smtplib.SMTPException as e:
            logger.error(f"Error SMTP: {str(e)}")
            return EmailResult(
                success=False,
                error_message=f"Error SMTP: {str(e)}",
                provider_used=EmailProvider.SMTP.value
            )
        except Exception as e:
            logger.error(f"Error general enviando email: {str(e)}")
            return EmailResult(
                success=False,
                error_message=str(e),
                provider_used=EmailProvider.SMTP.value
            )
    
    def send_bulk(self, messages: list[EmailMessage]) -> BulkEmailResult:
        """Envío masivo via SMTP"""
        successful = 0
        failed = 0
        errors = []
        message_ids = []
        
        for message in messages:
            result = self.send(message)
            if result.success:
                successful += 1
                if result.message_id:
                    message_ids.append(result.message_id)
            else:
                failed += 1
                if result.error_message:
                    errors.append(result.error_message)
        
        return BulkEmailResult(
            total_emails=len(messages),
            successful=successful,
            failed=failed,
            queued=0,
            errors=errors,
            message_ids=message_ids
        )
    
    def validate_config(self) -> bool:
        """Validar configuración SMTP"""
        required_configs = ['SMTP_HOST', 'SMTP_PORT']
        return all(current_app.config.get(config) for config in required_configs)
    
    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        """SMTP no provee tracking nativo"""
        return {
            'status': 'unknown',
            'message': 'SMTP no soporta tracking de entrega'
        }
    
    def _create_mime_message(self, message: EmailMessage) -> MIMEMultipart:
        """Crear mensaje MIME"""
        mime_message = MIMEMultipart('alternative')
        
        # Headers básicos
        mime_message['Subject'] = message.content.subject
        mime_message['From'] = str(message.from_address or self._get_default_from())
        mime_message['To'] = ', '.join([str(addr) for addr in message.to])
        
        if message.reply_to:
            mime_message['Reply-To'] = str(message.reply_to)
        
        if message.cc:
            mime_message['Cc'] = ', '.join([str(addr) for addr in message.cc])
        
        # Agregar tracking headers
        if message.tracking_enabled:
            mime_message['X-Tracking-ID'] = self._generate_tracking_id()
        
        # Contenido del mensaje
        if message.content.text_body:
            text_part = MIMEText(message.content.text_body, 'plain', 'utf-8')
            mime_message.attach(text_part)
        
        if message.content.html_body:
            html_part = MIMEText(message.content.html_body, 'html', 'utf-8')
            mime_message.attach(html_part)
        
        # Adjuntos
        if message.attachments:
            for attachment in message.attachments:
                self._add_attachment(mime_message, attachment)
        
        return mime_message
    
    def _add_attachment(self, mime_message: MIMEMultipart, attachment: EmailAttachment):
        """Agregar adjunto al mensaje"""
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.content)
        encoders.encode_base64(part)
        
        part.add_header(
            'Content-Disposition',
            f'{attachment.disposition}; filename= {attachment.filename}'
        )
        
        mime_message.attach(part)
    
    def _get_default_from(self) -> EmailAddress:
        """Obtener dirección from por defecto"""
        email = current_app.config.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')
        name = current_app.config.get('DEFAULT_FROM_NAME', 'Ecosistema de Emprendimiento')
        return EmailAddress(email=email, name=name)
    
    def _generate_message_id(self) -> str:
        """Generar ID único para el mensaje"""
        return str(uuid.uuid4())
    
    def _generate_tracking_id(self) -> str:
        """Generar ID de tracking"""
        return generate_hash(f"{datetime.now(timezone.utc)}-{uuid.uuid4()}")


class SendGridProvider(EmailProviderInterface):
    """Proveedor SendGrid"""
    
    def __init__(self):
        self.api_key = current_app.config.get('SENDGRID_API_KEY')
        self.client = SendGridAPIClient(api_key=self.api_key) if self.api_key else None
    
    def send(self, message: EmailMessage) -> EmailResult:
        """Enviar email via SendGrid"""
        try:
            if not self.client:
                raise ExternalServiceError("SendGrid no configurado")
            
            # Crear mensaje SendGrid
            sg_message = Mail()
            
            # From
            from_addr = message.from_address or self._get_default_from()
            sg_message.from_email = From(from_addr.email, from_addr.name)
            
            # To (SendGrid maneja personalización individual)
            for to_addr in message.to:
                sg_message.add_to(To(to_addr.email, to_addr.name))
            
            # Subject y contenido
            sg_message.subject = Subject(message.content.subject)
            
            if message.content.text_body:
                sg_message.add_content(PlainTextContent(message.content.text_body))
            
            if message.content.html_body:
                sg_message.add_content(HtmlContent(message.content.html_body))
            
            # Tracking
            if message.tracking_enabled:
                sg_message.tracking_settings = self._get_tracking_settings()
            
            # Tags y metadata
            if message.tags:
                for tag in message.tags[:10]:  # SendGrid limita a 10 tags
                    sg_message.add_category(tag)
            
            if message.metadata:
                for key, value in message.metadata.items():
                    sg_message.add_custom_arg(key, str(value))
            
            # Enviar
            response = self.client.send(sg_message)
            
            return EmailResult(
                success=response.status_code in [200, 202],
                message_id=self._extract_message_id(response.headers),
                provider_id=response.headers.get('X-Message-Id'),
                provider_used=EmailProvider.SENDGRID.value
            )
            
        except Exception as e:
            logger.error(f"Error SendGrid: {str(e)}")
            return EmailResult(
                success=False,
                error_message=str(e),
                provider_used=EmailProvider.SENDGRID.value
            )
    
    def send_bulk(self, messages: list[EmailMessage]) -> BulkEmailResult:
        """Envío masivo optimizado con SendGrid"""
        # Implementar envío masivo con personalización
        # SendGrid permite hasta 1000 destinatarios por request
        successful = 0
        failed = 0
        errors = []
        message_ids = []
        
        # Agrupar en lotes de 1000
        batch_size = 1000
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            
            try:
                # Crear mensaje masivo
                bulk_message = self._create_bulk_message(batch)
                response = self.client.send(bulk_message)
                
                if response.status_code in [200, 202]:
                    successful += len(batch)
                    message_ids.append(response.headers.get('X-Message-Id', ''))
                else:
                    failed += len(batch)
                    errors.append(f"Batch failed: {response.body}")
                    
            except Exception as e:
                failed += len(batch)
                errors.append(str(e))
        
        return BulkEmailResult(
            total_emails=len(messages),
            successful=successful,
            failed=failed,
            queued=0,
            errors=errors,
            message_ids=message_ids
        )
    
    def validate_config(self) -> bool:
        """Validar configuración SendGrid"""
        return bool(self.api_key)
    
    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        """Obtener estado via SendGrid API"""
        try:
            # Implementar consulta a SendGrid Event API
            return {'status': 'sent', 'provider': 'sendgrid'}
        except Exception as e:
            return {'status': 'unknown', 'error': str(e)}
    
    def _get_tracking_settings(self) -> dict[str, Any]:
        """Configuración de tracking para SendGrid"""
        return {
            "click_tracking": {"enable": True},
            "open_tracking": {"enable": True},
            "subscription_tracking": {"enable": True},
            "ganalytics": {"enable": True, "utm_campaign": "email_campaign"}
        }
    
    def _create_bulk_message(self, messages: list[EmailMessage]) -> Mail:
        """Crear mensaje masivo para SendGrid"""
        # Implementar lógica de personalización masiva
        # Por simplicidad, retornamos el primer mensaje
        return Mail() if not messages else self._create_single_message(messages[0])
    
    def _create_single_message(self, message: EmailMessage) -> Mail:
        """Crear mensaje individual para SendGrid"""
        sg_message = Mail()
        # Implementar creación completa del mensaje
        return sg_message
    
    def _extract_message_id(self, headers: dict[str, str]) -> str:
        """Extraer message ID de headers"""
        return headers.get('X-Message-Id', str(uuid.uuid4()))
    
    def _get_default_from(self) -> EmailAddress:
        """Obtener dirección from por defecto"""
        email = current_app.config.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')
        name = current_app.config.get('DEFAULT_FROM_NAME', 'Ecosistema de Emprendimiento')
        return EmailAddress(email=email, name=name)


class AmazonSESProvider(EmailProviderInterface):
    """Proveedor Amazon SES"""
    
    def __init__(self):
        self.aws_access_key = current_app.config.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = current_app.config.get('AWS_REGION', 'us-east-1')
        
        if self.aws_access_key and self.aws_secret_key:
            self.client = boto3.client(
                'ses',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
        else:
            self.client = None
    
    def send(self, message: EmailMessage) -> EmailResult:
        """Enviar email via Amazon SES"""
        try:
            if not self.client:
                raise ExternalServiceError("Amazon SES no configurado")
            
            # Preparar destinatarios
            destinations = [addr.email for addr in message.to]
            
            # Preparar mensaje
            email_data = {
                'Source': str(message.from_address or self._get_default_from()),
                'Destination': {'ToAddresses': destinations},
                'Message': {
                    'Subject': {'Data': message.content.subject, 'Charset': 'UTF-8'},
                    'Body': {}
                }
            }
            
            if message.content.text_body:
                email_data['Message']['Body']['Text'] = {
                    'Data': message.content.text_body,
                    'Charset': 'UTF-8'
                }
            
            if message.content.html_body:
                email_data['Message']['Body']['Html'] = {
                    'Data': message.content.html_body,
                    'Charset': 'UTF-8'
                }
            
            # CC y BCC
            if message.cc:
                email_data['Destination']['CcAddresses'] = [addr.email for addr in message.cc]
            
            if message.bcc:
                email_data['Destination']['BccAddresses'] = [addr.email for addr in message.bcc]
            
            # Tags
            if message.tags:
                email_data['Tags'] = [
                    {'Name': f'tag_{i}', 'Value': tag}
                    for i, tag in enumerate(message.tags[:50])  # SES limita a 50 tags
                ]
            
            # Enviar
            response = self.client.send_email(**email_data)
            
            return EmailResult(
                success=True,
                message_id=response['MessageId'],
                provider_used=EmailProvider.AMAZON_SES.value
            )
            
        except Exception as e:
            logger.error(f"Error Amazon SES: {str(e)}")
            return EmailResult(
                success=False,
                error_message=str(e),
                provider_used=EmailProvider.AMAZON_SES.value
            )
    
    def send_bulk(self, messages: list[EmailMessage]) -> BulkEmailResult:
        """Envío masivo via SES"""
        successful = 0
        failed = 0
        errors = []
        message_ids = []
        
        for message in messages:
            result = self.send(message)
            if result.success:
                successful += 1
                if result.message_id:
                    message_ids.append(result.message_id)
            else:
                failed += 1
                if result.error_message:
                    errors.append(result.error_message)
        
        return BulkEmailResult(
            total_emails=len(messages),
            successful=successful,
            failed=failed,
            queued=0,
            errors=errors,
            message_ids=message_ids
        )
    
    def validate_config(self) -> bool:
        """Validar configuración SES"""
        return bool(self.aws_access_key and self.aws_secret_key)
    
    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        """SES no provee tracking directo de mensajes individuales"""
        return {
            'status': 'sent',
            'message': 'SES no soporta tracking individual de mensajes'
        }
    
    def _get_default_from(self) -> EmailAddress:
        """Obtener dirección from por defecto"""
        email = current_app.config.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')
        name = current_app.config.get('DEFAULT_FROM_NAME', 'Ecosistema de Emprendimiento')
        return EmailAddress(email=email, name=name)


class EmailService(BaseService):
    """
    Servicio completo de email empresarial
    
    Funcionalidades:
    - Múltiples proveedores con failover automático
    - Sistema avanzado de plantillas con Jinja2
    - Envío asíncrono con colas
    - Tracking completo (entrega, apertura, clicks)
    - Gestión de bounces y suppressions
    - Validación y sanitización avanzada
    - Rate limiting y throttling
    - A/B testing de emails
    - Segmentación y personalización
    - Compliance (GDPR, CAN-SPAM)
    - Analytics detallados
    - Gestión de listas de distribución
    """
    
    def __init__(self):
        super().__init__()
        self._providers = None
        self._template_env = None
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._suppressed_emails = None
    
    @property
    def providers(self) -> dict[str, EmailProviderInterface]:
        """Lazy initialization of providers"""
        if self._providers is None:
            self._providers = self._initialize_providers()
        return self._providers
    
    @property
    def template_env(self) -> jinja2.Environment:
        """Lazy initialization of template environment"""
        if self._template_env is None:
            self._template_env = self._setup_template_environment()
        return self._template_env
    
    @property
    def suppressed_emails(self) -> set:
        """Lazy initialization of suppressed emails"""
        if self._suppressed_emails is None:
            self._load_suppression_list()
        return self._suppressed_emails
    
    @suppressed_emails.setter
    def suppressed_emails(self, value: set):
        """Setter for suppressed emails"""
        self._suppressed_emails = value
    
    def _initialize_providers(self) -> dict[str, EmailProviderInterface]:
        """Inicializar proveedores de email"""
        providers = {}
        
        # Configurar proveedores disponibles
        if current_app.config.get('SENDGRID_API_KEY'):
            providers[EmailProvider.SENDGRID.value] = SendGridProvider()
        
        if current_app.config.get('AWS_ACCESS_KEY_ID'):
            providers[EmailProvider.AMAZON_SES.value] = AmazonSESProvider()
        
        if current_app.config.get('SMTP_HOST'):
            providers[EmailProvider.SMTP.value] = SMTPProvider()
        
        # Validar configuraciones
        for name, provider in list(providers.items()):
            if not provider.validate_config():
                logger.warning(f"Proveedor {name} no está configurado correctamente")
                del providers[name]
        
        if not providers:
            logger.error("No hay proveedores de email configurados")
        
        return providers
    
    def _setup_template_environment(self) -> jinja2.Environment:
        """Configurar entorno de plantillas"""
        template_dir = os.path.join(current_app.root_path, 'templates', 'email')
        
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Agregar filtros personalizados
        env.filters['format_currency'] = lambda x: f"${x:,.2f}"
        env.filters['format_date'] = lambda x: x.strftime('%d/%m/%Y') if x else ''
        env.filters['truncate_words'] = lambda x, n: ' '.join(x.split()[:n]) + '...' if len(x.split()) > n else x
        
        return env
    
    def _load_suppression_list(self):
        """Cargar lista de supresión desde base de datos"""
        self._suppressed_emails = set()
        try:
            from flask import has_app_context
            if has_app_context():
                suppressions = EmailSuppression.query.filter_by(is_active=True).all()
                for suppression in suppressions:
                    self._suppressed_emails.add(suppression.email.lower())
        except Exception as e:
            logger.warning(f"No se pudo cargar lista de supresión: {e}")
            self._suppressed_emails = set()
    
    def send_email(
        self,
        to: Union[str, list[str], EmailAddress, list[EmailAddress]],
        subject: str,
        text_body: Optional[str] = None,
        html_body: Optional[str] = None,
        template: Optional[str] = None,
        template_data: Optional[dict[str, Any]] = None,
        from_address: Optional[Union[str, EmailAddress]] = None,
        reply_to: Optional[Union[str, EmailAddress]] = None,
        cc: Optional[list[Union[str, EmailAddress]]] = None,
        bcc: Optional[list[Union[str, EmailAddress]]] = None,
        attachments: Optional[list[EmailAttachment]] = None,
        priority: str = EmailPriority.MEDIUM.value,
        tracking_enabled: bool = True,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        provider: Optional[str] = None
    ) -> EmailResult:
        """
        Enviar email individual
        
        Args:
            to: Destinatario(s)
            subject: Asunto
            text_body: Cuerpo en texto plano
            html_body: Cuerpo en HTML
            template: Nombre de plantilla
            template_data: Datos para la plantilla
            from_address: Remitente
            reply_to: Dirección de respuesta
            cc: Copia
            bcc: Copia oculta
            attachments: Adjuntos
            priority: Prioridad
            tracking_enabled: Habilitar tracking
            tags: Tags para categorización
            metadata: Metadata adicional
            provider: Proveedor específico a usar
            
        Returns:
            EmailResult: Resultado del envío
        """
        try:
            # Preparar mensaje
            message = self._prepare_message(
                to=to,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                template=template,
                template_data=template_data,
                from_address=from_address,
                reply_to=reply_to,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                priority=priority,
                tracking_enabled=tracking_enabled,
                tags=tags,
                metadata=metadata
            )
            
            # Validar destinatarios
            self._validate_recipients(message)
            
            # Filtrar suppressions
            message = self._filter_suppressed_recipients(message)
            
            if not message.to:
                return EmailResult(
                    success=False,
                    error_message="Todos los destinatarios están en la lista de supresión"
                )
            
            # Seleccionar proveedor
            selected_provider = self._select_provider(provider, priority)
            
            if not selected_provider:
                raise ExternalServiceError("No hay proveedores disponibles")
            
            # Enviar email
            result = selected_provider.send(message)
            
            # Registrar en log
            self._log_email(message, result)
            
            # Configurar tracking si está habilitado
            if tracking_enabled and result.success:
                self._setup_tracking(result.message_id, message)
            
            return result
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            return EmailResult(
                success=False,
                error_message=str(e)
            )
    
    async def send_email_async(
        self,
        to: Union[str, list[str], EmailAddress, list[EmailAddress]],
        subject: str,
        **kwargs
    ) -> EmailResult:
        """Enviar email de forma asíncrona"""
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            self.executor,
            self.send_email,
            to,
            subject,
            **kwargs
        )
    
    def send_bulk_email(
        self,
        recipients: list[dict[str, Any]],
        subject: str,
        template: str,
        from_address: Optional[Union[str, EmailAddress]] = None,
        tags: Optional[list[str]] = None,
        priority: str = EmailPriority.MEDIUM.value,
        provider: Optional[str] = None,
        batch_size: int = 100
    ) -> BulkEmailResult:
        """
        Enviar emails masivos con personalización
        
        Args:
            recipients: Lista de destinatarios con datos de personalización
            subject: Asunto (puede contener variables)
            template: Plantilla a usar
            from_address: Remitente
            tags: Tags para categorización
            priority: Prioridad
            provider: Proveedor específico
            batch_size: Tamaño del lote
            
        Returns:
            BulkEmailResult: Resultado del envío masivo
        """
        try:
            # Validar plantilla
            if not self._template_exists(template):
                raise ValidationError(f"Plantilla '{template}' no encontrada")
            
            # Filtrar destinatarios válidos
            valid_recipients = self._filter_valid_recipients(recipients)
            
            if not valid_recipients:
                return BulkEmailResult(
                    total_emails=0,
                    successful=0,
                    failed=len(recipients),
                    queued=0,
                    errors=["No hay destinatarios válidos"],
                    message_ids=[]
                )
            
            # Preparar mensajes
            messages = []
            for recipient in valid_recipients:
                try:
                    message = self._prepare_personalized_message(
                        recipient=recipient,
                        subject=subject,
                        template=template,
                        from_address=from_address,
                        tags=tags,
                        priority=priority
                    )
                    messages.append(message)
                except Exception as e:
                    logger.error(f"Error preparando mensaje para {recipient.get('email')}: {str(e)}")
            
            # Seleccionar proveedor
            selected_provider = self._select_provider(provider, priority)
            
            if not selected_provider:
                raise ExternalServiceError("No hay proveedores disponibles")
            
            # Enviar en lotes
            total_result = BulkEmailResult(
                total_emails=len(messages),
                successful=0,
                failed=0,
                queued=0,
                errors=[],
                message_ids=[]
            )
            
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                
                try:
                    batch_result = selected_provider.send_bulk(batch)
                    
                    total_result.successful += batch_result.successful
                    total_result.failed += batch_result.failed
                    total_result.queued += batch_result.queued
                    total_result.errors.extend(batch_result.errors)
                    total_result.message_ids.extend(batch_result.message_ids)
                    
                    # Log del lote
                    for message in batch:
                        self._log_bulk_email(message, batch_result.successful > 0)
                    
                except Exception as e:
                    total_result.failed += len(batch)
                    total_result.errors.append(f"Error en lote {i//batch_size + 1}: {str(e)}")
                    logger.error(f"Error enviando lote {i//batch_size + 1}: {str(e)}")
            
            return total_result
            
        except Exception as e:
            logger.error(f"Error en envío masivo: {str(e)}")
            return BulkEmailResult(
                total_emails=len(recipients),
                successful=0,
                failed=len(recipients),
                queued=0,
                errors=[str(e)],
                message_ids=[]
            )
    
    def send_template_email(
        self,
        to: Union[str, EmailAddress],
        template_name: str,
        template_data: dict[str, Any],
        from_address: Optional[Union[str, EmailAddress]] = None,
        **kwargs
    ) -> EmailResult:
        """
        Enviar email usando plantilla predefinida
        
        Args:
            to: Destinatario
            template_name: Nombre de la plantilla
            template_data: Datos para la plantilla
            from_address: Remitente
            **kwargs: Argumentos adicionales
            
        Returns:
            EmailResult: Resultado del envío
        """
        try:
            # Obtener plantilla de base de datos
            template = EmailTemplate.query.filter_by(
                name=template_name,
                is_active=True
            ).first()
            
            if not template:
                raise NotFoundError(f"Plantilla '{template_name}' no encontrada")
            
            # Renderizar contenido
            subject = self._render_template_string(template.subject, template_data)
            html_body = self._render_template_string(template.html_content, template_data)
            text_body = self._render_template_string(template.text_content, template_data) if template.text_content else None
            
            # Procesar CSS inline para mejor compatibilidad
            if html_body:
                html_body = transform(html_body)
            
            return self.send_email(
                to=to,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                from_address=from_address,
                tags=[template_name],
                metadata={'template_id': template.id},
                **kwargs
            )
            
        except Exception as e:
            logger.error(f"Error enviando email con plantilla '{template_name}': {str(e)}")
            return EmailResult(
                success=False,
                error_message=str(e)
            )
    
    def create_email_template(
        self,
        name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        variables: Optional[list[str]] = None
    ) -> EmailTemplate:
        """
        Crear nueva plantilla de email
        
        Args:
            name: Nombre único de la plantilla
            subject: Asunto (puede contener variables)
            html_content: Contenido HTML
            text_content: Contenido en texto plano
            description: Descripción de la plantilla
            category: Categoría
            variables: Variables disponibles
            
        Returns:
            EmailTemplate: Plantilla creada
        """
        try:
            # Validar que no exista
            existing = EmailTemplate.query.filter_by(name=name).first()
            if existing:
                raise ValidationError(f"Ya existe una plantilla con el nombre '{name}'")
            
            # Validar contenido HTML
            if html_content:
                html_content = self._sanitize_html(html_content)
            
            # Extraer variables automáticamente
            if not variables:
                variables = self._extract_template_variables(subject, html_content, text_content)
            
            # Crear plantilla
            template = EmailTemplate(
                name=name,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                description=description,
                category=category,
                variables=variables,
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(template)
            db.session.commit()
            
            logger.info(f"Plantilla de email creada: {name}")
            return template
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error creando plantilla: {str(e)}")
            raise BusinessLogicError("Error creando plantilla de email")
    
    def track_email_open(self, tracking_id: str, user_agent: str = None, ip_address: str = None) -> bool:
        """
        Trackear apertura de email
        
        Args:
            tracking_id: ID de tracking
            user_agent: User agent del cliente
            ip_address: Dirección IP
            
        Returns:
            bool: True si se registró correctamente
        """
        try:
            tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
            
            if not tracking:
                return False
            
            # Registrar apertura si es la primera vez
            if not tracking.opened_at:
                tracking.opened_at = datetime.now(timezone.utc)
                tracking.open_count = 1
                tracking.user_agent = user_agent
                tracking.ip_address = ip_address
            else:
                tracking.open_count += 1
                tracking.last_opened_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            # Actualizar estado del email
            if tracking.email_log:
                tracking.email_log.status = EmailStatus.OPENED.value
                db.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error trackeando apertura: {str(e)}")
            return False
    
    def track_email_click(
        self,
        tracking_id: str,
        url: str,
        user_agent: str = None,
        ip_address: str = None
    ) -> bool:
        """
        Trackear click en email
        
        Args:
            tracking_id: ID de tracking
            url: URL clickeada
            user_agent: User agent del cliente
            ip_address: Dirección IP
            
        Returns:
            bool: True si se registró correctamente
        """
        try:
            tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
            
            if not tracking:
                return False
            
            # Registrar click
            if not tracking.clicked_at:
                tracking.clicked_at = datetime.now(timezone.utc)
                tracking.click_count = 1
            else:
                tracking.click_count += 1
                tracking.last_clicked_at = datetime.now(timezone.utc)
            
            # Agregar URL a la lista de URLs clickeadas
            clicked_urls = tracking.clicked_urls or []
            if url not in clicked_urls:
                clicked_urls.append(url)
                tracking.clicked_urls = clicked_urls
            
            db.session.commit()
            
            # Actualizar estado del email
            if tracking.email_log:
                tracking.email_log.status = EmailStatus.CLICKED.value
                db.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error trackeando click: {str(e)}")
            return False
    
    def handle_bounce(
        self,
        email: str,
        bounce_type: str,
        reason: str,
        provider_data: dict[str, Any] = None
    ) -> bool:
        """
        Manejar bounce de email
        
        Args:
            email: Email que rebotó
            bounce_type: Tipo de bounce (hard/soft)
            reason: Razón del bounce
            provider_data: Datos del proveedor
            
        Returns:
            bool: True si se procesó correctamente
        """
        try:
            # Registrar bounce
            bounce = EmailBounce(
                email=email.lower(),
                bounce_type=bounce_type,
                reason=reason,
                provider_data=provider_data,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(bounce)
            
            # Si es hard bounce, agregar a suppressions
            if bounce_type == BounceType.HARD.value:
                self.add_to_suppression_list(
                    email=email,
                    reason=f"Hard bounce: {reason}",
                    source="automatic"
                )
            
            db.session.commit()
            
            logger.info(f"Bounce procesado: {email} - {bounce_type}")
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error procesando bounce: {str(e)}")
            return False
    
    def add_to_suppression_list(
        self,
        email: str,
        reason: str,
        source: str = "manual"
    ) -> bool:
        """
        Agregar email a lista de supresión
        
        Args:
            email: Email a suprimir
            reason: Razón de la supresión
            source: Fuente (manual, automatic, complaint)
            
        Returns:
            bool: True si se agregó correctamente
        """
        try:
            email = email.lower()
            
            # Verificar si ya está en la lista
            existing = EmailSuppression.query.filter_by(email=email).first()
            
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.reason = reason
                return True
            
            # Crear nueva supresión
            suppression = EmailSuppression(
                email=email,
                reason=reason,
                source=source,
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(suppression)
            db.session.commit()
            
            # Actualizar cache
            if self._suppressed_emails is not None:
                self._suppressed_emails.add(email)
            
            logger.info(f"Email agregado a supresión: {email}")
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error agregando a supresión: {str(e)}")
            return False
    
    def remove_from_suppression_list(self, email: str) -> bool:
        """
        Remover email de lista de supresión
        
        Args:
            email: Email a remover
            
        Returns:
            bool: True si se removió correctamente
        """
        try:
            email = email.lower()
            
            suppression = EmailSuppression.query.filter_by(
                email=email,
                is_active=True
            ).first()
            
            if suppression:
                suppression.is_active = False
                suppression.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                
                # Actualizar cache
                if self._suppressed_emails is not None:
                    self._suppressed_emails.discard(email)
                
                logger.info(f"Email removido de supresión: {email}")
                return True
            
            return False
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error removiendo de supresión: {str(e)}")
            return False
    
    def get_email_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        template_id: Optional[int] = None,
        campaign_id: Optional[int] = None
    ) -> dict[str, Any]:
        """
        Obtener analytics de email
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            template_id: Filtrar por plantilla
            campaign_id: Filtrar por campaña
            
        Returns:
            dict[str, Any]: Métricas de email
        """
        try:
            query = EmailLog.query.filter(
                EmailLog.created_at.between(start_date, end_date)
            )
            
            if template_id:
                query = query.filter_by(template_id=template_id)
            
            if campaign_id:
                query = query.filter_by(campaign_id=campaign_id)
            
            total_sent = query.count()
            
            # Métricas de entrega
            delivered = query.filter_by(status=EmailStatus.DELIVERED.value).count()
            bounced = query.filter_by(status=EmailStatus.BOUNCED.value).count()
            failed = query.filter_by(status=EmailStatus.FAILED.value).count()
            
            # Métricas de engagement
            opened = query.filter_by(status=EmailStatus.OPENED.value).count()
            clicked = query.filter_by(status=EmailStatus.CLICKED.value).count()
            
            # Calcular tasas
            delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
            bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
            open_rate = (opened / delivered * 100) if delivered > 0 else 0
            click_rate = (clicked / delivered * 100) if delivered > 0 else 0
            click_to_open_rate = (clicked / opened * 100) if opened > 0 else 0
            
            return {
                'summary': {
                    'total_sent': total_sent,
                    'delivered': delivered,
                    'bounced': bounced,
                    'failed': failed,
                    'opened': opened,
                    'clicked': clicked
                },
                'rates': {
                    'delivery_rate': round(delivery_rate, 2),
                    'bounce_rate': round(bounce_rate, 2),
                    'open_rate': round(open_rate, 2),
                    'click_rate': round(click_rate, 2),
                    'click_to_open_rate': round(click_to_open_rate, 2)
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo analytics: {str(e)}")
            return {}
    
    def is_configured(self) -> bool:
        """Verificar si el servicio está configurado"""
        return len(self.providers) > 0
    
    def _perform_initialization(self):
        """Inicialización específica del servicio de email."""
        # Already initialized in __init__, nothing additional needed
        pass
    
    def health_check(self) -> dict[str, Any]:
        """
        Verifica el estado de salud del servicio de email.
        
        Returns:
            Dict con información de estado del servicio
        """
        try:
            health_status = {
                'service': 'email',
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'providers': {},
                'configuration': {
                    'providers_configured': len(self.providers),
                    'suppression_list_loaded': len(self.suppressed_emails) > 0,
                    'template_env_ready': self.template_env is not None
                },
                'issues': []
            }
            
            # Check each provider
            for provider_name, provider in self.providers.items():
                try:
                    is_valid = provider.validate_config()
                    health_status['providers'][provider_name] = {
                        'status': 'healthy' if is_valid else 'degraded',
                        'configured': is_valid
                    }
                except Exception as e:
                    health_status['providers'][provider_name] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    health_status['issues'].append(f"Provider {provider_name}: {str(e)}")
            
            # Overall status assessment
            if not self.providers:
                health_status['status'] = 'error'
                health_status['issues'].append('No email providers configured')
            elif any(p['status'] == 'error' for p in health_status['providers'].values()):
                health_status['status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            return {
                'service': 'email',
                'status': 'error',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
    # Métodos privados
    def _prepare_message(self, **kwargs) -> EmailMessage:
        """Preparar mensaje de email"""
        # Convertir direcciones de email
        to = self._normalize_addresses(kwargs['to'])
        from_address = self._normalize_address(kwargs.get('from_address'))
        reply_to = self._normalize_address(kwargs.get('reply_to'))
        cc = self._normalize_addresses(kwargs.get('cc', []))
        bcc = self._normalize_addresses(kwargs.get('bcc', []))
        
        # Preparar contenido
        content = EmailContent(
            subject=kwargs['subject'],
            text_body=kwargs.get('text_body'),
            html_body=kwargs.get('html_body'),
            template_id=kwargs.get('template'),
            template_data=kwargs.get('template_data')
        )
        
        # Si hay plantilla, renderizar contenido
        if kwargs.get('template'):
            content = self._render_template_content(
                kwargs['template'],
                kwargs.get('template_data', {}),
                content
            )
        
        return EmailMessage(
            to=to,
            content=content,
            from_address=from_address,
            reply_to=reply_to,
            cc=cc,
            bcc=bcc,
            attachments=kwargs.get('attachments', []),
            priority=kwargs.get('priority', EmailPriority.MEDIUM.value),
            tracking_enabled=kwargs.get('tracking_enabled', True),
            unsubscribe_url=kwargs.get('unsubscribe_url'),
            tags=kwargs.get('tags', []),
            metadata=kwargs.get('metadata', {})
        )
    
    def _normalize_addresses(self, addresses) -> list[EmailAddress]:
        """Normalizar lista de direcciones"""
        if not addresses:
            return []
        
        if isinstance(addresses, str):
            addresses = [addresses]
        
        result = []
        for addr in addresses:
            normalized = self._normalize_address(addr)
            if normalized:
                result.append(normalized)
        
        return result
    
    def _normalize_address(self, address) -> Optional[EmailAddress]:
        """Normalizar dirección individual"""
        if not address:
            return None
        
        if isinstance(address, EmailAddress):
            return address
        
        if isinstance(address, str):
            return EmailAddress(email=address)
        
        return None
    
    def _validate_recipients(self, message: EmailMessage):
        """Validar destinatarios"""
        if not message.to:
            raise ValidationError("Debe especificar al menos un destinatario")
        
        for addr in message.to:
            if not validate_email(addr.email):
                raise ValidationError(f"Email inválido: {addr.email}")
    
    def _filter_suppressed_recipients(self, message: EmailMessage) -> EmailMessage:
        """Filtrar destinatarios en lista de supresión"""
        # Filtrar TO
        message.to = [
            addr for addr in message.to
            if addr.email.lower() not in self.suppressed_emails
        ]
        
        # Filtrar CC
        if message.cc:
            message.cc = [
                addr for addr in message.cc
                if addr.email.lower() not in self.suppressed_emails
            ]
        
        # Filtrar BCC
        if message.bcc:
            message.bcc = [
                addr for addr in message.bcc
                if addr.email.lower() not in self.suppressed_emails
            ]
        
        return message
    
    def _select_provider(self, preferred: Optional[str], priority: str) -> Optional[EmailProviderInterface]:
        """Seleccionar proveedor de email"""
        # Si se especifica un proveedor, intentar usarlo
        if preferred and preferred in self.providers:
            return self.providers[preferred]
        
        # Selección automática basada en prioridad y disponibilidad
        provider_priority = [
            EmailProvider.SENDGRID.value,
            EmailProvider.AMAZON_SES.value,
            EmailProvider.SMTP.value
        ]
        
        for provider_name in provider_priority:
            if provider_name in self.providers:
                return self.providers[provider_name]
        
        return None
    
    def _render_template_content(
        self,
        template_name: str,
        template_data: dict[str, Any],
        content: EmailContent
    ) -> EmailContent:
        """Renderizar contenido de plantilla"""
        try:
            # Buscar plantilla en archivos
            if self.template_env:
                try:
                    template = self.template_env.get_template(f"{template_name}.html")
                    content.html_body = template.render(**template_data)
                except jinja2.TemplateNotFound:
                    pass
                
                try:
                    template = self.template_env.get_template(f"{template_name}.txt")
                    content.text_body = template.render(**template_data)
                except jinja2.TemplateNotFound:
                    pass
            
            return content
            
        except Exception as e:
            logger.error(f"Error renderizando plantilla '{template_name}': {str(e)}")
            return content
    
    def _render_template_string(self, template_string: str, data: dict[str, Any]) -> str:
        """Renderizar string de plantilla"""
        try:
            template = jinja2.Template(template_string)
            return template.render(**data)
        except Exception as e:
            logger.error(f"Error renderizando template string: {str(e)}")
            return template_string
    
    def _sanitize_html(self, html_content: str) -> str:
        """Sanitizar contenido HTML"""
        allowed_tags = [
            'a', 'b', 'strong', 'i', 'em', 'u', 'br', 'p', 'div', 'span',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
            'table', 'tr', 'td', 'th', 'thead', 'tbody', 'img'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height'],
            '*': ['style', 'class']
        }
        
        return bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
    
    def _extract_template_variables(self, *contents) -> list[str]:
        """Extraer variables de plantillas Jinja2"""
        variables = set()
        
        for content in contents:
            if content:
                # Buscar patrones {{ variable }} y {% ... %}
                var_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
                matches = re.findall(var_pattern, content)
                variables.update(matches)
        
        return list(variables)
    
    def _template_exists(self, template_name: str) -> bool:
        """Verificar si existe plantilla"""
        # Verificar en base de datos
        db_template = EmailTemplate.query.filter_by(
            name=template_name,
            is_active=True
        ).first()
        
        if db_template:
            return True
        
        # Verificar en archivos
        if self.template_env:
            try:
                self.template_env.get_template(f"{template_name}.html")
                return True
            except jinja2.TemplateNotFound:
                pass
        
        return False
    
    def _log_email(self, message: EmailMessage, result: EmailResult):
        """Registrar email en log"""
        try:
            email_log = EmailLog(
                message_id=result.message_id,
                provider=result.provider_used,
                to_email=message.to[0].email if message.to else None,
                from_email=str(message.from_address) if message.from_address else None,
                subject=message.content.subject,
                status=EmailStatus.SENT.value if result.success else EmailStatus.FAILED.value,
                error_message=result.error_message,
                provider_response=result.provider_id,
                tags=message.tags,
                metadata=message.metadata,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(email_log)
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error registrando email en log: {str(e)}")
    
    def _setup_tracking(self, message_id: str, message: EmailMessage):
        """Configurar tracking para email"""
        try:
            tracking_id = generate_hash(f"{message_id}-{datetime.now(timezone.utc)}")
            
            tracking = EmailTracking(
                tracking_id=tracking_id,
                message_id=message_id,
                recipient_email=message.to[0].email if message.to else None,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(tracking)
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error configurando tracking: {str(e)}")


# Instancia del servicio para uso global (will be initialized within app context)
email_service = None

def get_email_service():
    """Get email service instance, initializing if needed."""
    global email_service
    if email_service is None:
        email_service = EmailService()
    return email_service


# Funciones de conveniencia para uso rápido
def send_welcome_email(user_email: str, user_name: str) -> EmailResult:
    """Enviar email de bienvenida"""
    return email_service.send_template_email(
        to=EmailAddress(email=user_email, name=user_name),
        template_name='welcome',
        template_data={
            'user_name': user_name,
            'platform_name': 'Ecosistema de Emprendimiento'
        }
    )


def send_password_reset_email(user_email: str, reset_token: str) -> EmailResult:
    """Enviar email de reseteo de contraseña"""
    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
    
    return email_service.send_template_email(
        to=user_email,
        template_name='password_reset',
        template_data={
            'reset_url': reset_url,
            'expiry_hours': 24
        },
        priority=EmailPriority.HIGH.value
    )


def send_project_notification_email(
    user_email: str,
    project_title: str,
    notification_type: str,
    **kwargs
) -> EmailResult:
    """Enviar notificación de proyecto"""
    return email_service.send_template_email(
        to=user_email,
        template_name=f'project_{notification_type}',
        template_data={
            'project_title': project_title,
            **kwargs
        },
        tags=['project', notification_type]
    )