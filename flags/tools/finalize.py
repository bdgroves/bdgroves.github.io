"""
The flag robot, part 3: mark which flags are ready to play, write the search list, and schedule Flag of the Day.

    python flags/tools/finalize.py

- Every pack: "ready": true on flags whose picture is saved (the game only deals ready flags).
- data/places.json: every place once, for Flag of the Day's guess box.
- data/daily.json: one flag per day, the same for everyone. Days already scheduled never change; this only
  adds days up to three weeks ahead. Each weekday has a theme:
    Mon country · Tue US state, Canadian province or Mexican state · Wed world region · Thu country
    Fri city · Sat world region · Sun Pacific Northwest
"""
from __future__ import annotations

import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
START = dt.date(2026, 10, 27)                  # Flag of the Day #1
AHEAD = 21

CATS = {
    "country": ["world"],
    "state": ["us-states", "canada", "mexico"],
    "region": [f"regions-{c}" for c in ("africa", "americas", "europe", "asia", "oceania")],
    "city": ["us-cities"] + [f"cities-{c}" for c in ("africa", "americas", "europe", "asia", "oceania")],
    "northwest": ["pnw"],
}
WEEK = ["country", "state", "region", "country", "city", "region", "northwest"]     # Monday first


def fit_for_daily(cat: str, f: dict) -> bool:
    """Keep the daily flag findable: well-known regions and cities, every country, state and Northwest flag."""
    if not f.get("ready") or f.get("named"):
        return False
    if cat == "region":
        return bool(f.get("story")) or (f.get("pop") or 0) >= 2_000_000
    if cat == "city":
        return bool(f.get("story") or f.get("note")) or (f.get("pop") or 0) >= 500_000
    return True


def main() -> int:
    packs = {}
    for p in sorted(DATA.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and "flags" in doc and "id" in doc:
            changed = False
            for f in doc["flags"]:
                ready = (ROOT / f["img"]).exists()
                if bool(f.get("ready")) != ready:
                    f["ready"] = ready; changed = True
            if changed:
                txt = json.dumps(doc, ensure_ascii=False, indent=1) if p.stem == "pnw" else json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
                p.write_text(txt + ("\n" if p.stem == "pnw" else ""), encoding="utf-8")
            packs[doc["id"]] = doc

    # every place once, for the guess box: [id, name, region, kind, lat, lon, pack]
    places, seen = [], set()
    for cat, ids in CATS.items():
        for pid in ids:
            for f in packs.get(pid, {}).get("flags", []):
                key = f.get("q") or f["id"]
                if key in seen:
                    continue
                seen.add(key)
                places.append([f["id"], f["name"], f["region"], f["kind"], f["lat"], f["lon"], pid])
    (DATA / "places.json").write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Flag of the Day
    path = DATA / "daily.json"
    daily = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"start": START.isoformat(), "days": {}}
    days = daily["days"]
    home = {f["id"]: pid for pid, doc in packs.items() for f in doc["flags"]}
    for v in days.values():                     # a rebuild can move a place to another pack: keep the day, fix the address
        if v["id"] in home and home[v["id"]] != v["pack"]:
            v["pack"] = home[v["id"]]
    last = max((dt.date.fromisoformat(d) for d in days), default=START - dt.timedelta(days=1))
    end = dt.date.today() + dt.timedelta(days=AHEAD)
    d = last + dt.timedelta(days=1)
    added = 0
    while d <= end:
        cat = WEEK[d.weekday()]
        recent = {v["id"] for k, v in days.items() if (d - dt.date.fromisoformat(k)).days < 365}
        pool = [(pid, f) for pid in CATS[cat] for f in packs.get(pid, {}).get("flags", []) if fit_for_daily(cat, f)]
        fresh = [x for x in pool if x[1]["id"] not in recent] or pool
        if not fresh:
            print(f"  {d}: no {cat} flags ready yet; stopping here")
            break
        pid, f = random.Random(d.isoformat()).choice(sorted(fresh, key=lambda x: x[1]["id"]))
        days[d.isoformat()] = {"id": f["id"], "pack": pid, "cat": cat}
        added += 1
        d += dt.timedelta(days=1)
    daily["days"] = dict(sorted(days.items()))
    path.write_text(json.dumps(daily, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(places)} places; {added} day(s) added to Flag of the Day (through {max(days) if days else 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
