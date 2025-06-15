# -*- coding: utf-8 -*-
"""
Configuración de Producción del Ecosistema de Emprendimiento
==========================================================

Esta configuración está optimizada para ambientes de producción de alta disponibilidad,
con énfasis en seguridad, rendimiento, escalabilidad y monitoreo empresarial.

Características principales:
- Seguridad máxima con SSL obligatorio y CSRF estricto
- Rate limiting agresivo para prevenir ataques
- Pool de conexiones optimizado para alta concurrencia
- Logging estructurado con métricas y alertas
- Cache distribuido con TTL optimizados
- Monitoreo completo con Sentry y métricas
- Backup automático y disaster recovery
- Configuración para CDN y proxy reverso
- Compliance con estándares empresariales

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import logging
from datetime import timedelta
from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """
    Configuración específica para ambiente de producción.
    
    Optimizada para alta disponibilidad, seguridad máxima y rendimiento
    empresarial con monitoreo completo y configuraciones robustas.
    """
    
    # ========================================
    # CONFIGURACIÓN BÁSICA DE PRODUCCIÓN
    # ========================================
    
    # Deshabilitar completamente el modo debug
    DEBUG = False
    TESTING = False
    
    # Environment identifier
    ENV = 'production'
    ENVIRONMENT = 'production'
    
    # Configuración de sesiones ultra-segura
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8 horas máximo
    SESSION_COOKIE_SECURE = True  # Solo HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'  # Máxima protección CSRF
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')
    
    # Configuración de dominio y SSL
    SERVER_NAME = os.environ.get('SERVER_NAME')
    PREFERRED_URL_SCHEME = 'https'
    
    # ========================================
    # CONFIGURACIÓN DE BASE DE DATOS PRODUCCIÓN
    # ========================================
    
    # Base de datos de producción - REQUERIDA
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL es requerida en producción")
    
    # Corregir URLs de Heroku/Railway si es necesario
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Deshabilitado en producción
    SQLALCHEMY_RECORD_QUERIES = False  # Sin logging de queries en producción
    SQLALCHEMY_ECHO = False  # Sin echo en producción
    
    # Pool de conexiones optimizado para alta concurrencia
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Verificar conexiones antes de usar
        'pool_recycle': 1800,   # 30 minutos - más conservador
        'pool_timeout': 30,     # 30 segundos timeout
        'max_overflow': 20,     # Conexiones adicionales permitidas
        'pool_size': 20,        # Pool base grande para producción
        'connect_args': {
            'connect_timeout': 10,
            'application_name': 'ecosistema_emprendimiento_prod',
            'options': '-c default_transaction_isolation=read_committed'
        }
    }
    
    # Base de datos de solo lectura para reportes (opcional)
    READ_REPLICA_URL = os.environ.get('READ_REPLICA_URL')
    if READ_REPLICA_URL:
        SQLALCHEMY_BINDS = {
            'read_replica': READ_REPLICA_URL
        }
    
    # ========================================
    # CONFIGURACIÓN DE REDIS Y CACHE PRODUCCIÓN
    # ========================================
    
    REDIS_URL = os.environ.get('REDIS_URL')
    if not REDIS_URL:
        raise ValueError("REDIS_URL es requerida en producción")
    
    # Configuración de cache optimizada para producción
    CACHE_DEFAULT_TIMEOUT = 3600  # 1 hora por defecto
    CACHE_KEY_PREFIX = 'ecosistema:prod:'
    
    # Configuración avanzada de Redis
    CACHE_CONFIG = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': REDIS_URL,
        'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
        'CACHE_KEY_PREFIX': CACHE_KEY_PREFIX,
        'CACHE_REDIS_DB': 0,
        'CACHE_OPTIONS': {
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
            'retry_on_timeout': True,
            'health_check_interval': 30,
        }
    }
    
    # Cache específico para sesiones
    SESSION_REDIS_URL = os.environ.get('SESSION_REDIS_URL', REDIS_URL)
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'session:'
    SESSION_PERMANENT = False
    
    # ========================================
    # CONFIGURACIÓN DE CELERY PRODUCCIÓN
    # ========================================
    
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Configuración de Celery optimizada para producción
    CELERY_CONFIG = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 3600,  # 1 hora máximo
        'task_soft_time_limit': 3000,  # 50 minutos warning
        'worker_prefetch_multiplier': 1,  # Una tarea por worker
        'worker_max_tasks_per_child': 1000,  # Reiniciar workers periódicamente
        'worker_disable_rate_limits': False,
        'task_acks_late': True,  # Acknowledge después de completar
        'task_reject_on_worker_lost': True,
        'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        'broker_connection_retry_on_startup': True,
        'broker_connection_retry': True,
        'broker_connection_max_retries': 100,
        'result_expires': 3600,  # Resultados expiran en 1 hora
        'task_compression': 'gzip',
        'result_compression': 'gzip',
        'beat_schedule': {
            'cleanup-expired-sessions': {
                'task': 'app.tasks.maintenance_tasks.cleanup_expired_sessions',
                'schedule': timedelta(hours=6),
            },
            'generate-daily-analytics': {
                'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
                'schedule': timedelta(hours=24),
            },
            'send-reminder-notifications': {
                'task': 'app.tasks.notification_tasks.send_reminder_notifications',
                'schedule': timedelta(minutes=30),
            },
            'backup-database': {
                'task': 'app.tasks.backup_tasks.backup_database',
                'schedule': timedelta(hours=6),
            },
            'cleanup-old-logs': {
                'task': 'app.tasks.maintenance_tasks.cleanup_old_logs',
                'schedule': timedelta(days=1),
            },
            'health-check-services': {
                'task': 'app.tasks.maintenance_tasks.health_check_services',
                'schedule': timedelta(minutes=5),
            },
        },
    }
    
    # ========================================
    # CONFIGURACIÓN DE SEGURIDAD PRODUCCIÓN
    # ========================================
    
    # CSRF ultra-estricto
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora
    WTF_CSRF_SSL_STRICT = True
    WTF_CSRF_CHECK_DEFAULT = True
    
    # Rate limiting agresivo
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = '100 per hour'  # Límite base conservador
    RATELIMIT_STRATEGY = 'fixed-window-elastic-expiry'
    
    # Rate limits específicos para producción
    RATELIMIT_LOGIN = '10 per minute'  # Máximo 10 intentos de login por minuto
    RATELIMIT_REGISTER = '5 per hour'  # Máximo 5 registros por hora
    RATELIMIT_API = '1000 per hour'    # 1000 requests API por hora
    RATELIMIT_UPLOAD = '20 per hour'   # 20 uploads por hora
    RATELIMIT_PASSWORD_RESET = '3 per hour'  # 3 resets de password por hora
    
    # SSL obligatorio
    SSL_REDIRECT = True
    SSL_DISABLE = False
    FORCE_HTTPS = True
    
    # Headers de seguridad
    SECURITY_HEADERS = {
        'STRICT_TRANSPORT_SECURITY': 'max-age=31536000; includeSubDomains',
        'X_CONTENT_TYPE_OPTIONS': 'nosniff',
        'X_FRAME_OPTIONS': 'DENY',
        'X_XSS_PROTECTION': '1; mode=block',
        'REFERRER_POLICY': 'strict-origin-when-cross-origin',
        'CONTENT_SECURITY_POLICY': "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.google-analytics.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-src 'self' https://calendar.google.com https://meet.google.com;"
    }
    
    # CORS restrictivo
    CORS_ENABLED = True
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',') if os.environ.get('CORS_ORIGINS') else []
    CORS_SUPPORTS_CREDENTIALS = True
    CORS_MAX_AGE = 86400
    
    # Configuración de passwords más estricta
    PASSWORD_MIN_LENGTH = 12  # Mínimo 12 caracteres en producción
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SYMBOLS = True
    PASSWORD_HISTORY_LIMIT = 5  # No reutilizar últimas 5 passwords
    
    # ========================================
    # CONFIGURACIÓN DE EMAIL PRODUCCIÓN
    # ========================================
    
    # Email completamente habilitado
    MAIL_SUPPRESS_SEND = False
    MAIL_DEBUG = False
    
    # Configuración de email backend
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'sendgrid')
    
    # SendGrid (recomendado para producción)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    if EMAIL_BACKEND == 'sendgrid' and not SENDGRID_API_KEY:
        raise ValueError("SENDGRID_API_KEY es requerida cuando EMAIL_BACKEND es sendgrid")
    
    # Configuración SMTP como fallback
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.sendgrid.net')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'apikey')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', SENDGRID_API_KEY)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    if not MAIL_DEFAULT_SENDER:
        raise ValueError("MAIL_DEFAULT_SENDER es requerido en producción")
    
    # Email verification obligatoria
    EMAIL_VERIFICATION_REQUIRED = True
    
    # Configuración de templates de email
    EMAIL_TEMPLATE_FOLDER = 'app/templates/emails'
    EMAIL_BRAND_NAME = APP_NAME
    EMAIL_SUPPORT_EMAIL = os.environ.get('EMAIL_SUPPORT_EMAIL', MAIL_DEFAULT_SENDER)
    
    # ========================================
    # CONFIGURACIÓN DE SMS PRODUCCIÓN
    # ========================================
    
    SMS_ENABLED = True
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'twilio')
    
    # Twilio (recomendado para producción)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if SMS_ENABLED and SMS_PROVIDER == 'twilio':
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            raise ValueError("Credenciales de Twilio son requeridas cuando SMS está habilitado")
    
    # ========================================
    # CONFIGURACIÓN DE ALMACENAMIENTO PRODUCCIÓN
    # ========================================
    
    # Storage en la nube obligatorio
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 's3')
    
    if STORAGE_BACKEND == 's3':
        AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')
        AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
        AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
        AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
        
        if not all([AWS_S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
            raise ValueError("Credenciales de AWS S3 son requeridas en producción")
        
        # Configuración S3 optimizada
        AWS_S3_FILE_OVERWRITE = False
        AWS_S3_OBJECT_PARAMETERS = {
            'CacheControl': 'max-age=86400',  # 24 horas
        }
        AWS_STORAGE_BUCKET_NAME = AWS_S3_BUCKET_NAME
        AWS_S3_SIGNATURE_VERSION = 's3v4'
        AWS_S3_ADDRESSING_STYLE = 'virtual'
        
    elif STORAGE_BACKEND == 'gcs':
        GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
        GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not all([GCS_BUCKET_NAME, GOOGLE_APPLICATION_CREDENTIALS]):
            raise ValueError("Credenciales de Google Cloud Storage son requeridas")
    
    # Límites de archivos para producción
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25MB máximo
    
    # ========================================
    # CONFIGURACIÓN DE WEBSOCKETS PRODUCCIÓN
    # ========================================
    
    SOCKETIO_ENABLED = True
    SOCKETIO_ASYNC_MODE = 'eventlet'  # Mejor para producción
    SOCKETIO_REDIS_URL = REDIS_URL
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS
    SOCKETIO_LOGGER = False  # Sin logging verboso en producción
    SOCKETIO_ENGINEIO_LOGGER = False
    
    # Configuración avanzada de WebSockets
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25
    SOCKETIO_MAX_HTTP_BUFFER_SIZE = 1000000  # 1MB
    
    # ========================================
    # CONFIGURACIÓN DE LOGGING PRODUCCIÓN
    # ========================================
    
    LOG_LEVEL = 'INFO'  # Solo INFO y superior en producción
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(message)s'
    LOG_FILE = os.environ.get('LOG_FILE', '/var/log/ecosistema/production.log')
    LOG_MAX_BYTES = 50 * 1024 * 1024  # 50MB por archivo
    LOG_BACKUP_COUNT = 10
    
    # Configuración estructurada de logging para producción
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'production': {
                'format': '%(asctime)s [%(process)d] [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'json': {
                'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
            },
        },
        'handlers': {
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'production',
                'filename': LOG_FILE,
                'maxBytes': LOG_MAX_BYTES,
                'backupCount': LOG_BACKUP_COUNT,
                'encoding': 'utf8',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'json',
                'filename': '/var/log/ecosistema/errors.log',
                'maxBytes': LOG_MAX_BYTES,
                'backupCount': 5,
                'encoding': 'utf8',
            },
            'sentry': {
                'class': 'sentry_sdk.integrations.logging.SentryHandler',
                'level': 'WARNING',
            } if os.environ.get('SENTRY_DSN') else {
                'class': 'logging.NullHandler',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file', 'error_file', 'sentry'],
        },
        'loggers': {
            'gunicorn': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False,
            },
            'celery': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False,
            },
            'sqlalchemy.engine': {
                'level': 'WARNING',  # Solo errores de DB
                'handlers': ['error_file'],
                'propagate': False,
            },
        },
    }
    
    # Sentry para monitoreo de errores
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    SENTRY_ENABLED = bool(SENTRY_DSN)
    SENTRY_ENVIRONMENT = 'production'
    SENTRY_RELEASE = os.environ.get('SENTRY_RELEASE', APP_VERSION)
    
    # ========================================
    # CONFIGURACIÓN DE ANALYTICS Y MONITOREO
    # ========================================
    
    ANALYTICS_ENABLED = True
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID')
    
    # Métricas internas habilitadas
    METRICS_ENABLED = True
    METRICS_RETENTION_DAYS = 365  # 1 año de retención
    
    # Health checks obligatorios
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_PATH = '/health'
    
    # Configuración de APM (Application Performance Monitoring)
    APM_ENABLED = os.environ.get('APM_ENABLED', 'False').lower() == 'true'
    NEW_RELIC_LICENSE_KEY = os.environ.get('NEW_RELIC_LICENSE_KEY')
    DATADOG_API_KEY = os.environ.get('DATADOG_API_KEY')
    
    # ========================================
    # CONFIGURACIÓN DE SERVICIOS GOOGLE PRODUCCIÓN
    # ========================================
    
    # Google OAuth obligatorio en producción
    GOOGLE_OAUTH_ENABLED = True
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("Credenciales de Google OAuth son requeridas en producción")
    
    # Servicios Google habilitados
    GOOGLE_CALENDAR_ENABLED = True
    GOOGLE_MEET_ENABLED = True
    GOOGLE_DRIVE_ENABLED = True
    
    # ========================================
    # CONFIGURACIÓN DE BACKUP Y DISASTER RECOVERY
    # ========================================
    
    # Backup automático habilitado
    AUTO_BACKUP_ENABLED = True
    BACKUP_SCHEDULE = 'daily'  # daily, weekly, monthly
    BACKUP_RETENTION_DAYS = 30
    BACKUP_STORAGE_BACKEND = 's3'  # s3, gcs
    BACKUP_ENCRYPTION_KEY = os.environ.get('BACKUP_ENCRYPTION_KEY')
    
    # Database backup específico
    DB_BACKUP_ENABLED = True
    DB_BACKUP_SCHEDULE = '0 2 * * *'  # 2 AM daily
    DB_BACKUP_COMPRESS = True
    
    # File backup
    FILE_BACKUP_ENABLED = True
    FILE_BACKUP_SCHEDULE = '0 3 * * 0'  # 3 AM every Sunday
    
    # ========================================
    # CONFIGURACIÓN DE CDN Y PROXY
    # ========================================
    
    # CDN para assets estáticos
    CDN_ENABLED = os.environ.get('CDN_ENABLED', 'False').lower() == 'true'
    CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
    STATIC_URL_PATH = '/static'
    
    if CDN_ENABLED and CDN_DOMAIN:
        STATIC_URL = f"https://{CDN_DOMAIN}/static"
    
    # Configuración para proxy reverso
    PROXY_FIX_ENABLED = True
    PROXY_FIX_NUM_PROXIES = int(os.environ.get('PROXY_FIX_NUM_PROXIES', '1'))
    
    # ========================================
    # CONFIGURACIÓN ESPECÍFICA DEL ECOSISTEMA PRODUCCIÓN
    # ========================================
    
    # Configuraciones de negocio para producción
    DEFAULT_PROGRAM_DURATION_MONTHS = 6
    MAX_ENTREPRENEURS_PER_ALLY = 10
    MIN_MENTORSHIP_SESSION_MINUTES = 30
    MAX_MENTORSHIP_SESSION_MINUTES = 120
    
    # Configuración de notificaciones
    NOTIFICATION_RETENTION_DAYS = 90  # 3 meses
    EMAIL_NOTIFICATION_ENABLED = True
    SMS_NOTIFICATION_ENABLED = True
    PUSH_NOTIFICATION_ENABLED = True
    
    # Configuración de reuniones
    MEETING_BUFFER_MINUTES = 15
    MAX_MEETING_DURATION_HOURS = 4
    MEETING_REMINDER_MINUTES = [15, 60, 1440]  # 15 min, 1 hora, 1 día
    
    # Configuración de documentos
    DOCUMENT_RETENTION_YEARS = 7
    DOCUMENT_VERSIONING_ENABLED = True
    DOCUMENT_AUDIT_TRAIL_ENABLED = True
    
    # Configuración de API
    API_PAGINATION_MAX_PER_PAGE = 100
    API_PAGINATION_DEFAULT_PER_PAGE = 20
    API_DOCUMENTATION_ENABLED = False  # Swagger docs deshabilitado en producción
    
    # ========================================
    # CONFIGURACIÓN DE COMPLIANCE Y AUDITORÍA
    # ========================================
    
    # Auditoría completa habilitada
    AUDIT_LOG_ENABLED = True
    AUDIT_LOG_RETENTION_YEARS = 7
    
    # Compliance con GDPR/CCPA
    PRIVACY_COMPLIANCE_ENABLED = True
    DATA_RETENTION_POLICY_ENABLED = True
    
    # Configuración de términos y privacidad
    TERMS_VERSION = os.environ.get('TERMS_VERSION', '1.0')
    PRIVACY_VERSION = os.environ.get('PRIVACY_VERSION', '1.0')
    
    # ========================================
    # CONFIGURACIÓN DE ESCALABILIDAD
    # ========================================
    
    # Worker configuration para Gunicorn
    WORKERS = int(os.environ.get('WEB_WORKERS', '4'))
    WORKER_CLASS = os.environ.get('WORKER_CLASS', 'gevent')
    WORKER_CONNECTIONS = int(os.environ.get('WORKER_CONNECTIONS', '1000'))
    MAX_REQUESTS = int(os.environ.get('MAX_REQUESTS', '1000'))
    MAX_REQUESTS_JITTER = int(os.environ.get('MAX_REQUESTS_JITTER', '100'))
    TIMEOUT = int(os.environ.get('TIMEOUT', '30'))
    KEEPALIVE = int(os.environ.get('KEEPALIVE', '2'))
    
    # Configuración de load balancing
    LOAD_BALANCER_ENABLED = os.environ.get('LOAD_BALANCER_ENABLED', 'False').lower() == 'true'
    STICKY_SESSIONS = os.environ.get('STICKY_SESSIONS', 'False').lower() == 'true'
    
    # ========================================
    # MÉTODOS DE UTILIDAD PARA PRODUCCIÓN
    # ========================================
    
    @classmethod
    def validate_production_config(cls):
        """
        Valida que todas las configuraciones críticas estén presentes.
        
        Raises:
            ValueError: Si falta alguna configuración crítica
        """
        required_vars = [
            'SECRET_KEY', 'DATABASE_URL', 'REDIS_URL',
            'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET',
            'MAIL_DEFAULT_SENDER'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var, None):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables críticas faltantes en producción: {', '.join(missing_vars)}")
        
        # Validaciones adicionales
        if len(cls.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres en producción")
        
        if cls.DEBUG:
            raise ValueError("DEBUG no puede estar habilitado en producción")
    
    @classmethod
    def setup_production_monitoring(cls):
        """
        Configura monitoreo específico de producción.
        """
        # Configurar Sentry si está disponible
        if cls.SENTRY_ENABLED:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            
            sentry_sdk.init(
                dsn=cls.SENTRY_DSN,
                environment=cls.SENTRY_ENVIRONMENT,
                release=cls.SENTRY_RELEASE,
                integrations=[
                    FlaskIntegration(transaction_style='endpoint'),
                    SqlalchemyIntegration(),
                    CeleryIntegration(),
                    RedisIntegration(),
                ],
                traces_sample_rate=0.1,  # 10% de traces para performance
                profiles_sample_rate=0.1,
                attach_stacktrace=True,
                send_default_pii=False,  # No enviar PII por compliance
            )
    
    @classmethod
    def setup_production_logging(cls):
        """
        Configura logging específico de producción.
        """
        import logging.config
        
        # Crear directorios de logs si no existen
        log_dir = os.path.dirname(cls.LOG_FILE)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True, mode=0o755)
        
        # Aplicar configuración de logging
        logging.config.dictConfig(cls.LOGGING_CONFIG)
        
        # Logger de producción
        prod_logger = logging.getLogger('production')
        prod_logger.info(f"Aplicación iniciada en producción")
        prod_logger.info(f"Versión: {cls.APP_VERSION}")
        prod_logger.info(f"Environment: {cls.ENVIRONMENT}")
    
    @staticmethod
    def init_app(app):
        """
        Inicialización específica para producción.
        
        Args:
            app: Instancia de aplicación Flask
        """
        # Llamar inicialización base
        BaseConfig.init_app(app)
        
        # Validar configuración de producción
        ProductionConfig.validate_production_config()
        
        # Configurar monitoreo
        ProductionConfig.setup_production_monitoring()
        ProductionConfig.setup_production_logging()
        
        # Configurar proxy fix si está habilitado
        if ProductionConfig.PROXY_FIX_ENABLED:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=ProductionConfig.PROXY_FIX_NUM_PROXIES,
                x_proto=ProductionConfig.PROXY_FIX_NUM_PROXIES,
                x_host=ProductionConfig.PROXY_FIX_NUM_PROXIES,
                x_prefix=ProductionConfig.PROXY_FIX_NUM_PROXIES
            )
        
        # Configurar headers de seguridad
        @app.after_request
        def set_security_headers(response):
            for header, value in ProductionConfig.SECURITY_HEADERS.items():
                response.headers[header.replace('_', '-')] = value
            return response
        
        # Health check endpoint
        @app.route('/health')
        def health_check():
            """Endpoint de health check para load balancers."""
            return {'status': 'healthy', 'version': ProductionConfig.APP_VERSION}, 200
        
        # Logging de inicio en producción
        app.logger.info(f"Aplicación Flask iniciada en modo producción")
        app.logger.info(f"Configuración: {ProductionConfig.__name__}")
        app.logger.info(f"Features de seguridad habilitadas:")
        app.logger.info(f"  - SSL Redirect: {ProductionConfig.SSL_REDIRECT}")
        app.logger.info(f"  - CSRF Protection: {ProductionConfig.WTF_CSRF_ENABLED}")
        app.logger.info(f"  - Rate Limiting: {ProductionConfig.RATELIMIT_ENABLED}")
        app.logger.info(f"  - Sentry Monitoring: {ProductionConfig.SENTRY_ENABLED}")


# Función de utilidad para configuración de producción
def setup_production_environment():
    """
    Configura el ambiente de producción completo.
    
    Returns:
        Instancia de configuración de producción
    """
    config = ProductionConfig()
    config.validate_production_config()
    config.setup_production_monitoring()
    config.setup_production_logging()
    
    return config


# Exportar configuración
__all__ = ['ProductionConfig', 'setup_production_environment']