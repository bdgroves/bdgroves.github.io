"""Tiny polygon rasterizer (PIL) so the scene needs no rasterio."""
import numpy as np
from PIL import Image, ImageDraw


def rasterize_polys(geoms, to_grid, H, W, supersample=1):
    im = Image.new("L", (W * supersample, H * supersample), 0)
    d = ImageDraw.Draw(im)
    for g in geoms:
        polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
        for p in polys:
            x, y = to_grid(*np.asarray(p.exterior.coords).T)
            d.polygon(list(zip(x * supersample, y * supersample)), fill=255)
            for hole in p.interiors:
                x, y = to_grid(*np.asarray(hole.coords).T)
                d.polygon(list(zip(x * supersample, y * supersample)), fill=0)
    a = np.asarray(im)
    if supersample > 1:
        a = a.reshape(H, supersample, W, supersample).mean(axis=(1, 3))
    return a > 127


def rasterize_lines(geoms, to_grid, H, W, width=1, supersample=3):
    """Anti-aliased coverage (0-1) of polygon/line boundaries on the grid."""
    im = Image.new("L", (W * supersample, H * supersample), 0)
    d = ImageDraw.Draw(im)
    for g in geoms:
        b = g.boundary if g.geom_type in ("Polygon", "MultiPolygon") else g
        parts = [b] if b.geom_type == "LineString" else list(getattr(b, "geoms", [b]))
        for ln in parts:
            x, y = to_grid(*np.asarray(ln.coords).T)
            d.line(list(zip(x * supersample, y * supersample)), fill=255, width=max(1, int(width * supersample)))
    a = np.asarray(im, dtype=np.float32) / 255.0
    return a.reshape(H, supersample, W, supersample).mean(axis=(1, 3))
