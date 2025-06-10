"""
Gestión de Organizaciones - Panel Administrativo
================================================

Este módulo gestiona todas las funcionalidades relacionadas con organizaciones
del ecosistema de emprendimiento: incubadoras, aceleradoras, corporaciones, 
universidades, gobierno, inversionistas y partners.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, case, cast, Float, text
from sqlalchemy.orm import joinedload, selectinload, contains_eager
from werkzeug.utils import secure_filename

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required
from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.constants import (
    ORGANIZATION_TYPES, ORGANIZATION_STATUS, PARTNERSHIP_TYPES, 
    INVESTMENT_TYPES, PROGRAM_TYPES, CURRENCY_TYPES, PRIORITY_LEVELS
)

# Importaciones de modelos
from app.models import (
    Organization, Program, Entrepreneur, Project, User, Admin,
    Partnership, Investment, Contact, Document, ActivityLog, 
    Analytics, Notification
)

# Importaciones de servicios
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.currency import CurrencyService
from app.services.file_storage import FileStorageService

# Importaciones de formularios
from app.forms.admin import (
    OrganizationForm, OrganizationFilterForm, PartnershipForm,
    InvestmentForm, BulkOrganizationActionForm, OrganizationContactForm,
    EvaluateOrganizationForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number
from app.utils.date_utils import get_date_range, format_date_range
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.validators import validate_url, validate_tax_id, validate_amount

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_organizations = Blueprint('admin_organizations', __name__, url_prefix='/admin/organizations')

# ============================================================================
# VISTAS PRINCIPALES - LISTADO Y GESTIÓN
# ============================================================================

@admin_organizations.route('/')
@admin_organizations.route('/list')
@login_required
@admin_required
@handle_exceptions
def list_organizations():
    """
    Lista todas las organizaciones con filtros avanzados y métricas.
    Incluye información de programas, inversiones, partnerships y impacto.
    """
    try:
        # Parámetros de consulta
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        type_filter = request.args.get('type', 'all')
        status_filter = request.args.get('status', 'all')
        country_filter = request.args.get('country', 'all')
        partnership_filter = request.args.get('partnership', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        
        # Query base con optimizaciones
        query = Organization.query.options(
            selectinload(Organization.programs),
            selectinload(Organization.partnerships),
            selectinload(Organization.investments),
            selectinload(Organization.contacts)
        )
        
        # Aplicar filtros de búsqueda
        if search:
            search_filter = or_(
                Organization.name.ilike(f'%{search}%'),
                Organization.description.ilike(f'%{search}%'),
                Organization.industry.ilike(f'%{search}%'),
                Organization.website.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtros específicos
        if type_filter != 'all':
            query = query.filter(Organization.type == type_filter)
            
        if status_filter != 'all':
            query = query.filter(Organization.status == status_filter)
            
        if country_filter != 'all':
            query = query.filter(Organization.country == country_filter)
            
        if partnership_filter == 'active':
            query = query.filter(
                Organization.partnerships.any(Partnership.status == 'active')
            )
        elif partnership_filter == 'none':
            query = query.filter(~Organization.partnerships.any())
        
        # Aplicar ordenamiento
        if sort_by == 'name':
            order_field = Organization.name
        elif sort_by == 'type':
            order_field = Organization.type
        elif sort_by == 'programs_count':
            order_field = func.count(Program.id)
            query = query.outerjoin(Program).group_by(Organization.id)
        elif sort_by == 'total_investment':
            order_field = Organization.total_investment
        elif sort_by == 'entrepreneurs_count':
            order_field = Organization.entrepreneurs_supported
        elif sort_by == 'impact_score':
            order_field = Organization.impact_score
        else:  # created_at por defecto
            order_field = Organization.created_at
            
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc().nulls_last())
        
        # Paginación
        organizations = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
            max_per_page=50
        )
        
        # Estadísticas para el dashboard
        stats = _get_organization_statistics()
        
        # Países para filtros
        countries = db.session.query(Organization.country).filter(
            Organization.country.isnot(None)
        ).distinct().all()
        countries = [country[0] for country in countries if country[0]]
        
        # Formularios
        filter_form = OrganizationFilterForm(request.args)
        bulk_action_form = BulkOrganizationActionForm()
        
        return render_template(
            'admin/organizations/list.html',
            organizations=organizations,
            stats=stats,
            countries=countries,
            filter_form=filter_form,
            bulk_action_form=bulk_action_form,
            current_filters={
                'search': search,
                'type': type_filter,
                'status': status_filter,
                'country': country_filter,
                'partnership': partnership_filter,
                'sort': sort_by,
                'order': sort_order
            },
            organization_types=ORGANIZATION_TYPES,
            organization_status=ORGANIZATION_STATUS
        )
        
    except Exception as e:
        current_app.logger.error(f"Error listando organizaciones: {str(e)}")
        flash('Error al cargar la lista de organizaciones.', 'error')
        return redirect(url_for('admin_dashboard.index'))

@admin_organizations.route('/<int:organization_id>')
@login_required
@admin_required
@handle_exceptions
def view_organization(organization_id):
    """
    Vista detallada de una organización específica.
    Incluye programas, inversiones, partnerships, impacto y métricas.
    """
    try:
        organization = Organization.query.options(
            selectinload(Organization.programs),
            selectinload(Organization.partnerships),
            selectinload(Organization.investments),
            selectinload(Organization.contacts),
            selectinload(Organization.documents)
        ).get_or_404(organization_id)
        
        # Métricas de la organización
        metrics = _get_organization_detailed_metrics(organization)
        
        # Programas con estadísticas
        programs_data = _get_organization_programs_data(organization)
        
        # Partnerships y alianzas
        partnerships_data = _get_organization_partnerships_data(organization)
        
        # Inversiones y financiamiento
        investments_data = _get_organization_investments_data(organization)
        
        # Emprendedores impactados
        entrepreneurs_data = _get_organization_entrepreneurs_data(organization)
        
        # Proyectos apoyados
        projects_data = _get_organization_projects_data(organization)
        
        # Actividad reciente
        recent_activities = _get_organization_recent_activities(organization)
        
        # Documentos categorizados
        documents_by_category = _categorize_organization_documents(organization.documents)
        
        # Contactos por rol
        contacts_by_role = _categorize_contacts_by_role(organization.contacts)
        
        # KPIs y métricas de impacto
        impact_metrics = _calculate_organization_impact_metrics(organization)
        
        # ROI y análisis financiero
        financial_analysis = _get_organization_financial_analysis(organization)
        
        # Recomendaciones del sistema
        recommendations = _generate_organization_recommendations(organization)
        
        return render_template(
            'admin/organizations/view.html',
            organization=organization,
            metrics=metrics,
            programs_data=programs_data,
            partnerships_data=partnerships_data,
            investments_data=investments_data,
            entrepreneurs_data=entrepreneurs_data,
            projects_data=projects_data,
            recent_activities=recent_activities,
            documents_by_category=documents_by_category,
            contacts_by_role=contacts_by_role,
            impact_metrics=impact_metrics,
            financial_analysis=financial_analysis,
            recommendations=recommendations
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viendo organización {organization_id}: {str(e)}")
        flash('Error al cargar los datos de la organización.', 'error')
        return redirect(url_for('admin_organizations.list_organizations'))

@admin_organizations.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_organization')
@handle_exceptions
def create_organization():
    """
    Crea una nueva organización en el ecosistema.
    Configura información básica, contactos y partnerships iniciales.
    """
    form = OrganizationForm()
    
    if form.validate_on_submit():
        try:
            # Validaciones adicionales
            if Organization.query.filter_by(name=form.name.data.strip()).first():
                flash('Ya existe una organización con este nombre.', 'error')
                return render_template('admin/organizations/create.html', form=form)
            
            if form.website.data:
                is_valid, message = validate_url(form.website.data)
                if not is_valid:
                    flash(f'Website inválido: {message}', 'error')
                    return render_template('admin/organizations/create.html', form=form)
            
            if form.tax_id.data:
                is_valid, message = validate_tax_id(form.tax_id.data, form.country.data)
                if not is_valid:
                    flash(f'Tax ID inválido: {message}', 'error')
                    return render_template('admin/organizations/create.html', form=form)
            
            # Crear organización
            organization = Organization(
                name=form.name.data.strip(),
                type=form.type.data,
                status=form.status.data or 'active',
                description=form.description.data.strip() if form.description.data else None,
                industry=form.industry.data.strip() if form.industry.data else None,
                website=form.website.data.strip() if form.website.data else None,
                email=form.email.data.lower().strip() if form.email.data else None,
                phone=form.phone.data.strip() if form.phone.data else None,
                address=form.address.data.strip() if form.address.data else None,
                city=form.city.data.strip() if form.city.data else None,
                country=form.country.data.strip() if form.country.data else None,
                postal_code=form.postal_code.data.strip() if form.postal_code.data else None,
                tax_id=form.tax_id.data.strip() if form.tax_id.data else None,
                founded_year=form.founded_year.data,
                employees_count=form.employees_count.data,
                annual_revenue=form.annual_revenue.data,
                is_public=form.is_public.data,
                stock_symbol=form.stock_symbol.data.strip() if form.stock_symbol.data else None,
                linkedin_profile=form.linkedin_profile.data.strip() if form.linkedin_profile.data else None,
                twitter_handle=form.twitter_handle.data.strip() if form.twitter_handle.data else None,
                logo_url=form.logo_url.data.strip() if form.logo_url.data else None,
                impact_score=0,  # Se calculará posteriormente
                entrepreneurs_supported=0,
                total_investment=Decimal('0.00'),
                created_by=current_user.id
            )
            
            db.session.add(organization)
            db.session.flush()  # Para obtener el ID
            
            # Crear contacto principal si se proporciona
            if form.primary_contact_name.data or form.primary_contact_email.data:
                primary_contact = Contact(
                    organization_id=organization.id,
                    name=form.primary_contact_name.data.strip() if form.primary_contact_name.data else 'Contacto Principal',
                    email=form.primary_contact_email.data.lower().strip() if form.primary_contact_email.data else None,
                    phone=form.primary_contact_phone.data.strip() if form.primary_contact_phone.data else None,
                    title=form.primary_contact_title.data.strip() if form.primary_contact_title.data else None,
                    is_primary=True,
                    created_by=current_user.id
                )
                db.session.add(primary_contact)
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_organization',
                resource_type='Organization',
                resource_id=organization.id,
                details=f'Organización creada: {organization.name} ({organization.type})'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Organización {organization.name} creada exitosamente.', 'success')
            return redirect(url_for('admin_organizations.view_organization', organization_id=organization.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando organización: {str(e)}")
            flash('Error al crear la organización.', 'error')
    
    return render_template('admin/organizations/create.html', form=form)

@admin_organizations.route('/<int:organization_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('edit_organization')
@handle_exceptions
def edit_organization(organization_id):
    """
    Edita la información de una organización existente.
    Permite modificar datos básicos, contactos y configuraciones.
    """
    organization = Organization.query.get_or_404(organization_id)
    form = OrganizationForm(obj=organization)
    
    if form.validate_on_submit():
        try:
            # Verificar nombre único (excluyendo la organización actual)
            existing = Organization.query.filter(
                and_(
                    Organization.name == form.name.data.strip(),
                    Organization.id != organization.id
                )
            ).first()
            
            if existing:
                flash('Ya existe otra organización con este nombre.', 'error')
                return render_template('admin/organizations/edit.html', form=form, organization=organization)
            
            # Validaciones
            if form.website.data:
                is_valid, message = validate_url(form.website.data)
                if not is_valid:
                    flash(f'Website inválido: {message}', 'error')
                    return render_template('admin/organizations/edit.html', form=form, organization=organization)
            
            # Almacenar valores anteriores para auditoría
            old_values = {
                'name': organization.name,
                'type': organization.type,
                'status': organization.status,
                'industry': organization.industry,
                'country': organization.country,
                'annual_revenue': organization.annual_revenue
            }
            
            # Actualizar organización
            organization.name = form.name.data.strip()
            organization.type = form.type.data
            organization.status = form.status.data
            organization.description = form.description.data.strip() if form.description.data else None
            organization.industry = form.industry.data.strip() if form.industry.data else None
            organization.website = form.website.data.strip() if form.website.data else None
            organization.email = form.email.data.lower().strip() if form.email.data else None
            organization.phone = form.phone.data.strip() if form.phone.data else None
            organization.address = form.address.data.strip() if form.address.data else None
            organization.city = form.city.data.strip() if form.city.data else None
            organization.country = form.country.data.strip() if form.country.data else None
            organization.postal_code = form.postal_code.data.strip() if form.postal_code.data else None
            organization.tax_id = form.tax_id.data.strip() if form.tax_id.data else None
            organization.founded_year = form.founded_year.data
            organization.employees_count = form.employees_count.data
            organization.annual_revenue = form.annual_revenue.data
            organization.is_public = form.is_public.data
            organization.stock_symbol = form.stock_symbol.data.strip() if form.stock_symbol.data else None
            organization.linkedin_profile = form.linkedin_profile.data.strip() if form.linkedin_profile.data else None
            organization.twitter_handle = form.twitter_handle.data.strip() if form.twitter_handle.data else None
            organization.logo_url = form.logo_url.data.strip() if form.logo_url.data else None
            organization.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Registrar cambios en auditoría
            changes = []
            for field, old_value in old_values.items():
                new_value = getattr(organization, field)
                if old_value != new_value:
                    changes.append(f'{field}: {old_value} → {new_value}')
            
            if changes:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_organization',
                    resource_type='Organization',
                    resource_id=organization.id,
                    details=f'Organización actualizada: {", ".join(changes)}'
                )
                db.session.add(activity)
                db.session.commit()
            
            flash(f'Organización {organization.name} actualizada exitosamente.', 'success')
            return redirect(url_for('admin_organizations.view_organization', organization_id=organization.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando organización {organization_id}: {str(e)}")
            flash('Error al actualizar la organización.', 'error')
    
    return render_template('admin/organizations/edit.html', form=form, organization=organization)

# ============================================================================
# GESTIÓN DE PROGRAMAS
# ============================================================================

@admin_organizations.route('/<int:organization_id>/programs')
@login_required
@admin_required
@handle_exceptions
def programs(organization_id):
    """
    Muestra todos los programas de una organización.
    """
    try:
        organization = Organization.query.get_or_404(organization_id)
        
        # Obtener programas con estadísticas
        programs = Program.query.filter_by(
            organization_id=organization.id
        ).options(
            selectinload(Program.entrepreneurs),
            selectinload(Program.projects)
        ).order_by(desc(Program.updated_at)).all()
        
        # Estadísticas de programas
        program_stats = {
            'total': len(programs),
            'active': len([p for p in programs if p.status == 'active']),
            'completed': len([p for p in programs if p.status == 'completed']),
            'upcoming': len([p for p in programs if p.status == 'upcoming']),
            'total_entrepreneurs': sum([len(p.entrepreneurs) for p in programs]),
            'total_budget': sum([p.budget for p in programs if p.budget])
        }
        
        return render_template(
            'admin/organizations/programs.html',
            organization=organization,
            programs=programs,
            program_stats=program_stats,
            program_types=PROGRAM_TYPES
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando programas: {str(e)}")
        flash('Error al cargar los programas.', 'error')
        return redirect(url_for('admin_organizations.view_organization', organization_id=organization_id))

# ============================================================================
# GESTIÓN DE PARTNERSHIPS
# ============================================================================

@admin_organizations.route('/<int:organization_id>/partnerships')
@login_required
@admin_required
@handle_exceptions
def partnerships(organization_id):
    """
    Muestra y gestiona partnerships de una organización.
    """
    try:
        organization = Organization.query.get_or_404(organization_id)
        
        # Obtener partnerships
        partnerships = Partnership.query.filter_by(
            organization_id=organization.id
        ).options(
            joinedload(Partnership.partner_organization)
        ).order_by(desc(Partnership.created_at)).all()
        
        # Estadísticas de partnerships
        partnership_stats = {
            'total': len(partnerships),
            'active': len([p for p in partnerships if p.status == 'active']),
            'pending': len([p for p in partnerships if p.status == 'pending']),
            'completed': len([p for p in partnerships if p.status == 'completed']),
            'by_type': {}
        }
        
        # Agrupar por tipo
        for partnership_type in PARTNERSHIP_TYPES:
            partnership_stats['by_type'][partnership_type] = len([
                p for p in partnerships if p.type == partnership_type
            ])
        
        return render_template(
            'admin/organizations/partnerships.html',
            organization=organization,
            partnerships=partnerships,
            partnership_stats=partnership_stats,
            partnership_types=PARTNERSHIP_TYPES
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando partnerships: {str(e)}")
        flash('Error al cargar los partnerships.', 'error')
        return redirect(url_for('admin_organizations.view_organization', organization_id=organization_id))

@admin_organizations.route('/<int:organization_id>/create-partnership', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_partnership')
@handle_exceptions
def create_partnership(organization_id):
    """
    Crea un nuevo partnership para la organización.
    """
    organization = Organization.query.get_or_404(organization_id)
    form = PartnershipForm()
    
    # Poblar choices de organizaciones
    form.partner_organization_id.choices = [
        (org.id, org.name) for org in Organization.query.filter(
            and_(
                Organization.id != organization.id,
                Organization.status == 'active'
            )
        ).order_by(Organization.name).all()
    ]
    
    if form.validate_on_submit():
        try:
            # Verificar que no exista partnership activo similar
            existing = Partnership.query.filter(
                and_(
                    Partnership.organization_id == organization.id,
                    Partnership.partner_organization_id == form.partner_organization_id.data,
                    Partnership.type == form.type.data,
                    Partnership.status.in_(['active', 'pending'])
                )
            ).first()
            
            if existing:
                flash('Ya existe un partnership similar activo o pendiente.', 'warning')
                return render_template('admin/organizations/create_partnership.html', 
                                     form=form, organization=organization)
            
            # Crear partnership
            partnership = Partnership(
                organization_id=organization.id,
                partner_organization_id=form.partner_organization_id.data,
                type=form.type.data,
                status=form.status.data or 'pending',
                name=form.name.data.strip(),
                description=form.description.data.strip() if form.description.data else None,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                budget=form.budget.data,
                currency=form.currency.data or 'USD',
                terms=form.terms.data.strip() if form.terms.data else None,
                benefits=form.benefits.data.strip() if form.benefits.data else None,
                created_by=current_user.id
            )
            
            db.session.add(partnership)
            db.session.commit()
            
            # Registrar actividad
            partner_org = Organization.query.get(form.partner_organization_id.data)
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_partnership',
                resource_type='Partnership',
                resource_id=partnership.id,
                details=f'Partnership creado: {organization.name} - {partner_org.name}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Partnership {partnership.name} creado exitosamente.', 'success')
            return redirect(url_for('admin_organizations.partnerships', organization_id=organization.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando partnership: {str(e)}")
            flash('Error al crear el partnership.', 'error')
    
    return render_template('admin/organizations/create_partnership.html', 
                         form=form, organization=organization)

# ============================================================================
# GESTIÓN DE INVERSIONES
# ============================================================================

@admin_organizations.route('/<int:organization_id>/investments')
@login_required
@admin_required
@handle_exceptions
def investments(organization_id):
    """
    Muestra las inversiones realizadas por la organización.
    """
    try:
        organization = Organization.query.get_or_404(organization_id)
        
        # Obtener inversiones
        investments = Investment.query.filter_by(
            investor_organization_id=organization.id
        ).options(
            joinedload(Investment.entrepreneur),
            joinedload(Investment.entrepreneur).joinedload(Entrepreneur.user),
            joinedload(Investment.project)
        ).order_by(desc(Investment.investment_date)).all()
        
        # Estadísticas de inversiones
        investment_stats = {
            'total_investments': len(investments),
            'total_amount': sum([inv.amount for inv in investments]),
            'active_investments': len([inv for inv in investments if inv.status == 'active']),
            'avg_investment': sum([inv.amount for inv in investments]) / len(investments) if investments else 0,
            'by_type': {},
            'by_status': {},
            'portfolio_companies': len(set([inv.entrepreneur_id for inv in investments if inv.entrepreneur_id]))
        }
        
        # Agrupar por tipo
        for inv_type in INVESTMENT_TYPES:
            investment_stats['by_type'][inv_type] = {
                'count': len([inv for inv in investments if inv.type == inv_type]),
                'amount': sum([inv.amount for inv in investments if inv.type == inv_type])
            }
        
        return render_template(
            'admin/organizations/investments.html',
            organization=organization,
            investments=investments,
            investment_stats=investment_stats,
            investment_types=INVESTMENT_TYPES
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando inversiones: {str(e)}")
        flash('Error al cargar las inversiones.', 'error')
        return redirect(url_for('admin_organizations.view_organization', organization_id=organization_id))

@admin_organizations.route('/<int:organization_id>/create-investment', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_investment')
@handle_exceptions
def create_investment(organization_id):
    """
    Registra una nueva inversión de la organización.
    """
    organization = Organization.query.get_or_404(organization_id)
    form = InvestmentForm()
    
    # Poblar choices de emprendedores
    form.entrepreneur_id.choices = [
        (ent.id, f"{ent.user.full_name} - {ent.business_name}")
        for ent in Entrepreneur.query.join(User).filter(
            User.is_active == True
        ).order_by(User.first_name).all()
    ]
    
    if form.validate_on_submit():
        try:
            # Validar monto
            is_valid, message = validate_amount(form.amount.data)
            if not is_valid:
                flash(f'Monto inválido: {message}', 'error')
                return render_template('admin/organizations/create_investment.html', 
                                     form=form, organization=organization)
            
            # Crear inversión
            investment = Investment(
                investor_organization_id=organization.id,
                entrepreneur_id=form.entrepreneur_id.data,
                project_id=form.project_id.data if form.project_id.data else None,
                type=form.type.data,
                status='active',
                amount=form.amount.data,
                currency=form.currency.data or 'USD',
                equity_percentage=form.equity_percentage.data,
                investment_date=form.investment_date.data or datetime.utcnow().date(),
                valuation=form.valuation.data,
                terms=form.terms.data.strip() if form.terms.data else None,
                notes=form.notes.data.strip() if form.notes.data else None,
                created_by=current_user.id
            )
            
            db.session.add(investment)
            
            # Actualizar totales de la organización
            organization.total_investment = (organization.total_investment or 0) + form.amount.data
            organization.entrepreneurs_supported = len(set([
                inv.entrepreneur_id for inv in organization.investments + [investment]
                if inv.entrepreneur_id
            ]))
            
            db.session.commit()
            
            # Registrar actividad
            entrepreneur = Entrepreneur.query.get(form.entrepreneur_id.data)
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_investment',
                resource_type='Investment',
                resource_id=investment.id,
                details=f'Inversión registrada: ${form.amount.data} en {entrepreneur.business_name}'
            )
            db.session.add(activity)
            
            # Notificar al emprendedor
            notification_service = NotificationService()
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='investment_received',
                title='Nueva Inversión',
                message=f'Has recibido una inversión de ${form.amount.data} de {organization.name}',
                priority='high'
            )
            
            db.session.commit()
            
            flash(f'Inversión de ${form.amount.data} registrada exitosamente.', 'success')
            return redirect(url_for('admin_organizations.investments', organization_id=organization.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando inversión: {str(e)}")
            flash('Error al registrar la inversión.', 'error')
    
    return render_template('admin/organizations/create_investment.html', 
                         form=form, organization=organization)

# ============================================================================
# GESTIÓN DE CONTACTOS
# ============================================================================

@admin_organizations.route('/<int:organization_id>/contacts')
@login_required
@admin_required
@handle_exceptions
def contacts(organization_id):
    """
    Gestiona los contactos de una organización.
    """
    try:
        organization = Organization.query.get_or_404(organization_id)
        
        # Obtener contactos
        contacts = Contact.query.filter_by(
            organization_id=organization.id
        ).order_by(desc(Contact.is_primary), Contact.name).all()
        
        # Categorizar contactos
        contacts_by_role = _categorize_contacts_by_role(contacts)
        
        return render_template(
            'admin/organizations/contacts.html',
            organization=organization,
            contacts=contacts,
            contacts_by_role=contacts_by_role
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando contactos: {str(e)}")
        flash('Error al cargar los contactos.', 'error')
        return redirect(url_for('admin_organizations.view_organization', organization_id=organization_id))

@admin_organizations.route('/<int:organization_id>/add-contact', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_organization_contacts')
@handle_exceptions
def add_contact(organization_id):
    """
    Añade un nuevo contacto a la organización.
    """
    organization = Organization.query.get_or_404(organization_id)
    form = OrganizationContactForm()
    
    if form.validate_on_submit():
        try:
            # Si se marca como principal, desmarcar otros
            if form.is_primary.data:
                Contact.query.filter_by(
                    organization_id=organization.id,
                    is_primary=True
                ).update({'is_primary': False})
            
            # Crear contacto
            contact = Contact(
                organization_id=organization.id,
                name=form.name.data.strip(),
                email=form.email.data.lower().strip() if form.email.data else None,
                phone=form.phone.data.strip() if form.phone.data else None,
                title=form.title.data.strip() if form.title.data else None,
                department=form.department.data.strip() if form.department.data else None,
                role=form.role.data or 'contact',
                is_primary=form.is_primary.data,
                notes=form.notes.data.strip() if form.notes.data else None,
                created_by=current_user.id
            )
            
            db.session.add(contact)
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='add_organization_contact',
                resource_type='Contact',
                resource_id=contact.id,
                details=f'Contacto añadido: {contact.name} ({contact.role}) - {organization.name}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Contacto {contact.name} añadido exitosamente.', 'success')
            return redirect(url_for('admin_organizations.contacts', organization_id=organization.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error añadiendo contacto: {str(e)}")
            flash('Error al añadir el contacto.', 'error')
    
    return render_template('admin/organizations/add_contact.html', 
                         form=form, organization=organization)

# ============================================================================
# EVALUACIÓN Y PERFORMANCE
# ============================================================================

@admin_organizations.route('/<int:organization_id>/evaluate', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('evaluate_organization')
@handle_exceptions
def evaluate_organization(organization_id):
    """
    Evalúa el rendimiento e impacto de una organización.
    """
    organization = Organization.query.get_or_404(organization_id)
    form = EvaluateOrganizationForm()
    
    if form.validate_on_submit():
        try:
            # Preparar datos de evaluación
            evaluation_data = {
                'impact_quality': form.impact_quality.data,
                'program_effectiveness': form.program_effectiveness.data,
                'financial_health': form.financial_health.data,
                'partnership_value': form.partnership_value.data,
                'innovation_support': form.innovation_support.data,
                'sustainability': form.sustainability.data,
                'communication': form.communication.data,
                'strategic_alignment': form.strategic_alignment.data,
                'notes': form.notes.data.strip() if form.notes.data else None,
                'recommendations': form.recommendations.data.strip() if form.recommendations.data else None,
                'evaluator_id': current_user.id,
                'evaluation_date': datetime.utcnow()
            }
            
            # Calcular score promedio
            rating_fields = [
                'impact_quality', 'program_effectiveness', 'financial_health',
                'partnership_value', 'innovation_support', 'sustainability',
                'communication', 'strategic_alignment'
            ]
            total_score = sum([evaluation_data[field] for field in rating_fields]) / len(rating_fields)
            
            # Actualizar organización
            organization.evaluation_data = evaluation_data  # JSON field
            organization.last_evaluation_at = datetime.utcnow()
            organization.impact_score = total_score
            
            # Determinar nivel de partnership
            if total_score >= 4.5:
                partnership_level = 'strategic'
            elif total_score >= 3.5:
                partnership_level = 'preferred'
            elif total_score >= 2.5:
                partnership_level = 'standard'
            else:
                partnership_level = 'limited'
            
            organization.partnership_level = partnership_level
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='evaluate_organization',
                resource_type='Organization',
                resource_id=organization.id,
                details=f'Evaluación completada. Score: {total_score:.1f}/5.0, Nivel: {partnership_level}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Evaluación completada. Score: {total_score:.1f}/5.0 ({partnership_level})', 'success')
            return redirect(url_for('admin_organizations.view_organization', organization_id=organization.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error evaluando organización: {str(e)}")
            flash('Error al guardar la evaluación.', 'error')
    
    return render_template('admin/organizations/evaluate.html', 
                         form=form, organization=organization)

# ============================================================================
# ANALYTICS Y ESTADÍSTICAS
# ============================================================================

@admin_organizations.route('/analytics')
@login_required
@admin_required
@cache_result(timeout=300)
def analytics():
    """
    Dashboard de analytics para organizaciones del ecosistema.
    """
    try:
        analytics_service = AnalyticsService()
        
        # Métricas generales
        general_metrics = _get_comprehensive_organization_metrics()
        
        # Datos para gráficos
        charts_data = {
            'organizations_by_type': analytics_service.get_organizations_by_type(),
            'investment_trends': analytics_service.get_investment_trends(days=365),
            'partnership_distribution': analytics_service.get_partnership_distribution(),
            'impact_vs_investment': analytics_service.get_impact_vs_investment_correlation(),
            'geographic_presence': analytics_service.get_organizations_geographic_data(),
            'program_effectiveness': analytics_service.get_program_effectiveness_metrics(),
            'revenue_distribution': analytics_service.get_organization_revenue_distribution()
        }
        
        # Top performers
        top_performers = _get_top_performing_organizations(limit=10)
        
        # Organizaciones que necesitan atención
        needs_attention = _get_organizations_needing_attention(limit=10)
        
        # ROI del ecosistema
        ecosystem_roi = _calculate_ecosystem_roi()
        
        return render_template(
            'admin/organizations/analytics.html',
            general_metrics=general_metrics,
            charts_data=charts_data,
            top_performers=top_performers,
            needs_attention=needs_attention,
            ecosystem_roi=ecosystem_roi
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando analytics: {str(e)}")
        flash('Error al cargar los analytics.', 'error')
        return redirect(url_for('admin_organizations.list_organizations'))

# ============================================================================
# ACCIONES EN LOTE
# ============================================================================

@admin_organizations.route('/bulk-actions', methods=['POST'])
@login_required
@admin_required
@permission_required('bulk_organization_actions')
@handle_exceptions
def bulk_actions():
    """
    Ejecuta acciones en lote sobre múltiples organizaciones.
    """
    form = BulkOrganizationActionForm()
    
    if form.validate_on_submit():
        try:
            org_ids = [int(id) for id in form.organization_ids.data.split(',') if id.strip()]
            action = form.action.data
            
            if not org_ids:
                flash('No se seleccionaron organizaciones.', 'warning')
                return redirect(url_for('admin_organizations.list_organizations'))
            
            organizations = Organization.query.filter(
                Organization.id.in_(org_ids)
            ).all()
            
            success_count = 0
            
            for org in organizations:
                try:
                    if action == 'activate':
                        org.status = 'active'
                        success_count += 1
                        
                    elif action == 'deactivate':
                        org.status = 'inactive'
                        success_count += 1
                        
                    elif action == 'mark_strategic':
                        org.partnership_level = 'strategic'
                        success_count += 1
                        
                    elif action == 'update_currency':
                        if form.new_currency.data:
                            # Actualizar currency en inversiones y partnerships
                            Investment.query.filter_by(
                                investor_organization_id=org.id
                            ).update({'currency': form.new_currency.data})
                            success_count += 1
                            
                    elif action == 'send_notification':
                        # Enviar notificación a contactos principales
                        primary_contacts = Contact.query.filter_by(
                            organization_id=org.id,
                            is_primary=True
                        ).all()
                        
                        for contact in primary_contacts:
                            if contact.email:
                                email_service = EmailService()
                                email_service.send_organization_notification(
                                    contact,
                                    form.notification_title.data,
                                    form.notification_message.data
                                )
                        success_count += 1
                        
                except Exception as e:
                    current_app.logger.warning(f"Error procesando organización {org.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='bulk_organization_action',
                resource_type='Organization',
                details=f'Acción en lote: {action} aplicada a {success_count} organizaciones'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Acción aplicada exitosamente a {success_count} organización(es).', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error en acción en lote: {str(e)}")
            flash('Error al ejecutar la acción en lote.', 'error')
    else:
        flash('Datos de formulario inválidos.', 'error')
    
    return redirect(url_for('admin_organizations.list_organizations'))

# ============================================================================
# EXPORTACIÓN
# ============================================================================

@admin_organizations.route('/export')
@login_required
@admin_required
@permission_required('export_organizations')
@handle_exceptions
def export_organizations():
    """
    Exporta datos de organizaciones en diferentes formatos.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_investments = request.args.get('include_investments', 'false') == 'true'
        include_partnerships = request.args.get('include_partnerships', 'false') == 'true'
        type_filter = request.args.get('type', 'all')
        
        # Construir query
        query = Organization.query.options(
            selectinload(Organization.programs),
            selectinload(Organization.partnerships),
            selectinload(Organization.investments),
            selectinload(Organization.contacts)
        )
        
        if type_filter != 'all':
            query = query.filter(Organization.type == type_filter)
        
        organizations = query.order_by(Organization.created_at.desc()).all()
        
        # Preparar datos de exportación
        export_data = []
        for org in organizations:
            row = {
                'ID': org.id,
                'Nombre': org.name,
                'Tipo': org.type,
                'Estado': org.status,
                'Industria': org.industry or 'N/A',
                'País': org.country or 'N/A',
                'Ciudad': org.city or 'N/A',
                'Website': org.website or 'N/A',
                'Email': org.email or 'N/A',
                'Teléfono': org.phone or 'N/A',
                'Año de Fundación': org.founded_year or 'N/A',
                'Empleados': org.employees_count or 'N/A',
                'Ingresos Anuales': f"${org.annual_revenue:,.2f}" if org.annual_revenue else 'N/A',
                'Es Pública': 'Sí' if org.is_public else 'No',
                'Símbolo Bursátil': org.stock_symbol or 'N/A',
                'Score de Impacto': f"{org.impact_score:.1f}" if org.impact_score else 'N/A',
                'Nivel de Partnership': org.partnership_level or 'N/A',
                'Emprendedores Apoyados': org.entrepreneurs_supported or 0,
                'Inversión Total': f"${org.total_investment:,.2f}" if org.total_investment else '$0.00',
                'Programas Activos': len([p for p in org.programs if p.status == 'active']),
                'LinkedIn': org.linkedin_profile or 'N/A',
                'Twitter': org.twitter_handle or 'N/A',
                'Fecha de Registro': org.created_at.strftime('%Y-%m-%d'),
                'Última Actualización': org.updated_at.strftime('%Y-%m-%d %H:%M') if org.updated_at else 'N/A'
            }
            
            # Incluir datos de inversiones si se solicita
            if include_investments:
                total_investments = len(org.investments)
                active_investments = len([inv for inv in org.investments if inv.status == 'active'])
                row['Total Inversiones'] = total_investments
                row['Inversiones Activas'] = active_investments
                
            # Incluir datos de partnerships si se solicita
            if include_partnerships:
                total_partnerships = len(org.partnerships)
                active_partnerships = len([p for p in org.partnerships if p.status == 'active'])
                row['Total Partnerships'] = total_partnerships
                row['Partnerships Activos'] = active_partnerships
            
            export_data.append(row)
        
        # Generar archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            filename = f'organizaciones_{timestamp}.xlsx'
            return export_to_excel(export_data, filename, 'Organizaciones')
        elif export_format == 'csv':
            filename = f'organizaciones_{timestamp}.csv'
            return export_to_csv(export_data, filename)
        elif export_format == 'pdf':
            filename = f'organizaciones_{timestamp}.pdf'
            return export_to_pdf(export_data, filename, 'Reporte de Organizaciones')
        
    except Exception as e:
        current_app.logger.error(f"Error exportando organizaciones: {str(e)}")
        flash('Error al exportar los datos.', 'error')
        return redirect(url_for('admin_organizations.list_organizations'))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_organizations.route('/api/search')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_search_organizations():
    """API para búsqueda de organizaciones en tiempo real."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        org_type = request.args.get('type', '')
        
        if len(query) < 2:
            return jsonify({'organizations': []})
        
        search_query = Organization.query.filter(
            or_(
                Organization.name.ilike(f'%{query}%'),
                Organization.industry.ilike(f'%{query}%'),
                Organization.description.ilike(f'%{query}%')
            )
        )
        
        if org_type:
            search_query = search_query.filter(Organization.type == org_type)
        
        organizations = search_query.limit(limit).all()
        
        return jsonify({
            'organizations': [
                {
                    'id': org.id,
                    'name': org.name,
                    'type': org.type,
                    'industry': org.industry,
                    'country': org.country,
                    'status': org.status,
                    'impact_score': org.impact_score,
                    'entrepreneurs_supported': org.entrepreneurs_supported,
                    'total_investment': float(org.total_investment) if org.total_investment else 0
                }
                for org in organizations
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_organization_statistics():
    """Obtiene estadísticas básicas de organizaciones."""
    return {
        'total': Organization.query.count(),
        'active': Organization.query.filter_by(status='active').count(),
        'by_type': {
            org_type: Organization.query.filter_by(type=org_type).count()
            for org_type in ORGANIZATION_TYPES
        },
        'with_partnerships': Organization.query.filter(
            Organization.partnerships.any(Partnership.status == 'active')
        ).count(),
        'total_investment': db.session.query(
            func.sum(Organization.total_investment)
        ).scalar() or 0,
        'avg_impact_score': db.session.query(
            func.avg(Organization.impact_score)
        ).filter(Organization.impact_score.isnot(None)).scalar() or 0,
        'entrepreneurs_supported': db.session.query(
            func.sum(Organization.entrepreneurs_supported)
        ).scalar() or 0
    }

def _get_organization_detailed_metrics(organization):
    """Obtiene métricas detalladas de una organización."""
    return {
        'age_days': (datetime.utcnow() - organization.created_at).days,
        'programs_count': len(organization.programs),
        'active_programs': len([p for p in organization.programs if p.status == 'active']),
        'partnerships_count': len(organization.partnerships),
        'active_partnerships': len([p for p in organization.partnerships if p.status == 'active']),
        'investments_count': len(organization.investments),
        'portfolio_size': organization.entrepreneurs_supported or 0,
        'avg_investment': (organization.total_investment / len(organization.investments)) if organization.investments else 0,
        'contacts_count': len(organization.contacts),
        'documents_count': len(organization.documents),
        'impact_score': organization.impact_score or 0,
        'partnership_level': organization.partnership_level or 'standard'
    }

def _get_organization_programs_data(organization):
    """Obtiene datos de programas de la organización."""
    programs = organization.programs
    
    return {
        'total': len(programs),
        'by_status': {
            'active': len([p for p in programs if p.status == 'active']),
            'completed': len([p for p in programs if p.status == 'completed']),
            'upcoming': len([p for p in programs if p.status == 'upcoming'])
        },
        'total_budget': sum([p.budget for p in programs if p.budget]),
        'total_participants': sum([len(p.entrepreneurs) for p in programs])
    }

def _get_organization_partnerships_data(organization):
    """Obtiene datos de partnerships de la organización."""
    partnerships = organization.partnerships
    
    return {
        'total': len(partnerships),
        'by_status': {
            status: len([p for p in partnerships if p.status == status])
            for status in ['active', 'pending', 'completed', 'cancelled']
        },
        'by_type': {
            ptype: len([p for p in partnerships if p.type == ptype])
            for ptype in PARTNERSHIP_TYPES
        },
        'total_budget': sum([p.budget for p in partnerships if p.budget])
    }

def _get_organization_investments_data(organization):
    """Obtiene datos de inversiones de la organización."""
    investments = organization.investments
    
    return {
        'total_investments': len(investments),
        'total_amount': sum([inv.amount for inv in investments]),
        'by_type': {
            itype: {
                'count': len([inv for inv in investments if inv.type == itype]),
                'amount': sum([inv.amount for inv in investments if inv.type == itype])
            }
            for itype in INVESTMENT_TYPES
        },
        'avg_investment': sum([inv.amount for inv in investments]) / len(investments) if investments else 0,
        'portfolio_companies': len(set([inv.entrepreneur_id for inv in investments if inv.entrepreneur_id]))
    }

def _get_organization_entrepreneurs_data(organization):
    """Obtiene datos de emprendedores impactados por la organización."""
    # Emprendedores de programas + inversiones
    program_entrepreneurs = set()
    for program in organization.programs:
        program_entrepreneurs.update([e.id for e in program.entrepreneurs])
    
    investment_entrepreneurs = set([
        inv.entrepreneur_id for inv in organization.investments 
        if inv.entrepreneur_id
    ])
    
    all_entrepreneurs = program_entrepreneurs.union(investment_entrepreneurs)
    
    return {
        'total_unique': len(all_entrepreneurs),
        'from_programs': len(program_entrepreneurs),
        'from_investments': len(investment_entrepreneurs),
        'overlap': len(program_entrepreneurs.intersection(investment_entrepreneurs))
    }

def _get_organization_projects_data(organization):
    """Obtiene datos de proyectos apoyados por la organización."""
    # Proyectos de emprendedores en programas
    projects = []
    for program in organization.programs:
        for entrepreneur in program.entrepreneurs:
            projects.extend(entrepreneur.projects)
    
    return {
        'total': len(projects),
        'active': len([p for p in projects if p.status == 'active']),
        'completed': len([p for p in projects if p.status == 'completed']),
        'avg_progress': sum([p.progress for p in projects]) / len(projects) if projects else 0
    }

def _get_organization_recent_activities(organization):
    """Obtiene actividad reciente relacionada con la organización."""
    return ActivityLog.query.filter(
        or_(
            and_(
                ActivityLog.resource_type == 'Organization',
                ActivityLog.resource_id == organization.id
            ),
            and_(
                ActivityLog.resource_type.in_(['Program', 'Partnership', 'Investment']),
                ActivityLog.details.ilike(f'%{organization.name}%')
            )
        )
    ).options(
        joinedload(ActivityLog.user)
    ).order_by(desc(ActivityLog.created_at)).limit(15).all()

def _categorize_organization_documents(documents):
    """Categoriza documentos de la organización."""
    categories = {
        'legal': [],
        'financial': [],
        'agreements': [],
        'presentations': [],
        'reports': [],
        'other': []
    }
    
    for doc in documents:
        doc_name_lower = doc.name.lower()
        if any(word in doc_name_lower for word in ['legal', 'contract', 'agreement']):
            categories['legal'].append(doc)
        elif any(word in doc_name_lower for word in ['financial', 'budget', 'invoice']):
            categories['financial'].append(doc)
        elif any(word in doc_name_lower for word in ['agreement', 'partnership', 'mou']):
            categories['agreements'].append(doc)
        elif any(word in doc_name_lower for word in ['presentation', 'pitch', 'deck']):
            categories['presentations'].append(doc)
        elif any(word in doc_name_lower for word in ['report', 'analysis', 'study']):
            categories['reports'].append(doc)
        else:
            categories['other'].append(doc)
    
    return categories

def _categorize_contacts_by_role(contacts):
    """Categoriza contactos por rol."""
    roles = {}
    for contact in contacts:
        role = contact.role or 'contact'
        if role not in roles:
            roles[role] = []
        roles[role].append(contact)
    
    return roles

def _calculate_organization_impact_metrics(organization):
    """Calcula métricas de impacto de la organización."""
    # Emprendedores únicos impactados
    unique_entrepreneurs = set()
    for program in organization.programs:
        unique_entrepreneurs.update([e.id for e in program.entrepreneurs])
    for investment in organization.investments:
        if investment.entrepreneur_id:
            unique_entrepreneurs.add(investment.entrepreneur_id)
    
    # Proyectos completados
    completed_projects = 0
    for program in organization.programs:
        for entrepreneur in program.entrepreneurs:
            completed_projects += len([p for p in entrepreneur.projects if p.status == 'completed'])
    
    # Jobs creados (estimado)
    estimated_jobs = len(unique_entrepreneurs) * 3  # Promedio estimado
    
    return {
        'entrepreneurs_impacted': len(unique_entrepreneurs),
        'projects_completed': completed_projects,
        'estimated_jobs_created': estimated_jobs,
        'total_investment': float(organization.total_investment) if organization.total_investment else 0,
        'programs_delivered': len([p for p in organization.programs if p.status == 'completed']),
        'success_rate': (completed_projects / max(1, len(unique_entrepreneurs))) * 100
    }

def _get_organization_financial_analysis(organization):
    """Obtiene análisis financiero de la organización."""
    investments = organization.investments
    
    if not investments:
        return {
            'total_invested': 0,
            'avg_investment': 0,
            'roi_estimate': 0,
            'portfolio_valuation': 0
        }
    
    total_invested = sum([inv.amount for inv in investments])
    avg_investment = total_invested / len(investments)
    
    # ROI estimado basado en valuaciones actuales
    current_valuations = sum([inv.valuation for inv in investments if inv.valuation])
    roi_estimate = ((current_valuations - total_invested) / total_invested * 100) if total_invested > 0 else 0
    
    return {
        'total_invested': total_invested,
        'avg_investment': avg_investment,
        'roi_estimate': roi_estimate,
        'portfolio_valuation': current_valuations,
        'investment_count': len(investments),
        'avg_equity': sum([inv.equity_percentage for inv in investments if inv.equity_percentage]) / len([inv for inv in investments if inv.equity_percentage]) if any(inv.equity_percentage for inv in investments) else 0
    }

def _generate_organization_recommendations(organization):
    """Genera recomendaciones automáticas para la organización."""
    recommendations = []
    
    # Recomendaciones basadas en impacto
    if organization.impact_score and organization.impact_score < 3.0:
        recommendations.append({
            'type': 'improvement',
            'priority': 'high',
            'title': 'Mejorar Impacto',
            'description': 'El score de impacto es bajo. Revisar efectividad de programas.',
            'action': 'Evaluar programas y optimizar estrategia'
        })
    
    # Recomendaciones basadas en partnerships
    if not organization.partnerships:
        recommendations.append({
            'type': 'opportunity',
            'priority': 'medium',
            'title': 'Desarrollar Partnerships',
            'description': 'No tiene partnerships activos.',
            'action': 'Identificar organizaciones complementarias'
        })
    
    # Recomendaciones basadas en portfolio
    if organization.type in ['vc', 'investor'] and len(organization.investments) < 5:
        recommendations.append({
            'type': 'growth',
            'priority': 'medium',
            'title': 'Expandir Portfolio',
            'description': 'Portfolio pequeño para una organización inversora.',
            'action': 'Buscar nuevas oportunidades de inversión'
        })
    
    return recommendations

def _get_comprehensive_organization_metrics():
    """Obtiene métricas comprehensivas para analytics."""
    return {
        'total_organizations': Organization.query.count(),
        'total_investment': db.session.query(func.sum(Organization.total_investment)).scalar() or 0,
        'avg_impact_score': db.session.query(func.avg(Organization.impact_score)).filter(
            Organization.impact_score.isnot(None)
        ).scalar() or 0,
        'total_entrepreneurs_supported': db.session.query(
            func.sum(Organization.entrepreneurs_supported)
        ).scalar() or 0,
        'active_partnerships': Partnership.query.filter_by(status='active').count(),
        'ecosystem_roi': _calculate_ecosystem_roi()
    }

def _get_top_performing_organizations(limit=10):
    """Obtiene organizaciones con mejor desempeño."""
    return Organization.query.filter(
        Organization.impact_score.isnot(None)
    ).order_by(
        desc(Organization.impact_score),
        desc(Organization.entrepreneurs_supported)
    ).limit(limit).all()

def _get_organizations_needing_attention(limit=10):
    """Obtiene organizaciones que necesitan atención."""
    return Organization.query.filter(
        or_(
            Organization.impact_score < 2.0,
            Organization.updated_at < datetime.utcnow() - timedelta(days=90),
            and_(
                Organization.type.in_(['incubator', 'accelerator']),
                Organization.entrepreneurs_supported == 0
            )
        )
    ).order_by(
        Organization.impact_score.asc(),
        Organization.updated_at.asc()
    ).limit(limit).all()

def _calculate_ecosystem_roi():
    """Calcula ROI del ecosistema completo."""
    total_investment = db.session.query(func.sum(Organization.total_investment)).scalar() or 0
    
    if total_investment == 0:
        return 0
    
    # Valuación estimada del ecosistema (simplificado)
    total_valuations = db.session.query(func.sum(Investment.valuation)).filter(
        Investment.valuation.isnot(None)
    ).scalar() or 0
    
    if total_valuations == 0:
        return 0
    
    return ((total_valuations - total_investment) / total_investment * 100)