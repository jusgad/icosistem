"""
Chat Namespace - Ecosistema de Emprendimiento
=============================================

Este módulo maneja la comunicación en tiempo real para el chat
del ecosistema, incluyendo mensajes privados, grupales y de proyecto.

Funcionalidades:
- Envío y recepción de mensajes en tiempo real
- Gestión de salas de chat (privadas, grupales, por proyecto)
- Indicadores de escritura
- Notificaciones de mensajes no leídos
- Historial de chat
- Soporte para archivos adjuntos (básico)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from flask import request
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.user import User
from app.models.message import Message, MessageType, MessageThread
from app.models.project import Project # Asumiendo que existe un modelo Project
from app.services.user_service import UserService
from app.services.notification_service import NotificationService
from app.sockets import socket_manager # Usar la instancia global del __init__.py
from app.sockets.decorators import socket_auth_required, socket_log_activity, socket_validate_data
from app.sockets.namespaces import BaseNamespace # Heredar de BaseNamespace
from app.core.exceptions import SocketRoomError, SocketValidationError
from app.utils.validators import validate_message_content, validate_room_name
from app.utils.formatters import format_datetime, format_user_info

logger = logging.getLogger(__name__)

# Estructura para almacenar salas de chat activas y sus usuarios
# Esto podría moverse a app.sockets.__init__.py si se necesita acceso global
# o usar el socket_manager si ya tiene esta funcionalidad.
# Por ahora, lo mantenemos local al namespace para encapsulación.
active_chat_rooms: Dict[str, Set[str]] = {} # room_name -> set of user_ids

class ChatNamespace(BaseNamespace):
    """
    Namespace para la funcionalidad de Chat.
    Hereda de BaseNamespace para reutilizar la lógica de conexión/autenticación.
    """

    def __init__(self, namespace=None):
        super().__init__(namespace or '/chat')
        self.user_service = UserService() # Opcional, si se necesita lógica de usuario
        self.notification_service = NotificationService() # Para notificar mensajes

    def _authorize_namespace_access(self, user: User) -> bool:
        """
        Autoriza el acceso al namespace de chat.
        Todos los usuarios autenticados pueden acceder.
        """
        return user.is_active

    @socket_auth_required()
    @socket_log_activity(ActivityType.CHAT_JOIN_ROOM, "User joined chat room")
    @socket_validate_data(required_fields=['room_name'])
    def on_join_chat_room(self, data: Dict[str, Any], current_user: User):
        """
        Maneja la unión de un usuario a una sala de chat.
        
        Args:
            data (dict): {'room_name': str}
            current_user (User): Usuario autenticado.
        """
        room_name = data.get('room_name')

        if not validate_room_name(room_name):
            self._emit_error("Nombre de sala inválido.", 'INVALID_ROOM_NAME')
            return

        # Validar si el usuario tiene permiso para unirse a esta sala
        # Esta lógica dependerá de tu modelo de permisos para salas de chat
        # Ejemplo: salas de proyecto, salas de mentoría, etc.
        if not self._can_user_join_room(current_user, room_name):
            self._emit_error(f"No tienes permiso para unirte a la sala '{room_name}'.", 'ACCESS_DENIED')
            return

        try:
            join_room(room_name)
            user_id_str = str(current_user.id)

            if room_name not in active_chat_rooms:
                active_chat_rooms[room_name] = set()
            active_chat_rooms[room_name].add(user_id_str)

            # Notificar a otros en la sala
            self.emit('user_joined_chat', {
                'user': format_user_info(current_user),
                'room_name': room_name,
                'timestamp': format_datetime(datetime.utcnow())
            }, room=room_name, include_self=False)

            # Enviar confirmación al usuario
            emit('joined_chat_room_ack', {
                'room_name': room_name,
                'user_count': len(active_chat_rooms[room_name]),
                'message': f"Te has unido a la sala '{room_name}'."
            })
            logger.info(f"Usuario {current_user.username} se unió a la sala de chat '{room_name}'.")

        except Exception as e:
            logger.error(f"Error al unirse a la sala '{room_name}': {e}", exc_info=True)
            self._emit_error("Error al unirse a la sala.", 'JOIN_ROOM_FAILED')

    @socket_auth_required()
    @socket_log_activity(ActivityType.CHAT_LEAVE_ROOM, "User left chat room")
    @socket_validate_data(required_fields=['room_name'])
    def on_leave_chat_room(self, data: Dict[str, Any], current_user: User):
        """
        Maneja la salida de un usuario de una sala de chat.
        
        Args:
            data (dict): {'room_name': str}
            current_user (User): Usuario autenticado.
        """
        room_name = data.get('room_name')
        user_id_str = str(current_user.id)

        try:
            leave_room(room_name)

            if room_name in active_chat_rooms and user_id_str in active_chat_rooms[room_name]:
                active_chat_rooms[room_name].remove(user_id_str)
                if not active_chat_rooms[room_name]: # Si la sala queda vacía
                    del active_chat_rooms[room_name]

            # Notificar a otros en la sala
            self.emit('user_left_chat', {
                'user': format_user_info(current_user),
                'room_name': room_name,
                'timestamp': format_datetime(datetime.utcnow())
            }, room=room_name, include_self=False)

            # Enviar confirmación al usuario
            emit('left_chat_room_ack', {
                'room_name': room_name,
                'message': f"Has salido de la sala '{room_name}'."
            })
            logger.info(f"Usuario {current_user.username} salió de la sala de chat '{room_name}'.")

        except Exception as e:
            logger.error(f"Error al salir de la sala '{room_name}': {e}", exc_info=True)
            self._emit_error("Error al salir de la sala.", 'LEAVE_ROOM_FAILED')

    @socket_auth_required()
    @socket_log_activity(ActivityType.CHAT_MESSAGE_SENT, "User sent chat message")
    @socket_validate_data(required_fields=['room_name', 'content'])
    def on_send_chat_message(self, data: Dict[str, Any], current_user: User):
        """
        Maneja el envío de un mensaje de chat.
        
        Args:
            data (dict): {'room_name': str, 'content': str, 'message_type': str (opcional)}
            current_user (User): Usuario autenticado.
        """
        room_name = data.get('room_name')
        content = data.get('content')
        message_type_str = data.get('message_type', 'TEXT').upper() # Default a TEXT

        if not validate_message_content(content): # Validación básica de contenido
            self._emit_error("Contenido de mensaje inválido.", 'INVALID_CONTENT')
            return

        if not self._can_user_send_to_room(current_user, room_name):
            self._emit_error(f"No tienes permiso para enviar mensajes a la sala '{room_name}'.", 'SEND_PERMISSION_DENIED')
            return

        try:
            message_type = MessageType[message_type_str]
        except KeyError:
            self._emit_error(f"Tipo de mensaje '{message_type_str}' no válido.", 'INVALID_MESSAGE_TYPE')
            return

        try:
            # Guardar mensaje en la base de datos
            # Asumimos que existe un MessageThread o una forma de asociar mensajes a 'room_name'
            thread = self._get_or_create_thread_for_room(room_name, current_user)
            if not thread:
                self._emit_error("No se pudo encontrar o crear el hilo de chat.", 'THREAD_ERROR')
                return

            message = Message(
                thread_id=thread.id,
                sender_id=current_user.id,
                content=content, # Sanitizar antes de guardar si es necesario
                message_type=message_type,
                metadata=data.get('metadata', {})
            )
            db.session.add(message)
            db.session.commit()

            message_payload = {
                'id': str(message.id),
                'sender': format_user_info(current_user),
                'room_name': room_name,
                'content': message.content, # Enviar contenido sanitizado si se hizo
                'message_type': message.message_type.value,
                'timestamp': format_datetime(message.created_at),
                'metadata': message.metadata
            }

            # Emitir mensaje a todos en la sala
            self.emit('new_chat_message', message_payload, room=room_name)

            # Enviar notificaciones a usuarios offline o que no estén en la sala
            self._notify_room_participants(thread, message, current_user)

            logger.info(f"Mensaje de {current_user.username} en sala '{room_name}': {content[:50]}...")

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al enviar mensaje: {e}", exc_info=True)
            self._emit_error("Error al guardar el mensaje.", 'DB_ERROR')
        except Exception as e:
            logger.error(f"Error al enviar mensaje: {e}", exc_info=True)
            self._emit_error("Error al procesar el mensaje.", 'MESSAGE_PROCESSING_ERROR')

    @socket_auth_required()
    def on_typing_indicator(self, data: Dict[str, Any], current_user: User):
        """
        Maneja el indicador de "escribiendo".
        
        Args:
            data (dict): {'room_name': str, 'is_typing': bool}
            current_user (User): Usuario autenticado.
        """
        room_name = data.get('room_name')
        is_typing = data.get('is_typing', False)

        if not room_name:
            return

        if not self._can_user_send_to_room(current_user, room_name): # Reutilizar permiso de envío
            return

        payload = {
            'user': format_user_info(current_user),
            'room_name': room_name,
            'is_typing': is_typing,
            'timestamp': format_datetime(datetime.utcnow())
        }
        self.emit('typing_status', payload, room=room_name, include_self=False)

    def _can_user_join_room(self, user: User, room_name: str) -> bool:
        """Verifica si un usuario puede unirse a una sala específica."""
        # Lógica de ejemplo:
        if room_name.startswith("project_"):
            try:
                project_id = int(room_name.split("_")[1])
                project = Project.query.get(project_id)
                if not project: return False
                # El emprendedor del proyecto o un admin pueden unirse.
                return project.entrepreneur_id == user.id or user.is_admin
            except (ValueError, IndexError):
                return False
        elif room_name.startswith("user_"): # Chat privado
            parts = room_name.split("_")
            if len(parts) == 3: # user_ID1_ID2
                user_id1, user_id2 = parts[1], parts[2]
                return str(user.id) == user_id1 or str(user.id) == user_id2
            return False
        elif room_name == "general_chat":
            return True # Sala general para todos
        
        # Por defecto, denegar si no coincide con ninguna regla
        return False

    def _can_user_send_to_room(self, user: User, room_name: str) -> bool:
        """Verifica si un usuario puede enviar mensajes a una sala."""
        # A menudo, si puede unirse, puede enviar. Podría tener lógica más granular.
        if room_name in active_chat_rooms and str(user.id) in active_chat_rooms[room_name]:
            return True
        return self._can_user_join_room(user, room_name) # Fallback a la lógica de unirse

    def _get_or_create_thread_for_room(self, room_name: str, current_user: User) -> Optional[MessageThread]:
        """
        Obtiene o crea un MessageThread asociado a una sala de chat.
        La implementación exacta dependerá de cómo mapeas 'room_name' a tus hilos.
        """
        # Ejemplo simplificado:
        # Si room_name es 'project_X', buscar un hilo asociado a ese proyecto.
        # Si es 'user_A_B', buscar un hilo directo entre A y B.
        if room_name.startswith("project_"):
            try:
                project_id = int(room_name.split("_")[1])
                thread = MessageThread.query.filter_by(project_id=project_id, type='PROJECT').first()
                if not thread:
                    thread = MessageThread(
                        title=f"Chat del Proyecto {project_id}",
                        project_id=project_id,
                        type='PROJECT',
                        creator_id=current_user.id # O un ID de sistema
                    )
                    # Añadir participantes relevantes al hilo
                    project = Project.query.get(project_id)
                    if project and project.entrepreneur:
                        thread.participants.append(project.entrepreneur.user)
                    # Añadir otros miembros del equipo o mentores si es necesario
                    db.session.add(thread)
                    db.session.commit()
                return thread
            except (ValueError, IndexError, SQLAlchemyError):
                return None
        elif room_name.startswith("user_"): # Asume user_ID1_ID2
            parts = room_name.split("_")
            if len(parts) == 3:
                user_id1 = int(parts[1])
                user_id2 = int(parts[2])
                # Lógica para encontrar o crear hilo directo entre user_id1 y user_id2
                # Esta es una simplificación, necesitarías una forma robusta de identificar hilos directos.
                thread = MessageThread.query.filter(
                    MessageThread.type == 'DIRECT',
                    ((MessageThread.creator_id == user_id1) | (MessageThread.creator_id == user_id2)),
                    # Aquí necesitarías una forma de verificar los participantes
                ).first() # Esto es muy simplificado
                if not thread:
                    # Crear hilo directo
                    other_user_id = user_id1 if current_user.id == user_id2 else user_id2
                    other_user = User.query.get(other_user_id)
                    if not other_user: return None

                    thread = MessageThread(
                        title=f"Chat con {other_user.username}",
                        type='DIRECT',
                        creator_id=current_user.id
                    )
                    thread.participants.append(current_user)
                    thread.participants.append(other_user)
                    db.session.add(thread)
                    db.session.commit()
                return thread

        elif room_name == "general_chat":
            thread = MessageThread.query.filter_by(title="General Chat", type='GROUP').first()
            if not thread:
                thread = MessageThread(title="General Chat", type='GROUP', creator_id=current_user.id) # O un ID de sistema
                # Añadir todos los usuarios o un subconjunto como participantes
                db.session.add(thread)
                db.session.commit()
            return thread
            
        return None # No se pudo determinar el hilo

    def _notify_room_participants(self, thread: MessageThread, message: Message, sender: User):
        """Envía notificaciones a los participantes de la sala que no están activos en el chat."""
        if not socket_manager: return

        online_in_room_ids = active_chat_rooms.get(f"thread_{thread.id}", set()) # Asumiendo que el room_name es el thread_id
        
        for participant in thread.participants:
            if str(participant.id) == str(sender.id): # No notificar al remitente
                continue
            
            # Si el usuario no está online O no está en esta sala específica
            if not socket_manager.is_user_online(str(participant.id)) or str(participant.id) not in online_in_room_ids:
                # Enviar notificación push/email
                self.notification_service.send_notification(
                    user_id=participant.id,
                    type='new_chat_message', # Definir este tipo de notificación
                    title=f"Nuevo mensaje de {sender.username} en {thread.title}",
                    message=message.content[:100] + "..." if len(message.content) > 100 else message.content,
                    data={
                        'thread_id': str(thread.id),
                        'message_id': str(message.id),
                        'sender_id': str(sender.id)
                    }
                )

# Exportar el namespace para ser registrado en app.sockets.__init__.py
# Esto se haría si no usas register_all_namespaces
# chat_namespace = ChatNamespace('/chat')