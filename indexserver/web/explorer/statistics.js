/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {num,esc,heading,panel,stat,loading} from './ui.js';
import {t,isEnglish} from './i18n.js';

export async function statistics({root,api}){
  root.innerHTML=heading('NETWORK STATISTICS',t('高级网络统计'))+
    '<div id="supply" class="stat-grid">'+stat(t('UTXO 总数量'),'—',t('读取中'))+stat(t('UTXO 总金额'),'—',t('读取中'))+stat(t('历史地址总数'),'—',t('读取中'))+stat(t('当前非零余额地址'),'—',t('读取中'))+'</div>'+
    panel(t('地址余额分布 · Address Balance Distribution'),t('按当前非零余额地址统计各余额区间'),'<div id="distribution">'+loading+'</div>')+
    panel(t('供应量 · Coin Supply'),t('根据 nextBTC 区块补贴及减半规则计算'),'<div id="issuance">'+loading+'</div>')+
    '<p class="caption" id="stats-source"></p>';
  const data=await api('/statistics');
  const coin=s=>num(Number(s)/1e8)+' NBTC';
  root.querySelector('#supply').innerHTML=
    stat(t('UTXO 总数量'),num(data.utxo_count),t('已确认链 · 不含 OP_RETURN'),'blue')+
    stat(t('UTXO 总金额'),coin(data.utxo_total_sats),t('当前未花费输出总额'),'mint')+
    stat(t('历史地址总数'),num(data.historical_address_count),t('曾出现在索引交易活动中的地址'),'amber')+
    stat(t('当前非零余额地址'),num(data.nonzero_balance_addresses),t('当前确认余额大于零'),'pink');
  const labels=[['0 < balance < 1','bucket_0'],['1 ≤ balance < 10','bucket_1'],['10 ≤ balance < 100','bucket_2'],['100 ≤ balance < 1,000','bucket_3'],['1,000 ≤ balance < 10,000','bucket_4'],['balance ≥ 10,000','bucket_5']];
  const max=Math.max(1,...labels.map(x=>Number(data[x[1]]||0)));
  root.querySelector('#distribution').innerHTML='<div class="table-wrap"><table class="data-table"><thead><tr><th>'+t('余额区间 / NBTC')+'</th><th>'+t('地址数量 / Addresses')+'</th><th>'+t('占比 / Share')+'</th></tr></thead><tbody>'+labels.map(([label,key])=>{const n=Number(data[key]||0),share=data.nonzero_balance_addresses?n/data.nonzero_balance_addresses*100:0;return '<tr><td>'+esc(label)+'</td><td>'+num(n)+'</td><td><div class="distribution-bar"><span style="width:'+Math.max(0,Math.min(100,n/max*100))+'%"></span></div>'+num(share,2)+'%</td></tr>'}).join('')+'</tbody></table></div>';
  const x=data.issuance||{};
  if(!x.available){root.querySelector('#issuance').innerHTML='<p class="notice warn">'+esc(x.reason||t('发行量数据暂不可用'))+'</p>';}
  else{
    const pct=Math.max(0,Math.min(100,Number(x.issued_percent||0)));
    const reward=coin(x.next_block_subsidy_sats);
    const nextHalving=num(x.next_halving_height);
    root.querySelector('#issuance').innerHTML=
      '<div class="stat-grid">'+
      stat(t('理论最大供应量'),coin(x.nominal_max_supply_sats),t('名义上限；精确发行计划受 satoshi 整数截断影响'),'blue')+
      stat(t('累计已发行'),coin(x.issued_sats),t('按已确认区块高度和减半规则累计'),'mint')+
      stat(t('剩余可发行'),coin(x.remaining_sats),t('精确发行计划上限减去累计发行'),'amber')+
      stat(t('下一块区块补贴'),reward,t('不包含交易手续费'),'pink')+
      '</div><div class="supply-progress"><div class="supply-progress-head"><strong>'+t('发行进度')+'</strong><span>'+num(pct,6)+'%</span></div><div class="distribution-bar"><span style="width:'+pct+'%"></span></div><div class="caption">'+t('剩余发行比例')+'：'+num(100-pct,6)+'%</div></div>'+
      '<div class="table-wrap"><table class="data-table"><tbody>'+[
        [isEnglish()?'Current block subsidy':'当前区块补贴', coin(x.current_block_subsidy_sats)],
        [t('下一次减半高度'), '#'+nextHalving],
        [t('距离下一次减半'), num(x.blocks_until_halving)+' '+t('个区块')],
        [t('初始区块补贴'), coin(x.initial_subsidy_sats)],
        [t('减半间隔'), num(x.halving_interval)+' '+t('个区块')],
        [t('整数截断导致未发行'), coin(x.rounding_unissued_sats)],
        [t('创世区块特殊分配'), coin(x.genesis_allocation_sats)+' · '+t('不可花费，不计入发行量')]
      ].map(r=>'<tr><th>'+esc(r[0])+'</th><td>'+esc(r[1])+'</td></tr>').join('')+'</tbody></table></div>'+
      '<p class="caption">'+esc(t('累计发行量按区块补贴规则计算，不包含手续费；创世区块 50 NBTC 特殊分配不可花费，单独列示。'))+'</p>';
  }
  root.querySelector('#stats-source').textContent=t('统计高度')+' #'+num(data.height)+' · '+(isEnglish()?'Updated ':'更新于 ')+new Date(data.fetched_at*1000).toLocaleString(isEnglish()?'en-US':'zh-CN')+' · '+t('数据源：已确认区块索引 · 不包含 Mempool 未确认输出');
}
