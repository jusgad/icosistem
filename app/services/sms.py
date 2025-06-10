"""
SMS Service

Servicio completo para envío de SMS con múltiples proveedores, templates,
rate limiting, analytics y soporte internacional.

Author: Senior Developer
Date: 2025
"""

import re
import json
import logging
import phonenumbers
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from functools import wraps
from urllib.parse import quote_plus
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from flask import current_app
from celery import Celery
import boto3
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException

from app.core.exceptions import SMSServiceError, ExternalAPIError, ValidationError
from app.utils.cache_utils import CacheManager
from app.utils.decorators import retry_on_failure
from app.models.user import User
from app.models.notification import Notification


logger = logging.getLogger(__name__)


class SMSType(Enum):
    """Tipos de SMS soportados"""
    OTP = "otp"
    NOTIFICATION = "notification"
    MARKETING = "marketing"
    ALERT = "alert"
    REMINDER = "reminder"
    WELCOME = "welcome"
    VERIFICATION = "verification"
    MEETING_REMINDER = "meeting_reminder"
    PAYMENT_NOTIFICATION = "payment_notification"


class SMSStatus(Enum):
    """Estados de SMS"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"
    UNDELIVERED = "undelivered"


class SMSPriority(Enum):
    """Prioridades de envío"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class SMSTemplate:
    """Estructura para templates de SMS"""
    id: str
    name: str
    content: str
    sms_type: SMSType
    variables: List[str]
    max_length: int = 160
    language: str = "es"
    active: bool = True


@dataclass
class SMSMessage:
    """Estructura para mensajes SMS"""
    to: str
    message: str
    sms_type: SMSType = SMSType.NOTIFICATION
    priority: SMSPriority = SMSPriority.NORMAL
    template_id: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    user_id: Optional[int] = None
    reference_id: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class SMSResult:
    """Resultado del envío de SMS"""
    success: bool
    message_id: Optional[str] = None
    provider: Optional[str] = None
    status: SMSStatus = SMSStatus.PENDING
    error_message: Optional[str] = None
    cost: Optional[float] = None
    segments: int = 1
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class SMSProvider:
    """Clase base para proveedores SMS"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session = self._create_session()
        self.name = self.__class__.__name__.replace('Provider', '')
    
    def _create_session(self) -> requests.Session:
        """Crea sesión HTTP con reintentos"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Método base para enviar SMS"""
        raise NotImplementedError
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Obtiene estado de entrega"""
        raise NotImplementedError
    
    def get_balance(self) -> Optional[float]:
        """Obtiene balance de la cuenta"""
        raise NotImplementedError


class TwilioProvider(SMSProvider):
    """Proveedor Twilio SMS"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = TwilioClient(
            config['account_sid'],
            config['auth_token']
        )
        self.from_number = config['from_number']
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Envía SMS usando Twilio"""
        try:
            # Preparar parámetros
            params = {
                'body': message.message,
                'from_': self.from_number,
                'to': message.to
            }
            
            # Agregar parámetros opcionales
            if message.scheduled_at:
                params['send_at'] = message.scheduled_at
            
            if message.expires_at:
                params['validity_period'] = int(
                    (message.expires_at - datetime.utcnow()).total_seconds()
                )
            
            # Enviar mensaje
            twilio_message = self.client.messages.create(**params)
            
            # Calcular segmentos
            segments = self._calculate_segments(message.message)
            
            # Calcular costo aproximado
            cost = self._calculate_cost(message.to, segments)
            
            return SMSResult(
                success=True,
                message_id=twilio_message.sid,
                provider=self.name,
                status=self._map_twilio_status(twilio_message.status),
                segments=segments,
                cost=cost
            )
            
        except TwilioException as e:
            logger.error(f"Twilio SMS failed: {e}")
            return SMSResult(
                success=False,
                provider=self.name,
                status=SMSStatus.FAILED,
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error in Twilio provider: {e}")
            return SMSResult(
                success=False,
                provider=self.name,
                status=SMSStatus.FAILED,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Obtiene estado de entrega desde Twilio"""
        try:
            message = self.client.messages(message_id).fetch()
            return self._map_twilio_status(message.status)
        except TwilioException as e:
            logger.error(f"Failed to get Twilio message status: {e}")
            return SMSStatus.FAILED
    
    def get_balance(self) -> Optional[float]:
        """Obtiene balance de Twilio"""
        try:
            balance = self.client.balance.fetch()
            return float(balance.balance)
        except TwilioException as e:
            logger.error(f"Failed to get Twilio balance: {e}")
            return None
    
    def _map_twilio_status(self, twilio_status: str) -> SMSStatus:
        """Mapea estados de Twilio a nuestros estados"""
        status_map = {
            'queued': SMSStatus.QUEUED,
            'sending': SMSStatus.SENDING,
            'sent': SMSStatus.SENT,
            'delivered': SMSStatus.DELIVERED,
            'undelivered': SMSStatus.UNDELIVERED,
            'failed': SMSStatus.FAILED,
            'rejected': SMSStatus.REJECTED
        }
        return status_map.get(twilio_status, SMSStatus.PENDING)
    
    def _calculate_segments(self, message: str) -> int:
        """Calcula número de segmentos SMS"""
        # SMS estándar: 160 caracteres por segmento
        # SMS concatenado: 153 caracteres por segmento
        length = len(message)
        if length <= 160:
            return 1
        return (length - 1) // 153 + 1
    
    def _calculate_cost(self, to_number: str, segments: int) -> float:
        """Calcula costo aproximado basado en destino"""
        # Costos aproximados de Twilio (USD)
        base_costs = {
            'US': 0.0075,
            'CA': 0.0075,
            'GB': 0.0400,
            'CO': 0.0350,
            'MX': 0.0220,
            'BR': 0.0450,
            'AR': 0.0650,
        }
        
        try:
            parsed = phonenumbers.parse(to_number, None)
            country_code = phonenumbers.region_code_for_number(parsed)
            base_cost = base_costs.get(country_code, 0.05)  # Default
            return base_cost * segments
        except:
            return 0.05 * segments  # Costo por defecto


class AWSSNSProvider(SMSProvider):
    """Proveedor AWS SNS"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=config['access_key_id'],
            aws_secret_access_key=config['secret_access_key'],
            region_name=config.get('region', 'us-east-1')
        )
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Envía SMS usando AWS SNS"""
        try:
            # Configurar atributos del mensaje
            message_attributes = {
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'  # o 'Promotional'
                }
            }
            
            # Agregar sender ID si está disponible
            if 'sender_id' in self.config:
                message_attributes['AWS.SNS.SMS.SenderID'] = {
                    'DataType': 'String',
                    'StringValue': self.config['sender_id']
                }
            
            # Enviar mensaje
            response = self.sns_client.publish(
                PhoneNumber=message.to,
                Message=message.message,
                MessageAttributes=message_attributes
            )
            
            segments = self._calculate_segments(message.message)
            cost = self._calculate_cost(message.to, segments)
            
            return SMSResult(
                success=True,
                message_id=response['MessageId'],
                provider=self.name,
                status=SMSStatus.SENT,
                segments=segments,
                cost=cost
            )
            
        except Exception as e:
            logger.error(f"AWS SNS SMS failed: {e}")
            return SMSResult(
                success=False,
                provider=self.name,
                status=SMSStatus.FAILED,
                error_message=str(e)
            )
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """AWS SNS no proporciona tracking detallado para SMS"""
        return SMSStatus.SENT
    
    def get_balance(self) -> Optional[float]:
        """AWS SNS no tiene concepto de balance pre-pagado"""
        return None
    
    def _calculate_segments(self, message: str) -> int:
        """Calcula segmentos para AWS SNS"""
        return (len(message) - 1) // 160 + 1
    
    def _calculate_cost(self, to_number: str, segments: int) -> float:
        """Calcula costo AWS SNS"""
        # Costos aproximados AWS SNS (USD)
        return 0.0075 * segments  # Costo promedio


class VonageProvider(SMSProvider):
    """Proveedor Vonage (ex-Nexmo)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.from_number = config.get('from_number', 'VONAGE')
        self.base_url = "https://rest.nexmo.com"
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Envía SMS usando Vonage"""
        try:
            url = f"{self.base_url}/sms/json"
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'to': message.to,
                'from': self.from_number,
                'text': message.message,
                'type': 'text'
            }
            
            response = self.session.post(url, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result['messages'][0]['status'] == '0':
                segments = int(result['messages'][0]['message-count'])
                cost = float(result['messages'][0]['message-price'])
                
                return SMSResult(
                    success=True,
                    message_id=result['messages'][0]['message-id'],
                    provider=self.name,
                    status=SMSStatus.SENT,
                    segments=segments,
                    cost=cost
                )
            else:
                error_msg = result['messages'][0]['error-text']
                return SMSResult(
                    success=False,
                    provider=self.name,
                    status=SMSStatus.FAILED,
                    error_message=error_msg
                )
                
        except Exception as e:
            logger.error(f"Vonage SMS failed: {e}")
            return SMSResult(
                success=False,
                provider=self.name,
                status=SMSStatus.FAILED,
                error_message=str(e)
            )
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Obtiene estado desde Vonage"""
        try:
            url = f"{self.base_url}/search/message"
            params = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'id': message_id
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            status = result.get('status', 'unknown')
            
            status_map = {
                'delivered': SMSStatus.DELIVERED,
                'expired': SMSStatus.FAILED,
                'failed': SMSStatus.FAILED,
                'rejected': SMSStatus.REJECTED,
                'unknown': SMSStatus.SENT
            }
            
            return status_map.get(status, SMSStatus.SENT)
            
        except Exception as e:
            logger.error(f"Failed to get Vonage message status: {e}")
            return SMSStatus.SENT
    
    def get_balance(self) -> Optional[float]:
        """Obtiene balance de Vonage"""
        try:
            url = f"{self.base_url}/account/get-balance"
            params = {
                'api_key': self.api_key,
                'api_secret': self.api_secret
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            return float(result['value'])
            
        except Exception as e:
            logger.error(f"Failed to get Vonage balance: {e}")
            return None


class SMSService:
    """
    Servicio principal para manejo de SMS.
    Implementa múltiples proveedores, templates, rate limiting y analytics.
    """
    
    def __init__(self):
        self.cache = CacheManager()
        self.providers = self._initialize_providers()
        self.templates = self._load_templates()
        self.blacklist = self._load_blacklist()
        self.rate_limits = {
            SMSType.OTP: {'limit': 5, 'window': 3600},  # 5 OTP por hora
            SMSType.MARKETING: {'limit': 1, 'window': 86400},  # 1 marketing por día
            SMSType.NOTIFICATION: {'limit': 10, 'window': 3600},  # 10 notif por hora
        }
    
    def _initialize_providers(self) -> List[SMSProvider]:
        """Inicializa proveedores SMS"""
        providers = []
        
        # Twilio
        twilio_config = current_app.config.get('TWILIO_SMS_CONFIG')
        if twilio_config:
            providers.append(TwilioProvider(twilio_config))
        
        # AWS SNS
        aws_config = current_app.config.get('AWS_SNS_CONFIG')
        if aws_config:
            providers.append(AWSSNSProvider(aws_config))
        
        # Vonage
        vonage_config = current_app.config.get('VONAGE_SMS_CONFIG')
        if vonage_config:
            providers.append(VonageProvider(vonage_config))
        
        if not providers:
            logger.warning("No SMS providers configured")
        
        return providers
    
    def _load_templates(self) -> Dict[str, SMSTemplate]:
        """Carga templates predefinidos"""
        templates = {
            'welcome_entrepreneur': SMSTemplate(
                id='welcome_entrepreneur',
                name='Bienvenida Emprendedor',
                content='¡Hola {name}! Bienvenido al ecosistema de emprendimiento. Tu cuenta ha sido activada exitosamente.',
                sms_type=SMSType.WELCOME,
                variables=['name']
            ),
            'otp_verification': SMSTemplate(
                id='otp_verification',
                name='Código OTP',
                content='Tu código de verificación es: {otp_code}. Válido por {expiry_minutes} minutos. No lo compartas.',
                sms_type=SMSType.OTP,
                variables=['otp_code', 'expiry_minutes'],
                max_length=160
            ),
            'meeting_reminder': SMSTemplate(
                id='meeting_reminder',
                name='Recordatorio Reunión',
                content='Recordatorio: Tienes una reunión "{meeting_title}" programada para {meeting_time}. Link: {meeting_link}',
                sms_type=SMSType.MEETING_REMINDER,
                variables=['meeting_title', 'meeting_time', 'meeting_link']
            ),
            'payment_notification': SMSTemplate(
                id='payment_notification',
                name='Notificación Pago',
                content='Se ha procesado tu pago de {amount} {currency}. Referencia: {reference}. ¡Gracias!',
                sms_type=SMSType.PAYMENT_NOTIFICATION,
                variables=['amount', 'currency', 'reference']
            ),
            'project_milestone': SMSTemplate(
                id='project_milestone',
                name='Hito de Proyecto',
                content='¡Felicidades {name}! Has completado el hito "{milestone}" de tu proyecto "{project}". ¡Sigue adelante!',
                sms_type=SMSType.NOTIFICATION,
                variables=['name', 'milestone', 'project']
            )
        }
        return templates
    
    def _load_blacklist(self) -> set:
        """Carga números en blacklist"""
        # En producción, esto vendría de la base de datos
        blacklist_key = "sms_blacklist"
        cached_blacklist = self.cache.get(blacklist_key)
        if cached_blacklist:
            return set(cached_blacklist)
        
        # Cargar desde configuración o BD
        blacklist = set(current_app.config.get('SMS_BLACKLIST', []))
        self.cache.set(blacklist_key, list(blacklist), timeout=3600)
        return blacklist
    
    def send_sms(self, message: SMSMessage, async_send: bool = False) -> SMSResult:
        """
        Envía un SMS individual.
        
        Args:
            message: Mensaje a enviar
            async_send: Si enviar de forma asíncrona
            
        Returns:
            SMSResult: Resultado del envío
        """
        try:
            # Validaciones previas
            self._validate_message(message)
            
            # Verificar rate limiting
            if not self._check_rate_limit(message):
                return SMSResult(
                    success=False,
                    status=SMSStatus.REJECTED,
                    error_message="Rate limit exceeded"
                )
            
            # Verificar blacklist
            if self._is_blacklisted(message.to):
                return SMSResult(
                    success=False,
                    status=SMSStatus.REJECTED,
                    error_message="Number is blacklisted"
                )
            
            # Procesar template si aplica
            if message.template_id and message.variables:
                message.message = self._render_template(
                    message.template_id, 
                    message.variables
                )
            
            # Envío asíncrono
            if async_send:
                from app.tasks.sms_tasks import send_sms_task
                send_sms_task.delay(asdict(message))
                return SMSResult(
                    success=True,
                    status=SMSStatus.QUEUED,
                    message_id=f"queued_{datetime.utcnow().timestamp()}"
                )
            
            # Envío síncrono
            return self._send_with_fallback(message)
            
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_message=str(e)
            )
    
    def send_bulk_sms(self, messages: List[SMSMessage], 
                     batch_size: int = 100) -> Dict[str, Any]:
        """
        Envía SMS en lote de forma asíncrona.
        
        Args:
            messages: Lista de mensajes
            batch_size: Tamaño del lote
            
        Returns:
            Dict con estadísticas del envío
        """
        if not messages:
            return {'total': 0, 'queued': 0, 'failed': 0}
        
        # Validar todos los mensajes
        valid_messages = []
        failed_count = 0
        
        for message in messages:
            try:
                self._validate_message(message)
                if not self._is_blacklisted(message.to):
                    valid_messages.append(message)
                else:
                    failed_count += 1
            except Exception as e:
                logger.warning(f"Invalid message for {message.to}: {e}")
                failed_count += 1
        
        # Enviar en lotes
        from app.tasks.sms_tasks import send_bulk_sms_task
        
        queued_count = 0
        for i in range(0, len(valid_messages), batch_size):
            batch = valid_messages[i:i + batch_size]
            batch_data = [asdict(msg) for msg in batch]
            send_bulk_sms_task.delay(batch_data)
            queued_count += len(batch)
        
        return {
            'total': len(messages),
            'queued': queued_count,
            'failed': failed_count,
            'batches': (len(valid_messages) + batch_size - 1) // batch_size
        }
    
    def send_otp(self, phone_number: str, code: str, 
                expiry_minutes: int = 10) -> SMSResult:
        """Envía código OTP"""
        message = SMSMessage(
            to=phone_number,
            message="",  # Se llenará con template
            sms_type=SMSType.OTP,
            priority=SMSPriority.HIGH,
            template_id='otp_verification',
            variables={
                'otp_code': code,
                'expiry_minutes': str(expiry_minutes)
            },
            expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes)
        )
        
        return self.send_sms(message)
    
    def send_welcome_message(self, user: User) -> SMSResult:
        """Envía mensaje de bienvenida"""
        if not user.phone:
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_message="User has no phone number"
            )
        
        message = SMSMessage(
            to=user.phone,
            message="",
            sms_type=SMSType.WELCOME,
            template_id='welcome_entrepreneur',
            variables={'name': user.first_name or user.username},
            user_id=user.id
        )
        
        return self.send_sms(message, async_send=True)
    
    def send_meeting_reminder(self, phone_number: str, meeting_data: Dict[str, Any],
                            user_id: Optional[int] = None) -> SMSResult:
        """Envía recordatorio de reunión"""
        message = SMSMessage(
            to=phone_number,
            message="",
            sms_type=SMSType.MEETING_REMINDER,
            template_id='meeting_reminder',
            variables=meeting_data,
            user_id=user_id,
            scheduled_at=meeting_data.get('reminder_time')
        )
        
        return self.send_sms(message, async_send=True)
    
    def get_delivery_status(self, message_id: str, 
                          provider_name: str = None) -> SMSStatus:
        """Obtiene estado de entrega de un mensaje"""
        if provider_name:
            provider = self._get_provider_by_name(provider_name)
            if provider:
                return provider.get_delivery_status(message_id)
        
        # Intentar con todos los proveedores
        for provider in self.providers:
            try:
                status = provider.get_delivery_status(message_id)
                if status != SMSStatus.PENDING:
                    return status
            except Exception as e:
                logger.warning(f"Failed to get status from {provider.name}: {e}")
                continue
        
        return SMSStatus.PENDING
    
    def get_provider_balances(self) -> Dict[str, Optional[float]]:
        """Obtiene balances de todos los proveedores"""
        balances = {}
        for provider in self.providers:
            try:
                balance = provider.get_balance()
                balances[provider.name] = balance
            except Exception as e:
                logger.error(f"Failed to get balance from {provider.name}: {e}")
                balances[provider.name] = None
        
        return balances
    
    def add_to_blacklist(self, phone_number: str, reason: str = None) -> bool:
        """Agrega número a blacklist"""
        try:
            normalized_number = self._normalize_phone_number(phone_number)
            self.blacklist.add(normalized_number)
            
            # Actualizar cache
            blacklist_key = "sms_blacklist"
            self.cache.set(blacklist_key, list(self.blacklist), timeout=3600)
            
            # Log del evento
            logger.info(f"Added {normalized_number} to SMS blacklist. Reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add {phone_number} to blacklist: {e}")
            return False
    
    def remove_from_blacklist(self, phone_number: str) -> bool:
        """Remueve número de blacklist"""
        try:
            normalized_number = self._normalize_phone_number(phone_number)
            self.blacklist.discard(normalized_number)
            
            # Actualizar cache
            blacklist_key = "sms_blacklist"
            self.cache.set(blacklist_key, list(self.blacklist), timeout=3600)
            
            logger.info(f"Removed {normalized_number} from SMS blacklist")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove {phone_number} from blacklist: {e}")
            return False
    
    def get_analytics(self, start_date: datetime = None,
                     end_date: datetime = None) -> Dict[str, Any]:
        """Obtiene analytics de SMS"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # En producción, esto consultaría la base de datos
        # Por ahora retornamos datos de ejemplo
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_sent': 1250,
            'total_delivered': 1180,
            'total_failed': 70,
            'delivery_rate': 94.4,
            'total_cost': 15.75,
            'by_type': {
                'otp': 450,
                'notification': 600,
                'marketing': 200
            },
            'by_provider': {
                'Twilio': 800,
                'AWSSNS': 300,
                'Vonage': 150
            },
            'top_countries': {
                'CO': 500,
                'MX': 300,
                'US': 250,
                'BR': 200
            }
        }
    
    def _validate_message(self, message: SMSMessage) -> None:
        """Valida un mensaje SMS"""
        # Validar número de teléfono
        try:
            parsed_number = phonenumbers.parse(message.to, None)
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError(f"Invalid phone number: {message.to}")
            message.to = phonenumbers.format_number(
                parsed_number, 
                phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException as e:
            raise ValidationError(f"Cannot parse phone number {message.to}: {e}")
        
        # Validar longitud del mensaje
        if len(message.message) > 1600:  # 10 segmentos máximo
            raise ValidationError("Message too long (max 1600 characters)")
        
        # Validar template si se especifica
        if message.template_id and message.template_id not in self.templates:
            raise ValidationError(f"Template {message.template_id} not found")
        
        # Validar variables de template
        if message.template_id and message.variables:
            template = self.templates[message.template_id]
            missing_vars = set(template.variables) - set(message.variables.keys())
            if missing_vars:
                raise ValidationError(f"Missing template variables: {missing_vars}")
    
    def _check_rate_limit(self, message: SMSMessage) -> bool:
        """Verifica rate limiting"""
        if message.sms_type not in self.rate_limits:
            return True
        
        rate_config = self.rate_limits[message.sms_type]
        cache_key = f"sms_rate_limit_{message.sms_type.value}_{message.to}"
        
        # Obtener contador actual
        current_count = self.cache.get(cache_key) or 0
        
        if current_count >= rate_config['limit']:
            logger.warning(f"Rate limit exceeded for {message.to}, type {message.sms_type.value}")
            return False
        
        # Incrementar contador
        self.cache.set(
            cache_key, 
            current_count + 1, 
            timeout=rate_config['window']
        )
        
        return True
    
    def _is_blacklisted(self, phone_number: str) -> bool:
        """Verifica si un número está en blacklist"""
        try:
            normalized = self._normalize_phone_number(phone_number)
            return normalized in self.blacklist
        except:
            return False
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normaliza número de teléfono a formato E164"""
        try:
            parsed = phonenumbers.parse(phone_number, None)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except:
            return phone_number
    
    def _render_template(self, template_id: str, variables: Dict[str, Any]) -> str:
        """Renderiza un template con las variables"""
        if template_id not in self.templates:
            raise ValidationError(f"Template {template_id} not found")
        
        template = self.templates[template_id]
        
        try:
            return template.content.format(**variables)
        except KeyError as e:
            raise ValidationError(f"Missing template variable: {e}")
        except Exception as e:
            raise ValidationError(f"Template rendering error: {e}")
    
    def _send_with_fallback(self, message: SMSMessage) -> SMSResult:
        """Envía SMS con fallback automático entre proveedores"""
        if not self.providers:
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_message="No SMS providers configured"
            )
        
        last_error = None
        
        # Intentar con el proveedor especificado primero
        if message.provider:
            provider = self._get_provider_by_name(message.provider)
            if provider:
                try:
                    result = provider.send_sms(message)
                    if result.success:
                        self._log_sms_sent(message, result)
                        return result
                    last_error = result.error_message
                except Exception as e:
                    last_error = str(e)
        
        # Fallback a otros proveedores
        for provider in self.providers:
            if message.provider and provider.name == message.provider:
                continue  # Ya intentamos con este
            
            try:
                result = provider.send_sms(message)
                if result.success:
                    self._log_sms_sent(message, result)
                    return result
                last_error = result.error_message
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue
        
        # Todos los proveedores fallaron
        return SMSResult(
            success=False,
            status=SMSStatus.FAILED,
            error_message=f"All providers failed. Last error: {last_error}"
        )
    
    def _get_provider_by_name(self, name: str) -> Optional[SMSProvider]:
        """Obtiene proveedor por nombre"""
        for provider in self.providers:
            if provider.name.lower() == name.lower():
                return provider
        return None
    
    def _log_sms_sent(self, message: SMSMessage, result: SMSResult) -> None:
        """Log del envío de SMS"""
        logger.info(
            f"SMS sent successfully - To: {message.to}, "
            f"Type: {message.sms_type.value}, "
            f"Provider: {result.provider}, "
            f"MessageID: {result.message_id}, "
            f"Segments: {result.segments}, "
            f"Cost: {result.cost}"
        )
        
        # Aquí se podría guardar en base de datos para analytics
        # SMSLog.create(message=message, result=result)


# Instancia global del servicio
sms_service = SMSService()


def get_sms_service() -> SMSService:
    """Factory function para obtener el servicio SMS"""
    return sms_service


# Funciones de utilidad

def send_otp_sms(phone_number: str, code: str, expiry_minutes: int = 10) -> SMSResult:
    """Función helper para enviar OTP"""
    return sms_service.send_otp(phone_number, code, expiry_minutes)


def send_notification_sms(phone_number: str, message: str, 
                         user_id: Optional[int] = None) -> SMSResult:
    """Función helper para enviar notificación"""
    sms_message = SMSMessage(
        to=phone_number,
        message=message,
        sms_type=SMSType.NOTIFICATION,
        user_id=user_id
    )
    return sms_service.send_sms(sms_message, async_send=True)


# Decoradores

def sms_notification(phone_field: str = 'phone', 
                    message_field: str = 'sms_message'):
    """
    Decorador para enviar SMS automáticamente.
    
    Usage:
        @sms_notification('user_phone', 'notification_text')
        def create_user(user_data):
            # Se enviará SMS automáticamente
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Intentar extraer datos para SMS
            if args and isinstance(args[0], dict):
                data = args[0]
                phone = data.get(phone_field)
                message = data.get(message_field)
                
                if phone and message:
                    try:
                        send_notification_sms(phone, message)
                    except Exception as e:
                        logger.error(f"Failed to send automatic SMS: {e}")
            
            return result
        return wrapper
    return decorator


# Filtros para templates

def sms_format_phone(phone_number: str) -> str:
    """Formatea número de teléfono para mostrar"""
    try:
        parsed = phonenumbers.parse(phone_number, None)
        return phonenumbers.format_number(
            parsed, 
            phonenumbers.PhoneNumberFormat.NATIONAL
        )
    except:
        return phone_number