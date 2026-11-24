# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""nextBTC Index Server: isolated Wallet API and Explorer HTTP services."""
import configparser, json, logging, os, re, sys, threading, time
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from flask import send_from_directory
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from flask import Flask, request, jsonify
import secrets
from explorer_cache import ExplorerCache
try:
    from .mempool import MempoolTracker, fee_histogram
except ImportError:
    from mempool import MempoolTracker, fee_histogram
try:
    from .indexer import Indexer
    from .explorer_transactions import describe_transaction
    from .explorer_chain_data import decode_op_return_script, address_balance_buckets, cumulative_scheduled_issuance_sats, maximum_scheduled_issuance_sats, block_subsidy_sats, INITIAL_SUBSIDY_SATS, SUBSIDY_HALVING_INTERVAL, NOMINAL_MAX_SUPPLY_SATS
    from .explorer import POW_LIMIT_HEX, PAST_BLOCKS, predict_dgw, compact_to_target, verify_template_bits, read_header_range, network_series
except ImportError:
    from indexer import Indexer
    from explorer_transactions import describe_transaction
    from explorer_chain_data import decode_op_return_script, address_balance_buckets, cumulative_scheduled_issuance_sats, maximum_scheduled_issuance_sats, block_subsidy_sats, INITIAL_SUBSIDY_SATS, SUBSIDY_HALVING_INTERVAL, NOMINAL_MAX_SUPPLY_SATS
    from explorer import POW_LIMIT_HEX, PAST_BLOCKS, predict_dgw, compact_to_target, verify_template_bits, read_header_range, network_series

LOG=logging.getLogger('nextbtc-index')
request_budget=threading.local()
GENESIS='000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1'
BASE=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
# PyInstaller one-file extracts bundled read-only assets into _MEIPASS, while
# mutable config/database files must remain beside the executable.
RESOURCE_BASE=Path(getattr(sys,'_MEIPASS',BASE))
EXPLORER_ASSETS=RESOURCE_BASE/'web'/'explorer'
CONFIG=BASE/'config.ini'
DEFAULTS={'server':{'host':'127.0.0.1','port':'8777','cors_origins':'null,http://localhost:8777,http://127.0.0.1:8777'},
          'explorer':{'host':'127.0.0.1','port':'8778','cors_origins':'null,http://localhost:8778,http://127.0.0.1:8778','admin_token':'','read_limit_per_minute':'300','heavy_limit_per_minute':'60'},
          'rpc':{'url':'http://127.0.0.1:8554','user':'','password':'','cookie_file':'','timeout':'30','max_retries':'4','retry_delay':'0.4','retry_max_delay':'5','pool_size':'4'},
          'index':{'database':'index.db','poll_seconds':'5','batch_size':'200','commit_every':'25','mempool_poll_seconds':'10','mempool_max_txs':'12000'},'fees':{'fallback_sat_vb':'1.0','mempool_min_samples':'5'},'logging':{'level':'INFO'}}

def load_config(path=CONFIG):
    cp=configparser.ConfigParser()
    cp.read_dict(DEFAULTS)
    if path.exists(): cp.read(path,encoding='utf-8-sig')
    else:
        with open(path,'w',encoding='utf-8') as f: cp.write(f)
        try: os.chmod(path,0o600)
        except OSError: pass
    return cp

class CoreRPCError(RuntimeError):
    def __init__(self, error):
        super().__init__('Core RPC error: ' + str(error))
        self.code = error.get('code') if isinstance(error, dict) else None


class RPC:
    """Thread-local keep-alive RPC sessions. Only read-only calls are retried.

    Requests Session is not shared across threads: the sync worker and the
    API worker each get their own connection pool. One session reuses its TCP
    connection across successive getblockhash/getblock requests.
    """
    READ_ONLY = frozenset({
        'getblockhash', 'getblock', 'getblockcount', 'getblockchaininfo',
        'getblockheader', 'getrawtransaction', 'getmempoolinfo',
        'getrawmempool', 'gettxout', 'estimatesmartfee', 'getnetworkinfo',
        'getnetworkhashps', 'getdifficulty', 'getblocktemplate', 'validateaddress',
    })

    def __init__(self, config):
        self.url=config.get('rpc','url');self.timeout=config.getfloat('rpc','timeout')
        self.user=config.get('rpc','user');self.password=config.get('rpc','password')
        self.cookie=config.get('rpc','cookie_file')
        self.max_retries=config.getint('rpc','max_retries',fallback=4)
        self.retry_delay=config.getfloat('rpc','retry_delay',fallback=0.4)
        self.retry_max_delay=config.getfloat('rpc','retry_max_delay',fallback=5)
        self.pool_size=config.getint('rpc','pool_size',fallback=4)
        if not 0<=self.max_retries<=10: raise ValueError('RPC max_retries must be 0..10')
        if not 0<=self.retry_delay<=30 or not 0<=self.retry_max_delay<=120:
            raise ValueError('Invalid RPC retry delay')
        if not 1<=self.pool_size<=32: raise ValueError('RPC pool_size must be 1..32')
        parsed=urlparse(self.url)
        if parsed.scheme not in ('http','https') or not parsed.hostname: raise ValueError('Bad RPC URL')
        self._local=threading.local()

    def _session(self):
        session=getattr(self._local,'session',None)
        if session is None:
            session=requests.Session()
            # No urllib3 automatic retries, especially not for POST broadcasts.
            adapter=HTTPAdapter(pool_connections=self.pool_size,pool_maxsize=self.pool_size,
                                pool_block=True,max_retries=0)
            session.mount('http://',adapter)
            session.mount('https://',adapter)
            # Do not pick up environment proxy settings for local/private RPC.
            session.trust_env=False
            self._local.session=session
        return session

    def _reset_session(self):
        session=getattr(self._local,'session',None)
        if session is not None:
            session.close()
            self._local.session=None

    def transport_timeout(self):
        deadline=getattr(request_budget,'deadline',0)
        if not deadline:return self.timeout
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Explorer request time budget exceeded')
        return min(self.timeout,remaining)

    def call(self,method,*params):
        user,password=self.user,self.password
        if self.cookie:
            user,password=Path(self.cookie).read_text(encoding='utf-8').strip().split(':',1)
        safe_to_retry=method in self.READ_ONLY
        max_attempts=1+(self.max_retries if safe_to_retry else 0)
        for attempt in range(max_attempts):
            try:
                with self._session().post(
                    self.url,
                    json={'jsonrpc':'1.0','id':'nextbtc-index','method':method,'params':list(params)},
                    auth=(user,password),timeout=self.transport_timeout(),
                    headers={'Accept':'application/json'},
                ) as response:
                    # HTTP 500 may carry an RPC-level error; do not replay it.
                    if response.status_code >= 400:
                        try: obj=response.json()
                        except ValueError: obj=None
                        if isinstance(obj,dict) and obj.get('error'):
                            raise CoreRPCError(obj['error'])
                    response.raise_for_status()
                    obj=response.json()
                    if not isinstance(obj,dict): raise RuntimeError('Malformed Core RPC response')
                    if obj.get('error'): raise CoreRPCError(obj['error'])
                    if 'result' not in obj: raise RuntimeError('Core RPC missing result')
                    return obj['result']
            except (requests.ConnectionError,requests.Timeout) as exc:
                # A disconnected persistent socket must not be kept in the pool.
                self._reset_session()
                if attempt+1>=max_attempts:
                    raise RuntimeError(f'Core RPC connection failed ({method}, {attempt+1} attempt(s))') from exc
                delay=min(self.retry_max_delay,self.retry_delay*(2**attempt))
                LOG.warning('Transient Core RPC failure for %s; retry %d/%d in %.2fs: %s',
                            method,attempt+1,max_attempts-1,delay,type(exc).__name__)
                if delay: time.sleep(delay)
            except requests.RequestException as exc:
                # Do not retry HTTP errors such as authentication failures.
                raise RuntimeError(f'Core RPC HTTP error ({method}): {type(exc).__name__}') from exc

    def batch(self, method, params_list, batch_size=100):
        """Execute bounded JSON-RPC batches for explicitly read-only methods."""
        if method not in self.READ_ONLY:
            raise ValueError('RPC batch is restricted to read-only methods')
        if not 1<=batch_size<=250:
            raise ValueError('RPC batch_size must be 1..250')
        output=[]
        for offset in range(0,len(params_list),batch_size):
            chunk=params_list[offset:offset+batch_size]
            ids=[f'nextbtc-index-batch-{offset+i}' for i in range(len(chunk))]
            payload=[{'jsonrpc':'1.0','id':ids[i],'method':method,'params':list(params)} for i,params in enumerate(chunk)]
            user,password=self.user,self.password
            if self.cookie:
                user,password=Path(self.cookie).read_text(encoding='utf-8').strip().split(':',1)
            attempts=1+self.max_retries
            for attempt in range(attempts):
                try:
                    with self._session().post(self.url,json=payload,auth=(user,password),timeout=self.transport_timeout(),
                                              headers={'Accept':'application/json'}) as response:
                        response.raise_for_status()
                        body=response.json()
                    if not isinstance(body,list):
                        raise RuntimeError('Malformed Core JSON-RPC batch response')
                    by_id={str(item.get('id')):item for item in body if isinstance(item,dict) and 'id' in item}
                    if len(by_id)!=len(ids):
                        raise RuntimeError('Core JSON-RPC batch response count/id mismatch')
                    chunk_results=[]
                    for rid in ids:
                        item=by_id.get(rid)
                        if not isinstance(item,dict) or item.get('error') or 'result' not in item:
                            raise RuntimeError('Core JSON-RPC batch item failed: '+str((item or {}).get('error'))[:180])
                        chunk_results.append(item['result'])
                    output.extend(chunk_results)
                    break
                except (requests.ConnectionError,requests.Timeout) as exc:
                    self._reset_session()
                    if attempt+1>=attempts:
                        raise RuntimeError(f'Core RPC batch connection failed ({method})') from exc
                    delay=min(self.retry_max_delay,self.retry_delay*(2**attempt))
                    if delay:time.sleep(delay)
                except requests.RequestException as exc:
                    raise RuntimeError(f'Core RPC batch HTTP error ({method}): {type(exc).__name__}') from exc
        return output

ADDRESS=re.compile(r'^[123][1-9A-HJ-NP-Za-km-z]{24,60}$|^bc1[ac-hj-np-z02-9]{8,90}$')
HEXTX=re.compile(r'^[0-9a-fA-F]+$')

# Core chainparams uses Base58Check and bc/tb/bcrt witness addresses.
# Wallet input rules remain those accepted by the existing wallet API.
def explorer_address_format(value):
    return bool(re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{26,35}',value) or
                (len(value)<=90 and (value.islower() or value.isupper()) and
                 re.fullmatch(r'(?:bc|tb|bcrt)1[ac-hj-np-z02-9]{8,}',value.lower())))

def make_app(config,indexer,rpc,status,mempool=None,service='combined'):
    """Build a wallet-only, explorer-only, or combined Flask app.

    The production launcher creates two isolated Flask apps over the same
    Indexer/RPC/Mempool objects. The combined default remains for backwards
    compatibility with existing in-process integrations and tests.
    """
    from flask import Blueprint, g
    if service not in {'combined','wallet','explorer'}:
        raise ValueError('service must be combined, wallet, or explorer')
    app=Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH']=250000
    performance=ExplorerCache()
    started=time.monotonic()
    slots=threading.BoundedSemaphore(6)
    wallet_routes = Blueprint('wallet', __name__)
    explorer_routes = Blueprint('explorer', __name__)
    app.config['NEXTBTC_SERVICE']=service
    # Bounded in-process response cache for public, read-only Explorer data.
    from statistics_worker import StatisticsWorker
    statistics=StatisticsWorker(indexer) if service!='wallet' else None
    app.extensions['statistics_worker']=statistics
    api_cache={}
    api_cache_lock=threading.RLock()
    def cache_get(key):
        now=time.monotonic()
        with api_cache_lock:
            item=api_cache.get(key)
            if not item:return None
            if item[0]<=now:
                api_cache.pop(key,None);return None
            return item[1]
    def cache_put(key,value,ttl):
        now=time.monotonic()
        with api_cache_lock:
            if len(api_cache)>=512:
                for old in list(api_cache)[:128]:api_cache.pop(old,None)
            api_cache[key]=(now+ttl,value)
        return value
    def query_int(name, default=None):
        raw=request.args.get(name)
        if raw is None:return default
        try:
            text=str(raw).strip()
            if not re.fullmatch(r'[+-]?\d+',text):return None
            return int(text)
        except (TypeError,ValueError):return None
    limits={}
    limit_lock=threading.Lock()
    # Fee estimates use Core history when available, then the in-memory
    # mempool distribution, and finally a configurable low-fee fallback.
    fee_cache={'updated':0.0,'payload':None}
    fee_lock=threading.Lock()
    fee_tiers=(('low',24,0.25),('medium',6,0.60),('high',2,0.90))
    try:
        fallback_rate=Decimal(str(config.get('fees','fallback_sat_vb',fallback='1.0')))
        if not fallback_rate.is_finite() or fallback_rate<Decimal('1') or fallback_rate>Decimal('1000'):
            raise ValueError('fallback fee out of range')
    except Exception:
        fallback_rate=Decimal('1.0')
    try:
        mempool_min_samples=max(1,min(1000,config.getint('fees','mempool_min_samples',fallback=5)))
    except Exception:
        mempool_min_samples=5

    def ceil_rate(value):
        return value.quantize(Decimal('0.01'),rounding=ROUND_CEILING)

    def core_minimums():
        relay=Decimal('0')
        pool=Decimal('0')
        try:
            info=rpc.call('getmempoolinfo')
            if isinstance(info,dict):
                for key in ('minrelaytxfee','mempoolminfee'):
                    raw=info.get(key)
                    if raw is not None:
                        val=Decimal(str(raw))*Decimal('100000')
                        if val.is_finite() and val>0:
                            if key=='minrelaytxfee': relay=max(relay,val)
                            else: pool=max(pool,val)
        except Exception as exc:
            LOG.warning('Unable to read mempool fee floors: %s',exc)
        try:
            info=rpc.call('getnetworkinfo')
            raw=info.get('relayfee') if isinstance(info,dict) else None
            if raw is not None:
                val=Decimal(str(raw))*Decimal('100000')
                if val.is_finite() and val>0: relay=max(relay,val)
        except Exception as exc:
            LOG.warning('Unable to read network relay fee: %s',exc)
        return relay,pool

    def mempool_fee_tiers():
        snap=mempool.get() if mempool else {}
        # A failed refresh must not make old fee samples look current.
        if not snap or snap.get('error'):
            return None,0
        rates=snap.get('fee_rates') or []
        clean=[]
        for value in rates:
            try:
                d=Decimal(str(value))
                if d.is_finite() and d>0 and d<=Decimal('1000'): clean.append(d)
            except Exception:
                continue
        clean.sort()
        if len(clean)<mempool_min_samples:
            return None,len(clean)
        def percentile(p):
            # Nearest-rank percentile, deterministic for small low-volume pools.
            index=max(0,min(len(clean)-1,int((len(clean)-1)*p+0.999999)))
            return clean[index]
        return {name:ceil_rate(percentile(p)) for name,_,p in fee_tiers},len(clean)

    def fee_estimates():
        now=time.time()
        with fee_lock:
            if fee_cache['payload'] is not None and now-fee_cache['updated']<30:
                return fee_cache['payload']
            relay_floor,pool_floor=core_minimums()
            floor=max(Decimal('1'),fallback_rate,relay_floor,pool_floor)
            floor=ceil_rate(floor)
            mempool_tiers,sample_count=mempool_fee_tiers()
            tiers={}
            for name,target,_ in fee_tiers:
                row={'target_blocks':target,'sat_vb':None,'available':False}
                try:
                    result=rpc.call('estimatesmartfee',target,'CONSERVATIVE')
                    raw=result.get('feerate') if isinstance(result,dict) else None
                    if raw is not None:
                        btc_kvb=Decimal(str(raw))
                        if btc_kvb.is_finite() and btc_kvb>0:
                            estimated=ceil_rate(btc_kvb*Decimal('100000'))
                            estimated=max(estimated,floor)
                            if estimated<=Decimal('1000'):
                                row.update(sat_vb=float(estimated),available=True,source='estimatesmartfee')
                    if isinstance(result,dict) and result.get('errors'):
                        row['reason']='; '.join(str(x)[:160] for x in result['errors'][:3])
                except Exception as exc:
                    row['reason']=str(exc)[:200]
                tiers[name]=row

            # If Core history cannot estimate a tier, use the observed live
            # mempool distribution only when it has enough fee-bearing samples.
            if mempool_tiers:
                for name,_,_ in fee_tiers:
                    if not tiers[name]['available']:
                        rate=max(mempool_tiers[name],floor)
                        if rate<=Decimal('1000'):
                            tiers[name].update(sat_vb=float(rate),available=True,source='mempool')
            # Empty/quiet chains must remain usable: all tiers share the same
            # conservative low-fee fallback, never fabricated as a confirmation prediction.
            fallback_used=False
            for name,_,_ in fee_tiers:
                if not tiers[name]['available']:
                    fallback_used=True
                    if floor<=Decimal('1000'):
                        tiers[name].update(sat_vb=float(floor),available=True,source='fallback')
                    else:
                        tiers[name].update(reason='Required relay fee exceeds wallet safety limit')
            sources={tiers[n].get('source') for n,_,_ in fee_tiers if tiers[n]['available']}
            if fallback_used:
                source='fallback' if sources=={'fallback'} else 'mixed'
                message='当前网络交易较少，使用低费率兜底建议。' if source=='fallback' else '部分档位使用兜底费率。'
            elif sources=={'mempool'}:
                source='mempool';message='已根据当前交易池费率分布估算。'
            elif sources=={'estimatesmartfee'}:
                source='estimatesmartfee';message='节点手续费估算已更新。'
            else:
                source='mixed';message='已综合节点估算与交易池数据。'
            payload={'unit':'sat/vB','source':source,'message':message,
                     'cache_seconds':30,'fetched_at':int(now),
                     'fallback_sat_vb':float(floor),'mempool_samples':sample_count,
                     'tiers':tiers}
            fee_cache.update(updated=now,payload=payload)
            return payload
    cors_section='explorer' if service=='explorer' else 'server'
    cors_key='cors_origins'
    default_cors=('null,http://localhost:8778,http://127.0.0.1:8778' if service=='explorer'
                  else 'null,http://localhost:8777,http://127.0.0.1:8777')
    allowed={origin.strip() for origin in config.get(cors_section,cors_key,fallback=default_cors).split(',') if origin.strip()}
    explorer_port=config.getint('explorer','port',fallback=8778)
    broadcast_origins={f'http://{host}:{explorer_port}' for host in ('localhost','127.0.0.1')}
    @app.after_request
    def cors(resp):
        if hasattr(g,'api_started'):
            duration=time.monotonic()-g.api_started
            performance.observe(duration)
            if duration>=1 or resp.status_code in (400,413,414,429):
                LOG.warning('API endpoint=%s status=%d duration_ms=%d',request.endpoint,resp.status_code,duration*1000)
        if resp.status_code==429:resp.headers['Retry-After']='5'
        origin=request.headers.get('Origin')
        if origin in allowed or (service=='wallet' and request.path=='/api/v1/broadcast' and origin in broadcast_origins):
            resp.headers['Access-Control-Allow-Origin']=origin
            resp.headers['Vary']='Origin'
            resp.headers['Access-Control-Allow-Methods']='GET,HEAD,OPTIONS' if service=='explorer' else 'GET,POST,OPTIONS'
            resp.headers['Access-Control-Allow-Headers']='Content-Type'
        resp.headers['X-Content-Type-Options']='nosniff'
        if service=='explorer' and request.path.startswith('/explorer/') and Path(request.path).suffix.lower() in {'.js','.css','.svg','.png','.webmanifest'}:
            resp.headers['Cache-Control']='public, max-age=86400, stale-while-revalidate=3600'
        elif service=='explorer' and request.path in ('/','/explorer'):
            resp.headers['Cache-Control']='no-cache'
        else:
            resp.headers['Cache-Control']='no-store'
        return resp
    @app.before_request
    def preflight():
        # Enforce service boundaries before Flask dispatches a matching route.
        # Keep cross-service paths isolated even for automatic OPTIONS requests.
        if service == 'wallet':
            if (request.path == '/' or request.path == '/explorer'
                    or request.path.startswith('/explorer/')
                    or request.path.startswith('/api/v1/explorer/')):
                return jsonify(error='Not found'), 404
        elif service == 'explorer':
            explorer_path = (request.path == '/' or request.path == '/explorer'
                             or request.path.startswith('/explorer/')
                             or request.path.startswith('/api/v1/explorer/'))
            if not explorer_path:
                return jsonify(error='Not found'), 404
        if request.path.startswith('/api/'):
            g.api_started=time.monotonic()
            if len(request.query_string)>2048 or len(request.path)>512:
                return jsonify(error='Request URI too long'),414
        if request.method=='OPTIONS': return ('',204)
        if status.get('wrong_chain') and request.path.startswith('/api/v1/explorer/') and not request.path.endswith('/capabilities'):
            return jsonify(error='Configured RPC genesis does not match nextBTC'),503
        if request.content_length and request.content_length>250000: return jsonify(error='request too large'),413
        # Apply independent limits to sensitive public endpoints. Do not trust
        # X-Forwarded-For from an unauthenticated public client.
        endpoint=request.path
        if endpoint=='/api/v1/broadcast' or endpoint=='/api/v1/addresses/query' or endpoint.startswith('/api/v1/history/'):
            ceiling=6 if endpoint=='/api/v1/broadcast' else 180
            key=(request.remote_addr,endpoint if endpoint=='/api/v1/broadcast' else 'wallet-read')
        elif endpoint.startswith('/api/v1/explorer/'):
            heavy_prefixes=('/difficulty','/network/hashrate','/block/','/tx/','/address/','/mempool/','/statistics')
            heavy=any(endpoint.startswith('/api/v1/explorer'+prefix) for prefix in heavy_prefixes)
            try:
                ceiling=config.getint('explorer','heavy_limit_per_minute' if heavy else 'read_limit_per_minute',fallback=60 if heavy else 300)
            except Exception: ceiling=60 if heavy else 300
            ceiling=max(1,min(10000,ceiling))
            key=(request.remote_addr,'explorer-heavy' if heavy else 'explorer-read')
        else:
            ceiling=None;key=None
        if ceiling is not None:
            now=time.monotonic()
            with limit_lock:
                if len(limits)>10000:
                    for k,(start,count) in list(limits.items()):
                        if now-start>60: limits.pop(k,None)
                start,count=limits.get(key,(now,0))
                if now-start>=60:start,count=now,0
                if count>=ceiling:return jsonify(error='API rate limit exceeded'),429
                limits[key]=(start,count+1)
        if request.path.startswith('/api/v1/explorer/'):
            if not slots.acquire(timeout=0.25):return jsonify(error='Explorer busy'),429
            g.explorer_slot=True
            request_budget.deadline=time.monotonic()+15
            indexer.deadline.until=time.monotonic()+5

    @app.teardown_request
    def release_request(error):
        if g.pop('explorer_slot',False):
            request_budget.deadline=0
            indexer.deadline.until=0
            slots.release()

    import sqlite3
    @app.errorhandler(sqlite3.OperationalError)
    def database_error(exc):
        LOG.warning('SQLite request failed at %s: %s',request.endpoint,exc)
        return jsonify(error='Database temporarily unavailable; retry shortly'),503

    def readiness():
        if status.get('error'): return {'error':'Indexer unavailable: '+status['error']},503
        tip=indexer.tip()
        if not tip: return {'error':'Index has not started'},503
        # Prevent treating stale indexes as live for spending; conservative lag.
        remote=status.get('remote_height',-1)
        if remote<0 or tip['height']<remote-1: return {'error':'Index lagging; balance may be stale'},503
        if mempool is not None:
            snapshot=mempool.get()
            if snapshot['error'] or time.time()-snapshot['updated']>60:
                return {'error':'Mempool snapshot unavailable or stale; spending disabled'},503
        return None
    # Explorer endpoints are read-only and isolated from wallet spending paths.
    explorer_cache={'difficulty_at':0.0,'difficulty':None}
    explorer_lock=threading.Lock()

    @explorer_routes.get('/')
    @explorer_routes.get('/explorer', strict_slashes=False)
    def explorer_home():
        return send_from_directory(EXPLORER_ASSETS, 'index.html')

    @explorer_routes.get('/explorer/<path:asset>')
    def explorer_assets(asset):
        mime = {'.js': 'text/javascript', '.css': 'text/css'}.get(Path(asset).suffix)
        if asset=='monitor.html':return admin_metrics()
        return send_from_directory(EXPLORER_ASSETS, asset, mimetype=mime)

    @explorer_routes.get('/api/v1/explorer/statistics')
    def explorer_advanced_statistics():
        snapshot=statistics.latest()
        if snapshot is None:
            return jsonify(error='Statistics snapshot pending'),503
        return jsonify(snapshot)

    @explorer_routes.get('/api/v1/explorer/summary')
    def explorer_summary():
        tip=indexer.tip()
        if not tip: return jsonify(error='Index not initialized'),503
        result={'chain':'nextBTC','indexed_height':tip['height'],'indexed_hash':tip['hash'],
                'indexed_time':tip['timestamp'],'core_height':status.get('remote_height',-1),
                'synced':bool(not status.get('error') and status.get('remote_height',-1)>=0 and tip['height']==status.get('remote_height')),
                'index_error':status.get('error'),
                'mempool':{'available':False}}
        try:
            result['difficulty']=rpc.call('getdifficulty')
        except Exception as exc: result['difficulty_error']=str(exc)[:160]
        try:
            result['network_hashrate']=rpc.call('getnetworkhashps')
        except Exception as exc: result['hashrate_error']=str(exc)[:160]
        try:
            info=rpc.call('getblockchaininfo')
            result['verification_progress']=info.get('verificationprogress')
            result['chain_state']=info.get('chain')
        except Exception: pass
        snap=mempool.get() if mempool else {}
        if snap and not snap.get('error'):
            result['mempool']={'available':True,'count':len(snap.get('txs',{})),
                               'updated':int(snap.get('updated',0)),
                               'stale':time.time()-snap.get('updated',0)>60}
            try:
                mi=rpc.call('getmempoolinfo')
                result['mempool'].update(size_bytes=int(mi.get('bytes',0)),
                    usage_bytes=int(mi.get('usage',0)),total_fee_btc=mi.get('total_fee'),
                    maxmempool_bytes=int(mi.get('maxmempool',0)))
            except Exception: pass
        else:
            result['mempool']['error']=(snap or {}).get('error','Not configured')
        return jsonify(result)

    @explorer_routes.get('/api/v1/explorer/difficulty')
    def explorer_difficulty():
        # Core's canonical GetNextWorkRequired/DarkGravityWave logic is mirrored
        # in explorer.py; historical headers are fetched from Core, not inferred
        # from the wallet index (which intentionally does not persist nBits).
        now=time.time()
        try:
            # Always check the current tip before serving a cached prediction;
            # a newly mined block changes the candidate height immediately.
            height=int(rpc.call('getblockcount'))
            tip_hash_before=rpc.call('getblockhash',height)
        except Exception as exc:
            return jsonify(error='Unable to read current chain height',detail=str(exc)[:160]),503
        with explorer_lock:
            cached=explorer_cache.get('difficulty')
            if cached is not None and cached['tip_hash']==tip_hash_before and now-explorer_cache['difficulty_at']<30:
                return jsonify(cached)
            try:
                chain_info=rpc.call('getblockchaininfo')
                chain_name=str(chain_info.get('chain','')).lower() if isinstance(chain_info,dict) else ''
                if chain_name not in ('main','test','signet') or rpc.call('getblockhash',0)!=GENESIS:
                    raise RuntimeError('Unsupported or unknown Core chain for DWG parameters: '+chain_name)
                headers=read_header_range(rpc,max(0,height-PAST_BLOCKS*2+1),height)
                if headers[0]['hash']!=tip_hash_before:
                    raise RuntimeError('Active tip changed during DWG header read')
                prediction=predict_dgw(headers,height+1,pow_limit_hex=POW_LIMIT_HEX)
                template=None
                template_error=None
                try:
                    template=rpc.call('getblocktemplate',{'rules':['segwit']})
                except Exception as template_exc:
                    template_error=str(template_exc)[:180]
                try:
                    tip_hash_after=rpc.call('getblockhash',int(rpc.call('getblockcount')))
                except Exception as tip_exc:
                    tip_hash_after=None
                    template_error=template_error or str(tip_exc)[:180]
                if tip_hash_after!=tip_hash_before:
                    prediction['available']=False
                    prediction['reason']='Active chain changed or could not be revalidated during DWG calculation; retry after the next poll'
                    template_check={'available':False,'matched':None,'reason':'Active chain tip changed or could not be revalidated'}
                elif template is not None:
                    template_check=verify_template_bits(prediction,template,height+1,tip_hash_before)
                    if template_check['matched'] is False:
                        prediction['available']=False
                        prediction['reason']='Predicted nBits disagree with the Core template for this tip'
                else:
                    template_check={'available':False,'matched':None,'reason':template_error or 'Core template unavailable'}
                prediction['core_template_verification']=template_check
                reference_target=compact_to_target('1d00ffff')
                current=reference_target/compact_to_target(headers[0]['bits'])
                if prediction.get('available') and prediction.get('predicted_target'):
                    prediction['predicted_difficulty']=float(Decimal(reference_target)/Decimal(int(prediction['predicted_target'],16)))
                payload={'height':height,'tip_hash':tip_hash_before,'current_difficulty':current,
                         'next_block':prediction,'algorithm':'Dark Gravity Wave v3',
                         'target_spacing_seconds':150,'window_blocks':24,'core_chain':chain_name,
                         'instant_mine_end_height':55555,'fetched_at':int(now),
                         'history':network_series(headers,PAST_BLOCKS)}
                for row in payload['history']:
                    row['hashrate_estimate']=row['hashrate_hps']
                if prediction.get('available'):
                    explorer_cache.update(difficulty_at=now,difficulty=payload)
                return jsonify(payload)
            except Exception as exc:
                LOG.exception('Explorer DWG calculation failed')
                return jsonify(error='Unable to calculate DWG prediction from canonical Core headers',
                               detail=str(exc)[:200]),503

    @explorer_routes.get('/api/v1/explorer/mempool')
    def explorer_mempool():
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error'):
            return jsonify(available=False,error=(snap or {}).get('error','Not configured')),503
        txs=list(snap.get('txs',{}).values())
        # Bounded detail response; keep aggregate histogram over the full snapshot.
        bins=snap.get('fee_histogram') or fee_histogram(txs)
        details=sorted(txs,key=lambda x:(x.get('fee_sats',0)/max(1,x.get('vsize',1))),reverse=True)[:500]
        return jsonify(available=True,updated=int(snap.get('updated',0)),stale=time.time()-snap.get('updated',0)>60,count=len(txs),
                       displayed_count=len(details),truncated=len(txs)>len(details),coverage_complete=bool(snap.get('coverage_complete',False)),
                       fee_histogram=bins,transactions=details,
                       total_vsize=sum(x.get('vsize',0) for x in txs),
                       total_fee_sats=sum(x.get('fee_sats',0) for x in txs))

    @explorer_routes.get('/api/v1/explorer/transactions')
    def explorer_transactions():
        # Server-side pagination. Empty blocks naturally produce no rows; Coinbase
        # transactions are excluded from the default ordinary-transfer feed.
        limit=query_int('limit',25)
        offset=query_int('offset',0)
        block_height=query_int('block',None)
        if limit is None or not 1<=limit<=100:return jsonify(error='limit must be 1..100'),400
        if offset is None or not 0<=offset<=10_000_000:return jsonify(error='offset out of range'),400
        if request.args.get('block') is not None and (block_height is None or block_height<0):
            return jsonify(error='block must be a non-negative integer'),400
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            order=request.args.get('order','desc')
            if order not in ('desc','asc'):return jsonify(error='Invalid order'),400
            tx_cache_key=('transactions',tip['hash'],limit,offset,block_height,order)
            cached_tx=cache_get(tx_cache_key)
            if cached_tx is not None:
                response=jsonify(cached_tx);response.headers['X-Explorer-Cache']='HIT';return response
            where=['f.height<=?', 'f.vout=0 AND f.coinbase=0']
            params=[int(tip['height'])]
            if block_height is not None:
                where.append('f.height=?');params.append(block_height)
            clause=' AND '.join(where)
            count_key=('transactions-total',tip['hash'],block_height)
            total=cache_get(count_key)
            if total is None:
                total=int(indexer.db.execute('SELECT COUNT(*) FROM outputs f WHERE '+clause,params).fetchone()[0])
                cache_put(count_key,total,300)
            # Page first, then aggregate only outputs related to those page txids.
            # This avoids executing five correlated subqueries for every row and
            # prevents aggregation across the full outputs table.
            rows=[dict(r) for r in indexer.db.execute(
                'WITH page AS MATERIALIZED ('
                ' SELECT t.txid,t.height,t.block_hash,t.timestamp FROM outputs f CROSS JOIN txs t ON t.txid=f.txid WHERE '+clause+
                f" ORDER BY f.height {order}, f.txid {order} LIMIT ? OFFSET ?"
                '), out_stats AS ('
                ' SELECT o.txid,COUNT(*) output_count,COALESCE(SUM(o.value),0) total_output_sats'
                ' FROM page p CROSS JOIN outputs o ON p.txid=o.txid GROUP BY o.txid'
                '), in_stats AS ('
                ' SELECT i.spent_by txid,COUNT(*) input_count,COALESCE(SUM(i.value),0) total_input_sats'
                ' FROM page p CROSS JOIN outputs i ON p.txid=i.spent_by GROUP BY i.spent_by'
                ') SELECT p.txid,p.height,p.block_hash,p.timestamp,'
                'COALESCE(o.output_count,0) output_count,COALESCE(i.input_count,0) input_count,'
                'COALESCE(o.total_output_sats,0) total_output_sats,COALESCE(i.total_input_sats,0) total_input_sats,'
                'CASE WHEN i.txid IS NULL THEN NULL ELSE i.total_input_sats-COALESCE(o.total_output_sats,0) END fee_sats '
                'FROM page p LEFT JOIN out_stats o ON o.txid=p.txid LEFT JOIN in_stats i ON i.txid=p.txid '
                f"ORDER BY p.height {order},p.txid {order}",
                [*params,limit,offset])]
        payload=dict(transactions=rows,total=total,offset=offset,limit=limit,
                       has_more=offset+len(rows)<total,tip_height=int(tip['height']),tip_hash=tip['hash'],
                       definition='Confirmed non-Coinbase transactions only; empty blocks have no transaction rows.')
        cache_put(tx_cache_key,payload,300)
        response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS'
        return response

    @explorer_routes.get('/api/v1/explorer/blocks')
    def explorer_blocks():
        limit=query_int('limit',20)
        if limit is None:return jsonify(error='limit must be an integer'),400
        limit=min(max(limit,1),100)
        offset=query_int('offset',0)
        if offset is None or not 0<=offset<=10000000:return jsonify(error='offset out of range'),400
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            block_cache_key=('blocks',tip['hash'],limit,offset)
            cached_blocks=cache_get(block_cache_key)
            if cached_blocks is not None:return jsonify(cached_blocks)
            rows=[dict(r) for r in indexer.db.execute(
                'SELECT b.height,b.hash,b.prev_hash,b.timestamp,'
                '(SELECT COUNT(*) FROM txs t WHERE t.height=b.height) tx_count FROM blocks b '
                'WHERE b.height<=? ORDER BY b.height DESC LIMIT ?', (tip['height']-offset,limit))]
        total=tip['height']+1
        payload=dict(blocks=rows,total=total,offset=offset,limit=limit,has_more=offset+len(rows)<total)
        cache_put(block_cache_key,payload,3)
        return jsonify(payload)

    def lookup_error(label, exc):
        missing=isinstance(exc,CoreRPCError) and exc.code in (-5,-8)
        return jsonify(error=label,detail=str(exc)[:160]),404 if missing else 503

    def canonical_address(value):
        if not explorer_address_format(value):
            return None, (jsonify(error='Invalid address'),400)
        if value.lower().startswith(('bc1','tb1','bcrt1')):
            value=value.lower()
        with indexer.lock:
            known=indexer.db.execute('SELECT 1 FROM activity WHERE address=? LIMIT 1',(value,)).fetchone()
        if known:return value,None
        try:
            info=rpc.call('validateaddress',value)
            if info.get('isvalid'):return info['address'],None
            return None,(jsonify(error='Invalid address for the connected network'),400)
        except Exception as exc:return None,lookup_error('Address validation unavailable',exc)

    @explorer_routes.before_request
    def validate_explorer_address():
        if request.view_args and 'address' in request.view_args:
            value,error=canonical_address(request.view_args['address'])
            if error:return error
            request.view_args['address']=value

    @explorer_routes.get('/api/v1/explorer/block/<int:height>')
    def explorer_block(height):
        if height<0:return jsonify(error='Invalid block height'),400
        # Resolve the indexed canonical hash first. Confirmed block payloads are
        # immutable for a given hash, so they can be cached independently of tip.
        with indexer.lock:
            indexed=indexer.db.execute('SELECT hash FROM blocks WHERE height=?',(height,)).fetchone()
            tip=indexer.tip()
        if not indexed:return jsonify(error='Block not indexed'),404
        block_hash=str(indexed['hash'])
        block_key=('block-detail',block_hash)
        cached=cache_get(block_key)
        if cached is not None:
            response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
        try:
            if rpc.call('getblockhash',height)!=block_hash:
                return jsonify(error='Indexed block is no longer canonical'),404
            block=rpc.call('getblock',block_hash,1)
            if block.get('hash')!=block_hash or rpc.call('getblockhash',height)!=block_hash:
                return jsonify(error='Active chain changed during block lookup; retry'),503
            txids=block['tx']
            payload=dict(height=height,hash=block_hash,previousblockhash=block.get('previousblockhash'),
                time=block.get('time'),bits=block.get('bits'),difficulty=block.get('difficulty'),
                size=block.get('size'),weight=block.get('weight'),nonce=block.get('nonce'),
                version=block.get('version'),merkleroot=block.get('merkleroot'),
                tx_count=len(txids),txids=txids[:1000],txids_truncated=len(txids)>1000)
            cache_put(block_key,payload,3600)
            response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response
        except Exception as exc:return lookup_error('Block unavailable',exc)

    @explorer_routes.get('/api/v1/explorer/block/hash/<block_hash>')
    def explorer_block_by_hash(block_hash):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', block_hash):
            return jsonify(error='Invalid block hash'), 400
        try:
            header = rpc.call('getblockheader', block_hash.lower(), True)
            height = int(header.get('height', -1))
            canonical_hash = rpc.call('getblockhash', height)
            if canonical_hash.lower() != block_hash.lower():
                return jsonify(error='Block is not in the active chain', height=height, hash=block_hash.lower()), 404
            return jsonify(type='block', height=height, hash=canonical_hash)
        except Exception as exc:
            return lookup_error('Block unavailable',exc)

    @explorer_routes.get('/api/v1/explorer/block/<int:height>/neighbors')
    def explorer_block_neighbors(height):
        if height < 0:
            return jsonify(error='Invalid block height'), 400
        try:
            tip = int(rpc.call('getblockcount'))
            if height > tip:
                return jsonify(error='Block height above chain tip', tip_height=tip), 404
            result = {'height': height, 'tip_height': tip, 'previous': None, 'next': None}
            if height > 0:
                h = height - 1
                result['previous'] = {'height': h, 'hash': rpc.call('getblockhash', h)}
            if height < tip:
                h = height + 1
                result['next'] = {'height': h, 'hash': rpc.call('getblockhash', h)}
            return jsonify(result)
        except Exception as exc:
            return jsonify(error='Block neighbors unavailable', detail=str(exc)[:160]), 503

    @explorer_routes.get('/api/v1/explorer/tx/<txid>')
    def explorer_tx(txid):
        if not re.fullmatch(r'[0-9a-fA-F]{64}',txid):return jsonify(error='Invalid transaction id'),400
        txid=txid.lower()
        try:
            with indexer.lock:
                tip=indexer.tip()
                status_row=indexer.transaction_status(txid,tip['height']) if tip else None
            blockhash=status_row.get('block_hash') if status_row else None
            confirmed_cache_key=('tx-detail',txid,blockhash)+(tip['hash'],) if blockhash else None
            if confirmed_cache_key:
                cached=cache_get(confirmed_cache_key)
                if cached is not None:
                    response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
            if status_row and status_row['height']==0:
                # Core excludes the genesis coinbase from getrawtransaction.
                genesis=rpc.call('getblock',blockhash,2)
                tx=dict(next(t for t in genesis['tx'] if t['txid']==txid))
                tx.update(blockhash=blockhash,blocktime=genesis['time'],confirmations=genesis['confirmations'])
            elif blockhash:
                tx=rpc.call('getrawtransaction',txid,True,blockhash)
            else:
                tx=rpc.call('getrawtransaction',txid,True)
            if tx.get('txid')!=txid or tx.get('in_active_chain') is False or tx.get('confirmations',0)<0:
                return jsonify(error='Transaction changed chain during lookup; retry'),503
            if blockhash and (tx.get('blockhash')!=blockhash or rpc.call('getblockhash',status_row['height'])!=blockhash):
                return jsonify(error='Indexed transaction changed chain during lookup; retry'),503
            confirmations=tx.get('confirmations', status_row['confirmations'] if status_row else 0)
            state='confirmed' if confirmations>0 else 'mempool'
            snapshot=mempool.get() if mempool else {}
            if snapshot.get('error') or time.time()-snapshot.get('updated',0)>60:snapshot={}
            metrics=describe_transaction(indexer,tx,snapshot)
            memos=[]
            for output in tx.get('vout',[]):
                script=(output.get('scriptPubKey') or {}).get('hex')
                memo=decode_op_return_script(script)
                if memo is not None:
                    memos.append({'vout':int(output.get('n',0)),**memo})
            payload=dict(transaction=tx,state=state,confirmations=confirmations,
                           block_height=status_row['height'] if status_row else None,
                           onchain_memos=memos,**metrics)
            if confirmed_cache_key:
                cache_put(confirmed_cache_key,payload,3600)
                response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response
            response=jsonify(payload);response.headers['X-Explorer-Cache']='BYPASS'
            response.headers['Cache-Control']='no-store'
            return response
        except Exception as exc:return lookup_error('Transaction details unavailable',exc)

    @explorer_routes.get('/api/v1/explorer/tx/<txid>/flow')
    def explorer_tx_flow(txid):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', txid):
            return jsonify(error='Invalid transaction id'), 400
        txid = txid.lower()
        snapshot = mempool.get() if mempool else None
        try:
            flow = indexer.transaction_flows([txid], snapshot).get(txid)
            if not flow or (not flow.get('inputs') and not flow.get('outputs')):
                return jsonify(error='Transaction flow unavailable; transaction may be unindexed or prevouts unavailable'), 404
            # Resolve the canonical/mempool status separately; flow data may be partial
            # for nonstandard scripts or pruned historical prevouts.
            tip = indexer.tip()
            status_row = indexer.transaction_status(txid, tip['height']) if tip else None
            state = 'confirmed' if status_row else ('mempool' if snapshot and txid in (snapshot.get('txs') or {}) else 'unknown')
            return jsonify(txid=txid, state=state, flow=flow,
                           completeness={'inputs_unresolved': int(flow.get('inputs_unresolved', 0)),
                                          'inputs_truncated': bool(flow.get('inputs_truncated')),
                                          'outputs_truncated': bool(flow.get('outputs_truncated'))},
                           source='canonical_index_and_current_mempool_snapshot')
        except Exception as exc:
            LOG.exception('Explorer transaction flow failed')
            return jsonify(error='Transaction flow unavailable', detail=str(exc)[:160]), 503

    @explorer_routes.get('/api/v1/explorer/address/<address>')
    def explorer_address(address):
        # Keep tip, UTXO and history on one SQLite read snapshot so a block
        # commit cannot split a single address response across two chain states.
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            totals=indexer.db.execute(
                'SELECT COUNT(*) AS n,COALESCE(SUM(value),0) AS total FROM outputs WHERE address=? AND spent_by IS NULL',
                (address,)).fetchone()
            rows=indexer.db.execute(
                'SELECT txid,vout,value,height,script,coinbase FROM outputs WHERE address=? AND spent_by IS NULL ORDER BY height,txid,vout LIMIT 500',
                (address,)).fetchall()
            history=indexer.history(address,50,0,with_balances=True)
            history_total=int(indexer.db.execute('SELECT COUNT(*) FROM activity WHERE address=?',(address,)).fetchone()[0])
        utxos=[]
        for row in rows:
            item=dict(row);item['confirmations']=max(0,tip['height']-item['height']+1)
            item['mature']=(item['height']!=0) and (not item['coinbase'] or item['confirmations']>=100)
            utxos.append(item)
        return jsonify(address=address,confirmed_sats=int(totals['total']),utxo_count=int(totals['n']),
            utxos=utxos,utxos_truncated=int(totals['n'])>len(utxos),transactions=history,
            transaction_count=history_total,transactions_truncated=history_total>len(history),height=tip['height'])

    @explorer_routes.get('/api/v1/explorer/search')
    def explorer_search():
        q=(request.args.get('q') or '').strip()
        if not q or len(q)>128:return jsonify(error='Invalid search query'),400
        if re.fullmatch(r'[0-9]{1,10}',q):
            h=int(q)
            try:return jsonify(type='block',height=h,hash=rpc.call('getblockhash',h))
            except Exception as exc:return lookup_error('Block height unavailable',exc)
        if re.fullmatch(r'[0-9a-fA-F]{64}',q):
            q=q.lower()
            with indexer.lock:
                if indexer.db.execute('SELECT 1 FROM txs WHERE txid=?',(q,)).fetchone():
                    return jsonify(type='tx',txid=q)
            snap=mempool.get() if mempool else {}
            if not snap.get('error') and time.time()-snap.get('updated',0)<=60 and q in (snap.get('txs') or {}):
                return jsonify(type='tx',txid=q)
            try:
                header=rpc.call('getblockheader',q,True)
                height=int(header['height'])
                if rpc.call('getblockhash',height)!=q:
                    return jsonify(error='Block is not in the active chain'),404
                return jsonify(type='block',height=height,hash=q)
            except CoreRPCError as exc:
                if exc.code!=-5:return lookup_error('Block query unavailable',exc)
            except Exception as exc:return lookup_error('Block query unavailable',exc)
            try:
                tx=rpc.call('getrawtransaction',q,True)
                if tx['txid']==q and tx.get('confirmations',0)>=0:return jsonify(type='tx',txid=q)
                return jsonify(error='Hash not found'),404
            except Exception as exc:return lookup_error('Hash unavailable',exc)
        if explorer_address_format(q):
            address,error=canonical_address(q)
            return error if error else jsonify(type='address',address=address)
        return jsonify(error='Unsupported search value'),400

    @wallet_routes.get('/api/v1/status')
    def state():
        tip=indexer.tip()
        wallet_service=service!='explorer'
        return jsonify(api_version='0.4.0',capabilities={'address_index':True,'mempool_spend_guard':mempool is not None,'broadcast':wallet_service,'fee_estimates':True,'transaction_flow':True,'transaction_details':True,'explorer':service!='wallet','dwg_prediction':service!='wallet','mempool_visualization':service!='wallet','explorer_api_v1_0_20':service!='wallet','explorer_api_v1_0_21':service!='wallet','explorer_api_v1_0_23':service!='wallet','explorer_api_v1_0_25':service!='wallet','explorer_api_v1_0_28':service!='wallet','explorer_api_v1_0_29':service!='wallet','explorer_api_v1_0_31':service!='wallet','explorer_api_v1_0_33':service!='wallet','explorer_api_v1_0_32':service!='wallet','explorer_transaction_feed_cache':service!='wallet','explorer_transactions_list':service!='wallet','explorer_persisted_statistics_cache':service!='wallet'},
                       chain='nextBTC',genesis=GENESIS,indexed_height=tip['height'] if tip else -1,
                       indexed_hash=tip['hash'] if tip else None,core_height=status.get('remote_height',-1),
                       synced=bool(tip and status.get('remote_height',-1)>=0 and tip['height']>=status['remote_height']-1 and not status.get('error')),
                       last_error=status.get('error'),
                       mempool_error=mempool.get()['error'] if mempool else 'Not configured',
                       mempool_updated=int(mempool.get()['updated']) if mempool else 0,
                       mempool_count=len(mempool.get()['txs']) if mempool else 0)
    @wallet_routes.get('/api/v1/fees')
    def fee_suggestions():
        # Fee suggestions remain available even if the address index is catching up;
        # they are advisory only and never authorize spending or broadcasting.
        payload=fee_estimates()
        return jsonify(payload)

    @wallet_routes.post('/api/v1/addresses/query')
    def query():
        invalid=readiness()
        if invalid: return jsonify(invalid[0]),invalid[1]
        body=request.get_json(silent=True)
        addresses=body.get('addresses',[]) if isinstance(body,dict) else []
        if not isinstance(addresses,list) or not 1<=len(addresses)<=10 or any(not isinstance(a,str) or not ADDRESS.fullmatch(a) for a in addresses):
            return jsonify(error='Invalid address list'),400
        tip=indexer.tip()['height']
        snapshot=mempool.get() if mempool else None
        results=[]
        for a in addresses:
            info=indexer.address_info(a,tip)
            if snapshot:
                for u in info['utxos']:
                    if (u['txid'],u['vout']) in snapshot['spends']:
                        u['mature']=False
                        u['mempool_spent']=True
                        u['spent_by_mempool']=snapshot['spends'][(u['txid'],u['vout'])]
                info['spendable_sats']=sum(u['value'] for u in info['utxos'] if u['mature'])
                incoming=snapshot['received'].get(a,[])
                info['unconfirmed_received_sats']=sum(u['value'] for u in incoming)
                info['unconfirmed_outputs']=incoming
                info['mempool_spent_sats']=sum(u['value'] for u in info['utxos'] if u.get('mempool_spent'))
            results.append(info)
        return jsonify(height=tip, results=results, mempool_updated=int(snapshot['updated']) if snapshot else None,
                       note='Confirmed UTXOs, excluding any spends observed in current mempool')
    @wallet_routes.get('/api/v1/history/<address>')
    def history(address):
        invalid=readiness()
        if invalid: return jsonify(invalid[0]),invalid[1]
        if not ADDRESS.fullmatch(address): return jsonify(error='Invalid address'),400
        limit=min(max(request.args.get('limit',50,type=int),1),100)
        offset=min(max(request.args.get('offset',0,type=int),0),100000)
        confirmed=indexer.history(address,limit,offset)
        snapshot=mempool.get() if mempool else None
        pending=[]
        if snapshot:
            ids=set(snapshot['activity'].get(address,[]))
            for u in indexer.address_info(address,indexer.tip()['height'])['utxos']:
                spending=snapshot['spends'].get((u['txid'],u['vout']))
                if spending: ids.add(spending)
            confirmed_utxos=indexer.address_info(address,indexer.tip()['height'])['utxos']
            pending=[]
            for txid in ids:
                if txid not in snapshot['txs']: continue
                credit=sum(u['value'] for u in snapshot['received'].get(address,[]) if u['txid']==txid)
                debit=sum(u['value'] for u in confirmed_utxos if snapshot['spends'].get((u['txid'],u['vout']))==txid)
                pending.append(dict(snapshot['txs'][txid],height=-1,unconfirmed=True,
                                    received_sats=credit,sent_sats=debit,net_sats=credit-debit))
            pending.sort(key=lambda x:x['time'],reverse=True)
        transactions=pending+confirmed
        if request.args.get('include_flow')=='1':
            # DGChat opts in when it needs contact/address association. Other
            # clients retain the compact legacy response by default.
            transactions.sort(key=lambda row:int(row.get('timestamp') or row.get('time') or 0),reverse=True)
            transactions=transactions[:120]
            flows=indexer.transaction_flows([row['txid'] for row in transactions],snapshot)
            for row in transactions:
                flow=flows.get(row['txid'],{})
                row['input_addresses']=flow.get('input_addresses',[])
                row['output_addresses']=flow.get('output_addresses',[])
                row['inputs']=flow.get('inputs',[])
                row['outputs']=flow.get('outputs',[])
        return jsonify(address=address,transactions=transactions,mempool_updated=int(snapshot['updated']) if snapshot else None)
    @wallet_routes.get('/api/v1/tx/<txid>')
    def transaction_status(txid):
        if not re.fullmatch(r'[0-9a-fA-F]{64}',txid):return jsonify(error='Invalid transaction id'),400
        tip=indexer.tip()
        if not tip:return jsonify(error='Indexer not initialized'),503
        confirmed=indexer.transaction_status(txid.lower(),tip['height'])
        if confirmed:return jsonify(**confirmed)
        snapshot=mempool.get() if mempool else None
        if snapshot and txid.lower() in snapshot['txs']:
            return jsonify(txid=txid.lower(),state='mempool',confirmations=0,
                           timestamp=snapshot['txs'][txid.lower()]['time'])
        if snapshot and (snapshot['error'] or time.time()-snapshot['updated']>60):
            return jsonify(txid=txid.lower(),state='unknown',reason='mempool unavailable'),503
        return jsonify(txid=txid.lower(),state='not_found',confirmations=0)

    @wallet_routes.post('/api/v1/broadcast')
    def broadcast():
        invalid=readiness()
        if invalid: return jsonify(invalid[0]),invalid[1]
        body=request.get_json(silent=True)
        tx=body.get('hex','') if isinstance(body,dict) else ''
        if not isinstance(tx,str) or len(tx)<20 or len(tx)>200000 or len(tx)%2 or not HEXTX.fullmatch(tx):
            return jsonify(error='Invalid raw transaction'),400
        try: return jsonify(txid=rpc.call('sendrawtransaction',tx))
        except Exception as e: return jsonify(error='Node rejected transaction'),502

    # ---- Explorer API expansion (v1.0.13): bounded, read-only endpoints ----
    def page_args(default=50, maximum=200):
        limit=query_int('limit',default)
        offset=query_int('offset',0)
        if limit is None or offset is None or limit<1 or limit>maximum or offset<0 or offset>10_000_000:
            return None,None
        return limit,offset

    @explorer_routes.get('/api/v1/explorer/network')
    def explorer_network():
        tip=indexer.tip()
        try:
            bc=rpc.call('getblockchaininfo')
            ni=rpc.call('getnetworkinfo')
            result={'chain':bc.get('chain'),'blocks':bc.get('blocks'),'headers':bc.get('headers'),
                    'verification_progress':bc.get('verificationprogress'),'initial_block_download':bc.get('initialblockdownload'),
                    'connections':ni.get('connections'),'protocol_version':ni.get('protocolversion'),
                    'subversion':ni.get('subversion'),'relay_fee':ni.get('relayfee'),
                    'indexed_height':tip['height'] if tip else -1,
                    'indexed_hash':tip['hash'] if tip else None,
                    'index_lag':max(0,int(bc.get('blocks',0))-(tip['height'] if tip else -1)),
                    'fetched_at':int(time.time())}
            return jsonify(result)
        except Exception as exc:
            return jsonify(error='Network information unavailable',detail=str(exc)[:160]),503

    @explorer_routes.get('/api/v1/explorer/network/hashrate')
    def explorer_hashrate():
        height=query_int('height',None)
        if request.args.get('height') is not None and height is None:return jsonify(error='height must be an integer'),400
        blocks=query_int('blocks',120)
        if blocks is None or not 1<=blocks<=10000:return jsonify(error='blocks must be 1..10000'),400
        if height is not None and height < -1:return jsonify(error='height must be -1 or a non-negative block height'),400
        try:
            value=rpc.call('getnetworkhashps',blocks,height if height is not None else -1)
            return jsonify(hashrate=value,unit='H/s',blocks=blocks,at_height=height,
                           source='getnetworkhashps',fetched_at=int(time.time()))
        except Exception as exc:return jsonify(error='Hashrate unavailable',detail=str(exc)[:160]),503

    @explorer_routes.get('/api/v1/explorer/network/blocks')
    def explorer_block_stats():
        hours=query_int('hours',24)
        if hours is None or not 1<=hours<=8760:return jsonify(error='hours must be 1..8760'),400
        cutoff=int(time.time())-hours*3600
        with indexer.lock:
            rows=[dict(r) for r in indexer.db.execute(
                'SELECT (timestamp / 3600) * 3600 AS bucket,COUNT(*) AS blocks,AVG(timestamp) AS avg_timestamp '
                'FROM blocks WHERE timestamp>=? GROUP BY bucket ORDER BY bucket',(cutoff,))]
        return jsonify(hours=hours,series=rows,source='indexed_blocks',fetched_at=int(time.time()))

    @explorer_routes.get('/api/v1/explorer/network/transactions')
    def explorer_tx_stats():
        days=query_int('days',30)
        if days is None or not 1<=days<=3650:return jsonify(error='days must be 1..3650'),400
        cutoff=int(time.time())-days*86400
        with indexer.lock:
            rows=[dict(r) for r in indexer.db.execute(
                'SELECT (timestamp / 86400) * 86400 AS bucket,COUNT(*) AS transactions '
                'FROM txs WHERE timestamp>=? GROUP BY bucket ORDER BY bucket',(cutoff,))]
        return jsonify(days=days,series=rows,source='indexed_transactions',fetched_at=int(time.time()))

    @explorer_routes.get('/api/v1/explorer/difficulty/history')
    def explorer_difficulty_history():
        limit=query_int('limit',100); before=query_int('before',None)
        if request.args.get('before') is not None and before is None:return jsonify(error='before must be an integer'),400
        if limit is None or not 1<=limit<=200:return jsonify(error='limit must be 1..200'),400
        if before is not None and before < 0:return jsonify(error='before must be >= 0'),400
        try:
            tip_height=int(rpc.call('getblockcount'))
            end=tip_height if before is None else min(before,tip_height)
            start=max(0,end-limit+1)
            headers=read_header_range(rpc,max(0,start-PAST_BLOCKS),end)
            rows=network_series(headers,limit)
            return jsonify(tip_height=tip_height,items=rows,limit=limit,before=before,
                           has_more=start>0,source='canonical_core_headers',fetched_at=int(time.time()))
        except Exception as exc:return jsonify(error='Difficulty history unavailable',detail=str(exc)[:160]),503

    @explorer_routes.get('/api/v1/explorer/difficulty/window')
    def explorer_difficulty_window():
        try:
            height=int(rpc.call('getblockcount'))
            headers=read_header_range(rpc,max(0,height-PAST_BLOCKS+1),height)
            tip_hash_before=headers[0]['hash']
            if rpc.call('getblockhash',int(rpc.call('getblockcount')))!=tip_hash_before:
                return jsonify(error='Active chain changed during DWG window query; retry'),503
            return jsonify(tip_height=height,tip_hash=tip_hash_before,window=headers,window_blocks=len(headers),
                           required_window_blocks=24,source='canonical_core_headers')
        except Exception as exc:return jsonify(error='DWG window unavailable',detail=str(exc)[:160]),503

    @explorer_routes.get('/api/v1/explorer/block/<int:height>/transactions')
    def explorer_block_transactions(height):
        limit,offset=page_args(50,200)
        if limit is None:return jsonify(error='limit/offset out of range'),400
        try:
            bh=rpc.call('getblockhash',height); block=rpc.call('getblock',bh,1)
            if block.get('hash')!=bh or rpc.call('getblockhash',height)!=bh:return jsonify(error='Active chain changed during block transaction query; retry'),503
            ids=block['tx']
            return jsonify(height=height,hash=bh,total=len(ids),limit=limit,offset=offset,
                           txids=ids[offset:offset+limit],has_more=offset+limit<len(ids))
        except Exception as exc:return lookup_error('Block transactions unavailable',exc)

    @explorer_routes.get('/api/v1/explorer/block/<int:height>/statistics')
    def explorer_block_statistics(height):
        try:
            bh=rpc.call('getblockhash',height); b=rpc.call('getblock',bh,2)
            if str(b.get('hash','')).lower()!=str(bh).lower():return jsonify(error='Active chain changed during block statistics query; retry'),503
            txs=b.get('tx',[]); fees=[]; total_out=0
            for tx in txs:
                total_out += sum(int(Decimal(str(v['value']))*Decimal(100000000)) for v in tx.get('vout',[]))
                if 'fee' in tx: fees.append(int(Decimal(str(tx['fee']))*Decimal(100000000)))
            return jsonify(height=height,hash=bh,tx_count=len(txs),size=b.get('size'),weight=b.get('weight'),
                           total_output_sats=total_out,known_fees_sats=sum(fees) if len(fees)==max(0,len(txs)-1) else None,
                           fee_data_complete=len(fees)==max(0,len(txs)-1))
        except Exception as exc:return jsonify(error='Block statistics unavailable',detail=str(exc)[:160]),503

    @explorer_routes.get('/api/v1/explorer/address/<address>/history')
    def explorer_address_history(address):
        limit,offset=page_args(50,200)
        if limit is None:return jsonify(error='limit/offset out of range'),400
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            cache_key=('address-history',str(tip['hash']),address,limit,offset)
            cached=cache_get(cache_key)
            if cached is not None:
                response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
            rows=indexer.history(address,limit,offset,with_balances=True)
            total=indexer.db.execute('SELECT COUNT(*) FROM activity WHERE address=?',(address,)).fetchone()[0]
        payload=dict(address=address,total=int(total),limit=limit,offset=offset,transactions=rows,tip_hash=tip['hash'],height=tip['height'],
                     has_more=offset+len(rows)<total,source='canonical_index')
        cache_put(cache_key,payload,10)
        response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response

    @explorer_routes.get('/api/v1/explorer/address/<address>/utxos')
    def explorer_address_utxos(address):
        limit,offset=page_args(100,500)
        if limit is None:return jsonify(error='limit/offset out of range'),400
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            cache_key=('address-utxos',str(tip['hash']),address,limit,offset)
            cached=cache_get(cache_key)
            if cached is not None:
                response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
            total=indexer.db.execute('SELECT COUNT(*) FROM outputs WHERE address=? AND spent_by IS NULL',(address,)).fetchone()[0]
            rows=[dict(r) for r in indexer.db.execute(
                'SELECT txid,vout,value,height,script,coinbase FROM outputs WHERE address=? AND spent_by IS NULL '
                'ORDER BY height,txid,vout LIMIT ? OFFSET ?',(address,limit,offset))]
        for row in rows:
            row['confirmations']=max(0,tip['height']-row['height']+1)
            row['mature']=row['height']!=0 and (not row['coinbase'] or row['confirmations']>=100)
        payload=dict(address=address,total=int(total),limit=limit,offset=offset,utxos=rows,
                     has_more=offset+len(rows)<total,height=tip['height'],tip_hash=tip['hash'])
        cache_put(cache_key,payload,10)
        response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response

    @explorer_routes.get('/api/v1/explorer/address/<address>/statistics')
    def explorer_address_statistics(address):
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            cache_key=('address-statistics',str(tip['hash']),address)
            cached=cache_get(cache_key)
            if cached is not None:
                response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
            received=indexer.db.execute('SELECT COALESCE(SUM(value),0) FROM outputs WHERE address=?',(address,)).fetchone()[0]
            spent=indexer.db.execute('SELECT COALESCE(SUM(o.value),0) FROM outputs o WHERE o.address=? AND o.spent_by IS NOT NULL',(address,)).fetchone()[0]
            utxo=indexer.db.execute('SELECT COUNT(*),COALESCE(SUM(value),0) FROM outputs WHERE address=? AND spent_by IS NULL',(address,)).fetchone()
            txcount=indexer.db.execute('SELECT COUNT(*) FROM activity WHERE address=?',(address,)).fetchone()[0]
        payload=dict(address=address,total_received_sats=int(received),total_spent_sats=int(spent),height=tip['height'],tip_hash=tip['hash'],
                     balance_sats=int(utxo[1]),utxo_count=int(utxo[0]),transaction_count=int(txcount),
                     note='Address totals are derived from indexed outputs; change/self-transfer semantics are not identity attribution.')
        cache_put(cache_key,payload,10)
        response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response

    @explorer_routes.get('/api/v1/explorer/mempool/summary')
    def explorer_mempool_summary():
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error'):return jsonify(available=False,error=(snap or {}).get('error','Not configured')),503
        txs=list(snap.get('txs',{}).values())
        try: info=rpc.call('getmempoolinfo')
        except Exception: info=None
        current_core_count=int(info.get('size')) if isinstance(info,dict) and info.get('size') is not None else None
        snapshot_core_count=int(snap.get('core_count',len(txs)))
        return jsonify(available=True,updated=int(snap.get('updated',0)),stale=time.time()-snap.get('updated',0)>60,
                       indexed_count=len(txs),snapshot_core_count=snapshot_core_count,
                       core_bytes=info.get('bytes') if isinstance(info,dict) else None,
                       core_usage_bytes=info.get('usage') if isinstance(info,dict) else None,
                       core_size=current_core_count,current_core_count_matches_snapshot=(current_core_count==snapshot_core_count if current_core_count is not None else None),
                       total_vsize=sum(int(t.get('vsize',0)) for t in txs),
                       total_fee_sats=sum(int(t.get('fee_sats',0)) for t in txs),
                       coverage_complete=bool(snap.get('coverage_complete',False)),
                       max_txs=mempool.max_txs if mempool else 0)

    @explorer_routes.get('/api/v1/explorer/mempool/transactions')
    def explorer_mempool_transactions():
        limit,offset=page_args(100,500)
        if limit is None:return jsonify(error='limit/offset out of range'),400
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error'):return jsonify(available=False,error=(snap or {}).get('error','Not configured')),503
        sort=request.args.get('sort','feerate')
        txs=list(snap.get('txs',{}).values())
        if sort=='time':txs.sort(key=lambda x:int(x.get('time',0)),reverse=True)
        elif sort=='size':txs.sort(key=lambda x:int(x.get('vsize',0)),reverse=True)
        elif sort=='feerate':txs.sort(key=lambda x:int(x.get('fee_sats',0))/max(1,int(x.get('vsize',0))),reverse=True)
        elif sort=='package_feerate':txs.sort(key=lambda x:float(x.get('ancestor_feerate_sat_vb',0)),reverse=True)
        else:return jsonify(error='sort must be feerate, package_feerate, time or size'),400
        return jsonify(updated=int(snap.get('updated',0)),stale=time.time()-snap.get('updated',0)>60,total=len(txs),limit=limit,offset=offset,sort=sort,
                       transactions=txs[offset:offset+limit],has_more=offset+limit<len(txs),coverage_complete=bool(snap.get('coverage_complete',False)))

    @explorer_routes.get('/api/v1/explorer/mempool/map')
    def explorer_mempool_map():
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error'):return jsonify(available=False,error=(snap or {}).get('error','Not configured')),503
        txs=list(snap.get('txs',{}).values())
        max_items=query_int('limit',2000)
        if max_items is None or not 1<=max_items<=5000:return jsonify(error='limit must be 1..5000'),400
        txs.sort(key=lambda x:float(x.get('ancestor_feerate_sat_vb',x.get('fee_sats',0)/max(1,x.get('vsize',0)))),reverse=True)
        package_complete=all(bool(t.get('ancestor_metrics_available')) for t in txs)
        return jsonify(updated=int(snap.get('updated',0)),stale=time.time()-snap.get('updated',0)>60,total=len(txs),returned=min(len(txs),max_items),
                       truncated=len(txs)>max_items,coverage_complete=bool(snap.get('coverage_complete',False)),
                       snapshot_core_count=int(snap.get('core_count',len(txs))),package_metrics_complete=package_complete,sort='ancestor_package_feerate_with_individual_fallback',
                       items=[{'txid':t['txid'],'vsize':t.get('vsize',0),
                       'fee_sats':t.get('fee_sats',0),'feerate_sat_vb':t.get('fee_sats',0)/max(1,t.get('vsize',0)),
                       'ancestor_fee_sats':t.get('ancestor_fee_sats',t.get('fee_sats',0)),
                       'ancestor_vsize':t.get('ancestor_vsize',t.get('vsize',0)),
                       'ancestor_feerate_sat_vb':t.get('ancestor_feerate_sat_vb',t.get('fee_sats',0)/max(1,t.get('vsize',0))),
                       'ancestor_metrics_available':bool(t.get('ancestor_metrics_available',False)),
                       'ancestorcount':t.get('ancestorcount',1),'descendantcount':t.get('descendantcount',1),
                       'depends':t.get('depends',[]),'replaceable':t.get('replaceable')} for t in txs[:max_items]])

    @explorer_routes.get('/api/v1/explorer/mempool/fees')
    def explorer_mempool_fees():
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error'):return jsonify(available=False,error=(snap or {}).get('error','Not configured')),503
        groups=snap.get('fee_histogram') or fee_histogram(snap.get('txs',{}))
        return jsonify(updated=int(snap.get('updated',0)),stale=time.time()-snap.get('updated',0)>60,
                       coverage_complete=bool(snap.get('coverage_complete',False)),unit='sat/vB',histogram=groups)

    @explorer_routes.get('/api/v1/explorer/mempool/recent')
    def explorer_mempool_recent():
        limit, offset = page_args(50, 200)
        if limit is None:
            return jsonify(error='limit/offset out of range'), 400
        snap = mempool.get() if mempool else {}
        if not snap or snap.get('error'):
            return jsonify(available=False, error=(snap or {}).get('error', 'Not configured')), 503
        txs = list((snap.get('txs') or {}).values())
        txs.sort(key=lambda row: int(row.get('time', 0)), reverse=True)
        return jsonify(updated=int(snap.get('updated', 0)), stale=time.time()-snap.get('updated',0)>60, total=len(txs), limit=limit, offset=offset,
                       transactions=txs[offset:offset+limit], has_more=offset+limit < len(txs),
                       coverage_complete=bool(snap.get('coverage_complete', False)))

    @explorer_routes.get('/api/v1/explorer/mempool/tx/<txid>')
    def explorer_mempool_tx(txid):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', txid):
            return jsonify(error='Invalid transaction id'), 400
        snap = mempool.get() if mempool else {}
        if not snap or snap.get('error') or time.time()-float(snap.get('updated') or 0)>60:
            return jsonify(available=False,error=(snap or {}).get('error') or 'Mempool snapshot unavailable or stale'),503
        txid = txid.lower()
        row = (snap.get('txs') or {}).get(txid)
        if not row:
            return jsonify(error='Transaction not in current mempool snapshot'), 404
        return jsonify(updated=int(snap.get('updated', 0)), transaction=row,
                       coverage_complete=bool(snap.get('coverage_complete', False)))

    @explorer_routes.get('/api/v1/explorer/mempool/tx/<txid>/dependencies')
    def explorer_mempool_dependencies(txid):
        if not re.fullmatch(r'[0-9a-fA-F]{64}',txid):return jsonify(error='Invalid transaction id'),400
        snap=mempool.get() if mempool else {}
        if not snap or snap.get('error') or time.time()-float(snap.get('updated') or 0)>60:
            return jsonify(available=False,error=(snap or {}).get('error') or 'Mempool snapshot unavailable or stale'),503
        txid=txid.lower(); txs=snap.get('txs') or {}
        if txid not in txs:return jsonify(error='Transaction not in current mempool snapshot'),404
        row=txs[txid]; parents=list(row.get('depends') or [])
        # Reverse dependency index is built once during snapshot refresh; avoid
        # scanning the entire mempool for every transaction-detail request.
        children=list((snap.get('children') or {}).get(txid,[]))
        return jsonify(txid=txid,parents=parents,children=children,ancestorcount=row.get('ancestorcount'),
                       descendantcount=row.get('descendantcount'),updated=int(snap.get('updated',0)))

    @explorer_routes.get('/api/v1/explorer/mempool/events')
    def explorer_mempool_events():
        hours=query_int('hours',24)
        limit,offset=page_args(100,500)
        if hours is None or not 1<=hours<=8760:return jsonify(error='hours must be 1..8760'),400
        if limit is None:return jsonify(error='limit/offset out of range'),400
        cutoff=int(time.time())-hours*3600
        with indexer.lock:
            total=indexer.db.execute('SELECT COUNT(*) FROM mempool_events WHERE event_at>=?',(cutoff,)).fetchone()[0]
            rows=[dict(r) for r in indexer.db.execute(
                "SELECT e.event_at,e.txid,CASE WHEN e.event_type='removed_unknown' AND t.txid IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM mempool_events later WHERE later.txid=e.txid AND "
                "(later.event_at,later.id)>(e.event_at,e.id)) THEN 'confirmed' ELSE e.event_type END AS event_type,"
                "t.height AS current_confirmation_height,e.replacement_txid "
                "FROM mempool_events e LEFT JOIN txs t ON t.txid=e.txid "
                'WHERE e.event_at>=? ORDER BY e.event_at DESC,e.id DESC LIMIT ? OFFSET ?',
                (cutoff,limit,offset))]
        return jsonify(hours=hours,total=int(total),limit=limit,offset=offset,events=rows,
                       has_more=offset+len(rows)<total,
                       semantics={'replaced':'A removed transaction shared at least one spent outpoint with a newly observed transaction.',
                                   'removed_unknown':'Transaction left the observed mempool; cause is not inferable unless it is later found confirmed.',
                                   'confirmed':'Transaction was found in the canonical indexed chain.'})

    @explorer_routes.get('/api/v1/explorer/mempool/history')
    def explorer_mempool_history():
        hours=query_int('hours',24)
        limit,offset=page_args(1000,5000)
        if hours is None or not 1<=hours<=8760:return jsonify(error='hours must be 1..8760'),400
        if limit is None:return jsonify(error='limit/offset out of range'),400
        cutoff=int(time.time())-hours*3600
        with indexer.lock:
            total=indexer.db.execute('SELECT COUNT(*) FROM mempool_history WHERE sampled_at>=?',(cutoff,)).fetchone()[0]
            rows=[dict(r) for r in indexer.db.execute(
                'SELECT sampled_at,tx_count,total_vsize,total_fee_sats,fee_bins_json FROM mempool_history '
                'WHERE sampled_at>=? ORDER BY sampled_at LIMIT ? OFFSET ?',(cutoff,limit,offset))]
        for r in rows:
            try:r['fee_histogram']=json.loads(r.pop('fee_bins_json'))
            except Exception:r['fee_histogram']=[]
        return jsonify(hours=hours,total=int(total),limit=limit,offset=offset,series=rows,
                       has_more=offset+len(rows)<int(total),retention_samples=200000,
                       source='persisted_mempool_snapshots',note='History starts from V1.0.7 sampler activation.')

    @explorer_routes.get('/api/v1/explorer/address/<address>/balance-history')
    def explorer_address_balance_history(address):
        days=query_int('days',365)
        if days is None or not 1<=days<=3650:return jsonify(error='days must be 1..3650'),400
        with indexer.lock:
            tip=indexer.tip()
            if not tip:return jsonify(error='Index not initialized'),503
            cache_key=('address-balance-history',str(tip['hash']),address,days)
            cached=cache_get(cache_key)
            if cached is not None:
                response=jsonify(cached);response.headers['X-Explorer-Cache']='HIT';return response
            cutoff=int(time.time())-days*86400
            # Reconstruct daily closing balance from indexed creation/spend timestamps.
            # The index is canonical and rewind-safe; no identity or change attribution is inferred.
            rows=indexer.db.execute("""
              SELECT day, SUM(delta) AS balance_sats FROM (
                SELECT (t.timestamp / 86400)*86400 AS day, o.value AS delta
                FROM outputs o JOIN txs t ON t.txid=o.txid WHERE o.address=? AND t.timestamp>=?
                UNION ALL
                SELECT (t.timestamp / 86400)*86400 AS day, -o.value AS delta
                FROM outputs o JOIN txs t ON t.txid=o.spent_by WHERE o.address=? AND o.spent_by IS NOT NULL AND t.timestamp>=?
              ) GROUP BY day ORDER BY day""",(address,cutoff,address,cutoff)).fetchall()
            # Opening balance immediately before cutoff is computed from current canonical index rows
            # using creation/spend times, then daily deltas are accumulated.
            opening=indexer.db.execute("""
              SELECT COALESCE(SUM(o.value),0) FROM outputs o JOIN txs c ON c.txid=o.txid
              LEFT JOIN txs s ON s.txid=o.spent_by
              WHERE o.address=? AND c.timestamp<? AND (s.timestamp IS NULL OR s.timestamp>=?)""",(address,cutoff,cutoff)).fetchone()[0]
        balance=int(opening); series=[]
        for r in rows:
            balance+=int(r['balance_sats'] or 0)
            series.append({'timestamp':int(r['day']),'balance_sats':balance})
        payload=dict(address=address,days=days,series=series,unit='satoshis',tip_hash=tip['hash'],height=tip['height'],
                     source='reconstructed_from_canonical_outputs_and_spends',
                     note='Daily buckets use indexed block timestamps; same-day activity is aggregated.')
        cache_put(cache_key,payload,60)
        response=jsonify(payload);response.headers['X-Explorer-Cache']='MISS';return response

    @explorer_routes.get('/api/v1/explorer/capabilities')
    def explorer_capabilities():
        return jsonify(api_version='0.4.0',explorer_api_version='1.0.33',
          wallet_port=config.getint('server','port',fallback=8777),
          wallet_broadcast_path=config.get('explorer','wallet_broadcast_path',fallback=''),
          capabilities={'network_overview':True,'hashrate_rpc':True,'indexed_block_series':True,
          'indexed_transaction_series':True,'difficulty_history':True,'dgw_window':True,
          'block_transaction_pagination':True,'block_statistics':True,'address_history_pagination':True,
          'address_utxo_pagination':True,'address_statistics':True,'address_history_running_balance':True,'mempool_summary':True,
          'mempool_map':True,'mempool_fee_histogram':True,'mempool_transaction_pagination':True,
          'mempool_dependencies':True,'mempool_event_history':True,'historical_mempool_series':True,
          'historical_address_balance':True,'advanced_network_statistics':True,'onchain_memo_decoding':True,'difficulty_history_from_core_headers':True,'core_template_difficulty_verification':True,
          'transaction_flow':True,'block_lookup_by_hash':True,'block_neighbors':True,
          'mempool_recent_transactions':True,'mempool_transaction_detail':True,
          'mempool_reverse_dependency_index':True},
          limitations=['Mempool history and events begin only after sampler activation; prior mempool states cannot be reconstructed.',
                       'Ancestor package feerate falls back to individual transaction feerate when Core omits ancestor fee/size metadata; package_metrics_complete identifies this.',
                       'RBF replacement events are inferred from conflicting inputs across consecutive snapshots, not consensus-level proofs.',
                       'Difficulty history is read from canonical Core headers on demand and is not pre-materialized in SQLite.',
                       'Transaction flow can be partial when previous outputs are unavailable or scripts do not decode to addresses.',
                       'No WebSocket/SSE push transport is provided; clients poll bounded read-only endpoints.'])

    @explorer_routes.get('/explorer/admin')
    @explorer_routes.get('/api/v1/explorer/admin/metrics')
    def admin_metrics():
        token=config.get('explorer','admin_token',fallback='').encode()
        auth=request.authorization
        if not token:return jsonify(error='Not found'),404
        if not auth or auth.type!='basic' or auth.username!='admin' or not secrets.compare_digest((auth.password or '').encode(),token):
            return jsonify(error='Authentication required'),401,{'WWW-Authenticate':'Basic realm="nextBTC Admin", charset="UTF-8"'}
        if request.path in ('/explorer/admin','/explorer/monitor.html'):
            return send_from_directory(EXPLORER_ASSETS,'monitor.html')
        return jsonify(**performance.metrics(),uptime=int(time.monotonic()-started),database_bytes=indexer.path.stat().st_size,
                       sql_mean_ms=indexer.db.mean_ms(),worker=statistics.state,worker_seconds=round(statistics.seconds,3))

    if service in ('wallet', 'combined'):
        app.register_blueprint(wallet_routes)
    if service in ('explorer', 'combined'):
        app.register_blueprint(explorer_routes)
        for name in ('difficulty','block','tx','summary','network','hashrate','difficulty_history','difficulty_window','block_stats','tx_stats','blocks',
                     'transactions','address_history','address_utxos','address_statistics','address_balance_history',
                     'mempool_summary','mempool_map','mempool_fees','mempool_transactions','mempool_history','mempool_events'):
            endpoint='explorer.explorer_'+name
            ttl=3 if name.startswith('mempool') or name in ('summary','network','hashrate') else 10
            app.view_functions[endpoint]=performance.wrap(app,app.view_functions[endpoint],indexer,mempool,ttl)
    if service != 'combined':
        # Record the selected public surface. The pre-dispatch guard above is
        # authoritative; do not mutate Werkzeug's private URL-map internals.
        app.config['NEXTBTC_SERVICE_ROUTES'] = service
    return app

def main():
    try:
        from waitress import create_server
    except ImportError as exc:
        raise RuntimeError('Waitress is required to run the packaged HTTP services; install requirements.txt') from exc
    cfg=load_config()
    logging.basicConfig(level=getattr(logging,cfg.get('logging','level',fallback='INFO').upper(),logging.INFO),format='%(asctime)s %(levelname)s %(message)s')
    rpc=RPC(cfg)
    dbpath=Path(cfg.get('index','database'))
    if not dbpath.is_absolute(): dbpath=BASE/dbpath
    idx=Indexer(dbpath,rpc)
    mempool=MempoolTracker(rpc,cfg.getint('index','mempool_max_txs',fallback=12000),expected_genesis=GENESIS)
    idx.on_rewind=mempool.invalidate
    status={'remote_height':-1,'error':'Awaiting nextBTC Core connection'}
    def sync():
        while True:
            try:
                actual=rpc.call('getblockhash',0)
                status['wrong_chain']=actual!=GENESIS
                if status['wrong_chain']: raise RuntimeError('Wrong blockchain genesis. Refusing to index or broadcast')
                status['remote_height']=int(rpc.call('getblockcount'))
                processed=idx.sync_once(cfg.getint('index','batch_size'), cfg.getint('index','commit_every',fallback=25))
                status['error']=None
                explorer_app.extensions['statistics_worker'].wake.set()
                if processed: LOG.info('Indexed %d block(s), height %d / %d',processed,idx.tip()['height'],status['remote_height'])
                if processed: continue
            except Exception as e:
                status['error']=str(e);LOG.exception('Index sync failed')
            time.sleep(max(cfg.getfloat('index','poll_seconds'),1))
    def sync_mempool():
        while True:
            try:
                mempool.refresh()
                with idx.lock:
                    sample=mempool.get()
                    if not sample.get('error'):idx.record_mempool_snapshot(sample)
            except Exception as e:
                LOG.warning('Mempool sync failed: %s',e)
            time.sleep(max(cfg.getfloat('index','mempool_poll_seconds',fallback=10),2))
    wallet_host=cfg.get('server','host',fallback='127.0.0.1')
    wallet_port=cfg.getint('server','port',fallback=8777)
    explorer_host=cfg.get('explorer','host',fallback='127.0.0.1')
    explorer_port=cfg.getint('explorer','port',fallback=8778)
    if wallet_port == explorer_port and wallet_host == explorer_host:
        raise RuntimeError('Wallet API and Explorer cannot bind to the same host/port')
    wallet_app=make_app(cfg,idx,rpc,status,mempool,service='wallet')
    explorer_app=make_app(cfg,idx,rpc,status,mempool,service='explorer')
    # Acquire both sockets before indexing. A failed bind must fail startup.
    wallet_http = create_server(wallet_app, host=wallet_host, port=wallet_port, threads=8,channel_timeout=45,max_request_body_size=250000,max_request_header_size=32768)
    try:
        explorer_http = create_server(explorer_app, host=explorer_host, port=explorer_port, threads=8,channel_timeout=45,max_request_body_size=250000,max_request_header_size=32768)
        try:
            LOG.info('nextBTC Wallet API listening http://%s:%d',wallet_host,wallet_port)
            LOG.info('nextBTC Explorer listening http://%s:%d',explorer_host,explorer_port)
            threading.Thread(target=explorer_app.extensions['statistics_worker'].run, daemon=True, name='statistics').start()
            threading.Thread(target=sync, daemon=True, name='indexer').start()
            threading.Thread(target=sync_mempool, daemon=True, name='mempool').start()
            threading.Thread(target=wallet_http.run, daemon=True, name='wallet-http').start()
            explorer_http.run()
        finally:
            explorer_http.close()
    finally:
        wallet_http.close()

if __name__=='__main__': main()
