# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""nextBTC block index, independent of node's wallet. SQLite atomic block commits."""
import sqlite3, logging, time, threading, functools
from pathlib import Path
from contextlib import nullcontext
from decimal import Decimal

LOG = logging.getLogger('indexer')
COIN = Decimal('100000000')
def sats(value): return int(Decimal(str(value)) * COIN)

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS explorer_cache (cache_key TEXT PRIMARY KEY, tip_height INTEGER NOT NULL, tip_hash TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS blocks (height INTEGER PRIMARY KEY, hash TEXT NOT NULL UNIQUE, prev_hash TEXT NOT NULL, timestamp INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS outputs (txid TEXT NOT NULL, vout INTEGER NOT NULL, height INTEGER NOT NULL, value INTEGER NOT NULL, script TEXT NOT NULL, address TEXT, coinbase INTEGER NOT NULL DEFAULT 0, spent_by TEXT, spent_height INTEGER, PRIMARY KEY(txid,vout));
CREATE INDEX IF NOT EXISTS idx_outputs_addr ON outputs(address, spent_height);
CREATE INDEX IF NOT EXISTS idx_outputs_script ON outputs(script, spent_height);
CREATE INDEX IF NOT EXISTS idx_regular_feed ON outputs(height,txid) WHERE vout=0 AND coinbase=0;
CREATE INDEX IF NOT EXISTS idx_outputs_height ON outputs(height);
CREATE INDEX IF NOT EXISTS idx_outputs_spent_height ON outputs(spent_height);
CREATE INDEX IF NOT EXISTS idx_outputs_spent_by_address ON outputs(spent_by,address) WHERE spent_by IS NOT NULL;
-- Explorer query indexes: additive only; existing wallet/index schema semantics are unchanged.
CREATE INDEX IF NOT EXISTS idx_outputs_address_unspent_height ON outputs(address,height,txid,vout) WHERE spent_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_outputs_address_txid ON outputs(address,txid);
CREATE INDEX IF NOT EXISTS idx_outputs_address_spentby ON outputs(address,spent_by) WHERE spent_by IS NOT NULL;
CREATE TABLE IF NOT EXISTS txs (txid TEXT PRIMARY KEY, height INTEGER NOT NULL, block_hash TEXT NOT NULL, timestamp INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_txs_height ON txs(height);
CREATE INDEX IF NOT EXISTS idx_txs_timestamp ON txs(timestamp,txid);
-- Cover Explorer transaction feed ordering and common aggregate lookups.
CREATE INDEX IF NOT EXISTS idx_txs_explorer_order ON txs(height DESC,timestamp DESC,txid DESC,block_hash);
CREATE INDEX IF NOT EXISTS idx_outputs_coinbase_txid ON outputs(txid) WHERE coinbase=1;
CREATE INDEX IF NOT EXISTS idx_outputs_txid_value ON outputs(txid,value);
CREATE INDEX IF NOT EXISTS idx_outputs_spent_by_value ON outputs(spent_by,value) WHERE spent_by IS NOT NULL;
CREATE TABLE IF NOT EXISTS activity (address TEXT NOT NULL, txid TEXT NOT NULL, height INTEGER NOT NULL, PRIMARY KEY(address,txid));
CREATE TABLE IF NOT EXISTS mempool_history (id INTEGER PRIMARY KEY AUTOINCREMENT, sampled_at INTEGER NOT NULL, tx_count INTEGER NOT NULL, total_vsize INTEGER NOT NULL, total_fee_sats INTEGER NOT NULL, fee_bins_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_mempool_history_time ON mempool_history(sampled_at);
CREATE TABLE IF NOT EXISTS mempool_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_at INTEGER NOT NULL, txid TEXT NOT NULL, event_type TEXT NOT NULL, replacement_txid TEXT);
CREATE INDEX IF NOT EXISTS idx_mempool_events_time ON mempool_events(event_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS idx_mempool_events_txid ON mempool_events(txid,event_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_addr ON activity(address,height DESC);
'''

class MeasuredConnection(sqlite3.Connection):
    calls=0
    seconds=0.0

    def execute(self,*args,**kwargs):
        started=time.monotonic()
        try:
            return super().execute(*args,**kwargs)
        finally:
            self.calls+=1
            self.seconds+=time.monotonic()-started

    def mean_ms(self):
        return round(1000*self.seconds/max(self.calls,1),3)


class Indexer:
    def __init__(self, db_path, rpc):
        self.rpc = rpc
        self.lock = threading.RLock()
        db_path=Path(db_path)
        self.path=db_path.resolve()
        db_path.parent.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30, factory=MeasuredConnection)
        self.on_rewind=None
        self.deadline=threading.local()
        def expired():
            until=getattr(self.deadline,'until',0)
            return bool(until and time.monotonic()>until)
        self.db.set_progress_handler(expired,10000)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000;'+SCHEMA)
        self.db.commit()

    def tip(self):
        with self.lock:
            x=self.db.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
            return dict(x) if x else None

    def rewind(self):
        tip=self.tip()
        if not tip: return
        h=tip['height']
        with self.db:
            # Undo spending of earlier outputs before deleting this block's created outputs.
            self.db.execute('UPDATE outputs SET spent_by=NULL, spent_height=NULL WHERE spent_height=?',(h,))
            self.db.execute('DELETE FROM activity WHERE height=?',(h,))
            self.db.execute('DELETE FROM outputs WHERE height=?',(h,))
            self.db.execute('DELETE FROM txs WHERE height=?',(h,))
            self.db.execute('DELETE FROM blocks WHERE height=?',(h,))
        if self.on_rewind:self.on_rewind()
        LOG.warning('Rewound block at height %d (%s)',h,tip['hash'])

    def _match_tip(self):
        # Never hold the shared SQLite lock while waiting for Core RPC. This
        # keeps Explorer readers responsive during slow/disconnected nodes.
        remote_height=int(self.rpc.call('getblockcount'))
        while True:
            with self.lock:
                tip=self.db.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
                tip=dict(tip) if tip else None
            if tip is None:return
            if tip['height']>remote_height:
                with self.lock:
                    latest=self.db.execute('SELECT hash,height FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
                    if latest and latest['height']==tip['height'] and latest['hash']==tip['hash']:
                        self.rewind()
                continue
            try: canonical=self.rpc.call('getblockhash', tip['height'])
            except Exception as e:
                # RPC failure is not proof of a fork. Preserve database.
                raise RuntimeError('Cannot verify canonical chain tip; refusing to rewind') from e
            if canonical==tip['hash']:return
            with self.lock:
                latest=self.db.execute('SELECT hash,height FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
                if latest and latest['height']==tip['height'] and latest['hash']==tip['hash']:
                    self.rewind()

    def apply(self, height, blockhash, block, commit=True):
        prev=block.get('previousblockhash','0'*64)
        tip=self.tip()
        if tip and (tip['height']+1!=height or tip['hash']!=prev):
            raise ValueError('Block does not connect to indexed chain')
        if not tip and height!=0: raise ValueError('First index block must be genesis')
        timestamp=int(block['time'])
        with (self.db if commit else nullcontext()):
            self.db.execute('INSERT INTO blocks VALUES(?,?,?,?)',(height,blockhash,prev,timestamp))
            for tx in block['tx']:
                txid=tx['txid']; is_coinbase=int(any('coinbase' in v for v in tx['vin']))
                self.db.execute('INSERT INTO txs VALUES(?,?,?,?)',(txid,height,blockhash,timestamp))
                affected=set()
                for vin in tx['vin']:
                    if 'coinbase' in vin: continue
                    old=self.db.execute('SELECT address,spent_by FROM outputs WHERE txid=? AND vout=?',(vin['txid'],vin['vout'])).fetchone()
                    if old is None: raise RuntimeError('Missing input previous output %s:%s at block %s' % (vin['txid'],vin['vout'],height))
                    if old['spent_by'] is not None: raise RuntimeError('Double-spend in index: %s:%s' % (vin['txid'],vin['vout']))
                    self.db.execute('UPDATE outputs SET spent_by=?,spent_height=? WHERE txid=? AND vout=?',(txid,height,vin['txid'],vin['vout']))
                    if old['address']: affected.add(old['address'])
                for vout in tx['vout']:
                    sp=vout['scriptPubKey']; address=sp.get('address')
                    if not address and len(sp.get('addresses',[]))==1: address=sp['addresses'][0]
                    script=sp['hex'].lower()
                    self.db.execute('INSERT INTO outputs(txid,vout,height,value,script,address,coinbase) VALUES(?,?,?,?,?,?,?)',
                        (txid,int(vout['n']),height,sats(vout['value']),script,address,is_coinbase))
                    if address: affected.add(address)
                for a in affected: self.db.execute('INSERT OR IGNORE INTO activity VALUES(?,?,?)',(a,txid,height))
        return len(block['tx'])

    def sync_once(self, max_blocks=200, commit_every=25):
        """Fetch Core data without the DB lock; commit bounded groups atomically.

        Waitress readers are blocked only during the short SQLite write phase,
        not while getblockhash/getblock RPC calls are in flight.
        """
        if not 1 <= max_blocks <= 2000: raise ValueError('max_blocks must be 1..2000')
        if not 1 <= commit_every <= 100: raise ValueError('commit_every must be 1..100')
        self._match_tip()
        remote_height=int(self.rpc.call('getblockcount'))
        last=self.tip(); start=last['height']+1 if last else 0
        count=0
        stop=min(start+max_blocks, remote_height+1)
        for group_start in range(start, stop, commit_every):
            batch=[]
            for height in range(group_start,min(group_start+commit_every,stop)):
                bh=self.rpc.call('getblockhash',height)
                block=self.rpc.call('getblock',bh,2)
                if not isinstance(block,dict) or block.get('hash')!=bh:
                    raise RuntimeError('RPC returned wrong block hash')
                batch.append((height,bh,block))
            with self.lock:
                with self.db:
                    current=self.db.execute('SELECT height,hash FROM blocks ORDER BY height DESC LIMIT 1').fetchone()
                    expected_height=current['height']+1 if current else 0
                    if expected_height!=group_start:
                        raise RuntimeError('Indexed tip changed while fetching block batch; retrying next sync cycle')
                    for height,bh,block in batch:
                        self.apply(height,bh,block,commit=False)
                        count+=1
        return count

    def address_info(self, address, current_height):
        items=self.db.execute('SELECT txid,vout,value,height,script,coinbase FROM outputs WHERE address=? AND spent_by IS NULL ORDER BY height,txid,vout',(address,)).fetchall()
        utxos=[]
        for v in items:
            r=dict(v); r['confirmations']=max(0,current_height-r['height']+1)
            r['mature']=(r['height']!=0) and ((not r['coinbase']) or r['confirmations']>=100)
            utxos.append(r)
        return {'address':address,'confirmed_sats':sum(x['value'] for x in utxos),
                'spendable_sats':sum(x['value'] for x in utxos if x['mature']), 'utxos':utxos}

    def transaction_flows(self, txids, mempool_snapshot=None):
        """Return public input/output address lists for a bounded set of txids.

        Confirmed inputs are reconstructed from the existing outputs.spent_by
        relation. Mempool inputs are resolved against confirmed indexed outputs
        and the current in-memory mempool output snapshot. No raw transaction
        archive or additional persistent chain data is required.
        """
        clean=[]
        seen=set()
        for value in txids or []:
            txid=str(value or '').lower()
            if len(txid)==64 and all(c in '0123456789abcdef' for c in txid) and txid not in seen:
                clean.append(txid); seen.add(txid)
            if len(clean)>=120: break
        flows={txid:{'input_addresses':[],'output_addresses':[],'inputs':[],'outputs':[],
                    'input_count':0,'output_count':0,'inputs_unresolved':0} for txid in clean}
        if not clean: return flows

        marks=','.join('?' for _ in clean)
        for row in self.db.execute(
            f'SELECT spent_by,txid,vout,address,value,script FROM outputs WHERE spent_by IN ({marks}) ORDER BY spent_by,txid,vout', clean
        ):
            flow=flows.get(row['spent_by'])
            if flow is not None:
                item={'txid':row['txid'],'vout':int(row['vout']),'address':row['address'],
                      'value_sats':int(row['value']),'script':row['script']}
                flow['inputs'].append(item)
                flow['input_count']+=1
                if row['address']: flow['input_addresses'].append(row['address'])
        for row in self.db.execute(
            f'SELECT txid,vout,address,value,script FROM outputs WHERE txid IN ({marks}) ORDER BY txid,vout', clean
        ):
            flow=flows.get(row['txid'])
            if flow is not None:
                item={'vout':int(row['vout']),'address':row['address'],
                      'value_sats':int(row['value']),'script':row['script']}
                flow['outputs'].append(item)
                flow['output_count']+=1
                if row['address']: flow['output_addresses'].append(row['address'])

        snapshot=mempool_snapshot or {}
        pending=set((snapshot.get('txs') or {}).keys())
        input_outpoints=snapshot.get('input_outpoints') or {}
        mempool_outputs=snapshot.get('outputs_by_outpoint') or {}
        tx_output_addresses=snapshot.get('tx_output_addresses') or {}
        tx_output_details=snapshot.get('tx_output_details') or {}
        output_details_by_outpoint=snapshot.get('output_details_by_outpoint') or {}
        refs_by_tx={}
        needed_prev_txs=set()
        for txid in clean:
            if txid not in pending: continue
            refs=[]
            for ref in input_outpoints.get(txid,[]):
                try:
                    prev_txid=str(ref[0]).lower(); prev_vout=int(ref[1])
                except (TypeError,ValueError,IndexError):
                    continue
                if len(prev_txid)!=64 or any(c not in '0123456789abcdef' for c in prev_txid) or prev_vout<0:
                    continue
                refs.append((prev_txid,prev_vout))
                if (prev_txid,prev_vout) not in mempool_outputs:
                    needed_prev_txs.add(prev_txid)
            refs_by_tx[txid]=refs

        # Fetch previous outputs in bounded batches; this avoids one SQL query
        # per input and stays below SQLite's conservative bind-variable limit.
        prevout_map={}
        needed=sorted(needed_prev_txs)
        for start in range(0,len(needed),400):
            chunk=needed[start:start+400]
            chunk_marks=','.join('?' for _ in chunk)
            for row in self.db.execute(
                f'SELECT txid,vout,address,value,script FROM outputs WHERE txid IN ({chunk_marks})', chunk
            ):
                prevout_map[(row['txid'],int(row['vout']))]={
                    'txid':row['txid'],'vout':int(row['vout']),'address':row['address'],
                    'value_sats':int(row['value']),'script':row['script']}

        for txid in clean:
            if txid not in pending: continue
            flow=flows[txid]
            refs=refs_by_tx.get(txid,[])
            flow['input_count']=len(refs)
            for ref in refs:
                detail=output_details_by_outpoint.get(ref)
                if detail is None: detail=prevout_map.get(ref)
                address=(detail or {}).get('address') or mempool_outputs.get(ref)
                if detail:
                    flow['inputs'].append(dict(detail))
                else:
                    flow['inputs'].append({'txid':ref[0],'vout':ref[1],'address':address,'value_sats':None,'script':None})
                    flow['inputs_unresolved']+=1
                if address: flow['input_addresses'].append(address)
            pending_outputs=tx_output_details.get(txid,[])
            flow['output_count']=len(pending_outputs)
            for detail in pending_outputs:
                if isinstance(detail,dict): flow['outputs'].append(dict(detail))
            flow['output_addresses'].extend(
                a for a in tx_output_addresses.get(txid,[]) if isinstance(a,str) and a
            )

        # Stable de-duplication keeps responses compact while preserving order.
        for flow in flows.values():
            flow['input_addresses']=list(dict.fromkeys(flow['input_addresses']))[:256]
            flow['output_addresses']=list(dict.fromkeys(flow['output_addresses']))[:256]
            flow['inputs_truncated']=len(flow['inputs'])>256 or flow['input_count']>256
            flow['outputs_truncated']=len(flow['outputs'])>256 or flow['output_count']>256
            flow['inputs']=flow['inputs'][:256]
            flow['outputs']=flow['outputs'][:256]
        return flows


    def record_mempool_snapshot(self, snapshot):
        import json
        snapshot = snapshot or {}
        if snapshot.get('error'):
            raise ValueError('Cannot persist an errored mempool snapshot')
        if snapshot.get('coverage_complete') is not True:
            raise ValueError('Cannot persist a mempool snapshot without explicit complete coverage')
        txs=list(snapshot.get('txs',{}).values())
        from mempool import fee_histogram
        groups=snapshot.get('fee_histogram') or fee_histogram(txs)
        bins=[{k:v for k,v in group.items() if k!='label'} for group in groups]
        sampled=int(snapshot.get('updated') or time.time())
        with self.lock, self.db:
            # A retry in the same sampled second replaces that sample instead of
            # creating duplicate points that distort time-series charts.
            self.db.execute('DELETE FROM mempool_history WHERE sampled_at=?',(sampled,))
            self.db.execute('INSERT INTO mempool_history(sampled_at,tx_count,total_vsize,total_fee_sats,fee_bins_json) VALUES(?,?,?,?,?)',
                (sampled,len(txs),sum(int(x.get('vsize',0)) for x in txs),sum(int(x.get('fee_sats',0)) for x in txs),json.dumps(bins,separators=(',',':'))))
            # Avoid duplicate records when a scheduler retries within the same second.
            self.db.execute('DELETE FROM mempool_history WHERE id NOT IN (SELECT id FROM mempool_history ORDER BY sampled_at DESC,id DESC LIMIT 200000)')
            events=snapshot.get('events') or []
            if events:
                # Same-second sampler retries replace the event batch for that
                # timestamp, mirroring mempool_history de-duplication.
                self.db.execute('DELETE FROM mempool_events WHERE event_at=?',(sampled,))
            for event in events:
                txid=str(event.get('txid') or '').lower()
                if len(txid)!=64 or any(ch not in '0123456789abcdef' for ch in txid):
                    continue
                event_type=str(event.get('event_type') or 'unknown')
                replacement=event.get('replacement_txid')
                if event_type=='removed_unknown':
                    confirmed=self.db.execute('SELECT 1 FROM txs WHERE txid=?',(txid,)).fetchone()
                    if confirmed: event_type='confirmed'
                if replacement:
                    replacement=str(replacement).lower()
                    if len(replacement)!=64 or any(ch not in '0123456789abcdef' for ch in replacement):
                        replacement=None
                self.db.execute('INSERT INTO mempool_events(event_at,txid,event_type,replacement_txid) VALUES(?,?,?,?)',
                                (sampled,txid,event_type,replacement))
            self.db.execute('DELETE FROM mempool_events WHERE id NOT IN (SELECT id FROM mempool_events ORDER BY event_at DESC,id DESC LIMIT 100000)')

    def transaction_status(self,txid,current_height):
        r=self.db.execute('SELECT txid,height,block_hash,timestamp FROM txs WHERE txid=?',(txid,)).fetchone()
        if r:
            row=dict(r);row['confirmations']=max(0,current_height-row['height']+1)
            row['state']='confirmed';return row
        return None

    def history(self,address,limit=50,offset=0,*,with_balances=False):
        # Select the page before calculating its indexed credit and debit sums.
        # Skipped rows don't need any output or spend lookups.
        # apply() inserts txs sequentially in Core block order. Within a height
        # only their relative rowid order matters, including after a rewind.
        # Preserve the legacy wallet tie-breaker and payload.
        tie_breaker = 'indexed_order DESC' if with_balances else 'a.txid'
        rows=self.db.execute(f'''
            WITH page AS (
                SELECT a.address,a.txid,a.height,t.timestamp,t.rowid AS indexed_order
                FROM activity a JOIN txs t ON t.txid=a.txid
                WHERE a.address=?
                ORDER BY a.height DESC,{tie_breaker}
                LIMIT ? OFFSET ?
            )
            SELECT a.txid,a.height,a.timestamp,a.indexed_order,
              COALESCE((SELECT SUM(o.value) FROM outputs o
                        WHERE o.txid=a.txid AND o.address=a.address),0) AS received_sats,
              COALESCE((SELECT SUM(o.value) FROM outputs o
                        WHERE o.spent_by=a.txid AND o.address=a.address),0) AS sent_sats
            FROM page a
            ORDER BY a.height DESC,{tie_breaker}
        ''',(address,limit,offset)).fetchall()
        balance = None
        if rows and with_balances:
            if offset == 0:
                balance = self.db.execute(
                    'SELECT COALESCE(SUM(value),0) FROM outputs WHERE address=? AND spent_height IS NULL',
                    (address,)).fetchone()[0]
            else:
                # Reconstruct the UTXOs immediately after the first row of this
                # page. Only creations/spends at its exact height need a tx
                # order lookup. This avoids loading every preceding page.
                first = rows[0]
                balance = self.db.execute('''
                    SELECT COALESCE(SUM(o.value),0) FROM outputs o
                    WHERE o.address=:address
                      AND (o.spent_height IS NULL OR o.spent_height >= :height)
                      AND (o.height < :height OR (o.height = :height AND
                            (SELECT rowid FROM txs WHERE txid=o.txid) <= :position))
                      AND (o.spent_height IS NULL OR o.spent_height > :height OR
                            (SELECT rowid FROM txs WHERE txid=o.spent_by) > :position)
                ''', {'address':address,'height':first['height'],'position':first['indexed_order']}).fetchone()[0]
        result=[]
        for row in rows:
            item=dict(row)
            del item['indexed_order']
            item['received_sats']=int(item['received_sats'] or 0)
            item['sent_sats']=int(item['sent_sats'] or 0)
            item['net_sats']=item['received_sats']-item['sent_sats']
            if with_balances:
                item['balance_after_sats'] = balance
                balance -= item['net_sats']
            item['unconfirmed']=False
            result.append(item)
        return result

# A single SQLite connection is shared by Waitress readers and the indexer worker.
# Serialize each public operation, including multi-statement block transactions.
def _locked(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper
for _name in ('tip','rewind','apply','address_info','history','transaction_flows','transaction_status','record_mempool_snapshot'):
    setattr(Indexer, _name, _locked(getattr(Indexer,_name)))
