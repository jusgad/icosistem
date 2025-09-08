"""
Sistema de Mensajería del Emprendedor - Comunicación integral del ecosistema.

Este módulo contiene todas las vistas relacionadas con el sistema de mensajería
del emprendedor, incluyendo conversaciones, contactos, notificaciones en tiempo real,
archivado, búsqueda avanzada, plantillas y analytics de comunicación.
"""

import os
import json
import hashlib
from datetime import datetime, timedelta, date, timezone
from collections import defaultdict
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, g, send_file, session
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, text, case
from sqlalchemy.orm import joinedload, selectinload, aliased
from werkzeug.utils import secure_filename

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, ResourceNotFoundError
from app.models.entrepreneur import Entrepreneur
from app.models.message import (
    Message, MessageStatus, MessagePriority, MessageType,
    Conversation, ConversationParticipant, MessageAttachment,
    MessageTemplate, MessageFolder, MessageLabel, MessageThread
)
from app.models.user import User
from app.models.ally import Ally
from app.models.client import Client
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.forms.message import (
    MessageForm, MessageSearchForm, ConversationForm,
    ContactForm, MessageTemplateForm, MessageSettingsForm,
    BulkActionForm, MessageFilterForm, MessageScheduleForm
)
from app.services.entrepreneur_service import EntrepreneurService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.sms import SMSService
from app.services.file_storage import FileStorageService
from app.utils.decorators import cache_response, rate_limit, validate_json
from app.utils.validators import validate_email, validate_phone_number
from app.utils.formatters import (
    format_file_size, format_relative_time, format_date_short,
    format_message_preview, truncate_text
)
from app.utils.string_utils import sanitize_input, extract_mentions, highlight_search_terms
from app.utils.crypto_utils import encrypt_message, decrypt_message
from app.utils.file_utils import get_file_extension, allowed_file
from app.utils.pagination import get_pagination_params
from app.utils.notifications import send_real_time_notification

# Crear blueprint para mensajería del emprendedor
entrepreneur_messages = Blueprint(
    'entrepreneur_messages', 
    __name__, 
    url_prefix='/entrepreneur/messages'
)

# Configuraciones
MESSAGES_PER_PAGE = 25
CONVERSATIONS_PER_PAGE = 20
MAX_MESSAGE_LENGTH = 5000
MAX_SUBJECT_LENGTH = 200
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25MB
MAX_ATTACHMENTS_PER_MESSAGE = 5
ALLOWED_ATTACHMENT_TYPES = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'
}

# Configuración de búsqueda
SEARCH_HIGHLIGHT_LENGTH = 150
MAX_SEARCH_RESULTS = 100

# Configuración de notificaciones
REAL_TIME_EVENTS = {
    'new_message': 'message:new',
    'message_read': 'message:read',
    'typing': 'message:typing',
    'online_status': 'user:online'
}

# Prioridades con colores
PRIORITY_COLORS = {
    MessagePriority.LOW: '#28a745',      # Verde
    MessagePriority.NORMAL: '#6c757d',   # Gris
    MessagePriority.HIGH: '#fd7e14',     # Naranja
    MessagePriority.URGENT: '#dc3545'    # Rojo
}

# Iconos por tipo
TYPE_ICONS = {
    MessageType.DIRECT: 'fa-envelope',
    MessageType.GROUP: 'fa-users',
    MessageType.ANNOUNCEMENT: 'fa-bullhorn',
    MessageType.AUTOMATED: 'fa-robot'
}


@entrepreneur_messages.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
        g.file_storage = FileStorageService()
    else:
        g.entrepreneur = None
        g.entrepreneur_service = None
        g.file_storage = None


@entrepreneur_messages.route('/')
@entrepreneur_messages.route('/inbox')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=60)  # Cache por 1 minuto
def inbox():
    """
    Bandeja de entrada principal del sistema de mensajería.
    
    Incluye:
    - Lista de conversaciones activas
    - Mensajes no leídos destacados
    - Filtros por prioridad y tipo
    - Búsqueda rápida
    - Estado de conexión de contactos
    - Métricas de comunicación
    """
    try:
        # Parámetros de filtrado y paginación
        page, per_page = get_pagination_params(request, default_per_page=CONVERSATIONS_PER_PAGE)
        folder = request.args.get('folder', 'inbox')
        priority = request.args.get('priority')
        message_type = request.args.get('type')
        search_query = request.args.get('q', '').strip()
        
        # Construir query base de conversaciones
        conversations_query = _build_conversations_query(
            current_user.id, folder, priority, message_type, search_query
        )
        
        # Paginación
        conversations_pagination = conversations_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Mensajes no leídos
        unread_count = _get_unread_messages_count(current_user.id)
        
        # Conversaciones con mensajes no leídos
        unread_conversations = _get_unread_conversations(current_user.id, limit=5)
        
        # Contactos frecuentes
        frequent_contacts = _get_frequent_contacts(current_user.id, limit=8)
        
        # Contactos en línea
        online_contacts = _get_online_contacts(current_user.id, limit=10)
        
        # Métricas de comunicación
        comm_metrics = _get_communication_metrics(current_user.id)
        
        # Carpetas de mensajes
        folders = _get_message_folders(current_user.id)
        
        # Etiquetas disponibles
        labels = _get_message_labels(current_user.id)
        
        # Mensajes programados pendientes
        scheduled_messages = _get_scheduled_messages(current_user.id, limit=3)
        
        # Plantillas recientes
        recent_templates = _get_recent_templates(current_user.id, limit=5)
        
        return render_template(
            'entrepreneur/messages/inbox.html',
            conversations=conversations_pagination.items,
            pagination=conversations_pagination,
            unread_count=unread_count,
            unread_conversations=unread_conversations,
            frequent_contacts=frequent_contacts,
            online_contacts=online_contacts,
            comm_metrics=comm_metrics,
            folders=folders,
            labels=labels,
            scheduled_messages=scheduled_messages,
            recent_templates=recent_templates,
            current_folder=folder,
            current_filters={
                'priority': priority,
                'type': message_type,
                'search': search_query
            },
            MessagePriority=MessagePriority,
            MessageType=MessageType,
            priority_colors=PRIORITY_COLORS,
            type_icons=TYPE_ICONS
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando bandeja de entrada: {str(e)}")
        flash('Error cargando los mensajes', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_messages.route('/conversation/<int:conversation_id>')
@login_required
@require_role('entrepreneur')
def view_conversation(conversation_id):
    """
    Ver conversación completa con historial de mensajes.
    """
    try:
        # Obtener conversación con validación de acceso
        conversation = _get_conversation_or_404(conversation_id)
        
        # Verificar permisos de acceso
        if not _can_access_conversation(conversation, current_user.id):
            flash('No tienes acceso a esta conversación', 'error')
            return redirect(url_for('entrepreneur_messages.inbox'))
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Obtener mensajes de la conversación
        messages_query = Message.query.filter_by(
            conversation_id=conversation.id
        ).options(
            joinedload(Message.sender),
            joinedload(Message.attachments)
        ).order_by(desc(Message.created_at))
        
        messages_pagination = messages_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Marcar mensajes como leídos
        _mark_messages_as_read(conversation_id, current_user.id)
        
        # Obtener participantes
        participants = _get_conversation_participants(conversation.id)
        
        # Información del remitente (para conversaciones directas)
        other_participant = _get_other_participant(conversation, current_user.id)
        
        # Archivos compartidos en la conversación
        shared_files = _get_conversation_shared_files(conversation.id, limit=10)
        
        # Verificar si puede responder
        can_reply = _can_reply_to_conversation(conversation, current_user.id)
        
        # Información de tipeo en tiempo real
        typing_info = _get_typing_info(conversation_id, current_user.id)
        
        # Navegación entre conversaciones
        prev_conversation, next_conversation = _get_adjacent_conversations(
            conversation_id, current_user.id
        )
        
        return render_template(
            'entrepreneur/messages/conversation.html',
            conversation=conversation,
            messages=list(reversed(messages_pagination.items)),  # Orden cronológico
            pagination=messages_pagination,
            participants=participants,
            other_participant=other_participant,
            shared_files=shared_files,
            can_reply=can_reply,
            typing_info=typing_info,
            prev_conversation=prev_conversation,
            next_conversation=next_conversation,
            MessagePriority=MessagePriority,
            MessageType=MessageType,
            priority_colors=PRIORITY_COLORS
        )

    except ResourceNotFoundError:
        flash('Conversación no encontrada', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))
    except Exception as e:
        current_app.logger.error(f"Error mostrando conversación {conversation_id}: {str(e)}")
        flash('Error cargando la conversación', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.route('/compose', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def compose():
    """
    Componer nuevo mensaje o conversación.
    """
    form = MessageForm()
    
    if request.method == 'GET':
        # Pre-llenar destinatario si se especifica
        recipient_id = request.args.get('to', type=int)
        subject = request.args.get('subject', '')
        template_id = request.args.get('template_id', type=int)
        
        if recipient_id:
            form.recipient_id.data = recipient_id
        
        if subject:
            form.subject.data = subject
        
        if template_id:
            template = _get_message_template(template_id, current_user.id)
            if template:
                _populate_form_from_template(form, template)
        
        # Cargar opciones del formulario
        _populate_message_form_choices(form)
        
        # Obtener contactos sugeridos
        suggested_contacts = _get_suggested_contacts(current_user.id, limit=10)
        
        # Plantillas disponibles
        available_templates = _get_message_templates(current_user.id)
        
        return render_template(
            'entrepreneur/messages/compose.html',
            form=form,
            suggested_contacts=suggested_contacts,
            available_templates=available_templates,
            max_message_length=MAX_MESSAGE_LENGTH,
            max_attachments=MAX_ATTACHMENTS_PER_MESSAGE,
            allowed_file_types=ALLOWED_ATTACHMENT_TYPES
        )
    
    try:
        if not form.validate_on_submit():
            _populate_message_form_choices(form)
            return render_template(
                'entrepreneur/messages/compose.html',
                form=form,
                max_message_length=MAX_MESSAGE_LENGTH
            )
        
        # Validaciones adicionales
        validation_result = _validate_message_data(form)
        if not validation_result['valid']:
            for error in validation_result['errors']:
                flash(error, 'error')
            _populate_message_form_choices(form)
            return render_template('entrepreneur/messages/compose.html', form=form)
        
        # Verificar límites de rate limiting
        if not _check_message_rate_limit(current_user.id):
            flash('Has alcanzado el límite de mensajes por hora. Intenta más tarde.', 'error')
            _populate_message_form_choices(form)
            return render_template('entrepreneur/messages/compose.html', form=form)
        
        # Obtener o crear conversación
        conversation = _get_or_create_conversation(
            sender_id=current_user.id,
            recipient_id=form.recipient_id.data,
            subject=form.subject.data
        )
        
        # Crear mensaje
        message_data = {
            'subject': sanitize_input(form.subject.data),
            'content': sanitize_input(form.content.data),
            'priority': form.priority.data,
            'message_type': MessageType.DIRECT,
            'sender_id': current_user.id,
            'conversation_id': conversation.id,
            'is_encrypted': form.is_encrypted.data if hasattr(form, 'is_encrypted') else False
        }
        
        # Encriptar contenido si es necesario
        if message_data['is_encrypted']:
            message_data['content'] = encrypt_message(message_data['content'])
        
        message = Message.create(**message_data)
        
        # Procesar adjuntos
        attachments = []
        if hasattr(form, 'attachments') and form.attachments.data:
            attachments = _process_message_attachments(message, form.attachments.data)
        
        # Actualizar conversación
        conversation.last_message_id = message.id
        conversation.last_activity_at = datetime.now(timezone.utc)
        conversation.save()
        
        # Enviar notificaciones
        _send_message_notifications(message, conversation)
        
        # Notificación en tiempo real
        _send_real_time_message_notification(message, conversation)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='message_sent',
            resource_type='message',
            resource_id=message.id,
            details={
                'recipient_id': form.recipient_id.data,
                'subject': message.subject,
                'conversation_id': conversation.id,
                'attachments_count': len(attachments)
            }
        )
        
        # Programar mensaje si se especificó
        if hasattr(form, 'schedule_at') and form.schedule_at.data:
            _schedule_message(message, form.schedule_at.data)
            flash('Mensaje programado correctamente', 'success')
        else:
            flash('Mensaje enviado exitosamente', 'success')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Mensaje enviado exitosamente',
                'conversation_id': conversation.id,
                'message_id': message.id,
                'redirect_url': url_for('entrepreneur_messages.view_conversation', 
                                      conversation_id=conversation.id)
            })
        else:
            return redirect(url_for('entrepreneur_messages.view_conversation', 
                                  conversation_id=conversation.id))

    except ValidationError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(str(e), 'error')
            _populate_message_form_choices(form)
            return render_template('entrepreneur/messages/compose.html', form=form)
    
    except Exception as e:
        current_app.logger.error(f"Error enviando mensaje: {str(e)}")
        error_msg = 'Error enviando el mensaje'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            _populate_message_form_choices(form)
            return render_template('entrepreneur/messages/compose.html', form=form)


@entrepreneur_messages.route('/reply/<int:conversation_id>', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=30, window=60)  # 30 respuestas por minuto
def reply(conversation_id):
    """
    Responder a una conversación existente.
    """
    try:
        conversation = _get_conversation_or_404(conversation_id)
        
        # Verificar permisos
        if not _can_reply_to_conversation(conversation, current_user.id):
            return jsonify({
                'success': False,
                'error': 'No puedes responder a esta conversación'
            }), 403
        
        # Validar datos
        content = request.json.get('content', '').strip()
        priority = request.json.get('priority', MessagePriority.NORMAL.value)
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'El contenido del mensaje no puede estar vacío'
            }), 400
        
        if len(content) > MAX_MESSAGE_LENGTH:
            return jsonify({
                'success': False,
                'error': f'El mensaje no puede exceder {MAX_MESSAGE_LENGTH} caracteres'
            }), 400
        
        # Verificar rate limiting
        if not _check_message_rate_limit(current_user.id):
            return jsonify({
                'success': False,
                'error': 'Has alcanzado el límite de mensajes por minuto'
            }), 429
        
        # Crear mensaje de respuesta
        message_data = {
            'content': sanitize_input(content),
            'priority': MessagePriority(priority),
            'message_type': MessageType.DIRECT,
            'sender_id': current_user.id,
            'conversation_id': conversation.id,
            'parent_message_id': request.json.get('parent_message_id')
        }
        
        message = Message.create(**message_data)
        
        # Actualizar conversación
        conversation.last_message_id = message.id
        conversation.last_activity_at = datetime.now(timezone.utc)
        conversation.save()
        
        # Enviar notificaciones
        _send_message_notifications(message, conversation)
        
        # Notificación en tiempo real
        _send_real_time_message_notification(message, conversation)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='message_replied',
            resource_type='message',
            resource_id=message.id,
            details={
                'conversation_id': conversation.id,
                'parent_message_id': message.parent_message_id
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Respuesta enviada exitosamente',
            'message_id': message.id,
            'message_html': render_template(
                'entrepreneur/messages/_message_bubble.html',
                message=message,
                current_user_id=current_user.id
            )
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Conversación no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error respondiendo a conversación {conversation_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error enviando la respuesta'
        }), 500


@entrepreneur_messages.route('/search')
@login_required
@require_role('entrepreneur')
def search():
    """
    Búsqueda avanzada de mensajes y conversaciones.
    """
    try:
        # Parámetros de búsqueda
        query = request.args.get('q', '').strip()
        sender_id = request.args.get('sender_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        priority = request.args.get('priority')
        has_attachments = request.args.get('has_attachments', 'false').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        
        if not query and not sender_id and not date_from:
            # Mostrar formulario de búsqueda vacío
            return render_template(
                'entrepreneur/messages/search.html',
                search_form=MessageSearchForm(),
                search_results=None,
                search_params={}
            )
        
        # Realizar búsqueda
        search_results = _perform_message_search(
            user_id=current_user.id,
            query=query,
            sender_id=sender_id,
            date_from=date_from,
            date_to=date_to,
            priority=priority,
            has_attachments=has_attachments,
            page=page,
            per_page=25
        )
        
        # Contactos para filtros
        contacts = _get_user_contacts(current_user.id)
        
        # Guardar búsqueda reciente
        if query:
            _save_recent_search(current_user.id, query)
        
        # Búsquedas recientes
        recent_searches = _get_recent_searches(current_user.id, limit=5)
        
        # Sugerencias de búsqueda
        search_suggestions = _get_search_suggestions(current_user.id, query)
        
        return render_template(
            'entrepreneur/messages/search.html',
            search_results=search_results,
            contacts=contacts,
            recent_searches=recent_searches,
            search_suggestions=search_suggestions,
            search_params={
                'q': query,
                'sender_id': sender_id,
                'date_from': date_from,
                'date_to': date_to,
                'priority': priority,
                'has_attachments': has_attachments
            },
            MessagePriority=MessagePriority,
            priority_colors=PRIORITY_COLORS
        )

    except Exception as e:
        current_app.logger.error(f"Error en búsqueda de mensajes: {str(e)}")
        flash('Error realizando la búsqueda', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.route('/contacts')
@login_required
@require_role('entrepreneur')
def contacts():
    """
    Gestión de contactos y directorio.
    """
    try:
        # Parámetros de filtrado
        search_query = request.args.get('q', '').strip()
        contact_type = request.args.get('type', 'all')  # all, allies, clients, colleagues
        status = request.args.get('status', 'all')  # all, online, offline
        
        # Obtener contactos
        contacts_data = _get_contacts_directory(
            user_id=current_user.id,
            search_query=search_query,
            contact_type=contact_type,
            status=status
        )
        
        # Estadísticas de contactos
        contact_stats = _get_contact_statistics(current_user.id)
        
        # Contactos recientes (con quien se ha comunicado)
        recent_contacts = _get_recent_communication_contacts(current_user.id, limit=10)
        
        # Contactos favoritos
        favorite_contacts = _get_favorite_contacts(current_user.id)
        
        # Grupos de contactos
        contact_groups = _get_contact_groups(current_user.id)
        
        return render_template(
            'entrepreneur/messages/contacts.html',
            contacts=contacts_data,
            contact_stats=contact_stats,
            recent_contacts=recent_contacts,
            favorite_contacts=favorite_contacts,
            contact_groups=contact_groups,
            current_filters={
                'search': search_query,
                'type': contact_type,
                'status': status
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando contactos: {str(e)}")
        flash('Error cargando los contactos', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.route('/templates')
@login_required
@require_role('entrepreneur')
def templates():
    """
    Gestión de plantillas de mensajes.
    """
    try:
        # Obtener plantillas del usuario
        user_templates = MessageTemplate.query.filter_by(
            created_by=current_user.id
        ).order_by(desc(MessageTemplate.updated_at)).all()
        
        # Plantillas del sistema (públicas)
        system_templates = MessageTemplate.query.filter_by(
            is_system=True,
            is_active=True
        ).order_by(MessageTemplate.name).all()
        
        # Estadísticas de uso
        template_stats = _get_template_usage_stats(current_user.id)
        
        # Categorías de plantillas
        template_categories = _get_template_categories()
        
        return render_template(
            'entrepreneur/messages/templates.html',
            user_templates=user_templates,
            system_templates=system_templates,
            template_stats=template_stats,
            template_categories=template_categories
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando plantillas: {str(e)}")
        flash('Error cargando las plantillas', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.route('/templates/create', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def create_template():
    """
    Crear nueva plantilla de mensaje.
    """
    form = MessageTemplateForm()
    
    if request.method == 'GET':
        return render_template(
            'entrepreneur/messages/create_template.html',
            form=form
        )
    
    try:
        if not form.validate_on_submit():
            return render_template(
                'entrepreneur/messages/create_template.html',
                form=form
            )
        
        # Crear plantilla
        template_data = {
            'name': sanitize_input(form.name.data),
            'subject': sanitize_input(form.subject.data) if form.subject.data else None,
            'content': sanitize_input(form.content.data),
            'category': form.category.data if form.category.data else None,
            'is_active': True,
            'created_by': current_user.id
        }
        
        template = MessageTemplate.create(**template_data)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='template_created',
            resource_type='message_template',
            resource_id=template.id,
            details={
                'template_name': template.name,
                'category': template.category
            }
        )
        
        flash('Plantilla creada exitosamente', 'success')
        return redirect(url_for('entrepreneur_messages.templates'))

    except Exception as e:
        current_app.logger.error(f"Error creando plantilla: {str(e)}")
        flash('Error creando la plantilla', 'error')
        return render_template('entrepreneur/messages/create_template.html', form=form)


@entrepreneur_messages.route('/mark-read', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=100, window=60)  # 100 marcados como leído por minuto
def mark_as_read():
    """
    Marcar mensajes como leídos.
    """
    try:
        message_ids = request.json.get('message_ids', [])
        conversation_ids = request.json.get('conversation_ids', [])
        
        if not message_ids and not conversation_ids:
            return jsonify({
                'success': False,
                'error': 'No se especificaron mensajes o conversaciones'
            }), 400
        
        marked_count = 0
        
        # Marcar mensajes específicos
        if message_ids:
            marked_count += _mark_specific_messages_as_read(message_ids, current_user.id)
        
        # Marcar conversaciones completas
        if conversation_ids:
            for conv_id in conversation_ids:
                marked_count += _mark_conversation_as_read(conv_id, current_user.id)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='messages_marked_read',
            resource_type='message',
            details={
                'message_ids': message_ids,
                'conversation_ids': conversation_ids,
                'marked_count': marked_count
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'{marked_count} mensaje(s) marcado(s) como leído(s)',
            'marked_count': marked_count
        })

    except Exception as e:
        current_app.logger.error(f"Error marcando mensajes como leídos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error marcando los mensajes'
        }), 500


@entrepreneur_messages.route('/archive', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=50, window=300)  # 50 archivados por 5 minutos
def archive_messages():
    """
    Archivar mensajes o conversaciones.
    """
    try:
        conversation_ids = request.json.get('conversation_ids', [])
        
        if not conversation_ids:
            return jsonify({
                'success': False,
                'error': 'No se especificaron conversaciones'
            }), 400
        
        archived_count = 0
        for conv_id in conversation_ids:
            try:
                conversation = _get_conversation_or_404(conv_id)
                if _can_archive_conversation(conversation, current_user.id):
                    conversation.is_archived = True
                    conversation.archived_at = datetime.now(timezone.utc)
                    conversation.save()
                    archived_count += 1
            except ResourceNotFoundError:
                continue
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='conversations_archived',
            resource_type='conversation',
            details={
                'conversation_ids': conversation_ids,
                'archived_count': archived_count
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'{archived_count} conversación(es) archivada(s)',
            'archived_count': archived_count
        })

    except Exception as e:
        current_app.logger.error(f"Error archivando conversaciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error archivando las conversaciones'
        }), 500


@entrepreneur_messages.route('/typing', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=200, window=60)  # 200 indicadores de tipeo por minuto
def typing_indicator():
    """
    Enviar indicador de tipeo en tiempo real.
    """
    try:
        conversation_id = request.json.get('conversation_id')
        is_typing = request.json.get('is_typing', True)
        
        if not conversation_id:
            return jsonify({
                'success': False,
                'error': 'ID de conversación requerido'
            }), 400
        
        # Verificar acceso a la conversación
        conversation = _get_conversation_or_404(conversation_id)
        if not _can_access_conversation(conversation, current_user.id):
            return jsonify({
                'success': False,
                'error': 'Sin acceso a la conversación'
            }), 403
        
        # Enviar indicador en tiempo real
        _send_typing_indicator(conversation_id, current_user.id, is_typing)
        
        return jsonify({
            'success': True,
            'message': 'Indicador enviado'
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Conversación no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error enviando indicador de tipeo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error enviando indicador'
        }), 500


@entrepreneur_messages.route('/analytics')
@login_required
@require_role('entrepreneur')
def analytics():
    """
    Analytics y métricas de comunicación.
    """
    try:
        # Rango de fechas para análisis
        date_range = request.args.get('range', '30')  # días
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=int(date_range))
        
        # Métricas de comunicación
        communication_metrics = _get_communication_analytics(
            current_user.id, start_date, end_date
        )
        
        # Análisis de tiempo de respuesta
        response_time_analysis = _get_response_time_analysis(
            current_user.id, start_date, end_date
        )
        
        # Patrones de comunicación
        communication_patterns = _get_communication_patterns(
            current_user.id, start_date, end_date
        )
        
        # Top contactos
        top_contacts = _get_top_communication_contacts(
            current_user.id, start_date, end_date, limit=10
        )
        
        # Análisis de contenido
        content_analysis = _get_message_content_analysis(
            current_user.id, start_date, end_date
        )
        
        # Tendencias temporales
        temporal_trends = _get_communication_temporal_trends(
            current_user.id, start_date, end_date
        )
        
        # Efectividad de plantillas
        template_effectiveness = _get_template_effectiveness_metrics(
            current_user.id, start_date, end_date
        )
        
        return render_template(
            'entrepreneur/messages/analytics.html',
            communication_metrics=communication_metrics,
            response_time_analysis=response_time_analysis,
            communication_patterns=communication_patterns,
            top_contacts=top_contacts,
            content_analysis=content_analysis,
            temporal_trends=temporal_trends,
            template_effectiveness=template_effectiveness,
            start_date=start_date,
            end_date=end_date,
            current_range=date_range
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando analytics de mensajes: {str(e)}")
        flash('Error cargando las métricas', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.route('/settings', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def settings():
    """
    Configuración del sistema de mensajería.
    """
    form = MessageSettingsForm()
    
    if request.method == 'GET':
        # Cargar configuraciones actuales
        _load_current_message_settings(form, current_user.id)
        
        return render_template(
            'entrepreneur/messages/settings.html',
            form=form
        )
    
    try:
        if not form.validate_on_submit():
            return render_template(
                'entrepreneur/messages/settings.html',
                form=form
            )
        
        # Actualizar configuraciones
        _update_message_settings(current_user.id, form)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='message_settings_updated',
            resource_type='user_settings',
            details={
                'updated_settings': list(form.data.keys())
            }
        )
        
        flash('Configuraciones actualizadas correctamente', 'success')
        return redirect(url_for('entrepreneur_messages.settings'))

    except Exception as e:
        current_app.logger.error(f"Error actualizando configuraciones: {str(e)}")
        flash('Error actualizando las configuraciones', 'error')
        return render_template('entrepreneur/messages/settings.html', form=form)


# === API ENDPOINTS PARA TIEMPO REAL ===

@entrepreneur_messages.route('/api/conversations')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=30)  # Cache por 30 segundos
def api_conversations():
    """
    API endpoint para obtener conversaciones (para WebSocket/AJAX).
    """
    try:
        folder = request.args.get('folder', 'inbox')
        limit = request.args.get('limit', 20, type=int)
        
        conversations = _get_conversations_for_api(
            user_id=current_user.id,
            folder=folder,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'conversations': [_format_conversation_for_api(conv) for conv in conversations],
            'unread_count': _get_unread_messages_count(current_user.id)
        })

    except Exception as e:
        current_app.logger.error(f"Error en API de conversaciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error obteniendo conversaciones'
        }), 500


@entrepreneur_messages.route('/api/messages/<int:conversation_id>')
@login_required
@require_role('entrepreneur')
def api_messages(conversation_id):
    """
    API endpoint para obtener mensajes de una conversación.
    """
    try:
        conversation = _get_conversation_or_404(conversation_id)
        
        if not _can_access_conversation(conversation, current_user.id):
            return jsonify({
                'success': False,
                'error': 'Sin acceso a la conversación'
            }), 403
        
        since_id = request.args.get('since_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        
        messages = _get_messages_for_api(
            conversation_id=conversation_id,
            since_id=since_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'messages': [_format_message_for_api(msg) for msg in messages],
            'conversation_id': conversation_id
        })

    except ResourceNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Conversación no encontrada'
        }), 404
    except Exception as e:
        current_app.logger.error(f"Error en API de mensajes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error obteniendo mensajes'
        }), 500


@entrepreneur_messages.route('/api/upload-attachment', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 uploads por 5 minutos
def upload_attachment():
    """
    API endpoint para subir adjuntos de mensajes.
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No se seleccionó archivo'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No se seleccionó archivo'
            }), 400
        
        # Validar archivo
        validation_result = _validate_attachment_file(file)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'error': validation_result['error']
            }), 400
        
        # Guardar archivo
        file_info = _save_message_attachment(file, current_user.id)
        
        return jsonify({
            'success': True,
            'message': 'Archivo subido correctamente',
            'file_info': file_info
        })

    except Exception as e:
        current_app.logger.error(f"Error subiendo adjunto: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error subiendo el archivo'
        }), 500


# === FUNCIONES AUXILIARES ===

def _build_conversations_query(user_id, folder, priority, message_type, search_query):
    """Construir query de conversaciones con filtros."""
    # Alias para el último mensaje
    last_message = aliased(Message)
    
    query = Conversation.query.join(
        ConversationParticipant,
        Conversation.id == ConversationParticipant.conversation_id
    ).filter(
        ConversationParticipant.user_id == user_id
    ).outerjoin(
        last_message,
        Conversation.last_message_id == last_message.id
    ).options(
        joinedload(Conversation.participants).joinedload(ConversationParticipant.user),
        joinedload(Conversation.last_message).joinedload(Message.sender)
    )
    
    # Filtro por carpeta
    if folder == 'inbox':
        query = query.filter(Conversation.is_archived == False)
    elif folder == 'archived':
        query = query.filter(Conversation.is_archived == True)
    elif folder == 'sent':
        query = query.filter(last_message.sender_id == user_id)
    
    # Filtro por prioridad
    if priority and priority != 'all':
        query = query.filter(last_message.priority == MessagePriority(priority))
    
    # Filtro por tipo
    if message_type and message_type != 'all':
        query = query.filter(last_message.message_type == MessageType(message_type))
    
    # Búsqueda
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                Conversation.subject.ilike(search_term),
                last_message.content.ilike(search_term)
            )
        )
    
    return query.order_by(desc(Conversation.last_activity_at))


def _get_conversation_or_404(conversation_id):
    """Obtener conversación con validación."""
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        raise ResourceNotFoundError("Conversación no encontrada")
    return conversation


def _can_access_conversation(conversation, user_id):
    """Verificar si el usuario puede acceder a la conversación."""
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation.id,
        user_id=user_id
    ).first()
    return participant is not None


def _can_reply_to_conversation(conversation, user_id):
    """Verificar si el usuario puede responder a la conversación."""
    return _can_access_conversation(conversation, user_id)


def _can_archive_conversation(conversation, user_id):
    """Verificar si el usuario puede archivar la conversación."""
    return _can_access_conversation(conversation, user_id)


def _get_unread_messages_count(user_id):
    """Obtener cantidad de mensajes no leídos."""
    return Message.query.join(Conversation).join(ConversationParticipant).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
    ).count()


def _get_unread_conversations(user_id, limit=5):
    """Obtener conversaciones con mensajes no leídos."""
    return Conversation.query.join(ConversationParticipant).join(Message).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
    ).options(
        joinedload(Conversation.last_message).joinedload(Message.sender)
    ).distinct().order_by(desc(Conversation.last_activity_at)).limit(limit).all()


def _get_frequent_contacts(user_id, limit=8):
    """Obtener contactos con comunicación frecuente."""
    # Obtener IDs de usuarios con más mensajes intercambiados
    frequent_user_ids = Message.query.join(Conversation).join(ConversationParticipant).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id
        )
    ).with_entities(
        Message.sender_id,
        func.count(Message.id).label('message_count')
    ).group_by(Message.sender_id).order_by(desc('message_count')).limit(limit).all()
    
    if not frequent_user_ids:
        return []
    
    user_ids = [uid[0] for uid in frequent_user_ids]
    return User.query.filter(User.id.in_(user_ids)).all()


def _get_online_contacts(user_id, limit=10):
    """Obtener contactos en línea."""
    # Esta función requeriría un sistema de presencia en tiempo real
    # Por ahora retornamos contactos frecuentes
    return _get_frequent_contacts(user_id, limit)


def _get_communication_metrics(user_id):
    """Obtener métricas básicas de comunicación."""
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # Mensajes enviados
    sent_today = Message.query.filter(
        and_(
            Message.sender_id == user_id,
            func.date(Message.created_at) == today
        )
    ).count()
    
    sent_this_week = Message.query.filter(
        and_(
            Message.sender_id == user_id,
            Message.created_at >= datetime.combine(week_start, datetime.min.time())
        )
    ).count()
    
    sent_this_month = Message.query.filter(
        and_(
            Message.sender_id == user_id,
            Message.created_at >= datetime.combine(month_start, datetime.min.time())
        )
    ).count()
    
    # Mensajes recibidos
    received_today = Message.query.join(Conversation).join(ConversationParticipant).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id,
            func.date(Message.created_at) == today
        )
    ).count()
    
    # Tiempo promedio de respuesta (simplificado)
    avg_response_time = 2.5  # horas (placeholder)
    
    return {
        'sent_today': sent_today,
        'sent_this_week': sent_this_week,
        'sent_this_month': sent_this_month,
        'received_today': received_today,
        'unread_count': _get_unread_messages_count(user_id),
        'avg_response_time_hours': avg_response_time
    }


def _get_message_folders(user_id):
    """Obtener carpetas de mensajes del usuario."""
    # Esta función requeriría un modelo MessageFolder
    # Por ahora retornamos carpetas por defecto
    return [
        {'id': 'inbox', 'name': 'Bandeja de entrada', 'count': 0},
        {'id': 'sent', 'name': 'Enviados', 'count': 0},
        {'id': 'archived', 'name': 'Archivados', 'count': 0},
        {'id': 'drafts', 'name': 'Borradores', 'count': 0}
    ]


def _get_message_labels(user_id):
    """Obtener etiquetas de mensajes."""
    # Placeholder
    return []


def _get_scheduled_messages(user_id, limit=3):
    """Obtener mensajes programados."""
    # Placeholder
    return []


def _get_recent_templates(user_id, limit=5):
    """Obtener plantillas recientes."""
    return MessageTemplate.query.filter_by(
        created_by=user_id,
        is_active=True
    ).order_by(desc(MessageTemplate.updated_at)).limit(limit).all()


def _mark_messages_as_read(conversation_id, user_id):
    """Marcar mensajes de una conversación como leídos."""
    Message.query.filter(
        and_(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)})
    
    # Commit los cambios
    from app import db
    db.session.commit()


def _get_conversation_participants(conversation_id):
    """Obtener participantes de una conversación."""
    return ConversationParticipant.query.filter_by(
        conversation_id=conversation_id
    ).options(joinedload(ConversationParticipant.user)).all()


def _get_other_participant(conversation, current_user_id):
    """Obtener el otro participante en una conversación directa."""
    for participant in conversation.participants:
        if participant.user_id != current_user_id:
            return participant.user
    return None


def _get_conversation_shared_files(conversation_id, limit=10):
    """Obtener archivos compartidos en la conversación."""
    return MessageAttachment.query.join(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(desc(MessageAttachment.created_at)).limit(limit).all()


def _get_typing_info(conversation_id, exclude_user_id):
    """Obtener información de quién está escribiendo."""
    # Esta función requeriría un sistema de presencia en tiempo real
    return {'users_typing': []}


def _get_adjacent_conversations(conversation_id, user_id):
    """Obtener conversaciones anterior y siguiente."""
    # Obtener conversación actual para referencia de tiempo
    current_conv = Conversation.query.get(conversation_id)
    if not current_conv:
        return None, None
    
    # Conversación anterior (más reciente)
    prev_conv = Conversation.query.join(ConversationParticipant).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Conversation.last_activity_at > current_conv.last_activity_at
        )
    ).order_by(asc(Conversation.last_activity_at)).first()
    
    # Conversación siguiente (más antigua)
    next_conv = Conversation.query.join(ConversationParticipant).filter(
        and_(
            ConversationParticipant.user_id == user_id,
            Conversation.last_activity_at < current_conv.last_activity_at
        )
    ).order_by(desc(Conversation.last_activity_at)).first()
    
    return prev_conv, next_conv


def _populate_message_form_choices(form):
    """Poblar opciones del formulario de mensaje."""
    # Obtener contactos disponibles
    contacts = _get_user_contacts(current_user.id)
    form.recipient_id.choices = [(c.id, f"{c.full_name} ({c.email})") for c in contacts]
    
    # Prioridades
    form.priority.choices = [(p.value, p.value.title()) for p in MessagePriority]


def _validate_message_data(form):
    """Validar datos del mensaje."""
    errors = []
    
    # Validar longitud del contenido
    if len(form.content.data) > MAX_MESSAGE_LENGTH:
        errors.append(f'El mensaje no puede exceder {MAX_MESSAGE_LENGTH} caracteres')
    
    # Validar asunto
    if form.subject.data and len(form.subject.data) > MAX_SUBJECT_LENGTH:
        errors.append(f'El asunto no puede exceder {MAX_SUBJECT_LENGTH} caracteres')
    
    # Validar destinatario
    recipient = User.query.get(form.recipient_id.data)
    if not recipient:
        errors.append('Destinatario no válido')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def _check_message_rate_limit(user_id):
    """Verificar límites de velocidad de mensajes."""
    # Verificar mensajes en la última hora
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    messages_last_hour = Message.query.filter(
        and_(
            Message.sender_id == user_id,
            Message.created_at >= hour_ago
        )
    ).count()
    
    # Límite: 100 mensajes por hora
    return messages_last_hour < 100


def _get_or_create_conversation(sender_id, recipient_id, subject):
    """Obtener conversación existente o crear nueva."""
    # Buscar conversación existente entre estos usuarios
    existing_conv = Conversation.query.join(ConversationParticipant).filter(
        ConversationParticipant.user_id.in_([sender_id, recipient_id])
    ).group_by(Conversation.id).having(
        func.count(ConversationParticipant.user_id) == 2
    ).first()
    
    if existing_conv:
        # Verificar que ambos usuarios están en la conversación
        participant_ids = [p.user_id for p in existing_conv.participants]
        if sender_id in participant_ids and recipient_id in participant_ids:
            return existing_conv
    
    # Crear nueva conversación
    conversation = Conversation.create(
        subject=subject,
        conversation_type='direct',
        created_by=sender_id
    )
    
    # Agregar participantes
    ConversationParticipant.create(
        conversation_id=conversation.id,
        user_id=sender_id,
        role='participant'
    )
    
    ConversationParticipant.create(
        conversation_id=conversation.id,
        user_id=recipient_id,
        role='participant'
    )
    
    return conversation


def _process_message_attachments(message, attachments_data):
    """Procesar adjuntos del mensaje."""
    # Esta función procesaría los adjuntos subidos
    return []


def _send_message_notifications(message, conversation):
    """Enviar notificaciones por nuevo mensaje."""
    # Notificar a todos los participantes excepto el remitente
    for participant in conversation.participants:
        if participant.user_id != message.sender_id:
            NotificationService.send_notification(
                user_id=participant.user_id,
                title='Nuevo mensaje',
                message=f'{message.sender.full_name}: {truncate_text(message.content, 100)}',
                notification_type='new_message',
                related_id=message.id
            )
            
            # Enviar email si está configurado
            EmailService.send_message_notification(
                participant.user.email,
                participant.user.first_name,
                message,
                conversation
            )


def _send_real_time_message_notification(message, conversation):
    """Enviar notificación en tiempo real."""
    # Esta función enviaría notificaciones WebSocket
    for participant in conversation.participants:
        if participant.user_id != message.sender_id:
            send_real_time_notification(
                user_id=participant.user_id,
                event=REAL_TIME_EVENTS['new_message'],
                data={
                    'message_id': message.id,
                    'conversation_id': conversation.id,
                    'sender': {
                        'id': message.sender.id,
                        'name': message.sender.full_name
                    },
                    'content_preview': truncate_text(message.content, 100),
                    'priority': message.priority.value
                }
            )


def _schedule_message(message, schedule_at):
    """Programar mensaje para envío posterior."""
    # Esta función requeriría un sistema de colas/workers
    pass


# Funciones auxiliares adicionales (implementación simplificada por espacio)

def _get_user_contacts(user_id):
    """Obtener contactos del usuario."""
    # Obtener aliados, clientes y otros emprendedores
    contacts = []
    
    # Obtener emprendedor
    entrepreneur = Entrepreneur.query.filter_by(id=user_id).first()
    if entrepreneur:
        # Aliado asignado
        if entrepreneur.assigned_ally:
            contacts.append(entrepreneur.assigned_ally.user)
    
    # Por simplicidad, retornar solo aliados por ahora
    return contacts


def _get_message_template(template_id, user_id):
    """Obtener plantilla de mensaje."""
    return MessageTemplate.query.filter(
        and_(
            MessageTemplate.id == template_id,
            or_(
                MessageTemplate.created_by == user_id,
                MessageTemplate.is_system == True
            )
        )
    ).first()


def _populate_form_from_template(form, template):
    """Poblar formulario desde plantilla."""
    if template.subject:
        form.subject.data = template.subject
    form.content.data = template.content


def _perform_message_search(user_id, query, sender_id, date_from, date_to, 
                           priority, has_attachments, page, per_page):
    """Realizar búsqueda de mensajes."""
    # Implementar búsqueda full-text
    search_query = Message.query.join(Conversation).join(ConversationParticipant).filter(
        ConversationParticipant.user_id == user_id
    )
    
    if query:
        search_term = f"%{query}%"
        search_query = search_query.filter(
            or_(
                Message.content.ilike(search_term),
                Message.subject.ilike(search_term)
            )
        )
    
    if sender_id:
        search_query = search_query.filter(Message.sender_id == sender_id)
    
    # Aplicar otros filtros...
    
    return search_query.order_by(desc(Message.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )


def _save_recent_search(user_id, query):
    """Guardar búsqueda reciente."""
    # Implementar guardado de búsquedas recientes
    pass


def _get_recent_searches(user_id, limit=5):
    """Obtener búsquedas recientes."""
    return []


def _get_search_suggestions(user_id, query):
    """Obtener sugerencias de búsqueda."""
    return []


def _get_contacts_directory(user_id, search_query, contact_type, status):
    """Obtener directorio de contactos."""
    return []


def _get_contact_statistics(user_id):
    """Obtener estadísticas de contactos."""
    return {
        'total_contacts': 0,
        'online_contacts': 0,
        'recent_contacts': 0
    }


def _get_recent_communication_contacts(user_id, limit=10):
    """Obtener contactos de comunicación reciente."""
    return []


def _get_favorite_contacts(user_id):
    """Obtener contactos favoritos."""
    return []


def _get_contact_groups(user_id):
    """Obtener grupos de contactos."""
    return []


def _get_template_usage_stats(user_id):
    """Obtener estadísticas de uso de plantillas."""
    return {}


def _get_template_categories():
    """Obtener categorías de plantillas."""
    return ['General', 'Seguimiento', 'Propuesta', 'Agradecimiento']


def _mark_specific_messages_as_read(message_ids, user_id):
    """Marcar mensajes específicos como leídos."""
    count = Message.query.filter(
        and_(
            Message.id.in_(message_ids),
            Message.sender_id != user_id,
            Message.is_read == False
        )
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)}, synchronize_session=False)
    
    from app import db
    db.session.commit()
    return count


def _mark_conversation_as_read(conversation_id, user_id):
    """Marcar toda la conversación como leída."""
    count = Message.query.filter(
        and_(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)}, synchronize_session=False)
    
    from app import db
    db.session.commit()
    return count


def _send_typing_indicator(conversation_id, user_id, is_typing):
    """Enviar indicador de tipeo en tiempo real."""
    # Enviar via WebSocket a otros participantes
    pass


def _get_conversations_for_api(user_id, folder, limit):
    """Obtener conversaciones para API."""
    return []


def _get_messages_for_api(conversation_id, since_id, limit):
    """Obtener mensajes para API."""
    query = Message.query.filter_by(conversation_id=conversation_id)
    
    if since_id:
        query = query.filter(Message.id > since_id)
    
    return query.order_by(desc(Message.created_at)).limit(limit).all()


def _format_conversation_for_api(conversation):
    """Formatear conversación para API."""
    return {
        'id': conversation.id,
        'subject': conversation.subject,
        'last_activity': conversation.last_activity_at.isoformat() if conversation.last_activity_at else None,
        'unread_count': 0,  # Calcular
        'participants': [
            {
                'id': p.user.id,
                'name': p.user.full_name,
                'avatar': p.user.profile_picture_url
            } for p in conversation.participants
        ]
    }


def _format_message_for_api(message):
    """Formatear mensaje para API."""
    return {
        'id': message.id,
        'content': message.content,
        'sender': {
            'id': message.sender.id,
            'name': message.sender.full_name,
            'avatar': message.sender.profile_picture_url
        },
        'created_at': message.created_at.isoformat(),
        'is_read': message.is_read,
        'priority': message.priority.value,
        'attachments': [
            {
                'id': att.id,
                'filename': att.filename,
                'size': att.file_size,
                'url': url_for('entrepreneur_messages.download_attachment', attachment_id=att.id)
            } for att in message.attachments
        ]
    }


def _validate_attachment_file(file):
    """Validar archivo adjunto."""
    if not file or file.filename == '':
        return {'valid': False, 'error': 'No se seleccionó archivo'}
    
    # Verificar extensión
    extension = get_file_extension(file.filename).lower()
    if extension not in ALLOWED_ATTACHMENT_TYPES:
        return {'valid': False, 'error': f'Tipo de archivo no permitido: .{extension}'}
    
    # Verificar tamaño
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_ATTACHMENT_SIZE:
        return {'valid': False, 'error': f'Archivo muy grande (máximo {format_file_size(MAX_ATTACHMENT_SIZE)})'}
    
    return {'valid': True, 'file_size': file_size}


def _save_message_attachment(file, user_id):
    """Guardar adjunto de mensaje."""
    filename = secure_filename(file.filename)
    file_path = g.file_storage.save_file(
        file, 
        f"message_attachments/{user_id}/{filename}"
    )
    
    return {
        'filename': filename,
        'file_path': file_path,
        'file_size': os.path.getsize(file_path),
        'mime_type': file.content_type
    }


# Funciones de analytics (implementación simplificada)
def _get_communication_analytics(user_id, start_date, end_date):
    return {}

def _get_response_time_analysis(user_id, start_date, end_date):
    return {}

def _get_communication_patterns(user_id, start_date, end_date):
    return {}

def _get_top_communication_contacts(user_id, start_date, end_date, limit):
    return []

def _get_message_content_analysis(user_id, start_date, end_date):
    return {}

def _get_communication_temporal_trends(user_id, start_date, end_date):
    return {}

def _get_template_effectiveness_metrics(user_id, start_date, end_date):
    return {}

def _load_current_message_settings(form, user_id):
    """Cargar configuraciones actuales."""
    pass

def _update_message_settings(user_id, form):
    """Actualizar configuraciones."""
    pass


# === RUTAS ADICIONALES ===

@entrepreneur_messages.route('/download/<int:attachment_id>')
@login_required
@require_role('entrepreneur')
def download_attachment(attachment_id):
    """Descargar adjunto de mensaje."""
    try:
        attachment = MessageAttachment.query.get_or_404(attachment_id)
        
        # Verificar permisos
        if not _can_access_conversation(attachment.message.conversation, current_user.id):
            abort(403)
        
        file_path = g.file_storage.get_file_path(attachment.file_path)
        
        if not os.path.exists(file_path):
            abort(404)
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=attachment.filename
        )
    
    except Exception as e:
        current_app.logger.error(f"Error descargando adjunto: {str(e)}")
        abort(500)


# === MANEJADORES DE ERRORES ===

@entrepreneur_messages.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


@entrepreneur_messages.errorhandler(ResourceNotFoundError)
def handle_not_found_error(error):
    """Manejar errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 404
    else:
        flash(str(error), 'error')
        return redirect(url_for('entrepreneur_messages.inbox'))


# === CONTEXT PROCESSORS ===

@entrepreneur_messages.context_processor
def inject_message_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_relative_time': format_relative_time,
        'format_file_size': format_file_size,
        'format_message_preview': format_message_preview,
        'truncate_text': truncate_text,
        'MessagePriority': MessagePriority,
        'MessageType': MessageType,
        'MessageStatus': MessageStatus,
        'priority_colors': PRIORITY_COLORS,
        'type_icons': TYPE_ICONS,
        'max_message_length': MAX_MESSAGE_LENGTH,
        'max_attachments': MAX_ATTACHMENTS_PER_MESSAGE
    }