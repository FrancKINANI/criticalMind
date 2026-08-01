import pytest

from src.main import create_app
from src.models import db
from src.models.user import User
from src.models.organization import Organization


@pytest.fixture
def client():
    """Client de test Flask — base SQLite en mémoire isolée par test.

    Chaque test crée sa propre application via la factory (TestingConfig :
    ``sqlite:///:memory:``, TESTING=True, WTF_CSRF_ENABLED=False), donc son
    propre engine et sa propre base en mémoire. Aucun état partagé entre les
    tests (le module-level ``app = create_app()`` de main.py, qui lie l'engine
    à la base de développement, n'est jamais utilisé par les tests).
    """
    application = create_app('testing')
    with application.test_client() as client:
        with application.app_context():
            yield client
            db.drop_all()


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
