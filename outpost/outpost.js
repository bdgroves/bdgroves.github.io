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

  /* ---------- shopping list ---------- */
  // [id, qty, name, why, low $, high $, tag]  — prices are rough per line, USD, Oct 31 2026
  var SHOP = [
    { intro: "Prove the whole chain on the table: a reading leaves one radio, reaches the other, lands on a Raspberry Pi and gets committed to GitHub. Cheap ESP32 boards are fine here because they're plugged into USB.",
      items: [
        ["h4", "2", "Heltec LoRa 32 V4 boards, 915 MHz", "One is the station, one plugs into the Pi as the gateway radio. ESP32-S3 with a small screen; runs Meshtastic or your own code. Get the 915 MHz version for the US.", 52, 60, "checked price"],
        ["pi", "1", "Raspberry Pi (4, 5 or Zero 2 W) + power supply + 32 GB microSD", "The gateway at home: a Python script reads the radio over USB and pushes readings to GitHub. Skip it if one's already in a drawer.", 60, 110, ""],
        ["ds", "1", "DS18B20 waterproof temperature probes (pack, 3 m cable)", "The first sensor: water temperature, in a glass on the table for now. Packs often include the 4.7 kΩ pull-up resistor it needs. Likely needs a few lines of your own code.", 8, 15, ""],
        ["bme", "1", "BME280 sensor breakout (I2C)", "Air temperature, humidity and pressure. Meshtastic can report it as telemetry with no code at all.", 6, 12, ""],
        ["bb", "1", "Breadboard, jumper wires and USB-C data cables", "For wiring sensors without soldering. Make sure the cables carry data, not just charge.", 10, 18, ""],
        ["tools", "1", "Soldering iron kit and a basic multimeter", "Only if you don't own them. You'll want both by phase 1.", 40, 70, "if needed"]
      ] },
    { intro: "Move outside and survive a Northwest winter. Here the station has to run on sunlight, so it switches to a low-power nRF52 board built for solar life.",
      items: [
        ["p1pro", "1", "SenseCAP Solar Node P1 Pro", "Outdoor LoRa node with a 5 W panel, four 18650 cells and a plug-in spot for a BME280. Low-power nRF52840 chip. (The plain P1, about $70, skips the batteries and GPS.)", 90, 90, "checked price"],
        ["shield", "1", "Radiation shield for the air sensor", "The stacked-plate cover that keeps sun off the temperature sensor, or it reads hot.", 15, 30, ""],
        ["glands", "1", "Cable glands, silicone sealant and desiccant packs", "To get the water probe's cable into the box without letting rain in, and to keep it dry inside.", 10, 18, ""],
        ["mount", "1", "Post mount: hose clamps, UV-rated zip ties, a short pipe or bracket", "Holds it to a fence post facing south.", 10, 20, ""],
        ["usbm", "1", "USB power meter", "Measures what the station really draws, so the power-budget numbers below are real instead of guessed.", 10, 20, ""]
      ] },
    { intro: "The creek, near the USGS gauge, with permission. The new problems are distance (a relay helps), measuring water level, and keeping the probe in the water through a flood.",
      items: [
        ["relay", "1", "Second solar node as a relay", "Another SenseCAP P1 on a high spot between the creek and home, so the signal can hop around the canyon walls.", 70, 90, ""],
        ["ant", "1", "Outdoor 915 MHz antenna (5–6 dBi) and low-loss coax", "Up high at the house for the gateway. Height beats almost everything at these frequencies.", 40, 80, ""],
        ["level", "1", "Water level sensor", "A waterproof ultrasonic sensor looking down from a bridge or bank, or a submersible pressure transducer. Pick after scouting the site.", 15, 80, "choose one"],
        ["dslong", "1", "Long-cable DS18B20 probe (5–10 m)", "Reaches from the box above the high-water line down into the creek.", 8, 15, ""],
        ["well", "1", "Stilling well: 2-inch perforated PVC, end cap, rebar stakes", "Protects the probe from debris and calms the water for level readings.", 20, 35, ""],
        ["label", "1", "Weatherproof label with contact info", "Says who it belongs to and that it's there with permission. Cheap insurance against curious hands.", 5, 10, ""],
        ["ec", "1", "Conductivity probe kit (lab-grade)", "Later, for stormwater and road-salt pulses after rain.", 200, 260, "later"]
      ] },
    { intro: "A summer at an alpine lake ALPINE-WATCH already watches from orbit. Too far for LoRa, so it either talks to a satellite or keeps a log for whoever hikes in.",
      items: [
        ["rock", "1", "RockBLOCK 9603N Iridium modem", "Short satellite messages from anywhere with open sky. Line rental is about $15 a month in months you use it, plus message credits, so send one daily summary.", 300, 300, "checked price"],
        ["sd", "1", "microSD logger and DS3231 real-time clock (the cheap alternative)", "Stores every reading with an accurate timestamp for pickup on a hike, instead of sending by satellite.", 12, 20, "or this"],
        ["string", "1", "Temperature string: several DS18B20s at different depths", "Shows how the lake layers in summer, the thing satellites can't see.", 15, 30, ""],
        ["bat", "1", "Extra 18650 cells or a larger battery pack", "Longer, cloudier stretches with nobody around to help.", 30, 60, ""],
        ["permit", "1", "Talk to the Forest Service district", "Equipment on national forest land needs their OK. Free, but start early.", 0, 0, "no cost"]
      ] }
  ];
  var SKEY = "bg_outpost_shop", got = {}, ph = 0;
  try { got = JSON.parse(localStorage.getItem(SKEY) || "{}") || {}; } catch (e) { got = {}; }
  function money(lo, hi) { return lo === hi ? (lo ? "$" + lo : "free") : "$" + lo + "–" + hi; }
  function renderShop() {
    var P = SHOP[ph];
    document.querySelectorAll(".op-tab").forEach(function (t) { t.setAttribute("aria-selected", String(+t.dataset.ph === ph)); });
    $("shopIntro").textContent = P.intro;
    $("shopList").innerHTML = P.items.map(function (it) {
      var k = ph + "-" + it[0];
      return '<li><label><input type="checkbox" id="sh-' + k + '" data-k="' + k + '"' + (got[k] ? " checked" : "") + '><span class="op-qty">×' + it[1] + '</span>' +
        '<span class="op-item"><b>' + it[2] + "</b><span>" + it[3] + "</span>" + (it[6] ? "<em>" + it[6] + "</em>" : "") + "</span>" +
        '<span class="op-price">' + money(it[4], it[5]) + "</span></label></li>";
    }).join("");
    var lo = 0, hi = 0, llo = 0, lhi = 0;
    P.items.forEach(function (it) {
      if (it[6] === "later" || it[6] === "or this" || it[6] === "if needed") return; // optional extras stay out of the total
      lo += it[4]; hi += it[5];
      if (!got[ph + "-" + it[0]]) { llo += it[4]; lhi += it[5]; }
    });
    $("shopTotal").textContent = money(lo, hi);
    $("shopLeft").textContent = llo + lhi === 0 ? "all set" : money(llo, lhi);
  }
  document.querySelectorAll(".op-tab").forEach(function (t) {
    t.addEventListener("click", function () { ph = +t.dataset.ph; $("shopMsg").textContent = ""; renderShop(); });
  });
  $("shopList").addEventListener("change", function (e) {
    var k = e.target.dataset.k; if (!k) return;
    if (e.target.checked) got[k] = 1; else delete got[k];
    try { localStorage.setItem(SKEY, JSON.stringify(got)); } catch (_) {}
    renderShop(); var b = $("sh-" + k); if (b) b.focus();
  });
  $("shopCopy").addEventListener("click", function () {
    var P = SHOP[ph], names = ["Kitchen table", "Backyard", "Chambers Creek", "Alpine lake"];
    var txt = "OUTPOST phase " + ph + " (" + names[ph] + ") shopping list\n" + P.items.map(function (it) {
      return (got[ph + "-" + it[0]] ? "[x] " : "[ ] ") + it[1] + " × " + it[2] + " — " + money(it[4], it[5]) + (it[6] ? " (" + it[6] + ")" : "");
    }).join("\n") + "\nhttps://brooksgroves.com/outpost/#shopping\n";
    var ok = function () { $("shopMsg").textContent = "Copied"; };
    try { navigator.clipboard.writeText(txt).then(ok, function () { $("shopMsg").textContent = "Couldn't copy here"; }); } catch (_) { $("shopMsg").textContent = "Couldn't copy here"; }
  });
  renderShop();
})();
