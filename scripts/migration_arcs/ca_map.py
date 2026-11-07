"""California view: IRS flows out of (gold) and into (blue) Tuolumne County, 2018-19 to 2022-23."""
import sys, json, numpy as np, pandas as pd, geopandas as gpd
from PIL import Image
from build import build, camera, render, county_points
from arcs import arc_points, draw_arcs, dot, visible_mask
from camproj import project
from poster import sky, labels_and_title, km

QUALITY = sys.argv[1] if len(sys.argv) > 1 else "draft"
W, H = (960, 600) if QUALITY == "draft" else (2400, 1500)

exec(open("flows.py").read())          # -> df, out, inn (IRS)
real = lambda x, col: x[(x[col].str[:2].astype(int) <= 56) & (x[col].str[2:] != "000") & (x[col] != T)]
yrs = sorted(df.years.unique())[-5:]
O = real(out, "d"); O = O[O.years.isin(yrs)].groupby("d").people.sum()
I = real(inn, "o"); I = I[I.years.isin(yrs)].groupby("o").people.sum()

pts = county_points()
home = pts.loc["06109"].geometry
Ter = build()
cam = camera(Ter, -120.6, 36.9, 5, 48, 1560e3, fov=36, aspect=W / H, exposure=1.75)

import os
if os.path.exists(f"ca_base_{QUALITY}.png") and "--rerender" not in sys.argv:
    rgba = np.asarray(Image.open(f"ca_base_{QUALITY}.png")).copy(); depth = np.load(f"ca_depth_{QUALITY}.npy")
else:
    rgba, depth = render(Ter, cam, W, H, quality=QUALITY, sun=(255.0, 32.0))
    np.save(f"ca_depth_{QUALITY}.npy", depth); Image.fromarray(rgba).save(f"ca_base_{QUALITY}.png")
rgba = sky(rgba, depth)

mx = max(O.max(), I.max())
GOLD, BLUE = (253, 181, 21), (86, 170, 255)
arcs = []
for series, color, lean, outward in [(I, BLUE, -28, False), (O, GOLD, 28, True)]:
    for g, n in series.items():
        if g not in pts.index:
            continue
        p = pts.loc[g].geometry
        dist = km(Ter, (home.x, home.y), (p.x, p.y)) * 1e3
        h = 14e3 + 0.07 * dist + 300e3 * (n / mx) ** 0.85
        a, b = ((home.x, home.y), (p.x, p.y)) if outward else ((p.x, p.y), (home.x, home.y))
        arcs.append(dict(points=arc_points(Ter, a, b, h, lean_deg=lean), color=color,
                         width_px=(1.2 + 7.5 * (n / mx) ** 0.6) * W / 1600, alpha=0.95, n=int(n), geoid=g))

img = draw_arcs(rgba, arcs, cam, depth)
# endpoint dots
for a in arcs:
    end = a["points"][-1 if a["color"] == GOLD else 0][None]
    px, py, _, vis = visible_mask(end, cam, W, H, depth)
    if vis[0]:
        img = dot(img, (px[0], py[0]), (1.5 + 3.5 * (a["n"] / mx) ** 0.5) * W / 1600, a["color"])
hx, hz = Ter.world_xz(home.x, home.y)
hp = np.array([[hx, float(Ter.ground_y(hx, hz)), hz]])
px, py, _, _ = project(hp, cam, W, H)
img = dot(img, (px[0], py[0]), 7 * W / 1600, (255, 255, 255))
if "--notext" in sys.argv:
    img.convert("RGB").save(f"ca_arcs_{QUALITY}_notext.png")
    sys.exit(0)
img = labels_and_title(img, arcs, cam, depth, Ter, pts, home, O, I, W, H, GOLD, BLUE, yrs)
img.convert("RGB").save(f"ca_arcs_{QUALITY}.png")
json.dump({"years": yrs, "out": {k: int(v) for k, v in O.sort_values(ascending=False).items()},
           "in": {k: int(v) for k, v in I.sort_values(ascending=False).items()}},
          open("ca_flows.json", "w"), indent=1)
print("arcs", len(arcs), "max", mx)
