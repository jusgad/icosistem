"""
Clase base avanzada para servicios del ecosistema de emprendimiento.

Este módulo proporciona la infraestructura base para todos los servicios del sistema,
incluyendo patrones empresariales como Service Layer, Unit of Work, Repository Pattern,
Event-Driven Architecture y Domain-Driven Design.

Características principales:
- Service base class con lifecycle completo
- Transaction management automático
- Event-driven architecture integrada
- Caching inteligente multinivel
- Async/await support completo
- Configuration management avanzado
- Validation framework integrado
- Metrics y monitoring automático
- Testing utilities incorporadas
- Resource management automático
- Error handling y logging estructurado
- Performance optimization automática

Autor: Sistema de Emprendimiento
Versión: 2.0
"""

import asyncio
import inspect
import json
import logging
import time
import threading
import traceback
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps, lru_cache
from typing import (
    Dict, List, Any, Optional, Callable, Type, Union, Tuple, 
    Generic, TypeVar, ClassVar, AsyncGenerator, Generator
)
from weakref import WeakValueDictionary

import redis
from flask import current_app, g, request, has_request_context
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Type variables
T = TypeVar('T')
ServiceType = TypeVar('ServiceType', bound='BaseService')


class ServiceState(Enum):
    """Estados del ciclo de vida de un servicio."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


class LogLevel(Enum):
    """Niveles de logging específicos para servicios."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CacheStrategy(Enum):
    """Estrategias de caching para servicios."""
    NONE = "none"
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"
    DATABASE = "database"


@dataclass
class ServiceEvent:
    """Evento del sistema de servicios."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    event_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ServiceConfiguration:
    """Configuración de un servicio."""
    name: str
    enabled: bool = True
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_strategy: CacheStrategy = CacheStrategy.MEMORY
    cache_ttl: int = 300
    rate_limit: Optional[str] = None
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    async_enabled: bool = False
    database_transactions: bool = True
    event_publishing: bool = True
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceValidationRule:
    """Regla de validación para servicios."""
    field: str
    rule_type: str  # required, type, range, regex, custom
    rule_config: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class ServiceValidator:
    """Validador de datos para servicios."""
    
    def __init__(self):
        self.rules: List[ServiceValidationRule] = []
        self.custom_validators: Dict[str, Callable] = {}
    
    def add_rule(self, field: str, rule_type: str, **config):
        """Añade una regla de validación."""
        rule = ServiceValidationRule(
            field=field,
            rule_type=rule_type,
            rule_config=config,
            error_message=config.get('message', f'Validation failed for {field}')
        )
        self.rules.append(rule)
        return self
    
    def required(self, field: str, message: str = None):
        """Campo requerido."""
        return self.add_rule(field, 'required', message=message or f'{field} is required')
    
    def type_check(self, field: str, expected_type: Type, message: str = None):
        """Verificación de tipo."""
        return self.add_rule(
            field, 'type', 
            expected_type=expected_type,
            message=message or f'{field} must be of type {expected_type.__name__}'
        )
    
    def range_check(self, field: str, min_val=None, max_val=None, message: str = None):
        """Verificación de rango."""
        return self.add_rule(
            field, 'range',
            min_val=min_val, max_val=max_val,
            message=message or f'{field} out of range'
        )
    
    def custom(self, field: str, validator: Callable, message: str = None):
        """Validador personalizado."""
        validator_name = f"custom_{field}_{id(validator)}"
        self.custom_validators[validator_name] = validator
        return self.add_rule(
            field, 'custom',
            validator=validator_name,
            message=message or f'{field} failed custom validation'
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Ejecuta validación de datos."""
        errors = []
        
        for rule in self.rules:
            field_value = data.get(rule.field)
            
            if rule.rule_type == 'required':
                if field_value is None or field_value == '':
                    errors.append(rule.error_message)
            
            elif rule.rule_type == 'type' and field_value is not None:
                expected_type = rule.rule_config['expected_type']
                if not isinstance(field_value, expected_type):
                    errors.append(rule.error_message)
            
            elif rule.rule_type == 'range' and field_value is not None:
                min_val = rule.rule_config.get('min_val')
                max_val = rule.rule_config.get('max_val')
                
                if min_val is not None and field_value < min_val:
                    errors.append(rule.error_message)
                if max_val is not None and field_value > max_val:
                    errors.append(rule.error_message)
            
            elif rule.rule_type == 'custom' and field_value is not None:
                validator_name = rule.rule_config['validator']
                validator = self.custom_validators.get(validator_name)
                if validator and not validator(field_value):
                    errors.append(rule.error_message)
        
        return len(errors) == 0, errors


class ServiceCache:
    """Sistema de cache inteligente para servicios."""
    
    def __init__(self, strategy: CacheStrategy = CacheStrategy.MEMORY, ttl: int = 300):
        self.strategy = strategy
        self.ttl = ttl
        self._memory_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._redis_client = None
        self._lock = threading.Lock()
    
    @property
    def redis_client(self):
        """Cliente Redis lazy-loaded."""
        if self._redis_client is None and self.strategy in [CacheStrategy.REDIS, CacheStrategy.HYBRID]:
            try:
                from app.extensions import redis_client
                self._redis_client = redis_client
            except ImportError:
                # Fallback a configuración directa
                self._redis_client = redis.Redis(
                    host=current_app.config.get('REDIS_HOST', 'localhost'),
                    port=current_app.config.get('REDIS_PORT', 6379),
                    decode_responses=True
                )
        return self._redis_client
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """Verifica si un item ha expirado."""
        return datetime.utcnow() - timestamp > timedelta(seconds=self.ttl)
    
    def _generate_key(self, service_name: str, method_name: str, *args, **kwargs) -> str:
        """Genera clave de cache."""
        import hashlib
        
        # Crear hash de argumentos
        args_str = json.dumps([str(arg) for arg in args], sort_keys=True)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        combined = f"{args_str}:{kwargs_str}"
        
        args_hash = hashlib.md5(combined.encode()).hexdigest()
        return f"service:{service_name}:{method_name}:{args_hash}"
    
    def get(self, service_name: str, method_name: str, *args, **kwargs) -> Optional[Any]:
        """Obtiene valor del cache."""
        cache_key = self._generate_key(service_name, method_name, *args, **kwargs)
        
        try:
            if self.strategy == CacheStrategy.MEMORY:
                return self._get_from_memory(cache_key)
            elif self.strategy == CacheStrategy.REDIS:
                return self._get_from_redis(cache_key)
            elif self.strategy == CacheStrategy.HYBRID:
                # Intentar memoria primero, luego Redis
                value = self._get_from_memory(cache_key)
                if value is None:
                    value = self._get_from_redis(cache_key)
                    if value is not None:
                        # Guardar en memoria para próximas consultas
                        self._set_in_memory(cache_key, value)
                return value
        except Exception as e:
            logging.warning(f"Error obteniendo cache {cache_key}: {str(e)}")
        
        return None
    
    def set(self, service_name: str, method_name: str, value: Any, *args, **kwargs):
        """Guarda valor en cache."""
        cache_key = self._generate_key(service_name, method_name, *args, **kwargs)
        
        try:
            if self.strategy == CacheStrategy.MEMORY:
                self._set_in_memory(cache_key, value)
            elif self.strategy == CacheStrategy.REDIS:
                self._set_in_redis(cache_key, value)
            elif self.strategy == CacheStrategy.HYBRID:
                # Guardar en ambos
                self._set_in_memory(cache_key, value)
                self._set_in_redis(cache_key, value)
        except Exception as e:
            logging.warning(f"Error guardando cache {cache_key}: {str(e)}")
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Obtiene valor de cache en memoria."""
        with self._lock:
            if key in self._memory_cache:
                value, timestamp = self._memory_cache[key]
                if not self._is_expired(timestamp):
                    return value
                else:
                    del self._memory_cache[key]
        return None
    
    def _set_in_memory(self, key: str, value: Any):
        """Guarda valor en cache en memoria."""
        with self._lock:
            self._memory_cache[key] = (value, datetime.utcnow())
    
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Obtiene valor de Redis."""
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logging.warning(f"Error obteniendo de Redis {key}: {str(e)}")
        return None
    
    def _set_in_redis(self, key: str, value: Any):
        """Guarda valor en Redis."""
        if self.redis_client:
            try:
                serialized = json.dumps(value, default=str)
                self.redis_client.setex(key, self.ttl, serialized)
            except Exception as e:
                logging.warning(f"Error guardando en Redis {key}: {str(e)}")
    
    def invalidate(self, service_name: str, method_name: str = None):
        """Invalida cache de un servicio o método específico."""
        pattern = f"service:{service_name}"
        if method_name:
            pattern += f":{method_name}"
        pattern += ":*"
        
        # Limpiar memoria
        with self._lock:
            keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(pattern[:-1])]
            for key in keys_to_remove:
                del self._memory_cache[key]
        
        # Limpiar Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logging.warning(f"Error invalidando Redis con patrón {pattern}: {str(e)}")


class ServiceLogger:
    """Logger especializado para servicios."""
    
    def __init__(self, service_name: str, level: LogLevel = LogLevel.INFO):
        self.service_name = service_name
        self.level = level
        self.logger = logging.getLogger(f"services.{service_name}")
        self._correlation_id = None
        self._user_id = None
        self._session_id = None
    
    def set_context(self, correlation_id: str = None, user_id: str = None, session_id: str = None):
        """Establece contexto de logging."""
        self._correlation_id = correlation_id
        self._user_id = user_id
        self._session_id = session_id
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Formatea mensaje con contexto."""
        context = []
        
        if self._correlation_id:
            context.append(f"correlation_id={self._correlation_id}")
        if self._user_id:
            context.append(f"user_id={self._user_id}")
        if self._session_id:
            context.append(f"session_id={self._session_id}")
        
        if kwargs:
            context.extend([f"{k}={v}" for k, v in kwargs.items()])
        
        context_str = " | ".join(context)
        return f"[{self.service_name}] {message}" + (f" | {context_str}" if context else "")
    
    def trace(self, message: str, **kwargs):
        """Log trace level."""
        if self.level.value == LogLevel.TRACE.value:
            self.logger.debug(self._format_message(f"TRACE: {message}", **kwargs))
    
    def debug(self, message: str, **kwargs):
        """Log debug level."""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info level."""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning level."""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, exception: Exception = None, **kwargs):
        """Log error level."""
        if exception:
            kwargs['exception_type'] = type(exception).__name__
            kwargs['exception_message'] = str(exception)
            self.logger.error(self._format_message(message, **kwargs), exc_info=exception)
        else:
            self.logger.error(self._format_message(message, **kwargs))
    
    def critical(self, message: str, exception: Exception = None, **kwargs):
        """Log critical level."""
        if exception:
            kwargs['exception_type'] = type(exception).__name__
            kwargs['exception_message'] = str(exception)
            self.logger.critical(self._format_message(message, **kwargs), exc_info=exception)
        else:
            self.logger.critical(self._format_message(message, **kwargs))


class ServiceMetrics:
    """Sistema de métricas avanzado para servicios."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.call_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_execution_time = 0.0
        self.min_execution_time = float('inf')
        self.max_execution_time = 0.0
        self.last_called = None
        self.last_error = None
        self.error_types: Dict[str, int] = {}
        self.method_metrics: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def record_call(self, method_name: str, execution_time: float, 
                   success: bool, error_type: str = None):
        """Registra una llamada al servicio."""
        with self._lock:
            # Métricas generales
            self.call_count += 1
            self.total_execution_time += execution_time
            self.min_execution_time = min(self.min_execution_time, execution_time)
            self.max_execution_time = max(self.max_execution_time, execution_time)
            self.last_called = datetime.utcnow()
            
            if success:
                self.success_count += 1
            else:
                self.error_count += 1
                if error_type:
                    self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
                    self.last_error = error_type
            
            # Métricas por método
            if method_name not in self.method_metrics:
                self.method_metrics[method_name] = {
                    'call_count': 0,
                    'success_count': 0,
                    'error_count': 0,
                    'total_time': 0.0,
                    'avg_time': 0.0
                }
            
            method_stats = self.method_metrics[method_name]
            method_stats['call_count'] += 1
            method_stats['total_time'] += execution_time
            method_stats['avg_time'] = method_stats['total_time'] / method_stats['call_count']
            
            if success:
                method_stats['success_count'] += 1
            else:
                method_stats['error_count'] += 1
    
    @property
    def success_rate(self) -> float:
        """Tasa de éxito del servicio."""
        if self.call_count == 0:
            return 0.0
        return (self.success_count / self.call_count) * 100
    
    @property
    def avg_execution_time(self) -> float:
        """Tiempo promedio de ejecución."""
        if self.call_count == 0:
            return 0.0
        return self.total_execution_time / self.call_count
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas."""
        return {
            'service_name': self.service_name,
            'call_count': self.call_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'min_execution_time': self.min_execution_time if self.min_execution_time != float('inf') else 0,
            'max_execution_time': self.max_execution_time,
            'last_called': self.last_called.isoformat() if self.last_called else None,
            'last_error': self.last_error,
            'error_types': self.error_types,
            'method_metrics': self.method_metrics
        }


class ServiceContext:
    """Contexto de ejecución para servicios."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.correlation_id = str(uuid.uuid4())
        self.user_id = None
        self.session_id = None
        self.start_time = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        self._db_session = None
        self._events: List[ServiceEvent] = []
    
    @property
    def db_session(self) -> Optional[Session]:
        """Sesión de base de datos del contexto."""
        return self._db_session
    
    @db_session.setter
    def db_session(self, session: Session):
        """Establece sesión de base de datos."""
        self._db_session = session
    
    def add_event(self, event_type: str, data: Dict[str, Any] = None):
        """Añade evento al contexto."""
        event = ServiceEvent(
            service_name=self.service_name,
            event_type=event_type,
            data=data or {},
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            session_id=self.session_id
        )
        self._events.append(event)
    
    def get_events(self) -> List[ServiceEvent]:
        """Obtiene todos los eventos del contexto."""
        return self._events.copy()
    
    def set_user_context(self, user_id: str = None, session_id: str = None):
        """Establece contexto de usuario."""
        self.user_id = user_id
        self.session_id = session_id


class BaseService(ABC):
    """
    Clase base avanzada para todos los servicios del ecosistema.
    
    Proporciona infraestructura completa para servicios empresariales incluyendo:
    - Lifecycle management completo
    - Transaction management automático  
    - Event-driven architecture
    - Caching inteligente
    - Validation framework
    - Metrics y monitoring
    - Async/await support
    - Testing utilities
    """
    
    # Class variables
    _instances: ClassVar[WeakValueDictionary] = WeakValueDictionary()
    _global_config: ClassVar[Dict[str, Any]] = {}
    
    def __init__(self, name: str = None, config: ServiceConfiguration = None):
        self.name = name or self.__class__.__name__.replace('Service', '').lower()
        self.config = config or ServiceConfiguration(name=self.name)
        self.state = ServiceState.UNINITIALIZED
        
        # Componentes del servicio
        self.logger = ServiceLogger(self.name)
        self.metrics = ServiceMetrics(self.name)
        self.cache = ServiceCache(self.config.cache_strategy, self.config.cache_ttl)
        self.validator = ServiceValidator()
        
        # Contexto y eventos
        self._context = ServiceContext(self.name)
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Dependencies y recursos
        self.dependencies: List[str] = []
        self._resources: Dict[str, Any] = {}
        self._cleanup_callbacks: List[Callable] = []
        
        # Threading y async
        self._lock = threading.Lock()
        self._async_tasks: List[asyncio.Task] = []
        
        # Almacenar instancia
        BaseService._instances[id(self)] = self
        
        # Auto-configurar si es necesario
        self._auto_configure()
    
    def _auto_configure(self):
        """Configuración automática basada en el entorno."""
        if has_request_context():
            # Extraer contexto de usuario del request
            try:
                from flask_login import current_user
                if current_user and current_user.is_authenticated:
                    self._context.set_user_context(
                        user_id=str(current_user.id),
                        session_id=request.session.get('session_id')
                    )
            except ImportError:
                pass
            
            # Establecer correlation ID desde headers
            correlation_id = request.headers.get('X-Correlation-ID')
            if correlation_id:
                self._context.correlation_id = correlation_id
    
    # Lifecycle methods
    
    def initialize(self):
        """Inicializa el servicio."""
        if self.state != ServiceState.UNINITIALIZED:
            return
        
        self.state = ServiceState.INITIALIZING
        self.logger.info("Inicializando servicio")
        
        try:
            # Verificar dependencias
            self._check_dependencies()
            
            # Configurar validaciones
            self._setup_validations()
            
            # Inicialización específica del servicio
            self._perform_initialization()
            
            # Configurar event handlers
            self._setup_event_handlers()
            
            # Marcar como listo
            self.state = ServiceState.READY
            self.logger.info("Servicio inicializado correctamente")
            
            # Emitir evento de inicialización
            self._emit_event('service.initialized', {'state': self.state.value})
            
        except Exception as e:
            self.state = ServiceState.ERROR
            self.logger.error("Error inicializando servicio", exception=e)
            raise
    
    @abstractmethod
    def _perform_initialization(self):
        """Inicialización específica del servicio. Debe ser implementada por subclases."""
        pass
    
    def _setup_validations(self):
        """Configura validaciones del servicio. Puede ser sobrescrita."""
        pass
    
    def _setup_event_handlers(self):
        """Configura manejadores de eventos. Puede ser sobrescrita."""
        pass
    
    def shutdown(self):
        """Cierra el servicio ordenadamente."""
        if self.state == ServiceState.SHUTDOWN:
            return
        
        self.state = ServiceState.SHUTTING_DOWN
        self.logger.info("Cerrando servicio")
        
        try:
            # Cancelar tareas async
            self._cancel_async_tasks()
            
            # Ejecutar callbacks de limpieza
            for callback in self._cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    self.logger.warning(f"Error en callback de limpieza: {str(e)}")
            
            # Limpiar recursos
            self._cleanup_resources()
            
            # Shutdown específico del servicio
            self._perform_shutdown()
            
            self.state = ServiceState.SHUTDOWN
            self.logger.info("Servicio cerrado correctamente")
            
        except Exception as e:
            self.logger.error("Error cerrando servicio", exception=e)
            self.state = ServiceState.ERROR
            raise
    
    def _perform_shutdown(self):
        """Shutdown específico del servicio. Puede ser sobrescrita."""
        pass
    
    # Health check methods
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Verifica el estado de salud del servicio.
        Debe ser implementado por cada servicio específico.
        """
        pass
    
    def _check_dependencies(self):
        """Verifica que las dependencias estén disponibles."""
        for dep_name in self.dependencies:
            try:
                from . import get_service
                dep_service = get_service(dep_name)
                if dep_service.state not in [ServiceState.READY, ServiceState.RUNNING]:
                    raise Exception(f"Dependencia {dep_name} no está lista")
            except Exception as e:
                raise Exception(f"Error verificando dependencia {dep_name}: {str(e)}")
    
    # Context management
    
    @contextmanager
    def service_context(self, correlation_id: str = None, user_id: str = None):
        """Context manager para operaciones del servicio."""
        original_context = self._context
        
        # Crear nuevo contexto si se especifican parámetros
        if correlation_id or user_id:
            self._context = ServiceContext(self.name)
            if correlation_id:
                self._context.correlation_id = correlation_id
            if user_id:
                self._context.user_id = user_id
        
        try:
            yield self._context
        finally:
            self._context = original_context
    
    @asynccontextmanager
    async def async_service_context(self, correlation_id: str = None, user_id: str = None):
        """Context manager asíncrono para operaciones del servicio."""
        with self.service_context(correlation_id, user_id) as ctx:
            yield ctx
    
    # Transaction management
    
    @contextmanager
    def transaction(self, auto_commit: bool = True, auto_rollback: bool = True):
        """Context manager para transacciones de base de datos."""
        if not self.config.database_transactions:
            yield None
            return
        
        from app.extensions import db
        
        try:
            # Usar sesión existente o crear nueva
            if self._context.db_session:
                session = self._context.db_session
            else:
                session = db.session
                self._context.db_session = session
            
            yield session
            
            if auto_commit:
                session.commit()
                self.logger.debug("Transacción confirmada")
                
        except Exception as e:
            if auto_rollback:
                session.rollback()
                self.logger.warning(f"Transacción revertida: {str(e)}")
            raise
    
    # Event system
    
    def on(self, event_type: str, handler: Callable):
        """Registra un manejador de eventos."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def off(self, event_type: str, handler: Callable):
        """Desregistra un manejador de eventos."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _emit_event(self, event_type: str, data: Dict[str, Any] = None):
        """Emite un evento."""
        if not self.config.event_publishing:
            return
        
        # Añadir evento al contexto
        self._context.add_event(event_type, data)
        
        # Ejecutar handlers locales
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Handler asíncrono
                    task = asyncio.create_task(handler(data))
                    self._async_tasks.append(task)
                else:
                    # Handler síncrono
                    handler(data)
            except Exception as e:
                self.logger.error(f"Error en handler de evento {event_type}", exception=e)
    
    # Caching methods
    
    def cached(self, ttl: int = None, invalidate_on: List[str] = None):
        """
        Decorador para cache automático de métodos.
        
        Args:
            ttl: Time to live en segundos
            invalidate_on: Lista de eventos que invalidan el cache
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if self.config.cache_strategy == CacheStrategy.NONE:
                    return func(*args, **kwargs)
                
                # Intentar obtener del cache
                cached_result = self.cache.get(self.name, func.__name__, *args, **kwargs)
                if cached_result is not None:
                    self.logger.trace(f"Cache hit para {func.__name__}")
                    return cached_result
                
                # Ejecutar función y guardar en cache
                result = func(*args, **kwargs)
                self.cache.set(self.name, func.__name__, result, *args, **kwargs)
                self.logger.trace(f"Cache miss para {func.__name__}, resultado guardado")
                
                return result
            
            # Configurar invalidación automática
            if invalidate_on:
                for event_type in invalidate_on:
                    self.on(event_type, lambda data: self.cache.invalidate(self.name, func.__name__))
            
            return wrapper
        return decorator
    
    def invalidate_cache(self, method_name: str = None):
        """Invalida cache del servicio o método específico."""
        self.cache.invalidate(self.name, method_name)
        self.logger.debug(f"Cache invalidado para {method_name or 'todo el servicio'}")
    
    # Validation methods
    
    def validate(self, data: Dict[str, Any], rules: ServiceValidator = None) -> Tuple[bool, List[str]]:
        """Valida datos usando reglas del servicio."""
        validator = rules or self.validator
        return validator.validate(data)
    
    def require_valid(self, data: Dict[str, Any], rules: ServiceValidator = None):
        """Requiere que los datos sean válidos, lanza excepción si no."""
        is_valid, errors = self.validate(data, rules)
        if not is_valid:
            raise ValueError(f"Validation failed: {', '.join(errors)}")
    
    # Async support
    
    async def async_execute(self, coro):
        """Ejecuta corrutina con manejo de errores."""
        try:
            task = asyncio.create_task(coro)
            self._async_tasks.append(task)
            return await task
        except Exception as e:
            self.logger.error("Error en ejecución asíncrona", exception=e)
            raise
    
    def _cancel_async_tasks(self):
        """Cancela todas las tareas asíncronas pendientes."""
        for task in self._async_tasks:
            if not task.done():
                task.cancel()
        self._async_tasks.clear()
    
    # Resource management
    
    def add_resource(self, name: str, resource: Any, cleanup_callback: Callable = None):
        """Añade un recurso gestionado."""
        self._resources[name] = resource
        if cleanup_callback:
            self._cleanup_callbacks.append(cleanup_callback)
    
    def get_resource(self, name: str) -> Any:
        """Obtiene un recurso gestionado."""
        return self._resources.get(name)
    
    def _cleanup_resources(self):
        """Limpia todos los recursos gestionados."""
        for name, resource in self._resources.items():
            try:
                if hasattr(resource, 'close'):
                    resource.close()
                elif hasattr(resource, 'cleanup'):
                    resource.cleanup()
            except Exception as e:
                self.logger.warning(f"Error limpiando recurso {name}: {str(e)}")
        
        self._resources.clear()
    
    # Monitoring and metrics
    
    def track_method(self, func: Callable = None, track_args: bool = False):
        """Decorador para tracking automático de métodos."""
        def decorator(method):
            @wraps(method)
            def wrapper(*args, **kwargs):
                method_name = method.__name__
                start_time = time.time()
                
                self.state = ServiceState.RUNNING
                self.logger.trace(f"Ejecutando {method_name}")
                
                try:
                    result = method(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Registrar métricas
                    self.metrics.record_call(method_name, execution_time, True)
                    
                    self.logger.trace(f"Completado {method_name} en {execution_time:.3f}s")
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    error_type = type(e).__name__
                    
                    # Registrar métricas de error
                    self.metrics.record_call(method_name, execution_time, False, error_type)
                    
                    self.logger.error(f"Error en {method_name}", exception=e)
                    raise
                finally:
                    if self.state == ServiceState.RUNNING:
                        self.state = ServiceState.READY
            
            return wrapper
        
        if func is None:
            return decorator
        else:
            return decorator(func)
    
    # Testing utilities
    
    def create_test_context(self, user_id: str = "test_user", correlation_id: str = None):
        """Crea contexto para testing."""
        test_context = ServiceContext(self.name)
        test_context.user_id = user_id
        test_context.correlation_id = correlation_id or f"test_{uuid.uuid4()}"
        return test_context
    
    def reset_for_testing(self):
        """Resetea el servicio para testing."""
        self.metrics = ServiceMetrics(self.name)
        self.cache = ServiceCache(CacheStrategy.MEMORY, 60)
        self._context = ServiceContext(self.name)
        self.state = ServiceState.UNINITIALIZED
    
    # Properties
    
    @property
    def is_healthy(self) -> bool:
        """Indica si el servicio está saludable."""
        return self.state in [ServiceState.READY, ServiceState.RUNNING]
    
    @property
    def uptime(self) -> timedelta:
        """Tiempo que lleva el servicio ejecutándose."""
        return datetime.utcnow() - self._context.start_time
    
    # Class methods
    
    @classmethod
    def get_all_instances(cls) -> List['BaseService']:
        """Obtiene todas las instancias activas de servicios."""
        return list(cls._instances.values())
    
    @classmethod
    def set_global_config(cls, config: Dict[str, Any]):
        """Establece configuración global para todos los servicios."""
        cls._global_config.update(config)
    
    # String representation
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}', state={self.state.value})>"
    
    def __str__(self):
        return f"{self.name} Service ({self.state.value})"


# Utility functions para servicios

def service_method(*args, **kwargs):
    """Decorador que combina tracking y cache para métodos de servicio."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *method_args, **method_kwargs):
            if not isinstance(self, BaseService):
                raise TypeError("@service_method solo puede usarse en BaseService")
            
            # Aplicar tracking
            tracked_func = self.track_method(func)
            
            # Aplicar cache si está configurado
            cache_ttl = kwargs.get('cache_ttl')
            if cache_ttl and self.config.cache_strategy != CacheStrategy.NONE:
                cached_func = self.cached(ttl=cache_ttl)(tracked_func)
                return cached_func(*method_args, **method_kwargs)
            else:
                return tracked_func(*method_args, **method_kwargs)
        
        return wrapper
    
    # Permitir uso con y sin parámetros
    if len(args) == 1 and callable(args[0]):
        return decorator(args[0])
    else:
        return decorator


def async_service_method(**kwargs):
    """Decorador para métodos asíncronos de servicio."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **method_kwargs):
            if not isinstance(self, BaseService):
                raise TypeError("@async_service_method solo puede usarse en BaseService")
            
            method_name = func.__name__
            start_time = time.time()
            
            self.state = ServiceState.RUNNING
            self.logger.trace(f"Ejecutando async {method_name}")
            
            try:
                result = await func(self, *args, **method_kwargs)
                execution_time = time.time() - start_time
                
                self.metrics.record_call(method_name, execution_time, True)
                self.logger.trace(f"Completado async {method_name} en {execution_time:.3f}s")
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_type = type(e).__name__
                
                self.metrics.record_call(method_name, execution_time, False, error_type)
                self.logger.error(f"Error en async {method_name}", exception=e)
                raise
            finally:
                if self.state == ServiceState.RUNNING:
                    self.state = ServiceState.READY
        
        return wrapper
    return decorator


# Export principales
__all__ = [
    'BaseService',
    'ServiceState',
    'ServiceConfiguration',
    'ServiceValidator',
    'ServiceCache',
    'ServiceLogger',
    'ServiceMetrics',
    'ServiceContext',
    'ServiceEvent',
    'LogLevel',
    'CacheStrategy',
    'service_method',
    'async_service_method'
]