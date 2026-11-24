/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

const STORAGE_KEY = 'nextbtc-language';
let language = 'zh-CN';
try { language = localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'zh-CN'; } catch {}

const translations = {
  '共 ':'Total ','输入 / Inputs':'Inputs','输出 / Outputs':'Outputs','手续费 / Fee':'Fee',
  '按当前非零余额地址统计各余额区间':'Addresses with a positive balance, grouped by balance range', '根据 nextBTC 区块补贴及减半规则计算':'Calculated from the nextBTC block subsidy and halving schedule', '交易':'Transactions', 'Statistics snapshot pending':'Statistics snapshot pending',
  '跳到主要内容':'Skip to main content','nextBTC Explorer 首页':'nextBTC Explorer home','浏览器导航':'Explorer navigation',
  '网络概览':'Network Overview','DWG 分析':'DWG Analysis','区块':'Blocks','广播交易':'Broadcast Transaction',
  '搜索区块高度、哈希或地址':'Search block height, hash, or address','搜索高度、哈希或地址':'Search height, hash, or address','搜索':'Search',
  '数据来源 · nextBTC Core / Index Server':'Data source · nextBTC Core / Index Server','开源代码':'Open-source code','请启用 JavaScript 以查看区块链数据。':'Please enable JavaScript to view blockchain data.',
  '每 30 秒刷新':'Refresh every 30 seconds','服务器未返回 JSON':'Server did not return JSON','此页面不存在。请使用顶部导航。':'Page not found. Use the top navigation.',
  '正在查询…':'Searching…','无法识别搜索结果':'Search result could not be identified','搜索失败':'Search failed',
  '快照':'Snapshot','已过期':'stale','采集不完整':'incomplete collection','快照缺少可用交易大小':'Snapshot does not contain usable transaction sizes',
  '本次快照未采集到交易':'No transactions were collected in this snapshot','展示':'Showing','笔':'transactions','实际打包由矿工决定。':'Actual block selection is determined by miners.',
  '无':'None','快照中未观察到':'Not observed in snapshot','TRANSACTION POOL':'TRANSACTION POOL','刷新快照':'Refresh snapshot',
  '未确认交易图':'Unconfirmed Transaction Map','方块面积按 vsize 分配，颜色对应单笔费率。点击交易可查看依赖。':'Rectangle area represents vsize; color represents individual fee rate. Select a transaction to inspect its dependencies.',
  '手续费分布':'Fee Rate Distribution','按未确认交易的单笔手续费率分组':'Unconfirmed transactions grouped by individual fee rate',
  '交易与依赖':'Transactions & Dependencies','选择一笔交易，查看其父交易、子交易及可替换性信息。':'Select a transaction to view its parents, children, and replaceability information.',
  '内存池历史':'Mempool History','最近 24 小时的内存池交易数量变化':'Mempool transaction-count changes over the last 24 hours',
  '交易事件':'Transaction Events','展示交易进入、确认和移出内存池的记录；替换标记为系统根据冲突输入识别的疑似 RBF。':'Records of transactions entering, confirming, and leaving the mempool. Replacement labels indicate possible RBF inferred from conflicting inputs.',
  '信号未知':'Signal unknown','支持替换':'Replaceable','未发出替换信号':'No replaceability signal','直接父交易':'Direct parents','观察到的直接子交易':'Observed direct children',
  '依赖快照':'Dependency snapshot','节点交易数未核验':'Node transaction count not verified','与节点数量一致':'Matches node count','与当前节点交易数有差异':'Differs from current node transaction count',
  '已采集交易':'Indexed transactions','快照节点总数':'Snapshot node count','节点内存池大小':'Node mempool size','采集总虚拟大小':'Total indexed virtual size','已采集交易之和':'Sum of indexed transactions','采集总手续费':'Total indexed fees',
  '快照中没有可检查的交易':'No transactions available to inspect in this snapshot','选择交易':'Select transaction','采集交易数':'Collected transaction count','本地时间':'Local time',
  '观察时间':'Observed at','事件':'Event','交易哈希':'Transaction hash','替换交易':'Replacement transaction','新增':'Added','已确认':'Confirmed','移除 · 原因未知':'Removed · reason unknown','已移除':'Removed','疑似 RBF 替换':'Possible RBF replacement',
  '曾确认 · 当前索引未收录':'Previously confirmed · not present in current index','最近 24 小时尚无已记录事件':'No recorded events in the last 24 hours','上一页':'Previous','下一页':'Next',
  'WALLET':'WALLET','提交已签名交易':'Submit a Signed Transaction','在自己的钱包中核对收款地址和手续费，离线签名后将原始交易粘贴到下方。':'Verify the recipient address and fee in your wallet, sign offline, then paste the raw transaction below.',
  '已签名交易（十六进制）':'Signed transaction (hex)','我已核对交易，确认向 nextBTC 网络广播':'I have verified the transaction and confirm broadcasting it to the nextBTC network',
  '请输入完整、偶数长度的十六进制交易。':'Enter a complete hexadecimal transaction with an even number of characters.','交易数据格式有效':'Transaction data is valid',
  '字节':'bytes','交易数据格式无效，请检查十六进制内容':'Invalid transaction data. Check the hexadecimal string','请粘贴已签名的原始交易数据':'Paste the signed raw transaction data',
  '正在提交到节点…':'Submitting to the node…','提交失败':'Submission failed','节点未接受请求':'The node did not accept the request','节点已接受，查看交易':'Accepted by node. View transaction',
  '未取得有效回执。请先按钱包中的交易哈希查询状态，并检查 Wallet 地址及跨域配置。':'No valid acknowledgement was received. Check the transaction status using its wallet transaction hash, and verify the Wallet endpoint and cross-origin settings.',
  '请检查 Wallet 广播地址及 HTTPS 配置。':'Check the Wallet broadcast endpoint and HTTPS configuration.',
  '刷新':'Refresh','收起':'Collapse','展开':'Expand','历史高度范围':'Historical block range','块':'blocks','网络算力历史':'Network hashrate history','网络难度历史':'Network difficulty history',
  '同步状态待查':'Sync status pending','已索引区块':'Indexed blocks','网络算力':'Network hashrate','网络难度':'Network difficulty','未确认交易':'Unconfirmed transactions','读取中':'Loading',
  '网络趋势':'Network trends','最近至多 24 个区块的工作量 ÷ 实测窗口时长':'Work accumulated across up to 24 blocks ÷ observed time window',
  '根据各高度已确认区块的 nBits 计算':'Calculated from confirmed block nBits at each height','交易内存池':'Transaction Mempool','实时查看未确认交易及手续费分布':'Live view of unconfirmed transactions and fee distribution',
  '内存池详情':'Mempool details','最新区块':'Latest blocks','按已索引高度降序排列':'Sorted by indexed height, newest first','全部区块':'All blocks','高度':'Height','区块哈希':'Block hash','时间':'Time','交易数':'Transactions',
  '尚无已索引区块':'No indexed blocks yet','索引已同步':'Index synchronized','索引同步中':'Index syncing','节点高度':'Node height','未知':'Unknown','Core 算力暂不可用':'Core hashrate unavailable','Core 难度暂不可用':'Core difficulty unavailable',
  'Core · getnetworkhashps':'Core · getnetworkhashps','Core · getdifficulty':'Core · getdifficulty','快照已过期':'Snapshot is stale','采集于':'Collected at','暂无快照':'No snapshot available','索引状态不可用':'Index status unavailable',
  '预测暂不可用':'Prediction unavailable','已与 Core 模板 nBits 核对':'Verified against Core template nBits','预测与 Core 模板不一致':'Prediction does not match Core template','模板':'Template',
  'Core 模板尚未核验':'Core template not yet verified','暂无模板':'No template available','候选区块':'Candidate block','下一调整高度':'Next adjustment height','预计难度':'Predicted difficulty','候选值 · 尚未出块':'Candidate value · block not yet mined',
  '预计调整':'Predicted adjustment','相对当前难度':'Relative to current difficulty','预计 nBits':'Predicted nBits','候选区块目标':'Candidate block target',
  '计算阶段':'Calculation phase','参与计算':'Blocks used','时间间隔数':'Timestamp intervals','目标跨度':'Target timespan','实际跨度':'Actual timespan','限幅后跨度':'Clamped timespan',
  '秒':'s','依据当前链尖及 nextBTC 的工作量证明规则计算':'Calculated from the current chain tip and nextBTC proof-of-work rules','历史网络难度':'Historical network difficulty',
  '已确认区块 · 按区块高度':'Confirmed blocks · by block height','计算窗口':'Calculation window','当前链尖最近 24 个可用区块头':'Latest 24 available block headers at the current chain tip',
  '难度记录':'Difficulty records','已确认的 nBits 与对应网络难度':'Confirmed nBits and corresponding network difficulty','已确认链尖':'Confirmed chain tip','当前难度':'Current difficulty','DWG 激活高度':'DWG activation height',
  '查看':'View','个区块头':'block headers','区块时间':'Block time','nBits':'nBits','哈希':'Hash','变化幅度':'Change','返回最新':'Back to latest','更早区块':'Earlier blocks',
  '可用历史样本不足':'Not enough historical samples','无法加载本地图表组件':'Unable to load the local chart component','区块 #':'Block #','算力':'Hashrate','难度':'Difficulty',
  '区块列表':'Block list','区块详情':'Block details','地址详情':'Address details','交易详情':'Transaction details','页面':'Page','数据暂不可用':'Data unavailable',
  '暂无记录':'No records','正在读取数据…':'Loading data…','分页参数超出范围':'Pagination parameter is out of range','UTXO 分页':'UTXO pagination','记录分页':'Record pagination',
  '第 ':'Page ',' / ':' / ',' 页 · 共 ':' · ',' 条':' records','当前页没有已索引区块。':'No indexed blocks on this page.','无效的区块高度或哈希':'Invalid block height or hash',
  '查询时主链发生变化，请刷新重试。':'The active chain changed during the query. Refresh and try again.','交易数量':'Transaction count','区块大小':'Block size','区块头':'Block header',
  'Merkle 根':'Merkle root','Nonce':'Nonce','版本':'Version','权重':'Weight','前一区块':'Previous block','后一区块':'Next block','创世区块':'Genesis block','当前链尖':'Current chain tip',
  '区块交易':'Block transactions','序号':'Index','交易哈希':'Transaction hash','当前页没有交易。':'No transactions on this page.','脚本输出':'Script output','地址未解析':'Address not resolved',
  '交易状态':'Transaction status','内存池 · 未确认':'Mempool · unconfirmed','状态待核实':'Status unverified','确认数':'Confirmations','手续费':'Fee','手续费率':'Fee rate','不适用':'N/A','所在区块':'Included in block',
  '区块时间':'Block time','虚拟大小':'Virtual size','输入金额':'Input amount','输出金额':'Output amount','锁定时间':'Lock time','资金来源 · ':'Inputs · ',' 个输入':' inputs','资金去向 · ':'Outputs · ',' 个输出':' outputs',
  '地址或脚本':'Address or script','金额':'Amount','引用输出':'Referenced output','没有输入记录。':'No input records.','没有输出记录。':'No output records.','个前序输出尚未解析，暂时无法计算输入总额。':' previous outputs are unresolved; the total input amount cannot yet be calculated.',
  'Coinbase 发币输入':'Coinbase input','地址二维码 ':'Address QR code ','二维码组件未加载。':'QR code component did not load.','已确认账本 · 索引高度 #':'Confirmed ledger · indexed height #',
  '已确认余额':'Confirmed balance','收款总额':'Total received','支出总额':'Total spent','历史交易':'Historical transactions','交易历史':'Transaction history','收入 (nextBTC)':'Received (nextBTC)',
  '支出 (nextBTC)':'Spent (nextBTC)','净变化 (nextBTC)':'Net change (nextBTC)','交易后余额 (nextBTC)':'Balance after transaction (nextBTC)','此页没有已确认交易。':'No confirmed transactions on this page.',
  '未花费输出':'Unspent outputs','来源交易':'Source transaction','输出序号':'Output index','成熟状态':'Maturity status','创世输出':'Genesis output','已成熟':'Mature','未成熟':'Immature',
  '索引在查询期间更新，请刷新重试。':'The index updated during the query. Refresh and try again.','可替换性信息':'replaceability information',
  'UTXO 总数量':'Total UTXOs','UTXO 总金额':'Total UTXO Value','历史地址总数':'Historical Addresses','当前非零余额地址':'Addresses with Balance','已确认链 · 不含 OP_RETURN':'Confirmed chain · excludes OP_RETURN','当前未花费输出总额':'Total value of unspent outputs','曾出现在索引交易活动中的地址':'Addresses seen in indexed transaction activity','当前确认余额大于零':'Currently has a positive confirmed balance','余额区间 / NBTC':'Balance Range / NBTC','地址数量 / Addresses':'Address Count','占比 / Share':'Share','供应量 · Coin Supply':'Coin Supply','理论最大供应量':'Nominal Maximum Supply','累计已发行':'Cumulative Issued','剩余可发行':'Remaining Scheduled Supply','下一块区块补贴':'Next Block Subsidy','名义上限；精确发行计划受 satoshi 整数截断影响':'Nominal cap; exact schedule is affected by integer-satoshi truncation','按已确认区块高度和减半规则累计':'Accumulated from confirmed height and halving rules','精确发行计划上限减去累计发行':'Exact scheduled maximum minus cumulative issuance','不包含交易手续费':'Excludes transaction fees','发行进度':'Issuance Progress','剩余发行比例':'Remaining Supply Percentage','下一次减半高度':'Next Halving Height','距离下一次减半':'Blocks Until Halving','初始区块补贴':'Initial Block Subsidy','减半间隔':'Halving Interval','整数截断导致未发行':'Unissued Due to Integer Rounding','创世区块特殊分配':'Special Genesis Allocation','不可花费，不计入发行量':'Unspendable; excluded from issuance','累计发行量按区块补贴规则计算，不包含手续费；创世区块 50 NBTC 特殊分配不可花费，单独列示。':'Cumulative issuance follows the block subsidy schedule and excludes fees. The unspendable 50 NBTC genesis allocation is shown separately.','统计高度':'Statistics at height','数据源：已确认区块索引 · 不包含 Mempool 未确认输出':'Source: confirmed block index · excludes unconfirmed Mempool outputs','个区块':'blocks','发行量数据暂不可用':'Issuance data is temporarily unavailable',
};

let replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
const originalText = new WeakMap();
const translatedText = new WeakMap();
const originalAttrs = new WeakMap();
const translatedAttrs = new WeakMap();

export function getLanguage(){ return language; }
export function isEnglish(){ return language === 'en'; }
export function t(value){
  const input=String(value ?? '');
  if(language!=='en')return input;
  let output=input;
  for(const [zh,en] of replacements) if(output.includes(zh)) output=output.split(zh).join(en);
  return output;
}
export function setLanguage(next){
  language=next==='en'?'en':'zh-CN';
  try{localStorage.setItem(STORAGE_KEY,language==='en'?'en':'zh')}catch{}
  if(typeof document!=='undefined')document.documentElement.lang=language;
  updateLanguageButton();
}
export function updateLanguageButton(){
  if(typeof document==='undefined')return;
  const button=document.querySelector('#language-toggle');
  if(button){const label=language==='en'?'中文':'EN';if(button.textContent!==label)button.textContent=label;button.setAttribute('aria-label',language==='en'?'Switch language to Chinese':'切换语言为英文');button.title=button.getAttribute('aria-label');}
}
function translateNode(node){
  if(node.parentElement?.closest('.memo-text'))return;
  const current=node.nodeValue;
  const prior=translatedText.get(node);
  if(prior!==undefined && current!==prior) originalText.set(node,current);
  if(!originalText.has(node)) originalText.set(node,current);
  const next=t(originalText.get(node));
  if(next!==current){translatedText.set(node,next);node.nodeValue=next;} else translatedText.set(node,current);
}
function translateAttribute(el,name){
  const key=el.tagName+'|'+name;
  let store=originalAttrs.get(el); if(!store){store=new Map();originalAttrs.set(el,store);}
  let outputs=translatedAttrs.get(el); if(!outputs){outputs=new Map();translatedAttrs.set(el,outputs);}
  const current=el.getAttribute(name); if(current===null)return;
  if(outputs.has(name)&&current!==outputs.get(name))store.set(name,current);
  if(!store.has(name))store.set(name,current);
  const next=t(store.get(name));
  if(next!==current){el.setAttribute(name,next);outputs.set(name,next);}else outputs.set(name,current);
}
export function applyTranslations(root=document.body){
  if(!root)return;
  if(root.nodeType===Node.TEXT_NODE){translateNode(root);return}
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[]; while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes)translateNode(node);
  const elements=root.nodeType===Node.ELEMENT_NODE?[root,...root.querySelectorAll('*')]:[...root.querySelectorAll('*')];
  for(const el of elements){for(const attr of ['aria-label','aria-controls','placeholder','title','alt'])translateAttribute(el,attr);}
  if(typeof document!=='undefined')document.documentElement.lang=language;
  updateLanguageButton();
}
let observer;
export function installTranslationObserver(){
  if(observer||!document.body)return;
  observer=new MutationObserver(records=>{
    const roots=[];
    for(const record of records){
      if(record.type==='characterData')translateNode(record.target);
      for(const node of record.addedNodes||[]) if(node.nodeType===Node.ELEMENT_NODE||node.nodeType===Node.TEXT_NODE) roots.push(node);
      if(record.type==='attributes'&&record.target.nodeType===Node.ELEMENT_NODE)translateAttribute(record.target,record.attributeName);
    }
    for(const root of roots)applyTranslations(root);
  });
  observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','aria-controls','placeholder','title','alt']});
}

// Additional product terminology and DWG interval explanation.
Object.assign(translations, {
  '平均出块间隔':'Average block interval',
  '目标出块间隔':'Target block interval',
  '出块速度对比':'Block interval vs. target',
  '实际跨度 ÷ 时间间隔数':'Observed timespan ÷ timestamp intervals',
  'Core 共识目标时间':'Core consensus target interval',
  '与目标一致':'On target',
  '比目标慢 ':'slower than target by ',
  '比目标快 ':'faster than target by ',
  '24 个区块头之间有 23 个时间间隔；平均出块间隔按实际时间跨度除以时间间隔数计算。':'A 24-header window contains 23 timestamp intervals. Average block interval is calculated as the observed timespan divided by the number of intervals.',
  '平均出块间隔按实际时间跨度除以时间间隔数计算。':'Average block interval is calculated as the observed timespan divided by the number of intervals.',
  '目标时间跨度':'Target timespan',
  '实际时间跨度':'Observed timespan',
  '限幅后参与计算的时间跨度':'Clamped timespan used in calculation',
  '区块时间间隔数':'Timestamp intervals',
  '历史高度范围':'Historical height range',
  '每 30 秒刷新':'Refresh every 30 seconds',
  '查看交易':'View transaction',
  '本地时间':'Local time',
  '状态待核实':'Status unverified',
  '当前页没有已索引区块。':'No indexed blocks on this page.',
  '当前页没有交易。':'No transactions on this page.',
  '此页没有已确认交易。':'No confirmed transactions on this page.',
  '此页没有未花费输出。':'No unspent outputs on this page.',
  '无效的区块高度或哈希':'Invalid block height or hash',
  '已确认链尖':'Confirmed chain tip',
  '计算阶段':'Calculation phase',
  '参与计算':'Blocks used',
  '限幅后跨度':'Clamped timespan',
  '实际跨度':'Observed timespan',
  '目标跨度':'Target timespan',
  '个区块':' blocks',
  '个输入':' inputs',
  '个输出':' outputs',
  '个前序输出尚未解析，暂时无法计算输入总额。':' previous outputs are unresolved; the total input amount cannot yet be calculated.',
  '未解析':'Unresolved',
  '无效':'Invalid',
  '已成熟':'Mature',
  '未成熟':'Immature',
  '当前链尖':'Current chain tip',
  '索引高度':'Indexed height',
  '候选区块目标':'Candidate block target',
  '交易资金流向':'Transaction flow',
  '资金来源':'Inputs',
  '资金去向':'Outputs',
  '记录分页':'Record pagination',
  'UTXO 分页':'UTXO pagination',
  '第 ':'Page ',
  ' 页 · 共 ':' · ',
  ' 条':' records',
  '广播交易':'Broadcast transaction',
  '数据暂不可用 · ':'Data unavailable · ',
  'HTTP ':'HTTP ',
  '服务器未返回 JSON':'Server did not return JSON',
  '节点未接受请求':'The node did not accept the request',
  '正在提交到节点…':'Submitting to the node…',
  '未取得有效回执。':'No valid acknowledgement was received.',
  '快照节点总数 ':'Snapshot node count ',
  '已采集交易之和':'Sum of indexed transactions',
  '布局仅反映快照，实际打包由矿工决定。':'The layout reflects the snapshot only; actual block selection is determined by miners.',
  '实际打包由矿工决定。':'Actual block selection is determined by miners.',
  '展示 ':'Showing ',
  ' / ':' / ',
  ' 笔':' transactions',
  ' 个样本':' samples',
  '观察到的直接子交易':'Observed direct children',
  '快照中没有可检查的交易':'No transactions available to inspect in this snapshot',
  '采集交易数':'Collected transaction count',
  '已确认 · 当前索引未收录':'Confirmed · not present in current index',
  '曾确认 · 当前索引未收录':'Previously confirmed · not present in current index',
  '最近 24 小时尚无已记录事件':'No recorded events in the last 24 hours',
  '已索引区块':'Indexed blocks',
  '交易数量':'Transaction count',
  '区块大小':'Block size',
  '权重':'Weight',
  '前一区块':'Previous block',
  '后一区块':'Next block',
  '创世区块':'Genesis block',
  '地址未解析':'Address not resolved',
  '脚本输出':'Script output',
  '二维码组件未加载。':'QR code component did not load.',
  '索引在查询期间更新，请刷新重试。':'The index updated during the query. Refresh and try again.',
  '查询时主链发生变化，请刷新重试。':'The active chain changed during the query. Refresh and try again.',
  '当前页没有已索引区块。':'No indexed blocks on this page.',
  '当前页没有交易。':'No transactions on this page.',
  '没有输入记录。':'No input records.',
  '没有输出记录。':'No output records.',
  '此页没有已确认交易。':'No confirmed transactions on this page.',
  '此页没有未花费输出。':'No unspent outputs on this page.',
  '交易状态':'Transaction status',
  '手续费率':'Fee rate',
  '所在区块':'Included in block',
  '锁定时间':'Lock time',
  '输入金额':'Input amount',
  '输出金额':'Output amount',
  '收款总额':'Total received',
  '支出总额':'Total spent',
  '净变化 (nextBTC)':'Net change (nextBTC)',
  '交易后余额 (nextBTC)':'Balance after transaction (nextBTC)',
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
Object.assign(translations, {
  '出块时间':'Block time',
  '交易信息':'Transaction information',
  'Coinbase 发币输入':'Coinbase input',
  '地址二维码':'Address QR code',
  '已确认账本':'Confirmed ledger',
  '收入':'Received',
  '支出':'Spent',
  '净变化':'Net change',
  '发币输入':'Coinbase input',
  '下一块难度预测':'Next-block difficulty prediction',
  '算力暂不可用':'Hashrate unavailable',
  '难度暂不可用':'Difficulty unavailable',
  '同步状态待查':'Sync status pending',
  '同步状态不可用':'Sync status unavailable',
  '数据暂不可用':'Data unavailable',
  '无法识别搜索结果':'Search result could not be identified',
  '广播地址':'broadcast endpoint',
  '跨域配置':'cross-origin settings',
  '在自己的钱包中核对收款地址和手续费，离线签名后将原始交易粘贴到下方。':'Verify the recipient address and fee in your wallet, sign offline, then paste the raw transaction below.',
  '展示交易进入、确认和移出内存池的记录；替换标记为系统根据冲突输入识别的疑似 RBF。':'Records of transactions entering, confirming, and leaving the mempool. Replacement labels indicate possible RBF inferred from conflicting inputs.',
  '方块面积按 vsize 分配，颜色对应单笔费率。点击交易可查看依赖。':'Rectangle area represents vsize; color represents individual fee rate. Select a transaction to inspect its dependencies.',
  '选择一笔交易，查看其父交易、子交易及可替换性信息。':'Select a transaction to view its parents, children, and replaceability information.',
  '最近 24 小时的内存池交易数量变化':'Mempool transaction-count changes over the last 24 hours',
  '布局仅反映快照，实际打包由矿工决定。':'The layout reflects the snapshot only; actual block selection is determined by miners.',
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
Object.assign(translations, {
  '内存池':'Mempool',
  '网络':'Network',
  '笔数':'Transaction count',
  '已确认链尖':'Confirmed chain tip',
  '同步状态待查':'Sync status pending',
  '索引同步中':'Index syncing',
  '索引已同步':'Index synchronized',
  '展开':'Expand',
  '收起':'Collapse',
  '刷新':'Refresh',
  '刷新快照':'Refresh snapshot',
  '全部区块':'All blocks',
  '更早区块':'Earlier blocks',
  '返回最新':'Back to latest',
  '页面':'Page',
  '区块详情':'Block details',
  '地址详情':'Address details',
  '交易详情':'Transaction details',
  '网络概览':'Network Overview',
  'DWG 分析':'DWG Analysis',
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
Object.assign(translations, {
  'Mempool 内存池':'Mempool',
  '网络仪表盘':'Network Dashboard',
  'DWG 难度分析':'DWG Difficulty Analysis',
  'TRANSACTION POOL':'TRANSACTION POOL',
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
Object.assign(translations, {
  '切换语言为英文':'Switch language to English',
  '相对目标出块间隔':'Relative to the target block interval',
  ' 个区块头 · 链尖 #':' block headers · chain tip #',
  ' 笔数 · ':' transaction count · ',
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
Object.assign(translations, {
  '高级网络统计':'Advanced Network Statistics','高级统计':'Advanced Statistics',
  'UTXO 总数量':'Total UTXO Count','UTXO 总金额':'Total UTXO Value','历史地址总数':'Historical Address Count',
  '当前非零余额地址':'Current Non-zero Balance Addresses','地址余额分布 · Address Balance Distribution':'Address Balance Distribution',
  '余额区间 / NBTC':'Balance Range / NBTC','地址数量 / Addresses':'Address Count','占比 / Share':'Share',
  '供应量 · Coin Supply':'Coin Supply','暂无法可靠计算已发行量和剩余供应量。':'Issued and remaining supply cannot yet be calculated reliably.',
  '需要验证 nextBTC 的区块补贴规则。':'The nextBTC block subsidy schedule must be verified.',
  '不会使用 UTXO 总额代替累计发行量，也不会将包含矿工手续费的 Coinbase 总额误认为新发行币。':'UTXO value is not used as a substitute for cumulative issuance, and Coinbase totals containing transaction fees are not misrepresented as newly issued coins.',
  '已确认链 · 不含 OP_RETURN':'Confirmed chain · OP_RETURN excluded','当前未花费输出总额':'Total value of current unspent outputs',
  '曾出现在索引交易活动中的地址':'Addresses seen in indexed transaction activity','当前确认余额大于零':'Currently has a positive confirmed balance',
  '统计高度 #':'Statistics at height #','数据源：已确认区块索引 · 不包含 Mempool 未确认输出':'Source: confirmed block index · unconfirmed Mempool outputs excluded',
  '交易列表':'Transactions','已确认普通交易 · 不包含 Coinbase':'Confirmed ordinary transactions · Coinbase excluded',
  '最新交易 · Latest Transactions':'Latest Transactions','交易哈希 / Tx Hash':'Transaction Hash','区块高度 / Block':'Block Height',
  '时间 / Timestamp':'Timestamp','输出数量 / Outputs':'Outputs','输出总额 / Total Outputs':'Total Output Value',
  '当前没有已确认的普通交易。':'No confirmed ordinary transactions found.','笔普通交易 · 空交易区块不会出现在此列表中；Coinbase 交易单独排除。':' ordinary transactions · Empty blocks are omitted; Coinbase transactions are excluded.',
  '链上备注 · On-chain Memo':'On-chain Memo','输出 #':'Output #','bytes · UTF-8':'bytes · UTF-8','Binary/Hex':'Binary/Hex','≤ 80-byte standard-size payload':'≤ 80-byte standard-size payload','over 80-byte payload':'over 80-byte payload'
});
replacements = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
