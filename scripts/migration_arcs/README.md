# Tuolumne County migration arcs (forge3d)

Two posters of people moving out of and into Tuolumne County, CA, drawn as 3D arcs over
forge3d path-traced terrain. Arc height and thickness grow with the number of people, so
big nearby flows tower and small distant ones stay low.

- `ca_map.py` — California close-up, IRS SOI county-to-county flows, 2018-19 to 2022-23
  (gold = leaving, blue = arriving; flows under 20 returns a year are suppressed by the IRS).
- `us_map.py` — lower 48, Census ACS 2016-2020 county-to-county flows, everyone leaving
  (every destination, with wide survey margins on the small ones).

Data: run the **Fetch migration map data** workflow; it pushes everything to the
`migration-data` branch. Clone that branch into `data/` next to these scripts, and put the
house fonts (Playfair Display, Libre Baskerville, DM Mono) where `poster.py` looks.

How it renders: forge3d's `render_terrain_poster` path-traces the terrain (tiled, to stay
under its 512 MB budget) and `hybrid_render_terrain_reference` gives a half-size depth map.
`camproj.project` reproduces forge3d's pinhole camera exactly, so the arcs are drawn in 2D
on top and hidden wherever the depth map says a mountain is in front.

    python ca_map.py draft            # fast 960x600 check
    python ca_map.py final --rerender # 2400x1500
    CAM="-107.5,36.5,68,36,5100e3,34" python us_map.py final --rerender
