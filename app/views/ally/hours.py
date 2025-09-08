"""
Vistas para el registro y gestión de horas de trabajo de aliados/mentores.

Este módulo maneja todas las operaciones CRUD relacionadas con el registro
de horas de trabajo de los aliados, incluyendo reportes y exportación.
"""

from datetime import datetime, timedelta, timezone
from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, abort, send_file
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, extract
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import NotFound

from app.extensions import db
from app.models.user import User
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.meeting import Meeting
from app.core.exceptions import ValidationError, PermissionError
from app.core.permissions import require_role, require_ally_access
from app.utils.decorators import handle_db_errors, log_activity
from app.utils.validators import validate_date_range, validate_hours_format
from app.utils.formatters import format_currency, format_hours
from app.utils.export_utils import generate_hours_report_pdf, generate_hours_report_excel
from app.utils.date_utils import get_week_range, get_month_range, parse_date
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService

# Blueprint para las vistas de horas de aliados
ally_hours_bp = Blueprint('ally_hours', __name__, url_prefix='/ally/hours')


class HourEntry:
    """Clase para manejar entradas de horas de trabajo."""
    
    def __init__(self, date, hours, project_id, entrepreneur_id, description, 
                 activity_type='mentoring', billable=True, rate=None):
        self.date = date
        self.hours = hours
        self.project_id = project_id
        self.entrepreneur_id = entrepreneur_id
        self.description = description
        self.activity_type = activity_type
        self.billable = billable
        self.rate = rate or current_user.ally.default_hourly_rate
        
    @property
    def total_amount(self):
        """Calcula el monto total de la entrada."""
        if self.billable and self.rate:
            return self.hours * self.rate
        return 0


@ally_hours_bp.route('/')
@login_required
@require_role('ally')
@log_activity('view_hours_dashboard')
def index():
    """
    Dashboard principal de registro de horas para aliados.
    
    Muestra resumen de horas del período actual, estadísticas
    y accesos rápidos a funcionalidades principales.
    """
    try:
        ally = current_user.ally
        
        # Obtener parámetros de filtrado
        period = request.args.get('period', 'current_month')
        start_date, end_date = _get_date_range_for_period(period)
        
        # Consulta base de horas del aliado
        hours_query = (
            db.session.query(Meeting)
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == True,
                Meeting.date >= start_date,
                Meeting.date <= end_date
            )
        )
        
        # Estadísticas del período
        total_hours = hours_query.with_entities(
            func.sum(Meeting.duration_hours)
        ).scalar() or 0
        
        total_meetings = hours_query.count()
        
        billable_hours = hours_query.filter(
            Meeting.billable == True
        ).with_entities(
            func.sum(Meeting.duration_hours)
        ).scalar() or 0
        
        total_earnings = hours_query.filter(
            Meeting.billable == True
        ).with_entities(
            func.sum(Meeting.duration_hours * Meeting.hourly_rate)
        ).scalar() or 0
        
        # Horas por emprendedor
        hours_by_entrepreneur = (
            db.session.query(
                Entrepreneur.name,
                func.sum(Meeting.duration_hours).label('total_hours')
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
            .limit(10)
            .all()
        )
        
        # Horas por tipo de actividad
        hours_by_activity = (
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
        
        # Tendencia semanal (últimas 12 semanas)
        twelve_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=12)
        weekly_trend = (
            db.session.query(
                extract('week', Meeting.date).label('week'),
                extract('year', Meeting.date).label('year'),
                func.sum(Meeting.duration_hours).label('total_hours')
            )
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == True,
                Meeting.date >= twelve_weeks_ago
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
        
        # Objetivos mensuales
        monthly_goal = ally.monthly_hours_goal or 40
        monthly_progress = (total_hours / monthly_goal * 100) if monthly_goal > 0 else 0
        
        # Próximas reuniones
        upcoming_meetings = (
            Meeting.query
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == False,
                Meeting.date >= datetime.now(timezone.utc)
            )
            .order_by(Meeting.date)
            .limit(5)
            .all()
        )
        
        return render_template(
            'ally/hours/dashboard.html',
            ally=ally,
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_hours=total_hours,
            total_meetings=total_meetings,
            billable_hours=billable_hours,
            total_earnings=total_earnings,
            hours_by_entrepreneur=hours_by_entrepreneur,
            hours_by_activity=hours_by_activity,
            weekly_trend=weekly_trend,
            monthly_goal=monthly_goal,
            monthly_progress=monthly_progress,
            upcoming_meetings=upcoming_meetings,
            format_currency=format_currency,
            format_hours=format_hours
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de horas: {str(e)}")
        flash('Error al cargar el dashboard de horas.', 'error')
        return redirect(url_for('ally.dashboard'))


@ally_hours_bp.route('/register')
@login_required
@require_role('ally')
@log_activity('access_hours_registration')
def register():
    """
    Formulario para registrar nuevas horas de trabajo.
    
    Permite al aliado registrar horas trabajadas con emprendedores,
    especificando proyecto, tipo de actividad y detalles.
    """
    try:
        ally = current_user.ally
        
        # Obtener emprendedores asignados al aliado
        entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(Project.ally_id == ally.id)
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        # Obtener proyectos activos del aliado
        projects = (
            Project.query
            .filter(
                Project.ally_id == ally.id,
                Project.status.in_(['active', 'in_progress'])
            )
            .order_by(Project.name)
            .all()
        )
        
        # Tipos de actividad disponibles
        activity_types = [
            ('mentoring', 'Mentoría'),
            ('consultation', 'Consultoría'),
            ('workshop', 'Taller'),
            ('review', 'Revisión'),
            ('planning', 'Planificación'),
            ('research', 'Investigación'),
            ('presentation', 'Presentación'),
            ('other', 'Otro')
        ]
        
        return render_template(
            'ally/hours/register.html',
            ally=ally,
            entrepreneurs=entrepreneurs,
            projects=projects,
            activity_types=activity_types,
            default_rate=ally.default_hourly_rate
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar formulario de registro: {str(e)}")
        flash('Error al cargar el formulario de registro.', 'error')
        return redirect(url_for('ally_hours.index'))


@ally_hours_bp.route('/register', methods=['POST'])
@login_required
@require_role('ally')
@handle_db_errors
@log_activity('register_hours')
def register_post():
    """
    Procesa el registro de nuevas horas de trabajo.
    
    Valida los datos del formulario y crea una nueva entrada
    de horas en la base de datos.
    """
    try:
        ally = current_user.ally
        
        # Obtener datos del formulario
        date_str = request.form.get('date')
        hours_str = request.form.get('hours')
        entrepreneur_id = request.form.get('entrepreneur_id')
        project_id = request.form.get('project_id')
        activity_type = request.form.get('activity_type')
        description = request.form.get('description', '').strip()
        billable = request.form.get('billable') == 'on'
        hourly_rate = request.form.get('hourly_rate')
        
        # Validaciones
        if not all([date_str, hours_str, entrepreneur_id, activity_type]):
            flash('Todos los campos obligatorios deben ser completados.', 'error')
            return redirect(url_for('ally_hours.register'))
        
        # Validar y parsear fecha
        try:
            work_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if work_date > datetime.now(timezone.utc).date():
                flash('No se pueden registrar horas para fechas futuras.', 'error')
                return redirect(url_for('ally_hours.register'))
        except ValueError:
            flash('Formato de fecha inválido.', 'error')
            return redirect(url_for('ally_hours.register'))
        
        # Validar horas
        try:
            hours = float(hours_str)
            if hours <= 0 or hours > 24:
                flash('Las horas deben estar entre 0.1 y 24.', 'error')
                return redirect(url_for('ally_hours.register'))
        except ValueError:
            flash('Formato de horas inválido.', 'error')
            return redirect(url_for('ally_hours.register'))
        
        # Validar emprendedor
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        if not entrepreneur:
            flash('Emprendedor seleccionado no existe.', 'error')
            return redirect(url_for('ally_hours.register'))
        
        # Validar acceso al emprendedor
        if not _ally_has_access_to_entrepreneur(ally, entrepreneur):
            flash('No tienes acceso a este emprendedor.', 'error')
            return redirect(url_for('ally_hours.register'))
        
        # Validar proyecto si se especifica
        project = None
        if project_id:
            project = Project.query.get(project_id)
            if not project or project.ally_id != ally.id:
                flash('Proyecto seleccionado no válido.', 'error')
                return redirect(url_for('ally_hours.register'))
        
        # Validar tarifa horaria
        rate = ally.default_hourly_rate
        if billable and hourly_rate:
            try:
                rate = float(hourly_rate)
                if rate < 0:
                    flash('La tarifa horaria no puede ser negativa.', 'error')
                    return redirect(url_for('ally_hours.register'))
            except ValueError:
                flash('Formato de tarifa horaria inválido.', 'error')
                return redirect(url_for('ally_hours.register'))
        
        # Verificar si ya existe un registro para la misma fecha y emprendedor
        existing_meeting = (
            Meeting.query
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.entrepreneur_id == entrepreneur_id,
                func.date(Meeting.date) == work_date
            )
            .first()
        )
        
        if existing_meeting:
            flash('Ya existe un registro de horas para este emprendedor en esta fecha.', 'warning')
            return redirect(url_for('ally_hours.register'))
        
        # Crear nueva reunión/registro de horas
        meeting = Meeting(
            ally_id=ally.id,
            entrepreneur_id=entrepreneur_id,
            project_id=project_id,
            date=datetime.combine(work_date, datetime.min.time()),
            duration_hours=hours,
            activity_type=activity_type,
            description=description,
            billable=billable,
            hourly_rate=rate if billable else None,
            completed=True,
            created_by=current_user.id
        )
        
        db.session.add(meeting)
        db.session.commit()
        
        # Enviar notificación al emprendedor
        if current_app.config.get('ENABLE_NOTIFICATIONS', True):
            NotificationService.send_hours_registered_notification(
                entrepreneur, ally, meeting
            )
        
        # Actualizar analytics
        AnalyticsService.track_hours_registered(ally.id, hours, billable)
        
        flash(f'Registro de {format_hours(hours)} completado exitosamente.', 'success')
        return redirect(url_for('ally_hours.index'))
        
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(url_for('ally_hours.register'))
    except Exception as e:
        current_app.logger.error(f"Error al registrar horas: {str(e)}")
        flash('Error interno al registrar las horas.', 'error')
        return redirect(url_for('ally_hours.register'))


@ally_hours_bp.route('/list')
@login_required
@require_role('ally')
@log_activity('view_hours_list')
def list_hours():
    """
    Lista de todas las horas registradas con filtros y paginación.
    
    Permite filtrar por fecha, emprendedor, proyecto y tipo de actividad.
    Incluye opciones de exportación y edición.
    """
    try:
        ally = current_user.ally
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Filtros
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        entrepreneur_id = request.args.get('entrepreneur_id')
        project_id = request.args.get('project_id')
        activity_type = request.args.get('activity_type')
        billable_filter = request.args.get('billable')
        
        # Consulta base
        query = (
            Meeting.query
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == True
            )
            .order_by(Meeting.date.desc())
        )
        
        # Aplicar filtros de fecha
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(func.date(Meeting.date) >= start_date)
            except ValueError:
                flash('Formato de fecha de inicio inválido.', 'warning')
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(func.date(Meeting.date) <= end_date)
            except ValueError:
                flash('Formato de fecha de fin inválido.', 'warning')
        
        # Filtro por emprendedor
        if entrepreneur_id:
            query = query.filter(Meeting.entrepreneur_id == entrepreneur_id)
        
        # Filtro por proyecto
        if project_id:
            query = query.filter(Meeting.project_id == project_id)
        
        # Filtro por tipo de actividad
        if activity_type:
            query = query.filter(Meeting.activity_type == activity_type)
        
        # Filtro por facturación
        if billable_filter == 'true':
            query = query.filter(Meeting.billable == True)
        elif billable_filter == 'false':
            query = query.filter(Meeting.billable == False)
        
        # Paginación
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        meetings = pagination.items
        
        # Calcular totales
        total_hours = sum(meeting.duration_hours for meeting in meetings)
        total_billable_hours = sum(
            meeting.duration_hours for meeting in meetings if meeting.billable
        )
        total_earnings = sum(
            meeting.duration_hours * (meeting.hourly_rate or 0)
            for meeting in meetings if meeting.billable
        )
        
        # Datos para filtros
        entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(Project.ally_id == ally.id)
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        projects = (
            Project.query
            .filter(Project.ally_id == ally.id)
            .order_by(Project.name)
            .all()
        )
        
        activity_types = [
            ('mentoring', 'Mentoría'),
            ('consultation', 'Consultoría'),
            ('workshop', 'Taller'),
            ('review', 'Revisión'),
            ('planning', 'Planificación'),
            ('research', 'Investigación'),
            ('presentation', 'Presentación'),
            ('other', 'Otro')
        ]
        
        return render_template(
            'ally/hours/list.html',
            pagination=pagination,
            meetings=meetings,
            entrepreneurs=entrepreneurs,
            projects=projects,
            activity_types=activity_types,
            total_hours=total_hours,
            total_billable_hours=total_billable_hours,
            total_earnings=total_earnings,
            current_filters={
                'start_date': start_date_str,
                'end_date': end_date_str,
                'entrepreneur_id': entrepreneur_id,
                'project_id': project_id,
                'activity_type': activity_type,
                'billable': billable_filter
            },
            format_currency=format_currency,
            format_hours=format_hours
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al listar horas: {str(e)}")
        flash('Error al cargar la lista de horas.', 'error')
        return redirect(url_for('ally_hours.index'))


@ally_hours_bp.route('/edit/<int:meeting_id>')
@login_required
@require_role('ally')
@require_ally_access
@log_activity('edit_hours_form')
def edit(meeting_id):
    """
    Formulario para editar un registro de horas existente.
    
    Solo permite editar registros propios del aliado y dentro
    del período permitido de edición.
    """
    try:
        ally = current_user.ally
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Verificar permisos
        if meeting.ally_id != ally.id:
            abort(403)
        
        # Verificar si está dentro del período de edición permitido
        days_since_meeting = (datetime.now(timezone.utc).date() - meeting.date.date()).days
        max_edit_days = current_app.config.get('MAX_HOURS_EDIT_DAYS', 7)
        
        if days_since_meeting > max_edit_days:
            flash(f'No se pueden editar registros de más de {max_edit_days} días.', 'error')
            return redirect(url_for('ally_hours.list_hours'))
        
        # Obtener datos para el formulario
        entrepreneurs = (
            Entrepreneur.query
            .join(Project)
            .filter(Project.ally_id == ally.id)
            .distinct()
            .order_by(Entrepreneur.name)
            .all()
        )
        
        projects = (
            Project.query
            .filter(Project.ally_id == ally.id)
            .order_by(Project.name)
            .all()
        )
        
        activity_types = [
            ('mentoring', 'Mentoría'),
            ('consultation', 'Consultoría'),
            ('workshop', 'Taller'),
            ('review', 'Revisión'),
            ('planning', 'Planificación'),
            ('research', 'Investigación'),
            ('presentation', 'Presentación'),
            ('other', 'Otro')
        ]
        
        return render_template(
            'ally/hours/edit.html',
            meeting=meeting,
            entrepreneurs=entrepreneurs,
            projects=projects,
            activity_types=activity_types,
            max_edit_days=max_edit_days
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar formulario de edición: {str(e)}")
        flash('Error al cargar el formulario de edición.', 'error')
        return redirect(url_for('ally_hours.list_hours'))


@ally_hours_bp.route('/edit/<int:meeting_id>', methods=['POST'])
@login_required
@require_role('ally')
@require_ally_access
@handle_db_errors
@log_activity('edit_hours')
def edit_post(meeting_id):
    """
    Procesa la edición de un registro de horas existente.
    
    Valida los cambios y actualiza el registro en la base de datos.
    """
    try:
        ally = current_user.ally
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Verificar permisos
        if meeting.ally_id != ally.id:
            abort(403)
        
        # Verificar período de edición
        days_since_meeting = (datetime.now(timezone.utc).date() - meeting.date.date()).days
        max_edit_days = current_app.config.get('MAX_HOURS_EDIT_DAYS', 7)
        
        if days_since_meeting > max_edit_days:
            flash(f'No se pueden editar registros de más de {max_edit_days} días.', 'error')
            return redirect(url_for('ally_hours.list_hours'))
        
        # Obtener datos del formulario
        date_str = request.form.get('date')
        hours_str = request.form.get('hours')
        entrepreneur_id = request.form.get('entrepreneur_id')
        project_id = request.form.get('project_id')
        activity_type = request.form.get('activity_type')
        description = request.form.get('description', '').strip()
        billable = request.form.get('billable') == 'on'
        hourly_rate = request.form.get('hourly_rate')
        
        # Validaciones similares al registro
        if not all([date_str, hours_str, entrepreneur_id, activity_type]):
            flash('Todos los campos obligatorios deben ser completados.', 'error')
            return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Validar fecha
        try:
            work_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if work_date > datetime.now(timezone.utc).date():
                flash('No se pueden registrar horas para fechas futuras.', 'error')
                return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        except ValueError:
            flash('Formato de fecha inválido.', 'error')
            return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Validar horas
        try:
            hours = float(hours_str)
            if hours <= 0 or hours > 24:
                flash('Las horas deben estar entre 0.1 y 24.', 'error')
                return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        except ValueError:
            flash('Formato de horas inválido.', 'error')
            return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Validar emprendedor
        entrepreneur = Entrepreneur.query.get(entrepreneur_id)
        if not entrepreneur or not _ally_has_access_to_entrepreneur(ally, entrepreneur):
            flash('Emprendedor seleccionado no válido.', 'error')
            return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Validar proyecto
        project = None
        if project_id:
            project = Project.query.get(project_id)
            if not project or project.ally_id != ally.id:
                flash('Proyecto seleccionado no válido.', 'error')
                return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Validar tarifa
        rate = ally.default_hourly_rate
        if billable and hourly_rate:
            try:
                rate = float(hourly_rate)
                if rate < 0:
                    flash('La tarifa horaria no puede ser negativa.', 'error')
                    return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
            except ValueError:
                flash('Formato de tarifa horaria inválido.', 'error')
                return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))
        
        # Actualizar el registro
        old_values = {
            'hours': meeting.duration_hours,
            'billable': meeting.billable,
            'entrepreneur_id': meeting.entrepreneur_id
        }
        
        meeting.date = datetime.combine(work_date, datetime.min.time())
        meeting.duration_hours = hours
        meeting.entrepreneur_id = entrepreneur_id
        meeting.project_id = project_id
        meeting.activity_type = activity_type
        meeting.description = description
        meeting.billable = billable
        meeting.hourly_rate = rate if billable else None
        meeting.updated_at = datetime.now(timezone.utc)
        meeting.updated_by = current_user.id
        
        db.session.commit()
        
        # Log de cambios si es significativo
        if (old_values['hours'] != hours or 
            old_values['billable'] != billable or 
            old_values['entrepreneur_id'] != entrepreneur_id):
            
            current_app.logger.info(
                f"Horas editadas por ally {ally.id}: "
                f"meeting {meeting_id}, cambios: {old_values} -> nuevos valores"
            )
        
        flash('Registro de horas actualizado exitosamente.', 'success')
        return redirect(url_for('ally_hours.list_hours'))
        
    except Exception as e:
        current_app.logger.error(f"Error al editar horas: {str(e)}")
        flash('Error interno al actualizar el registro.', 'error')
        return redirect(url_for('ally_hours.edit', meeting_id=meeting_id))


@ally_hours_bp.route('/delete/<int:meeting_id>', methods=['POST'])
@login_required
@require_role('ally')
@require_ally_access
@handle_db_errors
@log_activity('delete_hours')
def delete(meeting_id):
    """
    Elimina un registro de horas existente.
    
    Solo permite eliminar registros propios y dentro del período permitido.
    """
    try:
        ally = current_user.ally
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Verificar permisos
        if meeting.ally_id != ally.id:
            abort(403)
        
        # Verificar período de eliminación
        days_since_meeting = (datetime.now(timezone.utc).date() - meeting.date.date()).days
        max_delete_days = current_app.config.get('MAX_HOURS_DELETE_DAYS', 3)
        
        if days_since_meeting > max_delete_days:
            flash(f'No se pueden eliminar registros de más de {max_delete_days} días.', 'error')
            return redirect(url_for('ally_hours.list_hours'))
        
        # Guardar información para el log
        hours_deleted = meeting.duration_hours
        entrepreneur_name = meeting.entrepreneur.name if meeting.entrepreneur else 'N/A'
        
        db.session.delete(meeting)
        db.session.commit()
        
        current_app.logger.info(
            f"Registro de horas eliminado por ally {ally.id}: "
            f"{hours_deleted}h con {entrepreneur_name}"
        )
        
        flash(f'Registro de {format_hours(hours_deleted)} eliminado exitosamente.', 'success')
        return redirect(url_for('ally_hours.list_hours'))
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar horas: {str(e)}")
        flash('Error interno al eliminar el registro.', 'error')
        return redirect(url_for('ally_hours.list_hours'))


@ally_hours_bp.route('/export')
@login_required
@require_role('ally')
@log_activity('export_hours')
def export():
    """
    Exporta los registros de horas en formato PDF o Excel.
    
    Permite exportar todos los registros o filtrar por período.
    """
    try:
        ally = current_user.ally
        format_type = request.args.get('format', 'pdf')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Consulta base
        query = (
            Meeting.query
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == True
            )
            .order_by(Meeting.date.desc())
        )
        
        # Aplicar filtros de fecha si se proporcionan
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(func.date(Meeting.date) >= start_date)
            except ValueError:
                flash('Formato de fecha de inicio inválido.', 'error')
                return redirect(url_for('ally_hours.list_hours'))
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(func.date(Meeting.date) <= end_date)
            except ValueError:
                flash('Formato de fecha de fin inválido.', 'error')
                return redirect(url_for('ally_hours.list_hours'))
        
        meetings = query.all()
        
        if not meetings:
            flash('No hay registros para exportar con los filtros seleccionados.', 'warning')
            return redirect(url_for('ally_hours.list_hours'))
        
        # Generar archivo según el formato
        if format_type == 'excel':
            file_path = generate_hours_report_excel(ally, meetings, start_date_str, end_date_str)
            filename = f'horas_reporte_{ally.id}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.xlsx'
        else:  # PDF por defecto
            file_path = generate_hours_report_pdf(ally, meetings, start_date_str, end_date_str)
            filename = f'horas_reporte_{ally.id}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.pdf'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al exportar horas: {str(e)}")
        flash('Error al generar el reporte de exportación.', 'error')
        return redirect(url_for('ally_hours.list_hours'))


@ally_hours_bp.route('/stats')
@login_required
@require_role('ally')
@log_activity('view_hours_stats')
def stats():
    """
    Página de estadísticas detalladas de horas trabajadas.
    
    Incluye gráficos, tendencias y análisis comparativo.
    """
    try:
        ally = current_user.ally
        period = request.args.get('period', 'last_6_months')
        
        start_date, end_date = _get_date_range_for_period(period)
        
        # Estadísticas generales
        stats_data = AnalyticsService.get_ally_hours_stats(
            ally.id, start_date, end_date
        )
        
        # Comparación con período anterior
        previous_start, previous_end = _get_previous_period_range(start_date, end_date)
        previous_stats = AnalyticsService.get_ally_hours_stats(
            ally.id, previous_start, previous_end
        )
        
        # Calcular cambios porcentuales
        changes = _calculate_period_changes(stats_data, previous_stats)
        
        return render_template(
            'ally/hours/stats.html',
            ally=ally,
            period=period,
            start_date=start_date,
            end_date=end_date,
            stats=stats_data,
            previous_stats=previous_stats,
            changes=changes,
            format_currency=format_currency,
            format_hours=format_hours
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar estadísticas: {str(e)}")
        flash('Error al cargar las estadísticas.', 'error')
        return redirect(url_for('ally_hours.index'))


# API Endpoints para AJAX

@ally_hours_bp.route('/api/entrepreneurs/<int:project_id>')
@login_required
@require_role('ally')
def api_get_entrepreneurs_by_project(project_id):
    """API endpoint para obtener emprendedores por proyecto."""
    try:
        ally = current_user.ally
        project = Project.query.filter_by(id=project_id, ally_id=ally.id).first()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        entrepreneurs = []
        if project.entrepreneur:
            entrepreneurs.append({
                'id': project.entrepreneur.id,
                'name': project.entrepreneur.name,
                'email': project.entrepreneur.email
            })
        
        return jsonify({'entrepreneurs': entrepreneurs})
        
    except Exception as e:
        current_app.logger.error(f"Error en API entrepreneurs: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@ally_hours_bp.route('/api/quick-stats')
@login_required
@require_role('ally')
def api_quick_stats():
    """API endpoint para estadísticas rápidas del dashboard."""
    try:
        ally = current_user.ally
        period = request.args.get('period', 'current_week')
        
        start_date, end_date = _get_date_range_for_period(period)
        
        # Consulta rápida de estadísticas
        stats = (
            db.session.query(
                func.sum(Meeting.duration_hours).label('total_hours'),
                func.count(Meeting.id).label('total_meetings'),
                func.sum(
                    func.case(
                        [(Meeting.billable == True, Meeting.duration_hours)],
                        else_=0
                    )
                ).label('billable_hours'),
                func.sum(
                    func.case(
                        [(Meeting.billable == True, Meeting.duration_hours * Meeting.hourly_rate)],
                        else_=0
                    )
                ).label('total_earnings')
            )
            .filter(
                Meeting.ally_id == ally.id,
                Meeting.completed == True,
                Meeting.date >= start_date,
                Meeting.date <= end_date
            )
            .first()
        )
        
        return jsonify({
            'total_hours': float(stats.total_hours or 0),
            'total_meetings': stats.total_meetings or 0,
            'billable_hours': float(stats.billable_hours or 0),
            'total_earnings': float(stats.total_earnings or 0),
            'period': period,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en API quick stats: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


# Funciones auxiliares privadas

def _get_date_range_for_period(period):
    """Obtiene el rango de fechas para un período dado."""
    today = datetime.now(timezone.utc).date()
    
    if period == 'current_week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'current_month':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    elif period == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == 'last_6_months':
        start_date = today - timedelta(days=180)
        end_date = today
    elif period == 'current_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # current_month por defecto
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    return start_date, end_date


def _get_previous_period_range(start_date, end_date):
    """Calcula el rango del período anterior para comparación."""
    period_length = (end_date - start_date).days
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_length)
    return previous_start, previous_end


def _calculate_period_changes(current_stats, previous_stats):
    """Calcula los cambios porcentuales entre períodos."""
    changes = {}
    
    for key in ['total_hours', 'total_meetings', 'billable_hours', 'total_earnings']:
        current_value = getattr(current_stats, key, 0) or 0
        previous_value = getattr(previous_stats, key, 0) or 0
        
        if previous_value > 0:
            change = ((current_value - previous_value) / previous_value) * 100
        else:
            change = 100 if current_value > 0 else 0
        
        changes[key] = round(change, 1)
    
    return changes


def _ally_has_access_to_entrepreneur(ally, entrepreneur):
    """Verifica si un aliado tiene acceso a un emprendedor específico."""
    return (
        Project.query
        .filter(
            Project.ally_id == ally.id,
            Project.entrepreneur_id == entrepreneur.id
        )
        .first() is not None
    )


# Registrar manejadores de errores específicos

@ally_hours_bp.errorhandler(403)
def forbidden(error):
    """Maneja errores de acceso prohibido."""
    flash('No tienes permisos para acceder a este recurso.', 'error')
    return redirect(url_for('ally_hours.index'))


@ally_hours_bp.errorhandler(404)
def not_found(error):
    """Maneja errores de recurso no encontrado."""
    flash('El registro de horas solicitado no existe.', 'error')
    return redirect(url_for('ally_hours.list_hours'))


@ally_hours_bp.errorhandler(500)
def internal_error(error):
    """Maneja errores internos del servidor."""
    db.session.rollback()
    current_app.logger.error(f"Error interno en ally hours: {str(error)}")
    flash('Error interno del servidor. Por favor, intenta nuevamente.', 'error')
    return redirect(url_for('ally_hours.index'))