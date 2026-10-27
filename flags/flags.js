/* Flag Atlas: guess the flag, find the place, learn the story.
   Packs live in data/<pack>.json (built from Wikidata and Wikimedia Commons); pictures in img/. */
'use strict';

const PACKS = [
  { id: 'pnw', name: 'Pacific Northwest', blurb: 'States, provinces, cities and counties', file: 'data/pnw.json' },
  { id: 'us', name: 'US states', blurb: 'Coming soon', soon: true },
  { id: 'world', name: 'Countries', blurb: 'Coming soon', soon: true },
];
const ROUND = 10;
const KIND = { state: 'US state', province: 'Canadian province', region: 'Region', city: 'City', county: 'County' };
const ZOOM = { state: 4, province: 4, region: 6, county: 8, city: 9 };

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window: play on without saving */ } },
};
const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

const S = {
  view: 'play', pack: null, packId: store.get('fa_pack', 'pnw'),
  round: null,                       // { items, i, score, answers: [{id, ok}] , answered }
  seen: store.get('fa_seen', {}),    // id -> { r: right count, w: wrong count }
  filter: 'all', map: null,
};

/* ---------- small helpers ---------- */
const where = f => f.kind === 'state' || f.kind === 'province' ? KIND[f.kind] : f.region;
const sub = f => (f.kind === 'state' || f.kind === 'province') ? KIND[f.kind] : `${KIND[f.kind]} · ${f.region}`;
function aboutLine(f) {
  let s = f.about.charAt(0).toUpperCase() + f.about.slice(1);
  if ((f.kind === 'city' || f.kind === 'county') && !s.includes(f.region)) s += `, ${f.region}`;
  if (f.pop) s += ` · pop. ${f.pop.toLocaleString()}`;
  return s;
}
function flagImg(f, alt) {
  return `<img src="${esc(f.img)}" alt="${esc(alt)}" decoding="async" onerror="this.outerHTML='<div class=&quot;noimg&quot;>Picture on its way</div>'">`;
}
function credit(f) {
  const c = f.credit, lic = c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.license)}</a>` : esc(c.license);
  return `Flag image: ${c.artist ? esc(c.artist) + ', ' : ''}${lic}, via <a href="${esc(c.page)}" target="_blank" rel="noopener">Wikimedia Commons</a>. Place facts: Wikidata.`;
}
function revealCard(f, verdict) {
  return `<div class="reveal">
    <div class="txt">
      ${verdict ? `<div class="verdict ${verdict.ok ? 'right' : 'wrong'}">${verdict.ok ? '✓ Right' : '✗ Not quite'}${verdict.ok ? '' : `: you picked ${esc(verdict.picked)}`}</div>` : ''}
      <div class="place">${esc(f.name)}</div>
      <div class="about">${esc(aboutLine(f))}</div>
      ${f.note ? `<p class="note">${esc(f.note)}</p>` : ''}
      <a class="more" href="${esc(f.wiki)}" target="_blank" rel="noopener">More about ${esc(f.name)} →</a>
      <p class="credit">${credit(f)}</p>
    </div>
    <div class="minimap" id="minimap" aria-label="Map showing ${esc(f.name)}"></div>
  </div>`;
}
function drawMap(f) {
  const el = $('#minimap'); if (!el || !window.L) return;
  if (S.map) { S.map.remove(); S.map = null; }
  const m = L.map(el, { scrollWheelZoom: false, attributionControl: true }).setView([f.lat, f.lon], ZOOM[f.kind] || 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(m);
  L.circleMarker([f.lat, f.lon], { radius: 8, color: '#8b3a2a', weight: 3, fillColor: '#c8922a', fillOpacity: 0.9 }).addTo(m);
  S.map = m;
  setTimeout(() => m.invalidateSize(), 60);
}

/* ---------- status bar ---------- */
function status() {
  const p = S.pack, r = S.round, best = store.get('fa_best_' + S.packId, null);
  const playable = p ? p.flags.filter(f => !f.named) : [];
  const known = playable.filter(f => (S.seen[f.id] || {}).r).length;
  $('#statusbar').innerHTML = r && !r.over
    ? `<span>Flag <b>${Math.min(r.i + 1, r.items.length)}/${r.items.length}</b></span><span>Score <b>${r.score}</b></span><span>Streak <b>${r.streak}</b></span>${best !== null ? `<span>Best <b>${best}/${ROUND}</b></span>` : ''}`
    : `<span>Flags you know <b>${known}/${playable.length}</b></span>${best !== null ? `<span>Best round <b>${best}/${ROUND}</b></span>` : ''}`;
}

/* ---------- play ---------- */
function renderStart() {
  const p = S.pack, best = store.get('fa_best_' + S.packId, null);
  const peek = shuffle(p.flags).slice(0, 5);
  $('#main').innerHTML = `<div class="start">
    <h2>Whose flag is it?</h2>
    <p>You'll see ${ROUND} flags. Pick the place that flies each one, then see where it is on the map and the story behind the design. State flags are the warm-up; city and county flags are where it gets good.</p>
    <div class="peek" aria-hidden="true">${peek.map((f, i) => `<img src="${esc(f.img)}" alt="" style="--t:${[-4, 3, -2, 4, -3][i]}deg" onerror="this.remove()">`).join('')}</div>
    <div class="packs" role="group" aria-label="Pick a set of flags">
      ${PACKS.map(k => `<button class="pack" data-pack="${k.id}" aria-pressed="${k.id === S.packId}" ${k.soon ? 'disabled' : ''}><b>${esc(k.name)}</b><small>${esc(k.soon ? k.blurb : `${p && k.id === p.id ? p.flags.length : ''} flags · ${k.blurb}`)}</small></button>`).join('')}
    </div>
    <button class="btn" id="go">Start a round</button>
    ${best !== null ? `<div class="best">Your best: ${best} of ${ROUND}</div>` : ''}
  </div>`;
  $('#go').onclick = startRound;
  status();
}

function startRound() {
  const flags = S.pack.flags.filter(f => !f.named);   // a flag with its own name on it would be a giveaway
  // favor flags you haven't got right yet, so rounds keep teaching you new ones
  const fresh = shuffle(flags.filter(f => !(S.seen[f.id] || {}).r)), known = shuffle(flags.filter(f => (S.seen[f.id] || {}).r));
  const items = [...fresh, ...known].slice(0, ROUND);
  S.round = { items: shuffle(items), i: 0, score: 0, streak: 0, answers: [], over: false };
  renderQuestion();
}

function choicesFor(f) {
  const pool = S.pack.flags.filter(x => x.id !== f.id);
  const same = shuffle(pool.filter(x => x.kind === f.kind || (f.kind === 'state' && x.kind === 'province') || (f.kind === 'province' && x.kind === 'state')));
  const rest = shuffle(pool.filter(x => !same.includes(x)));
  return shuffle([f, ...[...same, ...rest].slice(0, 3)]);
}

function renderQuestion() {
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
  const s = S.seen[f.id] || { r: 0, w: 0 }; ok ? s.r++ : s.w++; S.seen[f.id] = s; store.set('fa_seen', S.seen);
  $('#main').querySelectorAll('.choice').forEach((b, i) => {
    b.disabled = true;
    if (r.opts[i].id === f.id) b.classList.add('right');
    else if (i === k) b.classList.add('wrong');
    else b.classList.add('dim');
  });
  const img = $('.flagframe img'); if (img) img.alt = 'Flag of ' + f.name;
  const last = r.i === r.items.length - 1;
  $('#after').innerHTML = revealCard(f, { ok, picked: pick.name + (pick.name === f.name ? ` (${where(pick)})` : '') }) +
    `<div class="next-row"><button class="btn" id="next">${last ? 'See how you did' : 'Next flag →'}</button></div>`;
  drawMap(f);
  $('#next').onclick = () => { if (last) finish(); else { r.i++; renderQuestion(); scrollTo({ top: $('.console').offsetTop - 10, behavior: 'smooth' }); } };
  $('#next').focus({ preventScroll: true });
  status();
}

function finish() {
  const r = S.round; r.over = true;
  const best = store.get('fa_best_' + S.packId, null);
  const newBest = best === null || r.score > best;
  if (newBest) store.set('fa_best_' + S.packId, r.score);
  const line = r.score === ROUND ? 'A perfect round. You could design these.' : r.score >= 8 ? 'You know your Northwest.' : r.score >= 5 ? 'Not bad at all, and now you know a few more.' : 'City flags are hard. Every round, you know a few more.';
  $('#main').innerHTML = `<div class="done">
    <div class="big">${r.score} / ${r.items.length}</div>
    <div class="verdict-line">${line}${newBest && best !== null ? ' New best!' : ''}</div>
    <div class="recap">${r.items.map((f, i) => `<button class="${r.answers[i].ok ? 'r' : 'w'}" data-id="${f.id}">${flagImg(f, 'Flag of ' + f.name)}<span>${esc(f.name)}</span><small>${r.answers[i].ok ? '✓ ' : '✗ '}${esc(where(f))}</small></button>`).join('')}</div>
    <button class="btn" id="again">Another round</button>
    <button class="btn ghost" id="toAll">See all ${S.pack.flags.length} flags</button>
  </div>`;
  $('#again').onclick = startRound;
  $('#toAll').onclick = () => show('browse');
  $('#main').querySelectorAll('.recap button').forEach(b => b.onclick = () => openFlag(b.dataset.id));
  S.round = null;
  status();
}

/* ---------- all flags ---------- */
function renderBrowse() {
  const p = S.pack, counts = {};
  const group = f => f.kind === 'state' || f.kind === 'province' ? 'States & provinces' : f.region;
  p.flags.forEach(f => counts[group(f)] = (counts[group(f)] || 0) + 1);
  const groups = [['all', 'All', p.flags.length], ...Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, k, n])];
  if (!groups.some(([k]) => k === S.filter)) S.filter = 'all';
  const list = p.flags.filter(f => S.filter === 'all' || group(f) === S.filter);
  $('#main').innerHTML = `<div class="fb" role="group" aria-label="Filter">${groups.map(([k, label, n]) => `<button class="ch" data-f="${esc(k)}" aria-pressed="${S.filter === k}">${esc(label)}<span class="n">${n}</span></button>`).join('')}</div>
    <div class="grid">${list.map(f => {
      const s = S.seen[f.id];
      return `<button class="tile" data-id="${f.id}"><div class="fw">${flagImg(f, 'Flag of ' + f.name)}</div><span>${esc(f.name)}</span><small>${esc(sub(f))}${s && s.r ? ' · <b class="got">✓ known</b>' : ''}${f.named ? ' · name on flag' : ''}</small></button>`;
    }).join('')}</div>`;
  $('#main').querySelectorAll('.ch').forEach(b => b.onclick = () => { S.filter = b.dataset.f; renderBrowse(); });
  $('#main').querySelectorAll('.tile').forEach(b => b.onclick = () => openFlag(b.dataset.id));
  status();
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
    <h3>How to play</h3>
    <p>Each round shows ${ROUND} flags. Pick the place that flies it. Flags with the place's name written right on them sit out the rounds, but you'll find them under All flags. Right or wrong, you'll see where it is and, where we know it, the story behind the design. Rounds lean toward flags you haven't got right yet, so you keep meeting new ones. Keys 1 to 4 pick an answer and Enter goes to the next flag.</p>
    <h3>Where the flags come from</h3>
    <ul>
      <li>Flag pictures: <a href="https://commons.wikimedia.org/" target="_blank" rel="noopener">Wikimedia Commons</a>. Each flag's card credits its artist and license.</li>
      <li>Places, locations and populations: <a href="https://www.wikidata.org/" target="_blank" rel="noopener">Wikidata</a>.</li>
      <li>Flag stories: written for this game from Wikipedia's articles on each flag.</li>
      <li>Maps: &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors.</li>
    </ul>
    <h3>Your progress</h3>
    <p>Kept on this device only. No account, no ads.</p>
    <p style="margin-top:10px"><button class="btn ghost" id="resetBtn">Forget my progress</button></p>
  </div>`);
  $('#resetBtn').onclick = () => {
    S.seen = {}; store.set('fa_seen', {}); PACKS.forEach(k => { try { localStorage.removeItem('fa_best_' + k.id); } catch (e) { /* ignore */ } });
    closeDrawer(); show(S.view);
  };
}

/* ---------- views ---------- */
function show(view) {
  S.view = view;
  document.querySelectorAll('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.view === view));
  if (S.map) { S.map.remove(); S.map = null; }
  if (view === 'browse') { S.round = null; renderBrowse(); }
  else if (S.round && !S.round.over) renderQuestion();
  else renderStart();
}

async function loadPack(id) {
  const k = PACKS.find(p => p.id === id && !p.soon) || PACKS[0];
  const r = await fetch(k.file, { cache: 'no-cache' });
  S.pack = await r.json(); S.packId = k.id; store.set('fa_pack', k.id);
  $('#badge').textContent = S.pack.name;
}

document.addEventListener('keydown', e => {
  if ($('#drawer').classList.contains('open')) { if (e.key === 'Escape') closeDrawer(); return; }
  if (S.view !== 'play' || !S.round) return;
  if (!S.round.answered && /^[1-4]$/.test(e.key)) { const b = $(`.choice[data-k="${+e.key - 1}"]`); if (b) b.click(); }
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
  try { await loadPack(S.packId); show('play'); }
  catch (e) { $('#main').innerHTML = '<div class="empty"><b>🏳️</b>The flags didn\'t load. Check your connection and refresh.</div>'; }
})();
