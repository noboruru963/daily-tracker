from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models.calorie import CalorieLog, CalorieSettings, FoodItem

calories_bp = Blueprint('calories', __name__)

MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack']


def _get_or_create_settings():
    settings = CalorieSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = CalorieSettings(user_id=current_user.id, maintenance_calories=2000)
        db.session.add(settings)
        db.session.commit()
    return settings


def _day_range(dt):
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


@calories_bp.route('/')
@login_required
def dashboard():
    settings = _get_or_create_settings()
    today_start, today_end = _day_range(datetime.utcnow())

    today_logs = CalorieLog.query.filter(
        CalorieLog.user_id == current_user.id,
        CalorieLog.date >= today_start,
        CalorieLog.date < today_end,
    ).order_by(CalorieLog.date.asc()).all()

    total_today = sum(l.calories for l in today_logs)
    remaining = settings.maintenance_calories - total_today

    food_items = FoodItem.query.filter_by(user_id=current_user.id).order_by(FoodItem.name.asc()).all()

    return render_template(
        'calories/dashboard.html',
        settings=settings,
        today_logs=today_logs,
        total_today=total_today,
        remaining=remaining,
        meal_types=MEAL_TYPES,
        food_items=food_items,
        today=datetime.utcnow().strftime('%Y-%m-%d'),
    )


@calories_bp.route('/log', methods=['POST'])
@login_required
def log_entry():
    meal_type = request.form.get('meal_type', 'other')
    description = request.form.get('description', '').strip()
    date_str = request.form.get('date', '')
    food_item_ids = request.form.getlist('food_items')
    manual_names = request.form.getlist('manual_item_name')
    manual_cals = request.form.getlist('manual_item_calories')

    if date_str:
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            log_date = datetime.utcnow()
    else:
        log_date = datetime.utcnow()

    all_items = []

    if food_item_ids:
        items = FoodItem.query.filter(
            FoodItem.id.in_(food_item_ids),
            FoodItem.user_id == current_user.id,
        ).all()
        for item in items:
            all_items.append(f"{item.name} ({item.calories})")

    if manual_names and manual_cals:
        for name, cal in zip(manual_names, manual_cals):
            try:
                cal_val = int(cal)
                if cal_val > 0:
                    all_items.append(f"{name} ({cal_val})")
            except ValueError:
                pass

    if all_items:
        total_cal = sum(
            int(part.split('(')[-1].rstrip(')'))
            for part in all_items
        )
        desc_parts = []
        if description:
            desc_parts.append(description)
        desc_parts.append(' + '.join(all_items))
        final_desc = ' | '.join(desc_parts)
    else:
        flash('Please add ingredients or enter calories.', 'error')
        return redirect(url_for('calories.dashboard'))

    entry = CalorieLog(
        user_id=current_user.id,
        date=log_date,
        calories=total_cal,
        meal_type=meal_type,
        description=final_desc,
    )
    db.session.add(entry)
    db.session.commit()

    flash(f'Logged {total_cal} kcal ({meal_type}).', 'success')
    return redirect(url_for('calories.dashboard'))


@calories_bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_entry(log_id):
    entry = CalorieLog.query.get_or_404(log_id)
    if entry.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('calories.dashboard'))

    db.session.delete(entry)
    db.session.commit()
    flash('Entry deleted.', 'success')
    return redirect(url_for('calories.dashboard'))


@calories_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    maintenance = request.form.get('maintenance_calories', '').strip()
    if not maintenance:
        flash('Please enter your maintenance calories.', 'error')
        return redirect(url_for('calories.dashboard'))

    try:
        m_value = int(maintenance)
    except ValueError:
        flash('Invalid value.', 'error')
        return redirect(url_for('calories.dashboard'))

    if m_value < 1:
        flash('Maintenance calories must be at least 1.', 'error')
        return redirect(url_for('calories.dashboard'))

    settings = _get_or_create_settings()
    settings.maintenance_calories = m_value
    db.session.commit()

    flash('Maintenance calories updated.', 'success')
    return redirect(url_for('calories.dashboard'))


@calories_bp.route('/api/today')
@login_required
def api_today():
    settings = _get_or_create_settings()
    today_start, today_end = _day_range(datetime.utcnow())

    logs = CalorieLog.query.filter(
        CalorieLog.user_id == current_user.id,
        CalorieLog.date >= today_start,
        CalorieLog.date < today_end,
    ).order_by(CalorieLog.date.asc()).all()

    return jsonify({
        'maintenance': settings.maintenance_calories,
        'total': sum(l.calories for l in logs),
        'logs': [l.to_dict() for l in logs],
    })


@calories_bp.route('/api/weekly')
@login_required
def api_weekly():
    settings = _get_or_create_settings()
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=6)

    logs = CalorieLog.query.filter(
        CalorieLog.user_id == current_user.id,
        CalorieLog.date >= week_ago,
    ).all()

    daily = {}
    for i in range(7):
        d = week_ago + timedelta(days=i)
        daily[d.strftime('%Y-%m-%d')] = 0

    for log in logs:
        key = log.date.strftime('%Y-%m-%d')
        if key in daily:
            daily[key] += log.calories

    return jsonify({
        'maintenance': settings.maintenance_calories,
        'days': [{'date': k, 'total': v} for k, v in daily.items()],
    })


@calories_bp.route('/api/food-items', methods=['GET'])
@login_required
def api_food_items():
    items = FoodItem.query.filter_by(user_id=current_user.id).order_by(FoodItem.name.asc()).all()
    return jsonify([i.to_dict() for i in items])


@calories_bp.route('/api/food-items', methods=['POST'])
@login_required
def api_add_food_item():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('calories'):
        return jsonify({'error': 'Name and calories required'}), 400

    name = data['name'].strip()
    try:
        calories = int(data['calories'])
    except ValueError:
        return jsonify({'error': 'Invalid calorie value'}), 400

    if calories < 1:
        return jsonify({'error': 'Calories must be at least 1'}), 400

    existing = FoodItem.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        existing.calories = calories
        db.session.commit()
        return jsonify({'success': True, 'item': existing.to_dict(), 'updated': True})

    item = FoodItem(user_id=current_user.id, name=name, calories=calories)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': item.to_dict(), 'updated': False})


@calories_bp.route('/api/food-items/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_food_item(item_id):
    item = FoodItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})
