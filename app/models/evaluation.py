"""
Evaluation Models Module

Este módulo define los modelos relacionados con evaluaciones y feedback.
Gestiona evaluaciones de mentores, emprendedores y sesiones.

Author: Generated stub for import compatibility
Date: 2025
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Float
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from app.extensions import db
from app.models.base import BaseModel, AuditMixin, GUID, JSONType

logger = logging.getLogger(__name__)


class Evaluation(BaseModel, AuditMixin, db.Model):
    """
    Modelo de evaluación para sesiones de mentoría y feedback.
    Permite a emprendedores evaluar a mentores y viceversa.
    """
    
    __tablename__ = 'evaluations'
    __searchable__ = ['title', 'evaluator_type', 'evaluated_type']
    
    # Clave primaria
    id = Column(GUID(), primary_key=True, default=lambda: str(db.uuid.uuid4()))
    
    # Información de la evaluación
    title = Column(String(200), nullable=True, doc="Título de la evaluación")
    description = Column(Text, nullable=True, doc="Descripción de la evaluación")
    
    # Quién evalúa y a quién
    evaluator_id = Column(GUID(), ForeignKey('users.id'), nullable=False,
                         doc="ID del usuario que evalúa")
    
    evaluated_id = Column(GUID(), ForeignKey('users.id'), nullable=False,
                         doc="ID del usuario evaluado")
    
    # Tipos de evaluación
    evaluator_type = Column(String(50), nullable=False,
                          doc="Tipo de evaluador (entrepreneur, ally, admin)")
    
    evaluated_type = Column(String(50), nullable=False,
                          doc="Tipo de evaluado (entrepreneur, ally, admin)")
    
    # Relación con sesión o actividad (opcional)
    session_id = Column(GUID(), nullable=True,
                       doc="ID de la sesión relacionada (si aplica)")
    
    # Puntuaciones (escala 1-5)
    overall_rating = Column(Float, nullable=False, default=0.0,
                          doc="Puntuación general (1-5)")
    
    communication_rating = Column(Float, nullable=True, default=0.0,
                                doc="Calificación de comunicación")
    
    expertise_rating = Column(Float, nullable=True, default=0.0,
                            doc="Calificación de expertise/conocimiento")
    
    helpfulness_rating = Column(Float, nullable=True, default=0.0,
                              doc="Calificación de utilidad")
    
    punctuality_rating = Column(Float, nullable=True, default=0.0,
                              doc="Calificación de puntualidad")
    
    # Comentarios y feedback
    positive_feedback = Column(Text, nullable=True,
                             doc="Comentarios positivos")
    
    improvement_suggestions = Column(Text, nullable=True,
                                   doc="Sugerencias de mejora")
    
    additional_comments = Column(Text, nullable=True,
                               doc="Comentarios adicionales")
    
    # Estado y metadata
    is_public = Column(Boolean, default=False, nullable=False,
                      doc="Si la evaluación es pública")
    
    is_anonymous = Column(Boolean, default=False, nullable=False,
                         doc="Si la evaluación es anónima")
    
    status = Column(String(20), default='active', nullable=False,
                   doc="Estado de la evaluación")
    
    evaluation_date = Column(DateTime, default=datetime.utcnow,
                           doc="Fecha de la evaluación")
    
    # Datos adicionales en JSON
    metadata_fields = Column(JSONType, default=dict,
                           doc="Campos adicionales de metadata")
    
    # Relaciones
    evaluator = relationship("User", foreign_keys=[evaluator_id],
                           backref="evaluations_given")
    
    evaluated = relationship("User", foreign_keys=[evaluated_id],
                           backref="evaluations_received")
    
    def __init__(self, **kwargs):
        """Inicializa una nueva evaluación."""
        super().__init__(**kwargs)
    
    @validates('overall_rating', 'communication_rating', 'expertise_rating', 
               'helpfulness_rating', 'punctuality_rating')
    def validate_rating(self, key, value):
        """Valida que las calificaciones estén en el rango 1-5."""
        if value is not None and not (1.0 <= value <= 5.0):
            raise ValueError(f"{key} debe estar entre 1.0 y 5.0")
        return value
    
    @hybrid_property
    def average_rating(self):
        """Calcula el promedio de todas las calificaciones disponibles."""
        ratings = [
            self.communication_rating,
            self.expertise_rating, 
            self.helpfulness_rating,
            self.punctuality_rating
        ]
        valid_ratings = [r for r in ratings if r is not None and r > 0]
        
        if not valid_ratings:
            return self.overall_rating or 0.0
        
        return sum(valid_ratings) / len(valid_ratings)
    
    @hybrid_property
    def evaluator_name(self):
        """Retorna el nombre del evaluador (o 'Anónimo' si es anónima)."""
        if self.is_anonymous:
            return 'Anónimo'
        return self.evaluator.full_name if self.evaluator else 'Usuario Desconocido'
    
    @hybrid_property
    def evaluated_name(self):
        """Retorna el nombre del evaluado."""
        return self.evaluated.full_name if self.evaluated else 'Usuario Desconocido'
    
    def get_rating_summary(self) -> Dict[str, Any]:
        """Retorna un resumen de las calificaciones."""
        return {
            'overall': self.overall_rating,
            'communication': self.communication_rating,
            'expertise': self.expertise_rating,
            'helpfulness': self.helpfulness_rating,
            'punctuality': self.punctuality_rating,
            'average': self.average_rating
        }
    
    def to_dict(self, include_sensitive=False) -> Dict[str, Any]:
        """Convierte la evaluación a diccionario para serialización."""
        data = {
            'id': str(self.id),
            'title': self.title,
            'description': self.description,
            'evaluator_type': self.evaluator_type,
            'evaluated_type': self.evaluated_type,
            'overall_rating': self.overall_rating,
            'average_rating': self.average_rating,
            'evaluation_date': self.evaluation_date.isoformat() if self.evaluation_date else None,
            'is_public': self.is_public,
            'status': self.status
        }
        
        if include_sensitive or not self.is_anonymous:
            data.update({
                'evaluator_id': str(self.evaluator_id),
                'evaluator_name': self.evaluator_name,
                'positive_feedback': self.positive_feedback,
                'improvement_suggestions': self.improvement_suggestions,
                'additional_comments': self.additional_comments
            })
        
        if include_sensitive:
            data.update({
                'communication_rating': self.communication_rating,
                'expertise_rating': self.expertise_rating,
                'helpfulness_rating': self.helpfulness_rating,
                'punctuality_rating': self.punctuality_rating,
                'metadata_fields': self.metadata_fields
            })
        
        return data
    
    def __repr__(self):
        return f'<Evaluation {self.evaluator_type} -> {self.evaluated_type} ({self.overall_rating}/5)>'
    
    def __str__(self):
        return f'Evaluación de {self.evaluator_name} ({self.overall_rating}/5 estrellas)'


# Exportar el modelo principal
__all__ = ['Evaluation']