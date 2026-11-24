# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Bounded mempool snapshot, separate from persistent canonical-chain state.

Never applies unconfirmed spends to the durable SQLite index. If the RPC fails,
public endpoints mark mempool data as stale and do not authorize new spending.
"""
import threading
import time
from decimal import Decimal, InvalidOperation

COIN=Decimal('100000000')
def sat(value): return int(Decimal(str(value))*COIN)


def fee_histogram(txs):
    """Aggregate every transaction into a non-overlapping fee-rate bucket.

    Rates are sat/vB. The open-ended final bucket prevents high-fee outliers
    from silently disappearing from visualizer totals.
    """
    groups=[{'label':'<1','min':0,'max':1},
            {'label':'1-2','min':1,'max':2},
            {'label':'2-5','min':2,'max':5},
            {'label':'5-10','min':5,'max':10},
            {'label':'10-25','min':10,'max':25},
            {'label':'25-1M','min':25,'max':1000000},
            {'label':'1M+','min':1000000,'max':None}]
    for group in groups:
        group.update(count=0,vsize=0,fee_sats=0)
    for tx in (txs or {}).values() if isinstance(txs,dict) else (txs or []):
        size=max(0,int(tx.get('vsize',0) or 0))
        fee=max(0,int(tx.get('fee_sats',0) or 0))
        rate=fee/max(1,size)
        for group in groups:
            if rate>=group['min'] and (group['max'] is None or rate<group['max']):
                group['count']+=1
                group['vsize']+=size
                group['fee_sats']+=fee
                break
    return groups

class MempoolTracker:
    def __init__(self, rpc, max_txs=12000, expected_genesis=None):
        self.expected_genesis = expected_genesis
        self.rpc=rpc
        if not isinstance(max_txs,int) or not 1<=max_txs<=100000:
            raise ValueError('max_txs must be an integer in 1..100000')
        self.max_txs=max_txs
        self.lock=threading.RLock()
        self.generation=0
        self.raw_cache={}
        self.snapshot={'txs':{},'spends':{},'received':{},'activity':{},'children':{},'updated':0,'error':'Not yet synchronized'}

    def invalidate(self):
        with self.lock:
            self.generation+=1
            self.snapshot={'txs':{},'spends':{},'received':{},'activity':{},'children':{},
                           'updated':0,'error':'Waiting for post-reorg mempool sample'}

    def refresh(self):
        with self.lock:
            generation=self.generation
        try:
            if self.expected_genesis and self.rpc.call('getblockhash', 0) != self.expected_genesis:
                raise RuntimeError('Mempool RPC genesis does not match nextBTC')
            entries=self.rpc.call('getrawmempool',True)
            if not isinstance(entries,dict) or len(entries)>self.max_txs:
                raise RuntimeError('Mempool too large for safe indexing')
            # Fetch all unconfirmed transactions, not just newly seen ones,
            # so a restart or mining event cannot leave stale spend markers.
            txs={}
            spends={}
            received={}
            activity={}
            input_outpoints={}
            outputs_by_outpoint={}
            tx_output_addresses={}
            tx_output_details={}
            output_details_by_outpoint={}
            fee_rates=[]
            raw_cache={}
            children={}
            # First refresh can contain thousands of entries. Fetch uncached
            # raw transactions using bounded JSON-RPC batches where supported,
            # avoiding one HTTP round trip per transaction.
            missing=[];seen_ids=set()
            for raw_txid in entries:
                txid=str(raw_txid).lower()
                if len(txid)!=64 or any(ch not in '0123456789abcdef' for ch in txid):
                    raise RuntimeError('Mempool RPC returned invalid txid')
                if txid in seen_ids:raise RuntimeError('Mempool RPC returned duplicate normalized txid')
                seen_ids.add(txid)
                if txid not in self.raw_cache:missing.append((raw_txid,txid))
            prefetched={}
            if missing:
                if callable(getattr(self.rpc,'batch',None)):
                    results=self.rpc.batch('getrawtransaction',[[raw_txid,True] for raw_txid,_ in missing],batch_size=100)
                    if len(results)!=len(missing):raise RuntimeError('Core RPC batch result count mismatch')
                    prefetched={txid:tx for (_,txid),tx in zip(missing,results)}
                else:
                    prefetched={txid:self.rpc.call('getrawtransaction',raw_txid,True) for raw_txid,txid in missing}
            for raw_txid, meta in entries.items():
                if not isinstance(meta,dict):raise RuntimeError('Mempool RPC returned malformed entry metadata')
                txid=str(raw_txid).lower()
                if len(txid)!=64 or any(ch not in '0123456789abcdef' for ch in txid):
                    raise RuntimeError('Mempool RPC returned invalid txid')
                if txid in txs:
                    raise RuntimeError('Mempool RPC returned duplicate normalized txid')
                tx=self.raw_cache.get(txid)
                if tx is None:tx=prefetched.get(txid)
                if tx is None:raise RuntimeError('Core did not return raw transaction for '+txid)
                raw_cache[txid]=tx
                if not isinstance(tx,dict) or str(tx.get('txid','')).lower()!=txid:
                    raise RuntimeError('Mempool RPC returned mismatched txid')
                fee_meta=meta.get('fees') or {}
                if not isinstance(fee_meta,dict):raise RuntimeError('Mempool RPC returned malformed fee metadata')
                vsize=int(meta.get('vsize',0) or 0)
                if vsize<=0:raise RuntimeError('Mempool RPC returned invalid transaction vsize')
                base_raw=fee_meta.get('base',meta.get('fee'))
                if base_raw is None:
                    raise RuntimeError('Mempool RPC omitted transaction fee')
                base_fee=sat(base_raw)
                if base_fee<0:raise RuntimeError('Mempool RPC returned negative transaction fee')
                if 'ancestor' in fee_meta:
                    ancestor_fee=sat(fee_meta.get('ancestor') or 0)
                elif 'ancestorfees' in meta:
                    ancestor_fee=int(meta.get('ancestorfees') or 0)  # legacy Core field is already satoshis
                else:ancestor_fee=base_fee
                if 'descendant' in fee_meta:
                    descendant_fee=sat(fee_meta.get('descendant') or 0)
                elif 'descendantfees' in meta:
                    descendant_fee=int(meta.get('descendantfees') or 0)
                else:descendant_fee=base_fee
                if ancestor_fee<0 or descendant_fee<0:raise RuntimeError('Mempool RPC returned negative package fee')
                ancestor_size=int(meta.get('ancestorsize',vsize) or vsize)
                descendant_size=int(meta.get('descendantsize',vsize) or vsize)
                ancestor_metrics_available=(('ancestor' in fee_meta or 'ancestorfees' in meta) and meta.get('ancestorsize') is not None and ancestor_size>0)
                descendant_metrics_available=(('descendant' in fee_meta or 'descendantfees' in meta) and meta.get('descendantsize') is not None and descendant_size>0)
                if ancestor_size<=0:ancestor_size=vsize
                if descendant_size<=0:descendant_size=vsize
                signal=str(meta.get('bip125-replaceable')).lower().strip()
                replaceable={'true':True,'yes':True,'1':True,'false':False,'no':False,'0':False}.get(signal)
                txs[txid]={'txid':txid,'time':int(meta.get('time',0)),
                           'vsize':vsize,'weight':int(meta.get('weight',0) or 0),
                           'fee_sats':base_fee,
                           'modified_fee_sats':sat(fee_meta.get('modified',meta.get('modifiedfee',base_raw)) or 0),
                           'ancestor_fee_sats':ancestor_fee,'descendant_fee_sats':descendant_fee,
                           'ancestor_vsize':ancestor_size,'descendant_vsize':descendant_size,
                           'ancestor_feerate_sat_vb':(ancestor_fee/max(1,ancestor_size) if ancestor_metrics_available else base_fee/max(1,vsize)),
                           'descendant_feerate_sat_vb':(descendant_fee/max(1,descendant_size) if descendant_metrics_available else base_fee/max(1,vsize)),
                           'ancestor_metrics_available':ancestor_metrics_available,
                           'descendant_metrics_available':descendant_metrics_available,
                           'ancestorcount':int(meta.get('ancestorcount',1) or 1),
                           'descendantcount':int(meta.get('descendantcount',1) or 1),
                           'replaceable':replaceable,
                           'depends':[str(parent).lower() for parent in (meta.get('depends') or [])]}
                for parent in txs[txid]['depends']:
                    children.setdefault(parent,[]).append(txid)
                # getrawmempool(true) supplies fee.base in BTC and vsize in vbytes.
                # Keep only sane positive fee rates in the in-memory snapshot.
                try:
                    fee_meta=meta.get('fees') or {}
                    fee_base=Decimal(str(fee_meta.get('base',meta.get('fee'))))
                    vsize=int(meta.get('vsize',0))
                    rate=(fee_base*Decimal(100000000))/Decimal(vsize) if vsize>0 else Decimal(0)
                    if fee_base.is_finite() and fee_base>0 and rate.is_finite() and Decimal('0')<rate<=Decimal('1000'):
                        fee_rates.append(float(rate))
                except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
                    pass
                tx_inputs=[]
                if not isinstance(tx.get('vin',[]),list) or not isinstance(tx.get('vout',[]),list):
                    raise RuntimeError('Core returned malformed transaction inputs/outputs')
                for vin in tx.get('vin',[]):
                    if not isinstance(vin,dict):raise RuntimeError('Core returned malformed transaction input')
                    if 'txid' in vin and 'vout' in vin:
                        k=(str(vin['txid']).lower(),int(vin['vout']))
                        if k in spends: raise RuntimeError('Duplicate mempool spend')
                        spends[k]=txid
                        tx_inputs.append(k)
                input_outpoints[txid]=tx_inputs
                output_addresses=[]
                for vout in tx.get('vout',[]):
                    if not isinstance(vout,dict):raise RuntimeError('Core returned malformed transaction output')
                    sp=vout.get('scriptPubKey',{})
                    if not isinstance(sp,dict):sp={}
                    address=sp.get('address')
                    addresses=sp.get('addresses') or []
                    if not address and isinstance(addresses,list) and len(addresses)==1:address=addresses[0]
                    vout_n=int(vout['n'])
                    detail={'txid':txid,'vout':vout_n,'address':str(address) if address else None,
                            'value_sats':sat(vout['value']),'script':sp.get('hex','').lower()}
                    # Retain every prevout, including non-address scripts, so a
                    # mempool child can resolve its parent's input value/script.
                    output_details_by_outpoint[(txid,vout_n)]=detail
                    if address:
                        address=str(address)
                        outputs_by_outpoint[(txid,vout_n)]=address
                        output_addresses.append(address)
                        row={'txid':txid,'vout':vout_n,'value':sat(vout['value']),
                             'script':sp['hex'].lower(),'height':-1,'confirmations':0,
                             'mature':False,'unconfirmed':True}
                        received.setdefault(address,[]).append(row)
                        activity.setdefault(address,set()).add(txid)
                tx_output_addresses[txid]=output_addresses
                details=[]
                for vout in tx.get('vout',[]):
                    if not isinstance(vout,dict):raise RuntimeError('Core returned malformed transaction output detail')
                    sp=vout.get('scriptPubKey',{})
                    if not isinstance(sp,dict):sp={}
                    address=sp.get('address')
                    addresses=sp.get('addresses') or []
                    if not address and isinstance(addresses,list) and len(addresses)==1:
                        address=addresses[0]
                    details.append({'vout':int(vout['n']),'address':address,
                                    'value_sats':sat(vout['value']),
                                    'script':sp.get('hex','').lower()})
                tx_output_details[txid]=details
            histogram=fee_histogram(txs)
            with self.lock:
                if generation!=self.generation:
                    raise RuntimeError('Chain changed during mempool refresh')
                previous=self.snapshot
                previous_txs=previous.get('txs') or {}
                previous_inputs=previous.get('input_outpoints') or {}
                # The first successful poll is a baseline, not a burst of new
                # transactions. Only emit deltas after one complete prior view.
                baseline_ready=bool(previous.get('updated')) and not bool(previous.get('error')) and bool(previous.get('coverage_complete'))
                events=[]
                if baseline_ready:
                    for txid in txs.keys()-previous_txs.keys():
                        events.append({'txid':txid,'event_type':'added','replacement_txid':None})
                    removed=previous_txs.keys()-txs.keys()
                    for old_txid in removed:
                        replacement_ids=set()
                        for outpoint in previous_inputs.get(old_txid,[]):
                            spender=spends.get(tuple(outpoint))
                            if spender and spender!=old_txid:
                                replacement_ids.add(spender)
                        if replacement_ids:
                            for replacement_txid in sorted(replacement_ids):
                                events.append({'txid':old_txid,'event_type':'replaced','replacement_txid':replacement_txid})
                        else:
                            events.append({'txid':old_txid,'event_type':'removed_unknown','replacement_txid':None})
                self.raw_cache=raw_cache
                self.snapshot={'fee_histogram':histogram,'txs':txs,'spends':spends,'received':received,'activity':activity,
                               'input_outpoints':input_outpoints,'children':children,
                               'outputs_by_outpoint':outputs_by_outpoint,
                               'tx_output_addresses':tx_output_addresses,
                               'tx_output_details':tx_output_details,
                               'output_details_by_outpoint':output_details_by_outpoint,
                               'fee_rates':fee_rates,'events':events,'updated':time.time(),'error':None,
                               'coverage_complete':True,'core_count':len(entries),'indexed_count':len(txs)}
        except Exception as exc:
            with self.lock:
                self.snapshot={**self.snapshot,'error':str(exc)}
            raise

    def get(self):
        with self.lock:
            snap=self.snapshot
            # Copy top-level structures but never modify any inner entries.
            return dict(snap)
