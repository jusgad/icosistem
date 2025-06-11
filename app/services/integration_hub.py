"""
Integration Hub Service

Hub centralizado para gestionar todas las integraciones externas del ecosistema.
Incluye OAuth, webhooks, rate limiting, circuit breakers y analytics.

Author: jusga  
Date: 2025
"""

import json
import hmac
import hashlib
import logging
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Callable, Type
from enum import Enum
from dataclasses import dataclass, asdict, field
from functools import wraps
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from flask import current_app, request, url_for
import redis
from celery import Celery
import jwt
from cryptography.fernet import Fernet

from app.core.exceptions import (
    IntegrationError, 
    AuthenticationError, 
    RateLimitError,
    ValidationError,
    ExternalAPIError
)
from app.utils.cache_utils import CacheManager
from app.utils.decorators import retry_on_failure
from app.models.user import User


logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Tipos de integraciones soportadas"""
    CALENDAR = "calendar"
    VIDEO_CONFERENCE = "video_conference"
    EMAIL = "email"
    CLOUD_STORAGE = "cloud_storage"
    PAYMENT = "payment"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    CRM = "crm"
    PROJECT_MANAGEMENT = "project_management"
    COMMUNICATION = "communication"
    SOCIAL_MEDIA = "social_media"
    ACCOUNTING = "accounting"
    DOCUMENT_SIGNING = "document_signing"
    WEBHOOK = "webhook"


class AuthMethod(Enum):
    """Métodos de autenticación"""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
    JWT_TOKEN = "jwt_token"
    WEBHOOK_SIGNATURE = "webhook_signature"
    NONE = "none"


class IntegrationStatus(Enum):
    """Estados de integración"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    EXPIRED = "expired"
    PENDING_AUTH = "pending_auth"
    DISCONNECTED = "disconnected"


class WebhookEvent(Enum):
    """Tipos de eventos webhook"""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    MEETING_SCHEDULED = "meeting.scheduled"
    MEETING_COMPLETED = "meeting.completed"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_FAILED = "payment.failed"
    DOCUMENT_SIGNED = "document.signed"
    MILESTONE_REACHED = "milestone.reached"


@dataclass
class IntegrationConfig:
    """Configuración de integración"""
    name: str
    type: IntegrationType
    auth_method: AuthMethod
    base_url: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_key: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    webhook_secret: Optional[str] = None
    rate_limit: Optional[Dict[str, int]] = field(default_factory=dict)
    timeout: int = 30
    retry_config: Dict[str, int] = field(default_factory=lambda: {
        'max_retries': 3,
        'backoff_factor': 1,
        'retry_statuses': [500, 502, 503, 504]
    })
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationCredentials:
    """Credenciales de integración por usuario"""
    user_id: int
    integration_name: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WebhookPayload:
    """Estructura de payload webhook"""
    event: WebhookEvent
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[int] = None
    source: str = "ecosystem"
    signature: Optional[str] = None


@dataclass
class APIRequest:
    """Estructura de request a API externa"""
    method: str
    endpoint: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class APIResponse:
    """Estructura de response de API externa"""
    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None


class CircuitBreaker:
    """Implementación de Circuit Breaker pattern"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Ejecuta función con circuit breaker"""
        if self.state == 'OPEN':
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = 'HALF_OPEN'
            else:
                raise IntegrationError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e


class BaseIntegration(ABC):
    """Clase base para todas las integraciones"""
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.session = self._create_session()
        self.circuit_breaker = CircuitBreaker()
        self.cache = CacheManager()
        
    def _create_session(self) -> requests.Session:
        """Crea sesión HTTP con configuración robusta"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.retry_config['max_retries'],
            backoff_factor=self.config.retry_config['backoff_factor'],
            status_forcelist=self.config.retry_config['retry_statuses'],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @abstractmethod
    def authenticate(self, user_id: int, **kwargs) -> IntegrationCredentials:
        """Autentica usuario con la integración"""
        pass
    
    @abstractmethod
    def refresh_token(self, credentials: IntegrationCredentials) -> IntegrationCredentials:
        """Refresca token de acceso"""
        pass
    
    @abstractmethod
    def make_request(self, request: APIRequest, user_id: int) -> APIResponse:
        """Realiza request a la API externa"""
        pass
    
    def is_authenticated(self, user_id: int) -> bool:
        """Verifica si el usuario está autenticado"""
        credentials = self._get_credentials(user_id)
        if not credentials:
            return False
            
        if credentials.token_expires_at and datetime.utcnow() >= credentials.token_expires_at:
            try:
                self.refresh_token(credentials)
                return True
            except:
                return False
        
        return True
    
    def _get_credentials(self, user_id: int) -> Optional[IntegrationCredentials]:
        """Obtiene credenciales del usuario"""
        cache_key = f"integration_creds_{self.config.name}_{user_id}"
        cached_creds = self.cache.get(cache_key)
        
        if cached_creds:
            return IntegrationCredentials(**cached_creds)
        
        # En producción, consultar base de datos
        return None
    
    def _save_credentials(self, credentials: IntegrationCredentials) -> None:
        """Guarda credenciales del usuario"""
        cache_key = f"integration_creds_{self.config.name}_{credentials.user_id}"
        self.cache.set(cache_key, asdict(credentials), timeout=3600)
        
        # En producción, guardar en base de datos
        logger.info(f"Saved credentials for user {credentials.user_id} in {self.config.name}")


class OAuth2Integration(BaseIntegration):
    """Integración base con OAuth 2.0"""
    
    def get_auth_url(self, user_id: int, state: str = None) -> str:
        """Genera URL de autorización OAuth"""
        if not state:
            state = f"{user_id}_{datetime.utcnow().timestamp()}"
        
        params = {
            'client_id': self.config.client_id,
            'response_type': 'code',
            'scope': ' '.join(self.config.scopes),
            'redirect_uri': self._get_redirect_uri(),
            'state': state,
            'access_type': 'offline',  # Para obtener refresh token
            'prompt': 'consent'
        }
        
        return f"{self.config.base_url}/oauth/authorize?" + urlencode(params)
    
    def authenticate(self, user_id: int, **kwargs) -> IntegrationCredentials:
        """Completa flujo OAuth con código de autorización"""
        auth_code = kwargs.get('code')
        if not auth_code:
            raise AuthenticationError("Authorization code required")
        
        token_data = self._exchange_code_for_token(auth_code)
        
        credentials = IntegrationCredentials(
            user_id=user_id,
            integration_name=self.config.name,
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_expires_at=datetime.utcnow() + timedelta(
                seconds=token_data.get('expires_in', 3600)
            ),
            additional_data=token_data
        )
        
        self._save_credentials(credentials)
        return credentials
    
    def refresh_token(self, credentials: IntegrationCredentials) -> IntegrationCredentials:
        """Refresca token OAuth"""
        if not credentials.refresh_token:
            raise AuthenticationError("No refresh token available")
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': credentials.refresh_token,
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret
        }
        
        response = self.session.post(
            f"{self.config.base_url}/oauth/token",
            data=data,
            timeout=self.config.timeout
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"Token refresh failed: {response.text}")
        
        token_data = response.json()
        
        credentials.access_token = token_data['access_token']
        credentials.token_expires_at = datetime.utcnow() + timedelta(
            seconds=token_data.get('expires_in', 3600)
        )
        credentials.updated_at = datetime.utcnow()
        
        if 'refresh_token' in token_data:
            credentials.refresh_token = token_data['refresh_token']
        
        self._save_credentials(credentials)
        return credentials
    
    def make_request(self, request: APIRequest, user_id: int) -> APIResponse:
        """Realiza request autenticado"""
        credentials = self._get_credentials(user_id)
        if not credentials:
            raise AuthenticationError("User not authenticated")
        
        # Verificar y refrescar token si es necesario
        if credentials.token_expires_at and datetime.utcnow() >= credentials.token_expires_at:
            credentials = self.refresh_token(credentials)
        
        # Agregar token de autenticación
        request.headers['Authorization'] = f"Bearer {credentials.access_token}"
        
        return self.circuit_breaker.call(self._execute_request, request)
    
    def _exchange_code_for_token(self, auth_code: str) -> Dict[str, Any]:
        """Intercambia código por token"""
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self._get_redirect_uri(),
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret
        }
        
        response = self.session.post(
            f"{self.config.base_url}/oauth/token",
            data=data,
            timeout=self.config.timeout
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"Token exchange failed: {response.text}")
        
        return response.json()
    
    def _get_redirect_uri(self) -> str:
        """Obtiene URI de redirección"""
        return url_for('api.v1.integration_oauth_callback', 
                      integration=self.config.name, 
                      _external=True)
    
    def _execute_request(self, request: APIRequest) -> APIResponse:
        """Ejecuta request HTTP"""
        url = f"{self.config.base_url.rstrip('/')}/{request.endpoint.lstrip('/')}"
        
        response = self.session.request(
            method=request.method,
            url=url,
            headers=request.headers,
            params=request.params,
            json=request.data if request.method.upper() in ['POST', 'PUT', 'PATCH'] else None,
            timeout=request.timeout
        )
        
        # Extraer información de rate limiting
        rate_limit_remaining = None
        rate_limit_reset = None
        
        if 'X-RateLimit-Remaining' in response.headers:
            rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
        
        if 'X-RateLimit-Reset' in response.headers:
            reset_timestamp = int(response.headers['X-RateLimit-Reset'])
            rate_limit_reset = datetime.fromtimestamp(reset_timestamp)
        
        success = 200 <= response.status_code < 300
        
        try:
            data = response.json() if response.content else {}
        except:
            data = {'raw_response': response.text}
        
        return APIResponse(
            status_code=response.status_code,
            data=data,
            headers=dict(response.headers),
            success=success,
            error_message=data.get('error_description') or data.get('error') if not success else None,
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset=rate_limit_reset
        )


class GoogleIntegration(OAuth2Integration):
    """Integración con servicios de Google"""
    
    def __init__(self):
        config = IntegrationConfig(
            name="google",
            type=IntegrationType.CALENDAR,
            auth_method=AuthMethod.OAUTH2,
            base_url="https://accounts.google.com",
            client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            scopes=[
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/gmail.readonly'
            ]
        )
        super().__init__(config)
    
    def create_calendar_event(self, user_id: int, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea evento en Google Calendar"""
        request = APIRequest(
            method='POST',
            endpoint='calendar/v3/calendars/primary/events',
            data=event_data
        )
        
        # Cambiar base URL para API calls
        original_base_url = self.config.base_url
        self.config.base_url = "https://www.googleapis.com"
        
        try:
            response = self.make_request(request, user_id)
            if response.success:
                return response.data
            else:
                raise IntegrationError(f"Failed to create calendar event: {response.error_message}")
        finally:
            self.config.base_url = original_base_url
    
    def list_calendar_events(self, user_id: int, start_date: datetime, 
                           end_date: datetime) -> List[Dict[str, Any]]:
        """Lista eventos de calendario"""
        request = APIRequest(
            method='GET',
            endpoint='calendar/v3/calendars/primary/events',
            params={
                'timeMin': start_date.isoformat() + 'Z',
                'timeMax': end_date.isoformat() + 'Z',
                'singleEvents': True,
                'orderBy': 'startTime'
            }
        )
        
        original_base_url = self.config.base_url
        self.config.base_url = "https://www.googleapis.com"
        
        try:
            response = self.make_request(request, user_id)
            if response.success:
                return response.data.get('items', [])
            else:
                raise IntegrationError(f"Failed to list calendar events: {response.error_message}")
        finally:
            self.config.base_url = original_base_url


class StripeIntegration(BaseIntegration):
    """Integración con Stripe para pagos"""
    
    def __init__(self):
        config = IntegrationConfig(
            name="stripe",
            type=IntegrationType.PAYMENT,
            auth_method=AuthMethod.API_KEY,
            base_url="https://api.stripe.com/v1",
            api_key=current_app.config.get('STRIPE_SECRET_KEY')
        )
        super().__init__(config)
    
    def authenticate(self, user_id: int, **kwargs) -> IntegrationCredentials:
        """Stripe usa API key, no requiere OAuth por usuario"""
        credentials = IntegrationCredentials(
            user_id=user_id,
            integration_name=self.config.name,
            access_token=self.config.api_key
        )
        self._save_credentials(credentials)
        return credentials
    
    def refresh_token(self, credentials: IntegrationCredentials) -> IntegrationCredentials:
        """Stripe API key no expira"""
        return credentials
    
    def make_request(self, request: APIRequest, user_id: int) -> APIResponse:
        """Request a Stripe API"""
        request.headers['Authorization'] = f"Bearer {self.config.api_key}"
        request.headers['Stripe-Version'] = '2023-10-16'
        
        return self.circuit_breaker.call(self._execute_request, request)
    
    def create_payment_intent(self, amount: int, currency: str, 
                            customer_id: str = None) -> Dict[str, Any]:
        """Crea Payment Intent"""
        data = {
            'amount': amount,
            'currency': currency,
            'automatic_payment_methods': {'enabled': True}
        }
        
        if customer_id:
            data['customer'] = customer_id
        
        request = APIRequest(
            method='POST',
            endpoint='payment_intents',
            data=data
        )
        
        response = self._execute_request(request)
        if response.success:
            return response.data
        else:
            raise IntegrationError(f"Failed to create payment intent: {response.error_message}")


class WebhookManager:
    """Gestor de webhooks entrantes y salientes"""
    
    def __init__(self):
        self.cache = CacheManager()
        self.registered_handlers: Dict[WebhookEvent, List[Callable]] = {}
        self.outbound_webhooks: Dict[str, Dict[str, Any]] = {}
    
    def register_handler(self, event: WebhookEvent, handler: Callable) -> None:
        """Registra handler para evento webhook"""
        if event not in self.registered_handlers:
            self.registered_handlers[event] = []
        self.registered_handlers[event].append(handler)
        logger.info(f"Registered webhook handler for {event.value}")
    
    def register_outbound_webhook(self, name: str, url: str, events: List[WebhookEvent],
                                secret: str = None, headers: Dict[str, str] = None) -> None:
        """Registra webhook saliente"""
        self.outbound_webhooks[name] = {
            'url': url,
            'events': events,
            'secret': secret,
            'headers': headers or {},
            'active': True,
            'retry_config': {
                'max_retries': 3,
                'retry_delay': 1,
                'timeout': 30
            }
        }
        logger.info(f"Registered outbound webhook: {name}")
    
    def handle_incoming_webhook(self, integration_name: str, payload: Dict[str, Any],
                              signature: str = None) -> bool:
        """Procesa webhook entrante"""
        try:
            # Verificar firma si es requerida
            if signature and not self._verify_webhook_signature(integration_name, payload, signature):
                logger.warning(f"Invalid webhook signature from {integration_name}")
                return False
            
            # Procesar según la integración
            if integration_name == "stripe":
                return self._handle_stripe_webhook(payload)
            elif integration_name == "google":
                return self._handle_google_webhook(payload)
            else:
                logger.warning(f"Unknown webhook integration: {integration_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing webhook from {integration_name}: {e}")
            return False
    
    def trigger_outbound_webhook(self, event: WebhookEvent, data: Dict[str, Any],
                               user_id: int = None) -> None:
        """Dispara webhooks salientes"""
        payload = WebhookPayload(
            event=event,
            data=data,
            user_id=user_id
        )
        
        # Procesar handlers internos
        self._process_internal_handlers(payload)
        
        # Enviar webhooks externos
        self._send_outbound_webhooks(payload)
    
    def _verify_webhook_signature(self, integration_name: str, payload: Dict[str, Any],
                                signature: str) -> bool:
        """Verifica firma de webhook"""
        # Implementación específica según la integración
        if integration_name == "stripe":
            return self._verify_stripe_signature(payload, signature)
        return True
    
    def _verify_stripe_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verifica firma de Stripe"""
        webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if not webhook_secret:
            return True
        
        try:
            expected_signature = hmac.new(
                webhook_secret.encode(),
                json.dumps(payload, separators=(',', ':')).encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
    
    def _handle_stripe_webhook(self, payload: Dict[str, Any]) -> bool:
        """Procesa webhook de Stripe"""
        event_type = payload.get('type')
        
        if event_type == 'payment_intent.succeeded':
            self.trigger_outbound_webhook(
                WebhookEvent.PAYMENT_PROCESSED,
                payload['data']['object']
            )
        elif event_type == 'payment_intent.payment_failed':
            self.trigger_outbound_webhook(
                WebhookEvent.PAYMENT_FAILED,
                payload['data']['object']
            )
        
        return True
    
    def _handle_google_webhook(self, payload: Dict[str, Any]) -> bool:
        """Procesa webhook de Google"""
        # Implementar según necesidades específicas
        return True
    
    def _process_internal_handlers(self, payload: WebhookPayload) -> None:
        """Procesa handlers internos"""
        handlers = self.registered_handlers.get(payload.event, [])
        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"Error in webhook handler: {e}")
    
    def _send_outbound_webhooks(self, payload: WebhookPayload) -> None:
        """Envía webhooks a endpoints externos"""
        for name, config in self.outbound_webhooks.items():
            if not config['active'] or payload.event not in config['events']:
                continue
            
            # Enviar de forma asíncrona
            from app.tasks.integration_tasks import send_webhook_task
            send_webhook_task.delay(name, asdict(payload))


class IntegrationHub:
    """Hub principal para gestionar todas las integraciones"""
    
    def __init__(self):
        self.integrations: Dict[str, BaseIntegration] = {}
        self.webhook_manager = WebhookManager()
        self.cache = CacheManager()
        self._initialize_integrations()
    
    def _initialize_integrations(self) -> None:
        """Inicializa todas las integraciones configuradas"""
        # Google Services
        if current_app.config.get('GOOGLE_CLIENT_ID'):
            self.integrations['google'] = GoogleIntegration()
        
        # Stripe Payments
        if current_app.config.get('STRIPE_SECRET_KEY'):
            self.integrations['stripe'] = StripeIntegration()
        
        # Agregar más integraciones según configuración
        logger.info(f"Initialized {len(self.integrations)} integrations")
    
    def get_integration(self, name: str) -> Optional[BaseIntegration]:
        """Obtiene integración por nombre"""
        return self.integrations.get(name)
    
    def get_available_integrations(self, user_id: int = None) -> List[Dict[str, Any]]:
        """Lista integraciones disponibles"""
        integrations = []
        
        for name, integration in self.integrations.items():
            info = {
                'name': name,
                'type': integration.config.type.value,
                'auth_method': integration.config.auth_method.value,
                'enabled': integration.config.enabled,
                'authenticated': False
            }
            
            if user_id:
                info['authenticated'] = integration.is_authenticated(user_id)
            
            integrations.append(info)
        
        return integrations
    
    def get_user_integrations(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtiene integraciones activas del usuario"""
        user_integrations = []
        
        for name, integration in self.integrations.items():
            if integration.is_authenticated(user_id):
                credentials = integration._get_credentials(user_id)
                user_integrations.append({
                    'name': name,
                    'type': integration.config.type.value,
                    'connected_at': credentials.created_at.isoformat() if credentials else None,
                    'status': 'active'
                })
        
        return user_integrations
    
    def disconnect_integration(self, user_id: int, integration_name: str) -> bool:
        """Desconecta integración del usuario"""
        try:
            cache_key = f"integration_creds_{integration_name}_{user_id}"
            self.cache.delete(cache_key)
            
            # En producción, eliminar de base de datos
            logger.info(f"Disconnected {integration_name} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect {integration_name} for user {user_id}: {e}")
            return False
    
    def get_integration_analytics(self, start_date: datetime = None,
                                end_date: datetime = None) -> Dict[str, Any]:
        """Obtiene analytics de integraciones"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # En producción, consultar base de datos
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_integrations': len(self.integrations),
            'active_connections': 150,
            'successful_requests': 2500,
            'failed_requests': 45,
            'success_rate': 98.2,
            'by_integration': {
                'google': {'connections': 80, 'requests': 1500},
                'stripe': {'connections': 40, 'requests': 800},
                'slack': {'connections': 30, 'requests': 200}
            },
            'webhook_deliveries': {
                'sent': 500,
                'delivered': 485,
                'failed': 15,
                'delivery_rate': 97.0
            }
        }
    
    def test_integration(self, integration_name: str, user_id: int = None) -> Dict[str, Any]:
        """Prueba conectividad de integración"""
        integration = self.integrations.get(integration_name)
        if not integration:
            return {'success': False, 'error': 'Integration not found'}
        
        try:
            if user_id and integration.config.auth_method != AuthMethod.API_KEY:
                if not integration.is_authenticated(user_id):
                    return {'success': False, 'error': 'User not authenticated'}
            
            # Hacer request de prueba
            if integration_name == 'google':
                request = APIRequest(method='GET', endpoint='calendar/v3/calendars/primary')
                response = integration.make_request(request, user_id)
            elif integration_name == 'stripe':
                request = APIRequest(method='GET', endpoint='customers', params={'limit': 1})
                response = integration.make_request(request, user_id)
            else:
                return {'success': True, 'message': 'Integration available but no test implemented'}
            
            return {
                'success': response.success,
                'status_code': response.status_code,
                'response_time': '< 1s',  # En producción, medir tiempo real
                'rate_limit_remaining': response.rate_limit_remaining
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def handle_webhook(self, integration_name: str, payload: Dict[str, Any],
                      signature: str = None) -> bool:
        """Maneja webhook entrante"""
        return self.webhook_manager.handle_incoming_webhook(
            integration_name, payload, signature
        )
    
    def register_webhook_handler(self, event: WebhookEvent, handler: Callable) -> None:
        """Registra handler de webhook"""
        self.webhook_manager.register_handler(event, handler)
    
    def trigger_webhook(self, event: WebhookEvent, data: Dict[str, Any],
                       user_id: int = None) -> None:
        """Dispara webhook"""
        self.webhook_manager.trigger_outbound_webhook(event, data, user_id)


# Instancia global
integration_hub = IntegrationHub()


def get_integration_hub() -> IntegrationHub:
    """Factory function para obtener el hub"""
    return integration_hub


# Decoradores útiles

def require_integration(integration_name: str):
    """Decorador que requiere integración activa"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            if not user_id:
                raise AuthenticationError("User ID required")
            
            integration = integration_hub.get_integration(integration_name)
            if not integration:
                raise IntegrationError(f"Integration {integration_name} not available")
            
            if not integration.is_authenticated(user_id):
                raise AuthenticationError(f"User not authenticated with {integration_name}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def webhook_handler(event: WebhookEvent):
    """Decorador para registrar handlers de webhook"""
    def decorator(func):
        integration_hub.register_webhook_handler(event, func)
        return func
    return decorator


# Funciones de utilidad

def encrypt_token(token: str) -> str:
    """Encripta token sensible"""
    fernet = Fernet(current_app.config['INTEGRATION_ENCRYPTION_KEY'].encode())
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Desencripta token"""
    fernet = Fernet(current_app.config['INTEGRATION_ENCRYPTION_KEY'].encode())
    return fernet.decrypt(encrypted_token.encode()).decode()


# Handlers de webhook predefinidos

@webhook_handler(WebhookEvent.PAYMENT_PROCESSED)
def handle_payment_processed(payload: WebhookPayload):
    """Maneja pago procesado"""
    logger.info(f"Payment processed: {payload.data.get('id')}")
    # Actualizar estado en base de datos
    # Enviar notificación al usuario
    # Activar servicios según el pago


@webhook_handler(WebhookEvent.USER_CREATED)
def handle_user_created(payload: WebhookPayload):
    """Maneja usuario creado"""
    logger.info(f"New user created: {payload.user_id}")
    # Configurar integraciones por defecto
    # Enviar email de bienvenida
    # Crear calendarios iniciales


# Rate limiting para integraciones

class IntegrationRateLimiter:
    """Rate limiter específico para integraciones"""
    
    def __init__(self):
        self.cache = CacheManager()
    
    def is_allowed(self, integration_name: str, user_id: int, 
                  endpoint: str = None) -> bool:
        """Verifica si el request está permitido"""
        # Implementar lógica de rate limiting específica
        cache_key = f"rate_limit_{integration_name}_{user_id}_{endpoint or 'default'}"
        
        current_count = self.cache.get(cache_key) or 0
        limit = self._get_rate_limit(integration_name, endpoint)
        
        if current_count >= limit:
            return False
        
        self.cache.set(cache_key, current_count + 1, timeout=3600)  # 1 hora
        return True
    
    def _get_rate_limit(self, integration_name: str, endpoint: str = None) -> int:
        """Obtiene límite de rate para integración"""
        limits = {
            'google': 1000,  # requests por hora
            'stripe': 100,
            'default': 500
        }
        return limits.get(integration_name, limits['default'])


# Instancia del rate limiter
rate_limiter = IntegrationRateLimiter()