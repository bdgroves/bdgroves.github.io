"""Shared scene build: terrain, albedo, camera helper, terrain render with depth."""
import math, time, numpy as np, geopandas as gpd, forge3d as f
from scene import Terrain
import colors

BBOX = (-125.6, 31.4, -112.6, 43.0)


def build(exag=6.0, step=2, pad=(260, 220)):
    T = Terrain("data/dem_ca_z8.npz", BBOX, step=step, exag=exag, pad=pad)
    cols = np.arange(T.W); rows = np.arange(T.H)
    mx = T.left + (cols + 0.5) * T.px; my = T.top - (rows + 0.5) * T.px
    lon = np.degrees(mx / 6378137.0)[None, :].repeat(T.H, 0)
    lat = np.degrees(2 * np.arctan(np.exp(my / 6378137.0)) - np.pi / 2)[:, None].repeat(T.W, 1)
    st = gpd.read_file("data/counties.gpkg", layer="states")
    in_ca = T.grid_pixels(st[st.STUSPS == "CA"].geometry)
    alb = colors.albedo(T, lon, lat, in_ca)
    T.alb = np.concatenate([alb, np.ones(alb.shape[:2] + (1,), np.float32)], axis=-1)
    T.in_ca = in_ca
    return T


def camera(T, lon, lat, bearing_deg, tilt_deg, dist_m, fov=34.0, aspect=1.6, exposure=1.7):
    """Camera looking at (lon,lat) along compass bearing, tilt = degrees below horizontal."""
    tx, tz = T.world_xz(lon, lat)
    b, t = math.radians(bearing_deg), math.radians(tilt_deg)
    # world: +x east, +z south; view direction horizontal component points along bearing
    dx, dz = math.sin(b), -math.cos(b)
    ox = tx - dx * dist_m * math.cos(t); oz = tz - dz * dist_m * math.cos(t); oy = dist_m * math.sin(t)
    return {"origin": (ox, oy, oz), "look_at": (tx, 0.0, tz), "up": (0, 1, 0), "fov_y": fov,
            "aspect": aspect, "exposure": exposure}


def render(T, cam, W, H, quality="draft", sun=(250.0, 30.0)):
    kw = dict(spacing=(T.px, T.px), exaggeration=1.0, albedo_map=T.alb, albedo_sampling="bilinear",
              sun_azimuth_deg=sun[0], sun_elevation_deg=sun[1], sun_intensity=3.2, env_intensity=0.5)
    if quality == "draft":
        kw.update(min_frames=8, max_frames=32, variance_threshold=1.0)
    elif quality == "film":
        kw.update(min_frames=20, max_frames=64, variance_threshold=0.15)
    else:
        kw.update(min_frames=32, max_frames=160, variance_threshold=0.02)
    t = time.time()
    rgba = f.render_terrain_poster(T.height, W, H, cam, tile=512, **kw)["rgba"]
    d = f.hybrid_render_terrain_reference(T.height, W // 2, H // 2, cam, spacing=(T.px, T.px),
                                          exaggeration=1.0, min_frames=1, max_frames=32,
                                          variance_threshold=10.0)["depth"]
    print(f"render {W}x{H} {quality}: {time.time() - t:.0f}s", flush=True)
    return rgba, d
