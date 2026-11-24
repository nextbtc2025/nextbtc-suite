# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import unittest
from mempool import MempoolTracker

class FakeRPC:
    def call(self, method, *params):
        if method == 'getrawmempool':
            return {'a'*64:{'time':1700000000,'vsize':200,'weight':800,
                'fees':{'base':'0.00000200','modified':'0.00000300','ancestor':'0.00000600','descendant':'0.00000800'},
                'ancestorsize':500,'descendantsize':700,'bip125-replaceable':'no','ancestorcount':2,'descendantcount':3,
                'depends':['b'*64]}}
        if method == 'getrawtransaction':
            return {'txid':'a'*64,'vin':[{'txid':'b'*64,'vout':0}],
                'vout':[{'n':0,'value':'0.00001000','scriptPubKey':{'hex':'0014'+'11'*20,'address':'bc1q'+'a'*30}}]}
        raise AssertionError(method)

class TestMempoolMetadata(unittest.TestCase):
    def test_missing_fee_invalidates_the_sample(self):
        class MissingFeeRpc(FakeRPC):
            def call(self, method, *params):
                result=super().call(method,*params)
                if method=='getrawmempool':
                    del result['a'*64]['fees']['base']
                return result
        tracker=MempoolTracker(MissingFeeRpc())
        with self.assertRaisesRegex(RuntimeError,'omitted transaction fee'):
            tracker.refresh()
        self.assertFalse(tracker.get().get('coverage_complete'))
        self.assertIsNotNone(tracker.get()['error'])

    def test_explorer_metadata_is_retained_in_snapshot(self):
        tracker=MempoolTracker(FakeRPC(),max_txs=10)
        tracker.refresh()
        tx=tracker.get()['txs']['a'*64]
        self.assertEqual(tx['vsize'],200)
        self.assertEqual(tx['weight'],800)
        self.assertEqual(tx['fee_sats'],200)
        self.assertEqual(tx['modified_fee_sats'],300)
        self.assertEqual(tx['ancestor_fee_sats'],600)
        self.assertEqual(tx['ancestor_vsize'],500)
        self.assertEqual(tx['ancestor_feerate_sat_vb'],1.2)
        self.assertFalse(tx['replaceable'])
        self.assertEqual(tx['ancestorcount'],2)
        self.assertEqual(tx['descendantcount'],3)
        self.assertEqual(tx['depends'],['b'*64])
        self.assertEqual(tracker.get()['children'], {'b'*64:['a'*64]})


    def test_txids_are_normalized_before_cache_and_dependency_indexing(self):
        class UpperRPC(FakeRPC):
            def call(self, method, *params):
                if method == 'getrawmempool':
                    return {'A'*64:{'time':1700000000,'vsize':200,'fees':{'base':'0.00000200'},'depends':['B'*64]}}
                if method == 'getrawtransaction':
                    return {'txid':'A'*64,'vin':[],'vout':[]}
                raise AssertionError(method)
        tracker=MempoolTracker(UpperRPC(),max_txs=10)
        tracker.refresh()
        snap=tracker.get()
        self.assertIn('a'*64,snap['txs'])
        self.assertEqual(snap['children'],{'b'*64:['a'*64]})
        self.assertIn('a'*64,tracker.raw_cache)

    def test_mempool_over_limit_keeps_old_snapshot_marked_stale(self):
        class TooLargeRPC(FakeRPC):
            def call(self, method, *params):
                if method == 'getrawmempool':
                    return {str(i).zfill(64): {} for i in range(11)}
                return super().call(method, *params)
        tracker=MempoolTracker(FakeRPC(),max_txs=10)
        tracker.refresh()
        old_updated=tracker.get()['updated']
        tracker.rpc=TooLargeRPC()
        with self.assertRaises(RuntimeError):
            tracker.refresh()
        snap=tracker.get()
        self.assertEqual(snap['updated'],old_updated)
        self.assertIn('too large',snap['error'].lower())
        self.assertEqual(len(snap['txs']),1)


    def test_bip125_replaceable_yes_string_is_parsed_as_true(self):
        class ReplaceableRPC(FakeRPC):
            def call(self, method, *params):
                if method=='getrawmempool':
                    return {'a'*64:{'time':1700000000,'vsize':100,'fees':{'base':'0.000001'},'bip125-replaceable':'yes'}}
                if method=='getrawtransaction':
                    return {'txid':'a'*64,'vin':[],'vout':[]}
                raise AssertionError(method)
        tracker=MempoolTracker(ReplaceableRPC(),max_txs=10)
        tracker.refresh()
        self.assertTrue(tracker.get()['txs']['a'*64]['replaceable'])


    def test_package_feerate_is_marked_fallback_when_core_omits_ancestor_fields(self):
        class OldCoreRPC(FakeRPC):
            def call(self, method, *params):
                if method=='getrawmempool':
                    return {'a'*64:{'time':1,'vsize':100,'fees':{'base':'0.00000200'}}}
                if method=='getrawtransaction':
                    return {'txid':'a'*64,'vin':[],'vout':[]}
                raise AssertionError(method)
        tracker=MempoolTracker(OldCoreRPC(),max_txs=10)
        tracker.refresh()
        tx=tracker.get()['txs']['a'*64]
        self.assertFalse(tx['ancestor_metrics_available'])
        self.assertIsNone(tx['replaceable'])
        self.assertEqual(tx['ancestor_feerate_sat_vb'],2.0)


    def test_legacy_core_fee_fields_are_supported(self):
        class LegacyRPC(FakeRPC):
            def call(self,method,*params):
                if method=='getrawmempool':
                    return {'a'*64:{'time':1,'vsize':100,'fee':'0.00000200','modifiedfee':'0.00000300',
                                    'ancestorfees':600,'descendantfees':800,'ancestorsize':500,'descendantsize':700}}
                if method=='getrawtransaction':return {'txid':'a'*64,'vin':[],'vout':[]}
                raise AssertionError(method)
        tracker=MempoolTracker(LegacyRPC(),max_txs=10);tracker.refresh()
        tx=tracker.get()['txs']['a'*64]
        self.assertEqual(tx['fee_sats'],200)
        self.assertEqual(tx['modified_fee_sats'],300)
        self.assertEqual(tx['ancestor_fee_sats'],600)
        self.assertTrue(tx['ancestor_metrics_available'])

if __name__=='__main__':unittest.main()
