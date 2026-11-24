"""Measure the additional feed index using read-only production rows."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
from statistics import median
from time import perf_counter
import json

def measure(source):
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as real:
        ddl=real.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='outputs'").fetchone()[0]
        rows=real.execute('SELECT * FROM outputs ORDER BY rowid DESC LIMIT 25000').fetchall()
        indexes=[r[0] for r in real.execute("SELECT sql FROM sqlite_master WHERE tbl_name='outputs' AND type='index' AND sql IS NOT NULL AND name!='idx_regular_feed'")]
    result={}
    for variant in ['before','after']:
        times=[]
        for _ in range(3):
            with closing(sqlite3.connect(':memory:')) as db:
                db.execute(ddl)
                for statement in indexes:db.execute(statement)
                if variant=='after':
                    db.execute('CREATE INDEX idx_regular_feed ON outputs(height,txid) WHERE vout=0 AND coinbase=0')
                start=perf_counter()
                db.executemany('INSERT INTO outputs VALUES(?,?,?,?,?,?,?,?,?)',reversed(rows))
                db.commit()
                times.append((perf_counter()-start)*1000)
                pages=db.execute('PRAGMA page_count').fetchone()[0]
                size=db.execute('PRAGMA page_size').fetchone()[0]
        result[variant]={'median_ms':round(median(times),3),'allocated_bytes':pages*size}
    return {'rows':len(rows),'qualifying':sum(r[1]==0 and r[6]==0 for r in rows),**result}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    print(json.dumps(measure(parser.parse_args().database),indent=2))
