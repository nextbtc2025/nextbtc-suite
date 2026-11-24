# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Validate real Explorer responses against a consistent index backup and local Core."""
import argparse
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sys
import threading

import requests
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import GENESIS, RPC, Indexer, MempoolTracker, load_config, make_app


@contextmanager
def explorer_for_backup(config_path, database_copy):
    if not config_path.is_file() or not database_copy.is_file():
        raise ValueError('Provide an existing RPC configuration and database backup')
    cfg = load_config(config_path)
    configured_db = config_path.parent / cfg.get('index','database')
    if configured_db.exists() and database_copy.samefile(configured_db):
        raise ValueError('Supply a separate database backup')
    # Multiple desktop/mobile/language journeys share a loopback address in this harness.
    cfg.set('explorer','heavy_limit_per_minute','600')
    cfg.set('explorer','read_limit_per_minute','1200')
    rpc = RPC(cfg)
    if rpc.call('getblockhash',0) != GENESIS:
        raise ValueError('Unexpected Core genesis')
    index = Indexer(database_copy, rpc)
    try:
        sample = MempoolTracker(rpc, cfg.getint('index','mempool_max_txs'))
        sample.refresh()
        state = {'remote_height':rpc.call('getblockcount'), 'error':None}
        app = make_app(cfg, index, rpc, state, sample, service='explorer')
        app.extensions['statistics_worker'].refresh()
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}', index, rpc, sample
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
    finally:
        index.db.close()


def verify(url, index, rpc, tracker):
    http = requests.Session()
    http.trust_env = False
    checked = []
    def get(path):
        response = http.get(url+'/api/v1/explorer/'+path, timeout=35)
        response.raise_for_status()
        checked.append(path)
        return response.json()

    stats=get('statistics')
    assert stats['fetched_at'] and stats['issuance']['available']
    tip = index.tip()
    if not tip:
        raise ValueError('Backup has no indexed blocks')
    row = index.db.execute(
        'SELECT address,spent_by,spent_height FROM outputs WHERE spent_by IS NOT NULL '
        'AND address IS NOT NULL ORDER BY spent_height DESC LIMIT 1').fetchone()
    if not row:
        raise ValueError('A confirmed address spend is required for the transaction flow check')
    address, txid, height = row
    block = get(f'block/{height}')
    block_hash = block['hash']
    assert block_hash == rpc.call('getblockhash', height)
    assert get('summary')['indexed_height'] == tip['height']
    assert get('network')['chain'] == 'main'
    for route in ('capabilities','network/blocks','network/transactions','blocks',
                  'mempool','mempool/summary','mempool/fees','mempool/recent','mempool/transactions',
                  'mempool/history','mempool/events',f'block/{height}/neighbors',
                  f'block/{height}/statistics',f'address/{address}/balance-history'):
        get(route)
    assert get(f'block/hash/{block_hash}')['height'] == height
    assert get(f'block/{height}/transactions?limit=1')['total'] == block['tx_count']
    assert get(f'tx/{txid}')['confirmations'] > 0
    assert get(f'tx/{txid}/flow')['flow']['inputs']
    assert get(f'address/{address}')['address'] == address
    for suffix in ('utxos','history','statistics'):
        assert get(f'address/{address}/{suffix}')['address'] == address
    for query, kind in ((height,'block'),(block_hash,'block'),(txid,'tx'),(address,'address')):
        assert get(f'search?q={query}')['type'] == kind
    history = get('difficulty/history?limit=12')['items']
    assert len(history) == 12
    for item in history:
        header = rpc.call('getblockheader',rpc.call('getblockhash',item['height']),True)
        assert math.isclose(item['difficulty'],header['difficulty'],rel_tol=1e-12)
        rate = get(f"network/hashrate?blocks=24&height={item['height']}")['hashrate']
        assert math.isclose(rate,item['hashrate_hps'],rel_tol=1e-12)
    next_block = get('difficulty')['next_block']
    assert next_block['core_template_verification']['matched'] is True
    assert get('difficulty/window')['window_blocks'] == 24
    tiles = get('mempool/map?limit=10')
    assert tiles['total'] == len(tracker.get()['txs'])
    live_dependencies = 'SKIPPED'
    if tiles['items']:
        current = tiles['items'][0]['txid']
        get(f'mempool/tx/{current}')
        get(f'mempool/tx/{current}/dependencies')
        live_dependencies = 'PASS'
    http.close()
    return {'status':'PASS','requests':len(checked),'paths':checked,'tip':tip['height'],
            'height':height,'txid':txid,'address':address,'block_hash':block_hash,
            'historical_hashrate_and_difficulty_matches':len(history),
            'mempool_transactions':tiles['total'],'live_mempool_tx_dependencies':live_dependencies}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'config.ini')
    parser.add_argument('--database-copy', type=Path, required=True)
    args = parser.parse_args()
    with explorer_for_backup(args.config.resolve(),args.database_copy.resolve()) as resources:
        print(json.dumps(verify(*resources), indent=2))
