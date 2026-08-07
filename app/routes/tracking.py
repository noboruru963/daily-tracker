from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models.habit import Habit
from app.models.record import Record
from sqlalchemy.orm.attributes import flag_modified

tracking_bp = Blueprint('tracking', __name__)

NUMERIC_TYPES = {
    'positive_int': {'min': 0, 'step': 1, 'allow_negative': False, 'allow_decimal': False},
    'negative_int': {'max': 0, 'step': 1, 'allow_negative': True, 'allow_decimal': False},
    'positive_float': {'min': 0, 'step': 'any', 'allow_negative': False, 'allow_decimal': True},
    'negative_float': {'max': 0, 'step': 'any', 'allow_negative': True, 'allow_decimal': True},
    'float': {'step': 'any', 'allow_negative': True, 'allow_decimal': True}
}

def _clamp_percentage_value(habit, value):
    """Keep a percentage habit's progress within [min_value, max_value]."""
    if habit.visual_model_type != 'percentage':
        return value
    min_val = habit.visual_settings.get('min_value', 0)
    max_val = habit.visual_settings.get('max_value', 100)
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value

@tracking_bp.route('/<int:habit_id>/add', methods=['GET', 'POST'])
@login_required
def add_record(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('habits.dashboard'))
    
    if request.method == 'POST':
        raw_value = request.form.get('numerical_value', '0')
        numeric_type = request.form.get('numeric_type', 'float')
        description = request.form.get('description', '')
        record_date = request.form.get('date', '')
        record_icon = request.form.get('record_icon', '')
        
        try:
            numerical_value = float(raw_value)
        except (ValueError, TypeError):
            flash('Invalid numeric value.', 'error')
            return redirect(url_for('tracking.add_record', habit_id=habit_id))
        
        type_rules = NUMERIC_TYPES.get(numeric_type, NUMERIC_TYPES['float'])
        if 'min' in type_rules and numerical_value < type_rules['min']:
            flash(f'Value must be at least {type_rules["min"]}.', 'error')
            return redirect(url_for('tracking.add_record', habit_id=habit_id))
        if 'max' in type_rules and numerical_value > type_rules['max']:
            flash(f'Value must be at most {type_rules["max"]}.', 'error')
            return redirect(url_for('tracking.add_record', habit_id=habit_id))
        if not type_rules.get('allow_decimal', True) and numerical_value != int(numerical_value):
            flash('Value must be a whole number (no decimals).', 'error')
            return redirect(url_for('tracking.add_record', habit_id=habit_id))
        
        if record_date:
            try:
                parsed_date = datetime.strptime(record_date, '%Y-%m-%d')
            except ValueError:
                parsed_date = datetime.utcnow()
        else:
            parsed_date = datetime.utcnow()
        
        # Check daily limit for calendar habits
        if habit.visual_model_type == 'calendar':
            times_per_day = habit.visual_settings.get('times_per_day', 1)
            day_start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            daily_count = Record.query.filter(
                Record.habit_id == habit_id,
                Record.date >= day_start,
                Record.date < day_end
            ).count()
            if daily_count >= times_per_day:
                flash(f'Daily limit reached. You can only log this habit {times_per_day} time(s) per day.', 'error')
                return redirect(url_for('tracking.add_record', habit_id=habit_id))
        
        record = Record(
            habit_id=habit_id,
            numerical_value=numerical_value,
            description=description,
            date=parsed_date
        )
        
        if habit.visual_model_type == 'progression':
            record.step_number = int(request.form.get('step_number', 0))
            record.step_name = request.form.get('step_name', '')
            steps = habit.visual_settings.get('steps', [])
            if record.step_number < len(steps):
                steps[record.step_number]['completed'] = True
                if 'description' not in steps[record.step_number]:
                    steps[record.step_number]['description'] = ''
                habit.visual_settings['steps'] = steps
            habit.visual_settings['current_step'] = record.step_number + 1
            flag_modified(habit, 'visual_settings')
        elif habit.visual_model_type == 'calendar':
            record.time_spent = float(request.form.get('time_spent', 0))
            act_type = request.form.get('activity_type', '')
            record.activity_type = act_type if act_type else ''
        elif habit.visual_model_type == 'percentage':
            clamped = _clamp_percentage_value(habit, numerical_value)
            record.numerical_value = clamped
            record.target_value = clamped
            habit.visual_settings['current_value'] = clamped
            flag_modified(habit, 'visual_settings')
        
        db.session.add(record)
        db.session.commit()
        
        flash('Record added successfully!', 'success')
        return redirect(url_for('habits.view_habit', habit_id=habit_id))
    
    today_str = request.args.get('date', date.today().isoformat())
    return render_template('tracking/add.html', habit=habit, today=today_str, numeric_types=NUMERIC_TYPES)

@tracking_bp.route('/api/<int:habit_id>/quick-add', methods=['POST'])
@login_required
def quick_add_record(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    record_date_str = data.get('date', '')
    if record_date_str:
        try:
            parsed_date = datetime.strptime(record_date_str, '%Y-%m-%d')
        except ValueError:
            parsed_date = datetime.utcnow()
    else:
        parsed_date = datetime.utcnow()
    
    # Check daily limit for calendar habits
    if habit.visual_model_type == 'calendar':
        times_per_day = habit.visual_settings.get('times_per_day', 1)
        day_start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        daily_count = Record.query.filter(
            Record.habit_id == habit_id,
            Record.date >= day_start,
            Record.date < day_end
        ).count()
        if daily_count >= times_per_day:
            return jsonify({'error': f'Daily limit reached. You can only log this habit {times_per_day} time(s) per day.'}), 400

    numerical_value = float(data.get('numerical_value', 1))
    description = data.get('description', '')
    activity_type = data.get('activity_type', '')
    
    record = Record(
        habit_id=habit_id,
        numerical_value=numerical_value,
        description=description,
        date=parsed_date,
        activity_type=activity_type if habit.visual_model_type == 'calendar' else ''
    )
    
    if habit.visual_model_type == 'progression':
        record.step_number = int(data.get('step_number', 0))
        record.step_name = data.get('step_name', '')
        steps = habit.visual_settings.get('steps', [])
        if record.step_number < len(steps):
            steps[record.step_number]['completed'] = True
            if 'description' not in steps[record.step_number]:
                steps[record.step_number]['description'] = ''
            habit.visual_settings['steps'] = steps
        habit.visual_settings['current_step'] = record.step_number + 1
        flag_modified(habit, 'visual_settings')
    elif habit.visual_model_type == 'calendar':
        record.time_spent = float(data.get('time_spent', 0))
    elif habit.visual_model_type == 'percentage':
        clamped = _clamp_percentage_value(habit, numerical_value)
        record.numerical_value = clamped
        record.target_value = clamped
        habit.visual_settings['current_value'] = clamped
        flag_modified(habit, 'visual_settings')
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Record added', 'record_id': record.id})

@tracking_bp.route('/<int:habit_id>/records')
@login_required
def view_records(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('habits.dashboard'))
    
    records = Record.query.filter_by(habit_id=habit_id).order_by(Record.sort_order.desc(), Record.date.desc()).all()
    return render_template('tracking/records.html', habit=habit, records=records)

@tracking_bp.route('/api/daily-count/<int:habit_id>')
@login_required
def get_daily_count(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    date_str = request.args.get('date', '')
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
    except ValueError:
        query_date = datetime.utcnow()
    
    day_start = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    count = Record.query.filter(
        Record.habit_id == habit_id,
        Record.date >= day_start,
        Record.date < day_end
    ).count()
    
    return jsonify({'count': count})

@tracking_bp.route('/api/calendar-habits')
@login_required
def get_calendar_habits_data():
    habits = Habit.query.filter_by(user_id=current_user.id, visual_model_type='calendar').all()
    result = []
    for habit in habits:
        records = Record.query.filter_by(habit_id=habit.id).order_by(Record.date.asc()).all()
        result.append({
            'habit': habit.to_dict(),
            'records': [record.to_dict() for record in records]
        })
    return jsonify(result)

@tracking_bp.route('/api/<int:habit_id>/data')
@login_required
def get_habit_data(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    records = Record.query.filter_by(habit_id=habit_id).order_by(Record.sort_order.desc(), Record.date.desc()).all()
    
    data = {
        'habit': habit.to_dict(),
        'records': [record.to_dict() for record in records],
        'chart_data': {
            'labels': [record.date.strftime('%Y-%m-%d') for record in records],
            'values': [record.numerical_value for record in records]
        }
    }
    
    return jsonify(data)

@tracking_bp.route('/api/<int:habit_id>/record/<int:record_id>/update', methods=['POST'])
@login_required
def update_record(habit_id, record_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    record = Record.query.get_or_404(record_id)
    if record.habit_id != habit_id:
        return jsonify({'error': 'Record not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'numerical_value' in data:
        record.numerical_value = float(data['numerical_value'])
    if 'description' in data:
        record.description = data['description']
    if 'date' in data:
        try:
            record.date = datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            pass
    
    if habit.visual_model_type == 'percentage':
        clamped = _clamp_percentage_value(habit, record.numerical_value)
        record.numerical_value = clamped
        record.target_value = clamped
        habit.visual_settings['current_value'] = clamped
        flag_modified(habit, 'visual_settings')
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Record updated'})

@tracking_bp.route('/api/<int:habit_id>/record/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_record(habit_id, record_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    record = Record.query.get_or_404(record_id)
    if record.habit_id != habit_id:
        return jsonify({'error': 'Record not found'}), 404
    
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Record deleted'})

@tracking_bp.route('/api/<int:habit_id>/reorder', methods=['POST'])
@login_required
def reorder_records(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if not data or 'record_ids' not in data:
        return jsonify({'error': 'No data provided'}), 400
    
    record_ids = data['record_ids']
    total = len(record_ids)
    for idx, record_id in enumerate(record_ids):
        record = Record.query.get(record_id)
        if record and record.habit_id == habit_id:
            # Top row of the table gets the highest sort_order so that the
            # graph and table both display records in the manually chosen order.
            record.sort_order = total - idx
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Records reordered'})

@tracking_bp.route('/api/<int:habit_id>/reset-progress', methods=['POST'])
@login_required
def reset_progress(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    if habit.visual_model_type != 'percentage':
        return jsonify({'error': 'Reset is only available for percentage habits'}), 400
    
    min_val = habit.visual_settings.get('min_value', 0)
    habit.visual_settings['current_value'] = min_val
    flag_modified(habit, 'visual_settings')
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Progress reset'})
