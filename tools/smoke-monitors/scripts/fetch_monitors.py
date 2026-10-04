"""Download hourly PM2.5 from the air-quality monitors in and around Washington.

For comparing the HRRR-Smoke model with what monitors on the ground measured,
over the same window as the animation (config.START to config.END).

The readings come from AirNow, the EPA's real-time air-quality system, which
collects every state, tribal and federal monitor (including the temporary
smoke monitors the Forest Service sets up near big fires). AirNow publishes one
file per hour for the whole country, free and with no key:

    https://files.airnowtech.org/airnow/YYYY/YYYYMMDD/HourlyData_YYYYMMDDHH.dat

Each line is  date|time|AQSID|site|GMT offset|parameter|units|value|source,
with the hour in UTC (the hour the average starts). Monitor positions come from
Monitoring_Site_Locations_V2.dat in the same folders. These are AirNow's
real-time numbers: preliminary, before the agencies' final quality checks.

Each hour is cached in data/cache/airnow/ (only the Washington-area PM2.5 lines
are kept, so the cache stays small), and an interrupted run picks up where it
stopped. The result is one CSV:

    data/monitors_pm25_<START>_<END>.csv   site, name, lat, lon, agency, time_utc, pm25

    pixi run monitors
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

BASE = "https://files.airnowtech.org/airnow"
CACHE = config.DATA / "cache" / "airnow"
OUT = config.DATA / f"monitors_pm25_{config.START}_{config.END}.csv"
SITES = CACHE / "sites.csv"
MARGIN = 0.3                         # degrees around the animation's box
HEADERS = {"User-Agent": "wa-smoke (brooksgroves.com)"}


def get(url: str, tries: int = 4) -> bytes | None:
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            time.sleep(3 * (k + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"Could not download {url}")


def inside(lat: float, lon: float) -> bool:
    return (config.SOUTH - MARGIN <= lat <= config.NORTH + MARGIN
            and config.WEST - MARGIN <= lon <= config.EAST + MARGIN)


def hours() -> list[dt.datetime]:
    t = dt.datetime.fromisoformat(config.START)
    end = dt.datetime.fromisoformat(config.END) + dt.timedelta(hours=23)
    out = []
    while t <= end:
        out.append(t)
        t += dt.timedelta(hours=1)
    return out


# ── where the monitors are ───────────────────────────────────────────────────
def parse_locations(text: str) -> dict:
    """Monitoring_Site_Locations_V2.dat: pipe-delimited, one line per monitor and parameter.
    Columns: StationID|AQSID|FullAQSID|Parameter|MonitorType|SiteCode|SiteName|Status|AgencyID|
    AgencyName|EPARegion|Latitude|Longitude|Elevation|GMTOffset|CountryFIPS|CBSA_ID|CBSA_Name|
    StateAQSCode|StateAbbreviation|CountyAQSCode|CountyName"""
    sites = {}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    head = [h.strip().lower() for h in lines[0].split("|")] if lines and "latitude" in lines[0].lower() else None
    col = (lambda name, default: head.index(name) if head and name in head else default)
    i_id, i_par, i_type = col("aqsid", 1), col("parameter", 3), col("monitortype", 4)
    i_name, i_agency, i_lat, i_lon = col("sitename", 6), col("agencyname", 9), col("latitude", 11), col("longitude", 12)
    for ln in lines[1 if head else 0:]:
        f = ln.split("|")
        try:
            lat, lon = float(f[i_lat]), float(f[i_lon])
        except (IndexError, ValueError):
            continue
        if not inside(lat, lon):
            continue
        rec = sites.setdefault(f[i_id].strip(), {"name": f[i_name].strip(), "lat": lat, "lon": lon,
                                                  "agency": f[i_agency].strip(), "type": f[i_type].strip(),
                                                  "pm25": False})
        if "PM2.5" in f[i_par].upper():
            rec["pm25"] = True
    return sites


def parse_aqobs(text: str) -> dict:
    """Fallback: HourlyAQObs_YYYYMMDDHH.dat is a CSV with a header and site positions."""
    sites = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            lat, lon = float(r["Latitude"]), float(r["Longitude"])
        except (KeyError, ValueError):
            continue
        if inside(lat, lon):
            sites[r["AQSID"].strip()] = {"name": r.get("SiteName", "").strip(), "lat": lat, "lon": lon,
                                         "agency": r.get("DataSource", "").strip(), "type": "", "pm25": True}
    return sites


def find_sites(days: list[dt.date]) -> dict:
    """Monitor positions, gathered from a few days across the window (temporary smoke
    monitors come and go)."""
    sites = {}
    picks = days[:: max(1, len(days) // 6)] + [days[-1]]
    for d in picks:
        raw = get(f"{BASE}/{d:%Y}/{d:%Y%m%d}/Monitoring_Site_Locations_V2.dat")
        if raw:
            for k, v in parse_locations(raw.decode("utf-8", "replace")).items():
                sites.setdefault(k, v)
        else:
            raw = get(f"{BASE}/{d:%Y}/{d:%Y%m%d}/HourlyAQObs_{d:%Y%m%d}12.dat")
            if raw:
                for k, v in parse_aqobs(raw.decode("utf-8", "replace")).items():
                    sites.setdefault(k, v)
    return sites


# ── the readings ─────────────────────────────────────────────────────────────
def fetch_hour(t: dt.datetime, ids: set[str]) -> list[list[str]]:
    """PM2.5 lines for our monitors in one hourly file (cached)."""
    cache = CACHE / f"{t:%Y%m%d%H}.csv"
    if cache.exists():
        with open(cache, newline="") as f:
            return list(csv.reader(f))
    raw = get(f"{BASE}/{t:%Y}/{t:%Y%m%d}/HourlyData_{t:%Y%m%d%H}.dat")
    rows = []
    if raw:
        for ln in raw.decode("utf-8", "replace").splitlines():
            f = ln.split("|")
            if len(f) < 8 or f[2].strip() not in ids or f[5].strip().upper() not in ("PM2.5", "PM25"):
                continue
            try:
                v = float(f[7])
            except ValueError:
                continue
            if 0 <= v < 2000:                                  # -999 is missing
                rows.append([f[2].strip(), f"{t:%Y-%m-%dT%H:00}", f"{v:g}", f[8].strip() if len(f) > 8 else ""])
    with open(cache, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    if raw is None:                                            # don't cache a missing file as empty forever
        cache.unlink()
    return rows


def main() -> int:
    if OUT.exists():
        print(f"Monitor readings already present: {OUT.name}")
        return 0
    CACHE.mkdir(parents=True, exist_ok=True)
    hrs = hours()
    days = sorted({h.date() for h in hrs})
    print(f"AirNow monitors around Washington, {config.START} to {config.END}...")
    if SITES.exists():
        with open(SITES, newline="") as f:
            sites = {r["site"]: {**r, "lat": float(r["lat"]), "lon": float(r["lon"])} for r in csv.DictReader(f)}
    else:
        sites = find_sites(days)
        if not sites:
            print("Couldn't read the monitor locations from AirNow. Check https://files.airnowtech.org/airnow/ "
                  "opens in a browser, then try again.")
            return 1
        with open(SITES, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["site", "name", "lat", "lon", "agency", "type"])
            for k, v in sorted(sites.items()):
                w.writerow([k, v["name"], f"{v['lat']:.5f}", f"{v['lon']:.5f}", v["agency"], v.get("type", "")])
    ids = set(sites)
    print(f"  {len(ids)} monitoring sites in the box; {len(hrs)} hourly files to read")

    rows, t0, done = [], time.time(), 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for fut in as_completed([pool.submit(fetch_hour, t, ids) for t in hrs]):
            rows += fut.result()
            done += 1
            if done % 24 == 0 or done == len(hrs):
                rate = done / max(time.time() - t0, 1e-6)
                print(f"  {done}/{len(hrs)} hours  ~{(len(hrs) - done) / max(rate, 1e-6) / 60:.0f} min left", end="\r")
    print()
    if not rows:
        print("No PM2.5 readings found. Check data/cache/airnow/ and the AirNow site.")
        return 1
    rows.sort(key=lambda r: (r[0], r[1]))
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["site", "name", "lat", "lon", "agency", "time_utc", "pm25", "source"])
        for sid, t, v, src in rows:
            s = sites[sid]
            w.writerow([sid, s["name"], f"{s['lat']:.5f}", f"{s['lon']:.5f}", s["agency"], t, v, src])
    n_sites = len({r[0] for r in rows})
    top = max(rows, key=lambda r: float(r[2]))
    print(f"Saved {OUT.name}: {len(rows):,} hourly PM2.5 readings from {n_sites} monitors; "
          f"highest {float(top[2]):.0f} µg/m³ at {sites[top[0]]['name']} ({top[1]} UTC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
