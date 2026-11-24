# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer
from tools.audit_index_db import audit

class TestAudit(unittest.TestCase):
    def test_clean_index_passes_read_only_audit(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            path=Path(tmp.name)/'index.db'
            idx=Indexer(path,object())
            with idx.db:
                idx.db.execute('INSERT INTO blocks VALUES(0,?,?,?)',('a'*64,'0'*64,1000))
                idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',('b'*64,0,'a'*64,1000))
                idx.db.execute('INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)',
                               ('b'*64,0,0,100,'51','bc1q'+'a'*38))
                idx.db.execute('INSERT INTO activity VALUES(?,?,?)',('bc1q'+'a'*38,'b'*64,0))
            idx.db.close()
            report=audit(path)
            self.assertTrue(report['ok'],report['issues'])
        finally: tmp.cleanup()

    def test_orphan_activity_is_reported(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            path=Path(tmp.name)/'index.db';idx=Indexer(path,object())
            with idx.db: idx.db.execute('INSERT INTO activity VALUES(?,?,?)',('bc1q'+'a'*38,'f'*64,10))
            idx.db.close()
            report=audit(path)
            self.assertFalse(report['ok'])
            self.assertTrue(any(x['check']=='activity_missing_tx' for x in report['issues']))
        finally: tmp.cleanup()

if __name__=='__main__': unittest.main()
