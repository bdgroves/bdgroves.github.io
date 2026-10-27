"""
The flag robot, part 2: download flag pictures from Wikimedia Commons and check them for the place's name.

    python flags/tools/fetch_flags.py

For every flag in flags/data/*.json whose picture (flags/<img>) doesn't exist yet, downloads a 960 px
rendering from Commons ("src"), saves a WebP no wider than 480 px, and reads any lettering on it with
tesseract. If the lettering spells the place's name ("STATE OF OREGON"), the flag is marked "named" so it
sits out the guessing rounds (a giveaway); data/overrides.json can say otherwise for any flag.
Stops after about 20 minutes and leaves the rest for the next run (flags-robot.yml runs hourly).
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent          # flags/
DATA = ROOT / "data"
UA = {"User-Agent": "FlagAtlas/1.0 (https://brooksgroves.com/flags/; https://github.com/bdgroves) python-urllib"}
DEADLINE = time.monotonic() + 20 * 60
HAVE_OCR = shutil.which("tesseract") is not None

# ---------- does the flag spell out its place's name? ----------
STOP = {"CITY", "COUNTY", "STATE", "OF", "THE", "AND", "SAINT", "PORT", "MOUNT", "FALLS", "NORTH", "SOUTH", "EAST",
        "WEST", "NEW", "ISLAND", "LAKE", "REPUBLIC", "KINGDOM", "PROVINCE", "REGION", "DISTRICT", "FEDERAL", "UNITED",
        "STATES", "GREAT", "DEL", "DES", "LES", "LOS", "LAS", "SANTA", "SAN"}


def norm(s: str) -> str:
    return re.sub(r"[^A-Z ]", " ", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper())


def near(a: str, b: str) -> bool:
    """Equal, or one letter added, dropped or changed (OCR slips)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1; continue
        d += 1
        if d > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    return d + (len(b) - j) <= 1


def says_name(im: Image.Image, name: str) -> list[str]:
    keys = {w for w in norm(name).split() if len(w) >= 4 and w not in STOP}
    if not keys or not HAVE_OCR:
        return []
    bg = Image.new("RGBA", im.size, "white"); bg.alpha_composite(im.convert("RGBA"))
    g = bg.convert("L"); g = g.resize((1200, max(1, g.height * 1200 // g.width)), Image.LANCZOS)
    words = set()
    for v in (ImageOps.autocontrast(g), g.point(lambda p: 255 if p > 140 else 0), ImageOps.invert(g).point(lambda p: 255 if p > 140 else 0)):
        fd, t = tempfile.mkstemp(suffix=".png"); os.close(fd); v.save(t)
        try:
            txt = subprocess.run(["tesseract", t, "-", "--psm", "11"], capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            txt = ""
        os.remove(t)
        words |= {w for w in norm(txt).split() if len(w) >= 4}
    hits = set()
    for k in keys:
        for w in words:
            if w == k or (len(k) >= 5 and near(w, k)) or (len(w) >= 5 and w in k and len(w) >= 0.7 * len(k)) or (len(k) >= 5 and k in w):
                hits.add(k)
    return sorted(hits)


# ---------- download ----------
def fetch(url: str) -> Image.Image | None:
    try:
        url = urllib.parse.quote(url, safe=":/?=&%")      # file names can hold dashes like "2021–present"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            raw = r.read(10_000_000)
        im = Image.open(io.BytesIO(raw))
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
        return im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
    except Exception as e:  # noqa: BLE001
        print(f"  couldn't get {url}: {e}", file=sys.stderr, flush=True)
        return None


def main() -> int:
    named_path = DATA / "named.json"
    named = json.loads(named_path.read_text(encoding="utf-8")) if named_path.exists() else {}
    overrides = json.loads((DATA / "overrides.json").read_text(encoding="utf-8")) if (DATA / "overrides.json").exists() else {}
    got = left = 0
    fails: dict[str, int] = {}
    for pack in sorted(DATA.glob("*.json")):
        doc = json.loads(pack.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "flags" not in doc:
            continue
        hand_made = pack.stem == "pnw"                  # its 'named' marks were set by hand
        changed = False
        for f in doc["flags"]:
            dest = ROOT / f["img"]
            if dest.exists():
                continue
            host = urllib.parse.urlsplit(f["src"]).hostname or ""
            if time.monotonic() > DEADLINE or fails.get(host, 0) >= 8:
                left += 1
                continue
            im = fetch(f["src"])
            if im is None:
                fails[host] = fails.get(host, 0) + 1
                left += 1
                continue
            if not hand_made:
                hits = says_name(im, f["name"])
                named[f["id"]] = hits
                n = overrides.get(f["id"], bool(hits))
                if n != bool(f.get("named")):
                    if n:
                        f["named"] = True
                    else:
                        f.pop("named", None)
                    changed = True
                if hits:
                    print(f"  {f['name']}: name on the flag ({', '.join(hits)})")
            small = im if im.width <= 480 else im.resize((480, round(im.height * 480 / im.width)), Image.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            small.save(dest, "WEBP", quality=86, method=6)
            got += 1
            time.sleep(0.3)                             # be gentle with Commons
        if changed:
            pack.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    named_path.write_text(json.dumps(named, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{got} picture(s) saved, {left} left for the next run" + ("" if HAVE_OCR else " (no tesseract: name check skipped)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
