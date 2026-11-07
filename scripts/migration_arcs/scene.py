"""Terrain scene for the Tuolumne migration arcs (forge3d path tracer + my own arc overlay)."""
import math
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from rasterio_free_raster import rasterize_polys

R = 6378137.0


def lonlat_to_3857(lon, lat):
    x = np.radians(lon) * R
    y = R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return x, y


class Terrain:
    def __init__(self, npz, bbox, step=2, exag=6.0, pad=(0, 0)):
        z = np.load(npz)
        e = z["elev"]; L, B, Rr, T = z["bounds_3857"]
        h, w = e.shape
        px = (Rr - L) / w
        x0, y0 = lonlat_to_3857(bbox[0], bbox[3]); x1, y1 = lonlat_to_3857(bbox[2], bbox[1])
        c0, c1 = int((x0 - L) / px), int((x1 - L) / px)
        r0, r1 = int((T - y0) / px), int((T - y1) / px)
        e = e[r0:r1:step, c0:c1:step].astype(np.float32)
        # pad open ocean to the west and south so the frame never shows the grid edge
        pw, ps = pad
        e = np.pad(e, ((0, ps), (pw, 0)), mode="constant", constant_values=-3500.0)
        self.raw = e.copy()
        self.ocean = e <= 0
        e[self.ocean] = 0
        self.elev = e
        self.H, self.W = e.shape
        self.px = px * step                     # metres (web mercator) per grid cell
        self.left = L + c0 * px - pad[0] * px * step; self.top = T - r0 * px
        self.exag = exag
        self.height = e * exag                  # world Y (metres x exaggeration)

    # lon/lat -> world (x, z) ; world origin = grid centre
    def world_xz(self, lon, lat):
        mx, my = lonlat_to_3857(np.asarray(lon, float), np.asarray(lat, float))
        col = (mx - self.left) / self.px
        row = (self.top - my) / self.px
        return (col - self.W / 2) * self.px, (row - self.H / 2) * self.px

    def ground_y(self, x, z):
        col = np.clip((np.asarray(x) / self.px + self.W / 2).astype(int), 0, self.W - 1)
        row = np.clip((np.asarray(z) / self.px + self.H / 2).astype(int), 0, self.H - 1)
        return self.height[row, col]

    def grid_pixels(self, geoms_lonlat):
        """Rasterize lon/lat polygons onto the grid (bool mask)."""
        def to_grid(lon, lat):
            mx, my = lonlat_to_3857(np.asarray(lon), np.asarray(lat))
            return (mx - self.left) / self.px, (self.top - my) / self.px
        return rasterize_polys(geoms_lonlat, to_grid, self.H, self.W)
