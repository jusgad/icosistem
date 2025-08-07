"""
Ally views package.
"""

from flask import Blueprint, render_template

# Crear el blueprint de aliados
ally_bp = Blueprint('ally', __name__, url_prefix='/ally')

@ally_bp.route('/')
def dashboard():
    """Dashboard de aliado."""
    return render_template('ally/dashboard.html')

@ally_bp.route('/entrepreneurs')
def entrepreneurs():
    """Emprendedores asignados."""
    return render_template('ally/entrepreneurs.html')

@ally_bp.route('/mentorship')
def mentorship():
    """Sesiones de mentoría."""
    return render_template('ally/mentorship.html')

@ally_bp.route('/calendar')
def calendar():
    """Calendario."""
    return render_template('ally/calendar.html')

@ally_bp.route('/reports')
def reports():
    """Reportes."""
    return render_template('ally/reports.html')

@ally_bp.route('/profile')
def profile():
    """Perfil."""
    return render_template('ally/profile.html')