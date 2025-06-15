"""
Ecosistema de Emprendimiento - Configuración Avanzada de Pytest
===============================================================

Este archivo contiene configuraciones avanzadas de pytest, fixtures específicas,
hooks personalizados y utilidades especializadas para el testing del ecosistema.

Características avanzadas:
- Configuración de fixtures por scope y ambiente
- Manejo de transacciones complejas
- Testing de WebSockets en tiempo real
- Fixtures para testing de performance
- Configuración de mocking avanzado
- Testing de integraciones externas
- Fixtures para manejo de archivos y uploads
- Configuración de ambientes paralelos
- Testing de permisos y roles específicos
- Fixtures para analytics y métricas
- Configuración de debugging avanzado

Author: Sistema de Testing Empresarial
Created: 2025-06-13
Version: 2.1.0
"""

import os
import sys
import time
import uuid
import json
import tempfile
import shutil
import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator, Callable
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import logging
import warnings

# Suprimir warnings específicos durante testing
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*deprecated.*", category=PendingDeprecationWarning)

# Imports de testing
import pytest
import factory
from faker import Faker
import requests_mock

# Imports de Flask y SQLAlchemy
from flask import Flask, current_app, g
from flask.testing import FlaskClient
from werkzeug.test import Client
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Imports del proyecto (del __init__.py ya importado)
from tests import (
    logger, app, client, db_session, test_users,
    UserFactory, EntrepreneurFactory, AllyFactory, ClientFactory,
    ProjectFactory, MeetingFactory, MessageFactory,
    TestUtils, MockServices, TEST_CONFIG, fake
)

# Imports adicionales del proyecto
try:
    from app.extensions import db, mail, socketio, cache
    from app.models.user import User
    from app.models.entrepreneur import Entrepreneur
    from app.models.ally import Ally
    from app.models.client import Client
    from app.models.project import Project
    from app.models.meeting import Meeting
    from app.models.message import Message
    from app.models.document import Document
    from app.models.task import Task
    from app.models.notification import Notification
    from app.services.email import EmailService
    from app.services.google_calendar import GoogleCalendarService
    from app.services.analytics_service import AnalyticsService
    from app.utils.decorators import admin_required, entrepreneur_required
except ImportError as e:
    logger.warning(f"Algunos imports opcionales no disponibles: {e}")


# ============================================================================
# CONFIGURACIÓN GLOBAL AVANZADA
# ============================================================================

# Configuración de performance testing
PERFORMANCE_CONFIG = {
    'max_response_time_ms': 1000,
    'max_db_queries_per_request': 10,
    'memory_leak_threshold_mb': 50,
    'concurrent_users_limit': 100,
}

# Configuración de archivos de testing
TEST_FILES_CONFIG = {
    'upload_dir': 'tests/fixtures/uploads',
    'max_file_size_mb': 10,
    'allowed_extensions': ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png'],
    'temp_dir_prefix': 'ecosistema_test_',
}

# Configuración de WebSockets
WEBSOCKET_CONFIG = {
    'test_namespace': '/test',
    'timeout_seconds': 5,
    'max_connections': 50,
}

# Datos de testing complejos
COMPLEX_TEST_DATA = {
    'organizations': [
        {
            'name': 'Tech Innovators SAS',
            'type': 'corporation',
            'industry': 'Technology',
            'size': 'medium',
            'founded_year': 2018
        },
        {
            'name': 'Fundación Emprendimiento Social',
            'type': 'ngo',
            'industry': 'Social Impact',
            'size': 'small',
            'founded_year': 2015
        },
        {
            'name': 'Gobierno Digital Colombia',
            'type': 'government',
            'industry': 'Public Sector',
            'size': 'large',
            'founded_year': 2020
        }
    ],
    'programs': [
        {
            'name': 'Aceleradora TechStart',
            'type': 'accelerator',
            'duration_weeks': 12,
            'investment_range': '10000-50000',
            'focus_areas': ['technology', 'fintech', 'healthtech']
        },
        {
            'name': 'Incubadora Social Impact',
            'type': 'incubator',
            'duration_weeks': 24,
            'investment_range': '5000-25000',
            'focus_areas': ['social_impact', 'education', 'environment']
        }
    ],
    'mentorship_areas': [
        'business_strategy', 'marketing', 'finance', 'technology',
        'legal', 'operations', 'sales', 'product_development'
    ],
    'project_stages': [
        'idea', 'validation', 'prototype', 'mvp', 'growth', 'scale'
    ]
}


# ============================================================================
# HOOKS DE PYTEST PERSONALIZADOS
# ============================================================================

def pytest_configure(config):
    """Configuración avanzada de pytest."""
    # Registrar markers adicionales
    markers = [
        "slow: marca tests que tardan más de 5 segundos",
        "integration: tests de integración entre componentes",
        "functional: tests de flujos completos de usuario",
        "performance: tests de carga y performance",
        "external: tests que requieren servicios externos",
        "websocket: tests de funcionalidad WebSocket",
        "file_upload: tests de carga de archivos",
        "permissions: tests de sistema de permisos",
        "analytics: tests de métricas y analytics",
        "notifications: tests de sistema de notificaciones",
        "admin_only: tests que requieren permisos de administrador",
        "entrepreneur_flow: tests específicos de flujo emprendedor",
        "ally_flow: tests específicos de flujo aliado",
        "client_flow: tests específicos de flujo cliente",
        "parallel: tests que pueden ejecutarse en paralelo",
        "sequential: tests que deben ejecutarse secuencialmente",
    ]
    
    for marker in markers:
        config.addinivalue_line("markers", marker)
    
    # Configurar logging de pytest
    logging.getLogger("pytest").setLevel(logging.INFO)
    
    # Configurar directorio de reportes
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)


def pytest_sessionstart(session):
    """Ejecutado al inicio de la sesión de testing."""
    logger.info("🚀 Iniciando sesión de testing avanzada")
    logger.info(f"📊 Pytest version: {pytest.__version__}")
    logger.info(f"🐍 Python version: {sys.version.split()[0]}")
    logger.info(f"🗄️  Database URL: {os.getenv('DATABASE_URL', 'not configured')}")
    
    # Crear directorios necesarios
    test_dirs = [
        'tests/reports',
        'tests/fixtures',
        'tests/fixtures/uploads',
        'tests/tmp',
        'logs/tests'
    ]
    
    for directory in test_dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Limpiar archivos temporales de sesiones anteriores
    cleanup_previous_test_files()


def pytest_sessionfinish(session, exitstatus):
    """Ejecutado al final de la sesión de testing."""
    status_emoji = "✅" if exitstatus == 0 else "❌"
    logger.info(f"{status_emoji} Sesión de testing completada - Exit code: {exitstatus}")
    
    # Generar reporte de resumen
    generate_test_summary_report(session, exitstatus)
    
    # Limpiar archivos temporales
    cleanup_test_files()


def pytest_runtest_setup(item):
    """Ejecutado antes de cada test."""
    # Marcar inicio de test con timestamp
    item.start_time = time.time()
    
    # Log del test que inicia
    logger.debug(f"🔬 Iniciando test: {item.nodeid}")
    
    # Verificar markers requeridos
    check_test_requirements(item)


def pytest_runtest_teardown(item, nextitem):
    """Ejecutado después de cada test."""
    # Calcular duración
    duration = time.time() - getattr(item, 'start_time', time.time())
    
    # Log del test completado
    logger.debug(f"✅ Test completado: {item.nodeid} ({duration:.3f}s)")
    
    # Advertir sobre tests lentos
    if duration > 5.0:
        logger.warning(f"⚠️  Test lento detectado: {item.nodeid} ({duration:.3f}s)")


def pytest_runtest_call(pyfuncitem):
    """Ejecutado durante la llamada del test."""
    # Monitorear memoria si es test de performance
    if pyfuncitem.get_closest_marker("performance"):
        monitor_memory_usage(pyfuncitem)


# ============================================================================
# FIXTURES DE CONFIGURACIÓN AVANZADA
# ============================================================================

@pytest.fixture(scope='session')
def event_loop():
    """Fixture para asyncio event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def database_engine(app):
    """Fixture de engine de base de datos con monitoreo."""
    with app.app_context():
        engine = db.engine
        
        # Configurar monitoreo de queries
        query_counter = {'count': 0, 'queries': []}
        
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            query_counter['count'] += 1
            query_counter['queries'].append({
                'statement': statement,
                'parameters': parameters,
                'timestamp': datetime.utcnow()
            })
        
        yield engine, query_counter


@pytest.fixture(scope='function')
def clean_db(app, database_engine):
    """Fixture que garantiza base de datos limpia."""
    engine, query_counter = database_engine
    
    with app.app_context():
        # Limpiar todas las tablas
        db.session.execute(text('TRUNCATE TABLE users CASCADE'))
        db.session.execute(text('TRUNCATE TABLE entrepreneurs CASCADE'))
        db.session.execute(text('TRUNCATE TABLE allies CASCADE'))
        db.session.execute(text('TRUNCATE TABLE clients CASCADE'))
        db.session.execute(text('TRUNCATE TABLE projects CASCADE'))
        db.session.execute(text('TRUNCATE TABLE meetings CASCADE'))
        db.session.execute(text('TRUNCATE TABLE messages CASCADE'))
        db.session.commit()
        
        # Reset query counter
        query_counter['count'] = 0
        query_counter['queries'].clear()
        
        yield db.session
        
        # Cleanup final
        db.session.rollback()


@pytest.fixture(scope='function')
def performance_monitor():
    """Fixture para monitorear performance de tests."""
    start_time = time.time()
    initial_memory = get_memory_usage()
    
    monitor = {
        'start_time': start_time,
        'initial_memory': initial_memory,
        'query_count': 0,
        'warnings': []
    }
    
    yield monitor
    
    # Calcular métricas finales
    end_time = time.time()
    final_memory = get_memory_usage()
    
    monitor.update({
        'duration': end_time - start_time,
        'memory_delta': final_memory - initial_memory,
        'end_time': end_time
    })
    
    # Validar thresholds
    validate_performance_thresholds(monitor)


@pytest.fixture(scope='function')
def temp_directory():
    """Fixture para directorio temporal por test."""
    temp_dir = tempfile.mkdtemp(prefix=TEST_FILES_CONFIG['temp_dir_prefix'])
    logger.debug(f"📁 Directorio temporal creado: {temp_dir}")
    
    yield Path(temp_dir)
    
    # Cleanup
    try:
        shutil.rmtree(temp_dir)
        logger.debug(f"🗑️  Directorio temporal eliminado: {temp_dir}")
    except Exception as e:
        logger.warning(f"⚠️  No se pudo eliminar directorio temporal {temp_dir}: {e}")


# ============================================================================
# FIXTURES DE DATOS COMPLEJOS
# ============================================================================

@pytest.fixture(scope='function')
def complete_ecosystem(db_session):
    """Fixture que crea un ecosistema completo de datos."""
    logger.info("🏗️  Creando ecosistema completo de datos de prueba...")
    
    ecosystem = {}
    
    # 1. Crear organizaciones
    organizations = []
    for org_data in COMPLEX_TEST_DATA['organizations']:
        org = {
            'id': len(organizations) + 1,
            'name': org_data['name'],
            'type': org_data['type'],
            'industry': org_data['industry'],
            'created_at': datetime.utcnow()
        }
        organizations.append(org)
    
    ecosystem['organizations'] = organizations
    
    # 2. Crear usuarios de cada tipo
    admin = UserFactory(role_type='admin', email='admin@ecosystem.test')
    entrepreneur1 = UserFactory(role_type='entrepreneur', email='entrepreneur1@ecosystem.test')
    entrepreneur2 = UserFactory(role_type='entrepreneur', email='entrepreneur2@ecosystem.test')
    ally1 = UserFactory(role_type='ally', email='ally1@ecosystem.test')
    ally2 = UserFactory(role_type='ally', email='ally2@ecosystem.test')
    client1 = UserFactory(role_type='client', email='client1@ecosystem.test')
    
    ecosystem['users'] = {
        'admin': admin,
        'entrepreneurs': [entrepreneur1, entrepreneur2],
        'allies': [ally1, ally2],
        'clients': [client1]
    }
    
    # 3. Crear perfiles específicos
    entrepreneur_profile1 = EntrepreneurFactory(
        user=entrepreneur1,
        business_name='TechStart Innovation',
        stage='mvp',
        industry='Technology'
    )
    entrepreneur_profile2 = EntrepreneurFactory(
        user=entrepreneur2,
        business_name='Green Solutions',
        stage='prototype',
        industry='Environment'
    )
    
    ally_profile1 = AllyFactory(
        user=ally1,
        expertise_areas=['business_strategy', 'finance'],
        hourly_rate=150
    )
    ally_profile2 = AllyFactory(
        user=ally2,
        expertise_areas=['marketing', 'sales'],
        hourly_rate=120
    )
    
    client_profile1 = ClientFactory(
        user=client1,
        organization='Investment Corp',
        investment_capacity=500000
    )
    
    ecosystem['profiles'] = {
        'entrepreneurs': [entrepreneur_profile1, entrepreneur_profile2],
        'allies': [ally_profile1, ally_profile2],
        'clients': [client_profile1]
    }
    
    # 4. Crear proyectos
    project1 = ProjectFactory(
        entrepreneur=entrepreneur_profile1,
        name='AI-Powered Analytics Platform',
        status='active',
        budget=75000
    )
    project2 = ProjectFactory(
        entrepreneur=entrepreneur_profile2,
        name='Sustainable Packaging Solution',
        status='planning',
        budget=45000
    )
    
    ecosystem['projects'] = [project1, project2]
    
    # 5. Crear reuniones
    meeting1 = MeetingFactory(
        title='Strategic Planning Session',
        meeting_type='mentorship',
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        status='scheduled'
    )
    meeting2 = MeetingFactory(
        title='Project Review',
        meeting_type='project_review',
        scheduled_at=datetime.utcnow() + timedelta(days=3),
        status='scheduled'
    )
    
    ecosystem['meetings'] = [meeting1, meeting2]
    
    # 6. Commit todos los datos
    db_session.commit()
    
    logger.info(f"✅ Ecosistema completo creado: {len(ecosystem['users']['entrepreneurs'])} emprendedores, "
                f"{len(ecosystem['projects'])} proyectos, {len(ecosystem['meetings'])} reuniones")
    
    yield ecosystem


@pytest.fixture(scope='function')
def entrepreneur_with_complete_profile(db_session):
    """Fixture de emprendedor con perfil completo y proyectos."""
    user = UserFactory(role_type='entrepreneur', email='complete@entrepreneur.test')
    
    entrepreneur = EntrepreneurFactory(
        user=user,
        business_name='Complete Startup Inc',
        business_description='Una startup completa con todos los datos necesarios para testing',
        industry='Technology',
        stage='growth',
        location='Bogotá, Colombia',
        website='https://completestartup.com',
        founded_date=datetime(2020, 1, 15).date()
    )
    
    # Crear múltiples proyectos
    projects = []
    for i in range(3):
        project = ProjectFactory(
            entrepreneur=entrepreneur,
            name=f'Proyecto {i+1}',
            status=['active', 'planning', 'completed'][i],
            budget=50000 * (i + 1)
        )
        projects.append(project)
    
    # Crear reuniones
    meetings = []
    for i in range(2):
        meeting = MeetingFactory(
            title=f'Reunión {i+1}',
            scheduled_at=datetime.utcnow() + timedelta(days=i+1),
            duration_minutes=60
        )
        meetings.append(meeting)
    
    db_session.commit()
    
    yield {
        'user': user,
        'entrepreneur': entrepreneur,
        'projects': projects,
        'meetings': meetings
    }


@pytest.fixture(scope='function')
def mentorship_session_data(db_session):
    """Fixture para datos de sesión de mentoría completa."""
    # Crear emprendedor
    entrepreneur_user = UserFactory(role_type='entrepreneur')
    entrepreneur = EntrepreneurFactory(user=entrepreneur_user)
    
    # Crear aliado/mentor
    ally_user = UserFactory(role_type='ally')
    ally = AllyFactory(
        user=ally_user,
        expertise_areas=['business_strategy', 'finance', 'marketing'],
        hourly_rate=150
    )
    
    # Crear proyecto
    project = ProjectFactory(
        entrepreneur=entrepreneur,
        name='Mentorship Test Project'
    )
    
    # Crear reunión de mentoría
    meeting = MeetingFactory(
        title='Sesión de Mentoría Estratégica',
        meeting_type='mentorship',
        scheduled_at=datetime.utcnow() + timedelta(hours=2),
        duration_minutes=90
    )
    
    db_session.commit()
    
    yield {
        'entrepreneur': entrepreneur,
        'ally': ally,
        'project': project,
        'meeting': meeting
    }


# ============================================================================
# FIXTURES DE AUTENTICACIÓN Y PERMISOS
# ============================================================================

@pytest.fixture(scope='function')
def auth_tokens(complete_ecosystem):
    """Fixture que genera tokens de autenticación para todos los usuarios."""
    from app.utils.auth import generate_token
    
    tokens = {}
    
    # Token de admin
    admin_user = complete_ecosystem['users']['admin']
    tokens['admin'] = generate_token(admin_user)
    
    # Tokens de emprendedores
    tokens['entrepreneurs'] = []
    for entrepreneur in complete_ecosystem['users']['entrepreneurs']:
        token = generate_token(entrepreneur)
        tokens['entrepreneurs'].append(token)
    
    # Tokens de aliados
    tokens['allies'] = []
    for ally in complete_ecosystem['users']['allies']:
        token = generate_token(ally)
        tokens['allies'].append(token)
    
    # Tokens de clientes
    tokens['clients'] = []
    for client in complete_ecosystem['users']['clients']:
        token = generate_token(client)
        tokens['clients'].append(token)
    
    yield tokens


@pytest.fixture(scope='function')
def role_headers(auth_tokens):
    """Fixture que proporciona headers HTTP para cada rol."""
    headers = {}
    
    # Headers para admin
    headers['admin'] = {
        'Authorization': f'Bearer {auth_tokens["admin"]}',
        'Content-Type': 'application/json'
    }
    
    # Headers para emprendedores
    headers['entrepreneurs'] = []
    for token in auth_tokens['entrepreneurs']:
        header = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        headers['entrepreneurs'].append(header)
    
    # Headers para aliados
    headers['allies'] = []
    for token in auth_tokens['allies']:
        header = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        headers['allies'].append(header)
    
    # Headers para clientes
    headers['clients'] = []
    for token in auth_tokens['clients']:
        header = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        headers['clients'].append(header)
    
    yield headers


@pytest.fixture(scope='function')
def permission_tester():
    """Fixture para testing de permisos y autorizaciones."""
    def test_permission(client, endpoint, method='GET', headers=None, data=None, expected_status=200):
        """Función auxiliar para probar permisos en endpoints."""
        kwargs = {'headers': headers} if headers else {}
        
        if data and method in ['POST', 'PUT', 'PATCH']:
            kwargs['json'] = data
        
        response = getattr(client, method.lower())(endpoint, **kwargs)
        
        assert response.status_code == expected_status, (
            f"Endpoint {method} {endpoint} retornó {response.status_code}, "
            f"esperado {expected_status}. Response: {response.get_json()}"
        )
        
        return response
    
    yield test_permission


# ============================================================================
# FIXTURES DE TESTING DE ARCHIVOS
# ============================================================================

@pytest.fixture(scope='function')
def test_files(temp_directory):
    """Fixture que crea archivos de prueba de diferentes tipos."""
    files = {}
    
    # Archivo de texto
    txt_file = temp_directory / 'test_document.txt'
    txt_file.write_text('Este es un documento de prueba para testing.', encoding='utf-8')
    files['txt'] = txt_file
    
    # Archivo PDF simulado
    pdf_file = temp_directory / 'test_document.pdf'
    pdf_file.write_bytes(b'%PDF-1.4 fake pdf content for testing')
    files['pdf'] = pdf_file
    
    # Archivo de imagen simulado
    img_file = temp_directory / 'test_image.jpg'
    img_file.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF fake jpg content')
    files['jpg'] = img_file
    
    # Archivo grande para testing de límites
    large_file = temp_directory / 'large_file.txt'
    large_content = 'X' * (5 * 1024 * 1024)  # 5MB
    large_file.write_text(large_content, encoding='utf-8')
    files['large'] = large_file
    
    # Archivo con extensión no permitida
    exe_file = temp_directory / 'malicious.exe'
    exe_file.write_bytes(b'MZ fake exe content')
    files['exe'] = exe_file
    
    logger.debug(f"📁 Archivos de prueba creados: {list(files.keys())}")
    
    yield files


@pytest.fixture(scope='function')
def file_upload_tester(client):
    """Fixture para testing de carga de archivos."""
    def upload_file(endpoint, file_path, field_name='file', headers=None, additional_data=None):
        """Función auxiliar para subir archivos en tests."""
        with open(file_path, 'rb') as f:
            data = {field_name: (f, Path(file_path).name)}
            
            if additional_data:
                data.update(additional_data)
            
            kwargs = {'data': data}
            if headers:
                kwargs['headers'] = headers
            
            response = client.post(endpoint, **kwargs)
            
        return response
    
    yield upload_file


# ============================================================================
# FIXTURES DE WEBSOCKETS
# ============================================================================

@pytest.fixture(scope='function')
def socketio_client(app):
    """Fixture para cliente de WebSocket."""
    socketio_client = socketio.test_client(app, namespace=WEBSOCKET_CONFIG['test_namespace'])
    
    yield socketio_client
    
    socketio_client.disconnect()


@pytest.fixture(scope='function')
def websocket_tester(socketio_client):
    """Fixture para testing de funcionalidad WebSocket."""
    received_messages = []
    
    @socketio_client.on('message', namespace=WEBSOCKET_CONFIG['test_namespace'])
    def on_message(data):
        received_messages.append({
            'data': data,
            'timestamp': datetime.utcnow()
        })
    
    def send_and_wait(event, data, timeout=WEBSOCKET_CONFIG['timeout_seconds']):
        """Envía mensaje y espera respuesta."""
        socketio_client.emit(event, data, namespace=WEBSOCKET_CONFIG['test_namespace'])
        received = socketio_client.get_received(namespace=WEBSOCKET_CONFIG['test_namespace'])
        return received
    
    def get_received_messages():
        """Retorna mensajes recibidos."""
        return received_messages.copy()
    
    yield {
        'send_and_wait': send_and_wait,
        'get_received': get_received_messages,
        'client': socketio_client
    }


# ============================================================================
# FIXTURES DE MOCKING AVANZADO
# ============================================================================

@pytest.fixture(scope='function')
def mock_external_services():
    """Fixture que mockea todos los servicios externos."""
    with patch.multiple(
        'app.services',
        google_calendar=MockServices.mock_google_calendar(),
        google_meet=MockServices.mock_google_meet(),
        email=MockServices.mock_email_service(),
        sms=MockServices.mock_sms_service(),
        file_storage=MockServices.mock_file_storage()
    ):
        yield


@pytest.fixture(scope='function')
def requests_mocker():
    """Fixture para mockear requests HTTP externos."""
    with requests_mock.Mocker() as m:
        # Configurar mocks comunes
        m.get('https://api.example.com/health', json={'status': 'ok'})
        m.post('https://api.example.com/webhook', json={'received': True})
        
        yield m


@pytest.fixture(scope='function')
def mock_analytics():
    """Fixture para mockear servicio de analytics."""
    with patch('app.services.analytics_service.AnalyticsService') as mock:
        mock_instance = Mock()
        mock_instance.track_event.return_value = True
        mock_instance.get_metrics.return_value = {
            'users': 100,
            'entrepreneurs': 25,
            'projects': 50,
            'meetings': 75
        }
        mock_instance.generate_report.return_value = {
            'report_id': 'test_report_123',
            'url': 'https://reports.test.com/123'
        }
        mock.return_value = mock_instance
        yield mock_instance


# ============================================================================
# FIXTURES DE PERFORMANCE Y MONITOREO
# ============================================================================

@pytest.fixture(scope='function')
def query_counter():
    """Fixture para contar queries de base de datos."""
    queries = []
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries.append({
            'statement': statement,
            'parameters': parameters,
            'timestamp': datetime.utcnow()
        })
    
    yield queries
    
    # Cleanup del listener
    event.remove(Engine, "before_cursor_execute", receive_before_cursor_execute)


@pytest.fixture(scope='function')
def response_timer():
    """Fixture para medir tiempo de respuesta de requests."""
    times = {}
    
    def time_request(func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        times[func.__name__] = {
            'duration': end_time - start_time,
            'timestamp': datetime.utcnow()
        }
        
        return result
    
    yield time_request, times


# ============================================================================
# UTILIDADES AUXILIARES
# ============================================================================

def cleanup_previous_test_files():
    """Limpia archivos temporales de sesiones anteriores."""
    try:
        temp_base = Path(tempfile.gettempdir())
        for temp_dir in temp_base.glob(f"{TEST_FILES_CONFIG['temp_dir_prefix']}*"):
            if temp_dir.is_dir():
                shutil.rmtree(temp_dir)
                logger.debug(f"🗑️  Directorio temporal anterior eliminado: {temp_dir}")
    except Exception as e:
        logger.warning(f"⚠️  Error limpiando archivos temporales anteriores: {e}")


def cleanup_test_files():
    """Limpia archivos temporales al final de la sesión."""
    try:
        # Limpiar directorio de uploads de prueba
        upload_dir = Path(TEST_FILES_CONFIG['upload_dir'])
        if upload_dir.exists():
            for file in upload_dir.glob('*'):
                if file.is_file():
                    file.unlink()
        
        # Limpiar archivos temporales
        cleanup_previous_test_files()
        
        logger.info("🧹 Archivos temporales limpiados")
    except Exception as e:
        logger.warning(f"⚠️  Error en cleanup final: {e}")


def check_test_requirements(item):
    """Verifica requerimientos específicos de tests."""
    # Verificar si test requiere servicios externos
    if item.get_closest_marker("external"):
        if not os.getenv('ENABLE_EXTERNAL_TESTS'):
            pytest.skip("Tests externos deshabilitados. Usar ENABLE_EXTERNAL_TESTS=1")
    
    # Verificar si test requiere base de datos específica
    if item.get_closest_marker("performance"):
        if 'sqlite' in os.getenv('DATABASE_URL', ''):
            pytest.skip("Tests de performance requieren PostgreSQL")


def get_memory_usage():
    """Obtiene uso de memoria actual."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        return 0


def monitor_memory_usage(pyfuncitem):
    """Monitorea uso de memoria durante test de performance."""
    initial_memory = get_memory_usage()
    
    def check_memory():
        current_memory = get_memory_usage()
        if current_memory - initial_memory > PERFORMANCE_CONFIG['memory_leak_threshold_mb']:
            logger.warning(
                f"⚠️  Posible memory leak en {pyfuncitem.nodeid}: "
                f"{current_memory - initial_memory:.2f}MB incremento"
            )
    
    # Configurar timer para verificar memoria periódicamente
    timer = threading.Timer(2.0, check_memory)
    timer.start()


def validate_performance_thresholds(monitor):
    """Valida thresholds de performance."""
    # Verificar duración
    if monitor['duration'] > PERFORMANCE_CONFIG['max_response_time_ms'] / 1000:
        monitor['warnings'].append(
            f"Test tardó {monitor['duration']:.3f}s, "
            f"límite: {PERFORMANCE_CONFIG['max_response_time_ms']/1000}s"
        )
    
    # Verificar memoria
    if monitor['memory_delta'] > PERFORMANCE_CONFIG['memory_leak_threshold_mb']:
        monitor['warnings'].append(
            f"Incremento de memoria: {monitor['memory_delta']:.2f}MB, "
            f"límite: {PERFORMANCE_CONFIG['memory_leak_threshold_mb']}MB"
        )
    
    # Log warnings
    for warning in monitor['warnings']:
        logger.warning(f"⚠️  Performance: {warning}")


def generate_test_summary_report(session, exitstatus):
    """Genera reporte de resumen de la sesión de testing."""
    try:
        report_file = Path("tests/reports/test_summary.json")
        
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'exit_status': exitstatus,
            'python_version': sys.version.split()[0],
            'pytest_version': pytest.__version__,
            'database_url': os.getenv('DATABASE_URL', 'not configured'),
            'test_environment': os.getenv('FLASK_ENV', 'not configured'),
            'total_duration': getattr(session, 'testscollected', 0),
        }
        
        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 Reporte de resumen generado: {report_file}")
        
    except Exception as e:
        logger.warning(f"⚠️  Error generando reporte de resumen: {e}")


# ============================================================================
# CONFIGURACIÓN FINAL
# ============================================================================

# Configurar Faker para datos consistentes
fake.seed_instance(42)

logger.info("🔧 Configuración avanzada de pytest cargada")
logger.info(f"📋 Fixtures disponibles: {len([name for name in globals() if name.endswith('_fixture') or 'fixture' in str(globals()[name])])}")
logger.info(f"🎯 Markers configurados: unit, integration, functional, performance, external, websocket, file_upload, permissions")
logger.info("✅ conftest.py inicializado correctamente")