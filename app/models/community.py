from datetime import datetime
from app import db

class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey('habits.id'), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='community_posts', lazy=True)
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    reports = db.relationship('Report', backref='post', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CommunityPost {self.id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'habit_id': self.habit_id,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'likes_count': len(self.likes),
            'comments_count': len(self.comments)
        }

class Like(db.Model):
    __tablename__ = 'likes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='likes', lazy=True)
    
    def __repr__(self):
        return f'<Like {self.id}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='comments', lazy=True)
    reports = db.relationship('CommentReport', backref='comment', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Comment {self.id}>'

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    reason = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='reports', lazy=True)
    
    def __repr__(self):
        return f'<Report {self.id}>'

class CommentReport(db.Model):
    __tablename__ = 'comment_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=False)
    reason = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='comment_reports', lazy=True)
    
    def __repr__(self):
        return f'<CommentReport {self.id}>'
