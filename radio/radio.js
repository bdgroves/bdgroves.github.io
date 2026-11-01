/* South Sound Channel Plan — brooksgroves.com/radio/
   Repeaters near the South Sound on a range scope, exported as a CHIRP CSV.
   Data: Radio Club of Tacoma club & area list (Oct 31, 2026) + RepeaterBook WW7CH.
   Pins are placed at the named site (approximate), not surveyed tower positions. */
(function () {
  "use strict";

  var BANDS = {
    "6":   { l: "6 m",     c: "--band-6" },
    "2":   { l: "2 m",     c: "--band-2" },
    "125": { l: "1.25 m",  c: "--band-125" },
    "70":  { l: "70 cm",   c: "--band-70" },
    "wx":  { l: "NOAA",    c: "--band-wx" },
    "sx":  { l: "Simplex", c: "--band-sx" }
  };

  // output MHz, shift direction, shift MHz, tone up, tone down, call, site, lat, lon, short name, note
  var R = [
    [53.010, "-", 1.7, 100, 100, "K7NP", "University Place", 47.235, -122.548, "K7NP UP", ""],
    [53.170, "-", 1.7, 100, 0, "K7LWH", "Kirkland, Rose Hill", 47.680, -122.180, "LWH 6M", "Linked"],
    [53.190, "-", 1.7, 100, 0, "K7HW", "Tacoma", 47.240, -122.460, "K7HW 6M", ""],
    [53.230, "-", 1.7, 100, 103.5, "K7TGU", "University Place", 47.225, -122.535, "TGU UP", ""],
    [53.290, "-", 1.7, 100, 0, "W7AW", "Seattle", 47.560, -122.380, "W7AW 6M", ""],
    [53.390, "-", 1.7, 100, 103.5, "K7TGU", "Puyallup Ridge", 47.170, -122.270, "TGU PUY", "Solar powered, brief contacts"],
    [53.410, "-", 1.7, 100, 100, "W7PFR", "Eatonville", 46.867, -122.266, "PFR 6M", ""],
    [53.570, "-", 1.7, 100, 0, "W7SIX", "Capitol Peak", 46.968, -123.137, "CAP 6M", ""],
    [145.210, "-", 0.6, 141.3, 0, "W7DK", "N. Tacoma / Pt. Defiance", 47.300, -122.520, "DK NTAC", "Club repeater"],
    [145.330, "-", 0.6, 179.9, 0, "K7NWS", "West Tiger Mtn", 47.506, -121.990, "WTIGER", ""],
    [145.370, "-", 0.6, 136.5, 0, "W7AAO", "Grass Mtn, Enumclaw", 47.190, -121.800, "GRASS", ""],
    [145.470, "-", 0.6, 100, 0, "K7CPR", "Capitol Peak", 46.968, -123.137, "CAP PK", ""],
    [146.620, "-", 0.6, 103.5, 0, "WW7RA", "Gold Mtn, Bremerton", 47.548, -122.785, "GOLD 2M", ""],
    [146.660, "-", 0.6, 103.5, 0, "WA7ST", "SeaTac", 47.440, -122.300, "SEATAC", ""],
    [146.700, "-", 0.6, 103.5, 0, "W7EAT", "Eatonville, Pack Forest", 46.840, -122.310, "EAT 2M", "Linked to the Rainier system"],
    [146.760, "-", 0.6, 103.5, 0, "WA7FW", "Federal Way", 47.320, -122.310, "FWAY 76", ""],
    [146.780, "-", 0.6, 103.5, 103.5, "WW7CH", "Paradise, Mt Rainier", 46.785, -121.742, "PARADIS", "SAR first; AllStar 41340"],
    [146.820, "-", 0.6, 103.5, 0, "K7LED", "East Tiger Mtn", 47.480, -121.930, "ETIGER", ""],
    [146.940, "-", 0.6, 103.5, 0, "K7HW", "Tacoma Mall", 47.215, -122.467, "TAC MAL", ""],
    [146.960, "-", 0.6, 103.5, 0, "WW7PSR", "Capitol Hill, Seattle", 47.625, -122.320, "PSRG", ""],
    [147.040, "+", 0.6, 103.5, 0, "WA7FW", "Federal Way", 47.320, -122.310, "FWAY 04", ""],
    [147.080, "+", 0.6, 110.9, 0, "W7WWI", "Tiger Mtn", 47.490, -121.970, "TIGER08", ""],
    [147.140, "+", 0.6, 123, 123, "WB7DOB", "Baldi, Enumclaw", 47.170, -121.860, "BALDI", ""],
    [147.140, "+", 0.6, 114.8, 114.8, "WB7DOB", "Packwood", 46.610, -121.680, "PACKWD", ""],
    [147.240, "+", 0.6, 123, 0, "K7SYE", "Auburn", 47.307, -122.228, "AUBURN", ""],
    [147.280, "+", 0.6, 103.5, 103.5, "W7DK", "Central Tacoma", 47.2475, -122.4985, "DK TAC", "Club net Tue 7:30 pm; FM + C4FM"],
    [147.380, "+", 0.6, 103.5, 103.5, "W7DK", "Crawford Mtn", 46.810, -122.700, "CRAWFRD", "Club repeater"],
    [223.980, "-", 1.6, 100, 0, "N7NW", "East Tiger Mtn", 47.480, -121.930, "N7NW", ""],
    [224.120, "-", 1.6, 103.5, 0, "K7LED", "East Tiger Mtn", 47.480, -121.930, "LED 220", ""],
    [224.180, "-", 1.6, 103.5, 0, "W7EAT", "Graham", 47.050, -122.290, "GRAHAM", ""],
    [224.200, "-", 1.6, 123, 123, "W7TJL", "Gig Harbor", 47.330, -122.580, "GIG 220", ""],
    [224.460, "-", 1.6, 103.5, 0, "NT7H", "Crawford Mtn", 46.810, -122.700, "NT7H220", ""],
    [440.625, "+", 5, 103.5, 103.5, "W7DK", "Central Tacoma", 47.2475, -122.4985, "DK TACU", "FM + C4FM"],
    [441.400, "+", 5, 103.5, 0, "NT7H", "Crawford Mtn", 46.810, -122.700, "NT7H440", ""],
    [442.650, "+", 5, 103.5, 0, "WW7RA", "Gold Mtn, Bremerton", 47.548, -122.785, "GOLD440", ""],
    [442.725, "+", 5, 103.5, 103.5, "W7EAT", "Eatonville", 46.867, -122.266, "EAT440", ""],
    [443.975, "+", 5, 103.5, 0, "W7PFR", "Eatonville", 46.867, -122.266, "PFR440", ""]
  ];

  var EXTRAS = [
    { id: "wx1", band: "wx", f: 162.550, call: "KHB60", site: "Seattle (Cougar Mtn)", lat: 47.53, lon: -122.11, nm: "WX SEA", note: "NOAA weather, listen only" },
    { id: "wx2", band: "wx", f: 162.425, call: "WWG24", site: "Puget Sound Marine", lat: null, lon: null, nm: "WX MAR", note: "NOAA marine weather, listen only" },
    { id: "sx1", band: "sx", f: 146.520, call: "Simplex", site: "National 2 m calling", lat: null, lon: null, nm: "CALL 2M", note: "" },
    { id: "sx2", band: "sx", f: 446.000, call: "Simplex", site: "National 70 cm calling", lat: null, lon: null, nm: "CALL440", note: "", req: "70" },
    { id: "sx3", band: "sx", f: 223.500, call: "Simplex", site: "National 1.25 m calling", lat: null, lon: null, nm: "CALL220", note: "", req: "125" },
    { id: "sx4", band: "sx", f: 52.525, call: "Simplex", site: "National 6 m calling", lat: null, lon: null, nm: "CALL 6M", note: "", req: "6" }
  ];

  var HOMES = [["Lakewood", 47.1718, -122.5185], ["Tacoma", 47.2529, -122.4443], ["Seattle", 47.6062, -122.3321], ["Olympia", 47.0379, -122.9007], ["Puyallup", 47.1854, -122.2929]];

  function bandOf(f) { return f < 54 ? "6" : f < 149 ? "2" : f < 226 ? "125" : "70"; }
  var rows = R.map(function (r, i) {
    return { id: "r" + i, band: bandOf(r[0]), f: r[0], dup: r[1], off: r[2], up: r[3], dn: r[4], call: r[5], site: r[6], lat: r[7], lon: r[8], nm: r[9], note: r[10], use: true };
  });
  var st = { home: 0, bands: ["2", "70"], range: 50, extras: { wx1: 1, wx2: 1, sx1: 1, sx2: 1 }, hot: null };

  function $(id) { return document.getElementById(id); }
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function geo(lat, lon) {
    var h = HOMES[st.home], k = Math.cos(h[1] * Math.PI / 180);
    var dx = (lon - h[2]) * 69.17 * k, dy = (lat - h[1]) * 69.05;
    return { d: Math.hypot(dx, dy), dx: dx, dy: dy };
  }
  function inBand(b) { return st.bands.indexOf(b) !== -1; }
  function visible() {
    return rows.filter(function (r) { return inBand(r.band) && geo(r.lat, r.lon).d <= st.range; })
      .sort(function (a, b) { return geo(a.lat, a.lon).d - geo(b.lat, b.lon).d; });
  }
  function extrasOn() { return EXTRAS.filter(function (e) { return st.extras[e.id] && (!e.req || inBand(e.req)); }); }
  function plan() { return visible().filter(function (r) { return r.use; }).concat(extrasOn()); }
  function toneTxt(r) {
    if (!r.up) return "—";
    if (r.dn && r.dn !== r.up) return r.up + "/" + r.dn;
    return r.dn ? r.up + " ⇄" : String(r.up);
  }

  function renderExtras() {
    $("extras").innerHTML = EXTRAS.filter(function (e) { return !e.req || inBand(e.req); }).map(function (e) {
      return '<button type="button" class="rp-chip" style="--c:var(' + BANDS[e.band].c + ')" aria-pressed="' + (!!st.extras[e.id]) + '" data-x="' + e.id + '">' + esc(e.nm) + " " + e.f.toFixed(3) + "</button>";
    }).join("");
  }
  function renderLegend() {
    var h = st.bands.map(function (b) { return '<span style="--c:var(' + BANDS[b].c + ')"><i></i>' + BANDS[b].l + "</span>"; }).join("");
    if (st.extras.wx1) h += '<span style="--c:var(--band-wx)"><i></i>NOAA</span>';
    $("legend").innerHTML = h;
  }

  function renderScope() {
    var S = 360, c = S / 2, R0 = 158, sc = R0 / st.range;
    var line = css("--mist"), mut = css("--stone"), ink = css("--ink"), acc = css("--rust"), paper = css("--white");
    var s = "", q, r;
    for (q = 1; q <= 4; q++) {
      r = R0 * q / 4;
      s += '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="' + line + '" stroke-width="1"/>';
      s += '<text x="' + (c + 4) + '" y="' + (c - r + 12) + '" font-family="DM Mono,monospace" font-size="10" fill="' + mut + '">' + Math.round(st.range * q / 4) + " mi</text>";
    }
    s += '<line x1="' + c + '" y1="' + (c - R0) + '" x2="' + c + '" y2="' + (c + R0) + '" stroke="' + line + '"/>';
    s += '<line x1="' + (c - R0) + '" y1="' + c + '" x2="' + (c + R0) + '" y2="' + c + '" stroke="' + line + '"/>';
    s += '<text x="' + c + '" y="14" text-anchor="middle" font-family="Playfair Display,serif" font-weight="700" font-size="13" fill="' + mut + '">N</text>';

    var pts = [];
    rows.forEach(function (row) {
      if (!inBand(row.band)) return;
      var g = geo(row.lat, row.lon);
      if (g.d <= st.range) pts.push({ r: row, g: g, rep: true });
    });
    EXTRAS.forEach(function (e) {
      if (e.lat == null || !st.extras[e.id]) return;
      var g = geo(e.lat, e.lon);
      if (g.d <= st.range) pts.push({ r: e, g: g, rep: false });
    });
    var seen = {};
    pts.forEach(function (p) {
      var key = p.r.lat + "," + p.r.lon, n = seen[key] = (seen[key] || 0) + 1;
      var a = (n - 1) * 1.3, off = n > 1 ? 5 : 0;
      var x = c + p.g.dx * sc + Math.cos(a) * off, y = c - p.g.dy * sc + Math.sin(a) * off;
      var col = css(BANDS[p.r.band].c), on = p.rep ? p.r.use : true, hot = st.hot === p.r.id;
      s += '<g class="rp-pin" data-id="' + p.r.id + '"' + (p.rep ? ' tabindex="0" role="button" aria-label="' + esc(p.r.call + " " + p.r.f.toFixed(3) + ", " + p.r.site + (on ? ", included" : ", skipped")) + '"' : "") + ">" +
        "<title>" + esc(p.r.call + " " + p.r.f.toFixed(3) + " · " + p.r.site + " · about " + p.g.d.toFixed(0) + " mi") + "</title>" +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (hot ? 8 : 5.5) + '" fill="' + (on ? col : paper) + '" stroke="' + col + '" stroke-width="2"/></g>';
    });
    s += '<circle cx="' + c + '" cy="' + c + '" r="4" fill="' + acc + '"/>';
    s += '<text x="' + (c + 7) + '" y="' + (c + 15) + '" font-family="DM Mono,monospace" font-size="10" letter-spacing="1" fill="' + ink + '">' + HOMES[st.home][0].toUpperCase() + "</text>";
    $("scope").innerHTML = s;
  }

  function renderRows() {
    var v = visible(), m = +$("start").value || 0;
    $("rows").innerHTML = v.map(function (r) {
      var g = geo(r.lat, r.lon), mem = r.use ? String(m++).padStart(3, "0") : "—";
      return '<tr class="' + (r.use ? "" : "off") + (st.hot === r.id ? " hot" : "") + '" data-id="' + r.id + '">' +
        '<td><input type="checkbox" id="u-' + r.id + '"' + (r.use ? " checked" : "") + ' aria-label="Include ' + esc(r.call + " " + r.f) + '"></td>' +
        '<td class="rp-num">' + mem + "</td>" +
        '<td><span class="rp-band" style="--c:var(' + BANDS[r.band].c + ')">' + BANDS[r.band].l + "</span></td>" +
        '<td class="rp-num">' + r.f.toFixed(3) + "</td>" +
        '<td class="rp-num">' + r.dup + r.off + "</td>" +
        '<td class="rp-num">' + toneTxt(r) + "</td>" +
        '<td class="rp-num">' + esc(r.call) + "</td>" +
        "<td>" + esc(r.site) + (r.note ? '<div class="rp-note">' + esc(r.note) + "</div>" : "") + "</td>" +
        '<td class="rp-num">~' + g.d.toFixed(0) + " mi</td></tr>";
    }).join("") || '<tr><td colspan="9" class="rp-note" style="padding:18px 8px">No repeaters inside ' + st.range + " mi on these bands. Widen the range or add a band.</td></tr>";
    var n = v.filter(function (r) { return r.use; }).length;
    $("count").textContent = n + " of " + v.length + " repeaters in range";
  }

  function csv() {
    var len = +$("namelen").value, tsql = $("tsql").value === "tsql", m = +$("start").value || 0;
    var out = ["Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,RxDtcsCode,CrossMode,Mode,TStep,Skip,Comment"];
    plan().forEach(function (r) {
      var name = (r.nm || r.call).toUpperCase().slice(0, len).trim();
      var isR = r.dup !== undefined, tone = "", rt = 88.5, ct = 88.5;
      if (isR && r.up) {
        if (tsql && r.dn && r.dn === r.up) { tone = "TSQL"; rt = ct = r.up; }
        else { tone = "Tone"; rt = r.up; }
      }
      var comment = (r.call + " " + r.site + (r.note ? " - " + r.note : "")).replace(/[,"]/g, " ");
      out.push([m++, name, r.f.toFixed(6), isR ? r.dup : "", isR ? r.off.toFixed(6) : "0.000000", tone,
        rt.toFixed(1), ct.toFixed(1), "023", "NN", "023", "Tone->Tone", "FM", "5.00", "", comment].join(","));
    });
    return out.join("\r\n") + "\r\n";
  }

  function renderAll() {
    $("rangeVal").textContent = st.range;
    $("ro-r").textContent = st.range + " mi";
    $("ro-home").textContent = HOMES[st.home][0];
    renderExtras(); renderLegend(); renderScope(); renderRows();
    var n = plan().length;
    $("ro-n").textContent = String(n).padStart(2, "0");
    $("exCount").textContent = n + " channels";
    $("csv").value = csv();
  }

  function toggle(id) {
    var r = rows.filter(function (x) { return x.id === id; })[0];
    if (!r) return;
    r.use = !r.use; st.hot = id; renderAll();
    var tr = document.querySelector('tr[data-id="' + id + '"]');
    if (tr && window.matchMedia("(min-width:900px)").matches) tr.scrollIntoView({ block: "nearest" });
  }

  function say(t) { $("status").textContent = t; }

  $("home").innerHTML = HOMES.map(function (h, i) { return '<option value="' + i + '">' + h[0] + "</option>"; }).join("");
  $("home").addEventListener("change", function (e) { st.home = +e.target.value; renderAll(); });
  $("radio").addEventListener("change", function (e) { st.bands = e.target.value.split(","); renderAll(); });
  $("range").addEventListener("input", function (e) { st.range = +e.target.value; renderAll(); });
  ["namelen", "start", "tsql"].forEach(function (id) { $(id).addEventListener("input", renderAll); });
  $("extras").addEventListener("click", function (e) {
    var b = e.target.closest("[data-x]"); if (!b) return;
    var id = b.dataset.x; if (st.extras[id]) delete st.extras[id]; else st.extras[id] = 1;
    renderAll();
  });
  $("rows").addEventListener("change", function (e) { var tr = e.target.closest("tr"); if (tr) toggle(tr.dataset.id); });
  $("scope").addEventListener("click", function (e) { var g = e.target.closest(".rp-pin"); if (g && g.dataset.id.charAt(0) === "r") toggle(g.dataset.id); });
  $("scope").addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var g = e.target.closest(".rp-pin"); if (!g) return;
    e.preventDefault(); var id = g.dataset.id; toggle(id);
    var again = $("scope").querySelector('[data-id="' + id + '"]'); if (again) again.focus();
  });

  $("dl").addEventListener("click", function () {
    var url = URL.createObjectURL(new Blob([csv()], { type: "text/csv" }));
    var a = document.createElement("a");
    a.href = url; a.download = "south-sound-chirp.csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    say("Downloaded south-sound-chirp.csv");
  });
  $("copy").addEventListener("click", function () {
    var t = csv();
    function fb() { var a = $("csv"); a.focus(); a.select(); say("Selected. Copy it, then save it as a .csv file."); }
    try { navigator.clipboard.writeText(t).then(function () { say("Copied to the clipboard."); }, fb); } catch (_) { fb(); }
  });

  // Redraw the scope when the theme flips (its colours are read from the CSS tokens).
  new MutationObserver(renderScope).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  renderAll();
})();
