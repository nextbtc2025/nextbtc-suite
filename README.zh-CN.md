# nextBTC Suite

**面向 nextBTC 生态的开源钱包与基础设施项目。**

本仓库将分阶段开源。第一阶段只发布 **nextBTC 非托管浏览器轻钱包**。
Index Server 仍在继续开发，本次**不包含 Index Server 源码**。

- 当前钱包版本：**V0.5.83 USD Special**
- 项目许可证：**MIT**（见 [`LICENSE`](LICENSE)）
- 钱包源码：[`wallet/nextBTC_Wallet_V0.5.83_USD_Special.html`](wallet/nextBTC_Wallet_V0.5.83_USD_Special.html)
- English: [`README.md`](README.md)
- GitHub 仓库：https://github.com/nextbtc2025/nextbtc-suite

## 当前包含的功能

钱包以一个完整、自包含的 HTML 文件交付，不需要 Node.js 构建步骤，
也不依赖外部 JavaScript/CSS CDN。

当前版本主要功能：

- 浏览器端非托管钱包。
- 本地加密多账户保险库，以及独立密码保护的钱包备份。
- 创建钱包、导入私钥、观察钱包。
- 支持配置的 nextBTC 网络地址类型：Legacy（P2PKH）、
  Nested SegWit（P2SH-P2WPKH）、Native SegWit（P2WPKH）。
- 基于 UTXO 的余额查询、交易构建、手续费选择、找零计算、本地签名，
  并通过兼容的 Index Server 广播。
- 交易预览与确认，显示找零输出等重要信息。
- 可选本地交易备注。默认只保存在当前浏览器，不写入交易。
- 用户主动勾选后，可使用 OP_RETURN 将备注写入链上。链上备注公开、
  不可撤回，并会增加交易大小和矿工手续费。
- 二维码扫描、签名交易 HEX 展示、复制/下载及二维码图片导出。
- 可选美元参考估值。只有用户启用隐藏的估值显示时才需要获取行情；
  显示值只是参考估值，不代表可成交价格。

## 快速开始

1. 下载 `wallet/` 目录中的钱包 HTML 文件。
2. 使用现代浏览器打开。
3. 创建钱包或导入已有私钥。存入资金前务必完成备份。
4. 打开钱包的 Index Server 设置，填写你自己部署或信任的兼容 Index Server 地址。
5. 确认网络状态和地址格式正确后，再进行转账。

公开源码将默认 Index Server 设置为保留示例地址：

```text
https://your-index-server.example:8777
```

这是文档占位地址，不是真实可用的服务。请在钱包设置中替换为自己的
Index Server 地址；也可以修改主应用脚本中的 `INDEX_SERVER_DEFAULT`
常量。

远程部署建议使用 HTTPS。HTTP 仅建议用于可信的本地网络。浏览器对证书的
处理方式取决于浏览器和服务端证书配置。

## Index Server 依赖

**本次钱包开源不包含 Index Server 源码。**

钱包需要一个独立部署、且 API 与当前钱包版本兼容的 Index Server，
用于查询链状态、地址及 UTXO、手续费建议、交易历史和广播交易。

当前钱包调用以下 API：

| 方法 | 路由 | 用途 |
|---|---|---|
| GET | `/api/v1/status` | 网络与索引状态、安全能力声明 |
| POST | `/api/v1/addresses/query` | 地址和 UTXO 数据 |
| GET | `/api/v1/fees` | 手续费建议 |
| GET | `/api/v1/history/{address}` | 地址交易历史 |
| GET | `/api/v1/tx/{txid}` | 交易状态 |
| POST | `/api/v1/broadcast` | 广播已签名原始交易 HEX |

发送交易时，状态响应必须声明
`capabilities.mempool_spend_guard: true`。如果服务端没有提供该安全能力，
钱包可能会出于安全考虑限制发送。仅路由名称相同并不代表完全兼容，
请求/响应字段和链参数也必须匹配。

## 网络兼容性

本钱包针对 **nextBTC 网络**及其兼容 Index Server API 配置。
不要假设它可以直接用于 Bitcoin 主网或其他 Bitcoin 派生网络。
在其他链上使用前，必须独立核实地址前缀、网络参数、共识规则和服务端行为。

## 安全说明

- 私钥在浏览器本地处理，用于地址派生和交易签名。钱包向所选 Index
  Server 提交的是已签名交易 HEX 以便广播。不要向 Index Server 或任何人
  提交 WIF/私钥。
- 所选 Index Server 能够观察钱包查询的地址、请求时间，以及提交广播的
  已签名交易。请使用自己运营或信任的服务器。
- 浏览器数据保存在当前浏览器配置和设备中。本地备注和钱包数据不会自动
  同步到另一台电脑。
- OP_RETURN 备注公开且交易确认后无法删除。不要在链上备注中填写密码、
  私钥、个人隐私或其他机密信息。
- 美元估值只是参考，可能过期或无法获取。
- 本版本尚未经过独立专业安全审计。请先用小额资金测试，不要存放无法承受
  损失的资金。确认交易前，应在可信的独立设备或区块浏览器核对地址和交易详情。

## 目录结构

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

Index Server 将在开发和发布审查完成后再加入仓库。

## 许可证

项目采用 MIT License。请同时阅读 [`LICENSE`](LICENSE) 和
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 中的第三方声明。
