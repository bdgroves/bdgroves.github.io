/* Flag Atlas: guess the flag, find the place, learn the story.
   The flag robot (tools/, run hourly on GitHub) builds the packs in data/ from Wikidata, Wikimedia Commons
   and Wikipedia, downloads the pictures into img/, and schedules Flag of the Day in data/daily.json. */
'use strict';

const ROUND = 10;
const KIND = { country: 'Country', state: 'US state', province: 'Canadian province', territory: 'Canadian territory',
  mxstate: 'Mexican state', dependency: 'Territory', region: 'Region', city: 'City', county: 'County' };
const ZOOM = { country: 4, state: 5, province: 4, territory: 3, mxstate: 6, dependency: 6, region: 6, county: 8, city: 9 };
const CATS = {
  country: { packs: ['world'], label: 'a country' },
  state: { packs: ['us-states', 'canada', 'mexico'], label: 'a US state, Canadian province or Mexican state' },
  region: { packs: ['territories', 'regions-africa', 'regions-americas', 'regions-europe', 'regions-asia', 'regions-oceania'], label: 'a state, province or region somewhere in the world' },
  city: { packs: ['us-cities', 'cities-africa', 'cities-americas', 'cities-europe', 'cities-asia', 'cities-oceania'], label: 'a city' },
  northwest: { packs: ['pnw'], label: 'a place in the Pacific Northwest' },
};
const TRIES = 6;
const FALLBACK_PACKS = [{ id: 'pnw', name: 'Pacific Northwest', area: 'Start here', blurb: 'Hand-picked, with the stories', file: 'data/pnw.json' }];

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window: play on without saving */ } },
};
const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const getJSON = async url => { const r = await fetch(url, { cache: 'no-cache' }); if (!r.ok) throw new Error(url + ' ' + r.status); return r.json(); };
const cache = {};
const loadFile = url => (cache[url] = cache[url] || getJSON(url));

const S = {
  view: store.get('fa_view', 'today'), packs: FALLBACK_PACKS, pack: null, packId: store.get('fa_pack', 'world'),
  round: null, seen: store.get('fa_seen', {}), filter: 'all', q: '', shown: 120, map: null, pinmap: null,
  mode: store.get('fa_mode', 'name'),          // 'name': four choices · 'pin': click where it flies
};
// Pin it: points fall off with distance; a miss of SCALE miles keeps about a third of the 1,000
const PIN_SCALE = { country: 500, state: 250, province: 350, territory: 450, mxstate: 150, dependency: 400, region: 220, county: 50, city: 120 };

/* ---------- small helpers ---------- */
const isTop = f => ['state', 'province', 'territory', 'mxstate', 'country'].includes(f.kind);
const sub = f => f.kind === 'country' ? `Country · ${f.region}` : isTop(f) ? KIND[f.kind] : `${KIND[f.kind]} · ${f.region}`;
const playable = p => p.flags.filter(f => f.ready !== false && !f.named);
function aboutLine(f) {
  let s = f.about ? f.about.charAt(0).toUpperCase() + f.about.slice(1) : KIND[f.kind];
  if (!isTop(f) && f.region && !s.includes(f.region)) s += `, ${f.region}`;
  if (f.pop) s += ` · pop. ${f.pop.toLocaleString()}`;
  return s;
}
function flagImg(f, alt) {
  return `<img src="${esc(f.img)}" alt="${esc(alt)}" decoding="async" onerror="this.outerHTML='<div class=&quot;noimg&quot;>Picture on its way</div>'">`;
}
function credit(f) {
  const c = f.credit || {}, lic = c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.license)}</a>` : esc(c.license || '');
  return `Flag image: ${c.artist ? esc(c.artist) + ', ' : ''}${lic}, via <a href="${esc(c.page)}" target="_blank" rel="noopener">Wikimedia Commons</a>.${f.story && !f.note ? ` Story: from <a href="${esc(f.story_url)}" target="_blank" rel="noopener">Wikipedia</a> (<a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>).` : ''} Place facts: Wikidata.`;
}
function revealCard(f, verdict, noMap) {
  const story = f.note || f.story;
  return `<div class="reveal${noMap ? ' solo' : ''}">
    <div class="txt">
      ${verdict ? `<div class="verdict ${verdict.ok ? 'right' : 'wrong'}">${esc(verdict.text)}</div>` : ''}
      <div class="place">${esc(f.name)}</div>
      <div class="about">${esc(aboutLine(f))}</div>
      ${story ? `<p class="note">${esc(story)}</p>` : ''}
      ${f.wiki ? `<a class="more" href="${esc(f.wiki)}" target="_blank" rel="noopener">More about ${esc(f.name)} →</a>` : ''}
      <p class="credit">${credit(f)}</p>
    </div>
    ${noMap ? '' : `<div class="minimap" id="minimap" aria-label="Map showing ${esc(f.name)}"></div>`}
  </div>`;
}
function drawMap(f, extra = []) {
  const el = $('#minimap'); if (!el || !window.L) return;
  if (S.map) { S.map.remove(); S.map = null; }
  const m = L.map(el, { scrollWheelZoom: false, worldCopyJump: true }).setView([f.lat, f.lon], ZOOM[f.kind] || 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(m);
  const pts = [[f.lat, f.lon]];
  for (const g of extra) {   // Flag of the Day: your guesses, in grey
    L.circleMarker([g.lat, g.lon], { radius: 5, color: '#7a7268', weight: 2, fillColor: '#d6d0c4', fillOpacity: 0.9 }).bindTooltip(g.name).addTo(m);
    pts.push([g.lat, g.lon]);
  }
  L.circleMarker([f.lat, f.lon], { radius: 8, color: '#8b3a2a', weight: 3, fillColor: '#c8922a', fillOpacity: 0.9 }).addTo(m);
  if (pts.length > 1) m.fitBounds(pts, { padding: [24, 24], maxZoom: ZOOM[f.kind] || 6 });
  S.map = m;
  setTimeout(() => m.invalidateSize(), 60);
}

/* ---------- status bar ---------- */
const bestKey = () => (S.mode === 'pin' ? 'fa_bestpin_' : 'fa_best_') + S.packId;
const bestText = b => S.mode === 'pin' ? `${b.toLocaleString()} pts` : `${b}/${ROUND}`;
function status() {
  const p = S.pack, r = S.round, best = store.get(bestKey(), null);
  if (S.view === 'today') {
    const st = store.get('fa_daily_stats', { played: 0, won: 0, streak: 0, best: 0 });
    $('#statusbar').innerHTML = `<span>Played <b>${st.played}</b></span><span>Solved <b>${st.won}</b></span><span>Streak <b>${st.streak}</b></span><span>Best streak <b>${st.best}</b></span>`;
    $('#badge').textContent = 'Flag of the Day';
    return;
  }
  $('#badge').textContent = p ? p.name : '';
  const pl = p ? playable(p) : [];
  const known = pl.filter(f => (S.seen[f.id] || {}).r).length;
  $('#statusbar').innerHTML = r && !r.over
    ? `<span>Flag <b>${Math.min(r.i + 1, r.items.length)}/${r.items.length}</b></span><span>Score <b>${r.score.toLocaleString()}</b></span>${r.mode === 'pin' ? '' : `<span>Streak <b>${r.streak}</b></span>`}${best !== null ? `<span>Best <b>${bestText(best)}</b></span>` : ''}`
    : `<span>Flags you know <b>${known}/${pl.length}</b></span>${best !== null ? `<span>Best round <b>${bestText(best)}</b></span>` : ''}`;
}

/* ---------- play ---------- */
function packPicker() {
  const areas = [...new Set(S.packs.map(k => k.area))];
  return areas.map(a => `<div class="area"><div class="area-name">${esc(a)}</div><div class="packs">${S.packs.filter(k => k.area === a).map(k =>
    `<button class="pack" data-pack="${k.id}" aria-pressed="${k.id === S.packId}"><b>${esc(k.name)}</b><small>${k.count ? k.count.toLocaleString() + ' flags · ' : ''}${esc(k.blurb)}</small></button>`).join('')}</div></div>`).join('');
}
function renderStart() {
  const p = S.pack, best = store.get(bestKey(), null), pl = playable(p);
  const peek = shuffle(pl).slice(0, 5);
  $('#main').innerHTML = `<div class="start">
    <h2>${S.mode === 'pin' ? 'Where does it fly?' : 'Whose flag is it?'}</h2>
    <p>${S.mode === 'pin'
      ? `You'll see ${ROUND} flags. Click the map where you think each one flies; the closer you land, the more points, up to 1,000 a flag. The map has no names on it, so it's you and your geography.`
      : `You'll see ${ROUND} flags. Pick the place that flies each one, then see where it is on the map and the story behind the design.`} Pick a set below: countries are the warm-up; cities and regions are where it gets good.</p>
    <div class="peek" aria-hidden="true">${peek.map((f, i) => `<img src="${esc(f.img)}" alt="" style="--t:${[-4, 3, -2, 4, -3][i]}deg" onerror="this.remove()">`).join('')}</div>
    <div class="modes" role="group" aria-label="How to play">
      <button class="mode" data-mode="name" aria-pressed="${S.mode === 'name'}">🔤 Name it<small>Four choices</small></button>
      <button class="mode" data-mode="pin" aria-pressed="${S.mode === 'pin'}">📍 Pin it<small>Click where it flies</small></button>
    </div>
    ${packPicker()}
    ${pl.length >= 4 ? `<button class="btn" id="go">${S.mode === 'pin' ? 'Pin' : 'Name'} ${ROUND}: ${esc(p.name)}</button>` : `<p class="wait">The robot is still fetching this set's pictures. Try another set, or check back in an hour.</p>`}
    ${best !== null ? `<div class="best">Your best here: ${bestText(best)}</div>` : ''}
  </div>`;
  if ($('#go')) $('#go').onclick = startRound;
  $('#main').querySelectorAll('.pack').forEach(b => b.onclick = async () => { await loadPack(b.dataset.pack); renderStart(); });
  $('#main').querySelectorAll('.mode').forEach(b => b.onclick = () => { S.mode = b.dataset.mode; store.set('fa_mode', S.mode); renderStart(); });
  status();
}

function startRound() {
  const flags = playable(S.pack);   // a flag with its own name on it would be a giveaway
  const fresh = shuffle(flags.filter(f => !(S.seen[f.id] || {}).r)), known = shuffle(flags.filter(f => (S.seen[f.id] || {}).r));
  const items = [...fresh, ...known].slice(0, ROUND);
  S.round = { items: shuffle(items), i: 0, score: 0, streak: 0, answers: [], over: false, mode: S.mode };
  renderQuestion();
}

function choicesFor(f) {
  // two neighbours (same country or continent) when there are any, so the choices make you look closely
  const pool = S.pack.flags.filter(x => x.id !== f.id && x.ready !== false);
  const near = shuffle(pool.filter(x => x.region === f.region));
  const sameKind = shuffle(pool.filter(x => !near.includes(x) && x.kind === f.kind));
  const rest = shuffle(pool.filter(x => !near.includes(x) && !sameKind.includes(x)));
  const picks = [...near.slice(0, 2), ...sameKind, ...rest].slice(0, 3);
  return shuffle([f, ...picks]);
}

function nextFlag(last) {
  const r = S.round;
  if (last) return finish();
  r.i++; renderQuestion(); scrollTo({ top: $('.console').offsetTop - 10, behavior: 'smooth' });
}
const markSeen = (f, ok) => { const s = S.seen[f.id] || { r: 0, w: 0 }; ok ? s.r++ : s.w++; S.seen[f.id] = s; store.set('fa_seen', S.seen); };

function renderQuestion() {
  if (S.round.mode === 'pin') return renderPin();
  const r = S.round, f = r.items[r.i];
  r.opts = choicesFor(f); r.answered = false;
  $('#main').innerHTML = `<div class="q">
    <div class="q-label">Flag ${r.i + 1} of ${r.items.length} · whose flag is this?</div>
    <div class="flagframe">${flagImg(f, 'A flag to identify')}</div>
    <div class="choices" role="group" aria-label="Choices">
      ${r.opts.map((o, k) => `<button class="choice" data-k="${k}"><span>${esc(o.name)}</span><small>${esc(sub(o))}</small></button>`).join('')}
    </div>
    <div id="after"></div>
  </div>`;
  $('#main').querySelectorAll('.choice').forEach(b => b.onclick = () => answer(+b.dataset.k));
  status();
}

function answer(k) {
  const r = S.round; if (r.answered) return;
  r.answered = true;
  const f = r.items[r.i], pick = r.opts[k], ok = pick.id === f.id;
  r.answers.push({ id: f.id, ok });
  if (ok) { r.score++; r.streak++; } else r.streak = 0;
  markSeen(f, ok);
  $('#main').querySelectorAll('.choice').forEach((b, i) => {
    b.disabled = true;
    if (r.opts[i].id === f.id) b.classList.add('right');
    else if (i === k) b.classList.add('wrong');
    else b.classList.add('dim');
  });
  const img = $('.flagframe img'); if (img) img.alt = 'Flag of ' + f.name;
  const last = r.i === r.items.length - 1;
  $('#after').innerHTML = revealCard(f, { ok, text: ok ? '✓ Right' : `✗ Not quite: you picked ${pick.name} (${sub(pick)})` }) +
    `<div class="next-row"><button class="btn" id="next">${last ? 'See how you did' : 'Next flag →'}</button></div>`;
  drawMap(f);
  $('#next').onclick = () => nextFlag(last);
  $('#next').focus({ preventScroll: true });
  status();
}

/* ---------- Pin it: click where the flag flies ---------- */
function packBounds() {
  const pts = playable(S.pack).map(f => [f.lat, f.lon]);
  const lats = pts.map(p => p[0]).sort((a, b) => a - b), lons = pts.map(p => p[1]).sort((a, b) => a - b);
  const q = (a, x) => a[Math.min(a.length - 1, Math.max(0, Math.round(x * (a.length - 1))))];
  // the middle 96% of the set's places, so one far-flung island doesn't zoom the map out to the whole world
  return [[q(lats, 0.02), q(lons, 0.02)], [q(lats, 0.98), q(lons, 0.98)]];
}
function renderPin() {
  const r = S.round, f = r.items[r.i];
  r.answered = false; r.guess = null;
  $('#main').innerHTML = `<div class="q">
    <div class="q-label">Flag ${r.i + 1} of ${r.items.length} · where does this flag fly? Click the map, then lock it in.</div>
    <div class="flagframe small">${flagImg(f, 'A flag to place on the map')}</div>
    <div class="pinmap" id="pinmap" aria-label="Map: click where this flag flies"></div>
    <div class="next-row"><button class="btn" id="lock" disabled>Lock it in</button></div>
    <div id="after"></div>
  </div>`;
  if (S.pinmap) { S.pinmap.remove(); S.pinmap = null; }
  if (!window.L) { $('#pinmap').innerHTML = '<div class="noimg">The map didn\'t load. Check your connection.</div>'; return; }
  const m = L.map('pinmap', { worldCopyJump: true, minZoom: 1 });
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png', {
    maxZoom: 18, subdomains: 'abcd',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(m);
  if (S.packId === 'world') m.setView([20, 10], 2); else m.fitBounds(packBounds(), { padding: [20, 20] });
  let mark = null;
  m.on('click', e => {
    if (r.answered) return;
    const ll = e.latlng.wrap();
    r.guess = { lat: ll.lat, lon: ll.lng };
    if (mark) mark.setLatLng(e.latlng); else mark = L.circleMarker(e.latlng, { radius: 7, color: '#2a4a6b', weight: 3, fillColor: '#6fa0cc', fillOpacity: 0.9 }).addTo(m);
    $('#lock').disabled = false;
  });
  S.pinmap = m;
  setTimeout(() => m.invalidateSize(), 60);
  $('#lock').onclick = () => lockPin(mark);
  status();
}
function lockPin(mark) {
  const r = S.round; if (r.answered || !r.guess) return;
  r.answered = true;
  const f = r.items[r.i], mi = Math.round(miles(r.guess, f));
  const pts = Math.round(1000 * Math.exp(-mi / (PIN_SCALE[f.kind] || 200)));
  r.score += pts; r.answers.push({ id: f.id, ok: pts >= 500, pts, mi });
  markSeen(f, pts >= 500);
  const m = S.pinmap, here = mark.getLatLng();
  // draw the answer on whichever copy of the world is nearest the guess
  const lon = f.lon + 360 * Math.round((here.lng - f.lon) / 360);
  L.polyline([here, [f.lat, lon]], { color: '#8b3a2a', weight: 2, dashArray: '6 6' }).addTo(m);
  L.circleMarker([f.lat, lon], { radius: 9, color: '#8b3a2a', weight: 3, fillColor: '#c8922a', fillOpacity: 0.95 }).bindTooltip(f.name, { permanent: true, direction: 'top', offset: [0, -8] }).addTo(m);
  m.fitBounds([here, [f.lat, lon]], { padding: [50, 50], maxZoom: ZOOM[f.kind] || 6 });
  const img = $('.flagframe img'); if (img) img.alt = 'Flag of ' + f.name;
  const last = r.i === r.items.length - 1;
  const words = mi < 1 ? 'Dead on!' : pts >= 900 ? 'Bullseye territory.' : pts >= 600 ? 'Close!' : pts >= 250 ? 'In the neighborhood.' : 'A long way off.';
  $('#lock').closest('.next-row').remove();
  $('#after').innerHTML = revealCard(f, { ok: pts >= 500, text: `📍 ${mi.toLocaleString()} mi off · +${pts.toLocaleString()} points · ${words}` }, true) +
    `<div class="next-row"><button class="btn" id="next">${last ? 'See how you did' : 'Next flag →'}</button></div>`;
  $('#next').onclick = () => nextFlag(last);
  $('#next').focus({ preventScroll: true });
  status();
}

function finish() {
  const r = S.round; r.over = true;
  const pin = r.mode === 'pin', max = pin ? ROUND * 1000 : ROUND;
  const best = store.get(bestKey(), null);
  const newBest = best === null || r.score > best;
  if (newBest) store.set(bestKey(), r.score);
  const frac = r.score / max;
  const line = frac === 1 ? 'A perfect round. You could design these.' : frac >= 0.8 ? 'You really know your flags.' : frac >= 0.5 ? 'Not bad at all, and now you know a few more.' : 'These are hard. Every round, you know a few more.';
  $('#main').innerHTML = `<div class="done">
    <div class="big">${pin ? `${r.score.toLocaleString()} <small>points</small>` : `${r.score} / ${r.items.length}`}</div>
    <div class="verdict-line">${line}${newBest && best !== null ? ' New best!' : ''}</div>
    <div class="recap">${r.items.map((f, i) => { const a = r.answers[i]; return `<button class="${a.ok ? 'r' : 'w'}" data-id="${f.id}">${flagImg(f, 'Flag of ' + f.name)}<span>${esc(f.name)}</span><small>${pin ? `${a.mi.toLocaleString()} mi · +${a.pts}` : `${a.ok ? '✓ ' : '✗ '}${esc(f.region)}`}</small></button>`; }).join('')}</div>
    <button class="btn" id="again">Another round</button>
    <button class="btn ghost" id="toAll">See all ${S.pack.flags.length.toLocaleString()} flags</button>
  </div>`;
  if (S.pinmap) { S.pinmap.remove(); S.pinmap = null; }
  $('#again').onclick = startRound;
  $('#toAll').onclick = () => show('browse');
  $('#main').querySelectorAll('.recap button').forEach(b => b.onclick = () => openFlag(b.dataset.id));
  S.round = null;
  status();
}

/* ---------- all flags ---------- */
function renderBrowse() {
  const p = S.pack;
  const group = f => isTop(f) && f.kind !== 'country' ? KIND[f.kind] : f.region;
  const counts = {};
  p.flags.forEach(f => counts[group(f)] = (counts[group(f)] || 0) + 1);
  const groups = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (S.filter !== 'all' && !counts[S.filter]) S.filter = 'all';
  const q = S.q.trim().toLowerCase();
  const list = p.flags.filter(f => (S.filter === 'all' || group(f) === S.filter) && (!q || (f.name + ' ' + f.region).toLowerCase().includes(q)));
  $('#main').innerHTML = `<div class="picker-row">
      <select id="packSel" aria-label="Set of flags">${S.packs.map(k => `<option value="${k.id}"${k.id === S.packId ? ' selected' : ''}>${esc(k.name)}${k.count ? ` (${k.count.toLocaleString()})` : ''}</option>`).join('')}</select>
      ${groups.length > 1 ? `<select id="grpSel" aria-label="Filter"><option value="all">All (${p.flags.length.toLocaleString()})</option>${groups.map(([k, n]) => `<option value="${esc(k)}"${S.filter === k ? ' selected' : ''}>${esc(k)} (${n})</option>`).join('')}</select>` : ''}
      <input id="q" type="search" placeholder="Search ${esc(p.name)}" value="${esc(S.q)}" aria-label="Search flags" autocomplete="off">
    </div>
    <div class="grid">${list.slice(0, S.shown).map(f => {
      const s = S.seen[f.id];
      return `<button class="tile" data-id="${f.id}"><div class="fw">${flagImg(f, 'Flag of ' + f.name)}</div><span>${esc(f.name)}</span><small>${esc(sub(f))}${s && s.r ? ' · <b class="got">✓ known</b>' : ''}${f.named ? ' · name on flag' : ''}</small></button>`;
    }).join('') || '<div class="empty">No flags match.</div>'}</div>
    ${list.length > S.shown ? `<div class="next-row" style="padding-bottom:18px"><button class="btn ghost" id="more">Show more (${(list.length - S.shown).toLocaleString()} left)</button></div>` : ''}`;
  $('#packSel').onchange = async e => { S.filter = 'all'; S.q = ''; S.shown = 120; await loadPack(e.target.value); renderBrowse(); };
  if ($('#grpSel')) $('#grpSel').onchange = e => { S.filter = e.target.value; S.shown = 120; renderBrowse(); };
  const qi = $('#q'); let t;
  qi.oninput = () => { clearTimeout(t); t = setTimeout(() => { S.q = qi.value; S.shown = 120; renderBrowse(); const n = $('#q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 200); };
  if ($('#more')) $('#more').onclick = () => { S.shown += 240; renderBrowse(); };
  $('#main').querySelectorAll('.tile').forEach(b => b.onclick = () => openFlag(b.dataset.id));
  status();
}

/* ---------- Flag of the Day ---------- */
const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
function miles(a, b) {
  const R = 3958.8, rad = x => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}
function arrow(a, b) {
  const rad = x => x * Math.PI / 180, deg = x => x * 180 / Math.PI;
  const y = Math.sin(rad(b.lon - a.lon)) * Math.cos(rad(b.lat));
  const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat)) - Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(rad(b.lon - a.lon));
  const brg = (deg(Math.atan2(y, x)) + 360) % 360;
  return ['⬆️', '↗️', '➡️', '↘️', '⬇️', '↙️', '⬅️', '↖️'][Math.round(brg / 45) % 8];
}

async function renderToday() {
  $('#main').innerHTML = '<div class="empty"><b>🗓️</b>Raising today\'s flag&hellip;</div>';
  status();
  let daily, places;
  try { [daily, places] = await Promise.all([loadFile('data/daily.json'), loadFile('data/places.json')]); } catch (e) { daily = null; }
  const key = todayKey(), entry = daily && daily.days[key];
  if (!entry) {
    $('#main').innerHTML = `<div class="empty"><b>🗓️</b>Today's flag is still on its way up the pole. The robot schedules them every hour, so check back soon, or play a round in the meantime.</div>`;
    return;
  }
  const pack = await loadFile(S.packs.find(k => k.id === entry.pack)?.file || `data/${entry.pack}.json`);
  const f = pack.flags.find(x => x.id === entry.id);
  const num = Math.round((Date.parse(key) - Date.parse(daily.start)) / 864e5) + 1;
  const cat = CATS[entry.cat] || CATS.country;
  const pool = places.filter(p => cat.packs.includes(p[6])).map(p => ({ id: p[0], name: p[1], region: p[2], kind: p[3], lat: p[4], lon: p[5] }));
  const st = store.get('fa_daily_' + key, { guesses: [], done: false, won: false });

  const draw = () => {
    const rows = st.guesses.map(id => {
      const g = pool.find(p => p.id === id) || { name: id, lat: f.lat, lon: f.lon, region: '' };
      if (id === f.id) return `<li class="g win"><span>${esc(g.name)}</span><b>🎯 That's it!</b></li>`;
      const mi = Math.round(miles(g, f));
      return `<li class="g"><span>${esc(g.name)}<small>${esc(sub(g))}</small></span><b>${mi.toLocaleString()} mi ${arrow(g, f)}</b></li>`;
    }).join('');
    const left = TRIES - st.guesses.length;
    $('#main').innerHTML = `<div class="q daily">
      <div class="q-label">Flag of the Day #${num} · today it's ${esc(cat.label)}</div>
      <div class="flagframe">${flagImg(f, st.done ? 'Flag of ' + f.name : 'Today\'s flag')}</div>
      ${st.done ? '' : `<div class="guessbox">
        <input id="guess" type="text" placeholder="Type a place…" autocomplete="off" aria-label="Your guess" aria-autocomplete="list" aria-controls="sugg">
        <ul id="sugg" class="sugg" role="listbox"></ul>
        <div class="tries">${left} ${left === 1 ? 'try' : 'tries'} left · each miss tells you how far, and which way</div>
      </div>`}
      <ol class="guesses">${rows}</ol>
      <div id="after"></div>
    </div>`;
    if (st.done) {
      const text = st.won ? `✓ Solved in ${st.guesses.length} of ${TRIES}` : `✗ Out of tries. It was ${f.name}.`;
      $('#after').innerHTML = revealCard(f, { ok: st.won, text }) +
        `<div class="next-row"><button class="btn" id="share">Share your result</button><button class="btn ghost" id="toPlay">Play a round</button></div>
         <p class="tomorrow">A new flag every day at midnight, your time.</p>`;
      drawMap(f, st.guesses.filter(id => id !== f.id).map(id => pool.find(p => p.id === id)).filter(Boolean));
      $('#share').onclick = () => share(num, cat, st, pool, f);
      $('#toPlay').onclick = () => show('play');
      return;
    }
    const inp = $('#guess'), ul = $('#sugg');
    let hits = [], sel = 0;
    const paint = () => { ul.innerHTML = hits.map((p, i) => `<li role="option" data-i="${i}" aria-selected="${i === sel}">${esc(p.name)}<small>${esc(sub(p))}</small></li>`).join(''); ul.querySelectorAll('li').forEach(li => li.onmousedown = e => { e.preventDefault(); guess(hits[+li.dataset.i]); }); };
    inp.oninput = () => {
      const q = inp.value.trim().toLowerCase(); sel = 0;
      if (!q) { hits = []; paint(); return; }
      const starts = pool.filter(p => p.name.toLowerCase().startsWith(q)), has = pool.filter(p => !p.name.toLowerCase().startsWith(q) && (p.name + ' ' + p.region).toLowerCase().includes(q));
      hits = [...starts, ...has].filter(p => !st.guesses.includes(p.id)).slice(0, 8); paint();
    };
    inp.onkeydown = e => {
      if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, hits.length - 1); paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); paint(); e.preventDefault(); }
      else if (e.key === 'Enter' && hits[sel]) { guess(hits[sel]); e.preventDefault(); }
    };
    inp.focus({ preventScroll: true });
  };
  const guess = p => {
    if (st.done || st.guesses.includes(p.id)) return;
    st.guesses.push(p.id);
    if (p.id === f.id || st.guesses.length >= TRIES) {
      st.done = true; st.won = p.id === f.id;
      const s = store.get('fa_daily_stats', { played: 0, won: 0, streak: 0, best: 0, last: null });
      const yesterday = (() => { const d = new Date(Date.parse(key) - 864e5); return d.toISOString().slice(0, 10); })();
      s.played++; if (st.won) { s.won++; s.streak = s.last === yesterday ? s.streak + 1 : 1; s.best = Math.max(s.best, s.streak); } else s.streak = 0;
      s.last = st.won ? key : s.last; store.set('fa_daily_stats', s);
      const seen = S.seen[f.id] || { r: 0, w: 0 }; st.won ? seen.r++ : seen.w++; S.seen[f.id] = seen; store.set('fa_seen', S.seen);
    }
    store.set('fa_daily_' + key, st);
    draw(); status();
  };
  draw();
}

function share(num, cat, st, pool, f) {
  const lines = st.guesses.map(id => id === f.id ? '🎯' : (() => { const g = pool.find(p => p.id === id); return g ? `${arrow(g, f)} ${Math.round(miles(g, f)).toLocaleString()} mi` : '❔'; })());
  const text = `Flag Atlas #${num} 🏳️ ${st.won ? st.guesses.length : 'X'}/${TRIES}\n${lines.join('\n')}\nhttps://brooksgroves.com/flags/`;
  if (navigator.share) { navigator.share({ text }).catch(() => {}); return; }
  navigator.clipboard?.writeText(text).then(() => { const b = $('#share'); if (b) { b.textContent = 'Copied! Paste it anywhere'; } });
}

/* ---------- drawer ---------- */
function openSheet(html) {
  $('#drawerInner').innerHTML = html;
  $('#overlay').classList.add('open'); $('#drawer').classList.add('open');
  $('#drawerX').focus({ preventScroll: true });
}
function closeDrawer() {
  $('#overlay').classList.remove('open'); $('#drawer').classList.remove('open');
  if (S.map && $('#drawer #minimap')) { S.map.remove(); S.map = null; }
}
function openFlag(id) {
  const f = S.pack.flags.find(x => x.id === id); if (!f) return;
  openSheet(`<div class="bigflag">${flagImg(f, 'Flag of ' + f.name)}</div>${revealCard(f)}`);
  setTimeout(() => drawMap(f), 260);   // after the drawer slides up, so Leaflet measures the right size
}
function openAbout() {
  openSheet(`<div class="about-page">
    <h3>Flag of the Day</h3>
    <p>One flag a day, the same for everyone. Type your guess; each miss tells you how many miles off you are and which way to look. You get ${TRIES} tries. Mondays and Thursdays it's a country, Tuesdays a US state, Canadian province or Mexican state, Wednesdays and Saturdays a region somewhere in the world, Fridays a city, and Sundays a flag from the Pacific Northwest.</p>
    <h3>Rounds</h3>
    <p>Pick a set and you'll see ${ROUND} flags with four choices each. Rounds lean toward flags you haven't got right yet, so you keep meeting new ones. Keys 1 to 4 pick an answer and Enter goes to the next flag. Flags with the place's name written on them sit out the rounds, but you'll find them under All flags.</p>
    <h3>Where the flags come from</h3>
    <ul>
      <li>Flag pictures: <a href="https://commons.wikimedia.org/" target="_blank" rel="noopener">Wikimedia Commons</a>. Each flag's card credits its artist and license.</li>
      <li>Places, locations and populations: <a href="https://www.wikidata.org/" target="_blank" rel="noopener">Wikidata</a>.</li>
      <li>Flag stories: the opening of Wikipedia's article on each flag (CC BY-SA 4.0), or for the Pacific Northwest set, written for this game.</li>
      <li>Maps: &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors.</li>
      <li>A robot refreshes all of it from those sources every week, and fetches new pictures every hour.</li>
    </ul>
    <h3>Your progress</h3>
    <p>Kept on this device only. No account, no ads.</p>
    <p style="margin-top:10px"><button class="btn ghost" id="resetBtn">Forget my progress</button></p>
  </div>`);
  $('#resetBtn').onclick = () => {
    try { Object.keys(localStorage).filter(k => k.startsWith('fa_')).forEach(k => localStorage.removeItem(k)); } catch (e) { /* ignore */ }
    S.seen = {}; closeDrawer(); show(S.view);
  };
}

/* ---------- views ---------- */
async function show(view) {
  S.view = view; store.set('fa_view', view);
  document.querySelectorAll('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.view === view));
  if (S.map) { S.map.remove(); S.map = null; }
  if (S.pinmap) { S.pinmap.remove(); S.pinmap = null; }
  if (view === 'today') return renderToday();
  if (view === 'browse') { S.round = null; renderBrowse(); }
  else if (S.round && !S.round.over) renderQuestion();
  else renderStart();
}

async function loadPack(id) {
  const k = S.packs.find(p => p.id === id) || S.packs[0];
  S.pack = await loadFile(k.file); S.packId = k.id; store.set('fa_pack', k.id);
  status();
}

document.addEventListener('keydown', e => {
  if ($('#drawer').classList.contains('open')) { if (e.key === 'Escape') closeDrawer(); return; }
  if (S.view !== 'play' || !S.round) return;
  if (!S.round.answered && S.round.mode === 'pin') { if (e.key === 'Enter' && $('#lock') && !$('#lock').disabled) $('#lock').click(); }
  else if (!S.round.answered && /^[1-4]$/.test(e.key)) { const b = $(`.choice[data-k="${+e.key - 1}"]`); if (b) b.click(); }
  else if (S.round.answered && e.key === 'Enter' && $('#next') && document.activeElement !== $('#next')) $('#next').click();
});

(async function init() {
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => show(t.dataset.view));
  $('#aboutBtn').onclick = openAbout;
  $('#overlay').onclick = closeDrawer;
  $('#drawerX').onclick = closeDrawer;
  $('#theme-toggle').onclick = () => {
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (dark) document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', 'dark');
    try { localStorage.setItem('bg_theme', dark ? 'light' : 'dark'); } catch (e) { /* ignore */ }
  };
  try { const m = await getJSON('data/packs.json'); if (m.packs && m.packs.length) S.packs = m.packs; } catch (e) { /* robot hasn't built yet: the Northwest set */ }
  try { await loadPack(S.packId); await show(['today', 'play', 'browse'].includes(S.view) ? S.view : 'today'); }
  catch (e) { $('#main').innerHTML = '<div class="empty"><b>🏳️</b>The flags didn\'t load. Check your connection and refresh.</div>'; }
})();
