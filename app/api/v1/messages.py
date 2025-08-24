"""
API V1 - Endpoints para sistema de mensajería del ecosistema de emprendimiento
Autor: Sistema de Ecosistema de Emprendimiento
Versión: 1.0
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from marshmallow import Schema, fields, validate, ValidationError, post_load
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import uuid
import os
import mimetypes
from werkzeug.exceptions import BadRequest, NotFound, Forbidden, Conflict, RequestEntityTooLarge
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, desc, asc
from sqlalchemy.orm import joinedload

# Imports internos
from app.models.message import Message, MessageType, MessageStatus, MessageThread, MessageAttachment
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.services.file_storage import FileStorageService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.core.permissions import require_permission, check_message_access
from app.core.exceptions import ValidationException, BusinessException, StorageException
from app.utils.decorators import api_response, rate_limit, log_activity
from app.utils.validators import validate_uuid, validate_file_size, validate_file_type
from app.utils.formatters import format_file_size, sanitize_message_content
from app.utils.file_utils import get_file_extension, generate_unique_filename
from app.extensions import db, cache, socketio

# Importar eventos de WebSocket
from flask_socketio import join_room, leave_room, emit

# Blueprint configuration
messages_bp = Blueprint('messages_api', __name__, url_prefix='/api/v1/messages')

# Configuraciones
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_FILE_TYPES = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'],
    'spreadsheet': ['xls', 'xlsx', 'csv', 'ods'],
    'presentation': ['ppt', 'pptx', 'odp'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
    'audio': ['mp3', 'wav', 'ogg', 'm4a'],
    'video': ['mp4', 'avi', 'mov', 'mkv', 'webm']
}

# Schemas para validación y serialización
class MessageCreateSchema(Schema):
    """Schema para creación de mensajes"""
    content = fields.Str(required=True, validate=validate.Length(min=1, max=10000))
    message_type = fields.Str(missing='text', validate=validate.OneOf([
        'text', 'file', 'image', 'audio', 'video', 'system', 'notification'
    ]))
    thread_id = fields.UUID(allow_none=True)
    recipient_id = fields.UUID(allow_none=True)
    recipient_ids = fields.List(fields.UUID(), allow_none=True)
    subject = fields.Str(validate=validate.Length(max=200))
    priority = fields.Str(missing='normal', validate=validate.OneOf([
        'low', 'normal', 'high', 'urgent'
    ]))
    is_private = fields.Bool(missing=False)
    reply_to_id = fields.UUID(allow_none=True)
    project_id = fields.UUID(allow_none=True)
    meeting_id = fields.UUID(allow_none=True)
    scheduled_send_at = fields.DateTime(allow_none=True)
    auto_delete_at = fields.DateTime(allow_none=True)
    metadata = fields.Dict(missing={})
    
    @post_load
    def validate_recipients(self, data, **kwargs):
        """Validar que haya al menos un destinatario"""
        if not data.get('thread_id') and not data.get('recipient_id') and not data.get('recipient_ids'):
            raise ValidationException("Se requiere thread_id, recipient_id o recipient_ids")
        
        if data.get('recipient_ids') and len(data['recipient_ids']) > 50:
            raise ValidationException("Máximo 50 destinatarios por mensaje")
        
        # Validar fecha de envío programado
        if data.get('scheduled_send_at'):
            if data['scheduled_send_at'] <= datetime.utcnow():
                raise ValidationException("La fecha de envío programado debe ser futura")
        
        return data

class MessageUpdateSchema(Schema):
    """Schema para actualización de mensajes"""
    content = fields.Str(validate=validate.Length(min=1, max=10000))
    is_read = fields.Bool()
    is_starred = fields.Bool()
    is_archived = fields.Bool()
    priority = fields.Str(validate=validate.OneOf(['low', 'normal', 'high', 'urgent']))
    metadata = fields.Dict()

class ThreadCreateSchema(Schema):
    """Schema para creación de hilos de conversación"""
    title = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    description = fields.Str(validate=validate.Length(max=1000))
    participants = fields.List(fields.UUID(), required=True)
    thread_type = fields.Str(missing='group', validate=validate.OneOf([
        'direct', 'group', 'project', 'meeting', 'support'
    ]))
    is_private = fields.Bool(missing=False)
    project_id = fields.UUID(allow_none=True)
    meeting_id = fields.UUID(allow_none=True)
    auto_archive_after_days = fields.Int(validate=validate.Range(min=1, max=365))
    
    @post_load
    def validate_participants(self, data, **kwargs):
        """Validar participantes"""
        participants = data.get('participants', [])
        
        if len(participants) < 1:
            raise ValidationException("Se requiere al menos un participante")
        
        if len(participants) > 100:
            raise ValidationException("Máximo 100 participantes por hilo")
        
        # Agregar al creador si no está incluido
        if current_user.id not in participants:
            participants.append(current_user.id)
        
        return data

class MessageFilterSchema(Schema):
    """Schema para filtros de búsqueda"""
    page = fields.Int(missing=1, validate=validate.Range(min=1))
    per_page = fields.Int(missing=20, validate=validate.Range(min=1, max=100))
    search = fields.Str()
    thread_id = fields.UUID()
    sender_id = fields.UUID()
    recipient_id = fields.UUID()
    message_type = fields.Str(validate=validate.OneOf([
        'text', 'file', 'image', 'audio', 'video', 'system', 'notification'
    ]))
    priority = fields.Str(validate=validate.OneOf(['low', 'normal', 'high', 'urgent']))
    is_read = fields.Bool()
    is_starred = fields.Bool()
    is_archived = fields.Bool()
    has_attachments = fields.Bool()
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    project_id = fields.UUID()
    meeting_id = fields.UUID()
    sort_by = fields.Str(missing='created_at', validate=validate.OneOf([
        'created_at', 'updated_at', 'priority', 'sender'
    ]))
    sort_order = fields.Str(missing='desc', validate=validate.OneOf(['asc', 'desc']))

class MessageResponseSchema(Schema):
    """Schema para respuesta de mensaje"""
    id = fields.UUID()
    content = fields.Str()
    content_preview = fields.Str()
    message_type = fields.Str()
    status = fields.Str()
    priority = fields.Str()
    is_read = fields.Bool()
    is_starred = fields.Bool()
    is_archived = fields.Bool()
    is_private = fields.Bool()
    thread_id = fields.UUID()
    sender = fields.Nested('UserBasicSchema')
    recipients = fields.List(fields.Nested('UserBasicSchema'))
    subject = fields.Str()
    reply_to = fields.Nested('MessageBasicSchema', allow_none=True)
    project = fields.Nested('ProjectBasicSchema', allow_none=True)
    meeting = fields.Nested('MeetingBasicSchema', allow_none=True)
    attachments = fields.List(fields.Nested('AttachmentSchema'))
    read_by = fields.List(fields.Nested('MessageReadSchema'))
    reactions = fields.List(fields.Nested('MessageReactionSchema'))
    metadata = fields.Dict()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    read_at = fields.DateTime(allow_none=True)
    delivered_at = fields.DateTime(allow_none=True)

class ThreadResponseSchema(Schema):
    """Schema para respuesta de hilo"""
    id = fields.UUID()
    title = fields.Str()
    description = fields.Str()
    thread_type = fields.Str()
    is_private = fields.Bool()
    participants = fields.List(fields.Nested('UserBasicSchema'))
    creator = fields.Nested('UserBasicSchema')
    last_message = fields.Nested('MessageBasicSchema', allow_none=True)
    unread_count = fields.Int()
    total_messages = fields.Int()
    project = fields.Nested('ProjectBasicSchema', allow_none=True)
    meeting = fields.Nested('MeetingBasicSchema', allow_none=True)
    is_archived = fields.Bool()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    last_activity_at = fields.DateTime()

class AttachmentSchema(Schema):
    """Schema para archivos adjuntos"""
    id = fields.UUID()
    filename = fields.Str()
    original_filename = fields.Str()
    file_size = fields.Int()
    file_size_formatted = fields.Str()
    file_type = fields.Str()
    mime_type = fields.Str()
    file_url = fields.URL()
    thumbnail_url = fields.URL(allow_none=True)
    download_count = fields.Int()
    uploaded_at = fields.DateTime()

# Servicios - lazy loading
def get_services():
    from app.services.file_storage import get_file_storage_service
    from app.services.notification_service import NotificationService
    from app.services.analytics_service import AnalyticsService
    from app.services.email import EmailService
    
    return {
        'file_storage': get_file_storage_service(),
        'notification': NotificationService(),
        'analytics': AnalyticsService(),
        'email': EmailService()
    }

# Schema instances
message_create_schema = MessageCreateSchema()
message_update_schema = MessageUpdateSchema()
thread_create_schema = ThreadCreateSchema()
message_filter_schema = MessageFilterSchema()
message_response_schema = MessageResponseSchema()
thread_response_schema = ThreadResponseSchema()


@messages_bp.route('', methods=['GET'])
@login_required
@rate_limit(requests=300, window=3600)  # 300 requests per hour
@api_response
def get_messages():
    """
    Obtener lista de mensajes con filtros y paginación
    
    Returns:
        JSON: Lista paginada de mensajes
    """
    try:
        # Validar parámetros de consulta
        filter_data = message_filter_schema.load(request.args)
        
        # Construir query base
        messages_query = Message.query.options(
            joinedload(Message.sender),
            joinedload(Message.recipients),
            joinedload(Message.thread),
            joinedload(Message.attachments)
        )
        
        # Aplicar filtros de permisos (solo mensajes del usuario)
        user_messages_filter = or_(
            Message.sender_id == current_user.id,
            Message.recipients.any(User.id == current_user.id),
            Message.thread.has(MessageThread.participants.any(User.id == current_user.id))
        )
        messages_query = messages_query.filter(user_messages_filter)
        
        # Aplicar filtros específicos
        if 'search' in filter_data and filter_data['search']:
            search_term = f"%{filter_data['search']}%"
            messages_query = messages_query.filter(
                or_(
                    Message.content.ilike(search_term),
                    Message.subject.ilike(search_term)
                )
            )
        
        if 'thread_id' in filter_data:
            messages_query = messages_query.filter(Message.thread_id == filter_data['thread_id'])
        
        if 'sender_id' in filter_data:
            messages_query = messages_query.filter(Message.sender_id == filter_data['sender_id'])
        
        if 'recipient_id' in filter_data:
            messages_query = messages_query.filter(
                Message.recipients.any(User.id == filter_data['recipient_id'])
            )
        
        if 'message_type' in filter_data:
            messages_query = messages_query.filter(Message.message_type == filter_data['message_type'])
        
        if 'priority' in filter_data:
            messages_query = messages_query.filter(Message.priority == filter_data['priority'])
        
        if 'is_read' in filter_data:
            if filter_data['is_read']:
                messages_query = messages_query.filter(
                    Message.read_by.any(
                        and_(
                            Message.read_by.c.user_id == current_user.id,
                            Message.read_by.c.is_read == True
                        )
                    )
                )
            else:
                messages_query = messages_query.filter(
                    ~Message.read_by.any(
                        and_(
                            Message.read_by.c.user_id == current_user.id,
                            Message.read_by.c.is_read == True
                        )
                    )
                )
        
        if 'is_starred' in filter_data:
            messages_query = messages_query.filter(
                Message.starred_by.any(User.id == current_user.id) == filter_data['is_starred']
            )
        
        if 'is_archived' in filter_data:
            messages_query = messages_query.filter(Message.is_archived == filter_data['is_archived'])
        
        if 'has_attachments' in filter_data:
            if filter_data['has_attachments']:
                messages_query = messages_query.filter(Message.attachments.any())
            else:
                messages_query = messages_query.filter(~Message.attachments.any())
        
        if 'start_date' in filter_data:
            messages_query = messages_query.filter(Message.created_at >= filter_data['start_date'])
        
        if 'end_date' in filter_data:
            messages_query = messages_query.filter(Message.created_at <= filter_data['end_date'])
        
        if 'project_id' in filter_data:
            messages_query = messages_query.filter(Message.project_id == filter_data['project_id'])
        
        if 'meeting_id' in filter_data:
            messages_query = messages_query.filter(Message.meeting_id == filter_data['meeting_id'])
        
        # Aplicar ordenamiento
        sort_field = getattr(Message, filter_data['sort_by'])
        if filter_data['sort_order'] == 'desc':
            sort_field = sort_field.desc()
        else:
            sort_field = sort_field.asc()
        messages_query = messages_query.order_by(sort_field)
        
        # Aplicar paginación
        page = filter_data['page']
        per_page = filter_data['per_page']
        messages_paginated = messages_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Serializar resultados
        messages_data = []
        for message in messages_paginated.items:
            message_dict = message_response_schema.dump(message)
            # Agregar estado de lectura específico del usuario
            message_dict['user_read_status'] = message.get_user_read_status(current_user.id)
            # Agregar preview del contenido
            message_dict['content_preview'] = _get_content_preview(message.content, message.message_type)
            messages_data.append(message_dict)
        
        # Marcar mensajes como entregados
        _mark_messages_as_delivered(messages_paginated.items)
        
        return {
            'messages': messages_data,
            'pagination': {
                'page': messages_paginated.page,
                'pages': messages_paginated.pages,
                'per_page': messages_paginated.per_page,
                'total': messages_paginated.total,
                'has_next': messages_paginated.has_next,
                'has_prev': messages_paginated.has_prev
            },
            'filters_applied': filter_data,
            'unread_count': _get_user_unread_count()
        }, 200
        
    except ValidationError as e:
        raise BadRequest(f"Parámetros de consulta inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error al obtener mensajes: {str(e)}")
        raise


@messages_bp.route('/<uuid:message_id>', methods=['GET'])
@login_required
@rate_limit(requests=500, window=3600)
@api_response
def get_message(message_id: uuid.UUID):
    """
    Obtener detalles de un mensaje específico
    
    Args:
        message_id: UUID del mensaje
        
    Returns:
        JSON: Detalles completos del mensaje
    """
    try:
        # Obtener mensaje con relaciones
        message = Message.query.options(
            joinedload(Message.sender),
            joinedload(Message.recipients),
            joinedload(Message.thread),
            joinedload(Message.attachments),
            joinedload(Message.reply_to)
        ).get(message_id)
        
        if not message:
            raise NotFound("Mensaje no encontrado")
        
        # Verificar permisos de acceso
        if not check_message_access(current_user, message, 'read'):
            raise Forbidden("No tienes permisos para ver este mensaje")
        
        # Marcar como leído si no lo está
        if not message.is_read_by_user(current_user.id):
            message.mark_as_read(current_user.id)
            db.session.commit()
            
            # Emitir evento de lectura via WebSocket
            socketio.emit(
                'message_read',
                {
                    'message_id': str(message_id),
                    'read_by': current_user.id,
                    'read_at': datetime.utcnow().isoformat()
                },
                room=f"thread_{message.thread_id}"
            )
        
        # Serializar mensaje
        message_data = message_response_schema.dump(message)
        
        # Agregar información adicional
        message_data['user_read_status'] = message.get_user_read_status(current_user.id)
        message_data['delivery_status'] = message.get_delivery_status()
        
        # Registrar actividad
        ActivityLog.log_activity(
            user_id=current_user.id,
            action='view_message',
            resource_type='message',
            resource_id=message_id,
            metadata={'thread_id': str(message.thread_id)}
        )
        
        return message_data, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener mensaje {message_id}: {str(e)}")
        raise


@messages_bp.route('', methods=['POST'])
@login_required
@rate_limit(requests=100, window=3600)  # 100 messages per hour
@log_activity('send_message')
@api_response
def send_message():
    """
    Enviar un nuevo mensaje
    
    Returns:
        JSON: Mensaje enviado
    """
    try:
        # Validar datos de entrada
        message_data = message_create_schema.load(request.get_json())
        
        # Sanitizar contenido
        content = sanitize_message_content(message_data['content'])
        
        # Determinar destinatarios
        recipients = []
        thread = None
        
        if message_data.get('thread_id'):
            # Mensaje en hilo existente
            thread = MessageThread.query.get(message_data['thread_id'])
            if not thread:
                raise NotFound("Hilo de conversación no encontrado")
            
            # Verificar permisos en el hilo
            if current_user not in thread.participants:
                raise Forbidden("No eres participante de este hilo")
            
            recipients = [p for p in thread.participants if p.id != current_user.id]
            
        elif message_data.get('recipient_id'):
            # Mensaje directo a un usuario
            recipient = User.query.get(message_data['recipient_id'])
            if not recipient:
                raise NotFound("Destinatario no encontrado")
            recipients = [recipient]
            
            # Crear o encontrar hilo directo
            thread = _get_or_create_direct_thread(current_user.id, recipient.id)
            
        elif message_data.get('recipient_ids'):
            # Mensaje a múltiples usuarios
            recipients = User.query.filter(User.id.in_(message_data['recipient_ids'])).all()
            if len(recipients) != len(message_data['recipient_ids']):
                raise BadRequest("Algunos destinatarios no fueron encontrados")
            
            # Crear hilo de grupo si no existe
            if len(recipients) > 1:
                thread = _create_group_thread(recipients + [current_user])
            else:
                thread = _get_or_create_direct_thread(current_user.id, recipients[0].id)
        
        # Verificar límites de envío
        if not _check_sending_limits(current_user.id):
            raise Conflict("Has alcanzado el límite de mensajes por hora")
        
        # Crear mensaje
        message = Message(
            content=content,
            message_type=message_data['message_type'],
            sender_id=current_user.id,
            thread_id=thread.id,
            subject=message_data.get('subject'),
            priority=message_data['priority'],
            is_private=message_data['is_private'],
            reply_to_id=message_data.get('reply_to_id'),
            project_id=message_data.get('project_id'),
            meeting_id=message_data.get('meeting_id'),
            scheduled_send_at=message_data.get('scheduled_send_at'),
            auto_delete_at=message_data.get('auto_delete_at'),
            metadata=message_data.get('metadata', {})
        )
        
        # Agregar destinatarios
        for recipient in recipients:
            message.recipients.append(recipient)
        
        db.session.add(message)
        
        # Actualizar actividad del hilo
        thread.last_activity_at = datetime.utcnow()
        thread.last_message_id = message.id
        
        db.session.commit()
        
        # Emitir evento en tiempo real
        message_dict = message_response_schema.dump(message)
        socketio.emit(
            'new_message',
            message_dict,
            room=f"thread_{thread.id}"
        )
        
        # Enviar notificaciones
        if not message_data.get('scheduled_send_at'):  # Solo si no es programado
            _send_message_notifications(message)
        
        # Registrar en analytics
        analytics_service.track_message_sent(message.id, current_user.id, len(recipients))
        
        return {
            'message': 'Mensaje enviado exitosamente',
            'data': message_dict
        }, 201
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden, Conflict) as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al enviar mensaje: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/<uuid:message_id>', methods=['PUT'])
@login_required
@rate_limit(requests=50, window=3600)
@log_activity('update_message')
@api_response
def update_message(message_id: uuid.UUID):
    """
    Actualizar un mensaje (solo contenido si es el remitente)
    
    Args:
        message_id: UUID del mensaje
        
    Returns:
        JSON: Mensaje actualizado
    """
    try:
        # Obtener mensaje
        message = Message.query.get(message_id)
        if not message:
            raise NotFound("Mensaje no encontrado")
        
        # Verificar permisos
        if not check_message_access(current_user, message, 'update'):
            raise Forbidden("No tienes permisos para actualizar este mensaje")
        
        # Validar datos de actualización
        update_data = message_update_schema.load(request.get_json())
        
        # Solo el remitente puede editar el contenido y solo dentro de 15 minutos
        if 'content' in update_data:
            if message.sender_id != current_user.id:
                raise Forbidden("Solo el remitente puede editar el contenido")
            
            time_since_sent = datetime.utcnow() - message.created_at
            if time_since_sent > timedelta(minutes=15):
                raise BadRequest("No se puede editar el contenido después de 15 minutos")
            
            message.content = sanitize_message_content(update_data['content'])
            message.is_edited = True
            message.edited_at = datetime.utcnow()
        
        # Actualizar estado de lectura/estrella/archivo (solo para el usuario actual)
        if 'is_read' in update_data:
            if update_data['is_read']:
                message.mark_as_read(current_user.id)
            else:
                message.mark_as_unread(current_user.id)
        
        if 'is_starred' in update_data:
            if update_data['is_starred']:
                message.add_star(current_user.id)
            else:
                message.remove_star(current_user.id)
        
        if 'is_archived' in update_data and message.sender_id == current_user.id:
            message.is_archived = update_data['is_archived']
        
        if 'priority' in update_data and message.sender_id == current_user.id:
            message.priority = update_data['priority']
        
        if 'metadata' in update_data and message.sender_id == current_user.id:
            message.metadata.update(update_data['metadata'])
        
        message.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Emitir evento de actualización si se editó el contenido
        if 'content' in update_data:
            message_dict = message_response_schema.dump(message)
            socketio.emit(
                'message_updated',
                message_dict,
                room=f"thread_{message.thread_id}"
            )
        
        # Registrar en analytics
        analytics_service.track_message_update(message_id, current_user.id, list(update_data.keys()))
        
        return {
            'message': 'Mensaje actualizado exitosamente',
            'data': message_response_schema.dump(message)
        }, 200
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al actualizar mensaje {message_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/<uuid:message_id>', methods=['DELETE'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('delete_message')
@api_response
def delete_message(message_id: uuid.UUID):
    """
    Eliminar un mensaje (soft delete)
    
    Args:
        message_id: UUID del mensaje
        
    Returns:
        JSON: Confirmación de eliminación
    """
    try:
        # Obtener mensaje
        message = Message.query.get(message_id)
        if not message:
            raise NotFound("Mensaje no encontrado")
        
        # Verificar permisos
        if not check_message_access(current_user, message, 'delete'):
            raise Forbidden("No tienes permisos para eliminar este mensaje")
        
        # Solo el remitente puede eliminar dentro de 1 hora
        if message.sender_id != current_user.id:
            raise Forbidden("Solo el remitente puede eliminar el mensaje")
        
        time_since_sent = datetime.utcnow() - message.created_at
        if time_since_sent > timedelta(hours=1):
            raise BadRequest("No se puede eliminar el mensaje después de 1 hora")
        
        # Obtener motivo de eliminación
        delete_data = request.get_json() or {}
        reason = delete_data.get('reason', 'Eliminado por el usuario')
        
        # Soft delete
        message.is_deleted = True
        message.deleted_at = datetime.utcnow()
        message.deleted_by = current_user.id
        message.deletion_reason = reason
        
        db.session.commit()
        
        # Emitir evento de eliminación
        socketio.emit(
            'message_deleted',
            {
                'message_id': str(message_id),
                'deleted_by': current_user.id,
                'deleted_at': datetime.utcnow().isoformat()
            },
            room=f"thread_{message.thread_id}"
        )
        
        # Registrar en analytics
        analytics_service.track_message_deletion(message_id, current_user.id, reason)
        
        return {
            'message': 'Mensaje eliminado exitosamente',
            'reason': reason
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al eliminar mensaje {message_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/<uuid:message_id>/attachments', methods=['POST'])
@login_required
@rate_limit(requests=30, window=3600)
@log_activity('upload_attachment')
@api_response
def upload_attachment(message_id: uuid.UUID):
    """
    Subir archivo adjunto a un mensaje
    
    Args:
        message_id: UUID del mensaje
        
    Returns:
        JSON: Información del archivo subido
    """
    try:
        # Obtener mensaje
        message = Message.query.get(message_id)
        if not message:
            raise NotFound("Mensaje no encontrado")
        
        # Verificar permisos
        if not check_message_access(current_user, message, 'add_attachment'):
            raise Forbidden("No tienes permisos para agregar archivos a este mensaje")
        
        # Verificar que el archivo fue enviado
        if 'file' not in request.files:
            raise BadRequest("No se encontró archivo en la solicitud")
        
        file = request.files['file']
        if file.filename == '':
            raise BadRequest("No se seleccionó archivo")
        
        # Validar archivo
        if not _validate_file(file):
            raise BadRequest("Tipo de archivo no permitido")
        
        if file.content_length and file.content_length > MAX_FILE_SIZE:
            raise RequestEntityTooLarge(f"El archivo excede el tamaño máximo de {format_file_size(MAX_FILE_SIZE)}")
        
        # Generar nombre único
        original_filename = secure_filename(file.filename)
        file_extension = get_file_extension(original_filename)
        unique_filename = generate_unique_filename(original_filename)
        
        # Subir archivo
        try:
            services = get_services()
            file_info = services['file_storage'].upload_file(
                file=file,
                filename=unique_filename,
                folder=f"messages/{message.thread_id}"
            )
        except StorageException as e:
            raise BadRequest(f"Error al subir archivo: {str(e)}")
        
        # Crear registro de adjunto
        attachment = MessageAttachment(
            message_id=message_id,
            filename=unique_filename,
            original_filename=original_filename,
            file_size=file_info['size'],
            file_type=_get_file_type(file_extension),
            mime_type=file.mimetype or 'application/octet-stream',
            file_url=file_info['url'],
            uploaded_by=current_user.id
        )
        
        # Generar thumbnail si es imagen
        if attachment.file_type == 'image':
            try:
                thumbnail_info = services['file_storage'].generate_thumbnail(
                    file_url=file_info['url'],
                    sizes=[(150, 150), (300, 300)]
                )
                attachment.thumbnail_url = thumbnail_info.get('thumbnail_url')
            except Exception as e:
                current_app.logger.warning(f"Error al generar thumbnail: {str(e)}")
        
        db.session.add(attachment)
        
        # Actualizar tipo de mensaje si es necesario
        if message.message_type == 'text':
            if attachment.file_type in ['image', 'audio', 'video']:
                message.message_type = attachment.file_type
            else:
                message.message_type = 'file'
        
        db.session.commit()
        
        # Emitir evento de nuevo adjunto
        attachment_dict = AttachmentSchema().dump(attachment)
        socketio.emit(
            'attachment_added',
            {
                'message_id': str(message_id),
                'attachment': attachment_dict
            },
            room=f"thread_{message.thread_id}"
        )
        
        # Registrar en analytics
        analytics_service.track_file_upload(attachment.id, current_user.id, attachment.file_type)
        
        return {
            'message': 'Archivo subido exitosamente',
            'attachment': attachment_dict
        }, 201
        
    except (NotFound, Forbidden, BadRequest, RequestEntityTooLarge) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al subir archivo a mensaje {message_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/attachments/<uuid:attachment_id>/download', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)
@api_response
def download_attachment(attachment_id: uuid.UUID):
    """
    Descargar archivo adjunto
    
    Args:
        attachment_id: UUID del archivo adjunto
        
    Returns:
        File: Archivo para descarga
    """
    try:
        # Obtener adjunto
        attachment = MessageAttachment.query.get(attachment_id)
        if not attachment:
            raise NotFound("Archivo adjunto no encontrado")
        
        # Verificar permisos del mensaje
        if not check_message_access(current_user, attachment.message, 'read'):
            raise Forbidden("No tienes permisos para descargar este archivo")
        
        # Incrementar contador de descargas
        attachment.download_count += 1
        attachment.last_downloaded_at = datetime.utcnow()
        attachment.last_downloaded_by = current_user.id
        db.session.commit()
        
        # Obtener archivo del storage
        try:
            services = get_services()
            file_stream = services['file_storage'].get_file(attachment.file_url)
            
            # Registrar descarga en analytics
            services['analytics'].track_file_download(attachment_id, current_user.id)
            
            return send_file(
                file_stream,
                as_attachment=True,
                download_name=attachment.original_filename,
                mimetype=attachment.mime_type
            )
            
        except StorageException as e:
            raise NotFound(f"Archivo no disponible: {str(e)}")
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al descargar archivo {attachment_id}: {str(e)}")
        raise


@messages_bp.route('/threads', methods=['GET'])
@login_required
@rate_limit(requests=200, window=3600)
@api_response
def get_threads():
    """
    Obtener hilos de conversación del usuario
    
    Returns:
        JSON: Lista de hilos de conversación
    """
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        thread_type = request.args.get('type')
        search = request.args.get('search')
        is_archived = request.args.get('archived', 'false').lower() == 'true'
        
        # Construir query
        threads_query = MessageThread.query.filter(
            MessageThread.participants.any(User.id == current_user.id)
        )
        
        if thread_type:
            threads_query = threads_query.filter(MessageThread.thread_type == thread_type)
        
        if search:
            search_term = f"%{search}%"
            threads_query = threads_query.filter(
                or_(
                    MessageThread.title.ilike(search_term),
                    MessageThread.description.ilike(search_term)
                )
            )
        
        threads_query = threads_query.filter(MessageThread.is_archived == is_archived)
        
        # Ordenar por última actividad
        threads_query = threads_query.order_by(MessageThread.last_activity_at.desc())
        
        # Paginación
        threads_paginated = threads_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Serializar con información adicional
        threads_data = []
        for thread in threads_paginated.items:
            thread_dict = thread_response_schema.dump(thread)
            thread_dict['unread_count'] = thread.get_unread_count(current_user.id)
            thread_dict['last_message'] = thread.get_last_message_dict()
            threads_data.append(thread_dict)
        
        return {
            'threads': threads_data,
            'pagination': {
                'page': threads_paginated.page,
                'pages': threads_paginated.pages,
                'per_page': threads_paginated.per_page,
                'total': threads_paginated.total,
                'has_next': threads_paginated.has_next,
                'has_prev': threads_paginated.has_prev
            }
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener hilos: {str(e)}")
        raise


@messages_bp.route('/threads', methods=['POST'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('create_thread')
@api_response
def create_thread():
    """
    Crear nuevo hilo de conversación
    
    Returns:
        JSON: Hilo creado
    """
    try:
        # Validar datos
        thread_data = thread_create_schema.load(request.get_json())
        
        # Verificar que los participantes existen
        participant_ids = thread_data['participants']
        participants = User.query.filter(User.id.in_(participant_ids)).all()
        
        if len(participants) != len(participant_ids):
            raise BadRequest("Algunos participantes no fueron encontrados")
        
        # Verificar límites de hilos del usuario
        if not _check_thread_creation_limits(current_user.id):
            raise Conflict("Has alcanzado el límite de hilos activos")
        
        # Crear hilo
        thread = MessageThread(
            title=thread_data['title'],
            description=thread_data.get('description'),
            thread_type=thread_data['thread_type'],
            creator_id=current_user.id,
            is_private=thread_data['is_private'],
            project_id=thread_data.get('project_id'),
            meeting_id=thread_data.get('meeting_id'),
            auto_archive_after_days=thread_data.get('auto_archive_after_days')
        )
        
        # Agregar participantes
        for participant in participants:
            thread.participants.append(participant)
        
        db.session.add(thread)
        db.session.commit()
        
        # Crear mensaje de bienvenida del sistema
        welcome_message = Message(
            content=f"Hilo de conversación '{thread.title}' creado por {current_user.full_name}",
            message_type='system',
            sender_id=current_user.id,
            thread_id=thread.id
        )
        
        for participant in participants:
            if participant.id != current_user.id:
                welcome_message.recipients.append(participant)
        
        db.session.add(welcome_message)
        db.session.commit()
        
        # Unir usuarios a la sala de WebSocket
        for participant in participants:
            socketio.emit(
                'thread_created',
                thread_response_schema.dump(thread),
                room=f"user_{participant.id}"
            )
        
        # Enviar notificaciones
        notification_service.send_thread_created_notification(
            thread_id=thread.id,
            participant_ids=[p.id for p in participants if p.id != current_user.id]
        )
        
        # Registrar en analytics
        analytics_service.track_thread_creation(thread.id, current_user.id, len(participants))
        
        return {
            'message': 'Hilo creado exitosamente',
            'thread': thread_response_schema.dump(thread)
        }, 201
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (BadRequest, Conflict) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al crear hilo: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/threads/<uuid:thread_id>', methods=['GET'])
@login_required
@rate_limit(requests=300, window=3600)
@api_response
def get_thread(thread_id: uuid.UUID):
    """
    Obtener detalles de un hilo específico
    
    Args:
        thread_id: UUID del hilo
        
    Returns:
        JSON: Detalles del hilo con mensajes
    """
    try:
        # Obtener hilo
        thread = MessageThread.query.options(
            joinedload(MessageThread.participants),
            joinedload(MessageThread.creator)
        ).get(thread_id)
        
        if not thread:
            raise NotFound("Hilo de conversación no encontrado")
        
        # Verificar permisos
        if current_user not in thread.participants:
            raise Forbidden("No eres participante de este hilo")
        
        # Obtener mensajes del hilo
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        messages_query = Message.query.filter(
            Message.thread_id == thread_id,
            Message.is_deleted == False
        ).options(
            joinedload(Message.sender),
            joinedload(Message.attachments)
        ).order_by(Message.created_at.asc())
        
        messages_paginated = messages_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Serializar hilo
        thread_data = thread_response_schema.dump(thread)
        thread_data['unread_count'] = thread.get_unread_count(current_user.id)
        
        # Serializar mensajes
        messages_data = []
        for message in messages_paginated.items:
            message_dict = message_response_schema.dump(message)
            message_dict['user_read_status'] = message.get_user_read_status(current_user.id)
            messages_data.append(message_dict)
        
        # Marcar mensajes como leídos
        unread_messages = [m for m in messages_paginated.items if not m.is_read_by_user(current_user.id)]
        for message in unread_messages:
            message.mark_as_read(current_user.id)
        
        if unread_messages:
            db.session.commit()
        
        # Registrar actividad
        ActivityLog.log_activity(
            user_id=current_user.id,
            action='view_thread',
            resource_type='thread',
            resource_id=thread_id
        )
        
        return {
            'thread': thread_data,
            'messages': messages_data,
            'pagination': {
                'page': messages_paginated.page,
                'pages': messages_paginated.pages,
                'per_page': messages_paginated.per_page,
                'total': messages_paginated.total,
                'has_next': messages_paginated.has_next,
                'has_prev': messages_paginated.has_prev
            }
        }, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener hilo {thread_id}: {str(e)}")
        raise


@messages_bp.route('/threads/<uuid:thread_id>/participants', methods=['POST'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('add_thread_participant')
@api_response
def add_thread_participant(thread_id: uuid.UUID):
    """
    Agregar participante a un hilo
    
    Args:
        thread_id: UUID del hilo
        
    Returns:
        JSON: Confirmación de participante agregado
    """
    try:
        # Obtener hilo
        thread = MessageThread.query.get(thread_id)
        if not thread:
            raise NotFound("Hilo de conversación no encontrado")
        
        # Verificar permisos
        if current_user not in thread.participants:
            raise Forbidden("No eres participante de este hilo")
        
        if thread.thread_type == 'direct':
            raise BadRequest("No se pueden agregar participantes a conversaciones directas")
        
        # Validar datos
        data = request.get_json()
        if not data or 'user_id' not in data:
            raise BadRequest("user_id es requerido")
        
        user_id = data['user_id']
        user = User.query.get(user_id)
        if not user:
            raise NotFound("Usuario no encontrado")
        
        # Verificar que no esté ya en el hilo
        if user in thread.participants:
            raise Conflict("El usuario ya es participante del hilo")
        
        # Verificar límite de participantes
        if len(thread.participants) >= 100:
            raise Conflict("El hilo ha alcanzado el límite máximo de participantes")
        
        # Agregar participante
        thread.participants.append(user)
        thread.last_activity_at = datetime.utcnow()
        
        # Crear mensaje del sistema
        system_message = Message(
            content=f"{user.full_name} fue agregado al hilo por {current_user.full_name}",
            message_type='system',
            sender_id=current_user.id,
            thread_id=thread_id
        )
        
        for participant in thread.participants:
            if participant.id != current_user.id:
                system_message.recipients.append(participant)
        
        db.session.add(system_message)
        db.session.commit()
        
        # Emitir eventos
        socketio.emit(
            'participant_added',
            {
                'thread_id': str(thread_id),
                'user': {
                    'id': user.id,
                    'name': user.full_name,
                    'email': user.email
                },
                'added_by': current_user.id
            },
            room=f"thread_{thread_id}"
        )
        
        # Notificar al nuevo participante
        socketio.emit(
            'thread_joined',
            thread_response_schema.dump(thread),
            room=f"user_{user.id}"
        )
        
        # Enviar notificación
        notification_service.send_thread_participant_added_notification(
            thread_id=thread_id,
            new_participant_id=user_id,
            added_by=current_user.id
        )
        
        return {
            'message': 'Participante agregado exitosamente',
            'user': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email
            }
        }, 201
        
    except (NotFound, Forbidden, BadRequest, Conflict) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al agregar participante al hilo {thread_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/threads/<uuid:thread_id>/participants/<uuid:user_id>', methods=['DELETE'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('remove_thread_participant')
@api_response
def remove_thread_participant(thread_id: uuid.UUID, user_id: uuid.UUID):
    """
    Remover participante de un hilo
    
    Args:
        thread_id: UUID del hilo
        user_id: UUID del usuario a remover
        
    Returns:
        JSON: Confirmación de remoción
    """
    try:
        # Obtener hilo
        thread = MessageThread.query.get(thread_id)
        if not thread:
            raise NotFound("Hilo de conversación no encontrado")
        
        # Verificar permisos
        if current_user not in thread.participants:
            raise Forbidden("No eres participante de este hilo")
        
        if thread.thread_type == 'direct':
            raise BadRequest("No se pueden remover participantes de conversaciones directas")
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user or user not in thread.participants:
            raise NotFound("El usuario no es participante del hilo")
        
        # Verificar permisos de remoción
        can_remove = (
            current_user.id == user_id or  # Usuario se remueve a sí mismo
            thread.creator_id == current_user.id or  # Creador del hilo
            current_user.has_permission('manage_threads')  # Permisos administrativos
        )
        
        if not can_remove:
            raise Forbidden("No tienes permisos para remover este participante")
        
        # No permitir remover al creador
        if user_id == thread.creator_id and current_user.id != user_id:
            raise BadRequest("No se puede remover al creador del hilo")
        
        # Remover participante
        thread.participants.remove(user)
        thread.last_activity_at = datetime.utcnow()
        
        # Crear mensaje del sistema
        if current_user.id == user_id:
            content = f"{user.full_name} abandonó el hilo"
        else:
            content = f"{user.full_name} fue removido del hilo por {current_user.full_name}"
        
        system_message = Message(
            content=content,
            message_type='system',
            sender_id=current_user.id,
            thread_id=thread_id
        )
        
        for participant in thread.participants:
            if participant.id != current_user.id:
                system_message.recipients.append(participant)
        
        db.session.add(system_message)
        db.session.commit()
        
        # Emitir eventos
        socketio.emit(
            'participant_removed',
            {
                'thread_id': str(thread_id),
                'user_id': str(user_id),
                'removed_by': current_user.id
            },
            room=f"thread_{thread_id}"
        )
        
        # Notificar al usuario removido
        socketio.emit(
            'thread_left',
            {'thread_id': str(thread_id)},
            room=f"user_{user_id}"
        )
        
        return {
            'message': 'Participante removido exitosamente'
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al remover participante del hilo {thread_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/search', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)
@api_response
def search_messages():
    """
    Búsqueda avanzada de mensajes
    
    Returns:
        JSON: Resultados de búsqueda
    """
    try:
        query = request.args.get('q', '').strip()
        if not query:
            raise BadRequest("Consulta de búsqueda requerida")
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        thread_id = request.args.get('thread_id')
        message_type = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Construir query de búsqueda
        search_query = Message.query.filter(
            or_(
                Message.content.ilike(f"%{query}%"),
                Message.subject.ilike(f"%{query}%")
            ),
            Message.is_deleted == False
        )
        
        # Filtrar por permisos del usuario
        user_messages_filter = or_(
            Message.sender_id == current_user.id,
            Message.recipients.any(User.id == current_user.id),
            Message.thread.has(MessageThread.participants.any(User.id == current_user.id))
        )
        search_query = search_query.filter(user_messages_filter)
        
        # Aplicar filtros adicionales
        if thread_id:
            search_query = search_query.filter(Message.thread_id == thread_id)
        
        if message_type:
            search_query = search_query.filter(Message.message_type == message_type)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                search_query = search_query.filter(Message.created_at >= start_dt)
            except ValueError:
                raise BadRequest("Formato de fecha de inicio inválido")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                search_query = search_query.filter(Message.created_at <= end_dt)
            except ValueError:
                raise BadRequest("Formato de fecha de fin inválido")
        
        # Ordenar por relevancia y fecha
        search_query = search_query.order_by(Message.created_at.desc())
        
        # Paginación
        results_paginated = search_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Serializar resultados
        messages_data = []
        for message in results_paginated.items:
            message_dict = message_response_schema.dump(message)
            message_dict['content_preview'] = _get_content_preview(message.content, message.message_type)
            # Resaltar términos de búsqueda
            message_dict['highlighted_content'] = _highlight_search_terms(message.content, query)
            messages_data.append(message_dict)
        
        # Registrar búsqueda en analytics
        analytics_service.track_message_search(current_user.id, query, len(messages_data))
        
        return {
            'query': query,
            'messages': messages_data,
            'pagination': {
                'page': results_paginated.page,
                'pages': results_paginated.pages,
                'per_page': results_paginated.per_page,
                'total': results_paginated.total,
                'has_next': results_paginated.has_next,
                'has_prev': results_paginated.has_prev
            }
        }, 200
        
    except (BadRequest,) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error en búsqueda de mensajes: {str(e)}")
        raise


@messages_bp.route('/unread', methods=['GET'])
@login_required
@rate_limit(requests=200, window=3600)
@cache.cached(timeout=60)  # Cache for 1 minute
@api_response
def get_unread_messages():
    """
    Obtener mensajes no leídos del usuario
    
    Returns:
        JSON: Lista de mensajes no leídos
    """
    try:
        limit = int(request.args.get('limit', 50))
        
        # Obtener mensajes no leídos
        unread_query = Message.query.filter(
            Message.recipients.any(User.id == current_user.id),
            ~Message.read_by.any(
                and_(
                    Message.read_by.c.user_id == current_user.id,
                    Message.read_by.c.is_read == True
                )
            ),
            Message.is_deleted == False
        ).options(
            joinedload(Message.sender),
            joinedload(Message.thread)
        ).order_by(Message.created_at.desc()).limit(limit)
        
        unread_messages = unread_query.all()
        
        # Agrupar por hilo
        threads_unread = {}
        for message in unread_messages:
            thread_id = str(message.thread_id)
            if thread_id not in threads_unread:
                threads_unread[thread_id] = {
                    'thread': thread_response_schema.dump(message.thread),
                    'messages': [],
                    'count': 0
                }
            
            message_dict = message_response_schema.dump(message)
            message_dict['content_preview'] = _get_content_preview(message.content, message.message_type)
            threads_unread[thread_id]['messages'].append(message_dict)
            threads_unread[thread_id]['count'] += 1
        
        return {
            'unread_threads': list(threads_unread.values()),
            'total_unread': len(unread_messages),
            'threads_with_unread': len(threads_unread)
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener mensajes no leídos: {str(e)}")
        raise


@messages_bp.route('/mark-all-read', methods=['POST'])
@login_required
@rate_limit(requests=10, window=3600)
@log_activity('mark_all_messages_read')
@api_response
def mark_all_messages_read():
    """
    Marcar todos los mensajes como leídos
    
    Returns:
        JSON: Confirmación
    """
    try:
        thread_id = request.json.get('thread_id') if request.json else None
        
        # Construir query de mensajes no leídos
        unread_query = Message.query.filter(
            Message.recipients.any(User.id == current_user.id),
            ~Message.read_by.any(
                and_(
                    Message.read_by.c.user_id == current_user.id,
                    Message.read_by.c.is_read == True
                )
            ),
            Message.is_deleted == False
        )
        
        if thread_id:
            unread_query = unread_query.filter(Message.thread_id == thread_id)
        
        unread_messages = unread_query.all()
        
        # Marcar como leídos
        marked_count = 0
        for message in unread_messages:
            message.mark_as_read(current_user.id)
            marked_count += 1
        
        db.session.commit()
        
        # Emitir evento de mensajes leídos
        if thread_id:
            socketio.emit(
                'messages_read',
                {
                    'thread_id': thread_id,
                    'read_by': current_user.id,
                    'count': marked_count
                },
                room=f"thread_{thread_id}"
            )
        
        return {
            'message': f'{marked_count} mensajes marcados como leídos',
            'marked_count': marked_count
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al marcar mensajes como leídos: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/<uuid:message_id>/reactions', methods=['POST'])
@login_required
@rate_limit(requests=100, window=3600)
@log_activity('react_to_message')
@api_response
def react_to_message(message_id: uuid.UUID):
    """
    Agregar reacción a un mensaje
    
    Args:
        message_id: UUID del mensaje
        
    Returns:
        JSON: Confirmación de reacción agregada
    """
    try:
        # Obtener mensaje
        message = Message.query.get(message_id)
        if not message:
            raise NotFound("Mensaje no encontrado")
        
        # Verificar permisos
        if not check_message_access(current_user, message, 'react'):
            raise Forbidden("No tienes permisos para reaccionar a este mensaje")
        
        # Validar datos
        data = request.get_json()
        if not data or 'emoji' not in data:
            raise BadRequest("Emoji de reacción requerido")
        
        emoji = data['emoji']
        allowed_emojis = ['👍', '👎', '❤️', '😂', '😮', '😢', '😡', '🎉', '👏', '🔥']
        
        if emoji not in allowed_emojis:
            raise BadRequest("Emoji de reacción no permitido")
        
        # Agregar o quitar reacción
        reaction_added = message.toggle_reaction(current_user.id, emoji)
        db.session.commit()
        
        # Emitir evento de reacción
        socketio.emit(
            'message_reaction',
            {
                'message_id': str(message_id),
                'user_id': current_user.id,
                'emoji': emoji,
                'action': 'added' if reaction_added else 'removed'
            },
            room=f"thread_{message.thread_id}"
        )
        
        # Obtener reacciones actualizadas
        reactions = message.get_reactions_summary()
        
        return {
            'message': 'Reacción actualizada',
            'action': 'added' if reaction_added else 'removed',
            'emoji': emoji,
            'reactions': reactions
        }, 200
        
    except (NotFound, Forbidden, BadRequest) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al reaccionar al mensaje {message_id}: {str(e)}")
        db.session.rollback()
        raise


@messages_bp.route('/statistics', methods=['GET'])
@login_required
@require_permission('view_message_stats')
@rate_limit(requests=20, window=3600)
@cache.cached(timeout=600)  # Cache for 10 minutes
@api_response
def get_message_statistics():
    """
    Obtener estadísticas de mensajería
    
    Returns:
        JSON: Estadísticas detalladas de mensajes
    """
    try:
        period = request.args.get('period', 'month')  # week, month, quarter, year
        
        # Obtener estadísticas
        stats = analytics_service.get_message_statistics(
            user=current_user,
            period=period
        )
        
        return {
            'statistics': stats,
            'period': period,
            'generated_at': datetime.utcnow().isoformat()
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas de mensajes: {str(e)}")
        raise


@messages_bp.route('/export', methods=['POST'])
@login_required
@rate_limit(requests=5, window=3600)
@log_activity('export_messages')
@api_response
def export_messages():
    """
    Exportar mensajes a archivo
    
    Returns:
        JSON: URL de descarga del archivo exportado
    """
    try:
        # Validar datos
        data = request.get_json()
        export_format = data.get('format', 'json')  # json, csv, pdf
        thread_id = data.get('thread_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        include_attachments = data.get('include_attachments', False)
        
        if export_format not in ['json', 'csv', 'pdf']:
            raise BadRequest("Formato de exportación no válido")
        
        # Construir query de mensajes
        messages_query = Message.query.filter(
            or_(
                Message.sender_id == current_user.id,
                Message.recipients.any(User.id == current_user.id),
                Message.thread.has(MessageThread.participants.any(User.id == current_user.id))
            ),
            Message.is_deleted == False
        )
        
        if thread_id:
            messages_query = messages_query.filter(Message.thread_id == thread_id)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                messages_query = messages_query.filter(Message.created_at >= start_dt)
            except ValueError:
                raise BadRequest("Formato de fecha de inicio inválido")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                messages_query = messages_query.filter(Message.created_at <= end_dt)
            except ValueError:
                raise BadRequest("Formato de fecha de fin inválido")
        
        messages = messages_query.order_by(Message.created_at.asc()).all()
        
        if not messages:
            raise BadRequest("No hay mensajes para exportar")
        
        # Verificar límite de exportación
        if len(messages) > 10000:
            raise BadRequest("Demasiados mensajes para exportar. Refina los filtros.")
        
        # Generar archivo de exportación
        from app.tasks.export_tasks import export_messages_task
        
        task = export_messages_task.delay(
            user_id=current_user.id,
            message_ids=[m.id for m in messages],
            export_format=export_format,
            include_attachments=include_attachments
        )
        
        return {
            'message': 'Exportación iniciada',
            'task_id': task.id,
            'estimated_completion': datetime.utcnow() + timedelta(minutes=5)
        }, 202
        
    except (BadRequest,) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al exportar mensajes: {str(e)}")
        raise


# Funciones auxiliares privadas

def _get_content_preview(content: str, message_type: str, max_length: int = 100) -> str:
    """Obtener preview del contenido del mensaje"""
    if message_type == 'text':
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."
    elif message_type == 'file':
        return "📎 Archivo adjunto"
    elif message_type == 'image':
        return "🖼️ Imagen"
    elif message_type == 'audio':
        return "🎵 Audio"
    elif message_type == 'video':
        return "🎥 Video"
    elif message_type == 'system':
        return content
    else:
        return "Mensaje"


def _mark_messages_as_delivered(messages: List[Message]):
    """Marcar mensajes como entregados"""
    for message in messages:
        if not message.delivered_at and current_user in message.recipients:
            message.delivered_at = datetime.utcnow()
    
    if messages:
        db.session.commit()


def _get_user_unread_count() -> int:
    """Obtener cantidad de mensajes no leídos del usuario"""
    return Message.query.filter(
        Message.recipients.any(User.id == current_user.id),
        ~Message.read_by.any(
            and_(
                Message.read_by.c.user_id == current_user.id,
                Message.read_by.c.is_read == True
            )
        ),
        Message.is_deleted == False
    ).count()


def _validate_file(file) -> bool:
    """Validar archivo subido"""
    if not file.filename:
        return False
    
    extension = get_file_extension(file.filename).lower()
    
    # Verificar extensión
    allowed_extensions = []
    for file_type, extensions in ALLOWED_FILE_TYPES.items():
        allowed_extensions.extend(extensions)
    
    return extension in allowed_extensions


def _get_file_type(extension: str) -> str:
    """Determinar tipo de archivo basado en extensión"""
    extension = extension.lower()
    
    for file_type, extensions in ALLOWED_FILE_TYPES.items():
        if extension in extensions:
            return file_type
    
    return 'other'


def _get_or_create_direct_thread(user1_id: uuid.UUID, user2_id: uuid.UUID) -> MessageThread:
    """Obtener o crear hilo de conversación directa"""
    # Buscar hilo existente
    existing_thread = MessageThread.query.filter(
        MessageThread.thread_type == 'direct',
        MessageThread.participants.any(User.id == user1_id),
        MessageThread.participants.any(User.id == user2_id)
    ).first()
    
    if existing_thread:
        return existing_thread
    
    # Crear nuevo hilo
    user1 = User.query.get(user1_id)
    user2 = User.query.get(user2_id)
    
    thread = MessageThread(
        title=f"Conversación entre {user1.full_name} y {user2.full_name}",
        thread_type='direct',
        creator_id=user1_id,
        is_private=True
    )
    
    thread.participants.extend([user1, user2])
    db.session.add(thread)
    db.session.flush()
    
    return thread


def _create_group_thread(participants: List[User]) -> MessageThread:
    """Crear hilo de grupo"""
    participant_names = [p.full_name for p in participants[:3]]
    if len(participants) > 3:
        title = f"Grupo: {', '.join(participant_names)} y {len(participants) - 3} más"
    else:
        title = f"Grupo: {', '.join(participant_names)}"
    
    thread = MessageThread(
        title=title,
        thread_type='group',
        creator_id=current_user.id,
        is_private=False
    )
    
    thread.participants.extend(participants)
    db.session.add(thread)
    db.session.flush()
    
    return thread


def _check_sending_limits(user_id: uuid.UUID) -> bool:
    """Verificar límites de envío de mensajes"""
    # Verificar mensajes enviados en la última hora
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_messages = Message.query.filter(
        Message.sender_id == user_id,
        Message.created_at >= one_hour_ago
    ).count()
    
    # Límite de 200 mensajes por hora para usuarios normales
    limit = 200
    if current_user.has_permission('unlimited_messages'):
        limit = 1000
    
    return recent_messages < limit


def _check_thread_creation_limits(user_id: uuid.UUID) -> bool:
    """Verificar límites de creación de hilos"""
    # Verificar hilos activos del usuario
    active_threads = MessageThread.query.filter(
        MessageThread.creator_id == user_id,
        MessageThread.is_archived == False
    ).count()
    
    # Límite de 50 hilos activos para usuarios normales
    limit = 50
    if current_user.has_permission('unlimited_threads'):
        limit = 200
    
    return active_threads < limit


def _send_message_notifications(message: Message):
    """Enviar notificaciones de nuevo mensaje"""
    # Notificaciones push
    for recipient in message.recipients:
        if recipient.notification_preferences.get('messages', True):
            notification_service.send_new_message_notification(
                recipient_id=recipient.id,
                message_id=message.id
            )
    
    # Emails (solo si el usuario no está activo)
    for recipient in message.recipients:
        if (recipient.notification_preferences.get('email_messages', False) and
            not recipient.is_online):
            email_service.send_new_message_email(
                recipient=recipient,
                message=message
            )


def _highlight_search_terms(content: str, query: str) -> str:
    """Resaltar términos de búsqueda en el contenido"""
    import re
    
    # Escapar caracteres especiales en la consulta
    escaped_query = re.escape(query)
    
    # Resaltar términos (case insensitive)
    highlighted = re.sub(
        f'({escaped_query})',
        r'<mark>\1</mark>',
        content,
        flags=re.IGNORECASE
    )
    
    return highlighted


# Manejo de errores específicos del blueprint
@messages_bp.errorhandler(ValidationException)
def handle_validation_exception(e):
    return jsonify({
        'error': 'Validation Error',
        'message': str(e),
        'status_code': 400
    }), 400


@messages_bp.errorhandler(BusinessException)
def handle_business_exception(e):
    return jsonify({
        'error': 'Business Logic Error',
        'message': str(e),
        'status_code': 400
    }), 400


@messages_bp.errorhandler(StorageException)
def handle_storage_exception(e):
    return jsonify({
        'error': 'Storage Error',
        'message': str(e),
        'status_code': 503
    }), 503


# WebSocket events para mensajería en tiempo real
@socketio.on('join_thread')
def on_join_thread(data):
    """Usuario se une a una sala de hilo"""
    thread_id = data.get('thread_id')
    if thread_id:
        # Verificar permisos
        thread = MessageThread.query.get(thread_id)
        if thread and current_user in thread.participants:
            join_room(f"thread_{thread_id}")
            emit('joined_thread', {'thread_id': thread_id})


@socketio.on('leave_thread')
def on_leave_thread(data):
    """Usuario abandona una sala de hilo"""
    thread_id = data.get('thread_id')
    if thread_id:
        leave_room(f"thread_{thread_id}")
        emit('left_thread', {'thread_id': thread_id})


@socketio.on('typing_start')
def on_typing_start(data):
    """Usuario comenzó a escribir"""
    thread_id = data.get('thread_id')
    if thread_id:
        emit('user_typing', {
            'thread_id': thread_id,
            'user_id': current_user.id,
            'user_name': current_user.full_name,
            'typing': True
        }, room=f"thread_{thread_id}", include_self=False)


@socketio.on('typing_stop')
def on_typing_stop(data):
    """Usuario dejó de escribir"""
    thread_id = data.get('thread_id')
    if thread_id:
        emit('user_typing', {
            'thread_id': thread_id,
            'user_id': current_user.id,
            'typing': False
        }, room=f"thread_{thread_id}", include_self=False)


# Registro de hooks del blueprint
@messages_bp.before_request
def before_request():
    """Ejecutar antes de cada request"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Log de request para audit
    current_app.logger.info(
        f"Messages API Request: {request.method} {request.path} by user {current_user.id}"
    )


@messages_bp.after_request
def after_request(response):
    """Ejecutar después de cada request"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-API-Version'] = '1.0'
    
    return response