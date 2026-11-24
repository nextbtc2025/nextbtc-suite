# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import os, tempfile, unittest
from indexer import Indexer

class DummyRPC: pass

class TestMempoolHistory(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.idx=Indexer(self.path,DummyRPC())

    def tearDown(self):
        self.idx.db.close()
        try: os.unlink(self.path)
        except OSError: pass

    def test_schema_migration_and_snapshot_persistence(self):
        snap={'updated':1700000000,'coverage_complete':True,'txs':{
            'a'*64:{'vsize':100,'fee_sats':250,'time':1700000000},
            'b'*64:{'vsize':200,'fee_sats':100,'time':1700000000}}}
        self.idx.record_mempool_snapshot(snap)
        row=self.idx.db.execute('SELECT sampled_at,tx_count,total_vsize,total_fee_sats FROM mempool_history').fetchone()
        self.assertEqual(tuple(row),(1700000000,2,300,350))

    def test_same_second_retry_replaces_sample(self):
        self.idx.record_mempool_snapshot({'updated':1700000000,'coverage_complete':True,'txs':{'a'*64:{'vsize':100,'fee_sats':100}}})
        self.idx.record_mempool_snapshot({'updated':1700000000,'coverage_complete':True,'txs':{'b'*64:{'vsize':200,'fee_sats':400}}})
        rows=self.idx.db.execute('SELECT sampled_at,tx_count,total_vsize,total_fee_sats FROM mempool_history').fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(tuple(rows[0]),(1700000000,1,200,400))

    def test_incomplete_snapshot_is_not_persisted(self):
        with self.assertRaises(ValueError):
            self.idx.record_mempool_snapshot({'updated':1700000000,'coverage_complete':False,'txs':{}})
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM mempool_history').fetchone()[0],0)

    def test_fee_histogram_has_overflow_bucket_and_sums_all_transactions(self):
        self.idx.record_mempool_snapshot({'updated':1700000000,'coverage_complete':True,'txs':{
            'a'*64:{'vsize':100,'fee_sats':100},
            'b'*64:{'vsize':1,'fee_sats':2000000},
            'c'*64:{'vsize':100,'fee_sats':0}}})
        import json
        raw=self.idx.db.execute('SELECT fee_bins_json FROM mempool_history').fetchone()[0]
        bins=json.loads(raw)
        self.assertEqual(sum(x['count'] for x in bins),3)
        self.assertEqual(bins[-1]['count'],1)

    def test_errored_snapshot_is_not_persisted(self):
        with self.assertRaises(ValueError):
            self.idx.record_mempool_snapshot({'error':'rpc failed','coverage_complete':True,'txs':{}})
        self.assertEqual(self.idx.db.execute('SELECT COUNT(*) FROM mempool_history').fetchone()[0],0)

if __name__=='__main__': unittest.main()
