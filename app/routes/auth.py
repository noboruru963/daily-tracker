import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.settings import UserSettings
from app.models.user import User

auth_bp = Blueprint('auth', __name__)
FIREBASE_LOOKUP_URL = 'https://identitytoolkit.googleapis.com/v1/accounts:lookup'
FIREBASE_SEND_OOB_URL = 'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode'


class FirebaseAuthError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def verify_firebase_id_token(id_token):
    api_key = current_app.config.get('FIREBASE_API_KEY')
    if not api_key:
        raise FirebaseAuthError(
            'Set FIREBASE_API_KEY to the apiKey from Firebase Console → Project settings → Your apps.',
            503,
        )

    body = json.dumps({'idToken': id_token}).encode('utf-8')
    endpoint = f'{FIREBASE_LOOKUP_URL}?{urlencode({"key": api_key})}'
    firebase_request = Request(
        endpoint,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Referer': request.host_url,
        },
        method='POST',
    )
    try:
        with urlopen(firebase_request, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        try:
            error_body = json.loads(error.read().decode('utf-8'))
            firebase_message = error_body.get('error', {}).get('message', '')
        except (UnicodeDecodeError, json.JSONDecodeError):
            firebase_message = ''

        if firebase_message == 'API_KEY_INVALID':
            raise FirebaseAuthError(
                'Firebase rejected FIREBASE_API_KEY. Copy the exact apiKey from your Firebase web app config.',
                503,
            ) from error
        if error.code in (400, 401):
            raise FirebaseAuthError('Your Firebase sign-in expired. Please sign in again.', 401) from error
        current_app.logger.error('Firebase token verification failed with HTTP %s.', error.code)
        raise FirebaseAuthError('Firebase authentication is temporarily unavailable.', 503) from error
    except (URLError, TimeoutError, OSError) as error:
        current_app.logger.exception('Could not reach Firebase to verify the sign-in token.')
        raise FirebaseAuthError('Could not connect to Firebase. Check your internet connection.', 503) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        current_app.logger.exception('Firebase returned an invalid token-verification response.')
        raise FirebaseAuthError('Firebase returned an invalid response. Please try again.', 503) from error

    users = result.get('users', [])
    if not users:
        raise FirebaseAuthError('Your Firebase sign-in expired. Please sign in again.', 401)
    return users[0]


def send_firebase_password_reset(email):
    api_key = current_app.config.get('FIREBASE_API_KEY')
    if not api_key:
        raise FirebaseAuthError(
            'Firebase API key is not configured. Set FIREBASE_API_KEY in .env and restart Flask.',
            503,
        )

    body = json.dumps({
        'requestType': 'PASSWORD_RESET',
        'email': email,
    }).encode('utf-8')
    endpoint = f'{FIREBASE_SEND_OOB_URL}?{urlencode({"key": api_key})}'
    firebase_request = Request(
        endpoint,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Referer': request.host_url,
        },
        method='POST',
    )
    try:
        with urlopen(firebase_request, timeout=10) as response:
            json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        try:
            error_body = json.loads(error.read().decode('utf-8'))
            firebase_message = error_body.get('error', {}).get('message', '')
        except (UnicodeDecodeError, json.JSONDecodeError):
            firebase_message = ''

        if firebase_message == 'API_KEY_INVALID':
            raise FirebaseAuthError(
                'Firebase rejected FIREBASE_API_KEY. Copy the exact apiKey from Firebase Project settings → Your apps.',
                503,
            ) from error
        if firebase_message == 'OPERATION_NOT_ALLOWED':
            raise FirebaseAuthError(
                'Firebase password reset is disabled. Enable Email/Password in Firebase Authentication.',
                503,
            ) from error
        if firebase_message == 'TOO_MANY_ATTEMPTS_TRY_LATER':
            raise FirebaseAuthError(
                'Firebase temporarily blocked password-reset requests. Wait and try again later.',
                429,
            ) from error
        if firebase_message == 'INVALID_EMAIL':
            raise FirebaseAuthError('Enter a valid email address.', 400) from error
        if firebase_message in ('EMAIL_NOT_FOUND', 'USER_NOT_FOUND'):
            current_app.logger.info('Firebase did not find an account for a password-reset request.')
            return

        current_app.logger.error(
            'Firebase password-reset request failed with HTTP %s (%s).',
            error.code,
            firebase_message or 'unknown Firebase error',
        )
        raise FirebaseAuthError(
            'Firebase could not send the password-reset email. Check the Flask terminal for details.',
            503,
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        current_app.logger.exception('Could not connect to Firebase for a password-reset request.')
        raise FirebaseAuthError(
            'Could not connect to Firebase. Check your internet connection and try again.',
            503,
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        current_app.logger.exception('Firebase returned an invalid password-reset response.')
        raise FirebaseAuthError(
            'Firebase returned an invalid response. Please try again.',
            503,
        ) from error


def _unique_username(display_name, email, firebase_uid):
    base = (display_name or email.split('@', 1)[0]).strip()[:80] or 'user'
    if not User.query.filter_by(username=base).first():
        return base

    suffix = firebase_uid[-8:]
    username = f'{base[:70]}-{suffix}'
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f'{base[:66]}-{suffix}-{counter}'
        counter += 1
    return username


@auth_bp.route('/register', methods=['GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('habits.dashboard'))
    return render_template('auth/register.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Enter the email address for your Firebase account.', 'error')
            return redirect(url_for('auth.forgot_password'))

        try:
            send_firebase_password_reset(email)
        except FirebaseAuthError as error:
            current_app.logger.error('Firebase password-reset request failed: %s', error)
            flash(str(error), 'error')
            return redirect(url_for('auth.forgot_password'))

        flash(
            'Firebase accepted the request. If this email belongs to a Firebase Authentication account, '
            'a reset message should arrive. Check Inbox, Spam, and Promotions.',
            'success',
        )
        return redirect(url_for('auth.forgot_password'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('habits.dashboard'))
    return render_template('auth/login.html')


@auth_bp.route('/session-login', methods=['POST'])
def firebase_session_login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='A Firebase ID token is required.'), 400
    id_token = payload.get('idToken')
    if not isinstance(id_token, str) or not id_token or len(id_token) > 8192:
        return jsonify(error='A Firebase ID token is required.'), 400

    try:
        firebase_user = verify_firebase_id_token(id_token)
    except FirebaseAuthError as error:
        if error.status_code >= 500:
            current_app.logger.error('Firebase sign-in verification failed: %s', error)
        return jsonify(error=str(error)), error.status_code

    firebase_uid = firebase_user.get('localId')
    email = firebase_user.get('email')
    if not isinstance(firebase_uid, str) or not firebase_uid or not isinstance(email, str) or not email:
        return jsonify(error='Firebase did not return a valid user profile.'), 401
    if firebase_user.get('emailVerified') is not True:
        return jsonify(error='Please verify your email address before signing in.'), 403
    if firebase_user.get('disabled') is True:
        return jsonify(error='This Firebase account is disabled.'), 403

    user = User.query.filter(func.lower(User.email) == email.lower()).first()
    if user is None:
        display_name = firebase_user.get('displayName')
        username = _unique_username(
            display_name if isinstance(display_name, str) else '',
            email,
            firebase_uid,
        )
        user = User(username=username, email=email)
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.add(UserSettings(user=user))
    elif user.email != email:
        user.email = email

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Could not create or link the local user profile.')
        return jsonify(error='Could not create your profile. Please contact support.'), 409

    login_user(user, remember=payload.get('remember') is True)
    return jsonify(redirect=url_for('habits.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
