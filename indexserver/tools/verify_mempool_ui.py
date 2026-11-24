# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Replay a simulated, nonempty Mempool through the tracker, Flask API and Chrome.

The local-only test server uses a temporary SQLite database. No operator
configuration, production index or Core RPC is accessed.
"""
import configparser
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import time

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexer import Indexer
from mempool import MempoolTracker
from server import make_app


def txid(value):
    return f'{value:064x}'


PARENT, CHILD, REPLACEMENT, REMOVED, MINED, OLD = map(txid, range(1, 7))


class ReplayRPC:
    def __init__(self):
        self.active = []
        self.fail = False
        # Input txid, size in vB, fee in coins, reported opt-in signal.
        self.rows = {
            PARENT:(txid(91), 200, '0.00000400', True),
            CHILD:(PARENT, 100, '0.00000100', False),
            REPLACEMENT:(txid(92), 400, '0.00008000', None),
            OLD:(txid(92), 170, '0.00000200', True),
            REMOVED:(txid(93), 120, '0.00000200', None),
            MINED:(txid(94), 300, '0.00000600', None),
        }

    def call(self, method, *args):
        if method == 'getrawmempool':
            if self.fail:
                raise RuntimeError('Replay RPC disconnected')
            entries = {}
            for key in self.active:
                prev, size, fee, rbf = self.rows[key]
                entries[key] = {'time':int(time.time()), 'vsize':size, 'fees':{'base':fee},
                                'depends':[prev] if prev in self.active else []}
                if rbf is not None:
                    entries[key]['bip125-replaceable'] = rbf
            return entries
        if method == 'getrawtransaction':
            key = args[0]
            prev = self.rows[key][0]
            return {'txid':key, 'vin':[{'txid':prev, 'vout':0}],
                    'vout':[{'n':0,'value':'0.00010000','scriptPubKey':{'hex':'51'}}]}
        if method == 'getmempoolinfo':
            return {'size':len(self.active),'bytes':sum(self.rows[k][1] for k in self.active)}
        raise AssertionError(method)


def seed(index, tracker, rpc):
    now = int(time.time())
    phases = [[], [OLD, REMOVED, MINED], [REPLACEMENT], [PARENT, CHILD, REPLACEMENT]]
    for i, active in enumerate(phases):
        rpc.active = active
        tracker.refresh()
        snap = tracker.get()
        index.record_mempool_snapshot({**snap,'updated':now - 30 + i * 10})
    # Simulate delayed index catch-up after the sampler observed the removal.
    with index.db:
        index.db.execute('INSERT INTO txs VALUES(?,?,?,?)', (MINED, 2, txid(100), now))


def verify(origin, tracker, rpc):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width':1400, 'height':960}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(8000)
        page.goto(origin + '/#/')
        expect(page.locator('#home-map canvas')).to_be_visible()
        assert page.locator('#home-map').evaluate(
            'el=>echarts.getInstanceByDom(el).getOption().series[0].data.map(t=>t.name).sort()') == sorted([PARENT,CHILD,REPLACEMENT])
        page.goto(origin + '/#/broadcast')
        button=page.locator('#broadcast-form button')
        page.locator('#raw-tx').fill('invalid')
        expect(button).to_be_disabled()
        page.locator('#raw-tx').fill('ab'*24)
        expect(button).to_be_disabled()
        page.locator('#broadcast-form input').check()
        submissions=[]
        def receipt(route):
            submissions.append(route.request.post_data_json)
            route.fulfill(json={'txid':CHILD})
        page.route('**/api/v1/broadcast',receipt)
        button.click()
        expect(page.locator('#broadcast-form a')).to_have_attribute('href','#/tx/'+CHILD)
        assert submissions==[{'hex':'ab'*24}]
        expect(button).to_be_disabled()
        page.goto(origin + '/#/mempool')
        select = page.locator('#tx-select')
        expect(select.locator('option')).to_have_count(3)
        expect(page.locator('#map canvas')).to_be_visible()
        expect(page.locator('#m-stats')).to_contain_text('700 vB')
        expect(page.locator('#m-stats')).to_contain_text('8,500 sat')
        expect(page.locator('#fees .bin b')).to_have_text(['0','1','1','0','1','0','0'])
        expect(page.locator('#map-meta')).to_contain_text('3 / 3')

        # Read ECharts' rendered layout and click the actual Canvas tile. The
        # one-pixel inter-tile gap causes a small rounding difference in area.
        tiles = page.locator('#map').evaluate('''el => {
            const chart = echarts.getInstanceByDom(el);
            const series = chart.getModel().getSeriesByIndex(0);
            return series.getData().tree.root.children.map(node => {
                const {x,y,width,height} = node.getLayout();
                return {id:node.name, x:x+width/2, y:y+height/2, area:width*height,
                        color:node.getModel().get(['itemStyle','color'])};
            });
        }''')
        by_id = {t['id']:t for t in tiles}
        assert set(by_id) == {PARENT, CHILD, REPLACEMENT}, by_id
        for numerator, denominator in [(REPLACEMENT,PARENT),(PARENT,CHILD)]:
            assert abs(by_id[numerator]['area']/by_id[denominator]['area'] - 2) < .05, tiles
        assert len({t['color'] for t in tiles}) == 3, tiles
        child = by_id[CHILD]
        page.locator('#map canvas').click(position={'x':child['x'], 'y':child['y']})
        expect(select).to_have_value(CHILD)
        deps = page.locator('#dependencies')
        expect(deps.locator('.dependency-pair a')).to_have_attribute('href', '#/tx/' + PARENT)
        expect(deps).to_contain_text('未发出替换信号')
        select.select_option(PARENT)
        expect(deps.locator('.dependency-pair a')).to_have_attribute('href', '#/tx/' + CHILD)
        expect(deps).to_contain_text('支持替换')
        select.select_option(REPLACEMENT)
        expect(deps).to_contain_text('信号未知')

        events = page.locator('#events tbody tr')
        expect(events).to_have_count(9)
        def event_for(label, key):
            link=page.locator(f'td:nth-child(3) a[href="#/tx/{key}"]')
            return events.filter(has=link).filter(has_text=label)
        expect(event_for('疑似 RBF 替换', OLD).locator('td:nth-child(4) a')).to_have_attribute('href','#/tx/' + REPLACEMENT)
        expect(event_for('已确认', MINED)).to_have_count(1)
        expect(event_for('新增', MINED)).to_have_count(1)
        expect(event_for('移除', REMOVED)).to_have_count(1)
        arrivals = events.evaluate_all("""rows => rows.map(row =>
            [row.cells[1].textContent,row.cells[2].querySelector('a').hash.slice(5)])""")
        # Within a poll, simultaneous observations may use either order.
        # The newest poll added both relatives. The first delta added the
        # three transactions later observed as removed, confirmed or replaced.
        assert {tuple(row) for row in arrivals[:2]} == {('新增', PARENT),('新增', CHILD)}, arrivals
        assert {tuple(row) for row in arrivals[-3:]} == {('新增', key) for key in (OLD, REMOVED, MINED)}, arrivals
        history = page.locator('#pool-history').evaluate(
            'el => echarts.getInstanceByDom(el).getOption().series[0].data')
        assert [row[1] for row in history] == [0,3,1,3], history
        assert all(a[0]<b[0] for a,b in zip(history,history[1:])), history

        with tracker.lock:
            tracker.snapshot = {**tracker.snapshot, 'updated':time.time()-120}
        page.locator('[data-refresh]').click()
        expect(page.locator('#map-meta')).to_contain_text('已过期')
        expect(deps).to_contain_text('503')

        rpc.fail = True
        try:
            tracker.refresh()
        except RuntimeError as error:
            assert str(error) == 'Replay RPC disconnected'
        page.locator('[data-refresh]').click()
        expect(page.locator('#m-stats')).to_contain_text('Replay RPC disconnected')
        expect(page.locator('#map')).to_contain_text('503')
        expect(page.locator('#map canvas')).to_have_count(0)
        expect(page.locator('#pool-history canvas')).to_be_visible()
        expect(page.locator('#events tbody tr')).to_have_count(9)
        assert not errors, errors
        browser.close()
    return {'status':'PASS', 'data_source':'simulated_rpc_replay', 'browser':'Chrome',
            'map_transactions':3, 'map_fee_colors':3, 'observed_events':9,
            'history_counts':[0,3,1,3], 'stale_and_rpc_error_views':'PASS'}


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory() as directory:
        rpc = ReplayRPC()
        index = Indexer(Path(directory)/'replay.db', rpc)
        tracker = MempoolTracker(rpc)
        try:
            seed(index, tracker, rpc)
            app = make_app(configparser.ConfigParser(), index, rpc, {'remote_height':2},
                           tracker, service='explorer')
            server = make_server('127.0.0.1', 0, app, threaded=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                print(json.dumps(verify(f'http://127.0.0.1:{server.server_port}', tracker, rpc),indent=2))
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
        finally:
            index.db.close()


if __name__ == '__main__':
    main()
