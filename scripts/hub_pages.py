"""
The Work and Live data pages: /work/ and /live/.

    python3 scripts/hub_pages.py

Same look and header as the topic pages (it reuses topic_pages.HEAD/TAIL).

/work/  the featured projects (the homepage carousel's FEATURED list, read
        from index.html, with their images), then the eight fields, then a
        line to the code on GitHub.
/maps.html  (only the block between its maps-cards markers) the GIS projects,
        the map dashboards and the flyover films, as picture cards.
/live/  three live readings (Kīlauea, the day's biggest quake, Rainier's
        snowpack; the same data and code as the homepage panel), then every
        dashboard listed in data/topics.json, grouped by topic.

The Home topics workflow runs it, so a project added to FEATURED or a
dashboard added to data/topics.json shows up here on its own.
"""
from __future__ import annotations

import json
import re

from home_topics import ROOT, esc
from topic_pages import HEAD, TAIL, nav_html, write, ext
from keep_reading import TOPIC_COLORS

FIELDS = [
    ("🌩", "Meteorology", "/meteorology.html", "Weather pipelines, atmospheric analysis, and forecast automation."),
    ("💧", "Hydrology", "/hydrology.html", "Streamflow, snowpack, and water-resource tracking across the Sierra and Cascades."),
    ("🗺", "Geospatial", "/geospatial.html", "GIS and remote sensing in Python, R and QGIS, led by a study of how far West Coast wildfires burn from fire stations."),
    ("🌋", "Volcanology", "/volcanology.html", "Live eruption monitoring and lahar hazard tracking."),
    ("🦕", "Paleontology", "/paleontology.html", "Machine-learning fossil-locality prediction: finding where to dig next."),
    ("🌿", "Ecology", "/ecology.html", "Projects mapped from GBIF and iNaturalist: cui-ui, golden trout, pikas, island lizards and kangaroo rats."),
    ("🪨", "Geology", "/geology.html", "Gold country in bare-earth lidar, and the ground that shakes."),
    ("🏺", "Archaeology", "/archaeology.html", "Ancient places in lidar, and the sky the builders watched."),
]

EXTRA_CSS = """
<style>
  .hb-fields { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:14px; }
  .hb-field { display:flex; flex-direction:column; gap:4px; padding:16px 18px; border:1px solid var(--mist); border-top:3px solid var(--gold);
              background:var(--white); color:var(--ink); text-decoration:none; }
  .hb-field:hover { border-color:var(--stone); }
  .hb-field b { font-family:'Playfair Display',serif; font-size:19px; }
  .hb-field span { font-size:14px; color:var(--stone); line-height:1.55; }
  .hb-stack { display:flex; flex-wrap:wrap; gap:6px; padding:2px 16px 0; }
  .hb-stack i { font-style:normal; font-family:'DM Mono',monospace; font-size:10px; letter-spacing:.08em; text-transform:uppercase;
                color:var(--stone); border:1px solid var(--mist); padding:2px 7px; }
  .hb-live { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
  .hb-tile { display:flex; flex-direction:column; gap:5px; padding:18px 20px; border:1px solid var(--mist); background:var(--white);
             color:var(--ink); text-decoration:none; border-top:3px solid var(--rust); }
  .hb-tile:nth-child(2) { border-top-color:var(--gold); } .hb-tile:nth-child(3) { border-top-color:#5a7a8a; }
  .hb-tile:hover { border-color:var(--ink); }
  .hb-k { font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--stone); }
  .hb-v { font-family:'Playfair Display',serif; font-weight:900; font-size:28px; line-height:1.15; }
  .hb-s { font-size:14px; color:var(--stone); line-height:1.5; }
  .hb-group { margin:28px 0 12px; font-family:'Playfair Display',serif; font-size:22px; font-weight:700; }
  .hb-group:first-of-type { margin-top:0; }
  .hb-group a { color:var(--ink); text-decoration:none; } .hb-group a:hover { color:var(--rust); }
</style>
"""

LIVE_JS = r"""
<script>
(function(){
  function set(id, v, sub){ var el = document.getElementById(id); if (!el) return;
    el.querySelector('[data-live="v"]').textContent = v; el.querySelector('[data-live="s"]').textContent = sub; }
  function ago(ms){ var h = ms/3600000; if (h < 1) return Math.max(1, Math.round(ms/60000)) + ' min ago';
    if (h < 48) return Math.round(h) + ' h ago'; return Math.round(h/24) + ' days ago'; }
  function getJSON(u){ return fetch(u, {cache:'no-cache'}).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  var nf = new Intl.NumberFormat('en-US');
  Promise.all([getJSON('/PELE/data/volcanoes.json'), getJSON('/PELE/data/episodes.json')]).then(function(r){
    var v = r[0], e = r[1], k = (v.volcanoes || []).find(function(x){ return /kilauea|kīlauea/i.test(x.name); });
    var lvl = k ? k.alert_level.charAt(0) + k.alert_level.slice(1).toLowerCase() : 'Status unknown';
    var sm = e.summary || {}, sub = '';
    if (sm.last_episode && sm.last_end_iso) sub = 'Fountain episode ' + sm.last_episode + ' ended ' + ago(Date.now() - Date.parse(sm.last_end_iso)) + (sm.last_height_m ? ', ' + nf.format(sm.last_height_m) + ' m high.' : '.');
    set('live-kilauea', lvl + (k && k.color_code ? ' · ' + k.color_code.charAt(0) + k.color_code.slice(1).toLowerCase() : ''), sub || 'Open PELE for the latest.');
  }).catch(function(){ set('live-kilauea', 'See PELE', 'The live feed didn’t load just now.'); });
  getJSON('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson').then(function(g){
    var f = (g.features || []).sort(function(a, b){ return b.properties.mag - a.properties.mag; })[0];
    if (!f) { set('live-quake', 'Quiet', 'Nothing M2.5+ in the last day.'); return; }
    var p = f.properties;
    set('live-quake', 'M' + p.mag.toFixed(1), p.place + ', ' + ago(Date.now() - p.time) + '. ' + nf.format(g.features.length) + ' quakes M2.5+ worldwide today.');
  }).catch(function(){ set('live-quake', 'See AFTERSHOCK', 'The live feed didn’t load just now.'); });
  getJSON('/rainier-snowpack/data/processed/snotel_latest.json').then(function(d){
    var i = d.index || {}, b = d.basin || {}, swe = typeof i.swe_in === 'number' ? i.swe_in : null;
    var v = swe === null ? 'No reading' : (swe === 0 ? 'No snow yet' : swe.toFixed(1) + ' in of water');
    var bits = [];
    if (typeof i.pct_median === 'number') bits.push(i.pct_median + '% of median');
    if (typeof b.days_since_snow === 'number') bits.push(b.days_since_snow + ' days since new snow');
    if (typeof i.precip_pct_median === 'number') bits.push('water-year precipitation ' + i.precip_pct_median + '% of median');
    set('live-rainier', v, (bits.length ? bits.join(' · ') : 'Seven SNOTEL stations around the mountain') + '.');
  }).catch(function(){ set('live-rainier', 'See STORM CHASER', 'The live feed didn’t load just now.'); });
})();
</script>
"""


def featured():
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    a = s.index("const FEATURED = [")
    b = s.index("];", a)
    out = []
    for m in re.finditer(r"\{ url:\"([^\"]*)\", img:\"([^\"]*)\", alt:\"[^\"]*\", kicker:\"([^\"]*)\", hed:\"(.*?)\", dek:\"(.*?)\", stack:\[(.*?)\] \}", s[a:b]):
        url, img, kicker, hed, dek, stack = m.groups()
        name = re.sub(r"<br>\s*<em>(.*?)</em>", r" \1", hed)
        name = re.sub(r"<[^>]+>", "", name).replace(": ", ": ", 1)
        out.append(dict(url=url, img=img, kicker=kicker, name=name, dek=dek.replace('\\"', '"'),
                        stack=re.findall(r'"([^"]+)"', stack)))
    return out


def card(url, img, name, blurb, stack=None, col="var(--gold)"):
    media = (f'<img src="{esc(img)}" alt="" loading="lazy" decoding="async">' if img
             else f'<span class="tp-noimg" aria-hidden="true" style="--tc:{col}">{esc(name.split()[0])}</span>')
    pills = ("<span class=\"hb-stack\">" + "".join(f"<i>{esc(x)}</i>" for x in stack[:5]) + "</span>") if stack else ""
    return (f'      <a class="tp-card" href="{esc(url)}"{ext(url)}>{media}<b>{esc(name)}</b>'
            f'<span class="d">{esc(blurb)}</span>{pills}</a>')


def page(path, title, desc, img, h1, blurb, sections, js=""):
    out = [HEAD.format(title=esc(title), desc=esc(desc), path=path, img=img, nav=nav_html(h1)).replace("</head>", EXTRA_CSS + "</head>")]
    out.append('<main class="tp-main">')
    out.append('  <section class="tp-sec" style="border-bottom:4px solid var(--gold)">')
    out.append('    <a class="tp-back" href="/">&larr; Home</a>')
    out.append(f'    <h1 class="tp-h1">{h1}</h1>')
    out.append(f'    <p class="tp-blurb">{blurb}</p>')
    out.append('  </section>')
    out += sections
    out.append('</main>')
    out.append(TAIL.replace("</body>", js + "</body>"))
    return "\n".join(out)


# /maps.html: picture cards under the map. Dashboards come from data/topics.json
# (so a new one shows up on its own); these lists only say which go where.
MAP_PROJECTS = ["https://brooksgroves.com/mother-lode/", "https://brooksgroves.com/project-kiva",
                "https://brooksgroves.com/lidar-explore/", "https://brooksgroves.com/solstice",
                "https://brooksgroves.com/cypress-dome-watch/", "https://brooksgroves.com/sentinel-stockpile/",
                "https://brooksgroves.com/dipodomys", "https://brooksgroves.com/little-free-pantry",
                "https://brooksgroves.com/30DayMapChallenge/2026/"]
MAP_DASH_TOPICS = ["earth", "weather", "nature"]       # everything else in these topics counts as a dashboard
FILMS = [
    ("/blog/zermatt-diorama-post.html", "/blog/img/zermatt-diorama/og.jpg", "🐄 Zermatt in Miniature",
     "The Matterhorn, gondolas, the Gornergrat train, chalets and cows."),
    ("/blog/dakar-diorama-post.html", "/blog/img/dakar-diorama/og.jpg", "🏁 The Dakar in Miniature",
     "The 2027 rally from the Algarve to Marrakech, with a convoy in the dust."),
    ("/blog/amalfi-diorama-post.html", "/blog/img/amalfi-diorama/og.jpg", "🍋 The Amalfi Coast in Miniature",
     "Capri, Positano, Ravello and the coast road, with boats on the sea."),
    ("/blog/yosemite-diorama-post.html", "/blog/img/yosemite-diorama/og.jpg", "🧗 Yosemite in Miniature",
     "The valley, its waterfalls and Camp 4, as a tabletop diorama."),
    ("/blog/seattle-diorama-post.html", "/blog/img/seattle-diorama/og.jpg", "🏙️ Seattle in Miniature",
     "The Needle, the Monorail and the Westin, from OpenStreetMap."),
    ("/blog/athabasca-melt-post.html", "/blog/img/athabasca-melt/og.jpg", "🧊 The Athabasca Glacier, 1844 to 2100",
     "One view from the Icefield Centre lookout, 256 years of ice."),
    ("/blog/icefields-flyover-post.html", "/blog/img/icefields-flyover/og.jpg", "🏔️ The Icefields Parkway",
     "Lake Louise to the Columbia Icefield in 95 seconds."),
    ("/blog/ruby-flyover-post.html", "/images/features/ruby-flyover.jpg", "💎 The Ruby Mountains",
     "Up Lamoille Canyon to Liberty Lake on 1 m lidar."),
    ("/blog/mono-flyover-post.html", "/blog/img/mono-flyover/og.jpg", "🌋 Mono Basin",
     "Tioga Pass, Mono Lake and the Mono Craters on 1 m lidar."),
    ("/blog/yosemite-flyover-post.html", "/blog/img/yosemite-flyover/og.jpg", "🧗 Yosemite",
     "Half Dome to Tunnel View and back on a June evening."),
]
MAPS_CSS = """  <style>
    .mp { margin-top:3rem; padding-top:2rem; border-top:2px solid var(--ink); }
    .mp-head { font-family:'Playfair Display',serif; font-size:clamp(1.4rem,3vw,1.9rem); font-weight:900; margin:0 0 .35rem; }
    .mp-desc { color:var(--stone); font-size:.95rem; line-height:1.6; margin:0 0 1.25rem; max-width:62ch; }
    .mp-group { font-family:'DM Mono',monospace; font-size:.62rem; letter-spacing:.14em; text-transform:uppercase; color:var(--stone); margin:1.75rem 0 .75rem; }
    .mp .tp-dash { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:16px; }
    .mp .tp-card { display:flex; flex-direction:column; gap:6px; padding:0 0 16px; border:1px solid var(--mist); background:var(--white); color:var(--ink); text-decoration:none; overflow:hidden; transition:border-color .18s, box-shadow .18s, transform .18s; }
    .mp .tp-card:hover { border-color:var(--stone); transform:translateY(-2px); box-shadow:0 10px 24px -16px rgba(28,26,22,.45); }
    .mp .tp-card:focus-visible { outline:2px solid var(--rust); outline-offset:2px; }
    .mp .tp-card img { width:100%; height:auto; aspect-ratio:16/9; object-fit:cover; display:block; margin-bottom:6px; border-bottom:1px solid var(--mist); background:var(--cream); }
    .mp .tp-card b { padding:0 16px; font-family:'Playfair Display',serif; font-size:18px; line-height:1.3; }
    .mp .tp-card span.d { padding:0 16px; font-size:13.5px; color:var(--stone); line-height:1.55; }
    @media (prefers-reduced-motion: reduce) { .mp .tp-card { transition:none; } .mp .tp-card:hover { transform:none; } }
  </style>"""


def maps_cards(cfg) -> bool:
    path = ROOT / "maps.html"
    s = path.read_text(encoding="utf-8")
    a, b = "<!-- maps-cards:start (scripts/hub_pages.py) -->", "<!-- maps-cards:end -->"
    if a not in s or b not in s:
        print("hub pages: maps.html has no maps-cards markers, skipped")
        return False
    dash = {x["url"]: x for t in cfg["topics"] for x in t.get("dashboards", [])}
    projects = [dash[u] for u in MAP_PROJECTS if u in dash]
    live = [x for t in cfg["topics"] if t["id"] in MAP_DASH_TOPICS for x in t.get("dashboards", [])
            if x["url"] not in MAP_PROJECTS]
    out = [a, MAPS_CSS, '  <section class="mp" aria-labelledby="mp-h">',
           '    <h2 class="mp-head" id="mp-h">Projects, dashboards and films</h2>',
           '    <p class="mp-desc">The maps that grew into projects: lidar atlases and analyses, dashboards that update on their own, and flyover films.</p>',
           '    <h3 class="mp-group">GIS projects</h3>', '    <div class="tp-dash">']
    out += [card(x["url"], x.get("img", ""), x["name"], x["blurb"]) for x in projects]
    out += ['    </div>', '    <h3 class="mp-group">Live dashboards</h3>', '    <div class="tp-dash">']
    out += [card(x["url"], x.get("img", ""), x["name"], x["blurb"]) for x in live]
    out += ['    </div>', '    <h3 class="mp-group">Flyover films</h3>', '    <div class="tp-dash">']
    out += [card(u, img, n, d) for u, img, n, d in FILMS]
    out += ['    </div>', '  </section>', '  ' + b]
    i, j = s.index(a), s.index(b) + len(b)
    new = s[:i] + "\n".join(out) + s[j:]
    if new == s:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def build():
    cfg = json.loads((ROOT / "data/topics.json").read_text(encoding="utf-8"))
    changed = 0

    # /work/
    feats = featured()
    sec = ['  <section class="tp-sec" aria-labelledby="f-h">', '    <h2 class="tp-label" id="f-h">Featured projects</h2>',
           '    <div class="tp-dash">']
    sec += [card(f["url"], f["img"], f["name"], f["dek"], f["stack"]) for f in feats]
    sec += ['    </div>', '  </section>',
            '  <section class="tp-sec" aria-labelledby="by-h">', '    <h2 class="tp-label" id="by-h">By field</h2>',
            '    <div class="hb-fields">']
    sec += [f'      <a class="hb-field" href="{u}"><b>{e} {n}</b><span>{esc(b)}</span></a>' for e, n, u, b in FIELDS]
    sec += ['    </div>', '  </section>',
            '  <section class="tp-sec">',
            '    <p class="tp-blurb">Every project is open source: <a href="https://github.com/bdgroves" target="_blank" rel="noopener">the code is on GitHub</a>, '
            'and <a href="/topics/">the posts behind them are here, by topic</a>.</p>',
            '  </section>']
    changed += write(ROOT / "work" / "index.html", page(
        "/work/", "Work · Brooks Groves",
        "Brooks Groves's GIS and data projects: live dashboards, lidar atlases and analyses, by field.",
        feats[0]["img"] if feats else "", "Work",
        f"{len(feats)} featured projects and eight fields: live dashboards, lidar atlases and the analyses behind them.", sec))

    # /live/
    sec = ['  <section class="tp-sec" aria-labelledby="now-h">', '    <h2 class="tp-label" id="now-h">Right now</h2>',
           '    <div class="hb-live">',
           '      <a class="hb-tile" id="live-kilauea" href="https://brooksgroves.com/PELE" target="_blank" rel="noopener"><span class="hb-k">🌋 Kīlauea</span><span class="hb-v" data-live="v">…</span><span class="hb-s" data-live="s">Checking PELE</span></a>',
           '      <a class="hb-tile" id="live-quake" href="https://brooksgroves.com/aftershock" target="_blank" rel="noopener"><span class="hb-k">🌍 Biggest quake, last 24 hours</span><span class="hb-v" data-live="v">…</span><span class="hb-s" data-live="s">Checking USGS</span></a>',
           '      <a class="hb-tile" id="live-rainier" href="https://brooksgroves.com/rainier-snowpack" target="_blank" rel="noopener"><span class="hb-k">❄️ Rainier snowpack</span><span class="hb-v" data-live="v">…</span><span class="hb-s" data-live="s">Checking STORM CHASER</span></a>',
           '    </div>', '  </section>',
           '  <section class="tp-sec" aria-labelledby="all-h">', '    <h2 class="tp-label" id="all-h">Every dashboard</h2>']
    n = 0
    first = ["weather", "earth", "nature", "maps", "sports", "builds"]     # the liveliest first
    for t in sorted(cfg["topics"], key=lambda t: first.index(t["id"]) if t["id"] in first else 99):
        d = t.get("dashboards", [])
        if not d:
            continue
        col = TOPIC_COLORS.get(t["id"], "var(--gold)")
        sec.append(f'    <h3 class="hb-group"><a href="/topics/{t["id"]}/">{t["icon"]} {esc(t["name"])}</a></h3>')
        sec.append('    <div class="tp-dash">')
        sec += [card(x["url"], x.get("img", ""), x["name"], x["blurb"], col=col) for x in d]
        sec.append('    </div>')
        n += len(d)
    sec.append('  </section>')
    changed += write(ROOT / "live" / "index.html", page(
        "/live/", "Live data · Brooks Groves",
        "Live dashboards by Brooks Groves: Kīlauea, earthquakes, Rainier snowpack, Lake Tahoe, Sierra rivers, tides, fog and more, updating on their own.",
        "/images/features/pele.jpg", "Live data",
        f"{n} dashboards and tools, from Kīlauea to Lake Tahoe. First, three live readings, as of each dashboard’s last update:",
        sec, LIVE_JS))
    changed += maps_cards(cfg)
    print(f"hub pages: /work/ ({len(feats)} projects), /live/ ({n} dashboards); {changed} changed")


if __name__ == "__main__":
    build()
