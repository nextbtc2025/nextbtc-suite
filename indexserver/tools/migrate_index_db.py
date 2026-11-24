# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Apply additive Index Server schema migrations to a database copy.

This command is intentionally additive: it executes the canonical CREATE
TABLE/INDEX IF NOT EXISTS schema and never rewrites or deletes indexed rows.
For acceptance, always run it against a verified SQLite backup, not production.
"""
import argparse
import json
import sqlite3
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexer import SCHEMA


def migrate_database(path):
    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    db = sqlite3.connect(str(target), timeout=30)
    try:
        db.execute('PRAGMA busy_timeout=30000')
        before = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db.executescript(SCHEMA)
        db.commit()
        after = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError(f'SQLite integrity_check failed after migration: {integrity}')
        return {
            'database': str(target),
            'ok': True,
            'tables_before': sorted(before),
            'tables_after': sorted(after),
            'tables_added': sorted(after - before),
            'integrity_check': integrity,
            'migration': 'additive_schema_if_not_exists',
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    args = parser.parse_args()
    report = migrate_database(args.database)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
