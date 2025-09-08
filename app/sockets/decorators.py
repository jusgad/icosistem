"""
Decoradores Especializados para WebSockets - Ecosistema de Emprendimiento
=========================================================================

Este módulo proporciona decoradores especializados para el sistema de WebSockets,
incluyendo autenticación, autorización, rate limiting, validación, logging,
métricas y funcionalidades específicas del ecosistema de emprendimiento.

Decoradores disponibles:
- Autenticación y autorización
- Rate limiting avanzado
- Validación de datos
- Logging y auditoría
- Métricas y monitoreo
- Cache y optimización
- Manejo de errores
- Funcionalidades específicas del dominio
"""

import logging
import time
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union, Callable
from functools import wraps, lru_cache
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from flask import request, current_app, g
from flask_socketio import emit, disconnect, rooms
from flask_jwt_extended import (
    verify_jwt_in_request, 
    get_jwt_identity, 
    decode_token,
    get_jwt
)
from sqlalchemy.exc import SQLAlchemyError
from marshmallow import ValidationError
from redis import Redis

from app.core.exceptions import (
    SocketAuthenticationError,
    SocketAuthorizationError,
    SocketRateLimitError,
    SocketValidationError,
    SocketPermissionError,
    SystemMaintenanceError
)
from app.core.permissions import has_permission, UserRole
from app.core.constants import (
    RATE_LIMIT_DEFAULTS,
    SOCKET_EVENTS,
    PERMISSION_LEVELS,
    MAINTENANCE_MODES
)
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.models.project import Project
from app.models.mentorship import MentorshipSession
from app.models.organization import Organization
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.utils.cache_utils import cache_get, cache_set, cache_delete
from app.utils.validators import validate_event_data, validate_user_input
from app.utils.formatters import format_datetime, format_user_info
from app.utils.string_utils import sanitize_input, generate_session_key

logger = logging.getLogger(__name__)

# Cache global para rate limiting y métricas
rate_limit_cache = defaultdict(lambda: defaultdict(deque))
metrics_cache = defaultdict(int)
auth_cache = {}
permission_cache = {}

# Configuración de rate limiting por evento
EVENT_RATE_LIMITS = {
    'message_send': {'rate': 30, 'window': 60, 'burst': 5},
    'document_edit': {'rate': 60, 'window': 60, 'burst': 10},
    'presence_update': {'rate': 10, 'window': 30, 'burst': 3},
    'notification_send': {'rate': 20, 'window': 60, 'burst': 5},
    'system_query': {'rate': 100, 'window': 60, 'burst': 20},
    'admin_action': {'rate': 10, 'window': 300, 'burst': 2},
    'broadcast': {'rate': 5, 'window': 300, 'burst': 1}
}


class PermissionLevel(Enum):
    """Niveles de permisos para decoradores"""
    PUBLIC = "public"
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    MENTOR = "mentor"
    ENTREPRENEUR = "entrepreneur"


@dataclass
class EventMetrics:
    """Métricas de eventos para monitoreo"""
    event_name: str
    call_count: int = 0
    error_count: int = 0
    total_time: float = 0.0
    last_called: Optional[datetime] = None
    average_time: float = 0.0


class RateLimitStrategy(Enum):
    """Estrategias de rate limiting"""
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"
    ADAPTIVE = "adaptive"


def socket_auth_required(
    allow_guest: bool = False,
    check_active: bool = True,
    cache_duration: int = 300
):
    """
    Decorador de autenticación para eventos WebSocket
    
    Args:
        allow_guest: Permitir usuarios invitados
        check_active: Verificar que el usuario esté activo
        cache_duration: Duración del cache de autenticación en segundos
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                session_id = request.sid
                
                # Verificar cache de autenticación
                cache_key = f"auth_{session_id}"
                cached_user = cache_get(cache_key)
                
                if cached_user:
                    user = User.query.get(cached_user['user_id'])
                    if user and (not check_active or user.is_active):
                        kwargs['current_user'] = user
                        return f(*args, **kwargs)
                
                # Verificar JWT
                try:
                    verify_jwt_in_request()
                    user_id = get_jwt_identity()
                except Exception:
                    if allow_guest:
                        kwargs['current_user'] = None
                        return f(*args, **kwargs)
                    else:
                        emit('auth_error', {
                            'code': 'AUTHENTICATION_REQUIRED',
                            'message': 'Authentication required'
                        })
                        disconnect()
                        return
                
                if not user_id:
                    if allow_guest:
                        kwargs['current_user'] = None
                        return f(*args, **kwargs)
                    else:
                        emit('auth_error', {
                            'code': 'INVALID_TOKEN',
                            'message': 'Invalid authentication token'
                        })
                        disconnect()
                        return
                
                # Obtener usuario de la base de datos
                user = User.query.get(user_id)
                if not user:
                    emit('auth_error', {
                        'code': 'USER_NOT_FOUND',
                        'message': 'User not found'
                    })
                    disconnect()
                    return
                
                if check_active and not user.is_active:
                    emit('auth_error', {
                        'code': 'USER_INACTIVE',
                        'message': 'User account is inactive'
                    })
                    disconnect()
                    return
                
                # Cachear información de autenticación
                cache_set(cache_key, {
                    'user_id': user.id,
                    'username': user.username,
                    'role': user.role.value
                }, timeout=cache_duration)
                
                # Actualizar última actividad
                user.last_activity = datetime.now(timezone.utc)
                
                kwargs['current_user'] = user
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error en autenticación WebSocket: {str(e)}")
                emit('auth_error', {
                    'code': 'AUTHENTICATION_ERROR',
                    'message': 'Authentication failed'
                })
                disconnect()
        
        decorated_function._requires_auth = True
        return decorated_function
    
    return decorator


def socket_permission_required(
    permission: Union[str, list[str]],
    permission_level: PermissionLevel = PermissionLevel.USER,
    resource_id_param: Optional[str] = None,
    check_ownership: bool = False
):
    """
    Decorador de autorización basado en permisos
    
    Args:
        permission: Permiso(s) requerido(s)
        permission_level: Nivel de permisos requerido
        resource_id_param: Parámetro que contiene el ID del recurso
        check_ownership: Verificar propiedad del recurso
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                current_user = kwargs.get('current_user')
                
                if not current_user:
                    emit('permission_error', {
                        'code': 'USER_NOT_AUTHENTICATED',
                        'message': 'User not authenticated'
                    })
                    return
                
                # Verificar nivel de permisos básico
                if not _check_permission_level(current_user, permission_level):
                    emit('permission_error', {
                        'code': 'INSUFFICIENT_PERMISSION_LEVEL',
                        'message': f'Requires {permission_level.value} level'
                    })
                    return
                
                # Verificar permisos específicos
                permissions_to_check = permission if isinstance(permission, list) else [permission]
                
                for perm in permissions_to_check:
                    cache_key = f"perm_{current_user.id}_{perm}"
                    has_perm = cache_get(cache_key)
                    
                    if has_perm is None:
                        has_perm = has_permission(current_user, perm)
                        cache_set(cache_key, has_perm, timeout=300)
                    
                    if not has_perm:
                        emit('permission_error', {
                            'code': 'INSUFFICIENT_PERMISSIONS',
                            'message': f'Missing permission: {perm}'
                        })
                        return
                
                # Verificar propiedad del recurso si se requiere
                if check_ownership and resource_id_param:
                    data = args[0] if args else {}
                    resource_id = data.get(resource_id_param)
                    
                    if resource_id and not _check_resource_ownership(current_user, resource_id, resource_id_param):
                        emit('permission_error', {
                            'code': 'RESOURCE_ACCESS_DENIED',
                            'message': 'Access denied to resource'
                        })
                        return
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error en verificación de permisos: {str(e)}")
                emit('permission_error', {
                    'code': 'PERMISSION_CHECK_ERROR',
                    'message': 'Permission check failed'
                })
        
        decorated_function._required_permissions = permission
        decorated_function._permission_level = permission_level
        return decorated_function
    
    return decorator


def socket_rate_limit(
    rate: Optional[int] = None,
    window: int = 60,
    per_user: bool = True,
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW,
    burst_allowance: Optional[int] = None,
    adaptive: bool = False
):
    """
    Rate limiting avanzado para eventos WebSocket
    
    Args:
        rate: Número máximo de eventos permitidos
        window: Ventana de tiempo en segundos
        per_user: Rate limiting por usuario vs global
        strategy: Estrategia de rate limiting
        burst_allowance: Ráfagas permitidas
        adaptive: Rate limiting adaptativo basado en carga
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                event_name = f.__name__
                current_user = kwargs.get('current_user')
                
                # Determinar rate limit
                effective_rate = rate or _get_default_rate_limit(event_name)
                
                # Ajustar rate limit adaptativamente si está habilitado
                if adaptive:
                    effective_rate = _calculate_adaptive_rate_limit(event_name, effective_rate)
                
                # Crear clave de rate limiting
                if per_user and current_user:
                    limit_key = f"rate_limit_{current_user.id}_{event_name}"
                else:
                    limit_key = f"rate_limit_global_{event_name}"
                
                # Verificar rate limit según estrategia
                if not _check_rate_limit(limit_key, effective_rate, window, strategy, burst_allowance):
                    # Emitir error de rate limit
                    emit('rate_limit_error', {
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'message': f'Rate limit exceeded for {event_name}',
                        'retry_after': _calculate_retry_after(limit_key, window),
                        'limit': effective_rate,
                        'window': window
                    })
                    
                    # Log del rate limit
                    logger.warning(f"Rate limit excedido - Usuario: {current_user.username if current_user else 'Global'}, Evento: {event_name}")
                    
                    # Incrementar métricas de rate limit
                    metrics_cache[f'rate_limit_violations_{event_name}'] += 1
                    
                    return
                
                # Ejecutar función si pasa el rate limit
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error en rate limiting: {str(e)}")
                return f(*args, **kwargs)  # Continuar en caso de error
        
        decorated_function._rate_limit = {
            'rate': rate,
            'window': window,
            'strategy': strategy.value
        }
        return decorated_function
    
    return decorator


def socket_validate_data(
    schema: Optional[Any] = None,
    required_fields: Optional[list[str]] = None,
    sanitize: bool = True,
    max_size: Optional[int] = None
):
    """
    Validación de datos para eventos WebSocket
    
    Args:
        schema: Schema de Marshmallow para validación
        required_fields: Campos requeridos
        sanitize: Sanitizar datos de entrada
        max_size: Tamaño máximo de datos en bytes
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = args[0] if args else {}
                
                # Verificar tamaño máximo
                if max_size and len(json.dumps(data).encode('utf-8')) > max_size:
                    emit('validation_error', {
                        'code': 'DATA_TOO_LARGE',
                        'message': f'Data exceeds maximum size of {max_size} bytes'
                    })
                    return
                
                # Verificar campos requeridos
                if required_fields:
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        emit('validation_error', {
                            'code': 'MISSING_REQUIRED_FIELDS',
                            'message': f'Missing required fields: {missing_fields}'
                        })
                        return
                
                # Validar con schema de Marshmallow
                if schema:
                    try:
                        validated_data = schema.load(data)
                        args = (validated_data,) + args[1:]
                    except ValidationError as ve:
                        emit('validation_error', {
                            'code': 'SCHEMA_VALIDATION_FAILED',
                            'message': 'Data validation failed',
                            'errors': ve.messages
                        })
                        return
                
                # Sanitizar datos si se requiere
                if sanitize and isinstance(data, dict):
                    sanitized_data = _sanitize_dict_data(data)
                    args = (sanitized_data,) + args[1:]
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error en validación de datos: {str(e)}")
                emit('validation_error', {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Data validation failed'
                })
        
        decorated_function._validation_schema = schema
        decorated_function._required_fields = required_fields
        return decorated_function
    
    return decorator


def socket_log_activity(
    activity_type: ActivityType,
    description: Optional[str] = None,
    include_data: bool = False,
    sensitive_fields: Optional[list[str]] = None
):
    """
    Logging automático de actividades para eventos WebSocket
    
    Args:
        activity_type: Tipo de actividad a registrar
        description: Descripción personalizada
        include_data: Incluir datos del evento en el log
        sensitive_fields: Campos sensibles a excluir del log
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            current_user = kwargs.get('current_user')
            event_name = f.__name__
            
            try:
                # Ejecutar función
                result = f(*args, **kwargs)
                
                # Calcular tiempo de ejecución
                execution_time = time.time() - start_time
                
                # Preparar datos para el log
                log_data = {
                    'event_name': event_name,
                    'execution_time': execution_time,
                    'session_id': request.sid,
                    'ip_address': request.environ.get('REMOTE_ADDR'),
                    'user_agent': request.environ.get('HTTP_USER_AGENT')
                }
                
                # Incluir datos del evento si se requiere
                if include_data and args:
                    event_data = args[0] if args else {}
                    if sensitive_fields:
                        event_data = _remove_sensitive_fields(event_data, sensitive_fields)
                    log_data['event_data'] = event_data
                
                # Registrar actividad en base de datos
                if current_user:
                    _log_user_activity(
                        current_user,
                        activity_type,
                        description or f"WebSocket event: {event_name}",
                        log_data
                    )
                
                # Actualizar métricas de eventos
                _update_event_metrics(event_name, execution_time, success=True)
                
                return result
                
            except Exception as e:
                # Log de error
                execution_time = time.time() - start_time
                
                logger.error(f"Error en evento {event_name}: {str(e)}")
                
                if current_user:
                    _log_user_activity(
                        current_user,
                        ActivityType.ERROR,
                        f"Error in WebSocket event: {event_name} - {str(e)}",
                        {'event_name': event_name, 'error': str(e)}
                    )
                
                # Actualizar métricas de error
                _update_event_metrics(event_name, execution_time, success=False)
                
                raise
        
        decorated_function._logs_activity = True
        decorated_function._activity_type = activity_type
        return decorated_function
    
    return decorator


def socket_cache_result(
    ttl: int = 300,
    cache_key_func: Optional[Callable] = None,
    per_user: bool = True,
    invalidate_on: Optional[list[str]] = None
):
    """
    Cache de resultados para eventos WebSocket
    
    Args:
        ttl: Tiempo de vida del cache en segundos
        cache_key_func: Función personalizada para generar clave de cache
        per_user: Cache por usuario
        invalidate_on: Eventos que invalidan el cache
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                current_user = kwargs.get('current_user')
                
                # Generar clave de cache
                if cache_key_func:
                    cache_key = cache_key_func(*args, **kwargs)
                else:
                    cache_key = _generate_default_cache_key(f.__name__, args, current_user if per_user else None)
                
                # Verificar cache existente
                cached_result = cache_get(cache_key)
                if cached_result is not None:
                    # Emitir resultado desde cache
                    emit(f.__name__ + '_result', cached_result)
                    return cached_result
                
                # Ejecutar función y cachear resultado
                result = f(*args, **kwargs)
                
                if result is not None:
                    cache_set(cache_key, result, timeout=ttl)
                
                return result
                
            except Exception as e:
                logger.error(f"Error en cache de eventos: {str(e)}")
                return f(*args, **kwargs)
        
        decorated_function._cached = True
        decorated_function._cache_ttl = ttl
        return decorated_function
    
    return decorator


def socket_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Reintento automático para eventos WebSocket
    
    Args:
        max_attempts: Número máximo de intentos
        delay: Delay inicial en segundos
        backoff_factor: Factor de incremento del delay
        exceptions: Excepciones que activan el reintento
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        # Último intento, re-lanzar excepción
                        logger.error(f"Función {f.__name__} falló después de {max_attempts} intentos: {str(e)}")
                        raise
                    
                    # Log del intento fallido
                    logger.warning(f"Intento {attempt + 1} de {f.__name__} falló: {str(e)}, reintentando en {current_delay}s")
                    
                    # Esperar antes del siguiente intento
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                
                except Exception as e:
                    # Excepción no contemplada para reintento
                    logger.error(f"Error no recuperable en {f.__name__}: {str(e)}")
                    raise
        
        decorated_function._retryable = True
        decorated_function._max_attempts = max_attempts
        return decorated_function
    
    return decorator


def socket_maintenance_check(
    allow_admins: bool = True,
    custom_message: Optional[str] = None
):
    """
    Verificación de modo mantenimiento
    
    Args:
        allow_admins: Permitir acceso a administradores durante mantenimiento
        custom_message: Mensaje personalizado de mantenimiento
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verificar si el sistema está en mantenimiento
                maintenance_info = cache_get('system_maintenance')
                
                if maintenance_info and maintenance_info.get('enabled'):
                    current_user = kwargs.get('current_user')
                    
                    # Permitir acceso a administradores si está configurado
                    if allow_admins and current_user and current_user.role == UserRole.ADMIN:
                        return f(*args, **kwargs)
                    
                    # Emitir mensaje de mantenimiento
                    emit('maintenance_error', {
                        'code': 'SYSTEM_MAINTENANCE',
                        'message': custom_message or maintenance_info.get('message', 'System under maintenance'),
                        'estimated_duration': maintenance_info.get('estimated_duration'),
                        'timestamp': format_datetime(datetime.now(timezone.utc))
                    })
                    return
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error verificando mantenimiento: {str(e)}")
                return f(*args, **kwargs)
        
        decorated_function._checks_maintenance = True
        return decorated_function
    
    return decorator


def socket_namespace_required(namespace: str):
    """
    Verificación de namespace requerido
    
    Args:
        namespace: Namespace requerido para el evento
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_namespace = request.namespace
            
            if current_namespace != namespace:
                emit('namespace_error', {
                    'code': 'WRONG_NAMESPACE',
                    'message': f'This event requires namespace {namespace}',
                    'current_namespace': current_namespace,
                    'required_namespace': namespace
                })
                return
            
            return f(*args, **kwargs)
        
        decorated_function._required_namespace = namespace
        return decorated_function
    
    return decorator


def socket_project_access_required(
    project_id_param: str = 'project_id',
    roles: Optional[list[UserRole]] = None
):
    """
    Verificación de acceso a proyecto específico
    
    Args:
        project_id_param: Parámetro que contiene el ID del proyecto
        roles: Roles permitidos para acceder al proyecto
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                current_user = kwargs.get('current_user')
                if not current_user:
                    emit('project_access_error', {
                        'code': 'USER_NOT_AUTHENTICATED',
                        'message': 'Authentication required'
                    })
                    return
                
                data = args[0] if args else {}
                project_id = data.get(project_id_param)
                
                if not project_id:
                    emit('project_access_error', {
                        'code': 'PROJECT_ID_REQUIRED',
                        'message': f'Parameter {project_id_param} is required'
                    })
                    return
                
                # Verificar acceso al proyecto
                project = Project.query.get(project_id)
                if not project:
                    emit('project_access_error', {
                        'code': 'PROJECT_NOT_FOUND',
                        'message': 'Project not found'
                    })
                    return
                
                # Verificar permisos
                if not _check_project_access(current_user, project, roles):
                    emit('project_access_error', {
                        'code': 'PROJECT_ACCESS_DENIED',
                        'message': 'Access denied to project'
                    })
                    return
                
                # Añadir proyecto al contexto
                kwargs['project'] = project
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error verificando acceso a proyecto: {str(e)}")
                emit('project_access_error', {
                    'code': 'PROJECT_ACCESS_ERROR',
                    'message': 'Project access verification failed'
                })
        
        decorated_function._requires_project_access = True
        return decorated_function
    
    return decorator


def socket_mentorship_access_required(
    session_id_param: str = 'session_id',
    allow_observers: bool = False
):
    """
    Verificación de acceso a sesión de mentoría
    
    Args:
        session_id_param: Parámetro que contiene el ID de la sesión
        allow_observers: Permitir observadores en la sesión
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                current_user = kwargs.get('current_user')
                if not current_user:
                    emit('mentorship_access_error', {
                        'code': 'USER_NOT_AUTHENTICATED',
                        'message': 'Authentication required'
                    })
                    return
                
                data = args[0] if args else {}
                session_id = data.get(session_id_param)
                
                if not session_id:
                    emit('mentorship_access_error', {
                        'code': 'SESSION_ID_REQUIRED',
                        'message': f'Parameter {session_id_param} is required'
                    })
                    return
                
                # Verificar acceso a la sesión
                session = MentorshipSession.query.get(session_id)
                if not session:
                    emit('mentorship_access_error', {
                        'code': 'SESSION_NOT_FOUND',
                        'message': 'Mentorship session not found'
                    })
                    return
                
                # Verificar permisos de acceso
                if not _check_mentorship_access(current_user, session, allow_observers):
                    emit('mentorship_access_error', {
                        'code': 'SESSION_ACCESS_DENIED',
                        'message': 'Access denied to mentorship session'
                    })
                    return
                
                # Añadir sesión al contexto
                kwargs['mentorship_session'] = session
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error verificando acceso a mentoría: {str(e)}")
                emit('mentorship_access_error', {
                    'code': 'MENTORSHIP_ACCESS_ERROR',
                    'message': 'Mentorship access verification failed'
                })
        
        decorated_function._requires_mentorship_access = True
        return decorated_function
    
    return decorator


# Funciones auxiliares privadas

def _check_permission_level(user: User, level: PermissionLevel) -> bool:
    """Verifica el nivel de permisos del usuario"""
    user_role = user.role
    
    level_hierarchy = {
        PermissionLevel.PUBLIC: [UserRole.ADMIN, UserRole.ENTREPRENEUR, UserRole.ALLY, UserRole.CLIENT],
        PermissionLevel.USER: [UserRole.ADMIN, UserRole.ENTREPRENEUR, UserRole.ALLY, UserRole.CLIENT],
        PermissionLevel.ENTREPRENEUR: [UserRole.ADMIN, UserRole.ENTREPRENEUR],
        PermissionLevel.MENTOR: [UserRole.ADMIN, UserRole.ALLY],
        PermissionLevel.ADMIN: [UserRole.ADMIN],
        PermissionLevel.SUPER_ADMIN: [UserRole.ADMIN]  # Implementar super admin en el futuro
    }
    
    return user_role in level_hierarchy.get(level, [])


def _check_resource_ownership(user: User, resource_id: str, resource_type: str) -> bool:
    """Verifica la propiedad de un recurso"""
    try:
        if resource_type == 'project_id':
            project = Project.query.get(resource_id)
            return project and (project.entrepreneur_id == user.id or user.role == UserRole.ADMIN)
        
        elif resource_type == 'mentorship_session_id':
            session = MentorshipSession.query.get(resource_id)
            return session and (session.entrepreneur_id == user.id or session.mentor_id == user.id or user.role == UserRole.ADMIN)
        
        # Añadir más tipos de recursos según sea necesario
        return False
        
    except Exception as e:
        logger.error(f"Error verificando propiedad de recurso: {str(e)}")
        return False


def _get_default_rate_limit(event_name: str) -> int:
    """Obtiene el rate limit por defecto para un evento"""
    return EVENT_RATE_LIMITS.get(event_name, {}).get('rate', RATE_LIMIT_DEFAULTS.get(event_name, 60))


def _calculate_adaptive_rate_limit(event_name: str, base_rate: int) -> int:
    """Calcula rate limit adaptativo basado en carga del sistema"""
    try:
        # Obtener métricas de carga
        current_connections = metrics_cache.get('current_connections', 0)
        event_frequency = metrics_cache.get(f'event_frequency_{event_name}', 0)
        
        # Ajustar rate limit basado en carga
        if current_connections > 1000:
            return int(base_rate * 0.5)  # Reducir rate limit si hay muchas conexiones
        elif event_frequency > 100:
            return int(base_rate * 0.7)  # Reducir si el evento es muy frecuente
        else:
            return base_rate
            
    except Exception:
        return base_rate


def _check_rate_limit(
    key: str, 
    rate: int, 
    window: int, 
    strategy: RateLimitStrategy,
    burst_allowance: Optional[int] = None
) -> bool:
    """Verifica rate limit según la estrategia especificada"""
    try:
        now = datetime.now(timezone.utc)
        
        if strategy == RateLimitStrategy.SLIDING_WINDOW:
            return _check_sliding_window_rate_limit(key, rate, window, now)
        elif strategy == RateLimitStrategy.FIXED_WINDOW:
            return _check_fixed_window_rate_limit(key, rate, window, now)
        elif strategy == RateLimitStrategy.TOKEN_BUCKET:
            return _check_token_bucket_rate_limit(key, rate, window, now, burst_allowance)
        else:
            return _check_sliding_window_rate_limit(key, rate, window, now)
            
    except Exception as e:
        logger.error(f"Error verificando rate limit: {str(e)}")
        return True  # Permitir en caso de error


def _check_sliding_window_rate_limit(key: str, rate: int, window: int, now: datetime) -> bool:
    """Implementa rate limiting con ventana deslizante"""
    cutoff = now - timedelta(seconds=window)
    
    # Obtener timestamps de eventos recientes
    recent_events = rate_limit_cache[key]['events']
    
    # Limpiar eventos antiguos
    while recent_events and recent_events[0] < cutoff:
        recent_events.popleft()
    
    # Verificar si excede el límite
    if len(recent_events) >= rate:
        return False
    
    # Añadir evento actual
    recent_events.append(now)
    return True


def _check_fixed_window_rate_limit(key: str, rate: int, window: int, now: datetime) -> bool:
    """Implementa rate limiting con ventana fija"""
    window_start = now.replace(second=0, microsecond=0)
    window_key = f"{key}_{window_start.timestamp()}"
    
    current_count = rate_limit_cache[window_key]['count']
    
    if current_count >= rate:
        return False
    
    rate_limit_cache[window_key]['count'] += 1
    return True


def _check_token_bucket_rate_limit(key: str, rate: int, window: int, now: datetime, burst: Optional[int]) -> bool:
    """Implementa rate limiting con token bucket"""
    bucket_info = rate_limit_cache[key]['bucket']
    
    if not bucket_info:
        bucket_info = {
            'tokens': rate,
            'last_refill': now,
            'capacity': burst or rate * 2
        }
        rate_limit_cache[key]['bucket'] = bucket_info
    
    # Calcular tokens a añadir
    time_passed = (now - bucket_info['last_refill']).total_seconds()
    tokens_to_add = (time_passed / window) * rate
    
    bucket_info['tokens'] = min(bucket_info['capacity'], bucket_info['tokens'] + tokens_to_add)
    bucket_info['last_refill'] = now
    
    # Verificar si hay tokens disponibles
    if bucket_info['tokens'] < 1:
        return False
    
    bucket_info['tokens'] -= 1
    return True


def _calculate_retry_after(key: str, window: int) -> int:
    """Calcula el tiempo de espera para el siguiente intento"""
    recent_events = rate_limit_cache[key]['events']
    if recent_events:
        oldest_event = recent_events[0]
        return max(0, window - int((datetime.now(timezone.utc) - oldest_event).total_seconds()))
    return window


def _sanitize_dict_data(data: dict) -> dict:
    """Sanitiza datos del diccionario"""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_input(value)
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_dict_data(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_input(item) if isinstance(item, str) else item for item in value]
        else:
            sanitized[key] = value
    return sanitized


def _remove_sensitive_fields(data: dict, sensitive_fields: list[str]) -> dict:
    """Remueve campos sensibles de los datos"""
    filtered_data = data.copy()
    for field in sensitive_fields:
        if field in filtered_data:
            filtered_data[field] = '[REDACTED]'
    return filtered_data


def _log_user_activity(user: User, activity_type: ActivityType, description: str, metadata: dict):
    """Registra actividad del usuario en la base de datos"""
    try:
        from app import db
        
        activity = ActivityLog(
            user_id=user.id,
            activity_type=activity_type,
            description=description,
            metadata=metadata,
            ip_address=request.environ.get('REMOTE_ADDR'),
            user_agent=request.environ.get('HTTP_USER_AGENT'),
            session_id=request.sid
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except SQLAlchemyError as e:
        logger.error(f"Error registrando actividad en BD: {str(e)}")


def _update_event_metrics(event_name: str, execution_time: float, success: bool):
    """Actualiza métricas de eventos"""
    metrics_key = f'event_metrics_{event_name}'
    metrics = cache_get(metrics_key) or EventMetrics(event_name)
    
    metrics.call_count += 1
    metrics.total_time += execution_time
    metrics.last_called = datetime.now(timezone.utc)
    metrics.average_time = metrics.total_time / metrics.call_count
    
    if not success:
        metrics.error_count += 1
    
    cache_set(metrics_key, metrics, timeout=3600)


def _generate_default_cache_key(func_name: str, args: tuple, user: Optional[User]) -> str:
    """Genera clave de cache por defecto"""
    key_parts = [func_name]
    
    if user:
        key_parts.append(f"user_{user.id}")
    
    if args:
        # Hash de los argumentos para crear clave única
        args_hash = hashlib.md5(json.dumps(args[0] if args else {}, sort_keys=True).encode()).hexdigest()[:8]
        key_parts.append(f"args_{args_hash}")
    
    return "_".join(key_parts)


def _check_project_access(user: User, project: Project, allowed_roles: Optional[list[UserRole]]) -> bool:
    """Verifica acceso a proyecto"""
    # Verificar si es el emprendedor del proyecto
    if project.entrepreneur_id == user.id:
        return True
    
    # Verificar si es administrador
    if user.role == UserRole.ADMIN:
        return True
    
    # Verificar roles permitidos
    if allowed_roles and user.role not in allowed_roles:
        return False
    
    # Verificar si es mentor asignado al proyecto
    if user.role == UserRole.ALLY and user in project.mentors:
        return True
    
    # Verificar si es cliente con acceso al proyecto
    if user.role == UserRole.CLIENT and project.is_public:
        return True
    
    return False


def _check_mentorship_access(user: User, session: MentorshipSession, allow_observers: bool) -> bool:
    """Verifica acceso a sesión de mentoría"""
    # Verificar si es participante directo
    if session.entrepreneur_id == user.id or session.mentor_id == user.id:
        return True
    
    # Verificar si es administrador
    if user.role == UserRole.ADMIN:
        return True
    
    # Verificar observadores si está permitido
    if allow_observers and user.role in [UserRole.ALLY, UserRole.CLIENT]:
        return True
    
    return False


# Decorador compuesto para funcionalidad completa
def socket_endpoint(
    auth_required: bool = True,
    permission: Optional[Union[str, list[str]]] = None,
    permission_level: PermissionLevel = PermissionLevel.USER,
    rate_limit_config: Optional[dict] = None,
    validation_schema: Optional[Any] = None,
    required_fields: Optional[list[str]] = None,
    log_activity: bool = True,
    activity_type: ActivityType = ActivityType.USER_ACTIVITY,
    cache_result: bool = False,
    cache_ttl: int = 300,
    check_maintenance: bool = True,
    namespace: Optional[str] = None
):
    """
    Decorador compuesto que combina múltiples funcionalidades
    
    Proporciona un punto de entrada único para configurar
    todas las funcionalidades de un endpoint WebSocket.
    """
    def decorator(f: Callable) -> Callable:
        # Aplicar decoradores en orden
        decorated_func = f
        
        # Namespace (si se especifica)
        if namespace:
            decorated_func = socket_namespace_required(namespace)(decorated_func)
        
        # Verificación de mantenimiento
        if check_maintenance:
            decorated_func = socket_maintenance_check()(decorated_func)
        
        # Cache de resultados
        if cache_result:
            decorated_func = socket_cache_result(ttl=cache_ttl)(decorated_func)
        
        # Logging de actividad
        if log_activity:
            decorated_func = socket_log_activity(activity_type)(decorated_func)
        
        # Validación de datos
        if validation_schema or required_fields:
            decorated_func = socket_validate_data(
                schema=validation_schema,
                required_fields=required_fields
            )(decorated_func)
        
        # Rate limiting
        if rate_limit_config:
            decorated_func = socket_rate_limit(**rate_limit_config)(decorated_func)
        
        # Permisos
        if permission:
            decorated_func = socket_permission_required(
                permission=permission,
                permission_level=permission_level
            )(decorated_func)
        
        # Autenticación
        if auth_required:
            decorated_func = socket_auth_required()(decorated_func)
        
        return decorated_func
    
    return decorator


# Exportar decoradores principales
__all__ = [
    'socket_auth_required',
    'socket_permission_required',
    'socket_rate_limit',
    'socket_validate_data',
    'socket_log_activity',
    'socket_cache_result',
    'socket_retry',
    'socket_maintenance_check',
    'socket_namespace_required',
    'socket_project_access_required',
    'socket_mentorship_access_required',
    'socket_endpoint',
    'PermissionLevel',
    'RateLimitStrategy',
    'EventMetrics'
]