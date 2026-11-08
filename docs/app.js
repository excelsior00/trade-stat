/* 수출 잠정치 대시보드 — data/metrics.json 을 읽어 렌더링 */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem('ts.' + k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem('ts.' + k, JSON.stringify(v)); } catch { /* 무시 */ } },
  };

  let M = null;
  const S = Object.assign({
    tab: 'tenday', period: 'D10', basis: 'v', cnty: 'TOTAL',
    nCnty: 'TOTAL', nMetric: 'exp', iCnty: 'ALL', item: 'semi', iMetric: 'exp',
  }, store.get('state', {}));
  const charts = {};

  // ── 포맷 ────────────────────────────────────────────────
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const ymLabel = (ym) => `${ym.slice(2, 4)}.${ym.slice(4)}`;
  const ymLong = (ym) => `${ym.slice(0, 4)}년 ${+ym.slice(4)}월`;
  const eok = (v, digits = 1) => v == null ? '–' : (v).toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits });
  const pctTxt = (v) => v == null ? '–' : `${v > 0 ? '▲' : v < 0 ? '▼' : ''}${Math.abs(v).toFixed(1)}%`;
  const pctCls = (v) => v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : '';
  const span = (v) => `<span class="${pctCls(v)}">${pctTxt(v)}</span>`;
  const shift = (ym, n) => { const t = +ym.slice(0, 4) * 12 + (+ym.slice(4) - 1) + n; return `${Math.floor(t / 12)}${String(t % 12 + 1).padStart(2, '0')}`; };
  const cName = (code) => code === 'ALL' ? '전체' : (M.countries.find((c) => c.code === code)?.name || M.nation[code]?.name || code);

  // ── 뷰 모델: 탭마다 같은 형태로 변환 ──────────────────────
  // points: [{ym, val(억달러), yoy, mom, raw}]
  function view() {
    if (S.tab === 'tenday') {
      const pl = M.periodLabel[S.period];
      const toPts = (code) => (M.tenday[code]?.[S.period] || []).map((p) => ({
        ym: p.ym, raw: p,
        val: (S.basis === 'd' ? p.d : p.v) / 1e5,
        yoy: S.basis === 'd' ? p.dyoy : p.yoy,
        mom: S.basis === 'd' ? p.dmom : p.mom,
      }));
      const ents = M.countries.filter((c) => M.tenday[c.code]).map((c) => ({ id: c.code, name: c.name }));
      return {
        title: `${cName(S.cnty)} · ${pl}${S.basis === 'd' ? ' · 일평균' : ''}`,
        unit: S.basis === 'd' ? '억달러/일' : '억달러', periodText: pl,
        ents, cur: S.cnty, pick: (id) => { S.cnty = id; }, pts: toPts(S.cnty), toPts,
      };
    }
    if (S.tab === 'nation') {
      const k = S.nMetric;
      const toPts = (code) => (M.nation[code]?.points || []).map((p) => ({
        ym: p.ym, raw: p, val: p[k] / 1e8, yoy: p[k[0] + 'yoy'], mom: p[k[0] + 'mom'],
      }));
      const lastYm = maxYm(Object.values(M.nation).flatMap((s) => s.points.map((p) => p.ym)));
      const ents = Object.entries(M.nation)
        .map(([id, s]) => ({ id, name: s.name, size: s.points.find((p) => p.ym === lastYm)?.exp || 0 }))
        .sort((a, b) => (b.id === 'TOTAL') - (a.id === 'TOTAL') || b.size - a.size);
      return {
        title: `${M.nation[S.nCnty]?.name || S.nCnty} · ${k === 'exp' ? '수출' : '수입'} (월 확정)`,
        unit: '억달러', periodText: '월', ents, heatEnts: ents.slice(0, 16), cur: S.nCnty,
        pick: (id) => { S.nCnty = id; }, pts: toPts(S.nCnty), toPts,
      };
    }
    if (S.tab === 'items') {
      const k = S.iMetric;
      const toPts = (id) => (M.item[id]?.[S.iCnty] || []).map((p) => ({
        ym: p.ym, raw: p, val: p[k] / 1e8, yoy: p[k[0] + 'yoy'], mom: p[k[0] + 'mom'],
      }));
      const ents = M.items.filter((i) => M.item[i.id]?.[S.iCnty]).map((i) => ({ id: i.id, name: i.name }));
      const nm = M.items.find((i) => i.id === S.item)?.name || S.item;
      return {
        title: `${nm} · ${cName(S.iCnty)} · ${k === 'exp' ? '수출' : '수입'} (월 확정)`,
        unit: '억달러', periodText: '월', ents, cur: S.item,
        pick: (id) => { S.item = id; }, pts: toPts(S.item), toPts,
      };
    }
    return null;
  }
  const maxYm = (arr) => arr.reduce((a, b) => (b > a ? b : a), '');

  // ── 필터 UI ────────────────────────────────────────────
  function seg(label, opts, val, on) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<label>${label}</label>`;
    const g = document.createElement('div'); g.className = 'seg';
    opts.forEach(([v, t]) => {
      const b = document.createElement('button');
      b.textContent = t; b.setAttribute('aria-pressed', v === val);
      b.onclick = () => { on(v); render(); };
      g.appendChild(b);
    });
    wrap.appendChild(g); return wrap;
  }
  function sel(label, opts, val, on) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<label>${label}</label>`;
    const s = document.createElement('select');
    opts.forEach(([v, t]) => { const o = new Option(t, v, false, v === val); s.add(o); });
    s.onchange = () => { on(s.value); render(); };
    wrap.appendChild(s); return wrap;
  }
  function chips(ents, cur, pick) {
    const c = document.createElement('div'); c.className = 'chips';
    ents.forEach((e) => {
      const b = document.createElement('button');
      b.textContent = e.name; b.setAttribute('aria-pressed', e.id === cur);
      b.onclick = () => { pick(e.id); render(); };
      c.appendChild(b);
    });
    return c;
  }

  function renderFilters(v) {
    const f = $('#filters'); f.innerHTML = '';
    if (S.tab === 'tenday') {
      f.append(
        seg('기간', [['D10', '1~10일'], ['D20', '1~20일'], ['M', '월 전체']], S.period, (x) => { S.period = x; }),
        seg('기준', [['v', '금액'], ['d', '일평균']], S.basis, (x) => { S.basis = x; }),
        chips(v.ents, v.cur, v.pick),
      );
    } else if (S.tab === 'nation') {
      f.append(
        seg('구분', [['exp', '수출'], ['imp', '수입']], S.nMetric, (x) => { S.nMetric = x; }),
        sel('국가', v.ents.map((e) => [e.id, e.name]), S.nCnty, (x) => { S.nCnty = x; }),
      );
    } else if (S.tab === 'items') {
      const cs = Object.keys(Object.values(M.item)[0] || {});
      const order = ['ALL', ...M.countries.map((c) => c.code)];
      cs.sort((a, b) => order.indexOf(a) - order.indexOf(b));
      f.append(
        seg('구분', [['exp', '수출'], ['imp', '수입']], S.iMetric, (x) => { S.iMetric = x; }),
        sel('국가', cs.map((c) => [c, cName(c)]), S.iCnty, (x) => { S.iCnty = x; }),
        chips(v.ents, v.cur, v.pick),
      );
    }
  }

  // ── KPI ────────────────────────────────────────────────
  function ytd(pts) {
    const last = pts[pts.length - 1]; if (!last) return null;
    const y = last.ym.slice(0, 4), m = last.ym.slice(4);
    const by = Object.fromEntries(pts.map((p) => [p.ym, p.val]));
    let cur = 0, prev = 0;
    for (let i = 1; i <= +m; i++) {
      const mm = String(i).padStart(2, '0');
      const a = by[y + mm], b = by[(+y - 1) + mm];
      if (a == null || b == null) return null;
      cur += a; prev += b;
    }
    return prev > 0 ? { cur, pct: (cur / prev - 1) * 100 } : null;
  }

  function renderKpis(v) {
    const el = $('#kpis');
    const p = v.pts[v.pts.length - 1];
    if (!p) { el.innerHTML = '<div class="kpi empty">데이터 없음</div>'; return; }
    const tile = (k, val, s = '') => `<div class="kpi"><div class="k">${k}</div><div class="v">${val}</div><div class="s">${s}</div></div>`;
    const py = v.pts.find((x) => x.ym === shift(p.ym, -12));
    const pm = v.pts.find((x) => x.ym === shift(p.ym, -1));
    let html = tile(`${ymLong(p.ym)} ${v.periodText === '월' ? '' : v.periodText}`, `${eok(p.val, 1)}<small style="font-size:13px"> ${v.unit}</small>`, v.title);
    html += tile('전년동기대비', span(p.yoy), py ? `전년 ${eok(py.val)} ${v.unit}` : '');
    html += tile('전월동기대비', span(p.mom), pm ? `전월 ${eok(pm.val)} ${v.unit}` : '');
    if (S.tab === 'tenday') {
      const r = p.raw;
      html += S.basis === 'v'
        ? tile('일평균 기준 전년비', span(r.dyoy), `일평균 ${eok(r.d / 1e5, 2)} 억달러`)
        : tile('금액 기준 전년비', span(r.yoy), `금액 ${eok(r.v / 1e5)} 억달러`);
      const pyr = M.tenday[S.cnty][S.period].find((x) => x.ym === shift(p.ym, -12));
      html += r.cy != null
        ? tile('전체 증감 기여도', `<span class="${pctCls(r.cy)}">${r.cy > 0 ? '+' : ''}${r.cy.toFixed(2)}%p</span>`, `조업일수 ${r.wd}일`)
        : tile('조업일수', `${r.wd}일`, pyr ? `전년 ${pyr.wd}일 (${r.wd - pyr.wd >= 0 ? '+' : ''}${(r.wd - pyr.wd).toFixed(1)})` : '');
    } else {
      const r = p.raw;
      html += tile('무역수지', r.bal == null ? '–' : `<span class="${r.bal >= 0 ? 'up' : 'down'}">${eok(r.bal / 1e8)}</span>`, '억달러');
      const y = ytd(v.pts);
      html += tile(`${p.ym.slice(0, 4)}년 누적`, y ? span(y.pct) : '–', y ? `${eok(y.cur, 0)} 억달러` : '');
    }
    el.innerHTML = html;
  }

  // ── 차트 ────────────────────────────────────────────────
  function chart(id) {
    const el = document.getElementById(id);
    if (!charts[id]) charts[id] = echarts.init(el, null, { renderer: 'svg' });
    return charts[id];
  }
  const base = () => ({
    animationDuration: 300,
    textStyle: { fontFamily: getComputedStyle(document.body).fontFamily, color: css('--text-2') },
    grid: { left: 8, right: 12, top: 28, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis', confine: true, backgroundColor: css('--surface'), borderColor: css('--border'),
      textStyle: { color: css('--text'), fontSize: 12 },
    },
  });
  const axisCat = (data) => ({
    type: 'category', data, axisTick: { show: false },
    axisLine: { lineStyle: { color: css('--border') } }, axisLabel: { color: css('--muted'), fontSize: 11, hideOverlap: true },
  });
  const axisVal = (fmt) => ({
    type: 'value', splitLine: { lineStyle: { color: css('--border'), opacity: .6 } },
    axisLabel: { color: css('--muted'), fontSize: 11, formatter: fmt },
  });
  const pctBar = (v) => ({
    value: v, itemStyle: { color: v == null ? 'transparent' : v >= 0 ? css('--up') : css('--down'), borderRadius: v >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] },
  });

  function drawYoyLines(v) {
    const last = v.pts[v.pts.length - 1]; if (!last) return;
    const y0 = +last.ym.slice(0, 4);
    const by = Object.fromEntries(v.pts.map((p) => [p.ym, p]));
    const months = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'));
    const colors = [css('--y1'), css('--y2'), css('--y3')];
    const series = [y0 - 2, y0 - 1, y0].map((y, i) => ({
      name: `${y}년`, type: 'line', smooth: false, symbolSize: 7, connectNulls: false,
      lineStyle: { width: i === 2 ? 3 : 2 }, color: colors[i],
      data: months.map((m) => by[`${y}${m}`]?.val ?? null),
      endLabel: { show: i === 2, formatter: `${y}`, color: css('--text-2'), fontSize: 11 },
    }));
    $('#t-yoyLines').textContent = `최근 3년 추이 · ${v.title} (${v.unit})`;
    chart('c-yoyLines').setOption({
      ...base(), legend: { top: 0, right: 0, textStyle: { color: css('--text-2') }, itemWidth: 14 },
      tooltip: {
        ...base().tooltip, formatter: (ps) => {
          const m = +months[ps[0].dataIndex];
          return `<b>${m}월 ${v.periodText === '월' ? '' : v.periodText}</b><br>` + ps.map((p) => {
            const pt = by[`${p.seriesName.slice(0, 4)}${months[p.dataIndex]}`];
            return `${p.marker}${p.seriesName} ${eok(p.value)} ${pt ? '· 전년비 ' + pctTxt(pt.yoy) : ''}`;
          }).join('<br>');
        },
      },
      xAxis: axisCat(months.map((m) => `${+m}월`)), yAxis: { ...axisVal((x) => eok(x, 0)), scale: true }, series,
    }, true);
  }

  function drawPctBars(id, pts, key, n) {
    const sl = pts.slice(-n);
    chart(id).setOption({
      ...base(),
      tooltip: {
        ...base().tooltip, formatter: (ps) => {
          const p = sl[ps[0].dataIndex];
          return `<b>${ymLong(p.ym)}</b><br>${key === 'yoy' ? '전년동기대비' : '전월동기대비'} ${pctTxt(p[key])}<br>금액 ${eok(p.val)}`;
        },
      },
      xAxis: axisCat(sl.map((p) => ymLabel(p.ym))),
      yAxis: axisVal((x) => `${x}%`),
      series: [{
        type: 'bar', barMaxWidth: 22, data: sl.map((p) => pctBar(p[key])),
        label: { show: n <= 12, position: 'top', fontSize: 10, color: css('--text-2'), formatter: (p) => p.value == null ? '' : `${p.value > 0 ? '+' : ''}${p.value.toFixed(1)}` },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: css('--muted'), type: 'solid', width: 1 }, label: { show: false } },
      }],
    }, true);
  }

  function drawLast12(v) {
    const sl = v.pts.slice(-12);
    $('#t-last12').textContent = `최근 12개월 금액 · ${v.title} (${v.unit})`;
    chart('c-last12').setOption({
      ...base(),
      tooltip: { ...base().tooltip, formatter: (ps) => { const p = sl[ps[0].dataIndex]; return `<b>${ymLong(p.ym)}</b><br>${eok(p.val)} ${v.unit}<br>전월비 ${pctTxt(p.mom)} · 전년비 ${pctTxt(p.yoy)}`; } },
      xAxis: axisCat(sl.map((p) => ymLabel(p.ym))), yAxis: axisVal((x) => eok(x, 0)),
      series: [{
        type: 'bar', barMaxWidth: 28, data: sl.map((p, i) => ({ value: p.val, itemStyle: { color: i === sl.length - 1 ? css('--accent') : css('--bar'), borderRadius: [4, 4, 0, 0] } })),
        label: { show: true, position: 'top', fontSize: 10, color: css('--text-2'), formatter: (p) => p.dataIndex === sl.length - 1 || p.dataIndex === 0 ? eok(p.value) : '' },
      }],
    }, true);
  }

  function drawHeat(rows, months, onPick, label = '전년동기대비') {
    const data = [];
    rows.forEach((r, yi) => months.forEach((ym, xi) => {
      const p = r.pts.find((x) => x.ym === ym);
      data.push([xi, yi, p?.val ?? null]);
    }));
    const h = Math.max(260, rows.length * 26 + 70);
    document.getElementById('c-heat').style.height = `${h}px`;
    const c = chart('c-heat'); c.resize();
    c.setOption({
      ...base(), grid: { left: 8, right: 8, top: 8, bottom: 48, containLabel: true },
      tooltip: { trigger: 'item', confine: true, backgroundColor: css('--surface'), borderColor: css('--border'), textStyle: { color: css('--text'), fontSize: 12 },
        formatter: (p) => `<b>${rows[p.value[1]].name}</b> · ${ymLong(months[p.value[0]])}<br>${label} ${pctTxt(p.value[2])}` },
      xAxis: { ...axisCat(months.map(ymLabel)), position: 'top', splitArea: { show: false } },
      yAxis: { type: 'category', data: rows.map((r) => r.name), inverse: true, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: css('--text-2'), fontSize: 12 } },
      visualMap: {
        type: 'continuous', min: -30, max: 30, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 160, itemWidth: 10,
        text: ['+30%', '-30%'], textStyle: { color: css('--muted'), fontSize: 11 },
        inRange: { color: [css('--down'), css('--mid'), css('--up')] }, outOfRange: { color: css('--mid') },
      },
      series: [{
        type: 'heatmap', data: data.map((d) => ({ value: d, itemStyle: d[2] == null ? { color: 'transparent' } : {} })),
        itemStyle: { borderColor: css('--surface'), borderWidth: 2, borderRadius: 3 },
        label: { show: window.innerWidth > 760, fontSize: 10, color: css('--text'), formatter: (p) => p.value[2] == null ? '' : p.value[2].toFixed(0) },
      }],
    }, true);
    c.off('click');
    if (onPick) c.on('click', (p) => { onPick(rows[p.value[1]].id); render(); });
  }

  function renderTable(head, rows, sortCol = null) {
    const t = $('#tbl');
    t.innerHTML = `<thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>`;
  }

  function setCards(show) {
    ['c-yoyLines', 'c-yoyBars', 'c-momBars', 'c-last12'].forEach((id) => {
      document.getElementById(id).closest('.card').hidden = !show;
    });
    $('#kpis').hidden = !show;
  }

  // ── 렌더 ────────────────────────────────────────────────
  function render() {
    store.set('state', S);
    document.querySelectorAll('.tabs button').forEach((b) => b.setAttribute('aria-selected', b.dataset.tab === S.tab));
    if (location.hash !== '#' + S.tab) history.replaceState(null, '', '#' + S.tab);

    if (S.tab === 'prov') return renderProv();
    setCards(true);
    const v = view();
    if (!v.pts.length && v.ents.length) { v.pick(v.ents[0].id); return render(); }
    renderFilters(v); renderKpis(v); drawYoyLines(v);
    drawPctBars('c-yoyBars', v.pts, 'yoy', 36);
    drawPctBars('c-momBars', v.pts, 'mom', 12);
    drawLast12(v);

    const ents = v.heatEnts || v.ents;
    const last = v.pts[v.pts.length - 1]?.ym;
    const months = last ? Array.from({ length: 12 }, (_, i) => shift(last, i - 11)) : [];
    const heatRows = ents.map((e) => ({ id: e.id, name: e.name, pts: v.toPts(e.id).map((p) => ({ ym: p.ym, val: p.yoy })) }));
    $('#t-heat').textContent = `한눈에 보기 · 전년동기대비 (%) · ${S.tab === 'tenday' ? M.periodLabel[S.period] + (S.basis === 'd' ? ' 일평균' : '') : S.tab === 'items' ? cName(S.iCnty) : '상위 국가'}`;
    drawHeat(heatRows, months, v.pick);

    // 요약 표: 최신 월 기준 항목별
    $('#t-table').textContent = last ? `요약 · ${ymLong(last)} ${S.tab === 'tenday' ? M.periodLabel[S.period] : ''}` : '요약';
    const rows = ents.map((e) => {
      const pts = v.toPts(e.id); const p = pts.find((x) => x.ym === last);
      if (!p) return null;
      const r = [e.name, eok(p.val), span(p.yoy), span(p.mom)];
      if (S.tab === 'tenday') r.push(p.raw.cy == null ? '–' : `${p.raw.cy > 0 ? '+' : ''}${p.raw.cy.toFixed(2)}%p`, span(S.basis === 'd' ? p.raw.yoy : p.raw.dyoy));
      else { const y = ytd(pts); r.push(y ? span(y.pct) : '–'); }
      return r;
    }).filter(Boolean);
    renderTable(S.tab === 'tenday'
      ? ['국가', `금액(${v.unit})`, '전년동기비', '전월동기비', '전체 기여도', S.basis === 'd' ? '금액 전년비' : '일평균 전년비']
      : [S.tab === 'items' ? '품목' : '국가', `금액(${v.unit})`, '전년동월비', '전월비', '연간 누적 전년비'], rows);
  }

  function renderProv() {
    setCards(false);
    $('#filters').innerHTML = '<p class="hint">10일 잠정치(월 전체)와 이후 확정된 국가별 월 실적의 차이 — 잠정치가 얼마나 믿을 만한지 확인</p>';
    const pf = M.provFinal;
    if (!pf.length) {
      $('#t-heat').textContent = '잠정 vs 확정'; chart('c-heat').clear();
      renderTable(['안내'], [['아직 비교할 확정치가 없습니다']]); return;
    }
    const months = [...new Set(pf.map((x) => x.ym))].sort().slice(-12);
    const codes = M.countries.map((c) => c.code).filter((c) => pf.some((x) => x.cnty === c));
    const rows = codes.map((c) => ({ id: c, name: cName(c), pts: pf.filter((x) => x.cnty === c).map((x) => ({ ym: x.ym, val: x.diff })) }));
    $('#t-heat').textContent = '확정치 − 잠정치 차이 (%)';
    drawHeat(rows, months, null, '확정 대비 잠정 차이');
    $('#t-table').textContent = '최근 월 상세';
    const lm = months[months.length - 1];
    renderTable(['국가', '잠정(억달러)', '확정(억달러)', '차이'], pf.filter((x) => x.ym === lm).map((x) => [cName(x.cnty), eok(x.prov / 1e8), eok(x.final / 1e8), `${x.diff > 0 ? '+' : ''}${x.diff.toFixed(2)}%`]));
  }

  // ── 초기화 ──────────────────────────────────────────────
  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  }
  applyTheme(store.get('theme', null));
  $('#themeBtn').onclick = () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    const t = dark ? 'light' : 'dark'; applyTheme(t); store.set('theme', t);
    Object.values(charts).forEach((c) => c.dispose()); Object.keys(charts).forEach((k) => delete charts[k]);
    render();
  };
  document.querySelectorAll('.tabs button').forEach((b) => { b.onclick = () => { S.tab = b.dataset.tab; render(); }; });
  window.addEventListener('resize', () => Object.values(charts).forEach((c) => c.resize()));
  const h = location.hash.slice(1); if (['tenday', 'nation', 'items', 'prov'].includes(h)) S.tab = h;

  fetch('data/metrics.json', { cache: 'no-cache' }).then((r) => r.json()).then((d) => {
    M = d;
    if (!M.tenday[S.cnty]) S.cnty = 'TOTAL';
    if (!M.nation[S.nCnty]) S.nCnty = 'TOTAL';
    const lt = M.latest;
    $('#updated').textContent = `최신 잠정치 ${lt ? ymLong(lt.ym) + ' ' + M.periodLabel[lt.period] : '-'} · 갱신 ${M.generated.replace('T', ' ')}`;
    if (lt && !store.get('state', null)) S.period = lt.period;
    render();
  }).catch((e) => { $('main').innerHTML = `<div class="empty">데이터를 불러오지 못했습니다 (${e.message})</div>`; });
})();
