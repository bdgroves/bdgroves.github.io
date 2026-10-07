"""Canonical tags and sitemap.xml for brooksgroves.com.

Google Search Console reported "Duplicate without user-selected canonical":
the same page answers at more than one address (/blog/ and /blog/index.html,
with and without a trailing slash), and no page said which one is the real
one. This script:

  1. adds <link rel="canonical"> to every indexable page that lacks one, and
  2. writes sitemap.xml listing those same canonical addresses.

Pages marked noindex, the 404 page and Google's verification file are left
out. It only covers pages in this repo; the project sites (PELE, secchi,
HopLove...) are separate repos.

Safe to run any time: a page that already has a canonical is not touched.
The deploy workflow runs it before every build, so new pages are covered
without anyone remembering to.

    python scripts/seo.py
"""
from __future__ import annotations

import re
from pathlib import Path

SITE = "https://brooksgroves.com"
ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", "_site", ".pixi", "tools"}
SKIP_FILES = {"404.html"}


def canonical_url(rel: str) -> str:
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[: -len('index.html')]}"
    return f"{SITE}/{rel}"


def pages():
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT).as_posix()
        if set(p.relative_to(ROOT).parts[:-1]) & SKIP_DIRS:
            continue
        if p.name in SKIP_FILES or p.name.startswith("google"):
            continue
        yield p, rel


def main() -> None:
    added, listed = 0, []
    for p, rel in pages():
        s = p.read_text(encoding="utf-8")
        head = s.split("</head>", 1)[0].lower()
        if "</head>" not in s.lower() or re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', head):
            continue
        if 'http-equiv="refresh"' in head:
            continue
        url = canonical_url(rel)
        listed.append(url)
        if 'rel="canonical"' in head:
            continue
        tag = f'<link rel="canonical" href="{url}">'
        m = re.search(r"</title>[ \t]*\n", s, flags=re.I)
        if m:
            indent = re.match(r"[ \t]*", s[s.rfind("\n", 0, m.start()) + 1 :]).group(0)
            s = s[: m.end()] + indent + tag + "\n" + s[m.end() :]
        else:
            i = s.lower().index("</head>")
            s = s[:i] + "  " + tag + "\n" + s[i:]
        p.write_text(s, encoding="utf-8")
        added += 1

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"  <url><loc>{u}</loc></url>" for u in listed]
    xml.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
    print(f"canonical tags added: {added}; sitemap.xml: {len(listed)} pages")


if __name__ == "__main__":
    main()
