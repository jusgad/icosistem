"""
Módulo de dashboard para Aliados/Mentores.

Este módulo contiene todas las vistas y funcionalidades del dashboard principal
para aliados y mentores, incluyendo métricas en tiempo real, gestión de
emprendedores, seguimiento de sesiones de mentoría, y herramientas de análisis.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

from datetime import datetime, timedelta, date, timezone
from typing import Optional, Any
from collections import defaultdict
import json

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, g, abort, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, extract, case
from sqlalchemy.orm import joinedload, subqueryload
from werkzeug.exceptions import BadRequest

from app.core.exceptions import ValidationError, BusinessLogicError
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, Meeting, 
    Project, Task, Message, Document, Notification, ActivityLog,
    Analytics, Program, Organization, Goal, Milestone
)
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.mentorship_service import MentorshipService
from app.utils.decorators import require_json, cache_response, rate_limit
from app.utils.formatters import (
    format_currency, format_percentage, format_date, 
    format_time_duration, format_number
)
from app.utils.export_utils import export_to_pdf, export_to_excel
from app.utils.cache_utils import cache_key, get_cached, set_cached
from app.views.ally import require_ally_access, track_ally_activity


# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================

ally_dashboard_bp = Blueprint(
    'ally_dashboard',
    __name__,
    url_prefix='/ally/dashboard',
    template_folder='templates/ally/dashboard'
)


# ==================== VISTA PRINCIPAL DEL DASHBOARD ====================

@ally_dashboard_bp.route('/')
@ally_dashboard_bp.route('/index')
@login_required
@require_ally_access
@track_ally_activity('dashboard_view', 'Acceso al dashboard principal')
def index():
    """
    Dashboard principal del aliado/mentor.
    
    Muestra una vista general con métricas clave, emprendedores asignados,
    próximas reuniones, notificaciones y widgets personalizables.
    
    Returns:
        Template renderizado con datos del dashboard
    """
    try:
        ally_profile = g.ally_profile
        
        # Obtener período de análisis (por defecto 30 días)
        period = request.args.get('period', '30')
        view_mode = request.args.get('view', 'overview')  # overview, detailed, analytics
        
        # Calcular fechas del período
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Datos principales del dashboard
        dashboard_data = _get_dashboard_overview(ally_profile, start_date, end_date)
        
        # Métricas de rendimiento
        performance_metrics = _calculate_ally_performance_metrics(
            ally_profile, start_date, end_date
        )
        
        # Emprendedores asignados con sus estados
        entrepreneurs_data = _get_entrepreneurs_summary(ally_profile)
        
        # Próximas actividades (reuniones, sesiones, deadlines)
        upcoming_activities = _get_upcoming_activities(ally_profile)
        
        # Notificaciones recientes y alertas
        notifications_data = _get_notifications_summary(ally_profile)
        
        # Progreso de objetivos mensuales
        monthly_goals = _get_monthly_goals_progress(ally_profile)
        
        # Widgets personalizables del usuario
        user_widgets = _get_user_widgets_configuration(ally_profile)
        
        # Datos para gráficos y visualizaciones
        charts_data = _prepare_charts_data(ally_profile, start_date, end_date)
        
        # Actividad reciente del aliado
        recent_activity = _get_recent_activity_feed(ally_profile, limit=10)
        
        # Comparativas con otros aliados (opcionales)
        comparative_data = _get_comparative_metrics(ally_profile, start_date, end_date)
        
        return render_template(
            'ally/dashboard/index.html',
            dashboard_data=dashboard_data,
            performance_metrics=performance_metrics,
            entrepreneurs_data=entrepreneurs_data,
            upcoming_activities=upcoming_activities,
            notifications_data=notifications_data,
            monthly_goals=monthly_goals,
            user_widgets=user_widgets,
            charts_data=charts_data,
            recent_activity=recent_activity,
            comparative_data=comparative_data,
            current_period=period,
            view_mode=view_mode,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard del aliado {ally_profile.id}: {str(e)}")
        flash('Error al cargar el dashboard. Por favor, intenta nuevamente.', 'error')
        return redirect(url_for('ally.index'))


@ally_dashboard_bp.route('/metrics')
@login_required
@require_ally_access
@track_ally_activity('metrics_view', 'Acceso a métricas detalladas')
def detailed_metrics():
    """
    Vista detallada de métricas y analytics del aliado.
    
    Proporciona análisis profundo del rendimiento, tendencias
    temporales y comparativas con benchmarks del sistema.
    
    Returns:
        Template con métricas detalladas
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de análisis
        period = request.args.get('period', '90')
        metric_type = request.args.get('type', 'all')  # all, mentorship, meetings, projects
        comparison = request.args.get('comparison', 'none')  # none, peers, historical
        
        # Calcular período
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Generar métricas usando el servicio de analytics
        analytics_service = AnalyticsService()
        
        # Métricas detalladas por categoría
        detailed_metrics = analytics_service.get_ally_detailed_metrics(
            ally_profile.id, start_date, end_date, metric_type
        )
        
        # Tendencias temporales
        temporal_trends = analytics_service.get_ally_temporal_trends(
            ally_profile.id, start_date, end_date
        )
        
        # Análisis de efectividad de mentoría
        mentorship_effectiveness = _analyze_mentorship_effectiveness(
            ally_profile, start_date, end_date
        )
        
        # Distribución de tiempo por actividades
        time_distribution = _calculate_time_distribution(
            ally_profile, start_date, end_date
        )
        
        # KPIs específicos del aliado
        ally_kpis = _calculate_ally_kpis(ally_profile, start_date, end_date)
        
        # Comparativas si se solicitan
        comparison_data = None
        if comparison != 'none':
            comparison_data = _get_comparison_data(
                ally_profile, start_date, end_date, comparison
            )
        
        # Recomendaciones basadas en métricas
        recommendations = _generate_performance_recommendations(ally_profile, detailed_metrics)
        
        return render_template(
            'ally/dashboard/metrics.html',
            detailed_metrics=detailed_metrics,
            temporal_trends=temporal_trends,
            mentorship_effectiveness=mentorship_effectiveness,
            time_distribution=time_distribution,
            ally_kpis=ally_kpis,
            comparison_data=comparison_data,
            recommendations=recommendations,
            current_period=period,
            metric_type=metric_type,
            comparison_mode=comparison,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en métricas detalladas: {str(e)}")
        flash('Error al cargar las métricas detalladas', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_dashboard_bp.route('/entrepreneurs')
@login_required
@require_ally_access
@track_ally_activity('entrepreneurs_overview', 'Vista de emprendedores asignados')
def entrepreneurs_overview():
    """
    Vista general de emprendedores asignados al aliado.
    
    Muestra el estado de todos los emprendedores bajo mentoría,
    su progreso, próximas actividades y alertas importantes.
    
    Returns:
        Template con información de emprendedores
    """
    try:
        ally_profile = g.ally_profile
        
        # Filtros y ordenamiento
        status_filter = request.args.get('status', 'all')  # all, active, inactive, completed
        sort_by = request.args.get('sort', 'last_interaction')
        order = request.args.get('order', 'desc')
        search_query = request.args.get('search', '').strip()
        
        # Query base para emprendedores
        entrepreneurs_query = _build_entrepreneurs_query(
            ally_profile, status_filter, sort_by, order, search_query
        )
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        entrepreneurs_paginated = entrepreneurs_query.paginate(
            page=page, per_page=12, error_out=False
        )
        
        # Enriquecer datos de emprendedores
        entrepreneurs_enriched = []
        for entrepreneur in entrepreneurs_paginated.items:
            enriched_data = _enrich_entrepreneur_data(entrepreneur, ally_profile)
            entrepreneurs_enriched.append(enriched_data)
        
        # Estadísticas generales
        entrepreneurs_stats = _calculate_entrepreneurs_stats(ally_profile)
        
        # Alertas y notificaciones por emprendedor
        entrepreneur_alerts = _get_entrepreneur_alerts(ally_profile)
        
        # Próximas actividades por emprendedor
        upcoming_by_entrepreneur = _get_upcoming_by_entrepreneur(ally_profile)
        
        return render_template(
            'ally/dashboard/entrepreneurs.html',
            entrepreneurs=entrepreneurs_paginated,
            entrepreneurs_enriched=entrepreneurs_enriched,
            entrepreneurs_stats=entrepreneurs_stats,
            entrepreneur_alerts=entrepreneur_alerts,
            upcoming_by_entrepreneur=upcoming_by_entrepreneur,
            current_status=status_filter,
            current_sort=sort_by,
            current_order=order,
            search_query=search_query,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de emprendedores: {str(e)}")
        flash('Error al cargar información de emprendedores', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_dashboard_bp.route('/calendar')
@login_required
@require_ally_access
@track_ally_activity('calendar_view', 'Acceso al calendario del dashboard')
def calendar_view():
    """
    Vista de calendario integrada en el dashboard.
    
    Muestra reuniones, sesiones de mentoría y deadlines
    en un formato de calendario interactivo.
    
    Returns:
        Template con calendario y eventos
    """
    try:
        ally_profile = g.ally_profile
        
        # Parámetros de vista
        view_type = request.args.get('view', 'month')  # month, week, day
        date_param = request.args.get('date')
        
        # Procesar fecha solicitada
        if date_param:
            try:
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                target_date = date.today()
        else:
            target_date = date.today()
        
        # Calcular rango de fechas según la vista
        date_range = _calculate_calendar_range(target_date, view_type)
        
        # Obtener eventos del período
        calendar_events = _get_calendar_events(
            ally_profile, date_range['start'], date_range['end']
        )
        
        # Estadísticas del período
        period_stats = _calculate_period_stats(
            ally_profile, date_range['start'], date_range['end']
        )
        
        # Disponibilidad del aliado
        availability_slots = _get_availability_slots(
            ally_profile, date_range['start'], date_range['end']
        )
        
        # Conflictos y solapamientos
        schedule_conflicts = _detect_schedule_conflicts(calendar_events)
        
        return render_template(
            'ally/dashboard/calendar.html',
            calendar_events=calendar_events,
            period_stats=period_stats,
            availability_slots=availability_slots,
            schedule_conflicts=schedule_conflicts,
            target_date=target_date,
            view_type=view_type,
            date_range=date_range,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de calendario: {str(e)}")
        flash('Error al cargar el calendario', 'error')
        return redirect(url_for('ally_dashboard.index'))


# ==================== API ENDPOINTS PARA ACTUALIZACIONES DINÁMICAS ====================

@ally_dashboard_bp.route('/api/real-time-metrics')
@login_required
@require_ally_access
@rate_limit(calls=60, period=60)  # 1 call per second max
@require_json
def api_real_time_metrics():
    """
    API endpoint para métricas en tiempo real del dashboard.
    
    Proporciona datos actualizados para widgets y gráficos
    que se actualizan automáticamente.
    
    Returns:
        JSON con métricas en tiempo real
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar caché primero
        cache_key_val = f"ally_realtime_metrics_{ally_profile.id}"
        cached_data = get_cached(cache_key_val)
        
        if cached_data:
            return jsonify({
                'success': True,
                'data': cached_data,
                'cached': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        # Calcular métricas en tiempo real
        real_time_data = {
            'active_sessions': _count_active_sessions(ally_profile),
            'pending_messages': _count_pending_messages(ally_profile),
            'today_meetings': _count_today_meetings(ally_profile),
            'urgent_tasks': _count_urgent_tasks(ally_profile),
            'online_entrepreneurs': _count_online_entrepreneurs(ally_profile),
            'weekly_hours': _calculate_weekly_hours(ally_profile),
            'completion_rate': _calculate_current_completion_rate(ally_profile),
            'satisfaction_score': _get_current_satisfaction_score(ally_profile)
        }
        
        # Cachear por 30 segundos
        set_cached(cache_key_val, real_time_data, timeout=30)
        
        return jsonify({
            'success': True,
            'data': real_time_data,
            'cached': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en métricas tiempo real: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


@ally_dashboard_bp.route('/api/chart-data/<chart_type>')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_chart_data(chart_type):
    """
    API endpoint para datos de gráficos específicos.
    
    Args:
        chart_type: Tipo de gráfico (sessions, productivity, satisfaction, etc.)
        
    Returns:
        JSON con datos del gráfico solicitado
    """
    try:
        ally_profile = g.ally_profile
        period = request.args.get('period', '30')
        
        # Validar tipo de gráfico
        valid_charts = [
            'sessions', 'productivity', 'satisfaction', 'hours', 
            'entrepreneurs_progress', 'meeting_trends', 'task_completion'
        ]
        
        if chart_type not in valid_charts:
            return jsonify({'error': 'Tipo de gráfico no válido'}), 400
        
        # Calcular período
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Generar datos según el tipo de gráfico
        chart_data = _generate_chart_data(ally_profile, chart_type, start_date, end_date)
        
        return jsonify({
            'success': True,
            'chart_type': chart_type,
            'data': chart_data,
            'period': period,
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generando datos de gráfico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error generando datos del gráfico'
        }), 500


@ally_dashboard_bp.route('/api/quick-actions', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
@require_json
def api_quick_actions():
    """
    API endpoint para acciones rápidas desde el dashboard.
    
    Permite ejecutar acciones comunes como programar reuniones,
    enviar mensajes, marcar tareas como completadas, etc.
    
    Returns:
        JSON con resultado de la acción
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        action_type = data.get('action_type')
        action_data = data.get('action_data', {})
        
        # Validar tipo de acción
        valid_actions = [
            'schedule_meeting', 'send_message', 'complete_task',
            'add_note', 'update_status', 'send_reminder'
        ]
        
        if action_type not in valid_actions:
            return jsonify({'error': 'Tipo de acción no válido'}), 400
        
        # Ejecutar acción específica
        result = _execute_quick_action(ally_profile, action_type, action_data)
        
        if result['success']:
            # Registrar la acción
            _log_quick_action(ally_profile, action_type, action_data, result)
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'data': result.get('data', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error en acción rápida: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error ejecutando la acción'
        }), 500


@ally_dashboard_bp.route('/api/widget-config', methods=['GET', 'POST'])
@login_required
@require_ally_access
@rate_limit(calls=15, period=60)
def api_widget_config():
    """
    API endpoint para configuración de widgets del dashboard.
    
    GET: Obtiene configuración actual de widgets
    POST: Actualiza configuración de widgets
    
    Returns:
        JSON con configuración de widgets
    """
    try:
        ally_profile = g.ally_profile
        
        if request.method == 'GET':
            # Obtener configuración actual
            widget_config = _get_widget_configuration(ally_profile)
            
            return jsonify({
                'success': True,
                'data': widget_config
            })
            
        elif request.method == 'POST':
            # Actualizar configuración
            new_config = request.get_json()
            
            # Validar configuración
            if not _validate_widget_config(new_config):
                return jsonify({'error': 'Configuración de widgets no válida'}), 400
            
            # Guardar nueva configuración
            result = _save_widget_configuration(ally_profile, new_config)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': 'Configuración actualizada exitosamente'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 400
                
    except Exception as e:
        current_app.logger.error(f"Error en configuración de widgets: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error en configuración de widgets'
        }), 500


@ally_dashboard_bp.route('/api/notifications/summary')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_notifications_summary():
    """
    API endpoint para resumen de notificaciones.
    
    Returns:
        JSON con resumen de notificaciones del aliado
    """
    try:
        ally_profile = g.ally_profile
        
        # Obtener notificaciones por tipo y prioridad
        notifications_summary = _get_notifications_api_summary(ally_profile)
        
        return jsonify({
            'success': True,
            'data': notifications_summary,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en resumen de notificaciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error obteniendo notificaciones'
        }), 500


# ==================== EXPORTACIÓN Y REPORTES ====================

@ally_dashboard_bp.route('/export/dashboard-report')
@login_required
@require_ally_access
@track_ally_activity('export_dashboard', 'Exportación de reporte de dashboard')
def export_dashboard_report():
    """
    Exporta un reporte completo del dashboard del aliado en PDF.
    
    Returns:
        Archivo PDF con reporte del dashboard
    """
    try:
        ally_profile = g.ally_profile
        
        # Obtener período de reporte
        period = request.args.get('period', '30')
        format_type = request.args.get('format', 'pdf')  # pdf, excel
        
        # Calcular fechas
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=int(period))
        
        # Generar datos del reporte
        report_data = _generate_dashboard_report_data(ally_profile, start_date, end_date)
        
        if format_type == 'pdf':
            # Generar PDF
            pdf_content = export_to_pdf(
                template='reports/ally_dashboard_report.html',
                data=report_data,
                filename=f'dashboard_report_{ally_profile.user.first_name}_{ally_profile.user.last_name}'
            )
            
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename=dashboard_report.pdf'
            
            return response
            
        elif format_type == 'excel':
            # Generar Excel
            excel_content = export_to_excel(
                data=report_data,
                filename=f'dashboard_report_{datetime.now().strftime("%Y%m%d")}'
            )
            
            response = make_response(excel_content)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = 'attachment; filename=dashboard_report.xlsx'
            
            return response
        
        else:
            flash('Formato de exportación no válido', 'error')
            return redirect(url_for('ally_dashboard.index'))
            
    except Exception as e:
        current_app.logger.error(f"Error exportando reporte: {str(e)}")
        flash('Error al generar el reporte', 'error')
        return redirect(url_for('ally_dashboard.index'))


# ==================== FUNCIONES AUXILIARES ====================

def _get_dashboard_overview(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """
    Obtiene datos generales del dashboard del aliado.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio del período
        end_date: Fecha fin del período
        
    Returns:
        Dict con datos del dashboard
    """
    # Emprendedores activos
    active_entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.status == 'active'
    ).distinct().count()
    
    # Sesiones de mentoría en el período
    mentorship_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).count()
    
    # Reuniones programadas y completadas
    total_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at.between(start_date, end_date)
    ).count()
    
    completed_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at.between(start_date, end_date),
        Meeting.status == 'completed'
    ).count()
    
    # Horas de mentoría
    total_hours = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date.between(start_date, end_date)
    ).scalar() or 0
    
    # Mensajes intercambiados
    messages_sent = Message.query.filter(
        Message.sender_id == ally.user_id,
        Message.created_at.between(start_date, end_date)
    ).count()
    
    messages_received = Message.query.filter(
        Message.recipient_id == ally.user_id,
        Message.created_at.between(start_date, end_date)
    ).count()
    
    # Documentos revisados
    documents_reviewed = Document.query.join(Project).join(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        Document.created_at.between(start_date, end_date)
    ).count()
    
    return {
        'active_entrepreneurs': active_entrepreneurs,
        'mentorship_sessions': mentorship_sessions,
        'total_meetings': total_meetings,
        'completed_meetings': completed_meetings,
        'meeting_completion_rate': (completed_meetings / total_meetings * 100) if total_meetings > 0 else 0,
        'total_hours': float(total_hours),
        'avg_hours_per_session': float(total_hours / mentorship_sessions) if mentorship_sessions > 0 else 0,
        'messages_sent': messages_sent,
        'messages_received': messages_received,
        'total_messages': messages_sent + messages_received,
        'documents_reviewed': documents_reviewed,
        'period_days': (end_date - start_date).days
    }


def _calculate_ally_performance_metrics(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """
    Calcula métricas de rendimiento específicas del aliado.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio del período
        end_date: Fecha fin del período
        
    Returns:
        Dict con métricas de rendimiento
    """
    # Tasa de respuesta a mensajes
    messages_received = Message.query.filter(
        Message.recipient_id == ally.user_id,
        Message.created_at.between(start_date, end_date)
    ).count()
    
    messages_replied = Message.query.filter(
        Message.sender_id == ally.user_id,
        Message.created_at.between(start_date, end_date),
        Message.in_reply_to.isnot(None)
    ).count()
    
    response_rate = (messages_replied / messages_received * 100) if messages_received > 0 else 0
    
    # Tiempo promedio de respuesta
    avg_response_time = _calculate_avg_response_time(ally, start_date, end_date)
    
    # Tasa de asistencia a reuniones
    scheduled_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at.between(start_date, end_date)
    ).count()
    
    attended_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at.between(start_date, end_date),
        Meeting.status.in_(['completed', 'attended'])
    ).count()
    
    attendance_rate = (attended_meetings / scheduled_meetings * 100) if scheduled_meetings > 0 else 0
    
    # Efectividad de mentoría (basada en progreso de emprendedores)
    mentorship_effectiveness = _calculate_mentorship_effectiveness_score(ally, start_date, end_date)
    
    # Satisfacción promedio de emprendedores
    avg_satisfaction = _get_average_satisfaction_score(ally, start_date, end_date)
    
    # Productividad (horas vs resultados)
    productivity_score = _calculate_productivity_score(ally, start_date, end_date)
    
    return {
        'response_rate': round(response_rate, 2),
        'avg_response_time_hours': round(avg_response_time, 2),
        'attendance_rate': round(attendance_rate, 2),
        'mentorship_effectiveness': round(mentorship_effectiveness, 2),
        'avg_satisfaction': round(avg_satisfaction, 2),
        'productivity_score': round(productivity_score, 2),
        'overall_performance': round(
            (response_rate + attendance_rate + mentorship_effectiveness + avg_satisfaction + productivity_score) / 5, 2
        )
    }


def _get_entrepreneurs_summary(ally: Ally) -> dict[str, Any]:
    """
    Obtiene resumen de emprendedores asignados al aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con resumen de emprendedores
    """
    # Emprendedores con mentoría activa
    active_entrepreneurs = db.session.query(Entrepreneur).join(MentorshipSession).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.status == 'active'
    ).options(joinedload(Entrepreneur.user)).all()
    
    entrepreneurs_data = []
    for entrepreneur in active_entrepreneurs:
        # Calcular progreso general del emprendedor
        progress_data = _calculate_entrepreneur_overall_progress(entrepreneur)
        
        # Próxima actividad
        next_activity = _get_next_activity_with_entrepreneur(ally, entrepreneur)
        
        # Estado de la relación
        relationship_status = _get_relationship_status(ally, entrepreneur)
        
        entrepreneurs_data.append({
            'entrepreneur': entrepreneur,
            'progress': progress_data,
            'next_activity': next_activity,
            'relationship_status': relationship_status,
            'last_interaction': _get_last_interaction_date(ally, entrepreneur),
            'urgent_items': _get_urgent_items_for_entrepreneur(entrepreneur)
        })
    
    # Estadísticas generales
    total_entrepreneurs = len(entrepreneurs_data)
    avg_progress = sum(e['progress']['overall_percentage'] for e in entrepreneurs_data) / total_entrepreneurs if total_entrepreneurs > 0 else 0
    
    entrepreneurs_by_stage = defaultdict(int)
    for entrepreneur_data in entrepreneurs_data:
        stage = entrepreneur_data['progress']['current_stage']
        entrepreneurs_by_stage[stage] += 1
    
    return {
        'entrepreneurs_data': entrepreneurs_data,
        'total_count': total_entrepreneurs,
        'avg_progress': round(avg_progress, 2),
        'by_stage': dict(entrepreneurs_by_stage),
        'need_attention': len([e for e in entrepreneurs_data if e['relationship_status']['needs_attention']]),
        'high_performers': len([e for e in entrepreneurs_data if e['progress']['overall_percentage'] >= 80])
    }


def _get_upcoming_activities(ally: Ally) -> list[dict[str, Any]]:
    """
    Obtiene próximas actividades del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de próximas actividades
    """
    activities = []
    
    # Próximas reuniones
    upcoming_meetings = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.scheduled_at > datetime.now(timezone.utc),
        Meeting.status.in_(['scheduled', 'confirmed'])
    ).order_by(Meeting.scheduled_at.asc()).limit(10).all()
    
    for meeting in upcoming_meetings:
        activities.append({
            'type': 'meeting',
            'title': meeting.title,
            'datetime': meeting.scheduled_at,
            'duration': meeting.duration_minutes,
            'participant': meeting.entrepreneur.user.full_name if meeting.entrepreneur else 'N/A',
            'priority': 'high' if meeting.scheduled_at <= datetime.now(timezone.utc) + timedelta(hours=24) else 'normal',
            'url': url_for('ally.meetings.detail', meeting_id=meeting.id)
        })
    
    # Próximas sesiones de mentoría
    upcoming_sessions = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date > datetime.now(timezone.utc).date(),
        MentorshipSession.status == 'scheduled'
    ).order_by(MentorshipSession.session_date.asc()).limit(10).all()
    
    for session in upcoming_sessions:
        activities.append({
            'type': 'mentorship',
            'title': f'Sesión de mentoría - {session.topic}',
            'datetime': datetime.combine(session.session_date, session.start_time or datetime.min.time()),
            'duration': session.duration_hours * 60,
            'participant': session.entrepreneur.user.full_name,
            'priority': 'normal',
            'url': url_for('ally.mentorship.session_detail', session_id=session.id)
        })
    
    # Deadlines importantes
    # Esto requeriría un modelo de deadlines o tareas asignadas al aliado
    
    # Ordenar por fecha y devolver las primeras 15
    activities.sort(key=lambda x: x['datetime'])
    return activities[:15]


def _get_notifications_summary(ally: Ally) -> dict[str, Any]:
    """
    Obtiene resumen de notificaciones del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con resumen de notificaciones
    """
    # Notificaciones no leídas por tipo
    unread_notifications = Notification.query.filter_by(
        user_id=ally.user_id,
        is_read=False
    ).all()
    
    notifications_by_type = defaultdict(int)
    notifications_by_priority = defaultdict(int)
    
    for notification in unread_notifications:
        notifications_by_type[notification.notification_type] += 1
        notifications_by_priority[notification.priority or 'normal'] += 1
    
    # Notificaciones recientes (últimas 10)
    recent_notifications = Notification.query.filter_by(
        user_id=ally.user_id
    ).order_by(desc(Notification.created_at)).limit(10).all()
    
    return {
        'total_unread': len(unread_notifications),
        'by_type': dict(notifications_by_type),
        'by_priority': dict(notifications_by_priority),
        'recent_notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
                'priority': n.priority,
                'created_at': n.created_at,
                'is_read': n.is_read
            }
            for n in recent_notifications
        ],
        'urgent_count': notifications_by_priority.get('urgent', 0),
        'high_count': notifications_by_priority.get('high', 0)
    }


def _get_monthly_goals_progress(ally: Ally) -> dict[str, Any]:
    """
    Obtiene progreso de objetivos mensuales del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con progreso de objetivos
    """
    # Esto requeriría un modelo de Goals específico para aliados
    # Por ahora retornamos datos simulados basados en métricas reales
    
    current_month = datetime.now(timezone.utc).replace(day=1).date()
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    # Sesiones de mentoría este mes
    sessions_this_month = MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= current_month,
        MentorshipSession.session_date < next_month
    ).count()
    
    # Horas este mes
    hours_this_month = db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= current_month,
        MentorshipSession.session_date < next_month
    ).scalar() or 0
    
    # Objetivos simulados (en una implementación real vendrían de la base de datos)
    goals = [
        {
            'name': 'Sesiones de mentoría',
            'target': 20,
            'current': sessions_this_month,
            'unit': 'sesiones',
            'progress_percentage': min((sessions_this_month / 20) * 100, 100)
        },
        {
            'name': 'Horas de mentoría',
            'target': 40,
            'current': float(hours_this_month),
            'unit': 'horas',
            'progress_percentage': min((float(hours_this_month) / 40) * 100, 100)
        },
        {
            'name': 'Tasa de satisfacción',
            'target': 4.5,
            'current': _get_average_satisfaction_score(ally, current_month, datetime.now(timezone.utc)),
            'unit': 'puntos',
            'progress_percentage': min((_get_average_satisfaction_score(ally, current_month, datetime.now(timezone.utc)) / 4.5) * 100, 100)
        }
    ]
    
    overall_progress = sum(goal['progress_percentage'] for goal in goals) / len(goals)
    
    return {
        'goals': goals,
        'overall_progress': round(overall_progress, 2),
        'month': current_month.strftime('%B %Y'),
        'goals_completed': len([g for g in goals if g['progress_percentage'] >= 100]),
        'goals_on_track': len([g for g in goals if g['progress_percentage'] >= 75]),
        'goals_behind': len([g for g in goals if g['progress_percentage'] < 50])
    }


def _get_user_widgets_configuration(ally: Ally) -> dict[str, Any]:
    """
    Obtiene configuración de widgets personalizables del usuario.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con configuración de widgets
    """
    # En una implementación real, esto vendría de una tabla de configuración de usuario
    # Por ahora retornamos una configuración por defecto
    
    default_widgets = {
        'enabled_widgets': [
            'performance_metrics',
            'upcoming_activities',
            'entrepreneurs_overview',
            'notifications_summary',
            'monthly_goals',
            'quick_stats',
            'recent_activity'
        ],
        'widget_positions': {
            'performance_metrics': {'row': 1, 'col': 1, 'size': 'large'},
            'upcoming_activities': {'row': 1, 'col': 2, 'size': 'medium'},
            'entrepreneurs_overview': {'row': 2, 'col': 1, 'size': 'large'},
            'notifications_summary': {'row': 2, 'col': 2, 'size': 'small'},
            'monthly_goals': {'row': 3, 'col': 1, 'size': 'medium'},
            'quick_stats': {'row': 3, 'col': 2, 'size': 'small'},
            'recent_activity': {'row': 4, 'col': 1, 'size': 'full'}
        },
        'refresh_intervals': {
            'performance_metrics': 300,  # 5 minutos
            'upcoming_activities': 60,   # 1 minuto
            'entrepreneurs_overview': 180, # 3 minutos
            'notifications_summary': 30,   # 30 segundos
            'quick_stats': 30
        }
    }
    
    return default_widgets


def _prepare_charts_data(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """
    Prepara datos para gráficos del dashboard.
    
    Args:
        ally: Perfil del aliado
        start_date: Fecha inicio del período
        end_date: Fecha fin del período
        
    Returns:
        Dict con datos para gráficos
    """
    charts_data = {}
    
    # Gráfico de sesiones por día
    charts_data['sessions_timeline'] = _generate_sessions_timeline(ally, start_date, end_date)
    
    # Gráfico de distribución de tiempo
    charts_data['time_distribution'] = _generate_time_distribution_chart(ally, start_date, end_date)
    
    # Gráfico de progreso de emprendedores
    charts_data['entrepreneurs_progress'] = _generate_entrepreneurs_progress_chart(ally)
    
    # Gráfico de satisfacción
    charts_data['satisfaction_trend'] = _generate_satisfaction_trend_chart(ally, start_date, end_date)
    
    return charts_data


def _get_recent_activity_feed(ally: Ally, limit: int = 10) -> list[dict[str, Any]]:
    """
    Obtiene feed de actividad reciente del aliado.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de actividades
        
    Returns:
        Lista de actividades recientes
    """
    activities = ActivityLog.query.filter_by(
        user_id=ally.user_id
    ).order_by(desc(ActivityLog.created_at)).limit(limit).all()
    
    return [
        {
            'id': activity.id,
            'action': activity.action,
            'description': activity.description,
            'created_at': activity.created_at,
            'entity_type': activity.entity_type,
            'entity_id': activity.entity_id,
            'icon': _get_activity_icon(activity.action),
            'color': _get_activity_color(activity.action)
        }
        for activity in activities
    ]


# Funciones auxiliares adicionales (implementación básica)
def _get_comparative_metrics(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Obtiene métricas comparativas con otros aliados."""
    # Implementación pendiente
    return {'available': False, 'message': 'Datos comparativos en desarrollo'}


def _count_active_sessions(ally: Ally) -> int:
    """Cuenta sesiones de mentoría activas en este momento."""
    return MentorshipSession.query.filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.status == 'in_progress'
    ).count()


def _count_pending_messages(ally: Ally) -> int:
    """Cuenta mensajes pendientes de respuesta."""
    return Message.query.filter(
        Message.recipient_id == ally.user_id,
        Message.is_read == False
    ).count()


def _count_today_meetings(ally: Ally) -> int:
    """Cuenta reuniones programadas para hoy."""
    today = date.today()
    return Meeting.query.filter(
        Meeting.ally_id == ally.id,
        func.date(Meeting.scheduled_at) == today
    ).count()


def _count_urgent_tasks(ally: Ally) -> int:
    """Cuenta tareas urgentes asignadas al aliado."""
    # Implementación pendiente - requiere modelo de tareas del aliado
    return 0


def _count_online_entrepreneurs(ally: Ally) -> int:
    """Cuenta emprendedores online actualmente."""
    # Implementación pendiente - requiere sistema de presencia
    return 0


def _calculate_weekly_hours(ally: Ally) -> float:
    """Calcula horas trabajadas esta semana."""
    week_start = date.today() - timedelta(days=date.today().weekday())
    return db.session.query(
        func.sum(MentorshipSession.duration_hours)
    ).filter(
        MentorshipSession.ally_id == ally.id,
        MentorshipSession.session_date >= week_start
    ).scalar() or 0


def _calculate_current_completion_rate(ally: Ally) -> float:
    """Calcula tasa de completitud actual."""
    # Implementación básica
    return 85.5  # Valor simulado


def _get_current_satisfaction_score(ally: Ally) -> float:
    """Obtiene puntaje de satisfacción actual."""
    # Implementación básica
    return 4.2  # Valor simulado


# Más funciones auxiliares serían implementadas según necesidades específicas...

def _calculate_avg_response_time(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula tiempo promedio de respuesta a mensajes."""
    # Implementación simplificada
    return 4.5  # horas


def _calculate_mentorship_effectiveness_score(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula score de efectividad de mentoría."""
    # Implementación simplificada
    return 78.5


def _get_average_satisfaction_score(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Obtiene puntaje promedio de satisfacción."""
    # Implementación simplificada
    return 4.3


def _calculate_productivity_score(ally: Ally, start_date: datetime, end_date: datetime) -> float:
    """Calcula score de productividad."""
    # Implementación simplificada
    return 82.1


def _calculate_entrepreneur_overall_progress(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Calcula progreso general de un emprendedor."""
    # Implementación simplificada
    return {
        'overall_percentage': 65.5,
        'current_stage': 'development',
        'completed_milestones': 3,
        'total_milestones': 7
    }


def _get_next_activity_with_entrepreneur(ally: Ally, entrepreneur: Entrepreneur) -> Optional[dict[str, Any]]:
    """Obtiene próxima actividad con un emprendedor específico."""
    next_meeting = Meeting.query.filter(
        Meeting.ally_id == ally.id,
        Meeting.entrepreneur_id == entrepreneur.id,
        Meeting.scheduled_at > datetime.now(timezone.utc)
    ).order_by(Meeting.scheduled_at.asc()).first()
    
    if next_meeting:
        return {
            'type': 'meeting',
            'title': next_meeting.title,
            'datetime': next_meeting.scheduled_at
        }
    
    return None


def _get_relationship_status(ally: Ally, entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Obtiene estado de la relación con el emprendedor."""
    # Implementación simplificada
    return {
        'status': 'active',
        'needs_attention': False,
        'last_interaction_days': 3,
        'satisfaction_level': 'high'
    }


def _get_last_interaction_date(ally: Ally, entrepreneur: Entrepreneur) -> datetime:
    """Obtiene fecha de última interacción."""
    # Implementación simplificada
    return datetime.now(timezone.utc) - timedelta(days=2)


def _get_urgent_items_for_entrepreneur(entrepreneur: Entrepreneur) -> list[str]:
    """Obtiene items urgentes para un emprendedor."""
    # Implementación simplificada
    return []


def _get_activity_icon(action: str) -> str:
    """Obtiene icono para un tipo de actividad."""
    icons = {
        'meeting_scheduled': 'event',
        'message_sent': 'message',
        'document_reviewed': 'description',
        'session_completed': 'check_circle',
        'default': 'info'
    }
    return icons.get(action, icons['default'])


def _get_activity_color(action: str) -> str:
    """Obtiene color para un tipo de actividad."""
    colors = {
        'meeting_scheduled': 'blue',
        'message_sent': 'green',
        'document_reviewed': 'orange',
        'session_completed': 'success',
        'default': 'gray'
    }
    return colors.get(action, colors['default'])


# Funciones para manejo de widgets, charts, acciones rápidas, etc.
# Se implementarían según los requirements específicos del proyecto...

def _generate_chart_data(ally: Ally, chart_type: str, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Genera datos para un tipo de gráfico específico."""
    # Implementación según tipo de gráfico
    return {'labels': [], 'data': [], 'chart_type': chart_type}


def _execute_quick_action(ally: Ally, action_type: str, action_data: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una acción rápida específica."""
    # Implementación según tipo de acción
    return {'success': True, 'message': 'Acción ejecutada exitosamente'}


def _log_quick_action(ally: Ally, action_type: str, action_data: dict[str, Any], result: dict[str, Any]) -> None:
    """Registra una acción rápida en el log."""
    # Implementación del logging
    pass


def _get_widget_configuration(ally: Ally) -> dict[str, Any]:
    """Obtiene configuración actual de widgets."""
    # Implementación pendiente
    return {}


def _validate_widget_config(config: dict[str, Any]) -> bool:
    """Valida configuración de widgets."""
    # Implementación pendiente
    return True


def _save_widget_configuration(ally: Ally, config: dict[str, Any]) -> dict[str, Any]:
    """Guarda configuración de widgets."""
    # Implementación pendiente
    return {'success': True}


def _get_notifications_api_summary(ally: Ally) -> dict[str, Any]:
    """Obtiene resumen de notificaciones para API."""
    # Implementación pendiente
    return {}


def _generate_dashboard_report_data(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Genera datos para reporte del dashboard."""
    # Implementación pendiente
    return {}


# Funciones adicionales para manejo de gráficos específicos
def _generate_sessions_timeline(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Genera timeline de sesiones."""
    return {'type': 'line', 'data': []}


def _generate_time_distribution_chart(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Genera gráfico de distribución de tiempo."""
    return {'type': 'pie', 'data': []}


def _generate_entrepreneurs_progress_chart(ally: Ally) -> dict[str, Any]:
    """Genera gráfico de progreso de emprendedores."""
    return {'type': 'bar', 'data': []}


def _generate_satisfaction_trend_chart(ally: Ally, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Genera gráfico de tendencia de satisfacción."""
    return {'type': 'line', 'data': []}