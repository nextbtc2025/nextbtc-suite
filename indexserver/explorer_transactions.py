# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Resolve a decoded transaction against canonical and observed previous outputs."""
from decimal import Decimal


def describe_transaction(indexer, tx, snapshot):
    """Keep Core vin order. Only known input values may contribute to a total."""
    pending_outputs = (snapshot or {}).get('output_details_by_outpoint', {})
    refs = [(i['txid'], i['vout']) for i in tx['vin'] if 'coinbase' not in i]
    resolved = {ref: pending_outputs[ref] for ref in refs if ref in pending_outputs}
    missing = list(dict.fromkeys(ref for ref in refs if ref not in resolved))
    with indexer.lock:
        for start in range(0, len(missing), 400):
            group = missing[start:start + 400]
            marks = ','.join('(?,?)' for _ in group)
            rows = indexer.db.execute(
                f'WITH refs(t,n) AS (VALUES {marks}) '
                'SELECT o.txid,o.vout,o.value AS value_sats,o.address,o.script '
                'FROM refs CROSS JOIN outputs o ON o.txid=refs.t AND o.vout=refs.n',
                [v for ref in group for v in ref])
            for row in rows:
                resolved[(row['txid'], row['vout'])] = dict(row)
    coinbase = any('coinbase' in i for i in tx['vin'])
    inputs = []
    for item in tx['vin']:
        if 'coinbase' in item:
            inputs.append({'coinbase': True})
            continue
        ref = (item['txid'], item['vout'])
        inputs.append({'address': None, 'value_sats': None, 'script': None,
                       **resolved.get(ref, {}), 'txid': ref[0], 'vout': ref[1]})
    outputs = []
    for item in tx['vout']:
        script = item['scriptPubKey']
        addresses = script.get('addresses') or []
        address = script.get('address') or (addresses[0] if len(addresses) == 1 else None)
        outputs.append({'vout': item['n'], 'value_sats': int(Decimal(str(item['value'])) * 100000000),
                        'address': address, 'script': script['hex']})
    unresolved = sum(i['value_sats'] is None for i in inputs if not i.get('coinbase'))
    total_input = None if coinbase or unresolved else sum(i['value_sats'] for i in inputs)
    total_output = sum(o['value_sats'] for o in outputs)
    fee = total_input - total_output if total_input is not None else None
    if not coinbase and fee is None:
        fee = ((snapshot or {}).get('txs', {}).get(tx['txid']) or {}).get('fee_sats')
    if fee is not None and fee < 0:
        raise ValueError('Resolved inputs below total outputs')
    vsize = tx.get('vsize')
    if vsize is None and tx.get('weight') is not None:
        vsize = (int(tx['weight']) + 3) // 4
    return {'inputs': inputs, 'outputs': outputs, 'coinbase': coinbase, 'vsize': vsize,
            'unresolved_inputs': unresolved, 'total_input_sats': total_input, 'total_output_sats': total_output,
            'fee_sats': fee, 'feerate_sat_vb': fee / vsize if fee is not None and vsize else None}
