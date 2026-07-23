from app import db
from app.models.habit import Habit
from app.models.community import CommunityPost, Like, Comment

class CommunityService:
    @staticmethod
    def get_public_habits(exclude_user_id=None):
        query = Habit.query.filter_by(is_public=True)
        if exclude_user_id:
            query = query.filter(Habit.user_id != exclude_user_id)
        return query.all()
    
    @staticmethod
    def get_habit_posts(habit_id):
        return CommunityPost.query.filter_by(habit_id=habit_id).order_by(CommunityPost.created_at.desc()).all()
    
    @staticmethod
    def create_post(user_id, habit_id, content=''):
        # Verify habit is public
        habit = Habit.query.get(habit_id)
        if not habit or not habit.is_public:
            raise ValueError("Habit not found or not public")
        
        post = CommunityPost(
            user_id=user_id,
            habit_id=habit_id,
            content=content
        )
        db.session.add(post)
        db.session.commit()
        return post
    
    @staticmethod
    def like_post(user_id, post_id):
        existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
        
        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            return False  # Unliked
        else:
            like = Like(user_id=user_id, post_id=post_id)
            db.session.add(like)
            db.session.commit()
            return True  # Liked
    
    @staticmethod
    def add_comment(user_id, post_id, content):
        if not content.strip():
            raise ValueError("Comment cannot be empty")
        
        comment = Comment(
            user_id=user_id,
            post_id=post_id,
            content=content
        )
        db.session.add(comment)
        db.session.commit()
        return comment
    
    @staticmethod
    def get_post_with_details(post_id):
        post = CommunityPost.query.get_or_404(post_id)
        return {
            'post': post,
            'likes_count': len(post.likes),
            'comments_count': len(post.comments),
            'has_liked': any(like.user_id == post.user_id for like in post.likes)
        }