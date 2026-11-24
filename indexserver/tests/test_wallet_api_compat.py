# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Guard the public wallet API surface from the V1.0.5 baseline."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED = {
    ('GET', '/api/v1/status'),
    ('GET', '/api/v1/fees'),
    ('POST', '/api/v1/addresses/query'),
    ('GET', '/api/v1/history/<address>'),
    ('GET', '/api/v1/tx/<txid>'),
    ('POST', '/api/v1/broadcast'),
}

class TestWalletApiCompatibility(unittest.TestCase):
    def test_v105_wallet_routes_are_preserved(self):
        tree = ast.parse((ROOT / 'server.py').read_text(encoding='utf-8'))
        routes = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in {'get', 'post'} and dec.args
                        and isinstance(dec.args[0], ast.Constant)):
                    path = dec.args[0].value
                    if path.startswith('/api/v1/') and not path.startswith('/api/v1/explorer/'):
                        routes.add((dec.func.attr.upper(), path))
        self.assertTrue(EXPECTED.issubset(routes), f'missing wallet routes: {EXPECTED-routes}')
        self.assertIn(('POST', '/api/v1/broadcast'), routes)

    def test_wallet_payloads_and_broadcast_delegation(self):
        import configparser
        import tempfile
        from unittest.mock import Mock
        from server import DEFAULTS, GENESIS, make_app
        from indexer import Indexer
        from mempool import MempoolTracker

        address = 'bc1q' + 'a' * 38
        txid = 'b' * 64
        cfg = configparser.ConfigParser()
        cfg.read_dict(DEFAULTS)
        rpc = Mock()
        with tempfile.TemporaryDirectory() as temp:
            index = Indexer(pathlib.Path(temp) / 'wallet.db', rpc)
            try:
                index.apply(0, GENESIS, {'time':1, 'tx':[{'txid':txid, 'vin':[{'coinbase':'00'}],
                    'vout':[{'n':0,'value':1,'scriptPubKey':{'hex':'51','address':address}}]}]})
                pool = MempoolTracker(rpc)
                rpc.call.return_value = {}
                pool.refresh()
                client = make_app(cfg,index,rpc,{'remote_height':0,'error':None},pool,service='wallet').test_client()
                self.assertEqual(client.get('/api/v1/status').get_json()['api_version'],'0.4.0')
                result = client.post('/api/v1/addresses/query',json={'addresses':[address]}).get_json()
                self.assertEqual(result['results'][0]['confirmed_sats'],100_000_000)
                self.assertEqual(result['results'][0]['utxos'][0]['txid'],txid)
                self.assertEqual(client.get('/api/v1/history/'+address).get_json()['transactions'][0]['txid'],txid)
                self.assertEqual(client.get('/api/v1/tx/'+txid).get_json()['state'],'confirmed')
                self.assertEqual(client.get('/api/v1/fees').status_code,200)
                rpc.call.reset_mock()
                origin={'Origin':'http://127.0.0.1:8778'}
                self.assertEqual(client.options('/api/v1/broadcast',headers=origin).headers['Access-Control-Allow-Origin'],origin['Origin'])
                self.assertNotIn('Access-Control-Allow-Origin',client.options('/api/v1/status',headers=origin).headers)
                raw = '00' * 16
                rpc.call.return_value = txid
                result = client.post('/api/v1/broadcast', json={'hex':raw})
                self.assertEqual(result.get_json(),{'txid':txid})
                rpc.call.assert_called_once_with('sendrawtransaction',raw)
            finally:
                index.db.close()

if __name__ == '__main__':
    unittest.main()
