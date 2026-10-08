"""M4 (builder H): London's landmark structures as [[structures]] figures, written to
generated/structures-m4h.toml (city.toml `include`s it; re-run after editing the numbers here):

- the London Eye (a wheel of 120 m on its A-frame, 32 capsules: no OSM outline is used, M2 excludes it);
- Tower Bridge's high walkways, side-span chains and the towers' corner turrets (its towers' bodies are OSM's);
- Nelson's Column (its OSM parts excluded), the O2's twelve masts;
- St Paul's lantern and cross, the Old Royal Naval College's twin domes;
- church steeples over the bodies M2 cut to mean x 1.2 (towers at the west end of each OSM outline);
- the Cutty Sark and HMS Belfast (OSM tags them building=ship: skipped by 04_buildings).

Positions from OSM (the local Overpass / osm_buildings.gpkg), heights from landmarks_london.csv or the photos
(data/landmark_facades.md). Run from demos/london: `uv run python scripts/m4h_structures.py`.
"""
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point as _Pt
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "london"
LAT0 = 51.5
KX, KY = math.cos(math.radians(LAT0)) * 111320.0, 111320.0     # metres per degree (local, enough over 200 m)


def en(lon, lat, at):
    """East, north metres of (lon, lat) from `at`."""
    return np.array([(lon - at[0]) * KX, (lat - at[1]) * KY])


def frame(pt_en, facing):
    """A point's (x, z) in a figure's frame (x right, z forward = compass `facing`)."""
    az = math.radians(facing)
    fwd = np.array([math.sin(az), math.cos(az)])
    right = np.array([fwd[1], -fwd[0]])
    return float(pt_en @ right), float(pt_en @ fwd)


def bearing(a, b):
    d = en(b[0], b[1], a)
    return math.degrees(math.atan2(d[0], d[1])) % 360


def ll_from(at, e, n):
    return [round(at[0] + e / KX, 7), round(at[1] + n / KY, 7)]


def f(x):
    return f"{x:.10g}" if isinstance(x, float) else str(x)


def arr(v):
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    return f(float(v))


_TERRAIN = None


def ground_at(at):
    """The scene ground (m ODN) 06_tiles stands a figure on at (lon, lat)."""
    global _TERRAIN
    from pyproj import Transformer
    from city3d.common import UTM, Terrain
    if _TERRAIN is None:
        _TERRAIN = Terrain()
    x, y = Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform(*at)
    return float(_TERRAIN.height_utm([x], [y])[0])


def rel_base(geoms, centre_xy):
    """Each footprint's base (the lowest ground under it, as 06_tiles stands it) over the ground at the figure's
    point: heights of things set on parts' tops, in the figure's frame."""
    global _TERRAIN
    from city3d.common import Terrain
    if _TERRAIN is None:
        _TERRAIN = Terrain()
    g0 = float(_TERRAIN.height_utm([centre_xy[0]], [centre_xy[1]])[0])
    return np.asarray(_TERRAIN.bases(list(geoms)), float) - g0


def figure(name, at, facing, colour, top, style="floodlit", variant=0.5, base=0.0, sections=None, tubes=None,
           boxes=None, prisms=None, note=None, floor=None, slabs=None, walls=False, segments=None):
    """floor: the figure's 0 at this height (m ODN) whatever the ground under its point (a bridge's parts, a ship
    over the river, where the lidar's DTM keeps a deck or a hull)."""
    if floor is not None:
        base = round(floor - ground_at(at), 2)
    out = []
    if note:
        out += [f"# {line}" for line in note.split("\n")]
    out += ["[[structures]]", 'kind = "figure"', f'name = "{name}"', f"at = {arr(at)}", f"facing = {f(float(facing))}",
            f'style = "{style}"', f"variant = {variant}", f'colour = "{colour}"', f"top = {f(float(top))}"]
    if base:
        out.append(f"base = {f(float(base))}")
    if walls:
        out.append("walls = true")
    if segments:
        out.append(f"segments = {int(segments)}")
    for key, v in (("sections", sections), ("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs)):
        if v:
            out.append(f"{key} = [" + ",\n    ".join(arr(x) for x in v) + "]")
    return "\n".join(out) + "\n"


def ring(r, n=8, phase=None):
    phase = math.pi / n if phase is None else phase
    return [[r * math.cos(phase + 2 * math.pi * i / n), r * math.sin(phase + 2 * math.pi * i / n)] for i in range(n)]


def square(h):
    return [[-h, -h], [h, -h], [h, h], [-h, h]]


blocks = []

# ------------------------------------------------------------------ the London Eye
# OSM: the rim's outline w204068874 (134.9 x 8.5 m, long axis 5.1 deg: the wheel's plane), the hub part w1133007220
# (67-71 m) at its centre, the A-frame's legs as stacked slivers rising from feet ~37 m east (51.50341, -0.11913
# and 51.50319, -0.11919) to 65-68 m beside the hub. Wheel 120 m across, hub ~69 m, capsules outside the rim to
# 135 m (list); 32 capsules (8 m ovoids, here boxes), the rim a truss of two rings, spokes as cables
hub = (-0.119677, 51.503342)
face = 95.0                                       # forward: across the wheel's plane (5 deg), toward the A-frame
R, HUB_Y = 60.0, 69.0
tubes, boxes = [], []
n = 48
for side in (-2.6, 2.6):
    pts = [(R * math.cos(2 * math.pi * i / n), HUB_Y + R * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
    tubes += [[[a[0], a[1], side], [b[0], b[1], side], 0.55] for a, b in zip(pts, pts[1:])]
for i in range(0, n, 2):                          # the truss's struts between the two rings
    a = 2 * math.pi * i / n
    tubes.append([[R * math.cos(a), HUB_Y + R * math.sin(a), -2.6], [R * math.cos(a), HUB_Y + R * math.sin(a), 2.6], 0.3])
for i in range(32):                               # spokes (cables) from the hub's ends to the rim
    a = 2 * math.pi * (i + 0.5) / 32
    z = -5.0 if i % 2 else 5.0
    tubes.append([[0, HUB_Y, z], [R * math.cos(a), HUB_Y + R * math.sin(a), -2.6 if i % 2 else 2.6], 0.14])
for i in range(32):                               # capsules outside the rim
    a = 2 * math.pi * i / 32 + math.pi / 64
    rc = R + 3.6
    boxes.append([round(rc * math.cos(a), 2), round(HUB_Y + rc * math.sin(a), 2), 0, 3.6, 3.4, 8.2, "#d9dde0"])
tubes.append([[0, HUB_Y, -6.5], [0, HUB_Y, 9.0], 1.6])            # the spindle
boxes.append([0, HUB_Y, 0, 6.0, 6.0, 4.0])                        # the hub
for foot in ((-0.11913, 51.50341), (-0.11919, 51.50319)):          # the A-frame's legs
    x, z = frame(en(*foot, hub), face)
    tubes.append([[x, 0.0, z], [x * 0.12, HUB_Y + 1.0, 8.0], 1.25])
tubes.append([[frame(en(-0.11913, 51.50341, hub), face)[0] * 0.55, 32.0, 23.0],
              [frame(en(-0.11919, 51.50319, hub), face)[0] * 0.55, 32.0, 23.0], 0.6])     # the legs' tie
boxes.append([0, 1.0, -1.0, 26.0, 2.0, 12.0, "#a9adb0"])                                      # boarding platform
blocks.append(figure("London Eye", hub, face, "#e9eaec", 135.0, tubes=tubes, boxes=boxes,
                     note="The London Eye (1999-2000): 135 m, a 120 m wheel on a one-sided A-frame over the river wall, 32 capsules\n"
                          "(scripts/m4h_structures.py; OSM's outline, hub and pier are excluded in [buildings])"))

# ------------------------------------------------------------------ Tower Bridge
# towers' centres (OSM w934056837/w934056833, roofs 47-65 m), walkways w367652753/w367653917 (40-45 m, 295 m2, 14.7 m
# apart), corner turrets (6 m2, 36-58 m, pyramidal), the shore towers ("Northern Gate", "Southern Gate", 22 m
# + roof to 30). Chains: lattice girders from the main towers at ~38 m down to the deck's level at mid side span
# and up to the shore towers' tops (photos tower-bridge/*); paint pale blue and white (1977 scheme)
tn, ts = (-0.075136, 51.505857), (-0.075597, 51.505172)
mid = ((tn[0] + ts[0]) / 2, (tn[1] + ts[1]) / 2)
ax = bearing(ts, tn)
half = float(np.linalg.norm(en(*tn, mid)))
gn, gs = (-0.074592, 51.506660), (-0.076129, 51.504361)
BLUE, WHITE = "#7aa6cf", "#e4e6e6"
tubes, boxes = [], []
# M4 fix round (critic: "one flat blue bar"): each high walkway a pair of lattice trusses (chords and Warren
# diagonals, pale blue and white) round a recessed glazed gallery; the bascule span's blue girders at the deck
WL = 2 * half - 13.0                                                 # between the towers' river faces
for x in (-7.35, 7.35):
    boxes.append([x, 40.2, 0, 3.8, 0.7, WL, BLUE])                  # floor
    boxes.append([x, 44.9, 0, 3.8, 0.6, WL, BLUE])                  # roof
    boxes.append([x, 42.5, 0, 2.6, 4.2, WL, "#7f93a3"])             # the glazed gallery, set back
    for side in (-1.75, 1.75):
        xs = x + side
        boxes.append([xs, 40.5, 0, 0.45, 0.9, WL, WHITE])           # bottom chord
        boxes.append([xs, 44.6, 0, 0.45, 0.9, WL, WHITE])           # top chord
        n_p = 14
        for k in range(n_p):
            za, zb = -WL / 2 + k * WL / n_p, -WL / 2 + (k + 1) * WL / n_p
            y0, y1 = (40.9, 44.2) if k % 2 == 0 else (44.2, 40.9)
            tubes.append([[xs, y0, round(za, 2)], [xs, y1, round(zb, 2)], 0.2, WHITE])
            tubes.append([[xs, 40.9, round(za, 2)], [xs, 44.2, round(za, 2)], 0.16, BLUE])
for x in (-9.9, 9.9):                                                # the bascules' girders and railings
    boxes.append([x, 8.0, 0, 0.8, 2.6, WL, BLUE])
    boxes.append([x, 9.6, 0, 0.3, 0.3, WL, WHITE])
for tower, gate, s in ((tn, gn, 1), (ts, gs, -1)):
    gx, gz = frame(en(*gate, mid), ax)
    for x in (-7.35, 7.35):
        p0 = np.array([x, 38.0, s * (half + 8.5)])
        p1 = np.array([gx + x * 0.75, 24.0, gz - s * 4.0])
        pts = []
        for t in np.linspace(0, 1, 9):
            p = p0 + (p1 - p0) * t
            p[1] = (1 - t) * 38.0 + t * 24.0 - 4 * 19.0 * t * (1 - t)   # sags to ~12 m over the deck at mid span
            pts.append([round(float(v), 2) for v in p])
        tubes += [[a, b, 0.75, BLUE] for a, b in zip(pts, pts[1:])]
        for a in pts[1:-1]:                                          # hangers to the deck (11 m)
            if a[1] > 13.0:
                tubes.append([[a[0], 11.0, a[2]], [a[0], a[1], a[2]], 0.16, BLUE])
# the two river piers under the towers (OSM w367652787, w367652791, 9 m: boat-shaped, ~70 x 13 m), to the deck
PIERS = {"n": [(-0.0754851, 51.5059717), (-0.0755083, 51.5059278), (-0.0754753, 51.505866), (-0.0754034, 51.5058262),
               (-0.0749816, 51.5057128), (-0.0748921, 51.5057099), (-0.0747951, 51.5057334), (-0.0747537, 51.5057846),
               (-0.0747814, 51.5058421), (-0.0748619, 51.5058893), (-0.0752773, 51.5059989), (-0.0753563, 51.5060074),
               (-0.0754354, 51.5059946)],
         "s": [(-0.0759549, 51.5052898), (-0.0759781, 51.5052458), (-0.075941, 51.5051857), (-0.0758398, 51.5051395),
               (-0.0754876, 51.5050425), (-0.0754046, 51.5050262), (-0.0753238, 51.5050322), (-0.0752354, 51.5050671),
               (-0.0752383, 51.5051421), (-0.0753316, 51.5052073), (-0.0757409, 51.5053171), (-0.0758231, 51.5053217),
               (-0.0758983, 51.50531)]}
from shapely.geometry import MultiPoint as _MP
prisms = []
for ring_ll in PIERS.values():
    pts = [frame(en(lon, lat, mid), ax) for lon, lat in ring_ll]
    h_ = _MP(pts).convex_hull
    prisms.append([[[round(a_, 2), round(b_, 2)] for a_, b_ in list(h_.exterior.coords)[:-1]], -1.0, 8.3, "#a9a090"])
blocks.append(figure("Tower Bridge walkways and chains", [round(mid[0], 7), round(mid[1], 7)], round(ax, 1), BLUE,
                     65.0, variant=0.4, tubes=tubes, boxes=boxes, prisms=prisms, floor=2.7,
                     note="Tower Bridge (1894): the two high-level walkways (~42 m, 14.7 m apart, OSM's parts) and the side spans'\n"
                          "suspension chains to the shore towers; the towers are OSM's parts (gothic stone: [facade.zones])"))
# M4 fix round (critic: "two thin legs with a slot and spiky tips"): the towers as figures over OSM's parts (named
# by the `near` column of the Tower Bridge row in landmark_facades.csv and dropped there by h@): a solid stone
# shaft 20 x 13 m from the pier to 46 m with a pointed arch over the roadway (an elevation slab), a parapet, a
# steep slate pyramid roof with a gilt finial, four octagonal corner turrets with slate spirelets (OSM's turret
# outlines sit at x +-9.7, z +-5.1 in the tower's frame), Perpendicular windows (monument 0.56, wall runs)
STONE_TB, SLATE_TB, GILT = "#c3bdae", "#4d5560", "#c4a45c"
DECK_Y = 8.3                                                         # the figure's 0 is the water (2.7 m)


def octagon(r, cx=0.0, cz=0.0):
    return [[round(cx + r * math.cos(math.pi / 8 + i * math.pi / 4), 2), round(cz + r * math.sin(math.pi / 8 + i * math.pi / 4), 2)]
            for i in range(8)]


arch = [[-10, DECK_Y], [-5, DECK_Y], [-5, 20.0], [-4.3, 22.6], [-2.9, 24.6], [-1.3, 25.7], [0, 26.0], [1.3, 25.7],
        [2.9, 24.6], [4.3, 22.6], [5, 20.0], [5, DECK_Y], [10, DECK_Y], [10, 46.0], [-10, 46.0]]
for nm, at in (("Tower Bridge north tower", tn), ("Tower Bridge south tower", ts)):
    prisms = [[[[-10.4, -6.9], [10.4, -6.9], [10.4, 6.9], [-10.4, 6.9]], 44.6, 46.4, STONE_TB],
              [[[-9.6, -6.1], [9.6, -6.1], [9.6, 6.1], [-9.6, 6.1]], 46.4, 57.5, SLATE_TB, 0.06]]
    tubes_t = [[[0, 56.8, 0], [0, 62.5, 0], 0.32, GILT], [[0, 60.6, 0], [0, 61.4, 0], 0.75, GILT]]
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx, cz = sx * 9.7, sz * 5.6
            prisms.append([octagon(1.95, cx, cz), DECK_Y, 50.5, STONE_TB])
            prisms.append([octagon(2.25, cx, cz), 49.6, 50.6, STONE_TB])
            prisms.append([octagon(2.0, cx, cz), 50.6, 58.0, SLATE_TB, 0.0])
            tubes_t.append([[cx, 57.6, cz], [cx, 59.4, cz], 0.12, GILT])
    blocks.append(figure(nm, list(at), round(ax, 1), STONE_TB, 62.5, style="monument", variant=0.56, floor=2.7,
                         prisms=prisms, tubes=tubes_t, slabs=[[arch, -6.5, 6.5, STONE_TB]], walls=True))

# ------------------------------------------------------------------ Nelson's Column
# OSM's stack (w150920358, excluded): steps 0-4.7 m (341 -> 51 m2), the bronze-reliefed pedestal 5.2 m square to
# 14 m with its cornice, the fluted granite shaft (3 m) 14-44, the bronze Corinthian capital 43-46, the drum and
# Nelson (5.5 m) to 51.6 (list). Landseer's four lions on plinths at the corners of the steps
nel = (-0.127930, 51.507757)
lion = "#3f3a33"
boxes = [[0, 0.85, 0, 18.4, 1.7, 18.4, "#c9c3b6"], [0, 2.2, 0, 10.3, 1.0, 10.3, "#c9c3b6"],
         [0, 3.2, 0, 8.7, 1.0, 8.7, "#c9c3b6"], [0, 4.2, 0, 7.2, 1.0, 7.2, "#c2bcaf"],
         [0, 9.35, 0, 5.2, 9.3, 5.2, "#bdb6a8"], [0, 12.5, 0, 6.6, 1.0, 6.6, "#bdb6a8"],
         [0, 44.0, 0, 3.8, 0.8, 3.8, "#6e5f45"]]
for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
    boxes += [[sx * 6.7, 2.4, sz * 6.7, 2.6, 1.4, 6.6, "#c9c3b6"], [sx * 6.7, 3.9, sz * 6.7, 1.6, 1.6, 5.2, lion],
              [sx * 6.7, 5.0, sz * (6.7 + 1.6), 1.4, 1.4, 1.4, lion]]
blocks.append(figure("Nelson's Column", nel, 180.0, "#b1aa9d", 51.6, variant=0.5,
                     sections=[[14.0, 0, 0, 1.75, 1.75], [15.0, 0, 0, 1.55, 1.55], [43.0, 0, 0, 1.4, 1.4], [43.2, 0, 0, 1.75, 1.75],
                               [44.4, 0, 0, 1.75, 1.75], [44.4, 0, 0, 1.1, 1.1], [46.2, 0, 0, 1.1, 1.1], [46.2, 0, 0, 0.55, 0.55],
                               [49.5, 0, 0, 0.5, 0.5], [51.1, 0, 0, 0.32, 0.32], [51.6, 0, 0, 0.05, 0.05]],
                     boxes=boxes, note="Nelson's Column (1843): 51.6 m (list); OSM's parts (w150920358) are excluded"))

# ------------------------------------------------------------------ the O2's masts
# twelve masts (OSM man_made=tower nodes, height 100) round the dome's crown, leaning out ~ 5 deg, Busby yellow;
# their stays and hangers to the roof (a few cables each)
o2 = (0.0032, 51.50294)
masts = [(0.003379, 51.501981), (0.00259, 51.502053), (0.004116, 51.502161), (0.001965, 51.50236),
         (0.004615, 51.502549), (0.001667, 51.502827), (0.004736, 51.503041), (0.001786, 51.503319),
         (0.004446, 51.503504), (0.002293, 51.503712), (0.003824, 51.503815), (0.003035, 51.503891)]
c0 = np.mean([en(*m, o2) for m in masts], axis=0)
tubes = []
for m in masts:
    x, z = frame(en(*m, o2) - c0, 0.0)
    r = math.hypot(x, z)
    ux, uz = x / r, z / r
    # the dome's roof height at radius r (182 m, 52 m at the centre, ~10 m at the rim: a spherical cap)
    roof = 52.0 - 42.0 * (r / 182.0) ** 2
    tubes.append([[round(x, 2), round(roof - 8.0, 2), round(z, 2)], [round(x + ux * 6.0, 2), 100.0, round(z + uz * 6.0, 2)], 0.9])
    tubes.append([[round(x + ux * 6.0, 2), 99.0, round(z + uz * 6.0, 2)], [round(x * 0.55, 2), 52.0 - 42.0 * 0.3, round(z * 0.55, 2)], 0.12, "#e8e8e8"])
    tubes.append([[round(x + ux * 6.0, 2), 99.0, round(z + uz * 6.0, 2)], [round(x * 1.45, 2), 52.0 - 42.0 * (1.45 * r / 182) ** 2, round(z * 1.45, 2)], 0.12, "#e8e8e8"])
blocks.append(figure("The O2 masts", ll_from(o2, c0[0], c0[1]), 0.0, "#d8b53c", 100.0, variant=0.6, tubes=tubes,
                     note="The O2 (1999): twelve yellow masts 100 m high (OSM nodes) through the tent, with stays to the roof"))

# ------------------------------------------------------------------ St Paul's lantern and cross
# the table's dome (crown@ in landmark_facades.csv) tops out at 86 m; the stone lantern (85-104 m), the gilt ball
# and cross to 111 m (list) stand on its eye. The lantern's centre: OSM's 111 m part
sp = (-0.098347, 51.513788)
blocks.append(figure("St Paul's lantern", sp, 0.0, "#cdc6b6", 111.0, variant=0.4,
                     sections=[[84.5, 0, 0, 3.6, 3.6], [92.0, 0, 0, 3.6, 3.6], [92.0, 0, 0, 4.2, 4.2], [93.0, 0, 0, 4.2, 4.2],
                               [93.0, 0, 0, 2.6, 2.6], [98.5, 0, 0, 2.4, 2.4], [100.0, 0, 0, 1.6, 1.6], [102.5, 0, 0, 0.5, 0.5],
                               [104.0, 0, 0, 0.35, 0.35], [104.2, 0, 0, 1.1, 1.1], [105.9, 0, 0, 1.0, 1.0], [106.4, 0, 0, 0.18, 0.18],
                               [111.0, 0, 0, 0.18, 0.18]],
                     tubes=[[[-0.9, 109.6, 0], [0.9, 109.6, 0], 0.16, "#c4a45c"], [[0, 105.0, 0], [0, 111.0, 0], 0.2, "#c4a45c"]],
                     note="St Paul's Cathedral: the lantern, gilt ball and cross over the dome to 111 m (OSM's lantern part)"))

# ------------------------------------------------------------------ St Paul's dome, drum colonnade and west front
# M4 fix round (critic: "drum with a colonnade ring and the Stone Gallery, a taller dome profile with more
# segments, west front with two column tiers, pediment"): the table drops OSM's 66-85 m dome part (h@85=66); here
# the outer dome (66-85.5 m, 16.2 m radius, a raised semi-ellipse in 32 segments, lead) on the 16.7 m attic drum,
# the peristyle of 32 columns (radius 19.6 m, 56-64.5 m) on OSM's 52-56 m ring, the Stone Gallery (64.5-66.2 m,
# radius 20.8 m); at the west front two tiers of paired columns (12 below, 8 above) with their entablatures and
# the pediment (photos st-pauls-cathedral/01-04)
PORT = "#e2ddd2"
secs = [[65.8, 0, 0, 16.4, 16.4], [67.2, 0, 0, 16.4, 16.4]]
for t in np.linspace(0.08, 1.32, 14):
    secs.append([round(67.2 + 18.6 * math.sin(t), 2), 0, 0, round(16.4 * math.cos(t), 2), round(16.4 * math.cos(t), 2)])
blocks.append(figure("St Paul's dome", sp, 0.0, "#8f9396", 86.0, variant=0.4, sections=secs, segments=32,
                     note="St Paul's Cathedral: the outer dome, drum colonnade, Stone Gallery and west front (M4 fix round)"))
tubes = []
for i in range(32):
    a = 2 * math.pi * (i + 0.5) / 32
    tubes.append([[round(19.6 * math.cos(a), 2), 56.0, round(19.6 * math.sin(a), 2)],
                  [round(19.6 * math.cos(a), 2), 64.4, round(19.6 * math.sin(a), 2)], 0.62, PORT])
blocks.append(figure("St Paul's Stone Gallery", sp, 0.0, PORT, 66.2, variant=0.4, tubes=tubes,
                     sections=[[64.3, 0, 0, 20.9, 20.9], [66.2, 0, 0, 20.9, 20.9]], segments=32))
# the west front: the portico's centre (OSM's 15-19 m part) facing west along the nave's axis (81.6 deg)
_sp = gpd.read_file(DATA / "buildings.gpkg")
_sp = _sp[_sp.name == "St Paul's Cathedral"].to_crs(32630)
_wf = _sp[((_sp.h - 19.0).abs() < 0.3) & ((_sp.min_h - 15.0).abs() < 0.3)].geometry.iloc[0].centroid
_wf = gpd.GeoSeries([_wf], crs=32630).to_crs(4326).iloc[0]
wf = (round(_wf.x, 7), round(_wf.y, 7))
tubes, boxes = [], []
xs_low = [-14.6, -13.2, -9.0, -7.6, -3.4, -2.0, 2.0, 3.4, 7.6, 9.0, 13.2, 14.6]
xs_up = [-9.0, -7.6, -3.4, -2.0, 2.0, 3.4, 7.6, 9.0]
for x in xs_low:
    tubes.append([[x, 3.5, 4.2], [x, 15.0, 4.2], 0.62, PORT])
for x in xs_up:
    tubes.append([[x, 18.0, 3.4], [x, 29.0, 3.4], 0.55, PORT])
boxes += [[0, 16.0, 3.9, 32.0, 2.0, 2.2, PORT], [0, 29.9, 3.1, 21.0, 1.8, 2.0, PORT], [0, 17.2, 3.2, 22.0, 0.6, 1.6, PORT]]
blocks.append(figure("St Paul's west front", list(wf), 261.6, PORT, 37.0, variant=0.4, tubes=tubes, boxes=boxes,
                     slabs=[[[[-11.2, 30.8], [11.2, 30.8], [0, 36.6]], 1.6, 4.4, PORT]]))

# ------------------------------------------------------------------ the National Gallery's portico
# M4 fix round (critic: "portico and small domes"): eight Corinthian columns (3.5-13 m) before the central bay on
# Trafalgar Square, its entablature and pediment (15-19.5 m); the domes are the table's crowns
ng = gpd.read_file(DATA / "buildings.gpkg")
ng = ng[ng.name == "National Gallery"].to_crs(32630)
pr = ng[((ng.h - 15.0).abs() < 0.3) & (ng.area > 100)]
if len(pr):
    g = pr.geometry.iloc[0]
    q = np.array(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [q[1] - q[0], q[2] - q[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    L_, D_ = float(np.hypot(*e[i])), float(np.hypot(*e[1 - i]))
    fwd_ = np.array([e[1 - i][0], e[1 - i][1]]) / D_
    if fwd_[1] > 0:                                                  # forward: south, onto the square
        fwd_ = -fwd_
    face_ng = math.degrees(math.atan2(fwd_[0], fwd_[1])) % 360
    ctr = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
    ll = gpd.GeoSeries(gpd.points_from_xy([ctr[0]], [ctr[1]]), crs=32630).to_crs(4326).iloc[0]
    tubes = [[[round(float(x), 2), 3.5, round(D_ / 2 - 1.0, 2)], [round(float(x), 2), 13.0, round(D_ / 2 - 1.0, 2)], 0.55, "#d8d2c6"]
             for x in np.linspace(-L_ / 2 + 1.0, L_ / 2 - 1.0, 8)]
    blocks.append(figure("National Gallery portico", [round(ll.x, 7), round(ll.y, 7)], round(face_ng, 1), "#d8d2c6", 19.5,
                         variant=0.4, tubes=tubes, boxes=[[0, 3.2, 0, L_ + 1, 0.6, D_ + 1, "#cfc8bb"]],
                         slabs=[[[[-L_ / 2, 15.0], [L_ / 2, 15.0], [0, 19.5]], D_ / 2 - 2.0, D_ / 2, "#d8d2c6"]]))

# ------------------------------------------------------------------ the Old Royal Naval College's twin domes
# over the vestibules at the facing ends of the Painted Hall (w1031150753) and the Chapel (w467807043): a drum of
# paired columns (Wren, 1702-05) from the 22 m roof, a lead dome, a stone lantern; top ~50 m (list, ESTIMATED)
for nm, at in (("Old Royal Naval College west dome (Painted Hall)", (-0.005800, 51.482995)),
               ("Old Royal Naval College east dome (Chapel)", (-0.005085, 51.483245))):
    tubes = []
    for i in range(16):
        a = 2 * math.pi * i / 16
        tubes.append([[round(8.1 * math.cos(a), 2), 23.5, round(8.1 * math.sin(a), 2)],
                      [round(8.1 * math.cos(a), 2), 32.0, round(8.1 * math.sin(a), 2)], 0.42, "#dcd5c6"])
    blocks.append(figure(nm, at, 0.0, "#cfc8b8", 50.0, variant=0.4,
                         sections=[[20.0, 0, 0, 9.4, 9.4], [23.5, 0, 0, 9.4, 9.4], [23.5, 0, 0, 7.0, 7.0], [32.0, 0, 0, 7.0, 7.0],
                                   [32.0, 0, 0, 9.0, 9.0], [33.6, 0, 0, 9.0, 9.0], [33.6, 0, 0, 7.4, 7.4], [36.0, 0, 0, 7.4, 7.4],
                                   [39.0, 0, 0, 6.6, 6.6], [42.0, 0, 0, 4.5, 4.5], [43.6, 0, 0, 1.8, 1.8], [43.6, 0, 0, 1.5, 1.5],
                                   [47.6, 0, 0, 1.4, 1.4], [49.0, 0, 0, 0.4, 0.4], [50.0, 0, 0, 0.1, 0.1]],
                         tubes=tubes))

# ------------------------------------------------------------------ church steeples
# M2 cut 17 churches (and the City's) to their bodies (mean x 1.2); here their towers and spires come back at the
# west end of each OSM outline (the long side of its rotated rectangle; St Mary-le-Bow's tower is at its NW corner
# on Cheapside). kind: spire (square tower, octagonal spire), tower (pinnacled), wren (a Wren steeple: tower, then
# stacked stages and an obelisk or spirelet), cupola (tower with a lead cupola). Tip heights: the lidar's top of the
# outline (Carbon & Place height_max) or the photos/list where the lidar misses a slender spire.
CHURCHES = [
    # osm id, name, kind, tower side m, tower top m, tip m, end ("w" west / "e" east / "n" / "s" / lon,lat)
    ("w420026096", "Christ Church Spitalfields", "spire", 10.0, 38.0, 62.0, "w"),
    ("w4366294", "St Anne's Limehouse", "wren", 9.0, 34.0, 50.0, "w"),
    ("w79107228", "St Matthew's Church Bayswater", "spire", 7.5, 26.0, 53.5, "w"),
    ("w90244113", "St Mary-le-Bow", "wren", 9.5, 32.0, 68.0, "-0.093690,51.513860"),
    ("w30734422", "St Martin-in-the-Fields", "wren", 8.0, 30.0, 58.5, "w"),
    ("w58757328", "St Mary Magdalene", "spire", 6.5, 26.0, 45.4, "w"),
    ("w24348883", "St George-in-the-East", "cupola", 9.0, 36.0, 49.0, "w"),
    ("w174444765", "St Barnabas", "spire", 6.0, 22.0, 43.0, "w"),
    ("w4076420", "St Bride's", "wren", 8.5, 30.0, 69.0, "w"),
    ("w107740117", "St Botolph's Aldgate", "wren", 7.0, 26.0, 40.8, "w"),
    ("w170332136", "St James, Sussex Gardens", "spire", 6.5, 22.0, 40.3, "w"),
    ("w25904232", "St Clement Danes", "wren", 7.5, 26.0, 40.0, "w"),
    ("w158230794", "St Alfege Church", "wren", 7.5, 25.0, 37.4, "w"),
    ("w80888188", "St Marylebone Parish Church", "cupola", 8.0, 26.0, 36.5, "s"),
    ("w34038668", "St Giles-without-Cripplegate", "cupola", 8.0, 30.0, 35.9, "w"),
    ("w31755869", "St Sepulchre-without-Newgate", "tower", 9.0, 30.0, 33.8, "w"),
    ("w59213570", "All Hallows-by-the-Tower", "cupola", 7.0, 24.0, 31.7, "w"),
    ("w242282602", "St Saviour's, Pimlico", "spire", 6.0, 18.0, 31.7, "w"),
    ("w51517078", "St Pancras Church", "wren", 7.0, 24.0, 36.0, "w"),
    ("w38318529", "Grosvenor Chapel", "cupola", 5.5, 20.0, 29.9, "w"),
    ("w107278303", "St Gabriel's", "spire", 5.5, 18.0, 28.9, "w"),
    ("w361410984", "St Stephen's Church", "spire", 6.0, 18.0, 28.2, "w"),
    ("w170205774", "St Botolph-without-Aldersgate", "cupola", 5.5, 19.0, 25.7, "w"),
    ("w76236566", "St Augustine's Kilburn", "spire", 9.0, 34.0, 70.0, "w"),
    ("w197280789", "St Mary and St Joseph (Poplar)", "tower", 8.0, 30.0, 34.2, "w"),
]
osm = gpd.read_file(DATA / "osm_buildings.gpkg")
osm = osm[osm.osm_id.isin([c[0] for c in CHURCHES])].set_index("osm_id")
osm_m = osm.to_crs(32630)
STONE = "#bdb5a5"
for oid, name, kind, side, ttop, tip, end in CHURCHES:
    if oid not in osm.index:
        print(f"no OSM outline {oid} ({name})")
        continue
    g = osm_m.geometry[oid]
    if "," in end:
        at = tuple(map(float, end.split(",")))
        r = g.minimum_rotated_rectangle
        c = np.array(r.exterior.coords)[:4]
        e = [c[1] - c[0], c[2] - c[1]]
        i = int(np.argmax([np.hypot(*v) for v in e]))
        facing = math.degrees(math.atan2(e[i][0], e[i][1])) % 180
    else:
        r = g.minimum_rotated_rectangle
        c = np.array(r.exterior.coords)[:4]
        e = [c[1] - c[0], c[2] - c[1]]
        i = int(np.argmax([np.hypot(*v) for v in e]))
        u = e[i] / np.hypot(*e[i])                               # the long axis
        ctr = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
        L = np.hypot(*e[i])
        want = {"w": np.array([-1, 0]), "e": np.array([1, 0]), "n": np.array([0, 1]), "s": np.array([0, -1])}[end]
        if u @ want < 0:
            u = -u
        p = ctr + u * (L / 2 - side / 2 - 0.5)
        pt = gpd.GeoSeries(gpd.points_from_xy([p[0]], [p[1]]), crs=32630).to_crs(4326).iloc[0]
        at = (pt.x, pt.y)
        facing = math.degrees(math.atan2(u[0], u[1])) % 360
    h = side / 2
    prisms, sections, tubes = [[square(h), 0.0, ttop, STONE]], None, []
    if kind == "spire":
        prisms.append([square(h + 0.35), ttop - 1.2, ttop, STONE])
        sections = [[ttop, 0, 0, h * 0.92, h * 0.92], [ttop + 0.15 * (tip - ttop), 0, 0, h * 0.62, h * 0.62],
                    [tip - 0.6, 0, 0, 0.18, 0.18], [tip, 0, 0, 0.04, 0.04]]
        for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            tubes.append([[sx * (h - 0.4), ttop, sz * (h - 0.4)], [sx * (h - 0.4), ttop + 3.5, sz * (h - 0.4)], 0.35, STONE])
    elif kind == "tower":
        prisms.append([square(h + 0.3), ttop - 1.0, ttop, STONE])
        for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            tubes.append([[sx * (h - 0.5), ttop, sz * (h - 0.5)], [sx * (h - 0.5), tip, sz * (h - 0.5)], 0.45, STONE])
    elif kind == "cupola":
        s = tip - ttop
        sections = [[ttop, 0, 0, h * 0.75, h * 0.75], [ttop + 0.35 * s, 0, 0, h * 0.7, h * 0.7], [ttop + 0.35 * s, 0, 0, h * 0.78, h * 0.78],
                    [ttop + 0.6 * s, 0, 0, h * 0.55, h * 0.55], [ttop + 0.8 * s, 0, 0, 0.3, 0.3], [tip, 0, 0, 0.05, 0.05]]
    else:                                                       # wren: stages of a diminishing octagon, then a spirelet
        s = tip - ttop
        sections = [[ttop, 0, 0, h * 0.85, h * 0.85], [ttop + 0.18 * s, 0, 0, h * 0.85, h * 0.85],
                    [ttop + 0.18 * s, 0, 0, h * 0.7, h * 0.7], [ttop + 0.34 * s, 0, 0, h * 0.7, h * 0.7],
                    [ttop + 0.34 * s, 0, 0, h * 0.56, h * 0.56], [ttop + 0.48 * s, 0, 0, h * 0.56, h * 0.56],
                    [ttop + 0.48 * s, 0, 0, h * 0.44, h * 0.44], [ttop + 0.6 * s, 0, 0, h * 0.44, h * 0.44],
                    [ttop + 0.6 * s, 0, 0, h * 0.32, h * 0.32], [tip - 0.8, 0, 0, 0.15, 0.15], [tip, 0, 0, 0.04, 0.04]]
        prisms.append([square(h + 0.3), ttop - 1.0, ttop, STONE])
    if sections:
        sections = [[round(v, 2) if isinstance(v, float) else v for v in s_] for s_ in sections]
    prisms = [[[[round(a, 2), round(b, 2)] for a, b in pr[0]], pr[1], pr[2], pr[3]] for pr in prisms]
    blocks.append(figure(f"{name} steeple", [round(at[0], 7), round(at[1], 7)], round(facing, 1), STONE if kind != "cupola" else "#8a9097",
                         tip, variant=0.4, sections=sections, prisms=prisms, tubes=tubes or None))

# ------------------------------------------------------------------ St Pancras's towers
# the Midland Grand Hotel (1876; OSM w15694166, set_h 34 m to its roofs): the clock tower at the east end of the
# Euston Road front (82 m, list) and the west tower at the Midland Road corner (~70 m, est.): red brick, stone bands,
# steep slate roofs with a spirelet
BRICK, SLATE = "#9a5040", "#5d6168"
# (M4 fix round, critic: "a much taller clock tower"): its shaft 12 m square to 61 m under the 82 m roof's tip
for nm, at, side, top_body, tip in (("St Pancras clock tower", (-0.124640, 51.530120), 12.0, 61.0, 82.0),
                                     ("St Pancras west tower", (-0.126170, 51.529345), 9.5, 52.0, 70.0)):
    h = side / 2
    s = tip - top_body
    blocks.append(figure(nm, [at[0], at[1]], 20.0, SLATE, tip, variant=0.4,
                         prisms=[[square(h), 0.0, top_body, BRICK], [square(h + 0.4), top_body - 1.0, top_body, "#cdbfa6"]],
                         sections=[[top_body, 0, 0, h * 0.98, h * 0.98], [top_body + 0.55 * s, 0, 0, h * 0.5, h * 0.5],
                                   [top_body + 0.62 * s, 0, 0, 0.9, 0.9], [tip, 0, 0, 0.05, 0.05]],
                         boxes=[[0, top_body - 8.0, 0, side + 0.3, 4.0, 3.2, "#efe9da"],
                                [0, top_body - 8.0, 0, 3.2, 4.0, side + 0.3, "#efe9da"]] if "clock" in nm else None))

# ------------------------------------------------------------------ the Midland Grand Hotel's dormers
# M4 fix round (critic: "steep slate roofs with dormers"): the table's `roofs@9` makes the hotel's top 9 m a
# hipped slate roof from 25 m; a gabled dormer (brick cheeks, slate cap) every 7 m along its outer walls, 1.6 m
# in from the eaves
ho = gpd.read_file(DATA / "buildings.gpkg")
ho = ho[ho.name == "St Pancras Renaissance London Hotel"].to_crs(32630)
if len(ho):
    g = ho.geometry.union_all()
    c2 = np.array(g.centroid.coords[0])
    ll2 = gpd.GeoSeries(gpd.points_from_xy([c2[0]], [c2[1]]), crs=32630).to_crs(4326).iloc[0]
    eave = float(rel_base([g], c2)[0]) + float(ho.h.max()) - 9.0
    prisms = []
    for poly in getattr(g, "geoms", [g]):
        ring_ = poly.exterior
        for t in np.arange(3.0, ring_.length - 3.0, 7.0):
            a_, b_ = np.array(ring_.interpolate(t - 1.1).coords[0]), np.array(ring_.interpolate(t + 1.1).coords[0])
            d_ = (b_ - a_) / max(np.linalg.norm(b_ - a_), 1e-6)
            n_ = np.array([-d_[1], d_[0]])
            mid_ = (a_ + b_) / 2
            if not poly.contains(_Pt(*(mid_ + n_ * 3.0))):
                n_ = -n_                                               # inward
            q = [a_ + n_ * 1.6, b_ + n_ * 1.6, b_ + n_ * 3.4, a_ + n_ * 3.4]
            q = [[round(float(v[0] - c2[0]), 2), round(float(v[1] - c2[1]), 2)] for v in q]
            prisms.append([q, round(eave, 1), round(eave + 3.0, 1), "#9a5040"])
            prisms.append([q, round(eave + 3.0, 1), round(eave + 4.6, 1), "#4f5560", 0.15])
    blocks.append(figure("St Pancras hotel dormers", [round(ll2.x, 7), round(ll2.y, 7)], 0.0, "#9a5040", 40.0, variant=0.4,
                         prisms=prisms, note=f"the Midland Grand Hotel's dormers ({len(prisms) // 2}) on its slate roofs (M4 fix round)"))

# ------------------------------------------------------------------ the Elizabeth Tower's clock faces
# four dials (7 m across, centres ~55 m) on the shaft under the belfry: the tower's frame from the table's body
# piece (its rotated rectangle), opal glass in gilt frames
bt = gpd.read_file(DATA / "buildings.gpkg")
bt = bt[bt.name == "Elizabeth Tower (Big Ben)"].to_crs(32630)
body = bt[(bt.h > 50) & (bt.h <= 61)]
if len(body):
    g = body.geometry.union_all()
    r = g.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e = c[1] - c[0]
    fac = math.degrees(math.atan2(e[0], e[1])) % 90
    w = [float(np.hypot(*(c[1] - c[0]))), float(np.hypot(*(c[2] - c[1])))]
    ctr = gpd.GeoSeries([r.centroid], crs=32630).to_crs(4326).iloc[0]
    hx, hz = w[1] / 2 + 0.25, w[0] / 2 + 0.25            # x across e's normal, z along e
    gil = "#c4a45c"
    # M4 fix round (critic: "large pale clock dials with a gilded belfry and a dark spire"): dials 7 m in 8 m
    # gilt frames, the belfry stage (60.5-69 m, the table's crown under its dark iron spire) cased in gilt stone
    boxes = [[hx, 55.0, 0, 0.5, 8.2, 8.2, gil], [-hx, 55.0, 0, 0.5, 8.2, 8.2, gil],
             [0, 55.0, hz, 8.2, 8.2, 0.5, gil], [0, 55.0, -hz, 8.2, 8.2, 0.5, gil],
             [hx + 0.2, 55.0, 0, 0.3, 7.2, 7.2, "#f1ecd9"], [-hx - 0.2, 55.0, 0, 0.3, 7.2, 7.2, "#f1ecd9"],
             [0, 55.0, hz + 0.2, 7.2, 7.2, 0.3, "#f1ecd9"], [0, 55.0, -hz - 0.2, 7.2, 7.2, 0.3, "#f1ecd9"],
             [0, 65.0, 0, 2 * hx + 0.3, 8.6, 2 * hz + 0.3, "#c9b27c"]]
    blocks.append(figure("Elizabeth Tower clock faces", [round(ctr.x, 7), round(ctr.y, 7)], round(fac, 1), gil, 69.3,
                         variant=0.5, boxes=boxes,
                         note=f"the Elizabeth Tower's four dials (tower {w[0]:.1f} x {w[1]:.1f} m in the table)"))

# ------------------------------------------------------------------ the Palace's pinnacles
# M4 fix round (critic: "rows of pinnacles along the ridges"): a stone pinnacle every 7 m along each part's outline
# at its eaves (the table's `roofs@7` cuts the top 7 m of every part into a hipped iron roof), parts of 60 m2 and
# 15 m up; in UTM grid coordinates (the figure frame's own) from the Palace's centre
pal = gpd.read_file(DATA / "buildings.gpkg")
pal = pal[pal.name == "Palace of Westminster (Houses of Parliament)"].to_crs(32630)
if len(pal):
    c0_ = np.array(pal.geometry.union_all().centroid.coords[0])
    ll0 = gpd.GeoSeries(gpd.points_from_xy([c0_[0]], [c0_[1]]), crs=32630).to_crs(4326).iloc[0]
    prisms, seen = [], set()
    from shapely.geometry import Point as _Pt
    edge_ = pal.geometry.buffer(0.3).union_all().buffer(-0.3).boundary     # outer walls and courtyards, not shared ones
    pal["rb"] = rel_base(pal.geometry.values, c0_)
    for _, r in pal.iterrows():
        if r.geometry.area < 60 or r.h < 15 or r.h - (r.min_h or 0) < 9:
            continue
        eaves = float(r.rb) + float(r.h) - 7.0
        for poly in getattr(r.geometry, "geoms", [r.geometry]):
            ring_ = poly.exterior
            for t in np.arange(0, ring_.length, 7.0):
                pt_ = ring_.interpolate(t)
                if edge_.distance(pt_) > 1.2:
                    continue
                q = np.array(pt_.coords[0]) - c0_
                key = (round(q[0] / 3), round(q[1] / 3))
                if key in seen:
                    continue
                seen.add(key)
                prisms.append([[[round(q[0] + a_, 2), round(q[1] + b_, 2)] for a_, b_ in square(0.7)], round(eaves - 1.0, 1), round(eaves + 5.5, 1), "#c4b597", 0.0])
    blocks.append(figure("Palace of Westminster pinnacles", [round(ll0.x, 7), round(ll0.y, 7)], 0.0, "#c4b597", 30.0, variant=0.4,
                         prisms=prisms, note=f"the Palace of Westminster's pinnacles ({len(prisms)}) along its parts' eaves (M4 fix round)"))

# ------------------------------------------------------------------ the Tower of London's battlements
# M4 fix round (critic: "crenellated parapets on the walls"): merlons (1.3 m wide, 1.2 m high, every 2.6 m) along
# the outer faces of the curtain walls and towers (the [facade.zones] polygon, ragstone) and round the White Tower's
# parapet (pale Caen stone), in UTM grid coordinates from the castle's centre
import tomllib
_zone = tomllib.loads((HERE / "city.toml").read_text())["facade"]["zones"]["Tower of London (walls and towers)"]["polygon"]
from shapely.geometry import Polygon as _Poly
_zone = gpd.GeoSeries([_Poly(_zone)], crs=4326).to_crs(32630).iloc[0]
tol = gpd.read_file(DATA / "buildings.gpkg").to_crs(32630)
tol = tol[tol.geometry.representative_point().within(_zone)]
SKIP = {"International House", "Waterloo Block", "New Armouries", "Royal Regiment of Fusiliers Headquarters",
        "Chapel of Saint Peter ad Vincula", "Sergeant's Mess", "Ravens Enclosure"}
tol = tol[~tol.name.isin(SKIP) & (tol.h >= 6) & ((tol.h <= 23) | (tol.name == "Tower of London (White Tower)"))
          & (tol.geometry.area >= 20)]
if len(tol):
    c1 = np.array(tol.geometry.union_all().centroid.coords[0])
    ll1 = gpd.GeoSeries(gpd.points_from_xy([c1[0]], [c1[1]]), crs=32630).to_crs(4326).iloc[0]
    edge_t = tol.geometry.buffer(0.3).union_all().buffer(-0.3).boundary
    tol["rb"] = rel_base(tol.geometry.values, c1)
    prisms, seen = [], set()
    for _, r in tol.iterrows():
        keep_ = r["name"] == "Tower of London (White Tower)"
        if keep_ and r.h > 23:
            continue
        col = "#d3cab8" if keep_ else "#968c7c"
        for poly in getattr(r.geometry, "geoms", [r.geometry]):
            ring_ = poly.exterior
            for t in np.arange(1.0, ring_.length - 1.0, 2.6):
                pt_ = ring_.interpolate(t)
                if edge_t.distance(pt_) > 0.8 and not keep_:
                    continue
                a_, b_ = np.array(ring_.interpolate(t - 0.65).coords[0]), np.array(ring_.interpolate(t + 0.65).coords[0])
                d_ = (b_ - a_) / max(np.linalg.norm(b_ - a_), 1e-6)
                n_ = np.array([-d_[1], d_[0]]) * 0.45
                q = [a_ - n_ - c1, b_ - n_ - c1, b_ + n_ - c1, a_ + n_ - c1]
                key = (round(pt_.x), round(pt_.y))
                if key in seen:
                    continue
                seen.add(key)
                prisms.append([[[round(float(v[0]), 2), round(float(v[1]), 2)] for v in q], round(float(r.rb + r.h) - 0.2, 1), round(float(r.rb + r.h) + 1.2, 1), col])
    blocks.append(figure("Tower of London battlements", [round(ll1.x, 7), round(ll1.y, 7)], 0.0, "#968c7c", 24.0, variant=0.4,
                         prisms=prisms, note=f"the Tower of London's merlons ({len(prisms)}) on its walls, towers and the White Tower (M4 fix round)"))

# ------------------------------------------------------------------ the Palace's Central Tower spire
# OSM's octagon (53.5-62 m) and lantern (62-78 m) stop short of the spire's 91 m (list): the stone spirelet
blocks.append(figure("Palace of Westminster Central Tower spire", (-0.1247252, 51.4993864), 0.0, "#b8a482", 91.0, variant=0.4,
                     sections=[[76.0, 0, 0, 1.9, 1.9], [78.5, 0, 0, 1.6, 1.6], [88.0, 0, 0, 0.35, 0.35], [91.0, 0, 0, 0.05, 0.05]]))

# ------------------------------------------------------------------ the BT Tower's antenna galleries
# the open section over the equipment floors (OSM's core 134 m2 between its 24-100 and 144-166 m rings): the
# microwave galleries as four pale rings round the core (photos bt-tower/*; dishes removed 2011, rings remain)
sec = []
for y in (104.0, 112.0, 120.0, 128.0, 136.0):
    sec += [[y - 0.8, 0, 0, 6.6, 6.6], [y - 0.8, 0, 0, 9.6, 9.6], [y + 0.6, 0, 0, 9.6, 9.6], [y + 0.6, 0, 0, 6.6, 6.6]]
blocks.append(figure("BT Tower antenna galleries", (-0.138804, 51.521442), 0.0, "#d6d9da", 177.0, variant=0.4, sections=sec))

# ------------------------------------------------------------------ the Leadenhall Building's megaframe and core
# M4 fix round (critic: the wedge should show "large X megaframe braces spanning several floors, visible mostly at
# the edges" and the "yellow/orange lift core on the north side"): over the table's wedge (the 28.5-224.5 m part,
# `shape@224.5:lean:180:0:1 1:0.15`: the north face vertical, the south face sloping back to 15 % of the depth),
# the perimeter megaframe as steel tubes: the four edges, a ring beam every 28 m (seven storeys) and an X per bay
# of each tier on the east and west faces (photos cheesegrater/01-05: white-painted steel); on the north core's
# face (the 196 m part) the lift shafts' yellow and orange frames
BT_ = gpd.read_file(DATA / "buildings.gpkg")
BT_ = BT_[BT_.name.str.startswith("The Leadenhall Building", na=False)].to_crs(32630)


def part_frame(rows, h, min_h=None):
    """A part's minimum rotated rectangle as a frame: (centre lon/lat, facing = its north-most axis, half width
    across (x), half depth along (z))."""
    r = rows[((rows.h - h).abs() < 0.6) & (True if min_h is None else ((rows.min_h - min_h).abs() < 0.6))]
    g = r.geometry.iloc[r.area.argmax()]
    q = np.array(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [q[1] - q[0], q[2] - q[1]]
    i = 0 if abs(e[0][1]) > abs(e[0][0]) else 1                      # the edge running north-south-ish
    u = e[i] / np.hypot(*e[i])
    if u[1] < 0:
        u = -u
    face = math.degrees(math.atan2(u[0], u[1])) % 360
    ctr = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
    ll = gpd.GeoSeries(gpd.points_from_xy([ctr[0]], [ctr[1]]), crs=32630).to_crs(4326).iloc[0]
    return [round(ll.x, 7), round(ll.y, 7)], face, float(np.hypot(*e[1 - i])) / 2, float(np.hypot(*e[i])) / 2, ctr, u


if len(BT_):
    at_lb, face_lb, hx, hz, ctr_lb, u_lb = part_frame(BT_, 224.5, 28.5)
    Y0, Y1, K = 28.5, 224.5, 0.15
    STEEL = "#e2e4e3"

    def zs(y):                                                       # the south face's z at height y
        return hz - 2 * hz * (1 - (1 - K) * (y - Y0) / (Y1 - Y0))
    tubes = []
    for x in (-hx, hx):
        tubes.append([[x, Y0, hz], [x, Y1, hz], 0.55, STEEL])                         # north edges
        tubes.append([[x, Y0, round(zs(Y0), 2)], [x, Y1, round(zs(Y1), 2)], 0.55, STEEL])   # sloping south edges
    tiers = np.linspace(Y0, Y1, 8)
    for y in tiers:
        zz = round(zs(y), 2)
        tubes += [[[-hx, y, zz], [hx, y, zz], 0.4, STEEL], [[-hx, y, hz], [hx, y, hz], 0.3, STEEL]]
        for x in (-hx, hx):
            tubes.append([[x, y, zz], [x, y, hz], 0.4, STEEL])
    for ya, yb in zip(tiers, tiers[1:]):
        for x in (-hx * 1.003, hx * 1.003):                          # an X per tier on the east and west faces
            za, zb = zs(ya), zs(yb)
            tubes.append([[x, ya, round(za, 2)], [x, yb, hz], 0.35, STEEL])
            tubes.append([[x, ya, hz], [x, yb, round(zb, 2)], 0.35, STEEL])
    # the core: the 196 m part north of the wedge; its north face carries the lifts' frames
    core_at, core_face, cx_, cz_, core_ctr, _ = part_frame(BT_, 196.0)
    off = (core_ctr - ctr_lb) @ u_lb                                  # how far north of the wedge's centre
    boxes = []
    for k, (x, col) in enumerate(zip(np.linspace(-cx_ * 0.7, cx_ * 0.7, 5), ["#e0b23a", "#e0b23a", "#cf6b2a", "#e0b23a", "#e0b23a"])):
        boxes.append([round(float(x), 2), 100.0, round(off + cz_ + 0.5, 2), 3.2, 186.0, 1.0, col])
    for y in np.arange(14.0, 196.0, 14.0):                            # the core's steel floor bands
        boxes.append([0, float(y), round(off + cz_ + 1.1, 2), 2 * cx_ * 0.92, 0.7, 0.3, "#3b3f44"])
    blocks.append(figure("Leadenhall Building megaframe", at_lb, round(face_lb, 1), STEEL, 224.5, variant=0.4,
                         tubes=tubes, boxes=boxes,
                         note="the Leadenhall Building's perimeter megaframe and north core lifts (M4 fix round)"))

# ------------------------------------------------------------------ the Victoria Memorial
# before Buckingham Palace (1911-24): white marble, a round stepped base in its pool, the central pylon with the
# seated Queen, gilt Victory on top at ~25 m (est. from photos)
vm = (-0.140630, 51.501890)
blocks.append(figure("Victoria Memorial", vm, 60.0, "#e4e1da", 25.0, variant=0.5,
                     sections=[[0, 0, 0, 17.0, 17.0], [1.0, 0, 0, 17.0, 17.0], [1.0, 0, 0, 12.0, 12.0], [2.5, 0, 0, 12.0, 12.0],
                               [2.5, 0, 0, 6.5, 6.5], [11.0, 0, 0, 5.2, 5.2], [11.0, 0, 0, 3.4, 3.4], [18.5, 0, 0, 2.4, 2.4],
                               [18.5, 0, 0, 1.6, 1.6], [21.0, 0, 0, 1.2, 1.2], [21.0, 0, 0, 0.6, 0.6], [25.0, 0, 0, 0.2, 0.2]],
                     tubes=[[[0, 21.0, 0], [0, 24.2, 0], 0.55, "#c4a45c"], [[-1.6, 23.4, 0], [1.6, 23.6, 0], 0.25, "#c4a45c"]],
                     boxes=[[0, 4.0, 7.0, 3.0, 4.0, 3.0], [0, 4.0, -7.0, 3.0, 4.0, 3.0], [7.0, 4.0, 0, 3.0, 4.0, 3.0], [-7.0, 4.0, 0, 3.0, 4.0, 3.0]]))

# ------------------------------------------------------------------ ships
# OSM's hulls (building=ship, skipped by 04_buildings): the Cutty Sark (w25608663, 1869; 64.7 m, hull raised on
# its glazed dry-dock canopy, three masts ~46 m) and HMS Belfast (w5006061, 1938; 187 m, moored off the Pool,
# masts 41 m, Admiralty disruptive camouflage greys)


def hull(ring_ll, at, facing, y0, y1, colour):
    pts = [frame(en(lon, lat, at), facing) for lon, lat in ring_ll]
    from shapely.geometry import MultiPoint
    hull_ = MultiPoint(pts).convex_hull
    return [[[round(a, 2), round(b, 2)] for a, b in list(hull_.exterior.coords)[:-1]], y0, y1, colour]


cs = [(-0.009708, 51.483151), (-0.009731, 51.483076), (-0.009639, 51.482819), (-0.00953, 51.482602),
      (-0.009474, 51.482564), (-0.009419, 51.482579), (-0.009413, 51.482625), (-0.009501, 51.482843),
      (-0.009595, 51.483042), (-0.009671, 51.483129)]
cs_at = (float(np.mean([p[0] for p in cs])), float(np.mean([p[1] for p in cs])))
cs_face = bearing(cs[4], cs[0])                     # stern to bow (the bow points NNW, to the river)
L = float(np.linalg.norm(en(*cs[0], cs[4])))
# M10 fix round (critic: "its hull outline extruded as a Georgian terrace, three bare masts"): the dry dock's glazed
# canopy (OSM w969672514, 1,675 m2) is the landmark row "Cutty Sark dry dock" (pale glass, 2.8 m, no rooftops); here
# the black hull from the glass to 9.6 m with a gilt sheer line, a teak deck, three masts each with five yards
# (courses to royals), shrouds to the rails, the stays fore and aft and the bowsprit (photos cutty-sark/*)
GLASS_TOP, RAIL = 2.8, 9.6
hull_p = hull(cs, cs_at, cs_face, GLASS_TOP, RAIL, "#1b1d20")
cen_ = np.mean(hull_p[0], axis=0)
gilt_ring = [[round(float(cen_[0] + (x - cen_[0]) * 1.025), 2), round(float(cen_[1] + (z - cen_[1]) * 1.008), 2)] for x, z in hull_p[0]]
half_w = float(np.max(np.abs(np.array(hull_p[0])[:, 0])))
tubes = []
masts_ = ((0.28, 42.0), (0.02, 46.0), (-0.24, 36.0))
for k, (z, hm) in enumerate(masts_):
    zz = round(z * L, 2)
    tubes.append([[0, RAIL, zz], [0, hm, zz], 0.42 if k < 2 else 0.36, "#5e4f3c"])
    for f_, w in ((0.36, 10.5), (0.5, 9.0), (0.63, 7.6), (0.75, 6.0), (0.86, 4.4)):   # yards
        tubes.append([[-w, round(hm * f_, 2), zz], [w, round(hm * f_, 2), zz], 0.26, "#2c2620"])
    for sx in (-1, 1):                                                                   # shrouds
        for dz in (-2.2, 0.0, 2.2):
            tubes.append([[sx * (half_w - 0.6), RAIL, round(zz + dz - 1.5, 2)], [0, round(hm * 0.74, 2), zz], 0.1, "#2c2620"])
bow_z = round(0.5 * L, 2)
tubes.append([[0, RAIL, bow_z - 1.0], [0, 13.5, round(0.66 * L, 2)], 0.32, "#2c2620"])            # bowsprit
tubes.append([[0, 13.4, round(0.65 * L, 2)], [0, 40.0, round(0.28 * L, 2)], 0.12, "#2c2620"])      # forestays
tubes.append([[0, 40.0, round(0.28 * L, 2)], [0, 44.0, round(0.02 * L, 2)], 0.12, "#2c2620"])       # main topmast stay
tubes.append([[0, 30.0, round(0.28 * L, 2)], [0, 34.0, round(0.02 * L, 2)], 0.12, "#2c2620"])
tubes.append([[0, 44.0, round(0.02 * L, 2)], [0, 34.0, round(-0.24 * L, 2)], 0.12, "#2c2620"])      # mizzen stay
tubes.append([[0, 34.0, round(-0.24 * L, 2)], [0, RAIL, round(-0.48 * L, 2)], 0.12, "#2c2620"])     # backstay
blocks.append(figure("Cutty Sark", [round(cs_at[0], 7), round(cs_at[1], 7)], round(cs_face, 1), "#1b1d20", 46.0, variant=0.4,
                     prisms=[hull_p, [gilt_ring, 8.9, 9.25, "#c4a45c"], hull(cs, cs_at, cs_face, RAIL, RAIL + 0.3, "#7b5a3a")],
                     tubes=tubes,
                     note="the Cutty Sark (1869): black hull over its glazed dry dock, gilt sheer line, three masts with yards and rigging"))

hb = [(-0.080242, 51.506429), (-0.080533, 51.506513), (-0.081076, 51.506631), (-0.081625, 51.506725),
      (-0.082045, 51.506787), (-0.082345, 51.50681), (-0.082593, 51.506807), (-0.082382, 51.506709),
      (-0.081893, 51.506595), (-0.081122, 51.506435), (-0.080818, 51.506386), (-0.080257, 51.506324),
      (-0.080093, 51.506315), (-0.08003, 51.506335), (-0.080093, 51.506372)]
hb_at = (float(np.mean([p[0] for p in hb])), float(np.mean([p[1] for p in hb])))
bow, stern = (-0.08003, 51.506335), (-0.082593, 51.506807)
hb_face = bearing(stern, bow)
L = float(np.linalg.norm(en(*bow, stern)))
G1, G2, G3 = "#8b9297", "#5b646b", "#b9c0c4"
boxes = [[0, 9.0, 0.06 * L, 13.0, 4.0, 40.0, G1], [0, 13.5, 0.04 * L, 9.0, 5.0, 22.0, G2],     # superstructure
         [0, 17.5, 0.09 * L, 6.0, 3.0, 7.0, G3],                                                # the bridge
         [0, 14.0, -0.03 * L, 4.5, 8.0, 5.0, G1], [0, 14.0, -0.12 * L, 4.5, 8.0, 5.0, G1],     # funnels
         [0, 8.5, 0.27 * L, 7.0, 2.6, 8.0, G2], [0, 10.5, 0.2 * L, 7.0, 2.6, 8.0, G2],         # turrets A, B
         [0, 8.5, -0.3 * L, 7.0, 2.6, 8.0, G2], [0, 10.5, -0.23 * L, 7.0, 2.6, 8.0, G2]]       # X, Y
tubes = [[[0, 12.0, 0.12 * L], [0, 41.0, 0.12 * L], 0.4, G2], [[0, 12.0, -0.07 * L], [0, 34.0, -0.07 * L], 0.35, G2]]
for z in (0.27, 0.2, -0.3, -0.23):
    for x in (-1.6, 0.0, 1.6):
        s = 1 if z > 0 else -1
        y = 8.5 if abs(z) > 0.25 else 10.5
        tubes.append([[x, y, round(z * L, 2)], [x, y + 0.6, round((z + s * 0.08) * L, 2)], 0.22, G2])
blocks.append(figure("HMS Belfast", [round(hb_at[0], 7), round(hb_at[1], 7)], round(hb_face, 1), G1, 41.0, variant=0.4,
                     prisms=[hull(hb, hb_at, hb_face, 0.0, 4.5, "#6a7177"), hull(hb, hb_at, hb_face, 4.5, 7.0, G3)],
                     boxes=boxes, tubes=tubes, floor=2.7))

# ------------------------------------------------------------------ M10 fix round: landmark chips
# (critic round 1: "chips landing on generic boxes"); the outlines these stand on or replace are dropped or recoloured
# by their landmark_facades.csv rows (h@...=0, near)
B10 = gpd.read_file(DATA / "buildings.gpkg").to_crs(32630)


def ll_of(xy):
    q = gpd.GeoSeries(gpd.points_from_xy([xy[0]], [xy[1]]), crs=32630).to_crs(4326).iloc[0]
    return [round(q.x, 7), round(q.y, 7)]


def rect_frame(g):
    """A footprint's minimum rotated rectangle: centre (UTM), facing (its long axis, 0-180), half long, half short."""
    q = np.array(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [q[1] - q[0], q[2] - q[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    fac = math.degrees(math.atan2(e[i][0], e[i][1])) % 180
    return np.array(g.minimum_rotated_rectangle.centroid.coords[0]), fac, float(np.hypot(*e[i])) / 2, float(np.hypot(*e[1 - i])) / 2


# the Albert Memorial (1872, Gilbert Scott): OSM's outline (w372965957, an unnamed 117 m2 'house' at 9.6 m) dropped by
# its row; the granite steps (a 40 m square in three flights), the marble podium with the Parnassus frieze, four
# clustered piers under a gabled canopy, the gilt-and-enamel spire to 54 m (list: 53.6) with its cross, the gilt
# seated Prince under the canopy facing south to the Royal Albert Hall (photos albert-memorial, est. proportions)
am_ = B10[B10.osm_id == "w372965957"]
if len(am_):
    am_c = np.array(am_.geometry.iloc[0].centroid.coords[0])
    am_at = ll_of(am_c)
    GRAN, MARB, CAN, SPIRE = "#a9a59d", "#dcd7cb", "#cfc8b9", "#8c7a4c"
    prisms = [[square(20.0), 0.0, 1.0, GRAN], [square(16.5), 1.0, 2.0, GRAN], [square(13.0), 2.0, 3.0, GRAN],
              [square(9.6), 3.0, 7.2, MARB], [square(10.0), 7.2, 7.8, MARB]]
    tubes = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            prisms.append([[[sx * 6.2 + a, sz * 6.2 + b] for a, b in square(1.3)], 7.8, 17.5, CAN])
            tubes.append([[sx * 6.9, 17.5, sz * 6.9], [sx * 6.9, 25.5, sz * 6.9], 0.45, "#c4a45c"])   # corner pinnacles
    prisms.append([square(7.8), 17.5, 20.5, CAN])                               # the canopy's entablature
    boxes = [[0, 9.6, 0, 2.6, 3.6, 3.0, "#c4a45c"], [0, 8.2, 0, 3.6, 0.8, 3.6, MARB]]   # the Prince on his plinth
    gab = [[-7.8, 20.5], [7.8, 20.5], [0, 26.5]]
    blocks.append(figure("Albert Memorial", am_at, 180.0, SPIRE, 54.0, variant=0.5, prisms=prisms, tubes=tubes, boxes=boxes,
                         slabs=[[gab, -7.8, 7.8, "#7d838a"]], segments=8,
                         sections=[[20.0, 0, 0, 4.8, 4.8], [26.0, 0, 0, 4.4, 4.4], [27.5, 0, 0, 3.6, 3.6], [33.0, 0, 0, 3.2, 3.2],
                                   [33.0, 0, 0, 2.5, 2.5], [38.0, 0, 0, 2.2, 2.2], [46.0, 0, 0, 1.0, 1.0], [51.5, 0, 0, 0.35, 0.35],
                                   [54.0, 0, 0, 0.06, 0.06]],
                         note="the Albert Memorial (1872): steps, podium, canopy on four piers, gilt spire to 54 m (M10 fix round)"))
    blocks.append(figure("Albert Memorial gables", am_at, 270.0, "#7d838a", 26.5, variant=0.5,
                         slabs=[[gab, -7.8, 7.8, "#7d838a"]]))
    tubes = [[[0, 51.0, 0], [0, 54.6, 0], 0.18, "#c4a45c"], [[-1.0, 53.6, 0], [1.0, 53.6, 0], 0.15, "#c4a45c"]]
    blocks.append(figure("Albert Memorial cross", am_at, 180.0, "#c4a45c", 54.6, variant=0.5, tubes=tubes))

# the Royal Albert Hall (1871): the frieze (buff terracotta, 'A Tribute to the Arts and Sciences', 1.8 m) round the
# outer drum under its cornice (OSM's 25 m ring part), an ellipse fitted to that part's rotated rectangle; the table
# makes the walls blank red brick (monument 0.72) and the drum over 25 m the glazed dome (crown@25-43.8)
rah = B10[(B10.name == "Royal Albert Hall") & ((B10.h - 25.0).abs() < 0.3)]
if len(rah):
    g = rah.geometry.iloc[rah.area.argmax()]
    c_, fac, hl, hs = rect_frame(Polygon(g.exterior) if g.geom_type == "Polygon" else g.convex_hull)
    rb = float(rel_base([g], c_)[0])
    y0, y1 = round(rb + 21.2, 2), round(rb + 23.0, 2)
    blocks.append(figure("Royal Albert Hall frieze", ll_of(c_), round(fac, 1), "#d2b48c", 25.0, variant=0.4, segments=48,
                         sections=[[y0, 0, 0, round(hs + 0.3, 2), round(hl + 0.3, 2)], [y1, 0, 0, round(hs + 0.3, 2), round(hl + 0.3, 2)]],
                         note="the Royal Albert Hall's buff frieze round the drum (M10 fix round)"))

# Tate Modern's chimney (99 m): the table cuts it to 93 m and makes it windowless brick (crown@25-93); its top the
# translucent light box (Michael Craig-Martin's 'Swiss Light', 2000), 6 m of pale glass
tc = B10[(B10.name == "Tate Modern (Bankside Power Station chimney)") & ((B10.h - 99.0).abs() < 0.3)]
if len(tc):
    g = tc.geometry.iloc[0]
    c_, fac, hl, hs = rect_frame(g)
    rb = float(rel_base([g], c_)[0])
    blocks.append(figure("Tate Modern chimney light box", ll_of(c_), round(fac, 1), "#dfe3dc", 99.0, variant=0.5,
                         boxes=[[0, round(rb + 96.0, 2), 0, round(2 * hs - 0.4, 2), 6.0, round(2 * hl - 0.4, 2), "#dfe3dc"]],
                         note="Tate Modern: the chimney's light box (M10 fix round)"))

# the British Museum: the Great Court's glazed roof (Foster, 2000; 3,312 panes on a steel lattice) over the court (OSM's
# 3.5 m floor part, 5,139 m2) from its walls' tops (20 m) and the Reading Room (1857) in the middle: its drum (the
# 20 m part, 1,548 m2) rises through the glass to a lead-blue dome and a lantern (to 37 m; OSM's lifted 32-37 m part
# is dropped by the row)
bm = B10[B10.name == "British Museum"]
court = bm[((bm.h - 3.5).abs() < 0.3) & (bm.area > 4000)]
rr = bm[((bm.h - 20.0).abs() < 0.3) & ((bm.area - 1548).abs() < 60)]
if len(court) and len(rr):
    cg = court.geometry.iloc[0]
    cpoly = Polygon(cg.exterior) if cg.geom_type == "Polygon" else cg.convex_hull
    rg = rr.geometry.iloc[0]
    rc = np.array(rg.centroid.coords[0])
    rrad = math.sqrt(rg.area / math.pi)
    rb = float(rel_base([rg], rc)[0])
    at_bm = ll_of(rc)
    ring_ = [[round(float(x - rc[0]), 2), round(float(y - rc[1]), 2)] for x, y in list(cpoly.exterior.coords)[:-1]]
    GL, RIB = "#b7c3c8", "#e4e6e3"
    prisms = [[ring_, round(rb + 20.6, 2), round(rb + 21.1, 2), GL]]
    tubes = []
    from shapely.geometry import LineString as _LS
    cpl = cpoly.buffer(-0.4)
    for ang in (45.0, -45.0):
        d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        nrm = np.array([-d[1], d[0]])
        for off in np.arange(-110, 110, 4.0):
            ln = _LS([rc + nrm * off - d * 200, rc + nrm * off + d * 200]).intersection(cpl)
            for seg in getattr(ln, "geoms", [ln]):
                if seg.is_empty or seg.length < 2 or seg.geom_type != "LineString":
                    continue
                (x0, y0_), (x1, y1_) = seg.coords[0], seg.coords[-1]
                tubes.append([[round(x0 - rc[0], 2), round(rb + 21.15, 2), round(y0_ - rc[1], 2)],
                              [round(x1 - rc[0], 2), round(rb + 21.15, 2), round(y1_ - rc[1], 2)], 0.14, RIB])
    blocks.append(figure("British Museum Great Court roof", at_bm, 0.0, GL, 21.3, variant=0.4, prisms=prisms, tubes=tubes,
                         note=f"the British Museum's Great Court roof ({len(tubes)} lattice ribs) (M10 fix round)"))
    blocks.append(figure("British Museum Reading Room", at_bm, 0.0, "#6f7d86", 37.0, variant=0.4, segments=32,
                         prisms=[[ring(rrad + 0.2, 32), round(rb + 19.0, 2), round(rb + 24.5, 2), "#d3cdbf"]],
                         sections=[[round(rb + 24.5, 2), 0, 0, rrad - 0.3, rrad - 0.3], [round(rb + 27.0, 2), 0, 0, rrad * 0.93, rrad * 0.93],
                                   [round(rb + 30.0, 2), 0, 0, rrad * 0.74, rrad * 0.74], [round(rb + 32.5, 2), 0, 0, rrad * 0.45, rrad * 0.45],
                                   [round(rb + 33.6, 2), 0, 0, 3.4, 3.4], [round(rb + 36.0, 2), 0, 0, 3.0, 3.0], [round(rb + 37.0, 2), 0, 0, 0.3, 0.3]]))

# Piccadilly Circus: the Shaftesbury Memorial Fountain (1893; OSM w583928480, an 18 m2 'shed' dropped by its row):
# a bronze octagonal fountain on stepped granite in its basin, Anteros (aluminium) on top at ~10 m (est. from photos);
# the Piccadilly Lights: the curved LED screens on the Monico building's corner over the circus (w153661809), here a
# band of flat panels 12-22 m up along the face nearest the fountain, in advert colours (invented: they change)
sf = B10[B10.osm_id == "w583928480"]
if len(sf):
    c_ = np.array(sf.geometry.iloc[0].centroid.coords[0])
    BR, AL = "#5e4b36", "#c9ccc8"
    blocks.append(figure("Shaftesbury Memorial Fountain", ll_of(c_), 0.0, BR, 10.2, variant=0.5, segments=8,
                         prisms=[[ring(4.6, 8), 0.0, 0.5, "#9a958c"], [ring(3.6, 8), 0.5, 1.1, "#9a958c"], [ring(2.6, 8), 1.1, 1.7, "#9a958c"]],
                         sections=[[1.7, 0, 0, 1.6, 1.6], [3.2, 0, 0, 1.2, 1.2], [3.6, 0, 0, 2.0, 2.0], [4.1, 0, 0, 1.1, 1.1],
                                   [6.4, 0, 0, 0.6, 0.6], [7.0, 0, 0, 0.9, 0.9], [7.4, 0, 0, 0.3, 0.3]],
                         tubes=[[[0, 7.3, 0], [0, 9.6, 0], 0.32, AL], [[0, 9.2, 0], [0.9, 10.2, 0.2], 0.12, AL], [[-1.0, 9.0, 0], [0.7, 9.4, 0], 0.08, AL]],
                         note="Piccadilly Circus: the Shaftesbury Memorial Fountain with Anteros (M10 fix round)"))
    mo = B10[B10.osm_id == "w153661809"]
    if len(mo):
        g = mo.geometry.iloc[0]
        g = max(getattr(g, "geoms", [g]), key=lambda q: q.area)
        ring_ = np.array(g.exterior.coords)
        if not g.exterior.is_ccw:
            ring_ = ring_[::-1]                                        # counter-clockwise: outward is the right of each edge
        cols = ["#c8202a", "#1d3f9c", "#f0f0ee", "#f2b51b", "#18a0d8", "#d4246e", "#2fa34a", "#f0f0ee"]
        prisms, k = [], 0
        for a_, b_ in zip(ring_[:-1], ring_[1:]):
            L_ = float(np.hypot(*(b_ - a_)))
            if L_ < 2.0 or float(np.hypot(*((a_ + b_) / 2 - c_))) > 47.0:
                continue
            u = (b_ - a_) / L_
            n_ = np.array([u[1], -u[0]])
            q = [a_ + n_ * 0.3, b_ + n_ * 0.3, b_ + n_ * 0.8, a_ + n_ * 0.8]
            prisms.append([[[round(float(v[0] - c_[0]), 2), round(float(v[1] - c_[1]), 2)] for v in q], 5.5, 16.0, cols[k % len(cols)]])
            k += 1
        blocks.append(figure("Piccadilly Lights", ll_of(c_), 0.0, "#1d3f9c", 16.0, variant=0.5, prisms=prisms,
                             note=f"Piccadilly Circus: the Lights round the Monico building's corner ({k} panels, colours invented)"))

# ------------------------------------------------------------------ write the generated include file
out = HERE / "generated" / "structures-m4h.toml"
out.parent.mkdir(exist_ok=True)
out.write_text("# Generated by scripts/m4h_structures.py: do not edit (edit the script and run it again).\n"
               "# city.toml's `include` list lays this file under its own settings; the [[structures]] below are\n"
               "# in the order the script builds them.\n" + "\n".join(blocks))
print(f"{len(blocks)} structures written to {out}")
