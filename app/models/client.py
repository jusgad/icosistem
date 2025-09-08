"""
Modelo Cliente/Stakeholder del Ecosistema de Emprendimiento

Este módulo define el modelo para clientes y stakeholders que tienen interés
en monitorear y evaluar el progreso de emprendedores y proyectos.
"""

from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from enum import Enum

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    CLIENT_TYPES, 
    CLIENT_STATUS, 
    INDUSTRY_SECTORS, 
    COMPANY_SIZES,
    INTEREST_AREAS
)
from ..core.exceptions import ValidationError


class ClientType(Enum):
    """Tipos de cliente/stakeholder"""
    INVESTOR = "investor"
    CORPORATION = "corporation"
    GOVERNMENT = "government"
    NGO = "ngo"
    UNIVERSITY = "university"
    ACCELERATOR = "accelerator"
    INCUBATOR = "incubator"
    FOUNDATION = "foundation"
    INDIVIDUAL = "individual"


class ClientStatus(Enum):
    """Estados del cliente"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"
    PARTNER = "partner"
    SUSPENDED = "suspended"


class CompanySize(Enum):
    """Tamaños de empresa"""
    STARTUP = "startup"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class Client(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Cliente/Stakeholder
    
    Representa organizaciones o individuos que tienen interés en el ecosistema
    de emprendimiento, ya sea como inversores, corporaciones, gobierno, etc.
    """
    
    __tablename__ = 'clients'
    
    # Información básica
    name = Column(String(200), nullable=False, index=True)
    legal_name = Column(String(250))
    client_type = Column(SQLEnum(ClientType), nullable=False, index=True)
    status = Column(SQLEnum(ClientStatus), default=ClientStatus.ACTIVE, index=True)
    
    # Información de contacto
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    website = Column(String(200))
    
    # Información empresarial
    industry_sector = Column(String(100), index=True)
    company_size = Column(SQLEnum(CompanySize))
    founding_year = Column(Integer)
    tax_id = Column(String(50), unique=True)  # NIT, RFC, etc.
    
    # Ubicación
    country = Column(String(100), default='Colombia')
    city = Column(String(100))
    address = Column(Text)
    postal_code = Column(String(20))
    
    # Descripción y áreas de interés
    description = Column(Text)
    mission = Column(Text)
    vision = Column(Text)
    interest_areas = Column(JSON)  # Lista de áreas de interés
    investment_range = Column(JSON)  # Rango de inversión {min, max, currency}
    
    # Configuración de acceso
    dashboard_access = Column(Boolean, default=True)
    analytics_access = Column(Boolean, default=True)
    reports_access = Column(Boolean, default=True)
    
    # Configuración de notificaciones
    notification_preferences = Column(JSON, default=lambda: {
        'email_notifications': True,
        'sms_notifications': False,
        'weekly_reports': True,
        'monthly_reports': True,
        'project_updates': True,
        'milestone_alerts': True
    })
    
    # Configuración personalizada
    custom_fields = Column(JSON)  # Campos personalizados por cliente
    branding_config = Column(JSON)  # Configuración de marca personalizada
    
    # Métricas y estadísticas
    total_investment = Column(Integer, default=0)  # En centavos
    active_projects_count = Column(Integer, default=0)
    entrepreneurs_supported = Column(Integer, default=0)
    
    # Relaciones
    contact_person_id = Column(Integer, ForeignKey('users.id'))
    contact_person = relationship("User", foreign_keys=[contact_person_id])
    
    # Usuarios asociados al cliente
    users = relationship("User", back_populates="client", 
                        foreign_keys="User.client_id")
    
    # Proyectos en los que está interesado
    interested_projects = relationship("ProjectInterest", back_populates="client")
    
    # Reuniones programadas
    meetings = relationship("Meeting", back_populates="client")
    
    # Documentos compartidos
    documents = relationship("Document", back_populates="client")
    
    # Reportes generados
    reports = relationship("Report", back_populates="client")
    
    # Actividades del cliente
    activities = relationship("ActivityLog", back_populates="client")
    
    # Notificaciones
    notifications = relationship("Notification", back_populates="client")
    
    def __init__(self, **kwargs):
        """Inicialización del cliente"""
        super().__init__(**kwargs)
        
        # Inicializar configuraciones por defecto
        if not self.notification_preferences:
            self.notification_preferences = {
                'email_notifications': True,
                'sms_notifications': False,
                'weekly_reports': True,
                'monthly_reports': True,
                'project_updates': True,
                'milestone_alerts': True
            }
    
    def __repr__(self):
        return f'<Client {self.name} ({self.client_type.value})>'
    
    def __str__(self):
        return f'{self.name} - {self.client_type.value.title()}'
    
    # Validaciones
    @validates('email')
    def validate_email(self, key, email):
        """Validar formato de email"""
        import re
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError("Formato de email inválido")
        return email.lower() if email else None
    
    @validates('phone')
    def validate_phone(self, key, phone):
        """Validar formato de teléfono"""
        if phone:
            # Remover espacios y caracteres especiales
            cleaned = ''.join(filter(str.isdigit, phone))
            if len(cleaned) < 7 or len(cleaned) > 15:
                raise ValidationError("El teléfono debe tener entre 7 y 15 dígitos")
            return phone
        return None
    
    @validates('website')
    def validate_website(self, key, website):
        """Validar URL del sitio web"""
        if website and not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        return website
    
    @validates('founding_year')
    def validate_founding_year(self, key, year):
        """Validar año de fundación"""
        if year:
            current_year = datetime.now().year
            if year < 1800 or year > current_year:
                raise ValidationError(f"Año de fundación debe estar entre 1800 y {current_year}")
        return year
    
    @validates('interest_areas')
    def validate_interest_areas(self, key, areas):
        """Validar áreas de interés"""
        if areas:
            if not isinstance(areas, list):
                raise ValidationError("Las áreas de interés deben ser una lista")
            # Validar que las áreas estén en la lista permitida
            valid_areas = INTEREST_AREAS
            for area in areas:
                if area not in valid_areas:
                    raise ValidationError(f"Área de interés '{area}' no válida")
        return areas
    
    # Propiedades híbridas
    @hybrid_property
    def is_active(self):
        """Verificar si el cliente está activo"""
        return self.status == ClientStatus.ACTIVE and not self.is_deleted
    
    @hybrid_property
    def display_name(self):
        """Nombre para mostrar"""
        return self.legal_name or self.name
    
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
    def investment_range_formatted(self):
        """Rango de inversión formateado"""
        if not self.investment_range:
            return None
        
        min_val = self.investment_range.get('min', 0)
        max_val = self.investment_range.get('max', 0)
        currency = self.investment_range.get('currency', 'USD')
        
        if min_val and max_val:
            return f"{currency} {min_val:,} - {max_val:,}"
        elif min_val:
            return f"{currency} {min_val:,}+"
        elif max_val:
            return f"Hasta {currency} {max_val:,}"
        return None
    
    # Métodos de negocio
    def get_active_projects(self):
        """Obtener proyectos activos de interés"""
        from .project import Project, ProjectStatus
        
        return (Project.query
                .join(self.interested_projects)
                .filter(Project.status == ProjectStatus.ACTIVE)
                .filter(Project.is_deleted == False)
                .all())
    
    def get_supported_entrepreneurs(self):
        """Obtener emprendedores apoyados"""
        from .entrepreneur import Entrepreneur
        
        entrepreneur_ids = set()
        for project in self.get_active_projects():
            if project.entrepreneur_id:
                entrepreneur_ids.add(project.entrepreneur_id)
        
        if entrepreneur_ids:
            return Entrepreneur.query.filter(Entrepreneur.id.in_(entrepreneur_ids)).all()
        return []
    
    def add_interest_in_project(self, project, interest_level='medium', notes=None):
        """Agregar interés en un proyecto"""
        from .project import ProjectInterest
        
        # Verificar si ya existe el interés
        existing = ProjectInterest.query.filter_by(
            client_id=self.id,
            project_id=project.id
        ).first()
        
        if existing:
            existing.interest_level = interest_level
            existing.notes = notes
            existing.updated_at = datetime.now(timezone.utc)
            return existing
        
        # Crear nuevo interés
        interest = ProjectInterest(
            client_id=self.id,
            project_id=project.id,
            interest_level=interest_level,
            notes=notes
        )
        
        from .. import db
        db.session.add(interest)
        return interest
    
    def update_notification_preferences(self, preferences: dict[str, Any]):
        """Actualizar preferencias de notificación"""
        if not isinstance(preferences, dict):
            raise ValidationError("Las preferencias deben ser un diccionario")
        
        current_prefs = self.notification_preferences or {}
        current_prefs.update(preferences)
        self.notification_preferences = current_prefs
    
    def generate_dashboard_data(self) -> dict[str, Any]:
        """Generar datos para el dashboard del cliente"""
        active_projects = self.get_active_projects()
        entrepreneurs = self.get_supported_entrepreneurs()
        
        return {
            'client_info': {
                'name': self.display_name,
                'type': self.client_type.value,
                'status': self.status.value,
                'since': self.created_at.isoformat() if self.created_at else None
            },
            'metrics': {
                'active_projects': len(active_projects),
                'total_entrepreneurs': len(entrepreneurs),
                'total_investment': self.total_investment / 100,  # Convertir a unidades
                'success_stories': self._count_successful_projects()
            },
            'projects': [
                {
                    'id': project.id,
                    'name': project.name,
                    'entrepreneur': project.entrepreneur.full_name if project.entrepreneur else None,
                    'status': project.status.value,
                    'progress': project.progress_percentage,
                    'last_update': project.updated_at.isoformat() if project.updated_at else None
                }
                for project in active_projects[:10]  # Últimos 10 proyectos
            ],
            'recent_activities': self._get_recent_activities(limit=20)
        }
    
    def _count_successful_projects(self) -> int:
        """Contar proyectos exitosos"""
        from .project import Project, ProjectStatus
        
        return (Project.query
                .join(self.interested_projects)
                .filter(Project.status == ProjectStatus.COMPLETED)
                .count())
    
    def _get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
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
                'timestamp': activity.created_at.isoformat() if activity.created_at else None,
                'metadata': activity.metadata
            }
            for activity in activities
        ]
    
    def can_access_project(self, project) -> bool:
        """Verificar si el cliente puede acceder a un proyecto"""
        if not self.is_active:
            return False
        
        # Verificar si tiene interés en el proyecto
        from .project import ProjectInterest
        
        return ProjectInterest.query.filter_by(
            client_id=self.id,
            project_id=project.id
        ).first() is not None
    
    def get_investment_summary(self) -> dict[str, Any]:
        """Obtener resumen de inversiones"""
        active_projects = self.get_active_projects()
        
        return {
            'total_committed': self.total_investment / 100,
            'active_investments': len(active_projects),
            'avg_investment': (self.total_investment / len(active_projects) / 100) if active_projects else 0,
            'roi_estimate': self._calculate_roi_estimate(),
            'investment_by_sector': self._group_investments_by_sector()
        }
    
    def _calculate_roi_estimate(self) -> float:
        """Calcular estimación de ROI"""
        # Implementación simplificada - en producción sería más compleja
        successful_projects = self._count_successful_projects()
        total_projects = len(self.get_active_projects())
        
        if total_projects == 0:
            return 0.0
        
        success_rate = successful_projects / total_projects
        return success_rate * 100  # Porcentaje de éxito como ROI simplificado
    
    def _group_investments_by_sector(self) -> dict[str, int]:
        """Agrupar inversiones por sector"""
        sector_investments = {}
        
        for project in self.get_active_projects():
            sector = project.industry_sector or 'Otros'
            if sector not in sector_investments:
                sector_investments[sector] = 0
            # Aquí se podría calcular la inversión específica por proyecto
            sector_investments[sector] += 1
        
        return sector_investments
    
    @classmethod
    def get_active_clients(cls):
        """Obtener todos los clientes activos"""
        return cls.query.filter(
            cls.status == ClientStatus.ACTIVE,
            cls.is_deleted == False
        ).all()
    
    @classmethod
    def search_clients(cls, query: str, client_type: Optional[ClientType] = None):
        """Buscar clientes por nombre o email"""
        search = cls.query.filter(cls.is_deleted == False)
        
        if query:
            search_term = f"%{query}%"
            search = search.filter(
                cls.name.ilike(search_term) |
                cls.legal_name.ilike(search_term) |
                cls.email.ilike(search_term)
            )
        
        if client_type:
            search = search.filter(cls.client_type == client_type)
        
        return search.order_by(cls.name).all()
    
    def to_dict(self, include_sensitive=False) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'name': self.name,
            'legal_name': self.legal_name,
            'client_type': self.client_type.value if self.client_type else None,
            'status': self.status.value if self.status else None,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'industry_sector': self.industry_sector,
            'company_size': self.company_size.value if self.company_size else None,
            'founding_year': self.founding_year,
            'country': self.country,
            'city': self.city,
            'description': self.description,
            'interest_areas': self.interest_areas,
            'dashboard_access': self.dashboard_access,
            'analytics_access': self.analytics_access,
            'reports_access': self.reports_access,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'tax_id': self.tax_id,
                'address': self.address,
                'postal_code': self.postal_code,
                'investment_range': self.investment_range,
                'notification_preferences': self.notification_preferences,
                'custom_fields': self.custom_fields,
                'total_investment': self.total_investment / 100
            })
        
        return data