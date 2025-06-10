"""
Módulo de gestión de perfil para Aliados/Mentores.

Este módulo contiene todas las funcionalidades relacionadas con la gestión
del perfil de aliados, incluyendo información personal, profesional, 
especialidades, certificaciones, configuraciones y sistema de verificación.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

import os
import uuid
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
import json

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, g, abort, make_response, 
    send_from_directory
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import joinedload
from PIL import Image

from app.core.exceptions import ValidationError, BusinessLogicError, FileUploadError
from app.models import (
    db, User, Ally, Entrepreneur, MentorshipSession, 
    Document, Notification, ActivityLog, Organization,
    Specialization, Certification, AvailabilitySlot
)
from app.forms.ally import (
    AllyProfileForm, AllyPersonalInfoForm, AllyProfessionalInfoForm,
    AllySpecializationsForm, AllyAvailabilityForm, AllyPreferencesForm,
    AllyPrivacySettingsForm, CertificationForm, DocumentUploadForm,
    AllyVerificationForm, AllyContactInfoForm
)
from app.services.file_storage import FileStorageService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.utils.decorators import require_json, rate_limit, validate_file_upload
from app.utils.validators import validate_phone, validate_url, validate_file_type
from app.utils.formatters import format_currency, format_date, format_file_size
from app.utils.file_utils import (
    generate_unique_filename, resize_image, validate_image_file,
    compress_image, get_file_extension
)
from app.utils.crypto_utils import generate_verification_token, hash_sensitive_data
from app.views.ally import require_ally_access, track_ally_activity


# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================

ally_profile_bp = Blueprint(
    'ally_profile',
    __name__,
    url_prefix='/ally/profile',
    template_folder='templates/ally/profile'
)

# Configuración de archivos permitidos
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
PROFILE_IMAGE_SIZES = [(150, 150), (300, 300), (600, 600)]  # Diferentes tamaños


# ==================== VISTAS PRINCIPALES DEL PERFIL ====================

@ally_profile_bp.route('/')
@ally_profile_bp.route('/view')
@login_required
@require_ally_access
@track_ally_activity('profile_view', 'Visualización del perfil')
def view():
    """
    Vista principal del perfil del aliado.
    
    Muestra toda la información del perfil de manera organizada,
    incluyendo información personal, profesional, especialidades,
    certificaciones y estadísticas de actividad.
    
    Returns:
        Template renderizado con información del perfil
    """
    try:
        ally_profile = g.ally_profile
        
        # Cargar información completa del perfil
        profile_data = _get_complete_profile_data(ally_profile)
        
        # Estadísticas del perfil
        profile_stats = _calculate_profile_stats(ally_profile)
        
        # Certificaciones activas
        active_certifications = _get_active_certifications(ally_profile)
        
        # Especialidades organizadas
        specializations_data = _organize_specializations(ally_profile)
        
        # Disponibilidad semanal
        availability_summary = _get_availability_summary(ally_profile)
        
        # Histórico de verificaciones
        verification_history = _get_verification_history(ally_profile)
        
        # Documentos del perfil
        profile_documents = _get_profile_documents(ally_profile)
        
        # Score de completitud del perfil
        completeness_score = _calculate_profile_completeness(ally_profile)
        
        # Actividad reciente relacionada con el perfil
        recent_profile_activity = _get_recent_profile_activity(ally_profile)
        
        # Configuraciones de privacidad
        privacy_settings = _get_privacy_settings(ally_profile)
        
        return render_template(
            'ally/profile/view.html',
            profile_data=profile_data,
            profile_stats=profile_stats,
            active_certifications=active_certifications,
            specializations_data=specializations_data,
            availability_summary=availability_summary,
            verification_history=verification_history,
            profile_documents=profile_documents,
            completeness_score=completeness_score,
            recent_profile_activity=recent_profile_activity,
            privacy_settings=privacy_settings,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de perfil del aliado {ally_profile.id}: {str(e)}")
        flash('Error al cargar el perfil. Por favor, intenta nuevamente.', 'error')
        return redirect(url_for('ally_dashboard.index'))


@ally_profile_bp.route('/edit')
@login_required
@require_ally_access
@track_ally_activity('profile_edit', 'Acceso a edición del perfil')
def edit():
    """
    Vista de edición del perfil del aliado.
    
    Proporciona formularios organizados por secciones para editar
    toda la información del perfil del aliado.
    
    Returns:
        Template con formularios de edición
    """
    try:
        ally_profile = g.ally_profile
        
        # Inicializar formularios
        personal_form = AllyPersonalInfoForm(obj=ally_profile.user)
        professional_form = AllyProfessionalInfoForm(obj=ally_profile)
        contact_form = AllyContactInfoForm(obj=ally_profile)
        specializations_form = AllySpecializationsForm(obj=ally_profile)
        
        # Poblar campos específicos
        _populate_edit_forms(ally_profile, personal_form, professional_form, 
                           contact_form, specializations_form)
        
        # Opciones para selectores
        form_options = _get_form_options()
        
        # Datos actuales para comparación
        current_data = _get_current_profile_data(ally_profile)
        
        return render_template(
            'ally/profile/edit.html',
            personal_form=personal_form,
            professional_form=professional_form,
            contact_form=contact_form,
            specializations_form=specializations_form,
            form_options=form_options,
            current_data=current_data,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando formularios de edición: {str(e)}")
        flash('Error al cargar los formularios de edición', 'error')
        return redirect(url_for('ally_profile.view'))


@ally_profile_bp.route('/update', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('profile_update', 'Actualización del perfil')
def update():
    """
    Procesa la actualización del perfil del aliado.
    
    Maneja la actualización de diferentes secciones del perfil
    con validación robusta y logging de cambios.
    
    Returns:
        Redirección al perfil actualizado o formulario con errores
    """
    try:
        ally_profile = g.ally_profile
        section = request.form.get('section', 'personal')
        
        # Validar sección
        valid_sections = ['personal', 'professional', 'contact', 'specializations']
        if section not in valid_sections:
            flash('Sección de perfil no válida', 'error')
            return redirect(url_for('ally_profile.edit'))
        
        # Procesar actualización según la sección
        update_result = _process_profile_update(ally_profile, section)
        
        if update_result['success']:
            # Registrar cambios
            _log_profile_changes(ally_profile, section, update_result['changes'])
            
            # Notificar si es necesario
            if update_result.get('notify_admin', False):
                _notify_admin_profile_changes(ally_profile, update_result['changes'])
            
            # Recalcular completitud del perfil
            _update_profile_completeness(ally_profile)
            
            flash(f'Información {section} actualizada exitosamente', 'success')
            return redirect(url_for('ally_profile.view'))
        else:
            flash(f'Error actualizando información: {update_result["error"]}', 'error')
            return redirect(url_for('ally_profile.edit'))
            
    except ValidationError as e:
        flash(f'Error de validación: {str(e)}', 'error')
        return redirect(url_for('ally_profile.edit'))
    except Exception as e:
        current_app.logger.error(f"Error actualizando perfil: {str(e)}")
        flash('Error interno al actualizar el perfil', 'error')
        return redirect(url_for('ally_profile.edit'))


@ally_profile_bp.route('/settings')
@login_required
@require_ally_access
@track_ally_activity('profile_settings', 'Acceso a configuraciones del perfil')
def settings():
    """
    Vista de configuraciones del perfil.
    
    Permite al aliado configurar preferencias, privacidad,
    notificaciones y otras configuraciones personales.
    
    Returns:
        Template con configuraciones del perfil
    """
    try:
        ally_profile = g.ally_profile
        
        # Formularios de configuración
        preferences_form = AllyPreferencesForm(obj=ally_profile)
        privacy_form = AllyPrivacySettingsForm(obj=ally_profile)
        
        # Configuraciones actuales
        current_settings = _get_current_settings(ally_profile)
        
        # Opciones de configuración
        settings_options = _get_settings_options()
        
        return render_template(
            'ally/profile/settings.html',
            preferences_form=preferences_form,
            privacy_form=privacy_form,
            current_settings=current_settings,
            settings_options=settings_options,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando configuraciones: {str(e)}")
        flash('Error al cargar las configuraciones', 'error')
        return redirect(url_for('ally_profile.view'))


@ally_profile_bp.route('/availability')
@login_required
@require_ally_access
@track_ally_activity('availability_management', 'Gestión de disponibilidad')
def availability():
    """
    Vista de gestión de disponibilidad del aliado.
    
    Permite configurar horarios disponibles para sesiones de mentoría,
    reuniones y otras actividades.
    
    Returns:
        Template con gestión de disponibilidad
    """
    try:
        ally_profile = g.ally_profile
        
        # Formulario de disponibilidad
        availability_form = AllyAvailabilityForm()
        
        # Disponibilidad actual organizada por día
        current_availability = _get_organized_availability(ally_profile)
        
        # Próximas citas programadas
        upcoming_appointments = _get_upcoming_appointments(ally_profile)
        
        # Estadísticas de disponibilidad
        availability_stats = _calculate_availability_stats(ally_profile)
        
        # Conflictos de horario
        schedule_conflicts = _detect_availability_conflicts(ally_profile)
        
        return render_template(
            'ally/profile/availability.html',
            availability_form=availability_form,
            current_availability=current_availability,
            upcoming_appointments=upcoming_appointments,
            availability_stats=availability_stats,
            schedule_conflicts=schedule_conflicts,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en gestión de disponibilidad: {str(e)}")
        flash('Error al cargar la gestión de disponibilidad', 'error')
        return redirect(url_for('ally_profile.view'))


@ally_profile_bp.route('/certifications')
@login_required
@require_ally_access
@track_ally_activity('certifications_view', 'Vista de certificaciones')
def certifications():
    """
    Vista de gestión de certificaciones del aliado.
    
    Permite ver, agregar, editar y eliminar certificaciones
    profesionales del aliado.
    
    Returns:
        Template con gestión de certificaciones
    """
    try:
        ally_profile = g.ally_profile
        
        # Formulario para nueva certificación
        certification_form = CertificationForm()
        
        # Certificaciones organizadas por estado
        certifications_data = _organize_certifications(ally_profile)
        
        # Estadísticas de certificaciones
        cert_stats = _calculate_certification_stats(ally_profile)
        
        # Próximas renovaciones
        upcoming_renewals = _get_upcoming_renewals(ally_profile)
        
        return render_template(
            'ally/profile/certifications.html',
            certification_form=certification_form,
            certifications_data=certifications_data,
            cert_stats=cert_stats,
            upcoming_renewals=upcoming_renewals,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en gestión de certificaciones: {str(e)}")
        flash('Error al cargar las certificaciones', 'error')
        return redirect(url_for('ally_profile.view'))


@ally_profile_bp.route('/verification')
@login_required
@require_ally_access
@track_ally_activity('verification_view', 'Vista de verificación de perfil')
def verification():
    """
    Vista del proceso de verificación del perfil.
    
    Muestra el estado actual de verificación y permite
    enviar documentación adicional si es necesaria.
    
    Returns:
        Template con proceso de verificación
    """
    try:
        ally_profile = g.ally_profile
        
        # Estado actual de verificación
        verification_status = _get_detailed_verification_status(ally_profile)
        
        # Documentos requeridos y opcionales
        required_documents = _get_required_verification_documents(ally_profile)
        
        # Historial de verificación
        verification_timeline = _get_verification_timeline(ally_profile)
        
        # Próximos pasos en el proceso
        next_steps = _get_verification_next_steps(ally_profile)
        
        # Formulario para subir documentos
        document_form = DocumentUploadForm()
        
        return render_template(
            'ally/profile/verification.html',
            verification_status=verification_status,
            required_documents=required_documents,
            verification_timeline=verification_timeline,
            next_steps=next_steps,
            document_form=document_form,
            ally_profile=ally_profile
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en vista de verificación: {str(e)}")
        flash('Error al cargar el estado de verificación', 'error')
        return redirect(url_for('ally_profile.view'))


# ==================== GESTIÓN DE ARCHIVOS Y DOCUMENTOS ====================

@ally_profile_bp.route('/upload-profile-image', methods=['POST'])
@login_required
@require_ally_access
@validate_file_upload(max_size=MAX_IMAGE_SIZE, allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
@track_ally_activity('profile_image_upload', 'Carga de imagen de perfil')
def upload_profile_image():
    """
    Maneja la carga de imagen de perfil del aliado.
    
    Procesa, redimensiona y almacena la imagen de perfil
    en múltiples tamaños para diferentes usos.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        
        if 'profile_image' not in request.files:
            return jsonify({'error': 'No se encontró archivo de imagen'}), 400
        
        file = request.files['profile_image']
        
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        # Validar imagen
        if not validate_image_file(file):
            return jsonify({'error': 'Archivo de imagen no válido'}), 400
        
        # Generar nombre único
        filename = generate_unique_filename(file.filename)
        
        # Procesar y guardar imagen
        image_urls = _process_and_save_profile_image(file, filename, ally_profile)
        
        # Actualizar perfil con nueva imagen
        old_image = ally_profile.profile_image_url
        ally_profile.profile_image_url = image_urls['medium']
        ally_profile.profile_image_urls = json.dumps(image_urls)
        ally_profile.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Eliminar imagen anterior si existe
        if old_image:
            _delete_old_profile_images(old_image)
        
        # Registrar cambio
        _log_image_change(ally_profile, old_image, image_urls['medium'])
        
        return jsonify({
            'success': True,
            'message': 'Imagen de perfil actualizada exitosamente',
            'image_urls': image_urls
        })
        
    except Exception as e:
        current_app.logger.error(f"Error subiendo imagen de perfil: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/upload-document', methods=['POST'])
@login_required
@require_ally_access
@validate_file_upload(max_size=MAX_DOCUMENT_SIZE, allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)
@track_ally_activity('document_upload', 'Carga de documento')
def upload_document():
    """
    Maneja la carga de documentos del aliado.
    
    Procesa y almacena documentos como certificaciones,
    identificaciones, y otros documentos de verificación.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        form = DocumentUploadForm()
        
        if not form.validate_on_submit():
            return jsonify({
                'error': 'Datos del formulario no válidos',
                'details': form.errors
            }), 400
        
        file = form.document_file.data
        document_type = form.document_type.data
        description = form.description.data
        
        # Validar tipo de documento
        if not _validate_document_type(document_type, ally_profile):
            return jsonify({'error': 'Tipo de documento no válido para este perfil'}), 400
        
        # Procesar y guardar documento
        document_result = _process_and_save_document(
            file, document_type, description, ally_profile
        )
        
        if document_result['success']:
            return jsonify({
                'success': True,
                'message': 'Documento cargado exitosamente',
                'document': document_result['document_data']
            })
        else:
            return jsonify({
                'error': document_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error subiendo documento: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/delete-document/<int:document_id>', methods=['DELETE'])
@login_required
@require_ally_access
@rate_limit(calls=10, period=60)
@track_ally_activity('document_delete', 'Eliminación de documento')
def delete_document(document_id):
    """
    Elimina un documento del perfil del aliado.
    
    Args:
        document_id: ID del documento a eliminar
        
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar que el documento pertenece al aliado
        document = Document.query.filter_by(
            id=document_id,
            owner_id=ally_profile.user_id,
            owner_type='ally'
        ).first()
        
        if not document:
            return jsonify({'error': 'Documento no encontrado'}), 404
        
        # Verificar si el documento es crítico
        if _is_critical_document(document):
            return jsonify({
                'error': 'No se puede eliminar este documento crítico'
            }), 400
        
        # Eliminar archivo físico
        file_deleted = _delete_document_file(document.file_path)
        
        # Eliminar registro de la base de datos
        db.session.delete(document)
        db.session.commit()
        
        # Registrar eliminación
        _log_document_deletion(ally_profile, document)
        
        return jsonify({
            'success': True,
            'message': 'Documento eliminado exitosamente'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando documento: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== API ENDPOINTS ====================

@ally_profile_bp.route('/api/update-availability', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
@require_json
def api_update_availability():
    """
    API endpoint para actualizar disponibilidad del aliado.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        # Validar datos de disponibilidad
        if not _validate_availability_data(data):
            return jsonify({'error': 'Datos de disponibilidad no válidos'}), 400
        
        # Procesar actualización de disponibilidad
        update_result = _update_ally_availability(ally_profile, data)
        
        if update_result['success']:
            return jsonify({
                'success': True,
                'message': 'Disponibilidad actualizada exitosamente',
                'updated_slots': update_result['updated_slots']
            })
        else:
            return jsonify({
                'error': update_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error actualizando disponibilidad: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/api/add-certification', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=15, period=60)
@require_json
def api_add_certification():
    """
    API endpoint para agregar nueva certificación.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        # Validar datos de certificación
        cert_form = CertificationForm(data=data)
        if not cert_form.validate():
            return jsonify({
                'error': 'Datos de certificación no válidos',
                'details': cert_form.errors
            }), 400
        
        # Crear nueva certificación
        certification_result = _create_certification(ally_profile, data)
        
        if certification_result['success']:
            return jsonify({
                'success': True,
                'message': 'Certificación agregada exitosamente',
                'certification': certification_result['certification_data']
            })
        else:
            return jsonify({
                'error': certification_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error agregando certificación: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/api/update-specializations', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=10, period=60)
@require_json
def api_update_specializations():
    """
    API endpoint para actualizar especializaciones del aliado.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        specialization_ids = data.get('specialization_ids', [])
        custom_specializations = data.get('custom_specializations', [])
        
        # Validar especializaciones
        if not _validate_specializations(specialization_ids, custom_specializations):
            return jsonify({'error': 'Especializaciones no válidas'}), 400
        
        # Actualizar especializaciones
        update_result = _update_ally_specializations(
            ally_profile, specialization_ids, custom_specializations
        )
        
        if update_result['success']:
            return jsonify({
                'success': True,
                'message': 'Especializaciones actualizadas exitosamente'
            })
        else:
            return jsonify({
                'error': update_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error actualizando especializaciones: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/api/update-preferences', methods=['POST'])
@login_required
@require_ally_access
@rate_limit(calls=10, period=60)
@require_json
def api_update_preferences():
    """
    API endpoint para actualizar preferencias del aliado.
    
    Returns:
        JSON con resultado de la operación
    """
    try:
        ally_profile = g.ally_profile
        data = request.get_json()
        
        # Validar preferencias
        if not _validate_preferences_data(data):
            return jsonify({'error': 'Datos de preferencias no válidos'}), 400
        
        # Actualizar preferencias
        update_result = _update_ally_preferences(ally_profile, data)
        
        if update_result['success']:
            return jsonify({
                'success': True,
                'message': 'Preferencias actualizadas exitosamente'
            })
        else:
            return jsonify({
                'error': update_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error actualizando preferencias: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/api/profile-completeness')
@login_required
@require_ally_access
@rate_limit(calls=30, period=60)
@require_json
def api_profile_completeness():
    """
    API endpoint para obtener score de completitud del perfil.
    
    Returns:
        JSON con score de completitud detallado
    """
    try:
        ally_profile = g.ally_profile
        
        # Calcular completitud detallada
        completeness_data = _calculate_detailed_completeness(ally_profile)
        
        return jsonify({
            'success': True,
            'data': completeness_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error calculando completitud: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@ally_profile_bp.route('/api/verification-status')
@login_required
@require_ally_access
@rate_limit(calls=20, period=60)
@require_json
def api_verification_status():
    """
    API endpoint para obtener estado de verificación actual.
    
    Returns:
        JSON con estado de verificación
    """
    try:
        ally_profile = g.ally_profile
        
        # Obtener estado detallado de verificación
        verification_data = _get_api_verification_status(ally_profile)
        
        return jsonify({
            'success': True,
            'data': verification_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estado de verificación: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== VERIFICACIÓN DEL PERFIL ====================

@ally_profile_bp.route('/submit-verification', methods=['POST'])
@login_required
@require_ally_access
@track_ally_activity('verification_submit', 'Envío de verificación de perfil')
def submit_verification():
    """
    Envía el perfil para verificación administrativa.
    
    Returns:
        Redirección con mensaje de confirmación
    """
    try:
        ally_profile = g.ally_profile
        
        # Verificar que el perfil esté completo
        completeness = _calculate_profile_completeness(ally_profile)
        if completeness['overall_score'] < 80:
            flash('El perfil debe estar al menos 80% completo para enviar a verificación', 'warning')
            return redirect(url_for('ally_profile.view'))
        
        # Verificar documentos requeridos
        missing_documents = _check_required_documents(ally_profile)
        if missing_documents:
            flash(f'Faltan documentos requeridos: {", ".join(missing_documents)}', 'warning')
            return redirect(url_for('ally_profile.verification'))
        
        # Cambiar estado a pendiente de verificación
        ally_profile.verification_status = 'pending_review'
        ally_profile.verification_submitted_at = datetime.utcnow()
        ally_profile.verification_token = generate_verification_token()
        
        db.session.commit()
        
        # Notificar a administradores
        _notify_admin_verification_request(ally_profile)
        
        # Enviar confirmación al aliado
        _send_verification_confirmation_email(ally_profile)
        
        # Registrar envío
        _log_verification_submission(ally_profile)
        
        flash('Perfil enviado para verificación. Recibirás una notificación cuando sea revisado.', 'success')
        return redirect(url_for('ally_profile.verification'))
        
    except Exception as e:
        current_app.logger.error(f"Error enviando verificación: {str(e)}")
        db.session.rollback()
        flash('Error al enviar perfil para verificación', 'error')
        return redirect(url_for('ally_profile.view'))


@ally_profile_bp.route('/verification-pending')
@login_required
@require_ally_access
def verification_pending():
    """
    Página de estado pendiente de verificación.
    
    Returns:
        Template con información de estado pendiente
    """
    ally_profile = g.ally_profile
    
    if ally_profile.verification_status != 'pending_review':
        return redirect(url_for('ally_profile.verification'))
    
    # Tiempo estimado de verificación
    estimated_completion = _calculate_estimated_verification_time(ally_profile)
    
    # Documentos en revisión
    documents_in_review = _get_documents_in_review(ally_profile)
    
    return render_template(
        'ally/profile/verification_pending.html',
        estimated_completion=estimated_completion,
        documents_in_review=documents_in_review,
        ally_profile=ally_profile
    )


# ==================== EXPORTACIÓN Y REPORTES ====================

@ally_profile_bp.route('/export/profile-summary')
@login_required
@require_ally_access
@track_ally_activity('profile_export', 'Exportación de resumen de perfil')
def export_profile_summary():
    """
    Exporta un resumen completo del perfil en PDF.
    
    Returns:
        Archivo PDF con resumen del perfil
    """
    try:
        ally_profile = g.ally_profile
        
        # Generar datos para el reporte
        profile_report_data = _generate_profile_report_data(ally_profile)
        
        # Generar PDF
        from app.utils.export_utils import export_to_pdf
        
        pdf_content = export_to_pdf(
            template='reports/ally_profile_summary.html',
            data=profile_report_data,
            filename=f'perfil_{ally_profile.user.first_name}_{ally_profile.user.last_name}'
        )
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=perfil_aliado.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando perfil: {str(e)}")
        flash('Error al generar resumen del perfil', 'error')
        return redirect(url_for('ally_profile.view'))


# ==================== FUNCIONES AUXILIARES ====================

def _get_complete_profile_data(ally: Ally) -> Dict[str, Any]:
    """
    Obtiene todos los datos del perfil del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con datos completos del perfil
    """
    user = ally.user
    
    return {
        'personal_info': {
            'full_name': user.full_name,
            'email': user.email,
            'phone': ally.phone,
            'birth_date': ally.birth_date,
            'gender': ally.gender,
            'location': {
                'city': ally.city,
                'state': ally.state,
                'country': ally.country
            },
            'profile_image_url': ally.profile_image_url,
            'bio': ally.bio
        },
        'professional_info': {
            'title': ally.professional_title,
            'company': ally.current_company,
            'industry': ally.industry,
            'experience_years': ally.experience_years,
            'education': ally.education,
            'linkedin_url': ally.linkedin_url,
            'website_url': ally.website_url,
            'achievements': ally.achievements
        },
        'contact_info': {
            'primary_email': user.email,
            'secondary_email': ally.secondary_email,
            'phone': ally.phone,
            'whatsapp': ally.whatsapp_number,
            'preferred_contact_method': ally.preferred_contact_method,
            'timezone': ally.timezone
        },
        'mentorship_info': {
            'mentorship_areas': ally.mentorship_areas,
            'max_mentees': ally.max_mentees_per_period,
            'session_duration_preferences': ally.session_duration_preferences,
            'mentorship_style': ally.mentorship_style,
            'success_stories': ally.success_stories
        }
    }


def _calculate_profile_stats(ally: Ally) -> Dict[str, Any]:
    """
    Calcula estadísticas del perfil del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con estadísticas del perfil
    """
    return {
        'profile_views': ally.profile_views or 0,
        'mentorship_sessions': MentorshipSession.query.filter_by(ally_id=ally.id).count(),
        'active_mentorships': MentorshipSession.query.filter_by(
            ally_id=ally.id, status='active'
        ).count(),
        'total_mentees': db.session.query(Entrepreneur).join(MentorshipSession).filter(
            MentorshipSession.ally_id == ally.id
        ).distinct().count(),
        'avg_rating': ally.average_rating or 0,
        'total_ratings': ally.total_ratings or 0,
        'join_date': ally.created_at,
        'last_activity': ally.last_activity,
        'response_rate': ally.message_response_rate or 0
    }


def _get_active_certifications(ally: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene certificaciones activas del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de certificaciones activas
    """
    # Esto requeriría un modelo Certification
    # Por ahora retornamos datos simulados
    return [
        {
            'id': 1,
            'name': 'Certified Business Mentor',
            'issuer': 'International Mentoring Association',
            'issue_date': date(2023, 6, 15),
            'expiry_date': date(2025, 6, 15),
            'credential_id': 'CBM-2023-001',
            'verification_url': 'https://verify.ima.org/CBM-2023-001',
            'status': 'active'
        }
    ]


def _organize_specializations(ally: Ally) -> Dict[str, Any]:
    """
    Organiza las especializaciones del aliado por categorías.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con especializaciones organizadas
    """
    # Implementación básica - requeriría modelo Specialization
    return {
        'primary_specializations': [],
        'secondary_specializations': [],
        'custom_specializations': [],
        'total_count': 0
    }


def _get_availability_summary(ally: Ally) -> Dict[str, Any]:
    """
    Obtiene resumen de disponibilidad semanal del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con resumen de disponibilidad
    """
    # Implementación básica - requeriría modelo AvailabilitySlot
    return {
        'weekly_hours_available': 20,
        'days_available': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        'preferred_times': ['morning', 'afternoon'],
        'timezone': ally.timezone or 'UTC',
        'next_available_slot': datetime.utcnow() + timedelta(days=1)
    }


def _get_verification_history(ally: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene histórico de verificaciones del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista con histórico de verificaciones
    """
    return [
        {
            'date': ally.verification_submitted_at or ally.created_at,
            'status': ally.verification_status,
            'reviewer': 'Sistema',
            'notes': 'Perfil creado y en proceso de verificación'
        }
    ]


def _get_profile_documents(ally: Ally) -> List[Dict[str, Any]]:
    """
    Obtiene documentos del perfil del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de documentos del perfil
    """
    documents = Document.query.filter_by(
        owner_id=ally.user_id,
        owner_type='ally'
    ).order_by(desc(Document.created_at)).all()
    
    return [
        {
            'id': doc.id,
            'filename': doc.filename,
            'document_type': doc.document_type,
            'file_size': doc.file_size,
            'upload_date': doc.created_at,
            'status': doc.status,
            'description': doc.description
        }
        for doc in documents
    ]


def _calculate_profile_completeness(ally: Ally) -> Dict[str, Any]:
    """
    Calcula el score de completitud del perfil.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con score de completitud detallado
    """
    scores = {}
    
    # Información personal (25%)
    personal_score = 0
    if ally.user.first_name and ally.user.last_name:
        personal_score += 20
    if ally.user.email:
        personal_score += 15
    if ally.phone:
        personal_score += 15
    if ally.bio:
        personal_score += 25
    if ally.profile_image_url:
        personal_score += 25
    
    scores['personal'] = personal_score
    
    # Información profesional (30%)
    professional_score = 0
    if ally.professional_title:
        professional_score += 25
    if ally.experience_years:
        professional_score += 20
    if ally.industry:
        professional_score += 20
    if ally.education:
        professional_score += 20
    if ally.linkedin_url:
        professional_score += 15
    
    scores['professional'] = professional_score
    
    # Especializations (20%)
    # specializations_score = len(ally.specializations) * 20 if ally.specializations else 0
    specializations_score = 60  # Valor simulado
    scores['specializations'] = min(specializations_score, 100)
    
    # Disponibilidad (15%)
    # availability_score = len(ally.availability_slots) * 15 if ally.availability_slots else 0
    availability_score = 80  # Valor simulado
    scores['availability'] = min(availability_score, 100)
    
    # Documentos y verificación (10%)
    documents_count = Document.query.filter_by(
        owner_id=ally.user_id,
        owner_type='ally'
    ).count()
    documents_score = min(documents_count * 25, 100)
    scores['documents'] = documents_score
    
    # Calcular score general
    overall_score = (
        scores['personal'] * 0.25 +
        scores['professional'] * 0.30 +
        scores['specializations'] * 0.20 +
        scores['availability'] * 0.15 +
        scores['documents'] * 0.10
    )
    
    return {
        'overall_score': round(overall_score, 1),
        'section_scores': scores,
        'missing_items': _get_missing_profile_items(ally, scores),
        'next_steps': _get_profile_improvement_suggestions(scores)
    }


def _get_recent_profile_activity(ally: Ally, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtiene actividad reciente relacionada con el perfil.
    
    Args:
        ally: Perfil del aliado
        limit: Número máximo de actividades
        
    Returns:
        Lista de actividades recientes del perfil
    """
    activities = ActivityLog.query.filter(
        ActivityLog.user_id == ally.user_id,
        ActivityLog.action.in_([
            'profile_update', 'profile_image_upload', 'document_upload',
            'certification_add', 'availability_update', 'verification_submit'
        ])
    ).order_by(desc(ActivityLog.created_at)).limit(limit).all()
    
    return [
        {
            'action': activity.action,
            'description': activity.description,
            'created_at': activity.created_at,
            'icon': _get_profile_activity_icon(activity.action)
        }
        for activity in activities
    ]


def _get_privacy_settings(ally: Ally) -> Dict[str, Any]:
    """
    Obtiene configuraciones de privacidad del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con configuraciones de privacidad
    """
    return {
        'profile_visibility': ally.profile_visibility or 'public',
        'contact_info_visible': ally.contact_info_visible or False,
        'allow_direct_contact': ally.allow_direct_contact or True,
        'show_in_directory': ally.show_in_directory or True,
        'share_statistics': ally.share_statistics or False
    }


def _populate_edit_forms(ally: Ally, personal_form, professional_form, contact_form, specializations_form):
    """
    Pobla los formularios de edición con datos actuales.
    
    Args:
        ally: Perfil del aliado
        personal_form: Formulario de información personal
        professional_form: Formulario de información profesional
        contact_form: Formulario de información de contacto
        specializations_form: Formulario de especializaciones
    """
    # Poblar formulario personal
    if ally.birth_date:
        personal_form.birth_date.data = ally.birth_date
    personal_form.gender.data = ally.gender
    personal_form.bio.data = ally.bio
    personal_form.city.data = ally.city
    personal_form.state.data = ally.state
    personal_form.country.data = ally.country
    
    # Poblar formulario profesional
    professional_form.professional_title.data = ally.professional_title
    professional_form.current_company.data = ally.current_company
    professional_form.industry.data = ally.industry
    professional_form.experience_years.data = ally.experience_years
    professional_form.education.data = ally.education
    professional_form.linkedin_url.data = ally.linkedin_url
    professional_form.website_url.data = ally.website_url
    
    # Poblar formulario de contacto
    contact_form.phone.data = ally.phone
    contact_form.secondary_email.data = ally.secondary_email
    contact_form.whatsapp_number.data = ally.whatsapp_number
    contact_form.preferred_contact_method.data = ally.preferred_contact_method
    contact_form.timezone.data = ally.timezone


def _get_form_options() -> Dict[str, List[Tuple[str, str]]]:
    """
    Obtiene opciones para los selectores de los formularios.
    
    Returns:
        Dict con opciones para selectores
    """
    return {
        'countries': [('US', 'Estados Unidos'), ('CO', 'Colombia'), ('MX', 'México')],
        'industries': [
            ('technology', 'Tecnología'),
            ('finance', 'Finanzas'),
            ('healthcare', 'Salud'),
            ('education', 'Educación'),
            ('consulting', 'Consultoría')
        ],
        'experience_levels': [
            ('junior', '1-3 años'),
            ('mid', '3-7 años'),
            ('senior', '7-15 años'),
            ('expert', '15+ años')
        ],
        'contact_methods': [
            ('email', 'Email'),
            ('phone', 'Teléfono'),
            ('whatsapp', 'WhatsApp'),
            ('platform', 'Plataforma')
        ],
        'timezones': [
            ('America/Bogota', 'Colombia (UTC-5)'),
            ('America/Mexico_City', 'México (UTC-6)'),
            ('America/New_York', 'Nueva York (UTC-5)'),
            ('Europe/Madrid', 'España (UTC+1)')
        ]
    }


def _get_current_profile_data(ally: Ally) -> Dict[str, Any]:
    """
    Obtiene datos actuales del perfil para comparación.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Dict con datos actuales
    """
    return {
        'personal': {
            'full_name': ally.user.full_name,
            'email': ally.user.email,
            'phone': ally.phone,
            'bio': ally.bio,
            'location': f"{ally.city}, {ally.state}, {ally.country}".strip(', ')
        },
        'professional': {
            'title': ally.professional_title,
            'company': ally.current_company,
            'industry': ally.industry,
            'experience': ally.experience_years,
            'education': ally.education
        }
    }


def _process_profile_update(ally: Ally, section: str) -> Dict[str, Any]:
    """
    Procesa la actualización de una sección específica del perfil.
    
    Args:
        ally: Perfil del aliado
        section: Sección a actualizar
        
    Returns:
        Dict con resultado de la actualización
    """
    try:
        changes = []
        
        if section == 'personal':
            changes = _update_personal_info(ally)
        elif section == 'professional':
            changes = _update_professional_info(ally)
        elif section == 'contact':
            changes = _update_contact_info(ally)
        elif section == 'specializations':
            changes = _update_specializations_info(ally)
        
        if changes:
            ally.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'success': True,
                'changes': changes,
                'notify_admin': _should_notify_admin_of_changes(changes)
            }
        else:
            return {
                'success': True,
                'changes': [],
                'message': 'No se detectaron cambios'
            }
            
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        }


def _update_personal_info(ally: Ally) -> List[str]:
    """
    Actualiza información personal del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de campos modificados
    """
    changes = []
    
    # Actualizar campos del usuario
    user = ally.user
    
    if request.form.get('first_name') != user.first_name:
        user.first_name = request.form.get('first_name', '').strip()
        changes.append('first_name')
    
    if request.form.get('last_name') != user.last_name:
        user.last_name = request.form.get('last_name', '').strip()
        changes.append('last_name')
    
    # Actualizar campos del aliado
    if request.form.get('bio') != ally.bio:
        ally.bio = request.form.get('bio', '').strip()
        changes.append('bio')
    
    if request.form.get('city') != ally.city:
        ally.city = request.form.get('city', '').strip()
        changes.append('city')
    
    if request.form.get('state') != ally.state:
        ally.state = request.form.get('state', '').strip()
        changes.append('state')
    
    if request.form.get('country') != ally.country:
        ally.country = request.form.get('country', '').strip()
        changes.append('country')
    
    birth_date_str = request.form.get('birth_date')
    if birth_date_str:
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            if birth_date != ally.birth_date:
                ally.birth_date = birth_date
                changes.append('birth_date')
        except ValueError:
            pass
    
    gender = request.form.get('gender')
    if gender and gender != ally.gender:
        ally.gender = gender
        changes.append('gender')
    
    return changes


def _update_professional_info(ally: Ally) -> List[str]:
    """
    Actualiza información profesional del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de campos modificados
    """
    changes = []
    
    professional_title = request.form.get('professional_title', '').strip()
    if professional_title != ally.professional_title:
        ally.professional_title = professional_title
        changes.append('professional_title')
    
    current_company = request.form.get('current_company', '').strip()
    if current_company != ally.current_company:
        ally.current_company = current_company
        changes.append('current_company')
    
    industry = request.form.get('industry', '').strip()
    if industry != ally.industry:
        ally.industry = industry
        changes.append('industry')
    
    try:
        experience_years = int(request.form.get('experience_years', 0))
        if experience_years != ally.experience_years:
            ally.experience_years = experience_years
            changes.append('experience_years')
    except (ValueError, TypeError):
        pass
    
    education = request.form.get('education', '').strip()
    if education != ally.education:
        ally.education = education
        changes.append('education')
    
    linkedin_url = request.form.get('linkedin_url', '').strip()
    if linkedin_url != ally.linkedin_url:
        if linkedin_url and not validate_url(linkedin_url):
            raise ValidationError('URL de LinkedIn no válida')
        ally.linkedin_url = linkedin_url
        changes.append('linkedin_url')
    
    website_url = request.form.get('website_url', '').strip()
    if website_url != ally.website_url:
        if website_url and not validate_url(website_url):
            raise ValidationError('URL de sitio web no válida')
        ally.website_url = website_url
        changes.append('website_url')
    
    return changes


def _update_contact_info(ally: Ally) -> List[str]:
    """
    Actualiza información de contacto del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de campos modificados
    """
    changes = []
    
    phone = request.form.get('phone', '').strip()
    if phone != ally.phone:
        if phone and not validate_phone(phone):
            raise ValidationError('Número de teléfono no válido')
        ally.phone = phone
        changes.append('phone')
    
    secondary_email = request.form.get('secondary_email', '').strip()
    if secondary_email != ally.secondary_email:
        ally.secondary_email = secondary_email
        changes.append('secondary_email')
    
    whatsapp_number = request.form.get('whatsapp_number', '').strip()
    if whatsapp_number != ally.whatsapp_number:
        if whatsapp_number and not validate_phone(whatsapp_number):
            raise ValidationError('Número de WhatsApp no válido')
        ally.whatsapp_number = whatsapp_number
        changes.append('whatsapp_number')
    
    preferred_contact_method = request.form.get('preferred_contact_method')
    if preferred_contact_method != ally.preferred_contact_method:
        ally.preferred_contact_method = preferred_contact_method
        changes.append('preferred_contact_method')
    
    timezone = request.form.get('timezone')
    if timezone != ally.timezone:
        ally.timezone = timezone
        changes.append('timezone')
    
    return changes


def _update_specializations_info(ally: Ally) -> List[str]:
    """
    Actualiza especializaciones del aliado.
    
    Args:
        ally: Perfil del aliado
        
    Returns:
        Lista de campos modificados
    """
    changes = []
    
    # Esto requeriría un modelo de especializaciones más complejo
    # Por ahora solo actualizamos campos básicos
    
    mentorship_areas = request.form.get('mentorship_areas', '').strip()
    if mentorship_areas != ally.mentorship_areas:
        ally.mentorship_areas = mentorship_areas
        changes.append('mentorship_areas')
    
    try:
        max_mentees = int(request.form.get('max_mentees_per_period', 0))
        if max_mentees != ally.max_mentees_per_period:
            ally.max_mentees_per_period = max_mentees
            changes.append('max_mentees_per_period')
    except (ValueError, TypeError):
        pass
    
    return changes


def _should_notify_admin_of_changes(changes: List[str]) -> bool:
    """
    Determina si se debe notificar a administradores sobre los cambios.
    
    Args:
        changes: Lista de campos modificados
        
    Returns:
        True si se debe notificar, False en caso contrario
    """
    critical_fields = [
        'professional_title', 'current_company', 'industry', 
        'linkedin_url', 'website_url', 'mentorship_areas'
    ]
    
    return any(field in critical_fields for field in changes)


def _log_profile_changes(ally: Ally, section: str, changes: List[str]) -> None:
    """
    Registra cambios del perfil en el log de actividades.
    
    Args:
        ally: Perfil del aliado
        section: Sección modificada
        changes: Lista de campos modificados
    """
    try:
        activity = ActivityLog(
            user_id=ally.user_id,
            action='profile_update',
            description=f'Actualización de sección {section}: {", ".join(changes)}',
            entity_type='ally_profile',
            entity_id=ally.id,
            metadata={
                'section': section,
                'fields_changed': changes,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando cambios de perfil: {str(e)}")


def _notify_admin_profile_changes(ally: Ally, changes: List[str]) -> None:
    """
    Notifica a administradores sobre cambios importantes del perfil.
    
    Args:
        ally: Perfil del aliado
        changes: Lista de campos modificados
    """
    try:
        notification_service = NotificationService()
        
        # Buscar administradores
        admin_users = User.query.filter_by(role='admin', is_active=True).all()
        
        for admin in admin_users:
            notification_service.send_notification(
                user_id=admin.id,
                title='Cambios importantes en perfil de aliado',
                message=f'El aliado {ally.user.full_name} ha actualizado información crítica de su perfil',
                notification_type='profile_update',
                metadata={
                    'ally_id': ally.id,
                    'ally_name': ally.user.full_name,
                    'fields_changed': changes
                }
            )
            
    except Exception as e:
        current_app.logger.error(f"Error notificando cambios de perfil: {str(e)}")


def _update_profile_completeness(ally: Ally) -> None:
    """
    Actualiza el score de completitud del perfil después de cambios.
    
    Args:
        ally: Perfil del aliado
    """
    try:
        completeness = _calculate_profile_completeness(ally)
        ally.profile_completeness_score = completeness['overall_score']
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error actualizando completitud: {str(e)}")


# Funciones auxiliares para procesamiento de archivos
def _process_and_save_profile_image(file, filename: str, ally: Ally) -> Dict[str, str]:
    """
    Procesa y guarda imagen de perfil en múltiples tamaños.
    
    Args:
        file: Archivo de imagen
        filename: Nombre del archivo
        ally: Perfil del aliado
        
    Returns:
        Dict con URLs de las diferentes versiones de la imagen
    """
    storage_service = FileStorageService()
    image_urls = {}
    
    # Abrir imagen original
    image = Image.open(file.stream)
    
    # Generar diferentes tamaños
    for size in PROFILE_IMAGE_SIZES:
        # Redimensionar imagen
        resized_image = resize_image(image, size)
        
        # Comprimir imagen
        compressed_image = compress_image(resized_image, quality=85)
        
        # Generar nombre único para cada tamaño
        size_suffix = f"{size[0]}x{size[1]}"
        size_filename = f"{filename.rsplit('.', 1)[0]}_{size_suffix}.{filename.rsplit('.', 1)[1]}"
        
        # Guardar imagen
        image_url = storage_service.save_file(
            compressed_image,
            f"profiles/allies/{ally.id}/images/{size_filename}",
            'image'
        )
        
        # Mapear tamaño a nombre
        if size == (150, 150):
            image_urls['small'] = image_url
        elif size == (300, 300):
            image_urls['medium'] = image_url
        elif size == (600, 600):
            image_urls['large'] = image_url
    
    return image_urls


def _delete_old_profile_images(old_image_url: str) -> None:
    """
    Elimina imágenes anteriores del perfil.
    
    Args:
        old_image_url: URL de la imagen anterior
    """
    try:
        storage_service = FileStorageService()
        
        # Eliminar imagen anterior y sus variantes
        # Esta implementación dependería del servicio de almacenamiento específico
        storage_service.delete_file(old_image_url)
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando imagen anterior: {str(e)}")


def _log_image_change(ally: Ally, old_image: Optional[str], new_image: str) -> None:
    """
    Registra cambio de imagen de perfil.
    
    Args:
        ally: Perfil del aliado
        old_image: URL de imagen anterior
        new_image: URL de imagen nueva
    """
    try:
        activity = ActivityLog(
            user_id=ally.user_id,
            action='profile_image_upload',
            description='Actualización de imagen de perfil',
            entity_type='ally_profile',
            entity_id=ally.id,
            metadata={
                'old_image': old_image,
                'new_image': new_image,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando cambio de imagen: {str(e)}")


# Funciones auxiliares adicionales (implementación básica)
def _get_current_settings(ally: Ally) -> Dict[str, Any]:
    """Obtiene configuraciones actuales del aliado."""
    return {
        'notifications_enabled': ally.notifications_enabled or True,
        'email_notifications': ally.email_notifications or True,
        'timezone': ally.timezone or 'UTC',
        'language': ally.language or 'es',
        'profile_visibility': ally.profile_visibility or 'public'
    }


def _get_settings_options() -> Dict[str, List[Tuple[str, str]]]:
    """Obtiene opciones para configuraciones."""
    return {
        'timezones': [
            ('America/Bogota', 'Colombia (UTC-5)'),
            ('America/Mexico_City', 'México (UTC-6)'),
            ('UTC', 'UTC')
        ],
        'languages': [
            ('es', 'Español'),
            ('en', 'English'),
            ('pt', 'Português')
        ],
        'visibility_options': [
            ('public', 'Público'),
            ('private', 'Privado'),
            ('organization', 'Solo organización')
        ]
    }


def _get_organized_availability(ally: Ally) -> Dict[str, Any]:
    """Obtiene disponibilidad organizada por días."""
    # Implementación básica - requiere modelo AvailabilitySlot
    return {
        'monday': [],
        'tuesday': [],
        'wednesday': [],
        'thursday': [],
        'friday': [],
        'saturday': [],
        'sunday': []
    }


def _get_upcoming_appointments(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene próximas citas del aliado."""
    # Implementación básica
    return []


def _calculate_availability_stats(ally: Ally) -> Dict[str, Any]:
    """Calcula estadísticas de disponibilidad."""
    return {
        'total_hours_per_week': 20,
        'available_days': 5,
        'busiest_day': 'Tuesday',
        'next_free_slot': datetime.utcnow() + timedelta(hours=2)
    }


def _detect_availability_conflicts(ally: Ally) -> List[Dict[str, Any]]:
    """Detecta conflictos en la disponibilidad."""
    return []


def _organize_certifications(ally: Ally) -> Dict[str, Any]:
    """Organiza certificaciones por estado."""
    return {
        'active': [],
        'expired': [],
        'pending': [],
        'total_count': 0
    }


def _calculate_certification_stats(ally: Ally) -> Dict[str, Any]:
    """Calcula estadísticas de certificaciones."""
    return {
        'total_certifications': 0,
        'active_certifications': 0,
        'expired_certifications': 0,
        'renewal_due_soon': 0
    }


def _get_upcoming_renewals(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene próximas renovaciones de certificaciones."""
    return []


def _get_detailed_verification_status(ally: Ally) -> Dict[str, Any]:
    """Obtiene estado detallado de verificación."""
    return {
        'current_status': ally.verification_status,
        'submitted_at': ally.verification_submitted_at,
        'estimated_completion': None,
        'completion_percentage': 50,
        'pending_items': []
    }


def _get_required_verification_documents(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene documentos requeridos para verificación."""
    return [
        {
            'document_type': 'identification',
            'name': 'Documento de identidad',
            'required': True,
            'uploaded': False,
            'description': 'Cédula, pasaporte o documento oficial de identificación'
        },
        {
            'document_type': 'professional_certification',
            'name': 'Certificación profesional',
            'required': False,
            'uploaded': False,
            'description': 'Diplomas, certificados profesionales o títulos académicos'
        }
    ]


def _get_verification_timeline(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene timeline del proceso de verificación."""
    return [
        {
            'date': ally.created_at,
            'status': 'profile_created',
            'title': 'Perfil creado',
            'description': 'Se creó el perfil del aliado'
        }
    ]


def _get_verification_next_steps(ally: Ally) -> List[str]:
    """Obtiene próximos pasos en el proceso de verificación."""
    if ally.verification_status == 'pending':
        return [
            'Completar información profesional',
            'Subir documento de identificación',
            'Agregar al menos una certificación',
            'Configurar disponibilidad'
        ]
    return []


def _validate_document_type(document_type: str, ally: Ally) -> bool:
    """Valida si el tipo de documento es válido para el aliado."""
    valid_types = [
        'identification', 'professional_certification', 'diploma',
        'cv', 'portfolio', 'recommendation_letter'
    ]
    return document_type in valid_types


def _process_and_save_document(file, document_type: str, description: str, ally: Ally) -> Dict[str, Any]:
    """
    Procesa y guarda un documento del aliado.
    
    Args:
        file: Archivo a procesar
        document_type: Tipo de documento
        description: Descripción del documento
        ally: Perfil del aliado
        
    Returns:
        Dict con resultado del procesamiento
    """
    try:
        # Validar archivo
        if not validate_file_type(file.filename, ALLOWED_DOCUMENT_EXTENSIONS):
            return {'success': False, 'error': 'Tipo de archivo no permitido'}
        
        # Generar nombre único
        filename = generate_unique_filename(file.filename)
        
        # Guardar archivo
        storage_service = FileStorageService()
        file_url = storage_service.save_file(
            file,
            f"profiles/allies/{ally.id}/documents/{filename}",
            document_type
        )
        
        # Crear registro en base de datos
        document = Document(
            filename=filename,
            original_filename=file.filename,
            file_path=file_url,
            file_size=len(file.read()),
            document_type=document_type,
            description=description,
            owner_id=ally.user_id,
            owner_type='ally',
            status='pending_review'
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Registrar actividad
        _log_document_upload(ally, document)
        
        return {
            'success': True,
            'document_data': {
                'id': document.id,
                'filename': document.filename,
                'document_type': document.document_type,
                'upload_date': document.created_at.isoformat(),
                'status': document.status
            }
        }
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error procesando documento: {str(e)}")
        return {'success': False, 'error': 'Error interno procesando documento'}


def _is_critical_document(document: Document) -> bool:
    """Verifica si un documento es crítico y no se puede eliminar."""
    critical_types = ['identification', 'professional_certification']
    return document.document_type in critical_types and document.status == 'approved'


def _delete_document_file(file_path: str) -> bool:
    """
    Elimina archivo físico del documento.
    
    Args:
        file_path: Ruta del archivo
        
    Returns:
        True si se eliminó exitosamente
    """
    try:
        storage_service = FileStorageService()
        return storage_service.delete_file(file_path)
    except Exception as e:
        current_app.logger.error(f"Error eliminando archivo: {str(e)}")
        return False


def _log_document_deletion(ally: Ally, document: Document) -> None:
    """Registra eliminación de documento."""
    try:
        activity = ActivityLog(
            user_id=ally.user_id,
            action='document_delete',
            description=f'Eliminación de documento: {document.filename}',
            entity_type='document',
            entity_id=document.id,
            metadata={
                'document_type': document.document_type,
                'filename': document.filename
            }
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando eliminación: {str(e)}")


def _log_document_upload(ally: Ally, document: Document) -> None:
    """Registra carga de documento."""
    try:
        activity = ActivityLog(
            user_id=ally.user_id,
            action='document_upload',
            description=f'Carga de documento: {document.filename}',
            entity_type='document',
            entity_id=document.id,
            metadata={
                'document_type': document.document_type,
                'filename': document.filename
            }
        )
        
        db.session.add(activity)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error registrando carga: {str(e)}")


# Más funciones auxiliares según necesidades específicas...

def _get_missing_profile_items(ally: Ally, scores: Dict[str, float]) -> List[str]:
    """Obtiene items faltantes del perfil."""
    missing = []
    
    if scores['personal'] < 100:
        if not ally.profile_image_url:
            missing.append('Foto de perfil')
        if not ally.bio:
            missing.append('Biografía')
    
    if scores['professional'] < 100:
        if not ally.professional_title:
            missing.append('Título profesional')
        if not ally.linkedin_url:
            missing.append('Perfil de LinkedIn')
    
    return missing


def _get_profile_improvement_suggestions(scores: Dict[str, float]) -> List[str]:
    """Obtiene sugerencias para mejorar el perfil."""
    suggestions = []
    
    if scores['documents'] < 80:
        suggestions.append('Agregar certificaciones profesionales')
    
    if scores['availability'] < 80:
        suggestions.append('Configurar horarios de disponibilidad')
    
    if scores['specializations'] < 80:
        suggestions.append('Definir áreas de especialización')
    
    return suggestions


def _get_profile_activity_icon(action: str) -> str:
    """Obtiene icono para actividad del perfil."""
    icons = {
        'profile_update': 'edit',
        'profile_image_upload': 'photo_camera',
        'document_upload': 'file_upload',
        'certification_add': 'verified',
        'availability_update': 'schedule',
        'verification_submit': 'check_circle'
    }
    return icons.get(action, 'info')


def _calculate_detailed_completeness(ally: Ally) -> Dict[str, Any]:
    """Calcula completitud detallada para API."""
    return _calculate_profile_completeness(ally)


def _get_api_verification_status(ally: Ally) -> Dict[str, Any]:
    """Obtiene estado de verificación para API."""
    return _get_detailed_verification_status(ally)


# Funciones para validación y procesamiento de APIs
def _validate_availability_data(data: Dict[str, Any]) -> bool:
    """Valida datos de disponibilidad."""
    required_fields = ['day', 'start_time', 'end_time']
    return all(field in data for field in required_fields)


def _update_ally_availability(ally: Ally, data: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza disponibilidad del aliado."""
    # Implementación básica
    return {'success': True, 'updated_slots': []}


def _create_certification(ally: Ally, data: Dict[str, Any]) -> Dict[str, Any]:
    """Crea nueva certificación."""
    # Implementación básica
    return {'success': True, 'certification_data': {}}


def _validate_specializations(specialization_ids: List[int], custom_specializations: List[str]) -> bool:
    """Valida especializaciones."""
    return True  # Implementación básica


def _update_ally_specializations(ally: Ally, specialization_ids: List[int], custom_specializations: List[str]) -> Dict[str, Any]:
    """Actualiza especializaciones del aliado."""
    return {'success': True}


def _validate_preferences_data(data: Dict[str, Any]) -> bool:
    """Valida datos de preferencias."""
    return True  # Implementación básica


def _update_ally_preferences(ally: Ally, data: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza preferencias del aliado."""
    return {'success': True}


def _check_required_documents(ally: Ally) -> List[str]:
    """Verifica documentos requeridos faltantes."""
    return []  # Implementación básica


def _notify_admin_verification_request(ally: Ally) -> None:
    """Notifica a administradores sobre solicitud de verificación."""
    pass  # Implementación básica


def _send_verification_confirmation_email(ally: Ally) -> None:
    """Envía email de confirmación de verificación."""
    pass  # Implementación básica


def _log_verification_submission(ally: Ally) -> None:
    """Registra envío de verificación."""
    pass  # Implementación básica


def _calculate_estimated_verification_time(ally: Ally) -> datetime:
    """Calcula tiempo estimado de verificación."""
    return datetime.utcnow() + timedelta(days=5)


def _get_documents_in_review(ally: Ally) -> List[Dict[str, Any]]:
    """Obtiene documentos en revisión."""
    return []


def _generate_profile_report_data(ally: Ally) -> Dict[str, Any]:
    """Genera datos para reporte del perfil."""
    return {
        'ally': ally,
        'profile_data': _get_complete_profile_data(ally),
        'stats': _calculate_profile_stats(ally),
        'completeness': _calculate_profile_completeness(ally)
    }