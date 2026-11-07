"""Orbit film: arcs rise out of Sonora while the camera circles over the Sierra.

    python film.py --part 3 --parts 20      # renders every 20th frame starting at 3 into frames/
    python film.py --still 150              # one frame, for checking

Arcs: IRS county-to-county flows 2018-19 to 2022-23 (gold = leaving, blue = arriving).
"""
import os, sys, math, argparse, numpy as np, geopandas as gpd
from PIL import Image, ImageDraw
from build import build, camera, render, county_points
from arcs import arc_points, draw_arcs, dot, visible_mask
from camproj import project
from poster import sky, km, font, text_halo

ap = argparse.ArgumentParser()
ap.add_argument("--part", type=int, default=0); ap.add_argument("--parts", type=int, default=1)
ap.add_argument("--still", type=int, default=None); ap.add_argument("--w", type=int, default=1920)
ap.add_argument("--h", type=int, default=1080); ap.add_argument("--quality", default="film")
a = ap.parse_args()

FPS, SECONDS = 24, 14
N = FPS * SECONDS
W, H = a.w, a.h
OUTW, OUTH = 1280, 720
os.makedirs("frames", exist_ok=True)

exec(open("flows.py").read())
real = lambda x, col: x[(x[col].str[:2].astype(int) <= 56) & (x[col].str[2:] != "000") & (x[col] != T)]
yrs = sorted(df.years.unique())[-5:]
O = real(out, "d"); O = O[O.years.isin(yrs)].groupby("d").people.sum()
I = real(inn, "o"); I = I[I.years.isin(yrs)].groupby("o").people.sum()
pts = county_points()
names = pts["NAME"].to_dict()
home = pts.loc["06109"].geometry
Ter = build()
GOLD, BLUE = (253, 181, 21), (86, 170, 255)
mx = max(O.max(), I.max())

ARCS = []
for series, color, lean, outward in [(I, BLUE, -28, False), (O, GOLD, 28, True)]:
    for g, n in series.items():
        if g not in pts.index:
            continue
        p = pts.loc[g].geometry
        dist = km(Ter, (home.x, home.y), (p.x, p.y)) * 1e3
        h = 12e3 + 0.05 * dist + 215e3 * (n / mx) ** 0.85
        A, B = ((home.x, home.y), (p.x, p.y)) if outward else ((p.x, p.y), (home.x, home.y))
        ARCS.append(dict(points=arc_points(Ter, A, B, h, lean_deg=lean, n=140), color=color, n=int(n),
                         outward=outward, geoid=g, w=(1.2 + 7.5 * (n / mx) ** 0.6)))
# growth order: biggest flows first, gold and blue interleaved
order = sorted(range(len(ARCS)), key=lambda i: -ARCS[i]["n"])
START = {i: 0.6 + 2.6 * (r / len(order)) for r, i in enumerate(order)}
GROW = 1.5


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def cam_for(f):
    s = f / (N - 1)
    e = 0.5 - 0.5 * math.cos(math.pi * s)                    # ease in/out over the whole film
    bearing = 228 + 100 * e                                   # looking SW -> looking NW, from over the Sierra
    tilt = 34 + 5 * math.sin(math.pi * s)
    dist = 820e3 - 120e3 * e
    return camera(Ter, -120.55, 37.75, bearing, tilt, dist, fov=40, aspect=W / H, exposure=1.75)


LABELS = {"06099": "STANISLAUS", "06009": "CALAVERAS", "06067": "SACRAMENTO", "06001": "ALAMEDA",
          "06085": "SANTA CLARA", "06077": "SAN JOAQUIN", "06037": "LOS ANGELES", "32031": "RENO"}


def frame(f):
    t = f / FPS
    cam = cam_for(f)
    rgba, depth = render(Ter, cam, W, H, quality=a.quality, sun=(255.0, 30.0))
    rgba = sky(rgba, depth)
    arcs = []
    heads = []
    for i, A_ in enumerate(ARCS):
        p = ease((t - START[i]) / GROW)
        if p <= 0:
            continue
        P = A_["points"]
        k = max(2, int(round(p * (len(P) - 1))) + 1)
        seg = P[:k] if A_["outward"] else P[len(P) - k:]
        arcs.append(dict(points=seg, color=A_["color"], width_px=A_["w"] * W / 1600, alpha=0.95))
        if p < 1:
            heads.append((seg[-1] if A_["outward"] else seg[0], A_["color"], A_["w"]))
        else:
            end = P[-1] if A_["outward"] else P[0]
            heads.append((end, A_["color"], 1.2 + 0.4 * A_["w"]))
    img = draw_arcs(rgba, arcs, cam, depth) if arcs else Image.fromarray(rgba).convert("RGBA")
    for pnt, col, r in heads:
        px, py, _, vis = visible_mask(pnt[None], cam, W, H, depth)
        if vis[0]:
            img = dot(img, (px[0], py[0]), r * 0.9 * W / 1600, col)
    hx, hz = Ter.world_xz(home.x, home.y)
    hp = np.array([[hx, float(Ter.ground_y(hx, hz)), hz]])
    hpx, hpy, _, _ = project(hp, cam, W, H)
    img = dot(img, (hpx[0], hpy[0]), 7 * W / 1600, (255, 255, 255))

    d = ImageDraw.Draw(img, "RGBA")
    k = W / 1600
    # county labels fade in once the arcs are up
    la = ease((t - 4.6) / 1.0)
    if la > 0:
        fm = font("DMMono-Regular", 13 * k); fs = font("DMMono-Regular", 11.5 * k)
        for g, nm in LABELS.items():
            p = pts.loc[g].geometry
            x, z = Ter.world_xz(p.x, p.y)
            px, py, _, vis = visible_mask(np.array([[x, float(Ter.ground_y(x, z)), z]]), cam, W, H, depth)
            if not (vis[0] and 30 < px[0] < W - 160 * k and 30 < py[0] < H - 30):
                continue
            al = int(255 * la)
            text_halo(d, (px[0] + 10 * k, py[0] - 8 * k), nm, fm, (240, 236, 226, al), halo=(8, 18, 36, al), w=int(3 * k), anchor="lm")
            o, i_ = int(O.get(g, 0)), int(I.get(g, 0))
            X2 = px[0] + 10 * k
            for s_, col in [x for x in ((f"out {o:,}", GOLD, o), (f"in {i_:,}", BLUE, i_)) if x[2]] and [(x[0], x[1]) for x in ((f"out {o:,}", GOLD, o), (f"in {i_:,}", BLUE, i_)) if x[2]]:
                text_halo(d, (X2, py[0] + 9 * k), s_, fs, col + (al,), halo=(8, 18, 36, al), w=int(3 * k), anchor="lm")
                X2 += d.textlength(s_, font=fs) + 10 * k
        text_halo(d, (hpx[0] + 14 * k, hpy[0] - 6 * k), "SONORA", font("DMMono-Medium", 15 * k),
                  (255, 255, 255, int(255 * la)), halo=(8, 18, 36, int(255 * la)), w=int(3 * k))
    # opening title, then a quiet legend
    ta = ease(t / 0.8) * (1 - ease((t - 4.0) / 1.0))
    if ta > 0:
        al = int(255 * ta)
        ft = font("PlayfairDisplay-Black", 50 * k)
        text_halo(d, (52 * k, 52 * k), "Where Tuolumne County", ft, (255, 255, 255, al), w=0)
        text_halo(d, (52 * k, 112 * k), "comes and goes", ft, GOLD + (al,), w=0)
        text_halo(d, (52 * k, 186 * k), f"People moving in and out, five years of IRS data ({yrs[0][:4]}–{yrs[-1][-4:]})",
                  font("LibreBaskerville-Regular", 17 * k), (226, 230, 238, al), w=0)
    lg = ease((t - 3.8) / 1.0)
    if lg > 0:
        al = int(255 * lg); x0, y0 = 46 * k, H - 96 * k
        for col, txt in ((GOLD, "Moving out of Tuolumne County"), (BLUE, "Moving into Tuolumne County")):
            d.line([(x0, y0 + 9 * k), (x0 + 42 * k, y0 + 9 * k)], fill=col + (al,), width=max(2, int(5 * k)))
            text_halo(d, (x0 + 54 * k, y0), txt, font("DMMono-Regular", 13.5 * k), (240, 236, 226, al), w=0)
            y0 += 26 * k
        d.text((W - 30 * k, H - 26 * k), "Taller arcs = more people · Data: IRS SOI migration · forge3d · brooksgroves.com",
               font=font("DMMono-Regular", 11 * k), fill=(195, 205, 220, al), anchor="rs")
    return img.convert("RGB").resize((OUTW, OUTH), Image.LANCZOS)


if a.still is not None:
    frame(a.still).save(f"still_{a.still:03d}.jpg", quality=92)
else:
    for f in range(a.part, N, a.parts):
        frame(f).save(f"frames/f{f:04d}.jpg", quality=93)
        print("frame", f, flush=True)
