/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {num,finite,bytes,scaled,esc,short,date,ref,hashRef,heading,panel,stat,table,loading,section,empty,lineChart,canvasChart} from './ui.js';

const bands=[{min:10,color:'#de86a3'},{min:5,color:'#e8b66e'},{min:2,color:'#64c5ac'},{min:1,color:'#508ed0'},{min:0,color:'#466989'}];
const fill = fee=>finite(fee)?bands.find(b=>Number(fee)>=b.min)?.color||'#647084':'#647084';
const timeLabel = sample=>'快照 '+date(sample.updated)+(sample.stale?' · 已过期':'')+(sample.coverage_complete===false?' · 采集不完整':'');
function drawMap(el,rows,onSelect,signal){
  const usable=rows.filter(t=>finite(t.vsize)&&t.vsize>0);
  if(!usable.length){el.innerHTML=empty(rows.length?'快照缺少可用交易大小':'本次快照未采集到交易');return}
  canvasChart(el,signal,chart=>{
  chart.setOption({animation:false,tooltip:{confine:true,renderMode:'richText',backgroundColor:'#182330',textStyle:{color:'#e8eff8'},formatter:item=>{
    const t=item.data.tx;
    return short(t.txid)+'\n'+num(t.vsize)+' vB · '+num(t.feerate_sat_vb,4)+' sat/vB';
  }},series:[{type:'treemap',width:'100%',height:'100%',left:0,top:0,breadcrumb:{show:false},roam:false,nodeClick:false,visibleMin:0,sort:'desc',
    label:{show:true,color:'#0a1320',fontSize:11,overflow:'truncate',formatter:p=>short(p.name)},
    itemStyle:{borderWidth:0,gapWidth:1,borderColor:'#151c25'},
    data:usable.map(tx=>({name:tx.txid,value:Number(tx.vsize),tx,itemStyle:{color:fill(tx.feerate_sat_vb)}}))}]});
  chart.on('click',ev=>{if(ev.data?.tx)onSelect(ev.data.tx)});
  });
}
export async function overviewMap(el,meta,api,signal,onSample){
  let sample;
  try{sample=await api('/mempool/map?limit=2000')}
  catch(error){onSample?.({available:false,error});throw error}
  onSample?.(sample);
  el.replaceChildren();
  drawMap(el,sample.items,tx=>{location.hash='/tx/'+encodeURIComponent(tx.txid)},signal);
  meta.textContent=timeLabel(sample)+' · 展示 '+num(sample.returned)+' / '+num(sample.total)+' 笔 · 实际打包由矿工决定。';
  meta.insertAdjacentHTML('beforebegin','<div class="map-legend">'+bands.map(b=>'<span><i style="background:'+b.color+'"></i>≥ '+b.min+'</span>').join('')+' sat/vB</div>');
}
function depsList(title,items,complete){
  return '<div><h3>'+esc(title)+'</h3>'+(items.length?items.map(x=>hashRef('tx',x,x)).join(' · '):complete?'无':'快照中未观察到')+'</div>';
}
export async function mempool({root,api,signal,params,selectedTx}){
  const rawPage=Number(params.get('events')||1);
  const eventPage=Number.isSafeInteger(rawPage)&&rawPage>0&&rawPage<500000?rawPage:1;
  root.innerHTML=heading('TRANSACTION POOL','Mempool 内存池','<button class="btn btn-sm btn-outline-light" data-refresh>↻ 刷新快照</button>')+
    '<div id="m-stats">'+loading+'</div><div class="pool-pair">'+
    panel('未确认交易图','方块面积按 vsize 分配，颜色对应单笔费率。点击交易可查看依赖。','<div class="map-chart" id="map">'+loading+'</div><div class="map-legend">'+['< 1','1–2','2–5','5–10','≥ 10'].map((s,i)=>'<span><i style="background:'+bands[4-i].color+'"></i>'+esc(s)+'</span>').join('')+' sat/vB</div><p class="caption" id="map-meta"></p>')+
    panel('手续费分布','按未确认交易的单笔手续费率分组','<div id="fees">'+loading+'</div>')+'</div>'+
    panel('交易与依赖','选择一笔交易，查看其父交易、子交易及可替换性信息。','<div id="selection">'+loading+'</div><div id="dependencies"></div>')+
    panel('内存池历史','最近 24 小时的内存池交易数量变化','<div id="pool-history" class="chart">'+loading+'</div><p class="caption" id="sample-count"></p>')+
    panel('交易事件','展示交易进入、确认和移出内存池的记录；替换标记为系统根据冲突输入识别的疑似 RBF。','<div id="events">'+loading+'</div>');
  const find=s=>root.querySelector(s);
  const mapData=api('/mempool/map?limit=2000');
  let selected='';
  function select(tx){
    selected=tx.txid;
    const selectEl=find('#tx-select');
    if(selectEl)selectEl.value=tx.txid;
    const dep=find('#dependencies');
    dep.innerHTML=loading;
    section(dep,async el=>{
      let d;
      try{d=await api('/mempool/tx/'+encodeURIComponent(tx.txid)+'/dependencies')}
      catch(err){if(selected!==tx.txid)return;throw err}
      if(selected!==tx.txid||signal.aborted)return;
      const coverage=(await mapData).coverage_complete;
      const rbf=tx.replaceable==null?'信号未知':tx.replaceable?'支持替换':'未发出替换信号';
      el.innerHTML='<div class="selected-meta">'+ref('tx',tx.txid,tx.txid)+'<p>'+num(tx.vsize)+' vB · '+num(tx.fee_sats)+' sat · '+num(tx.feerate_sat_vb,4)+' sat/vB · RBF '+esc(rbf)+'</p></div>'+
        '<div class="dependency-pair">'+depsList('直接父交易',d.parents,coverage)+depsList('观察到的直接子交易',d.children,coverage)+'</div><p class="caption">依赖快照 '+esc(date(d.updated))+'</p>';
    });
  }
  await Promise.all([section(find('#m-stats'),async el=>{const m=await api('/mempool/summary');
    const alignment=m.current_core_count_matches_snapshot===null?'节点交易数未核验':m.current_core_count_matches_snapshot?'与节点数量一致':'与当前节点交易数有差异';
    el.innerHTML='<div class="stat-grid">'+stat('已采集交易',num(m.indexed_count,0),'快照节点总数 '+num(m.snapshot_core_count),'amber')+
      stat('节点内存池大小',bytes(m.core_bytes),'Core · bytes','blue')+stat('采集总虚拟大小',scaled(m.total_vsize,['vB','kvB','MvB']),'已采集交易之和','pink')+
      stat('采集总手续费',num(m.total_fee_sats,0)+' sat','已采集交易之和','mint')+'</div><p class="notice">'+esc(timeLabel(m))+' · '+alignment+'</p>'}),
    section(find('#map'),async el=>{const m=await mapData;el.replaceChildren();drawMap(el,m.items,select,signal);
      find('#map-meta').textContent=timeLabel(m)+' · 展示 '+num(m.returned)+' / '+num(m.total)+' 笔 · 布局仅反映快照，实际打包由矿工决定。'}),
    section(find('#selection'),async el=>{const m=await mapData;
      if(!m.items.length){el.innerHTML=empty('快照中没有可检查的交易');return}
      el.innerHTML='<label class="selector">选择交易<select class="form-select form-select-sm" id="tx-select">'+m.items.map(t=>'<option value="'+esc(t.txid)+'">'+esc(short(t.txid))+' · '+num(t.vsize)+' vB</option>').join('')+'</select></label>';
      el.querySelector('select').onchange=e=>select(m.items.find(t=>t.txid===e.target.value));
      select(m.items.find(t=>t.txid===selectedTx)||m.items[0]);}),
    section(find('#fees'),async el=>{const f=await api('/mempool/fees');const max=Math.max(1,...f.histogram.map(b=>b.count));
      el.innerHTML='<div class="histogram">'+f.histogram.map(b=>'<div class="bin"><span>'+esc(b.label)+'</span><div class="rail"><i style="width:'+Math.max(0,b.count/max*100)+'%"></i></div><b>'+num(b.count,0)+'</b></div>').join('')+'</div><p class="caption">sat/vB · 笔数 · '+esc(timeLabel(f))+'</p>';}),
    section(find('#pool-history'),async el=>{
      let h=await api('/mempool/history?hours=24&limit=5000');
      if(h.has_more)h=await api('/mempool/history?hours=24&limit=5000&offset='+Math.max(0,h.total-5000));
      el.replaceChildren();lineChart(el,{points:h.series.map(r=>[r.sampled_at*1000,r.tx_count]),name:'采集交易数',color:'#74cdb0',time:true,xName:'本地时间',yName:'笔',format:v=>num(v,0)},signal);
      find('#sample-count').textContent='展示 '+num(h.series.length,0)+' / '+num(h.total,0)+' 个样本';}),
    section(find('#events'),async el=>{const ev=await api('/mempool/events?hours=24&limit=20&offset='+((eventPage-1)*20));
      const labels={added:'新增',confirmed:'已确认',removed_unknown:'移除 · 原因未知',removed:'已移除',replaced:'疑似 RBF 替换'};
      el.innerHTML=table(['观察时间','事件','交易哈希','替换交易'],ev.events.map(e=>[esc(date(e.event_at)),esc(e.event_type==='confirmed'&&e.current_confirmation_height===null?'曾确认 · 当前索引未收录':labels[e.event_type]||e.event_type),hashRef('tx',e.txid,e.txid),e.replacement_txid?hashRef('tx',e.replacement_txid,e.replacement_txid):'—']),'最近 24 小时尚无已记录事件')+
        '<div class="pagination">'+(eventPage>1?'<a href="#/mempool?events='+(eventPage-1)+'">← 上一页</a>':'')+(ev.has_more?'<a href="#/mempool?events='+(eventPage+1)+'">下一页 →</a>':'')+'</div>';})]);
}



