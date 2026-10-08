"""M4 (landmarks, builder b-hk-m4l): Hong Kong's landmarks the building table can't draw, as [[structures]] figures
written to generated/structures-m4l.toml (city.toml `include`s it; re-run after editing the numbers here, then
06_tiles and 07_pack). Run from demos/hongkong: `uv run python scripts/m4l_structures.py`.

Positions and plans from LandsD's Building rows (by BuildingCSUID, from landsd_prepared/landsd_E600_ground.gpkg,
which keeps the rows city.toml's [buildings] exclude leaves out) and OSM's ways (raw/osm_roads.json); heights from
data/landmarks.csv and the published figures; shapes and colours from the photos in data/landmarks.md ("M4 figures").
Every figure's 0 is set with `floor` (an absolute scene height: the LandsD row's base, 06_tiles' Terrain.bases, the
lowest ground under its outline, plus its height), so a mast stands on its roof whatever the ground under its point.

The rows a figure replaces are listed in M4L_EXCLUDE (city.toml [buildings] exclude BuildingCSUID, written by hand);
the rows a figure caps keep their surveyed roof (fix_h in city.toml where the roof is not LandsD's TopHeight).
"""
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "hongkong"
OUT = HERE / "generated" / "structures-m4l.toml"
UTM = 32650
TO_UTM = Transformer.from_crs(4326, UTM, always_xy=True)
TO_LL = Transformer.from_crs(UTM, 4326, always_xy=True)


def ll(p):
    lon, lat = TO_LL.transform(float(p[0]), float(p[1]))
    return [round(lon, 7), round(lat, 7)]


def utm(lon, lat):
    return np.array(TO_UTM.transform(lon, lat))


def f(x):
    return f"{x:.10g}" if isinstance(x, float) else str(x)


def arr(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return "[" + ", ".join(arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    return f(round(float(v), 3))


_T = None


def terrain():
    global _T
    if _T is None:
        from city3d.common import Terrain
        _T = Terrain()
    return _T


def ground(p):
    """The scene ground 06_tiles stands a figure on at UTM point p."""
    return float(terrain().height_utm([p[0]], [p[1]])[0])


def frame_of(facing):
    az = math.radians(facing)
    fwd = np.array([math.sin(az), math.cos(az)])
    return np.array([fwd[1], -fwd[0]]), fwd


def local(p, origin, facing=0.0):
    """UTM point p in a figure's frame (x right, z forward) at origin facing `facing`."""
    right, fwd = frame_of(facing)
    d = np.asarray(p, float) - origin
    return [round(float(d @ right), 3), round(float(d @ fwd), 3)]


def rect(g):
    """A footprint's rotated rectangle: centre, long unit u, short unit v, length, width, bearing of u."""
    r = g.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e = [c[1] - c[0], c[2] - c[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    L, W = float(np.hypot(*e[i])), float(np.hypot(*e[1 - i]))
    u = e[i] / L
    return np.array(r.centroid.coords[0]), u, np.array([-u[1], u[0]]), L, W, math.degrees(math.atan2(u[0], u[1])) % 360


def ring(r, n=8, phase=None, cx=0.0, cz=0.0):
    phase = math.pi / n if phase is None else phase
    return [[round(cx + r * math.cos(phase + 2 * math.pi * i / n), 3), round(cz + r * math.sin(phase + 2 * math.pi * i / n), 3)]
            for i in range(n)]


def square(h, cx=0.0, cz=0.0):
    return [[cx - h, cz - h], [cx + h, cz - h], [cx + h, cz + h], [cx - h, cz + h]]


def rectangle(hx, hz, cx=0.0, cz=0.0):
    return [[cx - hx, cz - hz], [cx + hx, cz - hz], [cx + hx, cz + hz], [cx - hx, cz + hz]]


blocks, tri_est = [], {}


def figure(name, at_utm, facing=0.0, colour="#b0b0b0", top=None, style="plain", variant=0.5, base=0.0, floor=None,
           sections=None, tubes=None, boxes=None, prisms=None, slabs=None, wedges=None, walls=False, segments=None,
           note=None, glazing=None):
    """floor: the figure's 0 at this absolute scene height (m) whatever the ground under its point."""
    if floor is not None:
        base = floor - ground(at_utm)
    ys = [s[0] for s in sections or []] + [p[2] for p in prisms or []] + [b[1] + b[4] / 2 for b in boxes or []] \
        + [max(t[0][1], t[1][1]) for t in tubes or []] + [max(q[1] for q in s[0]) for s in slabs or []] \
        + [max(q[2] for q in w[0]) for w in wedges or []]
    top = top or max(ys + [1.0])
    seg = int(segments or 16)
    n = (2 * seg * max(0, len(sections or []) - 1) + 80 * len(tubes or []) + 12 * len(boxes or [])
         + sum(4 * len(p[0]) - 4 for p in prisms or []) + sum(4 * len(s[0]) - 4 for s in slabs or [])
         + sum(4 * len(w[0]) - 4 for w in wedges or [])
         + sum(2 * (len(g["grid"]) - 1) * (len(g["grid"][0]) - 1) for g in glazing or []))
    tri_est[name] = tri_est.get(name, 0) + n
    out = [f"# {line}" for line in (note or "").split("\n") if note]
    out += ["[[structures]]", 'kind = "figure"', f'name = "{name}"', "at = [%.7f, %.7f]" % tuple(ll(at_utm)),
            f"facing = {f(round(float(facing), 2))}", f'style = "{style}"', f"variant = {variant}", f'colour = "{colour}"',
            f"top = {f(round(float(top), 2))}"]
    if abs(base) > 1e-3:
        out.append(f"base = {f(round(float(base), 2))}")
    if walls:
        out.append("walls = true")
    if segments:
        out.append(f"segments = {int(segments)}")
    for key, v in (("sections", sections), ("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs),
                   ("wedges", wedges)):
        if v:
            out.append(f"{key} = [" + ",\n    ".join(arr(x) for x in v) + "]")
    for gz in glazing or []:
        out.append("[[structures.glazing]]")
        out.append("grid = " + arr(gz["grid"]))
        out.append(f"period = {arr(gz['period'])}")
        if gz.get("colour"):
            out.append(f'colour = "{gz["colour"]}"')
        if gz.get("kind"):
            out.append(f'kind = "{gz["kind"]}"')
    blocks.append("\n".join(out) + "\n")


def chain(pts, r, colour=None):
    """Tubes along a polyline (figure frame points)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        t = [[round(float(v), 2) for v in a], [round(float(v), 2) for v in b], r]
        if colour:
            t.append(colour)
        out.append(t)
    return out


# ------------------------------------------------------------------ LandsD rows
LD = gpd.read_file(DATA / "landsd_prepared/landsd_E600_ground.gpkg",
                   columns=["BuildingCSUID", "BuildingNameEN", "top_mpd", "ground_mpd", "min_h"]).to_crs(UTM)
PD = 1.30                       # mPD -> the scene's metres above mean sea level


def row(csuid):
    s = LD[LD.BuildingCSUID == csuid]
    if not len(s):
        raise KeyError(csuid)
    g = s.geometry.iloc[0]
    g = max(g.geoms, key=lambda q: q.area) if g.geom_type == "MultiPolygon" else g
    return g, s.iloc[0]


def roof_of(csuid, h=None):
    """(outline, its centroid, the absolute scene height of its roof): 06_tiles' base (the lowest ground under the
    outline) plus the row's height (LandsD's top - ground, or h where city.toml's fix_h or a landmark sets it)."""
    g, r = row(csuid)
    h = float(r.top_mpd - r.ground_mpd) if h is None else h
    base = float(terrain().bases([g])[0])
    return g, np.array(g.centroid.coords[0]), base + h, base


def outline_local(g, c, facing=0.0, simplify=0.4, buffer=0.0):
    if buffer:
        g = g.buffer(buffer, join_style=2)
    g = g.simplify(simplify)
    return [[round(x, 2), round(z, 2)] for x, z in (local(q, c, facing) for q in list(g.exterior.coords)[:-1])]


M4L_EXCLUDE = {}                 # BuildingCSUID: why (city.toml [buildings] exclude, by hand)


# ================================================================== the figures (filled in below)

# ------------------------------------------------------------------ crowns, spires and masts over LandsD's roofs
# (name, BuildingCSUID, the row's height over its ground (fix_h where city.toml sets it), the listed top over the
# same ground (data/landmarks.csv), the crown's shape: a list of (fraction of the crown's height, scale of the
# roof outline) for the solid crown, colour, and a mast/spire: (from fraction, radius at its foot) or None)
CROWNS = [
    # (photo: data/landmarks.md) the oval walls run on as an open ring of metal bands for the last ~25 m, plant behind
    ("Langham Place Office Tower crown", "3540319981T20050430", None, 255.0, "ring", "#a9afb5", None),
    # (photo) a low plant box on the flat roof and a white "Y" frame: two arms rising out from the blue spine, a mast
    ("The Masterpiece crown", "3595417627T20080331", None, 261.0, [(0.0, 0.55), (0.4, 0.5)], "#c9c9c4", "arms"),
    # (photo) a flat roof; a ~1.5 m lattice mast with ring flanges at a corner, 37 m
    ("Lee Garden One spire", "3706415509T20050430", None, 240.0, [], "#c2c6c9", "corner"),
    # (no photo, low confidence) a glazed tapering cap with a thin mast
    ("Victoria Dockside crown", "3615217330T20180806", None, 284.0, [(0.0, 0.95), (0.8, 0.55)], "#8fa2ad", (0.8, 0.7)),
    # (photo, night) the five added floors' slightly narrower stage, a flat roof, a small mast
    ("Sun Hung Kai Centre crown", "3627215726T20050430", None, 215.0, [(0.0, 0.94), (0.3, 0.94)], "#2f353b", (0.3, 0.6)),
    # (photo) a glass "junk sail" cap, its top edge sloping, one corner taller
    ("AIA Central crown", "3471615826T20050511", None, 185.0, "sail", "#9fb3c2", None),
    # (low confidence) small rounded lanterns with a pole; pale boxes; a glass pinnacle
    ("Sorrento Tower 2 crown", "3472818625T20050430", None, 236.0, [(0.0, 0.6), (0.7, 0.5)], "#d5d1c6", (0.7, 0.4)),
    ("The Belcher's Tower 6 crown", "3178916280T20050430", None, 227.0, [(0.0, 0.7), (0.8, 0.65)], "#cfcbc2", (0.8, 0.4)),
    ("The Hermitage Tower 1 crown", "3507619861T20101116", None, 234.0, [(0.0, 0.8), (1.0, 0.1)], "#9db3c4", None),
    ("The Harbourside crown", "3474418229T20050430", None, 251.0, [(0.0, 0.92), (1.0, 0.8)], "#c7c3b8", None),
]


def crown_figure(name, csuid, h, top, shape, colour, mast, note=None):
    g, c, roof, base = roof_of(csuid, h)
    hc = base + top - roof
    if hc <= 0.5:
        print(f"{name}: no crown ({top} m listed, roof {roof - base:.1f} m)")
        return
    loc = np.array(outline_local(g, c, simplify=0.8))
    prisms, wedges, tubes = [], [], []
    if shape == "sail":
        xs = loc[:, 0]
        t = (xs - xs.min()) / max(np.ptp(xs), 1e-6)
        wedges.append([[[round(x * 0.95, 2), round(z * 0.95, 2), round(2.0 + (hc - 2.0) * tt, 2)] for (x, z), tt in zip(loc, t)], 0.0, colour])
    elif shape == "ring":
        # (M4 fix round 1, Known issue 69) an open ring: the oval walls run on as five horizontal metal bands 1.5 m
        # deep, 0.7 m thick along the outline, on posts at every other corner; a dark plant box low inside
        ccw = np.sum(loc[:, 0] * np.roll(loc[:, 1], -1) - np.roll(loc[:, 0], -1) * loc[:, 1]) > 0
        bands = [(y, y + 1.5) for y in np.linspace(0.0, hc - 1.5, 5)]
        for i in range(len(loc)):
            a, b = loc[i], loc[(i + 1) % len(loc)]
            d = (b - a) / max(np.hypot(*(b - a)), 1e-6)
            inw = np.array([-d[1], d[0]]) * (1 if ccw else -1) * 0.7
            quad = [[round(float(q[0]), 2), round(float(q[1]), 2)] for q in (a, b, b + inw, a + inw)]
            prisms += [[quad, round(float(y0), 2), round(float(y1), 2), colour] for y0, y1 in bands]
            if i % 2 == 0:
                tubes.append([[round(float(a[0] + inw[0] / 2), 2), 0.0, round(float(a[1] + inw[1] / 2), 2)],
                              [round(float(a[0] + inw[0] / 2), 2), round(hc, 2), round(float(a[1] + inw[1] / 2), 2)], 0.35, colour])
        prisms.append([[[round(x * 0.55, 2), round(z * 0.55, 2)] for x, z in loc], 0.0, round(0.3 * hc, 2), "#5d6266"])
    else:
        for (f0, s0), (f1, s1) in zip(shape, shape[1:]):
            o = loc * s0
            prisms.append([[[round(x, 2), round(z, 2)] for x, z in o], f0 * hc, f1 * hc, colour, s1 / s0])
    if mast == "corner":
        k = int(np.argmax(np.hypot(loc[:, 0], loc[:, 1])))
        x, z = loc[k] * 0.85
        tubes.append([[x, 0.0, z], [x, hc, z], 0.75, colour])
        tubes += [[[x, y - 0.4, z], [x, y + 0.4, z], 1.3, colour] for y in np.arange(4.0, hc - 2.0, 6.0)]
    elif mast == "arms":
        _, u, v, L, W, _ = rect(g)
        for sgn in (-1, 1):
            p0 = u * sgn * 0.12 * L
            p1 = u * sgn * 0.42 * L
            tubes.append([[p0[0], 0.4 * hc, p0[1]], [p1[0], 0.95 * hc, p1[1]], 0.9, "#eceeee"])
        tubes.append([[0, 0.4 * hc, 0], [0, hc, 0], 0.3, "#d0d0cc"])
    elif mast:
        f0, r0 = mast
        tubes.append([[0, f0 * hc, 0], [0, hc, 0], r0, colour])
    figure(name, c, 0.0, colour, hc, floor=roof, prisms=prisms, wedges=wedges, tubes=tubes,
           note=note or f"{name}: {roof - base:.1f} m roof (LandsD) to {top:.0f} m (data/landmarks.csv)")


for args in CROWNS:
    crown_figure(*args)

# ------------------------------------------------------------------ Central Plaza: the tower, its pyramid and mast
# LandsD's row is the whole lot (3,656 m², 84 x 73 m, no triangle): kept as the 30.5 m podium (city.toml fix_h) and the
# tower drawn on it as a figure. Wikipedia: a triangle with its three corners cut, 30.5 m base, 235.4 m body, six plant
# floors and the 102 m mast to 374 m; roof 309, top floor 299. Research (data/landmarks.md): a flat side to the
# harbour (north), the apex to the hill; over the body the corners' white steel "horns" frame a three-sided glass
# pyramid to 309 m; gold and silver glass. The plan's side 74 m with 10 m corner cuts (~2,240 m² a floor, est. from the
# ~2,300 m² office floors)
CP_ROW = "3593215701T20050430"
CP_BODY, CP_ROOF, CP_TIP = 285.0, 309.0, 374.0
g, c_cp, _, base_cp = roof_of(CP_ROW, 0.0)
S_CP, CUT = 74.0, 10.0
R_CP = S_CP / math.sqrt(3.0)                                  # centroid to a corner
tri = [np.array([R_CP * math.sin(math.radians(a_)), R_CP * math.cos(math.radians(a_))]) for a_ in (180.0, 300.0, 60.0)]
plan = []                                                     # the triangle (apex south) with its corners cut
for k in range(3):
    p0, pm, p1 = tri[k - 1], tri[k], tri[(k + 1) % 3]
    plan.append(pm + (p0 - pm) * CUT / S_CP)
    plan.append(pm + (p1 - pm) * CUT / S_CP)
plan = [[round(float(x), 2), round(float(z), 2)] for x, z in plan]
GOLD_GL, SILVER = "#a39a86", "#c9cbc8"
figure("Central Plaza", c_cp, 0.0, GOLD_GL, CP_BODY, style="glass", variant=0.6, walls=True, floor=base_cp,
       prisms=[[plan, 0.0, CP_BODY, GOLD_GL]],
       note="Central Plaza (1992): the tower over LandsD's lot row (fix_h 30.5 m: the podium), a cut triangle to 285 m")
horns = [[[x * 0.98, CP_BODY - 2.0, z * 0.98], [x * 0.9, CP_BODY + 9.0, z * 0.9], 1.0, SILVER]
         for x, z in (np.array(plan[0::2]) + np.array(plan[1::2])) / 2]
figure("Central Plaza top", c_cp, 0.0, "#8f969c", CP_TIP, floor=base_cp,
       prisms=[[[[round(x * 0.9, 2), round(z * 0.9, 2)] for x, z in plan], CP_BODY, CP_ROOF, "#8f969c", 0.22]],
       tubes=horns + [[[0, CP_ROOF - 6.0, 0], [0, CP_ROOF + 8.0, 0], 1.6, SILVER],
                      [[0, CP_ROOF + 8.0, 0], [0, CP_TIP - 20.0, 0], 0.9, SILVER],
                      [[0, CP_TIP - 20.0, 0], [0, CP_TIP, 0], 0.4, SILVER]],
       note="Central Plaza: the glass pyramid 285-309 m in its corner horns, the mast to 374 m")

# ------------------------------------------------------------------ The Center: the stepped top and the mast
# LandsD's roof 291 m kept; the top's setbacks (est.) and the mast to 346 m (data/landmarks.csv)
g, c_tc, roof_tc, base_tc = roof_of("3398216188T20050430")
loc = np.array(outline_local(g, c_tc, simplify=0.8))
steps = [(0.0, 6.0, 0.86), (6.0, 11.0, 0.68), (11.0, 15.0, 0.48)]
figure("The Center top", c_tc, 0.0, "#9aa4ab", base_tc + 346.0 - roof_tc, floor=roof_tc,
       prisms=[[[[round(x * s, 2), round(z * s, 2)] for x, z in loc], y0, y1, "#8d979e"] for y0, y1, s in steps],
       tubes=[[[0, 15.0, 0], [0, base_tc + 346.0 - roof_tc - 15.0, 0], 1.2, "#c4c8ca"],
              [[0, base_tc + 346.0 - roof_tc - 15.0, 0], [0, base_tc + 346.0 - roof_tc, 0], 0.5, "#c4c8ca"]],
       note="The Center (1998): the stepped top over LandsD's 291 m roof and the mast to 346 m")

# ------------------------------------------------------------------ Kai Tak Stadium: the roof shell
# LandsD's one row (53,294 m², 55.6 m: a flat prism) excluded and rebuilt: the bowl's facade wall up to the roof's
# eaves, the roof shell over the outline as stacked frustums (a low dome: the outline moving in as it rises), the
# retractable roof's two panels a darker strip along the long (north-south) axis over the pitch
KT = "3837920357T20241029"
M4L_EXCLUDE[KT] = "Kai Tak Stadium: rebuilt as a figure (the roof shell)"
g, c_kt, roof_kt, base_kt = roof_of(KT)
H_KT = roof_kt - base_kt
EAVE = 34.0                                                   # the facade's top, where the shell starts (est.)
loc = np.array(outline_local(g, c_kt, simplify=2.0))
SHELL = [(EAVE, 1.0), (40.0, 0.96), (45.5, 0.88), (50.0, 0.76), (53.5, 0.6), (H_KT, 0.4)]
prisms = [[[[round(x, 2), round(z, 2)] for x, z in loc * 0.985], 0.0, EAVE, "#b9bcbd"]]
for (y0, s0), (y1, s1) in zip(SHELL, SHELL[1:]):
    prisms.append([[[round(x, 2), round(z, 2)] for x, z in loc * s0], y0, y1, "#dfe2e3", s1 / s0])
_, u_kt, v_kt, L_kt, W_kt, brg_kt = rect(g)
# the closed retractable roof: a slightly raised dark strip over the pitch (~ 0.4 of the plan across, est.)
prisms.append([rectangle(0.2 * W_kt, 0.3 * L_kt), H_KT, H_KT + 0.6, "#8e9496"])
figure("Kai Tak Stadium", c_kt, 0.0, "#dfe2e3", H_KT + 0.6, floor=base_kt, prisms=prisms,
       note="Kai Tak Stadium (2025): the facade and the roof shell over LandsD's outline (its row excluded), 55.6 m")

# ------------------------------------------------------------------ the Former KCR Clock Tower (Tsim Sha Tsui)
# 44 m to the lightning rod (data/landmarks.csv); LandsD's 7 m square row (40.2 m) excluded and rebuilt: the red
# brick shaft with granite bands, the clock stage, the octagonal cupola and the rod
CT = "3551517187T20050430"
M4L_EXCLUDE[CT] = "the Clock Tower: rebuilt as a figure"
g, c_ct, roof_ct, base_ct = roof_of(CT)
_, u_ct, v_ct, L_ct, W_ct, brg_ct = rect(g)
BRICK, GRANITE = "#9a5a44", "#d6d0c4"
hw = 0.5 * (L_ct + W_ct) / 2
bands = [[square(hw + 0.15), y, y + 0.6, GRANITE] for y in (6.0, 13.0, 20.0)]
figure("Clock Tower", c_ct, brg_ct, BRICK, 44.0, floor=base_ct,
       prisms=[[square(hw + 0.3), 0.0, 3.0, GRANITE], [square(hw), 3.0, 26.0, BRICK]] + bands
       + [[square(hw + 0.4), 26.0, 27.2, GRANITE], [square(hw - 0.2), 27.2, 33.0, BRICK],
          [square(hw + 0.3), 33.0, 34.0, GRANITE], [ring(hw * 0.95, 8), 34.0, 37.5, GRANITE],
          [ring(hw * 0.95, 8), 37.5, 41.0, "#5d6a63", 0.2]],
       boxes=[[0, 30.0, hw - 0.1, 2.6, 2.6, 0.3, "#f2efe6"], [0, 30.0, -hw + 0.1, 2.6, 2.6, 0.3, "#f2efe6"],
              [hw - 0.1, 30.0, 0, 0.3, 2.6, 2.6, "#f2efe6"], [-hw + 0.1, 30.0, 0, 0.3, 2.6, 2.6, "#f2efe6"]],
       tubes=[[[0, 40.5, 0], [0, 44.0, 0], 0.12, "#4a4a48"]],
       note="Former Kowloon-Canton Railway Clock Tower (1915): 44 m to the lightning rod")

# ------------------------------------------------------------------ the ferry piers on their piled decks
# Central Ferry Piers 2-8 (No. 7 the Star Ferry's), the Central Government Pier, Central Piers 9-10 and Tsim Sha Tsui's
# Star Ferry Pier: LandsD's rows stood as boxes straight in the sea (Known issue 35; OSM maps only the public piers'
# stubs as man_made=pier). Each row is excluded and rebuilt standing on a piled deck at DECK m over mean sea level:
# the deck (the row's outline + APRON m, swept to the shore along the direction of the nearest land, so the waterfront
# promenade reaches it), a row of piles under its sea edge, the pier building from the deck to LandsD's top less the
# roof, its pitched roof
DECK, APRON = 3.5, 3.0
PIERS = {
    "3418216606T20050430": "Central Pier No.2", "3427316583T20050430": "Central Pier No.3",
    "3436716557T20050430": "Central Pier No.4", "3446416525T20050430": "Central Pier No.5",
    "3455616499T20050430": "Central Pier No.6", "3465316464T20050430": "Central Pier No.7 (Star Ferry)",
    "3474316428T20060926": "Central Pier No.8", "3467216382T20060926": "Central Piers 9-10",
    "3408016626T20050430": "Central Government Pier", "3541917205T20050430": "Star Ferry Pier (Tsim Sha Tsui)",
    "3620416053T20141003": "Wan Chai Ferry Pier",
}
PIER_WALL, PIER_ROOF, DECK_C, PILE_C = "#e3dcc8", "#5c7a73", "#a19e96", "#6f6c66"


def land_dir(c, reach=160.0):
    """The unit direction from c to the nearest land (scene ground over 1.5 m) and its distance."""
    best = None
    for a in np.radians(np.arange(0, 360, 10)):
        d_ = np.array([math.sin(a), math.cos(a)])
        for r_ in np.arange(10.0, reach, 4.0):
            p = c + d_ * r_
            if ground(p) > 1.5:
                if best is None or r_ < best[1]:
                    best = (d_, r_)
                break
    return best


for cs, nm in PIERS.items():
    M4L_EXCLUDE[cs] = f"{nm}: rebuilt on a piled deck"
    g, r = row(cs)
    c_p = np.array(g.centroid.coords[0])
    top = float(r.top_mpd) - PD
    deck = g.buffer(APRON, join_style=2)
    ld = land_dir(c_p)
    if ld is not None:
        d_, dist = ld
        far = g.buffer(APRON, join_style=2)
        from shapely.affinity import translate
        moved = translate(far, *(d_ * (dist + 6.0)))
        deck = unary_union([deck, unary_union([far, moved]).convex_hull])
    deck = deck.simplify(0.5)
    dl = [[round(x, 2), round(z, 2)] for x, z in (local(q, c_p) for q in list(deck.exterior.coords)[:-1])]
    bl = outline_local(g, c_p, simplify=0.5)
    piles = []
    sea_edge = g.buffer(APRON - 0.8, join_style=2).exterior
    for s_ in np.arange(0, sea_edge.length, 9.0):
        p = np.array(sea_edge.interpolate(s_).coords[0])
        if ground(p) < 0.5:
            x, z = local(p, c_p)
            piles.append([x, 0.5, z, 0.9, 5.0, 0.9, PILE_C])
    roof_h = min(3.5, max(1.5, 0.25 * (top - DECK)))
    figure(nm + " deck", c_p, 0.0, DECK_C, DECK, floor=0.0, prisms=[[dl, DECK - 1.0, DECK, DECK_C]], boxes=piles,
           note=f"{nm}: LandsD's row (top {r.top_mpd} mPD) on a piled deck at {DECK} m" if cs.startswith("3418") else None)
    figure(nm, c_p, 0.0, PIER_WALL, top, style="colonial", walls=True, floor=0.0,
           prisms=[[bl, DECK, top - roof_h, PIER_WALL]])
    # the roof its own plain figure (no wall runs: no windows on it), teal-green metal (research #5c7a73) with a white fascia
    figure(nm + " roof", c_p, 0.0, PIER_ROOF, top, floor=0.0,
           prisms=[[[[round(x * 1.01, 2), round(z * 1.01, 2)] for x, z in bl], top - roof_h, top - roof_h + 0.5, "#e8e6df"],
                   [[[round(x * 0.99, 2), round(z * 0.99, 2)] for x, z in bl], top - roof_h + 0.5, top, PIER_ROOF, 0.55]])

# ------------------------------------------------------------------ Stonecutters Bridge (in the ground margin)
# 1,596 m: a 1,018 m cable-stayed main span over the Rambler Channel between two 298 m single-column towers (concrete
# to 175 m, a stainless steel skin over the composite top), side spans of 289 m on piers; a twin steel box-girder deck
# (two boxes joined by cross girders, 51 m across) with 73.5 m clearance; the stays in two planes to the boxes' outer
# edges (src: Wikipedia; Arup). The axis from OSM's carriageways (raw/osm_roads.json, the ways named for it); the
# margin's roads aren't drawn, so the deck is the figure's too
ROADS = json.loads((DATA / "raw/osm_roads.json").read_text())["elements"]
sc = np.array([TO_UTM.transform(q["lon"], q["lat"]) for e in ROADS
               if "Stonecutters Bridge" in e.get("tags", {}).get("name", "") and e.get("geometry")
               for q in e["geometry"]])
c_sc = sc.mean(0)
w_, v_ = np.linalg.eigh(np.cov((sc - c_sc).T))
u_sc = v_[:, -1] if v_[0, -1] > 0 else -v_[:, -1]               # along the bridge, toward the east (Stonecutters Island)
t_ = (sc - c_sc) @ u_sc
L_SC = float(t_.max() - t_.min())
c_sc = c_sc + u_sc * 0.5 * (t_.max() + t_.min())               # the bridge's middle
fwd_sc = np.array([-u_sc[1], u_sc[0]])
face_sc = math.degrees(math.atan2(fwd_sc[0], fwd_sc[1])) % 360    # the frame's x runs along the bridge
SPAN, H_T, CLEAR = 1018.0, 298.0, 73.5
DECK_T = CLEAR + 4.0                                            # the deck's top at mid-span (box ~4 m deep, est.)
half = 0.5 * L_SC


def deck_y(x):
    """The deck's underside along the bridge (x from the middle): level over the main span with a slight crest,
    falling on the side spans to the approach viaducts (est.)."""
    a = abs(x)
    if a <= SPAN / 2:
        return CLEAR + 1.5 * (1 - (a / (SPAN / 2)) ** 2)
    return CLEAR - (CLEAR - 48.0) * ((a - SPAN / 2) / max(half - SPAN / 2, 1.0)) ** 1.3


xs = np.linspace(-half, half, 41)
GIRDER = "#9a9d9f"
slabs = []
for z0, z1 in ((-25.5, -6.5), (6.5, 25.5)):                     # the two boxes, a 13 m gap between (est.)
    bot = [[round(float(x), 1), round(deck_y(x), 2)] for x in xs]
    topl = [[round(float(x), 1), round(deck_y(x) + 4.0, 2)] for x in xs[::-1]]
    slabs.append([bot + topl, z0, z1, GIRDER])
tubes, prisms = [], []
for xt in (-SPAN / 2, SPAN / 2):
    secs = [(0.0, 12.0), (CLEAR, 9.5), (175.0, 6.4), (H_T, 3.6)]   # radius by height: tapering (est.)
    for (y0, r0), (y1, r1) in zip(secs, secs[1:]):
        prisms.append([ring(r0, 16, 0.0, xt, 0.0), y0, y1, "#c3c4c1" if y0 < 175 else "#d9dcde", r1 / r0])
    prisms.append([ring(14.0, 16, 0.0, xt, 0.0), -2.0, 4.0, "#8f8d87"])        # the pile cap at the waterline
    # the stays: two planes, a fan each way, anchored on the tower from 180 to 290 m, on the deck every ~ 36 m
    for zp in (-25.0, 25.0):
        for side in (-1, 1):
            n_st = 12
            for k in range(n_st):
                ya = 180.0 + (290.0 - 180.0) * k / (n_st - 1)
                reach = 30.0 + (SPAN / 2 - 40.0) * (1 + k) / n_st
                xd = xt + side * reach
                if abs(xd) > half - 20:
                    continue
                tubes.append([[xt, ya, zp * 0.12], [xd, deck_y(xd) + 4.0, zp], 0.35, "#e4e6e6"])
for xp in (-half + 70.0, -half + 140.0, -half + 210.0, half - 70.0, half - 140.0, half - 210.0):   # side-span piers
    prisms.append([rectangle(4.0, 20.0, xp, 0.0), -2.0, deck_y(xp), "#a9a8a3"])
figure("Stonecutters Bridge", c_sc, face_sc, "#c3c4c1", H_T, floor=0.0, slabs=slabs, prisms=prisms, tubes=tubes,
       note=f"Stonecutters Bridge (2009): {L_SC:.0f} m along OSM's carriageways, the 1,018 m main span, 298 m towers")
print(f"Stonecutters Bridge: {L_SC:.0f} m, axis {math.degrees(math.atan2(u_sc[0], u_sc[1])):.1f} deg, towers at "
      f"{[ll(c_sc + u_sc * x) for x in (-SPAN / 2, SPAN / 2)]}")

# ------------------------------------------------------------------ Tseung Kwan O Cross Bay Bridge: the arch
# The 200 m main span over the channel (OSM's two bridge=yes ways of the Cross Bay Link, 1117111652/3) carried by a
# steel arch over the deck (research: data/landmarks.md); the deck is 05b_roads' (its height read from roads.gpkg)
RD = gpd.read_file(DATA / "roads.gpkg")
arch = RD[RD.osm_id.astype(str).isin(["1117111652", "1117111653"])]
pts = np.vstack([np.array(gm.coords) for gm in arch.geometry])
c_cb = pts[:, :2].mean(0)
w_, v_ = np.linalg.eigh(np.cov((pts[:, :2] - c_cb).T))
u_cb = v_[:, -1]
t_ = (pts[:, :2] - c_cb) @ u_cb
L_CB = float(t_.max() - t_.min())
c_cb = c_cb + u_cb * 0.5 * (t_.max() + t_.min())
deck_cb = float(np.median(pts[:, 2]))
fwd_cb = np.array([-u_cb[1], u_cb[0]])
face_cb = math.degrees(math.atan2(fwd_cb[0], fwd_cb[1])) % 360
RISE = 45.0                                                     # the arch's rise over the deck (est.: 55-60 m on a ~20 m deck)
half_cb = 0.5 * L_CB
tubes = []
for zr in (-9.0, 9.0):                                          # two ribs either side of the carriageways (est.)
    # the two arch planes lean outward (~15 deg, research): the ribs spread apart toward the crown
    pts_a = [[round(float(x), 2), round(deck_cb + RISE * (1 - (x / half_cb) ** 2), 2),
              round(zr + math.copysign(0.27 * RISE * (1 - (x / half_cb) ** 2), zr), 2)] for x in np.linspace(-half_cb, half_cb, 17)]
    tubes += chain(pts_a, 1.3, "#e8e9e6")
    for x in np.linspace(-half_cb, half_cb, 17)[2:-2:2]:       # hangers
        k_ = 1 - (x / half_cb) ** 2
        tubes.append([[float(x), deck_cb + RISE * k_, zr + math.copysign(0.27 * RISE * k_, zr)], [float(x), deck_cb, zr], 0.12, "#d0d2d0"])
figure("Cross Bay Link arch", c_cb, face_cb, "#e8e9e6", deck_cb + RISE + 1.5, floor=0.0, tubes=tubes,
       note=f"Tseung Kwan O Cross Bay Bridge (2022): the arch over the {L_CB:.0f} m main span, the deck at {deck_cb:.1f} m (05b_roads)")

# ------------------------------------------------------------------ Bank of China Tower: the four triangular prisms
# I. M. Pei (1990). A 52 m square cut by both diagonals into four triangular prisms, each with one side of the square as
# its X-braced outer face, ending at four heights under a 45-degree glass roof rising from the outer wall's top to the
# centre (rise = half a side); the masts on the last one's apex (research r-hk-m4l, data/landmarks.md: floors 25, 38,
# 51-52, 70 at ~4.12 m: the north prism first, then the west, the east, the south to the roof at 315 m; masts 52.4 m to
# 367.4, Wikipedia). LandsD's row (its plaza ledge 56 m across) keeps the full square up to the first prism's wall top
# (city.toml fix_h BOC_BODY); the figure stands the prisms on it and draws the white frame (the corner columns, the
# X-bracing per ~52 m module on each outer face, the slopes' edges, the centre edge to 315 m) over all of it
BOC = "3468315577T20050430"
g, c_bc, _, base_bc = roof_of(BOC, 0.0)
_, u_bc, v_bc, L_bc, W_bc, brg_bc = rect(g)
# the frame's +z faces the outline side whose normal is nearest north (bearing ~17: the "north" face)
FACE = min(((brg_bc + k * 90.0) % 360 for k in range(4)), key=lambda b_: min(b_, 360 - b_))
A = 0.5 * 0.5 * (L_bc + W_bc) - 1.0                          # half a side: 1 m inside LandsD's ledge
BOC_BODY = 103.0                                              # floor 25: the north prism's wall top (fix_h)
TOPS = {"N": 103.0, "W": 157.0, "E": 213.0, "S": 288.0}       # outer walls' tops; each prism's apex + A (45 deg)
RISE = A
# (M7 carry-over, critic c-hk-m4-2: the frame lost above the lowest X, the glass near black: the members wider, a
# whiter aluminium, the glass a shade lighter)
GL, WH = "#6f8794", "#e6e9ea"
XR, HR = 0.95, 0.75                                            # X-bracing and horizontal members' radii (m)
corners = {"NW": (-A, A), "NE": (A, A), "SE": (A, -A), "SW": (-A, -A)}
quad = {"N": ("NW", "NE"), "E": ("NE", "SE"), "S": ("SE", "SW"), "W": ("SW", "NW")}
wedges = []
for q, (ca, cb) in quad.items():
    h = TOPS[q] - BOC_BODY
    (xa, za), (xb, zb) = corners[ca], corners[cb]
    wedges.append([[[xa, za, h], [xb, zb, h], [0.0, 0.0, h + RISE]], 0.0, GL])
figure("Bank of China Tower prisms", c_bc, FACE, GL, 315.0 - BOC_BODY, style="glass", variant=0.35, walls=True,
       floor=base_bc + BOC_BODY, wedges=wedges,
       note="Bank of China Tower (1990): the four triangular prisms over LandsD's row (fix_h 103 m), 315 m roof")
# the frame, from the ground: corner columns to the taller of their two faces, X-bracing per module on each outer
# face up to its wall top, the sloped roofs' edges, the centre edge to the roof; the two masts on a white truss base
MOD = [0.0, 51.5, 103.0, 157.0, 213.0, 250.5, 288.0]
OFF = 0.6
tubes = []
for q, (ca, cb) in quad.items():
    (xa, za), (xb, zb) = corners[ca], corners[cb]
    nx, nz = (xa + xb) / 2 / A, (za + zb) / 2 / A             # the face's outward normal
    pa = (xa + nx * OFF, za + nz * OFF)
    pb = (xb + nx * OFF, zb + nz * OFF)
    lv = [y for y in MOD if y <= TOPS[q] + 0.1]
    for y0, y1 in zip(lv, lv[1:]):
        tubes.append([[pa[0], y0, pa[1]], [pb[0], y1, pb[1]], XR, WH])
        tubes.append([[pb[0], y0, pb[1]], [pa[0], y1, pa[1]], XR, WH])
        tubes.append([[pa[0], y1, pa[1]], [pb[0], y1, pb[1]], HR, WH])
    # the slope's edges up to the centre
    tubes.append([[xa, TOPS[q], za], [0.0, TOPS[q] + RISE, 0.0], 0.45, WH])
    tubes.append([[xb, TOPS[q], zb], [0.0, TOPS[q] + RISE, 0.0], 0.45, WH])
for k, (x, z) in corners.items():
    hk = max(TOPS[q] for q, cs in quad.items() if k in cs)
    s_ = 1.0 + OFF
    tubes.append([[x * s_ / 1.0 if False else x + math.copysign(OFF, x), 0.0, z + math.copysign(OFF, z)],
                  [x + math.copysign(OFF, x), hk, z + math.copysign(OFF, z)], 1.1, WH])
tubes.append([[0.0, TOPS["W"] + RISE, 0.0], [0.0, 315.0, 0.0], 0.6, WH])       # the centre edge above the lower prisms
# the masts: two, ~4 m apart across the apex, on an ~8 m white truss base (est.)
MAST = 367.4
boxes = [[0.0, 315.0 + 3.0, -1.5, 6.0, 6.0, 4.0, WH]]
tubes += [[[-2.0, 315.0, -1.5], [-2.0, MAST - 3.4, -1.5], 0.7, WH], [[2.0, 315.0, -1.5], [2.0, MAST, -1.5], 0.7, WH],
          [[-2.0, MAST - 12.0, -1.5], [-2.0, MAST - 3.4, -1.5], 0.35, WH], [[2.0, MAST - 12.0, -1.5], [2.0, MAST, -1.5], 0.35, WH]]
figure("Bank of China Tower frame", c_bc, FACE, WH, MAST, floor=base_bc, tubes=tubes, boxes=boxes,
       note="Bank of China Tower: the white frame (corner columns, X-bracing, slope edges) and the masts to 367.4 m")

# ------------------------------------------------------------------ the Peak Tower: the wok
# Terry Farrell (1997): the bowl-shaped ("wok") roof, its long ends turned up, over a lower body; Sky Terrace 428 on
# the roof (428 mPD). LandsD's row (75 x 29 m, 377.8-425.4 mPD) excluded and rebuilt: the body inside the outline up
# to the wok's underside, the wok in elevation along the long (east-west) axis, extruded across
PK = "3348614712T20050430"
M4L_EXCLUDE[PK] = "the Peak Tower: rebuilt as a figure (the wok roof)"
g, r_pk = row(PK)
c_pk, u_pk, v_pk, L_pk, W_pk, brg_pk = rect(g)
base_pk = float(terrain().bases([g])[0])
TOP_PK = 428.0 - PD                                           # the upturned ends' tips (Sky Terrace 428)
MID_PK = float(r_pk.top_mpd) - PD - 3.0                       # the terrace in the middle (est.)
UND_PK = MID_PK - 9.0                                         # the bowl's underside in the middle (est.)
fwd_pk = np.array([-u_pk[1], u_pk[0]])
face_pk = math.degrees(math.atan2(fwd_pk[0], fwd_pk[1])) % 360   # x along the long axis
hx = 0.5 * L_pk + 4.0                                         # the wok overhangs the body's ends (est.)
xs_ = np.linspace(-hx, hx, 15)
topc = [[round(float(x), 2), round(MID_PK + (TOP_PK - MID_PK) * (abs(x) / hx) ** 3 - base_pk, 2)] for x in xs_]
botc = [[round(float(x), 2), round(UND_PK + (TOP_PK - 2.0 - UND_PK) * (abs(x) / hx) ** 2.2 - base_pk, 2)] for x in xs_[::-1]]
body = outline_local(g.buffer(-3.0, join_style=2), c_pk, face_pk, simplify=0.8)
# the body glazed (blue-green glass, three floors under the wok, the glass style's mullions; a flat blue read as paint)
figure("Peak Tower body", c_pk, face_pk, "#56707c", UND_PK - base_pk + 2.0, style="glass", walls=True, floor=base_pk,
       prisms=[[body, 0.0, UND_PK - base_pk + 2.0, "#56707c"]])
figure("Peak Tower", c_pk, face_pk, "#eeeeea", TOP_PK - base_pk, floor=base_pk,
       slabs=[[topc + botc, -0.5 * W_pk - 1.0, 0.5 * W_pk + 1.0, "#eeeeea"]],
       note="The Peak Tower (1997): the wok roof, its ends turned up to 428 mPD (LandsD's row excluded)")

# ------------------------------------------------------------------ Tamar: the Central Government Offices' open door
# LandsD draws the CGO as one 7,908 m² row at 121.3 m (a solid box). Rocco Design (2011): two wings, the west light
# blue-silver, the east dark grey louvred, joined over the "open door" by the top floors; research (data/landmarks.md,
# a harbour photo, est.): the opening ~28 m wide, from the podium up to ~75 m, the lintel to the roof. The row is
# excluded and rebuilt: the outline cut across its long axis into the west wing, the door and the east wing
CGO = "3508215732T20110704"
M4L_EXCLUDE[CGO] = "the Central Government Offices: rebuilt with the open door"
g, r_cg = row(CGO)
c_cg, u_cg, v_cg, L_cg, W_cg, brg_cg = rect(g)
base_cg = float(terrain().bases([g])[0])
H_CG = float(r_cg.top_mpd - r_cg.ground_mpd)
u_e = u_cg if u_cg[0] > 0 else -u_cg                          # along the long axis, toward the east
fwd_cg = np.array([-u_e[1], u_e[0]])                          # x along the long axis (east), z across (north-ish)
face_cg = math.degrees(math.atan2(fwd_cg[0], fwd_cg[1])) % 360
P_cg = Polygon(outline_local(g, c_cg, face_cg, simplify=0.5)).buffer(0)
DOOR_W, DOOR_TOP = 28.0, 75.0


def clip_x(P, x0, x1):
    q = P.intersection(Polygon([[x0, -500], [x1, -500], [x1, 500], [x0, 500]]))
    q = max(getattr(q, "geoms", [q]), key=lambda t: t.area)
    return [[round(x, 2), round(z, 2)] for x, z in list(q.exterior.coords)[:-1]]


# (M7 carry-over, critic c-hk-m4-2: the CGO read as dark glass) light silver-blue glass with white bands (the floors'
# sunshades), the east wing a lighter grey than the M4 #4d524d
prisms = [[clip_x(P_cg, -500, -DOOR_W / 2), 0.0, H_CG, "#cfd8da"], [clip_x(P_cg, DOOR_W / 2, 500), 0.0, H_CG, "#9aa2a3"],
          [clip_x(P_cg, -DOOR_W / 2, DOOR_W / 2), DOOR_TOP, H_CG, "#b4c4c9"]]
figure("Central Government Offices", c_cg, face_cg, "#b4c4c9", H_CG, style="bands", variant=0.8, walls=True, floor=base_cg,
       prisms=prisms, note="Central Government Offices, Tamar (2011): the two wings and the open door under the top floors")

# ------------------------------------------------------------------ Hong Kong Cultural Centre: the sloping roofs
# LandsD's Auditoria Building (9,150 m², 56.3 m: a flat box) excluded and rebuilt: the concert hall's and the grand
# theatre's windowless volumes under one sloping roof plane over the outline, low at the west (~22 m, the Clock Tower's
# side) and high at the east (56.3 m) (research: one harbour photo, medium-low confidence); pink-beige tiles
HC = "3560617222T20050430"
M4L_EXCLUDE[HC] = "the Cultural Centre's auditoria: rebuilt under the sloping roof"
g, r_hc = row(HC)
c_hc = np.array(g.centroid.coords[0])
base_hc = float(terrain().bases([g])[0])
H_HC = float(r_hc.top_mpd - r_hc.ground_mpd)
# (M4 fix round 1, critic c-hk-m456-1: "two curved ski-slope hall roofs") rebuilt as two halls side by side, the
# Concert Hall (west, to ~46 m) and the Grand Theatre (east, to the row's 56.3 m), each under its own roof curving down
# towards the harbour (south) to ~12 m like a ski slope (concave: steep at the top, flattening at the foot; the
# direction from the harbour views, medium confidence), a lower link (20 m) in a 6 m gap between them; the walls in
# the hk-hongkong preset's `tiled` style (pink ceramic tiles over a joint grid, a darker plinth). Each hall in 8
# strips across the slope (a wedge's heights are its outline's: a strip per step of the curve)
CC_PINK = "#d29a88"
P_hc = Polygon(outline_local(g, c_hc, simplify=0.6)).buffer(0)
x0_hc, z0_hc, x1_hc, z1_hc = P_hc.bounds
xm_hc = x0_hc + 0.48 * (x1_hc - x0_hc)


def ski(z, top, low=12.0, za=z0_hc, zb=z1_hc):
    t = min(max((z - za) / (zb - za), 0.0), 1.0)
    return low + (top - low) * t ** 1.7


wedges = []
for xa, xb, top in ((x0_hc - 1, xm_hc - 3.0, 46.0), (xm_hc + 3.0, x1_hc + 1, H_HC)):
    hall = P_hc.intersection(Polygon([[xa, -500], [xb, -500], [xb, 500], [xa, 500]]))
    hz0, hz1 = hall.bounds[1], hall.bounds[3]                   # (each hall's slope over its own depth)
    cuts = np.linspace(hz0 - 1, hz1 + 1, 9)
    for za, zb in zip(cuts, cuts[1:]):
        q = hall.intersection(Polygon([[-500, za], [500, za], [500, zb], [-500, zb]]))
        for pg in getattr(q, "geoms", [q]):
            if pg.geom_type != "Polygon" or pg.area < 4:
                continue
            pts = [[round(x, 2), round(z, 2), round(ski(z, top, za=hz0, zb=hz1), 2)] for x, z in list(pg.simplify(0.3).exterior.coords)[:-1]]
            wedges.append([pts, 0.0, CC_PINK])
link = P_hc.intersection(Polygon([[xm_hc - 3.0, -500], [xm_hc + 3.0, -500], [xm_hc + 3.0, 500], [xm_hc - 3.0, 500]]))
prisms = [[[[round(x, 2), round(z, 2)] for x, z in list(pg.exterior.coords)[:-1]], 0.0, 20.0, CC_PINK]
          for pg in getattr(link, "geoms", [link]) if pg.geom_type == "Polygon" and pg.area > 4]
figure("Hong Kong Cultural Centre", c_hc, 0.0, CC_PINK, H_HC, style="tiled", floor=base_hc, wedges=wedges, prisms=prisms, walls=True,
       note="Hong Kong Cultural Centre (1989): the Concert Hall and the Grand Theatre under their own ski-slope roofs, 46 and 56 m")

# ------------------------------------------------------------------ the Space Museum's dome (M7 carry-over)
# critic c-hk-m4-2: the dome missing beside the Cultural Centre. LandsD's dome row (a 46 m circle, 1,645 m²) stops at
# its 13 mPD drum; rebuilt as the egg-shaped dome from the ground (est. 26 m high; photos: a white tiled half-egg on a
# low drum, its foot ~4 m)
SM = "3575217258T20050430"
M4L_EXCLUDE[SM] = "the Space Museum's dome: rebuilt as a dome figure"
g, r_sm = row(SM)
c_sm = np.array(g.centroid.coords[0])
base_sm = float(terrain().bases([g])[0])
R_SM, DRUM_SM, H_SM = math.sqrt(g.area / math.pi), 4.0, 26.0
prisms = [[ring(R_SM, 32), 0.0, DRUM_SM, "#d9d6cf"]]
ks = np.linspace(0.0, 1.0, 9)
for k0, k1 in zip(ks, ks[1:]):
    r0, r1 = math.sqrt(max(1 - k0 ** 2, 0)), math.sqrt(max(1 - k1 ** 2, 0.02))
    prisms.append([ring(R_SM * r0, 32), round(DRUM_SM + (H_SM - DRUM_SM) * k0, 2), round(DRUM_SM + (H_SM - DRUM_SM) * k1, 2),
                   "#e8e6e0", round(r1 / r0, 4)])
figure("Hong Kong Space Museum dome", c_sm, 0.0, "#e8e6e0", H_SM, floor=base_sm, prisms=prisms,
       note="Hong Kong Space Museum (1980): the egg-shaped dome (est. 26 m) on its drum")

# ------------------------------------------------------------------ HKCEC: the wing roof
# The 1997 extension's "seagull": LandsD's New Wing row (45,615 m², 67.5 m) kept to the eaves (city.toml fix_h 28 m)
# and the roof drawn over it: a ridge along the long axis at 67.5 m, the wings sweeping down to the eaves either
# side (research: est. eaves 25-30 m); silver aluminium. Strips along the ridge, each a wedge (heights at its edges)
HK = "3587616033T20101020"
EAVE_HK = 28.0
g, r_hk = row(HK)
c_hk, u_hk, v_hk, L_hk, W_hk, brg_hk = rect(g)
base_hk = float(terrain().bases([g])[0])
H_HK = float(r_hk.top_mpd - r_hk.ground_mpd)
fwd_hk = u_hk                                                  # z along the ridge, x across
face_hk = math.degrees(math.atan2(fwd_hk[0], fwd_hk[1])) % 360
P_hk = Polygon(outline_local(g, c_hk, face_hk, simplify=1.5)).buffer(0)
xm = max(abs(P_hk.bounds[0]), abs(P_hk.bounds[2]))
wedges = []
cuts = np.linspace(P_hk.bounds[0], P_hk.bounds[2], 19)
for x0, x1 in zip(cuts, cuts[1:]):
    q = P_hk.intersection(Polygon([[x0, -500], [x1, -500], [x1, 500], [x0, 500]]))
    for pg in getattr(q, "geoms", [q]):
        if pg.geom_type != "Polygon" or pg.area < 5:
            continue
        pts = [[round(x, 2), round(z, 2), round(EAVE_HK + (H_HK - EAVE_HK) * (1 - (abs(x) / xm) ** 1.6), 2)]
               for x, z in list(pg.simplify(0.3).exterior.coords)[:-1]]
        # (M4 fix round 1: darker aluminium, #a9afb4, every other strip a shade darker: the roof's ridge lines; it was
        # a white blob from the overview at #c3c8cc)
        wedges.append([pts, EAVE_HK - 1.0, "#a9afb4" if len(wedges) % 2 else "#9ba1a6"])
figure("HKCEC wing roof", c_hk, face_hk, "#a9afb4", H_HK, floor=base_hk, wedges=wedges,
       note="Hong Kong Convention and Exhibition Centre extension (1997): the wing roof over LandsD's row (fix_h 28 m)")

# ------------------------------------------------------------------ M+: the LED facade frame
# Herzog & de Meuron (2021): the inverted T; the slab's harbour (south) face carries a 66 m LED screen (Dezeen) in a
# lighter margin; LandsD's slab row (109 x 12 m, 32.3-102.7 mPD) is the slab; the screen a thin box on its face
MP = "3444117991T20210408"
g, r_mp = row(MP)
c_mp, u_mp, v_mp, L_mp, W_mp, brg_mp = rect(g)
fwd_mp = v_mp if v_mp[1] < 0 else -v_mp                       # the south face
face_mp = math.degrees(math.atan2(fwd_mp[0], fwd_mp[1])) % 360
top_mp = float(r_mp.top_mpd) - PD
ymid = 0.5 * (32.3 - PD + top_mp)
figure("M+ LED facade", c_mp, face_mp, "#2b2e30", top_mp, floor=0.0,
       boxes=[[0.0, ymid, 0.5 * W_mp + 0.15, L_mp - 1.0, top_mp - 32.3 + PD - 1.0, 0.3, "#8a8d86"],
              [0.0, ymid, 0.5 * W_mp + 0.4, L_mp - 4.0, 66.0, 0.3, "#24272a"]],
       note="M+ (2021): the LED screen in its frame on the slab's harbour face (LandsD's slab row kept)")

# ================================================================== write
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("# generated by scripts/m4l_structures.py (edit the script, not this file): Hong Kong's landmark figures (M4)\n\n"
               + "\n".join(blocks))
print(f"{OUT}: {len(blocks)} figures")
for k, v in tri_est.items():
    print(f"  {k}: ~{v:,} triangles")
print(f"  total ~{sum(tri_est.values()):,}")
print("exclude BuildingCSUID:", json.dumps(sorted(M4L_EXCLUDE)))
