# V1.0.33 migration / 数据库迁移

Back up SQLite using tools/backup_index_db.py and run tools/migrate_index_db.py on the copy. Startup applies the same additive schema. 仅新增部分索引 idx_regular_feed(height,txid)，条件为 vout=0 AND coinbase=0。每笔普通交易一个条目。高级统计使用 explorer_cache 中独立命名的快照。区块、交易和钱包历史保留。升级前停止原 EXE，保留同目录 config.ini 和 index.db。