# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import unittest
from mempool import MempoolTracker

class BatchRpc:
    def __init__(self,n=205):
        self.entries={f'{i:064x}':{'time':1700000000,'vsize':100,'fees':{'base':'0.000001'}} for i in range(1,n+1)}
        self.calls=[]
    def call(self,method,*params):
        if method=='getrawmempool':return self.entries
        if method=='getrawtransaction':raise AssertionError('single raw transaction RPC should not be used')
        raise AssertionError(method)
    def batch(self,method,params_list,batch_size=100):
        results=[]
        for offset in range(0,len(params_list),batch_size):
            chunk=params_list[offset:offset+batch_size]
            self.calls.append((method,len(chunk),batch_size))
            results.extend({'txid':params[0],'vin':[],'vout':[]} for params in chunk)
        return results

class TestMempoolBatch(unittest.TestCase):
    def test_initial_snapshot_uses_bounded_raw_transaction_batches(self):
        rpc=BatchRpc(205)
        tracker=MempoolTracker(rpc,max_txs=300)
        tracker.refresh()
        self.assertEqual(len(tracker.get()['txs']),205)
        self.assertEqual([x[1] for x in rpc.calls],[100,100,5])
        self.assertTrue(all(x[2]==100 for x in rpc.calls))

    def test_cached_transactions_are_not_refetched(self):
        rpc=BatchRpc(205);tracker=MempoolTracker(rpc,max_txs=300)
        tracker.refresh();self.assertEqual(len(rpc.calls),3)
        tracker.refresh();self.assertEqual(len(rpc.calls),3)

if __name__=='__main__':unittest.main()
