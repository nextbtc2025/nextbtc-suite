# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Verify Explorer DWG prediction against actual nextBTC Core block nBits.

The historical comparison uses each canonical block's actual nBits as the
consensus oracle for that candidate height. It also compares the current
candidate against getblocktemplate.bits. No wallet or signing RPC is used.
"""
import argparse
import configparser
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from explorer import predict_dgw, read_header_range, verify_template_bits

GENESIS='000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1'
POW_LIMITS={
    'main':'00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
    'test':'00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
    # Core's CDageSigNetParams uses the same genesis and PoW limit as main/test.
    'signet':'00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
}

class JsonRpc:
    def __init__(self,cfg):
        self.url=cfg.get('rpc','url')
        self.user=cfg.get('rpc','user',fallback='')
        self.password=cfg.get('rpc','password',fallback='')
        self.cookie=cfg.get('rpc','cookie_file',fallback='')
        self.timeout=cfg.getint('rpc','timeout',fallback=30)
        self.counter=0
    def call(self,method,*params):
        user,password=self.user,self.password
        if self.cookie:
            user,password=Path(self.cookie).read_text(encoding='utf-8').strip().split(':',1)
        import base64
        self.counter+=1
        payload=json.dumps({'jsonrpc':'1.0','id':self.counter,'method':method,'params':list(params)}).encode()
        auth=base64.b64encode(f'{user}:{password}'.encode()).decode()
        req=Request(self.url,data=payload,headers={'Content-Type':'application/json','Authorization':'Basic '+auth})
        try:
            with urlopen(req,timeout=self.timeout) as response: obj=json.loads(response.read().decode())
        except (HTTPError,URLError,TimeoutError) as exc:
            raise RuntimeError(f'RPC {method} failed: {exc}') from exc
        if obj.get('error'):
            raise RuntimeError(f'RPC {method} error: {obj["error"]}')
        return obj.get('result')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',default=str(ROOT/'config.ini'))
    ap.add_argument('--samples',type=int,default=1000,help='consecutive recent candidate heights to verify (1..10000)')
    ap.add_argument('--output',default=str(ROOT/'dwg_core_verification.json'))
    args=ap.parse_args()
    if not 1<=args.samples<=10000: ap.error('--samples must be 1..10000')
    cfg=configparser.ConfigParser();cfg.read(args.config,encoding='utf-8-sig')
    rpc=JsonRpc(cfg)
    started=time.time()
    chain=rpc.call('getblockchaininfo')
    chain_name=str(chain.get('chain','')).lower()
    if chain_name not in POW_LIMITS: raise SystemExit(f'Unsupported chain type: {chain_name}')
    genesis=rpc.call('getblockhash',0)
    if genesis!=GENESIS: raise SystemExit(f'Wrong nextBTC genesis: {genesis}')
    tip=int(rpc.call('getblockcount'))
    tip_hash_before=rpc.call('getblockhash',tip)
    first=max(1,tip-args.samples+1)
    candidates=set(range(first,tip+1))
    candidates.update(h for h in (1,24,25,55554,55555,55556) if 1<=h<=tip)
    needed=set(range(max(0,tip-24),tip+1))  # also load the live next-block window
    for candidate in candidates:
        needed.add(candidate)
        if candidate>=55555:
            needed.update(range(max(0,candidate-24),candidate))
    headers={}
    for height in sorted(needed):
        block_hash=rpc.call('getblockhash',height)
        header=rpc.call('getblockheader',block_hash,True)
        if int(header.get('height',-1))!=height or str(header.get('hash','')).lower()!=block_hash.lower():
            raise SystemExit(f'Core returned inconsistent header at height {height}')
        headers[height]={'height':height,'time':int(header['time']),'bits':str(header['bits']).lower()}
    results=[]
    for candidate in sorted(candidates):
        previous=[headers[h] for h in range(candidate-1,max(-1,candidate-25),-1) if h in headers]
        prediction=predict_dgw(previous,candidate,pow_limit_hex=POW_LIMITS[chain_name])
        actual=headers[candidate]['bits'].lower().removeprefix('0x').zfill(8)
        predicted=str(prediction.get('predicted_nbits','')).lower().removeprefix('0x').zfill(8)
        results.append({'height':candidate,'predicted_nbits':predicted,'actual_nbits':actual,
                        'matched':bool(prediction.get('available') and predicted==actual),
                        'phase':prediction.get('phase'),'reason':prediction.get('reason')})
    mismatches=[r for r in results if not r['matched']]
    if rpc.call('getblockhash',tip)!=tip_hash_before:
        raise SystemExit('Historical sample was reorganized during verification; rerun')
    # A normal tip extension during a large history scan does not invalidate
    # the history. Fetch a fresh candidate and bind it to its actual parent.
    for _ in range(3):
        template=rpc.call('getblocktemplate',{'rules':['segwit']})
        next_candidate=int(template['height'])
        parent=next_candidate-1
        recent=read_header_range(rpc,max(0,parent-23),parent)
        parent_hash=recent[0]['hash']
        next_prediction=predict_dgw(recent,next_candidate,pow_limit_hex=POW_LIMITS[chain_name])
        comparison=verify_template_bits(next_prediction,template,next_candidate,parent_hash)
        if comparison['available'] and rpc.call('getbestblockhash')==parent_hash:
            break
    else:
        raise SystemExit('Unable to verify a template tied to the current canonical tip')
    template_height=next_candidate
    template_bits=comparison['template_nbits']
    template_match=comparison['matched']
    report={'tool':'nextBTC DWG/Core verifier','chain':chain_name,'genesis':genesis,'tip_height':tip,'tip_hash':tip_hash_before,
            'candidate_range':[min(candidates),max(candidates)] if candidates else None,'candidate_count':len(results),
            'historical_matches':len(results)-len(mismatches),'historical_mismatches':mismatches,
            'next_candidate_height':next_candidate,'predicted_next_nbits':next_prediction.get('predicted_nbits'),
            'template_parent_hash':parent_hash,'getblocktemplate_height':template_height,'getblocktemplate_bits':template_bits,
            'getblocktemplate_match':bool(template_match),'elapsed_seconds':round(time.time()-started,3),
            'verified_at_unix':int(time.time())}
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    if mismatches or not template_match: raise SystemExit(2)

if __name__=='__main__': main()
