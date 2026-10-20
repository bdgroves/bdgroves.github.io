"""
Faster images: WebP copies at sensible sizes, used everywhere a page shows
a picture.

    python3 scripts/web_images.py

For every local JPEG or PNG that a page on this site shows in an <img>
(and the homepage carousel's FEATURED images), this writes WebP copies
under img-opt/, keeping the original path in the name:

    /blog/img/secchi/og.jpg  ->  /img-opt/blog/img/secchi/og.jpg.w640.webp
                                 /img-opt/blog/img/secchi/og.jpg.w1600.webp

(no copy wider than the original), then points the <img> at them with a
srcset and a sizes that suits where the picture sits (a card, a cover or
body text), and adds loading="lazy" / decoding="async" to images that
don't say otherwise. A copy is only used when it is at least 15% smaller
than the original. The originals stay put; link previews (og:image) keep
using them, because some sites still don't take WebP there.

Run it last: the other page scripts write plain src= links, and this
turns them into WebP. Re-running only converts new or changed images.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "img-opt"
WIDTHS = (640, 1600)
SKIP_DIRS = {".git", "node_modules", "_site", ".pixi", "img-opt", "games", "hightimes-db", "pagefind"}
CARD = re.compile(r'class="(?:kr-img|topic-img|lead-img|lead-bg)"|class="support-media"|class="lw-media"|tp-card|tp-thumb|tp-other|path-')
SIZES = {
    "card": "(max-width: 600px) 92vw, 400px",
    "cover": "(max-width: 1140px) 100vw, 1100px",
    "body": "(max-width: 760px) 100vw, 760px",
}
_cache: dict[str, dict | None] = {}


def variants(src: str):
    """{width: url} of WebP copies for a site path, making them if needed; None if not worth it."""
    if src in _cache:
        return _cache[src]
    p = ROOT / src.lstrip("/").split("?")[0]
    if not p.exists() or p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        _cache[src] = None
        return None
    orig = p.stat().st_size
    out = {}
    try:
        with Image.open(p) as im:
            im.load()
            w = im.width
            alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            mode = "RGBA" if alpha else "RGB"
            base = im.convert(mode)
            for W in WIDTHS:
                if W > w and out:
                    break
                tw = min(W, w)
                dst = OUT / (src.lstrip("/") + f".w{W}.webp")
                if not dst.exists() or dst.stat().st_mtime < p.stat().st_mtime:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    img = base if tw == w else base.resize((tw, round(base.height * tw / w)), Image.LANCZOS)
                    img.save(dst, "WEBP", quality=80, method=6)
                out[tw] = "/" + dst.relative_to(ROOT).as_posix()
    except Exception as e:                       # unreadable image: leave the page alone
        print("  skip", src, e)
        _cache[src] = None
        return None
    biggest = ROOT / out[max(out)].lstrip("/")
    if biggest.stat().st_size > 0.85 * orig:       # not worth it
        _cache[src] = None
        return None
    _cache[src] = out
    return out


IMG = re.compile(r"<img\b[^>]*>")


def attr(tag, name):
    m = re.search(r'\s%s="([^"]*)"' % name, tag)
    return m.group(1) if m else None


def set_attr(tag, name, value):
    if re.search(r'\s%s="[^"]*"' % name, tag):
        return re.sub(r'(\s%s=")[^"]*(")' % name, lambda m: m.group(1) + value + m.group(2), tag, count=1)
    return tag[:-1].rstrip("/").rstrip() + f' {name}="{value}">'


def original_of(src: str) -> str:
    """/img-opt/a/b.jpg.w640.webp -> /a/b.jpg"""
    m = re.match(r"/img-opt/(.+)\.w\d+\.webp$", src)
    return "/" + m.group(1) if m else src


def rewrite(page: Path, s: str) -> str:
    def fix(m):
        tag = m.group(0)
        src = attr(tag, "src")
        if not src or not src.startswith("/") or src.startswith("//"):
            return tag
        orig = original_of(src)
        v = variants(orig)
        if not v:
            return tag
        ctx = s[max(0, m.start() - 160):m.start()]
        kind = "cover" if "post-cover" in ctx else ("card" if CARD.search(tag + ctx[-120:]) else "body")
        ws = sorted(v)
        pick = v[ws[0]] if kind == "card" else v[ws[-1]]
        tag = set_attr(tag, "src", pick)
        if len(ws) > 1:
            tag = set_attr(tag, "srcset", ", ".join(f"{v[w]} {w}w" for w in ws))
            tag = set_attr(tag, "sizes", SIZES[kind])
        if "loading=" not in tag and "fetchpriority" not in tag:
            tag = set_attr(tag, "loading", "lazy")
        if "decoding=" not in tag:
            tag = set_attr(tag, "decoding", "async")
        return tag
    s = IMG.sub(fix, s)
    if page.name == "index.html" and page.parent == ROOT:
        # the carousel builds its <img> in script from FEATURED
        def feat(m):
            v = variants(original_of(m.group(1)))
            return f'img:"{v[max(v)]}"' if v else m.group(0)
        s = re.sub(r'img:"(/[^"]+\.(?:jpg|jpeg|png|webp))"', feat, s)
    return s


def main():
    pages = changed = 0
    for f in sorted(ROOT.rglob("*.html")):
        rel = f.relative_to(ROOT)
        if set(rel.parts[:-1]) & SKIP_DIRS or rel.name.startswith("google"):
            continue
        s0 = f.read_text(encoding="utf-8")
        s = rewrite(f, s0)
        pages += 1
        if s != s0:
            f.write_text(s, encoding="utf-8")
            changed += 1
    made = [v for v in _cache.values() if v]
    print(f"web images: {pages} pages, {changed} changed; {len(made)} images served as WebP")


if __name__ == "__main__":
    main()
