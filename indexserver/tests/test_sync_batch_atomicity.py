# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer

GEN='a'*64; B1='b'*64
class BatchRpc:
    def call(self,method,*params):
        if method=='getblockcount': return 1
        if method=='getblockhash': return GEN if params[0]==0 else B1
        if method=='getblock':
            if params[0]==GEN:
                return {'hash':GEN,'previousblockhash':'0'*64,'time':1000,
                        'tx':[{'txid':'1'*64,'vin':[{'coinbase':'00'}],
                               'vout':[{'n':0,'value':50,'scriptPubKey':{'hex':'51','address':'bc1q'+'a'*38}}]}]}
            raise RuntimeError('simulated RPC interruption before commit')
        raise AssertionError(method)

class TestSyncBatchAtomicity(unittest.TestCase):
    def test_rpc_failure_while_prefetching_group_commits_nothing(self):
        tmp=tempfile.TemporaryDirectory()
        try:
            idx=Indexer(Path(tmp.name)/'index.db',BatchRpc())
            with self.assertRaises(RuntimeError): idx.sync_once(max_blocks=2,commit_every=2)
            self.assertIsNone(idx.tip())
            self.assertEqual(idx.db.execute('SELECT COUNT(*) FROM txs').fetchone()[0],0)
            idx.db.close()
        finally: tmp.cleanup()

if __name__=='__main__': unittest.main()
