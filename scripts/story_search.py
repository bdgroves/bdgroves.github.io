"""
Give a story site (memoir, Westin, Journal, Y2K) its own search page.

    python3 scripts/story_search.py ../brooks-memoir

Writes REPO/search.html from the site's own index.html: the same <head>, gate,
menu and footer, with a Pagefind search in the middle that searches only that
site. The index itself (REPO/pagefind/) is built by the site's
.github/workflows/search-index.yml on every push, which this also writes.
The menu's search box on those sites already points at /search.html
(scripts/site_nav.py --other-site).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NAMES = {"brooks-memoir": "the Memoir", "westin-stories": "Westin Stories",
         "y2k-journal": "the Y2K Journal", "brooks-journal": "the Journal"}
EXAMPLES = {"brooks-memoir": ["Datsun", "Paragon", "Memorial Hall"],
            "westin-stories": ["Cantina", "Beanie Babies", "New Year"],
            "y2k-journal": ["geocache", "ferrets", "marathon"],
            "brooks-journal": ["Icefields", "Koningsdam", "Myles"]}
EXCLUDE = ("header, nav, footer, #gate, #gate-overlay, .gate, .site-footer, .article-footer, "
           ".reactions-section, .series-box, script, style, noscript")

STYLE = """
<link href="/pagefind/pagefind-ui.css" rel="stylesheet">
<style>
  .ss-main { max-width:860px; margin:0 auto; padding:clamp(2.5rem,6vw,4rem) clamp(1.25rem,5vw,3rem) 4rem; }
  .ss-eyebrow { font-family:'DM Mono',monospace; font-size:.62rem; letter-spacing:.18em; text-transform:uppercase; color:var(--stone); margin:0 0 .6rem; }
  .ss-title { font-family:'Playfair Display',serif; font-size:clamp(2.2rem,5vw,3.2rem); font-weight:900; line-height:1.05; margin:0 0 .6rem; }
  .ss-title em { color:var(--rust); }
  .ss-lede { color:var(--stone); line-height:1.7; margin:0 0 1.75rem; }
  .ss-lede a { color:var(--rust); }
  #search {
    --pagefind-ui-scale:.95; --pagefind-ui-primary:var(--rust); --pagefind-ui-text:var(--ink);
    --pagefind-ui-background:var(--white); --pagefind-ui-border:var(--mist); --pagefind-ui-tag:var(--cream);
    --pagefind-ui-border-width:1px; --pagefind-ui-border-radius:0; --pagefind-ui-font:'Libre Baskerville',Georgia,serif;
  }
  #search .pagefind-ui__result-link { font-family:'Playfair Display',serif; font-weight:700; color:var(--ink); }
  #search .pagefind-ui__result-link:hover { color:var(--rust); }
  #search .pagefind-ui__message, #search .pagefind-ui__button { font-family:'DM Mono',monospace; }
</style>
"""

WORKFLOW = """name: Search index

# Rebuilds this site's search (pagefind/) whenever a page changes, so
# /search.html always finds the latest stories. Made by bdgroves.github.io's
# scripts/story_search.py.
on:
  push:
    branches: [main]
    paths: ["**.html", ".github/workflows/search-index.yml"]
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: search-index
  cancel-in-progress: true

jobs:
  index:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Build the index (pages only; menus, footers and the gate left out)
        run: |
          python3 - "$RUNNER_TEMP/stage" <<'PY'
          import html, pathlib, re, sys
          dst = pathlib.Path(sys.argv[1])
          for f in pathlib.Path(".").rglob("*.html"):
              if f.parts[0] in (".git", "pagefind", ".github") or f.name in ("search.html", "entry-template.html"):
                  continue
              s = f.read_text(encoding="utf-8", errors="replace")
              # results take their title from <title>, not the gate's "Private Archive"
              m = re.search(r"<title>(.*?)</title>", s, re.S)
              t = re.split(r"\\s+[—·|]\\s+Brooks Groves", html.unescape(m.group(1)).strip())[0] if m else ""
              if t:
                  s = re.sub(r"<body([^>]*)>", lambda b: '<body' + b.group(1) + ' data-pagefind-meta="title:' + html.escape(t, quote=True) + '">', s, count=1)
              out = dst / f
              out.parent.mkdir(parents=True, exist_ok=True)
              out.write_text(s, encoding="utf-8")
          PY
          rm -rf pagefind
          npx -y pagefind@1.3.0 --site "$RUNNER_TEMP/stage" --output-path pagefind \\
            --exclude-selectors "{exclude}"
      - name: Commit if it changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A pagefind
          git diff --cached --quiet && exit 0
          git commit -q -m "search: rebuild index [skip ci]"
          for i in 1 2 3; do git pull -q --rebase && git push -q && exit 0; sleep 5; done
          exit 1
"""


def main() -> None:
    repo = Path(sys.argv[1]).resolve()
    name = NAMES.get(repo.name, "this site")
    s = (repo / "index.html").read_text(encoding="utf-8")
    head_end = s.index("</header>") + len("</header>")
    foot = s.index("<footer")
    top, tail = s[:head_end], s[foot:]
    top = re.sub(r"<title>.*?</title>", f"<title>Search · {name.replace('the ', '').strip()} · Brooks Groves</title>", top, count=1, flags=re.S)
    top = re.sub(r'(<meta name="description" content=")[^"]*', rf"\1Search {name}.", top, count=1)
    top = re.sub(r'<link rel="canonical"[^>]*>\n?', "", top)
    top = top.replace("</head>", STYLE + "</head>", 1)
    ex = " or ".join(f'<a href="?q={q.replace(" ", "+")}">{q}</a>' for q in EXAMPLES.get(repo.name, []))
    main_html = f"""

<main class="ss-main" data-pagefind-ignore="all">
  <p class="ss-eyebrow">Brooks Groves</p>
  <h1 class="ss-title">Search <em>{name.replace('the ', '')}</em></h1>
  <p class="ss-lede">Every story on this site. Try {ex}. To search the main site instead, use <a href="https://brooksgroves.com/search/">brooksgroves.com/search</a>.</p>
  <div id="search"></div>
  <noscript><p>Search needs JavaScript.</p></noscript>
</main>
<script src="/pagefind/pagefind-ui.js"></script>
<script>
  (function(){{
    if (!window.PagefindUI) {{ document.getElementById('search').innerHTML = '<p>Search isn’t available just now.</p>'; return; }}
    var ui = new PagefindUI({{ element:'#search', showSubResults:true, showImages:false, resetStyles:false,
                              translations:{{ placeholder:'Search {name.replace("the ", "")}' }} }});
    var q = new URLSearchParams(location.search).get('q');
    if (q) ui.triggerSearch(q);
  }})();
</script>

"""
    (repo / "search.html").write_text(top + main_html + tail, encoding="utf-8")
    wf = repo / ".github" / "workflows" / "search-index.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(WORKFLOW.replace("{exclude}", EXCLUDE), encoding="utf-8")
    print(f"story search: {repo.name}/search.html and its workflow written")


if __name__ == "__main__":
    main()
