/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {t,isEnglish} from './i18n.js';
export const num = (n, decimals=3) => finite(n) ? Number(n).toLocaleString('en-US',{maximumFractionDigits:decimals}) : '—';
export const finite = n => n !== null && n !== undefined && n !== '' && Number.isFinite(Number(n));
export const pct = n => finite(n) ? (n>0?'+':'')+num(n,5)+'%' : '—';
export const date = n => finite(n) ? new Date(Number(n)*1000).toLocaleString(isEnglish()?'en-US':'zh-CN',{hour12:false}) : '—';
export const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const short = s => s ? String(s).slice(0,12)+'…'+String(s).slice(-8) : '—';
export const ref = (type,id,label=id) => '<a class="mono" href="#/'+type+'/'+encodeURIComponent(id)+'">'+esc(label)+'</a>';
export const hashRef = (type,id,hash) => '<a class="mono identifier" title="'+esc(hash)+'" href="#/'+type+'/'+encodeURIComponent(id)+'">'+esc(hash)+'</a>';
export function scaled(n,units,base=1000){
  if(!finite(n))return '—';
  let value=Number(n),i=0;
  while(Math.abs(value)>=base && i<units.length-1){value/=base;i++}
  return num(value,2)+' '+units[i];
}
export const rate = n => scaled(n,['H/s','kH/s','MH/s','GH/s','TH/s','PH/s','EH/s','ZH/s']);
export const bytes = n => scaled(n,['B','kB','MB','GB']);
export function heading(kicker,title,controls=''){
  return '<div class="page-head"><div><p class="eyebrow">'+esc(kicker)+'</p><h1 class="page-title">'+esc(title)+'</h1></div><div class="page-controls">'+controls+'</div></div>';
}
export function panel(title,subtitle,body,action=''){
  return '<section class="panel"><div class="panel-head"><div><h2>'+esc(title)+'</h2><p>'+esc(subtitle)+'</p></div>'+action+'</div>'+body+'</section>';
}
export function stat(label,value,note,color='blue'){
  return '<div class="stat '+color+'"><span class="stat-label"><i></i>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(note)+'</small></div>';
}
export function table(columns,rows,empty='暂无记录'){
  return '<div class="table-wrap"><table class="data-table"><thead><tr>'+columns.map(x=>'<th scope="col">'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+(rows.length?rows.map(r=>'<tr>'+r.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join(''):'<tr><td colspan="'+columns.length+'" class="muted">'+esc(empty)+'</td></tr>')+'</tbody></table></div>';
}
export const loading = '<p class="state muted" role="status">正在读取数据…</p>';
export const empty = msg => '<p class="state">'+esc(msg)+'</p>';
export const problem = err => '<p class="state error" role="status">数据暂不可用 · '+esc(err.message)+'</p>';
export async function section(el,work){
  try{await work(el)}catch(err){if(err.name!=='AbortError')el.innerHTML=problem(err)}
}
/* A refresh builds the next page off-screen. ECharts needs a measured element. */
export function canvasChart(el,signal,configure){
  let chart;
  function resize(){
    if(signal.aborted || !el.clientWidth || !el.clientHeight)return;
    if(chart){chart.resize();return}
    chart=window.echarts.init(el,null,{renderer:'canvas'});
    configure(chart);
  }
  const observer=new ResizeObserver(resize);
  observer.observe(el);
  signal.addEventListener('abort',()=>{observer.disconnect();chart?.dispose()},{once:true});
  resize();
}
export function lineChart(el,{points,name,color,xName='区块高度',time=false,format=num,yName},signal){
  name=t(name); xName=t(xName); yName=t(yName||'');
  if(!points.some(p=>finite(p[1]))){el.innerHTML=empty(t('可用历史样本不足'));return}
  if(!window.echarts){el.innerHTML=empty(t('无法加载本地图表组件'));return}
  canvasChart(el,signal,chart=>{
  const axisLabel={color:'#9aa8ba',fontSize:10,hideOverlap:true};
  chart.setOption({
    animation:!matchMedia('(prefers-reduced-motion: reduce)').matches,
    textStyle:{fontFamily:'Inter, Segoe UI, sans-serif'},color:[color],
    grid:{top:55,right:20,bottom:50,left:14,containLabel:true},
    legend:{data:[name],top:2,right:10,textStyle:{color:'#b2c0d3'},icon:'roundRect',itemWidth:16,itemHeight:3},
    tooltip:{trigger:'axis',confine:true,renderMode:'richText',backgroundColor:'#192332',textStyle:{color:'#e7eef7'},formatter:items=>{
      const [x,y]=items[0].value;
      return (time?date(x/1000):t('区块 #')+num(x,0))+'\n'+name+'   '+format(y);
    }},
    xAxis:{type:time?'time':'value',scale:true,minInterval:time?undefined:1,name:xName,nameLocation:'middle',nameGap:28,
      nameTextStyle:{color:'#9aa8ba'},splitNumber:4,axisLabel:{...axisLabel,formatter:time?undefined:v=>num(v,0)},axisLine:{show:true,lineStyle:{color:'#354152'}},splitLine:{show:false}},
    yAxis:{type:'value',scale:true,name:yName,nameTextStyle:{color:'#9aa8ba',align:'left'},axisLabel:{...axisLabel,formatter:v=>format(v)},splitNumber:4,splitLine:{lineStyle:{color:'#28313c',type:'dashed'}}},
    series:[{name,type:'line',data:points,showSymbol:points.filter(p=>finite(p[1])).length<=1,symbolSize:6,lineStyle:{width:2},
      areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:color+'70'},{offset:1,color:color+'05'}]}}}]
  });
  });
}

