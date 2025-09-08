"""
Socket.IO Middleware - Ecosistema de Emprendimiento
==================================================

Este módulo proporciona middleware y utilidades para el sistema de WebSockets,
enfocado en manejo de errores global, gestión de conexiones y logging.
"""

import logging
from functools import wraps
from flask import request, g, current_app
from flask_socketio import emit, disconnect
from flask_jwt_extended import get_jwt_identity

from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.core.exceptions import SocketError, SocketAuthenticationError, SocketAuthorizationError

logger = logging.getLogger(__name__)

# Almacenamiento de conexiones activas (podría estar en __init__.py o aquí si se centraliza más)
# Asumiendo que active_connections y user_rooms están definidos en app.sockets.__init__
# from . import active_connections, user_rooms, room_users # Descomentar si se mueven aquí


def register_socketio_error_handler(socketio_instance):
    """
    Registra un manejador de errores global para Socket.IO.
    """
    @socketio_instance.on_error_default
    def default_error_handler(e):
        """
        Manejador de errores por defecto para todos los namespaces.
        """
        event_name = request.event.get('message') if request.event else 'unknown_event'
        namespace = request.event.get('namespace', '/') if request.event else '/'
        
        error_message = f"Error no manejado en evento '{event_name}' (namespace: {namespace}): {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # Intentar obtener el usuario actual si está disponible en el contexto del error
        user_id_str = get_jwt_identity() if 'jwt_identity' in g else None # Adaptar según cómo se maneje la identidad
        user_id = int(user_id_str) if user_id_str else None

        if user_id:
            user = User.query.get(user_id)
            username = user.username if user else "unknown_user"
        else:
            username = "anonymous"

        # Loguear la actividad de error
        try:
            ActivityLog.log_activity(
                activity_type=ActivityType.SYSTEM_ERROR,
                description=f"Socket.IO Error: {event_name} - {str(e)[:200]}",
                user_id=user_id,
                severity='high',
                metadata={
                    'event': event_name,
                    'namespace': namespace,
                    'error_type': type(e).__name__,
                    'error_details': str(e),
                    'sid': request.sid
                },
                ip_address=request.remote_addr
            )
        except Exception as log_exc:
            logger.error(f"Error al registrar la actividad de error de Socket.IO: {log_exc}")

        # Emitir un mensaje de error genérico al cliente
        # Es importante no exponer detalles sensibles del error al cliente
        client_error_payload = {
            'error': 'SERVER_ERROR',
            'message': 'Ocurrió un error inesperado en el servidor.',
            'event': event_name
        }
        
        # Solo emitir si la conexión sigue activa
        if request.sid:
            try:
                emit('server_error', client_error_payload)
            except Exception as emit_exc:
                logger.error(f"Error al emitir server_error al cliente {request.sid}: {emit_exc}")


def handle_socket_authenticated_connect(user: User, sid: str):
    """
    Lógica a ejecutar cuando un usuario autenticado se conecta.
    Esta función sería llamada por el decorador @socket_auth_required
    o directamente desde el handler on_connect global.

    Args:
        user: Objeto User del usuario conectado.
        sid: Session ID de Socket.IO.
    """
    from . import active_connections, user_rooms # Importar aquí para evitar circularidad
    
    logger.info(f"Usuario autenticado conectado: {user.username} (ID: {user.id}, SID: {sid})")

    # Registrar conexión activa
    active_connections[str(user.id)] = {
        'session_id': sid,
        'user_id': str(user.id),
        'username': user.username,
        'role': user.role.value if hasattr(user.role, 'value') else user.role, # Asegurar que role es un string
        'connected_at': datetime.now(timezone.utc),
        'last_activity': datetime.now(timezone.utc),
        'namespace': request.namespace or '/'
    }

    # Unir al usuario a su sala personal y a la sala de su rol
    personal_room = f"user_{user.id}"
    role_room = f"role_{user.role.value if hasattr(user.role, 'value') else user.role}"
    
    from flask_socketio import join_room # Importación local para el contexto de SocketIO
    join_room(personal_room)
    join_room(role_room)

    if str(user.id) not in user_rooms:
        user_rooms[str(user.id)] = []
    if personal_room not in user_rooms[str(user.id)]:
        user_rooms[str(user.id)].append(personal_room)
    if role_room not in user_rooms[str(user.id)]:
        user_rooms[str(user.id)].append(role_room)

    # Emitir evento de estado online a otros usuarios relevantes (ej. amigos, equipo)
    # Esta lógica dependerá de tu modelo de relaciones
    emit('user_status_change', {'user_id': str(user.id), 'status': 'online'}, broadcast=True, include_self=False)

    # Log de actividad
    try:
        ActivityLog.log_activity(
            activity_type=ActivityType.LOGIN, # O un tipo específico para conexión de socket
            description=f"Usuario {user.username} conectado vía WebSocket.",
            user_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
    except Exception as log_exc:
        logger.error(f"Error al registrar actividad de conexión de socket: {log_exc}")


def handle_socket_disconnect(sid: str):
    """
    Lógica a ejecutar cuando un usuario se desconecta.

    Args:
        sid: Session ID de Socket.IO.
    """
    from . import active_connections, user_rooms, room_users # Importar aquí
    
    user_id_disconnected = None
    user_info = None

    for user_id, conn_data in list(active_connections.items()):
        if conn_data['session_id'] == sid:
            user_id_disconnected = user_id
            user_info = conn_data
            del active_connections[user_id]
            break
    
    if user_id_disconnected and user_info:
        logger.info(f"Usuario desconectado: {user_info.get('username', 'N/A')} (ID: {user_id_disconnected}, SID: {sid})")

        # Remover de todas las salas
        if user_id_disconnected in user_rooms:
            for room_name in list(user_rooms[user_id_disconnected]): # Iterar sobre una copia
                from flask_socketio import leave_room # Importación local
                leave_room(room_name)
                if room_name in room_users and user_id_disconnected in room_users[room_name]:
                    room_users[room_name].remove(user_id_disconnected)
                    if not room_users[room_name]: # Si la sala queda vacía
                        del room_users[room_name]
            del user_rooms[user_id_disconnected]

        # Emitir evento de estado offline
        emit('user_status_change', {'user_id': user_id_disconnected, 'status': 'offline'}, broadcast=True, include_self=False)

        # Log de actividad
        try:
            ActivityLog.log_activity(
                activity_type=ActivityType.LOGOUT, # O un tipo específico para desconexión de socket
                description=f"Usuario {user_info.get('username', 'N/A')} desconectado de WebSocket.",
                user_id=int(user_id_disconnected), # Asegurar que es int
                ip_address=request.remote_addr if request else None, # Puede que request no esté disponible
                user_agent=request.headers.get("User-Agent") if request else None
            )
        except Exception as log_exc:
            logger.error(f"Error al registrar actividad de desconexión de socket: {log_exc}")
    else:
        logger.info(f"Desconexión de SID no rastreado: {sid}")


def log_socket_event(event_name: str, sid: str, user: Optional[User], data: Optional[dict] = None, error: Optional[Exception] = None):
    """
    Registra un evento de Socket.IO.

    Args:
        event_name: Nombre del evento.
        sid: Session ID de Socket.IO.
        user: Usuario que generó el evento (si está autenticado).
        data: Datos asociados al evento.
        error: Excepción si el evento resultó en un error.
    """
    log_level = logging.ERROR if error else logging.INFO
    user_info = f"User {user.username} (ID: {user.id})" if user else "AnonymousUser"
    
    message = f"Socket Event: '{event_name}' | SID: {sid} | User: {user_info}"
    if data:
        # Limitar el tamaño de los datos logueados para evitar logs muy grandes
        loggable_data = {k: (str(v)[:100] + '...' if isinstance(v, str) and len(v) > 100 else v) 
                         for k, v in data.items()}
        message += f" | Data: {loggable_data}"
    if error:
        message += f" | Error: {type(error).__name__} - {str(error)}"
    
    logger.log(log_level, message, exc_info=error if error else None)


def before_socket_request_hook(event_name: str, sid: str, data: Optional[dict]):
    """
    Hook para ejecutar antes de cada manejador de evento de Socket.IO.
    Podría usarse para logging, validación global, o configuración de contexto.
    """
    # Ejemplo: Configurar g.current_user_socket si no lo hace ya un decorador
    if not hasattr(g, 'current_user_socket'):
        g.current_user_socket = None # O intentar obtenerlo si es posible
        # user_id_str = get_jwt_identity() # Si el token se envía con cada evento
        # if user_id_str:
        #     g.current_user_socket = User.query.get(int(user_id_str))

    logger.debug(f"Before event '{event_name}' | SID: {sid} | User: {getattr(g, 'current_user_socket', 'N/A')}")
    # Aquí se podrían añadir más lógicas, como validaciones globales.


def after_socket_request_hook(event_name: str, sid: str, response: Optional[Any], exception: Optional[Exception]):
    """
    Hook para ejecutar después de cada manejador de evento de Socket.IO.
    Útil para logging de respuesta, limpieza de contexto, etc.
    """
    logger.debug(f"After event '{event_name}' | SID: {sid} | Response: {response is not None} | Exception: {exception is not None}")
    # Limpiar contexto si es necesario
    # if hasattr(g, 'current_user_socket'):
    #     del g.current_user_socket


# Exportar funciones principales del middleware
__all__ = [
    'register_socketio_error_handler',
    'handle_socket_authenticated_connect',
    'handle_socket_disconnect',
    'log_socket_event',
    'before_socket_request_hook',
    'after_socket_request_hook'
]