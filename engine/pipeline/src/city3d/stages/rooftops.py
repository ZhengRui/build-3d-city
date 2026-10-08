"""06c_rooftops: rooftop clutter for the viewer: stair and lift boxes, water tanks, solar water heaters, sheds,
cooling towers, air handlers, window-cleaning cranes, skylights, solar panels, green roofs, helipads, cars.

This module is the machinery (roofs and their free cells, placement, the tile format); what stands on a roof
is the region preset's (PROGRAMME and its items in presets/<preset>/rooftops.py, colours in
presets/<preset>.toml [rooftops.named]). As built for Shenzhen (preset china-south):

The building tiles (06_tiles.py) are flat roofs with at most one plant room, which reads as a clean slab
from the air, while a Shenzhen roof is anything but. What stands on each roof is invented, not mapped, but
follows what the kind of building usually carries:
  urban villages   parapets, a stair-access box in a corner (some with a small tiled hat or tanks on
                   top), stainless or blue plastic water tanks on stands, solar water heaters facing
                   south, blue corrugated lean-to sheds, potted plants, a few outdoor air-conditioner units
  residential      taller parapets; on towers extra stair and lift boxes, panel water tanks, tanks on the
                   plant room, pergola crowns on some, a helipad marking on most above 100 m; lower blocks
                   are treated like old walk-ups: stair boxes, tanks, heaters, plants
  offices (glass)  glass screens or parapets, cooling towers (square and round), air handlers, a
                   window-cleaning crane (BMU) on its track on taller ones, helipads on the tallest
  commercial       podiums and malls: stair boxes, clusters of rooftop units, cooling towers, skylights,
                   green roofs, now and then a rooftop car park with cars
  civic            schools, hospitals: stair boxes, tanks, a few units, solar panels, green beds
  factories        low steel sheds: roof ventilators along the ridge, skylight strips or solar panel rows,
                   no parapet; multi-storey factories: stair boxes, tanks, blue sheds or solar panels
Landmarks (a height from the landmark list or a researched facade) get nothing.

Buildings come from buildings.gpkg through 06_tiles.py's own steps (simplification, road clearance, facade
style, per-building seed, landmark facades), imported rather than copied, so every roof here is a roof
there, with the same height and wall colour. Items stay inside the roof outline minus the parapet and never
overlap 06_tiles.py's plant room, whose footprint is recomputed with its own function (some items stand on
top of it). Placement runs on a grid of free cells per roof, in the roof's own frame (its long axis).

Parapets are not written here: the viewer (web/rooftops.js) builds them from the building tiles' own walls,
so they follow the rendered outline exactly and cost no data; this script only keeps items clear of them
(PARAPET_T) and lists the landmark outlines the viewer must leave bare.

Output, rooftops/ in the data folder (the viewer reads it through web/rooftops, a link this stage makes):
  rooftops.json      index: prototypes, materials and facade styles (names in the viewer's order), colour
                     palette (linear RGB; the named colours, then 06_tiles.py's wall palettes), quantization
                     steps, landmark outlines (scene x, z), tiles with their roof and item counts
  r_<tx>_<ty>.bin    per 1 km tile (same grid and keys as 06_tiles.py), gzip of
                       u32 roofs m, u32 items n
                       roofs, along a Hilbert curve through the tile (neighbours follow each other):
                         centre x, z (ITEM_Q m from the tile's north-west corner, z southwards) and height
                         (Y_Q m, in the scene: the building's base on the ground plus its height) as int16
                         differences to the previous roof; axis (1/65536 turn,
                         counter-clockwise from east seen from above) and item count as uint16; each 16 bit
                         column split into its low bytes, then its high bytes (compresses better)
                       items, roof by roof:
                         u8[n] prototype x 32 + material, u8[n] colour (palette index), u8[n] param
                         a, b: centre in the roof's frame (along its axis, to its left; ITEM_Q m) as int16
                         u8[n] height above the roof (Y_Q m)
                         yaw relative to the roof's axis (1/65536 turn; its +x axis), uint16
                         size x, y, z (SIZE_Q m) as uint16
                       16 bit columns split as above
Prototypes (unit shapes the viewer instances, sized per item): a box (bottom at 0, centred), a cylinder
(param: bit 0 lying along x, bits 1-7 the height of its steel stand in 5 cm), a tilted panel on legs (param:
bits 0-6 front height / back height x 127, bit 7 a tank along the top), a gable (ridge along x) and a clump
of three leafy blobs. Rows of identical units (air handlers, cooling tower cells, solar heaters) are one
item whose param (or length) tells the viewer how many to draw.
"""
import gzip
import json
import multiprocessing as mp
import struct
import time
from concurrent.futures import ProcessPoolExecutor

import geopandas as gpd
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import Polygon

from .. import presets
from ..common import CFG, DATA, UTM_EPSG, UTM, Terrain, boundary, link_web
from . import tiles as tiles06

TILE, STYLES, polygons, plant_room, srgb = (tiles06.TILE, tiles06.STYLES, tiles06.polygons, tiles06.plant_room,
                                            tiles06.srgb)
PLANT_MIN_H, PLANT_MIN_AREA, PLANT_H = tiles06.PLANT_MIN_H, tiles06.PLANT_MIN_AREA, tiles06.PLANT_H

OUT = DATA / "rooftops"
ITEM_Q, Y_Q, SIZE_Q = 0.1, 0.05, 0.05     # metres (heights are rounded down: nothing floats)
TAU = 2 * np.pi
MIN_AREA = 12                 # roofs smaller than this (m²) get nothing
CELL = 0.5                    # placement grid (m); coarser on very large roofs
MAX_CELLS = 60000

PROTOS = ["box", "cylinder", "panel", "gable", "blob", "cone", "pots"]
BOX, CYL, PANEL, GABLE, BLOB, CONE, POTS = range(len(PROTOS))
# materials: the viewer's rooftops.js draws each (same order)
MATS = ["parapet", "concrete", "stair", "hvac", "cooling", "paneltank", "stainless", "plastic", "tubes", "pv",
        "corrugated", "tile", "skylight", "green", "foliage", "helipad", "steel", "screen", "parking", "car",
        "turbine", "wood", "chimney", "pot", "velux", "zinc"]
M = {name: i for i, name in enumerate(MATS)}

# named colours (sRGB, the preset's [rooftops.named]); the wall palettes of 06_tiles.py's styles follow them
# in the palette
NAMED = CFG["rooftops"]["named"]
NAMES = list(NAMED)
C = {name: i for i, name in enumerate(NAMES)}
WALL0 = {}                    # style -> palette index of its first wall colour
PALETTE = srgb(" ".join(NAMED.values()))
for _style, _st in STYLES.items():
    WALL0[_style] = len(PALETTE)
    PALETTE += _st["palette"]


def wall_colour(style: str, seed: float) -> int:
    """Palette index of the building's wall colour, picked as 06_tiles.py picks it."""
    pal = STYLES[style]["palette"]
    return WALL0[style] + int(seed * 997) % len(pal)


# ---------------------------------------------------------------- the roof and its free cells

class Roof:
    """A roof polygon in its own frame (a along its long axis, b to the left, origin at the centroid) with a
    grid of free cells: inside the outline minus `margin` and not yet taken by an item."""

    def __init__(self, poly: Polygon, margin: float, theta: float | None = None, blockers=()):
        c = poly.centroid
        self.cx, self.cy = c.x, c.y
        if theta is None:
            theta = Roof.axis(poly)
        self.theta = theta
        self.cos, self.sin = np.cos(theta), np.sin(theta)
        self.local = self.to_local(poly)
        inner = self.local.buffer(-margin, join_style="mitre")
        self.ok = not inner.is_empty and inner.area > 1
        if not self.ok:
            return
        self.inner = inner
        x0, y0, x1, y1 = inner.bounds
        self.cell = max(CELL, float(np.sqrt((x1 - x0) * (y1 - y0) / MAX_CELLS)))
        self.x0, self.y0 = x0, y0
        self.nx = max(1, int(np.ceil((x1 - x0) / self.cell)))
        self.ny = max(1, int(np.ceil((y1 - y0) / self.cell)))
        gx = x0 + (np.arange(self.nx) + 0.5) * self.cell
        gy = y0 + (np.arange(self.ny) + 0.5) * self.cell
        self.X, self.Y = np.meshgrid(gx, gy)
        self.free = shapely.contains_xy(inner, self.X, self.Y)
        for g in blockers:
            self.block(self.to_local(g), 0.3)

    @staticmethod
    def axis(poly) -> float:
        """The long axis of a polygon's minimum rotated rectangle (radians, counter-clockwise from east)."""
        r = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)
        e = np.diff(r[:3], axis=0)
        k = int(np.argmax(np.hypot(e[:, 0], e[:, 1])))
        return float(np.arctan2(e[k, 1], e[k, 0]))

    def to_local(self, geom):
        c, s = self.cos, self.sin
        return affinity.affine_transform(geom, [c, s, -s, c, -(c * self.cx + s * self.cy), s * self.cx - c * self.cy])

    def to_world(self, a, b):
        return self.cx + a * self.cos - b * self.sin, self.cy + a * self.sin + b * self.cos

    def block(self, geom_local, pad=0.0):
        g = geom_local.buffer(pad) if pad else geom_local
        self.free &= ~shapely.contains_xy(g, self.X, self.Y)

    def find(self, ea, eb, prefer="random", rng=None, target=None):
        """Centre (a, b) of a free window ea x eb metres (along a, b), or None.
        prefer: random, edge (against the parapet or another item), center, near (closest to target (a, b)),
        corner (closest to one of the inner outline's bounding-box corners)."""
        na, nb = int(np.ceil(ea / self.cell - 1e-6)), int(np.ceil(eb / self.cell - 1e-6))
        if na > self.nx or nb > self.ny or na < 1 or nb < 1:
            return None
        occ = np.ones((self.ny + 2, self.nx + 2), np.int32)
        occ[1:-1, 1:-1] = ~self.free
        S = np.zeros((self.ny + 3, self.nx + 3), np.int32)
        S[1:, 1:] = occ.cumsum(0).cumsum(1)

        def win(j0, i0, h, w):          # sums of occ over windows of h x w starting at padded (j0.., i0..)
            return S[j0 + h:, i0 + w:][:self.ny - nb + 1, :self.nx - na + 1] - \
                S[j0:, i0 + w:][:self.ny - nb + 1, :self.nx - na + 1] - \
                S[j0 + h:, i0:][:self.ny - nb + 1, :self.nx - na + 1] + \
                S[j0:, i0:][:self.ny - nb + 1, :self.nx - na + 1]
        ok = win(1, 1, nb, na) == 0
        if not ok.any():
            return None
        jj, ii = np.nonzero(ok)
        a = self.x0 + (ii + na / 2) * self.cell
        b = self.y0 + (jj + nb / 2) * self.cell
        if prefer == "edge":
            touch = win(0, 0, nb + 2, na + 2)[jj, ii] > 0
            if touch.any():
                a, b = a[touch], b[touch]
            k = rng.integers(len(a))
        elif prefer == "center":
            ca, cb = self.inner.centroid.x, self.inner.centroid.y
            k = int(np.argmin((a - ca) ** 2 + (b - cb) ** 2))
        elif prefer == "near":
            k = int(np.argmin((a - target[0]) ** 2 + (b - target[1]) ** 2))
        elif prefer == "corner":
            x0, y0, x1, y1 = self.inner.bounds
            ca, cb = (x0, x1)[rng.integers(2)], (y0, y1)[rng.integers(2)]
            k = int(np.argmin((a - ca) ** 2 + (b - cb) ** 2))
        else:
            k = rng.integers(len(a))
        return float(a[k]), float(b[k])

    def take(self, a, b, ea, eb, pad=0.3):
        m = (np.abs(self.X - a) < ea / 2 + pad) & (np.abs(self.Y - b) < eb / 2 + pad)
        self.free &= ~m

    def free_area(self):
        return float(self.free.sum()) * self.cell ** 2


class Items:
    """Items of one tile, grouped by roof: a roof record [centre E, N, axis theta, height y, item count] and
    its items (prototype, material, colour, param, E, N, y, yaw, sx, sy, sz). Heights are given from the
    building's base and stored in the scene, `base` (the ground it stands on, 06_tiles.py's) higher."""

    def __init__(self):
        self.rows, self.roofs = [], []
        self.base = 0.0

    def roof(self, roof, y):
        self.roofs.append([roof.cx, roof.cy, roof.theta, y + self.base, 0])

    def end(self):
        if self.roofs and not self.roofs[-1][4]:
            self.roofs.pop()

    def world(self, proto, mat, col, E, N, y, yaw, sx, sy, sz, param=0):
        # sizes over 1.5 m to 10 cm (fewer distinct values compress better; spots have room to spare)
        sx, sy, sz = (round(v, 1) if v > 1.5 else v for v in (sx, sy, sz))
        self.rows.append((proto, mat, col, param, E, N, y + self.base, yaw, sx, sy, sz))
        self.roofs[-1][4] += 1

    def put(self, roof, proto, mat, col, a, b, k, y, sx, sy, sz, param=0):
        """An item centred at (a, b) of the roof frame, turned k quarter turns from the roof's axis;
        sx along its own x, sz across (its front is +z in the viewer, a quarter turn clockwise from x)."""
        E, N = roof.to_world(a, b)
        self.world(proto, mat, col, E, N, y, roof.theta + k * np.pi / 2, sx, sy, sz, param)


def turn(k, lx, lz):
    """Offset (lx along the item's x, lz towards its front) -> roof frame (a, b), for k quarter turns."""
    ux, uy = [(1, 0), (0, 1), (-1, 0), (0, -1)][k % 4]
    fx, fy = uy, -ux                               # the front: x turned a quarter clockwise
    return lx * ux + lz * fx, lx * uy + lz * fy


def ext(k, sx, sz):
    """Extent along the roof's (a, b) of an item sx x sz turned k quarter turns."""
    return (sx, sz) if k % 2 == 0 else (sz, sx)


# ---------------------------------------------------------------- items

def spot(roof, rng, sx, sz, prefer="random", k=0, pad=0.3, target=None):
    ea, eb = ext(k, sx, sz)
    p = roof.find(ea + 2 * pad, eb + 2 * pad, prefer, rng, target)
    if p is None:
        return None
    roof.take(p[0], p[1], ea, eb, pad)
    return p


# solar heaters and panels face the equator: south in the northern hemisphere
EQUATOR_K = 0 if CFG["sun"]["latitude"] >= 0 else 2


def south_k(roof):
    """Quarter turns from the roof axis that make an item's front face closest to south (north in the southern
    hemisphere)."""
    return (int(np.round(-roof.theta / (np.pi / 2))) + EQUATOR_K) % 4


def pick(rng, table):
    names, weights = zip(*table)
    w = np.asarray(weights, float)
    return names[rng.choice(len(names), p=w / w.sum())]


def cyl_param(lying: bool, stand: float) -> int:
    """Cylinder param: bit 0 lying along x, bits 1-7 the height of its steel stand in 5 cm."""
    return int(lying) | min(127, round(stand / 0.05)) << 1


def panel_param(front: float, tank: bool = False) -> int:
    """Panel param: bits 0-6 the front edge's height as a share of the back's (x 127), bit 7 a tank along
    the top (solar water heaters)."""
    return min(127, round(front * 127)) | int(tank) << 7


# parapet thickness per style (m), kept clear of items; the viewer builds the parapets themselves from the
# tiles' walls (rooftops.js), so they follow the rendered outline exactly and cost no data
PARAPET_T = CFG["rooftops"]["parapet_t"]
PARAPET_DEFAULT = CFG["rooftops"]["parapet_default"]
# facade styles whose flat roofs get their party walls and footprint too (default none: as before)
FLAT_PARTY = set(CFG["rooftops"].get("flat_party", []))


# ---------------------------------------------------------------- per tile

def hilbert(u, v, bits=8):
    """Index along a Hilbert curve of points (u, v) in 0..1 (clipped), on a 2^bits grid."""
    n = 1 << bits
    x = np.clip((np.asarray(u) * n).astype(np.int64), 0, n - 1)
    y = np.clip((np.asarray(v) * n).astype(np.int64), 0, n - 1)
    d = np.zeros_like(x)
    s = n >> 1
    while s:
        rx = (x & s) > 0
        ry = (y & s) > 0
        d += s * s * ((3 * rx) ^ ry)
        # rotate the quadrant
        flip = ~ry
        x, y = np.where(flip & rx, s - 1 - x, x), np.where(flip & rx, s - 1 - y, y)
        x, y = np.where(flip, y, x), np.where(flip, x, y)
        s >>= 1
    return d


G = {}                        # shared with the worker processes (fork context, see main())


def tile_items(key):
    tx, ty = key
    b = G["by_tile"][key]
    tree, heights, geoms, party = G["tree"], G["heights"], G["geoms"], G["party"]
    rng = np.random.default_rng([tx + 1000, ty + 1000, 606])
    it = Items()
    # buildings along a Hilbert curve through the tile: neighbours follow each other, so the position
    # differences stored per roof stay small
    c = b.geometry.centroid
    order = np.argsort(hilbert((c.x.values - G["origin"][0]) / TILE - tx, (c.y.values - G["origin"][1]) / TILE - ty))
    for row in b.iloc[order].itertuples():
        if row.h_src == "landmark" or row.tint is not None or row.facade not in PROGRAMME:
            continue
        h, style = float(row.h), row.facade
        it.base = float(row.ground)
        pt = PARAPET_T.get(style, PARAPET_DEFAULT)
        # a roof shape (06_tiles.py's ROOF: a mansard or a pitched roof leaning in from the free walls)
        rise = float(getattr(row, "roof_h", 0.0) or 0.0)
        rise = rise if rise > 0 and row.profile is None else 0.0
        for poly in polygons(row.geometry):
            if poly.area < MIN_AREA:
                continue
            # taller buildings standing on this roof (overlapping footprints) are kept clear
            near = tree.query(poly, predicate="intersects")
            blockers = [geoms[j] for j in near if heights[j] > it.base + h + 0.5]
            shape, party_lines, free_lines, eaves, footprint, zone = "", [], [], h, None, None
            if rise > 0:
                # the roof's flat top (a mansard's terrasson, a pitched roof's ridge strip), exactly as 06_tiles.py
                # builds it; items stand on it, chimney stacks rise from the eaves along the party walls
                eaves = h - rise
                prof = [(0.0, 1.0, 0.0), ((eaves - float(row.min_h)) / max(h - float(row.min_h), 0.1), 1.0, 0.0),
                        (1.0, 1.0, float(row.roof_d))]
                free = (lambda pts, _i=row.Index, _e=eaves: party(pts, _i, _e))
                top_out = []
                tiles06.extrude(poly, h, G["origin"], (0.5, 0.5, 0.5), base=float(row.min_h), profile=prof,
                                ground=0.0, free=free, roof_out=top_out)
                shape = "pitched" if float(row.roof_d) >= 7.9 else "mansard"
                footprint = poly
                top = max(polygons(top_out[0].buffer(0)), key=lambda q: q.area, default=None) if top_out else None
                # (no flat top to speak of: a roof without free cells, only stacks along the party walls)
                ok_top = top is not None and top.area > 2
                roof = Roof(top if ok_top else poly, 0.1 if ok_top else 1e4, theta=Roof.axis(poly), blockers=blockers)
                # party walls: the footprint's edges against a neighbour reaching this roof's eaves
                ring = np.asarray(poly.exterior.coords)
                a_, b_ = ring[:-1], ring[1:]
                L = np.hypot(*(b_ - a_).T)
                ok = L > 1.0
                if ok.any():
                    w = free((a_[ok] + b_[ok]) / 2)
                    party_lines = [(tuple(p0), tuple(p1)) for p0, p1, wi in zip(a_[ok], b_[ok], w) if wi == 0]
                    free_lines = [(tuple(p0), tuple(p1)) for p0, p1, wi in zip(a_[ok], b_[ok], w) if wi > 0]
                # where a chimney stack may stand: the flat top (a hand's breadth beyond it), never on a slope;
                # without a top (a pitched roof's slopes meet) the band along the ridge, away from the free walls
                zone = None
                try:
                    if ok_top:
                        zone = poly.intersection(top.buffer(0.3, join_style="mitre"))
                    else:
                        edges = shapely.MultiLineString([list(e) for e in free_lines]) if free_lines else None
                        for f in (0.85, 0.7, 0.55, 0.4, 0.25):
                            z = poly.difference(edges.buffer(float(row.roof_d) * f, cap_style="flat")) if edges else poly
                            if not z.is_empty and z.area > 1:
                                zone = z
                                break
                    zone = zone.buffer(0) if zone is not None else None
                except shapely.errors.GEOSException:
                    zone = top.buffer(0.3) if ok_top else None
            else:
                roof = Roof(poly, pt + 0.35, blockers=blockers)
                if style in FLAT_PARTY:
                    # a flat roof whose stacks stand on its party walls (London's terraces behind their
                    # parapets): the footprint's edges against a neighbour as tall, as under a roof shape
                    footprint = poly
                    ring = np.asarray(poly.exterior.coords)
                    a_, b_ = ring[:-1], ring[1:]
                    ok = np.hypot(*(b_ - a_).T) > 1.0
                    if ok.any():
                        w = party((a_[ok] + b_[ok]) / 2, row.Index, h)
                        party_lines = [(tuple(p0), tuple(p1)) for p0, p1, wi in zip(a_[ok], b_[ok], w) if wi == 0]
                        free_lines = [(tuple(p0), tuple(p1)) for p0, p1, wi in zip(a_[ok], b_[ok], w) if wi > 0]
            if not roof.ok and rise == 0:
                continue
            room = None
            if rise == 0 and h >= PLANT_MIN_H and poly.area >= PLANT_MIN_AREA and style != "factory":
                room = plant_room(poly)          # 06_tiles.py's plant room, exactly
            top = None
            if room is not None:
                roof.block(roof.to_local(room), 0.6)
                top = Roof(room, 0.3, theta=roof.theta)
                top = top if top.ok else None
                if top is not None:
                    top.y = h + PLANT_H
            # (the roof record's height is the lowest item base: the eaves under a roof shape)
            it.roof(roof, eaves)
            ctx = {"wall": wall_colour(style, float(row.seed)), "h": h, "room": room, "top": top, "pt": pt,
                   "shape": shape, "rise": rise, "eaves": eaves, "party": party_lines, "free": free_lines, "footprint": footprint,
                   "zone": zone, "roof_d": float(getattr(row, "roof_d", 0.0) or 0.0),
                   "roof_ok": roof.ok}
            PROGRAMME[style](it, roof, rng, h, ctx)
            it.end()
    return key, it.roofs, it.rows


def split16(a) -> bytes:
    """Integers -> 16 bit (wrapping), low bytes then high bytes (compresses better than interleaved)."""
    b = np.ascontiguousarray(np.asarray(a).astype(np.int64).astype(np.uint16)).view(np.uint8).reshape(-1, 2)
    return b[:, 0].tobytes() + b[:, 1].tobytes()


def encode(key, roofs, rows) -> bytes:
    """The tile's binary body (see the module docstring). Items are stored in their roof's frame, from
    the roof's quantized centre and axis, so the viewer puts them back exactly."""
    tx, ty = key
    e0, n0 = G["origin"][0] + tx * TILE, G["origin"][1] + (ty + 1) * TILE     # north-west corner
    R, I = np.array(roofs, np.float64), np.array(rows, np.float64)
    bx = np.round((R[:, 0] - e0) / ITEM_Q).astype(np.int64)
    bz = np.round((n0 - R[:, 1]) / ITEM_Q).astype(np.int64)
    by = np.floor(R[:, 3] / Y_Q + 1e-6).astype(np.int64)
    th = np.round((R[:, 2] % TAU) / TAU * 65536).astype(np.int64) % 65536
    cnt = R[:, 4].astype(np.int64)
    assert np.abs(bx).max() < 32768 and np.abs(bz).max() < 32768 and by.max() < 65536 and cnt.max() < 65536
    own = np.repeat(np.arange(len(R)), cnt)
    thq = th[own] / 65536 * TAU
    dE, dN = I[:, 4] - (e0 + bx[own] * ITEM_Q), I[:, 5] - (n0 - bz[own] * ITEM_Q)
    qa = np.round((dE * np.cos(thq) + dN * np.sin(thq)) / ITEM_Q).astype(np.int64)
    qb = np.round((-dE * np.sin(thq) + dN * np.cos(thq)) / ITEM_Q).astype(np.int64)
    dy = np.clip(np.floor((I[:, 6] - by[own] * Y_Q) / Y_Q + 1e-6), 0, 255).astype(np.uint8)
    # yaw relative to the roof's axis (unquantized, so quarter turns come out exact)
    yaw = np.round(((I[:, 7] - R[own, 2]) % TAU) / TAU * 65536).astype(np.int64) % 65536
    size = np.round(I[:, 8:11] / SIZE_Q).clip(1, 65535).astype(np.int64)
    assert np.abs(qa).max() < 32768 and np.abs(qb).max() < 32768
    kind = (I[:, 0].astype(np.int64) * 32 + I[:, 1].astype(np.int64)).astype(np.uint8)
    diff = lambda q: np.diff(q, prepend=0)
    return struct.pack("<II", len(R), len(I)) + \
        split16(diff(bx)) + split16(diff(bz)) + split16(diff(by)) + split16(th) + split16(cnt) + \
        kind.tobytes() + I[:, 2].astype(np.uint8).tobytes() + I[:, 3].astype(np.uint8).tobytes() + \
        split16(qa) + split16(qb) + dy.tobytes() + split16(yaw) + \
        split16(size[:, 0]) + split16(size[:, 1]) + split16(size[:, 2])


def landmark_outlines(b, origin) -> list:
    """Scene outlines (x, z; 0.5 m outside the footprint) of the buildings that get nothing, so the viewer
    leaves their walls without a parapet too."""
    out = []
    sel = b[(b.h_src == "landmark") | b.tint.notna()]
    for geom in sel.geometry:
        for poly in polygons(geom.buffer(0.5, join_style="mitre").simplify(0.5)):
            c = np.asarray(poly.exterior.coords)[:-1]
            out.append([[round(x - origin[0], 1), round(origin[1] - y, 1)] for x, y in c])
    return out


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)
    # the building table exactly as 06_tiles.py prepares it (same order, styles, seeds, roof shapes and ground)
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    b, _terrain = tiles06.prepared_buildings(ways, origin)

    # every building part with its height, to keep roofs clear where a taller one stands on them
    parts = b[["h", "ground", "geometry"]].explode(index_parts=False)
    parts = parts[parts.geometry.geom_type == "Polygon"]
    G.update(origin=origin, tree=shapely.STRtree(parts.geometry.values), heights=(parts.h + parts.ground).values.astype(float),
             geoms=parts.geometry.values, by_tile=dict(iter(b.groupby(["tx", "ty"]))),
             party=tiles06.party_walls(b))
    keys = sorted(G["by_tile"])
    print(f"{len(b):,} buildings in {len(keys)} tiles ({time.time() - t0:.0f} s)")

    for f in OUT.glob("r_*.bin"):
        f.unlink()
    tiles, n_roofs, n_items, size = [], 0, 0, 0
    by_kind = np.zeros((len(PROTOS), len(MATS)), int)
    # fork, not the default start method (forkserver on Python 3.14): the workers read the module global G
    with ProcessPoolExecutor(8, mp_context=mp.get_context("fork")) as ex:
        for key, roofs, rows in ex.map(tile_items, keys, chunksize=4):
            if not rows:
                continue
            name = f"r_{key[0]}_{key[1]}.bin"
            (OUT / name).write_bytes(gzip.compress(encode(key, roofs, rows), 9))
            size += (OUT / name).stat().st_size
            top = max(r[6] + r[9] for r in rows)
            tiles.append({"file": name, "x": key[0] * TILE, "z": -(key[1] + 1) * TILE, "roofs": len(roofs),
                          "items": len(rows), "maxHeight": round(float(top), 1)})
            n_roofs += len(roofs)
            n_items += len(rows)
            for r in rows:
                by_kind[r[0], r[1]] += 1
    index = {"origin": {"utm_epsg": UTM_EPSG, "easting": origin[0], "northing": origin[1]}, "tileSize": TILE,
             "protos": PROTOS, "materials": MATS, "styles": list(STYLES),
             "palette": [[round(float(v), 5) for v in rgb] for rgb in PALETTE],
             "quant": {"item": ITEM_Q, "y": Y_Q, "size": SIZE_Q},
             "landmarks": landmark_outlines(b, origin), "tiles": tiles}
    (OUT / "rooftops.json").write_text(json.dumps(index, separators=(",", ":")))
    link_web("rooftops")
    print(f"{len(tiles)} tiles, {n_roofs:,} roofs, {n_items:,} items, {size / 1e6:.1f} MB ({time.time() - t0:.0f} s)")
    print({f"{PROTOS[p]}/{MATS[m]}": int(by_kind[p, m]) for p, m in zip(*np.nonzero(by_kind))})


# the region's roof programmes: facade style -> function(items, roof, rng, y, building); imported last, as
# they build on the machinery above
_PRESET = presets.module(part="rooftops")
PROGRAMME = _PRESET.PROGRAMME
# (opt-in, a preset's own: EXTRA_PROTOS and EXTRA_MATS, prototypes and materials appended after the shared ones, so
# every other city's indices and files stay as they were; Hong Kong's projecting street signs)
for _name in getattr(_PRESET, "EXTRA_PROTOS", ()):
    PROTOS.append(_name)
for _name in getattr(_PRESET, "EXTRA_MATS", ()):
    M[_name] = len(MATS)
    MATS.append(_name)
