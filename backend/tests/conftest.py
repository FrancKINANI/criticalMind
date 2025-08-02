import pytest
import tempfile
import os
from src.main import app
from src.models import db
from src.models.user import User
from src.models.organization import Organization

@pytest.fixture
def client():
    """Créer un client de test Flask"""
    # Créer un fichier de base de données temporaire
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{app.config['DATABASE']}"
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()
    
    os.close(db_fd)
    os.unlink(app.config['DATABASE'])

@pytest.fixture
def auth_headers(client):
    """Créer un utilisateur de test et retourner les headers d'authentification"""
    # Créer une organisation
    org = Organization(name="Test Organization")
    db.session.add(org)
    db.session.flush()
    
    # Créer un utilisateur admin
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
        organization_id=org.id
    )
    user.set_password("TestPassword123!")
    db.session.add(user)
    db.session.commit()
    
    # Se connecter
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'TestPassword123!'
    })
    
    data = response.get_json()
    token = data['tokens']['access_token']
    
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def student_headers(client):
    """Créer un utilisateur étudiant de test"""
    # Créer une organisation
    org = Organization(name="Student Test Organization")
    db.session.add(org)
    db.session.flush()
    
    # Créer un utilisateur étudiant
    user = User(
        email="student@example.com",
        first_name="Student",
        last_name="Test",
        role="student",
        organization_id=org.id
    )
    user.set_password("StudentPassword123!")
    db.session.add(user)
    db.session.commit()
    
    # Se connecter
    response = client.post('/api/auth/login', json={
        'email': 'student@example.com',
        'password': 'StudentPassword123!'
    })
    
    data = response.get_json()
    token = data['tokens']['access_token']
    
    return {'Authorization': f'Bearer {token}'}

