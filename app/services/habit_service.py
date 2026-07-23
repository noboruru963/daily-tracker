from app import db
from app.models.habit import Habit
from app.models.record import Record

class HabitService:
    @staticmethod
    def get_user_habits(user_id):
        return Habit.query.filter_by(user_id=user_id).all()
    
    @staticmethod
    def get_habit_by_id(habit_id, user_id):
        habit = Habit.query.get_or_404(habit_id)
        if habit.user_id != user_id:
            raise ValueError("Access denied")
        return habit
    
    @staticmethod
    def create_habit(user_id, name, description, visual_model_type, visual_settings=None, is_public=False):
        habit = Habit(
            user_id=user_id,
            name=name,
            description=description,
            visual_model_type=visual_model_type,
            visual_settings=visual_settings or {},
            is_public=is_public
        )
        db.session.add(habit)
        db.session.commit()
        return habit
    
    @staticmethod
    def update_habit(habit_id, user_id, **kwargs):
        habit = HabitService.get_habit_by_id(habit_id, user_id)
        
        for key, value in kwargs.items():
            if hasattr(habit, key):
                setattr(habit, key, value)
        
        db.session.commit()
        return habit
    
    @staticmethod
    def delete_habit(habit_id, user_id):
        habit = HabitService.get_habit_by_id(habit_id, user_id)
        db.session.delete(habit)
        db.session.commit()
    
    @staticmethod
    def get_habit_stats(habit_id, user_id):
        habit = HabitService.get_habit_by_id(habit_id, user_id)
        records = Record.query.filter_by(habit_id=habit_id).all()
        
        if not records:
            return {
                'total_records': 0,
                'average_value': 0,
                'min_value': 0,
                'max_value': 0,
                'last_record': None
            }
        
        values = [record.numerical_value for record in records]
        
        return {
            'total_records': len(records),
            'average_value': sum(values) / len(values),
            'min_value': min(values),
            'max_value': max(values),
            'last_record': records[-1] if records else None
        }