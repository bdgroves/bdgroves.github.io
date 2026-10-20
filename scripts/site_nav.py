"""
The site menu: the same six doors on every page.

    python3 scripts/site_nav.py

Work · Writing · Maps & films · Live data · Outside · About, with the page's
own door marked (aria-current). The homepage has its own richer menu with
dropdowns and is left alone; so are the games (full-screen, their own
chrome) and the 404 page.

Pages carry their header inline, in three shapes; each is handled:

  A  <header><div class="masthead-inner"> ... <nav> links + theme button </nav>
  B  <header class="top"> ... <nav class="topnav"> links + theme button </nav>
  C  <header><div class="masthead-inner"> ... <a class="header-link">← Back</a>

In every case the links are replaced and the page's own theme-toggle button
is kept exactly as it was, since each page's script looks it up by id. The
result is <nav class="site-nav" ...>, which a re-run recognises, so running
it again only changes pages whose door or links changed. Styles for
.site-nav are in css/site-footer.css ("SITE MENU").

New pages: copy any post's header; this script (run by the Home topics
workflow) brings it into line.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOORS = [("Work", "/#work"), ("Writing", "/writing/"), ("Maps &amp; films", "/maps.html"),
         ("Live data", "/#live"), ("Outside", "/outside.html"), ("About", "/about.html")]
SKIP = {"index.html", "404.html"}
SKIP_DIRS = {".git", "node_modules", "_site", ".pixi", "tools", "games", "hightimes-db"}

WORK = {"meteorology.html", "hydrology.html", "geospatial.html", "volcanology.html", "paleontology.html",
        "ecology.html", "geology.html", "archaeology.html", "fuelcast.html", "gisp-cheat-sheet.html"}
OUTSIDE = {"outside.html", "concerts.html", "sports.html", "games.html", "dakar-2027.html", "giro-2026.html",
           "tdf-2026.html", "vuelta-2026.html", "quotes.html"}


def door_for(rel: str) -> str | None:
    name = rel.split("/")[-1]
    if rel == "maps.html":
        return "Maps &amp; films"
    if rel == "about.html":
        return "About"
    if name in OUTSIDE and "/" not in rel:
        return "Outside"
    if name in WORK and "/" not in rel:
        return "Work"
    if rel.startswith(("blog/", "writing/", "learning/", "recipes")) or rel in ("tags.html", "recipes.html"):
        return "Writing"
    if rel.startswith("topics/"):
        return "Writing"
    return None


def nav(rel: str, toggle: str, indent: str = "    ") -> str:
    cur = door_for(rel)
    links = "".join(
        f'\n{indent}  <a href="{h}"{" aria-current=\"page\"" if t == cur else ""}>{t}</a>' for t, h in DOORS)
    tog = f"\n{indent}  {toggle.strip()}" if toggle else ""
    return f'<nav class="site-nav" aria-label="Main">{links}{tog}\n{indent}</nav>'


TOGGLE = re.compile(r'<button[^>]*id="theme-toggle".*?</button>', re.S)
A = re.compile(r'(<header>\s*<div class="masthead-inner">.*?)<nav(?:\s+class="site-nav"[^>]*)?>(.*?)</nav>', re.S)
B = re.compile(r'(<header class="top">.*?)<nav class="(?:topnav|site-nav)"[^>]*>(.*?)</nav>', re.S)
C = re.compile(r'(<header>\s*<div class="masthead-inner">.*?)<a [^>]*class="header-link"[^>]*>.*?</a>', re.S)


def fix(rel: str, s: str) -> str | None:
    m = A.search(s)
    if m and m.start(2) - m.start(0) < 1200:          # the nav is in the header, not further down
        tog = TOGGLE.search(m.group(2))
        new = m.group(1) + nav(rel, tog.group(0) if tog else "")
        return s[:m.start()] + new + s[m.end():]
    m = B.search(s)
    if m:
        tog = TOGGLE.search(m.group(2))
        new = m.group(1) + nav(rel, tog.group(0) if tog else "")
        return s[:m.start()] + new + s[m.end():]
    m = C.search(s)
    if m and m.end() - m.start() < 1200:
        head = m.group(1)
        tog = TOGGLE.search(head)                    # move the button into the menu
        if tog:
            head = head[:tog.start()].rstrip() + "\n    " + head[tog.end():].lstrip()
        return s[:m.start()] + head + nav(rel, tog.group(0) if tog else "") + s[m.end():]
    return None


def main():
    changed, done, missed = 0, 0, []
    for f in sorted(ROOT.rglob("*.html")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in SKIP or set(rel.split("/")[:-1]) & SKIP_DIRS or rel.startswith("google"):
            continue
        s = f.read_text(encoding="utf-8")
        out = fix(rel, s)
        if out is None:
            missed.append(rel)
            continue
        done += 1
        if out != s:
            f.write_text(out, encoding="utf-8")
            changed += 1
    print(f"site nav: {done} pages, {changed} changed; no header found in: {', '.join(missed) or 'none'}")


if __name__ == "__main__":
    main()
