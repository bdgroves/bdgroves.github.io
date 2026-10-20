"""
Post layout: a cover picture under the headline, and the reading aids.

    python3 scripts/post_polish.py

For every post in blog/ built on the usual template (.article-wrap with an
.article-body), this:

  * puts a full-width cover picture just above the article body, between
    POST-COVER markers, using the post's own picture (IMAGE_OVERRIDES in
    keep_reading.py, else its og:image, else its first image). It is
    skipped when that same picture already opens the article, so nothing
    shows twice, and when a post has no picture of its own;
  * adds <script src="/js/post.js" defer> (reading-progress bar and a
    Contents list for long posts).

The look is in css/site-footer.css under "POSTS". Re-running changes
nothing unless a post's picture changes. The Home topics workflow runs it.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from home_topics import ROOT
from keep_reading import IMAGE_OVERRIDES, card_image, SITE

START = "<!-- POST-COVER:START (scripts/post_polish.py) -->"
END = "<!-- POST-COVER:END -->"
# main() inserts exactly "  " + START ... END + "\n" at the start of a line; this removes exactly that.
COVER_RE = re.compile(r"  <!-- POST-COVER:START.*?<!-- POST-COVER:END -->\n", re.S)
SCRIPT = '<script src="/js/post.js" defer></script>'


def norm(src: str) -> str:
    src = src.replace(SITE, "").split("?")[0]
    src = re.sub(r"^/img-opt/(.+)\.w\d+\.webp$", r"/\1", src)   # a WebP copy counts as its original
    return src.rsplit("/", 1)[-1]


def main():
    done = changed = covers = 0
    for f in sorted((ROOT / "blog").glob("*.html")):
        if f.name == "index.html":
            continue
        s0 = f.read_text(encoding="utf-8")
        if 'class="article-wrap"' not in s0 or 'class="article-body"' not in s0:
            continue
        s = COVER_RE.sub("", s0, count=1)
        url_path = "/blog/" + f.name
        pic = IMAGE_OVERRIDES.get(url_path) or card_image(f, SITE + url_path)
        i = s.index('<div class="article-body"')
        opening = s[i:i + 2500]
        first_imgs = [norm(m) for m in re.findall(r'<img[^>]+src="([^"]+)"', opening)]
        if pic and norm(pic) not in first_imgs:
            title = re.search(r'<h1 class="article-title">(.*?)</h1>', s, re.S)
            alt = html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else ""
            fig = (f'  {START}<figure class="post-cover"><img src="{html.escape(pic)}" alt="" '
                   f'decoding="async" fetchpriority="high"></figure>{END}\n')
            # just above the article body (after the tags, links and meta)
            j = s.rfind("\n", 0, i) + 1
            s = s[:j] + fig + s[j:]
            covers += 1
        if SCRIPT not in s:
            k = s.rfind("</body>")
            s = s[:k] + SCRIPT + "\n" + s[k:]
        done += 1
        if s != s0:
            f.write_text(s, encoding="utf-8")
            changed += 1
    print(f"post polish: {done} posts, {covers} with a cover, {changed} changed")


if __name__ == "__main__":
    main()
