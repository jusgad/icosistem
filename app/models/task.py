"""
Modelo Tarea del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de tareas y actividades,
incluyendo asignación, seguimiento, dependencias, subtareas y automatización.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    TASK_TYPES,
    TASK_STATUS,
    TASK_PRIORITIES,
    TASK_CATEGORIES,
    RECURRENCE_PATTERNS,
    APPROVAL_REQUIREMENTS
)
from ..core.exceptions import ValidationError


class TaskType(Enum):
    """Tipos de tarea"""
    GENERAL = "general"
    MILESTONE = "milestone"
    DELIVERABLE = "deliverable"
    APPROVAL = "approval"
    REVIEW = "review"
    MEETING_PREP = "meeting_prep"
    FOLLOW_UP = "follow_up"
    ADMINISTRATIVE = "administrative"
    RESEARCH = "research"
    DEVELOPMENT = "development"
    MARKETING = "marketing"
    FINANCIAL = "financial"
    LEGAL = "legal"
    COMPLIANCE = "compliance"
    TRAINING = "training"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MAINTENANCE = "maintenance"
    SUPPORT = "support"
    RECURRING = "recurring"
    TEMPLATE = "template"


class TaskStatus(Enum):
    """Estados de tarea"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"
    ARCHIVED = "archived"
    FAILED = "failed"


class TaskPriority(Enum):
    """Prioridades de tarea"""
    LOWEST = "lowest"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HIGHEST = "highest"
    CRITICAL = "critical"
    URGENT = "urgent"


class TaskCategory(Enum):
    """Categorías de tarea"""
    BUSINESS_DEVELOPMENT = "business_development"
    PRODUCT_DEVELOPMENT = "product_development"
    MARKETING_SALES = "marketing_sales"
    OPERATIONS = "operations"
    FINANCE = "finance"
    LEGAL_COMPLIANCE = "legal_compliance"
    HR_TALENT = "hr_talent"
    TECHNOLOGY = "technology"
    RESEARCH = "research"
    CUSTOMER_SERVICE = "customer_service"
    STRATEGY = "strategy"
    ADMINISTRATION = "administration"
    PERSONAL = "personal"
    OTHER = "other"


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


class ApprovalRequirement(Enum):
    """Requisitos de aprobación"""
    NONE = "none"
    SINGLE_APPROVER = "single_approver"
    MULTIPLE_APPROVERS = "multiple_approvers"
    CONSENSUS = "consensus"
    HIERARCHICAL = "hierarchical"


# Tabla de asociación para asignados de tarea  
from app.extensions import db
task_assignees = Table(
    'task_assignees', db.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='assignee'),  # assignee, reviewer, approver, watcher
    Column('assigned_at', DateTime, default=datetime.utcnow),
    Column('assigned_by_id', Integer, ForeignKey('users.id')),
    Column('is_active', Boolean, default=True),
    Column('notification_settings', JSON),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para dependencias de tareas
task_dependencies = Table(
    'task_dependencies', db.metadata,
    Column('dependent_task_id', Integer, ForeignKey('tasks.id'), primary_key=True),
    Column('prerequisite_task_id', Integer, ForeignKey('tasks.id'), primary_key=True),
    Column('dependency_type', String(50), default='finish_to_start'),  # finish_to_start, start_to_start, etc.
    Column('lag_days', Integer, default=0),  # Días de retraso permitido
    Column('is_critical', Boolean, default=False),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para etiquetas de tarea
task_labels = Table(
    'task_labels', db.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id'), primary_key=True),
    Column('label_id', Integer, ForeignKey('task_labels_master.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Task(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Tarea
    
    Representa tareas y actividades en el ecosistema de emprendimiento
    con funcionalidades avanzadas de gestión, seguimiento y colaboración.
    """
    
    __tablename__ = 'tasks'
    
    # Información básica
    title = Column(String(300), nullable=False, index=True)
    description = Column(Text)
    task_type = Column(SQLEnum(TaskType), default=TaskType.GENERAL, index=True)
    category = Column(SQLEnum(TaskCategory), index=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.NOT_STARTED, index=True)
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.MEDIUM, index=True)
    
    # Creador y responsable principal
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    creator = relationship("User", foreign_keys=[creator_id])
    
    assignee_id = Column(Integer, ForeignKey('users.id'), index=True)  # Responsable principal
    assignee = relationship("User", foreign_keys=[assignee_id])
    
    # Fechas y plazos
    due_date = Column(DateTime, index=True)
    start_date = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_hours = Column(Float)
    actual_hours = Column(Float, default=0.0)
    
    # Progreso y seguimiento
    progress_percentage = Column(Float, default=0.0)
    completion_criteria = Column(JSON)  # Criterios específicos de completitud
    acceptance_criteria = Column(JSON)  # Criterios de aceptación
    
    # Jerarquía de tareas
    parent_task_id = Column(Integer, ForeignKey('tasks.id'))
    parent_task = relationship("Task", remote_side="Task.id", backref="subtasks")
    is_parent = Column(Boolean, default=False, index=True)
    
    # Recurrencia
    recurrence_pattern = Column(SQLEnum(RecurrencePattern), default=RecurrencePattern.NONE)
    recurrence_settings = Column(JSON)  # Configuración detallada de recurrencia
    parent_recurring_task_id = Column(Integer, ForeignKey('tasks.id'))
    next_occurrence_date = Column(DateTime)
    
    # Aprobación y revisión
    approval_requirement = Column(SQLEnum(ApprovalRequirement), default=ApprovalRequirement.NONE)
    approval_status = Column(String(50))  # pending, approved, rejected, partial
    approved_by_id = Column(Integer, ForeignKey('users.id'))
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    approved_at = Column(DateTime)
    approval_notes = Column(Text)
    
    # Bloqueos y dependencias
    is_blocked = Column(Boolean, default=False, index=True)
    blocked_reason = Column(Text)
    blocked_at = Column(DateTime)
    blocked_by_id = Column(Integer, ForeignKey('users.id'))
    blocked_by = relationship("User", foreign_keys=[blocked_by_id])
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project", back_populates="tasks")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    milestone_id = Column(Integer, ForeignKey('project_milestones.id'))
    milestone = relationship("ProjectMilestone")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting", back_populates="tasks")
    
    # Configuración de notificaciones
    notification_settings = Column(JSON, default=lambda: {
        'due_date_reminders': True,
        'status_changes': True,
        'comments': True,
        'assignments': True,
        'dependencies': True
    })
    
    # Automatización
    automation_rules = Column(JSON)  # Reglas de automatización
    auto_assign_rules = Column(JSON)  # Reglas de asignación automática
    
    # Estimación y esfuerzo
    story_points = Column(Integer)  # Para metodologías ágiles
    complexity_score = Column(Float)  # Puntuación de complejidad
    effort_estimation = Column(JSON)  # Estimación detallada de esfuerzo
    
    # Calidad y testing
    test_cases = Column(JSON)  # Casos de prueba asociados
    quality_metrics = Column(JSON)  # Métricas de calidad
    definition_of_done = Column(JSON)  # Definición de terminado
    
    # Configuración personalizada
    custom_fields = Column(JSON)
    task_metadata = Column(JSON)  # Metadatos adicionales
    tags = Column(JSON)  # Tags simples
    
    # Configuración de visibilidad
    is_private = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False, index=True)
    template_category = Column(String(100))
    
    # Relaciones
    
    # Usuarios asignados (múltiples)
    assignees = relationship("User",
                           secondary=task_assignees,
                           back_populates="assigned_tasks")
    
    # Dependencias
    prerequisites = relationship("Task",
                               secondary=task_dependencies,
                               primaryjoin="Task.id == task_dependencies.c.dependent_task_id",
                               secondaryjoin="Task.id == task_dependencies.c.prerequisite_task_id",
                               back_populates="dependents")
    
    dependents = relationship("Task",
                            secondary=task_dependencies,
                            primaryjoin="Task.id == task_dependencies.c.prerequisite_task_id",
                            secondaryjoin="Task.id == task_dependencies.c.dependent_task_id",
                            back_populates="prerequisites")
    
    # Etiquetas
    labels = relationship("TaskLabel", secondary=task_labels, back_populates="tasks")
    
    # Comentarios
    comments = relationship("TaskComment", back_populates="task")
    
    # Adjuntos
    attachments = relationship("TaskAttachment", back_populates="task")
    
    # Documentos relacionados
    documents = relationship("Document", back_populates="task")
    
    # Tiempo registrado
    time_entries = relationship("TimeEntry", back_populates="task")
    
    # Actividades de la tarea
    activities = relationship("ActivityLog", back_populates="task")
    
    def __init__(self, **kwargs):
        """Inicialización de la tarea"""
        super().__init__(**kwargs)
        
        # Configurar fechas por defecto
        if not self.start_date:
            self.start_date = datetime.now(timezone.utc)
        
        # Configuraciones por defecto
        if not self.notification_settings:
            self.notification_settings = {
                'due_date_reminders': True,
                'status_changes': True,
                'comments': True,
                'assignments': True,
                'dependencies': True
            }
        
        if not self.completion_criteria:
            self.completion_criteria = []
        
        if not self.acceptance_criteria:
            self.acceptance_criteria = []
    
    def __repr__(self):
        return f'<Task {self.title} ({self.status.value})>'
    
    def __str__(self):
        return f'{self.title} - {self.status.value} ({self.priority.value})'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título de la tarea"""
        if not title or len(title.strip()) < 3:
            raise ValidationError("El título debe tener al menos 3 caracteres")
        if len(title) > 300:
            raise ValidationError("El título no puede exceder 300 caracteres")
        return title.strip()
    
    @validates('progress_percentage')
    def validate_progress(self, key, progress):
        """Validar porcentaje de progreso"""
        if progress is not None:
            if progress < 0 or progress > 100:
                raise ValidationError("El progreso debe estar entre 0 y 100")
        return progress
    
    @validates('estimated_hours', 'actual_hours')
    def validate_hours(self, key, hours):
        """Validar horas"""
        if hours is not None:
            if hours < 0:
                raise ValidationError("Las horas no pueden ser negativas")
            if hours > 1000:  # Límite razonable
                raise ValidationError("Las horas no pueden exceder 1000")
        return hours
    
    @validates('story_points')
    def validate_story_points(self, key, points):
        """Validar story points"""
        if points is not None:
            if points < 0 or points > 100:
                raise ValidationError("Los story points deben estar entre 0 y 100")
        return points
    
    @validates('complexity_score')
    def validate_complexity(self, key, score):
        """Validar puntuación de complejidad"""
        if score is not None:
            if score < 0 or score > 10:
                raise ValidationError("La puntuación de complejidad debe estar entre 0 y 10")
        return score
    
    @validates('due_date', 'start_date')
    def validate_dates(self, key, date_value):
        """Validar fechas"""
        if date_value:
            if key == 'due_date' and self.start_date:
                if date_value < self.start_date:
                    raise ValidationError("La fecha de vencimiento no puede ser anterior al inicio")
        return date_value
    
    # Propiedades híbridas
    @hybrid_property
    def is_overdue(self):
        """Verificar si la tarea está vencida"""
        return (self.due_date and 
                self.due_date < datetime.now(timezone.utc) and 
                self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED])
    
    @hybrid_property
    def is_due_soon(self):
        """Verificar si vence pronto (próximas 24 horas)"""
        if not self.due_date:
            return False
        return (self.due_date - datetime.now(timezone.utc)).total_seconds() <= 86400  # 24 horas
    
    @hybrid_property
    def days_until_due(self):
        """Días hasta vencimiento"""
        if self.due_date:
            return (self.due_date.date() - date.today()).days
        return None
    
    @hybrid_property
    def is_completed(self):
        """Verificar si está completada"""
        return self.status == TaskStatus.COMPLETED
    
    @hybrid_property
    def is_in_progress(self):
        """Verificar si está en progreso"""
        return self.status == TaskStatus.IN_PROGRESS
    
    @hybrid_property
    def has_subtasks(self):
        """Verificar si tiene subtareas"""
        return self.is_parent and len(self.subtasks) > 0
    
    @hybrid_property
    def subtask_count(self):
        """Número de subtareas"""
        return len(self.subtasks) if self.subtasks else 0
    
    @hybrid_property
    def completed_subtasks_count(self):
        """Número de subtareas completadas"""
        if not self.subtasks:
            return 0
        return len([subtask for subtask in self.subtasks 
                   if subtask.status == TaskStatus.COMPLETED and not subtask.is_deleted])
    
    @hybrid_property
    def subtasks_completion_rate(self):
        """Tasa de finalización de subtareas"""
        if self.subtask_count == 0:
            return 0
        return (self.completed_subtasks_count / self.subtask_count) * 100
    
    @hybrid_property
    def time_spent_vs_estimated(self):
        """Comparación tiempo gastado vs estimado"""
        if not self.estimated_hours or self.estimated_hours == 0:
            return None
        return (self.actual_hours / self.estimated_hours) * 100
    
    @hybrid_property
    def dependency_count(self):
        """Número de dependencias"""
        return len(self.prerequisites) if self.prerequisites else 0
    
    @hybrid_property
    def blocking_count(self):
        """Número de tareas que bloquea"""
        return len(self.dependents) if self.dependents else 0
    
    @hybrid_property
    def assignee_count(self):
        """Número de asignados"""
        return len(self.assignees) if self.assignees else 0
    
    @hybrid_property
    def comment_count(self):
        """Número de comentarios"""
        return len(self.comments) if self.comments else 0
    
    # Métodos de negocio
    def assign_user(self, user, role: str = 'assignee', assigned_by_user_id: int = None,
                   notification_settings: dict[str, Any] = None) -> bool:
        """Asignar usuario a la tarea"""
        valid_roles = ['assignee', 'reviewer', 'approver', 'watcher']
        if role not in valid_roles:
            raise ValidationError(f"Rol inválido: {role}")
        
        # Verificar si ya está asignado
        from .. import db
        
        existing = db.session.execute(
            task_assignees.select().where(
                task_assignees.c.task_id == self.id,
                task_assignees.c.user_id == user.id
            )
        ).first()
        
        if existing:
            if existing.is_active:
                return False  # Ya está asignado
            else:
                # Reactivar asignación
                db.session.execute(
                    task_assignees.update().where(
                        task_assignees.c.task_id == self.id,
                        task_assignees.c.user_id == user.id
                    ).values(
                        is_active=True,
                        role=role,
                        assigned_at=datetime.now(timezone.utc),
                        assigned_by_id=assigned_by_user_id or self.creator_id,
                        notification_settings=notification_settings or {
                            'due_date_reminders': True,
                            'status_changes': True,
                            'comments': True
                        }
                    )
                )
                return True
        
        # Nueva asignación
        assignment_data = {
            'task_id': self.id,
            'user_id': user.id,
            'role': role,
            'assigned_by_id': assigned_by_user_id or self.creator_id,
            'notification_settings': notification_settings or {
                'due_date_reminders': True,
                'status_changes': True,
                'comments': True
            }
        }
        
        db.session.execute(task_assignees.insert().values(assignment_data))
        
        # Actualizar responsable principal si es el primer asignado
        if not self.assignee_id and role == 'assignee':
            self.assignee_id = user.id
        
        # Log de actividad
        self._log_activity('user_assigned', f"{user.full_name} asignado como {role}")
        
        return True
    
    def unassign_user(self, user, unassigned_by_user_id: int = None) -> bool:
        """Desasignar usuario de la tarea"""
        from .. import db
        
        # Verificar asignación activa
        assignment = db.session.execute(
            task_assignees.select().where(
                task_assignees.c.task_id == self.id,
                task_assignees.c.user_id == user.id,
                task_assignees.c.is_active == True
            )
        ).first()
        
        if not assignment:
            return False
        
        # Marcar como inactivo
        db.session.execute(
            task_assignees.update().where(
                task_assignees.c.task_id == self.id,
                task_assignees.c.user_id == user.id
            ).values(is_active=False)
        )
        
        # Actualizar responsable principal si era el asignado
        if self.assignee_id == user.id:
            # Buscar otro asignado activo
            other_assignee = db.session.execute(
                task_assignees.select().where(
                    task_assignees.c.task_id == self.id,
                    task_assignees.c.user_id != user.id,
                    task_assignees.c.role == 'assignee',
                    task_assignees.c.is_active == True
                )
            ).first()
            
            self.assignee_id = other_assignee.user_id if other_assignee else None
        
        self._log_activity('user_unassigned', f"{user.full_name} desasignado")
        
        return True
    
    def update_status(self, new_status: TaskStatus, updated_by_user_id: int, 
                     notes: str = None, completion_percentage: float = None):
        """Actualizar estado de la tarea"""
        if new_status == self.status:
            return False
        
        old_status = self.status
        self.status = new_status
        
        # Actualizar fechas relevantes
        if new_status == TaskStatus.IN_PROGRESS and old_status == TaskStatus.NOT_STARTED:
            if not self.start_date:
                self.start_date = datetime.now(timezone.utc)
        
        elif new_status == TaskStatus.COMPLETED:
            self.completed_at = datetime.now(timezone.utc)
            self.progress_percentage = 100.0
            
            # Verificar si se pueden desbloquear tareas dependientes
            self._check_and_unblock_dependents()
        
        elif new_status == TaskStatus.BLOCKED:
            self.is_blocked = True
            self.blocked_at = datetime.now(timezone.utc)
            self.blocked_by_id = updated_by_user_id
            if notes:
                self.blocked_reason = notes
        
        elif old_status == TaskStatus.BLOCKED and new_status != TaskStatus.BLOCKED:
            self.is_blocked = False
            self.blocked_reason = None
            self.blocked_at = None
            self.blocked_by_id = None
        
        # Actualizar progreso si se proporciona
        if completion_percentage is not None:
            self.progress_percentage = completion_percentage
        
        # Log de actividad
        self._log_activity('status_changed', 
                          f"Estado cambiado de {old_status.value} a {new_status.value}",
                          updated_by_user_id, {'notes': notes})
        
        # Actualizar tarea padre si es subtarea
        if self.parent_task_id:
            self.parent_task._update_parent_progress()
        
        return True
    
    def update_progress(self, progress_percentage: float, updated_by_user_id: int, 
                       notes: str = None):
        """Actualizar progreso de la tarea"""
        if progress_percentage < 0 or progress_percentage > 100:
            raise ValidationError("El progreso debe estar entre 0 y 100")
        
        old_progress = self.progress_percentage
        self.progress_percentage = progress_percentage
        
        # Actualizar estado basado en progreso
        if progress_percentage == 0 and self.status == TaskStatus.NOT_STARTED:
            pass  # Mantener estado
        elif progress_percentage > 0 and progress_percentage < 100:
            if self.status == TaskStatus.NOT_STARTED:
                self.status = TaskStatus.IN_PROGRESS
                if not self.start_date:
                    self.start_date = datetime.now(timezone.utc)
        elif progress_percentage == 100:
            if self.status != TaskStatus.COMPLETED:
                self.status = TaskStatus.COMPLETED
                self.completed_at = datetime.now(timezone.utc)
                self._check_and_unblock_dependents()
        
        self._log_activity('progress_updated', 
                          f"Progreso actualizado de {old_progress}% a {progress_percentage}%",
                          updated_by_user_id, {'notes': notes})
        
        # Actualizar tarea padre si es subtarea
        if self.parent_task_id:
            self.parent_task._update_parent_progress()
    
    def _update_parent_progress(self):
        """Actualizar progreso de tarea padre basado en subtareas"""
        if not self.has_subtasks:
            return
        
        active_subtasks = [st for st in self.subtasks if not st.is_deleted]
        if not active_subtasks:
            return
        
        total_progress = sum(st.progress_percentage for st in active_subtasks)
        average_progress = total_progress / len(active_subtasks)
        
        self.progress_percentage = round(average_progress, 1)
        
        # Actualizar estado basado en progreso de subtareas
        completed_subtasks = [st for st in active_subtasks if st.status == TaskStatus.COMPLETED]
        
        if len(completed_subtasks) == len(active_subtasks):
            # Todas las subtareas completadas
            if self.status != TaskStatus.COMPLETED:
                self.status = TaskStatus.COMPLETED
                self.completed_at = datetime.now(timezone.utc)
        elif len(completed_subtasks) > 0 or any(st.status == TaskStatus.IN_PROGRESS for st in active_subtasks):
            # Al menos una subtarea en progreso
            if self.status == TaskStatus.NOT_STARTED:
                self.status = TaskStatus.IN_PROGRESS
                if not self.start_date:
                    self.start_date = datetime.now(timezone.utc)
    
    def add_dependency(self, prerequisite_task, dependency_type: str = 'finish_to_start',
                      lag_days: int = 0, is_critical: bool = False):
        """Agregar dependencia con otra tarea"""
        # Verificar que no exista ya
        from .. import db
        
        existing = db.session.execute(
            task_dependencies.select().where(
                task_dependencies.c.dependent_task_id == self.id,
                task_dependencies.c.prerequisite_task_id == prerequisite_task.id
            )
        ).first()
        
        if existing:
            raise ValidationError("La dependencia ya existe")
        
        # Verificar que no cree dependencia circular
        if self._would_create_circular_dependency(prerequisite_task):
            raise ValidationError("La dependencia crearía un ciclo circular")
        
        dependency_data = {
            'dependent_task_id': self.id,
            'prerequisite_task_id': prerequisite_task.id,
            'dependency_type': dependency_type,
            'lag_days': lag_days,
            'is_critical': is_critical
        }
        
        db.session.execute(task_dependencies.insert().values(dependency_data))
        
        # Verificar si esta tarea debe bloquearse
        if prerequisite_task.status != TaskStatus.COMPLETED:
            self._check_if_should_be_blocked()
        
        self._log_activity('dependency_added', 
                          f"Dependencia agregada con tarea: {prerequisite_task.title}")
    
    def remove_dependency(self, prerequisite_task):
        """Remover dependencia"""
        from .. import db
        
        result = db.session.execute(
            task_dependencies.delete().where(
                task_dependencies.c.dependent_task_id == self.id,
                task_dependencies.c.prerequisite_task_id == prerequisite_task.id
            )
        )
        
        if result.rowcount > 0:
            self._log_activity('dependency_removed', 
                              f"Dependencia removida con tarea: {prerequisite_task.title}")
            
            # Verificar si se puede desbloquear
            self._check_if_should_be_blocked()
            return True
        
        return False
    
    def _would_create_circular_dependency(self, prerequisite_task) -> bool:
        """Verificar si agregaría dependencia circular"""
        # Implementación simplificada - en producción sería más robusta
        return prerequisite_task.id in self._get_all_dependent_task_ids()
    
    def _get_all_dependent_task_ids(self, visited=None) -> set:
        """Obtener todos los IDs de tareas dependientes recursivamente"""
        if visited is None:
            visited = set()
        
        if self.id in visited:
            return visited
        
        visited.add(self.id)
        
        for dependent in self.dependents:
            dependent._get_all_dependent_task_ids(visited)
        
        return visited
    
    def _check_if_should_be_blocked(self):
        """Verificar si la tarea debe bloquearse por dependencias"""
        incomplete_prerequisites = [
            prereq for prereq in self.prerequisites 
            if prereq.status != TaskStatus.COMPLETED and not prereq.is_deleted
        ]
        
        if incomplete_prerequisites and not self.is_blocked:
            self.is_blocked = True
            self.blocked_at = datetime.now(timezone.utc)
            self.blocked_reason = f"Bloqueada por {len(incomplete_prerequisites)} dependencia(s) incompleta(s)"
            
            if self.status == TaskStatus.IN_PROGRESS:
                self.status = TaskStatus.BLOCKED
        
        elif not incomplete_prerequisites and self.is_blocked:
            # Verificar si el bloqueo es solo por dependencias
            if "dependencia" in (self.blocked_reason or "").lower():
                self.is_blocked = False
                self.blocked_reason = None
                self.blocked_at = None
                self.blocked_by_id = None
                
                if self.status == TaskStatus.BLOCKED:
                    self.status = TaskStatus.NOT_STARTED if self.progress_percentage == 0 else TaskStatus.IN_PROGRESS
    
    def _check_and_unblock_dependents(self):
        """Verificar y desbloquear tareas dependientes cuando esta se completa"""
        for dependent in self.dependents:
            if not dependent.is_deleted:
                dependent._check_if_should_be_blocked()
    
    def create_subtask(self, title: str, description: str = None, 
                      assignee_id: int = None, due_date: datetime = None,
                      priority: TaskPriority = None, created_by_user_id: int = None) -> 'Task':
        """Crear subtarea"""
        subtask = Task(
            title=title,
            description=description,
            task_type=TaskType.GENERAL,
            category=self.category,
            priority=priority or TaskPriority.MEDIUM,
            creator_id=created_by_user_id or self.creator_id,
            assignee_id=assignee_id,
            due_date=due_date,
            parent_task_id=self.id,
            project_id=self.project_id,
            program_id=self.program_id,
            organization_id=self.organization_id
        )
        
        from .. import db
        db.session.add(subtask)
        
        # Marcar tarea padre
        self.is_parent = True
        
        self._log_activity('subtask_created', f"Subtarea creada: {title}", created_by_user_id)
        
        return subtask
    
    def add_time_entry(self, user_id: int, hours: float, description: str = None,
                      date_worked: date = None) -> 'TimeEntry':
        """Agregar registro de tiempo"""
        time_entry = TimeEntry(
            task_id=self.id,
            user_id=user_id,
            hours=hours,
            description=description,
            date_worked=date_worked or date.today(),
            project_id=self.project_id
        )
        
        from .. import db
        db.session.add(time_entry)
        
        # Actualizar tiempo total
        self.actual_hours = (self.actual_hours or 0) + hours
        
        self._log_activity('time_logged', f"{hours} horas registradas", user_id)
        
        return time_entry
    
    def add_comment(self, user_id: int, content: str, comment_type: str = 'comment') -> 'TaskComment':
        """Agregar comentario"""
        comment = TaskComment(
            task_id=self.id,
            author_id=user_id,
            content=content,
            comment_type=comment_type
        )
        
        from .. import db
        db.session.add(comment)
        
        self._log_activity('comment_added', "Comentario agregado", user_id)
        
        return comment
    
    def add_attachment(self, user_id: int, filename: str, file_path: str,
                      file_size: int, mime_type: str, description: str = None) -> 'TaskAttachment':
        """Agregar archivo adjunto"""
        attachment = TaskAttachment(
            task_id=self.id,
            uploaded_by_id=user_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            description=description
        )
        
        from .. import db
        db.session.add(attachment)
        
        self._log_activity('attachment_added', f"Archivo adjunto: {filename}", user_id)
        
        return attachment
    
    def duplicate_task(self, duplicated_by_user_id: int, include_subtasks: bool = True,
                      include_assignees: bool = False, new_title: str = None) -> 'Task':
        """Duplicar tarea"""
        new_task = Task(
            title=new_title or f"Copia de {self.title}",
            description=self.description,
            task_type=self.task_type,
            category=self.category,
            priority=self.priority,
            creator_id=duplicated_by_user_id,
            estimated_hours=self.estimated_hours,
            story_points=self.story_points,
            complexity_score=self.complexity_score,
            completion_criteria=self.completion_criteria.copy() if self.completion_criteria else None,
            acceptance_criteria=self.acceptance_criteria.copy() if self.acceptance_criteria else None,
            project_id=self.project_id,
            program_id=self.program_id,
            organization_id=self.organization_id,
            custom_fields=self.custom_fields.copy() if self.custom_fields else None
        )
        
        from .. import db
        db.session.add(new_task)
        db.session.flush()  # Para obtener ID
        
        # Duplicar asignados si se solicita
        if include_assignees:
            for assignee in self.assignees:
                new_task.assign_user(assignee, assigned_by_user_id=duplicated_by_user_id)
        
        # Duplicar subtareas si se solicita
        if include_subtasks and self.has_subtasks:
            for subtask in self.subtasks:
                if not subtask.is_deleted:
                    subtask_copy = subtask.duplicate_task(
                        duplicated_by_user_id, 
                        include_subtasks=False,  # Evitar recursión infinita
                        include_assignees=include_assignees
                    )
                    subtask_copy.parent_task_id = new_task.id
        
        self._log_activity('task_duplicated', f"Tarea duplicada como: {new_task.title}", duplicated_by_user_id)
        
        return new_task
    
    def create_recurring_instances(self, end_date: date, max_instances: int = 12) -> list['Task']:
        """Crear instancias de tarea recurrente"""
        if self.recurrence_pattern == RecurrencePattern.NONE:
            return []
        
        instances = []
        current_date = self.next_occurrence_date or self.due_date or datetime.now(timezone.utc)
        instance_count = 0
        
        while (current_date.date() <= end_date and 
               instance_count < max_instances):
            
            # Calcular próxima fecha
            next_date = self._calculate_next_occurrence(current_date)
            if not next_date or next_date.date() > end_date:
                break
            
            # Crear nueva instancia
            new_instance = Task(
                title=self.title,
                description=self.description,
                task_type=self.task_type,
                category=self.category,
                priority=self.priority,
                creator_id=self.creator_id,
                assignee_id=self.assignee_id,
                due_date=next_date,
                estimated_hours=self.estimated_hours,
                story_points=self.story_points,
                parent_recurring_task_id=self.id,
                project_id=self.project_id,
                program_id=self.program_id,
                organization_id=self.organization_id
            )
            
            from .. import db
            db.session.add(new_instance)
            instances.append(new_instance)
            
            # Copiar asignados
            for assignee in self.assignees:
                new_instance.assign_user(assignee)
            
            current_date = next_date
            instance_count += 1
        
        # Actualizar próxima ocurrencia de la tarea original
        self.next_occurrence_date = current_date if instance_count < max_instances else None
        
        return instances
    
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
            # Mismo día del siguiente trimestre
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
            # Lógica personalizada basada en recurrence_settings
            settings = self.recurrence_settings or {}
            interval = settings.get('interval', 1)
            unit = settings.get('unit', 'days')
            
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
    
    def _log_activity(self, activity_type: str, description: str, 
                     user_id: int = None, metadata: dict[str, Any] = None):
        """Registrar actividad de la tarea"""
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type=activity_type,
            description=description,
            task_id=self.id,
            user_id=user_id or self.creator_id,
            metadata=metadata or {}
        )
        
        db.session.add(activity)
    
    def get_task_analytics(self) -> dict[str, Any]:
        """Obtener analytics de la tarea"""
        return {
            'basic_info': {
                'title': self.title,
                'type': self.task_type.value,
                'category': self.category.value if self.category else None,
                'status': self.status.value,
                'priority': self.priority.value,
                'progress': self.progress_percentage,
                'is_overdue': self.is_overdue,
                'days_until_due': self.days_until_due
            },
            'time_tracking': {
                'estimated_hours': self.estimated_hours,
                'actual_hours': self.actual_hours,
                'time_variance': self.time_spent_vs_estimated,
                'story_points': self.story_points,
                'complexity_score': self.complexity_score
            },
            'collaboration': {
                'assignee_count': self.assignee_count,
                'comment_count': self.comment_count,
                'attachment_count': len(self.attachments) if self.attachments else 0,
                'has_subtasks': self.has_subtasks,
                'subtask_count': self.subtask_count,
                'subtasks_completion_rate': self.subtasks_completion_rate
            },
            'dependencies': {
                'prerequisite_count': self.dependency_count,
                'dependent_count': self.blocking_count,
                'is_blocked': self.is_blocked,
                'blocked_reason': self.blocked_reason
            },
            'lifecycle': {
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'due_date': self.due_date.isoformat() if self.due_date else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'days_active': (datetime.now(timezone.utc) - self.created_at).days if self.created_at else 0
            }
        }
    
    def get_completion_status(self) -> dict[str, Any]:
        """Obtener estado de completitud detallado"""
        completion_criteria_met = 0
        if self.completion_criteria:
            # En una implementación real, verificaríamos cada criterio
            completion_criteria_met = len(self.completion_criteria) if self.is_completed else 0
        
        acceptance_criteria_met = 0
        if self.acceptance_criteria:
            # En una implementación real, verificaríamos cada criterio
            acceptance_criteria_met = len(self.acceptance_criteria) if self.is_completed else 0
        
        return {
            'overall_progress': self.progress_percentage,
            'is_completed': self.is_completed,
            'completion_criteria': {
                'total': len(self.completion_criteria) if self.completion_criteria else 0,
                'met': completion_criteria_met,
                'percentage': (completion_criteria_met / len(self.completion_criteria) * 100) if self.completion_criteria else 0
            },
            'acceptance_criteria': {
                'total': len(self.acceptance_criteria) if self.acceptance_criteria else 0,
                'met': acceptance_criteria_met,
                'percentage': (acceptance_criteria_met / len(self.acceptance_criteria) * 100) if self.acceptance_criteria else 0
            },
            'subtasks': {
                'total': self.subtask_count,
                'completed': self.completed_subtasks_count,
                'completion_rate': self.subtasks_completion_rate
            } if self.has_subtasks else None,
            'blockers': {
                'is_blocked': self.is_blocked,
                'reason': self.blocked_reason,
                'incomplete_prerequisites': [
                    {
                        'id': prereq.id,
                        'title': prereq.title,
                        'status': prereq.status.value
                    }
                    for prereq in self.prerequisites 
                    if prereq.status != TaskStatus.COMPLETED and not prereq.is_deleted
                ]
            }
        }
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def search_tasks(cls, query: str = None, filters: dict[str, Any] = None,
                    user_id: int = None, limit: int = 50, offset: int = 0):
        """Buscar tareas"""
        search = cls.query.filter(cls.is_deleted == False)
        
        # Filtrar por usuario si se especifica
        if user_id:
            if filters and filters.get('scope') == 'assigned':
                # Solo tareas asignadas al usuario
                search = search.filter(
                    (cls.assignee_id == user_id) |
                    (cls.assignees.any(id=user_id))
                )
            elif filters and filters.get('scope') == 'created':
                # Solo tareas creadas por el usuario
                search = search.filter(cls.creator_id == user_id)
            else:
                # Tareas relacionadas al usuario (creadas o asignadas)
                search = search.filter(
                    (cls.creator_id == user_id) |
                    (cls.assignee_id == user_id) |
                    (cls.assignees.any(id=user_id))
                )
        
        # Búsqueda por texto
        if query:
            search_term = f"%{query}%"
            search = search.filter(
                cls.title.ilike(search_term) |
                cls.description.ilike(search_term)
            )
        
        # Aplicar filtros
        if filters:
            if filters.get('status'):
                if isinstance(filters['status'], list):
                    search = search.filter(cls.status.in_(filters['status']))
                else:
                    search = search.filter(cls.status == filters['status'])
            
            if filters.get('priority'):
                if isinstance(filters['priority'], list):
                    search = search.filter(cls.priority.in_(filters['priority']))
                else:
                    search = search.filter(cls.priority == filters['priority'])
            
            if filters.get('task_type'):
                search = search.filter(cls.task_type == filters['task_type'])
            
            if filters.get('category'):
                search = search.filter(cls.category == filters['category'])
            
            if filters.get('project_id'):
                search = search.filter(cls.project_id == filters['project_id'])
            
            if filters.get('organization_id'):
                search = search.filter(cls.organization_id == filters['organization_id'])
            
            if filters.get('assignee_id'):
                search = search.filter(cls.assignee_id == filters['assignee_id'])
            
            if filters.get('creator_id'):
                search = search.filter(cls.creator_id == filters['creator_id'])
            
            if filters.get('due_date_from'):
                search = search.filter(cls.due_date >= filters['due_date_from'])
            
            if filters.get('due_date_to'):
                search = search.filter(cls.due_date <= filters['due_date_to'])
            
            if filters.get('is_overdue'):
                if filters['is_overdue']:
                    search = search.filter(
                        cls.due_date < datetime.now(timezone.utc),
                        cls.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
                    )
                else:
                    search = search.filter(
                        (cls.due_date.is_(None)) |
                        (cls.due_date >= datetime.now(timezone.utc)) |
                        (cls.status.in_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]))
                    )
            
            if filters.get('is_blocked'):
                search = search.filter(cls.is_blocked == filters['is_blocked'])
            
            if filters.get('has_subtasks'):
                search = search.filter(cls.is_parent == filters['has_subtasks'])
            
            if filters.get('parent_tasks_only'):
                if filters['parent_tasks_only']:
                    search = search.filter(cls.parent_task_id.is_(None))
                else:
                    search = search.filter(cls.parent_task_id.isnot(None))
            
            if filters.get('progress_min'):
                search = search.filter(cls.progress_percentage >= filters['progress_min'])
            
            if filters.get('progress_max'):
                search = search.filter(cls.progress_percentage <= filters['progress_max'])
        
        # Ordenamiento
        sort_by = filters.get('sort_by', 'due_date') if filters else 'due_date'
        sort_order = filters.get('sort_order', 'asc') if filters else 'asc'
        
        if sort_by == 'title':
            order_column = cls.title
        elif sort_by == 'created_at':
            order_column = cls.created_at
        elif sort_by == 'priority':
            # Ordenar por prioridad (crítico primero)
            priority_order = {
                TaskPriority.CRITICAL: 7,
                TaskPriority.URGENT: 6,
                TaskPriority.HIGHEST: 5,
                TaskPriority.HIGH: 4,
                TaskPriority.MEDIUM: 3,
                TaskPriority.LOW: 2,
                TaskPriority.LOWEST: 1
            }
            order_column = cls.priority
        elif sort_by == 'progress':
            order_column = cls.progress_percentage
        elif sort_by == 'status':
            order_column = cls.status
        else:  # due_date
            order_column = cls.due_date
        
        if sort_order == 'desc':
            search = search.order_by(order_column.desc())
        else:
            search = search.order_by(order_column.asc())
        
        return search.offset(offset).limit(limit).all()
    
    @classmethod
    def get_overdue_tasks(cls, user_id: int = None, organization_id: int = None):
        """Obtener tareas vencidas"""
        query = cls.query.filter(
            cls.due_date < datetime.now(timezone.utc),
            cls.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]),
            cls.is_deleted == False
        )
        
        if user_id:
            query = query.filter(
                (cls.assignee_id == user_id) |
                (cls.assignees.any(id=user_id))
            )
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
        
        return query.order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_due_soon_tasks(cls, hours_ahead: int = 24, user_id: int = None):
        """Obtener tareas que vencen pronto"""
        due_before = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
        
        query = cls.query.filter(
            cls.due_date.between(datetime.now(timezone.utc), due_before),
            cls.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            cls.is_deleted == False
        )
        
        if user_id:
            query = query.filter(
                (cls.assignee_id == user_id) |
                (cls.assignees.any(id=user_id))
            )
        
        return query.order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_blocked_tasks(cls, user_id: int = None, organization_id: int = None):
        """Obtener tareas bloqueadas"""
        query = cls.query.filter(
            cls.is_blocked == True,
            cls.is_deleted == False
        )
        
        if user_id:
            query = query.filter(
                (cls.assignee_id == user_id) |
                (cls.assignees.any(id=user_id))
            )
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
        
        return query.all()
    
    @classmethod
    def get_user_task_summary(cls, user_id: int) -> dict[str, Any]:
        """Obtener resumen de tareas del usuario"""
        user_tasks = cls.query.filter(
            (cls.assignee_id == user_id) | (cls.assignees.any(id=user_id)),
            cls.is_deleted == False
        ).all()
        
        if not user_tasks:
            return {
                'total_tasks': 0,
                'by_status': {},
                'by_priority': {},
                'overdue_count': 0,
                'due_soon_count': 0,
                'blocked_count': 0,
                'completion_rate': 0
            }
        
        # Estadísticas por estado
        status_counts = {}
        for task in user_tasks:
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Estadísticas por prioridad
        priority_counts = {}
        for task in user_tasks:
            priority = task.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Contadores específicos
        overdue_count = len([t for t in user_tasks if t.is_overdue])
        due_soon_count = len([t for t in user_tasks if t.is_due_soon and not t.is_overdue])
        blocked_count = len([t for t in user_tasks if t.is_blocked])
        completed_count = status_counts.get('completed', 0)
        
        # Tasa de finalización
        completion_rate = (completed_count / len(user_tasks) * 100) if user_tasks else 0
        
        return {
            'total_tasks': len(user_tasks),
            'by_status': status_counts,
            'by_priority': priority_counts,
            'overdue_count': overdue_count,
            'due_soon_count': due_soon_count,
            'blocked_count': blocked_count,
            'completion_rate': round(completion_rate, 1),
            'avg_progress': round(sum(t.progress_percentage for t in user_tasks) / len(user_tasks), 1)
        }
    
    def to_dict(self, include_subtasks=False, include_assignees=False, 
               include_dependencies=False, include_comments=False) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type.value,
            'category': self.category.value if self.category else None,
            'status': self.status.value,
            'priority': self.priority.value,
            'progress_percentage': self.progress_percentage,
            'creator_id': self.creator_id,
            'creator_name': self.creator.full_name if self.creator else None,
            'assignee_id': self.assignee_id,
            'assignee_name': self.assignee.full_name if self.assignee else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'story_points': self.story_points,
            'complexity_score': self.complexity_score,
            'is_overdue': self.is_overdue,
            'is_due_soon': self.is_due_soon,
            'days_until_due': self.days_until_due,
            'is_completed': self.is_completed,
            'is_in_progress': self.is_in_progress,
            'is_blocked': self.is_blocked,
            'blocked_reason': self.blocked_reason,
            'has_subtasks': self.has_subtasks,
            'subtask_count': self.subtask_count,
            'completed_subtasks_count': self.completed_subtasks_count,
            'subtasks_completion_rate': self.subtasks_completion_rate,
            'assignee_count': self.assignee_count,
            'comment_count': self.comment_count,
            'dependency_count': self.dependency_count,
            'blocking_count': self.blocking_count,
            'parent_task_id': self.parent_task_id,
            'is_parent': self.is_parent,
            'recurrence_pattern': self.recurrence_pattern.value,
            'project_id': self.project_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Información de contexto
        if self.project_id:
            data['project'] = {
                'id': self.project_id,
                'name': self.project.name if self.project else None
            }
        
        if self.organization_id:
            data['organization'] = {
                'id': self.organization_id,
                'name': self.organization.name if self.organization else None
            }
        
        # Subtareas
        if include_subtasks and self.has_subtasks:
            data['subtasks'] = [
                subtask.to_dict(include_subtasks=False)
                for subtask in self.subtasks if not subtask.is_deleted
            ]
        
        # Asignados
        if include_assignees:
            data['assignees'] = [
                {
                    'id': assignee.id,
                    'name': assignee.full_name,
                    'email': assignee.email
                }
                for assignee in self.assignees
            ]
        
        # Dependencias
        if include_dependencies:
            data['prerequisites'] = [
                {
                    'id': prereq.id,
                    'title': prereq.title,
                    'status': prereq.status.value
                }
                for prereq in self.prerequisites if not prereq.is_deleted
            ]
            
            data['dependents'] = [
                {
                    'id': dep.id,
                    'title': dep.title,
                    'status': dep.status.value
                }
                for dep in self.dependents if not dep.is_deleted
            ]
        
        # Comentarios recientes
        if include_comments:
            recent_comments = self.comments[:5] if self.comments else []
            data['recent_comments'] = [
                {
                    'id': comment.id,
                    'content': comment.content[:100] + "..." if len(comment.content) > 100 else comment.content,
                    'author': comment.author.full_name if comment.author else None,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None
                }
                for comment in recent_comments
            ]
        
        return data


class TaskComment(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Comentario de Tarea
    
    Representa comentarios y discusiones en tareas.
    """
    
    __tablename__ = 'task_comments'
    
    # Relación con tarea
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    task = relationship("Task", back_populates="comments")
    
    # Autor del comentario
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    author = relationship("User")
    
    # Comentario padre (para respuestas)
    parent_comment_id = Column(Integer, ForeignKey('task_comments.id'))
    parent_comment = relationship("TaskComment", remote_side="TaskComment.id", backref="replies")
    
    # Contenido
    content = Column(Text, nullable=False)
    content_html = Column(Text)
    comment_type = Column(String(50), default='comment')  # comment, status_update, system
    
    # Menciones
    mentions = Column(JSON)  # Usuarios mencionados
    
    # Estado
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime)
    
    def __repr__(self):
        return f'<TaskComment {self.id} on Task {self.task_id}>'


class TaskAttachment(BaseModel, TimestampMixin):
    """
    Modelo de Archivo Adjunto de Tarea
    
    Representa archivos adjuntos a tareas.
    """
    
    __tablename__ = 'task_attachments'
    
    # Relación con tarea
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    task = relationship("Task", back_populates="attachments")
    
    # Usuario que subió el archivo
    uploaded_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    uploaded_by = relationship("User")
    
    # Información del archivo
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500))
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    description = Column(Text)
    
    def __repr__(self):
        return f'<TaskAttachment {self.filename}>'


class TimeEntry(BaseModel, TimestampMixin):
    """
    Modelo de Registro de Tiempo
    
    Representa tiempo trabajado en tareas.
    """
    
    __tablename__ = 'time_entries'
    
    # Relación con tarea
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    task = relationship("Task", back_populates="time_entries")
    
    # Usuario que registró el tiempo
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    user = relationship("User")
    
    # Información del tiempo
    hours = Column(Float, nullable=False)
    description = Column(Text)
    date_worked = Column(Date, nullable=False, default=date.today)
    
    # Contexto adicional
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    
    # Facturación
    is_billable = Column(Boolean, default=True)
    hourly_rate = Column(Float)  # Tarifa por hora
    
    def __repr__(self):
        return f'<TimeEntry {self.hours}h on {self.date_worked}>'
    
    @hybrid_property
    def billable_amount(self):
        """Monto facturable"""
        if self.is_billable and self.hourly_rate:
            return self.hours * self.hourly_rate
        return 0


class TaskLabel(BaseModel, TimestampMixin):
    """
    Modelo de Etiqueta de Tarea
    
    Representa etiquetas para categorizar tareas.
    """
    
    __tablename__ = 'task_labels_master'
    
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    color = Column(String(7))  # Color hex (#FF0000)
    
    # Organización propietaria
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    # Estadísticas
    usage_count = Column(Integer, default=0)
    
    # Relaciones
    tasks = relationship("Task", secondary=task_labels, back_populates="labels")
    
    def __repr__(self):
        return f'<TaskLabel {self.name}>'


# Funciones de utilidad para el módulo
def get_task_statistics(organization_id: int = None, user_id: int = None,
                       project_id: int = None, date_from: date = None, 
                       date_to: date = None) -> dict[str, Any]:
    """Obtener estadísticas de tareas"""
    query = Task.query.filter(Task.is_deleted == False)
    
    if organization_id:
        query = query.filter(Task.organization_id == organization_id)
    
    if user_id:
        query = query.filter(
            (Task.assignee_id == user_id) |
            (Task.assignees.any(id=user_id)) |
            (Task.creator_id == user_id)
        )
    
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    if date_from:
        date_from_dt = datetime.combine(date_from, datetime.min.time())
        query = query.filter(Task.created_at >= date_from_dt)
    
    if date_to:
        date_to_dt = datetime.combine(date_to, datetime.max.time())
        query = query.filter(Task.created_at <= date_to_dt)
    
    tasks = query.all()
    
    if not tasks:
        return {
            'total_tasks': 0,
            'completion_rate': 0,
            'average_completion_time': 0,
            'overdue_tasks': 0,
            'blocked_tasks': 0
        }
    
    # Estadísticas básicas
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    overdue_tasks = len([t for t in tasks if t.is_overdue])
    blocked_tasks = len([t for t in tasks if t.is_blocked])
    
    # Tasa de finalización
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tiempo promedio de finalización
    completed_with_times = [
        t for t in tasks 
        if t.status == TaskStatus.COMPLETED and t.start_date and t.completed_at
    ]
    
    if completed_with_times:
        total_completion_time = sum(
            (t.completed_at - t.start_date).days 
            for t in completed_with_times
        )
        avg_completion_time = total_completion_time / len(completed_with_times)
    else:
        avg_completion_time = 0
    
    # Distribución por estado
    status_distribution = {}
    for task in tasks:
        status = task.status.value
        status_distribution[status] = status_distribution.get(status, 0) + 1
    
    # Distribución por prioridad
    priority_distribution = {}
    for task in tasks:
        priority = task.priority.value
        priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
    
    # Distribución por tipo
    type_distribution = {}
    for task in tasks:
        task_type = task.task_type.value
        type_distribution[task_type] = type_distribution.get(task_type, 0) + 1
    
    # Métricas de tiempo
    total_estimated_hours = sum(t.estimated_hours or 0 for t in tasks)
    total_actual_hours = sum(t.actual_hours or 0 for t in tasks)
    
    time_variance = 0
    if total_estimated_hours > 0:
        time_variance = ((total_actual_hours - total_estimated_hours) / total_estimated_hours) * 100
    
    # Análisis de colaboración
    tasks_with_multiple_assignees = len([t for t in tasks if t.assignee_count > 1])
    tasks_with_comments = len([t for t in tasks if t.comment_count > 0])
    tasks_with_subtasks = len([t for t in tasks if t.has_subtasks])
    
    return {
        'total_tasks': total_tasks,
        'completion_rate': round(completion_rate, 1),
        'average_completion_time_days': round(avg_completion_time, 1),
        'overdue_tasks': overdue_tasks,
        'blocked_tasks': blocked_tasks,
        'status_distribution': status_distribution,
        'priority_distribution': priority_distribution,
        'type_distribution': type_distribution,
        'time_tracking': {
            'total_estimated_hours': total_estimated_hours,
            'total_actual_hours': total_actual_hours,
            'time_variance_percentage': round(time_variance, 1),
            'tasks_with_time_tracking': len([t for t in tasks if t.estimated_hours or t.actual_hours])
        },
        'collaboration_metrics': {
            'tasks_with_multiple_assignees': tasks_with_multiple_assignees,
            'tasks_with_comments': tasks_with_comments,
            'tasks_with_subtasks': tasks_with_subtasks,
            'collaboration_rate': round(tasks_with_multiple_assignees / total_tasks * 100, 1) if total_tasks > 0 else 0
        },
        'productivity_insights': {
            'tasks_per_day': round(total_tasks / 30, 1) if total_tasks > 0 else 0,  # Último mes
            'average_progress': round(sum(t.progress_percentage for t in tasks) / total_tasks, 1) if total_tasks > 0 else 0,
            'high_priority_completion_rate': round(
                len([t for t in tasks if t.priority in [TaskPriority.HIGH, TaskPriority.HIGHEST, TaskPriority.CRITICAL] and t.is_completed]) /
                len([t for t in tasks if t.priority in [TaskPriority.HIGH, TaskPriority.HIGHEST, TaskPriority.CRITICAL]]) * 100, 1
            ) if any(t.priority in [TaskPriority.HIGH, TaskPriority.HIGHEST, TaskPriority.CRITICAL] for t in tasks) else 0
        }
    }


def update_overdue_task_notifications():
    """Actualizar notificaciones para tareas vencidas"""
    overdue_tasks = Task.get_overdue_tasks()
    notifications_sent = 0
    
    for task in overdue_tasks:
        # Verificar si ya se envió notificación hoy
        today = date.today()
        
        # En una implementación real, verificaríamos la tabla de notificaciones
        # Por ahora, enviamos notificación a todos los asignados
        
        for assignee in task.assignees:
            # Crear notificación (usando el sistema de mensajería)
            from .message import send_system_notification
            
            send_system_notification(
                user_ids=[assignee.id],
                title=f"Tarea Vencida: {task.title}",
                content=f"La tarea '{task.title}' venció el {task.due_date.strftime('%d/%m/%Y')}. Por favor, actualiza su estado.",
                notification_type='urgent',
                related_entity_type='task',
                related_entity_id=task.id
            )
            
            notifications_sent += 1
    
    return notifications_sent


def process_recurring_tasks():
    """Procesar tareas recurrentes y crear nuevas instancias"""
    recurring_tasks = Task.query.filter(
        Task.recurrence_pattern != RecurrencePattern.NONE,
        Task.next_occurrence_date <= datetime.now(timezone.utc),
        Task.is_deleted == False
    ).all()
    
    created_instances = 0
    
    for task in recurring_tasks:
        try:
            # Crear próxima instancia
            end_date = date.today() + timedelta(days=365)  # Un año adelante
            instances = task.create_recurring_instances(end_date, max_instances=1)
            created_instances += len(instances)
            
        except Exception as e:
            print(f"Error creando instancia recurrente para tarea {task.id}: {e}")
    
    return created_instances


def auto_update_task_progress():
    """Actualizar automáticamente el progreso de tareas padre basado en subtareas"""
    parent_tasks = Task.query.filter(
        Task.is_parent == True,
        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]),
        Task.is_deleted == False
    ).all()
    
    updated_count = 0
    
    for parent_task in parent_tasks:
        try:
            old_progress = parent_task.progress_percentage
            parent_task._update_parent_progress()
            
            if old_progress != parent_task.progress_percentage:
                updated_count += 1
                
        except Exception as e:
            print(f"Error actualizando progreso de tarea padre {parent_task.id}: {e}")
    
    return updated_count


def generate_task_burndown_data(project_id: int, sprint_start: date, 
                               sprint_end: date) -> dict[str, Any]:
    """Generar datos para gráfico burndown de tareas"""
    project_tasks = Task.query.filter(
        Task.project_id == project_id,
        Task.created_at <= datetime.combine(sprint_end, datetime.max.time()),
        Task.is_deleted == False
    ).all()
    
    if not project_tasks:
        return {'error': 'No hay tareas en el proyecto'}
    
    # Calcular work remaining por día
    current_date = sprint_start
    burndown_data = []
    
    while current_date <= sprint_end:
        # Tareas restantes al final del día
        day_end = datetime.combine(current_date, datetime.max.time())
        
        remaining_tasks = len([
            task for task in project_tasks
            if (task.completed_at is None or task.completed_at > day_end) and
               task.created_at <= day_end
        ])
        
        # Story points restantes
        remaining_points = sum(
            task.story_points or 1 for task in project_tasks
            if (task.completed_at is None or task.completed_at > day_end) and
               task.created_at <= day_end
        )
        
        burndown_data.append({
            'date': current_date.isoformat(),
            'remaining_tasks': remaining_tasks,
            'remaining_points': remaining_points
        })
        
        current_date += timedelta(days=1)
    
    # Línea ideal
    total_tasks = len(project_tasks)
    total_points = sum(task.story_points or 1 for task in project_tasks)
    sprint_days = (sprint_end - sprint_start).days + 1
    
    ideal_burndown = []
    for i, data_point in enumerate(burndown_data):
        ideal_tasks = total_tasks - (total_tasks * i / (sprint_days - 1))
        ideal_points = total_points - (total_points * i / (sprint_days - 1))
        
        ideal_burndown.append({
            'date': data_point['date'],
            'ideal_tasks': max(0, ideal_tasks),
            'ideal_points': max(0, ideal_points)
        })
    
    return {
        'actual_burndown': burndown_data,
        'ideal_burndown': ideal_burndown,
        'sprint_summary': {
            'start_date': sprint_start.isoformat(),
            'end_date': sprint_end.isoformat(),
            'total_tasks': total_tasks,
            'total_story_points': total_points,
            'completed_tasks': len([t for t in project_tasks if t.is_completed]),
            'completion_rate': len([t for t in project_tasks if t.is_completed]) / total_tasks * 100 if total_tasks > 0 else 0
        }
    }
