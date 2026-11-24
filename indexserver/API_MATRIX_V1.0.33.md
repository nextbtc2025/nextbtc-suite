# Complete Explorer API Matrix — V1.0.33

All Explorer endpoints are read-only GET routes. Pagination and bounded result limits are enforced by the handlers.

| Method | Endpoint | Handler |
|---|---|---|
| GET | `/api/v1/explorer/admin/metrics` | admin_metrics |
| GET | `/api/v1/explorer/address/<address>` | `explorer_address` |
| GET | `/api/v1/explorer/address/<address>/balance-history` | `explorer_address_balance_history` |
| GET | `/api/v1/explorer/address/<address>/history` | `explorer_address_history` |
| GET | `/api/v1/explorer/address/<address>/statistics` | `explorer_address_statistics` |
| GET | `/api/v1/explorer/address/<address>/utxos` | `explorer_address_utxos` |
| GET | `/api/v1/explorer/block/<int:height>` | `explorer_block` |
| GET | `/api/v1/explorer/block/<int:height>/neighbors` | `explorer_block_neighbors` |
| GET | `/api/v1/explorer/block/<int:height>/statistics` | `explorer_block_statistics` |
| GET | `/api/v1/explorer/block/<int:height>/transactions` | `explorer_block_transactions` |
| GET | `/api/v1/explorer/block/hash/<block_hash>` | `explorer_block_by_hash` |
| GET | `/api/v1/explorer/blocks` | `explorer_blocks` |
| GET | `/api/v1/explorer/capabilities` | `explorer_capabilities` |
| GET | `/api/v1/explorer/difficulty` | `explorer_difficulty` |
| GET | `/api/v1/explorer/difficulty/history` | `explorer_difficulty_history` |
| GET | `/api/v1/explorer/difficulty/window` | `explorer_difficulty_window` |
| GET | `/api/v1/explorer/mempool` | `explorer_mempool` |
| GET | `/api/v1/explorer/mempool/events` | `explorer_mempool_events` |
| GET | `/api/v1/explorer/mempool/fees` | `explorer_mempool_fees` |
| GET | `/api/v1/explorer/mempool/history` | `explorer_mempool_history` |
| GET | `/api/v1/explorer/mempool/map` | `explorer_mempool_map` |
| GET | `/api/v1/explorer/mempool/recent` | `explorer_mempool_recent` |
| GET | `/api/v1/explorer/mempool/summary` | `explorer_mempool_summary` |
| GET | `/api/v1/explorer/mempool/transactions` | `explorer_mempool_transactions` |
| GET | `/api/v1/explorer/mempool/tx/<txid>` | `explorer_mempool_tx` |
| GET | `/api/v1/explorer/mempool/tx/<txid>/dependencies` | `explorer_mempool_dependencies` |
| GET | `/api/v1/explorer/network` | `explorer_network` |
| GET | `/api/v1/explorer/network/blocks` | `explorer_block_stats` |
| GET | `/api/v1/explorer/network/hashrate` | `explorer_hashrate` |
| GET | `/api/v1/explorer/network/transactions` | `explorer_tx_stats` |
| GET | `/api/v1/explorer/search` | `explorer_search` |
| GET | `/api/v1/explorer/statistics` | `explorer_advanced_statistics` |
| GET | `/api/v1/explorer/summary` | `explorer_summary` |
| GET | `/api/v1/explorer/transactions` | `explorer_transactions` |
| GET | `/api/v1/explorer/tx/<txid>` | `explorer_tx` |
| GET | `/api/v1/explorer/tx/<txid>/flow` | `explorer_tx_flow` |
