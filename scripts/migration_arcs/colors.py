"""California-flavoured albedo for the terrain (linear RGB)."""
import numpy as np


def srgb(h):
    h = h.lstrip("#"); c = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# elevation ramps (metres)
WET = [(0, "#8f9b62"), (120, "#a9a35a"), (350, "#c9a24e"), (900, "#b8924a"),
       (1300, "#5e7442"), (2300, "#4a6339"), (2800, "#9c978c"), (3500, "#c9c5bc"), (4300, "#e8e6e0")]
DRY = [(-100, "#cdb48a"), (600, "#c6aa7e"), (1400, "#b39a73"), (2200, "#8f8370"),
       (2900, "#a29d92"), (3600, "#d4d0c8")]
OCEAN_DEEP, OCEAN_SHALLOW = srgb("#123d66"), srgb("#2f6c99")

# Sierra/Cascade crest, roughly: east of this line inside California is rain shadow / desert
CREST = np.array([(-117.0, 32.5), (-116.6, 33.4), (-116.9, 34.0), (-117.6, 34.3), (-118.2, 34.7),
                  (-118.4, 35.4), (-118.2, 35.9), (-118.3, 36.4), (-118.9, 37.6), (-119.6, 38.3),
                  (-120.1, 39.0), (-120.3, 40.0), (-121.3, 41.0), (-121.6, 42.1)])


def ramp(elev, stops):
    xs = np.array([s[0] for s in stops], float)
    cs = np.stack([srgb(s[1]) for s in stops])
    out = np.empty(elev.shape + (3,), np.float32)
    for k in range(3):
        out[..., k] = np.interp(elev, xs, cs[:, k])
    return out


def albedo(terrain, lon, lat, in_ca):
    e = terrain.raw
    crest_lon = np.interp(lat, CREST[:, 1], CREST[:, 0])
    dry = (lon > crest_lon) | ~in_ca
    a = np.where(dry[..., None], ramp(e, DRY), ramp(e, WET))
    # neighbours: dimmer and greyer so California reads first
    g = a.mean(axis=-1, keepdims=True)
    nb = (0.55 * a + 0.45 * g) * 0.62
    a = np.where(in_ca[..., None], a, nb)
    depth = np.clip(-e / 3000.0, 0, 1)[..., None]
    sea = OCEAN_SHALLOW * (1 - depth) + OCEAN_DEEP * depth
    a = np.where(terrain.ocean[..., None], sea, a)
    return a.astype(np.float32)


HUMID = [(0, "#7e8f5c"), (300, "#728552"), (800, "#66784a"), (1500, "#8a8a6e"), (2500, "#9d988c"), (3500, "#c8c4ba")]


def albedo_us(terrain, lon, lat, in_ca, in_us):
    """California bright; rest of the US muted natural colours; Canada and Mexico darker."""
    e = terrain.raw
    crest_lon = np.interp(lat, CREST[:, 1], CREST[:, 0])
    ca = np.where((lon > crest_lon)[..., None], ramp(e, DRY), ramp(e, WET))
    west = ramp(e, DRY); east = ramp(e, HUMID)
    wgt = np.clip((lon + 103.0) / 8.0, 0, 1)[..., None]       # blend dry west -> humid east around 100W
    us = west * (1 - wgt) + east * wgt
    g = us.mean(axis=-1, keepdims=True)
    us = (0.7 * us + 0.3 * g) * 0.78
    other = (0.45 * us + 0.55 * g) * 0.55
    a = np.where(in_ca[..., None], ca, np.where(in_us[..., None], us, other))
    depth = np.clip(-e / 3000.0, 0, 1)[..., None]
    sea = OCEAN_SHALLOW * (1 - depth) + OCEAN_DEEP * depth
    a = np.where(terrain.ocean[..., None], sea, a)
    return a.astype(np.float32)
