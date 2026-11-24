# nextBTC Index Server

**A self-hosted blockchain indexer, Wallet API and Explorer for the nextBTC network.**

- Version: see [`VERSION`](VERSION)
- Author: **btcdage**
- Author site: [btcdage2011.github.io](https://btcdage2011.github.io) / [btcdage.rf.gd](https://btcdage.rf.gd)
- Monorepo: [nextbtc2025/nextbtc-suite](https://github.com/nextbtc2025/nextbtc-suite)
- License: [MIT](LICENSE)

This component works with a synchronized nextBTC Core node. It is not a full node and does not replace consensus validation performed by nextBTC Core.

## Features

- Indexes confirmed blocks, transactions, outputs, address activity and UTXO state into SQLite.
- Provides separate Wallet API and Explorer web/API services.
- Tracks Mempool information and fee distribution where available from the configured Core node.
- Explorer pages for network overview, blocks, transactions, addresses and Mempool.
- Network hashrate and difficulty charts, DWG difficulty information and advanced network statistics.
- Displays supported on-chain `OP_RETURN` payloads in transaction details. Local wallet notes are not blockchain data and are not indexed.
- Simplified Chinese and English interface.
- Database backup, audit, migration, acceptance-test and Windows packaging tools.

## Architecture and default ports

| Service | Default bind | Purpose |
|---|---|---|
| Wallet API | `127.0.0.1:8777` | Wallet-facing API |
| Explorer | `127.0.0.1:8778` | Explorer website and API |
| nextBTC Core RPC | `127.0.0.1:8554` | Local node RPC; never expose publicly |

Wallet API and Explorer use separate listeners and route boundaries while sharing the indexer, Mempool tracker and SQLite database. FRP or reverse-proxy public ports may differ from these local defaults. Configure the actual endpoint, CORS and access controls for your deployment.

## Requirements

- Windows 10/11 for the supplied Windows build workflow.
- Python 3.11.
- A running and synchronized nextBTC Core node with RPC enabled.
- Runtime packages: Flask, requests and waitress.
- For tests and packaging: pytest and PyInstaller.

## Source setup (Windows PowerShell)

From the repository root:

```powershell
cd indexserver
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install Flask requests waitress
python -m pip install pytest pyinstaller
Copy-Item config.example.ini config.ini
```

Edit `config.ini` with your own Core RPC URL, credentials and data paths. Never commit a real configuration file or credentials.

Start the service from this directory:

```powershell
python server.py
```

Check the startup log for actual listening addresses and confirm that the Index Server can reach Core RPC.

## Windows executable

With the virtual environment activated and dependencies installed, run:

```powershell
.\build_windows.bat
```

The script builds a console-enabled Windows executable with PyInstaller. Keep the real `config.ini`, database, logs and backups separate from the public source tree.

## API and operations documentation

- [`API_REFERENCE_V1.0.33.md`](API_REFERENCE_V1.0.33.md)
- [`API_MATRIX_V1.0.33.md`](API_MATRIX_V1.0.33.md)
- [`MIGRATION_V1.0.33.md`](MIGRATION_V1.0.33.md)
- [`CHANGELOG_V1.0.33.md`](CHANGELOG_V1.0.33.md)
- [`DWG_CORE_REFERENCE.md`](DWG_CORE_REFERENCE.md)

The running server implementation is authoritative if a document and actual route behavior differ.

## Testing

Run the automated tests from this directory:

```powershell
python -m pytest
```

The acceptance scripts may require a running nextBTC Core node and a populated index database. Report unavailable environment-dependent checks as skipped/unavailable, not passed.

## Security and privacy

- `config.ini` may contain RPC credentials. Never commit it.
- Do not commit production databases, SQLite WAL/SHM files, logs, backups or generated executables.
- Keep Core RPC bound to loopback or a protected private network.
- Public deployments should use an appropriately configured reverse proxy, TLS, authentication for administrative functions, rate limiting and CORS.
- On-chain `OP_RETURN` contents are public and generally immutable. Never put secrets or personal information in them.
- Address statistics follow the indexer's address-extraction model; not every script type necessarily maps to a conventional address.

## Third-party components

Browser assets under `web/explorer/vendor/` retain their original license and notice files, including Bootstrap, Apache ECharts and the QR-code library. The repository MIT license does not replace or override third-party licenses.

## Contributing and disclaimer

Contributions are welcome through the [nextBTC Suite repository](https://github.com/nextbtc2025/nextbtc-suite). Do not submit credentials, private keys, seed phrases or production data.

This software provides indexing, API and Explorer functionality; it is not a custody service and does not guarantee external node configuration, network availability or third-party infrastructure. Verify consensus-sensitive and financial information against nextBTC Core and trusted node data.
