import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app import create_app, db
from app.models.settings import UserSettings
from app.models.user import User
from app.routes.auth import (
    FirebaseAuthError,
    send_firebase_password_reset,
    verify_firebase_id_token,
)


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'route-test-secret'
    FIREBASE_API_KEY = 'test-firebase-api-key'
    FIREBASE_WEB_CONFIG = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': 'daily-tracker-c942a.firebaseapp.com',
        'projectId': 'daily-tracker-c942a',
    }


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_redirects_to_login(client):
    response = client.get('/')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_login_page_uses_firebase_email_auth(client):
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'id="loginForm"' in response.data
    assert b'daily-tracker-c942a.firebaseapp.com' in response.data
    assert b'/auth/forgot-password' in response.data


def test_register_page_uses_firebase_auth(client):
    response = client.get('/auth/register')
    assert response.status_code == 200
    assert b'id="registerForm"' in response.data


def test_forgot_password_page_uses_firebase_auth(client):
    response = client.get('/auth/forgot-password')
    assert response.status_code == 200
    assert b'method="POST"' in response.data


def test_forgot_password_posts_reset_request_to_firebase(client, app, monkeypatch):
    sent = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({'email': 'test@example.com'}).encode('utf-8')

    def fake_urlopen(request, timeout):
        sent['url'] = request.full_url
        sent['body'] = json.loads(request.data.decode('utf-8'))
        sent['referer'] = request.get_header('Referer')
        sent['timeout'] = timeout
        return FakeResponse()

    monkeypatch.setattr('app.routes.auth.urlopen', fake_urlopen)
    response = client.post(
        '/auth/forgot-password',
        data={'email': 'test@example.com'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Firebase accepted the request' in response.data
    assert sent['body'] == {
        'requestType': 'PASSWORD_RESET',
        'email': 'test@example.com',
    }
    assert 'test-firebase-api-key' in sent['url']
    assert sent['referer'] == 'http://localhost/'
    assert sent['timeout'] == 10


def test_forgot_password_surfaces_firebase_api_key_error(client, monkeypatch):
    def rejected_request(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            'Bad Request',
            {},
            BytesIO(json.dumps({
                'error': {'message': 'API_KEY_INVALID'}
            }).encode('utf-8')),
        )

    monkeypatch.setattr('app.routes.auth.urlopen', rejected_request)
    response = client.post(
        '/auth/forgot-password',
        data={'email': 'test@example.com'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Firebase rejected FIREBASE_API_KEY' in response.data

def test_user_registration_page_uses_firebase_auth(client):
    response = client.get('/auth/register')
    assert response.status_code == 200
    assert b'id="registerForm"' in response.data
    assert b'id="toggleConfirmPassword"' in response.data

def test_firebase_session_login_links_existing_python_profile(client, app, monkeypatch):
    with app.app_context():
        user = User(username='existinguser', email='test@example.com')
        user.set_password('old-python-password')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    monkeypatch.setattr('app.routes.auth.verify_firebase_id_token', lambda token: {
        'localId': 'firebase-user-2',
        'email': 'TEST@example.com',
        'emailVerified': True,
        'displayName': 'new-name',
    })
    response = client.post('/auth/session-login', json={'idToken': 'test-token'})
    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.email == 'TEST@example.com'
        assert user.username == 'existinguser'


def test_firebase_session_login_requires_verified_email(client, monkeypatch):
    monkeypatch.setattr('app.routes.auth.verify_firebase_id_token', lambda token: {
        'localId': 'firebase-user-3',
        'email': 'test@example.com',
        'emailVerified': False,
    })

    response = client.post('/auth/session-login', json={'idToken': 'test-token'})
    assert response.status_code == 403


def test_firebase_session_login_requires_id_token(client):
    response = client.post('/auth/session-login', json={})
    assert response.status_code == 400


def test_firebase_session_login_reports_missing_api_key(client, app, monkeypatch):
    app.config['FIREBASE_API_KEY'] = ''
    monkeypatch.setattr('app.routes.auth.verify_firebase_id_token', verify_firebase_id_token)

    response = client.post('/auth/session-login', json={'idToken': 'test-token'})
    assert response.status_code == 503
    assert 'FIREBASE_API_KEY' in response.json['error']


def test_verify_firebase_id_token_calls_identity_toolkit(app, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({'users': [{'localId': 'user-id'}]}).encode('utf-8')

    captured = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['body'] = json.loads(request.data.decode('utf-8'))
        captured['timeout'] = timeout
        captured['referer'] = request.get_header('Referer')
        return FakeResponse()

    monkeypatch.setattr('app.routes.auth.urlopen', fake_urlopen)
    with app.test_request_context('/'):
        result = verify_firebase_id_token('firebase-id-token')

    assert result['localId'] == 'user-id'
    assert 'accounts:lookup' in captured['url']
    assert 'test-firebase-api-key' in captured['url']
    assert captured['body'] == {'idToken': 'firebase-id-token'}
    assert captured['timeout'] == 10
    assert captured['referer'] == 'http://localhost/'


def test_dashboard_access_requires_login(client):
    response = client.get('/habits/dashboard')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
