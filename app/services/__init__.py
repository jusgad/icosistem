"""
Módulo de servicios del ecosistema de emprendimiento.

Este módulo implementa la capa de lógica de negocio utilizando patrones de diseño
empresariales como Service Layer, Dependency Injection, Factory Pattern y Registry.

Características principales:
- Service Registry centralizado para gestión de servicios
- Dependency Injection automático
- Base Service class con funcionalidades comunes
- Health checks automáticos de servicios
- Métricas y monitoring integrado
- Caching inteligente para servicios
- Rate limiting configurable
- Circuit breaker para servicios externos
- Async/await support para operaciones pesadas
- Transactional decorators para consistencia de datos

Servicios disponibles:
- Analytics: Business Intelligence y métricas
- ML: Machine Learning y predicciones  
- Notification: Notificaciones multi-canal
- Email: Gestión de correos electrónicos
- User: Gestión de usuarios y autenticación
- Entrepreneur: Lógica específica de emprendedores
- Project: Gestión de proyectos y workflow
- Mentorship: Sistema de mentoría
- FileStorage: Almacenamiento de archivos
- Integration: Hub de integraciones externas
- Currency: Conversión de monedas
- SMS: Servicios de mensajería de texto

Autor: Sistema de Emprendimiento
Versión: 2.0
"""

import asyncio
import logging
import threading
import time
import traceback
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps, lru_cache
from typing import Any, Optional, Callable, Type, Union
from weakref import WeakValueDictionary

from flask import current_app, g, request
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

# Configurar logger específico para servicios
logger = logging.getLogger(__name__)

# Registry global de servicios
_service_registry: dict[str, Any] = {}
_service_instances: WeakValueDictionary = WeakValueDictionary()
_service_health_status: dict[str, Dict] = {}
_service_metrics: dict[str, Dict] = {}

# Configuraciones globales del módulo de servicios
SERVICES_CONFIG = {
    'AUTO_REGISTER': True,
    'HEALTH_CHECK_INTERVAL': 300,  # 5 minutos
    'METRICS_COLLECTION': True,
    'CIRCUIT_BREAKER_ENABLED': True,
    'DEFAULT_TIMEOUT': 30,  # segundos
    'RETRY_ATTEMPTS': 3,
    'CACHE_DEFAULT_TTL': 300,  # 5 minutos
    'RATE_LIMIT_DEFAULT': '1000 per hour'
}

# Excepciones específicas de servicios
class ServiceError(Exception):
    """Excepción base para errores de servicios."""
    
    def __init__(self, message: str, service_name: str = None, error_code: str = None):
        self.message = message
        self.service_name = service_name
        self.error_code = error_code
        super().__init__(self.message)


class ServiceNotFoundError(ServiceError):
    """Excepción cuando un servicio no se encuentra registrado."""
    pass


class ServiceTimeoutError(ServiceError):
    """Excepción cuando un servicio excede el tiempo límite."""
    pass


class ServiceCircuitBreakerError(ServiceError):
    """Excepción cuando el circuit breaker está abierto."""
    pass


class ServiceDependencyError(ServiceError):
    """Excepción cuando una dependencia de servicio falla."""
    pass


@dataclass
class ServiceMetrics:
    """Métricas de un servicio."""
    name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    last_called: Optional[datetime] = None
    last_error: Optional[str] = None
    circuit_breaker_state: str = 'closed'  # closed, open, half_open


@dataclass 
class ServiceHealth:
    """Estado de salud de un servicio."""
    name: str
    status: str = 'healthy'  # healthy, degraded, unhealthy
    last_check: Optional[datetime] = None
    message: str = ''
    dependencies_status: dict[str, str] = field(default_factory=dict)
    response_time: Optional[float] = None


class CircuitBreaker:
    """Implementación de Circuit Breaker para servicios."""
    
    def __init__(self, name: str, failure_threshold: int = 5, timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """Ejecuta función con circuit breaker."""
        with self._lock:
            if self.state == 'open':
                if self._should_attempt_reset():
                    self.state = 'half_open'
                else:
                    raise ServiceCircuitBreakerError(
                        f"Circuit breaker abierto para {self.name}", 
                        service_name=self.name
                    )
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """Verifica si debe intentar resetear el circuit breaker."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.timeout
    
    def _on_success(self):
        """Maneja éxito en la ejecución."""
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self):
        """Maneja fallo en la ejecución."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'


class BaseService(ABC):
    """
    Clase base para todos los servicios del sistema.
    
    Proporciona funcionalidades comunes como logging, métricas,
    manejo de errores, caching y health checks.
    """
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"services.{self.name}")
        self.metrics = ServiceMetrics(name=self.name)
        self.health = ServiceHealth(name=self.name)
        self.circuit_breaker = CircuitBreaker(self.name)
        self.dependencies: list[str] = []
        self._initialized = False
        
        # Auto-registrar servicio si está habilitado
        if SERVICES_CONFIG['AUTO_REGISTER']:
            register_service(self.name, self)
    
    def initialize(self):
        """Inicializa el servicio. Sobrescribir en servicios específicos."""
        if self._initialized:
            return
        
        self.logger.info(f"Inicializando servicio {self.name}")
        self._perform_initialization()
        self._initialized = True
        self.logger.info(f"Servicio {self.name} inicializado correctamente")
    
    def _perform_initialization(self):
        """Lógica específica de inicialización. Sobrescribir si es necesario."""
        pass
    
    @abstractmethod
    def health_check(self) -> ServiceHealth:
        """
        Verifica el estado de salud del servicio.
        Debe ser implementado por cada servicio específico.
        """
        pass
    
    def get_metrics(self) -> ServiceMetrics:
        """Obtiene métricas del servicio."""
        return self.metrics
    
    def reset_metrics(self):
        """Resetea las métricas del servicio."""
        self.metrics = ServiceMetrics(name=self.name)
    
    def add_dependency(self, service_name: str):
        """Añade una dependencia de servicio."""
        if service_name not in self.dependencies:
            self.dependencies.append(service_name)
    
    def check_dependencies(self) -> dict[str, str]:
        """Verifica el estado de las dependencias."""
        dependencies_status = {}
        
        for dep_name in self.dependencies:
            try:
                dep_service = get_service(dep_name)
                dep_health = dep_service.health_check()
                dependencies_status[dep_name] = dep_health.status
            except Exception as e:
                dependencies_status[dep_name] = 'unhealthy'
                self.logger.error(f"Error verificando dependencia {dep_name}: {str(e)}")
        
        return dependencies_status
    
    def __enter__(self):
        """Context manager para manejo de recursos."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Limpieza de recursos."""
        if exc_type:
            self.logger.error(f"Error en servicio {self.name}: {exc_val}")
        return False


def service_method(timeout: int = None, retry_attempts: int = None, 
                  cache_ttl: int = None, rate_limit: str = None):
    """
    Decorador para métodos de servicios con funcionalidades avanzadas.
    
    Args:
        timeout: Tiempo límite en segundos
        retry_attempts: Número de intentos de reintento
        cache_ttl: Tiempo de vida del cache en segundos
        rate_limit: Límite de tasa (ej: "100 per hour")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, BaseService):
                raise ServiceError("Decorador solo puede ser usado en BaseService")
            
            method_name = f"{self.name}.{func.__name__}"
            start_time = time.time()
            
            try:
                # Verificar rate limiting
                if rate_limit:
                    _check_rate_limit(self.name, method_name, rate_limit)
                
                # Verificar cache
                cache_key = None
                if cache_ttl:
                    cache_key = _generate_cache_key(method_name, args, kwargs)
                    cached_result = _get_from_cache(cache_key)
                    if cached_result is not None:
                        return cached_result
                
                # Ejecutar con circuit breaker
                if SERVICES_CONFIG['CIRCUIT_BREAKER_ENABLED']:
                    result = self.circuit_breaker.call(func, self, *args, **kwargs)
                else:
                    result = func(self, *args, **kwargs)
                
                # Guardar en cache
                if cache_ttl and cache_key:
                    _save_to_cache(cache_key, result, cache_ttl)
                
                # Actualizar métricas
                execution_time = time.time() - start_time
                _update_service_metrics(self, method_name, execution_time, success=True)
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                _update_service_metrics(self, method_name, execution_time, success=False, error=str(e))
                
                # Reintento si está configurado
                if retry_attempts and hasattr(self, '_retry_count'):
                    if self._retry_count < retry_attempts:
                        self._retry_count += 1
                        self.logger.warning(f"Reintentando {method_name}, intento {self._retry_count}")
                        return wrapper(self, *args, **kwargs)
                
                self.logger.error(f"Error en {method_name}: {str(e)}")
                raise ServiceError(f"Error en {method_name}: {str(e)}", service_name=self.name)
        
        return wrapper
    return decorator


def transactional(rollback_on_error: bool = True):
    """
    Decorador para métodos que requieren transacciones de base de datos.
    
    Args:
        rollback_on_error: Si debe hacer rollback automático en caso de error
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from app.extensions import db
            
            try:
                result = func(*args, **kwargs)
                db.session.commit()
                return result
            except Exception as e:
                if rollback_on_error:
                    db.session.rollback()
                    logger.error(f"Rollback ejecutado para {func.__name__}: {str(e)}")
                raise
        
        return wrapper
    return decorator


def async_service_method(timeout: int = None):
    """Decorador para métodos asíncronos de servicios."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not isinstance(self, BaseService):
                raise ServiceError("Decorador solo puede ser usado en BaseService")
            
            start_time = time.time()
            method_name = f"{self.name}.{func.__name__}"
            
            try:
                if timeout:
                    result = await asyncio.wait_for(func(self, *args, **kwargs), timeout=timeout)
                else:
                    result = await func(self, *args, **kwargs)
                
                execution_time = time.time() - start_time
                _update_service_metrics(self, method_name, execution_time, success=True)
                
                return result
                
            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                _update_service_metrics(self, method_name, execution_time, success=False, error="Timeout")
                raise ServiceTimeoutError(f"Timeout en {method_name}", service_name=self.name)
            except Exception as e:
                execution_time = time.time() - start_time
                _update_service_metrics(self, method_name, execution_time, success=False, error=str(e))
                raise ServiceError(f"Error en {method_name}: {str(e)}", service_name=self.name)
        
        return wrapper
    return decorator


class ServiceRegistry:
    """Registry centralizado para gestión de servicios."""
    
    def __init__(self):
        self._services: dict[str, BaseService] = {}
        self._factories: dict[str, Callable] = {}
        self._singletons: dict[str, BaseService] = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, service: Union[BaseService, Callable], singleton: bool = True):
        """
        Registra un servicio en el registry.
        
        Args:
            name: Nombre del servicio
            service: Instancia del servicio o factory function
            singleton: Si debe ser singleton
        """
        with self._lock:
            if isinstance(service, BaseService):
                self._services[name] = service
                if singleton:
                    self._singletons[name] = service
            elif callable(service):
                self._factories[name] = service
            else:
                raise ValueError(f"Servicio {name} debe ser BaseService o callable")
            
            logger.info(f"Servicio {name} registrado exitosamente")
    
    def get(self, name: str) -> BaseService:
        """Obtiene un servicio del registry."""
        with self._lock:
            # Verificar si es singleton ya instanciado
            if name in self._singletons:
                return self._singletons[name]
            
            # Verificar si está registrado directamente
            if name in self._services:
                service = self._services[name]
                if not service._initialized:
                    service.initialize()
                return service
            
            # Intentar crear desde factory
            if name in self._factories:
                factory = self._factories[name]
                service = factory()
                if isinstance(service, BaseService):
                    if not service._initialized:
                        service.initialize()
                    self._singletons[name] = service
                    return service
                else:
                    raise ServiceError(f"Factory para {name} debe retornar BaseService")
            
            raise ServiceNotFoundError(f"Servicio {name} no encontrado", service_name=name)
    
    def unregister(self, name: str):
        """Desregistra un servicio."""
        with self._lock:
            self._services.pop(name, None)
            self._factories.pop(name, None)
            self._singletons.pop(name, None)
            logger.info(f"Servicio {name} desregistrado")
    
    def list_services(self) -> list[str]:
        """Lista todos los servicios registrados."""
        with self._lock:
            return list(set(list(self._services.keys()) + list(self._factories.keys())))
    
    def health_check_all(self) -> dict[str, ServiceHealth]:
        """Ejecuta health check en todos los servicios."""
        health_results = {}
        
        for service_name in self.list_services():
            try:
                service = self.get(service_name)
                health_results[service_name] = service.health_check()
            except Exception as e:
                health_results[service_name] = ServiceHealth(
                    name=service_name,
                    status='unhealthy',
                    message=str(e),
                    last_check=datetime.now(timezone.utc)
                )
        
        return health_results


# Instancia global del registry
service_registry = ServiceRegistry()


def register_service(name: str, service: Union[BaseService, Callable], singleton: bool = True):
    """Función helper para registrar servicios."""
    service_registry.register(name, service, singleton)


def get_service(name: str) -> BaseService:
    """Función helper para obtener servicios."""
    return service_registry.get(name)


def inject_service(service_name: str):
    """
    Decorador para inyección de dependencias de servicios.
    
    Args:
        service_name: Nombre del servicio a inyectar
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            service = get_service(service_name)
            return func(service, *args, **kwargs)
        return wrapper
    return decorator


@contextmanager
def service_context(*service_names):
    """
    Context manager para trabajar con múltiples servicios.
    
    Args:
        service_names: Nombres de servicios a inicializar
    """
    services = {}
    try:
        for name in service_names:
            services[name] = get_service(name)
        yield services
    except Exception as e:
        logger.error(f"Error en context de servicios: {str(e)}")
        raise
    finally:
        # Cleanup si es necesario
        for service in services.values():
            if hasattr(service, 'cleanup'):
                try:
                    service.cleanup()
                except Exception as e:
                    logger.warning(f"Error en cleanup de {service.name}: {str(e)}")


def get_all_service_metrics() -> dict[str, ServiceMetrics]:
    """Obtiene métricas de todos los servicios."""
    metrics = {}
    for service_name in service_registry.list_services():
        try:
            service = get_service(service_name)
            metrics[service_name] = service.get_metrics()
        except Exception as e:
            logger.error(f"Error obteniendo métricas de {service_name}: {str(e)}")
    
    return metrics


def health_check_all_services() -> dict[str, ServiceHealth]:
    """Ejecuta health check en todos los servicios."""
    return service_registry.health_check_all()


def initialize_all_services():
    """Inicializa todos los servicios registrados."""
    logger.info("Inicializando todos los servicios...")
    
    for service_name in service_registry.list_services():
        try:
            service = get_service(service_name)
            if not service._initialized:
                service.initialize()
        except Exception as e:
            logger.error(f"Error inicializando servicio {service_name}: {str(e)}")
    
    logger.info("Inicialización de servicios completada")


# Funciones auxiliares privadas

def _check_rate_limit(service_name: str, method_name: str, rate_limit: str):
    """Verifica rate limiting para un método de servicio."""
    # Implementación simplificada - en producción usaría Redis
    # Por ahora solo loggea
    logger.debug(f"Rate limit check para {service_name}.{method_name}: {rate_limit}")


def _generate_cache_key(method_name: str, args: tuple, kwargs: dict) -> str:
    """Genera clave de cache para un método."""
    import hashlib
    
    # Crear hash de argumentos
    args_str = str(args) + str(sorted(kwargs.items()))
    args_hash = hashlib.md5(args_str.encode()).hexdigest()
    
    return f"service_cache:{method_name}:{args_hash}"


def _get_from_cache(cache_key: str):
    """Obtiene valor del cache."""
    try:
        from app.extensions import cache
        return cache.get(cache_key)
    except Exception as e:
        logger.warning(f"Error obteniendo cache {cache_key}: {str(e)}")
        return None


def _save_to_cache(cache_key: str, value: Any, ttl: int):
    """Guarda valor en cache."""
    try:
        from app.extensions import cache
        cache.set(cache_key, value, timeout=ttl)
    except Exception as e:
        logger.warning(f"Error guardando cache {cache_key}: {str(e)}")


def _update_service_metrics(service: BaseService, method_name: str, 
                          execution_time: float, success: bool, error: str = None):
    """Actualiza métricas de un servicio."""
    if not SERVICES_CONFIG['METRICS_COLLECTION']:
        return
    
    service.metrics.call_count += 1
    service.metrics.total_execution_time += execution_time
    service.metrics.avg_execution_time = (
        service.metrics.total_execution_time / service.metrics.call_count
    )
    service.metrics.last_called = datetime.now(timezone.utc)
    
    if success:
        service.metrics.success_count += 1
    else:
        service.metrics.error_count += 1
        service.metrics.last_error = error
    
    # Actualizar circuit breaker state
    service.metrics.circuit_breaker_state = service.circuit_breaker.state


# Auto-importar y registrar servicios principales

def _auto_import_services():
    """Auto-importa y registra servicios principales."""
    try:
        # Importar servicios principales
        from .analytics_service import AnalyticsService
        from .notification_service import NotificationService
        from .email import EmailService
        from .user_service import UserService
        from .entrepreneur_service import EntrepreneurService
        from .project_service import ProjectService
        from .mentorship_service import MentorshipService
        from .file_storage import FileStorageService
        from .integration_hub import IntegrationHubService
        
        # Registrar servicios como factories para lazy loading
        register_service('analytics', lambda: AnalyticsService())
        register_service('notification', lambda: NotificationService())
        register_service('email', lambda: EmailService())
        register_service('user', lambda: UserService())
        register_service('entrepreneur', lambda: EntrepreneurService())
        register_service('project', lambda: ProjectService())
        register_service('mentorship', lambda: MentorshipService())
        register_service('file_storage', lambda: FileStorageService())
        register_service('integration', lambda: IntegrationHubService())
        
        logger.info("Servicios principales registrados exitosamente")
        
    except ImportError as e:
        logger.warning(f"No se pudieron importar algunos servicios: {str(e)}")
    except Exception as e:
        logger.error(f"Error en auto-importación de servicios: {str(e)}")


def _setup_service_monitoring():
    """Configura monitoring automático de servicios."""
    if not SERVICES_CONFIG['HEALTH_CHECK_INTERVAL']:
        return
    
    def _periodic_health_check():
        """Ejecuta health checks periódicos."""
        while True:
            try:
                health_results = health_check_all_services()
                
                # Log servicios con problemas
                for name, health in health_results.items():
                    if health.status != 'healthy':
                        logger.warning(f"Servicio {name} no saludable: {health.message}")
                
                # Actualizar status global
                global _service_health_status
                _service_health_status.update({
                    name: {
                        'status': health.status,
                        'last_check': health.last_check.isoformat() if health.last_check else None,
                        'message': health.message
                    }
                    for name, health in health_results.items()
                })
                
            except Exception as e:
                logger.error(f"Error en health check periódico: {str(e)}")
            
            time.sleep(SERVICES_CONFIG['HEALTH_CHECK_INTERVAL'])
    
    # Ejecutar en thread separado
    import threading
    health_thread = threading.Thread(target=_periodic_health_check, daemon=True)
    health_thread.start()
    
    logger.info("Monitoring de servicios configurado")


# Funciones para Flask integration

def init_services(app):
    """Inicializa servicios con Flask app."""
    logger.info("Configurando servicios con Flask app...")
    
    # Configurar logging
    if app.config.get('SERVICES_LOG_LEVEL'):
        logging.getLogger('services').setLevel(app.config['SERVICES_LOG_LEVEL'])
    
    # Actualizar configuración
    services_config = app.config.get('SERVICES_CONFIG', {})
    SERVICES_CONFIG.update(services_config)
    
    # Auto-importar servicios
    _auto_import_services()
    
    # Configurar monitoring si está habilitado
    if app.config.get('SERVICES_MONITORING_ENABLED', True):
        _setup_service_monitoring()
    
    # Hook para cleanup
    @app.teardown_appcontext
    def cleanup_services(error):
        """Limpia recursos de servicios al final del request."""
        if hasattr(g, 'services_in_use'):
            for service in g.services_in_use:
                if hasattr(service, 'cleanup'):
                    try:
                        service.cleanup()
                    except Exception as e:
                        logger.warning(f"Error en cleanup de servicio: {str(e)}")
    
    logger.info("Servicios configurados exitosamente con Flask")


def get_services_status():
    """Obtiene estado general de todos los servicios."""
    try:
        health_status = health_check_all_services()
        metrics = get_all_service_metrics()
        
        return {
            'status': 'healthy' if all(h.status == 'healthy' for h in health_status.values()) else 'degraded',
            'services_count': len(service_registry.list_services()),
            'health_status': {name: health.status for name, health in health_status.items()},
            'metrics_summary': {
                name: {
                    'call_count': m.call_count,
                    'success_rate': (m.success_count / m.call_count * 100) if m.call_count > 0 else 0,
                    'avg_execution_time': m.avg_execution_time
                }
                for name, m in metrics.items()
            },
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error obteniendo status de servicios: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }


# Exportar componentes principales
__all__ = [
    # Clases base
    'BaseService',
    'ServiceRegistry',
    'ServiceMetrics',
    'ServiceHealth',
    'CircuitBreaker',
    
    # Excepciones
    'ServiceError',
    'ServiceNotFoundError', 
    'ServiceTimeoutError',
    'ServiceCircuitBreakerError',
    'ServiceDependencyError',
    
    # Decoradores
    'service_method',
    'transactional',
    'async_service_method',
    'inject_service',
    
    # Funciones principales
    'register_service',
    'get_service',
    'service_context',
    'initialize_all_services',
    'health_check_all_services',
    'get_all_service_metrics',
    'init_services',
    'get_services_status',
    
    # Registry global
    'service_registry',
    
    # Configuración
    'SERVICES_CONFIG'
]

# Logging de inicialización del módulo
logger.info(f"Módulo de servicios inicializado")
logger.info(f"Configuración: {SERVICES_CONFIG}")
logger.info(f"Auto-registro habilitado: {SERVICES_CONFIG['AUTO_REGISTER']}")