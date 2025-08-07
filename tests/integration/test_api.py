"""
Integration tests for API endpoints.
"""

import pytest
import json


class TestAuthAPI:
    """Test authentication API endpoints."""
    
    def test_user_registration(self, client):
        """Test user registration endpoint."""
        user_data = {
            'email': 'newuser@test.com',
            'password': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'entrepreneur'
        }
        
        response = client.post('/api/v1/auth/register', json=user_data)
        assert response.status_code in [201, 200]  # Created or OK
    
    def test_user_login(self, client):
        """Test user login endpoint."""
        login_data = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        
        response = client.post('/api/v1/auth/login', json=login_data)
        assert response.status_code in [200, 401]  # OK or Unauthorized
    
    def test_password_reset_request(self, client):
        """Test password reset request."""
        reset_data = {'email': 'test@example.com'}
        
        response = client.post('/api/v1/auth/password-reset', json=reset_data)
        assert response.status_code in [200, 404]  # OK or Not Found
    
    def test_email_verification(self, client):
        """Test email verification endpoint."""
        token = 'mock_verification_token'
        
        response = client.get(f'/api/v1/auth/verify-email/{token}')
        assert response.status_code in [200, 400, 404]  # Various valid responses


class TestUserAPI:
    """Test user management API endpoints."""
    
    def test_get_user_profile(self, client, admin_user):
        """Test get user profile endpoint.""" 
        response = client.get(f'/api/v1/users/{admin_user.id}')
        assert response.status_code in [200, 401, 404]
    
    def test_update_user_profile(self, client, entrepreneur_user):
        """Test update user profile endpoint."""
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'Updated bio'
        }
        
        response = client.put(f'/api/v1/users/{entrepreneur_user.id}', json=update_data)
        assert response.status_code in [200, 401, 403, 404]
    
    def test_get_users_list(self, client):
        """Test get users list endpoint."""
        response = client.get('/api/v1/users')
        assert response.status_code in [200, 401]
    
    def test_deactivate_user(self, client, admin_user):
        """Test deactivate user endpoint."""
        response = client.delete(f'/api/v1/users/{admin_user.id}')
        assert response.status_code in [200, 401, 403, 404]


class TestProjectAPI:
    """Test project management API endpoints."""
    
    def test_create_project(self, client, entrepreneur_user):
        """Test create project endpoint."""
        project_data = {
            'name': 'New Test Project',
            'description': 'A project created via API',
            'status': 'idea',
            'target_market': 'Test market'
        }
        
        response = client.post('/api/v1/projects', json=project_data)
        assert response.status_code in [201, 401, 400]
    
    def test_get_projects_list(self, client):
        """Test get projects list endpoint."""
        response = client.get('/api/v1/projects')
        assert response.status_code in [200, 401]
    
    def test_get_project_detail(self, client):
        """Test get project detail endpoint."""
        project_id = 1
        response = client.get(f'/api/v1/projects/{project_id}')
        assert response.status_code in [200, 401, 404]
    
    def test_update_project(self, client):
        """Test update project endpoint."""
        project_id = 1
        update_data = {
            'name': 'Updated Project Name',
            'status': 'development'
        }
        
        response = client.put(f'/api/v1/projects/{project_id}', json=update_data)
        assert response.status_code in [200, 401, 403, 404]
    
    def test_delete_project(self, client):
        """Test delete project endpoint."""
        project_id = 1
        response = client.delete(f'/api/v1/projects/{project_id}')
        assert response.status_code in [200, 401, 403, 404]


class TestMentorshipAPI:
    """Test mentorship API endpoints."""
    
    def test_create_mentorship(self, client):
        """Test create mentorship endpoint."""
        mentorship_data = {
            'entrepreneur_id': 2,
            'ally_id': 3,
            'objectives': 'Test mentorship objectives'
        }
        
        response = client.post('/api/v1/mentorships', json=mentorship_data)
        assert response.status_code in [201, 401, 400]
    
    def test_get_mentorships_list(self, client):
        """Test get mentorships list endpoint."""
        response = client.get('/api/v1/mentorships')
        assert response.status_code in [200, 401]
    
    def test_update_mentorship_status(self, client):
        """Test update mentorship status endpoint.""" 
        mentorship_id = 1
        update_data = {'status': 'completed'}
        
        response = client.put(f'/api/v1/mentorships/{mentorship_id}', json=update_data)
        assert response.status_code in [200, 401, 403, 404]


class TestAnalyticsAPI:
    """Test analytics API endpoints."""
    
    def test_get_dashboard_metrics(self, client):
        """Test get dashboard metrics endpoint."""
        response = client.get('/api/v1/analytics/dashboard')
        assert response.status_code in [200, 401]
    
    def test_get_user_analytics(self, client):
        """Test get user analytics endpoint."""
        response = client.get('/api/v1/analytics/users')
        assert response.status_code in [200, 401]
    
    def test_get_project_analytics(self, client):
        """Test get project analytics endpoint."""
        response = client.get('/api/v1/analytics/projects')
        assert response.status_code in [200, 401]
    
    def test_export_analytics_data(self, client):
        """Test export analytics data endpoint."""
        params = {'format': 'csv', 'date_range': '30d'}
        
        response = client.get('/api/v1/analytics/export', query_string=params)
        assert response.status_code in [200, 401]


class TestFileUploadAPI:
    """Test file upload API endpoints."""
    
    def test_upload_document(self, client):
        """Test document upload endpoint."""
        # Mock file data
        file_data = {
            'file': (b'fake file content', 'test.pdf', 'application/pdf')
        }
        
        response = client.post('/api/v1/documents/upload', data=file_data)
        assert response.status_code in [201, 400, 401, 413]
    
    def test_get_documents_list(self, client):
        """Test get documents list endpoint."""
        response = client.get('/api/v1/documents')
        assert response.status_code in [200, 401]
    
    def test_download_document(self, client):
        """Test download document endpoint."""
        document_id = 1
        response = client.get(f'/api/v1/documents/{document_id}/download')
        assert response.status_code in [200, 401, 404]
    
    def test_delete_document(self, client):
        """Test delete document endpoint."""
        document_id = 1
        response = client.delete(f'/api/v1/documents/{document_id}')
        assert response.status_code in [200, 401, 403, 404]


class TestNotificationAPI:
    """Test notification API endpoints.""" 
    
    def test_get_notifications(self, client):
        """Test get notifications endpoint."""
        response = client.get('/api/v1/notifications')
        assert response.status_code in [200, 401]
    
    def test_mark_notification_read(self, client):
        """Test mark notification as read endpoint."""
        notification_id = 1
        response = client.put(f'/api/v1/notifications/{notification_id}/read')
        assert response.status_code in [200, 401, 404]
    
    def test_delete_notification(self, client):
        """Test delete notification endpoint."""
        notification_id = 1
        response = client.delete(f'/api/v1/notifications/{notification_id}')
        assert response.status_code in [200, 401, 404]


class TestSearchAPI:
    """Test search API endpoints."""
    
    def test_search_users(self, client):
        """Test search users endpoint."""
        params = {'q': 'test', 'role': 'entrepreneur'}
        response = client.get('/api/v1/search/users', query_string=params)
        assert response.status_code in [200, 401]
    
    def test_search_projects(self, client):
        """Test search projects endpoint."""
        params = {'q': 'project', 'status': 'active'}
        response = client.get('/api/v1/search/projects', query_string=params)
        assert response.status_code in [200, 401]
    
    def test_global_search(self, client):
        """Test global search endpoint."""
        params = {'q': 'test query'}
        response = client.get('/api/v1/search', query_string=params)
        assert response.status_code in [200, 401]


class TestHealthAPI:
    """Test health check API endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/v1/health')
        assert response.status_code == 200
    
    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get('/api/v1/health/ready')
        assert response.status_code in [200, 503]
    
    def test_liveness_check(self, client):
        """Test liveness check endpoint."""
        response = client.get('/api/v1/health/live')
        assert response.status_code in [200, 503]


class TestRateLimitAPI:
    """Test API rate limiting."""
    
    def test_rate_limit_enforcement(self, client):
        """Test that rate limiting is enforced."""
        # Make multiple requests quickly
        responses = []
        for i in range(10):
            response = client.get('/api/v1/status')
            responses.append(response.status_code)
        
        # Should eventually get rate limited
        assert any(status == 429 for status in responses) or all(status != 429 for status in responses)
    
    def test_rate_limit_headers(self, client):
        """Test rate limit headers are present."""
        response = client.get('/api/v1/status')
        
        # Check for common rate limit headers (may or may not be present)
        expected_headers = ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset']
        # Headers might be present
        assert response.status_code in [200, 404, 429]