"""
API v1 Clients/Stakeholders Endpoints
====================================

Este módulo implementa todos los endpoints específicos para clientes/stakeholders en la API v1,
incluyendo gestión de perfiles, seguimiento de emprendimientos, análisis de impacto,
generación de reportes, y herramientas de evaluación.

Funcionalidades:
- CRUD completo de perfiles de clientes/stakeholders
- Seguimiento de emprendimientos y proyectos
- Análisis de impacto y ROI
- Generación de reportes personalizados
- Dashboard de métricas y KPIs
- Sistema de evaluación y scoring
- Gestión de portfolio de inversiones
- Herramientas de due diligence
"""

from flask import Blueprint, request, jsonify, current_app, g, send_file
from flask_restful import Resource, Api
from sqlalchemy import or_, and_, func, desc, asc, case
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from decimal import Decimal
import json
import io
import xlsxwriter

from app.extensions import db, limiter
from app.models.user import User
from app.models.client import Client
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.relationship import Relationship, RelationshipType, RelationshipStatus
from app.models.analytics import AnalyticsMetric, MetricType, MetricCategory
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError,
    ResourceNotFoundError,
    BusinessLogicError
)
from app.services.client_service import ClientService
from app.services.analytics_service import AnalyticsService
from app.services.report_service import ReportService
from app.services.email import EmailService
from app.utils.decorators import validate_json, log_activity
from app.api.middleware.auth import api_auth_required, get_current_user
from app.api import paginated_response, api_response
from app.api.v1 import APIv1Validator


# Crear blueprint para clients
clients_bp = Blueprint('clients', __name__)
api = Api(clients_bp)


class ClientConfig:
    """Configuración específica para clientes/stakeholders"""
    
    # Tipos de clientes
    CLIENT_TYPES = [
        'investor', 'corporate_partner', 'government', 'ngo', 'foundation',
        'academic_institution', 'accelerator', 'incubator', 'venture_capital',
        'private_equity', 'family_office', 'angel_investor', 'strategic_partner'
    ]
    
    # Áreas de interés
    INTEREST_AREAS = [
        'technology', 'healthcare', 'fintech', 'edtech', 'cleantech', 'biotech',
        'agtech', 'foodtech', 'mobility', 'logistics', 'real_estate', 'retail',
        'manufacturing', 'energy', 'sustainability', 'social_impact', 'b2b', 'b2c'
    ]
    
    # Etapas de inversión preferidas
    INVESTMENT_STAGES = [
        'pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'growth',
        'late_stage', 'ipo_ready', 'any_stage'
    ]
    
    # Tipos de engagement
    ENGAGEMENT_TYPES = [
        'financial_investment', 'strategic_partnership', 'mentorship',
        'market_access', 'technology_transfer', 'pilot_programs',
        'acceleration_programs', 'grants', 'competitions', 'research_collaboration'
    ]
    
    # Métricas de evaluación
    EVALUATION_METRICS = [
        'financial_performance', 'market_traction', 'team_quality',
        'product_innovation', 'scalability', 'sustainability_impact',
        'social_impact', 'technology_readiness', 'market_size', 'competitive_advantage'
    ]
    
    # Estados de seguimiento
    TRACKING_STATUS = [
        'prospecting', 'under_evaluation', 'due_diligence', 'negotiation',
        'active_engagement', 'monitoring', 'exit', 'closed'
    ]


class ClientsListResource(Resource):
    """Endpoint para listar y crear clientes/stakeholders"""
    
    @api_auth_required
    def get(self):
        """
        Listar clientes/stakeholders con filtros especializados
        
        Query Parameters:
            page: Número de página
            per_page: Elementos por página
            search: Búsqueda en nombre/organización
            client_type: Filtrar por tipo de cliente
            interest_area: Filtrar por área de interés
            investment_stage: Filtrar por etapa de inversión
            location: Filtrar por ubicación
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            engagement_type: Tipo de engagement
            investment_range_min: Rango mínimo de inversión
            investment_range_max: Rango máximo de inversión
            active_engagements: Solo clientes con engagements activos
            sort_by: Campo para ordenar
        
        Returns:
            Lista paginada de clientes/stakeholders
        """
        current_user = get_current_user()
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        page, per_page = APIv1Validator.validate_pagination_params(page, per_page)
        
        # Construir query base con joins optimizados
        query = db.session.query(Client).join(User).options(
            joinedload(Client.user),
            joinedload(Client.organization),
            joinedload(Client.current_programs)
        )
        
        # Filtro base: solo clientes activos
        query = query.filter(User.is_active == True)
        
        # Aplicar filtros de acceso
        if not current_user.is_admin():
            # No admin: solo perfiles públicos o de su organización
            query = query.filter(
                or_(
                    User.is_public_profile == True,
                    User.organization_id == getattr(current_user, 'organization_id', None)
                )
            )
        
        # Filtros específicos
        search = request.args.get('search', '').strip()
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                Client.organization.ilike(f'%{search}%'),
                Client.role.ilike(f'%{search}%'),
                Client.bio.ilike(f'%{search}%'),
                func.concat(User.first_name, ' ', User.last_name).ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtro por tipo de cliente
        client_type = request.args.get('client_type')
        if client_type and client_type in ClientConfig.CLIENT_TYPES:
            query = query.filter(Client.client_type == client_type)
        
        # Filtro por área de interés
        interest_area = request.args.get('interest_area')
        if interest_area and interest_area in ClientConfig.INTEREST_AREAS:
            query = query.filter(Client.interest_areas.contains([interest_area]))
        
        # Filtro por etapa de inversión
        investment_stage = request.args.get('investment_stage')
        if investment_stage and investment_stage in ClientConfig.INVESTMENT_STAGES:
            query = query.filter(Client.preferred_investment_stages.contains([investment_stage]))
        
        # Filtro por ubicación
        location = request.args.get('location')
        if location:
            query = query.filter(
                or_(
                    User.city.ilike(f'%{location}%'),
                    User.country.ilike(f'%{location}%')
                )
            )
        
        # Filtro por organización
        organization_id = request.args.get('organization_id', type=int)
        if organization_id:
            query = query.filter(User.organization_id == organization_id)
        
        # Filtro por programa
        program_id = request.args.get('program_id', type=int)
        if program_id:
            query = query.filter(Client.current_programs.any(Program.id == program_id))
        
        # Filtro por tipo de engagement
        engagement_type = request.args.get('engagement_type')
        if engagement_type and engagement_type in ClientConfig.ENGAGEMENT_TYPES:
            query = query.filter(Client.preferred_engagement_types.contains([engagement_type]))
        
        # Filtro por rango de inversión
        investment_range_min = request.args.get('investment_range_min', type=float)
        if investment_range_min:
            query = query.filter(Client.investment_range_max >= investment_range_min)
        
        investment_range_max = request.args.get('investment_range_max', type=float)
        if investment_range_max:
            query = query.filter(Client.investment_range_min <= investment_range_max)
        
        # Filtro por engagements activos
        active_engagements = request.args.get('active_engagements', type=bool)
        if active_engagements is not None:
            if active_engagements:
                query = query.filter(Client.active_engagements > 0)
            else:
                query = query.filter(Client.active_engagements == 0)
        
        # Ordenamiento
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        valid_sort_fields = [
            'created_at', 'updated_at', 'organization', 'investment_range_min',
            'investment_range_max', 'active_engagements', 'total_investments'
        ]
        
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        if sort_by in ['created_at', 'updated_at']:
            sort_field = getattr(User, sort_by)
        else:
            sort_field = getattr(Client, sort_by)
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(sort_field))
        else:
            query = query.order_by(desc(sort_field))
        
        # Ejecutar paginación
        paginated = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Serializar resultados
        clients_data = []
        for client in paginated.items:
            data = client.to_dict(include_user=True, include_stats=True)
            # Agregar información adicional para listado
            data['portfolio_summary'] = ClientService.get_portfolio_summary(client)
            data['recent_activity'] = ClientService.get_recent_activity_summary(client)
            clients_data.append(data)
        
        return {
            'clients': clients_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages,
                'has_prev': paginated.has_prev,
                'has_next': paginated.has_next,
                'prev_page': paginated.prev_num if paginated.has_prev else None,
                'next_page': paginated.next_num if paginated.has_next else None
            },
            'filters_applied': {
                'search': search,
                'client_type': client_type,
                'interest_area': interest_area,
                'investment_stage': investment_stage,
                'location': location,
                'engagement_type': engagement_type,
                'active_engagements': active_engagements
            }
        }
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.USER_CREATE, "Client profile creation")
    def post(self):
        """
        Crear perfil de cliente/stakeholder
        
        Body:
            user_id: ID del usuario (opcional, usa usuario actual si no se especifica)
            organization: Organización del cliente
            role: Rol en la organización
            client_type: Tipo de cliente
            bio: Biografía profesional
            interest_areas: Áreas de interés
            preferred_investment_stages: Etapas de inversión preferidas
            preferred_engagement_types: Tipos de engagement preferidos
            investment_range_min: Rango mínimo de inversión
            investment_range_max: Rango máximo de inversión
            investment_criteria: Criterios de inversión
            portfolio_focus: Enfoque del portfolio
            decision_making_process: Proceso de toma de decisiones
            website_url: Sitio web
            linkedin_url: LinkedIn
            investment_thesis: Tesis de inversión
        
        Returns:
            Perfil de cliente creado
        """
        current_user = get_current_user()
        data = request.get_json()
        
        # Determinar usuario objetivo
        user_id = data.get('user_id')
        if user_id:
            # Solo admin puede crear perfiles para otros usuarios
            if not current_user.is_admin():
                raise AuthorizationError("No puede crear perfiles para otros usuarios")
            target_user = User.query.get_or_404(user_id)
        else:
            target_user = current_user
        
        # Validar que el usuario no tenga ya un perfil de cliente
        existing_client = Client.query.filter_by(user_id=target_user.id).first()
        if existing_client:
            raise BusinessLogicError("El usuario ya tiene un perfil de cliente")
        
        # Validar campos requeridos
        required_fields = ['organization', 'role', 'client_type', 'interest_areas']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        # Validar tipo de cliente
        client_type = data.get('client_type')
        if client_type not in ClientConfig.CLIENT_TYPES:
            raise ValidationError(f"Tipo de cliente inválido. Válidos: {', '.join(ClientConfig.CLIENT_TYPES)}")
        
        # Validar áreas de interés
        interest_areas = data.get('interest_areas', [])
        for area in interest_areas:
            if area not in ClientConfig.INTEREST_AREAS:
                raise ValidationError(f"Área de interés inválida: {area}")
        
        # Validar etapas de inversión
        investment_stages = data.get('preferred_investment_stages', [])
        for stage in investment_stages:
            if stage not in ClientConfig.INVESTMENT_STAGES:
                raise ValidationError(f"Etapa de inversión inválida: {stage}")
        
        # Validar tipos de engagement
        engagement_types = data.get('preferred_engagement_types', [])
        for e_type in engagement_types:
            if e_type not in ClientConfig.ENGAGEMENT_TYPES:
                raise ValidationError(f"Tipo de engagement inválido: {e_type}")
        
        try:
            # Crear perfil de cliente usando el servicio
            client = ClientService.create_client_profile(
                user_id=target_user.id,
                profile_data=data,
                created_by=current_user.id
            )
            
            # Actualizar tipo de usuario si es necesario
            if target_user.user_type != 'client':
                target_user.user_type = 'client'
                db.session.commit()
            
            return client.to_dict(include_user=True, include_stats=True), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating client profile: {e}")
            raise BusinessLogicError("Error al crear perfil de cliente")


class ClientDetailResource(Resource):
    """Endpoint para operaciones con cliente específico"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener detalles completos de un cliente/stakeholder
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            include_portfolio: Incluir información de portfolio (default: true)
            include_engagements: Incluir engagements activos (default: true)
            include_metrics: Incluir métricas de performance (default: true)
            include_pipeline: Incluir pipeline de oportunidades (default: false)
        
        Returns:
            Información completa del cliente
        """
        current_user = get_current_user()
        client = Client.query.options(
            joinedload(Client.user),
            joinedload(Client.organization),
            joinedload(Client.current_programs)
        ).get_or_404(client_id)
        
        # Verificar permisos de acceso
        if not self._can_view_client(current_user, client):
            raise AuthorizationError("No tiene permisos para ver este cliente")
        
        # Parámetros de inclusión
        include_portfolio = request.args.get('include_portfolio', 'true').lower() == 'true'
        include_engagements = request.args.get('include_engagements', 'true').lower() == 'true'
        include_metrics = request.args.get('include_metrics', 'true').lower() == 'true'
        include_pipeline = request.args.get('include_pipeline', 'false').lower() == 'true'
        
        # Construir respuesta
        client_data = client.to_dict(
            include_user=True,
            include_stats=True,
            include_sensitive=current_user.is_admin() or current_user.id == client.user_id
        )
        
        # Incluir portfolio si se solicita
        if include_portfolio:
            client_data['portfolio'] = ClientService.get_detailed_portfolio(client)
        
        # Incluir engagements activos si se solicita
        if include_engagements:
            client_data['active_engagements'] = ClientService.get_active_engagements(client)
        
        # Incluir métricas si se solicita
        if include_metrics:
            client_data['performance_metrics'] = ClientService.get_performance_metrics(client)
        
        # Incluir pipeline si se solicita y tiene permisos
        if include_pipeline and (current_user.is_admin() or current_user.id == client.user_id):
            client_data['opportunity_pipeline'] = ClientService.get_opportunity_pipeline(client)
        
        return client_data
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.USER_UPDATE, "Client profile update")
    def put(self, client_id):
        """
        Actualizar perfil completo de cliente
        
        Args:
            client_id: ID del cliente
        
        Body:
            Datos del perfil a actualizar
        
        Returns:
            Perfil actualizado
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not self._can_edit_client(current_user, client):
            raise AuthorizationError("No tiene permisos para editar este cliente")
        
        data = request.get_json()
        
        try:
            # Actualizar usando el servicio
            updated_client = ClientService.update_client_profile(
                client=client,
                update_data=data,
                updated_by=current_user.id
            )
            
            return updated_client.to_dict(include_user=True, include_stats=True)
            
        except Exception as e:
            current_app.logger.error(f"Error updating client: {e}")
            raise BusinessLogicError("Error al actualizar cliente")
    
    @api_auth_required
    @validate_json
    def patch(self, client_id):
        """Actualización parcial de cliente"""
        return self.put(client_id)
    
    @api_auth_required
    def delete(self, client_id):
        """
        Eliminar perfil de cliente
        
        Args:
            client_id: ID del cliente
        
        Returns:
            Confirmación de eliminación
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para eliminar este cliente")
        
        try:
            # Eliminar usando el servicio
            ClientService.delete_client_profile(
                client=client,
                deleted_by=current_user.id
            )
            
            return {'message': 'Perfil de cliente eliminado exitosamente'}
            
        except Exception as e:
            current_app.logger.error(f"Error deleting client: {e}")
            raise BusinessLogicError("Error al eliminar cliente")
    
    def _can_view_client(self, current_user: User, client: Client) -> bool:
        """Verifica permisos de visualización"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver su propio perfil
        if current_user.id == client.user_id:
            return True
        
        # Puede ver perfiles públicos
        if client.user.is_public_profile:
            return True
        
        # Puede ver clientes de su organización
        if (hasattr(current_user, 'organization_id') and 
            current_user.organization_id == client.user.organization_id):
            return True
        
        return False
    
    def _can_edit_client(self, current_user: User, client: Client) -> bool:
        """Verifica permisos de edición"""
        # Admin puede editar todo
        if current_user.is_admin():
            return True
        
        # Puede editar su propio perfil
        if current_user.id == client.user_id:
            return True
        
        return False


class ClientPortfolioResource(Resource):
    """Endpoint para gestión del portfolio del cliente"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener portfolio completo del cliente
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            status: Filtrar por estado (active, exited, failed)
            industry: Filtrar por industria
            stage: Filtrar por etapa de inversión
            include_performance: Incluir métricas de performance
            sort_by: Campo para ordenar
        
        Returns:
            Portfolio completo del cliente
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver este portfolio")
        
        # Parámetros de filtrado
        status = request.args.get('status')
        industry = request.args.get('industry')
        stage = request.args.get('stage')
        include_performance = request.args.get('include_performance', 'true').lower() == 'true'
        sort_by = request.args.get('sort_by', 'investment_date')
        
        try:
            portfolio = ClientService.get_portfolio_detailed(
                client=client,
                filters={
                    'status': status,
                    'industry': industry,
                    'stage': stage
                },
                include_performance=include_performance,
                sort_by=sort_by
            )
            
            return {
                'client_id': client_id,
                'portfolio': portfolio,
                'summary': ClientService.get_portfolio_summary_stats(client),
                'filters_applied': {
                    'status': status,
                    'industry': industry,
                    'stage': stage
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client portfolio: {e}")
            raise BusinessLogicError("Error al obtener portfolio")
    
    @api_auth_required
    @validate_json
    def post(self, client_id):
        """
        Agregar nueva inversión al portfolio
        
        Args:
            client_id: ID del cliente
        
        Body:
            entrepreneur_id: ID del emprendedor/startup
            project_id: ID del proyecto (opcional)
            investment_amount: Monto de inversión
            investment_type: Tipo de inversión
            equity_percentage: Porcentaje de equity (opcional)
            investment_date: Fecha de inversión
            valuation: Valuación de la empresa
            stage: Etapa de inversión
            notes: Notas adicionales
        
        Returns:
            Inversión agregada al portfolio
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No puede agregar inversiones a este portfolio")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['entrepreneur_id', 'investment_amount', 'investment_type', 'investment_date']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            investment = ClientService.add_portfolio_investment(
                client=client,
                investment_data=data,
                added_by=current_user.id
            )
            
            return {
                'message': 'Inversión agregada al portfolio',
                'investment': investment
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error adding portfolio investment: {e}")
            raise BusinessLogicError("Error al agregar inversión al portfolio")


class ClientEngagementsResource(Resource):
    """Endpoint para gestión de engagements del cliente"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener engagements del cliente
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            status: Filtrar por estado
            engagement_type: Filtrar por tipo de engagement
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango
        
        Returns:
            Lista de engagements
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver estos engagements")
        
        # Parámetros de filtrado
        status = request.args.get('status')
        engagement_type = request.args.get('engagement_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        try:
            engagements = ClientService.get_client_engagements(
                client=client,
                filters={
                    'status': status,
                    'engagement_type': engagement_type,
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
            
            return {
                'client_id': client_id,
                'engagements': engagements,
                'summary': ClientService.get_engagements_summary(client),
                'filters_applied': {
                    'status': status,
                    'engagement_type': engagement_type,
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client engagements: {e}")
            raise BusinessLogicError("Error al obtener engagements")
    
    @api_auth_required
    @validate_json
    def post(self, client_id):
        """
        Crear nuevo engagement
        
        Args:
            client_id: ID del cliente
        
        Body:
            entrepreneur_id: ID del emprendedor
            engagement_type: Tipo de engagement
            description: Descripción del engagement
            start_date: Fecha de inicio
            expected_end_date: Fecha esperada de finalización
            terms: Términos del engagement
            deliverables: Entregables esperados
        
        Returns:
            Engagement creado
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No puede crear engagements para este cliente")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['entrepreneur_id', 'engagement_type', 'description', 'start_date']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            engagement = ClientService.create_engagement(
                client=client,
                engagement_data=data,
                created_by=current_user.id
            )
            
            return {
                'message': 'Engagement creado exitosamente',
                'engagement': engagement
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating engagement: {e}")
            raise BusinessLogicError("Error al crear engagement")


class ClientReportsResource(Resource):
    """Endpoint para generación de reportes del cliente"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Listar reportes disponibles del cliente
        
        Args:
            client_id: ID del cliente
        
        Returns:
            Lista de reportes disponibles
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver estos reportes")
        
        try:
            available_reports = ClientService.get_available_reports(client)
            generated_reports = ClientService.get_generated_reports(client)
            
            return {
                'client_id': client_id,
                'available_reports': available_reports,
                'generated_reports': generated_reports,
                'report_templates': ClientService.get_report_templates()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client reports: {e}")
            raise BusinessLogicError("Error al obtener reportes")
    
    @api_auth_required
    @validate_json
    def post(self, client_id):
        """
        Generar nuevo reporte personalizado
        
        Args:
            client_id: ID del cliente
        
        Body:
            report_type: Tipo de reporte
            title: Título del reporte
            parameters: Parámetros del reporte
            format: Formato de salida (pdf, excel, json)
            schedule: Programación automática (opcional)
            recipients: Destinatarios del reporte (opcional)
        
        Returns:
            Reporte generado o job de generación
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No puede generar reportes para este cliente")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['report_type', 'title', 'parameters']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            report_job = ClientService.generate_custom_report(
                client=client,
                report_data=data,
                generated_by=current_user.id
            )
            
            return {
                'message': 'Reporte programado para generación',
                'report_job': report_job,
                'estimated_completion': report_job.get('estimated_completion')
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error generating report: {e}")
            raise BusinessLogicError("Error al generar reporte")


class ClientDashboardResource(Resource):
    """Endpoint para dashboard del cliente"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener datos del dashboard del cliente
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            period: Período de análisis (7d, 30d, 90d, 1y)
            metrics: Métricas específicas a incluir
        
        Returns:
            Datos del dashboard personalizado
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver este dashboard")
        
        period = request.args.get('period', '30d')
        specific_metrics = request.args.get('metrics', '').split(',') if request.args.get('metrics') else None
        
        try:
            dashboard_data = ClientService.get_dashboard_data(
                client=client,
                period=period,
                specific_metrics=specific_metrics
            )
            
            return {
                'client_id': client_id,
                'dashboard': dashboard_data,
                'period': period,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client dashboard: {e}")
            raise BusinessLogicError("Error al obtener dashboard")


class ClientEvaluationResource(Resource):
    """Endpoint para evaluación de oportunidades"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener evaluaciones pendientes del cliente
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            status: Filtrar por estado de evaluación
            priority: Filtrar por prioridad
        
        Returns:
            Lista de evaluaciones
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver estas evaluaciones")
        
        status = request.args.get('status')
        priority = request.args.get('priority')
        
        try:
            evaluations = ClientService.get_pending_evaluations(
                client=client,
                status=status,
                priority=priority
            )
            
            return {
                'client_id': client_id,
                'evaluations': evaluations,
                'evaluation_framework': ClientService.get_evaluation_framework(client),
                'filters_applied': {
                    'status': status,
                    'priority': priority
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client evaluations: {e}")
            raise BusinessLogicError("Error al obtener evaluaciones")
    
    @api_auth_required
    @validate_json
    def post(self, client_id):
        """
        Crear nueva evaluación de oportunidad
        
        Args:
            client_id: ID del cliente
        
        Body:
            entrepreneur_id: ID del emprendedor a evaluar
            project_id: ID del proyecto (opcional)
            evaluation_type: Tipo de evaluación
            criteria: Criterios de evaluación
            deadline: Fecha límite de evaluación
            evaluators: Evaluadores asignados
            notes: Notas iniciales
        
        Returns:
            Evaluación creada
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No puede crear evaluaciones para este cliente")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['entrepreneur_id', 'evaluation_type', 'criteria']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            evaluation = ClientService.create_evaluation(
                client=client,
                evaluation_data=data,
                created_by=current_user.id
            )
            
            return {
                'message': 'Evaluación creada exitosamente',
                'evaluation': evaluation
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating evaluation: {e}")
            raise BusinessLogicError("Error al crear evaluación")


class ClientAnalyticsResource(Resource):
    """Endpoint para analytics del cliente"""
    
    @api_auth_required
    def get(self, client_id):
        """
        Obtener analytics avanzados del cliente
        
        Args:
            client_id: ID del cliente
        
        Query Parameters:
            analysis_type: Tipo de análisis (portfolio, performance, trends)
            period: Período de análisis
            benchmark: Incluir benchmarking
        
        Returns:
            Analytics avanzados
        """
        current_user = get_current_user()
        client = Client.query.get_or_404(client_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == client.user_id):
            raise AuthorizationError("No tiene permisos para ver estos analytics")
        
        analysis_type = request.args.get('analysis_type', 'portfolio')
        period = request.args.get('period', '1y')
        include_benchmark = request.args.get('benchmark', 'false').lower() == 'true'
        
        try:
            analytics = ClientService.get_advanced_analytics(
                client=client,
                analysis_type=analysis_type,
                period=period,
                include_benchmark=include_benchmark
            )
            
            return {
                'client_id': client_id,
                'analytics': analytics,
                'analysis_type': analysis_type,
                'period': period,
                'benchmark_included': include_benchmark,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client analytics: {e}")
            raise BusinessLogicError("Error al obtener analytics")


class ClientSearchResource(Resource):
    """Endpoint para búsqueda avanzada de clientes"""
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Búsqueda avanzada de clientes/stakeholders
        
        Body:
            query: Término de búsqueda
            filters: Filtros específicos
            sort: Opciones de ordenamiento
            facets: Facetas para análisis
            limit: Límite de resultados
        
        Returns:
            Resultados de búsqueda con facetas
        """
        current_user = get_current_user()
        data = request.get_json() or {}
        
        query_term = data.get('query', '').strip()
        filters = data.get('filters', {})
        sort_options = data.get('sort', {})
        facets = data.get('facets', [])
        limit = min(data.get('limit', 50), 1000)
        
        try:
            results = ClientService.advanced_search(
                query=query_term,
                filters=filters,
                sort_options=sort_options,
                facets=facets,
                limit=limit,
                current_user=current_user
            )
            
            return {
                'results': results['clients'],
                'total': results['total'],
                'facets': results['facets'],
                'suggestions': results['suggestions'],
                'query': query_term,
                'filters_applied': filters
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in client search: {e}")
            raise BusinessLogicError("Error en búsqueda de clientes")


class ClientStatsResource(Resource):
    """Endpoint para estadísticas de clientes"""
    
    @api_auth_required
    def get(self):
        """
        Obtener estadísticas generales de clientes
        
        Query Parameters:
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            period: Período de análisis
            breakdown_by: Agrupar por campo específico
        
        Returns:
            Estadísticas de clientes
        """
        current_user = get_current_user()
        
        # Solo admin o usuarios con permisos específicos
        if not (current_user.is_admin() or current_user.has_permission('access_analytics')):
            raise AuthorizationError("No tiene permisos para ver estadísticas")
        
        organization_id = request.args.get('organization_id', type=int)
        program_id = request.args.get('program_id', type=int)
        period = request.args.get('period', '30d')
        breakdown_by = request.args.get('breakdown_by', 'client_type')
        
        try:
            stats = ClientService.get_comprehensive_statistics(
                organization_id=organization_id,
                program_id=program_id,
                period=period,
                breakdown_by=breakdown_by
            )
            
            return {
                'statistics': stats,
                'period': period,
                'breakdown_by': breakdown_by,
                'filters_applied': {
                    'organization_id': organization_id,
                    'program_id': program_id
                },
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting client statistics: {e}")
            raise BusinessLogicError("Error al obtener estadísticas")


# Registrar recursos en la API
api.add_resource(ClientsListResource, '')
api.add_resource(ClientDetailResource, '/<int:client_id>')
api.add_resource(ClientPortfolioResource, '/<int:client_id>/portfolio')
api.add_resource(ClientEngagementsResource, '/<int:client_id>/engagements')
api.add_resource(ClientReportsResource, '/<int:client_id>/reports')
api.add_resource(ClientDashboardResource, '/<int:client_id>/dashboard')
api.add_resource(ClientEvaluationResource, '/<int:client_id>/evaluations')
api.add_resource(ClientAnalyticsResource, '/<int:client_id>/analytics')
api.add_resource(ClientSearchResource, '/search')
api.add_resource(ClientStatsResource, '/statistics')


# Endpoints adicionales específicos para clientes
@clients_bp.route('/<int:client_id>/due-diligence', methods=['GET', 'POST'])
@api_auth_required
def due_diligence(client_id):
    """Gestión de due diligence"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para gestionar due diligence")
    
    if request.method == 'GET':
        # Obtener procesos de due diligence activos
        entrepreneur_id = request.args.get('entrepreneur_id', type=int)
        status = request.args.get('status', 'active')
        
        due_diligence_processes = ClientService.get_due_diligence_processes(
            client=client,
            entrepreneur_id=entrepreneur_id,
            status=status
        )
        
        return jsonify({
            'client_id': client_id,
            'due_diligence_processes': due_diligence_processes,
            'templates': ClientService.get_due_diligence_templates(),
            'checklists': ClientService.get_due_diligence_checklists()
        })
    
    elif request.method == 'POST':
        # Iniciar nuevo proceso de due diligence
        data = request.get_json()
        
        required_fields = ['entrepreneur_id', 'process_type', 'checklist_template']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            dd_process = ClientService.initiate_due_diligence(
                client=client,
                dd_data=data,
                initiated_by=current_user.id
            )
            
            return jsonify({
                'message': 'Proceso de due diligence iniciado',
                'due_diligence_process': dd_process
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error initiating due diligence: {e}")
            raise BusinessLogicError("Error al iniciar due diligence")


@clients_bp.route('/<int:client_id>/investment-committee', methods=['GET', 'POST'])
@api_auth_required
def investment_committee(client_id):
    """Gestión de comité de inversión"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para gestionar comité de inversión")
    
    if request.method == 'GET':
        # Obtener información del comité de inversión
        committee_info = ClientService.get_investment_committee_info(client)
        pending_decisions = ClientService.get_pending_investment_decisions(client)
        
        return jsonify({
            'client_id': client_id,
            'committee': committee_info,
            'pending_decisions': pending_decisions,
            'recent_decisions': ClientService.get_recent_investment_decisions(client, limit=10)
        })
    
    elif request.method == 'POST':
        # Someter propuesta al comité
        data = request.get_json()
        
        required_fields = ['entrepreneur_id', 'proposal_summary', 'requested_amount']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            committee_submission = ClientService.submit_to_investment_committee(
                client=client,
                proposal_data=data,
                submitted_by=current_user.id
            )
            
            return jsonify({
                'message': 'Propuesta sometida al comité de inversión',
                'committee_submission': committee_submission
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error submitting to investment committee: {e}")
            raise BusinessLogicError("Error al someter propuesta al comité")


@clients_bp.route('/<int:client_id>/market-intelligence', methods=['GET'])
@api_auth_required
def market_intelligence(client_id):
    """Inteligencia de mercado para el cliente"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para ver inteligencia de mercado")
    
    # Parámetros de consulta
    focus_areas = request.args.get('focus_areas', '').split(',') if request.args.get('focus_areas') else []
    time_horizon = request.args.get('time_horizon', '6m')
    
    try:
        market_intelligence = ClientService.get_market_intelligence(
            client=client,
            focus_areas=focus_areas,
            time_horizon=time_horizon
        )
        
        return jsonify({
            'client_id': client_id,
            'market_intelligence': market_intelligence,
            'trends': ClientService.get_market_trends(client),
            'opportunities': ClientService.get_market_opportunities(client),
            'competitive_landscape': ClientService.get_competitive_landscape(client),
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting market intelligence: {e}")
        raise BusinessLogicError("Error al obtener inteligencia de mercado")


@clients_bp.route('/<int:client_id>/portfolio-optimization', methods=['GET', 'POST'])
@api_auth_required
def portfolio_optimization(client_id):
    """Optimización de portfolio"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para optimizar este portfolio")
    
    if request.method == 'GET':
        # Obtener análisis de optimización actual
        optimization_analysis = ClientService.get_portfolio_optimization_analysis(client)
        
        return jsonify({
            'client_id': client_id,
            'current_allocation': optimization_analysis['current_allocation'],
            'optimization_recommendations': optimization_analysis['recommendations'],
            'risk_analysis': optimization_analysis['risk_analysis'],
            'diversification_metrics': optimization_analysis['diversification'],
            'rebalancing_suggestions': optimization_analysis['rebalancing']
        })
    
    elif request.method == 'POST':
        # Aplicar estrategia de optimización
        data = request.get_json()
        
        strategy = data.get('strategy', 'balanced')
        constraints = data.get('constraints', {})
        
        try:
            optimization_result = ClientService.apply_portfolio_optimization(
                client=client,
                strategy=strategy,
                constraints=constraints,
                applied_by=current_user.id
            )
            
            return jsonify({
                'message': 'Estrategia de optimización aplicada',
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            current_app.logger.error(f"Error applying portfolio optimization: {e}")
            raise BusinessLogicError("Error al aplicar optimización de portfolio")


@clients_bp.route('/<int:client_id>/benchmarking', methods=['GET'])
@api_auth_required
def benchmarking(client_id):
    """Benchmarking del cliente contra peers"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para ver benchmarking")
    
    # Parámetros de benchmarking
    benchmark_type = request.args.get('benchmark_type', 'performance')
    peer_group = request.args.get('peer_group', 'similar_clients')
    metrics = request.args.get('metrics', '').split(',') if request.args.get('metrics') else []
    
    try:
        benchmarking_data = ClientService.get_benchmarking_analysis(
            client=client,
            benchmark_type=benchmark_type,
            peer_group=peer_group,
            metrics=metrics
        )
        
        return jsonify({
            'client_id': client_id,
            'benchmarking': benchmarking_data,
            'peer_comparison': ClientService.get_peer_comparison(client),
            'industry_averages': ClientService.get_industry_averages(client),
            'performance_ranking': ClientService.get_performance_ranking(client),
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting benchmarking data: {e}")
        raise BusinessLogicError("Error al obtener datos de benchmarking")


@clients_bp.route('/<int:client_id>/alerts', methods=['GET', 'POST'])
@api_auth_required
def client_alerts(client_id):
    """Gestión de alertas del cliente"""
    current_user = get_current_user()
    client = Client.query.get_or_404(client_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == client.user_id):
        raise AuthorizationError("No tiene permisos para gestionar alertas")
    
    if request.method == 'GET':
        # Obtener alertas activas
        alert_type = request.args.get('alert_type')
        status = request.args.get('status', 'active')
        
        alerts = ClientService.get_client_alerts(
            client=client,
            alert_type=alert_type,
            status=status
        )
        
        return jsonify({
            'client_id': client_id,
            'alerts': alerts,
            'alert_types': ClientService.get_available_alert_types(),
            'notification_preferences': ClientService.get_notification_preferences(client)
        })
    
    elif request.method == 'POST':
        # Crear nueva alerta
        data = request.get_json()
        
        required_fields = ['alert_type', 'conditions', 'notification_method']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            alert = ClientService.create_alert(
                client=client,
                alert_data=data,
                created_by=current_user.id
            )
            
            return jsonify({
                'message': 'Alerta creada exitosamente',
                'alert': alert
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating alert: {e}")
            raise BusinessLogicError("Error al crear alerta")


@clients_bp.route('/config', methods=['GET'])
@api_auth_required
def get_client_config():
    """Obtener configuraciones disponibles para clientes"""
    return jsonify({
        'client_types': [
            {'value': c_type, 'label': c_type.replace('_', ' ').title()}
            for c_type in ClientConfig.CLIENT_TYPES
        ],
        'interest_areas': [
            {'value': area, 'label': area.replace('_', ' ').title()}
            for area in ClientConfig.INTEREST_AREAS
        ],
        'investment_stages': [
            {'value': stage, 'label': stage.replace('_', ' ').title()}
            for stage in ClientConfig.INVESTMENT_STAGES
        ],
        'engagement_types': [
            {'value': e_type, 'label': e_type.replace('_', ' ').title()}
            for e_type in ClientConfig.ENGAGEMENT_TYPES
        ],
        'evaluation_metrics': [
            {'value': metric, 'label': metric.replace('_', ' ').title()}
            for metric in ClientConfig.EVALUATION_METRICS
        ],
        'tracking_status': [
            {'value': status, 'label': status.replace('_', ' ').title()}
            for status in ClientConfig.TRACKING_STATUS
        ]
    })


@clients_bp.route('/dashboard-insights', methods=['GET'])
@api_auth_required
def get_client_dashboard_insights():
    """Obtener insights para dashboard de clientes"""
    current_user = get_current_user()
    
    # Solo para usuarios de tipo cliente o admin
    if current_user.user_type != 'client' and not current_user.is_admin():
        raise AuthorizationError("Acceso limitado a clientes")
    
    try:
        if current_user.user_type == 'client':
            # Insights personalizados para el cliente actual
            client = Client.query.filter_by(user_id=current_user.id).first()
            if not client:
                raise ResourceNotFoundError("Perfil de cliente no encontrado")
            
            insights = ClientService.get_personalized_insights(client)
        else:
            # Insights generales para admin
            insights = ClientService.get_global_insights()
        
        return jsonify({
            'insights': insights,
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting client dashboard insights: {e}")
        raise BusinessLogicError("Error al obtener insights del dashboard")


# Funciones auxiliares para otros módulos
def get_client_summary(client_id: int) -> Optional[dict[str, Any]]:
    """
    Obtiene resumen de un cliente
    
    Args:
        client_id: ID del cliente
        
    Returns:
        Resumen del cliente o None si no existe
    """
    client = Client.query.options(
        joinedload(Client.user)
    ).get(client_id)
    
    if not client:
        return None
    
    return {
        'id': client.id,
        'user_id': client.user_id,
        'name': client.user.full_name,
        'organization': client.organization,
        'role': client.role,
        'client_type': client.client_type,
        'interest_areas': client.interest_areas,
        'investment_range': {
            'min': float(client.investment_range_min) if client.investment_range_min else None,
            'max': float(client.investment_range_max) if client.investment_range_max else None
        },
        'active_engagements': client.active_engagements,
        'total_investments': client.total_investments,
        'portfolio_companies': client.portfolio_companies_count
    }


def check_client_investment_fit(client_id: int, entrepreneur_id: int) -> dict[str, Any]:
    """
    Verifica el fit entre un cliente y un emprendedor para inversión
    
    Args:
        client_id: ID del cliente
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Análisis de fit con puntuación y detalles
    """
    client = Client.query.get(client_id)
    entrepreneur = Entrepreneur.query.get(entrepreneur_id)
    
    if not client or not entrepreneur:
        return {'fit_score': 0, 'details': 'Entidades no encontradas'}
    
    return ClientService.calculate_investment_fit(client, entrepreneur)


# Exportaciones para otros módulos
__all__ = [
    'clients_bp',
    'ClientConfig',
    'get_client_summary',
    'check_client_investment_fit'
]