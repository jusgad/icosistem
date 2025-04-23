import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

class Config:
    """Configuración base para la aplicación"""
    # Configuración básica
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-por-defecto-cambiar-en-produccion'
    APP_NAME = 'Plataforma de Postpenados'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    
    # Configuración de base de datos
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    
    # Configuración de archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'}
    
    # Configuración de correo
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Configuración de seguridad
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT', 'sal-por-defecto-cambiar-en-produccion')
    SECURITY_PASSWORD_HASH = 'bcrypt'
    SECURITY_REGISTERABLE = True
    SECURITY_CONFIRMABLE = True
    SECURITY_RECOVERABLE = True
    SECURITY_CHANGEABLE = True
    
    # Configuración de CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora
    
    # Configuración de paginación
    ITEMS_PER_PAGE = 10
    
    # Configuración de Socket.IO
    SOCKETIO_PING_TIMEOUT = 10
    SOCKETIO_PING_INTERVAL = 25
    
    # Configuración de OAuth (para integración con servicios externos)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Configuración de moneda y localización
    DEFAULT_CURRENCY = 'COP'  # Peso colombiano
    DEFAULT_LANGUAGE = 'es'
    DEFAULT_TIMEZONE = 'America/Bogota'
    
    # Configuración de logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    
    @staticmethod
    def init_app(app):
        """Inicialización de la configuración"""
        # Crear carpetas necesarias si no existen
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo"""
    DEBUG = True
    TESTING = False
    
    # Conexión PostgreSQL para desarrollo
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://app_postpenados:contraseña_segura@localhost/proyecto_postpenados'
    
    # Activar echo de SQL para depuración
    SQLALCHEMY_ECHO = True
    
    # Configuración de correo para desarrollo (opcional)
    MAIL_SUPPRESS_SEND = True  # No enviar correos reales en desarrollo
    
    # Configuración para depuración
    DEBUG_TB_ENABLED = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False


class TestingConfig(Config):
    """Configuración para entorno de pruebas"""
    DEBUG = False
    TESTING = True
    
    # Conexión PostgreSQL para pruebas
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'postgresql://app_postpenados:contraseña_segura@localhost/proyecto_postpenados_test'
    
    # Desactivar CSRF para pruebas
    WTF_CSRF_ENABLED = False
    
    # No enviar correos en pruebas
    MAIL_SUPPRESS_SEND = True
    
    # Configuración para pruebas más rápidas
    BCRYPT_LOG_ROUNDS = 4  # Menos rondas para hashing de contraseñas en pruebas
    
    # Carpeta de uploads para pruebas
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../tests/uploads')


class ProductionConfig(Config):
    """Configuración para entorno de producción"""
    DEBUG = False
    TESTING = False
    
    # Conexión PostgreSQL para producción
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_postpenados:contraseña_segura@localhost/proyecto_postpenados'
    
    # Deshabilitar ECHO de SQL en producción por rendimiento
    SQLALCHEMY_ECHO = False
    
    # Configuración de seguridad para producción
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Configuración de SSL
    SSL_REDIRECT = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Configuración de logs para producción
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        file_handler = RotatingFileHandler('logs/postpenados.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Postpenados startup')
        
        # Configuración para proxy
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)


class DockerConfig(ProductionConfig):
    """Configuración específica para despliegue con Docker"""
    
    # Conexión PostgreSQL para Docker (generalmente usa el nombre del servicio como host)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_postpenados:contraseña_segura@postgres/proyecto_postpenados'
    
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)
        
        # Configuración específica para Docker
        # Asegurar que los logs vayan a stdout/stderr
        import logging
        from logging import StreamHandler
        
        # Eliminar handlers existentes
        del app.logger.handlers[:]
        
        # Agregar handler para stdout
        stream_handler = StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)


# Diccionario de configuraciones disponibles
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}