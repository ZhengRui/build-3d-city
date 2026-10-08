"""M4 (builder H): Berlin's historic landmarks, figures and station halls as [[structures]] figures, written to
generated/structures-m4h.toml (city.toml `include`s it; re-run after editing the numbers here; then 06_tiles):

- the Fernsehturm (its OSM stack and LoD2 solids are excluded in [buildings]): the tapering concrete shaft, the
  faceted steel sphere with its window band, the upper shaft and the red-white antenna to 368 m;
- the Brandenburg Gate (the LoD2 has only its attic as a raised roof: excluded): plinth, twelve Doric columns, the
  passage walls, entablature, attic and the copper-green Quadriga;
- the Reichstag's glass dome and four corner towers over the LoD2 body (28 m), the west portico;
- the Berliner Dom's drum, main dome, lantern and the four corner towers' cupolas over its 34 m body;
- the Rotes Rathaus tower's top (corner turrets and flagpole, 74 -> 94 m);
- the Siegessäule (its OSM parts excluded): red granite base, the column hall, the column with gilded bands, Victoria;
- the Gedächtniskirche's broken spire (61 -> 71 m), the Humboldt Forum's dome, the Gendarmenmarkt domes, St. Hedwig's
  dome, the Bode-Museum's dome, the Altes Museum's colonnade, the Konzerthaus portico;
- church steeples over the LoD2 towers (fix_h cuts them to the eave where the laser caught the spire's foot);
- the Oberbaumbrücke's towers (its U-Bahn arcade is [roads.piers]'), the Molecule Man, the East Side Gallery, the Kreuzberg monument;
- station halls on the Stadtbahn (Alexanderplatz, Zoologischer Garten, Ostbahnhof, Hackescher Markt, Warschauer
  Straße) as stepped vaults on their outlines at track level (the LoD2's hall roofs hanging over low bodies and
  OSM's skipped train_station fills).

Positions from the table (buildings.gpkg) and OSM (the local Overpass, cached in <data>/m4h_osm.json), heights from
landmarks_berlin.csv, Wikipedia and the photos (refs/). Run from demos/berlin: `uv run python scripts/m4h_structures.py`.
"""
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "berlin"
UTM = 32633
TO_UTM = Transformer.from_crs(4326, UTM, always_xy=True)
TO_LL = Transformer.from_crs(UTM, 4326, always_xy=True)
OVERPASS = "http://127.0.0.1:8793/api/interpreter"


def utm(lon, lat):
    return np.array(TO_UTM.transform(lon, lat))


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


def base_of(geom):
    """The lowest ground under a footprint (how 06_tiles stands a building)."""
    return float(terrain().bases([geom])[0])


def ring(r, n=8, phase=None, cx=0.0, cz=0.0):
    phase = math.pi / n if phase is None else phase
    return [[round(cx + r * math.cos(phase + 2 * math.pi * i / n), 3), round(cz + r * math.sin(phase + 2 * math.pi * i / n), 3)]
            for i in range(n)]


def square(h, cx=0.0, cz=0.0):
    return [[cx - h, cz - h], [cx + h, cz - h], [cx + h, cz + h], [cx - h, cz + h]]


def frame_of(facing):
    az = math.radians(facing)
    fwd = np.array([math.sin(az), math.cos(az)])
    return np.array([fwd[1], -fwd[0]]), fwd


def local(p, origin, facing=0.0):
    """UTM point p in a figure's frame (x right, z forward) at origin facing `facing`."""
    right, fwd = frame_of(facing)
    d = np.asarray(p, float) - origin
    return [round(float(d @ right), 3), round(float(d @ fwd), 3)]


def bearing(u):
    return math.degrees(math.atan2(u[0], u[1])) % 360


def rect(geom):
    """A footprint's rotated rectangle: centre, long unit u, short unit v, length, width."""
    r = geom.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e = [c[1] - c[0], c[2] - c[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    L, W = float(np.hypot(*e[i])), float(np.hypot(*e[1 - i]))
    u = e[i] / L
    return np.array(r.centroid.coords[0]), u, np.array([-u[1], u[0]]), L, W


blocks = []


def figure(name, at_utm, facing=0.0, colour="#b0b0b0", top=None, style="floodlit", variant=0.5, base=0.0, floor=None,
           sections=None, tubes=None, boxes=None, prisms=None, slabs=None, walls=False, segments=None, note=None, glazing=None):
    """floor: the figure's 0 at this absolute height (m) whatever the ground under its point."""
    if floor is not None:
        base = floor - ground(at_utm)
    ys = [s[0] for s in sections or []] + [p[2] for p in prisms or []] + [b[1] + b[4] / 2 for b in boxes or []] \
        + [max(t[0][1], t[1][1]) for t in tubes or []] + [max(q[1] for q in s[0]) for s in slabs or []]
    top = top or max(ys + [1.0])
    out = [f"# {line}" for line in (note or "").split("\n") if note]
    out += ["[[structures]]", 'kind = "figure"', f'name = "{name}"', "at = [%.7f, %.7f]" % tuple(ll(at_utm)), f"facing = {f(round(float(facing), 2))}",
            f'style = "{style}"', f"variant = {variant}", f'colour = "{colour}"', f"top = {f(round(float(top), 2))}"]
    if abs(base) > 1e-3:
        out.append(f"base = {f(round(float(base), 2))}")
    if walls:
        out.append("walls = true")
    if segments:
        out.append(f"segments = {int(segments)}")
    for key, v in (("sections", sections), ("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs)):
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


def osm_query():
    """OSM elements by id (ways with geometry), cached."""
    cache = DATA / "m4h_osm.json"
    have = json.loads(cache.read_text()) if cache.exists() else {}
    missing = [i for i in OSM_WAYS if str(i) not in have]
    if not missing:
        return have
    ids = ",".join(str(i) for i in missing)
    q = f"[out:json][timeout:90];way(id:{ids});out tags geom;"
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "3D-Fun berlin m4h"})
    els = json.loads(urllib.request.urlopen(req, timeout=120).read())["elements"]
    out = dict(have)
    out.update({str(e["id"]): {"tags": e.get("tags", {}), "geom": [[g["lon"], g["lat"]] for g in e["geometry"]]} for e in els})
    cache.write_text(json.dumps(out))
    return out


# OSM ways used here (outlines of things the table doesn't have, axes)
OSM_WAYS = {
    518071791: "Brandenburger Tor outline",
    20144781: "Bahnhof Alexanderplatz", 345095778: "Ostbahnhof platform hall", 345162607: "Ostbahnhof second hall",
    170063224: "S-Bahnhof Hackescher Markt", 297153147: "S Warschauer Straße station building",
    96955257: "Berlin Zoo Bhf. hall",
    155667532: "U1 on the Oberbaumbrücke (upper)", 155667537: "U1 on the Oberbaumbrücke (other track)",
    373626454: "Oberbaumbrücke tower part", 373626455: "Oberbaumbrücke tower part",
    166268035: "Molecule Man", 123011378: "East Side Gallery wall",
    208089016: "East Side Gallery wall", 448158193: "East Side Gallery wall", 448158194: "East Side Gallery wall",
    448172799: "East Side Gallery wall", 448172800: "East Side Gallery wall", 448173093: "East Side Gallery wall",
    373626459: "Oberbaumbrücke tower (34 m)", 1547500040: "Oberbaumbrücke tower (34 m)",
    11345963: "Hauptbahnhof east-west hall roof (west)", 226048334: "Hauptbahnhof east-west hall roof (east)",
    226048335: "Hauptbahnhof north-south hall roof",
    51688847: "St.-Thomas-Kirche", 110639235: "Ostkreuz Ringbahn hall",
}
OSM = osm_query()


def osm_poly(i):
    g = OSM[str(i)]["geom"]
    return Polygon([TO_UTM.transform(*q) for q in g])


def osm_line(i):
    return LineString([TO_UTM.transform(*q) for q in OSM[str(i)]["geom"]])


B = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)


def piece(gml):
    s = B[B.gml_id == gml]
    if not len(s):
        raise SystemExit(f"no table piece {gml}")
    return s.iloc[0]


def roof_abs(p):
    """A table piece's top, absolute (m), as 06_tiles stands it."""
    return base_of(p.geometry) + float(p.h)


STONE, SAND, GILT, COPPER = "#c8c2b0", "#bdb39c", "#c9a548", "#7e9b88"

# ------------------------------------------------------------------ the Fernsehturm
# OSM's shaft part (0-205 m, 100 m2) gives the centre. Wikipedia DE: 368 m; the concrete shaft 32 m wide at its
# foot (a 20 m hyperbolic cone with portholes), 16 m over it tapering to ~9 m under the sphere; the sphere 32 m across (centre ~213 m),
# its window band (deck 204 m, restaurant 208 m) dark; the shaft goes on above the sphere to ~250 m, then the
# antenna (red-white banded) to 368. The sphere's skin is pyramidal facets (stainless steel): 20 segments show them
ft = utm(13.4094205, 52.5208185)
osm_ft = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM) if (DATA / "osm_parts.gpkg").exists() else None
if osm_ft is not None and "osm_id" in osm_ft:
    sh = osm_ft[osm_ft.geometry.distance(Point(*ft)) < 15]
    sh = sh[sh.area.between(60, 140)]
    if len(sh):
        ft = np.array(sh.geometry.iloc[0].centroid.coords[0])
SHAFT, SPHERE, DARK = "#bdbdb8", "#b9bdc1", "#4b525b"
R0, CY = 16.0, 213.0
secs = [[0.0, 0, 0, 16.0, 16.0], [4.0, 0, 0, 12.6, 12.6], [10.0, 0, 0, 9.8, 9.8], [20.0, 0, 0, 8.0, 8.0], [60.0, 0, 0, 7.0, 7.0], [120.0, 0, 0, 5.8, 5.8], [186.0, 0, 0, 4.7, 4.7]]
figure("Fernsehturm shaft", ft, 0.0, SHAFT, 250.0, segments=24,
       sections=secs + [[198.0, 0, 0, 4.5, 4.5], [229.0, 0, 0, 3.4, 3.4], [248.0, 0, 0, 3.0, 3.0], [250.0, 0, 0, 2.2, 2.2]],
       note="The Fernsehturm (1969): 368 m (scripts/m4h_structures.py); its OSM parts and LoD2 solids are excluded in [buildings]")
# (M4 fix round) the sphere as stacked flat-sided frustums (24 sides; every other band turned half a facet): the
# stainless skin's pyramidal facets catch the light facet by facet instead of a smooth white ball; the window band
# (refs/fernsehturm/02-03: the deck's and the restaurant's windows) from 0.6 R under the equator to just over it
SPH2 = "#c3c8cd"
ts = np.linspace(-math.pi / 2 + 0.1, math.pi / 2 - 0.1, 15)
prisms = []
for i, (t0, t1) in enumerate(zip(ts, ts[1:])):
    y0, y1 = CY + R0 * math.sin(t0), CY + R0 * math.sin(t1)
    r0, r1 = R0 * math.cos(t0), R0 * math.cos(t1)
    ph = math.pi / 24 * (1 + (i % 2))
    prisms.append([ring(r0, 24, ph), round(y0, 2), round(y1, 2), SPHERE if i % 2 else SPH2, round(r1 / r0, 4)])
prisms.append([ring(R0 * math.cos(ts[-1]), 24), round(CY + R0 * math.sin(ts[-1]), 2), round(CY + R0, 2), SPH2, 0.0])
prisms.append([ring(R0 * math.cos(ts[0]) * 0.999, 24), round(CY - R0, 2), round(CY + R0 * math.sin(ts[0]), 2), SPHERE])
figure("Fernsehturm sphere", ft, 0.0, SPHERE, CY + R0, variant=0.6, prisms=prisms)
band = []
for y in (205.5, 207.5, 209.5, 211.5, 213.0):
    r = math.sqrt(max(R0 ** 2 - (y - CY) ** 2, 0)) + 0.3
    band.append([y, 0, 0, round(r, 2), round(r, 2)])
figure("Fernsehturm sphere windows", ft, 0.0, "#596068", 213.0, segments=24, variant=0.3, sections=band)
# the antenna: bands of red and white (the top 60 m), the lower mast pale
tubes = [[[0, 250.0, 0], [0, 290.0, 0], 1.5, "#d9d9d4"]]
ys = np.linspace(290.0, 366.0, 11)
for i, (a, b) in enumerate(zip(ys, ys[1:])):
    tubes.append([[0, round(a, 2), 0], [0, round(b, 2), 0], round(1.35 - 0.08 * i, 2), "#c23a30" if i % 2 == 0 else "#ecebe6"])
tubes.append([[0, 366.0, 0], [0, 368.0, 0], 0.35, "#c23a30"])
figure("Fernsehturm antenna", ft, 0.0, "#ecebe6", 368.0, tubes=tubes, variant=0.6,
       sections=[[249.0, 0, 0, 2.4, 2.4], [252.0, 0, 0, 2.4, 2.4], [252.0, 0, 0, 1.6, 1.6], [256.0, 0, 0, 1.6, 1.6]])

# ------------------------------------------------------------------ the Brandenburg Gate
# OSM's outline w518071791 (the gate with its steps); Wikipedia: 26 m to the Quadriga's top, 65.5 m wide with the
# Torhäuser (the LoD2's 10.8 m pieces, kept), 11 m deep, 20.3 m to the attic; six Doric columns per front, 13.5 m high,
# 1.73 m thick; five passages (the middle 5.65 m wide) between walls joining the column pairs; entablature, attic
# with a raised centre; the copper Quadriga facing east (to Pariser Platz)
g = osm_poly(518071791)
c, u, v, L, W = rect(g)
if v[0] < 0:                                       # forward: east, to Pariser Platz
    v = -v
face = bearing(v)
L, D = 35.0, min(W, 11.0)
xs = [-14.75, -9.22, -3.69, 3.69, 9.22, 14.75]    # column centres: 1.73 m columns, passages 5.65 / 3.8 m (WP)
zc = D / 2 - 1.3
# (M4 fix round: the critic read square slab piers, a flat attic and a green blob) twelve round fluted Doric
# columns (16 flat flutes, a shaft tapering a little, an echinus and abacus), the passage walls narrower than the
# columns and set back between the pairs, a profiled entablature (architrave, triglyph frieze, cornice), the
# stepped attic, and the Quadriga as four horse silhouettes, the chariot and Victoria
tubes, boxes, prisms = [], [], []
boxes.append([0, 0.6, 0, L + 1.0, 1.2, D + 1.0, "#b9b3a2"])
for x in xs:
    for z in (-zc, zc):
        prisms.append([ring(0.86, 16, 0.0, x, z), 1.2, 13.2, STONE, 0.88])
        prisms.append([ring(0.95, 16, 0.0, x, z), 13.2, 13.9, STONE, 1.12])          # echinus
        boxes.append([x, 14.15, z, 2.1, 0.5, 2.1, STONE])                            # abacus
    boxes.append([x, 7.6, 0, 1.0, 12.8, 2 * zc - 3.0, "#a59f8c"])        # the passage walls, behind the columns
boxes += [[-L / 2 + 0.9, 7.6, 0, 1.6, 12.8, D - 3.4, STONE], [L / 2 - 0.9, 7.6, 0, 1.6, 12.8, D - 3.4, STONE],   # the end walls
          [0, 15.1, 0, L + 1.0, 1.4, D + 0.6, STONE],                    # architrave
          [0, 16.45, 0, L + 1.2, 1.3, D + 0.8, "#b3ad9b"],               # triglyph frieze (shaded)
          [0, 17.25, 0, L + 2.0, 0.3, D + 1.6, STONE],                   # cornice, profiled in two
          [0, 17.55, 0, L + 2.4, 0.3, D + 2.0, "#cdc7b5"],
          [0, 18.35, 0, L - 1.0, 1.3, D - 0.6, STONE],                   # attic
          [0, 19.1, 0, L - 0.4, 0.25, D, "#cdc7b5"],                     # its coping
          [0, 19.75, 0, 20.0, 1.1, D - 1.6, STONE],                      # the stepped centre (the relief): 20.3 m (WP)
          [0, 20.3, 0, 8.0, 0.6, 5.5, "#b3ad9b"]]                         # the Quadriga's plinth
for x in xs[:-1]:                                                         # triglyphs: dark slots over the frieze
    for k in range(3):
        xt = x + (k + 1) * (xs[1] - xs[0]) / 4 if x < xs[2] or x >= xs[3] else x + (k + 1) * (xs[3] - xs[2]) / 4
        boxes.append([round(xt, 2), 16.45, 0, 0.35, 1.1, D + 0.9, "#8f8a7a"])
figure("Brandenburger Tor", c, face, STONE, 26.0, prisms=prisms, boxes=boxes, segments=16,
       note="The Brandenburg Gate (1791): the gate and the Quadriga (the LoD2 has only its attic: excluded in [buildings])")
# the Quadriga (refs/brandenburg-gate/04): in a frame turned 90 degrees (x' = back, so the horses' heads at -x';
# z' across the gate): four horses abreast drawn as side silhouettes 0.7 m thick, the chariot behind, Victoria
GR = "#6f9180"
HORSE = [[1.1, 0.0], [1.3, 0.0], [1.3, 1.2], [1.55, 1.6], [1.6, 2.05], [1.2, 2.3], [-0.6, 2.25], [-1.1, 2.9], [-1.35, 3.3],
         [-1.9, 3.1], [-1.95, 2.85], [-1.5, 2.75], [-1.05, 2.2], [-1.0, 1.6], [-1.6, 1.35], [-1.7, 1.05], [-1.5, 1.0],
         [-0.9, 1.25], [-0.8, 0.0], [-0.55, 0.0], [-0.55, 1.3], [0.85, 1.3]]
y0q = 20.6
slabs = []
for zq in (-2.4, -0.8, 0.8, 2.4):
    slabs.append([[[round(px * 1.15 - 0.6, 3), round(y0q + py * 1.15, 3)] for px, py in HORSE], zq - 0.35, zq + 0.35, GR])
# the chariot: a box with a round front, the wheels
slabs.append([[[1.6, y0q + 0.6], [3.0, y0q + 0.6], [3.0, y0q + 2.1], [2.0, y0q + 2.4], [1.6, y0q + 1.6]], -1.1, 1.1, GR])
slabs.append([[[round(2.3 + 0.7 * math.cos(a), 3), round(y0q + 0.7 + 0.7 * math.sin(a), 3)] for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)], -1.35, -1.15, GR])
slabs.append([[[round(2.3 + 0.7 * math.cos(a), 3), round(y0q + 0.7 + 0.7 * math.sin(a), 3)] for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)], 1.15, 1.35, GR])
tq = [[[2.4, y0q + 2.0, 0], [2.3, y0q + 4.2, 0], 0.42, GR],                  # Victoria
      [[2.2, y0q + 4.2, 0], [2.1, y0q + 4.9, 0], 0.26, GR],                  # her head
      [[2.2, y0q + 3.6, 0.3], [1.8, 26.0, 0.6], 0.07, GR],                    # the staff to ~26 m (WP) with the wreath
      [[1.75, 25.3, 0.35], [1.75, 25.3, 0.85], 0.32, GR],
      [[2.5, y0q + 3.8, 0.2], [3.0, y0q + 4.9, 1.6], 0.16, GR], [[2.5, y0q + 3.8, -0.2], [3.0, y0q + 4.9, -1.6], 0.16, GR]]   # the wings
figure("Brandenburger Tor Quadriga", c, (face + 90.0) % 360, GR, 26.0, slabs=slabs, tubes=tq)

# ------------------------------------------------------------------ the Reichstag
# the LoD2 body (28.1 m, DEBE01YYK0002MCN) is 137 x 97 m; the corner towers 46 m (WP; 21 m square, est. from photos),
# Foster's dome: 40 m across, 23.5 m high over the roof (to 47 m), a steel lattice of 24 ribs and 17 rings, glass;
# the west portico: six Corinthian columns, the pediment ("Dem deutschen Volke") to ~33 m
rb = piece("DEBE01YYK0002MCN")
c, u, v, L, W = rect(rb.geometry)
rt = roof_abs(rb)
gr = ground(c)
roof = rt - gr                                     # the body's roof over the ground at the centre
DOME, RIB = "#dfe3e4", "#c9cfd2"
# (M4 fix round: the critic read an opaque grey-blue ball) the glass as a see-through `glazing` sheet (the lattice
# mesh: light steel members, 24 ribs and 17 rings, over panes that let most of the light through), the mirror cone
# inside it, the ring at the top opening, the ribs and the base ring as solid tubes
prof = [(roof + 23.5 * t, 20.0 * math.sqrt(max(1 - t ** 2.2, 0.0)) if t < 1 else 5.0) for t in np.linspace(0, 1, 17)]
prof = [(y, max(r, 5.0)) for y, r in prof]
grid = [[[round(r * math.cos(2 * math.pi * k / 48), 2), round(y, 2), round(r * math.sin(2 * math.pi * k / 48), 2)] for k in range(49)] for y, r in prof]
cone = [[roof + 1.0, 0, 0, 1.4, 1.4], [roof + 5.0, 0, 0, 2.0, 2.0], [roof + 12.0, 0, 0, 4.2, 4.2], [roof + 17.0, 0, 0, 7.6, 7.6], [roof + 17.6, 0, 0, 0.2, 0.2]]
tubes = []
for k in range(24):
    a_ = 2 * math.pi * k / 24
    for (y0, r0), (y1, r1) in zip(prof[::2], prof[2::2]):
        tubes.append([[round((r0 + 0.15) * math.cos(a_), 2), round(y0, 2), round((r0 + 0.15) * math.sin(a_), 2)],
                      [round((r1 + 0.15) * math.cos(a_), 2), round(y1, 2), round((r1 + 0.15) * math.sin(a_), 2)], 0.2, RIB])
ringy = [[round(20.3 * math.cos(2 * math.pi * k / 40), 2), roof + 0.3, round(20.3 * math.sin(2 * math.pi * k / 40), 2)] for k in range(41)]
tubes += [[p0, p1, 0.45, "#b9bfc2"] for p0, p1 in zip(ringy, ringy[1:])]
topy = [[round(5.2 * math.cos(2 * math.pi * k / 16), 2), roof + 23.5, round(5.2 * math.sin(2 * math.pi * k / 16), 2)] for k in range(17)]
tubes += [[p0, p1, 0.35, "#b9bfc2"] for p0, p1 in zip(topy, topy[1:])]
figure("Reichstag dome glass", c, 0.0, "#b7c0c4", roof + 23.6, sections=cone, segments=24, variant=0.6, tubes=tubes,
       glazing=[{"grid": grid, "period": [5.2, 1.5], "colour": DOME}],
       note="The Reichstag's dome (Foster, 1999): 40 m across, 47 m to its top; the corner towers 46 m")
prisms = []
for su in (-1, 1):
    for sv in (-1, 1):
        q = c + u * su * (L / 2 - 10.5) + v * sv * (W / 2 - 10.5)
        x, z = local(q, c)
        hw = 10.5
        corners = [c + u * su * (L / 2 - 10.5) + v * sv * (W / 2 - 10.5) + u * a * hw + v * b * hw for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        prisms.append([[local(p, c) for p in corners], 0.0, roof + 15.0, "#bdb39d"])
        sm = [c + u * su * (L / 2 - 10.5) + v * sv * (W / 2 - 10.5) + u * a * 6.0 + v * b * 6.0 for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        prisms.append([[local(p, c) for p in sm], roof + 15.0, roof + 18.0, "#b3a990"])
figure("Reichstag corner towers", c, 0.0, "#bdb39d", roof + 18.0, style="monument", variant=0.3, prisms=prisms, walls=True)
# the west portico (the long side facing west: the Platz der Republik)
wv = u if u[0] < 0 else -u
if abs(u[0]) < abs(v[0]):
    wv = v if v[0] < 0 else -v
half = (L if abs(u @ wv) > 0.5 else W) / 2
pc = c + wv * (half + 3.5)
fw = bearing(wv)
tubes = [[[x, 5.0, 0.0], [x, roof - 3.0, 0.0], 1.0, "#c4bba5"] for x in np.linspace(-12.5, 12.5, 6)]
figure("Reichstag west portico", pc, fw, "#c4bba5", roof + 6.0, variant=0.4, tubes=tubes,
       boxes=[[0, 2.5, -1.0, 34.0, 5.0, 12.0, "#b3aa95"], [0, roof - 1.5, -1.0, 32.0, 3.0, 9.0, "#c4bba5"],
              [0, roof - 1.5, 3.55, 17.0, 0.9, 0.1, "#3d3a33"]],     # the bronze letters "Dem Deutschen Volke"
       slabs=[[[[-16.0, roof], [16.0, roof], [0.0, roof + 6.0]], -5.0, 2.5, "#c4bba5"]])

# ------------------------------------------------------------------ the Berliner Dom
# the LoD2 body (DEBE01YYK000000D, 33.7 m at the cornice after the M2 fix round); Wikipedia DE: 98 m to the lantern's
# cross, the main dome ~33 m across on a drum with paired columns; four corner towers with small domes and lanterns
# (WP: cut by 16 m after the war: ~60 m, est.); verdigris domes, dark Silesian sandstone
db = piece("DEBE01YYK000000D")
c, u, v, L, W = rect(db.geometry)
roof = roof_abs(db) - ground(c)
dc = c + 0.0 * u                                   # the dome over the Predigtkirche: the body's centre (photos)
DS, GD = "#8b877d", "#6f9486"
tubes = []
for k in range(16):
    a = 2 * math.pi * (k + 0.5) / 16
    for da in (-0.05, 0.05):
        tubes.append([[round(17.6 * math.cos(a + da), 2), roof, round(17.6 * math.sin(a + da), 2)],
                      [round(17.6 * math.cos(a + da), 2), roof + 16.0, round(17.6 * math.sin(a + da), 2)], 0.55, DS])
secs = [[roof - 1.0, 0, 0, 16.6, 16.6], [roof + 17.5, 0, 0, 16.6, 16.6], [roof + 17.5, 0, 0, 17.8, 17.8], [roof + 19.0, 0, 0, 17.8, 17.8],
        [roof + 19.0, 0, 0, 16.4, 16.4]]
figure("Berliner Dom drum", dc, 0.0, DS, roof + 19.0, sections=secs, tubes=tubes, segments=32, variant=0.3,
       note="The Berliner Dom (1905): drum, main dome, lantern to 98 m and the corner towers' cupolas over the LoD2 body")
dome = []
for t in np.linspace(0.0, 1.0, 10):
    a = t * math.pi / 2
    dome.append([round(roof + 19.0 + 26.0 * math.sin(a), 2), 0, 0, round(max(16.4 * math.cos(a), 3.2), 2), round(max(16.4 * math.cos(a), 3.2), 2)])
figure("Berliner Dom dome", dc, 0.0, GD, roof + 45.0, sections=dome, segments=32, variant=0.4)
ly = roof + 45.0
tip = 98.0 - (ground(dc) - base_of(db.geometry)) * 0.0        # 98 m over the street (Wikipedia)
figure("Berliner Dom lantern", dc, 0.0, GD, tip, variant=0.4, segments=12,
       sections=[[ly - 0.5, 0, 0, 3.2, 3.2], [ly + 7.0, 0, 0, 3.0, 3.0], [ly + 7.0, 0, 0, 3.6, 3.6], [ly + 8.0, 0, 0, 3.6, 3.6],
                 [ly + 10.0, 0, 0, 2.2, 2.2], [ly + 13.0, 0, 0, 0.9, 0.9], [ly + 15.5, 0, 0, 0.5, 0.5], [ly + 16.2, 0, 0, 0.8, 0.8],
                 [ly + 17.0, 0, 0, 0.12, 0.12], [max(tip, ly + 18.5), 0, 0, 0.1, 0.1]],
       tubes=[[[-0.9, max(tip, ly + 18.5) - 1.2, 0], [0.9, max(tip, ly + 18.5) - 1.2, 0], 0.12, GILT]])
# the four corner towers (est. from photos berliner-dom/03: square stone stages over the cornice, a ribbed copper
# cupola, a lantern; ~60 m)
for su in (-1, 1):
    for sv in (-1, 1):
        q = c + u * su * (L / 2 - 8.5) + v * sv * (W / 2 - 8.5)
        figure(f"Berliner Dom tower {su:+d}{sv:+d}", q, bearing(u), GD, roof + 26.0, variant=0.4, segments=16,
               prisms=[[square(6.0), roof - 2.0, roof + 9.0, DS], [square(6.4), roof + 8.2, roof + 9.0, DS]],
               sections=[[roof + 9.0, 0, 0, 5.4, 5.4], [roof + 11.0, 0, 0, 5.4, 5.4], [roof + 14.0, 0, 0, 4.4, 4.4], [roof + 16.0, 0, 0, 2.2, 2.2],
                         [roof + 16.5, 0, 0, 1.2, 1.2], [roof + 21.0, 0, 0, 1.0, 1.0], [roof + 22.5, 0, 0, 0.4, 0.4], [roof + 26.0, 0, 0, 0.06, 0.06]])

# ------------------------------------------------------------------ the Rotes Rathaus tower's top
# the tower solid (DEBE3DgmfpurHZfT) is cut to its 74 m parapet (fix_h); the photos (rotes-rathaus/03): the gallery's
# parapet with four corner turrets, a flag pole from the roof to 94 m
rr = piece("DEBE3DgmfpurHZfT")
c, u, v, L, W = rect(rr.geometry)
top = roof_abs(rr) - ground(c)
fr = bearing(u)
hx, hz = W / 2, L / 2
# (M4 fix round: the critic read a plain box) refs/rotes-rathaus/03: on each face of the tower's top stage a big round
# arch with the clock in its head, paired tall arched windows under it, the corners' open arcaded turrets (tall
# narrow arches), a corbelled parapet; the flat top with its lattice mast and the Berlin flag (white, red bands)
BRK, DK, CLK = "#b0643f", "#2a2522", "#e2ddd0"


def arch(x0, x1, y0, y1, n=8):
    """A round-headed opening's outline in an elevation, from y0 to the crown y1."""
    r = (x1 - x0) / 2
    xc, ys = (x0 + x1) / 2, y1 - r
    return [[round(x0, 3), round(y0, 3)], [round(x1, 3), round(y0, 3)]] + \
        [[round(xc + r * math.cos(a), 3), round(ys + r * math.sin(a), 3)] for a in np.linspace(0, math.pi, n)[1:-1]] + \
        [[round(x0, 3), round(ys, 3)]]


for k in range(4):                                       # the four faces: a figure each, facing out of that face
    fb = (fr + 90.0 * k) % 360
    half_w, half_d = (hx, hz) if k % 2 == 0 else (hz, hx)
    zf = half_d                                          # the face's plane
    slabs = []
    w = half_w * 2
    slabs.append([arch(-w * 0.27, w * 0.27, top - 21.0, top - 5.0), zf - 0.05, zf + 0.25, DK])          # the big arch
    slabs.append([[[round(1.9 * math.cos(a), 3), round(top - 9.0 + 1.9 * math.sin(a), 3)] for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)], zf + 0.25, zf + 0.4, CLK])
    for xw in (-0.11, 0.11):                              # paired windows under it
        slabs.append([arch(w * xw - 0.75, w * xw + 0.75, top - 34.0, top - 23.0), zf - 0.05, zf + 0.25, DK])
    for xs_ in (-1, 1):                                   # the corner turrets' open arcades, two stages
        for y0_, y1_ in ((top - 33.0, top - 22.0), (top - 19.0, top - 6.0)):
            xa = -half_w + 0.4 if xs_ < 0 else half_w - 1.5
            slabs.append([arch(xa, xa + 1.1, y0_, y1_), zf - 0.05, zf + 0.25, DK])
    slabs.append([[[-half_w - 0.3, top - 3.5], [half_w + 0.3, top - 3.5], [half_w + 0.3, top - 1.5], [-half_w - 0.3, top - 1.5]], zf - 0.6, zf + 0.5, "#c9b9a0"])   # the stone band
    figure(f"Rotes Rathaus tower face {k}", c, fb, BRK, top + 1.0, slabs=slabs, variant=0.4,
           note="The Rotes Rathaus: the tower's top stage (arches, clock, turrets' arcades), flat top, mast and flag" if k == 0 else None)
prisms = [[[[-hx - 0.3, -hz - 0.3], [hx + 0.3, -hz - 0.3], [hx + 0.3, hz + 0.3], [-hx - 0.3, hz + 0.3]], top - 0.4, top + 1.6, BRK]]
for sx in (-1, 1):
    for sz in (-1, 1):
        prisms.append([square(1.1, sx * (hx - 0.6), sz * (hz - 0.6)), top - 0.4, top + 2.6, BRK])
# the mast: a slim lattice frame (four posts) to ~12 m over the roof, the pole to 20 m, the flag 4 x 2.4 m
tubes = [[[sx * 0.9, top + 1.6, sz * 0.9], [sx * 0.25, top + 11.0, sz * 0.25], 0.09, "#3b3e40"] for sx in (-1, 1) for sz in (-1, 1)]
tubes += [[[0, top + 1.6, 0], [0, top + 20.0, 0], 0.12, "#d9d9d6"]]
boxes = [[2.05, top + 18.0, 0, 4.0, 2.4, 0.08, "#ece9e2"], [2.05, top + 18.95, 0, 4.0, 0.5, 0.1, "#c4322d"], [2.05, top + 17.05, 0, 4.0, 0.5, 0.1, "#c4322d"]]
figure("Rotes Rathaus tower top", c, fr, BRK, top + 20.0, prisms=prisms, tubes=tubes, boxes=boxes, variant=0.4)

# ------------------------------------------------------------------ the Siegessäule
# OSM's parts (w718035022, excluded): the red granite base 0-9.2 m (24.9 m square), the column hall 9.2-18 m (its
# floor and roof discs 17.3 m across, a 7.9 m core; 16 granite columns), the drum and capital to 58.6, Victoria (8.3 m,
# gilded) to 66.9 m (Wikipedia). The column's three drums are decorated with gilded cannon barrels: gilt bands
sg = utm(13.3501, 52.51451)
if osm_ft is not None and "osm_id" in osm_ft:
    s_ = osm_ft[osm_ft.geometry.distance(Point(*sg)) < 25]
    s_ = s_[s_.area.between(500, 700)]
    if len(s_):
        sg = np.array(s_.geometry.iloc[0].centroid.coords[0])
RED, GRAN, SST = "#8a5446", "#8c8378", "#a39478"
prisms = [[square(16.0), 0.0, 0.8, "#9c958a"], [square(12.45), 0.8, 2.0, "#9c958a"], [square(9.4), 2.0, 8.6, RED],
          [square(9.8), 8.6, 9.2, RED], [ring(8.67, 24), 9.2, 11.2, GRAN], [ring(3.95, 16), 11.2, 15.9, "#7e6f5d"],
          [ring(8.8, 24), 15.9, 18.0, GRAN], [ring(3.5, 16), 18.0, 20.5, SST], [ring(2.7, 16), 20.5, 22.0, SST],
          [ring(3.1, 16), 22.0, 23.0, SST], [ring(2.7, 16), 23.0, 24.5, GILT]]
y = 24.5
for k in range(4):
    prisms.append([ring(2.52, 16), y, y + 6.0, SST])
    prisms.append([ring(2.75, 16), y + 6.0, y + 7.0, GILT])
    y += 7.0
# (24.5 + 28 = 52.5) the capital and Victoria's drum
prisms += [[ring(3.2, 16), 52.5, 54.6, "#b49a62"], [ring(1.5, 12), 54.6, 58.6, SST]]
tubes = [[[8.0 * math.cos(2 * math.pi * k / 16), 11.2, 8.0 * math.sin(2 * math.pi * k / 16)],
          [8.0 * math.cos(2 * math.pi * k / 16), 15.9, 8.0 * math.sin(2 * math.pi * k / 16)], 0.38, GRAN] for k in range(16)]
tubes += [[[0, 58.6, 0], [0, 64.8, 0], 0.75, GILT], [[0, 64.6, 0], [0, 65.6, 0], 0.4, GILT],
          [[0, 63.0, -0.2], [-2.6, 66.0, -1.2], 0.35, GILT], [[0, 63.0, -0.2], [2.6, 66.0, -1.2], 0.35, GILT],
          [[0.3, 62.5, 0.3], [0.5, 66.9, 0.8], 0.08, GILT]]
figure("Siegessäule", sg, 0.0, SST, 66.9, prisms=prisms, tubes=tubes, variant=0.5,
       note="The Siegessäule (1873): 66.9 m with the Victoria (OSM's parts excluded in [buildings])")

# ------------------------------------------------------------------ the Gedächtniskirche's broken spire
# the ruined west tower (LoD2 DEBE3DfxQf2emt43, 61.4 m, eave 58.3): the spire's broken stump to 71 m (photos
# gedaechtniskirche/01-02: a jagged, hollow helm of verdigris copper over the belfry)
kw = piece("DEBE3DfxQf2emt43")
c, u, v, L, W = rect(kw.geometry)
top = roof_abs(kw) - ground(c)
eave = float(kw.eave_h) - (ground(c) - base_of(kw.geometry))
fk = bearing(u)
# (M4 fix round: the critic read an intact tower under a neat green pyramid) the "Hohler Zahn" (refs
# gedaechtniskirche/01-02): the belfry's walls broken off in a jagged, roofless crown of dark weathered stone, the
# stumps of the corner pinnacles, the hollow helm's last ribs rising from inside, the clock faces under the belfry
RUIN, RIB_K, CLK = "#5f5a53", "#4d524e", "#c9c2ae"
rng = np.random.default_rng(7)
for k in range(4):
    fb = (fk + 90.0 * k) % 360
    hw, hd = (W / 2, L / 2) if k % 2 == 0 else (L / 2, W / 2)
    # a jagged top: the wall rises and falls in broken steps between the corners (higher at the corners)
    xs_ = np.linspace(-hw, hw, 9)
    tops = [top + 6.5 + rng.uniform(-1.0, 1.5)] + [top + rng.uniform(-1.5, 4.5) for _ in xs_[1:-1]] + [top + 7.5 + rng.uniform(-1.0, 1.5)]
    outline = [[round(-hw, 2), round(eave - 2.0, 2)], [round(hw, 2), round(eave - 2.0, 2)]]
    for x_, y_ in zip(xs_[::-1], tops[::-1]):
        outline.append([round(float(x_), 2), round(float(y_), 2)])
        outline.append([round(float(x_) - 0.6 * (1 if x_ > -hw else 0), 2), round(float(y_) - rng.uniform(0.6, 2.0), 2)])
    outline = outline[:-1]
    slabs = [[outline, hd - 1.6, hd + 0.2, RUIN]]
    # the clock face (a pale disc with a dark rim) under the belfry
    cy_ = eave - 16.0
    slabs.append([[[round(2.4 * math.cos(a), 3), round(cy_ + 2.4 * math.sin(a), 3)] for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)], hd + 0.2, hd + 0.35, "#3e3a35"])
    slabs.append([[[round(2.0 * math.cos(a), 3), round(cy_ + 2.0 * math.sin(a), 3)] for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)], hd + 0.35, hd + 0.45, CLK])
    figure(f"Gedächtniskirche ruin crown {k}", c, fb, RUIN, top + 9.0, slabs=slabs, variant=0.4,
           note="The Kaiser-Wilhelm-Gedächtniskirche: the ruin's broken crown and clock faces (to ~71 m)" if k == 0 else None)
tubes = []
for (px, pz, h) in ((-0.42, -0.35, 9.5), (0.38, -0.3, 7.0), (0.32, 0.4, 8.5), (-0.36, 0.38, 6.0), (0.05, -0.42, 6.5)):
    tubes.append([[px * W, top - 1.0, pz * L], [px * W * 0.75, top + h, pz * L * 0.75], 0.55, RIB_K])
prisms = [[square(1.4, sx * (W / 2 - 1.2), sz * (L / 2 - 1.2)), eave - 2.0, top + 4.0 + 3.0 * ((sx + sz + 2) % 3) / 2, RUIN, 0.5]
          for sx in (-1, 1) for sz in (-1, 1)]
figure("Gedächtniskirche spire stump", c, fk, RUIN, top + 9.5, variant=0.4, tubes=tubes, prisms=prisms)

# ------------------------------------------------------------------ the Humboldt Forum's dome
# the LoD2 body (DEBE3DZbK4bVp6Kb, 31.2 m); the dome over the west portal (Eosander's, on Schlossfreiheit): an
# octagonal drum, the copper dome and lantern with the cross to ~70 m (est.)
hf = piece("DEBE3DZbK4bVp6Kb")
c, u, v, L, W = rect(hf.geometry)
wv = -u if u[0] > 0 else u                         # west along the long axis
roof = roof_abs(hf) - ground(c)
dc = c + wv * (L / 2 - 17.0)
roof = roof_abs(hf) - ground(dc)
# (M4 fix round: the critic read an octagonal drum tower with a flat top and a tiny lantern) refs/humboldt-forum/02,
# 06: a low octagonal drum with paired columns at its corners, a large ribbed copper-green dome (octagonal, eight ribs),
# the open lantern with its gilt cupola and cross to 70 m (WP)
CU, CUR = "#6f9487", "#89aa9c"
# the LoD2's drum (DEBE3DzLpp1avSfB, 444 m2, eave 50.6, a flat top at 59.6 m) stays as the drum, cut to its eave by the
# landmark row (h@59.6=50.6; the Umweltatlas's 53.2 m block over it likewise); paired columns round it, a cornice,
# the dome from its eave
dp = piece("DEBE3DzLpp1avSfB")
dc = np.array(dp.geometry.centroid.coords[0])
rd = math.sqrt(dp.geometry.area / math.pi)
g0 = base_of(dp.geometry) - ground(dc)
eave = g0 + float(dp.eave_h)
roof = roof_abs(hf) - ground(dc)
figure("Humboldt Forum drum", dc, bearing(wv), "#d2bb8f", eave + 1.2, variant=0.3,
       prisms=[[ring(rd + 0.9, 8, math.pi / 8), eave - 1.0, eave + 0.6, "#d9c59c"], [ring(rd + 0.3, 8, math.pi / 8), eave + 0.6, eave + 1.2, "#d2bb8f"]],
       tubes=[[[round((rd + 0.6) * math.cos(math.pi / 8 + 2 * math.pi * k / 8 + d), 2), roof, round((rd + 0.6) * math.sin(math.pi / 8 + 2 * math.pi * k / 8 + d), 2)],
               [round((rd + 0.6) * math.cos(math.pi / 8 + 2 * math.pi * k / 8 + d), 2), eave - 1.0, round((rd + 0.6) * math.sin(math.pi / 8 + 2 * math.pi * k / 8 + d), 2)], 0.45, "#e0d3b4"]
              for k in range(8) for d in (-0.06, 0.06)],
       note="The Humboldt Forum: the dome over the west portal on the LoD2's drum (cross 70 m, WP)")
prof = [(0.0, rd), (0.2, rd * 0.98), (0.4, rd * 0.92), (0.55, rd * 0.83), (0.7, rd * 0.68), (0.82, rd * 0.5), (0.92, rd * 0.33), (1.0, 2.5)]
H = 11.0
dome = [[round(eave + 1.2 + H * t, 2), 0, 0, round(r, 2), round(r, 2)] for t, r in prof]
ly = eave + 1.2 + H
tip = 70.0                                         # the cross: 70 m over the street (WP)
dome += [[ly, 0, 0, 2.5, 2.5], [ly + 3.0, 0, 0, 2.3, 2.3], [ly + 3.0, 0, 0, 2.7, 2.7], [ly + 3.4, 0, 0, 2.7, 2.7], [ly + 4.2, 0, 0, 2.0, 2.0], [ly + 5.2, 0, 0, 0.8, 0.8],
         [ly + 5.8, 0, 0, 0.3, 0.3], [ly + 6.2, 0, 0, 0.05, 0.05]]
ribs = []
for k in range(8):
    a_ = math.pi / 8 + 2 * math.pi * k / 8
    for (t0, r0), (t1, r1) in zip(prof, prof[1:]):
        ribs.append([[round((r0 + 0.1) * math.cos(a_), 2), round(eave + 1.2 + H * t0, 2), round((r0 + 0.1) * math.sin(a_), 2)],
                     [round((r1 + 0.1) * math.cos(a_), 2), round(eave + 1.2 + H * t1, 2), round((r1 + 0.1) * math.sin(a_), 2)], 0.35, CUR])
top_c = max(ly + 8.5, tip)
figure("Humboldt Forum dome", dc, bearing(wv), CU, ly, sections=dome[:len(prof)], segments=8, variant=0.4, tubes=ribs)
figure("Humboldt Forum lantern", dc, bearing(wv), GILT, top_c, sections=dome[len(prof):], segments=8, variant=0.5,
       tubes=[[[0, ly + 5.8, 0], [0, top_c, 0], 0.13, GILT], [[-0.8, top_c - 1.0, 0], [0.8, top_c - 1.0, 0], 0.11, GILT]] +
             [[[round(2.5 * math.cos(2 * math.pi * k / 8), 2), ly, round(2.5 * math.sin(2 * math.pi * k / 8), 2)],
               [round(2.5 * math.cos(2 * math.pi * k / 8), 2), ly + 3.0, round(2.5 * math.sin(2 * math.pi * k / 8), 2)], 0.2, "#d9c59c"] for k in range(8)])
roof = roof_abs(hf) - ground(c)
# the west portal (Eosander's triumphal arch, Portal III) on the west front, under the dome: a projecting frontispiece
# with four giant paired columns, the arch's dark opening
pts = np.array([q for g_ in getattr(hf.geometry, "geoms", [hf.geometry]) for q in g_.exterior.coords])
dw = float(((pts - c) @ wv).max())
pw = c + wv * dw
fw = bearing(wv)
figure("Humboldt Forum west portal", pw, fw, "#d2bb8f", roof + 2.0, style="monument", variant=0.3, walls=True,
       prisms=[[[[-12.0, -0.5], [12.0, -0.5], [12.0, 3.0], [-12.0, 3.0]], 0.0, roof + 1.0, "#d2bb8f"]],
       slabs=[[[[-4.2, 0.0], [4.2, 0.0], [4.2, 13.0]] + [[round(4.2 * math.cos(a), 2), round(13.0 + 4.2 * math.sin(a), 2)] for a in np.linspace(0, math.pi, 9)[1:-1]] + [[-4.2, 13.0]], 3.0, 3.2, "#2f2b26"]],
       tubes=[[[x, 1.0, 4.2], [x, roof - 5.5, 4.2], 0.85, "#dccaa4"] for x in (-9.5, -6.8, 6.8, 9.5)],
       boxes=[[0, roof - 4.5, 3.0, 25.0, 2.2, 3.6, "#d9c59c"]])
# the Spree front (Stella's modern east facade, refs/humboldt-forum/01): grey stone in a regular grid of deep openings
ev = -wv
de = float(((pts - c) @ ev).max())
pe = c + ev * de
figure("Humboldt Forum east facade", pe, bearing(ev), "#b9b5aa", roof, style="neubau", variant=0.4, walls=True,
       prisms=[[[[-W / 2 + 0.5, -0.4], [W / 2 - 0.5, -0.4], [W / 2 - 0.5, 0.3], [-W / 2 + 0.5, 0.3]], 0.0, roof + 0.2, "#b9b5aa"]])

# ------------------------------------------------------------------ the Gendarmenmarkt domes
# the domed towers of the Französischer and the Deutscher Dom (LoD2 tower solids cut to their 50-51 m eave by
# fix_h): a drum ring of columns, the copper dome, the lantern and a statue to ~70 m (est.; Wikipedia: 70 m)
# (M4 fix round: the critic read slim lighthouse cylinders on red-brick bases) refs/gendarmenmarkt/01-02, 05: over the
# square base a broad drum ringed by a colonnade of Corinthian columns with its entablature and balustrade, the
# upper drum (the LoD2's tower to its 50 m eave), a large tall copper dome, the lantern and the gilt statue to 70 m;
# three columned porticos with pediments on the base (where the LoD2's base solid reaches out past the square)
SST2 = "#d3cbb4"
for nm, gml, base_gml, ext_gml in (("Französischer Dom", "DEBE3DkEireAqk2H", "DEBE3Dz2P6h8WJ8G", "DEBE3DNvPpyGDD1T"),
                                   ("Deutscher Dom", "DEBE3DZe5I3ioLoM", "DEBE3Dy3iHNy8L3d", "DEBE3DxA4pOQjKoS")):
    p = piece(gml)
    c, u, v, L, W = rect(p.geometry)
    top = roof_abs(p) - ground(c)
    r = math.sqrt(p.geometry.area / math.pi)            # the LoD2 tower's radius (~9.2 m)
    pb = piece(base_gml)
    bt = roof_abs(pb) - ground(c)                       # the square base's top (~24 m)
    rc = r + 2.2                                         # the colonnade
    ytop_c = bt + 13.0
    tubes = [[[round(rc * math.cos(2 * math.pi * (k + 0.5) / 20), 2), bt + 0.8, round(rc * math.sin(2 * math.pi * (k + 0.5) / 20), 2)],
              [round(rc * math.cos(2 * math.pi * (k + 0.5) / 20), 2), ytop_c, round(rc * math.sin(2 * math.pi * (k + 0.5) / 20), 2)], 0.5, SST2] for k in range(20)]
    prisms = [[ring(rc + 0.9, 24), bt - 0.3, bt + 0.8, SST2],                                 # the colonnade's floor
              [ring(rc + 0.8, 24), ytop_c, ytop_c + 1.6, SST2],                               # entablature
              [ring(rc + 1.0, 24), ytop_c + 1.6, ytop_c + 2.0, "#ddd6c2"],
              [ring(rc + 0.6, 24), ytop_c + 2.0, ytop_c + 3.0, SST2],                         # balustrade
              [ring(r + 0.2, 24), top - 0.6, top + 0.6, "#ddd6c2"]]                           # the upper drum's cornice
    dome = []
    for t in np.linspace(0.0, 1.0, 10):
        a_ = t * math.pi / 2
        dome.append([round(top + 0.6 + 12.5 * math.sin(a_), 2), 0, 0, round(max((r - 0.2) * math.cos(a_) ** 0.8, 1.5), 2), round(max((r - 0.2) * math.cos(a_) ** 0.8, 1.5), 2)])
    ly = top + 13.1
    dome += [[ly + 2.2, 0, 0, 1.4, 1.4], [ly + 2.2, 0, 0, 1.8, 1.8], [ly + 2.7, 0, 0, 1.8, 1.8], [ly + 3.6, 0, 0, 0.7, 0.7], [ly + 3.8, 0, 0, 0.1, 0.1]]
    figure(f"{nm} drum", c, 0.0, SST2, ytop_c + 3.0, prisms=prisms, tubes=tubes, variant=0.3,
           note=f"The {nm} on the Gendarmenmarkt: colonnade, porticos, the copper dome, lantern and statue (~70 m)")
    figure(f"{nm} dome", c, 0.0, "#6e8c80", ly + 7.0, sections=dome, segments=24, variant=0.4,
           tubes=[[[0, ly + 3.6, 0], [0, ly + 6.0, 0], 0.45, GILT], [[0, ly + 5.3, 0], [0.9, ly + 6.6, 0.0], 0.12, GILT]])
    # porticos: on each side of the base where the base-and-porticos solid reaches 3 m past the square
    pe = piece(ext_gml)
    bc, bu, bv, bL, bW = rect(pb.geometry)
    ep = np.array([q for g_ in getattr(pe.geometry, "geoms", [pe.geometry]) for q in g_.exterior.coords])
    for d in (bu, -bu, bv, -bv):
        reach = float(((ep - bc) @ d).max())
        half = bL / 2 if abs(d @ bu) > 0.5 else bW / 2
        if reach - half < 3.0:
            continue
        pc = bc + d * (reach + 1.2)
        hgt = roof_abs(pe) - ground(pc)
        cols = [[[round(float(x), 2), 1.6, 0.0], [round(float(x), 2), hgt - 3.2, 0.0], 0.55, SST2] for x in np.linspace(-6.0, 6.0, 6)]
        figure(f"{nm} portico {bearing(d):.0f}", pc, bearing(d), SST2, hgt + 3.6, tubes=cols, variant=0.3,
               boxes=[[0, 0.8, -0.8, 15.0, 1.6, 4.0, "#c9c1aa"], [0, hgt - 2.0, -0.8, 14.4, 2.4, 3.2, SST2]],
               slabs=[[[[-7.4, hgt - 0.8], [7.4, hgt - 0.8], [0.0, hgt + 3.4]], -2.4, 0.8, "#ddd6c2"]])

# ------------------------------------------------------------------ St. Hedwig's dome
# the rotunda (LoD2 DEBE01YYK00000AQ, cut to its 19.5 m eave by fix_h): the copper dome to ~36 m with a lantern and
# cross (est.), green
sh = piece("DEBE01YYK00000AQ")
c = np.array(sh.geometry.centroid.coords[0])
top = roof_abs(sh) - ground(c)
r = math.sqrt(sh.geometry.area / math.pi) - 1.0
dome = []
for t in np.linspace(0.0, 1.0, 9):
    a = t * math.pi / 2
    dome.append([round(top + 14.0 * math.sin(a), 2), 0, 0, round(max(r * math.cos(a), 2.0), 2), round(max(r * math.cos(a), 2.0), 2)])
dome += [[top + 17.5, 0, 0, 2.0, 2.0], [top + 18.0, 0, 0, 0.4, 0.4], [top + 20.0, 0, 0, 0.1, 0.1]]
figure("St.-Hedwigs-Kathedrale dome", c, 0.0, "#6fa596", top + 20.0, sections=dome, segments=32, variant=0.4,
       note="St. Hedwig's Cathedral: the green dome over the rotunda (~36 m)")

# ------------------------------------------------------------------ the Bode-Museum's dome
# the dome's drum (LoD2 DEBE3DfDgUjMn2VJ, cut to its 28.3 m eave by fix_h): the copper dome and lantern to ~40 m
bm = piece("DEBE3DfDgUjMn2VJ")
c = np.array(bm.geometry.centroid.coords[0])
top = roof_abs(bm) - ground(c)
r = math.sqrt(bm.geometry.area / math.pi) - 1.2
# (M4 fix round, the critic: a dome on a columned drum with tall arched windows) paired columns round the drum's
# upper two thirds with their entablature, a fuller dome (rise 10 m) and the lantern
R = r + 1.2
dome = []
for t in np.linspace(0.0, 1.0, 9):
    a = t * math.pi / 2
    dome.append([round(top + 1.0 + 10.0 * math.sin(a), 2), 0, 0, round(max(R * math.cos(a) ** 0.85, 1.8), 2), round(max(R * math.cos(a) ** 0.85, 1.8), 2)])
dome += [[top + 13.5, 0, 0, 1.8, 1.8], [top + 13.5, 0, 0, 2.2, 2.2], [top + 14.0, 0, 0, 2.2, 2.2], [top + 15.0, 0, 0, 0.6, 0.6], [top + 16.5, 0, 0, 0.05, 0.05]]
tubes = [[[round((r + 0.7) * math.cos(2 * math.pi * k / 16 + d), 2), top - 11.0, round((r + 0.7) * math.sin(2 * math.pi * k / 16 + d), 2)],
          [round((r + 0.7) * math.cos(2 * math.pi * k / 16 + d), 2), top - 1.2, round((r + 0.7) * math.sin(2 * math.pi * k / 16 + d), 2)], 0.38, "#b5aa94"]
         for k in range(16) for d in (-0.035, 0.035)]
figure("Bode-Museum dome", c, 0.0, "#6f7f74", top + 16.5, sections=dome, segments=24, variant=0.4, tubes=tubes,
       prisms=[[ring(r + 1.4, 24), top - 1.2, top + 1.0, "#b5aa94"], [ring(r + 1.3, 24), top - 11.8, top - 11.0, "#b5aa94"]],
       note="The Bode-Museum: the columned drum and the copper dome over the island's tip (~44 m)")

# ------------------------------------------------------------------ the Altes Museum's colonnade
# Schinkel's 18 Ionic columns (87 m) along the front facing the Lustgarten (south-east), on the podium (the table's
# 22.2 m piece DEBE3Dz0QpLii9z0 is the front block): columns ~12 m from the podium at ~5 m
am = piece("DEBE3Dz0QpLii9z0")
c, u, v, L, W = rect(am.geometry)
fv = v if v[1] < 0 else -v                          # forward: south, onto the Lustgarten
pc = c + fv * (W / 2 + 1.0)
tubes = [[[round(float(x), 2), 4.6, 0.0], [round(float(x), 2), 17.4, 0.0], 0.62, "#d7cfbd"] for x in np.linspace(-41.0, 41.0, 18)]
figure("Altes Museum colonnade", pc, bearing(fv), "#d7cfbd", 19.6, variant=0.4, tubes=tubes,
       boxes=[[0, 2.3, -2.0, 90.0, 4.6, 8.0, "#c9c0ad"], [0, 18.5, -1.0, 88.0, 2.2, 4.0, "#d7cfbd"]],
       note="The Altes Museum: Schinkel's colonnade of 18 Ionic columns on the Lustgarten front")

# ------------------------------------------------------------------ the Konzerthaus portico
# Schinkel's Ionic portico (six columns) on its stair, facing the Gendarmenmarkt (east), the pediment
kh = piece("DEBE3DBjvNWYBGJA")
c, u, v, L, W = rect(kh.geometry)
fv = u if u[0] > 0 else -u
if abs(v[0]) > abs(u[0]):
    fv = v if v[0] > 0 else -v
half = (L if abs(fv @ u) > 0.5 else W) / 2
pc = c + fv * (half + 2.0)
tubes = [[[round(float(x), 2), 6.5, 0.0], [round(float(x), 2), 18.5, 0.0], 0.62, "#ddd5c0"] for x in np.linspace(-11.0, 11.0, 6)]
figure("Konzerthaus portico", pc, bearing(fv), "#ddd5c0", 24.5, variant=0.4, tubes=tubes,
       boxes=[[0, 3.2, -1.5, 28.0, 6.4, 9.0, "#cfc6b0"], [0, 19.6, -1.0, 26.0, 2.2, 5.0, "#ddd5c0"]],
       slabs=[[[[-13.0, 20.7], [13.0, 20.7], [0.0, 24.5]], -3.5, 1.5, "#ddd5c0"]],
       note="The Konzerthaus: Schinkel's portico on the Gendarmenmarkt")

# ------------------------------------------------------------------ church steeples
# the LoD2 tower solid of each church (the tallest piece in its outline); where the laser caught the spire's foot,
# fix_h in city.toml cuts it to its eave and the spire starts there. kind: spire (octagonal helm), twin (two spires
# on one westwork: the Nikolaikirche), baroque (stages and a lantern: the Sophienkirche), copper (the Marienkirche's
# lantern stage and copper spire). Tips from Wikipedia where stated, else ESTIMATED from photos (see notes)
CHURCHES = [
    # gml_id of the tower piece, name, kind, tip m, colour of the spire
    ("DEBE3Dm03ICrhanR", "St. Marienkirche", "copper", 89.7, "#6f9486"),
    ("DEBE3DJ5QoacFhgE", "Nikolaikirche", "twin", 84.4, "#5d7268"),
    ("DEBE3Dj5UEZckkkC", "Zionskirche", "spire", 67.0, "#4d5560"),
]
EXTRA = [  # churches found by OSM outline (their tower piece: the tallest LoD2 piece in the outline)
    # osm way, name, kind, tip m (source), spire colour
    ("w37533771", "Heilandskirche", "spire", 87.0, "#4d5560"),
]
SPIRES = {}
try:
    SPIRES = json.loads((DATA / "m4h_churches.json").read_text())
except FileNotFoundError:
    pass
for row in EXTRA:
    oid, name, kind, tip, col = row
    tip = SPIRES.get(name, {}).get("tip", tip)
    osm_b = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    o = osm_b[osm_b.osm_id == oid]
    if not len(o):
        print(f"no outline {oid} ({name})")
        continue
    g_out = o.geometry.iloc[0]
    s = B[B.intersects(g_out.buffer(2.0)) & (B.source == "lod2")]
    s = s[(s.intersection(g_out.buffer(2.0)).area > 0.6 * s.area) & (s.area.between(25, 400)) & (s.h >= 25)]
    s = s.sort_values("h", ascending=False)
    if not len(s):
        print(f"no tower piece for {name}")
        continue
    print(f"{name}: tower piece {s.iloc[0].gml_id} {s.iloc[0].h:.1f} m (eave {s.iloc[0].eave_h}), {s.iloc[0].geometry.area:.0f} m2")
    CHURCHES.append((s.iloc[0].gml_id, name, kind, tip, col))
FIXH = {}
for gml, name, kind, tip, col in CHURCHES:
    p = piece(gml)
    c, u, v, L, W = rect(p.geometry)
    side = min(L, W)
    eave = float(p.eave_h) if p.eave_h == p.eave_h else float(p.h)
    g0 = base_of(p.geometry)
    gc = ground(c)
    h_cut = float(p.h)
    if float(p.h) - eave > 3.0:                          # the laser caught the spire's foot: cut to the eave
        h_cut = eave
        FIXH[gml] = round(eave, 1)
    ttop = g0 + h_cut - gc                               # the tower's top over the ground at its centre
    tip_y = g0 + tip - gc
    if tip_y < ttop + 4.0:
        print(f"{name}: tower {ttop:.1f} m already near its tip {tip_y:.1f}: skipped")
        continue
    h = side / 2
    fc = bearing(u)
    s_ = tip_y - ttop
    if kind == "twin":                                   # two spires at the ends of the westwork's long axis
        hs = min(h, 3.6)
        for e in (-1, 1):
            q = c + u * e * (L / 2 - hs - 0.3)
            figure(f"{name} spire {e:+d}", q, fc, col, tip_y, variant=0.4, segments=8,
                   prisms=[[square(hs), ttop - 1.0, ttop + 2.0, "#8a5b44"]],
                   sections=[[ttop + 2.0, 0, 0, hs * 1.05, hs * 1.05], [ttop + 2.0 + 0.3 * (s_ - 2), 0, 0, hs * 0.72, hs * 0.72],
                             [tip_y - 0.8, 0, 0, 0.15, 0.15], [tip_y, 0, 0, 0.03, 0.03]])
        continue
    if kind == "copper":                                 # a pinnacled lantern stage, then the copper spire
        figure(f"{name} spire", c, fc, col, tip_y, variant=0.4, segments=8,
               prisms=[[ring(h * 0.92, 8), ttop - 0.5, ttop + 0.22 * s_, col], [ring(h * 0.98, 8), ttop + 0.22 * s_, ttop + 0.25 * s_, col],
                       [ring(h * 0.72, 8), ttop + 0.25 * s_, ttop + 0.45 * s_, col], [ring(h * 0.8, 8), ttop + 0.45 * s_, ttop + 0.48 * s_, col]],
               sections=[[ttop + 0.48 * s_, 0, 0, h * 0.55, h * 0.55], [ttop + 0.56 * s_, 0, 0, h * 0.35, h * 0.35],
                         [tip_y - 1.0, 0, 0, 0.12, 0.12], [tip_y, 0, 0, 0.03, 0.03]],
               note=f"{name}: the tower's top and spire to {tip} m")
        continue
    if kind == "baroque":                                # stages of a diminishing tower, a lantern and a needle
        figure(f"{name} tower top", c, fc, col, tip_y, variant=0.4, segments=8,
               prisms=[[square(h * 0.82), ttop - 0.5, ttop + 0.18 * s_, "#d8cfb8"], [square(h * 0.66), ttop + 0.18 * s_, ttop + 0.36 * s_, "#d8cfb8"]],
               sections=[[ttop + 0.36 * s_, 0, 0, h * 0.62, h * 0.62], [ttop + 0.5 * s_, 0, 0, h * 0.32, h * 0.32], [ttop + 0.58 * s_, 0, 0, h * 0.4, h * 0.4],
                         [ttop + 0.7 * s_, 0, 0, h * 0.2, h * 0.2], [tip_y - 0.6, 0, 0, 0.1, 0.1], [tip_y, 0, 0, 0.03, 0.03]],
               note=f"{name}: the baroque tower's top to {tip} m")
        continue
    # spire: corner pinnacles and an octagonal helm
    tubes = [[[sx * (h - 0.5), ttop - 0.5, sz * (h - 0.5)], [sx * (h - 0.5), ttop + 4.5, sz * (h - 0.5)], 0.45, "#8f6a52"]
             for sx in (-1, 1) for sz in (-1, 1)]
    figure(f"{name} spire", c, fc, col, tip_y, variant=0.4, segments=8, tubes=tubes,
           sections=[[ttop - 0.3, 0, 0, h * 0.92, h * 0.92], [ttop + 0.12 * s_, 0, 0, h * 0.7, h * 0.7], [tip_y - 0.8, 0, 0, 0.15, 0.15],
                     [tip_y, 0, 0, 0.03, 0.03]],
           note=f"{name}: the spire over the LoD2 tower to {tip} m")
# churches whose LoD2 is one generalised solid (no tower piece): the tower drawn whole from the ground at the end of
# the OSM outline the sources name (WP: the Sophienkirche's west tower, St. Bonifatius' twin towers on its north
# front, the Heilig-Kreuz-Kirche's crossing tower rebuilt to 59.3 m without its spire); sides and heights of the
# tower stages ESTIMATED from photos
MANUAL = [
    # osm way, name, kind, end, tower side, tower top, tip, colour
    ("w23816415", "Sophienkirche", "baroque", "w", 8.5, 40.0, 69.0, "#6e8c80"),
    ("w39349086", "St. Bonifatius", "twin", "n", 6.0, 38.0, 56.0, "#6f9486"),
    ("w68647307", "Heilig-Kreuz-Kirche", "flat", "c", 11.0, 59.3, 59.3, "#9a5a44"),
]
osm_b = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
for oid, name, kind, end, side, ttop, tip, col in MANUAL:
    o = osm_b[osm_b.osm_id == oid]
    if not len(o):
        print(f"no outline {oid} ({name})")
        continue
    g = o.geometry.iloc[0]
    c, u, v, L, W = rect(g)
    if end == "c":
        q, ax = c, u
    else:
        want = {"w": np.array([-1, 0]), "e": np.array([1, 0]), "n": np.array([0, 1]), "s": np.array([0, -1])}[end]
        ax = u if abs(u @ want) >= abs(v @ want) else v
        ax = ax if ax @ want > 0 else -ax
        half = (L if ax is u or abs(ax @ u) > 0.7 else W) / 2
        q = c + ax * (half - side / 2 - 0.5)
    h = side / 2
    s_ = tip - ttop
    BRK = "#9a5a44" if kind != "baroque" else "#d8cfb8"
    if kind == "twin":
        across = np.array([ax[1], -ax[0]])
        wd = (W if abs(ax @ u) > 0.7 else L) / 2
        for e in (-1, 1):
            q2 = q + across * e * (wd - h - 0.5)
            figure(f"{name} tower {e:+d}", q2, bearing(ax), col, tip, variant=0.4, segments=8,
                   prisms=[[square(h), 0.0, ttop, BRK], [square(h + 0.3), ttop - 1.0, ttop, BRK]],
                   sections=[[ttop, 0, 0, h * 0.95, h * 0.95], [ttop + 0.3 * s_, 0, 0, h * 0.6, h * 0.6], [tip - 0.6, 0, 0, 0.1, 0.1], [tip, 0, 0, 0.03, 0.03]],
                   note=f"{name}: the two towers with copper helms (~{tip} m, est.)" if e < 0 else None)
        continue
    if kind == "flat":
        figure(f"{name} tower", q, bearing(ax), col, tip, variant=0.4,
               prisms=[[square(h), 0.0, ttop - 1.5, BRK], [square(h + 0.3), ttop - 1.5, ttop, BRK]],
               note=f"{name}: the crossing tower ({ttop} m, WP)")
        continue
    figure(f"{name} tower", q, bearing(ax), col, tip, variant=0.4, segments=8,
           prisms=[[square(h), 0.0, ttop, BRK], [square(h * 0.82), ttop, ttop + 0.18 * s_, BRK], [square(h * 0.66), ttop + 0.18 * s_, ttop + 0.36 * s_, BRK]],
           sections=[[ttop + 0.36 * s_, 0, 0, h * 0.62, h * 0.62], [ttop + 0.5 * s_, 0, 0, h * 0.32, h * 0.32], [ttop + 0.58 * s_, 0, 0, h * 0.4, h * 0.4],
                     [ttop + 0.7 * s_, 0, 0, h * 0.2, h * 0.2], [tip - 0.6, 0, 0, 0.1, 0.1], [tip, 0, 0, 0.03, 0.03]],
           note=f"{name}: the baroque west tower with its copper hood and needle (~{tip} m, est.)")
# St. Thomas (Kreuzberg): the dome over the crossing (56 m, est.) and two west towers (48 m, est.)
if "51688847" in OSM:
    g = osm_poly(51688847)
    c, u, v, L, W = rect(g)
    wv = u if u[0] < 0 else -u
    s = B[B.intersects(g.buffer(-0.5)) & (B.source == "lod2")]
    if len(s):
        roof = max(float(base_of(q) + h_) for q, h_ in zip(s.geometry, s.h) if q.area > 300) - ground(c)
        dome = [[roof - 2.0, 0, 0, 7.5, 7.5], [roof + 6.0, 0, 0, 7.5, 7.5]]
        for t in np.linspace(0.1, 1.0, 6):
            a = t * math.pi / 2
            dome.append([round(roof + 6.0 + 8.0 * math.sin(a), 2), 0, 0, round(max(7.5 * math.cos(a), 1.4), 2), round(max(7.5 * math.cos(a), 1.4), 2)])
        dome += [[roof + 17.0, 0, 0, 1.4, 1.4], [roof + 17.5, 0, 0, 0.2, 0.2], [roof + 19.5, 0, 0, 0.05, 0.05]]
        figure("St.-Thomas-Kirche dome", c + u * 0.0, 0.0, "#5d7268", roof + 19.5, sections=dome, segments=16, variant=0.4,
               note="St. Thomas (Kreuzberg): the dome over the crossing and the two west towers (heights est.)")

# ------------------------------------------------------------------ the Oberbaumbrücke
# the U1's two tracks on the bridge (OSM w155667532/w155667537, layer 3) give the viaduct's axis; the road deck ~35 m
# (both banks' ground), the U-Bahn deck ~6.5 m over it on an arcade of pointed arches (red brick, photos
# oberbaumbruecke/05); the two towers (OSM parts w373626454/455, 18 m: the towers' feet) over the middle pier, 34 m
# over the water, square brick shafts with an arcaded top storey and a pointed copper-green spire (est. dims)
la, lb = osm_line(155667532), osm_line(155667537)
pa = np.array(la.coords)
pb = np.array(lb.coords)
p0 = (pa[0] + pb[-1]) / 2
p1 = (pa[-1] + pb[0]) / 2
axis = p1 - p0
Lb = float(np.hypot(*axis))
ua = axis / Lb
mid = (p0 + p1) / 2
fa = bearing(np.array([ua[1], -ua[0]]))                    # forward across the bridge; x along it
DECK = max(ground(p0), ground(p1)) + 0.3                   # the road deck: the banks' ground (scene heights; the bridge
# meets the streets at both ends)
BR, BR2 = "#a4523a", "#8e4532"
# the arcade's side elevation: x along the bridge, y up; pointed arches 4.2 m wide every 5.6 m, open to 4.8 m
n = int(Lb // 5.6)
x0 = -n * 5.6 / 2
outline = [[x0, 0.0], [x0, 6.2], [-x0, 6.2], [-x0, 0.0]]
for k in range(n - 1, -1, -1):
    a = x0 + k * 5.6 + 0.7
    b = a + 4.2
    outline += [[b, 0.0], [b, 3.2], [b - 0.6, 4.3], [(a + b) / 2, 4.9], [a + 0.6, 4.3], [a, 3.2], [a, 0.0]]
slabs = [[outline, -4.6, -3.6, BR], [outline, 3.6, 4.6, BR]]
boxes = [[0, 6.7, 0, Lb, 1.0, 9.4, BR2], [0, 7.6, -4.4, Lb, 0.9, 0.5, BR], [0, 7.6, 4.4, Lb, 0.9, 0.5, BR]]
# (M4 merge) not drawn: 05b_roads/06_tiles already stand the U1 on its arcade over the bridge ([roads.piers]
# "Oberbaumbrücke" arcade, decks.level_on, the M3 fix round); this figure's solid deck box and slabs covered that
# open arcade and ran 50 m further. The towers below stay.
# figure("Oberbaumbrücke U-Bahn arcade", mid, fa, BR, 8.1, slabs=slabs, boxes=boxes, floor=DECK, variant=0.4,
#        note="The Oberbaumbrücke (1896): the U-Bahn's arcade and upper deck, the two towers over the middle pier")
# (M4 fix round: the critic saw the towers at the bridge's north end: OSM's 18 m parts there are the end pavilion's)
# the two towers stand mid-span over the central navigation arch (OSM's 34 m parts w373626459 and w1547500040,
# refs/oberbaumbruecke/03): square brick shafts to over the arcade, a crenellated gallery, an octagonal belfry
# stage with tall arched openings, a second crenellated ring, the pointed octagonal cap and its finial, 34 m
DKB = "#7a3828"
for i in (373626459, 1547500040):
    g = osm_poly(i)
    tc = np.array(g.centroid.coords[0])
    hs = max(min(math.sqrt(g.area) / 2, 4.6), 3.2)
    ho = hs * 0.86                                          # the octagon's circumradius
    prisms = [[square(hs), 0.0, 19.5, BR], [square(hs + 0.45), 19.5, 20.4, "#c9b9a0"]]
    for k in range(8):                                      # merlons round the first gallery
        a_ = 2 * math.pi * k / 8
        prisms.append([square(0.45, round((hs + 0.1) * math.cos(a_) * 1.0, 2), round((hs + 0.1) * math.sin(a_), 2)), 20.4, 21.5, BR])
    prisms += [[ring(ho, 8, math.pi / 8), 20.4, 27.0, BR], [ring(ho + 0.35, 8, math.pi / 8), 27.0, 27.7, "#c9b9a0"]]
    for k in range(8):                                      # tall arched openings on the octagon (dark slots)
        a_ = math.pi / 8 + 2 * math.pi * k / 8 + math.pi / 8
        n_ = np.array([math.cos(a_), math.sin(a_)])
        t_ = np.array([-n_[1], n_[0]])
        rr_ = ho * math.cos(math.pi / 8) + 0.06
        q = [n_ * rr_ + t_ * 0.6, n_ * rr_ - t_ * 0.6, n_ * (rr_ - 0.3) - t_ * 0.6, n_ * (rr_ - 0.3) + t_ * 0.6]
        prisms.append([[[round(float(x), 3), round(float(z), 3)] for x, z in q], 22.0, 26.0, "#2a2320"])
        prisms.append([square(0.3, round(float((ho + 0.25) * math.cos(a_ - math.pi / 8)), 2), round(float((ho + 0.25) * math.sin(a_ - math.pi / 8)), 2)), 27.7, 28.5, BR])
    figure(f"Oberbaumbrücke tower {i}", tc, fa, DKB, 34.8, variant=0.4, segments=8, prisms=prisms,
           sections=[[27.6, 0, 0, ho * 0.92, ho * 0.92], [28.4, 0, 0, ho * 0.85, ho * 0.85], [33.2, 0, 0, 0.35, 0.35], [33.4, 0, 0, 0.05, 0.05]],
           tubes=[[[0, 33.0, 0], [0, 34.8, 0], 0.12, "#4f6a60"]],
           note="The Oberbaumbrücke's two towers mid-span (34 m, OSM)" if i == 373626459 else None)

# ------------------------------------------------------------------ the Molecule Man
# Borofsky (1999): three 30 m aluminium figures leaning together in the Spree (OSM w166268035), perforated; here
# each figure as a torso, head, legs and arms of tubes, the three facing a common centre, silver
mm = osm_poly(166268035)
mc = np.array(mm.centroid.coords[0])
AL = "#b9bec2"
tubes = []
for k in range(3):
    a = 2 * math.pi * k / 3
    ox, oz = 4.2 * math.cos(a), 4.2 * math.sin(a)
    ix, iz = -math.cos(a), -math.sin(a)                     # toward the centre
    px, pz = -iz, ix                                        # across
    def P(r, sd, y):
        return [round(ox + ix * r + px * sd, 2), round(y, 2), round(oz + iz * r + pz * sd, 2)]
    for sd in (-1.6, 1.6):                                  # legs
        tubes.append([P(0.0, sd * 1.4, 0.0), P(0.6, sd, 13.0), 1.0, AL])
    tubes.append([P(0.6, 0.0, 12.5), P(1.6, 0.0, 23.5), 2.1, AL])   # torso
    tubes.append([P(1.7, 0.0, 24.5), P(1.9, 0.0, 29.5), 1.6, AL])   # head
    for sd in (-1, 1):                                      # arms reaching to the others
        tubes.append([P(1.5, sd * 2.4, 22.5), P(3.4, sd * 3.6, 15.5), 0.8, AL])
figure("Molecule Man", mc, 0.0, AL, 30.0, tubes=tubes, variant=0.6,
       note="Molecule Man (Borofsky, 1999): three 30 m aluminium figures in the Spree")

# ------------------------------------------------------------------ the East Side Gallery
# (M4 fix round: the critic saw a grey strip with two painted panels) the Hinterlandmauer along the Mühlenstraße, all
# seven of OSM's outlines (thin closed ways, ~1 km of the 1,316 m with the gaps): the wall in 3.6 m segments (L-shaped
# elements 3.6 m high with the round pipe on top), each painted on both faces with its own ground colour and one or
# two bold shapes (invented: every panel differs), a few long hero murals (the Bruderkuss's pale blue and red, the
# Trabant's white, Thierry Noir's heads in yellow, red and blue); from 0.4 m under the ground so no kerb hides its foot;
# figures of ~60 m each so the wall follows the ground
ESG = [123011378, 208089016, 448158193, 448158194, 448172799, 448172800, 448173093]
GROUNDS = ["#e8d64a", "#d24a3a", "#3f78c0", "#f0ece0", "#4fae6a", "#e8873a", "#8a5ab0", "#28324a", "#7fc4d8", "#e06a9a",
           "#f2b53a", "#5a9a8a", "#c8c2b4", "#b23a4a", "#2f5aa0", "#9ac04a"]
HERO = {0.18: ("#9cc4e0", "#c8403a", "#e8ddc8"), 0.43: ("#f2f0e8", "#3a6ab0", "#c8b84a"), 0.62: ("#f0d23a", "#d23a3a", "#2a62b8"),
        0.8: ("#2a2a3a", "#e85a8a", "#f2f0e8")}
rng = np.random.default_rng(1989)


def centre_line(g):
    """The long centre line of a thin closed outline: its two farthest points split the ring into two sides; the
    mean of the two sides sampled at the same fractions."""
    q = np.array(g.exterior.coords)[:-1]
    d = np.linalg.norm(q[:, None] - q[None], axis=2)
    i, j = np.unravel_index(int(np.argmax(d)), d.shape)
    i, j = min(i, j), max(i, j)
    s1 = LineString(np.vstack([q[i:j + 1]]))
    s2 = LineString(np.vstack([q[j:], q[:i + 1]])[::-1])
    fr = np.linspace(0, 1, max(int(s1.length / 2.0), 2) + 1)
    return LineString([((np.array(s1.interpolate(t, normalized=True).coords[0]) + np.array(s2.interpolate(t, normalized=True).coords[0])) / 2)
                       for t in fr])


lines = [centre_line(osm_poly(i)) for i in ESG if str(i) in OSM]
total = sum(l_.length for l_ in lines)
done = 0.0
seg_i = 0
for ln in sorted(lines, key=lambda l_: -l_.coords[0][0]):
    nchunk = max(1, int(round(ln.length / 60.0)))
    for ci in range(nchunk):
        t0, t1 = ln.length * ci / nchunk, ln.length * (ci + 1) / nchunk
        mid = np.array(ln.interpolate((t0 + t1) / 2).coords[0])
        prisms = []
        n_p = max(1, int(round((t1 - t0) / 3.6)))
        for k in range(n_p):
            a_ = np.array(ln.interpolate(t0 + (t1 - t0) * k / n_p).coords[0])
            b_ = np.array(ln.interpolate(t0 + (t1 - t0) * (k + 1) / n_p).coords[0])
            dv = (b_ - a_) / max(np.linalg.norm(b_ - a_), 1e-6)
            nv = np.array([-dv[1], dv[0]])
            frac = (done + t0 + (t1 - t0) * (k + 0.5) / n_p) / total
            hero = next((HERO[h] for h in HERO if abs(frac - h) < 0.012), None)
            if hero:
                gcol, c1, c2 = hero
            else:
                gcol = GROUNDS[int(rng.integers(len(GROUNDS)))]
                c1 = GROUNDS[int(rng.integers(len(GROUNDS)))]
                c2 = GROUNDS[int(rng.integers(len(GROUNDS)))]
            e = 0.01
            body = [a_ + nv * 0.2 + dv * e, b_ + nv * 0.2 - dv * e, b_ - nv * 0.2 - dv * e, a_ - nv * 0.2 + dv * e]
            prisms.append([[local(p_, mid) for p_ in body], -0.4, 3.45, gcol])
            prisms.append([[local(p_, mid) for p_ in [a_ + nv * 0.3, b_ + nv * 0.3, b_ - nv * 0.3, a_ - nv * 0.3]], 3.45, 3.75, "#d8d4c8"])
            # one or two shapes on each face: a band, a block or a tall figure, proud of the wall by 3 cm
            for side in (1, -1):
                for col_, kind_ in ((c1, int(rng.integers(3))), (c2, int(rng.integers(4)))):
                    if kind_ == 3:
                        continue
                    if kind_ == 0:      # a horizontal band
                        x0, x1, y0, y1 = 0.0, 1.0, rng.uniform(0.3, 2.4), 0
                        y1 = y0 + rng.uniform(0.4, 1.1)
                    elif kind_ == 1:    # a block
                        x0 = rng.uniform(0.05, 0.5)
                        x1 = x0 + rng.uniform(0.25, 0.45)
                        y0 = rng.uniform(0.3, 1.5)
                        y1 = y0 + rng.uniform(0.8, 1.8)
                    else:               # a tall figure
                        x0 = rng.uniform(0.15, 0.7)
                        x1 = x0 + rng.uniform(0.12, 0.25)
                        y0, y1 = rng.uniform(0.2, 0.6), rng.uniform(2.2, 3.3)
                    pa_, pb_ = a_ + (b_ - a_) * x0, a_ + (b_ - a_) * x1
                    off0, off1 = nv * side * 0.2, nv * side * 0.24
                    prisms.append([[local(p_, mid) for p_ in [pa_ + off0, pb_ + off0, pb_ + off1, pa_ + off1]], round(float(y0), 2), round(float(min(y1, 3.4)), 2), col_])
        figure(f"East Side Gallery {seg_i}", mid, 0.0, "#c8c2b4", 3.75, prisms=prisms, variant=0.6,
               note="The East Side Gallery: 1,316 m of the wall along the Mühlenstraße (3.6 m), its murals invented" if seg_i == 0 else None)
        seg_i += 1
    done += ln.length
print(f"East Side Gallery: {len(lines)} outlines, {total:.0f} m, {seg_i} figures")

# ------------------------------------------------------------------ the Kreuzberg's Nationaldenkmal
# Schinkel's cast-iron gothic spire (1821) on the Kreuzberg's summit (OSM node 241490725): ~19 m, a cruciform base,
# pinnacles, the iron cross on top; dark iron
kd = utm(13.3814783, 52.4876488)
figure("Nationaldenkmal Kreuzberg", kd, 0.0, "#4a4f52", 19.0, variant=0.4, segments=8,
       prisms=[[square(5.5), 0.0, 1.5, "#9a958a"], [square(2.6), 1.5, 9.0, "#4a4f52"], [square(2.0), 9.0, 12.0, "#4a4f52"]],
       sections=[[12.0, 0, 0, 1.8, 1.8], [17.0, 0, 0, 0.4, 0.4], [19.0, 0, 0, 0.05, 0.05]],
       tubes=[[[sx * 2.5, 1.5, sz * 2.5], [sx * 2.5, 12.5, sz * 2.5], 0.35, "#4a4f52"] for sx in (-1, 1) for sz in (-1, 1)]
       + [[[-0.8, 18.2, 0], [0.8, 18.2, 0], 0.12, "#4a4f52"]],
       note="The Nationaldenkmal für die Befreiungskriege (Schinkel, 1821) on the Kreuzberg")

# ------------------------------------------------------------------ station halls on the Stadtbahn
# a vault on the hall's outline: glazed side walls from track level, then the roof stepping in on a quarter ellipse
# (the outline buffered inward), glass and steel grey. The LoD2's hall roofs hanging over the bodies are excluded in
# [buildings]; OSM's train_station fills (skipped by 04_buildings) give the halls the LoD2 lacks


def hall(name, g, y0, wall, apex, inset=None, steps=6, colour="#87939a", wall_colour="#6c7880", note=None):
    g = max(getattr(g, "geoms", [g]), key=lambda z: z.area)
    c = np.array(g.centroid.coords[0])
    _, _, _, L, W = rect(g)
    inset = inset or W * 0.45
    prisms = [[[local(p, c) for p in np.array(g.exterior.coords)[:-1]], y0, wall, wall_colour]]
    prev = wall
    for k in range(1, steps + 1):
        t = k / steps
        a = t * math.pi / 2
        d = inset * (1 - math.cos(a))
        y = wall + (apex - wall) * math.sin(a)
        q = g.buffer(-d, join_style=2) if d > 0 else g
        if q.is_empty:
            break
        q = max(getattr(q, "geoms", [q]), key=lambda z: z.area).simplify(0.3)
        prisms.append([[local(p, c) for p in np.array(q.exterior.coords)[:-1]], prev - 0.05, y, colour])
        prev = y
    figure(name, c, 0.0, colour, apex, prisms=prisms, variant=0.5, note=note)


def lod2_top(gml):
    p = piece(gml)
    return base_of(p.geometry) + float(p.h)


# Alexanderplatz: the hall roof (LoD2 DEBE01YYK0001z5U, 18.7-27.1 m, excluded) over the 6.7 m viaduct body
alex = osm_poly(20144781)
ah = B[B.gml_id == "DEBE01YYK00009vV"]
if len(ah):
    gA = alex
    cA = np.array(gA.centroid.coords[0])
    y0 = lod2_top("DEBE01YYK00009vV") - ground(cA)
    hall("Bahnhof Alexanderplatz hall", gA, y0 - 0.3, 18.7 - (ground(cA) - base_of(ah.geometry.iloc[0])), 27.1 - (ground(cA) - base_of(ah.geometry.iloc[0])),
         inset=14.0, note="Alexanderplatz station: the Stadtbahn hall (1885, rebuilt) over the viaduct (OSM's outline)")
# Ostbahnhof: the platform hall over the tracks (OSM w345095778, 230 x 57 m; skipped by 04_buildings): the track
# level ~6 m (the viaduct), the vault to ~22 m (est.)
for oid, nm in ((345095778, "Ostbahnhof platform hall"),):
    g = osm_poly(oid)
    hall(nm, g, 0.0, 12.0, 22.0, inset=22.0, wall_colour="#7d6a5c",
         note="Ostbahnhof: the platform hall (OSM's outline; vault ~22 m, est.)")
# Hackescher Markt: the curved hall on the viaduct (OSM w170063224; the LoD2 body DEBE01YYK00004lV cut to its 6.9 m
# eave by fix_h): the brick viaduct, glazed walls, the vault to 17 m (the LoD2's top)
g = osm_poly(170063224)
hk = B[B.gml_id == "DEBE01YYK00004lV"]
if len(hk):
    cH = np.array(g.centroid.coords[0])
    gb = base_of(hk.geometry.iloc[0]) - ground(cH)
    hall("S-Bahnhof Hackescher Markt hall", hk.geometry.iloc[0], gb + 6.9, gb + 10.5, gb + 17.1, inset=9.0,
         note="Hackescher Markt station: the curved hall over the brick viaduct")
    FIXH["DEBE01YYK00004lV"] = 6.9
# Zoologischer Garten: the hall (OSM w96955257, 8-20 m) over the 8.7 m body; the LoD2's two roof pieces at 20.8-25 m
# (excluded): glazed walls to 21 m, a low vault to 25 m
g = osm_poly(96955257)
cZ = np.array(g.centroid.coords[0])
zb = B[B.gml_id == "DEBE3DmEBBka4goT"]
if len(zb):
    gb = base_of(zb.geometry.iloc[0]) - ground(cZ)
    hz = B[B.gml_id.isin(["DEBE3DEWbuSeLh2K", "DEBE3DLPnzPapVrB"])]
    gh = hz.geometry.union_all().buffer(0.5).buffer(-0.5) if len(hz) else g
    gh = max(getattr(gh, "geoms", [gh]), key=lambda z: z.area)
    hall("Bahnhof Zoologischer Garten hall", gh, gb + 8.6, gb + 20.8, gb + 25.0, inset=8.0, steps=4,
         note="Zoologischer Garten: the glazed hall over the Stadtbahn (1934-40) on the 8.7 m body")
# Ostkreuz: the Ringbahn's hall on the upper level (2018; OSM w110639235, layer 2; the Umweltatlas's 24 m block is
# dropped): the platform at ~10 m, a broad low roof to ~19 m (est.)
if "110639235" in OSM:
    g = osm_poly(110639235)
    hall("Bahnhof Ostkreuz Ringbahn hall", g, 9.5, 13.0, 19.0, inset=10.0, steps=4,
         note="Ostkreuz: the Ringbahn hall over the upper platforms (est. heights)")
# Warschauer Straße: the S-Bahn station building on the bridge (2017; OSM w297153147, skipped): a glass box ~8 m
# on the bridge deck (the street's level, est.)
g = osm_poly(297153147)
cW = np.array(g.centroid.coords[0])
figure("S Warschauer Straße station", cW, 0.0, "#6c7880", 8.5, base=0.3, variant=0.5,
       prisms=[[[local(p, cW) for p in np.array(g.exterior.coords)[:-1]], 0.0, 7.5, "#6c7880"],
               [[local(p, cW) for p in np.array(g.buffer(0.8, join_style=2).exterior.coords)[:-1]], 7.5, 8.5, "#d8d8d4"]],
       note="Warschauer Straße: the S-Bahn station building on the bridge (2017)")

# ------------------------------------------------------------------ the Hauptbahnhof's glass halls
# (M4 fix round: the critic missed the east-west hall) OSM's glass roofs (roof:shape round, roof:material glass):
# the east-west hall in two halves (w11345963, w226048334: 8 -> 28 m, roof:height 18) on the curving upper tracks,
# 321 m (gmp), and the north-south hall's roof between the two bridge buildings (w226048335: 23 -> 28 m). Each as a
# barrel vault over its outline: cross-sections every ~4 m along its long axis spanning the outline's width there,
# rising to the crown in proportion to the width (the narrow ends lower), drawn as see-through `glazing` (light
# panes, white steel members every 3 m along and 1.8 m across) with the white steel arches as tubes every 12 m


def vault(name, g, spring, rise, period=(1.8, 3.0), arch_every=12.0, note=None):
    c = np.array(g.centroid.coords[0])
    _, u_, v_, L_, W_ = rect(g)
    pts = np.array(g.exterior.coords)
    t = (pts - c) @ u_
    stations = np.linspace(t.min() + 0.5, t.max() - 0.5, max(int((t.max() - t.min()) / 4.0), 3))
    spans = []
    for st in stations:
        cut = LineString([c + u_ * st - v_ * 200, c + u_ * st + v_ * 200]).intersection(g)
        if cut.is_empty:
            continue
        segs = getattr(cut, "geoms", [cut])
        seg = max(segs, key=lambda z: z.length)
        q = np.array(seg.coords)
        sv = (q - c) @ v_
        spans.append((st, float(sv.min()), float(sv.max())))
    wmax = max(b - a for _, a, b in spans)
    grid, tubes = [], []
    n = 14
    last_arch = -1e9
    for st, a, b in spans:
        hw_, mc = (b - a) / 2, (a + b) / 2
        r_ = rise * min(1.0, (2 * hw_ / wmax) ** 0.7)
        row = []
        for k in range(n + 1):
            th = math.pi * k / n
            pm = c + u_ * st + v_ * (mc - hw_ * math.cos(th))
            row.append(local(pm, c) + [round(spring + r_ * math.sin(th), 2)])
        grid.append([[x, y, z] for x, z, y in row])
        if st - last_arch >= arch_every:
            last_arch = st
            for (x0, z0, y0), (x1, z1, y1) in zip(row, row[1:]):
                tubes.append([[x0, y0 + 0.15, z0], [x1, y1 + 0.15, z1], 0.25, "#eceeee"])
    # the steel edge beams along both sides
    for side in (0, n):
        for r0, r1 in zip(grid, grid[1:]):
            tubes.append([r0[side], r1[side], 0.35, "#e4e6e6"])
    figure(name, c, 0.0, "#e8eaea", spring + rise, tubes=tubes, variant=0.5,
           glazing=[{"grid": grid, "period": list(period), "colour": "#eef0f0"}], note=note)


for oid, nm, sp, rs in ((11345963, "Hauptbahnhof east-west hall (west)", 10.0, 18.0), (226048334, "Hauptbahnhof east-west hall (east)", 10.0, 18.0),
                        (226048335, "Hauptbahnhof north-south hall roof", 23.0, 5.0)):
    if str(oid) in OSM:
        vault(nm, osm_poly(oid), sp, rs, note="Berlin Hauptbahnhof (2006): the glass halls over the tracks (OSM's roofs; gmp)" if oid == 11345963 else None)

# ------------------------------------------------------------------ write the generated include file
out = HERE / "generated" / "structures-m4h.toml"
out.parent.mkdir(exist_ok=True)
out.write_text("# Generated by scripts/m4h_structures.py: do not edit (edit the script and run it again).\n"
               "# city.toml's `include` list lays this file under its own settings; the [[structures]] below are\n"
               "# in the order the script builds them.\n" + "\n".join(blocks))
print(f"{len(blocks)} structures written to {out}")
print("fix_h for the church towers and halls (city.toml [buildings] fix_h):", json.dumps(FIXH))
