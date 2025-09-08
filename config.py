import os
import secrets
from datetime import timedelta

class Config:
    """Clase base de configuración con valores compartidos entre entornos."""
    
    # Configuración general
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    APP_NAME = 'Plataforma de Emprendimiento'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@emprendimiento-app.com'
    
    # Configuración de la base de datos
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de Flask-JWT-Extended
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_urlsafe(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Configuración de subida de archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'jpeg'}
    
    # Configuración de correo electrónico
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@emprendimiento-app.com'
    
    # Configuración de Socket.IO
    SOCKETIO_ASYNC_MODE = 'eventlet'
    
    # Configuración de Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    # Configuración de paginación
    ITEMS_PER_PAGE = 10
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    
    # Configuración de Flask-Admin
    FLASK_ADMIN_SWATCH = 'cerulean'
    
    # Métricas por defecto para medición de impacto
    DEFAULT_IMPACT_METRICS = [
        'jobs_created',
        'revenue_increase',
        'funding_secured',
        'market_expansion',
        'innovation_index'
    ]
    
    @staticmethod
    def init_app(app):
        """Inicialización de configuración para la aplicación."""
        pass


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dev.db')
    
    # Configuración para depuración de correos
    MAIL_DEBUG = True
    
    # Configuración para depuración de SQLAlchemy
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    """Configuración para entorno de pruebas."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite://'
    
    # Desactivar protección CSRF para facilitar las pruebas
    WTF_CSRF_ENABLED = False
    
    # Configuración de correo para pruebas
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    """Configuración para entorno de producción."""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Configuraciones de seguridad adicionales
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # Configuración de headers de seguridad
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
    }
    
    # Configuración de rate limiting
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Configuración de registros para producción
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('logs/emprendimiento-app.log',
                                          maxBytes=10*1024*1024,
                                          backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Configurar manejadores de error en producción
        from flask import render_template
        
        @app.errorhandler(500)
        def internal_server_error(e):
            app.logger.error(f'Error del servidor: {e}')
            return render_template('error/500.html'), 500


class DockerConfig(ProductionConfig):
    """Configuración específica para despliegue con Docker."""
    
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)
        
        # Configuración específica para Docker
        # Configurar proxy si es necesario
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# Mapeo de nombres de configuración a clases
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}