"""
Vistas del dashboard principal para clientes/stakeholders.

Este módulo maneja el dashboard central donde los clientes pueden ver:
- Métricas del ecosistema de emprendimiento
- KPIs según su tipo de acceso
- Gráficos interactivos y visualizaciones
- Resúmenes de impacto y progreso
- Notificaciones y alertas personalizadas

Tipos de cliente soportados:
- Public: Métricas públicas básicas
- Stakeholder: Analytics detallados  
- Investor: Métricas financieras y ROI
- Partner: Métricas de partnership y colaboración
"""

import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from decimal import Decimal

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, session, g
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, desc, asc, extract, case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db, cache
from app.models.user import User
from app.models.client import Client
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.meeting import Meeting
from app.models.analytics import AnalyticsEvent
from app.core.exceptions import ValidationError, PermissionError
from app.utils.decorators import cache_response, log_activity, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range_for_period, get_quarter_dates
from app.utils.export_utils import generate_dashboard_report_pdf, generate_dashboard_report_excel
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService

# Importar funciones del módulo principal
from . import (
    get_client_type, get_client_permissions, require_client_permission,
    require_authenticated_client, track_client_activity, cache_key_for_client
)

# Blueprint para el dashboard de clientes
client_dashboard_bp = Blueprint(
    'client_dashboard', 
    __name__, 
    url_prefix='/dashboard'
)

# Configuraciones específicas del dashboard
DASHBOARD_CONFIG = {
    'DEFAULT_PERIOD': 'current_quarter',
    'MAX_RECENT_ITEMS': 10,
    'CACHE_TIMEOUT': 300,  # 5 minutos
    'REFRESH_INTERVAL': 60,  # 1 minuto para auto-refresh
    'MAX_WIDGETS': 12,
    'DEFAULT_WIDGETS': ['overview', 'entrepreneurs', 'projects', 'impact']
}

# Widgets disponibles según tipo de cliente
AVAILABLE_WIDGETS = {
    'public': [
        'ecosystem_overview', 'public_metrics', 'success_stories', 'recent_achievements'
    ],
    'stakeholder': [
        'ecosystem_overview', 'detailed_metrics', 'project_progress', 'impact_summary',
        'success_stories', 'recent_activities', 'goal_tracking', 'notifications'
    ],
    'investor': [
        'financial_overview', 'roi_metrics', 'portfolio_performance', 'market_analysis',
        'investment_pipeline', 'due_diligence', 'exit_opportunities', 'risk_assessment'
    ],
    'partner': [
        'partnership_metrics', 'collaboration_summary', 'shared_projects', 'impact_contribution',
        'resource_utilization', 'joint_initiatives', 'performance_comparison', 'opportunities'
    ]
}


@client_dashboard_bp.route('/')
@require_authenticated_client
@cache_response(timeout=DASHBOARD_CONFIG['CACHE_TIMEOUT'])
@log_activity('view_dashboard')
def index():
    """
    Dashboard principal para clientes.
    
    Muestra una vista personalizada según el tipo de cliente
    con métricas, gráficos y funcionalidades específicas.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener período de análisis
        period = request.args.get('period', DASHBOARD_CONFIG['DEFAULT_PERIOD'])
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener configuración de widgets del usuario
        user_widgets = _get_user_widget_config(current_user, client_type)
        
        # Generar datos del dashboard según tipo de cliente
        dashboard_data = _generate_dashboard_data(client_type, start_date, end_date, user_widgets)
        
        # Datos adicionales según permisos
        additional_data = {}
        
        if permissions.get('can_access_detailed_analytics'):
            additional_data['detailed_analytics'] = _get_detailed_analytics(start_date, end_date)
        
        if permissions.get('can_view_financial_metrics'):
            additional_data['financial_data'] = _get_financial_dashboard_data(start_date, end_date)
        
        if permissions.get('can_view_partnership_metrics'):
            additional_data['partnership_data'] = _get_partnership_dashboard_data(start_date, end_date)
        
        # Notificaciones personalizadas
        notifications = _get_client_notifications(current_user, client_type)
        
        # Configuraciones para el frontend
        frontend_config = {
            'refresh_interval': DASHBOARD_CONFIG['REFRESH_INTERVAL'],
            'available_widgets': AVAILABLE_WIDGETS.get(client_type, []),
            'client_type': client_type,
            'permissions': permissions,
            'period': period
        }
        
        return render_template(
            'client/dashboard/index.html',
            dashboard_data=dashboard_data,
            additional_data=additional_data,
            notifications=notifications,
            user_widgets=user_widgets,
            frontend_config=frontend_config,
            period=period,
            start_date=start_date,
            end_date=end_date,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard principal: {str(e)}")
        flash('Error al cargar el dashboard. Por favor, intenta nuevamente.', 'error')
        return redirect(url_for('client.index'))


@client_dashboard_bp.route('/overview')
@require_authenticated_client
@log_activity('view_overview')
def overview():
    """
    Vista de resumen general del ecosistema.
    
    Proporciona métricas de alto nivel y tendencias generales
    accesibles según el nivel de permisos del cliente.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        period = request.args.get('period', 'current_year')
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas generales del ecosistema
        overview_data = _get_ecosystem_overview(start_date, end_date, permissions)
        
        # Tendencias históricas
        historical_trends = _get_historical_trends(client_type, permissions)
        
        # Comparación con períodos anteriores
        period_comparison = _get_period_comparison(start_date, end_date, permissions)
        
        # Highlights y logros recientes
        recent_highlights = _get_recent_highlights(permissions)
        
        return render_template(
            'client/dashboard/overview.html',
            overview_data=overview_data,
            historical_trends=historical_trends,
            period_comparison=period_comparison,
            recent_highlights=recent_highlights,
            period=period,
            start_date=start_date,
            end_date=end_date,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista overview: {str(e)}")
        flash('Error al cargar el resumen general.', 'error')
        return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.route('/metrics')
@require_client_permission('can_access_detailed_analytics')
@log_activity('view_detailed_metrics')
def metrics():
    """
    Vista detallada de métricas para stakeholders autenticados.
    
    Incluye KPIs específicos, análisis de tendencias y
    métricas de desempeño del ecosistema.
    """
    try:
        client_type = get_client_type(current_user)
        
        # Parámetros de filtrado
        period = request.args.get('period', 'current_quarter')
        metric_category = request.args.get('category', 'all')
        organization_id = request.args.get('organization_id', type=int)
        program_id = request.args.get('program_id', type=int)
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener métricas detalladas
        detailed_metrics = _get_detailed_metrics(
            start_date, end_date, metric_category, organization_id, program_id
        )
        
        # KPIs calculados
        kpis = _calculate_ecosystem_kpis(start_date, end_date, organization_id, program_id)
        
        # Métricas por categoría
        categorized_metrics = _get_categorized_metrics(start_date, end_date)
        
        # Análisis de rendimiento
        performance_analysis = _get_performance_analysis(start_date, end_date)
        
        # Datos para filtros
        organizations = Organization.query.filter_by(is_active=True).order_by(Organization.name).all()
        programs = Program.query.filter_by(status='active').order_by(Program.name).all()
        
        return render_template(
            'client/dashboard/metrics.html',
            detailed_metrics=detailed_metrics,
            kpis=kpis,
            categorized_metrics=categorized_metrics,
            performance_analysis=performance_analysis,
            organizations=organizations,
            programs=programs,
            period=period,
            metric_category=metric_category,
            selected_organization_id=organization_id,
            selected_program_id=program_id,
            start_date=start_date,
            end_date=end_date,
            client_type=client_type,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de métricas: {str(e)}")
        flash('Error al cargar las métricas detalladas.', 'error')
        return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.route('/financial')
@require_client_permission('can_view_financial_metrics')
@log_activity('view_financial_dashboard')
def financial():
    """
    Dashboard financiero para inversores.
    
    Incluye métricas de ROI, análisis de inversión,
    pipeline de oportunidades y evaluación de riesgos.
    """
    try:
        period = request.args.get('period', 'current_year')
        currency = request.args.get('currency', 'USD')
        investment_focus = request.args.get('focus', 'all')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Métricas financieras principales
        financial_overview = _get_financial_overview(start_date, end_date, currency)
        
        # Análisis de ROI
        roi_analysis = _get_roi_analysis(start_date, end_date, currency)
        
        # Pipeline de inversión
        investment_pipeline = _get_investment_pipeline(investment_focus)
        
        # Análisis de portafolio
        portfolio_analysis = _get_portfolio_analysis(start_date, end_date, currency)
        
        # Oportunidades de salida
        exit_opportunities = _get_exit_opportunities()
        
        # Evaluación de riesgos
        risk_assessment = _get_risk_assessment(start_date, end_date)
        
        # Análisis de mercado
        market_analysis = _get_market_analysis(start_date, end_date)
        
        return render_template(
            'client/dashboard/financial.html',
            financial_overview=financial_overview,
            roi_analysis=roi_analysis,
            investment_pipeline=investment_pipeline,
            portfolio_analysis=portfolio_analysis,
            exit_opportunities=exit_opportunities,
            risk_assessment=risk_assessment,
            market_analysis=market_analysis,
            period=period,
            currency=currency,
            investment_focus=investment_focus,
            start_date=start_date,
            end_date=end_date,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard financiero: {str(e)}")
        flash('Error al cargar el dashboard financiero.', 'error')
        return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.route('/partnerships')
@require_client_permission('can_view_partnership_metrics')
@log_activity('view_partnership_dashboard')
def partnerships():
    """
    Dashboard de partnerships para socios.
    
    Métricas de colaboración, proyectos conjuntos,
    utilización de recursos y oportunidades.
    """
    try:
        period = request.args.get('period', 'current_quarter')
        partnership_type = request.args.get('type', 'all')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Resumen de partnerships
        partnership_summary = _get_partnership_summary(start_date, end_date, partnership_type)
        
        # Proyectos colaborativos
        collaborative_projects = _get_collaborative_projects(start_date, end_date)
        
        # Contribución al impacto
        impact_contribution = _get_partnership_impact_contribution(start_date, end_date)
        
        # Utilización de recursos
        resource_utilization = _get_resource_utilization(start_date, end_date)
        
        # Iniciativas conjuntas
        joint_initiatives = _get_joint_initiatives(start_date, end_date)
        
        # Comparación de rendimiento
        performance_comparison = _get_partnership_performance_comparison(start_date, end_date)
        
        # Nuevas oportunidades
        new_opportunities = _get_partnership_opportunities()
        
        return render_template(
            'client/dashboard/partnerships.html',
            partnership_summary=partnership_summary,
            collaborative_projects=collaborative_projects,
            impact_contribution=impact_contribution,
            resource_utilization=resource_utilization,
            joint_initiatives=joint_initiatives,
            performance_comparison=performance_comparison,
            new_opportunities=new_opportunities,
            period=period,
            partnership_type=partnership_type,
            start_date=start_date,
            end_date=end_date,
            format_currency=format_currency,
            format_percentage=format_percentage,
            format_number=format_number
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de partnerships: {str(e)}")
        flash('Error al cargar el dashboard de partnerships.', 'error')
        return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.route('/customize')
@require_authenticated_client
@log_activity('customize_dashboard')
def customize():
    """
    Página de personalización del dashboard.
    
    Permite a los usuarios configurar widgets, layout
    y preferencias de visualización.
    """
    try:
        client_type = get_client_type(current_user)
        available_widgets = AVAILABLE_WIDGETS.get(client_type, [])
        current_config = _get_user_widget_config(current_user, client_type)
        
        # Información de widgets disponibles
        widget_info = _get_widget_information(available_widgets)
        
        return render_template(
            'client/dashboard/customize.html',
            available_widgets=available_widgets,
            current_config=current_config,
            widget_info=widget_info,
            client_type=client_type,
            max_widgets=DASHBOARD_CONFIG['MAX_WIDGETS']
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en personalización: {str(e)}")
        flash('Error al cargar la personalización.', 'error')
        return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.route('/customize', methods=['POST'])
@require_authenticated_client
@log_activity('save_dashboard_config')
def save_customization():
    """
    Guarda la configuración personalizada del dashboard.
    
    Procesa y valida la configuración de widgets y layout
    seleccionada por el usuario.
    """
    try:
        client_type = get_client_type(current_user)
        
        # Obtener configuración del formulario
        widget_config = request.form.getlist('widgets')
        layout_config = request.form.get('layout', 'grid')
        refresh_interval = request.form.get('refresh_interval', type=int) or 60
        
        # Validar widgets seleccionados
        available_widgets = AVAILABLE_WIDGETS.get(client_type, [])
        valid_widgets = [w for w in widget_config if w in available_widgets]
        
        if len(valid_widgets) > DASHBOARD_CONFIG['MAX_WIDGETS']:
            flash(f'Máximo {DASHBOARD_CONFIG["MAX_WIDGETS"]} widgets permitidos.', 'error')
            return redirect(url_for('client_dashboard.customize'))
        
        # Validar intervalo de actualización
        if refresh_interval < 30 or refresh_interval > 600:
            refresh_interval = 60
        
        # Guardar configuración
        config_data = {
            'widgets': valid_widgets,
            'layout': layout_config,
            'refresh_interval': refresh_interval,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        _save_user_widget_config(current_user, config_data)
        
        # Limpiar cache del usuario
        cache_key = cache_key_for_client(f'dashboard_config_{current_user.id}')
        cache.delete(cache_key)
        
        flash('Configuración del dashboard guardada exitosamente.', 'success')
        return redirect(url_for('client_dashboard.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error guardando personalización: {str(e)}")
        flash('Error al guardar la configuración.', 'error')
        return redirect(url_for('client_dashboard.customize'))


@client_dashboard_bp.route('/export')
@require_client_permission('can_export_basic_reports')
@log_activity('export_dashboard')
def export():
    """
    Exporta el dashboard en formato PDF o Excel.
    
    Genera un reporte completo con las métricas y gráficos
    visibles según los permisos del cliente.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de exportación
        format_type = request.args.get('format', 'pdf')
        period = request.args.get('period', 'current_quarter')
        include_charts = request.args.get('include_charts', 'true') == 'true'
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Generar datos completos para exportación
        export_data = {
            'client_type': client_type,
            'permissions': permissions,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'include_charts': include_charts,
            'generated_at': datetime.now(timezone.utc),
            'generated_by': current_user.name if current_user.is_authenticated else 'Cliente',
            'dashboard_data': _generate_dashboard_data(client_type, start_date, end_date)
        }
        
        if permissions.get('can_access_detailed_analytics'):
            export_data['detailed_analytics'] = _get_detailed_analytics(start_date, end_date)
        
        if permissions.get('can_view_financial_metrics'):
            export_data['financial_data'] = _get_financial_dashboard_data(start_date, end_date)
        
        # Generar archivo según formato
        if format_type == 'excel':
            file_path = generate_dashboard_report_excel(export_data)
            filename = f'dashboard_reporte_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:  # PDF por defecto
            file_path = generate_dashboard_report_pdf(export_data)
            filename = f'dashboard_reporte_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.pdf'
            mimetype = 'application/pdf'
        
        from flask import send_file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exportando dashboard: {str(e)}")
        flash('Error al generar la exportación.', 'error')
        return redirect(url_for('client_dashboard.index'))


# API Endpoints para funcionalidades AJAX

@client_dashboard_bp.route('/api/widget-data/<widget_name>')
@require_authenticated_client
@rate_limit('60 per minute')
def api_widget_data(widget_name):
    """API endpoint para obtener datos de un widget específico."""
    try:
        client_type = get_client_type(current_user)
        available_widgets = AVAILABLE_WIDGETS.get(client_type, [])
        
        if widget_name not in available_widgets:
            return jsonify({'error': 'Widget no disponible'}), 403
        
        period = request.args.get('period', 'current_month')
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener datos específicos del widget
        widget_data = _get_widget_data(widget_name, start_date, end_date, client_type)
        
        return jsonify({
            'success': True,
            'widget': widget_name,
            'data': widget_data,
            'period': period,
            'last_updated': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API widget data: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_dashboard_bp.route('/api/metrics-summary')
@require_authenticated_client
def api_metrics_summary():
    """API endpoint para resumen rápido de métricas."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        period = request.args.get('period', 'current_month')
        start_date, end_date = get_date_range_for_period(period)
        
        summary = {}
        
        # Métricas básicas para todos
        if permissions.get('can_view_public_metrics'):
            summary['public'] = _get_public_metrics_summary(start_date, end_date)
        
        # Métricas detalladas para stakeholders
        if permissions.get('can_access_detailed_analytics'):
            summary['detailed'] = _get_detailed_metrics_summary(start_date, end_date)
        
        # Métricas financieras para inversores
        if permissions.get('can_view_financial_metrics'):
            summary['financial'] = _get_financial_metrics_summary(start_date, end_date)
        
        return jsonify({
            'success': True,
            'summary': summary,
            'period': period,
            'client_type': client_type
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API metrics summary: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_dashboard_bp.route('/api/notifications')
@require_authenticated_client
def api_notifications():
    """API endpoint para obtener notificaciones del cliente."""
    try:
        client_type = get_client_type(current_user)
        notifications = _get_client_notifications(current_user, client_type)
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'count': len(notifications)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API notifications: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_dashboard_bp.route('/api/chart-data/<chart_type>')
@require_authenticated_client
@cache_response(timeout=300)
def api_chart_data(chart_type):
    """API endpoint para datos de gráficos específicos."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        period = request.args.get('period', 'current_quarter')
        start_date, end_date = get_date_range_for_period(period)
        
        # Verificar permisos para el tipo de gráfico
        if not _has_chart_permission(chart_type, permissions):
            return jsonify({'error': 'Sin permisos para este gráfico'}), 403
        
        chart_data = _get_chart_data(chart_type, start_date, end_date, client_type)
        
        return jsonify({
            'success': True,
            'chart_type': chart_type,
            'data': chart_data,
            'period': period
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API chart data: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _generate_dashboard_data(client_type, start_date, end_date, widgets=None):
    """Genera datos completos del dashboard según tipo de cliente."""
    dashboard_data = {}
    
    # Métricas básicas para todos los tipos
    dashboard_data['overview'] = _get_basic_overview(start_date, end_date)
    
    # Datos específicos según tipo de cliente
    if client_type in ['stakeholder', 'investor', 'partner']:
        dashboard_data['entrepreneurs'] = _get_entrepreneurs_summary(start_date, end_date)
        dashboard_data['projects'] = _get_projects_summary(start_date, end_date)
        dashboard_data['impact'] = _get_impact_summary(start_date, end_date)
    
    if client_type == 'investor':
        dashboard_data['financial'] = _get_financial_summary(start_date, end_date)
        dashboard_data['roi'] = _get_roi_summary(start_date, end_date)
    
    if client_type == 'partner':
        dashboard_data['partnerships'] = _get_partnerships_summary(start_date, end_date)
        dashboard_data['collaboration'] = _get_collaboration_summary(start_date, end_date)
    
    return dashboard_data


def _get_basic_overview(start_date, end_date):
    """Obtiene métricas básicas del ecosistema."""
    total_entrepreneurs = Entrepreneur.query.filter_by(is_public=True).count()
    
    active_projects = (
        Project.query
        .filter(
            Project.status == 'active',
            Project.is_public == True
        )
        .count()
    )
    
    completed_projects_period = (
        Project.query
        .filter(
            Project.status == 'completed',
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .count()
    )
    
    success_rate = 0
    if total_entrepreneurs > 0:
        successful_entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(
                Project.status == 'completed',
                Project.is_public == True
            )
            .distinct()
            .count()
        )
        success_rate = (successful_entrepreneurs / total_entrepreneurs) * 100
    
    return {
        'total_entrepreneurs': total_entrepreneurs,
        'active_projects': active_projects,
        'completed_projects': completed_projects_period,
        'success_rate': round(success_rate, 1)
    }


def _get_entrepreneurs_summary(start_date, end_date):
    """Obtiene resumen de emprendedores."""
    # Emprendedores activos en el período
    active_entrepreneurs = (
        db.session.query(func.count(func.distinct(Project.entrepreneur_id)))
        .filter(
            Project.status.in_(['active', 'in_progress']),
            Project.created_at >= start_date,
            Project.created_at <= end_date
        )
        .scalar() or 0
    )
    
    # Distribución por género
    gender_distribution = (
        db.session.query(
            Entrepreneur.gender,
            func.count(Entrepreneur.id)
        )
        .filter(
            Entrepreneur.is_public == True,
            Entrepreneur.created_at >= start_date,
            Entrepreneur.created_at <= end_date
        )
        .group_by(Entrepreneur.gender)
        .all()
    )
    
    # Distribución por industria
    industry_distribution = (
        db.session.query(
            Project.industry,
            func.count(Project.id)
        )
        .filter(
            Project.is_public == True,
            Project.created_at >= start_date,
            Project.created_at <= end_date
        )
        .group_by(Project.industry)
        .order_by(func.count(Project.id).desc())
        .limit(10)
        .all()
    )
    
    return {
        'active_count': active_entrepreneurs,
        'gender_distribution': [
            {'gender': g[0], 'count': g[1]} for g in gender_distribution
        ],
        'industry_distribution': [
            {'industry': i[0], 'count': i[1]} for i in industry_distribution
        ]
    }


def _get_projects_summary(start_date, end_date):
    """Obtiene resumen de proyectos."""
    # Proyectos por estado
    project_status = (
        db.session.query(
            Project.status,
            func.count(Project.id)
        )
        .filter(
            Project.is_public == True,
            Project.created_at >= start_date,
            Project.created_at <= end_date
        )
        .group_by(Project.status)
        .all()
    )
    
    # Progreso promedio
    avg_progress = (
        db.session.query(func.avg(Project.progress_percentage))
        .filter(
            Project.is_public == True,
            Project.status.in_(['active', 'in_progress'])
        )
        .scalar() or 0
    )
    
    # Proyectos más exitosos
    top_projects = (
        Project.query
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .order_by(Project.impact_score.desc())
        .limit(5)
        .all()
    )
    
    return {
        'status_distribution': [
            {'status': s[0], 'count': s[1]} for s in project_status
        ],
        'average_progress': round(float(avg_progress), 1),
        'top_projects': [
            {
                'id': p.id,
                'name': p.name,
                'impact_score': p.impact_score,
                'entrepreneur': p.entrepreneur.name if p.entrepreneur else 'N/A'
            }
            for p in top_projects
        ]
    }


def _get_impact_summary(start_date, end_date):
    """Obtiene resumen de impacto del ecosistema."""
    # Empleos generados
    jobs_created = (
        db.session.query(func.sum(Project.jobs_created))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    # Ingresos generados
    revenue_generated = (
        db.session.query(func.sum(Project.revenue_generated))
        .filter(
            Project.is_public == True,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    # Beneficiarios directos
    direct_beneficiaries = (
        db.session.query(func.sum(Project.direct_beneficiaries))
        .filter(
            Project.is_public == True,
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .scalar() or 0
    )
    
    return {
        'jobs_created': int(jobs_created),
        'revenue_generated': float(revenue_generated),
        'direct_beneficiaries': int(direct_beneficiaries),
        'social_impact_score': _calculate_social_impact_score(start_date, end_date)
    }


def _get_user_widget_config(user, client_type):
    """Obtiene configuración de widgets del usuario."""
    if not user.is_authenticated:
        return DASHBOARD_CONFIG['DEFAULT_WIDGETS']
    
    cache_key = cache_key_for_client(f'dashboard_config_{user.id}')
    config = cache.get(cache_key)
    
    if not config:
        # Buscar en base de datos o usar configuración por defecto
        if hasattr(user, 'client') and user.client and user.client.dashboard_config:
            try:
                config = json.loads(user.client.dashboard_config)
            except:
                config = None
        
        if not config:
            config = {
                'widgets': AVAILABLE_WIDGETS.get(client_type, [])[:4],
                'layout': 'grid',
                'refresh_interval': 60
            }
        
        cache.set(cache_key, config, timeout=3600)
    
    return config


def _save_user_widget_config(user, config_data):
    """Guarda configuración de widgets del usuario."""
    try:
        # Guardar en base de datos si el usuario tiene perfil de cliente
        if hasattr(user, 'client') and user.client:
            user.client.dashboard_config = json.dumps(config_data)
            db.session.commit()
        
        # Actualizar cache
        cache_key = cache_key_for_client(f'dashboard_config_{user.id}')
        cache.set(cache_key, config_data, timeout=3600)
        
    except Exception as e:
        current_app.logger.error(f"Error guardando config de dashboard: {str(e)}")
        db.session.rollback()


def _get_client_notifications(user, client_type):
    """Obtiene notificaciones personalizadas para el cliente."""
    notifications = []
    
    try:
        # Notificaciones del sistema
        if user.is_authenticated:
            system_notifications = NotificationService.get_client_notifications(
                user.id, client_type
            )
            notifications.extend(system_notifications)
        
        # Notificaciones basadas en actividad reciente
        recent_activity_notifications = _get_activity_based_notifications(client_type)
        notifications.extend(recent_activity_notifications)
        
        # Ordenar por prioridad y fecha
        notifications.sort(key=lambda x: (x.get('priority', 0), x.get('created_at', datetime.min)), reverse=True)
        
        return notifications[:10]  # Limitar a 10 notificaciones
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo notificaciones: {str(e)}")
        return []


def _get_detailed_analytics(start_date, end_date):
    """Obtiene analytics detallados para stakeholders."""
    return AnalyticsService.get_stakeholder_analytics(start_date, end_date)


def _get_financial_dashboard_data(start_date, end_date):
    """Obtiene datos financieros para el dashboard."""
    return AnalyticsService.get_financial_dashboard_data(start_date, end_date)


def _get_partnership_dashboard_data(start_date, end_date):
    """Obtiene datos de partnerships para el dashboard."""
    return AnalyticsService.get_partnership_dashboard_data(start_date, end_date)


def _has_chart_permission(chart_type, permissions):
    """Verifica si el cliente tiene permisos para un tipo de gráfico."""
    chart_permissions = {
        'financial_trends': 'can_view_financial_metrics',
        'investment_pipeline': 'can_view_financial_metrics',
        'partnership_metrics': 'can_view_partnership_metrics',
        'detailed_analytics': 'can_access_detailed_analytics'
    }
    
    required_permission = chart_permissions.get(chart_type)
    if not required_permission:
        return True  # Gráficos públicos
    
    return permissions.get(required_permission, False)


def _get_widget_data(widget_name, start_date, end_date, client_type):
    """Obtiene datos específicos para un widget."""
    widget_handlers = {
        'ecosystem_overview': lambda: _get_basic_overview(start_date, end_date),
        'entrepreneurs': lambda: _get_entrepreneurs_summary(start_date, end_date),
        'projects': lambda: _get_projects_summary(start_date, end_date),
        'impact': lambda: _get_impact_summary(start_date, end_date),
        'financial_overview': lambda: _get_financial_summary(start_date, end_date),
        'partnerships': lambda: _get_partnerships_summary(start_date, end_date)
    }
    
    handler = widget_handlers.get(widget_name)
    if handler:
        return handler()
    
    return {}


def _calculate_social_impact_score(start_date, end_date):
    """Calcula puntuación de impacto social."""
    # Implementar lógica de cálculo de impacto social
    # Por ahora retornar un valor de ejemplo
    return 85.3


# Manejadores de errores específicos

@client_dashboard_bp.errorhandler(403)
def dashboard_forbidden(error):
    """Maneja errores de permisos en el dashboard."""
    flash('No tienes permisos para acceder a esta funcionalidad del dashboard.', 'error')
    return redirect(url_for('client_dashboard.index'))


@client_dashboard_bp.errorhandler(500)
def dashboard_internal_error(error):
    """Maneja errores internos en el dashboard."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en dashboard: {str(error)}")
    flash('Error interno en el dashboard. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('client.index'))