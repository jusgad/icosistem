"""
Notification Namespace - Ecosistema de Emprendimiento
=====================================================

Este módulo maneja las notificaciones en tiempo real para los usuarios
del ecosistema, asegurando la entrega instantánea y la interacción.

Funcionalidades:
- Envío de notificaciones en tiempo real a usuarios específicos
- Marcado de notificaciones como leídas/no leídas
- Conteo de notificaciones no leídas
- Suscripción a tópicos de notificación
"""

import logging
from datetime import datetime
from typing import Optional, Any

from flask import request
from flask_socketio import emit, join_room, leave_room

from app.models.user import User
from app.models.notification import Notification # Asumiendo que existe este modelo
from app.services.notification_service import NotificationService # Asumiendo este servicio
from app.sockets import socket_manager # Usar la instancia global del __init__.py
from app.sockets.decorators import socket_auth_required, socket_log_activity, socket_validate_data
from app.sockets.namespaces import BaseNamespace # Heredar de BaseNamespace
from app.core.exceptions import SocketValidationError
from app.utils.formatters import format_datetime, format_user_info

logger = logging.getLogger(__name__)

class NotificationNamespace(BaseNamespace):
    """
    Namespace para la funcionalidad de Notificaciones en tiempo real.
    """

    def __init__(self, namespace=None):
        super().__init__(namespace or '/notifications')
        self.notification_service = NotificationService() # O inyectar si usas DI

    def _authorize_namespace_access(self, user: User) -> bool:
        """
        Autoriza el acceso al namespace de notificaciones.
        Todos los usuarios autenticados pueden acceder.
        """
        return user.is_active

    def on_connect(self, auth_data: Optional[Dict] = None):
        """
        Manejador para cuando un cliente se conecta al namespace de notificaciones.
        Llama al on_connect de BaseNamespace que maneja la autenticación.
        """
        super().on_connect(auth_data) # Llama al BaseNamespace.on_connect
        
        current_user = self._get_current_user() # Método de BaseNamespace
        if current_user:
            # Unir al usuario a su sala de notificaciones personal
            user_notification_room = f"user_notifications_{current_user.id}"
            join_room(user_notification_room)
            
            logger.info(f"Usuario {current_user.username} (ID: {current_user.id}) conectado al namespace de notificaciones y unido a la sala '{user_notification_room}'.")
            
            # Opcional: Enviar un conteo inicial de notificaciones no leídas
            try:
                unread_count = self.notification_service.get_unread_count(current_user.id)
                emit('unread_count_update', {'count': unread_count})
            except Exception as e:
                logger.error(f"Error obteniendo conteo de no leídas para {current_user.id}: {e}")

    def on_disconnect(self):
        """
        Manejador para cuando un cliente se desconecta del namespace de notificaciones.
        """
        current_user = self._get_current_user() # Método de BaseNamespace
        if current_user:
            user_notification_room = f"user_notifications_{current_user.id}"
            leave_room(user_notification_room)
            logger.info(f"Usuario {current_user.username} (ID: {current_user.id}) desconectado del namespace de notificaciones y salido de la sala '{user_notification_room}'.")
        
        super().on_disconnect() # Llama al BaseNamespace.on_disconnect

    @socket_auth_required()
    @socket_log_activity(ActivityType.NOTIFICATION_READ, "User marked notification as read")
    @socket_validate_data(required_fields=['notification_id'])
    def on_mark_notification_as_read(self, data: dict[str, Any], current_user: User):
        """
        Maneja el evento cuando un usuario marca una notificación como leída.
        
        Args:
            data (dict): {'notification_id': str}
            current_user (User): Usuario autenticado.
        """
        notification_id_str = data.get('notification_id')
        
        try:
            # Convertir a int o UUID según tu modelo Notification
            # Asumiendo que Notification.id es un entero
            notification_id = int(notification_id_str) 
        except ValueError:
            self._emit_error("ID de notificación inválido.", 'INVALID_NOTIFICATION_ID')
            return

        try:
            success = self.notification_service.mark_as_read(
                user_id=current_user.id,
                notification_id=notification_id
            )
            
            if success:
                emit('notification_read_ack', {
                    'notification_id': notification_id_str,
                    'status': 'success'
                })
                # Actualizar conteo de no leídas
                unread_count = self.notification_service.get_unread_count(current_user.id)
                emit('unread_count_update', {'count': unread_count})
                logger.info(f"Notificación {notification_id} marcada como leída por {current_user.username}.")
            else:
                self._emit_error("No se pudo marcar la notificación como leída.", 'MARK_READ_FAILED')
                
        except Exception as e:
            logger.error(f"Error marcando notificación {notification_id} como leída: {e}", exc_info=True)
            self._emit_error("Error procesando la solicitud.", 'PROCESSING_ERROR')

    @socket_auth_required()
    @socket_log_activity(ActivityType.NOTIFICATION_READ_ALL, "User marked all notifications as read")
    def on_mark_all_notifications_as_read(self, data: dict[str, Any], current_user: User):
        """
        Maneja el evento cuando un usuario marca todas sus notificaciones como leídas.
        
        Args:
            data (dict): Puede estar vacío o contener filtros.
            current_user (User): Usuario autenticado.
        """
        try:
            updated_count = self.notification_service.mark_all_as_read(current_user.id)
            
            emit('all_notifications_read_ack', {
                'updated_count': updated_count,
                'status': 'success'
            })
            # Actualizar conteo de no leídas
            emit('unread_count_update', {'count': 0})
            logger.info(f"{updated_count} notificaciones marcadas como leídas por {current_user.username}.")
            
        except Exception as e:
            logger.error(f"Error marcando todas las notificaciones como leídas para {current_user.username}: {e}", exc_info=True)
            self._emit_error("Error procesando la solicitud.", 'PROCESSING_ERROR')

    @socket_auth_required()
    def on_request_initial_notifications(self, data: dict[str, Any], current_user: User):
        """
        Maneja la solicitud del cliente para obtener un lote inicial de notificaciones.
        
        Args:
            data (dict): {'limit': int (opcional), 'offset': int (opcional)}
            current_user (User): Usuario autenticado.
        """
        limit = data.get('limit', 20)
        offset = data.get('offset', 0)
        
        try:
            notifications, total_unread = self.notification_service.get_user_notifications_paginated(
                user_id=current_user.id,
                limit=limit,
                offset=offset
            )
            
            # Formatear notificaciones para el cliente
            formatted_notifications = [
                {
                    'id': str(n.id),
                    'title': n.title,
                    'message': n.message,
                    'type': n.type.value if hasattr(n.type, 'value') else n.type,
                    'is_read': n.read_at is not None,
                    'created_at': format_datetime(n.created_at),
                    'data': n.data # Metadatos adicionales
                } for n in notifications
            ]
            
            emit('initial_notifications_data', {
                'notifications': formatted_notifications,
                'total_unread': total_unread,
                'limit': limit,
                'offset': offset
            })
            logger.debug(f"Enviadas notificaciones iniciales a {current_user.username}.")
            
        except Exception as e:
            logger.error(f"Error obteniendo notificaciones iniciales para {current_user.username}: {e}", exc_info=True)
            self._emit_error("Error obteniendo notificaciones.", 'FETCH_NOTIFICATIONS_ERROR')

# Esta función sería llamada desde NotificationService para enviar una nueva notificación
# a un usuario específico a través de WebSockets.
def send_realtime_notification(user_id: str, notification_payload: dict[str, Any]):
    """
    Envía una notificación en tiempo real a un usuario específico.
    Esta función es un helper que sería llamado por otros servicios.

    Args:
        user_id (str): ID del usuario destinatario.
        notification_payload (dict): Datos de la notificación.
    """
    if not socket_manager:
        logger.error("SocketManager no inicializado. No se puede enviar notificación en tiempo real.")
        return False
        
    room_name = f"user_notifications_{user_id}"
    
    # Usar el socket_manager para emitir al room específico del usuario
    # dentro del namespace '/notifications'
    success = socket_manager.emit_to_room(
        room=room_name,
        event='new_notification',
        data=notification_payload,
        namespace='/notifications'
    )
    
    if success:
        logger.info(f"Notificación en tiempo real enviada a usuario {user_id} en sala {room_name}.")
    else:
        logger.warning(f"No se pudo enviar notificación en tiempo real a usuario {user_id} en sala {room_name}.")
    
    return success

# Exportar el namespace para ser registrado en app.sockets.namespaces.py
# (si usas un sistema de registro centralizado como en el ejemplo de chat.py)
# notification_namespace = NotificationNamespace('/notifications')