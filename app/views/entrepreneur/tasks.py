# app/views/entrepreneur/tasks.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

from app.models.task import Task
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.forms.entrepreneur import TaskForm, TaskFilterForm
from app.extensions import db
from app.utils.decorators import entrepreneur_required
from app.utils.notifications import send_notification
from app.utils.formatters import format_date_for_humans

# Crear blueprint para las rutas de tareas de emprendedor
tasks_bp = Blueprint('entrepreneur_tasks', __name__, url_prefix='/entrepreneur/tasks')

@tasks_bp.route('/', methods=['GET'])
@login_required
@entrepreneur_required
def index():
    """Vista principal de tareas del emprendedor."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Procesar filtros
    filter_form = TaskFilterForm(request.args)
    status = request.args.get('status', 'all')
    priority = request.args.get('priority', 'all')
    date_range = request.args.get('date_range', 'all')
    
    # Construir query base
    query = Task.query.filter_by(entrepreneur_id=entrepreneur.id)
    
    # Aplicar filtros
    if status != 'all':
        query = query.filter_by(status=status)
    
    if priority != 'all':
        query = query.filter_by(priority=priority)
    
    if date_range == 'today':
        today = datetime.now().date()
        query = query.filter(Task.due_date == today)
    elif date_range == 'week':
        today = datetime.now().date()
        end_of_week = today + timedelta(days=(6-today.weekday()))
        query = query.filter(and_(Task.due_date >= today, Task.due_date <= end_of_week))
    elif date_range == 'overdue':
        today = datetime.now().date()
        query = query.filter(and_(Task.due_date < today, Task.status != 'completed'))
    elif date_range == 'upcoming':
        today = datetime.now().date()
        query = query.filter(Task.due_date > today)
    
    # Ordenar tareas
    tasks = query.order_by(Task.priority.desc(), Task.due_date.asc()).all()
    
    # Estadísticas de tareas
    task_stats = {
        'total': Task.query.filter_by(entrepreneur_id=entrepreneur.id).count(),
        'completed': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='completed').count(),
        'in_progress': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='in_progress').count(),
        'pending': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='pending').count(),
        'overdue': Task.query.filter(
            Task.entrepreneur_id == entrepreneur.id,
            Task.due_date < datetime.now().date(),
            Task.status != 'completed'
        ).count()
    }
    
    # Calcular porcentaje de progreso
    if task_stats['total'] > 0:
        task_stats['progress'] = int((task_stats['completed'] / task_stats['total']) * 100)
    else:
        task_stats['progress'] = 0
    
    return render_template('entrepreneur/tasks.html',
                          tasks=tasks,
                          task_stats=task_stats,
                          filter_form=filter_form,
                          current_status=status,
                          current_priority=priority,
                          current_date_range=date_range,
                          format_date=format_date_for_humans,
                          task_form=TaskForm())

@tasks_bp.route('/create', methods=['POST'])
@login_required
@entrepreneur_required
def create_task():
    """Crear una nueva tarea."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    form = TaskForm()
    
    if form.validate_on_submit():
        # Crear nueva tarea
        task = Task(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            status='pending',
            due_date=form.due_date.data,
            entrepreneur_id=entrepreneur.id,
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        # Si es compartida con el aliado
        if form.share_with_ally.data and entrepreneur.ally_id:
            task.shared_with_ally = True
            task.ally_id = entrepreneur.ally_id
            
            # Notificar al aliado
            ally = Ally.query.get(entrepreneur.ally_id)
            notification_message = f"El emprendedor {entrepreneur.business_name} ha creado una nueva tarea: {form.title.data}"
            send_notification(ally.user_id, 'new_task', notification_message, 
                             link=url_for('ally.entrepreneurs.view_task', entrepreneur_id=entrepreneur.id, task_id=task.id))
        
        db.session.add(task)
        db.session.commit()
        
        flash('Tarea creada exitosamente', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {getattr(form, field).label.text}: {error}", 'error')
    
    return redirect(url_for('entrepreneur_tasks.index'))

@tasks_bp.route('/<int:task_id>', methods=['GET'])
@login_required
@entrepreneur_required
def view_task(task_id):
    """Ver detalles de una tarea específica."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    task = Task.query.filter_by(id=task_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    form = TaskForm(obj=task)
    
    return render_template('entrepreneur/task_detail.html',
                          task=task,
                          form=form,
                          format_date=format_date_for_humans)

@tasks_bp.route('/<int:task_id>/update', methods=['POST'])
@login_required
@entrepreneur_required
def update_task(task_id):
    """Actualizar una tarea existente."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    task = Task.query.filter_by(id=task_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    form = TaskForm()
    
    if form.validate_on_submit():
        old_status = task.status
        
        # Actualizar datos de la tarea
        task.title = form.title.data
        task.description = form.description.data
        task.priority = form.priority.data
        task.due_date = form.due_date.data
        task.updated_at = datetime.utcnow()
        task.updated_by = current_user.id
        
        # Verificar si cambia el estado
        if form.status.data != old_status:
            task.status = form.status.data
            
            # Registrar fecha de completado si la tarea se marca como completada
            if form.status.data == 'completed' and old_status != 'completed':
                task.completed_at = datetime.utcnow()
                task.completed_by = current_user.id
            
            # Si se reactiva una tarea completada
            if old_status == 'completed' and form.status.data != 'completed':
                task.completed_at = None
                task.completed_by = None
        
        # Actualizar compartición con aliado
        if entrepreneur.ally_id:
            if form.share_with_ally.data and not task.shared_with_ally:
                # Tarea ahora compartida con aliado
                task.shared_with_ally = True
                task.ally_id = entrepreneur.ally_id
                
                # Notificar al aliado
                ally = Ally.query.get(entrepreneur.ally_id)
                notification_message = f"El emprendedor {entrepreneur.business_name} ha compartido una tarea contigo: {task.title}"
                send_notification(ally.user_id, 'task_shared', notification_message, 
                                link=url_for('ally.entrepreneurs.view_task', entrepreneur_id=entrepreneur.id, task_id=task.id))
            
            elif not form.share_with_ally.data and task.shared_with_ally:
                # Tarea ya no compartida con aliado
                task.shared_with_ally = False
                task.ally_id = None
        
        db.session.commit()
        
        flash('Tarea actualizada exitosamente', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {getattr(form, field).label.text}: {error}", 'error')
    
    return redirect(url_for('entrepreneur_tasks.view_task', task_id=task_id))

@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
@entrepreneur_required
def delete_task(task_id):
    """Eliminar una tarea."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    task = Task.query.filter_by(id=task_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    db.session.delete(task)
    db.session.commit()
    
    flash('Tarea eliminada exitosamente', 'success')
    return redirect(url_for('entrepreneur_tasks.index'))

@tasks_bp.route('/<int:task_id>/toggle_status', methods=['POST'])
@login_required
@entrepreneur_required
def toggle_status(task_id):
    """Cambiar rápidamente el estado de una tarea (Ajax)."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    task = Task.query.filter_by(id=task_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    new_status = request.form.get('status')
    if new_status in ['pending', 'in_progress', 'completed']:
        old_status = task.status
        task.status = new_status
        task.updated_at = datetime.utcnow()
        task.updated_by = current_user.id
        
        # Si se completa la tarea
        if new_status == 'completed' and old_status != 'completed':
            task.completed_at = datetime.utcnow()
            task.completed_by = current_user.id
        # Si se reactiva una tarea completada
        elif old_status == 'completed' and new_status != 'completed':
            task.completed_at = None
            task.completed_by = None
        
        db.session.commit()
        
        # Notificar al aliado si la tarea está compartida
        if task.shared_with_ally and task.ally_id:
            ally = Ally.query.get(task.ally_id)
            notification_message = f"El emprendedor {entrepreneur.business_name} ha actualizado el estado de una tarea: {task.title} → {new_status}"
            send_notification(ally.user_id, 'task_updated', notification_message, 
                            link=url_for('ally.entrepreneurs.view_task', entrepreneur_id=entrepreneur.id, task_id=task.id))
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'new_status': task.status,
            'updated_at': format_date_for_humans(task.updated_at)
        })
    
    return jsonify({
        'success': False,
        'error': 'Estado no válido'
    }), 400

@tasks_bp.route('/calendar', methods=['GET'])
@login_required
@entrepreneur_required
def calendar_view():
    """Ver tareas en formato de calendario."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Este endpoint podría devolver datos JSON para un calendario JavaScript
    # o renderizar una vista de calendario
    
    return render_template('entrepreneur/tasks_calendar.html',
                          entrepreneur=entrepreneur)

@tasks_bp.route('/calendar/data', methods=['GET'])
@login_required
@entrepreneur_required
def calendar_data():
    """Obtener datos de tareas para el calendario (Ajax)."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    start_date = request.args.get('start', type=str)
    end_date = request.args.get('end', type=str)
    
    # Convertir fechas de string a objetos date
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        tasks = Task.query.filter(
            Task.entrepreneur_id == entrepreneur.id,
            Task.due_date >= start_date,
            Task.due_date <= end_date
        ).all()
    else:
        tasks = Task.query.filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Formatear tareas para el calendario
    events = []
    status_colors = {
        'pending': '#FFC107',      # Amarillo
        'in_progress': '#2196F3',  # Azul
        'completed': '#4CAF50'     # Verde
    }
    
    priority_titles = {
        'high': '⚠️ ',
        'medium': '⚡ ',
        'low': ''
    }
    
    for task in tasks:
        # Color basado en estado
        color = status_colors.get(task.status, '#757575')
        
        # Título con prefijo basado en prioridad
        title = f"{priority_titles.get(task.priority, '')}{task.title}"
        
        events.append({
            'id': task.id,
            'title': title,
            'start': task.due_date.strftime('%Y-%m-%d'),
            'color': color,
            'url': url_for('entrepreneur_tasks.view_task', task_id=task.id),
            'description': task.description,
            'status': task.status,
            'priority': task.priority
        })
    
    return jsonify(events)

@tasks_bp.route('/dashboard_summary', methods=['GET'])
@login_required
@entrepreneur_required
def dashboard_summary():
    """Obtener resumen de tareas para el dashboard (Ajax)."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Tareas para hoy
    today = datetime.now().date()
    today_tasks = Task.query.filter(
        Task.entrepreneur_id == entrepreneur.id,
        Task.due_date == today
    ).order_by(Task.priority.desc()).limit(5).all()
    
    # Tareas atrasadas
    overdue_tasks = Task.query.filter(
        Task.entrepreneur_id == entrepreneur.id,
        Task.due_date < today,
        Task.status != 'completed'
    ).order_by(Task.due_date.asc()).limit(5).all()
    
    # Estadísticas 
    stats = {
        'total': Task.query.filter_by(entrepreneur_id=entrepreneur.id).count(),
        'completed': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='completed').count(),
        'in_progress': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='in_progress').count(),
        'pending': Task.query.filter_by(entrepreneur_id=entrepreneur.id, status='pending').count(),
        'overdue': len(overdue_tasks),
        'today': len(today_tasks)
    }
    
    # Calcular progreso
    if stats['total'] > 0:
        stats['progress'] = int((stats['completed'] / stats['total']) * 100)
    else:
        stats['progress'] = 0
    
    # Formatear tareas para el dashboard
    format_tasks = lambda tasks: [{
        'id': t.id,
        'title': t.title,
        'priority': t.priority,
        'status': t.status,
        'due_date': format_date_for_humans(t.due_date),
        'url': url_for('entrepreneur_tasks.view_task', task_id=t.id)
    } for t in tasks]
    
    return jsonify({
        'stats': stats,
        'today_tasks': format_tasks(today_tasks),
        'overdue_tasks': format_tasks(overdue_tasks)
    })