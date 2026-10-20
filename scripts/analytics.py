"""
Cloudflare Web Analytics on every page of brooksgroves.com.

    python3 scripts/analytics.py

Reads the site token from data/analytics.json. With a token, it adds
Cloudflare's beacon (one small deferred script, no cookies, so no consent
banner) just before </body> on every page, between ANALYTICS markers.
With an empty token it removes the beacon everywhere, so switching it
off is: clear the token and re-run.

The story sites (journal, memoir, Y2K, Westin) are private and are not
included. The Home topics workflow runs this.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", "_site", ".pixi", "img-opt", "pagefind"}
BLOCK = re.compile(r"<!-- ANALYTICS:START -->.*?<!-- ANALYTICS:END -->\n", re.S)


def main():
    token = json.loads((ROOT / "data/analytics.json").read_text(encoding="utf-8")).get("cloudflare_token", "").strip()
    if token and not re.fullmatch(r"[0-9a-f]{32}", token):
        raise SystemExit("data/analytics.json: cloudflare_token should be 32 hex characters")
    snippet = ("<!-- ANALYTICS:START -->"
               f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
               f"data-cf-beacon='{{\"token\": \"{token}\"}}'></script>"
               "<!-- ANALYTICS:END -->\n") if token else ""
    changed = pages = 0
    for f in sorted(ROOT.rglob("*.html")):
        rel = f.relative_to(ROOT)
        if set(rel.parts[:-1]) & SKIP_DIRS or rel.name.startswith("google"):
            continue
        s0 = f.read_text(encoding="utf-8")
        if "</body>" not in s0:
            continue
        s = BLOCK.sub("", s0)
        if snippet:
            i = s.rfind("</body>")
            s = s[:i] + snippet + s[i:]
        pages += 1
        if s != s0:
            f.write_text(s, encoding="utf-8")
            changed += 1
    print(f"analytics: {'on' if token else 'off (no token yet)'}; {pages} pages, {changed} changed")


if __name__ == "__main__":
    main()
