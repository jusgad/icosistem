# app/sockets/events.py

from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from flask import request
from app.extensions import socketio, db
from app.models.message import Message
from app.models.user import User
from app.models.relationship import Relationship
from app.models.notification import Notification
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

def register_message_events():
    """
    Registra los eventos relacionados con mensajes.
    """
    @socketio.on('send_message')
    def handle_send_message(data):
        """
        Maneja el envío de mensajes entre usuarios.
        
        Args:
            data (dict): Datos del mensaje con los siguientes campos:
                - recipient_id: ID del destinatario
                - content: Contenido del mensaje
                - message_type: Tipo de mensaje (texto, archivo, etc.)
                - attachment_url: URL del archivo adjunto (opcional)
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        # Validar datos
        recipient_id = data.get('recipient_id')
        content = data.get('content')
        message_type = data.get('message_type', 'text')
        attachment_url = data.get('attachment_url')
        
        if not recipient_id or not content:
            emit('error', {'message': 'Faltan datos requeridos'})
            return
        
        try:
            # Verificar si el destinatario existe
            recipient = User.query.get(recipient_id)
            if not recipient:
                emit('error', {'message': 'Destinatario no encontrado'})
                return
            
            # Verificar si el remitente tiene permiso para enviar mensajes al destinatario
            if not can_send_message(current_user.id, recipient_id):
                emit('error', {'message': 'No tienes permiso para enviar mensajes a este usuario'})
                return
            
            # Crear y guardar el mensaje
            message = Message(
                sender_id=current_user.id,
                recipient_id=recipient_id,
                content=content,
                message_type=message_type,
                attachment_url=attachment_url,
                sent_at=datetime.utcnow(),
                is_read=False
            )
            db.session.add(message)
            db.session.commit()
            
            # Preparar datos para emitir
            message_data = {
                'id': message.id,
                'sender_id': message.sender_id,
                'sender_name': f"{current_user.first_name} {current_user.last_name}",
                'recipient_id': message.recipient_id,
                'content': message.content,
                'message_type': message.message_type,
                'attachment_url': message.attachment_url,
                'sent_at': message.sent_at.isoformat(),
                'is_read': message.is_read
            }
            
            # Emitir mensaje al remitente
            emit('receive_message', message_data)
            
            # Emitir mensaje al destinatario
            emit('receive_message', message_data, room=f'user_{recipient_id}')
            
            # Registrar actividad
            logger.info(f"Mensaje enviado de usuario {current_user.id} a usuario {recipient_id}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al enviar mensaje: {str(e)}")
            emit('error', {'message': 'Error al enviar mensaje'})

    @socketio.on('mark_as_read')
    def handle_mark_as_read(data):
        """
        Maneja el marcado de mensajes como leídos.
        
        Args:
            data (dict): Datos con los siguientes campos:
                - message_id: ID del mensaje a marcar (opcional)
                - sender_id: ID del remitente para marcar todos sus mensajes (opcional)
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        try:
            message_id = data.get('message_id')
            sender_id = data.get('sender_id')
            
            if message_id:
                # Marcar un mensaje específico como leído
                message = Message.query.get(message_id)
                if message and message.recipient_id == current_user.id:
                    message.is_read = True
                    message.read_at = datetime.utcnow()
                    db.session.commit()
                    
                    # Notificar al remitente
                    emit('message_read', {'message_id': message_id}, room=f'user_{message.sender_id}')
                    
            elif sender_id:
                # Marcar todos los mensajes de un remitente como leídos
                messages = Message.query.filter_by(
                    sender_id=sender_id,
                    recipient_id=current_user.id,
                    is_read=False
                ).all()
                
                now = datetime.utcnow()
                message_ids = []
                for message in messages:
                    message.is_read = True
                    message.read_at = now
                    message_ids.append(message.id)
                
                if message_ids:
                    db.session.commit()
                    
                    # Notificar al remitente
                    emit('messages_read', {'message_ids': message_ids}, room=f'user_{sender_id}')
            else:
                emit('error', {'message': 'No se especificó mensaje_id o sender_id'})
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al marcar mensaje como leído: {str(e)}")
            emit('error', {'message': 'Error al marcar mensaje como leído'})

    @socketio.on('typing')
    def handle_typing(data):
        """
        Maneja las notificaciones de escritura.
        
        Args:
            data (dict): Datos con los siguientes campos:
                - recipient_id: ID del destinatario
                - is_typing: Si el usuario está escribiendo o no
        """
        if not current_user.is_authenticated:
            return
        
        recipient_id = data.get('recipient_id')
        is_typing = data.get('is_typing', False)
        
        if recipient_id:
            # Emitir estado de escritura al destinatario
            emit('user_typing', {
                'user_id': current_user.id,
                'user_name': f"{current_user.first_name} {current_user.last_name}",
                'is_typing': is_typing
            }, room=f'user_{recipient_id}')
    
    @socketio.on('get_unread_count')
    def handle_get_unread_count():
        """
        Maneja la solicitud para obtener el contador de mensajes no leídos.
        """
        if not current_user.is_authenticated:
            return
        
        try:
            # Contar mensajes no leídos
            unread_count = Message.query.filter_by(
                recipient_id=current_user.id,
                is_read=False
            ).count()
            
            # Enviar contador al usuario
            emit('unread_count', {'count': unread_count})
            
        except Exception as e:
            logger.error(f"Error al obtener contador de mensajes no leídos: {str(e)}")
            emit('error', {'message': 'Error al obtener contador de mensajes'})


def register_notification_events():
    """
    Registra los eventos relacionados con notificaciones.
    """
    @socketio.on('get_notifications')
    def handle_get_notifications(data):
        """
        Maneja la solicitud para obtener notificaciones.
        
        Args:
            data (dict): Datos con los siguientes campos:
                - limit: Número máximo de notificaciones a devolver
                - offset: Desplazamiento para paginación
                - include_read: Si se deben incluir notificaciones ya leídas
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        try:
            limit = data.get('limit', 10)
            offset = data.get('offset', 0)
            include_read = data.get('include_read', False)
            
            # Construir consulta
            query = Notification.query.filter_by(user_id=current_user.id)
            
            if not include_read:
                query = query.filter_by(is_read=False)
            
            # Ordenar y paginar
            notifications = query.order_by(Notification.created_at.desc()) \
                                .limit(limit) \
                                .offset(offset) \
                                .all()
            
            # Contar total de notificaciones no leídas
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
            
            # Preparar respuesta
            notification_data = []
            for notification in notifications:
                notification_data.append({
                    'id': notification.id,
                    'message': notification.message,
                    'category': notification.category,
                    'link': notification.link,
                    'created_at': notification.created_at.isoformat(),
                    'is_read': notification.is_read,
                    'data': json.loads(notification.data) if notification.data else None
                })
            
            # Emitir notificaciones al usuario
            emit('notifications', {
                'notifications': notification_data,
                'unread_count': unread_count,
                'has_more': len(notifications) == limit
            })
            
        except Exception as e:
            logger.error(f"Error al obtener notificaciones: {str(e)}")
            emit('error', {'message': 'Error al obtener notificaciones'})

    @socketio.on('mark_notification_read')
    def handle_mark_notification_read(data):
        """
        Maneja el marcado de notificaciones como leídas.
        
        Args:
            data (dict): Datos con los siguientes campos:
                - notification_id: ID de la notificación a marcar
                - mark_all: Si se deben marcar todas las notificaciones
        """
        if not current_user.is_authenticated:
            emit('error', {'message': 'No autenticado'})
            return
        
        try:
            notification_id = data.get('notification_id')
            mark_all = data.get('mark_all', False)
            
            if mark_all:
                # Marcar todas las notificaciones como leídas
                now = datetime.utcnow()
                Notification.query.filter_by(
                    user_id=current_user.id,
                    is_read=False
                ).update({
                    'is_read': True,
                    'read_at': now
                })
                
                db.session.commit()
                emit('all_notifications_read')
                
            elif notification_id:
                # Marcar una notificación específica como leída
                notification = Notification.query.get(notification_id)
                
                if notification and notification.user_id == current_user.id:
                    notification.is_read = True
                    notification.read_at = datetime.utcnow()
                    db.session.commit()
                    
                    emit('notification_read', {'notification_id': notification_id})
                else:
                    emit('error', {'message': 'Notificación no encontrada'})
            else:
                emit('error', {'message': 'No se especificó notification_id o mark_all'})
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al marcar notificación como leída: {str(e)}")
            emit('error', {'message': 'Error al marcar notificación como leída'})

    @socketio.on('get_unread_notification_count')
    def handle_get_unread_notification_count():
        """
        Maneja la solicitud para obtener el contador de notificaciones no leídas.
        """
        if not current_user.is_authenticated:
            return
        
        try:
            # Contar notificaciones no leídas
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
            
            # Enviar contador al usuario
            emit('unread_notification_count', {'count': unread_count})
            
        except Exception as e:
            logger.error(f"Error al obtener contador de notificaciones: {str(e)}")
            emit('error', {'message': 'Error al obtener contador de notificaciones'})


# Funciones auxiliares

def can_send_message(sender_id, recipient_id):
    """
    Verifica si un usuario puede enviar mensajes a otro.
    
    Args:
        sender_id (int): ID del remitente
        recipient_id (int): ID del destinatario
        
    Returns:
        bool: True si el remitente puede enviar mensajes al destinatario
    """
    # Si los IDs son iguales, no se puede enviar mensaje a uno mismo
    if sender_id == recipient_id:
        return False
    
    # Obtener usuarios
    sender = User.query.get(sender_id)
    recipient = User.query.get(recipient_id)
    
    if not sender or not recipient:
        return False
    
    # Administradores pueden enviar mensajes a cualquiera
    if sender.role == 'admin':
        return True
    
    # Verificar relación emprendedor-aliado
    if sender.role == 'entrepreneur' and recipient.role == 'ally':
        # Verificar si el aliado está asignado al emprendedor
        relationship = Relationship.query.filter_by(
            entrepreneur_id=sender_id,
            ally_id=recipient_id
        ).first()
        return relationship is not None
    
    if sender.role == 'ally' and recipient.role == 'entrepreneur':
        # Verificar si el emprendedor está asignado al aliado
        relationship = Relationship.query.filter_by(
            entrepreneur_id=recipient_id,
            ally_id=sender_id
        ).first()
        return relationship is not None
    
    # Clientes pueden enviar mensajes a administradores y viceversa
    if (sender.role == 'client' and recipient.role == 'admin') or \
       (sender.role == 'admin' and recipient.role == 'client'):
        return True
    
    # Otros casos no permitidos
    return False