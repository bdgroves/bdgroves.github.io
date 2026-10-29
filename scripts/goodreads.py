"""
The Bookshelf on Outside: writes books.json from Goodreads.

    python3 scripts/goodreads.py            (run daily by .github/workflows/fetch-goodreads.yml)

Goodreads stopped serving its public shelf RSS feeds in October 2026 (every /review/list_rss/
request now answers 404), and the shelf pages need a sign-in. So the books come from three places,
best first, and a failure never empties the shelf:

  1. The RSS feeds, in case Goodreads brings them back.
  2. Currently reading: the public profile page (goodreads.com/user/show/<id>), which still lists it.
  3. Finished books: a Goodreads library export, if one is in the repo at
     data/goodreads_library_export.csv (Goodreads → My Books → Import and export → Export Library).
     Drop a fresh one in whenever; the newest 12 finished books go on the shelf.

Anything that can't be read keeps the last good list from books.json. Covers come from the last
good list or from Goodreads' export ISBNs via Open Library.
"""
from __future__ import annotations

import csv
import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "books.json"
EXPORT = ROOT / "data" / "goodreads_library_export.csv"
USER_ID = "9579797"
SHELF_SIZE = 12
UAS = ["Mozilla/5.0 (compatible; brooksgroves-bot/1.0; +https://brooksgroves.com)",
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"]


def get(url: str) -> str:
    """The page's text, trying each user agent twice; raises with the last reason."""
    last = "no attempt"
    for ua in UAS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.8"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code} {e.reason}"
                if e.code == 404:          # a retired feed won't come back on a retry
                    raise RuntimeError(last)
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            print(f"  {url}: {last} (ua {UAS.index(ua) + 1}, try {attempt + 1})")
            time.sleep(4)
    raise RuntimeError(last)


def from_rss(shelf: str, limit: int) -> list[dict]:
    body = get(f"https://www.goodreads.com/review/list_rss/{USER_ID}?shelf={shelf}")
    if "<rss" not in body[:500]:
        raise RuntimeError("not RSS")
    books = []
    for item in ET.fromstring(body).find("channel").findall("item")[:limit]:
        def tag(name):
            el = item.find(name)
            return el.text.strip() if el is not None and el.text else ""
        books.append({"title": tag("title"), "author": tag("author_name"), "image": tag("book_medium_image_url"),
                      "link": tag("link"), "rating": tag("user_rating"), "shelf": tag("user_shelves"),
                      "read_at": tag("user_read_at")})
    return books


def strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def from_profile() -> list[dict]:
    """Currently reading, from the public profile page's 'currently reading' block."""
    page = get(f"https://www.goodreads.com/user/show/{USER_ID}")
    i = page.find('id="currentlyReadingReviews"')
    if i < 0:
        raise RuntimeError(f"no currently-reading block (page {len(page):,} chars; "
                           f"{'sign-in page' if 'sign_in' in page[:5000] else 'layout changed?'})")
    block = page[i:i + 20000]
    ends = [j for j in (block.find(k, 40) for k in ("Recent updates", "updatesTable", "favoriteGenres",
                                                     "Quotes", "Bookshelves", 'id="friends')) if j > 0]
    block = block[:min(ends)] if ends else block
    print(f"  profile: block of {len(block):,} chars")
    books, seen = [], set()
    for b in re.finditer(r'<a[^>]+class="bookTitle"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
        link = "https://www.goodreads.com" + b.group(1).split("?")[0] if b.group(1).startswith("/") else b.group(1)
        if link in seen:
            continue
        seen.add(link)
        tail = block[b.end():b.end() + 1500]
        head = block[max(0, b.start() - 2000):b.start()]
        author = re.search(r'class="authorName"[^>]*>(.*?)</a>', tail, re.S)
        img = re.findall(r'<img[^>]+src="([^"]+)"', head)
        books.append({"title": strip(b.group(2)), "author": strip(author.group(1)) if author else "",
                      "image": img[-1] if img else "", "link": link,
                      "rating": "", "shelf": "currently-reading", "read_at": ""})
    print(f"  profile: {len(books)} currently reading")
    return books[:3]


def from_export(limit: int, old: list[dict]) -> list[dict]:
    """Newest finished books from a Goodreads library export, covers kept from the last shelf."""
    rows = list(csv.DictReader(open(EXPORT, encoding="utf-8-sig")))
    done = [r for r in rows if (r.get("Exclusive Shelf") or "").strip() == "read"]

    def when(r):
        for k in ("Date Read", "Date Added"):
            try:
                return datetime.strptime((r.get(k) or "").strip(), "%Y/%m/%d")
            except ValueError:
                pass
        return datetime.min
    done.sort(key=when, reverse=True)
    covers = {b["title"].lower(): b.get("image", "") for b in old}
    books = []
    for r in done[:limit]:
        title = r["Title"].strip()
        isbn = re.sub(r"\D", "", r.get("ISBN13") or "") or re.sub(r"\D", "", r.get("ISBN") or "")
        image = covers.get(title.lower()) or (f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg" if isbn else "")
        d = when(r)
        books.append({"title": title, "author": r.get("Author", "").strip(), "image": image,
                      "link": f"https://www.goodreads.com/book/show/{r['Book Id']}" if r.get("Book Id") else "",
                      "rating": (r.get("My Rating") or "").strip(), "shelf": "read",
                      "read_at": d.strftime("%a, %d %b %Y") if d != datetime.min else ""})
    print(f"  export: {len(done)} finished books in {EXPORT.name}; newest: {books[0]['title'] if books else '-'}")
    return books


def main() -> None:
    try:
        out = json.loads(OUT.read_text())
    except Exception:
        out = {}
    out.setdefault("currently_reading", [])
    out.setdefault("recently_read", [])

    # 1 + 2: currently reading
    try:
        out["currently_reading"] = from_rss("currently-reading", 3)
        print(f"currently-reading (RSS): {len(out['currently_reading'])}")
    except Exception as e:
        print(f"currently-reading RSS: {e}")
        try:
            out["currently_reading"] = from_profile()
            print(f"currently-reading (profile): {len(out['currently_reading'])}")
        except Exception as e2:
            print(f"currently-reading profile: {e2}; keeping the last {len(out['currently_reading'])}")

    # 1 + 3: finished
    try:
        books = from_rss("read", SHELF_SIZE)
        if books:
            out["recently_read"] = books
        print(f"read (RSS): {len(books)}")
    except Exception as e:
        print(f"read RSS: {e}")
        if EXPORT.exists():
            books = from_export(SHELF_SIZE, out["recently_read"])
            if books:
                out["recently_read"] = books
        else:
            print(f"read: no {EXPORT.relative_to(ROOT)} yet; keeping the last {len(out['recently_read'])}")

    # a book being read isn't also shown as finished
    reading = {b["title"].lower() for b in out["currently_reading"]}
    out["recently_read"] = [b for b in out["recently_read"] if b["title"].lower() not in reading]
    OUT.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
