"""
Eventos Globales del Sistema WebSockets - Ecosistema de Emprendimiento
=====================================================================

Este módulo maneja todos los eventos globales del sistema de WebSockets
que son transversales a la aplicación y no están específicamente atados
a namespaces particulares.

Funcionalidades principales:
- Eventos de sistema (heartbeat, status, health checks)
- Eventos de conexión/desconexión mejorados
- Broadcasting del sistema
- Eventos de monitoreo y logging
- Integración con servicios del ecosistema
- Eventos de emergencia y mantenimiento
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from functools import wraps
from collections import defaultdict, deque

from flask import request, current_app, g
from flask_socketio import emit, join_room, leave_room, disconnect, rooms
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from redis import Redis
from celery import current_app as celery_app

from app.core.exceptions import (
    SocketError,
    SocketAuthenticationError,
    SocketRateLimitError,
    SystemMaintenanceError
)
from app.core.permissions import has_permission, UserRole
from app.core.constants import (
    SOCKET_EVENTS,
    SYSTEM_STATUS,
    RATE_LIMIT_DEFAULTS,
    HEARTBEAT_INTERVAL
)
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.models.analytics import SystemMetric
from app.services.user_service import UserService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.utils.decorators import rate_limit, log_activity
from app.utils.validators import validate_event_data
from app.utils.formatters import format_datetime, format_user_info
from app.utils.cache_utils import cache_get, cache_set, cache_delete

logger = logging.getLogger(__name__)

# Cache para métricas en tiempo real
metrics_cache = {}
connection_stats = defaultdict(int)
event_stats = defaultdict(int)
error_stats = defaultdict(list)

# Cola de eventos para procesamiento batch
event_queue = deque(maxlen=10000)

# Rate limiting por usuario
user_rate_limits = defaultdict(lambda: defaultdict(list))

# Sistema de health checks
health_checks = {
    'database': True,
    'redis': True,
    'celery': True,
    'email': True
}


class EventRegistry:
    """
    Registro central de eventos del sistema
    
    Mantiene un registro de todos los eventos disponibles,
    sus handlers y metadatos asociados.
    """
    
    def __init__(self):
        self._events: Dict[str, Dict[str, Any]] = {}
        self._middlewares: List[Callable] = []
        self._global_handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    def register_event(self, event_name: str, handler: Callable, 
                      metadata: Dict[str, Any] = None):
        """Registra un nuevo evento en el sistema"""
        self._events[event_name] = {
            'handler': handler,
            'metadata': metadata or {},
            'registered_at': datetime.utcnow(),
            'call_count': 0,
            'error_count': 0
        }
        logger.info(f"Evento '{event_name}' registrado exitosamente")
    
    def add_middleware(self, middleware: Callable):
        """Añade middleware que se ejecuta antes de cada evento"""
        self._middlewares.append(middleware)
    
    def add_global_handler(self, event_pattern: str, handler: Callable):
        """Añade handler global para patrones de eventos"""
        self._global_handlers[event_pattern].append(handler)
    
    def get_event_info(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un evento registrado"""
        return self._events.get(event_name)
    
    def get_all_events(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene todos los eventos registrados"""
        return self._events.copy()


# Instancia global del registro
event_registry = EventRegistry()


def socket_event(event_name: str, **metadata):
    """
    Decorador para registrar eventos de socket automáticamente
    
    Args:
        event_name: Nombre del evento
        **metadata: Metadatos adicionales del evento
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Ejecutar middlewares
                for middleware in event_registry._middlewares:
                    result = middleware(event_name, args, kwargs)
                    if result is False:
                        return
                
                # Incrementar contador de llamadas
                if event_name in event_registry._events:
                    event_registry._events[event_name]['call_count'] += 1
                
                # Ejecutar handler principal
                result = func(*args, **kwargs)
                
                # Ejecutar handlers globales
                for pattern, handlers in event_registry._global_handlers.items():
                    if pattern in event_name or pattern == '*':
                        for handler in handlers:
                            try:
                                handler(event_name, args, kwargs, result)
                            except Exception as e:
                                logger.error(f"Error en handler global {pattern}: {str(e)}")
                
                return result
                
            except Exception as e:
                # Incrementar contador de errores
                if event_name in event_registry._events:
                    event_registry._events[event_name]['error_count'] += 1
                
                logger.error(f"Error en evento {event_name}: {str(e)}")
                emit('error', {
                    'event': event_name,
                    'message': str(e),
                    'timestamp': format_datetime(datetime.utcnow())
                })
                raise
        
        # Registrar el evento
        event_registry.register_event(event_name, wrapper, metadata)
        return wrapper
    
    return decorator


def require_auth(f: Callable) -> Callable:
    """Decorador que requiere autenticación para eventos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            if not user_id:
                emit('auth_error', {'message': 'Authentication required'})
                disconnect()
                return
            
            user = User.query.get(user_id)
            if not user or not user.is_active:
                emit('auth_error', {'message': 'User not found or inactive'})
                disconnect()
                return
            
            # Añadir usuario al contexto
            g.current_user = user
            kwargs['current_user'] = user
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error en autenticación: {str(e)}")
            emit('auth_error', {'message': 'Authentication failed'})
            disconnect()
    
    return decorated_function


def check_rate_limit(event_name: str, user_id: str, 
                    rate: int = None, window: int = 60) -> bool:
    """
    Verifica rate limiting para eventos por usuario
    
    Args:
        event_name: Nombre del evento
        user_id: ID del usuario
        rate: Número máximo de eventos permitidos
        window: Ventana de tiempo en segundos
        
    Returns:
        bool: True si está dentro del límite
    """
    try:
        if rate is None:
            rate = RATE_LIMIT_DEFAULTS.get(event_name, 60)
        
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window)
        
        # Limpiar eventos antiguos
        user_rate_limits[user_id][event_name] = [
            timestamp for timestamp in user_rate_limits[user_id][event_name]
            if timestamp > cutoff
        ]
        
        # Verificar límite
        if len(user_rate_limits[user_id][event_name]) >= rate:
            return False
        
        # Añadir nuevo evento
        user_rate_limits[user_id][event_name].append(now)
        return True
        
    except Exception as e:
        logger.error(f"Error verificando rate limit: {str(e)}")
        return True  # En caso de error, permitir el evento


@socket_event('heartbeat', description="Mantiene conexión activa")
def handle_heartbeat(data=None, current_user=None):
    """
    Maneja heartbeat para mantener conexiones activas
    
    Los clientes deben enviar heartbeat cada 30 segundos para
    mantener la conexión activa y actualizar métricas.
    """
    try:
        timestamp = datetime.utcnow()
        
        # Responder con pong
        emit('pong', {
            'timestamp': format_datetime(timestamp),
            'server_time': format_datetime(timestamp)
        })
        
        # Actualizar métricas si hay usuario autenticado
        if current_user:
            _update_user_activity(current_user, 'heartbeat')
            
            # Actualizar estadísticas de conexión
            connection_stats['total_heartbeats'] += 1
            connection_stats['active_users'] = len(_get_active_users())
        
        logger.debug(f"Heartbeat recibido - Usuario: {current_user.username if current_user else 'Anónimo'}")
        
    except Exception as e:
        logger.error(f"Error en heartbeat: {str(e)}")


@socket_event('ping', description="Ping básico del sistema")
@rate_limit(rate=30, per=60)
def handle_ping(data=None):
    """Maneja ping básico del sistema"""
    emit('pong', {
        'timestamp': format_datetime(datetime.utcnow()),
        'latency': data.get('timestamp') if data else None
    })


@socket_event('get_server_status', description="Obtiene estado del servidor")
@require_auth
def handle_get_server_status(data=None, current_user=None):
    """
    Obtiene el estado actual del servidor y servicios
    
    Proporciona información sobre el estado de los servicios,
    métricas básicas y health checks.
    """
    try:
        # Verificar permisos
        if not has_permission(current_user, 'view_system_status'):
            emit('permission_error', {'message': 'Insufficient permissions'})
            return
        
        # Realizar health checks
        _perform_health_checks()
        
        # Obtener métricas del sistema
        system_metrics = _get_system_metrics()
        
        # Responder con estado completo
        emit('server_status', {
            'status': 'healthy' if all(health_checks.values()) else 'degraded',
            'timestamp': format_datetime(datetime.utcnow()),
            'services': health_checks,
            'metrics': system_metrics,
            'uptime': _get_server_uptime(),
            'version': current_app.config.get('APP_VERSION', '1.0.0')
        })
        
        logger.info(f"Estado del servidor consultado por {current_user.username}")
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del servidor: {str(e)}")
        emit('error', {'message': 'Failed to get server status'})


@socket_event('subscribe_to_system_events', description="Suscripción a eventos del sistema")
@require_auth
def handle_subscribe_to_system_events(data, current_user=None):
    """
    Suscribe usuario a eventos del sistema
    
    Permite a usuarios autorizados recibir eventos del sistema
    como actualizaciones de estado, alertas, etc.
    """
    try:
        event_types = data.get('event_types', [])
        
        if not event_types:
            emit('error', {'message': 'Event types required'})
            return
        
        # Validar tipos de eventos
        valid_events = [
            'system_alerts', 'maintenance_notices', 'security_alerts',
            'performance_warnings', 'user_activities'
        ]
        
        invalid_events = [e for e in event_types if e not in valid_events]
        if invalid_events:
            emit('error', {'message': f'Invalid event types: {invalid_events}'})
            return
        
        # Verificar permisos para cada tipo de evento
        for event_type in event_types:
            if not _can_subscribe_to_event(current_user, event_type):
                emit('permission_error', {
                    'message': f'No permission for event type: {event_type}'
                })
                return
        
        # Suscribir a rooms de eventos
        for event_type in event_types:
            join_room(f'system_{event_type}')
        
        emit('subscribed_to_system_events', {
            'event_types': event_types,
            'timestamp': format_datetime(datetime.utcnow())
        })
        
        logger.info(f"Usuario {current_user.username} suscrito a eventos del sistema: {event_types}")
        
    except Exception as e:
        logger.error(f"Error en suscripción a eventos del sistema: {str(e)}")
        emit('error', {'message': 'Failed to subscribe to system events'})


@socket_event('get_connection_info', description="Información de conexión")
@require_auth
def handle_get_connection_info(data=None, current_user=None):
    """
    Obtiene información detallada de la conexión actual
    
    Proporciona datos sobre la sesión WebSocket, ubicación,
    estadísticas de uso y configuración.
    """
    try:
        session_id = request.sid
        user_rooms = rooms(sid=session_id)
        
        connection_info = {
            'session_id': session_id,
            'user_id': str(current_user.id),
            'username': current_user.username,
            'role': current_user.role.value,
            'connected_at': format_datetime(datetime.utcnow()),
            'rooms': list(user_rooms),
            'namespace': request.namespace,
            'transport': getattr(request, 'transport', 'unknown'),
            'client_info': {
                'ip': request.environ.get('REMOTE_ADDR'),
                'user_agent': request.environ.get('HTTP_USER_AGENT'),
                'origin': request.environ.get('HTTP_ORIGIN')
            }
        }
        
        emit('connection_info', connection_info)
        
        logger.debug(f"Información de conexión enviada a {current_user.username}")
        
    except Exception as e:
        logger.error(f"Error obteniendo información de conexión: {str(e)}")
        emit('error', {'message': 'Failed to get connection info'})


@socket_event('broadcast_message', description="Difusión de mensajes")
@require_auth
@rate_limit(rate=5, per=300)  # 5 broadcasts por 5 minutos
def handle_broadcast_message(data, current_user=None):
    """
    Difunde un mensaje a usuarios específicos o grupos
    
    Permite a usuarios autorizados enviar mensajes de difusión
    a otros usuarios, roles o todo el sistema.
    """
    try:
        # Verificar permisos de broadcasting
        if not has_permission(current_user, 'broadcast_messages'):
            emit('permission_error', {'message': 'Broadcasting not allowed'})
            return
        
        message = data.get('message')
        target_type = data.get('target_type', 'role')  # role, user, all
        targets = data.get('targets', [])
        priority = data.get('priority', 'normal')
        
        if not message:
            emit('error', {'message': 'Message is required'})
            return
        
        # Validar datos
        if not validate_event_data(data, ['message', 'target_type']):
            emit('error', {'message': 'Invalid broadcast data'})
            return
        
        broadcast_data = {
            'type': 'broadcast',
            'message': message,
            'priority': priority,
            'from': format_user_info(current_user),
            'timestamp': format_datetime(datetime.utcnow()),
            'id': f"broadcast_{datetime.utcnow().timestamp()}"
        }
        
        # Determinar destinatarios y enviar
        sent_count = _send_broadcast(target_type, targets, broadcast_data)
        
        # Confirmar envío
        emit('broadcast_sent', {
            'target_type': target_type,
            'targets': targets,
            'sent_count': sent_count,
            'timestamp': format_datetime(datetime.utcnow())
        })
        
        # Log de actividad
        _log_user_activity(
            current_user,
            ActivityType.BROADCAST_MESSAGE,
            f"Mensaje difundido a {sent_count} usuarios"
        )
        
        logger.info(f"Broadcast enviado por {current_user.username} a {sent_count} usuarios")
        
    except Exception as e:
        logger.error(f"Error en broadcast: {str(e)}")
        emit('error', {'message': 'Failed to send broadcast'})


@socket_event('get_system_metrics', description="Métricas del sistema")
@require_auth
@rate_limit(rate=10, per=60)
def handle_get_system_metrics(data, current_user=None):
    """
    Obtiene métricas detalladas del sistema
    
    Proporciona métricas de rendimiento, uso y estadísticas
    para usuarios con permisos apropiados.
    """
    try:
        # Verificar permisos
        if not has_permission(current_user, 'view_system_metrics'):
            emit('permission_error', {'message': 'Metrics access denied'})
            return
        
        metric_types = data.get('metrics', ['basic'])
        time_range = data.get('time_range', '1h')
        
        # Obtener métricas solicitadas
        metrics = {}
        
        if 'basic' in metric_types:
            metrics['basic'] = _get_basic_metrics()
        
        if 'performance' in metric_types:
            metrics['performance'] = _get_performance_metrics()
        
        if 'websockets' in metric_types:
            metrics['websockets'] = _get_websocket_metrics()
        
        if 'users' in metric_types:
            metrics['users'] = _get_user_metrics(time_range)
        
        if 'errors' in metric_types:
            metrics['errors'] = _get_error_metrics(time_range)
        
        emit('system_metrics', {
            'metrics': metrics,
            'time_range': time_range,
            'timestamp': format_datetime(datetime.utcnow())
        })
        
        logger.debug(f"Métricas del sistema enviadas a {current_user.username}")
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {str(e)}")
        emit('error', {'message': 'Failed to get system metrics'})


@socket_event('emergency_alert', description="Alerta de emergencia")
@require_auth
def handle_emergency_alert(data, current_user=None):
    """
    Envía una alerta de emergencia a todo el sistema
    
    Solo disponible para administradores de sistema.
    Difunde alertas críticas a todos los usuarios conectados.
    """
    try:
        # Solo administradores pueden enviar alertas de emergencia
        if current_user.role != UserRole.ADMIN:
            emit('permission_error', {'message': 'Admin access required'})
            return
        
        alert_message = data.get('message')
        alert_level = data.get('level', 'critical')
        action_required = data.get('action_required', False)
        
        if not alert_message:
            emit('error', {'message': 'Alert message is required'})
            return
        
        # Preparar datos de la alerta
        alert_data = {
            'type': 'emergency_alert',
            'level': alert_level,
            'message': alert_message,
            'action_required': action_required,
            'from': format_user_info(current_user),
            'timestamp': format_datetime(datetime.utcnow()),
            'id': f"emergency_{datetime.utcnow().timestamp()}"
        }
        
        # Enviar a todos los usuarios conectados
        from app.sockets import socketio
        socketio.emit('emergency_alert', alert_data, broadcast=True)
        
        # Log crítico
        logger.critical(f"ALERTA DE EMERGENCIA enviada por {current_user.username}: {alert_message}")
        
        # Enviar confirmación
        emit('emergency_alert_sent', {
            'alert_id': alert_data['id'],
            'timestamp': alert_data['timestamp']
        })
        
        # Registrar en base de datos
        _log_user_activity(
            current_user,
            ActivityType.EMERGENCY_ALERT,
            f"Alerta de emergencia: {alert_message}"
        )
        
    except Exception as e:
        logger.error(f"Error enviando alerta de emergencia: {str(e)}")
        emit('error', {'message': 'Failed to send emergency alert'})


@socket_event('maintenance_mode', description="Modo mantenimiento")
@require_auth
def handle_maintenance_mode(data, current_user=None):
    """
    Activa/desactiva el modo de mantenimiento
    
    Solo administradores pueden controlar el modo de mantenimiento.
    Notifica a todos los usuarios sobre el estado del sistema.
    """
    try:
        # Solo administradores
        if current_user.role != UserRole.ADMIN:
            emit('permission_error', {'message': 'Admin access required'})
            return
        
        enable = data.get('enable', False)
        message = data.get('message', 'Sistema en mantenimiento')
        estimated_duration = data.get('estimated_duration')
        
        # Actualizar estado del sistema
        maintenance_data = {
            'enabled': enable,
            'message': message,
            'estimated_duration': estimated_duration,
            'started_by': format_user_info(current_user),
            'timestamp': format_datetime(datetime.utcnow())
        }
        
        # Guardar en cache
        cache_set('system_maintenance', maintenance_data, timeout=3600)
        
        # Notificar a todos los usuarios
        from app.sockets import socketio
        socketio.emit('maintenance_notice', maintenance_data, broadcast=True)
        
        # Confirmar al administrador
        emit('maintenance_mode_updated', {
            'enabled': enable,
            'timestamp': format_datetime(datetime.utcnow())
        })
        
        logger.warning(f"Modo mantenimiento {'activado' if enable else 'desactivado'} por {current_user.username}")
        
    except Exception as e:
        logger.error(f"Error en modo mantenimiento: {str(e)}")
        emit('error', {'message': 'Failed to update maintenance mode'})


@socket_event('user_activity_update', description="Actualización de actividad")
@require_auth
@rate_limit(rate=60, per=60)
def handle_user_activity_update(data, current_user=None):
    """
    Actualiza la actividad del usuario en tiempo real
    
    Registra acciones del usuario para analytics y presencia.
    """
    try:
        activity_type = data.get('activity_type')
        page = data.get('page')
        action = data.get('action')
        metadata = data.get('metadata', {})
        
        if not activity_type:
            return  # No emitir error para actividades opcionales
        
        # Actualizar actividad del usuario
        _update_user_activity(current_user, activity_type, {
            'page': page,
            'action': action,
            'metadata': metadata
        })
        
        # Actualizar métricas en tiempo real
        _update_realtime_metrics(current_user, activity_type)
        
        logger.debug(f"Actividad actualizada para {current_user.username}: {activity_type}")
        
    except Exception as e:
        logger.error(f"Error actualizando actividad: {str(e)}")


# Eventos de conexión/desconexión mejorados

@socket_event('connect', description="Conexión establecida")
def handle_connect(auth=None):
    """
    Maneja nuevas conexiones WebSocket
    
    Registra la conexión, valida autenticación y 
    configura el entorno inicial.
    """
    try:
        session_id = request.sid
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        user_agent = request.environ.get('HTTP_USER_AGENT', 'unknown')
        
        # Actualizar estadísticas
        connection_stats['total_connections'] += 1
        connection_stats['current_connections'] += 1
        
        # Log de conexión
        logger.info(f"Nueva conexión WebSocket - Session: {session_id}, IP: {client_ip}")
        
        # Verificar si hay mantenimiento activo
        maintenance_info = cache_get('system_maintenance')
        if maintenance_info and maintenance_info.get('enabled'):
            emit('maintenance_notice', maintenance_info)
        
        # Emitir confirmación de conexión
        emit('connection_established', {
            'session_id': session_id,
            'timestamp': format_datetime(datetime.utcnow()),
            'server_version': current_app.config.get('APP_VERSION', '1.0.0')
        })
        
    except Exception as e:
        logger.error(f"Error en conexión: {str(e)}")
        emit('error', {'message': 'Connection failed'})
        disconnect()


@socket_event('disconnect', description="Desconexión")
def handle_disconnect():
    """
    Maneja desconexiones WebSocket
    
    Limpia recursos y actualiza estadísticas.
    """
    try:
        session_id = request.sid
        
        # Buscar usuario por session_id
        user = _find_user_by_session(session_id)
        
        # Actualizar estadísticas
        connection_stats['current_connections'] = max(0, connection_stats['current_connections'] - 1)
        
        # Log de desconexión
        logger.info(f"Desconexión WebSocket - Session: {session_id}, Usuario: {user.username if user else 'Anónimo'}")
        
        # Limpiar datos del usuario si estaba autenticado
        if user:
            _cleanup_user_session(user, session_id)
        
    except Exception as e:
        logger.error(f"Error en desconexión: {str(e)}")


# Funciones auxiliares privadas

def _perform_health_checks():
    """Realiza health checks de todos los servicios"""
    try:
        # Check database
        from app import db
        db.session.execute('SELECT 1')
        health_checks['database'] = True
    except Exception:
        health_checks['database'] = False
    
    try:
        # Check Redis
        redis_client = Redis.from_url(current_app.config.get('REDIS_URL', 'redis://localhost:6379'))
        redis_client.ping()
        health_checks['redis'] = True
    except Exception:
        health_checks['redis'] = False
    
    try:
        # Check Celery
        celery_app.control.inspect().ping()
        health_checks['celery'] = True
    except Exception:
        health_checks['celery'] = False
    
    try:
        # Check Email service
        email_service = EmailService()
        health_checks['email'] = email_service.test_connection()
    except Exception:
        health_checks['email'] = False


def _get_system_metrics() -> Dict[str, Any]:
    """Obtiene métricas básicas del sistema"""
    return {
        'total_connections': connection_stats['total_connections'],
        'current_connections': connection_stats['current_connections'],
        'active_users': len(_get_active_users()),
        'total_events': sum(event_stats.values()),
        'memory_usage': _get_memory_usage(),
        'cpu_usage': _get_cpu_usage()
    }


def _get_basic_metrics() -> Dict[str, Any]:
    """Obtiene métricas básicas del sistema"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.meeting import Meeting
    
    return {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_projects': Project.query.count(),
        'active_projects': Project.query.filter_by(status='active').count(),
        'total_meetings': Meeting.query.count(),
        'meetings_today': Meeting.query.filter(
            Meeting.start_time >= datetime.utcnow().date()
        ).count()
    }


def _get_performance_metrics() -> Dict[str, Any]:
    """Obtiene métricas de rendimiento"""
    return {
        'response_time_avg': metrics_cache.get('response_time_avg', 0),
        'response_time_max': metrics_cache.get('response_time_max', 0),
        'database_queries_count': metrics_cache.get('db_queries', 0),
        'cache_hit_rate': metrics_cache.get('cache_hit_rate', 0),
        'memory_usage_mb': _get_memory_usage(),
        'cpu_usage_percent': _get_cpu_usage()
    }


def _get_websocket_metrics() -> Dict[str, Any]:
    """Obtiene métricas específicas de WebSockets"""
    return {
        'total_connections': connection_stats['total_connections'],
        'current_connections': connection_stats['current_connections'],
        'events_per_second': _calculate_events_per_second(),
        'average_latency': metrics_cache.get('websocket_latency', 0),
        'error_rate': _calculate_error_rate(),
        'namespace_usage': _get_namespace_usage()
    }


def _get_user_metrics(time_range: str) -> Dict[str, Any]:
    """Obtiene métricas de usuarios"""
    from app.models.user import User
    from app.models.activity_log import ActivityLog
    
    # Calcular rango de tiempo
    now = datetime.utcnow()
    if time_range == '1h':
        start_time = now - timedelta(hours=1)
    elif time_range == '24h':
        start_time = now - timedelta(days=1)
    elif time_range == '7d':
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(hours=1)
    
    return {
        'online_users': len(_get_active_users()),
        'new_users': User.query.filter(User.created_at >= start_time).count(),
        'active_sessions': ActivityLog.query.filter(
            ActivityLog.created_at >= start_time,
            ActivityLog.activity_type == ActivityType.USER_LOGIN
        ).count(),
        'user_activities': ActivityLog.query.filter(
            ActivityLog.created_at >= start_time
        ).count()
    }


def _get_error_metrics(time_range: str) -> Dict[str, Any]:
    """Obtiene métricas de errores"""
    # Filtrar errores por rango de tiempo
    now = datetime.utcnow()
    if time_range == '1h':
        cutoff = now - timedelta(hours=1)
    elif time_range == '24h':
        cutoff = now - timedelta(days=1)
    else:
        cutoff = now - timedelta(hours=1)
    
    recent_errors = []
    for error_type, error_list in error_stats.items():
        recent_errors.extend([
            err for err in error_list 
            if err.get('timestamp', datetime.min) > cutoff
        ])
    
    return {
        'total_errors': len(recent_errors),
        'error_rate': len(recent_errors) / max(1, (now - cutoff).total_seconds() / 60),
        'error_types': _group_errors_by_type(recent_errors),
        'critical_errors': len([e for e in recent_errors if e.get('level') == 'critical'])
    }


def _update_user_activity(user: User, activity_type: str, metadata: Dict = None):
    """Actualiza la actividad del usuario"""
    try:
        # Actualizar timestamp de última actividad
        user.last_activity = datetime.utcnow()
        
        # Registrar actividad en log si es significativa
        significant_activities = [
            'page_view', 'document_edit', 'message_sent', 
            'meeting_joined', 'project_created'
        ]
        
        if activity_type in significant_activities:
            _log_user_activity(user, ActivityType.USER_ACTIVITY, 
                             f"{activity_type}: {metadata or {}}")
        
        # Actualizar cache de usuarios activos
        active_users = cache_get('active_users') or set()
        active_users.add(str(user.id))
        cache_set('active_users', active_users, timeout=300)
        
    except Exception as e:
        logger.error(f"Error actualizando actividad de usuario: {str(e)}")


def _update_realtime_metrics(user: User, activity_type: str):
    """Actualiza métricas en tiempo real"""
    try:
        # Incrementar contador de eventos
        event_stats[activity_type] += 1
        event_stats['total'] += 1
        
        # Actualizar métricas por usuario
        user_key = f"user_metrics_{user.id}"
        user_metrics = cache_get(user_key) or {}
        user_metrics[activity_type] = user_metrics.get(activity_type, 0) + 1
        cache_set(user_key, user_metrics, timeout=3600)
        
        # Añadir a cola de eventos para procesamiento
        event_queue.append({
            'user_id': str(user.id),
            'activity_type': activity_type,
            'timestamp': datetime.utcnow(),
            'session_id': request.sid
        })
        
    except Exception as e:
        logger.error(f"Error actualizando métricas en tiempo real: {str(e)}")


def _can_subscribe_to_event(user: User, event_type: str) -> bool:
    """Verifica si el usuario puede suscribirse a un tipo de evento"""
    permission_map = {
        'system_alerts': 'view_system_alerts',
        'maintenance_notices': 'view_maintenance',
        'security_alerts': 'view_security_alerts',
        'performance_warnings': 'view_performance_metrics',
        'user_activities': 'view_user_activities'
    }
    
    required_permission = permission_map.get(event_type)
    if required_permission:
        return has_permission(user, required_permission)
    
    return False


def _send_broadcast(target_type: str, targets: List[str], data: Dict[str, Any]) -> int:
    """Envía un mensaje de broadcast y retorna el número de destinatarios"""
    from app.sockets import socketio
    
    sent_count = 0
    
    try:
        if target_type == 'all':
            socketio.emit('broadcast_message', data, broadcast=True)
            sent_count = connection_stats['current_connections']
        
        elif target_type == 'role':
            for role in targets:
                socketio.emit('broadcast_message', data, room=f'role_{role}')
                sent_count += _count_users_in_room(f'role_{role}')
        
        elif target_type == 'user':
            for user_id in targets:
                socketio.emit('broadcast_message', data, room=f'user_{user_id}')
                if _is_user_connected(user_id):
                    sent_count += 1
        
        return sent_count
        
    except Exception as e:
        logger.error(f"Error enviando broadcast: {str(e)}")
        return 0


def _log_user_activity(user: User, activity_type: ActivityType, description: str):
    """Registra actividad del usuario en la base de datos"""
    try:
        from app import db
        
        activity = ActivityLog(
            user_id=user.id,
            activity_type=activity_type,
            description=description,
            ip_address=request.environ.get('REMOTE_ADDR'),
            user_agent=request.environ.get('HTTP_USER_AGENT'),
            session_id=request.sid
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except SQLAlchemyError as e:
        logger.error(f"Error registrando actividad en BD: {str(e)}")
    except Exception as e:
        logger.error(f"Error en log de actividad: {str(e)}")


def _get_active_users() -> List[str]:
    """Obtiene lista de usuarios activos"""
    active_users = cache_get('active_users')
    return list(active_users) if active_users else []


def _find_user_by_session(session_id: str) -> Optional[User]:
    """Encuentra usuario por session_id"""
    try:
        # Buscar en cache primero
        session_cache = cache_get(f'session_{session_id}')
        if session_cache:
            return User.query.get(session_cache['user_id'])
        return None
    except Exception:
        return None


def _cleanup_user_session(user: User, session_id: str):
    """Limpia datos de sesión del usuario"""
    try:
        # Remover de usuarios activos
        active_users = cache_get('active_users') or set()
        active_users.discard(str(user.id))
        cache_set('active_users', active_users, timeout=300)
        
        # Limpiar cache de sesión
        cache_delete(f'session_{session_id}')
        
        # Limpiar rate limits del usuario
        if str(user.id) in user_rate_limits:
            del user_rate_limits[str(user.id)]
        
    except Exception as e:
        logger.error(f"Error limpiando sesión de usuario: {str(e)}")


def _get_server_uptime() -> str:
    """Obtiene el tiempo de actividad del servidor"""
    try:
        uptime_start = cache_get('server_start_time')
        if uptime_start:
            uptime = datetime.utcnow() - uptime_start
            return str(uptime)
        return "Unknown"
    except Exception:
        return "Unknown"


def _get_memory_usage() -> float:
    """Obtiene el uso de memoria en MB"""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


def _get_cpu_usage() -> float:
    """Obtiene el uso de CPU en porcentaje"""
    try:
        import psutil
        return psutil.cpu_percent(interval=1)
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


def _calculate_events_per_second() -> float:
    """Calcula eventos por segundo"""
    try:
        total_events = sum(event_stats.values())
        uptime_seconds = _get_uptime_seconds()
        return total_events / max(1, uptime_seconds)
    except Exception:
        return 0.0


def _calculate_error_rate() -> float:
    """Calcula la tasa de errores"""
    try:
        total_errors = sum(len(errors) for errors in error_stats.values())
        total_events = sum(event_stats.values())
        return (total_errors / max(1, total_events)) * 100
    except Exception:
        return 0.0


def _get_namespace_usage() -> Dict[str, int]:
    """Obtiene uso por namespace"""
    # Implementar lógica para contar conexiones por namespace
    return {
        '/': connection_stats['current_connections'],
        '/chat': 0,  # Implementar conteo real
        '/notifications': 0,
        '/presence': 0
    }


def _count_users_in_room(room: str) -> int:
    """Cuenta usuarios en una sala específica"""
    # Implementar conteo real de usuarios en sala
    return 0


def _is_user_connected(user_id: str) -> bool:
    """Verifica si un usuario específico está conectado"""
    active_users = _get_active_users()
    return user_id in active_users


def _group_errors_by_type(errors: List[Dict]) -> Dict[str, int]:
    """Agrupa errores por tipo"""
    error_counts = defaultdict(int)
    for error in errors:
        error_type = error.get('type', 'unknown')
        error_counts[error_type] += 1
    return dict(error_counts)


def _get_uptime_seconds() -> int:
    """Obtiene segundos de uptime del servidor"""
    try:
        start_time = cache_get('server_start_time')
        if start_time:
            return int((datetime.utcnow() - start_time).total_seconds())
        return 0
    except Exception:
        return 0


# Inicialización del módulo
def initialize_events():
    """Inicializa el sistema de eventos"""
    try:
        # Establecer tiempo de inicio del servidor
        cache_set('server_start_time', datetime.utcnow(), timeout=None)
        
        # Configurar middlewares globales
        event_registry.add_middleware(_auth_middleware)
        event_registry.add_middleware(_rate_limit_middleware)
        event_registry.add_middleware(_logging_middleware)
        
        # Configurar handlers globales
        event_registry.add_global_handler('*', _metrics_handler)
        event_registry.add_global_handler('error', _error_handler)
        
        logger.info("Sistema de eventos WebSocket inicializado correctamente")
        
    except Exception as e:
        logger.error(f"Error inicializando sistema de eventos: {str(e)}")
        raise


def _auth_middleware(event_name: str, args: tuple, kwargs: dict) -> bool:
    """Middleware de autenticación"""
    # Eventos que no requieren autenticación
    public_events = ['connect', 'ping', 'heartbeat']
    
    if event_name in public_events:
        return True
    
    # Verificar si hay usuario autenticado
    current_user = kwargs.get('current_user')
    if not current_user:
        emit('auth_error', {'message': 'Authentication required'})
        return False
    
    return True


def _rate_limit_middleware(event_name: str, args: tuple, kwargs: dict) -> bool:
    """Middleware de rate limiting"""
    current_user = kwargs.get('current_user')
    if not current_user:
        return True  # Skip rate limiting para usuarios no autenticados
    
    user_id = str(current_user.id)
    
    if not check_rate_limit(event_name, user_id):
        emit('rate_limit_error', {
            'event': event_name,
            'message': 'Rate limit exceeded'
        })
        return False
    
    return True


def _logging_middleware(event_name: str, args: tuple, kwargs: dict) -> bool:
    """Middleware de logging"""
    current_user = kwargs.get('current_user')
    user_info = current_user.username if current_user else 'Anónimo'
    
    logger.debug(f"Evento '{event_name}' ejecutado por {user_info}")
    return True


def _metrics_handler(event_name: str, args: tuple, kwargs: dict, result: Any):
    """Handler global para métricas"""
    event_stats[event_name] += 1
    event_stats['total'] += 1


def _error_handler(event_name: str, args: tuple, kwargs: dict, result: Any):
    """Handler global para errores"""
    if event_name.startswith('error') or 'error' in event_name:
        error_info = {
            'event': event_name,
            'timestamp': datetime.utcnow(),
            'user': kwargs.get('current_user').username if kwargs.get('current_user') else None,
            'args': str(args),
            'kwargs': str(kwargs)
        }
        
        error_stats['general'].append(error_info)
        
        # Limitar tamaño de la lista de errores
        if len(error_stats['general']) > 1000:
            error_stats['general'] = error_stats['general'][-500:]


# Exportar funciones y clases principales
__all__ = [
    'event_registry',
    'socket_event',
    'require_auth',
    'check_rate_limit',
    'initialize_events',
    'EventRegistry',
    'handle_heartbeat',
    'handle_ping',
    'handle_get_server_status',
    'handle_subscribe_to_system_events',
    'handle_get_connection_info',
    'handle_broadcast_message',
    'handle_get_system_metrics',
    'handle_emergency_alert',
    'handle_maintenance_mode',
    'handle_user_activity_update',
    'handle_connect',
    'handle_disconnect'
]