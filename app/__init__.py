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
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(habits_bp, url_prefix='/habits')
    app.register_blueprint(tracking_bp, url_prefix='/tracking')
    app.register_blueprint(community_bp, url_prefix='/community')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    with app.app_context():
        db.create_all()
    
    return app
