"""
API V1 - Endpoints para gestión de proyectos de emprendimiento
Autor: Sistema de Ecosistema de Emprendimiento
Versión: 1.0
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from werkzeug.exceptions import BadRequest, NotFound, Forbidden, Conflict

# Imports internos
from app.models.project import Project, ProjectStatus, ProjectPhase
from app.models.entrepreneur import Entrepreneur
from app.models.user import User
from app.models.organization import Organization
from app.models.program import Program
from app.models.activity_log import ActivityLog
from app.services.project_service import ProjectService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.core.permissions import require_permission, check_project_access
from app.core.exceptions import ValidationException, BusinessException
from app.utils.decorators import api_response, rate_limit, log_activity
from app.utils.validators import validate_uuid, validate_date_range
from app.extensions import db, cache

# Blueprint configuration
projects_bp = Blueprint('projects_api', __name__, url_prefix='/api/v1/projects')

# Schemas para validación y serialización
class ProjectCreateSchema(Schema):
    """Schema para creación de proyectos"""
    name = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    description = fields.Str(required=True, validate=validate.Length(min=10, max=2000))
    entrepreneur_id = fields.UUID(required=True)
    organization_id = fields.UUID(allow_none=True)
    program_id = fields.UUID(allow_none=True)
    category = fields.Str(required=True, validate=validate.OneOf([
        'technology', 'healthcare', 'education', 'fintech', 'ecommerce',
        'sustainability', 'agriculture', 'manufacturing', 'services', 'other'
    ]))
    industry = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    stage = fields.Str(required=True, validate=validate.OneOf([
        'idea', 'validation', 'prototype', 'mvp', 'growth', 'scaling'
    ]))
    budget_requested = fields.Decimal(allow_none=True, places=2)
    currency = fields.Str(missing='USD', validate=validate.OneOf(['USD', 'EUR', 'COP', 'MXN']))
    funding_goal = fields.Decimal(allow_none=True, places=2)
    expected_duration_months = fields.Int(validate=validate.Range(min=1, max=120))
    target_market = fields.Str(validate=validate.Length(min=5, max=500))
    competitive_advantage = fields.Str(validate=validate.Length(min=10, max=1000))
    team_size = fields.Int(validate=validate.Range(min=1, max=100))
    website_url = fields.URL(allow_none=True)
    social_media = fields.Dict(missing={})
    tags = fields.List(fields.Str(), missing=[])
    is_public = fields.Bool(missing=True)
    allow_collaboration = fields.Bool(missing=True)
    
class ProjectUpdateSchema(Schema):
    """Schema para actualización de proyectos"""
    name = fields.Str(validate=validate.Length(min=3, max=100))
    description = fields.Str(validate=validate.Length(min=10, max=2000))
    category = fields.Str(validate=validate.OneOf([
        'technology', 'healthcare', 'education', 'fintech', 'ecommerce',
        'sustainability', 'agriculture', 'manufacturing', 'services', 'other'
    ]))
    industry = fields.Str(validate=validate.Length(min=2, max=50))
    stage = fields.Str(validate=validate.OneOf([
        'idea', 'validation', 'prototype', 'mvp', 'growth', 'scaling'
    ]))
    status = fields.Str(validate=validate.OneOf([
        'draft', 'active', 'on_hold', 'completed', 'cancelled'
    ]))
    budget_requested = fields.Decimal(places=2)
    funding_goal = fields.Decimal(places=2)
    expected_duration_months = fields.Int(validate=validate.Range(min=1, max=120))
    target_market = fields.Str(validate=validate.Length(min=5, max=500))
    competitive_advantage = fields.Str(validate=validate.Length(min=10, max=1000))
    team_size = fields.Int(validate=validate.Range(min=1, max=100))
    website_url = fields.URL(allow_none=True)
    social_media = fields.Dict()
    tags = fields.List(fields.Str())
    is_public = fields.Bool()
    allow_collaboration = fields.Bool()
    progress_percentage = fields.Int(validate=validate.Range(min=0, max=100))
    
class ProjectFilterSchema(Schema):
    """Schema para filtros de búsqueda"""
    page = fields.Int(missing=1, validate=validate.Range(min=1))
    per_page = fields.Int(missing=20, validate=validate.Range(min=1, max=100))
    search = fields.Str()
    category = fields.Str()
    industry = fields.Str()
    stage = fields.Str()
    status = fields.Str()
    entrepreneur_id = fields.UUID()
    organization_id = fields.UUID()
    program_id = fields.UUID()
    is_public = fields.Bool()
    min_budget = fields.Decimal(places=2)
    max_budget = fields.Decimal(places=2)
    created_after = fields.DateTime()
    created_before = fields.DateTime()
    sort_by = fields.Str(missing='created_at', validate=validate.OneOf([
        'created_at', 'updated_at', 'name', 'stage', 'progress_percentage'
    ]))
    sort_order = fields.Str(missing='desc', validate=validate.OneOf(['asc', 'desc']))

class ProjectResponseSchema(Schema):
    """Schema para respuesta de proyecto"""
    id = fields.UUID()
    name = fields.Str()
    description = fields.Str()
    category = fields.Str()
    industry = fields.Str()
    stage = fields.Str()
    status = fields.Str()
    phase = fields.Str()
    progress_percentage = fields.Int()
    budget_requested = fields.Decimal(places=2)
    currency = fields.Str()
    funding_goal = fields.Decimal(places=2)
    funding_raised = fields.Decimal(places=2)
    expected_duration_months = fields.Int()
    target_market = fields.Str()
    competitive_advantage = fields.Str()
    team_size = fields.Int()
    website_url = fields.URL()
    social_media = fields.Dict()
    tags = fields.List(fields.Str())
    is_public = fields.Bool()
    allow_collaboration = fields.Bool()
    entrepreneur = fields.Nested('EntrepreneurBasicSchema')
    organization = fields.Nested('OrganizationBasicSchema', allow_none=True)
    program = fields.Nested('ProgramBasicSchema', allow_none=True)
    metrics = fields.Dict()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


# Servicios
project_service = ProjectService()
notification_service = NotificationService()
analytics_service = AnalyticsService()

# Schemas instances
project_create_schema = ProjectCreateSchema()
project_update_schema = ProjectUpdateSchema()
project_filter_schema = ProjectFilterSchema()
project_response_schema = ProjectResponseSchema()


@projects_bp.route('', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)  # 100 requests per hour
@api_response
def get_projects():
    """
    Obtener lista de proyectos con filtros y paginación
    
    Returns:
        JSON: Lista paginada de proyectos
    """
    try:
        # Validar parámetros de consulta
        filter_data = project_filter_schema.load(request.args)
        
        # Construir filtros basados en permisos del usuario
        filters = _build_project_filters(filter_data)
        
        # Obtener proyectos con paginación
        projects_query = project_service.get_projects_query(filters)
        
        # Aplicar paginación
        page = filter_data['page']
        per_page = filter_data['per_page']
        projects_paginated = projects_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Serializar resultados
        projects_data = []
        for project in projects_paginated.items:
            project_dict = project_response_schema.dump(project)
            # Agregar métricas específicas si el usuario tiene permisos
            if check_project_access(current_user, project, 'read_metrics'):
                project_dict['metrics'] = project_service.get_project_metrics(project.id)
            projects_data.append(project_dict)
        
        # Construir respuesta
        response_data = {
            'projects': projects_data,
            'pagination': {
                'page': projects_paginated.page,
                'pages': projects_paginated.pages,
                'per_page': projects_paginated.per_page,
                'total': projects_paginated.total,
                'has_next': projects_paginated.has_next,
                'has_prev': projects_paginated.has_prev
            },
            'filters_applied': filter_data
        }
        
        return response_data, 200
        
    except ValidationError as e:
        raise BadRequest(f"Parámetros de consulta inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error al obtener proyectos: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>', methods=['GET'])
@login_required
@rate_limit(requests=200, window=3600)
@api_response
def get_project(project_id: uuid.UUID):
    """
    Obtener detalles de un proyecto específico
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Detalles completos del proyecto
    """
    try:
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos de acceso
        if not check_project_access(current_user, project, 'read'):
            raise Forbidden("No tienes permisos para ver este proyecto")
        
        # Serializar proyecto
        project_data = project_response_schema.dump(project)
        
        # Agregar información adicional según permisos
        if check_project_access(current_user, project, 'read_metrics'):
            project_data['metrics'] = project_service.get_project_metrics(project_id)
            project_data['timeline'] = project_service.get_project_timeline(project_id)
            project_data['milestones'] = project_service.get_project_milestones(project_id)
        
        if check_project_access(current_user, project, 'read_financial'):
            project_data['financial_data'] = project_service.get_project_financial_data(project_id)
        
        # Registrar actividad
        ActivityLog.log_activity(
            user_id=current_user.id,
            action='view_project',
            resource_type='project',
            resource_id=project_id,
            metadata={'project_name': project.name}
        )
        
        return project_data, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('', methods=['POST'])
@login_required
@require_permission('create_project')
@rate_limit(requests=10, window=3600)
@log_activity('create_project')
@api_response
def create_project():
    """
    Crear un nuevo proyecto
    
    Returns:
        JSON: Proyecto creado
    """
    try:
        # Validar datos de entrada
        project_data = project_create_schema.load(request.get_json())
        
        # Verificar que el emprendedor existe y el usuario tiene permisos
        entrepreneur = Entrepreneur.query.get(project_data['entrepreneur_id'])
        if not entrepreneur:
            raise NotFound("Emprendedor no encontrado")
        
        # Verificar permisos para crear proyecto para este emprendedor
        if not _can_create_project_for_entrepreneur(current_user, entrepreneur):
            raise Forbidden("No tienes permisos para crear proyectos para este emprendedor")
        
        # Verificar límites del emprendedor
        if not project_service.can_create_project(entrepreneur.id):
            raise Conflict("El emprendedor ha alcanzado el límite de proyectos activos")
        
        # Crear proyecto
        project = project_service.create_project(
            project_data=project_data,
            created_by=current_user.id
        )
        
        # Enviar notificación
        notification_service.send_project_created_notification(
            project_id=project.id,
            recipient_ids=[entrepreneur.user_id]
        )
        
        # Registrar en analytics
        analytics_service.track_project_creation(project.id, current_user.id)
        
        # Serializar respuesta
        project_response = project_response_schema.dump(project)
        
        return {
            'message': 'Proyecto creado exitosamente',
            'project': project_response
        }, 201
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden, Conflict) as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al crear proyecto: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>', methods=['PUT'])
@login_required
@rate_limit(requests=20, window=3600)
@log_activity('update_project')
@api_response
def update_project(project_id: uuid.UUID):
    """
    Actualizar un proyecto existente
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Proyecto actualizado
    """
    try:
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos
        if not check_project_access(current_user, project, 'update'):
            raise Forbidden("No tienes permisos para actualizar este proyecto")
        
        # Validar datos de actualización
        update_data = project_update_schema.load(request.get_json())
        
        # Verificar cambios de estado válidos
        if 'status' in update_data:
            if not project_service.can_change_status(project, update_data['status']):
                raise BadRequest(f"No se puede cambiar el estado a {update_data['status']}")
        
        # Actualizar proyecto
        updated_project = project_service.update_project(
            project_id=project_id,
            update_data=update_data,
            updated_by=current_user.id
        )
        
        # Enviar notificaciones si hay cambios significativos
        if _has_significant_changes(update_data):
            notification_service.send_project_updated_notification(
                project_id=project_id,
                changes=update_data,
                updated_by=current_user.id
            )
        
        # Registrar en analytics
        analytics_service.track_project_update(project_id, current_user.id, update_data)
        
        # Serializar respuesta
        project_response = project_response_schema.dump(updated_project)
        
        return {
            'message': 'Proyecto actualizado exitosamente',
            'project': project_response
        }, 200
        
    except ValidationError as e:
        raise BadRequest(f"Datos inválidos: {e.messages}")
    except (NotFound, Forbidden) as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al actualizar proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>', methods=['DELETE'])
@login_required
@require_permission('delete_project')
@rate_limit(requests=5, window=3600)
@log_activity('delete_project')
@api_response
def delete_project(project_id: uuid.UUID):
    """
    Eliminar un proyecto (soft delete)
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Confirmación de eliminación
    """
    try:
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos
        if not check_project_access(current_user, project, 'delete'):
            raise Forbidden("No tienes permisos para eliminar este proyecto")
        
        # Verificar si se puede eliminar
        if not project_service.can_delete_project(project_id):
            raise Conflict("No se puede eliminar el proyecto en su estado actual")
        
        # Eliminar proyecto (soft delete)
        project_service.soft_delete_project(
            project_id=project_id,
            deleted_by=current_user.id
        )
        
        # Enviar notificaciones
        notification_service.send_project_deleted_notification(
            project_id=project_id,
            deleted_by=current_user.id
        )
        
        # Registrar en analytics
        analytics_service.track_project_deletion(project_id, current_user.id)
        
        return {
            'message': 'Proyecto eliminado exitosamente'
        }, 200
        
    except (NotFound, Forbidden, Conflict) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al eliminar proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>/status', methods=['PATCH'])
@login_required
@rate_limit(requests=30, window=3600)
@log_activity('change_project_status')
@api_response
def change_project_status(project_id: uuid.UUID):
    """
    Cambiar el estado de un proyecto
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Proyecto con estado actualizado
    """
    try:
        # Validar datos
        data = request.get_json()
        if not data or 'status' not in data:
            raise BadRequest("Estado requerido")
        
        new_status = data['status']
        comment = data.get('comment', '')
        
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos
        if not check_project_access(current_user, project, 'change_status'):
            raise Forbidden("No tienes permisos para cambiar el estado de este proyecto")
        
        # Cambiar estado
        updated_project = project_service.change_project_status(
            project_id=project_id,
            new_status=new_status,
            comment=comment,
            changed_by=current_user.id
        )
        
        # Enviar notificaciones
        notification_service.send_project_status_changed_notification(
            project_id=project_id,
            old_status=project.status,
            new_status=new_status,
            changed_by=current_user.id
        )
        
        # Serializar respuesta
        project_response = project_response_schema.dump(updated_project)
        
        return {
            'message': f'Estado del proyecto cambiado a {new_status}',
            'project': project_response
        }, 200
        
    except (BadRequest, NotFound, Forbidden) as e:
        raise e
    except BusinessException as e:
        raise BadRequest(str(e))
    except Exception as e:
        current_app.logger.error(f"Error al cambiar estado del proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>/metrics', methods=['GET'])
@login_required
@rate_limit(requests=50, window=3600)
@api_response
def get_project_metrics(project_id: uuid.UUID):
    """
    Obtener métricas detalladas de un proyecto
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Métricas del proyecto
    """
    try:
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos
        if not check_project_access(current_user, project, 'read_metrics'):
            raise Forbidden("No tienes permisos para ver las métricas de este proyecto")
        
        # Obtener métricas
        metrics = project_service.get_detailed_project_metrics(project_id)
        
        return {
            'project_id': project_id,
            'metrics': metrics,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener métricas del proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('/<uuid:project_id>/timeline', methods=['GET'])
@login_required
@rate_limit(requests=50, window=3600)
@api_response
def get_project_timeline(project_id: uuid.UUID):
    """
    Obtener línea de tiempo de un proyecto
    
    Args:
        project_id: UUID del proyecto
        
    Returns:
        JSON: Timeline del proyecto
    """
    try:
        # Obtener proyecto
        project = project_service.get_project_by_id(project_id)
        if not project:
            raise NotFound("Proyecto no encontrado")
        
        # Verificar permisos
        if not check_project_access(current_user, project, 'read'):
            raise Forbidden("No tienes permisos para ver este proyecto")
        
        # Obtener timeline
        timeline = project_service.get_project_timeline(project_id)
        
        return {
            'project_id': project_id,
            'timeline': timeline
        }, 200
        
    except (NotFound, Forbidden) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error al obtener timeline del proyecto {project_id}: {str(e)}")
        raise


@projects_bp.route('/search', methods=['GET'])
@login_required
@rate_limit(requests=100, window=3600)
@api_response
def search_projects():
    """
    Búsqueda avanzada de proyectos
    
    Returns:
        JSON: Resultados de búsqueda
    """
    try:
        search_query = request.args.get('q', '').strip()
        if not search_query:
            raise BadRequest("Consulta de búsqueda requerida")
        
        # Filtros adicionales
        filters = project_filter_schema.load(request.args)
        
        # Realizar búsqueda
        search_results = project_service.search_projects(
            query=search_query,
            filters=filters,
            user=current_user
        )
        
        # Serializar resultados
        projects_data = [project_response_schema.dump(project) for project in search_results['projects']]
        
        return {
            'query': search_query,
            'projects': projects_data,
            'total_found': search_results['total'],
            'search_time_ms': search_results['search_time_ms']
        }, 200
        
    except (BadRequest,) as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"Error en búsqueda de proyectos: {str(e)}")
        raise


@projects_bp.route('/stats', methods=['GET'])
@login_required
@require_permission('view_project_stats')
@rate_limit(requests=20, window=3600)
@cache.cached(timeout=300)  # Cache for 5 minutes
@api_response
def get_projects_statistics():
    """
    Obtener estadísticas generales de proyectos
    
    Returns:
        JSON: Estadísticas de proyectos
    """
    try:
        # Obtener estadísticas
        stats = analytics_service.get_projects_statistics(user=current_user)
        
        return {
            'statistics': stats,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas de proyectos: {str(e)}")
        raise


# Funciones auxiliares privadas

def _build_project_filters(filter_data: Dict) -> Dict:
    """Construir filtros basados en permisos del usuario"""
    filters = filter_data.copy()
    
    # Si no es admin, solo mostrar proyectos públicos o propios
    if not current_user.has_permission('view_all_projects'):
        if current_user.role == 'entrepreneur':
            filters['entrepreneur_id'] = current_user.entrepreneur.id
        elif current_user.role == 'ally':
            # Aliados pueden ver proyectos de sus emprendedores asignados
            entrepreneur_ids = [e.id for e in current_user.ally.assigned_entrepreneurs]
            filters['entrepreneur_ids'] = entrepreneur_ids
        else:
            # Solo proyectos públicos para otros roles
            filters['is_public'] = True
    
    return filters


def _can_create_project_for_entrepreneur(user: User, entrepreneur: Entrepreneur) -> bool:
    """Verificar si el usuario puede crear proyectos para el emprendedor"""
    if user.has_permission('create_project_any'):
        return True
    
    if user.role == 'entrepreneur' and user.entrepreneur.id == entrepreneur.id:
        return True
    
    if user.role == 'ally' and entrepreneur in user.ally.assigned_entrepreneurs:
        return True
    
    return False


def _has_significant_changes(update_data: Dict) -> bool:
    """Verificar si los cambios son significativos para notificación"""
    significant_fields = ['status', 'stage', 'progress_percentage', 'budget_requested']
    return any(field in update_data for field in significant_fields)


# Manejo de errores específicos del blueprint
@projects_bp.errorhandler(ValidationException)
def handle_validation_exception(e):
    return jsonify({
        'error': 'Validation Error',
        'message': str(e),
        'status_code': 400
    }), 400


@projects_bp.errorhandler(BusinessException)
def handle_business_exception(e):
    return jsonify({
        'error': 'Business Logic Error',
        'message': str(e),
        'status_code': 400
    }), 400


# Registro de rutas adicionales
@projects_bp.before_request
def before_request():
    """Ejecutar antes de cada request al blueprint"""
    # Verificar que el usuario esté autenticado
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Log de request para audit
    current_app.logger.info(
        f"API Request: {request.method} {request.path} by user {current_user.id}"
    )


@projects_bp.after_request
def after_request(response):
    """Ejecutar después de cada request al blueprint"""
    # Agregar headers de seguridad
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    
    return response