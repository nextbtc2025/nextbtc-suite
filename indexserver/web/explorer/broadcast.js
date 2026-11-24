/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {heading,panel} from './ui.js';

export async function broadcast({root,api}){
  const config=await api('/capabilities');
  const wallet=new URL(location.origin);
  wallet.port=String(config.wallet_port);
  wallet.pathname='/api/v1/broadcast';
  const endpoint=config.wallet_broadcast_path ? new URL(config.wallet_broadcast_path,location.origin) : wallet;
  if(!['https:','http:'].includes(endpoint.protocol) || endpoint.username || endpoint.password ||
      endpoint.hash || endpoint.search || (location.protocol==='https:' && endpoint.protocol!=='https:'))
    throw Error('请检查 Wallet 广播地址及 HTTPS 配置。');
  root.innerHTML=heading('WALLET','广播交易')+panel('提交已签名交易','在自己的钱包中核对收款地址和手续费，离线签名后将原始交易粘贴到下方。',
    '<form id="broadcast-form"><label for="raw-tx">已签名交易（十六进制）</label><textarea id="raw-tx" class="form-control mono my-2" rows="5" maxlength="200000" autocomplete="off" spellcheck="false" required></textarea><p class="caption" id="broadcast-meta"></p><label><input type="checkbox" required> 我已核对交易，确认向 nextBTC 网络广播</label><div class="mt-3"><button class="btn btn-outline-light" disabled>广播交易</button></div><p role="status" aria-live="polite" class="mt-3 break-id"></p></form>');
  const form=root.querySelector('form'), raw=form.querySelector('textarea'), confirm=form.querySelector('input');
  const button=form.querySelector('button'), status=form.querySelector('[role=status]');
  let sending=false;
  function update(){
    const hex=raw.value.trim();
    const valid=hex.length>=20 && hex.length<=200000 && hex.length%2===0 && /^[0-9a-f]+$/i.test(hex);
    raw.setCustomValidity(hex&&!valid?'请输入完整、偶数长度的十六进制交易。':'');
    form.querySelector('#broadcast-meta').textContent=valid?'交易数据格式有效 · '+hex.length/2+' 字节':hex?'交易数据格式无效，请检查十六进制内容':'请粘贴已签名的原始交易数据';
    button.disabled=sending||!valid||!confirm.checked;
  }
  raw.oninput=()=>{confirm.checked=false;status.textContent='';update()};
  confirm.onchange=update;
  form.onsubmit=async event=>{
    event.preventDefault();
    if(button.disabled||sending||!form.reportValidity())return;
    sending=true;raw.readOnly=true;confirm.disabled=true;update();
    status.textContent='正在提交到节点…';
    try{
      const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',redirect:'error',body:JSON.stringify({hex:raw.value.trim()})});
      const data=await response.json();
      if(!response.ok){status.textContent='提交失败 · HTTP '+response.status+' · '+(data.error||'节点未接受请求');return}
      if(!/^[0-9a-f]{64}$/i.test(data.txid))throw Error();
      raw.value='';
      const link=document.createElement('a');link.href='#/tx/'+data.txid;link.textContent=data.txid;
      status.replaceChildren('节点已接受，查看交易 ',link);
    }catch{status.textContent='未取得有效回执。请先按钱包中的交易哈希查询状态，并检查 Wallet 地址及跨域配置。'}
    finally{sending=false;raw.readOnly=false;confirm.disabled=false;confirm.checked=false;update()}
  };
  update();
}
