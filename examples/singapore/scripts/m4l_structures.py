"""M4 (landmarks, builder b-sg-m4l): Singapore's landmarks the building table can't draw, as [[structures]] figures
written to generated/structures-m4l.toml (city.toml `include`s it; re-run after editing the numbers here, then
06_tiles and 07_pack). Run from demos/singapore: `uv run python scripts/m4l_structures.py`.

- the Marina Bay Sands SkyPark: the "ship" over the three towers (OSM's outline w116800998, excluded in [buildings]),
  a hull thick over the towers thinning to the cantilevered bow, the deck, the infinity pool and its gardens;
- the Supertree Grove: the twelve Supertrees (their OSM rings excluded) with flared trunks and canopies, the OCBC Skyway;
- the Flower Dome and the Cloud Forest (their 30 m OSM prisms excluded): see-through glass shells on their outlines
  with the steel arches outside, the Cloud Mountain inside the Cloud Forest;
- the ArtScience Museum: the lotus, ten fingers round a bowl (no OSM piece of it is in the table);
- the Singapore Flyer: the 150 m wheel on its supports over the terminal (the rim's parts excluded since M2);
- the Helix Bridge's double helix over its deck; the Merlion on its pier;
- Victoria Theatre and Concert Hall's 54 m clock tower; the National Gallery's (Old Supreme Court's) dome; the Sultan
  Mosque's golden dome and minaret tops; Sri Mariamman Temple's gopuram; the Buddha Tooth Relic Temple's roofs;
- the National Stadium's 310 m dome (its OSM roof rings excluded).

Positions and plans from OSM (osm_buildings.gpkg / osm_parts.gpkg, the local Overpass for two relations, cached in
<data>/m4l_osm_rel.json), heights from data/landmarks.csv, shapes and colours from the photos in data/landmarks.md
("M4 figures").
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
DATA = HERE.parent / "data" / "singapore"
OUT = HERE / "generated" / "structures-m4l.toml"
UTM = 32648
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


def ground(p):
    """The scene ground 06_tiles stands a figure on at UTM point p."""
    global _T
    if _T is None:
        from city3d.common import Terrain
        _T = Terrain()
    return float(_T.height_utm([p[0]], [p[1]])[0])


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
           sections=None, tubes=None, boxes=None, prisms=None, slabs=None, walls=False, segments=None, note=None, glazing=None, model=None):
    """floor: the figure's 0 at this absolute height (m) whatever the ground under its point."""
    if floor is not None:
        base = floor - ground(at_utm)
    ys = [s[0] for s in sections or []] + [p[2] for p in prisms or []] + [b[1] + b[4] / 2 for b in boxes or []] \
        + [max(t[0][1], t[1][1]) for t in tubes or []] + [max(q[1] for q in s[0]) for s in slabs or []]
    top = top or max(ys + [1.0])
    seg = int(segments or 16)
    n = (2 * seg * max(0, len(sections or []) - 1) + 80 * len(tubes or []) + 12 * len(boxes or [])
         + sum(4 * len(p[0]) - 4 for p in prisms or []) + sum(4 * len(s[0]) - 4 for s in slabs or [])
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
    if model:
        out.append("model = { " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in model.items()) + " }")
        tri_est[name] += model.get("triangles", 0)
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


def chain(pts, r, colour=None):
    """Tubes along a polyline (figure frame points)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        t = [[round(float(v), 2) for v in a], [round(float(v), 2) for v in b], r]
        if colour:
            t.append(colour)
        out.append(t)
    return out


OB = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
OP = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM)


def osm(oid):
    s = OB[OB.osm_id == oid]
    if not len(s):
        s = OP[OP.osm_id == oid]
    g = s.geometry.iloc[0]
    return max(g.geoms, key=lambda q: q.area) if g.geom_type == "MultiPolygon" else g


REL = {e["id"]: e for e in json.loads((DATA / "m4l_osm_rel.json").read_text())["elements"]}


def rel_way(rid, wid):
    m = next(m for m in REL[rid]["members"] if m["ref"] == wid)
    return [TO_UTM.transform(q["lon"], q["lat"]) for q in m["geometry"]]


def resample(poly, n):
    """n points evenly along a polygon's exterior, counter-clockwise, starting at its east-most point."""
    ext = poly.exterior
    if not ext.is_ccw:
        ext = LineString(list(ext.coords)[::-1])
    L = ext.length
    pts = np.array([ext.interpolate(L * i / n).coords[0] for i in range(n)])
    k = int(np.argmax(pts[:, 0]))
    return np.roll(pts, -k, axis=0)


# ------------------------------------------------------------------ Marina Bay Sands SkyPark
# OSM w116800998 (339 x 58 m, axis 25.4 deg; the bow, rounded, 45 m north of Tower 3, the stern square over Tower 1's
# south end). Deck at 200 m over the towers' 198 m roofs (CTBUH: the towers' architectural tops 202.8-206.9 with it);
# the hull's underside 191 m over the towers, curving up to ~197 m at the bow's tip (the cantilever thins to ~3 m);
# the pool along the west (bay) edge of the north half; the deck's gardens; white-silver steel sides
SP = osm("w116800998")
c_sp = np.array(SP.centroid.coords[0])
AX = 25.4
right, fwd = frame_of(AX)
loc_sp = [local(q, c_sp, AX) for q in list(SP.exterior.coords)[:-1]]
loc_poly = Polygon(loc_sp)
TOWERS_Z = [(-152.0, -86.0), (-33.7, 27.5), (71.0, 130.0)]       # the towers' extents along the axis (OSM)
DECK, UNDER = 201.0, 190.0
WHITE, BELLY, DECKC = "#d9dcdd", "#8f989f", "#b7b3a8"


def under_at(z):
    """The hull's underside at z along the axis: 191.5 m from the stern to Tower 3's north face, rising toward the
    bow's tip on a curve (a cantilever thinning to ~3 m)."""
    z0, z1 = 130.0, 176.0
    if z <= z0:
        return UNDER
    t = min(1.0, (z - z0) / (z1 - z0))
    return UNDER + (DECK - 3.0 - UNDER) * t ** 1.4


prisms = []
zs = np.arange(-166.0, 178.0, 6.0)
belly = loc_poly.buffer(-7.0)
for za, zb in zip(zs, zs[1:]):
    cut = Polygon([[-60, za], [60, za], [60, zb], [-60, zb]])
    y0 = under_at(0.5 * (za + zb))
    # a convex belly (research: thickest on the centreline, thin at the edges): the outer band 4 m shallower,
    # the inner strip (7 m in from the edge) to the full depth, a darker silver-grey underneath
    for poly, yb, col in ((loc_poly, min(y0 + 4.0, DECK - 2.5), WHITE), (belly, y0, BELLY)):
        band = poly.intersection(cut)
        for pg in getattr(band, "geoms", [band]):
            if pg.geom_type != "Polygon" or pg.area < 2:
                continue
            pg = pg.simplify(0.3)
            prisms.append([[[round(x, 2), round(z, 2)] for x, z in list(pg.exterior.coords)[:-1]], yb,
                           DECK - 1.2 if col == WHITE else yb + 4.2, col])
# the deck's top: pale stone; the 146 m infinity pool on the towers' middle and north (research: mid-deck on the
# towers), gardens along the rim, two small white roof pavilions at the north and south thirds
top_poly = loc_poly.buffer(-1.0)
prisms.append([[[round(x, 2), round(z, 2)] for x, z in list(top_poly.simplify(0.5).exterior.coords)[:-1]], DECK - 1.2, DECK, DECKC])
pool = loc_poly.intersection(Polygon([[-60, -10], [60, -10], [60, 136], [-60, 136]])).buffer(-2.0)
west = pool.intersection(Polygon([[-60, -10], [60, -10], [60, 136], [-60, 136]]).buffer(0)).intersection(
    Polygon([[-60, -10], [-2.0, -10], [-6.0, 136], [-60, 136]]))
for pg in getattr(west, "geoms", [west]):
    if pg.area > 50:
        prisms.append([[[round(x, 2), round(z, 2)] for x, z in list(pg.simplify(0.5).exterior.coords)[:-1]], DECK, DECK + 0.2, "#4a8fa8"])
boxes = []
for k, z in enumerate(np.arange(-156.0, 150.0, 9.0)):     # planting along the east rim, and over the stern
    bx = loc_poly.intersection(LineString([[-60, z], [60, z]]))
    if bx.is_empty:
        continue
    x0, x1 = bx.bounds[0], bx.bounds[2]
    boxes.append([round(x1 - 3.0, 2), DECK + 0.7, round(z, 2), 3.0, 1.4, 6.5, "#56703f"])
    if z < -10:
        boxes.append([round(x0 + 3.0, 2), DECK + 0.7, round(z, 2), 3.0, 1.4, 6.5, "#56703f"])
for z in (-95.0, 95.0):
    bx = loc_poly.intersection(LineString([[-60, z], [60, z]]))
    boxes.append([round(0.5 * (bx.bounds[0] + bx.bounds[2]) + 6, 2), DECK + 2.0, z, 12.0, 4.0, 18.0, "#d6d6d2"])
figure("Marina Bay Sands SkyPark", c_sp, AX, WHITE, DECK + 4, prisms=prisms, boxes=boxes,
       note="Marina Bay Sands SkyPark (2010): the 340 m 'ship' over the three towers, its bow cantilevered north (OSM's\n"
            "outline w116800998, excluded in [buildings]; scripts/m4l_structures.py)")

# ------------------------------------------------------------------ Supertree Grove
# The twelve Supertrees of the grove as OSM maps them (rings of building:parts, excluded in [buildings]), clustered
# by centre, and three by the Cloud Forest (outlines only). Heights snapped to the five classes (25, 30, 37, 42 and
# 50 m, greenroofs.com) from OSM's rough tops; trunk: a concrete core in a planted steel frame, flared at the foot,
# dark plum-brown from afar (sampled #3e2b39 overcast; painted lighter); canopy: an open steel inverted cone, its
# diameter about two thirds of the height (est.), blue-purple ribs (#414259 sampled); the OCBC Skyway (128 m, 22 m
# up, OSM w687915906) between two trees
GROVE = OP[(OP["colour"].fillna("").str.lower() == "#76c82e")].copy()
trees = []
pts = np.c_[GROVE.geometry.centroid.x, GROVE.geometry.centroid.y]
used = np.zeros(len(GROVE), bool)
for i in range(len(GROVE)):
    if used[i]:
        continue
    near = np.hypot(*(pts - pts[i]).T) < 4.0
    used |= near
    trees.append((pts[near].mean(0), float(max(float(x) for x in GROVE[near]["height"]))))
for oid in ("w591619300", "w591619301", "w591619302"):            # three by the Cloud Forest (outlines, 26-30 m)
    trees.append((np.array(osm(oid).centroid.coords[0]), {"w591619302": 30.0}.get(oid, 26.0)))
# (M4 fix round 1, critic: canopies ~2x the trunk, trunks saturated maroon): the trunks' planting green over the
# purple frame, the canopy wider (radius 0.38 H) with eight ribs, its frame purple
TRUNK, PLANT, HOOD = "#4b5a3d", "#56713f", "#5b4470"


def snap(h):
    return 50.0 if h >= 48 else 42.0 if h >= 43 else 37.0 if h >= 39 else 30.0 if h >= 29 else 25.0


for k, (c, h) in enumerate(sorted(trees, key=lambda t: -t[1])):
    H = snap(h)
    Rc = 0.42 * H
    secs = [[0.0, 0, 0, 4.2, 4.2], [2.0, 0, 0, 3.0, 3.0], [0.3 * H, 0, 0, 2.3, 2.3], [0.6 * H, 0, 0, 2.5, 2.5],
            [0.72 * H, 0, 0, 3.0, 3.0], [0.8 * H, 0, 0, 0.3 * Rc, 0.3 * Rc]]
    # the canopy: an open inverted cone of steel members (see-through: the tile's lattice mesh), ribs as tubes
    cone = []
    for f_, y_ in ((0.3, 0.8 * H), (0.62, 0.9 * H), (0.86, 0.96 * H), (1.0, H)):
        cone.append([[round(f_ * Rc * math.cos(2 * math.pi * j / 16), 2), round(y_, 2), round(f_ * Rc * math.sin(2 * math.pi * j / 16), 2)]
                     for j in range(17)])
    tubes = []
    for j in range(8):
        a = 2 * math.pi * j / 8
        tubes.append([[0.3 * Rc * math.cos(a), 0.8 * H, 0.3 * Rc * math.sin(a)], [Rc * math.cos(a), H, Rc * math.sin(a)], 0.35, HOOD])
    figure(f"Supertree {k + 1}", c, 0.0, TRUNK, H + 0.5, sections=secs, segments=12, tubes=tubes,
           prisms=[[ring(0.3 * Rc, 12, 0.0), 0.8 * H - 0.5, 0.8 * H, HOOD], [ring(2.7, 8), 0.12 * H, 0.66 * H, PLANT, 0.85]],
           glazing=[{"grid": cone, "period": [1.3, 1.3], "colour": HOOD}],
           note=f"Supertrees (Gardens by the Bay, 2012): {len(trees)} figures, 25-50 m" if k == 0 else None)
WAYS = json.loads((DATA / "m4l_osm_ways.json").read_text())


def way_utm(wid):
    return [TO_UTM.transform(lon, lat) for lon, lat in WAYS[str(wid)]["geom"]]


SKY = way_utm(687915906)
c_sk = np.array(SKY[len(SKY) // 2])
pl = [local(q, c_sk) for q in SKY[::3] + [SKY[-1]]]
tubes = []
for (x0, z0), (x1, z1) in zip(pl, pl[1:]):
    tubes.append([[x0, 21.5, z0], [x1, 21.5, z1], 0.9, "#b98a4e"])
    tubes.append([[x0, 22.8, z0], [x1, 22.8, z1], 0.12, "#8c8f93"])
figure("OCBC Skyway", c_sk, 0.0, "#b98a4e", 23.0, tubes=tubes,
       note="OCBC Skyway (128 m, 22 m up between two Supertrees: OSM w687915906)")

# ------------------------------------------------------------------ Gardens by the Bay: the conservatories
# Flower Dome (OSM w171142595, 168 x 99 m, long axis 102 deg; 38 m) and Cloud Forest (w171142597, 99 x 94 m; 58 m, the
# project figure): asymmetric shells, not hemispheres (research: the Flower Dome highest toward its west end and
# sloping east, the Cloud Forest highest mid-way with steep faces). A height field over the outline: across the long
# axis at each station a rise to the ridge height there; the glass a see-through gridshell (the tile's lattice mesh),
# the white steel arches outside it across the short axis every ~13 m, a low plinth; the Cloud Mountain (42 m,
# planted) inside the Cloud Forest
GLASS, ARCH = "#a9bec2", "#eceeee"


def conservatory(name, oid, H, ridge, cross, n_u=15, n_v=17, arch_every=2, inner=None, rib_r=0.6):
    P = osm(oid)
    c, u, v, L, W, brg = rect(P)
    u = u if u[0] > 0 else -u                    # u toward the east: t = 0 at the west end
    Pl = Polygon([local(q, c, 0.0) for q in list(P.exterior.coords)[:-1]]).buffer(0)
    grid = []
    for t in np.linspace(0.004, 0.996, n_u):
        p0 = c + u * (t - 0.5) * L
        seg = Pl.intersection(LineString([local(p0 - v * 200, c), local(p0 + v * 200, c)]))
        if seg.is_empty:
            continue
        seg = max(getattr(seg, "geoms", [seg]), key=lambda g: g.length)
        a, b = np.array(seg.coords[0]), np.array(seg.coords[-1])
        Hr = 3.0 + (H - 3.0) * ridge(t) * min(1.0, min(t, 1 - t) / 0.06)   # the ends closed down to the plinth
        row = []
        for s in np.linspace(-1, 1, n_v):
            q = 0.5 * (a + b) + 0.5 * s * (b - a)
            y = 3.0 + (Hr - 3.0) * max(0.0, 1 - s * s) ** cross
            row.append([round(float(q[0]), 2), round(float(y), 2), round(float(q[1]), 2)])
        grid.append(row)
    tubes = []
    for i in range(1, len(grid) - 1, arch_every):
        tubes += chain([[p[0], p[1] + 0.7, p[2]] for p in grid[i][::2]], rib_r, ARCH)
    loc = [[round(x, 2), round(z, 2)] for x, z in list(Pl.exterior.simplify(0.5).coords)[:-1]]
    figure(name, c, 0.0, ARCH, H + 1, tubes=tubes, prisms=[[loc, 0.0, 3.0, "#b9b6ab"]] + (inner or []),
           glazing=[{"grid": grid, "period": [3.0, 3.0], "colour": GLASS}],
           note=f"{name}: an asymmetric glass shell on OSM's outline {oid} (excluded in [buildings]), {H:.0f} m")


# Flower Dome: highest toward the west end, a long fall to the east end
conservatory("Flower Dome", "w171142595", 38.0, lambda t: math.sin(math.pi * t) ** 0.5 * (1.0 - 0.4 * t) / 0.83, 0.42)
# Cloud Forest: highest mid-way, steep all round; the planted Cloud Mountain inside
CFm = osm("w171142597")
conservatory("Cloud Forest", "w171142597", 58.0, lambda t: math.sin(math.pi * t) ** 0.6, 0.45, n_u=13,
             inner=[[ring(17.0, 12, 0.0), 0.0, 34.0, "#4e6a3c", 0.6], [ring(10.0, 12, 0.0), 34.0, 42.0, "#58704a", 0.55]])

# ------------------------------------------------------------------ National Stadium
# The 310 m dome (Arup/DP Architects, 2014): a spherical cap 83 m high on a ring at the ground round the 20 m bowl;
# silver-white (ETFE and metal panels); the retractable roof's two halves over the pitch (a slightly darker oval)
ST = osm("w182827369")
c_st = np.array(ST.centroid.coords[0])
Rb = math.sqrt(ST.area / math.pi) * 0.99
Hd = 83.0
Rs = (Rb ** 2 + Hd ** 2) / (2 * Hd)
secs = []
for y in [0.0, 6.0, 14.0, 24.0, 35.0, 46.0, 56.0, 65.0, 72.0, 78.0, 81.5, 83.0]:
    r = math.sqrt(max(Rs ** 2 - (y + Rs - Hd) ** 2, 0.0))
    secs.append([y, 0, 0, max(r, 1.0), max(r, 1.0)])
ribs = []
for k in range(16):                                               # the steel ribs over the cap
    a = 2 * math.pi * k / 16
    pts = []
    for y in [0.0, 14.0, 35.0, 56.0, 72.0, 81.0]:
        r = math.sqrt(max(Rs ** 2 - (y + Rs - Hd) ** 2, 0.0)) + 0.8
        pts.append([r * math.cos(a), y + 0.6, r * math.sin(a)])
    ribs += chain(pts, 1.1, "#b7bcc1")
figure("National Stadium dome", c_st, 0.0, "#d3d7da", Hd, sections=secs, segments=40, tubes=ribs,
       note="National Stadium (2014): the 310 m dome, 83 m (OSM's roof rings on the outline w182827369 left out)")

# ------------------------------------------------------------------ ArtScience Museum
# Moshe Safdie's lotus (2011): ten fingers of unequal height in a swirl round a dish-shaped bowl, raised on a glazed
# ring of a base (12-15 m); the three tallest (60 m, Wikipedia) on the north-east and east, the lower ones (25-35 m)
# wrapping the west and south (research: the aerial photo); white fibre-reinforced polymer (#dcdad6 est. from
# #ece8e8 lit and #828e94 sky-lit samples). OSM's outline w261191086 (r14314416)
AS = Polygon(rel_way(14314416, 261191086))
c_as = np.array(AS.centroid.coords[0])
FINGERS = [(10, 46.0), (40, 60.0), (72, 60.0), (104, 56.0), (138, 40.0), (172, 32.0), (206, 27.0), (240, 26.0),
           (276, 30.0), (312, 36.0)]                              # (bearing of the finger, its tip's height)
for k, (brg, Ht) in enumerate(FINGERS):
    # in the finger's frame: z outward; sections up the finger, centres moving out, widths narrowing to the tip
    rows = []
    for t in np.linspace(0, 1, 7):
        y = 12.0 + (Ht - 12.0) * t
        z = 10.0 + (0.3 * Ht) * t ** 1.7
        w = 13.0 * (1 - t) ** 0.8 + 2.2 * t
        d = 5.0 * (1 - t) + 1.4 * t
        rows.append([round(y, 2), 0.0, round(z, 2), round(w, 2), round(d, 2)])
    figure(f"ArtScience Museum finger {k + 1}", c_as, brg, "#e2e0dc", Ht, sections=rows, segments=10,
           note="ArtScience Museum (2011): ten fingers round the bowl (OSM r14314416)" if k == 0 else None)
figure("ArtScience Museum bowl", c_as, 0.0, "#d8d6d2", 17.0, segments=20,
       sections=[[0.0, 0, 0, 17.0, 17.0], [9.0, 0, 0, 17.0, 17.0], [11.0, 0, 0, 21.0, 21.0], [14.5, 0, 0, 25.0, 25.0], [17.0, 0, 0, 25.5, 25.5]],
       prisms=[[ring(17.4, 20), 0.0, 9.0, "#6d7a80"]])

# ------------------------------------------------------------------ Singapore Flyer
# 165 m overall, a 150 m wheel (hub ~90 m: 15 m clearance + 75 m) over its three-storey terminal; the rim's plane from
# OSM's outline w230082125 (147 x 8 m, axis 52 deg); 28 capsules outboard of the rim; a trussed double rim, cable
# spokes in two planes; the spindle between two white pylons (2.3 m, one each side of the wheel), each held by a pair
# of cable stays fanning out to ground anchors (research: Arup, the side photo); no legs under the wheel
FL = osm("w230082125")
c_fl, u_fl, v_fl, Lf, Wf, brg_fl = rect(FL)
face_fl = (brg_fl + 90.0) % 360
R, HUB = 75.0, 90.0
tubes, boxes = [], []
nseg = 48
for side in (-3.0, 3.0):
    pts = [(R * math.cos(2 * math.pi * i / nseg), HUB + R * math.sin(2 * math.pi * i / nseg)) for i in range(nseg + 1)]
    tubes += [[[a[0], a[1], side], [b[0], b[1], side], 0.6] for a, b in zip(pts, pts[1:])]
for i in range(0, nseg, 2):
    a = 2 * math.pi * i / nseg
    tubes.append([[R * math.cos(a), HUB + R * math.sin(a), -3.0], [R * math.cos(a), HUB + R * math.sin(a), 3.0], 0.3])
for i in range(28):
    a = 2 * math.pi * (i + 0.5) / 28
    z = -9.0 if i % 2 else 9.0
    tubes.append([[0, HUB, z], [R * math.cos(a), HUB + R * math.sin(a), -3.0 if i % 2 else 3.0], 0.16, "#7d8287"])
for i in range(28):
    a = 2 * math.pi * i / 28
    rc = R + 4.0
    boxes.append([round(rc * math.cos(a), 2), round(HUB + rc * math.sin(a), 2), 0, 3.6, 3.4, 7.0, "#59626a"])
tubes.append([[0, HUB, -12.0], [0, HUB, 12.0], 2.0])
boxes.append([0, HUB, 0, 7.0, 7.0, 5.0])
for zf in (-1, 1):                                                 # a pylon each side, its two stays
    tubes.append([[0.0, 0.0, zf * 15.0], [0.0, HUB + 2.0, zf * 12.0], 1.15])
    for xf in (-1, 1):
        tubes.append([[0.0, HUB + 1.0, zf * 12.0], [xf * 42.0, 0.0, zf * 34.0], 0.18, "#8c9196"])
figure("Singapore Flyer", c_fl, face_fl, "#e6e8ea", 165.0, tubes=tubes, boxes=boxes,
       note="Singapore Flyer (2008): 165 m, a 150 m wheel, 28 capsules (the rim's OSM parts excluded since M2)")

# ------------------------------------------------------------------ Helix Bridge
# 280 m, an S-bend in plan along OSM's deck ways ("The Helix": w395120470 ... w687965211, north to south); two
# intertwined stainless steel helices round the deck (the envelope ~10.8 m across, unverified), joined by struts every
# few metres; silver #a8adb2 (sampled #838990-#938f89 in sun). The deck is OSM's bridge ways (05b_roads); the helix's
# axis is set ~3.6 m over the deck
HELIX_WAYS = [395120470, 395120469, 164881537, 687965213, 687965212, 687965211]
path = []
for w in HELIX_WAYS:
    q = way_utm(w)
    path += q if not path else q[1:]
c_hx = np.array(path[len(path) // 2])
line = LineString([local(q, c_hx) for q in path])
DECK_HX = 3.0                                                      # the deck as 05b_roads draws it (0.4-3.2 m over the water)
pitch, rad = 18.0, (5.2, 4.6)
n_s = int(line.length / 2.25)
tubes = []
P, Tn = [], []
for i in range(n_s + 1):
    s_ = line.length * i / n_s
    a, b = np.array(line.interpolate(max(0, s_ - 1)).coords[0]), np.array(line.interpolate(min(line.length, s_ + 1)).coords[0])
    t_ = (b - a) / max(np.linalg.norm(b - a), 1e-6)
    P.append((np.array(line.interpolate(s_).coords[0]), np.array([t_[1], -t_[0]]), s_))
for k, (r, ph, rr) in enumerate(((rad[0], 0.0, 0.32), (rad[1], math.pi, 0.26))):
    pts = [[p[0] + n[0] * r * math.cos(2 * math.pi * s_ / pitch + ph), DECK_HX + 3.6 + r * math.sin(2 * math.pi * s_ / pitch + ph),
            p[1] + n[1] * r * math.cos(2 * math.pi * s_ / pitch + ph)] for p, n, s_ in P]
    tubes += chain(pts, rr, "#aeb3b8")
    if k == 0:
        outer = pts
    else:
        tubes += [[a, b, 0.1, "#aeb3b8"] for a, b in zip(outer[::6], pts[::6])]
figure("Helix Bridge", c_hx, 0.0, "#aeb3b8", DECK_HX + 9.5, tubes=tubes,
       note="Helix Bridge (2010): the double helix round the deck along OSM's ways (4 viewing pods not drawn)")

# ------------------------------------------------------------------ the Merlion
# 8.6 m, on the tip of Merlion Park's pier, facing east (Wikipedia: aligned to face east), spouting toward the bay;
# white-grey cement (#e9e4d8 est.). M4 fix round 1 (critic: a grey bollard with a stiff rod, ~25 m inland): white, a
# lion's head in its mane over a fish body on a curled tail, the muzzle forward; the jet a translucent white arc (fabric
# ribbons over a thin core) into the bay; moved 4 m east to the scene's water edge on a granite platform (OSM's point
# lies 6 m from the scene's water: the pier's tip is not mapped as land)
c_me0 = utm(103.8544913, 1.2867871)
c_me = c_me0 + 4.0 * np.array([math.sin(math.radians(84.0)), math.cos(math.radians(84.0))])
WHITE_ME = "#e2e0d9"
# M7 (critic round 2: still a ball on a stem, a mushroom or hydrant): a low-poly figure from photos
# (scripts/m7_merlion.py writes data/singapore/models/merlion.obj: the lion's head in its tiered, grooved hood, the open
# mouth with the spout, the scaled fish body with its fan tail, on a wave plinth), on the granite platform; the jet from
# the spout pipe's end (0, 6.45, 1.8)
jet = [(0.0, 6.45 + 1.2 * t - 8.7 * t * t, 1.9 + 12.0 * t) for t in np.linspace(0, 1, 13)]
figure("Merlion", c_me, 90.0, WHITE_ME, 8.6,
       model={"file": "models/merlion.obj", "cut": 0.0, "up": "+y", "front": "+z", "height": 8.6, "triangles": 9000},
       prisms=[[ring(4.6, 16), -1.2, 0.3, "#9a978f"]],
       tubes=chain(jet, 0.1, "#eef3f5"),
       glazing=[{"grid": [[[x, round(y, 2), round(z, 2)] for _, y, z in jet] for x in (-0.35, 0.35)], "period": [30.0, 30.0],
                 "colour": "#f4f8fa", "kind": "fabric"},
                {"grid": [[[0.0, round(y + dy, 2), round(z, 2)] for _, y, z in jet] for dy in (-0.35, 0.35)], "period": [30.0, 30.0],
                 "colour": "#f4f8fa", "kind": "fabric"}],
       note="Merlion (1972): 8.6 m, white, facing east at the water's edge, its jet arcing into the bay")

# ------------------------------------------------------------------ Victoria Theatre and Concert Hall: the clock tower
# 54 m (Wikipedia), 1906, between the theatre and the concert hall on the Empress Place front; white render, a square
# shaft with the clock stage, a belfry and a domed cupola with a lantern
VT = osm("r3899820") if (OB.osm_id == "r3899820").any() else None
c_vt = utm(103.85159, 1.28835) if VT is None else np.array(VT.centroid.coords[0])
VTF = 35.0
WR = "#ecebe4"
figure("Victoria clock tower", c_vt, VTF, WR, 54.0,
       prisms=[[square(5.0), 0.0, 33.0, WR], [square(5.6), 33.0, 34.2, "#d8d6cc"], [square(4.6), 34.2, 41.0, WR],
               [square(5.0), 41.0, 42.0, "#d8d6cc"], [ring(3.8, 8), 42.0, 47.0, WR], [ring(3.9, 8), 47.0, 51.0, "#8a8f8c", 0.25],
               [ring(0.9, 8), 51.0, 54.0, "#8a8f8c", 0.1]],
       boxes=[[0, 37.6, 4.65, 3.2, 3.2, 0.2, "#f4f2ea"], [0, 37.6, -4.65, 3.2, 3.2, 0.2, "#f4f2ea"],
              [4.65, 37.6, 0, 0.2, 3.2, 3.2, "#f4f2ea"], [-4.65, 37.6, 0, 0.2, 3.2, 3.2, "#f4f2ea"]],
       note="Victoria Theatre and Concert Hall: the 54 m clock tower (1906) over the halls' 25 m roofs")

# ------------------------------------------------------------------ National Gallery: the Old Supreme Court's dome
# OSM's drum part w334127038 (36 m, r 8.6) and the 42 m needle w334127041 over it are excluded and rebuilt: the drum
# to 30 m with its colonnade's attic, the green copper dome to 38 m, the lantern to 42 m
DM = osm("w334127038")
c_dm = np.array(DM.centroid.coords[0])
rd = math.sqrt(DM.area / math.pi)
# (research: a tall drum with a colonnade, the finial ~50-60 m by a photo's scale (est.), OSM's mapper 36/42 m:
# between them, the dome's top at 40 m and the finial at 45; verdigris #96b7bd sampled in sun, painted #8fb0a6)
figure("Old Supreme Court dome", c_dm, 0.0, "#8fb0a6", 45.0, segments=24,
       prisms=[[ring(rd, 16), 20.0, 30.0, "#d9d3c4"], [ring(rd + 0.6, 16), 30.0, 31.2, "#cbc4b2"]],
       sections=[[31.2, 0, 0, rd - 0.3, rd - 0.3], [34.0, 0, 0, rd - 1.0, rd - 1.0], [36.8, 0, 0, rd - 2.8, rd - 2.8],
                 [38.9, 0, 0, rd - 5.4, rd - 5.4], [40.0, 0, 0, 1.6, 1.6]],
       tubes=[[[0, 39.8, 0], [0, 43.2, 0], 1.1, "#d9d3c4"], [[0, 43.2, 0], [0, 45.0, 0], 0.45, "#8fb0a6"]])

# ------------------------------------------------------------------ Sultan Mosque
# The golden onion dome over the prayer hall (OSM's dome part w1165450368 is 4 m on a 12 m min_height: dropped),
# on a black drum band (bottle ends); the two big minarets' tops (w694102549, w1165450378, 17-29 m) as octagonal
# turrets with gilt onion caps
SD = osm("w1165450368")
c_sd = np.array(SD.centroid.coords[0])
r_sd = 9.4                        # the dome ~15 m across (research, est. from the photo: 30 % of the front)
GOLD = "#bc9a4c"
figure("Sultan Mosque dome", c_sd, 0.0, GOLD, 31.0, segments=24,
       prisms=[[ring(r_sd * 0.72, 16), 12.0, 16.0, "#e3d8bf"], [ring(r_sd * 0.74, 16), 16.0, 18.0, "#2b2b2b"]],
       sections=[[18.0, 0, 0, r_sd * 0.72, r_sd * 0.72], [21.0, 0, 0, r_sd * 0.80, r_sd * 0.80], [24.0, 0, 0, r_sd * 0.72, r_sd * 0.72],
                 [27.0, 0, 0, r_sd * 0.45, r_sd * 0.45], [29.0, 0, 0, r_sd * 0.16, r_sd * 0.16], [30.0, 0, 0, 0.4, 0.4]],
       tubes=[[[0, 29.8, 0], [0, 32.5, 0], 0.18, GOLD]])
for oid in ("w694102549", "w1165450378"):
    M = osm(oid)
    cm = np.array(M.centroid.coords[0])
    rm = math.sqrt(M.area / math.pi)
    figure("Sultan Mosque minaret", cm, 0.0, GOLD, 30.0, segments=12,
           prisms=[[ring(rm, 8), 17.0, 25.0, "#e8dcc0"], [ring(rm + 0.6, 8), 25.0, 25.6, "#d8cba8"]],
           sections=[[25.6, 0, 0, rm * 0.75, rm * 0.75], [27.0, 0, 0, rm * 0.9, rm * 0.9], [28.6, 0, 0, rm * 0.5, rm * 0.5], [29.6, 0, 0, 0.3, 0.3]])

# ------------------------------------------------------------------ Sri Mariamman Temple: the gopuram
# The entrance tower over the South Bridge Road gate (the outline's east end, w300380459): ~15 m, six tiers of
# painted figures, tapering, a barrel top with kalasams; pastel from afar (pink, ochre, blue figures)
TM = osm("w300380459")
c_tm, u_tm, v_tm, Lt, Wt, brg_tm = rect(TM)
east = u_tm if u_tm[0] > 0 else -u_tm
gp = c_tm + east * (Lt / 2 - 5.0)
face_g = math.degrees(math.atan2(east[0], east[1])) % 360
tiers = []
# ~18 m (est.; no published height): a plain dark-grey gateway base (~5 m), five sculpted tiers each a little smaller,
# a barrel crown with gilt finials; from afar a mid-tone of many colours (#70706b sampled overall, overcast)
w0, d0 = 6.0, 3.2
tiers.append([rectangle(w0, d0), 0.0, 5.0, "#6e6c68"])
y, w, d = 5.0, w0 * 0.97, d0 * 0.95
for k in range(5):
    tiers.append([rectangle(w, d), y, y + 2.2, ["#b98f86", "#7f9a98", "#c5a774", "#a98a9e", "#c2b49a"][k], 0.9])
    y += 2.2
    w, d = w * 0.88, d * 0.88
tiers.append([rectangle(w, d * 0.6), y, y + 1.6, "#c07a4e", 0.7])
y += 1.6
figure("Sri Mariamman gopuram", gp, face_g, "#a08c7c", y + 1.0, prisms=tiers,
       tubes=[[[x, y, 0], [x, y + 1.0, 0], 0.22, "#c9a24a"] for x in np.linspace(-w * 0.7, w * 0.7, 5)])

# ------------------------------------------------------------------ Buddha Tooth Relic Temple: the Tang roofs
# OSM's parts: the hall (w429674890, 972 m², the table's 17.5 m) and the central tower (w429674895, 145 m², 21 m):
# dark tiled hip roofs with deep eaves on both, a gilt finial
BT = osm("w429674890")
c_bt, u_bt, v_bt, Lb, Wb, brg_bt = rect(BT)
BT2 = osm("w429674895")
c_b2, _, _, Lb2, Wb2, _ = rect(BT2)
x2, z2 = local(c_b2, c_bt, brg_bt + 90.0)
ROOF = "#3b3c3b"                   # dark charcoal tiles (research M4 fix round 1: #5a5d5b est; #361818 sampled overcast)
GILT = "#c9a24a"
# M4 fix round 1 (critic: a beige office, flat roof, a small dark pyramid): the walls a red landmark row (temple style);
# here the Tang roofs stacked: pent eaves round the hall at 6.5 and 12 m, the hall's double-eaved hip roof (a deep eave,
# then the hip) with a gilt ridge, the central tower's own eave and hip roof with a gilt finial, the eaves' corners
# turned up
def eave(hx, hz, y, d, cx=0.0, cz=0.0, rise=1.0, colour=ROOF):
    """A pent eave d m deep round a hx x hz body at y: a frustum down to the wall, its four corners turned up."""
    k = min(hx, hz) / (min(hx, hz) + d)
    out = [[rectangle(hx + d, hz + d, cx, cz), y, y + rise, colour, k]]
    tips = [[[cx + sx * (hx + d), y + 0.1, cz + sz * (hz + d)], [cx + sx * (hx + d + 0.6), y + 0.9, cz + sz * (hz + d + 0.6)], 0.16, GILT]
            for sx in (-1, 1) for sz in (-1, 1)]
    return out, tips


pr, tb = [], []
for y in (6.5, 12.0):
    a, t = eave(Lb / 2, Wb / 2, y, 2.0)
    pr += a
    tb += t
a, t = eave(Lb / 2, Wb / 2, 17.5, 2.6, rise=0.8)
pr += a
tb += t
# (the hip steep enough to read as a tile slope, not a flat roof: the facade shader takes faces under 26 degrees as flat
# roofs in the city's roof tones; the central tower's 21 m walls stand inside it, its finial on the ridge)
pr.append([rectangle(Lb / 2 + 0.6, Wb / 2 + 0.6), 18.3, 25.3, ROOF, 0.28])
tb.append([[-0.28 * (Lb / 2 + 0.6), 25.3, 0], [0.28 * (Lb / 2 + 0.6), 25.3, 0], 0.35, GILT])
tb.append([[x2, 25.3, z2], [x2, 29.0, z2], 0.35, GILT])
figure("Buddha Tooth Relic Temple roofs", c_bt, brg_bt + 90.0, ROOF, 30.0, prisms=pr, tubes=tb,
       note="Buddha Tooth Relic Temple (2007): Tang-style tiered roofs over its red walls (the walls: landmark_facades.csv)")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("# generated by scripts/m4l_structures.py (edit the script, not this file): Singapore's landmark figures (M4)\n\n"
               + "\n".join(blocks))
print(f"{OUT}: {len(blocks)} figures")
for k, v in tri_est.items():
    print(f"  {k}: ~{v:,} triangles")
print(f"  total ~{sum(tri_est.values()):,}")
