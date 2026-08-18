from datetime import datetime, date, timedelta
from app import db

class Habit(db.Model):
    __tablename__ = 'habits'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    visual_model_type = db.Column(db.String(20), nullable=False, default='graph')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    
    # Visual model settings (stored as JSON)
    visual_settings = db.Column(db.JSON, default=dict)
    
    # Relationships
    records = db.relationship('Record', backref='habit', lazy=True, cascade='all, delete-orphan')
    community_posts = db.relationship('CommunityPost', backref='habit', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Habit {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'visual_model_type': self.visual_model_type,
            'visual_settings': self.visual_settings,
            'created_at': self.created_at.isoformat(),
            'is_public': self.is_public,
            'is_pinned': self.is_pinned
        }
    
    def get_streak(self):
        """Calculate current streak (consecutive days with at least one record)."""
        if not self.records:
            return 0
        
        record_dates = set()
        for r in self.records:
            record_dates.add(r.date.date() if isinstance(r.date, datetime) else r.date)
        
        today = date.today()
        streak = 0
        check_date = today
        
        if today not in record_dates:
            check_date = today - timedelta(days=1)
        
        while check_date in record_dates:
            streak += 1
            check_date -= timedelta(days=1)
        
        return streak
    
    def get_best_streak(self):
        """Calculate the best (longest) streak ever achieved."""
        if not self.records:
            return 0
        
        record_dates = sorted(set(
            r.date.date() if isinstance(r.date, datetime) else r.date
            for r in self.records
        ))
        
        best = 1
        current = 1
        for i in range(1, len(record_dates)):
            if record_dates[i] - record_dates[i - 1] == timedelta(days=1):
                current += 1
                best = max(best, current)
            else:
                current = 1
        
        return best
    
    def get_total_days(self):
        """Get total number of unique days with records."""
        if not self.records:
            return 0
        return len(set(
            r.date.date() if isinstance(r.date, datetime) else r.date
            for r in self.records
        ))
