import pytest
import json
from src.models import db
from src.models.user import User
from src.models.organization import Organization

class TestAuth:
    """Tests pour l'authentification"""
    
    def test_register_success(self, client):
        """Test d'inscription réussie"""
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
        assert data['user']['role'] == 'admin'  # Premier utilisateur devient admin
    
    def test_register_invalid_email(self, client):
        """Test d'inscription avec email invalide"""
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
        """Test d'inscription avec mot de passe faible"""
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
        """Test d'inscription avec email déjà utilisé"""
        # Première inscription
        client.post('/api/auth/register', json={
            'email': 'duplicate@example.com',
            'password': 'Password123!',
            'first_name': 'First',
            'last_name': 'User'
        })
        
        # Tentative de duplication
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
        """Test de connexion réussie"""
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
        """Test de connexion avec identifiants invalides"""
        response = client.post('/api/auth/login', json={
            'email': 'nonexistent@example.com',
            'password': 'WrongPassword123!'
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid email or password' in data['error']
    
    def test_get_current_user(self, client, auth_headers):
        """Test de récupération de l'utilisateur actuel"""
        response = client.get('/api/auth/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'user' in data
        assert data['user']['email'] == 'test@example.com'
        assert 'organization' in data['user']
    
    def test_get_current_user_without_token(self, client):
        """Test de récupération de l'utilisateur sans token"""
        response = client.get('/api/auth/me')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Token is missing' in data['error']
    
    def test_get_current_user_invalid_token(self, client):
        """Test de récupération de l'utilisateur avec token invalide"""
        headers = {'Authorization': 'Bearer invalid_token'}
        response = client.get('/api/auth/me', headers=headers)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Token is invalid or expired' in data['error']
    
    def test_change_password(self, client, auth_headers):
        """Test de changement de mot de passe"""
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
        """Test de changement de mot de passe avec ancien mot de passe incorrect"""
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
        """Test de déconnexion"""
        response = client.post('/api/auth/logout', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Logout successful'
    
    def test_refresh_token(self, client):
        """Test de rafraîchissement de token"""
        # D'abord s'inscrire pour obtenir un refresh token
        register_response = client.post('/api/auth/register', json={
            'email': 'refresh@example.com',
            'password': 'RefreshPassword123!',
            'first_name': 'Refresh',
            'last_name': 'User'
        })
        
        register_data = register_response.get_json()
        refresh_token = register_data['tokens']['refresh_token']
        
        # Utiliser le refresh token
        response = client.post('/api/auth/refresh', json={
            'refresh_token': refresh_token
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Token refreshed successfully'
        assert 'tokens' in data

