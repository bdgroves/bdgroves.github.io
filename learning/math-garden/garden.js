// The Math Garden: six live gardens. Plain JS: 2D canvas for 1-4, WebGL for 5-6.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function bind(id, fn, fmt) {
    const el = $(id), out = $(id + '-o');
    const upd = () => { if (out) out.textContent = fmt ? fmt(+el.value) : el.value; fn(); };
    el.addEventListener('input', upd); return el;
  }
  // only animate what's on screen
  function onScreen(el, cb) {
    if (!('IntersectionObserver' in window)) { cb(true); return; }
    new IntersectionObserver((es) => es.forEach((e) => cb(e.isIntersecting)), { rootMargin: '100px' }).observe(el);
  }

  // ---------------------------------------------------------------- 1 circles
  (function () {
    const cv = $('c-circles'), g = cv.getContext('2d');
    const W = cv.width, H = cv.height, cx = 210, cy = H / 2, R = 110;
    let t = 0, wave = [], visible = false, n = 1;
    const shape = $('circ-shape');
    bind('circ-n', () => { n = +$('circ-n').value; wave = []; });
    shape.addEventListener('change', () => { wave = []; });
    function terms() {
      const out = [];
      for (let i = 0; i < n; i++) {
        if (shape.value === 'square') { const k = 2 * i + 1; out.push([k, 4 / (Math.PI * k)]); }
        else { const k = i + 1; out.push([k, (2 / Math.PI) * (i % 2 ? -1 : 1) / k]); }
      }
      return out;
    }
    function frame() {
      if (visible) {
        const ink = css('--ink'), rust = css('--rust'), mist = css('--mist'), stone = css('--stone');
        g.clearRect(0, 0, W, H);
        let x = cx, y = cy;
        g.lineWidth = 1.5;
        for (const [k, a] of terms()) {
          const r = R * a, px = x, py = y;
          g.strokeStyle = mist; g.beginPath(); g.arc(px, py, r, 0, Math.PI * 2); g.stroke();
          x += r * Math.cos(k * t); y -= r * Math.sin(k * t);
          g.strokeStyle = stone; g.beginPath(); g.moveTo(px, py); g.lineTo(x, y); g.stroke();
        }
        wave.unshift(y); if (wave.length > 600) wave.pop();
        const x0 = 440;
        g.strokeStyle = mist; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(x, y); g.lineTo(x0, wave[0]); g.stroke(); g.setLineDash([]);
        g.strokeStyle = rust; g.lineWidth = 2.5; g.beginPath();
        wave.forEach((wy, i) => (i ? g.lineTo(x0 + i, wy) : g.moveTo(x0, wy))); g.stroke();
        g.fillStyle = ink; g.beginPath(); g.arc(x, y, 4.5, 0, Math.PI * 2); g.fill();
        t += reduce ? 0.004 : 0.022;
      }
      requestAnimationFrame(frame);
    }
    onScreen(cv, (v) => { visible = v; });
    requestAnimationFrame(frame);
  })();

  // ---------------------------------------------------------------- 2 lissajous
  (function () {
    const cv = $('c-liss'), g = cv.getContext('2d'), S = cv.width;
    let anim = null;
    const val = (id) => +$(id).value;
    function pts(steps) {
      const a = val('li-a'), b = val('li-b'), p = val('li-p'), d = val('li-d');
      const T = d > 0 ? Math.min(400, 7 / d) : Math.PI * 2 * 60, out = [];
      for (let i = 0; i <= steps; i++) {
        const t = (i / steps) * T, e = Math.exp(-d * t);
        out.push([Math.sin(a * t + p) * e, Math.sin(b * t) * e]);
      }
      return out;
    }
    function draw(upto) {
      const P = pts(20000), n = upto == null ? P.length : upto;
      g.clearRect(0, 0, S, S);
      g.lineWidth = 1; g.globalAlpha = 0.85;
      const rust = css('--rust'), sky = css('--sky') || '#2a4a6b';
      for (let i = 1; i < n; i++) {
        if (i % 400 === 1) { if (i > 1) g.stroke(); g.beginPath(); g.strokeStyle = val('li-d') > 0 && i / P.length > 0.5 ? sky : rust; g.moveTo(S / 2 + P[i - 1][0] * S * 0.44, S / 2 - P[i - 1][1] * S * 0.44); }
        g.lineTo(S / 2 + P[i][0] * S * 0.44, S / 2 - P[i][1] * S * 0.44);
      }
      g.stroke(); g.globalAlpha = 1;
    }
    const redraw = () => { if (anim) { cancelAnimationFrame(anim); anim = null; } draw(); };
    const f2 = (v) => (Math.abs(v - Math.round(v)) < 0.0005 ? String(Math.round(v)) : v.toFixed(3));
    bind('li-a', redraw, f2); bind('li-b', redraw, f2); bind('li-p', redraw, (v) => v.toFixed(2)); bind('li-d', redraw, (v) => v.toFixed(4));
    $('li-draw').addEventListener('click', () => {
      if (anim) cancelAnimationFrame(anim);
      let k = 0; const step = () => { k += 120; draw(k); if (k < 20000) anim = requestAnimationFrame(step); else anim = null; };
      step();
    });
    draw();
    new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  })();

  // ---------------------------------------------------------------- 3 lines
  (function () {
    const cv = $('c-lines'), g = cv.getContext('2d'), S = cv.width, N = 2000;
    const v = (id) => +$(id).value;
    function draw() {
      const m = v('ln-m'), n = v('ln-n'), p = v('ln-p'), q = v('ln-q'), r = v('ln-r');
      g.clearRect(0, 0, S, S);
      g.lineWidth = 0.6; g.globalAlpha = 0.35;
      const sc = S * 0.45, o = S / 2;
      for (let k = 0; k < N; k++) {
        const th = (2 * Math.PI * k) / N;
        const x1 = Math.sin(m * th) ** 3, y1 = Math.cos(n * th);
        const x2 = r * Math.sin(p * th), y2 = r * Math.cos(q * th) ** 3;
        g.strokeStyle = `hsl(${(330 + (k / N) * 120) % 360} 70% ${document.documentElement.dataset.theme === 'dark' ? 62 : 42}%)`;
        g.beginPath(); g.moveTo(o + x1 * sc, o - y1 * sc); g.lineTo(o + x2 * sc, o - y2 * sc); g.stroke();
      }
      g.globalAlpha = 1;
    }
    ['ln-m', 'ln-n', 'ln-p', 'ln-q'].forEach((id) => bind(id, draw));
    bind('ln-r', draw, (x) => x.toFixed(2));
    $('ln-rand').addEventListener('click', () => {
      ['ln-m', 'ln-n', 'ln-p', 'ln-q'].forEach((id) => { $(id).value = 1 + Math.floor(Math.random() * 6); $(id + '-o').textContent = $(id).value; });
      $('ln-r').value = (0.3 + Math.random() * 0.6).toFixed(2); $('ln-r-o').textContent = $('ln-r').value; draw();
    });
    draw();
    new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  })();

  // ---------------------------------------------------------------- 4 attractor
  (function () {
    const cv = $('c-attr'), g = cv.getContext('2d'), S = cv.width;
    const PAL = {
      ember: [[14, 13, 18], [90, 20, 80], [200, 60, 70], [250, 160, 80], [255, 240, 210]],
      glacier: [[8, 14, 24], [20, 60, 110], [50, 140, 190], [150, 215, 235], [240, 252, 255]],
      aurora: [[6, 12, 16], [10, 80, 70], [40, 180, 120], [180, 230, 120], [250, 255, 230]],
    };
    let timer = null;
    const v = (id) => +$(id).value;
    function lerp(pal, x) {
      const f = Math.min(0.9999, Math.max(0, x)) * (pal.length - 1), i = Math.floor(f), t = f - i;
      return pal[i].map((c, j) => c + (pal[i + 1][j] - c) * t);
    }
    function compute(a, b, c, d, n) {
      const H = new Float32Array(S * S);
      let x = 0.1, y = 0.1, max = 0;
      const half = S / 2, sc = S / (2 * (1 + Math.max(Math.abs(c), Math.abs(d), 1)) ) * 0.98;
      for (let i = 0; i < n; i++) {
        const nx = Math.sin(a * y) + c * Math.cos(a * x), ny = Math.sin(b * x) + d * Math.cos(b * y);
        x = nx; y = ny;
        if (i < 100) continue;
        const px = (half + x * sc) | 0, py = (half - y * sc) | 0;
        if (px >= 0 && py >= 0 && px < S && py < S) { const k = py * S + px; const h = ++H[k]; if (h > max) max = h; }
      }
      return { H, max };
    }
    function spread(H) {          // how much of the canvas got hit: a collapsed attractor hits very little
      let hit = 0; for (let i = 0; i < H.length; i += 7) if (H[i]) hit++; return hit / (H.length / 7);
    }
    function paint({ H, max }) {
      const img = g.createImageData(S, S), pal = PAL[$('at-pal').value], lm = Math.log1p(max);
      for (let i = 0; i < H.length; i++) {
        const [r, gg, b] = lerp(pal, H[i] ? Math.pow(Math.log1p(H[i]) / lm, 0.8) : 0);
        img.data[i * 4] = r; img.data[i * 4 + 1] = gg; img.data[i * 4 + 2] = b; img.data[i * 4 + 3] = 255;
      }
      g.putImageData(img, 0, 0);
    }
    function render(quick) {
      clearTimeout(timer);
      const a = v('at-a'), b = v('at-b'), c = v('at-c'), d = v('at-d');
      paint(compute(a, b, c, d, 250000));                      // fast preview while dragging
      if (!quick) timer = setTimeout(() => paint(compute(a, b, c, d, 2500000)), 180);
    }
    ['at-a', 'at-b', 'at-c', 'at-d'].forEach((id) => bind(id, () => render(false), (x) => x.toFixed(2)));
    $('at-pal').addEventListener('change', () => render(false));
    $('at-rand').addEventListener('click', () => {
      let p, tries = 0;
      do { p = [0, 0, 0, 0].map(() => +(Math.random() * 6 - 3).toFixed(2)); tries++; }
      while (tries < 40 && spread(compute(p[0], p[1], p[2], p[3], 60000).H) < 0.04);
      ['at-a', 'at-b', 'at-c', 'at-d'].forEach((id, i) => { $(id).value = p[i]; $(id + '-o').textContent = p[i].toFixed(2); });
      render(false);
    });
    let started = false;
    onScreen(cv, (vis) => { if (vis && !started) { started = true; render(false); } });
  })();

  // ---------------------------------------------------------------- 5 + 6 mandelbrot / julia (WebGL)
  const FRAG = `precision highp float;
  uniform vec2 res; uniform vec2 center; uniform float span; uniform int maxIt; uniform int julia; uniform vec2 jc;
  vec3 pal(float t){
    // night blue -> violet -> rust -> gold -> cream, and round again
    t = fract(t);
    vec3 a = vec3(0.05,0.06,0.16), b = vec3(0.36,0.13,0.40), c = vec3(0.78,0.30,0.18), d = vec3(0.96,0.74,0.36), e = vec3(1.0,0.97,0.88);
    if (t < 0.25) return mix(a, b, t/0.25);
    if (t < 0.5) return mix(b, c, (t-0.25)/0.25);
    if (t < 0.7) return mix(c, d, (t-0.5)/0.2);
    if (t < 0.85) return mix(d, e, (t-0.7)/0.15);
    return mix(e, a, (t-0.85)/0.15);
  }
  void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5*res) / res.y;
    vec2 p = center + uv * span;
    vec2 z = julia == 1 ? p : vec2(0.0);
    vec2 c = julia == 1 ? jc : p;
    float n = 0.0; bool esc = false;
    for (int i = 0; i < 4000; i++) {
      if (i >= maxIt) break;
      z = vec2(z.x*z.x - z.y*z.y, 2.0*z.x*z.y) + c;
      if (dot(z,z) > 256.0) { esc = true; break; }
      n += 1.0;
    }
    if (!esc) { gl_FragColor = vec4(0.055,0.05,0.07,1.0); return; }
    float sn = n - log2(log2(dot(z,z))) + 4.0;
    float t = sqrt(sn) * 0.11 + 0.02;
    gl_FragColor = vec4(pal(t), 1.0);
  }`;
  function makeGL(canvas) {
    const gl = canvas.getContext('webgl', { preserveDrawingBuffer: true, antialias: false });
    if (!gl) return null;
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.warn(gl.getShaderInfoLog(s)); return s; };
    const pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, 'attribute vec2 p; void main(){ gl_Position = vec4(p,0.0,1.0); }'));
    gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(pr); gl.useProgram(pr);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const U = {}; ['res', 'center', 'span', 'maxIt', 'julia', 'jc'].forEach((k) => (U[k] = gl.getUniformLocation(pr, k)));
    return function draw(o) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(U.res, canvas.width, canvas.height); gl.uniform2f(U.center, o.cx, o.cy); gl.uniform1f(U.span, o.span);
      gl.uniform1i(U.maxIt, o.it); gl.uniform1i(U.julia, o.julia ? 1 : 0); gl.uniform2f(U.jc, o.jx || 0, o.jy || 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
  }
  function noGL(canvas) {
    const g = canvas.getContext('2d'); g.fillStyle = '#222'; g.fillRect(0, 0, canvas.width, canvas.height);
    g.fillStyle = '#ccc'; g.font = '20px monospace'; g.fillText('This garden needs WebGL, which this browser has turned off.', 40, canvas.height / 2);
  }

  // 5 mandelbrot
  (function () {
    const cv = $('c-mandel'), draw = makeGL(cv), hud = $('m-hud');
    if (!draw) return noGL(cv);
    const home = { cx: -0.65, cy: 0, span: 2.6 };
    const st = { ...home, it: 500 };
    const r = () => {
      draw({ ...st, julia: false });
      const zoom = home.span / st.span;
      hud.textContent = `zoom ${zoom < 1000 ? zoom.toFixed(1) : zoom.toExponential(1)}× · c = ${st.cx.toFixed(6)} ${st.cy >= 0 ? '+' : '−'} ${Math.abs(st.cy).toFixed(6)}i`;
    };
    function at(e) {
      const b = cv.getBoundingClientRect();
      const ux = ((e.clientX - b.left) / b.width) * cv.width, uy = (1 - (e.clientY - b.top) / b.height) * cv.height;
      return [st.cx + ((ux - cv.width / 2) / cv.height) * st.span, st.cy + ((uy - cv.height / 2) / cv.height) * st.span];
    }
    let anim = null;
    function flyTo(cx, cy, span) {
      cancelAnimationFrame(anim);
      const s0 = { cx: st.cx, cy: st.cy, span: st.span }, T = reduce ? 1 : 28; let k = 0;
      const step = () => {
        k++; const t = k / T, e = t * t * (3 - 2 * t);
        st.cx = s0.cx + (cx - s0.cx) * e; st.cy = s0.cy + (cy - s0.cy) * e;
        st.span = Math.exp(Math.log(s0.span) + (Math.log(span) - Math.log(s0.span)) * e);
        r(); if (k < T) anim = requestAnimationFrame(step);
      };
      step();
    }
    cv.addEventListener('click', (e) => { const [x, y] = at(e); flyTo(x, y, e.shiftKey ? st.span * 3 : st.span / 3); });
    cv.addEventListener('contextmenu', (e) => { e.preventDefault(); const [x, y] = at(e); flyTo(x, y, st.span * 3); });
    $('m-out').addEventListener('click', () => flyTo(st.cx, st.cy, Math.min(home.span * 1.5, st.span * 3)));
    $('m-reset').addEventListener('click', () => flyTo(home.cx, home.cy, home.span));
    $('m-go').addEventListener('change', (e) => { if (!e.target.value) return; const [x, y, s] = e.target.value.split(',').map(Number); flyTo(x, y, s); e.target.value = ''; });
    bind('m-it', () => { st.it = +$('m-it').value; r(); });
    r();
  })();

  // 6 julia
  (function () {
    const cv = $('c-julia'), pk = $('c-picker'), draw = makeGL(cv), drawP = makeGL(pk), hud = $('j-hud');
    if (!draw || !drawP) { noGL(cv); return; }
    const pv = { cx: -0.65, cy: 0, span: 2.6, it: 200 };
    let jx = -0.8, jy = 0.156;
    const dot = document.createElement('div'); dot.className = 'jdot'; pk.parentNode.appendChild(dot);
    function place() {
      const ux = (jx - pv.cx) / pv.span * pk.height + pk.width / 2, uy = (jy - pv.cy) / pv.span * pk.height + pk.height / 2;
      dot.style.left = (ux / pk.width) * 100 + '%'; dot.style.top = (100 - (uy / pk.height) * 100) + '%';
    }
    function r() {
      draw({ cx: 0, cy: 0, span: 3.0, it: 400, julia: true, jx, jy });
      hud.textContent = `c = ${jx.toFixed(4)} ${jy >= 0 ? '+' : '−'} ${Math.abs(jy).toFixed(4)}i`;
      place();
    }
    drawP({ ...pv, julia: false });
    function pick(e) {
      const b = pk.getBoundingClientRect(), p = e.touches ? e.touches[0] : e;
      const ux = ((p.clientX - b.left) / b.width) * pk.width, uy = (1 - (p.clientY - b.top) / b.height) * pk.height;
      jx = pv.cx + ((ux - pk.width / 2) / pk.height) * pv.span; jy = pv.cy + ((uy - pk.height / 2) / pk.height) * pv.span;
      r();
    }
    pk.addEventListener('mousemove', pick);
    pk.addEventListener('touchmove', (e) => { e.preventDefault(); pick(e); }, { passive: false });
    pk.addEventListener('click', pick);
    r();
  })();
})();
