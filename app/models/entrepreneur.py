"""
Modelo de emprendedor para el ecosistema de emprendimiento.
Este módulo define la clase Entrepreneur que extiende User con funcionalidades específicas de emprendimiento.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from decimal import Decimal
from flask import current_app
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Numeric, event
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.dialects.postgresql import ARRAY

from app.extensions import db
# from app.core.constants import (
#     ENTREPRENEUR_ROLE, PROJECT_STATUSES, ACTIVE_PROJECT_STATUSES,
#     MAX_PROJECTS_PER_ENTREPRENEUR, ECONOMIC_SECTORS, FUNDING_STAGES
# )
# from app.core.security import log_security_event

# Valores por defecto hasta arreglar las constantes
ENTREPRENEUR_ROLE = 'entrepreneur'
PROJECT_STATUSES = ['idea', 'development', 'launch', 'growth']
ACTIVE_PROJECT_STATUSES = ['development', 'launch', 'growth']
MAX_PROJECTS_PER_ENTREPRENEUR = 5
ECONOMIC_SECTORS = ['technology', 'healthcare', 'education', 'finance']
FUNDING_STAGES = ['pre-seed', 'seed', 'series-a', 'series-b']

def log_security_event(event_type, details):
    """Stub para log de seguridad."""
    print(f"Security event: {event_type} - {details}")
from .base import GUID, JSONType
from .user import User
from .mixins import SearchableMixin, CacheableMixin, NotifiableMixin, StateMachineMixin

# Configurar logger
entrepreneur_logger = logging.getLogger('ecosistema.models.entrepreneur')


# ====================================
# MODELO EMPRENDEDOR
# ====================================

class Entrepreneur(User):
    """
    Modelo de emprendedor que extiende User con funcionalidades específicas de emprendimiento.
    Los emprendedores pueden crear proyectos, recibir mentoría y participar en programas.
    """
    
    __tablename__ = 'entrepreneurs'
    __searchable__ = [
        'business_idea', 'target_market', 'value_proposition', 
        'current_challenges', 'entrepreneurship_stage', 'funding_stage'
    ]
    
    # Herencia de User
    id = Column(GUID(), ForeignKey('users.id'), primary_key=True)
    
    # ====================================
    # INFORMACIÓN DE EMPRENDIMIENTO
    # ====================================
    
    # Etapa y experiencia
    entrepreneurship_stage = Column(String(50), default='aspiring', nullable=False,
                                   doc="Etapa de emprendimiento: aspiring, early, established, serial")
    
    years_entrepreneurship = Column(Integer, default=0,
                                   doc="Años de experiencia en emprendimiento")
    
    previous_ventures = Column(Integer, default=0,
                              doc="Número de emprendimientos anteriores")
    
    # Ideas y proyectos
    business_idea = Column(Text, nullable=True,
                          doc="Idea de negocio principal actual")
    
    target_market = Column(Text, nullable=True,
                          doc="Mercado objetivo principal")
    
    value_proposition = Column(Text, nullable=True,
                              doc="Propuesta de valor única")
    
    business_model = Column(String(100), nullable=True,
                           doc="Modelo de negocio principal")
    
    # Sectores y especialización
    primary_sector = Column(String(50), nullable=True,
                           doc="Sector económico principal")
    
    secondary_sectors = Column(JSONType, default=list,
                              doc="Sectores secundarios de interés")
    
    expertise_areas = Column(JSONType, default=list,
                            doc="Áreas de expertise del emprendedor")
    
    # ====================================
    # FINANCIAMIENTO Y RECURSOS
    # ====================================
    
    funding_stage = Column(String(50), default='bootstrap', nullable=True,
                          doc="Etapa de financiamiento actual")
    
    funding_needed = Column(Numeric(15, 2), nullable=True,
                           doc="Monto de financiamiento necesario")
    
    funding_raised = Column(Numeric(15, 2), default=0,
                           doc="Monto total recaudado")
    
    current_revenue = Column(Numeric(15, 2), default=0,
                            doc="Ingresos mensuales actuales")
    
    projected_revenue = Column(Numeric(15, 2), nullable=True,
                              doc="Ingresos proyectados (mensual)")
    
    team_size = Column(Integer, default=1,
                      doc="Tamaño actual del equipo")
    
    looking_for_cofounders = Column(Boolean, default=False,
                                   doc="Buscando cofundadores")
    
    # ====================================
    # MENTORÍA Y DESARROLLO
    # ====================================
    
    seeking_mentorship = Column(Boolean, default=True,
                               doc="Buscando mentoría activamente")
    
    mentorship_areas = Column(JSONType, default=list,
                             doc="Áreas donde busca mentoría")
    
    current_challenges = Column(Text, nullable=True,
                               doc="Desafíos actuales principales")
    
    goals_short_term = Column(JSONType, default=list,
                             doc="Objetivos a corto plazo (3-6 meses)")
    
    goals_long_term = Column(JSONType, default=list,
                            doc="Objetivos a largo plazo (1-3 años)")
    
    # Progreso y logros
    key_achievements = Column(JSONType, default=list,
                             doc="Logros clave alcanzados")
    
    milestones_completed = Column(JSONType, default=list,
                                 doc="Hitos completados")
    
    next_milestones = Column(JSONType, default=list,
                            doc="Próximos hitos por alcanzar")
    
    # ====================================
    # MÉTRICAS Y SEGUIMIENTO
    # ====================================
    
    # Engagement en la plataforma
    profile_views = Column(Integer, default=0,
                          doc="Número de vistas del perfil")
    
    mentorship_sessions_completed = Column(Integer, default=0,
                                          doc="Sesiones de mentoría completadas")
    
    programs_participated = Column(Integer, default=0,
                                  doc="Programas en los que ha participado")
    
    networking_connections = Column(Integer, default=0,
                                   doc="Conexiones de networking realizadas")
    
    # Scores y evaluaciones
    commitment_score = Column(Numeric(3, 2), default=0.0,
                             doc="Score de compromiso (0.0-5.0)")
    
    progress_score = Column(Numeric(3, 2), default=0.0,
                           doc="Score de progreso (0.0-5.0)")
    
    impact_score = Column(Numeric(3, 2), default=0.0,
                         doc="Score de impacto potencial (0.0-5.0)")
    
    overall_rating = Column(Numeric(3, 2), default=0.0,
                           doc="Calificación general (0.0-5.0)")
    
    # ====================================
    # CONFIGURACIONES Y PREFERENCIAS
    # ====================================
    
    # Disponibilidad para mentoría
    available_for_mentorship = Column(Boolean, default=True,
                                     doc="Disponible para recibir mentoría")
    
    mentorship_frequency = Column(String(20), default='weekly',
                                 doc="Frecuencia preferida de mentoría")
    
    preferred_meeting_times = Column(JSONType, default=dict,
                                    doc="Horarios preferidos para reuniones")
    
    # Comunicación y networking
    open_to_collaboration = Column(Boolean, default=True,
                                  doc="Abierto a colaboraciones")
    
    willing_to_mentor_others = Column(Boolean, default=False,
                                     doc="Dispuesto a mentorear a otros")
    
    public_profile = Column(Boolean, default=True,
                           doc="Perfil visible públicamente")
    
    # ====================================
    # INFORMACIÓN ADICIONAL
    # ====================================
    
    # Motivaciones y background
    motivation_statement = Column(Text, nullable=True,
                                 doc="Declaración de motivación personal")
    
    entrepreneurship_inspiration = Column(Text, nullable=True,
                                        doc="Qué lo inspiró a emprender")
    
    success_definition = Column(Text, nullable=True,
                               doc="Cómo define el éxito")
    
    # Recursos y necesidades
    resources_needed = Column(JSONType, default=list,
                             doc="Recursos que necesita actualmente")
    
    resources_offered = Column(JSONType, default=list,
                              doc="Recursos que puede ofrecer a otros")
    
    # Timeline y fechas importantes
    started_entrepreneurship_at = Column(DateTime(timezone=True), nullable=True,
                                        doc="Fecha en que empezó a emprender")
    
    joined_ecosystem_at = Column(DateTime(timezone=True), default=datetime.utcnow,
                                doc="Fecha de ingreso al ecosistema")
    
    last_activity_update = Column(DateTime(timezone=True), nullable=True,
                                 doc="Última actualización de actividad")
    
    # ====================================
    # RELACIONES
    # ====================================
    
    # Proyectos del emprendedor
    projects = relationship("Project", backref="entrepreneur", lazy='dynamic',
                           cascade="all, delete-orphan")
    
    # Mentorías recibidas
    mentorships_received = relationship("Mentorship", backref="entrepreneur", lazy='dynamic',
                                       foreign_keys="Mentorship.entrepreneur_id")
    
    # Programas en los que participa
    program_participations = relationship("ProgramParticipation", backref="entrepreneur",
                                         cascade="all, delete-orphan")
    
    # Configurar relación con User
    __mapper_args__ = {
        'polymorphic_identity': ENTREPRENEUR_ROLE,
        'inherit_condition': id == User.id
    }
    
    # ====================================
    # CONFIGURACIÓN DE NOTIFICACIONES
    # ====================================
    
    _notification_events = {
        'entrepreneur_created': {'template': 'entrepreneur_welcome', 'enabled': True},
        'project_created': {'template': 'project_created_notification', 'enabled': True},
        'mentorship_assigned': {'template': 'mentorship_assigned', 'enabled': True},
        'milestone_achieved': {'template': 'milestone_celebration', 'enabled': True},
        'program_accepted': {'template': 'program_acceptance', 'enabled': True},
        'profile_featured': {'template': 'profile_featured', 'enabled': True}
    }
    
    # ====================================
    # PROPIEDADES CALCULADAS
    # ====================================
    
    @hybrid_property
    def active_projects_count(self):
        """Número de proyectos activos."""
        return self.projects.filter(
            db.text("status IN :statuses")
        ).params(statuses=ACTIVE_PROJECT_STATUSES).count()
    
    @hybrid_property
    def total_projects_count(self):
        """Número total de proyectos."""
        return self.projects.count()
    
    @property
    def can_create_new_project(self):
        """Verificar si puede crear un nuevo proyecto."""
        return self.active_projects_count < MAX_PROJECTS_PER_ENTREPRENEUR
    
    @property
    def entrepreneurship_stage_display(self):
        """Nombre legible de la etapa de emprendimiento."""
        stages = {
            'aspiring': 'Aspirante',
            'early': 'Emprendedor Temprano',
            'established': 'Emprendedor Establecido',
            'serial': 'Emprendedor Serial'
        }
        return stages.get(self.entrepreneurship_stage, self.entrepreneurship_stage.title())
    
    @property
    def funding_stage_display(self):
        """Nombre legible de la etapa de financiamiento."""
        from app.core.constants import FUNDING_STAGES
        return FUNDING_STAGES.get(self.funding_stage, self.funding_stage)
    
    @property
    def primary_sector_display(self):
        """Nombre legible del sector principal."""
        return ECONOMIC_SECTORS.get(self.primary_sector, self.primary_sector)
    
    @property
    def is_seeking_funding(self):
        """Verificar si está buscando financiamiento."""
        return self.funding_needed and self.funding_needed > 0
    
    @property
    def funding_gap(self):
        """Brecha de financiamiento."""
        if self.funding_needed and self.funding_raised:
            return max(0, self.funding_needed - self.funding_raised)
        return self.funding_needed or 0
    
    @property
    def revenue_growth_potential(self):
        """Potencial de crecimiento de ingresos."""
        if self.current_revenue and self.projected_revenue:
            if self.current_revenue > 0:
                return ((self.projected_revenue - self.current_revenue) / self.current_revenue) * 100
        return 0
    
    @property
    def entrepreneurship_experience_level(self):
        """Nivel de experiencia en emprendimiento."""
        if self.years_entrepreneurship >= 5 or self.previous_ventures >= 2:
            return 'experienced'
        elif self.years_entrepreneurship >= 2 or self.previous_ventures >= 1:
            return 'intermediate'
        else:
            return 'beginner'
    
    @property
    def is_first_time_entrepreneur(self):
        """Verificar si es emprendedor por primera vez."""
        return self.previous_ventures == 0
    
    @property
    def days_in_ecosystem(self):
        """Días desde que se unió al ecosistema."""
        if self.joined_ecosystem_at:
            return (datetime.now(timezone.utc) - self.joined_ecosystem_at).days
        return 0
    
    @property
    def engagement_level(self):
        """Nivel de engagement en la plataforma."""
        # Calcular basado en actividad
        score = 0
        
        # Proyectos activos
        score += self.active_projects_count * 20
        
        # Sesiones de mentoría
        score += min(self.mentorship_sessions_completed * 5, 50)
        
        # Participación en programas
        score += self.programs_participated * 15
        
        # Conexiones de networking
        score += min(self.networking_connections * 2, 30)
        
        # Actividad reciente
        if self.last_activity_update:
            days_since_activity = (datetime.now(timezone.utc) - self.last_activity_update).days
            if days_since_activity <= 7:
                score += 20
            elif days_since_activity <= 30:
                score += 10
        
        # Clasificar nivel
        if score >= 80:
            return 'high'
        elif score >= 40:
            return 'medium'
        else:
            return 'low'
    
    # ====================================
    # MÉTODOS DE GESTIÓN DE PROYECTOS
    # ====================================
    
    def create_project(self, project_data: dict[str, Any]) -> 'Project':
        """
        Crear nuevo proyecto.
        
        Args:
            project_data: Datos del proyecto
            
        Returns:
            Nueva instancia de Project
        """
        if not self.can_create_new_project:
            raise ValueError(f"Máximo de {MAX_PROJECTS_PER_ENTREPRENEUR} proyectos activos alcanzado")
        
        try:
            from .project import Project
            
            # Añadir entrepreneur_id automáticamente
            project_data['entrepreneur_id'] = self.id
            
            # Crear proyecto
            project = Project(**project_data)
            project.save()
            
            # Registrar logro si es el primer proyecto
            if self.total_projects_count == 1:
                self.add_achievement('first_project_created', {
                    'project_name': project.name,
                    'created_at': datetime.now(timezone.utc).isoformat()
                })
            
            # Enviar notificación
            self.send_notification('project_created', context={
                'project_name': project.name,
                'project_id': str(project.id)
            })
            
            entrepreneur_logger.info(f"Project created by entrepreneur {self.email}: {project.name}")
            return project
            
        except Exception as e:
            entrepreneur_logger.error(f"Error creating project: {str(e)}")
            raise
    
    def get_active_projects(self):
        """Obtener proyectos activos."""
        return self.projects.filter(
            db.text("status IN :statuses")
        ).params(statuses=ACTIVE_PROJECT_STATUSES).all()
    
    def get_project_by_status(self, status: str):
        """Obtener proyectos por estado."""
        return self.projects.filter_by(status=status).all()
    
    def get_projects_summary(self) -> dict[str, Any]:
        """Obtener resumen de proyectos."""
        try:
            projects = self.projects.all()
            
            summary = {
                'total_projects': len(projects),
                'active_projects': 0,
                'completed_projects': 0,
                'by_status': {},
                'by_sector': {},
                'average_duration': 0,
                'success_rate': 0
            }
            
            total_duration = 0
            successful_projects = 0
            
            for project in projects:
                # Contar por estado
                status = project.status
                if status not in summary['by_status']:
                    summary['by_status'][status] = 0
                summary['by_status'][status] += 1
                
                # Contar activos y completados
                if status in ACTIVE_PROJECT_STATUSES:
                    summary['active_projects'] += 1
                elif status in ['exit', 'completed']:
                    summary['completed_projects'] += 1
                    successful_projects += 1
                
                # Contar por sector
                sector = project.industry or 'unknown'
                if sector not in summary['by_sector']:
                    summary['by_sector'][sector] = 0
                summary['by_sector'][sector] += 1
                
                # Calcular duración si el proyecto ha terminado
                if project.end_date and project.start_date:
                    duration = (project.end_date - project.start_date).days
                    total_duration += duration
            
            # Calcular promedios
            if summary['completed_projects'] > 0:
                summary['average_duration'] = total_duration / summary['completed_projects']
                summary['success_rate'] = (successful_projects / summary['completed_projects']) * 100
            
            return summary
            
        except Exception as e:
            entrepreneur_logger.error(f"Error getting projects summary: {str(e)}")
            return {'error': str(e)}
    
    # ====================================
    # MÉTODOS DE MENTORÍA
    # ====================================
    
    def request_mentorship(self, areas: list[str] = None, preferences: dict[str, Any] = None) -> bool:
        """
        Solicitar mentoría.
        
        Args:
            areas: Áreas específicas donde busca mentoría
            preferences: Preferencias para el mentor
            
        Returns:
            True si la solicitud fue exitosa
        """
        try:
            # Actualizar áreas de mentoría solicitadas
            if areas:
                self.mentorship_areas = list(set((self.mentorship_areas or []) + areas))
            
            # Marcar como buscando mentoría
            self.seeking_mentorship = True
            self.available_for_mentorship = True
            
            # Guardar preferencias si se proporcionan
            if preferences:
                self.set_metadata('mentorship_preferences', preferences)
            
            db.session.commit()
            
            # Log del evento
            entrepreneur_logger.info(f"Mentorship requested by {self.email} for areas: {areas}")
            
            # Enviar notificación a posibles mentores (implementar lógica de matching)
            self._notify_potential_mentors(areas or self.mentorship_areas)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            entrepreneur_logger.error(f"Error requesting mentorship: {str(e)}")
            return False
    
    def _notify_potential_mentors(self, areas: list[str]):
        """Notificar a mentores potenciales sobre solicitud de mentoría."""
        try:
            from .ally import Ally
            
            # Buscar mentores que puedan ayudar en las áreas solicitadas
            potential_mentors = Ally.query.filter(
                Ally.is_active == True,
                Ally.available_for_mentorship == True
            ).all()
            
            # Filtrar por especialización (implementar lógica de matching más sofisticada)
            matching_mentors = []
            for mentor in potential_mentors:
                mentor_specializations = mentor.specializations or []
                if any(area in mentor_specializations for area in areas):
                    matching_mentors.append(mentor)
            
            # Enviar notificación a mentores compatibles
            for mentor in matching_mentors[:5]:  # Limitar a 5 mentores
                mentor.send_notification('mentorship_request', context={
                    'entrepreneur_name': self.full_name,
                    'entrepreneur_id': str(self.id),
                    'areas_requested': areas,
                    'business_idea': self.business_idea
                })
                
        except Exception as e:
            entrepreneur_logger.error(f"Error notifying potential mentors: {str(e)}")
    
    def get_mentorship_history(self) -> list[dict[str, Any]]:
        """Obtener historial de mentorías."""
        try:
            mentorships = self.mentorships_received.all()
            
            history = []
            for mentorship in mentorships:
                history.append({
                    'id': str(mentorship.id),
                    'mentor_name': mentorship.ally.full_name if mentorship.ally else 'Unknown',
                    'start_date': mentorship.start_date.isoformat() if mentorship.start_date else None,
                    'end_date': mentorship.end_date.isoformat() if mentorship.end_date else None,
                    'status': mentorship.status,
                    'areas_covered': mentorship.focus_areas or [],
                    'sessions_completed': mentorship.sessions_completed or 0,
                    'rating': mentorship.entrepreneur_rating
                })
            
            return history
            
        except Exception as e:
            entrepreneur_logger.error(f"Error getting mentorship history: {str(e)}")
            return []
    
    # ====================================
    # MÉTODOS DE LOGROS Y PROGRESO
    # ====================================
    
    def add_achievement(self, achievement_type: str, details: dict[str, Any] = None):
        """
        Añadir logro al perfil.
        
        Args:
            achievement_type: Tipo de logro
            details: Detalles adicionales del logro
        """
        try:
            achievement = {
                'type': achievement_type,
                'achieved_at': datetime.now(timezone.utc).isoformat(),
                'details': details or {}
            }
            
            if not self.key_achievements:
                self.key_achievements = []
            
            self.key_achievements.append(achievement)
            
            # Marcar como modificado para SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(self, 'key_achievements')
            
            db.session.commit()
            
            # Enviar notificación de logro
            self.send_notification('milestone_achieved', context={
                'achievement_type': achievement_type,
                'details': details
            })
            
            entrepreneur_logger.info(f"Achievement added for {self.email}: {achievement_type}")
            
        except Exception as e:
            entrepreneur_logger.error(f"Error adding achievement: {str(e)}")
    
    def complete_milestone(self, milestone: str, details: dict[str, Any] = None):
        """
        Marcar hito como completado.
        
        Args:
            milestone: Descripción del hito
            details: Detalles adicionales
        """
        try:
            completed_milestone = {
                'milestone': milestone,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'details': details or {}
            }
            
            if not self.milestones_completed:
                self.milestones_completed = []
            
            self.milestones_completed.append(completed_milestone)
            
            # Remover de próximos hitos si existe
            if self.next_milestones and milestone in self.next_milestones:
                self.next_milestones.remove(milestone)
            
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(self, 'milestones_completed')
            flag_modified(self, 'next_milestones')
            
            # Actualizar scores
            self._update_progress_scores()
            
            db.session.commit()
            
            entrepreneur_logger.info(f"Milestone completed by {self.email}: {milestone}")
            
        except Exception as e:
            entrepreneur_logger.error(f"Error completing milestone: {str(e)}")
    
    def set_goals(self, short_term: list[str] = None, long_term: list[str] = None):
        """
        Establecer objetivos a corto y largo plazo.
        
        Args:
            short_term: Objetivos a corto plazo
            long_term: Objetivos a largo plazo
        """
        if short_term is not None:
            self.goals_short_term = short_term
        if long_term is not None:
            self.goals_long_term = long_term
        
        db.session.commit()
        entrepreneur_logger.info(f"Goals updated for {self.email}")
    
    def _update_progress_scores(self):
        """Actualizar scores de progreso basado en actividad."""
        try:
            # Calcular commitment score
            commitment_factors = [
                min(self.mentorship_sessions_completed * 0.1, 1.0),
                min(self.active_projects_count * 0.3, 1.0),
                min(len(self.milestones_completed or []) * 0.2, 1.0),
                1.0 if self.last_activity_update and 
                     (datetime.now(timezone.utc) - self.last_activity_update).days <= 7 else 0.0
            ]
            self.commitment_score = sum(commitment_factors) * 1.25  # Max 5.0
            
            # Calcular progress score
            progress_factors = [
                len(self.milestones_completed or []) * 0.5,
                self.active_projects_count * 0.3,
                min(self.programs_participated * 0.4, 2.0)
            ]
            self.progress_score = min(sum(progress_factors), 5.0)
            
            # Calcular impact score (basado en métricas de negocio)
            impact_factors = [
                min(float(self.current_revenue or 0) / 10000, 2.0),  # Revenue impact
                min(self.team_size * 0.2, 1.0),  # Team impact
                min(self.networking_connections * 0.01, 1.0),  # Network impact
                1.0 if self.funding_raised and self.funding_raised > 0 else 0.0
            ]
            self.impact_score = min(sum(impact_factors), 5.0)
            
            # Calcular overall rating
            self.overall_rating = (
                self.commitment_score * 0.3 +
                self.progress_score * 0.4 +
                self.impact_score * 0.3
            )
            
        except Exception as e:
            entrepreneur_logger.error(f"Error updating progress scores: {str(e)}")
    
    # ====================================
    # MÉTODOS DE ANÁLISIS Y MÉTRICAS
    # ====================================
    
    def get_performance_dashboard(self) -> dict[str, Any]:
        """
        Obtener datos para dashboard de performance del emprendedor.
        
        Returns:
            Diccionario con métricas de performance
        """
        try:
            dashboard_data = {
                'personal_info': {
                    'name': self.full_name,
                    'stage': self.entrepreneurship_stage_display,
                    'experience_level': self.entrepreneurship_experience_level,
                    'days_in_ecosystem': self.days_in_ecosystem,
                    'engagement_level': self.engagement_level
                },
                'projects': self.get_projects_summary(),
                'scores': {
                    'commitment': float(self.commitment_score or 0),
                    'progress': float(self.progress_score or 0),
                    'impact': float(self.impact_score or 0),
                    'overall': float(self.overall_rating or 0)
                },
                'mentorship': {
                    'sessions_completed': self.mentorship_sessions_completed,
                    'currently_seeking': self.seeking_mentorship,
                    'areas_of_interest': self.mentorship_areas or [],
                    'history_count': self.mentorships_received.count()
                },
                'financial': {
                    'current_revenue': float(self.current_revenue or 0),
                    'projected_revenue': float(self.projected_revenue or 0),
                    'funding_raised': float(self.funding_raised or 0),
                    'funding_needed': float(self.funding_needed or 0),
                    'funding_gap': float(self.funding_gap or 0)
                },
                'achievements': {
                    'key_achievements': len(self.key_achievements or []),
                    'milestones_completed': len(self.milestones_completed or []),
                    'programs_participated': self.programs_participated
                },
                'networking': {
                    'connections': self.networking_connections,
                    'profile_views': self.profile_views,
                    'open_to_collaboration': self.open_to_collaboration
                }
            }
            
            return dashboard_data
            
        except Exception as e:
            entrepreneur_logger.error(f"Error getting performance dashboard: {str(e)}")
            return {'error': str(e)}
    
    def get_growth_trajectory(self, months_back: int = 12) -> dict[str, Any]:
        """
        Obtener trayectoria de crecimiento del emprendedor.
        
        Args:
            months_back: Meses hacia atrás para el análisis
            
        Returns:
            Datos de trayectoria de crecimiento
        """
        try:
            # Obtener datos históricos (implementar con activity logs)
            from .activity_log import ActivityLog
            
            start_date = datetime.now(timezone.utc)
            # TODO: Implementar lógica de trayectoria de crecimiento
            return {
                'growth_trend': 'positive',
                'months_analyzed': months_back,
                'start_date': start_date.isoformat(),
                'metrics': {
                    'projects_created': 0,
                    'meetings_completed': 0,
                    'skills_acquired': 0
                }
            }
        except Exception as e:
            entrepreneur_logger.error(f"Error getting growth trajectory: {str(e)}")
            return {'error': str(e)}