"""The europe-west preset's rooftop clutter (06c_rooftops): what stands on a roof, per facade style. Paris first
(demos/paris/data/region_research.md §4), London and Berlin to follow.

The roofs of Paris (APUR: 71 % brisis-terrasson mansards, 18 % flat, 10 % pitched; zinc on ~80 %):
  haussmann, faubourg,   chimney stacks ("souches"): rendered or brick, 0.5-0.9 m thick, 0.9-3.5 m long, rising
  brickstone, house      1-2.5 m over the roof, in rows along the party walls ("murs mitoyens") from the street
                         front back, each carrying a row of terracotta pots ("mitrons", some zinc cowls); a few
                         more on the terrasson over the inner walls; a glass stair lantern ("verrière") on some
                         Haussmann terrassons, Velux roof windows and zinc roof hatches. The dormers are the
                         facade shader's (on the brisis).
  hbm                    brick blocks of 1919-39: fewer stacks (boiler flues), a stair box, some roof terrace
  postwar, concretepanel flat roofs: lift overrun and stair box, vents, a boiler flue, some solar rows and green
  modern                 terraces (modern: more of both; Paris's "végétalisation des toits")
  glass (La Défense)     plant enclosures, cooling towers, air handlers, window-cleaning gantries on their track
  civic, factory         civic: a hatch, a lantern, a few vents; factory: skylight strips, ventilators, solar rows
  limestone, monument    nothing (their roofs are the landmark's)
No water tanks, no stair-box hats, no solar water heaters (Shenzhen's and New York's).

Each programme is function(items, roof, rng, y, building): `roof` a Roof (free cells in its own frame; under a
roof shape its flat top only, and roof.ok may be False when that top is too small), `y` the roof's height above
the building's base, `building` a dict with wall (palette index), h, room/top (plant room, flat roofs only), pt
(parapet), shape ("mansard", "pitched" or ""), rise, eaves (height of the eaves: a stack rising from there is
never in the air, whatever the roof's slope under it), party and free (the footprint's party-wall and free
edges, UTM ((E, N), (E, N)) pairs), footprint (UTM polygon, roof shapes only) and roof_ok. Colours are names of the preset's
[rooftops.named] (C), materials and prototypes the viewer's (M, BOX...).
"""
import numpy as np
import shapely
from shapely.geometry import box as rect
from shapely import affinity

from ...common import CFG
from ...stages.rooftops import (BOX, C, CYL, GABLE, M, PANEL, POTS, BLOB, cyl_param, panel_param, pick, south_k,
                                spot, turn)


# ---------------------------------------------------------------- Paris's items

# ([rooftops] stack_cols / pot_cols: [name, weight] pairs of [rooftops.named] colours; Paris's by default)
STACK_COLS = [tuple(x) for x in CFG["rooftops"].get("stack_cols", [("render", 5), ("render2", 4), ("render3", 2), ("brick", 2), ("brick_dark", 1)])]
POT_COLS = [tuple(x) for x in CFG["rooftops"].get("pot_cols", [("pot", 6), ("pot2", 3), ("pot_dark", 2)])]


POT_PITCH = 0.35             # m of stack per pot (a flue each)
# ([rooftops] stack_cap, off by default: stacks end in a flat cover slab (Abdeckplatte: a pot_cols colour, a little
# wider than the stack) instead of a row of pots, and are at most stack_cap_len m long, the flues inside them:
# Berlin's Altbau stacks, short brick or plastered blocks with a concrete or zinc cap, no terracotta pots)
STACK_CAP = bool(CFG["rooftops"].get("stack_cap", False))
STACK_CAP_LEN = float(CFG["rooftops"].get("stack_cap_len", 1.6))


def stack_at(it, rng, E, N, yaw, L, T, y0, top, col=None, pots=True):
    """A chimney stack of L x T metres (L along yaw), from y0 (at or under the roof) to `top`, with a row of pots
    on it, one every POT_PITCH: one item for the stack, one for each row of up to 8 pots (the viewer draws
    `param` pots along it)."""
    col = C[col] if col else C[pick(rng, STACK_COLS)]
    if STACK_CAP:
        L = min(L, STACK_CAP_LEN)
        ct = rng.uniform(0.06, 0.12)
        it.world(BOX, M["chimney"], col, E, N, y0, yaw, L, top - ct - y0, T)
        it.world(BOX, M["zinc"], C[pick(rng, POT_COLS)], E, N, top - ct, yaw, L + 0.1, ct, T + 0.1)
        return
    it.world(BOX, M["chimney"], col, E, N, y0, yaw, L, top - y0, T)
    if pots and L >= 0.5:
        n = int(np.clip(round((L - 0.1) / POT_PITCH), 1, 16))
        d = min(rng.uniform(0.2, 0.28), T - 0.1)
        ph, pc = rng.uniform(0.3, 0.55), C[pick(rng, POT_COLS)]
        rows = [n] if n <= 8 else [(n + 1) // 2, n // 2]
        ux, uy = np.cos(yaw), np.sin(yaw)
        x = -(L - 0.12) / 2
        for k in rows:
            l = (L - 0.12) * k / n
            c = x + l / 2
            it.world(POTS, M["pot"], pc, E + ux * c, N + uy * c, top, yaw, l, ph, d, k)
            x += l


def stack_len(rng, pots):
    """A stack's length for a row of pots drawn from `pots` (a range, both ends included)."""
    return int(rng.integers(pots[0], pots[1] + 1)) * POT_PITCH + 0.15


def party_stacks(it, roof, rng, b, per_wall=(1, 3), p=0.9, above=(1.0, 2.2), ridge=None, pots=(6, 12)):
    """Stacks in rows along the party walls: the stack's long side on the wall line, just inside this roof, from
    the eaves up to `above` over the ridge, as long as its row of pots needs. Only where the roof is flat enough
    to carry them (b["zone"]: the terrasson, a pitched roof's ridge band), never on a slope."""
    fp, zone = b["footprint"], b.get("zone")
    ridge = b["h"] if ridge is None else ridge
    n = 0
    for (x0, y0), (x1, y1) in b["party"]:
        if rng.random() > p:
            continue
        dx, dy = x1 - x0, y1 - y0
        L = float(np.hypot(dx, dy))
        if L < 3:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux                                     # left of the edge; flipped below if outside
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if fp is not None and not fp.contains(shapely.Point(mx + nx * 0.5, my + ny * 0.5)):
            nx, ny = -nx, -ny
        # a wall shared by two roofs: built on from one side (the one it faces into, roughly east-north-east),
        # now and then from both (stacks back to back)
        if nx * 0.94 + ny * 0.34 < 0 and rng.random() < 0.8:
            continue
        T = rng.uniform(0.55, 0.85)
        off = T / 2 + 0.03
        # the stretch of the wall line (just inside it) over the flat top
        line = shapely.LineString([(x0 + nx * off, y0 + ny * off), (x1 + nx * off, y1 + ny * off)])
        try:
            pieces = line.intersection(zone) if zone is not None else line
        except shapely.errors.GEOSException:
            continue
        pieces = [g for g in getattr(pieces, "geoms", [pieces]) if g.geom_type == "LineString" and g.length > 1.0]
        if not pieces:
            continue
        k = int(rng.integers(per_wall[0], per_wall[1] + 1))
        placed = []
        for _ in range(k * 3):
            if len(placed) >= k:
                break
            g = pieces[int(rng.integers(len(pieces)))]
            SL = min(stack_len(rng, pots), g.length - 0.1)
            if SL < 1.0:
                continue
            s0 = rng.uniform(SL / 2, g.length - SL / 2) if g.length > SL else g.length / 2
            if any(abs(s0 - q) < (SL + w) / 2 + 0.6 for q, w, gg in placed if gg is g):
                continue
            c = g.interpolate(s0)
            cx, cy = c.x, c.y
            if fp is not None:
                foot = affinity.rotate(rect(-SL / 2, -T / 2, SL / 2, T / 2), np.degrees(np.arctan2(uy, ux)),
                                       origin=(0, 0))
                foot = affinity.translate(foot, cx, cy)
                if not fp.buffer(0.05).contains(foot):
                    continue
            placed.append((s0, SL, g))
            top = ridge + rng.uniform(*above)
            stack_at(it, rng, cx, cy, float(np.arctan2(uy, ux)), SL, T, b["eaves"], top)
            if roof.ok:
                la = roof.to_local(shapely.Point(cx, cy))
                roof.take(la.x, la.y, SL + 0.4, SL + 0.4, 0.2)
            n += 1
    return n


def front_stacks(it, roof, rng, b, every=(12, 20), above=(1.0, 2.2), pots=(3, 8)):
    """Stacks at right angles to the street walls every `every` metres: the party walls inside a footprint that
    stands for several houses (the block's buildings are often one outline), rising
    from the break of the slope across the terrasson, as along any Paris street (never on the slope)."""
    fp, zone = b["footprint"], b.get("zone")
    if fp is None:
        return 0
    n, placed = 0, []
    for (x0, y0), (x1, y1) in b["free"]:
        dx, dy = x1 - x0, y1 - y0
        L = float(np.hypot(dx, dy))
        if L < 6:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        if not fp.contains(shapely.Point((x0 + x1) / 2 + nx * 0.5, (y0 + y1) / 2 + ny * 0.5)):
            nx, ny = -nx, -ny
        t = rng.uniform(0.3, 1.0) * rng.uniform(*every)
        while t < L - 2:
            SL, T = stack_len(rng, pots), rng.uniform(0.5, 0.8)
            d = b.get("roof_d", 0.0) + rng.uniform(0.05, 0.5) + SL / 2   # from the break of the slope inwards
            cx, cy = x0 + ux * t + nx * d, y0 + uy * t + ny * d
            t += rng.uniform(*every)
            if any((cx - px) ** 2 + (cy - py) ** 2 < 9 for px, py in placed):
                continue
            yaw = float(np.arctan2(ny, nx))                          # its long side into the building
            foot = affinity.translate(affinity.rotate(rect(-SL / 2, -T / 2, SL / 2, T / 2), np.degrees(yaw),
                                                      origin=(0, 0)), cx, cy)
            if not fp.buffer(-0.05).contains(foot) or (zone is not None and not zone.buffer(0.01).contains(foot)):
                continue
            stack_at(it, rng, cx, cy, yaw, SL, T, b["eaves"], b["h"] + rng.uniform(*above))
            placed.append((cx, cy))
            if roof.ok:
                la = roof.to_local(shapely.Point(cx, cy))
                roof.take(la.x, la.y, SL + 0.4, SL + 0.4, 0.2)
            n += 1
    return n


def free_stacks(it, roof, rng, y, b, n, above=(0.9, 1.9), prefer="random"):
    """Stacks standing on the flat top (the terrasson: flues of the inner walls), their long side along the roof."""
    if not roof.ok:
        return
    for _ in range(n):
        SL, T = rng.uniform(0.8, 2.2), rng.uniform(0.5, 0.8)
        k = int(rng.integers(2))
        p = spot(roof, rng, SL, T, prefer, k, 0.3)
        if p is None:
            return
        E, N = roof.to_world(*p)
        stack_at(it, rng, E, N, roof.theta + k * np.pi / 2, SL, T, b["eaves"], y + rng.uniform(*above))


def velux(it, roof, rng, y, n):
    """Roof windows on the terrasson: a dark glazed sash in a zinc frame, flush with the roof."""
    if not roof.ok:
        return
    for _ in range(n):
        w, l = pick(rng, [((0.78, 0.98), 3), ((0.66, 1.18), 2), ((1.14, 1.18), 1), ((0.55, 0.78), 2)])
        k = int(rng.integers(2))
        p = spot(roof, rng, w, l, "random", k, 0.4)
        if p is None:
            return
        it.put(roof, BOX, M["velux"], C["velux"], *p, k, y, w, 0.12, l)


def roof_hatch(it, roof, rng, y):
    if not roof.ok:
        return
    k = int(rng.integers(2))
    p = spot(roof, rng, 0.9, 1.1, "random", k, 0.3)
    if p is not None:
        it.put(roof, BOX, M["zinc"], C[pick(rng, [("zinc", 2), ("zinc_dark", 1)])], *p, k, y, 0.9, 0.45, 1.1)


def lantern(it, roof, rng, y):
    """A glass stair lantern (verrière) over the stairwell: a glazed ridge on a low zinc upstand."""
    if not roof.ok:
        return
    sx, sz = rng.uniform(2.0, 3.6), rng.uniform(1.6, 2.6)
    k = int(rng.integers(2))
    p = spot(roof, rng, sx, sz, "center", k, 0.5)
    if p is None:
        return
    it.put(roof, BOX, M["zinc"], C["zinc_dark"], *p, k, y, sx, 0.35, sz)
    it.put(roof, GABLE, M["skylight"], C["glass"], *p, k, y + 0.35, sx, min(0.4 * sz, 1.1), sz)


def vents(it, roof, rng, y, n, h=(0.5, 1.2)):
    """Ventilation stubs and cowls: small steel cylinders."""
    if not roof.ok:
        return
    for _ in range(n):
        d = rng.uniform(0.3, 0.6)
        p = spot(roof, rng, d, d, "random", 0, 0.3)
        if p is None:
            return
        it.put(roof, CYL, M["stainless"], C[pick(rng, [("stainless2", 2), ("steel", 1)])], *p, 0, y, d,
               rng.uniform(*h), d)


def flue(it, roof, rng, y, h=(2.0, 4.5)):
    """A boiler flue: a steel pipe standing on its own."""
    if not roof.ok:
        return
    d = rng.uniform(0.35, 0.6)
    p = spot(roof, rng, d, d, "edge", 0, 0.3)
    if p is not None:
        it.put(roof, CYL, M["stainless"], C["stainless2"], *p, 0, y, d, rng.uniform(*h), d)


def overrun(it, roof, rng, y, wall, lift=True):
    """The lift overrun and stair box of a flat roof, rendered like the facade or in grey concrete."""
    if not roof.ok:
        return None
    sx, sz = rng.uniform(2.4, 3.6), rng.uniform(3.0, 5.0)
    if lift:
        sx += 1.2
    k = int(rng.integers(4))
    p = spot(roof, rng, sx, sz, pick(rng, [("center", 2), ("edge", 2), ("corner", 1)]), k, 0.3)
    if p is None:
        return None
    col = wall if rng.random() < 0.5 else C[pick(rng, [("concrete_light", 2), ("concrete", 1)])]
    it.put(roof, BOX, M["stair"], col, *p, k, y, sx, rng.uniform(2.6, 3.4) + (0.8 if lift else 0), sz)
    return p


def green_roof(it, roof, rng, y, share=(0.4, 0.8)):
    """A planted terrace over much of a flat roof: sedum and grasses in a low bed, a few shrubs."""
    if not roof.ok:
        return False
    x0, y0, x1, y1 = roof.inner.bounds
    for f in np.linspace(share[1], share[0], 4):
        ea, eb = (x1 - x0) * np.sqrt(f), (y1 - y0) * np.sqrt(f)
        if ea < 3 or eb < 3:
            return False
        p = spot(roof, rng, ea, eb, "center", 0, 0.5)
        if p is not None:
            it.put(roof, BOX, M["green"], C[pick(rng, [("green", 2), ("green2", 1)])], *p, 0, y, ea, 0.3, eb)
            for _ in range(int(rng.integers(0, 4))):
                d = min(rng.uniform(0.8, 1.8), 0.4 * eb)
                a, b = rng.uniform(-ea / 2 + d, ea / 2 - d), rng.uniform(-eb / 2 + d / 2, eb / 2 - d / 2)
                it.put(roof, BLOB, M["foliage"], C[pick(rng, [("foliage", 1), ("foliage2", 1)])], p[0] + a,
                       p[1] + b, 0, y + 0.3, d * 1.5, d * 0.9, d)
            return True
    return False


def ac_units(it, roof, rng, y, n):
    if not roof.ok:
        return
    for _ in range(n):
        k = int(rng.integers(4))
        p = spot(roof, rng, 0.85, 0.35, "edge", k, 0.15)
        if p is None:
            return
        it.put(roof, BOX, M["hvac"], C["hvac"], *p, k, y, 0.85, 0.6, 0.35)


def hvac_cluster(it, roof, rng, y, rows, cols, unit=(2.4, 1.5, 1.4), gap=0.3):
    """A block of rooftop air handlers in rows."""
    if not roof.ok:
        return
    ux, uh, uz = unit[0] * rng.uniform(0.85, 1.15), unit[1] * rng.uniform(0.85, 1.15), unit[2] * rng.uniform(0.85, 1.2)
    k = int(rng.integers(2))
    while rows and cols:
        W, D = cols * ux + (cols - 1) * gap, rows * uz + (rows - 1) * gap
        p = spot(roof, rng, W, D, "random", k, 0.8)
        if p is not None:
            break
        rows, cols = (rows - 1, cols) if rows >= cols else (rows, cols - 1)
    if not rows or not cols:
        return
    col = C[pick(rng, [("hvac", 3), ("hvac2", 2), ("hvac3", 1)])]
    for r in range(rows):
        a, b = turn(k, 0, (r - (rows - 1) / 2) * (uz + gap))
        it.put(roof, BOX, M["hvac"], col, p[0] + a, p[1] + b, k, y, cols * ux + (cols - 1) * gap, uh, uz, cols)


def cooling_towers(it, roof, rng, y, n):
    """A row of square cooling-tower cells with a fan each (one item: param = cells)."""
    if not roof.ok:
        return
    s, h = rng.uniform(3.0, 4.0), rng.uniform(3.2, 4.2)
    k = int(rng.integers(2))
    while n:
        p = spot(roof, rng, n * s, s, "edge", k, 0.8)
        if p is not None:
            break
        n -= 1
    if n:
        col = C[pick(rng, [("cooling", 2), ("cooling2", 2), ("hvac2", 1)])]
        it.put(roof, BOX, M["cooling"], col, *p, k, y, n * s, h, s, n)


def plant_box(it, roof, rng, y, size=((8, 16), (5, 10), (3.2, 4.5))):
    """A plant enclosure: a big box with louvred walls (param 1)."""
    if not roof.ok:
        return
    sx, sz, h = (rng.uniform(*r) for r in size)
    k = int(rng.integers(2))
    p = spot(roof, rng, sx, sz, "random", k, 1.0)
    if p is None:
        return
    col = C[pick(rng, [("concrete_light", 2), ("hvac2", 2), ("concrete", 1)])]
    it.put(roof, BOX, M["concrete"], col, *p, k, y, sx, h, sz, 1)


def pv_rows(it, roof, rng, y, share=0.6, tilt_rise=0.35, depth=2.1, gap=0.6, max_blocks=1):
    """Solar panel rows facing south over the largest free part of the roof. Returns the number of rows."""
    if not roof.ok:
        return 0
    k = south_k(roof)
    rows = 0
    x0, y0, x1, y1 = roof.inner.bounds
    for _ in range(max_blocks):
        for f in np.linspace(share, 0.2, 5):
            ea, eb = (x1 - x0) * np.sqrt(f), (y1 - y0) * np.sqrt(f)
            sx, sz = (ea, eb) if k % 2 == 0 else (eb, ea)
            if sx < 4 or sz < depth:
                return rows
            p = spot(roof, rng, sx, sz, "center" if not rows else "random", k, 0.8)
            if p is None:
                continue
            n = max(1, int((sz + gap) // (depth + gap)))
            for r in range(n):
                a, b = turn(k, 0, (r - (n - 1) / 2) * (depth + gap))
                it.put(roof, PANEL, M["pv"], C["pv"], p[0] + a, p[1] + b, k, y, sx - 0.3, tilt_rise + 0.25, depth,
                       panel_param(0.25 / (tilt_rise + 0.25)))
                rows += 1
            break
    return rows


def bmu(it, roof, rng, y, poly_local, pt):
    """A window-cleaning gantry parked on its track, which runs round the roof inside the parapet."""
    if not roof.ok:
        return
    ring = poly_local.buffer(-(pt + 1.2), join_style="mitre")
    if ring.is_empty or ring.geom_type != "Polygon" or ring.area < 80:
        return
    ring = ring.simplify(0.5)
    c = np.asarray(ring.exterior.coords)
    for (a0, b0), (a1, b1) in zip(c[:-1], c[1:]):
        L = np.hypot(a1 - a0, b1 - b0)
        if L < 0.5:
            continue
        E, N = roof.to_world((a0 + a1) / 2, (b0 + b1) / 2)
        it.world(BOX, M["steel"], C["steel_dark"], E, N, y, roof.theta + np.arctan2(b1 - b0, a1 - a0), L + 0.3, 0.25, 0.4)
    roof.block(ring.exterior.buffer(0.6))
    a0, b0 = c[0]
    a1, b1 = c[1]
    L = np.hypot(a1 - a0, b1 - b0)
    if L < 6:
        return
    ang = np.arctan2(b1 - b0, a1 - a0)
    ma, mb = a0 + (a1 - a0) * 0.5, b0 + (b1 - b0) * 0.5
    E, N = roof.to_world(ma, mb)
    col = C[pick(rng, [("steel_white", 3), ("steel", 1)])]
    it.world(BOX, M["hvac"], col, E, N, y + 0.25, roof.theta + ang, 3.2, 2.4, 2.2)
    jl = min(rng.uniform(7, 11), L - 1)
    E, N = roof.to_world(ma + np.cos(ang) * (jl / 2 - 1), mb + np.sin(ang) * (jl / 2 - 1))
    it.world(BOX, M["steel"], col, E, N, y + 2.65, roof.theta + ang, jl, 0.45, 0.5)
    roof.take(ma, mb, 4, 4, 0.5)


def skylight_strips(it, roof, rng, y):
    """Rows of ribbed translucent roof lights along a shed's roof (param 1)."""
    if not roof.ok:
        return
    x0, y0, x1, y1 = roof.inner.bounds
    step, w = rng.uniform(6, 9), rng.uniform(0.9, 1.4)
    for a in np.arange(x0 + step / 2, x1 - 1, step):
        L = (y1 - y0) * rng.uniform(0.5, 0.85)
        p = roof.find(w, L, "near", rng, (a, (y0 + y1) / 2))
        if p is None or abs(p[0] - a) > 1.5:
            continue
        roof.take(p[0], p[1], w, L, 0.2)
        it.put(roof, BOX, M["skylight"], C["glass"], *p, 0, y, w, 0.2, L, 1)


# ---------------------------------------------------------------- roof programmes per facade style

def old_roof(it, roof, rng, y, b, stacks=(1, 3), p_wall=0.9, p_lantern=0.3, p_velux=0.45, n_free=(0, 2),
             above=(1.0, 2.3), every=(12, 20), pots=(5, 12)):
    """Mansards and pitched roofs of the old city (and their flat-roofed exceptions): stacks in rows along the
    party walls and on the top, a stair lantern, Velux windows, a hatch."""
    if b["shape"]:
        n = party_stacks(it, roof, rng, b, stacks, p_wall, above, pots=pots)
        if every:
            n += front_stacks(it, roof, rng, b, every, above, (3, max(4, pots[1] // 2)))
        extra = int(rng.integers(*n_free)) if n_free[1] > n_free[0] else n_free[0]
        if n == 0:                                       # free-standing: stacks along the top's edges
            extra = max(extra, int(rng.integers(2, 4)))
        free_stacks(it, roof, rng, y, b, extra, above, "edge" if n == 0 else "random")
    else:                                                # a flat roof on an old building: stacks on its edge
        if roof.ok:
            free_stacks(it, roof, rng, y, b | {"eaves": y}, int(rng.integers(1, 4)), (1.0, 1.8), "edge")
    if rng.random() < p_lantern and roof.ok and roof.inner.area > 25:
        lantern(it, roof, rng, y)
    if rng.random() < p_velux:
        velux(it, roof, rng, y, int(rng.integers(1, 4)))
    if rng.random() < 0.45:
        roof_hatch(it, roof, rng, y)
    if not b["shape"] and rng.random() < 0.25:
        ac_units(it, roof, rng, y, int(rng.integers(1, 3)))


def haussmann(it, roof, rng, y, b):
    """Stacks twice as thick on the ground as on older houses (a flue per room, 6-15 pots on a party wall)."""
    old_roof(it, roof, rng, y, b, (2, 4), 0.95, 0.3, 0.45, (1, 4), (1.0, 2.3), (7, 11), (6, 15))


def faubourg(it, roof, rng, y, b):
    old_roof(it, roof, rng, y, b, (1, 2), 0.8, 0.08, 0.35, (0, 2), (0.9, 1.9), (9, 15), (4, 10))


def house(it, roof, rng, y, b):
    old_roof(it, roof, rng, y, b, (1, 1), 0.7, 0.0, 0.3, (0, 2), (0.8, 1.6), (10, 16), (2, 6))


def brickstone(it, roof, rng, y, b):
    """Louis XIII brick and stone (Place des Vosges, Dauphine): tall brick stacks on steep slate roofs."""
    old_roof(it, roof, rng, y, b, (1, 3), 0.95, 0.0, 0.1, (1, 3), (1.6, 2.8), (8, 12), (4, 10))


def hbm(it, roof, rng, y, b):
    """Interwar social housing: a few boiler stacks, a stair box on the flat ones, some terrace planting."""
    if b["shape"]:
        old_roof(it, roof, rng, y, b, (1, 1), 0.5, 0.0, 0.15, (0, 1), (0.9, 1.8), (18, 30))
        return
    overrun(it, roof, rng, y, b["wall"], lift=b["h"] > 20 and rng.random() < 0.5)
    free_stacks(it, roof, rng, y, b | {"eaves": y}, int(rng.integers(1, 3)), (1.2, 2.2), "edge")
    flat_plant(it, roof, rng, y, roof.inner.area if roof.ok else 0, 4)
    vents(it, roof, rng, y, int(rng.integers(1, 4)))
    if rng.random() < 0.3:
        roof_hatch(it, roof, rng, y)
    if rng.random() < 0.15:
        green_roof(it, roof, rng, y, (0.2, 0.4))


def flat_plant(it, roof, rng, y, area, most=6):
    """Plant on a flat roof: 2-`most` boxes (air handlers, louvred enclosures, condensers) over ~150 m2, one or
    none on smaller roofs."""
    n = int(np.clip(round(area / 180 * rng.uniform(0.8, 1.3)), 2, most)) if area >= 150 else \
        int(rng.integers(0, 2)) if area >= 50 else 0
    for _ in range(n):
        r = rng.random()
        if r < 0.4:
            hvac_cluster(it, roof, rng, y, 1, int(rng.integers(1, 4)))
        elif r < 0.65:
            plant_box(it, roof, rng, y, ((2.2, 5.0), (1.6, 3.0), (1.4, 2.4)))
        elif r < 0.85:
            ac_units(it, roof, rng, y, int(rng.integers(2, 5)))
        else:
            hvac_cluster(it, roof, rng, y, 1, 1, unit=(1.2, 1.0, 0.9))


def flat_block(it, roof, rng, y, b, p_pv=0.08, p_green=0.08, p_flue=0.35):
    """Post-war and modern blocks: a lift housing (and a stair box on big roofs), 2-6 plant boxes (air handlers,
    condensers, small louvred enclosures), vents, a boiler flue, and on some solar rows or a green terrace.
    Under a roof shape (a modern zinc attic) the old roofs' Velux and hatch."""
    if b["shape"]:
        old_roof(it, roof, rng, y, b, (0, 1), 0.3, 0.0, 0.4, (0, 1), (0.8, 1.4), None, (2, 6))
        return
    area = roof.inner.area if roof.ok else 0
    # the terrace or the solar rows first: they need the roof's open middle
    r = rng.random()
    if area >= 120 and r < p_green:
        green_roof(it, roof, rng, y, (0.3, 0.6))
    elif area >= 150 and r < p_green + p_pv:
        pv_rows(it, roof, rng, y, 0.5)
    top = b["top"]
    if top is not None:                                  # the plant room is the lift machine room: kit on it
        vents(it, top, rng, top.y, int(rng.integers(0, 3)))
        if rng.random() < 0.4:
            hvac_cluster(it, top, rng, top.y, 1, int(rng.integers(1, 3)))
        if area >= 250 and rng.random() < 0.6:
            overrun(it, roof, rng, y, b["wall"], lift=False)
    elif area >= 60:
        overrun(it, roof, rng, y, b["wall"], lift=b["h"] > 12 or area >= 150)
    if area >= 400 and rng.random() < 0.5:
        overrun(it, roof, rng, y, b["wall"], lift=False)
    flat_plant(it, roof, rng, y, area)
    if rng.random() < p_flue:
        flue(it, roof, rng, y)
    vents(it, roof, rng, y, int(rng.integers(2, 4 + min(int(area // 150), 5))))
    if rng.random() < 0.3:
        roof_hatch(it, roof, rng, y)


def postwar(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.06, 0.06, 0.4)


def concretepanel(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.05, 0.03, 0.3)
    if b["h"] >= 50 and roof.ok and rng.random() < 0.5:
        bmu(it, roof, rng, y, roof.local, b["pt"])


def modern(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.12, 0.2, 0.15)


def glass(it, roof, rng, y, b):
    """Office towers (La Défense, Front de Seine, Montparnasse): plant enclosures, cooling towers, air handlers,
    a window-cleaning gantry on the tall ones."""
    if b["shape"] or not roof.ok:
        return
    if b["h"] >= 50 and rng.random() < 0.7:
        bmu(it, roof, rng, y, roof.local, b["pt"])
    area = roof.inner.area
    if area >= 250 and rng.random() < 0.8:
        cooling_towers(it, roof, rng, y, int(rng.integers(2, 6)))
    if area >= 150:
        for _ in range(int(np.clip(area / 500, 1, 4))):
            hvac_cluster(it, roof, rng, y, int(rng.integers(1, 3)), int(rng.integers(2, 5)))
    if area >= 900:
        plant_box(it, roof, rng, y)
    top = b["top"]
    if top is not None and rng.random() < 0.5:
        hvac_cluster(it, top, rng, top.y, 1, int(rng.integers(2, 4)))
    vents(it, roof, rng, y, int(rng.integers(0, 4)))


def civic(it, roof, rng, y, b):
    """Schools, ministries, hospitals, stations: a hatch, a lantern, a few vents or units; flat ones some plant."""
    if b["shape"]:
        old_roof(it, roof, rng, y, b, (0, 1), 0.3, 0.15, 0.2, (0, 1), (0.8, 1.5), None)
        return
    if not roof.ok:
        return
    area = roof.inner.area
    if area >= 150:
        overrun(it, roof, rng, y, b["wall"], lift=b["h"] > 12)
    flat_plant(it, roof, rng, y, area)
    vents(it, roof, rng, y, int(rng.integers(2, 5)))
    if area >= 300:
        hvac_cluster(it, roof, rng, y, 1, int(rng.integers(2, 4)))
    if area >= 800 and rng.random() < 0.3:
        plant_box(it, roof, rng, y, ((5, 10), (4, 7), (2.8, 3.6)))
    if rng.random() < 0.3:
        roof_hatch(it, roof, rng, y)
    if area >= 200 and rng.random() < 0.1:
        green_roof(it, roof, rng, y, (0.3, 0.6))


def factory(it, roof, rng, y, b):
    """Workshops, depots and big halls: skylight strips or solar rows, ventilators."""
    if b["shape"] or not roof.ok:
        return
    area = roof.inner.area
    r = rng.random()
    if area >= 300 and r < 0.4:
        skylight_strips(it, roof, rng, y)
    elif area >= 300 and r < 0.55:
        pv_rows(it, roof, rng, y, 0.7, 0.2, max_blocks=2)
    if area >= 200 and rng.random() < 0.6:
        x0, y0, x1, y1 = roof.inner.bounds
        d = rng.uniform(0.6, 0.8)
        for a in np.arange(x0 + 3, x1 - 1, rng.uniform(5, 8)):
            p = roof.find(d, d, "near", rng, (a, (y0 + y1) / 2))
            if p is not None and abs(p[0] - a) < 1 and abs(p[1] - (y0 + y1) / 2) < 2:
                roof.take(p[0], p[1], d, d, 0.2)
                it.put(roof, CYL, M["turbine"], C["stainless"], *p, 0, y, d, d * 1.1, d)
    if rng.random() < 0.3:
        hvac_cluster(it, roof, rng, y, 1, int(rng.integers(1, 4)))


PROGRAMME = {"haussmann": haussmann, "faubourg": faubourg, "house": house, "brickstone": brickstone, "hbm": hbm,
             "postwar": postwar, "concretepanel": concretepanel, "modern": modern, "glass": glass, "civic": civic,
             "factory": factory}
# (limestone and monument roofs are the landmarks' and the classical ensembles': nothing on them; nor on sheds,
# plant rooms, spires, statues and the landmark styles)
