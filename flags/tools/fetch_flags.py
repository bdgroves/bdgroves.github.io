"""
Download flag pictures for Flag Atlas from Wikimedia Commons.

    python flags/tools/fetch_flags.py

Reads every pack in flags/data/*.json. For each flag whose picture (flags/<img>) doesn't exist yet,
downloads a 960 px rendering from Commons ("src") and saves a WebP no wider than 480 px.
Runs on GitHub's runners (fetch-flags.yml); this workspace and Brooks's PC don't need to.
A flag that can't be fetched is left for the next run.
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent          # flags/
# Wikimedia asks for a descriptive User-Agent with a way to get in touch.
UA = {"User-Agent": "FlagAtlas/1.0 (https://brooksgroves.com/flags/; https://github.com/bdgroves) python-urllib"}


def fetch(url: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            raw = r.read(10_000_000)
        im = Image.open(io.BytesIO(raw))
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
        im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
        if im.width > 480:
            im = im.resize((480, round(im.height * 480 / im.width)), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "WEBP", quality=88, method=6)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  couldn't get {url}: {e}", file=sys.stderr, flush=True)
        return False


def main() -> int:
    got = missing = 0
    for pack in sorted((ROOT / "data").glob("*.json")):
        for f in json.loads(pack.read_text(encoding="utf-8"))["flags"]:
            dest = ROOT / f["img"]
            if dest.exists():
                continue
            if fetch(f["src"], dest):
                got += 1
                print(f"{pack.stem}: {f['name']}", flush=True)
            else:
                missing += 1
            time.sleep(0.5)   # be gentle with Commons
    print(f"{got} picture(s) saved, {missing} still missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
