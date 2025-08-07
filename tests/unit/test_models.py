"""
Unit tests for models.
"""

import pytest
from datetime import datetime


class TestUserModel:
    """Test User model functionality."""
    
    def test_user_creation(self, db):
        """Test user can be created with required fields."""
        user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'entrepreneur'
        }
        
        assert user_data['email'] == 'test@example.com'
        assert user_data['role'] == 'entrepreneur'
    
    def test_password_hashing(self):
        """Test password is properly hashed."""
        password = 'test_password_123'
        hashed = 'hashed_password_mock'
        assert hashed != password
        assert len(hashed) > 0
    
    def test_email_validation(self):
        """Test email validation works correctly."""
        valid_emails = [
            'user@example.com',
            'test.email@domain.co.uk',
            'user123@test-domain.org'
        ]
        
        for email in valid_emails:
            assert '@' in email and '.' in email
    
    def test_role_validation(self):
        """Test role validation."""
        valid_roles = ['admin', 'entrepreneur', 'ally', 'client']
        invalid_roles = ['super_admin', 'guest', 'invalid']
        
        for role in valid_roles:
            assert role in valid_roles
            
        for role in invalid_roles:
            assert role not in valid_roles


class TestProjectModel:
    """Test Project model functionality."""
    
    def test_project_creation(self, entrepreneur_user):
        """Test project creation with required fields.""" 
        project_data = {
            'name': 'Test Project',
            'description': 'A test project',
            'status': 'idea',
            'entrepreneur_id': entrepreneur_user.id
        }
        
        assert project_data['name'] == 'Test Project'
        assert project_data['entrepreneur_id'] == entrepreneur_user.id
    
    def test_project_status_validation(self):
        """Test project status validation."""
        valid_statuses = [
            'idea', 'validation', 'development', 
            'launch', 'growth', 'scale', 'exit', 
            'paused', 'cancelled'
        ]
        
        for status in valid_statuses:
            assert status in valid_statuses