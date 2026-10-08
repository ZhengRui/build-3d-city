"""M4 fix round (builder b-tk-m4f): Tokyo's projecting vertical signs (袖看板) on the sign streets, as [[structures]]
figures written to generated/structures-m4f-signs.toml (city.toml `include`s it; re-run after 04_buildings or after
editing [facade.tokyo] sign_zones, then 06_tiles and 07_pack). Run from demos/tokyo:
`uv run python scripts/m4f_signs.py`.

The critic (M4 round 1): at street level Akihabara read as a generic office town; the facade's flat signboard stacks
foreshorten to strips along a street. Real Chuo-dori, Kabukicho and Center-gai fronts carry vertical sign boxes
standing out ~1 m from the wall, one or two per narrow building, from the first floor nearly to the roof, each in a
brand colour with a column of characters, lit after dark. Here: for each commercial building under 60 m fronting a
zone's streets (presets/jp_tokyo sign_fronts(): the same test as the `signs` style's) on the zone's `boxes` share,
its outline's edge nearest the street, a box at one end of it (both ends on a front over 8 m, two in three): 0.3 m
thick along the wall, 0.8-1.3 m out, from 3-4 m up to 0.3-1.5 m under the roof (a shorter one on one in four); on
both broad faces (seen along the street) a column of glyph blocks in a contrasting ink. Style floodlit (no windows,
its own colours; washed by light after dark at variant 0.93, so they read lit).
"""
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

from city3d import config
from city3d.common import Terrain
from city3d.presets.jp_tokyo import COMMERCE, sign_fronts

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "tokyo"
OUT = HERE / "generated" / "structures-m4f-signs.toml"
UTM = 32654
TO_LL = Transformer.from_crs(UTM, 4326, always_xy=True)
TK = config.get()["facade"]["tokyo"]
ZONES = TK["sign_zones"]
TR = Terrain()
gh = lambda p: float(TR.height_utm([p[0]], [p[1]])[0])
# board colours (sRGB) and the ink on each: white, yellow, red, blue, green, black, pink, orange
BOARDS = [("#ecebe4", ["#b3171c", "#1b1b1f", "#123f8c"]), ("#f0c21b", ["#1b1b1f", "#b3171c"]),
          ("#c0161c", ["#f4f2ea", "#f0c21b"]), ("#173f95", ["#f4f2ea", "#f0c21b"]), ("#13723c", ["#f4f2ea"]),
          ("#1a1a1d", ["#f0c21b", "#f4f2ea", "#e8414b"]), ("#e46a92", ["#f4f2ea"]), ("#ea6b16", ["#f4f2ea", "#1b1b1f"])]
WEIGHT = np.array([0.24, 0.16, 0.16, 0.1, 0.07, 0.13, 0.06, 0.08])

rng = np.random.default_rng(97)
x0 = min(z["box"][0] for z in ZONES) - 0.001
y0 = min(z["box"][1] for z in ZONES) - 0.001
x1 = max(z["box"][2] for z in ZONES) + 0.001
y1 = max(z["box"][3] for z in ZONES) + 0.001
# (the zones lie in two clusters, Shinjuku/Shibuya and Akihabara: read each zone's box, not the hull)
b = pd.concat([gpd.read_file(DATA / "buildings.gpkg", bbox=tuple(z["box"])) for z in ZONES]).drop_duplicates("geometry")
b = b.to_crs(UTM).reset_index(drop=True)
sf = sign_fronts(b)
u = b.usage_name.fillna("").astype(str)
h = b.h.astype(float)
ok = sf.front & (sf.zone >= 0) & (u.isin(COMMERCE) | u.eq("")) & (h >= 8) & (h < 60) & (b.area >= 25)
print(f"fronting commercial pieces: {int(ok.sum()):,} of {len(b):,}")

ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
ways = ways[(ways.kind != "rail") & ~ways.elevated.fillna(False).astype(bool)]


def f(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


blocks, n_signs, n_tri = [], 0, 0
for i in b.index[ok]:
    z = ZONES[int(sf.zone[i])]
    if rng.random() > z.get("boxes", 0.7):
        continue
    g = max(getattr(b.geometry[i], "geoms", [b.geometry[i]]), key=lambda q: q.area)
    pts = np.array(g.exterior.coords)
    cen = np.array(g.centroid.coords[0])
    near = ways.cx[cen[0] - 60:cen[0] + 60, cen[1] - 60:cen[1] + 60]
    if not len(near):
        continue
    road = near.geometry.union_all()
    # the street edge: of the edges over 3 m, the one whose middle lies nearest a street
    best = None
    for a, c in zip(pts[:-1], pts[1:]):
        L = float(np.hypot(*(c - a)))
        if L < 3.0:
            continue
        m = (a + c) / 2
        d = road.distance(gpd.points_from_xy([m[0]], [m[1]])[0])
        if best is None or d < best[0]:
            best = (d, a, c, L)
    if best is None or best[0] > 25:
        continue
    _, a, c, L = best
    t = (c - a) / L
    nrm = np.array([t[1], -t[0]])
    if (((a + c) / 2 + nrm) - cen) @ nrm < 0:
        nrm = -nrm
    lo = min(gh(q) for q in pts)
    H = float(h[i])
    ends = [0.55] if L <= 8 or rng.random() < 0.35 else [0.55, L - 0.55]
    if rng.random() < 0.5:
        ends = [L - e for e in ends]
    for e in ends:
        at = a + t * e
        facing = math.degrees(math.atan2(nrm[0], nrm[1])) % 360
        base = round(lo - gh(at), 2)
        k = int(rng.choice(len(BOARDS), p=WEIGHT / WEIGHT.sum()))
        board, inks = BOARDS[k]
        ink = inks[int(rng.integers(len(inks)))]
        depth = float(rng.uniform(0.8, 1.3))
        ylo = float(rng.uniform(3.0, 4.2))
        yhi = H - float(rng.uniform(0.3, 1.5))
        if rng.random() < 0.25:
            yhi = min(yhi, ylo + float(rng.uniform(4.0, 9.0)))
        if yhi - ylo < 2.5:
            continue
        zc = depth / 2 + 0.08
        boxes = [[0.0, (ylo + yhi) / 2, zc, 0.3, yhi - ylo, depth, board]]
        # a glyph column on both broad faces (one box through the board, standing 0.04 m proud of each face)
        pitch = float(rng.uniform(0.95, 1.25))
        gw = min(0.62, depth * 0.62)
        yy = ylo + 0.45
        while yy + 0.75 < yhi - 0.3:
            if rng.random() < 0.88:
                boxes.append([0.0, yy + 0.37, zc, 0.38, 0.74, gw, ink])
            yy += pitch
        top = yhi
        lon, lat = TO_LL.transform(*at)
        blocks.append("\n".join([
            "[[structures]]", 'kind = "figure"', f'name = "sign {n_signs + 1} ({z["name"]})"',
            f"at = [{lon:.7f}, {lat:.7f}]", f"facing = {facing:.1f}", 'style = "floodlit"', "variant = 0.93",
            f'colour = "{board}"', f"top = {f(top)}", *( [f"base = {f(base)}"] if abs(base) > 0.01 else [] ),
            "boxes = [" + ", ".join("[" + ", ".join(f(v) if not isinstance(v, str) else f'"{v}"' for v in bx) + "]" for bx in boxes) + "]"]) + "\n")
        n_signs += 1
        n_tri += 12 * len(boxes)

OUT.write_text("# generated by scripts/m4f_signs.py (edit the script or [facade.tokyo] sign_zones, not this file): Tokyo's\n"
               "# projecting vertical signs on the sign streets (M4 fix round)\n\n" + "\n".join(blocks))
print(f"{OUT}: {n_signs} signs, ~{n_tri:,} triangles")
