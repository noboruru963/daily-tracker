import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.settings import UserSettings

settings_bp = Blueprint('settings', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def settings_page():
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        action = request.form.get('action', 'general')
        
        if action == 'username':
            new_username = request.form.get('new_username', '').strip()
            if not new_username:
                flash('Username cannot be empty.', 'error')
            elif len(new_username) < 3:
                flash('Username must be at least 3 characters.', 'error')
            elif new_username != current_user.username:
                from app.models.user import User
                if User.query.filter_by(username=new_username).first():
                    flash('Username already taken.', 'error')
                else:
                    current_user.username = new_username
                    db.session.commit()
                    flash('Username updated successfully!', 'success')
            return redirect(url_for('settings.settings_page'))
        
        elif action == 'profile_picture':
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file.filename != '' and allowed_file(file.filename):
                    upload_dir = os.path.join(current_app.static_folder, 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    current_user.profile_picture = url_for('static', filename=f'uploads/{filename}')
                    db.session.commit()
                    flash('Profile picture updated!', 'success')
                elif file.filename != '':
                    flash('Invalid file type. Use PNG, JPG, JPEG, or GIF.', 'error')
            return redirect(url_for('settings.settings_page'))
        
        else:
            settings.theme = request.form.get('theme', 'light')
            settings.primary_color = request.form.get('primary_color', '#10b981')
            settings.dashboard_layout = request.form.get('dashboard_layout', 'grid')
            settings.email_notifications = request.form.get('email_notifications') == 'on'
            settings.reminder_time = request.form.get('reminder_time', '')
            settings.default_habit_visibility = request.form.get('default_habit_visibility', 'private')
            
            habits_per_page = request.form.get('habits_per_page', '12')
            try:
                settings.habits_per_page = int(habits_per_page)
            except (ValueError, TypeError):
                settings.habits_per_page = 12
            
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('settings.settings_page'))
    
    return render_template('settings/index.html', settings=settings)

@settings_bp.route('/about')
@login_required
def about_page():
    return render_template('settings/about.html')
