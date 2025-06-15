# -*- coding: utf-8 -*-
"""
Configuración de Testing del Ecosistema de Emprendimiento
========================================================

Esta configuración está optimizada para testing automatizado, CI/CD y
desarrollo dirigido por pruebas (TDD), proporcionando un ambiente
controlado, rápido y reproducible para todas las pruebas.

Características principales:
- Base de datos en memoria para velocidad máxima
- Servicios externos completamente mockeados
- Configuración de fixtures y datos de prueba
- Logging optimizado para debugging de tests
- Configuración de coverage y métricas de calidad
- Support para testing paralelo y distributed
- Configuración específica para diferentes tipos de testing
- Integration con pytest, coverage, y herramientas de CI/CD

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import tempfile
from datetime import timedelta
from .base import BaseConfig


class TestingConfig(BaseConfig):
    """
    Configuración específica para ambiente de testing.
    
    Optimizada para ejecución rápida de pruebas, servicios mockeados
    y ambiente completamente controlado y reproducible.
    """
    
    # ========================================
    # CONFIGURACIÓN BÁSICA DE TESTING
    # ========================================
    
    # Habilitar modo testing
    DEBUG = False  # False para testing más realista
    TESTING = True
    
    # Environment identifier
    ENV = 'testing'
    ENVIRONMENT = 'testing'
    
    # Configuración de sesiones para testing
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)  # Corto para testing
    SESSION_COOKIE_SECURE = False  # HTTP OK en testing
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configuración de aplicación para testing
    SECRET_KEY = 'testing-secret-key-not-for-production-use-12345678'
    SERVER_NAME = 'localhost.localdomain'
    PREFERRED_URL_SCHEME = 'http'  # HTTP para simplicidad en testing
    
    # ========================================
    # CONFIGURACIÓN DE BASE DE DATOS TESTING
    # ========================================
    
    # Base de datos en memoria para testing ultra-rápido
    TEST_DATABASE_URL = os.environ.get(
        'TEST_DATABASE_URL',
        'sqlite:///:memory:'  # En memoria por defecto
    )
    
    # Para testing con PostgreSQL si se requiere
    POSTGRES_TEST_DATABASE_URL = os.environ.get(
        'POSTGRES_TEST_DATABASE_URL',
        'postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_test'
    )
    
    # Usar SQLite en memoria por defecto, PostgreSQL si se especifica
    DATABASE_URL = TEST_DATABASE_URL
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    
    # Configuración optimizada para testing
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True  # Para debugging de tests
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO_TESTS', 'False').lower() == 'true'
    
    # Engine options para testing
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': False,  # No necesario en testing
        'pool_recycle': -1,      # Sin reciclado en testing
        'pool_timeout': 5,       # Timeout corto
        'echo': SQLALCHEMY_ECHO,
        'strategy': 'mock' if DATABASE_URL.startswith('sqlite:///:memory:') else 'plain',
    }
    
    # ========================================
    # CONFIGURACIÓN DE REDIS Y CACHE TESTING
    # ========================================
    
    # Redis para testing (base de datos separada)
    REDIS_URL = os.environ.get('REDIS_TEST_URL', 'redis://localhost:6379/15')  # DB 15 para tests
    
    # Cache simple para testing
    CACHE_TYPE = 'SimpleCache'  # Cache en memoria para testing
    CACHE_DEFAULT_TIMEOUT = 60  # TTL corto para testing
    CACHE_KEY_PREFIX = 'test:'
    
    # Configuración alternativa con Redis si está disponible
    CACHE_CONFIG = {
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
        'CACHE_KEY_PREFIX': CACHE_KEY_PREFIX,
    }
    
    # Override con Redis si está disponible y se requiere
    if os.environ.get('USE_REDIS_IN_TESTS', 'False').lower() == 'true':
        CACHE_CONFIG = {
            'CACHE_TYPE': 'RedisCache',
            'CACHE_REDIS_URL': REDIS_URL,
            'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
            'CACHE_KEY_PREFIX': CACHE_KEY_PREFIX,
        }
    
    # ========================================
    # CONFIGURACIÓN DE CELERY TESTING
    # ========================================
    
    # Celery en modo eager para testing síncrono
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = 'memory://'  # Broker en memoria
    CELERY_RESULT_BACKEND = 'cache+memory://'  # Backend en memoria
    
    # Configuración de Celery para testing
    CELERY_CONFIG = {
        'task_always_eager': True,
        'task_eager_propagates': True,
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 60,  # 1 minuto máximo para tests
        'task_soft_time_limit': 45,
        'worker_disable_rate_limits': True,
        'beat_schedule': {},  # Sin schedule en testing
    }
    
    # ========================================
    # CONFIGURACIÓN DE SEGURIDAD TESTING
    # ========================================
    
    # CSRF deshabilitado para facilitar testing
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False
    
    # Rate limiting deshabilitado en testing
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URL = 'memory://'
    
    # Sin SSL en testing
    SSL_REDIRECT = False
    SSL_DISABLE = True
    
    # CORS muy permisivo para testing
    CORS_ENABLED = True
    CORS_ORIGINS = ['*']
    CORS_SUPPORTS_CREDENTIALS = True
    
    # Configuración de passwords simplificada para testing
    PASSWORD_MIN_LENGTH = 6  # Más corto para testing
    PASSWORD_REQUIRE_UPPERCASE = False
    PASSWORD_REQUIRE_LOWERCASE = False
    PASSWORD_REQUIRE_NUMBERS = False
    PASSWORD_REQUIRE_SYMBOLS = False
    
    # ========================================
    # CONFIGURACIÓN DE EMAIL TESTING
    # ========================================
    
    # Email completamente mockeado
    MAIL_SUPPRESS_SEND = True
    MAIL_DEBUG = False  # False para no spam en tests
    EMAIL_BACKEND = 'testing'  # Backend especial para testing
    
    # Configuración mock de email
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 25
    MAIL_USE_TLS = False
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'test@example.com'
    MAIL_PASSWORD = 'test-password'
    MAIL_DEFAULT_SENDER = 'test@ecosistema.local'
    
    # Email verification deshabilitada para testing
    EMAIL_VERIFICATION_REQUIRED = False
    
    # ========================================
    # CONFIGURACIÓN DE SMS TESTING
    # ========================================
    
    # SMS completamente mockeado
    SMS_ENABLED = True
    SMS_PROVIDER = 'mock'
    SMS_SIMULATION_MODE = True
    
    # Credenciales mock para testing
    TWILIO_ACCOUNT_SID = 'test_account_sid'
    TWILIO_AUTH_TOKEN = 'test_auth_token'
    TWILIO_PHONE_NUMBER = '+1234567890'
    
    # ========================================
    # CONFIGURACIÓN DE ALMACENAMIENTO TESTING
    # ========================================
    
    # Storage local temporal para testing
    STORAGE_BACKEND = 'local'
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix='ecosistema_test_uploads_')
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1MB para testing
    
    # Configuración de archivos para testing
    UPLOAD_ENABLED = True
    
    # ========================================
    # CONFIGURACIÓN DE WEBSOCKETS TESTING
    # ========================================
    
    # WebSockets simplificados para testing
    SOCKETIO_ENABLED = True
    SOCKETIO_ASYNC_MODE = 'threading'  # Threading para testing
    SOCKETIO_REDIS_URL = None  # Sin Redis para WebSockets en testing
    SOCKETIO_LOGGER = False
    SOCKETIO_ENGINEIO_LOGGER = False
    
    # ========================================
    # CONFIGURACIÓN DE LOGGING TESTING
    # ========================================
    
    LOG_LEVEL = 'WARNING'  # Solo warnings y errores en testing normal
    LOG_FORMAT = '[TEST] %(levelname)s in %(module)s: %(message)s'
    LOG_FILE = None  # Sin archivo de log en testing por defecto
    LOG_TO_CONSOLE = os.environ.get('TEST_LOG_TO_CONSOLE', 'False').lower() == 'true'
    
    # Configuración de logging para testing
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'test': {
                'format': LOG_FORMAT,
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'WARNING',
                'formatter': 'test',
                'stream': 'ext://sys.stdout',
            },
            'null': {
                'class': 'logging.NullHandler',
            },
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['null'],  # Por defecto sin logging
        },
        'loggers': {
            'test': {
                'level': 'DEBUG' if LOG_TO_CONSOLE else 'WARNING',
                'handlers': ['console'] if LOG_TO_CONSOLE else ['null'],
                'propagate': False,
            },
        },
    }
    
    # Sentry completamente deshabilitado en testing
    SENTRY_ENABLED = False
    SENTRY_DSN = None
    
    # ========================================
    # CONFIGURACIÓN DE ANALYTICS TESTING
    # ========================================
    
    # Analytics deshabilitados en testing
    ANALYTICS_ENABLED = False
    GOOGLE_ANALYTICS_ID = None
    METRICS_ENABLED = False
    
    # ========================================
    # CONFIGURACIÓN DE SERVICIOS EXTERNOS TESTING
    # ========================================
    
    # Google services completamente mockeados
    GOOGLE_OAUTH_ENABLED = True  # Habilitado pero mockeado
    GOOGLE_CLIENT_ID = 'test_client_id'
    GOOGLE_CLIENT_SECRET = 'test_client_secret'
    
    # Servicios Google mockeados
    GOOGLE_CALENDAR_ENABLED = True
    GOOGLE_MEET_ENABLED = True
    GOOGLE_DRIVE_ENABLED = True
    
    # Modo simulación para todos los servicios externos
    SIMULATION_MODE = True
    MOCK_EXTERNAL_APIS = True
    
    # ========================================
    # CONFIGURACIÓN ESPECÍFICA DE TESTING
    # ========================================
    
    # Configuraciones de negocio simplificadas para testing
    DEFAULT_PROGRAM_DURATION_MONTHS = 1  # Programas de 1 mes para testing
    MAX_ENTREPRENEURS_PER_ALLY = 2  # Límite bajo para testing
    MIN_MENTORSHIP_SESSION_MINUTES = 1  # 1 minuto para testing rápido
    MAX_MENTORSHIP_SESSION_MINUTES = 10  # 10 minutos máximo
    
    # Configuración de notificaciones para testing
    NOTIFICATION_RETENTION_DAYS = 1  # Solo 1 día
    EMAIL_NOTIFICATION_ENABLED = True  # Habilitado pero mockeado
    SMS_NOTIFICATION_ENABLED = True   # Habilitado pero mockeado
    PUSH_NOTIFICATION_ENABLED = False # Deshabilitado para simplicidad
    
    # Configuración de reuniones para testing
    MEETING_BUFFER_MINUTES = 0  # Sin buffer para testing
    MAX_MEETING_DURATION_HOURS = 1  # 1 hora máximo
    MEETING_REMINDER_MINUTES = [1]  # Solo 1 minuto antes
    
    # Configuración de API para testing
    API_PAGINATION_MAX_PER_PAGE = 1000  # Permisivo para testing
    API_PAGINATION_DEFAULT_PER_PAGE = 10  # Páginas pequeñas para testing
    
    # ========================================
    # CONFIGURACIÓN DE FIXTURES Y DATOS DE PRUEBA
    # ========================================
    
    # Control de fixtures
    LOAD_FIXTURES = os.environ.get('LOAD_FIXTURES', 'True').lower() == 'true'
    FIXTURE_DIR = 'tests/fixtures'
    
    # Configuración de datos de prueba
    TEST_DATA_SIZE = os.environ.get('TEST_DATA_SIZE', 'minimal')  # minimal, small, medium
    CREATE_TEST_USERS = True
    TEST_USER_COUNT = {
        'minimal': {'admin': 1, 'entrepreneur': 2, 'ally': 1, 'client': 1},
        'small': {'admin': 1, 'entrepreneur': 5, 'ally': 2, 'client': 2},
        'medium': {'admin': 2, 'entrepreneur': 10, 'ally': 5, 'client': 3},
    }
    
    # Configuración de mocks
    MOCK_EMAIL_SERVICE = True
    MOCK_SMS_SERVICE = True
    MOCK_GOOGLE_SERVICES = True
    MOCK_PAYMENT_SERVICES = True
    MOCK_FILE_STORAGE = True
    
    # ========================================
    # CONFIGURACIÓN DE COVERAGE Y MÉTRICAS
    # ========================================
    
    # Coverage configuration
    COVERAGE_ENABLED = os.environ.get('COVERAGE_ENABLED', 'True').lower() == 'true'
    COVERAGE_CONFIG = {
        'source': ['app'],
        'omit': [
            '*/tests/*',
            '*/venv/*',
            '*/migrations/*',
            '*/config/*',
            '*/__pycache__/*',
        ],
        'branch': True,
        'show_missing': True,
        'skip_covered': False,
        'fail_under': 80,  # 80% coverage mínimo
    }
    
    # Configuración de métricas de testing
    COLLECT_TEST_METRICS = True
    TEST_METRICS_FILE = 'test_metrics.json'
    
    # ========================================
    # CONFIGURACIÓN DE TESTING PARALELO
    # ========================================
    
    # Configuración para pytest-xdist
    PARALLEL_TESTING = os.environ.get('PARALLEL_TESTING', 'False').lower() == 'true'
    PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '2'))
    
    # Configuración de aislamiento
    ISOLATE_TESTS = True
    CLEAN_DB_BETWEEN_TESTS = True
    CLEAN_CACHE_BETWEEN_TESTS = True
    
    # ========================================
    # CONFIGURACIÓN DE TIPOS DE TESTING
    # ========================================
    
    # Unit testing
    UNIT_TESTING_ENABLED = True
    MOCK_ALL_EXTERNAL_CALLS = True
    
    # Integration testing
    INTEGRATION_TESTING_ENABLED = True
    USE_REAL_DATABASE = os.environ.get('USE_REAL_DATABASE', 'False').lower() == 'true'
    
    # Functional testing
    FUNCTIONAL_TESTING_ENABLED = True
    BROWSER_TESTING_ENABLED = os.environ.get('BROWSER_TESTING_ENABLED', 'False').lower() == 'true'
    SELENIUM_BROWSER = os.environ.get('SELENIUM_BROWSER', 'chrome')
    HEADLESS_BROWSER = os.environ.get('HEADLESS_BROWSER', 'True').lower() == 'true'
    
    # Performance testing
    PERFORMANCE_TESTING_ENABLED = os.environ.get('PERFORMANCE_TESTING_ENABLED', 'False').lower() == 'true'
    LOAD_TEST_USERS = int(os.environ.get('LOAD_TEST_USERS', '10'))
    LOAD_TEST_DURATION = int(os.environ.get('LOAD_TEST_DURATION', '60'))  # segundos
    
    # ========================================
    # CONFIGURACIÓN DE CI/CD
    # ========================================
    
    # Detección de ambiente CI
    CI_ENVIRONMENT = any([
        os.environ.get('CI'),
        os.environ.get('GITHUB_ACTIONS'),
        os.environ.get('GITLAB_CI'),
        os.environ.get('JENKINS_URL'),
        os.environ.get('TRAVIS'),
        os.environ.get('CIRCLECI'),
    ])
    
    # Configuración específica para CI
    if CI_ENVIRONMENT:
        LOG_TO_CONSOLE = True
        PARALLEL_TESTING = True
        COVERAGE_ENABLED = True
        BROWSER_TESTING_ENABLED = False  # Sin browser en CI por defecto
        HEADLESS_BROWSER = True
    
    # ========================================
    # MÉTODOS DE UTILIDAD PARA TESTING
    # ========================================
    
    @classmethod
    def get_test_database_uri(cls, db_name: str = None) -> str:
        """
        Construye URI de base de datos para testing.
        
        Args:
            db_name: Nombre específico de la base de datos de testing
            
        Returns:
            URI de conexión para testing
        """
        if cls.USE_REAL_DATABASE:
            if db_name:
                return cls.POSTGRES_TEST_DATABASE_URL.replace(
                    'ecosistema_emprendimiento_test', 
                    f'ecosistema_emprendimiento_test_{db_name}'
                )
            return cls.POSTGRES_TEST_DATABASE_URL
        return cls.TEST_DATABASE_URL
    
    @classmethod
    def setup_test_logging(cls, verbose: bool = False):
        """
        Configura logging específico para testing.
        
        Args:
            verbose: Si True, habilita logging verboso
        """
        import logging.config
        
        if verbose or cls.LOG_TO_CONSOLE:
            cls.LOGGING_CONFIG['root']['handlers'] = ['console']
            cls.LOGGING_CONFIG['root']['level'] = 'DEBUG'
            cls.LOGGING_CONFIG['handlers']['console']['level'] = 'DEBUG'
        
        logging.config.dictConfig(cls.LOGGING_CONFIG)
    
    @classmethod
    def create_test_directories(cls):
        """
        Crea directorios necesarios para testing.
        """
        import os
        
        directories = [
            cls.UPLOAD_FOLDER,
            cls.FIXTURE_DIR,
            'tests/reports',
            'tests/coverage',
            'tests/screenshots',  # Para testing de browser
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def cleanup_test_environment(cls):
        """
        Limpia el ambiente de testing después de las pruebas.
        """
        import shutil
        import os
        
        # Limpiar directorio de uploads temporales
        if os.path.exists(cls.UPLOAD_FOLDER) and 'test_uploads' in cls.UPLOAD_FOLDER:
            shutil.rmtree(cls.UPLOAD_FOLDER, ignore_errors=True)
    
    @classmethod
    def get_test_user_data(cls, role: str = 'entrepreneur') -> dict:
        """
        Obtiene datos de usuario de prueba para el rol especificado.
        
        Args:
            role: Rol del usuario (admin, entrepreneur, ally, client)
            
        Returns:
            Diccionario con datos de usuario de prueba
        """
        user_data = {
            'admin': {
                'email': 'admin@test.com',
                'password': 'testpass123',
                'first_name': 'Admin',
                'last_name': 'Test',
                'role': 'admin'
            },
            'entrepreneur': {
                'email': 'entrepreneur@test.com',
                'password': 'testpass123',
                'first_name': 'Entrepreneur',
                'last_name': 'Test',
                'role': 'entrepreneur'
            },
            'ally': {
                'email': 'ally@test.com',
                'password': 'testpass123',
                'first_name': 'Ally',
                'last_name': 'Test',
                'role': 'ally'
            },
            'client': {
                'email': 'client@test.com',
                'password': 'testpass123',
                'first_name': 'Client',
                'last_name': 'Test',
                'role': 'client'
            }
        }
        
        return user_data.get(role, user_data['entrepreneur'])
    
    @classmethod
    def configure_test_mocks(cls):
        """
        Configura todos los mocks necesarios para testing.
        """
        # Esta función será implementada en los tests para configurar mocks específicos
        pass
    
    @staticmethod
    def init_app(app):
        """
        Inicialización específica para testing.
        
        Args:
            app: Instancia de aplicación Flask
        """
        # Llamar inicialización base
        BaseConfig.init_app(app)
        
        # Configuración específica de testing
        TestingConfig.setup_test_logging()
        TestingConfig.create_test_directories()
        TestingConfig.configure_test_mocks()
        
        # Configurar context processors para testing
        @app.context_processor
        def inject_test_vars():
            return {
                'TESTING': True,
                'TEST_ENVIRONMENT': True,
                'CI_ENVIRONMENT': TestingConfig.CI_ENVIRONMENT,
            }
        
        # Configurar manejo de errores para testing
        @app.errorhandler(Exception)
        def handle_test_exception(e):
            if TestingConfig.LOG_TO_CONSOLE:
                app.logger.exception(f"Test exception: {e}")
            raise e
        
        # Health check para testing
        @app.route('/test/health')
        def test_health_check():
            """Endpoint de health check específico para testing."""
            return {
                'status': 'testing', 
                'environment': 'testing',
                'database': 'sqlite' if TestingConfig.DATABASE_URL.startswith('sqlite') else 'postgresql'
            }, 200
        
        # Endpoint para cleanup durante testing
        @app.route('/test/cleanup', methods=['POST'])
        def test_cleanup():
            """Endpoint para limpiar datos durante testing."""
            if TestingConfig.TESTING:
                TestingConfig.cleanup_test_environment()
                return {'status': 'cleaned'}, 200
            return {'error': 'not in testing mode'}, 400
        
        # Logging de inicio en testing
        if TestingConfig.LOG_TO_CONSOLE:
            app.logger.info(f"Aplicación iniciada en modo testing")
            app.logger.info(f"Configuración: {TestingConfig.__name__}")
            app.logger.info(f"Base de datos: {TestingConfig.DATABASE_URL}")
            app.logger.info(f"CI Environment: {TestingConfig.CI_ENVIRONMENT}")


# Función de utilidad para configuración rápida de testing
def setup_testing_environment(verbose: bool = False):
    """
    Configura el ambiente de testing completo.
    
    Args:
        verbose: Si True, habilita logging verboso
        
    Returns:
        Instancia de configuración de testing
    """
    config = TestingConfig()
    config.setup_test_logging(verbose)
    config.create_test_directories()
    config.configure_test_mocks()
    
    return config


# Función para obtener configuración de testing específica
def get_testing_config_for_type(test_type: str = 'unit'):
    """
    Obtiene configuración específica para tipo de testing.
    
    Args:
        test_type: Tipo de testing (unit, integration, functional, performance)
        
    Returns:
        Configuración adaptada para el tipo de testing
    """
    config = TestingConfig()
    
    if test_type == 'integration':
        config.USE_REAL_DATABASE = True
        config.DATABASE_URL = config.POSTGRES_TEST_DATABASE_URL
        config.CACHE_TYPE = 'RedisCache'
        config.MOCK_EXTERNAL_APIS = False
        
    elif test_type == 'functional':
        config.BROWSER_TESTING_ENABLED = True
        config.USE_REAL_DATABASE = True
        config.MOCK_EXTERNAL_APIS = False
        
    elif test_type == 'performance':
        config.PERFORMANCE_TESTING_ENABLED = True
        config.USE_REAL_DATABASE = True
        config.CACHE_TYPE = 'RedisCache'
        config.LOG_TO_CONSOLE = False
        
    return config


# Exportar configuración
__all__ = [
    'TestingConfig', 
    'setup_testing_environment', 
    'get_testing_config_for_type'
]