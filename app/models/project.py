"""
Modelo Proyecto del Ecosistema de Emprendimiento

Este módulo define el modelo para proyectos/emprendimientos desarrollados por entrepreneurs,
incluyendo seguimiento completo desde la idea hasta la implementación y escalamiento.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from app.extensions import db
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
from decimal import Decimal

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    PROJECT_STATUSES,
    PROJECT_TYPES,
    BUSINESS_MODELS,
    INDUSTRY_SECTORS,
    TARGET_MARKETS,
    FUNDING_STAGES,
    CURRENCIES,
    PRIORITY_LEVELS,
    RISK_LEVELS
)
from ..core.exceptions import ValidationError


class ProjectStatus(Enum):
    """Estados del proyecto"""
    IDEA = "idea"
    CONCEPT = "concept"
    PROTOTYPE = "prototype"
    VALIDATION = "validation"
    DEVELOPMENT = "development"
    PILOT = "pilot"
    TESTING = "testing"
    LAUNCH = "launch"
    ACTIVE = "active"
    SCALING = "scaling"
    MATURE = "mature"
    PIVOTING = "pivoting"
    PAUSED = "paused"
    COMPLETED = "completed"


class ProjectPriority(Enum):
    """Prioridades del proyecto"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProjectCategory(Enum):
    """Categorías del proyecto"""
    TECHNOLOGY = "technology"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    AGTECH = "agtech"
    CLEANTECH = "cleantech"
    ECOMMERCE = "ecommerce"
    MARKETPLACE = "marketplace"
    SAAS = "saas"
    MOBILE_APP = "mobile_app"
    IOT = "iot"
    AI_ML = "ai_ml"
    BLOCKCHAIN = "blockchain"
    SOCIAL_IMPACT = "social_impact"
    OTHER = "other"


# Alias for compatibility
PriorityLevel = ProjectPriority


class ProjectType(Enum):
    """Tipos de proyecto"""
    STARTUP = "startup"
    SOCIAL_VENTURE = "social_venture"
    TECH_STARTUP = "tech_startup"
    SERVICE_BUSINESS = "service_business"
    PRODUCT_BUSINESS = "product_business"
    MARKETPLACE = "marketplace"
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    AGTECH = "agtech"
    GREENTECH = "greentech"
    NONPROFIT = "nonprofit"
    FRANCHISE = "franchise"


class BusinessModel(Enum):
    """Modelos de negocio"""
    B2B = "b2b"
    B2C = "b2c"
    B2B2C = "b2b2c"
    C2C = "c2c"
    MARKETPLACE = "marketplace"
    SUBSCRIPTION = "subscription"
    FREEMIUM = "freemium"
    ADVERTISING = "advertising"
    COMMISSION = "commission"
    LICENSING = "licensing"
    FRANCHISE = "franchise"
    DONATION = "donation"
    HYBRID = "hybrid"


class FundingStage(Enum):
    """Etapas de financiamiento"""
    BOOTSTRAPPED = "bootstrapped"
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"
    IPO_READY = "ipo_ready"
    ACQUIRED = "acquired"


class PriorityLevel(Enum):
    """Niveles de prioridad"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(Enum):
    """Niveles de riesgo"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# Tabla de asociación para co-fundadores
project_cofounders = Table(
    'project_cofounders',
    db.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('entrepreneur_id', Integer, ForeignKey('entrepreneurs.id'), primary_key=True),
    Column('role', String(100)),
    Column('equity_percentage', Float),
    Column('is_active', Boolean, default=True),
    Column('joined_at', Date, default=date.today),
    Column('left_at', Date),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para inversores interesados
project_interests = Table(
    'project_interests',
    db.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), primary_key=True),
    Column('interest_level', String(20), default='medium'),  # low, medium, high
    Column('investment_amount', Integer),  # En centavos
    Column('notes', Text),
    Column('status', String(20), default='interested'),  # interested, negotiating, invested, declined
    Column('contacted_at', DateTime, default=datetime.utcnow),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para mentores asignados
project_mentors = Table(
    'project_mentors',
    db.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('ally_id', Integer, ForeignKey('allies.id'), primary_key=True),
    Column('specialization', String(100)),
    Column('hours_committed', Integer, default=0),
    Column('start_date', Date, default=date.today),
    Column('end_date', Date),
    Column('status', String(20), default='active'),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Project(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Proyecto
    
    Representa proyectos/emprendimientos desarrollados por entrepreneurs,
    con seguimiento completo del progreso, métricas, financiamiento y más.
    """
    
    __tablename__ = 'projects'
    
    # Información básica
    name = Column(String(200), nullable=False, index=True)
    slug = Column(String(150), unique=True, nullable=False, index=True)
    tagline = Column(String(300))  # Frase descriptiva corta
    description = Column(Text)
    
    # Clasificación
    project_type = Column(SQLEnum(ProjectType), nullable=False, index=True)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.IDEA, index=True)
    business_model = Column(SQLEnum(BusinessModel))
    industry_sector = Column(String(100), index=True)
    
    # Propietario principal
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=False, index=True)
    entrepreneur = relationship("Entrepreneur", back_populates="projects")
    
    # Co-fundadores
    cofounders = relationship("Entrepreneur",
                            secondary=project_cofounders,
                            back_populates="cofounder_projects")
    
    # Fechas importantes
    conception_date = Column(Date)  # Fecha de concepción de la idea
    launch_date = Column(Date)  # Fecha de lanzamiento
    target_launch_date = Column(Date)  # Fecha objetivo de lanzamiento
    last_milestone_date = Column(Date)  # Última fecha de hito
    
    # Información del mercado
    target_market = Column(JSON)  # Mercados objetivo
    target_audience = Column(Text)  # Audiencia objetivo
    problem_statement = Column(Text)  # Problema que resuelve
    solution_description = Column(Text)  # Descripción de la solución
    value_proposition = Column(Text)  # Propuesta de valor
    competitive_advantage = Column(Text)  # Ventaja competitiva
    
    # Análisis de competencia
    competitors = Column(JSON)  # Lista de competidores
    market_size = Column(String(200))  # Tamaño del mercado
    market_analysis = Column(Text)  # Análisis de mercado
    
    # Modelo de negocio y financiero
    revenue_streams = Column(JSON)  # Fuentes de ingresos
    cost_structure = Column(JSON)  # Estructura de costos
    pricing_model = Column(Text)  # Modelo de precios
    unit_economics = Column(JSON)  # Economía unitaria
    
    # Métricas de negocio
    current_revenue = Column(Integer, default=0)  # Ingresos actuales en centavos
    monthly_revenue = Column(Integer, default=0)  # Ingresos mensuales
    annual_revenue = Column(Integer, default=0)  # Ingresos anuales
    gross_margin = Column(Float, default=0.0)  # Margen bruto %
    burn_rate = Column(Integer, default=0)  # Tasa de quema mensual
    runway_months = Column(Integer, default=0)  # Pista de aterrizaje en meses
    
    # Métricas de tracción
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    customer_acquisition_cost = Column(Integer, default=0)  # CAC en centavos
    lifetime_value = Column(Integer, default=0)  # LTV en centavos
    churn_rate = Column(Float, default=0.0)  # Tasa de abandono %
    
    # Financiamiento
    funding_stage = Column(SQLEnum(FundingStage), default=FundingStage.BOOTSTRAPPED)
    total_funding_raised = Column(Integer, default=0)  # Total recaudado en centavos
    funding_target = Column(Integer, default=0)  # Objetivo de financiamiento
    valuation = Column(Integer, default=0)  # Valuación en centavos
    currency = Column(String(3), default='USD')
    
    # Equipo y recursos
    team_size = Column(Integer, default=1)
    full_time_employees = Column(Integer, default=0)
    part_time_employees = Column(Integer, default=0)
    contractors = Column(Integer, default=0)
    advisors_count = Column(Integer, default=0)
    
    # Tecnología y desarrollo
    tech_stack = Column(JSON)  # Stack tecnológico
    development_stage = Column(String(50))  # Etapa de desarrollo
    intellectual_property = Column(JSON)  # Propiedad intelectual
    patents = Column(JSON)  # Patentes
    
    # Operaciones
    location = Column(String(200))  # Ubicación principal
    legal_structure = Column(String(100))  # Estructura legal
    incorporation_date = Column(Date)  # Fecha de constitución
    regulatory_requirements = Column(JSON)  # Requisitos regulatorios
    
    # Gestión de riesgos
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)
    risk_factors = Column(JSON)  # Factores de riesgo
    mitigation_strategies = Column(JSON)  # Estrategias de mitigación
    
    # Sostenibilidad y impacto
    sustainability_goals = Column(JSON)  # Objetivos de sostenibilidad
    social_impact = Column(Text)  # Impacto social
    environmental_impact = Column(Text)  # Impacto ambiental
    sdg_alignment = Column(JSON)  # Alineación con ODS
    
    # Progreso y seguimiento
    progress_percentage = Column(Float, default=0.0)  # Progreso general %
    milestones_completed = Column(Integer, default=0)
    milestones_total = Column(Integer, default=0)
    priority_level = Column(SQLEnum(PriorityLevel), default=PriorityLevel.MEDIUM)
    
    # Organización de apoyo
    supporting_organization_id = Column(Integer, ForeignKey('organizations.id'))
    supporting_organization = relationship("Organization", back_populates="supported_projects")
    
    # Programa asociado
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    # Configuración
    is_public = Column(Boolean, default=False)  # Visible públicamente
    seeking_funding = Column(Boolean, default=False)  # Buscando financiamiento
    seeking_mentorship = Column(Boolean, default=True)  # Buscando mentoría
    seeking_partners = Column(Boolean, default=False)  # Buscando socios
    
    # SEO y marketing
    website_url = Column(String(500))
    demo_url = Column(String(500))
    video_pitch_url = Column(String(500))
    presentation_url = Column(String(500))
    logo_url = Column(String(500))
    screenshots = Column(JSON)  # URLs de screenshots
    social_media = Column(JSON)  # Enlaces a redes sociales
    
    # Configuración personalizada
    custom_fields = Column(JSON)
    tags = Column(JSON)  # Tags/etiquetas
    notes = Column(Text)  # Notas internas
    
    # Relaciones
    
    # Mentores asignados
    mentors = relationship("Ally",
                          secondary=project_mentors,
                          back_populates="mentored_projects")
    
    # Clientes/inversores interesados
    interested_clients = relationship("Client",
                                    secondary=project_interests,
                                    back_populates="interested_projects")
    
    # Hitos del proyecto
    milestones = relationship("ProjectMilestone", back_populates="project")
    
    # Tareas del proyecto
    tasks = relationship("Task", back_populates="project")
    
    # Reuniones relacionadas
    meetings = relationship("Meeting", back_populates="project")
    
    # Documentos del proyecto
    documents = relationship("Document", back_populates="project")
    
    # Evaluaciones
    evaluations = relationship("ProjectEvaluation", back_populates="project")
    
    # Actualizaciones/posts
    updates = relationship("ProjectUpdate", back_populates="project")
    
    # Actividades del proyecto
    activities = relationship("ActivityLog", back_populates="project")
    
    # Analytics del proyecto
    analytics = relationship("ProjectAnalytics", back_populates="project")
    
    def __init__(self, **kwargs):
        """Inicialización del proyecto"""
        super().__init__(**kwargs)
        
        # Generar slug si no se proporciona
        if not self.slug and self.name:
            self.slug = self._generate_slug(self.name)
        
        # Configurar fecha de concepción por defecto
        if not self.conception_date:
            self.conception_date = date.today()
    
    def __repr__(self):
        return f'<Project {self.name} ({self.status.value})>'
    
    def __str__(self):
        return f'{self.name} - {self.entrepreneur.full_name if self.entrepreneur else "Sin propietario"}'
    
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
        
        while Project.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
    
    # Validaciones
    @validates('name')
    def validate_name(self, key, name):
        """Validar nombre del proyecto"""
        if not name or len(name.strip()) < 2:
            raise ValidationError("El nombre debe tener al menos 2 caracteres")
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
    
    @validates('website_url', 'demo_url', 'video_pitch_url')
    def validate_urls(self, key, url):
        """Validar URLs"""
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(url):
                raise ValidationError(f"URL inválida para {key}")
        
        return url
    
    @validates('conception_date', 'launch_date', 'target_launch_date')
    def validate_dates(self, key, date_value):
        """Validar fechas del proyecto"""
        if date_value:
            if key == 'launch_date' and self.conception_date:
                if date_value < self.conception_date:
                    raise ValidationError("La fecha de lanzamiento no puede ser anterior a la concepción")
            
            if key == 'target_launch_date' and self.conception_date:
                if date_value < self.conception_date:
                    raise ValidationError("La fecha objetivo no puede ser anterior a la concepción")
        
        return date_value
    
    @validates('progress_percentage')
    def validate_progress(self, key, progress):
        """Validar porcentaje de progreso"""
        if progress is not None:
            if progress < 0 or progress > 100:
                raise ValidationError("El progreso debe estar entre 0 y 100")
        return progress
    
    @validates('gross_margin', 'churn_rate')
    def validate_percentages(self, key, value):
        """Validar porcentajes"""
        if value is not None:
            if value < 0 or value > 100:
                raise ValidationError(f"{key} debe estar entre 0 y 100")
        return value
    
    @validates('team_size', 'total_users', 'active_users')
    def validate_positive_integers(self, key, value):
        """Validar enteros positivos"""
        if value is not None and value < 0:
            raise ValidationError(f"{key} no puede ser negativo")
        return value
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si el proyecto está activo"""
        return (self.status in [
            ProjectStatus.DEVELOPMENT,
            ProjectStatus.PILOT,
            ProjectStatus.TESTING,
            ProjectStatus.LAUNCH,
            ProjectStatus.ACTIVE,
            ProjectStatus.SCALING
        ] and not self.is_deleted)
    
    @hybrid_property
    def is_seeking_investment(self):
        """Verificar si busca inversión"""
        return self.seeking_funding and self.is_active
    
    @hybrid_property
    def days_since_conception(self):
        """Días desde la concepción"""
        if self.conception_date:
            return (date.today() - self.conception_date).days
        return 0
    
    @hybrid_property
    def days_to_launch(self):
        """Días hasta el lanzamiento objetivo"""
        if self.target_launch_date:
            return (self.target_launch_date - date.today()).days
        return None
    
    @hybrid_property
    def revenue_formatted(self):
        """Ingresos formateados"""
        if self.current_revenue:
            return f"{self.currency} {self.current_revenue / 100:,.2f}"
        return f"{self.currency} 0.00"
    
    @hybrid_property
    def funding_formatted(self):
        """Financiamiento formateado"""
        if self.total_funding_raised:
            return f"{self.currency} {self.total_funding_raised / 100:,.2f}"
        return f"{self.currency} 0.00"
    
    @hybrid_property
    def valuation_formatted(self):
        """Valuación formateada"""
        if self.valuation:
            return f"{self.currency} {self.valuation / 100:,.2f}"
        return None
    
    @hybrid_property
    def burn_rate_formatted(self):
        """Tasa de quema formateada"""
        if self.burn_rate:
            return f"{self.currency} {self.burn_rate / 100:,.2f}/mes"
        return None
    
    @hybrid_property
    def milestone_completion_rate(self):
        """Tasa de finalización de hitos"""
        if self.milestones_total > 0:
            return (self.milestones_completed / self.milestones_total) * 100
        return 0
    
    @hybrid_property
    def ltv_cac_ratio(self):
        """Ratio LTV/CAC"""
        if self.customer_acquisition_cost > 0 and self.lifetime_value > 0:
            return self.lifetime_value / self.customer_acquisition_cost
        return 0
    
    @hybrid_property
    def user_engagement_rate(self):
        """Tasa de engagement de usuarios"""
        if self.total_users > 0:
            return (self.active_users / self.total_users) * 100
        return 0
    
    # Métodos de negocio
    def advance_status(self, new_status: ProjectStatus, notes: str = None):
        """Avanzar el estado del proyecto"""
        valid_transitions = self._get_valid_status_transitions()
        
        if new_status not in valid_transitions.get(self.status, []):
            raise ValidationError(f"Transición inválida de {self.status.value} a {new_status.value}")
        
        old_status = self.status
        self.status = new_status
        
        # Registrar cambio de estado
        self._log_status_change(old_status, new_status, notes)
        
        # Actualizar fechas importantes
        if new_status == ProjectStatus.LAUNCH:
            self.launch_date = date.today()
        
        # Actualizar progreso basado en estado
        self._update_progress_by_status()
    
    def _get_valid_status_transitions(self) -> Dict[ProjectStatus, List[ProjectStatus]]:
        """Obtener transiciones de estado válidas"""
        return {
            ProjectStatus.IDEA: [ProjectStatus.CONCEPT, ProjectStatus.CANCELLED],
            ProjectStatus.CONCEPT: [ProjectStatus.PROTOTYPE, ProjectStatus.VALIDATION, ProjectStatus.CANCELLED],
            ProjectStatus.PROTOTYPE: [ProjectStatus.VALIDATION, ProjectStatus.DEVELOPMENT, ProjectStatus.PIVOTING],
            ProjectStatus.VALIDATION: [ProjectStatus.DEVELOPMENT, ProjectStatus.PILOT, ProjectStatus.PIVOTING],
            ProjectStatus.DEVELOPMENT: [ProjectStatus.PILOT, ProjectStatus.TESTING, ProjectStatus.PAUSED],
            ProjectStatus.PILOT: [ProjectStatus.TESTING, ProjectStatus.LAUNCH, ProjectStatus.PIVOTING],
            ProjectStatus.TESTING: [ProjectStatus.LAUNCH, ProjectStatus.DEVELOPMENT, ProjectStatus.PAUSED],
            ProjectStatus.LAUNCH: [ProjectStatus.ACTIVE, ProjectStatus.FAILED, ProjectStatus.PAUSED],
            ProjectStatus.ACTIVE: [ProjectStatus.SCALING, ProjectStatus.MATURE, ProjectStatus.PIVOTING],
            ProjectStatus.SCALING: [ProjectStatus.MATURE, ProjectStatus.ACTIVE],
            ProjectStatus.MATURE: [ProjectStatus.COMPLETED],
            ProjectStatus.PIVOTING: [ProjectStatus.CONCEPT, ProjectStatus.DEVELOPMENT, ProjectStatus.CANCELLED],
            ProjectStatus.PAUSED: [ProjectStatus.DEVELOPMENT, ProjectStatus.TESTING, ProjectStatus.CANCELLED],
        }
    
    def _update_progress_by_status(self):
        """Actualizar progreso basado en el estado"""
        status_progress = {
            ProjectStatus.IDEA: 5,
            ProjectStatus.CONCEPT: 15,
            ProjectStatus.PROTOTYPE: 25,
            ProjectStatus.VALIDATION: 35,
            ProjectStatus.DEVELOPMENT: 50,
            ProjectStatus.PILOT: 65,
            ProjectStatus.TESTING: 75,
            ProjectStatus.LAUNCH: 85,
            ProjectStatus.ACTIVE: 90,
            ProjectStatus.SCALING: 95,
            ProjectStatus.MATURE: 100,
            ProjectStatus.COMPLETED: 100
        }
        
        base_progress = status_progress.get(self.status, self.progress_percentage)
        milestone_bonus = (self.milestone_completion_rate / 100) * 10  # Hasta 10% adicional
        
        self.progress_percentage = min(100, base_progress + milestone_bonus)
    
    def _log_status_change(self, old_status: ProjectStatus, new_status: ProjectStatus, notes: str = None):
        """Registrar cambio de estado en el log de actividades"""
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type='status_change',
            description=f"Estado cambiado de {old_status.value} a {new_status.value}",
            metadata={
                'old_status': old_status.value,
                'new_status': new_status.value,
                'notes': notes
            },
            project_id=self.id,
            user_id=self.entrepreneur.user_id if self.entrepreneur else None
        )
        
        db.session.add(activity)
    
    def add_cofounder(self, entrepreneur, role: str, equity_percentage: float = None):
        """Agregar co-fundador"""
        # Verificar que no esté ya como co-fundador
        existing = project_cofounders.query.filter_by(
            project_id=self.id,
            entrepreneur_id=entrepreneur.id
        ).first()
        
        if existing:
            raise ValidationError("Ya es co-fundador de este proyecto")
        
        if equity_percentage and (equity_percentage < 0 or equity_percentage > 100):
            raise ValidationError("El porcentaje de equity debe estar entre 0 y 100")
        
        from .. import db
        
        cofounder_data = {
            'project_id': self.id,
            'entrepreneur_id': entrepreneur.id,
            'role': role,
            'equity_percentage': equity_percentage,
            'is_active': True,
            'joined_at': date.today()
        }
        
        db.session.execute(project_cofounders.insert().values(cofounder_data))
    
    def add_mentor(self, ally, specialization: str = None, hours_committed: int = 0):
        """Agregar mentor al proyecto"""
        # Verificar que no esté ya asignado
        existing = project_mentors.query.filter_by(
            project_id=self.id,
            ally_id=ally.id
        ).first()
        
        if existing:
            raise ValidationError("El mentor ya está asignado a este proyecto")
        
        from .. import db
        
        mentor_data = {
            'project_id': self.id,
            'ally_id': ally.id,
            'specialization': specialization,
            'hours_committed': hours_committed,
            'start_date': date.today(),
            'status': 'active'
        }
        
        db.session.execute(project_mentors.insert().values(mentor_data))
    
    def add_interest(self, client, interest_level: str = 'medium', 
                    investment_amount: int = None, notes: str = None):
        """Agregar interés de un cliente/inversor"""
        # Verificar que no exista ya el interés
        existing = project_interests.query.filter_by(
            project_id=self.id,
            client_id=client.id
        ).first()
        
        if existing:
            # Actualizar interés existente
            existing.interest_level = interest_level
            existing.investment_amount = investment_amount
            existing.notes = notes
            existing.contacted_at = datetime.utcnow()
            return existing
        
        from .. import db
        
        interest_data = {
            'project_id': self.id,
            'client_id': client.id,
            'interest_level': interest_level,
            'investment_amount': investment_amount,
            'notes': notes,
            'status': 'interested'
        }
        
        db.session.execute(project_interests.insert().values(interest_data))
    
    def create_milestone(self, title: str, description: str = None, 
                        target_date: date = None, priority: str = 'medium'):
        """Crear un hito del proyecto"""
        from .milestone import ProjectMilestone
        from .. import db
        
        milestone = ProjectMilestone(
            project_id=self.id,
            title=title,
            description=description,
            target_date=target_date,
            priority=priority,
            status='pending'
        )
        
        db.session.add(milestone)
        self.milestones_total += 1
        
        return milestone
    
    def complete_milestone(self, milestone_id: int, notes: str = None):
        """Completar un hito"""
        from .milestone import ProjectMilestone
        
        milestone = ProjectMilestone.query.get(milestone_id)
        if not milestone or milestone.project_id != self.id:
            raise ValidationError("Hito no encontrado")
        
        milestone.complete(notes)
        self.milestones_completed += 1
        self.last_milestone_date = date.today()
        
        # Recalcular progreso
        self._update_progress_by_status()
    
    def update_metrics(self, metrics: Dict[str, Any]):
        """Actualizar métricas del proyecto"""
        allowed_metrics = [
            'current_revenue', 'monthly_revenue', 'annual_revenue',
            'total_users', 'active_users', 'gross_margin', 'churn_rate',
            'customer_acquisition_cost', 'lifetime_value', 'burn_rate',
            'runway_months', 'team_size', 'full_time_employees',
            'part_time_employees', 'contractors'
        ]
        
        for key, value in metrics.items():
            if key in allowed_metrics and hasattr(self, key):
                # Convertir valores monetarios a centavos si es necesario
                if key in ['current_revenue', 'monthly_revenue', 'annual_revenue', 
                          'customer_acquisition_cost', 'lifetime_value', 'burn_rate']:
                    if isinstance(value, (int, float)) and value >= 1:
                        # Si el valor es mayor a 1, asumimos que está en unidades, no centavos
                        value = int(value * 100)
                
                setattr(self, key, value)
        
        # Actualizar runway si se actualizó burn_rate
        if 'burn_rate' in metrics and self.burn_rate > 0:
            self._calculate_runway()
    
    def _calculate_runway(self):
        """Calcular runway en meses"""
        if self.burn_rate > 0 and self.total_funding_raised > 0:
            # Calcular fondos disponibles (asumiendo que algo se ha gastado)
            available_funds = self.total_funding_raised - (self.burn_rate * 6)  # Ejemplo
            if available_funds > 0:
                self.runway_months = int(available_funds / self.burn_rate)
            else:
                self.runway_months = 0
    
    def add_funding_round(self, amount: int, funding_type: str, 
                         investors: List[str] = None, notes: str = None):
        """Agregar ronda de financiamiento"""
        from .funding_round import FundingRound
        from .. import db
        
        funding_round = FundingRound(
            project_id=self.id,
            amount=amount,
            funding_type=funding_type,
            investors=investors or [],
            notes=notes,
            closed_at=datetime.utcnow()
        )
        
        db.session.add(funding_round)
        
        # Actualizar total de financiamiento
        self.total_funding_raised += amount
        
        # Actualizar etapa de financiamiento si corresponde
        self._update_funding_stage(amount)
        
        return funding_round
    
    def _update_funding_stage(self, amount: int):
        """Actualizar etapa de financiamiento basada en el monto"""
        total_raised = self.total_funding_raised / 100  # Convertir a unidades
        
        if total_raised >= 50000000:  # 50M+
            self.funding_stage = FundingStage.SERIES_C
        elif total_raised >= 15000000:  # 15M+
            self.funding_stage = FundingStage.SERIES_B
        elif total_raised >= 5000000:  # 5M+
            self.funding_stage = FundingStage.SERIES_A
        elif total_raised >= 500000:  # 500K+
            self.funding_stage = FundingStage.SEED
        elif total_raised >= 50000:  # 50K+
            self.funding_stage = FundingStage.PRE_SEED
    
    def create_update(self, title: str, content: str, is_public: bool = False,
                     metrics_update: Dict[str, Any] = None):
        """Crear actualización del proyecto"""
        from .project_update import ProjectUpdate
        from .. import db
        
        update = ProjectUpdate(
            project_id=self.id,
            title=title,
            content=content,
            is_public=is_public,
            metrics_snapshot=metrics_update or self._get_current_metrics(),
            author_id=self.entrepreneur.user_id if self.entrepreneur else None
        )
        
        db.session.add(update)
        return update
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Obtener snapshot de métricas actuales"""
        return {
            'revenue': self.current_revenue / 100 if self.current_revenue else 0,
            'users': self.total_users,
            'active_users': self.active_users,
            'team_size': self.team_size,
            'funding_raised': self.total_funding_raised / 100 if self.total_funding_raised else 0,
            'burn_rate': self.burn_rate / 100 if self.burn_rate else 0,
            'runway_months': self.runway_months,
            'progress': self.progress_percentage
        }
    
    def get_investment_summary(self) -> Dict[str, Any]:
        """Obtener resumen de inversión"""
        return {
            'seeking_funding': self.seeking_funding,
            'funding_stage': self.funding_stage.value,
            'funding_target': self.funding_target / 100 if self.funding_target else None,
            'total_raised': self.total_funding_raised / 100 if self.total_funding_raised else 0,
            'valuation': self.valuation / 100 if self.valuation else None,
            'burn_rate': self.burn_rate / 100 if self.burn_rate else 0,
            'runway_months': self.runway_months,
            'revenue': self.current_revenue / 100 if self.current_revenue else 0,
            'growth_metrics': {
                'users': self.total_users,
                'active_users': self.active_users,
                'engagement_rate': self.user_engagement_rate,
                'churn_rate': self.churn_rate
            },
            'unit_economics': {
                'ltv': self.lifetime_value / 100 if self.lifetime_value else 0,
                'cac': self.customer_acquisition_cost / 100 if self.customer_acquisition_cost else 0,
                'ltv_cac_ratio': self.ltv_cac_ratio,
                'gross_margin': self.gross_margin
            }
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Generar datos para dashboard del proyecto"""
        recent_milestones = (self.milestones
                           .order_by(ProjectMilestone.created_at.desc())
                           .limit(5)
                           .all())
        
        recent_activities = (self.activities
                           .order_by(ActivityLog.created_at.desc())
                           .limit(10)
                           .all())
        
        return {
            'project_info': {
                'name': self.name,
                'status': self.status.value,
                'type': self.project_type.value,
                'industry': self.industry_sector,
                'progress': self.progress_percentage,
                'days_since_conception': self.days_since_conception,
                'days_to_launch': self.days_to_launch,
                'is_public': self.is_public
            },
            'metrics': {
                'revenue': self.revenue_formatted,
                'users': self.total_users,
                'active_users': self.active_users,
                'engagement_rate': self.user_engagement_rate,
                'team_size': self.team_size,
                'funding_raised': self.funding_formatted,
                'burn_rate': self.burn_rate_formatted,
                'runway_months': self.runway_months
            },
            'progress': {
                'overall_progress': self.progress_percentage,
                'milestones_completed': self.milestones_completed,
                'milestones_total': self.milestones_total,
                'milestone_completion_rate': self.milestone_completion_rate,
                'last_milestone': self.last_milestone_date.isoformat() if self.last_milestone_date else None
            },
            'funding': {
                'stage': self.funding_stage.value,
                'seeking_funding': self.seeking_funding,
                'total_raised': self.total_funding_raised / 100 if self.total_funding_raised else 0,
                'target': self.funding_target / 100 if self.funding_target else None,
                'interested_investors': len(self.interested_clients)
            },
            'team': {
                'size': self.team_size,
                'cofounders': len(self.cofounders),
                'mentors': len(self.mentors),
                'full_time': self.full_time_employees,
                'part_time': self.part_time_employees
            },
            'recent_milestones': [
                {
                    'id': milestone.id,
                    'title': milestone.title,
                    'status': milestone.status,
                    'target_date': milestone.target_date.isoformat() if milestone.target_date else None,
                    'completed_at': milestone.completed_at.isoformat() if milestone.completed_at else None
                }
                for milestone in recent_milestones
            ],
            'recent_activities': [
                {
                    'id': activity.id,
                    'type': activity.activity_type,
                    'description': activity.description,
                    'created_at': activity.created_at.isoformat()
                }
                for activity in recent_activities
            ]
        }
    
    def get_public_profile(self) -> Dict[str, Any]:
        """Obtener perfil público del proyecto"""
        if not self.is_public:
            return None
        
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'tagline': self.tagline,
            'description': self.description,
            'type': self.project_type.value,
            'status': self.status.value,
            'industry_sector': self.industry_sector,
            'business_model': self.business_model.value if self.business_model else None,
            'target_market': self.target_market,
            'problem_statement': self.problem_statement,
            'solution_description': self.solution_description,
            'value_proposition': self.value_proposition,
            'website_url': self.website_url,
            'demo_url': self.demo_url,
            'video_pitch_url': self.video_pitch_url,
            'logo_url': self.logo_url,
            'screenshots': self.screenshots,
            'social_media': self.social_media,
            'team_size': self.team_size,
            'funding_stage': self.funding_stage.value,
            'seeking_funding': self.seeking_funding,
            'seeking_mentorship': self.seeking_mentorship,
            'seeking_partners': self.seeking_partners,
            'launch_date': self.launch_date.isoformat() if self.launch_date else None,
            'entrepreneur': {
                'name': self.entrepreneur.full_name,
                'title': self.entrepreneur.professional_title
            } if self.entrepreneur else None,
            'organization': {
                'name': self.supporting_organization.name,
                'type': self.supporting_organization.organization_type.value
            } if self.supporting_organization else None,
            'tags': self.tags,
            'social_impact': self.social_impact,
            'sdg_alignment': self.sdg_alignment
        }
    
    def calculate_health_score(self) -> Dict[str, Any]:
        """Calcular puntuación de salud del proyecto"""
        scores = {}
        total_score = 0
        
        # Progreso (25%)
        progress_score = min(100, self.progress_percentage)
        scores['progress'] = progress_score
        total_score += progress_score * 0.25
        
        # Métricas de negocio (25%)
        business_score = 0
        if self.current_revenue > 0:
            business_score += 30
        if self.total_users > 0:
            business_score += 25
        if self.active_users > 0 and self.total_users > 0:
            engagement = (self.active_users / self.total_users) * 100
            business_score += min(25, engagement * 0.25)
        if self.gross_margin > 0:
            business_score += min(20, self.gross_margin * 0.2)
        
        scores['business'] = business_score
        total_score += business_score * 0.25
        
        # Equipo (20%)
        team_score = min(100, self.team_size * 10)  # Max 10 personas = 100 pts
        scores['team'] = team_score
        total_score += team_score * 0.20
        
        # Financiamiento (15%)
        funding_score = 0
        if self.total_funding_raised > 0:
            funding_score = 50
        if self.runway_months >= 12:
            funding_score += 30
        elif self.runway_months >= 6:
            funding_score += 15
        if not self.seeking_funding or self.total_funding_raised > 0:
            funding_score += 20
        
        scores['funding'] = min(100, funding_score)
        total_score += scores['funding'] * 0.15
        
        # Tracción (15%)
        traction_score = 0
        if self.total_users >= 1000:
            traction_score += 30
        elif self.total_users >= 100:
            traction_score += 15
        
        if self.current_revenue > 0:
            traction_score += 40
        
        if len(self.mentors) > 0:
            traction_score += 15
        
        if len(self.interested_clients) > 0:
            traction_score += 15
        
        scores['traction'] = min(100, traction_score)
        total_score += scores['traction'] * 0.15
        
        # Determinar nivel de salud
        if total_score >= 80:
            health_level = 'excellent'
        elif total_score >= 60:
            health_level = 'good'
        elif total_score >= 40:
            health_level = 'fair'
        else:
            health_level = 'needs_attention'
        
        return {
            'total_score': round(total_score, 1),
            'health_level': health_level,
            'component_scores': scores,
            'recommendations': self._get_health_recommendations(scores)
        }
    
    def _get_health_recommendations(self, scores: Dict[str, float]) -> List[str]:
        """Obtener recomendaciones basadas en puntuaciones"""
        recommendations = []
        
        if scores['progress'] < 50:
            recommendations.append("Enfócate en completar más hitos y avanzar el desarrollo")
        
        if scores['business'] < 40:
            recommendations.append("Mejora las métricas de negocio: ingresos, usuarios y engagement")
        
        if scores['team'] < 60:
            recommendations.append("Considera expandir el equipo con talento complementario")
        
        if scores['funding'] < 50:
            recommendations.append("Evalúa opciones de financiamiento o mejora la gestión financiera")
        
        if scores['traction'] < 40:
            recommendations.append("Enfócate en generar tracción: usuarios, ingresos y partnerships")
        
        return recommendations
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def get_active_projects(cls):
        """Obtener proyectos activos"""
        return cls.query.filter(
            cls.status.in_([
                ProjectStatus.DEVELOPMENT,
                ProjectStatus.PILOT,
                ProjectStatus.TESTING,
                ProjectStatus.LAUNCH,
                ProjectStatus.ACTIVE,
                ProjectStatus.SCALING
            ]),
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def get_public_projects(cls, limit: int = None):
        """Obtener proyectos públicos"""
        query = cls.query.filter(
            cls.is_public == True,
            cls.is_deleted == False
        ).order_by(cls.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @classmethod
    def get_seeking_funding(cls):
        """Obtener proyectos que buscan financiamiento"""
        return cls.query.filter(
            cls.seeking_funding == True,
            cls.is_public == True,
            cls.status.in_([
                ProjectStatus.VALIDATION,
                ProjectStatus.DEVELOPMENT,
                ProjectStatus.PILOT,
                ProjectStatus.LAUNCH,
                ProjectStatus.ACTIVE,
                ProjectStatus.SCALING
            ]),
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def search_projects(cls, query_text: str = None, filters: Dict[str, Any] = None):
        """Buscar proyectos"""
        search = cls.query.filter(cls.is_deleted == False)
        
        if query_text:
            search_term = f"%{query_text}%"
            search = search.filter(
                cls.name.ilike(search_term) |
                cls.description.ilike(search_term) |
                cls.tagline.ilike(search_term) |
                cls.problem_statement.ilike(search_term)
            )
        
        if filters:
            if filters.get('status'):
                if isinstance(filters['status'], list):
                    search = search.filter(cls.status.in_(filters['status']))
                else:
                    search = search.filter(cls.status == filters['status'])
            
            if filters.get('type'):
                search = search.filter(cls.project_type == filters['type'])
            
            if filters.get('industry_sector'):
                search = search.filter(cls.industry_sector == filters['industry_sector'])
            
            if filters.get('funding_stage'):
                search = search.filter(cls.funding_stage == filters['funding_stage'])
            
            if filters.get('seeking_funding'):
                search = search.filter(cls.seeking_funding == True)
            
            if filters.get('entrepreneur_id'):
                search = search.filter(cls.entrepreneur_id == filters['entrepreneur_id'])
            
            if filters.get('organization_id'):
                search = search.filter(cls.supporting_organization_id == filters['organization_id'])
            
            if filters.get('public_only'):
                search = search.filter(cls.is_public == True)
            
            if filters.get('min_revenue'):
                search = search.filter(cls.current_revenue >= filters['min_revenue'] * 100)
            
            if filters.get('min_users'):
                search = search.filter(cls.total_users >= filters['min_users'])
        
        return search.order_by(cls.created_at.desc()).all()
    
    def to_dict(self, include_sensitive=False, include_relations=False) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'tagline': self.tagline,
            'description': self.description,
            'project_type': self.project_type.value,
            'status': self.status.value,
            'business_model': self.business_model.value if self.business_model else None,
            'industry_sector': self.industry_sector,
            'conception_date': self.conception_date.isoformat() if self.conception_date else None,
            'launch_date': self.launch_date.isoformat() if self.launch_date else None,
            'target_launch_date': self.target_launch_date.isoformat() if self.target_launch_date else None,
            'target_market': self.target_market,
            'problem_statement': self.problem_statement,
            'solution_description': self.solution_description,
            'value_proposition': self.value_proposition,
            'competitive_advantage': self.competitive_advantage,
            'progress_percentage': self.progress_percentage,
            'milestone_completion_rate': self.milestone_completion_rate,
            'funding_stage': self.funding_stage.value,
            'total_funding_raised': self.total_funding_raised / 100 if self.total_funding_raised else 0,
            'current_revenue': self.current_revenue / 100 if self.current_revenue else 0,
            'total_users': self.total_users,
            'active_users': self.active_users,
            'team_size': self.team_size,
            'is_public': self.is_public,
            'seeking_funding': self.seeking_funding,
            'seeking_mentorship': self.seeking_mentorship,
            'seeking_partners': self.seeking_partners,
            'website_url': self.website_url,
            'demo_url': self.demo_url,
            'logo_url': self.logo_url,
            'days_since_conception': self.days_since_conception,
            'days_to_launch': self.days_to_launch,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'revenue_streams': self.revenue_streams,
                'cost_structure': self.cost_structure,
                'pricing_model': self.pricing_model,
                'unit_economics': self.unit_economics,
                'monthly_revenue': self.monthly_revenue / 100 if self.monthly_revenue else 0,
                'annual_revenue': self.annual_revenue / 100 if self.annual_revenue else 0,
                'gross_margin': self.gross_margin,
                'burn_rate': self.burn_rate / 100 if self.burn_rate else 0,
                'runway_months': self.runway_months,
                'customer_acquisition_cost': self.customer_acquisition_cost / 100 if self.customer_acquisition_cost else 0,
                'lifetime_value': self.lifetime_value / 100 if self.lifetime_value else 0,
                'churn_rate': self.churn_rate,
                'valuation': self.valuation / 100 if self.valuation else 0,
                'funding_target': self.funding_target / 100 if self.funding_target else 0,
                'ltv_cac_ratio': self.ltv_cac_ratio,
                'user_engagement_rate': self.user_engagement_rate,
                'tech_stack': self.tech_stack,
                'intellectual_property': self.intellectual_property,
                'risk_factors': self.risk_factors,
                'mitigation_strategies': self.mitigation_strategies,
                'sustainability_goals': self.sustainability_goals,
                'social_impact': self.social_impact,
                'custom_fields': self.custom_fields,
                'notes': self.notes
            })
        
        if include_relations:
            data.update({
                'entrepreneur': self.entrepreneur.to_dict() if self.entrepreneur else None,
                'organization': self.supporting_organization.to_dict() if self.supporting_organization else None,
                'cofounders_count': len(self.cofounders),
                'mentors_count': len(self.mentors),
                'interested_clients_count': len(self.interested_clients),
                'milestones_count': len(self.milestones),
                'health_score': self.calculate_health_score()
            })
        
        return data


class ProjectMilestone(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Hito de Proyecto
    
    Representa hitos específicos dentro del desarrollo del proyecto.
    """
    
    __tablename__ = 'project_milestones'
    
    # Relación con proyecto
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    project = relationship("Project", back_populates="milestones")
    
    # Información del hito
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Fechas y plazos
    target_date = Column(Date)
    completed_at = Column(DateTime)
    
    # Estado y prioridad
    status = Column(String(20), default='pending', index=True)  # pending, in_progress, completed, cancelled
    priority = Column(SQLEnum(PriorityLevel), default=PriorityLevel.MEDIUM)
    
    # Métricas y KPIs asociados
    success_criteria = Column(JSON)  # Criterios de éxito
    metrics_target = Column(JSON)  # Métricas objetivo
    actual_metrics = Column(JSON)  # Métricas alcanzadas
    
    # Recursos y responsables
    assignee_id = Column(Integer, ForeignKey('users.id'))
    assignee = relationship("User")
    estimated_hours = Column(Integer)
    actual_hours = Column(Integer)
    
    # Notas y documentación
    notes = Column(Text)
    completion_notes = Column(Text)
    
    def __repr__(self):
        return f'<ProjectMilestone {self.title} - {self.status}>'
    
    @hybrid_property
    def is_overdue(self):
        """Verificar si está vencido"""
        return (self.target_date and 
                self.target_date < date.today() and 
                self.status != 'completed')
    
    @hybrid_property
    def days_until_due(self):
        """Días hasta vencimiento"""
        if self.target_date:
            return (self.target_date - date.today()).days
        return None
    
    def complete(self, completion_notes: str = None, actual_metrics: Dict[str, Any] = None):
        """Completar el hito"""
        if self.status == 'completed':
            raise ValidationError("El hito ya está completado")
        
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.completion_notes = completion_notes
        
        if actual_metrics:
            self.actual_metrics = actual_metrics
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority.value,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'success_criteria': self.success_criteria,
            'assignee': self.assignee.full_name if self.assignee else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }