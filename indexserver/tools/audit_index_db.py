# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Read-only structural and referential audit for nextBTC index.db."""
import argparse, json, sqlite3, sys, time
from pathlib import Path

def audit(path):
    db=sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    issues=[]; checks={}
    def scalar(name,sql,args=()):
        value=db.execute(sql,args).fetchone()[0]
        checks[name]=int(value or 0)
        if value: issues.append({'check':name,'count':int(value)})
    tables={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required={'blocks','txs','outputs','activity','mempool_history','mempool_events'}
    missing=sorted(required-tables)
    if missing: issues.append({'check':'required_tables','missing':missing})
    if not {'blocks','txs','outputs','activity'}.issubset(tables):
        return {'database':str(path),'ok':False,'issues':issues,'checks':checks}
    scalar('foreign_key_violations','SELECT COUNT(*) FROM pragma_foreign_key_check')
    scalar('transactions_without_canonical_block','SELECT COUNT(*) FROM txs t LEFT JOIN blocks b ON b.height=t.height AND b.hash=t.block_hash WHERE b.height IS NULL')
    scalar('outputs_without_transaction','SELECT COUNT(*) FROM outputs o LEFT JOIN txs t ON t.txid=o.txid WHERE t.txid IS NULL')
    scalar('outputs_height_mismatch','SELECT COUNT(*) FROM outputs o JOIN txs t ON t.txid=o.txid WHERE o.height<>t.height')
    scalar('spent_by_missing_transaction','SELECT COUNT(*) FROM outputs o LEFT JOIN txs t ON t.txid=o.spent_by WHERE o.spent_by IS NOT NULL AND t.txid IS NULL')
    scalar('spent_height_mismatch','SELECT COUNT(*) FROM outputs o JOIN txs t ON t.txid=o.spent_by WHERE o.spent_by IS NOT NULL AND o.spent_height<>t.height')
    scalar('partial_spend_marker','SELECT COUNT(*) FROM outputs WHERE (spent_by IS NULL)<>(spent_height IS NULL)')
    scalar('activity_missing_tx','SELECT COUNT(*) FROM activity a LEFT JOIN txs t ON t.txid=a.txid WHERE t.txid IS NULL')
    scalar('missing_receive_activity','''SELECT COUNT(*) FROM outputs o JOIN txs t ON t.txid=o.txid
      WHERE o.address IS NOT NULL AND NOT EXISTS(SELECT 1 FROM activity a WHERE a.address=o.address AND a.txid=o.txid)''')
    scalar('missing_spend_activity','''SELECT COUNT(*) FROM outputs o JOIN txs t ON t.txid=o.spent_by
      WHERE o.address IS NOT NULL AND o.spent_by IS NOT NULL
      AND NOT EXISTS(SELECT 1 FROM activity a WHERE a.address=o.address AND a.txid=o.spent_by)''')
    scalar('duplicate_mempool_samples','SELECT COUNT(*) FROM (SELECT sampled_at FROM mempool_history GROUP BY sampled_at HAVING COUNT(*)>1)') if 'mempool_history' in tables else None
    scalar('invalid_mempool_event_txids',"SELECT COUNT(*) FROM mempool_events WHERE length(txid)<>64 OR txid GLOB '*[^0-9a-f]*'") if 'mempool_events' in tables else None
    blocks=db.execute('SELECT height,hash,prev_hash FROM blocks ORDER BY height').fetchall()
    broken=[]
    for i,row in enumerate(blocks):
        if i and (row['height']!=blocks[i-1]['height']+1 or row['prev_hash']!=blocks[i-1]['hash']):
            broken.append({'height':row['height'],'prev_hash':row['prev_hash'],'expected_prev_hash':blocks[i-1]['hash']})
    checks['broken_block_links']=len(broken)
    if broken: issues.append({'check':'broken_block_links','examples':broken[:10]})
    if blocks and blocks[0]['height']!=0:
        issues.append({'check':'genesis_height','actual_first_height':blocks[0]['height']})
    tip=dict(blocks[-1]) if blocks else None
    report={'database':str(path),'ok':not issues,'tip':tip,'block_count':len(blocks),
            'transaction_count':db.execute('SELECT COUNT(*) FROM txs').fetchone()[0],
            'output_count':db.execute('SELECT COUNT(*) FROM outputs').fetchone()[0],
            'unspent_output_count':db.execute('SELECT COUNT(*) FROM outputs WHERE spent_by IS NULL').fetchone()[0],
            'checks':checks,'issues':issues,'audited_at_unix':int(time.time())}
    db.close();return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('database');p.add_argument('--output',default='index_db_audit.json')
    args=p.parse_args();report=audit(args.database)
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    if not report['ok']: raise SystemExit(2)
if __name__=='__main__': main()
