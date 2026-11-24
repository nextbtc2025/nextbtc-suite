# Wallet / Index Server API Compatibility

The Wallet and Index Server are maintained in this repository but are independently versioned. Always check the Wallet's expected API contract against the Index Server version you deploy.

The current Wallet API contract and Index Server routes are documented in:

- [`indexserver/API_REFERENCE_V1.0.33.md`](../indexserver/API_REFERENCE_V1.0.33.md)
- [`indexserver/API_MATRIX_V1.0.33.md`](../indexserver/API_MATRIX_V1.0.33.md)

The Wallet uses the following route families:

| Method | Path | Wallet use |
|---|---|---|
| GET | `/api/v1/status` | Network/index status and spend-safety capability |
| POST | `/api/v1/addresses/query` | Address balances and UTXO data |
| GET | `/api/v1/fees` | Fee-rate suggestions |
| GET | `/api/v1/history/{address}` | Address transaction history |
| GET | `/api/v1/tx/{txid}` | Transaction state |
| POST | `/api/v1/broadcast` | Submit signed raw transaction data |

## Spend-safety capability

For spending and UTXO sweep operations, the status response must advertise the capability expected by the Wallet version. Consult the versioned API reference for the exact response schema. A server that omits a required safety capability may be treated as incompatible or read-only.

## Compatibility warning

Matching route names is not sufficient. Response schemas, UTXO fields, transaction semantics, network parameters, fee units and broadcast behavior must match the Wallet's expectations. Verify the pair of versions before using a funded wallet.
