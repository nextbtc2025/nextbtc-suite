import sqlite3
import unittest
from pathlib import Path

class ExplorerTransactionIndexTests(unittest.TestCase):
    def test_required_covering_indexes_are_in_schema(self):
        schema = (Path(__file__).resolve().parents[1] / 'indexer.py').read_text(encoding='utf-8')
        for name in ('idx_txs_explorer_order', 'idx_outputs_coinbase_txid', 'idx_outputs_spent_by_value', 'idx_outputs_txid_value'):
            self.assertIn(name, schema)

    def test_sqlite_can_use_explorer_order_index(self):
        db = sqlite3.connect(':memory:')
        db.executescript('''
            CREATE TABLE txs(txid TEXT PRIMARY KEY,height INTEGER,block_hash TEXT,timestamp INTEGER);
            CREATE INDEX idx_txs_explorer_order ON txs(height DESC,timestamp DESC,txid DESC,block_hash);
            INSERT INTO txs VALUES('a',1,'h',1);
        ''')
        plan = ' '.join(str(x) for row in db.execute(
            'EXPLAIN QUERY PLAN SELECT txid,height,block_hash,timestamp FROM txs WHERE height<=? ORDER BY height DESC,timestamp DESC,txid DESC LIMIT ? OFFSET ?',
            (1,25,0)) for x in row)
        self.assertIn('idx_txs_explorer_order', plan)
        db.close()

if __name__ == '__main__':
    unittest.main()
