# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

#!/usr/bin/env python3
"""Create a consistent SQLite backup of index.db, including live WAL state."""
import argparse, sqlite3, sys, time
from pathlib import Path

def backup_database(source_path,destination_path):
    source=Path(source_path).resolve(); destination=Path(destination_path).resolve()
    if not source.is_file():raise FileNotFoundError(source)
    if source==destination:raise ValueError('Backup destination must differ from source')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise FileExistsError(destination)
    src=sqlite3.connect(str(source),timeout=30)
    dst=sqlite3.connect(str(destination),timeout=30)
    try:
        src.backup(dst,pages=100,sleep=0.05)
        result=dst.execute('PRAGMA integrity_check').fetchone()[0]
        if result!='ok':raise RuntimeError('Backup integrity_check failed: '+str(result))
        dst.commit()
    except Exception:
        dst.close();src.close()
        try:destination.unlink()
        except OSError:pass
        raise
    dst.close();src.close()
    return {'source':str(source),'destination':str(destination),'integrity_check':'ok','size_bytes':destination.stat().st_size}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database')
    p.add_argument('--output')
    args=p.parse_args()
    output=args.output or str(Path(args.database).with_name(Path(args.database).stem+'_backup_'+time.strftime('%Y%m%d_%H%M%S')+'.db'))
    report=backup_database(args.database,output)
    print(report)
if __name__=='__main__':main()
