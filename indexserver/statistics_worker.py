"""Canonical background statistics on an independent WAL read snapshot."""
import json
import logging
import sqlite3
import threading
import time
from contextlib import closing
from explorer_chain_data import (address_balance_buckets, cumulative_scheduled_issuance_sats, maximum_scheduled_issuance_sats, SUBSIDY_HALVING_INTERVAL, block_subsidy_sats, INITIAL_SUBSIDY_SATS, NOMINAL_MAX_SUPPLY_SATS)

def compute(db,tip):
    utxo=db.execute("SELECT COUNT(*) AS n, COALESCE(SUM(value),0) AS total FROM outputs WHERE height>0 AND spent_by IS NULL AND length(script)<=20000 AND substr(script,1,2)!='6a'").fetchone()
    historical=int(db.execute('SELECT COUNT(DISTINCT address) FROM activity').fetchone()[0])
    buckets=address_balance_buckets(db,spendable_only=True)
    indexed_height=int(tip['height'])
    issued_sats=cumulative_scheduled_issuance_sats(indexed_height)
    exact_max_sats=maximum_scheduled_issuance_sats();schedule_remaining=max(0,exact_max_sats-issued_sats)
    next_halving=((indexed_height//SUBSIDY_HALVING_INTERVAL)+1)*SUBSIDY_HALVING_INTERVAL
    current_reward=block_subsidy_sats(indexed_height+1)
    issuance={'available':True,'initial_subsidy_sats':INITIAL_SUBSIDY_SATS,'halving_interval':SUBSIDY_HALVING_INTERVAL,
        'current_block_subsidy_sats':block_subsidy_sats(indexed_height),'next_block_subsidy_sats':current_reward,'issued_sats':issued_sats,'nominal_max_supply_sats':NOMINAL_MAX_SUPPLY_SATS,
        'exact_scheduled_max_sats':exact_max_sats,'remaining_sats':schedule_remaining,
        'issued_percent':issued_sats/exact_max_sats*100 if exact_max_sats else 0.0,
        'remaining_percent':schedule_remaining/exact_max_sats*100 if exact_max_sats else 0.0,
        'next_halving_height':next_halving,'blocks_until_halving':max(0,next_halving-indexed_height),
        'genesis_allocation_sats':50*100_000_000,'genesis_allocation_spendable':False,
        'rounding_unissued_sats':NOMINAL_MAX_SUPPLY_SATS-exact_max_sats,
        'description':'Scheduled subsidy accumulated by confirmed height using integer-satoshi halving. The unspendable 50 NBTC genesis allocation is excluded.'}
    payload=dict(height=indexed_height,tip_hash=tip['hash'],utxo_count=int(utxo['n']),utxo_total_sats=int(utxo['total']),
        historical_address_count=historical,**buckets,issuance=issuance,
        definitions={'historical_address_count':'Distinct addresses seen in indexed transaction activity.',
            'nonzero_balance_addresses':'Distinct indexed addresses with a positive confirmed UTXO balance.',
            'utxo_count':'Unspent indexed outputs excluding genesis, OP_RETURN and scripts exceeding 10,000 bytes.',
            'utxo_total_sats':'Sum of values in the counted unspent outputs.',
            'issuance':'Scheduled block subsidy accumulated from block 1 through indexed height; excludes fees and the unspendable genesis allocation.','mempool_excluded':True},
        source='canonical_sqlite_index_plus_consensus_schedule',fetched_at=int(time.time()))
    return payload

class StatisticsWorker:
    def __init__(self,index):
        self.index=index
        self.wake=threading.Event()
        self.payload=None
        self.state='idle'
        self.seconds=0.0

    def latest(self):
        # Always establish ancestry against the index before exposing a snapshot.
        with self.index.lock:
            data=self.payload
            if data and self.index.db.execute('SELECT 1 FROM blocks WHERE height=? AND hash=?',
                    (data['height'],data['tip_hash'])).fetchone():
                return data
            rows=self.index.db.execute("""SELECT c.payload_json,b.height,b.hash FROM explorer_cache c
                JOIN blocks b ON b.height=c.tip_height AND b.hash=c.tip_hash
                WHERE c.cache_key LIKE 'worker-v33:%' ORDER BY c.tip_height DESC LIMIT 4""")
            self.payload=None
            for raw,height,block_hash in rows:
                try:
                    candidate=json.loads(raw)
                    if candidate['height']==height and candidate['tip_hash']==block_hash and 'issuance' in candidate:
                        self.payload=candidate
                        break
                except (ValueError,KeyError,TypeError):
                    continue
            return self.payload

    def refresh(self):
        tip=self.index.tip()
        previous=self.latest()
        if not tip or (previous and previous['tip_hash']==tip['hash']):
            return
        started=time.monotonic()
        self.state='running'
        try:
            with closing(sqlite3.connect(self.index.path.as_uri()+'?mode=ro',uri=True)) as db:
                db.row_factory=sqlite3.Row
                db.execute('BEGIN')
                tip=db.execute('SELECT height,hash FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
                if tip is None:return
                data=compute(db,tip)
            with self.index.lock,self.index.db:
                if not self.index.db.execute('SELECT 1 FROM blocks WHERE height=? AND hash=?',
                        (tip['height'],tip['hash'])).fetchone():return
                self.index.db.execute('INSERT OR REPLACE INTO explorer_cache VALUES(?,?,?,?,?)',
                    ('worker-v33:'+tip['hash'],tip['height'],tip['hash'],json.dumps(data),data['fetched_at']))
                self.index.db.execute("DELETE FROM explorer_cache WHERE cache_key LIKE 'worker-v33:%' AND (tip_height<? OR tip_hash NOT IN (SELECT hash FROM blocks WHERE height=tip_height))",(tip['height']-3,))
            self.payload=data
            self.state='idle'
        except Exception:
            self.state='failed'
            logging.getLogger(__name__).exception('Statistics update failed')
        finally:
            self.seconds=time.monotonic()-started
            if self.state=='running':self.state='idle'

    def run(self):
        while True:
            self.wake.clear()
            try:
                self.refresh()
            except Exception:
                self.state='failed'
                logging.getLogger(__name__).exception('Statistics worker could not read index')
            self.wake.wait(60)
