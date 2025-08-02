import pytest
import json
from src.models import db
from src.models.learning import LearningModule, Exercise, UserProgress
from src.models.user import User

class TestLearning:
    """Tests pour le système d'apprentissage"""
    
    def test_create_learning_module(self, client, auth_headers):
        """Test de création d'un module d'apprentissage"""
        response = client.post('/api/learning/modules', 
                              headers=auth_headers,
                              json={
                                  'title': 'Test Module',
                                  'description': 'A test learning module',
                                  'content': {
                                      'sections': [
                                          {'title': 'Introduction', 'content': 'Welcome to the module'}
                                      ]
                                  },
                                  'difficulty_level': 2,
                                  'estimated_duration': 30
                              })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'Learning module created successfully'
        assert data['module']['title'] == 'Test Module'
        assert data['module']['difficulty_level'] == 2
    
    def test_get_learning_modules(self, client, auth_headers):
        """Test de récupération des modules d'apprentissage"""
        # Créer d'abord un module
        client.post('/api/learning/modules', 
                   headers=auth_headers,
                   json={
                       'title': 'Test Module',
                       'content': {'sections': []},
                       'difficulty_level': 1
                   })
        
        response = client.get('/api/learning/modules', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'modules' in data
        assert len(data['modules']) > 0
        assert 'pagination' in data
    
    def test_get_learning_module_detail(self, client, auth_headers):
        """Test de récupération des détails d'un module"""
        # Créer un module
        create_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Detailed Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = create_response.get_json()['module']['id']
        
        response = client.get(f'/api/learning/modules/{module_id}', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'module' in data
        assert data['module']['title'] == 'Detailed Module'
        assert 'user_progress' in data['module']
        assert 'exercises' in data['module']
    
    def test_create_exercise(self, client, auth_headers):
        """Test de création d'un exercice"""
        # Créer d'abord un module
        module_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Module with Exercise',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = module_response.get_json()['module']['id']
        
        response = client.post(f'/api/learning/modules/{module_id}/exercises',
                              headers=auth_headers,
                              json={
                                  'title': 'Test Exercise',
                                  'question': 'What is 2 + 2?',
                                  'exercise_type': 'multiple_choice',
                                  'options': ['2', '3', '4', '5'],
                                  'correct_answer': '4',
                                  'explanation': 'Basic addition',
                                  'points': 10
                              })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'Exercise created successfully'
        assert data['exercise']['title'] == 'Test Exercise'
        assert data['exercise']['exercise_type'] == 'multiple_choice'
    
    def test_submit_exercise_response_correct(self, client, auth_headers):
        """Test de soumission d'une réponse correcte"""
        # Créer module et exercice
        module_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Test Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = module_response.get_json()['module']['id']
        
        exercise_response = client.post(f'/api/learning/modules/{module_id}/exercises',
                                       headers=auth_headers,
                                       json={
                                           'title': 'Math Exercise',
                                           'question': 'What is 5 + 3?',
                                           'exercise_type': 'multiple_choice',
                                           'correct_answer': '8',
                                           'points': 10
                                       })
        
        exercise_id = exercise_response.get_json()['exercise']['id']
        
        # Soumettre une réponse correcte
        response = client.post(f'/api/learning/exercises/{exercise_id}/submit',
                              headers=auth_headers,
                              json={'response': '8'})
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'Response submitted successfully'
        assert data['is_correct'] == True
        assert data['points_earned'] == 10
    
    def test_submit_exercise_response_incorrect(self, client, auth_headers):
        """Test de soumission d'une réponse incorrecte"""
        # Créer module et exercice
        module_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Test Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = module_response.get_json()['module']['id']
        
        exercise_response = client.post(f'/api/learning/modules/{module_id}/exercises',
                                       headers=auth_headers,
                                       json={
                                           'title': 'Math Exercise',
                                           'question': 'What is 5 + 3?',
                                           'exercise_type': 'multiple_choice',
                                           'correct_answer': '8',
                                           'points': 10
                                       })
        
        exercise_id = exercise_response.get_json()['exercise']['id']
        
        # Soumettre une réponse incorrecte
        response = client.post(f'/api/learning/exercises/{exercise_id}/submit',
                              headers=auth_headers,
                              json={'response': '7'})
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['is_correct'] == False
        assert data['points_earned'] == 0
    
    def test_get_user_progress(self, client, auth_headers):
        """Test de récupération de la progression utilisateur"""
        response = client.get('/api/learning/progress', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'progress' in data
        assert 'pagination' in data
    
    def test_duplicate_exercise_response(self, client, auth_headers):
        """Test de soumission de réponse en double"""
        # Créer module et exercice
        module_response = client.post('/api/learning/modules', 
                                     headers=auth_headers,
                                     json={
                                         'title': 'Test Module',
                                         'content': {'sections': []},
                                         'difficulty_level': 1
                                     })
        
        module_id = module_response.get_json()['module']['id']
        
        exercise_response = client.post(f'/api/learning/modules/{module_id}/exercises',
                                       headers=auth_headers,
                                       json={
                                           'title': 'Math Exercise',
                                           'question': 'What is 2 + 2?',
                                           'exercise_type': 'multiple_choice',
                                           'correct_answer': '4',
                                           'points': 10
                                       })
        
        exercise_id = exercise_response.get_json()['exercise']['id']
        
        # Première soumission
        client.post(f'/api/learning/exercises/{exercise_id}/submit',
                   headers=auth_headers,
                   json={'response': '4'})
        
        # Tentative de deuxième soumission
        response = client.post(f'/api/learning/exercises/{exercise_id}/submit',
                              headers=auth_headers,
                              json={'response': '4'})
        
        assert response.status_code == 409
        data = response.get_json()
        assert 'Response already submitted' in data['error']
    
    def test_student_cannot_create_module(self, client, student_headers):
        """Test qu'un étudiant ne peut pas créer de module"""
        response = client.post('/api/learning/modules', 
                              headers=student_headers,
                              json={
                                  'title': 'Unauthorized Module',
                                  'content': {'sections': []},
                                  'difficulty_level': 1
                              })
        
        assert response.status_code == 403
        data = response.get_json()
        assert 'Insufficient permissions' in data['error']

