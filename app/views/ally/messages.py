from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, desc
from datetime import datetime

from app.models.message import Message
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.forms.ally import MessageForm
from app.extensions import db
from app.utils.decorators import ally_required
from app.utils.notifications import send_message_notification

# Crear un blueprint para las vistas de mensajes del aliado
ally_messages = Blueprint('ally_messages', __name__, url_prefix='/ally/messages')

@ally_messages.route('/', methods=['GET'])
@login_required
@ally_required
def messages_dashboard():
    """Vista principal del panel de mensajes para aliados"""
    
    # Obtener el objeto Ally asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los emprendedores asignados al aliado
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    entrepreneurs = Entrepreneur.query.filter(Entrepreneur.id.in_(entrepreneur_ids)).all()
    
    # Si hay un emprendedor seleccionado en la URL
    selected_entrepreneur_id = request.args.get('entrepreneur_id', type=int)
    selected_entrepreneur = None
    
    if selected_entrepreneur_id:
        selected_entrepreneur = Entrepreneur.query.get_or_404(selected_entrepreneur_id)
        # Verificar que el emprendedor está asignado a este aliado
        if selected_entrepreneur.id not in entrepreneur_ids:
            flash('No tienes permiso para ver los mensajes de este emprendedor', 'danger')
            return redirect(url_for('ally_messages.messages_dashboard'))
    elif entrepreneurs:
        # Si no hay emprendedor seleccionado pero hay disponibles, seleccionar el primero
        selected_entrepreneur = entrepreneurs[0]
    
    # Formulario para enviar mensajes
    form = MessageForm()
    
    return render_template(
        'ally/messages.html',
        entrepreneurs=entrepreneurs,
        selected_entrepreneur=selected_entrepreneur,
        form=form
    )

@ally_messages.route('/conversation/<int:entrepreneur_id>', methods=['GET'])
@login_required
@ally_required
def load_conversation(entrepreneur_id):
    """Carga la conversación con un emprendedor específico"""
    
    # Obtener el objeto Ally asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Verificar que el emprendedor está asignado a este aliado
    relationship = Relationship.query.filter_by(
        ally_id=ally.id, 
        entrepreneur_id=entrepreneur_id
    ).first_or_404()
    
    # Obtener el emprendedor
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Cargar mensajes entre el aliado y el emprendedor
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id==current_user.id, Message.receiver_id==entrepreneur.user_id),
            and_(Message.sender_id==entrepreneur.user_id, Message.receiver_id==current_user.id)
        )
    ).order_by(Message.timestamp).all()
    
    # Marcar mensajes no leídos como leídos
    unread_messages = Message.query.filter_by(
        receiver_id=current_user.id,
        sender_id=entrepreneur.user_id,
        read=False
    ).all()
    
    for message in unread_messages:
        message.read = True
    
    db.session.commit()
    
    # Formatear mensajes para JSON
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_mine': msg.sender_id == current_user.id
        })
    
    return jsonify({
        'entrepreneur': {
            'id': entrepreneur.id,
            'name': entrepreneur.user.full_name,
            'profile_pic': entrepreneur.user.profile_pic or url_for('static', filename='images/default-profile.png')
        },
        'messages': messages_data
    })

@ally_messages.route('/send', methods=['POST'])
@login_required
@ally_required
def send_message():
    """Envía un mensaje a un emprendedor"""
    
    form = MessageForm()
    
    if form.validate_on_submit():
        entrepreneur_id = request.form.get('entrepreneur_id', type=int)
        content = form.content.data
        
        # Obtener el emprendedor
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar que el emprendedor está asignado a este aliado
        ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
        relationship = Relationship.query.filter_by(
            ally_id=ally.id, 
            entrepreneur_id=entrepreneur_id
        ).first_or_404()
        
        # Crear y guardar el mensaje
        message = Message(
            content=content,
            sender_id=current_user.id,
            receiver_id=entrepreneur.user_id,
            timestamp=datetime.utcnow(),
            read=False
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Enviar notificación al emprendedor
        send_message_notification(entrepreneur.user, current_user)
        
        return jsonify({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'is_mine': True
            }
        })
    
    return jsonify({'status': 'error', 'errors': form.errors}), 400

@ally_messages.route('/unread', methods=['GET'])
@login_required
@ally_required
def get_unread_count():
    """Obtiene el conteo de mensajes no leídos"""
    
    # Obtener el objeto Ally asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los emprendedores asignados al aliado
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    entrepreneurs = Entrepreneur.query.filter(Entrepreneur.id.in_(entrepreneur_ids)).all()
    
    # Obtener IDs de usuarios emprendedores
    entrepreneur_user_ids = [e.user_id for e in entrepreneurs]
    
    # Contar mensajes no leídos de cada emprendedor
    unread_counts = {}
    total_unread = 0
    
    for e_id, e_user_id in zip([e.id for e in entrepreneurs], entrepreneur_user_ids):
        count = Message.query.filter_by(
            sender_id=e_user_id,
            receiver_id=current_user.id,
            read=False
        ).count()
        
        unread_counts[e_id] = count
        total_unread += count
    
    return jsonify({
        'total_unread': total_unread,
        'unread_by_entrepreneur': unread_counts
    })

@ally_messages.route('/search', methods=['GET'])
@login_required
@ally_required
def search_messages():
    """Busca mensajes por contenido"""
    
    entrepreneur_id = request.args.get('entrepreneur_id', type=int)
    query = request.args.get('q', '')
    
    if not entrepreneur_id or not query:
        return jsonify({'status': 'error', 'message': 'Faltan parámetros'}), 400
    
    # Verificar que el emprendedor está asignado a este aliado
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    relationship = Relationship.query.filter_by(
        ally_id=ally.id, 
        entrepreneur_id=entrepreneur_id
    ).first_or_404()
    
    # Buscar mensajes que coincidan con la consulta
    messages = Message.query.filter(
        Message.content.ilike(f'%{query}%'),
        or_(
            and_(Message.sender_id==current_user.id, Message.receiver_id==entrepreneur.user_id),
            and_(Message.sender_id==entrepreneur.user_id, Message.receiver_id==current_user.id)
        )
    ).order_by(desc(Message.timestamp)).limit(20).all()
    
    # Formatear mensajes para JSON
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_mine': msg.sender_id == current_user.id
        })
    
    return jsonify({
        'status': 'success',
        'results': messages_data
    })

def init_app(app):
    """Registra el blueprint en la aplicación Flask"""
    app.register_blueprint(ally_messages)
    