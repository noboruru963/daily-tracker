"""SQL injection prevention tests for the three-layer guard system.

Layer 1 (bound parameters)   -> payload round-trip tests through real routes
Layer 2 (runtime SqlGuard)   -> statement interception and blocking tests
Layer 3 (static AST scanner) -> codebase-wide verification of every query
"""
import pytest
from sqlalchemy import text

from app import create_app, db
from app.models.user import User
from app.models.habit import Habit
from app.models.record import Record
from app.models.community import CommunityPost
from app.models.calorie import CalorieLog
from app.security.sql_guard import (
    SQLInjectionAttempt,
    assert_safe_statement,
    find_suspicious_tokens,
    safe_order_column,
    scan_source,
    verify_project,
)


class GuardTestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    SQL_GUARD_ENABLED = True
    SQL_GUARD_MODE = 'block'
    SQL_GUARD_MAX_AUDIT = 10000


# Classic SQL injection payloads drawn from public cheat-sheet corpora.
PAYLOADS = [
    "' OR '1'='1",
    "' OR '1'='1' --",
    "admin'--",
    "' OR 1=1--",
    "'; DROP TABLE users;--",
    '" OR "1"="1',
    "') OR ('1'='1",
    "' UNION SELECT NULL--",
]

MARKER = "PAYLOAD' OR '1'='1'; DROP TABLE records;--"


@pytest.fixture
def app():
    application = create_app(GuardTestConfig)
    with application.app_context():
        application.extensions['sql_guard'].clear()
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Layer 1: payloads sent through real routes are stored as inert data
# ---------------------------------------------------------------------------
def test_login_cannot_be_bypassed_with_classic_payloads(client, app):
    for payload in PAYLOADS:
        response = client.post(
            '/auth/login',
            data={'username': payload, 'password': payload},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    with app.app_context():
        # Only the seeded system user exists; nobody got in and no table broke.
        users = User.query.all()
        assert [u.username for u in users] == ['dailyteam']
        assert db.session.execute(text('SELECT COUNT(*) FROM users')).scalar() == 1


def test_register_stores_payload_as_literal_data(client, app):
    payload = "admin'; DROP TABLE users;--"
    response = client.post(
        '/auth/register',
        data={
            'username': payload,
            'email': 'attacker@gmail.com',
            'password': 'secret123',
            'confirm_password': 'secret123',
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username=payload).first()
        assert user is not None  # stored byte-for-byte as data, not executed
        assert db.session.execute(text('SELECT COUNT(*) FROM users')).scalar() >= 1

    # The literal payload can even be used to log back in as a normal user.
    response = client.post(
        '/auth/login',
        data={'username': payload, 'password': 'secret123'},
    )
    assert response.status_code == 302
    assert 'dashboard' in response.headers['Location']


def test_community_post_payload_neutralised(client, app):
    with app.app_context():
        user = User(username='poster', email='poster@gmail.com')
        user.set_password('secret123')
        db.session.add(user)
        db.session.flush()  # assign user.id before linking the habit
        habit = Habit(user_id=user.id, name='Safe Habit', visual_model_type='graph', is_public=True)
        db.session.add(habit)
        db.session.commit()
        habit_id = habit.id

    client.post('/auth/login', data={'username': 'poster', 'password': 'secret123'})

    payload = "'); DROP TABLE community_posts;--"
    response = client.post(
        '/community/habit/%d/share' % habit_id,
        data={'content': payload},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        posts = CommunityPost.query.all()
        assert len(posts) == 1
        assert posts[0].content == payload
        assert db.session.execute(text('SELECT COUNT(*) FROM community_posts')).scalar() == 1


# ---------------------------------------------------------------------------
# Layer 2: runtime interception of unsafe statements
# ---------------------------------------------------------------------------
def test_guard_blocks_injected_raw_statement(app):
    with app.app_context():
        with pytest.raises(SQLInjectionAttempt):
            db.session.execute(text("SELECT id FROM users WHERE username = 'a' OR '1'='1'"))
        db.session.rollback()
        assert db.session.execute(text('SELECT COUNT(*) FROM users')).scalar() >= 0


def test_guard_blocks_stacked_statement(app):
    from sqlalchemy import inspect as sa_inspect

    with app.app_context():
        with pytest.raises(SQLInjectionAttempt):
            db.session.execute(text('SELECT id FROM users; DROP TABLE users'))
        db.session.rollback()
        # Table is still there.
        assert 'users' in sa_inspect(db.engine).get_table_names()


def test_guard_allows_parameterised_payloads(app):
    payload = "' OR '1'='1"
    with app.app_context():
        user = User(username='victim', email='victim@gmail.com')
        user.set_password('secret123')
        db.session.add(user)
        db.session.commit()

        # The exact payload in a bound parameter is inert: it matches nothing.
        row = db.session.execute(
            text('SELECT id FROM users WHERE username = :uname'), {'uname': payload}
        ).fetchone()
        assert row is None

        row = db.session.execute(
            text('SELECT id FROM users WHERE username = :uname'), {'uname': 'victim'}
        ).fetchone()
        assert row is not None

        guard = app.extensions['sql_guard']
        assert guard.violations == []


def test_guard_log_mode_records_without_raising(app):
    app.config['SQL_GUARD_MODE'] = 'log'
    with app.app_context():
        db.session.execute(text("SELECT 1 FROM users WHERE username = 'x'--"))
        db.session.rollback()
        guard = app.extensions['sql_guard']
        assert any(record.suspicious for record in guard.audit_log)


def test_framework_ddl_from_metadata_is_not_blocked(app):
    # create_all()/drop_all() emit CREATE/DROP TABLE compiled from model
    # metadata; the guard must not block this framework DDL.
    with app.app_context():
        db.drop_all()
        db.create_all()
        # Tables were dropped and recreated - the guard let DDL through.
        assert User.query.count() == 0


def test_guard_captures_full_audit_trail(app):
    with app.app_context():
        db.session.execute(text('SELECT COUNT(*) FROM users'))
        db.session.rollback()
        guard = app.extensions['sql_guard']
        assert guard.statement_count >= 1
        record = guard.audit_log[-1]
        assert record.parameterized is False
        assert record.suspicious == ()


def test_assert_safe_statement():
    assert_safe_statement('ALTER TABLE records ADD COLUMN sort_order INTEGER DEFAULT 0')
    with pytest.raises(SQLInjectionAttempt):
        assert_safe_statement('DROP TABLE users')
    with pytest.raises(SQLInjectionAttempt):
        assert_safe_statement("SELECT * FROM users WHERE name = 'a' OR '1'='1'")


def test_find_suspicious_tokens_signatures():
    assert 'sql_comment' in find_suspicious_tokens('SELECT 1--')
    assert 'stacked_statement' in find_suspicious_tokens('SELECT 1; DROP TABLE t')
    assert 'union_select' in find_suspicious_tokens('SELECT NULL UNION SELECT password FROM users')
    assert 'boolean_tautology' in find_suspicious_tokens("SELECT 1 WHERE 1=1 OR '1'='1'")
    assert 'drop_object' in find_suspicious_tokens('DROP TABLE users')
    # Normal ORM/DDL statements produce no hits.
    assert find_suspicious_tokens('SELECT * FROM users WHERE users.username = ?') == ()
    assert find_suspicious_tokens(
        "ALTER TABLE records ADD COLUMN record_icon VARCHAR(50) DEFAULT ''"
    ) == ()


# ---------------------------------------------------------------------------
# Identifiers that cannot be parameterised must be allow-listed
# ---------------------------------------------------------------------------
def test_order_column_whitelist():
    allowed = {'date': Record.date, 'value': Record.numerical_value}
    assert safe_order_column('date', allowed) is Record.date

    for attack in ('date; DROP TABLE records;--', '1=1', 'random_col', None, 42):
        with pytest.raises(SQLInjectionAttempt):
            safe_order_column(attack, allowed)


# ---------------------------------------------------------------------------
# Layer 3: static verification of every query in the codebase
# ---------------------------------------------------------------------------
def test_static_scanner_flags_dynamic_sql():
    vulnerable = '''
from sqlalchemy import text

def run(db, user_input):
    db.session.execute(text(f"SELECT * FROM users WHERE name = '{user_input}'"))
    db.session.execute("SELECT * FROM t WHERE id = %s" % user_input)
    db.session.execute("SELECT * FROM t WHERE id = " + user_input)
    query = "SELECT * FROM users"
    db.session.execute(query)
    db.session.execute(text("SELECT * FROM t WHERE id = {}".format(user_input)))
'''
    violations = scan_source(vulnerable, 'vulnerable.py')
    assert len(violations) >= 5
    issues = ' | '.join(str(v) for v in violations)
    assert 'f-string' in issues
    assert '%-formatting' in issues
    assert 'concatenation' in issues
    assert 'unparameterised variable' in issues
    assert 'str.format()' in issues


def test_static_scanner_accepts_parameterised_sql():
    safe = '''
from sqlalchemy import text

def run(db, user_input):
    db.session.execute(text('SELECT * FROM users WHERE name = :name'), {'name': user_input})
    db.session.execute(text('ALTER TABLE records ADD COLUMN sort_order INTEGER DEFAULT 0'))
'''
    assert scan_source(safe, 'safe.py') == []


def test_entire_app_codebase_is_free_of_dynamic_sql():
    """Verification of ALL queries in the app package (layer 3)."""
    result = verify_project(['app'])
    assert result.ok, 'Unsafe query construction(s):\n' + '\n'.join(
        str(v) for v in result.violations
    )
    assert result.files_scanned > 10


# ---------------------------------------------------------------------------
# End-to-end: every statement of a full user flow is verified
# ---------------------------------------------------------------------------
def test_every_query_during_full_user_flow_is_parameterised(client, app):
    guard = app.extensions['sql_guard']
    guard.clear()

    client.post(
        '/auth/register',
        data={
            'username': 'flowuser',
            'email': 'flow@gmail.com',
            'password': 'secret123',
            'confirm_password': 'secret123',
        },
        follow_redirects=True,
    )
    client.post('/auth/login', data={'username': 'flowuser', 'password': 'secret123'})

    response = client.post(
        '/habits/create',
        data={
            'name': MARKER,
            'description': MARKER,
            'visual_model_type': 'graph',
            'is_public': 'on',
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        habit_id = Habit.query.filter_by(name=MARKER).first().id

    client.post(
        '/tracking/%d/add' % habit_id,
        data={
            'numerical_value': '5',
            'numeric_type': 'positive_int',
            'description': MARKER,
            'date': '2026-01-01',
            'record_icon': MARKER,
        },
        follow_redirects=True,
    )
    client.post('/community/habit/%d/share' % habit_id, data={'content': MARKER}, follow_redirects=True)
    client.post(
        '/calories/log',
        data={
            'meal_type': 'lunch',
            'description': MARKER,
            'date': '2026-01-01',
            'manual_item_name': [MARKER],
            'manual_item_calories': ['100'],
        },
        follow_redirects=True,
    )

    records = list(guard.audit_log)
    assert len(records) > 15  # the flow really exercised the query layer

    for record in records:
        assert record.suspicious == ()  # every statement passed verification
        assert MARKER not in record.statement  # user data never enters SQL text

    with app.app_context():
        # All payload-carrying rows were stored and remain readable.
        assert Record.query.filter_by(description=MARKER).count() == 1
        assert CommunityPost.query.filter_by(content=MARKER).count() == 1
        assert CalorieLog.query.filter(CalorieLog.description.contains(MARKER)).count() == 1
