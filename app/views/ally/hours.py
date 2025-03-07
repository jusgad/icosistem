from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

from app.extensions import db
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship, MeetingNote, HoursLog
from app.forms.ally import HoursLogForm, HoursReportForm
from app.utils.decorators import ally_required
from app.utils.formatters import format_date, format_hours
from app.utils.excel import generate_hours_excel

# Crear el Blueprint para las vistas de registro de horas
bp = Blueprint('ally_hours', __name__, url_prefix='/ally/hours')

@bp.route('/', methods=['GET'])
@login_required
@ally_required
def hours_dashboard():
    """Vista principal del dashboard de horas"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener fecha actual y primer día del mes actual
    today = datetime.now().date()
    first_day_of_month = datetime(today.year, today.month, 1).date()
    last_day_of_month = datetime(today.year, today.month, 
                                calendar.monthrange(today.year, today.month)[1]).date()
    
    # Obtener registros de horas del mes actual
    hours_logs = HoursLog.query.filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= first_day_of_month,
        HoursLog.date <= last_day_of_month
    ).order_by(HoursLog.date.desc()).all()
    
    # Calcular horas por emprendedor
    hours_by_entrepreneur = defaultdict(float)
    for log in hours_logs:
        if log.entrepreneur_id:
            entrepreneur = Entrepreneur.query.get(log.entrepreneur_id)
            if entrepreneur:
                hours_by_entrepreneur[entrepreneur.business_name] += log.hours
    
    # Calcular horas totales registradas este mes
    total_hours_this_month = sum(log.hours for log in hours_logs)
    
    # Calcular horas por categoría
    hours_by_category = defaultdict(float)
    for log in hours_logs:
        hours_by_category[log.category] += log.hours
    
    # Obtener objetivos de horas (podrían venir de la configuración)
    hours_goal = ally.monthly_hours_goal or 40  # Valor por defecto de 40 horas al mes
    hours_progress = (total_hours_this_month / hours_goal) * 100 if hours_goal > 0 else 0
    
    # Últimos 5 registros de horas para mostrar en el dashboard
    recent_logs = HoursLog.query.filter(
        HoursLog.ally_id == ally.id
    ).order_by(HoursLog.date.desc()).limit(5).all()
    
    return render_template('ally/hours_dashboard.html',
                          ally=ally,
                          total_hours=total_hours_this_month,
                          hours_goal=hours_goal,
                          hours_progress=hours_progress,
                          hours_by_entrepreneur=dict(hours_by_entrepreneur),
                          hours_by_category=dict(hours_by_category),
                          recent_logs=recent_logs,
                          current_month=first_day_of_month.strftime("%B %Y"))

@bp.route('/log', methods=['GET', 'POST'])
@login_required
@ally_required
def log_hours():
    """Vista para registrar nuevas horas"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener todos los emprendedores asignados al aliado para el formulario
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    entrepreneurs = [Entrepreneur.query.get(rel.entrepreneur_id) for rel in relationships]
    
    # Crear formulario para el registro de horas
    form = HoursLogForm()
    
    # Añadir opciones dinámicas al formulario
    form.entrepreneur_id.choices = [(0, 'No específico')] + [
        (e.id, e.business_name) for e in entrepreneurs if e is not None
    ]
    
    if form.validate_on_submit():
        # Crear nuevo registro de horas
        hours_log = HoursLog(
            ally_id=ally.id,
            date=form.date.data,
            hours=form.hours.data,
            category=form.category.data,
            description=form.description.data,
            location=form.location.data,
            billable=form.billable.data
        )
        
        # Asignar emprendedor si se seleccionó uno específico
        if form.entrepreneur_id.data > 0:
            hours_log.entrepreneur_id = form.entrepreneur_id.data
            # Actualizar las horas totales de la relación
            relationship = Relationship.query.filter_by(
                ally_id=ally.id,
                entrepreneur_id=form.entrepreneur_id.data
            ).first()
            if relationship:
                relationship.hours += form.hours.data
        
        # Guardar en la base de datos
        db.session.add(hours_log)
        db.session.commit()
        
        flash('Horas registradas correctamente', 'success')
        return redirect(url_for('ally_hours.hours_dashboard'))
    
    return render_template('ally/hours_log_form.html', 
                          form=form, 
                          ally=ally)

@bp.route('/log/<int:log_id>/edit', methods=['GET', 'POST'])
@login_required
@ally_required
def edit_hours_log(log_id):
    """Vista para editar un registro de horas existente"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener el registro de horas y verificar que pertenezca al aliado
    hours_log = HoursLog.query.filter_by(id=log_id, ally_id=ally.id).first_or_404()
    
    # Obtener todos los emprendedores asignados al aliado para el formulario
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    entrepreneurs = [Entrepreneur.query.get(rel.entrepreneur_id) for rel in relationships]
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = HoursLogForm(obj=hours_log)
    
    # Añadir opciones dinámicas al formulario
    form.entrepreneur_id.choices = [(0, 'No específico')] + [
        (e.id, e.business_name) for e in entrepreneurs if e is not None
    ]
    
    # Guardar las horas anteriores para ajustar la relación
    previous_hours = hours_log.hours
    previous_entrepreneur_id = hours_log.entrepreneur_id
    
    if form.validate_on_submit():
        # Actualizar datos del registro
        form.populate_obj(hours_log)
        
        # Ajustar las horas de la relación anterior si existía
        if previous_entrepreneur_id:
            previous_relationship = Relationship.query.filter_by(
                ally_id=ally.id,
                entrepreneur_id=previous_entrepreneur_id
            ).first()
            if previous_relationship:
                previous_relationship.hours -= previous_hours
        
        # Asignar emprendedor si se seleccionó uno específico
        if form.entrepreneur_id.data > 0:
            hours_log.entrepreneur_id = form.entrepreneur_id.data
            # Actualizar las horas totales de la nueva relación
            relationship = Relationship.query.filter_by(
                ally_id=ally.id,
                entrepreneur_id=form.entrepreneur_id.data
            ).first()
            if relationship:
                relationship.hours += form.hours.data
        else:
            hours_log.entrepreneur_id = None
        
        # Guardar cambios en la base de datos
        db.session.commit()
        
        flash('Registro de horas actualizado correctamente', 'success')
        return redirect(url_for('ally_hours.hours_dashboard'))
    
    return render_template('ally/hours_log_form.html', 
                          form=form, 
                          ally=ally,
                          hours_log=hours_log)

@bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
@ally_required
def delete_hours_log(log_id):
    """Vista para eliminar un registro de horas"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener el registro de horas y verificar que pertenezca al aliado
    hours_log = HoursLog.query.filter_by(id=log_id, ally_id=ally.id).first_or_404()
    
    # Ajustar las horas de la relación si existía
    if hours_log.entrepreneur_id:
        relationship = Relationship.query.filter_by(
            ally_id=ally.id,
            entrepreneur_id=hours_log.entrepreneur_id
        ).first()
        if relationship:
            relationship.hours -= hours_log.hours
    
    # Eliminar de la base de datos
    db.session.delete(hours_log)
    db.session.commit()
    
    flash('Registro de horas eliminado correctamente', 'success')
    return redirect(url_for('ally_hours.hours_dashboard'))

@bp.route('/report', methods=['GET', 'POST'])
@login_required
@ally_required
def generate_report():
    """Vista para generar reportes de horas"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Crear formulario para el reporte
    form = HoursReportForm()
    
    # Añadir opciones dinámicas al formulario
    relationships = Relationship.query.filter_by(ally_id=ally.id).all()
    entrepreneurs = [Entrepreneur.query.get(rel.entrepreneur_id) for rel in relationships if Entrepreneur.query.get(rel.entrepreneur_id)]
    
    form.entrepreneur_id.choices = [(0, 'Todos los emprendedores')] + [
        (e.id, e.business_name) for e in entrepreneurs
    ]
    
    if form.validate_on_submit():
        # Construir la consulta base
        query = HoursLog.query.filter(
            HoursLog.ally_id == ally.id,
            HoursLog.date >= form.start_date.data,
            HoursLog.date <= form.end_date.data
        )
        
        # Filtrar por emprendedor si se especificó
        if form.entrepreneur_id.data > 0:
            query = query.filter(HoursLog.entrepreneur_id == form.entrepreneur_id.data)
        
        # Filtrar por categoría si se especificó
        if form.category.data and form.category.data != 'all':
            query = query.filter(HoursLog.category == form.category.data)
        
        # Obtener los resultados
        hours_logs = query.order_by(HoursLog.date).all()
        
        # Calcular totales
        total_hours = sum(log.hours for log in hours_logs)
        hours_by_entrepreneur = defaultdict(float)
        hours_by_category = defaultdict(float)
        hours_by_date = defaultdict(float)
        
        for log in hours_logs:
            if log.entrepreneur_id:
                entrepreneur = Entrepreneur.query.get(log.entrepreneur_id)
                if entrepreneur:
                    hours_by_entrepreneur[entrepreneur.business_name] += log.hours
            else:
                hours_by_entrepreneur['No específico'] += log.hours
                
            hours_by_category[log.category] += log.hours
            hours_by_date[log.date.strftime('%Y-%m-%d')] += log.hours
        
        # Si se solicitó descargar como Excel
        if form.download_excel.data:
            return generate_hours_excel(
                hours_logs=hours_logs,
                ally=ally,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                total_hours=total_hours
            )
        
        return render_template('ally/hours_report.html',
                             ally=ally,
                             hours_logs=hours_logs,
                             total_hours=total_hours,
                             hours_by_entrepreneur=dict(hours_by_entrepreneur),
                             hours_by_category=dict(hours_by_category),
                             hours_by_date=dict(hours_by_date),
                             start_date=form.start_date.data,
                             end_date=form.end_date.data)
    
    return render_template('ally/hours_report_form.html', 
                          form=form, 
                          ally=ally)

@bp.route('/monthly', methods=['GET'])
@login_required
@ally_required
def monthly_view():
    """Vista para visualizar horas por mes"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener año y mes de los parámetros o usar el actual
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    # Crear fechas para el mes seleccionado
    first_day = datetime(year, month, 1).date()
    last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()
    
    # Obtener todos los registros del mes
    hours_logs = HoursLog.query.filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= first_day,
        HoursLog.date <= last_day
    ).order_by(HoursLog.date).all()
    
    # Preparar datos para el calendario
    calendar_data = {}
    for i in range(1, calendar.monthrange(year, month)[1] + 1):
        day_date = datetime(year, month, i).date()
        calendar_data[i] = {
            'date': day_date,
            'logs': [],
            'total_hours': 0
        }
    
    # Rellenar el calendario con los datos
    for log in hours_logs:
        day = log.date.day
        calendar_data[day]['logs'].append(log)
        calendar_data[day]['total_hours'] += log.hours
    
    # Calcular totales para el mes
    total_hours = sum(log.hours for log in hours_logs)
    
    # Calcular horas por categoría para el mes
    hours_by_category = defaultdict(float)
    for log in hours_logs:
        hours_by_category[log.category] += log.hours
    
    # Calcular días de la semana para la cabecera del calendario
    cal = calendar.monthcalendar(year, month)
    
    # Para navegación entre meses
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    return render_template('ally/hours_monthly.html',
                         ally=ally,
                         calendar_data=calendar_data,
                         cal=cal,
                         month_name=first_day.strftime("%B"),
                         year=year,
                         month=month,
                         total_hours=total_hours,
                         hours_by_category=dict(hours_by_category),
                         prev_month=prev_month,
                         prev_year=prev_year,
                         next_month=next_month,
                         next_year=next_year)

@bp.route('/statistics', methods=['GET'])
@login_required
@ally_required
def statistics():
    """Vista para estadísticas avanzadas de horas"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Establecer período de tiempo (último año por defecto)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    
    # Obtener período personalizado si se especifica
    period = request.args.get('period', 'year')
    if period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    elif period == 'custom':
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            # Usar valores por defecto si hay error
            pass
    
    # Obtener datos para el período
    hours_logs = HoursLog.query.filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= start_date,
        HoursLog.date <= end_date
    ).all()
    
    # Calcular estadísticas generales
    total_hours = sum(log.hours for log in hours_logs)
    billable_hours = sum(log.hours for log in hours_logs if log.billable)
    non_billable_hours = total_hours - billable_hours
    billable_percentage = (billable_hours / total_hours * 100) if total_hours > 0 else 0
    
    # Calcular horas por mes
    hours_by_month = db.session.query(
        func.strftime('%Y-%m', HoursLog.date).label('month'),
        func.sum(HoursLog.hours).label('total_hours')
    ).filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= start_date,
        HoursLog.date <= end_date
    ).group_by('month').order_by('month').all()
    
    # Calcular horas por categoría
    hours_by_category = db.session.query(
        HoursLog.category,
        func.sum(HoursLog.hours).label('total_hours')
    ).filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= start_date,
        HoursLog.date <= end_date
    ).group_by(HoursLog.category).all()
    
    # Calcular horas por emprendedor
    hours_by_entrepreneur = {}
    entrepreneurs_data = db.session.query(
        HoursLog.entrepreneur_id,
        func.sum(HoursLog.hours).label('total_hours')
    ).filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= start_date,
        HoursLog.date <= end_date,
        HoursLog.entrepreneur_id != None
    ).group_by(HoursLog.entrepreneur_id).all()
    
    for entrepreneur_id, total_hours in entrepreneurs_data:
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        if entrepreneur:
            hours_by_entrepreneur[entrepreneur.business_name] = total_hours
    
    # Añadir horas no específicas si existen
    non_specific_hours = db.session.query(
        func.sum(HoursLog.hours)
    ).filter(
        HoursLog.ally_id == ally.id,
        HoursLog.date >= start_date,
        HoursLog.date <= end_date,
        HoursLog.entrepreneur_id == None
    ).scalar() or 0
    
    if non_specific_hours > 0:
        hours_by_entrepreneur['No específico'] = non_specific_hours
    
    # Calcular horas promedio por día, semana y mes
    days_in_period = (end_date - start_date).days or 1
    avg_hours_per_day = total_hours / days_in_period
    avg_hours_per_week = total_hours / (days_in_period / 7)
    avg_hours_per_month = total_hours / (days_in_period / 30)
    
    return render_template('ally/hours_statistics.html',
                         ally=ally,
                         total_hours=total_hours,
                         billable_hours=billable_hours,
                         non_billable_hours=non_billable_hours,
                         billable_percentage=billable_percentage,
                         hours_by_month=hours_by_month,
                         hours_by_category=hours_by_category,
                         hours_by_entrepreneur=hours_by_entrepreneur,
                         avg_hours_per_day=avg_hours_per_day,
                         avg_hours_per_week=avg_hours_per_week,
                         avg_hours_per_month=avg_hours_per_month,
                         start_date=start_date,
                         end_date=end_date,
                         period=period)