#!/usr/bin/env node
/* ============================================================
   audit-dice.js — standing audit for every skill check in
   /games/. Run it after touching any DC, die, or stat modifier.

     node tools/audit-dice.js
     node tools/audit-dice.js --verbose

   It boots each game headlessly, enumerates every character
   build, and reports any check that is:

     IMPOSSIBLE  the best possible roll cannot reach the DC
     AUTOPASS    the worst possible roll cannot fail
     BRUTAL      only one face on the die succeeds
     CERTAIN     only one face fails

   IMPOSSIBLE and AUTOPASS are bugs. A button that cannot
   succeed is a lie, and a roll that cannot fail is a wasted
   animation. The other two are judgement calls.
   ============================================================ */

const fs = require('fs');
const path = require('path');

let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = require('jsdom'));
} catch (e) {
  console.error('This tool needs jsdom:  npm install --no-save jsdom');
  process.exit(2);
}

const VERBOSE = process.argv.includes('--verbose');
const GAMES_DIR = fs.existsSync('games') ? 'games'
                : fs.existsSync('../games') ? '../games'
                : '.';

/* ---------- which files to audit ---------- */
const MODULES = fs.readdirSync(GAMES_DIR)
  .filter(f => f.endsWith('.html'))
  .filter(f => !/^reference\.html$/.test(f))
  .map(f => path.join(GAMES_DIR, f));

/* ---------- boot a game with the engine inlined ---------- */
function boot(file) {
  let html = fs.readFileSync(file, 'utf8');
  if (!/Engine\.init\(/.test(html)) return null;      // not a game module

  const enginePath = path.join(GAMES_DIR, 'engine.js');
  const engine = fs.readFileSync(enginePath, 'utf8');
  html = html
    .replace(/<script src="[^"]*engine\.js"><\/script>/, '<script>' + engine + '</script>')
    .replace(/<script src="https?:[^"]*"><\/script>/g, '')   // leaflet etc
    .replace(/<link rel="stylesheet"[^>]*>/g, '');

  const vc = new VirtualConsole();
  const errs = [];
  vc.on('jsdomError', e => {
    if (!/Could not parse CSS/.test(String(e))) errs.push(String(e).slice(0, 140));
  });

  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
    url: 'https://brooksgroves.com/games/audit.html',
    beforeParse(w) {
      w.AudioContext = undefined;
      w.webkitAudioContext = undefined;
      w.confirm = () => true;
      w.onerror = m => errs.push('onerror: ' + m);
      // minimal Leaflet so map modules build their panel without throwing
      const chain = () => {
        const o = { addTo:()=>o, setStyle:()=>o, bindPopup:()=>o, on:()=>o,
                    setLatLng:()=>o, setView:()=>o, panTo:()=>o, remove:()=>o };
        return o;
      };
      w.L = { map: chain, tileLayer: chain, polyline: chain, circleMarker: chain };
    }
  });
  return { dom, errs };
}

/* ---------- find every check site in the source ---------- */
function findChecks(src) {
  const out = [];

  // Engine.check({die:12, mod:mod('FIELDCRAFT'), dc:DC.scene, label:'...'}
  const re = /Engine\.check\(\{\s*die:\s*(\d+)\s*,\s*mod:\s*(?:mod|statMod)\(\s*'(\w+)'\s*\)\s*,\s*dc:\s*([\w.$\[\]']+)\s*(?:,\s*label:\s*'([^']*)')?/g;
  let m;
  while ((m = re.exec(src))) {
    out.push({ die: +m[1], stat: m[2], dcExpr: m[3], label: m[4] || '(unlabelled)' });
  }

  // odds(12,'FIELDCRAFT',DC.x)  /  dcTag(8,'SOCIAL',DC.y) — button previews
  const re2 = /(?:odds|dcTag)\(\s*(\d+)\s*,\s*'(\w+)'\s*,\s*([\w.]+)\s*\)/g;
  while ((m = re2.exec(src))) {
    out.push({ die: +m[1], stat: m[2], dcExpr: m[3], label: '(button preview)', preview: true });
  }
  return out;
}

/* ---------- enumerate character builds ---------- */
function buildsFor(W) {
  // Every module names its build table differently; try each.
  const tables = ['KITS', 'LOADOUTS', 'METHODS', 'RACES'];
  for (const t of tables) {
    let obj;
    try { obj = W.eval('typeof ' + t + ' !== "undefined" ? ' + t + ' : null'); } catch (e) { obj = null; }
    if (obj && Object.keys(obj).length) return { name: t, keys: Object.keys(obj) };
  }
  return null;
}

/* Apply a build and read back the resulting stat modifiers. */
function statsForBuild(W, table, key) {
  try {
    return W.eval(`(function(){
      var base = {}, T = ${table}[${JSON.stringify(key)}];
      var names = Object.keys(player && player.stats ? player.stats : {});
      names.forEach(function(n){ base[n] = 1; });
      var mods = T.mods || {};
      Object.keys(mods).forEach(function(k){ base[k] = (base[k]||1) + mods[k]; });
      return base;
    })()`);
  } catch (e) { return null; }
}

/* Resolve a DC expression, accounting for per-run jitter. */
function resolveDC(W, expr, src) {
  // a DC read off a per-run record, e.g. F.dc from the FAULTS table
  if (/^[A-Z]\.\w+$/.test(expr)) {
    const field = expr.split('.')[1];
    // Only look inside record literals that also declare `fixable`,
    // so we don't scoop up a `dc:` from an unrelated Engine.check call.
    const vals = [];
    const recRe = /\{[^{}]*fixable\s*:[^{}]*\}/g;
    let rm;
    while ((rm = recRe.exec(src))) {
      const fm = new RegExp('\\b' + field + '\\s*:\\s*(\\d+)').exec(rm[0]);
      if (fm) vals.push(+fm[1]);
    }
    const real = vals.filter(v => v < 90);          // 99 means "not fixable here"
    if (real.length) return { base: Math.max(...real), spread: 0 };
    return null;
  }

  let val;
  try { val = W.eval(expr); } catch (e) { val = null; }
  if (typeof val !== 'number') {
    const lit = Number(expr);
    if (!Number.isNaN(lit)) val = lit; else return null;
  }

  // find the jitter spread for this key so we can test the worst case
  const key = expr.replace(/^DC\./, '');
  const jm = new RegExp(key + '\\s*:\\s*(?:Engine\\.)?jitter\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)').exec(src);
  if (jm) return { base: +jm[1], spread: +jm[2] };
  return { base: val, spread: 0 };
}

/* ---------- the audit ---------- */
const findings = [];
let checkedCount = 0, moduleCount = 0;

for (const file of MODULES) {
  const src = fs.readFileSync(file, 'utf8');
  const checks = findChecks(src);
  const maybePercentile = /function statTarget\(/.test(src);
  if (!checks.length && !maybePercentile) continue;

  const booted = boot(file);
  if (!booted) continue;
  const W = booted.dom.window;
  moduleCount++;

  const builds = buildsFor(W);
  const name = path.basename(file);

  if (!builds) {
    findings.push({ file: name, level: 'NOTE', msg: 'could not find a character build table; skipped' });
    booted.dom.window.close();
    continue;
  }

  // dedupe: the same check often appears as both a preview and a real call
  const seen = new Set();
  for (const c of checks) {
    const sig = c.die + '|' + c.stat + '|' + c.dcExpr;
    if (seen.has(sig)) continue;
    seen.add(sig);

    const dc = resolveDC(W, c.dcExpr, src);
    if (!dc) {
      findings.push({ file: name, level: 'NOTE',
        msg: `could not resolve DC "${c.dcExpr}" for ${c.label}` });
      continue;
    }
    checkedCount++;

    const hardest = dc.base + dc.spread;   // worst roll of the jitter
    const easiest = dc.base - dc.spread;

    for (const key of builds.keys) {
      const stats = statsForBuild(W, builds.name, key);
      if (!stats || stats[c.stat] === undefined) continue;
      const mod = stats[c.stat];

      const bestTotal  = c.die + mod;
      const worstTotal = 1 + mod;

      let level = null, msg = null;
      if (bestTotal < hardest) {
        level = 'IMPOSSIBLE';
        msg = `${c.label}: d${c.die}${mod>=0?'+':''}${mod} tops out at ${bestTotal}, needs ${hardest}`;
      } else if (worstTotal >= easiest) {
        level = 'AUTOPASS';
        msg = `${c.label}: d${c.die}${mod>=0?'+':''}${mod} cannot roll below ${worstTotal}, needs only ${easiest}`;
      } else if (bestTotal === hardest) {
        level = 'BRUTAL';
        msg = `${c.label}: only a natural ${c.die} passes at DC ${hardest}`;
      } else if (worstTotal === easiest - 1) {
        level = 'CERTAIN';
        msg = `${c.label}: only a natural 1 fails at DC ${easiest}`;
      }
      if (level) findings.push({ file: name, build: key, level, msg });
    }
  }

  // percentile modules: sanity-check target numbers instead
  try {
    const isUnder = W.eval('typeof statTarget === "function"');
    if (isUnder) {
      const probe = W.eval(`(function(){
        var out = [];
        var races = Object.keys(RACES), skills = ['military','technological','biosocial'];
        races.forEach(function(r){
          skills.forEach(function(s){
            player.race = r; player.skill = s;
            player.stats = {STR:30,STA:30,DEX:30,RS:30,INT:30,LOG:30,PER:30,LDR:30};
            var lo = statTarget('DEX', {});
            player.stats = {STR:90,STA:90,DEX:90,RS:90,INT:90,LOG:90,PER:90,LDR:90};
            var hi = statTarget('DEX', {skillBonus:s, gear:true});
            out.push({race:r, skill:s, lo:lo, hi:hi});
          });
        });
        return out;
      })()`);
      const worst = Math.min(...probe.map(p => p.lo));
      const best  = Math.max(...probe.map(p => p.hi));
      if (worst < 10) findings.push({ file: name, level: 'BRUTAL',
        msg: `percentile targets can fall to ${worst}% (weakest build, worst run drift)` });
      if (best > 95) findings.push({ file: name, level: 'CERTAIN',
        msg: `percentile targets can reach ${best}% (strongest build)` });
      if (VERBOSE) console.log(`  [${name}] percentile target range across builds: ${worst}%–${best}%`);
      checkedCount++;
    }
  } catch (e) { /* not a percentile module */ }

  if (booted.errs.length) {
    findings.push({ file: name, level: 'NOTE',
      msg: `${booted.errs.length} runtime error(s) on load: ${booted.errs[0]}` });
  }
  booted.dom.window.close();
}

/* ---------- report ---------- */
const RANK = { IMPOSSIBLE: 0, AUTOPASS: 1, BRUTAL: 2, CERTAIN: 3, NOTE: 4 };
findings.sort((a, b) => RANK[a.level] - RANK[b.level]);

const bad = findings.filter(f => f.level === 'IMPOSSIBLE' || f.level === 'AUTOPASS');
const soft = findings.filter(f => f.level === 'BRUTAL' || f.level === 'CERTAIN');
const notes = findings.filter(f => f.level === 'NOTE');

console.log('\n\u2500\u2500 dice audit \u2500\u2500');
console.log(`${moduleCount} module(s), ${checkedCount} distinct check(s)\n`);

if (!bad.length) {
  console.log('  \u2713 no impossible or auto-passing checks');
} else {
  console.log('  BUGS:');
  bad.forEach(f => console.log(`    [${f.level}] ${f.file}${f.build?' / '+f.build:''} \u2014 ${f.msg}`));
}

if (soft.length && (VERBOSE || soft.length <= 12)) {
  console.log('\n  worth a look:');
  soft.forEach(f => console.log(`    [${f.level}] ${f.file}${f.build?' / '+f.build:''} \u2014 ${f.msg}`));
} else if (soft.length) {
  console.log(`\n  ${soft.length} borderline check(s) \u2014 run with --verbose to list them`);
}

if (notes.length) {
  console.log('\n  notes:');
  notes.forEach(f => console.log(`    ${f.file} \u2014 ${f.msg}`));
}

console.log('');
process.exit(bad.length ? 1 : 0);
