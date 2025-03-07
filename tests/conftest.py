# tests/conftest.py
"""Configuración y fixtures para pytest."""

import os
import tempfile
import pytest
from app import create_app
from app.extensions import db as _db
from app.models import User, Entrepreneur, Ally, Client

@pytest.fixture(scope='session')
def app():
    """Crea y configura una instancia de la aplicación Flask para las pruebas."""
    # Configurar la aplicación para pruebas
    os.environ['FLASK_ENV'] = 'testing'
    
    # Crear la aplicación con configuración de prueba
    _app = create_app('testing')
    
    # Establecer el contexto de la aplicación
    with _app.app_context():
        yield _app


@pytest.fixture(scope='session')
def db(app):
    """Configurar y obtener el objeto db."""
    # Crear las tablas de la base de datos
    _db.create_all()
    
    yield _db
    
    # Limpiar después de todas las pruebas
    _db.session.remove()
    _db.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """Crear una nueva sesión de base de datos para una prueba."""
    connection = db.engine.connect()
    transaction = connection.begin()
    
    session = db.create_scoped_session(
        options=dict(bind=connection, binds={})
    )
    
    db.session = session
    
    yield session
    
    # Rollback de la transacción al finalizar la prueba
    transaction.rollback()
    connection.close()
    session.remove()


@pytest.fixture
def client(app):
    """Un cliente de prueba para la aplicación."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_user(session):
    """Crear un usuario administrador para pruebas."""
    user = User(
        username='admin_test',
        email='admin@test.com',
        role='admin'
    )
    user.set_password('password123')
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def entrepreneur_user(session):
    """Crear un usuario emprendedor para pruebas."""
    user = User(
        username='entrepreneur_test',
        email='entrepreneur@test.com',
        role='entrepreneur'
    )
    user.set_password('password123')
    session.add(user)
    session.commit()
    
    entrepreneur = Entrepreneur(
        user_id=user.id,
        business_name='Test Business',
        business_sector='Technology',
        business_stage='Early',
        employee_count=5
    )
    session.add(entrepreneur)
    session.commit()
    return user


@pytest.fixture
def ally_user(session):
    """Crear un usuario aliado para pruebas."""
    user = User(
        username='ally_test',
        email='ally@test.com',
        role='ally'
    )
    user.set_password('password123')
    session.add(user)
    session.commit()
    
    ally = Ally(
        user_id=user.id,
        specialty='Business Development',
        experience_years=5,
        organization='Test Organization'
    )
    session.add(ally)
    session.commit()
    return user


@pytest.fixture
def client_user(session):
    """Crear un usuario cliente para pruebas."""
    user = User(
        username='client_test',
        email='client@test.com',
        role='client'
    )
    user.set_password('password123')
    session.add(user)
    session.commit()
    
    client = Client(
        user_id=user.id,
        organization='Test Client Org',
        industry='Technology',
        contact_person='John Doe'
    )
    session.add(client)
    session.commit()
    return user


@pytest.fixture
def authenticated_client(client, admin_user):
    """Un cliente con un usuario autenticado."""
    client.post('/auth/login', data={
        'email': admin_user.email,
        'password': 'password123'
    }, follow_redirects=True)
    return client


@pytest.fixture
def upload_file():
    """Crear un archivo temporal para probar cargas de archivos."""
    with tempfile.NamedTemporaryFile(suffix='.pdf') as temp:
        temp.write(b'Test file content')
        temp.seek(0)
        yield temp