from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.document import Document
from app.models.message import Message
from app.forms.ally import HoursLogForm, TaskForm, NotesForm
from app.utils.decorators import ally_required
from app.utils.notifications import send_notification

# Crear el blueprint
ally_desktop = Blueprint('ally_desktop', __name__, url_prefix='/ally/desktop')

@ally_desktop.route('/', methods=['GET'])
@login_required
@ally_required
def index():
    """Vista principal del escritorio de acompañamiento del aliado"""
    # Obtener emprendedores asignados al aliado
    relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneurs = [rel.entrepreneur for rel in relationships]
    
    # Obtener reuniones próximas
    upcoming_meetings = Meeting.query.filter_by(ally_id=current_user.ally.id)\
        .filter(Meeting.start_time > datetime.now())\
        .filter(Meeting.start_time < datetime.now() + timedelta(days=7))\
        .order_by(Meeting.start_time)\
        .limit(5)\
        .all()
    
    # Obtener tareas pendientes
    pending_tasks = Task.query.filter_by(
        assigned_by_id=current_user.id, 
        status='pending'
    ).order_by(Task.due_date).limit(5).all()
    
    # Formularios
    hours_form = HoursLogForm()
    task_form = TaskForm()
    notes_form = NotesForm()
    
    # Si hay emprendedores, poblar los select de los formularios
    if entrepreneurs:
        hours_form.entrepreneur_id.choices = [(e.id, f"{e.user.first_name} {e.user.last_name}") for e in entrepreneurs]
        task_form.entrepreneur_id.choices = [(e.id, f"{e.user.first_name} {e.user.last_name}") for e in entrepreneurs]
        notes_form.entrepreneur_id.choices = [(e.id, f"{e.user.first_name} {e.user.last_name}") for e in entrepreneurs]
    
    # Obtener mensajes recientes
    recent_messages = Message.query.filter(
        (Message.sender_id == current_user.id) | 
        (Message.recipient_id == current_user.id)
    ).order_by(Message.timestamp.desc()).limit(5).all()
    
    # Obtener horas registradas este mes
    first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    hours_this_month = db.session.query(func.sum(Relationship.hours_logged))\
        .filter(Relationship.ally_id == current_user.ally.id)\
        .filter(Relationship.last_hours_update >= first_day)\
        .scalar() or 0
    
    # Renderizar la plantilla
    return render_template('ally/desktop.html',
                          entrepreneurs=entrepreneurs,
                          upcoming_meetings=upcoming_meetings,
                          pending_tasks=pending_tasks,
                          recent_messages=recent_messages,
                          hours_form=hours_form,
                          task_form=task_form,
                          notes_form=notes_form,
                          hours_this_month=hours_this_month,
                          title='Escritorio de Acompañamiento')

@ally_desktop.route('/entrepreneur/<int:entrepreneur_id>', methods=['GET'])
@login_required
@ally_required
def entrepreneur_workspace(entrepreneur_id):
    """Escritorio de trabajo específico para un emprendedor"""
    # Verificar que el emprendedor está asignado al aliado
    relationship = Relationship.query.filter_by(
        ally_id=current_user.ally.id,
        entrepreneur_id=entrepreneur_id
    ).first_or_404()
    
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Obtener reuniones con este emprendedor
    meetings = Meeting.query.filter_by(
        ally_id=current_user.ally.id,
        entrepreneur_id=entrepreneur_id
    ).order_by(Meeting.start_time.desc()).limit(5).all()
    
    # Obtener tareas asignadas a este emprendedor
    tasks = Task.query.filter_by(
        assigned_by_id=current_user.id,
        entrepreneur_id=entrepreneur_id
    ).order_by(Task.due_date).all()
    
    # Obtener documentos compartidos con este emprendedor
    documents = Document.query.filter(
        ((Document.owner_id == current_user.id) & (Document.shared_with.contains([entrepreneur.user_id]))) |
        ((Document.owner_id == entrepreneur.user_id) & (Document.shared_with.contains([current_user.id])))
    ).order_by(Document.updated_at.desc()).all()
    
    # Obtener mensajes intercambiados con este emprendedor
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == entrepreneur.user_id)) |
        ((Message.sender_id == entrepreneur.user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.desc()).limit(10).all()
    
    # Formularios
    hours_form = HoursLogForm()
    hours_form.entrepreneur_id.data = entrepreneur_id
    
    task_form = TaskForm()
    task_form.entrepreneur_id.data = entrepreneur_id
    
    notes_form = NotesForm()
    notes_form.entrepreneur_id.data = entrepreneur_id
    
    # Renderizar la plantilla
    return render_template('ally/entrepreneur_workspace.html',
                          entrepreneur=entrepreneur,
                          relationship=relationship,
                          meetings=meetings,
                          tasks=tasks,
                          documents=documents,
                          messages=messages,
                          hours_form=hours_form,
                          task_form=task_form,
                          notes_form=notes_form,
                          title=f'Workspace - {entrepreneur.user.first_name} {entrepreneur.user.last_name}')

@ally_desktop.route('/log-hours', methods=['POST'])
@login_required
@ally_required
def log_hours():
    """Registrar horas de acompañamiento a un emprendedor"""
    form = HoursLogForm()
    
    # Obtener emprendedores asignados para validación
    relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    form.entrepreneur_id.choices = [(id, "") for id in entrepreneur_ids]
    
    if form.validate_on_submit():
        entrepreneur_id = form.entrepreneur_id.data
        hours = form.hours.data
        description = form.description.data
        date = form.date.data
        
        # Verificar que el emprendedor está asignado al aliado
        if entrepreneur_id not in entrepreneur_ids:
            flash('No tienes permiso para registrar horas con este emprendedor', 'danger')
            return redirect(url_for('ally_desktop.index'))
        
        # Obtener la relación
        relationship = Relationship.query.filter_by(
            ally_id=current_user.ally.id,
            entrepreneur_id=entrepreneur_id
        ).first()
        
        # Actualizar horas y registro
        relationship.hours_logged += hours
        relationship.last_hours_update = datetime.now()
        
        # Guardar registro en el historial
        relationship.hours_history.append({
            'date': date.strftime('%Y-%m-%d'),
            'hours': hours,
            'description': description
        })
        
        db.session.commit()
        
        # Notificar al emprendedor
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        send_notification(
            user_id=entrepreneur.user_id,
            message=f"Tu aliado ha registrado {hours} horas de acompañamiento",
            type='hours_logged'
        )
        
        flash(f'Se han registrado {hours} horas exitosamente', 'success')
        
        # Redireccionar según la página de origen
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('ally_desktop.index'))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('ally_desktop.index'))

@ally_desktop.route('/assign-task', methods=['POST'])
@login_required
@ally_required
def assign_task():
    """Asignar tarea a un emprendedor"""
    form = TaskForm()
    
    # Obtener emprendedores asignados para validación
    relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    form.entrepreneur_id.choices = [(id, "") for id in entrepreneur_ids]
    
    if form.validate_on_submit():
        entrepreneur_id = form.entrepreneur_id.data
        
        # Verificar que el emprendedor está asignado al aliado
        if entrepreneur_id not in entrepreneur_ids:
            flash('No tienes permiso para asignar tareas a este emprendedor', 'danger')
            return redirect(url_for('ally_desktop.index'))
        
        # Crear la tarea
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        task = Task(
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
            status='pending',
            assigned_by_id=current_user.id,
            assigned_to_id=entrepreneur.user_id,
            entrepreneur_id=entrepreneur_id
        )
        
        db.session.add(task)
        db.session.commit()
        
        # Notificar al emprendedor
        send_notification(
            user_id=entrepreneur.user_id,
            message=f"Nueva tarea asignada: {form.title.data}",
            link=url_for('entrepreneur.tasks.index'),
            type='task_assigned'
        )
        
        flash('Tarea asignada exitosamente', 'success')
        
        # Redireccionar según la página de origen
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('ally_desktop.index'))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('ally_desktop.index'))

@ally_desktop.route('/save-notes', methods=['POST'])
@login_required
@ally_required
def save_notes():
    """Guardar notas de acompañamiento para un emprendedor"""
    form = NotesForm()
    
    # Obtener emprendedores asignados para validación
    relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    form.entrepreneur_id.choices = [(id, "") for id in entrepreneur_ids]
    
    if form.validate_on_submit():
        entrepreneur_id = form.entrepreneur_id.data
        notes = form.notes.data
        is_private = form.is_private.data
        
        # Verificar que el emprendedor está asignado al aliado
        if entrepreneur_id not in entrepreneur_ids:
            flash('No tienes permiso para guardar notas para este emprendedor', 'danger')
            return redirect(url_for('ally_desktop.index'))
        
        # Obtener la relación
        relationship = Relationship.query.filter_by(
            ally_id=current_user.ally.id,
            entrepreneur_id=entrepreneur_id
        ).first()
        
        # Guardar las notas
        note_entry = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'content': notes,
            'is_private': is_private
        }
        
        if 'notes' not in relationship.metadata:
            relationship.metadata['notes'] = []
        
        relationship.metadata['notes'].append(note_entry)
        db.session.commit()
        
        # Si las notas no son privadas, notificar al emprendedor
        if not is_private:
            entrepreneur = Entrepreneur.query.get(entrepreneur_id)
            send_notification(
                user_id=entrepreneur.user_id,
                message="Tu aliado ha compartido nuevas notas de acompañamiento",
                link=url_for('entrepreneur.profile.index'),
                type='notes_shared'
            )
        
        flash('Notas guardadas exitosamente', 'success')
        
        # Redireccionar según la página de origen
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('ally_desktop.index'))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('ally_desktop.index'))

@ally_desktop.route('/notes/<int:entrepreneur_id>', methods=['GET'])
@login_required
@ally_required
def get_notes(entrepreneur_id):
    """Obtener notas de acompañamiento para un emprendedor"""
    # Verificar que el emprendedor está asignado al aliado
    relationship = Relationship.query.filter_by(
        ally_id=current_user.ally.id,
        entrepreneur_id=entrepreneur_id
    ).first_or_404()
    
    notes = relationship.metadata.get('notes', [])
    
    return jsonify(notes)

@ally_desktop.route('/hours-history/<int:entrepreneur_id>', methods=['GET'])
@login_required
@ally_required
def get_hours_history(entrepreneur_id):
    """Obtener historial de horas para un emprendedor"""
    # Verificar que el emprendedor está asignado al aliado
    relationship = Relationship.query.filter_by(
        ally_id=current_user.ally.id,
        entrepreneur_id=entrepreneur_id
    ).first_or_404()
    
    history = relationship.hours_history or []
    
    return jsonify(history)

@ally_desktop.route('/summary', methods=['GET'])
@login_required
@ally_required
def summary():
    """Resumen de actividad del aliado"""
    # Rango de fechas para el resumen (último mes por defecto)
    end_date = datetime.now()
    start_date = request.args.get('start_date', (end_date - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', end_date.strftime('%Y-%m-%d'))
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Obtener relaciones con emprendedores
    relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [rel.entrepreneur_id for rel in relationships]
    
    # Estadísticas de reuniones
    meetings_count = Meeting.query.filter_by(ally_id=current_user.ally.id)\
        .filter(Meeting.start_time >= start_date)\
        .filter(Meeting.end_time <= end_date)\
        .count()
    
    # Estadísticas de tareas
    tasks_assigned = Task.query.filter_by(assigned_by_id=current_user.id)\
        .filter(Task.created_at >= start_date)\
        .filter(Task.created_at <= end_date)\
        .count()
    
    tasks_completed = Task.query.filter_by(assigned_by_id=current_user.id, status='completed')\
        .filter(Task.completed_at >= start_date)\
        .filter(Task.completed_at <= end_date)\
        .count()
    
    # Horas registradas
    total_hours = 0
    hours_by_entrepreneur = []
    
    for rel in relationships:
        entrepreneur_hours = 0
        if rel.hours_history:
            for entry in rel.hours_history:
                entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                if start_date <= entry_date <= end_date:
                    entrepreneur_hours += entry['hours']
                    total_hours += entry['hours']
        
        entrepreneur = Entrepreneur.query.get(rel.entrepreneur_id)
        hours_by_entrepreneur.append({
            'entrepreneur': f"{entrepreneur.user.first_name} {entrepreneur.user.last_name}",
            'hours': entrepreneur_hours
        })
    
    # Ordenar por horas (mayor a menor)
    hours_by_entrepreneur.sort(key=lambda x: x['hours'], reverse=True)
    
    summary_data = {
        'total_entrepreneurs': len(entrepreneur_ids),
        'total_hours': total_hours,
        'meetings_count': meetings_count,
        'tasks_assigned': tasks_assigned,
        'tasks_completed': tasks_completed,
        'completion_rate': (tasks_completed / tasks_assigned * 100) if tasks_assigned > 0 else 0,
        'hours_by_entrepreneur': hours_by_entrepreneur,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d')
    }
    
    return render_template('ally/summary.html', 
                          summary=summary_data,
                          title='Resumen de Actividad')