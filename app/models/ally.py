from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum, Float
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.user import User, UserRole

class AllyType(enum.Enum):
    MENTOR = "mentor"
    CONSULTANT = "consultant"
    INVESTOR = "investor"
    EXPERT = "expert"
    PARTNER = "partner"

class AllyStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"

class AllySpecialty(db.Model):
    """Especialidades que pueden tener los aliados"""
    __tablename__ = "ally_specialties"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<AllySpecialty {self.name}>"

# Tabla de asociación para especialidades
ally_specialties = db.Table(
    'ally_specialty_association',
    db.Model.metadata,
    Column('ally_id', Integer, ForeignKey('allies.id')),
    Column('specialty_id', Integer, ForeignKey('ally_specialties.id'))
)

class Ally(db.Model):
    """Modelo de Aliado que extiende al modelo User"""
    __tablename__ = "allies"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    
    # Información profesional
    title = Column(String(100), nullable=True)
    organization = Column(String(255), nullable=True)
    position = Column(String(255), nullable=True)
    linkedin_profile = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    ally_type = Column(Enum(AllyType), default=AllyType.MENTOR)
    
    # Disponibilidad y capacidad
    availability_hours = Column(Integer, default=10)  # Horas mensuales disponibles
    max_entrepreneurs = Column(Integer, default=5)    # Máximo de emprendedores asignados
    
    # Estado y métricas
    status = Column(Enum(AllyStatus), default=AllyStatus.PENDING)
    rating = Column(Float, default=0.0)  # Valoración promedio
    total_hours_registered = Column(Float, default=0.0)  # Total de horas registradas
    
    # Programa de mentoría
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    is_volunteer = Column(Boolean, default=True)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = relationship("User", backref="ally_profile")
    specialties = relationship("AllySpecialty", secondary=ally_specialties, backref="allies")
    
    # Horas registradas
    registered_hours = relationship("AllyHours", backref="ally", lazy="dynamic")
    
    # Relación con mensajes
    sent_messages = relationship("Message", 
                              foreign_keys="Message.sender_id",
                              backref="sender_ally", 
                              lazy="dynamic")
    received_messages = relationship("Message", 
                                 foreign_keys="Message.recipient_id",
                                 backref="recipient_ally", 
                                 lazy="dynamic")
    
    # Relación con reuniones
    meetings = relationship("Meeting", backref="ally", lazy="dynamic")
    
    @classmethod
    def create_from_user(cls, user, **kwargs):
        """
        Crea un perfil de aliado a partir de un usuario existente.
        """
        if user.role != UserRole.ALLY:
            raise ValueError("El usuario debe tener el rol de aliado")
        
        ally = cls(user_id=user.id, **kwargs)
        db.session.add(ally)
        db.session.commit()
        return ally
    
    def add_specialty(self, specialty):
        """Añade una especialidad al aliado"""
        if specialty not in self.specialties:
            self.specialties.append(specialty)
            db.session.commit()
    
    def remove_specialty(self, specialty):
        """Elimina una especialidad del aliado"""
        if specialty in self.specialties:
            self.specialties.remove(specialty)
            db.session.commit()
    
    def get_current_entrepreneurs_count(self):
        """Obtiene el número actual de emprendedores asignados"""
        from app.models.relationship import EntrepreneurAllyRelationship
        
        return EntrepreneurAllyRelationship.query.filter_by(
            ally_id=self.id, 
            is_active=True
        ).count()
    
    def has_capacity(self):
        """Verifica si el aliado tiene capacidad para más emprendedores"""
        return self.get_current_entrepreneurs_count() < self.max_entrepreneurs
    
    def register_hours(self, entrepreneur_id, hours, activity_description, meeting_date=None):
        """Registra horas de acompañamiento"""
        from app.models.relationship import EntrepreneurAllyRelationship, AllyHours
        
        # Verificar que existe la relación
        relationship = EntrepreneurAllyRelationship.query.filter_by(
            entrepreneur_id=entrepreneur_id,
            ally_id=self.id,
            is_active=True
        ).first()
        
        if not relationship:
            raise ValueError("No existe una relación activa con este emprendedor")
        
        hours_entry = AllyHours(
            relationship_id=relationship.id,
            ally_id=self.id,
            entrepreneur_id=entrepreneur_id,
            hours=hours,
            activity_description=activity_description,
            meeting_date=meeting_date or datetime.utcnow()
        )
        
        db.session.add(hours_entry)
        
        # Actualizar el total de horas registradas
        self.total_hours_registered += hours
        
        db.session.commit()
        return hours_entry
    
    def update_status(self, status):
        """Actualiza el estado del aliado"""
        self.status = status
        if status == AllyStatus.INACTIVE:
            self.end_date = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'organization': self.organization,
            'position': self.position,
            'linkedin_profile': self.linkedin_profile,
            'website': self.website,
            'ally_type': self.ally_type.value,
            'availability_hours': self.availability_hours,
            'max_entrepreneurs': self.max_entrepreneurs,
            'current_entrepreneurs': self.get_current_entrepreneurs_count(),
            'status': self.status.value,
            'rating': self.rating,
            'total_hours_registered': self.total_hours_registered,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_volunteer': self.is_volunteer,
            'specialties': [s.name for s in self.specialties],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<Ally {self.user.full_name} ({self.ally_type.value})>"


class AllyHours(db.Model):
    """Registro de horas de acompañamiento de los aliados"""
    __tablename__ = "ally_hours"
    
    id = Column(Integer, primary_key=True)
    relationship_id = Column(Integer, ForeignKey('entrepreneur_ally_relationships.id'), nullable=False)
    ally_id = Column(Integer, ForeignKey('allies.id'), nullable=False)
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=False)
    
    # Detalles de las horas registradas
    hours = Column(Float, nullable=False)
    activity_description = Column(Text, nullable=False)
    meeting_date = Column(DateTime, nullable=False)
    
    # Validación
    is_validated = Column(Boolean, default=False)
    validated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    validation_date = Column(DateTime, nullable=True)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    validator = relationship("User", foreign_keys=[validated_by])
    entrepreneur = relationship("Entrepreneur", foreign_keys=[entrepreneur_id])
    
    def validate(self, validator_user_id):
        """Valida el registro de horas"""
        self.is_validated = True
        self.validated_by = validator_user_id
        self.validation_date = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convierte el modelo a un diccionario para APIs"""
        return {
            'id': self.id,
            'relationship_id': self.relationship_id,
            'ally_id': self.ally_id,
            'entrepreneur_id': self.entrepreneur_id,
            'hours': self.hours,
            'activity_description': self.activity_description,
            'meeting_date': self.meeting_date.isoformat(),
            'is_validated': self.is_validated,
            'validated_by': self.validated_by,
            'validation_date': self.validation_date.isoformat() if self.validation_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<AllyHours {self.hours}h for relationship {self.relationship_id}>"