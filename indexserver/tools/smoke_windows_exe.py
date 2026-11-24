# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Exercise a packaged release on two temporary loopback ports with Core offline."""
import argparse
import configparser
from contextlib import contextmanager
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@contextmanager
def temporary_installation():
    temp = tempfile.TemporaryDirectory(prefix='nextbtc-exe-')
    try:
        yield temp.name
    finally:
        # Windows can keep the one-file loader's image mapped briefly after
        # taskkill reports that its parent and child have exited.
        deadline = time.monotonic() + 15
        while True:
            try:
                temp.cleanup()
                break
            except OSError as exc:
                if exc.winerror not in (5, 32, 267) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)


def check_exe(binary):
    with temporary_installation() as directory:
        install = Path(directory)
        exe = Path(shutil.copy2(binary, install))
        # Exercise the first-run path before switching to isolated test ports.
        first=subprocess.Popen([str(exe)],cwd=install,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+30
            while not (install/'index.db').exists() and time.monotonic()<deadline:
                if first.poll() is not None:break
                time.sleep(.1)
            generated=configparser.ConfigParser()
            generated.read(install/'config.ini',encoding='utf-8')
            assert generated.getint('server','port')==8777 and generated.getint('explorer','port')==8778
            assert (install/'index.db').is_file()
        finally:
            if first.poll() is None:
                subprocess.run(['taskkill','/PID',str(first.pid),'/T','/F'],check=True,stdout=subprocess.DEVNULL)
                first.wait(timeout=10)
        ports = set()
        while len(ports) < 3:
            ports.add(free_port())
        wallet_port, explorer_port, offline_core = sorted(ports)
        config = configparser.ConfigParser()
        config.read(ROOT / 'config.example.ini', encoding='utf-8')
        config['server']['port'] = str(wallet_port)
        config['explorer']['port'] = str(explorer_port)
        config['explorer']['admin_token']='local-smoke-token'
        config['rpc'].update(url=f'http://127.0.0.1:{offline_core}', max_retries='0', timeout='1')
        with (install / 'config.ini').open('w', encoding='utf-8') as out:
            config.write(out)
        session = requests.Session()
        session.trust_env = False
        wallet = f'http://127.0.0.1:{wallet_port}'
        explorer = f'http://127.0.0.1:{explorer_port}'
        with (install / 'console.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(exe)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f'EXE exited with code {process.returncode}')
                    try:
                        if session.get(wallet+'/api/v1/status', timeout=1).status_code == 200:
                            break
                    except requests.ConnectionError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError('Wallet listener did not start')
                for host, path, code in [(explorer,'/',200),(explorer,'/api/v1/explorer/capabilities',200),
                                         (wallet,'/',404),(wallet,'/api/v1/explorer/summary',404),
                                         (explorer,'/api/v1/status',404),(explorer,'/api/v1/broadcast',404),
                                         (explorer,'/api/v1/explorer/summary',503)]:
                    response = session.get(host + path, timeout=3)
                    assert response.status_code == code, (path, response.status_code)
                assert session.post(explorer+'/api/v1/broadcast', json={}, timeout=3).status_code == 404
                assets = ROOT / 'web' / 'explorer'
                count = 0
                for asset in assets.rglob('*'):
                    if asset.is_file():
                        route = '/explorer/' + asset.relative_to(assets).as_posix()
                        response = session.get(explorer + route, timeout=5)
                        if asset.name=='monitor.html':
                            assert response.status_code==401,route
                            response=session.get(explorer+route,auth=('admin','local-smoke-token'),timeout=5)
                        assert response.status_code == 200 and response.content == asset.read_bytes(), route
                        if asset.suffix == '.js':
                            assert 'javascript' in response.headers['Content-Type'], route
                        count += 1
                assert (install/'index.db').is_file()
                assert log.tell() or (install/'console.log').stat().st_size
            finally:
                session.close()
                if process.poll() is None:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                                   check=True, stdout=subprocess.DEVNULL)
                    process.wait(timeout=10)

    print(f'PASS: packaged dual listeners, cross-service 404s, {count} bundled assets, sibling config/database, console output and temporary process cleanup')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    check_exe(parser.parse_args().exe.resolve())
