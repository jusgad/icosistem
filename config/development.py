# -*- coding: utf-8 -*-
"""
Configuración de Desarrollo del Ecosistema de Emprendimiento
==========================================================

Esta configuración está optimizada para facilitar el desarrollo local,
proporcionando herramientas de debugging, logging verboso y configuraciones
que permiten un desarrollo ágil y eficiente.

Características principales:
- DEBUG habilitado con herramientas de desarrollo
- Base de datos local con logging de queries
- Servicios externos en modo de prueba/simulación
- CORS permisivo para desarrollo frontend
- Logging detallado para debugging
- Hot reloading y auto-restart
- Profiling y métricas de rendimiento

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import logging
from datetime import timedelta
from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """
    Configuración específica para ambiente de desarrollo.
    
    Hereda todas las configuraciones base y las adapta para
    facilitar el desarrollo local con herramientas de debugging
    y configuraciones optimizadas para desarrollo.
    """
    
    # ========================================
    # CONFIGURACIÓN BÁSICA DE DESARROLLO
    # ========================================
    
    # Habilitar modo debug
    DEBUG = True
    TESTING = False
    
    # Environment identifier
    ENV = 'development'
    ENVIRONMENT = 'development'
    
    # Configuración de desarrollo más permisiva para sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=48)  # 2 días para desarrollo
    SESSION_COOKIE_SECURE = False  # HTTP permitido en desarrollo
    SESSION_COOKIE_HTTPONLY = True  # Mantener seguridad básica
    
    # ========================================
    # CONFIGURACIÓN DE BASE DE DATOS DESARROLLO
    # ========================================
    
    # Base de datos local de desarrollo
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_dev'
    )
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = True  # Habilitar para debugging
    SQLALCHEMY_RECORD_QUERIES = True  # Registrar todas las queries
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # Pool de conexiones optimizado para desarrollo
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,  # 1 hora
        'pool_timeout': 30,
        'max_overflow': 10,
        'pool_size': 10,
        'echo': SQLALCHEMY_ECHO,  # SQL logging detallado
        'echo_pool': os.environ.get('SQLALCHEMY_ECHO_POOL', 'False').lower() == 'true',
    }
    
    # Base de datos de testing para desarrollo
    TEST_DATABASE_URL = os.environ.get(
        'TEST_DATABASE_URL',
        'postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_test'
    )
    
    # ========================================
    # CONFIGURACIÓN DE REDIS Y CACHE DESARROLLO
    # ========================================
    
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')  # DB 1 para dev
    
    # Cache con timeout más corto para desarrollo
    CACHE_DEFAULT_TIMEOUT = 60  # 1 minuto para ver cambios rápidamente
    CACHE_KEY_PREFIX = 'ecosistema:dev:'
    
    # Configuración de cache para desarrollo
    CACHE_CONFIG = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': REDIS_URL,
        'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
        'CACHE_KEY_PREFIX': CACHE_KEY_PREFIX,
        'CACHE_REDIS_DB': 1,
    }
    
    # ========================================
    # CONFIGURACIÓN DE CELERY DESARROLLO
    # ========================================
    
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Configuración de Celery optimizada para desarrollo
    CELERY_CONFIG = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'America/Bogota',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 300,  # 5 minutos para desarrollo
        'task_soft_time_limit': 240,  # 4 minutos
        'worker_prefetch_multiplier': 1,
        'worker_max_tasks_per_child': 100,  # Reiniciar más frecuentemente
        'task_always_eager': os.environ.get('CELERY_ALWAYS_EAGER', 'False').lower() == 'true',
        'task_eager_propagates': True,
        'worker_disable_rate_limits': True,  # Sin límites en desarrollo
        'beat_schedule': {
            # Tareas más frecuentes para testing en desarrollo
            'cleanup-expired-sessions': {
                'task': 'app.tasks.maintenance_tasks.cleanup_expired_sessions',
                'schedule': timedelta(minutes=30),  # Cada 30 min en dev
            },
            'generate-daily-analytics': {
                'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
                'schedule': timedelta(hours=2),  # Cada 2 horas en dev
            },
            'send-reminder-notifications': {
                'task': 'app.tasks.notification_tasks.send_reminder_notifications',
                'schedule': timedelta(minutes=5),  # Cada 5 min en dev
            },
        },
    }
    
    # ========================================
    # CONFIGURACIÓN DE SEGURIDAD DESARROLLO
    # ========================================
    
    # CSRF más permisivo para desarrollo
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'True').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = 7200  # 2 horas
    WTF_CSRF_SSL_STRICT = False  # No requerir SSL en desarrollo
    
    # Rate limiting más permisivo
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'False').lower() == 'true'
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = '10000 per hour'  # Muy permisivo para desarrollo
    
    # Rate limits específicos para desarrollo
    RATELIMIT_LOGIN = '100 per minute'
    RATELIMIT_REGISTER = '50 per minute'
    RATELIMIT_API = '1000 per minute'
    RATELIMIT_UPLOAD = '100 per minute'
    
    # Sin SSL en desarrollo
    SSL_REDIRECT = False
    SSL_DISABLE = True
    
    # CORS muy permisivo para desarrollo frontend
    CORS_ENABLED = True
    CORS_ORIGINS = ['*']
    CORS_SUPPORTS_CREDENTIALS = True
    CORS_ALLOW_HEADERS = ['*']
    CORS_EXPOSE_HEADERS = ['*']
    
    # ========================================
    # CONFIGURACIÓN DE EMAIL DESARROLLO
    # ========================================
    
    # Email en modo desarrollo - no enviar emails reales
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'True').lower() == 'true'
    MAIL_DEBUG = True
    
    # Configuración para testing local con MailHog o similar
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '1025'))  # MailHog default
    MAIL_USE_TLS = False
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'dev@ecosistema.local')
    
    # Email backend para desarrollo
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'console')  # Imprimir en consola
    EMAIL_VERIFICATION_REQUIRED = os.environ.get('EMAIL_VERIFICATION_REQUIRED', 'False').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE SMS DESARROLLO
    # ========================================
    
    # SMS en modo simulación
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'False').lower() == 'true'
    SMS_PROVIDER = 'console'  # Imprimir en consola en desarrollo
    SMS_SIMULATION_MODE = True
    
    # ========================================
    # CONFIGURACIÓN DE ALMACENAMIENTO DESARROLLO
    # ========================================
    
    # Storage local para desarrollo
    STORAGE_BACKEND = 'local'
    UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', 'app/static/uploads'))
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB para desarrollo
    
    # Crear directorio de uploads si no existe
    import os
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # ========================================
    # CONFIGURACIÓN DE WEBSOCKETS DESARROLLO
    # ========================================
    
    SOCKETIO_ENABLED = True
    SOCKETIO_ASYNC_MODE = 'threading'  # Mejor para desarrollo
    SOCKETIO_REDIS_URL = REDIS_URL
    SOCKETIO_CORS_ALLOWED_ORIGINS = '*'  # Muy permisivo para desarrollo
    SOCKETIO_LOGGER = True  # Logging detallado de WebSockets
    SOCKETIO_ENGINEIO_LOGGER = True
    
    # ========================================
    # CONFIGURACIÓN DE LOGGING DESARROLLO
    # ========================================
    
    LOG_LEVEL = 'DEBUG'  # Logging más verboso
    LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/development.log')
    LOG_TO_CONSOLE = True
    LOG_TO_FILE = True
    
    # Configuración detallada de logging
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': LOG_FORMAT,
            },
            'detailed': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]: %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'default',
                'stream': 'ext://sys.stdout',
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': LOG_FILE,
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8',
            },
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
        },
        'loggers': {
            'flask': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'sqlalchemy': {
                'level': 'INFO',  # Evitar spam de SQLAlchemy
                'handlers': ['file'],
                'propagate': False,
            },
            'werkzeug': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'celery': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
        },
    }
    
    # Sentry deshabilitado en desarrollo por defecto
    SENTRY_ENABLED = os.environ.get('SENTRY_ENABLED', 'False').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE ANALYTICS DESARROLLO
    # ========================================
    
    ANALYTICS_ENABLED = os.environ.get('ANALYTICS_ENABLED', 'False').lower() == 'true'
    GOOGLE_ANALYTICS_ID = None  # No analytics en desarrollo
    
    # Métricas internas habilitadas para desarrollo
    METRICS_ENABLED = True
    METRICS_RETENTION_DAYS = 7  # Solo 7 días en desarrollo
    
    # ========================================
    # CONFIGURACIÓN ESPECÍFICA DE DESARROLLO
    # ========================================
    
    # Configuraciones de desarrollo específicas del ecosistema
    DEFAULT_PROGRAM_DURATION_MONTHS = 1  # Programas más cortos para testing
    MAX_ENTREPRENEURS_PER_ALLY = 3  # Límites más bajos para testing
    MIN_MENTORSHIP_SESSION_MINUTES = 5  # Sesiones más cortas para testing
    MAX_MENTORSHIP_SESSION_MINUTES = 30
    
    # Notificaciones más frecuentes para testing
    MEETING_REMINDER_MINUTES = [1, 5, 15]  # Recordatorios más frecuentes
    NOTIFICATION_RETENTION_DAYS = 7
    
    # Configuración de API para desarrollo
    API_PAGINATION_MAX_PER_PAGE = 1000  # Más permisivo para desarrollo
    API_PAGINATION_DEFAULT_PER_PAGE = 50
    
    # ========================================
    # HERRAMIENTAS DE DESARROLLO
    # ========================================
    
    # Flask-DebugToolbar
    DEBUG_TB_ENABLED = os.environ.get('DEBUG_TB_ENABLED', 'True').lower() == 'true'
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    DEBUG_TB_PROFILER_ENABLED = True
    DEBUG_TB_TEMPLATE_EDITOR_ENABLED = True
    
    # Profiling
    PROFILE = os.environ.get('PROFILE', 'False').lower() == 'true'
    PROFILE_DIR = os.environ.get('PROFILE_DIR', 'profiles')
    
    # Hot reloading
    TEMPLATES_AUTO_RELOAD = True
    EXPLAIN_TEMPLATE_LOADING = os.environ.get('EXPLAIN_TEMPLATE_LOADING', 'False').lower() == 'true'
    
    # Assets development
    ASSETS_DEBUG = True
    ASSETS_AUTO_BUILD = True
    
    # ========================================
    # CONFIGURACIÓN DE SERVICIOS MOCK/SIMULACIÓN
    # ========================================
    
    # Google Services en modo de desarrollo
    GOOGLE_OAUTH_ENABLED = bool(os.environ.get('GOOGLE_CLIENT_ID'))
    GOOGLE_CALENDAR_ENABLED = False  # Deshabilitado por defecto en dev
    GOOGLE_MEET_ENABLED = False
    GOOGLE_DRIVE_ENABLED = False
    
    # Servicios en modo simulación
    SIMULATION_MODE = os.environ.get('SIMULATION_MODE', 'True').lower() == 'true'
    MOCK_EXTERNAL_APIS = os.environ.get('MOCK_EXTERNAL_APIS', 'True').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE TESTING INTEGRADO
    # ========================================
    
    # Configuración para testing durante desarrollo
    TESTING_ENABLED = True
    WTF_CSRF_ENABLED_IN_TESTS = False
    
    # Fixtures y datos de prueba
    LOAD_SAMPLE_DATA = os.environ.get('LOAD_SAMPLE_DATA', 'True').lower() == 'true'
    SAMPLE_DATA_SIZE = os.environ.get('SAMPLE_DATA_SIZE', 'small')  # small, medium, large
    
    # ========================================
    # CONFIGURACIONES ADICIONALES DE DESARROLLO
    # ========================================
    
    # Timezone para desarrollo (Colombia)
    TIMEZONE = 'America/Bogota'
    DEFAULT_LOCALE = 'es_CO'
    
    # Moneda por defecto en desarrollo
    DEFAULT_CURRENCY = 'COP'
    
    # Modo de mantenimiento deshabilitado
    MAINTENANCE_MODE = False
    
    # Health checks habilitados
    HEALTH_CHECK_ENABLED = True
    
    # Configuración de CORS específica para desarrollo frontend
    CORS_CONFIG = {
        'origins': ['http://localhost:3000', 'http://localhost:8080', 'http://127.0.0.1:3000'],
        'methods': ['GET', 'HEAD', 'POST', 'OPTIONS', 'PUT', 'PATCH', 'DELETE'],
        'allow_headers': ['Content-Type', 'Authorization', 'X-Requested-With', 'X-CSRF-Token'],
        'supports_credentials': True,
        'max_age': 86400,  # 24 horas
    }
    
    # ========================================
    # MÉTODOS DE UTILIDAD PARA DESARROLLO
    # ========================================
    
    @classmethod
    def get_development_database_uri(cls, db_name: str = 'ecosistema_emprendimiento_dev') -> str:
        """
        Construye URI de base de datos para desarrollo.
        
        Args:
            db_name: Nombre de la base de datos
            
        Returns:
            URI de conexión para desarrollo
        """
        base_uri = 'postgresql://postgres:password@localhost:5432'
        return f"{base_uri}/{db_name}"
    
    @classmethod
    def setup_development_logging(cls):
        """
        Configura logging específico para desarrollo.
        """
        import logging.config
        
        # Crear directorio de logs si no existe
        log_dir = os.path.dirname(cls.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Aplicar configuración de logging
        logging.config.dictConfig(cls.LOGGING_CONFIG)
        
        # Logger específico para desarrollo
        dev_logger = logging.getLogger('development')
        dev_logger.info(f"Configuración de desarrollo cargada")
        dev_logger.info(f"Base de datos: {cls.DATABASE_URL}")
        dev_logger.info(f"Redis: {cls.REDIS_URL}")
        dev_logger.info(f"Debug mode: {cls.DEBUG}")
    
    @classmethod
    def create_development_directories(cls):
        """
        Crea directorios necesarios para desarrollo.
        """
        directories = [
            cls.UPLOAD_FOLDER,
            os.path.dirname(cls.LOG_FILE),
            'profiles' if cls.PROFILE else None,
            'app/static/uploads/images',
            'app/static/uploads/documents',
            'app/static/uploads/videos',
            'app/static/uploads/audio',
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
    
    @staticmethod
    def init_app(app):
        """
        Inicialización específica para desarrollo.
        
        Args:
            app: Instancia de aplicación Flask
        """
        # Llamar inicialización base
        BaseConfig.init_app(app)
        
        # Configuración específica de desarrollo
        DevelopmentConfig.setup_development_logging()
        DevelopmentConfig.create_development_directories()
        
        # Configurar herramientas de desarrollo
        if DevelopmentConfig.DEBUG_TB_ENABLED:
            try:
                from flask_debugtoolbar import DebugToolbarExtension
                toolbar = DebugToolbarExtension(app)
            except ImportError:
                app.logger.warning("Flask-DebugToolbar no está instalado")
        
        # Configurar profiling si está habilitado
        if DevelopmentConfig.PROFILE:
            from werkzeug.middleware.profiler import ProfilerMiddleware
            app.wsgi_app = ProfilerMiddleware(
                app.wsgi_app,
                profile_dir=DevelopmentConfig.PROFILE_DIR
            )
        
        # Logging de inicio en desarrollo
        app.logger.info(f"Aplicación iniciada en modo desarrollo")
        app.logger.info(f"Configuración: {DevelopmentConfig.__name__}")
        app.logger.debug(f"Features habilitadas:")
        app.logger.debug(f"  - Debug: {DevelopmentConfig.DEBUG}")
        app.logger.debug(f"  - CSRF: {DevelopmentConfig.WTF_CSRF_ENABLED}")
        app.logger.debug(f"  - Rate Limiting: {DevelopmentConfig.RATELIMIT_ENABLED}")
        app.logger.debug(f"  - Analytics: {DevelopmentConfig.ANALYTICS_ENABLED}")


# Función de utilidad para configuración rápida de desarrollo
def setup_development_environment():
    """
    Configura el ambiente de desarrollo completo.
    
    Returns:
        Instancia de configuración de desarrollo
    """
    config = DevelopmentConfig()
    config.create_development_directories()
    config.setup_development_logging()
    
    return config


# Exportar configuración
__all__ = ['DevelopmentConfig', 'setup_development_environment']