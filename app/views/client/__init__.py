"""
Client views package.
"""

from flask import Blueprint, render_template

# Crear el blueprint de clientes
client_bp = Blueprint('client', __name__, url_prefix='/client')

@client_bp.route('/')
def dashboard():
    """Dashboard de cliente."""
    return render_template('client/dashboard.html')

@client_bp.route('/directory')
def directory():
    """Directorio de emprendedores."""
    return render_template('client/directory.html')

@client_bp.route('/analytics')
def analytics():
    """Análisis."""
    return render_template('client/analytics.html')

@client_bp.route('/reports')
def reports():
    """Reportes."""
    return render_template('client/reports.html')

@client_bp.route('/impact')
def impact():
    """Impacto."""
    return render_template('client/impact.html')