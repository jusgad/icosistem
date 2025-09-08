"""
Vistas para el sistema de mensajería de aliados/mentores.

Este módulo maneja todas las operaciones de mensajería entre aliados y emprendedores,
incluyendo chat en tiempo real, gestión de conversaciones y notificaciones.
"""

import os
import uuid
import mimetypes
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file, session
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db, socketio
from app.models.user import User
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.message import Message, MessageStatus, MessageThread
from app.models.document import Document
from app.core.exceptions import ValidationError, PermissionError
from app.core.permissions import require_role, require_ally_access
from app.utils.decorators import handle_db_errors, log_activity, rate_limit
from app.utils.validators import validate_file_type, validate_message_content
from app.utils.formatters import format_file_size, format_datetime
from app.utils.file_utils import save_upload_file, get_file_extension, is_image_file
from app.utils.string_utils import truncate_text, sanitize_html, extract_mentions
from app.services.notification_service import NotificationService
from app.services.file_storage import FileStorageService
from app.sockets.handlers.chat import emit_new_message, emit_message_status_update

# Blueprint para las vistas de mensajería de aliados
ally_messages_bp = Blueprint('ally_messages', __name__, url_prefix='/ally/messages')

# Configuraciones
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg',
    'zip', 'rar', '7z',
    'mp3', 'wav', 'mp4', 'avi', 'mov'
}
MESSAGES_PER_PAGE = 50


@ally_messages_bp.route('/')
@login_required
@require_role('ally')
@log_activity('view_messages_dashboard')
def index():
    """
    Dashboard principal de mensajería para aliados.
    
    Muestra lista de conversaciones activas, mensajes no leídos
    y accesos rápidos a funcionalidades principales.
    """
    try:
        ally = current_user.ally
        
        # Obtener parámetros de filtrado
        filter_type = request.args.get('filter', 'all')  # all, unread, important
        search_query = request.args.get('search', '').strip()
        
        # Consulta base de conversaciones del aliado
        conversations_query = (
            db.session.query(MessageThread)
            .filter(
                or_(
                    MessageThread.participant1_id == current_user.id,
                    MessageThread.participant2_id == current_user.id
                )
            )
            .options(
                joinedload(MessageThread.participant1),
                joinedload(MessageThread.participant2),
                joinedload(MessageThread.last_message)
            )
        )
        
        # Aplicar filtros
        if filter_type == 'unread':
            conversations_query = conversations_query.filter(
                MessageThread.unread_count > 0
            )
        elif filter_type == 'important':
            conversations_query = conversations_query.filter(
                MessageThread.is_important == True
            )
        
        # Búsqueda por nombre de participante
        if search_query:
            conversations_query = conversations_query.join(
                User, 
                or_(
                    MessageThread.participant1_id == User.id,
                    MessageThread.participant2_id == User.id
                )
            ).filter(
                and_(
                    User.id != current_user.id,
                    User.name.ilike(f'%{search_query}%')
                )
            )
        
        # Ordenar por última actividad
        conversations = (
            conversations_query
            .order_by(desc(MessageThread.last_message_at))
            .limit(50)
            .all()
        )
        
        # Estadísticas rápidas
        total_unread = sum(conv.unread_count for conv in conversations)
        
        recent_messages = (
            Message.query
            .join(MessageThread)
            .filter(
                or_(
                    MessageThread.participant1_id == current_user.id,
                    MessageThread.participant2_id == current_user.id
                ),
                Message.receiver_id == current_user.id,
                Message.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
            )
            .order_by(desc(Message.created_at))
            .limit(10)
            .all()
        )
        
        # Emprendedores disponibles para nueva conversación
        available_entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(
                Project.ally_id == ally.id,
                Project.status.in_(['active', 'in_progress'])
            )
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        return render_template(
            'ally/messages/dashboard.html',
            conversations=conversations,
            total_unread=total_unread,
            recent_messages=recent_messages,
            available_entrepreneurs=available_entrepreneurs,
            current_filter=filter_type,
            search_query=search_query,
            format_datetime=format_datetime,
            truncate_text=truncate_text
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de mensajes: {str(e)}")
        flash('Error al cargar el dashboard de mensajes.', 'error')
        return redirect(url_for('ally.dashboard'))


@ally_messages_bp.route('/conversation/<int:thread_id>')
@login_required
@require_role('ally')
@log_activity('view_conversation')
def conversation(thread_id):
    """
    Vista de conversación individual con historial de mensajes.
    
    Permite ver todos los mensajes de una conversación específica
    y enviar nuevos mensajes en tiempo real.
    """
    try:
        ally = current_user.ally
        
        # Obtener conversación
        thread = MessageThread.query.get_or_404(thread_id)
        
        # Verificar permisos de acceso
        if not _ally_has_access_to_thread(ally, thread):
            abort(403)
        
        # Obtener el otro participante
        other_participant = (
            thread.participant1 if thread.participant2_id == current_user.id 
            else thread.participant2
        )
        
        # Verificar que el otro participante sea un emprendedor asignado
        if not _ally_has_access_to_user(ally, other_participant):
            abort(403)
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        
        # Obtener mensajes de la conversación
        messages_query = (
            Message.query
            .filter(Message.thread_id == thread_id)
            .order_by(desc(Message.created_at))
        )
        
        pagination = messages_query.paginate(
            page=page,
            per_page=MESSAGES_PER_PAGE,
            error_out=False
        )
        
        messages = list(reversed(pagination.items))  # Mostrar en orden cronológico
        
        # Marcar mensajes como leídos
        _mark_messages_as_read(thread_id, current_user.id)
        
        # Información del proyecto compartido (si existe)
        shared_project = (
            Project.query
            .filter(
                Project.ally_id == ally.id,
                Project.entrepreneur_id == other_participant.id
            )
            .first()
        )
        
        # Archivos compartidos recientes
        recent_attachments = (
            db.session.query(Document)
            .join(Message, Message.id == Document.message_id)
            .filter(
                Message.thread_id == thread_id,
                Document.file_type.in_(['image', 'document'])
            )
            .order_by(desc(Document.created_at))
            .limit(10)
            .all()
        )
        
        return render_template(
            'ally/messages/conversation.html',
            thread=thread,
            other_participant=other_participant,
            messages=messages,
            pagination=pagination,
            shared_project=shared_project,
            recent_attachments=recent_attachments,
            allowed_extensions=ALLOWED_EXTENSIONS,
            max_file_size=MAX_FILE_SIZE,
            format_datetime=format_datetime,
            format_file_size=format_file_size,
            is_image_file=is_image_file
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar conversación: {str(e)}")
        flash('Error al cargar la conversación.', 'error')
        return redirect(url_for('ally_messages.index'))


@ally_messages_bp.route('/send', methods=['POST'])
@login_required
@require_role('ally')
@rate_limit('30 per minute')
@handle_db_errors
@log_activity('send_message')
def send_message():
    """
    Envía un nuevo mensaje en una conversación.
    
    Maneja tanto mensajes de texto como archivos adjuntos,
    con validaciones de seguridad y notificaciones en tiempo real.
    """
    try:
        ally = current_user.ally
        
        # Obtener datos del formulario
        thread_id = request.form.get('thread_id', type=int)
        recipient_id = request.form.get('recipient_id', type=int)
        content = request.form.get('content', '').strip()
        is_important = request.form.get('is_important') == 'on'
        
        # Validar que se proporcione contenido o archivo
        files = request.files.getlist('attachments')
        has_files = any(f.filename for f in files)
        
        if not content and not has_files:
            return jsonify({
                'success': False,
                'error': 'Debe proporcionar contenido de mensaje o archivo adjunto.'
            }), 400
        
        # Obtener o crear conversación
        if thread_id:
            thread = MessageThread.query.get(thread_id)
            if not thread or not _ally_has_access_to_thread(ally, thread):
                return jsonify({
                    'success': False,
                    'error': 'Conversación no encontrada o sin permisos.'
                }), 403
            
            recipient = (
                thread.participant1 if thread.participant2_id == current_user.id
                else thread.participant2
            )
        else:
            # Crear nueva conversación
            if not recipient_id:
                return jsonify({
                    'success': False,
                    'error': 'Debe especificar un destinatario.'
                }), 400
            
            recipient = User.query.get(recipient_id)
            if not recipient or not _ally_has_access_to_user(ally, recipient):
                return jsonify({
                    'success': False,
                    'error': 'Destinatario no válido o sin permisos.'
                }), 403
            
            # Buscar conversación existente
            thread = (
                MessageThread.query
                .filter(
                    or_(
                        and_(
                            MessageThread.participant1_id == current_user.id,
                            MessageThread.participant2_id == recipient_id
                        ),
                        and_(
                            MessageThread.participant1_id == recipient_id,
                            MessageThread.participant2_id == current_user.id
                        )
                    )
                )
                .first()
            )
            
            # Crear nueva conversación si no existe
            if not thread:
                thread = MessageThread(
                    participant1_id=current_user.id,
                    participant2_id=recipient_id,
                    created_by=current_user.id
                )
                db.session.add(thread)
                db.session.flush()  # Para obtener el ID
        
        # Validar y sanitizar contenido
        if content:
            if len(content) > 5000:
                return jsonify({
                    'success': False,
                    'error': 'El mensaje es demasiado largo (máximo 5000 caracteres).'
                }), 400
            
            content = sanitize_html(content)
        
        # Crear el mensaje
        message = Message(
            thread_id=thread.id,
            sender_id=current_user.id,
            receiver_id=recipient.id,
            content=content,
            message_type='text' if not has_files else 'mixed',
            is_important=is_important,
            status='sent'
        )
        
        db.session.add(message)
        db.session.flush()  # Para obtener el ID del mensaje
        
        # Procesar archivos adjuntos
        attachments_data = []
        if has_files:
            for file in files:
                if file.filename:
                    try:
                        attachment = _process_file_attachment(file, message.id)
                        if attachment:
                            attachments_data.append({
                                'id': attachment.id,
                                'filename': attachment.original_filename,
                                'file_type': attachment.file_type,
                                'file_size': attachment.file_size,
                                'download_url': url_for(
                                    'ally_messages.download_attachment',
                                    attachment_id=attachment.id
                                )
                            })
                    except Exception as e:
                        current_app.logger.error(f"Error procesando archivo: {str(e)}")
                        continue
        
        # Actualizar información de la conversación
        thread.last_message_id = message.id
        thread.last_message_at = datetime.now(timezone.utc)
        thread.updated_at = datetime.now(timezone.utc)
        
        # Incrementar contador de no leídos para el destinatario
        if thread.participant1_id == recipient.id:
            thread.unread_count_p1 += 1
        else:
            thread.unread_count_p2 += 1
        
        db.session.commit()
        
        # Emitir evento WebSocket
        emit_new_message(thread.id, {
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': current_user.name,
            'content': message.content,
            'is_important': message.is_important,
            'created_at': message.created_at.isoformat(),
            'attachments': attachments_data
        })
        
        # Enviar notificación push/email
        if current_app.config.get('ENABLE_NOTIFICATIONS', True):
            NotificationService.send_new_message_notification(
                recipient, current_user, message
            )
        
        # Extraer menciones y enviar notificaciones específicas
        if content:
            mentions = extract_mentions(content)
            for mention in mentions:
                mentioned_user = User.query.filter_by(username=mention).first()
                if mentioned_user and mentioned_user.id != current_user.id:
                    NotificationService.send_mention_notification(
                        mentioned_user, current_user, message
                    )
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'created_at': format_datetime(message.created_at),
                'attachments': attachments_data,
                'is_important': message.is_important
            },
            'thread_id': thread.id
        })
        
    except RequestEntityTooLarge:
        return jsonify({
            'success': False,
            'error': f'Archivo demasiado grande. Máximo permitido: {format_file_size(MAX_FILE_SIZE)}'
        }), 413
    except Exception as e:
        current_app.logger.error(f"Error al enviar mensaje: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno al enviar el mensaje.'
        }), 500


@ally_messages_bp.route('/mark-read', methods=['POST'])
@login_required
@require_role('ally')
@handle_db_errors
def mark_as_read():
    """
    Marca mensajes específicos como leídos.
    
    Actualiza el estado de lectura y emite eventos WebSocket
    para notificar cambios en tiempo real.
    """
    try:
        data = request.get_json()
        thread_id = data.get('thread_id')
        message_ids = data.get('message_ids', [])
        
        if not thread_id:
            return jsonify({'success': False, 'error': 'Thread ID requerido'}), 400
        
        # Verificar acceso a la conversación
        thread = MessageThread.query.get(thread_id)
        if not thread or not _ally_has_access_to_thread(current_user.ally, thread):
            return jsonify({'success': False, 'error': 'Sin permisos'}), 403
        
        # Marcar mensajes como leídos
        if message_ids:
            # Marcar mensajes específicos
            messages_updated = (
                Message.query
                .filter(
                    Message.id.in_(message_ids),
                    Message.receiver_id == current_user.id,
                    Message.status != 'read'
                )
                .update({
                    'status': 'read',
                    'read_at': datetime.now(timezone.utc)
                }, synchronize_session=False)
            )
        else:
            # Marcar todos los mensajes no leídos de la conversación
            messages_updated = (
                Message.query
                .filter(
                    Message.thread_id == thread_id,
                    Message.receiver_id == current_user.id,
                    Message.status != 'read'
                )
                .update({
                    'status': 'read',
                    'read_at': datetime.now(timezone.utc)
                }, synchronize_session=False)
            )
        
        # Actualizar contador de no leídos en la conversación
        if thread.participant1_id == current_user.id:
            thread.unread_count_p1 = 0
        else:
            thread.unread_count_p2 = 0
        
        db.session.commit()
        
        # Emitir evento WebSocket de actualización de estado
        emit_message_status_update(thread_id, {
            'reader_id': current_user.id,
            'messages_read': messages_updated,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return jsonify({
            'success': True,
            'messages_updated': messages_updated
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al marcar como leído: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@ally_messages_bp.route('/search')
@login_required
@require_role('ally')
@log_activity('search_messages')
def search():
    """
    Búsqueda avanzada de mensajes y conversaciones.
    
    Permite buscar por contenido, fecha, participante y tipo de archivo.
    """
    try:
        ally = current_user.ally
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')  # all, messages, files
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        participant_id = request.args.get('participant_id', type=int)
        page = request.args.get('page', 1, type=int)
        
        if not query and not participant_id:
            flash('Ingrese un término de búsqueda o seleccione un participante.', 'warning')
            return redirect(url_for('ally_messages.index'))
        
        results = []
        total_results = 0
        
        if search_type in ['all', 'messages']:
            # Búsqueda en mensajes
            messages_query = (
                Message.query
                .join(MessageThread)
                .filter(
                    or_(
                        MessageThread.participant1_id == current_user.id,
                        MessageThread.participant2_id == current_user.id
                    )
                )
            )
            
            if query:
                messages_query = messages_query.filter(
                    Message.content.ilike(f'%{query}%')
                )
            
            if participant_id:
                messages_query = messages_query.filter(
                    or_(
                        Message.sender_id == participant_id,
                        Message.receiver_id == participant_id
                    )
                )
            
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, '%Y-%m-%d')
                    messages_query = messages_query.filter(
                        Message.created_at >= from_date
                    )
                except ValueError:
                    pass
            
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, '%Y-%m-%d')
                    messages_query = messages_query.filter(
                        Message.created_at <= to_date + timedelta(days=1)
                    )
                except ValueError:
                    pass
            
            messages_pagination = messages_query.order_by(
                desc(Message.created_at)
            ).paginate(
                page=page,
                per_page=20,
                error_out=False
            )
            
            results.extend([{
                'type': 'message',
                'item': msg,
                'thread': msg.thread,
                'highlight': _highlight_search_term(msg.content, query) if query else msg.content
            } for msg in messages_pagination.items])
            
            total_results += messages_pagination.total
        
        if search_type in ['all', 'files']:
            # Búsqueda en archivos
            files_query = (
                Document.query
                .join(Message, Message.id == Document.message_id)
                .join(MessageThread, MessageThread.id == Message.thread_id)
                .filter(
                    or_(
                        MessageThread.participant1_id == current_user.id,
                        MessageThread.participant2_id == current_user.id
                    )
                )
            )
            
            if query:
                files_query = files_query.filter(
                    or_(
                        Document.original_filename.ilike(f'%{query}%'),
                        Document.description.ilike(f'%{query}%')
                    )
                )
            
            if participant_id:
                files_query = files_query.filter(
                    or_(
                        Message.sender_id == participant_id,
                        Message.receiver_id == participant_id
                    )
                )
            
            files = files_query.order_by(desc(Document.created_at)).limit(10).all()
            
            results.extend([{
                'type': 'file',
                'item': doc,
                'message': doc.message,
                'thread': doc.message.thread
            } for doc in files])
        
        # Obtener participantes disponibles para filtro
        available_participants = (
            User.query
            .join(
                MessageThread,
                or_(
                    MessageThread.participant1_id == User.id,
                    MessageThread.participant2_id == User.id
                )
            )
            .filter(
                or_(
                    MessageThread.participant1_id == current_user.id,
                    MessageThread.participant2_id == current_user.id
                ),
                User.id != current_user.id
            )
            .distinct()
            .order_by(User.name)
            .all()
        )
        
        return render_template(
            'ally/messages/search.html',
            results=results,
            query=query,
            search_type=search_type,
            total_results=total_results,
            available_participants=available_participants,
            current_filters={
                'q': query,
                'type': search_type,
                'date_from': date_from,
                'date_to': date_to,
                'participant_id': participant_id
            },
            format_datetime=format_datetime,
            truncate_text=truncate_text
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en búsqueda de mensajes: {str(e)}")
        flash('Error al realizar la búsqueda.', 'error')
        return redirect(url_for('ally_messages.index'))


@ally_messages_bp.route('/download/<int:attachment_id>')
@login_required
@require_role('ally')
@log_activity('download_attachment')
def download_attachment(attachment_id):
    """
    Descarga un archivo adjunto de un mensaje.
    
    Verifica permisos de acceso antes de permitir la descarga.
    """
    try:
        ally = current_user.ally
        
        # Obtener el documento
        document = Document.query.get_or_404(attachment_id)
        
        # Verificar permisos de acceso a través del mensaje y conversación
        if document.message_id:
            message = document.message
            thread = message.thread
            
            if not _ally_has_access_to_thread(ally, thread):
                abort(403)
        else:
            abort(403)
        
        # Verificar que el archivo existe
        if not os.path.exists(document.file_path):
            flash('El archivo solicitado no existe.', 'error')
            return redirect(url_for('ally_messages.index'))
        
        # Registrar descarga
        current_app.logger.info(
            f"Descarga de archivo por ally {ally.id}: "
            f"documento {document.id}, archivo {document.original_filename}"
        )
        
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=document.original_filename,
            mimetype=document.mime_type or 'application/octet-stream'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al descargar archivo: {str(e)}")
        flash('Error al descargar el archivo.', 'error')
        return redirect(url_for('ally_messages.index'))


@ally_messages_bp.route('/delete-message/<int:message_id>', methods=['POST'])
@login_required
@require_role('ally')
@handle_db_errors
@log_activity('delete_message')
def delete_message(message_id):
    """
    Elimina un mensaje específico.
    
    Solo permite eliminar mensajes propios y dentro del tiempo límite.
    """
    try:
        ally = current_user.ally
        message = Message.query.get_or_404(message_id)
        
        # Verificar que el mensaje es del usuario actual
        if message.sender_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Solo puedes eliminar tus propios mensajes.'
            }), 403
        
        # Verificar tiempo límite para eliminación (15 minutos)
        time_limit = current_app.config.get('MESSAGE_DELETE_TIME_LIMIT', 15)
        time_elapsed = (datetime.now(timezone.utc) - message.created_at).total_seconds() / 60
        
        if time_elapsed > time_limit:
            return jsonify({
                'success': False,
                'error': f'Solo puedes eliminar mensajes dentro de los primeros {time_limit} minutos.'
            }), 400
        
        # Verificar acceso a la conversación
        thread = message.thread
        if not _ally_has_access_to_thread(ally, thread):
            return jsonify({
                'success': False,
                'error': 'Sin permisos para acceder a esta conversación.'
            }), 403
        
        # Eliminar archivos adjuntos asociados
        documents = Document.query.filter_by(message_id=message_id).all()
        for doc in documents:
            try:
                if os.path.exists(doc.file_path):
                    os.remove(doc.file_path)
                db.session.delete(doc)
            except Exception as e:
                current_app.logger.error(f"Error eliminando archivo: {str(e)}")
        
        # Marcar mensaje como eliminado en lugar de borrarlo completamente
        message.content = "[Mensaje eliminado]"
        message.is_deleted = True
        message.deleted_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Emitir evento WebSocket
        emit_message_status_update(thread.id, {
            'action': 'delete',
            'message_id': message_id,
            'deleted_by': current_user.id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar mensaje: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno al eliminar el mensaje.'
        }), 500


@ally_messages_bp.route('/export/<int:thread_id>')
@login_required
@require_role('ally')
@log_activity('export_conversation')
def export_conversation(thread_id):
    """
    Exporta una conversación completa en formato PDF.
    
    Incluye todos los mensajes y metadatos de la conversación.
    """
    try:
        ally = current_user.ally
        thread = MessageThread.query.get_or_404(thread_id)
        
        # Verificar permisos
        if not _ally_has_access_to_thread(ally, thread):
            abort(403)
        
        # Obtener todos los mensajes de la conversación
        messages = (
            Message.query
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .all()
        )
        
        # Obtener el otro participante
        other_participant = (
            thread.participant1 if thread.participant2_id == current_user.id
            else thread.participant2
        )
        
        # Generar PDF usando utilidad de exportación
        from app.utils.export_utils import generate_conversation_pdf
        
        pdf_path = generate_conversation_pdf(
            thread, messages, current_user, other_participant
        )
        
        filename = f'conversacion_{thread_id}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.pdf'
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al exportar conversación: {str(e)}")
        flash('Error al exportar la conversación.', 'error')
        return redirect(url_for('ally_messages.conversation', thread_id=thread_id))


# API Endpoints para funcionalidades AJAX

@ally_messages_bp.route('/api/conversations')
@login_required
@require_role('ally')
def api_get_conversations():
    """API endpoint para obtener conversaciones via AJAX."""
    try:
        conversations = (
            MessageThread.query
            .filter(
                or_(
                    MessageThread.participant1_id == current_user.id,
                    MessageThread.participant2_id == current_user.id
                )
            )
            .order_by(desc(MessageThread.last_message_at))
            .limit(20)
            .all()
        )
        
        conversations_data = []
        for conv in conversations:
            other_participant = (
                conv.participant1 if conv.participant2_id == current_user.id
                else conv.participant2
            )
            
            unread_count = (
                conv.unread_count_p1 if conv.participant1_id == current_user.id
                else conv.unread_count_p2
            )
            
            conversations_data.append({
                'id': conv.id,
                'other_participant': {
                    'id': other_participant.id,
                    'name': other_participant.name,
                    'avatar_url': other_participant.avatar_url
                },
                'last_message': {
                    'content': truncate_text(conv.last_message.content, 50) if conv.last_message else '',
                    'created_at': conv.last_message_at.isoformat() if conv.last_message_at else None
                },
                'unread_count': unread_count,
                'is_important': conv.is_important
            })
        
        return jsonify({
            'success': True,
            'conversations': conversations_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API conversations: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@ally_messages_bp.route('/api/messages/<int:thread_id>')
@login_required
@require_role('ally')
def api_get_messages(thread_id):
    """API endpoint para obtener mensajes de una conversación via AJAX."""
    try:
        ally = current_user.ally
        thread = MessageThread.query.get_or_404(thread_id)
        
        if not _ally_has_access_to_thread(ally, thread):
            return jsonify({'success': False, 'error': 'Sin permisos'}), 403
        
        page = request.args.get('page', 1, type=int)
        
        messages_query = (
            Message.query
            .filter(Message.thread_id == thread_id)
            .order_by(desc(Message.created_at))
        )
        
        pagination = messages_query.paginate(
            page=page,
            per_page=MESSAGES_PER_PAGE,
            error_out=False
        )
        
        messages_data = []
        for msg in reversed(pagination.items):
            attachments = []
            if msg.documents:
                attachments = [{
                    'id': doc.id,
                    'filename': doc.original_filename,
                    'file_type': doc.file_type,
                    'file_size': doc.file_size,
                    'download_url': url_for(
                        'ally_messages.download_attachment',
                        attachment_id=doc.id
                    )
                } for doc in msg.documents]
            
            messages_data.append({
                'id': msg.id,
                'sender_id': msg.sender_id,
                'sender_name': msg.sender.name,
                'content': msg.content,
                'is_important': msg.is_important,
                'status': msg.status,
                'created_at': msg.created_at.isoformat(),
                'attachments': attachments,
                'is_deleted': getattr(msg, 'is_deleted', False)
            })
        
        return jsonify({
            'success': True,
            'messages': messages_data,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
            'total_pages': pagination.pages
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API messages: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@ally_messages_bp.route('/api/typing', methods=['POST'])
@login_required
@require_role('ally')
def api_typing_indicator():
    """API endpoint para indicadores de escritura en tiempo real."""
    try:
        data = request.get_json()
        thread_id = data.get('thread_id')
        is_typing = data.get('is_typing', False)
        
        if not thread_id:
            return jsonify({'success': False, 'error': 'Thread ID requerido'}), 400
        
        # Verificar acceso a la conversación
        thread = MessageThread.query.get(thread_id)
        if not thread or not _ally_has_access_to_thread(current_user.ally, thread):
            return jsonify({'success': False, 'error': 'Sin permisos'}), 403
        
        # Emitir evento de typing via WebSocket
        from app.sockets.handlers.chat import emit_typing_indicator
        emit_typing_indicator(thread_id, {
            'user_id': current_user.id,
            'user_name': current_user.name,
            'is_typing': is_typing,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error en typing indicator: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _ally_has_access_to_thread(ally, thread):
    """Verifica si un aliado tiene acceso a una conversación específica."""
    return (
        thread.participant1_id == ally.user_id or 
        thread.participant2_id == ally.user_id
    )


def _ally_has_access_to_user(ally, user):
    """Verifica si un aliado tiene acceso a comunicarse con un usuario específico."""
    # El aliado puede comunicarse con emprendedores asignados
    if hasattr(user, 'entrepreneur') and user.entrepreneur:
        return (
            Project.query
            .filter(
                Project.ally_id == ally.id,
                Project.entrepreneur_id == user.entrepreneur.id
            )
            .first() is not None
        )
    
    # También puede comunicarse con otros aliados y admins
    return user.role in ['ally', 'admin']


def _mark_messages_as_read(thread_id, user_id):
    """Marca todos los mensajes no leídos como leídos."""
    try:
        Message.query.filter(
            Message.thread_id == thread_id,
            Message.receiver_id == user_id,
            Message.status != 'read'
        ).update({
            'status': 'read',
            'read_at': datetime.now(timezone.utc)
        })
        
        # Actualizar contador en la conversación
        thread = MessageThread.query.get(thread_id)
        if thread:
            if thread.participant1_id == user_id:
                thread.unread_count_p1 = 0
            else:
                thread.unread_count_p2 = 0
        
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error marcando mensajes como leídos: {str(e)}")
        db.session.rollback()


def _process_file_attachment(file, message_id):
    """Procesa y guarda un archivo adjunto."""
    try:
        # Validar archivo
        if not file.filename:
            return None
        
        filename = secure_filename(file.filename)
        if not filename:
            return None
        
        # Validar extensión
        file_ext = get_file_extension(filename).lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f'Tipo de archivo no permitido: {file_ext}')
        
        # Validar tamaño
        file.seek(0, 2)  # Ir al final del archivo
        file_size = file.tell()
        file.seek(0)  # Volver al inicio
        
        if file_size > MAX_FILE_SIZE:
            raise ValidationError(f'Archivo demasiado grande: {format_file_size(file_size)}')
        
        # Determinar tipo de archivo
        file_type = 'document'
        if is_image_file(filename):
            file_type = 'image'
        elif file_ext in ['mp3', 'wav', 'ogg']:
            file_type = 'audio'
        elif file_ext in ['mp4', 'avi', 'mov', 'wmv']:
            file_type = 'video'
        
        # Generar nombre único
        unique_filename = f"{uuid.uuid4()}_{filename}"
        
        # Guardar archivo usando el servicio de almacenamiento
        file_path = FileStorageService.save_message_attachment(
            file, unique_filename, current_user.id
        )
        
        # Crear registro en base de datos
        document = Document(
            message_id=message_id,
            original_filename=filename,
            stored_filename=unique_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            mime_type=mimetypes.guess_type(filename)[0],
            uploaded_by=current_user.id
        )
        
        db.session.add(document)
        db.session.flush()  # Para obtener el ID
        
        return document
        
    except Exception as e:
        current_app.logger.error(f"Error procesando archivo adjunto: {str(e)}")
        raise


def _highlight_search_term(text, term):
    """Resalta términos de búsqueda en el texto."""
    if not term or not text:
        return text
    
    import re
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    return pattern.sub(f'<mark>{term}</mark>', text)


# Manejadores de errores específicos

@ally_messages_bp.errorhandler(403)
def forbidden(error):
    """Maneja errores de acceso prohibido."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Acceso prohibido'}), 403
    flash('No tienes permisos para acceder a este recurso.', 'error')
    return redirect(url_for('ally_messages.index'))


@ally_messages_bp.errorhandler(404)
def not_found(error):
    """Maneja errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404
    flash('El recurso solicitado no existe.', 'error')
    return redirect(url_for('ally_messages.index'))


@ally_messages_bp.errorhandler(413)
def request_entity_too_large(error):
    """Maneja errores de archivo demasiado grande."""
    if request.is_json:
        return jsonify({
            'success': False, 
            'error': f'Archivo demasiado grande. Máximo: {format_file_size(MAX_FILE_SIZE)}'
        }), 413
    flash(f'Archivo demasiado grande. Máximo permitido: {format_file_size(MAX_FILE_SIZE)}', 'error')
    return redirect(url_for('ally_messages.index'))


@ally_messages_bp.errorhandler(500)
def internal_error(error):
    """Maneja errores internos del servidor."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en mensajes: {str(error)}")
    
    if request.is_json:
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
    flash('Error interno del servidor. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('ally_messages.index'))


# Hooks de inicialización

@ally_messages_bp.before_request
def before_request():
    """Se ejecuta antes de cada request al blueprint."""
    # Verificar que el usuario esté autenticado y sea aliado
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    if current_user.role != 'ally':
        abort(403)


@ally_messages_bp.after_request
def after_request(response):
    """Se ejecuta después de cada request al blueprint."""
    # Agregar headers de seguridad específicos para mensajería
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response