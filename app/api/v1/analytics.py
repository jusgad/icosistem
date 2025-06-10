"""
API endpoints para analytics y métricas del ecosistema de emprendimiento.
Proporciona insights detallados sobre usuarios, proyectos, mentorías y actividad general.
Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from sqlalchemy import func, case, extract, and_, or_, text
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Tuple, Any
import json
from collections import defaultdict
from functools import wraps

# Importaciones locales
from app.models.user import User, UserType
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.project import Project, ProjectStatus
from app.models.mentorship import Mentorship, MentorshipStatus
from app.models.meeting import Meeting, MeetingStatus
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.task import Task, TaskStatus
from app.models.notification import Notification
from app.models.activity_log import ActivityLog, ActivityType
from app.models.organization import Organization
from app.models.program import Program
from app.core.permissions import require_permission
from app.core.exceptions import ValidationException, AuthorizationException
from app.utils.decorators import api_response, rate_limit, cache_response
from app.utils.formatters import format_currency, format_percentage, format_duration
from app.utils.date_utils import get_date_range, get_period_comparison
from app.services.analytics_service import AnalyticsService
from app.extensions import db, cache

# Blueprint para analytics
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')

# Configuración de cache
CACHE_TIMEOUT = 300  # 5 minutos
HEAVY_QUERY_CACHE_TIMEOUT = 900  # 15 minutos

# Schemas de validación
class DateRangeSchema(Schema):
    """Schema para validar rangos de fechas."""
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    compare_previous = fields.Bool(missing=False)
    
    def validate_date_range(self, data, **kwargs):
        if data['start_date'] > data['end_date']:
            raise ValidationError("start_date debe ser anterior a end_date")
        if data['start_date'] > date.today():
            raise ValidationError("start_date no puede ser futura")

class AnalyticsFilterSchema(Schema):
    """Schema para filtros de analytics."""
    start_date = fields.Date(missing=lambda: date.today() - timedelta(days=30))
    end_date = fields.Date(missing=lambda: date.today())
    organization_id = fields.Int(missing=None, allow_none=True)
    program_id = fields.Int(missing=None, allow_none=True)
    user_type = fields.Str(validate=validate.OneOf([t.value for t in UserType]))
    project_status = fields.Str(validate=validate.OneOf([s.value for s in ProjectStatus]))
    granularity = fields.Str(
        missing='day',
        validate=validate.OneOf(['hour', 'day', 'week', 'month', 'quarter', 'year'])
    )
    compare_previous = fields.Bool(missing=False)
    include_details = fields.Bool(missing=False)

class ReportSchema(Schema):
    """Schema para generación de reportes."""
    report_type = fields.Str(
        required=True,
        validate=validate.OneOf([
            'users', 'projects', 'mentorships', 'activities', 
            'financial', 'impact', 'engagement', 'custom'
        ])
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    filters = fields.Dict(missing={})
    format = fields.Str(
        missing='json',
        validate=validate.OneOf(['json', 'csv', 'excel', 'pdf'])
    )
    include_charts = fields.Bool(missing=True)
    email_recipients = fields.List(fields.Email(), missing=[])

# Funciones auxiliares
def get_current_user() -> User:
    """Obtiene el usuario actual."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        raise AuthorizationException("Usuario no encontrado")
    return user

def check_analytics_permission(user: User, scope: str = 'basic') -> bool:
    """Verifica permisos de analytics según el alcance."""
    if user.is_admin():
        return True
    
    if scope == 'basic':
        return True  # Todos pueden ver analytics básicos
    elif scope == 'advanced':
        return user.user_type in [UserType.ADMIN, UserType.CLIENT]
    elif scope == 'financial':
        return user.user_type == UserType.ADMIN
    elif scope == 'system':
        return user.user_type == UserType.ADMIN
    
    return False

def apply_user_filters(query, user: User, model_class):
    """Aplica filtros según permisos del usuario."""
    if user.is_admin():
        return query
    
    if user.user_type == UserType.ENTREPRENEUR:
        if hasattr(user, 'entrepreneur') and user.entrepreneur:
            # Solo datos del emprendedor
            if model_class == Project:
                query = query.filter(Project.entrepreneur_id == user.entrepreneur.id)
            elif model_class == Document:
                query = query.filter(Document.owner_id == user.id)
    
    elif user.user_type == UserType.ALLY:
        if hasattr(user, 'ally') and user.ally:
            # Datos de emprendedores que mentorea
            entrepreneur_ids = [e.id for e in user.ally.entrepreneurs]
            if model_class == Project:
                query = query.filter(Project.entrepreneur_id.in_(entrepreneur_ids))
    
    elif user.user_type == UserType.CLIENT:
        # Clientes ven datos de sus organizaciones/programas
        if hasattr(user, 'client') and user.client:
            org_ids = [org.id for org in user.client.organizations]
            if model_class == Project and org_ids:
                query = query.join(Entrepreneur).join(Organization).filter(
                    Organization.id.in_(org_ids)
                )
    
    return query

def calculate_growth_rate(current: float, previous: float) -> float:
    """Calcula tasa de crecimiento."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 2)

def generate_time_series(start_date: date, end_date: date, granularity: str) -> List[Dict]:
    """Genera serie temporal para gráficos."""
    series = []
    current = start_date
    
    while current <= end_date:
        series.append({
            'date': current.isoformat(),
            'timestamp': int(current.strftime('%s')) * 1000
        })
        
        if granularity == 'day':
            current += timedelta(days=1)
        elif granularity == 'week':
            current += timedelta(weeks=1)
        elif granularity == 'month':
            current += relativedelta(months=1)
        elif granularity == 'quarter':
            current += relativedelta(months=3)
        elif granularity == 'year':
            current += relativedelta(years=1)
    
    return series

# Endpoints principales

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@cache_response(timeout=CACHE_TIMEOUT)
@api_response
def get_dashboard():
    """
    Obtiene métricas del dashboard principal.
    
    Query parameters:
    - start_date: Fecha inicio (YYYY-MM-DD)
    - end_date: Fecha fin (YYYY-MM-DD)
    - compare_previous: Comparar con período anterior
    """
    try:
        current_user = get_current_user()
        
        # Validar parámetros
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        analytics_service = AnalyticsService()
        
        # Métricas básicas
        metrics = {
            'overview': analytics_service.get_overview_metrics(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            ),
            'users': analytics_service.get_user_metrics(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            ),
            'projects': analytics_service.get_project_metrics(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            ),
            'activity': analytics_service.get_activity_metrics(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            )
        }
        
        # Comparación con período anterior si se solicita
        if filters['compare_previous']:
            days_diff = (filters['end_date'] - filters['start_date']).days
            prev_start = filters['start_date'] - timedelta(days=days_diff + 1)
            prev_end = filters['start_date'] - timedelta(days=1)
            
            prev_metrics = analytics_service.get_overview_metrics(
                start_date=prev_start,
                end_date=prev_end,
                user=current_user
            )
            
            metrics['comparison'] = {
                'period': f"{prev_start} to {prev_end}",
                'growth_rates': {
                    'users': calculate_growth_rate(
                        metrics['overview']['total_users'],
                        prev_metrics['total_users']
                    ),
                    'projects': calculate_growth_rate(
                        metrics['overview']['total_projects'],
                        prev_metrics['total_projects']
                    ),
                    'active_sessions': calculate_growth_rate(
                        metrics['activity']['active_sessions'],
                        prev_metrics.get('active_sessions', 0)
                    )
                }
            }
        
        return {
            'dashboard': metrics,
            'period': f"{filters['start_date']} to {filters['end_date']}",
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error obteniendo dashboard: {str(e)}")
        raise

@analytics_bp.route('/users', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@cache_response(timeout=CACHE_TIMEOUT)
@api_response
def get_user_analytics():
    """
    Analytics detallados de usuarios.
    
    Query parameters:
    - start_date, end_date: Rango de fechas
    - user_type: Filtrar por tipo de usuario
    - organization_id: Filtrar por organización
    - granularity: Granularidad temporal (day, week, month)
    """
    try:
        current_user = get_current_user()
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        # Query base de usuarios
        query = User.query.filter(
            User.created_at.between(filters['start_date'], filters['end_date'])
        )
        
        # Aplicar filtros de usuario
        query = apply_user_filters(query, current_user, User)
        
        if filters.get('user_type'):
            query = query.filter(User.user_type == filters['user_type'])
        
        # Métricas por tipo de usuario
        user_type_stats = db.session.query(
            User.user_type,
            func.count(User.id).label('count'),
            func.count(case([(User.is_active == True, 1)])).label('active_count'),
            func.avg(
                func.extract('epoch', func.now() - User.last_login_at) / 86400
            ).label('avg_days_since_login')
        ).filter(
            User.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(User.user_type).all()
        
        # Serie temporal de registros
        if filters['granularity'] == 'day':
            date_trunc = func.date(User.created_at)
        elif filters['granularity'] == 'week':
            date_trunc = func.date_trunc('week', User.created_at)
        elif filters['granularity'] == 'month':
            date_trunc = func.date_trunc('month', User.created_at)
        
        registration_timeline = db.session.query(
            date_trunc.label('period'),
            User.user_type,
            func.count(User.id).label('registrations')
        ).filter(
            User.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(date_trunc, User.user_type).all()
        
        # Métricas de actividad por usuario
        activity_stats = db.session.query(
            User.user_type,
            func.avg(func.extract('epoch', func.now() - User.last_login_at) / 86400).label('avg_inactive_days'),
            func.count(case([(User.last_login_at >= datetime.utcnow() - timedelta(days=7), 1)])).label('active_last_week'),
            func.count(case([(User.last_login_at >= datetime.utcnow() - timedelta(days=30), 1)])).label('active_last_month')
        ).group_by(User.user_type).all()
        
        # Top usuarios por actividad (solo para admin)
        top_users = []
        if check_analytics_permission(current_user, 'advanced'):
            top_users = db.session.query(
                User.id,
                User.email,
                User.user_type,
                func.count(ActivityLog.id).label('activity_count')
            ).join(ActivityLog).filter(
                ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
            ).group_by(User.id, User.email, User.user_type).order_by(
                func.count(ActivityLog.id).desc()
            ).limit(10).all()
        
        return {
            'user_analytics': {
                'summary': {
                    'total_users': query.count(),
                    'active_users': query.filter(User.is_active == True).count(),
                    'new_registrations': len(registration_timeline)
                },
                'by_type': [
                    {
                        'user_type': stat.user_type.value,
                        'total_count': stat.count,
                        'active_count': stat.active_count,
                        'avg_days_since_login': round(stat.avg_days_since_login or 0, 1)
                    }
                    for stat in user_type_stats
                ],
                'registration_timeline': [
                    {
                        'period': reg.period.isoformat() if hasattr(reg.period, 'isoformat') else str(reg.period),
                        'user_type': reg.user_type.value,
                        'registrations': reg.registrations
                    }
                    for reg in registration_timeline
                ],
                'activity_metrics': [
                    {
                        'user_type': stat.user_type.value,
                        'avg_inactive_days': round(stat.avg_inactive_days or 0, 1),
                        'active_last_week': stat.active_last_week,
                        'active_last_month': stat.active_last_month
                    }
                    for stat in activity_stats
                ],
                'top_active_users': [
                    {
                        'user_id': user.id,
                        'email': user.email[:20] + '...' if len(user.email) > 20 else user.email,
                        'user_type': user.user_type.value,
                        'activity_count': user.activity_count
                    }
                    for user in top_users
                ] if check_analytics_permission(current_user, 'advanced') else []
            },
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error en analytics de usuarios: {str(e)}")
        raise

@analytics_bp.route('/projects', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@cache_response(timeout=CACHE_TIMEOUT)
@api_response
def get_project_analytics():
    """Analytics detallados de proyectos."""
    try:
        current_user = get_current_user()
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        # Query base de proyectos
        query = Project.query.filter(
            Project.created_at.between(filters['start_date'], filters['end_date'])
        )
        
        query = apply_user_filters(query, current_user, Project)
        
        if filters.get('project_status'):
            query = query.filter(Project.status == filters['project_status'])
        
        # Métricas por estado
        status_stats = db.session.query(
            Project.status,
            func.count(Project.id).label('count'),
            func.avg(Project.progress_percentage).label('avg_progress'),
            func.avg(
                func.extract('epoch', func.now() - Project.created_at) / 86400
            ).label('avg_age_days')
        ).filter(
            Project.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(Project.status).all()
        
        # Distribución por sector/industria
        sector_stats = db.session.query(
            Project.sector,
            func.count(Project.id).label('count'),
            func.avg(Project.progress_percentage).label('avg_progress')
        ).filter(
            Project.created_at.between(filters['start_date'], filters['end_date']),
            Project.sector.isnot(None)
        ).group_by(Project.sector).all()
        
        # Proyectos por rango de progreso
        progress_ranges = [
            (0, 25, 'Inicio'),
            (26, 50, 'Desarrollo'),
            (51, 75, 'Avanzado'),
            (76, 100, 'Casi completado')
        ]
        
        progress_distribution = []
        for min_prog, max_prog, label in progress_ranges:
            count = Project.query.filter(
                Project.progress_percentage.between(min_prog, max_prog),
                Project.created_at.between(filters['start_date'], filters['end_date'])
            ).count()
            progress_distribution.append({
                'range': f"{min_prog}-{max_prog}%",
                'label': label,
                'count': count
            })
        
        # Timeline de creación de proyectos
        if filters['granularity'] == 'day':
            date_trunc = func.date(Project.created_at)
        elif filters['granularity'] == 'week':
            date_trunc = func.date_trunc('week', Project.created_at)
        elif filters['granularity'] == 'month':
            date_trunc = func.date_trunc('month', Project.created_at)
        
        project_timeline = db.session.query(
            date_trunc.label('period'),
            func.count(Project.id).label('projects_created'),
            func.avg(Project.progress_percentage).label('avg_progress')
        ).filter(
            Project.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        # Métricas financieras (solo admin)
        financial_metrics = {}
        if check_analytics_permission(current_user, 'financial'):
            financial_metrics = {
                'total_funding_requested': db.session.query(
                    func.sum(Project.funding_goal)
                ).filter(
                    Project.created_at.between(filters['start_date'], filters['end_date'])
                ).scalar() or 0,
                'total_funding_received': db.session.query(
                    func.sum(Project.funding_received)
                ).filter(
                    Project.created_at.between(filters['start_date'], filters['end_date'])
                ).scalar() or 0,
                'avg_funding_goal': db.session.query(
                    func.avg(Project.funding_goal)
                ).filter(
                    Project.created_at.between(filters['start_date'], filters['end_date'])
                ).scalar() or 0
            }
        
        # Top proyectos por progreso
        top_projects = Project.query.filter(
            Project.created_at.between(filters['start_date'], filters['end_date'])
        ).order_by(Project.progress_percentage.desc()).limit(10).all()
        
        return {
            'project_analytics': {
                'summary': {
                    'total_projects': query.count(),
                    'active_projects': query.filter(Project.status == ProjectStatus.ACTIVE).count(),
                    'completed_projects': query.filter(Project.status == ProjectStatus.COMPLETED).count(),
                    'avg_progress': round(
                        query.with_entities(func.avg(Project.progress_percentage)).scalar() or 0, 1
                    )
                },
                'by_status': [
                    {
                        'status': stat.status.value,
                        'count': stat.count,
                        'avg_progress': round(stat.avg_progress or 0, 1),
                        'avg_age_days': round(stat.avg_age_days or 0, 1)
                    }
                    for stat in status_stats
                ],
                'by_sector': [
                    {
                        'sector': stat.sector,
                        'count': stat.count,
                        'avg_progress': round(stat.avg_progress or 0, 1)
                    }
                    for stat in sector_stats
                ],
                'progress_distribution': progress_distribution,
                'creation_timeline': [
                    {
                        'period': timeline.period.isoformat() if hasattr(timeline.period, 'isoformat') else str(timeline.period),
                        'projects_created': timeline.projects_created,
                        'avg_progress': round(timeline.avg_progress or 0, 1)
                    }
                    for timeline in project_timeline
                ],
                'financial_metrics': financial_metrics,
                'top_projects': [
                    {
                        'id': project.id,
                        'name': project.name,
                        'progress': project.progress_percentage,
                        'status': project.status.value,
                        'entrepreneur': project.entrepreneur.user.get_display_name()
                    }
                    for project in top_projects
                ] if check_analytics_permission(current_user, 'advanced') else []
            },
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error en analytics de proyectos: {str(e)}")
        raise

@analytics_bp.route('/mentorships', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@cache_response(timeout=CACHE_TIMEOUT)
@api_response
def get_mentorship_analytics():
    """Analytics de sesiones de mentoría."""
    try:
        current_user = get_current_user()
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        # Query base de mentorías
        query = Mentorship.query.filter(
            Mentorship.created_at.between(filters['start_date'], filters['end_date'])
        )
        
        # Aplicar filtros según tipo de usuario
        if current_user.user_type == UserType.ALLY and hasattr(current_user, 'ally'):
            query = query.filter(Mentorship.ally_id == current_user.ally.id)
        elif current_user.user_type == UserType.ENTREPRENEUR and hasattr(current_user, 'entrepreneur'):
            query = query.filter(Mentorship.entrepreneur_id == current_user.entrepreneur.id)
        
        # Estadísticas por estado
        status_stats = db.session.query(
            Mentorship.status,
            func.count(Mentorship.id).label('count'),
            func.avg(Mentorship.duration_hours).label('avg_duration'),
            func.sum(Mentorship.duration_hours).label('total_hours')
        ).filter(
            Mentorship.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(Mentorship.status).all()
        
        # Efectividad de mentorías (basada en ratings)
        effectiveness_stats = db.session.query(
            func.avg(Mentorship.entrepreneur_rating).label('avg_entrepreneur_rating'),
            func.avg(Mentorship.ally_rating).label('avg_ally_rating'),
            func.count(case([(Mentorship.entrepreneur_rating >= 4, 1)])).label('positive_ratings'),
            func.count(Mentorship.id).label('total_rated')
        ).filter(
            Mentorship.created_at.between(filters['start_date'], filters['end_date']),
            Mentorship.entrepreneur_rating.isnot(None)
        ).first()
        
        # Top aliados por horas de mentoría
        top_allies = db.session.query(
            Ally.id,
            User.email,
            func.sum(Mentorship.duration_hours).label('total_hours'),
            func.count(Mentorship.id).label('session_count'),
            func.avg(Mentorship.ally_rating).label('avg_rating')
        ).join(User).join(Mentorship).filter(
            Mentorship.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(Ally.id, User.email).order_by(
            func.sum(Mentorship.duration_hours).desc()
        ).limit(10).all()
        
        # Distribución de horas por día de la semana
        weekday_distribution = db.session.query(
            func.extract('dow', Mentorship.session_date).label('weekday'),
            func.sum(Mentorship.duration_hours).label('total_hours'),
            func.count(Mentorship.id).label('session_count')
        ).filter(
            Mentorship.created_at.between(filters['start_date'], filters['end_date']),
            Mentorship.session_date.isnot(None)
        ).group_by(func.extract('dow', Mentorship.session_date)).all()
        
        weekday_names = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
        
        return {
            'mentorship_analytics': {
                'summary': {
                    'total_sessions': query.count(),
                    'completed_sessions': query.filter(Mentorship.status == MentorshipStatus.COMPLETED).count(),
                    'total_hours': round(
                        query.with_entities(func.sum(Mentorship.duration_hours)).scalar() or 0, 1
                    ),
                    'avg_session_duration': round(
                        query.with_entities(func.avg(Mentorship.duration_hours)).scalar() or 0, 1
                    ),
                    'avg_effectiveness': round(
                        effectiveness_stats.avg_entrepreneur_rating or 0, 2
                    )
                },
                'by_status': [
                    {
                        'status': stat.status.value,
                        'count': stat.count,
                        'avg_duration': round(stat.avg_duration or 0, 1),
                        'total_hours': round(stat.total_hours or 0, 1)
                    }
                    for stat in status_stats
                ],
                'effectiveness': {
                    'avg_entrepreneur_rating': round(effectiveness_stats.avg_entrepreneur_rating or 0, 2),
                    'avg_ally_rating': round(effectiveness_stats.avg_ally_rating or 0, 2),
                    'satisfaction_rate': round(
                        (effectiveness_stats.positive_ratings / effectiveness_stats.total_rated * 100) 
                        if effectiveness_stats.total_rated > 0 else 0, 1
                    ),
                    'total_rated_sessions': effectiveness_stats.total_rated
                },
                'top_allies': [
                    {
                        'ally_id': ally.id,
                        'email': ally.email[:20] + '...' if len(ally.email) > 20 else ally.email,
                        'total_hours': round(ally.total_hours or 0, 1),
                        'session_count': ally.session_count,
                        'avg_rating': round(ally.avg_rating or 0, 2)
                    }
                    for ally in top_allies
                ] if check_analytics_permission(current_user, 'advanced') else [],
                'weekday_distribution': [
                    {
                        'weekday': weekday_names[int(dist.weekday)],
                        'total_hours': round(dist.total_hours or 0, 1),
                        'session_count': dist.session_count
                    }
                    for dist in weekday_distribution
                ]
            },
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error en analytics de mentorías: {str(e)}")
        raise

@analytics_bp.route('/activities', methods=['GET'])
@jwt_required()
@rate_limit(30, per=60)
@cache_response(timeout=CACHE_TIMEOUT)
@api_response
def get_activity_analytics():
    """Analytics de actividad del sistema."""
    try:
        current_user = get_current_user()
        
        if not check_analytics_permission(current_user, 'advanced'):
            raise AuthorizationException("Sin permisos para ver analytics de actividad")
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        # Actividades por tipo
        activity_type_stats = db.session.query(
            ActivityLog.activity_type,
            func.count(ActivityLog.id).label('count'),
            func.count(func.distinct(ActivityLog.user_id)).label('unique_users')
        ).filter(
            ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(ActivityLog.activity_type).all()
        
        # Timeline de actividad
        if filters['granularity'] == 'day':
            date_trunc = func.date(ActivityLog.created_at)
        elif filters['granularity'] == 'week':
            date_trunc = func.date_trunc('week', ActivityLog.created_at)
        elif filters['granularity'] == 'month':
            date_trunc = func.date_trunc('month', ActivityLog.created_at)
        
        activity_timeline = db.session.query(
            date_trunc.label('period'),
            ActivityLog.activity_type,
            func.count(ActivityLog.id).label('activity_count')
        ).filter(
            ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(date_trunc, ActivityLog.activity_type).order_by(date_trunc).all()
        
        # Usuarios más activos
        most_active_users = db.session.query(
            User.id,
            User.email,
            User.user_type,
            func.count(ActivityLog.id).label('activity_count'),
            func.max(ActivityLog.created_at).label('last_activity')
        ).join(ActivityLog).filter(
            ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(User.id, User.email, User.user_type).order_by(
            func.count(ActivityLog.id).desc()
        ).limit(15).all()
        
        # Actividad por hora del día
        hourly_activity = db.session.query(
            func.extract('hour', ActivityLog.created_at).label('hour'),
            func.count(ActivityLog.id).label('activity_count')
        ).filter(
            ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
        ).group_by(func.extract('hour', ActivityLog.created_at)).all()
        
        return {
            'activity_analytics': {
                'summary': {
                    'total_activities': ActivityLog.query.filter(
                        ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
                    ).count(),
                    'unique_active_users': db.session.query(
                        func.count(func.distinct(ActivityLog.user_id))
                    ).filter(
                        ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
                    ).scalar(),
                    'avg_activities_per_user': round(
                        db.session.query(func.avg(
                            db.session.query(func.count(ActivityLog.id)).filter(
                                ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
                            ).group_by(ActivityLog.user_id).subquery().c.count
                        )).scalar() or 0, 1
                    )
                },
                'by_type': [
                    {
                        'activity_type': stat.activity_type.value,
                        'count': stat.count,
                        'unique_users': stat.unique_users
                    }
                    for stat in activity_type_stats
                ],
                'timeline': [
                    {
                        'period': timeline.period.isoformat() if hasattr(timeline.period, 'isoformat') else str(timeline.period),
                        'activity_type': timeline.activity_type.value,
                        'count': timeline.activity_count
                    }
                    for timeline in activity_timeline
                ],
                'most_active_users': [
                    {
                        'user_id': user.id,
                        'email': user.email[:25] + '...' if len(user.email) > 25 else user.email,
                        'user_type': user.user_type.value,
                        'activity_count': user.activity_count,
                        'last_activity': user.last_activity.isoformat()
                    }
                    for user in most_active_users
                ],
                'hourly_distribution': [
                    {
                        'hour': int(hour_stat.hour),
                        'activity_count': hour_stat.activity_count
                    }
                    for hour_stat in hourly_activity
                ]
            },
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error en analytics de actividad: {str(e)}")
        raise

@analytics_bp.route('/engagement', methods=['GET'])
@jwt_required()
@rate_limit(20, per=60)
@cache_response(timeout=HEAVY_QUERY_CACHE_TIMEOUT)
@api_response
def get_engagement_analytics():
    """Analytics de engagement y participación."""
    try:
        current_user = get_current_user()
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        # Métricas de documentos
        document_stats = {
            'total_uploads': Document.query.filter(
                Document.created_at.between(filters['start_date'], filters['end_date'])
            ).count(),
            'total_downloads': db.session.query(
                func.sum(Document.download_count)
            ).filter(
                Document.created_at.between(filters['start_date'], filters['end_date'])
            ).scalar() or 0,
            'most_downloaded': Document.query.filter(
                Document.created_at.between(filters['start_date'], filters['end_date'])
            ).order_by(Document.download_count.desc()).limit(5).all()
        }
        
        # Métricas de reuniones
        meeting_stats = {
            'total_scheduled': Meeting.query.filter(
                Meeting.created_at.between(filters['start_date'], filters['end_date'])
            ).count(),
            'completed_meetings': Meeting.query.filter(
                Meeting.created_at.between(filters['start_date'], filters['end_date']),
                Meeting.status == MeetingStatus.COMPLETED
            ).count(),
            'avg_duration': db.session.query(
                func.avg(Meeting.duration_minutes)
            ).filter(
                Meeting.created_at.between(filters['start_date'], filters['end_date']),
                Meeting.status == MeetingStatus.COMPLETED
            ).scalar() or 0
        }
        
        # Métricas de tareas
        task_stats = {
            'total_created': Task.query.filter(
                Task.created_at.between(filters['start_date'], filters['end_date'])
            ).count(),
            'completed_tasks': Task.query.filter(
                Task.created_at.between(filters['start_date'], filters['end_date']),
                Task.status == TaskStatus.COMPLETED
            ).count(),
            'completion_rate': 0
        }
        
        if task_stats['total_created'] > 0:
            task_stats['completion_rate'] = round(
                (task_stats['completed_tasks'] / task_stats['total_created']) * 100, 1
            )
        
        # Notificaciones
        notification_stats = {
            'total_sent': Notification.query.filter(
                Notification.created_at.between(filters['start_date'], filters['end_date'])
            ).count(),
            'read_notifications': Notification.query.filter(
                Notification.created_at.between(filters['start_date'], filters['end_date']),
                Notification.read_at.isnot(None)
            ).count()
        }
        
        # Calcular engagement score
        total_users = User.query.filter(User.is_active == True).count()
        active_users = db.session.query(
            func.count(func.distinct(ActivityLog.user_id))
        ).filter(
            ActivityLog.created_at.between(filters['start_date'], filters['end_date'])
        ).scalar()
        
        engagement_score = round((active_users / total_users * 100), 1) if total_users > 0 else 0
        
        return {
            'engagement_analytics': {
                'engagement_score': engagement_score,
                'active_user_rate': f"{engagement_score}%",
                'documents': {
                    'uploads': document_stats['total_uploads'],
                    'downloads': document_stats['total_downloads'],
                    'avg_downloads_per_doc': round(
                        document_stats['total_downloads'] / document_stats['total_uploads']
                        if document_stats['total_uploads'] > 0 else 0, 1
                    ),
                    'most_downloaded': [
                        {
                            'id': doc.id,
                            'title': doc.title,
                            'downloads': doc.download_count,
                            'type': doc.document_type.value
                        }
                        for doc in document_stats['most_downloaded']
                    ]
                },
                'meetings': {
                    'total_scheduled': meeting_stats['total_scheduled'],
                    'completed': meeting_stats['completed_meetings'],
                    'completion_rate': round(
                        (meeting_stats['completed_meetings'] / meeting_stats['total_scheduled'] * 100)
                        if meeting_stats['total_scheduled'] > 0 else 0, 1
                    ),
                    'avg_duration_minutes': round(meeting_stats['avg_duration'], 1)
                },
                'tasks': task_stats,
                'notifications': {
                    'total_sent': notification_stats['total_sent'],
                    'read_notifications': notification_stats['read_notifications'],
                    'read_rate': round(
                        (notification_stats['read_notifications'] / notification_stats['total_sent'] * 100)
                        if notification_stats['total_sent'] > 0 else 0, 1
                    )
                }
            },
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error en analytics de engagement: {str(e)}")
        raise

@analytics_bp.route('/reports/generate', methods=['POST'])
@jwt_required()
@require_permission('admin')
@rate_limit(5, per=60)  # 5 reports per minute
@api_response
def generate_report():
    """Genera reportes personalizados."""
    try:
        current_user = get_current_user()
        
        schema = ReportSchema()
        data = schema.load(request.get_json() or {})
        
        analytics_service = AnalyticsService()
        
        # Generar reporte según tipo
        if data['report_type'] == 'users':
            report_data = analytics_service.generate_user_report(
                start_date=data['start_date'],
                end_date=data['end_date'],
                filters=data.get('filters', {}),
                format=data['format']
            )
        elif data['report_type'] == 'projects':
            report_data = analytics_service.generate_project_report(
                start_date=data['start_date'],
                end_date=data['end_date'],
                filters=data.get('filters', {}),
                format=data['format']
            )
        elif data['report_type'] == 'financial':
            report_data = analytics_service.generate_financial_report(
                start_date=data['start_date'],
                end_date=data['end_date'],
                filters=data.get('filters', {}),
                format=data['format']
            )
        else:
            raise ValidationException(f"Tipo de reporte no soportado: {data['report_type']}")
        
        # Enviar por email si se especifica
        if data.get('email_recipients'):
            analytics_service.email_report(
                report_data=report_data,
                recipients=data['email_recipients'],
                report_type=data['report_type']
            )
        
        return {
            'message': 'Reporte generado exitosamente',
            'report': report_data,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Datos inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error generando reporte: {str(e)}")
        raise

@analytics_bp.route('/export/<export_type>', methods=['GET'])
@jwt_required()
@rate_limit(10, per=60)
@api_response
def export_data(export_type: str):
    """Exporta datos en diferentes formatos."""
    try:
        current_user = get_current_user()
        
        if not check_analytics_permission(current_user, 'advanced'):
            raise AuthorizationException("Sin permisos para exportar datos")
        
        allowed_exports = ['users', 'projects', 'mentorships', 'activities']
        if export_type not in allowed_exports:
            raise ValidationException(f"Tipo de exportación no válido: {export_type}")
        
        schema = AnalyticsFilterSchema()
        filters = schema.load(request.args)
        
        analytics_service = AnalyticsService()
        
        if export_type == 'users':
            export_data = analytics_service.export_user_data(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            )
        elif export_type == 'projects':
            export_data = analytics_service.export_project_data(
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                user=current_user
            )
        # ... otros tipos de exportación
        
        return {
            'export_data': export_data,
            'export_type': export_type,
            'filters_applied': filters,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error exportando datos: {str(e)}")
        raise

# Manejo de errores
@analytics_bp.errorhandler(ValidationException)
def handle_validation_error(e):
    return jsonify({'error': str(e), 'type': 'validation_error'}), 400

@analytics_bp.errorhandler(AuthorizationException)
def handle_authorization_error(e):
    return jsonify({'error': str(e), 'type': 'authorization_error'}), 403