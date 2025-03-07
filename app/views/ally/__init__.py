# app/views/ally/__init__.py
from flask import Blueprint

# Crear el Blueprint para las vistas del aliado
ally_bp = Blueprint('ally', __name__, url_prefix='/ally')

# Importar las vistas después de crear el Blueprint para evitar
# importaciones circulares
from app.views.ally import dashboard, profile, entrepreneurs, hours, messages, calendar, desktop

# Registrar todas las rutas disponibles para aliados
# Esto podría incluir una página de inicio específica para aliados
@ally_bp.route('/')
def index():
    return dashboard.index()

# Definir variables que se pueden compartir en todas las plantillas del blueprint
@ally_bp.context_processor
def inject_ally_context():
    return {}