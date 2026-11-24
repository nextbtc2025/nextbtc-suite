import configparser
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import pytest
from flask import Flask,jsonify
from indexer import Indexer
from server import make_app
from statistics_worker import StatisticsWorker
from explorer_cache import ExplorerCache

@pytest.fixture
def idx(tmp_path):
    db=Indexer(tmp_path/'index.db',None)
    yield db
    db.db.close()

def add(index,h,hash,prev):
    index.apply(h,hash,{'previousblockhash':prev,'time':100+h,'tx':[
        {'txid':hash,'vin':[{'coinbase':'00'}],'vout':[{'n':0,'value':1,'scriptPubKey':{'hex':'51','address':'A'}}]}]})

def test_statistics_background_restart_failure_and_fork(idx,monkeypatch):
    add(idx,0,'0'*64,'0'*64)
    app=make_app(configparser.ConfigParser(),idx,None,{},service='explorer')
    worker=app.extensions['statistics_worker']
    client=app.test_client()
    traced=[]
    idx.db.set_trace_callback(traced.append)
    route='/api/v1/explorer/statistics'
    assert client.get(route).status_code==503
    assert not any('outputs' in q.lower() or 'activity' in q.lower() for q in traced)
    worker.refresh()
    assert client.get(route).json['height']==0
    add(idx,1,'1'*64,'0'*64)
    worker.refresh()
    assert StatisticsWorker(idx).latest()['tip_hash']=='1'*64
    idx.rewind()
    add(idx,1,'2'*64,'0'*64)
    assert client.get(route).json['height']==0
    with monkeypatch.context() as m:
        def broken(*args):raise RuntimeError('injected failure')
        m.setattr('statistics_worker.compute',broken)
        worker.refresh()
        assert worker.state=='failed' and worker.latest()['height']==0
    worker.refresh()
    assert client.get(route).json['tip_hash']=='2'*64

def test_admin_and_public_limits(idx):
    cfg=configparser.ConfigParser()
    cfg.read_dict({'explorer':{'admin_token':'test-token','read_limit_per_minute':'3'}})
    client=make_app(cfg,idx,None,{},service='explorer').test_client()
    path='/api/v1/explorer/admin/metrics'
    assert client.get(path).status_code==401
    assert client.get('/explorer/monitor.html').status_code==401
    assert client.get('/explorer/admin',auth=('admin','test-token')).status_code==200
    assert client.get(path,auth=('admin','test-token')).json['worker']=='idle'
    client.get(path)
    response=client.get(path)
    assert response.status_code==429 and response.headers['Retry-After']
    assert client.get(path+'?a='+'a'*2050).status_code==414
    assert make_app(cfg,idx,None,{},service='wallet').test_client().get(path).status_code==404

def test_coalescing_and_tip_change(idx):
    app=Flask(__name__)
    cache=ExplorerCache()
    calls=[]
    entered,release=Event(),Event()
    def view():
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return jsonify(number=len(calls))
    app.add_url_rule('/',view_func=cache.wrap(app,view,idx,None,5))
    def read():return app.test_client().get('/').json['number']
    with ThreadPoolExecutor(3) as executor:
        first=executor.submit(read)
        assert entered.wait(3)
        second=executor.submit(read)
        release.set()
        assert first.result()==second.result()==1
    add(idx,0,'a'*64,'0'*64)
    assert read()==2 and cache.metrics()['hits']==1

def test_feed_plan_order_and_filters(idx):
    with idx.db:
        for height in (1,2):
            txid=str(height)*64
            idx.db.execute('INSERT INTO blocks VALUES(?,?,?,?)',(height,txid,'',100))
            idx.db.execute('INSERT INTO txs VALUES(?,?,?,?)',(txid,height,txid,100))
            idx.db.execute("INSERT INTO outputs(txid,vout,height,value,script) VALUES(?,0,?,100,'51')",(txid,height))
    client=make_app(configparser.ConfigParser(),idx,None,{},service='explorer').test_client()
    path='/api/v1/explorer/transactions?'
    assert [r['height'] for r in client.get(path+'order=asc').json['transactions']]==[1,2]
    assert client.get(path+'block=2').json['total']==1
    assert client.get(path+'order=other').status_code==400
    assert 'idx_regular_feed' in str([tuple(r) for r in idx.db.execute(
        'EXPLAIN QUERY PLAN SELECT txid FROM outputs WHERE coinbase=0 AND vout=0 AND height<=99 ORDER BY height,txid')])

def test_reorg_during_mempool_refresh(idx):
    from unittest.mock import Mock
    from mempool import MempoolTracker
    rpc=Mock()
    tracker=MempoolTracker(rpc)
    idx.on_rewind=tracker.invalidate
    add(idx,0,'a'*64,'0'*64)
    rpc.call.side_effect=lambda *args: (idx.rewind() or {})
    with pytest.raises(RuntimeError,match='Chain changed'):
        tracker.refresh()
    assert tracker.get()['error'] and not tracker.get()['txs']
    rpc.call.side_effect=lambda *args:{}
    tracker.refresh()
    assert tracker.get()['coverage_complete'] and tracker.get()['error'] is None

def test_corrupt_stats_snapshot_recovers(idx):
    add(idx,0,'e'*64,'0'*64)
    worker=StatisticsWorker(idx)
    worker.refresh()
    with idx.db:idx.db.execute("UPDATE explorer_cache SET payload_json='invalid'")
    restored=StatisticsWorker(idx)
    assert restored.latest() is None
    restored.refresh()
    assert restored.latest()['height']==0
    assert restored.latest()['utxo_count']==0

def test_rpc_transport_budget_is_request_local():
    from server import RPC,request_budget
    rpc=object.__new__(RPC)
    rpc.timeout=30
    try:
        request_budget.deadline=time.monotonic()+2
        assert 0<rpc.transport_timeout()<=2
        request_budget.deadline=time.monotonic()-1
        with pytest.raises(TimeoutError):rpc.transport_timeout()
    finally:request_budget.deadline=0
    assert rpc.transport_timeout()==30
