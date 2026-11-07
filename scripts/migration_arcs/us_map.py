"""Lower-48 view: everyone leaving Tuolumne County, Census ACS 2016-2020 (all destinations)."""
import sys, os, numpy as np, pandas as pd, geopandas as gpd
from PIL import Image
from scene import Terrain
import colors
from build import camera, render
from arcs import arc_points, draw_arcs, dot, visible_mask
from camproj import project
from poster import sky, km, font, text_halo
from PIL import ImageDraw

QUALITY = sys.argv[1] if len(sys.argv) > 1 else "draft"
W, H = (960, 600) if QUALITY == "draft" else (2400, 1500)
CAM = [float(x) for x in os.environ.get("CAM", "-104,37.5,62,36,3600e3,34").split(",")]

exec(open("census_flows.py").read())        # -> c
out = c[c.us & (c.out_est > 0)].copy()
pts = gpd.read_file("data/counties.gpkg", layer="county_points").set_index("GEOID")
home = pts.loc["06109"].geometry

Ter = Terrain("data/dem_us_z6.npz", (-126.0, 23.6, -66.5, 50.4), step=1, exag=10.0, pad=(120, 90))
cols = np.arange(Ter.W); rows = np.arange(Ter.H)
mx_ = Ter.left + (cols + 0.5) * Ter.px; my_ = Ter.top - (rows + 0.5) * Ter.px
lon = np.degrees(mx_ / 6378137.0)[None, :].repeat(Ter.H, 0)
lat = np.degrees(2 * np.arctan(np.exp(my_ / 6378137.0)) - np.pi / 2)[:, None].repeat(Ter.W, 1)
st = gpd.read_file("data/counties.gpkg", layer="states")
in_ca = Ter.grid_pixels(st[st.STUSPS == "CA"].geometry)
in_us = Ter.grid_pixels(st[~st.STUSPS.isin(["AK", "HI", "PR", "GU", "VI", "MP", "AS"])].geometry)
alb = colors.albedo_us(Ter, lon, lat, in_ca, in_us)
sl = Ter.grid_lines(st[~st.STUSPS.isin(["AK", "HI", "PR", "GU", "VI", "MP", "AS"])].geometry, width=1.0)
ws = (sl * 0.55 * (~Ter.ocean))[..., None]
alb = alb * (1 - ws) + np.array([0.95, 0.92, 0.85], np.float32) * ws
Ter.alb = np.concatenate([alb, np.ones(alb.shape[:2] + (1,), np.float32)], -1)
print("grid", Ter.H, Ter.W, "cell km", round(Ter.px / 1000, 2))

cam = camera(Ter, CAM[0], CAM[1], CAM[2], CAM[3], CAM[4], fov=CAM[5], aspect=W / H, exposure=1.75)
tag = f"us_{QUALITY}"
if os.path.exists(f"{tag}_base.png") and "--rerender" not in sys.argv:
    rgba = np.asarray(Image.open(f"{tag}_base.png")).copy(); depth = np.load(f"{tag}_depth.npy")
else:
    rgba, depth = render(Ter, cam, W, H, quality=QUALITY, sun=(240.0, 30.0))
    Image.fromarray(rgba).save(f"{tag}_base.png"); np.save(f"{tag}_depth.npy", depth)
rgba = sky(rgba, depth)

GOLD = (253, 181, 21)
mx = out.out_est.max()
arcs = []
for _, r in out.iterrows():
    g = r.geoid
    if g not in pts.index or g in ("15009", "02020") or g[:2] in ("02", "15"):
        continue                                    # Alaska/Hawaii aren't on this map
    p = pts.loc[g].geometry
    dist = km(Ter, (home.x, home.y), (p.x, p.y)) * 1e3
    h = 18e3 + 0.012 * dist + 950e3 * (r.out_est / mx) ** 0.95
    arcs.append(dict(points=arc_points(Ter, (home.x, home.y), (p.x, p.y), h, n=160), color=GOLD,
                     width_px=(1.2 + 6.5 * (r.out_est / mx) ** 0.6) * W / 1600, alpha=0.95,
                     n=int(r.out_est), moe=r.out_moe, geoid=g, name=r.bname, state=r.bstate))
img = draw_arcs(rgba, arcs, cam, depth)
for a in arcs:
    px, py, _, vis = visible_mask(a["points"][-1][None], cam, W, H, depth)
    if vis[0]:
        img = dot(img, (px[0], py[0]), (1.6 + 3.2 * (a["n"] / mx) ** 0.5) * W / 1600, GOLD)
hx, hz = Ter.world_xz(home.x, home.y)
px, py, _, _ = project(np.array([[hx, float(Ter.ground_y(hx, hz)), hz]]), cam, W, H)
img = dot(img, (px[0], py[0]), 6.5 * W / 1600, (255, 255, 255))
# ---- labels: one per state at its biggest destination, plus California's total ----
d = ImageDraw.Draw(img)
k = W / 1600
fm = font("DMMono-Regular", 13 * k); fm2 = font("DMMono-Medium", 13.5 * k)
oo = out[out.bst != "006"]
bystate = oo.groupby("bstate").out_est.sum().sort_values(ascending=False)
for stname, n in bystate.items():
    if stname in ("Hawaii", "Alaska") or (n < 24 and stname != "Florida"):
        continue
    g = oo[oo.bstate == stname].sort_values("out_est").geoid.iloc[-1]
    if g not in pts.index:
        continue
    p = pts.loc[g].geometry
    x, z = Ter.world_xz(p.x, p.y)
    px_, py_, _, vis = visible_mask(np.array([[x, float(Ter.ground_y(x, z)), z]]), cam, W, H, depth)
    if not (0 < px_[0] < W and 0 < py_[0] < H):
        continue
    text_halo(d, (px_[0] + 9 * k, py_[0] - 2 * k), f"{stname.upper()} {int(n)}", fm, (240, 236, 226), w=int(3 * k), anchor="lm")
top = max(arcs, key=lambda a: a["n"])
P = top["points"]; apex = P[np.argmax(P[:, 1])][None]
apx, apy, _, _ = project(apex, cam, W, H)
text_halo(d, (apx[0] + 10 * k, apy[0] - 4 * k), f"{top['name'].replace(' County', '').upper()} {top['n']}", fm2, GOLD, w=int(3 * k), anchor="lm")
ca_n = int(out[out.bst == "006"].out_est.sum())
text_halo(d, (px[0] + 14 * k, py[0] + 18 * k), f"TUOLUMNE COUNTY", fm2, (255, 255, 255), w=int(3 * k))
text_halo(d, (px[0] + 14 * k, py[0] + 38 * k), f"{ca_n:,} a year stay in California", fm, GOLD, w=int(3 * k))
# ---- title block in the sky, upper left ----
GOLDc = GOLD
ft = font("PlayfairDisplay-Black", 44 * k); fs = font("LibreBaskerville-Regular", 16 * k)
x0, y0 = 46 * k, 40 * k
text_halo(d, (x0, y0), "Stanislaus, a lot.", ft, (255, 255, 255), w=0)
text_halo(d, (x0, y0 + 54 * k), "Florida, not so much.", ft, GOLDc, w=0)
yy = y0 + 124 * k
for line in ["Where people leaving Tuolumne County moved, per year, 2016\u20132020.",
             f"About {int(out.out_est.sum()):,} a year: {ca_n:,} to other California counties and",
             f"{int(oo.out_est.sum()):,} out of state. Taller and thicker arcs mean more people."]:
    text_halo(d, (x0, yy), line, fs, (226, 230, 238), w=0); yy += 23 * k
fo = font("DMMono-Regular", 10 * k)
yy += 8 * k
hi = int(oo[oo.bstate.isin(["Hawaii", "Alaska"])].out_est.sum())
for line in ["Data: US Census Bureau, ACS 2016\u20132020 county-to-county migration flows. These are survey",
             "estimates: the small flows carry wide margins (Florida: 23 \u00b1 37). Not shown: Hawaii and Alaska, "
             f"{hi} a year.",
             "Terrain: AWS Terrain Tiles, 10\u00d7 vertical. Rendered with forge3d. Brooks Groves \u00b7 brooksgroves.com"]:
    d.text((x0, yy), line, font=fo, fill=(185, 196, 212)); yy += 15 * k
img.convert("RGB").save(f"{tag}_arcs.png")
print("arcs", len(arcs), "max", mx, "total out", int(out.out_est.sum()))
