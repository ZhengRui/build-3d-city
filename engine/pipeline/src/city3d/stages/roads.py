"""05b_roads: fetch roads and railways from OSM and work out their width and, for bridges, their deck height.

Writes roads.gpkg (UTM) in the data folder, layer "ways", one row per OSM way:
  kind       major (motorway/trunk/primary/secondary), minor, service or rail
  width      carriageway width in metres: the width tag, else lanes × LANE_W, else a typical value
             ([roads.default_w], the region preset's)
  elevated   bridge/viaduct; its geometry is 3D with z = the deck's height in the scene (metres, the
             ground of 05a_terrain.py being 0 on the coastal plain)

Roads are cut off MARGIN ([roads] margin) outside the districts, where the buildings end too (bridges are kept whole
if they reach that far, as cutting would lose their deck heights). Tunnels and underground ways are
left out.

Deck heights: LAYER_H per OSM layer (a bridge without a layer counts as layer 1) above a grade line, or for
the bridges named in [roads] decks their own height (a river crossing: Manhattan's East River bridges carry
their roadways about 40 m over the water).
Nodes a bridge shares with a road at ground level are pinned to the ground there, and no deck climbs faster
than GRADE from there, so ramps rise gradually and short river bridges stay low. The grade line runs
smoothly along the elevated network between those pinned nodes (the ground's height interpolated along
it, harmonic on the network's graph, pulled towards the ground under it only over kilometres), so a viaduct
spans a valley instead of dipping into it; where the ground rises above the line (a ridge) the deck
follows the ground.

The Overpass response is cached in raw/osm_roads.json; delete it to fetch again.
"""
import heapq
import json
import re
from collections import defaultdict

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, box

from ..common import CFG, CHECKS, DATA, RAW, UTM, Terrain, boundary, element_geoms, overpass

R = CFG["roads"]
# named bridges drawn whole ([roads] bridge_outlines): OSM's man_made=bridge outline of each bridge whose ways are
# a [roads] decks span, as a slab at their deck height (06_tiles), with piers in the water by [roads] piers
OUTLINES = R.get("bridge_outlines", False)
# ... a multipolygon outline's parts each as its own slab (the two Golden Jubilee footbridges either side of the
# Hungerford rail bridge, one relation: drawn as one 35 m slab over all three), and railway bridges too: an
# outline whose own name is a decks span and over which no road deck runs takes the elevated railways under it
# (Cannon Street's, Blackfriars' and Grosvenor's tracks carry no bridge:name; drawn as fanned track ribbons)
OUTLINE_PARTS = R.get("outline_parts", False)
RAIL_OUTLINES = R.get("rail_outlines", False)
# [roads] outline_names: an elevated road way with no decks span of its own (no bridge:name: Berlin's Kronprinzenbrücke
# and Mühlendammbrücke carry their street's name) that lies at least half inside a man_made=bridge outline named as a
# decks span takes that span (its deck height, its outline drawn whole); off by default
OUTLINE_NAMES = R.get("outline_names", False)
# [roads] span_ways = {span: [OSM way ids]}: these elevated ways belong to that decks span, as if their bridge:name were
# the key (a key with "lower" in it, "<span> lower", puts them on its lower level): ways with no bridge:name whose
# name is the whole line's (Tokyo's Rainbow Bridge: the lower deck's unnamed roads and the Yurikamome, layer 3, under
# the Shuto's layer 4); off by default
# [roads] built_only = {margin, keep}: ground-level ways outside the districts and the masses ([ground] masses_within)
# are cut `margin` m beyond them, except highway values in `keep` (and railways), which run on to [roads] margin. A city
# whose masses stand only in some gaps (Tokyo) otherwise draws 1-2 km of streets, street trees and cars across the
# painted town around them, stopping on a rounded outline (M3 critic); empty: off
BUILT_ONLY = R.get("built_only", {})
SPAN_WAYS = {int(i): k for k, ids in R.get("span_ways", {}).items() for i in ids}
# [roads] rail_join: elevated railways with no decks span of their own, in connected groups, a group touching the ways
# of one rail decks span (and no other) taking that span (Berlin's Stadtbahn through the Hauptbahnhof: its station tracks carry no name and stood at OSM's
# layer, 21-26 m, over the named viaduct's 11 m); off by default
RAIL_JOIN = R.get("rail_join", False)
# [roads] rail_on = {field, values (prefixes), near, gap, step, source}: railway decks laid on the building table's
# viaduct structures (Berlin's LoD2 keeps the Stadtbahn's brick arches as 51009_1750 solids): an elevated railway's
# node within `near` m of such a structure takes its top (the lowest ground under its outline + its height, as
# 06_tiles stands it) as the deck's drawn top; nodes between two such nodes less than `gap` m apart along the way are
# interpolated (a steel span over a street); elevated railways get a node every `step` m. 06_tiles draws no stick
# piers inside those structures. Off by default ({})
RAIL_ON = R.get("rail_on", {})
_D = CFG["terrain"].get("datum", "auto")
DATUM = float(_D) if isinstance(_D, (int, float)) else float("nan")     # (inland, set: the scene's 0 in the DEM's metres)
# roads at ground level under a slab ([terrain] dalles: La Défense's) are covered: cut out
DALLES = CFG["terrain"].get("dalles", [])
GROUND_MARGIN = CFG["ground"]["margin"]   # fetch area, the same as 05_ground.py
MARGIN = R["margin"]
LAYER_H = R["layer_h"]
# a railway's first layer's deck height (default: layer_h; higher layers add layer_h): London's viaducts run on 8-9 m
# brick arches, which OSM maps as buildings, so at 7.5 m the tracks ran through their tops
RAIL_LAYER_H = R.get("rail_layer_h") or LAYER_H
GRADE = R["grade"]
PULL = 1e-5                 # how strongly the grade line is drawn to the ground under it (per metre)
DECK_STEP = 20.0            # metres between the points of a deck's line
PIN_REACH = 12.0            # a deck's end takes the highest ground this far along the roads it meets (m)
NODE_STEP = 40.0            # elevated ways get a node at least this often before their heights are worked out
LANE_W = R["lane_w"]
FOOTBRIDGES = R.get("footbridges", False)   # fetch footways on bridges too, drawn as decks (service)
FOOTBRIDGE_W = 4.0                           # their width where untagged (m)
PARKING_LANES = R.get("parking_lanes", {})   # highway -> parking lanes added to a lanes-tagged width
PARK_LANE_W = 2.4
CACHE = RAW / "osm_roads.json"

MAJOR = {"motorway", "trunk", "primary", "secondary"}
MINOR = {"tertiary", "residential", "unclassified", "living_street", "road"}
SERVICE = {"service", "pedestrian"}
RAIL = {"rail", "light_rail", "subway", "narrow_gauge", "monorail", "tram"}
SKIP_SERVICE = {"parking_aisle", "driveway", "drive-through"}
# typical carriageway width (m) when a way has neither width nor lanes: (two-way, one-way)
DEFAULT_W = {k: tuple(v) for k, v in R["default_w"].items()}


def is_yes(v) -> bool:
    return v is not None and v != "no"


def number(v):
    try:
        return float(str(v).replace(",", ".").split(";")[0].split()[0])
    except (ValueError, IndexError):
        return None


def classify(t: dict):
    if t.get("railway") in RAIL:
        return "rail"
    if t.get("footbridge") == "yes":
        return "service"
    hw = t.get("highway", "")
    base = hw.removesuffix("_link")
    if base in MAJOR:
        return "major"
    if base in MINOR:
        return "minor"
    if hw in SERVICE and t.get("service") not in SKIP_SERVICE:
        return "service"
    return None


def length_m(v):
    """A length tag in metres: "12", "12 m", "40 ft", "40'", "12'6\"" (feet and inches, common in the US)."""
    if v is None:
        return None
    v = str(v).strip().lower()
    m = re.match(r"^([\d.]+)\s*(?:'|ft|feet)\s*(?:([\d.]+)\s*(?:\"|in))?$", v)
    if m:
        return float(m[1]) * 0.3048 + (float(m[2]) * 0.0254 if m[2] else 0.0)
    return number(v)


DECKS = R["decks"]          # bridge name -> deck height over the water or ground below (m)
# OSM ways counted as bridges though not tagged so (off by default []): Tower Bridge's roadway through its two towers
# is tunnel=building_passage, so its nodes were pinned to the ground there (the river) and the deck lay on the water
BRIDGE_WAYS = set(R.get("bridge_ways", []))
# named decks whose approaches are eased (off by default []; a list, or {span: grade}): after the caps, no node of the
# span lies more than the grade (default GRADE) x distance under a neighbour, raised where it does (the deck ends pinned to the roads left as they are), so
# a span held level under a high bank's road climbs to it at GRADE instead of a step (the Pont de Puteaux: the
# Puteaux quay 6 m over the span's level, 20 % over its last 30 m)
_E = R.get("decks_ease", [])
DECKS_EASE = dict(_E) if isinstance(_E, dict) else {k: R["grade"] for k in _E}     # span -> grade ({span: grade} or [spans])


DECKS_REF = R.get("decks_ref", "ground")   # "water": named decks count from the lowest ground under the span
DECKS_LEVEL = R.get("decks_level", False)   # ... from the level of the water under it (quay walls drop the ground there)
LOWER = R["lower_level"]     # a lower level runs this far under its bridge's deck (m)


def span_of(t: dict):
    """The [roads] decks key a way belongs to: the key found in its bridge:name or name ("George Washington
    Bridge" in "George Washington Bridge Lower Level"), and whether it is a lower level."""
    for k in ("bridge:name", "name"):
        v = t.get(k) or ""
        for key in DECKS:
            if key.lower() in v.lower():
                return key, "lower" in v.lower()
    return None, False


def deck_target(t: dict):
    """A named bridge's deck height ([roads] decks), by its name or bridge:name; lower levels under it. A
    decks value is the deck's height, or {deck, lower (the lower level's height), rail_lower (tracks run on
    the lower level: the Manhattan Bridge's subway), water (its height over the water instead: a viaduct
    crossing a river on top of a road bridge, Paris's Métro 6 at Bir-Hakeim and Bercy), reach (the deck counts
    from the highest ground within this many metres along it: a viaduct level over a cutting)}."""
    key, lower = span_of(t)
    if key is None:
        return None
    d = DECKS[key]
    if isinstance(d, dict):
        lower = lower or (d.get("rail_lower", False) and t.get("railway") in ("subway", "rail", "light_rail"))
        return float(d["lower"] if lower else d["deck"])
    return float(d) - (LOWER if lower else 0.0)


def over_water(t: dict):
    """A named deck's height over the water ({deck, water}), or None."""
    key, _ = span_of(t)
    d = DECKS.get(key) if key else None
    return float(d["water"]) if isinstance(d, dict) and "water" in d else None


def width(t: dict, kind: str) -> float:
    w = length_m(t.get("width"))
    if w and 2 <= w <= 60:
        return w
    if t.get("footbridge") == "yes":
        return FOOTBRIDGE_W
    if kind == "rail":
        return 3.2 * max(1, int(number(t.get("tracks")) or 1))
    lanes = number(t.get("lanes"))
    if lanes and 1 <= lanes <= 12:
        # OSM's lanes are moving lanes: the parking lanes along the kerbs come on top ([roads] parking_lanes
        # per highway, unless parking:both / parking:lane:both is no)
        park = PARKING_LANES.get(t["highway"], 0)
        if any(t.get(k) in ("no", "no_parking", "no_stopping") for k in ("parking:both", "parking:lane:both")):
            park = 0
        return lanes * LANE_W + (2 if t["highway"] in ("motorway", "trunk") else 0) + park * PARK_LANE_W
    hw = t["highway"]
    two, one = DEFAULT_W["link" if hw.endswith("_link") else hw]
    return one if t.get("oneway") in ("yes", "1", "-1") else two


def fetch(bb: str) -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    res = overpass(f"""
        [out:json][timeout:900][bbox:{bb}];
        (
          way["highway"~"^(motorway|trunk|primary|secondary|tertiary)(_link)?$"];
          way["highway"~"^(residential|unclassified|living_street|road|service|pedestrian)$"];
          way["railway"~"^({'|'.join(RAIL)})$"];
        );
        out geom;
    """)
    CACHE.write_text(json.dumps(res))
    return res


def cached_ways():
    """The cached OSM ways as main() reads them (raw/osm_roads.json, and raw/osm_footbridges.json with [roads]
    footbridges): ([{id, tags, kind, tunnel, elevated, nodes}], {node: (e, n) UTM}), or None without the cache.
    For 05a_terrain's [terrain] deck_ends, which runs before this stage."""
    if not CACHE.exists():
        return None
    els = json.loads(CACHE.read_text())["elements"]
    fb = RAW / "osm_footbridges.json"
    if FOOTBRIDGES and fb.exists():
        seen = {el["id"] for el in els}
        els = els + [{**el, "tags": {**el["tags"], "footbridge": "yes"}} for el in json.loads(fb.read_text())["elements"]
                     if el["id"] not in seen and len(el.get("geometry", [])) >= 2
                     and el.get("tags", {}).get("footway") not in ("sidewalk", "crossing", "traffic_island")
                     and el.get("tags", {}).get("area") != "yes"]
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    ways, xy = [], {}
    for el in els:
        if el["type"] != "way" or len(el.get("nodes", [])) < 2:
            continue
        t = el.get("tags", {})
        kind = classify(t) if t.get("area") != "yes" else None
        tunnel = is_yes(t.get("tunnel")) or is_yes(t.get("covered")) or (number(t.get("layer")) or 0) < 0
        tunnel = tunnel and el["id"] not in BRIDGE_WAYS
        x, y = to_utm.transform([p["lon"] for p in el["geometry"]], [p["lat"] for p in el["geometry"]])
        xy.update(zip(el["nodes"], zip(x, y)))
        ways.append({"id": el["id"], "tags": t, "kind": kind, "tunnel": tunnel, "nodes": el["nodes"],
                     "elevated": (is_yes(t.get("bridge")) or el["id"] in BRIDGE_WAYS) and not tunnel})
    return ways, xy


def road_pins(ways: list[dict]) -> set:
    """[terrain] deck_ends: the nodes where a road deck (an elevated way drawn as a road, not a railway) meets a road
    drawn at ground level (not a railway, not in a tunnel), where 05a_terrain raises the ground to the road's (those
    it did go to deck_ends.json; their decks end on the ground at the node, not the highest within PIN_REACH)."""
    deck = {n for w in ways if w["elevated"] and w["kind"] not in (None, "rail") for n in w["nodes"]}
    return {n for w in ways if not w["elevated"] and not w["tunnel"] and w["kind"] not in (None, "rail")
            for n in w["nodes"] if n in deck}


DECK_ENDS = CFG["terrain"].get("deck_ends", {})


def deck_heights(ways: list[dict], xy: dict) -> dict:
    """Node id -> deck height for every node of an elevated way (see module docstring)."""
    init = {}
    for w in ways:
        if w["elevated"]:
            k = max(1, int(number(w["tags"].get("layer")) or 1))
            first = RAIL_LAYER_H if w["tags"].get("railway") in RAIL else LAYER_H
            h = deck_target(w["tags"]) or first + LAYER_H * (k - 1)
            for n in w["nodes"]:
                init[n] = max(init.get(n, 0), h)
    for w in ways:                              # anything at ground level (or in a tunnel) pins its nodes
        if not w["elevated"]:
            for n in w["nodes"]:
                if n in init:
                    init[n] = 0.0
    # a footbridge's end that meets no other way fetched comes down to the ground there (a footbridge's end
    # joins footways, which aren't fetched: the Pont des Arts stood 7.5 m over its quays' paving)
    uses = defaultdict(int)
    for w in ways:
        for n in set(w["nodes"]):
            uses[n] += 1
    for w in ways:
        if w["elevated"] and w["tags"].get("footbridge") == "yes":
            for n in (w["nodes"][0], w["nodes"][-1]):
                if uses[n] == 1:
                    init[n] = 0.0
    adj = defaultdict(list)
    for w in ways:
        if w["elevated"]:
            for a, b in zip(w["nodes"][:-1], w["nodes"][1:]):
                d = float(np.hypot(*np.subtract(xy[a], xy[b])))
                adj[a].append((b, d))
                adj[b].append((a, d))
    # lower envelope: h(n) = min over m of init(m) + GRADE * dist(n, m), by Dijkstra
    h = dict(init)
    heap = [(v, n) for n, v in h.items()]
    heapq.heapify(heap)
    while heap:
        v, n = heapq.heappop(heap)
        if v > h[n]:
            continue
        for m, d in adj[n]:
            nv = v + GRADE * d
            if nv < h[m]:
                h[m] = nv
                heapq.heappush(heap, (nv, m))
    return h


def grade_line(ways: list[dict], xy: dict, deck: dict, ground: dict) -> dict:
    """Node id -> height of the grade line under the decks: the ground at the nodes pinned to ground-level
    roads (deck 0), smooth along the elevated network in between (see the module docstring)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    nodes = sorted(deck)
    k = {n: i for i, n in enumerate(nodes)}
    rows, cols, w = [], [], []
    for way in ways:
        if way["elevated"]:
            for a, b in zip(way["nodes"][:-1], way["nodes"][1:]):
                if a != b:
                    rows.append(k[a]); cols.append(k[b])
                    w.append(1 / max(float(np.hypot(*np.subtract(xy[a], xy[b]))), 1.0))
    n = len(nodes)
    rows, cols, w = np.array(rows), np.array(cols), np.array(w)
    W = coo_matrix((np.r_[w, w], (np.r_[rows, cols], np.r_[cols, rows])), shape=(n, n)).tocsr()
    T = np.array([ground[m] for m in nodes])
    pin = np.array([deck[m] == 0 for m in nodes])
    # minimise sum w (B_i - B_j)^2 + PULL sum (B_i - T_i)^2 over the free nodes, pinned ones fixed at T
    L = (coo_matrix((np.asarray(W.sum(1)).ravel() + PULL, (np.arange(n), np.arange(n))), shape=(n, n)) - W).tocsr()
    free = np.flatnonzero(~pin)
    B = T.copy()
    if len(free):
        rhs = PULL * T[free] - L[free][:, np.flatnonzero(pin)] @ T[pin]
        B[free] = spsolve(L[free][:, free].tocsc(), rhs)
    return dict(zip(nodes, B))


def deck_line(pts, top, rise, terrain) -> LineString:
    """A deck's 3D line: between two nodes where the ground rises closer to the deck than the deck stands
    above the grade line (a crest), points every DECK_STEP m, each kept that high above the ground."""
    p = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    n = np.maximum(np.ceil(seg / DECK_STEP).astype(int), 1)
    f = np.concatenate([np.arange(k) / k for k in n] + [[0.0]])
    i = np.concatenate([np.full(k, j) for j, k in enumerate(n)] + [[len(p) - 1]])
    j = np.minimum(i + 1, len(p) - 1)
    q = p[i] + (p[j] - p[i]) * f[:, None]
    z = np.asarray(top)[i] + (np.asarray(top)[j] - np.asarray(top)[i]) * f
    d = np.asarray(rise)[i] + (np.asarray(rise)[j] - np.asarray(rise)[i]) * f
    lifted = terrain.height_utm(q[:, 0], q[:, 1]) + d
    # keep a segment's points in between only if one of them had to rise
    raised = np.zeros(len(n), bool)
    np.logical_or.at(raised, i[:-1], lifted[:-1] > z[:-1] + 0.05)
    keep = (f == 0) | raised[np.minimum(i, len(n) - 1)]
    return LineString(np.column_stack([q, np.maximum(z, lifted)])[keep])


def arch_structures(terrain=None):
    """[roads] rail_on: the building table's viaduct structures (UTM polygons) and, given the terrain, their tops in
    the scene (the lowest ground under the outline + the height, as 06_tiles stands a building)."""
    import pyogrio
    path = DATA / "buildings.gpkg"
    field = RAIL_ON.get("field", "function")
    vals = tuple(RAIL_ON.get("values", []))
    gz = RAIL_ON.get("ground_field", "ground_elevation")
    cols = [field, "h"] + ([gz] if gz in pyogrio.read_info(path)["fields"] else [])
    b = gpd.read_file(path, columns=cols)
    b = b[b[field].fillna("").astype(str).str.startswith(vals)].to_crs(UTM) if vals else b.iloc[:0]
    geoms = list(b.geometry.values)
    base = (terrain if terrain is not None else Terrain()).bases(geoms)
    # a structure whose own ground (the source's, less the inland datum) lies over a metre from the lowest scene ground
    # under its outline (an arch reaching over a quay wall's drop: 06_tiles stands it 4 m low) is left out: its drawn
    # top is not where the tracks run
    if gz in b.columns and np.isfinite(DATUM):
        own = b[gz].to_numpy(float) - DATUM
        ok = ~(np.abs(own - base) > 1.0)
        b, geoms, base = b[ok], [g for g, k in zip(geoms, ok) if k], base[ok]
    if terrain is None:
        return geoms, None
    return geoms, base + b.h.to_numpy(float)


def rail_on_structures(ways, xy, top, terrain):
    """[roads] rail_on (see RAIL_ON), in place on top (node -> deck height; the drawn top is ROAD_Y over it)."""
    import shapely
    from .tiles import ROAD_Y
    geoms, tops = arch_structures(terrain)
    if not geoms:
        print("rail on structures: none in the building table")
        return
    near, gap = float(RAIL_ON.get("near", 2.0)), float(RAIL_ON.get("gap", 80.0))
    tree = shapely.STRtree(geoms)
    snapped, filled, ways_n = 0, 0, 0
    for w in ways:
        if not (w["elevated"] and w["kind"] == "rail"):
            continue
        ns = w["nodes"]
        P = np.array([xy[n] for n in ns], float)
        hit = tree.query(shapely.points(P), predicate="dwithin", distance=near)
        z = np.full(len(ns), np.nan)
        for i, j in zip(*hit):
            v = tops[j] - ROAD_Y
            z[i] = v if np.isnan(z[i]) else max(z[i], v)
        ok = np.isfinite(z)
        if not ok.any():
            continue
        ways_n += 1
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        idx = np.flatnonzero(ok)
        for a, b in zip(idx[:-1], idx[1:]):
            if b > a + 1 and s[b] - s[a] <= gap:
                f = (s[a + 1:b] - s[a]) / max(s[b] - s[a], 1e-9)
                z[a + 1:b] = z[a] + (z[b] - z[a]) * f
                filled += b - a - 1
        for i in np.flatnonzero(np.isfinite(z)):
            top[ns[i]] = float(z[i])
        snapped += int(ok.sum())
    print(f"rail on structures: {len(geoms):,} structures; {snapped:,} track nodes of {ways_n} ways on their tops, "
          f"{filled:,} between them interpolated")


def outline_polys(bbox: str) -> list:
    """OSM's man_made=bridge outlines over the area: [(tags, polygon in UTM)] (cached in raw/)."""
    cache = RAW / "osm_bridge_outlines.json"
    if cache.exists():
        res = json.loads(cache.read_text())
    else:
        res = overpass(f"""
            [out:json][timeout:300][bbox:{bbox}];
            (way["man_made"="bridge"]; rel["man_made"="bridge"];);
            out geom;""")
        cache.write_text(json.dumps(res))
    polys = [(t, geom) for t, geom in element_geoms(res) if geom.geom_type in ("Polygon", "MultiPolygon")]
    geoms = gpd.GeoSeries([p for _, p in polys], crs="EPSG:4326").to_crs(UTM).make_valid()
    return [(t, p) for (t, _), p in zip(polys, geoms)]


def outlines(g, bbox: str, near):
    """The man_made=bridge outlines over which [roads] decks spans run (the span with the most length of its
    road ways inside, railways left out: a viaduct on top is its own deck), each with that deck's height (the
    median of those ways' nodes inside), and checks/bridges.md: the share of each outline the ways' own decks
    cover, which the outlines make up for (the M3 critic's Pont d'Iéna: two 3.2 m bus lanes for a 35 m deck)."""
    import shapely
    polys = outline_polys(bbox)
    geoms = [p for _, p in polys]
    el = g[g.elevated & (g.kind != "rail") & g.span.notna()]
    rail = g[g.elevated & (g.kind == "rail")] if RAIL_OUTLINES else None
    rows, lines = [], []
    pieces = []
    for (t, _), poly in zip(polys, geoms):
        if OUTLINE_PARTS and poly.geom_type == "MultiPolygon" and len(poly.geoms) > 1:
            pieces += [(t, p, i) for i, p in enumerate(poly.geoms)]
        else:
            pieces.append((t, poly, None))
    for t, poly, part in pieces:
        if poly.is_empty or not poly.intersects(near):
            continue
        cand = el[el.intersects(poly)]
        span = None
        if len(cand):
            inside = cand.geometry.intersection(poly)
            by = inside.length.groupby(cand.span.values).sum()
            span = by.idxmax()
            if by[span] < 10:
                span = None
        if span is not None:
            mine = cand[cand.span == span]
        elif rail is not None and span_of(t)[0] is not None:
            # a railway bridge: its outline's own name, the tracks on it
            mine = rail[rail.intersects(poly)]
            if not len(mine) or mine.geometry.intersection(poly).length.sum() < 10:
                continue
            span = span_of(t)[0]
        else:
            continue
        z = np.concatenate([np.asarray(c.coords)[:, 2] for c in mine.geometry])
        xy = np.concatenate([np.asarray(c.coords)[:, :2] for c in mine.geometry])
        z = z[shapely.contains_xy(poly.buffer(2), xy[:, 0], xy[:, 1])]
        if not len(z):
            continue
        ways = shapely.union_all(shapely.buffer(np.asarray(list(mine.geometry.force_2d()), dtype=object),
                                                mine.width.values / 2, cap_style="flat"))
        share = ways.intersection(poly).area / poly.area
        rows.append({"name": t.get("name") or span, "span": span, "deck": float(np.median(z)),
                     "ways_share": share, "group": span if part is None else f"{span} #{part}", "geometry": poly})
        lines.append((t.get("name") or span, span, poly.area, share))
    lines.sort(key=lambda r: r[3])
    bad = [r for r in lines if r[3] < 0.6]
    md = ["# Bridge decks against their outlines (05b_roads)", "",
          "Each OSM man_made=bridge outline over which a [roads] decks span runs: its area and the share the span's "
          "own road decks (way buffers at their widths) cover. Under 60 % the bridge would be drawn as strips with "
          "water between them; " + ("[roads] bridge_outlines draws every outline whole, as a slab at the deck's height "
          "(drawn share 100 %)." if OUTLINES else "[roads] bridge_outlines is off: FAIL rows are drawn as strips."), "",
          f"{len(lines)} outlines, {len(bad)} under 60 % by their ways.", "",
          "| Outline | decks span | area (m²) | ways' decks cover | drawn |", "|---|---|---|---|---|"]
    for name, span, a, sh in lines:
        drawn = 1.0 if OUTLINES else sh
        md.append(f"| {name} | {span} | {a:,.0f} | {sh:.0%} | {drawn:.0%}{'' if drawn >= 0.6 else ' FAIL'} |")
    (CHECKS / "bridges.md").write_text("\n".join(md) + "\n")
    print(f"bridge outlines: {len(rows)} named decks, {len(bad)} of them under 60 % covered by their ways "
          f"(checks/bridges.md)")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=UTM)


def built_only(g, built, opts):
    """[roads] built_only: ground-level ways (not railways, not the `keep` highway values) cut to `built` (the
    districts and the masses' clip) buffered `margin` m. Returns the ways and the km cut."""
    region = built.buffer(float(opts.get("margin", 50.0)))
    cut = ~g.elevated & (g.kind != "rail") & ~g.highway.isin(opts.get("keep", []))
    before = g.loc[cut].length.sum()
    g = g.copy()
    g.loc[cut, "geometry"] = g.loc[cut].geometry.intersection(region)
    return g, (before - g.loc[cut].length.sum()) / 1000


def main():
    b = boundary()
    area = box(*b.total_bounds).buffer(GROUND_MARGIN, join_style="mitre")
    near = b.geometry.iloc[0].buffer(MARGIN)
    s, w_, n, e = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    bbox = f"{s:.5f},{w_:.5f},{n:.5f},{e:.5f}"
    res = fetch(bbox)
    if FOOTBRIDGES:
        # footbridges ([roads] footbridges: Paris's Pont des Arts, Passerelle Senghor, Debilly, Simone-de-Beauvoir):
        # the footways, paths and cycleways on bridges, as service decks of their own width
        fb = RAW / "osm_footbridges.json"
        if fb.exists():
            extra = json.loads(fb.read_text())
        else:
            extra = overpass(f"""
                [out:json][timeout:600][bbox:{s:.5f},{w_:.5f},{n:.5f},{e:.5f}];
                way["highway"~"^(footway|path|cycleway|steps)$"]["bridge"]["bridge"!="no"];
                out geom;""")
            fb.write_text(json.dumps(extra))
        seen = {el["id"] for el in res["elements"]}
        foot = [el for el in extra["elements"] if el["id"] not in seen and len(el.get("geometry", [])) >= 2
                and el.get("tags", {}).get("footway") not in ("sidewalk", "crossing", "traffic_island")
                and el.get("tags", {}).get("area") != "yes"]         # a bridge's pavement drawn as an outline
        for el in foot:
            el["tags"] = {**el["tags"], "footbridge": "yes"}
        res = {**res, "elements": res["elements"] + foot}
        print(f"footbridges: {len(foot):,} ways")

    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    ways, xy = [], {}
    for el in res["elements"]:
        if el["type"] != "way" or len(el.get("nodes", [])) < 2:
            continue
        t = el.get("tags", {})
        # a square or plaza mapped as an area (highway=pedestrian + area=yes) is paving, not a road: its outline
        # drawn as an 8 m strip ringed every square (Paris: ~2,000 of them, La Défense's dalle criss-crossed)
        kind = classify(t) if t.get("area") != "yes" else None
        tunnel = is_yes(t.get("tunnel")) or is_yes(t.get("covered")) or (number(t.get("layer")) or 0) < 0
        tunnel = tunnel and el["id"] not in BRIDGE_WAYS     # (Tower Bridge's: tunnel=building_passage through a tower)
        lon = [p["lon"] for p in el["geometry"]]
        lat = [p["lat"] for p in el["geometry"]]
        x, y = to_utm.transform(lon, lat)
        xy.update(zip(el["nodes"], zip(x, y)))
        ways.append({"id": el["id"], "tags": t, "kind": kind, "tunnel": tunnel, "nodes": el["nodes"],
                     "elevated": (is_yes(t.get("bridge")) or el["id"] in BRIDGE_WAYS) and not tunnel})
    if SPAN_WAYS:
        n_span = 0
        for w in ways:
            if w["id"] in SPAN_WAYS and w["elevated"]:
                w["tags"] = {**w["tags"], "bridge:name": SPAN_WAYS[w["id"]]}
                n_span += 1
        print(f"span ways: {n_span} of {len(SPAN_WAYS)} listed elevated ways take their decks span")
    if OUTLINE_NAMES and DECKS:
        named = [(span_of(t)[0], poly) for t, poly in outline_polys(bbox) if span_of(t)[0] is not None]
        n_named = 0
        for w in ways:
            if not w["elevated"] or w["kind"] in (None, "rail") or span_of(w["tags"])[0] is not None:
                continue
            line = LineString([xy[k] for k in w["nodes"]])
            for key, poly in named:
                if line.length > 0 and line.intersection(poly).length >= 0.5 * line.length:
                    w["tags"] = {**w["tags"], "bridge:name": key}
                    n_named += 1
                    break
        print(f"outline names: {n_named} elevated ways take their bridge outline's decks span")
    if RAIL_JOIN and DECKS:
        # the unnamed elevated railways in connected groups (shared nodes); a group touching the ways of exactly one
        # rail decks span takes it (station tracks and sidings between and beside the named viaduct's ways)
        span_nodes = defaultdict(set)
        free = []
        for k, w in enumerate(ways):
            if not (w["elevated"] and w["kind"] == "rail"):
                continue
            key = span_of(w["tags"])[0]
            if key is not None:
                for n in w["nodes"]:
                    span_nodes[n].add(key)
            else:
                free.append(k)
        parent = {k: k for k in free}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        by_node = defaultdict(list)
        for k in free:
            for n in ways[k]["nodes"]:
                by_node[n].append(k)
        for ks in by_node.values():
            for a in ks[1:]:
                parent[find(a)] = find(ks[0])
        touch = defaultdict(set)
        for k in free:
            for n in ways[k]["nodes"]:
                touch[find(k)] |= span_nodes.get(n, set())
        n_join = 0
        for k in free:
            keys = touch[find(k)]
            if len(keys) == 1:
                ways[k]["tags"] = {**ways[k]["tags"], "bridge:name": next(iter(keys))}
                n_join += 1
        print(f"rail join: {n_join} unnamed elevated railways in groups touching one decks span take it")
    # long straight spans get nodes every NODE_STEP m: heights are worked out per node, and a river span
    # drawn as one segment between two tunnel portals (the Manhattan Bridge's subway) lay 10 m over the water
    nid = -1
    for w in ways:
        if not w["elevated"]:
            continue
        nodes = [w["nodes"][0]]
        step = float(RAIL_ON.get("step", 10.0)) if RAIL_ON and w["kind"] == "rail" else NODE_STEP
        for a, b in zip(w["nodes"][:-1], w["nodes"][1:]):
            pa, pb = np.asarray(xy[a]), np.asarray(xy[b])
            k = int(np.hypot(*(pb - pa)) // step)
            for j in range(1, k + 1):
                xy[nid] = tuple(pa + (pb - pa) * j / (k + 1))
                nodes.append(nid)
                nid -= 1
            nodes.append(b)
        w["nodes"] = nodes
    h = deck_heights(ways, xy)
    # decks stand on the grade line, or the ground where that is higher
    terrain = Terrain()
    ids = list(h)
    e, nn = np.array([xy[i] for i in ids]).T
    ground = dict(zip(ids, terrain.height_utm(e, nn)))
    # where a deck meets a ground-level road (a pinned node) the ground under the node itself may be the
    # bare earth under the bridge's abutment (a lidar DTM leaves bridges out: at a Paris bridge's end, the
    # lower quay or the water under the first arch): the road's own ground is the highest within PIN_REACH
    # along the ground-level ways leaving it
    flat_adj = defaultdict(list)
    for w in ways:
        if not w["elevated"]:
            for a, b in zip(w["nodes"][:-1], w["nodes"][1:]):
                d = float(np.hypot(*np.subtract(xy[a], xy[b])))
                flat_adj[a].append((b, d))
                flat_adj[b].append((a, d))
    pins = [n for n in ids if h[n] == 0 and n in flat_adj]
    if DECK_ENDS:
        # [terrain] deck_ends: 05a_terrain raised the ground under a road deck's end to the road it meets (the
        # road's level a few metres on, not the highest within PIN_REACH: the Pont Neuf's ends on the Île stood
        # 1.2-1.4 m over the ground the road leaves by); the deck ends on the ground at the node itself
        f = DATA / "deck_ends.json"         # the pins 05a_terrain raised (written by it)
        held_pins = set(json.loads(f.read_text())["pins"]) if f.exists() else set()
        if not f.exists():
            print("deck ends: no deck_ends.json from 05a_terrain: run it first (pins take the highest ground within 12 m)")
        print(f"deck ends: {sum(n in held_pins for n in pins)} of {len(pins)} pinned nodes on the ground 05a raised")
        pins = [n for n in pins if n not in held_pins]
    raised = 0
    for n in pins:
        # the ground-level network within PIN_REACH of the node (a short walk), sampled every 4 m
        best, heap, pts = {n: 0.0}, [(0.0, n)], []
        while heap:
            d, a = heapq.heappop(heap)
            if d > best.get(a, np.inf):
                continue
            for b, L in flat_adj[a]:
                pa, pb = np.asarray(xy[a], float), np.asarray(xy[b], float)
                for f in np.arange(4.0, min(L, PIN_REACH - d) + 1e-9, 4.0):
                    pts.append(pa + (pb - pa) * f / max(L, 1e-9))
                if d + L < PIN_REACH and d + L < best.get(b, np.inf):
                    best[b] = d + L
                    heapq.heappush(heap, (d + L, b))
        if pts:
            P = np.asarray(pts)
            g = float(terrain.height_utm(P[:, 0], P[:, 1]).max())
            if g > ground[n] + 0.5:
                ground[n] = g
                raised += 1
    print(f"deck ends: {raised} of {len(pins)} pinned nodes take their road's ground within {PIN_REACH:.0f} m")
    line = grade_line(ways, xy, h, ground)
    top = {i: max(line[i], ground[i]) + h[i] for i in ids}
    # the named decks ([roads] decks) are clearances over the water under them: no higher than that over
    # the ground (the grade line, smoothed between the approaches' heights, lifted the Brooklyn Bridge's
    # roadways 10 m over its trusses at midspan)
    # ...and at that height all the way between the anchorages of a suspension bridge built from [[structures]]
    # (its stiffening trusses run level there; the approach descends beyond)
    held = {}
    for st in CFG.get("structures", []):
        if st.get("kind") == "suspension" and st["name"] in DECKS and st.get("cables"):
            (x0, y0), (x1, y1) = (to_utm.transform(*p) for p in st["towers"])
            side = st["cables"]["side"]
            s0, s1 = (side if isinstance(side, list) else (side, side))
            held[st["name"]] = (np.array([x0, y0]), np.array([x1, y1]), float(s0), float(s1))
    # nodes over the water, for decks with a height of their own there ({deck, water}: a metro viaduct 7 m over
    # its boulevard crosses the river on top of a road bridge, 15 m over the water)
    wet = set()
    if any(isinstance(d, dict) and "water" in d for d in DECKS.values()):
        import shapely
        wu = gpd.read_file(DATA / "ground.gpkg", layer="water").union_all()
        el = [i for i in ids if isinstance(i, (int, np.integer))]
        P = np.array([xy[i] for i in el])
        wet = {i for i, k in zip(el, shapely.contains_xy(wu, P[:, 0], P[:, 1])) if k}
    # [roads] decks_ref = "water": a named deck's height counts from the lowest ground under its span (the water)
    # everywhere along it, not from the ground under each node (the Pont de Neuilly crossing the Île de Puteaux
    # rose 5 m over the island); a deck never comes closer than a metre to the ground under it
    ref = {}
    if DECKS_REF == "water":
        for w in ways:
            key = span_of(w["tags"])[0] if w["elevated"] else None
            if key is not None and not isinstance(DECKS[key], dict):     # {deck, water}: their own rule
                ref[key] = min(ref.get(key, np.inf), min(ground[n] for n in w["nodes"]))
        if DECKS_LEVEL and ref:
            # [roads] decks_level: from the level of the water under the span, not the lowest ground: with
            # [terrain] quay_walls the ground under the water beside a quay lies quay_depth under the level, and a
            # deck whose nodes fell there stood 1 m over the river (Berlin's Weidendammer Brücke)
            import shapely
            wl = gpd.read_file(DATA / "ground.gpkg", layer="water")
            wl = wl[wl.area >= 200].reset_index(drop=True)
            lv = np.full(len(wl), np.nan)
            rng = np.random.default_rng(11)
            spans = {}
            for w in ways:
                key = span_of(w["tags"])[0] if w["elevated"] else None
                if key in ref:
                    spans.setdefault(key, []).extend(xy[n] for n in w["nodes"] if n in xy)
            tree = shapely.STRtree(wl.geometry.values)
            for key, pts in spans.items():
                P = np.asarray(pts)
                hit = tree.query(shapely.points(P), predicate="within")
                levels = []
                for i in np.unique(hit[1]):
                    if np.isnan(lv[i]):
                        g = wl.geometry.iloc[i]
                        x0, y0, x1, y1 = g.bounds
                        n = int(min(max(g.area / 25, 200), 20000))
                        q = np.column_stack([rng.uniform(x0, x1, n * 3), rng.uniform(y0, y1, n * 3)])
                        q = q[shapely.contains_xy(g, q[:, 0], q[:, 1])][:n]
                        if len(q) >= 20:
                            v, c = np.unique(np.round(terrain.height_utm(q[:, 0], q[:, 1]), 2), return_counts=True)
                            lv[i] = v[np.argmax(c)] if c.max() >= 0.3 * len(q) else -np.inf
                    if np.isfinite(lv[i]):
                        levels.append(lv[i])
                if levels:
                    ref[key] = max(levels)
    # {deck, reach}: the deck stands `deck` over the highest ground within `reach` m along it, so a viaduct
    # keeps its height over a cutting it crosses (Métro 2 over the Gare du Nord's and the Gare de l'Est's tracks)
    # instead of following the ground down into it
    high = {}
    for key, d in DECKS.items():
        if isinstance(d, dict) and "reach" in d:
            from scipy.spatial import cKDTree
            ns = sorted({n for w in ways if w["elevated"] and span_of(w["tags"])[0] == key for n in w["nodes"]},
                        key=str)
            if ns:
                P = np.array([xy[n] for n in ns])
                G = np.array([ground[n] for n in ns])
                for n, nb in zip(ns, cKDTree(P).query_ball_point(P, float(d["reach"]))):
                    high[n] = float(G[nb].max())
    for w in ways:
        target = deck_target(w["tags"]) if w["elevated"] else None
        if target is None:
            continue
        key = span_of(w["tags"])[0]
        hold = held.get(key)
        over = over_water(w["tags"])
        for n in w["nodes"]:
            t = over if over is not None and n in wet else target
            cap = max(ref[key] + t, ground[n] + 1.0) if key in ref else high.get(n, ground[n]) + t
            top[n] = min(top[n], cap)
            if hold:
                a, b, s0, s1 = hold
                L = np.linalg.norm(b - a)
                s = float(np.dot(np.asarray(xy[n]) - a, (b - a) / L))
                if -s0 <= s <= L + s1:
                    top[n] = max(target, ground[n] + 3.0)     # over the water (scene y 0), as the cables are
    # from the held decks the approaches come down no steeper than GRADE (a few sweeps along the ways, both
    # ways, until nothing rises)
    named = [w for w in ways if w["elevated"] and span_of(w["tags"])[0] in held]
    for _ in range(20):
        changed = False
        for w in named:
            ns = w["nodes"]
            for seq in (ns, ns[::-1]):
                for a, b in zip(seq[:-1], seq[1:]):
                    lim = top[a] - GRADE * float(np.hypot(*np.subtract(xy[a], xy[b])))
                    if lim > top[b] + 0.01:
                        top[b], changed = lim, True
        if not changed:
            break
    # [roads] decks_ease: the span's approaches climb to a higher deck end at GRADE (its pinned ends left alone)
    eased = [(w, float(DECKS_EASE[span_of(w["tags"])[0]])) for w in ways
             if w["elevated"] and span_of(w["tags"])[0] in DECKS_EASE]
    raised = set()
    for _ in range(100):
        changed = False
        for w, gr in eased:
            ns = w["nodes"]
            for seq in (ns, ns[::-1]):
                for a, b in zip(seq[:-1], seq[1:]):
                    lim = top[a] - gr * float(np.hypot(*np.subtract(xy[a], xy[b])))
                    if lim > top[b] + 0.01 and h[b] > 0:
                        top[b], changed = lim, True
                        raised.add(b)
        if not changed:
            break
    if eased:
        print(f"decks_ease: {len(raised)} nodes of {len(eased)} ways raised to their spans' grades")

    # {deck, ..., level_on: "<bridge>"}: the span's nodes over that bridge's man_made=bridge outline held level at their
    # highest there, the approaches coming down from it no steeper than GRADE (the U1 on the Oberbaumbrücke's arcade:
    # pinned to the ground at Warschauer Straße, it had sloped 4 m over the bridge and met the road deck at its end)
    lv = {k: d["level_on"] for k, d in DECKS.items() if isinstance(d, dict) and d.get("level_on")}
    if lv:
        import shapely
        polys = outline_polys(bbox)
        for key, bridge in lv.items():
            sel = [p for t, p in polys if (t.get("name") or "") == bridge]
            if not sel:
                print(f"level_on: no outline named {bridge}")
                continue
            poly = shapely.union_all(sel)
            mine = [w for w in ways if w["elevated"] and span_of(w["tags"])[0] == key]
            on = {n for w in mine for n in w["nodes"] if poly.contains(shapely.Point(xy[n]))}
            if not on:
                continue
            hi = max(top[n] for n in on)
            for n in on:
                top[n] = hi
            for _ in range(50):
                changed = False
                for w in mine:
                    for seq in (w["nodes"], w["nodes"][::-1]):
                        for a, b in zip(seq[:-1], seq[1:]):
                            lim = top[a] - GRADE * float(np.hypot(*np.subtract(xy[a], xy[b])))
                            if lim > top[b] + 0.01:
                                top[b], changed = lim, True
                if not changed:
                    break
            print(f"level_on: {key} held at {hi:.1f} m over {len(on)} nodes on {bridge}")
    if RAIL_ON:
        rail_on_structures(ways, xy, top, terrain)

    # a suspension bridge's roadways where its structure has them ([[structures]] roadways = {centre, width}):
    # OSM draws the carriageways where their mappers put them, not symmetric about the towers the trusses and
    # cables are built on (the Brooklyn Bridge's at -7.7 and +9.0 m, 11.6 and 8.4 m wide, so its promenade stood
    # over one roadway): between the anchorages each is moved to +-centre from the towers' line, fading back
    # to where OSM has it over ALIGN_TAPER m beyond
    ALIGN_TAPER = 80.0
    widths = {}
    for st in CFG.get("structures", []):
        rw = st.get("roadways")
        if not rw or st["name"] not in held:
            continue
        a, b, s0, s1 = held[st["name"]]
        L = np.linalg.norm(b - a)
        u = (b - a) / L
        nrm = np.array([-u[1], u[0]])
        moved = set()
        for w in ways:
            if not w["elevated"] or span_of(w["tags"])[0] != st["name"]:
                continue
            widths[w["id"]] = float(rw["width"])
            for n in w["nodes"]:
                if n in moved:
                    continue
                p = np.asarray(xy[n], dtype=float)
                s, d = float(np.dot(p - a, u)), float(np.dot(p - a, nrm))
                out = max(-s0 - s, s - (L + s1), 0.0)
                k = max(0.0, 1.0 - out / ALIGN_TAPER)
                if k > 0 and abs(d) > 0.5:
                    xy[n] = tuple(p + nrm * (np.sign(d) * float(rw["centre"]) - d) * k)
                    moved.add(n)
        print(f"roadways of {st['name']}: {len(moved)} nodes moved to +-{rw['centre']} m of the towers' line")

    rows = []
    for w in ways:
        if w["kind"] is None or w["tunnel"]:
            continue
        pts = [xy[n] for n in w["nodes"]]
        # the clearance kept over crests: the deck's rise, no more than a named deck stands over its ground
        geom = deck_line(pts, [top[n] for n in w["nodes"]], [min(h[n], max(top[n] - ground[n], 0.0)) for n in w["nodes"]],
                         terrain) \
            if w["elevated"] else LineString(pts)
        t = w["tags"]
        span = span_of(t)[0] if w["elevated"] else None
        rows.append({"osm_id": w["id"], "kind": w["kind"], "highway": t.get("highway") or t.get("railway"),
                     "name": t.get("name"), "span": span, "width": widths.get(w["id"], width(t, w["kind"])), "elevated": w["elevated"],
                     "geometry": geom})
    g = gpd.GeoDataFrame(rows, crs=UTM)
    if FOOTBRIDGES:
        # a footway or cycleway along a road bridge (its pavement or cycle track, mapped apart) is part of the
        # road's deck already: dropped where mostly within the road deck's width plus 8 m
        fb = g.osm_id.isin({el["id"] for el in foot}) & g.elevated
        roads_el = g[g.elevated & ~fb & (g.kind != "rail")]
        if fb.any() and len(roads_el):
            import shapely
            cover = shapely.union_all(shapely.buffer(np.asarray(list(roads_el.geometry.force_2d()), dtype=object),
                                                     roads_el.width.values / 2 + 8.0, cap_style="flat"))
            share = g[fb].geometry.force_2d().intersection(cover).length / g[fb].geometry.length.clip(lower=1e-6)
            drop = share[share > 0.5].index
            g = g.drop(drop)
            print(f"footbridges: {len(drop)} along road bridges left to the road's deck, {int(fb.sum()) - len(drop)} kept")
    g = g[g.intersects(near)]
    flat = ~g.elevated
    g.loc[flat, "geometry"] = g.loc[flat].geometry.intersection(near)
    if BUILT_ONLY:
        from .masses import clip as masses_clip
        built = boundary().geometry.iloc[0]
        mc = masses_clip()
        if mc is not None:
            built = built.union(mc)
        g, cut_km = built_only(g, built, BUILT_ONLY)
        print(f"built_only: {cut_km:,.0f} km of ground ways cut beyond the districts and masses "
              f"(+{BUILT_ONLY.get('margin', 50.0):g} m)")
    if DALLES:
        from shapely.geometry import Polygon
        to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
        slab = gpd.GeoSeries([Polygon([to.transform(lo, la) for lo, la in r]) for r in DALLES], crs=UTM).union_all()
        under = flat & g.intersects(slab)
        g.loc[under, "geometry"] = g.loc[under].geometry.difference(slab)
        print(f"dalles: {int(under.sum())} ground-level ways cut where they run under the slab")
    g = g.explode(index_parts=False)
    g = g[(g.geom_type == "LineString") & (g.length > 1)].reset_index(drop=True)

    out = DATA / "roads.gpkg"
    out.unlink(missing_ok=True)
    g.to_file(out, layer="ways")
    if OUTLINES:
        outlines(g, bbox, near).to_file(out, layer="outlines")
    km = g.assign(km=g.length / 1000).groupby(["kind", "elevated"]).km.sum().unstack(fill_value=0)
    print(f"{len(g):,} ways; km by kind (columns: elevated):\n{km.round(0).to_string()}")
    el = g[g.elevated]
    zmax = el.geometry.apply(lambda l: max(c[2] for c in l.coords))
    print(f"elevated: {len(el):,} ways, deck height (scene y) max {zmax.max():.1f} m, "
          f"median of way maxima {zmax.median():.1f} m")

