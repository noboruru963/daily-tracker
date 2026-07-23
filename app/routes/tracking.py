from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models.habit import Habit
from app.models.record import Record

tracking_bp = Blueprint('tracking', __name__)

NUMERIC_TYPES = {
    'positive_int': {'min': 0, 'step': 1, 'allow_negative': False, 'allow_decimal': False},
    'negative_int': {'max': 0, 'step': 1, 'allow_negative': True, 'allow_decimal': False},
    'positive_float': {'min': 0, 'step': 0.01, 'allow_negative': False, 'allow_decimal': True},
    'negative_float': {'max': 0, 'step': 0.01, 'allow_negative': True, 'allow_decimal': True},
    'float': {'step': 0.01, 'allow_negative': True, 'allow_decimal': True}
}

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
        elif habit.visual_model_type == 'calendar':
            record.time_spent = float(request.form.get('time_spent', 0))
            act_type = request.form.get('activity_type', '')
            record.activity_type = act_type if act_type else ''
        elif habit.visual_model_type == 'percentage':
            record.target_value = numerical_value
            habit.visual_settings['current_value'] = numerical_value
        
        db.session.add(record)
        db.session.commit()
        
        flash('Record added successfully!', 'success')
        return redirect(url_for('habits.view_habit', habit_id=habit_id))
    
    today_str = date.today().isoformat()
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
    elif habit.visual_model_type == 'calendar':
        record.time_spent = float(data.get('time_spent', 0))
    elif habit.visual_model_type == 'percentage':
        record.target_value = numerical_value
        habit.visual_settings['current_value'] = numerical_value
    
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
    
    records = Record.query.filter_by(habit_id=habit_id).order_by(Record.date.desc()).all()
    return render_template('tracking/records.html', habit=habit, records=records)

@tracking_bp.route('/api/<int:habit_id>/data')
@login_required
def get_habit_data(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    records = Record.query.filter_by(habit_id=habit_id).order_by(Record.date.asc()).all()
    
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
        habit.visual_settings['current_value'] = record.numerical_value
    
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
    
    for idx, record_id in enumerate(data['record_ids']):
        record = Record.query.get(record_id)
        if record and record.habit_id == habit_id:
            record.date = record.date.replace(minute=idx)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Records reordered'})
