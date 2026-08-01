import pytest
import json
from src.models import db
from src.models.user import User
from src.models.learning import LearningModule

class TestAdmin:
    """Tests for the admin panel"""
    
    def test_admin_dashboard(self, client, auth_headers):
        """Test the admin dashboard"""
        response = client.get('/api/admin/dashboard', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'stats' in data
        assert 'popular_modules' in data
        assert 'recent_activity' in data
        
        # Check the statistics
        stats = data['stats']
        assert 'total_users' in stats
        assert 'active_users' in stats
        assert 'total_modules' in stats
        assert 'avg_progress' in stats
    
    def test_admin_get_all_users(self, client, auth_headers):
        """Test retrieving all users"""
        response = client.get('/api/admin/users', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'pagination' in data
        
        # Check that at least the admin user exists
        assert len(data['users']) >= 1
        
        # Check the user statistics
        user = data['users'][0]
        assert 'stats' in user
        assert 'modules_completed' in user['stats']
        assert 'total_points' in user['stats']
    
    def test_admin_get_all_modules(self, client, auth_headers):
        """Test retrieving all modules with statistics"""
        # First create a module
        client.post('/api/learning/modules', 
                   headers=auth_headers,
                   json={
                       'title': 'Admin Test Module',
                       'content': {'sections': []},
                       'difficulty_level': 1
                   })
        
        response = client.get('/api/admin/modules', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'modules' in data
        assert 'pagination' in data
        
        # Check the module statistics
        if len(data['modules']) > 0:
            module = data['modules'][0]
            assert 'stats' in module
            assert 'total_enrollments' in module['stats']
            assert 'completion_rate' in module['stats']
    
    def test_toggle_module_status(self, client, auth_headers):
        """Test activating/deactivating a module"""
        # Create a module
        create_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Toggle Test Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = create_response.get_json()['module']['id']
        
        # Deactivate the module
        response = client.post(f'/api/admin/modules/{module_id}/toggle-status',
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'deactivated' in data['message'] or 'activated' in data['message']
        assert 'is_active' in data
    
    def test_impersonate_user(self, client, auth_headers):
        """Test impersonating a user"""
        # Create a user to impersonate
        with client.application.app_context():
            # Retrieve the admin's organization
            admin_user = User.query.filter_by(email='test@example.com').first()
            
            target_user = User(
                email='target@example.com',
                first_name='Target',
                last_name='User',
                role='student',
                organization_id=admin_user.organization_id
            )
            target_user.set_password('TargetPassword123!')
            db.session.add(target_user)
            db.session.commit()
            target_user_id = target_user.id
        
        response = client.post(f'/api/admin/users/{target_user_id}/impersonate',
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Impersonation successful'
        assert 'user' in data
        assert 'tokens' in data
        assert data['user']['email'] == 'target@example.com'
    
    def test_forum_moderation(self, client, auth_headers):
        """Test the forum moderation tools"""
        response = client.get('/api/admin/forum/moderation', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'recent_topics' in data
        assert 'recent_replies' in data
        assert 'forum_stats' in data
        
        # Check the forum statistics
        forum_stats = data['forum_stats']
        assert 'total_topics' in forum_stats
        assert 'total_replies' in forum_stats
        assert 'active_categories' in forum_stats
    
    def test_analytics(self, client, auth_headers):
        """Test the admin analytics"""
        response = client.get('/api/admin/analytics?period=7', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'period_days' in data
        assert data['period_days'] == 7
        assert 'user_activity' in data
        assert 'module_completions' in data
        assert 'top_users' in data
        assert 'popular_modules' in data
    
    def test_system_health(self, client, auth_headers):
        """Test checking the system health"""
        response = client.get('/api/admin/system/health', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'system_health' in data
        assert 'table_counts' in data
        assert 'subscription_status' in data
        
        # Check the database status
        assert data['system_health']['database'] == 'healthy'
        
        # Check the table counters
        table_counts = data['table_counts']
        assert 'users' in table_counts
        assert 'modules' in table_counts
    
    def test_export_users(self, client, auth_headers):
        """Test exporting the users data"""
        response = client.get('/api/admin/export/users', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'exported_at' in data
        assert 'total_count' in data
        
        # Check that at least the admin user is exported
        assert data['total_count'] >= 1
        
        # Check the structure of the exported data
        if len(data['users']) > 0:
            user = data['users'][0]
            assert 'email' in user
            assert 'first_name' in user
            assert 'modules_completed' in user
            assert 'total_points' in user
    
    def test_organization_settings(self, client, auth_headers):
        """Test retrieving the organization settings"""
        response = client.get('/api/admin/settings', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'organization' in data
        assert 'features' in data
        assert 'limits' in data
        
        # Check the features
        features = data['features']
        assert 'forum_enabled' in features
        assert 'gamification_enabled' in features
        assert 'ai_features_enabled' in features
    
    def test_update_organization_settings(self, client, auth_headers):
        """Test updating the organization settings"""
        response = client.put('/api/admin/settings',
                             headers=auth_headers,
                             json={
                                 'name': 'Updated Organization Name',
                                 'domain': 'updated.example.com'
                             })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Settings updated successfully'
        assert data['organization']['name'] == 'Updated Organization Name'
    
    def test_student_cannot_access_admin(self, client, student_headers):
        """Test that a student cannot access the admin functions"""
        response = client.get('/api/admin/dashboard', headers=student_headers)
        
        assert response.status_code == 403
        data = response.get_json()
        assert 'Insufficient permissions' in data['error']
    
    def test_admin_search_users(self, client, auth_headers):
        """Test searching users"""
        response = client.get('/api/admin/users?search=test', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        
        # Check that the search works
        if len(data['users']) > 0:
            user = data['users'][0]
            search_term = 'test'
            assert (search_term.lower() in user['first_name'].lower() or 
                   search_term.lower() in user['last_name'].lower() or 
                   search_term.lower() in user['email'].lower())
    
    def test_admin_filter_users_by_role(self, client, auth_headers):
        """Test filtering users by role"""
        response = client.get('/api/admin/users?role=admin', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        
        # Check that all returned users are admins
        for user in data['users']:
            assert user['role'] == 'admin'

