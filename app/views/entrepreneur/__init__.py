from flask import Blueprint

# Importar los diferentes módulos de vistas para emprendedores
from app.views.entrepreneur.dashboard import *
from app.views.entrepreneur.profile import *
from app.views.entrepreneur.messages import *
from app.views.entrepreneur.calendar import *
from app.views.entrepreneur.desktop import *
from app.views.entrepreneur.documents import *
from app.views.entrepreneur.tasks import *

# Crear el Blueprint principal para las vistas de emprendedor
entrepreneur = Blueprint('entrepreneur', __name__, url_prefix='/entrepreneur')

# Registrar los sub-blueprints dentro del blueprint principal de emprendedor
entrepreneur.register_blueprint(entrepreneur_dashboard)
entrepreneur.register_blueprint(entrepreneur_profile)
entrepreneur.register_blueprint(entrepreneur_messages)
entrepreneur.register_blueprint(entrepreneur_calendar)
entrepreneur.register_blueprint(entrepreneur_desktop)
entrepreneur.register_blueprint(entrepreneur_documents)
entrepreneur.register_blueprint(entrepreneur_tasks)

# Definir la función para registrar este blueprint en la aplicación principal
def register_entrepreneur_blueprint(app):
    app.register_blueprint(entrepreneur)