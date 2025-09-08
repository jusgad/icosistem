"""
Relationship Model - Sistema de relaciones entre entidades
========================================================

Este módulo define los modelos para gestionar relaciones entre diferentes
entidades del ecosistema de emprendimiento de manera flexible y escalable.

Funcionalidades:
- Relaciones polimórficas entre cualquier entidad
- Tipos de relación configurables
- Estados y ciclo de vida de relaciones
- Metadatos y contexto adicional
- Relaciones bidireccionales y unidireccionales
- Historial y trazabilidad
- Permisos y visibilidad
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union
import json

from sqlalchemy import Index, event, and_, or_, func, case
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates, relationship as db_relationship

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class RelationshipType(Enum):
    """Tipos de relaciones en el ecosistema"""
    
    # Relaciones de mentoría
    MENTORSHIP = "mentorship"                    # Mentor -> Emprendedor
    PEER_MENTORSHIP = "peer_mentorship"          # Emprendedor -> Emprendedor
    REVERSE_MENTORSHIP = "reverse_mentorship"    # Joven -> Senior
    
    # Relaciones de colaboración
    PARTNERSHIP = "partnership"                  # Socios de negocio
    COLLABORATION = "collaboration"              # Colaboración en proyecto
    ADVISORY = "advisory"                        # Relación de asesoramiento
    
    # Relaciones organizacionales
    MEMBERSHIP = "membership"                    # Miembro de organización
    LEADERSHIP = "leadership"                    # Liderazgo en organización
    SPONSORSHIP = "sponsorship"                  # Patrocinio
    
    # Relaciones de programa
    ENROLLMENT = "enrollment"                    # Inscripción en programa
    FACILITATION = "facilitation"                # Facilitación de programa
    COORDINATION = "coordination"                # Coordinación de programa
    
    # Relaciones de apoyo
    SUPPORT = "support"                          # Relación de apoyo general
    COACHING = "coaching"                        # Relación de coaching
    CONSULTING = "consulting"                    # Relación de consultoría
    
    # Relaciones comerciales
    CLIENT_PROVIDER = "client_provider"          # Cliente -> Proveedor
    INVESTOR_ENTREPRENEUR = "investor_entrepreneur"  # Inversor -> Emprendedor
    SUPPLIER = "supplier"                        # Relación de proveedor
    
    # Relaciones de red
    NETWORK_CONNECTION = "network_connection"     # Conexión de red
    REFERRAL = "referral"                        # Referido por
    INTRODUCTION = "introduction"                # Introducción entre personas
    
    # Relaciones familiares/personales (en contexto profesional)
    FAMILY_BUSINESS = "family_business"          # Negocio familiar
    PERSONAL_REFERENCE = "personal_reference"    # Referencia personal
    
    # Relaciones institucionales
    UNIVERSITY_ALUMNI = "university_alumni"      # Ex-alumno universidad
    COMPANY_ALUMNI = "company_alumni"           # Ex-empleado empresa
    BOARD_MEMBER = "board_member"               # Miembro de junta
    
    # Relaciones de seguimiento
    FOLLOW = "follow"                           # Seguir (como redes sociales)
    SUBSCRIBE = "subscribe"                     # Suscripción a updates
    WATCH = "watch"                            # Observar progreso


class RelationshipStatus(Enum):
    """Estados de las relaciones"""
    PENDING = "pending"           # Pendiente de aceptación
    ACTIVE = "active"            # Activa
    INACTIVE = "inactive"        # Inactiva temporalmente
    PAUSED = "paused"           # Pausada
    COMPLETED = "completed"      # Completada exitosamente
    CANCELLED = "cancelled"      # Cancelada
    REJECTED = "rejected"        # Rechazada
    EXPIRED = "expired"         # Expirada


class RelationshipDirection(Enum):
    """Direccionalidad de la relación"""
    UNIDIRECTIONAL = "unidirectional"    # Solo en una dirección
    BIDIRECTIONAL = "bidirectional"      # Mutua/recíproca
    ASYMMETRIC = "asymmetric"           # Diferente en cada dirección


class RelationshipVisibility(Enum):
    """Visibilidad de la relación"""
    PUBLIC = "public"           # Visible públicamente
    ORGANIZATION = "organization"  # Visible en la organización
    PROGRAM = "program"         # Visible en el programa
    PARTICIPANTS = "participants"  # Solo participantes
    PRIVATE = "private"         # Privada


class Relationship(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Modelo principal para relaciones entre entidades
    
    Este modelo utiliza un patrón polimórfico para conectar cualquier
    tipo de entidad (usuarios, organizaciones, programas, proyectos, etc.)
    
    Attributes:
        id: ID único de la relación
        relationship_type: Tipo de relación
        status: Estado actual de la relación
        direction: Direccionalidad de la relación
        visibility: Nivel de visibilidad
        
        # Entidad origen (quien inicia/origina la relación)
        source_type: Tipo de entidad origen
        source_id: ID de entidad origen
        
        # Entidad destino (quien recibe la relación)
        target_type: Tipo de entidad destino
        target_id: ID de entidad destino
        
        # Contexto
        context_type: Tipo de contexto (organización, programa, etc.)
        context_id: ID del contexto
        
        # Metadata y configuración
        metadata: Datos adicionales en JSON
        settings: Configuraciones específicas
        tags: Etiquetas para categorización
        
        # Fechas importantes
        started_at: Fecha de inicio de la relación
        ended_at: Fecha de fin (si aplica)
        expires_at: Fecha de expiración (si aplica)
        
        # Información de gestión
        initiated_by: Usuario que inició la relación
        approved_by: Usuario que aprobó la relación
        priority: Prioridad de la relación
        strength: Fuerza/intensidad de la relación (0-100)
        
        # Métricas
        interaction_count: Número de interacciones
        last_interaction_at: Última interacción
        satisfaction_score: Puntuación de satisfacción
    """
    
    __tablename__ = 'relationships'
    
    # Tipo y estado
    relationship_type = db.Column(
        db.Enum(RelationshipType),
        nullable=False,
        index=True
    )
    
    status = db.Column(
        db.Enum(RelationshipStatus),
        nullable=False,
        default=RelationshipStatus.PENDING,
        index=True
    )
    
    direction = db.Column(
        db.Enum(RelationshipDirection),
        nullable=False,
        default=RelationshipDirection.BIDIRECTIONAL
    )
    
    visibility = db.Column(
        db.Enum(RelationshipVisibility),
        nullable=False,
        default=RelationshipVisibility.PARTICIPANTS
    )
    
    # Entidades relacionadas (polimórfico)
    source_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )
    
    source_id = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )
    
    target_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )
    
    target_id = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )
    
    # Contexto de la relación
    context_type = db.Column(
        db.String(50),
        nullable=True,
        index=True
    )
    
    context_id = db.Column(
        db.Integer,
        nullable=True,
        index=True
    )
    
    # Metadata flexible
    metadata = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    settings = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    tags = db.Column(
        JSONB,  # Array de strings
        nullable=True,
        default=list
    )
    
    # Fechas del ciclo de vida
    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    ended_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Gestión y aprobación
    initiated_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    approved_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # Propiedades de la relación
    priority = db.Column(
        db.Integer,
        nullable=False,
        default=5,  # 1-10 scale
        index=True
    )
    
    strength = db.Column(
        db.Integer,
        nullable=False,
        default=50,  # 0-100 scale
        index=True
    )
    
    # Métricas de interacción
    interaction_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    
    last_interaction_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    satisfaction_score = db.Column(
        db.Float,
        nullable=True  # 1.0-5.0 scale
    )
    
    # Notas y descripción
    description = db.Column(
        db.Text,
        nullable=True
    )
    
    notes = db.Column(
        db.Text,
        nullable=True
    )
    
    # Relaciones con usuarios
    initiator = db_relationship(
        'User',
        foreign_keys=[initiated_by],
        backref='initiated_relationships'
    )
    
    approver = db_relationship(
        'User',
        foreign_keys=[approved_by],
        backref='approved_relationships'
    )
    
    # Índices compuestos para optimización
    __table_args__ = (
        Index('ix_relationship_source', 'source_type', 'source_id'),
        Index('ix_relationship_target', 'target_type', 'target_id'),
        Index('ix_relationship_context', 'context_type', 'context_id'),
        Index('ix_relationship_type_status', 'relationship_type', 'status'),
        Index('ix_relationship_entities', 'source_type', 'source_id', 'target_type', 'target_id'),
        Index('ix_relationship_active', 'status', 'started_at'),
        # Constraint de unicidad para evitar duplicados
        db.UniqueConstraint('source_type', 'source_id', 'target_type', 'target_id', 
                           'relationship_type', 'context_type', 'context_id',
                           name='uq_relationship_entities'),
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<Relationship {self.relationship_type.value}: {self.source_type}({self.source_id}) -> {self.target_type}({self.target_id})>"
    
    @validates('priority')
    def validate_priority(self, key, value):
        """Valida que la prioridad esté en rango válido"""
        if value < 1 or value > 10:
            raise ValueError("La prioridad debe estar entre 1 y 10")
        return value
    
    @validates('strength')
    def validate_strength(self, key, value):
        """Valida que la fuerza esté en rango válido"""
        if value < 0 or value > 100:
            raise ValueError("La fuerza debe estar entre 0 y 100")
        return value
    
    @validates('satisfaction_score')
    def validate_satisfaction_score(self, key, value):
        """Valida que la puntuación de satisfacción esté en rango válido"""
        if value is not None and (value < 1.0 or value > 5.0):
            raise ValueError("La puntuación de satisfacción debe estar entre 1.0 y 5.0")
        return value
    
    @hybrid_property
    def is_active(self):
        """Verifica si la relación está activa"""
        return self.status == RelationshipStatus.ACTIVE
    
    @hybrid_property
    def is_expired(self):
        """Verifica si la relación ha expirado"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @hybrid_property
    def duration_days(self):
        """Calcula la duración de la relación en días"""
        if not self.started_at:
            return None
        
        end_date = self.ended_at or datetime.now(timezone.utc)
        return (end_date - self.started_at).days
    
    @hybrid_property
    def is_mentorship_type(self):
        """Verifica si es una relación de mentoría"""
        mentorship_types = {
            RelationshipType.MENTORSHIP,
            RelationshipType.PEER_MENTORSHIP,
            RelationshipType.REVERSE_MENTORSHIP,
            RelationshipType.COACHING
        }
        return self.relationship_type in mentorship_types
    
    def get_source_entity(self):
        """Obtiene la entidad origen de forma dinámica"""
        return self._get_entity(self.source_type, self.source_id)
    
    def get_target_entity(self):
        """Obtiene la entidad destino de forma dinámica"""
        return self._get_entity(self.target_type, self.target_id)
    
    def get_context_entity(self):
        """Obtiene la entidad de contexto de forma dinámica"""
        if not self.context_type or not self.context_id:
            return None
        return self._get_entity(self.context_type, self.context_id)
    
    def _get_entity(self, entity_type: str, entity_id: int):
        """Obtiene una entidad por tipo e ID"""
        # Mapeo de tipos a modelos
        type_to_model = {
            'user': 'User',
            'entrepreneur': 'Entrepreneur', 
            'ally': 'Ally',
            'client': 'Client',
            'admin': 'Admin',
            'organization': 'Organization',
            'program': 'Program',
            'project': 'Project',
            'meeting': 'Meeting'
        }
        
        model_name = type_to_model.get(entity_type.lower())
        if not model_name:
            return None
        
        try:
            from app.models import __dict__ as models_dict
            model_class = models_dict.get(model_name)
            if model_class:
                return model_class.query.get(entity_id)
        except Exception:
            pass
        
        return None
    
    def activate(self, approved_by_user_id: Optional[int] = None):
        """Activa la relación"""
        self.status = RelationshipStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)
        self.approved_by = approved_by_user_id
        
        # Crear relación inversa si es bidireccional
        if self.direction == RelationshipDirection.BIDIRECTIONAL:
            self._create_inverse_relationship()
    
    def deactivate(self, reason: Optional[str] = None):
        """Desactiva la relación"""
        self.status = RelationshipStatus.INACTIVE
        self.ended_at = datetime.now(timezone.utc)
        
        if reason:
            self.notes = f"{self.notes or ''}\nDesactivada: {reason}".strip()
    
    def complete(self, satisfaction_score: Optional[float] = None):
        """Marca la relación como completada"""
        self.status = RelationshipStatus.COMPLETED
        self.ended_at = datetime.now(timezone.utc)
        
        if satisfaction_score:
            self.satisfaction_score = satisfaction_score
    
    def record_interaction(self, interaction_metadata: Optional[dict[str, Any]] = None):
        """Registra una interacción en la relación"""
        self.interaction_count += 1
        self.last_interaction_at = datetime.now(timezone.utc)
        
        # Actualizar fuerza basada en frecuencia de interacciones
        self._update_strength_from_interactions()
        
        if interaction_metadata:
            interactions = self.metadata.get('interactions', [])
            interactions.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **interaction_metadata
            })
            self.metadata = {**self.metadata, 'interactions': interactions}
    
    def _update_strength_from_interactions(self):
        """Actualiza la fuerza basada en las interacciones"""
        if not self.started_at:
            return
        
        days_active = (datetime.now(timezone.utc) - self.started_at).days or 1
        interaction_frequency = self.interaction_count / days_active
        
        # Lógica simple: más interacciones = mayor fuerza
        if interaction_frequency > 1:  # Más de una interacción por día
            self.strength = min(100, self.strength + 1)
        elif interaction_frequency < 0.1:  # Menos de una interacción por 10 días
            self.strength = max(0, self.strength - 1)
    
    def _create_inverse_relationship(self):
        """Crea la relación inversa para relaciones bidireccionales"""
        inverse = Relationship.query.filter_by(
            source_type=self.target_type,
            source_id=self.target_id,
            target_type=self.source_type,
            target_id=self.source_id,
            relationship_type=self.relationship_type,
            context_type=self.context_type,
            context_id=self.context_id
        ).first()
        
        if not inverse:
            inverse = Relationship(
                relationship_type=self.relationship_type,
                source_type=self.target_type,
                source_id=self.target_id,
                target_type=self.source_type,
                target_id=self.source_id,
                context_type=self.context_type,
                context_id=self.context_id,
                status=RelationshipStatus.ACTIVE,
                direction=RelationshipDirection.BIDIRECTIONAL,
                visibility=self.visibility,
                started_at=self.started_at,
                expires_at=self.expires_at,
                priority=self.priority,
                strength=self.strength,
                initiated_by=self.initiated_by,
                approved_by=self.approved_by
            )
            db.session.add(inverse)
    
    def to_dict(self, include_entities=False):
        """Convierte la relación a diccionario"""
        data = {
            'id': self.id,
            'relationship_type': self.relationship_type.value,
            'status': self.status.value,
            'direction': self.direction.value,
            'visibility': self.visibility.value,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'context_type': self.context_type,
            'context_id': self.context_id,
            'priority': self.priority,
            'strength': self.strength,
            'interaction_count': self.interaction_count,
            'satisfaction_score': self.satisfaction_score,
            'description': self.description,
            'metadata': self.metadata,
            'settings': self.settings,
            'tags': self.tags,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_interaction_at': self.last_interaction_at.isoformat() if self.last_interaction_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_entities:
            data['source_entity'] = self._entity_to_dict(self.get_source_entity())
            data['target_entity'] = self._entity_to_dict(self.get_target_entity())
            data['context_entity'] = self._entity_to_dict(self.get_context_entity())
        
        return data
    
    def _entity_to_dict(self, entity):
        """Convierte una entidad a diccionario básico"""
        if not entity:
            return None
        
        return {
            'id': entity.id,
            'type': entity.__class__.__name__.lower(),
            'name': getattr(entity, 'name', None) or getattr(entity, 'full_name', None) or str(entity)
        }


class RelationshipHistory(BaseModel, TimestampMixin):
    """
    Historial de cambios en relaciones
    
    Attributes:
        id: ID único del registro de historial
        relationship_id: ID de la relación
        field_changed: Campo que cambió
        old_value: Valor anterior
        new_value: Nuevo valor
        changed_by: Usuario que realizó el cambio
        change_reason: Razón del cambio
        change_context: Contexto adicional del cambio
    """
    
    __tablename__ = 'relationship_history'
    
    relationship_id = db.Column(
        db.Integer,
        db.ForeignKey('relationships.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    field_changed = db.Column(
        db.String(100),
        nullable=False
    )
    
    old_value = db.Column(
        db.Text,
        nullable=True
    )
    
    new_value = db.Column(
        db.Text,
        nullable=True
    )
    
    changed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    
    change_reason = db.Column(
        db.Text,
        nullable=True
    )
    
    change_context = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Relaciones
    relationship = db_relationship('Relationship', backref='change_history')
    user = db_relationship('User', backref='relationship_changes')


class RelationshipManager:
    """Gestor de relaciones del sistema"""
    
    @staticmethod
    def create_relationship(
        relationship_type: RelationshipType,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        context_type: Optional[str] = None,
        context_id: Optional[int] = None,
        initiated_by: Optional[int] = None,
        auto_approve: bool = False,
        **kwargs
    ) -> Relationship:
        """
        Crea una nueva relación
        
        Args:
            relationship_type: Tipo de relación
            source_type: Tipo de entidad origen
            source_id: ID de entidad origen
            target_type: Tipo de entidad destino
            target_id: ID de entidad destino
            context_type: Tipo de contexto
            context_id: ID de contexto
            initiated_by: Usuario que inicia
            auto_approve: Si aprobar automáticamente
            **kwargs: Parámetros adicionales
            
        Returns:
            Nueva instancia de Relationship
        """
        # Verificar si ya existe
        existing = Relationship.query.filter_by(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            context_type=context_type,
            context_id=context_id
        ).first()
        
        if existing and existing.status != RelationshipStatus.CANCELLED:
            raise ValueError("La relación ya existe")
        
        relationship = Relationship(
            relationship_type=relationship_type,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            context_type=context_type,
            context_id=context_id,
            initiated_by=initiated_by,
            **kwargs
        )
        
        db.session.add(relationship)
        
        if auto_approve:
            relationship.activate(initiated_by)
        
        db.session.commit()
        return relationship
    
    @staticmethod
    def get_relationships_for_entity(
        entity_type: str,
        entity_id: int,
        relationship_types: Optional[list[RelationshipType]] = None,
        status_filter: Optional[RelationshipStatus] = None,
        as_source: bool = True,
        as_target: bool = True
    ) -> list[Relationship]:
        """
        Obtiene todas las relaciones de una entidad
        
        Args:
            entity_type: Tipo de entidad
            entity_id: ID de entidad
            relationship_types: Filtrar por tipos específicos
            status_filter: Filtrar por estado
            as_source: Incluir como entidad origen
            as_target: Incluir como entidad destino
            
        Returns:
            Lista de relaciones
        """
        conditions = []
        
        if as_source:
            conditions.append(
                and_(
                    Relationship.source_type == entity_type,
                    Relationship.source_id == entity_id
                )
            )
        
        if as_target:
            conditions.append(
                and_(
                    Relationship.target_type == entity_type,
                    Relationship.target_id == entity_id
                )
            )
        
        if not conditions:
            return []
        
        query = Relationship.query.filter(or_(*conditions))
        
        if relationship_types:
            query = query.filter(Relationship.relationship_type.in_(relationship_types))
        
        if status_filter:
            query = query.filter(Relationship.status == status_filter)
        
        return query.all()
    
    @staticmethod
    def get_mentorship_relationships(
        user_id: int,
        user_type: str = 'user',
        as_mentor: bool = True,
        as_mentee: bool = True,
        active_only: bool = True
    ) -> dict[str, list[Relationship]]:
        """
        Obtiene relaciones de mentoría específicas
        
        Returns:
            Diccionario con 'as_mentor' y 'as_mentee'
        """
        mentorship_types = [
            RelationshipType.MENTORSHIP,
            RelationshipType.PEER_MENTORSHIP,
            RelationshipType.COACHING
        ]
        
        all_relationships = RelationshipManager.get_relationships_for_entity(
            user_type, user_id, mentorship_types,
            RelationshipStatus.ACTIVE if active_only else None
        )
        
        result = {'as_mentor': [], 'as_mentee': []}
        
        for rel in all_relationships:
            # Si es la entidad origen y el tipo implica mentoría hacia el target
            if (rel.source_type == user_type and rel.source_id == user_id and as_mentor):
                result['as_mentor'].append(rel)
            # Si es la entidad destino y está recibiendo mentoría
            elif (rel.target_type == user_type and rel.target_id == user_id and as_mentee):
                result['as_mentee'].append(rel)
        
        return result
    
    @staticmethod
    def update_relationship_strength(relationship_id: int, new_strength: int):
        """Actualiza la fuerza de una relación"""
        relationship = Relationship.query.get(relationship_id)
        if relationship:
            old_strength = relationship.strength
            relationship.strength = new_strength
            
            # Registrar cambio en historial
            RelationshipManager._record_change(
                relationship_id, 'strength', str(old_strength), str(new_strength)
            )
            
            db.session.commit()
    
    @staticmethod
    def expire_old_relationships(days_inactive: int = 180):
        """Marca como expiradas las relaciones inactivas por mucho tiempo"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)
        
        old_relationships = Relationship.query.filter(
            Relationship.status == RelationshipStatus.ACTIVE,
            or_(
                Relationship.last_interaction_at < cutoff_date,
                and_(
                    Relationship.last_interaction_at.is_(None),
                    Relationship.started_at < cutoff_date
                )
            )
        )
        
        count = 0
        for rel in old_relationships:
            rel.status = RelationshipStatus.EXPIRED
            count += 1
        
        db.session.commit()
        return count
    
    @staticmethod
    def get_relationship_analytics(
        organization_id: Optional[int] = None,
        relationship_type: Optional[RelationshipType] = None
    ) -> dict[str, Any]:
        """
        Genera analytics básicas de relaciones
        
        Returns:
            Diccionario con métricas de relaciones
        """
        query = Relationship.query
        
        if organization_id:
            # Filtrar por contexto de organización o entidades de la organización
            query = query.filter(
                or_(
                    and_(Relationship.context_type == 'organization', 
                         Relationship.context_id == organization_id),
                    # También incluir relaciones donde las entidades pertenecen a la org
                    Relationship.metadata.contains({'organization_id': organization_id})
                )
            )
        
        if relationship_type:
            query = query.filter(Relationship.relationship_type == relationship_type)
        
        # Métricas básicas
        total_relationships = query.count()
        
        # Por estado
        status_counts = db.session.query(
            Relationship.status,
            func.count(Relationship.id)
        ).filter(
            query.whereclause
        ).group_by(Relationship.status).all()
        
        # Por tipo
        type_counts = db.session.query(
            Relationship.relationship_type,
            func.count(Relationship.id)
        ).filter(
            query.whereclause
        ).group_by(Relationship.relationship_type).all()
        
        # Métricas de fuerza promedio
        avg_strength = db.session.query(
            func.avg(Relationship.strength)
        ).filter(
            query.whereclause,
            Relationship.status == RelationshipStatus.ACTIVE
        ).scalar() or 0
        
        # Satisfacción promedio
        avg_satisfaction = db.session.query(
            func.avg(Relationship.satisfaction_score)
        ).filter(
            query.whereclause,
            Relationship.satisfaction_score.isnot(None)
        ).scalar() or 0
        
        return {
            'total_relationships': total_relationships,
            'status_breakdown': {status.value: count for status, count in status_counts},
            'type_breakdown': {rel_type.value: count for rel_type, count in type_counts},
            'average_strength': round(float(avg_strength), 2),
            'average_satisfaction': round(float(avg_satisfaction), 2),
            'active_relationships': sum(count for status, count in status_counts 
                                     if status == RelationshipStatus.ACTIVE)
        }
    
    @staticmethod
    def _record_change(
        relationship_id: int,
        field: str,
        old_value: str,
        new_value: str,
        changed_by: Optional[int] = None,
        reason: Optional[str] = None
    ):
        """Registra un cambio en el historial"""
        history = RelationshipHistory(
            relationship_id=relationship_id,
            field_changed=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            change_reason=reason
        )
        db.session.add(history)


class RelationshipRecommendation(BaseModel, TimestampMixin):
    """
    Modelo para recomendaciones de relaciones
    
    Attributes:
        id: ID único de la recomendación
        source_type: Tipo de entidad origen
        source_id: ID de entidad origen
        target_type: Tipo de entidad destino
        target_id: ID de entidad destino
        relationship_type: Tipo de relación recomendada
        confidence_score: Puntuación de confianza (0-100)
        reasoning: Lógica detrás de la recomendación
        metadata: Datos que respaldan la recomendación
        status: Estado de la recomendación
        expires_at: Fecha de expiración
        presented_at: Cuándo se presentó al usuario
        user_feedback: Feedback del usuario sobre la recomendación
    """
    
    __tablename__ = 'relationship_recommendations'
    
    source_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )
    
    source_id = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )
    
    target_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )
    
    target_id = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )
    
    relationship_type = db.Column(
        db.Enum(RelationshipType),
        nullable=False,
        index=True
    )
    
    confidence_score = db.Column(
        db.Integer,
        nullable=False,
        default=50  # 0-100
    )
    
    reasoning = db.Column(
        db.Text,
        nullable=True
    )
    
    metadata = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    status = db.Column(
        db.String(20),
        nullable=False,
        default='pending',
        index=True
    )
    
    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    presented_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )
    
    user_feedback = db.Column(
        db.String(20),
        nullable=True  # 'accepted', 'rejected', 'ignored'
    )
    
    feedback_reason = db.Column(
        db.Text,
        nullable=True
    )
    
    # Índices
    __table_args__ = (
        Index('ix_recommendation_source', 'source_type', 'source_id'),
        Index('ix_recommendation_target', 'target_type', 'target_id'),
        Index('ix_recommendation_confidence', 'confidence_score', 'status'),
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<RelationshipRecommendation {self.relationship_type.value}: {self.source_type}({self.source_id}) -> {self.target_type}({self.target_id})>"
    
    def mark_as_presented(self):
        """Marca la recomendación como presentada"""
        self.presented_at = datetime.now(timezone.utc)
        self.status = 'presented'
    
    def record_feedback(self, feedback: str, reason: Optional[str] = None):
        """Registra feedback del usuario"""
        self.user_feedback = feedback
        self.feedback_reason = reason
        self.status = 'completed'


class RelationshipRecommendationEngine:
    """Motor de recomendaciones de relaciones"""
    
    @staticmethod
    def generate_mentorship_recommendations(
        user_id: int,
        user_type: str = 'user',
        limit: int = 10
    ) -> list[RelationshipRecommendation]:
        """
        Genera recomendaciones de mentoría para un usuario
        
        Args:
            user_id: ID del usuario
            user_type: Tipo de usuario
            limit: Límite de recomendaciones
            
        Returns:
            Lista de recomendaciones
        """
        recommendations = []
        
        # Obtener información del usuario
        user_entity = RelationshipManager._get_entity_by_type(user_type, user_id)
        if not user_entity:
            return recommendations
        
        # Lógica de recomendación basada en:
        # 1. Experiencia complementaria
        # 2. Industria/sector
        # 3. Intereses comunes
        # 4. Ubicación geográfica
        # 5. Disponibilidad
        
        # Buscar potenciales mentores (usuarios más experimentados)
        potential_mentors = RelationshipManager._find_potential_mentors(
            user_entity, limit * 2
        )
        
        for mentor in potential_mentors:
            confidence = RelationshipRecommendationEngine._calculate_mentorship_confidence(
                user_entity, mentor
            )
            
            if confidence >= 30:  # Umbral mínimo
                recommendation = RelationshipRecommendation(
                    source_type='user',
                    source_id=mentor.id,
                    target_type=user_type,
                    target_id=user_id,
                    relationship_type=RelationshipType.MENTORSHIP,
                    confidence_score=confidence,
                    reasoning=RelationshipRecommendationEngine._generate_mentorship_reasoning(
                        user_entity, mentor
                    ),
                    metadata={
                        'mentor_experience': getattr(mentor, 'years_experience', 0),
                        'common_interests': RelationshipRecommendationEngine._find_common_interests(
                            user_entity, mentor
                        ),
                        'industry_match': RelationshipRecommendationEngine._check_industry_match(
                            user_entity, mentor
                        )
                    },
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30)
                )
                
                recommendations.append(recommendation)
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations
    
    @staticmethod
    def generate_collaboration_recommendations(
        project_id: int,
        limit: int = 10
    ) -> list[RelationshipRecommendation]:
        """
        Genera recomendaciones de colaboración para un proyecto
        
        Args:
            project_id: ID del proyecto
            limit: Límite de recomendaciones
            
        Returns:
            Lista de recomendaciones
        """
        recommendations = []
        
        # Obtener información del proyecto
        project = RelationshipManager._get_entity_by_type('project', project_id)
        if not project:
            return recommendations
        
        # Buscar emprendedores con proyectos complementarios
        complementary_entrepreneurs = RelationshipManager._find_complementary_entrepreneurs(
            project, limit * 2
        )
        
        for entrepreneur in complementary_entrepreneurs:
            confidence = RelationshipRecommendationEngine._calculate_collaboration_confidence(
                project, entrepreneur
            )
            
            if confidence >= 40:  # Umbral para colaboración
                recommendation = RelationshipRecommendation(
                    source_type='project',
                    source_id=project_id,
                    target_type='user',
                    target_id=entrepreneur.id,
                    relationship_type=RelationshipType.COLLABORATION,
                    confidence_score=confidence,
                    reasoning=RelationshipRecommendationEngine._generate_collaboration_reasoning(
                        project, entrepreneur
                    ),
                    metadata={
                        'skill_complementarity': RelationshipRecommendationEngine._calculate_skill_complementarity(
                            project, entrepreneur
                        ),
                        'project_stage_compatibility': RelationshipRecommendationEngine._check_stage_compatibility(
                            project, entrepreneur
                        )
                    },
                    expires_at=datetime.now(timezone.utc) + timedelta(days=14)
                )
                
                recommendations.append(recommendation)
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations
    
    @staticmethod
    def _calculate_mentorship_confidence(user_entity, mentor_entity) -> int:
        """Calcula la confianza para una recomendación de mentoría"""
        confidence = 0
        
        # Factor de experiencia (0-30 puntos)
        experience_diff = getattr(mentor_entity, 'years_experience', 0) - getattr(user_entity, 'years_experience', 0)
        if experience_diff > 5:
            confidence += min(30, experience_diff * 3)
        
        # Factor de industria (0-25 puntos)
        if RelationshipRecommendationEngine._check_industry_match(user_entity, mentor_entity):
            confidence += 25
        
        # Factor de intereses comunes (0-20 puntos)
        common_interests = len(RelationshipRecommendationEngine._find_common_interests(user_entity, mentor_entity))
        confidence += min(20, common_interests * 5)
        
        # Factor de disponibilidad (0-15 puntos)
        if getattr(mentor_entity, 'available_for_mentorship', False):
            confidence += 15
        
        # Factor de ubicación (0-10 puntos)
        if getattr(user_entity, 'location', '') == getattr(mentor_entity, 'location', ''):
            confidence += 10
        
        return min(100, confidence)
    
    @staticmethod
    def _calculate_collaboration_confidence(project, entrepreneur) -> int:
        """Calcula la confianza para una recomendación de colaboración"""
        confidence = 0
        
        # Factor de complementariedad de habilidades (0-35 puntos)
        skill_complement = RelationshipRecommendationEngine._calculate_skill_complementarity(project, entrepreneur)
        confidence += min(35, skill_complement * 7)
        
        # Factor de compatibilidad de etapa (0-25 puntos)
        if RelationshipRecommendationEngine._check_stage_compatibility(project, entrepreneur):
            confidence += 25
        
        # Factor de industria (0-20 puntos)
        if getattr(project, 'industry', '') == getattr(entrepreneur, 'industry', ''):
            confidence += 20
        
        # Factor de tamaño de equipo (0-20 puntos)
        project_team_size = getattr(project, 'team_size', 0)
        if project_team_size < 5:  # Proyectos pequeños más abiertos a colaboración
            confidence += 20
        
        return min(100, confidence)
    
    @staticmethod
    def _find_common_interests(entity1, entity2) -> list[str]:
        """Encuentra intereses comunes entre dos entidades"""
        interests1 = set(getattr(entity1, 'interests', []) or [])
        interests2 = set(getattr(entity2, 'interests', []) or [])
        return list(interests1.intersection(interests2))
    
    @staticmethod
    def _check_industry_match(entity1, entity2) -> bool:
        """Verifica si dos entidades están en la misma industria"""
        industry1 = getattr(entity1, 'industry', '')
        industry2 = getattr(entity2, 'industry', '')
        return industry1 and industry2 and industry1.lower() == industry2.lower()
    
    @staticmethod
    def _calculate_skill_complementarity(project, entrepreneur) -> int:
        """Calcula la complementariedad de habilidades (0-5 scale)"""
        project_skills = set(getattr(project, 'required_skills', []) or [])
        entrepreneur_skills = set(getattr(entrepreneur, 'skills', []) or [])
        
        if not project_skills:
            return 0
        
        # Porcentaje de habilidades del proyecto que el emprendedor posee
        matching_skills = project_skills.intersection(entrepreneur_skills)
        complementarity = len(matching_skills) / len(project_skills)
        
        return int(complementarity * 5)
    
    @staticmethod
    def _check_stage_compatibility(project, entrepreneur) -> bool:
        """Verifica compatibilidad de etapas de desarrollo"""
        project_stage = getattr(project, 'stage', '')
        entrepreneur_stage = getattr(entrepreneur, 'preferred_stage', '')
        
        # Lógica simple: etapas similares son compatibles
        stage_mapping = {
            'idea': 1,
            'prototype': 2,
            'mvp': 3,
            'growth': 4,
            'scale': 5
        }
        
        project_level = stage_mapping.get(project_stage.lower(), 0)
        entrepreneur_level = stage_mapping.get(entrepreneur_stage.lower(), 0)
        
        return abs(project_level - entrepreneur_level) <= 1
    
    @staticmethod
    def _generate_mentorship_reasoning(user_entity, mentor_entity) -> str:
        """Genera una explicación de por qué se recomienda la mentoría"""
        reasons = []
        
        # Experiencia
        experience_diff = getattr(mentor_entity, 'years_experience', 0) - getattr(user_entity, 'years_experience', 0)
        if experience_diff > 5:
            reasons.append(f"Mentor con {experience_diff} años más de experiencia")
        
        # Industria
        if RelationshipRecommendationEngine._check_industry_match(user_entity, mentor_entity):
            industry = getattr(mentor_entity, 'industry', 'tu industria')
            reasons.append(f"Experiencia en {industry}")
        
        # Intereses comunes
        common_interests = RelationshipRecommendationEngine._find_common_interests(user_entity, mentor_entity)
        if common_interests:
            reasons.append(f"Intereses comunes: {', '.join(common_interests[:3])}")
        
        return "; ".join(reasons) if reasons else "Perfil complementario para tu desarrollo"
    
    @staticmethod
    def _generate_collaboration_reasoning(project, entrepreneur) -> str:
        """Genera una explicación de por qué se recomienda la colaboración"""
        reasons = []
        
        # Habilidades complementarias
        skill_complement = RelationshipRecommendationEngine._calculate_skill_complementarity(project, entrepreneur)
        if skill_complement > 3:
            reasons.append("Habilidades complementarias ideales")
        
        # Etapa compatible
        if RelationshipRecommendationEngine._check_stage_compatibility(project, entrepreneur):
            reasons.append("Etapa de desarrollo compatible")
        
        # Industria
        if getattr(project, 'industry', '') == getattr(entrepreneur, 'industry', ''):
            reasons.append("Misma industria de especialización")
        
        return "; ".join(reasons) if reasons else "Potencial sinergia para colaboración"


# Funciones auxiliares para facilitar el uso del sistema
def create_mentorship_relationship(
    mentor_id: int,
    mentee_id: int,
    program_id: Optional[int] = None,
    initiated_by: Optional[int] = None,
    auto_approve: bool = False
) -> Relationship:
    """Función auxiliar para crear relación de mentoría"""
    return RelationshipManager.create_relationship(
        relationship_type=RelationshipType.MENTORSHIP,
        source_type='user',
        source_id=mentor_id,
        target_type='user',
        target_id=mentee_id,
        context_type='program' if program_id else None,
        context_id=program_id,
        initiated_by=initiated_by,
        auto_approve=auto_approve,
        direction=RelationshipDirection.BIDIRECTIONAL
    )


def create_collaboration_relationship(
    project_id: int,
    collaborator_id: int,
    initiated_by: Optional[int] = None,
    role: Optional[str] = None
) -> Relationship:
    """Función auxiliar para crear relación de colaboración"""
    metadata = {'role': role} if role else {}
    
    return RelationshipManager.create_relationship(
        relationship_type=RelationshipType.COLLABORATION,
        source_type='project',
        source_id=project_id,
        target_type='user',
        target_id=collaborator_id,
        initiated_by=initiated_by,
        metadata=metadata,
        direction=RelationshipDirection.BIDIRECTIONAL
    )


def get_user_network(
    user_id: int,
    relationship_types: Optional[list[RelationshipType]] = None,
    max_depth: int = 2
) -> dict[str, Any]:
    """
    Obtiene la red de relaciones de un usuario
    
    Args:
        user_id: ID del usuario
        relationship_types: Tipos de relación a incluir
        max_depth: Profundidad máxima de la red
        
    Returns:
        Diccionario con la red de relaciones
    """
    network = {
        'nodes': [],
        'edges': [],
        'user_id': user_id,
        'max_depth': max_depth
    }
    
    visited = set()
    queue = [(user_id, 'user', 0)]  # (id, type, depth)
    
    while queue:
        current_id, current_type, depth = queue.pop(0)
        
        if (current_id, current_type) in visited or depth > max_depth:
            continue
        
        visited.add((current_id, current_type))
        
        # Agregar nodo
        network['nodes'].append({
            'id': f"{current_type}_{current_id}",
            'type': current_type,
            'entity_id': current_id,
            'depth': depth
        })
        
        # Obtener relaciones
        relationships = RelationshipManager.get_relationships_for_entity(
            current_type, current_id, relationship_types,
            RelationshipStatus.ACTIVE
        )
        
        for rel in relationships:
            # Determinar el otro extremo de la relación
            if rel.source_type == current_type and rel.source_id == current_id:
                other_type, other_id = rel.target_type, rel.target_id
            else:
                other_type, other_id = rel.source_type, rel.source_id
            
            # Agregar arista
            network['edges'].append({
                'source': f"{current_type}_{current_id}",
                'target': f"{other_type}_{other_id}",
                'relationship_type': rel.relationship_type.value,
                'strength': rel.strength,
                'relationship_id': rel.id
            })
            
            # Agregar a la cola para explorar
            if depth < max_depth:
                queue.append((other_id, other_type, depth + 1))
    
    return network


# Event listeners para mantenimiento automático
@event.listens_for(Relationship, 'after_update')
def update_relationship_history(mapper, connection, target):
    """Registra cambios automáticamente en el historial"""
    # Esta función se ejecutaría después de actualizaciones
    # La lógica específica dependería de cómo quieras trackear cambios
    pass


@event.listens_for(Relationship, 'after_insert')
def notify_relationship_creation(mapper, connection, target):
    """Notifica cuando se crea una nueva relación"""
    # Aquí podrías enviar notificaciones, actualizar métricas, etc.
    pass