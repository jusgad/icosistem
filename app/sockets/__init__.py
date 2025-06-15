"""
Sistema de WebSockets para Ecosistema de Emprendimiento
======================================================

Este módulo inicializa y configura el sistema completo de WebSockets
para la plataforma de emprendimiento, incluyendo namespaces específicos
para cada tipo de usuario y funcionalidades en tiempo real.

Funcionalidades principales:
- Chat en tiempo real entre usuarios
- Notificaciones instantáneas
- Presencia de usuarios online
- Actualizaciones de estado en tiempo real
- Colaboración en documentos
- Alertas del sistema

Arquitectura:
- Namespaces separados por tipo de usuario
- Middleware de autenticación y autorización
- Sistema de salas (rooms) para comunicaciones privadas
- Handlers especializados para cada funcionalidad
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from flask import request, current_app
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from werkzeug.exceptions import Unauthorized

from app.core.exceptions import (
    SocketAuthenticationError, 
    SocketAuthorizationError,
    SocketRoomError
)
from app.core.permissions import has_permission, UserRole
from app.models.user import User
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.utils.decorators import rate_limit

# Configuración del logger
logger = logging.getLogger(__name__)

# Instancia global de SocketIO (se inicializa en create_app)
socketio: Optional[SocketIO] = None

# Almacenamiento en memoria de conexiones activas
active_connections: Dict[str, Dict[str, Any]] = {}
user_rooms: Dict[str, List[str]] = {}
room_users: Dict[str, List[str]] = {}


class SocketManager:
    """
    Gestor principal del sistema de WebSockets
    
    Centraliza la lógica de conexiones, salas, autenticación
    y comunicación entre diferentes componentes del sistema.
    """
    
    def __init__(self, socketio_instance: SocketIO):
        self.socketio = socketio_instance
        self.notification_service = NotificationService()
        
    def emit_to_user(self, user_id: str, event: str, data: Any, namespace: str = '/') -> bool:
        """
        Emite un evento a un usuario específico
        
        Args:
            user_id: ID del usuario destinatario
            event: Nombre del evento
            data: Datos a enviar
            namespace: Namespace del socket
            
        Returns:
            bool: True si se envió exitosamente
        """
        try:
            if user_id in active_connections:
                user_connection = active_connections[user_id]
                self.socketio.emit(
                    event, 
                    data, 
                    room=user_connection['session_id'],
                    namespace=namespace
                )
                logger.info(f"Evento '{event}' enviado a usuario {user_id}")
                return True
            else:
                logger.warning(f"Usuario {user_id} no está conectado")
                return False
        except Exception as e:
            logger.error(f"Error enviando evento a usuario {user_id}: {str(e)}")
            return False
    
    def emit_to_role(self, role: UserRole, event: str, data: Any, namespace: str = '/') -> int:
        """
        Emite un evento a todos los usuarios de un rol específico
        
        Args:
            role: Rol de usuario
            event: Nombre del evento
            data: Datos a enviar
            namespace: Namespace del socket
            
        Returns:
            int: Número de usuarios que recibieron el evento
        """
        count = 0
        try:
            for user_id, connection in active_connections.items():
                if connection.get('role') == role.value:
                    if self.emit_to_user(user_id, event, data, namespace):
                        count += 1
            logger.info(f"Evento '{event}' enviado a {count} usuarios con rol {role.value}")
            return count
        except Exception as e:
            logger.error(f"Error enviando evento a rol {role.value}: {str(e)}")
            return count
    
    def emit_to_room(self, room: str, event: str, data: Any, namespace: str = '/') -> bool:
        """
        Emite un evento a todos los usuarios en una sala
        
        Args:
            room: Nombre de la sala
            event: Nombre del evento
            data: Datos a enviar
            namespace: Namespace del socket
            
        Returns:
            bool: True si se envió exitosamente
        """
        try:
            self.socketio.emit(event, data, room=room, namespace=namespace)
            logger.info(f"Evento '{event}' enviado a sala '{room}'")
            return True
        except Exception as e:
            logger.error(f"Error enviando evento a sala {room}: {str(e)}")
            return False
    
    def join_user_room(self, user_id: str, room: str, namespace: str = '/') -> bool:
        """
        Une un usuario a una sala específica
        
        Args:
            user_id: ID del usuario
            room: Nombre de la sala
            namespace: Namespace del socket
            
        Returns:
            bool: True si se unió exitosamente
        """
        try:
            if user_id in active_connections:
                join_room(room, namespace=namespace)
                
                # Actualizar registro de salas
                if user_id not in user_rooms:
                    user_rooms[user_id] = []
                if room not in user_rooms[user_id]:
                    user_rooms[user_id].append(room)
                
                if room not in room_users:
                    room_users[room] = []
                if user_id not in room_users[room]:
                    room_users[room].append(user_id)
                
                logger.info(f"Usuario {user_id} se unió a sala '{room}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Error uniendo usuario {user_id} a sala {room}: {str(e)}")
            return False
    
    def leave_user_room(self, user_id: str, room: str, namespace: str = '/') -> bool:
        """
        Remueve un usuario de una sala específica
        
        Args:
            user_id: ID del usuario
            room: Nombre de la sala
            namespace: Namespace del socket
            
        Returns:
            bool: True si se removió exitosamente
        """
        try:
            if user_id in active_connections:
                leave_room(room, namespace=namespace)
                
                # Actualizar registro de salas
                if user_id in user_rooms and room in user_rooms[user_id]:
                    user_rooms[user_id].remove(room)
                
                if room in room_users and user_id in room_users[room]:
                    room_users[room].remove(user_id)
                    
                    # Limpiar sala vacía
                    if not room_users[room]:
                        del room_users[room]
                
                logger.info(f"Usuario {user_id} dejó sala '{room}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removiendo usuario {user_id} de sala {room}: {str(e)}")
            return False
    
    def get_room_users(self, room: str) -> List[str]:
        """
        Obtiene la lista de usuarios en una sala
        
        Args:
            room: Nombre de la sala
            
        Returns:
            List[str]: Lista de IDs de usuarios
        """
        return room_users.get(room, [])
    
    def get_user_rooms(self, user_id: str) -> List[str]:
        """
        Obtiene la lista de salas de un usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            List[str]: Lista de nombres de salas
        """
        return user_rooms.get(user_id, [])
    
    def is_user_online(self, user_id: str) -> bool:
        """
        Verifica si un usuario está conectado
        
        Args:
            user_id: ID del usuario
            
        Returns:
            bool: True si está conectado
        """
        return user_id in active_connections
    
    def get_online_users(self, role: Optional[UserRole] = None) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de usuarios conectados
        
        Args:
            role: Filtrar por rol específico (opcional)
            
        Returns:
            List[Dict]: Lista de usuarios conectados con su información
        """
        users = []
        for user_id, connection in active_connections.items():
            if role is None or connection.get('role') == role.value:
                users.append({
                    'user_id': user_id,
                    'username': connection.get('username'),
                    'role': connection.get('role'),
                    'connected_at': connection.get('connected_at'),
                    'last_activity': connection.get('last_activity')
                })
        return users


# Instancia global del gestor
socket_manager: Optional[SocketManager] = None


def init_socketio(app=None, **kwargs) -> SocketIO:
    """
    Inicializa SocketIO con la aplicación Flask
    
    Args:
        app: Instancia de Flask
        **kwargs: Argumentos adicionales para SocketIO
        
    Returns:
        SocketIO: Instancia configurada de SocketIO
    """
    global socketio, socket_manager
    
    # Configuración por defecto
    default_config = {
        'cors_allowed_origins': "*",
        'async_mode': 'threading',
        'logger': True,
        'engineio_logger': False,
        'ping_timeout': 60,
        'ping_interval': 25,
        'max_http_buffer_size': 1000000
    }
    
    # Combinar configuración
    config = {**default_config, **kwargs}
    
    # Crear instancia de SocketIO
    socketio = SocketIO(**config)
    
    if app is not None:
        socketio.init_app(app)
    
    # Inicializar gestor
    socket_manager = SocketManager(socketio)
    
    # Registrar eventos globales
    register_global_events()
    
    # Registrar namespaces
    register_namespaces()
    
    logger.info("Sistema de WebSockets inicializado correctamente")
    return socketio


def socket_auth_required(f: Callable) -> Callable:
    """
    Decorador para autenticación en WebSockets
    
    Verifica que el usuario esté autenticado antes de
    permitir el acceso a eventos de socket.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verificar token JWT en las cabeceras
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            
            if not current_user_id:
                logger.warning("Intento de conexión sin usuario autenticado")
                emit('error', {'message': 'Authentication required'})
                disconnect()
                return
            
            # Verificar que el usuario existe y está activo
            user = User.query.get(current_user_id)
            if not user or not user.is_active:
                logger.warning(f"Usuario inactivo o no encontrado: {current_user_id}")
                emit('error', {'message': 'User not found or inactive'})
                disconnect()
                return
            
            # Agregar usuario al contexto
            kwargs['current_user'] = user
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error en autenticación de socket: {str(e)}")
            emit('error', {'message': 'Authentication failed'})
            disconnect()
    
    return decorated_function


def socket_permission_required(permission: str):
    """
    Decorador para autorización basada en permisos
    
    Args:
        permission: Permiso requerido
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                emit('error', {'message': 'User not authenticated'})
                disconnect()
                return
            
            if not has_permission(current_user, permission):
                logger.warning(f"Usuario {current_user.id} sin permiso {permission}")
                emit('error', {'message': 'Insufficient permissions'})
                return
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@rate_limit(rate=10, per=60)  # 10 eventos por minuto
def register_global_events():
    """
    Registra eventos globales del sistema de WebSockets
    """
    
    @socketio.on('connect')
    @socket_auth_required
    def handle_connect(current_user=None):
        """Maneja conexiones de usuarios"""
        try:
            user_id = str(current_user.id)
            session_id = request.sid
            
            # Registrar conexión
            active_connections[user_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'username': current_user.username,
                'role': current_user.role.value,
                'connected_at': current_app.utc_now(),
                'last_activity': current_app.utc_now()
            }
            
            # Unirse a sala personal
            join_room(f"user_{user_id}")
            
            # Unirse a sala de rol
            join_room(f"role_{current_user.role.value}")
            
            # Emitir estado de conexión
            emit('connected', {
                'user_id': user_id,
                'username': current_user.username,
                'role': current_user.role.value,
                'timestamp': current_app.utc_now().isoformat()
            })
            
            # Notificar a otros usuarios relevantes
            socket_manager.emit_to_role(
                current_user.role,
                'user_online',
                {
                    'user_id': user_id,
                    'username': current_user.username,
                    'timestamp': current_app.utc_now().isoformat()
                }
            )
            
            logger.info(f"Usuario {current_user.username} ({user_id}) conectado")
            
        except Exception as e:
            logger.error(f"Error en conexión: {str(e)}")
            emit('error', {'message': 'Connection failed'})
            disconnect()
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Maneja desconexiones de usuarios"""
        try:
            session_id = request.sid
            user_id = None
            
            # Encontrar usuario por session_id
            for uid, connection in active_connections.items():
                if connection['session_id'] == session_id:
                    user_id = uid
                    break
            
            if user_id:
                user_info = active_connections[user_id]
                
                # Limpiar salas del usuario
                user_room_list = user_rooms.get(user_id, [])
                for room in user_room_list:
                    socket_manager.leave_user_room(user_id, room)
                
                # Notificar desconexión
                socket_manager.emit_to_role(
                    UserRole(user_info['role']),
                    'user_offline',
                    {
                        'user_id': user_id,
                        'username': user_info['username'],
                        'timestamp': current_app.utc_now().isoformat()
                    }
                )
                
                # Remover de conexiones activas
                del active_connections[user_id]
                if user_id in user_rooms:
                    del user_rooms[user_id]
                
                logger.info(f"Usuario {user_info['username']} ({user_id}) desconectado")
            
        except Exception as e:
            logger.error(f"Error en desconexión: {str(e)}")
    
    @socketio.on('ping')
    @socket_auth_required
    def handle_ping(current_user=None):
        """Maneja ping para mantener conexión activa"""
        user_id = str(current_user.id)
        if user_id in active_connections:
            active_connections[user_id]['last_activity'] = current_app.utc_now()
            emit('pong', {'timestamp': current_app.utc_now().isoformat()})
    
    @socketio.on('join_room')
    @socket_auth_required
    def handle_join_room(data, current_user=None):
        """Permite a usuarios unirse a salas específicas"""
        try:
            room_name = data.get('room')
            if not room_name:
                emit('error', {'message': 'Room name required'})
                return
            
            user_id = str(current_user.id)
            
            # Validar acceso a la sala
            if not _validate_room_access(current_user, room_name):
                emit('error', {'message': 'Access denied to room'})
                return
            
            # Unirse a la sala
            if socket_manager.join_user_room(user_id, room_name):
                emit('joined_room', {
                    'room': room_name,
                    'user_count': len(socket_manager.get_room_users(room_name)),
                    'timestamp': current_app.utc_now().isoformat()
                })
                
                # Notificar a otros en la sala
                socket_manager.emit_to_room(
                    room_name,
                    'user_joined_room',
                    {
                        'user_id': user_id,
                        'username': current_user.username,
                        'room': room_name,
                        'timestamp': current_app.utc_now().isoformat()
                    }
                )
            else:
                emit('error', {'message': 'Failed to join room'})
                
        except Exception as e:
            logger.error(f"Error uniendo a sala: {str(e)}")
            emit('error', {'message': 'Failed to join room'})
    
    @socketio.on('leave_room')
    @socket_auth_required
    def handle_leave_room(data, current_user=None):
        """Permite a usuarios dejar salas específicas"""
        try:
            room_name = data.get('room')
            if not room_name:
                emit('error', {'message': 'Room name required'})
                return
            
            user_id = str(current_user.id)
            
            if socket_manager.leave_user_room(user_id, room_name):
                emit('left_room', {
                    'room': room_name,
                    'timestamp': current_app.utc_now().isoformat()
                })
                
                # Notificar a otros en la sala
                socket_manager.emit_to_room(
                    room_name,
                    'user_left_room',
                    {
                        'user_id': user_id,
                        'username': current_user.username,
                        'room': room_name,
                        'timestamp': current_app.utc_now().isoformat()
                    }
                )
            else:
                emit('error', {'message': 'Failed to leave room'})
                
        except Exception as e:
            logger.error(f"Error dejando sala: {str(e)}")
            emit('error', {'message': 'Failed to leave room'})


def register_namespaces():
    """
    Registra namespaces específicos para diferentes funcionalidades
    """
    # Importar handlers después de la inicialización para evitar imports circulares
    from .handlers.chat import ChatNamespace
    from .handlers.notifications import NotificationNamespace
    from .handlers.presence import PresenceNamespace
    
    # Registrar namespaces
    socketio.on_namespace(ChatNamespace('/chat'))
    socketio.on_namespace(NotificationNamespace('/notifications'))
    socketio.on_namespace(PresenceNamespace('/presence'))
    
    logger.info("Namespaces de WebSockets registrados")


def _validate_room_access(user: User, room_name: str) -> bool:
    """
    Valida si un usuario tiene acceso a una sala específica
    
    Args:
        user: Usuario que solicita acceso
        room_name: Nombre de la sala
        
    Returns:
        bool: True si tiene acceso
    """
    try:
        # Salas públicas (acceso general)
        public_rooms = ['general', 'announcements']
        if room_name in public_rooms:
            return True
        
        # Salas por rol
        if room_name.startswith('role_'):
            role_name = room_name.replace('role_', '')
            return user.role.value == role_name
        
        # Salas de usuario personal
        if room_name.startswith('user_'):
            user_id = room_name.replace('user_', '')
            return str(user.id) == user_id
        
        # Salas de proyecto (solo emprendedores y mentores asignados)
        if room_name.startswith('project_'):
            project_id = room_name.replace('project_', '')
            # Aquí validarías si el usuario tiene acceso al proyecto específico
            # Implementar lógica según modelo de negocio
            return True
        
        # Salas de mentoría (solo participantes)
        if room_name.startswith('mentorship_'):
            session_id = room_name.replace('mentorship_', '')
            # Validar acceso a sesión de mentoría
            return True
        
        # Por defecto, denegar acceso
        return False
        
    except Exception as e:
        logger.error(f"Error validando acceso a sala {room_name}: {str(e)}")
        return False


# Funciones de utilidad para uso externo

def emit_notification(user_id: str, notification_data: Dict[str, Any]) -> bool:
    """
    Emite una notificación a un usuario específico
    
    Args:
        user_id: ID del usuario destinatario
        notification_data: Datos de la notificación
        
    Returns:
        bool: True si se envió exitosamente
    """
    if socket_manager:
        return socket_manager.emit_to_user(
            user_id, 
            'notification', 
            notification_data, 
            namespace='/notifications'
        )
    return False


def emit_system_alert(message: str, alert_type: str = 'info', roles: List[UserRole] = None) -> int:
    """
    Emite una alerta del sistema a usuarios específicos
    
    Args:
        message: Mensaje de la alerta
        alert_type: Tipo de alerta (info, warning, error)
        roles: Lista de roles que deben recibir la alerta
        
    Returns:
        int: Número de usuarios que recibieron la alerta
    """
    if not socket_manager:
        return 0
    
    alert_data = {
        'message': message,
        'type': alert_type,
        'timestamp': current_app.utc_now().isoformat()
    }
    
    total_sent = 0
    
    if roles:
        for role in roles:
            total_sent += socket_manager.emit_to_role(role, 'system_alert', alert_data)
    else:
        # Enviar a todos los usuarios conectados
        for user_id in active_connections.keys():
            if socket_manager.emit_to_user(user_id, 'system_alert', alert_data):
                total_sent += 1
    
    return total_sent


def get_socket_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas del sistema de WebSockets
    
    Returns:
        Dict: Estadísticas del sistema
    """
    return {
        'total_connections': len(active_connections),
        'active_rooms': len(room_users),
        'connections_by_role': _get_connections_by_role(),
        'uptime': current_app.utc_now().isoformat() if current_app else None
    }


def _get_connections_by_role() -> Dict[str, int]:
    """Obtiene el conteo de conexiones por rol"""
    role_counts = {}
    for connection in active_connections.values():
        role = connection.get('role', 'unknown')
        role_counts[role] = role_counts.get(role, 0) + 1
    return role_counts


# Exportar instancias y funciones principales
__all__ = [
    'socketio',
    'socket_manager',
    'init_socketio',
    'socket_auth_required',
    'socket_permission_required',
    'emit_notification',
    'emit_system_alert',
    'get_socket_stats',
    'SocketManager'
]