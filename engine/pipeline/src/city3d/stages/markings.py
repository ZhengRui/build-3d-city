"""06b_markings: road surface overlays for the viewer: lane markings, zebra crossings, sidewalks, medians, runways.

The road meshes from 06_tiles.py are flat merged polygons without texture coordinates, so nothing
along or across a road can be drawn on them. This step lays thin strips over them, following each
OSM way, whose texture coordinates are (across, along) in metres; the viewer's shader (web/ground.js)
draws the markings procedurally from those, anti-aliased and fading to the asphalt's average colour
where they get smaller than a pixel. Geometry is only a quad per centreline segment, so detail costs
nothing here.

Strip types (COLOR_0.r):
  LANES     the carriageway, OVER_Y above the road mesh (on bridges above the deck): asphalt with lane
            lines, edge lines, the yellow centre line of two-way roads, wear and patching. Opaque, and
            its asphalt matches the road mesh's, so where it ends the two meet without a seam.
  CROSSING  a zebra crossing and stop line at each end of a road that meets another street, just
            outside the junction box (which is left to the plain road mesh)
  SIDEWALK  kerb, paving, tree pits, tactile strip and on big roads a red bike lane, beside the road
            but SIDE_Y *below* it: where a sidewalk strip runs into another road, that road wins
  MEDIAN    planted median on the inner side of a one-way carriageway (dual carriageways are two ways)
  RUNWAY    a whole runway: edge and centre lines, threshold bars, touchdown and aiming point marks
            (b = its length / 20 m, so the shader can find the far threshold)
  PLAZA     pedestrian streets, paved across their width
  ZEBRA     ([markings] zebras) an OSM zebra crossing between junctions: the stripes, give-way lines and the
            zig-zags either side; along is 20 m at the crossing's middle, the lane strip leaves the gap to it
  BEACON    ([markings] zebras) a Belisha beacon at each end of a zebra: a banded pole and an amber globe, solid
            geometry at absolute heights (along = metres above the pavement)
  TRAM      ([markings] trams) a tram track (OSM railway=tram) over everything else, across 0 at the track's
            centre: two grooved rails 1.435 m apart; b the bed: 0 asphalt (embedded in a carriageway), 1 granite
            setts (Pflastergleis), 2 grass (Rasengleis), 3 ballast and sleepers (a track off the road)

Ground: strips of ground-level roads and runways lie OVER_Y (and so on) above the ground of 05a_terrain.py,
cut along its TIN's triangles wherever it bends more than DRAPE_TOL under them (common.Terrain.drape_triangles),
so they follow it as the road meshes do; strips on bridge decks keep the deck's own height.

Per vertex:
  POSITION    uint16 per axis, undone by the node's (non-uniform) scale and translation
  NORMAL      int8, the ground's (straight up on decks and level ground), stored times the node's scale
  TEXCOORD_0  (across + ACROSS_MAX, along) / (2 ACROSS_MAX, ALONG_MAX) as unorm16; across is metres
              left of the centreline (left of the way's direction), along metres along it
  COLOR_0     RGBA8 integers: r type, g half width x 4, b lanes (see lane_code), a type-specific
              flags (crossing: stop line sides; sidewalk: its width x 10; lanes: yellow left edge)
              lanes flags: 1 yellow left edge, 2 / 4 bus lane along the left / right kerb (across > 0 / < 0),
                8 the bus lanes red, 16 x k kerb lines (k: 0 none, 1 double yellow, 2 double red), 64 the
                warning line before a junction ([markings] warning), 128 cycle lanes along the kerbs
              lanes and crossings b: + 128 a sett (cobbled) carriageway ([markings] setts: OSM surface)
              sidewalk b: its style ([markings] sidewalk_style; 0 plain, 1 the second style: Berlin's
                mosaic-and-slab Gehweg)
              crossing flags: 1, 2 stop line sides, 4 x k the junction's marking (k: 0 zebra, 1 give-way
                line, 2 signals: stop line and stud lines, 3 none; [markings] junctions), 16 x k kerb lines

Junctions: OSM nodes where three or more road segments meet. A way is split there and each end cut
back by the width of the widest other road meeting it (plus that road's sidewalk), so markings stop
at the junction box; pieces shorter than MIN_PIECE between two junctions (the middle of a dual
carriageway junction) get no overlay at all.

Driving side (city.toml drive): on the right (Shenzhen), a two-way road's stop lines lie on the left half
at its start and the right half at its end, and a one-way carriageway of a dual road has its median and
yellow edge on the left; on the left, all of that is mirrored (the yellow edge flag is then left off: the
viewer only draws a yellow left edge).

Tiles: pieces are cut into chunks of at most CHUNK metres, each put in the 1 km tile (06_tiles.py's
keys) holding its midpoint, one mesh per tile. Writes markings_raw/ in the data folder, then compresses it
with 07_pack.py's meshopt encoder into markings/ with markings.json.
"""
import json
import struct
from collections import defaultdict

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from ..common import CFG, DATA, RAW, UTM, Terrain, boundary, generator, link_web, overpass, weld
from . import pack as pack07
from . import tiles as tiles06

TILE, ROAD_Y, optimize, to_scene = tiles06.TILE, tiles06.ROAD_Y, tiles06.optimize, tiles06.to_scene

OUT_RAW = DATA / "markings_raw"
OUT = DATA / "markings"

LANES, CROSSING, SIDEWALK, MEDIAN, RUNWAY, PLAZA, ZEBRA_T, BEACON, TRAM = range(9)
OVER_Y = 0.12                 # overlay above the road surface
SIDE_Y = -0.12                # sidewalks under it, still above the viewer's aeroway layer (1.2)
DRAPE_TOL = 0.03              # strips stay whole where a plane through their corners keeps this close to
                              # the ground; elsewhere they are cut along the TIN
RUNWAY_Y = 1.3                # runways over the aeroway layer
ACROSS_MAX = 40.0
ALONG_MAX = 4600.0            # runways up to 4.2 km
DUP_SHARE = CFG["markings"].get("dedupe", 0.0)   # see "overlapping carriageways" in main(); 0: off
ALONG_WRAP = 3600.0           # along restarts at a multiple of every dash period (6, 10, 15 m)
CHUNK = 400.0
MIN_PIECE = 20.0              # a piece between two junctions shorter than this is junction interior
CROSS_L = 6.0                 # zebra (4 m) plus the stop line behind it
SIMPLIFY = 0.5

MK = CFG["markings"]
BIG = set(MK["big"])
PARKING_LANES = CFG["roads"].get("parking_lanes", {})   # highway -> parking lanes within the width
ZEBRA = set(MK["zebra"])
# sidewalk width (m) each side for two-way ground-level roads; links and motorways have none
SIDEWALK_W = MK["sidewalk_w"]
MEDIAN_W = MK["median_w"]
RIGHT = CFG["drive"] == "right"     # driving side
# UK-style options (all off by default; see defaults.toml [markings])
WARN = float(MK.get("warning", 0.0))                  # m of warning line before a junction
KERB_LINES = MK.get("kerb_lines", {})                 # highway -> "yellow" | "red" along both kerbs
KERB_MOUTHS = MK.get("kerb_mouths", {})               # highway -> colour within WARN m of a junction only
RED_REFS = set(MK.get("red_refs", []))                # OSM ref values that make a road a red route
BUS = bool(MK.get("bus_lanes", False))
BUS_RED = float(MK.get("bus_red", 0.5))
CYCLE = bool(MK.get("cycle_lanes", False))
JUNCTIONS = MK.get("junctions", "zebra")              # "zebra" | "signals"
SIGNAL_R = float(MK.get("signal_reach", 25.0))
ZEBRAS = bool(MK.get("zebras", False))
ZIGZAG = float(MK.get("zigzag", 12.0))
BEACONS = bool(MK.get("beacons", ZEBRAS))
SIGNAL_X = bool(MK.get("signal_crossings", False))    # signal-controlled crossings between junctions
# [markings] scrambles (opt-in, Tokyo M5; {} off): diagonal crossings over a junction box (Shibuya's scramble), as zebra
# strips (type ZEBRA_T, along 20 at the crossing's middle): name = {lines = [[[lon, lat], [lon, lat]], ...] (each
# crossing from kerb to kerb), w = the crossing's width (m; city.json markings.zebra.mid.half = w / 2 draws its bars),
# big = true (the asphalt of the big roads)}
SCRAMBLES = MK.get("scrambles", {})
KERB_CODE = {None: 0, "yellow": 1, "red": 2}
# Berlin options (M5; all off by default): cobbled carriageways, a second sidewalk style per highway class (the share
# of its ways), tram tracks
# [markings] promenades (names, off by default): a dual carriageway's two one-way ways of these names have the
# space between them as one promenade: each way's sidewalk on its twin's side reaches halfway across (to the middle
# between the two ways) in sidewalk style 2 (city.json markings.sidewalk.promenade: a water-bound gravel walk with
# granite edging; Berlin's Unter den Linden: the Mittelpromenade, which read as two grey slab sidewalks)
PROMENADES = set(MK.get("promenades", []))
# [markings] sidewalk_style_names (off by default): streets whose every way takes sidewalk style 1 (Berlin: the
# Gehweg along Oranienstrasse, whose many short ways each drew it by chance)
SIDE_STYLE_NAMES = set(MK.get("sidewalk_style_names", []))
SETTS = set(MK.get("setts", []))                      # OSM surface values drawn as setts (e.g. sett, cobblestone)
SIDE_STYLE = MK.get("sidewalk_style", {})             # highway -> share of its ways with sidewalk style 1
TRAMS = MK.get("trams", False)                        # false, or {setts: share of embedded track laid in setts,
                                                      # road_w, off_w: strip widths on and off the carriageway}
TRAM_Y = 0.03                                         # over the lane strips
RANK = {"motorway": 6, "trunk": 5, "primary": 4, "secondary": 3, "tertiary": 2, "unclassified": 1, "residential": 1,
        "living_street": 0, "road": 1}
NODES_CACHE = DATA / "markings_nodes.json"


def osm_tags() -> dict:
    """OSM way id -> tags, from 05b_roads.py's cached Overpass answer (roads.gpkg keeps only a few)."""
    res = json.loads((RAW / "osm_roads.json").read_text())
    return {e["id"]: e.get("tags", {}) for e in res["elements"] if e["type"] == "way"}


def lane_code(tags: dict, width: float, oneway: bool, hw: str) -> int:
    """b channel: lanes per direction (one-way: all lanes) + 16 one-way + 32 big road + 64 motorway.
    Lanes 0 means a road too narrow for lane lines."""
    lanes = number(tags.get("lanes"))
    base = hw.removesuffix("_link")
    # the kerb-to-kerb width holds the parking lanes too ([roads] parking_lanes): moving lanes are what is left
    park = PARKING_LANES.get(hw, 0) * 2.4
    if any(tags.get(k) in ("no", "no_parking", "no_stopping") for k in ("parking:both", "parking:lane:both")):
        park = 0.0
    moving = max(width - park, 3.0)
    if oneway:
        n = int(lanes) if lanes and 1 <= lanes <= 15 else max(1, round(moving / 3.5))
    else:
        total = int(lanes) if lanes and 2 <= lanes <= 15 else (max(2, round(moving / 3.5)) if width >= 6 else 0)
        n = total // 2
    return min(n, 15) + 16 * oneway + 32 * (base in BIG or base == "motorway") + 64 * (base == "motorway")


def number(v):
    try:
        return float(str(v).replace(",", ".").split(";")[0].split()[0])
    except (ValueError, IndexError, AttributeError):
        return None


def sidewalks(tags: dict, hw: str, oneway: bool, elevated: bool):
    """(left, right, median) widths in metres; the median is on the left (driving on the right) or the right."""
    if elevated or hw.endswith("_link"):
        return 0.0, 0.0, 0.0
    w = SIDEWALK_W.get(hw, 0.0)
    tag = tags.get("sidewalk")
    left = right = w
    if tag == "no" or tag == "none":
        left = right = 0.0
    elif tag == "left":
        right = 0.0
    elif tag == "right":
        left = 0.0
    median = 0.0
    if oneway and hw in MEDIAN_W and tag not in (("left", "both") if RIGHT else ("right", "both")):
        # a one-way major road is usually one carriageway of a dual road: its inner side (left when driving
        # on the right) is the median
        if RIGHT:
            median, left = MEDIAN_W[hw], 0.0
        else:
            median, right = MEDIAN_W[hw], 0.0
    return left, right, median


def bus_sides(t: dict, oneway: bool) -> tuple:
    """(left kerb, right kerb) bus lanes, left/right of the way's direction (across > 0 / < 0), from OSM's
    busway, lanes:bus and bus:lanes tags. A lane in the direction of travel lies along the nearside kerb."""
    near_fwd = (False, True) if RIGHT else (True, False)          # (left, right)
    near_bwd = (near_fwd[1], near_fwd[0])
    left = right = False

    def add(side):
        nonlocal left, right
        left, right = left or side[0], right or side[1]

    for k in ("busway", "busway:both"):
        if t.get(k) in ("lane", "opposite_lane"):
            add(near_fwd if oneway else (True, True))
    if t.get("busway:left") in ("lane", "opposite_lane"):
        add((True, False))
    if t.get("busway:right") in ("lane", "opposite_lane"):
        add((False, True))
    if (number(t.get("lanes:bus")) or 0) >= 1 or (number(t.get("lanes:psv")) or 0) >= 1:
        add(near_fwd if oneway else (True, True))
    if (number(t.get("lanes:bus:forward")) or 0) >= 1 or (number(t.get("lanes:psv:forward")) or 0) >= 1:
        add(near_fwd)
    if (number(t.get("lanes:bus:backward")) or 0) >= 1 or (number(t.get("lanes:psv:backward")) or 0) >= 1:
        add(near_bwd)
    # bus:lanes lists the lanes left to right in the way's direction (forward: its own lanes)
    for k, side_of in (("bus:lanes", None), ("psv:lanes", None), ("bus:lanes:forward", near_fwd),
                       ("psv:lanes:forward", near_fwd), ("bus:lanes:backward", near_bwd), ("psv:lanes:backward", near_bwd)):
        v = t.get(k)
        if not v:
            continue
        ls = v.split("|")
        on = [x in ("designated", "yes") for x in ls]
        if not any(on):
            continue
        if side_of is not None:
            add(side_of)
        else:
            add((on[0], on[-1]))
    return left, right


def cycle_lane(t: dict) -> bool:
    return any(t.get(k) in ("lane", "opposite_lane") for k in ("cycleway", "cycleway:both", "cycleway:left", "cycleway:right"))


def kerb_kind(t: dict, base: str, mouth: bool) -> int:
    """Kerb lines' code: 0 none, 1 double yellow, 2 double red."""
    refs = {r.strip() for r in str(t.get("ref", "")).split(";")}
    if RED_REFS and refs & RED_REFS:
        return 2
    colour = KERB_LINES.get(base) or (KERB_MOUTHS.get(base) if mouth else None)
    if any(t.get(k) in ("no_stopping",) for k in ("parking:both", "parking:lane:both")) and colour is None and mouth and KERB_MOUTHS:
        colour = "yellow"
    return KERB_CODE.get(colour, 0)


def fetch_nodes(bbox_utm) -> dict:
    """Traffic signals and zebra crossings (OSM nodes) in the area, cached in the data folder."""
    if NODES_CACHE.exists():
        return json.loads(NODES_CACHE.read_text())
    s, w, n, e = gpd.GeoSeries([box(*bbox_utm)], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    res = overpass(f"""
        [out:json][timeout:900][bbox:{s},{w},{n},{e}];
        (
          node["highway"="traffic_signals"];
          node["crossing"="traffic_signals"];
          node["crossing"="zebra"];
          node["crossing_ref"="zebra"];
          node["crossing:markings"="zebra"];
        );
        out;
    """)
    NODES_CACHE.write_text(json.dumps(res))
    return res


def node_points(res: dict):
    """(signals, zebras, signal-controlled crossings) as UTM point arrays."""
    from pyproj import Transformer
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    sig, zeb, pel = [], [], []
    for el in res["elements"]:
        t = el.get("tags", {})
        x, y = to.transform(el["lon"], el["lat"])
        if t.get("highway") == "traffic_signals" or t.get("crossing") == "traffic_signals":
            sig.append((x, y))
        if t.get("crossing") == "traffic_signals" or t.get("crossing_ref") in ("pelican", "puffin", "toucan", "pegasus"):
            pel.append((x, y))
        if (t.get("crossing") == "zebra" or t.get("crossing_ref") == "zebra" or t.get("crossing:markings") == "zebra") \
                and t.get("crossing") not in ("traffic_signals", "unmarked", "no"):
            zeb.append((x, y))
    return tuple(np.asarray(a, float).reshape(-1, 2) for a in (sig, zeb, pel))


def beacon(xz, y):
    """A Belisha beacon at scene (x, z), its foot at height y: a square pole 2.75 m tall and an eight-sided
    double cone of 0.17 m radius above it. Returns positions, normals, along (m above the foot), triangles."""
    pos, nrm, al, tri = [], [], [], []

    def quad_face(pts, n, h):
        k = len(pos)
        pos.extend(pts); nrm.extend([n] * len(pts)); al.extend(h)
        a, b, c = np.asarray(pts[0]), np.asarray(pts[1]), np.asarray(pts[2])
        for t in ([k, k + 1, k + 2], [k, k + 2, k + 3])[: len(pts) - 2]:
            p0, p1, p2 = (np.asarray(pos[i]) for i in t)
            tri.append(t if np.dot(np.cross(p1 - p0, p2 - p0), n) > 0 else [t[0], t[2], t[1]])

    x, z, r, top = xz[0], xz[1], 0.06, 2.75
    for dx, dz in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        tx, tz = -dz, dx                          # along the face
        cx, cz = x + dx * r, z + dz * r
        quad_face([(cx - tx * r, y, cz - tz * r), (cx + tx * r, y, cz + tz * r), (cx + tx * r, y + top, cz + tz * r),
                   (cx - tx * r, y + top, cz - tz * r)], (dx, 0.0, dz), [0, 0, top, top])
    gr, gc = 0.17, top + 0.17
    for k in range(8):
        a0, a1 = 2 * np.pi * k / 8, 2 * np.pi * (k + 1) / 8
        p0 = (x + gr * np.cos(a0), y + gc, z + gr * np.sin(a0))
        p1 = (x + gr * np.cos(a1), y + gc, z + gr * np.sin(a1))
        am = (a0 + a1) / 2
        for sgn in (1, -1):
            apex = (x, y + gc + sgn * gr, z)
            n = np.array([np.cos(am), sgn * 1.0, np.sin(am)]) / np.sqrt(2)
            quad_face([p0, p1, apex], tuple(n), [gc, gc, gc + sgn * gr])
    return np.asarray(pos), np.asarray(nrm), np.asarray(al), np.asarray(tri)


# ---------------------------------------------------------------- strips

class Mesh:
    """Accumulates vertices (scene x, y, z), (across, along), RGBA bytes, whether y is above the ground (or
    absolute: decks), and triangles."""

    def __init__(self):
        self.pos, self.uv, self.col, self.rel, self.idx, self.n = [], [], [], [], [], 0
        self.nrm = []

    def solid(self, pos, nrm, uv, rgba, tri):
        """Solid geometry at absolute heights (beacons): positions, normals, (across, along), triangles."""
        self.pos.append(pos)
        self.nrm.append(nrm)
        self.uv.append(uv)
        self.col.append(np.tile(np.asarray(rgba, np.uint8), (len(pos), 1)))
        self.rel.append(np.zeros(len(pos), bool))
        self.idx.append(tri + self.n)
        self.n += len(pos)

    def strip(self, p, y, along, a0, a1, rgba, ground=True):
        """A strip between offsets a0 < a1 (metres left of the polyline p, scene xz) at heights y, over the
        ground (or absolute heights)."""
        if len(p) < 2:
            return
        d = np.diff(p, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True).clip(1e-9)
        # scene x = east, z = south: left of the direction (dx, dz) is (dz, -dx)
        seg_n = np.stack([d[:, 1], -d[:, 0]], 1)
        vn = np.zeros_like(p)
        vn[:-1] += seg_n
        vn[1:] += seg_n
        vn /= np.linalg.norm(vn, axis=1, keepdims=True).clip(1e-9)
        cos = np.ones(len(p))
        cos[1:-1] = (vn[1:-1] * seg_n[:-1]).sum(1)
        vn /= np.clip(cos, 0.5, 1)[:, None]                  # mitre, capped at 2x
        k = len(p)
        for a in (a0, a1):
            xz = p + vn * a
            self.pos.append(np.column_stack([xz[:, 0], y, xz[:, 1]]))
            self.uv.append(np.column_stack([np.full(k, a), along]))
        self.col.append(np.tile(np.asarray(rgba, np.uint8), (2 * k, 1)))
        self.rel.append(np.full(2 * k, ground))
        self.nrm.append(np.tile([0.0, 1.0, 0.0], (2 * k, 1)))
        i = np.arange(k - 1) + self.n
        # a0 row then a1 row; a1 is further left. Triangles face up (CCW seen from +y)
        t = np.stack([np.stack([i, i + 1, i + k + 1], 1), np.stack([i, i + k + 1, i + k], 1)], 1).reshape(-1, 3)
        self.idx.append(t)
        self.n += 2 * k

    def arrays(self, terrain: Terrain):
        pos, uv, col = np.concatenate(self.pos), np.concatenate(self.uv), np.concatenate(self.col)
        rel, idx = np.concatenate(self.rel), np.concatenate(self.idx)
        nrm = np.concatenate(self.nrm)
        # strips over the ground: cut along the TIN, heights and texture coordinates carried over
        on = rel[idx].all(1)
        d = terrain.drape_triangles(pos[:, [0, 2]], idx[on], tol=DRAPE_TOL) if on.any() else None
        if d is not None:
            xz, src, bary, gy, gn, t2 = d
            sv = idx[on][src]
            y = (bary * pos[sv, 1]).sum(1) + gy
            deck = np.flatnonzero(~rel)
            remap = np.full(len(pos), -1)
            remap[deck] = np.arange(len(deck))
            idx = np.concatenate([remap[idx[~on]], t2 + len(deck)])
            pos = np.concatenate([pos[deck], np.column_stack([xz[:, 0], y, xz[:, 1]])])
            uv = np.concatenate([uv[deck], (bary[:, :, None] * uv[sv]).sum(1)])
            col = np.concatenate([col[deck], col[sv[:, 0]]])
            nrm = np.concatenate([nrm[deck], gn])
        m = weld({"pos": pos, "nrm": nrm, "uv": uv, "col": col, "idx": idx})
        pos, nrm, uv, col, idx = m["pos"], m["nrm"], m["uv"], m["col"], m["idx"]
        # make every triangle face up whatever the strip's direction
        a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
        up = (c[:, 0] - a[:, 0]) * (b[:, 2] - a[:, 2]) - (b[:, 0] - a[:, 0]) * (c[:, 2] - a[:, 2])
        flip = (up < 0) & (col[idx[:, 0], 0] != BEACON)       # (beacons are wound outwards already)
        idx[flip] = idx[flip][:, [0, 2, 1]]
        return {"pos": pos, "nrm": nrm, "uv": uv, "col": col, "idx": idx.reshape(-1)}


def cut(c, s, a, b):
    """Part of polyline c (N x k) with cumulative distances s between distances a < b."""
    i0, i1 = np.searchsorted(s, a, "right"), np.searchsorted(s, b, "left")
    pa = np.array([np.interp(a, s, c[:, j]) for j in range(c.shape[1])])
    pb = np.array([np.interp(b, s, c[:, j]) for j in range(c.shape[1])])
    pts = np.vstack([pa, c[i0:i1], pb])
    return pts, np.r_[a, s[i0:i1], b]


def wet_area():
    """Sea (the ground area outside the land polygons) plus rivers, lakes and ponds, prepared for
    point tests: sidewalks and medians are not drawn over it."""
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    land = unary_union(gpd.read_file(DATA / "ground.gpkg", layer="land").geometry.values)
    water = unary_union(gpd.read_file(DATA / "ground.gpkg", layer="water").geometry.values)
    wet = unary_union([area.difference(land), water])
    shapely.prepare(wet)
    return wet


def dry_runs(c, s, lo, hi, offset, wet, step=4.0):
    """Stretches [a, b] of the piece between distances lo..hi whose strip, `offset` metres left of
    the polyline, lies on land; sampled every `step` metres."""
    if hi - lo < 1:
        return []
    t = np.r_[np.arange(lo, hi, step), hi]
    x, y = np.interp(t, s, c[:, 0]), np.interp(t, s, c[:, 1])
    seg = np.clip(np.searchsorted(s, t, "right") - 1, 0, len(s) - 2)
    d = c[seg + 1, :2] - c[seg, :2]
    d /= np.linalg.norm(d, axis=1, keepdims=True).clip(1e-9)
    dry = ~shapely.contains_xy(wet, x - d[:, 1] * offset, y + d[:, 0] * offset)   # left of (dx, dy) is (-dy, dx)
    runs, start = [], None
    for k, ok in enumerate(dry):
        if ok and start is None:
            start = t[k]
        if (not ok or k == len(t) - 1) and start is not None:
            end = t[k] if ok else t[max(k - 1, 0)]
            if end - start >= 2:
                runs.append((start, end))
            start = None
    return runs


# ---------------------------------------------------------------- main

def main():
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)
    terrain = Terrain()
    tags = osm_tags()
    wet = wet_area()
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    trams = ways[(ways.kind == "rail") & (ways.highway == "tram")].reset_index(drop=True)
    ways = ways[ways.kind != "rail"].reset_index(drop=True)

    # per way: coordinates (3D, z = deck height or 0), one-way (reversed if drawn against traffic)
    recs = []
    for r in ways.itertuples():
        t = tags.get(r.osm_id, {})
        c = np.asarray(r.geometry.coords, float)
        if c.shape[1] == 2:
            c = np.column_stack([c, np.zeros(len(c))])
        ow = t.get("oneway")
        oneway = ow in ("yes", "1", "-1", "true") or (ow is None and (r.highway.startswith("motorway")
                                                                       or t.get("junction") == "roundabout"))
        if ow == "-1":
            c = c[::-1]
        rec = {"c": c, "hw": r.highway, "kind": r.kind, "w": float(r.width), "elev": bool(r.elevated),
               "tags": t, "oneway": oneway, "bus": (False, False)}
        if BUS:
            # (tags and the oneway direction are the way's as drawn: a reversed way swaps its sides)
            bl, br = bus_sides(t, oneway and ow != "-1")
            rec["bus"] = (br, bl) if ow == "-1" else (bl, br)
        recs.append(rec)
    signals = zebras = pelicans = np.zeros((0, 2))
    if JUNCTIONS == "signals" or ZEBRAS or SIGNAL_X:
        signals, zebras, pelicans = node_points(fetch_nodes((x0, y0, x1, y1)))
        print(f"OSM nodes: {len(signals)} traffic signals, {len(zebras)} zebra crossings, {len(pelicans)} signal crossings")
    if not SIGNAL_X:
        pelicans = np.zeros((0, 2))
    if not ZEBRAS:
        zebras = np.zeros((0, 2))
    # zebras and signal crossings in one tree: index < n_zeb a zebra
    n_zeb = len(zebras)
    zebras = np.vstack([zebras, pelicans])
    sig_tree = shapely.STRtree(shapely.points(signals)) if len(signals) else None
    zeb_pts = shapely.points(zebras) if len(zebras) else None
    zeb_tree = shapely.STRtree(zeb_pts) if zeb_pts is not None else None
    for rec in recs:
        rec["sw"] = sidewalks(rec["tags"], rec["hw"], rec["oneway"], rec["elev"])
        rec["reach"] = rec["w"] / 2 + max(rec["sw"][0], rec["sw"][1])

    # junctions: node -> segment count and the ways touching it
    key = lambda p: (round(p[0], 2), round(p[1], 2))
    degree, touching = defaultdict(int), defaultdict(set)
    for i, rec in enumerate(recs):
        for j, p in enumerate(rec["c"]):
            k = key(p)
            degree[k] += 1 if j in (0, len(rec["c"]) - 1) else 2
            touching[k].add(i)

    meshes = defaultdict(Mesh)
    rng = np.random.default_rng(11)
    stats = defaultdict(int)

    def tile_of(xy):
        return int(np.floor((xy[0] - origin[0]) / TILE)), int(np.floor((xy[1] - origin[1]) / TILE))

    def emit(pts, s, along0, a0, a1, rgba, ylift, ground=True):
        """Chunk a 3D polyline piece and add strips to the tiles of the chunk midpoints."""
        total = s[-1] - s[0]
        n = max(1, int(np.ceil(total / CHUNK)))
        for q in range(n):
            ca, cb = s[0] + total * q / n, s[0] + total * (q + 1) / n
            cp, cs = cut(pts, s, ca, cb)
            if len(cp) < 2:
                continue
            start = (along0 + ca - s[0]) % ALONG_WRAP
            along = start + (cs - ca)
            xz = to_scene(cp[:, :2], origin)
            y = cp[:, 2] + ylift
            meshes[tile_of(cp[len(cp) // 2, :2])].strip(xz, y, along, a0, a1, rgba, ground)

    # overlapping carriageways: a ground road way lying mostly (DUP_SHARE of its length) on the carriageway of a
    # wider (or as wide, earlier) one is painted by that one alone (OSM draws some
    # dual carriageways twice, or a road and its contre-allée over each other: doubled lane dashes on the Voie
    # Georges-Pompidou and the Avenue de New York)
    lines = [LineString(r["c"][:, :2]) if len(r["c"]) >= 2 else None for r in recs]
    road = [] if not DUP_SHARE else [i for i, r in enumerate(recs) if r["kind"] in ("major", "minor") and not r["elev"] and lines[i] is not None
            and lines[i].length > 0]
    tree = shapely.STRtree([lines[i] for i in road])
    for n_i, i in enumerate(road):
        li, ri = lines[i], recs[i]
        for n_j in tree.query(li.buffer(ri["w"])):
            j = road[n_j]
            rj = recs[j]
            if j == i or rj.get("dup") or rj["w"] < ri["w"] or (rj["w"] == ri["w"] and j > i):
                continue
            on = li.intersection(lines[j].buffer(max(rj["w"] / 2 - 0.5, 1.0), cap_style="flat"))
            if on.length >= DUP_SHARE * li.length:
                ri["dup"] = True
                stats["overlapping ways unpainted"] += 1
                break

    for i, rec in enumerate(recs):
        hw, kind, elev = rec["hw"], rec["kind"], rec["elev"]
        base = hw.removesuffix("_link")
        plaza = hw == "pedestrian"
        if (kind == "service" and not plaza) or rec.get("dup"):
            continue
        c = rec["c"]
        # split at junctions with other streets (service driveways don't split a road)
        cut_at = [0]
        for j in range(1, len(c) - 1):
            k = key(c[j])
            if degree[k] >= 3 and any(recs[o]["kind"] in ("major", "minor") for o in touching[k] if o != i):
                cut_at.append(j)
        cut_at.append(len(c) - 1)
        half = rec["w"] / 2
        lcode = lane_code(rec["tags"], rec["w"], rec["oneway"], hw)
        if SETTS and rec["tags"].get("surface") in SETTS:
            lcode += 128
            stats["sett ways"] += 1
        side_style = int(bool(SIDE_STYLE) and rng.random() < SIDE_STYLE.get(base, 0.0))
        if SIDE_STYLE_NAMES and rec["tags"].get("name") in SIDE_STYLE_NAMES:
            side_style = 1                # ([markings] sidewalk_style_names: the whole street, not by chance per way)
        prom = None                       # (side: +1 left / -1 right, the promenade's half-gap) on a promenade way
        if PROMENADES and rec["tags"].get("name") in PROMENADES and rec["oneway"] and lines[i] is not None:
            li = lines[i]
            mid = li.interpolate(0.5, normalized=True)
            best = None
            a_ = li.interpolate(max(li.project(mid) - 1, 0)); b_ = li.interpolate(min(li.project(mid) + 1, li.length))
            tx, ty = b_.x - a_.x, b_.y - a_.y
            for j, rj in enumerate(recs):
                if j == i or rj["tags"].get("name") != rec["tags"].get("name") or lines[j] is None \
                        or not rj["oneway"] or rj["kind"] != rec["kind"]:
                    continue
                # (the twin runs the other way: not a parallel service lane of the same name)
                pj = lines[j].project(mid)
                c_ = lines[j].interpolate(max(pj - 1, 0)); e_ = lines[j].interpolate(min(pj + 1, lines[j].length))
                if (e_.x - c_.x) * tx + (e_.y - c_.y) * ty > -0.5 * np.hypot(tx, ty) * np.hypot(e_.x - c_.x, e_.y - c_.y):
                    continue
                d_ = lines[j].distance(mid)
                if 10 < d_ < 60 and (best is None or d_ < best[0]):
                    best = (d_, j)
            if best:
                q = shapely.ops.nearest_points(mid, lines[best[1]])[1]
                left = (-ty) * (q.x - mid.x) + tx * (q.y - mid.y) > 0
                prom = (1 if left else -1, best[0] / 2)
                stats["promenade ways"] += 1
        yellow_left = int(RIGHT and rec["oneway"] and base in ("motorway", "trunk", "primary", "secondary")
                          and not hw.endswith("_link"))
        # bus and cycle lanes, kerb lines (lanes flags, see the module docstring)
        bus_l, bus_r = rec["bus"]
        lane_flags = yellow_left + 2 * bus_l + 4 * bus_r + 128 * (CYCLE and cycle_lane(rec["tags"]))
        if bus_l or bus_r:
            lane_flags += 8 * (rng.random() < BUS_RED)
            stats["bus lane ways"] += 1
        kerb_main = 16 * kerb_kind(rec["tags"], base, False) if not elev else 0
        kerb_mouth = 16 * kerb_kind(rec["tags"], base, True) if not elev else 0
        g = min(255, round(half * 4))
        swl, swr, med = rec["sw"]
        if prom:                          # the promenade side's sidewalk reaches the middle (06b PROMENADES)
            if prom[0] > 0:
                swl = max(swl, prom[1] - half + 0.3)
            else:
                swr = max(swr, prom[1] - half + 0.3)

        for a, b in zip(cut_at[:-1], cut_at[1:]):
            pc = c[a:b + 1]
            seg = np.linalg.norm(np.diff(pc[:, :2], axis=0), axis=1)
            keep = np.r_[True, seg > 0.05]
            pc = pc[keep]
            if not elev and len(pc) > 2:          # ground pieces: drop OSM's surplus nodes (ends are kept)
                pc = np.asarray(LineString(pc[:, :2]).simplify(SIMPLIFY).coords)
                pc = np.column_stack([pc, np.zeros(len(pc))])
            if len(pc) < 2:
                continue
            s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pc[:, :2], axis=0), axis=1))]
            L = s[-1]

            def clearance(p):
                """(cut back, crossing there, the junction's marking: 0 zebra, 1 give-way, 2 signals, 3 none)"""
                k = key(p)
                if degree[k] < 3:
                    return 0.0, False, 0
                others = [recs[o] for o in touching[k] if o != i and recs[o]["kind"] in ("major", "minor")]
                if not others:
                    return 0.0, False, 0
                zebra = any(not o["hw"].endswith("_link") and o["hw"] != "motorway" and not o["elev"]
                            for o in others)
                style = 0
                if JUNCTIONS == "signals":
                    near = sig_tree is not None and len(sig_tree.query(shapely.Point(p[:2]), predicate="dwithin",
                                                                       distance=SIGNAL_R))
                    mine = RANK.get(base, 1)
                    top = max(RANK.get(o["hw"].removesuffix("_link"), 1) for o in others)
                    style = 2 if near else 1 if mine < top or (mine == top and mine <= 1 and rec["oneway"] is False
                                                                 and len(others) >= 2 and rng.random() < 0.5) else 3
                return max(o["reach"] for o in others) + 0.5, zebra, style

            ts, zs, st_s = clearance(pc[0])
            te, ze, st_e = clearance(pc[-1])
            usable = L - ts - te
            if usable < 3 or (ts > 0 and te > 0 and usable < MIN_PIECE):
                stats["dropped"] += 1
                continue
            along0 = rng.uniform(0, 600)
            # short pieces too (Times Square's avenues are split every few dozen metres): a crossing at each
            # junction end as long as some lane is left between them
            can_zebra = base in ZEBRA and not hw.endswith("_link") and not elev and half >= 2.5
            zs, ze = zs and can_zebra, ze and can_zebra
            if zs and ze and usable < CROSS_L * 2 + 1:      # no room for both: the start's only
                ze = False
            if (zs or ze) and usable < CROSS_L + 2:
                zs = ze = False
            la, lb = ts + CROSS_L * zs, L - te - CROSS_L * ze
            ylift = ROAD_Y + OVER_Y
            if plaza:
                emit(pc, s, along0, -half, half, (PLAZA, g, 0, 0), ylift, not elev)
                continue
            # zebra crossings (OSM nodes) on the piece: the lane strip leaves a gap for each
            def put_beacons(sc, _):
                """A Belisha beacon on each pavement at a zebra's ends (diagonally across)."""
                for ds, side in ((1.9, 1), (-1.9, -1)):
                    sp = min(max(sc + ds, 0), L)
                    px, py = np.interp(sp, s, pc[:, 0]), np.interp(sp, s, pc[:, 1])
                    seg_i = min(np.searchsorted(s, sp, "right") - 1, len(s) - 2)
                    dv = pc[seg_i + 1, :2] - pc[seg_i, :2]
                    dv = dv / max(np.linalg.norm(dv), 1e-9)
                    off = half + 0.55
                    bx, by = px - dv[1] * off * side, py + dv[0] * off * side   # left of (dx, dy) is (-dy, dx)
                    bxz = to_scene(np.array([[bx, by]]), origin)[0]
                    gy = float(terrain.height(np.array([bxz[0]]), np.array([bxz[1]]))[0]) + ROAD_Y + SIDE_Y
                    bp, bn, bal, bt = beacon(bxz, gy)
                    uvb = np.column_stack([np.zeros(len(bp)), bal])
                    meshes[tile_of((bx, by))].solid(bp, bn, uvb, (BEACON, 0, 0, 0), bt)
                    stats["beacons"] += 1

            gaps, arm_zebras = [], []
            if (ZEBRAS or SIGNAL_X) and zeb_tree is not None and not elev and base in ZEBRA and not hw.endswith("_link") and half >= 2.5:
                line_p = LineString(pc[:, :2])
                for zi in sorted(zeb_tree.query(line_p, predicate="dwithin", distance=1.5)):
                    sc = line_p.project(zeb_pts[zi])
                    sigx = int(zi >= n_zeb)
                    # (a zebra at a junction's arm, in its crossing strip: that arm is drawn as a zebra; a signal
                    # crossing there is the arm's own signal marking)
                    if sigx and ((zs and sc <= la + 2.5) or (ze and sc >= lb - 2.5) or sc < la + 3.5 or sc > lb - 3.5):
                        continue
                    if (zs or ze) and JUNCTIONS != "zebra":
                        if zs and ts - 2 <= sc <= la + 2.5:
                            st_s, arm_zebras = 0, arm_zebras + [(sc, 1)]
                            continue
                        if ze and lb - 2.5 <= sc <= L - te + 2:
                            st_e, arm_zebras = 0, arm_zebras + [(sc, -1)]
                            continue
                    # (signal crossings: OSM maps a node per carriageway or per side; one crossing within 10 m)
                    if la + 2.5 < sc < lb - 2.5 and all(abs(sc - g0) > 10 for g0, _, _, _ in gaps):
                        # zig-zags in whole 2 m marks from just past the give-way (or stop) line, 3 m from the middle
                        a_, b_ = max(la, sc - 3 - ZIGZAG), min(lb, sc + 3 + ZIGZAG)
                        gaps.append((sc, a_, b_, sigx))
                gaps.sort()
                # neighbours' zig-zags shortened to meet halfway
                for q in range(1, len(gaps)):
                    (s0, a0_, b0_, x0_), (s1, a1_, b1_, x1_) = gaps[q - 1], gaps[q]
                    if b0_ > a1_:
                        m_ = (s0 + s1) / 2
                        gaps[q - 1], gaps[q] = (s0, a0_, m_, x0_), (s1, m_, b1_, x1_)
            ranges, at = [], la
            for sc, a_, b_, _ in gaps:
                if a_ > at:
                    ranges.append((at, a_))
                at = b_
            if lb > at:
                ranges.append((at, lb))
            # the warning line (and kerb lines on junction mouths) within WARN m of a junction
            cuts = sorted({x for x in ((la + WARN) if WARN and ts > 0 else None, (lb - WARN) if WARN and te > 0 else None)
                           if x is not None})
            for ra, rb in ranges:
                pts_ = [ra] + [x for x in cuts if ra < x < rb] + [rb]
                for xa, xb in zip(pts_[:-1], pts_[1:]):
                    if xb - xa < 0.05:
                        continue
                    warn = WARN and ((ts > 0 and xb <= la + WARN + 1e-6) or (te > 0 and xa >= lb - WARN - 1e-6))
                    flags = lane_flags + (kerb_mouth if warn else kerb_main) + 64 * bool(warn)
                    emit(*cut(pc, s, xa, xb), along0 + xa, -half, half, (LANES, g, lcode, flags), ylift, not elev)
            stats["lanes"] += 1
            for sc, a_, b_, sigx in gaps:
                pts, ss = cut(pc, s, a_, b_)
                xz = to_scene(pts[:, :2], origin)
                meshes[tile_of(pts[len(pts) // 2, :2])].strip(xz, pts[:, 2] + ylift, 20 + ss - sc, -half, half,
                                                              (ZEBRA_T, g, lcode, sigx), True)
                stats["signal crossings" if sigx else "zebras"] += 1
                if BEACONS and not sigx:
                    put_beacons(sc, 0)
            for sgn in sorted({sg for _, sg in arm_zebras}):
                stats["zebras at junctions"] += 1
                if BEACONS:
                    # the arm's zebra lies 0.4-4 m from the junction box
                    put_beacons((ts + 2.2) if sgn > 0 else (L - te - 2.2), 0)

            # zebra crossings: along runs from the junction outwards (0 at the junction side)
            for at_start, on in ((True, zs), (False, ze)):
                if not on:
                    continue
                if at_start:
                    pts, ss = cut(pc, s, ts, ts + CROSS_L)
                    along = ss - ts
                    # traffic towards the start junction drives against the way: on its left (across > 0)
                    # when driving on the right
                    stop = 0 if rec["oneway"] else 1 if RIGHT else 2
                else:
                    pts, ss = cut(pc, s, L - te - CROSS_L, L - te)
                    along = (L - te) - ss
                    stop = 3 if rec["oneway"] else 2 if RIGHT else 1
                style = st_s if at_start else st_e
                xz = to_scene(pts[:, :2], origin)
                meshes[tile_of(pts[len(pts) // 2, :2])].strip(xz, pts[:, 2] + ylift, along, -half, half,
                                                              (CROSSING, g, lcode, stop + 4 * style + (kerb_mouth if WARN else kerb_main)), not elev)
                stats[f"crossings {['zebra', 'give-way', 'signals', 'plain'][style]}"] += 1
                stats["crossings"] += 1
            # sidewalks and medians run the whole piece up to the neighbouring roads' edges
            sy = ROAD_Y + SIDE_Y
            if not elev:
                # each strip only where it lies on land: roads along the shore or over a culvert keep
                # their sidewalk on the dry side
                mside = (half, half + med) if RIGHT else (-half - med, -half)
                for a0, a1, width, code in ((half, half + swl, swl, SIDEWALK), (-half - swr, -half, swr, SIDEWALK),
                                            (*mside, med, MEDIAN)):
                    if width <= 0:
                        continue
                    for ra, rb in dry_runs(pc, s, ts, L - te, (a0 + a1) / 2, wet):
                        st_ = side_style if code == SIDEWALK else 0
                        if prom and code == SIDEWALK and (a0 >= 0) == (prom[0] > 0):
                            st_ = 2
                        emit(*cut(pc, s, ra, rb), along0 + ra, a0, a1,
                             (code, g, st_, round(width * 10)), sy)
                        if code == SIDEWALK:
                            stats["sidewalk km"] += (rb - ra) / 1000

    if TRAMS:
        tram_tracks(trams, recs, tags, emit, stats)
    if SCRAMBLES:
        for strip_ in scramble_strips(SCRAMBLES):
            xz = to_scene(strip_["p"], origin)
            meshes[tile_of(strip_["p"].mean(0))].strip(xz, np.full(2, ROAD_Y + OVER_Y + strip_["dy"]), strip_["along"],
                                                       -strip_["half"], strip_["half"], strip_["rgba"], True)
            stats["scramble crossings"] += 1

    # runways: one rectangle per runway, along its long axis. Pieces of one runway (parallel and touching) are
    # merged; crossing runways are not (LaGuardia's 4/22 and 13/31: their union's rectangle covered the bay)
    aero = gpd.read_file(DATA / "ground.gpkg", layer="aeroway")
    pieces = [g for geom in aero[aero.kind == "runway"].geometry for g in getattr(geom, "geoms", [geom]) if g.area > 100]

    def heading(g):
        r = np.asarray(g.minimum_rotated_rectangle.exterior.coords)[:4]
        e = max((r[1] - r[0], r[2] - r[1]), key=np.linalg.norm)
        return np.degrees(np.arctan2(e[0], e[1])) % 180

    groups = []
    for g in pieces:
        h = heading(g)
        for grp in groups:
            dh = abs(h - grp["h"]) % 180
            if min(dh, 180 - dh) < 5 and grp["g"].buffer(5).intersects(g):
                grp["g"] = grp["g"].union(g)
                break
        else:
            groups.append({"g": g, "h": h})
    for k, grp in enumerate(groups):
        poly = grp["g"]
        if poly.area < 20000:
            continue
        rect = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)[:4]
        e0, e1 = rect[1] - rect[0], rect[2] - rect[1]
        if np.linalg.norm(e0) < np.linalg.norm(e1):
            rect = np.roll(rect, -1, axis=0)
            e0, e1 = e1, e0
        length, width = np.linalg.norm(e0), np.linalg.norm(e1)
        mid0 = rect[0] + e1 / 2
        mid1 = mid0 + e0
        # one quad along the centreline, in the tile of its midpoint (the viewer only culls far tiles)
        ss = np.array([0.0, length])
        xz = to_scene(np.array([mid0, mid1]), origin)
        m = meshes[tile_of((mid0 + mid1) / 2)]
        # (crossing runways a few cm apart in depth)
        m.strip(xz, np.full(2, RUNWAY_Y + 0.03 * k), ss, -width / 2, width / 2, (RUNWAY, min(255, round(width * 2)),
                                                                   min(255, round(length / 20)), 0))
        stats["runways"] += 1
        print(f"runway {length:.0f} x {width:.0f} m, heading {np.degrees(np.arctan2(e0[0], e0[1])) % 180:.1f} deg")

    OUT_RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in list(OUT_RAW.glob("*.glb")) + list(OUT.glob("*.glb")):
        f.unlink()
    files, verts, tris = [], 0, 0
    for (tx, ty), mesh in sorted(meshes.items()):
        m = mesh.arrays(terrain)
        if not len(m["idx"]):
            continue
        name = f"m_{tx}_{ty}.glb"
        write_glb(OUT_RAW / name, m)
        files.append({"file": name, "x": tx * TILE, "z": -(ty + 1) * TILE, "size": TILE})
        verts += len(m["pos"])
        tris += len(m["idx"]) // 3
    pack07.RAW, pack07.OUT = OUT_RAW, OUT
    for f in files:
        pack07.pack(f["file"])
    index = {"uvRange": {"across": ACROSS_MAX, "along": ALONG_MAX},
             "types": ["lanes", "crossing", "sidewalk", "median", "runway", "plaza", "zebra", "beacon", "tram"], "tiles": files}
    (OUT / "markings.json").write_text(json.dumps(index, indent=1))
    link_web("markings")
    raw = sum((OUT_RAW / f["file"]).stat().st_size for f in files) / 1e6
    packed = sum((OUT / f["file"]).stat().st_size for f in files) / 1e6
    print(dict(stats))
    print(f"{len(files)} tiles, {verts:,} vertices, {tris:,} triangles; {raw:.1f} MB raw -> {packed:.1f} MB packed")


def scramble_strips(scrambles: dict) -> list:
    """[markings] scrambles: one zebra strip per diagonal crossing, its centreline across the walk (UTM points p, two),
    along 20 +- (w / 2 + 0.4) m, across +-half (the crossing's length / 2); each later crossing 1 cm higher (they
    cross in the box)."""
    out = []
    for sc in scrambles.values():
        w, big = float(sc.get("w", 4.0)), bool(sc.get("big", True))
        for a, b in sc["lines"]:
            ab = gpd.GeoSeries(gpd.points_from_xy([a[0], b[0]], [a[1], b[1]]), crs="EPSG:4326").to_crs(UTM)
            p0, p1 = np.array([ab.iloc[0].x, ab.iloc[0].y]), np.array([ab.iloc[1].x, ab.iloc[1].y])
            walk = p1 - p0
            length = float(np.linalg.norm(walk))
            half = min(length / 2, ACROSS_MAX - 1)
            t = walk / max(length, 1e-9)
            d = np.array([t[1], -t[0]])          # the strip runs across the walk: the walk lies on its left (+across)
            m, e = (p0 + p1) / 2, w / 2 + 0.4
            out.append({"p": np.array([m - d * e, m + d * e]), "along": np.array([20 - e, 20 + e]), "half": half,
                        "rgba": (ZEBRA_T, min(255, round(half * 4)), 32 * big, 0), "dy": 0.01 * len(out)})
    return out


def tram_tracks(trams, recs, tags, emit, stats):
    """[markings] trams: a strip over each tram track. On a carriageway (the track within a road's half width,
    sampled every 8 m, the majority deciding) its rails are embedded in the road's asphalt, or in granite setts on a
    cobbled road or for the `setts` share of the others (Pflastergleis); off the road in grass where the green layer
    holds it (Rasengleis), else on ballast and sleepers. The strip covers 06_tiles' ballast band off the road."""
    opt = TRAMS if isinstance(TRAMS, dict) else {}
    road_w, off_w, sett_share = opt.get("road_w", 2.4), opt.get("off_w", 3.4), opt.get("setts", 0.0)
    rd = [(r, LineString(r["c"][:, :2])) for r in recs if r["kind"] in ("major", "minor") and len(r["c"]) >= 2]
    tree = shapely.STRtree([ln for _, ln in rd])
    green = gpd.read_file(DATA / "ground.gpkg", layer="green").geometry.values
    gtree = shapely.STRtree(green)
    rng = np.random.default_rng(23)
    for r in trams.itertuples():
        c = np.asarray(r.geometry.coords, float)
        if c.shape[1] == 2:
            c = np.column_stack([c, np.zeros(len(c))])
        if len(c) < 2:
            continue
        t = tags.get(r.osm_id, {})
        if t.get("tunnel") in ("yes", "building_passage") or t.get("layer", "0").startswith("-"):
            continue
        line = LineString(c[:, :2])
        n = max(2, int(line.length // 8))
        pts = shapely.points([line.interpolate(f, normalized=True).coords[0] for f in np.linspace(0.02, 0.98, n)])
        on_road, sett = 0, 0
        for p in pts:
            for k in tree.query(p, predicate="dwithin", distance=20.0):
                rec, ln = rd[k]
                if ln.distance(p) <= rec["w"] / 2 + 0.3:
                    on_road += 1
                    sett += rec["tags"].get("surface") in SETTS if SETTS else 0
                    break
        if on_road >= n / 2:
            bed = 1 if sett >= on_road / 2 or rng.random() < sett_share else 0
            half = road_w / 2
        else:
            in_green = sum(len(gtree.query(p, predicate="within")) > 0 for p in pts)
            bed = 2 if in_green >= n / 2 else 3
            half = off_w / 2
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c[:, :2], axis=0), axis=1))]
        if s[-1] < 1:
            continue
        elev = bool(r.elevated)
        emit(c, s, rng.uniform(0, 600), -half, half, (TRAM, min(255, round(half * 4)), bed, 0),
             ROAD_Y + OVER_Y + TRAM_Y, not elev)
        stats[f"tram km {['asphalt', 'setts', 'grass', 'ballast'][bed]}"] += s[-1] / 1000


def write_glb(path, m: dict):
    """One mesh named 'markings': positions uint16 per axis (non-uniform node scale), TEXCOORD_0 unorm16
    (see module docstring), COLOR_0 RGBA8 integers (not normalized in meaning: the shader multiplies by
    255), NORMAL int8, the ground's times the node's scale (three.js divides it out again; straight up on
    level ground, so it compresses to almost nothing)."""
    m = optimize(m)
    blob, views, accessors = bytearray(), [], []

    def add(arr, comp, typ, target, normalized=False, minmax=None):
        data = np.ascontiguousarray(arr).tobytes()
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target}
        if target == 34962:
            view["byteStride"] = arr.shape[1] * arr.itemsize
        views.append(view)
        blob.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": len(arr), "type": typ}
        if normalized:
            acc["normalized"] = True
        if minmax is not None:
            acc["min"], acc["max"] = minmax
        accessors.append(acc)
        return len(accessors) - 1

    n = len(m["pos"])
    lo, hi = m["pos"].min(0), m["pos"].max(0)
    # coarse steps compress far better than using all 16 bits: 5 cm across the map, 1 cm vertically
    step = np.maximum(np.maximum((hi - lo) / 65535, [0.05, 0.01, 0.05]), 1e-6)
    q = np.zeros((n, 4), np.uint16)
    q[:, :3] = np.round((m["pos"] - lo) / step)
    uv = np.column_stack([(m["uv"][:, 0] + ACROSS_MAX) / (2 * ACROSS_MAX), m["uv"][:, 1] / ALONG_MAX])
    # likewise snap across to 1 cm and along to 5 cm (low bits zero), still exact multiples of the unorm step
    snap = np.array([0.01 / (2 * ACROSS_MAX), 0.05 / ALONG_MAX]) * 65535
    snap = np.maximum(np.floor(snap), 1)
    uvq = (np.round(np.clip(uv, 0, 1) * 65535 / snap) * snap).clip(0, 65535).astype(np.uint16)
    attrs = {
        "POSITION": add(q, 5123, "VEC3", 34962, minmax=(q[:, :3].min(0).tolist(), q[:, :3].max(0).tolist())),
        "NORMAL": add(normals(m["nrm"], step), 5120, "VEC3", 34962, normalized=True),
        "TEXCOORD_0": add(uvq, 5123, "VEC2", 34962, normalized=True),
        "COLOR_0": add(m["col"].astype(np.uint8), 5121, "VEC4", 34962, normalized=True),
    }
    big = n >= 65536
    ind = add(m["idx"].astype(np.uint32 if big else np.uint16), 5125 if big else 5123, "SCALAR", 34963)
    while len(blob) % 4:
        blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": generator("06b_markings")},
            "extensionsUsed": ["KHR_mesh_quantization"], "extensionsRequired": ["KHR_mesh_quantization"],
            "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "markings", "translation": lo.tolist(), "scale": step.tolist()}],
            "meshes": [{"name": "markings", "primitives": [{"attributes": attrs, "indices": ind, "material": 0}]}],
            "materials": [{"name": "markings"}], "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942)); f.write(bytes(blob))


def normals(nrm, step):
    """int8 normals (padded to 4 bytes) for a node scaled by `step` per axis."""
    v = nrm * step
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    out = np.zeros((len(v), 4), np.int8)
    out[:, :3] = np.round(v * 127)
    return out

