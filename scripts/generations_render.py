"""Largest generation per census tract — Seattle metro and Tuolumne County.
Styled after a newsroom dot map from "The Twin Cities in 50 Maps" (dark navy, centroid dots sized by
the population of the largest generation). Data: ACS 2020-2024 5-year B01001.

Run from a folder holding data/seattle.gpkg and data/tuolumne.gpkg
(from the generations-data branch, made by scripts/generations_data.py).
"""
import sys
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
import numpy as np

plt.rcParams["font.family"] = "DejaVu Sans"
GENS = ["alpha", "genz", "millennials", "genx", "boomers", "silent"]
LABEL = {
    "alpha": ("Generation Alpha", "Born 2010–2024"),
    "genz": ("Generation Z", "Born 1995–2009"),
    "millennials": ("Millennials", "Born 1980–1994"),
    "genx": ("Generation X", "Born 1965–1979"),
    "boomers": ("Baby Boomers", "Born 1945–1964"),
    "silent": ("Silent Generation", "Born 1944 or earlier"),
}
COLOR = {"alpha": "#f2552c", "genz": "#f5e23b", "millennials": "#8cc63f",
         "genx": "#13a58c", "boomers": "#b9478f", "silent": "#ffffff"}
BG, LAND, LAND_OUT, WATER = "#16263a", "#1b2c42", "#172739", "#13304a"
ROAD, TEXT, SUB = "#2c4058", "#ffffff", "#c9d3df"
SIZE_PER_PERSON = 0.11          # marker area (pt^2) per person — same on both maps
LEGEND_SIZES = [500, 1500, 3000, 4500]


def load(name, crs):
    p = f"data/{name}.gpkg"
    L = {l: gpd.read_file(p, layer=l).to_crs(crs)
         for l in ["tracts", "land", "water", "roads", "cities", "places"]}
    t = L["tracts"]
    t = t[t.total > 0].copy()
    t["top"] = t[GENS].idxmax(axis=1)
    t["n"] = t[GENS].max(axis=1)
    L["tracts"] = t
    return L


def draw(name, crs, extent, metro_counties, labels, outlines, title, subtitle, note,
         water_labels, size, legend_w, out, source_extra="", footer_in_map=False, callouts=()):
    L = load(name, crs)
    W, H = size
    fig = plt.figure(figsize=(W, H), dpi=150, facecolor=BG)
    lw = legend_w / W
    ax = fig.add_axes([lw, 0, 1 - lw, 1])
    ax.set_facecolor(WATER)
    x0, y0, x1, y1 = extent
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")

    land = L["land"]
    inmetro = land.GEOID.str[2:].isin(metro_counties) & land.GEOID.str[:2].eq(L["tracts"].GEOID.iloc[0][:2])
    land[~inmetro].plot(ax=ax, color=LAND_OUT, lw=0, zorder=1)
    land[inmetro].plot(ax=ax, color=LAND, lw=0, zorder=1)
    w = L["water"]
    w[w.AWATER > 60000].plot(ax=ax, color=WATER, lw=0, zorder=2)
    r = L["roads"]
    r[r.MTFCC == "S1400"].plot(ax=ax, color=ROAD, lw=0.18, alpha=0.55, zorder=3)
    r[r.MTFCC.isin(["S1200", "S1630", "S1640"])].plot(ax=ax, color=ROAD, lw=0.5, alpha=0.9, zorder=3)
    r[r.MTFCC == "S1100"].plot(ax=ax, color="#3a5272", lw=1.0, zorder=3)
    # county line between metro and the rest (subtle)
    land.boundary.plot(ax=ax, color="#2a3d55", lw=0.6, zorder=3)

    land[inmetro].boundary.plot(ax=ax, color="#5b7393", lw=0.8, zorder=4)
    c = L["cities"]
    c[c.NAME.isin(outlines)].boundary.plot(ax=ax, color="#e8eef5", lw=0.9, alpha=0.9, zorder=4)

    t = L["tracts"].sort_values("n", ascending=False)
    ax.scatter(t.geometry.x, t.geometry.y, s=t.n * SIZE_PER_PERSON, c=t.top.map(COLOR),
               lw=0, alpha=0.95, zorder=5)

    halo = [pe.withStroke(linewidth=3, foreground=BG)]
    P = L["places"].drop_duplicates("NAME").set_index("NAME")
    for lab in labels:
        nm, dx, dy = (lab + (0, 0))[:3] if isinstance(lab, tuple) else (lab, 0, 0)
        if nm not in P.index:
            print("missing label", nm); continue
        g = P.loc[nm].geometry
        ax.text(g.x + dx, g.y + dy, nm.upper().replace("-", "‑"), color=TEXT, fontsize=8.6,
                ha="center", va="center", weight="medium", zorder=6, path_effects=halo,
                linespacing=0.95)
    T = L["tracts"].set_index("GEOID")
    for geoid, txt, dx, dy in callouts:
        g = T.loc[geoid].geometry
        ax.annotate(txt, (g.x, g.y), (g.x + dx, g.y + dy), color=SUB, fontsize=8.6, style="italic",
                    ha="center", va="center", zorder=7, path_effects=halo,
                    arrowprops=dict(arrowstyle="-", color=SUB, lw=0.6, shrinkB=6))
    for txt, x, y, rot in water_labels:
        ax.text(x, y, txt, color="#6f8fb0", fontsize=8.4, style="italic", ha="center",
                va="center", rotation=rot, zorder=6)

    # ---- legend panel (laid out in inches from the top) ----
    lg = fig.add_axes([0, 0, lw, 1]); lg.set_xlim(0, legend_w); lg.set_ylim(0, H); lg.axis("off")
    px = 0.55
    y = H - 0.6
    lg.text(px, y, title, color=TEXT, fontsize=20, weight="bold", va="top", linespacing=1.15)
    y -= 0.36 * (title.count("\n") + 1) + 0.25
    lg.text(px, y, subtitle, color=SUB, fontsize=10.5, va="top", linespacing=1.45)
    y -= 0.22 * (subtitle.count("\n") + 1) + 0.55
    lg.text(px, y, "LARGEST GENERATION\nIN CENSUS TRACT", color=TEXT, fontsize=11.5, va="top",
            linespacing=1.25, weight="medium")
    y -= 0.75
    counts = L["tracts"].top.value_counts()
    for g in GENS:
        lg.scatter([px + 0.16], [y - 0.14], s=230, color=COLOR[g], lw=0)
        nm, born = LABEL[g]
        k = counts.get(g, 0)
        lg.text(px + 0.48, y - 0.02, nm, color=TEXT, fontsize=11.5, va="center")
        lg.text(px + 0.48, y - 0.27, f"{born}  ·  {k} tract{'s' if k != 1 else ''}", color=SUB,
                fontsize=9.6, va="center")
        y -= 0.62
    y -= 0.25
    lg.text(px, y, "POPULATION OF\nLARGEST GENERATION", color=TEXT, fontsize=11.5, va="top",
            linespacing=1.25, weight="medium")
    y -= 0.75
    # size key: circles side by side on one baseline, value under each
    cx = px + 0.1
    base = y - 0.35
    for v in LEGEND_SIZES:
        d_in = np.sqrt(v * SIZE_PER_PERSON) / 72
        lg.scatter([cx + d_in / 2], [base + d_in / 2], s=v * SIZE_PER_PERSON, facecolor="none",
                   edgecolor="#e8eef5", lw=0.9)
        lg.text(cx + d_in / 2, base - 0.16, f"{v:,}", color=TEXT, fontsize=9.5, ha="center", va="top")
        cx += max(d_in, 0.25) + 0.42
    y = base - 0.6
    lg.text(px, y, note, color=SUB, fontsize=9, style="italic", va="top", linespacing=1.45)
    fx, fy, fax, fha = (px, 0.35, lg, "left") if not footer_in_map else (0.985, 0.02, ax, "right")
    if footer_in_map:
        fx, fy = x1 - (x1 - x0) * 0.012, y0 + (y1 - y0) * 0.02
    fax.text(fx, fy, "Data: US Census Bureau, ACS 2020–2024 5-year (table B01001),\n"
            "TIGER/Line 2024. Dots sit at each tract's internal point." + source_extra +
            "\nMap: Brooks Groves · brooksgroves.com · #30DayMapChallenge Day 1: Points",
            color="#8796a8", fontsize=7.6, va="bottom", ha=fha, linespacing=1.5, zorder=7)
    fig.savefig(out, facecolor=BG, dpi=150)
    print("wrote", out, dict(counts))


if __name__ == "__main__":
    which = sys.argv[1:] or ["seattle", "tuolumne"]
    NOTE = ("Generation age ranges follow the US Census\nBureau's age groups for the ACS 2020–2024\n"
            "estimates and differ slightly from other\ncommonly cited definitions.")
    if "seattle" in which:
        draw("seattle", 32610, (513000, 5198000, 600000, 5342000), ["033", "053", "061"],
             ["Everett", "Marysville", "Lake Stevens", "Mukilteo", "Mill Creek", "Lynnwood",
              "Edmonds", "Shoreline", ("Bothell", 0, 1200), "Kirkland", "Redmond", "Woodinville",
              "Sammamish", "Issaquah", "Bellevue", ("Seattle", -4500, 0), "Burien", "Renton",
              "SeaTac", "Kent", "Maple Valley", "Auburn", "Federal Way",
              ("Tacoma", -300, 5600), "University Place", "Lakewood", "Puyallup", "Bonney Lake",
              "Spanaway", "Gig Harbor", "Snohomish", "Monroe", "Duvall", "Bremerton",
              "Arlington", "Enumclaw"],
             ["Seattle", "Tacoma"],
             "Who's the biggest\ngeneration in your\nneighborhood?",
             "Seattle–Tacoma–Bellevue metro\n(King, Pierce and Snohomish counties)",
             NOTE,
             [("Puget Sound", 528500, 5272000, 72)],
             (15, 17.2), 4.6, "seattle-generations.png",
             "\nGrey land: counties outside the metro.")
    if "tuolumne" in which:
        draw("tuolumne", 3310, (-64000, -48000, 77000, 52000), ["109"],
             ["Sonora", "Jamestown", "Columbia", "Twain Harte", "Mi-Wuk Village",
              "Tuolumne City", "Soulsbyville", ("Groveland", -2000, -2600), "Chinese Camp",
              "Long Barn", "Tuttletown", "Strawberry", "Pine Mountain Lake", ("Yosemite Valley", 0, 2500),
              "Murphys", "Coulterville", "Buck Meadows"],
             ["Sonora"],
             "Who's the biggest\ngeneration in\nTuolumne County?",
             "Tuolumne County, California\n(18 census tracts)",
             NOTE,
             [("Don Pedro\nReservoir", -33000, -29500, 0), ("New Melones\nLake", -50500, -3000, 0),
              ("Hetch Hetchy", 24000, -5300, 0), ("YOSEMITE NATIONAL PARK", 40000, 2000, 0)],
             (20.1, 11), 4.6, "tuolumne-generations.png", footer_in_map=True,
             callouts=[("06109985202", "Sierra Conservation\nCenter (state prison):\nno kids, almost no one over 60", -7000, -9500)])
