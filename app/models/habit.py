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
    
    def _record_days(self, today=None):
        """Unique calendar days with at least one record (future days ignored)."""
        today = today or date.today()
        days = {
            r.date.date() if isinstance(r.date, datetime) else r.date
            for r in self.records
            if r.date is not None
        }
        return {d for d in days if d <= today}

    def is_done_today(self, today=None):
        today = today or date.today()
        return today in self._record_days(today)

    def get_streak(self, today=None):
        """Current streak: consecutive days with at least one record.

        Each new day with a record adds 1 (several records on the same day
        count once). A streak stays alive until the end of the day after the
        last record, so logging yesterday but not yet today still shows it.
        """
        today = today or date.today()
        days = self._record_days(today)

        if today in days:
            check_date = today
        elif (today - timedelta(days=1)) in days:
            check_date = today - timedelta(days=1)
        else:
            return 0

        streak = 0
        while check_date in days:
            streak += 1
            check_date -= timedelta(days=1)
        return streak

    def get_best_streak(self, today=None):
        """Longest run of consecutive days ever achieved."""
        days = sorted(self._record_days(today))
        if not days:
            return 0

        best = 1
        current = 1
        for i in range(1, len(days)):
            if days[i] - days[i - 1] == timedelta(days=1):
                current += 1
                best = max(best, current)
            else:
                current = 1
        return best
    
    def get_total_days(self, today=None):
        """Get total number of unique days with records."""
        return len(self._record_days(today))
