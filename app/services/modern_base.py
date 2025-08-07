"""
Clase base de servicio moderna para el ecosistema de emprendimiento.

Este módulo proporciona la infraestructura moderna para todos los servicios del sistema,
usando los patrones más recientes de Python, async/await, validación moderna y observabilidad.

Características:
- Arquitectura moderna async-first
- Integración de validación Pydantic
- Logging estructurado con Loguru
- Trazado OpenTelemetry
- Caché basado en Redis
- Patrón circuit breaker
- Inyección de dependencias
- Arquitectura orientada a eventos
- Verificaciones de salud y métricas
- Manejo de errores moderno
"""

import asyncio
import inspect
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any, Dict, List, Optional, Type, TypeVar, Generic,
    Callable, Union, Awaitable, AsyncGenerator
)
from uuid import UUID, uuid4

# Importaciones modernas
from pydantic import BaseModel, ValidationError, Field
from loguru import logger
import structlog
from prometheus_client import Counter, Histogram, Gauge
import redis.asyncio as redis

# OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Integración con Flask
from flask import current_app, g, has_request_context
from flask_login import current_user

# Importaciones locales
from app.schemas.common import BaseSchema, ErrorType, create_error_response
from app.extensions_modern import extensions

# Variables de tipo
T = TypeVar('T', bound=BaseModel)
ServiceT = TypeVar('ServiceT', bound='ModernBaseService')


class ServiceState(str, Enum):
    """Estados del ciclo de vida del servicio moderno."""
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


class OperationResult(BaseModel, Generic[T]):
    """Envoltorio genérico para resultados de operaciones."""
    
    success: bool = Field(description="Estado de éxito de la operación")
    data: Optional[T] = Field(default=None, description="Datos de la operación")
    error: Optional[str] = Field(default=None, description="Mensaje de error")
    error_code: Optional[str] = Field(default=None, description="Código de error")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")
    execution_time: Optional[float] = Field(default=None, description="Tiempo de ejecución en segundos")
    
    @classmethod
    def success_result(cls, data: T = None, metadata: Dict[str, Any] = None) -> 'OperationResult[T]':
        """Crear un resultado de operación exitoso."""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(
        cls, 
        error: str, 
        error_code: str = None,
        metadata: Dict[str, Any] = None
    ) -> 'OperationResult[T]':
        """Crear un resultado de operación con error."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata or {}
        )


class ServiceConfig(BaseModel):
    """Modern service configuration."""
    
    name: str = Field(description="Service name")
    enabled: bool = Field(default=True, description="Service enabled status")
    timeout_seconds: float = Field(default=30.0, description="Operation timeout")
    retry_attempts: int = Field(default=3, ge=0, description="Retry attempts")
    retry_delay: float = Field(default=1.0, ge=0, description="Retry delay in seconds")
    
    # Caching
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    cache_prefix: str = Field(default="service", description="Cache key prefix")
    
    # Circuit breaker
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_threshold: int = Field(default=5, ge=1, description="Failure threshold")
    circuit_breaker_timeout: int = Field(default=60, ge=1, description="Circuit breaker timeout")
    
    # Observability
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(default=True, description="Enable distributed tracing")
    structured_logging: bool = Field(default=True, description="Enable structured logging")
    
    # Database
    auto_commit: bool = Field(default=True, description="Auto commit database transactions")
    auto_rollback: bool = Field(default=True, description="Auto rollback on errors")
    
    # Additional configuration
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="Custom configuration")


class CircuitBreaker:
    """Modern circuit breaker implementation."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if self.last_failure_time:
                if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.timeout):
                    self.state = "half-open"
                    return True
            return False
        
        # half-open state
        return True
    
    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class ModernServiceContext:
    """Modern service execution context."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.correlation_id = str(uuid4())
        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.start_time = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        self.trace_id: Optional[str] = None
        
        # Auto-populate from Flask context
        self._populate_from_request_context()
    
    def _populate_from_request_context(self):
        """Populate context from Flask request."""
        if not has_request_context():
            return
        
        try:
            # Get user context
            if current_user and current_user.is_authenticated:
                self.user_id = str(current_user.id)
            
            # Get trace context from headers
            from flask import request
            self.correlation_id = request.headers.get('X-Correlation-ID', self.correlation_id)
            self.trace_id = request.headers.get('X-Trace-ID')
            
        except Exception:
            pass  # Ignore errors in context population
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'service_name': self.service_name,
            'correlation_id': self.correlation_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'trace_id': self.trace_id,
            'metadata': self.metadata
        }


class ModernBaseService(ABC):
    """
    Modern base class for all services in the entrepreneurship ecosystem.
    
    Features:
    - Async-first architecture
    - Modern validation with Pydantic
    - Structured logging and tracing
    - Built-in caching and circuit breaker
    - Health checks and metrics
    - Dependency injection ready
    """
    
    def __init__(self, config: ServiceConfig = None):
        self.config = config or ServiceConfig(name=self.__class__.__name__)
        self.state = ServiceState.INITIALIZING
        
        # Core components
        self._setup_logging()
        self._setup_metrics()
        self._setup_cache()
        self._setup_circuit_breaker()
        
        # Context and dependencies
        self.context = ModernServiceContext(self.config.name)
        self.dependencies: List[str] = []
        
        # Initialize service
        asyncio.create_task(self._initialize())
    
    def _setup_logging(self):
        """Setup structured logging."""
        self.logger = structlog.get_logger(self.config.name)
    
    def _setup_metrics(self):
        """Setup Prometheus metrics."""
        if not self.config.metrics_enabled:
            return
        
        service_name = self.config.name
        
        self.metrics = {
            'requests_total': Counter(
                f'{service_name}_requests_total',
                'Total service requests',
                ['method', 'status']
            ),
            'request_duration': Histogram(
                f'{service_name}_request_duration_seconds',
                'Request duration in seconds',
                ['method']
            ),
            'errors_total': Counter(
                f'{service_name}_errors_total',
                'Total service errors',
                ['method', 'error_type']
            ),
            'health_status': Gauge(
                f'{service_name}_health_status',
                'Service health status (1=healthy, 0=unhealthy)'
            )
        }
    
    def _setup_cache(self):
        """Setup Redis cache."""
        self.cache_enabled = self.config.cache_enabled
        self.redis_client: Optional[redis.Redis] = None
        
        if self.cache_enabled:
            try:
                redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                self.logger.warning("Failed to setup Redis cache", error=str(e))
                self.cache_enabled = False
    
    def _setup_circuit_breaker(self):
        """Setup circuit breaker."""
        if self.config.circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                timeout=self.config.circuit_breaker_timeout
            )
        else:
            self.circuit_breaker = None
    
    async def _initialize(self):
        """Initialize the service."""
        try:
            self.logger.info("Initializing service", service=self.config.name)
            
            # Check dependencies
            await self._check_dependencies()
            
            # Service-specific initialization
            await self._perform_initialization()
            
            # Health check
            health_result = await self.health_check()
            if not health_result.get('healthy', False):
                raise Exception("Service failed health check")
            
            self.state = ServiceState.HEALTHY
            self.logger.info("Service initialized successfully")
            
            # Update health metric
            if self.config.metrics_enabled:
                self.metrics['health_status'].set(1)
                
        except Exception as e:
            self.state = ServiceState.UNHEALTHY
            self.logger.error("Service initialization failed", error=str(e))
            
            if self.config.metrics_enabled:
                self.metrics['health_status'].set(0)
            
            raise
    
    @abstractmethod
    async def _perform_initialization(self):
        """Service-specific initialization. Must be implemented by subclasses."""
        pass
    
    async def _check_dependencies(self):
        """Check service dependencies."""
        for dep_name in self.dependencies:
            try:
                # Here you would check if dependent services are healthy
                # For now, we'll just log the dependency check
                self.logger.debug("Checking dependency", dependency=dep_name)
            except Exception as e:
                raise Exception(f"Dependency {dep_name} not available: {str(e)}")
    
    # Context Management
    
    @asynccontextmanager
    async def operation_context(
        self, 
        operation_name: str,
        user_id: str = None,
        correlation_id: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Async context manager for service operations."""
        
        # Create operation context
        op_context = ModernServiceContext(self.config.name)
        if user_id:
            op_context.user_id = user_id
        if correlation_id:
            op_context.correlation_id = correlation_id
        if metadata:
            op_context.metadata.update(metadata)
        
        # Setup tracing if available
        span = None
        tracer = None
        
        if TRACING_AVAILABLE and self.config.tracing_enabled:
            tracer = trace.get_tracer(__name__)
            span = tracer.start_span(
                f"{self.config.name}.{operation_name}",
                attributes={
                    'service.name': self.config.name,
                    'operation.name': operation_name,
                    'user.id': op_context.user_id or 'anonymous',
                    'correlation.id': op_context.correlation_id
                }
            )
        
        # Setup structured logging context
        with structlog.contextvars.bound_contextvars(
            service=self.config.name,
            operation=operation_name,
            correlation_id=op_context.correlation_id,
            user_id=op_context.user_id
        ):
            start_time = datetime.utcnow()
            
            try:
                self.logger.debug("Operation started", operation=operation_name)
                
                yield op_context
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Record success metrics
                if self.config.metrics_enabled:
                    self.metrics['requests_total'].labels(
                        method=operation_name, status='success'
                    ).inc()
                    self.metrics['request_duration'].labels(
                        method=operation_name
                    ).observe(execution_time)
                
                # Set span status
                if span:
                    span.set_status(Status(StatusCode.OK))
                
                self.logger.debug(
                    "Operation completed successfully",
                    operation=operation_name,
                    execution_time=execution_time
                )
                
            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                error_type = type(e).__name__
                
                # Record error metrics
                if self.config.metrics_enabled:
                    self.metrics['requests_total'].labels(
                        method=operation_name, status='error'
                    ).inc()
                    self.metrics['errors_total'].labels(
                        method=operation_name, error_type=error_type
                    ).inc()
                
                # Set span status
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                
                self.logger.error(
                    "Operation failed",
                    operation=operation_name,
                    error=str(e),
                    error_type=error_type,
                    execution_time=execution_time
                )
                
                # Record circuit breaker failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                
                raise
            
            finally:
                if span:
                    span.end()
    
    # Database Transaction Management
    
    @asynccontextmanager
    async def database_transaction(self, auto_commit: bool = None, auto_rollback: bool = None):
        """Async database transaction context manager."""
        
        auto_commit = auto_commit if auto_commit is not None else self.config.auto_commit
        auto_rollback = auto_rollback if auto_rollback is not None else self.config.auto_rollback
        
        # Use async database session
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.extensions_modern import db
        
        async with AsyncSession(db.engine) as session:
            try:
                yield session
                
                if auto_commit:
                    await session.commit()
                    self.logger.debug("Database transaction committed")
                
            except Exception as e:
                if auto_rollback:
                    await session.rollback()
                    self.logger.warning("Database transaction rolled back", error=str(e))
                raise
    
    # Caching Methods
    
    async def get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.cache_enabled or not self.redis_client:
            return None
        
        try:
            cache_key = f"{self.config.cache_prefix}:{self.config.name}:{key}"
            cached_value = await self.redis_client.get(cache_key)
            
            if cached_value:
                import json
                return json.loads(cached_value)
                
        except Exception as e:
            self.logger.warning("Cache get failed", key=key, error=str(e))
        
        return None
    
    async def set_cached(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache."""
        if not self.cache_enabled or not self.redis_client:
            return False
        
        try:
            import json
            cache_key = f"{self.config.cache_prefix}:{self.config.name}:{key}"
            ttl = ttl or self.config.cache_ttl
            
            serialized_value = json.dumps(value, default=str)
            await self.redis_client.setex(cache_key, ttl, serialized_value)
            
            return True
            
        except Exception as e:
            self.logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def invalidate_cache(self, pattern: str = None):
        """Invalidate cache entries."""
        if not self.cache_enabled or not self.redis_client:
            return
        
        try:
            if pattern:
                cache_pattern = f"{self.config.cache_prefix}:{self.config.name}:{pattern}"
            else:
                cache_pattern = f"{self.config.cache_prefix}:{self.config.name}:*"
            
            keys = await self.redis_client.keys(cache_pattern)
            if keys:
                await self.redis_client.delete(*keys)
                self.logger.debug("Cache invalidated", pattern=cache_pattern, keys_count=len(keys))
                
        except Exception as e:
            self.logger.warning("Cache invalidation failed", pattern=pattern, error=str(e))
    
    # Validation Methods
    
    def validate_input(self, data: Dict[str, Any], schema: Type[BaseModel]) -> BaseModel:
        """Validate input data using Pydantic schema."""
        try:
            return schema(**data)
        except ValidationError as e:
            self.logger.warning("Input validation failed", errors=e.errors())
            raise ValueError(f"Validation failed: {e}")
    
    async def validate_business_rules(self, data: Any) -> List[str]:
        """Validate business rules. Override in subclasses."""
        return []
    
    # Circuit Breaker Integration
    
    def can_execute_operation(self) -> bool:
        """Check if operation can be executed (circuit breaker)."""
        if not self.circuit_breaker:
            return True
        
        return self.circuit_breaker.can_execute()
    
    def record_success(self):
        """Record successful operation for circuit breaker."""
        if self.circuit_breaker:
            self.circuit_breaker.record_success()
    
    # Retry Logic
    
    async def execute_with_retry(
        self, 
        operation: Callable[[], Awaitable[T]], 
        max_attempts: int = None,
        delay: float = None
    ) -> T:
        """Execute operation with retry logic."""
        max_attempts = max_attempts or self.config.retry_attempts
        delay = delay or self.config.retry_delay
        
        last_exception = None
        
        for attempt in range(max_attempts + 1):
            try:
                if not self.can_execute_operation():
                    raise Exception("Circuit breaker is open")
                
                result = await operation()
                self.record_success()
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_attempts:
                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "Operation failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        "Operation failed after all retries",
                        attempts=max_attempts + 1,
                        error=str(e)
                    )
        
        raise last_exception
    
    # Health Check
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            # Basic health indicators
            health_info = {
                'service': self.config.name,
                'status': self.state.value,
                'healthy': self.state == ServiceState.HEALTHY,
                'timestamp': datetime.utcnow().isoformat(),
                'uptime_seconds': (datetime.utcnow() - self.context.start_time).total_seconds()
            }
            
            # Check dependencies
            dependencies_healthy = True
            for dep_name in self.dependencies:
                # Here you would actually check dependency health
                # For now, we assume they're healthy
                pass
            
            health_info['dependencies_healthy'] = dependencies_healthy
            
            # Check Redis cache if enabled
            if self.cache_enabled and self.redis_client:
                try:
                    await self.redis_client.ping()
                    health_info['cache_healthy'] = True
                except Exception:
                    health_info['cache_healthy'] = False
                    dependencies_healthy = False
            
            # Update overall health
            health_info['healthy'] = dependencies_healthy and self.state == ServiceState.HEALTHY
            
            # Service-specific health checks
            service_health = await self._perform_health_check()
            health_info.update(service_health)
            
            return health_info
            
        except Exception as e:
            return {
                'service': self.config.name,
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Service-specific health check. Override in subclasses."""
        return {'service_specific_checks': 'passed'}
    
    # Shutdown
    
    async def shutdown(self):
        """Shutdown the service gracefully."""
        self.state = ServiceState.SHUTTING_DOWN
        self.logger.info("Shutting down service")
        
        try:
            # Service-specific shutdown
            await self._perform_shutdown()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            self.state = ServiceState.SHUTDOWN
            self.logger.info("Service shutdown completed")
            
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))
            raise
    
    async def _perform_shutdown(self):
        """Service-specific shutdown. Override in subclasses."""
        pass
    
    # Utility Methods
    
    def create_operation_result(
        self, 
        data: T = None, 
        error: str = None,
        error_code: str = None,
        metadata: Dict[str, Any] = None
    ) -> OperationResult[T]:
        """Create an operation result."""
        if error:
            return OperationResult.error_result(error, error_code, metadata)
        return OperationResult.success_result(data, metadata)
    
    # Properties
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.state == ServiceState.HEALTHY
    
    @property 
    def uptime(self) -> timedelta:
        """Get service uptime."""
        return datetime.utcnow() - self.context.start_time


# Decorators for service methods

def service_operation(
    operation_name: str = None,
    cache_key: str = None,
    cache_ttl: int = None,
    validation_schema: Type[BaseModel] = None
):
    """Decorator for service operations with automatic instrumentation."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(self: ModernBaseService, *args, **kwargs):
            op_name = operation_name or func.__name__
            
            # Extract input data for validation
            input_data = kwargs.get('data') or (args[0] if args else {})
            
            # Validate input if schema provided
            if validation_schema and input_data:
                try:
                    validated_data = self.validate_input(input_data, validation_schema)
                    # Replace input data with validated data
                    if 'data' in kwargs:
                        kwargs['data'] = validated_data
                    elif args:
                        args = (validated_data,) + args[1:]
                except ValueError as e:
                    return self.create_operation_result(error=str(e), error_code="VALIDATION_ERROR")
            
            # Check cache if enabled
            if cache_key and self.cache_enabled:
                cache_result = await self.get_cached(cache_key)
                if cache_result:
                    return OperationResult.success_result(cache_result)
            
            # Execute with operation context
            async with self.operation_context(op_name) as context:
                try:
                    result = await func(self, *args, **kwargs)
                    
                    # Cache result if specified
                    if cache_key and self.cache_enabled and result.success:
                        await self.set_cached(cache_key, result.data, cache_ttl)
                    
                    return result
                    
                except Exception as e:
                    return self.create_operation_result(
                        error=str(e),
                        error_code=type(e).__name__
                    )
        
        return wrapper
    return decorator


def cached_operation(key_pattern: str, ttl: int = 300):
    """Decorator for caching operation results."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(self: ModernBaseService, *args, **kwargs):
            # Generate cache key
            import hashlib
            import json
            
            args_str = json.dumps(args, default=str, sort_keys=True)
            kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
            key_data = f"{key_pattern}:{args_str}:{kwargs_str}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = await self.get_cached(cache_key)
            if cached_result:
                return OperationResult.success_result(cached_result)
            
            # Execute function
            result = await func(self, *args, **kwargs)
            
            # Cache successful results
            if result.success:
                await self.set_cached(cache_key, result.data, ttl)
            
            return result
        
        return wrapper
    return decorator


# Export all classes and functions
__all__ = [
    'ModernBaseService',
    'ServiceState', 
    'OperationResult',
    'ServiceConfig',
    'ModernServiceContext',
    'CircuitBreaker',
    'service_operation',
    'cached_operation'
]