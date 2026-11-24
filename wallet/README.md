# nextBTC Wallet

**Version:** See [`VERSION`](VERSION)  
**Author:** btcdage  
**Project:** [nextBTC Suite](https://github.com/nextbtc2025/nextbtc-suite)  
**License:** MIT (repository root)

## Use

Open `nextBTC_Wallet_V0.5.83.html` in a modern browser. Create a wallet or import an existing key, then back up the wallet before funding it.

Configure an Index Server you operate or trust in Wallet settings. The default server address is a reserved example placeholder and is not a public service.

See the [root README](../README.md), [architecture](../docs/architecture.md), and [API compatibility notes](../docs/index-server-api.md) for system and server information.

## Security

Private keys are used locally in the browser for key derivation and transaction signing. Never share WIF/private keys, seed phrases or wallet passwords. Local transaction notes remain local by default. On-chain OP_RETURN memos are public and irreversible; do not include secrets or personal information.

The wallet has not been represented as having an independent professional security audit. Test with small amounts and verify transaction details before signing.
