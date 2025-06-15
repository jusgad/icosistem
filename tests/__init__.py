"""
Ecosistema de Emprendimiento - Testing Framework
===============================================

Este módulo configura el framework completo de testing para el ecosistema de emprendimiento,
incluyendo configuración de pytest, fixtures globales, factories, mocks y utilidades.

Características:
- Configuración automática de entorno de testing
- Base de datos de testing aislada
- Fixtures para todos los tipos de usuarios
- Factories para generación de datos de prueba
- Mocks para servicios externos
- Utilidades de autenticación para tests
- Configuración de logging para debugging
- Soporte para tests unitarios, integración y funcionales
- Métricas y coverage automático
- Cleanup automático entre tests

Estructura de Testing:
- unit/: Tests unitarios individuales
- integration/: Tests de integración entre componentes
- functional/: Tests de flujos completos de usuario
- performance/: Tests de carga y performance

Uso:
    # En cualquier test file
    from tests import (
        app, db, client, auth_headers,
        create_user, create_entrepreneur, create_project,
        mock_google_calendar, mock_email_service
    )
    
    def test_something(client, auth_headers):
        response = client.get('/api/v1/users', headers=auth_headers)
        assert response.status_code == 200
"""

import os
import sys
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Generator, Union
from pathlib import Path
import warnings

# Suprimir warnings durante testing
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

# Configurar path para importar módulos del proyecto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configurar variables de entorno para testing ANTES de cualquier import
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('ALEMBIC_ENV', 'testing')
os.environ.setdefault('WTF_CSRF_ENABLED', 'False')
os.environ.setdefault('TESTING', 'True')
os.environ.setdefault('SERVER_NAME', 'localhost:5000')

# Base de datos de testing temporal
test_db_url = 'sqlite:///:memory:'  # Base por defecto
if 'DATABASE_URL_TESTING' in os.environ:
    test_db_url = os.environ['DATABASE_URL_TESTING']
elif 'PYTEST_CURRENT_TEST' in os.environ:
    # PostgreSQL para tests de integración
    test_db_url = 'postgresql://test_user:test_pass@localhost:5432/ecosistema_test'

os.environ['DATABASE_URL'] = test_db_url


# ============================================================================
# CONFIGURACIÓN DE LOGGING PARA TESTING
# ============================================================================

def configure_test_logging():
    """Configura logging optimizado para testing."""
    # Crear directorio de logs de testing
    log_dir = project_root / 'logs' / 'tests'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar logger principal
    logging.basicConfig(
        level=logging.WARNING,  # Solo warnings y errores por defecto
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Logger específico para tests
    test_logger = logging.getLogger('tests')
    test_logger.setLevel(logging.DEBUG if os.getenv('DEBUG_TESTS') else logging.INFO)
    
    # Handler para archivo de tests
    if not test_logger.handlers:
        file_handler = logging.FileHandler(log_dir / 'test_run.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
        ))
        test_logger.addHandler(file_handler)
    
    # Silenciar loggers ruidosos durante testing
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return test_logger

# Configurar logging inmediatamente
logger = configure_test_logging()
logger.info("Inicializando framework de testing del ecosistema")


# ============================================================================
# IMPORTACIONES CORE DEL PROYECTO
# ============================================================================

try:
    # Imports principales de Flask
    import pytest
    import factory
    from faker import Faker
    from unittest.mock import Mock, patch, MagicMock
    
    # SQLAlchemy y base de datos
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker, scoped_session
    from sqlalchemy.pool import StaticPool
    
    # Flask y extensiones
    from flask import Flask
    from flask.testing import FlaskClient
    from werkzeug.test import Client
    
    # Imports del proyecto
    from app import create_app
    from app.extensions import db, mail, socketio
    from app.core.exceptions import ValidationError, AuthenticationError
    from app.utils.decorators import admin_required, entrepreneur_required
    
    logger.info("✓ Imports principales completados")
    
except ImportError as e:
    logger.error(f"✗ Error importando dependencias: {e}")
    raise


# ============================================================================
# CONFIGURACIÓN GLOBAL DE TESTING
# ============================================================================

# Faker con localización en español
fake = Faker(['es_ES', 'es_CO'])
Faker.seed(42)  # Seed fijo para reproducibilidad

# Configuración de testing
TEST_CONFIG = {
    'TESTING': True,
    'WTF_CSRF_ENABLED': False,
    'SECRET_KEY': 'test-secret-key-not-for-production',
    'SQLALCHEMY_DATABASE_URI': test_db_url,
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'poolclass': StaticPool,
        'pool_pre_ping': True,
        'echo': False,
    },
    'MAIL_SUPPRESS_SEND': True,
    'CELERY_TASK_ALWAYS_EAGER': True,
    'CELERY_TASK_EAGER_PROPAGATES': True,
    'REDIS_URL': 'redis://localhost:6379/15',  # DB diferente para tests
    'CACHE_TYPE': 'simple',
    'LOGIN_DISABLED': False,
    'SERVER_NAME': 'localhost:5000',
    'APPLICATION_ROOT': '/',
    'PREFERRED_URL_SCHEME': 'http',
    # Configuraciones específicas del ecosistema
    'GOOGLE_OAUTH_ENABLED': False,
    'EMAIL_NOTIFICATIONS_ENABLED': False,
    'SMS_NOTIFICATIONS_ENABLED': False,
    'ANALYTICS_ENABLED': False,
    'FILE_UPLOAD_ENABLED': True,
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB para tests
}

# Datos de testing base
TEST_DATA = {
    'admin_user': {
        'email': 'admin@test.ecosistema.com',
        'password': 'AdminTest123!',
        'first_name': 'Admin',
        'last_name': 'Test',
        'role_type': 'admin'
    },
    'entrepreneur_user': {
        'email': 'entrepreneur@test.ecosistema.com', 
        'password': 'EntrepreneurTest123!',
        'first_name': 'Entrepreneur',
        'last_name': 'Test',
        'role_type': 'entrepreneur'
    },
    'ally_user': {
        'email': 'ally@test.ecosistema.com',
        'password': 'AllyTest123!',
        'first_name': 'Ally',
        'last_name': 'Test', 
        'role_type': 'ally'
    },
    'client_user': {
        'email': 'client@test.ecosistema.com',
        'password': 'ClientTest123!',
        'first_name': 'Client',
        'last_name': 'Test',
        'role_type': 'client'
    }
}


# ============================================================================
# FACTORY CLASSES PARA GENERACIÓN DE DATOS
# ============================================================================

class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory base con configuración común."""
    
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = 'commit'
    
    @classmethod
    def _setup_next_sequence(cls):
        return 1


class UserFactory(BaseFactory):
    """Factory para crear usuarios de prueba."""
    
    class Meta:
        from app.models.user import User
        model = User
    
    id = factory.Sequence(lambda n: n)
    email = factory.LazyAttribute(lambda obj: fake.unique.email())
    first_name = factory.LazyAttribute(lambda obj: fake.first_name())
    last_name = factory.LazyAttribute(lambda obj: fake.last_name())
    phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    is_active = True
    email_verified = True
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return
        
        password = extracted or 'TestPassword123!'
        obj.set_password(password)


class AdminUserFactory(UserFactory):
    """Factory para usuarios administradores."""
    
    class Meta:
        from app.models.admin import Admin
        model = Admin
    
    role_type = 'admin'
    permissions = ['read', 'write', 'delete', 'admin']
    department = 'Administration'
    access_level = 'full'


class EntrepreneurFactory(BaseFactory):
    """Factory para emprendedores."""
    
    class Meta:
        from app.models.entrepreneur import Entrepreneur
        model = Entrepreneur
    
    user = factory.SubFactory(UserFactory, role_type='entrepreneur')
    business_name = factory.LazyAttribute(lambda obj: fake.company())
    business_description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    industry = factory.LazyAttribute(lambda obj: fake.random_element(['Technology', 'Health', 'Education', 'Finance']))
    stage = factory.LazyAttribute(lambda obj: fake.random_element(['idea', 'prototype', 'mvp', 'growth']))
    location = factory.LazyAttribute(lambda obj: fake.city())
    website = factory.LazyAttribute(lambda obj: fake.url())
    founded_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='-5y', end_date='today'))


class AllyFactory(BaseFactory):
    """Factory para aliados/mentores."""
    
    class Meta:
        from app.models.ally import Ally
        model = Ally
    
    user = factory.SubFactory(UserFactory, role_type='ally')
    organization = factory.LazyAttribute(lambda obj: fake.company())
    expertise_areas = ['business_strategy', 'marketing', 'finance']
    experience_years = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=20))
    hourly_rate = factory.LazyAttribute(lambda obj: fake.random_int(min=50, max=200))
    availability_hours = 10
    bio = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=300))


class ClientFactory(BaseFactory):
    """Factory para clientes/stakeholders."""
    
    class Meta:
        from app.models.client import Client
        model = Client
    
    user = factory.SubFactory(UserFactory, role_type='client')
    organization = factory.LazyAttribute(lambda obj: fake.company())
    organization_type = factory.LazyAttribute(
        lambda obj: fake.random_element(['corporation', 'ngo', 'government', 'foundation'])
    )
    industry = factory.LazyAttribute(
        lambda obj: fake.random_element(['Technology', 'Health', 'Education', 'Finance'])
    )
    investment_capacity = factory.LazyAttribute(lambda obj: fake.random_int(min=10000, max=1000000))


class ProjectFactory(BaseFactory):
    """Factory para proyectos."""
    
    class Meta:
        from app.models.project import Project
        model = Project
    
    entrepreneur = factory.SubFactory(EntrepreneurFactory)
    name = factory.LazyAttribute(lambda obj: fake.catch_phrase())
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=1000))
    status = factory.LazyAttribute(
        lambda obj: fake.random_element(['planning', 'active', 'paused', 'completed', 'cancelled'])
    )
    budget = factory.LazyAttribute(lambda obj: fake.random_int(min=1000, max=100000))
    start_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='-1y', end_date='today'))
    estimated_duration_months = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=24))


class MeetingFactory(BaseFactory):
    """Factory para reuniones."""
    
    class Meta:
        from app.models.meeting import Meeting
        model = Meeting
    
    title = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=4))
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    scheduled_at = factory.LazyAttribute(
        lambda obj: fake.date_time_between(start_date='+1d', end_date='+30d')
    )
    duration_minutes = factory.LazyAttribute(lambda obj: fake.random_element([30, 60, 90, 120]))
    meeting_type = factory.LazyAttribute(
        lambda obj: fake.random_element(['mentorship', 'project_review', 'evaluation', 'training'])
    )
    status = 'scheduled'
    google_meet_link = factory.LazyAttribute(lambda obj: fake.url())


class MessageFactory(BaseFactory):
    """Factory para mensajes."""
    
    class Meta:
        from app.models.message import Message
        model = Message
    
    content = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    message_type = factory.LazyAttribute(
        lambda obj: fake.random_element(['text', 'file', 'meeting_invite', 'system'])
    )
    is_read = False
    created_at = factory.LazyFunction(datetime.utcnow)


# ============================================================================
# UTILIDADES DE TESTING
# ============================================================================

class TestUtils:
    """Utilidades comunes para testing."""
    
    @staticmethod
    def get_auth_headers(user=None, token=None):
        """Genera headers de autenticación para requests."""
        if token:
            return {'Authorization': f'Bearer {token}'}
        
        if user:
            # Generar token JWT para el usuario
            from app.utils.auth import generate_token
            token = generate_token(user)
            return {'Authorization': f'Bearer {token}'}
        
        return {}
    
    @staticmethod
    def create_test_file(filename='test.txt', content='Test content'):
        """Crea un archivo temporal para testing."""
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return file_path, temp_dir
    
    @staticmethod
    def cleanup_test_files(temp_dir):
        """Limpia archivos temporales de testing."""
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"No se pudo limpiar directorio temporal {temp_dir}: {e}")
    
    @staticmethod
    def assert_response_json(response, expected_keys=None, status_code=200):
        """Valida respuesta JSON de API."""
        assert response.status_code == status_code
        assert response.content_type == 'application/json'
        
        json_data = response.get_json()
        assert json_data is not None
        
        if expected_keys:
            for key in expected_keys:
                assert key in json_data
        
        return json_data
    
    @staticmethod
    def assert_validation_error(response, field_name=None):
        """Valida que la respuesta sea un error de validación."""
        assert response.status_code == 400
        json_data = response.get_json()
        assert 'error' in json_data
        assert json_data['error'] == 'Validation error'
        
        if field_name:
            assert 'details' in json_data
            assert field_name in json_data['details']
    
    @staticmethod
    def login_user(client, email, password):
        """Realiza login de usuario y retorna token."""
        response = client.post('/api/v1/auth/login', json={
            'email': email,
            'password': password
        })
        
        assert response.status_code == 200
        json_data = response.get_json()
        return json_data.get('access_token')


class MockServices:
    """Mocks para servicios externos."""
    
    @staticmethod
    def mock_google_calendar():
        """Mock para Google Calendar API."""
        with patch('app.services.google_calendar.GoogleCalendarService') as mock:
            mock_instance = Mock()
            mock_instance.create_event.return_value = {
                'id': 'test_event_id',
                'htmlLink': 'https://calendar.google.com/test'
            }
            mock_instance.update_event.return_value = True
            mock_instance.delete_event.return_value = True
            mock.return_value = mock_instance
            return mock
    
    @staticmethod
    def mock_google_meet():
        """Mock para Google Meet API."""
        with patch('app.services.google_meet.GoogleMeetService') as mock:
            mock_instance = Mock()
            mock_instance.create_meeting.return_value = {
                'meet_link': 'https://meet.google.com/test-meeting'
            }
            mock.return_value = mock_instance
            return mock
    
    @staticmethod
    def mock_email_service():
        """Mock para servicio de email."""
        with patch('app.services.email.EmailService') as mock:
            mock_instance = Mock()
            mock_instance.send_email.return_value = True
            mock_instance.send_notification.return_value = True
            mock.return_value = mock_instance
            return mock
    
    @staticmethod
    def mock_sms_service():
        """Mock para servicio de SMS."""
        with patch('app.services.sms.SMSService') as mock:
            mock_instance = Mock()
            mock_instance.send_sms.return_value = True
            mock.return_value = mock_instance
            return mock
    
    @staticmethod
    def mock_file_storage():
        """Mock para almacenamiento de archivos."""
        with patch('app.services.file_storage.FileStorageService') as mock:
            mock_instance = Mock()
            mock_instance.upload_file.return_value = {
                'file_id': 'test_file_id',
                'url': 'https://storage.test.com/file.pdf'
            }
            mock_instance.delete_file.return_value = True
            mock.return_value = mock_instance
            return mock


class DatabaseUtils:
    """Utilidades para manejo de base de datos en tests."""
    
    @staticmethod
    def create_test_database():
        """Crea base de datos de testing."""
        if 'sqlite' not in test_db_url:
            # Para PostgreSQL, crear BD si no existe
            from sqlalchemy import create_engine
            from sqlalchemy.exc import ProgrammingError
            
            # Conectar a postgres para crear la BD de testing
            admin_url = test_db_url.replace('/ecosistema_test', '/postgres')
            admin_engine = create_engine(admin_url)
            
            try:
                with admin_engine.connect() as conn:
                    conn.execute(text("COMMIT"))  # End any transaction
                    conn.execute(text("CREATE DATABASE ecosistema_test"))
                logger.info("✓ Base de datos de testing creada")
            except ProgrammingError:
                # La BD ya existe
                pass
            finally:
                admin_engine.dispose()
    
    @staticmethod
    def drop_test_database():
        """Elimina base de datos de testing."""
        if 'sqlite' not in test_db_url:
            from sqlalchemy import create_engine
            
            admin_url = test_db_url.replace('/ecosistema_test', '/postgres')
            admin_engine = create_engine(admin_url)
            
            try:
                with admin_engine.connect() as conn:
                    conn.execute(text("COMMIT"))
                    conn.execute(text("""
                        SELECT pg_terminate_backend(pid) 
                        FROM pg_stat_activity 
                        WHERE datname = 'ecosistema_test' AND pid <> pg_backend_pid()
                    """))
                    conn.execute(text("DROP DATABASE IF EXISTS ecosistema_test"))
                logger.info("✓ Base de datos de testing eliminada")
            except Exception as e:
                logger.warning(f"No se pudo eliminar BD de testing: {e}")
            finally:
                admin_engine.dispose()
    
    @staticmethod
    def seed_test_data(db_session):
        """Carga datos de prueba básicos."""
        logger.info("Cargando datos de prueba...")
        
        # Crear usuarios base
        test_users = {}
        for role, user_data in TEST_DATA.items():
            if role.endswith('_user'):
                role_name = role.replace('_user', '')
                
                if role_name == 'admin':
                    user = AdminUserFactory(**user_data)
                elif role_name == 'entrepreneur':
                    user = UserFactory(**user_data)
                    entrepreneur = EntrepreneurFactory(user=user)
                    test_users[f'{role_name}_profile'] = entrepreneur
                elif role_name == 'ally':
                    user = UserFactory(**user_data)
                    ally = AllyFactory(user=user)
                    test_users[f'{role_name}_profile'] = ally
                elif role_name == 'client':
                    user = UserFactory(**user_data)
                    client = ClientFactory(user=user)
                    test_users[f'{role_name}_profile'] = client
                
                test_users[role_name] = user
        
        db_session.commit()
        logger.info(f"✓ {len(test_users)} usuarios de prueba creados")
        
        return test_users


# ============================================================================
# CONFIGURACIÓN DE PYTEST
# ============================================================================

def pytest_configure(config):
    """Configuración inicial de pytest."""
    logger.info("Configurando pytest para ecosistema de emprendimiento...")
    
    # Markers personalizados
    config.addinivalue_line(
        "markers", "unit: marca test como unitario"
    )
    config.addinivalue_line(
        "markers", "integration: marca test como de integración"
    )
    config.addinivalue_line(
        "markers", "functional: marca test como funcional"
    )
    config.addinivalue_line(
        "markers", "performance: marca test como de performance"
    )
    config.addinivalue_line(
        "markers", "slow: marca test como lento"
    )
    config.addinivalue_line(
        "markers", "external: test que requiere servicios externos"
    )


def pytest_sessionstart(session):
    """Ejecutado al inicio de la sesión de testing."""
    logger.info("="*60)
    logger.info("INICIANDO SESIÓN DE TESTING - ECOSISTEMA EMPRENDIMIENTO")
    logger.info("="*60)
    
    # Crear base de datos de testing
    DatabaseUtils.create_test_database()


def pytest_sessionfinish(session, exitstatus):
    """Ejecutado al final de la sesión de testing."""
    logger.info("="*60)
    logger.info(f"SESIÓN DE TESTING COMPLETADA - Código de salida: {exitstatus}")
    logger.info("="*60)
    
    # Limpiar base de datos de testing si no es SQLite en memoria
    if 'sqlite:///:memory:' not in test_db_url:
        DatabaseUtils.drop_test_database()


# ============================================================================
# FIXTURES GLOBALES
# ============================================================================

@pytest.fixture(scope='session')
def app():
    """Fixture de aplicación Flask para toda la sesión."""
    logger.info("Creando aplicación Flask para testing...")
    
    app = create_app(environment='testing', config_override=TEST_CONFIG)
    
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        logger.info("✓ Esquema de base de datos creado")
        
        yield app
        
        # Cleanup
        db.session.remove()
        db.drop_all()
        logger.info("✓ Esquema de base de datos eliminado")


@pytest.fixture(scope='function')
def client(app):
    """Fixture de cliente de testing."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Fixture de sesión de base de datos con rollback automático."""
    with app.app_context():
        # Crear una transacción
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Configurar sesión para usar la transacción
        session = scoped_session(
            sessionmaker(bind=connection, expire_on_commit=False)
        )
        db.session = session
        
        # Configurar factories para usar esta sesión
        UserFactory._meta.sqlalchemy_session = session
        AdminUserFactory._meta.sqlalchemy_session = session
        EntrepreneurFactory._meta.sqlalchemy_session = session
        AllyFactory._meta.sqlalchemy_session = session
        ClientFactory._meta.sqlalchemy_session = session
        ProjectFactory._meta.sqlalchemy_session = session
        MeetingFactory._meta.sqlalchemy_session = session
        MessageFactory._meta.sqlalchemy_session = session
        
        yield session
        
        # Rollback de la transacción
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope='function')
def test_users(db_session):
    """Fixture que crea usuarios de prueba."""
    return DatabaseUtils.seed_test_data(db_session)


@pytest.fixture(scope='function')
def admin_user(test_users):
    """Fixture de usuario administrador."""
    return test_users['admin']


@pytest.fixture(scope='function')
def entrepreneur_user(test_users):
    """Fixture de usuario emprendedor."""
    return test_users['entrepreneur']


@pytest.fixture(scope='function')
def ally_user(test_users):
    """Fixture de usuario aliado."""
    return test_users['ally']


@pytest.fixture(scope='function')
def client_user(test_users):
    """Fixture de usuario cliente."""
    return test_users['client']


@pytest.fixture(scope='function')
def auth_headers(admin_user):
    """Fixture de headers de autenticación."""
    return TestUtils.get_auth_headers(admin_user)


@pytest.fixture(scope='function')
def entrepreneur_auth_headers(entrepreneur_user):
    """Fixture de headers de autenticación para emprendedor."""
    return TestUtils.get_auth_headers(entrepreneur_user)


@pytest.fixture(scope='function')
def ally_auth_headers(ally_user):
    """Fixture de headers de autenticación para aliado."""
    return TestUtils.get_auth_headers(ally_user)


# ============================================================================
# EXPORTS PÚBLICOS
# ============================================================================

# Fixtures principales
__all__ = [
    # Fixtures
    'app', 'client', 'db_session', 'test_users',
    'admin_user', 'entrepreneur_user', 'ally_user', 'client_user',
    'auth_headers', 'entrepreneur_auth_headers', 'ally_auth_headers',
    
    # Factories
    'UserFactory', 'AdminUserFactory', 'EntrepreneurFactory', 
    'AllyFactory', 'ClientFactory', 'ProjectFactory', 
    'MeetingFactory', 'MessageFactory',
    
    # Utilidades
    'TestUtils', 'MockServices', 'DatabaseUtils',
    'fake', 'TEST_CONFIG', 'TEST_DATA',
    
    # Constantes y configuración
    'logger',
]

# Configurar factories para ser importadas fácilmente
create_user = UserFactory
create_admin = AdminUserFactory
create_entrepreneur = EntrepreneurFactory
create_ally = AllyFactory
create_client = ClientFactory
create_project = ProjectFactory
create_meeting = MeetingFactory
create_message = MessageFactory

# Mocks comunes
mock_google_calendar = MockServices.mock_google_calendar
mock_google_meet = MockServices.mock_google_meet
mock_email_service = MockServices.mock_email_service
mock_sms_service = MockServices.mock_sms_service
mock_file_storage = MockServices.mock_file_storage

logger.info("✓ Framework de testing inicializado correctamente")
logger.info(f"✓ Configuración: {len(TEST_CONFIG)} parámetros")
logger.info(f"✓ Factories disponibles: {len([x for x in __all__ if 'Factory' in x])}")
logger.info(f"✓ Fixtures disponibles: {len([x for x in __all__ if not x.endswith('Factory') and not x.isupper()])}")