from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.message import Message
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.document import Document
from app.models.relationship import Relationship
from app.forms.entrepreneur import TaskForm, DocumentUploadForm
from app.extensions import db
from app.utils.decorators import entrepreneur_required
from app.utils.formatters import format_date
from app.services.storage import upload_file, get_file_url

# Crear el blueprint para el escritorio del emprendedor
entrepreneur_desktop = Blueprint('entrepreneur_desktop', __name__)

@entrepreneur_desktop.route('/desktop')
@login_required
@entrepreneur_required
def desktop():
    """Vista principal del escritorio de trabajo para el emprendedor."""
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los aliados asignados al emprendedor
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Obtener las próximas 5 reuniones
    upcoming_meetings = Meeting.query.filter(
        (Meeting.creator_id == current_user.id) | (Meeting.attendees.any(id=current_user.id)),
        Meeting.start_time >= datetime.now()
    ).order_by(Meeting.start_time).limit(5).all()
    
    # Obtener las últimas 5 tareas
    recent_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).order_by(
        Task.completed.asc(), Task.due_date.asc(), Task.created_at.desc()
    ).limit(5).all()
    
    # Obtener los últimos 5 documentos
    recent_documents = Document.query.filter_by(entrepreneur_id=entrepreneur.id).order_by(
        Document.created_at.desc()
    ).limit(5).all()
    
    # Obtener mensajes no leídos
    unread_messages_count = Message.query.filter_by(
        recipient_id=current_user.id,
        read=False
    ).count()
    
    # Calcular progreso general
    total_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).count()
    completed_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id, completed=True).count()
    progress = 0
    if total_tasks > 0:
        progress = int((completed_tasks / total_tasks) * 100)
    
    # Obtener formularios
    task_form = TaskForm()
    document_form = DocumentUploadForm()
    
    # Para el formulario de tareas, precargar opciones de asignados
    task_form.assigned_to.choices = [(ally.user_id, ally.user.full_name) for ally in allies]
    task_form.assigned_to.choices.insert(0, (current_user.id, 'Yo mismo'))
    
    return render_template(
        'entrepreneur/desktop.html',
        entrepreneur=entrepreneur,
        allies=allies,
        upcoming_meetings=upcoming_meetings,
        recent_tasks=recent_tasks,
        recent_documents=recent_documents,
        unread_messages_count=unread_messages_count,
        progress=progress,
        task_form=task_form,
        document_form=document_form
    )

@entrepreneur_desktop.route('/desktop/tasks/create', methods=['POST'])
@login_required
@entrepreneur_required
def create_task():
    """Crear una nueva tarea."""
    form = TaskForm()
    
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener aliados para poblar el selector de asignado
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    form.assigned_to.choices = [(ally.user_id, ally.user.full_name) for ally in allies]
    form.assigned_to.choices.insert(0, (current_user.id, 'Yo mismo'))
    
    if form.validate_on_submit():
        # Crear la tarea
        task = Task(
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
            status='pending',
            completed=False,
            entrepreneur_id=entrepreneur.id,
            assigned_to=form.assigned_to.data,
            created_by=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Tarea creada exitosamente.', 'success')
        return redirect(url_for('entrepreneur_desktop.desktop'))
    
    # Si hay errores en el formulario
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('entrepreneur_desktop.desktop'))

@entrepreneur_desktop.route('/desktop/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
@entrepreneur_required
def toggle_task(task_id):
    """Marcar una tarea como completada o pendiente."""
    task = Task.query.get_or_404(task_id)
    
    # Verificar que la tarea pertenece al emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    if task.entrepreneur_id != entrepreneur.id:
        flash('No tienes permiso para modificar esta tarea.', 'error')
        return redirect(url_for('entrepreneur_desktop.desktop'))
    
    # Cambiar el estado de la tarea
    task.completed = not task.completed
    task.status = 'completed' if task.completed else 'pending'
    task.completed_at = datetime.now() if task.completed else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'completed': task.completed,
        'status': task.status
    })

@entrepreneur_desktop.route('/desktop/documents/upload', methods=['POST'])
@login_required
@entrepreneur_required
def upload_document():
    """Subir un nuevo documento."""
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        # Obtener el emprendedor actual
        entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Procesar el archivo
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                try:
                    # Subir archivo al servicio de almacenamiento
                    file_path = upload_file(
                        file,
                        folder=f'entrepreneurs/{entrepreneur.id}/documents',
                        allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
                    )
                    
                    # Crear registro del documento
                    document = Document(
                        title=form.title.data,
                        description=form.description.data,
                        file_path=file_path,
                        file_name=file.filename,
                        file_type=file.content_type,
                        entrepreneur_id=entrepreneur.id,
                        uploaded_by=current_user.id
                    )
                    
                    db.session.add(document)
                    db.session.commit()
                    
                    flash('Documento subido exitosamente.', 'success')
                    
                except Exception as e:
                    current_app.logger.error(f"Error al subir documento: {str(e)}")
                    flash('Error al subir el documento. Intenta nuevamente.', 'error')
            else:
                flash('Por favor selecciona un archivo para subir.', 'error')
        else:
            flash('No se recibió ningún archivo.', 'error')
    else:
        # Si hay errores en el formulario
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('entrepreneur_desktop.desktop'))

@entrepreneur_desktop.route('/desktop/summary')
@login_required
@entrepreneur_required
def summary():
    """Obtener resumen de actividades para el dashboard."""
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Calcular estadísticas
    total_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).count()
    completed_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id, completed=True).count()
    pending_tasks = total_tasks - completed_tasks
    
    total_meetings = Meeting.query.filter(
        (Meeting.creator_id == current_user.id) | (Meeting.attendees.any(id=current_user.id))
    ).count()
    upcoming_meetings = Meeting.query.filter(
        (Meeting.creator_id == current_user.id) | (Meeting.attendees.any(id=current_user.id)),
        Meeting.start_time >= datetime.now()
    ).count()
    
    total_documents = Document.query.filter_by(entrepreneur_id=entrepreneur.id).count()
    
    unread_messages = Message.query.filter_by(
        recipient_id=current_user.id,
        read=False
    ).count()
    
    # Calcular horas de acompañamiento
    relationships = Relationship.query.filter_by(entrepreneur_id=entrepreneur.id).all()
    total_hours = sum(rel.total_hours for rel in relationships)
    
    # Datos para gráfico de actividad semanal (últimos 7 días)
    today = datetime.now().date()
    week_start = today - timedelta(days=6)
    
    activity_data = []
    for i in range(7):
        current_date = week_start + timedelta(days=i)
        next_date = current_date + timedelta(days=1)
        
        # Contar tareas creadas en este día
        day_tasks = Task.query.filter(
            Task.entrepreneur_id == entrepreneur.id,
            Task.created_at >= datetime.combine(current_date, datetime.min.time()),
            Task.created_at < datetime.combine(next_date, datetime.min.time())
        ).count()
        
        # Contar reuniones en este día
        day_meetings = Meeting.query.filter(
            (Meeting.creator_id == current_user.id) | (Meeting.attendees.any(id=current_user.id)),
            Meeting.start_time >= datetime.combine(current_date, datetime.min.time()),
            Meeting.start_time < datetime.combine(next_date, datetime.min.time())
        ).count()
        
        # Contar documentos subidos en este día
        day_documents = Document.query.filter(
            Document.entrepreneur_id == entrepreneur.id,
            Document.created_at >= datetime.combine(current_date, datetime.min.time()),
            Document.created_at < datetime.combine(next_date, datetime.min.time())
        ).count()
        
        activity_data.append({
            'date': format_date(current_date, format='%d/%m'),
            'tasks': day_tasks,
            'meetings': day_meetings,
            'documents': day_documents
        })
    
    # Datos para gráfico de tareas por prioridad
    high_priority = Task.query.filter_by(entrepreneur_id=entrepreneur.id, priority='high').count()
    medium_priority = Task.query.filter_by(entrepreneur_id=entrepreneur.id, priority='medium').count()
    low_priority = Task.query.filter_by(entrepreneur_id=entrepreneur.id, priority='low').count()
    
    priority_data = [
        {'priority': 'Alta', 'count': high_priority},
        {'priority': 'Media', 'count': medium_priority},
        {'priority': 'Baja', 'count': low_priority}
    ]
    
    return jsonify({
        'stats': {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'total_meetings': total_meetings,
            'upcoming_meetings': upcoming_meetings,
            'total_documents': total_documents,
            'unread_messages': unread_messages,
            'total_hours': total_hours
        },
        'activity_data': activity_data,
        'priority_data': priority_data
    })

@entrepreneur_desktop.route('/desktop/progress')
@login_required
@entrepreneur_required
def get_progress():
    """Obtener el progreso general del emprendedor."""
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Calcular progreso basado en tareas completadas
    total_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).count()
    completed_tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id, completed=True).count()
    
    task_progress = 0
    if total_tasks > 0:
        task_progress = int((completed_tasks / total_tasks) * 100)
    
    # Calcular progreso basado en documentos requeridos
    required_docs = 5  # Ejemplo: número de documentos requeridos por el programa
    uploaded_docs = Document.query.filter_by(entrepreneur_id=entrepreneur.id).count()
    
    doc_progress = min(100, int((uploaded_docs / required_docs) * 100)) if required_docs > 0 else 0
    
    # Calcular progreso general (promedio simple)
    overall_progress = int((task_progress + doc_progress) / 2)
    
    return jsonify({
        'task_progress': task_progress,
        'doc_progress': doc_progress,
        'overall_progress': overall_progress
    })