"""Fetch the data for the "largest generation per census tract" maps.

Runs on GitHub Actions (census.gov is reachable there). Writes one
GeoPackage per area to ./generations-out/, uploaded as a workflow artifact:

  seattle.gpkg   King, Pierce and Snohomish counties (Seattle-Tacoma-Bellevue MSA)
  tuolumne.gpkg  Tuolumne County, CA

Layers: tracts (points at the Census internal point, with generation counts),
land, water, roads, places (labels) and cities (outlines to draw).

Generations follow the Census age groups in ACS table B01001 (5-year):
  alpha 0-14 · genz 15-29 · millennials 30-44 · genx 45-59 · boomers 60-79 · silent 80+
"""
import io, json, os, sys, urllib.request, zipfile, tempfile
import geopandas as gpd
import pandas as pd

OUT = "generations-out"
os.makedirs(OUT, exist_ok=True)
TIGER = "https://www2.census.gov/geo/tiger"

AREAS = {
    "seattle": {
        "state": "53", "counties": ["033", "053", "061"],
        # counties whose water and roads we draw for context
        "context": ["033", "053", "061", "035", "029", "067", "045"],
        "bbox": (-123.15, 46.80, -121.30, 48.35),
        "cities": ["Seattle", "Tacoma", "Everett", "Bellevue"],
    },
    "tuolumne": {
        "state": "06", "counties": ["109"],
        "context": ["109", "009", "043", "099", "003", "051"],
        "bbox": (-120.75, 37.55, -119.15, 38.55),
        "cities": ["Sonora"],
    },
}

# B01001 age rows: male _003.._025, female _027.._049 (23 groups each)
GEN_OF_GROUP = (["alpha"] * 3 + ["genz"] * 6 + ["millennials"] * 3 + ["genx"] * 3
                + ["boomers"] * 6 + ["silent"] * 2)
GENS = ["alpha", "genz", "millennials", "genx", "boomers", "silent"]


def get(url):
    print("GET", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "brooksgroves.com map script"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def read_zip(url, **kw):
    data = get(url)
    with tempfile.TemporaryDirectory() as d:
        zipfile.ZipFile(io.BytesIO(data)).extractall(d)
        shp = [f for f in os.listdir(d) if f.endswith(".shp")][0]
        return gpd.read_file(os.path.join(d, shp), **kw)


def acs(state, counties):
    """ACS 5-year table B01001 from the Census bulk "table-based summary file"
    (no API key needed)."""
    for year in (2024, 2023):
        url = (f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/"
               f"table-based-SF/data/5YRData/acsdt5y{year}-b01001.dat")
        try:
            raw = pd.read_csv(io.BytesIO(get(url)), sep="|", dtype=str)
            break
        except Exception as e:
            print("ACS", year, "failed:", e)
    else:
        sys.exit("no ACS data")
    raw.columns = [c.strip().upper() for c in raw.columns]
    prefixes = tuple(f"1400000US{state}{c}" for c in counties)
    df = raw[raw.GEO_ID.str.startswith(prefixes)].copy()
    df["GEOID"] = df.GEO_ID.str[9:]
    for g in GENS:
        df[g] = 0
    rows = list(range(3, 26)) + list(range(27, 50))
    for k, i in enumerate(rows):
        df[GEN_OF_GROUP[k]] += pd.to_numeric(df[f"B01001_E{i:03d}"], errors="coerce").fillna(0).clip(lower=0)
    df["total"] = pd.to_numeric(df["B01001_E001"], errors="coerce").fillna(0)
    df["acs_year"] = year
    df["NAME"] = df.GEOID
    print("ACS", year, len(df), "tracts", flush=True)
    return df[["GEOID", "NAME", "total", "acs_year"] + GENS]


year_tiger = "2024"
counties_us = read_zip(f"{TIGER}/GENZ2024/shp/cb_2024_us_county_500k.zip")

for name, a in AREAS.items():
    st = a["state"]
    path = f"{OUT}/{name}.gpkg"
    bbox = a["bbox"]

    df = acs(st, a["counties"])
    tr = read_zip(f"{TIGER}/TIGER{year_tiger}/TRACT/tl_{year_tiger}_{st}_tract.zip")
    tr = tr[tr.COUNTYFP.isin(a["counties"])]
    tr = tr.merge(df, on="GEOID", how="inner")
    pts = gpd.GeoDataFrame(
        tr.drop(columns="geometry"),
        geometry=gpd.points_from_xy(tr.INTPTLON.astype(float), tr.INTPTLAT.astype(float)),
        crs="EPSG:4269")
    pts = pts[["GEOID", "COUNTYFP", "NAME", "ALAND", "total", "acs_year"] + GENS + ["geometry"]]
    pts.to_file(path, layer="tracts", driver="GPKG")
    print(name, len(pts), "tracts, ACS", df.acs_year.iloc[0])

    land = counties_us[counties_us.STATEFP.isin(["53", "06", "41", "32"])].clip(bbox)
    land[["GEOID", "NAME", "STATEFP", "geometry"]].to_file(path, layer="land", driver="GPKG")

    water, roads = [], []
    for c in a["context"]:
        w = read_zip(f"{TIGER}/TIGER{year_tiger}/AREAWATER/tl_{year_tiger}_{st}{c}_areawater.zip")
        water.append(w[w.AWATER > 20000][["FULLNAME", "AWATER", "geometry"]])
        r = read_zip(f"{TIGER}/TIGER{year_tiger}/ROADS/tl_{year_tiger}_{st}{c}_roads.zip")
        r = r[r.MTFCC.isin(["S1100", "S1200", "S1400", "S1630", "S1640"])]
        roads.append(r[["MTFCC", "FULLNAME", "geometry"]])
    gpd.GeoDataFrame(pd.concat(water), crs=w.crs).clip(bbox).to_file(path, layer="water", driver="GPKG")
    rd = gpd.GeoDataFrame(pd.concat(roads), crs=r.crs).clip(bbox)
    rd["geometry"] = rd.geometry.simplify(0.00005)
    rd.to_file(path, layer="roads", driver="GPKG")

    pl = read_zip(f"{TIGER}/GENZ2024/shp/cb_2024_{st}_place_500k.zip").clip(bbox)
    pl[["GEOID", "NAME", "LSAD", "ALAND", "geometry"]].to_file(path, layer="cities", driver="GPKG")
    tp = read_zip(f"{TIGER}/TIGER{year_tiger}/PLACE/tl_{year_tiger}_{st}_place.zip")
    tp = gpd.GeoDataFrame(tp.drop(columns="geometry"),
                          geometry=gpd.points_from_xy(tp.INTPTLON.astype(float), tp.INTPTLAT.astype(float)),
                          crs=tp.crs).clip(bbox)
    tp[["NAME", "LSAD", "CLASSFP", "ALAND", "geometry"]].to_file(path, layer="places", driver="GPKG")
    print(name, "done", os.path.getsize(path) // 1024, "KB", flush=True)
