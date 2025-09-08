"""
Gestión de Aliados/Mentores - Panel Administrativo
==================================================

Este módulo gestiona todas las funcionalidades relacionadas con aliados/mentores
desde el panel administrativo, incluyendo gestión, evaluación, asignaciones y performance.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta, timezone
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
    USER_ROLES, MENTORSHIP_STATUS, AVAILABILITY_TYPES, EXPERTISE_AREAS,
    PAYMENT_STATUS, EVALUATION_CRITERIA, PRIORITY_LEVELS, CURRENCY_TYPES
)

# Importaciones de modelos
from app.models import (
    User, Ally, Entrepreneur, Mentorship, Meeting, Document, Task, 
    ActivityLog, Analytics, Notification, Program, Organization
)

# Importaciones de servicios
from app.services.mentorship_service import MentorshipService
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.currency import CurrencyService

# Importaciones de formularios
from app.forms.admin import (
    AllyFilterForm, AllyProfileForm, EvaluateAllyForm, AllyAvailabilityForm,
    BulkAllyActionForm, AssignEntrepreneurForm, SetAllyRatesForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.formatters import format_currency, format_percentage, format_number, format_hours
from app.utils.date_utils import get_date_range, format_date_range, get_business_hours
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.validators import validate_hourly_rate, validate_availability

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_allies = Blueprint('admin_allies', __name__, url_prefix='/admin/allies')

# ============================================================================
# VISTAS PRINCIPALES - LISTADO Y GESTIÓN
# ============================================================================

@admin_allies.route('/')
@admin_allies.route('/list')
@login_required
@admin_required
@handle_exceptions
def list_allies():
    """
    Lista todos los aliados/mentores con filtros avanzados y métricas.
    Incluye información de disponibilidad, expertise, rendimiento y asignaciones.
    """
    try:
        # Parámetros de consulta
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        expertise_filter = request.args.get('expertise', 'all')
        availability_filter = request.args.get('availability', 'all')
        experience_filter = request.args.get('experience', 'all')
        rating_filter = request.args.get('rating', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        location_filter = request.args.get('location', 'all')
        
        # Query base con optimizaciones
        query = Ally.query.options(
            joinedload(Ally.user),
            selectinload(Ally.mentorships),
            selectinload(Ally.assigned_entrepreneurs)
        ).join(User)
        
        # Aplicar filtros de búsqueda
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                Ally.company.ilike(f'%{search}%'),
                Ally.title.ilike(f'%{search}%'),
                Ally.bio.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtros específicos de aliados
        if expertise_filter != 'all':
            query = query.filter(
                Ally.expertise_areas.any(expertise_filter)
            )
            
        if availability_filter == 'available':
            query = query.filter(
                and_(
                    Ally.is_available == True,
                    Ally.max_entrepreneurs > func.coalesce(Ally.current_entrepreneurs, 0)
                )
            )
        elif availability_filter == 'full':
            query = query.filter(
                Ally.current_entrepreneurs >= Ally.max_entrepreneurs
            )
        elif availability_filter == 'inactive':
            query = query.filter(Ally.is_available == False)
            
        if experience_filter == 'senior':
            query = query.filter(Ally.years_experience >= 10)
        elif experience_filter == 'mid':
            query = query.filter(
                and_(Ally.years_experience >= 5, Ally.years_experience < 10)
            )
        elif experience_filter == 'junior':
            query = query.filter(Ally.years_experience < 5)
            
        if rating_filter == 'excellent':
            query = query.filter(Ally.average_rating >= 4.5)
        elif rating_filter == 'good':
            query = query.filter(
                and_(Ally.average_rating >= 3.5, Ally.average_rating < 4.5)
            )
        elif rating_filter == 'needs_improvement':
            query = query.filter(Ally.average_rating < 3.5)
            
        if location_filter != 'all':
            query = query.filter(User.country == location_filter)
        
        # Solo usuarios activos por defecto
        query = query.filter(User.is_active == True)
        
        # Aplicar ordenamiento
        if sort_by == 'name':
            order_field = User.first_name
        elif sort_by == 'rating':
            order_field = Ally.average_rating
        elif sort_by == 'experience':
            order_field = Ally.years_experience
        elif sort_by == 'entrepreneurs':
            order_field = Ally.current_entrepreneurs
        elif sort_by == 'hourly_rate':
            order_field = Ally.hourly_rate
        elif sort_by == 'last_activity':
            order_field = Ally.last_activity_at
        else:  # created_at por defecto
            order_field = User.created_at
            
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc().nulls_last())
        
        # Paginación
        allies = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
            max_per_page=50
        )
        
        # Estadísticas para el dashboard
        stats = _get_ally_statistics()
        
        # Países disponibles para filtros
        countries = db.session.query(User.country).filter(
            User.country.isnot(None)
        ).distinct().all()
        countries = [country[0] for country in countries if country[0]]
        
        # Formularios
        filter_form = AllyFilterForm(request.args)
        bulk_action_form = BulkAllyActionForm()
        
        return render_template(
            'admin/allies/list.html',
            allies=allies,
            stats=stats,
            countries=countries,
            filter_form=filter_form,
            bulk_action_form=bulk_action_form,
            current_filters={
                'search': search,
                'expertise': expertise_filter,
                'availability': availability_filter,
                'experience': experience_filter,
                'rating': rating_filter,
                'location': location_filter,
                'sort': sort_by,
                'order': sort_order
            },
            expertise_areas=EXPERTISE_AREAS,
            availability_types=AVAILABILITY_TYPES
        )
        
    except Exception as e:
        current_app.logger.error(f"Error listando aliados: {str(e)}")
        flash('Error al cargar la lista de aliados.', 'error')
        return redirect(url_for('admin_dashboard.index'))

@admin_allies.route('/<int:ally_id>')
@login_required
@admin_required
@handle_exceptions
def view_ally(ally_id):
    """
    Vista detallada de un aliado/mentor específico.
    Incluye métricas de rendimiento, emprendedores asignados, historial y evaluaciones.
    """
    try:
        ally = Ally.query.options(
            joinedload(Ally.user),
            selectinload(Ally.mentorships),
            selectinload(Ally.assigned_entrepreneurs),
            selectinload(Ally.assigned_entrepreneurs).joinedload(Entrepreneur.user)
        ).get_or_404(ally_id)
        
        # Verificar acceso
        if not ally.user.is_active:
            flash('Este aliado está inactivo.', 'warning')
        
        # Métricas del aliado
        metrics = _get_ally_detailed_metrics(ally)
        
        # Emprendedores asignados con datos
        entrepreneurs_data = _get_ally_entrepreneurs_data(ally)
        
        # Historial de mentorías
        mentorship_history = _get_ally_mentorship_history(ally)
        
        # Reuniones y sesiones
        meetings_data = _get_ally_meetings_data(ally)
        
        # Actividad reciente
        recent_activities = ActivityLog.query.filter_by(
            user_id=ally.user_id
        ).options(joinedload(ActivityLog.user)).order_by(
            desc(ActivityLog.created_at)
        ).limit(15).all()
        
        # Evaluaciones y feedback
        evaluations = _get_ally_evaluations(ally)
        
        # Disponibilidad y horarios
        availability_data = _get_ally_availability_data(ally)
        
        # Earnings y pagos (si aplica)
        earnings_data = _get_ally_earnings_data(ally)
        
        # Tendencias de rendimiento
        performance_trends = _get_ally_performance_trends(ally)
        
        # Recomendaciones del sistema
        recommendations = _generate_ally_recommendations(ally)
        
        return render_template(
            'admin/allies/view.html',
            ally=ally,
            metrics=metrics,
            entrepreneurs_data=entrepreneurs_data,
            mentorship_history=mentorship_history,
            meetings_data=meetings_data,
            recent_activities=recent_activities,
            evaluations=evaluations,
            availability_data=availability_data,
            earnings_data=earnings_data,
            performance_trends=performance_trends,
            recommendations=recommendations
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viendo aliado {ally_id}: {str(e)}")
        flash('Error al cargar los datos del aliado.', 'error')
        return redirect(url_for('admin_allies.list_allies'))

@admin_allies.route('/<int:ally_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('edit_ally')
@handle_exceptions
def edit_ally(ally_id):
    """
    Edita el perfil de un aliado/mentor.
    Permite modificar expertise, tarifas, disponibilidad y configuraciones.
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get_or_404(ally_id)
    
    form = AllyProfileForm(obj=ally)
    
    if form.validate_on_submit():
        try:
            # Validar tarifa por hora si se proporciona
            if form.hourly_rate.data:
                is_valid, message = validate_hourly_rate(form.hourly_rate.data)
                if not is_valid:
                    flash(f'Tarifa inválida: {message}', 'error')
                    return render_template('admin/allies/edit.html', form=form, ally=ally)
            
            # Almacenar valores anteriores para auditoría
            old_values = {
                'title': ally.title,
                'company': ally.company,
                'hourly_rate': ally.hourly_rate,
                'expertise_areas': ally.expertise_areas,
                'is_available': ally.is_available,
                'max_entrepreneurs': ally.max_entrepreneurs,
                'years_experience': ally.years_experience
            }
            
            # Actualizar información básica
            ally.title = form.title.data.strip() if form.title.data else None
            ally.company = form.company.data.strip() if form.company.data else None
            ally.bio = form.bio.data.strip() if form.bio.data else None
            ally.years_experience = form.years_experience.data
            ally.hourly_rate = form.hourly_rate.data
            ally.currency = form.currency.data or 'USD'
            ally.expertise_areas = form.expertise_areas.data or []
            ally.industries = form.industries.data or []
            ally.languages = form.languages.data or []
            ally.is_available = form.is_available.data
            ally.max_entrepreneurs = form.max_entrepreneurs.data or 5
            ally.availability_hours = form.availability_hours.data or 20
            ally.preferred_communication = form.preferred_communication.data or 'video'
            ally.linkedin_profile = form.linkedin_profile.data.strip() if form.linkedin_profile.data else None
            ally.website = form.website.data.strip() if form.website.data else None
            ally.updated_at = datetime.now(timezone.utc)
            
            # Validar disponibilidad si cambió
            if form.is_available.data != old_values['is_available']:
                if form.is_available.data and ally.current_entrepreneurs >= ally.max_entrepreneurs:
                    flash('No se puede activar disponibilidad: capacidad máxima alcanzada.', 'warning')
                    ally.is_available = False
            
            db.session.commit()
            
            # Registrar cambios en auditoría
            changes = []
            for field, old_value in old_values.items():
                new_value = getattr(ally, field)
                if old_value != new_value:
                    changes.append(f'{field}: {old_value} → {new_value}')
            
            if changes:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_ally_profile',
                    resource_type='Ally',
                    resource_id=ally.id,
                    details=f'Perfil actualizado: {", ".join(changes)}'
                )
                db.session.add(activity)
                
                # Notificar cambios importantes al aliado
                if 'is_available' in changes or 'hourly_rate' in changes:
                    notification_service = NotificationService()
                    notification_service.send_notification(
                        user_id=ally.user_id,
                        type='profile_updated',
                        title='Perfil Actualizado',
                        message='Tu perfil de mentor ha sido actualizado por un administrador.',
                        priority='medium'
                    )
                
                db.session.commit()
            
            flash(f'Perfil de {ally.user.full_name} actualizado exitosamente.', 'success')
            return redirect(url_for('admin_allies.view_ally', ally_id=ally.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando aliado {ally_id}: {str(e)}")
            flash('Error al actualizar el perfil del aliado.', 'error')
    
    return render_template('admin/allies/edit.html', form=form, ally=ally)

# ============================================================================
# GESTIÓN DE ASIGNACIONES Y MENTORÍAS
# ============================================================================

@admin_allies.route('/<int:ally_id>/assign-entrepreneur', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('assign_entrepreneur')
@handle_exceptions
def assign_entrepreneur(ally_id):
    """
    Asigna un emprendedor a un aliado/mentor.
    Considera compatibilidad, disponibilidad y carga de trabajo.
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get_or_404(ally_id)
    
    form = AssignEntrepreneurForm()
    
    # Verificar disponibilidad del mentor
    if ally.current_entrepreneurs >= ally.max_entrepreneurs:
        flash('Este mentor ha alcanzado su capacidad máxima de emprendedores.', 'warning')
        return redirect(url_for('admin_allies.view_ally', ally_id=ally_id))
    
    # Obtener emprendedores disponibles
    available_entrepreneurs = _get_available_entrepreneurs_for_ally(ally)
    form.entrepreneur_id.choices = [
        (entrepreneur.id, f"{entrepreneur.user.full_name} - {entrepreneur.business_name}")
        for entrepreneur in available_entrepreneurs
    ]
    
    if form.validate_on_submit():
        try:
            entrepreneur = Entrepreneur.query.get(form.entrepreneur_id.data)
            if not entrepreneur:
                flash('Emprendedor seleccionado no válido.', 'error')
                return render_template('admin/allies/assign_entrepreneur.html', 
                                     form=form, ally=ally)
            
            # Verificar que el emprendedor no tenga mentor activo
            if entrepreneur.assigned_mentor_id:
                flash('Este emprendedor ya tiene un mentor asignado.', 'warning')
                return render_template('admin/allies/assign_entrepreneur.html', 
                                     form=form, ally=ally)
            
            mentorship_service = MentorshipService()
            
            # Crear sesión de mentoría
            mentorship = mentorship_service.create_mentorship(
                entrepreneur_id=entrepreneur.id,
                mentor_id=ally.id,
                program_id=entrepreneur.program_id,
                objectives=form.objectives.data.strip() if form.objectives.data else None,
                expected_duration=form.expected_duration.data,
                hourly_rate=ally.hourly_rate,
                notes=f'Asignado por admin: {current_user.full_name}'
            )
            
            # Actualizar contadores
            entrepreneur.assigned_mentor_id = ally.id
            entrepreneur.mentor_assigned_at = datetime.now(timezone.utc)
            ally.current_entrepreneurs = (ally.current_entrepreneurs or 0) + 1
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='assign_entrepreneur_to_ally',
                resource_type='Mentorship',
                resource_id=mentorship.id,
                details=f'Emprendedor {entrepreneur.user.full_name} asignado a mentor {ally.user.full_name}'
            )
            db.session.add(activity)
            
            # Notificar a ambas partes
            notification_service = NotificationService()
            
            # Notificar al mentor
            notification_service.send_notification(
                user_id=ally.user_id,
                type='entrepreneur_assigned',
                title='Nuevo Emprendedor Asignado',
                message=f'Se te ha asignado como emprendedor a {entrepreneur.user.full_name}',
                priority='medium'
            )
            
            # Notificar al emprendedor
            notification_service.send_notification(
                user_id=entrepreneur.user_id,
                type='mentor_assigned',
                title='Mentor Asignado',
                message=f'Se te ha asignado como mentor a {ally.user.full_name}',
                priority='medium'
            )
            
            # Enviar emails
            try:
                email_service = EmailService()
                email_service.send_mentorship_assignment_notification(entrepreneur, ally)
            except Exception as e:
                current_app.logger.warning(f"Error enviando email de asignación: {str(e)}")
            
            db.session.commit()
            
            flash(f'Emprendedor {entrepreneur.user.full_name} asignado exitosamente.', 'success')
            return redirect(url_for('admin_allies.view_ally', ally_id=ally.id))
            
        except BusinessLogicError as e:
            flash(f'Error de lógica de negocio: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error asignando emprendedor: {str(e)}")
            flash('Error al asignar el emprendedor.', 'error')
    
    return render_template('admin/allies/assign_entrepreneur.html', 
                         form=form, ally=ally, available_entrepreneurs=available_entrepreneurs)

@admin_allies.route('/<int:ally_id>/mentorships')
@login_required
@admin_required
@handle_exceptions
def mentorships(ally_id):
    """
    Muestra todas las mentorías de un aliado con gestión avanzada.
    """
    try:
        ally = Ally.query.options(
            joinedload(Ally.user)
        ).get_or_404(ally_id)
        
        # Obtener mentorías con estadísticas
        mentorships = Mentorship.query.filter_by(
            mentor_id=ally.id
        ).options(
            joinedload(Mentorship.entrepreneur),
            joinedload(Mentorship.entrepreneur).joinedload(Entrepreneur.user),
            selectinload(Mentorship.sessions)
        ).order_by(desc(Mentorship.updated_at)).all()
        
        # Estadísticas de mentorías
        mentorship_stats = {
            'total': len(mentorships),
            'active': len([m for m in mentorships if m.status == 'active']),
            'completed': len([m for m in mentorships if m.status == 'completed']),
            'paused': len([m for m in mentorships if m.status == 'paused']),
            'total_hours': sum([m.total_hours for m in mentorships if m.total_hours]),
            'avg_rating': sum([m.mentor_rating for m in mentorships if m.mentor_rating]) / 
                         len([m for m in mentorships if m.mentor_rating]) 
                         if [m for m in mentorships if m.mentor_rating] else 0
        }
        
        return render_template(
            'admin/allies/mentorships.html',
            ally=ally,
            mentorships=mentorships,
            mentorship_stats=mentorship_stats,
            mentorship_status=MENTORSHIP_STATUS
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando mentorías: {str(e)}")
        flash('Error al cargar las mentorías.', 'error')
        return redirect(url_for('admin_allies.view_ally', ally_id=ally_id))

# ============================================================================
# EVALUACIÓN Y PERFORMANCE
# ============================================================================

@admin_allies.route('/<int:ally_id>/evaluate', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('evaluate_ally')
@handle_exceptions
def evaluate_ally(ally_id):
    """
    Evalúa el rendimiento de un aliado/mentor.
    Genera ratings y recomendaciones de mejora.
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get_or_404(ally_id)
    
    form = EvaluateAllyForm()
    
    if form.validate_on_submit():
        try:
            # Preparar datos de evaluación
            evaluation_data = {
                'mentoring_quality': form.mentoring_quality.data,
                'communication_skills': form.communication_skills.data,
                'expertise_level': form.expertise_level.data,
                'reliability': form.reliability.data,
                'empathy': form.empathy.data,
                'results_impact': form.results_impact.data,
                'professionalism': form.professionalism.data,
                'innovation': form.innovation.data,
                'notes': form.notes.data.strip() if form.notes.data else None,
                'recommendations': form.recommendations.data.strip() if form.recommendations.data else None,
                'evaluator_id': current_user.id,
                'evaluation_date': datetime.now(timezone.utc)
            }
            
            # Calcular rating promedio
            rating_fields = [
                'mentoring_quality', 'communication_skills', 'expertise_level',
                'reliability', 'empathy', 'results_impact', 'professionalism', 'innovation'
            ]
            total_rating = sum([evaluation_data[field] for field in rating_fields]) / len(rating_fields)
            
            # Actualizar aliado
            ally.evaluation_data = evaluation_data  # JSON field
            ally.last_evaluation_at = datetime.now(timezone.utc)
            ally.admin_rating = total_rating
            
            # Recalcular rating promedio general
            _recalculate_ally_average_rating(ally)
            
            # Determinar nivel de performance
            if total_rating >= 4.5:
                performance_level = 'excellent'
            elif total_rating >= 3.5:
                performance_level = 'good'
            elif total_rating >= 2.5:
                performance_level = 'fair'
            else:
                performance_level = 'needs_improvement'
            
            ally.performance_level = performance_level
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='evaluate_ally',
                resource_type='Ally',
                resource_id=ally.id,
                details=f'Evaluación completada. Rating: {total_rating:.1f}/5.0, Performance: {performance_level}'
            )
            db.session.add(activity)
            
            # Notificar al aliado
            notification_service = NotificationService()
            notification_service.send_notification(
                user_id=ally.user_id,
                type='performance_evaluation',
                title='Evaluación de Rendimiento',
                message=f'Tu evaluación de rendimiento ha sido actualizada. Rating: {total_rating:.1f}/5.0',
                priority='medium' if total_rating >= 3.5 else 'high'
            )
            
            # Acciones automáticas basadas en rating
            if total_rating < 2.0:
                # Rating muy bajo - marcar para revisión
                ally.needs_review = True
                flash('Rating bajo detectado. Aliado marcado para revisión.', 'warning')
            elif total_rating >= 4.5:
                # Excelente rating - considerar para reconocimiento
                ally.is_featured = True
                flash('Excelente rating! Aliado marcado como destacado.', 'success')
            
            db.session.commit()
            
            flash(f'Evaluación completada. Rating: {total_rating:.1f}/5.0 ({performance_level})', 'success')
            return redirect(url_for('admin_allies.view_ally', ally_id=ally.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error evaluando aliado: {str(e)}")
            flash('Error al guardar la evaluación.', 'error')
    
    return render_template('admin/allies/evaluate.html', 
                         form=form, ally=ally, evaluation_criteria=EVALUATION_CRITERIA)

# ============================================================================
# GESTIÓN DE TARIFAS Y PAGOS
# ============================================================================

@admin_allies.route('/<int:ally_id>/rates', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_ally_rates')
@handle_exceptions
def manage_rates(ally_id):
    """
    Gestiona tarifas y configuración de pagos del aliado.
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get_or_404(ally_id)
    
    form = SetAllyRatesForm(obj=ally)
    
    if form.validate_on_submit():
        try:
            # Validar nueva tarifa
            if form.hourly_rate.data:
                is_valid, message = validate_hourly_rate(form.hourly_rate.data)
                if not is_valid:
                    flash(f'Tarifa inválida: {message}', 'error')
                    return render_template('admin/allies/rates.html', form=form, ally=ally)
            
            old_rate = ally.hourly_rate
            
            # Actualizar tarifas
            ally.hourly_rate = form.hourly_rate.data
            ally.currency = form.currency.data or 'USD'
            ally.payment_terms = form.payment_terms.data or 'monthly'
            ally.minimum_session_hours = form.minimum_session_hours.data or 1.0
            ally.payment_methods = form.payment_methods.data or ['bank_transfer']
            ally.tax_id = form.tax_id.data.strip() if form.tax_id.data else None
            ally.invoice_email = form.invoice_email.data.strip() if form.invoice_email.data else ally.user.email
            
            db.session.commit()
            
            # Registrar cambio de tarifa
            if old_rate != ally.hourly_rate:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_ally_rate',
                    resource_type='Ally',
                    resource_id=ally.id,
                    details=f'Tarifa actualizada: ${old_rate} → ${ally.hourly_rate} {ally.currency}'
                )
                db.session.add(activity)
                
                # Notificar al aliado sobre cambio de tarifa
                notification_service = NotificationService()
                notification_service.send_notification(
                    user_id=ally.user_id,
                    type='rate_updated',
                    title='Tarifa Actualizada',
                    message=f'Tu tarifa por hora ha sido actualizada a ${ally.hourly_rate} {ally.currency}',
                    priority='medium'
                )
                
                db.session.commit()
            
            flash('Configuración de tarifas actualizada exitosamente.', 'success')
            return redirect(url_for('admin_allies.view_ally', ally_id=ally.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando tarifas: {str(e)}")
            flash('Error al actualizar las tarifas.', 'error')
    
    return render_template('admin/allies/rates.html', form=form, ally=ally, 
                         currency_types=CURRENCY_TYPES)

# ============================================================================
# DISPONIBILIDAD Y HORARIOS
# ============================================================================

@admin_allies.route('/<int:ally_id>/availability', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_ally_availability')
@handle_exceptions
def manage_availability(ally_id):
    """
    Gestiona la disponibilidad y horarios del aliado.
    """
    ally = Ally.query.options(
        joinedload(Ally.user)
    ).get_or_404(ally_id)
    
    form = AllyAvailabilityForm(obj=ally)
    
    if form.validate_on_submit():
        try:
            # Validar disponibilidad
            is_valid, message = validate_availability(form.availability_hours.data, form.max_entrepreneurs.data)
            if not is_valid:
                flash(f'Configuración inválida: {message}', 'error')
                return render_template('admin/allies/availability.html', form=form, ally=ally)
            
            # Actualizar disponibilidad
            ally.is_available = form.is_available.data
            ally.max_entrepreneurs = form.max_entrepreneurs.data or 5
            ally.availability_hours = form.availability_hours.data or 20
            ally.time_zone = form.time_zone.data or 'UTC'
            ally.preferred_meeting_duration = form.preferred_meeting_duration.data or 60
            ally.availability_note = form.availability_note.data.strip() if form.availability_note.data else None
            
            # Actualizar horarios de disponibilidad (JSON field)
            ally.weekly_schedule = {
                'monday': form.monday_hours.data or [],
                'tuesday': form.tuesday_hours.data or [],
                'wednesday': form.wednesday_hours.data or [],
                'thursday': form.thursday_hours.data or [],
                'friday': form.friday_hours.data or [],
                'saturday': form.saturday_hours.data or [],
                'sunday': form.sunday_hours.data or []
            }
            
            # Verificar si debe desactivarse por capacidad
            if ally.is_available and ally.current_entrepreneurs >= ally.max_entrepreneurs:
                ally.is_available = False
                flash('Disponibilidad desactivada automáticamente: capacidad máxima alcanzada.', 'warning')
            
            ally.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='update_ally_availability',
                resource_type='Ally',
                resource_id=ally.id,
                details=f'Disponibilidad actualizada: {"Disponible" if ally.is_available else "No disponible"}, Max: {ally.max_entrepreneurs}'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash('Configuración de disponibilidad actualizada exitosamente.', 'success')
            return redirect(url_for('admin_allies.view_ally', ally_id=ally.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando disponibilidad: {str(e)}")
            flash('Error al actualizar la disponibilidad.', 'error')
    
    return render_template('admin/allies/availability.html', form=form, ally=ally)

# ============================================================================
# ANALYTICS Y ESTADÍSTICAS
# ============================================================================

@admin_allies.route('/analytics')
@login_required
@admin_required
@cache_result(timeout=300)
def analytics():
    """
    Dashboard de analytics para aliados/mentores.
    Métricas avanzadas, rendimiento y comparativas.
    """
    try:
        analytics_service = AnalyticsService()
        
        # Métricas generales
        general_metrics = _get_comprehensive_ally_metrics()
        
        # Datos para gráficos
        charts_data = {
            'allies_by_expertise': analytics_service.get_allies_by_expertise(),
            'performance_distribution': analytics_service.get_ally_performance_distribution(),
            'mentorship_effectiveness': analytics_service.get_mentorship_effectiveness_by_ally(),
            'hourly_rates_distribution': analytics_service.get_hourly_rates_distribution(),
            'availability_trends': analytics_service.get_ally_availability_trends(days=90),
            'geographic_distribution': analytics_service.get_allies_geographic_data(),
            'experience_vs_rating': analytics_service.get_experience_vs_rating_correlation()
        }
        
        # Top performers
        top_performers = _get_top_performing_allies(limit=10)
        
        # Aliados que necesitan atención
        needs_attention = _get_allies_needing_attention(limit=10)
        
        # Tendencias de crecimiento
        growth_trends = analytics_service.get_ally_growth_trends(days=365)
        
        # Métricas de revenue (si aplica)
        revenue_metrics = _get_ally_revenue_metrics()
        
        return render_template(
            'admin/allies/analytics.html',
            general_metrics=general_metrics,
            charts_data=charts_data,
            top_performers=top_performers,
            needs_attention=needs_attention,
            growth_trends=growth_trends,
            revenue_metrics=revenue_metrics
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando analytics: {str(e)}")
        flash('Error al cargar los analytics.', 'error')
        return redirect(url_for('admin_allies.list_allies'))

# ============================================================================
# ACCIONES EN LOTE
# ============================================================================

@admin_allies.route('/bulk-actions', methods=['POST'])
@login_required
@admin_required
@permission_required('bulk_ally_actions')
@handle_exceptions
def bulk_actions():
    """
    Ejecuta acciones en lote sobre múltiples aliados.
    """
    form = BulkAllyActionForm()
    
    if form.validate_on_submit():
        try:
            ally_ids = [int(id) for id in form.ally_ids.data.split(',') if id.strip()]
            action = form.action.data
            
            if not ally_ids:
                flash('No se seleccionaron aliados.', 'warning')
                return redirect(url_for('admin_allies.list_allies'))
            
            allies = Ally.query.filter(
                Ally.id.in_(ally_ids)
            ).options(joinedload(Ally.user)).all()
            
            success_count = 0
            
            for ally in allies:
                try:
                    if action == 'activate':
                        ally.is_available = True
                        success_count += 1
                        
                    elif action == 'deactivate':
                        ally.is_available = False
                        success_count += 1
                        
                    elif action == 'update_rates':
                        if form.new_hourly_rate.data:
                            ally.hourly_rate = form.new_hourly_rate.data
                            success_count += 1
                            
                    elif action == 'set_capacity':
                        if form.new_max_entrepreneurs.data:
                            ally.max_entrepreneurs = form.new_max_entrepreneurs.data
                            success_count += 1
                            
                    elif action == 'mark_featured':
                        ally.is_featured = True
                        success_count += 1
                        
                    elif action == 'unmark_featured':
                        ally.is_featured = False
                        success_count += 1
                        
                    elif action == 'send_notification':
                        notification_service = NotificationService()
                        notification_service.send_notification(
                            user_id=ally.user_id,
                            type='admin_message',
                            title=form.notification_title.data,
                            message=form.notification_message.data,
                            priority='medium'
                        )
                        success_count += 1
                        
                except Exception as e:
                    current_app.logger.warning(f"Error procesando aliado {ally.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='bulk_ally_action',
                resource_type='Ally',
                details=f'Acción en lote: {action} aplicada a {success_count} aliados'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Acción aplicada exitosamente a {success_count} aliado(s).', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error en acción en lote: {str(e)}")
            flash('Error al ejecutar la acción en lote.', 'error')
    else:
        flash('Datos de formulario inválidos.', 'error')
    
    return redirect(url_for('admin_allies.list_allies'))

# ============================================================================
# EXPORTACIÓN
# ============================================================================

@admin_allies.route('/export')
@login_required
@admin_required
@permission_required('export_allies')
@handle_exceptions
def export_allies():
    """
    Exporta datos de aliados en diferentes formatos.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_mentorships = request.args.get('include_mentorships', 'false') == 'true'
        include_earnings = request.args.get('include_earnings', 'false') == 'true'
        availability_filter = request.args.get('availability', 'all')
        
        # Construir query
        query = Ally.query.options(
            joinedload(Ally.user),
            selectinload(Ally.mentorships),
            selectinload(Ally.assigned_entrepreneurs)
        ).join(User).filter(User.is_active == True)
        
        if availability_filter == 'available':
            query = query.filter(Ally.is_available == True)
        elif availability_filter == 'unavailable':
            query = query.filter(Ally.is_available == False)
        
        allies = query.order_by(Ally.created_at.desc()).all()
        
        # Preparar datos de exportación
        export_data = []
        for ally in allies:
            row = {
                'ID': ally.id,
                'Nombre': ally.user.full_name,
                'Email': ally.user.email,
                'Título': ally.title or 'N/A',
                'Empresa': ally.company or 'N/A',
                'Años de Experiencia': ally.years_experience or 'N/A',
                'Tarifa por Hora': f"${ally.hourly_rate} {ally.currency}" if ally.hourly_rate else 'N/A',
                'Áreas de Expertise': ', '.join(ally.expertise_areas) if ally.expertise_areas else 'N/A',
                'Industrias': ', '.join(ally.industries) if ally.industries else 'N/A',
                'Idiomas': ', '.join(ally.languages) if ally.languages else 'N/A',
                'Disponible': 'Sí' if ally.is_available else 'No',
                'Max Emprendedores': ally.max_entrepreneurs or 'N/A',
                'Emprendedores Actuales': ally.current_entrepreneurs or 0,
                'Horas Disponibles': ally.availability_hours or 'N/A',
                'Rating Promedio': f"{ally.average_rating:.1f}" if ally.average_rating else 'N/A',
                'Rating Admin': f"{ally.admin_rating:.1f}" if ally.admin_rating else 'N/A',
                'Nivel de Performance': ally.performance_level or 'N/A',
                'País': ally.user.country or 'N/A',
                'Zona Horaria': ally.time_zone or 'N/A',
                'LinkedIn': ally.linkedin_profile or 'N/A',
                'Website': ally.website or 'N/A',
                'Fecha de Registro': ally.user.created_at.strftime('%Y-%m-%d'),
                'Última Actividad': ally.last_activity_at.strftime('%Y-%m-%d %H:%M') if ally.last_activity_at else 'N/A'
            }
            
            # Incluir datos de mentorías si se solicita
            if include_mentorships:
                active_mentorships = [m for m in ally.mentorships if m.status == 'active']
                completed_mentorships = [m for m in ally.mentorships if m.status == 'completed']
                row['Mentorías Activas'] = len(active_mentorships)
                row['Mentorías Completadas'] = len(completed_mentorships)
                row['Total Horas de Mentoría'] = sum([m.total_hours for m in ally.mentorships if m.total_hours])
                
            # Incluir datos de earnings si se solicita
            if include_earnings:
                total_earnings = sum([m.total_cost for m in ally.mentorships if m.total_cost])
                row['Ingresos Totales'] = f"${total_earnings:.2f}"
                monthly_earnings = _calculate_monthly_earnings(ally)
                row['Ingresos Este Mes'] = f"${monthly_earnings:.2f}"
            
            export_data.append(row)
        
        # Generar archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            filename = f'aliados_{timestamp}.xlsx'
            return export_to_excel(export_data, filename, 'Aliados')
        elif export_format == 'csv':
            filename = f'aliados_{timestamp}.csv'
            return export_to_csv(export_data, filename)
        elif export_format == 'pdf':
            filename = f'aliados_{timestamp}.pdf'
            return export_to_pdf(export_data, filename, 'Reporte de Aliados')
        
    except Exception as e:
        current_app.logger.error(f"Error exportando aliados: {str(e)}")
        flash('Error al exportar los datos.', 'error')
        return redirect(url_for('admin_allies.list_allies'))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_allies.route('/api/search')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_search_allies():
    """API para búsqueda de aliados en tiempo real."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        expertise = request.args.get('expertise', '')
        
        if len(query) < 2:
            return jsonify({'allies': []})
        
        search_query = Ally.query.join(User).filter(
            and_(
                User.is_active == True,
                or_(
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%'),
                    Ally.company.ilike(f'%{query}%'),
                    Ally.title.ilike(f'%{query}%')
                )
            )
        ).options(joinedload(Ally.user))
        
        # Filtrar por expertise si se proporciona
        if expertise:
            search_query = search_query.filter(
                Ally.expertise_areas.any(expertise)
            )
        
        allies = search_query.limit(limit).all()
        
        return jsonify({
            'allies': [
                {
                    'id': ally.id,
                    'name': ally.user.full_name,
                    'title': ally.title,
                    'company': ally.company,
                    'email': ally.user.email,
                    'expertise_areas': ally.expertise_areas,
                    'hourly_rate': ally.hourly_rate,
                    'currency': ally.currency,
                    'is_available': ally.is_available,
                    'current_entrepreneurs': ally.current_entrepreneurs,
                    'max_entrepreneurs': ally.max_entrepreneurs,
                    'average_rating': ally.average_rating
                }
                for ally in allies
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_allies.route('/api/<int:ally_id>/toggle-availability', methods=['POST'])
@login_required
@admin_required
@permission_required('toggle_ally_availability')
def api_toggle_availability(ally_id):
    """API para cambiar disponibilidad de un aliado."""
    try:
        ally = Ally.query.get_or_404(ally_id)
        
        # Verificar si puede activarse
        if not ally.is_available and ally.current_entrepreneurs >= ally.max_entrepreneurs:
            return jsonify({
                'error': 'No se puede activar: capacidad máxima alcanzada'
            }), 400
        
        ally.is_available = not ally.is_available
        db.session.commit()
        
        # Registrar actividad
        activity = ActivityLog(
            user_id=current_user.id,
            action='toggle_ally_availability',
            resource_type='Ally',
            resource_id=ally.id,
            details=f'Disponibilidad {"activada" if ally.is_available else "desactivada"}'
        )
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_available': ally.is_available,
            'message': f'Disponibilidad {"activada" if ally.is_available else "desactivada"} exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_ally_statistics():
    """Obtiene estadísticas básicas de aliados."""
    total_allies = Ally.query.join(User).filter(User.is_active == True).count()
    
    return {
        'total': total_allies,
        'available': Ally.query.join(User).filter(
            and_(User.is_active == True, Ally.is_available == True)
        ).count(),
        'with_capacity': Ally.query.join(User).filter(
            and_(
                User.is_active == True,
                Ally.is_available == True,
                Ally.current_entrepreneurs < Ally.max_entrepreneurs
            )
        ).count(),
        'at_capacity': Ally.query.join(User).filter(
            and_(
                User.is_active == True,
                Ally.current_entrepreneurs >= Ally.max_entrepreneurs
            )
        ).count(),
        'high_rated': Ally.query.join(User).filter(
            and_(User.is_active == True, Ally.average_rating >= 4.0)
        ).count(),
        'needs_review': Ally.query.join(User).filter(
            and_(User.is_active == True, Ally.average_rating < 3.0)
        ).count(),
        'this_month': Ally.query.join(User).filter(
            and_(
                User.is_active == True,
                User.created_at >= datetime.now(timezone.utc).replace(day=1)
            )
        ).count(),
        'avg_hourly_rate': db.session.query(func.avg(Ally.hourly_rate)).filter(
            Ally.hourly_rate.isnot(None)
        ).scalar() or 0
    }

def _get_ally_detailed_metrics(ally):
    """Obtiene métricas detalladas de un aliado específico."""
    metrics = {
        'account_age_days': (datetime.now(timezone.utc) - ally.user.created_at).days,
        'last_login_days_ago': (datetime.now(timezone.utc) - ally.user.last_login).days if ally.user.last_login else None,
        'total_mentorships': len(ally.mentorships),
        'active_mentorships': len([m for m in ally.mentorships if m.status == 'active']),
        'completed_mentorships': len([m for m in ally.mentorships if m.status == 'completed']),
        'success_rate': _calculate_ally_success_rate(ally),
        'total_hours': sum([m.total_hours for m in ally.mentorships if m.total_hours]),
        'avg_session_rating': _calculate_avg_session_rating(ally),
        'total_earnings': sum([m.total_cost for m in ally.mentorships if m.total_cost]),
        'current_capacity_percentage': (ally.current_entrepreneurs / ally.max_entrepreneurs * 100) if ally.max_entrepreneurs else 0,
        'response_rate': getattr(ally, 'response_rate', 0),
        'punctuality_score': getattr(ally, 'punctuality_score', 0)
    }
    
    # Calcular tendencia de actividad
    recent_activity = [m for m in ally.mentorships if m.updated_at >= datetime.now(timezone.utc) - timedelta(days=30)]
    metrics['recent_activity_score'] = len(recent_activity) / len(ally.mentorships) if ally.mentorships else 0
    
    return metrics

def _get_ally_entrepreneurs_data(ally):
    """Obtiene datos de emprendedores asignados al aliado."""
    entrepreneurs = ally.assigned_entrepreneurs
    
    return {
        'total': len(entrepreneurs),
        'by_stage': {
            'idea': len([e for e in entrepreneurs if e.business_stage == 'idea']),
            'mvp': len([e for e in entrepreneurs if e.business_stage == 'mvp']),
            'growth': len([e for e in entrepreneurs if e.business_stage == 'growth']),
            'scale': len([e for e in entrepreneurs if e.business_stage == 'scale'])
        },
        'high_performers': len([e for e in entrepreneurs if e.evaluation_score and e.evaluation_score >= 80]),
        'needs_attention': len([e for e in entrepreneurs if e.evaluation_score and e.evaluation_score < 50])
    }

def _get_ally_mentorship_history(ally):
    """Obtiene historial de mentorías del aliado."""
    return Mentorship.query.filter_by(
        mentor_id=ally.id
    ).options(
        joinedload(Mentorship.entrepreneur),
        joinedload(Mentorship.entrepreneur).joinedload(Entrepreneur.user)
    ).order_by(desc(Mentorship.created_at)).all()

def _get_ally_meetings_data(ally):
    """Obtiene datos de reuniones del aliado."""
    meetings = Meeting.query.filter(
        or_(
            Meeting.organizer_id == ally.user_id,
            Meeting.participants.any(User.id == ally.user_id)
        )
    ).order_by(desc(Meeting.scheduled_for)).limit(20).all()
    
    upcoming = [m for m in meetings if m.scheduled_for >= datetime.now(timezone.utc)]
    past = [m for m in meetings if m.scheduled_for < datetime.now(timezone.utc)]
    
    return {
        'upcoming': upcoming[:5],
        'past': past[:10],
        'total_this_month': len([m for m in meetings if m.scheduled_for >= datetime.now(timezone.utc).replace(day=1)]),
        'avg_duration': sum([m.duration for m in past if m.duration]) / len([m for m in past if m.duration]) if past else 0
    }

def _get_ally_evaluations(ally):
    """Obtiene evaluaciones del aliado."""
    evaluations = []
    
    # Evaluación administrativa
    if ally.evaluation_data and ally.last_evaluation_at:
        evaluations.append({
            'type': 'administrative',
            'date': ally.last_evaluation_at,
            'rating': ally.admin_rating,
            'evaluator': 'Administración',
            'notes': ally.evaluation_data.get('notes', '') if isinstance(ally.evaluation_data, dict) else ''
        })
    
    # Evaluaciones de emprendedores (promedio)
    entrepreneur_ratings = [m.mentor_rating for m in ally.mentorships if m.mentor_rating]
    if entrepreneur_ratings:
        evaluations.append({
            'type': 'entrepreneur_average',
            'rating': sum(entrepreneur_ratings) / len(entrepreneur_ratings),
            'count': len(entrepreneur_ratings),
            'source': 'Emprendedores'
        })
    
    return evaluations

def _get_ally_availability_data(ally):
    """Obtiene datos de disponibilidad del aliado."""
    return {
        'is_available': ally.is_available,
        'max_entrepreneurs': ally.max_entrepreneurs,
        'current_entrepreneurs': ally.current_entrepreneurs,
        'availability_percentage': (ally.current_entrepreneurs / ally.max_entrepreneurs * 100) if ally.max_entrepreneurs else 0,
        'weekly_hours': ally.availability_hours,
        'time_zone': ally.time_zone,
        'preferred_duration': ally.preferred_meeting_duration,
        'schedule': ally.weekly_schedule if hasattr(ally, 'weekly_schedule') else {}
    }

def _get_ally_earnings_data(ally):
    """Obtiene datos de earnings del aliado."""
    current_month = datetime.now(timezone.utc).replace(day=1)
    last_month = (current_month - timedelta(days=1)).replace(day=1)
    
    mentorships = ally.mentorships
    
    current_month_earnings = sum([
        m.total_cost for m in mentorships 
        if m.total_cost and m.updated_at >= current_month
    ])
    
    last_month_earnings = sum([
        m.total_cost for m in mentorships 
        if m.total_cost and m.updated_at >= last_month and m.updated_at < current_month
    ])
    
    total_earnings = sum([m.total_cost for m in mentorships if m.total_cost])
    
    return {
        'total_earnings': total_earnings,
        'current_month': current_month_earnings,
        'last_month': last_month_earnings,
        'growth_percentage': ((current_month_earnings - last_month_earnings) / last_month_earnings * 100) if last_month_earnings else 0,
        'hourly_rate': ally.hourly_rate,
        'currency': ally.currency,
        'avg_monthly': total_earnings / max(1, (datetime.now(timezone.utc) - ally.user.created_at).days / 30.0)
    }

def _get_ally_performance_trends(ally):
    """Obtiene tendencias de rendimiento del aliado."""
    # Esto debería calcularse basado en ratings históricos y métricas de tiempo
    return {
        'rating_trend': 'stable',  # 'improving', 'declining', 'stable'
        'activity_trend': 'increasing',
        'engagement_trend': 'stable'
    }

def _generate_ally_recommendations(ally):
    """Genera recomendaciones automáticas para el aliado."""
    recommendations = []
    
    # Recomendaciones basadas en rating
    if ally.average_rating and ally.average_rating < 3.5:
        recommendations.append({
            'type': 'improvement',
            'priority': 'high',
            'title': 'Mejorar Rating',
            'description': 'El rating promedio es bajo. Considera capacitación adicional.',
            'action': 'Programar sesión de feedback'
        })
    
    # Recomendaciones basadas en capacidad
    if ally.is_available and ally.current_entrepreneurs < ally.max_entrepreneurs:
        recommendations.append({
            'type': 'opportunity',
            'priority': 'medium',
            'title': 'Capacidad Disponible',
            'description': 'Puede tomar más emprendedores.',
            'action': 'Asignar nuevos emprendedores'
        })
    
    # Recomendaciones basadas en actividad
    if ally.last_activity_at and ally.last_activity_at < datetime.now(timezone.utc) - timedelta(days=15):
        recommendations.append({
            'type': 'engagement',
            'priority': 'medium',
            'title': 'Baja Actividad',
            'description': 'No ha habido actividad reciente.',
            'action': 'Contactar al aliado'
        })
    
    return recommendations

def _get_available_entrepreneurs_for_ally(ally):
    """Obtiene emprendedores disponibles para asignar al aliado."""
    # Emprendedores sin mentor asignado
    entrepreneurs = Entrepreneur.query.join(User).filter(
        and_(
            User.is_active == True,
            Entrepreneur.assigned_mentor_id.is_(None)
        )
    ).options(
        joinedload(Entrepreneur.user)
    ).all()
    
    # Filtrar por compatibilidad si hay expertise e industria
    if ally.expertise_areas:
        compatible_entrepreneurs = []
        for entrepreneur in entrepreneurs:
            if (entrepreneur.industry and 
                any(area.lower() in entrepreneur.industry.lower() for area in ally.expertise_areas)):
                compatible_entrepreneurs.append(entrepreneur)
        
        # Si hay emprendedores compatibles, priorizarlos
        if compatible_entrepreneurs:
            # Retornar compatibles primero, luego otros
            other_entrepreneurs = [e for e in entrepreneurs if e not in compatible_entrepreneurs]
            return compatible_entrepreneurs + other_entrepreneurs[:5]  # Limitar otros
    
    return entrepreneurs

def _recalculate_ally_average_rating(ally):
    """Recalcula el rating promedio del aliado."""
    ratings = []
    
    # Rating administrativo
    if ally.admin_rating:
        ratings.append(ally.admin_rating)
    
    # Ratings de emprendedores
    entrepreneur_ratings = [m.mentor_rating for m in ally.mentorships if m.mentor_rating]
    ratings.extend(entrepreneur_ratings)
    
    # Calcular promedio ponderado (admin rating peso 2x)
    if ratings:
        if ally.admin_rating and entrepreneur_ratings:
            # Promedio ponderado: admin 2x peso
            total_weight = 2 + len(entrepreneur_ratings)
            weighted_sum = (ally.admin_rating * 2) + sum(entrepreneur_ratings)
            ally.average_rating = weighted_sum / total_weight
        else:
            # Solo uno de los tipos disponible
            ally.average_rating = sum(ratings) / len(ratings)
    else:
        ally.average_rating = None

def _calculate_ally_success_rate(ally):
    """Calcula tasa de éxito del aliado basada en emprendedores exitosos."""
    if not ally.mentorships:
        return 0
    
    # Considerar exitosos a emprendedores con proyectos completados o scores altos
    successful = 0
    for mentorship in ally.mentorships:
        entrepreneur = mentorship.entrepreneur
        if (entrepreneur.evaluation_score and entrepreneur.evaluation_score >= 75) or \
           any(p.status == 'completed' for p in entrepreneur.projects):
            successful += 1
    
    return (successful / len(ally.mentorships)) * 100

def _calculate_avg_session_rating(ally):
    """Calcula rating promedio de sesiones."""
    ratings = [m.mentor_rating for m in ally.mentorships if m.mentor_rating]
    return sum(ratings) / len(ratings) if ratings else 0

def _get_comprehensive_ally_metrics():
    """Obtiene métricas comprehensivas para analytics."""
    total = Ally.query.join(User).filter(User.is_active == True).count()
    
    return {
        'total_allies': total,
        'active_mentorships': Mentorship.query.filter_by(status='active').count(),
        'avg_rating': db.session.query(func.avg(Ally.average_rating)).filter(
            Ally.average_rating.isnot(None)
        ).scalar() or 0,
        'availability_rate': _calculate_availability_rate(),
        'capacity_utilization': _calculate_capacity_utilization(),
        'mentor_satisfaction': _calculate_mentor_satisfaction()
    }

def _calculate_availability_rate():
    """Calcula tasa de disponibilidad."""
    total = Ally.query.join(User).filter(User.is_active == True).count()
    if total == 0:
        return 0
    
    available = Ally.query.join(User).filter(
        and_(User.is_active == True, Ally.is_available == True)
    ).count()
    
    return (available / total) * 100

def _calculate_capacity_utilization():
    """Calcula utilización de capacidad promedio."""
    allies = Ally.query.join(User).filter(User.is_active == True).all()
    
    if not allies:
        return 0
    
    total_utilization = 0
    count = 0
    
    for ally in allies:
        if ally.max_entrepreneurs and ally.max_entrepreneurs > 0:
            utilization = (ally.current_entrepreneurs or 0) / ally.max_entrepreneurs
            total_utilization += utilization
            count += 1
    
    return (total_utilization / count * 100) if count > 0 else 0

def _calculate_mentor_satisfaction():
    """Calcula satisfacción promedio de mentores."""
    ratings = db.session.query(Ally.average_rating).filter(
        Ally.average_rating.isnot(None)
    ).all()
    
    if not ratings:
        return 0
    
    return sum([r[0] for r in ratings]) / len(ratings)

def _get_top_performing_allies(limit=10):
    """Obtiene aliados con mejor desempeño."""
    return Ally.query.join(User).filter(
        User.is_active == True
    ).options(
        joinedload(Ally.user)
    ).order_by(
        desc(Ally.average_rating),
        desc(Ally.years_experience)
    ).limit(limit).all()

def _get_allies_needing_attention(limit=10):
    """Obtiene aliados que necesitan atención."""
    return Ally.query.join(User).filter(
        and_(
            User.is_active == True,
            or_(
                Ally.average_rating < 3.0,
                Ally.last_activity_at < datetime.now(timezone.utc) - timedelta(days=30),
                and_(Ally.is_available == True, Ally.current_entrepreneurs == 0)
            )
        )
    ).options(
        joinedload(Ally.user)
    ).order_by(
        Ally.average_rating.asc(),
        Ally.last_activity_at.asc()
    ).limit(limit).all()

def _get_ally_revenue_metrics():
    """Obtiene métricas de ingresos de aliados."""
    current_month = datetime.now(timezone.utc).replace(day=1)
    
    total_revenue = db.session.query(
        func.sum(Mentorship.total_cost)
    ).filter(Mentorship.total_cost.isnot(None)).scalar() or 0
    
    monthly_revenue = db.session.query(
        func.sum(Mentorship.total_cost)
    ).filter(
        and_(
            Mentorship.total_cost.isnot(None),
            Mentorship.updated_at >= current_month
        )
    ).scalar() or 0
    
    return {
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'avg_hourly_rate': db.session.query(func.avg(Ally.hourly_rate)).filter(
            Ally.hourly_rate.isnot(None)
        ).scalar() or 0,
        'revenue_per_ally': total_revenue / max(1, Ally.query.count())
    }

def _calculate_monthly_earnings(ally):
    """Calcula ingresos del mes actual para un aliado."""
    current_month = datetime.now(timezone.utc).replace(day=1)
    
    monthly_earnings = sum([
        m.total_cost for m in ally.mentorships 
        if m.total_cost and m.updated_at >= current_month
    ])
    
    return monthly_earnings