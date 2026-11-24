# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import tempfile
import unittest
from pathlib import Path
from indexer import Indexer
from mempool import MempoolTracker

class DynamicRPC:
    def __init__(self, entries, txs): self.entries=entries; self.txs=txs
    def call(self, method, *params):
        if method=='getrawmempool': return self.entries
        if method=='getrawtransaction': return self.txs[params[0]]
        raise AssertionError(method)

def make_tx(txid, prev, address):
    return {'txid':txid,'vin':[{'txid':prev,'vout':0}],
            'vout':[{'n':0,'value':0.000009,'scriptPubKey':{'hex':'0014','address':address}}]}

class TestMempoolEvent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.idx=Indexer(Path(self.tmp.name)/'index.db',object())
    def tearDown(self):
        self.idx.db.close(); self.tmp.cleanup()

    def test_replacement_is_detected_by_conflicting_prevout(self):
        prev='a'*64; old='b'*64; new='c'*64
        address='bc1q'+'a'*38
        rpc=DynamicRPC({old:{'time':100,'vsize':100,'fees':{'base':0.000001}}},{old:make_tx(old,prev,address)})
        tracker=MempoolTracker(rpc,max_txs=10)
        tracker.refresh()
        self.assertEqual(tracker.get()['events'],[])  # first poll establishes baseline
        rpc.entries={new:{'time':101,'vsize':110,'fees':{'base':0.000002}}}
        rpc.txs={new:make_tx(new,prev,address)}
        tracker.refresh()
        events=tracker.get()['events']
        self.assertTrue(any(e['txid']==old and e['event_type']=='replaced' and e['replacement_txid']==new for e in events))

    def test_events_are_persisted_and_bounded_queryable(self):
        snap={'updated':1700000000,'coverage_complete':True,'txs':{},'events':[
            {'txid':'d'*64,'event_type':'replaced','replacement_txid':'e'*64},
            {'txid':'f'*64,'event_type':'removed_unknown'}]}
        self.idx.record_mempool_snapshot(snap)
        rows=self.idx.db.execute('SELECT txid,event_type,replacement_txid FROM mempool_events ORDER BY id').fetchall()
        self.assertEqual(len(rows),2)
        self.assertEqual(tuple(rows[0]),('d'*64,'replaced','e'*64))
        self.assertEqual(tuple(rows[1]),('f'*64,'removed_unknown',None))


    def test_same_second_event_retry_replaces_batch_without_duplicates(self):
        base={'updated':1700000001,'coverage_complete':True,'txs':{}}
        first={**base,'events':[{'txid':'1'*64,'event_type':'removed_unknown'}]}
        retry={**base,'events':[{'txid':'2'*64,'event_type':'replaced','replacement_txid':'3'*64}]}
        self.idx.record_mempool_snapshot(first)
        self.idx.record_mempool_snapshot(retry)
        rows=self.idx.db.execute('SELECT txid,event_type FROM mempool_events ORDER BY id').fetchall()
        self.assertEqual([tuple(r) for r in rows],[('2'*64,'replaced')])

if __name__=='__main__': unittest.main()
