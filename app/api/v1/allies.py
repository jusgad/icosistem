"""
API v1 Allies/Mentors Endpoints
==============================

Este módulo implementa todos los endpoints específicos para aliados/mentores en la API v1,
incluyendo gestión de perfiles, capacidades de mentoría, disponibilidad, matching con
emprendedores, seguimiento de sesiones y análisis de impacto.

Funcionalidades:
- CRUD completo de perfiles de aliados/mentores
- Gestión de expertise y áreas de especialización
- Sistema de disponibilidad y calendario
- Matching inteligente con emprendedores
- Seguimiento de sesiones de mentoría
- Métricas de impacto y efectividad
- Sistema de reputación y reviews
- Herramientas para mentores
"""

from flask import Blueprint, request, jsonify, current_app, g
from flask_restful import Resource, Api
from sqlalchemy import or_, and_, func, desc, asc, case
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import json

from app.extensions import db, limiter
from app.models.user import User
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.organization import Organization
from app.models.program import Program
from app.models.relationship import Relationship, RelationshipType, RelationshipStatus
from app.models.mentorship import MentorshipSession, MentorshipRequest
from app.models.meeting import Meeting
from app.models.analytics import AnalyticsMetric, MetricType, MetricCategory
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError,
    ResourceNotFoundError,
    BusinessLogicError
)
from app.services.ally_service import AllyService
from app.services.mentorship_service import MentorshipService
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.services.google_calendar import GoogleCalendarService
from app.utils.decorators import validate_json, log_activity
from app.api.middleware.auth import api_auth_required, get_current_user
from app.api import paginated_response, api_response
from app.api.v1 import APIv1Validator


# Crear blueprint para allies
allies_bp = Blueprint('allies', __name__)
api = Api(allies_bp)


class AllyConfig:
    """Configuración específica para aliados/mentores"""
    
    # Áreas de expertise disponibles
    EXPERTISE_AREAS = [
        'business_strategy', 'marketing', 'sales', 'finance', 'fundraising',
        'product_development', 'technology', 'operations', 'hr', 'legal',
        'leadership', 'scaling', 'international_expansion', 'digital_transformation',
        'sustainability', 'innovation', 'customer_experience', 'data_analytics',
        'supply_chain', 'partnerships', 'mergers_acquisitions', 'public_relations'
    ]
    
    # Tipos de mentoría
    MENTORSHIP_TYPES = [
        'one_on_one', 'group_mentoring', 'peer_mentoring', 'reverse_mentoring',
        'project_based', 'skills_based', 'career_coaching', 'strategic_advisory'
    ]
    
    # Niveles de experiencia
    EXPERIENCE_LEVELS = [
        'junior', 'mid_level', 'senior', 'executive', 'c_level', 'board_member'
    ]
    
    # Frecuencias de mentoría
    MENTORING_FREQUENCIES = [
        'weekly', 'biweekly', 'monthly', 'quarterly', 'as_needed', 'project_based'
    ]
    
    # Métodos de comunicación preferidos
    COMMUNICATION_METHODS = [
        'video_call', 'phone_call', 'in_person', 'email', 'messaging', 'mixed'
    ]
    
    # Estados de disponibilidad
    AVAILABILITY_STATUS = [
        'available', 'limited', 'busy', 'not_available', 'on_break'
    ]


class AlliesListResource(Resource):
    """Endpoint para listar y crear aliados/mentores"""
    
    @api_auth_required
    def get(self):
        """
        Listar aliados/mentores con filtros especializados
        
        Query Parameters:
            page: Número de página
            per_page: Elementos por página  
            search: Búsqueda en nombre/organización
            expertise_area: Filtrar por área de expertise
            experience_level: Filtrar por nivel de experiencia
            years_experience_min: Años mínimos de experiencia
            location: Filtrar por ubicación
            available_for_mentorship: Disponible para mentoría
            mentorship_type: Tipo de mentoría preferida
            industry: Filtrar por industria de experiencia
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            rating_min: Calificación mínima
            languages: Idiomas hablados
            sort_by: Campo para ordenar
        
        Returns:
            Lista paginada de aliados/mentores
        """
        current_user = get_current_user()
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        page, per_page = APIv1Validator.validate_pagination_params(page, per_page)
        
        # Construir query base con joins optimizados
        query = db.session.query(Ally).join(User).options(
            joinedload(Ally.user),
            joinedload(Ally.organization),
            joinedload(Ally.current_programs)
        )
        
        # Filtro base: solo aliados activos
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
                Ally.organization.ilike(f'%{search}%'),
                Ally.title.ilike(f'%{search}%'),
                Ally.bio.ilike(f'%{search}%'),
                func.concat(User.first_name, ' ', User.last_name).ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtro por área de expertise
        expertise_area = request.args.get('expertise_area')
        if expertise_area and expertise_area in AllyConfig.EXPERTISE_AREAS:
            query = query.filter(Ally.expertise_areas.contains([expertise_area]))
        
        # Filtro por nivel de experiencia
        experience_level = request.args.get('experience_level')
        if experience_level and experience_level in AllyConfig.EXPERIENCE_LEVELS:
            query = query.filter(Ally.experience_level == experience_level)
        
        # Filtro por años mínimos de experiencia
        years_experience_min = request.args.get('years_experience_min', type=int)
        if years_experience_min:
            query = query.filter(Ally.years_experience >= years_experience_min)
        
        # Filtro por ubicación
        location = request.args.get('location')
        if location:
            query = query.filter(
                or_(
                    User.city.ilike(f'%{location}%'),
                    User.country.ilike(f'%{location}%')
                )
            )
        
        # Filtro por disponibilidad para mentoría
        available_for_mentorship = request.args.get('available_for_mentorship', type=bool)
        if available_for_mentorship is not None:
            query = query.filter(Ally.available_for_mentorship == available_for_mentorship)
        
        # Filtro por tipo de mentoría
        mentorship_type = request.args.get('mentorship_type')
        if mentorship_type and mentorship_type in AllyConfig.MENTORSHIP_TYPES:
            query = query.filter(Ally.preferred_mentorship_types.contains([mentorship_type]))
        
        # Filtro por industria
        industry = request.args.get('industry')
        if industry:
            query = query.filter(Ally.industries.contains([industry]))
        
        # Filtro por organización
        organization_id = request.args.get('organization_id', type=int)
        if organization_id:
            query = query.filter(User.organization_id == organization_id)
        
        # Filtro por programa
        program_id = request.args.get('program_id', type=int)
        if program_id:
            query = query.filter(Ally.current_programs.any(Program.id == program_id))
        
        # Filtro por calificación mínima
        rating_min = request.args.get('rating_min', type=float)
        if rating_min:
            query = query.filter(Ally.average_rating >= rating_min)
        
        # Filtro por idiomas
        languages = request.args.get('languages')
        if languages:
            language_list = [lang.strip() for lang in languages.split(',')]
            for lang in language_list:
                query = query.filter(Ally.languages.contains([lang]))
        
        # Ordenamiento
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        valid_sort_fields = [
            'created_at', 'updated_at', 'years_experience', 'average_rating',
            'total_mentees', 'sessions_completed', 'last_active'
        ]
        
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        if sort_by in ['created_at', 'updated_at']:
            sort_field = getattr(User, sort_by)
        else:
            sort_field = getattr(Ally, sort_by)
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(sort_field))
        else:
            query = query.order_by(desc(sort_field))
        
        # Ejecutar paginación
        paginated = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Serializar resultados
        allies_data = []
        for ally in paginated.items:
            data = ally.to_dict(include_user=True, include_stats=True)
            # Agregar información adicional para listado
            data['mentoring_capacity'] = AllyService.get_mentoring_capacity(ally)
            data['next_available_slot'] = AllyService.get_next_available_slot(ally)
            allies_data.append(data)
        
        return {
            'allies': allies_data,
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
                'expertise_area': expertise_area,
                'experience_level': experience_level,
                'years_experience_min': years_experience_min,
                'location': location,
                'available_for_mentorship': available_for_mentorship,
                'mentorship_type': mentorship_type,
                'industry': industry
            }
        }
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.USER_CREATE, "Ally profile creation")
    def post(self):
        """
        Crear perfil de aliado/mentor
        
        Body:
            user_id: ID del usuario (opcional, usa usuario actual si no se especifica)
            title: Título profesional
            organization: Organización actual
            bio: Biografía profesional
            expertise_areas: Áreas de expertise
            industries: Industrias de experiencia
            years_experience: Años de experiencia
            experience_level: Nivel de experiencia
            available_for_mentorship: Disponible para mentoría
            preferred_mentorship_types: Tipos de mentoría preferidos
            max_mentees: Máximo número de mentees
            hourly_rate: Tarifa por hora (opcional)
            languages: Idiomas hablados
            linkedin_url: URL de LinkedIn
            website_url: Sitio web personal
            communication_preferences: Preferencias de comunicación
        
        Returns:
            Perfil de aliado creado
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
        
        # Validar que el usuario no tenga ya un perfil de aliado
        existing_ally = Ally.query.filter_by(user_id=target_user.id).first()
        if existing_ally:
            raise BusinessLogicError("El usuario ya tiene un perfil de aliado")
        
        # Validar campos requeridos
        required_fields = ['title', 'bio', 'expertise_areas', 'years_experience']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        # Validar áreas de expertise
        expertise_areas = data.get('expertise_areas', [])
        for area in expertise_areas:
            if area not in AllyConfig.EXPERTISE_AREAS:
                raise ValidationError(f"Área de expertise inválida: {area}")
        
        # Validar nivel de experiencia
        experience_level = data.get('experience_level')
        if experience_level and experience_level not in AllyConfig.EXPERIENCE_LEVELS:
            raise ValidationError(f"Nivel de experiencia inválido: {experience_level}")
        
        # Validar tipos de mentoría preferidos
        mentorship_types = data.get('preferred_mentorship_types', [])
        for m_type in mentorship_types:
            if m_type not in AllyConfig.MENTORSHIP_TYPES:
                raise ValidationError(f"Tipo de mentoría inválido: {m_type}")
        
        try:
            # Crear perfil de aliado usando el servicio
            ally = AllyService.create_ally_profile(
                user_id=target_user.id,
                profile_data=data,
                created_by=current_user.id
            )
            
            # Actualizar tipo de usuario si es necesario
            if target_user.user_type != 'ally':
                target_user.user_type = 'ally'
                db.session.commit()
            
            return ally.to_dict(include_user=True, include_stats=True), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating ally profile: {e}")
            raise BusinessLogicError("Error al crear perfil de aliado")


class AllyDetailResource(Resource):
    """Endpoint para operaciones con aliado específico"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener detalles completos de un aliado/mentor
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            include_mentees: Incluir información de mentees (default: false)
            include_sessions: Incluir sesiones recientes (default: true)
            include_availability: Incluir disponibilidad (default: true)
            include_reviews: Incluir reviews (default: true)
            include_metrics: Incluir métricas de impacto (default: true)
        
        Returns:
            Información completa del aliado
        """
        current_user = get_current_user()
        ally = Ally.query.options(
            joinedload(Ally.user),
            joinedload(Ally.organization),
            joinedload(Ally.current_programs)
        ).get_or_404(ally_id)
        
        # Verificar permisos de acceso
        if not self._can_view_ally(current_user, ally):
            raise AuthorizationError("No tiene permisos para ver este aliado")
        
        # Parámetros de inclusión
        include_mentees = request.args.get('include_mentees', 'false').lower() == 'true'
        include_sessions = request.args.get('include_sessions', 'true').lower() == 'true'
        include_availability = request.args.get('include_availability', 'true').lower() == 'true'
        include_reviews = request.args.get('include_reviews', 'true').lower() == 'true'
        include_metrics = request.args.get('include_metrics', 'true').lower() == 'true'
        
        # Construir respuesta
        ally_data = ally.to_dict(
            include_user=True,
            include_stats=True,
            include_sensitive=current_user.is_admin() or current_user.id == ally.user_id
        )
        
        # Incluir mentees si se solicita y tiene permisos
        if include_mentees and (current_user.is_admin() or current_user.id == ally.user_id):
            ally_data['mentees'] = AllyService.get_current_mentees(ally)
        
        # Incluir sesiones recientes si se solicita
        if include_sessions:
            ally_data['recent_sessions'] = AllyService.get_recent_sessions(ally, limit=10)
        
        # Incluir disponibilidad si se solicita
        if include_availability:
            ally_data['availability'] = AllyService.get_availability_summary(ally)
        
        # Incluir reviews si se solicita
        if include_reviews:
            ally_data['reviews'] = AllyService.get_recent_reviews(ally, limit=5)
            ally_data['review_summary'] = AllyService.get_review_summary(ally)
        
        # Incluir métricas si se solicita
        if include_metrics:
            ally_data['impact_metrics'] = AllyService.get_impact_metrics(ally)
        
        return ally_data
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.USER_UPDATE, "Ally profile update")
    def put(self, ally_id):
        """
        Actualizar perfil completo de aliado
        
        Args:
            ally_id: ID del aliado
        
        Body:
            Datos del perfil a actualizar
        
        Returns:
            Perfil actualizado
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not self._can_edit_ally(current_user, ally):
            raise AuthorizationError("No tiene permisos para editar este aliado")
        
        data = request.get_json()
        
        try:
            # Actualizar usando el servicio
            updated_ally = AllyService.update_ally_profile(
                ally=ally,
                update_data=data,
                updated_by=current_user.id
            )
            
            return updated_ally.to_dict(include_user=True, include_stats=True)
            
        except Exception as e:
            current_app.logger.error(f"Error updating ally: {e}")
            raise BusinessLogicError("Error al actualizar aliado")
    
    @api_auth_required
    @validate_json
    def patch(self, ally_id):
        """Actualización parcial de aliado"""
        return self.put(ally_id)
    
    @api_auth_required
    def delete(self, ally_id):
        """
        Eliminar perfil de aliado
        
        Args:
            ally_id: ID del aliado
        
        Returns:
            Confirmación de eliminación
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No tiene permisos para eliminar este aliado")
        
        try:
            # Eliminar usando el servicio
            AllyService.delete_ally_profile(
                ally=ally,
                deleted_by=current_user.id
            )
            
            return {'message': 'Perfil de aliado eliminado exitosamente'}
            
        except Exception as e:
            current_app.logger.error(f"Error deleting ally: {e}")
            raise BusinessLogicError("Error al eliminar aliado")
    
    def _can_view_ally(self, current_user: User, ally: Ally) -> bool:
        """Verifica permisos de visualización"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver su propio perfil
        if current_user.id == ally.user_id:
            return True
        
        # Puede ver perfiles públicos
        if ally.user.is_public_profile:
            return True
        
        # Puede ver aliados de su organización
        if (hasattr(current_user, 'organization_id') and 
            current_user.organization_id == ally.user.organization_id):
            return True
        
        return False
    
    def _can_edit_ally(self, current_user: User, ally: Ally) -> bool:
        """Verifica permisos de edición"""
        # Admin puede editar todo
        if current_user.is_admin():
            return True
        
        # Puede editar su propio perfil
        if current_user.id == ally.user_id:
            return True
        
        return False


class AllyAvailabilityResource(Resource):
    """Endpoint para gestión de disponibilidad del aliado"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener disponibilidad del aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango
            timezone: Zona horaria para mostrar horarios
        
        Returns:
            Información de disponibilidad
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not self._can_view_ally_availability(current_user, ally):
            raise AuthorizationError("No tiene permisos para ver esta disponibilidad")
        
        # Parámetros de consulta
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        timezone = request.args.get('timezone', 'UTC')
        
        # Parsear fechas
        try:
            if start_date:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start_date = datetime.utcnow()
            
            if end_date:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_date = start_date + timedelta(days=30)
                
        except ValueError:
            raise ValidationError("Formato de fecha inválido. Use ISO 8601")
        
        try:
            availability = AllyService.get_detailed_availability(
                ally=ally,
                start_date=start_date,
                end_date=end_date,
                timezone=timezone
            )
            
            return {
                'ally_id': ally_id,
                'availability': availability,
                'timezone': timezone,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting ally availability: {e}")
            raise BusinessLogicError("Error al obtener disponibilidad")
    
    @api_auth_required
    @validate_json
    def put(self, ally_id):
        """
        Actualizar disponibilidad del aliado
        
        Args:
            ally_id: ID del aliado
        
        Body:
            general_availability: Disponibilidad general
            weekly_schedule: Horario semanal
            special_dates: Fechas especiales (vacaciones, etc.)
            timezone: Zona horaria
            max_sessions_per_week: Máximo sesiones por semana
            session_duration_minutes: Duración de sesiones en minutos
        
        Returns:
            Disponibilidad actualizada
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede actualizar esta disponibilidad")
        
        data = request.get_json()
        
        try:
            updated_availability = AllyService.update_availability(
                ally=ally,
                availability_data=data,
                updated_by=current_user.id
            )
            
            return {
                'message': 'Disponibilidad actualizada exitosamente',
                'availability': updated_availability
            }
            
        except Exception as e:
            current_app.logger.error(f"Error updating availability: {e}")
            raise BusinessLogicError("Error al actualizar disponibilidad")
    
    def _can_view_ally_availability(self, current_user: User, ally: Ally) -> bool:
        """Verifica permisos para ver disponibilidad"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver su propia disponibilidad
        if current_user.id == ally.user_id:
            return True
        
        # Emprendedores pueden ver disponibilidad de mentores disponibles
        if (current_user.user_type == 'entrepreneur' and 
            ally.available_for_mentorship):
            return True
        
        return False


class AllyMenteesResource(Resource):
    """Endpoint para gestión de mentees del aliado"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener mentees actuales del aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            status: Filtrar por estado de la relación
            include_inactive: Incluir relaciones inactivas
            sort_by: Ordenar por campo específico
        
        Returns:
            Lista de mentees
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No tiene permisos para ver estos mentees")
        
        status = request.args.get('status', 'active')
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'started_date')
        
        try:
            mentees = AllyService.get_mentees(
                ally=ally,
                status=status,
                include_inactive=include_inactive,
                sort_by=sort_by
            )
            
            return {
                'ally_id': ally_id,
                'mentees': mentees,
                'total_mentees': len(mentees),
                'active_mentees': len([m for m in mentees if m.get('status') == 'active']),
                'filters_applied': {
                    'status': status,
                    'include_inactive': include_inactive
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting mentees: {e}")
            raise BusinessLogicError("Error al obtener mentees")
    
    @api_auth_required
    @validate_json
    def post(self, ally_id):
        """
        Agregar nuevo mentee (para admin o casos especiales)
        
        Args:
            ally_id: ID del aliado
        
        Body:
            entrepreneur_id: ID del emprendedor
            mentorship_type: Tipo de mentoría
            areas_of_focus: Áreas de enfoque
            frequency: Frecuencia de sesiones
            duration_months: Duración esperada en meses
        
        Returns:
            Relación de mentoría creada
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Solo admin o el propio aliado pueden agregar mentees directamente
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede agregar mentees a este aliado")
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('entrepreneur_id'):
            raise ValidationError("entrepreneur_id es requerido")
        
        entrepreneur_id = data['entrepreneur_id']
        
        # Verificar que el emprendedor existe
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        try:
            mentorship = AllyService.create_mentorship_relationship(
                ally=ally,
                entrepreneur=entrepreneur,
                mentorship_data=data,
                created_by=current_user.id
            )
            
            return {
                'message': 'Relación de mentoría creada exitosamente',
                'mentorship': mentorship
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating mentorship: {e}")
            raise BusinessLogicError("Error al crear relación de mentoría")


class AllySessionsResource(Resource):
    """Endpoint para gestión de sesiones de mentoría del aliado"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener sesiones de mentoría del aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            status: Filtrar por estado (scheduled, completed, cancelled)
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango
            mentee_id: Filtrar por mentee específico
            limit: Límite de resultados
        
        Returns:
            Lista de sesiones de mentoría
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No tiene permisos para ver estas sesiones")
        
        # Parámetros de filtrado
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        mentee_id = request.args.get('mentee_id', type=int)
        limit = min(request.args.get('limit', 50, type=int), 200)
        
        try:
            sessions = AllyService.get_mentorship_sessions(
                ally=ally,
                filters={
                    'status': status,
                    'start_date': start_date,
                    'end_date': end_date,
                    'mentee_id': mentee_id
                },
                limit=limit
            )
            
            return {
                'ally_id': ally_id,
                'sessions': sessions,
                'total_sessions': len(sessions),
                'summary': AllyService.get_sessions_summary(ally),
                'filters_applied': {
                    'status': status,
                    'start_date': start_date,
                    'end_date': end_date,
                    'mentee_id': mentee_id
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting sessions: {e}")
            raise BusinessLogicError("Error al obtener sesiones")
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.MENTORSHIP_SESSION_CREATE, "Mentorship session scheduled")
    def post(self, ally_id):
        """
        Programar nueva sesión de mentoría
        
        Args:
            ally_id: ID del aliado
        
        Body:
            mentee_id: ID del mentee
            scheduled_at: Fecha y hora programada
            duration_minutes: Duración en minutos
            session_type: Tipo de sesión
            agenda: Agenda de la sesión
            meeting_link: Enlace de reunión (opcional)
            notes: Notas adicionales
        
        Returns:
            Sesión programada
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede programar sesiones para este aliado")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['mentee_id', 'scheduled_at', 'duration_minutes']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            session = AllyService.schedule_mentorship_session(
                ally=ally,
                session_data=data,
                scheduled_by=current_user.id
            )
            
            return {
                'message': 'Sesión programada exitosamente',
                'session': session
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error scheduling session: {e}")
            raise BusinessLogicError("Error al programar sesión")


class AllyRequestsResource(Resource):
    """Endpoint para gestión de solicitudes de mentoría"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener solicitudes de mentoría pendientes
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            status: Filtrar por estado (pending, accepted, rejected)
            sort_by: Ordenar por campo específico
        
        Returns:
            Lista de solicitudes de mentoría
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No tiene permisos para ver estas solicitudes")
        
        status = request.args.get('status', 'pending')
        sort_by = request.args.get('sort_by', 'created_at')
        
        try:
            requests = AllyService.get_mentorship_requests(
                ally=ally,
                status=status,
                sort_by=sort_by
            )
            
            return {
                'ally_id': ally_id,
                'requests': requests,
                'total_requests': len(requests),
                'pending_count': len([r for r in requests if r.get('status') == 'pending']),
                'filters_applied': {
                    'status': status
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting mentorship requests: {e}")
            raise BusinessLogicError("Error al obtener solicitudes de mentoría")
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.MENTORSHIP_ACCEPT, "Mentorship request response")
    def patch(self, ally_id):
        """
        Responder a solicitud de mentoría
        
        Args:
            ally_id: ID del aliado
        
        Body:
            request_id: ID de la solicitud
            action: Acción (accept/reject)
            response_message: Mensaje de respuesta
            mentorship_terms: Términos de la mentoría (si se acepta)
        
        Returns:
            Solicitud actualizada
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede responder solicitudes para este aliado")
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('request_id') or not data.get('action'):
            raise ValidationError("request_id y action son requeridos")
        
        request_id = data['request_id']
        action = data['action']
        
        if action not in ['accept', 'reject']:
            raise ValidationError("action debe ser 'accept' o 'reject'")
        
        try:
            response = AllyService.respond_to_mentorship_request(
                ally=ally,
                request_id=request_id,
                action=action,
                response_data=data,
                responded_by=current_user.id
            )
            
            return {
                'message': f'Solicitud {action}ed exitosamente',
                'request': response
            }
            
        except Exception as e:
            current_app.logger.error(f"Error responding to mentorship request: {e}")
            raise BusinessLogicError("Error al responder solicitud de mentoría")


class AllyReviewsResource(Resource):
    """Endpoint para gestión de reviews del aliado"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener reviews del aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            rating_min: Calificación mínima
            limit: Límite de resultados
            include_detailed: Incluir reviews detalladas
        
        Returns:
            Reviews del aliado
        """
        ally = Ally.query.get_or_404(ally_id)
        
        # Reviews son públicas si el perfil es público
        if not ally.user.is_public_profile:
            current_user = get_current_user()
            if not (current_user.is_admin() or current_user.id == ally.user_id):
                raise AuthorizationError("No tiene permisos para ver estas reviews")
        
        rating_min = request.args.get('rating_min', type=float)
        limit = min(request.args.get('limit', 20, type=int), 100)
        include_detailed = request.args.get('include_detailed', 'true').lower() == 'true'
        
        try:
            reviews = AllyService.get_reviews(
                ally=ally,
                rating_min=rating_min,
                limit=limit,
                include_detailed=include_detailed
            )
            
            return {
                'ally_id': ally_id,
                'reviews': reviews['reviews'],
                'summary': reviews['summary'],
                'total_reviews': reviews['total'],
                'average_rating': reviews['average_rating']
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting ally reviews: {e}")
            raise BusinessLogicError("Error al obtener reviews")


class AllyMetricsResource(Resource):
    """Endpoint para métricas e impacto del aliado"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener métricas de impacto del aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            period: Período de análisis (30d, 90d, 1y, all)
            metrics: Métricas específicas (comma-separated)
        
        Returns:
            Métricas de impacto
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No tiene permisos para ver estas métricas")
        
        period = request.args.get('period', '90d')
        specific_metrics = request.args.get('metrics', '').split(',') if request.args.get('metrics') else None
        
        try:
            metrics = AllyService.get_comprehensive_metrics(
                ally=ally,
                period=period,
                specific_metrics=specific_metrics
            )
            
            return {
                'ally_id': ally_id,
                'period': period,
                'metrics': metrics,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting ally metrics: {e}")
            raise BusinessLogicError("Error al obtener métricas")
    
    @api_auth_required
    @validate_json
    def post(self, ally_id):
        """
        Registrar métrica personalizada para el aliado
        
        Args:
            ally_id: ID del aliado
        
        Body:
            metric_name: Nombre de la métrica
            value: Valor de la métrica
            unit: Unidad de medida
            description: Descripción
            metadata: Metadatos adicionales
        
        Returns:
            Métrica registrada
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede registrar métricas para este aliado")
        
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['metric_name', 'value']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"El campo {field} es requerido")
        
        try:
            metric = AllyService.record_custom_metric(
                ally=ally,
                metric_data=data,
                recorded_by=current_user.id
            )
            
            return metric, 201
            
        except Exception as e:
            current_app.logger.error(f"Error recording metric: {e}")
            raise BusinessLogicError("Error al registrar métrica")


class AllyMatchingResource(Resource):
    """Endpoint para matching del aliado con emprendedores"""
    
    @api_auth_required
    def get(self, ally_id):
        """
        Obtener emprendedores recomendados para el aliado
        
        Args:
            ally_id: ID del aliado
        
        Query Parameters:
            limit: Límite de recomendaciones
            industry_match: Priorizar match por industria
            experience_match: Priorizar match por experiencia
            location_match: Priorizar match por ubicación
            stage_preference: Preferencia por etapa de negocio
        
        Returns:
            Lista de emprendedores recomendados
        """
        current_user = get_current_user()
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == ally.user_id):
            raise AuthorizationError("No puede ver recomendaciones para este aliado")
        
        limit = min(request.args.get('limit', 10, type=int), 50)
        industry_match = request.args.get('industry_match', 'true').lower() == 'true'
        experience_match = request.args.get('experience_match', 'true').lower() == 'true'
        location_match = request.args.get('location_match', 'false').lower() == 'true'
        stage_preference = request.args.get('stage_preference')
        
        try:
            recommendations = AllyService.get_entrepreneur_recommendations(
                ally=ally,
                limit=limit,
                filters={
                    'industry_match': industry_match,
                    'experience_match': experience_match,
                    'location_match': location_match,
                    'stage_preference': stage_preference
                }
            )
            
            return {
                'ally_id': ally_id,
                'recommendations': recommendations,
                'total_recommendations': len(recommendations),
                'filters_applied': {
                    'industry_match': industry_match,
                    'experience_match': experience_match,
                    'location_match': location_match,
                    'stage_preference': stage_preference
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting entrepreneur recommendations: {e}")
            raise BusinessLogicError("Error al obtener recomendaciones")


class AllySearchResource(Resource):
    """Endpoint para búsqueda avanzada de aliados"""
    
    @api_auth_required
    @validate_json
    def post(self):
        """
        Búsqueda avanzada de aliados/mentores
        
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
            results = AllyService.advanced_search(
                query=query_term,
                filters=filters,
                sort_options=sort_options,
                facets=facets,
                limit=limit,
                current_user=current_user
            )
            
            return {
                'results': results['allies'],
                'total': results['total'],
                'facets': results['facets'],
                'suggestions': results['suggestions'],
                'query': query_term,
                'filters_applied': filters
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in ally search: {e}")
            raise BusinessLogicError("Error en búsqueda de aliados")


class AllyStatsResource(Resource):
    """Endpoint para estadísticas de aliados"""
    
    @api_auth_required
    def get(self):
        """
        Obtener estadísticas generales de aliados
        
        Query Parameters:
            organization_id: Filtrar por organización
            program_id: Filtrar por programa
            period: Período de análisis
            breakdown_by: Agrupar por campo específico
        
        Returns:
            Estadísticas de aliados
        """
        current_user = get_current_user()
        
        # Solo admin o usuarios con permisos específicos
        if not (current_user.is_admin() or current_user.has_permission('access_analytics')):
            raise AuthorizationError("No tiene permisos para ver estadísticas")
        
        organization_id = request.args.get('organization_id', type=int)
        program_id = request.args.get('program_id', type=int)
        period = request.args.get('period', '30d')
        breakdown_by = request.args.get('breakdown_by', 'expertise_area')
        
        try:
            stats = AllyService.get_comprehensive_statistics(
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
            current_app.logger.error(f"Error getting ally statistics: {e}")
            raise BusinessLogicError("Error al obtener estadísticas")


# Registrar recursos en la API
api.add_resource(AlliesListResource, '')
api.add_resource(AllyDetailResource, '/<int:ally_id>')
api.add_resource(AllyAvailabilityResource, '/<int:ally_id>/availability')
api.add_resource(AllyMenteesResource, '/<int:ally_id>/mentees')
api.add_resource(AllySessionsResource, '/<int:ally_id>/sessions')
api.add_resource(AllyRequestsResource, '/<int:ally_id>/requests')
api.add_resource(AllyReviewsResource, '/<int:ally_id>/reviews')
api.add_resource(AllyMetricsResource, '/<int:ally_id>/metrics')
api.add_resource(AllyMatchingResource, '/<int:ally_id>/matching')
api.add_resource(AllySearchResource, '/search')
api.add_resource(AllyStatsResource, '/statistics')


# Endpoints adicionales específicos para aliados
@allies_bp.route('/<int:ally_id>/calendar-integration', methods=['GET', 'POST', 'DELETE'])
@api_auth_required
def calendar_integration(ally_id):
    """Gestión de integración con calendario"""
    current_user = get_current_user()
    ally = Ally.query.get_or_404(ally_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == ally.user_id):
        raise AuthorizationError("No tiene permisos para gestionar esta integración")
    
    if request.method == 'GET':
        # Obtener estado de integración
        integration_status = AllyService.get_calendar_integration_status(ally)
        return jsonify({
            'ally_id': ally_id,
            'integration': integration_status,
            'available_providers': ['google', 'outlook', 'apple']
        })
    
    elif request.method == 'POST':
        # Configurar integración
        data = request.get_json()
        provider = data.get('provider')
        
        if provider not in ['google', 'outlook', 'apple']:
            raise ValidationError("Proveedor de calendario no válido")
        
        try:
            integration = AllyService.setup_calendar_integration(
                ally=ally,
                provider=provider,
                auth_data=data,
                setup_by=current_user.id
            )
            
            return jsonify({
                'message': 'Integración de calendario configurada',
                'integration': integration
            }), 201
            
        except Exception as e:
            current_app.logger.error(f"Error setting up calendar integration: {e}")
            raise BusinessLogicError("Error al configurar integración de calendario")
    
    elif request.method == 'DELETE':
        # Eliminar integración
        try:
            AllyService.remove_calendar_integration(
                ally=ally,
                removed_by=current_user.id
            )
            
            return jsonify({
                'message': 'Integración de calendario eliminada'
            })
            
        except Exception as e:
            current_app.logger.error(f"Error removing calendar integration: {e}")
            raise BusinessLogicError("Error al eliminar integración de calendario")


@allies_bp.route('/<int:ally_id>/mentoring-toolkit', methods=['GET'])
@api_auth_required
def mentoring_toolkit(ally_id):
    """Obtener herramientas y recursos para mentoría"""
    current_user = get_current_user()
    ally = Ally.query.get_or_404(ally_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == ally.user_id):
        raise AuthorizationError("No tiene permisos para acceder a estas herramientas")
    
    try:
        toolkit = AllyService.get_mentoring_toolkit(ally)
        
        return jsonify({
            'ally_id': ally_id,
            'toolkit': {
                'session_templates': toolkit['session_templates'],
                'assessment_tools': toolkit['assessment_tools'],
                'goal_tracking': toolkit['goal_tracking'],
                'resource_library': toolkit['resource_library'],
                'communication_templates': toolkit['communication_templates'],
                'progress_reports': toolkit['progress_reports']
            },
            'recommendations': AllyService.get_toolkit_recommendations(ally)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting mentoring toolkit: {e}")
        raise BusinessLogicError("Error al obtener herramientas de mentoría")


@allies_bp.route('/<int:ally_id>/impact-report', methods=['GET'])
@api_auth_required
def impact_report(ally_id):
    """Generar reporte de impacto del aliado"""
    current_user = get_current_user()
    ally = Ally.query.get_or_404(ally_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == ally.user_id):
        raise AuthorizationError("No tiene permisos para ver este reporte")
    
    period = request.args.get('period', '1y')
    format_type = request.args.get('format', 'json')  # json, pdf
    
    try:
        report = AllyService.generate_impact_report(
            ally=ally,
            period=period,
            format_type=format_type
        )
        
        if format_type == 'pdf':
            return send_file(
                report['file_path'],
                as_attachment=True,
                download_name=f'impact_report_{ally_id}_{period}.pdf'
            )
        else:
            return jsonify({
                'ally_id': ally_id,
                'period': period,
                'report': report,
                'generated_at': datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        current_app.logger.error(f"Error generating impact report: {e}")
        raise BusinessLogicError("Error al generar reporte de impacto")


@allies_bp.route('/<int:ally_id>/professional-development', methods=['GET', 'POST'])
@api_auth_required
def professional_development(ally_id):
    """Gestión de desarrollo profesional del aliado"""
    current_user = get_current_user()
    ally = Ally.query.get_or_404(ally_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == ally.user_id):
        raise AuthorizationError("No tiene permisos para gestionar este desarrollo")
    
    if request.method == 'GET':
        # Obtener plan de desarrollo
        development_plan = AllyService.get_professional_development_plan(ally)
        
        return jsonify({
            'ally_id': ally_id,
            'development_plan': development_plan,
            'recommendations': AllyService.get_development_recommendations(ally),
            'available_resources': AllyService.get_available_development_resources()
        })
    
    elif request.method == 'POST':
        # Actualizar plan de desarrollo
        data = request.get_json()
        
        try:
            updated_plan = AllyService.update_professional_development_plan(
                ally=ally,
                plan_data=data,
                updated_by=current_user.id
            )
            
            return jsonify({
                'message': 'Plan de desarrollo actualizado',
                'development_plan': updated_plan
            })
            
        except Exception as e:
            current_app.logger.error(f"Error updating development plan: {e}")
            raise BusinessLogicError("Error al actualizar plan de desarrollo")


@allies_bp.route('/config', methods=['GET'])
@api_auth_required
def get_ally_config():
    """Obtener configuraciones disponibles para aliados"""
    return jsonify({
        'expertise_areas': [
            {'value': area, 'label': area.replace('_', ' ').title()}
            for area in AllyConfig.EXPERTISE_AREAS
        ],
        'mentorship_types': [
            {'value': m_type, 'label': m_type.replace('_', ' ').title()}
            for m_type in AllyConfig.MENTORSHIP_TYPES
        ],
        'experience_levels': [
            {'value': level, 'label': level.replace('_', ' ').title()}
            for level in AllyConfig.EXPERIENCE_LEVELS
        ],
        'mentoring_frequencies': [
            {'value': freq, 'label': freq.replace('_', ' ').title()}
            for freq in AllyConfig.MENTORING_FREQUENCIES
        ],
        'communication_methods': [
            {'value': method, 'label': method.replace('_', ' ').title()}
            for method in AllyConfig.COMMUNICATION_METHODS
        ],
        'availability_status': [
            {'value': status, 'label': status.replace('_', ' ').title()}
            for status in AllyConfig.AVAILABILITY_STATUS
        ]
    })


@allies_bp.route('/dashboard-insights', methods=['GET'])
@api_auth_required
def get_ally_dashboard_insights():
    """Obtener insights para dashboard de aliados"""
    current_user = get_current_user()
    
    # Solo para usuarios de tipo aliado o admin
    if current_user.user_type != 'ally' and not current_user.is_admin():
        raise AuthorizationError("Acceso limitado a aliados")
    
    try:
        if current_user.user_type == 'ally':
            # Insights personalizados para el aliado actual
            ally = Ally.query.filter_by(user_id=current_user.id).first()
            if not ally:
                raise ResourceNotFoundError("Perfil de aliado no encontrado")
            
            insights = AllyService.get_personalized_insights(ally)
        else:
            # Insights generales para admin
            insights = AllyService.get_global_insights()
        
        return jsonify({
            'insights': insights,
            'generated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting ally dashboard insights: {e}")
        raise BusinessLogicError("Error al obtener insights del dashboard")


# Funciones auxiliares para otros módulos
def get_ally_summary(ally_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene resumen de un aliado
    
    Args:
        ally_id: ID del aliado
        
    Returns:
        Resumen del aliado o None si no existe
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get(ally_id)
    
    if not ally:
        return None
    
    return {
        'id': ally.id,
        'user_id': ally.user_id,
        'name': ally.user.full_name,
        'title': ally.title,
        'organization': ally.organization,
        'expertise_areas': ally.expertise_areas,
        'years_experience': ally.years_experience,
        'experience_level': ally.experience_level,
        'available_for_mentorship': ally.available_for_mentorship,
        'average_rating': ally.average_rating,
        'total_mentees': ally.total_mentees,
        'sessions_completed': ally.sessions_completed
    }


def check_ally_availability(ally_id: int, requested_datetime: datetime) -> bool:
    """
    Verifica disponibilidad de un aliado en fecha/hora específica
    
    Args:
        ally_id: ID del aliado
        requested_datetime: Fecha y hora solicitada
        
    Returns:
        True si está disponible
    """
    ally = Ally.query.get(ally_id)
    if not ally:
        return False
    
    return AllyService.check_availability(ally, requested_datetime)


# Exportaciones para otros módulos
__all__ = [
    'allies_bp',
    'AllyConfig',
    'get_ally_summary',
    'check_ally_availability'
]