"""M4 (landmarks, builder b-tk-m4l): Tokyo's landmarks the building table can't draw, as [[structures]] figures
written to generated/structures-m4l.toml (city.toml `include`s it; re-run after editing the numbers here, then
06_tiles and 07_pack). Run from demos/tokyo: `uv run python scripts/m4l_structures.py`.

Positions and plans from OSM (cached by this script's helper in <data>/m4l/osm.json from the local Overpass), heights
from data/landmarks_tokyo.csv and the operators, shapes and colours from photos (data/landmarks_m4l.md). The table's
own pieces these replace are left out in city.toml [buildings.exclude] (scripts/m2_fixes.py EXCLUDE_GML).
"""
import json
import math
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "tokyo"
OUT = HERE / "generated" / "structures-m4l.toml"
UTM = 32654
TO_UTM = Transformer.from_crs(4326, UTM, always_xy=True)
TO_LL = Transformer.from_crs(UTM, 4326, always_xy=True)
OSM = json.loads((DATA / "m4l" / "osm.json").read_text())


class LL(list):
    """A [lon, lat] pair, written with 7 decimals (arr() rounds other numbers to 3: M4 fix round, the figures stood up
    to ~60 m off their places, Docomo's spire beside its body)"""


def ll(p):
    lon, lat = TO_LL.transform(float(p[0]), float(p[1]))
    return LL([round(lon, 7), round(lat, 7)])


def utm(lon, lat):
    return np.array(TO_UTM.transform(lon, lat))


def f(x):
    return f"{x:.10g}" if isinstance(x, float) else str(x)


def arr(v):
    if isinstance(v, LL):
        return "[" + ", ".join(f"{x:.7f}" for x in v) + "]"
    if isinstance(v, (list, tuple, np.ndarray)):
        return "[" + ", ".join(arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {arr(x)}" for k, x in v.items()) + " }"
    if isinstance(v, bool):
        return "true" if v else "false"
    return f(round(float(v), 3))


def frame_of(facing):
    az = math.radians(facing)
    fwd = np.array([math.sin(az), math.cos(az)])
    return np.array([fwd[1], -fwd[0]]), fwd


def local(p, origin, facing=0.0):
    """UTM point p in a figure's frame (x right, z forward) at origin facing `facing`."""
    right, fwd = frame_of(facing)
    d = np.asarray(p, float) - origin
    return [round(float(d @ right), 3), round(float(d @ fwd), 3)]


def way(k):
    return np.array([TO_UTM.transform(*p) for p in OSM[k]["geom"]])[:-1]


def ring(r, n=8, phase=None, cx=0.0, cz=0.0):
    phase = math.pi / n if phase is None else phase
    return [[round(cx + r * math.cos(phase + 2 * math.pi * i / n), 3), round(cz + r * math.sin(phase + 2 * math.pi * i / n), 3)]
            for i in range(n)]


def square(h, cx=0.0, cz=0.0):
    return [[cx - h, cz - h], [cx + h, cz - h], [cx + h, cz + h], [cx - h, cz + h]]


def rectangle(hx, hz, cx=0.0, cz=0.0):
    return [[cx - hx, cz - hz], [cx + hx, cz - hz], [cx + hx, cz + hz], [cx - hx, cz + hz]]


def ground(p):
    global _T
    if "_T" not in globals():
        from city3d.common import Terrain
        _T = Terrain()
    return float(_T.height_utm([p[0]], [p[1]])[0])


blocks, tri_est = [], {}


def emit(kind, name, keys, note=None):
    out = [f"# {line}" for line in (note or "").split("\n") if note]
    out += ["[[structures]]", f'kind = "{kind}"', f'name = "{name}"']
    for k, v in keys.items():
        if v is None:
            continue
        if k in ("sections", "tubes", "boxes", "prisms", "slabs", "wedges", "legs", "faces", "belts", "floors", "railings",
                 "frustums", "colours") and isinstance(v, list):
            out.append(f"{k} = [" + ",\n    ".join(arr(x) for x in v) + "]")
        else:
            out.append(f"{k} = {arr(v)}")
    blocks.append("\n".join(out) + "\n")


def figure(name, at_utm, facing=0.0, colour="#b0b0b0", top=None, style="plain", variant=0.5, base=0.0,
           sections=None, tubes=None, boxes=None, prisms=None, slabs=None, wedges=None, walls=False, segments=None, note=None):
    ys = [s[0] for s in sections or []] + [p[2] for p in prisms or []] + [b[1] + b[4] / 2 for b in boxes or []] \
        + [max(t[0][1], t[1][1]) for t in tubes or []] + [max(q[2] for q in w[0]) for w in wedges or []]
    top = top or max(ys + [1.0])
    seg = int(segments or 16)
    n = (2 * seg * max(0, len(sections or []) - 1) + 80 * len(tubes or []) + 12 * len(boxes or [])
         + sum(4 * len(p[0]) - 4 for p in prisms or []) + sum(4 * len(s[0]) - 4 for s in slabs or [])
         + sum(4 * len(w[0]) - 4 for w in wedges or []))
    tri_est[name] = tri_est.get(name, 0) + n
    keys = {"at": ll(at_utm), "facing": round(float(facing), 2), "style": style, "variant": variant, "colour": colour,
            "top": round(float(top), 2)}
    if abs(base) > 1e-3:
        keys["base"] = round(float(base), 2)
    if walls:
        keys["walls"] = True
    if segments:
        keys["segments"] = int(segments)
    for k, v in (("sections", sections), ("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs),
                 ("wedges", wedges)):
        if v:
            keys[k] = v
    emit("figure", name, keys, note)


def chain(pts, r, colour=None):
    out = []
    for a, b in zip(pts, pts[1:]):
        t = [[round(float(v), 2) for v in a], [round(float(v), 2) for v in b], r]
        if colour:
            t.append(colour)
        out.append(t)
    return out


def outline(k, c, facing):
    return [local(q, c, facing) for q in way(k)]


# ================================================================== Tokyo Tower
# 333 m (1958). Plan from OSM's 3D mapping (data/landmarks_m4l.md §1): the legs' feet (w1244967004-07, 9 m squares,
# centres ~82 m apart), the arches joining the legs at 40 m, the tower's square cross-section at 53, 66, 77, 88, 97,
# 106, 120, 161, 188 and 217 m (the pyramidal "roof" rings r17133569-78; sides on a bearing of 34.7 deg; their common
# centre 1.3 m east, 1.2 m north of the CSV point); the Main Deck (w313815246: a ~35 m chamfered square, its two floors
# between 120 and 130 m over the ground: OSM and a photo's scale agree; the brochure's "150 m" counts from sea level
# less a few metres), the Top Deck (w313815247 and its drums, 217-251 m), the 4 m gain tower over it (OSM 251-333 m).
# The paint (JA Wikipedia): above the Main Deck seven equal bands, international orange and white, orange at both ends
# (since 1986; 11 before); below it all orange, the deck's sides white since 1998. Colours sampled from Commons photos
TT_C = utm(139.74543, 35.65858) + np.array([1.3, 1.2])
TT_F = 34.7
ORANGE, WHITE, GLASS = "#e05023", "#f2ece1", "#3f474e"
TT_BAND0, TT_BAND = 131.0, (333.0 - 131.0) / 7
TT_WHITE = [(TT_BAND0 + k * TT_BAND, TT_BAND0 + (k + 1) * TT_BAND) for k in (1, 3, 5)]


def tt_paint(y):
    return WHITE if any(a <= y < b for a, b in TT_WHITE) else ORANGE


def tt_colours():
    stops, eps = [[0.0, ORANGE]], 0.01
    for a, b in TT_WHITE:
        stops += [[a - eps, ORANGE], [a, WHITE], [b - eps, WHITE], [b, ORANGE]]
    return stops + [[333.0, ORANGE]]


DECK = [[round(x, 2), round(z, 2)] for x, z in outline("w313815246", TT_C, TT_F)]
# (fix round, the user 7 Oct: the legs' curve kinked at the Main Deck; the real silhouette is one continuous concave curve
# from the feet to the Top Deck) the outer half-widths of OSM's sections, fitted by one smooth curve (log width a cubic
# in height, the feet and the Top Deck held): within 1.5 m of every section; the inner edges keep each section's
# member depth
_TY = np.array([0, 20, 40, 53, 66, 77, 88, 97, 106, 120, 130, 161, 188, 217.0])
_TW = np.array([45.5, 34.5, 26.0, 20.7, 16.75, 15.35, 13.95, 12.5, 11.15, 9.7, 9.0, 7.55, 5.85, 4.1])
_TC = np.polyfit(_TY, np.log(_TW), 3, w=np.where((_TY == 0) | (_TY == 217), 8.0, 1.0))


def tt_smooth(prof):
    return [[y, round(float(np.exp(np.polyval(_TC, y))), 2), round(float(np.exp(np.polyval(_TC, y))) - (o - i), 2)]
            for y, o, i in prof]
# the gain tower (4 m square) in its bands, the antenna over it
gain = []
for y0, y1 in ((251.0, TT_WHITE[1][1]), (TT_WHITE[1][1], TT_WHITE[2][0]), (TT_WHITE[2][0], TT_WHITE[2][1]), (TT_WHITE[2][1], 311.0)):
    gain.append([square(2.0), round(y0, 2), round(y1, 2), tt_paint(0.5 * (y0 + y1))])
emit("lattice_tower", "Tokyo Tower", {
    "at": ll(TT_C), "facing": TT_F, "height": 333.0, "style": "floodlit", "variant": 0.6,
    "colours": tt_colours(), "colour": ORANGE, "segment": 3.0,
    # four legs to ~100 m, then one square shaft (its edges the legs' chords); [y, outer, inner] half-widths
    "legs": [{"profile": tt_smooth([[0, 45.5, 36.5], [20, 34.5, 26.0], [40, 26.0, 18.0], [53, 20.7, 12.8], [66, 16.75, 9.4],
                                    [77, 15.35, 7.6], [88, 13.95, 6.0], [97, 12.5, 5.0]]), "chord": 0.12},
             {"profile": tt_smooth([[97, 12.5, 10.6], [106, 11.15, 9.5], [120, 9.7, 8.3], [130, 9.0, 7.7], [161, 7.55, 6.4],
                                    [188, 5.85, 5.0], [217, 4.1, 3.4]]), "chord": 0.14}],
    "faces": [[40, 97], [97, 217]],
    # (fix round 2: the arches sprang at 20 m, FootTown's roof, so on the east and west faces they sat on it; photos
    # put the springing a few metres above the roof plaza's railings)
    "arches": {"spring": 23.0, "crown": 35.0, "rib": 2.2, "depth": 1.2, "inset": 0.6, "top": 40.0, "period": 2.0},
    "belts": [[117.5, 119.0, 12.5, 1.4, ORANGE]],
    "floors": [[119.0, 12.5, 5.0, 0.8, "#8a8a86"]],
    "prisms": [[DECK, 119.0, 121.0, WHITE], [DECK, 121.0, 124.6, GLASS], [DECK, 124.6, 125.8, WHITE],
               [DECK, 125.8, 129.4, GLASS], [DECK, 129.4, 131.0, WHITE],
               [ring(6.0, 16), 217.0, 241.0, WHITE], [ring(6.3, 16), 241.0, 246.0, GLASS],
               [ring(6.5, 16), 246.0, 251.0, ORANGE]] + gain,
    "tubes": [[[0, 311, 0], [0, 322, 0], 0.8, ORANGE], [[0, 322, 0], [0, 333, 0], 0.45, ORANGE]],
}, note="Tokyo Tower (1958): 333 m, a lattice tower (Paris's lattice_tower kind); plan from OSM's 3D mapping, the decks\n"
        "from OSM w313815246/w313815247, the paint from JA Wikipedia and Commons photos (scripts/m4l_structures.py)")
# FootTown: the 4-storey building between the legs (OSM r4247313 on outline w30526374, 20 m; PLATEAU's piece, which
# also held the lattice, is left out). Fix round 2 (the user, 8 Oct: the tower stood on a windowed office block): photos
# (Commons BaseofTokyoTower.JPG, TokyoTowerashi.jpg, Tokyo_Tower_2024.jpg; data/landmarks_m4l.md §1) show a box clad in
# dark mauve-brown panels (JA: 濃いブラウン since 2005; sampled #4d4443 overcast, #b28269 in low winter sun) with almost
# no windows, a thin pale line under the parapet, plant and a railed roof plaza on top; the legs come down OUTSIDE its
# corners onto sloped granite pedestals (OSM's 7 m leg ways, data/landmark_facades.csv), the arches springing from the
# legs a little above its roof. So: the panel style (seams, a rare glass strip), the outline notched where a leg's
# section passes between 0 and 20 m (its SE corner reached into the leg), the pale band, the roof plant.
TT_LEG_IN = 23.5          # the legs' inner half-width at the roof (20 m: 24.0, tt_smooth) less a little: no wall in a leg
_ft = Polygon(outline("w30526374", TT_C, TT_F))
for sx in (-1, 1):
    for sz in (-1, 1):
        _ft = _ft.difference(Polygon(rectangle(30, 30, sx * (TT_LEG_IN + 30), sz * (TT_LEG_IN + 30))))
FT = [[round(x, 2), round(z, 2)] for x, z in list(_ft.exterior.coords)[:-1]]
FT_BAND = [[round(x, 2), round(z, 2)] for x, z in list(_ft.buffer(0.15, join_style=2).exterior.coords)[:-1]]
figure("Tokyo Tower FootTown", TT_C, TT_F, "#6b5450", 20.0, style="panel", walls=True,
       prisms=[[FT, 0.0, 20.0], [FT_BAND, 17.6, 18.0, "#cfcac2"]],
       boxes=[[-14.0, 21.6, 2.0, 14.0, 3.2, 9.0, "#8d8781"], [12.0, 21.2, -12.0, 9.0, 2.4, 6.0, "#9a958f"],
              [24.0, 21.4, 12.0, 6.0, 2.8, 5.0, "#8d8781"]],
       note="FootTown (OSM r4247313, 20 m), under Tokyo Tower's legs: dark mauve-brown panels, few windows, a pale line\n"
            "under the parapet, roof plant; notched clear of the legs (fix round 2: it read as a pale office block)")

# ================================================================== Tokyo Skytree
# 634 m (2012). The shaft's section an equilateral triangle at the foot (OSM w557938593: side 66 m, circumradius
# 38 m) turning into a circle by 320 m (JA Wikipedia; the triangle's sides bow out, its corners recede); the Tembo
# Deck 340-350 m, the Tembo Galleria 445-451 m, the gain tower (antenna mast, ~8 m) from 497 m to the tip; widths
# measured on calibrated photos (OSM's deck parts, 35 and 27 m, are the decks' cores). "Skytree white" (aijiro, a very pale blue-white)
SK = way("w557938593")
SK_C = SK.mean(0)
v0 = SK[int(np.argmax(np.hypot(*(SK - SK_C).T)))] - SK_C
SK_PH = math.atan2(*local(SK_C + v0, SK_C)[::-1])        # the first corner's angle in the frame
SKW, SKG, SKD = "#e6eef2", "#3b444c", "#c9d0d4"


def sk_r(y):
    """The shaft's circumradius (triangle) / radius (circle) at height y."""
    # (the silhouette measured on two calibrated Asakusa photos, data/landmarks_m4l.md §2: ~58 m wide at 95 m,
    # 38.5 m at 306 m, 31-36 m between the decks)
    ys = [0, 40, 95, 185, 246, 276, 306, 320, 372, 430, 440, 460, 497]
    rs = [38.0, 34.5, 30.0, 25.0, 22.0, 20.8, 19.3, 19.0, 18.0, 16.0, 16.0, 12.0, 11.5]
    return float(np.interp(y, ys, rs))


def sk_ring(y, n=36):
    t = min(1.0, (y / 320.0)) ** 0.8
    R = sk_r(y)
    pts = []
    for i in range(n):
        th = SK_PH + 2 * math.pi * i / n
        a = ((th - SK_PH) % (2 * math.pi / 3)) - math.pi / 3
        tri = R * 0.5 / math.cos(a)
        r = (1 - t) * tri + t * R
        pts.append([round(r * math.cos(th), 2), round(r * math.sin(th), 2)])
    return pts


prisms = []
ys = list(np.arange(0.0, 306.0, 10.0)) + [306.0]
for y0, y1 in zip(ys, ys[1:]):
    r0 = sk_ring(y0)
    k = sk_r(y1) / sk_r(y0) if y1 >= 320 else None
    # (a prism's top scale only shrinks; the shape change between slabs is 1-2 % per 10 m: invisible)
    prisms.append([r0, round(y0, 2), round(y1, 2), SKW, round(sk_r(y1) / sk_r(y0), 4)])
# the Tembo Deck (~68 m across, measured on photos; OSM's 35 m part is its core): a flared underside, three glazed
# floors 340-350 m with white bands, a sloped white roof; the Tembo Galleria (~43 m) at 445-451 m the same way
prisms += [[ring(19.3, 48, 0.0), 306.0, 318.0, SKW, round(23.0 / 19.3, 4)],
           [ring(23.0, 48, 0.0), 318.0, 330.0, SKW, round(27.0 / 23.0, 4)],
           [ring(27.0, 48, 0.0), 330.0, 339.0, SKW, round(32.5 / 27.0, 4)],
           [ring(34.0, 48, 0.0), 339.0, 340.2, SKW], [ring(33.6, 48, 0.0), 340.2, 345.0, SKG],
           [ring(34.0, 48, 0.0), 345.0, 346.0, SKW], [ring(33.6, 48, 0.0), 346.0, 354.0, SKG],
           [ring(34.0, 48, 0.0), 354.0, 357.0, SKW], [ring(30.0, 48, 0.0), 357.0, 366.0, SKW, 0.6],
           [ring(18.0, 36, 0.0), 366.0, 436.0, SKW, round(16.0 / 18.0, 4)],
           [ring(16.0, 36, 0.0), 436.0, 442.0, SKW, round(21.5 / 16.0, 4)],
           [ring(21.5, 36, 0.0), 442.0, 443.2, SKW], [ring(21.2, 36, 0.0), 443.2, 451.5, SKG],
           [ring(21.5, 36, 0.0), 451.5, 456.0, SKW, 0.62],
           [ring(12.0, 36, 0.0), 456.0, 497.0, SKW, 0.96]]
# the gain tower: a lattice mast (white) stepping in, the antennas at its top (grey)
secs = [[497.0, 0, 0, 4.0, 4.0], [598.0, 0, 0, 3.8, 3.8], [600.0, 0, 0, 6.2, 6.2], [628.0, 0, 0, 6.0, 6.0],
        [630.0, 0, 0, 1.0, 1.0], [634.0, 0, 0, 0.3, 0.3]]
# the shaft's steel lattice (the diagonal tubes of its faces) through the `lattice` style's diamond cells on the
# shaft's walls (its own figure), the decks and the gain tower plain white
shaft = [p_ for p_ in prisms if p_[3] == SKW and (p_[2] <= 306.0 or (366.0 <= p_[1] < 437.0) or p_[1] >= 456.0)]
bulbs = [p_ for p_ in prisms if not any(p_ is q for q in shaft)]
figure("Tokyo Skytree shaft", SK_C, 0.0, "#cfd8de", 497.0, style="lattice", variant=0.5, walls=True, prisms=shaft,
       note="Tokyo Skytree: its shaft, in the lattice style (diamond steel cells)")
figure("Tokyo Skytree", SK_C, 0.0, SKW, 634.0, style="plain", variant=0.5, prisms=bulbs, sections=secs, segments=16,
       note="Tokyo Skytree (2012): 634 m; the shaft's section from OSM's base triangle (w557938593) to a circle at 320 m,\n"
            "the decks' rings from OSM (w362351415, w288269148), the gain tower from 497 m (PLATEAU's two prisms left out)")

# ================================================================== Rainbow Bridge
# 798 m suspension bridge (1993), main span 570 m, towers 126 m. OSM maps each tower's two legs (6 x 6 m: w1348279695/
# 96 east, w1348279698/1700 west) and its beams at 27-31 and 117-126 m; the Daiba anchorage (w1348279690-93: 30-60 m;
# Shibaura's is PLATEAU's own). Two cable planes on the legs' line (32.3 m apart); the decks are 05b_roads' ([roads]
# decks: the Shuto upper deck, the general road, Yurikamome and promenades below)
W_LEGS = [utm(139.760156, 35.637366), utm(139.760285, 35.637637)]
E_LEGS = [utm(139.766019, 35.635502), utm(139.766149, 35.635773)]
TW, TE = np.mean(W_LEGS, 0), np.mean(E_LEGS, 0)
LEG = float(np.hypot(*(E_LEGS[1] - E_LEGS[0]))) / 2
AN = way("w1348279691").mean(0)
side = float(np.hypot(*(AN - TE)))
emit("suspension", "Rainbow Bridge", {
    "towers": [ll(TW), ll(TE)],
    "tower": {"width": 2 * LEG + 8.0, "depth": 9.0, "height": 126.0, "pier": 4.0, "columns": [-LEG, LEG],
              "column_width": 7.0, "column_depth": 9.0, "column_top": 6.0, "cap": 9.0, "style": "spire",
              "colour": "#e9ebea", "pier_colour": "#b9b6ae"},
    "cables": {"across": [-LEG, LEG], "low": 69.0, "side": round(side, 1), "anchor": 52.0, "radius": 0.55,
               "below_top": 2.0, "colour": "#dcdedd", "deck": 56.0, "hangers": 12.0},
    "anchorage": {"length": 45.5, "width": 68.8, "height": 45.0, "colour": "#d0d2d4", "which": [1]},
}, note="Rainbow Bridge (1993): 126 m towers on OSM's leg parts, 570 m main span, cables to the Daiba anchorage;\n"
        "the Shibaura anchorage is PLATEAU's building (its decks: [roads] decks)")
# the towers' lower beams (27-31 m, OSM w1348279697/99): under the decks
for name, legs in (("Rainbow Bridge west tower beam", W_LEGS), ("Rainbow Bridge east tower beam", E_LEGS)):
    c = np.mean(legs, 0)
    d = legs[1] - legs[0]
    fac = math.degrees(math.atan2(d[0], d[1])) + 90.0
    figure(name, c, fac, "#e9ebea", 31.0, style="spire", boxes=[[0, 29.0, 0, 9.0, 4.0, 2 * LEG]])

# ================================================================== masts
def lattice_mast(name, c, facing, y0, y1, w0, w1, bands, note=None, tip=None, base=0.0):
    """A square lattice mast: four corner posts tapering from w0 to w1 (half-widths), X-bracing on each face every
    ~6 m, painted in `bands` [(y, colour), ...] (the colour from that height up); a thin antenna to `tip`."""
    col = lambda y: [cc for yy, cc in bands if yy <= y][-1]
    tubes = []
    ys = list(np.linspace(y0, y1, max(2, int((y1 - y0) / 6)) + 1))
    hw = lambda y: w0 + (w1 - w0) * (y - y0) / (y1 - y0)
    for (sx, sz) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        for a, b in zip(ys, ys[1:]):
            tubes.append([[sx * hw(a), a, sz * hw(a)], [sx * hw(b), b, sz * hw(b)], 0.45, col(0.5 * (a + b))])
    for a, b in zip(ys, ys[1:]):
        for k in range(4):
            p0 = [(-1, -1), (1, -1), (1, 1), (-1, 1)][k]
            p1 = [(-1, -1), (1, -1), (1, 1), (-1, 1)][(k + 1) % 4]
            cl = col(0.5 * (a + b))
            tubes.append([[p0[0] * hw(a), a, p0[1] * hw(a)], [p1[0] * hw(b), b, p1[1] * hw(b)], 0.18, cl])
            tubes.append([[p1[0] * hw(a), a, p1[1] * hw(a)], [p0[0] * hw(b), b, p0[1] * hw(b)], 0.18, cl])
            tubes.append([[p0[0] * hw(b), b, p0[1] * hw(b)], [p1[0] * hw(b), b, p1[1] * hw(b)], 0.25, cl])
    if tip:
        tubes.append([[0, y1, 0], [0, tip, 0], 0.3, col(y1)])
    figure(name, c, facing, bands[0][1], tip or y1, style="spire", tubes=tubes, note=note, base=base)


# ================================================================== NTT Docomo Yoyogi Building
# 240 m (2000): PLATEAU's stepped levels kept to 203.5 m (the body and the clock stage); its two top prisms (218.2 m on
# 137 m², 240.6 m on 53 m²) left out and rebuilt: four clock faces on the clock stage, the stepped cap, the spire
DC_C = np.array([382647.5, 3949719.1])          # the kept top level's centroid (PLATEAU bldg_52945d0d #r2)
DOC, MAST = "#6e625b", "#d4472c"


def piece(gml, lon, lat, r=60.0):
    """A building table piece's outline (UTM) by its gml id, read from a small box round (lon, lat)."""
    import geopandas as gpd
    d = r / 111000
    for src in ("buildings.gpkg", "plateau_buildings.gpkg"):    # (a piece left out of the table: PLATEAU's own)
        b = gpd.read_file(DATA / src, bbox=(lon - d / 0.81, lat - d, lon + d / 0.81, lat + d)).to_crs(UTM)
        if (b.gml_id == gml).any():
            return b[b.gml_id == gml].geometry.iloc[0]
    raise KeyError(gml)


def seat(gml, lon, lat, at):
    """The figure's base over the ground at `at` so that its y = 0 is the scene base 06_tiles gives the piece (the
    lowest ground under its outline): M4 fix round, Docomo's top floated on 203.5 m from a ground metres off"""
    g = piece(gml, lon, lat)
    g = max(getattr(g, "geoms", [g]), key=lambda q: q.area)
    pts = np.array(g.exterior.coords)
    lo = min(ground(q) for q in pts)
    return round(lo - ground(at), 2)


def plug(name, at, r=60.0):
    """PLATEAU's roof levels are rings round the levels above them (roof_split): leaving a building's top levels out
    for a figure left an open shaft from the figure's foot to the ground (fix round: Docomo's, TEPCO's, the domes').
    The hole of the kept levels round `at` (their interior rings holding it) as a plain prism up to the ring's top,
    seated as that piece is; returns the plug's top (m over the ground at `at`) or None."""
    import geopandas as gpd
    from shapely.geometry import Point
    from shapely.geometry import Polygon as P_
    lon, lat = ll(at)
    d = r / 111000
    b = gpd.read_file(DATA / "buildings.gpkg", bbox=(lon - d / 0.81, lat - d, lon + d / 0.81, lat + d)).to_crs(UTM)
    best = None
    for geom, h in zip(b.geometry, b.h):
        for g in getattr(geom, "geoms", [geom]):
            for ring in g.interiors:
                hole = P_(ring)
                if hole.contains(Point(*at)) and (best is None or h > best[1]):
                    lo = min(ground(q) for q in np.array(g.exterior.coords))
                    best = (hole, float(h), lo)
    if best is None:
        return None
    hole, h, lo = best
    base = round(lo - ground(at), 2)
    figure(f"{name} (core under it)", at, 0.0, "#8f8c88", h, style="plain", base=base,
           prisms=[[[local(q, at) for q in list(hole.simplify(0.3).exterior.coords)[:-1]], 0.0, round(h, 2)]],
           note=f"{name}: the hole the left-out top levels left in PLATEAU's ring below it, plugged to {h:.1f} m")
    return base + h


# (PLATEAU's levels agree with OSM's parts w380315124-28: 148.5, 173.5, 188.5, 203.5, 218.2, 240.6 m; sides on 78.6 deg)
# the top two (13.8 m square to 218.2 m, 7.3 m to 240.6 m) rebuilt over the kept #r2 level (its top 203.5 m over the
# lowest ground under it: the figure is seated on that, not on the ground at its centre), in the body's dark stone
# (the zone's tint, a shade lighter: the spire style has no windows), the 32 m derrick (red and white lattice) on top
# to 272 m (JA Wikipedia)
DC_B = seat("bldg_52945d0d-a897-4d55-b35c-a8bcca773e53#r2", 139.70312, 35.68440, DC_C)
plug("Docomo Yoyogi spire", DC_C)
figure("Docomo Yoyogi spire", DC_C, 78.6, DOC, 240.6, style="spire", base=DC_B,
       prisms=[[square(7.0), 203.3, 218.2, DOC], [square(7.3), 218.2, 218.8, "#8c8580"], [square(3.65), 218.8, 240.6, DOC],
               [square(3.9), 240.0, 240.6, "#8c8580"]],
       note="NTT Docomo Yoyogi Building (2000): the spire's top two steps over PLATEAU's stepped body (kept to 203.5 m)")
# the clock: ONE dial, 15 m across, on the north face of the clock stage (PLATEAU's 173.5 m level, 20.4 x 37.3 m, its
# north end 18.7 m from its centre), centre ~162 m (JA Wikipedia; the dial from a photo)
c4 = np.array([382646.2, 3949723.8])
u4 = np.array([math.sin(math.radians(168.6)), math.cos(math.radians(168.6))])
clk = c4 - u4 * 18.65
dial = [[round(7.5 * math.cos(t), 2), round(162.0 + 7.5 * math.sin(t), 2)] for t in np.linspace(0, 2 * math.pi, 25)[:-1]]
rim = [[round(8.1 * math.cos(t), 2), round(162.0 + 8.1 * math.sin(t), 2)] for t in np.linspace(0, 2 * math.pi, 25)[:-1]]
figure("Docomo Yoyogi clock", clk, 348.6, "#d9d4c7", 170.1, style="plain",
       base=seat("bldg_52945d0d-a897-4d55-b35c-a8bcca773e53#r4", 139.70312, 35.68440, clk),
       slabs=[[rim, 0.0, 0.25, "#3b3633"], [dial, 0.25, 0.45, "#d9d4c7"]],
       tubes=[[[0, 162.0, 0.6], [0, 167.5, 0.6], 0.35, "#24211f"], [[0, 162.0, 0.6], [4.0, 160.0, 0.6], 0.4, "#24211f"]],
       note="NTT Docomo Yoyogi Building: its 15 m clock on the north face")
lattice_mast("Docomo Yoyogi derrick", DC_C, 78.6, 240.6, 272.0, 2.2, 0.8,
             [(0.0, MAST), (246.0, "#eeeae2"), (252.0, MAST), (258.0, "#eeeae2"), (264.0, MAST)],
             note="NTT Docomo Yoyogi Building: the 32 m derrick over the spire (JA Wikipedia), red and white (photo)", base=DC_B)

# ================================================================== National Diet Building: the central tower
# 65.45 m (1936). OSM's parts: the tower's shaft (w331852164, 22.5 m square, to 47 m) and its stepped pyramid
# (w331852176, 18.2 m, to 63 m); the wings 20.91 m (the table's OSM outline r3361370). Pale granite (Hiroshima's
# 桜御影 and 恩田石: pale grey-beige), the pyramid stepping in over a colonnade
DT = way("w331852164")
DT_C = DT.mean(0)
e = DT[1] - DT[0]
DT_F = math.degrees(math.atan2(e[0], e[1]))
hs = 0.5 * float(np.hypot(*e))
WALL, STG, PYR, LAN = "#dddbd8", "#cdbdb1", "#d9c3ba", "#b4a89d"     # sampled (data/landmarks_m4l.md §5)
# the plinth block 30.8 m square to 28 m (OSM r4657362, with the colonnade in front), the stage 22.5 m square to 47 m,
# a cornice, the stone pyramid in fine steps to ~60 m, the lantern to 65.45 m
steps = []
y, h = 49.0, hs - 0.4
while h > 3.2:
    steps.append([square(round(h, 2)), round(y, 2), round(y + 1.4, 2), PYR])
    y += 1.4
    h -= 1.0
figure("National Diet central tower", DT_C, DT_F, STG, 65.45, style="floodlit", variant=0.5,
       prisms=[[square(15.4), 20.9, 28.0, WALL], [square(hs), 28.0, 47.0, STG], [square(hs + 0.8), 47.0, 49.0, LAN]]
       + steps + [[square(2.8), round(y, 2), 64.2, LAN], [square(3.2), 64.2, 65.45, LAN, 0.5]],
       note="National Diet Building (1936): the central tower, 65.45 m, on OSM's parts w331852164/w331852176 and r4657362")

# ================================================================== Tokyo Station Marunouchi building: the domes
# The 1914 station (restored 2012): two octagonal domes over the north and south halls (OSM r4856159: 22 m across,
# 36 m top; their pavilions r4856158 to 28 m); slate-grey domes, red brick drums with white bands
BRICK, SLATE, STONE = "#955b4c", "#706d70", "#cfc9bc"   # (M7: the slate lighter, c-tk-m456 item 4: the domes read nearly black)
for nm, (lon, lat) in (("Tokyo Station north dome", (139.766375, 35.68222)), ("Tokyo Station south dome", (139.765732, 35.680515))):
    c = utm(lon, lat)
    figure(nm, c, 22.0, SLATE, 43.0, style="floodlit", variant=0.4, segments=8,
           prisms=[[ring(11.0, 8), 0.0, 25.5, BRICK], [ring(11.4, 8), 25.5, 27.0, STONE]],   # (fix round: the drum from the ground: the left-out dome prism left a notch to the ground in PLATEAU's levels)
           sections=[[27.0, 0, 0, 11.0, 11.0], [30.0, 0, 0, 10.2, 10.2], [32.6, 0, 0, 8.0, 8.0], [34.6, 0, 0, 4.6, 4.6],
                     [36.0, 0, 0, 1.4, 1.4]],
           tubes=[[[0, 35.6, 0], [0, 39.5, 0], 1.0, SLATE], [[0, 39.5, 0], [0, 43.0, 0], 0.15, "#6b3d30"]],
           note="Tokyo Station Marunouchi building (1914, restored 2012): its two octagonal domes (OSM r4856159)" if "north" in nm else None)

# ================================================================== Sensō-ji: the five-storey pagoda and the main hall
# The pagoda (1973, 53.32 m with its sōrin; OSM w173154770, 18 m square plinth, sides at 6 deg): five vermilion
# storeys under dark tiled roofs, each roof's eaves ~3 m out, the bronze sōrin (spire with nine rings) from ~38 m
PG = way("w173154770")
PG_C = PG.mean(0)
PG_F = 6.0
VER, ROOF, PLAS = "#c8432b", "#393740", "#e8e6e1"     # sampled vermilion and tile (data/landmarks_m4l.md §8)
# a 5 m stone platform, five storeys (vermilion posts, white plaster) each under a roof ~3.4 m out, the sōrin from ~42.6 m
pr = [[square(9.0), 0.0, 5.0, "#9a968c"]]
y, hb = 5.0, 5.4
for k in range(5):
    sh = 6.0 if k == 0 else 4.6
    pr.append([square(hb), round(y, 2), round(y + sh, 2), VER])
    pr.append([square(hb + 3.4), round(y + sh, 2), round(y + sh + 0.7, 2), ROOF])
    pr.append([square(hb + 3.4), round(y + sh + 0.7, 2), round(y + sh + 2.4, 2), ROOF, round((hb + 0.6) / (hb + 3.4), 3)])
    y += sh + 2.4
    hb *= 0.9
pr.append([square(hb + 0.6), round(y, 2), round(y + 1.2, 2), ROOF, 0.4])
y += 1.2
figure("Senso-ji five-storey pagoda", PG_C, PG_F, VER, 53.32, style="floodlit", variant=0.5, prisms=pr,
       tubes=[[[0, y, 0], [0, 53.32, 0], 0.45, "#a8873c"]]
       + [[[0, yy, 0], [0, yy + 0.35, 0], 1.1 - 0.06 * i, "#c9a24a"] for i, yy in enumerate(np.linspace(y + 2.0, 50.5, 9))],
       note="Sensō-ji's five-storey pagoda (1973): 53.32 m (OSM w173154770; PLATEAU's prism left out)")
# (floodlit style: the figures keep their own colours, vermilion and dark tile, and are floodlit warm after dark as
# the real ones are; the temple style's timber frame drew its posts over the roofs)
# the main hall (Hondō, 1958): OSM w91008673 (54 x 52 m, 29.4 m); vermilion posts and walls to ~12 m under a huge
# hip-and-gable roof (titanium tiles since 2010: grey), its ridge at 29.4 m
HL = way("w91008673")
HL_C = Polygon(HL).centroid.coords[0]
HL_C = np.array(HL_C)
HL_F = 6.6
hx, hz = 21.0, 19.0
# (M4 fix round: the roof is two thirds of the hall's height in photos, steep and dark: the walls to 10.5 m under deep
# eaves, the hip rising steeply to 22 m, the gabled upper roof (irimoya) to the ridge at 29.4 m)
figure("Senso-ji main hall", HL_C, HL_F, VER, 29.4, style="floodlit", variant=0.5,
       prisms=[[rectangle(hx + 3.0, hz + 3.0), 0.0, 2.0, "#a19c92"], [rectangle(hx, hz), 2.0, 10.5, VER],
               [rectangle(hx + 1.0, hz + 1.0), 9.6, 10.5, "#2b2522"],
               [rectangle(hx + 5.5, hz + 5.5), 10.5, 11.6, ROOF], [rectangle(hx + 5.5, hz + 5.5), 11.6, 22.0, ROOF, 0.5],
               [rectangle(hx * 0.62, hz * 0.32), 22.0, 26.5, ROOF, 0.75], [rectangle(hx * 0.5, hz * 0.07), 26.5, 29.4, ROOF]],
       slabs=[[[[-hx * 0.62, 22.0], [hx * 0.62, 22.0], [hx * 0.5, 29.4], [-hx * 0.5, 29.4]], -hz * 0.26, hz * 0.26, ROOF]],
       note="Sensō-ji's main hall (1958): OSM w91008673, 29.4 m (PLATEAU's three pieces left out)")
# Hōzōmon (1964): 21.7 m, two storeys, OSM w573271561
HZ = way("w573271561")
HZ_C = HZ.mean(0)
figure("Senso-ji Hozomon", HZ_C, 5.3, VER, 21.7, style="floodlit", variant=0.5,
       prisms=[[rectangle(8.0, 4.4), 0.0, 8.0, VER], [rectangle(10.0, 6.2), 8.0, 9.0, ROOF], [rectangle(10.0, 6.2), 9.0, 10.6, ROOF, 0.85],
               [rectangle(7.6, 4.0), 10.6, 15.6, VER], [rectangle(10.4, 6.6), 15.6, 16.6, ROOF],
               [rectangle(10.4, 6.6), 16.6, 21.7, ROOF, 0.25]],
       note="Sensō-ji's Hōzōmon gate (1964): 21.7 m (OSM w573271561)")


# ================================================================== Fuji Television headquarters: the sphere
# Kenzo Tange (1996), 123.45 m: the 32 m titanium-clad sphere (Hachitama) in the grid between the two towers, OSM
# w287906915 (a dome part 96-130 m, 32 m across: its centre at ~112 m). PLATEAU drew it as a 758 m² cylinder to 123.2 m
# (#r0, left out with the two roof pieces it shares a row with; those two are rebuilt here as prisms to 123.2 m)
FS = way("w287906915")
FS_C = FS.mean(0)
TI = "#a7a6a2"          # titanium, lit (a shade lighter than M4's: the critic saw a dark ball)
R_S, Y_S = 16.0, 108.0
secs = [[round(Y_S + R_S * math.sin(a), 2), 0, 0, round(max(R_S * math.cos(a), 0.3), 2), round(max(R_S * math.cos(a), 0.3), 2)]
        for a in np.linspace(-math.pi / 2, math.pi / 2, 15)]
figure("Fuji TV sphere", FS_C, 0.0, TI, Y_S + R_S, style="spire", sections=secs, segments=24,
       tubes=[[[x, 88.0, z], [x * 0.55, Y_S - R_S * 0.75, z * 0.55], 0.6, "#bdbcba"] for x, z in ((-12, -12), (12, -12), (12, 12), (-12, 12))],
       note="Fuji Television headquarters (1996): the 32 m titanium sphere (OSM w287906915), its centre at ~112 m")
FTV_KEEP = json.loads((DATA / "m4l" / "fujitv_r0.json").read_text()) if (DATA / "m4l" / "fujitv_r0.json").exists() else []
for k, pts in enumerate(FTV_KEEP):
    figure(f"Fuji TV roof piece {k + 1}", FS_C, 0.0, "#a9adb1", 123.2, style="panel", walls=True,
           prisms=[[[local(q, FS_C) for q in pts], 0.0, 123.2]])
# (M4 fix round) the open grid between the two towers: PLATEAU's #r2 (4,453 m² to 123.8 m, between the west tower #r1
# and the east tower, the roof piece above) filled it solid, so from the north the sphere sat in a notch of a grey slab
# with punched windows. Left out (city.toml [buildings.exclude]) and rebuilt on its outline: the podium to 31.7 m (the
# neighbouring piece #r4's top), then Tange's megastructure grid: square columns in three rows along the long axis,
# three sky-corridor slabs (two storeys each) and the roof beam, open between them (the sky and the sphere seen through
# it from Daiba station and Yurikamome); light grey precast (#c4c4c6 sampled)
from shapely.geometry import Point
FG = piece("bldg_fd1573b3-1981-4526-958f-b6e64f09f390#r2", 139.7743, 35.6267, 140.0)
FG = max(getattr(FG, "geoms", [FG]), key=lambda q: q.area).simplify(0.8)
rr = np.array(FG.minimum_rotated_rectangle.exterior.coords)[:4]
ee = [rr[1] - rr[0], rr[2] - rr[1]]
il = int(np.argmax([np.hypot(*v) for v in ee]))
FG_F = math.degrees(math.atan2(ee[il][0], ee[il][1])) % 180
FG_C = np.array(FG.minimum_rotated_rectangle.centroid.coords[0])
FG_L, FG_W = float(np.hypot(*ee[il])), float(np.hypot(*ee[1 - il]))
FGB = seat("bldg_fd1573b3-1981-4526-958f-b6e64f09f390#r2", 139.7743, 35.6267, FG_C)
GRID = "#c4c4c6"
hole = Point(*FS_C).buffer(R_S + 1.5)
loc = lambda poly: [[round(x, 2), round(z, 2)] for x, z in (local(q, FG_C, FG_F) for q in list(poly.exterior.coords)[:-1])]
cut = FG.difference(hole)
cut = max(getattr(cut, "geoms", [cut]), key=lambda q: q.area).simplify(0.8)
pr = [[loc(FG), 0.0, 31.7, GRID]]
for y0, y1 in ((52.0, 59.5), (76.0, 83.5), (100.0, 107.5), (118.5, 123.8)):
    pr.append([loc(cut if y1 > Y_S - R_S else FG), y0, y1, GRID])
inner = FG.buffer(-1.6)
bx = []
for u in np.linspace(-FG_L / 2 + 1.6, FG_L / 2 - 1.6, 7):
    for v in (-FG_W / 2 + 1.6, 0.0, FG_W / 2 - 1.6):
        right, fwd = frame_of(FG_F)
        pw = FG_C + right * v + fwd * u
        if not inner.contains(Point(*pw)) or Point(*pw).distance(Point(*FS_C)) < R_S + 2.0:
            continue
        bx.append([round(v, 2), round((31.7 + 118.5) / 2, 2), round(u, 2), 3.2, round(118.5 - 31.7, 2), 3.2, GRID])
# the grid's lighter floor beams on the two long faces between the corridors (every ~8 m)
for y in (39.5, 47.0, 67.5, 91.5):
    for v in (-FG_W / 2 + 1.0, FG_W / 2 - 1.0):
        bx.append([round(v, 2), y, 0.0, 1.2, 1.4, round(FG_L - 3.0, 2), GRID])
figure("Fuji TV grid", FG_C, FG_F, GRID, 123.8, style="spire", base=FGB, prisms=pr, boxes=bx,
       note="Fuji Television headquarters: the open grid between its two towers (PLATEAU's solid #r2 left out)")


# ================================================================== the Sumida's bridges
ROAD_ENDS = {   # the carriageway's ends (OSM: Eitai w168663963, Kachidoki w286507872, Kiyosu w157238663)
    "w1060000228": ((139.786578, 35.676545), (139.788578, 35.676129)),
    "w549492916": ((139.774187, 35.663203), (139.775818, 35.661420)),
    "w856821159": ((139.791024, 35.682867), (139.792765, 35.681957))}


def bridge_frame(wid):
    """centre (the middle of the carriageway's crossing of the water), bearing along it, the outline's length and
    width: the man_made=bridge outlines' centroids lie up to 19 m off the river's middle (Eitai)"""
    import geopandas as gpd
    from shapely.geometry import LineString
    P = Polygon(way(wid))
    r = P.minimum_rotated_rectangle
    cc_ = np.array(r.exterior.coords)[:4]
    e = [cc_[1] - cc_[0], cc_[2] - cc_[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    L, W = float(np.hypot(*e[i])), float(np.hypot(*e[1 - i]))
    A, B = (utm(*q) for q in ROAD_ENDS[wid])
    global _WATER
    if "_WATER" not in globals():
        _WATER = gpd.read_file(DATA / "ground.gpkg", layer="water").to_crs(UTM).union_all()
    x = LineString([A, B]).intersection(_WATER)
    g = max(getattr(x, "geoms", [x]), key=lambda q: q.length)
    c = np.array(g.interpolate(0.5, normalized=True).coords[0])
    # (M4 fix round: the three-span bridges are symmetric (Eitai 26 + 101 + 26 m spans in a 185 m outline, Kachidoki's
    # two arches either side of the bascule), so the frame's centre is the bridge outline's middle projected on the
    # carriageway, which OSM's outline and the river's centreline agree on to ~3 m; the water's middle along the road
    # lies up to 19 m off where a bank's quay walls differ)
    d = B - A
    u = d / np.hypot(*d)
    mid = np.array(r.centroid.coords[0])
    c = A + u * float((mid - A) @ u)
    return c, math.degrees(math.atan2(d[0], d[1])) % 180, L, W


def deck_z(c, r=25.0):
    """The drawn deck's height (scene m) by the bridge's centre: 05b_roads' ways there."""
    import geopandas as gpd
    from shapely.geometry import Point
    global _ROADS
    if "_ROADS" not in globals():
        _ROADS = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    s = _ROADS[_ROADS.geometry.distance(Point(*c)) < r]
    zs = [q[2] for g in s.geometry for q in g.coords if np.hypot(q[0] - c[0], q[1] - c[1]) < r]
    return max(zs) if zs else 5.0


TRUE_W = {"w1060000228": 25.0, "w549492916": 22.0, "w856821159": 22.0}   # JA Wikipedia: the decks' widths (m)


def deck_frame(wid):
    """(fix round 2, the user 8 Oct: Eitai's arch hung off its deck, Kachidoki's arches stood over the water beside it,
    Kiyosu's towers were wider than its deck) the frame of the deck 06_tiles DRAWS: 05b_roads' elevated ways of the
    bridge (one or two carriageways, each drawn `width` wide), not OSM's bridge outline: Eitai's and Kachidoki's
    carriageways lie to one side of the ROAD_ENDS line (8 and 15 m off), and the drawn decks are 13-18 m wide where
    the outlines (and the old ribs at their +-W/2) are 25-26 m. Returns the centre (the middle of the drawn
    carriageways across, bridge_frame's centre along), the bearing, the half-width of the drawn carriageways, the
    drawn deck's ends along the axis (from the centre) and the outline's length."""
    import geopandas as gpd
    from shapely.geometry import Point
    global _ROADS
    if "_ROADS" not in globals():
        _ROADS = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    c, brg, L, W = bridge_frame(wid)
    right, fwd = frame_of(brg)
    s = _ROADS[(_ROADS.geometry.distance(Point(*c)) < 40) & _ROADS.elevated.astype(bool)]
    lo, hi, z0, z1, prof = [], [], [], [], []
    for g, w in zip(s.geometry, s.width):
        q = np.array(g.coords)[:, :2]
        dd = q[-1] - q[0]
        if abs(((math.degrees(math.atan2(dd[0], dd[1])) - brg) + 90) % 180 - 90) > 8:
            continue                                   # (a cross street, a ramp)
        x, z = (q - c) @ right, (q - c) @ fwd
        lo.append(float(np.median(x)) - w / 2)
        hi.append(float(np.median(x)) + w / 2)
        z0.append(float(z.min()))
        z1.append(float(z.max()))
        y = np.array(g.coords)[:, 2]
        o = np.argsort(z)
        prof.append((z[o], y[o]))
    xc = 0.5 * (min(lo) + max(hi))

    def deck_at(a):
        """(tk2) the drawn deck's height (scene m) at `a` m along the axis: the highest of the carriageways there (the
        decks are 05b_roads' tents, ~4 m higher mid-river than at the abutments)"""
        a = np.atleast_1d(np.asarray(a, float))
        out = np.full(a.shape, -np.inf)
        for zz, yy in prof:
            inside = (a >= zz[0] - 0.5) & (a <= zz[-1] + 0.5)
            out = np.where(inside, np.maximum(out, np.interp(a, zz, yy)), out)
        return out
    knots = sorted({round(float(v), 2) for zz, _ in prof for v in zz if max(z0) <= v <= min(z1)} | {max(z0), min(z1)})
    return c + right * xc, brg, 0.5 * (max(hi) - min(lo)), (max(z0), min(z1)), L, deck_at, knots


def along_deck(x0, x1, knots, rel, up, depth, colour):
    """(tk2, the user 8 Oct: the footway slabs and Kiyosu's edge girders, flat at the deck's mid-river height, ran on past
    its ends as boxes floating up to 4 m over the bank roads and the trees) wedges from x0 to x1 across, between each
    pair of the deck's knots along, their top `up` m over the drawn deck there (rel: the deck's height less the
    figure's base), `depth` m deep under its lower end: they follow the deck's tent down to its ends on the banks."""
    out = []
    for a, b in zip(knots[:-1], knots[1:]):
        if b - a < 0.05:
            continue
        ta, tb = float(rel(a)[0]) + up, float(rel(b)[0]) + up
        out.append([[[round(x0, 2), round(a, 2), round(ta, 2)], [round(x1, 2), round(a, 2), round(ta, 2)],
                     [round(x1, 2), round(b, 2), round(tb, 2)], [round(x0, 2), round(b, 2), round(tb, 2)]],
                    round(min(ta, tb) - depth, 2), colour])
    return out


def footways(half, true_w, knots, rel, colour="#8e8b85"):
    """The footways the drawn carriageways leave out: slabs from the carriageway's edge out to the deck's true width
    (+-true_w/2), their top 0.25 m over the road (a kerb), 0.9 m deep: the arches' and towers' feet stand on them.
    (tk2) Along the drawn deck's profile, from one end of the drawn deck to the other (where the approach roads begin)."""
    w = true_w / 2 - half
    if w < 0.5:
        return []
    return [q for sgn in (-1, 1) for q in along_deck(sgn * half, sgn * (half + w), knots, rel, 0.25, 0.9, colour)]


def arch(z0, z1, half, rise, rel, knots, colour, rib=0.9, hang=6.0, top=None):
    """Two arch ribs over a deck span from z0 to z1 along the frame, planes at x = +-half; hangers, a tie, bracing.
    (tk2) The springings and the tie on the drawn deck (rel: its height less the figure's base along the axis), the
    rib's line between its two springings (05b_roads' deck is a tent: Kachidoki's arches' feet stood up to 2 m over it)."""
    out, wedges = [], []
    L = z1 - z0
    d0, d1 = float(rel(z0)[0]), float(rel(z1)[0])
    base = lambda t: d0 + (d1 - d0) * t
    kn = [z0] + [k for k in knots if z0 < k < z1] + [z1]
    for x in (-half, half):
        pts = [[x, base(t) + rise * (1 - (2 * t - 1) ** 2), z0 + L * t] for t in np.linspace(0, 1, 17)]
        out += chain(pts, rib, colour)
        for z in np.arange(z0 + hang, z1 - hang / 2, hang):
            t = (z - z0) / L
            out.append([[x, round(float(rel(z)[0]) + 0.8, 2), round(z, 2)],
                        [x, round(base(t) + rise * (1 - (2 * t - 1) ** 2), 2), round(z, 2)], 0.12, colour])
        wedges += along_deck(x - 0.45, x + 0.45, kn, rel, 1.4, 1.6, colour)
    for z in np.arange(z0 + L * 0.25, z1 - L * 0.24, L / 8):
        t = (z - z0) / L
        y = base(t) + rise * (1 - (2 * t - 1) ** 2)
        out.append([[-half, round(y, 2), round(z, 2)], [half, round(y, 2), round(z, 2)], 0.35, colour])
    return out, wedges


for name, wid, spans, rise, col, note in (
        ("Eitai Bridge", "w1060000228", [(-50.4, 50.4)], 18.0, "#9db7d3",
         "Eitai Bridge (1926): the ~100 m central tied arch over the Sumida (after the Ludendorff Bridge), pale blue (est.)"),
        ("Kachidoki Bridge", "w549492916", [(-112.0, -28.0), (28.0, 112.0)], 14.5, "#c9c4b8",
         "Kachidoki Bridge (1940): the two tied arches either side of the 51.6 m bascule span (fixed since 1970), light\n"
         "warm grey (sampled #c9c4b8, data/landmarks_m4l.md §9)")):
    c, brg, half_c, (e0, e1), L, deck_at, knots = deck_frame(wid)
    d = deck_z(c)
    rel = lambda a, d=d, f=deck_at: f(a) - d
    # the ribs over the drawn carriageways' edges (+1 m: on the kerb), the footways out to the true width beside them
    tubes, wedges = [], footways(half_c, TRUE_W[wid], knots, rel)
    for z0, z1 in spans:
        t_, w_ = arch(z0, z1, half_c + 1.0, rise, rel, knots, col)
        tubes += t_
        wedges += w_
    figure(name, c, brg, col, rise + 1.0, style="spire", base=round(d - ground(c), 2), tubes=tubes, wedges=wedges, note=note)

# Kiyosu Bridge (1928): a self-anchored suspension bridge after Cologne's Hindenburgbrücke, main span 91.4 m, its
# eyebar chains from two portal towers ~25 m over the deck, light "Kiyosu blue" (est. from sampled railings #748caf)
c, brg, half_c, (e0, e1), L, deck_at, knots = deck_frame("w856821159")
d = deck_z(c)
rel = lambda a: deck_at(a) - d
KB = "#7f9fcf"
# (fix round 2) the towers' legs and chains over the drawn carriageway's edges (+1 m), the backstays to the drawn
# deck's ends, the footways out to the true 22 m beside them
half, Lm, Ht = half_c + 1.0, 91.4, 25.0
tubes, boxes = [], []
wedges = footways(half_c, TRUE_W["w856821159"], knots, rel)
for x in (-half, half):
    for zt in (-Lm / 2, Lm / 2):
        tubes.append([[x, round(float(rel(zt)[0]) - 0.5, 2), zt], [x, Ht, zt], 1.0, KB])   # (tk2) from the deck there
    pts = [[x, Ht - (Ht - 2.0) * (1 - (2 * t - 1) ** 2), -Lm / 2 + Lm * t] for t in np.linspace(0, 1, 15)]
    tubes += chain(pts, 0.7, KB)
    for sgn in (-1, 1):
        end = e1 if sgn > 0 else e0
        # (tk2) anchored on the deck at its end (the deck lies ~4 m under its mid-river height there)
        ze = end - sgn * 1.0
        tubes += chain([[x, Ht, sgn * Lm / 2], [x, Ht * 0.45, sgn * (Lm / 2 + 22)], [x, round(float(rel(ze)[0]) + 1.0, 2), ze]], 0.7, KB)
    for z in np.arange(-Lm / 2 + 6, Lm / 2 - 3, 6.0):
        t = (z + Lm / 2) / Lm
        tubes.append([[x, round(float(rel(z)[0]) + 0.8, 2), round(z, 2)], [x, round(Ht - (Ht - 2.0) * (1 - (2 * t - 1) ** 2), 2), round(z, 2)], 0.12, KB])
    wedges += along_deck(x - 0.4, x + 0.4, knots, rel, 1.6, 1.6, KB)   # (tk2) the edge girders on the deck's profile
for zt in (-Lm / 2, Lm / 2):
    tubes.append([[-half, Ht - 1.0, zt], [half, Ht - 1.0, zt], 0.8, KB])
figure("Kiyosu Bridge", c, brg, KB, Ht + 1.0, style="spire", base=round(d - ground(c), 2), tubes=tubes, boxes=boxes or None,
       wedges=wedges,
       note="Kiyosu Bridge (1928): the self-anchored chain suspension bridge over the Sumida, blue (est.)")

# ================================================================== Wakō's clock tower (Ginza 4-chome)
# 1932 (Watanabe Jin): OSM's parts (w1341815191, the tower's base on the cornice, 28-30 m; w1341775164, the 6 m
# square tower, to 38 m; w1341815951, the finial to 40 m): a square stage with the clock faces (~2.8 m, est.) near its
# top, a small cap and pinnacle; cream stone (#e9dfcf, from the sampled sunlit #fbf3e8)
WT = way("w1341775164")
WK = WT.mean(0)
ew = WT[1] - WT[0]
WKF = math.degrees(math.atan2(ew[0], ew[1]))
CR = "#e9dfcf"
figure("Wako clock tower", WK, WKF, CR, 40.0, style="floodlit", variant=0.5,
       prisms=[[square(4.8), 28.0, 30.5, CR], [square(2.95), 30.5, 37.0, CR], [square(3.3), 37.0, 37.6, "#d6cbb8"],
               [square(2.6), 37.6, 38.6, CR, 0.5]],
       boxes=[[0, 35.0, 3.0, 2.6, 2.6, 0.15, "#f6f3ea"], [0, 35.0, -3.0, 2.6, 2.6, 0.15, "#f6f3ea"],
              [3.0, 35.0, 0, 0.15, 2.6, 2.6, "#f6f3ea"], [-3.0, 35.0, 0, 0.15, 2.6, 2.6, "#f6f3ea"]],
       tubes=[[[0, 38.6, 0], [0, 40.0, 0], 0.25, "#b9a77d"]],
       note="Wakō (1932): the Ginza 4-chome clock tower on OSM's parts (w1341775164 etc.), 38 m, the finial to 40 m")

# ================================================================== Nikolai-dō
# Holy Resurrection Cathedral (1891, dome rebuilt 1929): OSM's parts (body w273260343 23 m square to 18 m, drum
# w273260342 19 m to 20 m, dome w273258751 16 m to 30 m; the cross to ~35 m); PLATEAU's 28.7 m prism of the dome
# (#r0) left out, its lower pieces kept. Verdigris dome #4a8174 (sampled #3f7267), cream walls, dark bands
NK = way("w273258751").mean(0)
figure("Nikolai-do dome", NK, 0.0, "#4a8174", 35.0, style="floodlit", variant=0.4, segments=24,
       prisms=[[ring(9.4, 16), 0.0, 18.0, "#d8d0c4"],   # (fix round: from the ground, as the domes')
                [ring(9.0, 16), 18.0, 19.4, "#3d3a33"], [ring(8.6, 16), 19.4, 22.0, "#d8d0c4"]],
       sections=[[22.0, 0, 0, 8.4, 8.4], [25.0, 0, 0, 7.9, 7.9], [27.6, 0, 0, 6.2, 6.2], [29.4, 0, 0, 3.4, 3.4],
                 [30.0, 0, 0, 1.0, 1.0]],
       tubes=[[[0, 29.8, 0], [0, 32.0, 0], 0.6, "#4a8174"], [[0, 32.0, 0], [0, 35.0, 0], 0.12, "#c9a24a"],
              [[-0.8, 34.0, 0], [0.8, 34.0, 0], 0.1, "#c9a24a"]],
       note="Nikolai-dō (1891/1929): the verdigris dome on OSM's parts, 35 m with its cross")


TEPCO_TOP = plug("TEPCO head office mast", np.array([387641.36, 3948089.98]))   # (the kept roof ring: the mast stands on it)
RW = [(0.0, "#d4472c"), (69.0, "#eeeae2"), (79.0, "#d4472c"), (89.0, "#eeeae2"), (99.0, "#d4472c")]
lattice_mast("TEPCO head office mast", np.array([387641.36, 3948089.98]), 26.9, round(TEPCO_TOP or 59.0, 2), 108.9, 5.2, 1.6, RW,
             note="TEPCO's head office (Uchisaiwaicho): the rooftop lattice mast, 59-108.9 m (PLATEAU's prism left out),\n"
                  "red and white bands (est.)")
# (Nittele Tower: no tall antenna, a curved steel arch on its roof (photo): not modelled)


# ================================================================== the two towers missing from the data (approximate)
# Neither has an outline in OSM or PLATEAU (both completed in 2026): massed from the developers' figures, placed on
# their sites' OSM outlines; plans and setbacks estimated (data/landmarks_m4l.md §15). Marked approximate.
def site(k):
    return Polygon(way(k))


# Tokyo Midtown Nihonbashi (日本橋野村三井タワー, Nihonbashi 1-chome C block, 2026): 284 m, 52 floors; the tower a
# wide rounded rectangle (~5,000 m² a floor from the GFA), one big setback on the east face at ~58 % of its height, a
# crown of louvre bands; blue-grey glass (sampled #778fa8-#9bacbc on a morning photo; #7f93a8 est. by day); the
# MICE/retail podium (~35 m, est.) over the rest of the C-block site (OSM w750976828)
S1 = site("w750976828")
r1 = S1.minimum_rotated_rectangle
cc = np.array(r1.exterior.coords)[:4]
e1 = [cc[1] - cc[0], cc[2] - cc[1]]
i1 = int(np.argmax([np.hypot(*v) for v in e1]))
F1 = math.degrees(math.atan2(e1[i1][0], e1[i1][1])) % 180
C1 = np.array(S1.centroid.coords[0])
GL1 = "#7f93a8"
pod = [[round(x, 2), round(z, 2)] for x, z in (local(q, C1, F1) for q in list(S1.buffer(-6.0).simplify(1.0).exterior.coords)[:-1])]
figure("Tokyo Midtown Nihonbashi (approx.)", C1, F1, GL1, 284.0, style="glass", walls=True,
       prisms=[[pod, 0.0, 34.0, "#93a3b1"], [rectangle(35.0, 33.0), 0.0, 165.0, GL1], [rectangle(30.0, 30.0, -4.0, 0.0), 165.0, 268.0, GL1],
               [rectangle(30.0, 30.0, -4.0, 0.0), 268.0, 284.0, "#5f6f80", 0.86]],
       note="Tokyo Midtown Nihonbashi (2026): 284 m, APPROXIMATE massing on its site (OSM w750976828; no outline in the data)")
# Grand City Tower Tsukishima (月島三丁目北地区, May 2026): 197.65 m, 58 floors, 1,284 homes; a squarish tower of
# ~2,200 m² a floor (est.) at the listing's point in the north of the site (OSM w1158707581), a 3-storey retail and
# parking podium (est.); white and light-grey precast with balconies (est.)
S2 = site("w1158707581")
C2 = utm(139.779584, 35.663154)
pod2 = [[round(x, 2), round(z, 2)] for x, z in (local(q, C2, 0.0) for q in list(S2.buffer(-5.0).simplify(1.0).exterior.coords)[:-1])]
figure("Grand City Tower Tsukishima (approx.)", C2, 0.0, "#d4cfc4", 197.65, style="mansion", walls=True,
       prisms=[[pod2, 0.0, 14.0, "#bdb6aa"], [rectangle(23.5, 23.5), 0.0, 197.65, "#d4cfc4"]],
       note="Grand City Tower Tsukishima (2026): 197.65 m, APPROXIMATE massing (OSM site w1158707581; no outline in the data)")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("# generated by scripts/m4l_structures.py (edit the script, not this file): Tokyo's landmark figures (M4)\n\n"
               + "\n".join(blocks))
print(f"{OUT}: {len(blocks)} structures")
for k, v in tri_est.items():
    print(f"  {k}: ~{v:,} triangles")
print(f"  total ~{sum(tri_est.values()):,} (figures; the lattice tower and the bridge print their own in 06_tiles)")
