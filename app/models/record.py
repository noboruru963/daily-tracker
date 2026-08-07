from datetime import datetime
from app import db

class Record(db.Model):
    __tablename__ = 'records'
    
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habits.id'), nullable=False)
    numerical_value = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Progression model fields
    step_number = db.Column(db.Integer)
    step_name = db.Column(db.String(100))
    
    # Calendar model fields
    time_spent = db.Column(db.Float)
    activity_type = db.Column(db.String(100), default='')
    
    # Percentage model fields
    target_value = db.Column(db.Float)
    
    # Manual ordering (used when the user drags records into a custom order)
    sort_order = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Record {self.id} for Habit {self.habit_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'habit_id': self.habit_id,
            'numerical_value': self.numerical_value,
            'description': self.description,
            'date': self.date.isoformat(),
            'step_number': self.step_number,
            'step_name': self.step_name,
            'time_spent': self.time_spent,
            'activity_type': self.activity_type or '',
            'target_value': self.target_value
        }
