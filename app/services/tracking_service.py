from datetime import datetime, timedelta
from app import db
from app.models.habit import Habit
from app.models.record import Record

class TrackingService:
    @staticmethod
    def add_record(habit_id, numerical_value, description='', **kwargs):
        record = Record(
            habit_id=habit_id,
            numerical_value=numerical_value,
            description=description,
            date=datetime.utcnow(),
            **kwargs
        )
        
        # Update habit-specific settings
        habit = Habit.query.get(habit_id)
        if habit.visual_model_type == 'percentage':
            habit.visual_settings['current_value'] = numerical_value
        
        db.session.add(record)
        db.session.commit()
        return record
    
    @staticmethod
    def get_records(habit_id, start_date=None, end_date=None):
        query = Record.query.filter_by(habit_id=habit_id)
        
        if start_date:
            query = query.filter(Record.date >= start_date)
        if end_date:
            query = query.filter(Record.date <= end_date)
        
        return query.order_by(Record.date.asc()).all()
    
    @staticmethod
    def get_chart_data(habit_id, days=30):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        records = TrackingService.get_records(habit_id, start_date, end_date)
        
        return {
            'labels': [record.date.strftime('%Y-%m-%d') for record in records],
            'values': [record.numerical_value for record in records],
            'descriptions': [record.description for record in records]
        }
    
    @staticmethod
    def get_progression_data(habit_id):
        habit = Habit.query.get(habit_id)
        records = Record.query.filter_by(habit_id=habit_id).order_by(Record.step_number.asc()).all()
        
        steps = habit.visual_settings.get('steps', [])
        completed_steps = [record.step_number for record in records]
        
        return {
            'total_steps': len(steps),
            'completed_steps': completed_steps,
            'current_step': max(completed_steps) if completed_steps else 0,
            'steps': steps
        }
    
    @staticmethod
    def get_calendar_data(habit_id, year, month):
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        records = TrackingService.get_records(habit_id, start_date, end_date)
        
        # Group by day
        calendar_data = {}
        for record in records:
            day = record.date.day
            if day not in calendar_data:
                calendar_data[day] = []
            calendar_data[day].append(record)
        
        return calendar_data
    
    @staticmethod
    def get_percentage_data(habit_id):
        habit = Habit.query.get(habit_id)
        settings = habit.visual_settings
        
        return {
            'current_value': settings.get('current_value', 0),
            'min_value': settings.get('min_value', 0),
            'max_value': settings.get('max_value', 100),
            'percentage': ((settings.get('current_value', 0) - settings.get('min_value', 0)) / 
                          (settings.get('max_value', 100) - settings.get('min_value', 0))) * 100
        }