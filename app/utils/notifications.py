# app/utils/notifications.py

import json
from flask import current_app, render_template
from flask_socketio import emit
from app.extensions import db, socketio, mail
from flask_mail import Message
from app.models.user import User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def send_notification(user_id, message, category='info', link=None, data=None):
    """
    Envía una notificación a un usuario específico.
    
    Args:
        user_id (int): ID del usuario destinatario
        message (str): Mensaje de la notificación
        category (str): Categoría de la notificación ('info', 'success', 'warning', 'error')
        link (str): Enlace opcional relacionado con la notificación
        data (dict): Datos adicionales opcionales
        
    Returns:
        bool: True si la notificación se envió correctamente, False en caso contrario
    """
    try:
        from app.models.notification import Notification
        
        # Crear nueva notificación en la base de datos
        notification = Notification(
            user_id=user_id,
            message=message,
            category=category,
            link=link,
            data=json.dumps(data) if data else None,
            created_at=datetime.utcnow(),
            is_read=False
        )
        
        db.session.add(notification)
        db.session.commit()
        
        # Enviar notificación en tiempo real si el usuario está conectado
        send_realtime_notification(user_id, notification)
        
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación: {str(e)}")
        db.session.rollback()
        return False

def send_bulk_notification(user_ids, message, category='info', link=None, data=None):
    """
    Envía una notificación a múltiples usuarios.
    
    Args:
        user_ids (list): Lista de IDs de usuarios destinatarios
        message (str): Mensaje de la notificación
        category (str): Categoría de la notificación ('info', 'success', 'warning', 'error')
        link (str): Enlace opcional relacionado con la notificación
        data (dict): Datos adicionales opcionales
        
    Returns:
        bool: True si todas las notificaciones se enviaron correctamente, False en caso contrario
    """
    try:
        from app.models.notification import Notification
        
        notifications = []
        current_time = datetime.utcnow()
        
        # Crear notificaciones para todos los usuarios
        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                message=message,
                category=category,
                link=link,
                data=json.dumps(data) if data else None,
                created_at=current_time,
                is_read=False
            )
            notifications.append(notification)
        
        # Guardar todas las notificaciones en la base de datos
        db.session.add_all(notifications)
        db.session.commit()
        
        # Enviar notificaciones en tiempo real a los usuarios conectados
        for notification in notifications:
            send_realtime_notification(notification.user_id, notification)
        
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificaciones masivas: {str(e)}")
        db.session.rollback()
        return False

def send_role_notification(role, message, category='info', link=None, data=None):
    """
    Envía una notificación a todos los usuarios con un rol específico.
    
    Args:
        role (str): Rol de los usuarios ('admin', 'entrepreneur', 'ally', 'client')
        message (str): Mensaje de la notificación
        category (str): Categoría de la notificación ('info', 'success', 'warning', 'error')
        link (str): Enlace opcional relacionado con la notificación
        data (dict): Datos adicionales opcionales
        
    Returns:
        bool: True si las notificaciones se enviaron correctamente, False en caso contrario
    """
    try:
        # Obtener IDs de los usuarios con el rol especificado
        user_ids = [user.id for user in User.query.filter_by(role=role).all()]
        
        if not user_ids:
            logger.warning(f"No se encontraron usuarios con el rol '{role}'")
            return False
        
        # Enviar notificación a los usuarios obtenidos
        return send_bulk_notification(user_ids, message, category, link, data)
    except Exception as e:
        logger.error(f"Error al enviar notificación por rol: {str(e)}")
        return False

def send_realtime_notification(user_id, notification):
    """
    Envía una notificación en tiempo real a través de WebSocket.
    
    Args:
        user_id (int): ID del usuario destinatario
        notification (Notification): Objeto de notificación
        
    Returns:
        bool: True si la notificación se envió correctamente, False en caso contrario
    """
    try:
        # Preparar datos para el cliente
        notification_data = {
            'id': notification.id,
            'message': notification.message,
            'category': notification.category,
            'link': notification.link,
            'created_at': notification.created_at.isoformat(),
            'data': json.loads(notification.data) if notification.data else None
        }
        
        # Enviar a través de Socket.IO al room específico del usuario
        socketio.emit('notification', notification_data, room=f'user_{user_id}')
        
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación en tiempo real: {str(e)}")
        return False

def send_email_notification(user_id, subject, template, **context):
    """
    Envía una notificación por correo electrónico a un usuario.
    
    Args:
        user_id (int): ID del usuario destinatario
        subject (str): Asunto del correo
        template (str): Nombre de la plantilla de correo
        **context: Variables de contexto para la plantilla
        
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Obtener información del usuario
        user = User.query.get(user_id)
        if not user or not user.email:
            logger.warning(f"No se pudo enviar correo: usuario {user_id} no encontrado o sin correo")
            return False
        
        # Renderizar la plantilla HTML del correo
        html_body = render_template(f'email/{template}.html', user=user, **context)
        
        # Crear mensaje
        msg = Message(
            subject=subject,
            recipients=[user.email],
            html=html_body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Enviar correo
        mail.send(msg)
        
        # Registrar el envío en la base de datos si es necesario
        from app.models.email_log import EmailLog
        email_log = EmailLog(
            user_id=user_id,
            subject=subject,
            template=template,
            sent_at=datetime.utcnow()
        )
        db.session.add(email_log)
        db.session.commit()
        
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo: {str(e)}")
        db.session.rollback()
        return False

def send_sms_notification(user_id, message):
    """
    Envía una notificación por SMS a un usuario.
    
    Args:
        user_id (int): ID del usuario destinatario
        message (str): Mensaje a enviar
        
    Returns:
        bool: True si el SMS se envió correctamente, False en caso contrario
    """
    try:
        # Obtener información del usuario
        user = User.query.get(user_id)
        if not user or not user.phone:
            logger.warning(f"No se pudo enviar SMS: usuario {user_id} no encontrado o sin teléfono")
            return False
        
        # Servicio de SMS (integración con terceros como Twilio, etc.)
        sms_service = current_app.config.get('SMS_SERVICE')
        if sms_service == 'twilio':
            return send_twilio_sms(user.phone, message)
        else:
            logger.warning(f"Servicio de SMS '{sms_service}' no implementado")
            return False
    except Exception as e:
        logger.error(f"Error al enviar SMS: {str(e)}")
        return False

def send_twilio_sms(phone_number, message):
    """
    Envía un SMS utilizando el servicio de Twilio.
    
    Args:
        phone_number (str): Número de teléfono del destinatario
        message (str): Mensaje a enviar
        
    Returns:
        bool: True si el SMS se envió correctamente, False en caso contrario
    """
    try:
        # Importar la biblioteca de Twilio
        from twilio.rest import Client
        
        # Obtener credenciales de Twilio
        account_sid = current_app.config['TWILIO_ACCOUNT_SID']
        auth_token = current_app.config['TWILIO_AUTH_TOKEN']
        twilio_number = current_app.config['TWILIO_PHONE_NUMBER']
        
        # Crear cliente Twilio
        client = Client(account_sid, auth_token)
        
        # Enviar mensaje
        message = client.messages.create(
            body=message,
            from_=twilio_number,
            to=phone_number
        )
        
        logger.info(f"SMS enviado con SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar SMS con Twilio: {str(e)}")
        return False

def mark_notification_as_read(notification_id):
    """
    Marca una notificación como leída.
    
    Args:
        notification_id (int): ID de la notificación
        
    Returns:
        bool: True si se marcó correctamente, False en caso contrario
    """
    try:
        from app.models.notification import Notification
        
        notification = Notification.query.get(notification_id)
        if not notification:
            return False
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return True
    except Exception as e:
        logger.error(f"Error al marcar notificación como leída: {str(e)}")
        db.session.rollback()
        return False

def mark_all_notifications_as_read(user_id):
    """
    Marca todas las notificaciones de un usuario como leídas.
    
    Args:
        user_id (int): ID del usuario
        
    Returns:
        bool: True si se marcaron correctamente, False en caso contrario
    """
    try:
        from app.models.notification import Notification
        
        # Actualizar todas las notificaciones no leídas del usuario
        current_time = datetime.utcnow()
        Notification.query.filter_by(
            user_id=user_id, 
            is_read=False
        ).update({
            'is_read': True,
            'read_at': current_time
        })
        
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error al marcar todas las notificaciones como leídas: {str(e)}")
        db.session.rollback()
        return False

def get_unread_notification_count(user_id):
    """
    Obtiene el número de notificaciones no leídas para un usuario.
    
    Args:
        user_id (int): ID del usuario
        
    Returns:
        int: Número de notificaciones no leídas
    """
    try:
        from app.models.notification import Notification
        
        return Notification.query.filter_by(
            user_id=user_id, 
            is_read=False
        ).count()
    except Exception as e:
        logger.error(f"Error al obtener el conteo de notificaciones: {str(e)}")
        return 0