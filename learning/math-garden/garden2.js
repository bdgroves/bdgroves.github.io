// The Math Garden, part 2: four more gardens, and the share bar (save a picture, record a video,
// post to X or Bluesky) on every garden. Gardens register themselves in window.MG with a canvas
// and an optional play(seconds) that animates them for a recording.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const dark = () => document.documentElement.dataset.theme === 'dark';
  const MG = (window.MG = window.MG || {});
  function bind(id, fn, fmt) {
    const el = $(id), out = $(id + '-o');
    el.addEventListener('input', () => { if (out) out.textContent = fmt ? fmt(+el.value) : el.value; fn(); });
  }
  function onScreen(el, cb) {
    if (!('IntersectionObserver' in window)) { cb(true); return; }
    new IntersectionObserver((es) => es.forEach((e) => cb(e.isIntersecting)), { rootMargin: '100px' }).observe(el);
  }

  // ---------------------------------------------------------------- spirograph
  (function () {
    const cv = $('c-spiro'); if (!cv) return;
    const g = cv.getContext('2d'), S = cv.width, R = 1;
    let sc = S * 0.45;
    const fit = (r, d) => { sc = (S * 0.45) / Math.max(1, R - r + d); };
    let raf = null, path = [];
    const v = (id) => +$(id).value;
    function gcdTurns(r) {           // how many trips round the ring before it closes (capped)
      for (let q = 1; q <= 60; q++) { const p = q * (R / r); if (Math.abs(p - Math.round(p)) < 0.01 * q) return q; }
      return 60;
    }
    function point(t, r, d) {
      const k = (R - r) / r;
      return [(R - r) * Math.cos(t) + d * Math.cos(k * t), (R - r) * Math.sin(t) - d * Math.sin(k * t)];
    }
    function paint(t, r, d, showGear) {
      const ink = css('--ink'), mist = css('--mist'), rust = css('--rust');
      g.clearRect(0, 0, S, S);
      const o = S / 2;
      g.strokeStyle = mist; g.lineWidth = 2; g.beginPath(); g.arc(o, o, R * sc, 0, Math.PI * 2); g.stroke();
      g.strokeStyle = rust; g.lineWidth = 1.4; g.beginPath();
      path.forEach(([x, y], i) => (i ? g.lineTo(o + x * sc, o - y * sc) : g.moveTo(o + x * sc, o - y * sc))); g.stroke();
      if (showGear) {
        const gx = (R - r) * Math.cos(t), gy = (R - r) * Math.sin(t), [px, py] = point(t, r, d);
        g.strokeStyle = ink; g.lineWidth = 1.5; g.beginPath(); g.arc(o + gx * sc, o - gy * sc, r * sc, 0, Math.PI * 2); g.stroke();
        g.beginPath(); g.moveTo(o + gx * sc, o - gy * sc); g.lineTo(o + px * sc, o - py * sc); g.stroke();
        g.fillStyle = ink; g.beginPath(); g.arc(o + px * sc, o - py * sc, 4, 0, Math.PI * 2); g.fill();
      }
    }
    function run(seconds) {
      cancelAnimationFrame(raf);
      const r = v('sp-r'), d = v('sp-d'); fit(r, d); const T = Math.PI * 2 * gcdTurns(r), frames = Math.round((seconds || 8) * 60);
      path = []; let f = 0;
      const step = () => {
        const t0 = (f / frames) * T, t1 = ((f + 1) / frames) * T;
        for (let i = 0; i <= 12; i++) path.push(point(t0 + ((t1 - t0) * i) / 12, r, d));
        paint(t1, r, d, f < frames - 1); f++;
        if (f < frames) raf = requestAnimationFrame(step);
      };
      step();
    }
    function still() { cancelAnimationFrame(raf); const r = v('sp-r'), d = v('sp-d'); fit(r, d); const T = Math.PI * 2 * gcdTurns(r); path = []; for (let i = 0; i <= 6000; i++) path.push(point((i / 6000) * T, r, d)); paint(0, r, d, false); }
    bind('sp-r', still, (x) => x.toFixed(2)); bind('sp-d', still, (x) => x.toFixed(2));
    $('sp-go').addEventListener('click', () => run(8));
    let started = false; onScreen(cv, (vis) => { if (vis && !started) { started = true; run(6); } });
    MG.spirograph = { canvas: cv, play: (s) => run(s) };
  })();

  // ---------------------------------------------------------------- golden angle
  (function () {
    const cv = $('c-golden'); if (!cv) return;
    const g = cv.getContext('2d'), S = cv.width;
    const v = (id) => +$(id).value;
    function draw(angle, n) {
      angle = angle ?? v('go-a'); n = n ?? v('go-n');
      g.clearRect(0, 0, S, S);
      const o = S / 2, c = (S * 0.46) / Math.sqrt(n), rad = (angle * Math.PI) / 180, dot = Math.max(2, c * 0.42);
      for (let i = 1; i <= n; i++) {
        const r = c * Math.sqrt(i), a = i * rad;
        g.fillStyle = `hsl(${30 + (i / n) * 30} ${dark() ? 75 : 70}% ${dark() ? 30 + (i / n) * 35 : 25 + (i / n) * 30}%)`;
        g.beginPath(); g.arc(o + r * Math.cos(a), o + r * Math.sin(a), dot, 0, Math.PI * 2); g.fill();
      }
    }
    bind('go-a', () => draw(), (x) => x.toFixed(2) + '°'); bind('go-n', () => draw());
    $('go-reset').addEventListener('click', () => { $('go-a').value = 137.51; $('go-a-o').textContent = '137.51°'; draw(); });
    draw();
    new MutationObserver(() => draw()).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    MG.golden = { canvas: cv, play(seconds) {   // sweep the angle through the golden one and back
      const a0 = 136.9, a1 = 138.1, frames = Math.round(seconds * 30); let f = 0;
      const step = () => { const t = f / frames, a = a0 + (a1 - a0) * (0.5 - 0.5 * Math.cos(t * Math.PI * 2)); draw(a); $('go-a').value = a; $('go-a-o').textContent = a.toFixed(2) + '°'; if (++f <= frames) requestAnimationFrame(step); };
      step();
    } };
  })();

  // ---------------------------------------------------------------- chaos game
  (function () {
    const cv = $('c-chaos'); if (!cv) return;
    const g = cv.getContext('2d'), S = cv.width;
    let raf = null;
    const FERN = [[0, 0, 0, 0.16, 0, 0, 0.01], [0.85, 0.04, -0.04, 0.85, 0, 1.6, 0.85], [0.2, -0.26, 0.23, 0.22, 0, 1.6, 0.07], [-0.15, 0.28, 0.26, 0.24, 0, 0.44, 0.07]];
    function corners(n) { return Array.from({ length: n }, (_, i) => [Math.cos(-Math.PI / 2 + (i * 2 * Math.PI) / n), Math.sin(-Math.PI / 2 + (i * 2 * Math.PI) / n)]); }
    function run(seconds) {
      cancelAnimationFrame(raf);
      const shape = $('ch-shape').value, frames = Math.round((seconds || 6) * 60), total = shape === 'fern' ? 260000 : 160000;
      g.fillStyle = '#0e0d12'; g.fillRect(0, 0, S, S);
      let x = 0, y = 0, done = 0, f = 0;
      const pts = shape === 'tri' ? corners(3) : corners(6), jump = shape === 'hex' ? 2 / 3 : 0.5;
      const step = () => {
        // ease in: few dots at first so you can watch the pattern emerge, then lots
        const goal = Math.round(total * Math.pow((f + 1) / frames, 2.2));
        g.fillStyle = shape === 'fern' ? 'rgba(140,210,120,0.55)' : 'rgba(240,180,110,0.55)';
        for (; done < goal; done++) {
          let px, py;
          if (shape === 'fern') {
            const rnd = Math.random(); let acc = 0, m = FERN[3];
            for (const t of FERN) { acc += t[6]; if (rnd < acc) { m = t; break; } }
            const nx = m[0] * x + m[1] * y + m[4], ny = m[2] * x + m[3] * y + m[5]; x = nx; y = ny;
            px = S / 2 + x * S * 0.085; py = S - 20 - y * S * 0.093;
          } else {
            const c = pts[(Math.random() * pts.length) | 0]; x += (c[0] - x) * jump; y += (c[1] - y) * jump;
            if (done < 20) continue;
            px = S / 2 + x * S * 0.46; py = S / 2 + 30 + y * S * 0.46;
          }
          g.fillRect(px, py, done < 3000 ? 2.5 : 1, done < 3000 ? 2.5 : 1);
        }
        if (++f < frames) raf = requestAnimationFrame(step);
      };
      step();
    }
    $('ch-shape').addEventListener('change', () => run(6));
    $('ch-go').addEventListener('click', () => run(6));
    let started = false; onScreen(cv, (vis) => { if (vis && !started) { started = true; run(6); } });
    MG.chaos = { canvas: cv, play: (s) => run(s) };
  })();

  // ---------------------------------------------------------------- lorenz
  (function () {
    const cv = $('c-lorenz'); if (!cv) return;
    const g = cv.getContext('2d'), S = cv.width, hud = $('lz-hud');
    const sigma = 10, beta = 8 / 3;
    let A, B, trailA, trailB, ang = 0, visible = false;
    function reset() { A = [1, 1, 20]; B = [1 + 1e-6, 1, 20]; trailA = []; trailB = []; }
    function stepP(p, rho, dt) {
      const f = (q) => [sigma * (q[1] - q[0]), q[0] * (rho - q[2]) - q[1], q[0] * q[1] - beta * q[2]];
      const k1 = f(p), k2 = f(p.map((v, i) => v + (dt / 2) * k1[i])), k3 = f(p.map((v, i) => v + (dt / 2) * k2[i])), k4 = f(p.map((v, i) => v + dt * k3[i]));
      return p.map((v, i) => v + (dt / 6) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
    }
    function proj([x, y, z]) {
      const a = 0.55 * Math.sin(ang), c = Math.cos(a), s = Math.sin(a), X = x * c - y * s;
      return [S / 2 + X * S * 0.019, S / 2 - (z - 25) * S * 0.0175];
    }
    function line(tr, color) {
      g.strokeStyle = color; g.lineWidth = 1.3; g.beginPath();
      tr.forEach((p, i) => { const [u, w] = proj(p); i ? g.lineTo(u, w) : g.moveTo(u, w); }); g.stroke();
    }
    function frame() {
      if (visible) {
        const rho = +$('lz-r').value;
        for (let i = 0; i < 6; i++) { A = stepP(A, rho, 0.006); B = stepP(B, rho, 0.006); trailA.push(A); trailB.push(B); }
        if (trailA.length > 2400) { trailA.splice(0, trailA.length - 2400); trailB.splice(0, trailB.length - 2400); }
        ang += 0.004;
        g.fillStyle = '#0e0d12'; g.fillRect(0, 0, S, S);
        line(trailB, 'rgba(110,170,225,0.85)'); line(trailA, 'rgba(225,110,80,0.85)');
        for (const [p, c] of [[A, '#e86e50'], [B, '#6eaae1']]) { const [u, w] = proj(p); g.fillStyle = c; g.beginPath(); g.arc(u, w, 5, 0, Math.PI * 2); g.fill(); }
        const dist = Math.hypot(A[0] - B[0], A[1] - B[1], A[2] - B[2]);
        hud.textContent = `apart: ${dist < 0.001 ? dist.toExponential(1) : dist.toFixed(dist < 1 ? 3 : 1)}`;
      }
      requestAnimationFrame(frame);
    }
    reset();
    bind('lz-r', () => {}, (x) => x.toFixed(1));
    $('lz-go').addEventListener('click', reset);
    onScreen(cv, (vis) => { visible = vis; });
    requestAnimationFrame(frame);
    MG.lorenz = { canvas: cv, play: () => reset() };
  })();

  // ---------------------------------------------------------------- the share bar
  const SITE = 'https://brooksgroves.com/learning/math-garden/';
  const TAGS = '#MathArt #generativeart';
  function mime() {
    const opts = ['video/mp4;codecs=avc1.42E01E', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
    return (window.MediaRecorder && opts.find((m) => MediaRecorder.isTypeSupported(m))) || null;
  }
  function download(blob, name) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }
  function flash(btn, text) { const t = btn.textContent; btn.textContent = text; setTimeout(() => (btn.textContent = t), 1800); }
  document.querySelectorAll('section.plot').forEach((sec) => {
    const id = sec.id, entry = MG[id], canvas = (entry && entry.canvas) || sec.querySelector('canvas');
    if (!canvas) return;
    const title = sec.querySelector('h2').textContent;
    const blurb = sec.dataset.share || title;
    const url = SITE + '#' + id;
    const bar = document.createElement('div'); bar.className = 'sharebar';
    bar.innerHTML = '<span class="sb-label">Share it</span>'
      + '<button type="button" class="sb" data-a="png">&#8681; Save picture</button>'
      + (mime() ? '<button type="button" class="sb" data-a="rec">&#9679; Record 10 s video</button>' : '')
      + `<a class="sb" target="_blank" rel="noopener" href="https://x.com/intent/post?text=${encodeURIComponent(blurb + ' ' + TAGS)}&url=${encodeURIComponent(url)}">Post to X</a>`
      + `<a class="sb" target="_blank" rel="noopener" href="https://bsky.app/intent/compose?text=${encodeURIComponent(blurb + ' ' + url + ' ' + TAGS)}">Post to Bluesky</a>`
      + '<button type="button" class="sb" data-a="link">Copy link</button>';
    const tryEl = sec.querySelector('.try'); sec.insertBefore(bar, tryEl);
    const slug = 'math-garden-' + id;
    bar.addEventListener('click', async (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.a === 'png') {
        canvas.toBlob((blob) => blob && download(blob, slug + '.png'), 'image/png');
      } else if (b.dataset.a === 'link') {
        try { await navigator.clipboard.writeText(url); flash(b, 'Copied ✓'); } catch (err) { prompt('Copy this link:', url); }
      } else if (b.dataset.a === 'rec') {
        const type = mime(), stream = canvas.captureStream(30), chunks = [];
        const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8_000_000 });
        rec.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
        rec.onstop = () => { download(new Blob(chunks, { type }), slug + (type.includes('mp4') ? '.mp4' : '.webm')); b.disabled = false; b.innerHTML = '&#9679; Record 10 s video'; };
        b.disabled = true; let left = 10; b.textContent = `Recording… ${left}`;
        const tick = setInterval(() => { left--; b.textContent = left > 0 ? `Recording… ${left}` : 'Saving…'; if (left <= 0) clearInterval(tick); }, 1000);
        rec.start(250);
        if (entry && entry.play) entry.play(9.5);
        setTimeout(() => rec.stop(), 10000);
      }
    });
  });
})();
