"""
Project Service - Ecosistema de Emprendimiento
Servicio para gestión completa de proyectos de emprendedores

Author: jusga
Version: 1.0.0
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass

from flask import current_app
from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db, cache
from app.core.exceptions import (
    ValidationError, 
    NotFoundError, 
    PermissionError, 
    BusinessLogicError
)
from app.core.constants import (
    PROJECT_STATUS, 
    PROJECT_CATEGORIES, 
    PROJECT_PRIORITY,
    NOTIFICATION_TYPES,
    USER_ROLES
)
from app.models.project import Project
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.organization import Organization
from app.models.program import Program
from app.models.document import Document
from app.models.task import Task
from app.models.activity_log import ActivityLog
from app.services.base import BaseService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.services.file_storage import FileStorageService
from app.utils.decorators import log_activity, cache_result
from app.utils.validators import validate_email, validate_phone
from app.utils.formatters import format_currency, format_percentage
from app.utils.date_utils import calculate_business_days, is_business_day


logger = logging.getLogger(__name__)


class ProjectStatus(Enum):
    """Estados del proyecto"""
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ProjectPriority(Enum):
    """Prioridades del proyecto"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProjectMetrics:
    """Métricas del proyecto"""
    completion_percentage: float
    tasks_completed: int
    tasks_total: int
    budget_used: Decimal
    budget_total: Decimal
    days_elapsed: int
    days_remaining: int
    milestone_progress: float
    risk_score: float


@dataclass
class ProjectFilter:
    """Filtros para búsqueda de proyectos"""
    status: Optional[List[str]] = None
    category: Optional[str] = None
    entrepreneur_id: Optional[int] = None
    ally_id: Optional[int] = None
    organization_id: Optional[int] = None
    program_id: Optional[int] = None
    priority: Optional[str] = None
    start_date_from: Optional[datetime] = None
    start_date_to: Optional[datetime] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    search_term: Optional[str] = None


class ProjectService(BaseService):
    """
    Servicio para gestión completa de proyectos de emprendedores
    
    Funcionalidades:
    - CRUD completo de proyectos
    - Gestión de estados y flujos de trabajo
    - Asignación de recursos y mentores
    - Seguimiento de progreso y métricas
    - Gestión de documentos y tareas
    - Notificaciones automáticas
    - Analytics y reportes
    """
    
    def __init__(self):
        super().__init__()
        self.model = Project
        self.notification_service = NotificationService()
        self.analytics_service = AnalyticsService()
        self.file_storage = FileStorageService()
    
    @log_activity("project_created")
    def create_project(
        self, 
        data: Dict[str, Any], 
        entrepreneur_id: int,
        created_by_id: int
    ) -> Project:
        """
        Crear un nuevo proyecto
        
        Args:
            data: Datos del proyecto
            entrepreneur_id: ID del emprendedor
            created_by_id: ID del usuario que crea el proyecto
            
        Returns:
            Project: Proyecto creado
            
        Raises:
            ValidationError: Si los datos no son válidos
            BusinessLogicError: Si hay errores de lógica de negocio
        """
        try:
            # Validar datos básicos
            self._validate_project_data(data)
            
            # Verificar que el emprendedor existe y está activo
            entrepreneur = self._get_active_entrepreneur(entrepreneur_id)
            
            # Verificar límites de proyectos por emprendedor
            self._check_project_limits(entrepreneur_id)
            
            # Crear el proyecto
            project = Project(
                title=data['title'],
                description=data['description'],
                category=data['category'],
                status=ProjectStatus.DRAFT.value,
                priority=data.get('priority', ProjectPriority.MEDIUM.value),
                entrepreneur_id=entrepreneur_id,
                organization_id=data.get('organization_id'),
                program_id=data.get('program_id'),
                budget_requested=Decimal(str(data.get('budget_requested', 0))),
                budget_approved=None,
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                objectives=data.get('objectives', []),
                target_market=data.get('target_market'),
                revenue_model=data.get('revenue_model'),
                competitive_analysis=data.get('competitive_analysis'),
                risk_assessment=data.get('risk_assessment'),
                success_metrics=data.get('success_metrics', []),
                tags=data.get('tags', []),
                is_public=data.get('is_public', False),
                created_by_id=created_by_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(project)
            db.session.flush()  # Para obtener el ID
            
            # Crear tareas iniciales si se proporcionan
            if data.get('initial_tasks'):
                self._create_initial_tasks(project.id, data['initial_tasks'])
            
            # Subir documentos iniciales si existen
            if data.get('documents'):
                self._upload_initial_documents(project.id, data['documents'])
            
            db.session.commit()
            
            # Enviar notificaciones
            self._send_project_created_notifications(project)
            
            # Registrar en analytics
            self.analytics_service.track_event(
                'project_created',
                {
                    'project_id': project.id,
                    'entrepreneur_id': entrepreneur_id,
                    'category': project.category,
                    'budget_requested': float(project.budget_requested)
                }
            )
            
            logger.info(f"Proyecto creado exitosamente: {project.id}")
            return project
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de base de datos al crear proyecto: {str(e)}")
            raise BusinessLogicError("Error al crear el proyecto")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error inesperado al crear proyecto: {str(e)}")
            raise
    
    def get_project(self, project_id: int, user_id: int) -> Project:
        """
        Obtener un proyecto por ID con verificación de permisos
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario que solicita
            
        Returns:
            Project: Proyecto encontrado
            
        Raises:
            NotFoundError: Si el proyecto no existe
            PermissionError: Si no tiene permisos para ver el proyecto
        """
        project = Project.query.options(
            joinedload(Project.entrepreneur),
            joinedload(Project.organization),
            joinedload(Project.program),
            joinedload(Project.assigned_allies),
            joinedload(Project.documents),
            joinedload(Project.tasks)
        ).filter_by(id=project_id).first()
        
        if not project:
            raise NotFoundError(f"Proyecto con ID {project_id} no encontrado")
        
        # Verificar permisos
        if not self._can_view_project(project, user_id):
            raise PermissionError("No tiene permisos para ver este proyecto")
        
        return project
    
    @cache_result(timeout=300)  # Cache por 5 minutos
    def get_projects(
        self, 
        filters: ProjectFilter, 
        user_id: int,
        page: int = 1, 
        per_page: int = 20,
        sort_by: str = 'created_at',
        sort_direction: str = 'desc'
    ) -> Tuple[List[Project], int]:
        """
        Obtener lista de proyectos con filtros y paginación
        
        Args:
            filters: Filtros a aplicar
            user_id: ID del usuario que solicita
            page: Número de página
            per_page: Proyectos por página
            sort_by: Campo para ordenar
            sort_direction: Dirección del ordenamiento
            
        Returns:
            Tuple[List[Project], int]: Lista de proyectos y total
        """
        query = self._build_projects_query(filters, user_id)
        
        # Aplicar ordenamiento
        if sort_direction.lower() == 'desc':
            query = query.order_by(desc(getattr(Project, sort_by)))
        else:
            query = query.order_by(asc(getattr(Project, sort_by)))
        
        # Paginación
        total = query.count()
        projects = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return projects, total
    
    @log_activity("project_updated")
    def update_project(
        self, 
        project_id: int, 
        data: Dict[str, Any], 
        updated_by_id: int
    ) -> Project:
        """
        Actualizar un proyecto existente
        
        Args:
            project_id: ID del proyecto
            data: Datos a actualizar
            updated_by_id: ID del usuario que actualiza
            
        Returns:
            Project: Proyecto actualizado
            
        Raises:
            NotFoundError: Si el proyecto no existe
            ValidationError: Si los datos no son válidos
            PermissionError: Si no tiene permisos para actualizar
        """
        try:
            project = self.get_project(project_id, updated_by_id)
            
            # Verificar permisos de edición
            if not self._can_edit_project(project, updated_by_id):
                raise PermissionError("No tiene permisos para editar este proyecto")
            
            # Validar cambio de estado si se incluye
            if 'status' in data:
                self._validate_status_change(project, data['status'])
            
            # Guardar estado anterior para comparación
            previous_status = project.status
            previous_data = self._serialize_project_for_comparison(project)
            
            # Actualizar campos permitidos
            updatable_fields = [
                'title', 'description', 'category', 'priority', 'budget_requested',
                'start_date', 'end_date', 'objectives', 'target_market',
                'revenue_model', 'competitive_analysis', 'risk_assessment',
                'success_metrics', 'tags', 'is_public', 'status'
            ]
            
            for field in updatable_fields:
                if field in data:
                    if field == 'budget_requested' and data[field] is not None:
                        setattr(project, field, Decimal(str(data[field])))
                    else:
                        setattr(project, field, data[field])
            
            project.updated_at = datetime.utcnow()
            project.updated_by_id = updated_by_id
            
            db.session.commit()
            
            # Detectar cambios significativos y enviar notificaciones
            changes = self._detect_significant_changes(previous_data, project)
            if changes:
                self._send_project_updated_notifications(project, changes)
            
            # Si cambió el estado, ejecutar acciones específicas
            if previous_status != project.status:
                self._handle_status_change(project, previous_status)
            
            logger.info(f"Proyecto actualizado exitosamente: {project_id}")
            return project
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de base de datos al actualizar proyecto: {str(e)}")
            raise BusinessLogicError("Error al actualizar el proyecto")
    
    @log_activity("project_deleted")
    def delete_project(self, project_id: int, deleted_by_id: int) -> bool:
        """
        Eliminar un proyecto (soft delete)
        
        Args:
            project_id: ID del proyecto
            deleted_by_id: ID del usuario que elimina
            
        Returns:
            bool: True si se eliminó correctamente
            
        Raises:
            NotFoundError: Si el proyecto no existe
            PermissionError: Si no tiene permisos para eliminar
            BusinessLogicError: Si no se puede eliminar por reglas de negocio
        """
        try:
            project = self.get_project(project_id, deleted_by_id)
            
            # Verificar permisos
            if not self._can_delete_project(project, deleted_by_id):
                raise PermissionError("No tiene permisos para eliminar este proyecto")
            
            # Verificar si se puede eliminar según reglas de negocio
            if not self._can_be_deleted(project):
                raise BusinessLogicError(
                    "No se puede eliminar el proyecto en su estado actual"
                )
            
            # Soft delete
            project.is_deleted = True
            project.deleted_at = datetime.utcnow()
            project.deleted_by_id = deleted_by_id
            
            # Cancelar tareas pendientes
            self._cancel_pending_tasks(project_id)
            
            db.session.commit()
            
            # Enviar notificaciones
            self._send_project_deleted_notifications(project)
            
            # Limpiar cache relacionado
            self._clear_project_cache(project_id)
            
            logger.info(f"Proyecto eliminado exitosamente: {project_id}")
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de base de datos al eliminar proyecto: {str(e)}")
            raise BusinessLogicError("Error al eliminar el proyecto")
    
    def assign_ally(
        self, 
        project_id: int, 
        ally_id: int, 
        role: str,
        assigned_by_id: int
    ) -> bool:
        """
        Asignar un aliado/mentor a un proyecto
        
        Args:
            project_id: ID del proyecto
            ally_id: ID del aliado
            role: Rol del aliado en el proyecto
            assigned_by_id: ID del usuario que asigna
            
        Returns:
            bool: True si se asignó correctamente
        """
        try:
            project = self.get_project(project_id, assigned_by_id)
            ally = Ally.query.filter_by(id=ally_id, is_active=True).first()
            
            if not ally:
                raise NotFoundError(f"Aliado con ID {ally_id} no encontrado")
            
            # Verificar que no esté ya asignado
            if ally in project.assigned_allies:
                raise ValidationError("El aliado ya está asignado a este proyecto")
            
            # Verificar disponibilidad del aliado
            if not self._check_ally_availability(ally_id):
                raise BusinessLogicError("El aliado no tiene disponibilidad")
            
            # Asignar aliado
            project.assigned_allies.append(ally)
            
            # Crear registro de asignación con rol
            assignment_data = {
                'project_id': project_id,
                'ally_id': ally_id,
                'role': role,
                'assigned_at': datetime.utcnow(),
                'assigned_by_id': assigned_by_id
            }
            
            db.session.commit()
            
            # Enviar notificaciones
            self._send_ally_assigned_notifications(project, ally, role)
            
            logger.info(f"Aliado {ally_id} asignado al proyecto {project_id}")
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error al asignar aliado: {str(e)}")
            raise BusinessLogicError("Error al asignar el aliado")
    
    def get_project_metrics(self, project_id: int, user_id: int) -> ProjectMetrics:
        """
        Obtener métricas completas de un proyecto
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario que solicita
            
        Returns:
            ProjectMetrics: Métricas del proyecto
        """
        project = self.get_project(project_id, user_id)
        
        # Calcular métricas de tareas
        total_tasks = len(project.tasks)
        completed_tasks = len([t for t in project.tasks if t.status == 'completed'])
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calcular métricas de presupuesto
        budget_used = self._calculate_budget_used(project_id)
        budget_total = project.budget_approved or project.budget_requested
        
        # Calcular métricas de tiempo
        days_elapsed = self._calculate_days_elapsed(project)
        days_remaining = self._calculate_days_remaining(project)
        
        # Calcular progreso de hitos
        milestone_progress = self._calculate_milestone_progress(project_id)
        
        # Calcular score de riesgo
        risk_score = self._calculate_risk_score(project)
        
        return ProjectMetrics(
            completion_percentage=completion_percentage,
            tasks_completed=completed_tasks,
            tasks_total=total_tasks,
            budget_used=budget_used,
            budget_total=budget_total,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            milestone_progress=milestone_progress,
            risk_score=risk_score
        )
    
    def generate_project_report(
        self, 
        project_id: int, 
        report_type: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Generar reporte detallado del proyecto
        
        Args:
            project_id: ID del proyecto
            report_type: Tipo de reporte (summary, detailed, financial, progress)
            user_id: ID del usuario que solicita
            
        Returns:
            Dict[str, Any]: Datos del reporte
        """
        project = self.get_project(project_id, user_id)
        metrics = self.get_project_metrics(project_id, user_id)
        
        base_report = {
            'project': {
                'id': project.id,
                'title': project.title,
                'status': project.status,
                'category': project.category,
                'entrepreneur': project.entrepreneur.user.full_name,
                'created_at': project.created_at,
                'start_date': project.start_date,
                'end_date': project.end_date
            },
            'metrics': metrics.__dict__,
            'generated_at': datetime.utcnow(),
            'generated_by': user_id,
            'report_type': report_type
        }
        
        if report_type == 'detailed':
            base_report.update({
                'tasks': [self._serialize_task(task) for task in project.tasks],
                'documents': [self._serialize_document(doc) for doc in project.documents],
                'activity_log': self._get_project_activity_log(project_id),
                'assigned_allies': [
                    self._serialize_ally(ally) for ally in project.assigned_allies
                ]
            })
        
        elif report_type == 'financial':
            base_report.update({
                'budget_breakdown': self._get_budget_breakdown(project_id),
                'expenses': self._get_project_expenses(project_id),
                'financial_projections': self._get_financial_projections(project_id)
            })
        
        elif report_type == 'progress':
            base_report.update({
                'milestones': self._get_project_milestones(project_id),
                'progress_timeline': self._get_progress_timeline(project_id),
                'blockers': self._get_project_blockers(project_id),
                'next_actions': self._get_next_actions(project_id)
            })
        
        return base_report
    
    # Métodos privados de validación
    def _validate_project_data(self, data: Dict[str, Any]) -> None:
        """Validar datos del proyecto"""
        required_fields = ['title', 'description', 'category']
        
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es obligatorio")
        
        if len(data['title']) < 5:
            raise ValidationError("El título debe tener al menos 5 caracteres")
        
        if len(data['description']) < 20:
            raise ValidationError("La descripción debe tener al menos 20 caracteres")
        
        if data['category'] not in PROJECT_CATEGORIES:
            raise ValidationError("Categoría de proyecto no válida")
        
        if 'budget_requested' in data:
            try:
                budget = Decimal(str(data['budget_requested']))
                if budget < 0:
                    raise ValidationError("El presupuesto no puede ser negativo")
            except (ValueError, TypeError):
                raise ValidationError("Presupuesto debe ser un número válido")
        
        # Validar fechas
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise ValidationError(
                    "La fecha de inicio debe ser anterior a la fecha de fin"
                )
    
    def _get_active_entrepreneur(self, entrepreneur_id: int) -> Entrepreneur:
        """Obtener emprendedor activo"""
        entrepreneur = Entrepreneur.query.filter_by(
            id=entrepreneur_id, 
            is_active=True
        ).first()
        
        if not entrepreneur:
            raise NotFoundError(f"Emprendedor con ID {entrepreneur_id} no encontrado")
        
        return entrepreneur
    
    def _check_project_limits(self, entrepreneur_id: int) -> None:
        """Verificar límites de proyectos por emprendedor"""
        active_projects = Project.query.filter_by(
            entrepreneur_id=entrepreneur_id,
            is_deleted=False
        ).filter(
            Project.status.in_([
                ProjectStatus.DRAFT.value,
                ProjectStatus.UNDER_REVIEW.value,
                ProjectStatus.APPROVED.value,
                ProjectStatus.IN_PROGRESS.value
            ])
        ).count()
        
        max_projects = current_app.config.get('MAX_PROJECTS_PER_ENTREPRENEUR', 5)
        
        if active_projects >= max_projects:
            raise BusinessLogicError(
                f"El emprendedor ya tiene {active_projects} proyectos activos. "
                f"Máximo permitido: {max_projects}"
            )
    
    def _can_view_project(self, project: Project, user_id: int) -> bool:
        """Verificar si el usuario puede ver el proyecto"""
        user = User.query.get(user_id)
        
        if not user:
            return False
        
        # Administradores pueden ver todo
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # El emprendedor dueño puede ver su proyecto
        if project.entrepreneur.user_id == user_id:
            return True
        
        # Aliados asignados pueden ver el proyecto
        if user.role == USER_ROLES.ALLY:
            ally = Ally.query.filter_by(user_id=user_id).first()
            if ally and ally in project.assigned_allies:
                return True
        
        # Clientes de la organización pueden ver proyectos públicos
        if project.is_public and user.role == USER_ROLES.CLIENT:
            return True
        
        return False
    
    def _can_edit_project(self, project: Project, user_id: int) -> bool:
        """Verificar si el usuario puede editar el proyecto"""
        user = User.query.get(user_id)
        
        # Administradores pueden editar todo
        if user.role == USER_ROLES.ADMIN:
            return True
        
        # El emprendedor dueño puede editar su proyecto
        if project.entrepreneur.user_id == user_id:
            return True
        
        # Aliados asignados pueden editar ciertos campos
        if user.role == USER_ROLES.ALLY:
            ally = Ally.query.filter_by(user_id=user_id).first()
            if ally and ally in project.assigned_allies:
                return True
        
        return False
    
    def _build_projects_query(self, filters: ProjectFilter, user_id: int):
        """Construir query con filtros aplicados"""
        query = Project.query.filter_by(is_deleted=False)
        
        # Aplicar filtros de permisos
        user = User.query.get(user_id)
        if user.role != USER_ROLES.ADMIN:
            if user.role == USER_ROLES.ENTREPRENEUR:
                entrepreneur = Entrepreneur.query.filter_by(user_id=user_id).first()
                if entrepreneur:
                    query = query.filter_by(entrepreneur_id=entrepreneur.id)
            elif user.role == USER_ROLES.ALLY:
                ally = Ally.query.filter_by(user_id=user_id).first()
                if ally:
                    query = query.filter(Project.assigned_allies.contains(ally))
            else:
                query = query.filter_by(is_public=True)
        
        # Aplicar filtros específicos
        if filters.status:
            query = query.filter(Project.status.in_(filters.status))
        
        if filters.category:
            query = query.filter_by(category=filters.category)
        
        if filters.entrepreneur_id:
            query = query.filter_by(entrepreneur_id=filters.entrepreneur_id)
        
        if filters.organization_id:
            query = query.filter_by(organization_id=filters.organization_id)
        
        if filters.program_id:
            query = query.filter_by(program_id=filters.program_id)
        
        if filters.priority:
            query = query.filter_by(priority=filters.priority)
        
        if filters.start_date_from:
            query = query.filter(Project.start_date >= filters.start_date_from)
        
        if filters.start_date_to:
            query = query.filter(Project.start_date <= filters.start_date_to)
        
        if filters.budget_min:
            query = query.filter(Project.budget_requested >= filters.budget_min)
        
        if filters.budget_max:
            query = query.filter(Project.budget_requested <= filters.budget_max)
        
        if filters.search_term:
            search = f"%{filters.search_term}%"
            query = query.filter(
                or_(
                    Project.title.ilike(search),
                    Project.description.ilike(search),
                    Project.target_market.ilike(search)
                )
            )
        
        return query
    
    # Métodos para notificaciones
    def _send_project_created_notifications(self, project: Project) -> None:
        """Enviar notificaciones de proyecto creado"""
        # Notificar al emprendedor
        self.notification_service.send_notification(
            user_id=project.entrepreneur.user_id,
            type=NOTIFICATION_TYPES.PROJECT_CREATED,
            title="Proyecto creado exitosamente",
            message=f"Tu proyecto '{project.title}' ha sido creado y está en revisión.",
            data={'project_id': project.id}
        )
        
        # Notificar a administradores para revisión
        admin_users = User.query.filter_by(role=USER_ROLES.ADMIN, is_active=True).all()
        for admin in admin_users:
            self.notification_service.send_notification(
                user_id=admin.id,
                type=NOTIFICATION_TYPES.PROJECT_REVIEW_NEEDED,
                title="Nuevo proyecto para revisión",
                message=f"El proyecto '{project.title}' necesita revisión.",
                data={'project_id': project.id}
            )
    
    def _send_project_updated_notifications(
        self, 
        project: Project, 
        changes: List[str]
    ) -> None:
        """Enviar notificaciones de proyecto actualizado"""
        # Notificar a aliados asignados
        for ally in project.assigned_allies:
            self.notification_service.send_notification(
                user_id=ally.user_id,
                type=NOTIFICATION_TYPES.PROJECT_UPDATED,
                title="Proyecto actualizado",
                message=f"El proyecto '{project.title}' ha sido actualizado. Cambios: {', '.join(changes)}",
                data={'project_id': project.id, 'changes': changes}
            )
    
    # Métodos de cálculo de métricas
    def _calculate_budget_used(self, project_id: int) -> Decimal:
        """Calcular presupuesto utilizado"""
        # Implementar lógica para calcular gastos del proyecto
        # Esto se integraría con un sistema de contabilidad
        return Decimal('0.00')
    
    def _calculate_days_elapsed(self, project: Project) -> int:
        """Calcular días transcurridos"""
        if not project.start_date:
            return 0
        
        start_date = project.start_date
        current_date = datetime.utcnow().date()
        
        return calculate_business_days(start_date, current_date)
    
    def _calculate_days_remaining(self, project: Project) -> int:
        """Calcular días restantes"""
        if not project.end_date:
            return 0
        
        current_date = datetime.utcnow().date()
        end_date = project.end_date
        
        if current_date >= end_date:
            return 0
        
        return calculate_business_days(current_date, end_date)
    
    def _calculate_risk_score(self, project: Project) -> float:
        """Calcular score de riesgo del proyecto"""
        risk_factors = []
        
        # Factor de tiempo
        if project.end_date:
            days_remaining = self._calculate_days_remaining(project)
            if days_remaining < 30:
                risk_factors.append(0.3)
        
        # Factor de presupuesto
        if project.budget_approved:
            budget_used = self._calculate_budget_used(project.id)
            usage_percentage = float(budget_used / project.budget_approved)
            if usage_percentage > 0.8:
                risk_factors.append(0.4)
        
        # Factor de tareas
        overdue_tasks = len([
            t for t in project.tasks 
            if t.due_date and t.due_date < datetime.utcnow().date() 
            and t.status != 'completed'
        ])
        if overdue_tasks > 0:
            risk_factors.append(min(overdue_tasks * 0.1, 0.3))
        
        return min(sum(risk_factors), 1.0)
    
    # Métodos auxiliares
    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        """Serializar tarea para reportes"""
        return {
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'priority': task.priority,
            'due_date': task.due_date,
            'completed_at': task.completed_at
        }
    
    def _serialize_document(self, document: Document) -> Dict[str, Any]:
        """Serializar documento para reportes"""
        return {
            'id': document.id,
            'name': document.name,
            'type': document.type,
            'size': document.size,
            'uploaded_at': document.uploaded_at
        }
    
    def _serialize_ally(self, ally: Ally) -> Dict[str, Any]:
        """Serializar aliado para reportes"""
        return {
            'id': ally.id,
            'name': ally.user.full_name,
            'email': ally.user.email,
            'expertise': ally.expertise,
            'company': ally.company
        }
    
    def _clear_project_cache(self, project_id: int) -> None:
        """Limpiar cache relacionado con el proyecto"""
        cache_keys = [
            f"project:{project_id}",
            f"project_metrics:{project_id}",
            f"project_tasks:{project_id}"
        ]
        
        for key in cache_keys:
            cache.delete(key)


# Instancia del servicio para uso global
project_service = ProjectService()