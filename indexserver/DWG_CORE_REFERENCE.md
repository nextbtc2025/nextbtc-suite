# nextBTC Core 的 DWG 和算力计算依据

V1.0.21 使用用户提供的 `src/src.zip` 复核。ZIP 全部条目通过 CRC 检查。归档 SHA256 为 `0bc8dcc90c9470aa075835cb12b5747af8f112b801be5284e4f300c90f5cc2c9`，其中 `src/pow.cpp` 的 SHA256 为 `e60484438dac384ab9f75ffe8bf562950792f19e2d963b5b9e504f3282fba2d6`。下表行号对应归档内文件。

| Core 源码 | Explorer 实现依据 |
| --- | --- |
| `src/chainparams.cpp` 第 68–81、151–163、280–290 行 | main、test、signet 的目标间隔均为 150 秒，powLimit 为 `00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`。用创世哈希 `000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1` 核对网络身份。regtest 具有单独的 PoW 参数。 |
| `src/pow.cpp` 第 22–45 行 | 候选高度小于 55,555 时返回 powLimit 的紧凑编码 `1e0fffff`。候选高度 55,555 起，每块调用 `DarkGravityWave`。 |
| `src/pow.cpp` 第 96–131 行 | 从候选块父块向前取 24 个块。初始平均值为第一个 target。第 i 次平均值为 `floor((prev*(i-1)+target[i])/i)`，每步整数截断。按 Core 顺序累加相邻时间戳的 23 个差值。 |
| `src/pow.cpp` 第 133–150 行 | 目标时长 24 × 150 = 3600 秒。实际跨度限制于 1200 至 10800 秒。平均目标先乘受限时长，再整除目标时长，取结果与 powLimit 的较小者，最后调用 `GetCompact()`。 |
| `src/rpc/blockchain.cpp` 第 93–109 行 | 确认块难度取参考 target（`0x1d00ffff`）与块 nBits 解码所得 target 的比。预计难度也使用最终紧凑编码解码后的 target。 |
| `src/chain.cpp` 第 131–143 行，`src/rpc/mining.cpp` 第 65–108 行 | 每个块的工作量等于 `floor(2^256/(target+1))`。算力等于窗口终点与起点的累计工作量差除以窗口内最大和最小时间戳之差。算力历史每点最多取 24 个区间。若没有可用时间差，接口返回 null。 |

## 可复现的对账

测试 `tests/test_explorer_dwg.py` 保存主链高度 59,976 至 59,999 的真实 nBits 及时间戳。预测高度 60,000 时，24 块窗口的实际跨度为 2172 秒。Core 确认块 `000000000465aeec467a8064104b8531b5fbc7f8adab4ccaa8375e8f2a678d8b` 的 nBits 为 `1c04dac9`。Core 的 `getnetworkhashps 24 60000` 返回 1,672,841,588.351364 H/s。该测试可离线重复。

配置目标节点后运行 `python tools/verify_dwg_core.py --samples 1000`。工具对照真实历史块头，并要求当前候选块与 `getblocktemplate` 的高度、父哈希及 nBits 对应。Explorer 在同一父块上观察到 nBits 不匹配时，会标记预测不可用。历史区块展示已确认值，当前模板以及本地计算结果均属于下一候选块。
