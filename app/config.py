import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///daily.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', '')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'daily-tracker-c942a')
    FIREBASE_WEB_CONFIG = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': os.environ.get(
            'FIREBASE_AUTH_DOMAIN',
            'daily-tracker-c942a.firebaseapp.com',
        ),
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': os.environ.get(
            'FIREBASE_STORAGE_BUCKET',
            'daily-tracker-c942a.firebasestorage.app',
        ),
        'messagingSenderId': os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '26363898390'),
        'appId': os.environ.get(
            'FIREBASE_APP_ID',
            '1:26363898390:web:9cef60b73f4608c4172337',
        ),
    }
    
    # Visual model settings
    VISUAL_MODELS = {
        'graph': {
            'name': 'Graph',
            'description': 'Track trends over time',
            'icon': 'graph-up'
        },
        'progression': {
            'name': 'Progression',
            'description': 'Step-by-step progress tracking',
            'icon': 'layers'
        },
        'calendar': {
            'name': 'Calendar',
            'description': 'Time-based habit tracking',
            'icon': 'calendar'
        },
        'percentage': {
            'name': 'Percentage',
            'description': 'Progress towards a goal',
            'icon': 'percent'
        }
    }
    
    # Customization options
    THEMES = {
        'light': 'Light Theme',
        'dark': 'Dark Theme',
        'blue': 'Ocean Blue',
        'green': 'Forest Green',
        'purple': 'Royal Purple'
    }