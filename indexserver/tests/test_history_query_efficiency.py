# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer

class NoRpc:
    def call(self, *args):
        raise AssertionError('unexpected RPC')

class TestHistoryQuery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.idx=Indexer(Path(self.tmp.name)/'index.db',NoRpc())
        self.address='bc1q'+'a'*38
        with self.idx.db:
            self.idx.db.execute("INSERT INTO blocks VALUES(0,?,?,?)",('f'*64,'0'*64,1000))
            self.idx.db.execute("INSERT INTO txs VALUES(?,?,?,?)",('1'*64,0,'f'*64,1000))
            self.idx.db.execute("INSERT INTO activity VALUES(?,?,?)",(self.address,'1'*64,0))
            self.idx.db.execute("INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)",('1'*64,0,0,500,'51',self.address))
            self.idx.db.execute("INSERT INTO txs VALUES(?,?,?,?)",('2'*64,1,'e'*64,1150))
            self.idx.db.execute("INSERT INTO activity VALUES(?,?,?)",(self.address,'2'*64,1))
            self.idx.db.execute("UPDATE outputs SET spent_by=?,spent_height=1 WHERE txid=? AND vout=0",('2'*64,'1'*64))
            self.idx.db.execute("INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)",('2'*64,0,1,450,'51',self.address))

    def tearDown(self):
        self.idx.db.close(); self.tmp.cleanup()

    def test_history_returns_correct_credit_debit_and_net(self):
        rows=self.idx.history(self.address,10,0)
        self.assertEqual([r['txid'] for r in rows],['2'*64,'1'*64])
        self.assertEqual((rows[0]['received_sats'],rows[0]['sent_sats'],rows[0]['net_sats']),(450,500,-50))
        self.assertEqual((rows[1]['received_sats'],rows[1]['sent_sats'],rows[1]['net_sats']),(500,0,500))

    def test_history_pagination_is_stable(self):
        first=self.idx.history(self.address,1,0)
        second=self.idx.history(self.address,1,1)
        self.assertEqual(first[0]['txid'],'2'*64)
        self.assertEqual(second[0]['txid'],'1'*64)

if __name__=='__main__': unittest.main()
