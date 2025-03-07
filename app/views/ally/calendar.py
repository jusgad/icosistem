from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.extensions import db
from app.models.meeting import Meeting
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship
from app.forms.ally import MeetingForm
from app.services.google_calendar import GoogleCalendarService
from app.services.google_meet import GoogleMeetService
from app.utils.decorators import ally_required
from app.utils.notifications import send_notification

# Crear el blueprint
ally_calendar = Blueprint('ally_calendar', __name__, url_prefix='/ally/calendar')

@ally_calendar.route('/', methods=['GET'])
@login_required
@ally_required
def index():
    """Vista principal del calendario del aliado"""
    # Obtener las reuniones del aliado
    meetings = Meeting.query.filter_by(ally_id=current_user.ally.id).all()
    
    # Obtener emprendedores asignados para el formulario de nueva reunión
    assigned_relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneurs = [relationship.entrepreneur for relationship in assigned_relationships]
    
    form = MeetingForm()
    form.entrepreneur_id.choices = [(e.id, f"{e.user.first_name} {e.user.last_name}") for e in entrepreneurs]
    
    # Renderizar la plantilla
    return render_template('ally/calendar.html', 
                          meetings=meetings, 
                          form=form, 
                          title='Mi Calendario')

@ally_calendar.route('/meetings', methods=['GET'])
@login_required
@ally_required
def get_meetings():
    """Obtener todas las reuniones en formato JSON para el calendario"""
    start_date = request.args.get('start', datetime.now().strftime('%Y-%m-%d'))
    end_date = request.args.get('end', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
    
    meetings = Meeting.query.filter_by(ally_id=current_user.ally.id).filter(
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date
    ).all()
    
    events = []
    for meeting in meetings:
        entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
        events.append({
            'id': meeting.id,
            'title': meeting.title,
            'start': meeting.start_time.isoformat(),
            'end': meeting.end_time.isoformat(),
            'description': meeting.description,
            'entrepreneur': f"{entrepreneur.user.first_name} {entrepreneur.user.last_name}",
            'location': meeting.location,
            'url': meeting.meet_url if meeting.meet_url else None,
            'color': '#3788d8' if meeting.status == 'confirmed' else 
                    ('#f8a51b' if meeting.status == 'pending' else '#dc3545')
        })
    
    return jsonify(events)

@ally_calendar.route('/create', methods=['POST'])
@login_required
@ally_required
def create_meeting():
    """Crear una nueva reunión"""
    form = MeetingForm()
    
    # Obtener emprendedores asignados para validación
    assigned_relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [relationship.entrepreneur_id for relationship in assigned_relationships]
    form.entrepreneur_id.choices = [(id, "") for id in entrepreneur_ids]
    
    if form.validate_on_submit():
        entrepreneur_id = form.entrepreneur_id.data
        
        # Verificar que el emprendedor está asignado al aliado
        if entrepreneur_id not in entrepreneur_ids:
            flash('No tienes permiso para agendar con este emprendedor', 'danger')
            return redirect(url_for('ally_calendar.index'))
        
        # Crear la reunión
        meeting = Meeting(
            title=form.title.data,
            description=form.description.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            location=form.location.data,
            status='pending',
            ally_id=current_user.ally.id,
            entrepreneur_id=entrepreneur_id
        )
        
        # Si está configurado para usar Google Meet, crear la reunión virtual
        if form.create_meet.data:
            try:
                google_meet = GoogleMeetService()
                meet_data = google_meet.create_meeting(
                    summary=form.title.data,
                    description=form.description.data,
                    start_time=form.start_time.data,
                    end_time=form.end_time.data,
                    timezone=current_app.config['TIMEZONE']
                )
                meeting.meet_url = meet_data.get('hangoutLink')
            except Exception as e:
                current_app.logger.error(f"Error creando reunión en Google Meet: {str(e)}")
                flash('No se pudo crear la reunión en Google Meet', 'warning')
        
        # Si está configurado para usar Google Calendar, añadir al calendario
        if form.add_to_calendar.data:
            try:
                # Obtener información del emprendedor
                entrepreneur = Entrepreneur.query.get(entrepreneur_id)
                
                google_calendar = GoogleCalendarService()
                calendar_data = google_calendar.create_event(
                    summary=form.title.data,
                    description=form.description.data,
                    location=form.location.data,
                    start_time=form.start_time.data,
                    end_time=form.end_time.data,
                    timezone=current_app.config['TIMEZONE'],
                    attendees=[
                        {'email': current_user.email},
                        {'email': entrepreneur.user.email}
                    ],
                    meet_url=meeting.meet_url
                )
                meeting.calendar_event_id = calendar_data.get('id')
            except Exception as e:
                current_app.logger.error(f"Error creando evento en Google Calendar: {str(e)}")
                flash('No se pudo agregar la reunión al calendario', 'warning')
        
        # Guardar en la base de datos
        db.session.add(meeting)
        db.session.commit()
        
        # Enviar notificación al emprendedor
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        send_notification(
            user_id=entrepreneur.user_id,
            message=f"Nueva reunión programada: {form.title.data}",
            link=url_for('entrepreneur.calendar.index'),
            type='meeting'
        )
        
        flash('Reunión creada exitosamente', 'success')
        return redirect(url_for('ally_calendar.index'))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('ally_calendar.index'))

@ally_calendar.route('/<int:meeting_id>/update', methods=['POST'])
@login_required
@ally_required
def update_meeting(meeting_id):
    """Actualizar una reunión existente"""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que la reunión pertenece al aliado actual
    if meeting.ally_id != current_user.ally.id:
        flash('No tienes permiso para editar esta reunión', 'danger')
        return redirect(url_for('ally_calendar.index'))
    
    form = MeetingForm()
    
    # Obtener emprendedores asignados para validación
    assigned_relationships = Relationship.query.filter_by(ally_id=current_user.ally.id).all()
    entrepreneur_ids = [relationship.entrepreneur_id for relationship in assigned_relationships]
    form.entrepreneur_id.choices = [(id, "") for id in entrepreneur_ids]
    
    if form.validate_on_submit():
        entrepreneur_id = form.entrepreneur_id.data
        
        # Verificar que el emprendedor está asignado al aliado
        if entrepreneur_id not in entrepreneur_ids:
            flash('No tienes permiso para agendar con este emprendedor', 'danger')
            return redirect(url_for('ally_calendar.index'))
        
        # Actualizar los datos de la reunión
        meeting.title = form.title.data
        meeting.description = form.description.data
        meeting.start_time = form.start_time.data
        meeting.end_time = form.end_time.data
        meeting.location = form.location.data
        
        # Si la reunión cambia de emprendedor, actualizar y notificar
        if meeting.entrepreneur_id != entrepreneur_id:
            old_entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
            meeting.entrepreneur_id = entrepreneur_id
            new_entrepreneur = Entrepreneur.query.get(entrepreneur_id)
            
            # Notificar al emprendedor anterior
            send_notification(
                user_id=old_entrepreneur.user_id,
                message=f"Reunión cancelada: {meeting.title}",
                type='meeting_cancelled'
            )
            
            # Notificar al nuevo emprendedor
            send_notification(
                user_id=new_entrepreneur.user_id,
                message=f"Nueva reunión programada: {meeting.title}",
                link=url_for('entrepreneur.calendar.index'),
                type='meeting'
            )
        
        # Actualizar en Google Calendar si existe
        if meeting.calendar_event_id and form.add_to_calendar.data:
            try:
                entrepreneur = Entrepreneur.query.get(entrepreneur_id)
                
                google_calendar = GoogleCalendarService()
                google_calendar.update_event(
                    event_id=meeting.calendar_event_id,
                    summary=form.title.data,
                    description=form.description.data,
                    location=form.location.data,
                    start_time=form.start_time.data,
                    end_time=form.end_time.data,
                    timezone=current_app.config['TIMEZONE'],
                    attendees=[
                        {'email': current_user.email},
                        {'email': entrepreneur.user.email}
                    ]
                )
            except Exception as e:
                current_app.logger.error(f"Error actualizando evento en Google Calendar: {str(e)}")
                flash('No se pudo actualizar la reunión en el calendario', 'warning')
        
        # Guardar cambios
        db.session.commit()
        
        flash('Reunión actualizada exitosamente', 'success')
        return redirect(url_for('ally_calendar.index'))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('ally_calendar.index'))

@ally_calendar.route('/<int:meeting_id>/delete', methods=['POST'])
@login_required
@ally_required
def delete_meeting(meeting_id):
    """Eliminar una reunión"""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que la reunión pertenece al aliado actual
    if meeting.ally_id != current_user.ally.id:
        flash('No tienes permiso para eliminar esta reunión', 'danger')
        return redirect(url_for('ally_calendar.index'))
    
    # Si existe en Google Calendar, eliminar
    if meeting.calendar_event_id:
        try:
            google_calendar = GoogleCalendarService()
            google_calendar.delete_event(meeting.calendar_event_id)
        except Exception as e:
            current_app.logger.error(f"Error eliminando evento de Google Calendar: {str(e)}")
            flash('No se pudo eliminar la reunión del calendario', 'warning')
    
    # Notificar al emprendedor
    entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
    send_notification(
        user_id=entrepreneur.user_id,
        message=f"Reunión cancelada: {meeting.title}",
        type='meeting_cancelled'
    )
    
    # Eliminar de la base de datos
    db.session.delete(meeting)
    db.session.commit()
    
    flash('Reunión eliminada exitosamente', 'success')
    return redirect(url_for('ally_calendar.index'))

@ally_calendar.route('/<int:meeting_id>/details', methods=['GET'])
@login_required
@ally_required
def meeting_details(meeting_id):
    """Obtener detalles de una reunión en formato JSON"""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que la reunión pertenece al aliado actual
    if meeting.ally_id != current_user.ally.id:
        return jsonify({'error': 'No tienes permiso para ver esta reunión'}), 403
    
    entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
    
    meeting_data = {
        'id': meeting.id,
        'title': meeting.title,
        'description': meeting.description,
        'start_time': meeting.start_time.strftime('%Y-%m-%d %H:%M'),
        'end_time': meeting.end_time.strftime('%Y-%m-%d %H:%M'),
        'location': meeting.location,
        'status': meeting.status,
        'meet_url': meeting.meet_url,
        'entrepreneur': {
            'id': entrepreneur.id,
            'name': f"{entrepreneur.user.first_name} {entrepreneur.user.last_name}",
            'email': entrepreneur.user.email,
            'phone': entrepreneur.contact_phone
        }
    }
    
    return jsonify(meeting_data)

@ally_calendar.route('/<int:meeting_id>/confirm', methods=['POST'])
@login_required
@ally_required
def confirm_meeting(meeting_id):
    """Confirmar una reunión pendiente"""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Verificar que la reunión pertenece al aliado actual
    if meeting.ally_id != current_user.ally.id:
        flash('No tienes permiso para confirmar esta reunión', 'danger')
        return redirect(url_for('ally_calendar.index'))
    
    meeting.status = 'confirmed'
    db.session.commit()
    
    # Notificar al emprendedor
    entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
    send_notification(
        user_id=entrepreneur.user_id,
        message=f"Reunión confirmada: {meeting.title}",
        link=url_for('entrepreneur.calendar.index'),
        type='meeting_confirmed'
    )
    
    flash('Reunión confirmada exitosamente', 'success')
    return redirect(url_for('ally_calendar.index'))