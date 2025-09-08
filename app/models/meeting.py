"""
Modelo Reunión del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de reuniones, incluyendo programación,
seguimiento, participantes, agenda, actas y seguimiento de compromisos.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Time, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
from decimal import Decimal

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    MEETING_TYPES,
    MEETING_STATUS,
    MEETING_PRIORITIES,
    RECURRENCE_PATTERNS,
    REMINDER_INTERVALS,
    PARTICIPANT_ROLES,
    ATTENDANCE_STATUS
)
from ..core.exceptions import ValidationError


class MeetingType(Enum):
    """Tipos de reunión"""
    ONE_ON_ONE = "one_on_one"
    TEAM = "team"
    BOARD = "board"
    INVESTOR_PITCH = "investor_pitch" 
    DEMO = "demo"
    STANDUP = "standup"
    RETROSPECTIVE = "retrospective"
    PLANNING = "planning"
    REVIEW = "review"
    TRAINING = "training"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    NETWORKING = "networking"
    INTERVIEW = "interview"
    CONSULTATION = "consultation"
    MENTORSHIP = "mentorship"
    CLIENT_MEETING = "client_meeting"
    PARTNER_MEETING = "partner_meeting"
    FOLLOW_UP = "follow_up"
    KICK_OFF = "kick_off"
    CLOSING = "closing"
    EMERGENCY = "emergency"
    SOCIAL = "social"
    OTHER = "other"


class MeetingStatus(Enum):
    """Estados de reunión"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class MeetingPriority(Enum):
    """Prioridades de reunión"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high" 
    URGENT = "urgent"
    CRITICAL = "critical"


class MeetingFormat(Enum):
    """Formato de reunión"""
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    PHONE_CALL = "phone_call"
    HYBRID = "hybrid"
    ASYNC = "async"


class RecurrencePattern(Enum):
    """Patrones de recurrencia"""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    BI_WEEKLY = "bi_weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ParticipantRole(Enum):
    """Roles de participante"""
    ORGANIZER = "organizer"
    REQUIRED = "required"
    OPTIONAL = "optional"
    RESOURCE = "resource"
    OBSERVER = "observer"
    PRESENTER = "presenter"
    FACILITATOR = "facilitator"
    NOTE_TAKER = "note_taker"


class AttendanceStatus(Enum):
    """Estados de asistencia"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ATTENDED = "attended"
    NO_SHOW = "no_show"
    LATE = "late"
    LEFT_EARLY = "left_early"


# Tabla de asociación para participantes
from app.extensions import db
meeting_participants = Table(
    'meeting_participants', db.metadata,
    Column('meeting_id', Integer, ForeignKey('meetings.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='required'),
    Column('attendance_status', String(20), default='pending'),
    Column('response_datetime', DateTime),
    Column('check_in_time', DateTime),
    Column('check_out_time', DateTime),
    Column('notes', Text),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para reuniones relacionadas
meeting_relations = Table(
    'meeting_relations', db.metadata,
    Column('parent_meeting_id', Integer, ForeignKey('meetings.id'), primary_key=True),
    Column('child_meeting_id', Integer, ForeignKey('meetings.id'), primary_key=True),
    Column('relation_type', String(50)),  # follow_up, prerequisite, related, series
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Meeting(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Reunión
    
    Representa reuniones en el ecosistema de emprendimiento con gestión completa
    de participantes, agenda, seguimiento y resultados.
    """
    
    __tablename__ = 'meetings'
    
    # Información básica
    title = Column(String(300), nullable=False, index=True)
    description = Column(Text)
    meeting_type = Column(SQLEnum(MeetingType), nullable=False, index=True)
    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.DRAFT, index=True)
    priority = Column(SQLEnum(MeetingPriority), default=MeetingPriority.MEDIUM)
    
    # Organizador
    organizer_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    organizer = relationship("User", foreign_keys=[organizer_id])
    
    # Fechas y horarios
    scheduled_start = Column(DateTime, nullable=False, index=True)
    scheduled_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    duration_minutes = Column(Integer, default=60)
    actual_duration_minutes = Column(Integer)
    
    # Ubicación y formato
    format = Column(SQLEnum(MeetingFormat), default=MeetingFormat.VIDEO_CALL)
    location = Column(String(500))  # Dirección física o descripción
    meeting_url = Column(String(1000))  # URL de video conferencia
    meeting_id = Column(String(200))  # ID de la reunión (Zoom, Meet, etc.)
    meeting_password = Column(String(100))
    dial_in_info = Column(JSON)  # Información de marcado telefónico
    
    # Recurrencia
    recurrence_pattern = Column(SQLEnum(RecurrencePattern), default=RecurrencePattern.NONE)
    recurrence_settings = Column(JSON)  # Configuración detallada de recurrencia
    parent_meeting_id = Column(Integer, ForeignKey('meetings.id'))  # Para reuniones recurrentes
    series_id = Column(String(100))  # ID único para serie de reuniones
    
    # Agenda y contenido
    agenda = Column(JSON)  # Agenda estructurada
    objectives = Column(JSON)  # Objetivos de la reunión
    pre_meeting_materials = Column(JSON)  # Materiales de preparación
    presentation_files = Column(JSON)  # Archivos de presentación
    
    # Configuración de participantes
    max_participants = Column(Integer)
    allow_guests = Column(Boolean, default=False)
    require_registration = Column(Boolean, default=False)
    auto_approve_requests = Column(Boolean, default=True)
    
    # Configuración de grabación y documentación
    record_meeting = Column(Boolean, default=False)
    recording_url = Column(String(1000))
    recording_password = Column(String(100))
    auto_generate_transcript = Column(Boolean, default=False)
    transcript_url = Column(String(1000))
    
    # Recordatorios y notificaciones
    reminder_settings = Column(JSON)  # Configuración de recordatorios
    send_calendar_invites = Column(Boolean, default=True)
    notification_preferences = Column(JSON)
    
    # Seguimiento y resultados
    meeting_notes = Column(Text)  # Notas generales de la reunión
    key_decisions = Column(JSON)  # Decisiones clave tomadas
    action_items = Column(JSON)  # Elementos de acción
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date)
    
    # Evaluación y feedback
    meeting_rating = Column(Float)  # Calificación general (1-5)
    effectiveness_score = Column(Float)  # Puntuación de efectividad
    participant_feedback = Column(JSON)  # Feedback de participantes
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project", back_populates="meetings")
    
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'))
    entrepreneur = relationship("Entrepreneur", back_populates="meetings")
    
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship("Client", back_populates="meetings")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organizing_organization = relationship("Organization", back_populates="meetings")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    mentorship_id = Column(Integer, ForeignKey('mentorship_relationships.id'))
    mentorship = relationship("MentorshipRelationship")
    
    # Configuración avanzada
    timezone = Column(String(50), default='UTC')
    language = Column(String(10), default='es')
    custom_fields = Column(JSON)
    tags = Column(JSON)  # Tags para categorización
    
    # Configuración de privacidad y seguridad
    is_private = Column(Boolean, default=False)
    requires_approval = Column(Boolean, default=False)
    waiting_room_enabled = Column(Boolean, default=False)
    password_required = Column(Boolean, default=False)
    
    # Costos (si aplica)
    has_cost = Column(Boolean, default=False)
    cost_per_participant = Column(Integer)  # En centavos
    currency = Column(String(3), default='USD')
    
    # Relaciones
    
    # Participantes
    participants = relationship("User",
                              secondary=meeting_participants,
                              back_populates="meetings_participating")
    
    # Documentos asociados
    documents = relationship("Document", back_populates="meeting")
    
    # Tareas generadas
    tasks = relationship("Task", back_populates="meeting")
    
    # Actividades relacionadas
    activities = relationship("ActivityLog", back_populates="meeting")
    
    # Reuniones relacionadas
    child_meetings = relationship("Meeting",
                                secondary=meeting_relations,
                                primaryjoin="Meeting.id == meeting_relations.c.parent_meeting_id",
                                secondaryjoin="Meeting.id == meeting_relations.c.child_meeting_id",
                                back_populates="parent_meetings")
    
    parent_meetings = relationship("Meeting",
                                  secondary=meeting_relations,
                                  primaryjoin="Meeting.id == meeting_relations.c.child_meeting_id",
                                  secondaryjoin="Meeting.id == meeting_relations.c.parent_meeting_id",
                                  back_populates="child_meetings")
    
    def __init__(self, **kwargs):
        """Inicialización de la reunión"""
        super().__init__(**kwargs)
        
        # Configurar duración por defecto
        if not self.scheduled_end and self.scheduled_start and self.duration_minutes:
            self.scheduled_end = self.scheduled_start + timedelta(minutes=self.duration_minutes)
        
        # Configuraciones por defecto
        if not self.reminder_settings:
            self.reminder_settings = {
                'send_reminders': True,
                'reminder_intervals': [24 * 60, 60, 15],  # 24h, 1h, 15min antes
                'reminder_methods': ['email', 'notification']
            }
        
        if not self.notification_preferences:
            self.notification_preferences = {
                'new_participants': True,
                'status_changes': True,
                'rescheduling': True,
                'cancellation': True
            }
        
        # Generar series_id para reuniones recurrentes
        if self.recurrence_pattern != RecurrencePattern.NONE and not self.series_id:
            self.series_id = f"series_{int(datetime.now(timezone.utc).timestamp())}"
    
    def __repr__(self):
        return f'<Meeting {self.title} - {self.scheduled_start}>'
    
    def __str__(self):
        return f'{self.title} ({self.meeting_type.value}) - {self.scheduled_start.strftime("%Y-%m-%d %H:%M")}'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título"""
        if not title or len(title.strip()) < 3:
            raise ValidationError("El título debe tener al menos 3 caracteres")
        if len(title) > 300:
            raise ValidationError("El título no puede exceder 300 caracteres")
        return title.strip()
    
    @validates('scheduled_start', 'scheduled_end')
    def validate_schedule(self, key, datetime_value):
        """Validar fechas programadas"""
        if datetime_value:
            if key == 'scheduled_end' and self.scheduled_start:
                if datetime_value <= self.scheduled_start:
                    raise ValidationError("La hora de fin debe ser posterior al inicio")
            
            # Solo validar fechas futuras para nuevas reuniones
            if not self.id and datetime_value < datetime.now(timezone.utc):
                raise ValidationError("No se pueden programar reuniones en el pasado")
        
        return datetime_value
    
    @validates('duration_minutes')
    def validate_duration(self, key, duration):
        """Validar duración"""
        if duration is not None:
            if duration < 5 or duration > 1440:  # Entre 5 minutos y 24 horas
                raise ValidationError("La duración debe estar entre 5 y 1440 minutos")
        return duration
    
    @validates('meeting_rating', 'effectiveness_score')
    def validate_ratings(self, key, rating):
        """Validar calificaciones"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("Las calificaciones deben estar entre 1 y 5")
        return rating
    
    @validates('max_participants')
    def validate_max_participants(self, key, max_participants):
        """Validar máximo de participantes"""
        if max_participants is not None:
            if max_participants < 1 or max_participants > 10000:
                raise ValidationError("El máximo de participantes debe estar entre 1 y 10,000")
        return max_participants
    
    @validates('meeting_url')
    def validate_meeting_url(self, key, url):
        """Validar URL de reunión"""
        if url:
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(url):
                raise ValidationError("URL de reunión inválida")
        
        return url
    
    # Propiedades híbridas
    @hybrid_property
    def is_upcoming(self):
        """Verificar si la reunión es próxima"""
        return (self.scheduled_start > datetime.now(timezone.utc) and 
                self.status in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED])
    
    @hybrid_property
    def is_ongoing(self):
        """Verificar si la reunión está en curso"""
        return self.status == MeetingStatus.IN_PROGRESS
    
    @hybrid_property
    def is_past(self):
        """Verificar si la reunión ya pasó"""
        return self.scheduled_start < datetime.now(timezone.utc)
    
    @hybrid_property
    def is_overdue(self):
        """Verificar si la reunión está vencida (pasó sin completarse)"""
        return (self.scheduled_end < datetime.now(timezone.utc) and 
                self.status == MeetingStatus.SCHEDULED)
    
    @hybrid_property
    def duration_actual_or_planned(self):
        """Duración real o planificada"""
        return self.actual_duration_minutes or self.duration_minutes
    
    @hybrid_property
    def participant_count(self):
        """Número de participantes"""
        return len(self.participants)
    
    @hybrid_property
    def days_until_meeting(self):
        """Días hasta la reunión"""
        if self.scheduled_start > datetime.now(timezone.utc):
            return (self.scheduled_start.date() - date.today()).days
        return 0
    
    @hybrid_property
    def hours_until_meeting(self):
        """Horas hasta la reunión"""
        if self.scheduled_start > datetime.now(timezone.utc):
            return (self.scheduled_start - datetime.now(timezone.utc)).total_seconds() / 3600
        return 0
    
    @hybrid_property
    def started_on_time(self):
        """Verificar si empezó a tiempo"""
        if self.actual_start and self.scheduled_start:
            delay_minutes = (self.actual_start - self.scheduled_start).total_seconds() / 60
            return delay_minutes <= 5  # Tolerancia de 5 minutos
        return None
    
    @hybrid_property
    def ended_on_time(self):
        """Verificar si terminó a tiempo"""
        if self.actual_end and self.scheduled_end:
            diff_minutes = (self.actual_end - self.scheduled_end).total_seconds() / 60
            return abs(diff_minutes) <= 10  # Tolerancia de 10 minutos
        return None
    
    # Métodos de negocio
    def add_participant(self, user, role: ParticipantRole = ParticipantRole.REQUIRED, 
                       send_invite: bool = True) -> bool:
        """Agregar participante"""
        # Verificar límite de participantes
        if self.max_participants and len(self.participants) >= self.max_participants:
            raise ValidationError("Se ha alcanzado el máximo de participantes")
        
        # Verificar si ya es participante
        if user in self.participants:
            return False
        
        from .. import db
        
        participant_data = {
            'meeting_id': self.id,
            'user_id': user.id,
            'role': role.value,
            'attendance_status': AttendanceStatus.PENDING.value
        }
        
        db.session.execute(meeting_participants.insert().values(participant_data))
        
        if send_invite and self.send_calendar_invites:
            self._send_calendar_invite(user)
        
        return True
    
    def remove_participant(self, user):
        """Remover participante"""
        if user not in self.participants:
            return False
        
        from .. import db
        
        db.session.execute(
            meeting_participants.delete().where(
                meeting_participants.c.meeting_id == self.id,
                meeting_participants.c.user_id == user.id
            )
        )
        
        return True
    
    def update_participant_status(self, user, status: AttendanceStatus, notes: str = None):
        """Actualizar estado de participante"""
        from .. import db
        
        db.session.execute(
            meeting_participants.update().where(
                meeting_participants.c.meeting_id == self.id,
                meeting_participants.c.user_id == user.id
            ).values(
                attendance_status=status.value,
                response_datetime=datetime.now(timezone.utc),
                notes=notes
            )
        )
    
    def start_meeting(self):
        """Iniciar la reunión"""
        if self.status not in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]:
            raise ValidationError("Solo se pueden iniciar reuniones programadas o confirmadas")
        
        self.status = MeetingStatus.IN_PROGRESS
        self.actual_start = datetime.now(timezone.utc)
        
        # Log de inicio
        self._log_status_change('started')
    
    def end_meeting(self, meeting_notes: str = None, key_decisions: list[str] = None,
                   action_items: list[dict[str, Any]] = None, meeting_rating: float = None):
        """Finalizar la reunión"""
        if self.status != MeetingStatus.IN_PROGRESS:
            raise ValidationError("Solo se pueden finalizar reuniones en progreso")
        
        self.status = MeetingStatus.COMPLETED
        self.actual_end = datetime.now(timezone.utc)
        
        if self.actual_start:
            duration = (self.actual_end - self.actual_start).total_seconds() / 60
            self.actual_duration_minutes = int(duration)
        
        if meeting_notes:
            self.meeting_notes = meeting_notes
        if key_decisions:
            self.key_decisions = key_decisions
        if action_items:
            self.action_items = action_items
            # Crear tareas para elementos de acción si es necesario
            self._create_action_item_tasks(action_items)
        if meeting_rating:
            self.meeting_rating = meeting_rating
        
        # Log de finalización
        self._log_status_change('completed')
        
        # Programar follow-up si es necesario
        if self.follow_up_required and self.follow_up_date:
            self._schedule_follow_up()
    
    def cancel_meeting(self, reason: str = None, notify_participants: bool = True):
        """Cancelar la reunión"""
        if self.status in [MeetingStatus.COMPLETED, MeetingStatus.CANCELLED]:
            raise ValidationError("No se puede cancelar una reunión ya finalizada")
        
        self.status = MeetingStatus.CANCELLED
        
        # Agregar razón a las notas
        if reason:
            self.meeting_notes = f"Cancelada: {reason}\n{self.meeting_notes or ''}"
        
        if notify_participants:
            self._notify_participants('meeting_cancelled', {'reason': reason})
        
        self._log_status_change('cancelled', reason)
    
    def reschedule_meeting(self, new_start: datetime, new_end: datetime = None, 
                          reason: str = None, notify_participants: bool = True):
        """Reprogramar la reunión"""
        if self.status in [MeetingStatus.COMPLETED, MeetingStatus.CANCELLED]:
            raise ValidationError("No se puede reprogramar una reunión finalizada")
        
        # Guardar horarios originales
        original_start = self.scheduled_start
        original_end = self.scheduled_end
        
        self.scheduled_start = new_start
        self.scheduled_end = new_end or (new_start + timedelta(minutes=self.duration_minutes))
        self.status = MeetingStatus.RESCHEDULED
        
        if notify_participants:
            self._notify_participants('meeting_rescheduled', {
                'original_start': original_start.isoformat(),
                'new_start': new_start.isoformat(),
                'reason': reason
            })
        
        self._log_status_change('rescheduled', reason)
    
    def add_agenda_item(self, title: str, description: str = None, 
                       duration_minutes: int = None, presenter: str = None):
        """Agregar elemento a la agenda"""
        if not self.agenda:
            self.agenda = []
        
        agenda_item = {
            'id': len(self.agenda) + 1,
            'title': title,
            'description': description,
            'duration_minutes': duration_minutes,
            'presenter': presenter,
            'completed': False,
            'start_time': None,
            'end_time': None
        }
        
        self.agenda.append(agenda_item)
    
    def add_action_item(self, description: str, assignee_id: int, due_date: date = None,
                       priority: str = 'medium'):
        """Agregar elemento de acción"""
        if not self.action_items:
            self.action_items = []
        
        action_item = {
            'id': len(self.action_items) + 1,
            'description': description,
            'assignee_id': assignee_id,
            'due_date': due_date.isoformat() if due_date else None,
            'priority': priority,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        self.action_items.append(action_item)
    
    def _create_action_item_tasks(self, action_items: list[dict[str, Any]]):
        """Crear tareas para elementos de acción"""
        from .task import Task
        from .. import db
        
        for item in action_items:
            if item.get('create_task', False):
                task = Task(
                    title=f"[Reunión] {item['description']}",
                    description=f"Elemento de acción de la reunión: {self.title}",
                    assignee_id=item.get('assignee_id'),
                    due_date=datetime.fromisoformat(item['due_date']) if item.get('due_date') else None,
                    priority=item.get('priority', 'medium'),
                    meeting_id=self.id,
                    project_id=self.project_id
                )
                
                db.session.add(task)
    
    def _schedule_follow_up(self):
        """Programar reunión de seguimiento"""
        if not self.follow_up_date:
            return
        
        follow_up_meeting = Meeting(
            title=f"Follow-up: {self.title}",
            description=f"Reunión de seguimiento para: {self.title}",
            meeting_type=MeetingType.FOLLOW_UP,
            organizer_id=self.organizer_id,
            scheduled_start=datetime.combine(self.follow_up_date, datetime.min.time().replace(hour=10)),
            duration_minutes=30,
            format=self.format,
            project_id=self.project_id,
            entrepreneur_id=self.entrepreneur_id,
            client_id=self.client_id,
            organization_id=self.organization_id
        )
        
        from .. import db
        db.session.add(follow_up_meeting)
        
        # Agregar relación
        self._add_related_meeting(follow_up_meeting, 'follow_up')
    
    def _add_related_meeting(self, related_meeting: 'Meeting', relation_type: str):
        """Agregar reunión relacionada"""
        from .. import db
        
        relation_data = {
            'parent_meeting_id': self.id,
            'child_meeting_id': related_meeting.id,
            'relation_type': relation_type
        }
        
        db.session.execute(meeting_relations.insert().values(relation_data))
    
    def _send_calendar_invite(self, user):
        """Enviar invitación de calendario"""
        # Implementar integración con servicio de calendario
        # Por ahora, solo log
        self._log_activity('calendar_invite_sent', f"Invitación enviada a {user.full_name}")
    
    def _notify_participants(self, notification_type: str, data: dict[str, Any] = None):
        """Notificar a participantes"""
        # Implementar sistema de notificaciones
        self._log_activity(notification_type, f"Notificación enviada: {notification_type}")
    
    def _log_status_change(self, action: str, notes: str = None):
        """Registrar cambio de estado"""
        self._log_activity('status_change', f"Reunión {action}", {'notes': notes})
    
    def _log_activity(self, activity_type: str, description: str, metadata: dict[str, Any] = None):
        """Registrar actividad"""
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type=activity_type,
            description=description,
            metadata=metadata or {},
            meeting_id=self.id,
            user_id=self.organizer_id
        )
        
        db.session.add(activity)
    
    def get_meeting_analytics(self) -> dict[str, Any]:
        """Obtener analytics de la reunión"""
        attendance_summary = self.get_attendance_summary()
        
        return {
            'basic_info': {
                'title': self.title,
                'type': self.meeting_type.value,
                'status': self.status.value,
                'priority': self.priority.value,
                'format': self.format.value,
                'duration_planned': self.duration_minutes,
                'duration_actual': self.actual_duration_minutes
            },
            'timing': {
                'scheduled_start': self.scheduled_start.isoformat(),
                'scheduled_end': self.scheduled_end.isoformat(),
                'actual_start': self.actual_start.isoformat() if self.actual_start else None,
                'actual_end': self.actual_end.isoformat() if self.actual_end else None,
                'started_on_time': self.started_on_time,
                'ended_on_time': self.ended_on_time,
                'is_upcoming': self.is_upcoming,
                'is_overdue': self.is_overdue,
                'days_until_meeting': self.days_until_meeting
            },
            'attendance': attendance_summary,
            'content': {
                'agenda_items': len(self.agenda) if self.agenda else 0,
                'action_items': len(self.action_items) if self.action_items else 0,
                'key_decisions': len(self.key_decisions) if self.key_decisions else 0,
                'has_recording': bool(self.recording_url),
                'has_transcript': bool(self.transcript_url),
                'has_notes': bool(self.meeting_notes)
            },
            'engagement': {
                'meeting_rating': self.meeting_rating,
                'effectiveness_score': self.effectiveness_score,
                'has_feedback': bool(self.participant_feedback)
            },
            'follow_up': {
                'follow_up_required': self.follow_up_required,
                'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
                'related_meetings': len(self.child_meetings)
            }
        }
    
    def get_dashboard_data(self) -> dict[str, Any]:
        """Generar datos para dashboard"""
        return {
            'meeting_info': {
                'title': self.title,
                'type': self.meeting_type.value,
                'status': self.status.value,
                'priority': self.priority.value,
                'scheduled_start': self.scheduled_start.isoformat(),
                'duration_minutes': self.duration_minutes,
                'format': self.format.value,
                'is_upcoming': self.is_upcoming,
                'is_ongoing': self.is_ongoing,
                'hours_until_meeting': self.hours_until_meeting if self.is_upcoming else None
            },
            'participants': {
                'total': self.participant_count,
                'max_allowed': self.max_participants,
                'organizer': self.organizer.full_name if self.organizer else None
            },
            'agenda': {
                'items_count': len(self.agenda) if self.agenda else 0,
                'estimated_duration': sum(item.get('duration_minutes', 0) for item in (self.agenda or [])),
                'items': self.agenda[:5] if self.agenda else []  # Primeros 5 items
            },
            'context': {
                'project': self.project.name if self.project else None,
                'entrepreneur': self.entrepreneur.full_name if self.entrepreneur else None,
                'client': self.client.name if self.client else None,
                'organization': self.organizing_organization.name if self.organizing_organization else None
            },
            'links': {
                'meeting_url': self.meeting_url,
                'has_dial_in': bool(self.dial_in_info),
                'requires_password': self.password_required
            }
        }
    
    def calculate_effectiveness_score(self) -> float:
        """Calcular puntuación de efectividad"""
        score = 0.0
        factors = 0
        
        # Factor 1: Puntualidad (25%)
        if self.started_on_time is not None:
            score += 25 if self.started_on_time else 10
            factors += 1
        
        # Factor 2: Asistencia (25%)
        attendance_summary = self.get_attendance_summary()
        if attendance_summary['total_invited'] > 0:
            attendance_rate = attendance_summary['attendance_rate']
            if attendance_rate >= 90:
                score += 25
            elif attendance_rate >= 75:
                score += 20
            elif attendance_rate >= 50:
                score += 15
            else:
                score += 5
            factors += 1
        
        # Factor 3: Duración apropiada (20%)
        if self.actual_duration_minutes and self.duration_minutes:
            duration_ratio = self.actual_duration_minutes / self.duration_minutes
            if 0.9 <= duration_ratio <= 1.1:  # ±10% de la duración planificada
                score += 20
            elif 0.8 <= duration_ratio <= 1.2:  # ±20%
                score += 15
            else:
                score += 5
            factors += 1
        
        # Factor 4: Contenido y resultados (30%)
        content_score = 0
        if self.agenda and len(self.agenda) > 0:
            content_score += 8
        if self.key_decisions and len(self.key_decisions) > 0:
            content_score += 8
        if self.action_items and len(self.action_items) > 0:
            content_score += 8
        if self.meeting_notes and len(self.meeting_notes.strip()) > 50:
            content_score += 6
        
        score += content_score
        factors += 1
        
        # Calcular puntuación final
        if factors == 0:
            return 0.0
        
        final_score = score / factors if factors > 0 else 0
        self.effectiveness_score = round(final_score, 1)
        
        return self.effectiveness_score
    
    def generate_meeting_summary(self) -> dict[str, Any]:
        """Generar resumen de la reunión"""
        if self.status != MeetingStatus.COMPLETED:
            return {'error': 'La reunión debe estar completada para generar resumen'}
        
        attendance_summary = self.get_attendance_summary()
        
        return {
            'meeting_details': {
                'title': self.title,
                'date': self.scheduled_start.strftime('%Y-%m-%d'),
                'time': f"{self.scheduled_start.strftime('%H:%M')} - {self.scheduled_end.strftime('%H:%M')}",
                'duration': f"{self.actual_duration_minutes or self.duration_minutes} minutos",
                'type': self.meeting_type.value,
                'format': self.format.value,
                'organizer': self.organizer.full_name if self.organizer else None
            },
            'attendance': {
                'invited': attendance_summary['total_invited'],
                'attended': attendance_summary['total_attended'],
                'attendance_rate': f"{attendance_summary['attendance_rate']:.1f}%",
                'no_shows': attendance_summary['no_shows']
            },
            'agenda_completion': {
                'total_items': len(self.agenda) if self.agenda else 0,
                'completed_items': len([item for item in (self.agenda or []) if item.get('completed', False)]),
                'completion_rate': self._calculate_agenda_completion_rate()
            },
            'outcomes': {
                'key_decisions': self.key_decisions or [],
                'action_items': len(self.action_items) if self.action_items else 0,
                'follow_up_required': self.follow_up_required,
                'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None
            },
            'evaluation': {
                'meeting_rating': self.meeting_rating,
                'effectiveness_score': self.effectiveness_score or self.calculate_effectiveness_score(),
                'started_on_time': self.started_on_time,
                'ended_on_time': self.ended_on_time
            },
            'resources': {
                'recording_available': bool(self.recording_url),
                'transcript_available': bool(self.transcript_url),
                'materials_shared': len(self.presentation_files) if self.presentation_files else 0,
                'documents_attached': len(self.documents) if self.documents else 0
            },
            'notes': self.meeting_notes
        }
    
    def _calculate_agenda_completion_rate(self) -> float:
        """Calcular tasa de finalización de agenda"""
        if not self.agenda or len(self.agenda) == 0:
            return 0.0
        
        completed = len([item for item in self.agenda if item.get('completed', False)])
        return (completed / len(self.agenda)) * 100
    
    def create_recurring_meetings(self, end_date: date, max_occurrences: int = 52) -> list['Meeting']:
        """Crear reuniones recurrentes"""
        if self.recurrence_pattern == RecurrencePattern.NONE:
            return []
        
        meetings = []
        current_date = self.scheduled_start
        occurrence_count = 0
        
        while (current_date.date() <= end_date and 
               occurrence_count < max_occurrences):
            
            # Calcular próxima fecha
            next_date = self._calculate_next_occurrence(current_date)
            if not next_date or next_date.date() > end_date:
                break
            
            # Crear nueva reunión
            new_meeting = Meeting(
                title=self.title,
                description=self.description,
                meeting_type=self.meeting_type,
                organizer_id=self.organizer_id,
                scheduled_start=next_date,
                scheduled_end=next_date + timedelta(minutes=self.duration_minutes),
                duration_minutes=self.duration_minutes,
                format=self.format,
                location=self.location,
                meeting_url=self.meeting_url,
                recurrence_pattern=self.recurrence_pattern,
                recurrence_settings=self.recurrence_settings,
                parent_meeting_id=self.id,
                series_id=self.series_id,
                agenda=self.agenda.copy() if self.agenda else None,
                objectives=self.objectives.copy() if self.objectives else None,
                project_id=self.project_id,
                entrepreneur_id=self.entrepreneur_id,
                client_id=self.client_id,
                organization_id=self.organization_id,
                program_id=self.program_id,
                priority=self.priority,
                max_participants=self.max_participants,
                allow_guests=self.allow_guests,
                record_meeting=self.record_meeting,
                auto_generate_transcript=self.auto_generate_transcript,
                reminder_settings=self.reminder_settings.copy() if self.reminder_settings else None,
                notification_preferences=self.notification_preferences.copy() if self.notification_preferences else None
            )
            
            from .. import db
            db.session.add(new_meeting)
            meetings.append(new_meeting)
            
            # Copiar participantes
            for participant in self.participants:
                new_meeting.add_participant(participant, send_invite=False)
            
            current_date = next_date
            occurrence_count += 1
        
        return meetings
    
    def _calculate_next_occurrence(self, current_date: datetime) -> Optional[datetime]:
        """Calcular próxima ocurrencia basada en patrón de recurrencia"""
        if self.recurrence_pattern == RecurrencePattern.DAILY:
            return current_date + timedelta(days=1)
        
        elif self.recurrence_pattern == RecurrencePattern.WEEKLY:
            return current_date + timedelta(weeks=1)
        
        elif self.recurrence_pattern == RecurrencePattern.BI_WEEKLY:
            return current_date + timedelta(weeks=2)
        
        elif self.recurrence_pattern == RecurrencePattern.MONTHLY:
            # Mismo día del siguiente mes
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1)
            return next_month
        
        elif self.recurrence_pattern == RecurrencePattern.QUARTERLY:
            # Mismo día del trimestre siguiente
            months_to_add = 3
            new_month = current_date.month + months_to_add
            new_year = current_date.year
            
            if new_month > 12:
                new_year += 1
                new_month -= 12
            
            return current_date.replace(year=new_year, month=new_month)
        
        elif self.recurrence_pattern == RecurrencePattern.YEARLY:
            return current_date.replace(year=current_date.year + 1)
        
        elif self.recurrence_pattern == RecurrencePattern.CUSTOM:
            # Implementar lógica personalizada basada en recurrence_settings
            settings = self.recurrence_settings or {}
            interval = settings.get('interval', 1)
            unit = settings.get('unit', 'weeks')  # days, weeks, months
            
            if unit == 'days':
                return current_date + timedelta(days=interval)
            elif unit == 'weeks':
                return current_date + timedelta(weeks=interval)
            elif unit == 'months':
                new_month = current_date.month + interval
                new_year = current_date.year
                while new_month > 12:
                    new_year += 1
                    new_month -= 12
                return current_date.replace(year=new_year, month=new_month)
        
        return None
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def get_upcoming_meetings(cls, user_id: int = None, days_ahead: int = 7):
        """Obtener reuniones próximas"""
        end_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        query = cls.query.filter(
            cls.scheduled_start.between(datetime.now(timezone.utc), end_date),
            cls.status.in_([MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]),
            cls.is_deleted == False
        )
        
        if user_id:
            query = query.filter(
                (cls.organizer_id == user_id) |
                (cls.participants.any(id=user_id))
            )
        
        return query.order_by(cls.scheduled_start.asc()).all()
    
    @classmethod
    def get_meetings_by_date_range(cls, start_date: date, end_date: date, 
                                  user_id: int = None, meeting_type: MeetingType = None):
        """Obtener reuniones por rango de fechas"""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        query = cls.query.filter(
            cls.scheduled_start.between(start_datetime, end_datetime),
            cls.is_deleted == False
        )
        
        if user_id:
            query = query.filter(
                (cls.organizer_id == user_id) |
                (cls.participants.any(id=user_id))
            )
        
        if meeting_type:
            query = query.filter(cls.meeting_type == meeting_type)
        
        return query.order_by(cls.scheduled_start.asc()).all()
    
    @classmethod
    def get_overdue_meetings(cls):
        """Obtener reuniones vencidas"""
        return cls.query.filter(
            cls.scheduled_end < datetime.now(timezone.utc),
            cls.status == MeetingStatus.SCHEDULED,
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def search_meetings(cls, query_text: str = None, filters: dict[str, Any] = None):
        """Buscar reuniones"""
        search = cls.query.filter(cls.is_deleted == False)
        
        if query_text:
            search_term = f"%{query_text}%"
            search = search.filter(
                cls.title.ilike(search_term) |
                cls.description.ilike(search_term) |
                cls.meeting_notes.ilike(search_term)
            )
        
        if filters:
            if filters.get('type'):
                search = search.filter(cls.meeting_type == filters['type'])
            
            if filters.get('status'):
                if isinstance(filters['status'], list):
                    search = search.filter(cls.status.in_(filters['status']))
                else:
                    search = search.filter(cls.status == filters['status'])
            
            if filters.get('organizer_id'):
                search = search.filter(cls.organizer_id == filters['organizer_id'])
            
            if filters.get('project_id'):
                search = search.filter(cls.project_id == filters['project_id'])
            
            if filters.get('organization_id'):
                search = search.filter(cls.organization_id == filters['organization_id'])
            
            if filters.get('date_from'):
                search = search.filter(cls.scheduled_start >= filters['date_from'])
            
            if filters.get('date_to'):
                search = search.filter(cls.scheduled_start <= filters['date_to'])
            
            if filters.get('format'):
                search = search.filter(cls.format == filters['format'])
            
            if filters.get('priority'):
                search = search.filter(cls.priority == filters['priority'])
        
        return search.order_by(cls.scheduled_start.desc()).all()
    
    def to_dict(self, include_sensitive=False, include_participants=False) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'meeting_type': self.meeting_type.value,
            'status': self.status.value,
            'priority': self.priority.value,
            'scheduled_start': self.scheduled_start.isoformat(),
            'scheduled_end': self.scheduled_end.isoformat(),
            'duration_minutes': self.duration_minutes,
            'actual_duration_minutes': self.actual_duration_minutes,
            'format': self.format.value,
            'location': self.location,
            'organizer_id': self.organizer_id,
            'participant_count': self.participant_count,
            'max_participants': self.max_participants,
            'is_upcoming': self.is_upcoming,
            'is_ongoing': self.is_ongoing,
            'is_past': self.is_past,
            'is_overdue': self.is_overdue,
            'days_until_meeting': self.days_until_meeting,
            'hours_until_meeting': self.hours_until_meeting,
            'recurrence_pattern': self.recurrence_pattern.value,
            'series_id': self.series_id,
            'agenda_items_count': len(self.agenda) if self.agenda else 0,
            'action_items_count': len(self.action_items) if self.action_items else 0,
            'meeting_rating': self.meeting_rating,
            'effectiveness_score': self.effectiveness_score,
            'follow_up_required': self.follow_up_required,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'meeting_url': self.meeting_url,
                'meeting_id': self.meeting_id,
                'meeting_password': self.meeting_password,
                'dial_in_info': self.dial_in_info,
                'recording_url': self.recording_url,
                'recording_password': self.recording_password,
                'transcript_url': self.transcript_url,
                'agenda': self.agenda,
                'objectives': self.objectives,
                'pre_meeting_materials': self.pre_meeting_materials,
                'presentation_files': self.presentation_files,
                'meeting_notes': self.meeting_notes,
                'key_decisions': self.key_decisions,
                'action_items': self.action_items,
                'participant_feedback': self.participant_feedback,
                'reminder_settings': self.reminder_settings,
                'notification_preferences': self.notification_preferences,
                'custom_fields': self.custom_fields,
                'tags': self.tags
            })
        
        if include_participants:
            data['participants'] = [
                {
                    'id': participant.id,
                    'name': participant.full_name,
                    'email': participant.email
                }
                for participant in self.participants
            ]
        
        return data


# Funciones de utilidad para el módulo
def get_meeting_statistics(organization_id: int = None, 
                          date_from: date = None, 
                          date_to: date = None,
                          user_id: int = None) -> dict[str, Any]:
    """Obtener estadísticas de reuniones"""
    query = Meeting.query.filter(Meeting.is_deleted == False)
    
    if organization_id:
        query = query.filter(Meeting.organization_id == organization_id)
    
    if user_id:
        query = query.filter(
            (Meeting.organizer_id == user_id) |
            (Meeting.participants.any(id=user_id))
        )
    
    if date_from:
        query = query.filter(Meeting.scheduled_start >= datetime.combine(date_from, datetime.min.time()))
    
    if date_to:
        query = query.filter(Meeting.scheduled_start <= datetime.combine(date_to, datetime.max.time()))
    
    meetings = query.all()
    
    if not meetings:
        return {
            'total_meetings': 0,
            'completed_meetings': 0,
            'cancelled_meetings': 0,
            'average_duration': 0,
            'average_attendance_rate': 0,
            'average_effectiveness': 0,
            'total_meeting_hours': 0
        }
    
    # Calcular estadísticas
    total = len(meetings)
    completed = len([m for m in meetings if m.status == MeetingStatus.COMPLETED])
    cancelled = len([m for m in meetings if m.status == MeetingStatus.CANCELLED])
    
    # Duración promedio
    durations = [m.actual_duration_minutes or m.duration_minutes for m in meetings]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Horas totales de reuniones
    total_hours = sum(durations) / 60 if durations else 0
    
    # Tasa de asistencia promedio
    attendance_rates = []
    for meeting in meetings:
        if meeting.status == MeetingStatus.COMPLETED:
            summary = meeting.get_attendance_summary()
            if summary['total_invited'] > 0:
                attendance_rates.append(summary['attendance_rate'])
    
    avg_attendance = sum(attendance_rates) / len(attendance_rates) if attendance_rates else 0
    
    # Efectividad promedio
    effectiveness_scores = [m.effectiveness_score for m in meetings if m.effectiveness_score]
    avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0
    
    # Distribución por tipo
    type_distribution = {}
    for meeting in meetings:
        meeting_type = meeting.meeting_type.value
        type_distribution[meeting_type] = type_distribution.get(meeting_type, 0) + 1
    
    # Distribución por formato
    format_distribution = {}
    for meeting in meetings:
        format_type = meeting.format.value
        format_distribution[format_type] = format_distribution.get(format_type, 0) + 1
    
    return {
        'total_meetings': total,
        'completed_meetings': completed,
        'cancelled_meetings': cancelled,
        'completion_rate': (completed / total * 100) if total > 0 else 0,
        'cancellation_rate': (cancelled / total * 100) if total > 0 else 0,
        'average_duration_minutes': round(avg_duration, 1),
        'average_attendance_rate': round(avg_attendance, 1),
        'average_effectiveness': round(avg_effectiveness, 1),
        'total_meeting_hours': round(total_hours, 1),
        'meetings_per_week': round(total / 52, 1) if total > 0 else 0,
        'type_distribution': type_distribution,
        'format_distribution': format_distribution,
        'status_breakdown': {
            'scheduled': len([m for m in meetings if m.status == MeetingStatus.SCHEDULED]),
            'completed': completed,
            'cancelled': cancelled,
            'in_progress': len([m for m in meetings if m.status == MeetingStatus.IN_PROGRESS]),
            'rescheduled': len([m for m in meetings if m.status == MeetingStatus.RESCHEDULED])
        }
    }


def get_user_meeting_metrics(user_id: int, date_from: date = None, date_to: date = None) -> dict[str, Any]:
    """Obtener métricas de reuniones para un usuario"""
    query = Meeting.query.filter(
        (Meeting.organizer_id == user_id) | (Meeting.participants.any(id=user_id)),
        Meeting.is_deleted == False
    )
    
    if date_from:
        query = query.filter(Meeting.scheduled_start >= datetime.combine(date_from, datetime.min.time()))
    
    if date_to:
        query = query.filter(Meeting.scheduled_start <= datetime.combine(date_to, datetime.max.time()))
    
    meetings = query.all()
    organized_meetings = [m for m in meetings if m.organizer_id == user_id]
    
    if not meetings:
        return {'error': 'No meetings found for user'}
    
    # Métricas básicas
    total_meetings = len(meetings)
    meetings_organized = len(organized_meetings)
    meetings_attended = total_meetings - meetings_organized
    
    # Tiempo en reuniones
    total_minutes = sum(m.actual_duration_minutes or m.duration_minutes for m in meetings)
    total_hours = total_minutes / 60
    
    # Distribución por tipo
    type_counts = {}
    for meeting in meetings:
        meeting_type = meeting.meeting_type.value
        type_counts[meeting_type] = type_counts.get(meeting_type, 0) + 1
    
    # Efectividad como organizador
    organized_effectiveness = []
    for meeting in organized_meetings:
        if meeting.effectiveness_score:
            organized_effectiveness.append(meeting.effectiveness_score)
    
    avg_effectiveness = sum(organized_effectiveness) / len(organized_effectiveness) if organized_effectiveness else 0
    
    return {
        'user_id': user_id,
        'total_meetings': total_meetings,
        'meetings_organized': meetings_organized,
        'meetings_attended': meetings_attended,
        'total_hours_in_meetings': round(total_hours, 1),
        'average_meetings_per_week': round(total_meetings / 52, 1) if total_meetings > 0 else 0,
        'average_meeting_duration': round(total_minutes / total_meetings, 1) if total_meetings > 0 else 0,
        'meeting_types': type_counts,
        'organization_effectiveness': {
            'average_effectiveness_score': round(avg_effectiveness, 1),
            'meetings_with_effectiveness_data': len(organized_effectiveness),
            'high_effectiveness_meetings': len([s for s in organized_effectiveness if s >= 80])
        },
        'productivity_insights': {
            'time_in_meetings_per_day': round(total_hours / 365, 2) if total_hours > 0 else 0,
            'organization_ratio': round(meetings_organized / total_meetings * 100, 1) if total_meetings > 0 else 0
        }
    }