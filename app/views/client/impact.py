"""
Vistas de métricas de impacto para clientes/stakeholders.

Este módulo maneja la visualización y análisis del impacto del ecosistema:
- Métricas de impacto social, económico y ambiental
- Indicadores de desarrollo y progreso
- Análisis comparativo temporal
- Visualizaciones interactivas y dashboards
- Reportes de impacto exportables
- KPIs específicos por tipo de cliente

Tipos de impacto medidos:
- Social: Empleos creados, beneficiarios, capacitaciones
- Económico: Ingresos generados, inversión atraída, crecimiento
- Ambiental: Sostenibilidad, reducción emisiones, eco-innovación
- Desarrollo: Habilidades, redes, oportunidades creadas
"""

import json
import math
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict, OrderedDict

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file
)
from flask_login import current_user
from sqlalchemy import and_, or_, func, desc, asc, extract, case, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db, cache
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.meeting import Meeting
from app.models.mentorship import MentorshipSession
from app.models.analytics import AnalyticsEvent
from app.core.exceptions import ValidationError, PermissionError
from app.utils.decorators import cache_response, log_activity, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range_for_period, get_quarter_dates, get_year_range
from app.utils.export_utils import generate_impact_report_pdf, generate_impact_report_excel
from app.services.analytics_service import AnalyticsService

# Importar funciones del módulo principal
from . import (
    get_client_type, get_client_permissions, require_client_permission,
    track_client_activity, cache_key_for_client
)

# Blueprint para métricas de impacto de clientes
client_impact_bp = Blueprint(
    'client_impact', 
    __name__, 
    url_prefix='/impact'
)

# Configuraciones de impacto
IMPACT_CONFIG = {
    'DEFAULT_PERIOD': 'current_year',
    'CACHE_TIMEOUT': 900,  # 15 minutos
    'MAX_COMPARISON_PERIODS': 5,
    'MIN_DATA_POINTS': 3,
    'CHART_COLORS': [
        '#3B82F6', '#10B981', '#F59E0B', '#EF4444', 
        '#8B5CF6', '#06B6D4', '#84CC16', '#F97316'
    ]
}

# Categorías de impacto
IMPACT_CATEGORIES = {
    'social': {
        'name': 'Impacto Social',
        'icon': 'fas fa-users',
        'color': '#10B981',
        'metrics': ['jobs_created', 'direct_beneficiaries', 'training_sessions', 'communities_reached']
    },
    'economic': {
        'name': 'Impacto Económico', 
        'icon': 'fas fa-chart-line',
        'color': '#3B82F6',
        'metrics': ['revenue_generated', 'investment_attracted', 'gdp_contribution', 'tax_generation']
    },
    'environmental': {
        'name': 'Impacto Ambiental',
        'icon': 'fas fa-leaf',
        'color': '#84CC16',
        'metrics': ['carbon_reduction', 'waste_reduction', 'energy_saved', 'sustainability_score']
    },
    'development': {
        'name': 'Desarrollo de Capacidades',
        'icon': 'fas fa-graduation-cap',
        'color': '#8B5CF6',
        'metrics': ['skills_developed', 'mentorship_hours', 'networks_created', 'knowledge_transfer']
    }
}

# Métricas disponibles por tipo de cliente
AVAILABLE_METRICS = {
    'public': ['jobs_created', 'direct_beneficiaries', 'revenue_generated', 'projects_completed'],
    'stakeholder': [
        'jobs_created', 'direct_beneficiaries', 'revenue_generated', 'projects_completed',
        'training_sessions', 'communities_reached', 'investment_attracted', 'mentorship_hours'
    ],
    'investor': [
        'revenue_generated', 'investment_attracted', 'gdp_contribution', 'tax_generation',
        'roi_metrics', 'market_penetration', 'scalability_index', 'exit_value'
    ],
    'partner': [
        'collaborative_projects', 'shared_resources', 'joint_impact', 'partnership_efficiency',
        'resource_utilization', 'synergy_metrics', 'co_creation_value'
    ]
}


@client_impact_bp.route('/')
@cache_response(timeout=IMPACT_CONFIG['CACHE_TIMEOUT'])
@log_activity('view_impact_dashboard')
def index():
    """
    Dashboard principal de métricas de impacto.
    
    Muestra indicadores clave de impacto del ecosistema
    con visualizaciones interactivas según permisos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Período de análisis
        period = request.args.get('period', IMPACT_CONFIG['DEFAULT_PERIOD'])
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas principales de impacto
        impact_overview = _get_impact_overview(start_date, end_date, permissions)
        
        # Métricas por categoría
        categorized_impact = _get_categorized_impact(start_date, end_date, permissions)
        
        # Tendencias históricas
        historical_trends = _get_historical_trends(start_date, end_date, permissions)
        
        # Impacto por programa/organización
        program_impact = _get_program_impact(start_date, end_date, permissions)
        
        # Top emprendedores por impacto
        top_impact_entrepreneurs = _get_top_impact_entrepreneurs(start_date, end_date, permissions)
        
        # Comparación con objetivos
        goal_comparison = _get_goal_comparison(start_date, end_date, permissions)
        
        # Métricas geográficas
        geographic_impact = _get_geographic_impact(start_date, end_date, permissions)
        
        # Datos para filtros
        filter_options = _get_impact_filter_options(permissions)
        
        return render_template(
            'client/impact/index.html',
            impact_overview=impact_overview,
            categorized_impact=categorized_impact,
            historical_trends=historical_trends,
            program_impact=program_impact,
            top_impact_entrepreneurs=top_impact_entrepreneurs,
            goal_comparison=goal_comparison,
            geographic_impact=geographic_impact,
            filter_options=filter_options,
            impact_categories=IMPACT_CATEGORIES,
            period=period,
            start_date=start_date,
            end_date=end_date,
            client_type=client_type,
            permissions=permissions,
            chart_colors=IMPACT_CONFIG['CHART_COLORS'],
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de impacto: {str(e)}")
        flash('Error al cargar las métricas de impacto.', 'error')
        return redirect(url_for('client.index'))


@client_impact_bp.route('/social')
@log_activity('view_social_impact')
def social():
    """
    Métricas detalladas de impacto social.
    
    Incluye empleos creados, beneficiarios directos,
    capacitaciones y alcance comunitario.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de filtrado
        period = request.args.get('period', 'current_year')
        organization_id = request.args.get('organization_id', type=int)
        program_id = request.args.get('program_id', type=int)
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas sociales principales
        social_metrics = _get_social_impact_metrics(
            start_date, end_date, organization_id, program_id, permissions
        )
        
        # Distribución de beneficiarios
        beneficiary_distribution = _get_beneficiary_distribution(
            start_date, end_date, organization_id, program_id
        )
        
        # Empleos por sector/industria
        jobs_by_sector = _get_jobs_by_sector(
            start_date, end_date, organization_id, program_id
        )
        
        # Impacto en comunidades
        community_impact = _get_community_impact(
            start_date, end_date, organization_id, program_id
        )
        
        # Capacitaciones y desarrollo
        training_metrics = _get_training_metrics(
            start_date, end_date, organization_id, program_id
        )
        
        # Historias de éxito
        success_stories = _get_social_success_stories(permissions)
        
        # Comparación temporal
        temporal_comparison = _get_social_temporal_comparison(
            start_date, end_date, organization_id, program_id
        )
        
        # Opciones de filtro
        filter_options = _get_impact_filter_options(permissions)
        
        return render_template(
            'client/impact/social.html',
            social_metrics=social_metrics,
            beneficiary_distribution=beneficiary_distribution,
            jobs_by_sector=jobs_by_sector,
            community_impact=community_impact,
            training_metrics=training_metrics,
            success_stories=success_stories,
            temporal_comparison=temporal_comparison,
            filter_options=filter_options,
            period=period,
            organization_id=organization_id,
            program_id=program_id,
            start_date=start_date,
            end_date=end_date,
            permissions=permissions,
            format_currency=format_currency,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en impacto social: {str(e)}")
        flash('Error al cargar las métricas de impacto social.', 'error')
        return redirect(url_for('client_impact.index'))


@client_impact_bp.route('/economic')
@require_client_permission('can_view_financial_metrics')
@log_activity('view_economic_impact')
def economic():
    """
    Métricas de impacto económico para inversores.
    
    ROI, ingresos generados, inversión atraída,
    contribución al PIB y generación de impuestos.
    """
    try:
        # Parámetros de filtrado
        period = request.args.get('period', 'current_year')
        currency = request.args.get('currency', 'USD')
        sector = request.args.get('sector', 'all')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas económicas principales
        economic_metrics = _get_economic_impact_metrics(
            start_date, end_date, currency, sector
        )
        
        # ROI y métricas financieras
        financial_performance = _get_financial_performance_metrics(
            start_date, end_date, currency
        )
        
        # Inversión atraída y funding
        investment_metrics = _get_investment_metrics(
            start_date, end_date, currency
        )
        
        # Contribución al PIB
        gdp_contribution = _get_gdp_contribution(
            start_date, end_date, currency
        )
        
        # Análisis por sector
        sector_analysis = _get_sector_economic_analysis(
            start_date, end_date, currency
        )
        
        # Multiplicadores económicos
        economic_multipliers = _get_economic_multipliers(
            start_date, end_date
        )
        
        # Proyecciones económicas
        economic_projections = _get_economic_projections(
            start_date, end_date, currency
        )
        
        return render_template(
            'client/impact/economic.html',
            economic_metrics=economic_metrics,
            financial_performance=financial_performance,
            investment_metrics=investment_metrics,
            gdp_contribution=gdp_contribution,
            sector_analysis=sector_analysis,
            economic_multipliers=economic_multipliers,
            economic_projections=economic_projections,
            period=period,
            currency=currency,
            sector=sector,
            start_date=start_date,
            end_date=end_date,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en impacto económico: {str(e)}")
        flash('Error al cargar las métricas de impacto económico.', 'error')
        return redirect(url_for('client_impact.index'))


@client_impact_bp.route('/environmental')
@log_activity('view_environmental_impact')
def environmental():
    """
    Métricas de impacto ambiental y sostenibilidad.
    
    Reducción de emisiones, eficiencia energética,
    gestión de residuos y innovación verde.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de filtrado
        period = request.args.get('period', 'current_year')
        metric_type = request.args.get('metric_type', 'carbon')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas ambientales principales
        environmental_metrics = _get_environmental_impact_metrics(
            start_date, end_date, permissions
        )
        
        # Reducción de emisiones de carbono
        carbon_metrics = _get_carbon_reduction_metrics(
            start_date, end_date
        )
        
        # Eficiencia energética
        energy_metrics = _get_energy_efficiency_metrics(
            start_date, end_date
        )
        
        # Gestión de residuos
        waste_metrics = _get_waste_reduction_metrics(
            start_date, end_date
        )
        
        # Proyectos de innovación verde
        green_innovation = _get_green_innovation_projects(
            start_date, end_date, permissions
        )
        
        # Puntuación de sostenibilidad
        sustainability_score = _get_sustainability_score(
            start_date, end_date
        )
        
        # Comparación con estándares
        standards_comparison = _get_environmental_standards_comparison(
            start_date, end_date
        )
        
        return render_template(
            'client/impact/environmental.html',
            environmental_metrics=environmental_metrics,
            carbon_metrics=carbon_metrics,
            energy_metrics=energy_metrics,
            waste_metrics=waste_metrics,
            green_innovation=green_innovation,
            sustainability_score=sustainability_score,
            standards_comparison=standards_comparison,
            period=period,
            metric_type=metric_type,
            start_date=start_date,
            end_date=end_date,
            permissions=permissions,
            format_number=format_number,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en impacto ambiental: {str(e)}")
        flash('Error al cargar las métricas de impacto ambiental.', 'error')
        return redirect(url_for('client_impact.index'))


@client_impact_bp.route('/development')
@require_client_permission('can_access_detailed_analytics')
@log_activity('view_development_impact')
def development():
    """
    Métricas de desarrollo de capacidades.
    
    Habilidades desarrolladas, mentoría, redes creadas
    y transferencia de conocimiento.
    """
    try:
        # Parámetros de filtrado
        period = request.args.get('period', 'current_year')
        skill_category = request.args.get('skill_category', 'all')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas de desarrollo principales
        development_metrics = _get_development_impact_metrics(
            start_date, end_date, skill_category
        )
        
        # Habilidades desarrolladas
        skills_metrics = _get_skills_development_metrics(
            start_date, end_date, skill_category
        )
        
        # Métricas de mentoría
        mentorship_metrics = _get_mentorship_impact_metrics(
            start_date, end_date
        )
        
        # Redes y conexiones creadas
        network_metrics = _get_network_creation_metrics(
            start_date, end_date
        )
        
        # Transferencia de conocimiento
        knowledge_transfer = _get_knowledge_transfer_metrics(
            start_date, end_date
        )
        
        # Progreso individual de emprendedores
        individual_progress = _get_individual_progress_metrics(
            start_date, end_date
        )
        
        # Evaluación de capacidades
        capacity_assessment = _get_capacity_assessment(
            start_date, end_date
        )
        
        return render_template(
            'client/impact/development.html',
            development_metrics=development_metrics,
            skills_metrics=skills_metrics,
            mentorship_metrics=mentorship_metrics,
            network_metrics=network_metrics,
            knowledge_transfer=knowledge_transfer,
            individual_progress=individual_progress,
            capacity_assessment=capacity_assessment,
            period=period,
            skill_category=skill_category,
            start_date=start_date,
            end_date=end_date,
            format_number=format_number,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en desarrollo de capacidades: {str(e)}")
        flash('Error al cargar las métricas de desarrollo.', 'error')
        return redirect(url_for('client_impact.index'))


@client_impact_bp.route('/comparative')
@require_client_permission('can_access_detailed_analytics')
@log_activity('view_comparative_impact')
def comparative():
    """
    Análisis comparativo de impacto.
    
    Comparaciones temporales, entre programas,
    organizaciones y benchmarking sectorial.
    """
    try:
        # Parámetros de comparación
        comparison_type = request.args.get('type', 'temporal')
        period1 = request.args.get('period1', 'current_year')
        period2 = request.args.get('period2', 'previous_year')
        dimension = request.args.get('dimension', 'all')
        
        # Análisis comparativo según tipo
        if comparison_type == 'temporal':
            comparison_data = _get_temporal_comparison(period1, period2, dimension)
        elif comparison_type == 'programs':
            comparison_data = _get_programs_comparison(period1, dimension)
        elif comparison_type == 'organizations':
            comparison_data = _get_organizations_comparison(period1, dimension)
        elif comparison_type == 'sectors':
            comparison_data = _get_sectors_comparison(period1, dimension)
        else:
            comparison_data = _get_temporal_comparison(period1, period2, dimension)
        
        # Análisis estadístico
        statistical_analysis = _get_statistical_analysis(comparison_data)
        
        # Insights y recomendaciones
        insights = _get_comparative_insights(comparison_data, comparison_type)
        
        # Visualizaciones comparativas
        chart_data = _get_comparative_chart_data(comparison_data, comparison_type)
        
        return render_template(
            'client/impact/comparative.html',
            comparison_data=comparison_data,
            statistical_analysis=statistical_analysis,
            insights=insights,
            chart_data=chart_data,
            comparison_type=comparison_type,
            period1=period1,
            period2=period2,
            dimension=dimension,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en análisis comparativo: {str(e)}")
        flash('Error al cargar el análisis comparativo.', 'error')
        return redirect(url_for('client_impact.index'))


@client_impact_bp.route('/export')
@require_client_permission('can_export_basic_reports')
@log_activity('export_impact_report')
def export():
    """
    Exporta reportes de impacto en diferentes formatos.
    
    Genera reportes completos con métricas, gráficos
    y análisis según permisos del cliente.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de exportación
        format_type = request.args.get('format', 'pdf')
        report_type = request.args.get('report_type', 'overview')
        period = request.args.get('period', 'current_year')
        include_charts = request.args.get('include_charts', 'true') == 'true'
        include_analysis = request.args.get('include_analysis', 'true') == 'true'
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Generar datos del reporte
        report_data = _generate_impact_report_data(
            report_type, start_date, end_date, permissions, 
            include_charts, include_analysis
        )
        
        # Configuración del reporte
        report_config = {
            'client_type': client_type,
            'permissions': permissions,
            'report_type': report_type,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'include_charts': include_charts,
            'include_analysis': include_analysis,
            'generated_at': datetime.utcnow(),
            'generated_by': current_user.name if current_user.is_authenticated else 'Cliente'
        }
        
        # Generar archivo según formato
        if format_type == 'excel':
            file_path = generate_impact_report_excel(report_data, report_config)
            filename = f'reporte_impacto_{report_type}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:  # PDF por defecto
            file_path = generate_impact_report_pdf(report_data, report_config)
            filename = f'reporte_impacto_{report_type}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
            mimetype = 'application/pdf'
        
        # Registrar exportación
        track_client_activity('impact_report_exported', {
            'report_type': report_type,
            'format': format_type,
            'period': period,
            'include_charts': include_charts,
            'include_analysis': include_analysis
        })
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exportando reporte de impacto: {str(e)}")
        flash('Error al generar el reporte de exportación.', 'error')
        return redirect(url_for('client_impact.index'))


# API Endpoints para datos dinámicos

@client_impact_bp.route('/api/metrics/<category>')
@cache_response(timeout=600)
@rate_limit('60 per minute')
def api_metrics(category):
    """API endpoint para métricas de impacto por categoría."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Validar categoría
        if category not in IMPACT_CATEGORIES:
            return jsonify({'error': 'Categoría de impacto no válida'}), 400
        
        period = request.args.get('period', 'current_month')
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener métricas según categoría
        if category == 'social':
            metrics = _get_social_impact_metrics(start_date, end_date, None, None, permissions)
        elif category == 'economic':
            if not permissions.get('can_view_financial_metrics'):
                return jsonify({'error': 'Sin permisos para métricas económicas'}), 403
            metrics = _get_economic_impact_metrics(start_date, end_date, 'USD', 'all')
        elif category == 'environmental':
            metrics = _get_environmental_impact_metrics(start_date, end_date, permissions)
        elif category == 'development':
            if not permissions.get('can_access_detailed_analytics'):
                return jsonify({'error': 'Sin permisos para métricas de desarrollo'}), 403
            metrics = _get_development_impact_metrics(start_date, end_date, 'all')
        else:
            metrics = {}
        
        return jsonify({
            'success': True,
            'category': category,
            'metrics': metrics,
            'period': period,
            'last_updated': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API métricas de impacto: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_impact_bp.route('/api/trends/<metric>')
@cache_response(timeout=1200)
def api_trends(metric):
    """API endpoint para tendencias históricas de métricas."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Verificar acceso a la métrica
        available_metrics = AVAILABLE_METRICS.get(client_type, [])
        if metric not in available_metrics:
            return jsonify({'error': 'Métrica no disponible para tu tipo de cliente'}), 403
        
        period = request.args.get('period', 'last_12_months')
        granularity = request.args.get('granularity', 'monthly')
        
        # Obtener datos de tendencia
        trend_data = _get_metric_trend_data(metric, period, granularity, permissions)
        
        return jsonify({
            'success': True,
            'metric': metric,
            'period': period,
            'granularity': granularity,
            'data': trend_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API tendencias: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_impact_bp.route('/api/comparison')
def api_comparison():
    """API endpoint para comparaciones de impacto."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        if not permissions.get('can_access_detailed_analytics'):
            return jsonify({'error': 'Sin permisos para comparaciones'}), 403
        
        comparison_type = request.args.get('type', 'temporal')
        metric = request.args.get('metric', 'jobs_created')
        period1 = request.args.get('period1', 'current_year')
        period2 = request.args.get('period2', 'previous_year')
        
        # Generar datos de comparación
        comparison_data = _get_api_comparison_data(
            comparison_type, metric, period1, period2, permissions
        )
        
        return jsonify({
            'success': True,
            'comparison_type': comparison_type,
            'metric': metric,
            'data': comparison_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API comparación: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_impact_bp.route('/api/geographic')
@cache_response(timeout=1800)
def api_geographic():
    """API endpoint para datos geográficos de impacto."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        period = request.args.get('period', 'current_year')
        metric = request.args.get('metric', 'projects_count')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener datos geográficos
        geographic_data = _get_geographic_impact_data(
            start_date, end_date, metric, permissions
        )
        
        return jsonify({
            'success': True,
            'metric': metric,
            'period': period,
            'data': geographic_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API geográfico: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _get_impact_overview(start_date, end_date, permissions):
    """Genera resumen general de impacto."""
    overview = {}
    
    # Métricas básicas para todos
    overview['jobs_created'] = (
        db.session.query(func.sum(Project.jobs_created))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    overview['direct_beneficiaries'] = (
        db.session.query(func.sum(Project.direct_beneficiaries))
        .filter(
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    overview['revenue_generated'] = (
        db.session.query(func.sum(Project.revenue_generated))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    overview['projects_completed'] = (
        Project.query
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .count()
    )
    
    # Métricas adicionales según permisos
    if permissions.get('can_access_detailed_analytics'):
        overview['training_sessions'] = _get_training_sessions_count(start_date, end_date)
        overview['mentorship_hours'] = _get_mentorship_hours_count(start_date, end_date)
        overview['communities_reached'] = _get_communities_reached_count(start_date, end_date)
    
    if permissions.get('can_view_financial_metrics'):
        overview['investment_attracted'] = _get_investment_attracted(start_date, end_date)
        overview['gdp_contribution'] = _calculate_gdp_contribution(start_date, end_date)
    
    return overview


def _get_categorized_impact(start_date, end_date, permissions):
    """Obtiene impacto organizado por categorías."""
    categorized = {}
    
    for category_key, category_info in IMPACT_CATEGORIES.items():
        categorized[category_key] = {
            'name': category_info['name'],
            'icon': category_info['icon'],
            'color': category_info['color'],
            'metrics': {}
        }
        
        # Obtener métricas según categoría y permisos
        if category_key == 'social':
            categorized[category_key]['metrics'] = _get_social_metrics_summary(
                start_date, end_date, permissions
            )
        elif category_key == 'economic' and permissions.get('can_view_financial_metrics'):
            categorized[category_key]['metrics'] = _get_economic_metrics_summary(
                start_date, end_date
            )
        elif category_key == 'environmental':
            categorized[category_key]['metrics'] = _get_environmental_metrics_summary(
                start_date, end_date
            )
        elif category_key == 'development' and permissions.get('can_access_detailed_analytics'):
            categorized[category_key]['metrics'] = _get_development_metrics_summary(
                start_date, end_date
            )
    
    return categorized


def _get_historical_trends(start_date, end_date, permissions):
    """Obtiene tendencias históricas de métricas clave."""
    # Calcular períodos históricos (últimos 12 meses)
    periods = []
    current_date = end_date
    
    for i in range(12):
        period_end = current_date.replace(day=1) - timedelta(days=1)
        period_start = period_end.replace(day=1)
        periods.append((period_start, period_end))
        current_date = period_start
    
    periods.reverse()  # Orden cronológico
    
    trends = {
        'periods': [p[1].strftime('%Y-%m') for p in periods],
        'jobs_created': [],
        'revenue_generated': [],
        'projects_completed': []
    }
    
    for period_start, period_end in periods:
        # Empleos creados en el período
        jobs = (
            db.session.query(func.sum(Project.jobs_created))
            .filter(
                Project.is_public == True,
                Project.status == 'completed',
                Project.completed_at >= period_start,
                Project.completed_at <= period_end
            )
            .scalar() or 0
        )
        trends['jobs_created'].append(int(jobs))
        
        # Ingresos generados
        revenue = (
            db.session.query(func.sum(Project.revenue_generated))
            .filter(
                Project.is_public == True,
                Project.status == 'completed',
                Project.completed_at >= period_start,
                Project.completed_at <= period_end
            )
            .scalar() or 0
        )
        trends['revenue_generated'].append(float(revenue))
        
        # Proyectos completados
        projects = (
            Project.query
            .filter(
                Project.is_public == True,
                Project.status == 'completed',
                Project.completed_at >= period_start,
                Project.completed_at <= period_end
            )
            .count()
        )
        trends['projects_completed'].append(projects)
    
    return trends


def _get_program_impact(start_date, end_date, permissions):
    """Obtiene impacto por programa."""
    program_impact = (
        db.session.query(
            Program.id,
            Program.name,
            func.count(Project.id).label('projects_count'),
            func.sum(Project.jobs_created).label('jobs_created'),
            func.sum(Project.revenue_generated).label('revenue_generated'),
            func.sum(Project.direct_beneficiaries).label('beneficiaries')
        )
        .join(Project, Project.program_id == Program.id)
        .filter(
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .group_by(Program.id, Program.name)
        .order_by(func.sum(Project.jobs_created).desc())
        .limit(10)
        .all()
    )
    
    return [
        {
            'id': p.id,
            'name': p.name,
            'projects_count': p.projects_count,
            'jobs_created': int(p.jobs_created or 0),
            'revenue_generated': float(p.revenue_generated or 0),
            'beneficiaries': int(p.beneficiaries or 0)
        }
        for p in program_impact
    ]


def _get_top_impact_entrepreneurs(start_date, end_date, permissions):
    """Obtiene emprendedores con mayor impacto."""
    top_entrepreneurs = (
        db.session.query(
            Entrepreneur.id,
            Entrepreneur.name,
            func.sum(Project.jobs_created).label('total_jobs'),
            func.sum(Project.revenue_generated).label('total_revenue'),
            func.sum(Project.direct_beneficiaries).label('total_beneficiaries'),
            func.count(Project.id).label('projects_count')
        )
        .join(Project, Project.entrepreneur_id == Entrepreneur.id)
        .filter(
            Entrepreneur.is_public == True,
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .group_by(Entrepreneur.id, Entrepreneur.name)
        .order_by(func.sum(Project.jobs_created).desc())
        .limit(10)
        .all()
    )
    
    return [
        {
            'id': e.id,
            'name': e.name,
            'total_jobs': int(e.total_jobs or 0),
            'total_revenue': float(e.total_revenue or 0),
            'total_beneficiaries': int(e.total_beneficiaries or 0),
            'projects_count': e.projects_count,
            'impact_score': _calculate_entrepreneur_impact_score(e)
        }
        for e in top_entrepreneurs
    ]


def _get_goal_comparison(start_date, end_date, permissions):
    """Compara métricas actuales con objetivos establecidos."""
    # Objetivos ejemplo (en un sistema real vendrían de la base de datos)
    goals = {
        'jobs_created': 1000,
        'revenue_generated': 5000000,
        'projects_completed': 50,
        'direct_beneficiaries': 10000
    }
    
    # Métricas actuales
    current_metrics = _get_impact_overview(start_date, end_date, permissions)
    
    # Calcular porcentajes de cumplimiento
    comparison = {}
    for metric, goal in goals.items():
        current_value = current_metrics.get(metric, 0)
        if goal > 0:
            achievement_percentage = (current_value / goal) * 100
        else:
            achievement_percentage = 0
        
        comparison[metric] = {
            'current': current_value,
            'goal': goal,
            'achievement_percentage': min(achievement_percentage, 100),
            'status': 'achieved' if achievement_percentage >= 100 else 'in_progress'
        }
    
    return comparison


def _get_geographic_impact(start_date, end_date, permissions):
    """Obtiene distribución geográfica del impacto."""
    geographic_data = (
        db.session.query(
            Entrepreneur.location,
            func.count(Project.id).label('projects_count'),
            func.sum(Project.jobs_created).label('jobs_created'),
            func.sum(Project.revenue_generated).label('revenue_generated')
        )
        .join(Project, Project.entrepreneur_id == Entrepreneur.id)
        .filter(
            Entrepreneur.is_public == True,
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date,
            Entrepreneur.location.isnot(None)
        )
        .group_by(Entrepreneur.location)
        .order_by(func.sum(Project.jobs_created).desc())
        .limit(20)
        .all()
    )
    
    return [
        {
            'location': g.location,
            'projects_count': g.projects_count,
            'jobs_created': int(g.jobs_created or 0),
            'revenue_generated': float(g.revenue_generated or 0)
        }
        for g in geographic_data
    ]


def _get_impact_filter_options(permissions):
    """Obtiene opciones disponibles para filtros."""
    options = {}
    
    # Programas activos
    programs = (
        Program.query
        .filter_by(status='active')
        .order_by(Program.name)
        .all()
    )
    options['programs'] = [{'id': p.id, 'name': p.name} for p in programs]
    
    # Organizaciones activas
    organizations = (
        Organization.query
        .filter_by(is_active=True)
        .order_by(Organization.name)
        .all()
    )
    options['organizations'] = [{'id': o.id, 'name': o.name} for o in organizations]
    
    # Ubicaciones con proyectos
    locations = (
        db.session.query(Entrepreneur.location)
        .join(Project)
        .filter(
            Entrepreneur.is_public == True,
            Project.is_public == True,
            Entrepreneur.location.isnot(None)
        )
        .distinct()
        .order_by(Entrepreneur.location)
        .all()
    )
    options['locations'] = [l[0] for l in locations]
    
    return options


def _get_social_impact_metrics(start_date, end_date, organization_id, program_id, permissions):
    """Obtiene métricas detalladas de impacto social."""
    query = (
        db.session.query(
            func.sum(Project.jobs_created).label('total_jobs'),
            func.sum(Project.direct_beneficiaries).label('total_beneficiaries'),
            func.count(Project.id).label('projects_count'),
            func.avg(Project.impact_score).label('avg_impact_score')
        )
        .filter(
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
    )
    
    if organization_id:
        query = query.filter(Project.organization_id == organization_id)
    
    if program_id:
        query = query.filter(Project.program_id == program_id)
    
    result = query.first()
    
    return {
        'total_jobs': int(result.total_jobs or 0),
        'total_beneficiaries': int(result.total_beneficiaries or 0),
        'projects_count': result.projects_count,
        'avg_impact_score': float(result.avg_impact_score or 0),
        'training_sessions': _get_training_sessions_count(start_date, end_date) if permissions.get('can_access_detailed_analytics') else 0
    }


def _get_social_metrics_summary(start_date, end_date, permissions):
    """Resumen de métricas sociales."""
    return {
        'jobs_created': _get_jobs_created_count(start_date, end_date),
        'beneficiaries': _get_beneficiaries_count(start_date, end_date),
        'communities': _get_communities_reached_count(start_date, end_date) if permissions.get('can_access_detailed_analytics') else 0
    }


def _get_economic_metrics_summary(start_date, end_date):
    """Resumen de métricas económicas."""
    return {
        'revenue_generated': _get_revenue_generated(start_date, end_date),
        'investment_attracted': _get_investment_attracted(start_date, end_date),
        'gdp_contribution': _calculate_gdp_contribution(start_date, end_date)
    }


def _get_environmental_metrics_summary(start_date, end_date):
    """Resumen de métricas ambientales."""
    return {
        'carbon_reduction': _get_carbon_reduction(start_date, end_date),
        'energy_saved': _get_energy_saved(start_date, end_date),
        'sustainability_score': _get_sustainability_score_average(start_date, end_date)
    }


def _get_development_metrics_summary(start_date, end_date):
    """Resumen de métricas de desarrollo."""
    return {
        'mentorship_hours': _get_mentorship_hours_count(start_date, end_date),
        'skills_developed': _get_skills_developed_count(start_date, end_date),
        'training_sessions': _get_training_sessions_count(start_date, end_date)
    }


# Funciones auxiliares para cálculos específicos

def _get_jobs_created_count(start_date, end_date):
    """Cuenta empleos creados en el período."""
    return (
        db.session.query(func.sum(Project.jobs_created))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )


def _get_beneficiaries_count(start_date, end_date):
    """Cuenta beneficiarios directos en el período."""
    return (
        db.session.query(func.sum(Project.direct_beneficiaries))
        .filter(
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )


def _get_revenue_generated(start_date, end_date):
    """Calcula ingresos generados en el período."""
    return (
        db.session.query(func.sum(Project.revenue_generated))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )


def _get_training_sessions_count(start_date, end_date):
    """Cuenta sesiones de capacitación."""
    # En un sistema real, esto vendría de una tabla de capacitaciones
    return (
        MentorshipSession.query
        .filter(
            MentorshipSession.session_date >= start_date,
            MentorshipSession.session_date <= end_date,
            MentorshipSession.status == 'completed'
        )
        .count()
    )


def _get_mentorship_hours_count(start_date, end_date):
    """Cuenta horas de mentoría."""
    return (
        db.session.query(func.sum(Meeting.duration_hours))
        .filter(
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date,
            Meeting.activity_type == 'mentoring'
        )
        .scalar() or 0
    )


def _get_communities_reached_count(start_date, end_date):
    """Cuenta comunidades alcanzadas."""
    # Implementar lógica específica según el modelo de datos
    return 25  # Valor de ejemplo


def _get_investment_attracted(start_date, end_date):
    """Calcula inversión atraída."""
    # Implementar según modelo de datos de inversión
    return 2500000  # Valor de ejemplo


def _calculate_gdp_contribution(start_date, end_date):
    """Calcula contribución estimada al PIB."""
    revenue = _get_revenue_generated(start_date, end_date)
    # Factor estimado de contribución al PIB
    gdp_factor = 0.15
    return float(revenue) * gdp_factor


def _calculate_entrepreneur_impact_score(entrepreneur_data):
    """Calcula puntuación de impacto de emprendedor."""
    jobs_weight = 0.4
    revenue_weight = 0.3
    beneficiaries_weight = 0.3
    
    jobs_score = min((entrepreneur_data.total_jobs or 0) / 10, 10)
    revenue_score = min((entrepreneur_data.total_revenue or 0) / 100000, 10)
    beneficiaries_score = min((entrepreneur_data.total_beneficiaries or 0) / 100, 10)
    
    impact_score = (
        jobs_score * jobs_weight +
        revenue_score * revenue_weight +
        beneficiaries_score * beneficiaries_weight
    )
    
    return round(impact_score, 2)


def _generate_impact_report_data(report_type, start_date, end_date, permissions, include_charts, include_analysis):
    """Genera datos completos para reporte de impacto."""
    report_data = {
        'overview': _get_impact_overview(start_date, end_date, permissions),
        'categorized_impact': _get_categorized_impact(start_date, end_date, permissions),
        'program_impact': _get_program_impact(start_date, end_date, permissions),
        'geographic_impact': _get_geographic_impact(start_date, end_date, permissions)
    }
    
    if include_charts:
        report_data['trends'] = _get_historical_trends(start_date, end_date, permissions)
    
    if include_analysis:
        report_data['insights'] = _generate_impact_insights(report_data, permissions)
    
    return report_data


def _generate_impact_insights(report_data, permissions):
    """Genera insights automáticos basados en los datos."""
    insights = []
    
    overview = report_data.get('overview', {})
    
    # Insight sobre empleos creados
    jobs = overview.get('jobs_created', 0)
    if jobs > 0:
        insights.append({
            'type': 'positive',
            'title': 'Generación de Empleo',
            'description': f'Se han creado {jobs:,} empleos directos, contribuyendo significativamente al desarrollo económico local.'
        })
    
    # Insight sobre beneficiarios
    beneficiaries = overview.get('direct_beneficiaries', 0)
    if beneficiaries > 0:
        insights.append({
            'type': 'positive',
            'title': 'Impacto Social',
            'description': f'{beneficiaries:,} personas han sido beneficiadas directamente por los proyectos del ecosistema.'
        })
    
    return insights


# Manejadores de errores específicos

@client_impact_bp.errorhandler(403)
def impact_forbidden(error):
    """Maneja errores de permisos en métricas de impacto."""
    flash('No tienes permisos para acceder a estas métricas de impacto.', 'error')
    return redirect(url_for('client_impact.index'))


@client_impact_bp.errorhandler(500)
def impact_internal_error(error):
    """Maneja errores internos en métricas de impacto."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en impacto: {str(error)}")
    flash('Error interno al cargar las métricas de impacto.', 'error')
    return redirect(url_for('client.index'))