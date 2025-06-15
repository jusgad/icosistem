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
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from flask_socketio import SocketIO
from flask import current_app

# Configuración del logger
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Almacenamiento en memoria de conexiones y salas
# Estas variables serán accesibles por otros módulos del paquete 'sockets'
# --------------------------------------------------------------------------

# active_connections: Dict[str(user_id), Dict[str, Any]]
# Ejemplo: {'123': {'session_id': 'abc', 'username': 'user1', 'role': 'entrepreneur', ...}}
active_connections: Dict[str, Dict[str, Any]] = {}

# user_rooms: Dict[str(user_id), List[str(room_name)]]
# Ejemplo: {'123': ['user_123', 'project_456', 'role_entrepreneur']}
user_rooms: Dict[str, List[str]] = {}

# room_users: Dict[str(room_name), Set[str(user_id)]]
# Ejemplo: {'project_456': {'123', '789'}}
room_users: Dict[str, Set[str]] = {}


# --------------------------------------------------------------------------
# Instancia de SocketIO
# Esta instancia será importada y configurada en app.extensions y app.__init__
# --------------------------------------------------------------------------
socketio = SocketIO()


# --------------------------------------------------------------------------
# SocketManager (Opcional, pero recomendado para centralizar lógica)
# Si no usas un SocketManager, puedes mover esta lógica a funciones
# o directamente en los handlers.
# --------------------------------------------------------------------------
class SocketManager:
    """
    Gestor principal del sistema de WebSockets.
    Centraliza la lógica de conexiones, salas, y emisión de eventos.
    """
    def __init__(self, sio_instance: SocketIO):
        self.sio = sio_instance
        # Referencias a las variables globales para claridad, aunque se acceden directamente
        self.active_connections = active_connections
        self.user_rooms = user_rooms
        self.room_users = room_users

    def add_user_connection(self, user_id: str, session_id: str, user_info: Dict[str, Any]):
        """Registra una nueva conexión de usuario."""
        self.active_connections[user_id] = {
            'session_id': session_id,
            'user_id': user_id,
            **user_info, # username, role, etc.
            'connected_at': datetime.utcnow(),
            'last_activity': datetime.utcnow()
        }
        logger.info(f"Usuario conectado: ID {user_id}, SID {session_id}, Info: {user_info.get('username', 'N/A')}")

    def remove_user_connection(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Remueve una conexión de usuario por session_id."""
        user_id_to_remove = None
        user_info_removed = None
        for uid, conn_data in list(self.active_connections.items()): # Iterar sobre una copia
            if conn_data['session_id'] == session_id:
                user_id_to_remove = uid
                user_info_removed = conn_data
                del self.active_connections[uid]
                break
        
        if user_id_to_remove:
            # Limpiar salas del usuario
            rooms_left = []
            if user_id_to_remove in self.user_rooms:
                for room_name in list(self.user_rooms[user_id_to_remove]): # Iterar sobre una copia
                    self.leave_room_for_user(user_id_to_remove, room_name, session_id)
                    rooms_left.append(room_name)
                del self.user_rooms[user_id_to_remove]
            logger.info(f"Usuario desconectado: ID {user_id_to_remove}, SID {session_id}. Salió de salas: {rooms_left}")
            return user_info_removed
        logger.warning(f"Intento de desconectar SID no rastreado: {session_id}")
        return None

    def join_room_for_user(self, user_id: str, room_name: str, session_id: str):
        """Añade un usuario a una sala."""
        from flask_socketio import join_room # Importación local para el contexto de SocketIO
        join_room(room_name, sid=session_id) # Especificar sid es importante
        
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = []
        if room_name not in self.user_rooms[user_id]:
            self.user_rooms[user_id].append(room_name)

        if room_name not in self.room_users:
            self.room_users[room_name] = set()
        self.room_users[room_name].add(user_id)
        logger.debug(f"Usuario {user_id} (SID: {session_id}) unido a sala '{room_name}'")

    def leave_room_for_user(self, user_id: str, room_name: str, session_id: str):
        """Remueve un usuario de una sala."""
        from flask_socketio import leave_room # Importación local
        leave_room(room_name, sid=session_id)

        if user_id in self.user_rooms and room_name in self.user_rooms[user_id]:
            self.user_rooms[user_id].remove(room_name)
            if not self.user_rooms[user_id]: # Si el usuario no está en más salas
                del self.user_rooms[user_id]

        if room_name in self.room_users and user_id in self.room_users[room_name]:
            self.room_users[room_name].remove(user_id)
            if not self.room_users[room_name]: # Si la sala queda vacía
                del self.room_users[room_name]
        logger.debug(f"Usuario {user_id} (SID: {session_id}) salió de sala '{room_name}'")

    def emit_to_user(self, user_id: str, event: str, data: Any, namespace: Optional[str] = None) -> bool:
        """Emite un evento a un usuario específico si está conectado."""
        if user_id in self.active_connections:
            sid = self.active_connections[user_id]['session_id']
            self.sio.emit(event, data, room=sid, namespace=namespace)
            return True
        return False

    def emit_to_room(self, room_name: str, event: str, data: Any, namespace: Optional[str] = None, include_self: bool = True):
        """Emite un evento a todos los usuarios en una sala."""
        self.sio.emit(event, data, room=room_name, namespace=namespace, include_self=include_self)

    def get_user_by_sid(self, sid: str) -> Optional[Dict[str, Any]]:
        """Obtiene la información del usuario conectado con un SID específico."""
        for user_id, conn_data in self.active_connections.items():
            if conn_data['session_id'] == sid:
                return conn_data
        return None

# Instancia global del gestor de sockets
# Se inicializará en register_socketio_events
socket_manager: Optional[SocketManager] = None

# --------------------------------------------------------------------------
# Función de Registro de Eventos (llamada desde app/__init__.py)
# --------------------------------------------------------------------------
def register_socketio_events(sio: SocketIO):
    """
    Registra todos los manejadores de eventos y namespaces de Socket.IO.
    Esta función es llamada desde la factory de la aplicación (`create_app`).

    Args:
        sio (SocketIO): La instancia de SocketIO configurada.
    """
    global socket_manager
    if not socket_manager:
        socket_manager = SocketManager(sio)

    # Importar y registrar middleware global (manejador de errores, etc.)
    from . import middleware
    middleware.register_socketio_error_handler(sio)
    # Aquí podrías registrar otros hooks globales de middleware si los tienes.

    # Importar y registrar manejadores de eventos principales
    # (connect, disconnect, y otros eventos globales)
    from . import events
    events.register_event_handlers(sio, socket_manager)

    # Importar y registrar namespaces especializados
    from . import namespaces
    namespaces.register_all_namespaces(sio, socket_manager)

    logger.info("Manejadores de eventos y namespaces de Socket.IO registrados.")


# --------------------------------------------------------------------------
# Funciones de utilidad (opcional, podrían estar en un utils.py)
# --------------------------------------------------------------------------
def get_socketio_instance() -> SocketIO:
    """Retorna la instancia global de SocketIO."""
    if socketio is None:
        raise RuntimeError("SocketIO no ha sido inicializado. Asegúrate de llamar a init_socketio.")
    return socketio

def get_socket_manager() -> SocketManager:
    """Retorna la instancia global del SocketManager."""
    if socket_manager is None:
        raise RuntimeError("SocketManager no ha sido inicializado.")
    return socket_manager


# Exportar elementos principales del paquete
__all__ = [
    'socketio',
    'active_connections',
    'user_rooms',
    'room_users',
    'SocketManager',
    'socket_manager',
    'register_socketio_events',
    'get_socketio_instance',
    'get_socket_manager'
]

logger.info("Módulo app.sockets cargado.")