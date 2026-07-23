import pytest
from app import create_app, db
from app.models.user import User
from app.models.habit import Habit
from app.models.record import Record

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

def test_user_creation(app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('password123')
        assert not user.check_password('wrongpassword')

def test_habit_creation(app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        habit = Habit(
            user_id=user.id,
            name='Test Habit',
            description='A test habit',
            visual_model_type='graph'
        )
        db.session.add(habit)
        db.session.commit()
        
        assert habit.id is not None
        assert habit.name == 'Test Habit'
        assert habit.visual_model_type == 'graph'

def test_record_creation(app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        habit = Habit(
            user_id=user.id,
            name='Test Habit',
            description='A test habit',
            visual_model_type='graph'
        )
        db.session.add(habit)
        db.session.commit()
        
        record = Record(
            habit_id=habit.id,
            numerical_value=42.5,
            description='Test record'
        )
        db.session.add(record)
        db.session.commit()
        
        assert record.id is not None
        assert record.numerical_value == 42.5
        assert record.description == 'Test record'