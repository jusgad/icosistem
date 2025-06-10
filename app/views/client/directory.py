"""
Vistas del directorio de emprendimientos para clientes/stakeholders.

Este módulo maneja el directorio público donde los clientes pueden:
- Explorar emprendedores y proyectos del ecosistema
- Buscar y filtrar por múltiples criterios
- Ver perfiles detallados y información de contacto
- Conectar con emprendedores según permisos
- Exportar información del directorio
- Acceder a métricas públicas de proyectos

El acceso está diferenciado por tipo de cliente:
- Public: Información básica y perfiles públicos
- Stakeholder: Detalles adicionales y métricas
- Investor: Información financiera y oportunidades
- Partner: Datos de colaboración y partnership
"""

import re
import csv
import tempfile
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from collections import defaultdict

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file, make_response
)
from flask_login import current_user
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db, cache
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.document import Document
from app.models.message import Message, MessageThread
from app.core.exceptions import ValidationError, PermissionError
from app.utils.decorators import cache_response, log_activity, rate_limit
from app.utils.validators import validate_email, validate_search_query
from app.utils.formatters import format_currency, format_date, format_phone
from app.utils.string_utils import sanitize_input, normalize_search_term
from app.utils.export_utils import generate_directory_pdf, generate_directory_excel
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService

# Importar funciones del módulo principal
from . import (
    get_client_type, get_client_permissions, require_client_permission,
    track_client_activity, cache_key_for_client
)

# Blueprint para el directorio de clientes
client_directory_bp = Blueprint(
    'client_directory', 
    __name__, 
    url_prefix='/directory'
)

# Configuraciones del directorio
DIRECTORY_CONFIG = {
    'ITEMS_PER_PAGE': 12,
    'MAX_SEARCH_RESULTS': 500,
    'CACHE_TIMEOUT': 600,  # 10 minutos
    'FEATURED_COUNT': 6,
    'RECENT_COUNT': 8,
    'SEARCH_MIN_LENGTH': 2,
    'MAX_EXPORT_RECORDS': 1000
}

# Campos de búsqueda disponibles
SEARCH_FIELDS = {
    'name': 'Nombre',
    'industry': 'Industria', 
    'location': 'Ubicación',
    'skills': 'Habilidades',
    'description': 'Descripción',
    'project_name': 'Nombre del Proyecto',
    'project_description': 'Descripción del Proyecto'
}

# Filtros disponibles
AVAILABLE_FILTERS = {
    'industry': 'Industria',
    'location': 'Ubicación',
    'gender': 'Género',
    'age_range': 'Rango de Edad',
    'project_status': 'Estado del Proyecto',
    'program': 'Programa',
    'organization': 'Organización',
    'experience_level': 'Nivel de Experiencia',
    'funding_stage': 'Etapa de Financiamiento'
}

# Opciones de ordenamiento
SORT_OPTIONS = {
    'relevance': 'Relevancia',
    'name_asc': 'Nombre (A-Z)',
    'name_desc': 'Nombre (Z-A)',
    'created_desc': 'Más Recientes',
    'created_asc': 'Más Antiguos',
    'projects_desc': 'Más Proyectos',
    'success_score_desc': 'Mayor Éxito',
    'location': 'Ubicación'
}


@client_directory_bp.route('/')
@cache_response(timeout=DIRECTORY_CONFIG['CACHE_TIMEOUT'])
@log_activity('view_directory')
def index():
    """
    Página principal del directorio de emprendimientos.
    
    Muestra emprendedores destacados, búsqueda rápida,
    filtros disponibles y estadísticas generales.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Emprendedores destacados
        featured_entrepreneurs = _get_featured_entrepreneurs(
            DIRECTORY_CONFIG['FEATURED_COUNT'], permissions
        )
        
        # Emprendedores recientes
        recent_entrepreneurs = _get_recent_entrepreneurs(
            DIRECTORY_CONFIG['RECENT_COUNT'], permissions
        )
        
        # Estadísticas generales
        directory_stats = _get_directory_stats(permissions)
        
        # Opciones de filtro disponibles
        filter_options = _get_filter_options(permissions)
        
        # Industrias más populares
        popular_industries = _get_popular_industries(permissions)
        
        # Proyectos destacados
        featured_projects = _get_featured_projects(permissions)
        
        return render_template(
            'client/directory/index.html',
            featured_entrepreneurs=featured_entrepreneurs,
            recent_entrepreneurs=recent_entrepreneurs,
            directory_stats=directory_stats,
            filter_options=filter_options,
            popular_industries=popular_industries,
            featured_projects=featured_projects,
            search_fields=SEARCH_FIELDS,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_date=format_date
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en directorio principal: {str(e)}")
        flash('Error al cargar el directorio.', 'error')
        return redirect(url_for('client.index'))


@client_directory_bp.route('/search')
@log_activity('search_directory')
def search():
    """
    Búsqueda avanzada en el directorio.
    
    Permite búsqueda por texto, filtros múltiples,
    ordenamiento y paginación de resultados.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de búsqueda
        query = request.args.get('q', '').strip()
        search_field = request.args.get('field', 'name')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', DIRECTORY_CONFIG['ITEMS_PER_PAGE'], type=int), 50)
        sort_by = request.args.get('sort', 'relevance')
        
        # Filtros
        filters = _extract_search_filters(request.args)
        
        # Validar parámetros
        if query and len(query) < DIRECTORY_CONFIG['SEARCH_MIN_LENGTH']:
            flash(f'La búsqueda debe tener al menos {DIRECTORY_CONFIG["SEARCH_MIN_LENGTH"]} caracteres.', 'warning')
            return redirect(url_for('client_directory.index'))
        
        if search_field not in SEARCH_FIELDS:
            search_field = 'name'
        
        # Realizar búsqueda
        search_results = _perform_search(
            query, search_field, filters, sort_by, page, per_page, permissions
        )
        
        # Registrar búsqueda para analytics
        if query:
            track_client_activity('directory_search', {
                'query': query,
                'field': search_field,
                'filters': filters,
                'results_count': search_results['total']
            })
        
        # Opciones disponibles para filtros
        filter_options = _get_filter_options(permissions)
        
        # Sugerencias de búsqueda
        search_suggestions = []
        if query and search_results['total'] == 0:
            search_suggestions = _get_search_suggestions(query, permissions)
        
        return render_template(
            'client/directory/search.html',
            search_results=search_results,
            query=query,
            search_field=search_field,
            filters=filters,
            sort_by=sort_by,
            page=page,
            per_page=per_page,
            search_fields=SEARCH_FIELDS,
            sort_options=SORT_OPTIONS,
            filter_options=filter_options,
            search_suggestions=search_suggestions,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_date=format_date
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en búsqueda del directorio: {str(e)}")
        flash('Error al realizar la búsqueda.', 'error')
        return redirect(url_for('client_directory.index'))


@client_directory_bp.route('/entrepreneur/<int:entrepreneur_id>')
@log_activity('view_entrepreneur_profile')
def view_entrepreneur(entrepreneur_id):
    """
    Perfil detallado de un emprendedor.
    
    Muestra información completa del emprendedor y sus proyectos
    según los permisos del cliente.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener emprendedor con datos relacionados
        entrepreneur = (
            Entrepreneur.query
            .options(
                joinedload(Entrepreneur.user),
                selectinload(Entrepreneur.projects).joinedload(Project.documents),
                selectinload(Entrepreneur.skills),
                selectinload(Entrepreneur.education),
                selectinload(Entrepreneur.experience)
            )
            .filter_by(id=entrepreneur_id)
            .first_or_404()
        )
        
        # Verificar si el perfil es público o si el cliente tiene permisos
        if not entrepreneur.is_public and not _has_detailed_access(permissions):
            abort(403)
        
        # Proyectos del emprendedor (filtrados por permisos)
        projects = _get_entrepreneur_projects(entrepreneur, permissions)
        
        # Métricas del emprendedor
        entrepreneur_metrics = _get_entrepreneur_metrics(entrepreneur, permissions)
        
        # Documentos y portfolio (si tiene permisos)
        portfolio_items = []
        if permissions.get('can_view_portfolio', False):
            portfolio_items = _get_entrepreneur_portfolio(entrepreneur)
        
        # Información de contacto disponible
        contact_info = _get_contact_info(entrepreneur, permissions)
        
        # Emprendedores similares
        similar_entrepreneurs = _get_similar_entrepreneurs(entrepreneur, permissions)
        
        # Verificar si puede contactar
        can_contact = _can_contact_entrepreneur(entrepreneur, current_user, permissions)
        
        # Registrar vista del perfil
        track_client_activity('entrepreneur_profile_view', {
            'entrepreneur_id': entrepreneur_id,
            'entrepreneur_name': entrepreneur.name
        })
        
        return render_template(
            'client/directory/entrepreneur_profile.html',
            entrepreneur=entrepreneur,
            projects=projects,
            entrepreneur_metrics=entrepreneur_metrics,
            portfolio_items=portfolio_items,
            contact_info=contact_info,
            similar_entrepreneurs=similar_entrepreneurs,
            can_contact=can_contact,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_date=format_date,
            format_phone=format_phone
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando perfil de emprendedor: {str(e)}")
        flash('Error al cargar el perfil del emprendedor.', 'error')
        return redirect(url_for('client_directory.index'))


@client_directory_bp.route('/project/<int:project_id>')
@log_activity('view_project_details')
def view_project(project_id):
    """
    Vista detallada de un proyecto específico.
    
    Muestra información completa del proyecto según permisos,
    incluyendo métricas, documentos y oportunidades.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Obtener proyecto con datos relacionados
        project = (
            Project.query
            .options(
                joinedload(Project.entrepreneur).joinedload(Entrepreneur.user),
                joinedload(Project.ally),
                joinedload(Project.organization),
                joinedload(Project.program),
                selectinload(Project.documents),
                selectinload(Project.tasks),
                selectinload(Project.milestones)
            )
            .filter_by(id=project_id)
            .first_or_404()
        )
        
        # Verificar acceso público o permisos
        if not project.is_public and not _has_detailed_access(permissions):
            abort(403)
        
        # Métricas del proyecto
        project_metrics = _get_project_metrics(project, permissions)
        
        # Documentos públicos del proyecto
        public_documents = _get_project_documents(project, permissions)
        
        # Timeline del proyecto
        project_timeline = _get_project_timeline(project, permissions)
        
        # Información financiera (si tiene permisos)
        financial_info = {}
        if permissions.get('can_view_financial_metrics'):
            financial_info = _get_project_financial_info(project)
        
        # Oportunidades relacionadas
        related_opportunities = []
        if permissions.get('can_view_opportunities'):
            related_opportunities = _get_project_opportunities(project)
        
        # Proyectos similares
        similar_projects = _get_similar_projects(project, permissions)
        
        # Registrar vista del proyecto
        track_client_activity('project_view', {
            'project_id': project_id,
            'project_name': project.name,
            'entrepreneur_id': project.entrepreneur_id
        })
        
        return render_template(
            'client/directory/project_details.html',
            project=project,
            project_metrics=project_metrics,
            public_documents=public_documents,
            project_timeline=project_timeline,
            financial_info=financial_info,
            related_opportunities=related_opportunities,
            similar_projects=similar_projects,
            client_type=client_type,
            permissions=permissions,
            format_currency=format_currency,
            format_date=format_date
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando detalles del proyecto: {str(e)}")
        flash('Error al cargar los detalles del proyecto.', 'error')
        return redirect(url_for('client_directory.index'))


@client_directory_bp.route('/contact/<int:entrepreneur_id>')
@require_client_permission('can_contact_entrepreneurs')
@log_activity('contact_entrepreneur')
def contact_entrepreneur(entrepreneur_id):
    """
    Formulario de contacto con un emprendedor.
    
    Permite enviar mensajes directos a emprendedores
    según permisos y configuraciones de privacidad.
    """
    try:
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar si puede contactar
        if not _can_contact_entrepreneur(entrepreneur, current_user, get_client_permissions()):
            flash('No puedes contactar a este emprendedor.', 'error')
            return redirect(url_for('client_directory.view_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        return render_template(
            'client/directory/contact_form.html',
            entrepreneur=entrepreneur,
            client_type=get_client_type(current_user)
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando formulario de contacto: {str(e)}")
        flash('Error al cargar el formulario de contacto.', 'error')
        return redirect(url_for('client_directory.view_entrepreneur', entrepreneur_id=entrepreneur_id))


@client_directory_bp.route('/contact/<int:entrepreneur_id>', methods=['POST'])
@require_client_permission('can_contact_entrepreneurs')
@rate_limit('5 per hour')
@log_activity('send_contact_message')
def send_contact_message(entrepreneur_id):
    """
    Procesa el envío de mensaje de contacto.
    
    Valida y envía el mensaje al emprendedor, creando
    una conversación si es necesario.
    """
    try:
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        # Verificar permisos
        if not _can_contact_entrepreneur(entrepreneur, current_user, get_client_permissions()):
            flash('No puedes contactar a este emprendedor.', 'error')
            return redirect(url_for('client_directory.view_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        # Obtener datos del formulario
        subject = request.form.get('subject', '').strip()
        message_content = request.form.get('message', '').strip()
        sender_name = request.form.get('sender_name', '').strip()
        sender_email = request.form.get('sender_email', '').strip()
        sender_company = request.form.get('sender_company', '').strip()
        
        # Validaciones
        if not all([subject, message_content, sender_name, sender_email]):
            flash('Todos los campos obligatorios deben ser completados.', 'error')
            return redirect(url_for('client_directory.contact_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        if not validate_email(sender_email):
            flash('Email inválido.', 'error')
            return redirect(url_for('client_directory.contact_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        if len(message_content) < 20:
            flash('El mensaje debe tener al menos 20 caracteres.', 'error')
            return redirect(url_for('client_directory.contact_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        if len(message_content) > 2000:
            flash('El mensaje no puede superar los 2000 caracteres.', 'error')
            return redirect(url_for('client_directory.contact_entrepreneur', entrepreneur_id=entrepreneur_id))
        
        # Sanitizar contenido
        subject = sanitize_input(subject)
        message_content = sanitize_input(message_content)
        sender_name = sanitize_input(sender_name)
        sender_company = sanitize_input(sender_company)
        
        # Enviar mensaje
        message_sent = _send_contact_message_to_entrepreneur(
            entrepreneur, subject, message_content, sender_name, 
            sender_email, sender_company
        )
        
        if message_sent:
            # Registrar contacto exitoso
            track_client_activity('contact_message_sent', {
                'entrepreneur_id': entrepreneur_id,
                'entrepreneur_name': entrepreneur.name,
                'sender_email': sender_email,
                'subject': subject
            })
            
            flash('Tu mensaje ha sido enviado exitosamente. El emprendedor se pondrá en contacto contigo pronto.', 'success')
        else:
            flash('Error al enviar el mensaje. Por favor, intenta nuevamente.', 'error')
        
        return redirect(url_for('client_directory.view_entrepreneur', entrepreneur_id=entrepreneur_id))
        
    except Exception as e:
        current_app.logger.error(f"Error enviando mensaje de contacto: {str(e)}")
        flash('Error interno al enviar el mensaje.', 'error')
        return redirect(url_for('client_directory.contact_entrepreneur', entrepreneur_id=entrepreneur_id))


@client_directory_bp.route('/export')
@require_client_permission('can_export_directory')
@log_activity('export_directory')
def export_directory():
    """
    Exporta el directorio en diferentes formatos.
    
    Permite exportar la lista de emprendedores y proyectos
    en PDF, Excel o CSV según permisos.
    """
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        # Parámetros de exportación
        format_type = request.args.get('format', 'pdf')
        include_projects = request.args.get('include_projects', 'true') == 'true'
        include_contact = request.args.get('include_contact', 'false') == 'true'
        filter_industry = request.args.get('industry')
        filter_location = request.args.get('location')
        
        # Validar formato
        if format_type not in ['pdf', 'excel', 'csv']:
            format_type = 'pdf'
        
        # Obtener datos para exportación
        export_data = _get_export_data(
            permissions, include_projects, include_contact, 
            filter_industry, filter_location
        )
        
        if not export_data['entrepreneurs']:
            flash('No hay datos para exportar con los filtros seleccionados.', 'warning')
            return redirect(url_for('client_directory.index'))
        
        # Verificar límite de registros
        if len(export_data['entrepreneurs']) > DIRECTORY_CONFIG['MAX_EXPORT_RECORDS']:
            flash(f'Demasiados registros para exportar. Máximo: {DIRECTORY_CONFIG["MAX_EXPORT_RECORDS"]}', 'error')
            return redirect(url_for('client_directory.index'))
        
        # Generar archivo según formato
        if format_type == 'excel':
            file_path = generate_directory_excel(export_data)
            filename = f'directorio_emprendedores_{datetime.utcnow().strftime("%Y%m%d")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif format_type == 'csv':
            file_path = _generate_directory_csv(export_data)
            filename = f'directorio_emprendedores_{datetime.utcnow().strftime("%Y%m%d")}.csv'
            mimetype = 'text/csv'
        else:  # PDF
            file_path = generate_directory_pdf(export_data)
            filename = f'directorio_emprendedores_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
            mimetype = 'application/pdf'
        
        # Registrar exportación
        track_client_activity('directory_exported', {
            'format': format_type,
            'records_count': len(export_data['entrepreneurs']),
            'include_projects': include_projects,
            'include_contact': include_contact
        })
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exportando directorio: {str(e)}")
        flash('Error al generar la exportación.', 'error')
        return redirect(url_for('client_directory.index'))


# API Endpoints para funcionalidades AJAX

@client_directory_bp.route('/api/search')
@rate_limit('30 per minute')
def api_search():
    """API endpoint para búsqueda dinámica via AJAX."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        query = request.args.get('q', '').strip()
        field = request.args.get('field', 'name')
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        if not query or len(query) < DIRECTORY_CONFIG['SEARCH_MIN_LENGTH']:
            return jsonify({'results': [], 'total': 0})
        
        # Realizar búsqueda rápida
        results = _perform_quick_search(query, field, limit, permissions)
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results),
            'query': query
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API search: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_directory_bp.route('/api/filters')
@cache_response(timeout=1800)  # 30 minutos
def api_filters():
    """API endpoint para obtener opciones de filtros dinámicos."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        filter_type = request.args.get('type', 'industry')
        search_term = request.args.get('search', '').strip()
        
        filter_options = _get_dynamic_filter_options(filter_type, search_term, permissions)
        
        return jsonify({
            'success': True,
            'filter_type': filter_type,
            'options': filter_options
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API filters: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_directory_bp.route('/api/entrepreneur/<int:entrepreneur_id>/quick-info')
@cache_response(timeout=600)
def api_entrepreneur_quick_info(entrepreneur_id):
    """API endpoint para información rápida de emprendedor."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
        
        if not entrepreneur.is_public and not _has_detailed_access(permissions):
            return jsonify({'error': 'Sin permisos'}), 403
        
        quick_info = {
            'id': entrepreneur.id,
            'name': entrepreneur.name,
            'title': entrepreneur.title,
            'location': entrepreneur.location,
            'industry': entrepreneur.industry,
            'experience_years': entrepreneur.experience_years,
            'projects_count': entrepreneur.projects.filter_by(is_public=True).count(),
            'avatar_url': entrepreneur.avatar_url,
            'bio_summary': entrepreneur.bio[:200] + '...' if entrepreneur.bio and len(entrepreneur.bio) > 200 else entrepreneur.bio
        }
        
        # Información adicional según permisos
        if permissions.get('can_view_contact_info'):
            quick_info.update({
                'email': entrepreneur.email,
                'phone': entrepreneur.phone,
                'website': entrepreneur.website
            })
        
        return jsonify({
            'success': True,
            'entrepreneur': quick_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API quick info: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@client_directory_bp.route('/api/suggestions')
def api_search_suggestions():
    """API endpoint para sugerencias de búsqueda."""
    try:
        client_type = get_client_type(current_user)
        permissions = get_client_permissions(client_type)
        
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []})
        
        suggestions = _get_search_suggestions(query, permissions, limit=10)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'query': query
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API suggestions: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _get_featured_entrepreneurs(limit, permissions):
    """Obtiene emprendedores destacados."""
    query = (
        Entrepreneur.query
        .filter_by(is_public=True, is_featured=True)
        .options(joinedload(Entrepreneur.user))
        .order_by(desc(Entrepreneur.featured_order), desc(Entrepreneur.created_at))
        .limit(limit)
    )
    
    return query.all()


def _get_recent_entrepreneurs(limit, permissions):
    """Obtiene emprendedores recientes."""
    query = (
        Entrepreneur.query
        .filter_by(is_public=True)
        .options(joinedload(Entrepreneur.user))
        .order_by(desc(Entrepreneur.created_at))
        .limit(limit)
    )
    
    return query.all()


def _get_directory_stats(permissions):
    """Obtiene estadísticas generales del directorio."""
    stats = {}
    
    # Estadísticas básicas
    stats['total_entrepreneurs'] = Entrepreneur.query.filter_by(is_public=True).count()
    stats['total_projects'] = Project.query.filter_by(is_public=True).count()
    stats['active_projects'] = Project.query.filter_by(is_public=True, status='active').count()
    
    # Distribución por industria
    industry_stats = (
        db.session.query(
            Entrepreneur.industry,
            func.count(Entrepreneur.id).label('count')
        )
        .filter(Entrepreneur.is_public == True)
        .group_by(Entrepreneur.industry)
        .order_by(func.count(Entrepreneur.id).desc())
        .limit(5)
        .all()
    )
    
    stats['top_industries'] = [
        {'industry': item[0], 'count': item[1]}
        for item in industry_stats if item[0]
    ]
    
    # Distribución por ubicación
    location_stats = (
        db.session.query(
            Entrepreneur.location,
            func.count(Entrepreneur.id).label('count')
        )
        .filter(Entrepreneur.is_public == True)
        .group_by(Entrepreneur.location)
        .order_by(func.count(Entrepreneur.id).desc())
        .limit(5)
        .all()
    )
    
    stats['top_locations'] = [
        {'location': item[0], 'count': item[1]}
        for item in location_stats if item[0]
    ]
    
    return stats


def _get_filter_options(permissions):
    """Obtiene opciones disponibles para filtros."""
    options = {}
    
    # Industrias
    industries = (
        db.session.query(Entrepreneur.industry)
        .filter(Entrepreneur.is_public == True, Entrepreneur.industry.isnot(None))
        .distinct()
        .order_by(Entrepreneur.industry)
        .all()
    )
    options['industries'] = [i[0] for i in industries]
    
    # Ubicaciones
    locations = (
        db.session.query(Entrepreneur.location)
        .filter(Entrepreneur.is_public == True, Entrepreneur.location.isnot(None))
        .distinct()
        .order_by(Entrepreneur.location)
        .all()
    )
    options['locations'] = [l[0] for l in locations]
    
    # Estados de proyecto
    project_statuses = (
        db.session.query(Project.status)
        .filter(Project.is_public == True)
        .distinct()
        .all()
    )
    options['project_statuses'] = [s[0] for s in project_statuses]
    
    # Programas
    programs = (
        Program.query
        .filter_by(status='active')
        .order_by(Program.name)
        .all()
    )
    options['programs'] = [{'id': p.id, 'name': p.name} for p in programs]
    
    # Organizaciones
    organizations = (
        Organization.query
        .filter_by(is_active=True)
        .order_by(Organization.name)
        .all()
    )
    options['organizations'] = [{'id': o.id, 'name': o.name} for o in organizations]
    
    return options


def _get_popular_industries(permissions):
    """Obtiene las industrias más populares."""
    industries = (
        db.session.query(
            Entrepreneur.industry,
            func.count(Entrepreneur.id).label('count'),
            func.count(Project.id).label('projects_count')
        )
        .outerjoin(Project, and_(
            Project.entrepreneur_id == Entrepreneur.id,
            Project.is_public == True
        ))
        .filter(Entrepreneur.is_public == True)
        .group_by(Entrepreneur.industry)
        .order_by(func.count(Entrepreneur.id).desc())
        .limit(8)
        .all()
    )
    
    return [
        {
            'industry': item[0],
            'entrepreneurs_count': item[1],
            'projects_count': item[2]
        }
        for item in industries if item[0]
    ]


def _get_featured_projects(permissions):
    """Obtiene proyectos destacados."""
    projects = (
        Project.query
        .filter_by(is_public=True, is_featured=True)
        .options(
            joinedload(Project.entrepreneur),
            joinedload(Project.organization)
        )
        .order_by(desc(Project.featured_order), desc(Project.created_at))
        .limit(6)
        .all()
    )
    
    return projects


def _extract_search_filters(args):
    """Extrae y valida filtros de búsqueda."""
    filters = {}
    
    # Filtros estándar
    for filter_name in AVAILABLE_FILTERS.keys():
        value = args.get(filter_name)
        if value and value.strip():
            filters[filter_name] = value.strip()
    
    # Filtros especiales
    if args.get('min_experience'):
        try:
            filters['min_experience'] = int(args.get('min_experience'))
        except ValueError:
            pass
    
    if args.get('max_experience'):
        try:
            filters['max_experience'] = int(args.get('max_experience'))
        except ValueError:
            pass
    
    return filters


def _perform_search(query, search_field, filters, sort_by, page, per_page, permissions):
    """Realiza búsqueda completa con filtros y paginación."""
    # Consulta base
    base_query = (
        Entrepreneur.query
        .filter_by(is_public=True)
        .options(
            joinedload(Entrepreneur.user),
            selectinload(Entrepreneur.projects).joinedload(Project.organization)
        )
    )
    
    # Aplicar búsqueda por texto
    if query:
        search_term = f"%{normalize_search_term(query)}%"
        
        if search_field == 'name':
            base_query = base_query.filter(Entrepreneur.name.ilike(search_term))
        elif search_field == 'industry':
            base_query = base_query.filter(Entrepreneur.industry.ilike(search_term))
        elif search_field == 'location':
            base_query = base_query.filter(Entrepreneur.location.ilike(search_term))
        elif search_field == 'skills':
            base_query = base_query.filter(Entrepreneur.skills.ilike(search_term))
        elif search_field == 'description':
            base_query = base_query.filter(Entrepreneur.bio.ilike(search_term))
        elif search_field == 'project_name':
            base_query = base_query.join(Project).filter(
                Project.name.ilike(search_term),
                Project.is_public == True
            )
        elif search_field == 'project_description':
            base_query = base_query.join(Project).filter(
                Project.description.ilike(search_term),
                Project.is_public == True
            )
    
    # Aplicar filtros
    if filters.get('industry'):
        base_query = base_query.filter(Entrepreneur.industry == filters['industry'])
    
    if filters.get('location'):
        base_query = base_query.filter(Entrepreneur.location == filters['location'])
    
    if filters.get('gender'):
        base_query = base_query.filter(Entrepreneur.gender == filters['gender'])
    
    if filters.get('min_experience'):
        base_query = base_query.filter(Entrepreneur.experience_years >= filters['min_experience'])
    
    if filters.get('max_experience'):
        base_query = base_query.filter(Entrepreneur.experience_years <= filters['max_experience'])
    
    if filters.get('program'):
        base_query = base_query.join(Project).filter(Project.program_id == filters['program'])
    
    if filters.get('organization'):
        base_query = base_query.join(Project).filter(Project.organization_id == filters['organization'])
    
    # Aplicar ordenamiento
    if sort_by == 'name_asc':
        base_query = base_query.order_by(asc(Entrepreneur.name))
    elif sort_by == 'name_desc':
        base_query = base_query.order_by(desc(Entrepreneur.name))
    elif sort_by == 'created_desc':
        base_query = base_query.order_by(desc(Entrepreneur.created_at))
    elif sort_by == 'created_asc':
        base_query = base_query.order_by(asc(Entrepreneur.created_at))
    elif sort_by == 'projects_desc':
        # Subquery para contar proyectos
        project_count = (
            db.session.query(
                Project.entrepreneur_id,
                func.count(Project.id).label('project_count')
            )
            .filter(Project.is_public == True)
            .group_by(Project.entrepreneur_id)
            .subquery()
        )
        
        base_query = (
            base_query
            .outerjoin(project_count, Entrepreneur.id == project_count.c.entrepreneur_id)
            .order_by(desc(project_count.c.project_count))
        )
    elif sort_by == 'location':
        base_query = base_query.order_by(asc(Entrepreneur.location), asc(Entrepreneur.name))
    else:  # relevance o default
        if query:
            # Ordenar por relevancia (simple scoring)
            base_query = base_query.order_by(desc(Entrepreneur.is_featured), desc(Entrepreneur.created_at))
        else:
            base_query = base_query.order_by(desc(Entrepreneur.is_featured), desc(Entrepreneur.created_at))
    
    # Ejecutar paginación
    pagination = base_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
        max_per_page=DIRECTORY_CONFIG['MAX_SEARCH_RESULTS']
    )
    
    return {
        'entrepreneurs': pagination.items,
        'pagination': pagination,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'prev_num': pagination.prev_num,
        'next_num': pagination.next_num
    }


def _perform_quick_search(query, field, limit, permissions):
    """Realiza búsqueda rápida para autocompletar."""
    search_term = f"%{normalize_search_term(query)}%"
    
    results = []
    
    if field == 'name':
        entrepreneurs = (
            Entrepreneur.query
            .filter(
                Entrepreneur.is_public == True,
                Entrepreneur.name.ilike(search_term)
            )
            .order_by(Entrepreneur.name)
            .limit(limit)
            .all()
        )
        
        results = [
            {
                'id': e.id,
                'name': e.name,
                'type': 'entrepreneur',
                'industry': e.industry,
                'location': e.location
            }
            for e in entrepreneurs
        ]
    
    elif field == 'project_name':
        projects = (
            Project.query
            .filter(
                Project.is_public == True,
                Project.name.ilike(search_term)
            )
            .options(joinedload(Project.entrepreneur))
            .order_by(Project.name)
            .limit(limit)
            .all()
        )
        
        results = [
            {
                'id': p.id,
                'name': p.name,
                'type': 'project',
                'entrepreneur': p.entrepreneur.name if p.entrepreneur else 'N/A',
                'status': p.status
            }
            for p in projects
        ]
    
    return results


def _get_search_suggestions(query, permissions, limit=10):
    """Genera sugerencias de búsqueda."""
    suggestions = []
    
    # Sugerencias basadas en nombres similares
    similar_names = (
        Entrepreneur.query
        .filter(
            Entrepreneur.is_public == True,
            Entrepreneur.name.ilike(f"%{query}%")
        )
        .order_by(Entrepreneur.name)
        .limit(limit // 2)
        .all()
    )
    
    suggestions.extend([e.name for e in similar_names])
    
    # Sugerencias basadas en industrias
    similar_industries = (
        db.session.query(Entrepreneur.industry)
        .filter(
            Entrepreneur.is_public == True,
            Entrepreneur.industry.ilike(f"%{query}%"),
            Entrepreneur.industry.isnot(None)
        )
        .distinct()
        .limit(limit // 2)
        .all()
    )
    
    suggestions.extend([i[0] for i in similar_industries])
    
    return list(set(suggestions))[:limit]


def _get_entrepreneur_projects(entrepreneur, permissions):
    """Obtiene proyectos del emprendedor según permisos."""
    query = entrepreneur.projects.filter_by(is_public=True)
    
    # Filtros adicionales según permisos
    if not _has_detailed_access(permissions):
        # Solo proyectos completados para usuarios públicos
        query = query.filter(Project.status.in_(['completed', 'active']))
    
    return query.order_by(desc(Project.created_at)).all()


def _get_entrepreneur_metrics(entrepreneur, permissions):
    """Calcula métricas del emprendedor."""
    metrics = {
        'total_projects': entrepreneur.projects.filter_by(is_public=True).count(),
        'completed_projects': entrepreneur.projects.filter_by(is_public=True, status='completed').count(),
        'active_projects': entrepreneur.projects.filter_by(is_public=True, status='active').count(),
        'experience_years': entrepreneur.experience_years or 0
    }
    
    # Métricas adicionales según permisos
    if _has_detailed_access(permissions):
        # Calcular tasa de éxito
        if metrics['total_projects'] > 0:
            metrics['success_rate'] = (metrics['completed_projects'] / metrics['total_projects']) * 100
        else:
            metrics['success_rate'] = 0
        
        # Impacto agregado
        impact_data = (
            db.session.query(
                func.sum(Project.jobs_created).label('total_jobs'),
                func.sum(Project.revenue_generated).label('total_revenue'),
                func.sum(Project.direct_beneficiaries).label('total_beneficiaries')
            )
            .filter(
                Project.entrepreneur_id == entrepreneur.id,
                Project.is_public == True,
                Project.status == 'completed'
            )
            .first()
        )
        
        metrics.update({
            'total_jobs_created': int(impact_data.total_jobs or 0),
            'total_revenue_generated': float(impact_data.total_revenue or 0),
            'total_beneficiaries': int(impact_data.total_beneficiaries or 0)
        })
    
    return metrics


def _get_entrepreneur_portfolio(entrepreneur):
    """Obtiene elementos del portfolio del emprendedor."""
    portfolio_items = (
        Document.query
        .join(Project)
        .filter(
            Project.entrepreneur_id == entrepreneur.id,
            Project.is_public == True,
            Document.is_portfolio_item == True,
            Document.is_public == True
        )
        .order_by(desc(Document.created_at))
        .limit(10)
        .all()
    )
    
    return portfolio_items


def _get_contact_info(entrepreneur, permissions):
    """Obtiene información de contacto disponible según permisos."""
    contact_info = {
        'email_available': False,
        'phone_available': False,
        'website_available': False,
        'social_media_available': False
    }
    
    if _has_contact_access(permissions):
        contact_info.update({
            'email': entrepreneur.email if entrepreneur.allow_contact_email else None,
            'phone': entrepreneur.phone if entrepreneur.allow_contact_phone else None,
            'website': entrepreneur.website,
            'linkedin': entrepreneur.linkedin_url,
            'twitter': entrepreneur.twitter_url,
            'email_available': bool(entrepreneur.email and entrepreneur.allow_contact_email),
            'phone_available': bool(entrepreneur.phone and entrepreneur.allow_contact_phone),
            'website_available': bool(entrepreneur.website),
            'social_media_available': bool(entrepreneur.linkedin_url or entrepreneur.twitter_url)
        })
    
    return contact_info


def _get_similar_entrepreneurs(entrepreneur, permissions, limit=4):
    """Obtiene emprendedores similares."""
    similar = (
        Entrepreneur.query
        .filter(
            Entrepreneur.is_public == True,
            Entrepreneur.id != entrepreneur.id,
            or_(
                Entrepreneur.industry == entrepreneur.industry,
                Entrepreneur.location == entrepreneur.location
            )
        )
        .order_by(
            func.random()  # PostgreSQL: func.random(), MySQL: func.rand()
        )
        .limit(limit)
        .all()
    )
    
    return similar


def _can_contact_entrepreneur(entrepreneur, user, permissions):
    """Verifica si puede contactar al emprendedor."""
    # Verificar configuración de privacidad del emprendedor
    if not entrepreneur.allow_public_contact:
        return False
    
    # Verificar permisos del cliente
    if not permissions.get('can_contact_entrepreneurs', False):
        return False
    
    # Verificar rate limiting (opcional)
    # Aquí podrías implementar lógica adicional
    
    return True


def _send_contact_message_to_entrepreneur(entrepreneur, subject, message, sender_name, sender_email, sender_company):
    """Envía mensaje de contacto al emprendedor."""
    try:
        # Crear mensaje en el sistema (si hay usuarios registrados)
        if entrepreneur.user_id:
            # Aquí podrías crear un mensaje interno en el sistema
            pass
        
        # Enviar email de notificación
        email_sent = EmailService.send_contact_message(
            recipient_email=entrepreneur.email,
            recipient_name=entrepreneur.name,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_company=sender_company,
            subject=subject,
            message=message
        )
        
        return email_sent
        
    except Exception as e:
        current_app.logger.error(f"Error enviando mensaje de contacto: {str(e)}")
        return False


def _get_export_data(permissions, include_projects, include_contact, filter_industry, filter_location):
    """Obtiene datos para exportación."""
    # Consulta base
    query = Entrepreneur.query.filter_by(is_public=True)
    
    # Aplicar filtros
    if filter_industry:
        query = query.filter(Entrepreneur.industry == filter_industry)
    
    if filter_location:
        query = query.filter(Entrepreneur.location == filter_location)
    
    # Limitar registros
    entrepreneurs = query.limit(DIRECTORY_CONFIG['MAX_EXPORT_RECORDS']).all()
    
    export_data = {
        'entrepreneurs': entrepreneurs,
        'include_projects': include_projects,
        'include_contact': include_contact and _has_contact_access(permissions),
        'generated_at': datetime.utcnow(),
        'permissions': permissions
    }
    
    if include_projects:
        project_ids = [e.id for e in entrepreneurs]
        projects = (
            Project.query
            .filter(
                Project.entrepreneur_id.in_(project_ids),
                Project.is_public == True
            )
            .all()
        )
        export_data['projects'] = projects
    
    return export_data


def _generate_directory_csv(export_data):
    """Genera archivo CSV del directorio."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
    
    fieldnames = ['nombre', 'industria', 'ubicacion', 'experiencia_años', 'genero']
    
    if export_data['include_contact']:
        fieldnames.extend(['email', 'telefono', 'sitio_web'])
    
    if export_data['include_projects']:
        fieldnames.extend(['proyectos_totales', 'proyectos_completados', 'proyectos_activos'])
    
    writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
    writer.writeheader()
    
    for entrepreneur in export_data['entrepreneurs']:
        row = {
            'nombre': entrepreneur.name,
            'industria': entrepreneur.industry or '',
            'ubicacion': entrepreneur.location or '',
            'experiencia_años': entrepreneur.experience_years or 0,
            'genero': entrepreneur.gender or ''
        }
        
        if export_data['include_contact']:
            row.update({
                'email': entrepreneur.email if entrepreneur.allow_contact_email else '',
                'telefono': entrepreneur.phone if entrepreneur.allow_contact_phone else '',
                'sitio_web': entrepreneur.website or ''
            })
        
        if export_data['include_projects']:
            projects = entrepreneur.projects.filter_by(is_public=True)
            row.update({
                'proyectos_totales': projects.count(),
                'proyectos_completados': projects.filter_by(status='completed').count(),
                'proyectos_activos': projects.filter_by(status='active').count()
            })
        
        writer.writerow(row)
    
    temp_file.close()
    return temp_file.name


def _has_detailed_access(permissions):
    """Verifica si tiene acceso a información detallada."""
    return permissions.get('can_access_detailed_analytics', False)


def _has_contact_access(permissions):
    """Verifica si tiene acceso a información de contacto."""
    return permissions.get('can_view_contact_info', False)


def _get_dynamic_filter_options(filter_type, search_term, permissions):
    """Obtiene opciones dinámicas para filtros."""
    options = []
    
    if filter_type == 'industry':
        query = (
            db.session.query(
                Entrepreneur.industry,
                func.count(Entrepreneur.id).label('count')
            )
            .filter(Entrepreneur.is_public == True)
            .group_by(Entrepreneur.industry)
            .order_by(func.count(Entrepreneur.id).desc())
        )
        
        if search_term:
            query = query.filter(Entrepreneur.industry.ilike(f'%{search_term}%'))
        
        results = query.limit(20).all()
        options = [
            {'value': r[0], 'label': f'{r[0]} ({r[1]})', 'count': r[1]}
            for r in results if r[0]
        ]
    
    elif filter_type == 'location':
        query = (
            db.session.query(
                Entrepreneur.location,
                func.count(Entrepreneur.id).label('count')
            )
            .filter(Entrepreneur.is_public == True)
            .group_by(Entrepreneur.location)
            .order_by(func.count(Entrepreneur.id).desc())
        )
        
        if search_term:
            query = query.filter(Entrepreneur.location.ilike(f'%{search_term}%'))
        
        results = query.limit(20).all()
        options = [
            {'value': r[0], 'label': f'{r[0]} ({r[1]})', 'count': r[1]}
            for r in results if r[0]
        ]
    
    return options


# Manejadores de errores específicos

@client_directory_bp.errorhandler(403)
def directory_forbidden(error):
    """Maneja errores de permisos en el directorio."""
    flash('No tienes permisos para acceder a esta información.', 'error')
    return redirect(url_for('client_directory.index'))


@client_directory_bp.errorhandler(404)
def directory_not_found(error):
    """Maneja errores de recurso no encontrado."""
    flash('El perfil o proyecto solicitado no existe.', 'error')
    return redirect(url_for('client_directory.index'))


@client_directory_bp.errorhandler(500)
def directory_internal_error(error):
    """Maneja errores internos en el directorio."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en directorio: {str(error)}")
    flash('Error interno del directorio. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('client.index'))