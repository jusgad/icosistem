"""
API v1 Entrepreneurs Endpoints
=============================

Este módulo implementa todos los endpoints específicos para emprendedores en la API v1,
incluyendo gestión de perfiles, proyectos, métricas de negocio, matching con mentores,
y herramientas especializadas para emprendedores.

Funcionalidades:
- CRUD completo de perfiles de emprendedores
- Gestión de proyectos emprendedores
- Métricas de negocio y crecimiento
- Matching inteligente con mentores
- Herramientas de desarrollo empresarial
- Portfolio y showcasing
- Seguimiento de milestones
- Networking y conexiones
"""

from flask import Blueprint, request, jsonify, current_app, g
from flask_restful import Resource, Api
from sqlalchemy import or_, and_, func, desc, asc, case
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import json

from app.extensions import db, limiter
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.relationship import Relationship, RelationshipType, RelationshipStatus
from app.models.mentorship import MentorshipSession
from app.models.analytics import AnalyticsMetric, MetricType, MetricCategory
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError,
    ResourceNotFoundError,
    BusinessLogicError
)
from app.services.entrepreneur_service import EntrepreneurService
from app.services.project_service import ProjectService
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.utils.decorators import validate_json, log_activity
from app.api.middleware.auth import api_auth_required, get_current_user
from app.api import paginated_response, api_response
from app.api.v1 import APIv1Validator


# Crear blueprint para entrepreneurs
entrepreneurs_bp = Blueprint('entrepreneurs', __name__)
api = Api(entrepreneurs_bp)


class EntrepreneurConfig:
    """Configuración específica para emprendedores"""
    
    # Etapas de negocio válidas
    BUSINESS_STAGES = [
        'idea', 'validation', 'prototype', 'mvp', 
        'early_stage', 'growth', 'scale', 'mature'
    ]
    
    # Industrias principales
    INDUSTRIES = [
        'technology', 'healthcare', 'finance', 'education', 'retail',
        'manufacturing', 'agriculture', 'energy', 'real_estate', 'media',
        'transportation', 'food_beverage', 'fashion', 'gaming', 'other'
    ]
    
    # Tipos de funding
    FUNDING_TYPES = [
        'bootstrapped', 'friends_family', 'angel', 'seed', 'series_a',
        'series_b', 'series_c', 'venture_capital', 'private_equity',
        'crowdfunding', 'grants', 'bank_loan', 'other'
    ]
    
    # Métricas clave para emprendedores
    KEY_METRICS = [
        'revenue', 'users', 'customers', 'growth_rate', 'burn_rate',
        'runway', 'team_size', 'funding_raised', 'market_size'
    ]


class EntrepreneursListResource(Resource):
    """Endpoint para listar y crear emprendedores"""
    
    @api_auth_required
    def get(self):
        """
        Listar emprendedores con filtros especializados
        
        Query Parameters:
            page: Número de página
            per_page: Elementos por página
            search: Búsqueda en nombre/empresa
            business_stage: Filtrar por etapa de negocio
            industry: Filtrar por industria
            location: Filtrar por ubicación
            funding_stage: Filtrar por etapa de financiamiento
            has_projects: Solo emprendedores con proyectos
            looking_for_mentor: Buscando mentor
            available_for_collaboration: Disponible para colaborar
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            sort_by: Campo para ordenar
        
        Returns:
            Lista paginada de emprendedores
        """
        current_user = get_current_user()
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        page, per_page = APIv1Validator.validate_pagination_params(page, per_page)
        
        # Construir query base con joins optimizados
        query = db.session.query(Entrepreneur).join(User).options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.projects),
            joinedload(Entrepreneur.organization)
        )
        
        # Filtro base: solo emprendedores activos
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
                Entrepreneur.company_name.ilike(f'%{search}%'),
                Entrepreneur.business_description.ilike(f'%{search}%'),
                func.concat(User.first_name, ' ', User.last_name).ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtro por etapa de negocio
        business_stage = request.args.get('business_stage')
        if business_stage and business_stage in EntrepreneurConfig.BUSINESS_STAGES:
            query = query.filter(Entrepreneur.business_stage == business_stage)
        
        # Filtro por industria
        industry = request.args.get('industry')
        if industry and industry in EntrepreneurConfig.INDUSTRIES:
            query = query.filter(Entrepreneur.industry == industry)
        
        # Filtro por ubicación
        location = request.args.get('location')
        if location:
            query = query.filter(
                or_(
                    User.city.ilike(f'%{location}%'),
                    User.country.ilike(f'%{location}%')
                )
            )
        
        # Filtro por etapa de financiamiento
        funding_stage = request.args.get('funding_stage')
        if funding_stage and funding_stage in EntrepreneurConfig.FUNDING_TYPES:
            query = query.filter(Entrepreneur.funding_stage == funding_stage)
        
        # Filtro por emprendedores con proyectos
        has_projects = request.args.get('has_projects', type=bool)
        if has_projects is not None:
            if has_projects:
                query = query.filter(Entrepreneur.projects.any())
            else:
                query = query.filter(~Entrepreneur.projects.any())
        
        # Filtro por búsqueda de mentor
        looking_for_mentor = request.args.get('looking_for_mentor', type=bool)
        if looking_for_mentor is not None:
            query = query.filter(Entrepreneur.looking_for_mentor == looking_for_mentor)
        
        # Filtro por disponibilidad de colaboración
        available_for_collaboration = request.args.get('available_for_collaboration', type=bool)
        if available_for_collaboration is not None:
            query = query.filter(Entrepreneur.available_for_collaboration == available_for_collaboration)
        
        # Filtro por organización
        organization_id = request.args.get('organization_id', type=int)
        if organization_id:
            query = query.filter(User.organization_id == organization_id)
        
        # Filtro por programa
        program_id = request.args.get('program_id', type=int)
        if program_id:
            query = query.filter(Entrepreneur.current_programs.any(Program.id == program_id))
        
        # Ordenamiento
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        valid_sort_fields = [
            'created_at', 'updated_at', 'company_name', 'business_stage',
            'years_experience', 'funding_raised', 'team_size'
        ]
        
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        if sort_by in ['created_at', 'updated_at']:
            sort_field = getattr(User, sort_by)
        else:
            sort_field = getattr(Entrepreneur, sort_by)
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(sort_field))
        else:
            query = query.order_by(desc(sort_field))
        
        # Ejecutar paginación
        paginated = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Serializar resultados
        entrepreneurs_data = []
        for entrepreneur in paginated.items:
            data = entrepreneur.to_dict(include_user=True, include_stats=True)
            entrepreneurs_data.append(data)
        
        return {
            'entrepreneurs': entrepreneurs_data,
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
                'business_stage': business_stage,
                'industry': industry,
                'location': location,
                'funding_stage': funding_stage,
                'has_projects': has_projects,
                'looking_for_mentor': looking_for_mentor,
                'available_for_collaboration': available_for_collaboration
            }
        }
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.ENTREPRENEUR_ONBOARDING, "Entrepreneur profile creation")
    def post(self):
        """
        Crear perfil de emprendedor
        
        Body:
            user_id: ID del usuario (opcional, usa usuario actual si no se especifica)
            company_name: Nombre de la empresa
            business_description: Descripción del negocio
            business_stage: Etapa del negocio
            industry: Industria
            target_market: Mercado objetivo
            business_model: Modelo de negocio
            years_experience: Años de experiencia
            skills: Habilidades clave
            interests: Intereses
            looking_for_mentor: Buscando mentor
            available_for_collaboration: Disponible para colaborar
            website_url: Sitio web
            linkedin_url: LinkedIn
            pitch_deck_url: Pitch deck
        
        Returns:
            Perfil de emprendedor creado
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
        
        # Validar que el usuario no tenga ya un perfil de emprendedor
        existing_entrepreneur = Entrepreneur.query.filter_by(user_id=target_user.id).first()
        if existing_entrepreneur:
            raise BusinessLogicError("El usuario ya tiene un perfil de emprendedor")
        
        # Validar campos requeridos
        required_fields = ['company_name', 'business_description', 'business_stage', 'industry']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        # Validar valores específicos
        business_stage = data.get('business_stage')
        if business_stage not in EntrepreneurConfig.BUSINESS_STAGES:
            raise ValidationError(f"Etapa de negocio inválida. Válidas: {', '.join(EntrepreneurConfig.BUSINESS_STAGES)}")
        
        industry = data.get('industry')
        if industry not in EntrepreneurConfig.INDUSTRIES:
            raise ValidationError(f"Industria inválida. Válidas: {', '.join(EntrepreneurConfig.INDUSTRIES)}")
        
        try:
            # Crear perfil de emprendedor usando el servicio
            entrepreneur = EntrepreneurService.create_entrepreneur_profile(
                user_id=target_user.id,
                profile_data=data,
                created_by=current_user.id
            )
            
            # Actualizar tipo de usuario si es necesario
            if target_user.user_type != 'entrepreneur':
                target_user.user_type = 'entrepreneur'
                db.session.commit()
            
            return entrepreneur.to_dict(include_user=True, include_stats=True), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating entrepreneur profile: {e}")
            raise BusinessLogicError("Error al crear perfil de emprendedor")


class EntrepreneurDetailResource(Resource):
    """Endpoint para operaciones con emprendedor específico"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener detalles completos de un emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            include_projects: Incluir proyectos (default: true)
            include_metrics: Incluir métricas (default: true)
            include_relationships: Incluir relaciones (default: false)
            include_mentorship: Incluir información de mentoría (default: true)
        
        Returns:
            Información completa del emprendedor
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.projects),
            joinedload(Entrepreneur.organization)
        ).get_or_404(entrepreneur_id)
        
        # Verificar permisos de acceso
        if not self._can_view_entrepreneur(current_user, entrepreneur):
            raise AuthorizationError("No tiene permisos para ver este emprendedor")
        
        # Parámetros de inclusión
        include_projects = request.args.get('include_projects', 'true').lower() == 'true'
        include_metrics = request.args.get('include_metrics', 'true').lower() == 'true'
        include_relationships = request.args.get('include_relationships', 'false').lower() == 'true'
        include_mentorship = request.args.get('include_mentorship', 'true').lower() == 'true'
        
        # Construir respuesta
        entrepreneur_data = entrepreneur.to_dict(
            include_user=True,
            include_stats=True,
            include_sensitive=current_user.is_admin() or current_user.id == entrepreneur.user_id
        )
        
        # Incluir proyectos si se solicita
        if include_projects:
            entrepreneur_data['projects'] = [
                project.to_dict(include_stats=True) 
                for project in entrepreneur.projects
            ]
        
        # Incluir métricas si se solicita
        if include_metrics:
            entrepreneur_data['metrics'] = EntrepreneurService.get_entrepreneur_metrics(entrepreneur)
        
        # Incluir relaciones si se solicita
        if include_relationships:
            entrepreneur_data['relationships'] = EntrepreneurService.get_entrepreneur_relationships(entrepreneur)
        
        # Incluir información de mentoría si se solicita
        if include_mentorship:
            entrepreneur_data['mentorship'] = EntrepreneurService.get_mentorship_info(entrepreneur)
        
        return entrepreneur_data
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.ENTREPRENEUR_PROJECT_CREATION, "Entrepreneur profile update")
    def put(self, entrepreneur_id):
        """
        Actualizar perfil completo de emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            Datos del perfil a actualizar
        
        Returns:
            Perfil actualizado
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede solicitar mentoría para este emprendedor")
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('mentor_id'):
            raise ValidationError("mentor_id es requerido")
        
        mentor_id = data['mentor_id']
        message = data.get('message', '')
        areas_of_interest = data.get('areas_of_interest', [])
        preferred_frequency = data.get('preferred_frequency', 'weekly')
        
        try:
            # Crear solicitud de mentoría usando el servicio
            mentorship_request = EntrepreneurService.request_mentorship(
                entrepreneur=entrepreneur,
                mentor_id=mentor_id,
                message=message,
                areas_of_interest=areas_of_interest,
                preferred_frequency=preferred_frequency,
                requested_by=current_user.id
            )
            
            return {
                'message': 'Solicitud de mentoría enviada exitosamente',
                'mentorship_request': mentorship_request,
                'mentor_id': mentor_id,
                'entrepreneur_id': entrepreneur_id
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error requesting mentorship: {e}")
            raise BusinessLogicError("Error al solicitar mentoría")


class EntrepreneurMilestonesResource(Resource):
    """Endpoint para milestone tracking del emprendedor"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener milestones del emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            status: Filtrar por estado (pending, in_progress, completed)
            category: Filtrar por categoría
            project_id: Filtrar por proyecto específico
        
        Returns:
            Lista de milestones
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No tiene permisos para ver estos milestones")
        
        status = request.args.get('status')
        category = request.args.get('category')
        project_id = request.args.get('project_id', type=int)
        
        try:
            milestones = EntrepreneurService.get_milestones(
                entrepreneur=entrepreneur,
                filters={
                    'status': status,
                    'category': category,
                    'project_id': project_id
                }
            )
            
            return {
                'entrepreneur_id': entrepreneur_id,
                'milestones': milestones,
                'summary': EntrepreneurService.get_milestones_summary(entrepreneur),
                'filters_applied': {
                    'status': status,
                    'category': category,
                    'project_id': project_id
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting milestones: {e}")
            raise BusinessLogicError("Error al obtener milestones")
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.ENTREPRENEUR_MILESTONE_COMPLETION, "Milestone created")
    def post(self, entrepreneur_id):
        """
        Crear nuevo milestone
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            title: Título del milestone
            description: Descripción
            category: Categoría
            target_date: Fecha objetivo
            project_id: ID del proyecto (opcional)
            metrics: Métricas asociadas
        
        Returns:
            Milestone creado
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede crear milestones para este emprendedor")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['title', 'category', 'target_date']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            milestone = EntrepreneurService.create_milestone(
                entrepreneur=entrepreneur,
                milestone_data=data,
                created_by=current_user.id
            )
            
            return milestone, 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating milestone: {e}")
            raise BusinessLogicError("Error al crear milestone")


class EntrepreneurNetworkingResource(Resource):
    """Endpoint para networking y conexiones"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener red de contactos del emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            relationship_type: Tipo de relación
            include_potential: Incluir conexiones potenciales
            max_depth: Profundidad máxima de la red (default: 2)
        
        Returns:
            Red de contactos
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No tiene permisos para ver esta red")
        
        relationship_type = request.args.get('relationship_type')
        include_potential = request.args.get('include_potential', 'false').lower() == 'true'
        max_depth = min(request.args.get('max_depth', 2, type=int), 3)
        
        try:
            from app.models.relationship import get_user_network
            
            # Obtener red del emprendedor
            network = get_user_network(
                user_id=entrepreneur.user_id,
                relationship_types=[RelationshipType(relationship_type)] if relationship_type else None,
                max_depth=max_depth
            )
            
            # Agregar conexiones potenciales si se solicita
            if include_potential:
                potential_connections = EntrepreneurService.get_potential_connections(
                    entrepreneur=entrepreneur,
                    limit=20
                )
                network['potential_connections'] = potential_connections
            
            return {
                'entrepreneur_id': entrepreneur_id,
                'network': network,
                'analysis': EntrepreneurService.analyze_network(network),
                'recommendations': EntrepreneurService.get_networking_recommendations(entrepreneur)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting entrepreneur network: {e}")
            raise BusinessLogicError("Error al obtener red de contactos")
    
    @api_auth_required
    @validate_json
    def post(self, entrepreneur_id):
        """
        Crear nueva conexión
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            target_user_id: ID del usuario objetivo
            relationship_type: Tipo de relación
            message: Mensaje personalizado
            context: Contexto de la conexión
        
        Returns:
            Conexión creada
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede crear conexiones para este emprendedor")
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('target_user_id'):
            raise ValidationError("target_user_id es requerido")
        
        if not data.get('relationship_type'):
            raise ValidationError("relationship_type es requerido")
        
        try:
            connection = EntrepreneurService.create_connection(
                entrepreneur=entrepreneur,
                target_user_id=data['target_user_id'],
                relationship_type=data['relationship_type'],
                message=data.get('message', ''),
                context=data.get('context', ''),
                created_by=current_user.id
            )
            
            return {
                'message': 'Solicitud de conexión enviada',
                'connection': connection
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating connection: {e}")
            raise BusinessLogicError("Error al crear conexión")


class EntrepreneurPortfolioResource(Resource):
    """Endpoint para portfolio del emprendedor"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener portfolio público del emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Returns:
            Portfolio completo del emprendedor
        """
        entrepreneur = Entrepreneur.query.options(
            joinedload(Entrepreneur.user),
            joinedload(Entrepreneur.projects),
            joinedload(Entrepreneur.organization)
        ).get_or_404(entrepreneur_id)
        
        # Portfolio público - verificar si está habilitado
        if not entrepreneur.public_portfolio_enabled:
            raise AuthorizationError("El portfolio no está disponible públicamente")
        
        try:
            portfolio = EntrepreneurService.generate_portfolio(entrepreneur)
            
            return {
                'entrepreneur': portfolio['entrepreneur_info'],
                'projects': portfolio['featured_projects'],
                'achievements': portfolio['achievements'],
                'skills': portfolio['skills'],
                'experience': portfolio['experience'],
                'testimonials': portfolio['testimonials'],
                'metrics': portfolio['public_metrics'],
                'contact_info': portfolio['contact_info'],
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating portfolio: {e}")
            raise BusinessLogicError("Error al generar portfolio")
    
    @api_auth_required
    @validate_json
    def put(self, entrepreneur_id):
        """
        Actualizar configuración del portfolio
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            public_portfolio_enabled: Habilitar portfolio público
            featured_projects: IDs de proyectos destacados
            bio: Biografía personalizada
            custom_sections: Secciones personalizadas
        
        Returns:
            Configuración actualizada
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede actualizar este portfolio")
        
        data = request.get_json()
        
        try:
            updated_config = EntrepreneurService.update_portfolio_config(
                entrepreneur=entrepreneur,
                config_data=data,
                updated_by=current_user.id
            )
            
            return {
                'message': 'Configuración de portfolio actualizada',
                'config': updated_config
            }
            
        except Exception as e:
            current_app.logger.error(f"Error updating portfolio config: {e}")
            raise BusinessLogicError("Error al actualizar configuración de portfolio")


class EntrepreneurSearchResource(Resource):
    """Endpoint para búsqueda avanzada de emprendedores"""
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Búsqueda avanzada de emprendedores
        
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
            results = EntrepreneurService.advanced_search(
                query=query_term,
                filters=filters,
                sort_options=sort_options,
                facets=facets,
                limit=limit,
                current_user=current_user
            )
            
            return {
                'results': results['entrepreneurs'],
                'total': results['total'],
                'facets': results['facets'],
                'suggestions': results['suggestions'],
                'query': query_term,
                'filters_applied': filters
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in entrepreneur search: {e}")
            raise BusinessLogicError("Error en búsqueda de emprendedores")


class EntrepreneurStatsResource(Resource):
    """Endpoint para estadísticas de emprendedores"""
    
    @api_auth_required
    def get(self):
        """
        Obtener estadísticas generales de emprendedores
        
        Query Parameters:
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            period: Período de análisis
            breakdown_by: Agrupar por campo específico
        
        Returns:
            Estadísticas de emprendedores
        """
        current_user = get_current_user()
        
        # Solo admin o usuarios con permisos específicos
        if not (current_user.is_admin() or current_user.has_permission('access_analytics')):
            raise AuthorizationError("No tiene permisos para ver estadísticas")
        
        organization_id = request.args.get('organization_id', type=int)
        program_id = request.args.get('program_id', type=int)
        period = request.args.get('period', '30d')
        breakdown_by = request.args.get('breakdown_by', 'business_stage')
        
        try:
            stats = EntrepreneurService.get_comprehensive_statistics(
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
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting entrepreneur statistics: {e}")
            raise BusinessLogicError("Error al obtener estadísticas")


# Registrar recursos en la API
api.add_resource(EntrepreneursListResource, '')
api.add_resource(EntrepreneurDetailResource, '/<int:entrepreneur_id>')
api.add_resource(EntrepreneurProjectsResource, '/<int:entrepreneur_id>/projects')
api.add_resource(EntrepreneurMetricsResource, '/<int:entrepreneur_id>/metrics')
api.add_resource(EntrepreneurMentorMatchingResource, '/<int:entrepreneur_id>/mentor-matching')
api.add_resource(EntrepreneurMilestonesResource, '/<int:entrepreneur_id>/milestones')
api.add_resource(EntrepreneurNetworkingResource, '/<int:entrepreneur_id>/network')
api.add_resource(EntrepreneurPortfolioResource, '/<int:entrepreneur_id>/portfolio')
api.add_resource(EntrepreneurSearchResource, '/search')
api.add_resource(EntrepreneurStatsResource, '/statistics')


# Endpoints adicionales específicos para emprendedores
@entrepreneurs_bp.route('/<int:entrepreneur_id>/business-canvas', methods=['GET', 'PUT'])
@api_auth_required
def business_canvas(entrepreneur_id):
    """Gestión del Business Model Canvas"""
    current_user = get_current_user()
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
        raise AuthorizationError("No tiene permisos para acceder a este canvas")
    
    if request.method == 'GET':
        # Obtener canvas actual
        canvas = EntrepreneurService.get_business_canvas(entrepreneur)
        return jsonify({
            'entrepreneur_id': entrepreneur_id,
            'canvas': canvas,
            'last_updated': canvas.get('updated_at') if canvas else None
        })
    
    elif request.method == 'PUT':
        # Actualizar canvas
        data = request.get_json()
        
        try:
            updated_canvas = EntrepreneurService.update_business_canvas(
                entrepreneur=entrepreneur,
                canvas_data=data,
                updated_by=current_user.id
            )
            
            return jsonify({
                'message': 'Business Canvas actualizado',
                'canvas': updated_canvas
            })
            
        except Exception as e:
            current_app.logger.error(f"Error updating business canvas: {e}")
            raise BusinessLogicError("Error al actualizar Business Canvas")


@entrepreneurs_bp.route('/<int:entrepreneur_id>/funding-tracker', methods=['GET', 'POST'])
@api_auth_required
def funding_tracker(entrepreneur_id):
    """Seguimiento de funding y inversiones"""
    current_user = get_current_user()
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
        raise AuthorizationError("No tiene permisos para acceder a este tracker")
    
    if request.method == 'GET':
        # Obtener historial de funding
        funding_history = EntrepreneurService.get_funding_history(entrepreneur)
        
        return jsonify({
            'entrepreneur_id': entrepreneur_id,
            'current_funding_stage': entrepreneur.funding_stage,
            'total_funding_raised': entrepreneur.total_funding_raised,
            'funding_goal': entrepreneur.funding_goal,
            'funding_history': funding_history,
            'investor_contacts': EntrepreneurService.get_investor_contacts(entrepreneur)
        })
    
    elif request.method == 'POST':
        # Registrar nueva ronda de funding
        data = request.get_json()
        
        required_fields = ['amount', 'funding_type', 'date']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            funding_round = EntrepreneurService.add_funding_round(
                entrepreneur=entrepreneur,
                funding_data=data,
                added_by=current_user.id
            )
            
            return jsonify({
                'message': 'Ronda de funding registrada',
                'funding_round': funding_round
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error adding funding round: {e}")
            raise BusinessLogicError("Error al registrar ronda de funding")


@entrepreneurs_bp.route('/<int:entrepreneur_id>/pitch-deck', methods=['GET', 'POST', 'DELETE'])
@api_auth_required
def pitch_deck_management(entrepreneur_id):
    """Gestión de pitch deck"""
    current_user = get_current_user()
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
        raise AuthorizationError("No tiene permisos para gestionar este pitch deck")
    
    if request.method == 'GET':
        # Obtener información del pitch deck
        pitch_deck_info = EntrepreneurService.get_pitch_deck_info(entrepreneur)
        
        return jsonify({
            'entrepreneur_id': entrepreneur_id,
            'pitch_deck': pitch_deck_info,
            'versions': EntrepreneurService.get_pitch_deck_versions(entrepreneur)
        })
    
    elif request.method == 'POST':
        # Subir nuevo pitch deck
        if 'pitch_deck' not in request.files:
            raise ValidationError("No se proporcionó archivo de pitch deck")
        
        file = request.files['pitch_deck']
        version_notes = request.form.get('version_notes', '')
        
        try:
            pitch_deck = EntrepreneurService.upload_pitch_deck(
                entrepreneur=entrepreneur,
                file=file,
                version_notes=version_notes,
                uploaded_by=current_user.id
            )
            
            return jsonify({
                'message': 'Pitch deck subido exitosamente',
                'pitch_deck': pitch_deck
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error uploading pitch deck: {e}")
            raise BusinessLogicError("Error al subir pitch deck")
    
    elif request.method == 'DELETE':
        # Eliminar pitch deck actual
        try:
            EntrepreneurService.delete_pitch_deck(
                entrepreneur=entrepreneur,
                deleted_by=current_user.id
            )
            
            return jsonify({
                'message': 'Pitch deck eliminado exitosamente'
            })
            
        except Exception as e:
            current_app.logger.error(f"Error deleting pitch deck: {e}")
            raise BusinessLogicError("Error al eliminar pitch deck")


@entrepreneurs_bp.route('/config', methods=['GET'])
@api_auth_required
def get_entrepreneur_config():
    """Obtener configuraciones disponibles para emprendedores"""
    return jsonify({
        'business_stages': [
            {'value': stage, 'label': stage.replace('_', ' ').title()}
            for stage in EntrepreneurConfig.BUSINESS_STAGES
        ],
        'industries': [
            {'value': industry, 'label': industry.replace('_', ' ').title()}
            for industry in EntrepreneurConfig.INDUSTRIES
        ],
        'funding_types': [
            {'value': funding, 'label': funding.replace('_', ' ').title()}
            for funding in EntrepreneurConfig.FUNDING_TYPES
        ],
        'key_metrics': EntrepreneurConfig.KEY_METRICS,
        'milestone_categories': [
            'product_development', 'market_validation', 'team_building',
            'funding', 'partnerships', 'legal', 'marketing', 'operations'
        ]
    })


@entrepreneurs_bp.route('/dashboard-insights', methods=['GET'])
@api_auth_required
def get_dashboard_insights():
    """Obtener insights para dashboard de emprendedores"""
    current_user = get_current_user()
    
    # Solo para usuarios de tipo emprendedor o admin
    if current_user.user_type != 'entrepreneur' and not current_user.is_admin():
        raise AuthorizationError("Acceso limitado a emprendedores")
    
    try:
        if current_user.user_type == 'entrepreneur':
            # Insights personalizados para el emprendedor actual
            entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first()
            if not entrepreneur:
                raise ResourceNotFoundError("Perfil de emprendedor no encontrado")
            
            insights = EntrepreneurService.get_personalized_insights(entrepreneur)
        else:
            # Insights generales para admin
            insights = EntrepreneurService.get_global_insights()
        
        return jsonify({
            'insights': insights,
            'generated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting dashboard insights: {e}")
        raise BusinessLogicError("Error al obtener insights del dashboard")


# Funciones auxiliares para otros módulos
def get_entrepreneur_summary(entrepreneur_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene resumen de un emprendedor
    
    Args:
        entrepreneur_id: ID del emprendedor
        
    Returns:
        Resumen del emprendedor o None si no existe
    """
    entrepreneur = Entrepreneur.query.options(
        joinedload(Entrepreneur.user)
    ).get(entrepreneur_id)
    
    if not entrepreneur:
        return None
    
    return {
        'id': entrepreneur.id,
        'user_id': entrepreneur.user_id,
        'name': entrepreneur.user.full_name,
        'company_name': entrepreneur.company_name,
        'business_stage': entrepreneur.business_stage,
        'industry': entrepreneur.industry,
        'location': f"{entrepreneur.user.city}, {entrepreneur.user.country}".strip(', '),
        'projects_count': len(entrepreneur.projects),
        'looking_for_mentor': entrepreneur.looking_for_mentor,
        'available_for_collaboration': entrepreneur.available_for_collaboration
    }


# Exportaciones para otros módulos
__all__ = [
    'entrepreneurs_bp',
    'EntrepreneurConfig',
    'get_entrepreneur_summary'
]d)
        
        # Verificar permisos
        if not self._can_edit_entrepreneur(current_user, entrepreneur):
            raise AuthorizationError("No tiene permisos para editar este emprendedor")
        
        data = request.get_json()
        
        try:
            # Actualizar usando el servicio
            updated_entrepreneur = EntrepreneurService.update_entrepreneur_profile(
                entrepreneur=entrepreneur,
                update_data=data,
                updated_by=current_user.id
            )
            
            return updated_entrepreneur.to_dict(include_user=True, include_stats=True)
            
        except Exception as e:
            current_app.logger.error(f"Error updating entrepreneur: {e}")
            raise BusinessLogicError("Error al actualizar emprendedor")
    
    @api_auth_required
    @validate_json
    def patch(self, entrepreneur_id):
        """Actualización parcial de emprendedor"""
        return self.put(entrepreneur_id)
    
    @api_auth_required
    def delete(self, entrepreneur_id):
        """
        Eliminar perfil de emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Returns:
            Confirmación de eliminación
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No tiene permisos para eliminar este emprendedor")
        
        try:
            # Eliminar usando el servicio
            EntrepreneurService.delete_entrepreneur_profile(
                entrepreneur=entrepreneur,
                deleted_by=current_user.id
            )
            
            return {'message': 'Perfil de emprendedor eliminado exitosamente'}
            
        except Exception as e:
            current_app.logger.error(f"Error deleting entrepreneur: {e}")
            raise BusinessLogicError("Error al eliminar emprendedor")
    
    def _can_view_entrepreneur(self, current_user: User, entrepreneur: Entrepreneur) -> bool:
        """Verifica permisos de visualización"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver su propio perfil
        if current_user.id == entrepreneur.user_id:
            return True
        
        # Puede ver perfiles públicos
        if entrepreneur.user.is_public_profile:
            return True
        
        # Puede ver emprendedores de su organización
        if (hasattr(current_user, 'organization_id') and 
            current_user.organization_id == entrepreneur.user.organization_id):
            return True
        
        return False
    
    def _can_edit_entrepreneur(self, current_user: User, entrepreneur: Entrepreneur) -> bool:
        """Verifica permisos de edición"""
        # Admin puede editar todo
        if current_user.is_admin():
            return True
        
        # Puede editar su propio perfil
        if current_user.id == entrepreneur.user_id:
            return True
        
        return False


class EntrepreneurProjectsResource(Resource):
    """Endpoint para proyectos del emprendedor"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener proyectos del emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            status: Filtrar por estado del proyecto
            stage: Filtrar por etapa del proyecto
            include_archived: Incluir proyectos archivados
        
        Returns:
            Lista de proyectos del emprendedor
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not self._can_view_entrepreneur_projects(current_user, entrepreneur):
            raise AuthorizationError("No tiene permisos para ver estos proyectos")
        
        # Filtros
        status = request.args.get('status')
        stage = request.args.get('stage')
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        
        # Construir query
        query = Project.query.filter(Project.entrepreneur_id == entrepreneur_id)
        
        if status:
            query = query.filter(Project.status == status)
        
        if stage:
            query = query.filter(Project.stage == stage)
        
        if not include_archived:
            query = query.filter(Project.is_archived == False)
        
        projects = query.order_by(Project.created_at.desc()).all()
        
        return {
            'entrepreneur_id': entrepreneur_id,
            'projects': [project.to_dict(include_stats=True) for project in projects],
            'total_projects': len(projects),
            'filters_applied': {
                'status': status,
                'stage': stage,
                'include_archived': include_archived
            }
        }
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.ENTREPRENEUR_PROJECT_CREATION, "Project creation by entrepreneur")
    def post(self, entrepreneur_id):
        """
        Crear nuevo proyecto para el emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            Datos del proyecto
        
        Returns:
            Proyecto creado
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede crear proyectos para este emprendedor")
        
        data = request.get_json()
        data['entrepreneur_id'] = entrepreneur_id
        
        try:
            # Crear proyecto usando el servicio
            project = ProjectService.create_project(
                project_data=data,
                created_by=current_user.id
            )
            
            return project.to_dict(include_stats=True), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating project: {e}")
            raise BusinessLogicError("Error al crear proyecto")
    
    def _can_view_entrepreneur_projects(self, current_user: User, entrepreneur: Entrepreneur) -> bool:
        """Verifica permisos para ver proyectos"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver sus propios proyectos
        if current_user.id == entrepreneur.user_id:
            return True
        
        # Puede ver proyectos públicos
        # (Implementar lógica según privacidad de proyectos)
        
        return False


class EntrepreneurMetricsResource(Resource):
    """Endpoint para métricas del emprendedor"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener métricas del emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            period: Período de análisis (7d, 30d, 90d, 1y)
            metrics: Métricas específicas (comma-separated)
        
        Returns:
            Métricas del emprendedor
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No tiene permisos para ver estas métricas")
        
        period = request.args.get('period', '30d')
        specific_metrics = request.args.get('metrics', '').split(',') if request.args.get('metrics') else None
        
        try:
            metrics = EntrepreneurService.get_comprehensive_metrics(
                entrepreneur=entrepreneur,
                period=period,
                specific_metrics=specific_metrics
            )
            
            return {
                'entrepreneur_id': entrepreneur_id,
                'period': period,
                'metrics': metrics,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting entrepreneur metrics: {e}")
            raise BusinessLogicError("Error al obtener métricas")
    
    @api_auth_required
    @validate_json
    def post(self, entrepreneur_id):
        """
        Registrar nueva métrica para el emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            metric_type: Tipo de métrica
            value: Valor de la métrica
            unit: Unidad de medida
            description: Descripción
            metadata: Metadatos adicionales
        
        Returns:
            Métrica registrada
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede registrar métricas para este emprendedor")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['metric_type', 'value']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            # Registrar métrica usando el servicio de analytics
            metric = AnalyticsService.record_metric(
                metric_type=MetricType(data['metric_type']),
                value=data['value'],
                category=MetricCategory.BUSINESS_GROWTH,
                name=data.get('description', f"Entrepreneur {data['metric_type']}"),
                unit=data.get('unit'),
                user_id=entrepreneur.user_id,
                metadata=data.get('metadata', {}),
                organization_id=entrepreneur.user.organization_id
            )
            
            return metric.to_dict(), 201
            
        except Exception as e:
            current_app.logger.error(f"Error recording metric: {e}")
            raise BusinessLogicError("Error al registrar métrica")


class EntrepreneurMentorMatchingResource(Resource):
    """Endpoint para matching con mentores"""
    
    @api_auth_required
    def get(self, entrepreneur_id):
        """
        Obtener mentores recomendados para el emprendedor
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Query Parameters:
            limit: Límite de recomendaciones (default: 10)
            industry_match: Priorizar match por industria
            experience_match: Priorizar match por experiencia
            location_match: Priorizar match por ubicación
        
        Returns:
            Lista de mentores recomendados
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == entrepreneur.user_id):
            raise AuthorizationError("No puede ver recomendaciones para este emprendedor")
        
        limit = min(request.args.get('limit', 10, type=int), 50)
        industry_match = request.args.get('industry_match', 'true').lower() == 'true'
        experience_match = request.args.get('experience_match', 'true').lower() == 'true'
        location_match = request.args.get('location_match', 'false').lower() == 'true'
        
        try:
            # Obtener recomendaciones usando el servicio
            recommendations = EntrepreneurService.get_mentor_recommendations(
                entrepreneur=entrepreneur,
                limit=limit,
                filters={
                    'industry_match': industry_match,
                    'experience_match': experience_match,
                    'location_match': location_match
                }
            )
            
            return {
                'entrepreneur_id': entrepreneur_id,
                'recommendations': recommendations,
                'total_recommendations': len(recommendations),
                'filters_applied': {
                    'industry_match': industry_match,
                    'experience_match': experience_match,
                    'location_match': location_match
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting mentor recommendations: {e}")
            raise BusinessLogicError("Error al obtener recomendaciones de mentores")
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.MENTORSHIP_REQUEST, "Mentorship request sent")
    def post(self, entrepreneur_id):
        """
        Solicitar mentoría a un mentor específico
        
        Args:
            entrepreneur_id: ID del emprendedor
        
        Body:
            mentor_id: ID del mentor
            message: Mensaje personalizado
            areas_of_interest: Áreas de interés para la mentoría
            preferred_frequency: Frecuencia preferida de sesiones
        
        Returns:
            Solicitud de mentoría creada
        """
        current_user = get_current_user()
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        # Verificar permisos        