from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.config import Config
from app.forms.admin import GlobalSettingsForm
from app.utils.decorators import admin_required

# Creación del Blueprint
admin_settings = Blueprint('admin_settings', __name__)

@admin_settings.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def global_settings():
    """Vista para gestionar la configuración global de la aplicación"""
    # Obtener configuración actual o crear una nueva si no existe
    config = Config.query.first()
    if not config:
        config = Config()
        db.session.add(config)
        db.session.commit()
    
    form = GlobalSettingsForm(obj=config)
    
    if form.validate_on_submit():
        # Actualizar la configuración global
        config.site_name = form.site_name.data
        config.contact_email = form.contact_email.data
        config.max_file_size = form.max_file_size.data
        config.allow_registration = form.allow_registration.data
        config.default_entrepreneur_hours = form.default_entrepreneur_hours.data
        config.enable_chat = form.enable_chat.data
        config.maintenance_mode = form.maintenance_mode.data
        config.maintenance_message = form.maintenance_message.data
        config.footer_text = form.footer_text.data
        
        # Configuración de notificaciones
        config.email_notifications = form.email_notifications.data
        config.push_notifications = form.push_notifications.data
        
        # Configuración de integración
        config.google_calendar_enabled = form.google_calendar_enabled.data
        config.google_meet_enabled = form.google_meet_enabled.data
        config.enable_analytics = form.enable_analytics.data
        
        # Configuración de visualización
        config.primary_color = form.primary_color.data
        config.secondary_color = form.secondary_color.data
        config.logo_url = form.logo_url.data
        
        db.session.commit()
        flash('Configuración actualizada exitosamente', 'success')
        return redirect(url_for('admin_settings.global_settings'))
    
    return render_template('admin/settings.html', form=form, config=config)

@admin_settings.route('/admin/settings/reset', methods=['POST'])
@login_required
@admin_required
def reset_settings():
    """Restaurar la configuración a los valores predeterminados"""
    config = Config.query.first()
    if config:
        # Establecer valores predeterminados
        config.site_name = "Plataforma de Emprendimiento"
        config.contact_email = "contacto@emprendimiento-app.com"
        config.max_file_size = 10 # MB
        config.allow_registration = True
        config.default_entrepreneur_hours = 20
        config.enable_chat = True
        config.maintenance_mode = False
        config.maintenance_message = "Sistema en mantenimiento. Intente nuevamente más tarde."
        config.footer_text = "© 2025 Emprendimiento App - Todos los derechos reservados"
        config.email_notifications = True
        config.push_notifications = False
        config.google_calendar_enabled = False
        config.google_meet_enabled = False
        config.enable_analytics = True
        config.primary_color = "#3498db"
        config.secondary_color = "#2ecc71"
        config.logo_url = "/static/images/logo.png"
        
        db.session.commit()
        flash('Configuración restaurada a valores predeterminados', 'success')
    
    return redirect(url_for('admin_settings.global_settings'))

@admin_settings.route('/admin/settings/backup', methods=['GET'])
@login_required
@admin_required
def backup_settings():
    """Generar un archivo de respaldo de la configuración actual"""
    from app.utils.formatters import generate_config_json
    
    config = Config.query.first()
    if not config:
        flash('No hay configuración para respaldar', 'warning')
        return redirect(url_for('admin_settings.global_settings'))
    
    # Genera un archivo JSON con la configuración actual
    config_json = generate_config_json(config)
    
    # Configurar respuesta para descarga de archivo
    from flask import Response
    import json
    from datetime import datetime
    
    filename = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        json.dumps(config_json, indent=4),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@admin_settings.route('/admin/settings/restore', methods=['POST'])
@login_required
@admin_required
def restore_settings():
    """Restaurar la configuración desde un archivo de respaldo"""
    from app.utils.formatters import restore_config_from_json
    
    if 'config_file' not in request.files:
        flash('No se proporcionó ningún archivo', 'error')
        return redirect(url_for('admin_settings.global_settings'))
    
    file = request.files['config_file']
    if file.filename == '':
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('admin_settings.global_settings'))
    
    try:
        import json
        config_data = json.loads(file.read().decode('utf-8'))
        
        config = Config.query.first()
        if not config:
            config = Config()
            db.session.add(config)
        
        # Restaurar configuración desde el archivo
        restore_config_from_json(config, config_data)
        db.session.commit()
        
        flash('Configuración restaurada exitosamente desde el archivo de respaldo', 'success')
    except Exception as e:
        flash(f'Error al restaurar la configuración: {str(e)}', 'error')
    
    return redirect(url_for('admin_settings.global_settings'))