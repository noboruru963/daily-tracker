#!/usr/bin/env python3
"""Project-wide SQL injection verification report.

Statically verifies that every raw-SQL call site in the scanned trees uses
literal SQL strings with bound parameters (never f-strings, concatenation,
``str.format``, ``%`` formatting or bare variables).

Usage:
    python verify_queries.py              # scan the app package
    python verify_queries.py app tests    # scan extra trees
"""
import sys

from app.security.sql_guard import verify_project


def main(argv=None):
    roots = argv if argv is not None else sys.argv[1:]
    roots = roots or ['app']

    result = verify_project(roots)

    print('SQL injection verification')
    print('  trees scanned : %s' % ', '.join(roots))
    print('  python files  : %d' % result.files_scanned)
    print('  raw SQL sites : %d (text()/execute() call sites)' % result.raw_sql_call_sites)

    if result.violations:
        print()
        print('[FAIL] %d unsafe query construction(s) found:' % len(result.violations))
        for violation in result.violations:
            print('  - %s' % violation)
        return 1

    print()
    print('[OK] Every raw SQL call site uses a literal string with bound parameters.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
