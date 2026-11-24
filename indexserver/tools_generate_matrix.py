# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import ast,re,pathlib
root=pathlib.Path(__file__).resolve().parent
src=(root/'server.py').read_text(encoding='utf-8')
tree=ast.parse(src)
rows=set()
for node in ast.walk(tree):
    if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
    for dec in node.decorator_list:
        if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr in {'get','post'} and dec.args and isinstance(dec.args[0],ast.Constant):
            path=dec.args[0].value
            if path.startswith('/api/v1/explorer/'):
                rows.add((dec.func.attr.upper(),path,node.name))
version=(root/'VERSION').read_text().strip()
lines=[f'# Complete Explorer API Matrix — V{version}','', 'All Explorer endpoints are read-only GET routes. Pagination and bounded result limits are enforced by the handlers.','', '| Method | Endpoint | Handler |','|---|---|---|']
for method,path,handler in sorted(rows): lines.append(f'| {method} | `{path}` | `{handler}` |')
(root/f'API_MATRIX_V{version}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Wrote API_MATRIX_V{version}.md with {len(rows)} routes')
