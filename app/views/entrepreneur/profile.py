"""
Perfil del Emprendedor - Gestión completa del perfil, configuraciones y preferencias.

Este módulo contiene todas las vistas relacionadas con la gestión del perfil
del emprendedor, incluyendo información personal, configuraciones de cuenta,
preferencias de notificaciones, cambio de contraseña y gestión de privacidad.
"""

import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, g
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import and_, desc
from PIL import Image
import pyotp
import qrcode
from io import BytesIO
import base64

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, FileError
from app.core.security import generate_secure_token, validate_password_strength
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.activity_log import ActivityLog
from app.models.notification import Notification, NotificationPreference
from app.models.document import Document
from app.forms.entrepreneur import (
    ProfileForm, PasswordChangeForm, PreferencesForm, 
    PrivacySettingsForm, TwoFactorForm, SocialLinksForm,
    ProfilePictureForm, BusinessInfoForm, ContactInfoForm
)
from app.services.user_service import UserService
from app.services.entrepreneur_service import EntrepreneurService
from app.services.file_storage import FileStorageService
from app.services.email import EmailService
from app.services.sms import SMSService
from app.services.oauth import OAuthService
from app.utils.decorators import rate_limit, validate_json, require_fresh_login
from app.utils.validators import validate_phone_number, validate_url, validate_social_handle
from app.utils.formatters import format_phone_number, format_currency
from app.utils.file_utils import allowed_file, get_file_extension, generate_unique_filename
from app.utils.crypto_utils import encrypt_sensitive_data, decrypt_sensitive_data
from app.utils.string_utils import sanitize_input, generate_slug

# Crear blueprint para el perfil del emprendedor
entrepreneur_profile = Blueprint(
    'entrepreneur_profile', 
    __name__, 
    url_prefix='/entrepreneur/profile'
)

# Configuración de archivos permitidos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
PROFILE_PICTURE_SIZE = (400, 400)
THUMBNAIL_SIZE = (150, 150)


@entrepreneur_profile.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.user_service = UserService(current_user)
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
    else:
        g.entrepreneur = None
        g.user_service = None
        g.entrepreneur_service = None


@entrepreneur_profile.route('/')
@entrepreneur_profile.route('/view')
@login_required
@require_role('entrepreneur')
def view():
    """
    Vista principal del perfil del emprendedor.
    Muestra toda la información del perfil en modo solo lectura.
    """
    try:
        entrepreneur = g.entrepreneur
        if not entrepreneur:
            flash('Perfil de emprendedor no encontrado', 'error')
            return redirect(url_for('main.index'))

        # Obtener información adicional
        recent_activity = ActivityLog.query.filter_by(
            user_id=current_user.id
        ).order_by(desc(ActivityLog.created_at)).limit(10).all()

        # Estadísticas del perfil
        profile_stats = _get_profile_statistics(entrepreneur.id)
        
        # Configuraciones de privacidad
        privacy_settings = _get_privacy_settings(current_user.id)
        
        # Verificar completitud del perfil
        profile_completion = _calculate_profile_completion(entrepreneur)

        return render_template(
            'entrepreneur/profile/view.html',
            entrepreneur=entrepreneur,
            user=current_user,
            recent_activity=recent_activity,
            profile_stats=profile_stats,
            privacy_settings=privacy_settings,
            profile_completion=profile_completion
        )

    except Exception as e:
        current_app.logger.error(f"Error mostrando perfil: {str(e)}")
        flash('Error cargando el perfil', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_profile.route('/edit')
@login_required
@require_role('entrepreneur')
def edit():
    """
    Vista para editar el perfil del emprendedor.
    """
    try:
        entrepreneur = g.entrepreneur
        if not entrepreneur:
            flash('Perfil de emprendedor no encontrado', 'error')
            return redirect(url_for('main.index'))

        # Crear formularios
        profile_form = ProfileForm(obj=current_user)
        business_form = BusinessInfoForm(obj=entrepreneur)
        contact_form = ContactInfoForm(obj=entrepreneur)
        social_form = SocialLinksForm(obj=entrepreneur)

        # Pre-poblar formularios con datos existentes
        if request.method == 'GET':
            _populate_forms(profile_form, business_form, contact_form, social_form, entrepreneur)

        return render_template(
            'entrepreneur/profile/edit.html',
            profile_form=profile_form,
            business_form=business_form,
            contact_form=contact_form,
            social_form=social_form,
            entrepreneur=entrepreneur,
            user=current_user
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando formulario de edición: {str(e)}")
        flash('Error cargando el formulario', 'error')
        return redirect(url_for('entrepreneur_profile.view'))


@entrepreneur_profile.route('/update', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 requests en 5 minutos
def update():
    """
    Actualizar información del perfil del emprendedor.
    """
    try:
        entrepreneur = g.entrepreneur
        if not entrepreneur:
            flash('Perfil de emprendedor no encontrado', 'error')
            return redirect(url_for('main.index'))

        # Obtener tipo de actualización
        update_type = request.form.get('update_type', 'basic')
        
        if update_type == 'basic':
            return _update_basic_info()
        elif update_type == 'business':
            return _update_business_info()
        elif update_type == 'contact':
            return _update_contact_info()
        elif update_type == 'social':
            return _update_social_links()
        else:
            flash('Tipo de actualización no válido', 'error')
            return redirect(url_for('entrepreneur_profile.edit'))

    except ValidationError as e:
        flash(str(e), 'error')
        return redirect(url_for('entrepreneur_profile.edit'))
    except Exception as e:
        current_app.logger.error(f"Error actualizando perfil: {str(e)}")
        flash('Error actualizando el perfil', 'error')
        return redirect(url_for('entrepreneur_profile.edit'))


@entrepreneur_profile.route('/picture', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def profile_picture():
    """
    Gestión de foto de perfil del emprendedor.
    """
    if request.method == 'GET':
        form = ProfilePictureForm()
        return render_template(
            'entrepreneur/profile/picture.html',
            form=form,
            entrepreneur=g.entrepreneur
        )
    
    try:
        form = ProfilePictureForm()
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400

        file = form.picture.data
        if not file or file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No se seleccionó ningún archivo'
            }), 400

        # Validar archivo
        if not allowed_file(file.filename, ALLOWED_EXTENSIONS):
            return jsonify({
                'success': False,
                'error': 'Tipo de archivo no permitido'
            }), 400

        # Validar tamaño
        if len(file.read()) > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': 'El archivo es muy grande (máximo 5MB)'
            }), 400
        
        file.seek(0)  # Resetear puntero del archivo

        # Procesar y guardar imagen
        result = _process_profile_picture(file, g.entrepreneur.id)
        
        if result['success']:
            # Actualizar URL en base de datos
            g.entrepreneur.profile_picture_url = result['url']
            g.entrepreneur.updated_at = datetime.utcnow()
            g.entrepreneur.save()

            # Registrar actividad
            ActivityLog.create(
                user_id=current_user.id,
                action='profile_picture_updated',
                resource_type='entrepreneur',
                resource_id=g.entrepreneur.id,
                details={'new_picture_url': result['url']}
            )

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': 'Foto de perfil actualizada correctamente',
                    'picture_url': result['url'],
                    'thumbnail_url': result['thumbnail_url']
                })
            else:
                flash('Foto de perfil actualizada correctamente', 'success')
                return redirect(url_for('entrepreneur_profile.view'))
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500

    except Exception as e:
        current_app.logger.error(f"Error actualizando foto de perfil: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error procesando la imagen'
        }), 500


@entrepreneur_profile.route('/password', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
@require_fresh_login(max_age=1800)  # Requiere login reciente (30 min)
def change_password():
    """
    Cambiar contraseña del emprendedor.
    """
    form = PasswordChangeForm()
    
    if request.method == 'GET':
        return render_template(
            'entrepreneur/profile/password.html',
            form=form
        )
    
    try:
        if not form.validate_on_submit():
            if request.is_json:
                return jsonify({
                    'success': False,
                    'errors': form.errors
                }), 400
            else:
                return render_template('entrepreneur/profile/password.html', form=form)

        # Verificar contraseña actual
        if not check_password_hash(current_user.password_hash, form.current_password.data):
            error_msg = 'Contraseña actual incorrecta'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            else:
                flash(error_msg, 'error')
                return render_template('entrepreneur/profile/password.html', form=form)

        # Validar fortaleza de nueva contraseña
        password_validation = validate_password_strength(form.new_password.data)
        if not password_validation['valid']:
            error_msg = 'La nueva contraseña no cumple los requisitos de seguridad'
            if request.is_json:
                return jsonify({
                    'success': False, 
                    'error': error_msg,
                    'details': password_validation['errors']
                }), 400
            else:
                flash(error_msg, 'error')
                return render_template('entrepreneur/profile/password.html', form=form)

        # Actualizar contraseña
        current_user.password_hash = generate_password_hash(form.new_password.data)
        current_user.password_changed_at = datetime.utcnow()
        current_user.updated_at = datetime.utcnow()
        current_user.save()

        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='password_changed',
            resource_type='user',
            resource_id=current_user.id,
            details={'ip_address': request.remote_addr}
        )

        # Enviar notificación por email
        EmailService.send_password_change_notification(current_user.email, current_user.first_name)

        success_msg = 'Contraseña actualizada correctamente'
        if request.is_json:
            return jsonify({'success': True, 'message': success_msg})
        else:
            flash(success_msg, 'success')
            return redirect(url_for('entrepreneur_profile.view'))

    except Exception as e:
        current_app.logger.error(f"Error cambiando contraseña: {str(e)}")
        error_msg = 'Error actualizando la contraseña'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            return render_template('entrepreneur/profile/password.html', form=form)


@entrepreneur_profile.route('/preferences', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def preferences():
    """
    Configuración de preferencias del emprendedor.
    """
    form = PreferencesForm()
    
    if request.method == 'GET':
        # Cargar preferencias actuales
        _load_current_preferences(form)
        return render_template(
            'entrepreneur/profile/preferences.html',
            form=form,
            entrepreneur=g.entrepreneur
        )
    
    try:
        if not form.validate_on_submit():
            return render_template('entrepreneur/profile/preferences.html', form=form)

        # Actualizar preferencias
        _update_notification_preferences(form)
        _update_privacy_preferences(form)
        _update_communication_preferences(form)

        # Actualizar entrepreneur
        g.entrepreneur.timezone = form.timezone.data
        g.entrepreneur.language = form.language.data
        g.entrepreneur.currency = form.currency.data
        g.entrepreneur.updated_at = datetime.utcnow()
        g.entrepreneur.save()

        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='preferences_updated',
            resource_type='entrepreneur',
            resource_id=g.entrepreneur.id
        )

        flash('Preferencias actualizadas correctamente', 'success')
        return redirect(url_for('entrepreneur_profile.preferences'))

    except Exception as e:
        current_app.logger.error(f"Error actualizando preferencias: {str(e)}")
        flash('Error actualizando las preferencias', 'error')
        return render_template('entrepreneur/profile/preferences.html', form=form)


@entrepreneur_profile.route('/privacy', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def privacy_settings():
    """
    Configuración de privacidad del emprendedor.
    """
    form = PrivacySettingsForm()
    
    if request.method == 'GET':
        _load_privacy_settings(form)
        return render_template(
            'entrepreneur/profile/privacy.html',
            form=form,
            entrepreneur=g.entrepreneur
        )
    
    try:
        if not form.validate_on_submit():
            return render_template('entrepreneur/profile/privacy.html', form=form)

        # Actualizar configuraciones de privacidad
        _update_privacy_settings(form)

        flash('Configuración de privacidad actualizada', 'success')
        return redirect(url_for('entrepreneur_profile.privacy_settings'))

    except Exception as e:
        current_app.logger.error(f"Error actualizando privacidad: {str(e)}")
        flash('Error actualizando la configuración', 'error')
        return render_template('entrepreneur/profile/privacy.html', form=form)


@entrepreneur_profile.route('/two-factor', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
@require_fresh_login(max_age=900)  # Requiere login reciente (15 min)
def two_factor_auth():
    """
    Configuración de autenticación de dos factores.
    """
    form = TwoFactorForm()
    
    if request.method == 'GET':
        # Generar QR code si no está habilitado 2FA
        qr_code_data = None
        if not current_user.two_factor_enabled:
            secret = pyotp.random_base32()
            current_user.two_factor_secret = secret
            current_user.save()
            
            # Generar QR code
            qr_code_data = _generate_qr_code(secret)
        
        return render_template(
            'entrepreneur/profile/two_factor.html',
            form=form,
            qr_code_data=qr_code_data,
            two_factor_enabled=current_user.two_factor_enabled
        )
    
    try:
        if not form.validate_on_submit():
            return render_template('entrepreneur/profile/two_factor.html', form=form)

        action = form.action.data
        
        if action == 'enable':
            return _enable_two_factor(form)
        elif action == 'disable':
            return _disable_two_factor(form)
        else:
            flash('Acción no válida', 'error')
            return redirect(url_for('entrepreneur_profile.two_factor_auth'))

    except Exception as e:
        current_app.logger.error(f"Error configurando 2FA: {str(e)}")
        flash('Error en la configuración de 2FA', 'error')
        return redirect(url_for('entrepreneur_profile.two_factor_auth'))


@entrepreneur_profile.route('/delete-account', methods=['POST'])
@login_required
@require_role('entrepreneur')
@require_fresh_login(max_age=300)  # Requiere login muy reciente (5 min)
def delete_account():
    """
    Eliminar cuenta del emprendedor (soft delete).
    """
    try:
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')
        
        if not password or confirmation != 'ELIMINAR':
            return jsonify({
                'success': False,
                'error': 'Confirmación incorrecta'
            }), 400

        # Verificar contraseña
        if not check_password_hash(current_user.password_hash, password):
            return jsonify({
                'success': False,
                'error': 'Contraseña incorrecta'
            }), 400

        # Soft delete
        current_user.is_active = False
        current_user.deleted_at = datetime.utcnow()
        current_user.deletion_reason = 'user_requested'
        current_user.save()

        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='account_deleted',
            resource_type='user',
            resource_id=current_user.id,
            details={'deletion_reason': 'user_requested'}
        )

        # Enviar confirmación por email
        EmailService.send_account_deletion_confirmation(
            current_user.email, 
            current_user.first_name
        )

        return jsonify({
            'success': True,
            'message': 'Cuenta eliminada correctamente',
            'redirect_url': url_for('auth.logout')
        })

    except Exception as e:
        current_app.logger.error(f"Error eliminando cuenta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error procesando la solicitud'
        }), 500


@entrepreneur_profile.route('/export-data')
@login_required
@require_role('entrepreneur')
@rate_limit(requests=3, window=3600)  # 3 requests por hora
def export_data():
    """
    Exportar todos los datos del emprendedor (GDPR compliance).
    """
    try:
        # Generar archivo de exportación
        export_service = g.entrepreneur_service
        export_data = export_service.export_all_data()
        
        # Crear archivo temporal
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(export_data, f, indent=2, default=str)
            temp_file_path = f.name

        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='data_exported',
            resource_type='user',
            resource_id=current_user.id
        )

        return jsonify({
            'success': True,
            'message': 'Datos exportados correctamente',
            'download_url': url_for('entrepreneur_profile.download_export', 
                                  filename=os.path.basename(temp_file_path))
        })

    except Exception as e:
        current_app.logger.error(f"Error exportando datos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error exportando los datos'
        }), 500


# === FUNCIONES AUXILIARES ===

def _populate_forms(profile_form, business_form, contact_form, social_form, entrepreneur):
    """Poblar formularios con datos existentes."""
    # Información personal
    profile_form.first_name.data = current_user.first_name
    profile_form.last_name.data = current_user.last_name
    profile_form.email.data = current_user.email
    
    # Información de negocio
    business_form.company_name.data = entrepreneur.company_name
    business_form.industry.data = entrepreneur.industry
    business_form.business_stage.data = entrepreneur.business_stage
    business_form.description.data = entrepreneur.description
    business_form.website.data = entrepreneur.website
    
    # Información de contacto
    contact_form.phone.data = entrepreneur.phone
    contact_form.address.data = entrepreneur.address
    contact_form.city.data = entrepreneur.city
    contact_form.country.data = entrepreneur.country
    
    # Redes sociales
    social_form.linkedin_url.data = entrepreneur.linkedin_url
    social_form.twitter_handle.data = entrepreneur.twitter_handle
    social_form.facebook_url.data = entrepreneur.facebook_url
    social_form.instagram_handle.data = entrepreneur.instagram_handle


def _update_basic_info():
    """Actualizar información básica del perfil."""
    form = ProfileForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 400

    # Actualizar usuario
    current_user.first_name = sanitize_input(form.first_name.data)
    current_user.last_name = sanitize_input(form.last_name.data)
    
    # Verificar si el email cambió
    if current_user.email != form.email.data:
        # Validar que el nuevo email no exista
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user and existing_user.id != current_user.id:
            return jsonify({
                'success': False, 
                'error': 'El email ya está en uso'
            }), 400
        
        current_user.email = form.email.data
        current_user.email_verified = False  # Requerir verificación
        
        # Enviar email de verificación
        EmailService.send_email_verification(current_user)

    current_user.updated_at = datetime.utcnow()
    current_user.save()

    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='basic_info_updated',
        resource_type='user',
        resource_id=current_user.id
    )

    flash('Información básica actualizada correctamente', 'success')
    return redirect(url_for('entrepreneur_profile.view'))


def _update_business_info():
    """Actualizar información de negocio."""
    form = BusinessInfoForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 400

    entrepreneur = g.entrepreneur
    
    # Actualizar información de negocio
    entrepreneur.company_name = sanitize_input(form.company_name.data)
    entrepreneur.industry = form.industry.data
    entrepreneur.business_stage = form.business_stage.data
    entrepreneur.description = sanitize_input(form.description.data)
    
    # Validar URL del website
    if form.website.data:
        if not validate_url(form.website.data):
            return jsonify({
                'success': False,
                'error': 'URL del website no válida'
            }), 400
        entrepreneur.website = form.website.data

    entrepreneur.updated_at = datetime.utcnow()
    entrepreneur.save()

    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='business_info_updated',
        resource_type='entrepreneur',
        resource_id=entrepreneur.id
    )

    flash('Información de negocio actualizada correctamente', 'success')
    return redirect(url_for('entrepreneur_profile.view'))


def _update_contact_info():
    """Actualizar información de contacto."""
    form = ContactInfoForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 400

    entrepreneur = g.entrepreneur
    
    # Validar teléfono
    if form.phone.data:
        if not validate_phone_number(form.phone.data):
            return jsonify({
                'success': False,
                'error': 'Número de teléfono no válido'
            }), 400
        entrepreneur.phone = format_phone_number(form.phone.data)

    entrepreneur.address = sanitize_input(form.address.data)
    entrepreneur.city = sanitize_input(form.city.data)
    entrepreneur.country = form.country.data
    entrepreneur.updated_at = datetime.utcnow()
    entrepreneur.save()

    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='contact_info_updated',
        resource_type='entrepreneur',
        resource_id=entrepreneur.id
    )

    flash('Información de contacto actualizada correctamente', 'success')
    return redirect(url_for('entrepreneur_profile.view'))


def _update_social_links():
    """Actualizar enlaces de redes sociales."""
    form = SocialLinksForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 400

    entrepreneur = g.entrepreneur
    
    # Validar URLs de redes sociales
    if form.linkedin_url.data and not validate_url(form.linkedin_url.data):
        return jsonify({'success': False, 'error': 'URL de LinkedIn no válida'}), 400
    
    if form.facebook_url.data and not validate_url(form.facebook_url.data):
        return jsonify({'success': False, 'error': 'URL de Facebook no válida'}), 400
    
    # Validar handles de redes sociales
    if form.twitter_handle.data and not validate_social_handle(form.twitter_handle.data):
        return jsonify({'success': False, 'error': 'Handle de Twitter no válido'}), 400
    
    if form.instagram_handle.data and not validate_social_handle(form.instagram_handle.data):
        return jsonify({'success': False, 'error': 'Handle de Instagram no válido'}), 400

    entrepreneur.linkedin_url = form.linkedin_url.data
    entrepreneur.twitter_handle = form.twitter_handle.data
    entrepreneur.facebook_url = form.facebook_url.data
    entrepreneur.instagram_handle = form.instagram_handle.data
    entrepreneur.updated_at = datetime.utcnow()
    entrepreneur.save()

    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='social_links_updated',
        resource_type='entrepreneur',
        resource_id=entrepreneur.id
    )

    flash('Enlaces de redes sociales actualizados correctamente', 'success')
    return redirect(url_for('entrepreneur_profile.view'))


def _process_profile_picture(file, entrepreneur_id):
    """Procesar y guardar imagen de perfil."""
    try:
        # Generar nombre único
        filename = generate_unique_filename(
            secure_filename(file.filename), 
            f"profile_{entrepreneur_id}"
        )
        
        # Abrir imagen con PIL
        image = Image.open(file)
        
        # Convertir a RGB si es necesario
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Redimensionar imagen principal
        image_resized = image.resize(PROFILE_PICTURE_SIZE, Image.Resampling.LANCZOS)
        
        # Crear thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        
        # Guardar archivos
        storage_service = FileStorageService()
        
        # Guardar imagen principal
        main_image_path = storage_service.save_image(
            image_resized, 
            f"profiles/{filename}"
        )
        
        # Guardar thumbnail
        thumb_filename = f"thumb_{filename}"
        thumbnail_path = storage_service.save_image(
            thumbnail, 
            f"profiles/thumbnails/{thumb_filename}"
        )
        
        return {
            'success': True,
            'url': main_image_path,
            'thumbnail_url': thumbnail_path
        }
        
    except Exception as e:
        current_app.logger.error(f"Error procesando imagen: {str(e)}")
        return {
            'success': False,
            'error': 'Error procesando la imagen'
        }


def _generate_qr_code(secret):
    """Generar código QR para 2FA."""
    try:
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=current_user.email,
            issuer_name="Ecosistema Emprendimiento"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
        
    except Exception as e:
        current_app.logger.error(f"Error generando QR: {str(e)}")
        return None


def _enable_two_factor(form):
    """Habilitar autenticación de dos factores."""
    # Verificar código TOTP
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if not totp.verify(form.verification_code.data):
        flash('Código de verificación incorrecto', 'error')
        return redirect(url_for('entrepreneur_profile.two_factor_auth'))
    
    # Habilitar 2FA
    current_user.two_factor_enabled = True
    current_user.two_factor_enabled_at = datetime.utcnow()
    current_user.save()
    
    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='two_factor_enabled',
        resource_type='user',
        resource_id=current_user.id
    )
    
    flash('Autenticación de dos factores habilitada correctamente', 'success')
    return redirect(url_for('entrepreneur_profile.two_factor_auth'))


def _disable_two_factor(form):
    """Deshabilitar autenticación de dos factores."""
    # Verificar código TOTP
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if not totp.verify(form.verification_code.data):
        flash('Código de verificación incorrecto', 'error')
        return redirect(url_for('entrepreneur_profile.two_factor_auth'))
    
    # Deshabilitar 2FA
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.save()
    
    # Registrar actividad
    ActivityLog.create(
        user_id=current_user.id,
        action='two_factor_disabled',
        resource_type='user',
        resource_id=current_user.id
    )
    
    flash('Autenticación de dos factores deshabilitada', 'success')
    return redirect(url_for('entrepreneur_profile.two_factor_auth'))


def _get_profile_statistics(entrepreneur_id):
    """Obtener estadísticas del perfil."""
    from app.models.project import Project
    from app.models.meeting import Meeting
    from app.models.task import Task
    
    stats = {
        'total_projects': Project.query.filter_by(entrepreneur_id=entrepreneur_id).count(),
        'total_meetings': Meeting.query.filter_by(entrepreneur_id=entrepreneur_id).count(),
        'completed_tasks': Task.query.filter_by(
            entrepreneur_id=entrepreneur_id, 
            status='completed'
        ).count(),
        'profile_views': 0,  # Implementar si es necesario
        'last_login': current_user.last_login_at
    }
    
    return stats


def _get_privacy_settings(user_id):
    """Obtener configuraciones de privacidad."""
    # Implementar según tu modelo de configuraciones
    return {
        'profile_visible': True,
        'email_visible': False,
        'phone_visible': False,
        'show_in_directory': True
    }


def _calculate_profile_completion(entrepreneur):
    """Calcular porcentaje de completitud del perfil."""
    fields_to_check = [
        entrepreneur.company_name,
        entrepreneur.industry,
        entrepreneur.description,
        entrepreneur.phone,
        entrepreneur.city,
        entrepreneur.country,
        entrepreneur.profile_picture_url
    ]
    
    completed_fields = sum(1 for field in fields_to_check if field)
    completion_percentage = (completed_fields / len(fields_to_check)) * 100
    
    return {
        'percentage': round(completion_percentage, 1),
        'completed_fields': completed_fields,
        'total_fields': len(fields_to_check)
    }


def _load_current_preferences(form):
    """Cargar preferencias actuales en el formulario."""
    entrepreneur = g.entrepreneur
    form.timezone.data = entrepreneur.timezone or 'UTC'
    form.language.data = entrepreneur.language or 'es'
    form.currency.data = entrepreneur.currency or 'USD'
    
    # Cargar preferencias de notificaciones
    # Implementar según tu modelo de preferencias


def _update_notification_preferences(form):
    """Actualizar preferencias de notificaciones."""
    # Implementar según tu modelo NotificationPreference
    pass


def _update_privacy_preferences(form):
    """Actualizar preferencias de privacidad."""
    # Implementar según tu modelo de configuraciones
    pass


def _update_communication_preferences(form):
    """Actualizar preferencias de comunicación."""
    # Implementar según tu modelo de configuraciones
    pass


def _load_privacy_settings(form):
    """Cargar configuraciones de privacidad."""
    # Implementar según tu modelo
    pass


def _update_privacy_settings(form):
    """Actualizar configuraciones de privacidad."""
    # Implementar según tu modelo
    pass


# === MANEJADORES DE ERRORES ===

@entrepreneur_profile.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_profile.view'))


@entrepreneur_profile.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_profile.view'))


@entrepreneur_profile.errorhandler(FileError)
def handle_file_error(error):
    """Manejar errores de archivos."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_profile.view'))