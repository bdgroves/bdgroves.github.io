"""
The flag robot, part 1b: the deeper level. Second-level places (Italy's provinces, France's departments,
Brazil's and Switzerland's municipalities, US counties…), one set per country.

    python flags/tools/build_deep.py            # rebuild if more than 6 days old, else just re-list the sets
    python flags/tools/build_deep.py --force

Writes flags/data/deep/<country>.json and adds the sets to data/packs.json (area "Go deeper").
There are more than 13,000 of these, so their pictures aren't copied into the site: the game shows each one
straight from Wikimedia Commons (a 330 px thumbnail), credited as usual. fetch_flags.py still reads each one
for a printed place name before the game deals it ("ready").
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_packs import DATA, commons_info, filename, gather, pick_flag, qid, sparql, story, tidy_about  # noqa: E402

DEEP = DATA / "deep"
VERSION = 3                 # bump when the rules below change
MIN_FLAGS = 5               # a country needs at least this many to get its own set
SECOND_LEVEL = "Q12357832"  # second-level administrative division

COUNTRIES_Q = f"""SELECT ?country ?countryLabel (COUNT(DISTINCT ?c) AS ?n) WHERE {{
 ?c wdt:P31 ?t . ?t wdt:P279/wdt:P279? wd:{SECOND_LEVEL} . ?c wdt:P41 ?f ; wdt:P17 ?country ; wdt:P625 ?co .
 FILTER NOT EXISTS {{ ?c wdt:P576 [] }} FILTER NOT EXISTS {{ ?country wdt:P576 [] }}
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} GROUP BY ?country ?countryLabel"""


def country_q(cq: str) -> str:
    return f"""SELECT ?item ?itemLabel ?itemDescription ?flag ?coord ?pop ?type ?typeLabel ?parent ?parentLabel ?flagArticle ?article WHERE {{
 ?item wdt:P17 wd:{cq} ; wdt:P31 ?type . ?type wdt:P279/wdt:P279? wd:{SECOND_LEVEL} .
 ?item wdt:P41 ?flag ; wdt:P625 ?coord . FILTER NOT EXISTS {{ ?item wdt:P576 [] }}
 OPTIONAL {{ ?item wdt:P1082 ?pop }} OPTIONAL {{ ?item wdt:P131 ?parent }}
 OPTIONAL {{ ?item wdt:P163 ?fi . ?flagArticle schema:about ?fi ; schema:isPartOf <https://en.wikipedia.org/> }}
 OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }}
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""


def thumb(file: str, width: int | None, mime: str) -> str:
    """A Commons thumbnail URL (330 px), or the original when it's already that small."""
    name = file.replace(" ", "_")
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    q = urllib.parse.quote(name)
    if mime == "image/svg+xml":
        return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/330px-{q}.png"
    if width and width > 330:
        return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/330px-{q}"
    return f"https://upload.wikimedia.org/wikipedia/commons/{h[0]}/{h[:2]}/{q}"


def short_type(label: str) -> str:
    """'province of Italy' -> 'Province'; 'municipality of Brazil' -> 'Municipality'."""
    t = re.split(r"\s+(?:of|in)\s+", label or "", maxsplit=1)[0].strip()
    return (t[:1].upper() + t[1:])[:40] if t else "District"


def plural(t: str) -> str:
    """'municipality' -> 'municipalities'; 'metropolitan city' -> 'metropolitan cities';
    'city with powiat rights' -> 'cities with powiat rights' (the noun before 'with'/'of' takes the plural)."""
    def one(w: str) -> str:
        if w.endswith("y") and w[-2:-1] not in "aeiou":
            return w[:-1] + "ies"
        return w if w.endswith("s") else w + "s"
    words = t.lower().split()
    cut = next((i for i, w in enumerate(words) if w in ("with", "of", "in")), len(words))
    words[cut - 1] = one(words[cut - 1])
    return " ".join(words)


def list_sets(meta: list[dict]) -> None:
    """Put the deep sets into packs.json (build_packs.py rewrites that file weekly without them)."""
    path = DATA / "packs.json"
    if not path.exists():
        return
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["packs"] = [p for p in doc["packs"] if p.get("area") != "Go deeper"] + meta
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    DEEP.mkdir(parents=True, exist_ok=True)
    index_path = DEEP / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    fresh = index.get("version") == VERSION and index.get("built") and \
        (dt.date.today() - dt.date.fromisoformat(index["built"])).days < 7
    if fresh and "--force" not in sys.argv:
        list_sets(index["packs"])
        print(f"deep sets built {index['built']}; re-listed {len(index['packs'])} of them")
        return 0

    # everything the first-level sets already have stays there
    taken = set()
    for p in DATA.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "flags" in d:
            taken |= {f.get("q") for f in d["flags"]}
    stories_path = DATA / "stories.json"
    stories = json.loads(stories_path.read_text(encoding="utf-8")) if stories_path.exists() else {}
    named = json.loads((DATA / "named.json").read_text(encoding="utf-8")) if (DATA / "named.json").exists() else {}
    overrides = json.loads((DATA / "overrides.json").read_text(encoding="utf-8")) if (DATA / "overrides.json").exists() else {}

    countries = [(qid(r["country"]), r.get("countryLabel", ""), int(r["n"])) for r in sparql(COUNTRIES_Q)]
    countries = sorted([c for c in countries if c[2] >= MIN_FLAGS], key=lambda c: -c[2])
    print(f"{len(countries)} countries with {sum(c[2] for c in countries)} second-level flags", flush=True)

    meta, today = [], dt.date.today().isoformat()
    old = {p["id"]: p for p in index.get("packs", [])}
    for cq, cname, n in countries:
        pid = "deep-" + cq.lower()
        try:
            recs = gather(sparql(country_q(cq)), extra=("type", "parent"))
        except RuntimeError as e:                      # Wikidata too slow for this one today: keep last week's
            print(f"  {cname}: {e}; keeping the old set", file=sys.stderr)
            if pid in old:
                meta.append(old[pid])
            continue
        recs = {k: o for k, o in recs.items() if k not in taken and o["coord"] and o["flags"]
                and not all("former" in (tl or "").lower() for _, tl in o["type"])}   # a former municipality is gone
        files = {o["q"]: pick_flag(o["flags"]) for o in recs.values()}
        info = commons_info(sorted(set(files.values())), size=True)
        flags, types = [], {}
        for o in sorted(recs.values(), key=lambda o: (-(o["pop"] or 0), o["name"])):
            c = info.get(files[o["q"]])
            if not c:
                continue
            live = sorted((t for t in o["type"] if "former" not in (t[1] or "").lower()), key=lambda t: t[1])
            t = short_type(live[0][1]) if live else "District"
            types[t] = types.get(t, 0) + 1
            parent = sorted(o["parent"], key=lambda x: x[1])
            fid = o["q"].lower()
            rec = {"id": fid, "q": o["q"], "name": o["name"], "region": parent[0][1] if parent and parent[0][1] else cname,
                   "country": cname, "kind": "division", "type": t, "lat": o["coord"][0], "lon": o["coord"][1],
                   "pop": o["pop"] or None, "about": tidy_about(o["desc"]), "wiki": o["article"],
                   "img": thumb(files[o["q"]], c.pop("width", None), c.pop("mime", "")),
                   "src": "https://commons.wikimedia.org/wiki/Special:FilePath/" + files[o["q"]].replace(" ", "_") + "?width=960",
                   "credit": c}
            a = o["flag_article"]
            if a:
                if a not in stories:
                    stories[a] = story(a); time.sleep(0.05)
                if stories[a]:
                    rec["story"], rec["story_url"] = stories[a], a
            if fid in named:                            # already read by fetch_flags.py
                rec["ready"] = True
                if overrides.get(fid, bool(named[fid])):
                    rec["named"] = True
            flags.append(rec)
        if len(flags) < MIN_FLAGS:
            continue
        top = sorted(types.items(), key=lambda x: -x[1])[:2]
        blurb = " and ".join(plural(t) for t, _ in top).capitalize()
        (DEEP / f"{cq.lower()}.json").write_text(json.dumps({"id": pid, "name": cname, "blurb": blurb, "flags": flags},
                                                            ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        meta.append({"id": pid, "name": cname, "area": "Go deeper", "blurb": blurb, "count": len(flags),
                     "file": f"data/deep/{cq.lower()}.json", "remote": True})
        print(f"  {cname}: {len(flags)}", flush=True)
    meta.sort(key=lambda m: m["name"])
    index = {"built": today, "version": VERSION, "packs": meta}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    stories_path.write_text(json.dumps(stories, ensure_ascii=False, indent=0), encoding="utf-8")
    list_sets(meta)
    print(f"{sum(m['count'] for m in meta)} deep flags in {len(meta)} sets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
