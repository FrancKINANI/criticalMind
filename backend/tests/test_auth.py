import pytest
import json
from src.models import db
from src.models.user import User
from src.models.organization import Organization

class TestAuth:
    """Tests for authentication"""
    
    def test_register_success(self, client):
        """Test successful registration"""
        response = client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'password': 'NewPassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'organization_name': 'New Organization'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'User registered successfully'
        assert 'tokens' in data
        assert 'user' in data
        assert data['user']['email'] == 'newuser@example.com'
        assert data['user']['role'] == 'admin'  # First user becomes admin
    
    def test_register_invalid_email(self, client):
        """Test registration with an invalid email"""
        response = client.post('/api/auth/register', json={
            'email': 'invalid-email',
            'password': 'Password123!',
            'first_name': 'Test',
            'last_name': 'User'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid email format' in data['error']
    
    def test_register_weak_password(self, client):
        """Test registration with a weak password"""
        response = client.post('/api/auth/register', json={
            'email': 'test@example.com',
            'password': '123',
            'first_name': 'Test',
            'last_name': 'User'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Password must be at least 8 characters long' in data['error']
    
    def test_register_duplicate_email(self, client):
        """Test registration with an already used email"""
        # First registration
        client.post('/api/auth/register', json={
            'email': 'duplicate@example.com',
            'password': 'Password123!',
            'first_name': 'First',
            'last_name': 'User'
        })
        
        # Attempt to duplicate
        response = client.post('/api/auth/register', json={
            'email': 'duplicate@example.com',
            'password': 'Password123!',
            'first_name': 'Second',
            'last_name': 'User'
        })
        
        assert response.status_code == 409
        data = response.get_json()
        assert 'User with this email already exists' in data['error']
    
    def test_login_success(self, client, auth_headers):
        """Test successful login"""
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'
        assert 'tokens' in data
        assert 'user' in data
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post('/api/auth/login', json={
            'email': 'nonexistent@example.com',
            'password': 'WrongPassword123!'
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid email or password' in data['error']
    
    def test_get_current_user(self, client, auth_headers):
        """Test retrieving the current user"""
        response = client.get('/api/auth/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'user' in data
        assert data['user']['email'] == 'test@example.com'
        assert 'organization' in data['user']
    
    def test_get_current_user_without_token(self, client):
        """Test retrieving the user without a token"""
        response = client.get('/api/auth/me')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Token is missing' in data['error']
    
    def test_get_current_user_invalid_token(self, client):
        """Test retrieving the user with an invalid token"""
        headers = {'Authorization': 'Bearer invalid_token'}
        response = client.get('/api/auth/me', headers=headers)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Token is invalid or expired' in data['error']
    
    def test_change_password(self, client, auth_headers):
        """Test changing the password"""
        response = client.post('/api/auth/change-password', 
                              headers=auth_headers,
                              json={
                                  'current_password': 'TestPassword123!',
                                  'new_password': 'NewPassword123!'
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Password changed successfully'
    
    def test_change_password_wrong_current(self, client, auth_headers):
        """Test changing the password with an incorrect current password"""
        response = client.post('/api/auth/change-password', 
                              headers=auth_headers,
                              json={
                                  'current_password': 'WrongPassword123!',
                                  'new_password': 'NewPassword123!'
                              })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Current password is incorrect' in data['error']
    
    def test_logout(self, client, auth_headers):
        """Test logout"""
        response = client.post('/api/auth/logout', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Logout successful'
    
    def test_refresh_token(self, client):
        """Test token refresh"""
        # First register to get a refresh token
        register_response = client.post('/api/auth/register', json={
            'email': 'refresh@example.com',
            'password': 'RefreshPassword123!',
            'first_name': 'Refresh',
            'last_name': 'User'
        })
        
        register_data = register_response.get_json()
        refresh_token = register_data['tokens']['refresh_token']
        
        # Use the refresh token
        response = client.post('/api/auth/refresh', json={
            'refresh_token': refresh_token
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Token refreshed successfully'
        assert 'tokens' in data

