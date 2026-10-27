"""
The flag robot, part 1: build Flag Atlas's packs from Wikidata, Wikimedia Commons and Wikipedia.

    python flags/tools/build_packs.py            # rebuild if the packs are more than 6 days old
    python flags/tools/build_packs.py --force    # rebuild now

Writes flags/data/<pack>.json for every pack below, plus flags/data/packs.json (the picker's list).
The hand-made Pacific Northwest pack (data/pnw.json) is never touched here.
Runs on GitHub's runners (flags-robot.yml); Wikidata isn't reachable from Claude's workspace.

Where things come from:
  places, coordinates, populations, flag files ... Wikidata (CC0)
  licenses and artists ........................ Wikimedia Commons file pages
  "story" ...................................... the opening of Wikipedia's article on that flag,
                                                  shown in the game with credit (CC BY-SA 4.0)
  "named" (place name printed on the flag) ..... fetch_flags.py's text check, data/named.json,
                                                  overridden by data/overrides.json
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # flags/
DATA = ROOT / "data"
UA = {"User-Agent": "FlagAtlas/1.0 (https://brooksgroves.com/flags/; https://github.com/bdgroves) python-urllib",
      "Accept": "application/json"}

CONT = {"Q15": "africa", "Q49": "americas", "Q18": "americas", "Q46": "europe", "Q48": "asia",
        "Q538": "oceania", "Q55643": "oceania", "Q3960": "oceania"}
CONT_ORDER = ["africa", "americas", "europe", "asia", "oceania"]     # Egypt -> Africa, Turkey/Russia -> Europe
CONT_NAME = {"africa": "Africa", "americas": "The Americas", "europe": "Europe", "asia": "Asia", "oceania": "Oceania"}

# The packs, in the order the picker shows them. "area" groups them in the picker.
PACKS = [
    ("world", "Countries", "Start here", "Every country's flag"),
    ("us-states", "US states", "Start here", "All 50 states"),
    ("canada", "Canada", "North America", "Provinces and territories"),
    ("mexico", "Mexico", "North America", "The states of Mexico"),
    ("us-cities", "US cities", "North America", "American cities that fly their own flag"),
    *[(f"regions-{c}", f"Regions: {CONT_NAME[c]}", "Regions of the world", "States, provinces and regions") for c in CONT_ORDER],
    *[(f"cities-{c}", f"Cities: {CONT_NAME[c]}", "Big cities", "Cities of 200,000 people or more") for c in CONT_ORDER],
]

COMMON = """OPTIONAL { ?item wdt:P625 ?coord } OPTIONAL { ?item wdt:P1082 ?pop }
 OPTIONAL { ?item wdt:P163 ?fi . ?flagArticle schema:about ?fi ; schema:isPartOf <https://en.wikipedia.org/> }
 OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }"""
QUERIES = {
    "countries": f"""SELECT ?item ?itemLabel ?itemDescription ?flag ?coord ?pop ?cont ?flagArticle ?article WHERE {{
 ?item wdt:P31 wd:Q3624078 ; wdt:P41 ?flag . FILTER NOT EXISTS {{ ?item wdt:P576 [] }}
 OPTIONAL {{ ?item wdt:P30 ?cont }} {COMMON} }}""",
    "regions": f"""SELECT ?item ?itemLabel ?itemDescription ?flag ?coord ?pop ?country ?countryLabel ?cont ?type ?flagArticle ?article WHERE {{
 ?item wdt:P31 ?type . ?type wdt:P279 wd:Q10864048 . ?item wdt:P41 ?flag ; wdt:P17 ?country .
 FILTER NOT EXISTS {{ ?item wdt:P576 [] }} OPTIONAL {{ ?country wdt:P30 ?cont }} {COMMON} }}""",
    "cities": f"""SELECT ?item ?itemLabel ?itemDescription ?flag ?coord ?pop ?country ?countryLabel ?cont ?flagArticle ?article WHERE {{
 ?item wdt:P31/wdt:P279? wd:Q515 ; wdt:P41 ?flag ; wdt:P1082 ?p0 ; wdt:P17 ?country . FILTER(?p0 >= 200000)
 FILTER NOT EXISTS {{ ?item wdt:P576 [] }} OPTIONAL {{ ?country wdt:P30 ?cont }} {COMMON} }}""",
    "uscities": f"""SELECT ?item ?itemLabel ?itemDescription ?flag ?coord ?pop ?state ?stateLabel ?flagArticle ?article WHERE {{
 ?item wdt:P31/wdt:P279? wd:Q515 ; wdt:P17 wd:Q30 ; wdt:P41 ?flag .
 FILTER NOT EXISTS {{ ?item wdt:P576 [] }}
 OPTIONAL {{ ?item wdt:P131/wdt:P131? ?state . ?state wdt:P31 wd:Q35657 }} {COMMON} }}""",
}
US, CA, MX = "Q30", "Q16", "Q96"
US_STATE, CA_TERRITORY = "Q35657", "Q9357527"


def get(url: str, tries: int = 3, timeout: int = 90):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i + 1} after {e}", file=sys.stderr, flush=True)
            time.sleep(5 * (i + 1))
    raise RuntimeError("gave up on " + url[:120])


def sparql(q: str) -> list[dict]:
    j = get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
    return [{k: v["value"] for k, v in b.items()} for b in j["results"]["bindings"]]


qid = lambda uri: uri.rsplit("/", 1)[-1]
filename = lambda uri: urllib.parse.unquote(uri.rsplit("/", 1)[-1]).replace("_", " ")
PAST = re.compile(r"\(\s*\d{3,4}\s*[–-]\s*\d{2,4}\s*\)|\bformer\b|\bhistoric|\bold\b|\bproposed\b|\bunofficial\b", re.I)


def pick_flag(files: set[str]) -> str:
    """Several flag files: prefer one that isn't marked as old, proposed or unofficial, then the plainest name."""
    return sorted(files, key=lambda f: (bool(PAST.search(f)), not f.lower().endswith(".svg"), len(f), f))[0]


def gather(rows: list[dict], extra: tuple = ()) -> dict:
    """Wikidata hands back one row per combination of values; fold them into one record per place."""
    out: dict[str, dict] = {}
    for r in rows:
        q = qid(r["item"])
        label = r.get("itemLabel", "")
        if not label or re.fullmatch(r"Q\d+", label):
            continue                                   # no English name: skip
        o = out.setdefault(q, {"q": q, "name": label, "desc": r.get("itemDescription", ""), "flags": set(),
                               "pop": 0, "coord": None, "conts": set(), "flag_article": None, "article": None,
                               **{k: set() for k in extra}})
        o["flags"].add(filename(r["flag"]))
        if r.get("pop"):
            try:
                o["pop"] = max(o["pop"], int(float(r["pop"])))
            except ValueError:
                pass
        if r.get("coord") and not o["coord"]:
            m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", r["coord"])
            if m:
                o["coord"] = (round(float(m.group(2)), 4), round(float(m.group(1)), 4))
        if r.get("cont"):
            o["conts"].add(qid(r["cont"]))
        o["flag_article"] = o["flag_article"] or r.get("flagArticle")
        o["article"] = o["article"] or r.get("article")
        for k in extra:
            if r.get(k):
                o[k].add((qid(r[k]), r.get(k + "Label", "")))
    return out


def continent(conts: set[str]) -> str | None:
    named = {CONT[c] for c in conts if c in CONT}
    return next((c for c in CONT_ORDER if c in named), None)


def commons_info(files: list[str]) -> dict[str, dict]:
    info = {}
    strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
    for i in range(0, len(files), 50):
        titles = "|".join("File:" + f for f in files[i:i + 50])
        j = get("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=extmetadata&format=json&titles="
                + urllib.parse.quote(titles))
        norm = {n["to"]: n["from"] for n in j["query"].get("normalized", [])}
        for p in j["query"]["pages"].values():
            if "imageinfo" not in p:
                continue
            m = p["imageinfo"][0].get("extmetadata", {})
            title = norm.get(p["title"], p["title"]).replace("File:", "", 1)
            info[title] = {
                "artist": (strip(m.get("Artist", {}).get("value")) or "")[:90] or None,
                "license": strip(m.get("LicenseShortName", {}).get("value")) or "See Commons",
                "url": m.get("LicenseUrl", {}).get("value") or None,
                "page": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(p["title"][5:].replace(" ", "_")),
            }
        time.sleep(0.3)
    return info


def story(article_url: str) -> str | None:
    """The opening of Wikipedia's article on the flag, cut at a sentence end (at most about 320 characters)."""
    title = article_url.rsplit("/wiki/", 1)[-1]
    try:
        j = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + title + "?redirect=true", tries=2, timeout=30)
    except RuntimeError:
        return None
    if j.get("type") != "standard":
        return None
    text = re.sub(r"\s+", " ", j.get("extract", "")).strip()
    if len(text) <= 320:
        return text or None
    cut = text[:320]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end > 80 else None


def tidy_about(desc: str) -> str:
    d = (desc or "").strip()
    return (d[:1].upper() + d[1:])[:140] if d else ""


def main() -> int:
    stamp = DATA / "packs.json"
    if "--force" not in sys.argv and stamp.exists():
        built = json.loads(stamp.read_text(encoding="utf-8")).get("built", "2000-01-01")
        if (dt.date.today() - dt.date.fromisoformat(built)).days < 7:
            print(f"packs built {built}; nothing to do (use --force to rebuild)")
            return 0

    print("asking Wikidata…", flush=True)
    countries = gather(sparql(QUERIES["countries"]))
    regions = gather(sparql(QUERIES["regions"]), extra=("country", "type"))
    cities = gather(sparql(QUERIES["cities"]), extra=("country",))
    uscities = gather(sparql(QUERIES["uscities"]), extra=("state",))
    print(f"  {len(countries)} countries, {len(regions)} regions, {len(cities)} cities, {len(uscities)} US cities")

    named = json.loads((DATA / "named.json").read_text(encoding="utf-8")) if (DATA / "named.json").exists() else {}
    overrides = json.loads((DATA / "overrides.json").read_text(encoding="utf-8")) if (DATA / "overrides.json").exists() else {}
    stories_cache = json.loads((DATA / "stories.json").read_text(encoding="utf-8")) if (DATA / "stories.json").exists() else {}

    packs: dict[str, list[dict]] = {p[0]: [] for p in PACKS}
    seen: set[str] = set()

    def add(pack: str, o: dict, kind: str, region: str):
        if o["q"] in seen or not o["coord"] or not o["flags"]:
            return
        seen.add(o["q"])
        packs[pack].append({"q": o["q"], "name": o["name"], "region": region, "kind": kind,
                            "lat": o["coord"][0], "lon": o["coord"][1], "pop": o["pop"] or None,
                            "about": tidy_about(o["desc"]), "file": pick_flag(o["flags"]),
                            "wiki": o["article"], "flag_article": o["flag_article"]})

    for o in countries.values():
        c = continent(o["conts"])
        if c:
            add("world", o, "country", CONT_NAME[c])
    for o in regions.values():
        cs = sorted(o["country"])
        if not cs:
            continue
        cq, cname = cs[0]
        types = {t for t, _ in o["type"]}
        if cq == US:
            if US_STATE in types:
                add("us-states", o, "state", "United States")
        elif cq == CA:
            add("canada", o, "territory" if CA_TERRITORY in types or "territory" in o["desc"] else "province", "Canada")
        elif cq == MX:
            add("mexico", o, "mxstate", "Mexico")
        else:
            c = continent(o["conts"])
            if c:
                add(f"regions-{c}", o, "region", cname)
    for o in uscities.values():
        st = sorted(o["state"])
        add("us-cities", o, "city", st[0][1] if st else "United States")
    for o in cities.values():
        cs = sorted(o["country"])
        if not cs or cs[0][0] == US:
            continue
        c = continent(o["conts"])
        if c:
            add(f"cities-{c}", o, "city", cs[0][1])

    allrecs = [f for recs in packs.values() for f in recs]
    print(f"checking {len(allrecs)} flag files on Commons…", flush=True)
    info = commons_info(sorted({f["file"] for f in allrecs}))

    print("reading Wikipedia's flag articles…", flush=True)
    for f in allrecs:
        a = f.pop("flag_article")
        if a:
            if a not in stories_cache:
                stories_cache[a] = story(a)
                time.sleep(0.05)
            if stories_cache[a]:
                f["story"] = stories_cache[a]
                f["story_url"] = a

    meta = []
    today = dt.date.today().isoformat()
    for pid, name, area, blurb in PACKS:
        recs = []
        for f in sorted(packs[pid], key=lambda f: (-(f["pop"] or 0), f["name"])):
            c = info.get(f["file"])
            if not c:
                continue                               # file missing on Commons
            fid = f["q"].lower()
            rec = {"id": fid, **{k: v for k, v in f.items() if k != "file"}, "img": f"img/{fid}.webp",
                   "src": "https://commons.wikimedia.org/wiki/Special:FilePath/" + f["file"].replace(" ", "_") + "?width=960",
                   "credit": c}
            n = overrides.get(fid, bool(named.get(fid)))
            if n:
                rec["named"] = True
            recs.append(rec)
        (DATA / f"{pid}.json").write_text(json.dumps({"id": pid, "name": name, "blurb": blurb, "flags": recs},
                                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        meta.append({"id": pid, "name": name, "area": area, "blurb": blurb, "count": len(recs), "file": f"data/{pid}.json"})
        print(f"  {pid}: {len(recs)}")

    pnw = json.loads((DATA / "pnw.json").read_text(encoding="utf-8"))
    meta.insert(2, {"id": "pnw", "name": pnw["name"], "area": "Start here", "blurb": "Hand-picked, with the stories",
                    "count": len(pnw["flags"]), "file": "data/pnw.json"})
    stamp.write_text(json.dumps({"built": today, "packs": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "stories.json").write_text(json.dumps(stories_cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{sum(m['count'] for m in meta)} flags in {len(meta)} packs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
