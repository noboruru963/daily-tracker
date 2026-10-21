from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name=None):
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///daily.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    from app.routes.auth import auth_bp
    from app.routes.habits import habits_bp
    from app.routes.tracking import tracking_bp
    from app.routes.community import community_bp
    from app.routes.settings import settings_bp
    from app.routes.calories import calories_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(habits_bp, url_prefix='/habits')
    app.register_blueprint(tracking_bp, url_prefix='/tracking')
    app.register_blueprint(community_bp, url_prefix='/community')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(calories_bp, url_prefix='/calories')
    
    with app.app_context():
        db.create_all()
        
        # Lightweight migration: add sort_order column to records table for existing DBs
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'records' in inspector.get_table_names():
                record_cols = [col['name'] for col in inspector.get_columns('records')]
                if 'sort_order' not in record_cols:
                    db.session.execute(text('ALTER TABLE records ADD COLUMN sort_order INTEGER DEFAULT 0'))
                    db.session.commit()
                if 'record_icon' not in record_cols:
                    db.session.execute(text("ALTER TABLE records ADD COLUMN record_icon VARCHAR(50) DEFAULT ''"))
                    db.session.commit()
        except Exception:
            app.logger.warning('Could not run records migration.', exc_info=True)
        
        # Seed placeholder public community habits
        try:
            from app.models.habit import Habit
            from app.models.user import User
            system_user = User.query.filter_by(username='dailyteam').first()
            if not system_user:
                system_user = User(
                    username='dailyteam',
                    email='team@dailyapp.com',
                )
                system_user.set_password('system-only-not-for-login')
                db.session.add(system_user)
                db.session.commit()

                community_habits = [
                    {
                        'name': 'Read 30 Minutes Daily',
                        'description': 'Spend at least 30 minutes reading a book every day. Build your knowledge and vocabulary.',
                        'icon': 'book',
                        'theme_color': '#0ea5e9',
                        'visual_model_type': 'graph',
                        'settings': {'graph_type': 'line', 'time_range': 30}
                    },
                    {
                        'name': 'Drink 8 Glasses of Water',
                        'description': 'Stay hydrated throughout the day by drinking at least 8 glasses of water.',
                        'icon': 'droplet',
                        'theme_color': '#06b6d4',
                        'visual_model_type': 'percentage',
                        'settings': {'min_value': 0, 'max_value': 8, 'current_value': 0, 'unit': 'glasses'}
                    },
                    {
                        'name': 'Morning Meditation',
                        'description': 'Practice 10 minutes of mindfulness meditation every morning.',
                        'icon': 'moon',
                        'theme_color': '#8b5cf6',
                        'visual_model_type': 'graph',
                        'settings': {'graph_type': 'line', 'time_range': 30}
                    },
                    {
                        'name': 'Workout 3x per Week',
                        'description': 'Hit the gym or exercise at least 3 times per week.',
                        'icon': 'bicycle',
                        'theme_color': '#ef4444',
                        'visual_model_type': 'calendar',
                        'settings': {'schedule': ['monday', 'wednesday', 'friday'], 'reminder_time': '17:00', 'times_per_day': 1}
                    },
                    {
                        'name': 'Learn a New Skill',
                        'description': 'Dedicate 20 minutes each day to learning something new.',
                        'icon': 'laptop',
                        'theme_color': '#a855f7',
                        'visual_model_type': 'graph',
                        'settings': {'graph_type': 'line', 'time_range': 30}
                    },
                    {
                        'name': 'Practice Guitar',
                        'description': 'Practice playing guitar for 30 minutes daily.',
                        'icon': 'music-note',
                        'theme_color': '#ec4899',
                        'visual_model_type': 'graph',
                        'settings': {'graph_type': 'line', 'time_range': 30}
                    },
                ]

                for h in community_habits:
                    habit = Habit(
                        user_id=system_user.id,
                        name=h['name'],
                        description=h['description'],
                        visual_model_type=h['visual_model_type'],
                        visual_settings={'theme_color': h['theme_color'], 'icon': h['icon'], **h['settings']},
                        is_public=True
                    )
                    db.session.add(habit)
                db.session.commit()
        except Exception:
            app.logger.warning('Could not seed community habits.', exc_info=True)
        
    return app
