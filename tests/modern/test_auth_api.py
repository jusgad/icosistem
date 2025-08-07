"""
Modern tests for authentication API endpoints.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from flask_jwt_extended import decode_token

from app.models.user import User
from .conftest import assert_valid_json_response, assert_error_response, assert_success_response


@pytest.mark.api
@pytest.mark.auth
class TestAuthAPI:
    """Test authentication API endpoints."""
    
    def test_login_success(self, api_client, test_user, clean_db):
        """Test successful login."""
        login_data = {
            'email': test_user.email,
            'password': 'testpassword123!',
            'remember_me': False
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_success_response(response, 200)
        
        # Verify response structure
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['token_type'] == 'bearer'
        assert 'expires_in' in data
        assert 'user' in data
        assert 'permissions' in data
        
        # Verify user data
        user_data = data['user']
        assert user_data['email'] == test_user.email
        assert user_data['first_name'] == test_user.first_name
        assert user_data['user_type'] == test_user.user_type
    
    def test_login_invalid_credentials(self, api_client, test_user):
        """Test login with invalid credentials."""
        login_data = {
            'email': test_user.email,
            'password': 'wrongpassword'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_error_response(response, 'authentication_error', 401)
        
        assert 'Invalid email or password' in data['message']
    
    def test_login_nonexistent_user(self, api_client):
        """Test login with nonexistent user."""
        login_data = {
            'email': 'nonexistent@example.com',
            'password': 'password123'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_error_response(response, 'authentication_error', 401)
    
    def test_login_inactive_user(self, api_client, test_user, clean_db):
        """Test login with inactive user account."""
        test_user.is_active = False
        clean_db.commit()
        
        login_data = {
            'email': test_user.email,
            'password': 'testpassword123!'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_error_response(response, 'account_inactive', 401)
    
    def test_login_unverified_email(self, api_client, test_user, clean_db):
        """Test login with unverified email."""
        test_user.email_verified = False
        clean_db.commit()
        
        login_data = {
            'email': test_user.email,
            'password': 'testpassword123!'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_error_response(response, 'email_not_verified', 401)
    
    def test_login_missing_fields(self, api_client):
        """Test login with missing required fields."""
        # Missing password
        response = api_client.post('/api/v2/auth/login', json={'email': 'test@example.com'})
        assert_error_response(response, 'validation_error', 400)
        
        # Missing email
        response = api_client.post('/api/v2/auth/login', json={'password': 'password123'})
        assert_error_response(response, 'validation_error', 400)
    
    @patch('app.services.auth_service.AuthService.is_account_locked')
    def test_login_account_locked(self, mock_locked, api_client, test_user):
        """Test login with locked account."""
        mock_locked.return_value = True
        
        login_data = {
            'email': test_user.email,
            'password': 'testpassword123!'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_error_response(response, 'account_locked', 423)
    
    def test_register_success(self, api_client, clean_db):
        """Test successful user registration."""
        register_data = {
            'email': 'newuser@example.com',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'entrepreneur',
            'terms_accepted': True,
            'privacy_accepted': True,
            'marketing_consent': False
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        data = assert_success_response(response, 201)
        
        assert 'Registration successful' in data['message']
        assert data['email_verification_required'] is True
        assert 'user' in data
        
        # Verify user was created in database
        user = User.query.filter_by(email='newuser@example.com').first()
        assert user is not None
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert user.user_type == 'entrepreneur'
        assert user.email_verified is False  # Should require verification
    
    def test_register_password_mismatch(self, api_client):
        """Test registration with password mismatch."""
        register_data = {
            'email': 'newuser@example.com',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'entrepreneur',
            'terms_accepted': True,
            'privacy_accepted': True
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        assert_error_response(response, 'validation_error', 400)
    
    def test_register_weak_password(self, api_client):
        """Test registration with weak password."""
        register_data = {
            'email': 'newuser@example.com',
            'password': '123',  # Too weak
            'confirm_password': '123',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'entrepreneur',
            'terms_accepted': True,
            'privacy_accepted': True
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        assert_error_response(response, 'validation_error', 400)
    
    def test_register_existing_email(self, api_client, test_user):
        """Test registration with existing email."""
        register_data = {
            'email': test_user.email,
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'entrepreneur',
            'terms_accepted': True,
            'privacy_accepted': True
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        data = assert_error_response(response, 'user_exists', 409)
    
    def test_register_terms_not_accepted(self, api_client):
        """Test registration without accepting terms."""
        register_data = {
            'email': 'newuser@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'entrepreneur',
            'terms_accepted': False,  # Not accepted
            'privacy_accepted': True
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        assert_error_response(response, 'validation_error', 400)
    
    def test_logout_success(self, authenticated_api_client):
        """Test successful logout."""
        response = authenticated_api_client.post('/api/v2/auth/logout')
        data = assert_success_response(response, 200)
        
        assert 'Logged out successfully' in data['message']
    
    def test_logout_without_auth(self, api_client):
        """Test logout without authentication."""
        response = api_client.post('/api/v2/auth/logout')
        assert response.status_code == 401
    
    def test_token_refresh_success(self, api_client, test_user, auth_headers):
        """Test successful token refresh."""
        from flask_jwt_extended import create_refresh_token
        
        with api_client.client.application.app_context():
            refresh_token = create_refresh_token(identity=test_user.id)
        
        headers = {'Authorization': f'Bearer {refresh_token}'}
        response = api_client.post('/api/v2/auth/refresh', headers=headers)
        
        data = assert_success_response(response, 200)
        
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'
        assert 'expires_in' in data
    
    def test_token_refresh_invalid_token(self, api_client):
        """Test token refresh with invalid token."""
        headers = {'Authorization': 'Bearer invalid_token'}
        response = api_client.post('/api/v2/auth/refresh', headers=headers)
        
        assert response.status_code == 422  # Unprocessable Entity for invalid JWT
    
    def test_token_refresh_inactive_user(self, api_client, test_user, clean_db):
        """Test token refresh with inactive user."""
        from flask_jwt_extended import create_refresh_token
        
        # Create refresh token first
        with api_client.client.application.app_context():
            refresh_token = create_refresh_token(identity=test_user.id)
        
        # Deactivate user
        test_user.is_active = False
        clean_db.commit()
        
        headers = {'Authorization': f'Bearer {refresh_token}'}
        response = api_client.post('/api/v2/auth/refresh', headers=headers)
        
        data = assert_error_response(response, 'invalid_user', 401)
    
    def test_password_reset_request(self, api_client, test_user, mock_email):
        """Test password reset request."""
        reset_data = {'email': test_user.email}
        
        response = api_client.post('/api/v2/auth/password-reset', json=reset_data)
        data = assert_success_response(response, 200)
        
        # Should always return success for security
        assert 'password reset email has been sent' in data['message'].lower()
    
    def test_password_reset_request_nonexistent_email(self, api_client, mock_email):
        """Test password reset request with nonexistent email."""
        reset_data = {'email': 'nonexistent@example.com'}
        
        response = api_client.post('/api/v2/auth/password-reset', json=reset_data)
        data = assert_success_response(response, 200)
        
        # Should still return success for security
        assert 'password reset email has been sent' in data['message'].lower()
    
    def test_password_reset_missing_email(self, api_client):
        """Test password reset request without email."""
        response = api_client.post('/api/v2/auth/password-reset', json={})
        assert_error_response(response, 'validation_error', 400)
    
    @patch('app.services.auth_service.AuthService.save_temp_two_factor_secret')
    @patch('app.services.auth_service.AuthService.generate_backup_codes')
    def test_two_factor_setup(self, mock_backup_codes, mock_save_secret, authenticated_api_client):
        """Test two-factor authentication setup."""
        mock_backup_codes.return_value = ['123456', '789012', '345678']
        
        response = authenticated_api_client.post('/api/v2/auth/two-factor/setup')
        data = assert_success_response(response, 200)
        
        assert 'qr_code' in data
        assert 'secret' in data
        assert 'backup_codes' in data
        assert len(data['backup_codes']) == 3
    
    def test_two_factor_setup_without_auth(self, api_client):
        """Test 2FA setup without authentication."""
        response = api_client.post('/api/v2/auth/two-factor/setup')
        assert response.status_code == 401
    
    @patch('app.services.auth_service.AuthService.verify_temp_two_factor_code')
    @patch('app.services.auth_service.AuthService.enable_two_factor_auth')
    def test_two_factor_verify_success(self, mock_enable, mock_verify, authenticated_api_client):
        """Test successful 2FA verification."""
        mock_verify.return_value = True
        
        verify_data = {'code': '123456'}
        
        response = authenticated_api_client.post('/api/v2/auth/two-factor/verify', json=verify_data)
        data = assert_success_response(response, 200)
        
        assert 'enabled successfully' in data['message']
        mock_enable.assert_called_once()
    
    @patch('app.services.auth_service.AuthService.verify_temp_two_factor_code')
    def test_two_factor_verify_invalid_code(self, mock_verify, authenticated_api_client):
        """Test 2FA verification with invalid code."""
        mock_verify.return_value = False
        
        verify_data = {'code': '000000'}
        
        response = authenticated_api_client.post('/api/v2/auth/two-factor/verify', json=verify_data)
        data = assert_error_response(response, 'invalid_code', 400)
    
    def test_two_factor_verify_missing_code(self, authenticated_api_client):
        """Test 2FA verification without code."""
        response = authenticated_api_client.post('/api/v2/auth/two-factor/verify', json={})
        assert_error_response(response, 'validation_error', 400)
    
    def test_two_factor_verify_without_auth(self, api_client):
        """Test 2FA verification without authentication."""
        response = api_client.post('/api/v2/auth/two-factor/verify', json={'code': '123456'})
        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.auth
@pytest.mark.integration
class TestAuthIntegration:
    """Integration tests for authentication flow."""
    
    def test_complete_registration_and_login_flow(self, api_client, clean_db, mock_email):
        """Test complete registration and login flow."""
        # 1. Register new user
        register_data = {
            'email': 'integration@example.com',
            'password': 'IntegrationTest123!',
            'confirm_password': 'IntegrationTest123!',
            'first_name': 'Integration',
            'last_name': 'Test',
            'user_type': 'entrepreneur',
            'terms_accepted': True,
            'privacy_accepted': True
        }
        
        response = api_client.post('/api/v2/auth/register', json=register_data)
        assert_success_response(response, 201)
        
        # 2. Verify user was created but email not verified
        user = User.query.filter_by(email='integration@example.com').first()
        assert user is not None
        assert user.email_verified is False
        
        # 3. Manually verify email for testing
        user.email_verified = True
        clean_db.commit()
        
        # 4. Login with new user
        login_data = {
            'email': 'integration@example.com',
            'password': 'IntegrationTest123!'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_success_response(response, 200)
        
        access_token = data['access_token']
        refresh_token = data['refresh_token']
        
        # 5. Access protected resource
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.get('/api/v2/users/me', headers=headers)
        user_data = assert_success_response(response, 200)
        
        assert user_data['email'] == 'integration@example.com'
        
        # 6. Refresh token
        headers = {'Authorization': f'Bearer {refresh_token}'}
        response = api_client.post('/api/v2/auth/refresh', headers=headers)
        refresh_data = assert_success_response(response, 200)
        
        assert 'access_token' in refresh_data
        
        # 7. Logout
        headers = {'Authorization': f'Bearer {refresh_data["access_token"]}'}
        response = api_client.post('/api/v2/auth/logout', headers=headers)
        assert_success_response(response, 200)
    
    def test_login_attempt_lockout_flow(self, api_client, test_user, clean_db):
        """Test account lockout after multiple failed login attempts."""
        login_data = {
            'email': test_user.email,
            'password': 'wrongpassword'
        }
        
        # Make multiple failed attempts
        with patch('app.services.auth_service.AuthService.is_account_locked') as mock_locked:
            # First few attempts should fail normally
            mock_locked.return_value = False
            
            for _ in range(3):
                response = api_client.post('/api/v2/auth/login', json=login_data)
                assert_error_response(response, 'authentication_error', 401)
            
            # Subsequent attempt should be locked
            mock_locked.return_value = True
            response = api_client.post('/api/v2/auth/login', json=login_data)
            assert_error_response(response, 'account_locked', 423)
    
    @patch('app.services.auth_service.AuthService.verify_two_factor_code')
    def test_two_factor_authentication_flow(self, mock_verify_2fa, api_client, test_user, clean_db):
        """Test two-factor authentication flow."""
        # Enable 2FA for test user
        test_user.two_factor_enabled = True
        clean_db.commit()
        
        # First login without 2FA code
        login_data = {
            'email': test_user.email,
            'password': 'testpassword123!'
        }
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_success_response(response, 200)
        
        assert data['two_factor_required'] is True
        assert 'access_token' not in data
        
        # Login with 2FA code
        mock_verify_2fa.return_value = True
        login_data['two_factor_code'] = '123456'
        
        response = api_client.post('/api/v2/auth/login', json=login_data)
        data = assert_success_response(response, 200)
        
        assert data['two_factor_required'] is False
        assert 'access_token' in data
        assert 'refresh_token' in data
    
    def test_token_expiration_and_refresh_flow(self, api_client, test_user):
        """Test token expiration and refresh flow."""
        from flask_jwt_extended import create_access_token, create_refresh_token
        
        with api_client.client.application.app_context():
            # Create short-lived access token
            access_token = create_access_token(
                identity=test_user.id,
                expires_delta=timedelta(seconds=1)
            )
            refresh_token = create_refresh_token(identity=test_user.id)
        
        # Wait for token to expire (in real test, you'd mock time)
        import time
        time.sleep(2)
        
        # Try to access protected resource with expired token
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.get('/api/v2/users/me', headers=headers)
        assert response.status_code == 422  # Token expired
        
        # Refresh token
        headers = {'Authorization': f'Bearer {refresh_token}'}
        response = api_client.post('/api/v2/auth/refresh', headers=headers)
        data = assert_success_response(response, 200)
        
        # Use new token
        new_access_token = data['access_token']
        headers = {'Authorization': f'Bearer {new_access_token}'}
        response = api_client.get('/api/v2/users/me', headers=headers)
        assert_success_response(response, 200)
    
    @pytest.mark.slow
    def test_concurrent_login_attempts(self, api_client, test_user):
        """Test handling of concurrent login attempts."""
        import threading
        import time
        
        results = []
        
        def login_attempt():
            login_data = {
                'email': test_user.email,
                'password': 'testpassword123!'
            }
            response = api_client.post('/api/v2/auth/login', json=login_data)
            results.append(response.status_code)
        
        # Start multiple concurrent login attempts
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=login_attempt)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All attempts should succeed (assuming no rate limiting in tests)
        assert all(status == 200 for status in results)
        assert len(results) == 5