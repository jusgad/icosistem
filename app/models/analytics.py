"""
Analytics Model - Sistema de métricas y análisis
===============================================

Este módulo define los modelos para recopilar, almacenar y analizar métricas
del ecosistema de emprendimiento, proporcionando insights valiosos para
la toma de decisiones.

Funcionalidades:
- Métricas de usuarios y engagement
- KPIs de emprendimiento y mentoría
- Análisis de rendimiento de programas
- Métricas financieras y de crecimiento
- Analytics en tiempo real y históricos
- Dashboards personalizables
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union
from decimal import Decimal
import json

from sqlalchemy import Index, func, case, and_, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin


class MetricType(Enum):
    """Tipos de métricas del sistema"""
    
    # Métricas de usuarios
    USER_REGISTRATION = "user_registration"
    USER_ACTIVATION = "user_activation"
    USER_RETENTION = "user_retention"
    USER_ENGAGEMENT = "user_engagement"
    USER_SESSION_DURATION = "user_session_duration"
    
    # Métricas de emprendedores
    ENTREPRENEUR_ONBOARDING = "entrepreneur_onboarding"
    ENTREPRENEUR_PROJECT_CREATION = "entrepreneur_project_creation"
    ENTREPRENEUR_MILESTONE_COMPLETION = "entrepreneur_milestone_completion"
    ENTREPRENEUR_REVENUE_GROWTH = "entrepreneur_revenue_growth"
    ENTREPRENEUR_FUNDING_RAISED = "entrepreneur_funding_raised"
    
    # Métricas de mentoría
    MENTORSHIP_REQUESTS = "mentorship_requests"
    MENTORSHIP_MATCHES = "mentorship_matches"
    MENTORSHIP_SESSION_COMPLETION = "mentorship_session_completion"
    MENTORSHIP_SATISFACTION = "mentorship_satisfaction"
    MENTOR_UTILIZATION = "mentor_utilization"
    
    # Métricas de programas
    PROGRAM_ENROLLMENT = "program_enrollment"
    PROGRAM_COMPLETION = "program_completion"
    PROGRAM_SATISFACTION = "program_satisfaction"
    PROGRAM_SUCCESS_RATE = "program_success_rate"
    
    # Métricas de colaboración
    MEETING_FREQUENCY = "meeting_frequency"
    DOCUMENT_SHARING = "document_sharing"
    MESSAGE_VOLUME = "message_volume"
    TASK_COMPLETION_RATE = "task_completion_rate"
    
    # Métricas de negocio
    CONVERSION_RATE = "conversion_rate"
    CUSTOMER_ACQUISITION_COST = "customer_acquisition_cost"
    LIFETIME_VALUE = "lifetime_value"
    CHURN_RATE = "churn_rate"
    
    # Métricas de sistema
    API_USAGE = "api_usage"
    SYSTEM_PERFORMANCE = "system_performance"
    ERROR_RATE = "error_rate"
    UPTIME = "uptime"


class MetricFrequency(Enum):
    """Frecuencia de recolección de métricas"""
    REAL_TIME = "real_time"    # Tiempo real
    HOURLY = "hourly"          # Por hora
    DAILY = "daily"            # Diario
    WEEKLY = "weekly"          # Semanal
    MONTHLY = "monthly"        # Mensual
    QUARTERLY = "quarterly"    # Trimestral
    YEARLY = "yearly"          # Anual


class MetricCategory(Enum):
    """Categorías de métricas"""
    USER_BEHAVIOR = "user_behavior"
    BUSINESS_GROWTH = "business_growth"
    PROGRAM_SUCCESS = "program_success"
    SYSTEM_HEALTH = "system_health"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"


class AnalyticsMetric(BaseModel, TimestampMixin):
    """
    Modelo para almacenar métricas individuales
    
    Attributes:
        id: ID único de la métrica
        metric_type: Tipo de métrica
        category: Categoría de la métrica
        frequency: Frecuencia de recolección
        name: Nombre descriptivo de la métrica
        description: Descripción detallada
        value: Valor numérico de la métrica
        unit: Unidad de medida
        dimensions: Dimensiones adicionales (JSON)
        timestamp: Momento de la medición
        organization_id: ID de la organización
        program_id: ID del programa (opcional)
        user_id: ID del usuario relacionado (opcional)
        metadata: Metadatos adicionales
    """
    
    __tablename__ = 'analytics_metrics'
    
    # Campos principales
    metric_type = db.Column(
        db.Enum(MetricType),
        nullable=False,
        index=True
    )
    
    category = db.Column(
        db.Enum(MetricCategory),
        nullable=False,
        index=True
    )
    
    frequency = db.Column(
        db.Enum(MetricFrequency),
        nullable=False,
        default=MetricFrequency.DAILY
    )
    
    name = db.Column(
        db.String(200),
        nullable=False
    )
    
    description = db.Column(
        db.Text,
        nullable=True
    )
    
    # Valor y dimensiones
    value = db.Column(
        db.Numeric(15, 4),  # Precisión para valores financieros
        nullable=False
    )
    
    unit = db.Column(
        db.String(50),
        nullable=True
    )
    
    dimensions = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Timestamp específico para la métrica
    timestamp = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    # Referencias
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    program_id = db.Column(
        db.Integer,
        db.ForeignKey('programs.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # Metadatos flexibles
    analytics_metadata = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Relaciones
    organization = db.relationship('Organization', backref='metrics')
    program = db.relationship('Program', backref='metrics')
    user = db.relationship('User', backref='metrics')
    
    # Índices compuestos
    __table_args__ = (
        Index('ix_metric_type_timestamp', 'metric_type', 'timestamp'),
        Index('ix_metric_org_timestamp', 'organization_id', 'timestamp'),
        Index('ix_metric_category_timestamp', 'category', 'timestamp'),
        Index('ix_metric_freq_timestamp', 'frequency', 'timestamp'),
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<AnalyticsMetric {self.name}: {self.value} {self.unit or ''}>"
    
    @validates('value')
    def validate_value(self, key, value):
        """Valida que el valor sea numérico válido"""
        if value is None:
            raise ValueError("El valor de la métrica no puede ser nulo")
        return value
    
    def to_dict(self):
        """Convierte la métrica a diccionario"""
        return {
            'id': self.id,
            'metric_type': self.metric_type.value,
            'category': self.category.value,
            'frequency': self.frequency.value,
            'name': self.name,
            'description': self.description,
            'value': float(self.value),
            'unit': self.unit,
            'dimensions': self.dimensions,
            'timestamp': self.timestamp.isoformat(),
            'organization_id': self.organization_id,
            'program_id': self.program_id,
            'user_id': self.user_id,
            'metadata': self.analytics_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AnalyticsDashboard(BaseModel, TimestampMixin):
    """
    Modelo para dashboards personalizados de analytics
    
    Attributes:
        id: ID único del dashboard
        name: Nombre del dashboard
        description: Descripción del dashboard
        config: Configuración del dashboard (JSON)
        owner_id: ID del propietario
        organization_id: ID de la organización
        is_public: Si es público o privado
        is_default: Si es dashboard por defecto
        layout: Layout del dashboard
        filters: Filtros predeterminados
    """
    
    __tablename__ = 'analytics_dashboards'
    
    name = db.Column(
        db.String(200),
        nullable=False
    )
    
    description = db.Column(
        db.Text,
        nullable=True
    )
    
    config = db.Column(
        JSONB,
        nullable=False,
        default=dict
    )
    
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    is_public = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    
    is_default = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    
    layout = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    filters = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Relaciones
    owner = db.relationship('User', backref='owned_dashboards')
    organization = db.relationship('Organization', backref='dashboards')
    
    def __repr__(self):
        return f"<AnalyticsDashboard {self.name}>"


class AnalyticsReport(BaseModel, TimestampMixin):
    """
    Modelo para reportes generados de analytics
    
    Attributes:
        id: ID único del reporte
        title: Título del reporte
        report_type: Tipo de reporte
        content: Contenido del reporte (JSON)
        parameters: Parámetros usados para generar el reporte
        generated_by: Usuario que generó el reporte
        organization_id: ID de la organización
        status: Estado del reporte
        file_path: Ruta del archivo generado (opcional)
        expires_at: Fecha de expiración
    """
    
    __tablename__ = 'analytics_reports'
    
    title = db.Column(
        db.String(300),
        nullable=False
    )
    
    report_type = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )
    
    content = db.Column(
        JSONB,
        nullable=True
    )
    
    parameters = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    generated_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    status = db.Column(
        db.String(50),
        nullable=False,
        default='pending'
    )
    
    file_path = db.Column(
        db.String(500),
        nullable=True
    )
    
    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )
    
    # Relaciones
    generator = db.relationship('User', backref='generated_reports')
    organization = db.relationship('Organization', backref='reports')


class AnalyticsService:
    """Servicio para operaciones de analytics"""
    
    @staticmethod
    def record_metric(
        metric_type: MetricType,
        value: Union[int, float, Decimal],
        category: MetricCategory,
        name: str,
        frequency: MetricFrequency = MetricFrequency.DAILY,
        unit: Optional[str] = None,
        dimensions: Optional[dict[str, Any]] = None,
        organization_id: Optional[int] = None,
        program_id: Optional[int] = None,
        user_id: Optional[int] = None,
        analytics_metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> AnalyticsMetric:
        """
        Registra una nueva métrica
        
        Args:
            metric_type: Tipo de métrica
            value: Valor de la métrica
            category: Categoría de la métrica
            name: Nombre descriptivo
            frequency: Frecuencia de recolección
            unit: Unidad de medida
            dimensions: Dimensiones adicionales
            organization_id: ID de organización
            program_id: ID de programa
            user_id: ID de usuario
            metadata: Metadatos adicionales
            timestamp: Momento específico de la medición
            
        Returns:
            Nueva instancia de AnalyticsMetric
        """
        metric = AnalyticsMetric(
            metric_type=metric_type,
            category=category,
            frequency=frequency,
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions or {},
            timestamp=timestamp or datetime.now(timezone.utc),
            organization_id=organization_id,
            program_id=program_id,
            user_id=user_id,
            analytics_metadata=analytics_metadata or {}
        )
        
        db.session.add(metric)
        db.session.commit()
        
        return metric
    
    @staticmethod
    def get_metrics_summary(
        metric_types: Optional[list[MetricType]] = None,
        category: Optional[MetricCategory] = None,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = 'day'
    ) -> dict[str, Any]:
        """
        Obtiene resumen de métricas agrupadas
        
        Args:
            metric_types: Tipos específicos de métricas
            category: Categoría de métricas
            organization_id: ID de organización
            start_date: Fecha de inicio
            end_date: Fecha de fin
            group_by: Agrupación temporal ('hour', 'day', 'week', 'month')
            
        Returns:
            Diccionario con datos agrupados
        """
        query = db.session.query(AnalyticsMetric)
        
        # Aplicar filtros
        if metric_types:
            query = query.filter(AnalyticsMetric.metric_type.in_(metric_types))
        
        if category:
            query = query.filter(AnalyticsMetric.category == category)
            
        if organization_id:
            query = query.filter(AnalyticsMetric.organization_id == organization_id)
            
        if start_date:
            query = query.filter(AnalyticsMetric.timestamp >= start_date)
            
        if end_date:
            query = query.filter(AnalyticsMetric.timestamp <= end_date)
        
        # Configurar agrupación temporal
        date_trunc_format = {
            'hour': 'hour',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }.get(group_by, 'day')
        
        # Ejecutar consulta agrupada
        results = query.with_entities(
            func.date_trunc(date_trunc_format, AnalyticsMetric.timestamp).label('period'),
            AnalyticsMetric.metric_type,
            func.sum(AnalyticsMetric.value).label('total_value'),
            func.avg(AnalyticsMetric.value).label('avg_value'),
            func.count().label('count')
        ).group_by(
            func.date_trunc(date_trunc_format, AnalyticsMetric.timestamp),
            AnalyticsMetric.metric_type
        ).order_by('period').all()
        
        # Procesar resultados
        summary = {}
        for result in results:
            period_key = result.period.strftime('%Y-%m-%d %H:%M:%S')
            metric_key = result.metric_type.value
            
            if period_key not in summary:
                summary[period_key] = {}
                
            summary[period_key][metric_key] = {
                'total': float(result.total_value),
                'average': float(result.avg_value),
                'count': result.count
            }
        
        return summary
    
    @staticmethod
    def calculate_kpis(
        organization_id: Optional[int] = None,
        period_days: int = 30
    ) -> dict[str, Any]:
        """
        Calcula KPIs principales del ecosistema
        
        Args:
            organization_id: ID de organización
            period_days: Período en días para el cálculo
            
        Returns:
            Diccionario con KPIs calculados
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        query_filter = and_(
            AnalyticsMetric.timestamp >= start_date,
            AnalyticsMetric.timestamp <= end_date
        )
        
        if organization_id:
            query_filter = and_(
                query_filter,
                AnalyticsMetric.organization_id == organization_id
            )
        
        # Usuarios activos
        active_users = db.session.query(func.count(func.distinct(AnalyticsMetric.user_id))).filter(
            query_filter,
            AnalyticsMetric.metric_type == MetricType.USER_ENGAGEMENT
        ).scalar() or 0
        
        # Proyectos creados
        projects_created = db.session.query(func.sum(AnalyticsMetric.value)).filter(
            query_filter,
            AnalyticsMetric.metric_type == MetricType.ENTREPRENEUR_PROJECT_CREATION
        ).scalar() or 0
        
        # Sesiones de mentoría completadas
        mentorship_sessions = db.session.query(func.sum(AnalyticsMetric.value)).filter(
            query_filter,
            AnalyticsMetric.metric_type == MetricType.MENTORSHIP_SESSION_COMPLETION
        ).scalar() or 0
        
        # Tasa de conversión promedio
        conversion_rate = db.session.query(func.avg(AnalyticsMetric.value)).filter(
            query_filter,
            AnalyticsMetric.metric_type == MetricType.CONVERSION_RATE
        ).scalar() or 0
        
        # Retención de usuarios
        retention_rate = db.session.query(func.avg(AnalyticsMetric.value)).filter(
            query_filter,
            AnalyticsMetric.metric_type == MetricType.USER_RETENTION
        ).scalar() or 0
        
        return {
            'active_users': int(active_users),
            'projects_created': int(projects_created),
            'mentorship_sessions': int(mentorship_sessions),
            'conversion_rate': float(conversion_rate),
            'retention_rate': float(retention_rate),
            'period_days': period_days,
            'calculated_at': datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def get_trend_analysis(
        metric_type: MetricType,
        organization_id: Optional[int] = None,
        days: int = 90
    ) -> dict[str, Any]:
        """
        Analiza tendencias de una métrica específica
        
        Args:
            metric_type: Tipo de métrica a analizar
            organization_id: ID de organización
            days: Días de historial a analizar
            
        Returns:
            Análisis de tendencia con predicciones básicas
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = db.session.query(
            func.date_trunc('day', AnalyticsMetric.timestamp).label('date'),
            func.sum(AnalyticsMetric.value).label('value')
        ).filter(
            AnalyticsMetric.metric_type == metric_type,
            AnalyticsMetric.timestamp >= start_date,
            AnalyticsMetric.timestamp <= end_date
        )
        
        if organization_id:
            query = query.filter(AnalyticsMetric.organization_id == organization_id)
        
        results = query.group_by(
            func.date_trunc('day', AnalyticsMetric.timestamp)
        ).order_by('date').all()
        
        if not results:
            return {'trend': 'no_data', 'values': [], 'prediction': None}
        
        values = [float(r.value) for r in results]
        dates = [r.date.strftime('%Y-%m-%d') for r in results]
        
        # Análisis básico de tendencia
        if len(values) < 2:
            trend = 'insufficient_data'
        else:
            # Calcular pendiente promedio
            total_change = values[-1] - values[0]
            trend = 'growing' if total_change > 0 else 'declining' if total_change < 0 else 'stable'
        
        # Predicción simple (promedio móvil)
        prediction = None
        if len(values) >= 7:
            recent_avg = sum(values[-7:]) / 7
            prediction = recent_avg
        
        return {
            'trend': trend,
            'values': values,
            'dates': dates,
            'prediction': prediction,
            'total_change': values[-1] - values[0] if len(values) > 1 else 0,
            'percent_change': ((values[-1] - values[0]) / values[0] * 100) if len(values) > 1 and values[0] != 0 else 0
        }


# Funciones auxiliares para métricas comunes
def track_user_activity(user_id: int, activity_type: str, organization_id: Optional[int] = None):
    """Registra actividad de usuario"""
    AnalyticsService.record_metric(
        metric_type=MetricType.USER_ENGAGEMENT,
        value=1,
        category=MetricCategory.USER_BEHAVIOR,
        name=f"User Activity: {activity_type}",
        dimensions={'activity_type': activity_type},
        user_id=user_id,
        organization_id=organization_id
    )


def track_project_milestone(project_id: int, milestone_type: str, user_id: int, organization_id: Optional[int] = None):
    """Registra milestone de proyecto"""
    AnalyticsService.record_metric(
        metric_type=MetricType.ENTREPRENEUR_MILESTONE_COMPLETION,
        value=1,
        category=MetricCategory.BUSINESS_GROWTH,
        name=f"Project Milestone: {milestone_type}",
        dimensions={
            'project_id': project_id,
            'milestone_type': milestone_type
        },
        user_id=user_id,
        organization_id=organization_id
    )


def track_mentorship_session(mentor_id: int, mentee_id: int, duration_minutes: int, organization_id: Optional[int] = None):
    """Registra sesión de mentoría"""
    AnalyticsService.record_metric(
        metric_type=MetricType.MENTORSHIP_SESSION_COMPLETION,
        value=1,
        category=MetricCategory.PROGRAM_SUCCESS,
        name="Mentorship Session Completed",
        unit="sessions",
        dimensions={
            'mentor_id': mentor_id,
            'mentee_id': mentee_id,
            'duration_minutes': duration_minutes
        },
        organization_id=organization_id
    )