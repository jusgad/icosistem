from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from app.extensions import db
import enum


class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(db.Model):
    """Modelo para las tareas asignadas a emprendedores y aliados."""
    
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Estado y prioridad
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    
    # Fechas
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relaciones
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = relationship('User', foreign_keys=[created_by_id])
    
    assigned_to_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    assigned_to = relationship('User', foreign_keys=[assigned_to_id])
    
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=True)
    entrepreneur = relationship('Entrepreneur', back_populates='tasks')
    
    ally_id = Column(Integer, ForeignKey('allies.id'), nullable=True)
    ally = relationship('Ally', back_populates='tasks')
    
    # Relación con documentos
    documents = relationship('Document', back_populates='task')
    
    # Relación con reuniones
    meeting_id = Column(Integer, ForeignKey('meetings.id'), nullable=True)
    meeting = relationship('Meeting', back_populates='tasks')
    
    # Para tareas recurrentes o dependientes
    parent_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    subtasks = relationship('Task', 
                           backref=db.backref('parent_task', remote_side=[id]),
                           foreign_keys=[parent_task_id])
    
    # Campos adicionales
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)  # Ej: "daily", "weekly", "monthly"
    recurrence_count = Column(Integer, nullable=True)        # Número de repeticiones
    progress = Column(Integer, default=0)                    # Porcentaje de progreso (0-100)
    
    # Notificaciones
    notify_before = Column(Integer, nullable=True)  # Minutos antes para notificar
    
    def __repr__(self):
        return f'<Task {self.title} ({self.status.value})>'
    
    def to_dict(self):
        """Convierte el modelo a un diccionario."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_by_id': self.created_by_id,
            'assigned_to_id': self.assigned_to_id,
            'entrepreneur_id': self.entrepreneur_id,
            'ally_id': self.ally_id,
            'meeting_id': self.meeting_id,
            'parent_task_id': self.parent_task_id,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'recurrence_count': self.recurrence_count,
            'progress': self.progress,
            'notify_before': self.notify_before,
            'documents': [doc.id for doc in self.documents]
        }
    
    def complete(self):
        """Marca la tarea como completada."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100
        return self
    
    def cancel(self):
        """Cancela la tarea."""
        self.status = TaskStatus.CANCELLED
        return self
    
    def start(self):
        """Inicia la tarea."""
        self.status = TaskStatus.IN_PROGRESS
        if self.progress == 0:
            self.progress = 5  # Asignar un progreso inicial mínimo
        return self
    
    def send_to_review(self):
        """Envía la tarea a revisión."""
        self.status = TaskStatus.REVIEW
        self.progress = 90  # Casi completada, pendiente de revisión
        return self
    
    def update_progress(self, progress):
        """Actualiza el progreso de la tarea."""
        if 0 <= progress <= 100:
            self.progress = progress
            
            # Actualizar automáticamente el estado basado en el progreso
            if progress == 0:
                self.status = TaskStatus.PENDING
            elif progress == 100:
                self.status = TaskStatus.COMPLETED
                self.completed_at = datetime.utcnow()
            elif progress >= 90:
                self.status = TaskStatus.REVIEW
            else:
                self.status = TaskStatus.IN_PROGRESS
        return self
    
    def create_subtask(self, title, description=None, due_date=None, **kwargs):
        """Crea una subtarea asociada a esta tarea."""
        subtask = Task(
            title=title,
            description=description,
            due_date=due_date,
            created_by_id=self.created_by_id,
            entrepreneur_id=self.entrepreneur_id,
            ally_id=self.ally_id,
            parent_task_id=self.id,
            **kwargs
        )
        return subtask
    
    def create_recurring_tasks(self):
        """Crea tareas recurrentes basadas en la configuración."""
        if not self.is_recurring or not self.recurrence_pattern or not self.recurrence_count:
            return []
            
        # Implementación básica - expandir según necesidades
        recurring_tasks = []
        for i in range(1, self.recurrence_count + 1):
            # Calcular nueva fecha de vencimiento según el patrón
            if self.due_date:
                if self.recurrence_pattern == "daily":
                    new_due_date = self.due_date + datetime.timedelta(days=i)
                elif self.recurrence_pattern == "weekly":
                    new_due_date = self.due_date + datetime.timedelta(weeks=i)
                elif self.recurrence_pattern == "monthly":
                    # Aproximación simple - un mes es 30 días
                    new_due_date = self.due_date + datetime.timedelta(days=30*i)
                else:
                    new_due_date = None
            else:
                new_due_date = None
                
            # Crear nueva tarea recurrente
            task = Task(
                title=f"{self.title} (recurrente {i+1})",
                description=self.description,
                due_date=new_due_date,
                created_by_id=self.created_by_id,
                entrepreneur_id=self.entrepreneur_id,
                ally_id=self.ally_id,
                priority=self.priority,
                parent_task_id=self.id
            )
            recurring_tasks.append(task)
            
        return recurring_tasks
    
    @classmethod
    def get_pending_for_entrepreneur(cls, entrepreneur_id):
        """Retorna tareas pendientes para un emprendedor."""
        return cls.query.filter_by(
            entrepreneur_id=entrepreneur_id
        ).filter(
            cls.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW])
        ).order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_pending_for_ally(cls, ally_id):
        """Retorna tareas pendientes para un aliado."""
        return cls.query.filter_by(
            ally_id=ally_id
        ).filter(
            cls.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW])
        ).order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_overdue(cls):
        """Retorna todas las tareas vencidas no completadas."""
        now = datetime.utcnow()
        return cls.query.filter(
            cls.due_date < now,
            cls.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
        ).order_by(cls.due_date.asc()).all()
    
    @property
    def is_overdue(self):
        """Verifica si la tarea está vencida."""
        if self.due_date and self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return self.due_date < datetime.utcnow()
        return False
    
    @property
    def days_remaining(self):
        """Calcula días restantes hasta la fecha de vencimiento."""
        if self.due_date:
            delta = self.due_date - datetime.utcnow()
            return max(0, delta.days)
        return None
    
    @property
    def has_subtasks(self):
        """Verifica si la tarea tiene subtareas."""
        return len(self.subtasks) > 0