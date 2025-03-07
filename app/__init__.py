from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail

from app.extensions import db
from app.config import config_dict

# Inicialización de extensiones
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()
csrf = CSRFProtect()
mail = Mail()

def create_app(config_name='default'):
    """
    Función factory para crear la aplicación Flask
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Cargar configuración
    app.config.from_object(config_dict[config_name])
    app.config.from_pyfile('config.py', silent=True)
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    socketio.init_app(app, cors_allowed_origins="*")
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    
    # Registrar blueprints
    from app.views.main import main_bp
    from app.views.auth import auth_bp
    
    # Admin blueprints
    from app.views.admin import admin_bp
    from app.views.admin.users import users_bp
    from app.views.admin.entrepreneurs import entrepreneurs_bp
    from app.views.admin.allies import allies_bp
    from app.views.admin.settings import settings_bp
    
    # Entrepreneur blueprints
    from app.views.entrepreneur import entrepreneur_bp
    
    # Ally blueprints
    from app.views.ally import ally_bp
    
    # Client blueprints
    from app.views.client import client_bp
    
    # Registrar blueprints principales
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Registrar blueprints de admin
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(users_bp, url_prefix='/admin/users')
    app.register_blueprint(entrepreneurs_bp, url_prefix='/admin/entrepreneurs')
    app.register_blueprint(allies_bp, url_prefix='/admin/allies')
    app.register_blueprint(settings_bp, url_prefix='/admin/settings')
    
    # Registrar blueprints de emprendedor
    app.register_blueprint(entrepreneur_bp, url_prefix='/entrepreneur')
    
    # Registrar blueprints de aliado
    app.register_blueprint(ally_bp, url_prefix='/ally')
    
    # Registrar blueprints de cliente
    app.register_blueprint(client_bp, url_prefix='/client')
    
    # Configurar manejadores de errores
    from app.views.errors import register_error_handlers
    register_error_handlers(app)
    
    # Registrar comandos CLI
    from app.commands import register_commands
    register_commands(app)
    
    # Configurar sockets
    from app.sockets import register_socket_events
    register_socket_events(socketio)
    
    # Configurar modelo de usuario para Flask-Login
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Configurar filtros personalizados para Jinja2
    from app.utils.formatters import register_template_filters
    register_template_filters(app)
    
    # Configurar variables globales para plantillas
    @app.context_processor
    def inject_global_vars():
        return {
            'app_name': app.config['APP_NAME'],
            'current_year': __import__('datetime').datetime.now().year
        }
    
    return app