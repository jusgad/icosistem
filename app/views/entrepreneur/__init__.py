"""
Entrepreneur views package.
"""

from flask import Blueprint, render_template

# Crear el blueprint de emprendedores
entrepreneur_bp = Blueprint('entrepreneur', __name__, url_prefix='/entrepreneur')

@entrepreneur_bp.route('/')
def dashboard():
    """Dashboard de emprendedor."""
    return render_template('entrepreneur/dashboard.html')

@entrepreneur_bp.route('/projects')
def projects():
    """Mis proyectos."""
    return render_template('entrepreneur/projects.html')

@entrepreneur_bp.route('/mentorship')
def mentorship():
    """Mentoría."""
    return render_template('entrepreneur/mentorship.html')

@entrepreneur_bp.route('/calendar')
def calendar():
    """Calendario."""
    return render_template('entrepreneur/calendar.html')

@entrepreneur_bp.route('/documents')
def documents():
    """Documentos."""
    return render_template('entrepreneur/documents.html')

@entrepreneur_bp.route('/profile')
def profile():
    """Perfil."""
    return render_template('entrepreneur/profile.html')