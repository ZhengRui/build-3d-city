"""The hk-hongkong preset's rooftop clutter (06c_rooftops): china-south's programmes under Hong Kong's style names.
Estate blocks, private towers and composite buildings get the apartment towers' roofs (lift and stair bulkheads, water
tanks, plant), tong lau the urban village's (tanks, stair boxes, sheds and plants: the rooftop huts), industrial
buildings the factory's, colonial civic buildings the civic one.
M6: estate and apartment towers take china-south's slab-block programme (Singapore's HDB) without its PV rows: lift motor
rooms over the cores, the water-tank housing on the plant room, a few aerial masts; no helipads (a Mainland fire-code
look). Composite buildings keep the apartment towers' clutter (steel tanks, plants, condensers).

M4 fix round 1 (city.toml `[rooftops] street_signs = true`, opt-in): projecting street signs (招牌) on the tong lau and
composite buildings' walls that face a street: boxes 0.3-0.4 m thick standing out from the wall at right angles, on
floors 1-6 (from 3.6 m up to 22 m, under the roof), in columns every 2-5 m along the front, one to three a column, tall
upright boards (0.9-2.2 m out, 2-6 m high) and wide ones (2.5-5.5 m out, 0.9-1.8 m high), in the colours of Nathan Road's
and Sham Shui Po's light boxes (white, yellow, red, blue, green, black). Densest on primary, secondary and tertiary roads,
fewer on side streets and market streets (Apliu Street, Fa Yuen Street: residential, pedestrian, unclassified), a few
on trunk roads; none on service roads, footways or motorways. A wall faces a street when a road of those classes
lies 3-24 m out from its middle along its normal and no building stands in the first 1.5 m (party walls, back lanes
against a neighbour). The boards reach at most to 3.5 m short of the road's centre line. Prototype `sign` (a box),
material `sign` (rooftops.js: a lit board with a column or row of glyphs; its own instanced mesh, lit after dark).
Each column of boards is its own roof record (the records' height is the lowest board's foot: items stand at most
12.75 m over their record)."""
import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString

from ...common import CFG, DATA
from ..china_south.rooftops import PROGRAMME as CS
from ..china_south.rooftops import hdb


def estate(it, roof, rng, y, b):
    return hdb(it, roof, rng, y, b, hk=True)


SIGNS_ON = bool(CFG["rooftops"].get("street_signs", False))
EXTRA_PROTOS = ["sign"] if SIGNS_ON else []
EXTRA_MATS = ["sign"] if SIGNS_ON else []

# share of a front's sign columns per road class (none for the classes left out)
SIGN_DENSITY = {"primary": 0.9, "secondary": 0.9, "tertiary": 0.75, "primary_link": 0.5, "secondary_link": 0.5,
                "unclassified": 0.6, "residential": 0.55, "pedestrian": 0.65, "living_street": 0.55, "trunk": 0.25}
SIGN_COLOURS = ["sign_white", "sign_white", "sign_cream", "sign_yellow", "sign_yellow", "sign_red", "sign_red",
                "sign_blue", "sign_green", "sign_black", "sign_orange", "sign_pink"]
ROADS = None


def roads():
    """The roads signs face (their classes' density): an STRtree of 05b's centre lines (loaded once, before the
    stage's workers fork)."""
    global ROADS
    if ROADS is None:
        w = gpd.read_file(DATA / "roads.gpkg", layer="ways", columns=["highway"])
        w = w[w.highway.isin(list(SIGN_DENSITY)) & w.geometry.notna()]
        ROADS = (shapely.STRtree(w.geometry.values), w.geometry.values, w.highway.map(SIGN_DENSITY).values.astype(float))
    return ROADS


if SIGNS_ON and (DATA / "roads.gpkg").exists():
    roads()


def world_poly(roof):
    """The roof's outline back in map coordinates (Roof.local is it in the roof's own frame)."""
    c, s = roof.cos, roof.sin
    return shapely.affinity.affine_transform(roof.local, [c, -s, s, c, roof.cx, roof.cy])


def street_signs(it, roof, rng, h, b):
    """Projecting signs on the walls of this roof's building that face a street (see the module docstring)."""
    from ...stages import rooftops as R          # (the stage's machinery: G, M, C, PROTOS)
    if h < 7 or not roof.ok:
        return
    tree, geoms, dens = roads()
    btree, bgeoms = R.G["tree"], R.G["geoms"]
    proto, mat = R.PROTOS.index("sign"), R.M["sign"]
    cols = [R.C[n] for n in SIGN_COLOURS]
    poly = world_poly(roof)
    top = min(h - 1.2, 22.0)
    if top < 5.0:
        return
    for ring in [poly.exterior]:
        pts = np.asarray(ring.coords)
        for p0, p1 in zip(pts[:-1], pts[1:]):
            d = p1 - p0
            L = float(np.hypot(*d))
            if L < 3.5:
                continue
            t = d / L
            n = np.array([t[1], -t[0]])
            mid = (p0 + p1) / 2
            if poly.contains(shapely.Point(*(mid + n * 0.4))):
                n = -n
            # a neighbour against this wall: no street front
            probe = shapely.Point(*(mid + n * 1.5))
            if any(bgeoms[j].contains(probe) for j in btree.query(probe)):
                continue
            ray = LineString([mid + n * 0.5, mid + n * 24.0])
            hit = tree.query(ray, predicate="intersects")
            if not len(hit):
                continue
            dist, k = min((float(shapely.distance(shapely.Point(*mid), shapely.intersection(ray, geoms[j]))), dens[j]) for j in hit)
            if dist < 3.0:
                continue
            reach = max(1.0, dist - 3.5)
            yaw = float(np.arctan2(n[1], n[0]))
            a = float(rng.uniform(0.6, 2.0))
            while a < L - 0.6:
                if rng.random() < k:
                    column(it, rng, p0 + t * a, n, yaw, reach, top, proto, mat, cols)
                a += float(rng.uniform(2.0, 5.0))


def column(it, rng, at, n, yaw, reach, top, proto, mat, cols):
    """One column of 1-3 boards at a point of the wall: its own roof record at the lowest board's foot."""
    boards, y = [], float(rng.uniform(3.6, 6.5))
    for _ in range(int(rng.integers(1, 4))):
        if rng.random() < 0.65:          # upright
            sx, sy = float(rng.uniform(0.9, 2.2)), float(rng.uniform(2.0, 6.0))
        else:                            # wide
            sx, sy = float(rng.uniform(2.5, 5.5)), float(rng.uniform(0.9, 1.8))
        sx = min(sx, reach)
        if y + sy > top or (boards and y + sy - boards[0][0] > 12.7):
            break
        boards.append((y, sx, sy))
        y += sy + float(rng.uniform(0.4, 2.5))
    if not boards:
        return
    gap = 0.15
    y0 = boards[0][0]
    it.roofs.append([float(at[0]), float(at[1]), yaw, y0 + it.base, 0])
    for by, sx, sy in boards:
        c = at + n * (gap + sx / 2)
        it.world(proto, mat, cols[int(rng.integers(len(cols)))], float(c[0]), float(c[1]), by, yaw, sx, sy,
                 float(rng.uniform(0.28, 0.42)))


def with_signs(programme):
    def run(it, roof, rng, y, b):
        programme(it, roof, rng, y, b)
        if it.roofs and not it.roofs[-1][4]:
            it.roofs.pop()                       # (the roof's own record, left empty)
        street_signs(it, roof, rng, y, b)
        # (06c_rooftops ends the roof with it.end(), which drops the last record if empty: it never is here, or is
        # the previous building's)
    return run if SIGNS_ON else programme


PROGRAMME = {**CS, "estate": estate, "apartment": estate, "composite": with_signs(CS["residential"]),
             "tonglau": with_signs(CS["village"]), "industrial": CS["factory"], "colonial": CS["civic"]}
