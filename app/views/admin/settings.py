"""
Configuraciones del Sistema - Panel Administrativo
==================================================

Este módulo gestiona todas las configuraciones del ecosistema de emprendimiento,
incluyendo configuraciones generales, seguridad, integraciones, personalizaciones,
y configuraciones avanzadas del sistema.

Autor: Sistema de Emprendimiento
Fecha: 2025
"""

import os
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, abort, send_file, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_, text
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

# Importaciones del core del sistema
from app.core.permissions import admin_required, permission_required, super_admin_required
from app.core.exceptions import ValidationError, AuthorizationError, ConfigurationError
from app.core.constants import (
    SUPPORTED_LANGUAGES, SUPPORTED_CURRENCIES, SUPPORTED_TIMEZONES,
    EMAIL_PROVIDERS, SMS_PROVIDERS, STORAGE_PROVIDERS, PAYMENT_PROVIDERS,
    SECURITY_LEVELS, LOG_LEVELS, BACKUP_FREQUENCIES
)
from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data

# Importaciones de modelos
from app.models import (
    SystemConfiguration, ConfigurationHistory, User, ActivityLog,
    Integration, SecuritySettings, NotificationSettings
)

# Importaciones de servicios
from app.services.email import EmailService
from app.services.sms import SMSService
from app.services.file_storage import FileStorageService
from app.services.backup_service import BackupService
from app.services.monitoring_service import MonitoringService
from app.services.cache_service import CacheService

# Importaciones de formularios
from app.forms.admin import (
    GeneralSettingsForm, SecuritySettingsForm, EmailSettingsForm,
    SMSSettingsForm, IntegrationSettingsForm, PersonalizationSettingsForm,
    BackupSettingsForm, PerformanceSettingsForm, RegionalSettingsForm,
    MaintenanceSettingsForm, MonitoringSettingsForm, APISettingsForm
)

# Importaciones de utilidades
from app.utils.decorators import handle_exceptions, cache_result, rate_limit
from app.utils.validators import (
    validate_email_config, validate_api_key, validate_webhook_url,
    validate_storage_config, validate_security_config
)
from app.utils.formatters import format_currency, format_file_size
from app.utils.config_utils import (
    backup_current_config, restore_config_backup, validate_config_integrity,
    migrate_config_schema, export_config, import_config
)
from app.utils.encryption_utils import generate_encryption_key, rotate_encryption_keys

# Extensiones
from app.extensions import db, cache, redis_client

# Crear blueprint
admin_settings = Blueprint('admin_settings', __name__, url_prefix='/admin/settings')

# ============================================================================
# DASHBOARD PRINCIPAL DE CONFIGURACIONES
# ============================================================================

@admin_settings.route('/')
@admin_settings.route('/dashboard')
@login_required
@admin_required
@handle_exceptions
def dashboard():
    """
    Dashboard principal de configuraciones del sistema.
    Muestra el estado general de todas las configuraciones.
    """
    try:
        # Estado general del sistema
        system_status = _get_system_status()
        
        # Configuraciones críticas
        critical_configs = _get_critical_configurations_status()
        
        # Integraciones activas
        active_integrations = _get_active_integrations_status()
        
        # Alertas de configuración
        config_alerts = _get_configuration_alerts()
        
        # Últimos cambios
        recent_changes = ConfigurationHistory.query.options(
            joinedload(ConfigurationHistory.changed_by)
        ).order_by(desc(ConfigurationHistory.changed_at)).limit(10).all()
        
        # Estadísticas de uso
        usage_stats = _get_configuration_usage_stats()
        
        # Health checks
        health_checks = _run_configuration_health_checks()
        
        return render_template(
            'admin/settings/dashboard.html',
            system_status=system_status,
            critical_configs=critical_configs,
            active_integrations=active_integrations,
            config_alerts=config_alerts,
            recent_changes=recent_changes,
            usage_stats=usage_stats,
            health_checks=health_checks
        )
        
    except Exception as e:
        current_app.logger.error(f"Error en dashboard de configuraciones: {str(e)}")
        flash('Error al cargar el dashboard de configuraciones.', 'error')
        return redirect(url_for('admin_dashboard.index'))

# ============================================================================
# CONFIGURACIONES GENERALES
# ============================================================================

@admin_settings.route('/general', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_general_settings')
@handle_exceptions
def general_settings():
    """
    Configuraciones generales del sistema.
    """
    form = GeneralSettingsForm()
    
    # Cargar configuraciones actuales
    current_configs = _load_current_general_settings()
    
    if not form.is_submitted():
        # Poblar formulario con valores actuales
        _populate_general_settings_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            # Backup de configuración actual
            backup_current_config('general_settings')
            
            # Preparar nuevas configuraciones
            new_configs = {
                'site_name': form.site_name.data.strip(),
                'site_description': form.site_description.data.strip(),
                'site_url': form.site_url.data.strip(),
                'admin_email': form.admin_email.data.lower().strip(),
                'support_email': form.support_email.data.lower().strip(),
                'maintenance_mode': form.maintenance_mode.data,
                'registration_enabled': form.registration_enabled.data,
                'email_verification_required': form.email_verification_required.data,
                'default_timezone': form.default_timezone.data,
                'default_language': form.default_language.data,
                'max_file_upload_size': form.max_file_upload_size.data,
                'session_timeout_minutes': form.session_timeout_minutes.data,
                'terms_of_service_url': form.terms_of_service_url.data.strip() if form.terms_of_service_url.data else None,
                'privacy_policy_url': form.privacy_policy_url.data.strip() if form.privacy_policy_url.data else None,
                'contact_phone': form.contact_phone.data.strip() if form.contact_phone.data else None,
                'company_address': form.company_address.data.strip() if form.company_address.data else None,
                'google_analytics_id': form.google_analytics_id.data.strip() if form.google_analytics_id.data else None,
                'allow_public_registration': form.allow_public_registration.data,
                'require_admin_approval': form.require_admin_approval.data
            }
            
            # Validar configuraciones
            validation_result = _validate_general_settings(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/general.html', form=form)
            
            # Guardar configuraciones
            _save_general_settings(new_configs)
            
            # Invalidar cache
            cache.delete('general_settings')
            
            # Registrar cambio
            _log_configuration_change('general_settings', current_configs, new_configs)
            
            flash('Configuraciones generales actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.general_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones generales: {str(e)}")
            flash('Error al guardar las configuraciones.', 'error')
    
    return render_template('admin/settings/general.html', form=form, current_configs=current_configs)

# ============================================================================
# CONFIGURACIONES DE SEGURIDAD
# ============================================================================

@admin_settings.route('/security', methods=['GET', 'POST'])
@login_required
@super_admin_required  # Requiere permisos de super admin
@handle_exceptions
def security_settings():
    """
    Configuraciones de seguridad del sistema.
    Solo accesible para super administradores.
    """
    form = SecuritySettingsForm()
    current_configs = _load_current_security_settings()
    
    if not form.is_submitted():
        _populate_security_settings_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            # Backup de configuración actual
            backup_current_config('security_settings')
            
            new_configs = {
                'password_min_length': form.password_min_length.data,
                'password_require_uppercase': form.password_require_uppercase.data,
                'password_require_lowercase': form.password_require_lowercase.data,
                'password_require_numbers': form.password_require_numbers.data,
                'password_require_symbols': form.password_require_symbols.data,
                'password_expiry_days': form.password_expiry_days.data,
                'max_login_attempts': form.max_login_attempts.data,
                'lockout_duration_minutes': form.lockout_duration_minutes.data,
                'two_factor_required': form.two_factor_required.data,
                'session_security_level': form.session_security_level.data,
                'ip_whitelist_enabled': form.ip_whitelist_enabled.data,
                'allowed_ip_ranges': form.allowed_ip_ranges.data.split('\n') if form.allowed_ip_ranges.data else [],
                'api_rate_limit_per_minute': form.api_rate_limit_per_minute.data,
                'enable_audit_logging': form.enable_audit_logging.data,
                'log_retention_days': form.log_retention_days.data,
                'encryption_algorithm': form.encryption_algorithm.data,
                'force_https': form.force_https.data,
                'secure_cookies': form.secure_cookies.data,
                'csrf_protection': form.csrf_protection.data,
                'content_security_policy': form.content_security_policy.data
            }
            
            # Validar configuraciones de seguridad
            validation_result = validate_security_config(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación de seguridad: {validation_result["message"]}', 'error')
                return render_template('admin/settings/security.html', form=form)
            
            # Verificar si necesita rotar claves de encriptación
            if new_configs['encryption_algorithm'] != current_configs.get('encryption_algorithm'):
                _rotate_encryption_keys(new_configs['encryption_algorithm'])
            
            # Guardar configuraciones
            _save_security_settings(new_configs)
            
            # Aplicar configuraciones inmediatamente
            _apply_security_settings(new_configs)
            
            # Registrar cambio crítico
            _log_critical_configuration_change('security_settings', current_configs, new_configs)
            
            flash('Configuraciones de seguridad actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.security_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de seguridad: {str(e)}")
            flash('Error crítico al guardar configuraciones de seguridad.', 'error')
    
    return render_template('admin/settings/security.html', form=form, current_configs=current_configs)

# ============================================================================
# CONFIGURACIONES DE EMAIL
# ============================================================================

@admin_settings.route('/email', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_email_settings')
@handle_exceptions
def email_settings():
    """
    Configuraciones de email y notificaciones.
    """
    form = EmailSettingsForm()
    current_configs = _load_current_email_settings()
    
    if not form.is_submitted():
        _populate_email_settings_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            backup_current_config('email_settings')
            
            new_configs = {
                'email_provider': form.email_provider.data,
                'smtp_host': form.smtp_host.data.strip(),
                'smtp_port': form.smtp_port.data,
                'smtp_username': form.smtp_username.data.strip(),
                'smtp_password': encrypt_sensitive_data(form.smtp_password.data) if form.smtp_password.data else current_configs.get('smtp_password'),
                'smtp_use_tls': form.smtp_use_tls.data,
                'smtp_use_ssl': form.smtp_use_ssl.data,
                'default_from_email': form.default_from_email.data.lower().strip(),
                'default_from_name': form.default_from_name.data.strip(),
                'default_reply_to': form.default_reply_to.data.lower().strip() if form.default_reply_to.data else None,
                'email_rate_limit': form.email_rate_limit.data,
                'enable_email_tracking': form.enable_email_tracking.data,
                'email_templates_enabled': form.email_templates_enabled.data,
                'bounce_handling_enabled': form.bounce_handling_enabled.data,
                'unsubscribe_handling': form.unsubscribe_handling.data,
                'email_encryption': form.email_encryption.data,
                'dkim_enabled': form.dkim_enabled.data,
                'spf_enabled': form.spf_enabled.data
            }
            
            # Validar configuraciones de email
            validation_result = validate_email_config(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/email.html', form=form)
            
            # Probar conexión si se solicita
            if form.test_connection.data:
                test_result = _test_email_connection(new_configs)
                if not test_result['success']:
                    flash(f'Error de conexión: {test_result["message"]}', 'error')
                    return render_template('admin/settings/email.html', form=form)
                else:
                    flash('Conexión de email probada exitosamente.', 'success')
            
            # Guardar configuraciones
            _save_email_settings(new_configs)
            
            # Recargar servicio de email
            _reload_email_service(new_configs)
            
            _log_configuration_change('email_settings', current_configs, new_configs)
            
            flash('Configuraciones de email actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.email_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de email: {str(e)}")
            flash('Error al guardar configuraciones de email.', 'error')
    
    return render_template('admin/settings/email.html', form=form, current_configs=current_configs)

# ============================================================================
# CONFIGURACIONES DE INTEGRACIONES
# ============================================================================

@admin_settings.route('/integrations', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_integrations')
@handle_exceptions
def integration_settings():
    """
    Configuraciones de integraciones con servicios externos.
    """
    try:
        # Obtener integraciones existentes
        integrations = Integration.query.order_by(Integration.name).all()
        
        # Agrupar por categoría
        integrations_by_category = {}
        for integration in integrations:
            category = integration.category or 'other'
            if category not in integrations_by_category:
                integrations_by_category[category] = []
            integrations_by_category[category].append(integration)
        
        # Estado de integraciones
        integration_status = _get_integrations_status()
        
        return render_template(
            'admin/settings/integrations.html',
            integrations=integrations,
            integrations_by_category=integrations_by_category,
            integration_status=integration_status
        )
        
    except Exception as e:
        current_app.logger.error(f"Error cargando integraciones: {str(e)}")
        flash('Error al cargar las integraciones.', 'error')
        return redirect(url_for('admin_settings.dashboard'))

@admin_settings.route('/integrations/configure/<integration_name>', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('configure_integrations')
@handle_exceptions
def configure_integration(integration_name):
    """
    Configura una integración específica.
    """
    integration = Integration.query.filter_by(name=integration_name).first_or_404()
    form = IntegrationSettingsForm()
    
    # Personalizar formulario según tipo de integración
    _customize_integration_form(form, integration)
    
    if not form.is_submitted():
        _populate_integration_form(form, integration)
    
    if form.validate_on_submit():
        try:
            # Backup de configuración actual
            backup_current_config(f'integration_{integration.name}')
            
            # Preparar configuración
            config_data = _prepare_integration_config(form, integration)
            
            # Validar configuración específica
            validation_result = _validate_integration_config(integration, config_data)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/configure_integration.html', 
                                     form=form, integration=integration)
            
            # Probar conexión si se solicita
            if form.test_connection.data:
                test_result = _test_integration_connection(integration, config_data)
                if not test_result['success']:
                    flash(f'Error de conexión: {test_result["message"]}', 'error')
                    return render_template('admin/settings/configure_integration.html', 
                                         form=form, integration=integration)
            
            # Guardar configuración
            old_config = integration.configuration.copy() if integration.configuration else {}
            integration.configuration = config_data
            integration.is_enabled = form.is_enabled.data
            integration.last_configured_at = datetime.now(timezone.utc)
            integration.configured_by = current_user.id
            
            db.session.commit()
            
            # Aplicar configuración
            _apply_integration_config(integration)
            
            # Registrar cambio
            _log_configuration_change(f'integration_{integration.name}', old_config, config_data)
            
            flash(f'Integración {integration.display_name} configurada exitosamente.', 'success')
            return redirect(url_for('admin_settings.integration_settings'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error configurando integración {integration_name}: {str(e)}")
            flash('Error al guardar la configuración de integración.', 'error')
    
    return render_template('admin/settings/configure_integration.html', 
                         form=form, integration=integration)

# ============================================================================
# CONFIGURACIONES DE PERSONALIZACIÓN
# ============================================================================

@admin_settings.route('/personalization', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_personalization')
@handle_exceptions
def personalization_settings():
    """
    Configuraciones de personalización y branding.
    """
    form = PersonalizationSettingsForm()
    current_configs = _load_current_personalization_settings()
    
    if not form.is_submitted():
        _populate_personalization_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            backup_current_config('personalization_settings')
            
            new_configs = {
                'brand_name': form.brand_name.data.strip(),
                'brand_tagline': form.brand_tagline.data.strip() if form.brand_tagline.data else None,
                'primary_color': form.primary_color.data,
                'secondary_color': form.secondary_color.data,
                'accent_color': form.accent_color.data,
                'logo_url': form.logo_url.data.strip() if form.logo_url.data else None,
                'favicon_url': form.favicon_url.data.strip() if form.favicon_url.data else None,
                'custom_css': form.custom_css.data.strip() if form.custom_css.data else None,
                'custom_js': form.custom_js.data.strip() if form.custom_js.data else None,
                'footer_text': form.footer_text.data.strip() if form.footer_text.data else None,
                'social_media_links': {
                    'facebook': form.facebook_url.data.strip() if form.facebook_url.data else None,
                    'twitter': form.twitter_url.data.strip() if form.twitter_url.data else None,
                    'linkedin': form.linkedin_url.data.strip() if form.linkedin_url.data else None,
                    'instagram': form.instagram_url.data.strip() if form.instagram_url.data else None
                },
                'theme': form.theme.data,
                'enable_dark_mode': form.enable_dark_mode.data,
                'custom_fonts': form.custom_fonts.data.split(',') if form.custom_fonts.data else [],
                'show_powered_by': form.show_powered_by.data
            }
            
            # Procesar logo upload si hay uno
            if form.logo_file.data:
                logo_url = _upload_brand_asset(form.logo_file.data, 'logo')
                new_configs['logo_url'] = logo_url
            
            # Procesar favicon upload si hay uno
            if form.favicon_file.data:
                favicon_url = _upload_brand_asset(form.favicon_file.data, 'favicon')
                new_configs['favicon_url'] = favicon_url
            
            # Validar CSS y JS personalizado
            if new_configs['custom_css']:
                css_validation = _validate_custom_css(new_configs['custom_css'])
                if not css_validation['valid']:
                    flash(f'CSS inválido: {css_validation["message"]}', 'error')
                    return render_template('admin/settings/personalization.html', form=form)
            
            if new_configs['custom_js']:
                js_validation = _validate_custom_js(new_configs['custom_js'])
                if not js_validation['valid']:
                    flash(f'JavaScript inválido: {js_validation["message"]}', 'error')
                    return render_template('admin/settings/personalization.html', form=form)
            
            # Guardar configuraciones
            _save_personalization_settings(new_configs)
            
            # Invalidar cache de assets
            cache.delete('personalization_settings')
            cache.delete('brand_assets')
            
            # Compilar assets si es necesario
            _compile_custom_assets(new_configs)
            
            _log_configuration_change('personalization_settings', current_configs, new_configs)
            
            flash('Configuraciones de personalización actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.personalization_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de personalización: {str(e)}")
            flash('Error al guardar configuraciones de personalización.', 'error')
    
    return render_template('admin/settings/personalization.html', form=form, current_configs=current_configs)

# ============================================================================
# CONFIGURACIONES DE BACKUP Y MANTENIMIENTO
# ============================================================================

@admin_settings.route('/backup', methods=['GET', 'POST'])
@login_required
@super_admin_required
@handle_exceptions
def backup_settings():
    """
    Configuraciones de backup y mantenimiento del sistema.
    """
    form = BackupSettingsForm()
    current_configs = _load_current_backup_settings()
    
    # Estado de backups
    backup_status = _get_backup_status()
    
    if not form.is_submitted():
        _populate_backup_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            new_configs = {
                'auto_backup_enabled': form.auto_backup_enabled.data,
                'backup_frequency': form.backup_frequency.data,
                'backup_time': form.backup_time.data.strftime('%H:%M') if form.backup_time.data else '02:00',
                'backup_retention_days': form.backup_retention_days.data,
                'backup_storage_provider': form.backup_storage_provider.data,
                'backup_encryption_enabled': form.backup_encryption_enabled.data,
                'backup_compression': form.backup_compression.data,
                'include_user_data': form.include_user_data.data,
                'include_file_uploads': form.include_file_uploads.data,
                'include_system_logs': form.include_system_logs.data,
                'backup_notification_email': form.backup_notification_email.data.strip() if form.backup_notification_email.data else None,
                'maintenance_window_start': form.maintenance_window_start.data.strftime('%H:%M') if form.maintenance_window_start.data else '01:00',
                'maintenance_window_end': form.maintenance_window_end.data.strftime('%H:%M') if form.maintenance_window_end.data else '05:00',
                'auto_cleanup_enabled': form.auto_cleanup_enabled.data,
                'cleanup_temp_files_days': form.cleanup_temp_files_days.data,
                'cleanup_logs_days': form.cleanup_logs_days.data
            }
            
            # Validar configuraciones de backup
            validation_result = _validate_backup_settings(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/backup.html', form=form, backup_status=backup_status)
            
            # Guardar configuraciones
            _save_backup_settings(new_configs)
            
            # Programar backup automático si está habilitado
            if new_configs['auto_backup_enabled']:
                _schedule_automatic_backups(new_configs)
            else:
                _cancel_automatic_backups()
            
            _log_configuration_change('backup_settings', current_configs, new_configs)
            
            flash('Configuraciones de backup actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.backup_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de backup: {str(e)}")
            flash('Error al guardar configuraciones de backup.', 'error')
    
    return render_template('admin/settings/backup.html', form=form, 
                         current_configs=current_configs, backup_status=backup_status)

# ============================================================================
# CONFIGURACIONES DE PERFORMANCE
# ============================================================================

@admin_settings.route('/performance', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_performance_settings')
@handle_exceptions
def performance_settings():
    """
    Configuraciones de performance y optimización del sistema.
    """
    form = PerformanceSettingsForm()
    current_configs = _load_current_performance_settings()
    
    # Métricas de performance actuales
    performance_metrics = _get_current_performance_metrics()
    
    if not form.is_submitted():
        _populate_performance_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            new_configs = {
                'cache_enabled': form.cache_enabled.data,
                'cache_default_timeout': form.cache_default_timeout.data,
                'cache_type': form.cache_type.data,
                'redis_cache_enabled': form.redis_cache_enabled.data,
                'database_pool_size': form.database_pool_size.data,
                'database_pool_timeout': form.database_pool_timeout.data,
                'database_pool_recycle': form.database_pool_recycle.data,
                'query_timeout_seconds': form.query_timeout_seconds.data,
                'enable_query_logging': form.enable_query_logging.data,
                'slow_query_threshold': form.slow_query_threshold.data,
                'cdn_enabled': form.cdn_enabled.data,
                'cdn_provider': form.cdn_provider.data,
                'static_files_compression': form.static_files_compression.data,
                'image_optimization_enabled': form.image_optimization_enabled.data,
                'lazy_loading_enabled': form.lazy_loading_enabled.data,
                'async_task_workers': form.async_task_workers.data,
                'max_concurrent_requests': form.max_concurrent_requests.data,
                'request_timeout_seconds': form.request_timeout_seconds.data,
                'enable_gzip_compression': form.enable_gzip_compression.data,
                'minify_html': form.minify_html.data,
                'minify_css': form.minify_css.data,
                'minify_js': form.minify_js.data
            }
            
            # Validar configuraciones de performance
            validation_result = _validate_performance_settings(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/performance.html', form=form, performance_metrics=performance_metrics)
            
            # Aplicar configuraciones de cache
            if new_configs['cache_enabled'] != current_configs.get('cache_enabled'):
                _toggle_cache_system(new_configs['cache_enabled'])
            
            # Aplicar configuraciones de base de datos
            if new_configs['database_pool_size'] != current_configs.get('database_pool_size'):
                _update_database_pool_settings(new_configs)
            
            # Guardar configuraciones
            _save_performance_settings(new_configs)
            
            # Aplicar configuraciones inmediatamente
            _apply_performance_settings(new_configs)
            
            _log_configuration_change('performance_settings', current_configs, new_configs)
            
            flash('Configuraciones de performance actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.performance_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de performance: {str(e)}")
            flash('Error al guardar configuraciones de performance.', 'error')
    
    return render_template('admin/settings/performance.html', form=form, 
                         current_configs=current_configs, performance_metrics=performance_metrics)

# ============================================================================
# CONFIGURACIONES REGIONALES
# ============================================================================

@admin_settings.route('/regional', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_regional_settings')
@handle_exceptions
def regional_settings():
    """
    Configuraciones regionales e internacionalización.
    """
    form = RegionalSettingsForm()
    current_configs = _load_current_regional_settings()
    
    if not form.is_submitted():
        _populate_regional_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            new_configs = {
                'default_country': form.default_country.data,
                'default_currency': form.default_currency.data,
                'supported_currencies': form.supported_currencies.data,
                'currency_exchange_provider': form.currency_exchange_provider.data,
                'auto_detect_timezone': form.auto_detect_timezone.data,
                'supported_languages': form.supported_languages.data,
                'auto_detect_language': form.auto_detect_language.data,
                'date_format': form.date_format.data,
                'time_format': form.time_format.data,
                'number_format': form.number_format.data,
                'first_day_of_week': form.first_day_of_week.data,
                'enable_rtl_support': form.enable_rtl_support.data,
                'translation_service': form.translation_service.data,
                'auto_translation_enabled': form.auto_translation_enabled.data,
                'region_specific_features': form.region_specific_features.data,
                'gdpr_compliance_enabled': form.gdpr_compliance_enabled.data,
                'data_residency_region': form.data_residency_region.data
            }
            
            # Validar configuraciones regionales
            validation_result = _validate_regional_settings(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/regional.html', form=form)
            
            # Actualizar tasas de cambio si cambió el proveedor
            if new_configs['currency_exchange_provider'] != current_configs.get('currency_exchange_provider'):
                _update_currency_exchange_rates(new_configs['currency_exchange_provider'])
            
            # Guardar configuraciones
            _save_regional_settings(new_configs)
            
            # Aplicar configuraciones de localización
            _apply_localization_settings(new_configs)
            
            _log_configuration_change('regional_settings', current_configs, new_configs)
            
            flash('Configuraciones regionales actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.regional_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones regionales: {str(e)}")
            flash('Error al guardar configuraciones regionales.', 'error')
    
    return render_template('admin/settings/regional.html', form=form, current_configs=current_configs)

# ============================================================================
# CONFIGURACIONES DE API
# ============================================================================

@admin_settings.route('/api', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('manage_api_settings')
@handle_exceptions
def api_settings():
    """
    Configuraciones de API y webhooks.
    """
    form = APISettingsForm()
    current_configs = _load_current_api_settings()
    
    # Estado de APIs
    api_status = _get_api_status()
    
    if not form.is_submitted():
        _populate_api_form(form, current_configs)
    
    if form.validate_on_submit():
        try:
            new_configs = {
                'api_enabled': form.api_enabled.data,
                'api_version': form.api_version.data,
                'rate_limiting_enabled': form.rate_limiting_enabled.data,
                'default_rate_limit': form.default_rate_limit.data,
                'authenticated_rate_limit': form.authenticated_rate_limit.data,
                'api_key_expiry_days': form.api_key_expiry_days.data,
                'webhook_enabled': form.webhook_enabled.data,
                'webhook_secret': form.webhook_secret.data.strip() if form.webhook_secret.data else secrets.token_urlsafe(32),
                'webhook_timeout_seconds': form.webhook_timeout_seconds.data,
                'webhook_retry_attempts': form.webhook_retry_attempts.data,
                'cors_enabled': form.cors_enabled.data,
                'cors_origins': form.cors_origins.data.split('\n') if form.cors_origins.data else ['*'],
                'api_documentation_enabled': form.api_documentation_enabled.data,
                'api_playground_enabled': form.api_playground_enabled.data,
                'require_api_key': form.require_api_key.data,
                'log_api_requests': form.log_api_requests.data,
                'api_analytics_enabled': form.api_analytics_enabled.data,
                'deprecation_warnings': form.deprecation_warnings.data
            }
            
            # Validar configuraciones de API
            validation_result = _validate_api_settings(new_configs)
            if not validation_result['valid']:
                flash(f'Error de validación: {validation_result["message"]}', 'error')
                return render_template('admin/settings/api.html', form=form, api_status=api_status)
            
            # Guardar configuraciones
            _save_api_settings(new_configs)
            
            # Aplicar configuraciones de API
            _apply_api_settings(new_configs)
            
            # Regenerar documentación de API si está habilitada
            if new_configs['api_documentation_enabled']:
                _regenerate_api_documentation()
            
            _log_configuration_change('api_settings', current_configs, new_configs)
            
            flash('Configuraciones de API actualizadas exitosamente.', 'success')
            return redirect(url_for('admin_settings.api_settings'))
            
        except Exception as e:
            current_app.logger.error(f"Error guardando configuraciones de API: {str(e)}")
            flash('Error al guardar configuraciones de API.', 'error')
    
    return render_template('admin/settings/api.html', form=form, 
                         current_configs=current_configs, api_status=api_status)

# ============================================================================
# GESTIÓN DE CONFIGURACIONES
# ============================================================================

@admin_settings.route('/backup-config')
@login_required
@super_admin_required
@handle_exceptions
def backup_configuration():
    """
    Crea un backup completo de todas las configuraciones.
    """
    try:
        backup_service = BackupService()
        backup_file = backup_service.create_configuration_backup()
        
        _log_configuration_change('system_backup', {}, {'backup_created': backup_file})
        
        flash(f'Backup de configuraciones creado: {backup_file}', 'success')
        return redirect(url_for('admin_settings.dashboard'))
        
    except Exception as e:
        current_app.logger.error(f"Error creando backup de configuraciones: {str(e)}")
        flash('Error al crear backup de configuraciones.', 'error')
        return redirect(url_for('admin_settings.dashboard'))

@admin_settings.route('/restore-config', methods=['POST'])
@login_required
@super_admin_required
@handle_exceptions
def restore_configuration():
    """
    Restaura configuraciones desde un backup.
    """
    try:
        backup_file = request.form.get('backup_file')
        if not backup_file:
            flash('Debe especificar un archivo de backup.', 'error')
            return redirect(url_for('admin_settings.dashboard'))
        
        # Validar integridad del backup
        if not validate_config_integrity(backup_file):
            flash('El archivo de backup está corrupto o es inválido.', 'error')
            return redirect(url_for('admin_settings.dashboard'))
        
        # Crear backup actual antes de restaurar
        backup_current_config('pre_restore_backup')
        
        # Restaurar configuraciones
        restore_result = restore_config_backup(backup_file)
        
        if restore_result['success']:
            _log_configuration_change('system_restore', {}, {'backup_restored': backup_file})
            flash('Configuraciones restauradas exitosamente.', 'success')
        else:
            flash(f'Error restaurando configuraciones: {restore_result["message"]}', 'error')
        
        return redirect(url_for('admin_settings.dashboard'))
        
    except Exception as e:
        current_app.logger.error(f"Error restaurando configuraciones: {str(e)}")
        flash('Error crítico al restaurar configuraciones.', 'error')
        return redirect(url_for('admin_settings.dashboard'))

@admin_settings.route('/export-config')
@login_required
@admin_required
@permission_required('export_configurations')
@handle_exceptions
def export_configuration():
    """
    Exporta configuraciones en formato JSON.
    """
    try:
        export_data = export_config()
        
        response = make_response(jsonify(export_data))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=system_config_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        _log_configuration_change('config_export', {}, {'exported_by': current_user.email})
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error exportando configuraciones: {str(e)}")
        flash('Error al exportar configuraciones.', 'error')
        return redirect(url_for('admin_settings.dashboard'))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_settings.route('/api/system-status')
@login_required
@admin_required
@rate_limit(60, per_minute=True)
def api_system_status():
    """API para obtener estado del sistema en tiempo real."""
    try:
        status = _get_comprehensive_system_status()
        
        return jsonify({
            'success': True,
            'data': status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_settings.route('/api/test-integration/<integration_name>', methods=['POST'])
@login_required
@admin_required
@permission_required('test_integrations')
def api_test_integration(integration_name):
    """API para probar una integración específica."""
    try:
        integration = Integration.query.filter_by(name=integration_name).first_or_404()
        
        test_result = _test_integration_connection(integration, integration.configuration)
        
        return jsonify({
            'success': test_result['success'],
            'message': test_result['message'],
            'details': test_result.get('details', {})
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_settings.route('/api/performance-metrics')
@login_required
@admin_required
@rate_limit(30, per_minute=True)
def api_performance_metrics():
    """API para obtener métricas de performance."""
    try:
        metrics = _get_current_performance_metrics()
        
        return jsonify({
            'success': True,
            'data': metrics,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _get_system_status():
    """Obtiene el estado general del sistema."""
    return {
        'database': _check_database_health(),
        'cache': _check_cache_health(),
        'email': _check_email_service_health(),
        'storage': _check_storage_health(),
        'integrations': _check_integrations_health(),
        'security': _check_security_status(),
        'performance': _check_performance_status()
    }

def _get_critical_configurations_status():
    """Obtiene el estado de configuraciones críticas."""
    return {
        'security_configured': _is_security_properly_configured(),
        'email_configured': _is_email_properly_configured(),
        'backup_configured': _is_backup_properly_configured(),
        'ssl_configured': _is_ssl_properly_configured(),
        'monitoring_configured': _is_monitoring_properly_configured()
    }

def _get_active_integrations_status():
    """Obtiene el estado de integraciones activas."""
    integrations = Integration.query.filter_by(is_enabled=True).all()
    
    status = {}
    for integration in integrations:
        status[integration.name] = {
            'name': integration.display_name,
            'status': 'active' if integration.last_ping_success else 'error',
            'last_ping': integration.last_ping_at,
            'configuration_valid': bool(integration.configuration)
        }
    
    return status

def _get_configuration_alerts():
    """Obtiene alertas de configuración."""
    alerts = []
    
    # Check for missing critical configurations
    if not _is_email_properly_configured():
        alerts.append({
            'type': 'warning',
            'message': 'Configuración de email incompleta',
            'action': 'Configurar email'
        })
    
    if not _is_backup_properly_configured():
        alerts.append({
            'type': 'error',
            'message': 'Backup automático no configurado',
            'action': 'Configurar backup'
        })
    
    if not _is_ssl_properly_configured():
        alerts.append({
            'type': 'warning',
            'message': 'SSL/HTTPS no configurado adecuadamente',
            'action': 'Configurar SSL'
        })
    
    return alerts

def _get_configuration_usage_stats():
    """Obtiene estadísticas de uso de configuraciones."""
    return {
        'total_configurations': SystemConfiguration.query.count(),
        'last_change': ConfigurationHistory.query.order_by(desc(ConfigurationHistory.changed_at)).first(),
        'changes_this_month': ConfigurationHistory.query.filter(
            ConfigurationHistory.changed_at >= datetime.now(timezone.utc).replace(day=1)
        ).count(),
        'most_changed_section': _get_most_changed_configuration_section()
    }

def _run_configuration_health_checks():
    """Ejecuta health checks de configuraciones."""
    checks = {}
    
    # Database health
    checks['database'] = {
        'status': 'healthy' if _check_database_health() else 'unhealthy',
        'response_time': _measure_database_response_time()
    }
    
    # Cache health
    checks['cache'] = {
        'status': 'healthy' if _check_cache_health() else 'unhealthy',
        'hit_rate': _get_cache_hit_rate()
    }
    
    # Email service health
    checks['email'] = {
        'status': 'healthy' if _check_email_service_health() else 'unhealthy',
        'queue_size': _get_email_queue_size()
    }
    
    return checks

def _load_current_general_settings():
    """Carga configuraciones generales actuales."""
    config = SystemConfiguration.query.filter_by(section='general').first()
    return json.loads(config.configuration_data) if config else {}

def _populate_general_settings_form(form, configs):
    """Pobla el formulario con configuraciones actuales."""
    form.site_name.data = configs.get('site_name', '')
    form.site_description.data = configs.get('site_description', '')
    form.site_url.data = configs.get('site_url', '')
    form.admin_email.data = configs.get('admin_email', '')
    form.support_email.data = configs.get('support_email', '')
    form.maintenance_mode.data = configs.get('maintenance_mode', False)
    form.registration_enabled.data = configs.get('registration_enabled', True)
    form.email_verification_required.data = configs.get('email_verification_required', True)
    # ... continuar con otros campos

def _validate_general_settings(configs):
    """Valida configuraciones generales."""
    if not configs.get('site_name'):
        return {'valid': False, 'message': 'El nombre del sitio es requerido'}
    
    if not configs.get('admin_email'):
        return {'valid': False, 'message': 'El email del administrador es requerido'}
    
    if configs.get('max_file_upload_size', 0) > 100 * 1024 * 1024:  # 100MB
        return {'valid': False, 'message': 'El tamaño máximo de archivo no puede exceder 100MB'}
    
    return {'valid': True}

def _save_general_settings(configs):
    """Guarda configuraciones generales."""
    config = SystemConfiguration.query.filter_by(section='general').first()
    
    if not config:
        config = SystemConfiguration(
            section='general',
            configuration_data=json.dumps(configs),
            created_by=current_user.id
        )
        db.session.add(config)
    else:
        config.configuration_data = json.dumps(configs)
        config.updated_at = datetime.now(timezone.utc)
        config.updated_by = current_user.id
    
    db.session.commit()

def _log_configuration_change(section, old_config, new_config):
    """Registra cambio de configuración en el log."""
    changes = []
    
    # Identificar cambios específicos
    all_keys = set(old_config.keys()) | set(new_config.keys())
    
    for key in all_keys:
        old_value = old_config.get(key)
        new_value = new_config.get(key)
        
        if old_value != new_value:
            # Enmascarar datos sensibles
            if 'password' in key.lower() or 'secret' in key.lower() or 'key' in key.lower():
                old_value = '***' if old_value else None
                new_value = '***' if new_value else None
            
            changes.append({
                'field': key,
                'old_value': old_value,
                'new_value': new_value
            })
    
    if changes:
        history = ConfigurationHistory(
            section=section,
            changes=json.dumps(changes),
            changed_by=current_user.id,
            changed_at=datetime.now(timezone.utc),
            change_reason=f'Configuration update by {current_user.full_name}'
        )
        db.session.add(history)
        
        # Log de actividad
        activity = ActivityLog(
            user_id=current_user.id,
            action='update_configuration',
            resource_type='Configuration',
            resource_id=section,
            details=f'Updated {section} configuration: {len(changes)} changes'
        )
        db.session.add(activity)
        
        db.session.commit()

def _log_critical_configuration_change(section, old_config, new_config):
    """Registra cambio crítico de configuración con alertas."""
    _log_configuration_change(section, old_config, new_config)
    
    # Enviar alerta por email a super admins
    super_admins = User.query.join(User.admin).filter(
        User.admin.has(is_super_admin=True)
    ).all()
    
    for admin in super_admins:
        try:
            email_service = EmailService()
            email_service.send_critical_config_change_alert(admin, section, current_user)
        except Exception as e:
            current_app.logger.error(f"Error enviando alerta de configuración crítica: {str(e)}")

# Funciones auxiliares adicionales (simuladas para completar funcionalidad)
def _check_database_health():
    """Verifica salud de la base de datos."""
    try:
        db.session.execute('SELECT 1')
        return True
    except:
        return False

def _check_cache_health():
    """Verifica salud del cache."""
    try:
        cache.set('health_check', 'ok', timeout=1)
        return cache.get('health_check') == 'ok'
    except:
        return False

def _check_email_service_health():
    """Verifica salud del servicio de email."""
    try:
        email_service = EmailService()
        return email_service.test_connection()
    except:
        return False

def _check_storage_health():
    """Verifica salud del almacenamiento."""
    try:
        import shutil
        free_space = shutil.disk_usage('/').free
        return free_space > 1024 * 1024 * 1024  # 1GB libre mínimo
    except:
        return False

def _check_integrations_health():
    """Verifica salud de integraciones."""
    try:
        active_integrations = Integration.query.filter_by(is_enabled=True).count()
        failed_integrations = Integration.query.filter(
            and_(Integration.is_enabled == True, Integration.last_ping_success == False)
        ).count()
        
        return failed_integrations == 0
    except:
        return False

def _is_security_properly_configured():
    """Verifica si la seguridad está configurada adecuadamente."""
    security_config = _load_current_security_settings()
    
    required_settings = [
        'password_min_length',
        'max_login_attempts',
        'two_factor_required',
        'encryption_algorithm'
    ]
    
    return all(setting in security_config for setting in required_settings)

def _is_email_properly_configured():
    """Verifica si el email está configurado adecuadamente."""
    email_config = _load_current_email_settings()
    
    required_settings = ['smtp_host', 'smtp_port', 'smtp_username', 'default_from_email']
    return all(setting in email_config for setting in required_settings)

def _is_backup_properly_configured():
    """Verifica si el backup está configurado adecuadamente."""
    backup_config = _load_current_backup_settings()
    return backup_config.get('auto_backup_enabled', False)

def _is_ssl_properly_configured():
    """Verifica si SSL está configurado adecuadamente."""
    return current_app.config.get('PREFERRED_URL_SCHEME') == 'https'

def _is_monitoring_properly_configured():
    """Verifica si el monitoreo está configurado adecuadamente."""
    # Implementación simulada
    return True

def _get_most_changed_configuration_section():
    """Obtiene la sección de configuración más cambiada."""
    result = db.session.query(
        ConfigurationHistory.section,
        func.count(ConfigurationHistory.id).label('change_count')
    ).group_by(ConfigurationHistory.section).order_by(
        desc('change_count')
    ).first()
    
    return result.section if result else 'general'

def _measure_database_response_time():
    """Mide tiempo de respuesta de la base de datos."""
    import time
    start_time = time.time()
    try:
        db.session.execute('SELECT 1')
        return round((time.time() - start_time) * 1000, 2)  # ms
    except:
        return float('inf')

def _get_cache_hit_rate():
    """Obtiene tasa de aciertos del cache."""
    try:
        if hasattr(redis_client, 'info'):
            info = redis_client.info()
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            return (hits / total * 100) if total > 0 else 0
        return 0
    except:
        return 0

def _get_email_queue_size():
    """Obtiene tamaño de la cola de email."""
    # En un sistema real esto vendría del broker de tareas
    return 0

# Más funciones auxiliares se implementarían según necesidades específicas
def _load_current_security_settings():
    """Carga configuraciones de seguridad actuales."""
    config = SystemConfiguration.query.filter_by(section='security').first()
    return json.loads(config.configuration_data) if config else {}

def _load_current_email_settings():
    """Carga configuraciones de email actuales."""
    config = SystemConfiguration.query.filter_by(section='email').first()
    return json.loads(config.configuration_data) if config else {}

def _load_current_backup_settings():
    """Carga configuraciones de backup actuales."""
    config = SystemConfiguration.query.filter_by(section='backup').first()
    return json.loads(config.configuration_data) if config else {}

def _get_comprehensive_system_status():
    """Obtiene estado comprehensivo del sistema."""
    return {
        'system_health': _get_system_status(),
        'critical_configs': _get_critical_configurations_status(),
        'integrations': _get_active_integrations_status(),
        'performance': _get_current_performance_metrics(),
        'alerts': _get_configuration_alerts(),
        'uptime': _get_system_uptime(),
        'version': current_app.config.get('VERSION', '1.0.0'),
        'environment': current_app.config.get('ENV', 'production')
    }

def _get_current_performance_metrics():
    """Obtiene métricas actuales de performance."""
    return {
        'response_time': _measure_average_response_time(),
        'memory_usage': _get_memory_usage_percentage(),
        'cpu_usage': _get_cpu_usage_percentage(),
        'disk_usage': _get_disk_usage_percentage(),
        'cache_hit_rate': _get_cache_hit_rate(),
        'active_connections': _get_active_database_connections()
    }

def _get_system_uptime():
    """Obtiene uptime del sistema."""
    # Implementación simulada
    return "99.9% (30 days)"

def _measure_average_response_time():
    """Mide tiempo promedio de respuesta."""
    # Implementación simulada
    return 245  # ms

def _get_memory_usage_percentage():
    """Obtiene porcentaje de uso de memoria."""
    import psutil
    try:
        return psutil.virtual_memory().percent
    except:
        return 0

def _get_cpu_usage_percentage():
    """Obtiene porcentaje de uso de CPU."""
    import psutil
    try:
        return psutil.cpu_percent(interval=1)
    except:
        return 0

def _get_disk_usage_percentage():
    """Obtiene porcentaje de uso de disco."""
    import psutil
    try:
        return psutil.disk_usage('/').percent
    except:
        return 0

def _get_active_database_connections():
    """Obtiene número de conexiones activas a la base de datos."""
    try:
        result = db.session.execute("SELECT count(*) FROM pg_stat_activity").scalar()
        return result
    except:
        return 0