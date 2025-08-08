"""
Modelo Programa del Ecosistema de Emprendimiento

Este módulo define el modelo para programas de emprendimiento ofrecidos por organizaciones,
incluyendo incubación, aceleración, mentoría, capacitación, etc.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from app.extensions import db
from ..core.constants import (
    PROGRAM_TYPES,
    PROGRAM_STATUS,
    INDUSTRY_SECTORS,
    ENTREPRENEUR_STAGES,
    CURRENCIES,
    PROGRAM_FORMATS,
    SELECTION_CRITERIA
)
from ..core.exceptions import ValidationError


class ProgramType(Enum):
    """Tipos de programa"""
    INCUBATION = "incubation"
    ACCELERATION = "acceleration"
    MENTORSHIP = "mentorship"
    TRAINING = "training"
    BOOTCAMP = "bootcamp"
    WORKSHOP = "workshop"
    MASTERCLASS = "masterclass"
    COMPETITION = "competition"
    PITCH_EVENT = "pitch_event"
    NETWORKING = "networking"
    FUNDING = "funding"
    PRE_INCUBATION = "pre_incubation"
    SCALE_UP = "scale_up"
    CORPORATE_INNOVATION = "corporate_innovation"
    SOCIAL_IMPACT = "social_impact"


class ProgramStatus(Enum):
    """Estados del programa"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    FULL = "full"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class ProgramFormat(Enum):
    """Formato del programa"""
    PRESENTIAL = "presential"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    SELF_PACED = "self_paced"


class SelectionProcess(Enum):
    """Proceso de selección"""
    OPEN = "open"
    APPLICATION = "application"
    INVITATION = "invitation"
    COMPETITION = "competition"
    INTERVIEW = "interview"
    PORTFOLIO = "portfolio"


class EnrollmentStatus(Enum):
    """Estados de inscripción"""
    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    COMPLETED = "completed"
    GRADUATED = "graduated"
    DROPPED_OUT = "dropped_out"
    SUSPENDED = "suspended"


# Tabla de asociación para mentores del programa
program_mentors = Table(
    'program_mentors',
    db.metadata,
    Column('program_id', Integer, ForeignKey('programs.id'), primary_key=True),
    Column('mentor_id', Integer, ForeignKey('allies.id'), primary_key=True),
    Column('role', String(50), default='mentor'),
    Column('specialization', String(100)),
    Column('hours_committed', Integer, default=0),
    Column('start_date', Date),
    Column('end_date', Date),
    Column('status', String(20), default='active'),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para partners del programa
program_partners = Table(
    'program_partners',
    db.metadata,
    Column('program_id', Integer, ForeignKey('programs.id'), primary_key=True),
    Column('organization_id', Integer, ForeignKey('organizations.id'), primary_key=True),
    Column('partnership_type', String(50)),
    Column('contribution', Text),
    Column('start_date', Date),
    Column('end_date', Date),
    Column('status', String(20), default='active'),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Program(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Programa
    
    Representa programas de emprendimiento ofrecidos por organizaciones,
    con todas las características necesarias para gestión completa.
    """
    
    __tablename__ = 'programs'
    
    # Información básica
    name = Column(String(200), nullable=False, index=True)
    slug = Column(String(150), unique=True, nullable=False, index=True)
    program_type = Column(SQLEnum(ProgramType), nullable=False, index=True)
    status = Column(SQLEnum(ProgramStatus), default=ProgramStatus.DRAFT, index=True)
    
    # Descripción y objetivos
    short_description = Column(String(300))
    description = Column(Text)
    objectives = Column(JSON)  # Lista de objetivos
    methodology = Column(Text)
    curriculum = Column(JSON)  # Estructura del currículum
    
    # Organización responsable
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False, index=True)
    organization = relationship("Organization", back_populates="programs")
    
    # Coordinador/Director del programa
    coordinator_id = Column(Integer, ForeignKey('users.id'))
    coordinator = relationship("User", foreign_keys=[coordinator_id])
    
    # Fechas y duración
    start_date = Column(Date)
    end_date = Column(Date)
    application_deadline = Column(Date)
    announcement_date = Column(Date)
    duration_weeks = Column(Integer)
    duration_hours = Column(Integer)
    
    # Formato y modalidad
    program_format = Column(SQLEnum(ProgramFormat), default=ProgramFormat.HYBRID)
    location = Column(String(200))  # Ubicación física si aplica
    timezone = Column(String(50), default='UTC')
    language = Column(String(10), default='es')
    
    # Capacidad y participantes
    max_participants = Column(Integer)
    min_participants = Column(Integer, default=1)
    current_participants = Column(Integer, default=0)
    target_audience = Column(JSON)  # Audiencia objetivo
    
    # Criterios de selección
    selection_process = Column(SQLEnum(SelectionProcess), default=SelectionProcess.APPLICATION)
    selection_criteria = Column(JSON)  # Criterios específicos
    requirements = Column(JSON)  # Requisitos para aplicar
    
    # Sectores y etapas objetivo
    target_sectors = Column(JSON)  # Sectores de industria objetivo
    target_stages = Column(JSON)  # Etapas de emprendimiento objetivo
    
    # Información financiera
    cost = Column(Integer)  # Costo en centavos
    currency = Column(String(3), default='USD')
    scholarships_available = Column(Integer, default=0)
    funding_provided = Column(Integer)  # Financiamiento proporcionado
    equity_percentage = Column(Float)  # Porcentaje de equity si aplica
    
    # Beneficios y recursos
    benefits = Column(JSON)  # Lista de beneficios
    resources_provided = Column(JSON)  # Recursos proporcionados
    mentorship_hours = Column(Integer)
    office_space = Column(Boolean, default=False)
    legal_support = Column(Boolean, default=False)
    
    # Configuración de aplicación
    is_public = Column(Boolean, default=True)
    accepts_applications = Column(Boolean, default=True)
    application_form = Column(JSON)  # Configuración del formulario
    documents_required = Column(JSON)  # Documentos requeridos
    
    # Métricas y resultados
    graduation_rate = Column(Float, default=0.0)
    job_creation_rate = Column(Float, default=0.0)
    funding_success_rate = Column(Float, default=0.0)
    average_funding_raised = Column(Integer, default=0)
    
    # SEO y marketing
    meta_description = Column(String(160))
    keywords = Column(JSON)
    promotional_image = Column(String(500))  # URL de imagen promocional
    promotional_video = Column(String(500))  # URL de video promocional
    
    # Configuración avanzada
    custom_fields = Column(JSON)
    automation_settings = Column(JSON)  # Configuración de automatizaciones
    notification_settings = Column(JSON)
    
    # Certificación
    provides_certificate = Column(Boolean, default=False)
    certificate_template = Column(String(500))  # Plantilla de certificado
    accreditation_body = Column(String(200))
    
    # Evaluación y feedback
    evaluation_criteria = Column(JSON)  # Criterios de evaluación
    feedback_mechanism = Column(JSON)  # Mecanismo de retroalimentación
    
    # Relaciones
    
    # Inscripciones/Participantes
    enrollments = relationship("ProgramEnrollment", back_populates="program")
    
    # Mentores asignados
    mentors = relationship("Ally", 
                          secondary=program_mentors,
                          back_populates="programs_mentoring")
    
    # Organizaciones partner
    partner_organizations = relationship("Organization",
                                       secondary=program_partners,
                                       back_populates="partnered_programs")
    
    # Sesiones del programa
    sessions = relationship("ProgramSession", back_populates="program")
    
    # Tareas y asignaciones
    assignments = relationship("Assignment", back_populates="program")
    
    # Eventos relacionados
    events = relationship("Event", back_populates="program")
    
    # Documentos del programa
    documents = relationship("Document", back_populates="program")
    
    # Evaluaciones
    evaluations = relationship("Evaluation", back_populates="program")
    
    # Actividades y logs
    activities = relationship("ActivityLog", back_populates="program")
    
    # Analytics del programa
    analytics = relationship("ProgramAnalytics", back_populates="program")
    
    def __init__(self, **kwargs):
        """Inicialización del programa"""
        super().__init__(**kwargs)
        
        # Generar slug si no se proporciona
        if not self.slug and self.name:
            self.slug = self._generate_slug(self.name)
        
        # Configuraciones por defecto
        if not self.notification_settings:
            self.notification_settings = {
                'new_applications': True,
                'participant_updates': True,
                'milestone_reminders': True,
                'completion_alerts': True
            }
        
        if not self.automation_settings:
            self.automation_settings = {
                'welcome_email': True,
                'reminder_emails': True,
                'completion_certificates': True,
                'feedback_requests': True
            }
    
    def __repr__(self):
        return f'<Program {self.name} ({self.program_type.value})>'
    
    def __str__(self):
        return f'{self.name} - {self.organization.name if self.organization else "Sin organización"}'
    
    # Métodos de generación
    def _generate_slug(self, name: str) -> str:
        """Generar slug único basado en el nombre"""
        import unicodedata
        
        # Normalizar y limpiar el nombre
        slug = unicodedata.normalize('NFKD', name.lower())
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Verificar unicidad
        original_slug = slug
        counter = 1
        
        while Program.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
    
    # Validaciones
    @validates('name')
    def validate_name(self, key, name):
        """Validar nombre del programa"""
        if not name or len(name.strip()) < 3:
            raise ValidationError("El nombre debe tener al menos 3 caracteres")
        if len(name) > 200:
            raise ValidationError("El nombre no puede exceder 200 caracteres")
        return name.strip()
    
    @validates('slug')
    def validate_slug(self, key, slug):
        """Validar slug único"""
        if slug:
            if not re.match(r'^[a-z0-9-]+$', slug):
                raise ValidationError("El slug solo puede contener letras minúsculas, números y guiones")
            if len(slug) > 150:
                raise ValidationError("El slug no puede exceder 150 caracteres")
        return slug
    
    @validates('start_date', 'end_date', 'application_deadline')
    def validate_dates(self, key, date_value):
        """Validar fechas del programa"""
        if date_value:
            if key == 'end_date' and self.start_date:
                if date_value <= self.start_date:
                    raise ValidationError("La fecha de fin debe ser posterior a la de inicio")
            
            if key == 'application_deadline':
                if self.start_date and date_value >= self.start_date:
                    raise ValidationError("La fecha límite de aplicación debe ser anterior al inicio")
                if date_value < date.today():
                    raise ValidationError("La fecha límite no puede ser pasada")
        
        return date_value
    
    @validates('duration_weeks')
    def validate_duration_weeks(self, key, weeks):
        """Validar duración en semanas"""
        if weeks is not None:
            if weeks < 1 or weeks > 104:  # Máximo 2 años
                raise ValidationError("La duración debe estar entre 1 y 104 semanas")
        return weeks
    
    @validates('max_participants', 'min_participants')
    def validate_participants(self, key, value):
        """Validar número de participantes"""
        if value is not None:
            if value < 1:
                raise ValidationError("El número de participantes debe ser mayor a 0")
            if key == 'max_participants' and value > 1000:
                raise ValidationError("El máximo de participantes no puede exceder 1000")
            if key == 'min_participants' and self.max_participants:
                if value > self.max_participants:
                    raise ValidationError("El mínimo no puede ser mayor al máximo")
        return value
    
    @validates('cost', 'funding_provided')
    def validate_financial(self, key, value):
        """Validar valores financieros"""
        if value is not None and value < 0:
            raise ValidationError("Los valores financieros no pueden ser negativos")
        return value
    
    @validates('equity_percentage')
    def validate_equity(self, key, value):
        """Validar porcentaje de equity"""
        if value is not None:
            if value < 0 or value > 100:
                raise ValidationError("El porcentaje de equity debe estar entre 0 y 100")
        return value
    
    @validates('target_sectors')
    def validate_target_sectors(self, key, sectors):
        """Validar sectores objetivo"""
        if sectors:
            if not isinstance(sectors, list):
                raise ValidationError("Los sectores objetivo deben ser una lista")
            valid_sectors = INDUSTRY_SECTORS
            for sector in sectors:
                if sector not in valid_sectors:
                    raise ValidationError(f"Sector '{sector}' no válido")
        return sectors
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si el programa está activo"""
        return (self.status in [ProgramStatus.ACTIVE, ProgramStatus.IN_PROGRESS] 
                and not self.is_deleted)
    
    @hybrid_property
    def is_accepting_applications(self):
        """Verificar si acepta aplicaciones"""
        if not self.accepts_applications or self.status != ProgramStatus.PUBLISHED:
            return False
        
        if self.application_deadline and self.application_deadline < date.today():
            return False
        
        if self.max_participants and self.current_participants >= self.max_participants:
            return False
        
        return True
    
    @hybrid_property
    def is_full(self):
        """Verificar si está lleno"""
        return (self.max_participants and 
                self.current_participants >= self.max_participants)
    
    @hybrid_property
    def days_until_start(self):
        """Días hasta el inicio"""
        if self.start_date:
            return (self.start_date - date.today()).days
        return None
    
    @hybrid_property
    def days_until_deadline(self):
        """Días hasta la fecha límite"""
        if self.application_deadline:
            return (self.application_deadline - date.today()).days
        return None
    
    @hybrid_property
    def duration_formatted(self):
        """Duración formateada"""
        parts = []
        if self.duration_weeks:
            parts.append(f"{self.duration_weeks} semanas")
        if self.duration_hours:
            parts.append(f"{self.duration_hours} horas")
        return " / ".join(parts) if parts else None
    
    @hybrid_property
    def cost_formatted(self):
        """Costo formateado"""
        if self.cost:
            return f"{self.currency} {self.cost / 100:,.2f}"
        return "Gratis"
    
    @hybrid_property
    def funding_formatted(self):
        """Financiamiento формateado"""
        if self.funding_provided:
            return f"{self.currency} {self.funding_provided / 100:,.2f}"
        return None
    
    @hybrid_property
    def occupancy_rate(self):
        """Tasa de ocupación"""
        if self.max_participants:
            return (self.current_participants / self.max_participants) * 100
        return 0
    
    # Métodos de negocio
    def get_active_enrollments(self):
        """Obtener inscripciones activas"""
        return self.enrollments.filter(
            ProgramEnrollment.status.in_([
                EnrollmentStatus.ENROLLED,
                EnrollmentStatus.ACTIVE
            ])
        ).all()
    
    def get_applications(self, status=None):
        """Obtener aplicaciones"""
        query = self.enrollments
        
        if status:
            if isinstance(status, list):
                query = query.filter(ProgramEnrollment.status.in_(status))
            else:
                query = query.filter(ProgramEnrollment.status == status)
        
        return query.order_by(ProgramEnrollment.created_at.desc()).all()
    
    def get_pending_applications(self):
        """Obtener aplicaciones pendientes"""
        return self.get_applications([
            EnrollmentStatus.APPLIED,
            EnrollmentStatus.UNDER_REVIEW
        ])
    
    def can_apply(self, entrepreneur) -> Dict[str, Any]:
        """Verificar si un emprendedor puede aplicar"""
        result = {
            'can_apply': True,
            'reasons': []
        }
        
        # Verificar estado del programa
        if not self.is_accepting_applications:
            result['can_apply'] = False
            if self.status != ProgramStatus.PUBLISHED:
                result['reasons'].append("Programa no publicado")
            if self.is_full:
                result['reasons'].append("Programa completo")
            if self.application_deadline and self.application_deadline < date.today():
                result['reasons'].append("Fecha límite vencida")
        
        # Verificar si ya aplicó
        existing_application = ProgramEnrollment.query.filter_by(
            program_id=self.id,
            entrepreneur_id=entrepreneur.id
        ).first()
        
        if existing_application:
            result['can_apply'] = False
            result['reasons'].append(f"Ya tiene una aplicación: {existing_application.status.value}")
        
        # Verificar requisitos específicos
        if self.requirements:
            missing_requirements = self._check_requirements(entrepreneur)
            if missing_requirements:
                result['can_apply'] = False
                result['reasons'].extend([f"Requisito faltante: {req}" for req in missing_requirements])
        
        return result
    
    def _check_requirements(self, entrepreneur) -> List[str]:
        """Verificar requisitos específicos"""
        missing = []
        
        if not self.requirements:
            return missing
        
        # Verificar edad mínima
        if self.requirements.get('min_age'):
            if not entrepreneur.age or entrepreneur.age < self.requirements['min_age']:
                missing.append(f"Edad mínima: {self.requirements['min_age']} años")
        
        # Verificar nivel educativo
        if self.requirements.get('education_level'):
            required_level = self.requirements['education_level']
            if not entrepreneur.education_level or entrepreneur.education_level != required_level:
                missing.append(f"Nivel educativo: {required_level}")
        
        # Verificar sector
        if self.target_sectors:
            if not entrepreneur.industry_sector or entrepreneur.industry_sector not in self.target_sectors:
                missing.append(f"Sector objetivo: {', '.join(self.target_sectors)}")
        
        # Verificar etapa del emprendimiento
        if self.target_stages:
            if not entrepreneur.business_stage or entrepreneur.business_stage not in self.target_stages:
                missing.append(f"Etapa objetivo: {', '.join(self.target_stages)}")
        
        return missing
    
    def enroll_entrepreneur(self, entrepreneur, application_data=None):
        """Inscribir un emprendedor"""
        # Verificar si puede aplicar
        can_apply_result = self.can_apply(entrepreneur)
        if not can_apply_result['can_apply']:
            raise ValidationError(f"No puede aplicar: {'; '.join(can_apply_result['reasons'])}")
        
        # Crear inscripción
        enrollment = ProgramEnrollment(
            program_id=self.id,
            entrepreneur_id=entrepreneur.id,
            status=EnrollmentStatus.APPLIED,
            application_data=application_data or {},
            applied_at=datetime.utcnow()
        )
        
        from .. import db
        db.session.add(enrollment)
        
        # Si es proceso abierto, aprobar automáticamente
        if self.selection_process == SelectionProcess.OPEN:
            enrollment.status = EnrollmentStatus.ENROLLED
            enrollment.enrolled_at = datetime.utcnow()
            self.current_participants += 1
        
        return enrollment
    
    def approve_application(self, enrollment_id, notes=None):
        """Aprobar una aplicación"""
        enrollment = ProgramEnrollment.query.get(enrollment_id)
        if not enrollment or enrollment.program_id != self.id:
            raise ValidationError("Inscripción no encontrada")
        
        if enrollment.status not in [EnrollmentStatus.APPLIED, EnrollmentStatus.UNDER_REVIEW]:
            raise ValidationError("La aplicación no está en estado válido para aprobación")
        
        if self.is_full:
            raise ValidationError("El programa está completo")
        
        enrollment.status = EnrollmentStatus.ACCEPTED
        enrollment.approved_at = datetime.utcnow()
        enrollment.reviewer_notes = notes
        
        return enrollment
    
    def reject_application(self, enrollment_id, reason=None):
        """Rechazar una aplicación"""
        enrollment = ProgramEnrollment.query.get(enrollment_id)
        if not enrollment or enrollment.program_id != self.id:
            raise ValidationError("Inscripción no encontrada")
        
        enrollment.status = EnrollmentStatus.REJECTED
        enrollment.rejected_at = datetime.utcnow()
        enrollment.rejection_reason = reason
        
        return enrollment
    
    def start_program(self):
        """Iniciar el programa"""
        if self.status != ProgramStatus.PUBLISHED:
            raise ValidationError("El programa debe estar publicado para iniciar")
        
        if self.current_participants < self.min_participants:
            raise ValidationError(f"Se requieren al menos {self.min_participants} participantes")
        
        self.status = ProgramStatus.IN_PROGRESS
        self.actual_start_date = date.today()
        
        # Actualizar estado de inscripciones aceptadas
        accepted_enrollments = self.enrollments.filter(
            ProgramEnrollment.status == EnrollmentStatus.ACCEPTED
        ).all()
        
        for enrollment in accepted_enrollments:
            enrollment.status = EnrollmentStatus.ACTIVE
        
        self.current_participants = len(accepted_enrollments)
    
    def complete_program(self):
        """Completar el programa"""
        if self.status != ProgramStatus.IN_PROGRESS:
            raise ValidationError("El programa debe estar en progreso para completar")
        
        self.status = ProgramStatus.COMPLETED
        self.actual_end_date = date.today()
        
        # Procesar graduaciones
        active_enrollments = self.enrollments.filter(
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE
        ).all()
        
        for enrollment in active_enrollments:
            if self._meets_graduation_criteria(enrollment):
                enrollment.status = EnrollmentStatus.GRADUATED
                enrollment.graduated_at = datetime.utcnow()
                
                # Generar certificado si aplica
                if self.provides_certificate:
                    self._generate_certificate(enrollment)
            else:
                enrollment.status = EnrollmentStatus.COMPLETED
        
        # Actualizar métricas
        self._update_success_metrics()
    
    def _meets_graduation_criteria(self, enrollment) -> bool:
        """Verificar si cumple criterios de graduación"""
        if not self.evaluation_criteria:
            return True  # Sin criterios específicos, todos gradúan
        
        # Implementar lógica específica de evaluación
        # Por ahora, criterio simple de asistencia
        min_attendance = self.evaluation_criteria.get('min_attendance', 80)
        
        if hasattr(enrollment, 'attendance_rate'):
            return enrollment.attendance_rate >= min_attendance
        
        return True  # Por defecto, aprobar
    
    def _generate_certificate(self, enrollment):
        """Generar certificado para una inscripción"""
        # Implementar generación de certificado
        # Por ahora, solo crear registro
        certificate_data = {
            'program_name': self.name,
            'participant_name': enrollment.entrepreneur.full_name,
            'completion_date': date.today().isoformat(),
            'certificate_id': f"{self.slug}-{enrollment.id}-{int(datetime.utcnow().timestamp())}"
        }
        
        enrollment.certificate_data = certificate_data
        enrollment.certificate_issued = True
    
    def _update_success_metrics(self):
        """Actualizar métricas de éxito"""
        total_participants = len(self.enrollments.filter(
            ProgramEnrollment.status.in_([
                EnrollmentStatus.COMPLETED,
                EnrollmentStatus.GRADUATED,
                EnrollmentStatus.DROPPED_OUT
            ])
        ).all())
        
        graduated = len(self.enrollments.filter(
            ProgramEnrollment.status == EnrollmentStatus.GRADUATED
        ).all())
        
        if total_participants > 0:
            self.graduation_rate = (graduated / total_participants) * 100
    
    def add_mentor(self, ally, role='mentor', specialization=None, hours_committed=0):
        """Agregar mentor al programa"""
        # Verificar que no esté ya asignado
        existing = program_mentors.query.filter_by(
            program_id=self.id,
            mentor_id=ally.id
        ).first()
        
        if existing:
            raise ValidationError("El mentor ya está asignado al programa")
        
        from .. import db
        
        mentor_data = {
            'program_id': self.id,
            'mentor_id': ally.id,
            'role': role,
            'specialization': specialization,
            'hours_committed': hours_committed,
            'start_date': date.today(),
            'status': 'active'
        }
        
        db.session.execute(program_mentors.insert().values(mentor_data))
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Generar datos para dashboard del programa"""
        active_enrollments = self.get_active_enrollments()
        pending_applications = self.get_pending_applications()
        
        return {
            'program_info': {
                'name': self.name,
                'type': self.program_type.value,
                'status': self.status.value,
                'format': self.program_format.value,
                'duration': self.duration_formatted,
                'cost': self.cost_formatted,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'days_until_start': self.days_until_start
            },
            'enrollment_metrics': {
                'current_participants': self.current_participants,
                'max_participants': self.max_participants,
                'occupancy_rate': self.occupancy_rate,
                'pending_applications': len(pending_applications),
                'accepts_applications': self.is_accepting_applications,
                'days_until_deadline': self.days_until_deadline
            },
            'performance_metrics': {
                'graduation_rate': self.graduation_rate,
                'job_creation_rate': self.job_creation_rate,
                'funding_success_rate': self.funding_success_rate,
                'average_funding_raised': self.average_funding_raised / 100 if self.average_funding_raised else 0
            },
            'recent_applications': [
                {
                    'id': app.id,
                    'entrepreneur': app.entrepreneur.full_name,
                    'status': app.status.value,
                    'applied_at': app.applied_at.isoformat() if app.applied_at else None
                }
                for app in pending_applications[:10]
            ]
        }
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def get_published_programs(cls):
        """Obtener programas publicados"""
        return cls.query.filter(
            cls.status.in_([ProgramStatus.PUBLISHED, ProgramStatus.ACTIVE]),
            cls.is_public == True,
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def search_programs(cls, query_text: str = None, filters: Dict[str, Any] = None):
        """Buscar programas"""
        search = cls.query.filter(cls.is_deleted == False)
        
        if query_text:
            search_term = f"%{query_text}%"
            search = search.filter(
                cls.name.ilike(search_term) |
                cls.description.ilike(search_term) |
                cls.short_description.ilike(search_term)
            )
        
        if filters:
            if filters.get('type'):
                search = search.filter(cls.program_type == filters['type'])
            
            if filters.get('status'):
                search = search.filter(cls.status == filters['status'])
            
            if filters.get('organization_id'):
                search = search.filter(cls.organization_id == filters['organization_id'])
            
            if filters.get('format'):
                search = search.filter(cls.program_format == filters['format'])
            
            if filters.get('sector'):
                search = search.filter(cls.target_sectors.contains([filters['sector']]))
            
            if filters.get('free_only'):
                search = search.filter(cls.cost.is_(None) | (cls.cost == 0))
            
            if filters.get('accepting_applications'):
                search = search.filter(
                    cls.status == ProgramStatus.PUBLISHED,
                    cls.accepts_applications == True,
                    cls.application_deadline >= date.today()
                )
            
            if filters.get('start_date_from'):
                search = search.filter(cls.start_date >= filters['start_date_from'])
            
            if filters.get('start_date_to'):
                search = search.filter(cls.start_date <= filters['start_date_to'])
        
        return search.order_by(cls.start_date.desc(), cls.name).all()
    
    @classmethod
    def get_featured_programs(cls, limit=10):
        """Obtener programas destacados"""
        return (cls.query
                .filter(
                    cls.status == ProgramStatus.PUBLISHED,
                    cls.is_public == True,
                    cls.accepts_applications == True,
                    cls.is_deleted == False
                )
                .order_by(cls.application_deadline.asc(), cls.start_date.asc())
                .limit(limit)
                .all())
    
    def to_dict(self, include_sensitive=False, include_relations=False) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'program_type': self.program_type.value,
            'status': self.status.value,
            'short_description': self.short_description,
            'description': self.description,
            'objectives': self.objectives,
            'methodology': self.methodology,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'application_deadline': self.application_deadline.isoformat() if self.application_deadline else None,
            'duration_weeks': self.duration_weeks,
            'duration_hours': self.duration_hours,
            'program_format': self.program_format.value,
            'location': self.location,
            'language': self.language,
            'max_participants': self.max_participants,
            'current_participants': self.current_participants,
            'target_audience': self.target_audience,
            'selection_process': self.selection_process.value,
            'target_sectors': self.target_sectors,
            'target_stages': self.target_stages,
            'cost': self.cost / 100 if self.cost else 0,
            'currency': self.currency,
            'cost_formatted': self.cost_formatted,
            'benefits': self.benefits,
            'resources_provided': self.resources_provided,
            'mentorship_hours': self.mentorship_hours,
            'office_space': self.office_space,
            'legal_support': self.legal_support,
            'is_public': self.is_public,
            'accepts_applications': self.accepts_applications,
            'is_accepting_applications': self.is_accepting_applications,
            'provides_certificate': self.provides_certificate,
            'graduation_rate': self.graduation_rate,
            'occupancy_rate': self.occupancy_rate,
            'days_until_start': self.days_until_start,
            'days_until_deadline': self.days_until_deadline,
            'promotional_image': self.promotional_image,
            'promotional_video': self.promotional_video,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'selection_criteria': self.selection_criteria,
                'requirements': self.requirements,
                'application_form': self.application_form,
                'documents_required': self.documents_required,
                'scholarships_available': self.scholarships_available,
                'funding_provided': self.funding_provided / 100 if self.funding_provided else None,
                'equity_percentage': self.equity_percentage,
                'evaluation_criteria': self.evaluation_criteria,
                'automation_settings': self.automation_settings,
                'notification_settings': self.notification_settings,
                'custom_fields': self.custom_fields,
                'job_creation_rate': self.job_creation_rate,
                'funding_success_rate': self.funding_success_rate,
                'average_funding_raised': self.average_funding_raised / 100 if self.average_funding_raised else 0
            })
        
        if include_relations:
            data.update({
                'organization': self.organization.to_dict() if self.organization else None,
                'coordinator': self.coordinator.to_dict() if self.coordinator else None,
                'mentors_count': len(self.mentors) if self.mentors else 0,
                'sessions_count': len(self.sessions) if self.sessions else 0,
                'total_applications': len(self.enrollments) if self.enrollments else 0,
                'pending_applications': len(self.get_pending_applications())
            })
        
        return data


class ProgramEnrollment(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Inscripción a Programa
    
    Representa la inscripción de un emprendedor a un programa específico,
    incluyendo todo el proceso desde aplicación hasta graduación.
    """
    
    __tablename__ = 'program_enrollments'
    
    # Relaciones principales
    program_id = Column(Integer, ForeignKey('programs.id'), nullable=False, index=True)
    program = relationship("Program", back_populates="enrollments")
    
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=False, index=True)
    entrepreneur = relationship("Entrepreneur", back_populates="program_enrollments")
    
    # Estado de la inscripción
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.APPLIED, index=True)
    
    # Fechas del proceso
    applied_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    enrolled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    graduated_at = Column(DateTime)
    dropped_out_at = Column(DateTime)
    
    # Datos de aplicación
    application_data = Column(JSON)  # Respuestas del formulario
    motivation_letter = Column(Text)
    documents_submitted = Column(JSON)  # URLs de documentos
    
    # Proceso de revisión
    reviewer_id = Column(Integer, ForeignKey('users.id'))
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewer_notes = Column(Text)
    review_score = Column(Integer)  # Puntuación de 1-100
    rejection_reason = Column(Text)
    
    # Seguimiento durante el programa
    attendance_rate = Column(Float, default=0.0)  # Porcentaje de asistencia
    participation_score = Column(Float, default=0.0)  # Puntuación participación
    assignments_completed = Column(Integer, default=0)
    assignments_total = Column(Integer, default=0)
    
    # Evaluaciones y calificaciones
    midterm_score = Column(Float)
    final_score = Column(Float)
    overall_grade = Column(String(5))  # A, B, C, D, F
    
    # Certificación
    certificate_issued = Column(Boolean, default=False)
    certificate_data = Column(JSON)  # Datos del certificado
    certificate_url = Column(String(500))  # URL del certificado
    
    # Feedback y evaluación
    program_feedback = Column(JSON)  # Evaluación del programa
    mentor_feedback = Column(JSON)  # Feedback de mentores
    peer_feedback = Column(JSON)  # Feedback de pares
    
    # Seguimiento post-programa
    employment_status = Column(String(50))  # Estado laboral post-programa
    funding_received = Column(Integer)  # Financiamiento obtenido
    business_created = Column(Boolean, default=False)
    jobs_created = Column(Integer, default=0)
    
    # Configuración personalizada
    custom_fields = Column(JSON)
    notes = Column(Text)  # Notas adicionales
    
    def __repr__(self):
        return f'<ProgramEnrollment {self.entrepreneur.full_name if self.entrepreneur else "N/A"} -> {self.program.name if self.program else "N/A"}>'
    
    def __str__(self):
        return f'{self.entrepreneur.full_name if self.entrepreneur else "N/A"} en {self.program.name if self.program else "N/A"} ({self.status.value})'
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si la inscripción está activa"""
        return self.status in [
            EnrollmentStatus.ENROLLED,
            EnrollmentStatus.ACTIVE
        ]
    
    @hybrid_property
    def is_completed(self):
        """Verificar si completó el programa"""
        return self.status in [
            EnrollmentStatus.COMPLETED,
            EnrollmentStatus.GRADUATED
        ]
    
    @hybrid_property
    def completion_rate(self):
        """Tasa de finalización de asignaciones"""
        if self.assignments_total > 0:
            return (self.assignments_completed / self.assignments_total) * 100
        return 0
    
    @hybrid_property
    def days_in_program(self):
        """Días en el programa"""
        if self.started_at:
            end_date = self.completed_at or datetime.utcnow()
            return (end_date - self.started_at).days
        return 0
    
    # Métodos de negocio
    def approve(self, reviewer, notes=None, score=None):
        """Aprobar la aplicación"""
        if self.status not in [EnrollmentStatus.APPLIED, EnrollmentStatus.UNDER_REVIEW]:
            raise ValidationError("Solo se pueden aprobar aplicaciones pendientes")
        
        self.status = EnrollmentStatus.ACCEPTED
        self.approved_at = datetime.utcnow()
        self.reviewed_at = datetime.utcnow()
        self.reviewer_id = reviewer.id
        self.reviewer_notes = notes
        self.review_score = score
    
    def reject(self, reviewer, reason, notes=None):
        """Rechazar la aplicación"""
        if self.status not in [EnrollmentStatus.APPLIED, EnrollmentStatus.UNDER_REVIEW]:
            raise ValidationError("Solo se pueden rechazar aplicaciones pendientes")
        
        self.status = EnrollmentStatus.REJECTED
        self.rejected_at = datetime.utcnow()
        self.reviewed_at = datetime.utcnow()
        self.reviewer_id = reviewer.id
        self.rejection_reason = reason
        self.reviewer_notes = notes
    
    def enroll(self):
        """Inscribir oficialmente al programa"""
        if self.status != EnrollmentStatus.ACCEPTED:
            raise ValidationError("Solo se pueden inscribir aplicaciones aceptadas")
        
        self.status = EnrollmentStatus.ENROLLED
        self.enrolled_at = datetime.utcnow()
    
    def start_program(self):
        """Iniciar participación en el programa"""
        if self.status != EnrollmentStatus.ENROLLED:
            raise ValidationError("Debe estar inscrito para iniciar")
        
        self.status = EnrollmentStatus.ACTIVE
        self.started_at = datetime.utcnow()
    
    def complete_program(self, final_score=None, grade=None):
        """Completar el programa"""
        if self.status != EnrollmentStatus.ACTIVE:
            raise ValidationError("Debe estar activo para completar")
        
        self.status = EnrollmentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        
        if final_score:
            self.final_score = final_score
        if grade:
            self.overall_grade = grade
    
    def graduate(self, certificate_data=None):
        """Graduar del programa"""
        if self.status != EnrollmentStatus.COMPLETED:
            raise ValidationError("Debe completar el programa para graduarse")
        
        self.status = EnrollmentStatus.GRADUATED
        self.graduated_at = datetime.utcnow()
        
        # Generar certificado
        if self.program.provides_certificate:
            self._generate_certificate(certificate_data)
    
    def drop_out(self, reason=None):
        """Abandonar el programa"""
        if self.status not in [EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE]:
            raise ValidationError("Solo participantes activos pueden abandonar")
        
        self.status = EnrollmentStatus.DROPPED_OUT
        self.dropped_out_at = datetime.utcnow()
        if reason:
            self.notes = f"Razón de abandono: {reason}"
    
    def update_attendance(self, attended_sessions, total_sessions):
        """Actualizar tasa de asistencia"""
        if total_sessions > 0:
            self.attendance_rate = (attended_sessions / total_sessions) * 100
    
    def update_assignments(self, completed, total):
        """Actualizar progreso de asignaciones"""
        self.assignments_completed = completed
        self.assignments_total = total
    
    def submit_feedback(self, feedback_data):
        """Enviar feedback del programa"""
        self.program_feedback = feedback_data
    
    def _generate_certificate(self, certificate_data=None):
        """Generar certificado"""
        cert_data = {
            'program_name': self.program.name,
            'participant_name': self.entrepreneur.full_name,
            'completion_date': self.graduated_at.date().isoformat(),
            'certificate_id': f"{self.program.slug}-{self.id}-{int(self.graduated_at.timestamp())}",
            'grade': self.overall_grade,
            'organization': self.program.organization.name
        }
        
        if certificate_data:
            cert_data.update(certificate_data)
        
        self.certificate_data = cert_data
        self.certificate_issued = True
    
    def to_dict(self, include_sensitive=False) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'program_id': self.program_id,
            'entrepreneur_id': self.entrepreneur_id,
            'status': self.status.value,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'graduated_at': self.graduated_at.isoformat() if self.graduated_at else None,
            'attendance_rate': self.attendance_rate,
            'completion_rate': self.completion_rate,
            'days_in_program': self.days_in_program,
            'certificate_issued': self.certificate_issued,
            'is_active': self.is_active,
            'is_completed': self.is_completed
        }
        
        if include_sensitive:
            data.update({
                'application_data': self.application_data,
                'motivation_letter': self.motivation_letter,
                'reviewer_notes': self.reviewer_notes,
                'review_score': self.review_score,
                'rejection_reason': self.rejection_reason,
                'participation_score': self.participation_score,
                'midterm_score': self.midterm_score,
                'final_score': self.final_score,
                'overall_grade': self.overall_grade,
                'program_feedback': self.program_feedback,
                'mentor_feedback': self.mentor_feedback,
                'employment_status': self.employment_status,
                'funding_received': self.funding_received / 100 if self.funding_received else None,
                'business_created': self.business_created,
                'jobs_created': self.jobs_created,
                'certificate_data': self.certificate_data,
                'notes': self.notes
            })
        
        return data


class ProgramSession(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Sesión de Programa
    
    Representa sesiones individuales dentro de un programa,
    como clases, talleres, mentoría, etc.
    """
    
    __tablename__ = 'program_sessions'
    
    # Relación con programa
    program_id = Column(Integer, ForeignKey('programs.id'), nullable=False, index=True)
    program = relationship("Program", back_populates="sessions")
    
    # Información básica
    title = Column(String(200), nullable=False)
    description = Column(Text)
    session_type = Column(String(50), default='class')  # class, workshop, mentoring, assessment
    
    # Fechas y horarios
    scheduled_date = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    actual_start_time = Column(DateTime)
    actual_end_time = Column(DateTime)
    
    # Ubicación y formato
    location = Column(String(200))
    meeting_url = Column(String(500))  # URL para sesiones virtuales
    meeting_password = Column(String(50))
    is_virtual = Column(Boolean, default=False)
    
    # Facilitador/Instructor
    facilitator_id = Column(Integer, ForeignKey('users.id'))
    facilitator = relationship("User", foreign_keys=[facilitator_id])
    
    # Contenido y materiales
    agenda = Column(JSON)  # Agenda de la sesión
    materials = Column(JSON)  # Materiales y recursos
    recording_url = Column(String(500))  # URL de grabación
    presentation_url = Column(String(500))  # URL de presentación
    
    # Estado y configuración
    status = Column(String(20), default='scheduled')  # scheduled, in_progress, completed, cancelled
    is_mandatory = Column(Boolean, default=True)
    max_participants = Column(Integer)
    
    # Asistencia y participación
    attendees = relationship("SessionAttendance", back_populates="session")
    
    def __repr__(self):
        return f'<ProgramSession {self.title} - {self.scheduled_date}>'
    
    @hybrid_property
    def attendance_rate(self):
        """Tasa de asistencia"""
        if not self.attendees:
            return 0
        
        attended = len([a for a in self.attendees if a.attended])
        return (attended / len(self.attendees)) * 100 if self.attendees else 0
    
    def mark_attendance(self, enrollment_id, attended=True, notes=None):
        """Marcar asistencia"""
        attendance = SessionAttendance.query.filter_by(
            session_id=self.id,
            enrollment_id=enrollment_id
        ).first()
        
        if not attendance:
            attendance = SessionAttendance(
                session_id=self.id,
                enrollment_id=enrollment_id
            )
            from .. import db
            db.session.add(attendance)
        
        attendance.attended = attended
        attendance.notes = notes
        attendance.marked_at = datetime.utcnow()
        
        return attendance


class SessionAttendance(BaseModel, TimestampMixin):
    """Modelo de Asistencia a Sesión"""
    
    __tablename__ = 'session_attendance'
    
    session_id = Column(Integer, ForeignKey('program_sessions.id'), nullable=False)
    session = relationship("ProgramSession", back_populates="attendees")
    
    enrollment_id = Column(Integer, ForeignKey('program_enrollments.id'), nullable=False)
    enrollment = relationship("ProgramEnrollment")
    
    attended = Column(Boolean, default=False)
    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)
    marked_at = Column(DateTime)
    notes = Column(Text)
    
    __table_args__ = (
        {'extend_existing': True}
    )