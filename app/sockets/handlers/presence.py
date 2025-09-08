"""
Presence Namespace - Ecosistema de Emprendimiento
=================================================

Este módulo maneja la presencia en tiempo real de los usuarios,
permitiendo saber quién está online, away, busy, etc.

Funcionalidades:
- Actualización de estado de presencia (online, away, busy, offline)
- Difusión de cambios de estado a usuarios relevantes
- Consulta de estado de presencia de otros usuarios
- Integración con el estado de conexión/desconexión global
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any

from flask import request
from flask_socketio import emit, join_room, leave_room

from app.models.user import User
from app.sockets import socket_manager # Usar la instancia global del __init__.py
from app.sockets.decorators import socket_auth_required, socket_log_activity, socket_validate_data
from app.sockets.namespaces import BaseNamespace # Heredar de BaseNamespace
from app.core.exceptions import SocketValidationError
from app.utils.formatters import format_datetime, format_user_info

logger = logging.getLogger(__name__)

class PresenceNamespace(BaseNamespace):
    """
    Namespace para la funcionalidad de Presencia en tiempo real.
    """

    def __init__(self, namespace=None):
        super().__init__(namespace or '/presence')
        # No se necesita un servicio específico de presencia si usamos active_connections

    def _authorize_namespace_access(self, user: User) -> bool:
        """
        Autoriza el acceso al namespace de presencia.
        Todos los usuarios autenticados pueden acceder.
        """
        return user.is_active

    def on_connect(self, auth_data: Optional[Dict] = None):
        """
        Manejador para cuando un cliente se conecta al namespace de presencia.
        Llama al on_connect de BaseNamespace que maneja la autenticación.
        """
        super().on_connect(auth_data) # Llama al BaseNamespace.on_connect
        
        current_user = self._get_current_user() # Método de BaseNamespace
        if current_user:
            user_id_str = str(current_user.id)
            
            # Unir al usuario a su sala de presencia personal (para actualizaciones directas)
            user_presence_room = f"user_presence_{user_id_str}"
            join_room(user_presence_room)
            
            logger.info(f"Usuario {current_user.username} (ID: {user_id_str}) conectado al namespace de presencia y unido a sala '{user_presence_room}'.")

            # Asegurar que el estado de presencia inicial esté en active_connections
            if user_id_str in socket_manager.active_connections:
                if 'presence_status' not in socket_manager.active_connections[user_id_str]:
                    socket_manager.active_connections[user_id_str]['presence_status'] = 'online'
                    socket_manager.active_connections[user_id_str]['custom_status_message'] = ''
                
                # Emitir estado actual al usuario que se conecta
                emit('my_presence_status', {
                    'status': socket_manager.active_connections[user_id_str]['presence_status'],
                    'custom_message': socket_manager.active_connections[user_id_str]['custom_status_message']
                })
            else:
                # Esto no debería ocurrir si on_connect global funciona bien
                logger.warning(f"Usuario {user_id_str} conectado a /presence pero no en active_connections.")
                self._emit_error("Error de sincronización de conexión.", "SYNC_ERROR")
                disconnect()


    def on_disconnect(self):
        """
        Manejador para cuando un cliente se desconecta del namespace de presencia.
        La lógica principal de 'offline' se maneja en el disconnect global.
        Aquí solo limpiamos lo específico del namespace si es necesario.
        """
        current_user = self._get_current_user()
        if current_user:
            user_id_str = str(current_user.id)
            user_presence_room = f"user_presence_{user_id_str}"
            leave_room(user_presence_room)
            logger.info(f"Usuario {current_user.username} (ID: {user_id_str}) desconectado del namespace de presencia y salido de sala '{user_presence_room}'.")
        
        super().on_disconnect() # Llama al BaseNamespace.on_disconnect

    @socket_auth_required()
    @socket_log_activity(ActivityType.PRESENCE_UPDATE, "User updated presence status")
    @socket_validate_data(required_fields=['status'])
    def on_update_my_status(self, data: dict[str, Any], current_user: User):
        """
        Permite al usuario actualizar su estado de presencia detallado.
        
        Args:
            data (dict): {'status': str ('online', 'away', 'busy', 'dnd'), 
                          'custom_message': str (opcional)}
            current_user (User): Usuario autenticado.
        """
        new_status = data.get('status')
        custom_message = data.get('custom_message', '')

        valid_statuses = ['online', 'away', 'busy', 'dnd', 'offline'] # 'offline' manejado por disconnect global
        if new_status not in valid_statuses:
            self._emit_error(f"Estado '{new_status}' inválido. Válidos: {valid_statuses}", 'INVALID_STATUS')
            return

        user_id_str = str(current_user.id)

        if user_id_str not in socket_manager.active_connections:
            logger.warning(f"Intento de actualizar estado para usuario no conectado: {user_id_str}")
            self._emit_error("Usuario no conectado.", "NOT_CONNECTED")
            return
        
        try:
            # Actualizar estado en active_connections
            socket_manager.active_connections[user_id_str]['presence_status'] = new_status
            socket_manager.active_connections[user_id_str]['custom_status_message'] = custom_message
            socket_manager.active_connections[user_id_str]['last_activity'] = datetime.now(timezone.utc)

            payload = {
                'user_id': user_id_str,
                'username': current_user.username,
                'status': new_status,
                'custom_message': custom_message,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }

            # Emitir a la sala personal del usuario (para sus otras sesiones/dispositivos)
            emit('my_presence_status_updated', payload, room=f"user_presence_{user_id_str}")

            # Difundir el cambio de estado a otros usuarios relevantes
            # Esto podría ser a salas de proyectos, organización, o globalmente
            # Por ahora, un broadcast general (excluyendo al propio usuario)
            # En una app real, esto se segmentaría (ej. amigos, colegas)
            self.emit('user_presence_changed', payload, broadcast=True, include_self=False)
            
            logger.info(f"Usuario {current_user.username} actualizó estado a '{new_status}'.")

        except Exception as e:
            logger.error(f"Error actualizando estado de presencia para {user_id_str}: {e}", exc_info=True)
            self._emit_error("Error al actualizar estado.", 'UPDATE_STATUS_FAILED')

    @socket_auth_required()
    @socket_validate_data(required_fields=['user_ids'])
    def on_get_users_status(self, data: dict[str, Any], current_user: User):
        """
        Permite a un cliente solicitar el estado de presencia de una lista de usuarios.
        
        Args:
            data (dict): {'user_ids': list[str]}
            current_user (User): Usuario autenticado.
        """
        user_ids_to_query = data.get('user_ids')

        if not isinstance(user_ids_to_query, list):
            self._emit_error("user_ids debe ser una lista.", 'INVALID_USER_IDS_FORMAT')
            return
        
        if len(user_ids_to_query) > 50: # Limitar la cantidad de usuarios a consultar
            self._emit_error("Demasiados user_ids solicitados (máximo 50).", 'TOO_MANY_USER_IDS')
            return

        statuses = {}
        for user_id_str in user_ids_to_query:
            if user_id_str in socket_manager.active_connections:
                conn_data = socket_manager.active_connections[user_id_str]
                statuses[user_id_str] = {
                    'status': conn_data.get('presence_status', 'offline'), # Default a offline si no está el campo
                    'custom_message': conn_data.get('custom_status_message', ''),
                    'last_activity': format_datetime(conn_data.get('last_activity', datetime.min))
                }
            else:
                statuses[user_id_str] = {
                    'status': 'offline',
                    'custom_message': '',
                    'last_activity': None # O una fecha muy antigua
                }
        
        emit('users_status_data', {
            'statuses': statuses,
            'timestamp': format_datetime(datetime.now(timezone.utc))
        })

# Función helper que podría ser llamada desde otros servicios para emitir cambios de presencia
# si no se quiere depender directamente de la instancia del namespace.
def broadcast_user_presence_update(user_id: str, status: str, custom_message: str = ""):
    """
    Helper para difundir una actualización de presencia de un usuario.
    Esta función es útil si la lógica de cambio de estado ocurre fuera del namespace.
    """
    if not socket_manager:
        logger.error("SocketManager no inicializado. No se puede difundir presencia.")
        return

    user = User.query.get(user_id)
    if not user:
        logger.warning(f"Usuario {user_id} no encontrado para difundir presencia.")
        return

    payload = {
        'user_id': user_id,
        'username': user.username,
        'status': status,
        'custom_message': custom_message,
        'timestamp': format_datetime(datetime.now(timezone.utc))
    }
    
    # Emitir al namespace de presencia
    socket_manager.emit_to_room(
        room=None, # Broadcast
        event='user_presence_changed',
        data=payload,
        namespace='/presence',
        include_self=False # Asumiendo que el cambio se originó en el propio usuario
    )
    logger.info(f"Presencia de usuario {user_id} difundida: {status}")