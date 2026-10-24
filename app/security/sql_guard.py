"""SQL injection prevention and query verification for the Daily Tracker app.

Three layers of defence:

1. Bound parameters everywhere (SQLAlchemy ORM + ``text()`` with named binds).
   This is the primary defence: user input never becomes part of the SQL
   string, so it can never change the meaning of a query.

2. Runtime statement verification (``SqlGuard``).  Every statement sent to the
   database driver is inspected for SQL-injection signatures (comments,
   stacked queries, UNION probes, boolean tautologies, ...).  Anything
   suspicious is recorded and, in ``block`` mode, aborted before it reaches
   the database.  Because safe code always sends user data as bound
   parameters, the statement text of a normal query never contains user
   input, so any signature hit is either an injection attempt or unsafe
   string-built SQL.

3. Static verification (``scan_source`` / ``verify_project``).  An AST scan of
   the whole codebase that fails any raw-SQL call site built from f-strings,
   ``str.format``, ``%`` formatting, string concatenation or bare variables.

Run ``python verify_queries.py`` (or the pytest suite) to verify every query
in the project at once.
"""

import ast
import os
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.sql.compiler import DDLCompiler


class SQLInjectionAttempt(Exception):
    """Raised when a statement carrying an injection signature reaches the driver."""


# ---------------------------------------------------------------------------
# Layer 2 - runtime signature detection
# ---------------------------------------------------------------------------
# These rules are matched against the *statement text* only.  Bound
# parameters are never inspected: putting user data in parameters is the
# correct, safe pattern (payload characters such as quotes, semicolons or
# comments are just data to the driver and cannot alter the SQL).
_SUSPICION_RULES = (
    (
        'sql_comment',
        re.compile(r'--|/\*|\*/|%2D%2D|(?<![A-Za-z0-9_])#(?![A-Za-z0-9_])'),
    ),
    (
        'stacked_statement',
        re.compile(
            r';\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|UNION|TRUNCATE|GRANT|REVOKE|EXEC)\b',
            re.I,
        ),
    ),
    (
        'union_select',
        re.compile(r'\bUNION\b[\s/*]+(?:ALL\s+)?SELECT\b', re.I),
    ),
    (
        'boolean_tautology',
        re.compile(
            r"\b(?:OR|AND)\b\s*(?:'\d*'\s*=\s*'\d*'|\d+\s*=\s*\d+|\"[^\"]*\"\s*=\s*\"|'[^']*'\s*=\s*')",
            re.I,
        ),
    ),
    (
        'drop_object',
        re.compile(r'\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b', re.I),
    ),
    (
        'delete_without_where',
        re.compile(r'\bDELETE\s+FROM\b(?![^;]*\bWHERE\b)'),
    ),
    (
        'privilege_change',
        re.compile(r'\b(?:GRANT|REVOKE)\b'),
    ),
    (
        'dangerous_procedure',
        re.compile(r'\b(?:xp_cmdshell|sp_executesql|pg_sleep|sleep|benchmark)\s*\(|\bwaitfor\s+delay', re.I),
    ),
    (
        'url_encoded_payload',
        re.compile(r'%(?:27|23|3B|2D%2D|7C)', re.I),
    ),
)


def find_suspicious_tokens(sql):
    """Return the names of injection signatures found in a SQL statement."""
    if not sql:
        return ()
    return tuple(name for name, pattern in _SUSPICION_RULES if pattern.search(sql))


def assert_safe_statement(sql):
    """Verify a raw SQL statement before executing it; raise if unsafe.

    Use this for any raw SQL (migrations, maintenance scripts) before passing
    it to ``db.session.execute(text(sql))``.
    """
    findings = find_suspicious_tokens(sql)
    if findings:
        raise SQLInjectionAttempt(
            'Unsafe SQL pattern(s) %s in statement: %s' % (', '.join(findings), sql)
        )
    return sql


def safe_order_column(user_value, allowed_columns, param_name='order'):
    """Resolve a user-supplied sort key against an allow-list.

    Column identifiers cannot be bound as query parameters in SQL, so any
    dynamic ORDER BY / LIMIT column must come from an allow-list.  Returns the
    mapped column (e.g. ``Record.date``) or raises ``SQLInjectionAttempt``.
    """
    if not isinstance(user_value, str) or user_value not in allowed_columns:
        raise SQLInjectionAttempt(
            'Invalid value %r for %s: identifiers cannot be bound as query '
            'parameters and must be allow-listed.' % (user_value, param_name)
        )
    return allowed_columns[user_value]


# ---------------------------------------------------------------------------
# Layer 2 - engine-wide query interceptor
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryRecord:
    """Audit entry for one statement sent to the database driver."""

    statement: str
    param_count: int
    suspicious: tuple
    timestamp: str

    @property
    def parameterized(self):
        return self.param_count > 0


class SqlGuard:
    """Intercepts every statement executed through SQLAlchemy and verifies it.

    Attach with ``SqlGuard(app, db)`` (done automatically by ``create_app``).
    Inspected statements are kept in an audit log; those
    matching an injection signature are logged and, in ``block`` mode
    (default), aborted with ``SQLInjectionAttempt`` before reaching the
    database.

    Configuration keys on the Flask app:

    ``SQL_GUARD_ENABLED``
        Master switch (default ``True``).
    ``SQL_GUARD_MODE``
        ``'block'`` (default) raises ``SQLInjectionAttempt`` on a signature
        hit; ``'log'`` only records it.
    ``SQL_GUARD_MAX_AUDIT``
        Maximum number of audit records kept in memory (default 5000).
    """

    def __init__(self, app=None, db=None):
        self.app = None
        self.db = None
        self.audit_log = deque()
        self._lock = threading.Lock()
        if app is not None:
            self.init_app(app, db)

    def init_app(self, app, db):
        if db is None or not hasattr(db, 'engine'):
            raise ValueError('SqlGuard requires the Flask-SQLAlchemy db object')
        self.app = app
        self.db = db
        app.extensions['sql_guard'] = self
        self.audit_log = deque(maxlen=int(app.config.get('SQL_GUARD_MAX_AUDIT', 5000)))

        @app.errorhandler(SQLInjectionAttempt)
        def _handle_sql_injection_attempt(error):
            app.logger.error('SQL injection attempt blocked: %s', error)
            return 'Bad request: your input contained an unsafe SQL pattern.', 400

        with app.app_context():
            engine = db.engine
            if not event.contains(engine, 'before_cursor_execute', self._before_cursor_execute):
                # weak=False: the listener is bound to this guard instance,
                # which lives as long as the app (app.extensions['sql_guard']).
                event.listen(engine, 'before_cursor_execute', self._before_cursor_execute, weak=False)

    # -- interceptor --------------------------------------------------------
    def _before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        if not self.app.config.get('SQL_GUARD_ENABLED', True):
            return

        suspicious = find_suspicious_tokens(statement)

        # Framework DDL (CREATE/DROP TABLE emitted by create_all()/drop_all()
        # from model metadata) is generated by SQLAlchemy from code-defined
        # table names, never from user input, so signature hits on DDL
        # compiler statements are not enforced.  Raw text('DROP ...')
        # executes compile as regular SQL statements and stay fully checked.
        if isinstance(getattr(context, 'compiled', None), DDLCompiler):
            suspicious = ()

        record = QueryRecord(
            statement=statement,
            param_count=len(parameters) if parameters is not None else 0,
            suspicious=suspicious,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self.audit_log.append(record)

        if suspicious:
            message = 'Unsafe SQL pattern(s) %s in statement: %s' % (
                ', '.join(suspicious),
                statement,
            )
            self.app.logger.warning('SQL guard: %s', message)
            if self.app.config.get('SQL_GUARD_MODE', 'block') == 'block':
                raise SQLInjectionAttempt(message)

    # -- audit access -------------------------------------------------------
    @property
    def violations(self):
        with self._lock:
            return [record for record in self.audit_log if record.suspicious]

    @property
    def statement_count(self):
        with self._lock:
            return len(self.audit_log)

    def clear(self):
        with self._lock:
            self.audit_log.clear()


# ---------------------------------------------------------------------------
# Layer 3 - static AST verification of the whole codebase
# ---------------------------------------------------------------------------
_RAW_SQL_FUNCS = {'text', 'execute', 'executemany', 'execute_sql'}

_DYNAMIC_ARG_HINTS = {'dedent', 'join', 'strip', 'replace', 'lower', 'upper', 'split'}


@dataclass(frozen=True)
class ScanViolation:
    """One unsafe raw-SQL construction found by the static scanner."""

    filename: str
    lineno: int
    call: str
    issue: str

    def __str__(self):
        return '%s:%d  %s()  ->  %s' % (self.filename, self.lineno, self.call, self.issue)


@dataclass
class ScanResult:
    """Outcome of scanning one or more source trees."""

    files_scanned: int = 0
    raw_sql_call_sites: int = 0
    violations: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.violations


def _call_qualified_name(func):
    """Return e.g. 'db.session.execute' for the callee of a Call node."""
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    elif isinstance(func, ast.Call):
        parts.append('<call>')
    else:
        return ''
    return '.'.join(reversed(parts))


def _describe_dynamic_arg(arg):
    """Explain why a raw-SQL argument is unsafe, or return None if it is fine."""
    if isinstance(arg, ast.JoinedStr):
        return 'f-string interpolation inside raw SQL'
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod)):
        return 'string concatenation or %-formatting inside raw SQL'
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == 'format':
        return 'str.format() inside raw SQL'
    if isinstance(arg, ast.IfExp):
        return 'conditional expression inside raw SQL'
    if isinstance(arg, ast.Name):
        return 'unparameterised variable passed to raw SQL (use a literal string with bound parameters)'
    if isinstance(arg, ast.Call):
        tail = getattr(arg.func, 'attr', None) or getattr(arg.func, 'id', '')
        if tail in _DYNAMIC_ARG_HINTS:
            return 'dynamically built SQL string'
    return None


def _scan_tree(tree, filename):
    violations = []
    call_sites = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_qualified_name(node.func)
        tail = name.rsplit('.', 1)[-1] if name else ''
        if tail not in _RAW_SQL_FUNCS:
            continue
        call_sites += 1
        for arg in node.args:
            issue = _describe_dynamic_arg(arg)
            if issue:
                violations.append(
                    ScanViolation(filename, getattr(arg, 'lineno', node.lineno), name, issue)
                )
    return violations, call_sites


def scan_source(source, filename='<string>'):
    """Statically verify every raw-SQL call site in a piece of Python source."""
    tree = ast.parse(source, filename=filename)
    violations, _ = _scan_tree(tree, filename)
    return violations


_SKIP_DIRS = {'__pycache__', '.git', '.pytest_cache', 'instance', '.venv', 'venv', 'node_modules'}


def iter_python_files(paths):
    for path in paths:
        if os.path.isfile(path) and path.endswith('.py'):
            yield path
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                for filename in sorted(files):
                    if filename.endswith('.py'):
                        yield os.path.join(root, filename)


def verify_project(paths=('app',)):
    """Verify every raw-SQL call site in the given files/directories."""
    result = ScanResult()
    for filename in iter_python_files(paths):
        with open(filename, encoding='utf-8') as handle:
            source = handle.read()
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as error:
            result.violations.append(ScanViolation(filename, error.lineno or 0, '<parse>', str(error)))
            continue
        result.files_scanned += 1
        violations, call_sites = _scan_tree(tree, filename)
        result.raw_sql_call_sites += call_sites
        result.violations.extend(violations)
    return result
