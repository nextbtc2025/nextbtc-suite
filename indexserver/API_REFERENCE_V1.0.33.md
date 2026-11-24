# nextBTC Index Server API Reference — V1.0.33

## Explorer service

Default bind: `127.0.0.1:8778` (configurable in `[explorer]`). All Explorer endpoints are read-only `GET` routes under `/api/v1/explorer/`.

### Transaction list

`GET /api/v1/explorer/transactions?limit=25&offset=0`

Returns confirmed ordinary transactions, one row per transaction. Coinbase transactions are excluded from this default feed. Empty blocks naturally produce no rows. `limit` is restricted to 1–100; `offset` is restricted to 0–10,000,000. Optional `block=<height>` filters to a single block. The bounded response cache is keyed by canonical tip hash and query parameters; the count query has a separate cache.

### Block and transaction details

`GET /api/v1/explorer/block/<height>` caches confirmed block detail by canonical block hash for up to one hour. The indexed hash is checked against Core before populating the cache.

`GET /api/v1/explorer/tx/<txid>` caches confirmed transaction detail by transaction ID and containing block hash for up to one hour. Unconfirmed/mempool details bypass shared caching and return `Cache-Control: no-store`.

Responses expose `X-Explorer-Cache` with `HIT`, `MISS`, or `BYPASS` for diagnostics.

### Advanced network statistics

`GET /api/v1/explorer/statistics`

Returns UTXO totals, historical and non-zero address counts, balance buckets, and scheduled subsidy/halving statistics. The response is persisted in SQLite and keyed by canonical tip hash; a new tip or reorganization produces a new cache key.

### Existing endpoints

See `API_MATRIX_V1.0.33.md` for the complete route inventory. Wallet API routes remain isolated on the Wallet service (default `127.0.0.1:8777`). Core RPC remains a local backend dependency and must not be exposed publicly.


## V1.0.33 operations / 运维

`GET /api/v1/explorer/statistics` reads the last canonical background snapshot. Height, tip_hash and fetched_at identify the sample. HTTP 503 indicates the first snapshot is pending. 高级统计后台使用独立 SQLite WAL 读事务计算，页面可暂时显示较早的主链快照。区块奖励为计划补贴，不含手续费。

`GET /api/v1/explorer/transactions?block=123&order=asc&limit=25&offset=0` filters by optional height and sorts by height then transaction hash. Defaults to descending. 交易列表排除 Coinbase，可选择区块高度及升降序。

Set a strong random `[explorer] admin_token` to enable `/explorer/admin` and `/api/v1/explorer/admin/metrics`. Use HTTP Basic username admin and the configured token as password over HTTPS or trusted loopback. 空令牌关闭监控。FRP 对外提供管理功能时请在入口启用 TLS。监控记录 Explorer 公共响应缓存及本服务 API 耗时，慢请求阈值为 1 秒。SQLite 耗时指标记录共享索引连接 execute 阶段。