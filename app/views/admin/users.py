"""
Gestión de Usuarios - Panel Administrativo
==========================================

Este módulo contiene todas las funcionalidades para la gestión de usuarios
desde el panel administrativo, incluyendo CRUD, roles, permisos y estadísticas.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, text
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required
from app.core.exceptions import ValidationError, AuthorizationError, BusinessLogicError
from app.core.constants import (
    USER_ROLES, USER_STATUS, ACTIVITY_TYPES, NOTIFICATION_TYPES,
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE
)
from app.core.security import validate_password_strength, generate_secure_token

# Importaciones de modelos
from app.models import (
    User, Admin, Entrepreneur, Ally, Client, Organization, Program,
    Project, Meeting, Document, ActivityLog, Notification
)

# Importaciones de servicios
from app.services.user_service import UserService
from app.services.email import EmailService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.services.file_storage import FileStorageService

# Importaciones de formularios
from app.forms.admin import (
    CreateUserForm, EditUserForm, BulkActionForm, UserFilterForm,
    ChangePasswordForm, AssignRoleForm, ImportUsersForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.validators import validate_email, validate_phone
from app.utils.formatters import format_date, format_currency, format_number
from app.utils.export_utils import export_to_excel, export_to_pdf, export_to_csv
from app.utils.import_utils import import_from_excel, import_from_csv
from app.utils.file_utils import allowed_file, get_file_extension
from app.utils.string_utils import generate_username, slugify

# Extensiones
from app.extensions import db, cache

# Crear blueprint
admin_users = Blueprint('admin_users', __name__, url_prefix='/admin/users')

# ============================================================================
# VISTAS PRINCIPALES - LISTADO Y GESTIÓN
# ============================================================================

@admin_users.route('/')
@admin_users.route('/list')
@login_required
@admin_required
@handle_exceptions
def list_users():
    """
    Lista todos los usuarios con filtros, búsqueda y paginación.
    Incluye estadísticas básicas y acciones en lote.
    """
    try:
        # Parámetros de consulta
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        search = request.args.get('search', '').strip()
        role_filter = request.args.get('role', 'all')
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Construir query base
        query = User.query.options(
            selectinload(User.entrepreneur),
            selectinload(User.ally),
            selectinload(User.client),
            selectinload(User.admin)
        )
        
        # Aplicar filtros
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.phone.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        if role_filter != 'all':
            query = query.filter(User.role == role_filter)
            
        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)
        elif status_filter == 'verified':
            query = query.filter(User.email_verified == True)
        elif status_filter == 'unverified':
            query = query.filter(User.email_verified == False)
            
        # Filtros de fecha
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(User.created_at >= from_date)
            except ValueError:
                flash('Fecha de inicio inválida.', 'warning')
                
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(User.created_at <= to_date)
            except ValueError:
                flash('Fecha de fin inválida.', 'warning')
        
        # Aplicar ordenamiento
        if sort_by == 'name':
            order_field = User.first_name
        elif sort_by == 'email':
            order_field = User.email
        elif sort_by == 'role':
            order_field = User.role
        elif sort_by == 'last_login':
            order_field = User.last_login
        else:  # created_at por defecto
            order_field = User.created_at
            
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
        
        # Paginación
        users = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
            max_per_page=100
        )
        
        # Estadísticas rápidas
        stats = _get_user_statistics()
        
        # Formularios
        filter_form = UserFilterForm(request.args)
        bulk_action_form = BulkActionForm()
        
        return render_template(
            'admin/users/list.html',
            users=users,
            stats=stats,
            filter_form=filter_form,
            bulk_action_form=bulk_action_form,
            current_filters={
                'search': search,
                'role': role_filter,
                'status': status_filter,
                'sort': sort_by,
                'order': sort_order,
                'date_from': date_from,
                'date_to': date_to
            },
            user_roles=USER_ROLES,
            user_status=USER_STATUS
        )
        
    except Exception as e:
        current_app.logger.error(f"Error listando usuarios: {str(e)}")
        flash('Error al cargar la lista de usuarios.', 'error')
        return redirect(url_for('admin_dashboard.index'))

@admin_users.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('create_user')
@handle_exceptions
def create_user():
    """
    Crea un nuevo usuario con el rol especificado.
    Envía email de bienvenida y configura perfil inicial.
    """
    form = CreateUserForm()
    
    if form.validate_on_submit():
        try:
            user_service = UserService()
            email_service = EmailService()
            
            # Validaciones adicionales
            if User.query.filter_by(email=form.email.data.lower()).first():
                flash('Este email ya está registrado en el sistema.', 'error')
                return render_template('admin/users/create.html', form=form)
            
            # Validar fortaleza de contraseña si se proporciona
            if form.password.data:
                is_valid, message = validate_password_strength(form.password.data)
                if not is_valid:
                    flash(f'Contraseña insegura: {message}', 'error')
                    return render_template('admin/users/create.html', form=form)
            
            # Crear usuario base
            user_data = {
                'first_name': form.first_name.data.strip(),
                'last_name': form.last_name.data.strip(),
                'email': form.email.data.lower().strip(),
                'phone': form.phone.data.strip() if form.phone.data else None,
                'role': form.role.data,
                'is_active': form.is_active.data,
                'email_verified': form.send_welcome_email.data,
                'created_by_admin': True
            }
            
            # Generar contraseña si no se proporciona
            if form.password.data:
                user_data['password'] = generate_password_hash(form.password.data)
                temp_password = form.password.data
            else:
                temp_password = generate_secure_token(12)
                user_data['password'] = generate_password_hash(temp_password)
            
            # Crear usuario usando el servicio
            user = user_service.create_user(user_data)
            
            # Crear perfil específico según el rol
            if form.role.data == 'entrepreneur':
                entrepreneur = Entrepreneur(
                    user_id=user.id,
                    business_stage=form.business_stage.data if hasattr(form, 'business_stage') else 'idea',
                    industry=form.industry.data if hasattr(form, 'industry') else None
                )
                db.session.add(entrepreneur)
                
            elif form.role.data == 'ally':
                ally = Ally(
                    user_id=user.id,
                    expertise_areas=form.expertise_areas.data if hasattr(form, 'expertise_areas') else [],
                    hourly_rate=form.hourly_rate.data if hasattr(form, 'hourly_rate') else None,
                    availability=form.availability.data if hasattr(form, 'availability') else 'part_time'
                )
                db.session.add(ally)
                
            elif form.role.data == 'client':
                client = Client(
                    user_id=user.id,
                    organization_type=form.organization_type.data if hasattr(form, 'organization_type') else 'corporate',
                    interest_areas=form.interest_areas.data if hasattr(form, 'interest_areas') else []
                )
                db.session.add(client)
                
            elif form.role.data == 'admin':
                admin = Admin(
                    user_id=user.id,
                    permissions=form.permissions.data if hasattr(form, 'permissions') else ['basic'],
                    can_create_users=form.can_create_users.data if hasattr(form, 'can_create_users') else False
                )
                db.session.add(admin)
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='create_user',
                resource_type='User',
                resource_id=user.id,
                details=f'Usuario creado: {user.email} ({user.role})'
            )
            db.session.add(activity)
            db.session.commit()
            
            # Enviar email de bienvenida si está habilitado
            if form.send_welcome_email.data:
                try:
                    email_service.send_welcome_email(
                        user=user,
                        temp_password=temp_password,
                        created_by_admin=True
                    )
                    flash(f'Usuario {user.full_name} creado exitosamente. Email de bienvenida enviado.', 'success')
                except Exception as e:
                    current_app.logger.warning(f"Error enviando email de bienvenida: {str(e)}")
                    flash(f'Usuario creado, pero no se pudo enviar el email de bienvenida.', 'warning')
            else:
                flash(f'Usuario {user.full_name} creado exitosamente.', 'success')
            
            return redirect(url_for('admin_users.view_user', user_id=user.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except BusinessLogicError as e:
            flash(f'Error de lógica de negocio: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando usuario: {str(e)}")
            flash('Error interno al crear el usuario. Inténtalo de nuevo.', 'error')
    
    return render_template('admin/users/create.html', form=form)

@admin_users.route('/<int:user_id>')
@login_required
@admin_required
@handle_exceptions
def view_user(user_id):
    """
    Vista detallada de un usuario específico.
    Incluye estadísticas, actividad reciente y acciones disponibles.
    """
    try:
        user = User.query.options(
            joinedload(User.entrepreneur),
            joinedload(User.ally),
            joinedload(User.client),
            joinedload(User.admin)
        ).get_or_404(user_id)
        
        # Estadísticas del usuario
        user_stats = _get_user_detailed_stats(user)
        
        # Actividad reciente
        recent_activities = ActivityLog.query.filter_by(
            user_id=user.id
        ).order_by(desc(ActivityLog.created_at)).limit(10).all()
        
        # Proyectos si es emprendedor
        projects = []
        if user.role == 'entrepreneur' and user.entrepreneur:
            projects = Project.query.filter_by(
                entrepreneur_id=user.entrepreneur.id
            ).order_by(desc(Project.updated_at)).limit(5).all()
        
        # Reuniones recientes
        recent_meetings = Meeting.query.filter(
            or_(
                Meeting.organizer_id == user.id,
                Meeting.participants.any(User.id == user.id)
            )
        ).order_by(desc(Meeting.created_at)).limit(5).all()
        
        # Documentos subidos
        documents = Document.query.filter_by(
            uploaded_by=user.id
        ).order_by(desc(Document.uploaded_at)).limit(5).all()
        
        return render_template(
            'admin/users/view.html',
            user=user,
            user_stats=user_stats,
            recent_activities=recent_activities,
            projects=projects,
            recent_meetings=recent_meetings,
            documents=documents
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viendo usuario {user_id}: {str(e)}")
        flash('Error al cargar los datos del usuario.', 'error')
        return redirect(url_for('admin_users.list_users'))

@admin_users.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('edit_user')
@handle_exceptions
def edit_user(user_id):
    """
    Edita la información de un usuario existente.
    Permite modificar datos básicos, rol y configuraciones.
    """
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    # Prevenir auto-edición de admin principal
    if user.id == current_user.id and form.is_active.data == False:
        flash('No puedes desactivar tu propia cuenta.', 'warning')
        return redirect(url_for('admin_users.view_user', user_id=user_id))
    
    if form.validate_on_submit():
        try:
            # Verificar si el email cambió y ya existe
            if form.email.data.lower() != user.email:
                existing_user = User.query.filter_by(email=form.email.data.lower()).first()
                if existing_user:
                    flash('Este email ya está registrado por otro usuario.', 'error')
                    return render_template('admin/users/edit.html', form=form, user=user)
            
            # Almacenar valores anteriores para auditoría
            old_values = {
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            
            # Actualizar datos básicos
            user.first_name = form.first_name.data.strip()
            user.last_name = form.last_name.data.strip()
            user.email = form.email.data.lower().strip()
            user.phone = form.phone.data.strip() if form.phone.data else None
            user.is_active = form.is_active.data
            user.email_verified = form.email_verified.data
            user.updated_at = datetime.utcnow()
            
            # Cambio de rol si es necesario
            if form.role.data != user.role:
                user_service = UserService()
                user_service.change_user_role(user, form.role.data)
            
            db.session.commit()
            
            # Registrar cambios en auditoría
            changes = []
            for field, old_value in old_values.items():
                new_value = getattr(user, field)
                if old_value != new_value:
                    changes.append(f'{field}: {old_value} → {new_value}')
            
            if changes:
                activity = ActivityLog(
                    user_id=current_user.id,
                    action='update_user',
                    resource_type='User',
                    resource_id=user.id,
                    details=f'Usuario actualizado: {", ".join(changes)}'
                )
                db.session.add(activity)
                db.session.commit()
            
            # Notificar al usuario si hay cambios importantes
            if not user.is_active and old_values['is_active']:
                notification_service = NotificationService()
                notification_service.send_notification(
                    user_id=user.id,
                    type='account_suspended',
                    title='Cuenta Suspendida',
                    message='Tu cuenta ha sido suspendida. Contacta al administrador.',
                    priority='high'
                )
            
            flash(f'Usuario {user.full_name} actualizado exitosamente.', 'success')
            return redirect(url_for('admin_users.view_user', user_id=user.id))
            
        except ValidationError as e:
            flash(f'Error de validación: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error actualizando usuario {user_id}: {str(e)}")
            flash('Error al actualizar el usuario.', 'error')
    
    return render_template('admin/users/edit.html', form=form, user=user)

# ============================================================================
# GESTIÓN DE CONTRASEÑAS Y SEGURIDAD
# ============================================================================

@admin_users.route('/<int:user_id>/change-password', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('change_user_password')
@handle_exceptions
def change_password(user_id):
    """
    Cambia la contraseña de un usuario específico.
    Solo disponible para administradores con permisos especiales.
    """
    user = User.query.get_or_404(user_id)
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        try:
            # Validar fortaleza de la nueva contraseña
            is_valid, message = validate_password_strength(form.new_password.data)
            if not is_valid:
                flash(f'Contraseña insegura: {message}', 'error')
                return render_template('admin/users/change_password.html', form=form, user=user)
            
            # Actualizar contraseña
            user.password = generate_password_hash(form.new_password.data)
            user.password_changed_at = datetime.utcnow()
            user.force_password_change = form.force_change_on_login.data
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='change_user_password',
                resource_type='User',
                resource_id=user.id,
                details=f'Contraseña cambiada para usuario: {user.email}'
            )
            db.session.add(activity)
            db.session.commit()
            
            # Notificar al usuario
            if form.notify_user.data:
                try:
                    email_service = EmailService()
                    email_service.send_password_changed_notification(user)
                except Exception as e:
                    current_app.logger.warning(f"Error enviando notificación: {str(e)}")
            
            flash(f'Contraseña cambiada exitosamente para {user.full_name}.', 'success')
            return redirect(url_for('admin_users.view_user', user_id=user.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cambiando contraseña: {str(e)}")
            flash('Error al cambiar la contraseña.', 'error')
    
    return render_template('admin/users/change_password.html', form=form, user=user)

@admin_users.route('/<int:user_id>/reset-password')
@login_required
@admin_required
@permission_required('reset_user_password')
@handle_exceptions
def reset_password(user_id):
    """
    Envía un email de recuperación de contraseña al usuario.
    Genera un token seguro para el proceso de recuperación.
    """
    try:
        user = User.query.get_or_404(user_id)
        
        if not user.is_active:
            flash('No se puede resetear la contraseña de un usuario inactivo.', 'warning')
            return redirect(url_for('admin_users.view_user', user_id=user_id))
        
        # Generar token de recuperación
        reset_token = generate_secure_token(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
        
        db.session.commit()
        
        # Enviar email de recuperación
        email_service = EmailService()
        email_service.send_password_reset_email(user, reset_token)
        
        # Registrar actividad
        activity = ActivityLog(
            user_id=current_user.id,
            action='reset_user_password',
            resource_type='User',
            resource_id=user.id,
            details=f'Reset de contraseña iniciado para: {user.email}'
        )
        db.session.add(activity)
        db.session.commit()
        
        flash(f'Email de recuperación enviado a {user.email}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reseteando contraseña: {str(e)}")
        flash('Error al enviar el email de recuperación.', 'error')
    
    return redirect(url_for('admin_users.view_user', user_id=user_id))

# ============================================================================
# ACCIONES EN LOTE
# ============================================================================

@admin_users.route('/bulk-actions', methods=['POST'])
@login_required
@admin_required
@permission_required('bulk_user_actions')
@handle_exceptions
def bulk_actions():
    """
    Ejecuta acciones en lote sobre múltiples usuarios.
    Soporta activar, desactivar, eliminar y cambiar roles.
    """
    form = BulkActionForm()
    
    if form.validate_on_submit():
        try:
            user_ids = [int(id) for id in form.user_ids.data.split(',') if id.strip()]
            action = form.action.data
            
            if not user_ids:
                flash('No se seleccionaron usuarios.', 'warning')
                return redirect(url_for('admin_users.list_users'))
            
            # Verificar que no se incluya el usuario actual en operaciones peligrosas
            if current_user.id in user_ids and action in ['deactivate', 'delete']:
                flash('No puedes realizar esta acción sobre tu propia cuenta.', 'error')
                return redirect(url_for('admin_users.list_users'))
            
            users = User.query.filter(User.id.in_(user_ids)).all()
            
            if len(users) != len(user_ids):
                flash('Algunos usuarios seleccionados no existen.', 'warning')
            
            success_count = 0
            
            for user in users:
                try:
                    if action == 'activate':
                        user.is_active = True
                        success_count += 1
                        
                    elif action == 'deactivate':
                        user.is_active = False
                        success_count += 1
                        
                    elif action == 'verify_email':
                        user.email_verified = True
                        success_count += 1
                        
                    elif action == 'unverify_email':
                        user.email_verified = False
                        success_count += 1
                        
                    elif action == 'delete':
                        # Soft delete - marcar como eliminado
                        user.is_deleted = True
                        user.deleted_at = datetime.utcnow()
                        success_count += 1
                        
                    elif action == 'change_role' and form.new_role.data:
                        user_service = UserService()
                        user_service.change_user_role(user, form.new_role.data)
                        success_count += 1
                        
                except Exception as e:
                    current_app.logger.warning(f"Error procesando usuario {user.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=current_user.id,
                action='bulk_user_action',
                resource_type='User',
                details=f'Acción en lote: {action} aplicada a {success_count} usuarios'
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Acción aplicada exitosamente a {success_count} usuario(s).', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error en acción en lote: {str(e)}")
            flash('Error al ejecutar la acción en lote.', 'error')
    else:
        flash('Datos de formulario inválidos.', 'error')
    
    return redirect(url_for('admin_users.list_users'))

# ============================================================================
# ESTADÍSTICAS Y ANALYTICS
# ============================================================================

@admin_users.route('/statistics')
@login_required
@admin_required
@cache_result(timeout=300)  # Cache por 5 minutos
def statistics():
    """
    Página de estadísticas detalladas de usuarios.
    Incluye gráficos, métricas y tendencias.
    """
    try:
        analytics_service = AnalyticsService()
        
        # Métricas generales
        general_stats = _get_comprehensive_user_stats()
        
        # Datos para gráficos
        charts_data = {
            'user_growth': analytics_service.get_user_growth_chart(days=90),
            'role_distribution': analytics_service.get_role_distribution_chart(),
            'registration_trends': analytics_service.get_registration_trends(days=30),
            'activity_levels': analytics_service.get_user_activity_levels(),
            'geographic_distribution': analytics_service.get_user_geographic_data()
        }
        
        # Top usuarios más activos
        most_active_users = _get_most_active_users(limit=10)
        
        # Usuarios inactivos
        inactive_users_count = User.query.filter(
            and_(
                User.is_active == True,
                or_(
                    User.last_login.is_(None),
                    User.last_login < datetime.utcnow() - timedelta(days=30)
                )
            )
        ).count()
        
        return render_template(
            'admin/users/statistics.html',
            general_stats=general_stats,
            charts_data=charts_data,
            most_active_users=most_active_users,
            inactive_users_count=inactive_users_count
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando estadísticas: {str(e)}")
        flash('Error al cargar las estadísticas.', 'error')
        return redirect(url_for('admin_users.list_users'))

# ============================================================================
# IMPORTACIÓN Y EXPORTACIÓN
# ============================================================================

@admin_users.route('/export')
@login_required
@admin_required
@permission_required('export_users')
@handle_exceptions
def export_users():
    """
    Exporta usuarios en diferentes formatos (Excel, CSV, PDF).
    Respeta los filtros aplicados en la lista de usuarios.
    """
    try:
        export_format = request.args.get('format', 'excel')
        include_inactive = request.args.get('include_inactive', 'false') == 'true'
        role_filter = request.args.get('role', 'all')
        
        # Construir query basada en filtros
        query = User.query.options(
            joinedload(User.entrepreneur),
            joinedload(User.ally),
            joinedload(User.client),
            joinedload(User.admin)
        )
        
        if not include_inactive:
            query = query.filter_by(is_active=True)
            
        if role_filter != 'all':
            query = query.filter_by(role=role_filter)
        
        users = query.order_by(User.created_at.desc()).all()
        
        # Preparar datos para exportación
        export_data = []
        for user in users:
            row = {
                'ID': user.id,
                'Nombre Completo': user.full_name,
                'Email': user.email,
                'Teléfono': user.phone or 'N/A',
                'Rol': user.role.title() if user.role else 'N/A',
                'Estado': 'Activo' if user.is_active else 'Inactivo',
                'Email Verificado': 'Sí' if user.email_verified else 'No',
                'Último Acceso': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Nunca',
                'Fecha Registro': user.created_at.strftime('%Y-%m-%d %H:%M'),
                'País': getattr(user, 'country', 'N/A'),
                'Ciudad': getattr(user, 'city', 'N/A')
            }
            
            # Agregar campos específicos del rol
            if user.role == 'entrepreneur' and user.entrepreneur:
                row['Etapa del Negocio'] = user.entrepreneur.business_stage or 'N/A'
                row['Industria'] = user.entrepreneur.industry or 'N/A'
            elif user.role == 'ally' and user.ally:
                row['Tarifa por Hora'] = f"${user.ally.hourly_rate}" if user.ally.hourly_rate else 'N/A'
                row['Disponibilidad'] = user.ally.availability or 'N/A'
            
            export_data.append(row)
        
        # Generar archivo según formato
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            filename = f'usuarios_{timestamp}.xlsx'
            return export_to_excel(export_data, filename, 'Usuarios')
            
        elif export_format == 'csv':
            filename = f'usuarios_{timestamp}.csv'
            return export_to_csv(export_data, filename)
            
        elif export_format == 'pdf':
            filename = f'usuarios_{timestamp}.pdf'
            return export_to_pdf(export_data, filename, 'Reporte de Usuarios')
            
        else:
            flash('Formato de exportación no válido.', 'error')
            return redirect(url_for('admin_users.list_users'))
        
    except Exception as e:
        current_app.logger.error(f"Error exportando usuarios: {str(e)}")
        flash('Error al exportar los usuarios.', 'error')
        return redirect(url_for('admin_users.list_users'))

@admin_users.route('/import', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('import_users')
@handle_exceptions
def import_users():
    """
    Importa usuarios masivamente desde archivo Excel o CSV.
    Valida datos y maneja errores de forma robusta.
    """
    form = ImportUsersForm()
    
    if form.validate_on_submit():
        try:
            file = form.file.data
            
            if not file or not allowed_file(file.filename):
                flash('Archivo no válido. Solo se permiten archivos Excel (.xlsx) y CSV (.csv).', 'error')
                return render_template('admin/users/import.html', form=form)
            
            # Guardar archivo temporalmente
            filename = secure_filename(file.filename)
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', filename)
            file.save(temp_path)
            
            try:
                # Procesar archivo según extensión
                file_ext = get_file_extension(filename)
                
                if file_ext in ['.xlsx', '.xls']:
                    import_data = import_from_excel(temp_path)
                else:  # CSV
                    import_data = import_from_csv(temp_path)
                
                # Validar y procesar datos
                results = _process_user_import(import_data, form.send_welcome_emails.data)
                
                flash(
                    f'Importación completada: {results["success"]} usuarios creados, '
                    f'{results["errors"]} errores, {results["skipped"]} omitidos.',
                    'success' if results["success"] > 0 else 'warning'
                )
                
                # Mostrar errores detallados si los hay
                if results["error_details"]:
                    for error in results["error_details"][:10]:  # Mostrar solo los primeros 10
                        flash(f'Línea {error["line"]}: {error["message"]}', 'warning')
                
            finally:
                # Limpiar archivo temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            return redirect(url_for('admin_users.list_users'))
            
        except Exception as e:
            current_app.logger.error(f"Error importando usuarios: {str(e)}")
            flash('Error al procesar el archivo de importación.', 'error')
    
    return render_template('admin/users/import.html', form=form)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_users.route('/api/search')
@login_required
@admin_required
@rate_limit(100, per_minute=True)
def api_search_users():
    """API endpoint para búsqueda de usuarios en tiempo real."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        
        if len(query) < 2:
            return jsonify({'users': []})
        
        users = User.query.filter(
            or_(
                User.first_name.ilike(f'%{query}%'),
                User.last_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        ).filter_by(is_active=True).limit(limit).all()
        
        return jsonify({
            'users': [
                {
                    'id': user.id,
                    'name': user.full_name,
                    'email': user.email,
                    'role': user.role,
                    'avatar_url': user.avatar_url or '/static/img/default-avatar.png'
                }
                for user in users
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_users.route('/api/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
@permission_required('toggle_user_status')
def api_toggle_user_status(user_id):
    """API endpoint para cambiar el estado activo/inactivo de un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == current_user.id:
            return jsonify({'error': 'No puedes cambiar tu propio estado'}), 400
        
        user.is_active = not user.is_active
        db.session.commit()
        
        # Registrar actividad
        activity = ActivityLog(
            user_id=current_user.id,
            action='toggle_user_status',
            resource_type='User',
            resource_id=user.id,
            details=f'Usuario {"activado" if user.is_active else "desactivado"}: {user.email}'
        )
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_active': user.is_active,
            'message': f'Usuario {"activado" if user.is_active else "desactivado"} exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_user_statistics():
    """Obtiene estadísticas básicas de usuarios."""
    return {
        'total': User.query.count(),
        'active': User.query.filter_by(is_active=True).count(),
        'inactive': User.query.filter_by(is_active=False).count(),
        'verified': User.query.filter_by(email_verified=True).count(),
        'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
        'allies': User.query.filter_by(role='ally').count(),
        'clients': User.query.filter_by(role='client').count(),
        'admins': User.query.filter_by(role='admin').count(),
        'new_this_month': User.query.filter(
            User.created_at >= datetime.utcnow().replace(day=1)
        ).count()
    }

def _get_user_detailed_stats(user):
    """Obtiene estadísticas detalladas de un usuario específico."""
    stats = {
        'login_count': getattr(user, 'login_count', 0),
        'last_activity': user.last_login,
        'account_age_days': (datetime.utcnow() - user.created_at).days,
        'documents_uploaded': Document.query.filter_by(uploaded_by=user.id).count(),
        'meetings_organized': Meeting.query.filter_by(organizer_id=user.id).count()
    }
    
    # Estadísticas específicas por rol
    if user.role == 'entrepreneur' and user.entrepreneur:
        stats.update({
            'projects_count': Project.query.filter_by(entrepreneur_id=user.entrepreneur.id).count(),
            'active_projects': Project.query.filter_by(
                entrepreneur_id=user.entrepreneur.id, 
                status='active'
            ).count()
        })
    elif user.role == 'ally' and user.ally:
        stats.update({
            'mentorship_sessions': 0,  # Implementar cuando esté el modelo
            'total_hours': getattr(user.ally, 'total_hours_logged', 0)
        })
    
    return stats

def _get_comprehensive_user_stats():
    """Obtiene estadísticas comprehensivas para la página de analytics."""
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    return {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'new_today': User.query.filter(User.created_at >= today).count(),
        'new_this_week': User.query.filter(User.created_at >= week_ago).count(),
        'new_this_month': User.query.filter(User.created_at >= month_ago).count(),
        'verified_users': User.query.filter_by(email_verified=True).count(),
        'users_with_profiles': User.query.filter(User.profile_completed == True).count(),
        'average_age': db.session.query(func.avg(
            func.extract('days', datetime.utcnow() - User.created_at)
        )).scalar() or 0
    }

def _get_most_active_users(limit=10):
    """Obtiene los usuarios más activos basado en último login y actividad."""
    return User.query.filter(
        and_(
            User.is_active == True,
            User.last_login.isnot(None)
        )
    ).order_by(desc(User.last_login)).limit(limit).all()

def _process_user_import(import_data, send_welcome_emails=False):
    """Procesa los datos de importación masiva de usuarios."""
    results = {
        'success': 0,
        'errors': 0,
        'skipped': 0,
        'error_details': []
    }
    
    user_service = UserService()
    email_service = EmailService() if send_welcome_emails else None
    
    for line_num, row in enumerate(import_data, start=2):
        try:
            # Validaciones básicas
            if not row.get('email'):
                results['error_details'].append({
                    'line': line_num,
                    'message': 'Email es requerido'
                })
                results['errors'] += 1
                continue
            
            email = row['email'].lower().strip()
            
            # Verificar si el usuario ya existe
            if User.query.filter_by(email=email).first():
                results['skipped'] += 1
                continue
            
            # Validar email
            if not validate_email(email):
                results['error_details'].append({
                    'line': line_num,
                    'message': f'Email inválido: {email}'
                })
                results['errors'] += 1
                continue
            
            # Preparar datos del usuario
            user_data = {
                'first_name': row.get('first_name', '').strip(),
                'last_name': row.get('last_name', '').strip(),
                'email': email,
                'phone': row.get('phone', '').strip() if row.get('phone') else None,
                'role': row.get('role', 'entrepreneur').lower(),
                'is_active': True,
                'email_verified': False,
                'password': generate_password_hash(generate_secure_token(12))
            }
            
            # Validar rol
            if user_data['role'] not in [role.value for role in USER_ROLES]:
                user_data['role'] = 'entrepreneur'  # Rol por defecto
            
            # Crear usuario
            user = user_service.create_user(user_data)
            
            # Enviar email de bienvenida si está habilitado
            if send_welcome_emails and email_service:
                try:
                    email_service.send_welcome_email(user, created_by_admin=True)
                except Exception as e:
                    current_app.logger.warning(f"Error enviando email a {email}: {str(e)}")
            
            results['success'] += 1
            
        except Exception as e:
            results['error_details'].append({
                'line': line_num,
                'message': str(e)
            })
            results['errors'] += 1
            continue
    
    return results