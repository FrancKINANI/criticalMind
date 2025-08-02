import pytest
import json
from src.models import db
from src.models.user import User
from src.models.learning import LearningModule

class TestAdmin:
    """Tests pour le panneau d'administration"""
    
    def test_admin_dashboard(self, client, auth_headers):
        """Test du tableau de bord administrateur"""
        response = client.get('/api/admin/dashboard', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'stats' in data
        assert 'popular_modules' in data
        assert 'recent_activity' in data
        
        # Vérifier les statistiques
        stats = data['stats']
        assert 'total_users' in stats
        assert 'active_users' in stats
        assert 'total_modules' in stats
        assert 'avg_progress' in stats
    
    def test_admin_get_all_users(self, client, auth_headers):
        """Test de récupération de tous les utilisateurs"""
        response = client.get('/api/admin/users', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'pagination' in data
        
        # Vérifier qu'au moins l'utilisateur admin existe
        assert len(data['users']) >= 1
        
        # Vérifier les statistiques utilisateur
        user = data['users'][0]
        assert 'stats' in user
        assert 'modules_completed' in user['stats']
        assert 'total_points' in user['stats']
    
    def test_admin_get_all_modules(self, client, auth_headers):
        """Test de récupération de tous les modules avec statistiques"""
        # Créer d'abord un module
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
        
        # Vérifier les statistiques du module
        if len(data['modules']) > 0:
            module = data['modules'][0]
            assert 'stats' in module
            assert 'total_enrollments' in module['stats']
            assert 'completion_rate' in module['stats']
    
    def test_toggle_module_status(self, client, auth_headers):
        """Test d'activation/désactivation d'un module"""
        # Créer un module
        create_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Toggle Test Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = create_response.get_json()['module']['id']
        
        # Désactiver le module
        response = client.post(f'/api/admin/modules/{module_id}/toggle-status',
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'deactivated' in data['message'] or 'activated' in data['message']
        assert 'is_active' in data
    
    def test_impersonate_user(self, client, auth_headers):
        """Test d'impersonation d'un utilisateur"""
        # Créer un utilisateur à impersonner
        with client.application.app_context():
            # Récupérer l'organisation de l'admin
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
        """Test des outils de modération du forum"""
        response = client.get('/api/admin/forum/moderation', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'recent_topics' in data
        assert 'recent_replies' in data
        assert 'forum_stats' in data
        
        # Vérifier les statistiques du forum
        forum_stats = data['forum_stats']
        assert 'total_topics' in forum_stats
        assert 'total_replies' in forum_stats
        assert 'active_categories' in forum_stats
    
    def test_analytics(self, client, auth_headers):
        """Test des analyses administrateur"""
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
        """Test de vérification de l'état du système"""
        response = client.get('/api/admin/system/health', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'system_health' in data
        assert 'table_counts' in data
        assert 'subscription_status' in data
        
        # Vérifier l'état de la base de données
        assert data['system_health']['database'] == 'healthy'
        
        # Vérifier les compteurs de tables
        table_counts = data['table_counts']
        assert 'users' in table_counts
        assert 'modules' in table_counts
    
    def test_export_users(self, client, auth_headers):
        """Test d'export des données utilisateurs"""
        response = client.get('/api/admin/export/users', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'exported_at' in data
        assert 'total_count' in data
        
        # Vérifier qu'au moins l'utilisateur admin est exporté
        assert data['total_count'] >= 1
        
        # Vérifier la structure des données exportées
        if len(data['users']) > 0:
            user = data['users'][0]
            assert 'email' in user
            assert 'first_name' in user
            assert 'modules_completed' in user
            assert 'total_points' in user
    
    def test_organization_settings(self, client, auth_headers):
        """Test de récupération des paramètres d'organisation"""
        response = client.get('/api/admin/settings', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'organization' in data
        assert 'features' in data
        assert 'limits' in data
        
        # Vérifier les fonctionnalités
        features = data['features']
        assert 'forum_enabled' in features
        assert 'gamification_enabled' in features
        assert 'ai_features_enabled' in features
    
    def test_update_organization_settings(self, client, auth_headers):
        """Test de mise à jour des paramètres d'organisation"""
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
        """Test qu'un étudiant ne peut pas accéder aux fonctions admin"""
        response = client.get('/api/admin/dashboard', headers=student_headers)
        
        assert response.status_code == 403
        data = response.get_json()
        assert 'Insufficient permissions' in data['error']
    
    def test_admin_search_users(self, client, auth_headers):
        """Test de recherche d'utilisateurs"""
        response = client.get('/api/admin/users?search=test', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        
        # Vérifier que la recherche fonctionne
        if len(data['users']) > 0:
            user = data['users'][0]
            search_term = 'test'
            assert (search_term.lower() in user['first_name'].lower() or 
                   search_term.lower() in user['last_name'].lower() or 
                   search_term.lower() in user['email'].lower())
    
    def test_admin_filter_users_by_role(self, client, auth_headers):
        """Test de filtrage des utilisateurs par rôle"""
        response = client.get('/api/admin/users?role=admin', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        
        # Vérifier que tous les utilisateurs retournés sont des admins
        for user in data['users']:
            assert user['role'] == 'admin'

