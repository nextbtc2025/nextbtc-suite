# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import sqlite3
import tempfile
import unittest
from pathlib import Path

from indexer import SCHEMA

class TestExplorerSQLiteIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = sqlite3.connect(str(Path(self.tmp.name) / 'test.db'))
        self.db.executescript(SCHEMA)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _plan(self, sql, params):
        return ' '.join(str(row[3]) for row in self.db.execute('EXPLAIN QUERY PLAN ' + sql, params))

    def test_unspent_address_query_uses_partial_index(self):
        plan = self._plan(
            'SELECT txid,vout,value,height,script,coinbase FROM outputs WHERE address=? AND spent_by IS NULL ORDER BY height,txid,vout LIMIT ? OFFSET ?',
            ('address-1', 100, 0))
        self.assertIn('idx_outputs_address_unspent_height', plan)

    def test_address_history_lookup_has_address_txid_index(self):
        plan = self._plan('SELECT txid FROM outputs WHERE address=?', ('address-1',))
        self.assertIn('idx_outputs_address_txid', plan)

    def test_spent_address_statistics_uses_partial_index(self):
        plan = self._plan('SELECT COALESCE(SUM(o.value),0) FROM outputs o WHERE o.address=? AND o.spent_by IS NOT NULL', ('address-1',))
        self.assertIn('idx_outputs_address_spentby', plan)

    def test_address_history_credit_debit_subqueries_use_indexes(self):
        credit=self._plan('SELECT SUM(value) FROM outputs WHERE txid=? AND address=?',('a'*64,'address-1'))
        debit=self._plan('SELECT SUM(value) FROM outputs WHERE spent_by=? AND address=?',('b'*64,'address-1'))
        self.assertIn('idx_outputs_address_txid',credit)
        self.assertIn('idx_outputs_address_spentby',debit)

    def test_timestamp_history_index_exists(self):
        indexes = {row[1] for row in self.db.execute("PRAGMA index_list('txs')")}
        self.assertIn('idx_txs_timestamp', indexes)

    def test_existing_schema_migration_is_idempotent(self):
        self.db.executescript(SCHEMA)
        self.db.commit()
        indexes = {row[1] for row in self.db.execute("PRAGMA index_list('outputs')")}
        self.assertTrue({'idx_outputs_address_unspent_height','idx_outputs_address_txid','idx_outputs_address_spentby'}.issubset(indexes))

if __name__ == '__main__':
    unittest.main()
