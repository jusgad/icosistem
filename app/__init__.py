"""
Factory pattern para la aplicación del ecosistema de emprendimiento.
Este módulo centraliza la creación y configuración de la aplicación Flask.
"""

import os
from flask import Flask
from flask_migrate import Migrate

# Importar extensiones
from .extensions import (
    db, ma, login_manager, mail, socketio, cors, limiter,
    jwt, cache, babel, session, oauth, compress, talisman,
    init_all_extensions
)

# Importar configuraciones
from config import config

# Importar comandos CLI
# from .commands import register_commands  # Comentado temporalmente

# Importar blueprints
from .views.main import main_bp
from .views.auth import auth_bp
from .views.errors import errors_bp
from .views.admin import admin_bp
from .views.entrepreneur import entrepreneur_bp
from .views.ally import ally_bp
from .views.client import client_bp

# Importar API blueprints
from .api.v1 import api_v1_bp

# Importar manejadores de errores
from .core.exceptions import register_error_handlers

# Importar context processors
from .utils.formatters import register_template_filters
from .core.context_processors import register_context_processors

# Importar middleware (simplificado)
try:
    from .api.middleware.auth import AuthMiddleware
except ImportError:
    AuthMiddleware = None
try:
    from .api.middleware.cors import setup_cors
except ImportError:
    def setup_cors(app):
        pass
try:
    from .api.middleware.rate_limiting import setup_rate_limiting
except ImportError:
    def setup_rate_limiting(app):
        pass

# Importar eventos de WebSocket
from .sockets import register_socketio_events


def create_app(config_name=None):
    """
    Factory function para crear la aplicación Flask.
    
    Args:
        config_name (str): Nombre de la configuración a usar.
                          Si es None, usa la variable de entorno FLASK_ENV.
    
    Returns:
        Flask: Instancia de la aplicación configurada.
    """
    
    # Crear instancia de Flask
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder='static/dist',
                static_url_path='/static')
    
    # Determinar configuración
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Cargar configuración
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Inicializar extensiones
    init_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Blueprints will handle all routes
    
    # Registrar comandos CLI
    # register_commands(app)  # Comentado temporalmente para evitar errores de tabla duplicada
    
    # Registrar manejadores de errores
    register_error_handlers(app)
    
    # Registrar filtros de templates
    register_template_filters(app)
    
    # Registrar context processors
    register_context_processors(app)
    
    # Configurar middleware
    setup_middleware(app)
    
    # Registrar eventos de WebSocket
    register_socketio_events(socketio)
    
    # Configurar logging
    setup_logging(app)
    
    # Crear directorio de uploads si no existe
    setup_upload_directory(app)
    
    return app


def init_extensions(app):
    """
    Inicializa todas las extensiones de Flask usando el método centralizado.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    # Usar la función centralizada de extensions.py
    init_all_extensions(app)
    
    # Migración de base de datos (se inicializa aquí para mantener la referencia)
    migrate = Migrate(app, db)


def register_blueprints(app):
    """
    Registra todos los blueprints de la aplicación.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    
    # Blueprints principales
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(errors_bp)
    
    # Blueprints por roles
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(entrepreneur_bp, url_prefix='/entrepreneur')
    app.register_blueprint(ally_bp, url_prefix='/ally')
    app.register_blueprint(client_bp, url_prefix='/client')
    
    # API blueprints
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')


def setup_middleware(app):
    """
    Configura middleware personalizado para la aplicación.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    
    # Configurar CORS adicional
    setup_cors(app)
    
    # Configurar rate limiting adicional
    setup_rate_limiting(app)
    
    # Middleware de autenticación para API
    if AuthMiddleware:
        app.wsgi_app = AuthMiddleware(app.wsgi_app)


def setup_logging(app):
    """
    Configura el sistema de logging de la aplicación.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    
    if not app.debug and not app.testing:
        import logging
        from logging.handlers import RotatingFileHandler
        try:
            from config.logging import setup_logging_config
            # Configurar logging personalizado
            setup_logging_config(app)
        except ImportError:
            pass
        
        # Handler para archivos
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        file_handler = RotatingFileHandler(
            'logs/ecosistema_emprendimiento.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Ecosistema de Emprendimiento startup')


def setup_upload_directory(app):
    """
    Crea el directorio de uploads si no existe.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        
        # Crear subdirectorios
        subdirs = ['documents', 'images', 'profiles', 'temp']
        for subdir in subdirs:
            os.makedirs(os.path.join(upload_folder, subdir), exist_ok=True)


# El user_loader se configura ahora en extensions.py para evitar imports circulares


# Babel locale selector already configured in init_extensions()


def create_celery_app(app=None):
    """
    Factory function para crear la aplicación Celery.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    
    Returns:
        Celery: Instancia de Celery configurada.
    """
    from .tasks.celery_app import make_celery
    
    app = app or create_app()
    return make_celery(app)


# Función de conveniencia para crear la app en desarrollo
def create_dev_app():
    """
    Función de conveniencia para crear la app en modo desarrollo.
    
    Returns:
        Flask: Instancia de la aplicación en modo desarrollo.
    """
    return create_app('development')


# Función de conveniencia para crear la app en producción
def create_prod_app():
    """
    Función de conveniencia para crear la app en modo producción.
    
    Returns:
        Flask: Instancia de la aplicación en modo producción.
    """
    return create_app('production')


# Función de conveniencia para crear la app de testing
def create_test_app():
    """
    Función de conveniencia para crear la app en modo testing.
    
    Returns:
        Flask: Instancia de la aplicación en modo testing.
    """
    return create_app('testing')


# Exportar funciones principales
__all__ = [
    'create_app',
    'create_celery_app', 
    'create_dev_app',
    'create_prod_app',
    'create_test_app'
]