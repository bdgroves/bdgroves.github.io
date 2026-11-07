"""3D arcs over the forge3d terrain, projected with the same pinhole camera and
hidden where the terrain's depth says a mountain is in front."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from camproj import project


def arc_points(T, a_lonlat, b_lonlat, height_m, lean_deg=0.0, n=120):
    ax, az = T.world_xz(*a_lonlat); bx, bz = T.world_xz(*b_lonlat)
    ay = float(T.ground_y(ax, az)); by = float(T.ground_y(bx, bz))
    s = np.linspace(0, 1, n)
    x = ax + (bx - ax) * s; z = az + (bz - az) * s; y = ay + (by - ay) * s
    bump = 4 * s * (1 - s)
    # lean the arc plane sideways (so out- and in-arcs between the same pair separate)
    d = np.array([bx - ax, bz - az]); d /= (np.linalg.norm(d) + 1e-9)
    side = np.array([-d[1], d[0]])
    L = np.radians(lean_deg)
    y = y + height_m * bump * np.cos(L)
    x = x + side[0] * height_m * bump * np.sin(L)
    z = z + side[1] * height_m * bump * np.sin(L)
    return np.stack([x, y, z], 1)


def visible_mask(P, cam, W, H, depth):
    px, py, zc, dist = project(P, cam, W, H)
    dh, dw = depth.shape
    ix = np.clip((px * dw / W).astype(int), 0, dw - 1); iy = np.clip((py * dh / H).astype(int), 0, dh - 1)
    inside = (px >= -50) & (px < W + 50) & (py >= -50) & (py < H + 50) & (zc > 0)
    dt = depth[iy, ix]
    vis = inside & (~np.isfinite(dt) | (dist < dt * 1.003 + 2000))
    return px, py, dist, vis


def draw_arcs(base_rgba, arcs, cam, depth, ss=2, glow=True):
    """arcs: list of dict(points, color(rgb 0-255), width_px, alpha)."""
    H, W = base_rgba.shape[:2]
    layer = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    order = []
    for a in arcs:
        px, py, dist, vis = visible_mask(a["points"], cam, W, H, depth)
        order.append((np.nanmean(dist), a, px, py, vis))
    for _, a, px, py, vis in sorted(order, key=lambda t: -t[0]):
        w = max(1, int(round(a["width_px"] * ss)))
        col = tuple(a["color"]) + (int(255 * a.get("alpha", 0.95)),)
        n = len(px)
        # taper: thin at the ends, full in the middle
        for i in range(n - 1):
            if not (vis[i] and vis[i + 1]):
                continue
            t = i / (n - 1)
            ww = max(1, int(round(w * (0.45 + 0.55 * np.sin(np.pi * t)))))
            dr.line([(px[i] * ss, py[i] * ss), (px[i + 1] * ss, py[i + 1] * ss)], fill=col, width=ww)
    layer = layer.resize((W, H), Image.LANCZOS)
    base = Image.fromarray(base_rgba).convert("RGBA")
    if glow:
        g = layer.filter(ImageFilter.GaussianBlur(7))
        g2 = layer.filter(ImageFilter.GaussianBlur(2.5))
        base = Image.alpha_composite(base, _scale_alpha(g, 0.85))
        base = Image.alpha_composite(base, _scale_alpha(g2, 0.7))
    return Image.alpha_composite(base, layer)


def _scale_alpha(im, k):
    a = np.asarray(im).copy()
    a[..., 3] = np.clip(a[..., 3] * k, 0, 255).astype(np.uint8)
    return Image.fromarray(a)


def dot(img, xy, r, color, glow=True):
    r = float(r); xy = (float(xy[0]), float(xy[1]))
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x, y = xy
    d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(color) + (255,))
    if glow:
        img = Image.alpha_composite(img, _scale_alpha(lay.filter(ImageFilter.GaussianBlur(r * 1.6)), 0.9))
    return Image.alpha_composite(img, lay)
