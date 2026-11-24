/* Copyright (c) 2026 btcdage / nextbtc2025
 * Project: nextBTC Index Server
 * Source: https://github.com/nextbtc2025/nextbtc-suite
 * License: MIT (see LICENSE)
 */

import {isEnglish} from './i18n.js';
const PAGE = 25;
const numberFormat = new Intl.NumberFormat(isEnglish()?'en-US':'zh-CN', { maximumFractionDigits: 12, maximumSignificantDigits: 15 });

function el(tag, className, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.append(...children.filter(value => value !== null && value !== undefined));
  return node;
}

function num(value) {
  return value == null ? '—' : numberFormat.format(value);
}

function money(sats) {
  return sats == null ? '未解析' : (Number(sats) / 1e8).toLocaleString('en-US',
    {minimumFractionDigits: 8, maximumFractionDigits: 8}) + ' nextBTC';
}

function ledgerAmount(sats) {
  return money(sats === 0 ? 0 : sats).replace(/ nextBTC$/, '');
}

function movement(sats) {
  const direction = sats > 0 ? 'positive' : sats < 0 ? 'negative' : 'neutral';
  return el('span', 'amount-' + direction, (sats > 0 ? '+' : '') + ledgerAmount(sats));
}

function date(seconds) {
  return seconds == null ? '—' : new Date(seconds * 1000).toLocaleString(isEnglish()?'en-US':'zh-CN', {hour12: false});
}

function pageOf(params, key = 'page') {
  const page = Number(params.get(key) || 1);
  if (!Number.isSafeInteger(page) || page < 1 || (page - 1) * PAGE > 10000000) throw Error('分页参数超出范围');
  return page;
}

function link(view, id, label) {
  const a = el('a', 'detail-link', label ?? String(id));
  a.href = '#/' + view + (id == null || id === '' ? '' : '/' + encodeURIComponent(id));
  if (a.firstChild?.nodeName === 'CODE') a.title = a.textContent;
  return a;
}

function heading(title, subtitle) {
  return el('header', 'details-heading', el('h1', 'page-title', title), subtitle ? el('p', 'mono break-id muted', subtitle) : null);
}

function panel(title, ...children) {
  return el('section', 'panel details-panel', el('h2', 'details-h2', title), ...children);
}

function stats(fields) {
  return el('div', 'stat-grid details-stats', ...fields.map(([name, value]) =>
    el('div', 'stat', el('span', 'muted', name), el('strong', '', value))));
}

function fields(rows) {
  return el('dl', 'detail-fields', ...rows.flatMap(([name, value]) =>
    [el('dt', 'muted', name), el('dd', 'mono break-id', value ?? '—')]));
}

function table(headers, rows, emptyMessage) {
  if (!rows.length) return el('p', 'detail-empty muted', emptyMessage);
  return el('div', 'table-wrap', el('table', 'data-table',
    el('thead', '', el('tr', '', ...headers.map(text => el('th', '', text)))),
    el('tbody', '', ...rows.map(cells => el('tr', '', ...cells.map(value => el('td', '', value)))))));
}

function pager(ctx, key, total) {
  const page = pageOf(ctx.params, key);
  const pages = Math.max(1, Math.ceil(total / PAGE));
  const nav = el('nav', 'pagination detail-pager');
  nav.setAttribute('aria-label', key === 'utxo' ? 'UTXO 分页' : '记录分页');
  for (const [label, target] of [['上一页', Math.min(page - 1, pages)], ['下一页', page + 1]]) {
    if (label === '下一页') nav.append(el('span', 'muted', '第 ' + page + ' / ' + pages + ' 页 · 共 ' + num(total) + ' 条'));
    if (target < 1 || target > pages) nav.append(el('span', 'disabled', label));
    else {
      const params = new URLSearchParams(ctx.params);
      params.set(key, target);
      const a = link(ctx.view, ctx.id, label);
      a.href += '?' + params.toString();
      nav.append(a);
    }
  }
  return nav;
}

const txLink = txid => link('tx', txid, el('code', 'hash-link', txid));
const heightLink = height => link('block', height, '#' + num(height));
const sliceQuery = page => 'limit=' + PAGE + '&offset=' + (page - 1) * PAGE;

async function blocks(ctx) {
  const data = await ctx.api('/blocks?' + sliceQuery(pageOf(ctx.params)));
  return [heading('区块列表'), panel('已索引区块', table(['高度', '区块哈希', '出块时间', '交易数'],
    data.blocks.map(b => [heightLink(b.height), link('block', b.hash, el('code', 'hash-link', b.hash)), date(b.timestamp), num(b.tx_count)]),
    '当前页没有已索引区块。'), pager(ctx, 'page', data.total))];
}

async function transactions(ctx) {
  const page=pageOf(ctx.params);
  const query=new URLSearchParams(sliceQuery(page));
  for(const key of ['block','order'])if(ctx.params.has(key))query.set(key,ctx.params.get(key));
  const data=await ctx.api('/transactions?'+query);
  const form=el('form','page-controls'),height=el('input','form-control'),order=el('select','form-select');
  height.type='number';height.min=0;height.placeholder=isEnglish()?'Block height':'区块高度';height.setAttribute('aria-label',height.placeholder);
  height.value=query.get('block')||'';
  order.setAttribute('aria-label',isEnglish()?'Sort order':'排序');
  for(const [value,cn,en] of [['desc','最新在前','Newest first'],['asc','最早在前','Oldest first']]){
    const option=el('option','',isEnglish()?en:cn);option.value=value;order.append(option);
  }
  order.value=query.get('order')||'desc';
  form.append(height,order,el('button','btn btn-outline-light',isEnglish()?'Apply':'筛选'));
  form.onsubmit=event=>{event.preventDefault();const p=new URLSearchParams({order:order.value});
    if(height.value)p.set('block',height.value);location.hash='/transactions?'+p};

  return [heading('交易列表','已确认普通交易 · 不包含 Coinbase'),
    form,panel('最新交易 · Latest Transactions',
      table(['交易哈希 / Tx Hash','区块高度 / Block','时间 / Timestamp','输入 / Inputs','输出 / Outputs','输出总额 / Total Outputs','手续费 / Fee'],
        data.transactions.map(tx=>[txLink(tx.txid),heightLink(tx.height),date(tx.timestamp),num(tx.input_count),num(tx.output_count),money(tx.total_output_sats),money(tx.fee_sats)]),
        '当前没有已确认的普通交易。'),
      pager(ctx,'page',data.total),
      el('p','caption','共 '+num(data.total)+' 笔普通交易 · 空交易区块不会出现在此列表中；Coinbase 交易单独排除。'))];
}

async function block(ctx) {
  let height = ctx.id;
  const byHash = /^[0-9a-f]{64}$/i.test(height);
  if (byHash) height = (await ctx.api('/block/hash/' + encodeURIComponent(ctx.id))).height;
  else if (!/^\d{1,10}$/.test(height)) throw Error('无效的区块高度或哈希');
  const path = '/block/' + height;
  const [b, txs, neighbors] = await Promise.all([ctx.api(path), ctx.api(path + '/transactions?' + sliceQuery(pageOf(ctx.params))), ctx.api(path + '/neighbors')]);
  if (b.hash !== txs.hash || (byHash && ctx.id.toLowerCase() !== b.hash)) throw Error('查询时主链发生变化，请刷新重试。');
  return [heading('区块 #' + num(b.height), b.hash),
    stats([['网络难度', num(b.difficulty)], ['nBits', b.bits ?? '—'], ['交易数量', num(b.tx_count)], ['区块大小', num(b.size) + ' B']]),
    panel('区块头', fields([['时间', date(b.time)], ['Merkle 根', b.merkleroot], ['Nonce', num(b.nonce)], ['版本', num(b.version)], ['权重', num(b.weight) + ' WU'],
      ['前一区块', neighbors.previous ? heightLink(neighbors.previous.height) : '创世区块'], ['后一区块', neighbors.next ? heightLink(neighbors.next.height) : '当前链尖']])),
    panel('区块交易', table(['序号', '交易哈希'], txs.txids.map((txid, i) => [num(txs.offset + i + 1), txLink(txid)]), '当前页没有交易。'),
      pager(ctx, 'page', txs.total))];
}

function endpoint(item) {
  if (item.address) return link('address', item.address, el('code', 'hash-link', item.address));
  if (item.script) {
    const details = el('details', 'script-data', el('summary', '', '脚本输出'), el('code', 'break-id', item.script));
    return details;
  }
  return el('span', 'muted', '地址未解析');
}

async function transaction(ctx) {
  const data = await ctx.api('/tx/' + encodeURIComponent(ctx.id));
  const tx = data.transaction;
  const coinbase = data.coinbase;
  const confirmed = data.state === 'confirmed';
  const state = confirmed ? '已确认' : data.state === 'mempool' ? '内存池 · 未确认' : '状态待核实';
  const inputPage = pageOf(ctx.params, 'input');
  const outputPage = pageOf(ctx.params, 'output');
  const portion = (rows, page) => rows.slice((page - 1) * PAGE, page * PAGE);
  const inputRows = portion(data.inputs, inputPage).map(i => [
    i.coinbase ? el('span', 'muted', 'Coinbase 发币输入') : endpoint(i),
    i.coinbase ? '—' : money(i.value_sats), i.txid ? link('tx', i.txid, el('code', 'hash-link', i.txid + ':' + i.vout)) : '—']);
  const outputRows = portion(data.outputs, outputPage).map(o => [String(o.vout), endpoint(o), money(o.value_sats)]);
  const blockRef = data.block_height != null ? heightLink(data.block_height) : tx.blockhash ? link('block', tx.blockhash) : '—';
  return [heading('交易详情', tx.txid), stats([['交易状态', state], ['确认数', num(data.confirmations)],
    ['手续费', coinbase ? '不适用' : money(data.fee_sats)], ['手续费率', data.feerate_sat_vb == null ? '—' : num(data.feerate_sat_vb) + ' sat/vB']]),
    panel('交易信息', fields([['所在区块', blockRef], ['区块时间', date(tx.blocktime)], ['虚拟大小', num(data.vsize) + ' vB'],
      ['输入金额', coinbase ? 'Coinbase' : money(data.total_input_sats)], ['输出金额', money(data.total_output_sats)], ['锁定时间', num(tx.locktime)]])),
    ...(data.onchain_memos?.length ? [panel('链上备注 · On-chain Memo', ...data.onchain_memos.map(m=>el('div','memo-card',
      el('p','memo-text',m.text ?? ('Hex: '+m.data_hex)),
      el('p','caption',`输出 #${m.vout} · ${num(m.byte_length)} bytes · ${m.encoding==='utf-8'?'UTF-8':'Binary/Hex'} · ${m.within_80_byte_limit?'≤ 80-byte payload':'over 80-byte payload'}`))))] : []),
    el('div', 'detail-flow',
      panel('资金来源 · ' + num(data.inputs.length) + ' 个输入', table(['地址或脚本', '金额', '引用输出'], inputRows, '没有输入记录。'),
        data.unresolved_inputs ? el('p', 'muted', num(data.unresolved_inputs) + ' 个前序输出尚未解析，暂时无法计算输入总额。') : null,
        data.inputs.length > PAGE || inputPage > 1 ? pager(ctx, 'input', data.inputs.length) : null),
      panel('资金去向 · ' + num(data.outputs.length) + ' 个输出', table(['序号', '地址或脚本', '金额'], outputRows, '没有输出记录。'),
        data.outputs.length > PAGE || outputPage > 1 ? pager(ctx, 'output', data.outputs.length) : null))];
}

function qr(address) {
  if (typeof window.qrcode !== 'function') return el('p', 'muted', '二维码组件未加载。');
  const code = window.qrcode(0, 'M');
  code.addData(address, 'Byte');
  code.make();
  const count = code.getModuleCount(), scale = 5, margin = 4;
  const canvas = el('canvas', 'address-code');
  canvas.width = canvas.height = (count + margin * 2) * scale;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', '地址二维码 ' + address);
  const g = canvas.getContext('2d');
  g.fillStyle = '#fff';
  g.fillRect(0, 0, canvas.width, canvas.height);
  g.fillStyle = '#07111b';
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      if (code.isDark(row, col)) g.fillRect((col + margin) * scale, (row + margin) * scale, scale, scale);
    }
  }
  return canvas;
}

async function address(ctx) {
  const path = '/address/' + encodeURIComponent(ctx.id);
  const [s, h, u] = await Promise.all([ctx.api(path + '/statistics'),
    ctx.api(path + '/history?' + sliceQuery(pageOf(ctx.params))), ctx.api(path + '/utxos?' + sliceQuery(pageOf(ctx.params, 'utxo')))]);
  if (s.tip_hash !== h.tip_hash || s.tip_hash !== u.tip_hash) throw Error('索引在查询期间更新，请刷新重试。');
  return [el('div', 'address-heading', heading('地址详情', s.address), qr(s.address)),
    el('p', 'muted', '已确认账本 · 索引高度 #' + num(s.height)),
    stats([['已确认余额', money(s.balance_sats)], ['收款总额', money(s.total_received_sats)], ['支出总额', money(s.total_spent_sats)], ['历史交易', num(s.transaction_count)]]),
    panel('交易历史', table(['交易哈希', '区块', '时间', '收入 (nextBTC)', '支出 (nextBTC)', '净变化 (nextBTC)', '交易后余额 (nextBTC)'],
      h.transactions.map(t => [txLink(t.txid), heightLink(t.height), date(t.timestamp), movement(t.received_sats), movement(-t.sent_sats), movement(t.net_sats), ledgerAmount(t.balance_after_sats)]), '此页没有已确认交易。'), pager(ctx, 'page', h.total)),
    panel('未花费输出', table(['来源交易', '输出序号', '金额', '确认数', '成熟状态'],
      u.utxos.map(o => [txLink(o.txid), num(o.vout), money(o.value), num(o.confirmations), o.height === 0 ? '创世输出' : o.mature ? '已成熟' : '未成熟']), '此页没有未花费输出。'),
      pager(ctx, 'utxo', u.total))];
}

export async function renderDetail(ctx) {
  const pages = { blocks, transactions, block, tx: transaction, address };
  const content = await pages[ctx.view](ctx);
  if (!ctx.signal?.aborted) ctx.root.replaceChildren(...content);
}
