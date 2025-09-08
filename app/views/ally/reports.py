"""
Vistas para el sistema de reportes de aliados/mentores.

Este módulo maneja la generación, visualización y exportación de reportes
detallados sobre actividades, métricas y progreso de emprendedores asignados.
"""

import os
import json
import tempfile
from datetime import datetime, timedelta, date, timezone
from collections import defaultdict
from decimal import Decimal

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, desc, asc, extract, case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db, cache
from app.models.user import User
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.mentorship import MentorshipSession
from app.models.task import Task
from app.models.document import Document
from app.models.analytics import AnalyticsEvent
from app.core.exceptions import ValidationError, ReportGenerationError
from app.core.permissions import require_role, require_ally_access
from app.utils.decorators import handle_db_errors, log_activity, cache_response
from app.utils.validators import validate_date_range, validate_report_params
from app.utils.formatters import format_currency, format_hours, format_percentage
from app.utils.date_utils import get_date_range_for_period, get_quarter_dates
from app.utils.export_utils import (
    generate_report_pdf, generate_report_excel, 
    generate_chart_image, create_dashboard_pdf
)
from app.services.analytics_service import AnalyticsService
from app.services.project_service import ProjectService
from app.services.mentorship_service import MentorshipService

# Blueprint para las vistas de reportes de aliados
ally_reports_bp = Blueprint('ally_reports', __name__, url_prefix='/ally/reports')

# Tipos de reportes disponibles
REPORT_TYPES = {
    'overview': 'Resumen General',
    'entrepreneurs': 'Emprendedores Asignados',
    'projects': 'Proyectos y Progreso',
    'hours': 'Registro de Horas',
    'mentorship': 'Sesiones de Mentoría',
    'financial': 'Reporte Financiero',
    'performance': 'Métricas de Desempeño',
    'comparative': 'Análisis Comparativo',
    'activity': 'Log de Actividades'
}

# Períodos disponibles
PERIOD_OPTIONS = {
    'current_week': 'Semana Actual',
    'last_week': 'Semana Pasada',
    'current_month': 'Mes Actual',
    'last_month': 'Mes Pasado',
    'current_quarter': 'Trimestre Actual',
    'last_quarter': 'Trimestre Pasado',
    'current_year': 'Año Actual',
    'last_year': 'Año Pasado',
    'custom': 'Período Personalizado'
}


@ally_reports_bp.route('/')
@login_required
@require_role('ally')
@log_activity('view_reports_dashboard')
def index():
    """
    Dashboard principal de reportes para aliados.
    
    Muestra resumen de métricas clave, reportes disponibles
    y accesos rápidos a funcionalidades principales.
    """
    try:
        ally = current_user.ally
        
        # Obtener período por defecto (mes actual)
        start_date, end_date = get_date_range_for_period('current_month')
        
        # Métricas generales del período
        metrics = _get_dashboard_metrics(ally, start_date, end_date)
        
        # Reportes recientes generados
        recent_reports = _get_recent_reports(ally.id)
        
        # Tendencias semanales (últimas 8 semanas)
        weekly_trends = _get_weekly_trends(ally, weeks=8)
        
        # Top emprendedores por actividad
        top_entrepreneurs = _get_top_entrepreneurs_by_activity(ally, start_date, end_date)
        
        # Distribución de tiempo por tipo de actividad
        activity_distribution = _get_activity_time_distribution(ally, start_date, end_date)
        
        # Próximos hitos y deadlines
        upcoming_milestones = _get_upcoming_milestones(ally)
        
        return render_template(
            'ally/reports/dashboard.html',
            ally=ally,
            metrics=metrics,
            recent_reports=recent_reports,
            weekly_trends=weekly_trends,
            top_entrepreneurs=top_entrepreneurs,
            activity_distribution=activity_distribution,
            upcoming_milestones=upcoming_milestones,
            report_types=REPORT_TYPES,
            period_options=PERIOD_OPTIONS,
            start_date=start_date,
            end_date=end_date,
            format_currency=format_currency,
            format_hours=format_hours,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de reportes: {str(e)}")
        flash('Error al cargar el dashboard de reportes.', 'error')
        return redirect(url_for('ally.dashboard'))


@ally_reports_bp.route('/generate')
@login_required
@require_role('ally')
@log_activity('access_report_generator')
def generate():
    """
    Formulario para generar reportes personalizados.
    
    Permite seleccionar tipo de reporte, período, filtros
    y formato de exportación.
    """
    try:
        ally = current_user.ally
        
        # Obtener emprendedores asignados para filtros
        entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(
                Project.ally_id == ally.id,
                Project.status.in_(['active', 'in_progress', 'completed'])
            )
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        # Obtener proyectos para filtros
        projects = (
            Project.query
            .filter(Project.ally_id == ally.id)
            .order_by(Project.name)
            .all()
        )
        
        # Configuraciones por defecto
        default_config = {
            'report_type': 'overview',
            'period': 'current_month',
            'format': 'pdf',
            'include_charts': True,
            'include_details': True,
            'group_by': 'entrepreneur'
        }
        
        return render_template(
            'ally/reports/generate.html',
            ally=ally,
            entrepreneurs=entrepreneurs,
            projects=projects,
            report_types=REPORT_TYPES,
            period_options=PERIOD_OPTIONS,
            default_config=default_config
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar generador de reportes: {str(e)}")
        flash('Error al cargar el generador de reportes.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/generate', methods=['POST'])
@login_required
@require_role('ally')
@handle_db_errors
@log_activity('generate_report')
def generate_post():
    """
    Procesa la generación de un reporte personalizado.
    
    Valida parámetros, genera el reporte y devuelve el archivo
    o la vista según el formato solicitado.
    """
    try:
        ally = current_user.ally
        
        # Obtener parámetros del formulario
        report_type = request.form.get('report_type', 'overview')
        period = request.form.get('period', 'current_month')
        format_type = request.form.get('format', 'pdf')
        
        # Fechas personalizadas si aplica
        custom_start = request.form.get('start_date')
        custom_end = request.form.get('end_date')
        
        # Filtros opcionales
        entrepreneur_ids = request.form.getlist('entrepreneur_ids')
        project_ids = request.form.getlist('project_ids')
        include_charts = request.form.get('include_charts') == 'on'
        include_details = request.form.get('include_details') == 'on'
        group_by = request.form.get('group_by', 'entrepreneur')
        
        # Validar tipo de reporte
        if report_type not in REPORT_TYPES:
            flash('Tipo de reporte no válido.', 'error')
            return redirect(url_for('ally_reports.generate'))
        
        # Determinar rango de fechas
        if period == 'custom':
            if not custom_start or not custom_end:
                flash('Debe especificar fechas de inicio y fin para período personalizado.', 'error')
                return redirect(url_for('ally_reports.generate'))
            
            try:
                start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
                
                if start_date > end_date:
                    flash('La fecha de inicio debe ser anterior a la fecha de fin.', 'error')
                    return redirect(url_for('ally_reports.generate'))
                    
                if (end_date - start_date).days > 365:
                    flash('El período no puede ser mayor a un año.', 'error')
                    return redirect(url_for('ally_reports.generate'))
                    
            except ValueError:
                flash('Formato de fecha inválido.', 'error')
                return redirect(url_for('ally_reports.generate'))
        else:
            start_date, end_date = get_date_range_for_period(period)
        
        # Configuración del reporte
        report_config = {
            'ally_id': ally.id,
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'entrepreneur_ids': [int(id) for id in entrepreneur_ids if id],
            'project_ids': [int(id) for id in project_ids if id],
            'include_charts': include_charts,
            'include_details': include_details,
            'group_by': group_by,
            'generated_by': current_user.id,
            'generated_at': datetime.now(timezone.utc)
        }
        
        # Generar reporte según el tipo
        if format_type == 'html':
            return _generate_html_report(report_config)
        elif format_type == 'excel':
            return _generate_excel_report(report_config)
        else:  # PDF por defecto
            return _generate_pdf_report(report_config)
            
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(url_for('ally_reports.generate'))
    except ReportGenerationError as e:
        flash(f'Error al generar reporte: {str(e)}', 'error')
        return redirect(url_for('ally_reports.generate'))
    except Exception as e:
        current_app.logger.error(f"Error al generar reporte: {str(e)}")
        flash('Error interno al generar el reporte.', 'error')
        return redirect(url_for('ally_reports.generate'))


@ally_reports_bp.route('/overview')
@login_required
@require_role('ally')
@cache_response(timeout=300)  # Cache por 5 minutos
@log_activity('view_overview_report')
def overview():
    """
    Reporte de resumen general del aliado.
    
    Muestra métricas clave, gráficos de tendencias y resumen
    de actividades en un período específico.
    """
    try:
        ally = current_user.ally
        
        # Obtener parámetros
        period = request.args.get('period', 'current_month')
        start_date, end_date = get_date_range_for_period(period)
        
        # Datos del reporte
        report_data = _generate_overview_data(ally, start_date, end_date)
        
        return render_template(
            'ally/reports/overview.html',
            ally=ally,
            report_data=report_data,
            period=period,
            start_date=start_date,
            end_date=end_date,
            period_options=PERIOD_OPTIONS,
            format_currency=format_currency,
            format_hours=format_hours,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte overview: {str(e)}")
        flash('Error al generar el reporte de resumen.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/entrepreneurs')
@login_required
@require_role('ally')
@log_activity('view_entrepreneurs_report')
def entrepreneurs():
    """
    Reporte detallado de emprendedores asignados.
    
    Incluye progreso individual, métricas de mentorías
    y evaluación de desempeño.
    """
    try:
        ally = current_user.ally
        
        # Parámetros de filtrado
        period = request.args.get('period', 'current_quarter')
        entrepreneur_id = request.args.get('entrepreneur_id', type=int)
        sort_by = request.args.get('sort_by', 'progress')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Obtener emprendedores con datos
        entrepreneurs_data = _generate_entrepreneurs_report_data(
            ally, start_date, end_date, entrepreneur_id, sort_by
        )
        
        # Lista de emprendedores para filtro
        all_entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(Project.ally_id == ally.id)
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        return render_template(
            'ally/reports/entrepreneurs.html',
            ally=ally,
            entrepreneurs_data=entrepreneurs_data,
            all_entrepreneurs=all_entrepreneurs,
            period=period,
            selected_entrepreneur_id=entrepreneur_id,
            sort_by=sort_by,
            start_date=start_date,
            end_date=end_date,
            period_options=PERIOD_OPTIONS,
            format_currency=format_currency,
            format_hours=format_hours,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte de emprendedores: {str(e)}")
        flash('Error al generar el reporte de emprendedores.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/projects')
@login_required
@require_role('ally')
@log_activity('view_projects_report')
def projects():
    """
    Reporte de progreso de proyectos.
    
    Análisis detallado del estado, hitos, tareas completadas
    y métricas de cada proyecto asignado.
    """
    try:
        ally = current_user.ally
        
        # Parámetros
        status_filter = request.args.get('status', 'all')
        project_id = request.args.get('project_id', type=int)
        sort_by = request.args.get('sort_by', 'progress')
        include_completed = request.args.get('include_completed') == 'true'
        
        # Generar datos del reporte
        projects_data = _generate_projects_report_data(
            ally, status_filter, project_id, sort_by, include_completed
        )
        
        # Estadísticas generales
        total_projects = len(projects_data)
        active_projects = len([p for p in projects_data if p['status'] == 'active'])
        avg_progress = sum(p['progress_percentage'] for p in projects_data) / total_projects if total_projects > 0 else 0
        
        stats = {
            'total_projects': total_projects,
            'active_projects': active_projects,
            'completed_projects': len([p for p in projects_data if p['status'] == 'completed']),
            'avg_progress': avg_progress,
            'overdue_projects': len([p for p in projects_data if p.get('is_overdue', False)])
        }
        
        return render_template(
            'ally/reports/projects.html',
            ally=ally,
            projects_data=projects_data,
            stats=stats,
            status_filter=status_filter,
            selected_project_id=project_id,
            sort_by=sort_by,
            include_completed=include_completed,
            format_currency=format_currency,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte de proyectos: {str(e)}")
        flash('Error al generar el reporte de proyectos.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/hours')
@login_required
@require_role('ally')
@log_activity('view_hours_report')
def hours():
    """
    Reporte detallado de horas trabajadas.
    
    Análisis de tiempo invertido, distribución por actividades,
    tendencias y métricas de productividad.
    """
    try:
        ally = current_user.ally
        
        # Parámetros
        period = request.args.get('period', 'current_month')
        group_by = request.args.get('group_by', 'week')
        activity_type = request.args.get('activity_type', 'all')
        billable_only = request.args.get('billable_only') == 'true'
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Generar datos del reporte
        hours_data = _generate_hours_report_data(
            ally, start_date, end_date, group_by, activity_type, billable_only
        )
        
        return render_template(
            'ally/reports/hours.html',
            ally=ally,
            hours_data=hours_data,
            period=period,
            group_by=group_by,
            activity_type=activity_type,
            billable_only=billable_only,
            start_date=start_date,
            end_date=end_date,
            period_options=PERIOD_OPTIONS,
            format_hours=format_hours,
            format_currency=format_currency
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte de horas: {str(e)}")
        flash('Error al generar el reporte de horas.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/financial')
@login_required
@require_role('ally')
@log_activity('view_financial_report')
def financial():
    """
    Reporte financiero detallado.
    
    Ingresos, horas facturables, pagos pendientes
    y análisis de rentabilidad.
    """
    try:
        ally = current_user.ally
        
        # Parámetros
        period = request.args.get('period', 'current_quarter')
        currency = request.args.get('currency', 'USD')
        include_projections = request.args.get('include_projections') == 'true'
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Generar datos financieros
        financial_data = _generate_financial_report_data(
            ally, start_date, end_date, currency, include_projections
        )
        
        return render_template(
            'ally/reports/financial.html',
            ally=ally,
            financial_data=financial_data,
            period=period,
            currency=currency,
            include_projections=include_projections,
            start_date=start_date,
            end_date=end_date,
            period_options=PERIOD_OPTIONS,
            format_currency=format_currency,
            format_hours=format_hours,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte financiero: {str(e)}")
        flash('Error al generar el reporte financiero.', 'error')
        return redirect(url_for('ally_reports.index'))


@ally_reports_bp.route('/performance')
@login_required
@require_role('ally')
@log_activity('view_performance_report')
def performance():
    """
    Reporte de métricas de desempeño.
    
    KPIs, comparaciones con objetivos, eficiencia
    y evaluación de impacto en emprendedores.
    """
    try:
        ally = current_user.ally
        
        # Parámetros
        period = request.args.get('period', 'current_quarter')
        compare_with = request.args.get('compare_with', 'previous_period')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Generar datos de desempeño
        performance_data = _generate_performance_report_data(
            ally, start_date, end_date, compare_with
        )
        
        return render_template(
            'ally/reports/performance.html',
            ally=ally,
            performance_data=performance_data,
            period=period,
            compare_with=compare_with,
            start_date=start_date,
            end_date=end_date,
            period_options=PERIOD_OPTIONS,
            format_currency=format_currency,
            format_hours=format_hours,
            format_percentage=format_percentage
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en reporte de desempeño: {str(e)}")
        flash('Error al generar el reporte de desempeño.', 'error')
        return redirect(url_for('ally_reports.index'))


# API Endpoints para datos dinámicos

@ally_reports_bp.route('/api/chart-data/<report_type>')
@login_required
@require_role('ally')
@cache_response(timeout=600)  # Cache por 10 minutos
def api_chart_data(report_type):
    """API endpoint para obtener datos de gráficos via AJAX."""
    try:
        ally = current_user.ally
        
        # Parámetros
        period = request.args.get('period', 'current_month')
        chart_type = request.args.get('chart_type', 'line')
        
        start_date, end_date = get_date_range_for_period(period)
        
        if report_type == 'hours_trend':
            data = _get_hours_trend_data(ally, start_date, end_date)
        elif report_type == 'entrepreneur_progress':
            data = _get_entrepreneur_progress_data(ally, start_date, end_date)
        elif report_type == 'project_status':
            data = _get_project_status_data(ally)
        elif report_type == 'activity_distribution':
            data = _get_activity_distribution_data(ally, start_date, end_date)
        elif report_type == 'financial_trend':
            data = _get_financial_trend_data(ally, start_date, end_date)
        else:
            return jsonify({'error': 'Tipo de gráfico no válido'}), 400
        
        return jsonify({
            'success': True,
            'data': data,
            'period': period,
            'chart_type': chart_type
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API chart data: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@ally_reports_bp.route('/api/metrics/<metric_type>')
@login_required
@require_role('ally')
def api_metrics(metric_type):
    """API endpoint para métricas específicas."""
    try:
        ally = current_user.ally
        period = request.args.get('period', 'current_month')
        start_date, end_date = get_date_range_for_period(period)
        
        if metric_type == 'summary':
            metrics = _get_dashboard_metrics(ally, start_date, end_date)
        elif metric_type == 'kpis':
            metrics = _get_kpi_metrics(ally, start_date, end_date)
        elif metric_type == 'goals':
            metrics = _get_goals_progress(ally, start_date, end_date)
        else:
            return jsonify({'error': 'Tipo de métrica no válido'}), 400
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'period': period
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API metrics: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@ally_reports_bp.route('/export/<report_type>')
@login_required
@require_role('ally')
@log_activity('export_report')
def export_report(report_type):
    """
    Exporta un reporte específico en el formato solicitado.
    
    Soporta exportación en PDF, Excel y CSV según el tipo de reporte.
    """
    try:
        ally = current_user.ally
        
        # Parámetros
        format_type = request.args.get('format', 'pdf')
        period = request.args.get('period', 'current_month')
        
        start_date, end_date = get_date_range_for_period(period)
        
        # Configuración del reporte
        export_config = {
            'ally_id': ally.id,
            'report_type': report_type,
            'format': format_type,
            'start_date': start_date,
            'end_date': end_date,
            'timestamp': datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        }
        
        if format_type == 'excel':
            file_path = _export_to_excel(export_config)
            filename = f'{report_type}_reporte_{export_config["timestamp"]}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif format_type == 'csv':
            file_path = _export_to_csv(export_config)
            filename = f'{report_type}_reporte_{export_config["timestamp"]}.csv'
            mimetype = 'text/csv'
        else:  # PDF por defecto
            file_path = _export_to_pdf(export_config)
            filename = f'{report_type}_reporte_{export_config["timestamp"]}.pdf'
            mimetype = 'application/pdf'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al exportar reporte: {str(e)}")
        flash('Error al generar el archivo de exportación.', 'error')
        return redirect(url_for('ally_reports.index'))


# Funciones auxiliares privadas para generación de datos

def _get_dashboard_metrics(ally, start_date, end_date):
    """Obtiene métricas generales para el dashboard."""
    
    # Horas totales trabajadas
    total_hours = (
        db.session.query(func.sum(Meeting.duration_hours))
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .scalar() or 0
    )
    
    # Número de emprendedores activos
    active_entrepreneurs = (
        db.session.query(func.count(func.distinct(Project.entrepreneur_id)))
        .filter(
            Project.ally_id == ally.id,
            Project.status.in_(['active', 'in_progress'])
        )
        .scalar() or 0
    )
    
    # Proyectos completados en el período
    completed_projects = (
        Project.query
        .filter(
            Project.ally_id == ally.id,
            Project.status == 'completed',
            Project.completed_at >= start_date,
            Project.completed_at <= end_date
        )
        .count()
    )
    
    # Sesiones de mentoría realizadas
    mentorship_sessions = (
        MentorshipSession.query
        .filter(
            MentorshipSession.mentor_id == ally.user_id,
            MentorshipSession.status == 'completed',
            MentorshipSession.session_date >= start_date,
            MentorshipSession.session_date <= end_date
        )
        .count()
    )
    
    # Ingresos del período (horas facturables)
    total_earnings = (
        db.session.query(
            func.sum(Meeting.duration_hours * Meeting.hourly_rate)
        )
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.billable == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .scalar() or 0
    )
    
    # Promedio de satisfacción (si hay evaluaciones)
    avg_satisfaction = (
        db.session.query(func.avg(MentorshipSession.satisfaction_rating))
        .filter(
            MentorshipSession.mentor_id == ally.user_id,
            MentorshipSession.satisfaction_rating.isnot(None),
            MentorshipSession.session_date >= start_date,
            MentorshipSession.session_date <= end_date
        )
        .scalar() or 0
    )
    
    return {
        'total_hours': float(total_hours),
        'active_entrepreneurs': active_entrepreneurs,
        'completed_projects': completed_projects,
        'mentorship_sessions': mentorship_sessions,
        'total_earnings': float(total_earnings),
        'avg_satisfaction': float(avg_satisfaction) if avg_satisfaction else 0,
        'hours_goal_progress': _calculate_hours_goal_progress(ally, total_hours),
        'period_comparison': _get_period_comparison(ally, start_date, end_date)
    }


def _get_recent_reports(ally_id, limit=5):
    """Obtiene los reportes generados recientemente."""
    # Esto podría venir de una tabla de log de reportes generados
    # Por ahora devolvemos datos de ejemplo
    return [
        {
            'type': 'overview',
            'generated_at': datetime.now(timezone.utc) - timedelta(days=1),
            'period': 'current_month',
            'format': 'pdf'
        },
        {
            'type': 'entrepreneurs',
            'generated_at': datetime.now(timezone.utc) - timedelta(days=3),
            'period': 'current_quarter',
            'format': 'excel'
        }
    ]


def _get_weekly_trends(ally, weeks=8):
    """Obtiene tendencias semanales de actividad."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(weeks=weeks)
    
    # Horas por semana
    weekly_hours = (
        db.session.query(
            extract('week', Meeting.date).label('week'),
            extract('year', Meeting.date).label('year'),
            func.sum(Meeting.duration_hours).label('total_hours')
        )
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date
        )
        .group_by(
            extract('year', Meeting.date),
            extract('week', Meeting.date)
        )
        .order_by(
            extract('year', Meeting.date),
            extract('week', Meeting.date)
        )
        .all()
    )
    
    return [
        {
            'week': f"{w.year}-W{w.week:02d}",
            'hours': float(w.total_hours)
        }
        for w in weekly_hours
    ]


def _get_top_entrepreneurs_by_activity(ally, start_date, end_date, limit=5):
    """Obtiene los emprendedores más activos en el período."""
    entrepreneurs = (
        db.session.query(
            Entrepreneur.id,
            Entrepreneur.name,
            func.sum(Meeting.duration_hours).label('total_hours'),
            func.count(Meeting.id).label('total_meetings')
        )
        .join(Meeting, Meeting.entrepreneur_id == Entrepreneur.id)
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .group_by(Entrepreneur.id, Entrepreneur.name)
        .order_by(func.sum(Meeting.duration_hours).desc())
        .limit(limit)
        .all()
    )
    
    return [
        {
            'id': e.id,
            'name': e.name,
            'total_hours': float(e.total_hours),
            'total_meetings': e.total_meetings
        }
        for e in entrepreneurs
    ]


def _get_activity_time_distribution(ally, start_date, end_date):
    """Obtiene la distribución de tiempo por tipo de actividad."""
    distribution = (
        db.session.query(
            Meeting.activity_type,
            func.sum(Meeting.duration_hours).label('total_hours')
        )
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .group_by(Meeting.activity_type)
        .all()
    )
    
    total_hours = sum(float(d.total_hours) for d in distribution)
    
    return [
        {
            'activity_type': d.activity_type,
            'hours': float(d.total_hours),
            'percentage': (float(d.total_hours) / total_hours * 100) if total_hours > 0 else 0
        }
        for d in distribution
    ]


def _get_upcoming_milestones(ally, days_ahead=30):
    """Obtiene próximos hitos y deadlines."""
    cutoff_date = datetime.now(timezone.utc).date() + timedelta(days=days_ahead)
    
    # Tareas con fechas límite próximas
    upcoming_tasks = (
        Task.query
        .join(Project)
        .filter(
            Project.ally_id == ally.id,
            Task.due_date <= cutoff_date,
            Task.due_date >= datetime.now(timezone.utc).date(),
            Task.status != 'completed'
        )
        .order_by(Task.due_date)
        .limit(10)
        .all()
    )
    
    return [
        {
            'type': 'task',
            'title': task.title,
            'due_date': task.due_date,
            'project_name': task.project.name,
            'priority': task.priority
        }
        for task in upcoming_tasks
    ]


def _generate_overview_data(ally, start_date, end_date):
    """Genera datos completos para el reporte de resumen."""
    metrics = _get_dashboard_metrics(ally, start_date, end_date)
    
    # Datos adicionales específicos del overview
    project_progress = _get_projects_progress_summary(ally)
    entrepreneur_stats = _get_entrepreneurs_stats_summary(ally, start_date, end_date)
    activity_calendar = _get_activity_calendar_data(ally, start_date, end_date)
    
    return {
        'metrics': metrics,
        'project_progress': project_progress,
        'entrepreneur_stats': entrepreneur_stats,
        'activity_calendar': activity_calendar,
        'trends': _get_weekly_trends(ally, weeks=12),
        'goals_progress': _get_goals_progress(ally, start_date, end_date)
    }


def _generate_entrepreneurs_report_data(ally, start_date, end_date, entrepreneur_id=None, sort_by='progress'):
    """Genera datos del reporte de emprendedores."""
    query = (
        db.session.query(Entrepreneur)
        .join(Project)
        .filter(Project.ally_id == ally.id)
        .distinct()
    )
    
    if entrepreneur_id:
        query = query.filter(Entrepreneur.id == entrepreneur_id)
    
    entrepreneurs = query.all()
    
    entrepreneurs_data = []
    for entrepreneur in entrepreneurs:
        # Métricas del emprendedor en el período
        entrepreneur_metrics = _get_entrepreneur_metrics(
            entrepreneur, ally, start_date, end_date
        )
        
        entrepreneurs_data.append({
            'entrepreneur': entrepreneur,
            'metrics': entrepreneur_metrics,
            'projects': _get_entrepreneur_projects_summary(entrepreneur, ally),
            'recent_activities': _get_entrepreneur_recent_activities(
                entrepreneur, ally, start_date, end_date
            )
        })
    
    # Ordenar según criterio
    if sort_by == 'progress':
        entrepreneurs_data.sort(
            key=lambda x: x['metrics']['avg_project_progress'], 
            reverse=True
        )
    elif sort_by == 'hours':
        entrepreneurs_data.sort(
            key=lambda x: x['metrics']['total_hours'], 
            reverse=True
        )
    elif sort_by == 'name':
        entrepreneurs_data.sort(
            key=lambda x: x['entrepreneur'].name
        )
    
    return entrepreneurs_data


def _generate_projects_report_data(ally, status_filter='all', project_id=None, sort_by='progress', include_completed=False):
    """Genera datos del reporte de proyectos."""
    query = Project.query.filter(Project.ally_id == ally.id)
    
    if not include_completed:
        query = query.filter(Project.status != 'completed')
    
    if status_filter != 'all':
        query = query.filter(Project.status == status_filter)
    
    if project_id:
        query = query.filter(Project.id == project_id)
    
    projects = query.all()
    
    projects_data = []
    for project in projects:
        project_metrics = _get_project_detailed_metrics(project)
        
        projects_data.append({
            'project': project,
            'metrics': project_metrics,
            'progress_percentage': _calculate_project_progress_percentage(project),
            'tasks_summary': _get_project_tasks_summary(project),
            'recent_activities': _get_project_recent_activities(project),
            'is_overdue': _is_project_overdue(project),
            'next_milestones': _get_project_next_milestones(project)
        })
    
    # Ordenar
    if sort_by == 'progress':
        projects_data.sort(key=lambda x: x['progress_percentage'], reverse=True)
    elif sort_by == 'due_date':
        projects_data.sort(key=lambda x: x['project'].end_date or date.max)
    elif sort_by == 'name':
        projects_data.sort(key=lambda x: x['project'].name)
    
    return projects_data


def _generate_hours_report_data(ally, start_date, end_date, group_by='week', activity_type='all', billable_only=False):
    """Genera datos del reporte de horas."""
    query = (
        Meeting.query
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
    )
    
    if activity_type != 'all':
        query = query.filter(Meeting.activity_type == activity_type)
    
    if billable_only:
        query = query.filter(Meeting.billable == True)
    
    meetings = query.all()
    
    # Agrupar datos según el criterio
    grouped_data = defaultdict(lambda: {
        'total_hours': 0,
        'billable_hours': 0,
        'meetings_count': 0,
        'earnings': 0,
        'activities': defaultdict(float)
    })
    
    for meeting in meetings:
        if group_by == 'week':
            key = f"{meeting.date.year}-W{meeting.date.isocalendar()[1]:02d}"
        elif group_by == 'month':
            key = f"{meeting.date.year}-{meeting.date.month:02d}"
        elif group_by == 'entrepreneur':
            key = meeting.entrepreneur.name if meeting.entrepreneur else 'Sin asignar'
        elif group_by == 'project':
            key = meeting.project.name if meeting.project else 'Sin proyecto'
        else:  # day
            key = meeting.date.strftime('%Y-%m-%d')
        
        group = grouped_data[key]
        group['total_hours'] += meeting.duration_hours
        group['meetings_count'] += 1
        group['activities'][meeting.activity_type] += meeting.duration_hours
        
        if meeting.billable:
            group['billable_hours'] += meeting.duration_hours
            group['earnings'] += meeting.duration_hours * (meeting.hourly_rate or 0)
    
    # Convertir a lista ordenada
    hours_data = []
    for key, data in sorted(grouped_data.items()):
        hours_data.append({
            'period': key,
            'total_hours': data['total_hours'],
            'billable_hours': data['billable_hours'],
            'meetings_count': data['meetings_count'],
            'earnings': data['earnings'],
            'activities': dict(data['activities']),
            'utilization_rate': (data['billable_hours'] / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
        })
    
    # Estadísticas generales
    total_hours = sum(d['total_hours'] for d in hours_data)
    total_billable = sum(d['billable_hours'] for d in hours_data)
    total_earnings = sum(d['earnings'] for d in hours_data)
    
    return {
        'grouped_data': hours_data,
        'summary': {
            'total_hours': total_hours,
            'total_billable_hours': total_billable,
            'total_earnings': total_earnings,
            'avg_utilization': (total_billable / total_hours * 100) if total_hours > 0 else 0,
            'avg_hourly_rate': (total_earnings / total_billable) if total_billable > 0 else 0
        }
    }


def _generate_financial_report_data(ally, start_date, end_date, currency='USD', include_projections=False):
    """Genera datos del reporte financiero."""
    # Ingresos del período
    earnings_query = (
        db.session.query(
            func.sum(Meeting.duration_hours * Meeting.hourly_rate).label('total_earnings'),
            func.sum(Meeting.duration_hours).label('billable_hours'),
            func.avg(Meeting.hourly_rate).label('avg_rate')
        )
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.billable == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .first()
    )
    
    total_earnings = float(earnings_query.total_earnings or 0)
    billable_hours = float(earnings_query.billable_hours or 0)
    avg_rate = float(earnings_query.avg_rate or 0)
    
    # Ingresos por mes para tendencia
    monthly_earnings = (
        db.session.query(
            extract('year', Meeting.date).label('year'),
            extract('month', Meeting.date).label('month'),
            func.sum(Meeting.duration_hours * Meeting.hourly_rate).label('earnings')
        )
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.billable == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .group_by(
            extract('year', Meeting.date),
            extract('month', Meeting.date)
        )
        .order_by(
            extract('year', Meeting.date),
            extract('month', Meeting.date)
        )
        .all()
    )
    
    # Ingresos por emprendedor
    earnings_by_entrepreneur = (
        db.session.query(
            Entrepreneur.name,
            func.sum(Meeting.duration_hours * Meeting.hourly_rate).label('earnings'),
            func.sum(Meeting.duration_hours).label('hours')
        )
        .join(Meeting, Meeting.entrepreneur_id == Entrepreneur.id)
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.billable == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .group_by(Entrepreneur.id, Entrepreneur.name)
        .order_by(func.sum(Meeting.duration_hours * Meeting.hourly_rate).desc())
        .all()
    )
    
    # Proyecciones si se solicitan
    projections = {}
    if include_projections:
        projections = _calculate_earnings_projections(ally, start_date, end_date)
    
    return {
        'summary': {
            'total_earnings': total_earnings,
            'billable_hours': billable_hours,
            'avg_hourly_rate': avg_rate,
            'currency': currency
        },
        'monthly_trend': [
            {
                'period': f"{int(m.year)}-{int(m.month):02d}",
                'earnings': float(m.earnings)
            }
            for m in monthly_earnings
        ],
        'by_entrepreneur': [
            {
                'name': e.name,
                'earnings': float(e.earnings),
                'hours': float(e.hours),
                'avg_rate': float(e.earnings / e.hours) if e.hours > 0 else 0
            }
            for e in earnings_by_entrepreneur
        ],
        'projections': projections
    }


def _generate_performance_report_data(ally, start_date, end_date, compare_with='previous_period'):
    """Genera datos del reporte de desempeño."""
    current_metrics = _get_comprehensive_metrics(ally, start_date, end_date)
    
    # Período de comparación
    if compare_with == 'previous_period':
        period_length = (end_date - start_date).days
        compare_start = start_date - timedelta(days=period_length)
        compare_end = start_date - timedelta(days=1)
    elif compare_with == 'same_period_last_year':
        compare_start = start_date.replace(year=start_date.year - 1)
        compare_end = end_date.replace(year=end_date.year - 1)
    else:  # sin comparación
        compare_start = compare_end = None
    
    comparison_metrics = {}
    if compare_start and compare_end:
        comparison_metrics = _get_comprehensive_metrics(ally, compare_start, compare_end)
    
    # Calcular cambios y tendencias
    performance_changes = _calculate_performance_changes(current_metrics, comparison_metrics)
    
    # KPIs específicos
    kpis = _calculate_performance_kpis(ally, current_metrics)
    
    return {
        'current_metrics': current_metrics,
        'comparison_metrics': comparison_metrics,
        'changes': performance_changes,
        'kpis': kpis,
        'satisfaction_trend': _get_satisfaction_trend(ally, start_date, end_date),
        'efficiency_metrics': _get_efficiency_metrics(ally, start_date, end_date)
    }


# Funciones auxiliares adicionales

def _calculate_hours_goal_progress(ally, current_hours):
    """Calcula el progreso hacia el objetivo de horas."""
    monthly_goal = ally.monthly_hours_goal or 40
    return min((current_hours / monthly_goal * 100), 100) if monthly_goal > 0 else 0


def _get_period_comparison(ally, start_date, end_date):
    """Obtiene comparación con período anterior."""
    period_length = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date - timedelta(days=1)
    
    current_hours = (
        db.session.query(func.sum(Meeting.duration_hours))
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= start_date,
            Meeting.date <= end_date
        )
        .scalar() or 0
    )
    
    previous_hours = (
        db.session.query(func.sum(Meeting.duration_hours))
        .filter(
            Meeting.ally_id == ally.id,
            Meeting.completed == True,
            Meeting.date >= prev_start,
            Meeting.date <= prev_end
        )
        .scalar() or 0
    )
    
    if previous_hours > 0:
        change_percentage = ((current_hours - previous_hours) / previous_hours) * 100
    else:
        change_percentage = 100 if current_hours > 0 else 0
    
    return {
        'current_hours': float(current_hours),
        'previous_hours': float(previous_hours),
        'change_percentage': round(change_percentage, 1)
    }


def _get_kpi_metrics(ally, start_date, end_date):
    """Obtiene KPIs específicos del aliado."""
    # Implementar cálculo de KPIs específicos
    return {
        'entrepreneur_retention_rate': 95.0,
        'project_completion_rate': 78.5,
        'avg_session_rating': 4.6,
        'response_time_hours': 2.3,
        'goal_achievement_rate': 89.2
    }


def _get_goals_progress(ally, start_date, end_date):
    """Obtiene progreso hacia objetivos establecidos."""
    # Esto podría venir de una tabla de objetivos del aliado
    return {
        'monthly_hours': {
            'target': ally.monthly_hours_goal or 40,
            'achieved': 35.5,
            'progress': 88.75
        },
        'entrepreneur_satisfaction': {
            'target': 4.5,
            'achieved': 4.6,
            'progress': 102.2
        },
        'project_completion': {
            'target': 5,
            'achieved': 4,
            'progress': 80.0
        }
    }


# Funciones de exportación

def _generate_html_report(config):
    """Genera reporte en formato HTML."""
    report_type = config['report_type']
    
    if report_type == 'overview':
        data = _generate_overview_data(
            current_user.ally, config['start_date'], config['end_date']
        )
        template = 'ally/reports/exports/overview_html.html'
    elif report_type == 'entrepreneurs':
        data = _generate_entrepreneurs_report_data(
            current_user.ally, config['start_date'], config['end_date']
        )
        template = 'ally/reports/exports/entrepreneurs_html.html'
    else:
        raise ReportGenerationError(f"Tipo de reporte HTML no soportado: {report_type}")
    
    return render_template(template, data=data, config=config)


def _generate_excel_report(config):
    """Genera reporte en formato Excel."""
    file_path = generate_report_excel(config)
    
    filename = f"{config['report_type']}_reporte_{config['generated_at'].strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


def _generate_pdf_report(config):
    """Genera reporte en formato PDF."""
    file_path = generate_report_pdf(config)
    
    filename = f"{config['report_type']}_reporte_{config['generated_at'].strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


def _export_to_excel(config):
    """Exporta datos a Excel."""
    # Implementar exportación específica a Excel
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    # ... lógica de exportación ...
    return temp_file.name


def _export_to_csv(config):
    """Exporta datos a CSV."""
    # Implementar exportación específica a CSV
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    # ... lógica de exportación ...
    return temp_file.name


def _export_to_pdf(config):
    """Exporta datos a PDF."""
    # Implementar exportación específica a PDF
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    # ... lógica de exportación ...
    return temp_file.name


# Manejadores de errores

@ally_reports_bp.errorhandler(403)
def forbidden(error):
    """Maneja errores de acceso prohibido."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Acceso prohibido'}), 403
    flash('No tienes permisos para acceder a este reporte.', 'error')
    return redirect(url_for('ally_reports.index'))


@ally_reports_bp.errorhandler(404)
def not_found(error):
    """Maneja errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Reporte no encontrado'}), 404
    flash('El reporte solicitado no existe.', 'error')
    return redirect(url_for('ally_reports.index'))


@ally_reports_bp.errorhandler(500)
def internal_error(error):
    """Maneja errores internos del servidor."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en reportes: {str(error)}")
    
    if request.is_json:
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
    flash('Error interno al generar el reporte. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('ally_reports.index'))


# Hooks del blueprint

@ally_reports_bp.before_request
def before_request():
    """Se ejecuta antes de cada request al blueprint."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    if current_user.role != 'ally':
        abort(403)


@ally_reports_bp.after_request
def after_request(response):
    """Se ejecuta después de cada request al blueprint."""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response