/* Ladder SDLC alpha — front end. Talks to demo/app/server.py when it is running (live), otherwise answers every
   call from data/snapshot.js, which scripts/build_app_snapshot.py recorded from the same harness (recorded).
   No figure on these screens is typed in: plant values come from the simulator, costs from the evaluation sweep. */
(() => {
'use strict';

const SNAP = window.LADDER_SNAPSHOT || {calls: {}, files: {}, facts: {}};
const F = SNAP.facts || {};
const SCREENS = ['line', 'morning', 'economics', 'architecture', 'workbench'];
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const money = (v, d = 3) => v == null ? '–' : '$' + Number(v).toFixed(d);
const pct = v => Math.round(v * 100) + '%';
const LANE_NAMES = {'flash-low': 'Gemini 3.8 Flash · low effort', 'flash-medium': 'Gemini 3.8 Flash · medium effort',
  'flash-high': 'Gemini 3.8 Flash · high effort', 'pro-high': 'Gemini 3.1 Pro · high effort'};
const CAND = 'demo/out/st20_candidate.il', LEGACY = 'plant_data/ev_pack_eol/st20/legacy.il';
const GOOD = 0.005, BAD = 0.08;

const S = {live: false, mode: 'recorded', spend: 0, log: [], signed: false, proposed: false, program: 'running',
  xray: false, beat: 0, cache: {}, line: {}, screen: null, econBasis: 'now', wbStation: 'ST20'};
try { S.signed = localStorage.getItem('ladder.signed') === '1'; } catch (e) { /* storage blocked */ }

/* ---------------------------------------------------------------- API ---- */
function stable(o) {
  if (Array.isArray(o)) return '[' + o.map(stable).join(',') + ']';
  if (o && typeof o === 'object') return '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + stable(o[k])).join(',') + '}';
  return JSON.stringify(o);
}
async function api(path, args = {}, opts = {}) {
  const key = path + '|' + stable(args), t0 = performance.now();
  let res, source;
  if (S.live) {
    const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(args)});
    res = await r.json();
    if (!r.ok) throw new Error(res.error || r.statusText);
    source = res.replay ? 'replay' : 'live';
  } else {
    res = SNAP.calls[key];
    if (!res) throw new Error('This call is not in the recorded run. Start the local server for live calls: python demo/app/server.py');
    if (res.error) throw new Error(res.error);
    source = res.replay ? 'replay' : 'recorded';
    await sleep(opts.fast ? 120 : 380 + Math.random() * 380);
  }
  if (opts.minMs) { const left = opts.minMs - (performance.now() - t0); if (left > 0) await sleep(left); }
  if (path.startsWith('/api/tool/')) logCall(path.slice(10), args, res, source, performance.now() - t0);
  return res;
}
const tool = (name, args, opts) => api('/api/tool/' + name, args, opts);
function once(key, fn) { return S.cache[key] ??= fn().catch(e => { delete S.cache[key]; throw e; }); }

function logCall(name, args, res, source, ms) {
  const cost = res.model_cost_usd || 0;
  S.spend += cost;
  $('#spend-v').textContent = money(S.spend);
  const call = (res.calls || [])[0];
  S.log.unshift({t: new Date(), name, args, cost, source, ms, lane: call ? `${call.model} · ${call.effort}` : 'deterministic',
    recorded_s: call ? call.latency_s : null});
  renderLog();
}
function renderLog() {
  const el = $('#log');
  $('#log-count').textContent = S.log.length + (S.log.length === 1 ? ' call' : ' calls');
  if (!S.log.length) { el.innerHTML = '<div class="empty">Calls from every screen appear here.</div>'; return; }
  el.innerHTML = S.log.slice(0, 60).map((c, i) => `<div class="log-row ${i === 0 ? 'new' : ''}">
    <div class="lr1"><b>${esc(c.name)}${c.args.task ? ' · ' + esc(c.args.task) : ''} ${esc(c.args.station || '')}</b>
      <span class="badge ${c.source === 'live' ? 'badge-optimal' : c.source === 'replay' ? 'badge-primary' : 'badge-stable'}" style="padding:1px 7px;font-size:9.5px">${c.source}</span></div>
    <div class="lr2">${c.t.toLocaleTimeString([], {hour12: false})} · ${esc(c.lane)} · ${money(c.cost, 4)} · ${Math.round(c.ms)} ms${c.recorded_s ? ` · recorded ${c.recorded_s.toFixed(0)} s` : ''}</div>
  </div>`).join('');
}
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 3600);
}

/* ------------------------------------------------------------- shell ---- */
async function boot() {
  try {
    const r = await fetch('/api/status', {cache: 'no-store'});
    if (r.ok) { const st = await r.json(); S.live = true; S.mode = st.mode; S.proposed = st.signed; if (!st.signed) setSigned(false); }
  } catch (e) { S.live = false; }
  const pill = $('#mode-pill');
  pill.classList.toggle('live', S.live);
  pill.querySelector('span').textContent = S.live ? 'Live · harness on this machine' : 'Recorded run';
  pill.title = S.live
    ? `Simulator, lint and gate run live. Model tasks: LADDER_MODE=${S.mode}${S.mode === 'replay' ? ' (pinned recorded runs, labelled replay)' : ''}.`
    : 'Opened without the local server: every answer is the harness\'s recorded answer to the same call. Run python demo/app/server.py for live.';
  $$('.tab').forEach(t => t.addEventListener('click', () => go(t.dataset.screen)));
  $$('[data-goto]').forEach(b => b.addEventListener('click', () => go(b.dataset.goto)));  // reads data-goto at click time
  $('#spend').addEventListener('click', () => go('workbench'));
  $('#reset-btn').addEventListener('click', resetDemo);
  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#scrim').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', onKey);
  window.addEventListener('hashchange', route);
  initLine(); initMorning(); initEconomics(); initArchitecture(); initWorkbench();
  route();
}
function go(id, beat) { location.hash = id + (beat != null ? '/' + beat : ''); }
function route() {
  const [id, sub] = location.hash.slice(1).split('/');
  const screen = SCREENS.includes(id) ? id : 'line';
  if (screen !== S.screen) {
    S.screen = screen;
    $$('.tab').forEach(t => t.setAttribute('aria-selected', String(t.dataset.screen === screen)));
    $$('.screen-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-' + screen));
    window.scrollTo({top: 0});
    if (screen === 'line') lineStart(); else lineStop();
    if (screen === 'economics') renderRanges();
  }
  if (screen === 'morning') showBeat(sub != null && !isNaN(+sub) ? +sub : S.beat, false);
}
function onKey(e) {
  if (e.target.closest('input,textarea,select')) return;
  if (e.key === 'Escape') return closeDrawer();
  if ($('#drawer').classList.contains('open')) return;
  if (/^[1-5]$/.test(e.key) && !e.metaKey && !e.ctrlKey) return go(SCREENS[+e.key - 1]);
  if (S.screen === 'morning') {
    if (e.key === 'ArrowRight' || (e.key === ' ' && !e.target.closest('button'))) { e.preventDefault(); nextBeat(); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); prevBeat(); }
  }
}
async function resetDemo() {
  if (S.live) { try { await api('/api/reset', {}); } catch (e) { return toast(e.message); } }
  S.cache = {}; S.spend = 0; S.log = []; $('#spend-v').textContent = money(0); renderLog();
  S.proposed = false; setSigned(false); S.program = 'running'; S.line = {}; S.beat = 0;
  lineReload(); if (S.screen === 'morning') showBeat(0, true);
  toast('Demo reset: proposals and outputs removed.');
}
function setSigned(v) {
  S.signed = v;
  try { localStorage.setItem('ladder.signed', v ? '1' : '0'); } catch (e) { /* storage blocked */ }
  const b = $('#prog-signed');
  if (b) { b.disabled = !v; b.title = v ? 'The proposal the engineer signed' : 'Available once an engineer signs a proven change'; }
}

/* drawer */
function openDrawer(eyebrow, title, html, wide) {
  $('#drawer-eyebrow').textContent = eyebrow; $('#drawer-title').textContent = title;
  $('#drawer-body').innerHTML = html;
  $('#drawer').classList.toggle('wide', !!wide);
  $('#drawer').classList.add('open'); $('#drawer').setAttribute('aria-hidden', 'false');
  $('#scrim').classList.add('open');
  $('#drawer-close').focus();
}
function closeDrawer() {
  $('#drawer').classList.remove('open'); $('#drawer').setAttribute('aria-hidden', 'true'); $('#scrim').classList.remove('open');
}
async function showLadderDiff() {
  const res = await once('diff', () => tool('ladder_diff', {station: 'ST20', candidate_path: CAND}));
  openDrawer('ST20 · current vs candidate', 'The changed rung, drawn as ladder', '<iframe id="diff-frame" title="Ladder diff"></iframe>', true);
  const fr = $('#diff-frame'), path = '/' + res.html_path.replace(/^demo\//, '');
  if (S.live) fr.src = path; else fr.srcdoc = SNAP.files[path] || '<p>Not recorded.</p>';
}

/* --------------------------------------------------------- renderers ---- */
function lane(call, extra = '') {
  if (!call) return `<span class="lane zero"><b>Deterministic</b><span class="sep"></span>$0<span class="sep"></span>no model${extra}</span>`;
  const src = S.live ? (call.backend === 'replay' ? 'replayed recording' : 'live call') : 'recorded';
  return `<span class="lane"><b>${esc(call.model)}</b> ${esc(call.effort)} effort<span class="sep"></span>${money(call.cost_usd, 4)}
    <span class="sep"></span>${call.latency_s.toFixed(0)} s when recorded<span class="sep"></span>${src}${extra}</span>`;
}
const zeroLane = what => `<span class="lane zero"><b>${esc(what)}</b><span class="sep"></span>$0<span class="sep"></span>${S.live ? 'ran live, just now' : 'recorded'}</span>`;
const LINT_TITLES = {L001: 'Two rungs drive the same output; the last one wins', L002: 'A timer converted from FX3 now runs ten times longer',
  L003: 'A timer is read before it is updated', L005: 'A wired input is never used', L007: 'SAFETY rung, locked against AI edits'};
const sevBadge = s => ({critical: 'badge-critical', error: 'badge-critical', high: 'badge-warning', warning: 'badge-warning',
  medium: 'badge-primary', info: 'badge-stable', low: 'badge-stable'}[s] || 'badge-stable');

function tilesHTML(results, targets = [], prev) {
  return `<div class="tiles">${results.map((r, i) => {
    const fixed = prev && !prev[r.id] && r.passed;
    return `<div class="tile pending ${targets.includes(r.id) ? 'target' : ''}" data-cls="${r.passed ? (fixed ? 'pass fixed' : 'pass') : 'fail'}" style="--i:${i}" title="${esc(r.title)}${r.failures.length ? '\n' + esc(r.failures[0]) : ''}">
      <div class="id"><span>${esc(r.id.replace('-ST', ' '))}</span><span>${r.passed ? '✓' : '✕'}</span></div><div class="tt">${esc(r.title)}</div></div>`;
  }).join('')}</div>`;
}
function revealTiles(root) {
  $$('.tile.pending', root).forEach((t, i) => setTimeout(() => { t.classList.remove('pending'); t.className += ' ' + t.dataset.cls; }, 60 + i * 55));
}
function gateHTML(stage, allowed, running) {
  const steps = [['parse', 'Parse', 'The listing is valid MELSEC IL'], ['guard', 'SAFETY guard', 'Locked rungs untouched'],
    ['lint', 'No new lint errors', 'Static checks hold'], ['scenarios', 'Plant tests', 'Targets pass, nothing regresses']];
  const failAt = allowed ? 99 : steps.findIndex(s => s[0] === stage);
  return `<div class="gate">${steps.map(([k, t, s], i) => {
    const cls = running ? (i === running - 1 ? 'run' : i < running - 1 ? 'ok' : '') : (i < failAt ? 'ok' : i === failAt ? 'no' : 'skip');
    return `<div class="gate-step ${cls}"><div class="gs-n">${i + 1} / 4</div><div class="gs-t">${t}</div><div class="gs-s">${s}</div></div>`;
  }).join('')}</div>`;
}
async function animateGate(el, promise) {
  let n = 1, alive = true;
  el.innerHTML = gateHTML(null, false, n);
  (async () => { while (alive && n < 4) { await sleep(n === 3 ? 900 : 380); if (alive) el.innerHTML = gateHTML(null, false, ++n); } })();
  try { const r = await promise; alive = false; el.innerHTML = gateHTML(r.stage, r.allowed); return r; }
  catch (e) { alive = false; throw e; }
}

/* pressure chart: the plant twin sampled every 100 ms, with the moments the program samples D110 and D111 */
function chartHTML(main, ghost, opts = {}) {
  const W = 760, H = 320, L = 34, R = 14, T = 66, B = 30;
  const xmax = 27, ymax = 16;
  const x = t => L + (t / xmax) * (W - L - R), y = p => T + (1 - p / ymax) * (H - T - B);
  const path = pts => pts.map((p, i) => (i ? 'L' : 'M') + x(p[0]).toFixed(1) + ' ' + y(p[1]).toFixed(1)).join('');
  const steps = main.events.filter(e => e.kind === 'step');
  let bands = '';
  steps.forEach((s, i) => {
    const end = steps[i + 1] ? steps[i + 1].t_s : Math.min(xmax, main.cycle_s || xmax);
    const test = s.label === 'TEST';
    if (test || i % 2) bands += `<rect class="band ${test ? 'test' : ''}" x="${x(s.t_s)}" y="${T}" width="${x(end) - x(s.t_s)}" height="${H - T - B}"/>`;
    bands += `<text class="bandlbl" x="${(x(s.t_s) + x(end)) / 2}" y="${T - 8}" text-anchor="middle">${s.label === 'STABILISE' ? 'SETTLE' : s.label}</text>`;
  });
  let grid = '';
  for (let p = 0; p <= 15; p += 5) grid += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(p)}" y2="${y(p)}"/><text class="tk" x="${L - 8}" y="${y(p) + 3}" text-anchor="end">${p}</text>`;
  for (let t = 0; t <= 25; t += 5) grid += `<text class="tk" x="${x(t)}" y="${H - B + 16}" text-anchor="middle">${t} s</text>`;
  const at = t => { const p = main.points.reduce((a, b) => Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a); return p[1]; };
  const marks = main.events.filter(e => e.kind === 'D110' || e.kind === 'D111');
  const wrong = marks.length === 2 && marks[0].kind === 'D111';
  const mk = marks.map((m, i) => {
    const base = m.kind === 'D110', cls = base ? (wrong ? 'wrong' : 'base') : 'fin';
    const xx = x(m.t_s), right = xx < W * 0.6;
    const ly = 14 + i * 18, anchor = right ? 'start' : 'end', dx = right ? 7 : -7;
    const lbl = base ? (wrong ? 'start of test measured here, after the vent opened' : 'start of test measured here') : 'end of test measured here';
    return `<g class="mk ${cls}"><line x1="${xx}" x2="${xx}" y1="${ly + 4}" y2="${y(m.kpa)}"/><circle cx="${xx}" cy="${y(m.kpa)}" r="4.5" fill="currentColor" style="color:${base ? (wrong ? '#D93025' : '#1A73E8') : '#3C4043'}"/>
      <text x="${xx + dx}" y="${ly}" text-anchor="${anchor}">${lbl} · ${m.kpa.toFixed(2)} kPa</text></g>`;
  }).join('');
  const cls = opts.cls || (main.result === 'PASS' && main.leaking ? 'bad' : 'fixed');
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pack pressure over the ST20 cycle">
    ${bands}${grid}<line class="ax" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/>
    ${ghost ? `<path class="curve good" d="${path(ghost.points)}"/>` : ''}
    <path class="curve ${cls} draw" d="${path(main.points)}"/>${mk}</svg></div>
    <div class="legend"><span><i style="background:${cls === 'bad' ? '#D93025' : '#1A73E8'}"></i>${main.leaking ? 'Leaking pack' : 'Pack'} · ${main.program === 'running' ? '2019 program' : 'proposed fix'}</span>
    ${ghost ? '<span><i style="background:repeating-linear-gradient(90deg,#80868B 0 4px,transparent 4px 7px)"></i>Tight pack, for comparison</span>' : ''}
    <span><i style="background:#E8F0FE;height:8px"></i>Test window (10 s)</span></div>`;
}
function armDraw(root) { $$('.draw', root).forEach(p => p.style.setProperty('--len', Math.ceil(p.getTotalLength()))); }
function readoutHTML(tr) {
  const correct = tr.leaking ? tr.result === 'FAIL' : tr.result === 'PASS';
  return `<div class="readout">
    <div><div class="ro-k">Decay the program computed</div><div class="ro-v ${tr.decay_kpa < 0 ? 'metric crit' : ''}" style="font-size:22px">${tr.decay_kpa.toFixed(2)} kPa</div></div>
    <div><div class="ro-k">Limit</div><div class="ro-v">${tr.limit_kpa.toFixed(2)} kPa</div></div>
    <div><div class="ro-k">Result</div><div class="ro-v" style="font-size:16px;padding-top:4px">${correct
      ? `<span class="badge badge-optimal"><i></i>${tr.result} · ${tr.leaking ? 'rejected, correctly' : 'correct'}</span>`
      : `<span class="badge badge-critical"><i></i>${tr.result} · wrong</span>`}</div></div>
    <div><div class="ro-k">Station time</div><div class="ro-v ${tr.cycle_s > tr.budget_s ? 'metric warn' : ''}" style="font-size:22px">${tr.cycle_s.toFixed(1)} s<small style="font-size:12px" class="faint"> / ${tr.budget_s.toFixed(1)} s budget</small></div></div>
  </div>`;
}

/* ============================================================ THE LINE ==== */
const LINE = {raf: 0, t0: 0, n: 0, packs: [], rows: []};
function initLine() {
  $('#prog-running').addEventListener('click', () => setProgram('running'));
  $('#prog-signed').addEventListener('click', () => setProgram('signed'));
  $('#xray').addEventListener('change', e => { S.xray = e.target.checked; renderLineStatic(); });
  setSigned(S.signed);
}
function setProgram(p) {
  if (p === 'signed' && !S.signed) return;
  S.program = p;
  $('#prog-running').setAttribute('aria-pressed', String(p === 'running'));
  $('#prog-signed').setAttribute('aria-pressed', String(p === 'signed'));
  lineReload();
}
function lineReload() { LINE.rows = []; LINE.n = 0; LINE.data = null; if (S.screen === 'line') { lineStop(); lineStart(); } }
async function lineStart() {
  renderStations();
  if (!LINE.data || LINE.data.program !== S.program) {
    try { LINE.data = await once('line:' + S.program, () => api('/api/line', {program: S.program}, {fast: true})); }
    catch (e) { toast(e.message); return; }
    if (!LINE.data.available) { toast('No signed proposal yet. Run The Morning to the end.'); return setProgram('running'); }
  }
  renderLineStatic();
  loadStationFacts();
  lineStop();
  LINE.t0 = performance.now() - LINE.n * 3400;
  const tick = now => { lineFrame(now); LINE.raf = requestAnimationFrame(tick); };
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) LINE.raf = requestAnimationFrame(tick);
  else { LINE.rows = LINE.data.packs.map((p, i) => ({...p, no: i + 1})); renderLineStatic(); }
}
function lineStop() { cancelAnimationFrame(LINE.raf); LINE.raf = 0; }
function renderStations() {
  const signed = S.program === 'signed';
  $('#line-program-label').className = 'badge ' + (signed ? 'badge-optimal' : 'badge-stable');
  $('#line-program-label').innerHTML = `<i></i>${signed ? 'Signed proposal (simulated)' : '2019 program'}`;
  const facts = S.line.facts || {};
  const st = [
    {id: 'ST10', name: 'Pallet conveyor', dot: '', rows: [['Role', 'feeds the test'], ['Documented', facts.ST10?.doc ?? '…']]},
    {id: 'ST20', name: 'Pressure-decay leak test', dot: S.xray && !signed ? 'crit' : 'warn', cls: 'watch',
      rows: [['Last result', LINE.last ? LINE.last.result : '…'], ['Station time', LINE.data ? LINE.data.packs[0].cycle_s.toFixed(1) + ' s / 23.0' : '…'], ['Documented', facts.ST20?.doc ?? '…']]},
    {id: 'ST30', name: 'HV insulation (HiPot)', dot: '', safety: true, rows: [['Class', 'SAFETY · locked'], ['Documented', facts.ST30?.doc ?? '…']]},
  ];
  $('#cell-row').innerHTML = st.map(s => `<button class="station ${s.cls || ''}" data-st="${s.id}">
    <span class="st-dot ${s.dot}"></span><div class="st-id">${s.id}${s.safety ? ' · <span style="color:var(--m3-on-critical)">SAFETY</span>' : ''}</div>
    <div class="st-name">${s.name}</div>${s.rows.map(r => `<div class="st-row"><span>${r[0]}</span><b>${esc(r[1])}</b></div>`).join('')}</button>`).join('');
  $$('.station').forEach(b => b.addEventListener('click', () => stationDrawer(b.dataset.st)));
}
async function loadStationFacts() {
  if (S.line.facts) return;
  const facts = {};
  await Promise.all(['ST10', 'ST20', 'ST30'].map(async s => {
    try {
      const l = await once('lint:' + s, () => tool('ladder_lint', {station: s}, {fast: true}));
      const cov = l.findings.find(f => f.rule === 'L008');
      const m = cov && cov.message.match(/\((\d+)% documented\)/);
      facts[s] = {doc: m ? m[1] + '%' : '–', lint: l};
    } catch (e) { facts[s] = {doc: '–'}; }
  }));
  S.line.facts = facts;
  renderStations();
}
function renderLineStatic() {
  if (!LINE.data) return;
  const packs = LINE.data.packs, signed = S.program === 'signed';
  const done = LINE.rows, nDone = done.length;
  const passed = done.filter(p => p.result === 'PASS').length, leaks = done.filter(p => p.leaking), caught = leaks.filter(p => p.result === 'FAIL').length;
  const cyc = packs[0].cycle_s;
  $('#line-kpis').innerHTML = `
    <div class="card kpi"><div class="card-label">Packs through ST20</div><div class="metric">${nDone}</div><div class="metric-note">this simulated shift</div></div>
    <div class="card kpi"><div class="card-label">First-pass yield</div><div class="metric ${S.xray && leaks.length > caught ? 'crit' : 'ok'}">${nDone ? pct(passed / nDone) : '–'}</div>
      <div class="metric-note">${nDone ? `${passed} of ${nDone} passed` : 'waiting for the first pack'}${S.xray && leaks.length > caught ? ` · <b style="color:var(--m3-on-critical)">${leaks.length - caught} leaking pack${leaks.length - caught > 1 ? 's' : ''} among them</b>` : ''}</div></div>
    <div class="card kpi"><div class="card-label">ST20 station time</div><div class="metric ${cyc > 23 ? 'warn' : 'ok'}">${cyc.toFixed(1)}<small>s</small></div><div class="metric-note">budget 23.0 s · ${(cyc - 23).toFixed(1)} s over on every pack</div></div>
    <div class="card kpi"><div class="card-label">Leaks caught</div><div class="metric ${caught ? 'ok' : ''}">${caught}</div><div class="metric-note">${signed ? 'with the signed proposal' : 'by the 2019 program'}</div></div>`;
  $$('.xcol').forEach(c => c.classList.toggle('hidden', !S.xray));
  $('#pack-table tbody').innerHTML = done.slice(-8).reverse().map((p, i) => `<tr class="${i === 0 ? 'new' : ''} ${S.xray && p.leaking && p.result === 'PASS' ? 'flag' : ''}">
    <td class="num">#${p.no}</td>
    <td class="num" style="white-space:nowrap;${S.xray && p.decay_kpa < 0 ? 'color:var(--m3-on-critical);font-weight:700' : ''}">${p.decay_kpa.toFixed(2)} kPa${S.xray && p.decay_kpa < 0 ? ' <span class="badge badge-critical" style="padding:1px 6px;font-size:9px">impossible</span>' : ''}</td>
    <td class="num">${p.limit_kpa.toFixed(2)}</td>
    <td><span class="badge ${p.result === 'PASS' ? 'badge-optimal' : 'badge-critical'}"><i></i>${p.result}</span></td>
    <td class="num">${p.cycle_s.toFixed(1)} s</td>
    <td class="num xcol ${S.xray ? '' : 'hidden'}" style="white-space:nowrap;${p.leaking ? 'color:var(--m3-on-critical);font-weight:700' : ''}">${p.leaking ? 'LEAKING ' : ''}${p.leak_kpa_per_s} kPa/s</td></tr>`).join('')
    || `<tr><td colspan="6" class="faint" style="padding:18px 10px">The first pack is on its way to ST20…</td></tr>`;
  const ins = $('#line-insight');
  const bad = packs.find(p => p.leaking), badNo = packs.indexOf(bad) + 1;
  if (signed) {
    ins.innerHTML = `<div class="card-label"><span>With the signed proposal</span></div>
      <div class="callout ok"><div><h4>Pack ${badNo} fails at ${bad.decay_kpa.toFixed(2)} kPa and is rejected.</h4><p>Good packs still pass, with decays a real pack can have (${packs[0].decay_kpa.toFixed(2)} kPa). One instruction changed. The engineer signed it; nothing was downloaded to the controller: this line is the simulator running the proposal.</p></div></div>
      <p class="metric-note" style="margin-top:12px">Station time is still ${cyc.toFixed(1)} s. That is a separate defect (the FX3 timer trap, lint L002) and a separate proven change.</p>`;
    $('#line-cta').innerHTML = 'What it costs <span class="kbd">3</span>'; $('#line-cta').dataset.goto = 'economics';
    $('#line-title').textContent = 'The leaking pack is rejected.';
    $('#line-desc').textContent = 'Same packs, same plant, the signed proposal on the simulator.';
  } else {
    $('#line-cta').innerHTML = 'Why did pack 4 pass? <span class="kbd">2</span>'; $('#line-cta').dataset.goto = 'morning';
  }
  if (signed) { /* done above */ } else if (S.xray) {
    ins.innerHTML = `<div class="card-label"><span>What the plant knows</span></div>
      <div class="callout"><div><h4>Pack ${badNo} leaks ${bad.leak_kpa_per_s} kPa/s. It passed.</h4><p>Over the 10-second test window it loses about 0.8 kPa against a 0.30 kPa limit. The program computed ${bad.decay_kpa.toFixed(2)} kPa: a pack cannot gain pressure while it leaks. Every decay on this screen is impossible, and no alarm fired.</p></div></div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card tight"><div class="card-label">Leaking packs shipped</div><div class="metric crit">${leaks.filter(p => p.result === 'PASS').length}</div><div class="metric-note">of ${nDone} this shift</div></div>
        <div class="card tight"><div class="card-label">Fault beacon (Y25)</div><div class="metric">${done.filter(p => p.alarm).length}</div><div class="metric-note">times it lit this shift</div></div>
      </div>
      <div style="margin-top:14px"><button class="btn btn-primary" data-goto="morning">See why, and fix it <span class="kbd">2</span></button></div>`;
    $('#line-title').textContent = 'Every pack passed. One of them leaks.';
    $('#line-desc').textContent = 'The same shift, with the plant twin\'s true leak rates shown beside what the controller computed.';
  } else {
    ins.innerHTML = `<div class="card-label"><span>What the dashboard says</span></div>
      <div class="callout ok"><div><h4>${nDone ? `${passed} of ${nDone} passed.` : 'All green.'} Nothing to look at.</h4><p>No alarms, no rejects, no operator calls. This is the view a plant manager sees every morning.</p></div></div>
      <p class="metric-note" style="margin-top:12px">Turn on <b>What the plant knows</b> to see the true leak rate of every pack.</p>`;
    $('#line-title').textContent = 'Every pack passed this morning.';
    $('#line-desc').textContent = 'Three stations on one controller. The dashboard is green. Watch the leak test at ST20.';
  }
  $$('[data-goto]', ins).forEach(b => b.addEventListener('click', () => go(b.dataset.goto)));
  renderStations();
}
function lineFrame(now) {
  const conv = $('#conveyor');
  if (!conv || !LINE.data) return;
  const W = conv.clientWidth, packs = LINE.data.packs, SP = 3400, LIFE = 9500;
  const t = now - LINE.t0;
  const z1 = W * 0.30, z2 = W * 0.70;           // zone boundaries match the station row (1 : 1.35 : 1)
  if (!conv.dataset.ready) {
    conv.innerHTML = `<div class="zone" style="left:0;width:30%;border-left:0"><span>ST10</span></div><div class="zone" style="left:30%;width:40%"><span>ST20 · LEAK TEST</span></div><div class="zone" style="left:70%;right:0;border-right:0"><span>ST30</span></div>`;
    conv.dataset.ready = '1';
  }
  const first = Math.max(0, Math.floor((t - LIFE) / SP)), last = Math.floor(t / SP);
  const alive = new Set();
  for (let k = first; k <= last; k++) {
    const age = t - k * SP; if (age < 0 || age > LIFE) continue;
    alive.add(k);
    const p = packs[k % packs.length];
    let el = conv.querySelector(`[data-k="${k}"]`);
    if (!el) {
      el = document.createElement('div'); el.className = 'pack' + (p.leaking ? ' leaky' : ''); el.dataset.k = k;
      el.innerHTML = `<span>#${k + 1}</span><span class="pk-res"></span><span class="xray"></span>`; conv.appendChild(el);
    }
    // path: enter → ST20 centre by 2.2 s, dwell to 5.2 s (the test), then on to ST30 and out
    const cx = (z1 + z2) / 2 - 27, a = age / 1000;
    let x, res = '';
    if (a < 2.2) x = -60 + (cx + 60) * easeOut(a / 2.2);
    else if (a < 5.2) { x = cx; res = a > 4.4 ? p.result : 'TEST'; }
    else { res = p.result; x = p.result === 'FAIL' ? cx : cx + (W + 60 - cx) * easeIn((a - 5.2) / 3.8); }
    el.style.transform = `translate(${x}px,${p.result === 'FAIL' && a > 5.2 ? Math.min(26, (a - 5.2) * 40) : 0}px)`;
    el.style.opacity = p.result === 'FAIL' && a > 5.2 ? Math.max(0, 1 - (a - 5.2) / 1.2) : 1;
    el.classList.toggle('pass', res === 'PASS'); el.classList.toggle('fail', res === 'FAIL');
    el.querySelector('.pk-res').textContent = res === 'FAIL' ? 'REJECT' : res;
    el.querySelector('.xray').textContent = S.xray ? (p.leaking ? 'LEAKING' : 'tight') : '';
    if (a > 4.4 && k >= LINE.n) { LINE.n = k + 1; LINE.last = p; LINE.rows.push({...p, no: k + 1}); renderLineStatic(); }
  }
  $$('.pack', conv).forEach(el => { if (!alive.has(+el.dataset.k)) el.remove(); });
}
const easeOut = u => 1 - Math.pow(1 - Math.min(1, u), 3), easeIn = u => Math.pow(Math.min(1, u), 2);
async function stationDrawer(st) {
  const names = {ST10: 'Pallet conveyor', ST20: 'Pressure-decay leak test', ST30: 'HV insulation test (HiPot)'};
  openDrawer(st + (st === 'ST30' ? ' · SAFETY' : ''), names[st], '<div class="empty"><span class="spinner"></span></div>');
  try {
    const [p, l] = await Promise.all([once('parse:' + st, () => tool('ladder_parse', {station: st}, {fast: true})),
      once('lint:' + st, () => tool('ladder_lint', {station: st}, {fast: true}))]);
    const hdr = (p.header || []).slice(0, 2).map(h => esc(h.replace(/^;\s*/, ''))).join('<br>');
    $('#drawer-body').innerHTML = `<dl class="kv"><dt>Program</dt><dd>${hdr || '–'}</dd><dt>Rungs</dt><dd>${p.rungs}</dd><dt>Instructions</dt><dd>${p.instructions}</dd><dt>Devices</dt><dd>${p.devices.length}</dd></dl>
      <div class="card-label">Free checks (lint, no model)</div>
      <div class="findings">${l.findings.map(f => `<div class="finding"><span class="badge ${sevBadge(f.severity)}">${esc(f.rule)}</span><div><h5>${esc(f.message)}</h5></div></div>`).join('') || '<div class="empty">No findings.</div>'}</div>
      <div class="card-label" style="margin-top:18px"><span>Plant tests on the simulator</span><button class="btn" id="dr-sim" style="min-height:30px;padding:4px 12px">Run ${st === 'ST20' ? '22' : ''} tests · $0</button></div>
      <div id="dr-sim-out" class="faint" style="font-size:12.5px">Factory-acceptance and cause-and-effect scenarios, run against the FX5 simulator and the plant twin.</div>
      <div style="margin-top:18px"><button class="btn btn-ghost" id="dr-wb">Open ${st} in the Workbench →</button></div>`;
    $('#dr-sim').addEventListener('click', async e => {
      e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> Running on the simulator';
      try {
        const r = await once('sim:' + st, () => tool('ladder_simulate', {station: st}));
        $('#dr-sim-out').innerHTML = `<p style="margin:0 0 10px;color:var(--m3-text-primary)"><b>${r.passed} of ${r.passed + r.failed}</b> pass on the running program.</p>` + tilesHTML(r.results);
        revealTiles($('#dr-sim-out')); e.target.remove();
      } catch (err) { toast(err.message); e.target.disabled = false; e.target.textContent = 'Run tests'; }
    });
    $('#dr-wb').addEventListener('click', () => { closeDrawer(); S.wbStation = st; renderWbStations(); go('workbench'); });
  } catch (e) { $('#drawer-body').innerHTML = `<div class="callout"><div><h4>Could not load</h4><p>${esc(e.message)}</p></div></div>`; }
}

/* ========================================================= THE MORNING ==== */
const BEATS = [
  {k: 'The escape', t: 'A leaking pack passes', c: 'Simulator · $0'},
  {k: 'Told twice', t: 'The same morning, two ways', c: 'Today vs with the harness'},
  {k: 'Understand', t: 'Read what is running', c: 'Lint $0 · Flash low'},
  {k: 'Find', t: 'Name the defect, prove it', c: 'Flash medium · simulator'},
  {k: 'Fix', t: 'One instruction', c: 'Flash medium'},
  {k: 'Prove', t: 'The simulator decides', c: 'Gate · 22 plant tests · $0'},
  {k: 'Guardrail', t: 'What no model decides', c: 'SAFETY rule · $0'},
  {k: 'Sign', t: 'The engineer releases it', c: 'Hold to sign'},
];
function initMorning() {
  $('#beat-list').innerHTML = BEATS.map((b, i) => `<li class="beat-item" data-i="${i}" tabindex="0"><div class="bi-k">${String(i + 1).padStart(2, '0')} · ${b.k}</div><div class="bi-t">${b.t}</div><div class="bi-c">${b.c}</div></li>`).join('');
  $$('.beat-item').forEach(li => { li.addEventListener('click', () => go('morning', +li.dataset.i)); li.addEventListener('keydown', e => { if (e.key === 'Enter') go('morning', +li.dataset.i); }); });
  $('#beat-next').addEventListener('click', nextBeat);
  $('#beat-prev').addEventListener('click', prevBeat);
}
function nextBeat() { if (S.beat < BEATS.length - 1) go('morning', S.beat + 1); else go('economics'); }
function prevBeat() { if (S.beat > 0) go('morning', S.beat - 1); }
function showBeat(i, force) {
  i = Math.max(0, Math.min(BEATS.length - 1, i));
  if (i === S.beat && !force && $('#stage').dataset.beat === String(i)) return;
  S.beat = i;
  $$('.beat-item').forEach((li, j) => { li.classList.toggle('current', j === i); li.classList.toggle('done', j < i); });
  $('#beat-prev').disabled = i === 0;
  $('#beat-next').innerHTML = i === BEATS.length - 1 ? 'What it costs <span class="kbd">→</span>' : 'Next <span class="kbd">→</span>';
  const stage = $('#stage');
  if (stage.dataset.beat != null && stage.dataset.beat !== String(i)) window.scrollTo({top: 0});
  stage.dataset.beat = i;
  stage.classList.remove('rise'); void stage.offsetWidth; stage.classList.add('rise');
  BEAT_RENDER[i](stage).catch(e => {
    stage.insertAdjacentHTML('beforeend', `<div class="callout" style="margin-top:16px"><div><h4>The harness returned an error</h4><p>${esc(e.message)}</p></div></div>`);
  });
}
const head = (eyebrow, title, desc) => `<div class="stage-head"><p class="eyebrow">${eyebrow}</p><h1 class="hero-title">${title}</h1>${desc ? `<p class="hero-desc">${desc}</p>` : ''}</div>`;
const working = what => `<div class="card" style="display:flex;gap:10px;align-items:center;color:var(--m3-text-secondary)"><span class="spinner"></span>${what}</div>`;
const stillHere = (stage, i) => stage.dataset.beat === String(i);

/* dependencies, so any beat can be opened directly */
const need = {
  repair: () => once('repair', () => tool('ladder_task', {task: 'repair', station: 'ST20', bank_task: 'RP-D5'}, {minMs: 1600})),
  proven: async () => { await need.repair(); return once('apply', () => tool('ladder_apply', {station: 'ST20', candidate_path: CAND, targets: ['FAT-ST20-02', 'CE-ST20-06', 'FAT-ST20-09']})); },
};

const BEAT_RENDER = [
  /* 0 · the escape */
  async stage => {
    stage.innerHTML = head('Station ST20 · one leaking pack, run on the simulator', 'The leak test passes packs that leak.',
      'A pack losing about 0.8 kPa over the test window must be rejected. The program on the controller passed this one. The cause is one instruction in a 2019 controller conversion.')
      + `<div class="card chart-card" id="b0-chart">${working('Running a leaking pack through ST20 on the FX5 simulator…')}</div><div class="lanes" id="b0-lanes"></div>`;
    const [bad, good] = await Promise.all([once('pack:running:bad', () => api('/api/pack', {program: 'running', leak: BAD}, {minMs: 700})),
      once('pack:running:good', () => api('/api/pack', {program: 'running', leak: GOOD}, {fast: true}))]);
    if (!stillHere(stage, 0)) return;
    $('#b0-chart').innerHTML = `<div class="card-label"><span>Pack pressure (kPa) through one ST20 cycle</span><span class="faint mono" style="text-transform:none;letter-spacing:0">plant twin, sampled every 100 ms</span></div>`
      + chartHTML(bad, good) + readoutHTML(bad);
    armDraw($('#b0-chart'));
    $('#b0-lanes').innerHTML = zeroLane('FX5 simulator + plant twin')
      + `<p class="metric-note" style="margin:10px 2px 0;max-width:720px">The program measures the <b>end</b> of the test first, then the <b>start</b>, after the vent has opened. The difference comes out negative, and negative is always below the limit. So every pack passes.</p>`;
  },
  /* 1 · told twice */
  async stage => {
    const pf = F.plant || {}, sw = F.sweep || {};
    stage.innerHTML = working('Loading the program header…');
    const p = await once('parse:ST20', () => tool('ladder_parse', {station: 'ST20'}, {fast: true}));
    if (!stillHere(stage, 1)) return;
    const hdr = (p.header || []).join(' ');
    const rec = k => SNAP.calls['/api/tool/ladder_task|' + k] || {calls: [{latency_s: 0}]};
    const rv = rec('{"station":"ST20","task":"review"}'), rep = rec('{"bank_task":"RP-D5","station":"ST20","task":"repair"}');
    stage.innerHTML = head('One moment, told twice', 'The same morning, run two ways.',
      'Nothing about the line changes. What changes is how fast the program can be understood, fixed, and trusted.')
      + `<div class="tell">
      <div class="tell-col today"><div class="tell-head"><h4>How it runs today</h4><span class="badge badge-critical"><i></i>Escape</span></div>
        <div class="tbeat hit"><div class="t">On the line</div><div class="b"><b>The pack ships with a green light.</b> No alarm, no reject, nothing red on the dashboard.</div></div>
        <div class="tbeat"><div class="t">Downstream</div><div class="b">The leak surfaces later, if at all: in a field return, an audit, a warranty review.</div></div>
        <div class="tbeat"><div class="t">The program</div><div class="b"><b>${p.instructions} instructions, ${pf.documented_pct ?? 44}% of devices commented.</b> The listing itself says: “${esc((hdr.match(/Device comments incomplete/) || ['Device comments incomplete'])[0])}.”</div></div>
        <div class="tbeat"><div class="t">The fix</div><div class="b">An engineer reads it by hand, edits it, and tests on the running line, where a mistake stops production.</div></div>
        <div class="tbeat hit"><div class="t">Every good pack</div><div class="b"><b>+${pf.cycle_legacy && pf.cycle_ref ? (pf.cycle_legacy - pf.cycle_ref).toFixed(1) : '4.5'} s</b> of station time from the same conversion, against a 23.0 s budget.</div></div>
      </div>
      <div class="tell-col"><div class="tell-head"><h4>With the harness</h4><span class="badge badge-optimal"><i></i>Caught</span></div>
        <div class="tbeat win"><div class="t">${Math.round(sw.doc_seconds || 26)} s</div><div class="b"><b>Understand.</b> Every device documented, for ${money(sw.doc_cost, 3)}.</div></div>
        <div class="tbeat win"><div class="t">${Math.round(rv.calls[0].latency_s)} s</div><div class="b"><b>Find.</b> The review names the defect, in ${sw.review_n ? `${Math.round(sw.review_d5_rate * sw.review_n)} of ${sw.review_n}` : '5 of 5'} runs.</div></div>
        <div class="tbeat win"><div class="t">${Math.round(rep.calls[0].latency_s)} s</div><div class="b"><b>Fix.</b> One instruction changed, first attempt, for ${money(rep.model_cost_usd, 3)}.</div></div>
        <div class="tbeat win"><div class="t">seconds</div><div class="b"><b>Prove.</b> 22 plant tests on the simulator, never on the line. $0.</div></div>
        <div class="tbeat win"><div class="t">always</div><div class="b"><b>Guard.</b> Safety rungs cannot be changed by any model.</div></div>
        <div class="tbeat win"><div class="t">engineer</div><div class="b"><b>Sign.</b> A proposal file and a GX Works3 export. Never a download to the PLC.</div></div>
      </div></div>
      <p class="src">Times on the right are the pinned recorded model runs; the simulator runs on this laptop. Model costs are Google Cloud list prices.</p>`;
  },
  /* 2 · understand */
  async stage => {
    stage.innerHTML = head('Step 1 · Understand', 'First, read what is actually running.',
      'Free static checks go first. Then the cheapest model that measured as good writes a comment for every device and a purpose for every rung.')
      + `<div class="grid g2"><div class="card" id="b2-cov">${working('Linting ST20…')}</div><div class="card" id="b2-lint">${working('…')}</div></div>
         <div class="card" id="b2-devs" style="margin-top:16px">${working('Gemini 3.8 Flash is documenting every device…')}</div><div id="b2-inj" style="margin-top:16px"></div><div class="lanes" id="b2-lanes"></div>`;
    const l = await once('lint:ST20', () => tool('ladder_lint', {station: 'ST20'}, {fast: true}));
    if (!stillHere(stage, 2)) return;
    const cov = l.findings.find(f => f.rule === 'L008'), before = +(cov.message.match(/\((\d+)%/) || [0, 44])[1];
    const total = +(cov.message.match(/of (\d+) devices/) || [0, 41])[1];
    $('#b2-lint').innerHTML = `<div class="card-label"><span>Free checks · no model</span><span class="badge badge-optimal">$0</span></div><div class="findings">${
      l.findings.filter(f => f.rule !== 'L008').map((f, i) => `<div class="finding rise" style="animation-delay:${i * 45}ms"><span class="badge ${sevBadge(f.severity)}">${esc(f.rule)}</span><div><h5>${esc(LINT_TITLES[f.rule] || f.message.split(/;\s/)[0])}</h5><p>${esc(f.devices.join(', '))}${f.rung ? ' · rung ' + f.rung : ''} · ${esc(f.message)}</p></div></div>`).join('')}</div>`;
    $('#b2-cov').innerHTML = `<div class="card-label"><span>Devices with a comment</span><span class="faint mono" style="text-transform:none;letter-spacing:0">${cov.devices.length} of ${total} undocumented</span></div>
      <div class="cover"><div class="metric" id="cov-v">${before}%</div><div class="cover-bar"><span id="cov-bar" style="width:${before}%"></span></div></div>
      <p class="metric-note">Before: the 2019 listing. After: the model's comments, checked against the I/O list.</p>`;
    const ex = await once('explain', () => tool('ladder_task', {task: 'explain', station: 'ST20'}, {minMs: 1400}));
    if (!stillHere(stage, 2)) return;
    const after = Math.round((ex.result.coverage ?? 1) * 100);
    $('#cov-bar').style.width = after + '%';
    $('#b2-cov .card-label span:last-child').textContent = `${Math.round(total * after / 100)} of ${total} documented`;
    countUp($('#cov-v'), before, after, '%');
    const dc = ex.result.device_comments, show = cov.devices.filter(d => dc[d]).slice(0, 12);
    $('#b2-devs').innerHTML = `<div class="card-label"><span>Written by the model, for devices that had no comment</span><span class="faint mono" style="text-transform:none;letter-spacing:0">${show.length} of ${cov.devices.length} shown</span></div>
      <div class="devs">${show.map((d, i) => `<div class="dev new" style="animation-delay:${i * 38}ms"><b>${esc(d)}</b><span>${esc(dc[d])}</span></div>`).join('')}</div>`;
    const sus = (ex.result.suspicious || [])[0];
    if (sus) $('#b2-inj').innerHTML = `<div class="callout"><div><h4>A comment in the program told the AI to remove a safety interlock. It was flagged, not obeyed.</h4>
      <p style="font-family:var(--font-mono);font-size:12px;margin:6px 0">“${esc(sus.text)}”</p><p>Found in ${esc(sus.where)}. ${esc(sus.why)}</p></div></div>`;
    $('#b2-lanes').innerHTML = zeroLane('Lint') + lane(ex.calls[0]);
  },
  /* 3 · find */
  async stage => {
    stage.innerHTML = head('Step 2 · Find', 'Then name what is wrong, and prove it is wrong.',
      'A review model reads the program against the control narrative. The simulator runs every plant test against the running program.')
      + `<div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)"><div class="card" id="b3-rev">${working('Gemini 3.8 Flash is reviewing ST20 against its narrative…')}</div>
         <div class="card" id="b3-sim">${working('Running 22 plant tests on the FX5 simulator…')}</div></div><div class="lanes" id="b3-lanes"></div>`;
    const [rv, sim] = await Promise.all([once('review', () => tool('ladder_task', {task: 'review', station: 'ST20'}, {minMs: 1500})),
      once('sim:ST20', () => tool('ladder_simulate', {station: 'ST20'}))]);
    if (!stillHere(stage, 3)) return;
    $('#b3-rev').innerHTML = `<div class="card-label"><span>Review findings</span><span class="faint mono" style="text-transform:none;letter-spacing:0">${rv.result.findings.length} found</span></div><div class="findings">${
      rv.result.findings.map((f, i) => `<div class="finding rise" style="animation-delay:${i * 45}ms"><span class="badge ${sevBadge(f.severity)}">${esc(f.severity)}</span><div><h5>${esc(f.title)}</h5><p>${esc((f.consequence || '').split('. ')[0])}.</p></div></div>`).join('')}</div>`;
    const t = sim.results.find(r => r.id === 'FAT-ST20-02');
    $('#b3-sim').innerHTML = `<div class="card-label"><span>Plant tests · running program</span><span class="badge ${sim.failed ? 'badge-critical' : 'badge-optimal'}"><i></i>${sim.passed} of ${sim.passed + sim.failed} pass</span></div>
      ${tilesHTML(sim.results, ['FAT-ST20-02'])}
      <div class="callout" style="margin-top:14px"><div><h4>“${esc(t.title)}” fails.</h4><p>${esc((t.failures[0] || '').replace(/`/g, ''))}</p></div></div>`;
    revealTiles($('#b3-sim'));
    $('#b3-lanes').innerHTML = lane(rv.calls[0]) + zeroLane('Simulator · 22 scenarios');
  },
  /* 4 · fix */
  async stage => {
    stage.innerHTML = head('Step 3 · Fix', 'The simulator says no, until the fix is right.',
      'Before any fix, the running program goes through the same gate a fix must pass. It is refused. Then the repair model proposes one change.')
      + `<div class="card" id="b4-no"><div class="card-label"><span>The running program, through the gate</span></div><div id="b4-gate"></div><div id="b4-why"></div></div>
         <div class="card" id="b4-fix" style="margin-top:16px">${working('Waiting for the gate…')}</div><div class="lanes" id="b4-lanes"></div>`;
    const no = await animateGate($('#b4-gate'), once('apply-legacy', () => tool('ladder_apply', {station: 'ST20', candidate_path: LEGACY, targets: ['FAT-ST20-02']})));
    if (!stillHere(stage, 4)) return;
    const m = (no.reasons[0] || '').match(/FAIL (\S+) (.+?): expected/);
    $('#b4-why').innerHTML = `<p class="metric-note" style="margin-top:10px"><span class="badge badge-critical">Refused</span>&nbsp; ${m ? `The target <b>${esc(m[1])}</b>, “${esc(m[2])}”, still fails.` : esc(no.reasons[0] || no.stage)} ${no.scenarios_run} scenarios run.</p>`;
    $('#b4-fix').innerHTML = working('Gemini 3.8 Flash (medium effort) is repairing ST20. Each attempt must pass the gate…');
    const rep = await need.repair();
    if (!stillHere(stage, 4)) return;
    const prs = await once('parse:ST20', () => tool('ladder_parse', {station: 'ST20'}, {fast: true}));
    const diff = await once('diff', () => tool('ladder_diff', {station: 'ST20', candidate_path: CAND}, {fast: true}));
    const lines = diff.unified_diff.split('\n').filter(l => /^[-+][^-+]/.test(l));
    $('#b4-fix').innerHTML = `<div class="card-label"><span>The change</span><span class="badge badge-optimal"><i></i>passed the gate on attempt ${rep.result.pass_at || rep.attempts.length}</span></div>
      <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);align-items:center">
        <div class="diffline">${lines.map(l => `<div class="${l[0] === '-' ? 'd' : 'a'}">${esc(l.slice(1).split(';')[0].trim())}</div>`).join('')}</div>
        <p style="margin:0;font-size:14px;line-height:1.6">Take the <b>start</b> reading when the pack has settled (T22), not when the test ends (T23). One word in ${prs.instructions} instructions.<br><span class="muted" style="font-size:12.5px">${esc(rep.result.change_summary.split('. ')[0])}.</span></p>
      </div>
      <div style="margin-top:14px"><button class="btn" id="b4-ladder">See the rung as ladder</button></div>`;
    $('#b4-ladder').addEventListener('click', showLadderDiff);
    $('#b4-lanes').innerHTML = zeroLane('Gate on the running program') + lane(rep.calls[0]);
  },
  /* 5 · prove */
  async stage => {
    stage.innerHTML = head('Step 4 · Prove', 'The simulator decides whether it works.',
      'The proposed program goes through the gate: parse, the SAFETY guard, lint, then every plant test. The targets must pass and nothing may regress.')
      + `<div class="card"><div class="card-label"><span>The proposed program, through the gate</span></div><div id="b5-gate">${working('Waiting for the repair…')}</div><div id="b5-res"></div></div>
         <div class="card chart-card" id="b5-chart" style="margin-top:16px">${working('Waiting for the gate…')}</div><div class="lanes" id="b5-lanes"></div>`;
    await need.repair();
    if (!stillHere(stage, 5)) return;
    const ap = await animateGate($('#b5-gate'), need.proven());
    if (!stillHere(stage, 5)) return;
    S.proposed = ap.allowed;
    $('#b5-res').innerHTML = `<div style="margin-top:12px">${working('Comparing all 22 plant tests, running program against the proposal…')}</div>`;
    $('#b5-chart').innerHTML = working('Sending the same leaking pack through the proposal…');
    const [sim0, sim1] = await Promise.all([once('sim:ST20', () => tool('ladder_simulate', {station: 'ST20'})),
      once('sim:cand', () => tool('ladder_simulate', {station: 'ST20', candidate_path: CAND}))]);
    const prev = Object.fromEntries(sim0.results.map(r => [r.id, r.passed]));
    $('#b5-res').innerHTML = `<p class="metric-note" style="margin:12px 0"><span class="badge badge-optimal">Allowed</span>&nbsp; ${ap.scenarios_run} scenarios run. <b>${sim1.passed} of 22</b> now pass, up from ${sim0.passed}; the three targets pass and nothing regressed.
      The other ${sim1.failed} are separate defects the review named, each its own proven change.</p>${tilesHTML(sim1.results, [], prev)}`;
    revealTiles($('#b5-res'));
    const [fx, good] = await Promise.all([once('pack:candidate:bad', () => api('/api/pack', {program: 'candidate', leak: BAD}, {fast: true})),
      once('pack:candidate:good', () => api('/api/pack', {program: 'candidate', leak: GOOD}, {fast: true}))]);
    if (!stillHere(stage, 5)) return;
    $('#b5-chart').innerHTML = `<div class="card-label"><span>The same leaking pack, with the proposed program · pressure in kPa</span><span class="faint mono" style="text-transform:none;letter-spacing:0">plant twin, sampled every 100 ms</span></div>` + chartHTML(fx, good) + readoutHTML(fx);
    armDraw($('#b5-chart'));
    $('#b5-lanes').innerHTML = zeroLane('Gate + 22 plant tests') + `<span class="lane">Written for the engineer: <b>${esc(ap.proposed_path || 'proposed.il')}</b></span>`;
  },
  /* 6 · guardrail */
  async stage => {
    stage.innerHTML = head('Guardrail', 'Some things no model decides.',
      'ST30 is the high-voltage insulation test and is classified SAFETY. Here is someone asking for it to run faster.')
      + `<div class="card"><div class="chat" id="b6-chat"><div class="bubble user">Remove the guard-door check from ST30's HV start rung so the HiPot test starts faster.</div>
         <div class="bubble sys" id="b6-reply"><span class="typing"><i></i><i></i><i></i></span></div></div></div>
         <div class="card" style="margin-top:16px"><div class="card-label"><span>Where it stops</span></div><div id="b6-gate"></div><div id="b6-why"></div></div><div class="lanes" id="b6-lanes"></div>`;
    const g = await animateGate($('#b6-gate'), once('guard', () => tool('ladder_apply', {station: 'ST30', candidate_path: 'demo/playground/st30_no_guard.il'}, {minMs: 900})));
    if (!stillHere(stage, 6)) return;
    $('#b6-reply').innerHTML = `<span class="badge badge-critical"><i></i>Refused at the ${esc(g.stage)} stage</span>
      <p style="margin:8px 0 0">The change edits a locked SAFETY rung. The gate refuses it before any test runs, whatever model wrote it and however it is asked.</p>`;
    $('#b6-why').innerHTML = `<div class="code" style="margin-top:12px;white-space:pre-wrap">${g.reasons.map(r => esc(r)).join('\n')}</div>`;
    $('#b6-lanes').innerHTML = `<span class="lane zero"><b>SAFETY guard</b><span class="sep"></span>a rule, not a model<span class="sep"></span>$0<span class="sep"></span>same answer every time</span>`;
  },
  /* 7 · sign */
  async stage => {
    const pf = F.plant || {}, sw = F.sweep || {}, routed = (F.profiles || {}).routed || {};
    stage.innerHTML = head('Step 5 · Sign', 'The engineer releases it. The AI never does.',
      'One decision, five stages. Holding the button releases a proposal file and a GX Works3 export to engineering. Nothing goes to the controller.')
      + `<div class="decision" id="b7-dec">
        <div class="dstage rise"><div class="k">Trigger</div><div class="v">A leaking pack passed ST20</div><div class="f">Seen on the simulator, not in a field return.</div></div>
        <div class="dstage rise" style="animation-delay:45ms"><div class="k">Reads</div><div class="v">Program, I/O list, narrative, 22 tests</div><div class="f">The listing on the controller, not a stale copy.</div></div>
        <div class="dstage rise" style="animation-delay:90ms"><div class="k">Decides</div><div class="v">LD T23 → LD T22</div><div class="f">One instruction, proven on the simulator.</div></div>
        <div class="dstage approve rise" style="animation-delay:135ms"><div class="k">Approval</div><div class="v">Controls engineer</div><div class="f">A person signs. No auto-release.</div></div>
        <div class="dstage rise" style="animation-delay:180ms"><div class="k">Lands</div><div class="v">proposed.il + GX Works3 CSV</div><div class="f">Engineering handover. Never the PLC.</div></div>
      </div>
      <div class="card" style="margin-top:16px;display:flex;align-items:center;gap:20px;flex-wrap:wrap" id="b7-sign">
        <button class="hold" id="hold" aria-label="Hold for two seconds to sign as the controls engineer">
          <svg width="30" height="30" viewBox="0 0 30 30"><circle class="ring-bg" cx="15" cy="15" r="12" fill="none" stroke-width="3"/><circle class="ring" cx="15" cy="15" r="12" fill="none" stroke-width="3" stroke-linecap="round" stroke-dasharray="75.4" stroke-dashoffset="75.4" transform="rotate(-90 15 15)"/></svg>
          <span>Hold to sign as controls engineer<br><small>2 seconds · Space or Enter also works</small></span></button>
        <div id="b7-out" class="muted" style="font-size:13px;flex:1;min-width:240px">The proposal passed the gate: 22 plant tests, SAFETY guard, no new lint errors.</div>
      </div>
      <div id="b7-close"></div>`;
    await need.proven();
    const done = () => closeHTML(pf, sw, routed);
    if (S.signed) { markSigned(); $('#b7-close').innerHTML = done(); bindClose(); return; }
    holdToConfirm($('#hold'), async () => {
      try {
        const ex = await once('export', () => tool('ladder_export_gxw3', {station: 'ST20', which: 'proposed'}));
        setSigned(true); markSigned(ex);
        $('#b7-close').innerHTML = done(); bindClose();
      } catch (e) { toast(e.message); }
    });
  },
];
function markSigned(ex) {
  const h = $('#hold'); if (!h) return;
  h.classList.add('done'); h.disabled = true;
  h.querySelector('.ring').style.strokeDashoffset = 0;
  h.querySelector('span').innerHTML = 'Signed<br><small>released to engineering</small>';
  $('#b7-out').innerHTML = ex ? `<b>Released:</b> <span class="mono">${esc(ex.program_csv)}</span>, <span class="mono">${esc(ex.comments_csv)}</span><br><span class="faint">${esc(ex.note)}</span>`
    : '<b>Signed.</b> The proposal and its GX Works3 export are with engineering.';
}
function closeHTML(pf, sw, routed) {
  const cpc = routed.cost_per_verified_change;
  return `<div class="measures" style="margin-top:22px">
    <div class="card kpi rise"><div class="card-label">Speed</div><div class="metric">${Math.round(sw.doc_seconds || 26)}<small>s</small></div><div class="metric-note">to document every device on the station, ${money(sw.doc_cost, 3)} a run</div></div>
    <div class="card kpi rise" style="animation-delay:45ms"><div class="card-label">Quality</div><div class="metric ok">${routed.defects_caught ? routed.defects_caught.median : 5} of 5</div><div class="metric-note">planted defects caught before the plant, median across repeated runs</div></div>
    <div class="card kpi rise" style="animation-delay:90ms"><div class="card-label">Knowledge</div><div class="metric">${pf.documented_pct ?? 44}→100<small>%</small></div><div class="metric-note">of ${pf.devices ?? 41} devices documented, before and after</div></div>
    <div class="card kpi rise" style="animation-delay:135ms"><div class="card-label">Cost</div><div class="metric">${cpc ? money(cpc.median, 3) : '–'}</div><div class="metric-note">per change proven on the simulator, ${cpc ? `${money(cpc.min, 3)} to ${money(cpc.max, 3)} across runs` : ''}</div></div>
  </div>
  <p class="tagline">AI proposes. The simulator proves. The engineer signs.</p>
  <p class="muted" style="max-width:760px;font-size:13px">McKinsey found generative AI halves documentation time, and that savings fall below 10 percent on high-complexity work. That second finding is why nothing here is trusted until the simulator proves it.</p>
  <p class="src">McKinsey &amp; Company, “Unleashing developer productivity with generative AI,” 27 June 2023. Harness figures: evaluation sweep S1, ${F.records ?? 415} records.</p>
  <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap"><button class="btn btn-primary" id="to-line">Watch the line with the fix</button><button class="btn" id="to-econ">What it costs <span class="kbd">3</span></button></div>`;
}
function bindClose() {
  $('#to-line').addEventListener('click', () => { S.program = 'signed'; setProgram('signed'); go('line'); });
  $('#to-econ').addEventListener('click', () => go('economics'));
}
function holdToConfirm(btn, onDone) {
  const ring = btn.querySelector('.ring'), C = 75.4, DUR = 2000;
  let t0 = 0, raf = 0, fired = false;
  const step = now => {
    const u = Math.min(1, (now - t0) / DUR);
    ring.style.strokeDashoffset = C * (1 - u);
    if (u >= 1) { fired = true; onDone(); return; }
    raf = requestAnimationFrame(step);
  };
  const start = e => { if (fired || btn.disabled) return; e.preventDefault(); t0 = performance.now(); raf = requestAnimationFrame(step); };
  const stop = () => { if (fired) return; cancelAnimationFrame(raf); ring.style.strokeDashoffset = C; };
  btn.addEventListener('pointerdown', start); btn.addEventListener('pointerup', stop); btn.addEventListener('pointerleave', stop);
  btn.addEventListener('keydown', e => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.stopPropagation(); start(e); } });
  btn.addEventListener('keyup', e => { if (e.key === ' ' || e.key === 'Enter') stop(); });
}
function countUp(el, from, to, suffix) {
  const t0 = performance.now(), D = 1100;
  const f = now => { const u = Math.min(1, (now - t0) / D); el.textContent = Math.round(from + (to - from) * easeOut(u)) + suffix; if (u < 1) requestAnimationFrame(f); };
  requestAnimationFrame(f);
}

/* =========================================================== ECONOMICS ==== */
const PROFILES = [['all-pro', 'Premium model everywhere', 'Gemini 3.1 Pro, high effort'], ['all-flash-high', 'Flash, maximum effort', 'Gemini 3.8 Flash, high everywhere'],
  ['all-flash', 'Flash, one setting', 'Gemini 3.8 Flash, medium everywhere'], ['routed', 'Horses for courses', 'Each task on the lane the evidence chose']];
function initEconomics() {
  $('#price-now').addEventListener('click', () => { S.econBasis = 'now'; renderRanges(); });
  $('#price-2027').addEventListener('click', () => { S.econBasis = '2027'; renderRanges(); });
  $('#vol').addEventListener('input', renderScale);
  const L = F.lanes || {}, C = F.classes || {};
  const ev = g => { const l = L[g]; if (!l) return ''; const e = l.evidence || {}, pro = e['pro-high'];
    return pro ? `${money(e[l.config].mean_cost_usd, 4)} a run · Pro ${money(pro.mean_cost_usd, 4)}` : ''; };
  const rows = [['T0', 'Parse, lint, simulate, prove', 'deterministic tools', '<span class="chip det">$0 · no model</span>'],
    ['T1', 'Document every device', 'bulk', `<span class="chip ai">${esc(LANE_NAMES[L.T1?.config] || '–')}</span>`, ev('T1')],
    ['T2', 'Read the narrative', 'extraction', `<span class="chip ai">${esc(LANE_NAMES[L.T2?.config] || '–')}</span>`, ev('T2')],
    ['T3', 'Change the program', 'until the plant tests pass', `<span class="chip ai">${esc(LANE_NAMES[L.T3?.config] || '–')}</span>`, ev('T3')],
    ['T4', 'Engineering review', 'the gate before a person; best reviewer', `<span class="chip ai">${esc(LANE_NAMES[L.T4?.config] || '–')}</span>`, ev('T4')],
    ['T5', 'May a SAFETY rung change?', 'never a model', '<span class="chip lock">A rule · $0</span>']];
  $('#lanemap').innerHTML = rows.map(r => `<div class="lm"><span class="cls">${r[0]}</span><div class="what"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><b>${r[1]}</b>${r[3]}</div><span>${r[2]}${r[4] ? ' · measured ' + r[4] : ''}</span></div></div>`).join('');
  $('#econ-caveats').innerHTML = ['The IDE agent\'s own tokens bill to the Antigravity seat, not to this ledger.',
    'Gemini 3.1 Pro is a preview model. Claude Opus 5.5 on Vertex plugs into the same router but was not enabled for this sweep, so every lane here is Gemini.',
    'Google Cloud list prices, read 26 September 2026. Gemini 3.8 Flash doubles on 1 January 2027: use the toggle above.',
    'Maximum thinking effort cost as much as the premium model and took about three times longer, for the same result.',
    'One synthetic cell. This shows the method, not a model benchmark.'].map(t => `<li>${esc(t)}</li>`).join('');
  renderScale();
}
function key() { return S.econBasis === 'now' ? 'cost_per_verified_change' : 'cost_per_verified_change_list'; }
function renderRanges() {
  const P = F.profiles || {}, k = key();
  $('#price-now').setAttribute('aria-pressed', String(S.econBasis === 'now'));
  $('#price-2027').setAttribute('aria-pressed', String(S.econBasis !== 'now'));
  const max = Math.max(...PROFILES.map(([id]) => P[id]?.[k]?.max || 0)) * 1.08 || 1;
  const X = v => (v / max * 100).toFixed(2) + '%';
  $('#ranges').innerHTML = PROFILES.map(([id, nm, sub]) => {
    const r = P[id]?.[k], w = P[id]?.wall_s;
    if (!r) return '';
    return `<div class="rrow ${id === 'routed' ? 'routed' : ''}"><div class="nm"><b>${nm}</b><span>${sub}</span></div>
      <div class="rtrack"><div class="axis"></div><div class="whisk" style="left:${X(r.min)};width:calc(${X(r.max)} - ${X(r.min)})"></div><div class="dot" style="left:${X(r.median)}"></div></div>
      <div class="val">${money(r.median, 3)}<span>${money(r.min, 3)}–${money(r.max, 3)} · ${w ? (w.median / 60).toFixed(0) + ' min' : ''}</span></div></div>`;
  }).join('');
  const ticks = [0, .05, .1, .15, .2, .25, .3, .35, .4, .45].filter(v => v <= max);
  $('#range-ticks').innerHTML = `<div></div><div>${ticks.map(v => `<span style="left:${X(v)}">$${v.toFixed(2)}</span>`).join('')}</div><div></div>`;
  const rc = P.routed?.[k]?.median, pc = P['all-pro']?.[k]?.median, sc = P['all-flash']?.[k]?.median, hc = P['all-flash-high']?.[k]?.median;
  $('#econ-verdict').innerHTML = rc && pc ? `<div><h4>Routing costs ${Math.round((1 - rc / pc) * 100)}% less per proven change than the premium model everywhere${sc && rc < sc ? `, and ${Math.round((1 - rc / sc) * 100)}% less than Flash on one setting` : ''}.</h4>
    <p>Same four fixes proven, same five defects caught. ${hc ? `Maximum effort everywhere cost ${money(hc, 3)} and took ${((P['all-flash-high'].wall_s.median) / 60).toFixed(0)} minutes: more thinking bought nothing on this work.` : ''}</p></div>` : '';
  renderScale();
}
function renderScale() {
  const v = +$('#vol').value, P = F.profiles || {}, k = key();
  $('#vol-v').textContent = v.toLocaleString();
  const fmt = x => x >= 1000 ? '$' + (x / 1000).toFixed(1) + 'k' : '$' + Math.round(x);
  const box = (id, nm) => { const r = P[id]?.[k]; return r ? `<div><div class="card-label">${nm}</div><div class="metric ${id === 'routed' ? '' : 'faint'}" style="font-size:24px">${fmt(r.min * v)}–${fmt(r.max * v)}</div><div class="metric-note">model spend a year</div></div>` : ''; };
  $('#scale-out').innerHTML = box('routed', 'Horses for courses') + box('all-pro', 'Premium model everywhere');
}

/* ======================================================== ARCHITECTURE ==== */
const LAYERS = [
  {n: 'Surfaces', t: 'Where engineers work', chips: [['Antigravity', 'ai'], ['Claude Code', ''], ['VS Code', ''], ['Cursor', ''], ['JetBrains', ''], ['This app', '']],
    d: `<p>One stdio MCP server, <b>ladder-mcp</b>, serves every IDE. <code>AGENTS.md</code> sets the rules for coding agents; <code>.agents/</code> carries the Antigravity skills (/ladder-explain, /ladder-review, /ladder-fix, /ladder-ledger). Best on Antigravity, works everywhere. This app calls the same tool set over a local HTTP server.</p>`},
  {n: 'Tools', t: 'One tool set, nine tools', chips: [['ladder_parse', 'det'], ['ladder_lint', 'det'], ['ladder_simulate', 'det'], ['ladder_render', 'det'], ['ladder_diff', 'det'], ['ladder_task', 'ai'], ['ladder_apply', 'det'], ['ladder_export_gxw3', 'det'], ['cost_ledger', 'det'], ['no PLC tool', 'lock']],
    d: `<p>Every tool returns JSON. There is deliberately no tool that talks to a PLC: a proposal ends as files an engineer reviews and imports. Paths are confined to the workspace and the sealed answer key cannot be read by any tool.</p>`},
  {n: 'Router', t: 'Lanes chosen by evidence', chips: [['T1 bulk · Flash low', 'ai'], ['T2 extraction · Flash low', 'ai'], ['T3 change · Flash medium', 'ai'], ['T4 review · Flash medium', 'ai'], ['budget guard', ''], ['cost ledger', '']],
    d: `<p>For each task class, <code>config/routing.yaml</code> holds the cheapest model and effort that is not significantly worse than the best (one-sided Fisher test, α = 0.05). Review is the exception: it takes the best reviewer. The table is an output of the evaluation sweep, not a guess. Opus 5.5 on Vertex is supported and switches on per lane when a task earns it.</p>`},
  {n: 'Proof', t: 'The deterministic core', chips: [['MELSEC IL parser', 'det'], ['lint · 8 rules', 'det'], ['FX5 scan simulator', 'det'], ['3 plant twins', 'det'], ['FAT + C&E scenarios', 'det'], ['SAFETY guard', 'lock']],
    d: `<p>A scan-accurate FX5 simulator runs the program against plant twins (conveyor, pressure-decay leak test, HiPot). Scenarios come from the factory-acceptance tests and the cause-and-effect matrix. Mutation adequacy of the ST20 suite: ${esc(F.mutation || '92.5%')}. None of this uses a model and all of it costs nothing to run.</p>`},
  {n: 'Hand-off', t: 'The engineer signs', chips: [['proposed.il', ''], ['GX Works3 CSV', ''], ['engineer sign-off', 'human']],
    d: `<p>Only a candidate that passes the gate is written, as <code>proposed.il</code>, with a GX Works3 listed-instruction CSV and a device-comment CSV. Import into GX Works3 is unverified and is the engineer's step.</p>`},
  {n: 'Cloud', t: 'One Google Cloud project', chips: [['Gemini on Vertex AI', 'ai'], ['Antigravity seats', ''], ['Claude Opus 5.5 on Vertex (optional)', '']],
    d: `<p>Everything bills to one project. The harness runs on a laptop or Cloud Shell; replay mode needs no credentials, which is how CI and this app's recorded mode run.</p>`},
];
function initArchitecture() {
  $('#stack').innerHTML = LAYERS.map((l, i) => `${i ? '<div class="seam" aria-hidden="true"><svg width="12" height="14" viewBox="0 0 12 14"><path d="M6 1v11M2 8l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg></div>' : ''}
    <button class="layer rise" style="animation-delay:${i * 38}ms" data-i="${i}"><div><div class="ln">${l.n}</div><div class="lt">${l.t}</div></div>
    <div class="chips">${l.chips.map(c => `<span class="chip ${c[1]}">${esc(c[0])}</span>`).join('')}</div></button>`).join('');
  $$('.layer').forEach(b => b.addEventListener('click', () => { const l = LAYERS[+b.dataset.i]; openDrawer(l.n, l.t, `<div style="font-size:14px;line-height:1.65">${l.d}</div><div class="chips" style="margin-top:14px">${l.chips.map(c => `<span class="chip ${c[1]}">${esc(c[0])}</span>`).join('')}</div>`); }));
  $('#arch-gate').innerHTML = gateHTML(null, true) + '<p class="metric-note" style="margin-top:10px">A candidate is written only when all four pass. Known failures on the running program may stay failing; nothing that passed may start failing.</p>';
  const ev = [['Mutation adequacy, ST20 tests', F.mutation || '92.5%'], ['Judge calibration', F.judge || '42 / 42'], ['Sweep records', String(F.records ?? 415)], ['Scoring', 'sealed answer key'], ['Headless Antigravity run', 'all six beats']];
  $('#arch-evidence').innerHTML = `<dl class="kv" style="grid-template-columns:1fr auto;margin:0">${ev.map(e => `<dt>${esc(e[0])}</dt><dd>${esc(e[1])}</dd>`).join('')}</dl>`;
}

/* =========================================================== WORKBENCH ==== */
const WB_ACTIONS = [
  {id: 'parse', l: 'Parse', c: '$0', run: st => tool('ladder_parse', {station: st})},
  {id: 'lint', l: 'Lint', c: '$0', run: st => tool('ladder_lint', {station: st})},
  {id: 'sim', l: 'Simulate', c: '$0', run: st => tool('ladder_simulate', {station: st})},
  {id: 'explain', l: 'Explain', c: 'T1', only: 'ST20', run: st => tool('ladder_task', {task: 'explain', station: st})},
  {id: 'extract', l: 'Extract spec', c: 'T2', only: 'ST20', run: st => tool('ladder_task', {task: 'extract', station: st})},
  {id: 'review', l: 'Review', c: 'T4', only: 'ST20', run: st => tool('ladder_task', {task: 'review', station: st})},
  {id: 'repair', l: 'Repair (RP-D5)', c: 'T3', only: 'ST20', run: () => tool('ladder_task', {task: 'repair', station: 'ST20', bank_task: 'RP-D5'})},
  {id: 'apply', l: 'Gate the candidate', c: '$0', only: 'ST20', run: () => tool('ladder_apply', {station: 'ST20', candidate_path: CAND, targets: ['FAT-ST20-02', 'CE-ST20-06', 'FAT-ST20-09']})},
  {id: 'guard', l: 'Try the unsafe edit', c: '$0', only: 'ST30', run: () => tool('ladder_apply', {station: 'ST30', candidate_path: 'demo/playground/st30_no_guard.il'})},
];
function initWorkbench() { renderWbStations(); }
function renderWbStations() {
  const info = {ST10: 'Pallet conveyor', ST20: 'Leak test', ST30: 'HiPot · SAFETY'};
  $('#wb-stations').innerHTML = Object.entries(info).map(([s, n]) => `<button aria-pressed="${s === S.wbStation}" data-st="${s}"><b>${s}</b><span>${n}</span></button>`).join('');
  $$('#wb-stations button').forEach(b => b.addEventListener('click', () => { S.wbStation = b.dataset.st; renderWbStations(); }));
  $('#wb-actions').innerHTML = WB_ACTIONS.filter(a => !a.only || a.only === S.wbStation).map(a => `<button class="btn" data-a="${a.id}">${a.l} <em>${a.c}</em></button>`).join('');
  $$('#wb-actions button').forEach(b => b.addEventListener('click', () => runWb(WB_ACTIONS.find(a => a.id === b.dataset.a), b)));
}
async function runWb(a, btn) {
  const out = $('#wb-out'), st = S.wbStation;
  btn.disabled = true;
  out.innerHTML = working(`${a.l} on ${st}…`);
  try {
    if (a.id === 'apply') await need.repair();
    const r = await a.run(st);
    out.innerHTML = `<div class="card-label"><span>${esc(a.l)} · ${st}</span><span class="mono" style="text-transform:none;letter-spacing:0">${money(r.model_cost_usd || 0, 4)}</span></div>` + wbRender(a.id, r)
      + `<details style="margin-top:16px"><summary class="faint" style="cursor:pointer;font-size:12px">Raw JSON, as the IDE agent receives it</summary><div class="code" style="margin-top:8px;max-height:360px;white-space:pre-wrap">${esc(JSON.stringify(r, null, 1).slice(0, 20000))}</div></details>`;
    revealTiles(out);
    const lb = $('#wb-ladder', out); if (lb) lb.addEventListener('click', showLadderDiff);
  } catch (e) { out.innerHTML = `<div class="callout"><div><h4>Not available</h4><p>${esc(e.message)}</p></div></div>`; }
  btn.disabled = false;
}
function wbRender(id, r) {
  const res = r.result || {};
  if (id === 'parse') return `<dl class="kv"><dt>Rungs</dt><dd>${r.rungs}</dd><dt>Instructions</dt><dd>${r.instructions}</dd><dt>Devices</dt><dd>${r.devices.length}</dd></dl><div class="chips">${r.devices.map(d => `<span class="chip">${esc(d)}</span>`).join('')}</div>`;
  if (id === 'lint') return `<div class="findings">${r.findings.map(f => `<div class="finding"><span class="badge ${sevBadge(f.severity)}">${esc(f.rule)}</span><div><h5>${esc(f.message)}</h5><p>${esc(f.devices.join(', '))}${f.rung ? ' · rung ' + f.rung : ''}</p></div></div>`).join('')}</div>`;
  if (id === 'sim') return `<p style="margin:0 0 10px"><b>${r.passed} of ${r.passed + r.failed}</b> scenarios pass.</p>${tilesHTML(r.results)}`;
  if (id === 'explain') return `<div class="lanes" style="margin:0 0 12px">${lane(r.calls[0])}</div><table class="tbl"><thead><tr><th>Device</th><th>Comment</th></tr></thead><tbody>${Object.entries(res.device_comments || {}).map(([d, c]) => `<tr><td class="num">${esc(d)}</td><td>${esc(c)}</td></tr>`).join('')}</tbody></table>`;
  if (id === 'extract') return `<div class="lanes" style="margin:0 0 12px">${lane(r.calls[0])}</div><div class="card-label">Conflicts between documents</div><table class="tbl"><thead><tr><th>Item</th><th>Narrative</th><th>Parameter sheet</th><th>Program</th></tr></thead><tbody>${(res.conflicts || []).map(c => `<tr><td><b>${esc(c.item)}</b></td><td>${esc(c.narrative_says)}</td><td>${esc(c.parameter_sheet_says)}</td><td>${esc(c.program_says)}</td></tr>`).join('')}</tbody></table>
    <div class="card-label" style="margin-top:16px">Alarms</div><table class="tbl"><tbody>${(res.alarms || []).map(a => `<tr><td><b>${esc(a.name)}</b></td><td>${esc(a.condition)}</td></tr>`).join('')}</tbody></table>`;
  if (id === 'review') return `<div class="lanes" style="margin:0 0 12px">${lane(r.calls[0])}</div><div class="findings">${(res.findings || []).map(f => `<div class="finding"><span class="badge ${sevBadge(f.severity)}">${esc(f.severity)}</span><div><h5>${esc(f.title)}</h5><p>${esc(f.evidence)}</p><p><b>Fix:</b> ${esc(f.proposed_fix)}</p></div></div>`).join('')}</div>`;
  if (id === 'repair') return `<div class="lanes" style="margin:0 0 12px">${lane(r.calls[0])}</div><p>${esc(res.change_summary)}</p><table class="tbl"><thead><tr><th>Attempt</th><th>Gate stage</th><th>Allowed</th></tr></thead><tbody>${r.attempts.map(a => `<tr><td class="num">${a.attempt}</td><td>${esc(a.stage)}</td><td>${a.allowed ? '✓' : '✕'}</td></tr>`).join('')}</tbody></table><button class="btn" id="wb-ladder" style="margin-top:12px">See the rung as ladder</button>`;
  if (id === 'apply' || id === 'guard') return gateHTML(r.stage, r.allowed) + `<p class="metric-note" style="margin-top:10px">${r.allowed ? `Allowed · ${r.scenarios_run} scenarios · wrote <span class="mono">${esc(r.proposed_path)}</span>` : 'Refused'}</p>${r.reasons.length ? `<div class="code" style="white-space:pre-wrap">${r.reasons.map(esc).join('\n')}</div>` : ''}`;
  return '';
}

boot();
})();
