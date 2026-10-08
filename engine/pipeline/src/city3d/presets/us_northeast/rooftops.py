"""The us-northeast preset's rooftop clutter (06c_rooftops): what stands on a roof, per facade style. The items
are those of the china-south preset (whose code this started from) plus New York's own: wooden water tanks on
steel stands with conical roofs, brick stair and elevator bulkheads, chimneys, roof hatches and skylights.

(china-south's notes follow.)
The china-south preset's rooftop clutter (06c_rooftops): what stands on a roof, per facade style.

The items and the roof programmes of western Shenzhen, invented but following what the kind of building
usually carries (see stages/rooftops.py for the full list): urban villages with stair boxes, stainless and
blue plastic water tanks, solar water heaters and blue lean-to sheds; residential towers with stair and lift
boxes, panel tanks and helipad markings; offices with cooling towers, air handlers and window-cleaning
cranes; malls and podiums with rows of rooftop units; factories with ventilators, skylights and solar panels.

Each programme is function(items, roof, rng, y, building): `roof` a Roof (free cells in its own frame),
`y` its height above the building's base, `building` a dict with wall (palette index), h, room (the plant
room or None), top (a Roof on the plant room or None) and pt (parapet thickness). Colours are names of the
preset's [rooftops.named] (C), materials and prototypes the viewer's (M, BOX...).
"""
import numpy as np

from ...stages.rooftops import (BLOB, BOX, C, CONE, CYL, GABLE, M, PANEL, cyl_param, panel_param, pick, south_k,
                                spot, turn)


# ---------------------------------------------------------------- items

def tank(it, roof, rng, y, prefer="edge", kind=None, target=None):
    """A water tank: stainless on a steel stand, blue or white plastic, or a stainless one lying on saddles."""
    kind = kind or pick(rng, [("steel", 5), ("blue", 3), ("white", 1), ("lying", 1)])
    if kind == "lying":
        L, d = rng.uniform(1.8, 2.5), rng.uniform(0.9, 1.15)
        k = int(rng.integers(2))
        p = spot(roof, rng, L, d + 0.2, prefer, k, 0.3, target)
        if p is None:
            return False
        stand = 0.4
        it.put(roof, CYL, M["stainless"], C[pick(rng, [("stainless", 2), ("stainless2", 1)])], *p, k,
               y, L, d + stand, d, cyl_param(True, stand))
        return True
    d = rng.uniform(0.95, 1.35) if kind != "blue" else rng.uniform(1.0, 1.45)
    hgt = rng.uniform(1.15, 1.7)
    p = spot(roof, rng, d, d, prefer, 0, 0.3, target)
    if p is None:
        return False
    k = int(rng.integers(4))
    if kind == "steel":
        stand = rng.uniform(0.3, 0.6)
        it.put(roof, CYL, M["stainless"], C[pick(rng, [("stainless", 2), ("stainless2", 1)])], *p, k,
               y, d, hgt + stand, d, cyl_param(False, stand))
    else:
        col = C[pick(rng, [("tank_blue", 3), ("tank_blue2", 2)])] if kind == "blue" else C["tank_white"]
        it.put(roof, CYL, M["plastic"], col, *p, k, y, d, hgt, d)
    return True


def stair_box(it, roof, rng, y, wall, size=(2.4, 3.3, 3.6, 5.0), hgt=(2.6, 3.0), prefer="corner", hats=0.3):
    """The stair-access box (and on some a small tiled hat or tanks on top). Returns its top or None."""
    sx, sz = rng.uniform(*size[:2]), rng.uniform(*size[2:])
    k = int(rng.integers(4))
    p = spot(roof, rng, sx, sz, prefer, k, 0.25)
    if p is None:
        sx, sz = sx * 0.75, sz * 0.75
        p = spot(roof, rng, sx, sz, prefer, k, 0.2)
        if p is None:
            return None
    h = rng.uniform(*hgt)
    col = wall if rng.random() < 0.6 else C[pick(rng, [("concrete_light", 2), ("white_tile", 2), ("concrete", 1)])]
    it.put(roof, BOX, M["stair"], col, *p, k, y, sx, h, sz)
    r = rng.random()
    if r < hats:
        tile = C[pick(rng, [("tile_red", 3), ("tile_orange", 2), ("tile_green", 2), ("tile_grey", 2),
                            ("tile_blue", 1), ("tile_yellow", 1)])]
        it.put(roof, GABLE, M["tile"], tile, *p, k, y + h, sx + 0.5, rng.uniform(0.9, 1.4), sz + 0.5)
    elif r < hats + 0.35:
        # one or two tanks on the box: common in the villages, out of the way of the roof
        n = 1 + int(rng.random() < 0.4 and sz > 3.4)
        for j in range(n):
            d = rng.uniform(0.9, min(1.3, sx - 0.4))
            off = (j - (n - 1) / 2) * (d + 0.3)
            a, b = turn(k, 0, off)
            blue = rng.random() < 0.35
            it.put(roof, CYL, M["plastic" if blue else "stainless"],
                   C["tank_blue"] if blue else C["stainless"], p[0] + a, p[1] + b, k, y + h, d,
                   rng.uniform(1.1, 1.5), d)
    return p


def heaters(it, roof, rng, y, n_max=3):
    """A row of solar water heaters facing south: a tilted rack of evacuated tubes, the tank along its top."""
    k = south_k(roof)
    n = int(rng.integers(1, n_max + 1))
    w, depth, rise = rng.uniform(1.8, 2.2), rng.uniform(1.4, 1.7), rng.uniform(1.1, 1.35)
    while n:
        p = spot(roof, rng, n * w + (n - 1) * 0.15, depth + 0.3, "edge", k, 0.3)
        if p is not None:
            break
        n -= 1
    if not n:
        return 0
    # the whole row is one item: the viewer splits it into units about 2 m wide
    a, b = turn(k, 0, 0.15)
    it.put(roof, PANEL, M["tubes"], C["tubes"], p[0] + a, p[1] + b, k, y, n * w + (n - 1) * 0.15, rise, depth,
           panel_param(0.25, True))
    return n


def shed(it, roof, rng, y, share=(0.3, 0.6), hgt=(2.3, 2.9), cols=None):
    """A lean-to of corrugated steel over part of the roof (blue, now and then white, grey or red)."""
    x0, y0, x1, y1 = roof.inner.bounds
    col = C[pick(rng, cols or [("shed_blue", 5), ("shed_blue2", 3), ("shed_cyan", 2), ("shed_white", 1),
                               ("shed_grey", 1), ("shed_red", 1), ("shed_green", 1)])]
    k = int(rng.integers(4))
    for f in np.linspace(share[1], share[0], 4):
        ea, eb = (x1 - x0) * np.sqrt(f) * rng.uniform(0.9, 1.1), (y1 - y0) * np.sqrt(f) * rng.uniform(0.9, 1.1)
        if ea < 2.5 or eb < 2.5:
            return False
        sx, sz = (ea, eb) if k % 2 == 0 else (eb, ea)
        p = spot(roof, rng, sx, sz, "edge", k, 0.1)
        if p is not None:
            lo, hi = rng.uniform(hgt[0], hgt[1] - 0.3), hgt[1]
            it.put(roof, PANEL, M["corrugated"], col, *p, k, y, sx, hi, sz, panel_param(lo / hi))
            return True
    return False


def plants(it, roof, rng, y, n):
    """Potted plants and shrubs along the parapet, in clumps of three (one blob prototype each)."""
    for _ in range(max(1, n // 3)):
        d = rng.uniform(0.6, 1.2)
        L = d * rng.uniform(2.2, 3.2)
        k = int(rng.integers(4))
        p = spot(roof, rng, L, d, "edge", k, 0.1)
        if p is None:
            return
        col = C[pick(rng, [("foliage", 3), ("foliage2", 3), ("foliage3", 2), ("foliage4", 1)])]
        it.put(roof, BLOB, M["foliage"], col, *p, k, y, L, d * rng.uniform(0.7, 1.1), d)


def ac_units(it, roof, rng, y, n):
    for _ in range(n):
        k = int(rng.integers(4))
        p = spot(roof, rng, 0.85, 0.35, "edge", k, 0.15)
        if p is None:
            return
        it.put(roof, BOX, M["hvac"], C["hvac"], *p, k, y, 0.85, 0.6, 0.35)


def hvac_cluster(it, roof, rng, y, rows, cols, unit=(2.4, 1.5, 1.4), gap=0.3):
    """A block of rooftop air handlers in rows."""
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
        # one row of units side by side is one item; the viewer draws the joints (param: units in the row)
        a, b = turn(k, 0, (r - (rows - 1) / 2) * (uz + gap))
        it.put(roof, BOX, M["hvac"], col, p[0] + a, p[1] + b, k, y, cols * ux + (cols - 1) * gap, uh, uz, cols)


def cooling_towers(it, roof, rng, y, n):
    """A row of cooling towers: square cells with a fan on top, or round ones."""
    if rng.random() < 0.3:
        d, h = rng.uniform(3.4, 4.6), rng.uniform(3.0, 4.2)
        k = int(rng.integers(2))
        while n:
            p = spot(roof, rng, n * d + (n - 1) * 0.8, d, "edge", k, 0.8)
            if p is not None:
                break
            n -= 1
        for j in range(n):
            a, b = turn(k, (j - (n - 1) / 2) * (d + 0.8), 0)
            it.put(roof, CYL, M["cooling"], C[pick(rng, [("cooling_blue", 2), ("cooling", 1), ("cooling2", 1)])],
                   p[0] + a, p[1] + b, k, y, d, h, d)
        return
    s, h = rng.uniform(3.0, 4.0), rng.uniform(3.2, 4.2)
    k = int(rng.integers(2))
    while n:
        p = spot(roof, rng, n * s, s, "edge", k, 0.8)
        if p is not None:
            break
        n -= 1
    if n:                             # one item, the viewer draws a fan per cell (param: cells)
        col = C[pick(rng, [("cooling", 2), ("cooling2", 2), ("hvac2", 1)])]
        it.put(roof, BOX, M["cooling"], col, *p, k, y, n * s, h, s, n)


def plant_box(it, roof, rng, y):
    """A plant enclosure: a big box with louvred walls (param 1)."""
    sx, sz, h = rng.uniform(8, 16), rng.uniform(5, 10), rng.uniform(3.2, 4.5)
    k = int(rng.integers(2))
    p = spot(roof, rng, sx, sz, "random", k, 1.0)
    if p is None:
        return
    col = C[pick(rng, [("concrete_light", 2), ("hvac2", 2), ("concrete", 1)])]
    it.put(roof, BOX, M["concrete"], col, *p, k, y, sx, h, sz, 1)


def ducts(it, roof, rng, y, n):
    """Runs of sheet-metal ductwork across the roof on low supports."""
    for _ in range(n):
        L, w = rng.uniform(8, 30), rng.uniform(0.6, 1.2)
        k = int(rng.integers(2))
        p = spot(roof, rng, L, w, "random", k, 0.4)
        if p is None:
            continue
        it.put(roof, BOX, M["steel"], C[pick(rng, [("stainless2", 2), ("steel", 1)])], *p, k, y + 0.3, L, w, w)


def panel_tank(it, roof, rng, y, prefer="edge"):
    """A sectional (1 m panel) water tank: stainless, beige or blue fibreglass."""
    sx, sz, h = float(rng.integers(3, 7)), float(rng.integers(2, 4)), float(rng.integers(2, 4))
    k = int(rng.integers(2))
    p = spot(roof, rng, sx, sz, prefer, k, 0.6)
    if p is None:
        return False
    col = C[pick(rng, [("tank_beige", 3), ("stainless2", 2), ("tank_blue", 1), ("tank_green", 1)])]
    it.put(roof, BOX, M["steel"], C["steel_dark"], *p, k, y, sx + 0.2, 0.5, sz + 0.2)
    it.put(roof, BOX, M["paneltank"], col, *p, k, y + 0.5, sx, h, sz)
    return True


def pv_rows(it, roof, rng, y, share=0.7, tilt_rise=0.35, depth=2.1, gap=0.5, facing_south=True, max_blocks=2):
    """Solar panel rows over the largest free parts of the roof. Returns the number of rows."""
    k = south_k(roof) if facing_south else int(rng.integers(2)) * 2
    rows = 0
    x0, y0, x1, y1 = roof.inner.bounds
    for _ in range(max_blocks):
        placed = False
        for f in np.linspace(share, 0.2, 5):
            ea, eb = (x1 - x0) * np.sqrt(f), (y1 - y0) * np.sqrt(f)
            sx, sz = (ea, eb) if k % 2 == 0 else (eb, ea)
            if sx < 4 or sz < depth:
                break
            p = spot(roof, rng, sx, sz, "center" if not rows else "random", k, 0.8)
            if p is None:
                continue
            n = max(1, int((sz + gap) // (depth + gap)))
            L = min(sx, 60.0)
            pieces = int(np.ceil(sx / L))
            for r in range(n):
                lz = (r - (n - 1) / 2) * (depth + gap)
                for q in range(pieces):
                    lx = (q - (pieces - 1) / 2) * (sx / pieces)
                    a, b = turn(k, lx, lz)
                    it.put(roof, PANEL, M["pv"], C["pv"], p[0] + a, p[1] + b, k, y, sx / pieces - 0.3,
                           tilt_rise + 0.25, depth, panel_param(0.25 / (tilt_rise + 0.25)))
                rows += 1
            placed = True
            break
        if not placed:
            break
    return rows


def helipad(it, roof, rng, y, d=(12, 16)):
    D = rng.uniform(*d)
    while D >= 8.5:
        p = spot(roof, rng, D, D, "center", 0, 0.3)
        if p is not None:
            it.put(roof, BOX, M["helipad"], C[pick(rng, [("helipad", 2), ("helipad_grey", 1)])], *p, 0, y, D, 0.12, D)
            return True
        D *= 0.85
    return False


def pergola(it, roof, rng, y, wall):
    """A decorative frame on a tower top: posts, two edge beams and cross beams every 1.2 m."""
    W, D, H = rng.uniform(6, 12), rng.uniform(5, 10), rng.uniform(3.5, 5.5)
    k = int(rng.integers(2))
    p = spot(roof, rng, W, D, "edge", k, 0.3)
    if p is None:
        return
    col = wall if rng.random() < 0.5 else C["steel_white"]
    for sa in (-1, 1):
        for sb in (-1, 1):
            a, b = turn(k, sa * (W / 2 - 0.2), sb * (D / 2 - 0.2))
            it.put(roof, BOX, M["concrete"], col, p[0] + a, p[1] + b, k, y, 0.4, H, 0.4)
    for sb in (-1, 1):
        a, b = turn(k, 0, sb * (D / 2 - 0.2))
        it.put(roof, BOX, M["concrete"], col, p[0] + a, p[1] + b, k, y + H - 0.5, W, 0.5, 0.35)
    n = int(W / 1.2)
    for j in range(n):
        a, b = turn(k, (j - (n - 1) / 2) * (W / n), 0)
        it.put(roof, BOX, M["concrete"], col, p[0] + a, p[1] + b, k, y + H - 0.25, 0.22, 0.3, D + 0.6)


def bmu(it, roof, rng, y, poly_local, pt):
    """A window-cleaning crane parked on its track, which runs around the roof inside the parapet."""
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
    # the machine on the track, its jib along the edge
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


def car_park(it, roof, rng, y):
    """A deck with parking bays in rows and parked cars."""
    x0, y0, x1, y1 = roof.inner.bounds
    for f in (0.7, 0.5, 0.35):
        ea, eb = (x1 - x0) * np.sqrt(f), (y1 - y0) * np.sqrt(f)
        if ea < 20 or eb < 16:
            return False
        p = roof.find(ea, eb, "center", rng)
        if p is not None:
            break
    else:
        return False
    roof.take(p[0], p[1], ea, eb, 0.3)
    it.put(roof, BOX, M["parking"], C["asphalt"], *p, 0, y, ea, 0.08, eb)
    # rows of bays across b: bay 2.5 m wide along a, 5 m deep, an aisle of 6 m between pairs of rows
    rows = []
    b = -eb / 2 + 2.5
    while b + 2.5 <= eb / 2:            # pairs of rows back to back, an aisle between pairs
        rows.append(b)
        b += 5 if len(rows) % 2 else 11
    n = int((ea - 2) // 2.5)
    cars = [("car_white", 5), ("car_silver", 3), ("car_black", 3), ("car_grey", 2), ("car_red", 1),
            ("car_blue", 1), ("car_champagne", 1)]
    fill = rng.uniform(0.35, 0.85)
    for rb in rows:
        for j in range(n):
            if rng.random() > fill:
                continue
            a = -ea / 2 + 1 + (j + 0.5) * 2.5
            it.put(roof, BOX, M["car"], C[pick(rng, cars)], p[0] + a, p[1] + rb + rng.uniform(-0.2, 0.2), 1,
                   y + 0.08, rng.uniform(4.2, 4.8), rng.uniform(1.4, 1.6), rng.uniform(1.75, 1.85))
    return True


def green_beds(it, roof, rng, y, n):
    for _ in range(n):
        sx, sz = rng.uniform(4, 14), rng.uniform(3, 8)
        k = int(rng.integers(2))
        p = spot(roof, rng, sx, sz, "random", k, 1.0)
        if p is None:
            return
        it.put(roof, BOX, M["green"], C[pick(rng, [("green", 2), ("green2", 1)])], *p, k, y, sx, 0.45, sz)
        for _ in range(int(rng.integers(0, 4))):
            d = min(rng.uniform(1.0, 2.2), sz * 0.8)
            ra, rb = max(0.0, sx / 2 - 0.75 * d), max(0.0, sz / 2 - 0.5 * d)
            a, b = turn(k, rng.uniform(-ra, ra), rng.uniform(-rb, rb))
            it.put(roof, BLOB, M["foliage"], C[pick(rng, [("foliage", 1), ("foliage2", 1)])], p[0] + a, p[1] + b,
                   k, y + 0.45, d * 1.5, d * 0.9, d)


def skylights(it, roof, rng, y, n):
    x0, y0, x1, y1 = roof.inner.bounds
    for _ in range(n):
        sx, sz = (x1 - x0) * rng.uniform(0.15, 0.4), (y1 - y0) * rng.uniform(0.12, 0.3)
        if sx < 3 or sz < 3:
            return
        p = spot(roof, rng, sx, sz, "center", 0, 1.0)
        if p is None:
            return
        if rng.random() < 0.45:
            it.put(roof, GABLE, M["skylight"], C["glass"], *p, 0, y + 0.5, sx, min(sz * 0.3, 2.5), sz)
            it.put(roof, BOX, M["concrete"], C["concrete_light"], *p, 0, y, sx, 0.5, sz)
        else:
            it.put(roof, BOX, M["skylight"], C["glass"], *p, 0, y, sx, 0.7, sz)


# ---------------------------------------------------------------- roof programmes per kind of building

def village(it, roof, rng, y, b):
    area = roof.inner.area
    if area >= 20 and rng.random() < 0.85:
        small = area < 60
        stair_box(it, roof, rng, y, b["wall"], (2.2, 2.8, 3.0, 4.0) if small else (2.5, 3.3, 3.6, 5.0))
    for _ in range(pick(rng, [(0, 3), (1, 4), (2, 2), (3, 1)])):
        tank(it, roof, rng, y)
    if area >= 30 and rng.random() < 0.35:
        heaters(it, roof, rng, y, 3 if area > 80 else 2)
    if area >= 30 and rng.random() < 0.2:
        shed(it, roof, rng, y)
    if rng.random() < 0.45:
        plants(it, roof, rng, y, int(rng.integers(2, 8)))
    if rng.random() < 0.12:
        ac_units(it, roof, rng, y, int(rng.integers(1, 3)))


def residential(it, roof, rng, y, b):
    if b["room"] is None:            # a walk-up block or low-rise: roofs like the villages', a little tidier
        n_boxes = 1 + int(roof.inner.area > 350 and rng.random() < 0.6)
        for _ in range(n_boxes):
            stair_box(it, roof, rng, y, b["wall"], (2.8, 3.6, 4.0, 5.5), (2.8, 3.2), "edge", 0.2)
        for _ in range(int(rng.integers(0, 4))):
            tank(it, roof, rng, y)
        if rng.random() < 0.3:
            heaters(it, roof, rng, y, int(rng.integers(2, 7)))
        if rng.random() < 0.1:
            shed(it, roof, rng, y, (0.2, 0.4))
        if rng.random() < 0.25:
            plants(it, roof, rng, y, int(rng.integers(2, 6)))
        if rng.random() < 0.2:
            ac_units(it, roof, rng, y, int(rng.integers(1, 4)))
        return
    for _ in range(int(rng.integers(1, 3))):
        stair_box(it, roof, rng, y, b["wall"], (3.0, 4.0, 4.0, 6.0), (2.8, 3.3), "center", 0.0)
    if rng.random() < 0.4:
        panel_tank(it, roof, rng, y)
    top = b["top"]
    helipad_done = b["h"] < 100 or rng.random() > 0.7
    if top is not None:
        if not helipad_done and top.inner.area > 110:
            helipad_done = helipad(it, top, rng, top.y, (9, 13))
        if rng.random() < 0.5:
            panel_tank(it, top, rng, top.y, "random") or tank(it, top, rng, top.y)
    if not helipad_done:
        helipad(it, roof, rng, y)
    if b["h"] >= 60 and rng.random() < 0.25:
        pergola(it, roof, rng, y, b["wall"])
    if rng.random() < 0.35:
        panel_tank(it, roof, rng, y)
    for _ in range(int(rng.integers(1, 4))):
        tank(it, roof, rng, y, kind="steel")
    if rng.random() < 0.15:
        heaters(it, roof, rng, y, int(rng.integers(2, 6)))
    if rng.random() < 0.2:              # a roof garden kept by the top-floor residents
        plants(it, roof, rng, y, int(rng.integers(3, 10)))
    if rng.random() < 0.3:
        ac_units(it, roof, rng, y, int(rng.integers(1, 4)))


def glass(it, roof, rng, y, b):
    if b["h"] >= 60 and rng.random() < 0.6:
        bmu(it, roof, rng, y, roof.local, b["pt"])
    area = roof.inner.area
    if area >= 250 and rng.random() < 0.75:
        cooling_towers(it, roof, rng, y, int(rng.integers(2, 6)))
    if area >= 150:
        for _ in range(int(np.clip(area / 500, 1, 4))):
            hvac_cluster(it, roof, rng, y, int(rng.integers(1, 3)), int(rng.integers(2, 5)))
    if area >= 1200:
        plant_box(it, roof, rng, y)
        ducts(it, roof, rng, y, int(rng.integers(1, 4)))
    helipad_done = b["h"] < 150 or rng.random() > 0.6
    top = b["top"]
    if top is not None and not helipad_done and top.inner.area > 110:
        helipad_done = helipad(it, top, rng, top.y, (9, 13))
    if not helipad_done:
        helipad(it, roof, rng, y)
    if top is not None and rng.random() < 0.4:
        hvac_cluster(it, top, rng, top.y, 1, int(rng.integers(2, 4)))
    for _ in range(int(rng.integers(0, 2))):
        stair_box(it, roof, rng, y, C["concrete_light"], (3.0, 4.0, 4.0, 6.0), (2.8, 3.3), "center", 0.0)


def commercial(it, roof, rng, y, b, civic=False):
    area = roof.inner.area
    if area < 150:
        ac_units(it, roof, rng, y, int(rng.integers(1, 4)))
        if rng.random() < 0.5:
            tank(it, roof, rng, y)
        return
    if not civic and area >= 4000 and b["h"] <= 30 and rng.random() < 0.08:
        car_park(it, roof, rng, y)
    for _ in range(int(np.clip(area / 1500, 1, 5 if not civic else 3))):
        stair_box(it, roof, rng, y, b["wall"], (3.0, 4.0, 4.0, 6.0), (2.8, 3.3), "edge", 0.0)   # (no tiled hats: a Shenzhen civic habit)
    if area >= 3000:                  # plant enclosures on big podiums and malls, louvred
        for _ in range(int(np.clip(area / 6000, 1, 4))):
            plant_box(it, roof, rng, y)
    if area >= 2000 and rng.random() < (0.6 if not civic else 0.3):
        cooling_towers(it, roof, rng, y, int(rng.integers(2, 6)))
    big = area > 5000
    n_hvac = int(np.clip(area / 700, 1, 12)) if not civic else int(np.clip(area / 1500, 0, 4))
    for _ in range(n_hvac):
        hvac_cluster(it, roof, rng, y, int(rng.integers(1, 4)), int(rng.integers(2, 8)),
                     (3.6, 2.0, 2.2) if big and rng.random() < 0.5 else (2.4, 1.5, 1.4))
    if area >= 1500:
        ducts(it, roof, rng, y, int(np.clip(area / 2500, 1, 6)))
    if area >= 1200 and rng.random() < (0.35 if not civic else 0.15):
        skylights(it, roof, rng, y, int(rng.integers(1, 3)))
    if rng.random() < (0.18 if not civic else 0.15):
        green_beds(it, roof, rng, y, int(rng.integers(1, 5)))
    if area >= 600 and rng.random() < (0.12 if not civic else 0.25):
        pv_rows(it, roof, rng, y, 0.5, 0.35, max_blocks=1)
    if civic:
        for _ in range(int(rng.integers(1, 3))):
            tank(it, roof, rng, y)
    if b["top"] is not None and rng.random() < 0.4:
        tank(it, b["top"], rng, b["top"].y)


def factory(it, roof, rng, y, b):
    area = roof.inner.area
    if b["h"] < 12:                # a steel shed: vents along the ridge, skylight strips or solar panels
        x0, y0, x1, y1 = roof.inner.bounds
        if rng.random() < 0.35 and area >= 400:
            pv_rows(it, roof, rng, y, 0.8, 0.12, depth=rng.uniform(2.0, 4.2), gap=0.3, facing_south=False)
        elif rng.random() < 0.6 and area >= 300:
            step = rng.uniform(6, 9)
            w = rng.uniform(0.9, 1.3)
            for a in np.arange(x0 + step / 2, x1 - 1, step):
                cols = np.abs(roof.X[0] - a) < w / 2
                if not cols.any():
                    continue
                run = roof.free[:, cols].all(1)
                # longest free run across the roof at this position
                best, cur, start, bs = 0, 0, 0, 0
                for j, f in enumerate(run):
                    cur = cur + 1 if f else 0
                    if cur == 1:
                        start = j
                    if cur > best:
                        best, bs = cur, start
                L = best * roof.cell - 1.0
                if L < 4:
                    continue
                bm = roof.y0 + (bs + best / 2) * roof.cell
                it.put(roof, BOX, M["skylight"], C["glass"], a, bm, 0, y, w, 0.15, L, 1)
                roof.take(a, bm, w, L, 0.2)
        if rng.random() < 0.6 and area >= 200:
            step = rng.uniform(5, 8)
            d = rng.uniform(0.6, 0.8)
            for a in np.arange(x0 + step / 2, x1 - 1, step):
                p = roof.find(d, d, "near", rng, (a, (y0 + y1) / 2))
                if p is not None and abs(p[0] - a) < 1 and abs(p[1] - (y0 + y1) / 2) < 2:
                    roof.take(p[0], p[1], d, d, 0.2)
                    it.put(roof, CYL, M["turbine"], C["stainless"], *p, 0, y, d, d * 1.1, d)
        return
    for _ in range(int(np.clip(area / 1200, 1, 3))):
        stair_box(it, roof, rng, y, b["wall"], (3.0, 4.0, 5.0, 7.0), (2.8, 3.3), "edge", 0.0)
    if rng.random() < 0.6:
        panel_tank(it, roof, rng, y) if rng.random() < 0.5 else tank(it, roof, rng, y)
    r = rng.random()
    if r < 0.25:
        shed(it, roof, rng, y, (0.35, 0.75), (3.0, 4.0))
    elif r < 0.6 and area >= 400:
        pv_rows(it, roof, rng, y, 0.7, 0.4)
    if rng.random() < 0.3:
        for _ in range(int(rng.integers(2, 7))):
            k = int(rng.integers(2))
            p = spot(roof, rng, 1.3, 1.3, "random", k, 0.4)
            if p is None:
                break
            it.put(roof, BOX, M["hvac"], C["hvac2"], *p, k, y, 1.2, 1.0, 1.2)


# ---------------------------------------------------------------- New York's roofs

def water_tower(it, roof, rng, y, big=False):
    """A wooden (cedar) water tank on a steel stand, under a conical roof: on most pre-war buildings of six
    floors and more. Weathered grey-brown, now and then a new one, pale."""
    d = rng.uniform(3.4, 4.8) if big else rng.uniform(3.0, 4.2)
    tank_h = d * rng.uniform(1.0, 1.35)
    stand = rng.uniform(2.2, 4.2)
    p = spot(roof, rng, d + 0.8, d + 0.8, pick(rng, [("edge", 2), ("random", 2), ("corner", 1)]), 0, 0.4)
    if p is None:
        return False
    col = C[pick(rng, [("cedar", 6), ("cedar_dark", 3), ("cedar_new", 1)])]
    it.put(roof, CYL, M["wood"], col, *p, 0, y, d, stand + tank_h, d, cyl_param(False, stand))
    it.put(roof, CONE, M["wood"], C["cedar_dark"], *p, 0, y + stand + tank_h, d * 1.1, d * rng.uniform(0.3, 0.42), d * 1.1)
    return True


def bulkhead(it, roof, rng, y, wall, lift=False):
    """The brick box over the stairs (and, on elevator buildings, the taller machine room beside it)."""
    sx, sz = rng.uniform(2.6, 3.6), rng.uniform(3.4, 5.0)
    if lift:
        sx, sz = sx + 1.5, sz + 0.5
    k = int(rng.integers(4))
    p = spot(roof, rng, sx, sz, pick(rng, [("center", 2), ("edge", 2), ("corner", 1)]), k, 0.3)
    if p is None:
        return None
    col = wall if rng.random() < 0.35 else C[pick(rng, [("brick_dark", 3), ("brick", 1), ("concrete_light", 1)])]   # tar-streaked, darker than the facade
    it.put(roof, BOX, M["stair"], col, *p, k, y, sx, rng.uniform(2.8, 3.4) + (1.2 if lift else 0), sz)
    return p


def chimneys(it, roof, rng, y, n):
    for _ in range(n):
        s_ = rng.uniform(0.7, 1.2)
        p = spot(roof, rng, s_, s_, "edge", 0, 0.1)
        if p is None:
            return
        it.put(roof, BOX, M["stair"], C[pick(rng, [("brick", 3), ("brick_dark", 2)])], *p, 0, y, s_, rng.uniform(1.0, 2.2), s_)


def hatch(it, roof, rng, y):
    p = spot(roof, rng, 1.0, 1.2, "random", 0, 0.2)
    if p is not None:
        it.put(roof, BOX, M["steel"], C["steel_dark"], *p, 0, y, 0.9, 0.6, 1.1)


def prewar(it, roof, rng, y, b):
    """Walk-ups, pre-war apartment houses and lofts: a water tank (most of those of six floors and more), the
    stair bulkhead, chimneys, window units' condensers, sometimes a roof garden."""
    area = roof.inner.area
    if b["h"] >= 17 and b["h"] < 130 and area >= 45 and rng.random() < 0.75:
        water_tower(it, roof, rng, y, big=area > 600)
        if area > 1400 and rng.random() < 0.5:
            water_tower(it, roof, rng, y, big=True)
    if area >= 30:
        bulkhead(it, roof, rng, y, b["wall"], lift=b["h"] > 30 and rng.random() < 0.6)
    chimneys(it, roof, rng, y, int(rng.integers(0, 3)))
    if rng.random() < 0.3:
        hatch(it, roof, rng, y)
    if rng.random() < 0.6:                              # window units' condensers, split systems
        ac_units(it, roof, rng, y, int(rng.integers(1, 3 + min(int(area // 150), 4))))
    if area > 200 and rng.random() < 0.15:
        plants(it, roof, rng, y, int(rng.integers(3, 9)))


def rowhouse(it, roof, rng, y, b):
    """Brownstones and row houses: a hatch or a small stair box, chimneys, a skylight, a roof deck's plants."""
    if rng.random() < 0.6:
        hatch(it, roof, rng, y)
    elif roof.inner.area > 40:
        bulkhead(it, roof, rng, y, b["wall"])
    chimneys(it, roof, rng, y, int(rng.integers(1, 3)))
    if rng.random() < 0.3:
        skylights(it, roof, rng, y, 1)
    if rng.random() < 0.25:
        plants(it, roof, rng, y, int(rng.integers(2, 6)))
    if rng.random() < 0.3:
        ac_units(it, roof, rng, y, 1)


def nyc_residential(it, roof, rng, y, b):
    """Post-war and new apartment towers: bulkheads, a water tank on some, rooftop units, a garden now and then."""
    area = roof.inner.area
    if area >= 60:
        bulkhead(it, roof, rng, y, b["wall"], lift=True)
    if b["h"] < 90 and area >= 80 and rng.random() < 0.3:
        water_tower(it, roof, rng, y, big=True)
    if area >= 150:
        hvac_cluster(it, roof, rng, y, 1, int(rng.integers(2, 5)))
    if area >= 300 and rng.random() < 0.3:
        cooling_towers(it, roof, rng, y, int(rng.integers(1, 3)))
    if rng.random() < 0.2:
        plants(it, roof, rng, y, int(rng.integers(3, 10)))
    if rng.random() < 0.55:
        ac_units(it, roof, rng, y, int(rng.integers(1, 3 + min(int(area // 200), 4))))


def nyc_office(it, roof, rng, y, b):
    """Offices: cooling towers, air handlers, window-cleaning rigs on the tall ones; no helipads."""
    if b["h"] >= 60 and rng.random() < 0.5:
        bmu(it, roof, rng, y, roof.local, b["pt"])
    area = roof.inner.area
    if area >= 200 and rng.random() < 0.8:
        cooling_towers(it, roof, rng, y, int(rng.integers(2, 6)))
    if area >= 150:
        for _ in range(int(np.clip(area / 500, 1, 4))):
            hvac_cluster(it, roof, rng, y, int(rng.integers(1, 3)), int(rng.integers(2, 5)))
    if area >= 1000:
        plant_box(it, roof, rng, y)
        ducts(it, roof, rng, y, int(rng.integers(1, 4)))
    top = b["top"]
    if top is not None and rng.random() < 0.5:
        hvac_cluster(it, top, rng, top.y, 1, int(rng.integers(2, 4)))


def stone(it, roof, rng, y, b):
    (prewar if b["h"] < 90 else nyc_office)(it, roof, rng, y, b)


PROGRAMME = {"village": prewar,        # (Shenzhen's village roofs, tiled hats and all, have no place here)
              "residential": nyc_residential, "glass": nyc_office, "commercial": commercial,
             "civic": lambda *a: commercial(*a, civic=True), "factory": factory, "brick": prewar, "brownstone": rowhouse,
             "stone": stone, "crowned": stone, "castiron": prewar, "signs": commercial, "spire": lambda *a: None, "plain": lambda *a: None}
