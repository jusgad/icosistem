"""
Availability Models Module

Este módulo define los modelos relacionados con la disponibilidad de mentores y aliados.
Gestiona horarios, slots de tiempo disponibles y configuraciones de calendario.

Author: Generated stub for import compatibility
Date: 2025
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Any, Optional
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Time
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from app.extensions import db
from app.models.base import BaseModel, AuditMixin, GUID, JSONType

logger = logging.getLogger(__name__)


class Availability(BaseModel, AuditMixin, db.Model):
    """
    Modelo de disponibilidad para aliados/mentores.
    Gestiona los horarios y slots disponibles para sesiones de mentoría.
    """
    
    __tablename__ = 'availability'
    __searchable__ = ['day_of_week', 'ally_id']
    
    # Clave primaria
    id = Column(GUID(), primary_key=True, default=lambda: str(db.uuid.uuid4()))
    
    # Relación con el aliado/mentor
    ally_id = Column(GUID(), ForeignKey('allies.id'), nullable=False,
                     doc="ID del aliado al que pertenece esta disponibilidad")
    
    # Configuración de día y horario
    day_of_week = Column(Integer, nullable=False,
                        doc="Día de la semana (0=Lunes, 6=Domingo)")
    
    start_time = Column(Time, nullable=False,
                       doc="Hora de inicio del slot disponible")
    
    end_time = Column(Time, nullable=False,
                     doc="Hora final del slot disponible")
    
    # Estado y configuración
    is_active = Column(Boolean, default=True, nullable=False,
                      doc="Si este slot está activo")
    
    is_recurring = Column(Boolean, default=True, nullable=False,
                         doc="Si es un slot recurrente semanal")
    
    timezone = Column(String(50), default='America/Bogota',
                     doc="Zona horaria para este slot")
    
    # Configuración de sesiones
    max_sessions = Column(Integer, default=1,
                         doc="Máximo número de sesiones en este slot")
    
    session_duration_minutes = Column(Integer, default=60,
                                    doc="Duración estándar de sesión en minutos")
    
    buffer_minutes = Column(Integer, default=15,
                           doc="Tiempo de buffer entre sesiones")
    
    # Metadata adicional
    notes = Column(Text, nullable=True,
                  doc="Notas adicionales sobre este slot")
    
    preferences = Column(JSONType, default=dict,
                        doc="Preferencias específicas para este horario")
    
    # Relaciones
    ally = relationship("Ally", back_populates="availability_slots",
                       doc="Aliado propietario de esta disponibilidad")
    
    def __init__(self, **kwargs):
        """Inicializa una nueva disponibilidad."""
        super().__init__(**kwargs)
    
    @validates('day_of_week')
    def validate_day_of_week(self, key, value):
        """Valida que el día de la semana esté en rango válido."""
        if not 0 <= value <= 6:
            raise ValueError("day_of_week debe estar entre 0 (Lunes) y 6 (Domingo)")
        return value
    
    @validates('start_time', 'end_time')
    def validate_times(self, key, value):
        """Valida que los horarios sean válidos."""
        if key == 'end_time' and hasattr(self, 'start_time') and self.start_time:
            if value <= self.start_time:
                raise ValueError("end_time debe ser posterior a start_time")
        return value
    
    @hybrid_property
    def duration_minutes(self):
        """Calcula la duración total del slot en minutos."""
        if self.start_time and self.end_time:
            start_minutes = self.start_time.hour * 60 + self.start_time.minute
            end_minutes = self.end_time.hour * 60 + self.end_time.minute
            return end_minutes - start_minutes
        return 0
    
    @hybrid_property
    def day_name(self):
        """Retorna el nombre del día de la semana."""
        days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return days[self.day_of_week] if 0 <= self.day_of_week <= 6 else 'Desconocido'
    
    def is_available_at(self, target_time: time) -> bool:
        """Verifica si el slot está disponible a una hora específica."""
        return self.start_time <= target_time <= self.end_time
    
    def get_time_slots(self, session_duration: int = None) -> List[Dict[str, Any]]:
        """
        Retorna una lista de slots de tiempo disponibles dentro de este horario.
        
        Args:
            session_duration: Duración de sesión en minutos (usa default si no se especifica)
        
        Returns:
            Lista de diccionarios con información de cada slot
        """
        duration = session_duration or self.session_duration_minutes
        slots = []
        
        # Convertir tiempos a minutos desde medianoche
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        
        current_minutes = start_minutes
        slot_number = 1
        
        while current_minutes + duration + self.buffer_minutes <= end_minutes:
            slot_start_hour = current_minutes // 60
            slot_start_minute = current_minutes % 60
            
            slot_end_minutes = current_minutes + duration
            slot_end_hour = slot_end_minutes // 60
            slot_end_minute = slot_end_minutes % 60
            
            slots.append({
                'slot_number': slot_number,
                'start_time': time(slot_start_hour, slot_start_minute),
                'end_time': time(slot_end_hour, slot_end_minute),
                'duration_minutes': duration
            })
            
            current_minutes += duration + self.buffer_minutes
            slot_number += 1
        
        return slots
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a diccionario para serialización."""
        return {
            'id': str(self.id),
            'ally_id': str(self.ally_id),
            'day_of_week': self.day_of_week,
            'day_name': self.day_name,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'is_active': self.is_active,
            'is_recurring': self.is_recurring,
            'timezone': self.timezone,
            'max_sessions': self.max_sessions,
            'session_duration_minutes': self.session_duration_minutes,
            'buffer_minutes': self.buffer_minutes,
            'duration_minutes': self.duration_minutes,
            'notes': self.notes,
            'preferences': self.preferences
        }
    
    def __repr__(self):
        return f'<Availability {self.day_name} {self.start_time}-{self.end_time}>'
    
    def __str__(self):
        return f'{self.day_name} de {self.start_time.strftime("%H:%M")} a {self.end_time.strftime("%H:%M")}'


# Exportar el modelo principal
__all__ = ['Availability']