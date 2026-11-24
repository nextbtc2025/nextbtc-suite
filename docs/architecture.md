# nextBTC Suite Architecture

## Components

nextBTC Suite contains two independently versioned and deployable components:

- **Wallet** (`wallet/`): a self-contained browser application. UI, cryptographic utilities, transaction construction, signing, encrypted local vault, backup, localization and QR support are packaged in one HTML file.
- **Index Server** (`indexserver/`): a Python service that connects to nextBTC Core, indexes chain data into SQLite, tracks Mempool information, and exposes separate Wallet API and Explorer HTTP services.

## Service topology

```text
Browser
  |
  +---- nextBTC Wallet (local HTML)
  |          |
  |          +---- Wallet API :8777
  |
  +---- Explorer UI :8778
                 |
             Explorer API
                 |
       Shared Indexer / Mempool
                 |
             SQLite DB
                 |
          nextBTC Core RPC :8554
```

The Wallet API and Explorer service have separate listeners and route boundaries. They share indexing and database infrastructure. Default binds are loopback addresses; deployments using a reverse proxy or FRP may map different public hosts and ports.

## Wallet data flow

1. The browser loads the wallet HTML.
2. The user configures an Index Server endpoint.
3. The wallet queries network status, addresses, UTXOs, fee estimates and transaction history.
4. Private keys remain in the browser for key derivation and signing.
5. The wallet submits signed raw transaction data to the configured server for broadcast.
6. Local transaction notes remain local by default. An OP_RETURN memo is included only after explicit user opt-in and is public on-chain data.

## Indexing data flow

1. nextBTC Core provides chain and Mempool information over its private RPC interface.
2. Index Server synchronizes blocks and transactions and maintains indexed address/UTXO data in SQLite.
3. Wallet API serves wallet-facing endpoints.
4. Explorer serves the bilingual browser interface and read-only browsing APIs.
5. Background workers maintain derived statistics and cached views.

## Trust boundaries

- The Core RPC interface must remain private and must not be exposed directly to the public Internet.
- An Index Server can observe queried addresses and signed transactions submitted for broadcast. Users should operate or select a server they trust.
- Browser wallet data is local to the browser profile/device unless explicitly backed up.
- On-chain OP_RETURN content is public and generally irreversible.
- Public Explorer deployments should use deliberate reverse-proxy, TLS, CORS, rate-limit and access-control settings.
