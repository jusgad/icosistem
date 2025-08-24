from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin, UserTrackingMixin
from app.core.exceptions import ValidationError


class ApplicationStatus(Enum):
    """Estados de aplicaciones"""
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'


class ApplicationType(Enum):
    """Tipos de aplicaciones"""
    PROGRAM = 'program'
    PROJECT = 'project'
    MENTORSHIP = 'mentorship'
    FUNDING = 'funding'
    WORKSHOP = 'workshop'


class Application(BaseModel, TimestampMixin, UserTrackingMixin):
    """Modelo para aplicaciones a programas"""
    __tablename__ = 'applications'
    __table_args__ = {'extend_existing': True}
    
    # Información básica
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    application_type = db.Column(db.Enum(ApplicationType), default=ApplicationType.PROGRAM, nullable=False)
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False)
    
    # Relaciones
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    
    # Fechas importantes
    submitted_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    decision_date = db.Column(db.Date)
    
    # Datos de la aplicación
    application_data = db.Column(db.JSON)
    
    # Revisión y feedback
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_notes = db.Column(db.Text)
    rejection_reason = db.Column(db.String(500))
    
    # Métricas
    score = db.Column(db.Float)  # Puntuación de 0-100
    priority = db.Column(db.String(20), default='medium')
    
    # Relaciones
    applicant = db.relationship('User', foreign_keys=[applicant_id], backref='applications')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='reviewed_applications')
    program = db.relationship('Program', backref='applications', lazy='select')
    project = db.relationship('Project', backref='applications', lazy='select')
    
    def __repr__(self):
        return f'<Application {self.title}>'
    
    @property
    def status_display(self) -> str:
        """Mostrar estado legible"""
        status_map = {
            ApplicationStatus.DRAFT: 'Borrador',
            ApplicationStatus.SUBMITTED: 'Enviada',
            ApplicationStatus.UNDER_REVIEW: 'En Revisión',
            ApplicationStatus.APPROVED: 'Aprobada',
            ApplicationStatus.REJECTED: 'Rechazada',
            ApplicationStatus.WITHDRAWN: 'Retirada'
        }
        return status_map.get(self.status, self.status.value)
    
    @property
    def type_display(self) -> str:
        """Mostrar tipo legible"""
        type_map = {
            ApplicationType.PROGRAM: 'Programa',
            ApplicationType.PROJECT: 'Proyecto',
            ApplicationType.MENTORSHIP: 'Mentoría',
            ApplicationType.FUNDING: 'Financiamiento',
            ApplicationType.WORKSHOP: 'Taller'
        }
        return type_map.get(self.application_type, self.application_type.value)
    
    @property
    def days_since_submission(self) -> Optional[int]:
        """Días desde la submisión"""
        if not self.submitted_at:
            return None
        delta = datetime.utcnow() - self.submitted_at
        return delta.days
    
    @property
    def is_overdue(self) -> bool:
        """Verificar si la revisión está atrasada"""
        if self.status != ApplicationStatus.UNDER_REVIEW:
            return False
        return self.days_since_submission and self.days_since_submission > 14
    
    def submit(self) -> bool:
        """Enviar aplicación para revisión"""
        if self.status != ApplicationStatus.DRAFT:
            return False
        
        self.status = ApplicationStatus.SUBMITTED
        self.submitted_at = datetime.utcnow()
        return True
    
    def start_review(self, reviewer_id: int) -> bool:
        """Iniciar proceso de revisión"""
        if self.status != ApplicationStatus.SUBMITTED:
            return False
        
        self.status = ApplicationStatus.UNDER_REVIEW
        self.reviewer_id = reviewer_id
        return True
    
    def approve(self, notes: str = None) -> bool:
        """Aprobar aplicación"""
        if self.status != ApplicationStatus.UNDER_REVIEW:
            return False
        
        self.status = ApplicationStatus.APPROVED
        self.reviewed_at = datetime.utcnow()
        self.decision_date = date.today()
        if notes:
            self.review_notes = notes
        return True
    
    def reject(self, reason: str, notes: str = None) -> bool:
        """Rechazar aplicación"""
        if self.status != ApplicationStatus.UNDER_REVIEW:
            return False
        
        self.status = ApplicationStatus.REJECTED
        self.reviewed_at = datetime.utcnow()
        self.decision_date = date.today()
        self.rejection_reason = reason
        if notes:
            self.review_notes = notes
        return True
    
    def withdraw(self) -> bool:
        """Retirar aplicación"""
        if self.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]:
            return False
        
        self.status = ApplicationStatus.WITHDRAWN
        return True
    
    @classmethod
    def get_pending_review(cls) -> List['Application']:
        """Obtener aplicaciones pendientes de revisión"""
        return cls.query.filter_by(status=ApplicationStatus.UNDER_REVIEW).all()
    
    @classmethod
    def get_overdue_reviews(cls) -> List['Application']:
        """Obtener revisiones vencidas"""
        cutoff_date = datetime.utcnow() - timedelta(days=14)
        return cls.query.filter(
            cls.status == ApplicationStatus.UNDER_REVIEW,
            cls.submitted_at <= cutoff_date
        ).all()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'application_type': self.application_type.value,
            'type_display': self.type_display,
            'status': self.status.value,
            'status_display': self.status_display,
            'applicant_id': self.applicant_id,
            'program_id': self.program_id,
            'project_id': self.project_id,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'reviewer_id': self.reviewer_id,
            'review_notes': self.review_notes,
            'rejection_reason': self.rejection_reason,
            'score': self.score,
            'priority': self.priority,
            'days_since_submission': self.days_since_submission,
            'is_overdue': self.is_overdue,
            'application_data': self.application_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }