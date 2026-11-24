# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Create a safe source ZIP without operator config, databases, or build artifacts."""
import argparse
import hashlib
import re
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    '.git', '.pytest_cache', '__pycache__', '.venv', 'venv',
    'build', 'dist', 'backups', 'logs', 'tmp',
}
EXCLUDED_NAMES = {
    'config.ini', 'index.db', 'index.db-wal', 'index.db-shm',
    'final_acceptance_report.json', 'dwg_core_verification.json',
}
EXCLUDED_SUFFIXES = {'.exe', '.zip', '.sqlite-wal', '.pyc', '.pyo', '.log', '.db', '.sqlite', '.sqlite3'}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    # Ship product files only. The working tree can contain operator databases,
    # Core archives, previous executables, local verification logs and backups.
    if len(rel.parts) > 1 and rel.parts[0] not in {'tools', 'tests', 'web'}:
        return False
    if len(rel.parts) == 1:
        release_files = {'VERSION','config.example.ini','pytest.ini','nextbtc-index.service',
                         'statistics_worker.py','explorer_cache.py','server.py','indexer.py','explorer.py','explorer_transactions.py','explorer_chain_data.py','mempool.py','tools_generate_matrix.py',
                         'build_windows.bat','run_acceptance.bat','run_full_acceptance.bat',
                         'requirements.txt','requirements-dev.txt','DWG_CORE_REFERENCE.md',
                         'README.md','LICENSE','NOTICE',
                         'UPDATE_NOTES.txt','HANDOFF_TO_CHATGPT.md'}
        document = re.fullmatch(r'(README|MIGRATION|TEST_REPORT|API_REFERENCE|API_MATRIX|CHANGELOG)_[A-Za-z0-9_.-]+\.(md|txt)', path.name)
        if path.name not in release_files and not document:
            return False
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    # SQLite sidecars and arbitrary local database names must never enter a source release.
    lower_name = path.name.lower()
    if lower_name.endswith(('-wal', '-shm', '-journal')):
        return False
    if lower_name in {'.env', 'secrets.ini', 'config.local.ini'} or lower_name.endswith('.env'):
        return False
    if path.name.startswith('index_acceptance_') and path.suffix.lower() == '.db':
        return False
    return path.is_file()


def create_source_zip(destination: Path) -> dict:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in ROOT.rglob('*') if should_include(p) and p.resolve() != destination)
    if not files:
        raise RuntimeError('No source files found to package')
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(destination, 'r') as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f'ZIP integrity check failed at {bad}')
        names = set(archive.namelist())
        forbidden = [name for name in names if (Path(name).name.lower() in {'config.ini', '.env', 'secrets.ini', 'config.local.ini'}
                    or Path(name).suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pyc', '.pyo'}
                    or name.lower().endswith(('-wal', '-shm', '-journal')))]
        if forbidden:
            raise RuntimeError('Sensitive/runtime files entered source package: ' + ', '.join(forbidden[:10]))
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
    return {'sha256':digest, 'output': str(destination), 'file_count': len(files), 'size_bytes': destination.stat().st_size,
            'zip_integrity': 'ok', 'runtime_config_included': False, 'sample_config_included': 'config.example.ini' in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'dist' / f"nextBTC_Explorer_V{(ROOT/'VERSION').read_text().strip()}_Source.zip"))
    args = parser.parse_args()
    result = create_source_zip(Path(args.output))
    print(result)


if __name__ == '__main__':
    main()
