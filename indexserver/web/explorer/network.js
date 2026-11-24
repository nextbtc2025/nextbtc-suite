/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {num,finite,rate,pct,esc,short,date,ref,hashRef,heading,panel,stat,table,loading,section,lineChart} from './ui.js';
import {overviewMap} from './mempool.js';
const refresh='<button type="button" class="btn btn-sm btn-outline-light" data-refresh>↻ 刷新</button>';
let homeMempoolHasTransactions=null;
let homeMempoolManualExpanded=null;
function setHomeMempoolExpanded(root,expanded){
  const content=root.querySelector('#home-pool-content');
  const button=root.querySelector('#home-pool-toggle');
  const panel=root.querySelector('#home-pool-panel');
  if(!content||!button||!panel)return;
  content.hidden=!expanded;
  panel.classList.toggle('is-collapsed',!expanded);
  button.setAttribute('aria-expanded',String(expanded));
  button.textContent=expanded?'收起':'展开';
}
function updateHomeMempoolState(root,sample){
  if(sample?.available===false){setHomeMempoolExpanded(root,homeMempoolManualExpanded??true);return}
  if(sample?.stale){setHomeMempoolExpanded(root,homeMempoolManualExpanded??true);return}
  const hasTransactions=Number(sample?.total??sample?.items?.length??0)>0;
  if(homeMempoolHasTransactions!==null&&homeMempoolHasTransactions!==hasTransactions){
    homeMempoolManualExpanded=null;
  }
  homeMempoolHasTransactions=hasTransactions;
  setHomeMempoolExpanded(root,homeMempoolManualExpanded??hasTransactions);
}
const chartBox=id=>'<div class="chart" id="'+id+'" role="img" aria-label="'+({hash:'网络算力历史',diff:'网络难度历史'}[id])+'">'+loading+'</div>';
function networkChart(el,rows,isHash,signal){
  const key=isHash?'hashrate_hps':'difficulty';
  const points=rows.slice().reverse().map(r=>[r.height,finite(r[key])?Number(r[key]):null]);
  el.replaceChildren();
  lineChart(el,{points,name:isHash?'算力':'难度',color:isHash?'#5caaff':'#f28fbb',format:isHash?rate:n=>num(n,8),yName:isHash?'H/s':'难度'},signal);
}
const rangeControl=count=>'<div class="range" aria-label="历史高度范围">'+[24,72,120].map(n=>'<a href="#/?range='+n+'" '+(count===n?'aria-current="true"':'')+'>'+n+' 块</a>').join('')+'</div>';
export async function home({root,params,api,signal}){
  const count=[24,72,120].includes(Number(params.get('range')))?Number(params.get('range')):72;
  root.innerHTML=heading('NETWORK OVERVIEW','网络仪表盘','<span id="sync" class="status">同步状态待查</span>'+refresh)+
    '<div id="stats" class="stat-grid" aria-live="polite">'+['已索引区块','网络算力','网络难度','未确认交易'].map(s=>stat(s,'—','读取中')).join('')+'</div>'+
    '<div class="section-title"><h2>网络趋势</h2>'+rangeControl(count)+'</div><div class="chart-pair">'+
    panel('Network Hashrate','最近至多 24 个区块的工作量 ÷ 实测窗口时长',chartBox('hash'))+
    panel('Network Difficulty','根据各高度已确认区块的 nBits 计算',chartBox('diff'))+'</div>'+
    '<section class="panel home-mempool is-collapsed" id="home-pool-panel"><div class="panel-head"><div><h2>交易内存池</h2><p>实时查看未确认交易及手续费分布</p></div><div class="panel-actions"><button type="button" class="btn btn-sm btn-outline-light" id="home-pool-toggle" aria-controls="home-pool-content" aria-expanded="false">展开</button><a class="more" href="#/mempool">内存池详情 →</a></div></div><div id="home-pool-content" hidden><div class="map-chart" id="home-map">'+loading+'</div><p class="caption" id="home-map-meta"></p></div></section>'+
    panel('最新区块','按已索引高度降序排列','<div id="recent">'+loading+'</div>','<a class="more" href="#/blocks">全部区块 →</a>');
  const find=s=>root.querySelector(s);
  find('#home-pool-toggle').addEventListener('click',()=>{
    const content=find('#home-pool-content');
    const expanded=!!content?.hidden;
    homeMempoolManualExpanded=expanded;
    setHomeMempoolExpanded(root,expanded);
  });
  const summary=section(find('#stats'),async el=>{
    try{
      const s=await api('/summary');
      const m=s.mempool;
      find('#sync').textContent=s.synced?'索引已同步':'索引同步中';
      find('#sync').classList.toggle('ready',s.synced);
      el.innerHTML=stat('已索引区块',num(s.indexed_height,0),'节点高度 '+(s.core_height>=0?num(s.core_height,0):'未知'),'amber')+
        stat('网络算力',rate(s.network_hashrate),s.hashrate_error?'Core 算力暂不可用':'Core · getnetworkhashps','blue')+
        stat('网络难度',num(s.difficulty,8),s.difficulty_error?'Core 难度暂不可用':'Core · getdifficulty','pink')+
        stat('未确认交易',m?.available?num(m.count,0):'—',m?.available?(m.stale?'快照已过期':'采集于 '+date(m.updated)):'暂无快照','mint');
    }catch(err){find('#sync').textContent='索引状态不可用';throw err}
  });
  const history=api('/difficulty/history?limit='+count);
  await Promise.all([summary,...['hash','diff'].map(id=>section(find('#'+id),async el=>{
    const h=await history;
    networkChart(el,h.items,id==='hash',signal);
  })),section(find('#home-map'),el=>overviewMap(el,find('#home-map-meta'),api,signal,sample=>updateHomeMempoolState(root,sample))),section(find('#recent'),async el=>{
    const b=await api('/blocks?limit=8');
    el.innerHTML=table(['高度','区块哈希','时间','交易数'],b.blocks.map(x=>[ref('block',x.height,'#'+num(x.height,0)),hashRef('block',x.height,x.hash),esc(date(x.timestamp)),num(x.tx_count,0)]),'尚无已索引区块');
  })]);
}
function prediction(p,targetSpacing=150){
  if(!p.available)return '<p class="state">'+esc(p.reason||'预测暂不可用')+'</p>';
  const check=p.core_template_verification||{};
  const verified=check.available&&check.matched===true;
  const verifyText=verified?'已与 Core 模板 nBits 核对':check.available?'预测与 Core 模板不一致 · 模板 '+check.template_nbits:'Core 模板尚未核验 · '+(check.reason||'暂无模板');
  const seconds=v=>finite(v)?num(v)+' 秒':'—';
  const intervals=Number(p.timestamp_intervals||0);
  const averageInterval=intervals>0&&finite(p.actual_timespan)?Number(p.actual_timespan)/intervals:null;
  const targetInterval=finite(targetSpacing)?Number(targetSpacing):null;
  const deviation=averageInterval!==null&&targetInterval>0?(averageInterval/targetInterval-1)*100:null;
  const paceText=deviation===null?'—':Math.abs(deviation)<0.005?'与目标一致':deviation>0?'比目标慢 '+num(deviation,2)+'%':'比目标快 '+num(Math.abs(deviation),2)+'%';
  const paceColor=deviation===null?'blue':deviation>0?'amber':'mint';
  return '<div class="stat-grid">'+stat('候选区块',num(p.candidate_height),'下一调整高度','amber')+
    stat('预计难度',num(p.predicted_difficulty,8),'候选值 · 尚未出块','pink')+stat('预计调整',pct(p.change_percent),'相对当前难度','blue')+
    stat('预计 nBits',p.predicted_nbits,'候选区块目标','mint')+'</div>'+
    '<dl class="readings">'+[['计算阶段',p.phase],['参与计算',num(p.window_blocks)+' 个区块'],['时间间隔数',num(p.timestamp_intervals)],['目标跨度',seconds(p.target_timespan)],['实际跨度',seconds(p.actual_timespan)],['限幅后跨度',seconds(p.clamped_timespan)]].map(([k,v])=>'<div><dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd></div>').join('')+'</dl>'+
    (averageInterval!==null&&targetInterval>0?'<div class="stat-grid pace-grid">'+stat('平均出块间隔',num(averageInterval,2)+' 秒','实际跨度 ÷ 时间间隔数',paceColor)+stat('目标出块间隔',num(targetInterval,2)+' 秒','Core 共识目标时间','blue')+stat('出块速度对比',paceText,'相对目标出块间隔',paceColor)+'</div><p class="caption">24 个区块头之间有 23 个时间间隔；平均出块间隔按实际时间跨度除以时间间隔数计算。</p>':'')+
    '<p class="notice '+(verified?'':'warn')+'">'+esc(verifyText)+'</p>';
}
export async function dwg({root,params,api,signal}){
  const before=params.get('before');
  root.innerHTML=heading('PROOF OF WORK','DWG 难度分析',refresh)+
    panel('下一块难度预测','依据当前链尖及 nextBTC 的工作量证明规则计算','<div id="forecast">'+loading+'</div>')+
    panel('历史网络难度','已确认区块 · 按区块高度','<div id="diff" class="chart">'+loading+'</div>')+
    panel('计算窗口','当前链尖最近 24 个可用区块头','<div id="window">'+loading+'</div>')+
    panel('难度记录','已确认的 nBits 与对应网络难度','<div id="history">'+loading+'</div>');
  const find=s=>root.querySelector(s);
  const history=api('/difficulty/history?limit=72'+(before!==null?'&before='+encodeURIComponent(before):''));
  await Promise.all([section(find('#forecast'),async el=>{const d=await api('/difficulty');
      el.innerHTML='<p class="caption mb-3">已确认链尖 '+ref('block',d.height,'#'+num(d.height,0))+' · 当前难度 '+num(d.current_difficulty,8)+' · DWG 激活高度 #'+num(d.instant_mine_end_height,0)+'</p>'+prediction(d.next_block,d.target_spacing_seconds)}),
    section(find('#window'),async el=>{const w=await api('/difficulty/window');
      el.innerHTML='<details><summary>查看 '+num(w.window.length,0)+' 个区块头 · 链尖 #'+num(w.tip_height,0)+'</summary>'+
      table(['区块','区块时间','nBits','哈希'],w.window.map(r=>[ref('block',r.height,r.height),esc(date(r.time)),esc(r.bits),hashRef('block',r.height,r.hash)]))+'</details>'}),
    section(find('#diff'),async el=>{const h=await history;networkChart(el,h.items,false,signal)}),
    section(find('#history'),async el=>{const h=await history;const rows=h.items;
      el.innerHTML=table(['高度','时间','难度','变化幅度','nBits'],rows.map(r=>[ref('block',r.height,num(r.height,0)),esc(date(r.time)),num(r.difficulty,8),pct(r.difficulty_change_percent),esc(r.bits)]))+
        '<div class="pagination">'+(before!==null?'<a href="#/dwg">返回最新</a>':'')+(h.has_more&&rows.length?'<a href="#/dwg?before='+(rows.at(-1).height-1)+'">更早区块 →</a>':'')+'</div>'})]);
}

