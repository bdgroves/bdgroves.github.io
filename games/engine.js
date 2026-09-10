/* ============================================================
   brooksgroves.com — shared adventure-game engine
   ------------------------------------------------------------
   A module supplies content (scenes, checks, endings) and calls
   Engine.init(). Everything below — dice, audio, history, the
   character sheet, saves — is the same across every game.

   Minimal module:

     Engine.init({
       id: 'my-game',
       title: 'MY GAME',
       subtitle: 'SOMETHING IN SMALL CAPS',
       mode: 'over',                 // 'over' = roll high, 'under' = percentile
       state: () => ({ hp: 20 }),    // fresh state for a new run
       status: () => [['HP', S.hp]], // status bar fields
       start: firstScene
     });
   ============================================================ */

const Engine = (function(){

  /* ---------- config, filled by init ---------- */
  let cfg = {};
  let S = {};                 // live run state, owned by the module
  let logEl = null;

  /* ================= DICE ================= */
  function die(sides){ return 1 + Math.floor(Math.random()*sides); }
  function d10(){ return Math.floor(Math.random()*10); }   // 0-9 for percentile
  function percentile(){
    const tens = d10(), ones = d10();
    let value = tens*10 + ones;
    if(value === 0) value = 100;
    return {tens, ones, value};
  }
  function jitter(base, spread){
    return base + (Math.floor(Math.random()*(spread*2+1)) - spread);
  }
  function pick(arr){ return arr[Math.floor(Math.random()*arr.length)]; }

  /* ================= AUDIO ================= */
  let audioCtx = null, soundOn = true;
  try { soundOn = localStorage.getItem('bg_game_sound') !== 'off'; } catch(e) {}

  function ac(){
    if(!soundOn) return null;
    if(!audioCtx){
      try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
      catch(e){ return null; }
    }
    if(audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
  }
  function sfxTick(gainMul){
    const ctx = ac(); if(!ctx) return;
    const dur = 0.045;
    const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate*dur), ctx.sampleRate);
    const data = buf.getChannelData(0);
    for(let i=0;i<data.length;i++){
      data[i] = (Math.random()*2-1) * Math.pow(1 - i/data.length, 3);
    }
    const src = ctx.createBufferSource(); src.buffer = buf;
    const bp = ctx.createBiquadFilter();
    bp.type='bandpass'; bp.frequency.value = 900 + Math.random()*1400; bp.Q.value = 1.2;
    const g = ctx.createGain();
    g.gain.value = (gainMul === undefined ? 0.18 : gainMul);
    src.connect(bp); bp.connect(g); g.connect(ctx.destination);
    src.start();
  }
  function sfxLand(){
    const ctx = ac(); if(!ctx) return;
    sfxTick(0.32);
    const osc = ctx.createOscillator(), g = ctx.createGain();
    osc.type='triangle';
    osc.frequency.setValueAtTime(180, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(70, ctx.currentTime+0.12);
    g.gain.setValueAtTime(0.22, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime+0.16);
    osc.connect(g); g.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime+0.18);
  }
  function sfxSuccess(){
    const ctx = ac(); if(!ctx) return;
    [[523.25,0],[783.99,0.09]].forEach(([f,t])=>{
      const osc = ctx.createOscillator(), g = ctx.createGain();
      osc.type='sine'; osc.frequency.value=f;
      g.gain.setValueAtTime(0.0001, ctx.currentTime+t);
      g.gain.exponentialRampToValueAtTime(0.16, ctx.currentTime+t+0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime+t+0.42);
      osc.connect(g); g.connect(ctx.destination);
      osc.start(ctx.currentTime+t); osc.stop(ctx.currentTime+t+0.45);
    });
  }
  function sfxFail(){
    const ctx = ac(); if(!ctx) return;
    const osc = ctx.createOscillator(), g = ctx.createGain(), lp = ctx.createBiquadFilter();
    osc.type='sawtooth';
    osc.frequency.setValueAtTime(220, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(110, ctx.currentTime+0.3);
    lp.type='lowpass'; lp.frequency.value=800;
    g.gain.setValueAtTime(0.14, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime+0.34);
    osc.connect(lp); lp.connect(g); g.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime+0.36);
  }
  function sfxHurt(){
    const ctx = ac(); if(!ctx) return;
    const osc = ctx.createOscillator(), g = ctx.createGain(), lp = ctx.createBiquadFilter();
    osc.type='square';
    osc.frequency.setValueAtTime(140, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(55, ctx.currentTime+0.18);
    lp.type='lowpass'; lp.frequency.value=500;
    g.gain.setValueAtTime(0.2, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime+0.22);
    osc.connect(lp); lp.connect(g); g.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime+0.24);
  }
  function toggleSound(){
    soundOn = !soundOn;
    try { localStorage.setItem('bg_game_sound', soundOn?'on':'off'); } catch(e){}
    syncSoundBtn();
    if(soundOn) sfxTick();
  }
  function syncSoundBtn(){
    const b = document.getElementById('navSound');
    if(b) b.textContent = soundOn ? '\u{1F50A} SOUND' : '\u{1F507} MUTED';
  }

  /* ================= SAVE / PERSISTENCE =================
     Cross-run memory. Modules read it to let a previous run
     leak into the next one. Keyed per game id.               */
  function saveKey(){ return 'bg_save_' + (cfg.id || 'game'); }
  let SAVE = null;
  function loadSave(){
    try {
      const raw = localStorage.getItem(saveKey());
      SAVE = raw ? JSON.parse(raw) : null;
    } catch(e){ SAVE = null; }
    if(!SAVE || typeof SAVE !== 'object'){
      SAVE = { runs:0, endings:{}, lastRun:null, flags:{} };
    }
    SAVE.runs    = SAVE.runs    || 0;
    SAVE.endings = SAVE.endings || {};
    SAVE.flags   = SAVE.flags   || {};
    return SAVE;
  }
  function persist(){
    try { localStorage.setItem(saveKey(), JSON.stringify(SAVE)); } catch(e){}
  }
  // Modules call this from their ending screen.
  function recordEnding(key, summary){
    loadSave();
    SAVE.runs += 1;
    SAVE.endings[key] = (SAVE.endings[key] || 0) + 1;
    SAVE.lastRun = Object.assign({ ending:key, at:Date.now() }, summary||{});
    persist();
  }
  function setFlag(k,v){ loadSave(); SAVE.flags[k]=v; persist(); }
  function getFlag(k){ loadSave(); return SAVE.flags[k]; }
  function lastRun(){ loadSave(); return SAVE.lastRun; }
  function runCount(){ loadSave(); return SAVE.runs; }
  function endingsFound(){ loadSave(); return Object.keys(SAVE.endings).length; }
  function hasEnding(k){ loadSave(); return !!SAVE.endings[k]; }
  function wipeSave(){
    try { localStorage.removeItem(saveKey()); } catch(e){}
    SAVE = null; loadSave();
  }

  /* ================= LOG ================= */
  function log(text, cls){
    if(!logEl) logEl = document.getElementById('log');
    if(!logEl) return;
    const d = document.createElement('div');
    if(cls) d.className = cls;
    d.textContent = text;
    logEl.appendChild(d);
    logEl.scrollTop = logEl.scrollHeight;
  }

  /* ================= RENDER HELPERS ================= */
  function render(html){ document.getElementById('main').innerHTML = html; }
  function badge(t){ document.getElementById('sceneBadge').textContent = t; }
  function contBtn(label){
    return '<button class="smallbtn primary-go" id="n">' + (label || 'CONTINUE \u2192') + '</button>';
  }
  function wire(fn){
    const n = document.getElementById('n');
    if(n) n.onclick = ()=> go(fn);
  }
  function refreshStatus(){
    if(cfg.sheet) setTimeout(renderSheet, 0);
    const bar = document.getElementById('statusbar');
    if(!bar || !cfg.status) return;
    const fields = cfg.status() || [];
    bar.innerHTML = fields.map(f=>{
      const cls = f[2] ? ' class="'+f[2]+'"' : '';
      return '<span>'+f[0]+': <b'+cls+'>'+f[1]+'</b></span>';
    }).join('') +
    '<span style="margin-left:auto;"><button class="sheetToggle" id="sheetToggle">\u25b8 '+
      (cfg.sheetLabel||'CHARACTER SHEET')+'</button></span>';
    const st = document.getElementById('sheetToggle');
    if(st) st.onclick = toggleSheet;
    syncSheetBtn();
  }

  /* ================= CHARACTER SHEET ================= */
  let sheetOpen = false;
  function toggleSheet(){ sheetOpen = !sheetOpen; renderSheet(); }
  function syncSheetBtn(){
    const btn = document.getElementById('sheetToggle');
    if(btn) btn.textContent = (sheetOpen?'\u25be ':'\u25b8 ') + (cfg.sheetLabel||'CHARACTER SHEET');
  }
  function renderSheet(){
    const el = document.getElementById('charsheet');
    if(!el || !cfg.sheet) return;
    const html = cfg.sheet();
    if(!sheetOpen || !html){ el.classList.remove('open'); syncSheetBtn(); return; }
    el.classList.add('open');
    el.innerHTML = html;
    syncSheetBtn();
  }

  /* ================= NAVIGATION ================= */
  let history = [];
  function go(fn){
    clearRolls();
    history.push(fn);
    fn();
    buildPanelOnce();
    updatePanel();
    updateNav();
  }
  function goBack(){
    if(history.length <= 1) return;
    clearRolls();
    history.pop();
    history[history.length-1]();
    updateNav();
  }
  function updateNav(){
    const b = document.getElementById('navBack');
    if(!b) return;
    const bad = document.getElementById('sceneBadge').textContent;
    const locked = (cfg.lockBackOn || []).some(x=> bad.indexOf(x) === 0);
    b.disabled = history.length <= 1 || locked;
  }
  function restart(){
    clearRolls();
    if(cfg.panelReset) cfg.panelReset(panelEl());
    S = cfg.state();
    Engine.S = S;
    if(cfg.onRestart) cfg.onRestart();
    if(logEl) logEl.innerHTML = '';
    history = [];
    refreshStatus();
    go(cfg.start);
  }

  /* ================= DICE UI ================= */
  let timers = [], rolling = false;
  function clearRolls(){
    timers.forEach(t=>{ clearTimeout(t); clearInterval(t); });
    timers = [];
    document.querySelectorAll('.diceRig').forEach(el=> el.remove());
    rolling = false;
  }
  function later(fn, ms){ const t = setTimeout(fn, ms); timers.push(t); return t; }
  function repeat(fn, ms){ const t = setInterval(fn, ms); timers.push(t); return t; }
  function lockChoices(){
    document.querySelectorAll('#main .choice, #main .smallbtn').forEach(b=>{
      if(!b.closest('.diceRig')) b.disabled = true;
    });
  }


  /* Faint interior lines so each die reads as a solid, not a badge. */
  function facetsFor(sides){
    const L = (x1,y1,x2,y2)=> '<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'"/>';
    let inner = '';
    if(sides === 20) inner = L(7,25,93,25) + L(7,75,93,75) + L(50,0,7,75) + L(50,0,93,75);
    else if(sides === 12) inner = L(50,0,50,55) + L(50,55,2,35) + L(50,55,98,35) + L(50,55,20,92) + L(50,55,80,92);
    else if(sides === 10) inner = L(50,0,50,100) + L(4,36,50,58) + L(96,36,50,58);
    else if(sides === 8)  inner = L(4,50,96,50) + L(50,0,50,100);
    else if(sides === 6)  inner = L(8,8,92,92);
    else if(sides === 4)  inner = L(50,2,50,96);
    return '<svg class="facets" viewBox="0 0 100 100" preserveAspectRatio="none">' + inner + '</svg>';
  }

  /* check({die, mod, dc, label}) for roll-over games,
     check({target, label})      for percentile roll-under games. */
  function check(opts, done){
    if(rolling) return;
    rolling = true; clearRolls(); rolling = true;
    lockChoices();
    const prior = document.getElementById('sceneBadge').textContent;
    badge('CHECK');
    const id = 'rig-' + Math.random().toString(36).slice(2,7);
    const under = (cfg.mode === 'under');

    let head, faces;
    if(under){
      head = (opts.label||'SKILL CHECK') + ' \u2014 TARGET \u2264 ' + opts.target;
      faces = '<div class="d10 spin" id="'+id+'-a">0</div><div class="d10 spin" id="'+id+'-b">0</div>';
    } else {
      const ms = (opts.mod>=0?'+':'') + opts.mod;
      head = (opts.label||'CHECK') + ' \u2014 d' + opts.die + ' ' + ms + ' vs DC ' + opts.dc;
      faces = '<div class="dieWrap">' +
                '<div class="dieShape die-'+opts.die+' spin" id="'+id+'-a">' +
                  '<div class="facesize">d'+opts.die+'</div>' +
                  '<div class="facenum">0</div>' +
                '</div>' + facetsFor(opts.die) +
              '</div>';
    }

    document.getElementById('main').insertAdjacentHTML('beforeend',
      '<div class="diceRig show" id="'+id+'">'+
        '<div class="label">'+head+'</div>'+
        '<div class="diceRow">'+faces+
          '<div class="diceMeta" id="'+id+'-meta">Rolling&hellip;</div>'+
        '</div>'+
        '<div class="result-banner" id="'+id+'-banner"></div>'+
        '<div id="'+id+'-cont" style="margin-top:14px; display:none;">'+
          '<button class="smallbtn primary-go" id="'+id+'-contbtn">CONTINUE \u2192</button>'+
        '</div>'+
      '</div>');

    const rig  = document.getElementById(id);
    const aEl  = document.getElementById(id+'-a');
    const bEl  = document.getElementById(id+'-b');
    const meta = document.getElementById(id+'-meta');
    const alive = ()=> document.body.contains(rig);

    function finish(success, value, detail){
      if(!alive()) return;
      later(()=>{ success ? sfxSuccess() : sfxFail(); }, 260);
      meta.innerHTML = detail;
      const banner = document.getElementById(id+'-banner');
      banner.textContent = success ? 'SUCCESS' : 'FAILURE';
      banner.className = 'result-banner ' + (success?'success':'fail');
      log((opts.label||'Check') + ': ' + value + ' \u2192 ' + (success?'SUCCESS':'FAILURE'),
          success ? 'l-good' : 'l-bad');
      rolling = false;
      badge(prior);
      document.getElementById(id+'-cont').style.display = 'block';
      const cb = document.getElementById(id+'-contbtn');
      let used = false;
      cb.onclick = ()=>{
        if(used) return;
        used = true; cb.disabled = true;
        clearRolls();
        done(success, value);
      };
    }

    if(under){
      const r = percentile();
      let n = 0;
      const t1 = repeat(()=>{
        if(!alive()) return;
        aEl.textContent = d10(); bEl.textContent = d10();
        if(n%2===0) sfxTick(); n++;
      }, 80);
      later(()=>{
        clearInterval(t1);
        if(!alive()) return;
        aEl.classList.remove('spin'); aEl.textContent = r.tens; sfxLand();
        meta.innerHTML = 'Tens die: <b>'+r.tens+'</b> &nbsp;\u00b7&nbsp; ones die still rolling&hellip;';
        let m = 0;
        const t2 = repeat(()=>{
          if(!alive()) return;
          bEl.textContent = d10();
          if(m%2===0) sfxTick(); m++;
        }, 80);
        later(()=>{
          clearInterval(t2);
          if(!alive()) return;
          bEl.classList.remove('spin'); bEl.textContent = r.ones; sfxLand();
          finish(r.value <= opts.target, r.value,
                 'Read as <b>'+r.value+'</b> against a target of <b>'+opts.target+'</b>.');
        }, 1100);
      }, 1300);
    } else {
      const raw = die(opts.die), total = raw + opts.mod;
      const face = aEl.querySelector('.facenum');
      let n = 0;
      const t1 = repeat(()=>{
        if(!alive()) return;
        face.textContent = die(opts.die);
        if(n%2===0) sfxTick(); n++;
      }, 80);
      later(()=>{
        clearInterval(t1);
        if(!alive()) return;
        aEl.classList.remove('spin'); face.textContent = raw; sfxLand();
        meta.innerHTML = 'The d'+opts.die+' lands on <b>'+raw+'</b>&hellip;';
        later(()=>{
          const ms = (opts.mod>=0?'+':'') + opts.mod;
          finish(total >= opts.dc, total,
                 '<b>'+raw+'</b> '+ms+' = <b>'+total+'</b> against DC <b>'+opts.dc+'</b>.');
        }, 1000);
      }, 1500);
    }
  }

  /* Odds badge for a choice button, so the player sees the
     shape of a gamble before committing to it. */
  function odds(o){
    if(cfg.mode === 'under'){
      return ' <span class="tgtBadge">roll \u2264 ' + o.target + '</span>';
    }
    const need = o.dc - o.mod;
    const p = Math.max(0, Math.min(100, Math.round((o.die - need + 1)/o.die*100)));
    return ' <span class="tgtBadge">d'+o.die+' vs DC '+o.dc+' \u00b7 '+p+'%</span>';
  }


  /* ================= PERSISTENT PANEL =================
     A module-owned region above #main that survives scene
     changes. Built once; render() never touches it. Needed
     for anything stateful and expensive — a Leaflet map, a
     canvas, a chart you don't want torn down every turn.   */
  let panelBuilt = false;
  function panelEl(){ return document.getElementById('panel'); }
  function showPanel(on){
    const el = panelEl();
    if(el) el.style.display = (on === false) ? 'none' : 'block';
  }
  function buildPanelOnce(){
    if(panelBuilt || !cfg.panel) return;
    const el = panelEl();
    if(!el) return;
    panelBuilt = true;
    showPanel(true);
    cfg.panel(el);              // module fills it and keeps its own handle
  }
  function updatePanel(){
    if(cfg.panelUpdate) cfg.panelUpdate(panelEl());
  }

  /* ================= CHROME ================= */
  function buildChrome(){
    document.title = cfg.pageTitle || cfg.title;
    const host = document.getElementById('game');
    host.innerHTML =
      '<div class="topline"></div>'+
      '<div class="sitebar"><div class="masthead-inner">'+
        '<a href="/" class="site-name">Brooks Groves</a>'+
        '<div class="sitenav">'+
          '<a href="/games.html">Games</a>'+
          '<a href="/games/reference.html">Screen</a>'+
          '<a href="/">Home</a>'+
          '<button id="theme-toggle" class="theme-toggle" title="Toggle dark mode">\u25d0</button>'+
        '</div>'+
      '</div></div>'+
      '<div class="console">'+
        '<header><div><h1>'+cfg.title+'</h1>'+
          '<div class="sub">'+(cfg.subtitle||'')+'</div></div>'+
          '<div class="badge" id="sceneBadge">START</div></header>'+
        '<div class="statusbar" id="statusbar"></div>'+
        '<div class="charsheet" id="charsheet"></div>'+
        '<div id="panel" class="gamePanel" style="display:none;"></div>'+
        '<main id="main"></main>'+
        '<footer class="log" id="log"></footer>'+
        '<div class="navbar">'+
          '<button class="navbtn" id="navRestart">\u27f2 RESTART</button>'+
          '<button class="navbtn" id="navBack" disabled>\u2190 BACK</button>'+
          '<button class="navbtn" id="navSound">\u{1F50A} SOUND</button>'+
          '<a class="navbtn navhome" href="/games.html">\u{1F3E0} GAMES</a>'+
        '</div>'+
      '</div>';

    document.getElementById('navRestart').onclick = ()=>{
      if(confirm('Restart from the beginning?')) restart();
    };
    document.getElementById('navBack').onclick = goBack;
    document.getElementById('navSound').onclick = toggleSound;

    const root = document.documentElement;
    const tb = document.getElementById('theme-toggle');
    const sync = ()=>{ tb.textContent = root.getAttribute('data-theme')==='dark' ? '\u25d0' : '\u25d1'; };
    sync();
    tb.onclick = ()=>{
      const dark = root.getAttribute('data-theme')==='dark';
      if(dark) root.removeAttribute('data-theme'); else root.setAttribute('data-theme','dark');
      try { localStorage.setItem('bg_theme', dark?'light':'dark'); } catch(e){}
      sync();
    };
  }

  /* ================= INIT ================= */
  function init(config){
    cfg = config;
    if(cfg.accent){
      document.documentElement.style.setProperty('--accent', cfg.accent);
    }
    buildChrome();
    loadSave();
    S = cfg.state();
    Engine.S = S;
    logEl = document.getElementById('log');
    syncSoundBtn();
    refreshStatus();
    go(cfg.start);
  }

  return {
    init, go, goBack, restart, check, odds,
    render, badge, log, contBtn, wire, refreshStatus, renderSheet,
    clearRolls, later, repeat,
    panelEl, showPanel, updatePanel,
    die, d10, percentile, jitter, pick,
    sfxTick, sfxLand, sfxSuccess, sfxFail, sfxHurt,
    recordEnding, setFlag, getFlag, lastRun, runCount, endingsFound, hasEnding, wipeSave,
    get state(){ return S; },
    S: {}
  };
})();

// Expose for debugging from the browser console and for test harnesses.
// (A top-level `const` does not attach to window on its own.)
if (typeof window !== 'undefined') window.Engine = Engine;
