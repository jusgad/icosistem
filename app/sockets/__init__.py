# app/sockets/__init__.py

from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app.extensions import socketio
import logging
from .events import register_message_events, register_notification_events
from .namespaces import register_namespaces

logger = logging.getLogger(__name__)

def init_socketio():
    """
    Inicializa todas las funcionalidades de Socket.IO.
    Esta función registra todos los eventos y namespaces.
    """
    register_connection_events()
    register_message_events()
    register_notification_events()
    register_namespaces()
    
    logger.info("Socket.IO inicializado correctamente")
    return socketio

def register_connection_events():
    """
    Registra los eventos básicos de conexión de Socket.IO.
    """
    @socketio.on('connect')
    def handle_connect():
        """
        Maneja el evento de conexión.
        Cuando un usuario se conecta, se une a su sala personal.
        """
        if current_user.is_authenticated:
            # Unir al usuario a su sala personal
            user_room = f'user_{current_user.id}'
            join_room(user_room)
            
            # Unir al usuario a su sala de rol
            role_room = f'role_{current_user.role}'
            join_room(role_room)
            
            logger.info(f"Usuario {current_user.id} conectado y unido a salas {user_room} y {role_room}")
            
            # Emitir evento de conexión exitosa
            emit('connect_response', {'status': 'success', 'user_id': current_user.id})
            
            # Notificar al usuario que está conectado
            emit('status', {'status': 'online'}, room=user_room)
        else:
            # Emitir evento de error si el usuario no está autenticado
            emit('connect_response', {'status': 'error', 'message': 'No autenticado'})
            logger.warning("Intento de conexión sin autenticación")

    @socketio.on('disconnect')
    def handle_disconnect():
        """
        Maneja el evento de desconexión.
        Cuando un usuario se desconecta, se abandona su sala personal.
        """
        if current_user.is_authenticated:
            # Abandonar sala personal
            user_room = f'user_{current_user.id}'
            leave_room(user_room)
            
            # Abandonar sala de rol
            role_room = f'role_{current_user.role}'
            leave_room(role_room)
            
            logger.info(f"Usuario {current_user.id} desconectado y removido de salas {user_room} y {role_room}")
            
            # Notificar que el usuario está desconectado
            emit('status', {'status': 'offline'}, room=user_room)
        else:
            logger.info("Usuario no autenticado desconectado")

    @socketio.on('join')
    def handle_join(data):
        """
        Maneja el evento de unión a una sala.
        
        Args:
            data (dict): Diccionario con el campo 'room' que contiene el nombre de la sala
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        room = data.get('room')
        if not room:
            emit('error', {'message': 'Sala no especificada'})
            return
        
        # Verificar permisos para unirse a la sala
        if room.startswith('admin_') and current_user.role != 'admin':
            emit('error', {'message': 'No autorizado'})
            return
        
        join_room(room)
        logger.info(f"Usuario {current_user.id} unido a sala {room}")
        emit('joined', {'room': room})

    @socketio.on('leave')
    def handle_leave(data):
        """
        Maneja el evento de abandono de una sala.
        
        Args:
            data (dict): Diccionario con el campo 'room' que contiene el nombre de la sala
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        room = data.get('room')
        if not room:
            emit('error', {'message': 'Sala no especificada'})
            return
        
        leave_room(room)
        logger.info(f"Usuario {current_user.id} abandonó sala {room}")
        emit('left', {'room': room})

    @socketio.on_error()
    def error_handler(e):
        """
        Maneja errores en eventos de Socket.IO.
        
        Args:
            e (Exception): Excepción ocurrida
        """
        logger.error(f"Error en Socket.IO: {str(e)}")
        if current_user.is_authenticated:
            emit('error', {'message': 'Ocurrió un error en el servidor'}, room=f'user_{current_user.id}')