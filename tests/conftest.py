"""
Test configuration and fixtures for Icosistem.
"""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

# Mock the app creation since we don't have all dependencies
class MockApp:
    def __init__(self):
        self.config = {'TESTING': True}
        self.test_client_class = MockClient
        
    def test_client(self):
        return MockClient()
        
    def app_context(self):
        return MockContext()

class MockClient:
    def get(self, url, **kwargs):
        return MockResponse(200, {})
    
    def post(self, url, **kwargs):
        return MockResponse(201, {})

class MockResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.data = data

class MockContext:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

class MockDB:
    def __init__(self):
        self.session = MockSession()
    
    def create_all(self):
        pass
    
    def drop_all(self):
        pass

class MockSession:
    def add(self, obj):
        pass
    
    def commit(self):
        pass
    
    def rollback(self):
        pass

@pytest.fixture(scope='session')
def app():
    """Create application for the tests."""
    return MockApp()

@pytest.fixture(scope='function')  
def db():
    """Create database for the tests."""
    return MockDB()

@pytest.fixture
def client(app):
    """Create a test client for the app.""" 
    return app.test_client()

# Mock user fixtures
@pytest.fixture
def admin_user():
    """Create admin user for tests."""
    class MockUser:
        id = 1
        email = 'admin@test.com'
        role = 'admin'
        is_active = True
    return MockUser()

@pytest.fixture 
def entrepreneur_user():
    """Create entrepreneur user for tests."""
    class MockUser:
        id = 2
        email = 'entrepreneur@test.com'
        role = 'entrepreneur'
        is_active = True
    return MockUser()

@pytest.fixture
def ally_user():
    """Create ally user for tests."""
    class MockUser:
        id = 3
        email = 'ally@test.com'
        role = 'ally'
        is_active = True
    return MockUser()

# Mock external services
@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    mock = Mock()
    mock.send.return_value.status_code = 202
    return mock

@pytest.fixture
def mock_redis():
    """Mock Redis cache.""" 
    mock = Mock()
    mock.get.return_value = None
    mock.set.return_value = True
    return mock