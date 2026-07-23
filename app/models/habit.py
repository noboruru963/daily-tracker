from datetime import datetime
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
