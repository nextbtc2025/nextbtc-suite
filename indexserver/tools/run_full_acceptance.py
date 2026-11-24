# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Run the release regression, database copy audit and live nextBTC checks."""
import argparse
import configparser
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MIN_EXPECTED_TESTS = 81
sys.path.insert(0, str(ROOT))
from tools.backup_index_db import backup_database
from tools.audit_index_db import audit
from tools.migrate_index_db import migrate_database


def run(command, env, timeout=1800):
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
        return {'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'returncode': result.returncode, 'output': result.stdout + result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'FAIL', 'reason': str(exc)}


def skipped(reason):
    return {'status': 'SKIPPED', 'reason': reason}


def write_dwg_skipped_report(path, reason):
    report = dict(skipped(reason), historical_matches=None, getblocktemplate_match=None)
    Path(path).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--database', type=Path, help='database to back up and audit (defaults to configured database)')
    ap.add_argument('--config', type=Path, default=ROOT/'config.ini')
    ap.add_argument('--samples', type=int, default=1000)
    ap.add_argument('--require-live-core', action='store_true')
    ap.add_argument('--build-exe', action='store_true')
    ap.add_argument('--browser', action='store_true',help='check desktop and mobile layouts using installed Chrome')
    ap.add_argument('--output', type=Path, default=ROOT/'final_acceptance_report.json')
    args = ap.parse_args()
    if not 1 <= args.samples <= 10000:
        ap.error('--samples must be 1..10000')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONPATH=str(ROOT),
               PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
    py = sys.executable
    checks = {}
    version = (ROOT / 'VERSION').read_text().strip()
    report = {'version': version, 'started_at_unix': int(time.time()), 'checks': checks}
    checks['python_compile'] = run([py,'-m','compileall','-q','tools','tests',
                                    *[str(p) for p in ROOT.glob('*.py')]], env)
    required = ['pytest','flask','waitress','requests']
    missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]
    if missing:
        checks['pytest'] = {'status':'FAIL','reason':'Missing test dependencies: '+', '.join(missing)}
    else:
        suite = run([py,'-m','pytest','-q','-rs','-p','no:cacheprovider','tests'], env)
        checks['pytest'] = suite
        output = suite.get('output', '')
        counts = {kind: sum(map(int, re.findall(r'(\d+) '+kind+r'\b', output)))
                  for kind in ['passed','skipped','failed']}
        suite['counts'] = counts
        if suite['status'] == 'PASS':
            if counts['passed'] + counts['skipped'] < MIN_EXPECTED_TESTS:
                suite.update(status='FAIL', reason='Incomplete test discovery')
            elif counts['skipped']:
                suite.update(status='SKIPPED', reason='Suite includes skipped tests; see counts and output')
    scripts = sorted((ROOT / 'web' / 'explorer').rglob('*.js'))
    node = shutil.which('node')
    if node:
        js = {p.relative_to(ROOT).as_posix():run([node,'--check',str(p)],env) for p in scripts}
        checks['javascript_syntax'] = {'status':'PASS' if js and all(v['status']=='PASS' for v in js.values()) else 'FAIL',
                                       'files': js}
    else:
        checks['javascript_syntax'] = skipped('Node.js is unavailable')
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(args.config, encoding='utf-8-sig')
    database = args.database or args.config.parent/cfg.get('index','database',fallback='index.db')
    if database.is_file():
        backup = ROOT/'backups'/f'index_acceptance_{time.time_ns()}.db'
        try:
            checks['database_backup'] = dict(backup_database(database,backup),status='PASS')
            checks['database_migration'] = dict(migrate_database(backup),status='PASS')
            audited = audit(backup)
            checks['database_audit'] = dict(audited,status='PASS' if audited['ok'] else 'FAIL')
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            checks['database_copy_checks'] = {'status':'FAIL','reason':str(exc)}
    elif args.database:
        checks['database_copy_checks'] = {'status':'FAIL','reason':'Specified database does not exist'}
    else:
        checks['database_copy_checks'] = skipped('No existing database supplied')
    dwg_output = args.output.resolve().with_name('dwg_core_verification.json')
    if args.config.is_file():
        dwg = run([py,'tools/verify_dwg_core.py','--config',str(args.config.resolve()),'--samples',
                   str(args.samples),'--output',str(dwg_output)],env)
        if dwg['status'] == 'FAIL' and any(t in dwg.get('output','').lower()
                  for t in ('connectionrefusederror','winerror 10061','connection refused','timed out')):
            dwg = skipped('Configured nextBTC Core RPC is unreachable')
    else:
        dwg = skipped('RPC config.ini is unavailable')
    if dwg['status'] == 'SKIPPED':
        write_dwg_skipped_report(dwg_output, dwg['reason'])
        if args.require_live_core:
            dwg['status'] = 'FAIL'
    checks['live_dwg_core'] = dwg
    if dwg['status']=='PASS' and checks.get('database_audit', {}).get('status')=='PASS':
        checks['live_explorer_http'] = run([py,'tools/verify_live_explorer.py',
            '--config',str(args.config.resolve()),'--database-copy',str(backup)],env)
        live = checks['live_explorer_http']
        if live['status'] == 'PASS':
            # The verifier writes JSON to stdout and server logs to stderr.
            details, _ = json.JSONDecoder().raw_decode(live['output'].lstrip())
            live['summary'] = {k:v for k,v in details.items() if k!='paths'}
            checks['live_nonempty_mempool_dependencies'] = (
                {'status':'PASS'} if details['live_mempool_tx_dependencies']=='PASS'
                else skipped('Observed Core snapshot contained zero transactions'))
    else:
        checks['live_explorer_http'] = skipped('Requires verified Core and audited backup')
    if args.browser:
        checks['observed_mempool_browser_fixture'] = run([py,'tools/verify_mempool_ui.py'],env)
        if checks['live_explorer_http']['status']=='PASS':
            checks['browser'] = run([py,'tools/verify_explorer_ui.py','--config',
                str(args.config.resolve()),'--database-copy',str(backup)],env)
        else:
            checks['browser'] = skipped('Requires successful live Explorer and database checks')
    else:
        checks['browser'] = skipped('Use --browser with a local Chrome installation')
    if args.build_exe and os.name == 'nt':
        env['PYINSTALLER_CONFIG_DIR'] = str(ROOT/'build'/'pyinstaller-cache')
        checks['windows_exe_build'] = run(['cmd','/c',str(ROOT/'build_windows.bat')],env)
        if checks['windows_exe_build']['status']=='PASS':
            checks['windows_exe_http'] = run([py,'tools/smoke_windows_exe.py',
                                       f'dist/nextBTC_IndexServer_V{version}.exe'],env)
    else:
        checks['windows_exe_build'] = skipped('Windows with --build-exe required')
    statuses = {c['status'] for c in checks.values()}
    report['status'] = 'FAIL' if 'FAIL' in statuses else 'SKIPPED' if 'SKIPPED' in statuses else 'PASS'
    report['finished_at_unix'] = int(time.time())
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    for name, value in checks.items():
        print(name, value['status'], value.get('reason',''))
    print('Report:', args.output)
    return 1 if 'FAIL' in statuses else 0


if __name__ == '__main__':
    sys.exit(main())
