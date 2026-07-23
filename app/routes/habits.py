from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.habit import Habit
from app.models.record import Record
from app.config import Config

habits_bp = Blueprint('habits', __name__)

@habits_bp.route('/dashboard')
@login_required
def dashboard():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    pinned = [h for h in habits if h.is_pinned]
    unpinned = [h for h in habits if not h.is_pinned]
    return render_template('habits/dashboard.html', habits=habits, pinned_habits=pinned, unpinned_habits=unpinned, visual_models=Config.VISUAL_MODELS)

@habits_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_habit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        visual_model_type = request.form.get('visual_model_type')
        is_public = request.form.get('is_public') == 'on'
        
        if not name or not visual_model_type:
            flash('Name and visual model type are required.', 'error')
            return render_template('habits/create.html', visual_models=Config.VISUAL_MODELS)
        
        visual_settings = {}
        visual_settings['theme_color'] = request.form.get('theme_color', '#10b981')
        visual_settings['icon'] = request.form.get('habit_icon', 'house')
        
        if visual_model_type == 'graph':
            visual_settings['graph_type'] = request.form.get('graph_type', 'line')
            visual_settings['time_range'] = int(request.form.get('time_range', 30))
        elif visual_model_type == 'progression':
            step_names = request.form.getlist('step_name[]')
            step_descs = request.form.getlist('step_desc[]')
            steps = []
            for i, name_val in enumerate(step_names):
                if name_val:
                    desc = step_descs[i] if i < len(step_descs) else ''
                    steps.append({'name': name_val, 'description': desc, 'completed': False})
            visual_settings['steps'] = steps
            visual_settings['current_step'] = 0
        elif visual_model_type == 'percentage':
            visual_settings['min_value'] = float(request.form.get('min_value', 0))
            visual_settings['max_value'] = float(request.form.get('max_value', 100))
            visual_settings['current_value'] = float(request.form.get('current_value', 0))
            visual_settings['unit'] = request.form.get('unit', '')
        elif visual_model_type == 'calendar':
            visual_settings['schedule'] = request.form.getlist('schedule[]')
            visual_settings['reminder_time'] = request.form.get('reminder_time', '09:00')
            visual_settings['activity_types'] = []
        
        habit = Habit(
            user_id=current_user.id,
            name=name,
            description=description,
            visual_model_type=visual_model_type,
            visual_settings=visual_settings,
            is_public=is_public
        )
        
        db.session.add(habit)
        db.session.commit()
        
        flash('Habit created successfully!', 'success')
        return redirect(url_for('habits.view_habit', habit_id=habit.id))
    
    return render_template('habits/create.html', visual_models=Config.VISUAL_MODELS)

@habits_bp.route('/<int:habit_id>')
@login_required
def view_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('habits.dashboard'))
    
    records = Record.query.filter_by(habit_id=habit_id).order_by(Record.date.desc()).all()
    return render_template('habits/view.html', habit=habit, records=records)

@habits_bp.route('/<int:habit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('habits.dashboard'))
    
    if request.method == 'POST':
        habit.name = request.form.get('name')
        habit.description = request.form.get('description')
        habit.is_public = request.form.get('is_public') == 'on'
        
        habit.visual_settings['theme_color'] = request.form.get('theme_color', habit.visual_settings.get('theme_color', '#10b981'))
        habit.visual_settings['icon'] = request.form.get('habit_icon', habit.visual_settings.get('icon', 'house'))
        
        if habit.visual_model_type == 'graph':
            habit.visual_settings['graph_type'] = request.form.get('graph_type', 'line')
            habit.visual_settings['time_range'] = int(request.form.get('time_range', 30))
        elif habit.visual_model_type == 'progression':
            step_names = request.form.getlist('step_name[]')
            step_descs = request.form.getlist('step_desc[]')
            steps = []
            for i, name_val in enumerate(step_names):
                if name_val:
                    desc = step_descs[i] if i < len(step_descs) else ''
                    steps.append({'name': name_val, 'description': desc, 'completed': False})
            habit.visual_settings['steps'] = steps
        elif habit.visual_model_type == 'percentage':
            habit.visual_settings['min_value'] = float(request.form.get('min_value', 0))
            habit.visual_settings['max_value'] = float(request.form.get('max_value', 100))
            habit.visual_settings['current_value'] = float(request.form.get('current_value', 0))
            habit.visual_settings['unit'] = request.form.get('unit', '')
        elif habit.visual_model_type == 'calendar':
            habit.visual_settings['schedule'] = request.form.getlist('schedule[]')
            habit.visual_settings['reminder_time'] = request.form.get('reminder_time', '09:00')
            act_names = request.form.getlist('activity_type_name[]')
            act_icons = request.form.getlist('activity_type_icon[]')
            act_colors = request.form.getlist('activity_type_color[]')
            activity_types = []
            for i, aname in enumerate(act_names):
                if aname:
                    aicon = act_icons[i] if i < len(act_icons) else 'circle'
                    acolor = act_colors[i] if i < len(act_colors) else '#10b981'
                    activity_types.append({'name': aname, 'icon': aicon, 'color': acolor})
            habit.visual_settings['activity_types'] = activity_types
        
        db.session.commit()
        flash('Habit updated successfully!', 'success')
        return redirect(url_for('habits.view_habit', habit_id=habit.id))
    
    return render_template('habits/edit.html', habit=habit, visual_models=Config.VISUAL_MODELS)

@habits_bp.route('/<int:habit_id>/delete', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('habits.dashboard'))
    
    db.session.delete(habit)
    db.session.commit()
    
    flash('Habit deleted successfully!', 'success')
    return redirect(url_for('habits.dashboard'))

@habits_bp.route('/<int:habit_id>/pin', methods=['POST'])
@login_required
def toggle_pin(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    habit.is_pinned = not habit.is_pinned
    db.session.commit()
    
    return jsonify({'success': True, 'pinned': habit.is_pinned})
