"""
Vistas del sistema de reportes para clientes/stakeholders.

Este módulo maneja la generación, personalización y gestión de reportes:
- Reportes predefinidos por tipo de cliente
- Constructor de reportes personalizado
- Generación en múltiples formatos (PDF, Excel, CSV)
- Programación automática de reportes
- Historial y gestión de reportes generados
- Compartir y distribuir reportes
- Templates y branding personalizado

Tipos de reportes disponibles:
- Resumen Ejecutivo: Métricas clave y KPIs
- Impacto Detallado: Análisis profundo de resultados
- Financiero: ROI, ingresos, inversiones (inversores)
- Operacional: Actividades, procesos, eficiencia
- Comparativo: Benchmarking temporal y sectorial
- Personalizado: Constructor libre con widgets
"""

import os
import json
import uuid
import tempfile
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file, session
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
from app.models.document import Document
from app.models.analytics import AnalyticsEvent
from app.core.exceptions import ValidationError, ReportGenerationError
from app.utils.decorators import cache_response, log_activity, rate_limit, async_task
from app.utils.validators import validate_date_range, validate_report_config
from app.utils.formatters import format_currency, format_percentage, format_number, format_date
from app.utils.date_utils import get_date_range_for_period, get_quarter_dates
from app.utils.export_utils import (
    generate_custom_report_pdf, generate_custom_report_excel, 
    generate_executive_summary_pdf, generate_impact_analysis_pdf,
    generate_financial_report_pdf, generate_operational_report_pdf
)
from app.utils.string_utils import sanitize_input, generate_slug
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.services.notification_service import NotificationService

# Importar funciones del módulo principal
from . import (
    get_client_type, get_client_permissions, require_client_permission,
    track_client_activity, cache_key_for_client
)

# Blueprint para reportes de clientes
client_reports_bp = Blueprint(
    'client_reports', 
    __name__, 
    url_prefix='/reports'
)

# Configuraciones de reportes
REPORTS_CONFIG = {
    'MAX_REPORTS_PER_USER': 50,
    'MAX_SCHEDULED_REPORTS': 10,
    'CACHE_TIMEOUT': 1800,  # 30 minutos
    'MAX_REPORT_SIZE_MB': 50,
    'RETENTION_DAYS': 90,
    'MAX_RECIPIENTS': 20,
    'SUPPORTED_FORMATS': ['pdf', 'excel', 'csv', 'powerpoint']
}

# Templates de reportes predefinidos
REPORT_TEMPLATES = {
    'executive_summary': {
        'name': 'Resumen Ejecutivo',
        'description': 'Métricas clave y KPIs para stakeholders ejecutivos',
        'icon': 'fas fa-chart-pie',
        'estimated_time': '2-5 minutos',
        'sections': ['overview', 'key_metrics', 'trends', 'highlights'],
        'available_for': ['stakeholder', 'investor', 'partner']
    },
    'impact_analysis': {
        'name': 'Análisis de Impacto',
        'description': 'Evaluación detallada del impacto social y económico',
        'icon': 'fas fa-heart',
        'estimated_time': '5-10 minutos',
        'sections': ['social_impact', 'economic_impact', 'environmental_impact', 'case_studies'],
        'available_for': ['stakeholder', 'investor', 'partner']
    },
    'financial_performance': {
        'name': 'Desempeño Financiero',
        'description': 'ROI, métricas financieras y análisis de inversión',
        'icon': 'fas fa-dollar-sign',
        'estimated_time': '3-7 minutos',
        'sections': ['financial_overview', 'roi_analysis', 'investment_metrics', 'projections'],
        'available_for': ['investor']
    },
    'operational_report': {
        'name': 'Reporte Operacional',
        'description': 'Actividades, procesos y métricas operacionales',
        'icon': 'fas fa-cogs',
        'estimated_time': '4-8 minutos',
        'sections': ['activities_summary', 'process_metrics', 'efficiency_analysis', 'recommendations'],
        'available_for': ['stakeholder', 'partner']
    },
    'comparative_analysis': {
        'name': 'Análisis Comparativo',
        'description': 'Benchmarking temporal y sectorial',
        'icon': 'fas fa-balance-scale',
        'estimated_time': '5-12 minutos',
        'sections': ['temporal_comparison', 'sector_benchmark', 'performance_ranking', 'insights'],
        'available_for': ['stakeholder', 'investor', 'partner']
    },
    'custom_report': {
        'name': 'Reporte Personalizado',
        'description': 'Constructor libre para reportes a medida',
        'icon': 'fas fa-puzzle-piece',
        'estimated_time': 'Variable',
        'sections': 'configurable',
        'available_for': ['stakeholder', 'investor', 'partner']
    }
}

# Widgets disponibles para reportes personalizados
REPORT_WIDGETS = {
    'metrics_overview': {
        'name': 'Resumen de Métricas',
        'category': 'overview',
        'data_sources': ['projects', 'entrepreneurs', 'impact'],
        'chart_types': ['cards', 'gauges']
    },
    'trend_chart': {
        'name': 'Gráfico de Tendencias',
        'category': 'analytics',
        'data_sources': ['historical_data', 'time_series'],
        'chart_types': ['line', 'area', 'bar']
    },
    'geographic_map': {
        'name': 'Mapa Geográfico',
        'category': 'geographic',
        'data_sources': ['location_data', 'regional_metrics'],
        'chart_types': ['choropleth', 'bubble_map']
    },
    'top_performers': {
        'name': 'Top Performers',
        'category': 'ranking',
        'data_sources': ['entrepreneurs', 'projects', 'organizations'],
        'chart_types': ['leaderboard', 'horizontal_bar']
    },
    'financial_charts': {
        'name': 'Gráficos Financieros',
        'category': 'financial',
        'data_sources': ['revenue', 'investment', 'roi'],
        'chart_types': ['waterfall', 'funnel', 'financial_bar'],
        'restricted_to': ['investor']
    },
    'impact_metrics': {
        'name': 'Métricas de Impacto',
        'category': 'impact',
        'data_sources': ['social_impact', 'economic_impact', 'environmental_impact'],
        'chart_types': ['donut', 'stacked_bar', 'radar']
    },
    'comparison_table': {
        'name': 'Tabla Comparativa',
        'category': 'comparison',
        'data_sources': ['comparative_data', 'benchmarks'],
        'chart_types': ['table', 'heatmap']
    },
    'success_stories': {
        'name': 'Historias de Éxito',
        'category': 'narrative',
        'data_sources': ['case_studies', 'testimonials'],
        'chart_types': ['text_blocks', 'image_gallery']
    }
}


@dataclass
class ReportConfig:
    """Configuración de un reporte."""
    template: str
    title: str
    period: str
    start_date: datetime
    end_date: datetime
    filters: Dict[str, Any]
    widgets: List[str]
    format_type: str
    include_charts: bool
    include_analysis: bool
    branding: Dict[str, str]


@client_reports_bp.route('/')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('view_reports_dashboard')
def index():
    """
    Dashboard principal de reportes.
    
    Muestra reportes disponibles, historial de generación,
    reportes programados y accesos rápidos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Templates disponibles para el tipo de cliente
        available_templates = {
            k: v for k, v in REPORT_TEMPLATES.items()
            if client_type in v.get('available_for', [])
        }
        
        # Reportes recientes del usuario
        recent_reports = _get_user_recent_reports(current_user.id)
        
        # Reportes programados
        scheduled_reports = _get_user_scheduled_reports(current_user.id)
        
        # Estadísticas de uso
        usage_stats = _get_user_reports_usage_stats(current_user.id)
        
        # Reportes populares/recomendados
        popular_templates = _get_popular_report_templates(client_type)
        
        # Límites y cuotas
        user_limits = _get_user_report_limits(current_user.id)
        
        return render_template(
            'client/reports/index.html',
            available_templates=available_templates,
            recent_reports=recent_reports,
            scheduled_reports=scheduled_reports,
            usage_stats=usage_stats,
            popular_templates=popular_templates,
            user_limits=user_limits,
            reports_config=REPORTS_CONFIG,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de reportes: {str(e)}")
        flash('Error al cargar el dashboard de reportes.', 'error')
        return redirect(url_for('client.index'))


@client_reports_bp.route('/create')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('access_report_creator')
def create():
    """
    Formulario para crear nuevos reportes.
    
    Permite seleccionar template, configurar parámetros,
    filtros y opciones de formato.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Template seleccionado
        template = request.args.get('template', 'executive_summary')
        
        # Validar que el template esté disponible
        if template not in REPORT_TEMPLATES:
            flash('Template de reporte no válido.', 'error')
            return redirect(url_for('client_reports.index'))
        
        template_info = REPORT_TEMPLATES[template]
        if client_type not in template_info.get('available_for', []):
            flash('No tienes permisos para este tipo de reporte.', 'error')
            return redirect(url_for('client_reports.index'))
        
        # Opciones de configuración
        filter_options = _get_report_filter_options(permissions)
        period_options = _get_period_options()
        format_options = _get_format_options(permissions)
        
        # Widgets disponibles para reportes personalizados
        available_widgets = {}
        if template == 'custom_report':
            available_widgets = {
                k: v for k, v in REPORT_WIDGETS.items()
                if not v.get('restricted_to') or client_type in v.get('restricted_to', [])
            }
        
        # Configuración por defecto
        default_config = {
            'period': 'current_quarter',
            'format': 'pdf',
            'include_charts': True,
            'include_analysis': True,
            'include_branding': True
        }
        
        return render_template(
            'client/reports/create.html',
            template=template,
            template_info=template_info,
            filter_options=filter_options,
            period_options=period_options,
            format_options=format_options,
            available_widgets=available_widgets,
            default_config=default_config,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar creador de reportes: {str(e)}")
        flash('Error al cargar el creador de reportes.', 'error')
        return redirect(url_for('client_reports.index'))


@client_reports_bp.route('/create', methods=['POST'])
@login_required
@require_client_permission('can_export_basic_reports')
@rate_limit('10 per hour')
@log_activity('create_report')
def create_post():
    """
    Procesa la creación de un nuevo reporte.
    
    Valida configuración, genera el reporte y lo entrega
    al usuario o programa para entrega posterior.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Verificar límites del usuario
        if not _check_user_report_limits(current_user.id):
            flash('Has alcanzado el límite máximo de reportes. Elimina reportes antiguos para continuar.', 'error')
            return redirect(url_for('client_reports.index'))
        
        # Obtener configuración del formulario
        report_config = _extract_report_config_from_form(request.form)
        
        # Validar configuración
        validation_result = _validate_report_config(report_config, client_type, permissions)
        if not validation_result['valid']:
            for error in validation_result['errors']:
                flash(error, 'error')
            return redirect(url_for('client_reports.create', template=report_config.template))
        
        # Verificar modo de entrega
        delivery_mode = request.form.get('delivery_mode', 'immediate')
        
        if delivery_mode == 'immediate':
            # Generar reporte inmediatamente
            report_result = _generate_report_immediate(report_config, current_user.id)
            
            if report_result['success']:
                # Registrar reporte generado
                _save_report_record(report_config, current_user.id, report_result['file_path'])
                
                # Rastrear actividad
                track_client_activity('report_generated', {
                    'template': report_config.template,
                    'format': report_config.format_type,
                    'delivery_mode': 'immediate'
                })
                
                return send_file(
                    report_result['file_path'],
                    as_attachment=True,
                    download_name=report_result['filename'],
                    mimetype=report_result['mimetype']
                )
            else:
                flash('Error al generar el reporte. Por favor, intenta nuevamente.', 'error')
                return redirect(url_for('client_reports.create', template=report_config.template))
        
        elif delivery_mode == 'email':
            # Programar entrega por email
            email_recipients = request.form.get('email_recipients', '').strip()
            if not email_recipients:
                flash('Debe especificar al menos un destinatario de email.', 'error')
                return redirect(url_for('client_reports.create', template=report_config.template))
            
            # Validar emails
            recipients = [email.strip() for email in email_recipients.split(',')]
            if len(recipients) > REPORTS_CONFIG['MAX_RECIPIENTS']:
                flash(f'Máximo {REPORTS_CONFIG["MAX_RECIPIENTS"]} destinatarios permitidos.', 'error')
                return redirect(url_for('client_reports.create', template=report_config.template))
            
            # Programar generación y envío
            task_result = _schedule_report_generation_and_email(
                report_config, current_user.id, recipients
            )
            
            if task_result['success']:
                flash('Reporte programado para generación y envío. Recibirás una notificación cuando esté listo.', 'success')
                
                track_client_activity('report_scheduled_email', {
                    'template': report_config.template,
                    'recipients_count': len(recipients)
                })
            else:
                flash('Error al programar el reporte. Por favor, intenta nuevamente.', 'error')
            
            return redirect(url_for('client_reports.index'))
        
        elif delivery_mode == 'schedule':
            # Crear reporte programado recurrente
            schedule_config = _extract_schedule_config_from_form(request.form)
            
            # Validar configuración de programación
            if not _validate_schedule_config(schedule_config, current_user.id):
                flash('Configuración de programación inválida.', 'error')
                return redirect(url_for('client_reports.create', template=report_config.template))
            
            # Crear programación
            scheduled_report = _create_scheduled_report(
                report_config, schedule_config, current_user.id
            )
            
            if scheduled_report:
                flash('Reporte programado creado exitosamente.', 'success')
                
                track_client_activity('report_scheduled_recurring', {
                    'template': report_config.template,
                    'frequency': schedule_config['frequency']
                })
            else:
                flash('Error al crear la programación del reporte.', 'error')
            
            return redirect(url_for('client_reports.scheduled'))
        
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(url_for('client_reports.create'))
    except ReportGenerationError as e:
        flash(f'Error al generar reporte: {str(e)}', 'error')
        return redirect(url_for('client_reports.create'))
    except Exception as e:
        current_app.logger.error(f"Error creando reporte: {str(e)}")
        flash('Error interno al crear el reporte.', 'error')
        return redirect(url_for('client_reports.create'))


@client_reports_bp.route('/builder')
@login_required
@require_client_permission('can_access_detailed_analytics')
@log_activity('access_report_builder')
def builder():
    """
    Constructor visual de reportes personalizados.
    
    Interface drag & drop para crear reportes a medida
    con widgets configurables.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Widgets disponibles
        available_widgets = {
            k: v for k, v in REPORT_WIDGETS.items()
            if not v.get('restricted_to') or client_type in v.get('restricted_to', [])
        }
        
        # Configuración del builder
        builder_config = {
            'max_widgets': 12,
            'grid_columns': 12,
            'auto_save': True,
            'preview_enabled': True
        }
        
        # Templates guardados del usuario
        user_templates = _get_user_custom_templates(current_user.id)
        
        # Datos de muestra para preview
        sample_data = _get_sample_data_for_preview(permissions)
        
        return render_template(
            'client/reports/builder.html',
            available_widgets=available_widgets,
            builder_config=builder_config,
            user_templates=user_templates,
            sample_data=sample_data,
            client_type=client_type,
            permissions=permissions
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar constructor de reportes: {str(e)}")
        flash('Error al cargar el constructor de reportes.', 'error')
        return redirect(url_for('client_reports.index'))


@client_reports_bp.route('/history')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('view_reports_history')
def history():
    """
    Historial de reportes generados.
    
    Lista todos los reportes creados por el usuario
    con opciones de descarga, re-generación y gestión.
    """
    try:
        # Parámetros de paginación y filtrado
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        template_filter = request.args.get('template')
        format_filter = request.args.get('format')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Obtener historial de reportes
        reports_query = _build_reports_history_query(
            current_user.id, template_filter, format_filter, date_from, date_to
        )
        
        pagination = reports_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Estadísticas del historial
        history_stats = _get_reports_history_stats(current_user.id)
        
        # Opciones de filtro
        filter_options = {
            'templates': list(REPORT_TEMPLATES.keys()),
            'formats': REPORTS_CONFIG['SUPPORTED_FORMATS']
        }
        
        return render_template(
            'client/reports/history.html',
            pagination=pagination,
            reports=pagination.items,
            history_stats=history_stats,
            filter_options=filter_options,
            current_filters={
                'template': template_filter,
                'format': format_filter,
                'date_from': date_from,
                'date_to': date_to
            },
            report_templates=REPORT_TEMPLATES,
            format_date=format_date
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar historial de reportes: {str(e)}")
        flash('Error al cargar el historial de reportes.', 'error')
        return redirect(url_for('client_reports.index'))


@client_reports_bp.route('/scheduled')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('view_scheduled_reports')
def scheduled():
    """
    Gestión de reportes programados.
    
    Lista y administra reportes con programación automática,
    permitiendo editar, pausar o eliminar programaciones.
    """
    try:
        # Obtener reportes programados del usuario
        scheduled_reports = _get_user_scheduled_reports_detailed(current_user.id)
        
        # Estadísticas de programación
        scheduling_stats = _get_scheduling_stats(current_user.id)
        
        # Próximas ejecuciones
        upcoming_executions = _get_upcoming_report_executions(current_user.id)
        
        return render_template(
            'client/reports/scheduled.html',
            scheduled_reports=scheduled_reports,
            scheduling_stats=scheduling_stats,
            upcoming_executions=upcoming_executions,
            reports_config=REPORTS_CONFIG,
            report_templates=REPORT_TEMPLATES,
            format_date=format_date
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar reportes programados: {str(e)}")
        flash('Error al cargar los reportes programados.', 'error')
        return redirect(url_for('client_reports.index'))


@client_reports_bp.route('/download/<report_id>')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('download_report')
def download(report_id):
    """
    Descarga un reporte previamente generado.
    
    Verifica permisos de acceso y sirve el archivo
    con headers apropiados para descarga.
    """
    try:
        # Obtener información del reporte
        report_info = _get_report_info(report_id, current_user.id)
        
        if not report_info:
            flash('Reporte no encontrado o sin permisos para acceder.', 'error')
            return redirect(url_for('client_reports.history'))
        
        # Verificar que el archivo existe
        if not os.path.exists(report_info['file_path']):
            flash('El archivo del reporte ya no está disponible.', 'error')
            return redirect(url_for('client_reports.history'))
        
        # Actualizar contador de descargas
        _increment_report_download_count(report_id)
        
        # Rastrear descarga
        track_client_activity('report_downloaded', {
            'report_id': report_id,
            'template': report_info['template'],
            'format': report_info['format']
        })
        
        return send_file(
            report_info['file_path'],
            as_attachment=True,
            download_name=report_info['filename'],
            mimetype=report_info['mimetype']
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al descargar reporte: {str(e)}")
        flash('Error al descargar el reporte.', 'error')
        return redirect(url_for('client_reports.history'))


@client_reports_bp.route('/share/<report_id>')
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('share_report')
def share(report_id):
    """
    Formulario para compartir un reporte.
    
    Permite enviar reportes por email a destinatarios
    específicos con mensaje personalizado.
    """
    try:
        # Obtener información del reporte
        report_info = _get_report_info(report_id, current_user.id)
        
        if not report_info:
            flash('Reporte no encontrado o sin permisos para acceder.', 'error')
            return redirect(url_for('client_reports.history'))
        
        return render_template(
            'client/reports/share.html',
            report_info=report_info,
            max_recipients=REPORTS_CONFIG['MAX_RECIPIENTS']
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar formulario de compartir: {str(e)}")
        flash('Error al cargar el formulario para compartir.', 'error')
        return redirect(url_for('client_reports.history'))


@client_reports_bp.route('/share/<report_id>', methods=['POST'])
@login_required
@require_client_permission('can_export_basic_reports')
@rate_limit('20 per hour')
@log_activity('send_shared_report')
def share_post(report_id):
    """
    Procesa el envío de un reporte compartido.
    
    Valida destinatarios, genera email personalizado
    y envía el reporte como adjunto.
    """
    try:
        # Obtener información del reporte
        report_info = _get_report_info(report_id, current_user.id)
        
        if not report_info:
            flash('Reporte no encontrado o sin permisos para acceder.', 'error')
            return redirect(url_for('client_reports.history'))
        
        # Obtener datos del formulario
        recipients_input = request.form.get('recipients', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        include_sender_info = request.form.get('include_sender_info') == 'on'
        
        # Validar destinatarios
        if not recipients_input:
            flash('Debe especificar al menos un destinatario.', 'error')
            return redirect(url_for('client_reports.share', report_id=report_id))
        
        recipients = [email.strip() for email in recipients_input.split(',')]
        if len(recipients) > REPORTS_CONFIG['MAX_RECIPIENTS']:
            flash(f'Máximo {REPORTS_CONFIG["MAX_RECIPIENTS"]} destinatarios permitidos.', 'error')
            return redirect(url_for('client_reports.share', report_id=report_id))
        
        # Validar emails
        invalid_emails = [email for email in recipients if not _is_valid_email(email)]
        if invalid_emails:
            flash(f'Emails inválidos: {", ".join(invalid_emails)}', 'error')
            return redirect(url_for('client_reports.share', report_id=report_id))
        
        # Preparar datos del email
        email_data = {
            'recipients': recipients,
            'subject': subject or f'Reporte: {report_info["title"]}',
            'message': message,
            'report_info': report_info,
            'sender_name': current_user.name,
            'sender_email': current_user.email,
            'include_sender_info': include_sender_info
        }
        
        # Enviar email
        email_result = _send_shared_report_email(email_data)
        
        if email_result['success']:
            flash(f'Reporte enviado exitosamente a {len(recipients)} destinatario(s).', 'success')
            
            # Registrar compartido
            _log_report_shared(report_id, recipients, current_user.id)
            
            track_client_activity('report_shared', {
                'report_id': report_id,
                'recipients_count': len(recipients)
            })
        else:
            flash('Error al enviar el reporte. Por favor, intenta nuevamente.', 'error')
        
        return redirect(url_for('client_reports.history'))
        
    except Exception as e:
        current_app.logger.error(f"Error al compartir reporte: {str(e)}")
        flash('Error interno al compartir el reporte.', 'error')
        return redirect(url_for('client_reports.share', report_id=report_id))


@client_reports_bp.route('/delete/<report_id>', methods=['POST'])
@login_required
@require_client_permission('can_export_basic_reports')
@log_activity('delete_report')
def delete(report_id):
    """
    Elimina un reporte generado.
    
    Remueve el archivo y el registro de la base de datos,
    liberando espacio de almacenamiento.
    """
    try:
        # Verificar que el reporte pertenece al usuario
        report_info = _get_report_info(report_id, current_user.id)
        
        if not report_info:
            return jsonify({'success': False, 'error': 'Reporte no encontrado'}), 404
        
        # Eliminar archivo físico
        if os.path.exists(report_info['file_path']):
            try:
                os.remove(report_info['file_path'])
            except OSError as e:
                current_app.logger.warning(f"Error eliminando archivo de reporte: {str(e)}")
        
        # Eliminar registro de base de datos
        _delete_report_record(report_id)
        
        track_client_activity('report_deleted', {
            'report_id': report_id,
            'template': report_info['template']
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando reporte: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# API Endpoints para funcionalidades dinámicas

@client_reports_bp.route('/api/preview')
@login_required
@require_client_permission('can_export_basic_reports')
@rate_limit('30 per minute')
def api_preview():
    """API endpoint para preview de reportes."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener configuración del reporte
        template = request.args.get('template', 'executive_summary')
        period = request.args.get('period', 'current_month')
        filters = request.args.get('filters', '{}')
        
        try:
            filters_dict = json.loads(filters)
        except json.JSONDecodeError:
            filters_dict = {}
        
        # Validar template
        if template not in REPORT_TEMPLATES:
            return jsonify({'error': 'Template inválido'}), 400
        
        if client_type not in REPORT_TEMPLATES[template].get('available_for', []):
            return jsonify({'error': 'Sin permisos para este template'}), 403
        
        # Generar preview
        preview_data = _generate_report_preview(
            template, period, filters_dict, permissions
        )
        
        return jsonify({
            'success': True,
            'preview_data': preview_data,
            'template': template,
            'period': period
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API preview: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_reports_bp.route('/api/widgets/data')
@login_required
@require_client_permission('can_access_detailed_analytics')
def api_widget_data():
    """API endpoint para datos de widgets del builder."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        widget_type = request.args.get('widget_type')
        config = request.args.get('config', '{}')
        
        try:
            config_dict = json.loads(config)
        except json.JSONDecodeError:
            config_dict = {}
        
        # Validar widget
        if widget_type not in REPORT_WIDGETS:
            return jsonify({'error': 'Tipo de widget inválido'}), 400
        
        widget_info = REPORT_WIDGETS[widget_type]
        if widget_info.get('restricted_to') and client_type not in widget_info['restricted_to']:
            return jsonify({'error': 'Sin permisos para este widget'}), 403
        
        # Obtener datos del widget
        widget_data = _get_widget_data(widget_type, config_dict, permissions)
        
        return jsonify({
            'success': True,
            'widget_type': widget_type,
            'data': widget_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API widget data: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_reports_bp.route('/api/templates/save', methods=['POST'])
@login_required
@require_client_permission('can_access_detailed_analytics')
def api_save_template():
    """API endpoint para guardar templates personalizados."""
    try:
        data = request.get_json()
        
        # Validar datos
        if not data or 'name' not in data or 'config' not in data:
            return jsonify({'error': 'Datos inválidos'}), 400
        
        template_name = sanitize_input(data['name']).strip()
        if not template_name or len(template_name) > 100:
            return jsonify({'error': 'Nombre de template inválido'}), 400
        
        # Verificar límite de templates personalizados
        user_templates_count = _get_user_custom_templates_count(current_user.id)
        if user_templates_count >= 10:  # Límite de templates por usuario
            return jsonify({'error': 'Límite de templates personalizados alcanzado'}), 400
        
        # Guardar template
        template_id = _save_user_custom_template(
            current_user.id, template_name, data['config']
        )
        
        if template_id:
            track_client_activity('custom_template_saved', {
                'template_name': template_name,
                'widgets_count': len(data['config'].get('widgets', []))
            })
            
            return jsonify({
                'success': True,
                'template_id': template_id,
                'message': 'Template guardado exitosamente'
            })
        else:
            return jsonify({'error': 'Error al guardar template'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error guardando template: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_reports_bp.route('/api/generation-status/<task_id>')
@login_required
def api_generation_status(task_id):
    """API endpoint para verificar estado de generación de reportes."""
    try:
        # Verificar que la tarea pertenece al usuario
        task_info = _get_report_generation_task_info(task_id, current_user.id)
        
        if not task_info:
            return jsonify({'error': 'Tarea no encontrada'}), 404
        
        return jsonify({
            'success': True,
            'status': task_info['status'],
            'progress': task_info['progress'],
            'message': task_info['message'],
            'result_url': task_info.get('result_url'),
            'error_details': task_info.get('error_details')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error verificando estado de generación: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _extract_report_config_from_form(form_data):
    """Extrae configuración de reporte del formulario."""
    # Validar y parsear fechas
    period = form_data.get('period', 'current_quarter')
    
    if period == 'custom':
        start_date = datetime.strptime(form_data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(form_data.get('end_date'), '%Y-%m-%d').date()
    else:
        start_date, end_date = get_date_range_for_period(period)
    
    # Extraer filtros
    filters = {}
    if form_data.get('organization_filter'):
        filters['organization_id'] = int(form_data.get('organization_filter'))
    if form_data.get('program_filter'):
        filters['program_id'] = int(form_data.get('program_filter'))
    if form_data.get('location_filter'):
        filters['location'] = form_data.get('location_filter')
    if form_data.get('industry_filter'):
        filters['industry'] = form_data.get('industry_filter')
    
    # Extraer widgets para reportes personalizados
    widgets = form_data.getlist('widgets') if form_data.get('template') == 'custom_report' else []
    
    # Configuración de branding
    branding = {
        'include_logo': form_data.get('include_branding') == 'on',
        'color_scheme': form_data.get('color_scheme', 'default'),
        'footer_text': form_data.get('footer_text', '')
    }
    
    return ReportConfig(
        template=form_data.get('template', 'executive_summary'),
        title=sanitize_input(form_data.get('title', '')).strip(),
        period=period,
        start_date=start_date,
        end_date=end_date,
        filters=filters,
        widgets=widgets,
        format_type=form_data.get('format', 'pdf'),
        include_charts=form_data.get('include_charts') == 'on',
        include_analysis=form_data.get('include_analysis') == 'on',
        branding=branding
    )


def _validate_report_config(config, client_type, permissions):
    """Valida la configuración de un reporte."""
    errors = []
    
    # Validar template
    if config.template not in REPORT_TEMPLATES:
        errors.append('Template de reporte inválido.')
    elif client_type not in REPORT_TEMPLATES[config.template].get('available_for', []):
        errors.append('No tienes permisos para este tipo de reporte.')
    
    # Validar fechas
    if config.start_date > config.end_date:
        errors.append('La fecha de inicio debe ser anterior a la fecha de fin.')
    
    if (config.end_date - config.start_date).days > 365:
        errors.append('El período del reporte no puede ser mayor a un año.')
    
    # Validar formato
    if config.format_type not in REPORTS_CONFIG['SUPPORTED_FORMATS']:
        errors.append('Formato de reporte no soportado.')
    
    # Validar widgets para reportes personalizados
    if config.template == 'custom_report':
        if not config.widgets:
            errors.append('Debe seleccionar al menos un widget para el reporte personalizado.')
        
        for widget in config.widgets:
            if widget not in REPORT_WIDGETS:
                errors.append(f'Widget "{widget}" no válido.')
            elif (REPORT_WIDGETS[widget].get('restricted_to') and 
                  client_type not in REPORT_WIDGETS[widget]['restricted_to']):
                errors.append(f'Sin permisos para el widget "{widget}".')
    
    # Validar título
    if config.title and len(config.title) > 200:
        errors.append('El título del reporte es demasiado largo (máximo 200 caracteres).')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def _generate_report_immediate(config, user_id):
    """Genera un reporte inmediatamente."""
    try:
        # Generar datos del reporte
        report_data = _generate_report_data(config)
        
        # Generar archivo según formato
        if config.format_type == 'excel':
            file_path = generate_custom_report_excel(report_data, config)
            filename = f'{config.template}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif config.format_type == 'csv':
            file_path = _generate_report_csv(report_data, config)
            filename = f'{config.template}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            mimetype = 'text/csv'
        elif config.format_type == 'powerpoint':
            file_path = _generate_report_powerpoint(report_data, config)
            filename = f'{config.template}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pptx'
            mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        else:  # PDF por defecto
            file_path = _generate_report_pdf(report_data, config)
            filename = f'{config.template}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
            mimetype = 'application/pdf'
        
        return {
            'success': True,
            'file_path': file_path,
            'filename': filename,
            'mimetype': mimetype
        }
        
    except Exception as e:
        current_app.logger.error(f"Error generando reporte inmediato: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _generate_report_data(config):
    """Genera los datos para el reporte según la configuración."""
    report_data = {
        'config': config,
        'generated_at': datetime.utcnow(),
        'metadata': {
            'template': config.template,
            'period': f"{config.start_date} to {config.end_date}",
            'filters_applied': len(config.filters) > 0
        }
    }
    
    # Generar datos según template
    if config.template == 'executive_summary':
        report_data.update(_generate_executive_summary_data(config))
    elif config.template == 'impact_analysis':
        report_data.update(_generate_impact_analysis_data(config))
    elif config.template == 'financial_performance':
        report_data.update(_generate_financial_performance_data(config))
    elif config.template == 'operational_report':
        report_data.update(_generate_operational_report_data(config))
    elif config.template == 'comparative_analysis':
        report_data.update(_generate_comparative_analysis_data(config))
    elif config.template == 'custom_report':
        report_data.update(_generate_custom_report_data(config))
    
    return report_data


def _generate_executive_summary_data(config):
    """Genera datos para reporte de resumen ejecutivo."""
    # Métricas clave
    key_metrics = {
        'total_entrepreneurs': Entrepreneur.query.filter_by(is_public=True).count(),
        'active_projects': Project.query.filter_by(status='active', is_public=True).count(),
        'jobs_created': _get_jobs_created_in_period(config.start_date, config.end_date),
        'revenue_generated': _get_revenue_generated_in_period(config.start_date, config.end_date)
    }
    
    # Tendencias
    trends = _get_key_metrics_trends(config.start_date, config.end_date)
    
    # Highlights
    highlights = _get_period_highlights(config.start_date, config.end_date)
    
    return {
        'key_metrics': key_metrics,
        'trends': trends,
        'highlights': highlights,
        'overview': _get_ecosystem_overview_for_period(config.start_date, config.end_date)
    }


def _generate_report_pdf(report_data, config):
    """Genera reporte en formato PDF."""
    if config.template == 'executive_summary':
        return generate_executive_summary_pdf(report_data)
    elif config.template == 'impact_analysis':
        return generate_impact_analysis_pdf(report_data)
    elif config.template == 'financial_performance':
        return generate_financial_report_pdf(report_data)
    elif config.template == 'operational_report':
        return generate_operational_report_pdf(report_data)
    else:
        return generate_custom_report_pdf(report_data, config)


def _check_user_report_limits(user_id):
    """Verifica límites de reportes del usuario."""
    # Contar reportes del último mes
    month_ago = datetime.utcnow() - timedelta(days=30)
    recent_reports_count = _get_user_reports_count_since(user_id, month_ago)
    
    return recent_reports_count < REPORTS_CONFIG['MAX_REPORTS_PER_USER']


def _get_user_recent_reports(user_id, limit=10):
    """Obtiene reportes recientes del usuario."""
    # En un sistema real, esto vendría de una tabla de reportes
    return [
        {
            'id': f'report_{i}',
            'title': f'Reporte {i}',
            'template': 'executive_summary',
            'format': 'pdf',
            'created_at': datetime.utcnow() - timedelta(days=i),
            'file_size': 1024 * 1024 * 2,  # 2MB
            'download_count': i
        }
        for i in range(1, min(limit + 1, 6))
    ]


def _get_user_scheduled_reports(user_id):
    """Obtiene reportes programados del usuario."""
    # Datos de ejemplo
    return [
        {
            'id': 'scheduled_1',
            'title': 'Reporte Mensual de Impacto',
            'template': 'impact_analysis',
            'frequency': 'monthly',
            'next_execution': datetime.utcnow() + timedelta(days=5),
            'recipients': ['stakeholder@example.com'],
            'status': 'active'
        }
    ]


def _get_report_filter_options(permissions):
    """Obtiene opciones disponibles para filtros de reportes."""
    options = {}
    
    # Organizaciones
    organizations = Organization.query.filter_by(is_active=True).all()
    options['organizations'] = [{'id': o.id, 'name': o.name} for o in organizations]
    
    # Programas
    programs = Program.query.filter_by(status='active').all()
    options['programs'] = [{'id': p.id, 'name': p.name} for p in programs]
    
    # Ubicaciones
    locations = (
        db.session.query(Entrepreneur.location)
        .filter(Entrepreneur.is_public == True, Entrepreneur.location.isnot(None))
        .distinct()
        .all()
    )
    options['locations'] = [l[0] for l in locations]
    
    # Industrias
    industries = (
        db.session.query(Entrepreneur.industry)
        .filter(Entrepreneur.is_public == True, Entrepreneur.industry.isnot(None))
        .distinct()
        .all()
    )
    options['industries'] = [i[0] for i in industries]
    
    return options


def _get_period_options():
    """Obtiene opciones de períodos disponibles."""
    return [
        ('current_week', 'Semana Actual'),
        ('current_month', 'Mes Actual'),
        ('current_quarter', 'Trimestre Actual'),
        ('current_year', 'Año Actual'),
        ('last_month', 'Mes Pasado'),
        ('last_quarter', 'Trimestre Pasado'),
        ('last_year', 'Año Pasado'),
        ('custom', 'Período Personalizado')
    ]


def _get_format_options(permissions):
    """Obtiene formatos disponibles según permisos."""
    formats = [
        ('pdf', 'PDF - Documento'),
        ('excel', 'Excel - Hoja de Cálculo')
    ]
    
    if permissions.get('can_access_detailed_analytics'):
        formats.extend([
            ('csv', 'CSV - Datos'),
            ('powerpoint', 'PowerPoint - Presentación')
        ])
    
    return formats


def _is_valid_email(email):
    """Valida formato de email."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# Funciones auxiliares para métricas específicas

def _get_jobs_created_in_period(start_date, end_date):
    """Obtiene empleos creados en el período."""
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


def _get_revenue_generated_in_period(start_date, end_date):
    """Obtiene ingresos generados en el período."""
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


# Funciones placeholder para funcionalidades futuras

def _save_report_record(config, user_id, file_path):
    """Guarda registro del reporte en base de datos."""
    # Implementar guardado en tabla de reportes
    pass


def _schedule_report_generation_and_email(config, user_id, recipients):
    """Programa generación y envío de reporte por email."""
    # Implementar con Celery o sistema de tareas asíncronas
    return {'success': True, 'task_id': str(uuid.uuid4())}


def _create_scheduled_report(config, schedule_config, user_id):
    """Crea un reporte programado recurrente."""
    # Implementar creación de programación
    return True


def _extract_schedule_config_from_form(form_data):
    """Extrae configuración de programación del formulario."""
    return {
        'frequency': form_data.get('frequency', 'monthly'),
        'day_of_month': form_data.get('day_of_month', 1),
        'time': form_data.get('time', '09:00'),
        'recipients': form_data.get('schedule_recipients', '').split(','),
        'auto_send': form_data.get('auto_send') == 'on'
    }


def _validate_schedule_config(schedule_config, user_id):
    """Valida configuración de programación."""
    # Implementar validaciones de programación
    return True


# Manejadores de errores específicos

@client_reports_bp.errorhandler(403)
def reports_forbidden(error):
    """Maneja errores de permisos en reportes."""
    flash('No tienes permisos para acceder a esta funcionalidad de reportes.', 'error')
    return redirect(url_for('client_reports.index'))


@client_reports_bp.errorhandler(413)
def reports_file_too_large(error):
    """Maneja errores de archivo demasiado grande."""
    flash(f'El reporte generado es demasiado grande. Máximo: {REPORTS_CONFIG["MAX_REPORT_SIZE_MB"]}MB', 'error')
    return redirect(url_for('client_reports.index'))


@client_reports_bp.errorhandler(500)
def reports_internal_error(error):
    """Maneja errores internos en reportes."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en reportes: {str(error)}")
    flash('Error interno al procesar reportes. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('client.index'))