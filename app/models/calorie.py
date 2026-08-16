from datetime import datetime
from app import db


class FoodItem(db.Model):
    __tablename__ = 'food_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('food_items', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<FoodItem {self.name} {self.calories}kcal>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'calories': self.calories,
        }


class CalorieSettings(db.Model):
    __tablename__ = 'calorie_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    maintenance_calories = db.Column(db.Integer, default=2000)

    user = db.relationship('User', backref=db.backref('calorie_settings', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<CalorieSettings user={self.user_id} maintenance={self.maintenance_calories}>'


class CalorieLog(db.Model):
    __tablename__ = 'calorie_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    calories = db.Column(db.Integer, nullable=False)
    meal_type = db.Column(db.String(20), default='other')
    description = db.Column(db.String(200), default='')

    user = db.relationship('User', backref=db.backref('calorie_logs', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<CalorieLog {self.calories}kcal {self.meal_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'calories': self.calories,
            'meal_type': self.meal_type,
            'description': self.description,
        }
