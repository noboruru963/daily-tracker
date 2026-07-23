import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///daily.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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