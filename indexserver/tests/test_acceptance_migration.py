# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import sqlite3
from pathlib import Path

from indexer import SCHEMA
from tools.migrate_index_db import migrate_database
from tools.audit_index_db import audit
from tools.run_full_acceptance import write_dwg_skipped_report


def test_additive_migration_adds_mempool_tables_without_touching_chain_rows(tmp_path):
    db_path = tmp_path / 'legacy.db'
    db = sqlite3.connect(db_path)
    # Minimal legacy schema representative of an older wallet index database.
    db.executescript('''
        CREATE TABLE blocks(height INTEGER PRIMARY KEY, hash TEXT NOT NULL UNIQUE, prev_hash TEXT NOT NULL, timestamp INTEGER NOT NULL);
        CREATE TABLE txs(txid TEXT PRIMARY KEY, height INTEGER NOT NULL, block_hash TEXT NOT NULL, timestamp INTEGER NOT NULL);
        CREATE TABLE outputs(txid TEXT NOT NULL, vout INTEGER NOT NULL, height INTEGER NOT NULL, value INTEGER NOT NULL, script TEXT NOT NULL, address TEXT, coinbase INTEGER NOT NULL DEFAULT 0, spent_by TEXT, spent_height INTEGER, PRIMARY KEY(txid,vout));
        CREATE TABLE activity(address TEXT NOT NULL, txid TEXT NOT NULL, height INTEGER NOT NULL, PRIMARY KEY(address,txid));
        INSERT INTO blocks VALUES(0, 'genesis', '0000', 1);
    ''')
    db.commit()
    db.close()

    result = migrate_database(db_path)
    assert result['ok'] is True
    assert set(result['tables_added']) >= {'mempool_history', 'mempool_events'}

    audit_result = audit(db_path)
    assert audit_result['ok'] is True
    assert audit_result['block_count'] == 1


def test_migration_is_idempotent(tmp_path):
    db_path = tmp_path / 'index.db'
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    db.commit()
    db.close()

    first = migrate_database(db_path)
    second = migrate_database(db_path)
    assert first['ok'] and second['ok']
    assert second['tables_added'] == []


def test_offline_dwg_skip_is_written_as_machine_readable_report(tmp_path):
    report_path = tmp_path / 'dwg.json'
    report = write_dwg_skipped_report(report_path, 'Core RPC unavailable')
    assert report['status'] == 'SKIPPED'
    assert report['historical_matches'] is None
    assert report['getblocktemplate_match'] is None
    assert 'Core RPC unavailable' in report_path.read_text(encoding='utf-8')
