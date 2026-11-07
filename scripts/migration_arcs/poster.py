"""Poster finishing: dusk sky, labels, title and legend (house fonts)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from camproj import project
from arcs import visible_mask

FONTS = "/home/claude/30daymapchallenge/2026/toolkit/fonts/"
def font(name, size):
    import glob
    cand = sorted(glob.glob(FONTS + name + "*.ttf"))
    return ImageFont.truetype(cand[0], int(size))

NAVY_TOP, NAVY_BOT = np.array([10, 22, 44]), np.array([38, 58, 92])


def km(T, a, b):
    from math import radians, sin, cos, asin, sqrt
    lon1, lat1, lon2, lat2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def sky(rgba, depth):
    H, W = rgba.shape[:2]
    rgb = rgba[..., :3].astype(int)
    bg = rgb[1, 1]
    flat = (np.abs(rgb - bg).max(-1) <= 1)
    dn = np.isnan(depth)
    dn_up = np.array(Image.fromarray(dn.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0
    m = flat & dn_up
    m = np.array(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    t = np.linspace(0, 1, H)[:, None, None]
    grad = NAVY_TOP * (1 - t) + NAVY_BOT * t
    out = rgb * (1 - m[..., None]) + grad * m[..., None]
    return np.dstack([out.clip(0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])


def text_halo(d, xy, s, f, fill, halo=(8, 18, 36), w=3, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=w, stroke_fill=halo)


EDGE = {"04013": "PHOENIX, AZ"}

LABELS = {  # geoid: (short name, dx, dy) offsets in units of W/1600 px
    "06099": ("STANISLAUS", 0, 6), "06009": ("CALAVERAS", 0, -4), "06067": ("SACRAMENTO", 0, -6),
    "06037": ("LOS ANGELES", 0, 0), "32031": ("WASHOE (RENO)", 0, 0), "06073": ("SAN DIEGO", 0, 0),
}


def labels_and_title(img, arcs, cam, depth, Ter, pts, home, O, I, W, H, GOLD, BLUE, yrs):
    k = W / 1600
    d = ImageDraw.Draw(img)
    fm = font("DMMono-Regular", 13 * k); fm_s = font("DMMono-Regular", 11.5 * k)
    hx, hz = Ter.world_xz(home.x, home.y)
    hpx, hpy, _, _ = project(np.array([[hx, float(Ter.ground_y(hx, hz)), hz]]), cam, W, H)
    for g, (name, ox, oy) in LABELS.items():
        if g not in pts.index:
            continue
        p = pts.loc[g].geometry
        x, z = Ter.world_xz(p.x, p.y)
        px, py, _, vis = visible_mask(np.array([[x, float(Ter.ground_y(x, z)), z]]), cam, W, H, depth)
        if not (0 < px[0] < W and 0 < py[0] < H):
            continue
        left = px[0] < hpx[0]
        X = px[0] + (-12 * k if left else 12 * k) + ox * k
        Y = py[0] + oy * k
        anc = "rm" if left else "lm"
        text_halo(d, (X, Y - 8 * k), name, fm, (240, 236, 226), w=int(3 * k), anchor=anc)
        o, i = int(O.get(g, 0)), int(I.get(g, 0))
        segs = []
        if o: segs.append((f"out {o:,}", GOLD))
        if i: segs.append((f"in {i:,}", BLUE))
        widths = [d.textlength(t, font=fm_s) for t, _ in segs]
        total = sum(widths) + 10 * k * (len(segs) - 1)
        X2 = X - total if left else X
        for (t, col), wdt in zip(segs, widths):
            text_halo(d, (X2, Y + 9 * k), t, fm_s, col, w=int(3 * k), anchor="lm")
            X2 += wdt + 10 * k
    # ranked list, upper left over the Pacific
    names = pts["NAME"].to_dict()
    tot = (O.add(I, fill_value=0)).sort_values(ascending=False).head(10)
    x0, y0 = 46 * k, 70 * k
    text_halo(d, (x0, y0), "BIGGEST FLOWS, 5 YEARS", font("DMMono-Medium", 13 * k), (240, 236, 226), w=0)
    yy = y0 + 28 * k
    fl = font("DMMono-Regular", 12.5 * k)
    for g, _ in tot.items():
        nm = names.get(g, g).replace(" County", "")
        st = {"06": "", "32": ", NV", "04": ", AZ"}.get(g[:2], "")
        d.text((x0, yy), (nm + st)[:20], font=fl, fill=(232, 228, 218))
        o, i = int(O.get(g, 0)), int(I.get(g, 0))
        d.text((x0 + 215 * k, yy), f"{o:>5,}", font=fl, fill=GOLD, anchor="ra")
        d.text((x0 + 290 * k, yy), f"{i:>5,}", font=fl, fill=BLUE, anchor="ra")
        yy += 20 * k
    d.text((x0 + 215 * k, y0 + 2 * k), "out", font=font("DMMono-Regular", 11 * k), fill=GOLD, anchor="ra")
    d.text((x0 + 290 * k, y0 + 2 * k), "in", font=font("DMMono-Regular", 11 * k), fill=BLUE, anchor="ra")
    # home label
    px, py = hpx, hpy
    text_halo(d, (px[0] + 14 * k, py[0] - 6 * k), "TUOLUMNE COUNTY", font("DMMono-Medium", 15 * k), (255, 255, 255), w=int(3 * k))
    # title block, lower left over the Pacific
    ft = font("PlayfairDisplay-Black", 46 * k); fs = font("LibreBaskerville-Regular", 16.5 * k)
    x0 = 46 * k
    y0 = H - 330 * k
    text_halo(d, (x0, y0), "Where Tuolumne County", ft, (255, 255, 255), w=0)
    text_halo(d, (x0, y0 + 56 * k), "comes and goes", ft, GOLD, w=0)
    yy = y0 + 128 * k
    for line in ["Every county with at least 20 tax returns a year moving between it",
                 f"and Tuolumne, added up over five years ({yrs[0][:4]}\u2013{yrs[-1][-4:]}). Taller and",
                 "thicker arcs mean more people; small or distant flows stay low."]:
        text_halo(d, (x0, yy), line, fs, (226, 230, 238), w=0); yy += 24 * k
    yy += 14 * k
    for col, txt in [(GOLD, "Moving out of Tuolumne County"), (BLUE, "Moving into Tuolumne County")]:
        d.line([(x0, yy + 9 * k), (x0 + 46 * k, yy + 9 * k)], fill=col, width=max(2, int(5 * k)))
        text_halo(d, (x0 + 58 * k, yy), txt, font("DMMono-Regular", 13.5 * k), (240, 236, 226), w=0)
        yy += 26 * k
    fo = font("DMMono-Regular", 10 * k)
    yy += 10 * k
    for line in [f"Data: IRS Statistics of Income county-to-county migration, people on returns, {yrs[0]} to {yrs[-1]}.",
                 "Terrain: AWS Terrain Tiles, 6\u00d7 vertical. Rendered with forge3d. Brooks Groves \u00b7 brooksgroves.com"]:
        d.text((x0, yy), line, font=fo, fill=(185, 196, 212)); yy += 15 * k
    # arcs that leave the frame: a small label at the edge
    for a in arcs:
        if a["geoid"] not in EDGE:
            continue
        px, py, _, vis = visible_mask(a["points"], cam, W, H, depth)
        inside = (px > 0) & (px < W) & (py > 0) & (py < H) & vis
        if inside.all() or not inside.any():
            continue
        idx = np.where(inside)[0]
        j = idx[-1] if a["color"] == GOLD else idx[0]
        X, Y = min(px[j], W - 10 * k), py[j]
        txt = EDGE[a["geoid"]] + f"  {'out' if a['color'] == GOLD else 'in'} {a['n']:,}"
        text_halo(d, (X - 6 * k, Y - 14 * k), txt, fm_s, a["color"], w=int(3 * k), anchor="rs")
    return img
