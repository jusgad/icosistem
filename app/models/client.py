from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.user import User

class Client(db.Model):
    """Modelo para clientes corporativos o institucionales que patrocinan el programa"""
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    company_name = Column(String(100), nullable=False)
    industry = Column(String(100))
    company_size = Column(String(50))  # ej. "1-10", "11-50", "51-200", "201-500", "501+"
    website = Column(String(255))
    description = Column(Text)
    logo_url = Column(String(255))
    address = Column(String(255))
    city = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    phone = Column(String(20))
    
    # Campos específicos para clientes
    contact_person = Column(String(100))  # Persona de contacto principal
    contact_email = Column(String(100))
    contact_phone = Column(String(20))
    
    # Detalles del programa
    program_name = Column(String(100))  # Nombre del programa de emprendimiento
    max_entrepreneurs = Column(Integer, default=0)  # Número máximo de emprendedores
    program_start_date = Column(DateTime)
    program_end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = relationship('User', backref='client_profile', uselist=False)
    entrepreneurs = relationship('Entrepreneur', backref='client', lazy='dynamic')
    
    def __init__(self, user_id, company_name, **kwargs):
        self.user_id = user_id
        self.company_name = company_name
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        return f'<Client {self.company_name}>'
    
    @property
    def full_address(self):
        """Devuelve la dirección completa formateada"""
        address_parts = [self.address, self.city, self.country, self.postal_code]
        return ', '.join(filter(None, address_parts))
    
    @property
    def program_duration_days(self):
        """Calcula la duración del programa en días"""
        if self.program_start_date and self.program_end_date:
            return (self.program_end_date - self.program_start_date).days
        return None
    
    @property
    def entrepreneurs_count(self):
        """Devuelve el número actual de emprendedores en el programa"""
        return self.entrepreneurs.count()
    
    @property
    def program_progress(self):
        """Calcula el porcentaje de progreso del programa"""
        if not (self.program_start_date and self.program_end_date):
            return 0
            
        now = datetime.utcnow()
        
        # Si el programa no ha comenzado
        if now < self.program_start_date:
            return 0
            
        # Si el programa ha terminado
        if now > self.program_end_date:
            return 100
            
        # Calcular el progreso
        total_days = (self.program_end_date - self.program_start_date).days
        days_passed = (now - self.program_start_date).days
        
        if total_days <= 0:
            return 0
        
        return min(100, int((days_passed / total_days) * 100))
    
    def get_impact_metrics(self):
        """Obtiene métricas de impacto para el dashboard del cliente"""
        # Aquí se implementaría lógica para calcular métricas de impacto
        # como empleos generados, ingresos de emprendimientos, etc.
        return {
            'total_entrepreneurs': self.entrepreneurs.count(),
            'active_entrepreneurs': self.entrepreneurs.filter_by(is_active=True).count(),
            # Otras métricas se calcularían basándose en datos reales
        }
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs"""
        return {
            'id': self.id,
            'company_name': self.company_name,
            'industry': self.industry,
            'company_size': self.company_size,
            'website': self.website,
            'description': self.description,
            'logo_url': self.logo_url,
            'contact_person': self.contact_person,
            'program_name': self.program_name,
            'entrepreneurs_count': self.entrepreneurs_count,
            'program_progress': self.program_progress,
            'is_active': self.is_active
        }