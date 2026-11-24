# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Regression coverage for the detail pages' read-only HTTP contracts."""
import configparser
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from indexer import Indexer
from server import CoreRPCError, DEFAULTS, make_app


ADDRESS = '1BoatSLRHtKNngkdXEeobR76b53LETtpyT'
PREV_TX = 'a' * 64
TXID = '0' * 63 + '1'
PARENT = 'b' * 64
BLOCK = 'd' * 64


class DetailHTTP(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.rpc = Mock()
        self.rpc.call.side_effect = self.core
        self.index = Indexer(Path(temp.name)/'index.db', self.rpc)
        self.addCleanup(self.index.db.close)
        self.db = self.index.db
        with self.db:
            self.db.executemany('INSERT INTO blocks VALUES (?,?,?,?)',
                                [(0, PARENT, '', 100), (1, BLOCK, PARENT, 250)])
            self.db.execute('INSERT INTO txs VALUES (?,?,?,?)', (TXID, 1, BLOCK, 250))
            self.db.execute('INSERT INTO outputs VALUES (?,?,?,?,?,?,?,?,?)',
                            (PREV_TX, 3, 0, 10000, '51', ADDRESS, 0, TXID, 1))
            self.db.execute('INSERT INTO activity VALUES (?,?,?)', (ADDRESS, TXID, 1))
        self.raw = {'txid': TXID,'vin': [{'txid': PREV_TX,'vout': 3}],
                    'vout': [{'value': 0.00009,'n': 0,'scriptPubKey': {'hex': '51','address': ADDRESS}}],
                    'vsize': 100,'confirmations': 5,'blockhash': BLOCK}
        self.tracker = Mock()
        self.tracker.get.return_value = {'txs': {}, 'updated': time.time()}
        cfg = configparser.ConfigParser()
        cfg.read_dict(DEFAULTS)
        self.client = make_app(cfg, self.index, self.rpc, {}, self.tracker, service='explorer').test_client()

    def core(self, method, *args):
        if method == 'getrawtransaction' and args[0] == TXID:
            return self.raw
        if method == 'getblockhash' and args[0] == 1:
            return BLOCK
        if method == 'getblockheader' and args[0] == BLOCK:
            return {'height': 1, 'hash': BLOCK}
        if method == 'validateaddress':
            return {'isvalid': False}
        raise CoreRPCError({'code': -5,'message': 'Not found'})

    def get(self, suffix):
        return self.client.get('/api/v1/explorer/' + suffix)

    def test_confirmed_raw_and_exact_prevout_fee(self):
        row = self.get('tx/' + TXID).get_json()
        self.assertEqual((row['state'], row['confirmations'], row['block_height']), ('confirmed', 5, 1))
        self.assertEqual((row['total_input_sats'], row['total_output_sats'], row['fee_sats'], row['feerate_sat_vb']),
                         (10000, 9000, 1000, 10))
        self.assertEqual(row['inputs'][0]['address'], ADDRESS)
        self.assertEqual(row['outputs'][0]['address'], ADDRESS)

    def test_confirmations_after_index_advances(self):
        self.assertEqual(self.get('tx/'+TXID).json['confirmations'],5)
        with self.db:self.db.execute('INSERT INTO blocks VALUES(?,?,?,?)',(2,'e'*64,BLOCK,300))
        self.raw['confirmations']=6
        self.assertEqual(self.get('tx/'+TXID).json['confirmations'],6)

    def test_mempool_parent_and_unresolved_input(self):
        self.db.execute('DELETE FROM txs')
        self.raw.pop('blockhash')
        self.raw.pop('confirmations')
        self.raw['vin'] = [{'txid': PARENT, 'vout': 0}, {'txid': PREV_TX, 'vout': 99}]
        self.tracker.get.return_value['output_details_by_outpoint'] = {
            (PARENT, 0): {'address': ADDRESS, 'script': '51', 'value_sats': 9800}}
        row = self.get('tx/' + TXID).get_json()
        self.assertEqual((row['state'], row['unresolved_inputs']), ('mempool', 1))
        self.assertEqual(row['inputs'][0]['value_sats'], 9800)
        self.assertIsNone(row['fee_sats'])
        self.assertIsNone(row['total_input_sats'])
        self.assertIsNone(row['feerate_sat_vb'])

    def test_coinbase_has_no_fee_or_total_input(self):
        self.raw['vin'] = [{'coinbase': '00'}]
        row = self.get('tx/' + TXID).get_json()
        self.assertTrue(row['coinbase'])
        self.assertIsNone(row['fee_sats'])
        self.assertIsNone(row['total_input_sats'])

    def test_search_disambiguates_numeric_hash_and_height(self):
        self.assertEqual(self.get('search?q=' + TXID).get_json()['type'], 'tx')
        self.assertEqual(self.get('search?q=' + BLOCK).get_json()['type'], 'block')
        self.assertEqual(self.get('search?q=1').get_json()['height'], 1)
        self.assertEqual(self.get('search?q=' + ADDRESS).get_json()['address'], ADDRESS)
        self.assertEqual(self.get('search?q=' + ADDRESS[:-1] + '4').status_code, 400)
        self.assertEqual(self.get('search?q=²').status_code, 400)

    def test_stale_block_and_transport_errors(self):
        self.rpc.call.side_effect = lambda method,*_: {'height': 1} if method == 'getblockheader' else BLOCK
        self.assertEqual(self.get('search?q=' + PARENT).status_code, 404)
        self.rpc.call.side_effect = RuntimeError('offline')
        self.assertEqual(self.get('search?q=42').status_code, 503)
        self.assertEqual(self.get('tx/' + TXID).status_code, 503)

    def test_real_page_and_address_tip_fields(self):
        p = self.get('blocks?limit=1&offset=1').get_json()
        self.assertEqual((p['total'],p['blocks'][0]['height'],p['has_more']), (2, 0, False))
        for path in ('statistics','utxos','history'):
            body = self.get(f'address/{ADDRESS}/{path}?limit=1').get_json()
            self.assertEqual((body['height'],body['tip_hash']), (1,BLOCK))
