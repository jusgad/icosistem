# -*- coding: utf-8 -*-
"""
Configuración Base del Ecosistema de Emprendimiento
=================================================

Esta clase base contiene todas las configuraciones comunes que son
heredadas por los diferentes ambientes (desarrollo, producción, testing, docker).

Incluye configuraciones para:
- Flask y extensiones principales
- Base de datos y almacenamiento
- Servicios externos (Google, email, SMS)
- Seguridad y autenticación
- Logging y monitoreo
- Funcionalidades específicas del ecosistema

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import secrets
from datetime import timedelta
from typing import Optional, Any
from urllib.parse import quote_plus


class BaseConfig:
    """
    Configuración base para el ecosistema de emprendimiento.
    
    Contiene todas las configuraciones comunes que son heredadas
    por las configuraciones específicas de cada ambiente.
    """
    
    # ========================================
    # CONFIGURACIÓN BÁSICA DE FLASK
    # ========================================
    
    # Clave secreta para sesiones y CSRF
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Configuración de aplicación
    APP_NAME = os.environ.get('APP_NAME', 'Ecosistema de Emprendimiento')
    APP_VERSION = os.environ.get('APP_VERSION', '2.0.0')
    APP_DESCRIPTION = os.environ.get(
        'APP_DESCRIPTION', 
        'Plataforma integral para el desarrollo y acompañamiento de emprendedores'
    )
    
    # URLs y dominios
    SERVER_NAME = os.environ.get('SERVER_NAME')
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '/')
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get('SESSION_LIFETIME_HOURS', '24'))
    )
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configuración JSON
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False
    
    # ========================================
    # CONFIGURACIÓN DE BASE DE DATOS
    # ========================================
    
    # PostgreSQL principal
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/ecosistema_emprendimiento')
    
    # Corregir URLs de Heroku si es necesario
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = os.environ.get('SQLALCHEMY_RECORD_QUERIES', 'False').lower() == 'true'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '300')),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '20')),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '0')),
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '5')),
    }
    
    # ========================================
    # CONFIGURACIÓN DE REDIS Y CACHE
    # ========================================
    
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Configuración de cache
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '300'))
    CACHE_KEY_PREFIX = os.environ.get('CACHE_KEY_PREFIX', 'ecosistema:')
    
    # ========================================
    # CONFIGURACIÓN DE CELERY (TAREAS ASÍNCRONAS)
    # ========================================
    
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or REDIS_URL
    
    CELERY_CONFIG = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': os.environ.get('TIMEZONE', 'UTC'),
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': int(os.environ.get('CELERY_TASK_TIME_LIMIT', '1800')),  # 30 min
        'task_soft_time_limit': int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '1200')),  # 20 min
        'worker_prefetch_multiplier': int(os.environ.get('CELERY_WORKER_PREFETCH', '1')),
        'worker_max_tasks_per_child': int(os.environ.get('CELERY_WORKER_MAX_TASKS', '1000')),
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
        },
    }
    
    # ========================================
    # CONFIGURACIÓN DE AUTENTICACIÓN Y OAUTH
    # ========================================
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    
    # Configuración OAuth
    OAUTH_PROVIDERS = {
        'google': {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'server_metadata_url': 'https://accounts.google.com/.well-known/openid_configuration',
            'client_kwargs': {
                'scope': ' '.join([
                    'openid',
                    'email',
                    'profile',
                    'https://www.googleapis.com/auth/calendar',
                    'https://www.googleapis.com/auth/drive.file'
                ])
            }
        }
    }
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_HOURS', '1'))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES_DAYS', '30'))
    )
    
    # ========================================
    # CONFIGURACIÓN DE SEGURIDAD
    # ========================================
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('CSRF_TIME_LIMIT', '3600'))
    WTF_CSRF_SSL_STRICT = os.environ.get('CSRF_SSL_STRICT', 'True').lower() == 'true'
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True').lower() == 'true'
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '1000 per hour')
    
    # Rate limits específicos
    RATELIMIT_LOGIN = os.environ.get('RATELIMIT_LOGIN', '5 per minute')
    RATELIMIT_REGISTER = os.environ.get('RATELIMIT_REGISTER', '3 per minute')
    RATELIMIT_API = os.environ.get('RATELIMIT_API', '100 per minute')
    RATELIMIT_UPLOAD = os.environ.get('RATELIMIT_UPLOAD', '10 per minute')
    
    # Configuración de passwords con seguridad mejorada
    PASSWORD_MIN_LENGTH = int(os.environ.get('PASSWORD_MIN_LENGTH', '12'))
    PASSWORD_REQUIRE_UPPERCASE = os.environ.get('PASSWORD_REQUIRE_UPPERCASE', 'True').lower() == 'true'
    PASSWORD_REQUIRE_LOWERCASE = os.environ.get('PASSWORD_REQUIRE_LOWERCASE', 'True').lower() == 'true'
    PASSWORD_REQUIRE_NUMBERS = os.environ.get('PASSWORD_REQUIRE_NUMBERS', 'True').lower() == 'true'
    PASSWORD_REQUIRE_SYMBOLS = os.environ.get('PASSWORD_REQUIRE_SYMBOLS', 'True').lower() == 'true'
    PASSWORD_BLACKLIST_COMMON = os.environ.get('PASSWORD_BLACKLIST_COMMON', 'True').lower() == 'true'
    PASSWORD_CHECK_BREACHED = os.environ.get('PASSWORD_CHECK_BREACHED', 'False').lower() == 'true'
    
    # Configuración SSL/HTTPS
    SSL_REDIRECT = os.environ.get('SSL_REDIRECT', 'False').lower() == 'true'
    SSL_DISABLE = os.environ.get('SSL_DISABLE', 'False').lower() == 'true'
    
    # CORS Configuration
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'True').lower() == 'true'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Security Headers Configuration
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'X-Permitted-Cross-Domain-Policies': 'none',
        'X-Download-Options': 'noopen',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' *.googleapis.com *.google.com; "
            "style-src 'self' 'unsafe-inline' *.googleapis.com fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com data:; "
            "img-src 'self' data: https: *.google.com *.googleapis.com; "
            "connect-src 'self' *.google.com *.googleapis.com; "
            "frame-src 'self' *.google.com *.youtube.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'self';"
        ),
        'Permissions-Policy': (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "payment=(), "
            "usb=()"
        )
    }
    
    # Additional security configurations
    SECURITY_REGISTERABLE = os.environ.get('SECURITY_REGISTERABLE', 'True').lower() == 'true'
    SECURITY_RECOVERABLE = os.environ.get('SECURITY_RECOVERABLE', 'True').lower() == 'true'
    SECURITY_CHANGEABLE = os.environ.get('SECURITY_CHANGEABLE', 'True').lower() == 'true'
    SECURITY_CONFIRMABLE = os.environ.get('SECURITY_CONFIRMABLE', 'True').lower() == 'true'
    SECURITY_TRACKABLE = os.environ.get('SECURITY_TRACKABLE', 'True').lower() == 'true'
    
    # Session security
    SESSION_PERMANENT = False
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'True').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # Encryption configuration
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or secrets.token_urlsafe(32)
    
    # Account lockout configuration
    ACCOUNT_LOCKOUT_ENABLED = os.environ.get('ACCOUNT_LOCKOUT_ENABLED', 'True').lower() == 'true'
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
    LOCKOUT_DURATION_MINUTES = int(os.environ.get('LOCKOUT_DURATION_MINUTES', '15'))
    
    # ========================================
    # CONFIGURACIÓN DE EMAIL
    # ========================================
    
    # Configuración SMTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME
    
    # Configuración de servicios de email
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'smtp')  # smtp, sendgrid, mailgun
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN')
    
    # Email templates y configuración
    EMAIL_VERIFICATION_REQUIRED = os.environ.get('EMAIL_VERIFICATION_REQUIRED', 'True').lower() == 'true'
    EMAIL_CONFIRMATION_SALT = os.environ.get('EMAIL_CONFIRMATION_SALT') or 'email-confirmation'
    PASSWORD_RESET_SALT = os.environ.get('PASSWORD_RESET_SALT') or 'password-reset'
    
    # ========================================
    # CONFIGURACIÓN DE SMS
    # ========================================
    
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'False').lower() == 'true'
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'twilio')  # twilio, aws_sns
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # AWS SNS
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # ========================================
    # CONFIGURACIÓN DE ALMACENAMIENTO DE ARCHIVOS
    # ========================================
    
    # Configuración general de uploads
    UPLOAD_ENABLED = os.environ.get('UPLOAD_ENABLED', 'True').lower() == 'true'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', str(16 * 1024 * 1024)))  # 16MB
    
    # Tipos de archivo permitidos
    ALLOWED_EXTENSIONS = {
        'images': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'},
        'videos': {'mp4', 'avi', 'mov', 'wmv', 'flv'},
        'audio': {'mp3', 'wav', 'ogg', 'aac'}
    }
    
    # Storage backends
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local')  # local, s3, gcs
    
    # AWS S3
    AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', AWS_REGION)
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
    
    # Google Cloud Storage
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
    GCS_PROJECT_ID = os.environ.get('GCS_PROJECT_ID')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    # ========================================
    # CONFIGURACIÓN DE SERVICIOS GOOGLE
    # ========================================
    
    # Google Calendar
    GOOGLE_CALENDAR_ENABLED = bool(GOOGLE_CLIENT_ID)
    GOOGLE_CALENDAR_TIMEZONE = os.environ.get('GOOGLE_CALENDAR_TIMEZONE', 'America/Bogota')
    
    # Google Meet
    GOOGLE_MEET_ENABLED = bool(GOOGLE_CLIENT_ID)
    
    # Google Drive
    GOOGLE_DRIVE_ENABLED = bool(GOOGLE_CLIENT_ID)
    GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
    
    # ========================================
    # CONFIGURACIÓN DE WEBSOCKETS
    # ========================================
    
    SOCKETIO_ENABLED = os.environ.get('SOCKETIO_ENABLED', 'True').lower() == 'true'
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'threading')
    SOCKETIO_REDIS_URL = REDIS_URL
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS
    
    # ========================================
    # CONFIGURACIÓN DE LOGGING
    # ========================================
    
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/ecosistema.log')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', str(10 * 1024 * 1024)))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    
    # Logging externo
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    SENTRY_ENABLED = bool(SENTRY_DSN)
    
    # ========================================
    # CONFIGURACIÓN DE ANALYTICS Y MONITOREO
    # ========================================
    
    ANALYTICS_ENABLED = os.environ.get('ANALYTICS_ENABLED', 'True').lower() == 'true'
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID')
    
    # Métricas internas
    METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'True').lower() == 'true'
    METRICS_RETENTION_DAYS = int(os.environ.get('METRICS_RETENTION_DAYS', '90'))
    
    # Health checks
    HEALTH_CHECK_ENABLED = os.environ.get('HEALTH_CHECK_ENABLED', 'True').lower() == 'true'
    
    # ========================================
    # CONFIGURACIÓN ESPECÍFICA DEL ECOSISTEMA
    # ========================================
    
    # Configuración de emprendimiento
    DEFAULT_PROGRAM_DURATION_MONTHS = int(os.environ.get('DEFAULT_PROGRAM_DURATION_MONTHS', '6'))
    MAX_ENTREPRENEURS_PER_ALLY = int(os.environ.get('MAX_ENTREPRENEURS_PER_ALLY', '10'))
    MIN_MENTORSHIP_SESSION_MINUTES = int(os.environ.get('MIN_MENTORSHIP_SESSION_MINUTES', '30'))
    MAX_MENTORSHIP_SESSION_MINUTES = int(os.environ.get('MAX_MENTORSHIP_SESSION_MINUTES', '120'))
    
    # Configuración de roles y permisos
    DEFAULT_USER_ROLE = os.environ.get('DEFAULT_USER_ROLE', 'entrepreneur')
    ADMIN_EMAIL_DOMAINS = os.environ.get('ADMIN_EMAIL_DOMAINS', '').split(',')
    
    # Configuración de notificaciones
    NOTIFICATION_RETENTION_DAYS = int(os.environ.get('NOTIFICATION_RETENTION_DAYS', '30'))
    EMAIL_NOTIFICATION_ENABLED = os.environ.get('EMAIL_NOTIFICATION_ENABLED', 'True').lower() == 'true'
    SMS_NOTIFICATION_ENABLED = SMS_ENABLED and os.environ.get('SMS_NOTIFICATION_ENABLED', 'False').lower() == 'true'
    PUSH_NOTIFICATION_ENABLED = os.environ.get('PUSH_NOTIFICATION_ENABLED', 'False').lower() == 'true'
    
    # Configuración de reuniones
    MEETING_BUFFER_MINUTES = int(os.environ.get('MEETING_BUFFER_MINUTES', '15'))
    MAX_MEETING_DURATION_HOURS = int(os.environ.get('MAX_MEETING_DURATION_HOURS', '4'))
    MEETING_REMINDER_MINUTES = [
        int(x.strip()) for x in os.environ.get('MEETING_REMINDER_MINUTES', '15,60,1440').split(',')
    ]
    
    # Configuración de documentos
    DOCUMENT_RETENTION_YEARS = int(os.environ.get('DOCUMENT_RETENTION_YEARS', '7'))
    AUTO_BACKUP_ENABLED = os.environ.get('AUTO_BACKUP_ENABLED', 'True').lower() == 'true'
    
    # Configuración de reportes
    REPORT_CACHE_TIMEOUT = int(os.environ.get('REPORT_CACHE_TIMEOUT', '3600'))  # 1 hora
    AUTO_REPORT_GENERATION = os.environ.get('AUTO_REPORT_GENERATION', 'True').lower() == 'true'
    
    # Configuración de API
    API_VERSION = os.environ.get('API_VERSION', 'v1')
    API_PAGINATION_MAX_PER_PAGE = int(os.environ.get('API_PAGINATION_MAX_PER_PAGE', '100'))
    API_PAGINATION_DEFAULT_PER_PAGE = int(os.environ.get('API_PAGINATION_DEFAULT_PER_PAGE', '20'))
    
    # ========================================
    # CONFIGURACIÓN DE MONEDA Y LOCALIZACIÓN
    # ========================================
    
    DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY', 'COP')
    SUPPORTED_CURRENCIES = os.environ.get('SUPPORTED_CURRENCIES', 'COP,USD,EUR').split(',')
    DEFAULT_LOCALE = os.environ.get('DEFAULT_LOCALE', 'es_CO')
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Bogota')
    
    # API de conversión de monedas
    CURRENCY_API_KEY = os.environ.get('CURRENCY_API_KEY')
    CURRENCY_API_PROVIDER = os.environ.get('CURRENCY_API_PROVIDER', 'fixer')
    
    # ========================================
    # CONFIGURACIÓN DE MANTENIMIENTO
    # ========================================
    
    MAINTENANCE_MODE = os.environ.get('MAINTENANCE_MODE', 'False').lower() == 'true'
    MAINTENANCE_MESSAGE = os.environ.get(
        'MAINTENANCE_MESSAGE', 
        'El sistema está en mantenimiento. Volveremos pronto.'
    )
    
    # ========================================
    # MÉTODOS DE UTILIDAD
    # ========================================
    
    @classmethod
    def get_database_uri(cls, database_name: Optional[str] = None) -> str:
        """
        Construye URI de base de datos con nombre específico.
        
        Args:
            database_name: Nombre específico de la base de datos
            
        Returns:
            URI de conexión a la base de datos
        """
        if not database_name:
            return cls.DATABASE_URL
        
        # Parsear URL existente y cambiar nombre de DB
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(cls.DATABASE_URL)
        new_path = f'/{database_name}'
        new_parsed = parsed._replace(path=new_path)
        return urlunparse(new_parsed)
    
    @classmethod
    def get_redis_uri(cls, database_number: int = 0) -> str:
        """
        Construye URI de Redis con número de base de datos específico.
        
        Args:
            database_number: Número de base de datos Redis (0-15)
            
        Returns:
            URI de conexión a Redis
        """
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(cls.REDIS_URL)
        new_path = f'/{database_number}'
        new_parsed = parsed._replace(path=new_path)
        return urlunparse(new_parsed)
    
    @classmethod
    def is_extension_allowed(cls, filename: str, category: str = 'documents') -> bool:
        """
        Verifica si una extensión de archivo está permitida.
        
        Args:
            filename: Nombre del archivo
            category: Categoría de archivo (images, documents, videos, audio)
            
        Returns:
            True si la extensión está permitida
        """
        if '.' not in filename:
            return False
        
        ext = filename.rsplit('.', 1)[1].lower()
        allowed = cls.ALLOWED_EXTENSIONS.get(category, set())
        return ext in allowed
    
    @classmethod
    def get_upload_path(cls, category: str, filename: str) -> str:
        """
        Construye la ruta de upload para un archivo.
        
        Args:
            category: Categoría del archivo
            filename: Nombre del archivo
            
        Returns:
            Ruta completa para el archivo
        """
        import os
        return os.path.join(cls.UPLOAD_FOLDER, category, filename)
    
    @staticmethod
    def init_app(app):
        """
        Inicialización específica de la aplicación Flask.
        
        Args:
            app: Instancia de aplicación Flask
        """
        pass


# Función de utilidad para obtener configuración por clave
def get_config_value(key: str, default: Any = None) -> Any:
    """
    Obtiene un valor de configuración de forma segura.
    
    Args:
        key: Clave de configuración
        default: Valor por defecto si no existe
        
    Returns:
        Valor de configuración o default
    """
    return getattr(BaseConfig, key, default)


# Validaciones de configuración
def validate_required_config() -> list[str]:
    """
    Valida que las configuraciones críticas estén presentes.
    
    Returns:
        Lista de errores de configuración
    """
    errors = []
    
    # Validaciones críticas
    if not BaseConfig.SECRET_KEY:
        errors.append("SECRET_KEY es requerida")
    
    if not BaseConfig.DATABASE_URL:
        errors.append("DATABASE_URL es requerida")
    
    if BaseConfig.GOOGLE_OAUTH_ENABLED and not BaseConfig.GOOGLE_CLIENT_SECRET:
        errors.append("GOOGLE_CLIENT_SECRET es requerido cuando OAuth está habilitado")
    
    if BaseConfig.EMAIL_VERIFICATION_REQUIRED and not BaseConfig.MAIL_USERNAME:
        errors.append("MAIL_USERNAME es requerido cuando verificación de email está habilitada")
    
    return errors