# SQL Injection Prevention

The Daily Tracker app protects every database query with a three-layer SQL
injection prevention system, implemented in `app/security/sql_guard.py`.

## Layer 1 — Bound parameters (primary defence)

All application queries go through the SQLAlchemy ORM (`Model.query.filter_by()`,
`.filter(Model.col == value)`, `.in_([...])`). SQLAlchemy compiles these into
statements with placeholders and sends user data exclusively as *bound
parameters*, so payload characters (quotes, semicolons, comments) are inert
data and can never change the meaning of a statement.

Where raw SQL is required, it must use `sqlalchemy.text()` with named binds:

```python
db.session.execute(text('SELECT * FROM users WHERE username = :name'), {'name': username})
```

Column identifiers cannot be bound as parameters. Any dynamic `ORDER BY` /
sort key must be resolved through an allow-list:

```python
from app.security import safe_order_column

column = safe_order_column(request.args.get('order'), {'date': Record.date, 'value': Record.numerical_value})
query = query.order_by(column.desc())
```

## Layer 2 — Runtime statement verification (`SqlGuard`)

`create_app()` attaches a `SqlGuard` to the SQLAlchemy engine via the
`before_cursor_execute` event. Every statement sent to the database driver is
checked against injection signatures:

| Rule                    | Detects                                                    |
|-------------------------|------------------------------------------------------------|
| `sql_comment`           | `--`, `/* */`, `#` and URL-encoded comment probes          |
| `stacked_statement`     | `; DROP TABLE ...`, `; DELETE ...` chained statements      |
| `union_select`          | `UNION ... SELECT` column-probing payloads                 |
| `boolean_tautology`     | `' OR '1'='1`, `OR 1=1`, `" OR "a"="a`                     |
| `drop_object`           | `DROP/TRUNCATE TABLE/DATABASE/SCHEMA/INDEX/VIEW`           |
| `delete_without_where`  | `DELETE FROM` with no `WHERE` clause                       |
| `privilege_change`      | `GRANT` / `REVOKE`                                         |
| `dangerous_procedure`   | `xp_cmdshell`, `sleep()`, `benchmark()`, `WAITFOR DELAY`   |
| `url_encoded_payload`   | `%27`, `%23`, `%3B`, `%2D%2D`, `%7C`                       |

Because safe code never embeds user data in the statement text, any hit is
either an injection attempt or unsafe string-built SQL. Hits are logged and,
in `block` mode (default), aborted with `SQLInjectionAttempt` before reaching
the database. The HTTP error handler returns a generic `400`.

Framework DDL emitted by `create_all()` / `drop_all()` is compiled from model
metadata (never user input) and is therefore recorded but not enforced; raw
`text('DROP TABLE ...')` remains fully checked.

### Configuration

| Key                     | Default | Meaning                                     |
|-------------------------|---------|---------------------------------------------|
| `SQL_GUARD_ENABLED`     | `True`  | Master switch                               |
| `SQL_GUARD_MODE`        | `'block'` | `'block'` raises, `'log'` only records     |
| `SQL_GUARD_MAX_AUDIT`   | `5000`  | Max audit records kept in memory            |

### Audit log

Every executed statement is recorded (statement text, parameter count,
timestamp — parameter *values* are deliberately not stored):

```python
guard = current_app.extensions['sql_guard']
guard.statement_count      # number of audited statements
guard.violations           # statements that matched a signature
guard.clear()
```

### Verifying a raw statement manually

```python
from app.security import assert_safe_statement

assert_safe_statement('ALTER TABLE records ADD COLUMN sort_order INTEGER DEFAULT 0')
db.session.execute(text('ALTER TABLE records ADD COLUMN sort_order INTEGER DEFAULT 0'))
```

## Layer 3 — Static verification of every query

An AST scanner walks the codebase and fails any raw-SQL call site
(`text()`, `execute()`, `executemany()`) whose SQL is built from:

- f-strings (`text(f"... {user_input}")`)
- string concatenation (`"... " + user_input`)
- `%` formatting (`"... %s" % user_input`)
- `str.format()` (`"{}".format(user_input)`)
- bare variables (`execute(sql_variable)`)

Verify the whole project any time:

```
python verify_queries.py             # scans the app/ package
python verify_queries.py app tests   # scan extra trees
```

The scanner is also enforced in the test suite
(`tests/unit/test_sql_guard.py::test_entire_app_codebase_is_free_of_dynamic_sql`).

## Tests

`tests/unit/test_sql_guard.py` verifies all three layers:

- classic login-bypass / stacked-query / UNION payloads through real routes
  are stored as inert data and cannot authenticate or damage tables
- raw injected statements are blocked at the driver; the same payload in a
  bound parameter executes safely and matches nothing
- an end-to-end flow (register → habit → record → community post → calorie
  log) submits injection payloads in every field and asserts that **every**
  statement executed during the flow was verified, parameterized, and never
  contained the payload in its SQL text
