/* On the Air — brooksgroves.com/radio/
   Live grey-line map (d3-geo + Natural Earth land), the ISS from its TLE
   (satellite.js), pass predictions for Lakewood, click-to-aim great-circle
   headings, a licence logbook, the General band chart and a phonetic speller.
   The TLE is kept fresh in radio/data/iss-tle.txt by .github/workflows/fetch-iss-tle.yml. */
(function () {
  "use strict";

  var HOME = { name: "Lakewood", lat: 47.1718, lon: -122.5185 };
  var R_EARTH = 6371;
  var TZ = "America/Los_Angeles";
  var $ = function (id) { return document.getElementById(id); };
  var D2R = Math.PI / 180, R2D = 180 / Math.PI;

  /* ---------------- small helpers ---------------- */
  function pad(n) { return String(n).padStart(2, "0"); }
  function fmtTime(d, opts) { return d.toLocaleTimeString("en-US", Object.assign({ timeZone: TZ, hour: "numeric", minute: "2-digit" }, opts || {})); }
  function fmtDay(d) { return d.toLocaleDateString("en-US", { timeZone: TZ, weekday: "short", month: "short", day: "numeric" }); }
  function compass(deg) { var p = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]; return p[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16]; }
  function km(n) { return Math.round(n).toLocaleString("en-US"); }
  function latlon(lat, lon) { return Math.abs(lat).toFixed(1) + "°" + (lat >= 0 ? "N" : "S") + " " + Math.abs(lon).toFixed(1) + "°" + (lon >= 0 ? "E" : "W"); }
  function grid(lat, lon) {
    var L = lon + 180, A = lat + 90, U = "ABCDEFGHIJKLMNOPQR", l = "abcdefghijklmnopqrstuvwx";
    var g = U[Math.floor(L / 20)] + U[Math.floor(A / 10)] + Math.floor((L % 20) / 2) + Math.floor(A % 10);
    return g + l[Math.floor(((L % 2) / 2) * 24)] + l[Math.floor((A % 1) * 24)];
  }
  function gcDist(a, b) { // km
    var p1 = a.lat * D2R, p2 = b.lat * D2R, dl = (b.lon - a.lon) * D2R;
    return R_EARTH * Math.acos(Math.min(1, Math.max(-1, Math.sin(p1) * Math.sin(p2) + Math.cos(p1) * Math.cos(p2) * Math.cos(dl))));
  }
  function bearing(a, b) {
    var p1 = a.lat * D2R, p2 = b.lat * D2R, dl = (b.lon - a.lon) * D2R;
    var y = Math.sin(dl) * Math.cos(p2), x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    return (Math.atan2(y, x) * R2D + 360) % 360;
  }

  /* ---------------- the sun ---------------- */
  function sun(date) {
    var n = date.getTime() / 86400000 + 2440587.5 - 2451545.0;
    var L = (280.460 + 0.9856474 * n) % 360, g = ((357.528 + 0.9856003 * n) % 360) * D2R;
    var lam = (L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * D2R, eps = (23.439 - 0.0000004 * n) * D2R;
    var dec = Math.asin(Math.sin(eps) * Math.sin(lam));
    var ra = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam)) * R2D;
    var gmst = (18.697374558 + 24.06570982441908 * n) % 24 * 15;
    var lon = ((ra - gmst + 540) % 360) - 180;
    return { lat: dec * R2D, lon: lon };
  }
  function sunElev(date, lat, lon) {
    var s = sun(date), p = lat * D2R, d = s.lat * D2R, h = (lon - s.lon) * D2R;
    return Math.asin(Math.sin(p) * Math.sin(d) + Math.cos(p) * Math.cos(d) * Math.cos(h)) * R2D;
  }
  function daylight(e) { return e > 0.5 ? "Daylight" : e > -6 ? "On the grey line" : e > -12 ? "Twilight" : "Night"; }
  function nextSunEvent(from) { // next sunrise or sunset at home
    var up = sunElev(from, HOME.lat, HOME.lon) > -0.833, t = new Date(from);
    for (var i = 0; i < 48 * 60; i++) {
      t = new Date(from.getTime() + i * 60000);
      if ((sunElev(t, HOME.lat, HOME.lon) > -0.833) !== up) return { t: t, rise: !up };
    }
    return null;
  }

  /* ---------------- the ISS ---------------- */
  var satrec = null, tleAge = null;
  function parseTLE(txt) {
    var lines = String(txt).split(/\r?\n/).map(function (s) { return s.trim(); });
    var l1 = lines.filter(function (s) { return /^1 25544/.test(s); })[0], l2 = lines.filter(function (s) { return /^2 25544/.test(s); })[0];
    return l1 && l2 ? [l1, l2] : null;
  }
  function ageDays(rec) { return (Date.now() / 86400000 + 2440587.5) - rec.jdsatepoch; }
  async function loadTLE() {
    var sources = [
      { url: "data/iss-tle.txt", json: false },
      { url: "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE", json: false },
      { url: "https://api.wheretheiss.at/v1/satellites/25544/tles?format=json", json: true }
    ];
    var best = null;
    for (var i = 0; i < sources.length; i++) {
      try {
        var r = await fetch(sources[i].url, { cache: "no-cache" });
        if (!r.ok) continue;
        var tl = sources[i].json ? (function (j) { return j && j.line1 ? [j.line1, j.line2] : null; })(await r.json()) : parseTLE(await r.text());
        if (!tl) continue;
        var rec = satellite.twoline2satrec(tl[0], tl[1]);
        if (!best || ageDays(rec) < ageDays(best)) best = rec;
        if (ageDays(best) < 3) break; // fresh enough, stop looking
      } catch (e) { /* try the next source */ }
    }
    return best;
  }
  function issAt(date) {
    if (!satrec) return null;
    var pv = satellite.propagate(satrec, date);
    if (!pv || !pv.position) return null;
    var gmst = satellite.gstime(date), geo = satellite.eciToGeodetic(pv.position, gmst);
    var v = pv.velocity, speed = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z) * 3600;
    var look = satellite.ecfToLookAngles({ longitude: HOME.lon * D2R, latitude: HOME.lat * D2R, height: 0.08 }, satellite.eciToEcf(pv.position, gmst));
    return { lat: satellite.degreesLat(geo.latitude), lon: satellite.degreesLong(geo.longitude), h: geo.height, speed: speed, el: look.elevation * R2D, az: look.azimuth * R2D };
  }
  function findPasses(from, hours, max) {
    var out = [], step = 20000, t0 = from.getTime(), cur = null;
    for (var t = t0; t < t0 + hours * 3600000 && out.length < max; t += step) {
      var p = issAt(new Date(t)); if (!p) break;
      if (p.el > 0) {
        if (!cur) cur = { rise: new Date(t), riseAz: p.az, max: p.el, maxT: new Date(t) };
        if (p.el > cur.max) { cur.max = p.el; cur.maxT = new Date(t); }
        cur.set = new Date(t); cur.setAz = p.az;
      } else if (cur) { if (cur.max >= 5) out.push(cur); cur = null; }
    }
    if (cur && cur.max >= 5 && out.length < max) out.push(cur);
    return out;
  }
  function quality(el) { return el >= 45 ? ["Overhead, easy", "q-hi"] : el >= 20 ? ["Good", "q-ok"] : el >= 10 ? ["Low; a beam helps", "q-lo"] : ["Marginal", "q-no"]; }

  /* ---------------- the map ---------------- */
  var canvas = $("map"), ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height;
  var projection = null, path = null, base = null, land = null, aimTarget = null;
  var C = { ocean: "#122029", land: "#353a2c", landEdge: "#4a4f3c", grat: "rgba(245,240,232,0.06)", night: "rgba(2,6,12,0.24)",
            grey: "217,166,63", iss: "#e8805f", home: "#f5f0e8", aim: "#d9a63f" };

  function buildBase() {
    base = document.createElement("canvas"); base.width = W; base.height = H;
    var b = base.getContext("2d"), p = d3.geoPath(projection, b);
    b.fillStyle = C.ocean; b.fillRect(0, 0, W, H);
    b.beginPath(); p(d3.geoGraticule().step([30, 30])()); b.strokeStyle = C.grat; b.lineWidth = 1; b.stroke();
    if (land) { b.beginPath(); p(land); b.fillStyle = C.land; b.fill(); b.strokeStyle = C.landEdge; b.lineWidth = 0.8; b.stroke(); }
  }
  function draw(now, iss) {
    if (!projection) return;
    if (!base) buildBase();
    ctx.drawImage(base, 0, 0);
    var s = sun(now), anti = [s.lon + 180, -s.lat], circ = d3.geoCircle().center(anti);
    // night, darker toward the middle (civil, nautical, astronomical twilight)
    [90, 84, 78, 72].forEach(function (r) { ctx.beginPath(); path(circ.radius(r)()); ctx.fillStyle = C.night; ctx.fill(); });
    // the grey line: a warm band between sunset and civil dusk
    ctx.beginPath(); path(circ.radius(90.5)()); path(circ.radius(84)()); ctx.fillStyle = "rgba(" + C.grey + ",0.16)"; ctx.fill("evenodd");
    ctx.beginPath(); path(circ.radius(90)()); ctx.strokeStyle = "rgba(" + C.grey + ",0.75)"; ctx.lineWidth = 1.6; ctx.stroke();

    // aim path
    if (aimTarget) {
      ctx.beginPath(); path({ type: "LineString", coordinates: [[HOME.lon, HOME.lat], [aimTarget.lon, aimTarget.lat]] });
      ctx.setLineDash([]); ctx.strokeStyle = C.aim; ctx.lineWidth = 2.5; ctx.stroke();
      var tp = projection([aimTarget.lon, aimTarget.lat]);
      ctx.beginPath(); ctx.arc(tp[0], tp[1], 6, 0, 7); ctx.fillStyle = C.aim; ctx.fill();
    }

    // ISS: track, footprint, dot
    if (iss) {
      var track = [], past = [];
      for (var m = -45; m <= 95; m += 1) {
        var q = issAt(new Date(now.getTime() + m * 60000)); if (!q) continue;
        (m <= 0 ? past : track).push([q.lon, q.lat]);
      }
      track.unshift([iss.lon, iss.lat]); past.push([iss.lon, iss.lat]);
      ctx.beginPath(); path({ type: "LineString", coordinates: past }); ctx.setLineDash([3, 5]); ctx.strokeStyle = "rgba(232,128,95,0.45)"; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.beginPath(); path({ type: "LineString", coordinates: track }); ctx.setLineDash([]); ctx.strokeStyle = "rgba(232,128,95,0.8)"; ctx.lineWidth = 1.6; ctx.stroke();
      var fr = Math.acos(R_EARTH / (R_EARTH + iss.h)) * R2D;
      ctx.beginPath(); path(d3.geoCircle().center([iss.lon, iss.lat]).radius(fr)()); ctx.fillStyle = "rgba(232,128,95,0.10)"; ctx.fill(); ctx.strokeStyle = "rgba(232,128,95,0.7)"; ctx.lineWidth = 1.2; ctx.stroke();
      var ip = projection([iss.lon, iss.lat]);
      ctx.beginPath(); ctx.arc(ip[0], ip[1], 11, 0, 7); ctx.fillStyle = "rgba(232,128,95,0.25)"; ctx.fill();
      ctx.beginPath(); ctx.arc(ip[0], ip[1], 5.5, 0, 7); ctx.fillStyle = C.iss; ctx.fill(); ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.font = "600 15px 'DM Mono', monospace"; ctx.fillStyle = "#f5f0e8"; ctx.textAlign = ip[0] > W - 60 ? "right" : "left";
      ctx.fillText("ISS", ip[0] + (ip[0] > W - 60 ? -14 : 14), ip[1] - 10);
    }

    // home
    var hp = projection([HOME.lon, HOME.lat]);
    ctx.beginPath(); ctx.arc(hp[0], hp[1], 5, 0, 7); ctx.fillStyle = C.home; ctx.fill();
    ctx.beginPath(); ctx.arc(hp[0], hp[1], 10, 0, 7); ctx.strokeStyle = "rgba(245,240,232,0.6)"; ctx.lineWidth = 1.5; ctx.stroke();

    // sun
    var sp = projection([s.lon, s.lat]);
    ctx.beginPath(); ctx.arc(sp[0], sp[1], 9, 0, 7); ctx.fillStyle = "rgba(" + C.grey + ",0.95)"; ctx.fill();
    ctx.beginPath(); ctx.arc(sp[0], sp[1], 16, 0, 7); ctx.strokeStyle = "rgba(" + C.grey + ",0.4)"; ctx.lineWidth = 2; ctx.stroke();
  }

  /* ---------------- aiming ---------------- */
  var TARGETS = [
    { name: "Tokyo", lat: 35.68, lon: 139.69 }, { name: "Sydney", lat: -33.87, lon: 151.21 },
    { name: "Cape Town", lat: -33.92, lon: 18.42 }, { name: "McMurdo Station", lat: -77.85, lon: 166.67 },
    { name: "London", lat: 51.51, lon: -0.13 }, { name: "Honolulu", lat: 21.31, lon: -157.86 },
    { name: "Rio de Janeiro", lat: -22.91, lon: -43.17 }, { name: "Reykjavík", lat: 64.15, lon: -21.94 }
  ];
  function renderTargets() {
    $("targets").innerHTML = TARGETS.map(function (t, i) {
      return '<button type="button" class="oa-chip" data-t="' + i + '" aria-pressed="' + (aimTarget && aimTarget.name === t.name) + '">' + t.name + "</button>";
    }).join("");
  }
  function aim(t) {
    aimTarget = t; renderTargets();
    var d = gcDist(HOME, t), b = bearing(HOME, t), lp = (b + 180) % 360, e = sunElev(new Date(), t.lat, t.lon);
    var hops = Math.max(1, Math.ceil(d / 4000));
    var local = new Date(Date.now() + (t.lon / 15) * 3600000);
    $("aim").innerHTML =
      '<div class="oa-aim-name"><b>' + (t.name || latlon(t.lat, t.lon)) + '</b><span>' + latlon(t.lat, t.lon) + " · grid " + grid(t.lat, t.lon) + "</span></div>" +
      '<div class="oa-aim-grid">' +
      '<div><span class="oa-k">Beam heading</span><span class="oa-big">' + Math.round(b) + "°</span><span class=\"oa-s\">" + compass(b) + " · long path " + Math.round(lp) + "°</span></div>" +
      '<div><span class="oa-k">Distance</span><span class="oa-big">' + km(d) + " km</span><span class=\"oa-s\">" + km(d * 0.621371) + " mi · long path " + km(40030 - d) + " km</span></div>" +
      '<div><span class="oa-k">Skips off the sky</span><span class="oa-big">about ' + hops + "</span><span class=\"oa-s\">F2-layer hops of up to ~4,000 km</span></div>" +
      '<div><span class="oa-k">There right now</span><span class="oa-big">' + daylight(e) + "</span><span class=\"oa-s\">Sun " + Math.round(e) + "° · solar time " + pad(local.getUTCHours()) + ":" + pad(local.getUTCMinutes()) + "</span></div>" +
      "</div>";
    tick();
  }
  canvas.addEventListener("click", function (ev) {
    if (!projection) return;
    var r = canvas.getBoundingClientRect(), x = (ev.clientX - r.left) * W / r.width, y = (ev.clientY - r.top) * H / r.height;
    var ll = projection.invert([x, y]); if (!ll) return;
    aim({ name: "", lat: ll[1], lon: ll[0] });
  });
  $("targets").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-t]"); if (b) aim(TARGETS[+b.dataset.t]);
  });

  /* ---------------- live readouts ---------------- */
  var passes = [];
  function tick() {
    var now = new Date();
    $("ro-utc").textContent = pad(now.getUTCHours()) + ":" + pad(now.getUTCMinutes()) + ":" + pad(now.getUTCSeconds()) + "Z";
    $("ro-local").textContent = "Lakewood " + fmtTime(now) + " · " + fmtDay(now);

    var e = sunElev(now, HOME.lat, HOME.lon), ev = nextSunEvent(now);
    $("ro-sun").textContent = daylight(e);
    $("ro-sun2").textContent = "Sun " + Math.round(e) + "°" + (ev ? " · " + (ev.rise ? "rises " : "sets ") + fmtTime(ev.t) : "");

    var iss = issAt(now);
    if (iss) {
      var over = land && d3.geoContains(land, [iss.lon, iss.lat]) ? "land" : "water";
      $("ro-iss").textContent = latlon(iss.lat, iss.lon);
      $("ro-iss2").textContent = "Over " + over + " · " + Math.round(iss.h) + " km up · " + km(iss.speed) + " km/h";
      if (iss.el > 0) {
        $("ro-pass").textContent = "Overhead now";
        $("ro-pass2").textContent = Math.round(iss.el) + "° up, look " + compass(iss.az) + " · repeater 437.800";
      } else {
        passes = passes.filter(function (p) { return p.set > now; });
        var p = passes[0];
        if (p) {
          var mins = Math.round((p.rise - now) / 60000), h = Math.floor(mins / 60);
          $("ro-pass").textContent = "in " + (h ? h + " h " : "") + (mins % 60) + " min";
          $("ro-pass2").textContent = fmtTime(p.rise) + " · up to " + Math.round(p.max) + "° · " + compass(p.riseAz) + " → " + compass(p.setAz);
        }
      }
    }
    draw(now, iss);
  }
  function renderPasses() {
    var rows = findPasses(new Date(), 72, 8);
    passes = rows.slice();
    $("passRows").innerHTML = rows.length ? rows.map(function (p) {
      var q = quality(p.max);
      return "<tr><td>" + fmtDay(p.rise) + '</td><td class="oa-mono">' + fmtTime(p.rise) + '</td><td class="oa-mono">' + fmtTime(p.maxT) + '</td><td class="oa-mono">' + fmtTime(p.set) +
        '</td><td class="oa-mono">' + compass(p.riseAz) + " → " + compass(p.setAz) + '</td><td class="oa-mono">' + Math.round(p.max) + '°</td><td><span class="oa-q ' + q[1] + '">' + q[0] + "</span></td></tr>";
    }).join("") : '<tr><td colspan="7" class="oa-fine">No passes above 5° in the next three days.</td></tr>';
    if (satrec) $("passNote").textContent = "Times are Lakewood local. Orbit data is " + (ageDays(satrec) < 1 ? "less than a day" : Math.round(ageDays(satrec)) + " days") + " old.";
  }
  function issUnavailable() {
    $("ro-iss").textContent = "Orbit data unavailable";
    $("ro-iss2").textContent = "Try again in a while";
    $("ro-pass").textContent = "Unavailable";
    $("ro-pass2").innerHTML = 'See <a href="https://www.heavens-above.com/PassSummary.aspx?satid=25544&lat=47.1718&lng=-122.5185&loc=Lakewood&tz=PST" target="_blank" rel="noopener">Heavens-Above</a>';
    $("passRows").innerHTML = '<tr><td colspan="7" class="oa-fine">Couldn\'t load the ISS orbit just now. <a href="https://www.heavens-above.com/PassSummary.aspx?satid=25544&lat=47.1718&lng=-122.5185&loc=Lakewood&tz=PST" target="_blank" rel="noopener">Heavens-Above</a> has the passes.</td></tr>';
  }

  /* ---------------- logbook (per browser) ---------------- */
  var STEPS = [
    ["frn", "Get an FCC Registration Number (FRN) in the FCC's CORES system. You need it at the exam."],
    ["books", "Get the books: Ham Radio License Manual (6th ed.) and General Class License Manual (10th ed.)"],
    ["club", "Visit the Radio Club of Tacoma clubhouse on a Saturday"],
    ["tstudy", "Work through the Technician question pool on HamStudy"],
    ["tprac", "Score 85% or better on three Technician practice exams in a row"],
    ["book", "Book the Technician exam at the clubhouse (Feb 9 or Mar 9, 2027)"],
    ["tpass", "Pass Technician"],
    ["fee", "Pay the $35 FCC fee within 10 days of the email"],
    ["call", "See my call sign in the FCC database"],
    ["gstudy", "Work through the General pool (good through June 30, 2027)"],
    ["gprac", "Score 85% or better on three General practice exams in a row"],
    ["pass", "Pass General by the June 8, 2027 session"],
    ["chirp", "Program the radio with the South Sound Channel Plan"],
    ["net", "Check in to the Tuesday night W7DK net"],
    ["iss", "Hear the ISS, then work it through the repeater"],
    ["hf", "Make a first HF contact"],
    ["ft8", "Get heard on another continent, seen on PSK Reporter"],
    ["pota", "Activate a park"],
    ["dxcc", "Confirm 100 countries for DXCC"]
  ];
  var KEY = "bg_radio_log", done = {};
  try { done = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { done = {}; }
  function renderLog() {
    var n = STEPS.filter(function (s) { return done[s[0]]; }).length;
    $("checks").innerHTML = STEPS.map(function (s) {
      return '<li><label><input type="checkbox" id="lg-' + s[0] + '" data-k="' + s[0] + '"' + (done[s[0]] ? " checked" : "") + "><span>" + s[1] + "</span></label></li>";
    }).join("");
    $("logPct").textContent = n + " of " + STEPS.length;
    $("logBar").style.width = (100 * n / STEPS.length) + "%";
  }
  $("checks").addEventListener("change", function (e) {
    var k = e.target.dataset.k; if (!k) return;
    if (e.target.checked) done[k] = Date.now(); else delete done[k];
    try { localStorage.setItem(KEY, JSON.stringify(done)); } catch (_) {}
    renderLog();
    var box = $("lg-" + k); if (box) box.focus();
  });

  /* ---------------- band chart ---------------- */
  var BANDS = [
    { b: "160 m", lo: 1.8, hi: 2.0, G: [["all", 1.8, 2.0]], T: [], ft8: 1.840, note: "Winter nights; needs a big antenna" },
    { b: "80 m", lo: 3.5, hi: 4.0, G: [["cw", 3.525, 3.6], ["ph", 3.8, 4.0]], T: [["cw", 3.525, 3.6]], ft8: 3.573, note: "Nights; regional nets" },
    { b: "40 m", lo: 7.0, hi: 7.3, G: [["cw", 7.025, 7.125], ["ph", 7.175, 7.3]], T: [["cw", 7.025, 7.125]], ft8: 7.074, note: "Night for distance, day for the Northwest" },
    { b: "30 m", lo: 10.1, hi: 10.15, G: [["cw", 10.1, 10.15]], T: [], ft8: 10.136, note: "Morse and data only; quiet and steady" },
    { b: "20 m", lo: 14.0, hi: 14.35, G: [["cw", 14.025, 14.15], ["ph", 14.225, 14.35]], T: [], ft8: 14.074, note: "The workhorse, day and dusk" },
    { b: "17 m", lo: 18.068, hi: 18.168, G: [["cw", 18.068, 18.11], ["ph", 18.11, 18.168]], T: [], ft8: 18.100, note: "Like 20 m, with less crowding" },
    { b: "15 m", lo: 21.0, hi: 21.45, G: [["cw", 21.025, 21.2], ["ph", 21.275, 21.45]], T: [["cw", 21.025, 21.2]], ft8: 21.074, note: "Daytime DX when the sun is busy" },
    { b: "12 m", lo: 24.89, hi: 24.99, G: [["cw", 24.89, 24.93], ["ph", 24.93, 24.99]], T: [], ft8: 24.915, note: "A sunspot band" },
    { b: "10 m", lo: 28.0, hi: 29.7, G: [["cw", 28.0, 28.3], ["ph", 28.3, 29.7]], T: [["cw", 28.0, 28.3], ["ph", 28.3, 28.5]], ft8: 28.074, note: "Wide open near solar max; Technicians get voice here" }
  ];
  var cls = "G";
  function f(n) { return n < 10 ? n.toFixed(3) : n.toFixed(3).replace(/0+$/, "").replace(/\.$/, ""); }
  function renderBands() {
    $("bandchart").innerHTML = BANDS.map(function (bd) {
      var span = bd.hi - bd.lo, segs = bd[cls];
      var html = segs.map(function (s) {
        return '<span class="oa-seg-' + s[0] + '" style="left:' + (100 * (s[1] - bd.lo) / span) + "%;width:" + (100 * (s[2] - s[1]) / span) + '%" title="' + f(s[1]) + "–" + f(s[2]) + ' MHz"></span>';
      }).join("");
      var ft = '<span class="oa-ft8" style="left:' + (100 * (bd.ft8 - bd.lo) / span) + '%" title="FT8 ' + bd.ft8.toFixed(3) + ' MHz"></span>';
      var mine = segs.length ? segs.map(function (s) { return f(s[1]) + "–" + f(s[2]); }).join(", ") + " MHz" : (cls === "T" ? "Needs General" : "");
      return '<div class="oa-band"><div class="oa-band-name">' + bd.b + '</div><div class="oa-band-bar"' + (segs.length ? "" : ' data-empty="1"') + ">" + html + ft + "</div>" +
        '<div class="oa-band-info"><span class="oa-mono">' + mine + "</span><span>" + bd.note + "</span></div></div>";
    }).join("");
    $("exKey").textContent = cls === "G" ? "Extra only" : "Needs General or Extra";
    $("showG").setAttribute("aria-pressed", cls === "G"); $("showT").setAttribute("aria-pressed", cls === "T");
  }
  $("showG").addEventListener("click", function () { cls = "G"; renderBands(); });
  $("showT").addEventListener("click", function () { cls = "T"; renderBands(); });

  /* ---------------- phonetics ---------------- */
  var NATO = { A: "Alfa", B: "Bravo", C: "Charlie", D: "Delta", E: "Echo", F: "Foxtrot", G: "Golf", H: "Hotel", I: "India", J: "Juliett", K: "Kilo", L: "Lima", M: "Mike", N: "November", O: "Oscar", P: "Papa", Q: "Quebec", R: "Romeo", S: "Sierra", T: "Tango", U: "Uniform", V: "Victor", W: "Whiskey", X: "X-ray", Y: "Yankee", Z: "Zulu",
    "0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Niner", "/": "Stroke" };
  function spell() {
    var s = $("spellIn").value.toUpperCase().split("").filter(function (c) { return NATO[c]; });
    $("spellOut").textContent = s.length ? s.map(function (c) { return NATO[c]; }).join(" · ") : "Letters and numbers only";
  }
  $("spellIn").addEventListener("input", spell);
  $("nato").innerHTML = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map(function (c) { return "<span><b>" + c + "</b>" + NATO[c] + "</span>"; }).join("");

  /* ---------------- boot ---------------- */
  renderLog(); renderBands(); spell(); renderTargets();
  var ready = typeof d3 !== "undefined" && d3.geoEquirectangular;
  if (ready) {
    projection = d3.geoEquirectangular().fitSize([W, H], { type: "Sphere" });
    path = d3.geoPath(projection, ctx);
    tick();
    fetch("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json").then(function (r) { return r.json(); }).then(function (t) {
      land = topojson.feature(t, t.objects.land); base = null; tick();
    }).catch(function () { /* the map still works over a plain ocean */ });
  } else {
    canvas.hidden = true;
  }
  if (typeof satellite !== "undefined") {
    loadTLE().then(function (rec) {
      if (!rec) { issUnavailable(); return; }
      satrec = rec; renderPasses(); tick();
      setInterval(renderPasses, 10 * 60000);
    });
  } else { issUnavailable(); }
  setInterval(tick, 1000);
})();
