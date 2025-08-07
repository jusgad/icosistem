"""
Admin views package.
"""

from flask import Blueprint, render_template

# Crear el blueprint principal de admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
def dashboard():
    """Dashboard principal de admin.""" 
    return render_template('admin/dashboard.html')

@admin_bp.route('/users')
def users():
    """Gestión de usuarios."""
    return render_template('admin/users.html')

@admin_bp.route('/entrepreneurs') 
def entrepreneurs():
    """Gestión de emprendedores."""
    return render_template('admin/entrepreneurs.html')

@admin_bp.route('/allies')
def allies():
    """Gestión de aliados."""
    return render_template('admin/allies.html')

@admin_bp.route('/analytics')
def analytics():
    """Análisis y métricas."""
    return render_template('admin/analytics.html')

@admin_bp.route('/organizations')
def organizations():
    """Gestión de organizaciones."""
    return render_template('admin/organizations.html')

@admin_bp.route('/programs')
def programs():
    """Gestión de programas."""
    return render_template('admin/programs.html')

@admin_bp.route('/settings')
def settings():
    """Configuraciones del sistema."""
    return render_template('admin/settings.html')