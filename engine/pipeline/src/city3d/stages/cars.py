"""06d_cars: cars for the viewer: traffic in every lane of the road network, parked cars along minor streets and
in car parks, bus stations full of buses.

Like the trees, the cars are plausible, not mapped: nobody knows where a city's cars are at a given
moment, so they are placed where they would be. Vehicle types, colours, speeds, the traffic mix and kerbside
parking odds are the region preset's ([cars]); the driving side is city.toml's drive. As built for Shenzhen:
aerial photos of Shenzhen show mostly white, black,
silver and grey cars, many blue-and-white BYD e6 taxis (red ones in the old city, a few green), green
or blue BYD buses, white vans, and trucks and container lorries on the expressways, heaviest near the
ports (Shekou, Chiwan, Dachan Bay, the airport's cargo area). Minor streets, above all in the urban
villages, are lined with parked cars; surface car parks are full in the day.

Moving traffic. The roads (roads.gpkg, with 06b_markings.py's reading of the cached OSM tags: lanes,
one-way) are first joined into chains where two ways simply continue each other (same lane count and
direction), so traffic doesn't stop where OSM splits a way for a tag change, then split at junctions and
cut back from them exactly like the markings. Each piece gets lanes (driving on the right; lane centres
where 06b_markings.py paints the lane lines), and each lane is a loop: a car drives along it, into the
junction box a little, fades out, and comes back at the other end fading in out of the previous
junction. Cars never overtake within a lane, so they only need a place in the loop: the viewer moves
all of a lane's cars in step along a "free" coordinate p (metres at free-flow speed) and maps p to the
distance s along the lane through a speed profile that slows to a crawl (factor k) at the stop line of
signalled junctions and speeds up again beyond it; cars bunch into a queue there and pull away. Gaps in
p are at least a car length plus 2 m divided by k, so even queued cars never touch.

Density per lane follows the road class and an "activity" field (floor area of the buildings around,
blurred over some 400 m): Futian CBD and the centres of Bao'an and Nanshan are busy, the edges quiet.
Vehicle mix follows the class, the lane (buses and lorries keep right) and the distance to the ports.

Parked cars. Ground-level minor and service streets get a kerbside row on one or both sides (more in
urban villages and residential areas, fewer on through roads), where the carriageway leaves room for
the traffic, which then moves inwards. OSM surface car parks (amenity=parking, not underground,
multi-storey or rooftop) are filled with rows of stalls along their long axis, and bus stations with
buses. Nothing is placed over water or on buildings.

Driving on the left, lanes and parked rows are mirrored about each road's centre line.
A one-way carriageway of a dual road keeps its lanes on its own side of the midline to the other carriageway
where OSM's two centre lines lie closer than their widths (twin_limits).

Output, cars/ in the data folder (the viewer reads it through web/cars, a link this stage makes):
  cars.json        index: origin, tile size, vehicle types (name, length, width, height), colour
                   palettes per type (sRGB pairs: body and second colour, e.g. a taxi's white roof, a
                   bus's livery, a lorry's container), the tiles with their counts
  c_<tx>_<ty>.bin  per 1 km tile (06_tiles.py's grid; a lane goes to the tile of its middle), gzip of
                     u32 lanes L, points P, moving cars M, parked cars Q
                     per lane: u16 points, u16 cars, u8 speed (0.2 m/s), u8 k (queue speed x 100; 100:
                       none), u8 ramp D (m, slowing before the stop line), u8 spare, u16 stop (dm along
                       the lane; beyond it the car accelerates again until the lane ends)
                     points: x, z relative to the tile's north-west corner in dm (int16 differences to
                       the previous point, low bytes then high bytes), y in cm (u16, the same split)
                     moving cars, grouped by lane: u16 p (dm in the lane's free coordinate), u8 type,
                       u8 colour index into the type's palette
                     parked cars: x, z as the points, y in cm (u16 split), u8 heading (256ths of a turn, 0 = east, then
                       towards south), u8 type, u8 colour
Heading convention: a car's forward direction is (cos a, sin a) in scene (x, z), x east, z south.

Needs 06_tiles.py's inputs only (roads.gpkg, buildings.gpkg, landuse.gpkg, ground.gpkg) plus the parking
areas, fetched once from Overpass and cached in raw/osm_parking.json.
"""
import gzip
import json
import math
from collections import defaultdict

import geopandas as gpd
import numpy as np
import rasterio.features
import shapely
from affine import Affine
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from ..common import CFG, DATA, RAW, UTM, UTM_EPSG, Terrain, boundary, element_geoms, link_web, overpass
from . import markings as mk

CA = CFG["cars"]
tiles06 = mk.tiles06
TILE, ROAD_Y, to_scene = tiles06.TILE, tiles06.ROAD_Y, tiles06.to_scene

OUT = DATA / "cars"
CACHE = RAW / "osm_parking.json"
CAR_Y = ROAD_Y + mk.OVER_Y           # cars stand on the markings layer (on bridges: deck + the same)
CHUNK = 2000.0                       # longest lane loop; longer pieces are cut (cars fade there)
FADE = 4.0                           # metres over which a car fades in at a lane's start and out at its end
INTO_JUNCTION = 5.0                  # lanes reach this far into the junction box at either end
MIN_LANE = 12.0
LANE_STEP = 10.0                     # metres between lane points on sloping ground
SEED = CA["seed"]
SIDE = 1 if CFG["drive"] == "right" else -1     # lane and parking offsets are mirrored driving on the left
PARKING_MARGIN = CA["parking_margin"]            # car parks are fetched this far beyond the districts' box

# vehicle types: name, length, width, height (m); the viewer builds its models to these sizes (by name,
# in this order: web/cars.js)
# (an optional fifth item names the viewer's model for the type, e.g. "hatch" for a sedan-sized two-box car)
TYPES = [tuple(t[:4]) for t in CA["types"]]
MODEL = [t[4] if len(t) > 4 else None for t in CA["types"]]
T = {name: i for i, (name, *_) in enumerate(TYPES)}
LEN = np.array([t[1] for t in TYPES])
# the bus types: "bus" and any type named bus_* (Berlin: bus_art, the articulated bus; bus_dd, the double-decker)
BUSES = [i for i, (n, *_) in enumerate(TYPES) if n == "bus" or n.startswith("bus_")]
HEAVY = BUSES + [T[n] for n in ("truck", "lorry") if n in T]       # kept to the kerb lane of big roads
COMMERCIAL = [T[n] for n in ("van",) if n in T] + BUSES + [T[n] for n in ("truck", "lorry") if n in T]
MOTO = T.get("moto")                                               # two-wheelers (optional type)

# colour palettes per type: (body sRGB, second colour or "" for none, weight); Shenzhen's taxis are
# blue-and-white BYD e6 (most), red, green
PALETTES = {k: [(a, b or None, w) for a, b, w in v] for k, v in CA["palettes"].items()}

# per road class: free-flow speed (m/s), mean gap front to front (m, per lane at activity 1), queue
# factor at signalled junction ends, and the vehicle mix (sedan, suv, taxi, van, bus, truck, lorry)
# (mixes shorter than the type list leave the types after them out: trams, extra bus types)
pad = lambda m: tuple(m) + (0.0,) * (len(TYPES) - len(m))
CLASS = {k: (v[0], v[1], v[2], pad(v[3])) for k, v in CA["class"].items()}
LINK_SPEED = CA["link_speed"]
PARKED_MIX = pad(CA["parked_mix"])
CARS_ONLY = CA.get("cars_only", [])
# [cars] deck_ends: where a ground road meets a bridge deck the lane takes the deck's height at their shared node,
# not the ground's there (off by default). Beside a quay wall the ground at a bridge's end can read the river bed
# (Berlin's Admiralbrücke: 6.5 m deck, -0.7 m ground at its end node): cars sank metres into the deck towards it.
DECK_ENDS = bool(CA.get("deck_ends", False))
ONEWAY_BOTH = CA.get("oneway_both_sides", False)
KERB_OCC = CA.get("kerb_occupancy", 0.55)         # share of a parked row's slots taken (before village and activity)
# ... and at most ([cars] kerb_occupancy_max, 0.95 by default: Berlin 0.82, the M6 critic's 15-25 % of slots empty)
KERB_OCC_MAX = CA.get("kerb_occupancy_max", 0.95)
# [cars] stop_clear (m, off by default): queues stop this much further back (a half car length: the queue profile
# centres the first car on its stop point), and a crossing's length back on every arm, not only where a zebra is
# mapped (06b_markings draws a Furt and a stop line at every signalled arm; Berlin M5 critic: a van on the Furt)
STOP_CLEAR = CA.get("stop_clear", 0.0)
# Paris (all off by default): free-flow speed from OSM maxspeed (x this factor; 0: the class table's), kerbside
# rows on the major classes the kerbside table names too, OSM's parking:* tags deciding a side where tagged,
# no rows on ways of these names, ways open to residents/permits only (motor_vehicle=destination;permit: the Rue
# de Rivoli) with their own mix and density, two-wheeler bays in the kerbside rows
MAXSPEED_K = CA.get("maxspeed_factor", 0.0)
KERB_MAJOR = CA.get("kerbside_major", False)
OSM_PARKING = CA.get("osm_parking", False)
NO_KERBSIDE = CA.get("no_kerbside", [])
RESTRICTED_MIX = pad(CA["restricted_mix"]) if CA.get("restricted_mix") else ()
RESTRICTED_DENS = CA.get("restricted_density", 0.4)
MOTO_BAYS = CA.get("moto_bays", 0.0) if MOTO is not None else 0.0   # chance a kerbside slot holds a bay of two-wheelers
# ways closed to motor vehicles but designated for buses (psv/bus=designated: the Pont d'Iéna) carry buses and
# taxis at this density factor (0: none, as any car-free way)
PSV_DENS = CA.get("psv_density", 0.0)
# OSM's kerbside parking polygons (amenity=parking + parking=street_side/lane/on_kerb/half_on_kerb: Paris maps
# ~3,300 of them) are a strip along a kerb, not a lot: "row" parks one file along the strip's long axis (off:
# filled as a car park, rows of stalls across the strip, which read as a car park spilling over the lanes)
STREET_SIDE_ROW = CA.get("street_side_lots", "lot") == "row"
# [cars] lot_capacity (opt-in, Singapore 7 Oct): a surface car park holds no more cars than its OSM capacity
# (capacity:motorcar, else capacity) where tagged: the stall grid over a lot drawn with its planted islands and
# lawns filled Gardens by the Bay's Meadow car park (284 bays) with ~500. Off (default): the grid's occupancy only
LOT_CAPACITY = CA.get("lot_capacity", False)
# [ground] lots_off_green puts the car parks inside a park on the asphalt layer (viewer 0.25 m): their cars stand on it
LOTS_ASPHALT = CFG["ground"].get("lots_off_green", False)
STREET_SIDE = {"street_side", "lane", "on_kerb", "half_on_kerb", "layby"}
BIG_ROADS = {"motorway", "trunk", "primary", "secondary"}
# [cars] none_in = {name = [[lon, lat], ...]}: no cars inside (ways whose middle point lies inside carry none,
# car parks and bus stations there stay empty): building sites, car parks on decks drawn at ground level
NONE_IN = (gpd.GeoSeries([Polygon(r) for r in CA.get("none_in", {}).values()], crs="EPSG:4326").to_crs(UTM)
           .union_all() if CA.get("none_in") else None)
KERBSIDE = CA["kerbside"]        # chance a side of a ground-level street has a parked row, by its class

# kerbside parking: chance a side of a ground-level street has a row, by what is around it
PARK_W = CA.get("park_w", 2.2)   # the row's width
PARK_PITCH = tuple(CA.get("park_pitch", (5.6, 7.0)))   # front-to-front spacing along the kerb
LANE_MIN = 2.7                   # narrowest lane that still takes moving traffic
LANE_SMALL = 2.5                 # ... as a single file between parked rows on a small street
# dual carriageways (twin_limits): a one-way way running the other way within this much beyond a piece's
# half-width (the widest half-width a way gets) and at least TWIN_MIN_GAP from it (closer: one road drawn
# twice) takes its share of the overlap; a carriageway keeps at least TWIN_MIN_HALF m on that side
TWIN_REACH, TWIN_MIN_GAP, TWIN_MIN_HALF, TWIN_COS = 12.0, 2.0, 1.5, 0.85
# ([cars] twin_limits, off by default so other cities' cars stay as they are until they opt in: London M6 fix round)
TWINS = CA.get("twin_limits", False)
# [cars.bus_routes] (off by default): buses only on the ways OSM's bus routes (route=bus relations, cached in the
# data folder's osm_bus_routes.json) take, at least `min` (a mix weight) there; the bus types share it by `split`
# ({type: weight}); a double-deck type (`dd`, e.g. "bus_dd") only on ways carrying a route whose ref is in
# `dd_refs`, taking `dd_share` of the buses there; `networks`: only routes whose network tag names one; `skip`: refs starting so (night lines) left out (London M6 critic: no buses on the bus corridors, buses on side
# streets)
BUS_ROUTES = CA.get("bus_routes") or {}
# [cars.trams] (off by default): trams on OSM's railway=tram ways (not sidings, yards or depots), each an
# articulated train of `modules` (type names, rear to front: each module is a car of the lane, so the train bends
# on curves), `gap` m apart, at `speed` m/s, one train every `spacing` m (mean) per track; a track's direction:
# with the other track of the pair on its left driving on the right (on its right driving on the left), a lone
# track either way
TRAMS = CA.get("trams") or {}
# [[cars.areas]] (off by default; Hong Kong M6): parts of the city with their own livery mix: districts = [names in
# boundary.gpkg] or ring = [[lon, lat], ...], and weights = {type = [a weight per entry of the type's palette]}: a moving
# car takes its lane's middle, a parked car its own place; the first area holding it wins, elsewhere the palette's own
# weights (green New Territories taxis in Sai Kung, Citybus on the island and KMB in Kowloon)
AREAS = CA.get("areas") or []
STALL_W, STALL_L, AISLE = 2.5, 5.0, 6.0
BUS_STALL_W, BUS_STALL_L, BUS_AISLE = 3.8, 13.0, 14.0


# ---------------------------------------------------------------- inputs

def fetch_bus_routes(bb: str) -> dict:
    """OSM way id -> set of the bus routes' refs on it ([cars.bus_routes]), from route=bus relations, cached."""
    cache = DATA / "osm_bus_routes.json"
    if cache.exists():
        res = json.loads(cache.read_text())
    else:
        res = overpass(f'[out:json][timeout:300][bbox:{bb}];rel["route"="bus"];out body;')
        cache.write_text(json.dumps(res))
    routes = defaultdict(set)
    for e in res["elements"]:
        if e["type"] != "relation":
            continue
        ref = str(e.get("tags", {}).get("ref", ""))
        nets = BUS_ROUTES.get("networks")         # (only these networks' routes: not the coach lines)
        if nets and not any(n in str(e.get("tags", {}).get("network", "")) for n in nets):
            continue
        if any(ref.startswith(p) for p in BUS_ROUTES.get("skip", [])):      # (night lines: "N")
            continue
        for m in e.get("members", []):
            if m["type"] == "way" and m.get("role", "") in ("", "forward", "backward"):
                routes[m["ref"]].add(ref)
    print(f"bus routes: {sum(1 for e in res['elements'] if e['type'] == 'relation'):,} relations on {len(routes):,} ways")
    return routes


def bus_route_mix(mix, rec):
    """[cars.bus_routes]: the bus types' weights in a lane's mix (in place) by the bus routes on its way."""
    refs = rec.get("routes") or set()
    w = float(mix[BUSES].sum())
    mix[BUSES] = 0
    if not refs:
        return
    w = max(w, BUS_ROUTES.get("min", 3.0))
    split = {T[k]: v for k, v in BUS_ROUTES.get("split", {"bus": 1.0}).items() if k in T}
    dd = T.get(BUS_ROUTES.get("dd", ""))
    dd_on = dd is not None and bool(refs & set(BUS_ROUTES.get("dd_refs", [])))
    if dd is not None:
        split.pop(dd, None)
    tot = sum(split.values()) or 1.0
    share = BUS_ROUTES.get("dd_share", 0.5) if dd_on else 0.0
    for i, v in split.items():
        mix[i] = w * (1 - share) * v / tot
    if dd_on:
        mix[dd] = w * share


def tram_lanes(terrain, origin, tile_of, rng):
    """[cars.trams]: lanes along OSM's tram tracks, each holding trams as trains of module cars. Returns
    [(tile, (points, speed, k, D, stop, p, types))], the lanes' format."""
    tags = mk.osm_tags()
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ways = ways[(ways.kind == "rail") & (ways.highway == "tram")].reset_index(drop=True)
    keep = [not tags.get(o, {}).get("service") and tags.get(o, {}).get("usage") != "industrial"
            and "depot" not in str(tags.get(o, {}).get("name", "")).lower() for o in ways.osm_id]
    ways = ways[np.array(keep, bool)].reset_index(drop=True)
    lines = list(ways.geometry)
    tree = shapely.STRtree([LineString(np.asarray(g.coords)[:, :2]) for g in lines])
    recs = []
    lone = 0
    for i, g in enumerate(lines):
        c = np.asarray(g.coords, float)
        if c.shape[1] == 2:
            c = np.column_stack([c, terrain.height_utm(c[:, 0], c[:, 1]), np.ones(len(c))])
        else:
            c = np.column_stack([c, np.zeros(len(c))])
        if len(c) < 2:
            continue
        # the partner track: the nearest other tram way 1.5-10 m from the middle (stops part the tracks round an island)
        l2 = LineString(c[:, :2])
        mid = l2.interpolate(0.5, normalized=True)
        a = np.asarray(l2.interpolate(max(l2.project(mid) - 2, 0)).coords[0])
        b = np.asarray(l2.interpolate(min(l2.project(mid) + 2, l2.length)).coords[0])
        t = (b - a) / max(np.linalg.norm(b - a), 1e-6)
        side = 0
        best = 1e9
        for j in tree.query(mid.buffer(10.0)):
            if j == i:
                continue
            o = tree.geometries[j]
            q = o.interpolate(o.project(mid))
            d = mid.distance(o)
            if 1.5 < d < 10.0 and d < best:
                pq = o.project(q)
                ta = np.asarray(o.interpolate(min(pq + 2, o.length)).coords[0]) - np.asarray(o.interpolate(max(pq - 2, 0)).coords[0])
                if abs(ta @ t) < 0.8 * max(np.linalg.norm(ta), 1e-6):      # crossing, not alongside
                    continue
                dv = np.asarray(q.coords[0]) - np.asarray(mid.coords[0])
                best, side = d, np.sign(t[0] * dv[1] - t[1] * dv[0])      # > 0: the partner is on the left
        if side == 0:
            lone += 1
            side = 1 if rng.random() < 0.5 else -1
        if side * SIDE < 0:
            c = c[::-1]
        recs.append(c)
    # join ways that continue each other (one way in, one way out at a node)
    key = lambda p: (round(p[0], 1), round(p[1], 1))
    starts, ends = defaultdict(list), defaultdict(list)
    for i, c in enumerate(recs):
        starts[key(c[0])].append(i)
        ends[key(c[-1])].append(i)
    nxt = {i: starts[key(c[-1])][0] for i, c in enumerate(recs) if len(starts[key(c[-1])]) == 1 and len(ends[key(c[-1])]) == 1}
    has_prev = set(nxt.values())
    seen, chains_ = set(), []
    for i in [i for i in range(len(recs)) if i not in has_prev] + list(range(len(recs))):
        if i in seen:
            continue
        ch = [i]
        seen.add(i)
        while ch[-1] in nxt and nxt[ch[-1]] not in seen:
            ch.append(nxt[ch[-1]])
            seen.add(ch[-1])
        chains_.append(np.vstack([recs[ch[0]]] + [recs[j][1:] for j in ch[1:]]))
    mods = [T[m] for m in TRAMS["modules"]]
    gap = TRAMS.get("gap", 0.25)
    offs = np.cumsum([0.0] + [(LEN[a] + LEN[b]) / 2 + gap for a, b in zip(mods[:-1], mods[1:])])
    train = offs[-1] + (LEN[mods[0]] + LEN[mods[-1]]) / 2
    spacing, v0 = TRAMS.get("spacing", 600.0), TRAMS.get("speed", 7.0)
    out, n_trams, km = [], 0, 0.0
    for c in chains_:
        s = cum(c)
        L = s[-1]
        if L < train + 20:
            continue
        nch = max(1, int(np.ceil(L / CHUNK)))
        for q in range(nch):
            ca, cb = L * q / nch, L * (q + 1) / nch
            cp, cs2 = mk.cut(c, s, ca, cb)
            Lc = cs2[-1] - cs2[0]
            if Lc < train + 10:
                continue
            km += Lc / 1000
            ps, ty = [], []
            p = rng.uniform(0, spacing)
            while p + train < Lc:
                ps += list(p + offs)
                ty += mods
                n_trams += 1
                p += train + 10 + rng.exponential(max(spacing - train - 10, 1.0))
            if not ps:
                continue
            mid_pt = cp[len(cp) // 2]
            cp = lane_points(cp, terrain)
            scene = to_scene(cp[:, :2], origin)
            y = cp[:, 2] + CAR_Y
            v = v0 * rng.uniform(0.9, 1.1)
            out.append((tile_of(*mid_pt[:2]), (np.column_stack([scene[:, 0], y, scene[:, 1]]), v, 1.0, 1.0,
                                               round(float(Lc), 1), np.array(ps), np.array(ty))))
    print(f"trams: {len(ways):,} tram ways ({lone} lone tracks), {len(chains_):,} tracks, {km:.1f} km of lanes, "
          f"{n_trams:,} trams")
    return out


def fetch_parking(bb: str) -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    res = overpass(f"""
        [out:json][timeout:900][bbox:{bb}];
        (
          way["amenity"="parking"];
          relation["amenity"="parking"]["type"="multipolygon"];
          way["amenity"="bus_station"];
          way["landuse"="port"];
          relation["landuse"="port"];
          way["industrial"="port"];
        );
        out geom;
    """)
    CACHE.write_text(json.dumps(res))
    return res


def areas(res: dict):
    """Car parks (polygon, kind 'car' or 'bus') and port polygons from the cached answer, in UTM."""
    lots, ports, caps = [], [], {}
    for t, g in element_geoms(res):
        if g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        if t.get("landuse") == "port" or t.get("industrial") == "port":
            ports.append(g)
            continue
        if t.get("amenity") == "bus_station":
            lots.append(("bus", g))
            continue
        kind = t.get("parking", "surface")
        if kind in ("underground", "multi-storey", "rooftop", "garage_boxes", "carports") or "building" in t:
            continue
        if (mk.number(t.get("layer")) or 0) != 0 or t.get("access") == "private" and kind == "garage":
            continue
        lots.append(("row" if STREET_SIDE_ROW and kind in STREET_SIDE else "car", g))
        if LOT_CAPACITY:
            caps[len(lots) - 1] = mk.number(t.get("capacity:motorcar", t.get("capacity")))
    # [cars] none_in: car parks and bus stations whose middle lies in one of these lon/lat rings are left empty
    # (London: a car park on the deck over Victoria's platforms, drawn at the tracks' level; a cleared site)
    for name, ring in CA.get("none_in", {}).items():
        poly = Polygon(ring)
        n = len(lots)
        keep = [i for i, (k, g) in enumerate(lots) if not poly.contains(g.representative_point())]
        caps = {j: caps[i] for j, i in enumerate(keep) if i in caps}
        lots = [lots[i] for i in keep]
        print(f"no cars in {name}: {n - len(lots)} car parks left empty")
    to = lambda gs: gpd.GeoSeries(gs, crs="EPSG:4326").to_crs(UTM).make_valid()
    lot_g = to([g for _, g in lots]) if lots else gpd.GeoSeries([], crs=UTM)
    return [(k, g, caps.get(i)) for i, ((k, _), g) in enumerate(zip(lots, lot_g))], \
        (unary_union(to(ports).values) if ports else None)


class Field:
    """A raster over the scene area, sampled at UTM points."""

    def __init__(self, arr, x0, y1, cell):
        self.a, self.x0, self.y1, self.cell = arr, x0, y1, cell

    def __call__(self, x, y):
        c = np.clip(((np.asarray(x) - self.x0) / self.cell).astype(int), 0, self.a.shape[1] - 1)
        r = np.clip(((self.y1 - np.asarray(y)) / self.cell).astype(int), 0, self.a.shape[0] - 1)
        return self.a[r, c]


def blur(a, radius_cells, passes=3):
    """Approximate Gaussian blur: repeated box filters (separable, via cumulative sums)."""
    k = 2 * radius_cells + 1
    for _ in range(passes):
        for axis in (0, 1):
            p = np.pad(a, [(radius_cells + 1, radius_cells)] * 1 + [(0, 0)] if axis == 0 else
                       [(0, 0), (radius_cells + 1, radius_cells)], mode="edge")
            c = np.cumsum(p, axis=axis)
            a = (np.take(c, range(k, c.shape[axis]), axis=axis) - np.take(c, range(0, c.shape[axis] - k), axis=axis)) / k
    return a


def activity_fields(bounds):
    """Activity (floor area around, 0..~1.3) and urban-village share, from the building table."""
    b = gpd.read_file(DATA / "buildings.gpkg", columns=["h", "kind"]).to_crs(UTM)
    x0, y0, x1, y1 = bounds
    cell = 50.0
    W, H = int(np.ceil((x1 - x0) / cell)), int(np.ceil((y1 - y0) / cell))
    tr = Affine(cell, 0, x0, 0, -cell, y1)
    area = b.geometry.area.values
    floors = np.clip(b.h.values / 3.2, 1, 120)
    fa = rasterio.features.rasterize(
        ((g, v) for g, v in zip(b.geometry.centroid.values, area * floors)), out_shape=(H, W), transform=tr,
        merge_alg=rasterio.enums.MergeAlg.add, dtype="float32")
    vil = b.kind.values == "village"
    va = rasterio.features.rasterize(
        ((g, v) for g, v in zip(b.geometry.centroid.values[vil], area[vil])), out_shape=(H, W), transform=tr,
        merge_alg=rasterio.enums.MergeAlg.add, dtype="float32")
    fa = blur(fa / cell ** 2, 4)                     # floor area ratio, blurred over ~400 m
    va = blur(va / cell ** 2, 2)                     # village footprint share, ~200 m
    ref = np.percentile(fa[fa > 0.05], 92)
    act = np.clip(fa / ref, 0, 1.3)
    return Field(act, x0, y1, cell), Field(np.clip(va / 0.35, 0, 1), x0, y1, cell)


def landuse_at(xy):
    """Land use per point (residential, industrial, commercial, civic or '')."""
    lu = gpd.read_file(DATA / "landuse.gpkg")
    tree = shapely.STRtree(lu.geometry.values)
    pts = shapely.points(xy)
    pi, gi = tree.query(pts, predicate="within")
    out = np.full(len(xy), "", dtype=object)
    order = np.argsort(-lu.geometry.area.values[gi])            # smaller areas win (written last)
    out[pi[order]] = lu.use.values[gi[order]]
    return out


# ---------------------------------------------------------------- road network

PARK_NO = {"no", "no_parking", "no_stopping", "separate", "fire_lane", "no_standing"}
PARK_YES = {"lane", "street_side", "yes", "parallel", "marked", "diagonal", "perpendicular", "half_on_kerb",
            "on_kerb", "shoulder", "inline", "painted_area_only"}


def osm_parking(t: dict):
    """Kerbside parking from OSM's parking:* tags (the 2022 scheme and the older parking:lane:*): per side of
    the way (left, right), True (a row), False (none) or None (not tagged)."""
    out = []
    for side in ("left", "right"):
        v = None
        for k in (f"parking:{side}", "parking:both", f"parking:lane:{side}", "parking:lane:both"):
            if k in t:
                v = t[k]
                break
        r = t.get(f"parking:{side}:restriction", t.get("parking:both:restriction"))
        if r in ("no_parking", "no_stopping", "no_standing") and v in (None, "yes", "lane", "street_side"):
            v = "no"
        out.append(None if v is None else (True if v in PARK_YES else False if v in PARK_NO else None))
    return tuple(out)


def maxspeed(t: dict):
    """OSM maxspeed in km/h (plain numbers, "mph" converted), or None."""
    v = str(t.get("maxspeed", "")).strip()
    try:
        return float(v.removesuffix("mph").strip()) * 1.609 if v.endswith("mph") else float(v)
    except ValueError:
        return None


def load_network(terrain: Terrain, routes=None):
    """Per way (as 06b_markings.py reads it): coordinates (x, y, height, 1 on the ground / 0 on a deck:
    the ground's height, or the deck's), class, width, one-way, lanes, reach."""
    tags = mk.osm_tags()
    routes = routes or {}
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ways = ways[ways.kind != "rail"].reset_index(drop=True)
    recs = []
    for r in ways.itertuples():
        t = tags.get(r.osm_id, {})
        c = np.asarray(r.geometry.coords, float)
        if c.shape[1] == 2:
            c = np.column_stack([c, terrain.height_utm(c[:, 0], c[:, 1]), np.ones(len(c))])
        else:
            c = np.column_stack([c, np.zeros(len(c))])
        ow = t.get("oneway")
        oneway = ow in ("yes", "1", "-1", "true") or (ow is None and (r.highway.startswith("motorway")
                                                                       or t.get("junction") == "roundabout"))
        if ow == "-1":
            c = c[::-1]
        park_lr = osm_parking(t)
        if ow == "-1":                                       # the way now runs the other way round
            park_lr = park_lr[::-1]
        keep = np.r_[True, np.linalg.norm(np.diff(c[:, :2], axis=0), axis=1) > 0.05]
        c = c[keep]
        if len(c) < 2:
            continue
        rec = {"c": c, "hw": r.highway, "kind": r.kind, "w": float(r.width), "elev": bool(r.elevated),
               "tags": t, "oneway": oneway, "access_no": t.get("access") in ("no", "private"),
               # no traffic: pedestrian streets, and roads closed to motor vehicles or open to authorised ones
               # only (Central Park's drives: motor_vehicle=no or private)
               "no_cars": r.highway == "pedestrian" or t.get("motor_vehicle") in ("no", "private")
               or t.get("motorcar") in ("no", "private") or t.get("access") == "no",
               # cars only: no lorries, trucks, vans or buses (hgv=no, goods=no, or [cars] cars_only by
               # name: the Brooklyn Bridge)
               "cars_only": t.get("hgv") == "no" or t.get("goods") == "no"
               or any(n in f"{t.get('bridge:name', '')} {t.get('name', '')}" for n in CARS_ONLY),
               "park_lr": park_lr, "maxspeed": maxspeed(t),
               "no_kerbside": any(n in t.get("name", "") for n in NO_KERBSIDE),
               # open to residents, deliveries, permit holders: buses, taxis and bikes mostly (the Rue de Rivoli)
               "restricted": any(v in str(t.get("motor_vehicle", "")) for v in ("destination", "permit", "delivery")),
               "psv": r.highway != "pedestrian" and (t.get("psv") in ("designated", "yes") or t.get("bus") in ("designated", "yes"))}
        if NONE_IN is not None and NONE_IN.contains(shapely.Point(*c[len(c) // 2, :2])):
            rec["no_cars"] = True                    # [cars] none_in: no traffic, no kerbside rows
        rec["routes"] = routes.get(r.osm_id)
        rec["sw"] = mk.sidewalks(t, r.highway, oneway, rec["elev"])
        rec["reach"] = rec["w"] / 2 + max(rec["sw"][0], rec["sw"][1])
        rec["lcode"] = mk.lane_code(t, rec["w"], oneway, r.highway)
        recs.append(rec)
    return recs


def junctions(recs):
    key = lambda p: (round(p[0], 2), round(p[1], 2))
    degree, touching, ends = defaultdict(int), defaultdict(set), defaultdict(list)
    for i, rec in enumerate(recs):
        c = rec["c"]
        for j, p in enumerate(c):
            k = key(p)
            degree[k] += 1 if j in (0, len(c) - 1) else 2
            touching[k].add(i)
        ends[key(c[0])].append((i, 0))
        ends[key(c[-1])].append((i, 1))
    return key, degree, touching, ends


def chains(recs, key, degree, ends):
    """Join ways that simply continue each other (a node shared by exactly two way ends, the same lane
    count and one-way status, one-way ways head to tail) into chains: lists of (way index, reversed)."""
    link = {}
    for k, es in ends.items():
        if degree[k] != 2 or len(es) != 2 or es[0][0] == es[1][0]:
            continue
        (i, ei), (j, ej) = es
        a, b = recs[i], recs[j]
        if a["oneway"] != b["oneway"] or (a["lcode"] & 31) != (b["lcode"] & 31):
            continue
        if (a["kind"] == "service") != (b["kind"] == "service"):
            continue
        if a["no_cars"] != b["no_cars"]:           # a car-free drive never takes a road's class through a chain
            continue
        if a["oneway"] and ei == ej:
            continue
        link[(i, ei)] = (j, ej)
        link[(j, ej)] = (i, ei)
    seen, out = set(), []
    for start in range(len(recs)):
        if start in seen:
            continue
        # walk back to the head of the chain: entering way i at its end `e`
        i, e, guard = start, 0, set()
        while (i, e) in link and i not in guard:
            guard.add(i)
            j, ej = link[(i, e)]
            if j in guard or j in seen:
                break
            i, e = j, 1 - ej
        chain, cur, enter = [], i, e
        while cur is not None and cur not in seen:
            seen.add(cur)
            chain.append((cur, enter == 1))           # entered at its end: reversed
            nxt = link.get((cur, 1 - enter))
            cur, enter = (nxt if nxt else (None, 0))
        out.append(chain)
    return out


def offset_line(p, a):
    """Polyline p (N x 2, scene or UTM) shifted a[i] metres to the left of its direction (mitred)."""
    d = np.diff(p, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True).clip(1e-9)
    seg_n = np.stack([-d[:, 1], d[:, 0]], 1)            # left of (dx, dy) in UTM is (-dy, dx)
    vn = np.zeros_like(p)
    vn[:-1] += seg_n
    vn[1:] += seg_n
    vn /= np.linalg.norm(vn, axis=1, keepdims=True).clip(1e-9)
    cos = np.ones(len(p))
    cos[1:-1] = (vn[1:-1] * seg_n[:-1]).sum(1)
    vn /= np.clip(cos, 0.5, 1)[:, None]
    return p + vn * np.asarray(a)[:, None]


def twin_index(recs):
    """The one-way ways (each carriageway of a dual road is one), for twin_limits."""
    ids = [i for i, r in enumerate(recs) if r["oneway"]]
    geoms = [LineString(recs[i]["c"][:, :2]) for i in ids]
    return ids, geoms, shapely.STRtree(geoms)


def twin_limits(pc, ph, pe, members, recs, twins):
    """Per vertex of a one-way piece (UTM, in its direction): how far its carriageway reaches to the left and
    to the right of its centre line. Its own half-width, except where a one-way way running the other way
    (the other carriageway of a dual road) lies alongside closer than their two half-widths: OSM draws the
    two centre lines a few metres apart with each way's full width, so lanes spread over the way's own width
    crossed into the other carriageway (cars in the oncoming half: the Strand, Regent Street, Euston Road).
    There the gap between the centre lines is shared in proportion to the two widths."""
    ids, geoms, tree = twins
    left, right = ph.astype(float).copy(), ph.astype(float).copy()
    d = np.diff(pc[:, :2], axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True).clip(1e-9)
    tan = np.zeros((len(pc), 2))
    tan[:-1] += d
    tan[1:] += d
    tan /= np.linalg.norm(tan, axis=1, keepdims=True).clip(1e-9)
    for i, (p, t) in enumerate(zip(pc[:, :2], tan)):
        pt = shapely.Point(p)
        for q in tree.query(pt.buffer(ph[i] + TWIN_REACH)):
            j = ids[q]
            if j in members or recs[j]["elev"] != bool(pe[i]):
                continue
            g = geoms[q]
            s = g.project(pt)
            a = np.asarray(g.interpolate(s).coords[0])
            b0 = np.asarray(g.interpolate(max(0.0, s - 1.0)).coords[0])
            b1 = np.asarray(g.interpolate(min(g.length, s + 1.0)).coords[0])
            wd = b1 - b0
            wd /= max(np.linalg.norm(wd), 1e-9)
            if t @ wd > -TWIN_COS:                  # not running the other way alongside
                continue
            v = a - p
            if abs(t @ v) > 2.0:                    # past the other way's end: no foot across from this vertex
                continue
            off = t[0] * v[1] - t[1] * v[0]         # > 0: the other way lies to the left
            gap, w2 = abs(off), recs[j]["w"] / 2
            if gap < TWIN_MIN_GAP or gap >= ph[i] + w2:
                continue
            lim = max(TWIN_MIN_HALF, gap * ph[i] / (ph[i] + w2))
            if off > 0:
                left[i] = min(left[i], lim)
            else:
                right[i] = min(right[i], lim)
    return left, right


def lane_points(cp, terrain: Terrain):
    """A lane's points (UTM x, y, height, ground flag) -> (x, y, height): on the ground it follows the
    terrain, with points every LANE_STEP m along stretches where it isn't level; on decks their height."""
    out = [cp[:1, :3]]
    for a, b in zip(cp[:-1], cp[1:]):
        n = int(np.ceil(np.hypot(*(b[:2] - a[:2])) / LANE_STEP)) if a[3] > 0.5 and b[3] > 0.5 else 1
        f = (np.arange(1, n + 1) / n)[:, None]
        q = a[:3] + (b[:3] - a[:3]) * f
        if n > 1:
            g = terrain.height_utm(q[:, 0], q[:, 1])
            lin = a[2] + (b[2] - a[2]) * f[:, 0]
            # the inserted points only where the ground bends between the two
            if np.abs(g[:-1] - lin[:-1]).max() > 0.06:
                q[:-1, 2] = g[:-1]
            else:
                q = q[-1:]
        out.append(q)
    return np.vstack(out)


def cum(c):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(c[:, :2], axis=0), axis=1))]


def warp_length(L, stop, D, k):
    """Length of a lane's free coordinate p (see the module docstring; web/cars.js inverts it)."""
    if k >= 0.99:
        return L
    lam = math.log(1 / k) / (1 - k)
    D = min(D, stop)
    return (stop - D) + (D + (L - stop)) * lam


# ---------------------------------------------------------------- main

def main():
    rng = np.random.default_rng(SEED)
    bnd = boundary()
    x0, y0, x1, y1 = bnd.total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)
    area = box(x0, y0, x1, y1).buffer(PARKING_MARGIN, join_style="mitre")
    s_, w_, n_, e_ = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    lots, ports = areas(fetch_parking(f"{s_:.5f},{w_:.5f},{n_:.5f},{e_:.5f}"))
    print(f"{len(lots)} car parks and bus stations, ports: {0 if ports is None else ports.area / 1e6:.1f} km²")
    activity, village = activity_fields(area.bounds)
    wet = mk.wet_area()
    bld = gpd.read_file(DATA / "buildings.gpkg", columns=["h"]).to_crs(UTM).geometry.values
    btree = shapely.STRtree(bld)
    roads = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    roads = roads[~roads.elevated & (roads.kind != "rail")]
    road_tree = shapely.STRtree(roads.geometry.buffer(roads.width / 2, resolution=2).values)
    if ports is not None:
        shapely.prepare(ports)

    def port_near(x, y):
        if ports is None:
            return np.zeros(len(x))
        d = shapely.distance(ports, shapely.points(np.column_stack([x, y])))
        return np.clip(1 - (d - 1500) / 2500, 0, 1)

    terrain = Terrain()
    recs = load_network(terrain, fetch_bus_routes(f"{s_:.5f},{w_:.5f},{n_:.5f},{e_:.5f}") if BUS_ROUTES else None)
    key, degree, touching, ends = junctions(recs)
    chs = chains(recs, key, degree, ends)
    twins = twin_index(recs) if TWINS else None
    print(f"{len(recs):,} ways joined into {len(chs):,} chains")

    palettes = {name: [(a, b or a, w) for a, b, w in PALETTES[name]] for name, *_ in TYPES}
    pal_p = {name: np.array([w for *_, w in p]) / sum(w for *_, w in p) for name, p in palettes.items()}

    area_polys, area_p = [], []
    if AREAS:
        from ..common import districts as all_districts
        dall = all_districts()
        for a in AREAS:
            if "ring" in a:
                g = gpd.GeoSeries([Polygon(a["ring"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
            else:
                g = dall[dall.name.isin(a["districts"])].geometry.union_all()
            shapely.prepare(g)
            area_polys.append(g)
            ap = {}
            for name, w in a.get("weights", {}).items():
                if name not in pal_p:
                    continue
                w = np.asarray(w, float)
                if len(w) != len(pal_p[name]):
                    raise ValueError(f"[[cars.areas]] weights for {name}: {len(w)} for a palette of {len(pal_p[name])}")
                ap[name] = w / w.sum()
            area_p.append(ap)

    def pick_colours(types, e=None, n=None):
        out = np.zeros(len(types), np.uint8)
        area = np.full(len(types), -1)
        if area_polys and e is not None and len(types):
            for ai in range(len(area_polys) - 1, -1, -1):      # (the first area holding a car wins)
                area[shapely.contains_xy(area_polys[ai], e, n)] = ai
        for ti, (name, *_) in enumerate(TYPES):
            for ai in np.unique(area):
                m = (types == ti) & (area == ai)
                if m.any():
                    p = area_p[ai].get(name, pal_p[name]) if ai >= 0 else pal_p[name]
                    out[m] = rng.choice(len(p), m.sum(), p=p)
        return out

    def tile_of(x, y):
        return int(np.floor((x - origin[0]) / TILE)), int(np.floor((y - origin[1]) / TILE))

    lanes_by_tile = defaultdict(list)       # (tx, ty) -> [(pts scene xyz, speed, k, D, stop, cars p, types)]
    parked = []                             # (x utm, y utm, heading scene rad, type)
    stats = defaultdict(float)

    # ---- per chain: vertex arrays, then pieces between junctions
    for chain in chs:
        cs, half, hws, elev, idx = [], [], [], [], []
        for i, rev in chain:
            rec = recs[i]
            c = rec["c"][::-1] if rev else rec["c"]
            if cs:
                if DECK_ENDS and cs[-1][-1, 3] > 0.5 and c[0, 3] < 0.5:
                    cs[-1] = cs[-1].copy()
                    cs[-1][-1, 2:] = c[0, 2:]           # a ground road meeting a deck: the deck's height there
                c = c[1:]
            cs.append(c)
            half += [rec["w"] / 2] * len(c)
            hws += [rec["hw"]] * len(c)
            elev += [rec["elev"]] * len(c)
            idx += [i] * len(c)
        c = np.vstack(cs)
        half, elev, idx = np.array(half), np.array(elev), np.array(idx)
        if len(c) < 2:
            continue
        members = {i for i, _ in chain}
        main_i, main_rev = max(chain, key=lambda e: len(recs[e[0]]["c"]))
        main_rec = recs[main_i]
        hw = main_rec["hw"]
        base = hw.removesuffix("_link")
        oneway = main_rec["oneway"]
        kind = main_rec["kind"]
        psv_only = bool(PSV_DENS) and main_rec["no_cars"] and main_rec["psv"]
        if base not in CLASS or hw == "pedestrian" or (main_rec["no_cars"] and not psv_only):
            continue
        lcode = main_rec["lcode"]
        n_dir = lcode & 15

        cut_at = [0]
        for j in range(1, len(c) - 1):
            k = key(c[j])
            if degree[k] >= 3 and any(recs[o]["kind"] in ("major", "minor") for o in touching[k] if o not in members):
                cut_at.append(j)
        cut_at.append(len(c) - 1)

        def clearance(p):
            k = key(p)
            if degree[k] < 3:
                return 0.0, False, False
            others = [recs[o] for o in touching[k] if o not in members and recs[o]["kind"] in ("major", "minor", "service")]
            if not others:
                return 0.0, False, False
            big = [o for o in others if o["kind"] in ("major", "minor")]
            if not big:                           # only driveways: no cut back, no signal
                return 0.0, False, False
            zebra = any(not o["hw"].endswith("_link") and o["hw"] != "motorway" and not o["elev"] for o in big)
            return max(o["reach"] for o in big) + 0.5, zebra, True

        for a, b in zip(cut_at[:-1], cut_at[1:]):
            pc, ph, pe = c[a:b + 1], half[a:b + 1], elev[a:b + 1]
            if not pe.any() and len(pc) > 2:        # ground pieces: drop surplus nodes, keep per-vertex widths
                ls = LineString(pc[:, :2]).simplify(mk.SIMPLIFY)
                keep = np.array([np.argmin(np.linalg.norm(pc[:, :2] - q, axis=1)) for q in np.asarray(ls.coords)])
                keep = np.unique(keep)
                pc, ph, pe = pc[keep], ph[keep], pe[keep]
            if len(pc) < 2:
                continue
            s = cum(pc)
            L = s[-1]
            ts, zs, js = clearance(pc[0])
            te, ze, je = clearance(pc[-1])
            usable = L - ts - te
            if usable < 3 or (ts > 0 and te > 0 and usable < mk.MIN_PIECE):
                continue
            any_elev = bool(pe.any())
            # (06b_markings' rule: crossings on short pieces too, so queues stop behind them)
            can_zebra = base in mk.ZEBRA and not hw.endswith("_link") and not any_elev and ph.mean() >= 2.5
            zs, ze = zs and can_zebra, ze and can_zebra
            if zs and ze and usable < mk.CROSS_L * 2 + 1:
                ze = False
            if (zs or ze) and usable < mk.CROSS_L + 2:
                zs = ze = False
            mid = pc[np.searchsorted(s, L / 2) - 1 if np.searchsorted(s, L / 2) > 0 else 0, :2]
            act = float(activity(mid[0], mid[1]))
            vil = float(village(mid[0], mid[1]))
            port = float(port_near([mid[0]], [mid[1]])[0])
            hmed = float(np.median(ph))

            # ---- kerbside parking: which sides (left/right of the piece's direction)
            park_l = park_r = False
            ground_minor = not any_elev and not hw.endswith("_link") and (
                kind == "minor" or kind == "service" or (KERB_MAJOR and kind == "major" and base in KERBSIDE))
            if (ground_minor and not main_rec["access_no"] and not main_rec["no_cars"] and usable > 20
                    and not main_rec["no_kerbside"]):
                p_side = KERBSIDE[base]
                p_side = min(0.95, p_side + 0.45 * vil + 0.15 * min(act, 1))
                if hw == "service" and hmed * 2 < 4.4:
                    p_side *= 0.5
                park_r = rng.random() < p_side
                park_l = (not oneway or ONEWAY_BOTH) and rng.random() < p_side * (1.0 if ONEWAY_BOTH else 0.8)
                if hw == "tertiary" and hmed * 2 < 11:
                    park_l = park_r = False
                if OSM_PARKING:                     # where OSM says, it decides (sides in the piece's direction)
                    tl, tr = main_rec["park_lr"][::-1] if main_rev else main_rec["park_lr"]
                    if SIDE < 0:                    # driving on the left, park_r is the kerb on the left (mirrored)
                        tl, tr = tr, tl
                    park_l = park_l if tl is None else tl
                    park_r = park_r if tr is None else tr

            # ---- moving lanes: offsets a = alpha * half + beta + centre (metres left of the piece's direction,
            # mirrored driving on the left); half and centre: the carriageway's, about the way's own centre line
            # (a one-way carriageway of a dual road stops short of the other one: twin_limits)
            pr, pl = PARK_W * park_r, PARK_W * park_l
            lanes = []                                  # (alpha, beta, forward, index from kerb, n)
            lim_l, lim_r = twin_limits(pc, ph, pe, members, recs, twins) if oneway and TWINS else (ph, ph)
            # (u: the mirrored frame the lanes are laid out in, kerb lane on the right; u = SIDE * offset)
            u_hi, u_lo = (lim_l, lim_r) if SIDE > 0 else (lim_r, lim_l)
            ph_c, c_c = (u_hi + u_lo) / 2, (u_hi - u_lo) / 2
            if oneway:
                hmed = float(np.median(ph_c))
                n = max(1, n_dir)
                if pr and 2 * hmed - pr < n * LANE_MIN:
                    n = max(1, n - 1)
                    if 2 * hmed - pr < n * LANE_MIN:
                        park_r, pr = False, 0.0
                # region [-half + pr, half - pl]; lane k from the kerb (right)
                for k in range(n):
                    f = (k + 0.5) / n
                    lanes.append((-1 + 2 * f, pr - f * (pr + pl), True, k, n))
            else:
                n = max(1, n_dir)
                # both directions need n lanes in what parking leaves; on small streets a single file
                # between the parked rows will do (narrow village lanes work like that), otherwise
                # parking goes first
                small = n == 1 and (base in ("residential", "living_street", "unclassified", "road", "service")
                                    or vil > 0.2)
                need = LANE_SMALL if small else 2 * n * LANE_MIN
                while (pr or pl) and 2 * hmed - pr - pl < need:
                    if pl:
                        park_l, pl = False, 0.0
                    else:
                        park_r, pr = False, 0.0
                if 2 * hmed - pr - pl < 2 * min(LANE_MIN, 2.4) * n:
                    n_single = 1 if 2 * hmed - pr - pl >= LANE_SMALL else 0
                    # a single file in the middle, one direction (narrow village lanes run one way)
                    if n_single:
                        lanes.append((0.0, (pr - pl) / 2, bool(rng.random() < 0.5), 0, 1))
                else:
                    # split point: the centre line, or the middle of what's left beside a parked row
                    m_a, m_b = 0.0, (pr - pl) / 2 if (pr > 0) != (pl > 0) else 0.0
                    for k in range(n):
                        f = (k + 0.5) / n
                        # forward: from the right kerb (-half + pr) to the split
                        lanes.append((-1 + f * (1 + m_a), pr * (1 - f) + f * m_b, True, k, n))
                        # backward: from the left kerb (half - pl) to the split
                        lanes.append((1 - f * (1 - m_a), -pl * (1 - f) + f * m_b, False, k, n))

            spd0, gap0, kq0, mix = CLASS[base]
            if hw.endswith("_link"):
                spd0 = LINK_SPEED.get(base, spd0)
            if MAXSPEED_K and main_rec["maxspeed"]:
                spd0 = main_rec["maxspeed"] / 3.6 * MAXSPEED_K
            restricted = bool(RESTRICTED_MIX) and main_rec["restricted"]
            if restricted:
                mix = RESTRICTED_MIX
            dens = (0.35 + 0.65 * min(act, 1.2)) * (1.25 if base in ("motorway", "trunk") else 1)
            if any_elev and base not in ("motorway", "trunk"):
                dens *= 1.1
            if kind == "service":
                dens *= 0.5 + 0.5 * min(act, 1)
            if restricted:
                dens *= RESTRICTED_DENS
            if psv_only:
                mix = tuple(1.0 if j in BUSES[:1] or TYPES[j][0] == "taxi" else 0.0 for j in range(len(TYPES)))
                dens *= PSV_DENS
            for alpha, beta, fwd, k_lane, n_lanes in lanes:
                off = SIDE * (alpha * ph_c + beta + c_c)
                xy = offset_line(pc[:, :2], off)
                xyz = np.column_stack([xy, pc[:, 2:]])
                t0, t1, z0, z1, j0, j1 = ts, te, zs, ze, js, je
                if not fwd:
                    xyz = xyz[::-1]
                    t0, t1, z0, z1, j0, j1 = te, ts, ze, zs, je, js
                sl = cum(xyz)
                Ls = sl[-1]
                # the lane: from INTO_JUNCTION inside the junction behind to INTO_JUNCTION inside the one ahead
                lo = max(0.0, t0 - (INTO_JUNCTION if j0 else 0))
                hi = min(Ls, Ls - t1 + (INTO_JUNCTION if j1 else 0))
                stop_at = Ls - t1 - (mk.CROSS_L if z1 or STOP_CLEAR else 0) - 0.8 - STOP_CLEAR
                if hi - lo < MIN_LANE:
                    continue
                pts, ss = mk.cut(xyz, sl, lo, hi)
                # speed: faster lanes away from the kerb, slower in busy areas
                v = spd0 * (1 + 0.1 * k_lane) * (1 - (0.25 if not any_elev else 0.12) * min(act, 1.2))
                v *= rng.uniform(0.92, 1.08)
                signal = j1 and base not in ("motorway",) and not any_elev and not hw.endswith("_link")
                kq = kq0 if signal else (0.6 if j1 and hw.endswith("_link") else 1.0)
                # chunk long lanes (each chunk its own loop)
                total = ss[-1] - ss[0]
                nch = max(1, int(np.ceil(total / CHUNK)))
                for q in range(nch):
                    ca, cb = ss[0] + total * q / nch, ss[0] + total * (q + 1) / nch
                    cp, cs2 = mk.cut(pts, ss, ca, cb)
                    Lc = cs2[-1] - cs2[0]
                    last = q == nch - 1
                    k_this = kq if last else 1.0
                    stop = (stop_at - ca) if last and k_this < 1 else Lc
                    # rounded as stored, so the viewer's free coordinate matches this one
                    stop = round(float(np.clip(stop, 1.0, Lc)), 1)
                    D = float(max(1, round(min(45.0, 0.5 * stop))))
                    k_this = round(k_this, 2)
                    P = warp_length(Lc, stop, D, k_this)
                    # cars in the free coordinate: gaps of at least a car plus 2 m at the slowest
                    mix_l = np.array(mix, float)
                    if BUS_ROUTES:                  # buses only on the ways their routes take
                        bus_route_mix(mix_l, main_rec)
                    if kind == "major" or base == "tertiary":
                        heavy_ok = k_lane == 0 or (base in ("motorway", "trunk") and k_lane == 1 and n_lanes >= 3)
                    else:
                        heavy_ok = True
                    if not heavy_ok:
                        mix_l[HEAVY] = 0
                    if heavy_ok and k_lane != 0:
                        mix_l[BUSES] = 0
                    if main_rec["cars_only"]:
                        mix_l[COMMERCIAL] = 0
                    if port > 0 and heavy_ok and not main_rec["cars_only"] and "lorry" in T:
                        mix_l[T["lorry"]] += 30 * port * (base in BIG_ROADS or kind == "service" or base == "unclassified")
                        mix_l[T["truck"]] += 8 * port
                    if base in ("motorway",) or any_elev:
                        mix_l[BUSES] *= 0.4
                    mix_l[T["taxi"]] *= 0.6 + 0.8 * min(act, 1)
                    mix_l /= mix_l.sum()
                    mean = gap0 / dens
                    ps, ty = [], []
                    p = rng.uniform(0, mean)
                    prev_len = None
                    first = None
                    while p < P:
                        t = rng.choice(len(TYPES), p=mix_l)
                        if prev_len is not None:
                            min_gap = ((prev_len + LEN[t]) / 2 + 2.0) / k_this
                            if p - ps[-1] < min_gap:
                                p = ps[-1] + min_gap
                                if p >= P:
                                    break
                        if first is not None and P - p + first < ((LEN[t] + LEN[ty[0]]) / 2 + 2.0) / min(k_this, 1):
                            break
                        ps.append(p)
                        ty.append(t)
                        first = ps[0]
                        prev_len = LEN[t]
                        gmin = ((LEN[t] + 4.75) / 2 + 2.0) / k_this
                        p += gmin + rng.exponential(max(mean - gmin, 1.0))
                    if not ps:
                        continue
                    mid_pt = cp[len(cp) // 2]
                    cp = lane_points(cp, terrain)
                    scene = to_scene(cp[:, :2], origin)
                    y = cp[:, 2] + CAR_Y
                    lanes_by_tile[tile_of(*mid_pt[:2])].append(
                        (np.column_stack([scene[:, 0], y, scene[:, 1]]), v, k_this, D, stop, np.array(ps), np.array(ty)))
                    stats["lane km"] += Lc / 1000
                    stats["moving"] += len(ps)

            # ---- kerbside rows (UTM, left/right of the piece's direction)
            for side, on in ((-1, park_r), (1, park_l)):
                if not on:
                    continue
                lo = ts + (mk.CROSS_L if zs else 0) + 3
                hi = L - te - (mk.CROSS_L if ze else 0) - 3
                if hi - lo < 8:
                    continue
                occ = min(KERB_OCC_MAX, KERB_OCC + 0.35 * vil + 0.1 * min(act, 1))
                at = lo + rng.uniform(0, 3)
                pos, turn, moto = [], [], []
                while at < hi - 2.5:
                    # a bay of two-wheelers parked side by side across the row, 4.5 m long (Paris)
                    if MOTO_BAYS and rng.random() < MOTO_BAYS and at + 4.5 < hi:
                        nose = rng.random() < 0.5
                        for q in np.arange(0.5, 4.5, 0.9):
                            if rng.random() < 0.85:
                                pos.append(at + q - 1.4)
                                turn.append(np.pi / 2 * (1 if nose else -1) + rng.normal(0, 0.12))
                                moto.append(True)
                        at += 4.5 + rng.uniform(0.3, 1.0)
                        continue
                    # driveways and gaps: runs of cars broken now and then
                    if rng.random() < occ:
                        pos.append(at)
                        turn.append(0.0)
                        moto.append(False)
                    elif rng.random() < 0.25:
                        at += rng.uniform(4, 10)
                    at += rng.uniform(*PARK_PITCH)
                if not pos:
                    continue
                pos, turn, moto = np.array(pos), np.array(turn), np.array(moto)
                kerb = (lim_l if SIDE * side > 0 else lim_r)           # the row's kerb (its own carriageway's)
                off = SIDE * side * (kerb - PARK_W / 2 - 0.05)
                line = offset_line(pc[:, :2], off)
                sx, sy = np.interp(pos, s, line[:, 0]), np.interp(pos, s, line[:, 1])
                seg = np.clip(np.searchsorted(s, pos, "right") - 1, 0, len(s) - 2)
                d = pc[seg + 1, :2] - pc[seg, :2]
                ang = np.arctan2(-d[:, 1], d[:, 0])          # scene heading (z = -north)
                if side == 1:
                    ang = ang + np.pi                          # the left row faces the other way
                mixp = np.array(PARKED_MIX, float)
                if "truck" in T:
                    mixp[T["truck"]] += 6 * (port > 0.3)
                for x_, y_, a_, tn, mo in zip(sx, sy, ang, turn, moto):
                    h_ = a_ + tn + rng.normal(0, 0.02)           # (drawn in the order they always were)
                    parked.append((x_, y_, h_, MOTO if mo else rng.choice(len(TYPES), p=mixp / mixp.sum()), 1))
                stats["kerbside"] += len(pos)

    if TRAMS:
        for tk, lane in tram_lanes(terrain, origin, tile_of, np.random.default_rng(SEED + 7)):
            lanes_by_tile[tk].append(lane)
            stats["tram lane km"] += (lane[4]) / 1000
            stats["tram modules"] += len(lane[5])

    # ---- car parks and bus stations
    for kind, poly, cap in lots:
        if poly.is_empty or poly.area < 120 or poly.area > 300000:
            continue
        inner = poly.buffer(0.4 if kind == "row" else -0.6)    # (a strip is about a car wide: no margin)
        if inner.is_empty:
            continue
        # skip lots mostly covered by buildings (multi-storey ones mapped without their tag)
        hits = btree.query(poly, predicate="intersects")
        if len(hits) and shapely.area(shapely.intersection(bld[hits], poly)).sum() > 0.3 * poly.area:
            continue
        rect = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)[:4]
        e0, e1 = rect[1] - rect[0], rect[2] - rect[1]
        if np.linalg.norm(e0) < np.linalg.norm(e1):
            e0, e1 = e1, e0
        u = e0 / np.linalg.norm(e0)
        vv = np.array([-u[1], u[0]])
        cx, cy = poly.centroid.x, poly.centroid.y
        corners = np.asarray(poly.exterior.coords if poly.geom_type == "Polygon" else
                             np.vstack([g.exterior.coords for g in poly.geoms]))
        us, vs = (corners - [cx, cy]) @ u, (corners - [cx, cy]) @ vv
        sw, sl, aisle = (BUS_STALL_W, BUS_STALL_L, BUS_AISLE) if kind == "bus" else (STALL_W, STALL_L, AISLE)
        period = 2 * sl + aisle
        v_start = vs.min() + rng.uniform(0, 1.5)
        u0 = us.min() + rng.uniform(0, sw)
        cand = []
        if kind == "row":
            # one file along the strip's middle, nose to tail (face 0: heading along u), bays of the kerbside
            # pitch; a strip under 1.6 m or over 8 m across is not a kerbside row (skip / leave to the lot rule)
            if vs.max() - vs.min() < 1.6:
                continue
            for cu in np.arange(us.min() + rng.uniform(0.3, 1.5) + 2.3, us.max() - 2.3, float(np.mean(PARK_PITCH))):
                cand.append((cu, (vs.min() + vs.max()) / 2, 0))
            sw, sl = float(np.mean(PARK_PITCH)) * 0.85, 1.8
        else:
          for rv in np.arange(v_start, vs.max(), period):
            for row, face in ((rv + sl / 2, 1), (rv + sl * 1.5, -1)):
                for cu in np.arange(u0 + sw / 2, us.max(), sw):
                    cand.append((cu, row, face))
        if not cand:
            continue
        cand = np.array(cand)
        px = cx + cand[:, 0] * u[0] + cand[:, 1] * vv[0]
        py = cy + cand[:, 0] * u[1] + cand[:, 1] * vv[1]
        hu, hv = sw / 2 * 0.85, sl / 2 * 0.9
        quads = np.stack([np.column_stack([px + su * hu * u[0] + sv * hv * vv[0], py + su * hu * u[1] + sv * hv * vv[1]])
                          for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))], 1)
        polys = shapely.polygons(quads)
        ok = shapely.contains(inner, polys)
        if not ok.any():
            continue
        pi, _ = btree.query(polys[ok], predicate="intersects")
        okk = np.flatnonzero(ok)
        ok[okk[np.unique(pi)]] = False
        ok &= ~shapely.contains_xy(wet, px, py)
        occ = rng.uniform(0.55, 0.9) if kind == "car" else KERB_OCC + 0.1 if kind == "row" else rng.uniform(0.6, 0.85)
        # cars cluster near the entrance side: fill a stall with a chance falling along the lot
        ramp = 1 - 0.35 * (cand[:, 0] - us.min()) / max(us.max() - us.min(), 1)
        ok &= rng.random(len(cand)) < occ * ramp * (1.1 if kind == "car" else 1)
        if cap and kind == "car" and ok.sum() > cap * occ:
            # ([cars] lot_capacity) the lot's tagged bays at its occupancy, a random share of the stalls drawn
            keep = rng.choice(np.flatnonzero(ok), int(round(cap * occ)), replace=False)
            ok[:] = False
            ok[keep] = True
        # stalls face the aisle (along v); the heading is the car's nose
        ang = np.arctan2(-(vv[1] * cand[:, 2]), vv[0] * cand[:, 2])
        if kind == "row":                              # along the strip, either way
            ang = np.arctan2(-u[1], u[0]) + np.pi * (rng.random(len(cand)) < 0.5)
        nose_out = rng.random(len(cand)) < 0.25
        ang = np.where(nose_out, ang + np.pi, ang)
        for j in np.flatnonzero(ok):
            if kind == "bus":
                t = T["bus"]
            else:
                mixp = np.array(PARKED_MIX, float)
                t = rng.choice(len(TYPES), p=mixp / mixp.sum())
            parked.append((px[j], py[j], ang[j] + rng.normal(0, 0.015), t, 2 if kind == "row" else 0))
            stats["kerbside strips" if kind == "row" else "car parks"] += 1

    # kerbside cars on buildings or water, or on another street's carriageway, are dropped
    parked = np.array(parked, dtype=float).reshape(-1, 5)
    if len(parked):
        c_, s_ = np.cos(parked[:, 2]), -np.sin(parked[:, 2])            # scene heading back to UTM direction
        Lh = LEN[parked[:, 3].astype(int)] / 2 * 0.9
        Wh = np.array([t[2] for t in TYPES])[parked[:, 3].astype(int)] / 2 * 0.9
        quads = np.stack([np.column_stack([parked[:, 0] + a * Lh * c_ - b * Wh * s_, parked[:, 1] + a * Lh * s_ + b * Wh * c_])
                          for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], 1)
        polys = shapely.polygons(quads)
        pi, _ = btree.query(polys, predicate="intersects")
        bad = np.zeros(len(parked), bool)
        bad[np.unique(pi)] = True
        bad |= shapely.contains_xy(wet, parked[:, 0], parked[:, 1])
        # car park stalls under a street (a service road through the lot) would be hidden by its surface
        lot = parked[:, 4] == 0
        pi, _ = road_tree.query(polys[lot], predicate="intersects")
        bad[np.flatnonzero(lot)[np.unique(pi)]] = True
        # overlapping each other (a kerbside row and a car park, two rows at a corner): keep the first
        ptree = shapely.STRtree(polys)
        a_, b_ = ptree.query(polys, predicate="intersects")
        clash = a_ > b_
        drop = np.zeros(len(parked), bool)
        for i, j in zip(a_[clash], b_[clash]):
            if not drop[j]:
                drop[i] = True
        stats["parked dropped"] = int((bad | drop).sum())
        parked = parked[~(bad | drop)]
    # the ground under car park stalls: land (0), or a park or airport apron (lifted layers, 05_ground.py),
    # over the terrain
    ground_y = np.where(parked[:, 4] >= 1, CAR_Y, 0.02)   # (kerbside rows and strips stand on the street)
    for layer, y in (("green", 0.62), ("aeroway", 1.22)) + ((("asphalt", 0.27),) if LOTS_ASPHALT else ()):
        g = gpd.read_file(DATA / "ground.gpkg", layer=layer).geometry.values
        pi, _ = shapely.STRtree(g).query(shapely.points(parked[:, :2]), predicate="within")
        pi = pi[parked[pi, 4] == 0]
        ground_y[pi] = np.maximum(ground_y[pi], y)
    ground_y += terrain.height_utm(parked[:, 0], parked[:, 1])
    parked = np.column_stack([parked, ground_y])
    parked_by_tile = defaultdict(list)
    for row in parked:
        parked_by_tile[tile_of(row[0], row[1])].append(row)

    # ---- write
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("c_*.bin"):
        f.unlink()
    files, total_bytes = [], 0
    keys = sorted(set(lanes_by_tile) | set(parked_by_tile))
    for tk in keys:
        tx, ty = tk
        cx, cz = tx * TILE, -(ty + 1) * TILE                       # the tile's north-west corner, scene
        lanes = lanes_by_tile.get(tk, [])
        pk = np.array(parked_by_tile.get(tk, [])).reshape(-1, 6)
        head = np.zeros((len(lanes), 5), np.uint16)                 # points, cars, speed|k, D|spare, stop
        pts = np.vstack([ln[0] for ln in lanes]) if lanes else np.zeros((0, 3))
        cars_p, cars_t, cars_m = [], [], []
        for i, (xyz, v, kq, D, stop, ps, ty_) in enumerate(lanes):
            head[i] = (len(xyz), len(ps), min(255, round(v / 0.2)) | (min(100, round(kq * 100)) << 8),
                       min(255, round(D)), min(65535, round(stop * 10)))
            cars_p.append(np.minimum(np.round(ps * 10), 65535).astype(np.uint16))
            cars_t.append(ty_)
            if area_polys:                              # (the lane's middle, UTM: [[cars.areas]])
                mid = np.asarray(xyz)[len(xyz) // 2]
                cars_m.append(np.repeat([[origin[0] + mid[0], origin[1] - mid[2]]], len(ps), axis=0))
        cars_p = np.concatenate(cars_p) if cars_p else np.zeros(0, np.uint16)
        cars_t = np.concatenate(cars_t).astype(np.uint8) if cars_t else np.zeros(0, np.uint8)
        if area_polys and cars_m:
            cm = np.concatenate(cars_m)
            cars_c = pick_colours(cars_t, cm[:, 0], cm[:, 1])
        else:
            cars_c = pick_colours(cars_t)
        # points: dm relative to the corner, as int16 differences
        qx = np.round((pts[:, 0] - cx) * 10).astype(np.int64)
        qz = np.round((pts[:, 2] - cz) * 10).astype(np.int64)
        qy = np.clip(np.round(pts[:, 1] * 100), 0, 65535).astype(np.uint16)
        if len(pk):
            sc = to_scene(pk[:, :2], origin)
            order = np.lexsort((sc[:, 0], np.round(sc[:, 1] / 50)))       # rows of nearby cars: small differences
            pk, sc = pk[order], sc[order]
            px_ = np.round((sc[:, 0] - cx) * 10).astype(np.int64)
            pz_ = np.round((sc[:, 1] - cz) * 10).astype(np.int64)
            ph_ = (np.round(pk[:, 2] / (2 * np.pi) * 256) % 256).astype(np.uint8)
            pt_ = pk[:, 3].astype(np.uint8)
            pc_ = pick_colours(pt_, pk[:, 0], pk[:, 1]) if area_polys else pick_colours(pt_)
            py_ = np.clip(np.round(pk[:, 5] * 100), 0, 65535).astype(np.uint16)
        else:
            px_ = pz_ = np.zeros(0, np.int64)
            ph_ = pt_ = pc_ = np.zeros(0, np.uint8)
            py_ = np.zeros(0, np.uint16)

        def diff16(q):
            d = np.diff(np.r_[0, q])
            if len(d) and (d.min() < -32768 or d.max() > 32767):
                raise ValueError("coordinate step out of int16 range")
            return split(d.astype(np.int16).view(np.uint16))

        blob = b"".join([
            np.array([len(lanes), len(pts), len(cars_p), len(pk)], np.uint32).tobytes(),
            split(head[:, 0]), split(head[:, 1]), split(head[:, 2]), split(head[:, 3]), split(head[:, 4]),
            diff16(qx), diff16(qz), split(qy),
            split(cars_p), cars_t.tobytes(), cars_c.tobytes(),
            diff16(px_), diff16(pz_), split(py_), ph_.tobytes(), pt_.tobytes(), pc_.tobytes(),
        ])
        name = f"c_{tx}_{ty}.bin"
        data = gzip.compress(blob, 9, mtime=0)
        (OUT / name).write_bytes(data)
        total_bytes += len(data)
        files.append({"file": name, "x": cx, "z": cz, "lanes": len(lanes), "moving": int(len(cars_p)),
                      "parked": int(len(pk))})

    index = {
        "origin": {"utm_epsg": UTM_EPSG, "easting": origin[0], "northing": origin[1]},
        "tileSize": TILE, "carY": CAR_Y, "fade": FADE,
        "types": [{"name": n, "length": l, "width": w, "height": h, **({"model": m} if m else {})}
                  for (n, l, w, h), m in zip(TYPES, MODEL)],
        "palettes": {name: [[a, b] for a, b, _ in palettes[name]] for name, *_ in TYPES},
        "tiles": files,
    }
    (OUT / "cars.json").write_text(json.dumps(index, indent=1))
    link_web("cars")
    moving = sum(f["moving"] for f in files)
    print({k: round(v, 1) for k, v in stats.items()})
    print(f"{len(files)} tiles, {sum(f['lanes'] for f in files):,} lanes, {moving:,} moving and "
          f"{len(parked):,} parked cars, {total_bytes / 1e6:.1f} MB")


def split(a) -> bytes:
    """uint16 array -> its low bytes, then its high bytes (compresses better than interleaved)."""
    a = np.asarray(a, np.uint16)
    return (a & 255).astype(np.uint8).tobytes() + (a >> 8).astype(np.uint8).tobytes()

