# nextBTC Suite

**Open-source wallet and infrastructure for the nextBTC ecosystem.**

This repository is being opened in stages. The first published component is the
**nextBTC non-custodial browser wallet**. The Index Server implementation is
still under development and is intentionally **not included** in this repository
at this time.

- Current wallet version: **V0.5.83 USD Special**
- License: **MIT** (see [`LICENSE`](LICENSE))
- Wallet source: [`wallet/nextBTC_Wallet_V0.5.83_USD_Special.html`](wallet/nextBTC_Wallet_V0.5.83_USD_Special.html)
- 中文说明: [`README.zh-CN.md`](README.zh-CN.md)
- GitHub repository: https://github.com/nextbtc2025/nextbtc-suite

## What is included

The wallet is distributed as a single self-contained HTML file. It does not
require a Node.js build step or external JavaScript/CSS CDN libraries.

Current wallet capabilities include:

- Browser-based, non-custodial wallet workflow.
- Local encrypted multi-account vault and password-protected portable backup.
- Private-key import and wallet creation, plus watch-only accounts.
- Legacy (P2PKH), Nested SegWit (P2SH-P2WPKH), and Native SegWit (P2WPKH)
  address support for the configured nextBTC network.
- UTXO-based balance display, transaction construction, fee selection,
  change calculation, signing, and broadcast through a compatible Index Server.
- Transaction preview and confirmation, including change output details.
- Optional local transaction notes. Notes remain in the current browser and are
  not included in the transaction by default.
- Explicit opt-in OP_RETURN memo output. On-chain memos are public, irreversible,
  and increase transaction size and miner fees.
- QR scanning, signed-transaction HEX display, copy/download, and QR image export.
- Optional USD reference valuation. Market-price requests are only relevant when
  the user enables the hidden valuation display; a displayed estimate is not a
  guaranteed executable exchange price.

## Quick start

1. Download the wallet HTML file from the `wallet/` directory.
2. Open it in a modern browser.
3. Create a wallet or import an existing key. Back up the wallet before funding it.
4. Open the wallet's Index Server settings and enter the URL of a compatible
   Index Server that you operate or trust.
5. Confirm the network status and address format before sending any funds.

The public source intentionally uses this reserved example URL as its initial
configuration:

```text
https://your-index-server.example:8777
```

This is a documentation placeholder, not a working service. Replace it with
your own compatible Index Server URL in the wallet settings, or edit the
`INDEX_SERVER_DEFAULT` constant near the top of the main application script.

HTTPS is recommended for remote deployments. HTTP may be suitable only in a
trusted local network. Browser certificate handling depends on the browser and
the server certificate configuration.

## Index Server requirement

**The Index Server source code is not part of this first wallet release.**
The wallet requires a separately available, API-compatible Index Server for
chain data, UTXO queries, fee estimates, transaction history, and broadcasting.

The current wallet calls these API routes:

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/status` | Network and index status; spend-safety capability |
| POST | `/api/v1/addresses/query` | Address and UTXO data |
| GET | `/api/v1/fees` | Fee-rate suggestions |
| GET | `/api/v1/history/{address}` | Address transaction history |
| GET | `/api/v1/tx/{txid}` | Transaction state |
| POST | `/api/v1/broadcast` | Broadcast signed raw transaction HEX |

For spending, the status response must advertise
`capabilities.mempool_spend_guard: true`. If the server does not provide the
required capability, the wallet may restrict sending for safety. Route names
alone do not guarantee compatibility; request/response schemas and chain
parameters must also match the wallet version.

## Network compatibility

This wallet is configured for the **nextBTC network** and its compatible
Index Server API. Do not assume that it is ready for Bitcoin mainnet or another
Bitcoin-derived network. Address prefixes, network parameters, consensus rules,
and server behavior must be independently verified before using another chain.

## Security notes

- Private keys are handled in the browser and are used locally to derive
  addresses and sign transactions. The wallet sends the signed transaction HEX
  to the selected Index Server for broadcasting; never send a WIF/private key
  to an Index Server or another person.
- The selected Index Server can observe queried addresses, request timing, and
  signed transactions submitted for broadcast. Use a server you operate or
  trust.
- Browser storage is local to the browser profile/device. Local notes and
  wallet data do not automatically move to another computer.
- An OP_RETURN memo is public and cannot be removed after the transaction is
  confirmed. Do not put passwords, private keys, personal data, or confidential
  information in an on-chain memo.
- USD values are estimates and can be stale or unavailable.
- This release has not undergone an independent professional security audit.
  Test with small amounts first. Do not use it to store funds you cannot afford
  to lose. Verify addresses and transaction details on a trusted independent
  device or explorer before confirming.

## Repository layout

```text
nextbtc-suite/
├── wallet/
│   ├── nextBTC_Wallet_V0.5.83_USD_Special.html
│   ├── VERSION
│   └── README.md
├── docs/
│   ├── architecture.md
│   └── index-server-api.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── CONTRIBUTING.md
├── SECURITY.md
├── README.md
└── README.zh-CN.md
```

The Index Server will be added only after its development and release review
are complete.

## License

The project is released under the MIT License. See [`LICENSE`](LICENSE) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for third-party notices.
