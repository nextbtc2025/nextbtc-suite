# nextBTC Suite

**面向 nextBTC 生态的开源钱包与区块链基础设施项目。**

nextBTC Suite 在同一个仓库中维护两个可独立部署的组件：

- **nextBTC Wallet**：自包含的非托管浏览器轻钱包。
- **nextBTC Index Server**：自托管区块链索引服务、Wallet API 和双语区块浏览器。

两个组件分别维护独立版本号。

- 钱包版本：见 [`wallet/VERSION`](wallet/VERSION)
- Index Server 版本：见 [`indexserver/VERSION`](indexserver/VERSION)
- 作者：**btcdage**
- 作者主页：[btcdage2011.github.io](https://btcdage2011.github.io) / [btcdage.rf.gd](https://btcdage.rf.gd)
- GitHub：[nextbtc2025/nextbtc-suite](https://github.com/nextbtc2025/nextbtc-suite)
- 开源协议：[MIT](LICENSE)

## 项目组成

### nextBTC Wallet

位于 `wallet/` 目录，是一个单文件浏览器钱包，可使用现代浏览器直接打开。

- 非托管密钥管理与本地交易签名。
- 本地加密多账户保险库及密码保护的钱包备份。
- 创建钱包、导入私钥和观察钱包。
- 支持当前 nextBTC 网络配置的 Legacy、Nested SegWit、Native SegWit 地址类型。
- 基于 UTXO 的余额查询、交易构建、手续费选择和找零计算。
- 交易预览与确认。
- 默认使用本地交易备注。
- 用户主动选择后，可通过 OP_RETURN 将备注写入链上。链上数据公开且不可撤回，并可能增加交易手续费。
- 二维码扫描及交易数据导出。

钱包需要兼容的 Index Server 提供链状态、UTXO、手续费建议、交易历史和交易广播服务。

### nextBTC Index Server

位于 `indexserver/` 目录，是配合已同步的 nextBTC Core 全节点使用的 Python 服务。

- 将已确认区块、交易、输出、地址活动和 UTXO 状态索引到 SQLite。
- Wallet API 与 Explorer 网页/API 分别监听，服务路由相互隔离。
- 展示网络概览、区块、交易、地址和 Mempool 信息。
- 提供算力、难度曲线、DWG 难度信息和高级网络统计。
- 读取支持的 OP_RETURN 链上数据，并在交易详情中展示。
- Explorer 支持简体中文和英文。
- 提供数据库备份、审计、迁移、验收测试及 Windows 打包工具。

部署、配置、端口和 API 说明请阅读 [`indexserver/README.md`](indexserver/README.md)。

## 系统架构

```text
                         nextBTC Core
                    RPC（默认 127.0.0.1:8554）
                              |
                     Indexer / Mempool
                              |
                         共享 SQLite
                       /              \
                      /                \
             Wallet API 服务       Explorer 服务
             127.0.0.1:8777          127.0.0.1:8778
               钱包接口              网页及 Explorer API
                    ^
                    |
              nextBTC 浏览器钱包
```

Wallet API 和 Explorer 使用独立的监听配置及路由边界，同时共享索引器、Mempool 跟踪器和数据库。默认监听地址仅供本机访问。以上是本地默认端口，不代表 FRP 映射后的公网端口。不要将 Core RPC 端口暴露到公网。

## 快速开始

### Wallet

1. 使用现代浏览器打开 `wallet/nextBTC_Wallet.html`。
2. 创建钱包或导入已有私钥。
3. 存入资金前务必完成钱包备份。
4. 在钱包设置中填写自己部署或信任的 Index Server 地址。
5. 转账前确认网络及地址格式正确。

### Index Server

请按照 [`indexserver/README.md`](indexserver/README.md) 部署。简要来说，需要 Python 3.11、项目运行依赖，以及一个已运行并启用 RPC 的 nextBTC Core 全节点。使用 `indexserver/config.example.ini` 作为配置参考。真实凭据应保存在本地私有 `config.ini` 中，禁止提交到公开仓库。

默认本地端口：

| 服务 | 默认监听地址 | 用途 |
|---|---|---|
| Wallet API | `127.0.0.1:8777` | 钱包接口 |
| Explorer | `127.0.0.1:8778` | 区块浏览器网页及 API |
| Core RPC | `127.0.0.1:8554` | 本机节点 RPC，不应暴露公网 |

通过反向代理或 FRP 部署时，公网域名和端口可以不同。请按实际部署配置服务地址、CORS 和访问控制，不要假定公网端口一定是 8777 或 8778。

## 文档

- [系统架构](docs/architecture.md)
- [Wallet / Index Server API 兼容说明](docs/index-server-api.md)
- [Index Server 部署与运维](indexserver/README.md)
- [Index Server API 参考](indexserver/API_REFERENCE_V1.0.33.md)
- [Index Server API 矩阵](indexserver/API_MATRIX_V1.0.33.md)
- [Index Server 数据库迁移说明](indexserver/MIGRATION_V1.0.33.md)
- [Index Server 更新记录](indexserver/CHANGELOG_V1.0.33.md)

## 安全与隐私

- 私钥在浏览器本地用于地址派生和交易签名。钱包向配置的 Index Server 提交已签名交易数据用于广播。不要向 Index Server 提交 WIF、私钥或助记词。
- Index Server 能够观察查询地址、请求时间及提交广播的已签名交易。请使用自己运营或信任的服务器。
- 钱包数据和本地备注保存在当前浏览器配置及设备中，不会自动同步到其他设备。请单独保管加密备份。
- OP_RETURN 链上数据公开且通常不可撤回，不要写入秘密或个人隐私。
- Core RPC 应保持私有。不要提交 `config.ini`、RPC 凭据、私钥、生产数据库、日志或备份。
- 对公网提供服务时，应正确配置反向代理、TLS、必要的身份验证、限流和 CORS。
- 本项目不宣称已经通过独立专业安全审计。请先使用小额资金测试，并在签名前独立核对交易信息。

漏洞报告方式见 [`SECURITY.md`](SECURITY.md)。

## 参与贡献

欢迎提交 Issue 和 Pull Request。提交前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。不要在 Issue 或 Pull Request 中上传秘密信息、钱包数据或生产数据库。

## 第三方组件

第三方许可和署名信息见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。仓库的 MIT 许可证不会替代或覆盖所包含第三方组件各自的许可证。

## 免责声明

本软件用于 nextBTC 钱包、区块链索引、API 和浏览器展示，不是托管服务，也不保证外部节点配置、网络连接或第三方基础设施始终可用。涉及共识及资产的重要信息，请结合 nextBTC Core 和可信节点数据核验。
