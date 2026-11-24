/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {applyTranslations,installTranslationObserver,setLanguage,getLanguage,t as tr} from './i18n.js';
import {home,dwg} from './network.js';
import {mempool} from './mempool.js';
import {loading,problem} from './ui.js';
const main=document.querySelector('main');
const form=document.querySelector('#search');
const feedback=document.querySelector('#search-feedback');
let routeController,searchController,pendingRefresh;
let currentPage='',autoEnabled=true,loadingRoute=false;
try{autoEnabled=localStorage.getItem('nextbtc-auto')!=='off'}catch{}
function choosingTransaction(){
  const select=document.activeElement;
  if(select?.id!=='tx-select')return false;
  return CSS.supports('selector(select:open)') && select.matches(':open');
}
function autoPage(){return ['home','mempool'].includes(currentPage)}
function toggleControl(root){
  if(!autoPage())return;
  const label=document.createElement('label');
  label.className='auto-control';
  label.innerHTML='<input type="checkbox" data-auto> '+tr('每 30 秒刷新');
  label.firstChild.checked=autoEnabled;
  root.querySelector('.page-controls')?.prepend(label);
}
async function api(path,signal){
  const response=await fetch('/api/v1/explorer'+path,{signal,cache:'no-store',headers:{Accept:'application/json'}});
  let data;
  try{data=await response.json()}catch{throw Error('HTTP '+response.status+' · 服务器未返回 JSON')}
  if(!response.ok){const err=Error('HTTP '+response.status+' · '+(data.error||response.statusText));err.status=response.status;throw err}
  return data;
}
async function render(refresh=false){
  pendingRefresh?.abort();pendingRefresh=null;
  if(refresh && loadingRoute)return;
  const ctrl=new AbortController();
  if(refresh){pendingRefresh=ctrl}
  else{
  routeController?.abort();searchController?.abort();
  routeController=ctrl;
  }
  const {signal}=ctrl;
  if(!refresh)feedback.hidden=true;
  const [path,query='']=location.hash.slice(1).split('?');
  const [,view='home',encodedId]=path.split('/');
  const page=view||'home';
  currentPage=page;
  document.querySelectorAll('[data-nav]').forEach(a=>{
    if(a.dataset.nav===(page==='block'?'blocks':page))a.setAttribute('aria-current','page');
    else a.removeAttribute('aria-current');
  });
  const names={home:'网络概览',dwg:'DWG 分析',mempool:'Mempool',statistics:'高级统计',broadcast:'广播交易',blocks:'区块列表',transactions:'交易列表',block:'区块详情',address:'地址详情',tx:'交易详情'};
  document.title=tr((names[page]||'页面'))+' · nextBTC Explorer';
  const root=document.createElement('div');
  root.innerHTML=loading;
  const selectedTx=main.querySelector('#tx-select')?.value;
  if(!refresh){main.replaceChildren(root);loadingRoute=true}
  try{
    const context={view:page,id:decodeURIComponent(encodedId||''),params:new URLSearchParams(query),root,api:p=>api(p,signal),signal,selectedTx};
    if(page==='home')await home(context);
    else if(page==='broadcast'){const {broadcast}=await import('./broadcast.js');await broadcast(context)}
    else if(page==='dwg')await dwg(context);
    else if(page==='mempool')await mempool(context);
    else if(page==='statistics'){const {statistics}=await import('./statistics.js');await statistics(context);}
    else if(['blocks','transactions','block','tx','address'].includes(page)){const {renderDetail}=await import('./details.js');await renderDetail(context)}
    else throw Error('此页面不存在。请使用顶部导航。');
  }catch(err){if(!signal.aborted)root.innerHTML=problem(err)}
  if(signal.aborted)return;
  toggleControl(root);
  applyTranslations(root);
  if(refresh){
    if(document.hidden || selectedTx!==main.querySelector('#tx-select')?.value || choosingTransaction()){
      ctrl.abort();pendingRefresh=null;return;
    }
    const active=document.activeElement;
    const focusTarget=main.contains(active) ? ['data-auto','data-refresh','href','id'].find(a=>active.hasAttribute(a)) : null;
    const y=window.scrollY;
    routeController?.abort();
    routeController=ctrl;
    pendingRefresh=null;
    main.replaceChildren(root);
    if(focusTarget)Array.from(root.querySelectorAll('['+focusTarget+']')).find(el=>el.getAttribute(focusTarget)===active.getAttribute(focusTarget))?.focus({preventScroll:true});
    window.scrollTo(0,y);
  }
  loadingRoute=false;
}
form.addEventListener('submit',async e=>{
  e.preventDefault();
  const q=form.elements.query.value.trim();
  if(!q)return;
  searchController?.abort();
  const ctrl=searchController=new AbortController();
  feedback.hidden=false;feedback.textContent='正在查询…';
  try{
    const data=await api('/search?q='+encodeURIComponent(q),ctrl.signal);
    const id={block:data.height,tx:data.txid,address:data.address}[data.type];
    if(id==null)throw Error('无法识别搜索结果');
    feedback.hidden=true;
    location.hash='/'+data.type+'/'+encodeURIComponent(id);
  }catch(err){if(!ctrl.signal.aborted)feedback.textContent='搜索失败 · '+err.message}
});
form.addEventListener('input',()=>{searchController?.abort();feedback.hidden=true});
document.querySelector('.skip').onclick=e=>{e.preventDefault();main.focus()};
document.querySelector('#language-toggle')?.addEventListener('click',()=>{setLanguage(getLanguage()==='en'?'zh-CN':'en');applyTranslations(document.body);render()});
installTranslationObserver();
applyTranslations(document.body);
main.addEventListener('click',e=>{if(e.target.closest('[data-refresh]'))render(true)});
main.addEventListener('change',e=>{
  if(e.target.hasAttribute('data-auto')){
    autoEnabled=e.target.checked;
    if(!autoEnabled){pendingRefresh?.abort();pendingRefresh=null}
    try{localStorage.setItem('nextbtc-auto',autoEnabled?'on':'off')}catch{}
  }
});
setInterval(()=>{
  if(autoPage()&&autoEnabled&&!loadingRoute&&!pendingRefresh&&!document.hidden&&!choosingTransaction())render(true);
},30000);
window.addEventListener('hashchange',()=>{window.scrollTo(0,0);render()});
render();




