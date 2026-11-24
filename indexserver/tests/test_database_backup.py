# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer
from tools.backup_index_db import backup_database

class TestBackup(unittest.TestCase):
    def test_sqlite_backup_api_produces_integrity_checked_copy(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            source=Path(tmp.name)/'index.db';dest=Path(tmp.name)/'backup.db'
            idx=Indexer(source,object())
            with idx.db:
                idx.db.execute('INSERT INTO blocks VALUES(0,?,?,?)',('a'*64,'0'*64,1000))
            report=backup_database(source,dest)
            self.assertEqual(report['integrity_check'],'ok')
            import sqlite3
            db=sqlite3.connect(dest)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0],1)
            db.close();idx.db.close()
        finally:tmp.cleanup()

    def test_backup_refuses_to_overwrite_existing_destination(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            source=Path(tmp.name)/'index.db';dest=Path(tmp.name)/'backup.db'
            idx=Indexer(source,object());dest.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):backup_database(source,dest)
            self.assertEqual(dest.read_bytes(),b'keep')
            idx.db.close()
        finally:tmp.cleanup()

if __name__=='__main__':unittest.main()
