# Wallet Architecture

## Overview

The wallet is a single-file browser application. Its HTML contains the UI,
styles, application logic, cryptographic utilities, transaction builder,
encrypted vault, backup functions, localization, and bundled QR generation.

There is no wallet backend in this repository. Chain data and transaction
broadcasting are provided by a separately operated compatible Index Server.

## Main components

- **UI and navigation:** wallet pages, dialogs, notifications, settings, and
  responsive controls.
- **WIF/address utilities:** key import/generation and nextBTC address derivation.
- **Transaction engine:** UTXO selection, transaction serialization, fee and
  change calculation, deterministic ECDSA signing, and optional OP_RETURN output.
- **Encrypted vault:** local multi-account storage and unlock/session handling.
- **Portable backup:** independently password-protected wallet backup.
- **QR support:** address/transaction display and QR scanning using the bundled
  QRCode for JavaScript implementation.
- **Localization:** Chinese and English UI text.

## Data flow

1. The browser loads the wallet file.
2. The user configures an Index Server URL.
3. The wallet queries status, addresses, UTXOs, fees, and history from that
   server.
4. Private keys remain in the browser for key derivation and transaction signing.
5. The wallet submits the signed raw transaction HEX to the configured server
   for broadcast.
6. Optional market-price requests are made to public market-data providers only
   when the user enables the USD valuation display.

## Local data

Wallet vault data, UI preferences, and local transaction notes are stored in
browser storage. They are tied to the browser profile/device and are not
automatically synchronized across devices. Users should maintain encrypted
wallet backups separately.

## Trust boundaries

The configured Index Server is not a trusted source of private-key custody.
It can observe address queries and signed transactions submitted for broadcast.
Users should operate or select a server they trust and verify transaction
details independently before signing.
