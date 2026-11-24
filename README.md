# nextBTC Suite

**Open-source wallet and blockchain infrastructure for the nextBTC ecosystem.**

nextBTC Suite brings together two independently deployable components:

- **nextBTC Wallet** — a self-contained, non-custodial browser wallet.
- **nextBTC Index Server** — a self-hosted blockchain indexer, Wallet API and bilingual Explorer.

Both components are maintained in this repository and have independent version numbers.

- Wallet version: see [`wallet/VERSION`](wallet/VERSION)
- Index Server version: see [`indexserver/VERSION`](indexserver/VERSION)
- Author: **btcdage**
- Author site: [btcdage2011.github.io](https://btcdage2011.github.io) / [btcdage.rf.gd](https://btcdage.rf.gd)
- GitHub: [nextbtc2025/nextbtc-suite](https://github.com/nextbtc2025/nextbtc-suite)
- License: [MIT](LICENSE)

## Components

### nextBTC Wallet

A single-file browser wallet. Open the HTML file in `wallet/` with a modern browser.

- Non-custodial key handling and local transaction signing.
- Local encrypted multi-account vault and password-protected backup.
- Wallet creation, private-key import and watch-only accounts.
- Legacy, Nested SegWit and Native SegWit address formats supported by the configured nextBTC network.
- UTXO-based balance, transaction construction, fee selection and change calculation.
- Transaction preview and confirmation.
- Local transaction notes by default.
- Optional on-chain memo output through explicit OP_RETURN opt-in. On-chain data is public and irreversible and may increase transaction fees.
- QR scanning and transaction data export.

The wallet requires a compatible Index Server for chain data, UTXO queries, fee estimates, transaction history and transaction broadcast.

### nextBTC Index Server

A Python service designed to work with a synchronized nextBTC Core node.

- Indexes confirmed blocks, transactions, outputs, address activity and UTXO state into SQLite.
- Provides a Wallet API and a separately hosted Explorer web/API service.
- Displays network overview, blocks, transactions, addresses and Mempool information.
- Provides hashrate and difficulty charts, DWG difficulty information and advanced network statistics.
- Reads supported on-chain OP_RETURN payloads for display in transaction details.
- Simplified Chinese and English Explorer interface.
- Database backup, audit, migration, acceptance-test and Windows packaging tools.

See [`indexserver/README.md`](indexserver/README.md) for setup, configuration, ports, API references and Windows packaging.

## Architecture

```text
                         nextBTC Core
                    RPC (default 127.0.0.1:8554)
                              |
                     Indexer / Mempool
                              |
                       Shared SQLite DB
                       /              \
                      /                \
          Wallet API service       Explorer service
             127.0.0.1:8777          127.0.0.1:8778
          wallet endpoints          Web UI + Explorer API
                 ^
                 |
          nextBTC Wallet (browser)
```

The Wallet API and Explorer service use separate listening configuration and route boundaries while sharing the indexer, Mempool tracker and database. Default addresses are loopback-only. These are local defaults, not fixed public FRP ports. Do not expose the Core RPC port to the public Internet.

## Quick start

### Wallet

1. Open `wallet/nextBTC_Wallet_V0.5.83.html` in a modern browser.
2. Create a wallet or import an existing key.
3. Back up the wallet before funding it.
4. In Wallet settings, configure the URL of an Index Server you operate or trust.
5. Verify the network and address format before sending funds.

### Index Server

Follow the instructions in [`indexserver/README.md`](indexserver/README.md). In brief, the Index Server requires Python 3.11, its Python dependencies, and a running nextBTC Core node with RPC enabled. Configure it using `indexserver/config.example.ini` as a reference. Keep real credentials in a private `config.ini` and never commit that file.

The default local service ports are:

| Service | Default bind | Purpose |
|---|---|---|
| Wallet API | `127.0.0.1:8777` | Wallet-facing API |
| Explorer | `127.0.0.1:8778` | Explorer website and API |
| Core RPC | `127.0.0.1:8554` | Local node RPC; do not expose publicly |

A reverse proxy or FRP deployment may use different public hostnames and ports. Configure the actual endpoint, CORS allow-list and access controls for the deployment; do not assume the public port is 8777 or 8778.

## Documentation

- [Architecture](docs/architecture.md)
- [Wallet / Index Server API compatibility](docs/index-server-api.md)
- [Index Server setup and operations](indexserver/README.md)
- [Index Server API reference](indexserver/API_REFERENCE_V1.0.33.md)
- [Index Server API matrix](indexserver/API_MATRIX_V1.0.33.md)
- [Index Server migration notes](indexserver/MIGRATION_V1.0.33.md)
- [Index Server changelog](indexserver/CHANGELOG_V1.0.33.md)

## Security and privacy

- Private keys are handled in the browser for key derivation and signing. The wallet submits signed transaction data to the configured Index Server for broadcast. Never send a WIF/private key or seed phrase to an Index Server.
- An Index Server can observe queried addresses, request timing and signed transactions submitted for broadcast. Use a server you operate or trust.
- Wallet data and local notes are stored in the browser profile/device and are not automatically synchronized between devices. Maintain encrypted backups.
- On-chain OP_RETURN data is public and generally irreversible. Do not include secrets or personal information.
- Keep Core RPC private. Do not commit `config.ini`, RPC credentials, private keys, production databases, logs or backups.
- When exposing services publicly, configure an appropriate reverse proxy, TLS, authentication where applicable, rate limits and CORS.
- The software has not been represented as having an independent professional security audit. Test with small amounts and independently verify transaction details before signing.

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting guidance.

## Contributing

Issues and pull requests are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting changes. Never include secrets, wallet data or production databases in issues or pull requests.

## Third-party components

Third-party license and attribution information is collected in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The repository MIT license does not replace or override licenses of bundled third-party components.

## Disclaimer

This software is provided for nextBTC wallet, indexing, API and Explorer purposes. It is not a hosted custody service and does not guarantee external node configuration, network availability or third-party infrastructure. Verify consensus-sensitive and financial information against nextBTC Core and trusted node data.
