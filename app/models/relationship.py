from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.extensions import db

class Relationship(db.Model):
    """Modelo para gestionar la relación entre un emprendedor y un aliado/mentor"""
    __tablename__ = 'relationships'

    id = Column(Integer, primary_key=True)
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=False)
    ally_id = Column(Integer, ForeignKey('allies.id'), nullable=False)
    
    # Estado de la relación
    status = Column(String(20), default='active')  # active, paused, completed, terminated
    
    # Fechas de la relación
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    
    # Objetivos y metas
    goals = Column(Text, nullable=True)
    success_metrics = Column(Text, nullable=True)
    
    # Contador de horas y reuniones
    total_hours = Column(Float, default=0.0)  # Total de horas registradas
    total_meetings = Column(Integer, default=0)  # Total de reuniones realizadas
    
    # Evaluación de la relación
    entrepreneur_satisfaction = Column(Integer, nullable=True)  # Escala 1-5
    ally_satisfaction = Column(Integer, nullable=True)  # Escala 1-5
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # Usuario que creó la relación
    
    # Relaciones
    entrepreneur = relationship('Entrepreneur', backref='relationships')
    ally = relationship('Ally', backref='relationships')
    meetings = relationship('Meeting', backref='relationship', lazy='dynamic')
    tasks = relationship('Task', backref='relationship', lazy='dynamic')
    hour_logs = relationship('HourLog', backref='relationship', lazy='dynamic')
    progress_reports = relationship('ProgressReport', backref='relationship', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('entrepreneur_id', 'ally_id', name='uix_relationship'),
    )
    
    def __init__(self, entrepreneur_id, ally_id, **kwargs):
        self.entrepreneur_id = entrepreneur_id
        self.ally_id = ally_id
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        return f'<Relationship {self.entrepreneur_id}-{self.ally_id}>'
    
    @hybrid_property
    def is_active(self):
        """Verifica si la relación está activa"""
        return self.status == 'active'
    
    @hybrid_property
    def duration_days(self):
        """Calcula la duración de la relación en días"""
        end = self.end_date or datetime.utcnow()
        return (end - self.start_date).days
    
    def log_hours(self, hours, activity_type, description, date=None):
        """Registra horas de mentoría/acompañamiento"""
        from app.models.hour_log import HourLog
        
        if date is None:
            date = datetime.utcnow()
            
        hour_log = HourLog(
            relationship_id=self.id,
            hours=hours,
            activity_type=activity_type,
            description=description,
            date=date
        )
        
        db.session.add(hour_log)
        self.total_hours += hours
        db.session.commit()
        
        return hour_log
    
    def add_meeting(self, title, start_time, end_time, meeting_type, description=None, location=None):
        """Crea una nueva reunión asociada a esta relación"""
        from app.models.meeting import Meeting
        
        meeting = Meeting(
            relationship_id=self.id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            meeting_type=meeting_type,
            description=description,
            location=location
        )
        
        db.session.add(meeting)
        self.total_meetings += 1
        db.session.commit()
        
        return meeting
    
    def add_task(self, title, description, due_date, assigned_to):
        """Crea una nueva tarea asociada a esta relación"""
        from app.models.task import Task
        
        task = Task(
            relationship_id=self.id,
            title=title,
            description=description,
            due_date=due_date,
            assigned_to=assigned_to
        )
        
        db.session.add(task)
        db.session.commit()
        
        return task
    
    def complete_relationship(self, entrepreneur_satisfaction=None, ally_satisfaction=None):
        """Marca la relación como completada"""
        self.status = 'completed'
        self.end_date = datetime.utcnow()
        
        if entrepreneur_satisfaction:
            self.entrepreneur_satisfaction = entrepreneur_satisfaction
            
        if ally_satisfaction:
            self.ally_satisfaction = ally_satisfaction
            
        db.session.commit()
    
    def get_progress_metrics(self):
        """Obtiene métricas de progreso para esta relación"""
        completed_tasks = self.tasks.filter_by(status='completed').count()
        total_tasks = self.tasks.count()
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            'duration_days': self.duration_days,
            'total_hours': self.total_hours,
            'total_meetings': self.total_meetings,
            'tasks_completion_rate': task_completion_rate,
            'entrepreneur_satisfaction': self.entrepreneur_satisfaction,
            'ally_satisfaction': self.ally_satisfaction
        }
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs"""
        return {
            'id': self.id,
            'entrepreneur_id': self.entrepreneur_id,
            'ally_id': self.ally_id,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_hours': self.total_hours,
            'total_meetings': self.total_meetings,
            'duration_days': self.duration_days,
            'is_active': self.is_active
        }


class HourLog(db.Model):
    """Modelo para registrar horas de mentoría/acompañamiento"""
    __tablename__ = 'hour_logs'
    
    id = Column(Integer, primary_key=True)
    relationship_id = Column(Integer, ForeignKey('relationships.id'), nullable=False)
    hours = Column(Float, nullable=False)
    activity_type = Column(String(50), nullable=False)  # meeting, call, review, etc.
    description = Column(Text, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # Usuario que registró las horas
    
    def __repr__(self):
        return f'<HourLog {self.id}: {self.hours}h - {self.activity_type}>'


class ProgressReport(db.Model):
    """Modelo para informes de progreso periódicos"""
    __tablename__ = 'progress_reports'
    
    id = Column(Integer, primary_key=True)
    relationship_id = Column(Integer, ForeignKey('relationships.id'), nullable=False)
    
    report_date = Column(DateTime, default=datetime.utcnow)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Contenido del informe
    goals_achieved = Column(Text, nullable=True)
    challenges = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)
    hours_invested = Column(Float, default=0.0)
    
    # Métricas específicas del emprendimiento
    metrics = Column(Text, nullable=True)  # JSON con métricas
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    def __repr__(self):
        return f'<ProgressReport {self.id}: {self.period_start.strftime("%Y-%m-%d")} to {self.period_end.strftime("%Y-%m-%d")}>'