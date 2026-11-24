# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# License: MIT (see LICENSE)
import configparser, tempfile, time, unittest
from pathlib import Path
from indexer import Indexer
try:
    from server import make_app
except Exception:
    make_app=None

class Rpc:
    def call(self, method, *params):
        if method=='getblockcount': return 2
        if method=='getblockchaininfo': return {'chain':'main'}
        if method=='getblockhash': return '0'*64
        if method=='getblockheader': return {'height':0,'time':1,'bits':'1e0ffff0','hash':'0'*64}
        if method=='getblocktemplate': return {'height':3,'bits':'1e0fffff','previousblockhash':'0'*64}
        if method=='getdifficulty': return 1
        raise AssertionError(method)

@unittest.skipIf(make_app is None, 'Flask/Waitress dependencies are not installed')
class TestExplorerTransactionFeed(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.rpc=Rpc()
        self.idx=Indexer(Path(self.tmp.name)/'index.db',self.rpc)
        now=int(time.time()); tip='b'*64
        with self.idx.db:
            self.idx.db.execute('INSERT INTO blocks VALUES(?,?,?,?)',(2,tip,'a'*64,now))
            self.idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',('1'*64,2,tip,now))
            self.idx.db.execute('INSERT INTO outputs(txid,vout,height,value,script,address,coinbase) VALUES(?,?,?,?,?,?,?)',('1'*64,0,2,500000000,'0014'+'11'*20,'addr1',0))
            self.idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',('2'*64,2,tip,now))
            self.idx.db.execute('INSERT INTO outputs(txid,vout,height,value,script,address,coinbase) VALUES(?,?,?,?,?,?,?)',('2'*64,0,2,312500000,'0014'+'22'*20,'addr2',1))
        cfg=configparser.ConfigParser(); cfg.read_dict({'server':{'cors_origins':'null'},'explorer':{'cors_origins':'null'}})
        self.client=make_app(cfg,self.idx,self.rpc,{'remote_height':2,'error':None},None,service='explorer').test_client()
    def tearDown(self):
        self.idx.db.close(); self.tmp.cleanup()
    def test_feed_includes_ordinary_transactions_and_excludes_coinbase(self):
        response=self.client.get('/api/v1/explorer/transactions?limit=25&offset=0')
        self.assertEqual(response.status_code,200)
        data=response.get_json()
        self.assertEqual(data['total'],1)
        self.assertEqual([x['txid'] for x in data['transactions']],['1'*64])
        self.assertEqual(data['transactions'][0]['total_output_sats'],500000000)
    def test_pagination_limit_is_bounded(self):
        self.assertEqual(self.client.get('/api/v1/explorer/transactions?limit=1000').status_code,400)
