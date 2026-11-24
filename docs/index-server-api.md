# Index Server API Compatibility

The Index Server implementation is not included in this repository. The wallet
requires an independently deployed service that matches the API contract of the
wallet version being used.

The V0.5.83 wallet uses the following routes:

| Method | Path | Wallet use |
|---|---|---|
| GET | `/api/v1/status` | Network/index status and spend-safety capability |
| POST | `/api/v1/addresses/query` | Address balances and UTXO data |
| GET | `/api/v1/fees` | Low/medium/high fee suggestions |
| GET | `/api/v1/history/{address}?limit=30&include_flow=1` | Address transaction history |
| GET | `/api/v1/tx/{txid}` | Transaction state after broadcast |
| POST | `/api/v1/broadcast` | Submit signed raw transaction HEX |

## Spend-safety capability

For sending and UTXO sweep operations, the status response must declare:

```json
{
  "capabilities": {
    "mempool_spend_guard": true
  }
}
```

The wallet checks this capability before enabling spending. A server that omits
it may be treated as read-only/incompatible.

## Compatibility warning

Matching route names is not sufficient. The response schemas, UTXO fields,
transaction semantics, network parameters, fee units, and broadcast behavior
must match the wallet's expectations. Do not point a funded wallet at an
unverified server implementation.
