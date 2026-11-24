# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer

class TestDatabasePath(unittest.TestCase):
    def test_missing_database_parent_is_created(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            path=Path(tmp.name)/'nested'/'data'/'index.db'
            idx=Indexer(path,object())
            self.assertTrue(path.is_file())
            idx.db.close()
        finally:tmp.cleanup()

if __name__=='__main__':unittest.main()
