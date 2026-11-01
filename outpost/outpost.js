/* OUTPOST — brooksgroves.com/outpost/
   Concept page for a homemade sensor station. Live USGS gauge on Chambers Creek
   (12091500) plus a solar/battery power-budget calculator. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var TZ = "America/Los_Angeles";
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function fmt(n, d) { return Number(n).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }); }

  /* ---------- the USGS gauge ---------- */
  var series = null;
  function drawChart() {
    var svg = $("gChart");
    if (!series || series.length < 2) { svg.innerHTML = ""; return; }
    var W = 900, H = 220, L = 46, R = 12, T = 14, B = 28;
    var t0 = series[0].t, t1 = series[series.length - 1].t;
    var vals = series.map(function (p) { return p.v; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var pad = (hi - lo) * 0.15 || hi * 0.1 || 1; lo = Math.max(0, lo - pad); hi = hi + pad;
    function x(t) { return L + (t - t0) / (t1 - t0) * (W - L - R); }
    function y(v) { return T + (1 - (v - lo) / (hi - lo)) * (H - T - B); }
    var ink = css("--ink"), stone = css("--stone"), mist = css("--mist"), line = css("--water"), fill = css("--water-fill");
    var s = "";
    for (var i = 0; i <= 3; i++) {
      var v = lo + (hi - lo) * i / 3, yy = y(v);
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + yy + '" y2="' + yy + '" stroke="' + mist + '" stroke-width="1"/>';
      s += '<text x="' + (L - 6) + '" y="' + (yy + 4) + '" text-anchor="end" font-family="DM Mono,monospace" font-size="11" fill="' + stone + '">' + fmt(v, v < 10 ? 1 : 0) + "</text>";
    }
    // a tick at each local midnight
    var d = new Date(t0); d.setMinutes(0, 0, 0);
    for (var k = 0; k < 9 * 24; k++) {
      var tt = new Date(d.getTime() + k * 3600000);
      if (tt > t1) break;
      var hr = +tt.toLocaleString("en-US", { timeZone: TZ, hour: "numeric", hour12: false });
      if (hr === 0 && tt >= t0) {
        var xx = x(tt.getTime());
        s += '<line x1="' + xx + '" x2="' + xx + '" y1="' + T + '" y2="' + (H - B) + '" stroke="' + mist + '" stroke-dasharray="2 4"/>';
        s += '<text x="' + (xx + 4) + '" y="' + (H - 9) + '" font-family="DM Mono,monospace" font-size="11" fill="' + stone + '">' + tt.toLocaleDateString("en-US", { timeZone: TZ, weekday: "short" }) + "</text>";
      }
    }
    var pts = series.map(function (p) { return x(p.t).toFixed(1) + "," + y(p.v).toFixed(1); });
    s += '<path d="M' + pts.join(" L") + " L" + x(t1) + "," + (H - B) + " L" + x(t0) + "," + (H - B) + ' Z" fill="' + fill + '"/>';
    s += '<path d="M' + pts.join(" L") + '" fill="none" stroke="' + line + '" stroke-width="2" vector-effect="non-scaling-stroke"/>';
    var last = series[series.length - 1];
    s += '<circle cx="' + x(last.t) + '" cy="' + y(last.v) + '" r="4.5" fill="' + line + '" stroke="' + css("--white") + '" stroke-width="2"/>';
    s += '<text x="' + L + '" y="' + (T - 2) + '" font-family="DM Mono,monospace" font-size="10" fill="' + stone + '">CFS</text>';
    svg.innerHTML = s;
  }
  function gaugeFail() {
    $("gNote").innerHTML = 'Couldn\'t reach the USGS just now. The gauge is on <a href="https://waterdata.usgs.gov/monitoring-location/USGS-12091500" target="_blank" rel="noopener">its USGS page</a>.';
  }
  fetch("https://waterservices.usgs.gov/nwis/iv/?format=json&sites=12091500&parameterCd=00060,00065&period=P7D&siteStatus=all")
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (j) {
      var ts = (j.value && j.value.timeSeries) || [], q = null, h = null;
      ts.forEach(function (s) {
        var code = s.variable.variableCode[0].value, nd = s.variable.noDataValue;
        var pts = ((s.values[0] || {}).value || []).map(function (p) { return { t: Date.parse(p.dateTime), v: parseFloat(p.value) }; })
          .filter(function (p) { return isFinite(p.v) && p.v !== nd && p.v > -999; });
        if (code === "00060") q = pts; else if (code === "00065") h = pts;
      });
      if (!q || !q.length) { gaugeFail(); return; }
      series = q;
      var last = q[q.length - 1], vals = q.map(function (p) { return p.v; });
      $("gQ").textContent = fmt(last.v, last.v < 10 ? 1 : 0);
      $("gH").textContent = h && h.length ? fmt(h[h.length - 1].v, 2) : "—";
      $("gR").textContent = fmt(Math.min.apply(null, vals), 0) + "–" + fmt(Math.max.apply(null, vals), 0);
      var when = new Date(last.t);
      $("gT").textContent = when.toLocaleTimeString("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
      $("gAge").textContent = when.toLocaleDateString("en-US", { timeZone: TZ, weekday: "short", month: "short", day: "numeric" });
      $("gNote").textContent = "Provisional USGS data, every 15 minutes for the last seven days. Times are Pacific.";
      drawChart();
    })
    .catch(gaugeFail);
  new MutationObserver(drawChart).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  /* ---------- power budget ---------- */
  var ids = ["Rate", "Awake", "Ion", "Ioff", "Bat", "Sol", "Sun"];
  function calc() {
    var g = function (k) { return parseFloat($("p" + k).value); };
    var rate = g("Rate"), awake = g("Awake"), ion = g("Ion"), ioff = g("Ioff"), bat = g("Bat"), sol = g("Sol"), sun = g("Sun");
    $("vRate").textContent = rate + " / hr";
    $("vAwake").textContent = awake + " s";
    $("vIon").textContent = ion + " mA";
    $("vIoff").textContent = ioff.toFixed(2) + " mA";
    $("vBat").textContent = fmt(bat, 0) + " mAh";
    $("vSol").textContent = sol + " W";
    $("vSun").textContent = sun + " h";
    var awakeFrac = Math.min(1, rate * awake / 3600);
    var use = 24 * (awakeFrac * ion + (1 - awakeFrac) * ioff);   // mAh per day
    var gain = sol * sun * 0.7 / 3.7 * 1000;                     // mAh per day
    var days = bat / use;
    $("oUse").textContent = fmt(use, use < 100 ? 1 : 0) + " mAh";
    $("oIn").textContent = fmt(gain, 0) + " mAh";
    $("oDays").textContent = days > 999 ? "years" : fmt(days, days < 10 ? 1 : 0) + " days";
    var v = $("oVerdict");
    if (gain >= use * 1.5) { v.textContent = "Runs forever: the panel covers it with room to spare, even on this kind of day."; v.className = "op-verdict ok"; }
    else if (gain >= use) { v.textContent = "Breaks even. Fine most days, but a long gray stretch will drain it."; v.className = "op-verdict warn"; }
    else { v.textContent = "Slowly losing: about " + fmt((use - gain), 0) + " mAh a day comes out of the battery, so it lasts roughly " + fmt(bat / (use - gain), 0) + " days at this rate."; v.className = "op-verdict bad"; }
  }
  ids.forEach(function (k) { $("p" + k).addEventListener("input", calc); });
  calc();
})();
