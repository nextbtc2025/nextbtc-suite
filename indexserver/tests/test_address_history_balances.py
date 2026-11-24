# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Confirmed running balances must survive page boundaries and chain rewinds."""
import configparser

import pytest

from indexer import Indexer
from server import DEFAULTS, make_app


ADDRESS = '1BoatSLRHtKNngkdXEeobR76b53LETtpyT'
OTHER = '1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY'


def tx(key, prevout, outputs):
    return {
        'txid': key * 64,
        'vin': [{'coinbase':'00'}] if prevout is None else [{'txid':prevout[0] * 64, 'vout':prevout[1]}],
        'vout': [{'n':n,'value':f'0.{amount:08}','scriptPubKey':{'address':address,'hex':'51'}}
                 for n,(address,amount) in enumerate(outputs)],
    }


@pytest.fixture
def ledger(tmp_path):
    idx = Indexer(tmp_path / 'test.db', None)
    try:
        # The second block includes an unrelated transaction, an output spent
        # later in that block, and multiple changes involving the same address.
        idx.apply(0, 'a'*64, {'time':100,'tx':[tx('9',None,[(ADDRESS,100),(OTHER,35)])]})
        idx.apply(1, 'b'*64, {'time':90,'previousblockhash':'a'*64,'tx':[
            tx('d',None,[(OTHER,10)]),
            tx('1',('9',0),[(ADDRESS,60),(OTHER,35)]),
            tx('f',('9',1),[(ADDRESS,30)]),
            tx('3',('1',0),[(OTHER,59)]),
        ]})
        idx.apply(2, 'c'*64, {'time':110,'previousblockhash':'b'*64,'tx':[
            tx('4',('f',0),[(ADDRESS,30)]),
        ]})
        idx.apply(3, 'd'*64, {'time':120,'previousblockhash':'c'*64,'tx':[tx('5',None,[(ADDRESS,5)])]})
        cfg = configparser.ConfigParser()
        cfg.read_dict(DEFAULTS)
        app = make_app(cfg, idx, None, {}, None, service='explorer')
        yield idx, app.test_client()
    finally:
        idx.db.close()


def test_explorer_balances_use_transaction_order_and_remain_exact_on_every_page(ledger):
    idx, client = ledger
    route = '/api/v1/explorer/address/' + ADDRESS
    expected = [('5',35),('4',30),('3',30),('f',90),('1',60),('9',100)]
    full = client.get(route).get_json()['transactions']
    assert [(t['txid'][0],t['balance_after_sats']) for t in full] == expected
    assert full[1]['net_sats'] == 0
    for offset in range(len(full) + 1):
        page = client.get(route + '/history', query_string={'limit':2,'offset':offset})
        assert page.status_code == 200
        assert page.get_json()['transactions'] == full[offset:offset + 2]
    legacy = idx.history(ADDRESS)
    assert [row['txid'][0] for row in legacy if row['height']==1] == ['1','3','f']
    assert all('balance_after_sats' not in row and 'indexed_order' not in row for row in legacy)


def test_balances_follow_replaced_chain_and_height_falls(ledger):
    idx, client = ledger
    for _ in range(3):
        idx.rewind()
    idx.apply(1, 'e'*64, {'time':100,'previousblockhash':'a'*64,'tx':[
        tx('6',('9',0),[(ADDRESS,70)]), tx('7',('6',0),[(ADDRESS,50)])]})
    route = '/api/v1/explorer/address/' + ADDRESS + '/history'
    result = client.get(route).get_json()
    assert result['tip_hash'] == 'e'*64
    assert [(t['txid'][0],t['balance_after_sats']) for t in result['transactions']] == [
        ('7',50),('6',70),('9',100)]
    page = client.get(route + '?offset=1&limit=1').get_json()['transactions']
    assert page == result['transactions'][1:2]
