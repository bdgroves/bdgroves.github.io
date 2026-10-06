"""Check every external URL found by scan.py; write a markdown report.

    python tools/linkcheck/scan.py . urls.json && python tools/linkcheck/check.py urls.json report.md
"""
import json, sys, concurrent.futures as cf
import urllib.request, urllib.error, ssl
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
SKIP = ("twitter.com/intent", "x.com/intent", "bsky.app/intent", "fonts.googleapis.com", "fonts.gstatic.com",
        "/cdn-cgi/l/email-protection", "linkedin.com", "connect.garmin.com", "strava.com")

def fetch(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 404, 405, 429, 500, 501, 503):
                continue
            return e.code, url
        except Exception as e:
            if method == "HEAD":
                continue
            return f"ERR {type(e).__name__}: {str(e)[:80]}", url
    return "ERR", url

def main(src, out):
    urls = json.load(open(src))
    todo = {u: w for u, w in urls.items() if not any(s in u for s in SKIP)}
    with cf.ThreadPoolExecutor(16) as ex:
        res = dict(zip(todo, ex.map(fetch, todo)))
    bad = {u: r for u, r in res.items() if not (isinstance(r[0], int) and r[0] < 400)}
    lines = [f"# Link check\n\n{len(urls)} URLs found, {len(todo)} checked, {len(bad)} not OK.\n"]
    for u, (code, final) in sorted(bad.items(), key=lambda x: str(x[1][0])):
        lines.append(f"- **{code}** {u}\n  - on: {', '.join(urls[u][:4])}")
    moved = {u: f for u, (c, f) in res.items() if isinstance(c, int) and c < 400 and f.rstrip('/') != u.rstrip('/')}
    lines.append(f"\n## Redirected ({len(moved)})\n")
    lines += [f"- {u} -> {f}" for u, f in sorted(moved.items())]
    open(out, "w").write("\n".join(lines) + "\n")
    print(f"{len(bad)} not OK of {len(todo)}")

if __name__ == "__main__":
    main(*sys.argv[1:3])
