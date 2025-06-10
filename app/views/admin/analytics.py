"""
Analytics Empresariales - Panel Administrativo
==============================================

Este módulo proporciona analytics avanzados y business intelligence para todo
el ecosistema de emprendimiento, incluyendo KPIs, tendencias, predicciones
y insights accionables para la toma de decisiones estratégicas.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
import json
import pandas as pd
import numpy as np
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, case, cast, Float, text, extract
from sqlalchemy.orm import joinedload, selectinload, contains_eager

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required
from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.constants import (
    USER_ROLES, BUSINESS_STAGES, ORGANIZATION_TYPES, PROGRAM_TYPES,
    PARTNERSHIP_TYPES, INVESTMENT_TYPES, PRIORITY_LEVELS
)

# Importaciones de modelos
from app.models import (
    User, Entrepreneur, Ally, Client, Admin, Organization, Program,
    Project, Mentorship, Meeting, Partnership, Investment, Document,
    ActivityLog, Analytics, Notification, Cohort
)

# Importaciones de servicios
from app.services.analytics_service import AnalyticsService
from app.services.prediction_service import PredictionService
from app.services.benchmark_service import BenchmarkService
from app.services.report_service import ReportService

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range, format_date_range, get_quarters
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.analytics_utils import (
    calculate_cohort_analysis, calculate_funnel_metrics, 
    calculate_retention_rates, calculate_lifetime_value
)

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_analytics = Blueprint('admin_analytics', __name__, url_prefix='/admin/analytics')

# ============================================================================
# DASHBOARD PRINCIPAL DE ANALYTICS
# ============================================================================

@admin_analytics.route('/')
@admin_analytics.route('/dashboard')
@login_required
@admin_required
@handle_exceptions
@cache_result(timeout=300)  # Cache 5 minutos
def dashboard():
    """
    Dashboard principal de analytics con KPIs clave y métricas en tiempo real.
    Proporciona una vista ejecutiva del ecosistema completo.
    """
    try:
        # Parámetros de tiempo
        date_range = request.args.get('date_range', '30d')
        start_date, end_date = get_date_range(date_range)
        compare_period = request.args.get('compare', 'previous_period')
        
        analytics_service = AnalyticsService()
        
        # KPIs Principales del Ecosistema
        ecosystem_kpis = _get_ecosystem_kpis(start_date, end_date)
        
        # Métricas de Crecimiento
        growth_metrics = _get_growth_metrics(start_date, end_date)
        
        # Performance del Ecosistema
        ecosystem_performance = _get_ecosystem_performance()
        
        # Métricas Financieras
        financial_metrics = _get_financial_overview(start_date, end_date)
        
        # Health Score del Ecosistema
        ecosystem_health = _calculate_ecosystem_health_score()
        
        # Datos para gráficos principales
        charts_data = {
            'ecosystem_growth': analytics_service.get_ecosystem_growth_trend(start_date, end_date),
            'user_acquisition': analytics_service.get_user_acquisition_funnel(start_date, end_date),
            'success_pipeline': analytics_service.get_success_pipeline_data(),
            'revenue_trends': analytics_service.get_revenue_trends(start_date, end_date),
            'geographic_distribution': analytics_service.get_geographic_heatmap(),
            'engagement_matrix': analytics_service.get_engagement_matrix(),
            'prediction_chart': analytics_service.get_growth_predictions(days=90)
        }
        
        # Alertas y Insights Automáticos
        automated_insights = _generate_automated_insights(ecosystem_kpis, growth_metrics)
        
        # Comparación con período anterior
        comparison_data = _get_comparison_data(start_date, end_date, compare_period)
        
        # Top Performers y Attention Items
        top_performers = _get_top_performers_summary()
        attention_items = _get_attention_items_summary()
        
        # Métricas en Tiempo Real
        realtime_metrics = _get_realtime_metrics()
        
        return render_template(
            'admin/analytics/dashboard.html',
            ecosystem_kpis=ecosystem_kpis,
            growth_metrics=growth_metrics,
            ecosystem_performance=ecosystem_performance,
            financial_metrics=financial_metrics,
            ecosystem_health=ecosystem_health,
            charts_data=charts_data,
            automated_insights=automated_insights,
            comparison_data=comparison_data,
            top_performers=top_performers,
            attention_items=attention_items,
            realtime_metrics=realtime_metrics,
            date_range=date_range,
            date_range_formatted=format_date_range(start_date, end_date)
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de analytics: {str(e)}")
        flash('Error al cargar el dashboard de analytics.', 'error')
        return redirect(url_for('admin_dashboard.index'))

# ============================================================================
# ANALYTICS POR MÓDULOS
# ============================================================================

@admin_analytics.route('/users')
@login_required
@admin_required
@handle_exceptions
def users_analytics():
    """
    Analytics detallados de usuarios: adquisición, retención, engagement.
    """
    try:
        date_range = request.args.get('date_range', '90d')
        start_date, end_date = get_date_range(date_range)
        
        analytics_service = AnalyticsService()
        
        # Métricas de Usuarios
        user_metrics = {
            'total_users': User.query.filter_by(is_active=True).count(),
            'new_users': User.query.filter(
                and_(User.created_at >= start_date, User.created_at <= end_date)
            ).count(),
            'monthly_active_users': _calculate_monthly_active_users(),
            'user_retention_rate': _calculate_user_retention_rate(),
            'avg_session_duration': _calculate_avg_session_duration(),
            'user_lifetime_value': calculate_lifetime_value('user')
        }
        
        # Análisis de Cohortes de Usuarios
        cohort_analysis = calculate_cohort_analysis('user', start_date, end_date)
        
        # Funnel de Adquisición
        acquisition_funnel = calculate_funnel_metrics('user_acquisition')
        
        # Segmentación de Usuarios
        user_segmentation = {
            'by_role': _get_user_segmentation_by_role(),
            'by_activity': _get_user_segmentation_by_activity(),
            'by_geography': _get_user_segmentation_by_geography(),
            'by_engagement': _get_user_segmentation_by_engagement()
        }
        
        # Análisis de Churn
        churn_analysis = _get_user_churn_analysis(start_date, end_date)
        
        # Predicciones de Usuarios
        prediction_service = PredictionService()
        user_predictions = prediction_service.predict_user_growth(days=90)
        
        # Gráficos específicos de usuarios
        user_charts = {
            'growth_trend': analytics_service.get_user_growth_trend(start_date, end_date),
            'role_distribution': analytics_service.get_role_distribution_over_time(start_date, end_date),
            'engagement_heatmap': analytics_service.get_user_engagement_heatmap(),
            'retention_curves': analytics_service.get_retention_curves(),
            'churn_prediction': analytics_service.get_churn_prediction_data()
        }
        
        return render_template(
            'admin/analytics/users.html',
            user_metrics=user_metrics,
            cohort_analysis=cohort_analysis,
            acquisition_funnel=acquisition_funnel,
            user_segmentation=user_segmentation,
            churn_analysis=churn_analysis,
            user_predictions=user_predictions,
            user_charts=user_charts,
            date_range=date_range
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics de usuarios: {str(e)}")
        flash('Error al cargar analytics de usuarios.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

@admin_analytics.route('/entrepreneurs')
@login_required
@admin_required
@handle_exceptions
def entrepreneurs_analytics():
    """
    Analytics específicos de emprendedores: success pipeline, outcomes, ROI.
    """
    try:
        date_range = request.args.get('date_range', '90d')
        start_date, end_date = get_date_range(date_range)
        
        analytics_service = AnalyticsService()
        
        # Success Pipeline
        success_pipeline = {
            'total_entrepreneurs': Entrepreneur.query.join(User).filter(User.is_active == True).count(),
            'idea_stage': Entrepreneur.query.filter_by(business_stage='idea').count(),
            'mvp_stage': Entrepreneur.query.filter_by(business_stage='mvp').count(),
            'growth_stage': Entrepreneur.query.filter_by(business_stage='growth').count(),
            'scale_stage': Entrepreneur.query.filter_by(business_stage='scale').count(),
            'success_rate': _calculate_entrepreneur_success_rate(),
            'graduation_rate': _calculate_entrepreneur_graduation_rate()
        }
        
        # Análisis de Outcomes
        outcomes_analysis = {
            'funded_startups': _count_funded_startups(),
            'total_funding_raised': _calculate_total_funding_raised(),
            'jobs_created': _estimate_jobs_created(),
            'revenue_generated': _estimate_revenue_generated(),
            'exits': _count_successful_exits(),
            'avg_time_to_funding': _calculate_avg_time_to_funding()
        }
        
        # ROI del Ecosistema
        ecosystem_roi = {
            'total_investment': _calculate_total_ecosystem_investment(),
            'current_valuation': _calculate_current_portfolio_valuation(),
            'roi_percentage': _calculate_ecosystem_roi_percentage(),
            'irr': _calculate_internal_rate_of_return()
        }
        
        # Análisis por Industria
        industry_analysis = analytics_service.get_entrepreneur_performance_by_industry()
        
        # Análisis de Mentorías
        mentorship_impact = _analyze_mentorship_impact()
        
        # Predictive Analytics
        prediction_service = PredictionService()
        entrepreneur_predictions = {
            'success_probability': prediction_service.predict_entrepreneur_success(),
            'funding_likelihood': prediction_service.predict_funding_likelihood(),
            'time_to_success': prediction_service.predict_time_to_success()
        }
        
        # Gráficos específicos
        entrepreneur_charts = {
            'success_pipeline': analytics_service.get_success_pipeline_visualization(),
            'funding_timeline': analytics_service.get_funding_timeline(),
            'industry_performance': analytics_service.get_industry_performance_matrix(),
            'mentor_impact': analytics_service.get_mentor_impact_analysis(),
            'geographic_success': analytics_service.get_geographic_success_map()
        }
        
        return render_template(
            'admin/analytics/entrepreneurs.html',
            success_pipeline=success_pipeline,
            outcomes_analysis=outcomes_analysis,
            ecosystem_roi=ecosystem_roi,
            industry_analysis=industry_analysis,
            mentorship_impact=mentorship_impact,
            entrepreneur_predictions=entrepreneur_predictions,
            entrepreneur_charts=entrepreneur_charts,
            date_range=date_range
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics de emprendedores: {str(e)}")
        flash('Error al cargar analytics de emprendedores.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

@admin_analytics.route('/programs')
@login_required
@admin_required
@handle_exceptions
def programs_analytics():
    """
    Analytics de programas: efectividad, ROI, outcomes, comparativas.
    """
    try:
        date_range = request.args.get('date_range', '365d')
        start_date, end_date = get_date_range(date_range)
        
        analytics_service = AnalyticsService()
        
        # Performance de Programas
        program_performance = {
            'total_programs': Program.query.count(),
            'active_programs': Program.query.filter_by(status='active').count(),
            'avg_completion_rate': _calculate_avg_program_completion_rate(),
            'avg_success_rate': _calculate_avg_program_success_rate(),
            'total_participants': _count_total_program_participants(),
            'total_graduates': _count_total_program_graduates()
        }
        
        # ROI por Tipo de Programa
        program_roi_analysis = _analyze_program_roi_by_type()
        
        # Efectividad Comparativa
        program_effectiveness = {
            'by_type': analytics_service.get_program_effectiveness_by_type(),
            'by_organization': analytics_service.get_program_effectiveness_by_organization(),
            'by_duration': analytics_service.get_program_effectiveness_by_duration(),
            'by_cohort_size': analytics_service.get_program_effectiveness_by_cohort_size()
        }
        
        # Análisis de Cohortes de Programas
        program_cohort_analysis = _analyze_program_cohorts()
        
        # Benchmarking con Industria
        benchmark_service = BenchmarkService()
        industry_benchmarks = benchmark_service.get_program_industry_benchmarks()
        
        # Predictive Analytics para Programas
        prediction_service = PredictionService()
        program_predictions = {
            'optimal_cohort_size': prediction_service.predict_optimal_cohort_size(),
            'success_factors': prediction_service.identify_program_success_factors(),
            'recommended_improvements': prediction_service.recommend_program_improvements()
        }
        
        # Gráficos específicos de programas
        program_charts = {
            'effectiveness_matrix': analytics_service.get_program_effectiveness_matrix(),
            'roi_comparison': analytics_service.get_program_roi_comparison(),
            'participant_journey': analytics_service.get_participant_journey_map(),
            'outcome_correlation': analytics_service.get_outcome_correlation_analysis(),
            'benchmark_comparison': analytics_service.get_benchmark_comparison_chart()
        }
        
        return render_template(
            'admin/analytics/programs.html',
            program_performance=program_performance,
            program_roi_analysis=program_roi_analysis,
            program_effectiveness=program_effectiveness,
            program_cohort_analysis=program_cohort_analysis,
            industry_benchmarks=industry_benchmarks,
            program_predictions=program_predictions,
            program_charts=program_charts,
            date_range=date_range
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics de programas: {str(e)}")
        flash('Error al cargar analytics de programas.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

@admin_analytics.route('/financial')
@login_required
@admin_required
@handle_exceptions
def financial_analytics():
    """
    Analytics financieros: inversiones, revenue, costs, ROI, projections.
    """
    try:
        date_range = request.args.get('date_range', '365d')
        start_date, end_date = get_date_range(date_range)
        
        analytics_service = AnalyticsService()
        
        # Revenue Overview
        revenue_overview = {
            'total_revenue': _calculate_total_revenue(start_date, end_date),
            'recurring_revenue': _calculate_recurring_revenue(),
            'program_revenue': _calculate_program_revenue(start_date, end_date),
            'partnership_revenue': _calculate_partnership_revenue(start_date, end_date),
            'revenue_growth_rate': _calculate_revenue_growth_rate(),
            'average_revenue_per_user': _calculate_arpu()
        }
        
        # Investment Analysis
        investment_analysis = {
            'total_investments': _calculate_total_investments(),
            'active_investments': _calculate_active_investments(),
            'portfolio_valuation': _calculate_portfolio_valuation(),
            'realized_returns': _calculate_realized_returns(),
            'unrealized_gains': _calculate_unrealized_gains(),
            'investment_roi': _calculate_investment_roi()
        }
        
        # Cost Analysis
        cost_analysis = {
            'operational_costs': _calculate_operational_costs(start_date, end_date),
            'program_costs': _calculate_program_costs(start_date, end_date),
            'marketing_costs': _calculate_marketing_costs(start_date, end_date),
            'cost_per_acquisition': _calculate_cost_per_acquisition(),
            'cost_efficiency_ratio': _calculate_cost_efficiency_ratio()
        }
        
        # Profitability Analysis
        profitability = {
            'gross_profit': revenue_overview['total_revenue'] - cost_analysis['operational_costs'],
            'net_profit_margin': _calculate_net_profit_margin(),
            'ebitda': _calculate_ebitda(),
            'break_even_analysis': _calculate_break_even_point(),
            'cash_flow': _calculate_cash_flow_analysis(start_date, end_date)
        }
        
        # Financial Projections
        prediction_service = PredictionService()
        financial_projections = {
            'revenue_forecast': prediction_service.forecast_revenue(months=12),
            'investment_forecast': prediction_service.forecast_investments(months=12),
            'profitability_forecast': prediction_service.forecast_profitability(months=12),
            'cash_flow_projection': prediction_service.project_cash_flow(months=12)
        }
        
        # Financial Health Indicators
        financial_health = {
            'liquidity_ratio': _calculate_liquidity_ratio(),
            'burn_rate': _calculate_burn_rate(),
            'runway_months': _calculate_runway_months(),
            'financial_efficiency_score': _calculate_financial_efficiency_score()
        }
        
        # Gráficos financieros
        financial_charts = {
            'revenue_trends': analytics_service.get_revenue_trend_analysis(start_date, end_date),
            'investment_portfolio': analytics_service.get_investment_portfolio_breakdown(),
            'cost_breakdown': analytics_service.get_cost_breakdown_analysis(),
            'profitability_trends': analytics_service.get_profitability_trends(),
            'cash_flow_projection': analytics_service.get_cash_flow_projection_chart(),
            'roi_analysis': analytics_service.get_roi_analysis_chart()
        }
        
        return render_template(
            'admin/analytics/financial.html',
            revenue_overview=revenue_overview,
            investment_analysis=investment_analysis,
            cost_analysis=cost_analysis,
            profitability=profitability,
            financial_projections=financial_projections,
            financial_health=financial_health,
            financial_charts=financial_charts,
            date_range=date_range
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics financieros: {str(e)}")
        flash('Error al cargar analytics financieros.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

# ============================================================================
# PREDICTIVE ANALYTICS
# ============================================================================

@admin_analytics.route('/predictions')
@login_required
@admin_required
@permission_required('view_predictions')
@handle_exceptions
def predictive_analytics():
    """
    Analytics predictivos: tendencias futuras, alertas tempranas, recomendaciones.
    """
    try:
        prediction_horizon = request.args.get('horizon', '90d')
        confidence_level = float(request.args.get('confidence', '0.95'))
        
        prediction_service = PredictionService()
        
        # Predicciones de Crecimiento
        growth_predictions = {
            'user_growth': prediction_service.predict_user_growth(prediction_horizon),
            'revenue_growth': prediction_service.predict_revenue_growth(prediction_horizon),
            'entrepreneur_success': prediction_service.predict_entrepreneur_success_rate(prediction_horizon),
            'program_demand': prediction_service.predict_program_demand(prediction_horizon)
        }
        
        # Alertas Tempranas
        early_warnings = {
            'churn_risk': prediction_service.identify_churn_risk_users(),
            'underperforming_programs': prediction_service.identify_underperforming_programs(),
            'capacity_constraints': prediction_service.predict_capacity_constraints(),
            'financial_risks': prediction_service.identify_financial_risks()
        }
        
        # Recomendaciones del Sistema
        ai_recommendations = {
            'resource_allocation': prediction_service.recommend_resource_allocation(),
            'program_optimization': prediction_service.recommend_program_optimizations(),
            'investment_opportunities': prediction_service.identify_investment_opportunities(),
            'partnership_suggestions': prediction_service.suggest_strategic_partnerships()
        }
        
        # Análisis de Escenarios
        scenario_analysis = {
            'best_case': prediction_service.generate_best_case_scenario(),
            'worst_case': prediction_service.generate_worst_case_scenario(),
            'most_likely': prediction_service.generate_most_likely_scenario(),
            'stress_test': prediction_service.run_stress_test_scenarios()
        }
        
        # Market Intelligence
        market_intelligence = {
            'industry_trends': prediction_service.analyze_industry_trends(),
            'competitive_landscape': prediction_service.analyze_competitive_landscape(),
            'market_opportunities': prediction_service.identify_market_opportunities(),
            'threat_analysis': prediction_service.conduct_threat_analysis()
        }
        
        # Gráficos predictivos
        prediction_charts = {
            'growth_forecast': prediction_service.get_growth_forecast_chart(prediction_horizon),
            'risk_heatmap': prediction_service.get_risk_heatmap(),
            'opportunity_matrix': prediction_service.get_opportunity_matrix(),
            'scenario_comparison': prediction_service.get_scenario_comparison_chart(),
            'confidence_intervals': prediction_service.get_confidence_interval_chart(confidence_level)
        }
        
        return render_template(
            'admin/analytics/predictions.html',
            growth_predictions=growth_predictions,
            early_warnings=early_warnings,
            ai_recommendations=ai_recommendations,
            scenario_analysis=scenario_analysis,
            market_intelligence=market_intelligence,
            prediction_charts=prediction_charts,
            prediction_horizon=prediction_horizon,
            confidence_level=confidence_level
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics predictivos: {str(e)}")
        flash('Error al cargar analytics predictivos.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

# ============================================================================
# BENCHMARKING Y COMPARATIVAS
# ============================================================================

@admin_analytics.route('/benchmarks')
@login_required
@admin_required
@handle_exceptions
def benchmark_analytics():
    """
    Comparativas con benchmarks de la industria y competidores.
    """
    try:
        benchmark_service = BenchmarkService()
        
        # Benchmarks de Industria
        industry_benchmarks = {
            'incubator_standards': benchmark_service.get_incubator_industry_benchmarks(),
            'accelerator_standards': benchmark_service.get_accelerator_industry_benchmarks(),
            'vc_standards': benchmark_service.get_vc_industry_benchmarks(),
            'regional_standards': benchmark_service.get_regional_benchmarks()
        }
        
        # Performance vs Benchmarks
        performance_comparison = {
            'success_rates': benchmark_service.compare_success_rates(),
            'graduation_rates': benchmark_service.compare_graduation_rates(),
            'funding_rates': benchmark_service.compare_funding_rates(),
            'time_to_market': benchmark_service.compare_time_to_market(),
            'cost_efficiency': benchmark_service.compare_cost_efficiency()
        }
        
        # Competitive Analysis
        competitive_analysis = {
            'market_position': benchmark_service.analyze_market_position(),
            'competitive_advantages': benchmark_service.identify_competitive_advantages(),
            'improvement_areas': benchmark_service.identify_improvement_areas(),
            'best_practices': benchmark_service.extract_best_practices()
        }
        
        # Percentile Rankings
        percentile_rankings = {
            'overall_performance': benchmark_service.calculate_overall_percentile(),
            'program_effectiveness': benchmark_service.calculate_program_percentile(),
            'financial_performance': benchmark_service.calculate_financial_percentile(),
            'innovation_index': benchmark_service.calculate_innovation_percentile()
        }
        
        # Benchmark Trends
        benchmark_trends = benchmark_service.analyze_benchmark_trends()
        
        # Gráficos de benchmarking
        benchmark_charts = {
            'radar_chart': benchmark_service.get_performance_radar_chart(),
            'percentile_chart': benchmark_service.get_percentile_comparison_chart(),
            'trend_analysis': benchmark_service.get_benchmark_trend_chart(),
            'gap_analysis': benchmark_service.get_gap_analysis_chart(),
            'improvement_roadmap': benchmark_service.get_improvement_roadmap_chart()
        }
        
        return render_template(
            'admin/analytics/benchmarks.html',
            industry_benchmarks=industry_benchmarks,
            performance_comparison=performance_comparison,
            competitive_analysis=competitive_analysis,
            percentile_rankings=percentile_rankings,
            benchmark_trends=benchmark_trends,
            benchmark_charts=benchmark_charts
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en benchmark analytics: {str(e)}")
        flash('Error al cargar benchmark analytics.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

# ============================================================================
# REPORTES EJECUTIVOS
# ============================================================================

@admin_analytics.route('/reports')
@login_required
@admin_required
@handle_exceptions
def executive_reports():
    """
    Reportes ejecutivos y de alto nivel para stakeholders.
    """
    try:
        report_type = request.args.get('type', 'quarterly')
        period = request.args.get('period', 'current')
        
        report_service = ReportService()
        
        # Reporte Ejecutivo Principal
        executive_summary = {
            'ecosystem_overview': report_service.generate_ecosystem_overview(),
            'key_achievements': report_service.identify_key_achievements(),
            'strategic_challenges': report_service.identify_strategic_challenges(),
            'financial_highlights': report_service.generate_financial_highlights(),
            'operational_metrics': report_service.generate_operational_metrics()
        }
        
        # Reportes por Tipo
        if report_type == 'quarterly':
            detailed_report = report_service.generate_quarterly_report(period)
        elif report_type == 'annual':
            detailed_report = report_service.generate_annual_report(period)
        elif report_type == 'board':
            detailed_report = report_service.generate_board_report(period)
        elif report_type == 'investor':
            detailed_report = report_service.generate_investor_report(period)
        else:
            detailed_report = report_service.generate_monthly_report(period)
        
        # Impact Report
        impact_report = {
            'social_impact': report_service.calculate_social_impact(),
            'economic_impact': report_service.calculate_economic_impact(),
            'environmental_impact': report_service.calculate_environmental_impact(),
            'innovation_impact': report_service.calculate_innovation_impact()
        }
        
        # Strategic Insights
        strategic_insights = {
            'growth_opportunities': report_service.identify_growth_opportunities(),
            'risk_assessment': report_service.conduct_risk_assessment(),
            'resource_optimization': report_service.recommend_resource_optimization(),
            'strategic_priorities': report_service.recommend_strategic_priorities()
        }
        
        # Visualizaciones para reportes
        report_visualizations = {
            'executive_dashboard': report_service.generate_executive_dashboard(),
            'performance_scorecard': report_service.generate_performance_scorecard(),
            'trend_analysis': report_service.generate_trend_analysis(),
            'comparative_analysis': report_service.generate_comparative_analysis()
        }
        
        return render_template(
            'admin/analytics/reports.html',
            executive_summary=executive_summary,
            detailed_report=detailed_report,
            impact_report=impact_report,
            strategic_insights=strategic_insights,
            report_visualizations=report_visualizations,
            report_type=report_type,
            period=period
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reportes ejecutivos: {str(e)}")
        flash('Error al cargar reportes ejecutivos.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

# ============================================================================
# REAL-TIME ANALYTICS
# ============================================================================

@admin_analytics.route('/realtime')
@login_required
@admin_required
@handle_exceptions
def realtime_analytics():
    """
    Analytics en tiempo real con actualización automática.
    """
    try:
        # Métricas en tiempo real
        realtime_metrics = _get_comprehensive_realtime_metrics()
        
        # Actividad en vivo
        live_activity = _get_live_activity_feed()
        
        # Alertas activas
        active_alerts = _get_active_alerts()
        
        # Performance en tiempo real
        realtime_performance = _get_realtime_performance_metrics()
        
        return render_template(
            'admin/analytics/realtime.html',
            realtime_metrics=realtime_metrics,
            live_activity=live_activity,
            active_alerts=active_alerts,
            realtime_performance=realtime_performance
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en analytics en tiempo real: {str(e)}")
        flash('Error al cargar analytics en tiempo real.', 'error')
        return redirect(url_for('admin_analytics.dashboard'))

# ============================================================================
# API ENDPOINTS PARA ANALYTICS
# ============================================================================

@admin_analytics.route('/api/kpis')
@login_required
@admin_required
@rate_limit(200, per_minute=True)
def api_get_kpis():
    """API para obtener KPIs en tiempo real."""
    try:
        date_range = request.args.get('date_range', '30d')
        start_date, end_date = get_date_range(date_range)
        
        kpis = _get_ecosystem_kpis(start_date, end_date)
        
        return jsonify({
            'success': True,
            'data': kpis,
            'timestamp': datetime.utcnow().isoformat(),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_analytics.route('/api/chart-data/<chart_type>')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_get_chart_data(chart_type):
    """API para obtener datos específicos de gráficos."""
    try:
        date_range = request.args.get('date_range', '30d')
        start_date, end_date = get_date_range(date_range)
        
        analytics_service = AnalyticsService()
        
        if chart_type == 'ecosystem_growth':
            data = analytics_service.get_ecosystem_growth_trend(start_date, end_date)
        elif chart_type == 'user_acquisition':
            data = analytics_service.get_user_acquisition_funnel(start_date, end_date)
        elif chart_type == 'revenue_trends':
            data = analytics_service.get_revenue_trends(start_date, end_date)
        elif chart_type == 'success_pipeline':
            data = analytics_service.get_success_pipeline_data()
        elif chart_type == 'geographic_heatmap':
            data = analytics_service.get_geographic_heatmap()
        else:
            return jsonify({'error': 'Chart type not supported'}), 400
        
        return jsonify({
            'success': True,
            'chart_type': chart_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_analytics.route('/api/realtime-metrics')
@login_required
@admin_required
@rate_limit(300, per_minute=True)
def api_realtime_metrics():
    """API para métricas en tiempo real."""
    try:
        metrics = _get_comprehensive_realtime_metrics()
        
        return jsonify({
            'success': True,
            'data': metrics,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_analytics.route('/api/export-data')
@login_required
@admin_required
@permission_required('export_analytics')
def api_export_analytics_data():
    """API para exportar datos de analytics."""
    try:
        export_type = request.args.get('type', 'comprehensive')
        format_type = request.args.get('format', 'json')
        date_range = request.args.get('date_range', '90d')
        
        start_date, end_date = get_date_range(date_range)
        
        # Preparar datos para exportación
        export_data = _prepare_export_data(export_type, start_date, end_date)
        
        if format_type == 'json':
            response = make_response(jsonify(export_data))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=analytics_{export_type}_{datetime.now().strftime("%Y%m%d")}.json'
            return response
        elif format_type == 'csv':
            # Convertir a CSV
            df = pd.DataFrame(export_data)
            csv_data = df.to_csv(index=False)
            response = make_response(csv_data)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=analytics_{export_type}_{datetime.now().strftime("%Y%m%d")}.csv'
            return response
        else:
            return jsonify({'error': 'Format not supported'}), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# FUNCIONES AUXILIARES - MÉTRICAS PRINCIPALES
# ============================================================================

def _get_ecosystem_kpis(start_date, end_date):
    """Obtiene los KPIs principales del ecosistema."""
    return {
        # Métricas de Usuarios
        'total_active_users': User.query.filter_by(is_active=True).count(),
        'new_users_period': User.query.filter(
            and_(User.created_at >= start_date, User.created_at <= end_date)
        ).count(),
        'monthly_active_users': _calculate_monthly_active_users(),
        'user_retention_rate': _calculate_user_retention_rate(),
        
        # Métricas de Emprendedores
        'total_entrepreneurs': Entrepreneur.query.join(User).filter(User.is_active == True).count(),
        'active_entrepreneurs': _count_active_entrepreneurs(),
        'success_rate': _calculate_entrepreneur_success_rate(),
        'funding_success_rate': _calculate_funding_success_rate(),
        
        # Métricas de Programas
        'total_programs': Program.query.count(),
        'active_programs': Program.query.filter_by(status='active').count(),
        'program_completion_rate': _calculate_avg_program_completion_rate(),
        'program_effectiveness_score': _calculate_program_effectiveness_score(),
        
        # Métricas Financieras
        'total_funding_raised': _calculate_total_funding_raised(),
        'ecosystem_valuation': _calculate_ecosystem_valuation(),
        'roi_percentage': _calculate_ecosystem_roi_percentage(),
        'revenue_growth_rate': _calculate_revenue_growth_rate(),
        
        # Métricas de Impacto
        'jobs_created': _estimate_jobs_created(),
        'companies_launched': _count_companies_launched(),
        'patents_filed': _count_patents_filed(),
        'social_impact_score': _calculate_social_impact_score()
    }

def _get_growth_metrics(start_date, end_date):
    """Obtiene métricas de crecimiento."""
    previous_period_start = start_date - (end_date - start_date)
    previous_period_end = start_date
    
    current_users = User.query.filter(
        and_(User.created_at >= start_date, User.created_at <= end_date)
    ).count()
    
    previous_users = User.query.filter(
        and_(User.created_at >= previous_period_start, User.created_at <= previous_period_end)
    ).count()
    
    user_growth_rate = ((current_users - previous_users) / previous_users * 100) if previous_users > 0 else 0
    
    return {
        'user_growth_rate': user_growth_rate,
        'entrepreneur_growth_rate': _calculate_entrepreneur_growth_rate(start_date, end_date),
        'revenue_growth_rate': _calculate_revenue_growth_rate(),
        'program_growth_rate': _calculate_program_growth_rate(start_date, end_date),
        'ecosystem_expansion_rate': _calculate_ecosystem_expansion_rate()
    }

def _get_ecosystem_performance():
    """Obtiene métricas de performance del ecosistema."""
    return {
        'overall_health_score': _calculate_ecosystem_health_score(),
        'efficiency_score': _calculate_efficiency_score(),
        'innovation_index': _calculate_innovation_index(),
        'sustainability_score': _calculate_sustainability_score(),
        'competitive_advantage_score': _calculate_competitive_advantage_score()
    }

def _get_financial_overview(start_date, end_date):
    """Obtiene overview financiero."""
    return {
        'total_revenue': _calculate_total_revenue(start_date, end_date),
        'total_investments': _calculate_total_investments(),
        'operational_costs': _calculate_operational_costs(start_date, end_date),
        'net_profit': _calculate_net_profit(start_date, end_date),
        'cash_flow': _calculate_cash_flow(start_date, end_date),
        'burn_rate': _calculate_burn_rate()
    }

def _calculate_ecosystem_health_score():
    """Calcula un score compuesto de salud del ecosistema."""
    # Factores de salud (0-100 cada uno)
    user_health = min(100, (_calculate_monthly_active_users() / 1000) * 100)
    financial_health = min(100, (_calculate_net_profit_margin() + 50) * 2)
    growth_health = min(100, (_calculate_revenue_growth_rate() + 10) * 5)
    success_health = _calculate_entrepreneur_success_rate()
    retention_health = _calculate_user_retention_rate()
    
    # Promedio ponderado
    weights = [0.25, 0.25, 0.2, 0.15, 0.15]
    scores = [user_health, financial_health, growth_health, success_health, retention_health]
    
    health_score = sum(w * s for w, s in zip(weights, scores))
    
    return round(health_score, 1)

def _generate_automated_insights(ecosystem_kpis, growth_metrics):
    """Genera insights automáticos basados en datos."""
    insights = []
    
    # Insight sobre crecimiento de usuarios
    if growth_metrics['user_growth_rate'] > 20:
        insights.append({
            'type': 'positive',
            'title': 'Crecimiento Acelerado de Usuarios',
            'description': f"El crecimiento de usuarios ({growth_metrics['user_growth_rate']:.1f}%) está por encima de objetivos.",
            'action': 'Considerar escalar infraestructura y programas.'
        })
    elif growth_metrics['user_growth_rate'] < 5:
        insights.append({
            'type': 'warning',
            'title': 'Crecimiento Lento de Usuarios',
            'description': f"El crecimiento de usuarios ({growth_metrics['user_growth_rate']:.1f}%) está por debajo de objetivos.",
            'action': 'Revisar estrategias de marketing y adquisición.'
        })
    
    # Insight sobre tasa de éxito
    if ecosystem_kpis['success_rate'] > 30:
        insights.append({
            'type': 'positive',
            'title': 'Alta Tasa de Éxito',
            'description': f"La tasa de éxito ({ecosystem_kpis['success_rate']:.1f}%) supera benchmarks de industria.",
            'action': 'Documentar y replicar mejores prácticas.'
        })
    
    # Insight sobre ROI
    if ecosystem_kpis['roi_percentage'] > 200:
        insights.append({
            'type': 'positive',
            'title': 'ROI Excepcional',
            'description': f"El ROI del ecosistema ({ecosystem_kpis['roi_percentage']:.1f}%) es excepcional.",
            'action': 'Considerar expandir inversiones y programas.'
        })
    
    return insights

def _get_comparison_data(start_date, end_date, compare_period):
    """Obtiene datos de comparación con período anterior."""
    if compare_period == 'previous_period':
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
    elif compare_period == 'year_over_year':
        prev_start = start_date.replace(year=start_date.year - 1)
        prev_end = end_date.replace(year=end_date.year - 1)
    else:
        # Previous month
        prev_end = start_date.replace(day=1) - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
    
    current_kpis = _get_ecosystem_kpis(start_date, end_date)
    previous_kpis = _get_ecosystem_kpis(prev_start, prev_end)
    
    comparison = {}
    for key in current_kpis:
        if isinstance(current_kpis[key], (int, float)) and isinstance(previous_kpis[key], (int, float)):
            if previous_kpis[key] != 0:
                change_percent = ((current_kpis[key] - previous_kpis[key]) / previous_kpis[key]) * 100
                comparison[key] = {
                    'current': current_kpis[key],
                    'previous': previous_kpis[key],
                    'change_percent': round(change_percent, 2),
                    'trend': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
                }
            else:
                comparison[key] = {
                    'current': current_kpis[key],
                    'previous': previous_kpis[key],
                    'change_percent': float('inf') if current_kpis[key] > 0 else 0,
                    'trend': 'up' if current_kpis[key] > 0 else 'stable'
                }
    
    return comparison

def _get_top_performers_summary():
    """Obtiene resumen de top performers."""
    return {
        'entrepreneurs': Entrepreneur.query.filter(
            Entrepreneur.evaluation_score >= 85
        ).order_by(desc(Entrepreneur.evaluation_score)).limit(5).all(),
        
        'programs': Program.query.filter(
            and_(Program.success_rate >= 40, Program.graduation_rate >= 80)
        ).order_by(desc(Program.success_rate)).limit(5).all(),
        
        'organizations': Organization.query.filter(
            Organization.impact_score >= 4.0
        ).order_by(desc(Organization.impact_score)).limit(5).all()
    }

def _get_attention_items_summary():
    """Obtiene items que requieren atención."""
    return {
        'underperforming_entrepreneurs': Entrepreneur.query.filter(
            Entrepreneur.evaluation_score < 40
        ).count(),
        
        'struggling_programs': Program.query.filter(
            or_(Program.graduation_rate < 50, Program.success_rate < 15)
        ).count(),
        
        'inactive_users': User.query.filter(
            and_(
                User.is_active == True,
                User.last_login < datetime.utcnow() - timedelta(days=30)
            )
        ).count(),
        
        'capacity_issues': Program.query.filter(
            Program.current_participants > Program.max_participants * 0.9
        ).count()
    }

def _get_realtime_metrics():
    """Obtiene métricas en tiempo real."""
    now = datetime.utcnow()
    last_hour = now - timedelta(hours=1)
    
    return {
        'active_users_now': _count_currently_active_users(),
        'new_registrations_today': User.query.filter(
            User.created_at >= now.replace(hour=0, minute=0, second=0)
        ).count(),
        'meetings_today': Meeting.query.filter(
            func.date(Meeting.scheduled_for) == now.date()
        ).count(),
        'documents_uploaded_today': Document.query.filter(
            func.date(Document.uploaded_at) == now.date()
        ).count(),
        'system_load': _get_system_load_metric(),
        'response_time': _get_avg_response_time()
    }

# ============================================================================
# FUNCIONES AUXILIARES - CÁLCULOS ESPECÍFICOS
# ============================================================================

def _calculate_monthly_active_users():
    """Calcula usuarios activos mensuales."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    return User.query.filter(
        and_(
            User.is_active == True,
            User.last_login >= thirty_days_ago
        )
    ).count()

def _calculate_user_retention_rate():
    """Calcula tasa de retención de usuarios."""
    # Usuarios que se registraron hace 30 días
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    cohort_users = User.query.filter(
        and_(
            User.created_at >= sixty_days_ago,
            User.created_at < thirty_days_ago
        )
    ).count()
    
    retained_users = User.query.filter(
        and_(
            User.created_at >= sixty_days_ago,
            User.created_at < thirty_days_ago,
            User.last_login >= thirty_days_ago
        )
    ).count()
    
    return (retained_users / cohort_users * 100) if cohort_users > 0 else 0

def _calculate_entrepreneur_success_rate():
    """Calcula tasa de éxito de emprendedores."""
    total_entrepreneurs = Entrepreneur.query.join(User).filter(User.is_active == True).count()
    successful_entrepreneurs = Entrepreneur.query.filter(
        or_(
            Entrepreneur.evaluation_score >= 80,
            and_(
                Entrepreneur.funding_raised.isnot(None),
                Entrepreneur.funding_raised > 0
            )
        )
    ).count()
    
    return (successful_entrepreneurs / total_entrepreneurs * 100) if total_entrepreneurs > 0 else 0

def _calculate_funding_success_rate():
    """Calcula tasa de éxito en conseguir funding."""
    total_entrepreneurs = Entrepreneur.query.count()
    funded_entrepreneurs = Entrepreneur.query.filter(
        and_(
            Entrepreneur.funding_raised.isnot(None),
            Entrepreneur.funding_raised > 0
        )
    ).count()
    
    return (funded_entrepreneurs / total_entrepreneurs * 100) if total_entrepreneurs > 0 else 0

def _calculate_total_funding_raised():
    """Calcula total de funding recaudado."""
    total = db.session.query(
        func.sum(Entrepreneur.funding_raised)
    ).filter(Entrepreneur.funding_raised.isnot(None)).scalar()
    
    return float(total) if total else 0

def _calculate_ecosystem_valuation():
    """Calcula valuación total del ecosistema."""
    # Simulación basada en empresas exitosas y funding
    successful_companies = Entrepreneur.query.filter(
        Entrepreneur.evaluation_score >= 80
    ).count()
    
    avg_valuation_multiplier = 5  # 5x el funding como estimación
    total_funding = _calculate_total_funding_raised()
    
    return total_funding * avg_valuation_multiplier

def _calculate_ecosystem_roi_percentage():
    """Calcula ROI del ecosistema."""
    total_investment = _calculate_total_ecosystem_investment()
    current_valuation = _calculate_ecosystem_valuation()
    
    if total_investment > 0:
        return ((current_valuation - total_investment) / total_investment * 100)
    return 0

def _calculate_total_ecosystem_investment():
    """Calcula inversión total en el ecosistema."""
    # Suma de presupuestos de programas + inversiones directas
    program_investments = db.session.query(
        func.sum(Program.budget)
    ).filter(Program.budget.isnot(None)).scalar() or 0
    
    direct_investments = db.session.query(
        func.sum(Investment.amount)
    ).scalar() or 0
    
    return float(program_investments + direct_investments)

def _estimate_jobs_created():
    """Estima empleos creados por el ecosistema."""
    # Estimación: 3 empleos promedio por emprendedor activo
    active_entrepreneurs = _count_active_entrepreneurs()
    return active_entrepreneurs * 3

def _count_companies_launched():
    """Cuenta empresas lanzadas."""
    return Entrepreneur.query.filter(
        Entrepreneur.business_stage.in_(['growth', 'scale'])
    ).count()

def _count_patents_filed():
    """Cuenta patentes registradas (simulado)."""
    # En un sistema real esto vendría de una base de datos de patentes
    innovative_entrepreneurs = Entrepreneur.query.filter(
        and_(
            Entrepreneur.evaluation_score >= 85,
            Entrepreneur.industry.in_(['technology', 'biotech', 'fintech'])
        )
    ).count()
    
    return int(innovative_entrepreneurs * 0.3)  # 30% registran patentes

def _calculate_social_impact_score():
    """Calcula score de impacto social."""
    # Score basado en empleos creados, empresas en sectores sociales, etc.
    jobs_created = _estimate_jobs_created()
    social_entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.industry.in_(['social', 'health', 'education', 'environment'])
    ).count()
    
    # Normalizar a escala 0-100
    job_score = min(100, (jobs_created / 1000) * 100)
    social_score = min(100, (social_entrepreneurs / 50) * 100)
    
    return (job_score + social_score) / 2

def _count_active_entrepreneurs():
    """Cuenta emprendedores activos."""
    return Entrepreneur.query.join(User).filter(
        and_(
            User.is_active == True,
            User.last_login >= datetime.utcnow() - timedelta(days=30)
        )
    ).count()

def _calculate_avg_program_completion_rate():
    """Calcula tasa promedio de completación de programas."""
    rates = db.session.query(Program.graduation_rate).filter(
        Program.graduation_rate.isnot(None)
    ).all()
    
    if rates:
        return sum(rate[0] for rate in rates) / len(rates)
    return 0

def _calculate_program_effectiveness_score():
    """Calcula score de efectividad de programas."""
    avg_graduation = _calculate_avg_program_completion_rate()
    avg_success = db.session.query(func.avg(Program.success_rate)).filter(
        Program.success_rate.isnot(None)
    ).scalar() or 0
    
    return (avg_graduation + avg_success) / 2

def _get_comprehensive_realtime_metrics():
    """Obtiene métricas comprehensivas en tiempo real."""
    now = datetime.utcnow()
    
    return {
        'timestamp': now.isoformat(),
        'active_sessions': _count_currently_active_users(),
        'new_registrations_last_hour': _count_new_registrations_last_hour(),
        'meetings_in_progress': _count_meetings_in_progress(),
        'documents_uploaded_last_hour': _count_documents_uploaded_last_hour(),
        'system_health': {
            'cpu_usage': _get_cpu_usage(),
            'memory_usage': _get_memory_usage(),
            'response_time': _get_avg_response_time(),
            'error_rate': _get_error_rate()
        },
        'user_activity': {
            'page_views_last_hour': _count_page_views_last_hour(),
            'api_calls_last_hour': _count_api_calls_last_hour(),
            'feature_usage': _get_feature_usage_stats()
        }
    }

def _get_live_activity_feed():
    """Obtiene feed de actividad en vivo."""
    return ActivityLog.query.options(
        joinedload(ActivityLog.user)
    ).order_by(desc(ActivityLog.created_at)).limit(20).all()

def _get_active_alerts():
    """Obtiene alertas activas del sistema."""
    alerts = []
    
    # Alert por alta carga del sistema
    if _get_cpu_usage() > 80:
        alerts.append({
            'type': 'critical',
            'message': 'Alta carga de CPU detectada',
            'timestamp': datetime.utcnow(),
            'action_required': True
        })
    
    # Alert por muchos usuarios inactivos
    inactive_rate = _calculate_inactive_user_rate()
    if inactive_rate > 30:
        alerts.append({
            'type': 'warning',
            'message': f'Alta tasa de usuarios inactivos: {inactive_rate:.1f}%',
            'timestamp': datetime.utcnow(),
            'action_required': False
        })
    
    return alerts

def _get_realtime_performance_metrics():
    """Obtiene métricas de performance en tiempo real."""
    return {
        'throughput': _calculate_system_throughput(),
        'latency': _get_avg_response_time(),
        'error_rate': _get_error_rate(),
        'availability': _calculate_system_availability(),
        'concurrent_users': _count_currently_active_users()
    }

def _prepare_export_data(export_type, start_date, end_date):
    """Prepara datos para exportación."""
    if export_type == 'comprehensive':
        return {
            'ecosystem_kpis': _get_ecosystem_kpis(start_date, end_date),
            'growth_metrics': _get_growth_metrics(start_date, end_date),
            'financial_overview': _get_financial_overview(start_date, end_date),
            'export_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'period': f"{start_date.isoformat()} to {end_date.isoformat()}",
                'generated_by': current_user.email
            }
        }
    elif export_type == 'financial':
        return _get_financial_overview(start_date, end_date)
    elif export_type == 'users':
        return _get_user_analytics_export(start_date, end_date)
    else:
        return _get_ecosystem_kpis(start_date, end_date)

# ============================================================================
# FUNCIONES AUXILIARES - MÉTRICAS SIMULADAS PARA DEMO
# ============================================================================

def _count_currently_active_users():
    """Cuenta usuarios actualmente activos (simulado)."""
    return User.query.filter(
        User.last_login >= datetime.utcnow() - timedelta(minutes=15)
    ).count()

def _get_system_load_metric():
    """Obtiene métrica de carga del sistema (simulado)."""
    import random
    return round(random.uniform(10, 90), 1)

def _get_avg_response_time():
    """Obtiene tiempo promedio de respuesta (simulado)."""
    import random
    return round(random.uniform(50, 300), 0)  # ms

def _get_cpu_usage():
    """Obtiene uso de CPU (simulado)."""
    import random
    return round(random.uniform(20, 85), 1)

def _get_memory_usage():
    """Obtiene uso de memoria (simulado)."""
    import random
    return round(random.uniform(40, 75), 1)

def _get_error_rate():
    """Obtiene tasa de errores (simulado)."""
    import random
    return round(random.uniform(0.1, 2.0), 2)

def _calculate_system_throughput():
    """Calcula throughput del sistema (simulado)."""
    import random
    return round(random.uniform(100, 1000), 0)  # requests/min

def _calculate_system_availability():
    """Calcula disponibilidad del sistema (simulado)."""
    return 99.9  # 99.9% uptime

def _calculate_inactive_user_rate():
    """Calcula tasa de usuarios inactivos."""
    total_users = User.query.filter_by(is_active=True).count()
    inactive_users = User.query.filter(
        and_(
            User.is_active == True,
            User.last_login < datetime.utcnow() - timedelta(days=30)
        )
    ).count()
    
    return (inactive_users / total_users * 100) if total_users > 0 else 0

# Funciones adicionales simuladas para completar la funcionalidad
def _count_new_registrations_last_hour():
    last_hour = datetime.utcnow() - timedelta(hours=1)
    return User.query.filter(User.created_at >= last_hour).count()

def _count_meetings_in_progress():
    now = datetime.utcnow()
    return Meeting.query.filter(
        and_(
            Meeting.scheduled_for <= now,
            Meeting.scheduled_for + timedelta(hours=1) >= now  # Asumiendo 1h de duración
        )
    ).count()

def _count_documents_uploaded_last_hour():
    last_hour = datetime.utcnow() - timedelta(hours=1)
    return Document.query.filter(Document.uploaded_at >= last_hour).count()

def _count_page_views_last_hour():
    # En un sistema real vendría de analytics web
    import random
    return random.randint(500, 2000)

def _count_api_calls_last_hour():
    # En un sistema real vendría de logs de API
    import random
    return random.randint(1000, 5000)

def _get_feature_usage_stats():
    # En un sistema real vendría de analytics de features
    return {
        'dashboard_views': 156,
        'profile_updates': 23,
        'document_uploads': 45,
        'meeting_scheduling': 12
    }