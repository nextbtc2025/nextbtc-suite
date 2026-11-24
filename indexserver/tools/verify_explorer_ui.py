# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Exercise Explorer UI navigation in Chrome using a real database copy and Core."""
import argparse
from decimal import Decimal
import re
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from verify_live_explorer import ROOT, explorer_for_backup


def check_full_hash(link, expected, wide):
    """Text ranges expose CSS clipping even when textContent still holds a full hash."""
    link.wait_for()
    assert link.inner_text().strip() == expected, (link.inner_text(),expected)
    if wide:
        visible = link.evaluate("""link => {
            const range = document.createRange();
            const label = link.querySelector("code") || link;
            range.selectNodeContents(label);
            const rects = [...range.getClientRects()].filter(r => r.width > 0);
            for (let n = label; n; n = n.parentElement) {
                if (getComputedStyle(n).overflowX === 'visible') continue;
                const box = n.getBoundingClientRect();
                if (rects.some(r => r.left < box.left-1 || r.right > box.right+1)) return false;
            }
            return rects.length > 0 && rects.every(r => r.left >= -1 && r.right <= innerWidth+1);
        }""")
        assert visible, f'Hash clipped with space available: {expected}'
    else:
        assert link.evaluate('''el => {const n=el.querySelector("code")||el;
            return getComputedStyle(n).textOverflow==="ellipsis" && n.scrollWidth>n.clientWidth}''')


def verify_history_page(page, db, rpc, address, closing, previous, visited):
    panel = page.locator('section').filter(has=page.get_by_role('heading', name='交易历史',exact=True))
    rows = panel.locator('tbody tr')
    rows.first.wait_for()
    render = rows.evaluate_all("""rows => rows.map(row => {
        const link = row.cells[0].querySelector('a');
        return { txid:link.hash.split('/').pop(), amounts:[...row.cells].slice(-4).map(cell => {
            const amount = cell.lastElementChild || cell;
            return {text:amount.textContent.trim(), color:getComputedStyle(amount).color};
        }) };
    })""")
    block_order = {}
    for item in render:
        txid = item['txid']
        assert txid not in visited, f'Duplicate address transaction {txid}'
        visited.add(txid)
        height, received, spent = db.execute("""
            SELECT height,
                COALESCE((SELECT SUM(value) FROM outputs WHERE address=? AND txid=?),0),
                COALESCE((SELECT SUM(value) FROM outputs WHERE address=? AND spent_by=?),0)
            FROM activity WHERE address=? AND txid=?""", (address,txid)*3).fetchone()
        if previous:
            prior_height, prior_txid = previous
            assert height <= prior_height
            if height == prior_height:
                if height not in block_order:
                    ids = rpc.call('getblock', rpc.call('getblockhash',height), 1)['tx']
                    block_order[height] = {tx:i for i,tx in enumerate(ids)}
                positions = block_order[height]
                assert positions[txid] < positions[prior_txid], (height, prior_txid, txid)
        previous = (height,txid)
        net = received-spent
        for column, (cell, value) in enumerate(zip(item['amounts'],(received,-spent,net,closing),strict=True)):
            raw = cell['text'].replace(',','').removesuffix('nextBTC').strip()
            assert Decimal(raw) * 100000000 == value, (txid,cell,value)
            if column != 3:
                color = tuple(map(int,re.findall(r'[0-9]+',cell['color'])[:3]))
                red,green,blue = color
                if value > 0:
                    assert raw.startswith('+') and green > max(red,blue), (txid,cell)
                elif value < 0:
                    assert raw.startswith('-') and red > max(green,blue), (txid,cell)
                else:
                    assert not raw.startswith(('+','-')) and blue >= max(red,green), (txid,cell)
        closing -= net
    return closing, previous


def check_ui(origin, index, rpc, _tracker, screenshots=None):
    address, txid, height = index.db.execute(
        'SELECT address,spent_by,spent_height FROM outputs WHERE spent_by IS NOT NULL '
        'AND address IS NOT NULL ORDER BY spent_height DESC LIMIT 1').fetchone()
    block_hash = rpc.call('getblockhash',height)
    first_block_tx = rpc.call('getblock',block_hash,1)['tx'][0]
    candidate = index.db.execute(
        'SELECT address FROM activity GROUP BY address HAVING COUNT(*) > 25 LIMIT 1').fetchone()
    history_checks = []
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        for width, screen_height in [(1440,960),(390,844)]:
            context = browser.new_context(viewport={'width':width,'height':screen_height})
            page = context.new_page()
            errors = []
            external = []
            page.on('pageerror',lambda error:errors.append(str(error)))
            def note_request(request):
                url = urlsplit(request.url)
                if url.scheme in ('http','https') and url.netloc != urlsplit(origin).netloc:
                    external.append(request.url)
            page.on('request',note_request)
            routes = ['/','/dwg','/mempool','/blocks',f'/block/{height}',f'/tx/{txid}',f'/address/{address}']
            if candidate:
                routes.extend([f'/address/{candidate[0]}',f'/address/{candidate[0]}?page=2'])
            for route in routes:
                page.goto(origin+'/#'+route)
                page.wait_for_load_state('networkidle')
                page.locator('main').wait_for()
                if route=='/':
                    hash_link = page.locator('#recent tbody tr').first.locator('td').nth(1).locator('a')
                    check_full_hash(hash_link, index.tip()['hash'], width>=1000)
                    page.wait_for_function("document.querySelectorAll('main [_echarts_instance_]').length >= 2")
                    if page.locator('#home-pool-toggle').get_attribute('aria-expanded')=='false':
                        page.locator('#home-pool-toggle').click()
                    page.locator('#home-map-meta').get_by_text('展示',exact=False).wait_for()
                    charts = page.locator('.chart-pair [_echarts_instance_]').evaluate_all('''elements => elements.map(el => {
                        const opts = echarts.getInstanceByDom(el).getOption();
                        const rect = el.getBoundingClientRect();
                        return {kind:opts.series[0].type, count:opts.series[0].data.length,
                                area:!!opts.series[0].areaStyle, axis:opts.xAxis[0].type,
                                tooltip:opts.tooltip[0].trigger, top:rect.top, left:rect.left};
                    })''')
                    assert all(c['kind']=='line' and c['count']>=2 and c['area'] and
                               c['axis']=='value' and c['tooltip']=='axis' for c in charts[:2]), charts
                    if width >= 1000:
                        assert abs(charts[0]['top']-charts[1]['top'])<5 and charts[0]['left']<charts[1]['left'], charts
                elif route=='/dwg':
                    page.wait_for_function("document.querySelectorAll('main tbody tr').length >= 2")
                elif route=='/blocks':
                    block_link = page.locator('main tbody tr').first.locator('td').nth(1).locator('a')
                    check_full_hash(block_link, index.tip()['hash'], width>=1000)
                elif route.startswith('/block/'):
                    page.get_by_text(block_hash, exact=True).first.wait_for(state='attached',timeout=8000)
                    link=page.locator('main table a[href="#/tx/'+first_block_tx+'"]')
                    check_full_hash(link, first_block_tx, width>=1000)
                elif route.startswith('/tx/'):
                    page.get_by_text(txid, exact=True).first.wait_for(state='attached',timeout=8000)
                elif route.startswith('/address/'):
                    current_address = route.split('?')[0].split('/')[-1]
                    page.get_by_text(current_address,exact=True).first.wait_for(state='attached',timeout=8000)
                    page.locator('canvas.address-code').wait_for()
                    if '?page=2' in route:
                        page.get_by_text(re.compile(r'第 2 /'),exact=False).first.wait_for()
                    else:
                        closing = index.db.execute('SELECT COALESCE(SUM(value),0) FROM outputs '
                            'WHERE address=? AND spent_by IS NULL',(current_address,)).fetchone()[0]
                        previous, visited = None, set()
                    closing, previous = verify_history_page(
                        page,index.db,rpc,current_address,closing,previous,visited)
                    history_checks.append({'width':width,'route':route,'checked_rows_so_far':len(visited)})
                overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                if overflow:
                    raise AssertionError(f'Horizontal page overflow at width {width}, route {route}')
                if screenshots:
                    screenshots.mkdir(parents=True,exist_ok=True)
                    name = route.strip('/').split('/')[0] or 'home'
                    page.screenshot(path=screenshots/f'{width}-{name}.png')
                results.append((width,route))
            for value, expected in [(str(height),'block'),(block_hash,'block'),(txid,'tx'),(address,'address')]:
                field=page.locator('form input').first
                field.fill(value)
                with page.expect_response(lambda r:'/api/v1/explorer/search?' in r.url) as search:
                    field.press('Enter')
                assert search.value.status==200
                target = str(height) if expected=='block' else value
                page.wait_for_url(origin+f'/#/{expected}/{target}',timeout=8000)
                page.wait_for_load_state('networkidle')
            page.locator('#language-toggle').click()
            for view in [*routes[:7],'/transactions','/statistics','/broadcast']:
                page.goto(origin+'/#'+view)
                page.reload(wait_until='networkidle')
                page.wait_for_load_state('networkidle')
                assert page.locator('html').get_attribute('lang')=='en'
                visible=page.locator('main').inner_text()
                assert not re.search(r'[㐀-鿿]',visible), (view,visible)
                assert 'HTTP 5' not in visible and 'HTTP 4' not in visible,view
            if errors or external:
                raise AssertionError({'page_errors':errors,'external_requests':external})
            context.close()
        browser.close()
    return {'status':'PASS','route_viewports':results,'searches':8,'address_ledger':history_checks,
            'two_page_ledger':'PASS' if candidate else 'SKIPPED: backup has no address with more than 25 transactions'}


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--database-copy',type=Path,required=True)
    ap.add_argument('--config',type=Path,default=ROOT/'config.ini')
    ap.add_argument('--screenshots',type=Path)
    args=ap.parse_args()
    with explorer_for_backup(args.config.resolve(),args.database_copy.resolve()) as resources:
        print(json.dumps(check_ui(*resources,args.screenshots),indent=2))
