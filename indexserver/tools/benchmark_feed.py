"""Time ordinary-transaction pages on an operator database backup."""
import argparse
import configparser
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import closing

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from indexer import Indexer
from server import make_app


def benchmark(source):
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'bench.db'
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(path)) as db:
            src.backup(db)
        index=Indexer(path,None)
        try:
            db=index.db
            old='SELECT COUNT(*) FROM txs t WHERE height<=? AND NOT EXISTS (SELECT 1 FROM outputs c WHERE c.txid=t.txid AND c.coinbase=1)'
            new='SELECT COUNT(*) FROM outputs WHERE height<=? AND vout=0 AND coinbase=0'
            height=index.tip()['height']
            report={'height':height,'transactions':db.execute('SELECT COUNT(*) FROM txs').fetchone()[0],
                    'bytes':path.stat().st_size}
            counts=[]
            for name,sql in [('baseline',old),('partial_index',new)]:
                timings=[]
                for _ in range(3):
                    start=time.perf_counter()
                    count=db.execute(sql,(height,)).fetchone()[0]
                    timings.append((time.perf_counter()-start)*1000)
                counts.append(count)
                report[name]={'median_count_ms':round(statistics.median(timings),3),
                              'plan':[r[3] for r in db.execute('EXPLAIN QUERY PLAN '+sql,(height,))]}
            assert counts[0]==counts[1]
            report['ordinary_transactions']=counts[0]
            report['pages']=[]
            for offset in (0,counts[0]//2,max(0,counts[0]-25)):
                app=make_app(configparser.ConfigParser(),index,None,{},service='explorer')
                client=app.test_client()
                url='/api/v1/explorer/transactions?limit=25&offset='+str(offset)
                times=[]
                for _ in range(6):
                    start=time.perf_counter()
                    r=client.get(url)
                    assert r.status_code==200 and r.json['total']==counts[0]
                    times.append((time.perf_counter()-start)*1000)
                report['pages'].append({'offset':offset,'uncached_ms':round(times[0],3),'cached_median_ms':round(statistics.median(times[1:]),3)})
            return report
        finally:index.db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    print(json.dumps(benchmark(parser.parse_args().database),indent=2))
