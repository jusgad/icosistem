"""
Modelo de aliado/mentor para el ecosistema de emprendimiento.
Este módulo define la clase Ally que extiende User con funcionalidades específicas de mentoría y apoyo.
"""

import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Union
from decimal import Decimal
from flask import current_app
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Numeric, Time, event
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.dialects.postgresql import ARRAY

from app.extensions import db
from app.core.constants import (
    ALLY_ROLE, ENTREPRENEUR_ROLE, MAX_ENTREPRENEURS_PER_ALLY,
    ECONOMIC_SECTORS, MENTORSHIP_CONFIG
)
from app.core.security import log_security_event
from .base import GUID, JSONType
from .user import User
from .mixins import SearchableMixin, CacheableMixin, NotifiableMixin, ValidatableMixin

# Configurar logger
ally_logger = logging.getLogger('ecosistema.models.ally')


# ====================================
# MODELO ALIADO/MENTOR
# ====================================

class Ally(User):
    """
    Modelo de aliado/mentor que extiende User con funcionalidades específicas de mentoría.
    Los aliados pueden mentorear emprendedores, crear programas y proporcionar expertise.
    """
    
    __tablename__ = 'allies'
    __searchable__ = [
        'expertise_description', 'mentorship_approach', 'specializations',
        'professional_background', 'achievements', 'current_role'
    ]
    
    # Herencia de User
    id = Column(GUID(), ForeignKey('users.id'), primary_key=True)
    
    # ====================================
    # INFORMACIÓN PROFESIONAL
    # ====================================
    
    # Experiencia y background
    current_role = Column(String(150), nullable=True,
                         doc="Rol profesional actual")
    
    current_organization = Column(String(150), nullable=True,
                                 doc="Organización actual")
    
    years_professional_experience = Column(Integer, default=0,
                                          doc="Años de experiencia profesional total")
    
    years_entrepreneurship_experience = Column(Integer, default=0,
                                              doc="Años de experiencia en emprendimiento")
    
    years_mentoring_experience = Column(Integer, default=0,
                                       doc="Años de experiencia mentoreando")
    
    professional_background = Column(Text, nullable=True,
                                    doc="Resumen del background profesional")
    
    career_highlights = Column(JSONType, default=list,
                              doc="Puntos destacados de la carrera")
    
    achievements = Column(JSONType, default=list,
                         doc="Logros profesionales principales")
    
    # Credenciales y educación
    education_background = Column(JSONType, default=list,
                                 doc="Background educativo detallado")
    
    certifications = Column(JSONType, default=list,
                           doc="Certificaciones profesionales")
    
    awards_recognition = Column(JSONType, default=list,
                               doc="Premios y reconocimientos")
    
    # ====================================
    # EXPERTISE Y ESPECIALIZACIÓN
    # ====================================
    
    # Áreas de expertise
    primary_expertise = Column(String(100), nullable=True,
                              doc="Área principal de expertise")
    
    secondary_expertise = Column(JSONType, default=list,
                                doc="Áreas secundarias de expertise")
    
    specializations = Column(JSONType, default=list,
                            doc="Especializaciones específicas")
    
    expertise_description = Column(Text, nullable=True,
                                  doc="Descripción detallada del expertise")
    
    # Industrias y sectores
    target_industries = Column(JSONType, default=list,
                              doc="Industrias objetivo para mentoría")
    
    preferred_business_stages = Column(JSONType, default=list,
                                      doc="Etapas de negocio preferidas para mentorear")
    
    # Servicios que ofrece
    services_offered = Column(JSONType, default=list,
                             doc="Servicios específicos que ofrece")
    
    consulting_areas = Column(JSONType, default=list,
                             doc="Áreas de consultoría disponibles")
    
    # ====================================
    # CONFIGURACIÓN DE MENTORÍA
    # ====================================
    
    # Disponibilidad
    available_for_mentorship = Column(Boolean, default=True,
                                     doc="Disponible para mentoría")
    
    max_mentees = Column(Integer, default=MAX_ENTREPRENEURS_PER_ALLY,
                        doc="Máximo número de mentees simultáneos")
    
    current_mentees = Column(Integer, default=0,
                            doc="Número actual de mentees")
    
    # Horarios y disponibilidad
    preferred_meeting_days = Column(JSONType, default=list,
                                   doc="Días preferidos para reuniones")
    
    preferred_meeting_times = Column(JSONType, default=dict,
                                    doc="Horarios preferidos por día")
    
    timezone_for_meetings = Column(String(50), default='America/Bogota',
                                  doc="Zona horaria para programar reuniones")
    
    # Enfoque y metodología
    mentorship_approach = Column(Text, nullable=True,
                                doc="Descripción del enfoque de mentoría")
    
    mentorship_style = Column(String(50), default='collaborative',
                             doc="Estilo de mentoría: directive, collaborative, supportive")
    
    session_duration_preference = Column(Integer, default=60,
                                        doc="Duración preferida de sesiones en minutos")
    
    follow_up_frequency = Column(String(20), default='weekly',
                                doc="Frecuencia preferida de seguimiento")
    
    # ====================================
    # MÉTRICAS Y ESTADÍSTICAS
    # ====================================
    
    # Estadísticas de mentoría
    total_mentees_helped = Column(Integer, default=0,
                                 doc="Total de emprendedores mentoreados")
    
    total_mentorship_hours = Column(Numeric(8, 2), default=0,
                                   doc="Total de horas de mentoría brindadas")
    
    active_mentorship_sessions = Column(Integer, default=0,
                                       doc="Sesiones de mentoría activas")
    
    completed_mentorship_programs = Column(Integer, default=0,
                                          doc="Programas de mentoría completados")
    
    # Ratings y feedback
    average_mentor_rating = Column(Numeric(3, 2), default=0.0,
                                  doc="Calificación promedio como mentor")
    
    total_ratings_received = Column(Integer, default=0,
                                   doc="Total de calificaciones recibidas")
    
    mentee_success_rate = Column(Numeric(5, 2), default=0.0,
                                doc="Tasa de éxito de mentees (porcentaje)")
    
    # Engagement y contribución
    programs_created = Column(Integer, default=0,
                             doc="Programas creados por el aliado")
    
    workshops_conducted = Column(Integer, default=0,
                                doc="Talleres conducidos")
    
    speaking_engagements = Column(Integer, default=0,
                                 doc="Participaciones como speaker")
    
    content_contributions = Column(Integer, default=0,
                                  doc="Contribuciones de contenido")
    
    # ====================================
    # CONFIGURACIONES DE SERVICIO
    # ====================================
    
    # Modalidades de trabajo
    offers_pro_bono = Column(Boolean, default=True,
                            doc="Ofrece servicios pro bono")
    
    offers_paid_consulting = Column(Boolean, default=False,
                                   doc="Ofrece consultoría pagada")
    
    hourly_rate = Column(Numeric(8, 2), nullable=True,
                        doc="Tarifa por hora para consultoría pagada")
    
    # Tipos de interacción
    offers_one_on_one = Column(Boolean, default=True,
                              doc="Ofrece mentoría uno a uno")
    
    offers_group_mentoring = Column(Boolean, default=True,
                                   doc="Ofrece mentoría grupal")
    
    offers_workshops = Column(Boolean, default=False,
                             doc="Ofrece talleres")
    
    offers_speaking = Column(Boolean, default=False,
                            doc="Disponible para speaking")
    
    # Comunicación
    preferred_communication_methods = Column(JSONType, default=list,
                                            doc="Métodos de comunicación preferidos")
    
    response_time_commitment = Column(String(50), default='24_hours',
                                     doc="Compromiso de tiempo de respuesta")
    
    # ====================================
    # INFORMACIÓN ADICIONAL
    # ====================================
    
    # Motivación y filosofía
    mentorship_motivation = Column(Text, nullable=True,
                                  doc="Motivación para ser mentor")
    
    success_philosophy = Column(Text, nullable=True,
                               doc="Filosofía sobre el éxito empresarial")
    
    advice_for_entrepreneurs = Column(Text, nullable=True,
                                     doc="Consejos principales para emprendedores")
    
    # Red profesional
    professional_network_size = Column(Integer, default=0,
                                      doc="Tamaño estimado de red profesional")
    
    can_provide_introductions = Column(Boolean, default=True,
                                      doc="Puede proporcionar presentaciones")
    
    investor_connections = Column(Boolean, default=False,
                                 doc="Tiene conexiones con inversionistas")
    
    corporate_connections = Column(Boolean, default=False,
                                  doc="Tiene conexiones corporativas")
    
    # Fechas importantes
    started_mentoring_at = Column(DateTime(timezone=True), nullable=True,
                                 doc="Fecha en que empezó a mentorear")
    
    joined_as_ally_at = Column(DateTime(timezone=True), default=datetime.utcnow,
                              doc="Fecha de ingreso como aliado al ecosistema")
    
    last_mentorship_activity = Column(DateTime(timezone=True), nullable=True,
                                     doc="Fecha de última actividad de mentoría")
    
    # ====================================
    # RELACIONES
    # ====================================
    
    # Mentorías que proporciona
    mentorships_provided = relationship("Mentorship", backref="ally", lazy='dynamic',
                                       foreign_keys="Mentorship.ally_id")
    
    # Programas creados
    programs_created_rel = relationship("Program", backref="creator", lazy='dynamic',
                                       foreign_keys="Program.creator_id")
    
    # Configurar relación con User
    __mapper_args__ = {
        'polymorphic_identity': ALLY_ROLE,
        'inherit_condition': id == User.id
    }
    
    # ====================================
    # CONFIGURACIÓN DE NOTIFICACIONES
    # ====================================
    
    _notification_events = {
        'ally_created': {'template': 'ally_welcome', 'enabled': True},
        'mentorship_request': {'template': 'new_mentorship_request', 'enabled': True},
        'mentee_assigned': {'template': 'mentee_assigned', 'enabled': True},
        'session_scheduled': {'template': 'mentorship_session_scheduled', 'enabled': True},
        'mentee_milestone': {'template': 'mentee_achievement', 'enabled': True},
        'rating_received': {'template': 'mentor_rating_received', 'enabled': True},
        'program_enrollment': {'template': 'program_new_enrollment', 'enabled': True}
    }
    
    # ====================================
    # PROPIEDADES CALCULADAS
    # ====================================
    
    @hybrid_property
    def is_available_for_new_mentees(self):
        """Verificar si está disponible para nuevos mentees."""
        return (self.available_for_mentorship and 
                self.current_mentees < self.max_mentees and
                self.is_active)
    
    @property
    def mentorship_capacity_percentage(self):
        """Porcentaje de capacidad de mentoría utilizada."""
        if self.max_mentees == 0:
            return 100.0
        return (self.current_mentees / self.max_mentees) * 100
    
    @property
    def years_in_ecosystem(self):
        """Años como aliado en el ecosistema."""
        if self.joined_as_ally_at:
            delta = datetime.utcnow() - self.joined_as_ally_at
            return round(delta.days / 365.25, 1)
        return 0
    
    @property
    def mentorship_experience_level(self):
        """Nivel de experiencia en mentoría."""
        if self.years_mentoring_experience >= 5 and self.total_mentees_helped >= 20:
            return 'expert'
        elif self.years_mentoring_experience >= 3 and self.total_mentees_helped >= 10:
            return 'experienced'
        elif self.years_mentoring_experience >= 1 and self.total_mentees_helped >= 3:
            return 'intermediate'
        else:
            return 'beginner'
    
    @property
    def expertise_score(self):
        """Score de expertise basado en experiencia y logros."""
        score = 0
        
        # Experiencia profesional (máx 30 puntos)
        score += min(self.years_professional_experience * 2, 30)
        
        # Experiencia en emprendimiento (máx 25 puntos)
        score += min(self.years_entrepreneurship_experience * 3, 25)
        
        # Experiencia mentoreando (máx 20 puntos)
        score += min(self.years_mentoring_experience * 4, 20)
        
        # Logros y reconocimientos (máx 15 puntos)
        achievements_count = len(self.achievements or [])
        score += min(achievements_count * 3, 15)
        
        # Rating como mentor (máx 10 puntos)
        if self.average_mentor_rating:
            score += (float(self.average_mentor_rating) / 5.0) * 10
        
        return min(score, 100)
    
    @property
    def impact_score(self):
        """Score de impacto basado en métricas de mentoría."""
        score = 0
        
        # Mentees ayudados (máx 40 puntos)
        score += min(self.total_mentees_helped * 2, 40)
        
        # Horas de mentoría (máx 30 puntos)
        if self.total_mentorship_hours:
            score += min(float(self.total_mentorship_hours) / 10, 30)
        
        # Tasa de éxito de mentees (máx 20 puntos)
        if self.mentee_success_rate:
            score += (float(self.mentee_success_rate) / 100) * 20
        
        # Contribuciones adicionales (máx 10 puntos)
        contributions = (self.programs_created + self.workshops_conducted + 
                        self.speaking_engagements + self.content_contributions)
        score += min(contributions, 10)
        
        return min(score, 100)
    
    @property
    def overall_mentor_score(self):
        """Score general como mentor."""
        return (self.expertise_score * 0.4 + 
                self.impact_score * 0.4 +
                (float(self.average_mentor_rating or 0) / 5.0) * 100 * 0.2)
    
    @property
    def specializations_display(self):
        """Lista legible de especializaciones."""
        if not self.specializations:
            return []
        return [spec.replace('_', ' ').title() for spec in self.specializations]
    
    @property
    def is_premium_mentor(self):
        """Verificar si es mentor premium basado en métricas."""
        return (self.overall_mentor_score >= 80 and 
                self.total_mentees_helped >= 10 and
                float(self.average_mentor_rating or 0) >= 4.5)
    
    @property
    def next_available_slot(self):
        """Próximo slot disponible para mentoría."""
        # Implementar lógica para calcular próximo slot disponible
        # basado en horarios preferidos y reuniones existentes
        return None  # Placeholder
    
    # ====================================
    # MÉTODOS DE GESTIÓN DE MENTORÍA
    # ====================================
    
    def accept_mentee(self, entrepreneur_id: str, 
                     mentorship_areas: List[str] = None) -> 'Mentorship':
        """
        Aceptar un emprendedor como mentee.
        
        Args:
            entrepreneur_id: ID del emprendedor
            mentorship_areas: Áreas específicas de mentoría
            
        Returns:
            Nueva instancia de Mentorship
        """
        if not self.is_available_for_new_mentees:
            raise ValueError("No hay capacidad disponible para nuevos mentees")
        
        try:
            from .mentorship import Mentorship
            from .entrepreneur import Entrepreneur
            
            entrepreneur = Entrepreneur.get_by_id(entrepreneur_id)
            if not entrepreneur:
                raise ValueError("Emprendedor no encontrado")
            
            # Verificar que no existe mentoría activa
            existing = Mentorship.query.filter_by(
                ally_id=self.id,
                entrepreneur_id=entrepreneur_id,
                status='active'
            ).first()
            
            if existing:
                raise ValueError("Ya existe una mentoría activa con este emprendedor")
            
            # Crear nueva mentoría
            mentorship = Mentorship(
                ally_id=self.id,
                entrepreneur_id=entrepreneur_id,
                focus_areas=mentorship_areas or [],
                status='active',
                start_date=datetime.utcnow()
            )
            
            mentorship.save()
            
            # Actualizar contadores
            self.current_mentees += 1
            self.total_mentees_helped += 1
            db.session.commit()
            
            # Enviar notificaciones
            self.send_notification('mentee_assigned', context={
                'mentee_name': entrepreneur.full_name,
                'mentee_id': str(entrepreneur.id),
                'focus_areas': mentorship_areas or []
            })
            
            entrepreneur.send_notification('mentorship_assigned', context={
                'mentor_name': self.full_name,
                'mentor_id': str(self.id),
                'focus_areas': mentorship_areas or []
            })
            
            ally_logger.info(f"Mentorship accepted: {self.email} -> {entrepreneur.email}")
            return mentorship
            
        except Exception as e:
            db.session.rollback()
            ally_logger.error(f"Error accepting mentee: {str(e)}")
            raise
    
    def complete_mentorship(self, mentorship_id: str, 
                           success_rating: int = None,
                           completion_notes: str = None) -> bool:
        """
        Completar una mentoría.
        
        Args:
            mentorship_id: ID de la mentoría
            success_rating: Rating de éxito (1-5)
            completion_notes: Notas de finalización
            
        Returns:
            True si se completó exitosamente
        """
        try:
            from .mentorship import Mentorship
            
            mentorship = Mentorship.get_by_id(mentorship_id)
            if not mentorship or mentorship.ally_id != self.id:
                raise ValueError("Mentoría no encontrada o no autorizada")
            
            # Completar mentoría
            mentorship.status = 'completed'
            mentorship.end_date = datetime.utcnow()
            mentorship.completion_notes = completion_notes
            
            if success_rating:
                mentorship.ally_success_rating = success_rating
            
            # Actualizar métricas del aliado
            self.current_mentees = max(0, self.current_mentees - 1)
            self.completed_mentorship_programs += 1
            self.last_mentorship_activity = datetime.utcnow()
            
            # Calcular horas totales si hay sesiones
            total_hours = sum(session.duration_minutes or 60 
                            for session in mentorship.sessions) / 60
            self.total_mentorship_hours += Decimal(str(total_hours))
            
            db.session.commit()
            
            ally_logger.info(f"Mentorship completed: {mentorship_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            ally_logger.error(f"Error completing mentorship: {str(e)}")
            return False
    
    def get_current_mentees(self):
        """Obtener mentees actuales."""
        try:
            from .mentorship import Mentorship
            
            active_mentorships = self.mentorships_provided.filter_by(status='active').all()
            
            mentees = []
            for mentorship in active_mentorships:
                if mentorship.entrepreneur:
                    mentees.append({
                        'mentorship_id': str(mentorship.id),
                        'entrepreneur': mentorship.entrepreneur.to_dict(public_view=True),
                        'start_date': mentorship.start_date.isoformat(),
                        'focus_areas': mentorship.focus_areas or [],
                        'sessions_completed': len(mentorship.sessions),
                        'next_session': self._get_next_session_date(mentorship)
                    })
            
            return mentees
            
        except Exception as e:
            ally_logger.error(f"Error getting current mentees: {str(e)}")
            return []
    
    def _get_next_session_date(self, mentorship) -> Optional[str]:
        """Obtener fecha de próxima sesión."""
        # Implementar lógica para obtener próxima sesión programada
        try:
            from .meeting import Meeting
            
            next_meeting = Meeting.query.filter_by(
                mentorship_id=mentorship.id,
                status='scheduled'
            ).order_by(Meeting.start_time.asc()).first()
            
            return next_meeting.start_time.isoformat() if next_meeting else None
            
        except Exception:
            return None
    
    def get_mentorship_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas detalladas de mentoría."""
        try:
            stats = {
                'overview': {
                    'total_mentees_helped': self.total_mentees_helped,
                    'current_mentees': self.current_mentees,
                    'total_hours': float(self.total_mentorship_hours or 0),
                    'average_rating': float(self.average_mentor_rating or 0),
                    'success_rate': float(self.mentee_success_rate or 0),
                    'years_mentoring': self.years_mentoring_experience,
                    'experience_level': self.mentorship_experience_level
                },
                'capacity': {
                    'max_mentees': self.max_mentees,
                    'capacity_used': self.mentorship_capacity_percentage,
                    'available_slots': max(0, self.max_mentees - self.current_mentees),
                    'is_available': self.is_available_for_new_mentees
                },
                'performance': {
                    'expertise_score': self.expertise_score,
                    'impact_score': self.impact_score,
                    'overall_score': self.overall_mentor_score,
                    'is_premium': self.is_premium_mentor
                },
                'contributions': {
                    'programs_created': self.programs_created,
                    'workshops_conducted': self.workshops_conducted,
                    'speaking_engagements': self.speaking_engagements,
                    'content_contributions': self.content_contributions
                }
            }
            
            return stats
            
        except Exception as e:
            ally_logger.error(f"Error getting mentorship statistics: {str(e)}")
            return {'error': str(e)}
    
    # ====================================
    # MÉTODOS DE HORARIOS Y DISPONIBILIDAD
    # ====================================
    
    def set_availability_schedule(self, schedule: Dict[str, Any]):
        """
        Establecer horarios de disponibilidad.
        
        Args:
            schedule: Diccionario con horarios por día
        """
        try:
            # Formato esperado:
            # {
            #     'monday': {'start': '09:00', 'end': '17:00', 'available': True},
            #     'tuesday': {'start': '10:00', 'end': '16:00', 'available': True},
            #     ...
            # }
            
            self.preferred_meeting_times = schedule
            
            # Extraer días disponibles
            available_days = [day for day, config in schedule.items() 
                            if config.get('available', False)]
            self.preferred_meeting_days = available_days
            
            db.session.commit()
            ally_logger.info(f"Availability schedule updated for {self.email}")
            
        except Exception as e:
            ally_logger.error(f"Error setting availability schedule: {str(e)}")
            raise
    
    def is_available_at_time(self, datetime_slot: datetime) -> bool:
        """
        Verificar si está disponible en un horario específico.
        
        Args:
            datetime_slot: Fecha y hora a verificar
            
        Returns:
            True si está disponible
        """
        try:
            # Obtener día de la semana
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 
                        'friday', 'saturday', 'sunday']
            day_name = day_names[datetime_slot.weekday()]
            
            # Verificar si el día está disponible
            if day_name not in (self.preferred_meeting_days or []):
                return False
            
            # Verificar horario específico
            day_schedule = (self.preferred_meeting_times or {}).get(day_name, {})
            if not day_schedule.get('available', False):
                return False
            
            # Verificar rango horario
            start_time = day_schedule.get('start')
            end_time = day_schedule.get('end')
            
            if start_time and end_time:
                slot_time = datetime_slot.time()
                start = time.fromisoformat(start_time)
                end = time.fromisoformat(end_time)
                
                return start <= slot_time <= end
            
            return True
            
        except Exception as e:
            ally_logger.error(f"Error checking availability: {str(e)}")
            return False
    
    def get_available_slots(self, start_date: datetime, end_date: datetime,
                           duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Obtener slots disponibles en un rango de fechas.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            duration_minutes: Duración de cada slot
            
        Returns:
            Lista de slots disponibles
        """
        try:
            slots = []
            current_date = start_date.date()
            
            while current_date <= end_date.date():
                day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 
                            'friday', 'saturday', 'sunday']
                day_name = day_names[current_date.weekday()]
                
                # Verificar si el día está disponible
                if day_name in (self.preferred_meeting_days or []):
                    day_schedule = (self.preferred_meeting_times or {}).get(day_name, {})
                    
                    if day_schedule.get('available', False):
                        start_time_str = day_schedule.get('start', '09:00')
                        end_time_str = day_schedule.get('end', '17:00')
                        
                        # Generar slots para el día
                        day_slots = self._generate_day_slots(
                            current_date, start_time_str, end_time_str, duration_minutes
                        )
                        slots.extend(day_slots)
                
                current_date += timedelta(days=1)
            
            return slots
            
        except Exception as e:
            ally_logger.error(f"Error getting available slots: {str(e)}")
            return []
    
    def _generate_day_slots(self, date: datetime.date, start_time: str, 
                           end_time: str, duration_minutes: int) -> List[Dict[str, Any]]:
        """Generar slots para un día específico."""
        slots = []
        
        try:
            start = datetime.combine(date, time.fromisoformat(start_time))
            end = datetime.combine(date, time.fromisoformat(end_time))
            duration = timedelta(minutes=duration_minutes)
            
            current_slot = start
            while current_slot + duration <= end:
                # Verificar si el slot está ocupado (implementar verificación con reuniones)
                if not self._is_slot_occupied(current_slot):
                    slots.append({
                        'start_time': current_slot.isoformat(),
                        'end_time': (current_slot + duration).isoformat(),
                        'duration_minutes': duration_minutes,
                        'available': True
                    })
                
                current_slot += timedelta(minutes=30)  # Slots cada 30 minutos
            
        except Exception as e:
            ally_logger.error(f"Error generating day slots: {str(e)}")
        
        return slots
    
    def _is_slot_occupied(self, datetime_slot: datetime) -> bool:
        """Verificar si un slot está ocupado."""
        try:
            from .meeting import Meeting
            
            # Verificar reuniones existentes
            existing_meeting = Meeting.query.filter(
                Meeting.organizer_id == self.id,
                Meeting.start_time <= datetime_slot,
                Meeting.end_time > datetime_slot,
                Meeting.status.in_(['scheduled', 'in_progress'])
            ).first()
            
            return existing_meeting is not None
            
        except Exception:
            return False
    
    # ====================================
    # MÉTODOS DE PROGRAMAS Y CONTENIDO
    # ====================================
    
    def create_program(self, program_data: Dict[str, Any]) -> 'Program':
        """
        Crear nuevo programa de mentoría/capacitación.
        
        Args:
            program_data: Datos del programa
            
        Returns:
            Nueva instancia de Program
        """
        try:
            from .program import Program
            
            # Añadir creator_id automáticamente
            program_data['creator_id'] = self.id
            
            # Crear programa
            program = Program(**program_data)
            program.save()
            
            # Actualizar contador
            self.programs_created += 1
            db.session.commit()
            
            # Enviar notificación
            self.send_notification('program_created', context={
                'program_name': program.name,
                'program_id': str(program.id)
            })
            
            ally_logger.info(f"Program created by ally {self.email}: {program.name}")
            return program
            
        except Exception as e:
            ally_logger.error(f"Error creating program: {str(e)}")
            raise
    
    def get_created_programs(self):
        """Obtener programas creados por el aliado."""
        return self.programs_created_rel.all()
    
    def schedule_workshop(self, workshop_data: Dict[str, Any]) -> bool:
        """
        Programar un taller.
        
        Args:
            workshop_data: Datos del taller
            
        Returns:
            True si se programó exitosamente
        """
        try:
            # Implementar lógica de programación de taller
            # Esto podría crear un Meeting de tipo workshop
            from .meeting import Meeting
            
            workshop_meeting = Meeting(
                title=workshop_data.get('title'),
                description=workshop_data.get('description'),
                meeting_type='workshop',
                organizer_id=self.id,
                start_time=workshop_data.get('start_time'),
                end_time=workshop_data.get('end_time'),
                max_participants=workshop_data.get('max_participants', 20),
                is_public=workshop_data.get('is_public', True)
            )
            
            workshop_meeting.save()
            
            # Actualizar contador
            self.workshops_conducted += 1
            db.session.commit()
            
            ally_logger.info(f"Workshop scheduled by {self.email}: {workshop_data.get('title')}")
            return True
            
        except Exception as e:
            ally_logger.error(f"Error scheduling workshop: {str(e)}")
            return False
    
    def contribute_content(self, content_type: str, content_data: Dict[str, Any]) -> bool:
        """
        Contribuir contenido al ecosistema.
        
        Args:
            content_type: Tipo de contenido (article, guide, template, etc.)
            content_data: Datos del contenido
            
        Returns:
            True si se contribuyó exitosamente
        """
        try:
            # Implementar lógica de contribución de contenido
            # Esto podría crear un registro en una tabla de contenido
            
            # Por ahora, solo actualizar contador
            self.content_contributions += 1
            
            # Registrar en metadata
            contributions = self.get_metadata('content_contributions', [])
            contributions.append({
                'type': content_type,
                'title': content_data.get('title'),
                'created_at': datetime.utcnow().isoformat(),
                'data': content_data
            })
            self.set_metadata('content_contributions', contributions)
            
            ally_logger.info(f"Content contributed by {self.email}: {content_type}")
            return True
            
        except Exception as e:
            ally_logger.error(f"Error contributing content: {str(e)}")
            return False
    
    # ====================================
    # MÉTODOS DE ANÁLISIS Y REPORTES
    # ====================================
    
    def get_mentor_dashboard_data(self) -> Dict[str, Any]:
        """
        Obtener datos para el dashboard del mentor.
        
        Returns:
            Diccionario con datos del dashboard
        """
        try:
            # Obtener mentees actuales
            current_mentees = self.get_current_mentees()
            
            # Obtener próximas sesiones
            upcoming_sessions = self._get_upcoming_sessions()
            
            # Calcular métricas del período actual
            current_month_stats = self._get_current_month_stats()
            
            dashboard_data = {
                'mentor_info': {
                    'name': self.full_name,
                    'experience_level': self.mentorship_experience_level,
                    'years_mentoring': self.years_mentoring_experience,
                    'overall_score': self.overall_mentor_score,
                    'is_premium': self.is_premium_mentor
                },
                'current_status': {
                    'current_mentees': len(current_mentees),
                    'max_capacity': self.max_mentees,
                    'capacity_percentage': self.mentorship_capacity_percentage,
                    'available_for_new': self.is_available_for_new_mentees
                },
                'statistics': self.get_mentorship_statistics(),
                'mentees': current_mentees[:5],  # Primeros 5 mentees
                'upcoming_sessions': upcoming_sessions[:3],  # Próximas 3 sesiones
                'monthly_stats': current_month_stats,
                'specializations': self.specializations_display,
                'recent_achievements': self._get_recent_achievements()
            }
            
            return dashboard_data
            
        except Exception as e:
            ally_logger.error(f"Error getting mentor dashboard data: {str(e)}")
            return {'error': str(e)}
    
    def _get_upcoming_sessions(self) -> List[Dict[str, Any]]:
        """Obtener próximas sesiones programadas."""
        try:
            from .meeting import Meeting
            
            upcoming = Meeting.query.filter(
                Meeting.organizer_id == self.id,
                Meeting.start_time > datetime.utcnow(),
                Meeting.status == 'scheduled'
            ).order_by(Meeting.start_time.asc()).limit(5).all()
            
            sessions = []
            for meeting in upcoming:
                sessions.append({
                    'id': str(meeting.id),
                    'title': meeting.title,
                    'start_time': meeting.start_time.isoformat(),
                    'duration': meeting.duration_minutes,
                    'mentee_name': meeting.participants[0].full_name if meeting.participants else 'TBD',
                    'type': meeting.meeting_type
                })
            
            return sessions
            
        except Exception as e:
            ally_logger.error(f"Error getting upcoming sessions: {str(e)}")
            return []
    
    def _get_current_month_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del mes actual."""
        try:
            from .meeting import Meeting
            from .activity_log import ActivityLog
            
            # Primer día del mes actual
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Sesiones completadas este mes
            sessions_this_month = Meeting.query.filter(
                Meeting.organizer_id == self.id,
                Meeting.start_time >= month_start,
                Meeting.status == 'completed'
            ).count()
            
            # Horas de mentoría este mes
            meetings = Meeting.query.filter(
                Meeting.organizer_id == self.id,
                Meeting.start_time >= month_start,
                Meeting.status == 'completed'
            ).all()
            
            hours_this_month = sum(meeting.duration_minutes or 60 for meeting in meetings) / 60
            
            # Nuevos mentees este mes
            new_mentees = self.mentorships_provided.filter(
                db.text("start_date >= :month_start")
            ).params(month_start=month_start).count()
            
            return {
                'sessions_completed': sessions_this_month,
                'hours_provided': round(hours_this_month, 1),
                'new_mentees': new_mentees,
                'month_name': now.strftime('%B %Y')
            }
            
        except Exception as e:
            ally_logger.error(f"Error getting current month stats: {str(e)}")
            return {}
    
    def _get_recent_achievements(self) -> List[Dict[str, Any]]:
        """Obtener logros recientes."""
        try:
            achievements = []
            
            # Milestone de mentees ayudados
            if self.total_mentees_helped > 0:
                milestones = [5, 10, 25, 50, 100]
                for milestone in milestones:
                    if self.total_mentees_helped >= milestone:
                        achievements.append({
                            'type': 'mentees_milestone',
                            'title': f'{milestone} Emprendedores Mentoreados',
                            'description': f'Has ayudado a {self.total_mentees_helped} emprendedores',
                            'icon': 'fas fa-users'
                        })
            
            # Milestone de horas
            if self.total_mentorship_hours:
                hours = float(self.total_mentorship_hours)
                hour_milestones = [10, 50, 100, 500, 1000]
                for milestone in hour_milestones:
                    if hours >= milestone:
                        achievements.append({
                            'type': 'hours_milestone',
                            'title': f'{milestone} Horas de Mentoría',
                            'description': f'Has brindado {hours:.1f} horas de mentoría',
                            'icon': 'fas fa-clock'
                        })
            
            # Rating alto
            if self.average_mentor_rating and float(self.average_mentor_rating) >= 4.5:
                achievements.append({
                    'type': 'high_rating',
                    'title': 'Mentor Excepcional',
                    'description': f'Rating promedio: {self.average_mentor_rating:.1f}/5.0',
                    'icon': 'fas fa-star'
                })
            
            # Mentor premium
            if self.is_premium_mentor:
                achievements.append({
                    'type': 'premium_mentor',
                    'title': 'Mentor Premium',
                    'description': 'Reconocido como mentor de alto impacto',
                    'icon': 'fas fa-crown'
                })
            
            return achievements[-3:]  # Últimos 3 logros
            
        except Exception as e:
            ally_logger.error(f"Error getting recent achievements: {str(e)}")
            return []
    
    def generate_mentorship_report(self, period_months: int = 6) -> Dict[str, Any]:
        """
        Generar reporte de mentoría para un período específico.
        
        Args:
            period_months: Meses a incluir en el reporte
            
        Returns:
            Reporte detallado de mentoría
        """
        try:
            from .mentorship import Mentorship
            from .meeting import Meeting
            
            # Calcular fechas
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_months * 30)
            
            # Obtener mentorías del período
            mentorships = self.mentorships_provided.filter(
                db.text("start_date >= :start_date")
            ).params(start_date=start_date).all()
            
            # Obtener sesiones del período
            sessions = Meeting.query.filter(
                Meeting.organizer_id == self.id,
                Meeting.start_time >= start_date,
                Meeting.meeting_type.in_(['mentorship', 'review'])
            ).all()
            
            # Calcular métricas
            total_sessions = len(sessions)
            completed_sessions = len([s for s in sessions if s.status == 'completed'])
            total_hours = sum(s.duration_minutes or 60 for s in sessions) / 60
            
            # Agrupar por mes
            monthly_data = {}
            for session in sessions:
                month_key = session.start_time.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'sessions': 0, 'hours': 0}
                monthly_data[month_key]['sessions'] += 1
                monthly_data[month_key]['hours'] += (session.duration_minutes or 60) / 60
            
            # Analizar outcomes de mentees
            mentee_outcomes = []
            for mentorship in mentorships:
                if mentorship.entrepreneur:
                    entrepreneur = mentorship.entrepreneur
                    outcomes = {
                        'name': entrepreneur.full_name,
                        'mentorship_duration': self._calculate_mentorship_duration(mentorship),
                        'sessions_completed': len([s for s in sessions 
                                                 if hasattr(s, 'mentorship_id') and 
                                                    s.mentorship_id == mentorship.id]),
                        'progress_score': float(entrepreneur.progress_score or 0),
                        'projects_created': entrepreneur.active_projects_count,
                        'rating_given': mentorship.entrepreneur_rating
                    }
                    mentee_outcomes.append(outcomes)
            
            report = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'months': period_months
                },
                'summary': {
                    'total_mentorships': len(mentorships),
                    'active_mentorships': len([m for m in mentorships if m.status == 'active']),
                    'completed_mentorships': len([m for m in mentorships if m.status == 'completed']),
                    'total_sessions': total_sessions,
                    'completed_sessions': completed_sessions,
                    'total_hours': round(total_hours, 1),
                    'average_sessions_per_mentee': round(total_sessions / max(len(mentorships), 1), 1)
                },
                'monthly_breakdown': monthly_data,
                'mentee_outcomes': mentee_outcomes,
                'performance_metrics': {
                    'session_completion_rate': (completed_sessions / max(total_sessions, 1)) * 100,
                    'average_mentee_progress': sum(outcome['progress_score'] 
                                                 for outcome in mentee_outcomes) / max(len(mentee_outcomes), 1),
                    'mentee_satisfaction': sum(outcome['rating_given'] or 0 
                                             for outcome in mentee_outcomes) / max(len(mentee_outcomes), 1)
                }
            }
            
            return report
            
        except Exception as e:
            ally_logger.error(f"Error generating mentorship report: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_mentorship_duration(self, mentorship) -> int:
        """Calcular duración de mentoría en días."""
        if mentorship.end_date:
            return (mentorship.end_date - mentorship.start_date).days
        else:
            return (datetime.utcnow() - mentorship.start_date).days
    
    # ====================================
    # MÉTODOS DE MATCHING Y RECOMENDACIONES
    # ====================================
    
    def get_recommended_mentees(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Obtener emprendedores recomendados para mentorear.
        
        Args:
            limit: Número máximo de recomendaciones
            
        Returns:
            Lista de emprendedores recomendados
        """
        try:
            from .entrepreneur import Entrepreneur
            
            # Solo si tiene capacidad disponible
            if not self.is_available_for_new_mentees:
                return []
            
            # Obtener emprendedores buscando mentoría
            seeking_mentorship = Entrepreneur.query.filter_by(
                seeking_mentorship=True,
                available_for_mentorship=True,
                is_active=True
            ).all()
            
            recommendations = []
            
            for entrepreneur in seeking_mentorship:
                # Calcular score de compatibilidad
                compatibility_score = self._calculate_mentee_compatibility(entrepreneur)
                
                if compatibility_score > 0.3:  # Threshold mínimo
                    recommendations.append({
                        'entrepreneur': entrepreneur.to_dict(public_view=True),
                        'compatibility_score': compatibility_score,
                        'matching_reasons': self._get_matching_reasons(entrepreneur),
                        'mentorship_areas': entrepreneur.mentorship_areas or []
                    })
            
            # Ordenar por compatibilidad y limitar
            recommendations.sort(key=lambda x: x['compatibility_score'], reverse=True)
            return recommendations[:limit]
            
        except Exception as e:
            ally_logger.error(f"Error getting recommended mentees: {str(e)}")
            return []
    
    def _calculate_mentee_compatibility(self, entrepreneur) -> float:
        """Calcular compatibilidad con un emprendedor."""
        score = 0.0
        
        # Compatibilidad de sector (peso: 30%)
        if (entrepreneur.primary_sector and 
            entrepreneur.primary_sector == self.primary_expertise):
            score += 0.3
        elif (entrepreneur.primary_sector in (self.secondary_expertise or [])):
            score += 0.2
        
        # Compatibilidad de áreas de mentoría (peso: 40%)
        entrepreneur_areas = set(entrepreneur.mentorship_areas or [])
        ally_specializations = set(self.specializations or [])
        
        if entrepreneur_areas and ally_specializations:
            overlap = len(entrepreneur_areas.intersection(ally_specializations))
            total_areas = len(entrepreneur_areas.union(ally_specializations))
            if total_areas > 0:
                score += (overlap / total_areas) * 0.4
        
        # Compatibilidad de etapa (peso: 20%)
        stage_preferences = self.preferred_business_stages or []
        if entrepreneur.entrepreneurship_stage in stage_preferences:
            score += 0.2
        
        # Motivación y engagement del emprendedor (peso: 10%)
        if entrepreneur.engagement_level == 'high':
            score += 0.1
        elif entrepreneur.engagement_level == 'medium':
            score += 0.05
        
        return min(score, 1.0)
    
    def _get_matching_reasons(self, entrepreneur) -> List[str]:
        """Obtener razones de compatibilidad con un emprendedor."""
        reasons = []
        
        if entrepreneur.primary_sector == self.primary_expertise:
            reasons.append(f"Mismo sector: {entrepreneur.primary_sector_display}")
        
        entrepreneur_areas = set(entrepreneur.mentorship_areas or [])
        ally_specializations = set(self.specializations or [])
        common_areas = entrepreneur_areas.intersection(ally_specializations)
        
        if common_areas:
            reasons.append(f"Áreas en común: {', '.join(common_areas)}")
        
        if entrepreneur.entrepreneurship_stage in (self.preferred_business_stages or []):
            reasons.append(f"Etapa preferida: {entrepreneur.entrepreneurship_stage_display}")
        
        if entrepreneur.engagement_level == 'high':
            reasons.append("Alto nivel de engagement")
        
        return reasons
    
    # ====================================
    # MÉTODOS DE VALIDACIÓN
    # ====================================
    
    @validates('mentorship_style')
    def validate_mentorship_style(self, key, style):
        """Validar estilo de mentoría."""
        valid_styles = ['directive', 'collaborative', 'supportive', 'hands_off']
        if style and style not in valid_styles:
            raise ValueError(f"Estilo inválido. Válidos: {valid_styles}")
        return style
    
    @validates('max_mentees')
    def validate_max_mentees(self, key, max_mentees):
        """Validar máximo de mentees."""
        if max_mentees is not None and max_mentees < 0:
            raise ValueError("El máximo de mentees no puede ser negativo")
        if max_mentees is not None and max_mentees > 20:
            raise ValueError("El máximo de mentees no puede exceder 20")
        return max_mentees
    
    @validates('session_duration_preference')
    def validate_session_duration(self, key, duration):
        """Validar duración de sesión."""
        if duration is not None:
            if duration < 15 or duration > 240:
                raise ValueError("La duración debe estar entre 15 y 240 minutos")
        return duration
    
    @validates('response_time_commitment')
    def validate_response_time(self, key, response_time):
        """Validar tiempo de respuesta."""
        if response_time:
            valid_times = ['1_hour', '4_hours', '24_hours', '48_hours', 'weekly']
            if response_time not in valid_times:
                raise ValueError(f"Tiempo de respuesta inválido. Válidos: {valid_times}")
        return response_time
    
    def _validate_on_init(self):
        """Validaciones al inicializar el modelo."""
        super()._validate_on_init()
        
        # Forzar rol de ally
        self.role = ALLY_ROLE
        
        # Establecer fecha de ingreso como aliado
        if not self.joined_as_ally_at:
            self.joined_as_ally_at = datetime.utcnow()
    
    # ====================================
    # MÉTODOS DE SERIALIZACIÓN
    # ====================================
    
    def to_dict(self, include_sensitive: bool = False, include_relationships: bool = False,
                exclude_fields: List[str] = None, public_view: bool = False) -> Dict[str, Any]:
        """
        Convertir ally a diccionario.
        
        Args:
            include_sensitive: Incluir campos sensibles
            include_relationships: Incluir relaciones
            exclude_fields: Campos a excluir
            public_view: Vista pública (excluye información privada)
            
        Returns:
            Diccionario con datos del aliado
        """
        # Campos privados para vista pública
        private_fields = [
            'hourly_rate', 'total_mentorship_hours', 'current_mentees',
            'response_time_commitment', 'preferred_meeting_times'
        ]
        
        exclude_fields = exclude_fields or []
        if public_view and not include_sensitive:
            exclude_fields.extend(private_fields)
        
        # Obtener diccionario base
        data = super().to_dict(include_sensitive=include_sensitive,
                              include_relationships=include_relationships,
                              exclude_fields=exclude_fields)
        
        # Añadir campos específicos de ally
        ally_data = {
            'mentorship_experience_level': self.mentorship_experience_level,
            'specializations_display': self.specializations_display,
            'is_available_for_new_mentees': self.is_available_for_new_mentees,
            'mentorship_capacity_percentage': self.mentorship_capacity_percentage,
            'years_in_ecosystem': self.years_in_ecosystem,
            'expertise_score': self.expertise_score,
            'impact_score': self.impact_score,
            'overall_mentor_score': self.overall_mentor_score,
            'is_premium_mentor': self.is_premium_mentor
        }
        
        # Añadir campos no privados si es necesario
        if not public_view or include_sensitive:
            ally_data.update({
                'current_mentees_count': self.current_mentees,
                'available_slots': max(0, self.max_mentees - self.current_mentees)
            })
        
        data.update(ally_data)
        return data
    
    def to_mentor_profile(self) -> Dict[str, Any]:
        """Convertir a perfil de mentor para directorio público."""
        return {
            'id': str(self.id),
            'name': self.full_name,
            'current_role': self.current_role,
            'current_organization': self.current_organization,
            'years_experience': self.years_professional_experience,
            'years_mentoring': self.years_mentoring_experience,
            'expertise_level': self.mentorship_experience_level,
            'primary_expertise': self.primary_expertise,
            'specializations': self.specializations_display,
            'mentorship_approach': self.mentorship_approach,
            'mentorship_style': self.mentorship_style,
            'total_mentees_helped': self.total_mentees_helped,
            'average_rating': float(self.average_mentor_rating or 0),
            'is_available': self.is_available_for_new_mentees,
            'offers_pro_bono': self.offers_pro_bono,
            'offers_paid_consulting': self.offers_paid_consulting,
            'offers_workshops': self.offers_workshops,
            'offers_speaking': self.offers_speaking,
            'can_provide_introductions': self.can_provide_introductions,
            'investor_connections': self.investor_connections,
            'corporate_connections': self.corporate_connections,
            'avatar_url': self.avatar_url_or_default,
            'city': self.city,
            'country': self.country,
            'website': self.website,
            'social_links': self.social_links or {},
            'is_premium': self.is_premium_mentor,
            'overall_score': self.overall_mentor_score
        }
    
    # ====================================
    # CONSULTAS ESTÁTICAS
    # ====================================
    
    @classmethod
    def get_available_mentors(cls):
        """Obtener mentores disponibles para nuevos mentees."""
        return cls.query.filter(
            cls.is_available_for_new_mentees == True,
            cls.is_active == True
        ).all()
    
    @classmethod
    def get_by_specialization(cls, specialization: str):
        """Obtener aliados por especialización."""
        return cls.query.filter(
            cls.specializations.contains([specialization]),
            cls.is_active == True
        ).all()
    
    @classmethod
    def get_premium_mentors(cls):
        """Obtener mentores premium."""
        return cls.query.filter(
            cls.average_mentor_rating >= 4.5,
            cls.total_mentees_helped >= 10,
            cls.is_active == True
        ).order_by(cls.overall_mentor_score.desc()).all()
    
    @classmethod
    def get_ally_stats(cls) -> Dict[str, Any]:
        """Obtener estadísticas de aliados."""
        try:
            total_allies = cls.query.filter_by(is_active=True).count()
            available_mentors = cls.query.filter(
                cls.available_for_mentorship == True,
                cls.is_active == True
            ).count()
            
            # Por especialización
            specializations = {}
            all_specs = db.session.query(cls.specializations).filter_by(is_active=True).all()
            for spec_list in all_specs:
                if spec_list[0]:  # Si no es None
                    for spec in spec_list[0]:
                        specializations[spec] = specializations.get(spec, 0) + 1
            
            # Promedio de rating
            avg_rating = db.session.query(
                db.func.avg(cls.average_mentor_rating)
            ).filter(
                cls.average_mentor_rating > 0,
                cls.is_active == True
            ).scalar() or 0
            
            # Total mentees ayudados
            total_mentees_helped = db.session.query(
                db.func.sum(cls.total_mentees_helped)
            ).filter_by(is_active=True).scalar() or 0
            
            # Total horas de mentoría
            total_hours = db.session.query(
                db.func.sum(cls.total_mentorship_hours)
            ).filter_by(is_active=True).scalar() or 0
            
            return {
                'total_allies': total_allies,
                'available_mentors': available_mentors,
                'top_specializations': dict(sorted(specializations.items(), 
                                                  key=lambda x: x[1], reverse=True)[:10]),
                'average_rating': round(float(avg_rating), 2),
                'total_mentees_helped': int(total_mentees_helped),
                'total_hours_provided': round(float(total_hours), 1),
                'premium_mentors': cls.query.filter(
                    cls.average_mentor_rating >= 4.5,
                    cls.total_mentees_helped >= 10,
                    cls.is_active == True
                ).count()
            }
            
        except Exception as e:
            ally_logger.error(f"Error getting ally stats: {str(e)}")
            return {'error': str(e)}
    
    # ====================================
    # REPRESENTACIÓN
    # ====================================
    
    def __repr__(self):
        return f"<Ally(id={self.id}, email='{self.email}', specialization='{self.primary_expertise}')>"
    
    def __str__(self):
        return f"Mentor: {self.display_name} ({self.mentorship_experience_level})"


# ====================================
# EVENTOS DEL MODELO
# ====================================

@event.listens_for(Ally, 'before_insert')
def set_ally_defaults(mapper, connection, target):
    """Establecer valores por defecto antes de insertar."""
    # Asegurar que el rol sea ally
    target.role = ALLY_ROLE
    
    # Establecer fecha de ingreso como aliado
    if not target.joined_as_ally_at:
        target.joined_as_ally_at = datetime.utcnow()
    
    # Establecer fecha de inicio de mentoría si tiene experiencia
    if target.years_mentoring_experience > 0 and not target.started_mentoring_at:
        years_ago = target.years_mentoring_experience
        target.started_mentoring_at = datetime.utcnow() - timedelta(days=years_ago * 365)


@event.listens_for(Ally, 'before_update')
def update_ally_fields(mapper, connection, target):
    """Actualizar campos antes de actualizar."""
    # Actualizar última actividad de mentoría si cambió algo relevante
    mentorship_fields = ['current_mentees', 'total_mentees_helped', 'total_mentorship_hours']
    
    session = db.session
    if session.is_modified(target):
        for field in mentorship_fields:
            if session.is_modified(target, field):
                target.last_mentorship_activity = datetime.utcnow()
                break


@event.listens_for(Ally, 'after_insert')
def ally_created_actions(mapper, connection, target):
    """Acciones después de crear aliado."""
    ally_logger.info(f"New ally created: {target.email} with expertise: {target.primary_expertise}")
    
    # Programar envío de email de bienvenida
    @event.listens_for(db.session, 'after_commit', once=True)
    def send_ally_welcome(session):
        try:
            target.send_notification('ally_created', context={
                'expertise': target.primary_expertise,
                'specializations': target.specializations or []
            })
        except Exception as e:
            ally_logger.error(f"Error sending ally welcome notification: {str(e)}")


# ====================================
# FUNCIONES UTILITARIAS
# ====================================

def find_mentors_for_entrepreneur(entrepreneur_id: str, 
                                 max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Encontrar mentores compatibles para un emprendedor específico.
    
    Args:
        entrepreneur_id: ID del emprendedor
        max_results: Máximo número de resultados
        
    Returns:
        Lista de mentores compatibles
    """
    try:
        from .entrepreneur import Entrepreneur
        
        entrepreneur = Entrepreneur.get_by_id(entrepreneur_id)
        if not entrepreneur:
            raise ValueError("Emprendedor no encontrado")
        
        # Obtener mentores disponibles
        available_mentors = Ally.get_available_mentors()
        
        mentor_matches = []
        
        for mentor in available_mentors:
            # Calcular compatibilidad
            compatibility_score = mentor._calculate_mentee_compatibility(entrepreneur)
            
            if compatibility_score > 0.3:  # Threshold mínimo
                mentor_matches.append({
                    'mentor': mentor.to_mentor_profile(),
                    'compatibility_score': compatibility_score,
                    'matching_reasons': mentor._get_matching_reasons(entrepreneur),
                    'available_slots': max(0, mentor.max_mentees - mentor.current_mentees)
                })
        
        # Ordenar por compatibilidad
        mentor_matches.sort(key=lambda x: x['compatibility_score'], reverse=True)
        
        return mentor_matches[:max_results]
        
    except Exception as e:
        ally_logger.error(f"Error finding mentors for entrepreneur: {str(e)}")
        return []


def generate_mentor_directory(filters: Dict[str, Any] = None,
                             page: int = 1, per_page: int = 20) -> Dict[str, Any]:
    """
    Generar directorio público de mentores.
    
    Args:
        filters: Filtros a aplicar
        page: Página de resultados
        per_page: Resultados por página
        
    Returns:
        Directorio paginado de mentores
    """
    try:
        # Query base - solo mentores activos y disponibles
        query = Ally.query.filter_by(is_active=True)
        
        # Aplicar filtros
        if filters:
            if 'available_only' in filters and filters['available_only']:
                query = query.filter_by(available_for_mentorship=True)
            
            if 'specialization' in filters:
                query = query.filter(
                    Ally.specializations.contains([filters['specialization']])
                )
            
            if 'expertise' in filters:
                query = query.filter_by(primary_expertise=filters['expertise'])
            
            if 'min_rating' in filters:
                query = query.filter(
                    Ally.average_mentor_rating >= filters['min_rating']
                )
            
            if 'offers_pro_bono' in filters and filters['offers_pro_bono']:
                query = query.filter_by(offers_pro_bono=True)
            
            if 'offers_paid' in filters and filters['offers_paid']:
                query = query.filter_by(offers_paid_consulting=True)
            
            if 'city' in filters:
                query = query.filter_by(city=filters['city'])
            
            if 'experience_level' in filters:
                exp_level = filters['experience_level']
                if exp_level == 'expert':
                    query = query.filter(
                        Ally.years_mentoring_experience >= 5,
                        Ally.total_mentees_helped >= 20
                    )
                elif exp_level == 'experienced':
                    query = query.filter(
                        Ally.years_mentoring_experience >= 3,
                        Ally.total_mentees_helped >= 10
                    )
            
            if 'search' in filters:
                search_term = f"%{filters['search']}%"
                query = query.filter(db.or_(
                    Ally.first_name.ilike(search_term),
                    Ally.last_name.ilike(search_term),
                    Ally.current_role.ilike(search_term),
                    Ally.current_organization.ilike(search_term),
                    Ally.expertise_description.ilike(search_term)
                ))
        
        # Ordenar por score y rating
        query = query.order_by(
            Ally.average_mentor_rating.desc().nullslast(),
            Ally.total_mentees_helped.desc()
        )
        
        # Paginar
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Convertir a perfiles de mentor
        mentors = [mentor.to_mentor_profile() for mentor in pagination.items]
        
        # Obtener filtros disponibles
        available_specializations = set()
        available_expertise = set()
        available_cities = set()
        
        all_allies = Ally.query.filter_by(is_active=True).all()
        for ally in all_allies:
            if ally.specializations:
                available_specializations.update(ally.specializations)
            if ally.primary_expertise:
                available_expertise.add(ally.primary_expertise)
            if ally.city:
                available_cities.add(ally.city)
        
        return {
            'mentors': mentors,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            },
            'filters_applied': filters or {},
            'available_filters': {
                'specializations': sorted(list(available_specializations)),
                'expertise_areas': sorted(list(available_expertise)),
                'cities': sorted(list(available_cities)),
                'experience_levels': ['beginner', 'intermediate', 'experienced', 'expert']
            }
        }
        
    except Exception as e:
        ally_logger.error(f"Error generating mentor directory: {str(e)}")
        return {'error': str(e)}


def calculate_mentor_rankings() -> Dict[str, Any]:
    """
    Calcular rankings de mentores basado en métricas de performance.
    
    Returns:
        Rankings de mentores por diferentes categorías
    """
    try:
        active_mentors = Ally.query.filter_by(is_active=True).all()
        
        rankings = {
            'top_rated': [],
            'most_experienced': [],
            'highest_impact': [],
            'most_active': [],
            'rising_stars': []
        }
        
        # Top rated (por rating promedio)
        top_rated = sorted(
            [m for m in active_mentors if m.average_mentor_rating and m.total_ratings_received >= 3],
            key=lambda x: float(x.average_mentor_rating),
            reverse=True
        )[:10]
        
        rankings['top_rated'] = [
            {
                'mentor': mentor.to_mentor_profile(),
                'rating': float(mentor.average_mentor_rating),
                'total_ratings': mentor.total_ratings_received
            }
            for mentor in top_rated
        ]
        
        # Most experienced (por años de experiencia y mentees ayudados)
        most_experienced = sorted(
            active_mentors,
            key=lambda x: (x.years_mentoring_experience, x.total_mentees_helped),
            reverse=True
        )[:10]
        
        rankings['most_experienced'] = [
            {
                'mentor': mentor.to_mentor_profile(),
                'years_experience': mentor.years_mentoring_experience,
                'mentees_helped': mentor.total_mentees_helped
            }
            for mentor in most_experienced
        ]
        
        # Highest impact (por score de impacto)
        highest_impact = sorted(
            active_mentors,
            key=lambda x: x.impact_score,
            reverse=True
        )[:10]
        
        rankings['highest_impact'] = [
            {
                'mentor': mentor.to_mentor_profile(),
                'impact_score': mentor.impact_score,
                'mentees_helped': mentor.total_mentees_helped,
                'hours_provided': float(mentor.total_mentorship_hours or 0)
            }
            for mentor in highest_impact
        ]
        
        # Most active (actividad reciente)
        most_active = sorted(
            [m for m in active_mentors if m.last_mentorship_activity],
            key=lambda x: x.last_mentorship_activity,
            reverse=True
        )[:10]
        
        rankings['most_active'] = [
            {
                'mentor': mentor.to_mentor_profile(),
                'last_activity': mentor.last_mentorship_activity.isoformat(),
                'current_mentees': mentor.current_mentees
            }
            for mentor in most_active
        ]
        
        # Rising stars (nuevos con buen performance)
        rising_stars = sorted(
            [m for m in active_mentors 
             if m.years_in_ecosystem <= 2 and m.total_mentees_helped >= 3],
            key=lambda x: x.overall_mentor_score,
            reverse=True
        )[:10]
        
        rankings['rising_stars'] = [
            {
                'mentor': mentor.to_mentor_profile(),
                'years_in_ecosystem': mentor.years_in_ecosystem,
                'overall_score': mentor.overall_mentor_score,
                'mentees_helped': mentor.total_mentees_helped
            }
            for mentor in rising_stars
        ]
        
        return rankings
        
    except Exception as e:
        ally_logger.error(f"Error calculating mentor rankings: {str(e)}")
        return {'error': str(e)}


def analyze_mentorship_network() -> Dict[str, Any]:
    """
    Analizar la red de mentoría del ecosistema.
    
    Returns:
        Análisis de la red de mentoría
    """
    try:
        from .mentorship import Mentorship
        
        # Obtener todas las mentorías
        all_mentorships = Mentorship.query.all()
        active_mentorships = Mentorship.query.filter_by(status='active').all()
        
        # Métricas de red
        total_mentors = Ally.query.filter_by(is_active=True).count()
        active_mentors = len(set(m.ally_id for m in active_mentorships))
        
        # Análisis de conectividad
        mentor_connections = {}
        entrepreneur_connections = {}
        
        for mentorship in all_mentorships:
            mentor_id = mentorship.ally_id
            entrepreneur_id = mentorship.entrepreneur_id
            
            if mentor_id not in mentor_connections:
                mentor_connections[mentor_id] = set()
            mentor_connections[mentor_id].add(entrepreneur_id)
            
            if entrepreneur_id not in entrepreneur_connections:
                entrepreneur_connections[entrepreneur_id] = set()
            entrepreneur_connections[entrepreneur_id].add(mentor_id)
        
        # Métricas de distribución
        mentorship_distribution = {}
        for mentor_id, mentees in mentor_connections.items():
            count = len(mentees)
            if count not in mentorship_distribution:
                mentorship_distribution[count] = 0
            mentorship_distribution[count] += 1
        
        # Mentores más conectados
        top_connected_mentors = sorted(
            mentor_connections.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        
        # Calcular métricas de red
        total_connections = len(all_mentorships)
        avg_mentees_per_mentor = total_connections / max(total_mentors, 1)
        
        # Análisis de sectores
        sector_analysis = {}
        for mentorship in all_mentorships:
            if mentorship.ally and mentorship.entrepreneur:
                mentor_sector = mentorship.ally.primary_expertise
                entrepreneur_sector = mentorship.entrepreneur.primary_sector
                
                if mentor_sector:
                    if mentor_sector not in sector_analysis:
                        sector_analysis[mentor_sector] = {'same_sector': 0, 'cross_sector': 0}
                    
                    if mentor_sector == entrepreneur_sector:
                        sector_analysis[mentor_sector]['same_sector'] += 1
                    else:
                        sector_analysis[mentor_sector]['cross_sector'] += 1
        
        analysis = {
            'network_overview': {
                'total_mentors': total_mentors,
                'active_mentors': active_mentors,
                'total_mentorships': total_connections,
                'active_mentorships': len(active_mentorships),
                'avg_mentees_per_mentor': round(avg_mentees_per_mentor, 2),
                'network_density': round((total_connections / max(total_mentors, 1)) / 10, 3)
            },
            'mentorship_distribution': mentorship_distribution,
            'top_connected_mentors': [
                {
                    'mentor_id': str(mentor_id),
                    'total_mentees': len(mentees),
                    'mentor_name': Ally.get_by_id(mentor_id).full_name if Ally.get_by_id(mentor_id) else 'Unknown'
                }
                for mentor_id, mentees in top_connected_mentors
            ],
            'sector_analysis': sector_analysis,
            'network_health': {
                'utilization_rate': round((active_mentors / max(total_mentors, 1)) * 100, 2),
                'average_load': round(len(active_mentorships) / max(active_mentors, 1), 2),
                'capacity_available': sum(
                    max(0, mentor.max_mentees - mentor.current_mentees)
                    for mentor in Ally.query.filter_by(is_active=True, available_for_mentorship=True).all()
                )
            }
        }
        
        return analysis
        
    except Exception as e:
        ally_logger.error(f"Error analyzing mentorship network: {str(e)}")
        return {'error': str(e)}


def update_mentor_ratings():
    """
    Actualizar ratings promedio de todos los mentores basado en feedback reciente.
    Esta función se ejecutaría periódicamente.
    """
    try:
        from .mentorship import Mentorship
        
        allies = Ally.query.filter_by(is_active=True).all()
        updated_count = 0
        
        for ally in allies:
            # Obtener todas las mentorías con ratings
            mentorships_with_ratings = ally.mentorships_provided.filter(
                Mentorship.entrepreneur_rating.isnot(None)
            ).all()
            
            if mentorships_with_ratings:
                # Calcular nuevo promedio
                ratings = [m.entrepreneur_rating for m in mentorships_with_ratings]
                new_average = sum(ratings) / len(ratings)
                
                # Actualizar si cambió
                if ally.average_mentor_rating != new_average:
                    ally.average_mentor_rating = round(new_average, 2)
                    ally.total_ratings_received = len(ratings)
                    updated_count += 1
        
        db.session.commit()
        ally_logger.info(f"Updated ratings for {updated_count} mentors")
        
        return updated_count
        
    except Exception as e:
        ally_logger.error(f"Error updating mentor ratings: {str(e)}")
        return 0


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    'Ally',
    'find_mentors_for_entrepreneur',
    'generate_mentor_directory',
    'calculate_mentor_rankings',
    'analyze_mentorship_network',
    'update_mentor_ratings'
]

"""
Modelo de aliado/mentor para el ecosistema de emprendimiento.
Este módulo define la clase Ally que extiende User con funcionalidades específicas de mentoría y apoyo.
"""

import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Union
from decimal import Decimal
from flask import current_app
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Numeric, Time, event
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.dialects.postgresql import ARRAY

from app.extensions import db
from app.core.constants import (
    ALLY_ROLE, ENTREPRENEUR_ROLE, MAX_ENTREPRENEURS_PER_ALLY,
    ECONOMIC_SECTORS, MENTORSHIP_CONFIG
)
from app.core.security import log_security_event
from .base import GUID, JSONType
from .user import User
from .mixins import SearchableMixin, CacheableMixin, NotifiableMixin, ValidatableMixin

# Configurar logger
ally_logger = logging.getLogger('ecosistema.models.ally')

