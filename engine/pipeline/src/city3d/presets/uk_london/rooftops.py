"""The uk-london preset's rooftop clutter (06c_rooftops): europe-west's items (stacks, pots, hatches, plant) in
London's programmes (region_research.md §4.5). Stacks are stock brick, sooted or red ([rooftops] stack_cols in
uk-london.toml), pots terracotta. On the terraces they are London's own (london_stack, [rooftops.london]): one
big stack per party wall at the house-width rhythm, its long side along the wall (front to back, at right
angles to the street), 1.5-2.5 m over the roof, with 6-14 pots in one or two rows; also on the flat roofs behind
the parapets ([rooftops] flat_party), and every 5-7 m along the street front of a footprint that stands for
several houses (no party walls inside it in the data):
  georgian, stucco  party-wall stacks (95 %, a second at the back now and then), roof lights, hatches
  victorian         party-wall stacks astride the ridge (90 %), 5-12 pots, a roof light now and then
  mansion           tall stacks with 8-14 pots on the party walls and every 6-9 m along the fronts, a hatch,
                    a plant box on some
  warehouse         a stack on some, a hatch, flat plant on big roofs
  portland, civic   europe-west's civic: hatch, lantern, vents, plant
  estate            europe-west's post-war flat roof: lift housing, stair box, vents, a boiler flue
  modern, glass     europe-west's
No zinc hatches' Paris stair lanterns on terraces, no wooden water tanks.
"""
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import box as rect

from ...common import CFG, DATA
from ...stages import rooftops as R06c
from ...stages.rooftops import BOX, C, M, POTS, pick
from ..europe_west.rooftops import (PROGRAMME as EW, POT_COLS, STACK_COLS, flat_block, flat_plant, overrun,
                                    roof_hatch, velux, vents)

# ([rooftops.london] in uk-london.toml; these defaults are its values)
LON = {"pot_pitch": 0.36, "two_rows": 8, "above": [1.5, 2.5], "every": [5.0, 7.0], "front_d": [3.5, 5.5],
       "multi_area": 350.0, "street": 14.0} | CFG["rooftops"].get("london", {})


def london_stack(it, rng, E, N, yaw, n, y0, top, col=None):
    """A London party-wall stack (L along yaw) from y0 (the eaves) to `top`, with n pots on it: one row along its
    middle up to LON two_rows pots, else two rows side by side (a flue each, the stack as thick as two pots)."""
    rows = [n] if n < LON["two_rows"] else [(n + 1) // 2, n // 2]
    per = rows[0]
    L = per * LON["pot_pitch"] + rng.uniform(0.25, 0.45)
    T = rng.uniform(0.7, 0.85) if len(rows) == 1 else rng.uniform(1.0, 1.25)
    col = C[col] if col else C[pick(rng, STACK_COLS)]
    it.world(BOX, M["chimney"], col, E, N, y0, yaw, L, top - y0, T)
    d = min(rng.uniform(0.22, 0.27), T / len(rows) - 0.12)
    ph, pc = rng.uniform(0.35, 0.6), C[pick(rng, POT_COLS)]
    ux, uy = np.cos(yaw), np.sin(yaw)
    for j, k in enumerate(rows):
        a = 0.0 if len(rows) == 1 else (j - 0.5) * T / 2           # across the stack
        l = (L - 0.2) * k / per
        c = -(L - 0.2) / 2 + l / 2                                  # a shorter second row starts at the same end
        it.world(POTS, M["pot"], pc, E + ux * c - uy * a, N + uy * c + ux * a, top, yaw, l, ph, d, k)
    return L, T


def _place(it, roof, rng, b, cx, cy, yaw, pots, above, top0, check):
    """One London stack at (cx, cy), if its footprint fits `check` (a polygon it must stay in)."""
    n = int(rng.integers(pots[0], pots[1] + 1))
    rows = 1 if n < LON["two_rows"] else 2
    L = ((n + 1) // 2 if rows == 2 else n) * LON["pot_pitch"] + 0.45
    T = 1.25 if rows == 2 else 0.85
    foot = affinity.translate(affinity.rotate(rect(-L / 2, -T / 2, L / 2, T / 2), np.degrees(yaw), origin=(0, 0)),
                              cx, cy)
    if check is not None and not check.contains(foot):
        return False
    london_stack(it, rng, cx, cy, yaw, n, b["eaves"], top0 + rng.uniform(*above))
    if roof.ok:
        la = roof.to_local(shapely.Point(cx, cy))
        roof.take(la.x, la.y, L + 0.4, L + 0.4, 0.2)
    return True


_STREETS = []


def _touching(lines, p):
    """The longest of `lines` ending within 0.6 m of point p (0 if none)."""
    best = 0.0
    for q0, q1 in lines:
        if min(np.hypot(q0[0] - p[0], q0[1] - p[1]), np.hypot(q1[0] - p[0], q1[1] - p[1])) < 0.6:
            best = max(best, float(np.hypot(q1[0] - q0[0], q1[1] - q0[1])))
    return best


def street_d(pts):
    """Distance (m) from each point to the nearest street centre line (roads.gpkg's minor and major ways and
    pedestrian streets; not service lanes, which are the mews behind the terraces), to tell a terrace's front
    from its back. Read once per worker process."""
    if not _STREETS:
        import geopandas as gpd
        try:
            w = gpd.read_file(DATA / "roads.gpkg", layer="ways", columns=["kind", "highway"])
            w = w[w.kind.isin(["minor", "major"]) | (w.highway == "pedestrian")]
            _STREETS.append(shapely.STRtree(w.geometry.values))
        except Exception:                                   # no roads: every wall as far as any other
            _STREETS.append(None)
    tree = _STREETS[0]
    pts = shapely.points(np.asarray(pts, float).reshape(-1, 2))
    if tree is None:
        return np.zeros(len(pts))
    i = tree.nearest(pts)
    return shapely.distance(pts, tree.geometries[i])


def wall_stacks(it, roof, rng, b, p=0.95, pots=(6, 14), above=None, p_back=0.35):
    """A stack on each party wall (built from one side of a shared wall), its long side along the wall, set back
    front_d from the street front (the end of the wall nearer a street, on the house's whole front wall), so the stacks of a terrace line up at its house-width rhythm; on a deep house a second, smaller one
    at the back now and then. Under a pitched roof it stands astride the ridge (the zone's band). Returns the
    stacks placed and their centres."""
    fp, zone = b["footprint"], b.get("zone")
    above = above or LON["above"]
    check = fp.buffer(0.05) if fp is not None else None
    placed = []
    for (x0, y0), (x1, y1) in b["party"]:
        dx, dy = x1 - x0, y1 - y0
        L = float(np.hypot(dx, dy))
        if L < 3 or rng.random() > p:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if fp is not None and not fp.contains(shapely.Point(mx + nx * 0.5, my + ny * 0.5)):
            nx, ny = -nx, -ny
        # a wall shared by two roofs: built on from one side (the one facing roughly east-north-east)
        if nx * 0.94 + ny * 0.34 < 0 and rng.random() < 0.85:
            continue
        off = 0.65
        # the street front: the end nearer a street, unless the other ends on the house's whole front wall (the
        # back is the ragged side, closet wings and light wells, where a mews often runs too)
        d0, d1 = street_d([(x0, y0), (x1, y1)])
        d0 -= 0.6 * min(_touching(b["free"], (x0, y0)), 8.0)
        d1 -= 0.6 * min(_touching(b["free"], (x1, y1)), 8.0)
        if d1 < d0:                                          # the street at the (x1, y1) end
            x0, y0, x1, y1, ux, uy = x1, y1, x0, y0, -ux, -uy
        yaw = float(np.arctan2(uy, ux))
        spots = []
        if zone is not None and b["shape"]:
            # astride the ridge: the middle of the wall's stretch over the roof's top band
            line = shapely.LineString([(x0 + nx * off, y0 + ny * off), (x1 + nx * off, y1 + ny * off)])
            try:
                g = line.intersection(zone)
            except shapely.errors.GEOSException:
                continue
            g = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "LineString" and q.length > 0.3]
            if not g:
                continue
            c = min(g, key=lambda q: line.project(q.centroid)).centroid
            spots.append((c.x, c.y, pots))
        else:
            s = min(rng.uniform(*LON["front_d"]), L / 2)
            spots.append((x0 + ux * s + nx * off, y0 + uy * s + ny * off, pots))
            if L >= 14 and rng.random() < p_back:
                s = L - rng.uniform(2.0, 3.5)
                spots.append((x0 + ux * s + nx * off, y0 + uy * s + ny * off, (pots[0], max(pots[0], pots[1] // 2 + 1))))
        for cx, cy, pr in spots:
            if any((cx - qx) ** 2 + (cy - qy) ** 2 < 4 for qx, qy in placed):
                continue
            if _place(it, roof, rng, b, cx, cy, yaw, pr, above, b["h"], check):
                placed.append((cx, cy))
    return placed


def front_stacks(it, roof, rng, b, placed, every=None, pots=(6, 14), above=None, min_area=None):
    """Footprints that stand for several houses (no party walls inside them in the data): a stack every
    `every` metres (one house width, the same along the whole front) at right angles to each long free wall on
    a street (within LON street m of its centre line), front_d in from it (a pitched roof's: astride the ridge),
    as the party walls inside would carry them. Corner and end houses (small footprints) keep their party-wall
    stacks only."""
    fp = b["footprint"]
    if fp is None or fp.area < (min_area or LON["multi_area"]):
        return placed
    above = above or LON["above"]
    w = rng.uniform(*(every or LON["every"]))
    inner = fp.buffer(-0.2)
    for (x0, y0), (x1, y1) in b["free"]:
        dx, dy = x1 - x0, y1 - y0
        L = float(np.hypot(dx, dy))
        if L < 2 * w or street_d([((x0 + x1) / 2, (y0 + y1) / 2)])[0] > LON["street"]:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        if not fp.contains(shapely.Point((x0 + x1) / 2 + nx * 0.5, (y0 + y1) / 2 + ny * 0.5)):
            nx, ny = -nx, -ny
        yaw = float(np.arctan2(ny, nx))                      # its long side into the building
        n = int(L // w)
        t0 = (L - n * w) / 2                                 # the houses centred on the front
        d0 = b["roof_d"] if b["shape"] == "pitched" else rng.uniform(*LON["front_d"])
        for i in range(1, n):
            t = t0 + i * w
            cx, cy = x0 + ux * t + nx * d0, y0 + uy * t + ny * d0
            if any((cx - qx) ** 2 + (cy - qy) ** 2 < 9 for qx, qy in placed):
                continue
            if _place(it, roof, rng, b, cx, cy, yaw, pots, above, b["h"], inner):
                placed.append((cx, cy))
    return placed


def lone_stack(it, roof, rng, b, pots, above=None):
    """A house without party walls (detached, or the data's): one stack at right angles to its street wall,
    front_d in from it."""
    fp = b["footprint"]
    if fp is None or not b["free"]:
        return
    fr = [e for e in b["free"] if np.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]) >= 2]
    if not fr:
        return
    (x0, y0), (x1, y1) = fr[int(np.argmin(street_d([((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)
                                                     for e in fr])))]
    L = float(np.hypot(x1 - x0, y1 - y0))
    if L < 2:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    if not fp.contains(shapely.Point((x0 + x1) / 2 + nx * 0.5, (y0 + y1) / 2 + ny * 0.5)):
        nx, ny = -nx, -ny
    d0 = b["roof_d"] if b["shape"] == "pitched" else rng.uniform(*LON["front_d"])
    t = L * rng.uniform(0.25, 0.75)
    _place(it, roof, rng, b, x0 + ux * t + nx * d0, y0 + uy * t + ny * d0, float(np.arctan2(ny, nx)), pots,
           above or LON["above"], b["h"], fp.buffer(-0.2))


def with_neighbours(it, b, drop=4.0):
    """The building's walls with those against a lower neighbour (a house of the terrace up to `drop` m lower:
    the survey's heights step from house to house) counted as party walls too: 06_tiles' party walls are only
    those against a neighbour reaching this roof's eaves, so the taller house of each pair had none there and
    the stack fell back to the middle of the roof."""
    if b["footprint"] is None or not b["free"]:
        return b
    tree, heights = R06c.G["tree"], R06c.G["heights"]
    fp, top = b["footprint"], it.base + b["h"]
    party, free = list(b["party"]), []
    for e in b["free"]:
        (x0, y0), (x1, y1) = e
        L = float(np.hypot(x1 - x0, y1 - y0))
        if L < 3:
            free.append(e)
            continue
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if fp.contains(shapely.Point(mx + nx * 0.5, my + ny * 0.5)):
            nx, ny = -nx, -ny
        q = shapely.Point(mx + nx * 0.4, my + ny * 0.4)
        hit = tree.query(q, predicate="intersects")
        (party if any(heights[j] >= top - drop for j in hit) else free).append(e)
    return b | {"party": party, "free": free}


def terrace(it, roof, rng, y, b, p_wall=0.95, pots=(6, 14), p_velux=0.15, p_back=0.35):
    """A terrace's roof: London stacks on the party walls and along the fronts of multi-house footprints, else
    one on its own; a roof light or a hatch now and then."""
    b = with_neighbours(it, b)
    placed = wall_stacks(it, roof, rng, b, p_wall, pots, p_back=p_back)
    placed = front_stacks(it, roof, rng, b, placed, pots=pots)
    if not placed:
        lone_stack(it, roof, rng, b, pots)
    if rng.random() < p_velux:
        velux(it, roof, rng, y, int(rng.integers(1, 3)))
    if rng.random() < 0.2:
        roof_hatch(it, roof, rng, y)


def georgian(it, roof, rng, y, b):
    terrace(it, roof, rng, y, b, 0.95, (6, 14), 0.15, 0.4)


def stucco(it, roof, rng, y, b):
    terrace(it, roof, rng, y, b, 0.95, (6, 14), 0.2, 0.4)


def victorian(it, roof, rng, y, b):
    terrace(it, roof, rng, y, b, 0.9, (5, 12), 0.25, 0.25)


def mansion(it, roof, rng, y, b):
    """Mansion blocks: tall stacks with many pots on the party walls and every 6-9 m along the fronts."""
    b = with_neighbours(it, b)
    placed = wall_stacks(it, roof, rng, b, 0.95, (8, 14), (1.8, 2.8), 0.5)
    placed = front_stacks(it, roof, rng, b, placed, (6.0, 9.0), (8, 14), (1.8, 2.8), 150.0)
    if not placed:
        lone_stack(it, roof, rng, b, (8, 14), (1.8, 2.8))
    if rng.random() < 0.45:
        roof_hatch(it, roof, rng, y)
    if not b["shape"] and roof.ok and roof.inner.area >= 200 and rng.random() < 0.4:
        flat_plant(it, roof, rng, y, roof.inner.area, 3)


def warehouse(it, roof, rng, y, b):
    if rng.random() < 0.4:
        if not wall_stacks(it, roof, rng, b, 0.5, (2, 6), (1.0, 2.0), 0.0):
            lone_stack(it, roof, rng, b, (2, 6), (1.0, 2.0))
    if roof.ok:
        if roof.inner.area >= 300 and rng.random() < 0.5:
            overrun(it, roof, rng, y, b["wall"], lift=b["h"] > 18)
        flat_plant(it, roof, rng, y, roof.inner.area, 3)
        vents(it, roof, rng, y, int(rng.integers(0, 3)))
    if rng.random() < 0.4:
        roof_hatch(it, roof, rng, y)


def estate(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.04, 0.03, 0.45)


PROGRAMME = {"georgian": georgian, "stucco": stucco, "victorian": victorian, "mansion": mansion,
             "warehouse": warehouse, "estate": estate, "portland": EW["civic"], "civic": EW["civic"],
             "modern": EW["modern"], "glass": EW["glass"], "factory": EW["factory"],
             "concretepanel": EW["concretepanel"]}
