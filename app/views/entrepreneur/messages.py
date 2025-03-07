from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from app.models.message import Message
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.forms.entrepreneur import MessageForm
from app.extensions import db
from app.utils.decorators import entrepreneur_required
from app.utils.notifications import send_message_notification
from app.sockets.events import emit_new_message

# Crear el blueprint para las rutas de mensajes de emprendedores
entrepreneur_messages = Blueprint('entrepreneur_messages', __name__)

@entrepreneur_messages.route('/messages')
@login_required
@entrepreneur_required
def messages():
    """Vista principal de mensajes para el emprendedor."""
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los aliados asignados al emprendedor
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Obtener el ID del usuario seleccionado si existe
    selected_user_id = request.args.get('user_id', None)
    
    # Lista para almacenar las conversaciones
    conversations = []
    
    # Obtener las conversaciones del emprendedor con sus aliados
    for ally in allies:
        # Contar mensajes no leídos para este aliado
        unread_count = Message.query.filter_by(
            recipient_id=current_user.id,
            sender_id=ally.user_id,
            read=False
        ).count()
        
        # Obtener el último mensaje intercambiado con este aliado
        last_message = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == ally.user_id)) |
            ((Message.sender_id == ally.user_id) & (Message.recipient_id == current_user.id))
        ).order_by(Message.created_at.desc()).first()
        
        conversations.append({
            'user': ally.user,
            'unread_count': unread_count,
            'last_message': last_message
        })
    
    # Ordenar conversaciones por la fecha del último mensaje
    conversations.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else None, reverse=True)
    
    selected_user = None
    messages = []
    
    # Si hay un usuario seleccionado, cargar los mensajes correspondientes
    if selected_user_id:
        selected_user = User.query.get_or_404(selected_user_id)
        
        # Marcar mensajes como leídos
        unread_messages = Message.query.filter_by(
            recipient_id=current_user.id,
            sender_id=selected_user_id,
            read=False
        ).all()
        
        for msg in unread_messages:
            msg.read = True
        
        db.session.commit()
        
        # Obtener todos los mensajes entre el emprendedor y el usuario seleccionado
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == selected_user_id)) |
            ((Message.sender_id == selected_user_id) & (Message.recipient_id == current_user.id))
        ).order_by(Message.created_at).all()
    
    # Crear formulario para nuevo mensaje
    form = MessageForm()
    
    return render_template(
        'entrepreneur/messages.html',
        conversations=conversations,
        selected_user=selected_user,
        messages=messages,
        form=form
    )

@entrepreneur_messages.route('/messages/send', methods=['POST'])
@login_required
@entrepreneur_required
def send_message():
    """Enviar un nuevo mensaje."""
    form = MessageForm()
    
    if form.validate_on_submit():
        recipient_id = form.recipient_id.data
        content = form.content.data
        
        # Verificar que el destinatario existe y es un aliado del emprendedor
        entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
        ally = Ally.query.join(Ally.user).filter(User.id == recipient_id).first()
        
        if not ally:
            flash('El destinatario no es válido.', 'error')
            return redirect(url_for('entrepreneur_messages.messages'))
        
        # Crear el nuevo mensaje
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            content=content
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Emitir evento de socket para actualización en tiempo real
        emit_new_message(message)
        
        # Enviar notificación al destinatario
        send_message_notification(message)
        
        return redirect(url_for('entrepreneur_messages.messages', user_id=recipient_id))
    
    flash('Error al enviar el mensaje.', 'error')
    return redirect(url_for('entrepreneur_messages.messages'))

@entrepreneur_messages.route('/messages/load/<int:user_id>', methods=['GET'])
@login_required
@entrepreneur_required
def load_messages(user_id):
    """Cargar mensajes para un usuario específico vía AJAX."""
    # Verificar que el usuario existe
    user = User.query.get_or_404(user_id)
    
    # Marcar mensajes como leídos
    unread_messages = Message.query.filter_by(
        recipient_id=current_user.id,
        sender_id=user_id,
        read=False
    ).all()
    
    for msg in unread_messages:
        msg.read = True
    
    db.session.commit()
    
    # Obtener todos los mensajes entre el emprendedor y el usuario seleccionado
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at).all()
    
    # Convertir mensajes a formato JSON
    messages_data = []
    for message in messages:
        messages_data.append({
            'id': message.id,
            'content': message.content,
            'sender_id': message.sender_id,
            'recipient_id': message.recipient_id,
            'created_at': message.created_at.strftime('%d/%m/%Y %H:%M'),
            'is_mine': message.sender_id == current_user.id
        })
    
    return jsonify({'messages': messages_data, 'user': {'id': user.id, 'name': user.full_name}})

@entrepreneur_messages.route('/messages/check_new', methods=['GET'])
@login_required
@entrepreneur_required
def check_new_messages():
    """Verificar si hay nuevos mensajes (para polling si no hay WebSockets)."""
    last_check = request.args.get('last_check', None)
    
    if last_check:
        # Contar nuevos mensajes desde la última verificación
        from datetime import datetime
        
        last_check_time = datetime.fromisoformat(last_check)
        new_messages_count = Message.query.filter_by(
            recipient_id=current_user.id,
            read=False
        ).filter(Message.created_at > last_check_time).count()
        
        return jsonify({'new_messages': new_messages_count})
    
    return jsonify({'new_messages': 0})