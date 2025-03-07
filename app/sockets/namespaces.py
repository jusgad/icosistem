# app/sockets/namespaces.py

from flask_socketio import Namespace, emit, join_room, leave_room
from flask_login import current_user
from app.extensions import socketio, db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.meeting import Meeting
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class ChatNamespace(Namespace):
    """
    Namespace para el chat de la aplicación.
    Maneja eventos específicos de chat en el namespace '/chat'.
    """
    
    def on_connect(self):
        """Maneja evento de conexión al namespace de chat."""
        if not current_user.is_authenticated:
            return False
        
        # Unir al usuario a sus salas de chat
        self._join_user_chat_rooms()
        emit('status', {'status': 'connected', 'namespace': '/chat'})
        logger.info(f"Usuario {current_user.id} conectado al namespace /chat")
    
    def on_disconnect(self):
        """Maneja evento de desconexión del namespace de chat."""
        if current_user.is_authenticated:
            logger.info(f"Usuario {current_user.id} desconectado del namespace /chat")
    
    def on_join_chat(self, data):
        """
        Maneja la unión a una sala de chat.
        
        Args:
            data (dict): Datos con el campo 'chat_id' que contiene el ID del chat
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        chat_id = data.get('chat_id')
        if not chat_id:
            emit('error', {'message': 'ID de chat no especificado'})
            return
        
        # Verificar acceso al chat
        if not self._can_access_chat(chat_id):
            emit('error', {'message': 'No tienes acceso a este chat'})
            return
        
        # Unir al usuario a la sala de chat
        chat_room = f'chat_{chat_id}'
        join_room(chat_room)
        
        emit('joined_chat', {'chat_id': chat_id})
        logger.info(f"Usuario {current_user.id} unido al chat {chat_id}")
    
    def on_leave_chat(self, data):
        """
        Maneja el abandono de una sala de chat.
        
        Args:
            data (dict): Datos con el campo 'chat_id' que contiene el ID del chat
        """
        if not current_user.is_authenticated:
            return
        
        chat_id = data.get('chat_id')
        if not chat_id:
            return
        
        # Abandonar sala de chat
        chat_room = f'chat_{chat_id}'
        leave_room(chat_room)
        
        emit('left_chat', {'chat_id': chat_id})
        logger.info(f"Usuario {current_user.id} abandonó el chat {chat_id}")
    
    def _join_user_chat_rooms(self):
        """
        Une al usuario a todas sus salas de chat relevantes según su rol.
        """
        if current_user.role == 'entrepreneur':
            # Obtener relaciones con aliados
            entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first()
            if entrepreneur and entrepreneur.relationships:
                for rel in entrepreneur.relationships:
                    chat_room = f'chat_e{entrepreneur.id}_a{rel.ally_id}'
                    join_room(chat_room)
        
        elif current_user.role == 'ally':
            # Obtener relaciones con emprendedores
            ally = Ally.query.filter_by(user_id=current_user.id).first()
            if ally and ally.relationships:
                for rel in ally.relationships:
                    chat_room = f'chat_e{rel.entrepreneur_id}_a{ally.id}'
                    join_room(chat_room)
        
        elif current_user.role == 'admin':
            # Administradores se unen a salas relevantes
            join_room('chat_admin')
    
    def _can_access_chat(self, chat_id):
        """
        Verifica si el usuario puede acceder a un chat específico.
        
        Args:
            chat_id (str): ID del chat
            
        Returns:
            bool: True si el usuario puede acceder al chat
        """
        # Administradores pueden acceder a todos los chats
        if current_user.role == 'admin':
            return True
        
        # Verificar formato de ID de chat (ej. "e123_a456" para chat entre emprendedor 123 y aliado 456)
        try:
            if chat_id.startswith('chat_e') and '_a' in chat_id:
                parts = chat_id.replace('chat_', '').split('_a')
                entrepreneur_id = int(parts[0].replace('e', ''))
                ally_id = int(parts[1])
                
                if current_user.role == 'entrepreneur':
                    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first()
                    return entrepreneur and entrepreneur.id == entrepreneur_id
                
                elif current_user.role == 'ally':
                    ally = Ally.query.filter_by(user_id=current_user.id).first()
                    return ally and ally.id == ally_id
        except:
            pass
        
        return False


class MeetingNamespace(Namespace):
    """
    Namespace para reuniones virtuales.
    Maneja eventos específicos de reuniones en el namespace '/meeting'.
    """
    
    def on_connect(self):
        """Maneja evento de conexión al namespace de reuniones."""
        if not current_user.is_authenticated:
            return False
        
        emit('status', {'status': 'connected', 'namespace': '/meeting'})
        logger.info(f"Usuario {current_user.id} conectado al namespace /meeting")
    
    def on_join_meeting(self, data):
        """
        Maneja la unión a una sala de reunión.
        
        Args:
            data (dict): Datos con el campo 'meeting_id' que contiene el ID de la reunión
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        meeting_id = data.get('meeting_id')
        if not meeting_id:
            emit('error', {'message': 'ID de reunión no especificado'})
            return
        
        # Verificar acceso a la reunión
        if not self._can_access_meeting(meeting_id):
            emit('error', {'message': 'No tienes acceso a esta reunión'})
            return
        
        # Unir al usuario a la sala de reunión
        meeting_room = f'meeting_{meeting_id}'
        join_room(meeting_room)
        
        # Registrar asistencia
        self._register_attendance(meeting_id)
        
        # Notificar a los participantes
        emit('user_joined', {
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}",
            'role': current_user.role,
            'timestamp': datetime.utcnow().isoformat()
        }, room=meeting_room)
        
        emit('joined_meeting', {'meeting_id': meeting_id})
        logger.info(f"Usuario {current_user.id} unido a la reunión {meeting_id}")
    
    def on_leave_meeting(self, data):
        """
        Maneja el abandono de una sala de reunión.
        
        Args:
            data (dict): Datos con el campo 'meeting_id' que contiene el ID de la reunión
        """
        if not current_user.is_authenticated:
            return
        
        meeting_id = data.get('meeting_id')
        if not meeting_id:
            return
        
        # Abandonar sala de reunión
        meeting_room = f'meeting_{meeting_id}'
        leave_room(meeting_room)
        
        # Notificar a los participantes
        emit('user_left', {
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}",
            'timestamp': datetime.utcnow().isoformat()
        }, room=meeting_room)
        
        emit('left_meeting', {'meeting_id': meeting_id})
        logger.info(f"Usuario {current_user.id} abandonó la reunión {meeting_id}")
    
    def on_meeting_message(self, data):
        """
        Maneja el envío de mensajes en una reunión.
        
        Args:
            data (dict): Datos del mensaje con los campos:
                - meeting_id: ID de la reunión
                - message: Contenido del mensaje
                - type: Tipo de mensaje (text, file, etc.)
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        meeting_id = data.get('meeting_id')
        message = data.get('message')
        message_type = data.get('type', 'text')
        
        if not meeting_id or not message:
            emit('error', {'message': 'Faltan datos requeridos'})
            return
        
        # Verificar acceso a la reunión
        if not self._can_access_meeting(meeting_id):
            emit('error', {'message': 'No tienes acceso a esta reunión'})
            return
        
        # Enviar mensaje a todos los participantes
        meeting_room = f'meeting_{meeting_id}'
        emit('new_message', {
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}",
            'message': message,
            'type': message_type,
            'timestamp': datetime.utcnow().isoformat()
        }, room=meeting_room)
    
    def _can_access_meeting(self, meeting_id):
        """
        Verifica si el usuario puede acceder a una reunión específica.
        
        Args:
            meeting_id (int): ID de la reunión
            
        Returns:
            bool: True si el usuario puede acceder a la reunión
        """
        try:
            meeting = Meeting.query.get(meeting_id)
            if not meeting:
                return False
            
            # Administradores pueden acceder a todas las reuniones
            if current_user.role == 'admin':
                return True
            
            # Verificar si el usuario es participante
            return meeting.is_participant(current_user.id)
        except:
            return False
    
    def _register_attendance(self, meeting_id):
        """
        Registra la asistencia del usuario a una reunión.
        
        Args:
            meeting_id (int): ID de la reunión
        """
        try:
            meeting = Meeting.query.get(meeting_id)
            if meeting:
                meeting.register_attendance(current_user.id)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error al registrar asistencia: {str(e)}")


class NotificationNamespace(Namespace):
    """
    Namespace para notificaciones en tiempo real.
    Maneja eventos específicos de notificaciones en el namespace '/notifications'.
    """
    
    def on_connect(self):
        """Maneja evento de conexión al namespace de notificaciones."""
        if not current_user.is_authenticated:
            return False
        
        # Unir al usuario a su sala personal de notificaciones
        notification_room = f'notifications_user_{current_user.id}'
        join_room(notification_room)
        
        # Unir al usuario a la sala de notificaciones de su rol
        role_room = f'notifications_role_{current_user.role}'
        join_room(role_room)
        
        emit('status', {'status': 'connected', 'namespace': '/notifications'})
        logger.info(f"Usuario {current_user.id} conectado al namespace /notifications")


def register_namespaces():
    """
    Registra todos los namespaces de Socket.IO.
    """
    socketio.on_namespace(ChatNamespace('/chat'))
    socketio.on_namespace(MeetingNamespace('/meeting'))
    socketio.on_namespace(NotificationNamespace('/notifications'))
    
    logger.info("Namespaces de Socket.IO registrados")