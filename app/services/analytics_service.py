"""
Analytics Service - Ecosistema de Emprendimiento
Servicio completo de analytics, métricas y business intelligence

Author: Senior Developer
Version: 1.0.0
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import hashlib

from flask import current_app
from sqlalchemy import and_, or_, desc, asc, func, text, distinct
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from redis import Redis

from app.extensions import db, cache, redis_client
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ExternalServiceError
)
from app.core.constants import (
    USER_ROLES,
    PROJECT_STATUS,
    NOTIFICATION_TYPES,
    MENTORSHIP_STATUS
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.project import Project
from app.models.mentorship import Mentorship
from app.models.meeting import Meeting
from app.models.organization import Organization
from app.models.program import Program
from app.models.task import Task
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.analytics import (
    AnalyticsEvent, 
    UserSession, 
    MetricSnapshot,
    CohortAnalysis,
    FunnelStep,
    ABTestResult
)
from app.services.base import BaseService
from app.utils.decorators import log_activity, cache_result
from app.utils.date_utils import (
    get_date_range, 
    calculate_business_days,
    get_week_start,
    get_month_start,
    get_quarter_start
)
from app.utils.formatters import format_currency, format_percentage
from app.utils.crypto_utils import generate_hash


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Tipos de métricas"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"
    PERCENTAGE = "percentage"


class TimeGranularity(Enum):
    """Granularidad temporal"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class EventCategory(Enum):
    """Categorías de eventos"""
    USER_ENGAGEMENT = "user_engagement"
    PROJECT_LIFECYCLE = "project_lifecycle"
    MENTORSHIP_ACTIVITY = "mentorship_activity"
    SYSTEM_PERFORMANCE = "system_performance"
    BUSINESS_METRIC = "business_metric"
    USER_BEHAVIOR = "user_behavior"
    CONVERSION = "conversion"
    RETENTION = "retention"


@dataclass
class AnalyticsEvent:
    """Evento de analytics"""
    event_type: str
    user_id: Optional[int]
    session_id: Optional[str]
    properties: Dict[str, Any]
    timestamp: datetime
    category: str = EventCategory.USER_ENGAGEMENT.value
    value: Optional[float] = None
    revenue: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MetricResult:
    """Resultado de métrica"""
    name: str
    value: Union[int, float, Decimal]
    type: str
    timestamp: datetime
    labels: Optional[Dict[str, str]] = None
    trend: Optional[float] = None
    previous_value: Optional[Union[int, float, Decimal]] = None


@dataclass
class DashboardWidget:
    """Widget de dashboard"""
    id: str
    title: str
    type: str  # chart, kpi, table, etc.
    data: Any
    config: Dict[str, Any]
    refresh_interval: int = 300  # 5 minutos


@dataclass
class CohortData:
    """Datos de análisis de cohorte"""
    cohort_period: str
    cohort_size: int
    retention_rates: List[float]
    revenue_per_cohort: List[Decimal]
    periods: List[str]


@dataclass
class FunnelData:
    """Datos de embudo de conversión"""
    step_name: str
    users_entered: int
    users_completed: int
    conversion_rate: float
    drop_off_rate: float
    avg_time_to_complete: timedelta


class AnalyticsService(BaseService):
    """
    Servicio completo de analytics y business intelligence
    
    Funcionalidades:
    - Tracking de eventos en tiempo real
    - KPIs del ecosistema de emprendimiento
    - Análisis de cohortes y retención
    - Embudos de conversión
    - Segmentación avanzada de usuarios
    - Dashboards dinámicos
    - Reportes automatizados
    - Forecasting y predicciones
    - A/B Testing analytics
    - Performance monitoring
    """
    
    def __init__(self):
        super().__init__()
        self.redis = redis_client
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._initialize_event_processors()
    
    def _initialize_event_processors(self):
        """Inicializar procesadores de eventos"""
        self.event_processors = {
            'user_registration': self._process_user_registration,
            'project_created': self._process_project_created,
            'mentorship_started': self._process_mentorship_started,
            'meeting_completed': self._process_meeting_completed,
            'task_completed': self._process_task_completed,
            'login': self._process_login,
            'page_view': self._process_page_view,
            'feature_used': self._process_feature_usage
        }
    
    @log_activity("analytics_event_tracked")
    def track_event(
        self,
        event_type: str,
        properties: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        category: str = EventCategory.USER_ENGAGEMENT.value,
        value: Optional[float] = None,
        revenue: Optional[Decimal] = None
    ) -> bool:
        """
        Trackear evento de analytics
        
        Args:
            event_type: Tipo de evento
            properties: Propiedades del evento
            user_id: ID del usuario (opcional)
            session_id: ID de sesión (opcional)
            category: Categoría del evento
            value: Valor numérico del evento
            revenue: Ingresos asociados al evento
            
        Returns:
            bool: True si se trackeó correctamente
        """
        try:
            # Crear evento
            event = AnalyticsEvent(
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                properties=properties,
                timestamp=datetime.utcnow(),
                category=category,
                value=value,
                revenue=revenue,
                metadata=self._extract_metadata(properties)
            )
            
            # Procesar en tiempo real
            self._process_event_realtime(event)
            
            # Encolar para procesamiento asíncrono
            self._queue_event_for_processing(event)
            
            # Almacenar en base de datos
            self._store_event(event)
            
            logger.debug(f"Evento trackeado: {event_type} para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error trackeando evento {event_type}: {str(e)}")
            return False
    
    def get_ecosystem_kpis(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[int] = None
    ) -> Dict[str, MetricResult]:
        """
        Obtener KPIs principales del ecosistema
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            organization_id: Filtrar por organización específica
            
        Returns:
            Dict[str, MetricResult]: KPIs calculados
        """
        try:
            kpis = {}
            
            # KPI 1: Total de emprendedores activos
            kpis['active_entrepreneurs'] = self._calculate_active_entrepreneurs(
                start_date, end_date, organization_id
            )
            
            # KPI 2: Proyectos en progreso
            kpis['projects_in_progress'] = self._calculate_projects_in_progress(
                start_date, end_date, organization_id
            )
            
            # KPI 3: Tasa de éxito de proyectos
            kpis['project_success_rate'] = self._calculate_project_success_rate(
                start_date, end_date, organization_id
            )
            
            # KPI 4: Horas de mentoría completadas
            kpis['mentorship_hours'] = self._calculate_mentorship_hours(
                start_date, end_date, organization_id
            )
            
            # KPI 5: Satisfacción promedio
            kpis['avg_satisfaction'] = self._calculate_avg_satisfaction(
                start_date, end_date, organization_id
            )
            
            # KPI 6: Tiempo promedio de finalización de proyectos
            kpis['avg_project_duration'] = self._calculate_avg_project_duration(
                start_date, end_date, organization_id
            )
            
            # KPI 7: Retención de usuarios
            kpis['user_retention'] = self._calculate_user_retention(
                start_date, end_date, organization_id
            )
            
            # KPI 8: Engagement score
            kpis['engagement_score'] = self._calculate_engagement_score(
                start_date, end_date, organization_id
            )
            
            # KPI 9: Crecimiento de usuarios
            kpis['user_growth'] = self._calculate_user_growth(
                start_date, end_date, organization_id
            )
            
            # KPI 10: ROI del ecosistema
            kpis['ecosystem_roi'] = self._calculate_ecosystem_roi(
                start_date, end_date, organization_id
            )
            
            return kpis
            
        except Exception as e:
            logger.error(f"Error calculando KPIs: {str(e)}")
            raise BusinessLogicError(f"Error calculando KPIs: {str(e)}")
    
    @cache_result(timeout=600)  # Cache por 10 minutos
    def get_user_analytics(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Obtener analytics específicos de un usuario
        
        Args:
            user_id: ID del usuario
            days: Número de días a analizar
            
        Returns:
            Dict[str, Any]: Analytics del usuario
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            user = User.query.get(user_id)
            if not user:
                raise NotFoundError(f"Usuario {user_id} no encontrado")
            
            analytics = {
                'user_info': {
                    'id': user.id,
                    'name': user.full_name,
                    'role': user.role,
                    'joined_date': user.created_at,
                    'last_login': user.last_login_at
                },
                'activity_summary': self._get_user_activity_summary(
                    user_id, start_date, end_date
                ),
                'engagement_metrics': self._get_user_engagement_metrics(
                    user_id, start_date, end_date
                ),
                'progress_tracking': self._get_user_progress_tracking(
                    user_id, start_date, end_date
                ),
                'performance_score': self._calculate_user_performance_score(
                    user_id, start_date, end_date
                )
            }
            
            # Analytics específicos por rol
            if user.role == USER_ROLES.ENTREPRENEUR:
                analytics['entrepreneur_metrics'] = self._get_entrepreneur_metrics(
                    user_id, start_date, end_date
                )
            elif user.role == USER_ROLES.ALLY:
                analytics['ally_metrics'] = self._get_ally_metrics(
                    user_id, start_date, end_date
                )
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error obteniendo analytics de usuario {user_id}: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo analytics de usuario: {str(e)}")
    
    def get_cohort_analysis(
        self,
        cohort_type: str = 'monthly',
        metric: str = 'retention',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[CohortData]:
        """
        Realizar análisis de cohortes
        
        Args:
            cohort_type: Tipo de cohorte (daily, weekly, monthly)
            metric: Métrica a analizar (retention, revenue, activity)
            start_date: Fecha de inicio
            end_date: Fecha de fin
            
        Returns:
            List[CohortData]: Datos de análisis de cohortes
        """
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=365)
            if not end_date:
                end_date = datetime.utcnow()
            
            # Obtener usuarios agrupados por cohorte
            cohorts = self._get_user_cohorts(cohort_type, start_date, end_date)
            
            cohort_data = []
            
            for cohort_period, users in cohorts.items():
                if metric == 'retention':
                    retention_data = self._calculate_cohort_retention(
                        users, cohort_period, cohort_type
                    )
                elif metric == 'revenue':
                    retention_data = self._calculate_cohort_revenue(
                        users, cohort_period, cohort_type
                    )
                else:
                    retention_data = self._calculate_cohort_activity(
                        users, cohort_period, cohort_type
                    )
                
                cohort_data.append(retention_data)
            
            return sorted(cohort_data, key=lambda x: x.cohort_period)
            
        except Exception as e:
            logger.error(f"Error en análisis de cohortes: {str(e)}")
            raise BusinessLogicError(f"Error en análisis de cohortes: {str(e)}")
    
    def get_conversion_funnel(
        self,
        funnel_name: str,
        start_date: datetime,
        end_date: datetime,
        segment: Optional[Dict[str, Any]] = None
    ) -> List[FunnelData]:
        """
        Analizar embudo de conversión
        
        Args:
            funnel_name: Nombre del embudo (registration, project_creation, etc.)
            start_date: Fecha de inicio
            end_date: Fecha de fin
            segment: Segmento específico a analizar
            
        Returns:
            List[FunnelData]: Datos del embudo de conversión
        """
        try:
            funnel_steps = self._get_funnel_definition(funnel_name)
            funnel_data = []
            
            previous_users = None
            
            for step in funnel_steps:
                step_users = self._get_users_in_funnel_step(
                    step, start_date, end_date, segment
                )
                
                if previous_users is None:
                    # Primer paso
                    users_entered = len(step_users)
                    users_completed = len(step_users)
                    conversion_rate = 100.0
                    drop_off_rate = 0.0
                else:
                    # Pasos subsecuentes
                    users_entered = len(previous_users)
                    completed_users = step_users.intersection(previous_users)
                    users_completed = len(completed_users)
                    
                    conversion_rate = (users_completed / users_entered * 100) if users_entered > 0 else 0
                    drop_off_rate = 100 - conversion_rate
                
                avg_time = self._calculate_avg_time_in_step(
                    step, step_users, start_date, end_date
                )
                
                funnel_data.append(FunnelData(
                    step_name=step['name'],
                    users_entered=users_entered,
                    users_completed=users_completed,
                    conversion_rate=conversion_rate,
                    drop_off_rate=drop_off_rate,
                    avg_time_to_complete=avg_time
                ))
                
                previous_users = step_users
            
            return funnel_data
            
        except Exception as e:
            logger.error(f"Error analizando embudo {funnel_name}: {str(e)}")
            raise BusinessLogicError(f"Error analizando embudo: {str(e)}")
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Obtener métricas en tiempo real
        
        Returns:
            Dict[str, Any]: Métricas en tiempo real
        """
        try:
            current_time = datetime.utcnow()
            
            # Métricas de los últimos 5 minutos
            last_5_min = current_time - timedelta(minutes=5)
            
            # Métricas en tiempo real desde Redis
            real_time_data = {
                'active_users_now': self._get_active_users_count(),
                'events_last_5min': self._get_events_count(last_5_min, current_time),
                'avg_response_time': self._get_avg_response_time(),
                'error_rate': self._get_error_rate(),
                'new_registrations_today': self._get_new_registrations_today(),
                'projects_created_today': self._get_projects_created_today(),
                'meetings_in_progress': self._get_meetings_in_progress(),
                'system_health': self._get_system_health_metrics(),
                'top_events': self._get_top_events_last_hour(),
                'geographic_distribution': self._get_geographic_distribution()
            }
            
            return real_time_data
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas en tiempo real: {str(e)}")
            return {}
    
    def generate_dashboard(
        self,
        dashboard_type: str,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[DashboardWidget]:
        """
        Generar dashboard dinámico
        
        Args:
            dashboard_type: Tipo de dashboard (executive, entrepreneur, ally, admin)
            user_id: ID del usuario que solicita
            filters: Filtros aplicados
            
        Returns:
            List[DashboardWidget]: Widgets del dashboard
        """
        try:
            widgets = []
            
            if dashboard_type == 'executive':
                widgets = self._generate_executive_dashboard(user_id, filters)
            elif dashboard_type == 'entrepreneur':
                widgets = self._generate_entrepreneur_dashboard(user_id, filters)
            elif dashboard_type == 'ally':
                widgets = self._generate_ally_dashboard(user_id, filters)
            elif dashboard_type == 'admin':
                widgets = self._generate_admin_dashboard(user_id, filters)
            else:
                widgets = self._generate_default_dashboard(user_id, filters)
            
            return widgets
            
        except Exception as e:
            logger.error(f"Error generando dashboard {dashboard_type}: {str(e)}")
            raise BusinessLogicError(f"Error generando dashboard: {str(e)}")
    
    def create_custom_report(
        self,
        report_config: Dict[str, Any],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Crear reporte personalizado
        
        Args:
            report_config: Configuración del reporte
            user_id: ID del usuario que solicita
            
        Returns:
            Dict[str, Any]: Datos del reporte
        """
        try:
            report_data = {
                'metadata': {
                    'title': report_config.get('title', 'Reporte Personalizado'),
                    'description': report_config.get('description', ''),
                    'created_by': user_id,
                    'created_at': datetime.utcnow(),
                    'filters': report_config.get('filters', {}),
                    'date_range': report_config.get('date_range', {})
                },
                'sections': []
            }
            
            # Procesar cada sección del reporte
            for section_config in report_config.get('sections', []):
                section_data = self._generate_report_section(section_config)
                report_data['sections'].append(section_data)
            
            # Generar resumen ejecutivo si se solicita
            if report_config.get('include_summary', True):
                report_data['executive_summary'] = self._generate_executive_summary(
                    report_data['sections']
                )
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error creando reporte personalizado: {str(e)}")
            raise BusinessLogicError(f"Error creando reporte: {str(e)}")
    
    def get_predictive_analytics(
        self,
        metric: str,
        periods_ahead: int = 12,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Obtener analytics predictivos
        
        Args:
            metric: Métrica a predecir
            periods_ahead: Períodos futuros a predecir
            confidence_level: Nivel de confianza
            
        Returns:
            Dict[str, Any]: Predicciones y métricas
        """
        try:
            # Obtener datos históricos
            historical_data = self._get_historical_metric_data(metric)
            
            if len(historical_data) < 12:  # Mínimo 12 puntos de datos
                raise ValidationError("Datos insuficientes para predicción")
            
            # Preparar datos para el modelo
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            # Aplicar modelo de predicción (ejemplo con tendencia linear)
            predictions = self._generate_predictions(
                df, metric, periods_ahead, confidence_level
            )
            
            # Calcular métricas de confianza
            accuracy_metrics = self._calculate_prediction_accuracy(
                historical_data[-6:], metric
            )
            
            return {
                'metric': metric,
                'historical_data': historical_data,
                'predictions': predictions,
                'accuracy_metrics': accuracy_metrics,
                'confidence_level': confidence_level,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error en analytics predictivos para {metric}: {str(e)}")
            raise BusinessLogicError(f"Error en analytics predictivos: {str(e)}")
    
    def segment_users(
        self,
        segmentation_criteria: Dict[str, Any]
    ) -> Dict[str, List[int]]:
        """
        Segmentar usuarios basado en criterios específicos
        
        Args:
            segmentation_criteria: Criterios de segmentación
            
        Returns:
            Dict[str, List[int]]: Segmentos con IDs de usuarios
        """
        try:
            segments = {}
            
            # Segmentación por comportamiento
            if 'behavior' in segmentation_criteria:
                behavior_segments = self._segment_by_behavior(
                    segmentation_criteria['behavior']
                )
                segments.update(behavior_segments)
            
            # Segmentación por demografía
            if 'demographics' in segmentation_criteria:
                demo_segments = self._segment_by_demographics(
                    segmentation_criteria['demographics']
                )
                segments.update(demo_segments)
            
            # Segmentación por actividad
            if 'activity' in segmentation_criteria:
                activity_segments = self._segment_by_activity(
                    segmentation_criteria['activity']
                )
                segments.update(activity_segments)
            
            # Segmentación por valor
            if 'value' in segmentation_criteria:
                value_segments = self._segment_by_value(
                    segmentation_criteria['value']
                )
                segments.update(value_segments)
            
            return segments
            
        except Exception as e:
            logger.error(f"Error segmentando usuarios: {str(e)}")
            raise BusinessLogicError(f"Error segmentando usuarios: {str(e)}")
    
    # Métodos privados para KPIs
    def _calculate_active_entrepreneurs(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[int]
    ) -> MetricResult:
        """Calcular emprendedores activos"""
        query = db.session.query(func.count(distinct(Entrepreneur.id))).join(User)
        
        if organization_id:
            query = query.filter(Entrepreneur.organization_id == organization_id)
        
        # Emprendedores con actividad en el período
        query = query.join(ActivityLog).filter(
            and_(
                ActivityLog.created_at.between(start_date, end_date),
                User.is_active == True
            )
        )
        
        current_value = query.scalar() or 0
        
        # Calcular valor anterior para tendencia
        previous_start = start_date - (end_date - start_date)
        previous_query = query.filter(
            ActivityLog.created_at.between(previous_start, start_date)
        )
        previous_value = previous_query.scalar() or 0
        
        trend = ((current_value - previous_value) / previous_value * 100) if previous_value > 0 else 0
        
        return MetricResult(
            name="active_entrepreneurs",
            value=current_value,
            type=MetricType.GAUGE.value,
            timestamp=datetime.utcnow(),
            trend=trend,
            previous_value=previous_value
        )
    
    def _calculate_projects_in_progress(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[int]
    ) -> MetricResult:
        """Calcular proyectos en progreso"""
        query = Project.query.filter(
            Project.status.in_(['in_progress', 'approved']),
            Project.is_deleted == False
        )
        
        if organization_id:
            query = query.filter(Project.organization_id == organization_id)
        
        current_value = query.count()
        
        return MetricResult(
            name="projects_in_progress",
            value=current_value,
            type=MetricType.GAUGE.value,
            timestamp=datetime.utcnow()
        )
    
    def _calculate_project_success_rate(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[int]
    ) -> MetricResult:
        """Calcular tasa de éxito de proyectos"""
        base_query = Project.query.filter(
            Project.created_at.between(start_date, end_date),
            Project.is_deleted == False
        )
        
        if organization_id:
            base_query = base_query.filter(Project.organization_id == organization_id)
        
        total_projects = base_query.count()
        successful_projects = base_query.filter(
            Project.status == 'completed'
        ).count()
        
        success_rate = (successful_projects / total_projects * 100) if total_projects > 0 else 0
        
        return MetricResult(
            name="project_success_rate",
            value=round(success_rate, 2),
            type=MetricType.PERCENTAGE.value,
            timestamp=datetime.utcnow()
        )
    
    def _calculate_mentorship_hours(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[int]
    ) -> MetricResult:
        """Calcular horas de mentoría completadas"""
        query = db.session.query(func.sum(Meeting.duration_minutes)).join(Mentorship)
        
        query = query.filter(
            Meeting.start_time.between(start_date, end_date),
            Meeting.status == 'completed'
        )
        
        if organization_id:
            query = query.join(Project).filter(
                Project.organization_id == organization_id
            )
        
        total_minutes = query.scalar() or 0
        total_hours = total_minutes / 60
        
        return MetricResult(
            name="mentorship_hours",
            value=round(total_hours, 1),
            type=MetricType.GAUGE.value,
            timestamp=datetime.utcnow()
        )
    
    def _calculate_user_retention(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[int]
    ) -> MetricResult:
        """Calcular retención de usuarios"""
        # Usuarios que se registraron al inicio del período
        period_start_users = User.query.filter(
            User.created_at < start_date,
            User.is_active == True
        )
        
        if organization_id:
            period_start_users = period_start_users.join(Entrepreneur).filter(
                Entrepreneur.organization_id == organization_id
            )
        
        start_user_ids = [u.id for u in period_start_users.all()]
        
        if not start_user_ids:
            return MetricResult(
                name="user_retention",
                value=0,
                type=MetricType.PERCENTAGE.value,
                timestamp=datetime.utcnow()
            )
        
        # Usuarios que tuvieron actividad en el período
        active_in_period = ActivityLog.query.filter(
            ActivityLog.user_id.in_(start_user_ids),
            ActivityLog.created_at.between(start_date, end_date)
        ).distinct(ActivityLog.user_id).count()
        
        retention_rate = (active_in_period / len(start_user_ids) * 100)
        
        return MetricResult(
            name="user_retention",
            value=round(retention_rate, 2),
            type=MetricType.PERCENTAGE.value,
            timestamp=datetime.utcnow()
        )
    
    # Métodos de procesamiento de eventos
    def _process_event_realtime(self, event: AnalyticsEvent) -> None:
        """Procesar evento en tiempo real"""
        try:
            # Actualizar contadores en Redis
            self._update_realtime_counters(event)
            
            # Procesar con procesador específico si existe
            if event.event_type in self.event_processors:
                self.event_processors[event.event_type](event)
            
            # Detectar anomalías
            self._detect_anomalies(event)
            
        except Exception as e:
            logger.error(f"Error procesando evento en tiempo real: {str(e)}")
    
    def _update_realtime_counters(self, event: AnalyticsEvent) -> None:
        """Actualizar contadores en tiempo real en Redis"""
        current_hour = datetime.utcnow().strftime('%Y%m%d%H')
        
        # Contadores globales
        self.redis.incr(f"events:{current_hour}")
        self.redis.incr(f"events:{event.event_type}:{current_hour}")
        
        # Contadores por usuario
        if event.user_id:
            self.redis.incr(f"user_events:{event.user_id}:{current_hour}")
            
            # Tracking de usuarios activos
            self.redis.sadd("active_users:current", event.user_id)
            self.redis.expire("active_users:current", 300)  # 5 minutos
        
        # Contadores por categoría
        self.redis.incr(f"category:{event.category}:{current_hour}")
        
        # TTL para limpieza automática
        self.redis.expire(f"events:{current_hour}", 86400 * 7)  # 7 días
    
    def _process_user_registration(self, event: AnalyticsEvent) -> None:
        """Procesar evento de registro de usuario"""
        if event.user_id:
            # Actualizar métricas de adquisición
            self.redis.incr("registrations:today")
            
            # Tracking para análisis de cohorte
            cohort_key = f"cohort:{datetime.utcnow().strftime('%Y%m')}"
            self.redis.sadd(cohort_key, event.user_id)
    
    def _process_project_created(self, event: AnalyticsEvent) -> None:
        """Procesar evento de creación de proyecto"""
        if event.user_id:
            # Actualizar métricas de conversión
            self.redis.incr("projects:created:today")
            
            # Tracking de embudo de conversión
            funnel_key = f"funnel:project_creation:{event.user_id}"
            self.redis.hset(funnel_key, "project_created", datetime.utcnow().timestamp())
    
    # Métodos de análisis de cohortes
    def _get_user_cohorts(
        self, 
        cohort_type: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, List[int]]:
        """Obtener usuarios agrupados por cohorte"""
        cohorts = defaultdict(list)
        
        users = User.query.filter(
            User.created_at.between(start_date, end_date)
        ).all()
        
        for user in users:
            if cohort_type == 'daily':
                cohort_key = user.created_at.strftime('%Y-%m-%d')
            elif cohort_type == 'weekly':
                cohort_key = get_week_start(user.created_at).strftime('%Y-W%U')
            else:  # monthly
                cohort_key = user.created_at.strftime('%Y-%m')
            
            cohorts[cohort_key].append(user.id)
        
        return dict(cohorts)
    
    def _calculate_cohort_retention(
        self, 
        user_ids: List[int], 
        cohort_period: str,
        cohort_type: str
    ) -> CohortData:
        """Calcular retención de cohorte"""
        cohort_size = len(user_ids)
        retention_rates = []
        periods = []
        
        # Determinar períodos a analizar
        if cohort_type == 'monthly':
            periods_to_check = 12
            period_delta = timedelta(days=30)
        else:
            periods_to_check = 8
            period_delta = timedelta(weeks=1)
        
        cohort_start = datetime.strptime(cohort_period.split('-')[0] + '-' + cohort_period.split('-')[1], '%Y-%m')
        
        for i in range(periods_to_check):
            period_start = cohort_start + (period_delta * i)
            period_end = period_start + period_delta
            
            # Contar usuarios activos en este período
            active_users = ActivityLog.query.filter(
                ActivityLog.user_id.in_(user_ids),
                ActivityLog.created_at.between(period_start, period_end)
            ).distinct(ActivityLog.user_id).count()
            
            retention_rate = (active_users / cohort_size * 100) if cohort_size > 0 else 0
            retention_rates.append(retention_rate)
            periods.append(f"Período {i + 1}")
        
        return CohortData(
            cohort_period=cohort_period,
            cohort_size=cohort_size,
            retention_rates=retention_rates,
            revenue_per_cohort=[],
            periods=periods
        )
    
    # Métodos de dashboard
    def _generate_executive_dashboard(
        self, 
        user_id: int, 
        filters: Optional[Dict[str, Any]]
    ) -> List[DashboardWidget]:
        """Generar dashboard ejecutivo"""
        widgets = []
        
        # Widget 1: KPIs principales
        kpis = self.get_ecosystem_kpis(
            datetime.utcnow() - timedelta(days=30),
            datetime.utcnow()
        )
        
        widgets.append(DashboardWidget(
            id="executive_kpis",
            title="KPIs Principales",
            type="kpi_grid",
            data=kpis,
            config={"layout": "4x2", "update_interval": 300}
        ))
        
        # Widget 2: Tendencias de crecimiento
        growth_data = self._get_growth_trends()
        widgets.append(DashboardWidget(
            id="growth_trends",
            title="Tendencias de Crecimiento",
            type="line_chart",
            data=growth_data,
            config={"period": "monthly", "show_forecast": True}
        ))
        
        # Widget 3: Estado de proyectos
        project_status_data = self._get_project_status_distribution()
        widgets.append(DashboardWidget(
            id="project_status",
            title="Estado de Proyectos",
            type="donut_chart",
            data=project_status_data,
            config={"show_percentages": True}
        ))
        
        return widgets
    
    def _store_event(self, event: AnalyticsEvent) -> None:
        """Almacenar evento en base de datos"""
        try:
            # Crear registro en la tabla de eventos
            db_event = AnalyticsEvent(
                event_type=event.event_type,
                user_id=event.user_id,
                session_id=event.session_id,
                properties=json.dumps(event.properties),
                timestamp=event.timestamp,
                category=event.category,
                value=event.value,
                revenue=event.revenue,
                metadata=json.dumps(event.metadata) if event.metadata else None
            )
            
            db.session.add(db_event)
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error almacenando evento: {str(e)}")
    
    def _queue_event_for_processing(self, event: AnalyticsEvent) -> None:
        """Encolar evento para procesamiento asíncrono"""
        try:
            from app.tasks.analytics_tasks import process_analytics_event
            
            # Serializar evento para Celery
            event_data = {
                'event_type': event.event_type,
                'user_id': event.user_id,
                'session_id': event.session_id,
                'properties': event.properties,
                'timestamp': event.timestamp.isoformat(),
                'category': event.category,
                'value': event.value,
                'revenue': float(event.revenue) if event.revenue else None,
                'metadata': event.metadata
            }
            
            process_analytics_event.delay(event_data)
            
        except Exception as e:
            logger.error(f"Error encolando evento: {str(e)}")
    
    def _extract_metadata(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Extraer metadata del evento"""
        metadata = {}
        
        # Extraer información de contexto
        if 'user_agent' in properties:
            metadata['user_agent'] = properties['user_agent']
        
        if 'ip_address' in properties:
            metadata['ip_address'] = properties['ip_address']
        
        if 'referrer' in properties:
            metadata['referrer'] = properties['referrer']
        
        # Generar hash del evento para deduplicación
        event_string = json.dumps(properties, sort_keys=True)
        metadata['event_hash'] = generate_hash(event_string)
        
        return metadata
    
    # Métodos auxiliares de métricas en tiempo real
    def _get_active_users_count(self) -> int:
        """Obtener conteo de usuarios activos ahora"""
        return self.redis.scard("active_users:current") or 0
    
    def _get_events_count(self, start_time: datetime, end_time: datetime) -> int:
        """Obtener conteo de eventos en rango de tiempo"""
        count = 0
        current = start_time
        
        while current <= end_time:
            hour_key = current.strftime('%Y%m%d%H')
            count += int(self.redis.get(f"events:{hour_key}") or 0)
            current += timedelta(hours=1)
        
        return count
    
    def _get_new_registrations_today(self) -> int:
        """Obtener nuevos registros de hoy"""
        today = datetime.utcnow().date()
        return User.query.filter(
            func.date(User.created_at) == today
        ).count()


# Instancia del servicio para uso global
analytics_service = AnalyticsService()


# Funciones de conveniencia para tracking rápido
def track_user_action(user_id: int, action: str, properties: Dict[str, Any] = None):
    """Trackear acción de usuario"""
    return analytics_service.track_event(
        event_type=action,
        user_id=user_id,
        properties=properties or {},
        category=EventCategory.USER_BEHAVIOR.value
    )


def track_project_milestone(project_id: int, milestone: str, user_id: int = None):
    """Trackear hito de proyecto"""
    return analytics_service.track_event(
        event_type='project_milestone',
        user_id=user_id,
        properties={'project_id': project_id, 'milestone': milestone},
        category=EventCategory.PROJECT_LIFECYCLE.value
    )


def track_conversion_event(event_type: str, user_id: int, value: float = None, revenue: Decimal = None):
    """Trackear evento de conversión"""
    return analytics_service.track_event(
        event_type=event_type,
        user_id=user_id,
        properties={'conversion': True},
        category=EventCategory.CONVERSION.value,
        value=value,
        revenue=revenue
    )