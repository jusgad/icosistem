from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc

from app.extensions import db
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship, MeetingNote, ActionItem
from app.models.message import Message
from app.models.document import Document
from app.models.task import Task
from app.forms.ally import MeetingNoteForm, ActionItemForm, RelationshipProgressForm
from app.utils.decorators import ally_required
from app.utils.formatters import format_date
from app.utils.notifications import send_notification

# Crear el Blueprint para las vistas de emprendedores asignados al aliado
bp = Blueprint('ally_entrepreneurs', __name__, url_prefix='/ally/entrepreneurs')

@bp.route('/', methods=['GET'])
@login_required
@ally_required
def list_entrepreneurs():
    """Vista para listar los emprendedores asignados al aliado"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los emprendedores asignados al aliado
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    
    # Compilar datos para la plantilla
    entrepreneurs_data = []
    for rel in relationships:
        entrepreneur = Entrepreneur.query.get(rel.entrepreneur_id)
        
        # Calcular estadísticas básicas
        last_meeting = MeetingNote.query.filter_by(relationship_id=rel.id).order_by(desc(MeetingNote.meeting_date)).first()
        pending_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='pendiente').count()
        unread_messages = Message.query.filter_by(
            receiver_id=current_user.id, 
            sender_id=entrepreneur.user_id,
            read=False
        ).count()
        
        entrepreneurs_data.append({
            'entrepreneur': entrepreneur,
            'relationship': rel,
            'last_meeting': last_meeting,
            'pending_tasks': pending_tasks,
            'unread_messages': unread_messages
        })
    
    return render_template('ally/entrepreneurs.html', 
                          entrepreneurs_data=entrepreneurs_data,
                          ally=ally)

@bp.route('/<int:entrepreneur_id>', methods=['GET'])
@login_required
@ally_required
def entrepreneur_detail(entrepreneur_id):
    """Vista detallada de un emprendedor específico"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener al emprendedor y verificar que esté asignado al aliado
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    relationship = Relationship.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id
    ).first_or_404()
    
    # Obtener datos adicionales del emprendedor
    meeting_notes = MeetingNote.query.filter_by(relationship_id=relationship.id).order_by(desc(MeetingNote.meeting_date)).all()
    action_items = ActionItem.query.filter_by(relationship_id=relationship.id).order_by(desc(ActionItem.created_at)).all()
    documents = Document.query.filter_by(entrepreneur_id=entrepreneur.id).order_by(desc(Document.upload_date)).all()
    tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).order_by(desc(Task.due_date)).all()
    
    # Marcar mensajes como leídos
    unread_messages = Message.query.filter_by(
        receiver_id=current_user.id, 
        sender_id=entrepreneur.user_id,
        read=False
    ).all()
    
    for message in unread_messages:
        message.read = True
    
    db.session.commit()
    
    return render_template('ally/entrepreneur_detail.html',
                          entrepreneur=entrepreneur,
                          relationship=relationship,
                          meeting_notes=meeting_notes,
                          action_items=action_items,
                          documents=documents,
                          tasks=tasks)

@bp.route('/<int:entrepreneur_id>/add-meeting-note', methods=['GET', 'POST'])
@login_required
@ally_required
def add_meeting_note(entrepreneur_id):
    """Vista para añadir una nota de reunión"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener al emprendedor y verificar que esté asignado al aliado
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    relationship = Relationship.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id
    ).first_or_404()
    
    # Crear formulario para la nota de reunión
    form = MeetingNoteForm()
    
    if form.validate_on_submit():
        # Crear nueva nota de reunión
        meeting_note = MeetingNote(
            relationship_id=relationship.id,
            meeting_date=form.meeting_date.data,
            duration_minutes=form.duration_minutes.data,
            meeting_type=form.meeting_type.data,
            summary=form.summary.data,
            key_topics=form.key_topics.data,
            next_steps=form.next_steps.data
        )
        
        # Guardar en la base de datos
        db.session.add(meeting_note)
        
        # Actualizar las horas totales del aliado
        relationship.hours += form.duration_minutes.data / 60
        
        db.session.commit()
        
        # Notificar al emprendedor
        send_notification(
            user_id=entrepreneur.user_id,
            title="Nueva nota de reunión",
            message=f"Tu aliado ha registrado una nueva nota de la reunión del {format_date(form.meeting_date.data)}",
            link=url_for('entrepreneur.meetings', _external=True)
        )
        
        flash('Nota de reunión añadida correctamente', 'success')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    return render_template('ally/meeting_note_form.html', 
                          form=form, 
                          entrepreneur=entrepreneur)

@bp.route('/meeting-note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
@ally_required
def edit_meeting_note(note_id):
    """Vista para editar una nota de reunión existente"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la nota de reunión y verificar que pertenezca a una relación del aliado
    meeting_note = MeetingNote.query.get_or_404(note_id)
    relationship = Relationship.query.get_or_404(meeting_note.relationship_id)
    
    if relationship.ally_id != ally.id:
        flash('No tienes permiso para editar esta nota', 'danger')
        return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))
    
    entrepreneur = Entrepreneur.query.get(relationship.entrepreneur_id)
    
    # Calcular las horas anteriores para el ajuste
    previous_hours = meeting_note.duration_minutes / 60
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = MeetingNoteForm(obj=meeting_note)
    
    if form.validate_on_submit():
        # Actualizar la nota de reunión
        form.populate_obj(meeting_note)
        
        # Ajustar las horas totales del aliado
        new_hours = form.duration_minutes.data / 60
        relationship.hours = relationship.hours - previous_hours + new_hours
        
        db.session.commit()
        
        flash('Nota de reunión actualizada correctamente', 'success')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    return render_template('ally/meeting_note_form.html', 
                          form=form,
                          entrepreneur=entrepreneur,
                          meeting_note=meeting_note)

@bp.route('/meeting-note/<int:note_id>/delete', methods=['POST'])
@login_required
@ally_required
def delete_meeting_note(note_id):
    """Vista para eliminar una nota de reunión"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la nota de reunión y verificar que pertenezca a una relación del aliado
    meeting_note = MeetingNote.query.get_or_404(note_id)
    relationship = Relationship.query.get_or_404(meeting_note.relationship_id)
    
    if relationship.ally_id != ally.id:
        flash('No tienes permiso para eliminar esta nota', 'danger')
        return redirect(url_for('ally_entrepreneurs.list_entrepreneurs'))
    
    entrepreneur = Entrepreneur.query.get(relationship.entrepreneur_id)
    
    # Ajustar las horas totales del aliado
    relationship.hours -= meeting_note.duration_minutes / 60
    
    # Eliminar de la base de datos
    db.session.delete(meeting_note)
    db.session.commit()
    
    flash('Nota de reunión eliminada correctamente', 'success')
    return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))

@bp.route('/<int:entrepreneur_id>/add-action-item', methods=['GET', 'POST'])
@login_required
@ally_required
def add_action_item(entrepreneur_id):
    """Vista para añadir un elemento de acción"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener al emprendedor y verificar que esté asignado al aliado
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    relationship = Relationship.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id
    ).first_or_404()
    
    # Crear formulario para el elemento de acción
    form = ActionItemForm()
    
    if form.validate_on_submit():
        # Crear nuevo elemento de acción
        action_item = ActionItem(
            relationship_id=relationship.id,
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
            status='pendiente'
        )
        
        # Guardar en la base de datos
        db.session.add(action_item)
        db.session.commit()
        
        # Notificar al emprendedor
        send_notification(
            user_id=entrepreneur.user_id,
            title="Nueva tarea asignada",
            message=f"Tu aliado te ha asignado una nueva tarea: {form.title.data}",
            link=url_for('entrepreneur.tasks', _external=True)
        )
        
        # También crear una tarea para el emprendedor
        task = Task(
            entrepreneur_id=entrepreneur.id,
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
            status='pendiente',
            assigned_by=current_user.id,
            related_action_item_id=action_item.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Elemento de acción añadido correctamente', 'success')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    return render_template('ally/action_item_form.html', 
                          form=form, 
                          entrepreneur=entrepreneur)

@bp.route('/action-item/<int:item_id>/update-status', methods=['POST'])
@login_required
@ally_required
def update_action_item_status(item_id):
    """Vista para actualizar el estado de un elemento de acción"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener el elemento de acción y verificar que pertenezca a una relación del aliado
    action_item = ActionItem.query.get_or_404(item_id)
    relationship = Relationship.query.get_or_404(action_item.relationship_id)
    
    if relationship.ally_id != ally.id:
        return jsonify(success=False, error='No tienes permiso para actualizar este elemento'), 403
    
    # Obtener el nuevo estado del request
    new_status = request.form.get('status')
    if new_status not in ['pendiente', 'en_progreso', 'completado', 'cancelado']:
        return jsonify(success=False, error='Estado no válido'), 400
    
    # Actualizar el estado
    action_item.status = new_status
    db.session.commit()
    
    # Si hay una tarea relacionada, actualizar también su estado
    if action_item.related_task:
        action_item.related_task.status = new_status
        db.session.commit()
    
    return jsonify(success=True)

@bp.route('/<int:entrepreneur_id>/progress', methods=['GET', 'POST'])
@login_required
@ally_required
def update_progress(entrepreneur_id):
    """Vista para actualizar el progreso del emprendedor"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener al emprendedor y verificar que esté asignado al aliado
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    relationship = Relationship.query.filter_by(
        ally_id=ally.id,
        entrepreneur_id=entrepreneur.id
    ).first_or_404()
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = RelationshipProgressForm(obj=relationship)
    
    if form.validate_on_submit():
        # Guardar el progreso anterior para notificaciones
        previous_stage = relationship.current_stage
        
        # Actualizar datos de progreso
        form.populate_obj(relationship)
        
        # Guardar cambios en la base de datos
        db.session.commit()
        
        # Notificar al emprendedor si hubo cambio de etapa
        if previous_stage != relationship.current_stage:
            send_notification(
                user_id=entrepreneur.user_id,
                title="Actualización de progreso",
                message=f"Tu aliado ha actualizado tu etapa de progreso a: {relationship.current_stage}",
                link=url_for('entrepreneur.dashboard', _external=True)
            )
        
        flash('Progreso actualizado correctamente', 'success')
        return redirect(url_for('ally_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    return render_template('ally/progress_form.html', 
                          form=form,
                          entrepreneur=entrepreneur,
                          relationship=relationship)