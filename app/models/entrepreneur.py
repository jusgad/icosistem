from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Table, Enum
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.user import User, UserRole

# Tabla de asociación para categorías
entrepreneur_categories = Table(
    'entrepreneur_categories',
    db.Model.metadata,
    Column('entrepreneur_id', Integer, ForeignKey('entrepreneurs.id')),
    Column('category_id', Integer, ForeignKey('categories.id'))
)

class EntrepreneurStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    GRADUATED = "graduated"
    INACTIVE = "inactive"

class EntrepreneurType(enum.Enum):
    STARTUP = "startup"
    SOCIAL = "social_enterprise"
    SMALL_BUSINESS = "small_business"
    COOPERATIVE = "cooperative"
    OTHER = "other"

class Category(db.Model):
    """Categorías para clasificar emprendimientos"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Category {self.name}>"

class Entrepreneur(db.Model):
    """Modelo de Emprendedor que extiende al modelo User"""
    __tablename__ = "entrepreneurs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    
    # Información del emprendimiento
    business_name = Column(String(255), nullable=False)
    business_description = Column(Text, nullable=True)
    foundation_date = Column(DateTime, nullable=True)
    business_type = Column(Enum(EntrepreneurType), default=EntrepreneurType.STARTUP)
    website = Column(String(255), nullable=True)
    logo = Column(String(255), nullable=True)
    
    # Localización
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    
    # Métricas y estado
    status = Column(Enum(EntrepreneurStatus), default=EntrepreneurStatus.PENDING)
    employees_count = Column(Integer, default=1)
    annual_revenue = Column(Float, nullable=True)
    investment_received = Column(Float, default=0.0)
    
    # Programa de emprendimiento
    entry_date = Column(DateTime, default=datetime.utcnow)
    graduation_date = Column(DateTime, nullable=True)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = relationship("User", backref="entrepreneur_profile")
    categories = relationship("Category", secondary=entrepreneur_categories, backref="entrepreneurs")
    documents = relationship("Document", backref="entrepreneur", lazy="dynamic")
    tasks = relationship("Task", backref="entrepreneur", lazy="dynamic")
    
    # Relación con aliados a través de la tabla relationship
    allies = relationship("Ally", secondary="entrepreneur_ally_relationships", 
                          backref="supported_entrepreneurs")
    
    # Relación con mensajes
    sent_messages = relationship("Message", 
                              foreign_keys="Message.sender_id",
                              backref="sender", 
                              lazy="dynamic")
    received_messages = relationship("Message", 
                                  foreign_keys="Message.recipient_id",
                                  backref="recipient", 
                                  lazy="dynamic")
    
    # Relación con reuniones
    meetings = relationship("Meeting", backref="entrepreneur", lazy="dynamic")
    
    @classmethod
    def create_from_user(cls, user, business_name, **kwargs):
        """
        Crea un perfil de emprendedor a partir de un usuario existente.
        """
        if user.role != UserRole.ENTREPRENEUR:
            raise ValueError("El usuario debe tener el rol de emprendedor")
        
        entrepreneur = cls(user_id=user.id, business_name=business_name, **kwargs)
        db.session.add(entrepreneur)
        db.session.commit()
        return entrepreneur
    
    def add_category(self, category):
        """Añade una categoría al emprendimiento"""
        if category not in self.categories:
            self.categories.append(category)
            db.session.commit()
    
    def remove_category(self, category):
        """Elimina una categoría del emprendimiento"""
        if category in self.categories:
            self.categories.remove(category)
            db.session.commit()
    
    def assign_ally(self, ally):
        """Asigna un aliado al emprendedor"""
        from app.models.relationship import EntrepreneurAllyRelationship
        
        # Verificar si ya existe la relación
        existing = EntrepreneurAllyRelationship.query.filter_by(
            entrepreneur_id=self.id, ally_id=ally.id
        ).first()
        
        if not existing:
            relationship = EntrepreneurAllyRelationship(
                entrepreneur_id=self.id,
                ally_id=ally.id
            )
            db.session.add(relationship)
            db.session.commit()
            return relationship
        return existing
    
    def update_status(self, status):
        """Actualiza el estado del emprendedor"""
        self.status = status
        if status == EntrepreneurStatus.GRADUATED:
            self.graduation_date = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'business_name': self.business_name,
            'business_description': self.business_description,
            'foundation_date': self.foundation_date.isoformat() if self.foundation_date else None,
            'business_type': self.business_type.value,
            'website': self.website,
            'logo': self.logo,
            'country': self.country,
            'city': self.city,
            'status': self.status.value,
            'employees_count': self.employees_count,
            'annual_revenue': self.annual_revenue,
            'investment_received': self.investment_received,
            'entry_date': self.entry_date.isoformat(),
            'graduation_date': self.graduation_date.isoformat() if self.graduation_date else None,
            'categories': [c.name for c in self.categories],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<Entrepreneur {self.business_name}>"