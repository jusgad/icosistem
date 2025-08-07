"""
Modern pytest configuration and fixtures for the entrepreneurship ecosystem.

This module provides comprehensive fixtures and utilities for testing with:
- Async support
- Factory patterns
- Database management
- Authentication helpers
- API testing utilities
- Modern mocking
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Generator
from unittest.mock import AsyncMock, MagicMock, patch

# Flask and SQLAlchemy
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

# Factory Boy for modern test data generation
import factory
from factory import fuzzy
from factory.alchemy import SQLAlchemyModelFactory

# Testing utilities
from faker import Faker
import responses

# Application imports
from app import create_app
from app.extensions_modern import extensions, db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project

fake = Faker()


# ====================================
# PYTEST CONFIGURATION
# ====================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests") 
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "async_test: Async tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "database: Tests requiring database")
    config.addinivalue_line("markers", "redis: Tests requiring Redis")
    config.addinivalue_line("markers", "auth: Authentication tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark async tests."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.async_test)


# ====================================
# ASYNC SUPPORT
# ====================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client(app):
    """Async HTTP client for testing."""
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# ====================================
# APPLICATION FIXTURES
# ====================================

@pytest.fixture(scope="session")
def app() -> Generator[Flask, None, None]:
    """Create test application instance."""
    app = create_app('testing')
    
    # Override configuration for testing
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'REDIS_URL': 'redis://localhost:6379/15',  # Test database
        'CELERY_TASK_ALWAYS_EAGER': True,
        'CELERY_TASK_EAGER_PROPAGATES': True,
        'JWT_ACCESS_TOKEN_EXPIRES': timedelta(minutes=15),
        'JWT_REFRESH_TOKEN_EXPIRES': timedelta(days=1),
        'RATELIMIT_ENABLED': False,  # Disable rate limiting in tests
        'CACHE_TYPE': 'SimpleCache',  # Use simple cache for tests
        'MAIL_SUPPRESS_SEND': True,  # Don't send emails in tests
    })
    
    with app.app_context():
        yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app: Flask):
    """Flask CLI test runner."""
    return app.test_cli_runner()


# ====================================
# DATABASE FIXTURES
# ====================================

@pytest.fixture(scope="session")
def database_engine(app: Flask):
    """Create database engine for testing."""
    # Use in-memory SQLite with connection pooling for tests
    engine = create_engine(
        'sqlite:///:memory:',
        poolclass=StaticPool,
        connect_args={'check_same_thread': False},
        echo=app.config.get('SQLALCHEMY_ECHO', False)
    )
    
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(app: Flask, database_engine):
    """Create database session for testing."""
    connection = database_engine.connect()
    transaction = connection.begin()
    
    # Create all tables
    with app.app_context():
        db.metadata.create_all(bind=connection)
        
        # Create scoped session
        session = scoped_session(
            sessionmaker(bind=connection, expire_on_commit=False)
        )
        
        # Replace app db session with test session
        db.session = session
        
        yield session
        
        # Cleanup
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def clean_db(db_session):
    """Clean database fixture that truncates all tables."""
    # Truncate all tables before each test
    for table in reversed(db.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
    
    yield db_session
    
    # Clean up after test
    for table in reversed(db.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()


# ====================================
# FACTORY FIXTURES
# ====================================

class UserFactory(SQLAlchemyModelFactory):
    """Factory for creating test users."""
    
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name') 
    password_hash = factory.LazyFunction(
        lambda: generate_password_hash('testpassword123!')
    )
    user_type = fuzzy.FuzzyChoice(['entrepreneur', 'ally', 'client'])
    is_active = True
    email_verified = True
    phone = factory.Faker('phone_number')
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class EntrepreneurFactory(SQLAlchemyModelFactory):
    """Factory for creating test entrepreneurs."""
    
    class Meta:
        model = Entrepreneur
        sqlalchemy_session_persistence = "commit"
    
    user = factory.SubFactory(UserFactory, user_type='entrepreneur')
    business_stage = fuzzy.FuzzyChoice(['idea', 'validation', 'growth', 'scale'])
    company_name = factory.Faker('company')
    industry = factory.Faker('bs')
    description = factory.Faker('text', max_nb_chars=500)
    founded_year = fuzzy.FuzzyInteger(2015, 2024)
    employees_count = fuzzy.FuzzyInteger(1, 100)
    annual_revenue = fuzzy.FuzzyInteger(0, 1000000)


class ProjectFactory(SQLAlchemyModelFactory):
    """Factory for creating test projects."""
    
    class Meta:
        model = Project
        sqlalchemy_session_persistence = "commit"
    
    name = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=1000)
    owner = factory.SubFactory(EntrepreneurFactory)
    status = fuzzy.FuzzyChoice(['active', 'completed', 'paused', 'cancelled'])
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


@pytest.fixture
def user_factory():
    """User factory fixture."""
    return UserFactory


@pytest.fixture
def entrepreneur_factory():
    """Entrepreneur factory fixture."""
    return EntrepreneurFactory


@pytest.fixture
def project_factory():
    """Project factory fixture."""
    return ProjectFactory


# ====================================
# AUTHENTICATION FIXTURES
# ====================================

@pytest.fixture
def test_user(clean_db) -> User:
    """Create a test user."""
    from werkzeug.security import generate_password_hash
    
    user = User(
        email='testuser@example.com',
        first_name='Test',
        last_name='User',
        password_hash=generate_password_hash('testpassword123!'),
        user_type='entrepreneur',
        is_active=True,
        email_verified=True
    )
    clean_db.add(user)
    clean_db.commit()
    clean_db.refresh(user)
    
    return user


@pytest.fixture 
def admin_user(clean_db) -> User:
    """Create an admin user."""
    from werkzeug.security import generate_password_hash
    
    user = User(
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        password_hash=generate_password_hash('adminpassword123!'),
        user_type='admin',
        is_active=True,
        email_verified=True
    )
    clean_db.add(user)
    clean_db.commit()
    clean_db.refresh(user)
    
    return user


@pytest.fixture
def auth_headers(test_user, client) -> Dict[str, str]:
    """Generate authentication headers for test user."""
    from flask_jwt_extended import create_access_token
    
    with client.application.app_context():
        access_token = create_access_token(identity=test_user.id)
        
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def admin_auth_headers(admin_user, client) -> Dict[str, str]:
    """Generate authentication headers for admin user."""
    from flask_jwt_extended import create_access_token
    
    with client.application.app_context():
        access_token = create_access_token(identity=admin_user.id)
        
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }


# ====================================
# API TESTING FIXTURES
# ====================================

@pytest.fixture
def api_client(client):
    """API client with JSON content type."""
    class APIClient:
        def __init__(self, test_client):
            self.client = test_client
            
        def get(self, url, headers=None, **kwargs):
            headers = headers or {}
            headers.setdefault('Content-Type', 'application/json')
            return self.client.get(url, headers=headers, **kwargs)
            
        def post(self, url, json=None, headers=None, **kwargs):
            headers = headers or {}
            headers.setdefault('Content-Type', 'application/json')
            return self.client.post(url, json=json, headers=headers, **kwargs)
            
        def put(self, url, json=None, headers=None, **kwargs):
            headers = headers or {}
            headers.setdefault('Content-Type', 'application/json')
            return self.client.put(url, json=json, headers=headers, **kwargs)
            
        def patch(self, url, json=None, headers=None, **kwargs):
            headers = headers or {}
            headers.setdefault('Content-Type', 'application/json')
            return self.client.patch(url, json=json, headers=headers, **kwargs)
            
        def delete(self, url, headers=None, **kwargs):
            headers = headers or {}
            headers.setdefault('Content-Type', 'application/json')
            return self.client.delete(url, headers=headers, **kwargs)
    
    return APIClient(client)


@pytest.fixture
def authenticated_api_client(api_client, auth_headers):
    """Authenticated API client."""
    class AuthenticatedAPIClient:
        def __init__(self, client, headers):
            self.client = client
            self.default_headers = headers
            
        def _merge_headers(self, headers=None):
            merged = self.default_headers.copy()
            if headers:
                merged.update(headers)
            return merged
            
        def get(self, url, headers=None, **kwargs):
            return self.client.get(url, headers=self._merge_headers(headers), **kwargs)
            
        def post(self, url, json=None, headers=None, **kwargs):
            return self.client.post(url, json=json, headers=self._merge_headers(headers), **kwargs)
            
        def put(self, url, json=None, headers=None, **kwargs):
            return self.client.put(url, json=json, headers=self._merge_headers(headers), **kwargs)
            
        def patch(self, url, json=None, headers=None, **kwargs):
            return self.client.patch(url, json=json, headers=self._merge_headers(headers), **kwargs)
            
        def delete(self, url, headers=None, **kwargs):
            return self.client.delete(url, headers=self._merge_headers(headers), **kwargs)
    
    return AuthenticatedAPIClient(api_client, auth_headers)


# ====================================
# MOCKING FIXTURES
# ====================================

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('app.extensions_modern.redis') as mock:
        # Create async mock
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock(return_value=True)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.keys = AsyncMock(return_value=[])
        
        mock.from_url = MagicMock(return_value=mock_client)
        yield mock_client


@pytest.fixture
def mock_celery():
    """Mock Celery tasks."""
    with patch('app.tasks.celery_app.celery') as mock:
        # Mock task execution
        mock.send_task = MagicMock(return_value=MagicMock(id='test-task-id'))
        yield mock


@pytest.fixture
def mock_email():
    """Mock email service."""
    with patch('app.services.email.EmailService') as mock:
        email_service = MagicMock()
        email_service.send_email = MagicMock(return_value=True)
        email_service.send_template_email = MagicMock(return_value=True)
        mock.return_value = email_service
        yield email_service


@pytest.fixture
def mock_file_storage():
    """Mock file storage service."""
    with patch('app.services.file_storage.FileStorageService') as mock:
        storage_service = MagicMock()
        storage_service.upload_file = MagicMock(return_value='test-file-url')
        storage_service.delete_file = MagicMock(return_value=True)
        storage_service.get_file_url = MagicMock(return_value='test-file-url')
        mock.return_value = storage_service
        yield storage_service


@pytest.fixture
def responses_mock():
    """Mock HTTP responses for external API calls."""
    with responses.RequestsMock() as rsps:
        yield rsps


# ====================================
# TIME AND DATE FIXTURES
# ====================================

@pytest.fixture
def fixed_datetime():
    """Fixed datetime for consistent testing."""
    fixed_dt = datetime(2024, 1, 15, 10, 30, 0)
    
    with patch('app.utils.datetime') as mock_dt:
        mock_dt.utcnow = MagicMock(return_value=fixed_dt)
        mock_dt.now = MagicMock(return_value=fixed_dt)
        yield fixed_dt


@pytest.fixture
def time_machine():
    """Time machine for testing time-dependent code."""
    class TimeMachine:
        def __init__(self):
            self._current_time = datetime.utcnow()
            
        def travel_to(self, target_time: datetime):
            self._current_time = target_time
            
        def advance(self, **kwargs):
            self._current_time += timedelta(**kwargs)
            
        @property
        def current_time(self):
            return self._current_time
    
    return TimeMachine()


# ====================================
# PERFORMANCE TESTING FIXTURES
# ====================================

@pytest.fixture
def benchmark_timer():
    """Simple benchmark timer for performance tests."""
    import time
    
    class BenchmarkTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            
        def start(self):
            self.start_time = time.perf_counter()
            
        def stop(self):
            self.end_time = time.perf_counter()
            
        @property
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time
    
    return BenchmarkTimer()


# ====================================
# DATA GENERATORS
# ====================================

@pytest.fixture
def sample_user_data():
    """Generate sample user data."""
    return {
        'email': fake.email(),
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'password': 'TestPassword123!',
        'confirm_password': 'TestPassword123!',
        'user_type': 'entrepreneur',
        'phone': fake.phone_number(),
        'terms_accepted': True,
        'privacy_accepted': True,
        'marketing_consent': False
    }


@pytest.fixture
def sample_project_data():
    """Generate sample project data."""
    return {
        'name': fake.catch_phrase(),
        'description': fake.text(max_nb_chars=500),
        'industry': fake.bs(),
        'stage': 'idea',
        'budget': fake.random_int(min=1000, max=100000),
        'timeline_months': fake.random_int(min=3, max=24)
    }


# ====================================
# CLEANUP UTILITIES
# ====================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatic cleanup after each test."""
    yield
    
    # Clear any cached data
    if hasattr(extensions, 'cache') and extensions.cache:
        try:
            extensions.cache.clear()
        except Exception:
            pass
    
    # Clear Redis test data
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=15)
        r.flushdb()
    except Exception:
        pass


# ====================================
# PYTEST MARKERS
# ====================================

# Automatically apply database marker to tests that use database fixtures
pytestmark = pytest.mark.database


# ====================================
# HELPER FUNCTIONS
# ====================================

def assert_valid_json_response(response, expected_status=200):
    """Assert response is valid JSON with expected status."""
    assert response.status_code == expected_status
    assert response.content_type == 'application/json'
    return response.get_json()


def assert_error_response(response, error_type: str, status_code: int = 400):
    """Assert response is an error response."""
    data = assert_valid_json_response(response, status_code)
    assert data['success'] is False
    assert data['error_type'] == error_type
    return data


def assert_success_response(response, status_code: int = 200):
    """Assert response is a success response."""
    data = assert_valid_json_response(response, status_code)
    assert data.get('success', True) is True
    return data


# Export helper functions
__all__ = [
    'assert_valid_json_response',
    'assert_error_response', 
    'assert_success_response'
]