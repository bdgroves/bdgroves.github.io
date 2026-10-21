"""
Link-preview tags on every blog post.

    python3 scripts/og_tags.py

When a post is shared on LinkedIn, X, Bluesky, Slack or iMessage, the
preview comes from its og:* and twitter:* tags. Many posts had a title and
description but no picture, so they shared as a bare link. For each post in
blog/ this adds whichever of these is missing:

  og:type (article), og:title, og:description (from the meta description),
  og:url, og:image, twitter:card (summary_large_image)

The picture is the same one the post's Keep-reading card uses
(IMAGE_OVERRIDES, else og:image, else the first image in the post), and
when a post has none, its topic's image, so every post shares with a
picture. An og:image that points at a file that doesn't exist on this site
is replaced the same way.

Tags a post already has are left alone. The added lines sit together under
a comment, so a re-run changes nothing unless a post's picture changes.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from home_topics import ROOT, posts, topic_of, local
from keep_reading import IMAGE_OVERRIDES, card_image, page_file, SIBLING_REPOS, SITE

MARK_START = "<!-- link-preview tags: scripts/og_tags.py -->"
MARK_END = "<!-- /link-preview tags -->"
BLOCK = re.compile(r"\n[ \t]*<!-- link-preview tags: scripts/og_tags.py -->.*?<!-- /link-preview tags -->", re.S)


def meta(s, prop):
    m = (re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), s) or
         re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % re.escape(prop), s))
    return html.unescape(m.group(1)) if m else None


def exists_here(url):
    if not url.startswith(SITE + "/"):
        return True
    rel = url[len(SITE) + 1:].split("?")[0]
    return rel.startswith(SIBLING_REPOS) or (ROOT / rel).exists()


def main():
    cfg = json.loads((ROOT / "data/topics.json").read_text(encoding="utf-8"))
    topics, fallback = cfg["topics"], cfg.get("fallback", cfg["topics"][-1]["id"])
    by_id = {t["id"]: t for t in topics}
    info = {}
    for p in posts():
        u = local(p["url"])
        if u.startswith("/blog/"):
            info[u] = p

    changed = done = 0
    for f in sorted((ROOT / "blog").glob("*.html")):
        if f.name == "index.html":
            continue
        url_path = "/blog/" + f.name
        s0 = f.read_text(encoding="utf-8")
        s = BLOCK.sub("", s0)                         # start from the post's own tags
        p = info.get(url_path)
        add = []
        esc = lambda v: html.escape(v, quote=True)
        if not meta(s, "og:type"):
            add.append('<meta property="og:type" content="article">')
        if not meta(s, "og:title"):
            t = re.search(r"<title>(.*?)</title>", s, re.S)
            title = (p["title"] if p else html.unescape(t.group(1)).split(" — ")[0].split(" | ")[0].strip()) if (p or t) else None
            if title:
                add.append(f'<meta property="og:title" content="{esc(title)}">')
        if not meta(s, "og:description"):
            d = meta(s, "description")
            if d:
                add.append(f'<meta property="og:description" content="{esc(d)}">')
        if not meta(s, "og:url"):
            add.append(f'<meta property="og:url" content="{SITE}{url_path}">')
        img = meta(s, "og:image")
        over = IMAGE_OVERRIDES.get(url_path)
        # a hand-picked picture (IMAGE_OVERRIDES) replaces a topic stand-in;
        # a post's own chosen og:image is kept
        if not img or not exists_here(img) or (over and "/images/features/topic-" in img):
            pic = IMAGE_OVERRIDES.get(url_path) or card_image(f, SITE + url_path)
            if not pic and p:
                pic = by_id.get(topic_of(p, topics, fallback), {}).get("img", "")
            if pic:
                if img:                                   # a broken one: replace it in place
                    s = re.sub(r'(<meta[^>]+property="og:image"[^>]+content=")[^"]*(")', r"\g<1>" + SITE + pic + r"\g<2>", s, count=1)
                else:
                    add.append(f'<meta property="og:image" content="{SITE}{pic}">')
        if meta(s, "twitter:card") == "summary" and (meta(s, "og:image") or any("og:image" in x for x in add)):
            # the small square card wastes the picture; use the large one
            s = re.sub(r'(<meta[^>]+name="twitter:card"[^>]+content=")summary(")', r"\1summary_large_image\2", s, count=1)
        if not meta(s, "twitter:card"):
            add.append('<meta name="twitter:card" content="summary_large_image">')
        if add:
            block = "\n  " + MARK_START + "\n  " + "\n  ".join(add) + "\n  " + MARK_END
            m = re.search(r'\n[ \t]*<meta name="description"[^>]*>', s)
            i = m.end() if m else s.index("</head>")
            s = s[:i] + block + s[i:]
        done += 1
        if s != s0:
            f.write_text(s, encoding="utf-8")
            changed += 1
    print(f"link previews: {done} posts checked, {changed} changed")


if __name__ == "__main__":
    main()
