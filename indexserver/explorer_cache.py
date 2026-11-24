"""Bounded, tip-aware caching for public Explorer GET requests."""
from collections import OrderedDict
from functools import wraps
from threading import Event, Lock
from time import monotonic, time
from flask import request, jsonify

class ExplorerCache:
    def __init__(self):
        self.lock=Lock()
        self.entries=OrderedDict()
        self.flights={}
        self.bytes=0
        self.hits=self.misses=self.updated=self.calls=self.slow=self.elapsed=0

    def metrics(self):
        with self.lock:
            return dict(hits=self.hits,misses=self.misses,entries=len(self.entries),updated=self.updated,
                        hit_percent=round(100*self.hits/max(1,self.hits+self.misses),2),
                        average_ms=round(self.elapsed*1000/max(1,self.calls),2),slow=self.slow)

    def observe(self,elapsed):
        with self.lock:
            self.calls+=1
            self.elapsed+=elapsed
            self.slow+=elapsed>=1

    def wrap(self,app,handler,index,pool,ttl):
        @wraps(handler)
        def serve(**kwargs):
            tip=index.tip() or {}
            snap=pool.get() if pool and ('mempool' in request.path or request.path.endswith('/summary')) else {}
            key=(request.full_path,tip.get('height'),tip.get('hash'),snap.get('updated'),bool(snap.get('error')),
                 time()-snap.get('updated',0)>60)
            with self.lock:
                item=self.entries.get(key)
                if item and item[0]>monotonic():
                    self.hits+=1
                    self.entries.move_to_end(key)
                    result=app.response_class(item[1],mimetype='application/json')
                    result.headers['X-Explorer-Cache']='HIT'
                    return result
                event=self.flights.get(key)
                if event is None:
                    event=self.flights[key]=Event()
                    self.misses+=1
                    owner=True
                else:owner=False
            if not owner:
                if event.wait(5):
                    with self.lock:
                        item=self.entries.get(key)
                        if item and item[0]>monotonic():
                            self.hits+=1
                            result=app.response_class(item[1],mimetype='application/json')
                            result.headers['X-Explorer-Cache']='HIT'
                            return result
                return jsonify(error='Request busy; retry shortly'),429
            try:
                response=app.make_response(handler(**kwargs))
                if response.status_code==200 and response.is_json and response.headers.get('X-Explorer-Cache')!='BYPASS':
                    body=response.get_data()
                    if len(body)<=2_000_000:
                        with self.lock:
                            old=self.entries.pop(key,None)
                            if old:self.bytes-=len(old[1])
                            self.entries[key]=(monotonic()+ttl,body)
                            self.bytes+=len(body)
                            self.updated=int(time())
                            while len(self.entries)>512 or self.bytes>32_000_000:
                                self.bytes-=len(self.entries.popitem(last=False)[1][1])
                return response
            finally:
                with self.lock:
                    self.flights.pop(key,None)
                    event.set()
        return serve
