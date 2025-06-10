"""
Entrepreneur Service Module

Servicio especializado para gestión de emprendedores en el ecosistema.
Maneja toda la lógica de negocio específica para emprendedores, sus proyectos,
mentoría, progreso y métricas.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, asc, case
from flask import current_app
import statistics

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.user import User
from app.models.ally import Ally
from app.models.project import Project
from app.models.program import Program
from app.models.mentorship import MentorshipSession
from app.models.organization import Organization
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.document import Document
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.core.exceptions import (
    ValidationError,
    UserNotFoundError,
    PermissionError,
    ServiceError,
    BusinessRuleError
)
from app.core.constants import (
    USER_STATUS,
    PROJECT_STATUS,
    MENTORSHIP_STATUS,
    TASK_STATUS,
    NOTIFICATION_TYPES,
    ACTIVITY_TYPES,
    ENTREPRENEUR_STAGES,
    PROJECT_PHASES,
    MENTORSHIP_TYPES
)
from app.services.base import BaseService
from app.services.user_service import UserService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.analytics_service import AnalyticsService
from app.utils.validators import validate_business_model, validate_market_size
from app.utils.formatters import format_currency, format_percentage
from app.utils.date_utils import get_business_days_between, add_business_days
from app.utils.export_utils import generate_entrepreneur_report

logger = logging.getLogger(__name__)


class EntrepreneurService(BaseService):
    """
    Servicio especializado para gestión de emprendedores.
    
    Funcionalidades principales:
    - Onboarding y perfil de emprendedores
    - Gestión de proyectos de emprendimiento
    - Sistema de mentoría y seguimiento
    - Tracking de progreso y métricas
    - Asignación a programas
    - Relaciones con aliados/mentores
    - Gestión de documentos y tareas
    - Reportes y analytics específicos
    - Evaluaciones y validaciones
    """

    def __init__(self):
        super().__init__()
        self.user_service = UserService()
        self.notification_service = NotificationService()
        self.email_service = EmailService()
        self.analytics_service = AnalyticsService()

    # ==================== GESTIÓN DE PERFIL EMPRENDEDOR ====================

    def complete_entrepreneur_profile(self, user_id: int, profile_data: Dict[str, Any]) -> Entrepreneur:
        """
        Completa el perfil de un emprendedor después del registro inicial.
        
        Args:
            user_id: ID del usuario emprendedor
            profile_data: Datos del perfil a completar
            
        Returns:
            Emprendedor con perfil completado
            
        Raises:
            UserNotFoundError: Si el emprendedor no existe
            ValidationError: Si los datos no son válidos
        """
        try:
            entrepreneur = self.get_entrepreneur_by_user_id(user_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor con user_id {user_id} no encontrado")
            
            # Validar datos del perfil
            self._validate_profile_data(profile_data)
            
            # Actualizar perfil
            self._update_entrepreneur_profile(entrepreneur, profile_data)
            
            # Marcar perfil como completado
            entrepreneur.profile_completed = True
            entrepreneur.profile_completion_date = datetime.utcnow()
            entrepreneur.current_stage = ENTREPRENEUR_STAGES.VALIDATED
            
            db.session.commit()
            
            # Crear proyecto inicial si no existe
            if not entrepreneur.projects:
                self._create_initial_project(entrepreneur, profile_data)
            
            # Asignar a programa apropiado
            self._assign_to_appropriate_program(entrepreneur)
            
            # Notificaciones
            self.notification_service.create_notification(
                user_id=user_id,
                type=NOTIFICATION_TYPES.PROFILE_COMPLETED,
                title="¡Perfil completado!",
                message="Tu perfil de emprendedor ha sido completado. Ahora puedes acceder a todos los recursos."
            )
            
            # Log de actividad
            self._log_activity(
                user_id=user_id,
                activity_type=ACTIVITY_TYPES.PROFILE_COMPLETED,
                details="Perfil de emprendedor completado"
            )
            
            logger.info(f"Perfil completado para emprendedor: {entrepreneur.user.email}")
            return entrepreneur
            
        except (UserNotFoundError, ValidationError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completando perfil: {str(e)}")
            raise ServiceError(f"Error interno completando perfil: {str(e)}")

    def update_entrepreneur_stage(self, entrepreneur_id: int, new_stage: str, 
                                 updated_by: int = None, notes: str = None) -> bool:
        """
        Actualiza la etapa de desarrollo del emprendedor.
        
        Args:
            entrepreneur_id: ID del emprendedor
            new_stage: Nueva etapa
            updated_by: ID del usuario que actualiza
            notes: Notas sobre el cambio
            
        Returns:
            True si se actualizó exitosamente
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            if new_stage not in ENTREPRENEUR_STAGES.__dict__.values():
                raise ValidationError(f"Etapa inválida: {new_stage}")
            
            old_stage = entrepreneur.current_stage
            entrepreneur.current_stage = new_stage
            entrepreneur.stage_updated_at = datetime.utcnow()
            
            # Crear entrada en historial de etapas
            stage_history = {
                'from_stage': old_stage,
                'to_stage': new_stage,
                'changed_at': datetime.utcnow(),
                'changed_by': updated_by,
                'notes': notes
            }
            
            if not entrepreneur.stage_history:
                entrepreneur.stage_history = []
            entrepreneur.stage_history.append(stage_history)
            
            db.session.commit()
            
            # Notificación
            self.notification_service.create_notification(
                user_id=entrepreneur.user_id,
                type=NOTIFICATION_TYPES.STAGE_UPDATE,
                title="Etapa actualizada",
                message=f"Tu etapa de desarrollo ha cambiado a: {new_stage}"
            )
            
            # Log de actividad
            self._log_activity(
                user_id=entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.STAGE_UPDATED,
                details=f"Etapa cambiada de {old_stage} a {new_stage}",
                performed_by=updated_by
            )
            
            # Trigger automático para nuevas oportunidades
            self._trigger_stage_based_opportunities(entrepreneur)
            
            logger.info(f"Etapa actualizada para {entrepreneur.user.email}: {old_stage} -> {new_stage}")
            return True
            
        except (UserNotFoundError, ValidationError):
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando etapa: {str(e)}")
            raise ServiceError(f"Error interno actualizando etapa: {str(e)}")

    # ==================== GESTIÓN DE PROYECTOS ====================

    def create_project(self, entrepreneur_id: int, project_data: Dict[str, Any]) -> Project:
        """
        Crea un nuevo proyecto para el emprendedor.
        
        Args:
            entrepreneur_id: ID del emprendedor
            project_data: Datos del proyecto
            
        Returns:
            Proyecto creado
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            # Validar datos del proyecto
            self._validate_project_data(project_data)
            
            # Crear proyecto
            project = Project(
                entrepreneur_id=entrepreneur_id,
                name=project_data['name'],
                description=project_data.get('description', ''),
                industry=project_data.get('industry'),
                target_market=project_data.get('target_market'),
                business_model=project_data.get('business_model'),
                revenue_model=project_data.get('revenue_model'),
                market_size=project_data.get('market_size'),
                funding_required=project_data.get('funding_required'),
                current_phase=PROJECT_PHASES.IDEATION,
                status=PROJECT_STATUS.ACTIVE,
                created_at=datetime.utcnow()
            )
            
            db.session.add(project)
            db.session.commit()
            
            # Crear tareas iniciales del proyecto
            self._create_initial_project_tasks(project)
            
            # Notificación
            self.notification_service.create_notification(
                user_id=entrepreneur.user_id,
                type=NOTIFICATION_TYPES.PROJECT_CREATED,
                title="Proyecto creado",
                message=f"Tu proyecto '{project.name}' ha sido creado exitosamente"
            )
            
            # Log de actividad
            self._log_activity(
                user_id=entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.PROJECT_CREATED,
                details=f"Proyecto creado: {project.name}"
            )
            
            logger.info(f"Proyecto creado: {project.name} para {entrepreneur.user.email}")
            return project
            
        except (UserNotFoundError, ValidationError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando proyecto: {str(e)}")
            raise ServiceError(f"Error interno creando proyecto: {str(e)}")

    def update_project_phase(self, project_id: int, new_phase: str, 
                           completion_percentage: float = None) -> bool:
        """
        Actualiza la fase del proyecto.
        
        Args:
            project_id: ID del proyecto
            new_phase: Nueva fase
            completion_percentage: Porcentaje de completado
            
        Returns:
            True si se actualizó exitosamente
        """
        try:
            project = Project.query.get(project_id)
            if not project:
                raise ValidationError(f"Proyecto {project_id} no encontrado")
            
            if new_phase not in PROJECT_PHASES.__dict__.values():
                raise ValidationError(f"Fase inválida: {new_phase}")
            
            old_phase = project.current_phase
            project.current_phase = new_phase
            project.phase_updated_at = datetime.utcnow()
            
            if completion_percentage is not None:
                project.completion_percentage = max(0, min(100, completion_percentage))
            
            # Actualizar métricas de progreso
            self._update_project_progress_metrics(project)
            
            db.session.commit()
            
            # Notificación al emprendedor
            self.notification_service.create_notification(
                user_id=project.entrepreneur.user_id,
                type=NOTIFICATION_TYPES.PROJECT_PHASE_UPDATE,
                title="Fase del proyecto actualizada",
                message=f"Tu proyecto '{project.name}' ahora está en fase: {new_phase}"
            )
            
            # Si hay mentor asignado, notificar también
            if project.entrepreneur.assigned_mentor:
                self.notification_service.create_notification(
                    user_id=project.entrepreneur.assigned_mentor.user_id,
                    type=NOTIFICATION_TYPES.MENTEE_PROGRESS,
                    title="Progreso del mentoreado",
                    message=f"El proyecto '{project.name}' de {project.entrepreneur.user.get_full_name()} avanzó a: {new_phase}"
                )
            
            logger.info(f"Fase actualizada para proyecto {project.name}: {old_phase} -> {new_phase}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando fase del proyecto: {str(e)}")
            raise ServiceError(f"Error interno actualizando fase: {str(e)}")

    # ==================== SISTEMA DE MENTORÍA ====================

    def assign_mentor(self, entrepreneur_id: int, mentor_id: int, 
                     assigned_by: int = None, notes: str = None) -> bool:
        """
        Asigna un mentor a un emprendedor.
        
        Args:
            entrepreneur_id: ID del emprendedor
            mentor_id: ID del mentor (Ally)
            assigned_by: ID del usuario que asigna
            notes: Notas sobre la asignación
            
        Returns:
            True si se asignó exitosamente
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            mentor = Ally.query.get(mentor_id)
            if not mentor:
                raise UserNotFoundError(f"Mentor {mentor_id} no encontrado")
            
            # Verificar disponibilidad del mentor
            if not self._check_mentor_availability(mentor):
                raise BusinessRuleError("El mentor no tiene disponibilidad para nuevos mentoreados")
            
            # Verificar si ya tiene mentor asignado
            if entrepreneur.assigned_mentor_id:
                raise BusinessRuleError("El emprendedor ya tiene un mentor asignado")
            
            # Asignar mentor
            entrepreneur.assigned_mentor_id = mentor_id
            entrepreneur.mentor_assigned_at = datetime.utcnow()
            entrepreneur.mentor_assignment_notes = notes
            
            # Actualizar contador del mentor
            mentor.current_mentees_count = (mentor.current_mentees_count or 0) + 1
            
            db.session.commit()
            
            # Notificaciones
            self.notification_service.create_notification(
                user_id=entrepreneur.user_id,
                type=NOTIFICATION_TYPES.MENTOR_ASSIGNED,
                title="Mentor asignado",
                message=f"{mentor.user.get_full_name()} ha sido asignado como tu mentor"
            )
            
            self.notification_service.create_notification(
                user_id=mentor.user_id,
                type=NOTIFICATION_TYPES.MENTEE_ASSIGNED,
                title="Nuevo mentoreado asignado",
                message=f"{entrepreneur.user.get_full_name()} ha sido asignado como tu mentoreado"
            )
            
            # Email de introducción
            self._send_mentor_introduction_email(entrepreneur, mentor)
            
            # Programar primera sesión
            self._schedule_initial_mentorship_session(entrepreneur, mentor)
            
            # Log de actividad
            self._log_activity(
                user_id=entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.MENTOR_ASSIGNED,
                details=f"Mentor asignado: {mentor.user.get_full_name()}",
                performed_by=assigned_by
            )
            
            logger.info(f"Mentor asignado: {mentor.user.email} -> {entrepreneur.user.email}")
            return True
            
        except (UserNotFoundError, BusinessRuleError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error asignando mentor: {str(e)}")
            raise ServiceError(f"Error interno asignando mentor: {str(e)}")

    def schedule_mentorship_session(self, entrepreneur_id: int, session_data: Dict[str, Any]) -> MentorshipSession:
        """
        Programa una sesión de mentoría.
        
        Args:
            entrepreneur_id: ID del emprendedor
            session_data: Datos de la sesión
            
        Returns:
            Sesión de mentoría creada
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            if not entrepreneur.assigned_mentor:
                raise BusinessRuleError("El emprendedor no tiene mentor asignado")
            
            # Validar datos de la sesión
            self._validate_session_data(session_data)
            
            # Verificar disponibilidad de horario
            if not self._check_time_availability(
                entrepreneur.assigned_mentor.user_id,
                session_data['scheduled_at'],
                session_data.get('duration_minutes', 60)
            ):
                raise BusinessRuleError("El mentor no está disponible en el horario solicitado")
            
            # Crear sesión
            session = MentorshipSession(
                entrepreneur_id=entrepreneur_id,
                mentor_id=entrepreneur.assigned_mentor_id,
                title=session_data.get('title', 'Sesión de Mentoría'),
                description=session_data.get('description', ''),
                session_type=session_data.get('type', MENTORSHIP_TYPES.GENERAL),
                scheduled_at=session_data['scheduled_at'],
                duration_minutes=session_data.get('duration_minutes', 60),
                status=MENTORSHIP_STATUS.SCHEDULED,
                created_at=datetime.utcnow()
            )
            
            db.session.add(session)
            db.session.commit()
            
            # Crear evento en calendario
            self._create_calendar_event_for_session(session)
            
            # Notificaciones
            self.notification_service.create_notification(
                user_id=entrepreneur.user_id,
                type=NOTIFICATION_TYPES.SESSION_SCHEDULED,
                title="Sesión programada",
                message=f"Sesión de mentoría programada para {session.scheduled_at.strftime('%d/%m/%Y %H:%M')}"
            )
            
            self.notification_service.create_notification(
                user_id=entrepreneur.assigned_mentor.user_id,
                type=NOTIFICATION_TYPES.SESSION_SCHEDULED,
                title="Nueva sesión programada",
                message=f"Sesión con {entrepreneur.user.get_full_name()} programada para {session.scheduled_at.strftime('%d/%m/%Y %H:%M')}"
            )
            
            logger.info(f"Sesión programada: {session.title} entre {entrepreneur.user.email} y {entrepreneur.assigned_mentor.user.email}")
            return session
            
        except (UserNotFoundError, BusinessRuleError, ValidationError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error programando sesión: {str(e)}")
            raise ServiceError(f"Error interno programando sesión: {str(e)}")

    # ==================== PROGRESO Y MÉTRICAS ====================

    def calculate_entrepreneur_progress(self, entrepreneur_id: int) -> Dict[str, Any]:
        """
        Calcula el progreso general del emprendedor.
        
        Args:
            entrepreneur_id: ID del emprendedor
            
        Returns:
            Dict con métricas de progreso
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id, include_relationships=True)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            # Métricas de perfil
            profile_completion = self._calculate_profile_completion(entrepreneur)
            
            # Métricas de proyecto
            project_metrics = self._calculate_project_metrics(entrepreneur)
            
            # Métricas de mentoría
            mentorship_metrics = self._calculate_mentorship_metrics(entrepreneur)
            
            # Métricas de tareas
            task_metrics = self._calculate_task_metrics(entrepreneur)
            
            # Métricas de documentos
            document_metrics = self._calculate_document_metrics(entrepreneur)
            
            # Score general
            overall_score = self._calculate_overall_score(
                profile_completion,
                project_metrics,
                mentorship_metrics,
                task_metrics,
                document_metrics
            )
            
            # Recomendaciones
            recommendations = self._generate_progress_recommendations(entrepreneur, overall_score)
            
            progress_data = {
                'overall_score': overall_score,
                'profile_completion': profile_completion,
                'project_metrics': project_metrics,
                'mentorship_metrics': mentorship_metrics,
                'task_metrics': task_metrics,
                'document_metrics': document_metrics,
                'recommendations': recommendations,
                'last_calculated': datetime.utcnow(),
                'entrepreneur_stage': entrepreneur.current_stage,
                'days_in_program': (datetime.utcnow() - entrepreneur.created_at).days
            }
            
            # Guardar métricas en el emprendedor
            entrepreneur.progress_metrics = progress_data
            entrepreneur.progress_last_calculated = datetime.utcnow()
            db.session.commit()
            
            return progress_data
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error calculando progreso: {str(e)}")
            raise ServiceError(f"Error interno calculando progreso: {str(e)}")

    def get_entrepreneur_kpis(self, entrepreneur_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Obtiene KPIs del emprendedor para un período específico.
        
        Args:
            entrepreneur_id: ID del emprendedor
            period_days: Días del período a analizar
            
        Returns:
            Dict con KPIs
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # KPIs de actividad
            sessions_attended = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.entrepreneur_id == entrepreneur_id,
                    MentorshipSession.status == MENTORSHIP_STATUS.COMPLETED,
                    MentorshipSession.completed_at >= start_date
                )
            ).count()
            
            tasks_completed = Task.query.filter(
                and_(
                    Task.assigned_to == entrepreneur.user_id,
                    Task.status == TASK_STATUS.COMPLETED,
                    Task.completed_at >= start_date
                )
            ).count()
            
            documents_uploaded = Document.query.filter(
                and_(
                    Document.uploaded_by == entrepreneur.user_id,
                    Document.created_at >= start_date
                )
            ).count()
            
            # KPIs de progreso
            project_progress = 0
            if entrepreneur.projects:
                project_progress = statistics.mean([
                    p.completion_percentage or 0 for p in entrepreneur.projects
                    if p.status == PROJECT_STATUS.ACTIVE
                ])
            
            # KPIs de engagement
            login_count = ActivityLog.query.filter(
                and_(
                    ActivityLog.user_id == entrepreneur.user_id,
                    ActivityLog.activity_type == ACTIVITY_TYPES.USER_LOGIN,
                    ActivityLog.created_at >= start_date
                )
            ).count()
            
            # KPIs de comunicación
            messages_sent = self._count_messages_sent(entrepreneur.user_id, start_date, end_date)
            
            return {
                'period_days': period_days,
                'start_date': start_date,
                'end_date': end_date,
                'activity': {
                    'sessions_attended': sessions_attended,
                    'tasks_completed': tasks_completed,
                    'documents_uploaded': documents_uploaded,
                    'login_count': login_count,
                    'messages_sent': messages_sent
                },
                'progress': {
                    'project_completion_avg': round(project_progress, 2),
                    'stage': entrepreneur.current_stage,
                    'mentor_assigned': entrepreneur.assigned_mentor_id is not None
                },
                'engagement_score': self._calculate_engagement_score(
                    sessions_attended, tasks_completed, login_count, messages_sent, period_days
                )
            }
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error obteniendo KPIs: {str(e)}")
            raise ServiceError(f"Error interno obteniendo KPIs: {str(e)}")

    # ==================== CONSULTAS Y BÚSQUEDAS ====================

    def get_entrepreneur_by_id(self, entrepreneur_id: int, include_relationships: bool = False) -> Optional[Entrepreneur]:
        """Obtiene emprendedor por ID."""
        try:
            query = Entrepreneur.query.filter_by(id=entrepreneur_id)
            
            if include_relationships:
                query = query.options(
                    joinedload(Entrepreneur.user),
                    joinedload(Entrepreneur.assigned_mentor),
                    selectinload(Entrepreneur.projects),
                    selectinload(Entrepreneur.mentorship_sessions)
                )
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo emprendedor por ID {entrepreneur_id}: {str(e)}")
            return None

    def get_entrepreneur_by_user_id(self, user_id: int) -> Optional[Entrepreneur]:
        """Obtiene emprendedor por user_id."""
        try:
            return Entrepreneur.query.filter_by(user_id=user_id).first()
        except Exception as e:
            logger.error(f"Error obteniendo emprendedor por user_id {user_id}: {str(e)}")
            return None

    def search_entrepreneurs(self, 
                           search_term: str = None,
                           stage: str = None,
                           industry: str = None,
                           program_id: int = None,
                           mentor_id: int = None,
                           has_mentor: bool = None,
                           min_progress: float = None,
                           page: int = 1,
                           per_page: int = 20,
                           sort_by: str = 'created_at',
                           sort_order: str = 'desc') -> Dict[str, Any]:
        """
        Búsqueda avanzada de emprendedores.
        
        Args:
            search_term: Término de búsqueda
            stage: Etapa del emprendedor
            industry: Industria
            program_id: ID del programa
            mentor_id: ID del mentor
            has_mentor: Si tiene mentor asignado
            min_progress: Progreso mínimo
            page: Página actual
            per_page: Elementos por página
            sort_by: Campo para ordenar
            sort_order: Orden (asc/desc)
            
        Returns:
            Dict con emprendedores y metadatos
        """
        try:
            query = Entrepreneur.query.join(User)
            
            # Filtros de búsqueda
            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        User.first_name.ilike(search_pattern),
                        User.last_name.ilike(search_pattern),
                        User.email.ilike(search_pattern),
                        Entrepreneur.business_idea.ilike(search_pattern)
                    )
                )
            
            if stage:
                query = query.filter(Entrepreneur.current_stage == stage)
            
            if industry:
                query = query.filter(Entrepreneur.industry == industry)
            
            if program_id:
                query = query.filter(Entrepreneur.current_program_id == program_id)
            
            if mentor_id:
                query = query.filter(Entrepreneur.assigned_mentor_id == mentor_id)
            
            if has_mentor is not None:
                if has_mentor:
                    query = query.filter(Entrepreneur.assigned_mentor_id.isnot(None))
                else:
                    query = query.filter(Entrepreneur.assigned_mentor_id.is_(None))
            
            # Filtro de progreso mínimo requiere subconsulta
            if min_progress is not None:
                # Simplificado para ejemplo - en producción sería más complejo
                query = query.filter(Entrepreneur.overall_progress >= min_progress)
            
            # Ordenamiento
            if sort_by == 'name':
                sort_column = User.first_name
            elif sort_by == 'progress':
                sort_column = Entrepreneur.overall_progress
            elif sort_by == 'stage':
                sort_column = Entrepreneur.current_stage
            else:
                sort_column = getattr(Entrepreneur, sort_by, Entrepreneur.created_at)
            
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Paginación
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'entrepreneurs': pagination.items,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'per_page': per_page,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev,
                'next_page': pagination.next_num if pagination.has_next else None,
                'prev_page': pagination.prev_num if pagination.has_prev else None
            }
            
        except Exception as e:
            logger.error(f"Error en búsqueda de emprendedores: {str(e)}")
            raise ServiceError(f"Error interno en búsqueda: {str(e)}")

    # ==================== REPORTES Y ANALYTICS ====================

    def generate_entrepreneur_report(self, entrepreneur_id: int, report_type: str = 'comprehensive') -> Dict[str, Any]:
        """
        Genera reporte detallado del emprendedor.
        
        Args:
            entrepreneur_id: ID del emprendedor
            report_type: Tipo de reporte (comprehensive, progress, mentorship)
            
        Returns:
            Dict con datos del reporte
        """
        try:
            entrepreneur = self.get_entrepreneur_by_id(entrepreneur_id, include_relationships=True)
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {entrepreneur_id} no encontrado")
            
            report_data = {
                'entrepreneur': {
                    'id': entrepreneur.id,
                    'name': entrepreneur.user.get_full_name(),
                    'email': entrepreneur.user.email,
                    'current_stage': entrepreneur.current_stage,
                    'created_at': entrepreneur.created_at,
                    'profile_completed': entrepreneur.profile_completed
                },
                'generated_at': datetime.utcnow(),
                'report_type': report_type
            }
            
            if report_type in ['comprehensive', 'progress']:
                # Datos de progreso
                progress_data = self.calculate_entrepreneur_progress(entrepreneur_id)
                report_data['progress'] = progress_data
                
                # KPIs
                kpis_30_days = self.get_entrepreneur_kpis(entrepreneur_id, 30)
                report_data['kpis_30_days'] = kpis_30_days
            
            if report_type in ['comprehensive', 'mentorship']:
                # Datos de mentoría
                mentorship_data = self._get_mentorship_summary(entrepreneur)
                report_data['mentorship'] = mentorship_data
            
            if report_type == 'comprehensive':
                # Proyectos
                projects_data = self._get_projects_summary(entrepreneur)
                report_data['projects'] = projects_data
                
                # Tareas
                tasks_data = self._get_tasks_summary(entrepreneur)
                report_data['tasks'] = tasks_data
                
                # Documentos
                documents_data = self._get_documents_summary(entrepreneur)
                report_data['documents'] = documents_data
            
            return report_data
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error generando reporte: {str(e)}")
            raise ServiceError(f"Error interno generando reporte: {str(e)}")

    def get_entrepreneurs_statistics(self, date_from: datetime = None, date_to: datetime = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de emprendedores.
        
        Args:
            date_from: Fecha desde
            date_to: Fecha hasta
            
        Returns:
            Dict con estadísticas
        """
        try:
            base_query = Entrepreneur.query
            
            if date_from:
                base_query = base_query.filter(Entrepreneur.created_at >= date_from)
            if date_to:
                base_query = base_query.filter(Entrepreneur.created_at <= date_to)
            
            # Estadísticas básicas
            total_entrepreneurs = base_query.count()
            active_entrepreneurs = base_query.join(User).filter(User.is_active == True).count()
            with_mentor = base_query.filter(Entrepreneur.assigned_mentor_id.isnot(None)).count()
            profile_completed = base_query.filter(Entrepreneur.profile_completed == True).count()
            
            # Por etapa
            stages_stats = db.session.query(
                Entrepreneur.current_stage,
                func.count(Entrepreneur.id).label('count')
            ).filter(
                Entrepreneur.created_at >= (date_from or datetime(2020, 1, 1)),
                Entrepreneur.created_at <= (date_to or datetime.utcnow())
            ).group_by(Entrepreneur.current_stage).all()
            
            # Por industria
            industry_stats = db.session.query(
                Entrepreneur.industry,
                func.count(Entrepreneur.id).label('count')
            ).filter(
                Entrepreneur.created_at >= (date_from or datetime(2020, 1, 1)),
                Entrepreneur.created_at <= (date_to or datetime.utcnow()),
                Entrepreneur.industry.isnot(None)
            ).group_by(Entrepreneur.industry).all()
            
            # Progreso promedio
            avg_progress = db.session.query(
                func.avg(Entrepreneur.overall_progress)
            ).filter(
                Entrepreneur.created_at >= (date_from or datetime(2020, 1, 1)),
                Entrepreneur.created_at <= (date_to or datetime.utcnow())
            ).scalar() or 0
            
            return {
                'total_entrepreneurs': total_entrepreneurs,
                'active_entrepreneurs': active_entrepreneurs,
                'with_mentor': with_mentor,
                'profile_completed': profile_completed,
                'mentor_assignment_rate': round((with_mentor / total_entrepreneurs * 100) if total_entrepreneurs > 0 else 0, 2),
                'profile_completion_rate': round((profile_completed / total_entrepreneurs * 100) if total_entrepreneurs > 0 else 0, 2),
                'average_progress': round(float(avg_progress), 2),
                'by_stage': {stage: count for stage, count in stages_stats},
                'by_industry': {industry: count for industry, count in industry_stats if industry}
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            raise ServiceError(f"Error interno obteniendo estadísticas: {str(e)}")

    # ==================== MÉTODOS PRIVADOS DE VALIDACIÓN ====================

    def _validate_profile_data(self, data: Dict[str, Any]) -> None:
        """Valida datos del perfil del emprendedor."""
        required_fields = ['business_idea', 'industry', 'target_market']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Campo requerido: {field}")
        
        if 'business_model' in data and data['business_model']:
            if not validate_business_model(data['business_model']):
                raise ValidationError("Modelo de negocio inválido")
        
        if 'market_size' in data and data['market_size']:
            if not validate_market_size(data['market_size']):
                raise ValidationError("Tamaño de mercado inválido")

    def _validate_project_data(self, data: Dict[str, Any]) -> None:
        """Valida datos del proyecto."""
        required_fields = ['name']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Campo requerido: {field}")
        
        if len(data['name'].strip()) < 3:
            raise ValidationError("El nombre del proyecto debe tener al menos 3 caracteres")

    def _validate_session_data(self, data: Dict[str, Any]) -> None:
        """Valida datos de sesión de mentoría."""
        required_fields = ['scheduled_at']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Campo requerido: {field}")
        
        # Verificar que la fecha sea futura
        if data['scheduled_at'] <= datetime.utcnow():
            raise ValidationError("La fecha de la sesión debe ser futura")
        
        # Verificar duración
        duration = data.get('duration_minutes', 60)
        if duration < 15 or duration > 240:
            raise ValidationError("La duración debe estar entre 15 y 240 minutos")

    # ==================== MÉTODOS PRIVADOS DE UTILIDAD ====================

    def _update_entrepreneur_profile(self, entrepreneur: Entrepreneur, data: Dict[str, Any]) -> None:
        """Actualiza el perfil del emprendedor."""
        updatable_fields = [
            'business_idea', 'industry', 'target_market', 'business_model',
            'revenue_model', 'market_size', 'funding_required', 'experience_years',
            'team_size', 'website', 'social_media_links'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(entrepreneur, field, data[field])

    def _create_initial_project(self, entrepreneur: Entrepreneur, profile_data: Dict[str, Any]) -> None:
        """Crea el proyecto inicial basado en el perfil."""
        project_data = {
            'name': profile_data.get('business_idea', 'Mi Emprendimiento'),
            'description': f"Proyecto inicial para {profile_data.get('business_idea', 'emprendimiento')}",
            'industry': profile_data.get('industry'),
            'target_market': profile_data.get('target_market'),
            'business_model': profile_data.get('business_model'),
            'revenue_model': profile_data.get('revenue_model'),
            'market_size': profile_data.get('market_size'),
            'funding_required': profile_data.get('funding_required')
        }
        
        self.create_project(entrepreneur.id, project_data)

    def _assign_to_appropriate_program(self, entrepreneur: Entrepreneur) -> None:
        """Asigna al emprendedor a un programa apropiado."""
        try:
            # Buscar programa activo apropiado
            appropriate_program = Program.query.filter(
                and_(
                    Program.is_active == True,
                    or_(
                        Program.target_industries.contains([entrepreneur.industry]),
                        Program.target_industries == None
                    )
                )
            ).first()
            
            if appropriate_program:
                entrepreneur.current_program_id = appropriate_program.id
                entrepreneur.program_joined_at = datetime.utcnow()
                
        except Exception as e:
            logger.warning(f"No se pudo asignar programa: {str(e)}")

    def _create_initial_project_tasks(self, project: Project) -> None:
        """Crea tareas iniciales para el proyecto."""
        initial_tasks = [
            {
                'title': 'Validar idea de negocio',
                'description': 'Realizar investigación inicial para validar la viabilidad de la idea',
                'priority': 'high',
                'due_date': datetime.utcnow() + timedelta(days=7)
            },
            {
                'title': 'Analizar mercado objetivo',
                'description': 'Investigar y definir el mercado objetivo del proyecto',
                'priority': 'medium',
                'due_date': datetime.utcnow() + timedelta(days=14)
            },
            {
                'title': 'Desarrollar MVP',
                'description': 'Crear el producto mínimo viable',
                'priority': 'medium',
                'due_date': datetime.utcnow() + timedelta(days=30)
            }
        ]
        
        for task_data in initial_tasks:
            task = Task(
                title=task_data['title'],
                description=task_data['description'],
                assigned_to=project.entrepreneur.user_id,
                project_id=project.id,
                priority=task_data['priority'],
                due_date=task_data['due_date'],
                status=TASK_STATUS.PENDING,
                created_at=datetime.utcnow()
            )
            db.session.add(task)

    def _check_mentor_availability(self, mentor: Ally) -> bool:
        """Verifica disponibilidad del mentor."""
        max_mentees = mentor.max_mentees or 5
        current_mentees = mentor.current_mentees_count or 0
        return current_mentees < max_mentees

    def _check_time_availability(self, user_id: int, scheduled_at: datetime, duration_minutes: int) -> bool:
        """Verifica disponibilidad de horario."""
        # Simplificado para ejemplo - en producción integraría con Google Calendar
        end_time = scheduled_at + timedelta(minutes=duration_minutes)
        
        conflicting_sessions = MentorshipSession.query.filter(
            and_(
                or_(
                    MentorshipSession.entrepreneur_id == user_id,
                    MentorshipSession.mentor_id == user_id
                ),
                MentorshipSession.status.in_([MENTORSHIP_STATUS.SCHEDULED, MENTORSHIP_STATUS.IN_PROGRESS]),
                or_(
                    and_(
                        MentorshipSession.scheduled_at <= scheduled_at,
                        MentorshipSession.scheduled_at + func.interval(MentorshipSession.duration_minutes, 'minute') > scheduled_at
                    ),
                    and_(
                        MentorshipSession.scheduled_at < end_time,
                        MentorshipSession.scheduled_at >= scheduled_at
                    )
                )
            )
        ).count()
        
        return conflicting_sessions == 0

    def _calculate_profile_completion(self, entrepreneur: Entrepreneur) -> Dict[str, Any]:
        """Calcula completitud del perfil."""
        required_fields = [
            'business_idea', 'industry', 'target_market', 'business_model',
            'revenue_model', 'experience_years'
        ]
        
        completed_fields = sum(1 for field in required_fields if getattr(entrepreneur, field))
        completion_percentage = (completed_fields / len(required_fields)) * 100
        
        return {
            'percentage': round(completion_percentage, 2),
            'completed_fields': completed_fields,
            'total_fields': len(required_fields),
            'missing_fields': [field for field in required_fields if not getattr(entrepreneur, field)]
        }

    def _calculate_project_metrics(self, entrepreneur: Entrepreneur) -> Dict[str, Any]:
        """Calcula métricas de proyectos."""
        projects = entrepreneur.projects
        if not projects:
            return {'count': 0, 'avg_completion': 0, 'active_count': 0}
        
        active_projects = [p for p in projects if p.status == PROJECT_STATUS.ACTIVE]
        avg_completion = statistics.mean([p.completion_percentage or 0 for p in active_projects]) if active_projects else 0
        
        return {
            'count': len(projects),
            'active_count': len(active_projects),
            'avg_completion': round(avg_completion, 2),
            'phases_distribution': self._get_project_phases_distribution(active_projects)
        }

    def _calculate_mentorship_metrics(self, entrepreneur: Entrepreneur) -> Dict[str, Any]:
        """Calcula métricas de mentoría."""
        has_mentor = entrepreneur.assigned_mentor_id is not None
        sessions = entrepreneur.mentorship_sessions if hasattr(entrepreneur, 'mentorship_sessions') else []
        
        completed_sessions = [s for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]
        avg_rating = statistics.mean([s.entrepreneur_rating for s in completed_sessions if s.entrepreneur_rating]) if completed_sessions else 0
        
        return {
            'has_mentor': has_mentor,
            'total_sessions': len(sessions),
            'completed_sessions': len(completed_sessions),
            'avg_rating': round(avg_rating, 2) if avg_rating else None,
            'last_session': max([s.scheduled_at for s in sessions]) if sessions else None
        }

    def _log_activity(self, user_id: int, activity_type: str, details: str, performed_by: int = None) -> None:
        """Registra actividad en el log."""
        try:
            activity = ActivityLog(
                user_id=user_id,
                activity_type=activity_type,
                details=details,
                performed_by=performed_by or user_id,
                created_at=datetime.utcnow()
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error registrando actividad: {str(e)}")