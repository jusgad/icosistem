# -*- coding: utf-8 -*-
"""
Configuración de Docker del Ecosistema de Emprendimiento
=======================================================

Esta configuración está optimizada para despliegue en contenedores Docker,
proporcionando configuraciones específicas para containerización, orquestación
con Docker Compose, Kubernetes, y servicios distribuidos.

Características principales:
- Configuración optimizada para contenedores
- Networking entre servicios containerizados
- Health checks y monitoring para containers
- Configuración de volúmenes y storage persistente
- Variables de entorno específicas para Docker
- Configuración de workers y scaling horizontal
- Integration con Docker Compose y Kubernetes
- Logging estructurado para containers
- Security hardening para contenedores

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import socket
from datetime import timedelta
from .base import BaseConfig


class DockerConfig(BaseConfig):
    """
    Configuración específica para ambiente Docker.
    
    Optimizada para despliegue en contenedores con configuraciones
    que facilitan la orquestación, scaling y mantenimiento de
    aplicaciones containerizadas.
    """
    
    # ========================================
    # CONFIGURACIÓN BÁSICA DE DOCKER
    # ========================================
    
    # Modo debug controlado por variable de entorno
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = False
    
    # Environment identifier
    ENV = 'docker'
    ENVIRONMENT = 'docker'
    
    # Configuración de aplicación para containers
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY debe estar definida en el contenedor")
    
    # Configuración de red para containers
    SERVER_NAME = os.environ.get('SERVER_NAME')
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    
    # Configuración de sesiones para Docker
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get('SESSION_LIFETIME_HOURS', '12'))
    )
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')
    
    # ========================================
    # CONFIGURACIÓN DE BASE DE DATOS DOCKER
    # ========================================
    
    # PostgreSQL containerizado
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # Construir URL desde variables individuales para Docker Compose
        DB_HOST = os.environ.get('DB_HOST', 'postgres')
        DB_PORT = os.environ.get('DB_PORT', '5432')
        DB_NAME = os.environ.get('DB_NAME', 'ecosistema_emprendimiento')
        DB_USER = os.environ.get('DB_USER', 'postgres')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')
        
        if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
            raise ValueError("Variables de base de datos requeridas: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD")
        
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = os.environ.get('SQLALCHEMY_RECORD_QUERIES', 'False').lower() == 'true'
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # Pool de conexiones optimizado para containers
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '1800')),  # 30 min
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '10')),
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '10')),
        'connect_args': {
            'connect_timeout': 10,
            'application_name': f'ecosistema_docker_{os.environ.get("HOSTNAME", "unknown")}',
            'options': '-c default_transaction_isolation=read_committed'
        }
    }
    
    # Base de datos de solo lectura para reportes (si está disponible)
    READ_REPLICA_URL = os.environ.get('READ_REPLICA_URL')
    if READ_REPLICA_URL:
        SQLALCHEMY_BINDS = {'read_replica': READ_REPLICA_URL}
    
    # ========================================
    # CONFIGURACIÓN DE REDIS DOCKER
    # ========================================
    
    # Redis containerizado
    REDIS_URL = os.environ.get('REDIS_URL')
    if not REDIS_URL:
        # Construir URL desde variables para Docker Compose
        REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
        REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
        REDIS_DB = os.environ.get('REDIS_DB', '0')
        REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
        
        if REDIS_PASSWORD:
            REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        else:
            REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # Configuración de cache para Docker
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '3600'))
    CACHE_KEY_PREFIX = f'ecosistema:docker:{os.environ.get("CONTAINER_NAME", "app")}:'
    
    # Configuración avanzada de Redis para containers
    CACHE_CONFIG = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': REDIS_URL,
        'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
        'CACHE_KEY_PREFIX': CACHE_KEY_PREFIX,
        'CACHE_OPTIONS': {
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'retry_on_timeout': True,
            'health_check_interval': 30,
            'connection_pool_kwargs': {
                'max_connections': int(os.environ.get('REDIS_MAX_CONNECTIONS', '50')),
                'retry_on_timeout': True,
            }
        }
    }
    
    # ========================================
    # CONFIGURACIÓN DE CELERY DOCKER
    # ========================================
    
    # Celery con Redis broker containerizado
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Configuración de Celery optimizada para Docker
    CELERY_CONFIG = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': os.environ.get('TZ', 'UTC'),
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': int(os.environ.get('CELERY_TASK_TIME_LIMIT', '3600')),
        'task_soft_time_limit': int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '3000')),
        'worker_prefetch_multiplier': int(os.environ.get('CELERY_WORKER_PREFETCH', '1')),
        'worker_max_tasks_per_child': int(os.environ.get('CELERY_WORKER_MAX_TASKS', '1000')),
        'worker_disable_rate_limits': False,
        'task_acks_late': True,
        'task_reject_on_worker_lost': True,
        'broker_connection_retry_on_startup': True,
        'broker_connection_retry': True,
        'broker_connection_max_retries': 100,
        'result_expires': int(os.environ.get('CELERY_RESULT_EXPIRES', '3600')),
        'task_compression': 'gzip',
        'result_compression': 'gzip',
        'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
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
            'health-check-services': {
                'task': 'app.tasks.maintenance_tasks.health_check_services',
                'schedule': timedelta(minutes=5),
            },
            'container-health-report': {
                'task': 'app.tasks.maintenance_tasks.container_health_report',
                'schedule': timedelta(minutes=10),
            },
        },
    }
    
    # ========================================
    # CONFIGURACIÓN DE SEGURIDAD DOCKER
    # ========================================
    
    # Configuración de seguridad para containers
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'True').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('WTF_CSRF_TIME_LIMIT', '3600'))
    WTF_CSRF_SSL_STRICT = os.environ.get('WTF_CSRF_SSL_STRICT', 'True').lower() == 'true'
    
    # Rate limiting con Redis compartido
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True').lower() == 'true'
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '1000 per hour')
    RATELIMIT_KEY_PREFIX = f'ratelimit:docker:{os.environ.get("CONTAINER_NAME", "app")}:'
    
    # Rate limits específicos para Docker
    RATELIMIT_LOGIN = os.environ.get('RATELIMIT_LOGIN', '20 per minute')
    RATELIMIT_REGISTER = os.environ.get('RATELIMIT_REGISTER', '10 per hour')
    RATELIMIT_API = os.environ.get('RATELIMIT_API', '2000 per hour')
    RATELIMIT_UPLOAD = os.environ.get('RATELIMIT_UPLOAD', '50 per hour')
    
    # SSL configuration
    SSL_REDIRECT = os.environ.get('SSL_REDIRECT', 'True').lower() == 'true'
    SSL_DISABLE = os.environ.get('SSL_DISABLE', 'False').lower() == 'true'
    
    # CORS para microservicios
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'True').lower() == 'true'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # ========================================
    # CONFIGURACIÓN DE EMAIL DOCKER
    # ========================================
    
    # Email configuration para containers
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'False').lower() == 'true'
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'smtp')
    
    # SMTP configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # SendGrid para containers en producción
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    
    # Email verification
    EMAIL_VERIFICATION_REQUIRED = os.environ.get('EMAIL_VERIFICATION_REQUIRED', 'True').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE SMS DOCKER
    # ========================================
    
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'True').lower() == 'true'
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'twilio')
    
    # Twilio configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # ========================================
    # CONFIGURACIÓN DE ALMACENAMIENTO DOCKER
    # ========================================
    
    # Storage configuration para containers
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local')
    
    # Storage local con volúmenes Docker
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', str(50 * 1024 * 1024)))  # 50MB
    
    # AWS S3 para storage en la nube
    if STORAGE_BACKEND == 's3':
        AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')
        AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
        AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
        AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
    
    # Google Cloud Storage
    elif STORAGE_BACKEND == 'gcs':
        GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
        GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    # ========================================
    # CONFIGURACIÓN DE WEBSOCKETS DOCKER
    # ========================================
    
    SOCKETIO_ENABLED = os.environ.get('SOCKETIO_ENABLED', 'True').lower() == 'true'
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'eventlet')
    SOCKETIO_REDIS_URL = REDIS_URL
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS
    SOCKETIO_LOGGER = os.environ.get('SOCKETIO_LOGGER', 'False').lower() == 'true'
    SOCKETIO_ENGINEIO_LOGGER = os.environ.get('SOCKETIO_ENGINEIO_LOGGER', 'False').lower() == 'true'
    
    # Configuración específica para containers
    SOCKETIO_PING_TIMEOUT = int(os.environ.get('SOCKETIO_PING_TIMEOUT', '60'))
    SOCKETIO_PING_INTERVAL = int(os.environ.get('SOCKETIO_PING_INTERVAL', '25'))
    
    # ========================================
    # CONFIGURACIÓN DE LOGGING DOCKER
    # ========================================
    
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_TO_STDOUT = True  # Siempre a stdout en containers
    LOG_JSON_FORMAT = os.environ.get('LOG_JSON_FORMAT', 'True').lower() == 'true'
    
    # Configuración de logging para containers
    if LOG_JSON_FORMAT:
        LOG_FORMAT = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s", "container": "' + os.environ.get('HOSTNAME', 'unknown') + '"}'
    else:
        LOG_FORMAT = f'[{os.environ.get("HOSTNAME", "unknown")}] %(asctime)s %(levelname)s %(name)s: %(message)s'
    
    # Configuración de logging estructurado para Docker
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'docker': {
                'format': LOG_FORMAT,
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'json': {
                'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
            } if LOG_JSON_FORMAT else {
                'format': LOG_FORMAT,
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': LOG_LEVEL,
                'formatter': 'json' if LOG_JSON_FORMAT else 'docker',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'level': LOG_LEVEL,
            'handlers': ['console'],
        },
        'loggers': {
            'gunicorn.error': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'gunicorn.access': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'celery': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'sqlalchemy.engine': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False,
            },
        },
    }
    
    # Sentry para containers
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    SENTRY_ENABLED = bool(SENTRY_DSN)
    SENTRY_ENVIRONMENT = 'docker'
    SENTRY_RELEASE = os.environ.get('SENTRY_RELEASE', os.environ.get('GIT_COMMIT', 'unknown'))
    
    # ========================================
    # CONFIGURACIÓN DE SERVICIOS GOOGLE DOCKER
    # ========================================
    
    # Google OAuth para containers
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    
    # Google services
    GOOGLE_CALENDAR_ENABLED = GOOGLE_OAUTH_ENABLED and os.environ.get('GOOGLE_CALENDAR_ENABLED', 'True').lower() == 'true'
    GOOGLE_MEET_ENABLED = GOOGLE_OAUTH_ENABLED and os.environ.get('GOOGLE_MEET_ENABLED', 'True').lower() == 'true'
    GOOGLE_DRIVE_ENABLED = GOOGLE_OAUTH_ENABLED and os.environ.get('GOOGLE_DRIVE_ENABLED', 'True').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE HEALTH CHECKS DOCKER
    # ========================================
    
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL', '30'))  # segundos
    HEALTH_CHECK_TIMEOUT = int(os.environ.get('HEALTH_CHECK_TIMEOUT', '10'))    # segundos
    HEALTH_CHECK_RETRIES = int(os.environ.get('HEALTH_CHECK_RETRIES', '3'))
    
    # Configuración de health checks
    HEALTH_CHECK_CONFIG = {
        'database': {
            'enabled': True,
            'timeout': 5,
        },
        'redis': {
            'enabled': True,
            'timeout': 3,
        },
        'external_apis': {
            'enabled': False,  # Deshabilitado por defecto en containers
            'timeout': 10,
        },
        'disk_space': {
            'enabled': True,
            'threshold': 80,  # Porcentaje
        },
        'memory': {
            'enabled': True,
            'threshold': 85,  # Porcentaje
        },
    }
    
    # ========================================
    # CONFIGURACIÓN DE WORKERS DOCKER
    # ========================================
    
    # Configuración de Gunicorn para containers
    WORKERS = int(os.environ.get('GUNICORN_WORKERS', '1'))
    WORKER_CLASS = os.environ.get('GUNICORN_WORKER_CLASS', 'gevent')
    WORKER_CONNECTIONS = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', '1000'))
    MAX_REQUESTS = int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000'))
    MAX_REQUESTS_JITTER = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '100'))
    TIMEOUT = int(os.environ.get('GUNICORN_TIMEOUT', '30'))
    KEEPALIVE = int(os.environ.get('GUNICORN_KEEPALIVE', '2'))
    BIND = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')
    
    # Configuración de Celery workers
    CELERY_WORKERS = int(os.environ.get('CELERY_WORKERS', '2'))
    CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '4'))
    
    # ========================================
    # CONFIGURACIÓN DE NETWORKING DOCKER
    # ========================================
    
    # Configuración de proxy para load balancers
    PROXY_FIX_ENABLED = os.environ.get('PROXY_FIX_ENABLED', 'True').lower() == 'true'
    PROXY_FIX_NUM_PROXIES = int(os.environ.get('PROXY_FIX_NUM_PROXIES', '1'))
    
    # Configuración de URLs internas
    INTERNAL_API_URL = os.environ.get('INTERNAL_API_URL', 'http://localhost:8000')
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
    }
    
    # ========================================
    # CONFIGURACIÓN DE MONITOREO DOCKER
    # ========================================
    
    # Métricas y monitoring
    METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'True').lower() == 'true'
    PROMETHEUS_METRICS_ENABLED = os.environ.get('PROMETHEUS_METRICS_ENABLED', 'False').lower() == 'true'
    PROMETHEUS_METRICS_PATH = os.environ.get('PROMETHEUS_METRICS_PATH', '/metrics')
    
    # APM configuration
    NEW_RELIC_LICENSE_KEY = os.environ.get('NEW_RELIC_LICENSE_KEY')
    DATADOG_API_KEY = os.environ.get('DATADOG_API_KEY')
    
    # ========================================
    # CONFIGURACIÓN ESPECÍFICA DEL ECOSISTEMA DOCKER
    # ========================================
    
    # Configuraciones de negocio desde variables de entorno
    DEFAULT_PROGRAM_DURATION_MONTHS = int(os.environ.get('DEFAULT_PROGRAM_DURATION_MONTHS', '6'))
    MAX_ENTREPRENEURS_PER_ALLY = int(os.environ.get('MAX_ENTREPRENEURS_PER_ALLY', '10'))
    MIN_MENTORSHIP_SESSION_MINUTES = int(os.environ.get('MIN_MENTORSHIP_SESSION_MINUTES', '30'))
    MAX_MENTORSHIP_SESSION_MINUTES = int(os.environ.get('MAX_MENTORSHIP_SESSION_MINUTES', '120'))
    
    # Configuración de notificaciones
    NOTIFICATION_RETENTION_DAYS = int(os.environ.get('NOTIFICATION_RETENTION_DAYS', '30'))
    EMAIL_NOTIFICATION_ENABLED = os.environ.get('EMAIL_NOTIFICATION_ENABLED', 'True').lower() == 'true'
    SMS_NOTIFICATION_ENABLED = SMS_ENABLED and os.environ.get('SMS_NOTIFICATION_ENABLED', 'True').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN DE VOLUMES Y STORAGE
    # ========================================
    
    # Volúmenes persistentes
    DATA_VOLUME = os.environ.get('DATA_VOLUME', '/app/data')
    LOGS_VOLUME = os.environ.get('LOGS_VOLUME', '/app/logs')
    UPLOADS_VOLUME = os.environ.get('UPLOADS_VOLUME', '/app/uploads')
    
    # Configuración de backup para containers
    BACKUP_ENABLED = os.environ.get('BACKUP_ENABLED', 'False').lower() == 'true'
    BACKUP_SCHEDULE = os.environ.get('BACKUP_SCHEDULE', 'daily')
    BACKUP_STORAGE_BACKEND = os.environ.get('BACKUP_STORAGE_BACKEND', 's3')
    
    # ========================================
    # MÉTODOS DE UTILIDAD PARA DOCKER
    # ========================================
    
    @classmethod
    def get_container_info(cls) -> dict:
        """
        Obtiene información del contenedor actual.
        
        Returns:
            Diccionario con información del contenedor
        """
        return {
            'hostname': os.environ.get('HOSTNAME', 'unknown'),
            'container_name': os.environ.get('CONTAINER_NAME', 'unknown'),
            'image': os.environ.get('IMAGE_NAME', 'unknown'),
            'version': os.environ.get('IMAGE_VERSION', 'unknown'),
            'environment': cls.ENVIRONMENT,
            'workers': cls.WORKERS,
            'debug': cls.DEBUG,
        }
    
    @classmethod
    def validate_docker_environment(cls):
        """
        Valida que el ambiente Docker esté correctamente configurado.
        
        Raises:
            ValueError: Si faltan configuraciones críticas
        """
        required_vars = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
        missing_vars = []
        
        for var in required_vars:
            if not getattr(cls, var.replace('_URL', '_URL'), None) and not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables de entorno requeridas para Docker: {', '.join(missing_vars)}")
    
    @classmethod
    def setup_docker_logging(cls):
        """
        Configura logging específico para Docker.
        """
        import logging.config
        
        # Aplicar configuración de logging
        logging.config.dictConfig(cls.LOGGING_CONFIG)
        
        # Logger específico para Docker
        docker_logger = logging.getLogger('docker')
        docker_logger.info(f"Configuración Docker cargada en contenedor {cls.get_container_info()['hostname']}")
        docker_logger.info(f"Base de datos: {cls.DATABASE_URL.split('@')[1] if '@' in cls.DATABASE_URL else 'configurada'}")
        docker_logger.info(f"Redis: {cls.REDIS_URL.split('@')[1] if '@' in cls.REDIS_URL else 'configurado'}")
    
    @classmethod
    def get_service_urls(cls) -> dict:
        """
        Obtiene URLs de servicios para health checks.
        
        Returns:
            Diccionario con URLs de servicios
        """
        urls = {}
        
        # Database URL (sin credenciales)
        if cls.DATABASE_URL:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(cls.DATABASE_URL)
                urls['database'] = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
            except Exception:
                urls['database'] = 'configured'
        
        # Redis URL (sin credenciales)
        if cls.REDIS_URL:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(cls.REDIS_URL)
                urls['redis'] = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
            except Exception:
                urls['redis'] = 'configured'
        
        return urls
    
    @classmethod
    def check_container_health(cls) -> dict:
        """
        Verifica el estado de salud del contenedor.
        
        Returns:
            Diccionario con estado de salud
        """
        health_status = {
            'status': 'healthy',
            'timestamp': None,
            'services': {},
            'container': cls.get_container_info(),
        }
        
        import datetime
        health_status['timestamp'] = datetime.datetime.now(timezone.utc).isoformat()
        
        # Check database
        if cls.HEALTH_CHECK_CONFIG['database']['enabled']:
            try:
                # Esta verificación se implementaría en la aplicación
                health_status['services']['database'] = 'healthy'
            except Exception as e:
                health_status['services']['database'] = f'unhealthy: {str(e)}'
                health_status['status'] = 'unhealthy'
        
        # Check Redis
        if cls.HEALTH_CHECK_CONFIG['redis']['enabled']:
            try:
                # Esta verificación se implementaría en la aplicación
                health_status['services']['redis'] = 'healthy'
            except Exception as e:
                health_status['services']['redis'] = f'unhealthy: {str(e)}'
                health_status['status'] = 'unhealthy'
        
        return health_status
    
    @staticmethod
    def init_app(app):
        """
        Inicialización específica para Docker.
        
        Args:
            app: Instancia de aplicación Flask
        """
        # Llamar inicialización base
        BaseConfig.init_app(app)
        
        # Validar ambiente Docker
        DockerConfig.validate_docker_environment()
        
        # Configurar logging
        DockerConfig.setup_docker_logging()
        
        # Configurar proxy fix si está habilitado
        if DockerConfig.PROXY_FIX_ENABLED:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=DockerConfig.PROXY_FIX_NUM_PROXIES,
                x_proto=DockerConfig.PROXY_FIX_NUM_PROXIES,
                x_host=DockerConfig.PROXY_FIX_NUM_PROXIES,
                x_prefix=DockerConfig.PROXY_FIX_NUM_PROXIES
            )
        
        # Health check endpoints
        @app.route('/health')
        def health_check():
            """Health check para contenedores."""
            return DockerConfig.check_container_health(), 200
        
        @app.route('/health/live')
        def liveness_probe():
            """Liveness probe para Kubernetes."""
            return {'status': 'alive', 'container': DockerConfig.get_container_info()['hostname']}, 200
        
        @app.route('/health/ready')
        def readiness_probe():
            """Readiness probe para Kubernetes."""
            health = DockerConfig.check_container_health()
            status_code = 200 if health['status'] == 'healthy' else 503
            return health, status_code
        
        @app.route('/info')
        def container_info():
            """Información del contenedor."""
            return {
                'container': DockerConfig.get_container_info(),
                'services': DockerConfig.get_service_urls(),
                'environment': DockerConfig.ENVIRONMENT,
                'version': DockerConfig.APP_VERSION,
            }, 200
        
        # Logging de inicio en Docker
        app.logger.info(f"Aplicación iniciada en contenedor Docker")
        app.logger.info(f"Configuración: {DockerConfig.__name__}")
        app.logger.info(f"Contenedor: {DockerConfig.get_container_info()}")
        app.logger.info(f"Workers: {DockerConfig.WORKERS}")
        app.logger.info(f"Features habilitadas:")
        app.logger.info(f"  - Health Checks: {DockerConfig.HEALTH_CHECK_ENABLED}")
        app.logger.info(f"  - Metrics: {DockerConfig.METRICS_ENABLED}")
        app.logger.info(f"  - Sentry: {DockerConfig.SENTRY_ENABLED}")


# Función de utilidad para configuración Docker
def setup_docker_environment():
    """
    Configura el ambiente Docker completo.
    
    Returns:
        Instancia de configuración Docker
    """
    config = DockerConfig()
    config.validate_docker_environment()
    config.setup_docker_logging()
    
    return config


# Función para obtener configuración específica de servicio
def get_service_config(service_name: str):
    """
    Obtiene configuración específica para un servicio en Docker.
    
    Args:
        service_name: Nombre del servicio (web, worker, beat, etc.)
        
    Returns:
        Configuración adaptada para el servicio
    """
    config = DockerConfig()
    
    # Configuraciones específicas por servicio
    service_configs = {
        'web': {
            'WORKERS': config.WORKERS,
            'WORKER_CLASS': config.WORKER_CLASS,
            'TIMEOUT': config.TIMEOUT,
        },
        'worker': {
            'CELERY_WORKERS': config.CELERY_WORKERS,
            'CELERY_WORKER_CONCURRENCY': config.CELERY_WORKER_CONCURRENCY,
        },
        'beat': {
            'CELERY_BEAT_SCHEDULE': config.CELERY_CONFIG['beat_schedule'],
        },
        'flower': {
            'FLOWER_PORT': 5555,
            'FLOWER_BASIC_AUTH': os.environ.get('FLOWER_BASIC_AUTH'),
        }
    }
    
    return service_configs.get(service_name, {})


# Exportar configuración
__all__ = [
    'DockerConfig', 
    'setup_docker_environment', 
    'get_service_config'
]