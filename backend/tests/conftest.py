import pytest

from src.main import create_app
from src.models import db
from src.models.user import User
from src.models.organization import Organization


@pytest.fixture
def client():
    """Flask test client — in-memory SQLite database isolated per test.

    Each test creates its own application via the factory (TestingConfig:
    ``sqlite:///:memory:``, TESTING=True, WTF_CSRF_ENABLED=False), therefore
    its own engine and in-memory database. No state is shared between tests
    (the module-level ``app = create_app()`` of main.py, which binds the engine
    to the development database, is never used by the tests).
    """
    application = create_app('testing')
    with application.test_client() as client:
        with application.app_context():
            yield client
            db.drop_all()


@pytest.fixture
def auth_headers(client):
    """Create a test user and return the authentication headers"""
    # Create an organization
    org = Organization(name="Test Organization")
    db.session.add(org)
    db.session.flush()

    # Create an admin user
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

    # Log in
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'TestPassword123!'
    })

    data = response.get_json()
    token = data['tokens']['access_token']

    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def student_headers(client):
    """Create a test student user"""
    # Create an organization
    org = Organization(name="Student Test Organization")
    db.session.add(org)
    db.session.flush()

    # Create a student user
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

    # Log in
    response = client.post('/api/auth/login', json={
        'email': 'student@example.com',
        'password': 'StudentPassword123!'
    })

    data = response.get_json()
    token = data['tokens']['access_token']

    return {'Authorization': f'Bearer {token}'}
