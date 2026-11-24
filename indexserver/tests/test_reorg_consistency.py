# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path

from indexer import Indexer


class NoRpc:
    def call(self, method, *params):
        raise AssertionError(f'unexpected RPC: {method}')


def coinbase(txid, address, value=50):
    return {'txid': txid, 'vin': [{'coinbase': '00'}],
            'vout': [{'n': 0, 'value': value,
                      'scriptPubKey': {'hex': '51', 'address': address}}]}


def spend(txid, prev_txid, address, value=49):
    return {'txid': txid, 'vin': [{'txid': prev_txid, 'vout': 0}],
            'vout': [{'n': 0, 'value': value,
                      'scriptPubKey': {'hex': '51', 'address': address}}]}


class TestReorgConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.idx = Indexer(Path(self.tmp.name) / 'index.db', NoRpc())

    def tearDown(self):
        self.idx.db.close()
        self.tmp.cleanup()

    def apply(self, height, blockhash, prev, txs, timestamp):
        self.idx.apply(height, blockhash, {
            'previousblockhash': prev, 'time': timestamp, 'tx': txs
        })

    def test_rewind_restores_spent_output_and_removes_orphan_activity(self):
        a, b = 'bc1q' + 'a' * 38, 'bc1q' + 'b' * 38
        genesis_tx, spend_tx = '1' * 64, '2' * 64
        self.apply(0, 'a' * 64, '0' * 64, [coinbase(genesis_tx, a)], 1000)
        self.apply(1, 'b' * 64, 'a' * 64, [spend(spend_tx, genesis_tx, b)], 1150)
        self.assertEqual(self.idx.address_info(a, 1)['confirmed_sats'], 0)
        self.assertEqual(self.idx.address_info(b, 1)['confirmed_sats'], 49 * 100000000)
        self.idx.rewind()
        self.assertEqual(self.idx.address_info(a, 0)['confirmed_sats'], 50 * 100000000)
        self.assertEqual(self.idx.address_info(b, 0)['confirmed_sats'], 0)
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM txs WHERE txid=?', (spend_tx,)).fetchone()[0], 0)
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM activity WHERE txid=?', (spend_tx,)).fetchone()[0], 0)

    def test_multiple_rewinds_restore_each_canonical_state(self):
        a, b, c = ('bc1q' + x * 38 for x in 'abc')
        tx0, tx1, tx2 = '3' * 64, '4' * 64, '5' * 64
        self.apply(0, 'a' * 64, '0' * 64, [coinbase(tx0, a)], 1000)
        self.apply(1, 'b' * 64, 'a' * 64, [spend(tx1, tx0, b)], 1150)
        self.apply(2, 'c' * 64, 'b' * 64, [spend(tx2, tx1, c, 48)], 1300)
        self.idx.rewind()
        self.assertEqual(self.idx.address_info(b, 1)['confirmed_sats'], 49 * 100000000)
        self.idx.rewind()
        self.assertEqual(self.idx.address_info(a, 0)['confirmed_sats'], 50 * 100000000)
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 1)

    def test_failed_block_apply_is_atomic(self):
        tx0 = '6' * 64
        self.apply(0, 'a' * 64, '0' * 64, [coinbase(tx0, 'bc1q' + 'd' * 38)], 1000)
        bad = spend('7' * 64, 'f' * 64, 'bc1q' + 'e' * 38)
        with self.assertRaises(RuntimeError):
            self.apply(1, 'b' * 64, 'a' * 64, [bad], 1150)
        self.assertEqual(self.idx.tip()['height'], 0)
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM txs WHERE txid=?', ('7' * 64,)).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
