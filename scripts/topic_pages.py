"""
Topic landing pages: /topics/ and /topics/<id>/ for each topic.

    python3 scripts/topic_pages.py

Built from the same sources as the homepage topic cards (POSTS in tags.html,
topics in data/topics.json), so a post lands on the same topic page as the
card that counts it. Each page has:

  * the topic's image, name, blurb and counts;
  * its live dashboards (data/topics.json -> "dashboards"), as image cards;
  * every post in the topic, newest first, with a picture where the post has
    one (the same picture its Keep-reading card uses) and a tag filter;
  * the other topics, to keep people moving.

/topics/index.html lists all six. Gated subdomains stay off, as on the
homepage. The Home topics workflow runs this after home_topics.py, so a new
post in tags.html shows up on its topic page on its own. Re-running only
rewrites a page whose content changed.

Styles are inline (this page only) plus the shared css/site-footer.css;
the footer comes from js/site-footer.js.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from home_topics import ROOT, posts, topic_of, local, esc
from keep_reading import (page_file, card_image, IMAGE_OVERRIDES, pretty_date,
                          TOPIC_COLORS)

# Tool and data-source tags say how a post was built, not what it's about;
# they make poor filters for a reader, so the chips skip them.
TOOL_TAGS = {"Python", "R", "JavaScript", "GitHub Actions", "Open Data", "Leaflet", "pixi", "D3",
             "Node", "SQL", "COBOL", "FORTRAN", "C#", ".NET", "forge3d", "Data Engineering",
             "Automation", "Open Source", "Web", "Dashboard", "API", "Cloudflare",
             "Real-Time Data", "Personal Infrastructure", "Building", "AI"}

NAV = [("Work", "/work/"), ("Writing", "/writing/"), ("Maps &amp; films", "/maps.html"),
       ("Live data", "/live/"), ("Outside", "/outside.html"), ("About", "/about.html")]

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="https://brooksgroves.com{path}">
  <meta property="og:image" content="https://brooksgroves.com{img}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:site" content="@bdgroves">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌲</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=DM+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    :root {{ --ink:#1c1a16; --parchment:#f5f0e8; --cream:#ede8dc; --sage:#4a5c45; --rust:#8b3a2a;
             --stone:#7a7268; --gold:#c8922a; --mist:#d6d0c4; --white:#fdfaf4; --sky:#5a7a8a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--parchment); color:var(--ink); font-family:'Libre Baskerville',Georgia,serif; line-height:1.7; }}
    a {{ color:var(--rust); }}
    .topline {{ height:4px; background:linear-gradient(90deg,var(--rust),var(--gold) 50%,var(--sage)); }}
    .tp-header {{ border-bottom:2px solid var(--ink); }}
    .tp-header-in {{ max-width:1200px; margin:0 auto; padding:18px clamp(16px,4vw,32px); display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:10px 32px; }}
    .tp-name {{ font-family:'Playfair Display',serif; font-weight:900; font-size:30px; letter-spacing:-.02em; text-decoration:none; color:var(--ink); }}
    .tp-nav {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px 22px; font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.12em; text-transform:uppercase; }}
    .tp-nav a {{ color:var(--ink); text-decoration:none; border-bottom:2px solid transparent; padding-bottom:2px; }}
    .tp-nav a:hover {{ color:var(--rust); border-bottom-color:var(--rust); }}
    .tp-nav a[aria-current="page"] {{ color:var(--rust); border-bottom-color:var(--rust); }}
    .tp-main {{ max-width:1200px; margin:0 auto; padding:0 clamp(16px,4vw,32px) 24px; }}
    .tp-hero {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:32px; align-items:center; padding:36px 0 28px; border-bottom:4px solid var(--tc,var(--gold)); }}
    .tp-hero img {{ width:100%; height:auto; aspect-ratio:16/9; object-fit:cover; display:block; border:1px solid var(--mist); }}
    .tp-back {{ font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--stone); text-decoration:none; }}
    .tp-back:hover {{ color:var(--rust); }}
    .tp-h1 {{ margin:10px 0 12px; font-family:'Playfair Display',serif; font-weight:900; font-size:clamp(34px,5vw,52px); line-height:1.05; letter-spacing:-.02em; }}
    .tp-blurb {{ margin:0 0 10px; font-size:18px; color:var(--stone); max-width:36em; }}
    .tp-count {{ font-family:'DM Mono',monospace; font-size:12px; color:var(--stone); }}
    @media (max-width:760px) {{ .tp-hero {{ grid-template-columns:1fr; gap:18px; padding-top:24px; }} .tp-hero img {{ order:-1; }} }}
    .tp-sec {{ padding:32px 0; border-bottom:1px solid var(--mist); }}
    .tp-sec:last-of-type {{ border-bottom:none; }}
    .tp-label {{ margin:0 0 16px; font-family:'DM Mono',monospace; font-weight:400; font-size:12px; letter-spacing:.2em; text-transform:uppercase; color:var(--ink); }}
    .tp-dash {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:16px; }}
    .tp-card {{ display:flex; flex-direction:column; gap:6px; padding:0 0 16px; border:1px solid var(--mist); background:var(--white); color:var(--ink); text-decoration:none; overflow:hidden; transition:border-color .18s, box-shadow .18s, transform .18s; }}
    .tp-card:hover {{ border-color:var(--stone); transform:translateY(-2px); box-shadow:0 10px 24px -16px rgba(28,26,22,.45); }}
    .tp-card img, .tp-card .tp-noimg {{ width:100%; aspect-ratio:16/9; object-fit:cover; display:block; margin-bottom:6px; border-bottom:1px solid var(--mist); background:var(--cream); }}
    .tp-noimg {{ display:flex !important; align-items:center; justify-content:center; font-size:44px; border-bottom:3px solid var(--tc,var(--gold)) !important; }}
    .tp-card b {{ padding:0 16px; font-family:'Playfair Display',serif; font-size:18px; line-height:1.3; }}
    .tp-card span.d {{ padding:0 16px; font-size:13.5px; color:var(--stone); line-height:1.55; }}
    .tp-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 8px; }}
    .tp-chip {{ font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.08em; text-transform:uppercase; padding:8px 12px; border:1px solid var(--mist); background:none; color:var(--ink); cursor:pointer; }}
    .tp-chip:hover {{ border-color:var(--ink); }}
    .tp-chip[aria-pressed="true"] {{ background:var(--ink); color:var(--parchment); border-color:var(--ink); }}
    .tp-chip:focus-visible, .tp-card:focus-visible {{ outline:2px solid var(--rust); outline-offset:2px; }}
    .tp-post {{ display:grid; grid-template-columns:120px minmax(0,1fr) 224px; gap:24px; padding:20px 0; border-bottom:1px solid var(--mist); align-items:start; }}
    .tp-post[hidden] {{ display:none; }}
    .tp-date {{ font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--stone); padding-top:4px; }}
    .tp-post h3 {{ margin:0 0 6px; font-family:'Playfair Display',serif; font-size:21px; line-height:1.3; }}
    .tp-post h3 a {{ color:var(--ink); text-decoration:none; }}
    .tp-post h3 a:hover {{ color:var(--rust); }}
    .tp-post p {{ margin:0; font-size:15px; color:var(--stone); line-height:1.65; }}
    .tp-thumb {{ display:block; }}
    .tp-thumb img {{ width:224px; aspect-ratio:16/9; object-fit:cover; display:block; border:1px solid var(--mist); }}
    @media (max-width:760px) {{ .tp-post {{ grid-template-columns:1fr; gap:8px; }} .tp-thumb {{ order:-1; }} .tp-thumb img {{ width:100%; aspect-ratio:16/9; }} }}
    .tp-empty {{ font-size:15px; color:var(--stone); padding:16px 0; }}
    .tp-others {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:14px; }}
    .tp-other {{ display:flex; flex-direction:column; border:1px solid var(--mist); background:var(--white); color:var(--ink); text-decoration:none; overflow:hidden; }}
    .tp-other img {{ width:100%; aspect-ratio:16/9; object-fit:cover; display:block; }}
    .tp-other span {{ padding:10px 12px; font-family:'Playfair Display',serif; font-weight:700; font-size:15px; line-height:1.3; }}
    .tp-other small {{ display:block; font-family:'DM Mono',monospace; font-weight:400; font-size:11px; color:var(--stone); margin-top:2px; }}
    .tp-other:hover {{ border-color:var(--ink); }}
    .theme-toggle {{ background:none; border:none; cursor:pointer; padding:0; font-size:14px; color:var(--stone); }}
    @media (prefers-reduced-motion: reduce) {{ .tp-card {{ transition:none; }} .tp-card:hover {{ transform:none; }} }}
    html[data-theme="dark"] .tp-chip[aria-pressed="true"] {{ background:var(--ink); color:#17150f; }}
  </style>
  <link rel="stylesheet" href="/css/site-footer.css">
  <script>
    (function(){{ try {{ var s = localStorage.getItem('bg_theme'); var d = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
      if (s === 'dark' || (!s && d)) document.documentElement.setAttribute('data-theme','dark'); }} catch(e) {{}} }})();
  </script>
</head>
<body>
<div class="topline"></div>
<header class="tp-header">
  <div class="tp-header-in">
    <a class="tp-name" href="/">Brooks Groves</a>
    <nav class="tp-nav" aria-label="Main">{nav}<button class="theme-toggle" id="theme-toggle" type="button" aria-label="Switch to dark mode" title="Switch to dark mode">&#9681;</button></nav>
  </div>
</header>
"""

TAIL = """
<script src="/js/site-footer.js" defer></script>
<script>
(function(){
  var root = document.documentElement, btn = document.getElementById('theme-toggle');
  function sync(){ var d = root.getAttribute('data-theme') === 'dark'; btn.textContent = d ? '\\u25D0' : '\\u25D1';
    var l = d ? 'Switch to light mode' : 'Switch to dark mode'; btn.setAttribute('aria-label', l); btn.setAttribute('title', l); }
  sync();
  btn.addEventListener('click', function(){ var d = root.getAttribute('data-theme') === 'dark';
    if (d) root.removeAttribute('data-theme'); else root.setAttribute('data-theme','dark');
    try { localStorage.setItem('bg_theme', d ? 'light' : 'dark'); } catch(e) {}
    sync(); });
  // Tag filter: show the posts that carry the chosen tag.
  var chips = document.querySelectorAll('.tp-chip'), rows = document.querySelectorAll('.tp-post'), empty = document.getElementById('tp-empty');
  function pick(tag){
    var shown = 0;
    chips.forEach(function(c){ c.setAttribute('aria-pressed', c.dataset.tag === tag ? 'true' : 'false'); });
    rows.forEach(function(r){ var ok = !tag || (r.dataset.tags || '').split('|').indexOf(tag) >= 0; r.hidden = !ok; if (ok) shown++; });
    if (empty) empty.hidden = shown > 0;
    try { history.replaceState(null, '', tag ? '#tag=' + encodeURIComponent(tag) : location.pathname); } catch(e) {}
  }
  chips.forEach(function(c){ c.addEventListener('click', function(){ pick(c.dataset.tag); }); });
  var m = location.hash.match(/^#tag=(.+)$/); if (m) pick(decodeURIComponent(m[1]));
})();
</script>
</body>
</html>
"""


def nav_html(current="Writing"):
    return ("".join(f'<a href="{h}"{" aria-current=\"page\"" if t == current else ""}>{t}</a>' for t, h in NAV)
            + '<a href="/search/" aria-label="Search">⌕ Search</a>')


def page_url(t):
    return f"/topics/{t['id']}/"


def write(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def ext(url):
    return ' target="_blank" rel="noopener"' if url.startswith("http") and "brooksgroves.com" not in url else ""


def build():
    cfg = json.loads((ROOT / "data/topics.json").read_text(encoding="utf-8"))
    topics, fallback = cfg["topics"], cfg.get("fallback", cfg["topics"][-1]["id"])
    hidden = tuple("https://" + h for h in cfg.get("exclude_hosts", []))
    skip = set(cfg.get("exclude_urls", []))
    pool = [p for p in posts() if not p["url"].startswith(hidden) and p["url"] not in skip]
    groups = {t["id"]: [] for t in topics}
    for p in pool:
        groups[topic_of(p, topics, fallback)].append(p)
    imgs = {p["url"]: IMAGE_OVERRIDES.get(local(p["url"])) or card_image(page_file(p["url"]), p["url"])
            for p in pool}
    order = sorted(topics, key=lambda t: -len(groups[t["id"]]))
    changed = 0

    for t in topics:
        g = groups[t["id"]]
        col = TOPIC_COLORS.get(t["id"], "var(--gold)")
        dashes = t.get("dashboards", [])
        tagcount = collections.Counter(tag for p in g for tag in p["tags"])
        top = [tag for tag, n in tagcount.most_common() if n >= 2 and tag not in TOOL_TAGS][:8]
        title = f"{t['name']} · Brooks Groves"
        desc = f"{t['blurb']} {len(g)} posts and {len(dashes)} live dashboards."
        out = [HEAD.format(title=esc(title), desc=esc(desc), path=page_url(t), img=t.get("img", ""), nav=nav_html())]
        out.append(f'<main class="tp-main" style="--tc:{col}">')
        out.append('  <section class="tp-hero">')
        out.append('    <div>')
        out.append('      <a class="tp-back" href="/topics/">&larr; All topics</a>')
        out.append(f'      <h1 class="tp-h1">{t["icon"]} {esc(t["name"])}</h1>')
        out.append(f'      <p class="tp-blurb">{esc(t["blurb"])}</p>')
        out.append(f'      <p class="tp-count">{len(g)} {"post" if len(g) == 1 else "posts"}'
                   f'{f" · {len(dashes)} live dashboards" if dashes else ""}</p>')
        out.append('    </div>')
        if t.get("img"):
            out.append(f'    <img src="{esc(t["img"])}" alt="" width="800" height="450">')
        out.append('  </section>')

        if dashes:
            out.append('  <section class="tp-sec" aria-labelledby="dash-h">')
            out.append('    <h2 class="tp-label" id="dash-h">Live dashboards</h2>')
            out.append('    <div class="tp-dash">')
            for d in dashes:
                media = (f'<img src="{esc(d["img"])}" alt="" loading="lazy" decoding="async">' if d.get("img")
                         else f'<span class="tp-noimg" aria-hidden="true">{esc(d["name"].split()[0])}</span>')
                out.append(f'      <a class="tp-card" href="{esc(d["url"])}"{ext(d["url"])}>{media}'
                           f'<b>{esc(d["name"])}</b><span class="d">{esc(d["blurb"])}</span></a>')
            out.append('    </div>')
            out.append('  </section>')

        out.append('  <section class="tp-sec" aria-labelledby="posts-h">')
        out.append('    <h2 class="tp-label" id="posts-h">Posts</h2>')
        if top:
            out.append('    <div class="tp-chips" role="group" aria-label="Filter posts by tag">')
            out.append(f'      <button class="tp-chip" type="button" data-tag="" aria-pressed="true">All {len(g)}</button>')
            for tag in top:
                out.append(f'      <button class="tp-chip" type="button" data-tag="{esc(tag)}" aria-pressed="false">'
                           f'{esc(tag)} {tagcount[tag]}</button>')
            out.append('    </div>')
        for p in g:
            u = local(p["url"])
            img = imgs.get(p["url"])
            thumb = (f'<a class="tp-thumb" href="{esc(u)}" tabindex="-1" aria-hidden="true">'
                     f'<img src="{esc(img)}" alt="" loading="lazy" decoding="async"></a>') if img else '<span></span>'
            out.append(f'    <article class="tp-post" data-tags="{esc("|".join(p["tags"]))}">'
                       f'<span class="tp-date">{esc(pretty_date(p["date"]))}</span>'
                       f'<div><h3><a href="{esc(u)}">{esc(p["title"])}</a></h3><p>{esc(p["dek"])}</p></div>{thumb}</article>')
        out.append('    <p class="tp-empty" id="tp-empty" hidden>No posts with that tag.</p>')
        out.append('  </section>')

        out.append('  <section class="tp-sec" aria-labelledby="more-h">')
        out.append('    <h2 class="tp-label" id="more-h">Other topics</h2>')
        out.append('    <div class="tp-others">')
        for o in order:
            if o is t:
                continue
            out.append(f'      <a class="tp-other" href="{page_url(o)}"><img src="{esc(o.get("img", ""))}" alt="" loading="lazy">'
                       f'<span>{o["icon"]} {esc(o["name"])}<small>{len(groups[o["id"]])} posts</small></span></a>')
        out.append('    </div>')
        out.append('  </section>')
        out.append('</main>')
        out.append(TAIL)
        changed += write(ROOT / "topics" / t["id"] / "index.html", "\n".join(out))

    # the hub
    title = "Topics · Brooks Groves"
    desc = "Everything on brooksgroves.com by topic: weather and water, volcanoes and ruins, maps, nature, sports and builds."
    out = [HEAD.format(title=title, desc=esc(desc), path="/topics/", img=order[0].get("img", ""), nav=nav_html())]
    out.append('<main class="tp-main">')
    out.append('  <section class="tp-sec" style="border-bottom:4px solid var(--gold)">')
    out.append('    <a class="tp-back" href="/">&larr; Home</a>')
    out.append('    <h1 class="tp-h1">Topics</h1>')
    out.append(f'    <p class="tp-blurb">{len(pool)} posts and the live dashboards behind them, in six topics.</p>')
    out.append('  </section>')
    out.append('  <section class="tp-sec"><div class="tp-dash">')
    for o in order:
        out.append(f'    <a class="tp-card" href="{page_url(o)}"><img src="{esc(o.get("img", ""))}" alt="" loading="lazy">'
                   f'<b>{o["icon"]} {esc(o["name"])}</b><span class="d">{esc(o["blurb"])}</span>'
                   f'<span class="d" style="font-family:\'DM Mono\',monospace;font-size:11px">{len(groups[o["id"]])} posts · '
                   f'{len(o.get("dashboards", []))} dashboards</span></a>')
    out.append('  </div></section>')
    out.append('</main>')
    out.append(TAIL)
    changed += write(ROOT / "topics" / "index.html", "\n".join(out))
    print(f"topic pages: {len(topics) + 1} pages, {changed} changed")


if __name__ == "__main__":
    build()
