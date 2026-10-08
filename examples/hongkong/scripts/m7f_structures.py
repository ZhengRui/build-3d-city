"""M7 fix round 1 (builder b-hk-m7f): the Lantau Link's bridges beyond the tiles' extent, as [[structures]] figures
written to generated/structures-m7f.toml (city.toml `include`s it; re-run after editing the numbers here, then 06_tiles,
07_pack and 07b_blocks). Run from demos/hongkong: `uv run python scripts/m7f_structures.py`.

The critic (M7 round 1): Tsing Ma Bridge missing from the views west over Tsing Yi; it stands ~1 km beyond the ground
area, where no roads are drawn, so the deck is the figure's too (as Stonecutters Bridge's, scripts/m4l_structures.py).
Axes and lengths from OSM's man_made=bridge outlines (the local Overpass, 7 Oct 2026: Tsing Ma w635348630, 2,184 m;
Kap Shui Mun w635348629); spans and heights from the published figures (Wikipedia, Highways Department):

  Tsing Ma (1997)   suspension, main span 1,377 m between two 206 m concrete portal towers (two legs, four cross beams),
                    Ma Wan side span 355 m (on piers), Tsing Yi side span 300 m (hung), main cables 1.1 m, 36 m apart,
                    a double-deck stiffening girder 41 m wide and 7.3 m deep, 62 m clearance
  Kap Shui Mun (1997)  cable-stayed, main span 430 m between two H-shaped towers (~150 m est.), double deck, ~35 m
                    wide, ~47 m clearance; side spans on piers

Leg sizes, beam heights, the cables' sag and the anchorage blocks are estimates (est.).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
OUT = HERE / "generated" / "structures-m7f.toml"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "hongkong" / "raw" / "osm_lantau_link.json"
TO_UTM = Transformer.from_crs(4326, 32650, always_xy=True)
TO_LL = Transformer.from_crs(32650, 4326, always_xy=True)


def ll(p):
    lon, lat = TO_LL.transform(float(p[0]), float(p[1]))
    return [round(lon, 7), round(lat, 7)]


def f(x):
    return f"{x:.10g}" if isinstance(x, float) else str(x)


def arr(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return "[" + ", ".join(arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    return f(round(float(v), 3))


def rectangle(hx, hz, cx=0.0, cz=0.0):
    return [[cx - hx, cz - hz], [cx + hx, cz - hz], [cx + hx, cz + hz], [cx - hx, cz + hz]]


blocks, tris = [], {}


def figure(name, at, facing, colour, top, note, slabs=(), prisms=(), tubes=(), boxes=()):
    """A figure whose 0 is the scene's sea level (base = -ground at its point, from 06_tiles' terrain)."""
    from city3d.common import Terrain
    base = -float(Terrain().height_utm([at[0]], [at[1]])[0])
    tris[name] = 80 * len(tubes) + 12 * len(boxes) + sum(4 * len(p[0]) - 4 for p in prisms) + \
        sum(4 * len(s[0]) - 4 for s in slabs)
    out = [f"# {note}", "[[structures]]", 'kind = "figure"', f'name = "{name}"', "at = [%.7f, %.7f]" % tuple(ll(at)),
           f"facing = {f(round(float(facing), 2))}", 'style = "plain"', "variant = 0.5", f'colour = "{colour}"',
           f"top = {f(round(float(top), 2))}"]
    if abs(base) > 1e-3:
        out.append(f"base = {f(round(base, 2))}")
    for key, v in (("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs)):
        if v:
            out.append(f"{key} = [" + ",\n    ".join(arr(x) for x in v) + "]")
    blocks.append("\n".join(out) + "\n")


def axis(way_id):
    """A bridge outline's middle, unit axis (west to east), length."""
    if not SRC.exists():                         # (fetched once from the city's Overpass list, cached in raw/)
        from city3d.common import overpass
        q = ('[out:json][timeout:100];(way["name:en"~"Tsing Ma Bridge|Ting Kau Bridge|Kap Shui Mun Bridge"];'
             'way["name"~"Tsing Ma Bridge|Ting Kau Bridge|Kap Shui Mun Bridge"];);out tags geom;')
        SRC.write_text(json.dumps(overpass(q)))
    els = json.loads(SRC.read_text())["elements"]
    e = next(x for x in els if x["id"] == way_id)
    P = np.array([TO_UTM.transform(q["lon"], q["lat"]) for q in e["geometry"]])
    c = P.mean(0)
    _, v = np.linalg.eigh(np.cov((P - c).T))
    u = v[:, -1] if v[0, -1] > 0 else -v[:, -1]
    t = (P - c) @ u
    c = c + u * 0.5 * (t.max() + t.min())
    return c, u, float(t.max() - t.min())


def frame(u):
    fwd = np.array([-u[1], u[0]])                   # the frame's z across the bridge, x along it (west to east)
    return math.degrees(math.atan2(fwd[0], fwd[1])) % 360


def catenary(x0, y0, x1, y1, low=None, n=12):
    """Points of a cable from (x0, y0) to (x1, y1), a parabola through `low` at mid-way (None: straight)."""
    pts = []
    for k in range(n + 1):
        s = k / n
        x = x0 + (x1 - x0) * s
        y = y0 + (y1 - y0) * s
        if low is not None:
            y -= 4 * (0.5 * (y0 + y1) - low) * s * (1 - s)
        pts.append([x, y])
    return pts


# ------------------------------------------------------------------ Tsing Ma Bridge
c, u, L = axis(635348630)
half = 0.5 * L
END = 75.0                                       # the outline reaches ~75 m past each anchorage (approach viaducts)
X_TY = half - END - 300.0                        # the Tsing Yi tower (east)
X_MW = X_TY - 1377.0                             # the Ma Wan tower (west)
A_MW, A_TY = X_MW - 355.0, X_TY + 300.0          # the anchorages
H_T, CLEAR, DEPTH, HALF_W = 206.0, 62.0, 7.3, 20.5
CAB_Z, LOW = 18.0, 84.0                          # the cables' half spacing; their lowest point at mid-span (est.)
STEEL, CONCRETE, CABLE = "#9fa3a6", "#bdbbb4", "#c9cbcc"


def deck_y(x):
    """The deck's underside: a slight crest over the main span, easing down to the anchorages (est.)."""
    if X_MW <= x <= X_TY:
        m = 0.5 * (X_MW + X_TY)
        return CLEAR + 4.0 * (1 - ((x - m) / (0.5 * (X_TY - X_MW))) ** 2)
    a = (X_MW - x) / (X_MW + half) if x < X_MW else (x - X_TY) / (half - X_TY)
    return CLEAR - 14.0 * min(max(a, 0.0), 1.0)


xs = np.concatenate([np.linspace(-half, X_MW, 8), np.linspace(X_MW, X_TY, 30)[1:], np.linspace(X_TY, half, 8)[1:]])
bot = [[round(float(x), 1), round(deck_y(x), 2)] for x in xs]
topl = [[round(float(x), 1), round(deck_y(x) + DEPTH, 2)] for x in xs[::-1]]
slabs = [[bot + topl, -HALF_W, HALF_W, STEEL]]
prisms, tubes, boxes = [], [], []
for xt in (X_MW, X_TY):
    for zl in (-CAB_Z, CAB_Z):                   # two tapering legs (est. 14 x 9 m at the foot, 8 x 6 at the top)
        prisms.append([rectangle(7.0, 4.5, xt, zl), 0.0, H_T, CONCRETE, 0.62])
    for yb, d in ((CLEAR - 4.0, 8.0), (105.0, 6.0), (150.0, 6.0), (H_T - 6.0, 6.0)):   # the four portal beams (est.)
        boxes.append([xt, yb, 0.0, 6.0, d, 2 * CAB_Z - 6.0, CONCRETE])
    boxes.append([xt, -1.0, 0.0, 26.0, 6.0, 2 * CAB_Z + 16.0, "#8f8d87"])               # the pile cap at the waterline
for xa in (A_MW, A_TY):                          # the anchorage blocks on the shores (est.)
    boxes.append([xa, 18.0, 0.0, 60.0, 50.0, 2 * CAB_Z + 22.0, CONCRETE])
for xp in np.linspace(A_MW + 90.0, X_MW - 90.0, 3):   # the Ma Wan side span's piers
    boxes.append([float(xp), 0.5 * deck_y(xp), 0.0, 8.0, deck_y(xp), 2 * CAB_Z, CONCRETE])
for zc in (-CAB_Z, CAB_Z):
    lines = [catenary(A_MW, 40.0, X_MW, H_T - 2.0, None, 4), catenary(X_MW, H_T - 2.0, X_TY, H_T - 2.0, LOW, 24),
             catenary(X_TY, H_T - 2.0, A_TY, 40.0, H_T - 2.0 - 0.6 * (H_T - 40.0), 6)]
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            tubes.append([[round(a[0], 2), round(a[1], 2), zc], [round(b[0], 2), round(b[1], 2), zc], 0.55, CABLE])
    # hangers every 36 m over the main span and the Tsing Yi side span (18 m really: half of them, from afar the same)
    for x0, x1, y0, y1, low in ((X_MW, X_TY, H_T - 2.0, H_T - 2.0, LOW),
                                (X_TY, A_TY, H_T - 2.0, 40.0, H_T - 2.0 - 0.6 * (H_T - 40.0))):
        n = int((x1 - x0) // 36)
        for k in range(1, n):
            x = x0 + (x1 - x0) * k / n
            s = (x - x0) / (x1 - x0)
            y = y0 + (y1 - y0) * s - 4 * (0.5 * (y0 + y1) - low) * s * (1 - s)
            if y - (deck_y(x) + DEPTH) > 2.0:
                tubes.append([[round(x, 2), round(y, 2), zc], [round(x, 2), round(deck_y(x) + DEPTH, 2), zc], 0.12, CABLE])
figure("Tsing Ma Bridge", c, frame(u), STEEL, H_T,
       f"Tsing Ma Bridge (1997): {L:.0f} m along OSM's outline, the 1,377 m main span, 206 m towers (scripts/m7f_structures.py)",
       slabs=slabs, prisms=prisms, tubes=tubes, boxes=boxes)
print(f"Tsing Ma: {L:.0f} m, bearing {math.degrees(math.atan2(u[0], u[1])):.1f}, towers at "
      f"{[ll(c + u * x) for x in (X_MW, X_TY)]}")

# ------------------------------------------------------------------ Kap Shui Mun Bridge
c2, u2, L2 = axis(635348629)
half2 = 0.5 * L2
SPAN2, H2, CLEAR2, DEPTH2, W2 = 430.0, 150.0, 47.0, 7.0, 17.5
X1, X2 = -0.5 * SPAN2, 0.5 * SPAN2                # the towers, the main span centred on the outline (est.)


def deck2(x):
    a = abs(x)
    return CLEAR2 + 2.0 * (1 - min(a / X2, 1.0) ** 2) - (max(a - X2, 0.0) / max(half2 - X2, 1.0)) * 10.0


xs2 = np.linspace(-half2, half2, 25)
slabs2 = [[[[round(float(x), 1), round(deck2(x), 2)] for x in xs2]
           + [[round(float(x), 1), round(deck2(x) + DEPTH2, 2)] for x in xs2[::-1]], -W2, W2, STEEL]]
prisms2, boxes2, tubes2 = [], [], []
for xt in (X1, X2):
    for zl in (-W2 - 3.0, W2 + 3.0):
        prisms2.append([rectangle(5.0, 3.5, xt, zl), 0.0, H2, CONCRETE, 0.7])
    for yb in (CLEAR2 - 3.0, H2 - 8.0):
        boxes2.append([xt, yb, 0.0, 5.0, 5.0, 2 * W2 + 2.0, CONCRETE])
    boxes2.append([xt, -1.0, 0.0, 18.0, 6.0, 2 * W2 + 16.0, "#8f8d87"])
    for zp in (-W2 - 1.0, W2 + 1.0):              # stays: a fan each way, anchored from 100 to 145 m (est.)
        for side in (-1, 1):
            for k in range(9):
                ya = 100.0 + 45.0 * k / 8
                xd = xt + side * (25.0 + (SPAN2 / 2 - 30.0) * (k + 1) / 9)
                if abs(xd) > half2 - 10:
                    continue
                tubes2.append([[xt, ya, zp * 0.98], [round(xd, 2), round(deck2(xd) + DEPTH2, 2), zp], 0.3, CABLE])
for xp in (-half2 + 60.0, -half2 + 130.0, half2 - 60.0, half2 - 130.0):
    boxes2.append([xp, 0.5 * deck2(xp), 0.0, 6.0, deck2(xp), 2 * W2 - 6.0, CONCRETE])
figure("Kap Shui Mun Bridge", c2, frame(u2), STEEL, H2,
       f"Kap Shui Mun Bridge (1997): {L2:.0f} m along OSM's outline, a 430 m cable-stayed main span (scripts/m7f_structures.py)",
       slabs=slabs2, prisms=prisms2, tubes=tubes2, boxes=boxes2)
print(f"Kap Shui Mun: {L2:.0f} m, bearing {math.degrees(math.atan2(u2[0], u2[1])):.1f}")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("# generated by scripts/m7f_structures.py (edit the script, not this file): the Lantau Link's bridges (M7 fix 1)\n\n"
               + "\n".join(blocks))
print(f"{OUT}: {len(blocks)} figures, ~{sum(tris.values()):,} triangles {tris}")
