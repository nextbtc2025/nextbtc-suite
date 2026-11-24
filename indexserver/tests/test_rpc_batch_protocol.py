# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class TestRpcBatchProtocol(unittest.TestCase):
    def test_rpc_batch_chunks_maps_out_of_order_results_and_blocks_writes(self):
        script=r'''
import sys,types,configparser
flask=types.ModuleType('flask')
flask.send_from_directory=lambda *a,**k:None
flask.Flask=object
flask.request=object()
flask.jsonify=lambda *a,**k:None
sys.modules['flask']=flask
waitress=types.ModuleType('waitress');waitress.serve=lambda *a,**k:None;sys.modules['waitress']=waitress
import server
cp=configparser.ConfigParser();cp.read_dict({'rpc':{'url':'http://127.0.0.1:8554','user':'','password':'','cookie_file':'','timeout':'5','max_retries':'0','retry_delay':'0','retry_max_delay':'0','pool_size':'2'}})
rpc=server.RPC(cp)
class Response:
 def __init__(self,body):self.body=body
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def raise_for_status(self):pass
 def json(self):return self.body
class Session:
 def __init__(self):self.calls=[]
 def post(self,url,**kwargs):
  payload=kwargs['json'];self.calls.append(payload)
  return Response([{'id':item['id'],'result':item['params'][0]} for item in reversed(payload)])
session=Session();rpc._session=lambda:session
params=[[str(i),True] for i in range(205)]
result=rpc.batch('getrawtransaction',params,batch_size=100)
assert result==[str(i) for i in range(205)]
assert [len(c) for c in session.calls]==[100,100,5]
try:rpc.batch('sendrawtransaction',[['00']])
except ValueError:pass
else:raise AssertionError('write RPC was allowed in batch')
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode,0,result.stdout)

if __name__=='__main__':unittest.main()
