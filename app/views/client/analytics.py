"""
Sistema de Analytics Avanzado para clientes/stakeholders.

Este módulo implementa business intelligence y analytics predictivos:
- Dashboards interactivos con drill-down capabilities
- Machine learning para predicciones y forecasting
- Análisis de cohortes y segmentación avanzada
- Funnel analysis y conversion tracking
- Correlación y análisis causal
- Benchmarking inteligente automático
- Alertas basadas en ML y anomalías
- Data exploration tools empresariales
- Custom KPIs y métricas definidas por usuario
- Real-time streaming analytics

Tipos de analytics por cliente:
- Public: Trends básicos y métricas públicas
- Stakeholder: Business Intelligence completo
- Investor: Financial modeling y ROI analytics
- Partner: Collaboration analytics y performance
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, asdict
from typing import Any, Optional
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, session, stream_template
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, desc, asc, extract, case, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from flask_socketio import emit

from app.extensions import db, cache, socketio
from app.models.user import User
from app.models.client import Client
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.meeting import Meeting
from app.models.analytics import AnalyticsEvent
from app.core.exceptions import ValidationError, AnalyticsError
from app.utils.decorators import cache_response, log_activity, rate_limit, websocket_auth
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range_for_period, get_quarter_dates
from app.utils.math_utils import calculate_correlation, detect_anomalies, forecast_time_series
from app.services.analytics_service import AnalyticsService
from app.services.ml_service import MLService
from app.services.notification_service import NotificationService

# Importar funciones del módulo principal
from . import (
    get_client_type, get_client_permissions, require_client_permission,
    track_client_activity, cache_key_for_client
)

# Blueprint para analytics de clientes
client_analytics_bp = Blueprint(
    'client_analytics', 
    __name__, 
    url_prefix='/analytics'
)

# Configuraciones de analytics
ANALYTICS_CONFIG = {
    'CACHE_TIMEOUT': 600,  # 10 minutos
    'REAL_TIME_INTERVAL': 30,  # 30 segundos
    'MAX_DATA_POINTS': 10000,
    'ML_PREDICTION_DAYS': 90,
    'ANOMALY_THRESHOLD': 2.5,  # Desviaciones estándar
    'MIN_DATA_FOR_PREDICTION': 30,
    'MAX_CUSTOM_KPIS': 20,
    'CORRELATION_MIN_CONFIDENCE': 0.7
}

# Tipos de análisis disponibles
ANALYSIS_TYPES = {
    'descriptive': {
        'name': 'Análisis Descriptivo',
        'description': 'Qué ha pasado: métricas históricas y tendencias',
        'icon': 'fas fa-chart-bar',
        'complexity': 'basic',
        'available_for': ['public', 'stakeholder', 'investor', 'partner']
    },
    'diagnostic': {
        'name': 'Análisis Diagnóstico', 
        'description': 'Por qué ha pasado: correlaciones y causas',
        'icon': 'fas fa-search',
        'complexity': 'intermediate',
        'available_for': ['stakeholder', 'investor', 'partner']
    },
    'predictive': {
        'name': 'Análisis Predictivo',
        'description': 'Qué va a pasar: forecasting y machine learning',
        'icon': 'fas fa-crystal-ball',
        'complexity': 'advanced',
        'available_for': ['stakeholder', 'investor', 'partner']
    },
    'prescriptive': {
        'name': 'Análisis Prescriptivo',
        'description': 'Qué hacer: recomendaciones y optimización',
        'icon': 'fas fa-lightbulb',
        'complexity': 'expert',
        'available_for': ['investor', 'partner']
    }
}

# Widgets de analytics avanzados
ANALYTICS_WIDGETS = {
    'time_series_forecasting': {
        'name': 'Forecasting de Series de Tiempo',
        'category': 'predictive',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'advanced'
    },
    'cohort_analysis': {
        'name': 'Análisis de Cohortes',
        'category': 'diagnostic',
        'ml_powered': False,
        'real_time': False,
        'complexity': 'intermediate'
    },
    'funnel_conversion': {
        'name': 'Análisis de Embudo de Conversión',
        'category': 'descriptive',
        'ml_powered': False,
        'real_time': True,
        'complexity': 'intermediate'
    },
    'correlation_matrix': {
        'name': 'Matriz de Correlación',
        'category': 'diagnostic',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'advanced'
    },
    'anomaly_detection': {
        'name': 'Detección de Anomalías',
        'category': 'diagnostic',
        'ml_powered': True,
        'real_time': True,
        'complexity': 'expert'
    },
    'segment_performance': {
        'name': 'Rendimiento por Segmentos',
        'category': 'descriptive',
        'ml_powered': False,
        'real_time': True,
        'complexity': 'intermediate'
    },
    'predictive_scoring': {
        'name': 'Scoring Predictivo',
        'category': 'predictive',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'expert'
    },
    'attribution_analysis': {
        'name': 'Análisis de Atribución',
        'category': 'diagnostic',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'advanced'
    },
    'churn_prediction': {
        'name': 'Predicción de Abandono',
        'category': 'predictive',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'expert'
    },
    'optimization_recommendations': {
        'name': 'Recomendaciones de Optimización',
        'category': 'prescriptive',
        'ml_powered': True,
        'real_time': False,
        'complexity': 'expert'
    }
}


@dataclass
class AnalyticsQuery:
    """Configuración de consulta de analytics."""
    metrics: list[str]
    dimensions: list[str]
    filters: dict[str, Any]
    date_range: tuple[datetime, datetime]
    granularity: str  # daily, weekly, monthly
    aggregation: str  # sum, avg, count, etc.


@dataclass
class MLPrediction:
    """Resultado de predicción de machine learning."""
    metric: str
    predictions: list[float]
    confidence_intervals: list[tuple[float, float]]
    model_accuracy: float
    feature_importance: dict[str, float]


@client_analytics_bp.route('/')
@login_required
@require_client_permission('can_access_detailed_analytics')
@cache_response(timeout=ANALYTICS_CONFIG['CACHE_TIMEOUT'])
@log_activity('view_analytics_dashboard')
def index():
    """
    Dashboard principal de analytics empresariales.
    
    Proporciona una vista 360° con analytics descriptivos,
    diagnósticos, predictivos y prescriptivos según permisos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Análisis disponibles para el tipo de cliente
        available_analyses = {
            k: v for k, v in ANALYSIS_TYPES.items()
            if client_type in v.get('available_for', [])
        }
        
        # Widgets configurados del usuario
        user_dashboard_config = _get_user_analytics_dashboard_config(current_user.id)
        
        # Métricas clave en tiempo real
        real_time_metrics = _get_real_time_metrics(client_type, permissions)
        
        # Insights automáticos basados en ML
        ml_insights = _get_ml_generated_insights(client_type, permissions)
        
        # Alertas y anomalías detectadas
        active_alerts = _get_active_analytics_alerts(current_user.id)
        
        # Tendencias clave identificadas automáticamente
        key_trends = _get_automatically_detected_trends(client_type)
        
        # Recomendaciones de análisis
        recommended_analyses = _get_recommended_analyses(current_user.id, client_type)
        
        # Configuración para el frontend
        frontend_config = {
            'real_time_enabled': True,
            'update_interval': ANALYTICS_CONFIG['REAL_TIME_INTERVAL'],
            'ml_features_enabled': permissions.get('can_use_ml_features', False),
            'custom_kpis_limit': ANALYTICS_CONFIG['MAX_CUSTOM_KPIS'],
            'websocket_namespace': '/analytics'
        }
        
        return render_template(
            'client/analytics/index.html',
            available_analyses=available_analyses,
            user_dashboard_config=user_dashboard_config,
            real_time_metrics=real_time_metrics,
            ml_insights=ml_insights,
            active_alerts=active_alerts,
            key_trends=key_trends,
            recommended_analyses=recommended_analyses,
            analytics_widgets=ANALYTICS_WIDGETS,
            frontend_config=frontend_config,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de analytics: {str(e)}")
        flash('Error al cargar el dashboard de analytics.', 'error')
        return redirect(url_for('client.index'))


@client_analytics_bp.route('/explorer')
@login_required
@require_client_permission('can_access_detailed_analytics')
@log_activity('access_data_explorer')
def explorer():
    """
    Explorador de datos interactivo tipo BI.
    
    Permite construir consultas personalizadas, aplicar filtros,
    crear visualizaciones ad-hoc y explorar datos libremente.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Métricas disponibles según permisos
        available_metrics = _get_available_metrics(client_type, permissions)
        
        # Dimensiones disponibles para agrupación
        available_dimensions = _get_available_dimensions(client_type, permissions)
        
        # Filtros aplicables
        available_filters = _get_available_filters(client_type, permissions)
        
        # Consultas guardadas del usuario
        saved_queries = _get_user_saved_queries(current_user.id)
        
        # Templates de consultas populares
        query_templates = _get_popular_query_templates(client_type)
        
        # Configuración del explorador
        explorer_config = {
            'max_data_points': ANALYTICS_CONFIG['MAX_DATA_POINTS'],
            'auto_refresh': True,
            'export_enabled': permissions.get('can_export_basic_reports', False),
            'ml_suggestions': permissions.get('can_use_ml_features', False)
        }
        
        return render_template(
            'client/analytics/explorer.html',
            available_metrics=available_metrics,
            available_dimensions=available_dimensions,
            available_filters=available_filters,
            saved_queries=saved_queries,
            query_templates=query_templates,
            explorer_config=explorer_config,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar explorador de datos: {str(e)}")
        flash('Error al cargar el explorador de datos.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/predictive')
@login_required
@require_client_permission('can_use_ml_features')
@log_activity('access_predictive_analytics')
def predictive():
    """
    Analytics predictivos con machine learning.
    
    Forecasting, predicciones de tendencias, análisis de escenarios
    y modelado predictivo avanzado.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Modelos predictivos disponibles
        available_models = _get_available_predictive_models(client_type)
        
        # Predicciones activas y resultados
        active_predictions = _get_active_predictions(current_user.id)
        
        # Accuracy histórico de modelos
        model_performance = _get_model_performance_history(current_user.id)
        
        # Forecasts automáticos generados
        auto_forecasts = _get_automatic_forecasts(client_type, permissions)
        
        # Escenarios de simulación
        scenario_simulations = _get_scenario_simulations(client_type)
        
        # Configuración de ML
        ml_config = {
            'prediction_horizon_days': ANALYTICS_CONFIG['ML_PREDICTION_DAYS'],
            'min_data_points': ANALYTICS_CONFIG['MIN_DATA_FOR_PREDICTION'],
            'confidence_levels': [0.8, 0.9, 0.95],
            'model_types': ['linear', 'random_forest', 'neural_network']
        }
        
        return render_template(
            'client/analytics/predictive.html',
            available_models=available_models,
            active_predictions=active_predictions,
            model_performance=model_performance,
            auto_forecasts=auto_forecasts,
            scenario_simulations=scenario_simulations,
            ml_config=ml_config,
            client_type=client_type,
            permissions=permissions,
            format_number=format_number,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics predictivos: {str(e)}")
        flash('Error al cargar analytics predictivos.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/cohorts')
@login_required
@require_client_permission('can_access_detailed_analytics')
@log_activity('access_cohort_analysis')
def cohorts():
    """
    Análisis de cohortes de emprendedores.
    
    Segmentación por fecha de entrada, progreso,
    retención y performance comparativo.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de análisis
        cohort_type = request.args.get('type', 'entry_date')  # entry_date, program, industry
        metric = request.args.get('metric', 'retention')  # retention, progress, revenue
        period = request.args.get('period', 'monthly')  # weekly, monthly, quarterly
        
        # Generar análisis de cohortes
        cohort_analysis = _generate_cohort_analysis(
            cohort_type, metric, period, permissions
        )
        
        # Insights automáticos de cohortes
        cohort_insights = _generate_cohort_insights(cohort_analysis)
        
        # Comparación entre cohortes
        cohort_comparison = _compare_cohort_performance(cohort_analysis)
        
        # Segmentación avanzada
        advanced_segments = _get_advanced_cohort_segments(permissions)
        
        return render_template(
            'client/analytics/cohorts.html',
            cohort_analysis=cohort_analysis,
            cohort_insights=cohort_insights,
            cohort_comparison=cohort_comparison,
            advanced_segments=advanced_segments,
            cohort_type=cohort_type,
            metric=metric,
            period=period,
            client_type=client_type,
            permissions=permissions,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en análisis de cohortes: {str(e)}")
        flash('Error al cargar análisis de cohortes.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/correlations')
@login_required
@require_client_permission('can_use_ml_features')
@log_activity('access_correlation_analysis')
def correlations():
    """
    Análisis de correlaciones y causalidad.
    
    Identificación automática de relaciones entre variables,
    análisis de causalidad y detección de drivers clave.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Matriz de correlación automática
        correlation_matrix = _generate_correlation_matrix(permissions)
        
        # Correlaciones más significativas
        significant_correlations = _find_significant_correlations(
            correlation_matrix, ANALYTICS_CONFIG['CORRELATION_MIN_CONFIDENCE']
        )
        
        # Análisis de causalidad
        causality_analysis = _perform_causality_analysis(permissions)
        
        # Drivers clave identificados
        key_drivers = _identify_key_performance_drivers(permissions)
        
        # Recomendaciones basadas en correlaciones
        correlation_recommendations = _generate_correlation_recommendations(
            significant_correlations, key_drivers
        )
        
        return render_template(
            'client/analytics/correlations.html',
            correlation_matrix=correlation_matrix,
            significant_correlations=significant_correlations,
            causality_analysis=causality_analysis,
            key_drivers=key_drivers,
            correlation_recommendations=correlation_recommendations,
            client_type=client_type,
            permissions=permissions,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en análisis de correlaciones: {str(e)}")
        flash('Error al cargar análisis de correlaciones.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/anomalies')
@login_required
@require_client_permission('can_use_ml_features')
@log_activity('access_anomaly_detection')
def anomalies():
    """
    Detección automática de anomalías.
    
    ML para identificar patrones inusuales, outliers
    y eventos significativos en los datos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de detección
        sensitivity = request.args.get('sensitivity', 'medium')  # low, medium, high
        time_window = request.args.get('window', '30d')  # 7d, 30d, 90d
        
        # Anomalías detectadas automáticamente
        detected_anomalies = _detect_anomalies_ml(
            sensitivity, time_window, permissions
        )
        
        # Análisis de impacto de anomalías
        anomaly_impact_analysis = _analyze_anomaly_impact(detected_anomalies)
        
        # Patrones de anomalías históricas
        historical_patterns = _get_historical_anomaly_patterns(permissions)
        
        # Alertas configuradas
        configured_alerts = _get_user_anomaly_alerts(current_user.id)
        
        # Recomendaciones de investigación
        investigation_recommendations = _generate_anomaly_investigation_recommendations(
            detected_anomalies
        )
        
        return render_template(
            'client/analytics/anomalies.html',
            detected_anomalies=detected_anomalies,
            anomaly_impact_analysis=anomaly_impact_analysis,
            historical_patterns=historical_patterns,
            configured_alerts=configured_alerts,
            investigation_recommendations=investigation_recommendations,
            sensitivity=sensitivity,
            time_window=time_window,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en detección de anomalías: {str(e)}")
        flash('Error al cargar detección de anomalías.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/benchmarking')
@login_required
@require_client_permission('can_access_detailed_analytics')
@log_activity('access_benchmarking')
def benchmarking():
    """
    Benchmarking inteligente automático.
    
    Comparación con pares, industria, mejores prácticas
    y análisis competitivo automatizado.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Configuración de benchmarking
        benchmark_type = request.args.get('type', 'industry')  # industry, size, geography
        comparison_period = request.args.get('period', 'current_year')
        
        # Benchmarks automáticos generados
        industry_benchmarks = _generate_industry_benchmarks(
            benchmark_type, comparison_period, permissions
        )
        
        # Posicionamiento relativo
        relative_positioning = _calculate_relative_positioning(
            industry_benchmarks, permissions
        )
        
        # Gaps de rendimiento identificados
        performance_gaps = _identify_performance_gaps(
            industry_benchmarks, relative_positioning
        )
        
        # Best practices recomendadas
        best_practices = _recommend_best_practices(performance_gaps, client_type)
        
        # Análisis competitivo
        competitive_analysis = _generate_competitive_analysis(
            benchmark_type, permissions
        )
        
        return render_template(
            'client/analytics/benchmarking.html',
            industry_benchmarks=industry_benchmarks,
            relative_positioning=relative_positioning,
            performance_gaps=performance_gaps,
            best_practices=best_practices,
            competitive_analysis=competitive_analysis,
            benchmark_type=benchmark_type,
            comparison_period=comparison_period,
            client_type=client_type,
            permissions=permissions,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en benchmarking: {str(e)}")
        flash('Error al cargar benchmarking.', 'error')
        return redirect(url_for('client_analytics.index'))


@client_analytics_bp.route('/real-time')
@login_required
@require_client_permission('can_access_detailed_analytics')
@log_activity('access_real_time_analytics')
def real_time():
    """
    Analytics en tiempo real con WebSockets.
    
    Métricas streaming, dashboards live y alertas
    instantáneas basadas en eventos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Configuración de tiempo real
        real_time_config = {
            'update_interval': ANALYTICS_CONFIG['REAL_TIME_INTERVAL'],
            'websocket_namespace': '/analytics',
            'max_history_points': 100,
            'alert_thresholds': _get_user_alert_thresholds(current_user.id)
        }
        
        # Métricas en tiempo real disponibles
        available_real_time_metrics = _get_available_real_time_metrics(
            client_type, permissions
        )
        
        # Dashboard configurado del usuario
        user_real_time_dashboard = _get_user_real_time_dashboard(current_user.id)
        
        # Estado actual de métricas
        current_metrics_state = _get_current_metrics_snapshot(
            client_type, permissions
        )
        
        return render_template(
            'client/analytics/real_time.html',
            real_time_config=real_time_config,
            available_real_time_metrics=available_real_time_metrics,
            user_real_time_dashboard=user_real_time_dashboard,
            current_metrics_state=current_metrics_state,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics en tiempo real: {str(e)}")
        flash('Error al cargar analytics en tiempo real.', 'error')
        return redirect(url_for('client_analytics.index'))


# API Endpoints para funcionalidades avanzadas

@client_analytics_bp.route('/api/query', methods=['POST'])
@login_required
@require_client_permission('can_access_detailed_analytics')
@rate_limit('60 per minute')
def api_custom_query():
    """API endpoint para consultas personalizadas del explorador."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener configuración de la consulta
        query_data = request.get_json()
        
        # Validar y construir consulta
        analytics_query = _build_analytics_query(query_data, permissions)
        
        # Ejecutar consulta
        query_result = _execute_analytics_query(analytics_query, permissions)
        
        # Aplicar transformaciones si se especifican
        if query_data.get('transformations'):
            query_result = _apply_query_transformations(
                query_result, query_data['transformations']
            )
        
        # Registrar consulta para analytics de uso
        track_client_activity('custom_query_executed', {
            'metrics_count': len(analytics_query.metrics),
            'dimensions_count': len(analytics_query.dimensions),
            'filters_count': len(analytics_query.filters),
            'result_rows': len(query_result.get('data', []))
        })
        
        return jsonify({
            'success': True,
            'data': query_result['data'],
            'metadata': query_result['metadata'],
            'execution_time_ms': query_result['execution_time'],
            'cache_hit': query_result.get('cache_hit', False)
        })
        
    except ValidationError as e:
        return jsonify({'success': False, 'error': f'Consulta inválida: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Error en consulta personalizada: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_analytics_bp.route('/api/predict', methods=['POST'])
@login_required
@require_client_permission('can_use_ml_features')
@rate_limit('20 per hour')
def api_ml_prediction():
    """API endpoint para predicciones con machine learning."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener parámetros de predicción
        prediction_data = request.get_json()
        
        metric = prediction_data.get('metric')
        horizon_days = prediction_data.get('horizon_days', 30)
        model_type = prediction_data.get('model_type', 'auto')
        confidence_level = prediction_data.get('confidence_level', 0.9)
        
        # Validar parámetros
        if not metric or metric not in _get_predictable_metrics(client_type):
            return jsonify({'error': 'Métrica no válida para predicción'}), 400
        
        if horizon_days > ANALYTICS_CONFIG['ML_PREDICTION_DAYS']:
            return jsonify({'error': f'Horizonte máximo: {ANALYTICS_CONFIG["ML_PREDICTION_DAYS"]} días'}), 400
        
        # Generar predicción
        ml_prediction = _generate_ml_prediction(
            metric, horizon_days, model_type, confidence_level, permissions
        )
        
        if ml_prediction.model_accuracy < 0.6:  # Accuracy mínimo
            return jsonify({
                'success': False,
                'error': 'Datos insuficientes para predicción confiable',
                'min_accuracy': 0.6,
                'current_accuracy': ml_prediction.model_accuracy
            }), 422
        
        # Guardar predicción para seguimiento
        prediction_id = _save_ml_prediction(ml_prediction, current_user.id)
        
        track_client_activity('ml_prediction_generated', {
            'metric': metric,
            'horizon_days': horizon_days,
            'model_accuracy': ml_prediction.model_accuracy,
            'prediction_id': prediction_id
        })
        
        return jsonify({
            'success': True,
            'prediction_id': prediction_id,
            'metric': ml_prediction.metric,
            'predictions': ml_prediction.predictions,
            'confidence_intervals': ml_prediction.confidence_intervals,
            'model_accuracy': ml_prediction.model_accuracy,
            'feature_importance': ml_prediction.feature_importance,
            'horizon_days': horizon_days
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en predicción ML: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_analytics_bp.route('/api/correlations')
@login_required
@require_client_permission('can_use_ml_features')
@cache_response(timeout=1800)  # 30 minutos
def api_correlation_analysis():
    """API endpoint para análisis de correlaciones."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de análisis
        variables = request.args.getlist('variables')
        method = request.args.get('method', 'pearson')  # pearson, spearman, kendall
        min_confidence = float(request.args.get('min_confidence', 0.7))
        
        # Validar variables
        available_vars = _get_available_correlation_variables(client_type)
        invalid_vars = [v for v in variables if v not in available_vars]
        if invalid_vars:
            return jsonify({'error': f'Variables inválidas: {invalid_vars}'}), 400
        
        # Generar análisis de correlación
        correlation_results = _analyze_correlations(
            variables, method, min_confidence, permissions
        )
        
        return jsonify({
            'success': True,
            'correlations': correlation_results['correlations'],
            'significant_pairs': correlation_results['significant_pairs'],
            'method': method,
            'confidence_level': min_confidence,
            'variable_count': len(variables)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en análisis de correlaciones: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_analytics_bp.route('/api/anomalies/detect', methods=['POST'])
@login_required
@require_client_permission('can_use_ml_features')
def api_detect_anomalies():
    """API endpoint para detección de anomalías en tiempo real."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener parámetros
        detection_data = request.get_json()
        
        metric = detection_data.get('metric')
        sensitivity = detection_data.get('sensitivity', 'medium')
        time_window_days = detection_data.get('time_window_days', 30)
        
        # Validar métrica
        if metric not in _get_anomaly_detectable_metrics(client_type):
            return jsonify({'error': 'Métrica no válida para detección'}), 400
        
        # Detectar anomalías
        anomalies = _detect_metric_anomalies(
            metric, sensitivity, time_window_days, permissions
        )
        
        return jsonify({
            'success': True,
            'metric': metric,
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies,
            'sensitivity': sensitivity,
            'time_window_days': time_window_days
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en detección de anomalías: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_analytics_bp.route('/api/real-time/metrics')
@login_required
@require_client_permission('can_access_detailed_analytics')
def api_real_time_metrics():
    """API endpoint para métricas en tiempo real."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Métricas solicitadas
        requested_metrics = request.args.getlist('metrics')
        
        # Obtener valores actuales
        current_values = _get_real_time_metric_values(
            requested_metrics, client_type, permissions
        )
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': current_values,
            'next_update': (datetime.now(timezone.utc) + timedelta(
                seconds=ANALYTICS_CONFIG['REAL_TIME_INTERVAL']
            )).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en métricas tiempo real: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_analytics_bp.route('/api/dashboard/save', methods=['POST'])
@login_required
@require_client_permission('can_access_detailed_analytics')
def api_save_dashboard_config():
    """API endpoint para guardar configuración de dashboard."""
    try:
        config_data = request.get_json()
        
        # Validar configuración
        if not _validate_dashboard_config(config_data):
            return jsonify({'error': 'Configuración de dashboard inválida'}), 400
        
        # Guardar configuración
        success = _save_user_analytics_dashboard_config(
            current_user.id, config_data
        )
        
        if success:
            track_client_activity('analytics_dashboard_configured', {
                'widgets_count': len(config_data.get('widgets', [])),
                'layout_type': config_data.get('layout', 'grid')
            })
            
            return jsonify({
                'success': True,
                'message': 'Configuración guardada exitosamente'
            })
        else:
            return jsonify({'error': 'Error al guardar configuración'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error guardando configuración dashboard: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# WebSocket handlers para tiempo real

@socketio.on('join_analytics', namespace='/analytics')
@websocket_auth
def join_analytics_room():
    """Usuario se une a room de analytics en tiempo real."""
    from flask_socketio import join_room
    
    user_id = current_user.id
    room = f'analytics_{user_id}'
    join_room(room)
    
    emit('joined_analytics', {
        'message': 'Conectado a analytics en tiempo real',
        'update_interval': ANALYTICS_CONFIG['REAL_TIME_INTERVAL']
    })


@socketio.on('request_metric_update', namespace='/analytics')
@websocket_auth
def handle_metric_update_request(data):
    """Maneja solicitudes de actualización de métricas específicas."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        metric = data.get('metric')
        
        # Obtener valor actual de la métrica
        current_value = _get_real_time_metric_value(
            metric, client_type, permissions
        )
        
        emit('metric_updated', {
            'metric': metric,
            'value': current_value,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en actualización WebSocket: {str(e)}")
        emit('error', {'message': 'Error al actualizar métrica'})


# Funciones auxiliares privadas

def _get_user_analytics_dashboard_config(user_id):
    """Obtiene configuración del dashboard de analytics del usuario."""
    # En implementación real, esto vendría de base de datos
    return {
        'layout': 'grid',
        'widgets': [
            {
                'type': 'time_series_forecasting',
                'position': {'x': 0, 'y': 0, 'w': 6, 'h': 4},
                'config': {'metric': 'projects_completed', 'horizon_days': 30}
            },
            {
                'type': 'correlation_matrix',
                'position': {'x': 6, 'y': 0, 'w': 6, 'h': 4},
                'config': {'variables': ['jobs_created', 'revenue_generated']}
            }
        ],
        'refresh_interval': 300,
        'auto_refresh': True
    }


def _get_real_time_metrics(client_type, permissions):
    """Obtiene métricas en tiempo real según tipo de cliente."""
    base_metrics = {
        'active_projects': _count_active_projects(),
        'entrepreneurs_online': _count_online_entrepreneurs(),
        'recent_activities': _count_recent_activities()
    }
    
    if permissions.get('can_view_financial_metrics'):
        base_metrics.update({
            'revenue_today': _get_revenue_today(),
            'investment_pipeline_value': _get_pipeline_value()
        })
    
    return base_metrics


def _get_ml_generated_insights(client_type, permissions):
    """Genera insights automáticos usando machine learning."""
    insights = []
    
    try:
        # Insight sobre tendencias
        trend_insight = MLService.generate_trend_insight(client_type)
        if trend_insight:
            insights.append({
                'type': 'trend',
                'title': 'Tendencia Detectada',
                'description': trend_insight['description'],
                'confidence': trend_insight['confidence'],
                'action_recommended': trend_insight.get('action')
            })
        
        # Insight sobre anomalías
        anomaly_insight = MLService.generate_anomaly_insight(permissions)
        if anomaly_insight:
            insights.append({
                'type': 'anomaly',
                'title': 'Anomalía Detectada',
                'description': anomaly_insight['description'],
                'severity': anomaly_insight['severity'],
                'investigation_needed': True
            })
        
        # Insight predictivo
        if permissions.get('can_use_ml_features'):
            prediction_insight = MLService.generate_prediction_insight(client_type)
            if prediction_insight:
                insights.append({
                    'type': 'prediction',
                    'title': 'Predicción Importante',
                    'description': prediction_insight['description'],
                    'timeline': prediction_insight['timeline'],
                    'action_recommended': prediction_insight.get('action')
                })
    
    except Exception as e:
        current_app.logger.error(f"Error generando insights ML: {str(e)}")
    
    return insights


def _get_active_analytics_alerts(user_id):
    """Obtiene alertas activas de analytics para el usuario."""
    # En implementación real, esto vendría de base de datos
    return [
        {
            'id': 'alert_1',
            'type': 'anomaly',
            'metric': 'project_completion_rate',
            'message': 'Tasa de finalización de proyectos por debajo del umbral',
            'severity': 'warning',
            'created_at': datetime.now(timezone.utc) - timedelta(hours=2),
            'threshold': 75,
            'current_value': 68
        }
    ]


def _generate_cohort_analysis(cohort_type, metric, period, permissions):
    """Genera análisis completo de cohortes."""
    # Implementación simplificada - en producción sería más complejo
    cohorts_data = {}
    
    if cohort_type == 'entry_date':
        # Análisis por fecha de entrada al programa
        cohorts_data = _analyze_entry_date_cohorts(metric, period)
    elif cohort_type == 'program':
        # Análisis por programa de emprendimiento
        cohorts_data = _analyze_program_cohorts(metric, period)
    elif cohort_type == 'industry':
        # Análisis por industria
        cohorts_data = _analyze_industry_cohorts(metric, period)
    
    return cohorts_data


def _generate_correlation_matrix(permissions):
    """Genera matriz de correlación para variables clave."""
    # Variables base disponibles para todos
    variables = [
        'projects_completed', 'jobs_created', 'entrepreneurs_active',
        'mentorship_hours', 'training_sessions'
    ]
    
    # Variables adicionales según permisos
    if permissions.get('can_view_financial_metrics'):
        variables.extend(['revenue_generated', 'investment_attracted'])
    
    # Simular matriz de correlación
    correlation_matrix = {}
    for i, var1 in enumerate(variables):
        correlation_matrix[var1] = {}
        for j, var2 in enumerate(variables):
            if i == j:
                correlation_matrix[var1][var2] = 1.0
            else:
                # Simular correlación (en producción se calcularía con datos reales)
                correlation_matrix[var1][var2] = np.random.uniform(-1, 1)
    
    return correlation_matrix


def _build_analytics_query(query_data, permissions):
    """Construye objeto de consulta validado."""
    metrics = query_data.get('metrics', [])
    dimensions = query_data.get('dimensions', [])
    filters = query_data.get('filters', {})
    
    # Validar métricas disponibles
    available_metrics = _get_available_metrics('stakeholder', permissions)  # Simplificado
    invalid_metrics = [m for m in metrics if m not in available_metrics]
    if invalid_metrics:
        raise ValidationError(f'Métricas no disponibles: {invalid_metrics}')
    
    # Parsear rango de fechas
    date_range_str = query_data.get('date_range', 'current_month')
    start_date, end_date = get_date_range_for_period(date_range_str)
    
    return AnalyticsQuery(
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        date_range=(start_date, end_date),
        granularity=query_data.get('granularity', 'daily'),
        aggregation=query_data.get('aggregation', 'sum')
    )


def _execute_analytics_query(query, permissions):
    """Ejecuta consulta de analytics y retorna resultados."""
    start_time = datetime.now(timezone.utc)
    
    # Simular ejecución de consulta
    # En producción, esto ejecutaría la consulta real contra la base de datos
    data = []
    for i in range(30):  # 30 días de datos simulados
        row = {'date': (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()}
        for metric in query.metrics:
            row[metric] = np.random.randint(1, 100)
        data.append(row)
    
    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    return {
        'data': data,
        'metadata': {
            'row_count': len(data),
            'columns': ['date'] + query.metrics,
            'query_hash': hash(str(query))
        },
        'execution_time': execution_time
    }


def _generate_ml_prediction(metric, horizon_days, model_type, confidence_level, permissions):
    """Genera predicción usando machine learning."""
    # Obtener datos históricos para entrenamiento
    historical_data = _get_historical_data_for_prediction(metric, permissions)
    
    if len(historical_data) < ANALYTICS_CONFIG['MIN_DATA_FOR_PREDICTION']:
        raise AnalyticsError(f'Datos insuficientes para predicción. Mínimo: {ANALYTICS_CONFIG["MIN_DATA_FOR_PREDICTION"]} puntos')
    
    # Preparar datos para ML
    X, y = _prepare_ml_data(historical_data)
    
    # Entrenar modelo según tipo
    if model_type == 'linear' or model_type == 'auto':
        model = LinearRegression()
    elif model_type == 'random_forest':
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        model = LinearRegression()  # Fallback
    
    # Entrenar
    model.fit(X, y)
    
    # Generar predicciones
    future_X = _generate_future_features(horizon_days)
    predictions = model.predict(future_X).tolist()
    
    # Calcular intervalos de confianza (simplificado)
    prediction_std = np.std(predictions)
    confidence_intervals = [
        (pred - prediction_std, pred + prediction_std) 
        for pred in predictions
    ]
    
    # Calcular accuracy del modelo
    model_accuracy = model.score(X, y)
    
    # Feature importance (si aplicable)
    feature_importance = {}
    if hasattr(model, 'feature_importances_'):
        feature_names = ['trend', 'seasonality', 'lag_1', 'lag_7']
        feature_importance = dict(zip(feature_names, model.feature_importances_))
    
    return MLPrediction(
        metric=metric,
        predictions=predictions,
        confidence_intervals=confidence_intervals,
        model_accuracy=model_accuracy,
        feature_importance=feature_importance
    )


def _get_available_metrics(client_type, permissions):
    """Obtiene métricas disponibles según tipo de cliente."""
    base_metrics = [
        'projects_completed', 'entrepreneurs_active', 'jobs_created',
        'mentorship_hours', 'training_sessions', 'direct_beneficiaries'
    ]
    
    if permissions.get('can_view_financial_metrics'):
        base_metrics.extend([
            'revenue_generated', 'investment_attracted', 'roi_percentage',
            'operational_costs', 'profit_margin'
        ])
    
    if permissions.get('can_view_partnership_metrics'):
        base_metrics.extend([
            'partnership_projects', 'shared_resources', 'collaboration_efficiency'
        ])
    
    return base_metrics


def _get_available_dimensions(client_type, permissions):
    """Obtiene dimensiones disponibles para agrupación."""
    dimensions = [
        'date', 'entrepreneur_id', 'project_id', 'industry',
        'location', 'program_id', 'organization_id'
    ]
    
    if permissions.get('can_access_detailed_analytics'):
        dimensions.extend([
            'entrepreneur_age_group', 'entrepreneur_gender',
            'project_stage', 'funding_status'
        ])
    
    return dimensions


# Funciones auxiliares para métricas específicas

def _count_active_projects():
    """Cuenta proyectos activos actualmente."""
    return Project.query.filter_by(status='active', is_public=True).count()


def _count_online_entrepreneurs():
    """Cuenta emprendedores activos recientemente."""
    # Actividad en las últimas 24 horas
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return (
        Entrepreneur.query
        .join(User)
        .filter(
            Entrepreneur.is_public == True,
            User.last_seen >= cutoff
        )
        .count()
    )


def _count_recent_activities():
    """Cuenta actividades recientes del ecosistema."""
    # Actividades en las últimas 6 horas
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    return (
        AnalyticsEvent.query
        .filter(AnalyticsEvent.created_at >= cutoff)
        .count()
    )


def _get_revenue_today():
    """Obtiene ingresos generados hoy."""
    today = datetime.now(timezone.utc).date()
    return (
        db.session.query(func.sum(Project.revenue_generated))
        .filter(
            Project.is_public == True,
            func.date(Project.completed_at) == today
        )
        .scalar() or 0
    )


# Funciones placeholder para ML y análisis avanzado

def _get_historical_data_for_prediction(metric, permissions):
    """Obtiene datos históricos para entrenar modelo predictivo."""
    # Implementación simplificada
    return [{'value': np.random.randint(10, 100), 'date': datetime.now(timezone.utc) - timedelta(days=i)} for i in range(90)]


def _prepare_ml_data(historical_data):
    """Prepara datos para machine learning."""
    # Implementación simplificada - extraer features y targets
    X = np.array([[i, i%7, (i-1)%30] for i in range(len(historical_data))])  # Trend, day_of_week, day_of_month
    y = np.array([d['value'] for d in historical_data])
    return X, y


def _generate_future_features(horizon_days):
    """Genera features para predicciones futuras."""
    base_day = len(range(90))  # Continúa desde los datos históricos
    return np.array([[base_day + i, (base_day + i)%7, (base_day + i)%30] for i in range(horizon_days)])


# Manejadores de errores específicos

@client_analytics_bp.errorhandler(AnalyticsError)
def analytics_error(error):
    """Maneja errores específicos de analytics."""
    return jsonify({'success': False, 'error': str(error)}), 422


@client_analytics_bp.errorhandler(403)
def analytics_forbidden(error):
    """Maneja errores de permisos en analytics."""
    flash('No tienes permisos para acceder a esta funcionalidad de analytics.', 'error')
    return redirect(url_for('client_analytics.index'))


@client_analytics_bp.errorhandler(500)
def analytics_internal_error(error):
    """Maneja errores internos en analytics."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en analytics: {str(error)}")
    flash('Error interno en analytics. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('client.index'))