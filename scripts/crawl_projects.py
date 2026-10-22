"""
Bring the project sites into the site search.

    python3 scripts/crawl_projects.py STAGE_DIR

The dashboards and projects (Mother Lode, secchi, PELE, SOLSTICE...) live in
their own repos and are served at brooksgroves.com/<name>/, so they are not in
this repo's build. At deploy time this fetches each one's published pages
(the start page and the pages it links to under the same path, up to a limit)
and saves them under STAGE_DIR/<name>/..., so Pagefind can index them next to
the main site with the right URLs. Nothing fetched here is deployed; only the
search index is.

The list of projects is read from the homepage (FEATURED and the menus) and
data/topics.json, plus EXTRA below, so a new dashboard joins the search on its
own. It prints the glob for Pagefind as the last line.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://brooksgroves.com"
EXTRA = ["30DayMapChallenge/2026", "hoplove", "secchi"]
NOT_PROJECTS = {"search", "tags", "blog", "work", "live", "writing", "learning", "topics", "images", "img",
                "img-opt", "css", "js", "games", "recipes", "about", "maps", "outside"}
MAX_PAGES = 40           # per project
MAX_BYTES = 3_000_000    # skip giant pages (inlined data)


def projects() -> list[str]:
    segs = set(EXTRA)
    for f in ("index.html", "data/topics.json", "maps.html"):
        s = (ROOT / f).read_text(encoding="utf-8")
        found = re.findall(r'https://brooksgroves\.com/([A-Za-z0-9_-]+)/?(?=["\'\s])', s)
        found += re.findall(r'(?:href|url)["=: ]+"/([A-Za-z0-9_-]+)/"', s)
        for seg in found:
            if seg in NOT_PROJECTS or (ROOT / seg).exists() or (ROOT / f"{seg}.html").exists():
                continue          # part of this repo, already in the build
            segs.add(seg)
    return sorted(segs, key=str.lower)


def fetch(url: str) -> tuple[str, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": "brooksgroves-search-indexer"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                if "html" not in r.headers.get("Content-Type", ""):
                    return None
                data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    return None
                return r.geturl(), data.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) == 404:
                return None
            time.sleep(2 * (attempt + 1))
    return None


def crawl(seg: str, stage: Path) -> int:
    base = f"{SITE}/{seg}/"
    seen, queue, n = {base}, deque([base]), 0
    while queue and n < MAX_PAGES:
        url = queue.popleft()
        got = fetch(url)
        if not got:
            continue
        final, html = got
        path = urllib.parse.urlparse(url).path
        rel = path.lstrip("/")
        if rel.endswith("/") or not rel:
            rel += "index.html"
        elif not rel.endswith(".html"):
            rel += "/index.html"
        out = stage / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        n += 1
        for href in re.findall(r'href="([^"#?]+)', html):
            u = urllib.parse.urljoin(final, href)
            u = u.replace(final.split(f"/{seg}/")[0] + f"/{seg}/", base) if f"/{seg}/" in u else u
            if (u.startswith(base) and (u.endswith("/") or u.endswith(".html")) and u not in seen
                    and "/share/" not in u):
                seen.add(u)
                queue.append(u)
    return n


def main() -> None:
    stage = Path(sys.argv[1]).resolve()
    segs = projects()
    total, done = 0, []
    for seg in segs:
        n = crawl(seg, stage)
        print(f"  {seg}: {n} page{'s' if n != 1 else ''}", file=sys.stderr)
        if n:
            done.append(seg)
            total += n
    missed = sorted(set(segs) - set(done))
    print(f"::notice title=Search: project sites::{total} pages from {len(done)} of {len(segs)} projects"
          + (f"; nothing fetched from {', '.join(missed)}" if missed else ""), file=sys.stderr)
    print(",".join(f"{s}/**/*.html" for s in done))


if __name__ == "__main__":
    main()
