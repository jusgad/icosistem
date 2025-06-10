"""
API endpoints para manejo de webhooks del ecosistema de emprendimiento.
Maneja integraciones con servicios externos como pagos, calendarios, comunicaciones, etc.
Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from marshmallow import Schema, fields, validate, ValidationError
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
import hashlib
import hmac
import json
import uuid
import base64
from functools import wraps
from dataclasses import dataclass
from enum import Enum

# Importaciones locales
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.document import Document
from app.models.notification import Notification
from app.models.webhook_event import WebhookEvent, WebhookStatus, WebhookProvider
from app.models.integration import Integration, IntegrationStatus
from app.models.payment import Payment, PaymentStatus
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.google_calendar import GoogleCalendarService
from app.services.integration_hub import IntegrationHubService
from app.core.exceptions import (
    ValidationException, 
    AuthorizationException,
    WebhookException,
    IntegrationException
)
from app.utils.decorators import api_response, rate_limit
from app.utils.crypto_utils import verify_signature, generate_signature
from app.utils.string_utils import sanitize_input, mask_sensitive_data
from app.tasks.webhook_tasks import process_webhook_async, retry_failed_webhook
from app.extensions import db, cache
from app.config import Config

# Blueprint para webhooks
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/v1/webhooks')

# Configuración de webhooks
WEBHOOK_TIMEOUT = 30  # seconds
MAX_RETRY_ATTEMPTS = 3
WEBHOOK_SIGNATURE_TOLERANCE = 300  # 5 minutes

class WebhookProvider(Enum):
    """Proveedores de webhooks soportados."""
    STRIPE = "stripe"
    PAYPAL = "paypal"
    GOOGLE_CALENDAR = "google_calendar"
    SLACK = "slack"
    MICROSOFT_TEAMS = "microsoft_teams"
    ZOOM = "zoom"
    GITHUB = "github"
    MAILGUN = "mailgun"
    TWILIO = "twilio"
    CUSTOM = "custom"

class WebhookEventType(Enum):
    """Tipos de eventos de webhook."""
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    CALENDAR_EVENT_CREATED = "calendar.event.created"
    CALENDAR_EVENT_UPDATED = "calendar.event.updated"
    CALENDAR_EVENT_DELETED = "calendar.event.deleted"
    MESSAGE_RECEIVED = "message.received"
    DOCUMENT_UPLOADED = "document.uploaded"
    USER_CREATED = "user.created"
    PROJECT_UPDATED = "project.updated"
    MEETING_SCHEDULED = "meeting.scheduled"
    MEETING_COMPLETED = "meeting.completed"
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    CUSTOM_EVENT = "custom.event"

@dataclass
class WebhookConfig:
    """Configuración de webhook por proveedor."""
    provider: WebhookProvider
    signature_header: str
    signature_prefix: str
    secret_key: str
    verify_signature: bool = True
    require_https: bool = True
    allowed_ips: List[str] = None

# Configuraciones por proveedor
WEBHOOK_CONFIGS = {
    WebhookProvider.STRIPE: WebhookConfig(
        provider=WebhookProvider.STRIPE,
        signature_header='Stripe-Signature',
        signature_prefix='t=',
        secret_key='webhook_stripe_secret',
        verify_signature=True,
        require_https=True
    ),
    WebhookProvider.PAYPAL: WebhookConfig(
        provider=WebhookProvider.PAYPAL,
        signature_header='PAYPAL-TRANSMISSION-SIG',
        signature_prefix='',
        secret_key='webhook_paypal_secret',
        verify_signature=True,
        require_https=True
    ),
    WebhookProvider.GOOGLE_CALENDAR: WebhookConfig(
        provider=WebhookProvider.GOOGLE_CALENDAR,
        signature_header='X-Goog-Channel-Token',
        signature_prefix='',
        secret_key='webhook_google_secret',
        verify_signature=True,
        require_https=True
    ),
    WebhookProvider.SLACK: WebhookConfig(
        provider=WebhookProvider.SLACK,
        signature_header='X-Slack-Signature',
        signature_prefix='v0=',
        secret_key='webhook_slack_secret',
        verify_signature=True,
        require_https=True
    ),
    WebhookProvider.GITHUB: WebhookConfig(
        provider=WebhookProvider.GITHUB,
        signature_header='X-Hub-Signature-256',
        signature_prefix='sha256=',
        secret_key='webhook_github_secret',
        verify_signature=True,
        require_https=True
    )
}

# Schemas de validación
class WebhookEventSchema(Schema):
    """Schema base para eventos de webhook."""
    event_type = fields.Str(required=True)
    event_id = fields.Str(required=True)
    timestamp = fields.DateTime(required=True)
    data = fields.Dict(required=True)
    version = fields.Str(missing='1.0')
    source = fields.Str(required=True)

class StripeWebhookSchema(Schema):
    """Schema para webhooks de Stripe."""
    id = fields.Str(required=True)
    type = fields.Str(required=True)
    data = fields.Dict(required=True)
    created = fields.Int(required=True)
    livemode = fields.Bool(required=True)
    pending_webhooks = fields.Int(required=True)
    request = fields.Dict(missing={})

class GoogleCalendarWebhookSchema(Schema):
    """Schema para webhooks de Google Calendar."""
    kind = fields.Str(required=True)
    id = fields.Str(required=True)
    resourceId = fields.Str(required=True)
    resourceUri = fields.Str(required=True)
    token = fields.Str(required=True)
    expiration = fields.Str(required=True)

class SlackWebhookSchema(Schema):
    """Schema para webhooks de Slack."""
    token = fields.Str(required=True)
    team_id = fields.Str(required=True)
    api_app_id = fields.Str(required=True)
    event = fields.Dict(required=True)
    type = fields.Str(required=True)
    event_id = fields.Str(required=True)
    event_time = fields.Int(required=True)

# Funciones auxiliares
def get_webhook_config(provider: WebhookProvider) -> WebhookConfig:
    """Obtiene configuración de webhook por proveedor."""
    config = WEBHOOK_CONFIGS.get(provider)
    if not config:
        raise WebhookException(f"Proveedor de webhook no soportado: {provider.value}")
    return config

def verify_webhook_signature(
    provider: WebhookProvider, 
    payload: bytes, 
    signature: str, 
    timestamp: Optional[str] = None
) -> bool:
    """Verifica la firma del webhook según el proveedor."""
    config = get_webhook_config(provider)
    
    if not config.verify_signature:
        return True
    
    secret = current_app.config.get(config.secret_key.upper())
    if not secret:
        current_app.logger.error(f"Secret key no configurado para {provider.value}")
        return False
    
    try:
        if provider == WebhookProvider.STRIPE:
            return verify_stripe_signature(payload, signature, secret, timestamp)
        elif provider == WebhookProvider.PAYPAL:
            return verify_paypal_signature(payload, signature, secret)
        elif provider == WebhookProvider.SLACK:
            return verify_slack_signature(payload, signature, secret, timestamp)
        elif provider == WebhookProvider.GITHUB:
            return verify_github_signature(payload, signature, secret)
        else:
            # Verificación genérica HMAC
            return verify_hmac_signature(payload, signature, secret, config.signature_prefix)
    
    except Exception as e:
        current_app.logger.error(f"Error verificando firma {provider.value}: {str(e)}")
        return False

def verify_stripe_signature(payload: bytes, signature: str, secret: str, timestamp: str) -> bool:
    """Verifica firma de Stripe."""
    try:
        # Extraer timestamp y firma de la cabecera
        elements = signature.split(',')
        timestamp_str = None
        signature_hash = None
        
        for element in elements:
            if element.startswith('t='):
                timestamp_str = element[2:]
            elif element.startswith('v1='):
                signature_hash = element[3:]
        
        if not timestamp_str or not signature_hash:
            return False
        
        # Verificar timestamp (tolerancia de 5 minutos)
        webhook_timestamp = int(timestamp_str)
        current_timestamp = int(datetime.utcnow().timestamp())
        
        if abs(current_timestamp - webhook_timestamp) > WEBHOOK_SIGNATURE_TOLERANCE:
            return False
        
        # Crear payload firmado
        signed_payload = f"{timestamp_str}.{payload.decode('utf-8')}"
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature_hash, expected_signature)
    
    except Exception:
        return False

def verify_paypal_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verifica firma de PayPal."""
    try:
        expected_signature = base64.b64encode(
            hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception:
        return False

def verify_slack_signature(payload: bytes, signature: str, secret: str, timestamp: str) -> bool:
    """Verifica firma de Slack."""
    try:
        if not timestamp:
            return False
        
        # Verificar timestamp
        webhook_timestamp = int(timestamp)
        current_timestamp = int(datetime.utcnow().timestamp())
        
        if abs(current_timestamp - webhook_timestamp) > WEBHOOK_SIGNATURE_TOLERANCE:
            return False
        
        # Crear signature
        sig_basestring = f"v0:{timestamp}:{payload.decode('utf-8')}"
        expected_signature = 'v0=' + hmac.new(
            secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception:
        return False

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verifica firma de GitHub."""
    try:
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception:
        return False

def verify_hmac_signature(payload: bytes, signature: str, secret: str, prefix: str = '') -> bool:
    """Verificación HMAC genérica."""
    try:
        if prefix and signature.startswith(prefix):
            signature = signature[len(prefix):]
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception:
        return False

def log_webhook_event(
    provider: WebhookProvider,
    event_type: str,
    event_id: str,
    payload: Dict,
    status: WebhookStatus,
    error_message: Optional[str] = None
) -> WebhookEvent:
    """Registra evento de webhook en la base de datos."""
    try:
        webhook_event = WebhookEvent(
            provider=provider,
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            status=status,
            error_message=error_message,
            processed_at=datetime.utcnow() if status == WebhookStatus.PROCESSED else None
        )
        
        db.session.add(webhook_event)
        db.session.commit()
        
        return webhook_event
    
    except Exception as e:
        current_app.logger.error(f"Error guardando evento webhook: {str(e)}")
        db.session.rollback()
        raise

def is_duplicate_webhook(provider: WebhookProvider, event_id: str) -> bool:
    """Verifica si es un webhook duplicado."""
    existing = WebhookEvent.query.filter_by(
        provider=provider,
        event_id=event_id,
        status=WebhookStatus.PROCESSED
    ).first()
    
    return existing is not None

def require_webhook_auth(provider: WebhookProvider):
    """Decorador para autenticación de webhooks."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar HTTPS en producción
            config = get_webhook_config(provider)
            if config.require_https and not request.is_secure and not current_app.debug:
                raise WebhookException("HTTPS requerido para webhooks")
            
            # Verificar IPs permitidas si están configuradas
            if config.allowed_ips:
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if client_ip not in config.allowed_ips:
                    raise AuthorizationException(f"IP no autorizada: {client_ip}")
            
            # Obtener payload
            payload = request.get_data()
            
            # Verificar firma
            signature_header = request.headers.get(config.signature_header)
            if config.verify_signature and not signature_header:
                raise WebhookException(f"Cabecera de firma faltante: {config.signature_header}")
            
            timestamp = request.headers.get('X-Timestamp') or request.headers.get('X-Slack-Request-Timestamp')
            
            if config.verify_signature and not verify_webhook_signature(
                provider, payload, signature_header, timestamp
            ):
                raise WebhookException("Firma de webhook inválida")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# Handlers específicos por proveedor
class WebhookHandlers:
    """Manejadores de eventos por proveedor."""
    
    @staticmethod
    def handle_stripe_event(event_type: str, data: Dict) -> bool:
        """Maneja eventos de Stripe."""
        try:
            if event_type == 'payment_intent.succeeded':
                return WebhookHandlers._handle_payment_success(data, 'stripe')
            elif event_type == 'payment_intent.payment_failed':
                return WebhookHandlers._handle_payment_failed(data, 'stripe')
            elif event_type == 'charge.dispute.created':
                return WebhookHandlers._handle_payment_dispute(data, 'stripe')
            elif event_type == 'customer.subscription.created':
                return WebhookHandlers._handle_subscription_created(data, 'stripe')
            elif event_type == 'invoice.payment_succeeded':
                return WebhookHandlers._handle_invoice_paid(data, 'stripe')
            else:
                current_app.logger.info(f"Evento Stripe no manejado: {event_type}")
                return True
        
        except Exception as e:
            current_app.logger.error(f"Error manejando evento Stripe {event_type}: {str(e)}")
            return False
    
    @staticmethod
    def handle_google_calendar_event(event_type: str, data: Dict) -> bool:
        """Maneja eventos de Google Calendar."""
        try:
            calendar_service = GoogleCalendarService()
            
            if event_type == 'calendar.event.created':
                return calendar_service.handle_event_created(data)
            elif event_type == 'calendar.event.updated':
                return calendar_service.handle_event_updated(data)
            elif event_type == 'calendar.event.deleted':
                return calendar_service.handle_event_deleted(data)
            else:
                current_app.logger.info(f"Evento Google Calendar no manejado: {event_type}")
                return True
        
        except Exception as e:
            current_app.logger.error(f"Error manejando evento Google Calendar {event_type}: {str(e)}")
            return False
    
    @staticmethod
    def handle_slack_event(event_type: str, data: Dict) -> bool:
        """Maneja eventos de Slack."""
        try:
            if event_type == 'message':
                return WebhookHandlers._handle_slack_message(data)
            elif event_type == 'app_mention':
                return WebhookHandlers._handle_slack_mention(data)
            elif event_type == 'file_shared':
                return WebhookHandlers._handle_slack_file_shared(data)
            else:
                current_app.logger.info(f"Evento Slack no manejado: {event_type}")
                return True
        
        except Exception as e:
            current_app.logger.error(f"Error manejando evento Slack {event_type}: {str(e)}")
            return False
    
    @staticmethod
    def _handle_payment_success(data: Dict, provider: str) -> bool:
        """Maneja pagos exitosos."""
        try:
            payment_intent_id = data.get('id') or data.get('payment_id')
            amount = data.get('amount') or data.get('value', {}).get('amount')
            currency = data.get('currency') or data.get('value', {}).get('currency')
            
            # Buscar el pago en la base de datos
            payment = Payment.query.filter_by(
                external_id=payment_intent_id,
                provider=provider
            ).first()
            
            if payment:
                payment.status = PaymentStatus.COMPLETED
                payment.processed_at = datetime.utcnow()
                payment.amount_received = amount
                db.session.commit()
                
                # Notificar al usuario
                notification_service = NotificationService()
                notification_service.notify_payment_success(payment)
                
                current_app.logger.info(f"Pago procesado exitosamente: {payment_intent_id}")
                return True
            else:
                current_app.logger.warning(f"Pago no encontrado: {payment_intent_id}")
                return False
        
        except Exception as e:
            current_app.logger.error(f"Error procesando pago exitoso: {str(e)}")
            return False
    
    @staticmethod
    def _handle_payment_failed(data: Dict, provider: str) -> bool:
        """Maneja pagos fallidos."""
        try:
            payment_intent_id = data.get('id') or data.get('payment_id')
            error_message = data.get('last_payment_error', {}).get('message') or data.get('error', {}).get('message')
            
            payment = Payment.query.filter_by(
                external_id=payment_intent_id,
                provider=provider
            ).first()
            
            if payment:
                payment.status = PaymentStatus.FAILED
                payment.error_message = error_message
                payment.failed_at = datetime.utcnow()
                db.session.commit()
                
                # Notificar al usuario
                notification_service = NotificationService()
                notification_service.notify_payment_failed(payment)
                
                current_app.logger.info(f"Pago falló: {payment_intent_id} - {error_message}")
                return True
            else:
                current_app.logger.warning(f"Pago fallido no encontrado: {payment_intent_id}")
                return False
        
        except Exception as e:
            current_app.logger.error(f"Error procesando pago fallido: {str(e)}")
            return False
    
    @staticmethod
    def _handle_slack_message(data: Dict) -> bool:
        """Maneja mensajes de Slack."""
        try:
            # Procesar mensaje y crear notificación si es relevante
            user_id = data.get('user')
            text = data.get('text', '')
            channel = data.get('channel')
            
            # Buscar menciones a usuarios del sistema
            if '@' in text:
                # Lógica para procesar menciones
                pass
            
            current_app.logger.info(f"Mensaje de Slack procesado: {user_id}")
            return True
        
        except Exception as e:
            current_app.logger.error(f"Error procesando mensaje Slack: {str(e)}")
            return False

# Endpoints de webhooks

@webhooks_bp.route('/stripe', methods=['POST'])
@require_webhook_auth(WebhookProvider.STRIPE)
@rate_limit(100, per=60)  # 100 webhooks per minute
@api_response
def stripe_webhook():
    """Webhook para eventos de Stripe."""
    try:
        payload = request.get_json()
        schema = StripeWebhookSchema()
        data = schema.load(payload)
        
        event_id = data['id']
        event_type = data['type']
        
        # Verificar duplicados
        if is_duplicate_webhook(WebhookProvider.STRIPE, event_id):
            current_app.logger.info(f"Webhook duplicado ignorado: {event_id}")
            return {'status': 'duplicate', 'event_id': event_id}
        
        # Procesar evento
        success = WebhookHandlers.handle_stripe_event(event_type, data['data'])
        
        # Registrar evento
        status = WebhookStatus.PROCESSED if success else WebhookStatus.FAILED
        webhook_event = log_webhook_event(
            WebhookProvider.STRIPE,
            event_type,
            event_id,
            payload,
            status,
            None if success else "Error procesando evento"
        )
        
        if success:
            return {
                'status': 'success',
                'event_id': event_id,
                'webhook_id': webhook_event.id
            }
        else:
            # Programar reintento
            retry_failed_webhook.apply_async(
                args=[webhook_event.id],
                countdown=60  # Reintentar en 1 minuto
            )
            return {
                'status': 'failed',
                'event_id': event_id,
                'webhook_id': webhook_event.id
            }, 500
    
    except ValidationError as e:
        current_app.logger.error(f"Webhook Stripe inválido: {e.messages}")
        return {'error': 'Invalid payload', 'details': e.messages}, 400
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook Stripe: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/google/calendar', methods=['POST'])
@require_webhook_auth(WebhookProvider.GOOGLE_CALENDAR)
@rate_limit(100, per=60)
@api_response
def google_calendar_webhook():
    """Webhook para eventos de Google Calendar."""
    try:
        # Google Calendar usa diferentes headers
        resource_id = request.headers.get('X-Goog-Resource-ID')
        resource_uri = request.headers.get('X-Goog-Resource-URI')
        resource_state = request.headers.get('X-Goog-Resource-State')
        
        if not resource_id or not resource_uri:
            raise WebhookException("Cabeceras de Google Calendar faltantes")
        
        event_id = f"calendar_{resource_id}_{int(datetime.utcnow().timestamp())}"
        
        # Verificar duplicados
        if is_duplicate_webhook(WebhookProvider.GOOGLE_CALENDAR, event_id):
            return {'status': 'duplicate', 'event_id': event_id}
        
        # Procesar según el estado
        data = {
            'resource_id': resource_id,
            'resource_uri': resource_uri,
            'resource_state': resource_state
        }
        
        success = WebhookHandlers.handle_google_calendar_event(
            f'calendar.{resource_state}',
            data
        )
        
        # Registrar evento
        status = WebhookStatus.PROCESSED if success else WebhookStatus.FAILED
        webhook_event = log_webhook_event(
            WebhookProvider.GOOGLE_CALENDAR,
            f'calendar.{resource_state}',
            event_id,
            data,
            status
        )
        
        return {
            'status': 'success' if success else 'failed',
            'event_id': event_id,
            'webhook_id': webhook_event.id
        }
    
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook Google Calendar: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/slack', methods=['POST'])
@require_webhook_auth(WebhookProvider.SLACK)
@rate_limit(100, per=60)
@api_response
def slack_webhook():
    """Webhook para eventos de Slack."""
    try:
        payload = request.get_json()
        
        # Manejar challenge de Slack
        if payload.get('type') == 'url_verification':
            return {'challenge': payload.get('challenge')}
        
        schema = SlackWebhookSchema()
        data = schema.load(payload)
        
        event_id = data['event_id']
        event_type = data['event']['type']
        
        # Verificar duplicados
        if is_duplicate_webhook(WebhookProvider.SLACK, event_id):
            return {'status': 'duplicate', 'event_id': event_id}
        
        # Procesar evento
        success = WebhookHandlers.handle_slack_event(event_type, data['event'])
        
        # Registrar evento
        status = WebhookStatus.PROCESSED if success else WebhookStatus.FAILED
        webhook_event = log_webhook_event(
            WebhookProvider.SLACK,
            event_type,
            event_id,
            payload,
            status
        )
        
        return {
            'status': 'success' if success else 'failed',
            'event_id': event_id,
            'webhook_id': webhook_event.id
        }
    
    except ValidationError as e:
        current_app.logger.error(f"Webhook Slack inválido: {e.messages}")
        return {'error': 'Invalid payload', 'details': e.messages}, 400
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook Slack: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/paypal', methods=['POST'])
@require_webhook_auth(WebhookProvider.PAYPAL)
@rate_limit(100, per=60)
@api_response
def paypal_webhook():
    """Webhook para eventos de PayPal."""
    try:
        payload = request.get_json()
        
        event_id = payload.get('id')
        event_type = payload.get('event_type')
        
        if not event_id or not event_type:
            raise WebhookException("Datos de PayPal incompletos")
        
        # Verificar duplicados
        if is_duplicate_webhook(WebhookProvider.PAYPAL, event_id):
            return {'status': 'duplicate', 'event_id': event_id}
        
        # Procesar según tipo de evento
        success = True
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            success = WebhookHandlers._handle_payment_success(payload.get('resource', {}), 'paypal')
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            success = WebhookHandlers._handle_payment_failed(payload.get('resource', {}), 'paypal')
        
        # Registrar evento
        status = WebhookStatus.PROCESSED if success else WebhookStatus.FAILED
        webhook_event = log_webhook_event(
            WebhookProvider.PAYPAL,
            event_type,
            event_id,
            payload,
            status
        )
        
        return {
            'status': 'success' if success else 'failed',
            'event_id': event_id,
            'webhook_id': webhook_event.id
        }
    
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook PayPal: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/github', methods=['POST'])
@require_webhook_auth(WebhookProvider.GITHUB)
@rate_limit(100, per=60)
@api_response
def github_webhook():
    """Webhook para eventos de GitHub."""
    try:
        payload = request.get_json()
        event_type = request.headers.get('X-GitHub-Event')
        
        if not event_type:
            raise WebhookException("Tipo de evento GitHub faltante")
        
        # Generar ID único para el evento
        event_id = f"github_{event_type}_{int(datetime.utcnow().timestamp())}"
        
        # Procesar eventos relevantes
        success = True
        if event_type == 'push':
            # Manejar push events
            success = True
        elif event_type == 'pull_request':
            # Manejar pull request events
            success = True
        elif event_type == 'issues':
            # Manejar issue events
            success = True
        
        # Registrar evento
        status = WebhookStatus.PROCESSED if success else WebhookStatus.FAILED
        webhook_event = log_webhook_event(
            WebhookProvider.GITHUB,
            event_type,
            event_id,
            payload,
            status
        )
        
        return {
            'status': 'success' if success else 'failed',
            'event_id': event_id,
            'webhook_id': webhook_event.id
        }
    
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook GitHub: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/custom/<integration_id>', methods=['POST'])
@jwt_required(optional=True)
@rate_limit(50, per=60)
@api_response
def custom_webhook(integration_id: str):
    """Webhook personalizado para integraciones específicas."""
    try:
        # Verificar que la integración existe y está activa
        integration = Integration.query.filter_by(
            id=integration_id,
            status=IntegrationStatus.ACTIVE
        ).first()
        
        if not integration:
            raise WebhookException("Integración no encontrada o inactiva")
        
        payload = request.get_json()
        event_type = payload.get('event_type', 'custom.event')
        event_id = payload.get('event_id') or str(uuid.uuid4())
        
        # Verificar duplicados
        if is_duplicate_webhook(WebhookProvider.CUSTOM, event_id):
            return {'status': 'duplicate', 'event_id': event_id}
        
        # Procesar de forma asíncrona
        process_webhook_async.apply_async(args=[
            WebhookProvider.CUSTOM.value,
            event_type,
            event_id,
            payload,
            integration_id
        ])
        
        # Registrar evento como pendiente
        webhook_event = log_webhook_event(
            WebhookProvider.CUSTOM,
            event_type,
            event_id,
            payload,
            WebhookStatus.PENDING
        )
        
        return {
            'status': 'accepted',
            'event_id': event_id,
            'webhook_id': webhook_event.id
        }, 202
    
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook personalizado: {str(e)}")
        return {'error': 'Internal server error'}, 500

@webhooks_bp.route('/events', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@api_response
def list_webhook_events():
    """Lista eventos de webhook con filtros."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        provider = request.args.get('provider')
        status = request.args.get('status')
        event_type = request.args.get('event_type')
        
        query = WebhookEvent.query
        
        if provider:
            query = query.filter(WebhookEvent.provider == provider)
        if status:
            query = query.filter(WebhookEvent.status == status)
        if event_type:
            query = query.filter(WebhookEvent.event_type == event_type)
        
        pagination = query.order_by(
            WebhookEvent.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        events = []
        for event in pagination.items:
            event_data = {
                'id': event.id,
                'provider': event.provider.value,
                'event_type': event.event_type,
                'event_id': event.event_id,
                'status': event.status.value,
                'created_at': event.created_at.isoformat(),
                'processed_at': event.processed_at.isoformat() if event.processed_at else None,
                'retry_count': event.retry_count
            }
            
            if event.error_message:
                event_data['error_message'] = event.error_message
            
            # Mascarar datos sensibles en el payload
            if event.payload:
                event_data['payload'] = mask_sensitive_data(event.payload)
            
            events.append(event_data)
        
        return {
            'events': events,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        }
    
    except Exception as e:
        current_app.logger.error(f"Error listando eventos webhook: {str(e)}")
        raise

@webhooks_bp.route('/events/<int:event_id>/retry', methods=['POST'])
@jwt_required()
@rate_limit(10, per=60)
@api_response
def retry_webhook_event(event_id: int):
    """Reintenta procesar un evento de webhook fallido."""
    try:
        event = WebhookEvent.query.get(event_id)
        if not event:
            return {'error': 'Evento no encontrado'}, 404
        
        if event.status != WebhookStatus.FAILED:
            return {'error': 'Solo se pueden reintentar eventos fallidos'}, 400
        
        if event.retry_count >= MAX_RETRY_ATTEMPTS:
            return {'error': 'Máximo número de reintentos alcanzado'}, 400
        
        # Programar reintento asíncrono
        retry_failed_webhook.apply_async(args=[event_id])
        
        return {
            'status': 'retry_scheduled',
            'event_id': event.event_id,
            'retry_count': event.retry_count + 1
        }
    
    except Exception as e:
        current_app.logger.error(f"Error reintentando webhook: {str(e)}")
        raise

# Manejo de errores
@webhooks_bp.errorhandler(WebhookException)
def handle_webhook_error(e):
    return jsonify({'error': str(e), 'type': 'webhook_error'}), 400

@webhooks_bp.errorhandler(AuthorizationException)
def handle_authorization_error(e):
    return jsonify({'error': str(e), 'type': 'authorization_error'}), 403

@webhooks_bp.errorhandler(ValidationException)
def handle_validation_error(e):
    return jsonify({'error': str(e), 'type': 'validation_error'}), 400

@webhooks_bp.errorhandler(IntegrationException)
def handle_integration_error(e):
    return jsonify({'error': str(e), 'type': 'integration_error'}), 422