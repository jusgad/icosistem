"""
Configuraciones por ambiente para el ecosistema de emprendimiento.
Este módulo define las configuraciones base y específicas para cada ambiente.
"""

import os
import secrets
from datetime import timedelta
from urllib.parse import quote_plus
from pathlib import Path


# Directorio base del proyecto
basedir = Path(__file__).parent.parent.absolute()


class Config:
    """Configuración base compartida por todos los ambientes."""
    
    # === CONFIGURACIÓN BÁSICA ===
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    FLASK_APP = os.environ.get('FLASK_APP') or 'run.py'
    
    # === BASE DE DATOS ===
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # === SEGURIDAD ===
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    BCRYPT_LOG_ROUNDS = 12
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    
    # === SESIONES ===
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'ecosist_emp:'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # === EMAIL ===
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_MAX_EMAILS = 50
    MAIL_SUPPRESS_SEND = False
    
    # Plantillas de email
    MAIL_TEMPLATES = {
        'welcome': 'emails/welcome.html',
        'password_reset': 'emails/password_reset.html',
        'email_verification': 'emails/email_verification.html',
        'meeting_reminder': 'emails/meeting_reminder.html',
        'task_reminder': 'emails/task_reminder.html',
        'monthly_report': 'emails/monthly_report.html'
    }
    
    # === FILE UPLOADS ===
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {
        'images': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
        'spreadsheets': {'xls', 'xlsx', 'csv'},
        'presentations': {'ppt', 'pptx'},
        'archives': {'zip', 'rar', '7z'}
    }
    
    # === PAGINACIÓN ===
    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100
    
    # === CACHE ===
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # === RATE LIMITING ===
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    # Límites específicos
    RATE_LIMITS = {
        'login': '5 per minute',
        'register': '3 per minute',
        'password_reset': '3 per hour',
        'api_general': '1000 per hour',
        'file_upload': '10 per minute',
        'email_send': '20 per hour'
    }
    
    # === INTERNACIONALIZACIÓN ===
    LANGUAGES = {
        'es': 'Español',
        'en': 'English'
    }
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_DEFAULT_TIMEZONE = 'America/Bogota'
    
    # === INTEGRACIONES EXTERNAS ===
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Google Calendar & Meet
    GOOGLE_CALENDAR_CREDENTIALS = os.environ.get('GOOGLE_CALENDAR_CREDENTIALS')
    GOOGLE_MEET_ENABLED = os.environ.get('GOOGLE_MEET_ENABLED', 'true').lower() == 'true'
    
    # Microsoft OAuth (opcional)
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
    
    # SMS Service (Twilio)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
    
    # === WEBSOCKETS ===
    SOCKETIO_LOGGER = False
    ENGINEIO_LOGGER = False
    SOCKETIO_ASYNC_MODE = 'threading'
    
    # === CELERY (Tareas Asíncronas) ===
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'America/Bogota'
    CELERY_ENABLE_UTC = True
    
    # Configuración de tareas programadas
    CELERYBEAT_SCHEDULE = {
        'send-daily-reminders': {
            'task': 'app.tasks.notification_tasks.send_daily_reminders',
            'schedule': 3600.0,  # cada hora
        },
        'generate-analytics': {
            'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
            'schedule': 86400.0,  # diario
        },
        'cleanup-temp-files': {
            'task': 'app.tasks.maintenance_tasks.cleanup_temp_files',
            'schedule': 7200.0,  # cada 2 horas
        }
    }
    
    # === MONITOREO Y LOGGING ===
    LOG_LEVEL = 'INFO'
    LOG_FILE = os.path.join(basedir, 'logs', 'app.log')
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # === SEGURIDAD AVANZADA ===
    ENABLE_SECURITY_HEADERS = True
    TALISMAN_CONFIG = {
        'force_https': False,
        'strict_transport_security': True,
        'strict_transport_security_max_age': 31536000,
        'content_security_policy': {
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline' 'unsafe-eval' *.googleapis.com *.gstatic.com",
            'style-src': "'self' 'unsafe-inline' *.googleapis.com",
            'img-src': "'self' data: *.googleapis.com",
            'font-src': "'self' *.gstatic.com",
            'connect-src': "'self' *.googleapis.com"
        }
    }
    
    # === BUSINESS LOGIC ===
    
    # Configuración de roles
    DEFAULT_ROLES = {
        'admin': 'Administrador',
        'entrepreneur': 'Emprendedor',
        'ally': 'Aliado/Mentor',
        'client': 'Cliente/Stakeholder'
    }
    
    # Estados de proyectos
    PROJECT_STATUSES = {
        'idea': 'Idea',
        'validation': 'Validación',
        'development': 'Desarrollo',
        'launch': 'Lanzamiento',
        'growth': 'Crecimiento',
        'scale': 'Escalamiento',
        'exit': 'Salida'
    }
    
    # Configuración de mentoría
    MENTORSHIP_CONFIG = {
        'max_sessions_per_month': 8,
        'session_duration_minutes': 60,
        'reminder_hours_before': 24,
        'max_entrepreneurs_per_ally': 10
    }
    
    # === APIS Y WEBHOOKS ===
    API_VERSION = 'v1'
    API_TITLE = 'Ecosistema de Emprendimiento API'
    API_DESCRIPTION = 'API para gestión del ecosistema de emprendimiento'
    
    # Webhooks permitidos
    ALLOWED_WEBHOOK_ORIGINS = os.environ.get('ALLOWED_WEBHOOK_ORIGINS', '').split(',')
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET') or secrets.token_urlsafe(32)
    
    # === MÉTRICAS Y ANALYTICS ===
    ANALYTICS_ENABLED = True
    ANALYTICS_RETENTION_DAYS = 365
    
    # KPIs del ecosistema
    KPI_CONFIG = {
        'entrepreneur_engagement_threshold': 0.7,
        'project_success_metrics': ['revenue', 'users', 'funding'],
        'mentor_effectiveness_metrics': ['session_rating', 'entrepreneur_progress']
    }
    
    @staticmethod
    def init_app(app):
        """Inicialización base para todas las configuraciones."""
        
        # Crear directorios necesarios
        os.makedirs('logs', exist_ok=True)
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        
        # Validar configuraciones críticas
        if not app.config.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY no está configurada")
        
        if not app.config.get('MAIL_USERNAME') and not app.debug:
            app.logger.warning("MAIL_USERNAME no está configurado")


class DevelopmentConfig(Config):
    """Configuración para ambiente de desarrollo."""
    
    DEBUG = True
    TESTING = False
    
    # Base de datos local
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "ecosistema_dev.db")}'
    
    # Cache simple para desarrollo
    CACHE_TYPE = 'simple'
    
    # Logging más verboso
    LOG_LEVEL = 'DEBUG'
    
    # Deshabilitar rate limiting en desarrollo
    RATELIMIT_ENABLED = False
    
    # Email: usar consola en desarrollo
    MAIL_SUPPRESS_SEND = True
    MAIL_DEBUG = True
    
    # Seguridad relajada para desarrollo
    WTF_CSRF_ENABLED = False
    ENABLE_SECURITY_HEADERS = False
    
    # WebSockets con logging
    SOCKETIO_LOGGER = True
    ENGINEIO_LOGGER = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Configurar logging para desarrollo
        import logging
        logging.basicConfig(level=logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)


class TestingConfig(Config):
    """Configuración para testing."""
    
    TESTING = True
    DEBUG = False
    
    # Base de datos en memoria para tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Deshabilitar protecciones para tests
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True
    MAIL_SUPPRESS_SEND = True
    
    # Cache deshabilitado
    CACHE_TYPE = 'null'
    
    # Sin rate limiting en tests
    RATELIMIT_ENABLED = False
    
    # Celery síncrono para tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)


class ProductionConfig(Config):
    """Configuración para producción."""
    
    DEBUG = False
    TESTING = False
    
    # Base de datos PostgreSQL para producción
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://usuario:password@localhost/ecosistema_emprendimiento'
    
    # Si es Heroku, ajustar la URL
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    # Cache Redis para producción
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/1'
    
    # Rate limiting con Redis
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/2'
    
    # Configuración optimizada de base de datos
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }
    
    # Logging a archivo
    LOG_LEVEL = 'WARNING'
    
    # Seguridad máxima
    TALISMAN_CONFIG = {
        'force_https': True,
        'strict_transport_security': True,
        'strict_transport_security_max_age': 31536000,
        'content_security_policy': {
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline' https:",
            'style-src': "'self' 'unsafe-inline' https:",
            'img-src': "'self' data: https:",
            'connect-src': "'self' https:",
            'font-src': "'self' https:",
            'object-src': "'none'",
            'media-src': "'self'",
            'frame-src': "'none'"
        }
    }
    
    # Email real
    MAIL_SUPPRESS_SEND = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Configurar logging para producción
        import logging
        from logging.handlers import RotatingFileHandler, SMTPHandler
        
        # Handler para archivos
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        file_handler = RotatingFileHandler(
            'logs/ecosistema_emprendimiento.log',
            maxBytes=10240000,
            backupCount=10
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        
        # Handler para emails críticos
        if app.config.get('MAIL_SERVER'):
            auth = None
            if app.config.get('MAIL_USERNAME'):
                auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                
            secure = None
            if app.config.get('MAIL_USE_TLS'):
                secure = ()
                
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr=app.config['MAIL_DEFAULT_SENDER'],
                toaddrs=app.config.get('ADMIN_EMAILS', []),
                subject='Ecosistema Emprendimiento - Error Crítico',
                credentials=auth,
                secure=secure
            )
            
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)


class DockerConfig(ProductionConfig):
    """Configuración específica para contenedores Docker."""
    
    # Variables de entorno específicas para Docker
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:postgres@db:5432/ecosistema_emprendimiento'
    
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/1'
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/2'
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://redis:6379/0'
    
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)
        
        # Configuración específica para contenedores
        import logging
        logging.basicConfig(level=logging.INFO)


# Diccionario de configuraciones disponibles
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}