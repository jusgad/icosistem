from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin, UserTrackingMixin
from app.core.exceptions import ValidationError


class MilestoneStatus(Enum):
    """Estados de hitos"""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    DELAYED = 'delayed'


class MilestonePriority(Enum):
    """Prioridades de hitos"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class Milestone(BaseModel, TimestampMixin, UserTrackingMixin):
    """Modelo base para hitos"""
    __tablename__ = 'milestones'
    __table_args__ = {'extend_existing': True}
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    status = db.Column(db.Enum(MilestoneStatus), default=MilestoneStatus.PENDING, nullable=False)
    priority = db.Column(db.Enum(MilestonePriority), default=MilestonePriority.MEDIUM, nullable=False)
    progress_percentage = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    
    # Relaciones polimórficas
    entity_type = db.Column(db.String(50))  # 'project', 'program', etc.
    entity_id = db.Column(db.Integer)
    
    # Metadatos adicionales
    extra_data = db.Column(db.JSON)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.target_date and kwargs.get('days_from_now'):
            from datetime import timedelta
            self.target_date = date.today() + timedelta(days=kwargs['days_from_now'])
    
    def __repr__(self):
        return f'<Milestone {self.title}>'
    
    @property
    def is_overdue(self) -> bool:
        """Verificar si el hito está vencido"""
        if not self.target_date:
            return False
        return date.today() > self.target_date and self.status != MilestoneStatus.COMPLETED
    
    @property
    def days_remaining(self) -> Optional[int]:
        """Días restantes hasta la fecha objetivo"""
        if not self.target_date:
            return None
        delta = self.target_date - date.today()
        return delta.days
    
    @property
    def status_display(self) -> str:
        """Mostrar estado legible"""
        status_map = {
            MilestoneStatus.PENDING: 'Pendiente',
            MilestoneStatus.IN_PROGRESS: 'En Progreso',
            MilestoneStatus.COMPLETED: 'Completado',
            MilestoneStatus.CANCELLED: 'Cancelado',
            MilestoneStatus.DELAYED: 'Retrasado'
        }
        return status_map.get(self.status, self.status.value)
    
    @property
    def priority_display(self) -> str:
        """Mostrar prioridad legible"""
        priority_map = {
            MilestonePriority.LOW: 'Baja',
            MilestonePriority.MEDIUM: 'Media',
            MilestonePriority.HIGH: 'Alta',
            MilestonePriority.CRITICAL: 'Crítica'
        }
        return priority_map.get(self.priority, self.priority.value)
    
    def complete(self, notes: str = None, completion_date: date = None) -> bool:
        """Marcar hito como completado"""
        if self.status == MilestoneStatus.COMPLETED:
            return False
        
        self.status = MilestoneStatus.COMPLETED
        self.completed_date = completion_date or date.today()
        self.progress_percentage = 100
        
        if notes:
            self.notes = notes
        
        return True
    
    def update_progress(self, percentage: int) -> None:
        """Actualizar progreso del hito"""
        if not 0 <= percentage <= 100:
            raise ValidationError("El porcentaje debe estar entre 0 y 100")
        
        self.progress_percentage = percentage
        
        if percentage == 100 and self.status != MilestoneStatus.COMPLETED:
            self.complete()
        elif percentage > 0 and self.status == MilestoneStatus.PENDING:
            self.status = MilestoneStatus.IN_PROGRESS
    
    def cancel(self, reason: str = None) -> None:
        """Cancelar hito"""
        self.status = MilestoneStatus.CANCELLED
        if reason:
            self.notes = f"Cancelado: {reason}"
    
    def delay(self, new_date: date, reason: str = None) -> None:
        """Retrasar hito"""
        if new_date <= date.today():
            raise ValidationError("La nueva fecha debe ser futura")
        
        self.target_date = new_date
        self.status = MilestoneStatus.DELAYED
        
        if reason:
            delay_note = f"Retrasado hasta {new_date}: {reason}"
            self.notes = f"{self.notes}\n{delay_note}" if self.notes else delay_note
    
    @classmethod
    def get_by_entity(cls, entity_type: str, entity_id: int) -> List['Milestone']:
        """Obtener hitos por entidad"""
        return cls.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by(cls.target_date.asc()).all()
    
    @classmethod
    def get_overdue(cls) -> List['Milestone']:
        """Obtener hitos vencidos"""
        return cls.query.filter(
            cls.target_date < date.today(),
            cls.status != MilestoneStatus.COMPLETED
        ).all()
    
    @classmethod
    def get_upcoming(cls, days: int = 7) -> List['Milestone']:
        """Obtener hitos próximos"""
        from datetime import timedelta
        future_date = date.today() + timedelta(days=days)
        
        return cls.query.filter(
            cls.target_date.between(date.today(), future_date),
            cls.status.in_([MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS])
        ).order_by(cls.target_date.asc()).all()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'status': self.status.value,
            'status_display': self.status_display,
            'priority': self.priority.value,
            'priority_display': self.priority_display,
            'progress_percentage': self.progress_percentage,
            'notes': self.notes,
            'is_overdue': self.is_overdue,
            'days_remaining': self.days_remaining,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'extra_data': self.extra_data
        }


class ProjectMilestone(Milestone):
    """Hito específico de proyecto"""
    __tablename__ = 'project_milestones'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, db.ForeignKey('milestones.id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    # Relación con proyecto
    project = db.relationship('Project', backref='milestones_rel', lazy='select')
    
    __mapper_args__ = {
        'polymorphic_identity': 'project_milestone'
    }
    
    def __init__(self, **kwargs):
        kwargs['entity_type'] = 'project'
        if 'project_id' in kwargs:
            kwargs['entity_id'] = kwargs['project_id']
        super().__init__(**kwargs)


class ProgramMilestone(Milestone):
    """Hito específico de programa"""
    __tablename__ = 'program_milestones'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, db.ForeignKey('milestones.id'), primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    
    # Relación con programa
    program = db.relationship('Program', backref='milestones_rel', lazy='select')
    
    __mapper_args__ = {
        'polymorphic_identity': 'program_milestone'
    }
    
    def __init__(self, **kwargs):
        kwargs['entity_type'] = 'program'
        if 'program_id' in kwargs:
            kwargs['entity_id'] = kwargs['program_id']
        super().__init__(**kwargs)