from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.habit import Habit
from app.models.community import CommunityPost, Like, Comment, Report
from sqlalchemy.orm import joinedload

community_bp = Blueprint('community', __name__)

@community_bp.route('/')
@login_required
def index():
    public_habits = Habit.query.filter_by(is_public=True).filter(Habit.user_id != current_user.id).all()
    return render_template('community/index.html', habits=public_habits)

@community_bp.route('/habit/<int:habit_id>')
@login_required
def view_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if not habit.is_public and habit.user_id != current_user.id:
        flash('This habit is private.', 'error')
        return redirect(url_for('community.index'))
    
    posts = CommunityPost.query.options(
        joinedload(CommunityPost.user),
        joinedload(CommunityPost.comments).joinedload(Comment.user),
        joinedload(CommunityPost.likes)
    ).filter_by(habit_id=habit_id).order_by(CommunityPost.created_at.desc()).all()
    return render_template('community/habit.html', habit=habit, posts=posts)

@community_bp.route('/habit/<int:habit_id>/share', methods=['POST'])
@login_required
def share_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if not habit.is_public and habit.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('community.index'))
    
    content = request.form.get('content', '').strip()
    if not content:
        flash('Post content cannot be empty.', 'error')
        return redirect(url_for('community.view_habit', habit_id=habit_id))
    
    post = CommunityPost(
        user_id=current_user.id,
        habit_id=habit_id,
        content=content
    )
    
    db.session.add(post)
    db.session.commit()
    
    flash('Post shared with community!', 'success')
    return redirect(url_for('community.view_habit', habit_id=habit_id))

@community_bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
    
    db.session.commit()
    return redirect(url_for('community.view_habit', habit_id=post.habit_id))

@community_bp.route('/post/<int:post_id>/report', methods=['POST'])
@login_required
def report_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_report = Report.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing_report:
        flash('You have already reported this post.', 'info')
    else:
        reason = request.form.get('reason', '')
        report = Report(user_id=current_user.id, post_id=post_id, reason=reason)
        db.session.add(report)
        db.session.commit()
        flash('Post has been reported. Thank you for your feedback.', 'success')
    
    return redirect(url_for('community.view_habit', habit_id=post.habit_id))

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('community.view_habit', habit_id=post.habit_id))
    
    comment = Comment(
        user_id=current_user.id,
        post_id=post_id,
        content=content
    )
    
    db.session.add(comment)
    db.session.commit()
    
    return redirect(url_for('community.view_habit', habit_id=post.habit_id))

@community_bp.route('/habit/<int:habit_id>/copy', methods=['POST'])
@login_required
def copy_habit(habit_id):
    from app.models.settings import UserSettings
    original = Habit.query.get_or_404(habit_id)
    
    if original.user_id == current_user.id:
        flash('You cannot copy your own habit.', 'info')
        return redirect(url_for('community.view_habit', habit_id=habit_id))
    
    import copy
    new_settings = copy.deepcopy(original.visual_settings or {})
    
    new_habit = Habit(
        user_id=current_user.id,
        name=f"Copy of {original.name}",
        description=original.description,
        visual_model_type=original.visual_model_type,
        visual_settings=new_settings,
        is_public=False
    )
    
    db.session.add(new_habit)
    db.session.commit()
    
    flash(f'Habit "{original.name}" copied! You can now customize it.', 'success')
    return redirect(url_for('habits.edit_habit', habit_id=new_habit.id))
