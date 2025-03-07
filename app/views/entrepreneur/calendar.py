from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.meeting import Meeting
from app.models.user import User
from app.forms.entrepreneur import MeetingForm
from app.extensions import db
from app.utils.decorators import entrepreneur_required
from app.utils.notifications import send_meeting_notification
from app.services.google_calendar import create_google_event, update_google_event, delete_google_event
from app.services.google_meet import create_meet_link

# Crear el blueprint para las rutas de calendario de emprendedores
entrepreneur_calendar = Blueprint('entrepreneur_calendar', __name__)

@entrepreneur_calendar.route('/calendar')
@login_required
@entrepreneur_required
def calendar():
    """Vista principal del calendario para el emprendedor."""
    # Obtener el emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los aliados asignados al emprendedor para el formulario
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Obtener las reuniones del emprendedor (tanto las que ha creado como las que ha sido invitado)
    meetings = Meeting.query.filter(
        (Meeting.creator_id == current_user.id) | 
        (Meeting.attendees.any(id=current_user.id))
    ).all()
    
    # Crear formulario para nueva reunión
    form = MeetingForm()
    
    # Poblar el campo de aliados en el formulario
    form.attendee_id.choices = [(ally.user_id, ally.user.full_name) for ally in allies]
    
    return render_template(
        'entrepreneur/calendar.html',
        meetings=meetings,
        form=form,
        allies=allies
    )

@entrepreneur_calendar.route('/calendar/events')
@login_required
@entrepreneur_required
def get_events():
    """Retorna eventos para el calendario en formato JSON."""
    # Obtener parámetros de fecha del request (para filtrar por rango si es necesario)
    start = request.args.get('start', None)
    end = request.args.get('end', None)
    
    if start and end:
        start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
    else:
        # Si no hay fechas, obtener eventos para el mes actual
        today = datetime.today()
        start_date = datetime(today.year, today.month, 1)
        end_date = start_date + timedelta(days=31)
    
    # Consultar reuniones dentro del rango de fechas
    meetings = Meeting.query.filter(
        ((Meeting.creator_id == current_user.id) | (Meeting.attendees.any(id=current_user.id))),
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date
    ).all()
    
    # Formatear eventos para FullCalendar
    events = []
    for meeting in meetings:
        creator = User.query.get(meeting.creator_id)
        
        # Determinar el color del evento según el creador
        color = '#3788d8'  # Azul por defecto
        if meeting.creator_id != current_user.id:
            color = '#28a745'  # Verde para reuniones creadas por aliados
        
        events.append({
            'id': meeting.id,
            'title': meeting.title,
            'start': meeting.start_time.isoformat(),
            'end': meeting.end_time.isoformat(),
            'description': meeting.description,
            'location': meeting.location,
            'creator': creator.full_name,
            'creator_id': creator.id,
            'is_creator': meeting.creator_id == current_user.id,
            'url': url_for('entrepreneur_calendar.view_meeting', meeting_id=meeting.id),
            'color': color,
            'editable': meeting.creator_id == current_user.id,
            'allDay': False
        })
    
    return jsonify(events)

@entrepreneur_calendar.route('/calendar/meetings/create', methods=['POST'])
@login_required
@entrepreneur_required
def create_meeting():
    """Crear una nueva reunión."""
    form = MeetingForm()
    
    # Obtener aliados disponibles
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Actualizar las opciones del formulario
    form.attendee_id.choices = [(ally.user_id, ally.user.full_name) for ally in allies]
    
    if form.validate_on_submit():
        # Crear objeto de reunión
        meeting = Meeting(
            title=form.title.data,
            description=form.description.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            location=form.location.data,
            creator_id=current_user.id
        )
        
        # Obtener el aliado seleccionado
        attendee = User.query.get(form.attendee_id.data)
        if attendee:
            meeting.attendees.append(attendee)
        
        # Verificar si se debe crear un enlace de Google Meet
        if form.create_meet_link.data:
            try:
                # Crear enlace de Google Meet
                meet_link = create_meet_link(
                    summary=meeting.title,
                    description=meeting.description,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    attendees=[attendee.email, current_user.email]
                )
                
                if meet_link:
                    meeting.location = meet_link
            except Exception as e:
                current_app.logger.error(f"Error al crear enlace de Meet: {str(e)}")
                flash('No se pudo crear el enlace de Google Meet, pero la reunión ha sido agendada.', 'warning')
        
        # Guardar la reunión en la base de datos
        db.session.add(meeting)
        db.session.commit()
        
        # Crear evento en Google Calendar si la integración está habilitada
        try:
            if current_user.google_calendar_enabled:
                event_id = create_google_event(
                    summary=meeting.title,
                    description=meeting.description,
                    location=meeting.location,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    attendees=[attendee.email]
                )
                if event_id:
                    meeting.google_event_id = event_id
                    db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error al crear evento en Google Calendar: {str(e)}")
            flash('La reunión fue creada, pero no se pudo sincronizar con Google Calendar.', 'warning')
        
        # Enviar notificación al aliado
        send_meeting_notification(meeting, attendee)
        
        flash('Reunión creada exitosamente.', 'success')
        return redirect(url_for('entrepreneur_calendar.calendar'))
    
    # Si hay errores en el formulario
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('entrepreneur_calendar.calendar'))

@entrepreneur_calendar.route('/calendar/meetings/<int:meeting_id>')
@login_required
@entrepreneur_required
def view_meeting(meeting_id):
    """Ver detalles de una reunión específica."""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que el usuario actual tiene acceso a esta reunión
    if meeting.creator_id != current_user.id and current_user not in meeting.attendees:
        flash('No tienes permiso para ver esta reunión.', 'error')
        return redirect(url_for('entrepreneur_calendar.calendar'))
    
    # Obtener información del creador y asistentes
    creator = User.query.get(meeting.creator_id)
    
    return render_template(
        'entrepreneur/meeting_detail.html',
        meeting=meeting,
        creator=creator
    )

@entrepreneur_calendar.route('/calendar/meetings/<int:meeting_id>/edit', methods=['GET', 'POST'])
@login_required
@entrepreneur_required
def edit_meeting(meeting_id):
    """Editar una reunión existente."""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que el usuario actual es el creador de la reunión
    if meeting.creator_id != current_user.id:
        flash('Solo el creador puede editar la reunión.', 'error')
        return redirect(url_for('entrepreneur_calendar.calendar'))
    
    # Obtener aliados disponibles
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    allies = Ally.query.join(Ally.relationships).filter_by(entrepreneur_id=entrepreneur.id).all()
    
    # Crear formulario y completarlo con los datos actuales
    form = MeetingForm(obj=meeting)
    form.attendee_id.choices = [(ally.user_id, ally.user.full_name) for ally in allies]
    
    # Si hay un asistente, preseleccionarlo
    if meeting.attendees and len(meeting.attendees) > 0:
        form.attendee_id.data = meeting.attendees[0].id
    
    if request.method == 'GET':
        return render_template(
            'entrepreneur/edit_meeting.html',
            form=form,
            meeting=meeting
        )
    
    if form.validate_on_submit():
        # Actualizar datos de la reunión
        meeting.title = form.title.data
        meeting.description = form.description.data
        meeting.start_time = form.start_time.data
        meeting.end_time = form.end_time.data
        meeting.location = form.location.data
        
        # Actualizar asistente
        attendee = User.query.get(form.attendee_id.data)
        if attendee:
            meeting.attendees = [attendee]  # Reemplazar asistentes
        
        # Actualizar enlace de Google Meet si es necesario
        if form.create_meet_link.data and 'meet.google.com' not in meeting.location:
            try:
                meet_link = create_meet_link(
                    summary=meeting.title,
                    description=meeting.description,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    attendees=[attendee.email, current_user.email]
                )
                
                if meet_link:
                    meeting.location = meet_link
            except Exception as e:
                current_app.logger.error(f"Error al crear enlace de Meet: {str(e)}")
                flash('No se pudo crear el enlace de Google Meet.', 'warning')
        
        # Guardar cambios
        db.session.commit()
        
        # Actualizar evento en Google Calendar
        if meeting.google_event_id and current_user.google_calendar_enabled:
            try:
                update_google_event(
                    event_id=meeting.google_event_id,
                    summary=meeting.title,
                    description=meeting.description,
                    location=meeting.location,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    attendees=[attendee.email]
                )
            except Exception as e:
                current_app.logger.error(f"Error al actualizar evento en Google Calendar: {str(e)}")
                flash('La reunión fue actualizada, pero no se pudo sincronizar con Google Calendar.', 'warning')
        
        # Notificar al asistente sobre los cambios
        send_meeting_notification(meeting, attendee, is_update=True)
        
        flash('Reunión actualizada exitosamente.', 'success')
        return redirect(url_for('entrepreneur_calendar.calendar'))
    
    # Si hay errores en el formulario
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'error')
    
    return render_template(
        'entrepreneur/edit_meeting.html',
        form=form,
        meeting=meeting
    )

@entrepreneur_calendar.route('/calendar/meetings/<int:meeting_id>/delete', methods=['POST'])
@login_required
@entrepreneur_required
def delete_meeting(meeting_id):
    """Eliminar una reunión."""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que el usuario actual es el creador de la reunión
    if meeting.creator_id != current_user.id:
        flash('Solo el creador puede eliminar la reunión.', 'error')
        return redirect(url_for('entrepreneur_calendar.calendar'))
    
    # Eliminar el evento de Google Calendar si existe
    if meeting.google_event_id and current_user.google_calendar_enabled:
        try:
            delete_google_event(meeting.google_event_id)
        except Exception as e:
            current_app.logger.error(f"Error al eliminar evento de Google Calendar: {str(e)}")
    
    # Notificar a los asistentes sobre la cancelación
    for attendee in meeting.attendees:
        send_meeting_notification(meeting, attendee, is_cancelled=True)
    
    # Eliminar la reunión
    db.session.delete(meeting)
    db.session.commit()
    
    flash('Reunión eliminada exitosamente.', 'success')
    return redirect(url_for('entrepreneur_calendar.calendar'))

@entrepreneur_calendar.route('/calendar/meetings/update-time', methods=['POST'])
@login_required
@entrepreneur_required
def update_meeting_time():
    """Actualizar horario de una reunión (arrastrar y soltar en el calendario)."""
    meeting_id = request.json.get('id')
    start_time = request.json.get('start')
    end_time = request.json.get('end')
    
    if not meeting_id or not start_time or not end_time:
        return jsonify({'success': False, 'message': 'Datos incompletos'})
    
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que el usuario actual es el creador de la reunión
    if meeting.creator_id != current_user.id:
        return jsonify({'success': False, 'message': 'No tienes permiso para modificar esta reunión'})
    
    # Convertir strings a datetime
    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    
    # Actualizar horarios
    meeting.start_time = start_time
    meeting.end_time = end_time
    
    # Guardar cambios
    db.session.commit()
    
    # Actualizar evento en Google Calendar
    if meeting.google_event_id and current_user.google_calendar_enabled:
        try:
            update_google_event(
                event_id=meeting.google_event_id,
                start_time=meeting.start_time,
                end_time=meeting.end_time
            )
        except Exception as e:
            current_app.logger.error(f"Error al actualizar evento en Google Calendar: {str(e)}")
            return jsonify({
                'success': True, 
                'warning': 'La reunión fue actualizada, pero no se pudo sincronizar con Google Calendar.'
            })
    
    # Notificar a los asistentes sobre el cambio de horario
    for attendee in meeting.attendees:
        send_meeting_notification(meeting, attendee, is_update=True)
    
    return jsonify({'success': True})