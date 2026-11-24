# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import configparser
import tempfile
import time
import unittest
from pathlib import Path

from indexer import Indexer
from mempool import MempoolTracker
try:
    from server import make_app
except ImportError:
    make_app=None

class HttpRpc:
    def call(self,method,*params):
        if method=='getblockcount': return 0
        if method=='getblockchaininfo': return {'chain':'main','blocks':0,'headers':0}
        if method=='getblockhash': return '000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1'
        if method=='getblockheader': return {'height':0,'time':1368374520,'bits':'1e0ffff0','hash':'000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1'}
        if method=='getblocktemplate':
            return {'height':1,'bits':'1e0fffff','previousblockhash':self.call('getblockhash',0)}
        if method=='getdifficulty': return 1.0
        if method=='getmempoolinfo': return {'size':1,'bytes':100,'usage':200,'total_fee':0.000001}
        raise AssertionError(method)

class FakeMempool:
    max_txs=100
    def __init__(self):
        self.snapshot={'txs':{'a'*64:{'txid':'a'*64,'vsize':1,'fee_sats':2_000_000,
                                    'ancestor_fee_sats':2_000_000,'ancestor_vsize':1,
                                    'ancestor_feerate_sat_vb':2_000_000,'time':int(time.time()),
                                    'depends':[],'ancestorcount':1,'descendantcount':1}},
                       'spends':{},'received':{},'activity':{},'input_outpoints':{},'children':{},
                       'updated':time.time(),'error':None,'coverage_complete':True,'core_count':1,'indexed_count':1}
    def get(self): return dict(self.snapshot)

@unittest.skipIf(make_app is None,'Flask/Waitress dependencies are not installed in this test environment')
class TestExplorerHttpIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.idx=Indexer(Path(self.tmp.name)/'index.db',HttpRpc())
        self.rpc=HttpRpc();self.mempool=FakeMempool()
        cfg=configparser.ConfigParser()
        cfg.read_dict({'server':{'cors_origins':'null','explorer_read_limit_per_minute':'300','explorer_heavy_limit_per_minute':'60'},
                       'fees':{'fallback_sat_vb':'1.0','mempool_min_samples':'5'}})
        self.app=make_app(cfg,self.idx,self.rpc,{'remote_height':0,'error':None},self.mempool)
        self.client=self.app.test_client()
    def tearDown(self):
        self.idx.db.close();self.tmp.cleanup()

    def test_wallet_and_explorer_services_are_route_isolated(self):
        wallet_app=make_app(self._service_config(),self.idx,self.rpc,
                            {'remote_height':0,'error':None},self.mempool,service='wallet')
        explorer_app=make_app(self._service_config(),self.idx,self.rpc,
                              {'remote_height':0,'error':None},self.mempool,service='explorer')
        wallet_paths = {rule.rule for rule in wallet_app.url_map.iter_rules()}
        self.assertEqual(wallet_paths, {'/api/v1/status','/api/v1/fees','/api/v1/addresses/query',
                                       '/api/v1/history/<address>','/api/v1/tx/<txid>','/api/v1/broadcast'})
        explorer_paths = {rule.rule for rule in explorer_app.url_map.iter_rules()}
        self.assertFalse(wallet_paths.intersection(explorer_paths))
        self.assertIn('/api/v1/explorer/tx/<txid>', explorer_paths)
        wallet=wallet_app.test_client()
        explorer=explorer_app.test_client()
        self.assertEqual(wallet.get('/api/v1/status').status_code,200)
        self.assertEqual(wallet.get('/api/v1/explorer/capabilities').status_code,404)
        self.assertEqual(wallet.get('/').status_code,404)
        self.assertEqual(wallet.get('/explorer').status_code,404)
        self.assertEqual(explorer.get('/').status_code,200)
        self.assertEqual(explorer.get('/explorer').status_code,200)
        self.assertEqual(explorer.get('/api/v1/explorer/capabilities').status_code,200)
        self.assertEqual(explorer.get('/api/v1/status').status_code,404)
        # A GET to a wallet-only POST endpoint must be 404, not 405. A 405
        # would reveal that the wallet route is still registered on Explorer.
        self.assertEqual(explorer.get('/api/v1/broadcast').status_code,404)
        self.assertEqual(explorer.post('/api/v1/broadcast').status_code,404)
        self.assertEqual(explorer.get('/api/v1/fees').status_code,404)

    def _service_config(self):
        cfg=configparser.ConfigParser()
        cfg.read_dict({'server':{'cors_origins':'null','host':'127.0.0.1','port':'8777'},
                       'explorer':{'cors_origins':'null','host':'127.0.0.1','port':'8778',
                                   'read_limit_per_minute':'300','heavy_limit_per_minute':'60'},
                       'fees':{'fallback_sat_vb':'1.0','mempool_min_samples':'5'}})
        return cfg

    def test_capabilities_and_routes_respond(self):
        r=self.client.get('/api/v1/explorer/capabilities')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()['explorer_api_version'],(Path(__file__).resolve().parents[1]/'VERSION').read_text().strip())
        self.assertTrue(r.get_json()['capabilities']['mempool_event_history'])

    def test_fee_histogram_includes_high_fee_overflow(self):
        r=self.client.get('/api/v1/explorer/mempool/fees')
        self.assertEqual(r.status_code,200)
        body=r.get_json()
        self.assertEqual(sum(x['count'] for x in body['histogram']),1)
        self.assertEqual(body['histogram'][-1]['count'],1)

    def test_map_uses_ancestor_package_rate(self):
        r=self.client.get('/api/v1/explorer/mempool/map?limit=10')
        self.assertEqual(r.status_code,200)
        item=r.get_json()['items'][0]
        self.assertEqual(item['ancestor_feerate_sat_vb'],2_000_000)
        self.assertEqual(r.get_json()['sort'],'ancestor_package_feerate_with_individual_fallback')
        self.assertEqual(r.get_json()['items'][0]['ancestor_feerate_sat_vb'],2_000_000)
        self.assertFalse(r.get_json()['package_metrics_complete'])

    def test_invalid_blocks_limit_is_client_error_not_server_error(self):
        r=self.client.get('/api/v1/explorer/blocks?limit=not-a-number')
        self.assertEqual(r.status_code,400)

    def test_mempool_history_and_event_endpoints_are_paginated(self):
        now=int(time.time())
        self.idx.record_mempool_snapshot({'updated':now,'coverage_complete':True,
            'txs':{'a'*64:{'vsize':100,'fee_sats':200}},
            'events':[{'txid':'a'*64,'event_type':'added'}]})
        history=self.client.get('/api/v1/explorer/mempool/history?hours=1&limit=1&offset=0')
        events=self.client.get('/api/v1/explorer/mempool/events?hours=1&limit=1&offset=0')
        self.assertEqual(history.status_code,200)
        self.assertEqual(events.status_code,200)
        self.assertEqual(len(history.get_json()['series']),1)
        self.assertEqual(events.get_json()['events'][0]['event_type'],'added')


    def test_mempool_summary_reports_snapshot_alignment(self):
        r=self.client.get('/api/v1/explorer/mempool/summary')
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.get_json()['current_core_count_matches_snapshot'])

    def test_difficulty_endpoint_reports_core_template_comparison(self):
        r=self.client.get('/api/v1/explorer/difficulty')
        self.assertEqual(r.status_code,200)
        check=r.get_json()['next_block']['core_template_verification']
        self.assertTrue(check['available'])
        self.assertTrue(check['matched'])

    def test_added_event_retains_its_type_after_confirmation(self):
        now=int(time.time())
        txid='c'*64
        self.idx.record_mempool_snapshot({'updated':now-1,'coverage_complete':True,'txs':{},
            'events':[{'txid':txid,'event_type':'added'}]})
        self.idx.record_mempool_snapshot({'updated':now,'coverage_complete':True,'txs':{},
            'events':[{'txid':txid,'event_type':'removed_unknown'}]})
        with self.idx.db:
            self.idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',(txid,10,'a'*64,now))
        data=self.client.get('/api/v1/explorer/mempool/events?hours=1').get_json()
        self.assertEqual([row['event_type'] for row in data['events']],['confirmed','added'])

    def test_only_latest_removal_can_infer_confirmation_after_readmission(self):
        now=int(time.time())
        txid='d'*64
        for i,kind in enumerate(['removed_unknown','added','removed_unknown']):
            self.idx.record_mempool_snapshot({'updated':now-2+i,'coverage_complete':True,'txs':{},
                'events':[{'txid':txid,'event_type':kind}]})
        with self.idx.db:
            self.idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',(txid,8,'a'*64,now))
        rows=self.client.get('/api/v1/explorer/mempool/events').get_json()['events']
        self.assertEqual([r['event_type'] for r in rows],['confirmed','added','removed_unknown'])
        self.assertTrue(all(r['current_confirmation_height']==8 for r in rows))

if __name__=='__main__': unittest.main()
