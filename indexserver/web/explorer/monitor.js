const labels=[
 ['hit_percent','命中率 (%)','Hit rate (%)'],['hits','命中次数','Hits'],['misses','未命中次数','Misses'],
 ['entries','响应缓存条目','Response cache entries'],['updated','缓存最后写入','Last cache write'],
 ['average_ms','平均 API 响应 (ms)','Mean API latency (ms)'],['slow','慢请求 (≥1s)','Slow requests (≥1s)'],
 ['sql_mean_ms','平均 SQLite execute (ms)','Mean SQLite execute (ms)'],['worker','统计任务','Statistics worker'],
 ['worker_seconds','最近统计耗时 (s)','Last statistics duration (s)'],['database_bytes','数据库大小 (B)','Database size (B)'],
 ['uptime','服务运行时间 (s)','Uptime (s)']];
let en=localStorage.getItem('nextbtc-language')==='en',last;
const find=s=>document.querySelector(s);
function render(){
  document.documentElement.lang=en?'en':'zh-CN';
  find('#title').textContent=en?'Performance monitor':'性能监控';
  find('#lang').textContent=en?'中文':'English';
  find('tbody').replaceChildren(...labels.map(([key,zh,english])=>{
    const row=document.createElement('tr'),title=document.createElement('th'),value=document.createElement('td');
    title.textContent=en?english:zh;
    let v=last?.[key];
    if(key==='updated')v=v?new Date(v*1000).toLocaleString(document.documentElement.lang):null;
    if(key==='worker'&&!en)v=({idle:'空闲',running:'计算中',failed:'失败'})[v];
    value.textContent=v??'—';row.append(title,value);return row;
  }));
}
async function poll(){
  try{const r=await fetch('/api/v1/explorer/admin/metrics',{cache:'no-store'});
    if(!r.ok)throw Error('HTTP '+r.status);last=await r.json();find('[role=status]').textContent='';
  }catch(e){find('[role=status]').textContent=(en?'Update failed · ':'更新失败 · ')+e.message}
  render();setTimeout(poll,10000);
}
find('#lang').onclick=()=>{en=!en;localStorage.setItem('nextbtc-language',en?'en':'zh-CN');render()};
render();poll();
