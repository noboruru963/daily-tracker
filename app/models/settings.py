from app import db

class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Theme and appearance
    theme = db.Column(db.String(20), default='light')
    primary_color = db.Column(db.String(7), default='#10b981')
    
    # Dashboard settings
    dashboard_layout = db.Column(db.String(20), default='grid')
    habits_per_page = db.Column(db.Integer, default=12)
    
    # Notification settings
    email_notifications = db.Column(db.Boolean, default=True)
    reminder_time = db.Column(db.String(5))
    
    # Privacy settings
    default_habit_visibility = db.Column(db.String(10), default='private')
    
    def __repr__(self):
        return f'<UserSettings for User {self.user_id}>'
