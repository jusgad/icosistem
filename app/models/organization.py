"""
Modelo Organización del Ecosistema de Emprendimiento

Este módulo define el modelo para organizaciones que participan en el ecosistema,
incluyendo incubadoras, aceleradoras, universidades, corporaciones, etc.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from app.extensions import db
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin, ContactMixin
from ..core.constants import (
    ORGANIZATION_TYPES,
    ORGANIZATION_STATUS,
    INDUSTRY_SECTORS,
    ORGANIZATION_SIZES,
    CERTIFICATION_TYPES,
    COUNTRIES,
    CURRENCIES
)
from ..core.exceptions import ValidationError


class OrganizationType(Enum):
    """Tipos de organización"""
    INCUBATOR = "incubator"
    ACCELERATOR = "accelerator"
    UNIVERSITY = "university"
    RESEARCH_CENTER = "research_center"
    CORPORATION = "corporation"
    GOVERNMENT = "government"
    NGO = "ngo"
    FOUNDATION = "foundation"
    VENTURE_CAPITAL = "venture_capital"
    ANGEL_NETWORK = "angel_network"
    STARTUP_HUB = "startup_hub"
    COWORKING = "coworking"
    CONSULTANCY = "consultancy"
    SERVICE_PROVIDER = "service_provider"


class OrganizationStatus(Enum):
    """Estados de la organización"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    PARTNER = "partner"
    SUSPENDED = "suspended"
    VERIFIED = "verified"


class OrganizationSize(Enum):
    """Tamaños de organización"""
    STARTUP = "startup"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class CertificationLevel(Enum):
    """Niveles de certificación"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


# Tabla de asociación para organizaciones colaboradoras
organization_partnerships = Table(
    'organization_partnerships',
    db.metadata,
    Column('organization_id', Integer, ForeignKey('organizations.id'), primary_key=True),
    Column('partner_id', Integer, ForeignKey('organizations.id'), primary_key=True),
    Column('partnership_type', String(50)),
    Column('start_date', Date),
    Column('end_date', Date),
    Column('status', String(20), default='active'),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Organization(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin, ContactMixin):
    """
    Modelo Organización
    
    Representa organizaciones que participan en el ecosistema de emprendimiento,
    proporcionando servicios, programas, financiamiento o apoyo.
    """
    
    __tablename__ = 'organizations'
    
    # Información básica
    name = Column(String(200), nullable=False, index=True)
    legal_name = Column(String(300))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    organization_type = Column(SQLEnum(OrganizationType), nullable=False, index=True)
    status = Column(SQLEnum(OrganizationStatus), default=OrganizationStatus.PENDING, index=True)
    
    # Información corporativa
    tax_id = Column(String(50), unique=True, index=True)  # NIT, RFC, EIN, etc.
    registration_number = Column(String(100))
    founding_date = Column(Date)
    organization_size = Column(SQLEnum(OrganizationSize))
    
    # Información de contacto (heredada de ContactMixin)
    # email, phone, website, address, city, country, postal_code
    
    # Información adicional
    description = Column(Text)
    mission = Column(Text)
    vision = Column(Text)
    values = Column(JSON)  # Lista de valores organizacionales
    
    # Sectores y especializaciones
    industry_sectors = Column(JSON)  # Lista de sectores de industria
    specializations = Column(JSON)  # Lista de especializaciones
    target_stages = Column(JSON)  # Etapas de emprendimiento que atienden
    
    # Información financiera
    annual_budget = Column(Integer)  # En centavos
    investment_capacity = Column(Integer)  # En centavos
    currency = Column(String(3), default='USD')
    
    # Capacidades y recursos
    team_size = Column(Integer)
    mentors_count = Column(Integer, default=0)
    programs_count = Column(Integer, default=0)
    entrepreneurs_served = Column(Integer, default=0)
    
    # Certificaciones y acreditaciones
    certifications = Column(JSON)  # Lista de certificaciones
    certification_level = Column(SQLEnum(CertificationLevel))
    accreditation_date = Column(Date)
    accreditation_expires = Column(Date)
    
    # Configuración de servicios
    services_offered = Column(JSON)  # Lista de servicios ofrecidos
    programs_offered = Column(JSON)  # Lista de programas disponibles
    application_process = Column(JSON)  # Proceso de aplicación
    
    # Métricas y KPIs
    success_rate = Column(Float, default=0.0)  # Tasa de éxito %
    average_program_duration = Column(Integer)  # En días
    total_investments_made = Column(Integer, default=0)  # En centavos
    companies_graduated = Column(Integer, default=0)
    jobs_created = Column(Integer, default=0)
    
    # Configuración de visibilidad
    is_public = Column(Boolean, default=True)
    show_in_directory = Column(Boolean, default=True)
    allow_applications = Column(Boolean, default=True)
    featured = Column(Boolean, default=False, index=True)
    
    # Configuración de notificaciones
    notification_settings = Column(JSON, default=lambda: {
        'new_applications': True,
        'program_updates': True,
        'partnership_requests': True,
        'weekly_reports': True,
        'monthly_analytics': True
    })
    
    # Configuración personalizada
    custom_fields = Column(JSON)
    branding_config = Column(JSON)  # Logo, colores, etc.
    social_media = Column(JSON)  # Enlaces a redes sociales
    
    # Geolocalización
    latitude = Column(Float)
    longitude = Column(Float)
    timezone = Column(String(50), default='UTC')
    
    # SEO y marketing
    meta_description = Column(String(160))
    keywords = Column(JSON)  # Keywords para SEO
    
    # Relaciones
    
    # Director/Contacto principal
    director_id = Column(Integer, ForeignKey('users.id'))
    director = relationship("User", foreign_keys=[director_id])
    
    # Usuarios/empleados de la organización
    employees = relationship("User", back_populates="organization",
                           foreign_keys="User.organization_id")
    
    # Programas ofrecidos por la organización
    programs = relationship("Program", back_populates="organization")
    
    # Proyectos apoyados
    supported_projects = relationship("Project", back_populates="supporting_organization")
    
    # Emprendedores en programas
    entrepreneurs = relationship("Entrepreneur", 
                               secondary="program_enrollments",
                               back_populates="organizations")
    
    # Reuniones organizadas
    meetings = relationship("Meeting", back_populates="organizing_organization")
    
    # Documentos y recursos
    documents = relationship("Document", back_populates="organization")
    
    # Eventos organizados
    events = relationship("Event", back_populates="organizer")
    
    # Actividades y logs
    activities = relationship("ActivityLog", back_populates="organization")
    
    # Métricas y analytics
    analytics = relationship("Analytics", back_populates="organization")
    
    # Organizaciones colaboradoras
    partnerships = relationship("Organization",
                              secondary=organization_partnerships,
                              primaryjoin="Organization.id == organization_partnerships.c.organization_id",
                              secondaryjoin="Organization.id == organization_partnerships.c.partner_id",
                              back_populates="partners")
    
    partners = relationship("Organization",
                          secondary=organization_partnerships,
                          primaryjoin="Organization.id == organization_partnerships.c.partner_id",
                          secondaryjoin="Organization.id == organization_partnerships.c.organization_id",  
                          back_populates="partnerships")
    
    def __init__(self, **kwargs):
        """Inicialización de la organización"""
        super().__init__(**kwargs)
        
        # Generar slug si no se proporciona
        if not self.slug and self.name:
            self.slug = self._generate_slug(self.name)
        
        # Inicializar configuraciones por defecto
        if not self.notification_settings:
            self.notification_settings = {
                'new_applications': True,
                'program_updates': True,
                'partnership_requests': True,
                'weekly_reports': True,
                'monthly_analytics': True
            }
        
        # Inicializar valores por defecto
        if not self.currency:
            self.currency = 'USD'
            
        if not self.timezone:
            self.timezone = 'UTC'
    
    def __repr__(self):
        return f'<Organization {self.name} ({self.organization_type.value})>'
    
    def __str__(self):
        return f'{self.name} - {self.organization_type.value.replace("_", " ").title()}'
    
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
        
        while Organization.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
    
    # Validaciones
    @validates('name')
    def validate_name(self, key, name):
        """Validar nombre de la organización"""
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
            if len(slug) > 100:
                raise ValidationError("El slug no puede exceder 100 caracteres")
        return slug
    
    @validates('tax_id')
    def validate_tax_id(self, key, tax_id):
        """Validar ID fiscal"""
        if tax_id:
            # Remover espacios y caracteres especiales
            cleaned = re.sub(r'[^\w]', '', tax_id)
            if len(cleaned) < 5:
                raise ValidationError("El ID fiscal debe tener al menos 5 caracteres")
        return tax_id
    
    @validates('email')
    def validate_email(self, key, email):
        """Validar formato de email"""
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError("Formato de email inválido")
        return email.lower() if email else None
    
    @validates('website')
    def validate_website(self, key, website):
        """Validar URL del sitio web"""
        if website:
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            # Validación básica de URL
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
                r'localhost|'  # localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(website):
                raise ValidationError("URL del sitio web inválida")
        return website
    
    @validates('founding_date')
    def validate_founding_date(self, key, founding_date):
        """Validar fecha de fundación"""
        if founding_date:
            if founding_date > date.today():
                raise ValidationError("La fecha de fundación no puede ser futura")
            if founding_date.year < 1800:
                raise ValidationError("La fecha de fundación no puede ser anterior a 1800")
        return founding_date
    
    @validates('industry_sectors')
    def validate_industry_sectors(self, key, sectors):
        """Validar sectores de industria"""
        if sectors:
            if not isinstance(sectors, list):
                raise ValidationError("Los sectores deben ser una lista")
            valid_sectors = INDUSTRY_SECTORS
            for sector in sectors:
                if sector not in valid_sectors:
                    raise ValidationError(f"Sector '{sector}' no válido")
        return sectors
    
    @validates('currency')
    def validate_currency(self, key, currency):
        """Validar código de moneda"""
        if currency:
            if currency not in CURRENCIES:
                raise ValidationError(f"Moneda '{currency}' no válida")
        return currency
    
    @validates('success_rate')
    def validate_success_rate(self, key, rate):
        """Validar tasa de éxito"""
        if rate is not None:
            if rate < 0 or rate > 100:
                raise ValidationError("La tasa de éxito debe estar entre 0 y 100")
        return rate
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si la organización está activa"""
        return self.status in [OrganizationStatus.ACTIVE, OrganizationStatus.VERIFIED] and not self.is_deleted
    
    @hybrid_property
    def display_name(self):
        """Nombre para mostrar"""
        return self.legal_name or self.name
    
    @hybrid_property
    def is_verified(self):
        """Verificar si está verificada"""
        return self.status == OrganizationStatus.VERIFIED
    
    @hybrid_property
    def is_partner(self):
        """Verificar si es socio/partner"""
        return self.status == OrganizationStatus.PARTNER
    
    @hybrid_property
    def full_address(self):
        """Dirección completa formateada"""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.country:
            parts.append(self.country)
        if self.postal_code:
            parts.append(f"CP: {self.postal_code}")
        return ', '.join(parts) if parts else None
    
    @hybrid_property
    def years_in_operation(self):
        """Años en operación"""
        if self.founding_date:
            return (date.today() - self.founding_date).days // 365
        return None
    
    @hybrid_property
    def budget_formatted(self):
        """Presupuesto formateado"""
        if self.annual_budget:
            return f"{self.currency} {self.annual_budget / 100:,.2f}"
        return None
    
    @hybrid_property
    def investment_capacity_formatted(self):
        """Capacidad de inversión formateada"""
        if self.investment_capacity:
            return f"{self.currency} {self.investment_capacity / 100:,.2f}"
        return None
    
    # Métodos de negocio
    def get_active_programs(self):
        """Obtener programas activos"""
        from .program import Program, ProgramStatus
        
        return self.programs.filter(
            Program.status == ProgramStatus.ACTIVE,
            Program.is_deleted == False
        ).all()
    
    def get_current_entrepreneurs(self):
        """Obtener emprendedores actuales en programas"""
        from .entrepreneur import Entrepreneur
        from .program import ProgramEnrollment
        
        current_enrollments = (ProgramEnrollment.query
                             .join(ProgramEnrollment.program)
                             .filter(Program.organization_id == self.id)
                             .filter(ProgramEnrollment.status == 'active')
                             .all())
        
        entrepreneur_ids = [enrollment.entrepreneur_id for enrollment in current_enrollments]
        
        return Entrepreneur.query.filter(Entrepreneur.id.in_(entrepreneur_ids)).all()
    
    def add_partnership(self, partner_org, partnership_type='collaboration', start_date=None):
        """Agregar una asociación con otra organización"""
        if not start_date:
            start_date = date.today()
        
        # Verificar que no existe ya la asociación
        existing = (organization_partnerships.query
                   .filter_by(organization_id=self.id, partner_id=partner_org.id)
                   .first())
        
        if existing:
            raise ValidationError("Ya existe una asociación con esta organización")
        
        from .. import db
        
        # Crear la asociación bidireccional
        partnership_data = {
            'organization_id': self.id,
            'partner_id': partner_org.id,
            'partnership_type': partnership_type,
            'start_date': start_date,
            'status': 'active'
        }
        
        db.session.execute(organization_partnerships.insert().values(partnership_data))
        
        # Asociación inversa
        reverse_partnership = {
            'organization_id': partner_org.id,
            'partner_id': self.id,
            'partnership_type': partnership_type,
            'start_date': start_date,
            'status': 'active'
        }
        
        db.session.execute(organization_partnerships.insert().values(reverse_partnership))
    
    def create_program(self, program_data):
        """Crear un nuevo programa"""
        from .program import Program
        
        program_data['organization_id'] = self.id
        program = Program(**program_data)
        
        from .. import db
        db.session.add(program)
        
        # Actualizar contador
        self.programs_count = len(self.programs)
        
        return program
    
    def calculate_success_metrics(self):
        """Calcular métricas de éxito"""
        from .program import Program, ProgramEnrollment
        from .project import Project, ProjectStatus
        
        # Calcular tasa de éxito
        total_enrollments = (ProgramEnrollment.query
                           .join(Program)
                           .filter(Program.organization_id == self.id)
                           .count())
        
        successful_enrollments = (ProgramEnrollment.query
                                .join(Program)
                                .filter(Program.organization_id == self.id)
                                .filter(ProgramEnrollment.status == 'graduated')
                                .count())
        
        if total_enrollments > 0:
            self.success_rate = (successful_enrollments / total_enrollments) * 100
        
        # Actualizar otros contadores
        self.entrepreneurs_served = total_enrollments
        self.companies_graduated = successful_enrollments
        
        # Calcular empleos creados (aproximación)
        successful_projects = (Project.query
                             .filter(Project.supporting_organization_id == self.id)
                             .filter(Project.status == ProjectStatus.COMPLETED)
                             .count())
        
        self.jobs_created = successful_projects * 5  # Estimación promedio
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Generar datos para el dashboard"""
        active_programs = self.get_active_programs()
        current_entrepreneurs = self.get_current_entrepreneurs()
        
        return {
            'organization_info': {
                'name': self.display_name,
                'type': self.organization_type.value,
                'status': self.status.value,
                'years_operating': self.years_in_operation,
                'certification_level': self.certification_level.value if self.certification_level else None,
                'is_verified': self.is_verified
            },
            'metrics': {
                'active_programs': len(active_programs),
                'current_entrepreneurs': len(current_entrepreneurs),
                'total_served': self.entrepreneurs_served,
                'success_rate': self.success_rate,
                'companies_graduated': self.companies_graduated,
                'jobs_created': self.jobs_created,
                'team_size': self.team_size,
                'mentors_count': self.mentors_count
            },
            'financial': {
                'annual_budget': self.budget_formatted,
                'investment_capacity': self.investment_capacity_formatted,
                'total_investments': f"{self.currency} {self.total_investments_made / 100:,.2f}" if self.total_investments_made else None
            },
            'programs': [
                {
                    'id': program.id,
                    'name': program.name,
                    'type': program.program_type.value if program.program_type else None,
                    'duration': program.duration_weeks,
                    'participants': len(program.active_enrollments),
                    'status': program.status.value
                }
                for program in active_programs[:10]
            ],
            'recent_activities': self._get_recent_activities(limit=20)
        }
    
    def get_public_profile(self) -> Dict[str, Any]:
        """Obtener perfil público de la organización"""
        if not self.is_public or not self.show_in_directory:
            return None
        
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'type': self.organization_type.value,
            'description': self.description,
            'mission': self.mission,
            'website': self.website,
            'city': self.city,
            'country': self.country,
            'industry_sectors': self.industry_sectors,
            'specializations': self.specializations,
            'services_offered': self.services_offered,
            'programs_count': self.programs_count,
            'entrepreneurs_served': self.entrepreneurs_served,
            'success_rate': self.success_rate,
            'certification_level': self.certification_level.value if self.certification_level else None,
            'is_verified': self.is_verified,
            'featured': self.featured,
            'social_media': self.social_media,
            'founded': self.founding_date.year if self.founding_date else None
        }
    
    def _get_recent_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtener actividades recientes"""
        activities = (self.activities
                     .order_by(self.activities.property.mapper.class_.created_at.desc())
                     .limit(limit)
                     .all())
        
        return [
            {
                'id': activity.id,
                'type': activity.activity_type,
                'description': activity.description,
                'timestamp': activity.created_at.isoformat(),
                'metadata': activity.metadata
            }
            for activity in activities
        ]
    
    def update_settings(self, settings: Dict[str, Any]):
        """Actualizar configuraciones"""
        allowed_settings = [
            'notification_settings', 'custom_fields', 'branding_config',
            'social_media', 'is_public', 'show_in_directory', 
            'allow_applications'
        ]
        
        for key, value in settings.items():
            if key in allowed_settings and hasattr(self, key):
                setattr(self, key, value)
    
    def can_accept_applications(self) -> bool:
        """Verificar si puede aceptar aplicaciones"""
        return (self.is_active and 
                self.allow_applications and 
                len(self.get_active_programs()) > 0)
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def get_active_organizations(cls):
        """Obtener organizaciones activas"""
        return cls.query.filter(
            cls.status.in_([OrganizationStatus.ACTIVE, OrganizationStatus.VERIFIED]),
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def get_public_directory(cls, organization_type=None, city=None, sector=None):
        """Obtener directorio público de organizaciones"""
        query = cls.query.filter(
            cls.is_public == True,
            cls.show_in_directory == True,
            cls.is_deleted == False
        )
        
        if organization_type:
            query = query.filter(cls.organization_type == organization_type)
        
        if city:
            query = query.filter(cls.city.ilike(f"%{city}%"))
        
        if sector:
            query = query.filter(cls.industry_sectors.contains([sector]))
        
        return query.order_by(cls.featured.desc(), cls.name).all()
    
    @classmethod
    def search_organizations(cls, query_text: str, filters: Dict[str, Any] = None):
        """Buscar organizaciones"""
        search = cls.query.filter(cls.is_deleted == False)
        
        if query_text:
            search_term = f"%{query_text}%"
            search = search.filter(
                cls.name.ilike(search_term) |
                cls.legal_name.ilike(search_term) |
                cls.description.ilike(search_term)
            )
        
        if filters:
            if filters.get('type'):
                search = search.filter(cls.organization_type == filters['type'])
            
            if filters.get('status'):
                search = search.filter(cls.status == filters['status'])
            
            if filters.get('city'):
                search = search.filter(cls.city.ilike(f"%{filters['city']}%"))
            
            if filters.get('country'):
                search = search.filter(cls.country == filters['country'])
            
            if filters.get('sector'):
                search = search.filter(cls.industry_sectors.contains([filters['sector']]))
            
            if filters.get('verified_only'):
                search = search.filter(cls.status == OrganizationStatus.VERIFIED)
        
        return search.order_by(cls.name).all()
    
    def to_dict(self, include_sensitive=False, include_relations=False) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'name': self.name,
            'legal_name': self.legal_name,
            'slug': self.slug,
            'organization_type': self.organization_type.value,
            'status': self.status.value,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'city': self.city,
            'country': self.country,
            'description': self.description,
            'mission': self.mission,
            'vision': self.vision,
            'industry_sectors': self.industry_sectors,
            'specializations': self.specializations,
            'services_offered': self.services_offered,
            'team_size': self.team_size,
            'mentors_count': self.mentors_count,
            'programs_count': self.programs_count,
            'entrepreneurs_served': self.entrepreneurs_served,
            'success_rate': self.success_rate,
            'is_public': self.is_public,
            'show_in_directory': self.show_in_directory,
            'featured': self.featured,
            'is_verified': self.is_verified,
            'years_in_operation': self.years_in_operation,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'tax_id': self.tax_id,
                'registration_number': self.registration_number,
                'address': self.address,
                'postal_code': self.postal_code,
                'annual_budget': self.annual_budget / 100 if self.annual_budget else None,
                'investment_capacity': self.investment_capacity / 100 if self.investment_capacity else None,
                'currency': self.currency,
                'notification_settings': self.notification_settings,
                'custom_fields': self.custom_fields,
                'branding_config': self.branding_config,
                'social_media': self.social_media
            })
        
        if include_relations:
            data.update({
                'programs': [program.to_dict() for program in self.get_active_programs()],
                'director': self.director.to_dict() if self.director else None,
                'partnerships_count': len(self.partnerships) if self.partnerships else 0
            })
        
        return data