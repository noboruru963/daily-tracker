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



def validate_password(password):
    if not isinstance(password, str) or not password:
        return False, 'Password is required.'
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not any(character.isupper() for character in password):
        return False, 'Password must contain at least one capital letter.'
    if not any(not character.isalnum() and not character.isspace() for character in password):
        return False, 'Password must contain at least one symbol.'
    return True, ''


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('habits.dashboard'))
    return render_template('auth/register.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        form_data = {'username': username, 'email': email}
        
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        email_domain = email.split('@')[-1].lower() if '@' in email else ''
        if email_domain not in ALLOWED_EMAIL_DOMAINS:
            flash('Please use a valid email address (e.g. Gmail, Yahoo, Outlook, etc.).', 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        password_is_valid, password_error = validate_password(password)
        if not password_is_valid:
            flash(password_error, 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html', form_data=form_data)
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        
        settings = UserSettings(user=user)
        db.session.add(settings)
        
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form_data={})

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
