"""
Modelo Mentoría del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de mentoría, incluyendo relaciones
mentor-mentee, sesiones, seguimiento de progreso y evaluaciones.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Time
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
from decimal import Decimal

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    MENTORSHIP_STATUS,
    SESSION_TYPES,
    SESSION_STATUS,
    FEEDBACK_RATINGS,
    EXPERTISE_AREAS,
    MENTORSHIP_GOALS,
    COMMUNICATION_PREFERENCES
)
from ..core.exceptions import ValidationError


class MentorshipStatus(Enum):
    """Estados de la relación de mentoría"""
    REQUESTED = "requested"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SessionType(Enum):
    """Tipos de sesión de mentoría"""
    ONE_ON_ONE = "one_on_one"
    GROUP = "group"
    WORKSHOP = "workshop"
    REVIEW = "review"
    GOAL_SETTING = "goal_setting"
    PROGRESS_CHECK = "progress_check"
    PITCH_PRACTICE = "pitch_practice"
    STRATEGIC_PLANNING = "strategic_planning"
    PROBLEM_SOLVING = "problem_solving"
    NETWORKING = "networking"
    SKILLS_DEVELOPMENT = "skills_development"
    FEEDBACK_SESSION = "feedback_session"


class SessionStatus(Enum):
    """Estados de sesión"""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class SessionFormat(Enum):
    """Formato de sesión"""
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    PHONE_CALL = "phone_call"
    EMAIL = "email"
    CHAT = "chat"
    HYBRID = "hybrid"


class FeedbackRating(Enum):
    """Calificaciones de feedback"""
    EXCELLENT = "excellent"
    VERY_GOOD = "very_good"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class GoalStatus(Enum):
    """Estados de objetivos de mentoría"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class MentorshipRelationship(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo de Relación de Mentoría
    
    Representa la relación ongoing entre un mentor (ally) y un mentee (entrepreneur),
    incluyendo objetivos, duración, términos y seguimiento general.
    """
    
    __tablename__ = 'mentorship_relationships'
    
    # Participantes
    mentor_id = Column(Integer, ForeignKey('allies.id'), nullable=False, index=True)
    mentor = relationship("Ally", back_populates="mentorship_relationships", foreign_keys=[mentor_id])
    
    mentee_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=False, index=True)
    mentee = relationship("Entrepreneur", back_populates="mentorship_relationships", foreign_keys=[mentee_id])
    
    # Estado y configuración
    status = Column(SQLEnum(MentorshipStatus), default=MentorshipStatus.REQUESTED, index=True)
    
    # Fechas importantes
    start_date = Column(Date)
    end_date = Column(Date)
    expected_duration_months = Column(Integer, default=6)  # Duración esperada en meses
    
    # Objetivos y enfoque
    primary_goals = Column(JSON)  # Lista de objetivos principales
    success_metrics = Column(JSON)  # Métricas de éxito
    focus_areas = Column(JSON)  # Áreas de enfoque (technical, business, leadership, etc.)
    expertise_needed = Column(JSON)  # Expertise específica requerida
    
    # Términos y expectativas
    frequency = Column(String(50), default='bi_weekly')  # weekly, bi_weekly, monthly
    session_duration_minutes = Column(Integer, default=60)
    preferred_format = Column(SQLEnum(SessionFormat), default=SessionFormat.VIDEO_CALL)
    
    # Contexto del proyecto
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    # Organización facilitadora
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    # Progreso y métricas
    total_sessions_planned = Column(Integer, default=0)
    total_sessions_completed = Column(Integer, default=0)
    total_hours_completed = Column(Float, default=0.0)
    
    # Evaluaciones y feedback
    mentor_satisfaction = Column(Float)  # 1-5 rating
    mentee_satisfaction = Column(Float)  # 1-5 rating
    overall_rating = Column(Float)  # 1-5 rating promedio
    
    # Resultados y impacto
    goals_achieved = Column(Integer, default=0)
    impact_summary = Column(Text)
    
    # Configuración y preferencias
    communication_preferences = Column(JSON)  # Preferencias de comunicación
    timezone = Column(String(50), default='UTC')
    language = Column(String(10), default='es')
    
    # Notas y observaciones
    mentor_notes = Column(Text)  # Notas privadas del mentor
    mentee_notes = Column(Text)  # Notas privadas del mentee
    coordinator_notes = Column(Text)  # Notas del coordinador/organización
    
    # Configuración personalizada
    custom_fields = Column(JSON)
    tags = Column(JSON)  # Tags para categorización
    
    # Relaciones
    sessions = relationship("MentorshipSession", back_populates="mentorship")
    goals = relationship("MentorshipGoal", back_populates="mentorship")
    evaluations = relationship("MentorshipEvaluation", back_populates="mentorship")
    activities = relationship("ActivityLog", back_populates="mentorship")
    
    def __init__(self, **kwargs):
        """Inicialización de la relación de mentoría"""
        super().__init__(**kwargs)
        
        # Configurar fecha de fin por defecto
        if not self.end_date and self.start_date and self.expected_duration_months:
            self.end_date = self.start_date + timedelta(days=self.expected_duration_months * 30)
        
        # Configuraciones por defecto
        if not self.communication_preferences:
            self.communication_preferences = {
                'email_notifications': True,
                'sms_reminders': False,
                'calendar_invites': True,
                'progress_reports': True
            }
    
    def __repr__(self):
        return f'<MentorshipRelationship {self.mentor.full_name if self.mentor else "N/A"} -> {self.mentee.full_name if self.mentee else "N/A"}>'
    
    def __str__(self):
        return f'{self.mentor.full_name if self.mentor else "Mentor"} mentoring {self.mentee.full_name if self.mentee else "Mentee"} ({self.status.value})'
    
    # Validaciones
    @validates('expected_duration_months')
    def validate_duration(self, key, duration):
        """Validar duración esperada"""
        if duration is not None:
            if duration < 1 or duration > 24:  # Entre 1 mes y 2 años
                raise ValidationError("La duración debe estar entre 1 y 24 meses")
        return duration
    
    @validates('session_duration_minutes')
    def validate_session_duration(self, key, duration):
        """Validar duración de sesión"""
        if duration is not None:
            if duration < 15 or duration > 240:  # Entre 15 minutos y 4 horas
                raise ValidationError("La duración de sesión debe estar entre 15 y 240 minutos")
        return duration
    
    @validates('start_date', 'end_date')
    def validate_dates(self, key, date_value):
        """Validar fechas"""
        if date_value:
            if key == 'end_date' and self.start_date:
                if date_value <= self.start_date:
                    raise ValidationError("La fecha de fin debe ser posterior al inicio")
        return date_value
    
    @validates('mentor_satisfaction', 'mentee_satisfaction', 'overall_rating')
    def validate_ratings(self, key, rating):
        """Validar calificaciones"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("Las calificaciones deben estar entre 1 y 5")
        return rating
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si la mentoría está activa"""
        return self.status == MentorshipStatus.ACTIVE and not self.is_deleted
    
    @hybrid_property
    def duration_in_days(self):
        """Duración en días"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @hybrid_property
    def days_remaining(self):
        """Días restantes"""
        if self.end_date and self.is_active:
            remaining = (self.end_date - date.today()).days
            return max(0, remaining)
        return 0
    
    @hybrid_property
    def completion_rate(self):
        """Tasa de finalización de sesiones"""
        if self.total_sessions_planned > 0:
            return (self.total_sessions_completed / self.total_sessions_planned) * 100
        return 0
    
    @hybrid_property
    def is_overdue(self):
        """Verificar si está vencida"""
        return (self.end_date and 
                self.end_date < date.today() and 
                self.status == MentorshipStatus.ACTIVE)
    
    @hybrid_property
    def progress_percentage(self):
        """Porcentaje de progreso general"""
        if not self.start_date or not self.end_date:
            return 0
        
        total_days = (self.end_date - self.start_date).days
        if total_days <= 0:
            return 100
        
        elapsed_days = (date.today() - self.start_date).days
        elapsed_days = max(0, min(elapsed_days, total_days))
        
        return (elapsed_days / total_days) * 100
    
    # Métodos de negocio
    def approve(self, approver_notes: str = None):
        """Aprobar la relación de mentoría"""
        if self.status != MentorshipStatus.REQUESTED:
            raise ValidationError("Solo se pueden aprobar solicitudes pendientes")
        
        self.status = MentorshipStatus.ACTIVE
        self.start_date = date.today()
        
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.expected_duration_months * 30)
        
        # Log de aprobación
        self._log_status_change('approved', approver_notes)
    
    def pause(self, reason: str = None):
        """Pausar la mentoría"""
        if self.status != MentorshipStatus.ACTIVE:
            raise ValidationError("Solo se pueden pausar mentorías activas")
        
        self.status = MentorshipStatus.PAUSED
        self._log_status_change('paused', reason)
    
    def resume(self, notes: str = None):
        """Reanudar la mentoría"""
        if self.status != MentorshipStatus.PAUSED:
            raise ValidationError("Solo se pueden reanudar mentorías pausadas")
        
        self.status = MentorshipStatus.ACTIVE
        # Extender fecha de fin si es necesario
        if self.end_date and self.end_date < date.today():
            self.end_date = date.today() + timedelta(days=30)  # Extender un mes
        
        self._log_status_change('resumed', notes)
    
    def complete(self, completion_notes: str = None, impact_summary: str = None):
        """Completar la mentoría"""
        if self.status not in [MentorshipStatus.ACTIVE, MentorshipStatus.PAUSED]:
            raise ValidationError("Solo se pueden completar mentorías activas o pausadas")
        
        self.status = MentorshipStatus.COMPLETED
        if impact_summary:
            self.impact_summary = impact_summary
        
        # Calcular métricas finales
        self._calculate_final_metrics()
        self._log_status_change('completed', completion_notes)
    
    def cancel(self, reason: str = None):
        """Cancelar la mentoría"""
        if self.status in [MentorshipStatus.COMPLETED, MentorshipStatus.CANCELLED]:
            raise ValidationError("No se puede cancelar una mentoría ya finalizada")
        
        self.status = MentorshipStatus.CANCELLED
        self._log_status_change('cancelled', reason)
    
    def _log_status_change(self, action: str, notes: str = None):
        """Registrar cambio de estado"""
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type='mentorship_status_change',
            description=f"Mentoría {action}",
            metadata={
                'action': action,
                'old_status': self.status.value,
                'notes': notes
            },
            mentorship_id=self.id,
            user_id=self.mentor.user_id if self.mentor else None
        )
        
        db.session.add(activity)
    
    def schedule_session(self, session_type: SessionType, scheduled_datetime: datetime,
                        duration_minutes: int = None, notes: str = None) -> 'MentorshipSession':
        """Programar una sesión"""
        from .. import db
        
        session = MentorshipSession(
            mentorship_id=self.id,
            session_type=session_type,
            scheduled_datetime=scheduled_datetime,
            duration_minutes=duration_minutes or self.session_duration_minutes,
            format=self.preferred_format,
            notes=notes
        )
        
        db.session.add(session)
        self.total_sessions_planned += 1
        
        return session
    
    def add_goal(self, title: str, description: str = None, 
                target_date: date = None, metrics: dict[str, Any] = None) -> 'MentorshipGoal':
        """Agregar objetivo de mentoría"""
        from .. import db
        
        goal = MentorshipGoal(
            mentorship_id=self.id,
            title=title,
            description=description,
            target_date=target_date,
            success_metrics=metrics or {}
        )
        
        db.session.add(goal)
        return goal
    
    def update_satisfaction_ratings(self, mentor_rating: float = None, 
                                  mentee_rating: float = None):
        """Actualizar calificaciones de satisfacción"""
        if mentor_rating:
            self.mentor_satisfaction = mentor_rating
        if mentee_rating:
            self.mentee_satisfaction = mentee_rating
        
        # Calcular rating general
        ratings = []
        if self.mentor_satisfaction:
            ratings.append(self.mentor_satisfaction)
        if self.mentee_satisfaction:
            ratings.append(self.mentee_satisfaction)
        
        if ratings:
            self.overall_rating = sum(ratings) / len(ratings)
    
    def _calculate_final_metrics(self):
        """Calcular métricas finales"""
        # Actualizar total de horas
        total_minutes = sum(session.actual_duration_minutes or session.duration_minutes 
                          for session in self.sessions 
                          if session.status == SessionStatus.COMPLETED)
        self.total_hours_completed = total_minutes / 60.0
        
        # Contar objetivos logrados
        self.goals_achieved = len([goal for goal in self.goals 
                                 if goal.status == GoalStatus.COMPLETED])
    
    def get_progress_summary(self) -> dict[str, Any]:
        """Obtener resumen de progreso"""
        completed_sessions = [s for s in self.sessions if s.status == SessionStatus.COMPLETED]
        pending_sessions = [s for s in self.sessions if s.status == SessionStatus.SCHEDULED]
        
        return {
            'status': self.status.value,
            'progress_percentage': self.progress_percentage,
            'days_remaining': self.days_remaining,
            'sessions': {
                'completed': len(completed_sessions),
                'planned': self.total_sessions_planned,
                'pending': len(pending_sessions),
                'completion_rate': self.completion_rate
            },
            'goals': {
                'total': len(self.goals),
                'completed': self.goals_achieved,
                'in_progress': len([g for g in self.goals if g.status == GoalStatus.IN_PROGRESS])
            },
            'hours_completed': self.total_hours_completed,
            'satisfaction': {
                'mentor': self.mentor_satisfaction,
                'mentee': self.mentee_satisfaction,
                'overall': self.overall_rating
            }
        }
    
    def get_dashboard_data(self) -> dict[str, Any]:
        """Generar datos para dashboard"""
        recent_sessions = (self.sessions
                         .order_by(MentorshipSession.scheduled_datetime.desc())
                         .limit(5)
                         .all())
        
        upcoming_sessions = (self.sessions
                           .filter(MentorshipSession.scheduled_datetime > datetime.now(timezone.utc))
                           .filter(MentorshipSession.status == SessionStatus.SCHEDULED)
                           .order_by(MentorshipSession.scheduled_datetime.asc())
                           .limit(3)
                           .all())
        
        return {
            'relationship_info': {
                'mentor': self.mentor.full_name if self.mentor else None,
                'mentee': self.mentee.full_name if self.mentee else None,
                'status': self.status.value,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'progress': self.progress_percentage,
                'focus_areas': self.focus_areas
            },
            'metrics': self.get_progress_summary(),
            'recent_sessions': [
                {
                    'id': session.id,
                    'type': session.session_type.value,
                    'date': session.scheduled_datetime.isoformat(),
                    'status': session.status.value,
                    'duration': session.actual_duration_minutes or session.duration_minutes
                }
                for session in recent_sessions
            ],
            'upcoming_sessions': [
                {
                    'id': session.id,
                    'type': session.session_type.value,
                    'date': session.scheduled_datetime.isoformat(),
                    'duration': session.duration_minutes
                }
                for session in upcoming_sessions
            ],
            'active_goals': [
                {
                    'id': goal.id,
                    'title': goal.title,
                    'status': goal.status.value,
                    'target_date': goal.target_date.isoformat() if goal.target_date else None
                }
                for goal in self.goals if goal.status in [GoalStatus.PENDING, GoalStatus.IN_PROGRESS]
            ]
        }
    
    # Métodos de búsqueda
    @classmethod
    def get_active_relationships(cls):
        """Obtener relaciones activas"""
        return cls.query.filter(
            cls.status == MentorshipStatus.ACTIVE,
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def get_by_mentor(cls, mentor_id: int):
        """Obtener mentorías por mentor"""
        return cls.query.filter(
            cls.mentor_id == mentor_id,
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def get_by_mentee(cls, mentee_id: int):
        """Obtener mentorías por mentee"""
        return cls.query.filter(
            cls.mentee_id == mentee_id,
            cls.is_deleted == False
        ).all()
    
    def to_dict(self, include_sensitive=False) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'mentor_id': self.mentor_id,
            'mentee_id': self.mentee_id,
            'status': self.status.value,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'expected_duration_months': self.expected_duration_months,
            'primary_goals': self.primary_goals,
            'focus_areas': self.focus_areas,
            'frequency': self.frequency,
            'session_duration_minutes': self.session_duration_minutes,
            'preferred_format': self.preferred_format.value,
            'total_sessions_completed': self.total_sessions_completed,
            'total_hours_completed': self.total_hours_completed,
            'overall_rating': self.overall_rating,
            'progress_percentage': self.progress_percentage,
            'days_remaining': self.days_remaining,
            'completion_rate': self.completion_rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'mentor_satisfaction': self.mentor_satisfaction,
                'mentee_satisfaction': self.mentee_satisfaction,
                'mentor_notes': self.mentor_notes,
                'mentee_notes': self.mentee_notes,
                'coordinator_notes': self.coordinator_notes,
                'impact_summary': self.impact_summary,
                'communication_preferences': self.communication_preferences,
                'custom_fields': self.custom_fields
            })
        
        return data


class MentorshipSession(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Sesión de Mentoría
    
    Representa sesiones individuales entre mentor y mentee,
    con seguimiento detallado y evaluación.
    """
    
    __tablename__ = 'mentorship_sessions'
    
    # Relación con mentoría
    mentorship_id = Column(Integer, ForeignKey('mentorship_relationships.id'), nullable=False, index=True)
    mentorship = relationship("MentorshipRelationship", back_populates="sessions")
    
    # Información de la sesión
    session_type = Column(SQLEnum(SessionType), default=SessionType.ONE_ON_ONE)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.SCHEDULED, index=True)
    
    # Fechas y duración
    scheduled_datetime = Column(DateTime, nullable=False, index=True)
    actual_start_time = Column(DateTime)
    actual_end_time = Column(DateTime)
    duration_minutes = Column(Integer, default=60)
    actual_duration_minutes = Column(Integer)
    
    # Formato y ubicación
    format = Column(SQLEnum(SessionFormat), default=SessionFormat.VIDEO_CALL)
    location = Column(String(300))  # Dirección física o URL de reunión
    meeting_url = Column(String(500))
    meeting_password = Column(String(100))
    
    # Contenido y objetivos
    agenda = Column(JSON)  # Agenda de la sesión
    objectives = Column(JSON)  # Objetivos específicos
    topics_covered = Column(JSON)  # Temas cubiertos
    
    # Preparación
    pre_session_materials = Column(JSON)  # Materiales de preparación
    homework_assigned = Column(JSON)  # Tareas asignadas
    homework_completed = Column(Boolean)
    
    # Seguimiento y resultados
    key_takeaways = Column(JSON)  # Puntos clave
    action_items = Column(JSON)  # Elementos de acción
    next_steps = Column(Text)  # Próximos pasos
    
    # Evaluación y feedback
    mentor_feedback = Column(Text)
    mentee_feedback = Column(Text)
    session_rating = Column(Float)  # Calificación de la sesión (1-5)
    
    # Recursos y materiales
    documents_shared = Column(JSON)  # Documentos compartidos
    resources_recommended = Column(JSON)  # Recursos recomendados
    recording_url = Column(String(500))  # URL de grabación si aplica
    
    # Notas y observaciones
    mentor_notes = Column(Text)  # Notas privadas del mentor
    mentee_notes = Column(Text)  # Notas privadas del mentee
    session_summary = Column(Text)  # Resumen de la sesión
    
    # Seguimiento de asistencia
    mentor_attended = Column(Boolean, default=True)
    mentee_attended = Column(Boolean, default=True)
    late_cancellation = Column(Boolean, default=False)
    cancellation_reason = Column(String(500))
    
    # Reprogramación
    original_datetime = Column(DateTime)  # Fecha/hora original si fue reprogramada
    reschedule_count = Column(Integer, default=0)
    reschedule_reason = Column(String(500))
    
    def __init__(self, **kwargs):
        """Inicialización de la sesión"""
        super().__init__(**kwargs)
        
        # Configurar duración por defecto si no se especifica
        if not self.duration_minutes and self.mentorship:
            self.duration_minutes = self.mentorship.session_duration_minutes
    
    def __repr__(self):
        return f'<MentorshipSession {self.session_type.value} - {self.scheduled_datetime}>'
    
    def __str__(self):
        return f'{self.session_type.value} session on {self.scheduled_datetime.strftime("%Y-%m-%d %H:%M")}'
    
    # Validaciones
    @validates('duration_minutes', 'actual_duration_minutes')
    def validate_duration(self, key, duration):
        """Validar duración"""
        if duration is not None:
            if duration < 5 or duration > 480:  # Entre 5 minutos y 8 horas
                raise ValidationError("La duración debe estar entre 5 y 480 minutos")
        return duration
    
    @validates('session_rating')
    def validate_rating(self, key, rating):
        """Validar calificación"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("La calificación debe estar entre 1 y 5")
        return rating
    
    @validates('scheduled_datetime')
    def validate_scheduled_datetime(self, key, scheduled_dt):
        """Validar fecha programada"""
        if scheduled_dt and scheduled_dt < datetime.now(timezone.utc):
            # Solo permitir fechas pasadas si es una actualización
            if not self.id:
                raise ValidationError("No se pueden programar sesiones en el pasado")
        return scheduled_dt
    
    # Propiedades híbridas
    @hybrid_property
    def is_upcoming(self):
        """Verificar si la sesión es próxima"""
        return (self.scheduled_datetime > datetime.now(timezone.utc) and 
                self.status == SessionStatus.SCHEDULED)
    
    @hybrid_property
    def is_overdue(self):
        """Verificar si la sesión está vencida"""
        return (self.scheduled_datetime < datetime.now(timezone.utc) and 
                self.status == SessionStatus.SCHEDULED)
    
    @hybrid_property
    def duration_actual_or_planned(self):
        """Duración real o planificada"""
        return self.actual_duration_minutes or self.duration_minutes
    
    @hybrid_property
    def was_completed_on_time(self):
        """Verificar si se completó a tiempo"""
        if self.status == SessionStatus.COMPLETED and self.actual_start_time:
            # Considerar "a tiempo" si empezó dentro de 15 minutos de la hora programada
            time_diff = abs((self.actual_start_time - self.scheduled_datetime).total_seconds())
            return time_diff <= 900  # 15 minutos
        return False
    
    @hybrid_property
    def attendance_summary(self):
        """Resumen de asistencia"""
        if self.mentor_attended and self.mentee_attended:
            return "Both attended"
        elif self.mentor_attended:
            return "Mentor only"
        elif self.mentee_attended:
            return "Mentee only"
        else:
            return "No show"
    
    # Métodos de negocio
    def start_session(self):
        """Iniciar la sesión"""
        if self.status != SessionStatus.SCHEDULED:
            raise ValidationError("Solo se pueden iniciar sesiones programadas")
        
        self.status = SessionStatus.IN_PROGRESS
        self.actual_start_time = datetime.now(timezone.utc)
    
    def complete_session(self, session_summary: str = None, action_items: list[str] = None,
                        mentor_feedback: str = None, session_rating: float = None):
        """Completar la sesión"""
        if self.status != SessionStatus.IN_PROGRESS:
            raise ValidationError("Solo se pueden completar sesiones en progreso")
        
        self.status = SessionStatus.COMPLETED
        self.actual_end_time = datetime.now(timezone.utc)
        
        if self.actual_start_time:
            duration = (self.actual_end_time - self.actual_start_time).total_seconds() / 60
            self.actual_duration_minutes = int(duration)
        
        if session_summary:
            self.session_summary = session_summary
        if action_items:
            self.action_items = action_items
        if mentor_feedback:
            self.mentor_feedback = mentor_feedback
        if session_rating:
            self.session_rating = session_rating
        
        # Actualizar contador en la relación de mentoría
        self.mentorship.total_sessions_completed += 1
    
    def cancel_session(self, reason: str, late_cancellation: bool = False):
        """Cancelar la sesión"""
        if self.status in [SessionStatus.COMPLETED, SessionStatus.CANCELLED]:
            raise ValidationError("No se puede cancelar una sesión ya finalizada")
        
        self.status = SessionStatus.CANCELLED
        self.cancellation_reason = reason
        self.late_cancellation = late_cancellation
    
    def reschedule_session(self, new_datetime: datetime, reason: str = None):
        """Reprogramar la sesión"""
        if self.status not in [SessionStatus.SCHEDULED, SessionStatus.CONFIRMED]:
            raise ValidationError("Solo se pueden reprogramar sesiones programadas o confirmadas")
        
        # Guardar fecha original si es la primera reprogramación
        if self.reschedule_count == 0:
            self.original_datetime = self.scheduled_datetime
        
        self.scheduled_datetime = new_datetime
        self.reschedule_count += 1
        self.reschedule_reason = reason
        self.status = SessionStatus.RESCHEDULED
    
    def mark_no_show(self, mentor_attended: bool = False, mentee_attended: bool = False):
        """Marcar como no asistencia"""
        self.status = SessionStatus.NO_SHOW
        self.mentor_attended = mentor_attended
        self.mentee_attended = mentee_attended
    
    def confirm_session(self):
        """Confirmar la sesión"""
        if self.status != SessionStatus.SCHEDULED:
            raise ValidationError("Solo se pueden confirmar sesiones programadas")
        
        self.status = SessionStatus.CONFIRMED
    
    def add_homework(self, title: str, description: str, due_date: date = None):
        """Agregar tarea"""
        if not self.homework_assigned:
            self.homework_assigned = []
        
        homework = {
            'title': title,
            'description': description,
            'due_date': due_date.isoformat() if due_date else None,
            'assigned_at': datetime.now(timezone.utc).isoformat(),
            'completed': False
        }
        
        self.homework_assigned.append(homework)
    
    def add_action_item(self, description: str, assignee: str, due_date: date = None):
        """Agregar elemento de acción"""
        if not self.action_items:
            self.action_items = []
        
        action_item = {
            'description': description,
            'assignee': assignee,  # 'mentor' or 'mentee'
            'due_date': due_date.isoformat() if due_date else None,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'completed': False
        }
        
        self.action_items.append(action_item)
    
    def get_session_analytics(self) -> dict[str, Any]:
        """Obtener analytics de la sesión"""
        return {
            'basic_info': {
                'type': self.session_type.value,
                'status': self.status.value,
                'format': self.format.value,
                'scheduled_date': self.scheduled_datetime.isoformat(),
                'duration_planned': self.duration_minutes,
                'duration_actual': self.actual_duration_minutes
            },
            'attendance': {
                'mentor_attended': self.mentor_attended,
                'mentee_attended': self.mentee_attended,
                'was_on_time': self.was_completed_on_time,
                'summary': self.attendance_summary
            },
            'content': {
                'topics_covered_count': len(self.topics_covered) if self.topics_covered else 0,
                'action_items_count': len(self.action_items) if self.action_items else 0,
                'homework_assigned': len(self.homework_assigned) if self.homework_assigned else 0,
                'resources_shared': len(self.resources_recommended) if self.resources_recommended else 0
            },
            'feedback': {
                'session_rating': self.session_rating,
                'has_mentor_feedback': bool(self.mentor_feedback),
                'has_mentee_feedback': bool(self.mentee_feedback),
                'has_recording': bool(self.recording_url)
            },
            'rescheduling': {
                'reschedule_count': self.reschedule_count,
                'was_rescheduled': self.reschedule_count > 0,
                'late_cancellation': self.late_cancellation
            }
        }
    
    # Métodos de búsqueda
    @classmethod
    def get_upcoming_sessions(cls, days_ahead: int = 7):
        """Obtener sesiones próximas"""
        end_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        return cls.query.filter(
            cls.scheduled_datetime.between(datetime.now(timezone.utc), end_date),
            cls.status == SessionStatus.SCHEDULED
        ).order_by(cls.scheduled_datetime.asc()).all()
    
    @classmethod
    def get_overdue_sessions(cls):
        """Obtener sesiones vencidas"""
        return cls.query.filter(
            cls.scheduled_datetime < datetime.now(timezone.utc),
            cls.status == SessionStatus.SCHEDULED
        ).all()
    
    def to_dict(self, include_sensitive=False) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'mentorship_id': self.mentorship_id,
            'session_type': self.session_type.value,
            'status': self.status.value,
            'scheduled_datetime': self.scheduled_datetime.isoformat(),
            'duration_minutes': self.duration_minutes,
            'actual_duration_minutes': self.actual_duration_minutes,
            'format': self.format.value,
            'location': self.location,
            'objectives': self.objectives,
            'topics_covered': self.topics_covered,
            'key_takeaways': self.key_takeaways,
            'action_items': self.action_items,
            'session_rating': self.session_rating,
            'mentor_attended': self.mentor_attended,
            'mentee_attended': self.mentee_attended,
            'attendance_summary': self.attendance_summary,
            'is_upcoming': self.is_upcoming,
            'is_overdue': self.is_overdue,
            'reschedule_count': self.reschedule_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_sensitive:
            data.update({
                'meeting_url': self.meeting_url,
                'meeting_password': self.meeting_password,
                'mentor_feedback': self.mentor_feedback,
                'mentee_feedback': self.mentee_feedback,
                'mentor_notes': self.mentor_notes,
                'mentee_notes': self.mentee_notes,
                'session_summary': self.session_summary,
                'homework_assigned': self.homework_assigned,
                'homework_completed': self.homework_completed,
                'documents_shared': self.documents_shared,
                'resources_recommended': self.resources_recommended,
                'recording_url': self.recording_url,
                'cancellation_reason': self.cancellation_reason,
                'reschedule_reason': self.reschedule_reason
            })
        
        return data


class MentorshipGoal(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Objetivo de Mentoría
    
    Representa objetivos específicos establecidos en la relación de mentoría.
    """
    
    __tablename__ = 'mentorship_goals'
    
    # Relación con mentoría
    mentorship_id = Column(Integer, ForeignKey('mentorship_relationships.id'), nullable=False, index=True)
    mentorship = relationship("MentorshipRelationship", back_populates="goals")
    
    # Información del objetivo
    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # technical, business, leadership, personal, etc.
    
    # Estado y fechas
    status = Column(SQLEnum(GoalStatus), default=GoalStatus.PENDING, index=True)
    target_date = Column(Date)
    completed_at = Column(DateTime)
    
    # Métricas de éxito
    success_metrics = Column(JSON)  # Métricas específicas para medir el éxito
    current_progress = Column(Float, default=0.0)  # Progreso actual (0-100%)
    
    # Seguimiento
    milestones = Column(JSON)  # Hitos intermedios
    progress_notes = Column(Text)  # Notas de progreso
    completion_evidence = Column(JSON)  # Evidencia de completitud
    
    # Evaluación
    mentor_assessment = Column(Text)  # Evaluación del mentor
    mentee_reflection = Column(Text)  # Reflexión del mentee
    achievement_rating = Column(Float)  # Calificación de logro (1-5)
    
    def __repr__(self):
        return f'<MentorshipGoal {self.title} - {self.status.value}>'
    
    # Validaciones
    @validates('current_progress')
    def validate_progress(self, key, progress):
        """Validar progreso"""
        if progress is not None:
            if progress < 0 or progress > 100:
                raise ValidationError("El progreso debe estar entre 0 y 100")
        return progress
    
    @validates('achievement_rating')
    def validate_rating(self, key, rating):
        """Validar calificación"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("La calificación debe estar entre 1 y 5")
        return rating
    
    # Propiedades híbridas
    @hybrid_property
    def is_overdue(self):
        """Verificar si está vencido"""
        return (self.target_date and 
                self.target_date < date.today() and 
                self.status != GoalStatus.COMPLETED)
    
    @hybrid_property
    def days_until_due(self):
        """Días hasta vencimiento"""
        if self.target_date:
            return (self.target_date - date.today()).days
        return None
    
    # Métodos de negocio
    def update_progress(self, progress: float, notes: str = None):
        """Actualizar progreso"""
        if progress < 0 or progress > 100:
            raise ValidationError("El progreso debe estar entre 0 y 100")
        
        self.current_progress = progress
        if notes:
            self.progress_notes = notes
        
        # Cambiar estado basado en progreso
        if progress == 100:
            self.status = GoalStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)
        elif progress > 0:
            self.status = GoalStatus.IN_PROGRESS
    
    def complete(self, completion_evidence: dict[str, Any] = None, 
                mentor_assessment: str = None, achievement_rating: float = None):
        """Completar el objetivo"""
        self.status = GoalStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.current_progress = 100.0
        
        if completion_evidence:
            self.completion_evidence = completion_evidence
        if mentor_assessment:
            self.mentor_assessment = mentor_assessment
        if achievement_rating:
            self.achievement_rating = achievement_rating
    
    def postpone(self, new_target_date: date, reason: str = None):
        """Posponer el objetivo"""
        self.status = GoalStatus.POSTPONED
        self.target_date = new_target_date
        if reason:
            self.progress_notes = f"Pospuesto: {reason}"
    
    def cancel(self, reason: str = None):
        """Cancelar el objetivo"""
        self.status = GoalStatus.CANCELLED
        if reason:
            self.progress_notes = f"Cancelado: {reason}"
    
    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'status': self.status.value,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'current_progress': self.current_progress,
            'success_metrics': self.success_metrics,
            'milestones': self.milestones,
            'progress_notes': self.progress_notes,
            'achievement_rating': self.achievement_rating,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MentorshipEvaluation(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Evaluación de Mentoría
    
    Representa evaluaciones periódicas de la relación de mentoría.
    """
    
    __tablename__ = 'mentorship_evaluations'
    
    # Relación con mentoría
    mentorship_id = Column(Integer, ForeignKey('mentorship_relationships.id'), nullable=False, index=True)
    mentorship = relationship("MentorshipRelationship", back_populates="evaluations")
    
    # Información de la evaluación
    evaluation_type = Column(String(50), default='periodic')  # periodic, mid_term, final
    evaluation_date = Column(Date, default=date.today)
    evaluator_type = Column(String(20))  # mentor, mentee, coordinator, mutual
    
    # Evaluador
    evaluator_id = Column(Integer, ForeignKey('users.id'))
    evaluator = relationship("User")
    
    # Calificaciones (1-5 escala)
    relationship_quality = Column(Float)
    goal_achievement = Column(Float)
    communication_effectiveness = Column(Float)
    mentor_expertise = Column(Float)
    mentee_engagement = Column(Float)
    session_quality = Column(Float)
    overall_satisfaction = Column(Float)
    
    # Feedback cualitativo
    strengths = Column(Text)
    areas_for_improvement = Column(Text)
    specific_feedback = Column(Text)
    recommendations = Column(Text)
    
    # Progreso y logros
    key_achievements = Column(JSON)
    challenges_faced = Column(JSON)
    lessons_learned = Column(Text)
    
    # Futuro de la relación
    continue_relationship = Column(Boolean)
    suggested_changes = Column(Text)
    additional_resources_needed = Column(JSON)
    
    def __repr__(self):
        return f'<MentorshipEvaluation {self.evaluation_type} - {self.evaluation_date}>'
    
    # Validaciones
    @validates('relationship_quality', 'goal_achievement', 'communication_effectiveness',
              'mentor_expertise', 'mentee_engagement', 'session_quality', 'overall_satisfaction')
    def validate_ratings(self, key, rating):
        """Validar calificaciones"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("Las calificaciones deben estar entre 1 y 5")
        return rating
    
    # Propiedades híbridas
    @hybrid_property
    def average_rating(self):
        """Calificación promedio"""
        ratings = []
        for field in ['relationship_quality', 'goal_achievement', 'communication_effectiveness',
                     'mentor_expertise', 'mentee_engagement', 'session_quality', 'overall_satisfaction']:
            value = getattr(self, field)
            if value is not None:
                ratings.append(value)
        
        return sum(ratings) / len(ratings) if ratings else None
    
    def calculate_improvement_score(self, previous_evaluation: 'MentorshipEvaluation' = None) -> float:
        """Calcular puntuación de mejora"""
        if not previous_evaluation:
            return 0.0
        
        current_avg = self.average_rating
        previous_avg = previous_evaluation.average_rating
        
        if current_avg and previous_avg:
            return current_avg - previous_avg
        return 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'evaluation_type': self.evaluation_type,
            'evaluation_date': self.evaluation_date.isoformat(),
            'evaluator_type': self.evaluator_type,
            'ratings': {
                'relationship_quality': self.relationship_quality,
                'goal_achievement': self.goal_achievement,
                'communication_effectiveness': self.communication_effectiveness,
                'mentor_expertise': self.mentor_expertise,
                'mentee_engagement': self.mentee_engagement,
                'session_quality': self.session_quality,
                'overall_satisfaction': self.overall_satisfaction,
                'average': self.average_rating
            },
            'feedback': {
                'strengths': self.strengths,
                'areas_for_improvement': self.areas_for_improvement,
                'specific_feedback': self.specific_feedback,
                'recommendations': self.recommendations
            },
            'progress': {
                'key_achievements': self.key_achievements,
                'challenges_faced': self.challenges_faced,
                'lessons_learned': self.lessons_learned
            },
            'future': {
                'continue_relationship': self.continue_relationship,
                'suggested_changes': self.suggested_changes,
                'additional_resources_needed': self.additional_resources_needed
            },
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Funciones de utilidad para el módulo
def get_mentorship_statistics(organization_id: int = None, 
                             date_from: date = None, 
                             date_to: date = None) -> dict[str, Any]:
    """Obtener estadísticas de mentoría"""
    query = MentorshipRelationship.query
    
    if organization_id:
        query = query.filter(MentorshipRelationship.organization_id == organization_id)
    
    if date_from:
        query = query.filter(MentorshipRelationship.start_date >= date_from)
    
    if date_to:
        query = query.filter(MentorshipRelationship.start_date <= date_to)
    
    relationships = query.all()
    
    if not relationships:
        return {
            'total_relationships': 0,
            'active_relationships': 0,
            'completed_relationships': 0,
            'average_duration_days': 0,
            'total_sessions': 0,
            'average_satisfaction': 0,
            'success_rate': 0
        }
    
    # Calcular estadísticas
    total = len(relationships)
    active = len([r for r in relationships if r.status == MentorshipStatus.ACTIVE])
    completed = len([r for r in relationships if r.status == MentorshipStatus.COMPLETED])
    
    # Duración promedio
    durations = [r.duration_in_days for r in relationships if r.duration_in_days > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Sesiones totales
    total_sessions = sum(r.total_sessions_completed for r in relationships)
    
    # Satisfacción promedio
    satisfactions = [r.overall_rating for r in relationships if r.overall_rating]
    avg_satisfaction = sum(satisfactions) / len(satisfactions) if satisfactions else 0
    
    # Tasa de éxito (completadas exitosamente)
    success_rate = (completed / total) * 100 if total > 0 else 0
    
    return {
        'total_relationships': total,
        'active_relationships': active,
        'completed_relationships': completed,
        'cancelled_relationships': len([r for r in relationships if r.status == MentorshipStatus.CANCELLED]),
        'average_duration_days': round(avg_duration, 1),
        'total_sessions': total_sessions,
        'average_sessions_per_relationship': round(total_sessions / total, 1) if total > 0 else 0,
        'average_satisfaction': round(avg_satisfaction, 2),
        'success_rate': round(success_rate, 1),
        'status_breakdown': {
            'active': active,
            'completed': completed,
            'paused': len([r for r in relationships if r.status == MentorshipStatus.PAUSED]),
            'cancelled': len([r for r in relationships if r.status == MentorshipStatus.CANCELLED])
        }
    }


def get_mentor_performance_metrics(mentor_id: int) -> dict[str, Any]:
    """Obtener métricas de rendimiento de un mentor"""
    relationships = MentorshipRelationship.query.filter_by(mentor_id=mentor_id).all()
    
    if not relationships:
        return {'error': 'No mentorship relationships found'}
    
    # Métricas básicas
    total_mentees = len(relationships)
    active_mentees = len([r for r in relationships if r.status == MentorshipStatus.ACTIVE])
    completed_relationships = [r for r in relationships if r.status == MentorshipStatus.COMPLETED]
    
    # Satisfacción
    mentor_ratings = [r.mentor_satisfaction for r in relationships if r.mentor_satisfaction]
    avg_mentor_rating = sum(mentor_ratings) / len(mentor_ratings) if mentor_ratings else 0
    
    # Sesiones
    total_sessions = sum(r.total_sessions_completed for r in relationships)
    total_hours = sum(r.total_hours_completed for r in relationships)
    
    # Objetivos
    total_goals = sum(len(r.goals) for r in relationships)
    completed_goals = sum(r.goals_achieved for r in relationships)
    
    return {
        'mentor_id': mentor_id,
        'total_mentees': total_mentees,
        'active_mentees': active_mentees,
        'completed_relationships': len(completed_relationships),
        'success_rate': (len(completed_relationships) / total_mentees * 100) if total_mentees > 0 else 0,
        'average_satisfaction': round(avg_mentor_rating, 2),
        'total_sessions_delivered': total_sessions,
        'total_hours_mentoring': round(total_hours, 1),
        'average_sessions_per_mentee': round(total_sessions / total_mentees, 1) if total_mentees > 0 else 0,
        'goals_management': {
            'total_goals_set': total_goals,
            'goals_achieved': completed_goals,
            'goal_achievement_rate': (completed_goals / total_goals * 100) if total_goals > 0 else 0
        },
        'relationship_duration': {
            'average_days': sum(r.duration_in_days for r in completed_relationships) / len(completed_relationships) if completed_relationships else 0
        }
    }