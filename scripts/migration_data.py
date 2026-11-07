"""Fetch data for the Tuolumne County migration-arcs project (forge3d).

Runs on GitHub Actions; writes ./migration-out/ which the workflow pushes to the
"migration-data" branch. Contents:

  census_listing.txt      what the Census county-to-county migration folders hold
  census/*                the newest Census ACS county-to-county flow table(s)
  irs_tuolumne.csv        IRS SOI county-to-county flows in and out of Tuolumne (06109), all years found
  counties.gpkg           county internal points (Gazetteer) + county and state outlines (cartographic boundary)
  dem_ca_z8.npz           elevation for California (AWS terrain tiles, zoom 8, Web Mercator)
  dem_us_z6.npz           elevation for the lower 48 (zoom 6)
"""
import io, os, re, sys, zipfile, tempfile, urllib.request, math
import numpy as np

OUT = "migration-out"
os.makedirs(f"{OUT}/census", exist_ok=True)
UA = {"User-Agent": "brooksgroves.com map script"}


def get(url, timeout=300):
    print("GET", url, flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


# ---------- Census ACS county-to-county flows ----------
BASE = "https://www2.census.gov/programs-surveys/demo/tables/geographic-mobility/"
listing = []
try:
    years = sorted(set(re.findall(r'href="(\d{4})/"', get(BASE).decode())))
    folders = []
    for y in years[-6:]:
        html = get(BASE + y + "/").decode()
        for d in re.findall(r'href="(county-to-county[^"/]*)/"', html):
            folders.append(f"{y}/{d}/")
    listing.append("folders: " + ", ".join(folders))
    if folders:
        latest = sorted(folders, key=lambda s: re.findall(r"(\d{4})-(\d{4})", s)[-1] if re.findall(r"(\d{4})-(\d{4})", s) else ("0", "0"))[-1]
        html = get(BASE + latest).decode()
        files = re.findall(r'href="([^"?/][^"]*\.(?:xlsx|xls|csv|zip|txt))"', html)
        listing.append("latest: " + latest)
        listing += ["  " + f for f in files]
        for f in []:
            low = f.lower()
            # the "current residence" and "ins/outs" sorts are national; grab the national file(s)
            # and anything specific to California, skipping per-state files for other states
            if ("california" in low or "_ca" in low or "-ca" in low or "us" in low
                    or "county-to-county" in low or "metro" in low) and "puerto" not in low:
                try:
                    data = get(BASE + latest + f, timeout=600)
                    saved = sum(os.path.getsize(f"{OUT}/census/{x}") for x in os.listdir(f"{OUT}/census"))
                    if len(data) < 90_000_000 and saved + len(data) < 150_000_000:
                        open(f"{OUT}/census/{f}", "wb").write(data)
                        listing.append(f"  saved {f} {len(data)//1024} KB")
                except Exception as e:
                    listing.append(f"  failed {f}: {e}")
except Exception as e:
    listing.append(f"census crawl failed: {e}")
open(f"{OUT}/census_listing.txt", "w").write("\n".join(listing))
print("\n".join(listing))

# ---------- Census ACS flows: Tuolumne rows from the newest national workbook ----------
try:
    import pandas as pd
    links = []
    queue = [BASE + latest]
    while queue and len(links) == 0 or queue and len(queue) < 8:
        folder = queue.pop(0)
        html = get(folder).decode("latin-1")
        found = sorted(set(re.findall(r'href="([^"]+?\.xlsx?)"', html, flags=re.I)))
        links += [folder + x if not x.startswith("http") else x for x in found]
        queue += [folder + d for d in re.findall(r'href="([A-Za-z0-9][^"?/]*/)"', html)]
        if links:
            break
    print("census workbooks:", links, flush=True)
    for url in links:
        name = url.split("/")[-1]
        if "metro" in name.lower() or "puerto" in name.lower():
            continue
        data = get(url, timeout=900)
        print("  ", name, len(data) // 1024, "KB", flush=True)
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=str)
        keep = []
        for sh, d in sheets.items():
            m = d.apply(lambda r: r.astype(str).str.contains("Tuolumne County", na=False).any(), axis=1)
            if m.any():
                head = d.head(4)
                keep.append(pd.concat([head, d[m]]).assign(sheet=sh))
        if keep:
            pd.concat(keep).to_csv(f"{OUT}/census/{name.rsplit('.', 1)[0]}_tuolumne.csv", index=False)
            print("   saved Tuolumne rows", sum(len(k) for k in keep), flush=True)
except Exception as e:
    print("census workbook step failed:", e)

if os.environ.get("ONLY") == "census":
    sys.exit(0)

# ---------- IRS SOI county-to-county ----------
rows = []
for y in range(26, 15, -1):
    yy = f"{y-1:02d}{y:02d}"
    for kind in ("inflow", "outflow"):
        url = f"https://www.irs.gov/pub/irs-soi/county{kind}{yy}.csv"
        try:
            text = get(url).decode("latin-1").splitlines()
        except Exception as e:
            print("  skip", url, e)
            continue
        head = text[0]
        cols = [c.strip().lower() for c in head.split(",")]
        for line in text[1:]:
            parts = line.split(",")
            if len(parts) < len(cols):
                continue
            d = dict(zip(cols, parts))
            try:
                y1 = (int(d["y1_statefips"]), int(d["y1_countyfips"]))
                y2 = (int(d["y2_statefips"]), int(d["y2_countyfips"]))
            except Exception:
                continue
            if (6, 109) in (y1, y2):
                rows.append(f"20{yy[:2]}-20{yy[2:]},{kind}," + line.strip())
        if rows and not os.path.exists(f"{OUT}/irs_header.txt"):
            open(f"{OUT}/irs_header.txt", "w").write("years,file," + head.strip())
open(f"{OUT}/irs_tuolumne.csv", "w").write(
    (open(f"{OUT}/irs_header.txt").read() + "\n" if rows else "") + "\n".join(rows))
print("IRS rows", len(rows))

# ---------- counties ----------
import geopandas as gpd
import pandas as pd


def read_zip(url, inner_ext=".shp"):
    data = get(url)
    with tempfile.TemporaryDirectory() as d:
        zipfile.ZipFile(io.BytesIO(data)).extractall(d)
        f = [x for x in os.listdir(d) if x.endswith(inner_ext)][0]
        if inner_ext == ".txt":
            return pd.read_csv(os.path.join(d, f), sep="\t", dtype=str)
        return gpd.read_file(os.path.join(d, f))


gz = read_zip("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip", ".txt")
gz.columns = [c.strip() for c in gz.columns]
pts = gpd.GeoDataFrame(gz[["USPS", "GEOID", "NAME", "POP"]] if "POP" in gz.columns else gz[["USPS", "GEOID", "NAME"]],
                       geometry=gpd.points_from_xy(gz.INTPTLONG.astype(float), gz.INTPTLAT.astype(float)), crs=4269)
pts.to_file(f"{OUT}/counties.gpkg", layer="county_points", driver="GPKG")
co = read_zip("https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_5m.zip")
co[["GEOID", "STATEFP", "NAME", "geometry"]].to_file(f"{OUT}/counties.gpkg", layer="counties", driver="GPKG")
st = read_zip("https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_5m.zip")
st[["GEOID", "STUSPS", "NAME", "geometry"]].to_file(f"{OUT}/counties.gpkg", layer="states", driver="GPKG")
print("counties", len(pts))

# ---------- elevation (AWS terrain tiles, terrarium encoding) ----------
from PIL import Image


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def dem(bbox, z, name):
    w, s, e, n = bbox
    x0, y0 = tile_xy(w, n, z)
    x1, y1 = tile_xy(e, s, z)
    xs, ys = range(int(x0), int(x1) + 1), range(int(y0), int(y1) + 1)
    arr = np.zeros((len(ys) * 256, len(xs) * 256), np.float32)
    for j, ty in enumerate(ys):
        for i, tx in enumerate(xs):
            png = get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{tx}/{ty}.png", 120)
            im = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(np.float32)
            arr[j*256:(j+1)*256, i*256:(i+1)*256] = im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768
    # web-mercator bounds of the mosaic (in tile units -> meters)
    R = 6378137.0
    def m(tx, ty):
        n2 = 2 ** z
        return (tx / n2 * 2 * math.pi * R - math.pi * R, math.pi * R - ty / n2 * 2 * math.pi * R)
    left, top = m(xs[0], ys[0]); right, bottom = m(xs[-1] + 1, ys[-1] + 1)
    np.savez_compressed(f"{OUT}/{name}.npz", elev=arr.astype(np.float32),
                        bounds_3857=np.array([left, bottom, right, top]), zoom=z)
    print(name, arr.shape, float(arr.min()), float(arr.max()))


dem((-126.5, 31.5, -112.5, 43.0), 8, "dem_ca_z8")
dem((-126.0, 23.5, -66.0, 50.5), 6, "dem_us_z6")
print("done")
