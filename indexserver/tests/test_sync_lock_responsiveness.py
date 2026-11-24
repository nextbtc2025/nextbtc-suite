# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import threading
import unittest
from pathlib import Path
from indexer import Indexer

class RpcWithLockProbe:
    def __init__(self): self.indexer=None; self.reader_acquired_during_fetch=False
    def call(self,method,*params):
        if method=='getblockcount': return 0
        if method=='getblockhash': return 'a'*64
        if method=='getblock':
            acquired=[]
            def probe():
                ok=self.indexer.lock.acquire(timeout=0.5)
                acquired.append(ok)
                if ok:self.indexer.lock.release()
            t=threading.Thread(target=probe);t.start();t.join()
            self.reader_acquired_during_fetch=bool(acquired and acquired[0])
            return {'hash':'a'*64,'previousblockhash':'0'*64,'time':1000,
                    'tx':[{'txid':'b'*64,'vin':[{'coinbase':'00'}],
                           'vout':[{'n':0,'value':50,'scriptPubKey':{'hex':'51','address':'bc1q'+'a'*38}}]}]}
        raise AssertionError(method)

class TestSyncLock(unittest.TestCase):
    def test_core_rpc_fetch_does_not_hold_shared_database_lock(self):
        tmp=tempfile.TemporaryDirectory(); rpc=RpcWithLockProbe()
        try:
            idx=Indexer(Path(tmp.name)/'index.db',rpc);rpc.indexer=idx
            self.assertEqual(idx.sync_once(max_blocks=1,commit_every=1),1)
            self.assertTrue(rpc.reader_acquired_during_fetch)
            self.assertEqual(idx.tip()['height'],0)
            idx.db.close()
        finally: tmp.cleanup()

    def test_mempool_sampler_cannot_commit_a_partial_block_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Indexer(Path(directory)/'index.db', object())
            started = threading.Event()
            finished = threading.Event()

            def record():
                started.set()
                index.record_mempool_snapshot({'coverage_complete':True, 'txs':{}})
                finished.set()

            with index.lock:
                index.db.execute("INSERT INTO meta VALUES('pending', 'value')")
                worker = threading.Thread(target=record)
                worker.start()
                self.assertTrue(started.wait(2))
                self.assertFalse(finished.wait(0.1))
                index.db.rollback()
            worker.join(2)
            self.assertTrue(finished.is_set())
            self.assertIsNone(index.db.execute("SELECT v FROM meta WHERE k='pending'").fetchone())
            index.db.close()

if __name__=='__main__': unittest.main()
