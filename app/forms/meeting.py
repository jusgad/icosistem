# -*- coding: utf-8 -*-
"""
Meeting Forms Module
==================

Formularios para la gestión completa de reuniones en el ecosistema de emprendimiento.
Incluye creación, edición, agendamiento, gestión de asistentes y seguimiento.

Author: Ecosistema Emprendimiento Team
Date: 2025
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, FloatField,
    DateField, DateTimeField, TimeField, BooleanField, FieldList, FormField,
    HiddenField, RadioField, SelectMultipleField
)
from wtforms.validators import (
    DataRequired, Length, Email, NumberRange, Optional,
    ValidationError, URL, Regexp
)
from wtforms.widgets import TextArea, Select, CheckboxInput
from datetime import datetime, timedelta, time

from .base import BaseForm
from .validators import (
    validate_future_datetime, validate_past_or_today_datetime,
    validate_business_hours, validate_meeting_duration,
    validate_phone_number, validate_timezone,
    ConditionalRequired, UniqueFieldValidator
)
from ..models.meeting import Meeting, MeetingStatus, MeetingType, MeetingPriority
from ..models.user import User
from ..models.project import Project
from ..models.organization import Organization
from ..core.constants import (
    MEETING_TYPES, MEETING_STATUSES, MEETING_PRIORITIES,
    MEETING_DURATIONS, TIMEZONES, MEETING_PLATFORMS,
    MAX_MEETING_TITLE_LENGTH, MAX_MEETING_DESCRIPTION_LENGTH,
    MIN_MEETING_DESCRIPTION_LENGTH, DEFAULT_MEETING_DURATION
)


class CreateMeetingForm(BaseForm):
    """Formulario para crear una nueva reunión."""
    
    # Información básica
    title = StringField(
        'Título de la Reunión',
        validators=[
            DataRequired(message='El título es obligatorio'),
            Length(
                min=5,
                max=MAX_MEETING_TITLE_LENGTH,
                message=f'El título debe tener entre 5 y {MAX_MEETING_TITLE_LENGTH} caracteres'
            )
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Ej: Revisión de avances del proyecto',
            'autocomplete': 'off'
        }
    )
    
    description = TextAreaField(
        'Descripción / Agenda',
        validators=[
            DataRequired(message='La descripción es obligatoria'),
            Length(
                min=MIN_MEETING_DESCRIPTION_LENGTH,
                max=MAX_MEETING_DESCRIPTION_LENGTH,
                message=f'La descripción debe tener entre {MIN_MEETING_DESCRIPTION_LENGTH} y {MAX_MEETING_DESCRIPTION_LENGTH} caracteres'
            )
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe el propósito de la reunión y la agenda a tratar...',
            'rows': '5'
        }
    )
    
    meeting_type = SelectField(
        'Tipo de Reunión',
        choices=MEETING_TYPES,
        validators=[DataRequired(message='Selecciona el tipo de reunión')],
        render_kw={'class': 'form-select'}
    )
    
    priority = SelectField(
        'Prioridad',
        choices=MEETING_PRIORITIES,
        default='medium',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    # Fecha y hora
    meeting_date = DateField(
        'Fecha de la Reunión',
        validators=[
            DataRequired(message='La fecha es obligatoria'),
            validate_future_datetime
        ],
        render_kw={'class': 'form-control'}
    )
    
    start_time = TimeField(
        'Hora de Inicio',
        validators=[
            DataRequired(message='La hora de inicio es obligatoria'),
            validate_business_hours
        ],
        render_kw={'class': 'form-control'}
    )
    
    duration = SelectField(
        'Duración',
        choices=MEETING_DURATIONS,
        default=str(DEFAULT_MEETING_DURATION),
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    timezone = SelectField(
        'Zona Horaria',
        choices=TIMEZONES,
        default='America/Bogota',
        validators=[DataRequired(), validate_timezone],
        render_kw={'class': 'form-select'}
    )
    
    # Modalidad y plataforma
    is_virtual = BooleanField(
        'Reunión Virtual',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    platform = SelectField(
        'Plataforma',
        choices=MEETING_PLATFORMS,
        validators=[ConditionalRequired('is_virtual')],
        render_kw={'class': 'form-select'}
    )
    
    meeting_url = StringField(
        'URL de la Reunión',
        validators=[
            ConditionalRequired('is_virtual'),
            URL(message='Ingresa una URL válida')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'https://meet.google.com/xxx-xxxx-xxx'
        }
    )
    
    meeting_id = StringField(
        'ID de la Reunión',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'ID o código de acceso'
        }
    )
    
    meeting_password = StringField(
        'Contraseña',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Contraseña de acceso (opcional)'
        }
    )
    
    # Ubicación física (si aplica)
    location = StringField(
        'Ubicación',
        validators=[ConditionalRequired('is_virtual', negate=True)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Dirección física de la reunión'
        }
    )
    
    room = StringField(
        'Sala/Oficina',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Nombre de la sala o número de oficina'
        }
    )
    
    # Relaciones
    project_id = SelectField(
        'Proyecto Relacionado',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    organization_id = SelectField(
        'Organización',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    # Configuración de asistentes
    max_attendees = IntegerField(
        'Máximo de Asistentes',
        validators=[
            Optional(),
            NumberRange(min=2, max=100, message='Entre 2 y 100 asistentes')
        ],
        render_kw={
            'class': 'form-control',
            'min': '2',
            'max': '100'
        }
    )
    
    requires_confirmation = BooleanField(
        'Requiere Confirmación',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    allow_guests = BooleanField(
        'Permitir Invitados',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    # Notificaciones y recordatorios
    send_invitations = BooleanField(
        'Enviar Invitaciones',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    reminder_email = BooleanField(
        'Recordatorio por Email',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    reminder_minutes = SelectField(
        'Recordatorio (minutos antes)',
        choices=[
            ('5', '5 minutos'),
            ('15', '15 minutos'),
            ('30', '30 minutos'),
            ('60', '1 hora'),
            ('120', '2 horas'),
            ('1440', '1 día')
        ],
        default='15',
        validators=[ConditionalRequired('reminder_email')],
        render_kw={'class': 'form-select'}
    )
    
    # Configuración adicional
    is_recurring = BooleanField(
        'Reunión Recurrente',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    recurrence_pattern = SelectField(
        'Patrón de Recurrencia',
        choices=[
            ('daily', 'Diario'),
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral')
        ],
        validators=[ConditionalRequired('is_recurring')],
        render_kw={'class': 'form-select'}
    )
    
    recurrence_end_date = DateField(
        'Fecha Fin de Recurrencia',
        validators=[ConditionalRequired('is_recurring')],
        render_kw={'class': 'form-control'}
    )
    
    # Archivos adjuntos
    agenda_file = FileField(
        'Archivo de Agenda',
        validators=[
            FileAllowed(['pdf', 'doc', 'docx', 'txt'], 'Solo documentos permitidos')
        ],
        render_kw={'class': 'form-control'}
    )
    
    # Configuración de grabación
    record_meeting = BooleanField(
        'Grabar Reunión',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    auto_transcript = BooleanField(
        'Transcripción Automática',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    # Notas adicionales
    internal_notes = TextAreaField(
        'Notas Internas',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Notas internas (no visibles para los asistentes)',
            'rows': '3'
        }
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar proyectos activos
        self.project_id.choices = [(0, 'Sin proyecto asociado')] + [
            (project.id, project.name) 
            for project in Project.query.filter_by(is_active=True).all()
        ]
        
        # Cargar organizaciones activas
        self.organization_id.choices = [(0, 'Sin organización')] + [
            (org.id, org.name) 
            for org in Organization.query.filter_by(is_active=True).all()
        ]
    
    def validate_meeting_date(self, field):
        """Validar que la fecha no sea en el pasado."""
        if field.data and field.data < datetime.now().date():
            raise ValidationError('La fecha de la reunión no puede ser en el pasado')
    
    def validate_start_time(self, field):
        """Validar hora de inicio en conjunto con la fecha."""
        if field.data and self.meeting_date.data:
            meeting_datetime = datetime.combine(self.meeting_date.data, field.data)
            if meeting_datetime <= datetime.now():
                raise ValidationError('La hora de la reunión debe ser en el futuro')
    
    def validate_recurrence_end_date(self, field):
        """Validar fecha fin de recurrencia."""
        if field.data and self.meeting_date.data:
            if field.data <= self.meeting_date.data:
                raise ValidationError('La fecha fin debe ser posterior a la fecha de la reunión')


class EditMeetingForm(CreateMeetingForm):
    """Formulario para editar una reunión existente."""
    
    id = HiddenField()
    
    status = SelectField(
        'Estado',
        choices=MEETING_STATUSES,
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    cancellation_reason = TextAreaField(
        'Motivo de Cancelación',
        validators=[ConditionalRequired('status', 'cancelled')],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Explica el motivo de la cancelación',
            'rows': '3'
        }
    )
    
    postponement_reason = TextAreaField(
        'Motivo de Postergación',
        validators=[ConditionalRequired('status', 'postponed')],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Explica el motivo de la postergación',
            'rows': '3'
        }
    )
    
    def __init__(self, meeting=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting


class MeetingAttendeesForm(BaseForm):
    """Formulario para gestionar asistentes de la reunión."""
    
    meeting_id = HiddenField()
    
    attendees = SelectMultipleField(
        'Asistentes',
        coerce=int,
        validators=[DataRequired(message='Selecciona al menos un asistente')],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '10'
        }
    )
    
    guest_emails = TextAreaField(
        'Invitados Externos (emails)',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Un email por línea para invitados externos',
            'rows': '4'
        }
    )
    
    required_attendees = SelectMultipleField(
        'Asistentes Obligatorios',
        coerce=int,
        validators=[Optional()],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '5'
        }
    )
    
    optional_attendees = SelectMultipleField(
        'Asistentes Opcionales',
        coerce=int,
        validators=[Optional()],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '5'
        }
    )
    
    send_calendar_invite = BooleanField(
        'Enviar Invitación de Calendario',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    custom_message = TextAreaField(
        'Mensaje Personalizado',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Mensaje adicional para los asistentes',
            'rows': '3'
        }
    )
    
    def __init__(self, meeting=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar usuarios activos
        users = User.query.filter_by(is_active=True).all()
        user_choices = [
            (user.id, f"{user.first_name} {user.last_name} ({user.email})")
            for user in users
        ]
        
        self.attendees.choices = user_choices
        self.required_attendees.choices = user_choices
        self.optional_attendees.choices = user_choices
    
    def validate_guest_emails(self, field):
        """Validar formato de emails de invitados."""
        if field.data:
            emails = [email.strip() for email in field.data.split('\n') if email.strip()]
            import re
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            
            for email in emails:
                if not email_pattern.match(email):
                    raise ValidationError(f'Email inválido: {email}')


class MeetingNotesForm(BaseForm):
    """Formulario para registrar actas y notas de la reunión."""
    
    meeting_id = HiddenField()
    
    summary = TextAreaField(
        'Resumen de la Reunión',
        validators=[
            DataRequired(message='El resumen es obligatorio'),
            Length(min=50, max=2000, message='El resumen debe tener entre 50 y 2000 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Resumen general de lo tratado en la reunión',
            'rows': '4'
        }
    )
    
    key_points = TextAreaField(
        'Puntos Clave Discutidos',
        validators=[
            DataRequired(message='Los puntos clave son obligatorios'),
            Length(min=30, max=3000, message='Los puntos clave deben tener entre 30 y 3000 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Lista los puntos más importantes discutidos',
            'rows': '6'
        }
    )
    
    decisions_made = TextAreaField(
        'Decisiones Tomadas',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Decisiones importantes tomadas durante la reunión',
            'rows': '4'
        }
    )
    
    action_items = TextAreaField(
        'Elementos de Acción',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Tareas y compromisos asignados (incluir responsables y fechas)',
            'rows': '5'
        }
    )
    
    next_steps = TextAreaField(
        'Próximos Pasos',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Pasos a seguir después de esta reunión',
            'rows': '4'
        }
    )
    
    attendees_present = SelectMultipleField(
        'Asistentes Presentes',
        coerce=int,
        validators=[DataRequired(message='Marca los asistentes que estuvieron presentes')],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '8'
        }
    )
    
    attendees_absent = SelectMultipleField(
        'Asistentes Ausentes',
        coerce=int,
        validators=[Optional()],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '5'
        }
    )
    
    meeting_rating = SelectField(
        'Calificación de la Reunión',
        choices=[
            ('1', '1 - Muy Mala'),
            ('2', '2 - Mala'),
            ('3', '3 - Regular'),
            ('4', '4 - Buena'),
            ('5', '5 - Excelente')
        ],
        validators=[DataRequired(message='Califica la reunión')],
        render_kw={'class': 'form-select'}
    )
    
    effectiveness_rating = SelectField(
        'Efectividad de la Reunión',
        choices=[
            ('1', '1 - Nada Efectiva'),
            ('2', '2 - Poco Efectiva'),
            ('3', '3 - Moderadamente Efectiva'),
            ('4', '4 - Efectiva'),
            ('5', '5 - Muy Efectiva')
        ],
        validators=[DataRequired(message='Califica la efectividad')],
        render_kw={'class': 'form-select'}
    )
    
    # Seguimiento
    follow_up_needed = BooleanField(
        'Requiere Seguimiento',
        render_kw={'class': 'form-check-input'}
    )
    
    follow_up_date = DateField(
        'Fecha de Seguimiento',
        validators=[ConditionalRequired('follow_up_needed')],
        render_kw={'class': 'form-control'}
    )
    
    follow_up_notes = TextAreaField(
        'Notas de Seguimiento',
        validators=[ConditionalRequired('follow_up_needed')],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Detalles del seguimiento necesario',
            'rows': '3'
        }
    )
    
    # Archivos adjuntos
    meeting_recording = FileField(
        'Grabación de la Reunión',
        validators=[
            FileAllowed(['mp4', 'avi', 'mov', 'mp3', 'm4a'], 'Solo archivos de audio/video')
        ],
        render_kw={'class': 'form-control'}
    )
    
    presentation_files = FileField(
        'Presentaciones/Documentos',
        validators=[
            FileAllowed(['pdf', 'ppt', 'pptx', 'doc', 'docx'], 'Solo documentos permitidos')
        ],
        render_kw={'class': 'form-control'}
    )
    
    additional_notes = TextAreaField(
        'Notas Adicionales',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Cualquier información adicional relevante',
            'rows': '3'
        }
    )
    
    def __init__(self, meeting=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if meeting:
            # Cargar asistentes de la reunión
            invited_users = meeting.attendees.all()
            user_choices = [
                (user.id, f"{user.first_name} {user.last_name}")
                for user in invited_users
            ]
            
            self.attendees_present.choices = user_choices
            self.attendees_absent.choices = user_choices


class MeetingSearchForm(BaseForm):
    """Formulario para buscar y filtrar reuniones."""
    
    search_term = StringField(
        'Buscar',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Buscar por título, descripción o notas...'
        }
    )
    
    meeting_type = SelectField(
        'Tipo de Reunión',
        choices=[('', 'Todos los tipos')] + MEETING_TYPES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    status = SelectField(
        'Estado',
        choices=[('', 'Todos los estados')] + MEETING_STATUSES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    priority = SelectField(
        'Prioridad',
        choices=[('', 'Todas las prioridades')] + MEETING_PRIORITIES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    project_id = SelectField(
        'Proyecto',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    organizer_id = SelectField(
        'Organizador',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    is_virtual = SelectField(
        'Modalidad',
        choices=[('', 'Todas'), ('true', 'Virtual'), ('false', 'Presencial')],
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    date_from = DateField(
        'Fecha Desde',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    date_to = DateField(
        'Fecha Hasta',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    duration_min = SelectField(
        'Duración Mínima',
        choices=[('', 'Cualquiera')] + MEETING_DURATIONS,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    duration_max = SelectField(
        'Duración Máxima',
        choices=[('', 'Cualquiera')] + MEETING_DURATIONS,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    my_meetings_only = BooleanField(
        'Solo Mis Reuniones',
        render_kw={'class': 'form-check-input'}
    )
    
    include_past = BooleanField(
        'Incluir Pasadas',
        render_kw={'class': 'form-check-input'}
    )
    
    sort_by = SelectField(
        'Ordenar por',
        choices=[
            ('date_desc', 'Más recientes'),
            ('date_asc', 'Más antiguas'),
            ('title_asc', 'Título A-Z'),
            ('title_desc', 'Título Z-A'),
            ('priority_desc', 'Mayor prioridad'),
            ('duration_desc', 'Mayor duración'),
            ('created_desc', 'Creadas recientemente')
        ],
        default='date_desc',
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar proyectos
        self.project_id.choices = [(0, 'Todos los proyectos')] + [
            (project.id, project.name) 
            for project in Project.query.filter_by(is_active=True).all()
        ]
        
        # Cargar usuarios como organizadores
        self.organizer_id.choices = [(0, 'Todos los organizadores')] + [
            (user.id, f"{user.first_name} {user.last_name}")
            for user in User.query.filter_by(is_active=True).all()
        ]
    
    def validate_date_to(self, field):
        """Validar que la fecha final sea posterior a la inicial."""
        if field.data and self.date_from.data:
            if field.data < self.date_from.data:
                raise ValidationError('La fecha final debe ser posterior a la inicial')


class QuickMeetingForm(BaseForm):
    """Formulario rápido para crear reuniones inmediatas."""
    
    title = StringField(
        'Título',
        validators=[
            DataRequired(message='El título es obligatorio'),
            Length(min=5, max=100, message='Entre 5 y 100 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Reunión rápida'
        }
    )
    
    duration = SelectField(
        'Duración',
        choices=[
            ('15', '15 minutos'),
            ('30', '30 minutos'),
            ('45', '45 minutos'),
            ('60', '1 hora')
        ],
        default='30',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    attendees = SelectMultipleField(
        'Asistentes',
        coerce=int,
        validators=[DataRequired(message='Selecciona asistentes')],
        render_kw={
            'class': 'form-select',
            'multiple': True,
            'size': '5'
        }
    )
    
    platform = SelectField(
        'Plataforma',
        choices=[
            ('google_meet', 'Google Meet'),
            ('zoom', 'Zoom'),
            ('teams', 'Microsoft Teams'),
            ('manual', 'Configurar manualmente')
        ],
        default='google_meet',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    start_immediately = BooleanField(
        'Iniciar Inmediatamente',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar usuarios activos
        self.attendees.choices = [
            (user.id, f"{user.first_name} {user.last_name}")
            for user in User.query.filter_by(is_active=True).all()
        ]


class BulkMeetingActionForm(BaseForm):
    """Formulario para acciones masivas en reuniones."""
    
    meeting_ids = FieldList(
        HiddenField(),
        min_entries=1,
        validators=[DataRequired(message='Selecciona al menos una reunión')]
    )
    
    action = SelectField(
        'Acción',
        choices=[
            ('cancel', 'Cancelar'),
            ('postpone', 'Postergar'),
            ('export', 'Exportar'),
            ('send_reminder', 'Enviar Recordatorio'),
            ('change_organizer', 'Cambiar Organizador'),
            ('archive', 'Archivar'),
            ('delete', 'Eliminar')
        ],
        validators=[DataRequired(message='Selecciona una acción')],
        render_kw={'class': 'form-select'}
    )
    
    # Campos condicionales
    new_organizer_id = SelectField(
        'Nuevo Organizador',
        coerce=int,
        validators=[ConditionalRequired('action', 'change_organizer')],
        render_kw={'class': 'form-select'}
    )
    
    reason = TextAreaField(
        'Motivo',
        validators=[ConditionalRequired('action', ['cancel', 'postpone'])],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Explica el motivo de la acción',
            'rows': '3'
        }
    )
    
    new_date = DateField(
        'Nueva Fecha',
        validators=[ConditionalRequired('action', 'postpone')],
        render_kw={'class': 'form-control'}
    )
    
    new_time = TimeField(
        'Nueva Hora',
        validators=[ConditionalRequired('action', 'postpone')],
        render_kw={'class': 'form-control'}
    )
    
    notify_attendees = BooleanField(
        'Notificar a Asistentes',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    confirm_action = BooleanField(
        'Confirmar Acción',
        validators=[DataRequired(message='Debes confirmar la acción')],
        render_kw={'class': 'form-check-input'}
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar usuarios para cambio de organizador
        self.new_organizer_id.choices = [
            (user.id, f"{user.first_name} {user.last_name}")
            for user in User.query.filter_by(is_active=True).all()
        ]


# Exportar formularios principales
__all__ = [
    'CreateMeetingForm',
    'EditMeetingForm',
    'MeetingAttendeesForm',
    'MeetingNotesForm',
    'MeetingSearchForm',
    'QuickMeetingForm',
    'BulkMeetingActionForm'
]