"""08_trees: place trees: street trees along the roads, woods on the hills, trees in parks and estate courtyards.

The geography is real, the trees are imagined: nobody has mapped a city's millions of trees, so
they are placed where trees plausibly grow, following what the city looks like from the air. The species
odds, sizes and the OSM tag -> class mapping are the region preset's ([trees]); as built for Shenzhen:
Shenzhen
is very green: most roads are lined with trees on both sides (and in the median of dual carriageways),
the hills are covered in evergreen broadleaf forest, and residential estates plant their courtyards.

Two kinds of trees, stored differently:
  street trees   explicit points, both sides of every ground-level road (not motorways or ramps), at
                 STREET_STEP along lines ROW_OFFSET beyond the carriageway edge, dropped where they would
                 stand on a building, another road, water, a runway or under a bridge deck. One species,
                 size and colour per road, so a street reads as one planting.
  area trees     not stored as points but as a class raster (MASK_CELL metres) saying what grows where:
                 forest, park, orchard, mangrove, scrub, grass, estate courtyards, open land. The viewer
                 scatters trees over it on a jittered grid whose spacing and density depend on the class
                 (web/trees.js), so a hillside of a hundred thousand trees costs a few hundred bytes.
Buildings (buffered by BUILDING_GAP), roads, water, runways and bridge decks are cut out of the raster,
which is drawn at CELL and stored at MASK_CELL with a cell kept only where all its finer cells are free.

What grows where comes from OSM's green areas with their tags (natural=wood, leisure=park, ...), which
05_ground.py merged into one untagged layer, so they are fetched again here (cached in raw/osm_green.json),
and from OSM land use (05c_landuse.py). Smaller areas win over larger ones they sit in (a wood in a park).

Also writes a canopy "carpet": the wooded classes as polygons (polygonized from the stored raster) laid on
the ground of 05a_terrain.py (cut along its TIN where it is not level), which the viewer draws under the
trees as shaded forest floor and, beyond the distance it draws trees at, as the forest itself. The viewer
puts the trees themselves on the same ground (web/terrain.js).

`08_trees --green-only` only fetches and caches the green areas (raw/osm_green.json), which 05a_terrain
reads: on a fresh city it runs once before the terrain, the whole stage after it (city3d all does both).

Output, trees/ in the data folder (the viewer reads it through web/trees, a link this stage makes):
  trees.json        index: origin, tile size, cell, classes, tiles with their street tree counts
  t_<tx>_<ty>.bin   per 1 km tile (same grid as 06_tiles.py), gzip of:
                      u32 street tree count n, u32 1 if a class raster follows
                      u8[(TILE/MASK_CELL)^2] class raster, row 0 at the north edge, column 0 west
                      x, z within the tile in decimetres (z grows southwards), each as the difference
                        to the previous tree (trees follow each other along their rows, so these are
                        small), int16 split into u8[n] low bytes then u8[n] high bytes
                      u8[n] height in decimetres ([trees] height_q: in 1/height_q m, trees.json heightQ),
                      u8[n] kind (species in bits 0-1, colour seed in 2-7; census.species_bits
                        = 3: bits 0-2 and 3-7, trees.json speciesBits), with [trees] clip_walls
                      u8[n] crown radius cap in 0.2 m (trees.json caps)
  carpet.bin        gzip of: u32 vertex count, u32 index count, x and z / CARPET_Q as int16 differences
                    to the previous vertex (low bytes, then high bytes, x then z), the ground's height
                    / CARPET_YQ as uint16 (low bytes, then high bytes), u8[v] class, padding to 4 bytes,
                    u32[i] triangle indices
Splitting bytes and storing differences roughly halves the gzipped size.
"""
import gzip
import json
import struct

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
import shapely
from affine import Affine
from shapely.geometry import Polygon, shape

from ..common import CFG, DATA, RAW, UTM, UTM_EPSG, Terrain, boundary, element_geoms, link_web, overpass, weld

TR = CFG["trees"]
OUT = DATA / "trees"
TILE = CFG["tiles"]["size"]
CELL = 4.0                     # class raster resolution while drawing it, metres
MASK_CELL = 8.0                # ... and as stored (the viewer's tree spacing is 6-12 m anyway)
N = int(TILE / CELL)
URBAN_MARGIN = TR["urban_margin"]   # estates and open land get trees this far outside the districts

# class ids in the raster; the viewer (web/trees.js) holds how dense and tall each grows
CLASSES = ["none", "forest", "park", "orchard", "mangrove", "scrub", "grass", "residential",
           "campus", "industrial", "open"]
# (opt-in, Tokyo M6) [trees.zones.<name>] = {parks = [OSM names of green areas], ring = [[lon, lat], ...], from = [classes]}:
# the area-tree cells of the `from` classes (park and grass by default) inside the named green areas or the ring take
# the class <name>, appended to CLASSES, whose density and species mix the viewer's trees.classes.<name> gives (every
# key: step, p, h, wr, mix, clump, tone): Kokyo Gaien's black pines, the Sumida's and Chidorigafuchi's cherries. The
# far carpet keeps the zone's own class; {} (default): off, the class list unchanged
ZONES = TR.get("zones") or {}
CLASSES += [z for z in ZONES if z not in CLASSES]
C = {k: i for i, k in enumerate(CLASSES)}
ROAD, BUILDING = 255, 254      # temporary codes: street trees may not stand here, the rest of the class
                               # raster doesn't matter to them; both become "none" before writing
# OSM green tag ("key=value") -> class, the first that matches (the preset's: Shenzhen's cemeteries sit on
# wooded hillsides, lychee and longan orchards on Bao'an's hills)
GREEN = {tuple(k.split("=", 1)): v for k, v in TR["green"].items()}
LANDUSE = TR["landuse"]        # 05c_landuse's use -> class
BUILDING_GAP = TR["building_gap"]   # trees keep this far from walls (their crowns still overhang a little)
ROAD_GAP = TR["road_gap"]           # ... and from carriageway edges
NONE = TR.get("none", [])           # OSM "key=value" areas without trees (sports fields)
# no invented trees on 05_ground's paved and asphalt layers (squares and parvis: Paris M5 critic, the Concorde
# "sprinkled with trees", the Notre-Dame parvis); the census's street trees stay where they stand
NONE_PAVED = TR.get("none_on_paved", False)
# (opt-in, Tokyo tk2) [trees] none_on_layers = [05_ground layers]: no invented area trees on these layers either (nor the
# far carpet): Kokyo Gaien's raked gravel plaza and paths ([ground] gravel_parks) took the park's (and the pine zone's)
# trees, ~560 dark pines over the open gravel; [] (default): off
NONE_LAYERS = TR.get("none_on_layers") or []
# more OSM "key=value" areas without any tree, census or invented ([trees] none_extra: London's rail land, the
# slab between Victoria's sheds), fetched into the data folder (not raw/: osm_treeless.json is [trees] none's)
NONE_EXTRA = TR.get("none_extra", [])
# street-tree heights in u8 steps of 1 / HEIGHT_Q m: 10 (decimetres, up to 25.5 m) by default; London's planes
# reach 30-45 m in the inventory, so London stores half metres ([trees] height_q = 2, up to 127 m)
HEIGHT_Q = TR.get("height_q", 10)
# crowns kept off the walls ([trees] clip_walls {gap, min}): each street tree's crown radius is capped at its
# distance to the nearest footprint + gap (not under min), stored per tree (trees.json "caps"); off by default
CLIP = TR.get("clip_walls") or {}
# garden squares ([trees.squares]): named garden polygons (tags) of area [min, max] m² that the census leaves
# nearly bare (< per_ha trees a hectare) get a ring of tall trees inside their railings, every `step` m at
# `inset` m, heights [lo, hi], census group `group`; a few more inside (`inner` trees a hectare). Invented:
# private squares' trees are in no council inventory (Bedford Square, Belgravia's, Kensington's)
SQUARES = TR.get("squares") or {}
# [trees] lift_flag (off by default): street and census trees standing on the drawn street surface (inside a ground
# road's carriageway and sidewalks, 06b_markings' widths, and not on 05_ground's green layer) get bit 7 of their
# kind byte (trees.json liftBit), and only they take the viewer's trees.streetLift; park trees from a census stand
# on the ground like the area trees (Berlin M6: the Baumkataster's 125 k park trees floated 1.75 m over the lawns)
LIFT_FLAG = TR.get("lift_flag", False)
# [trees] census_off_decks (off by default): no census tree under an elevated way (bridge decks, viaducts): the
# inventories list trees beside the U-Bahn viaduct's piers that our widths put under its deck
OFF_DECKS = TR.get("census_off_decks", False)

# street trees
ST = TR["street"]
STREET_STEP = ST["step"]
ROW_OFFSET = ST["row_offset"]       # tree line beyond the carriageway edge (kerb + tree pit)
NO_STREET_TREES = set(ST["none_on"])
NAMED = ST.get("named") or {}         # (opt-in) plantings of named roads, see street_trees
CENSUS = ST.get("census") or {}
SPECIES = {"broadleaf": 0, "palm": 1, "flowering": 2}   # the viewer's street species (web/trees.js)
BITS = CENSUS.get("species_bits", 2)   # kind byte: species in the low BITS bits, a colour seed above

CARPET_CLASSES = ["forest", "park", "orchard", "mangrove", "scrub"]
# (opt-in, Hong Kong M7f) [trees] carpet = {extra = [classes], smooth = m}: the far carpet also over the `extra` classes
# (grass: the viewer colours it with trees.carpetBlend.colours), and its classes smoothed: each class's share blurred
# (a Gaussian of `smooth` m) and every cell given the class with the largest share, so the 24 m WorldCover cells' stair
# steps round off and patches and holes much under the blur's size close. From the harbour Lion Rock's and Sha Tin's
# hills showed pale square patches in the dark canopy (critic M7). {} (default): off, the carpet as before
CARPET_OPTS = TR.get("carpet") or {}
CARPET_CLASSES = CARPET_CLASSES + [c for c in CARPET_OPTS.get("extra", []) if c not in CARPET_CLASSES]
CARPET_Q = 2.0                 # carpet vertex quantization: int16 * 2 m covers ±65 km
CARPET_YQ = 0.02               # ... and heights: uint16 * 2 cm covers 1310 m
CACHE = RAW / "osm_green.json"
# (opt-in, Hong Kong M6) [trees] worldcover = {"10" = "forest", "20" = "scrub", ...}: land OSM leaves without a green
# area or land use (class none, or the urban margin's "open") takes the class of ESA WorldCover 2021's cover there
# (10 trees, 20 shrubs, 30 grass), read at worldcover_cell m (the class by majority) so its edges stay simple: the
# hillsides OSM's woods don't reach (critic M3b: a hard line where OSM's forest polygons stop, bare paint beyond)
WORLDCOVER = {int(k): v for k, v in (TR.get("worldcover") or {}).items()}
WORLDCOVER_CELL = float(TR.get("worldcover_cell", 24.0))
WC_URL = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
# (opt-in) [trees] feather = {edge = m, fringe = m, into = [classes], share}: area trees thin out over the last `edge` m
# inside the ground area's outline (to none at the outline, where the painted backdrop takes over), and the forest's
# edge frays: cells of the `into` classes within `fringe` m of the forest become forest, at most `share` of them right
# at the edge, fewer further out. The carpet keeps the unfeathered classes (simple polygons)
FEATHER = TR.get("feather") or {}


def fetch_green(area: Polygon) -> gpd.GeoDataFrame:
    """OSM green areas with a class from GREEN, cached."""
    if CACHE.exists():
        res = json.loads(CACHE.read_text())
    else:
        s, w, n, e = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
        sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in GREEN)
        res = overpass(f"[out:json][timeout:900][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];({sel});out geom;")
        wetland = overpass(f'[out:json][timeout:900][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];'
                           '(way["wetland"="mangrove"]; rel["wetland"="mangrove"];);out geom;')
        res["elements"] += wetland["elements"]
        CACHE.write_text(json.dumps(res))
    rows = []
    for t, g in element_geoms(res):
        cls = "mangrove" if t.get("wetland") == "mangrove" else \
            next((c for (k, v), c in GREEN.items() if t.get(k) == v), None)
        if cls and g.geom_type in ("Polygon", "MultiPolygon"):
            rows.append({"cls": cls, "geometry": g})
    g = gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(UTM)
    g["geometry"] = g.geometry.make_valid()
    return g[g.geom_type.isin(["Polygon", "MultiPolygon"])]


def burn(raster, transform, geoms, value):
    """Burn geometries into the raster in place (later burns overwrite earlier ones)."""
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return
    if np.isscalar(value):
        shapes = ((g, value) for g in geoms)
    else:
        shapes = zip(geoms, value)
    rasterio.features.rasterize(shapes, out=raster, transform=transform, merge_alg=rasterio.enums.MergeAlg.replace)


def class_raster(area, origin, tx0, tx1, ty0, ty1, ways, buildings):
    """The class raster over tiles tx0..tx1 × ty0..ty1, row 0 at the north edge."""
    w, h = (tx1 - tx0 + 1) * N, (ty1 - ty0 + 1) * N
    west, north = origin[0] + tx0 * TILE, origin[1] + (ty1 + 1) * TILE
    tr = Affine(CELL, 0, west, 0, -CELL, north)
    r = np.zeros((h, w), np.uint8)
    print(f"class raster {w} × {h}")

    land = gpd.read_file(DATA / "ground.gpkg", layer="land").union_all()
    urban = boundary().geometry.iloc[0].buffer(URBAN_MARGIN)
    burn(r, tr, [land.intersection(urban)], C["open"])
    lu = gpd.read_file(DATA / "landuse.gpkg", layer="landuse")
    lu = lu.assign(a=lu.area).sort_values("a", ascending=False)
    burn(r, tr, lu.geometry, [C[LANDUSE[u]] for u in lu.use])
    green = fetch_green(area)
    green = green.assign(a=green.area).sort_values("a", ascending=False)   # small areas burn last and win
    burn(r, tr, green.geometry, [C[c] for c in green.cls])
    print("green km² by class:", (green.groupby("cls").a.sum() / 1e6).round(1).to_dict())
    if WORLDCOVER:
        wc = worldcover_grid(tr, r.shape)
        bare = (r == 0) | (r == C["open"])
        # ([trees] worldcover_over = [classes], opt-in: OSM's grass or scrub where WorldCover sees trees becomes forest:
        # Hong Kong's hillsides mapped as grassland are mostly shrubland and woodland on their slopes)
        over = np.isin(r, [C[c] for c in TR.get("worldcover_over", [])])
        for code, cls in WORLDCOVER.items():
            sel = (bare | (over & (C[cls] == C["forest"]))) & (wc == code)
            r[sel] = C[cls]
            print(f"worldcover {code} -> {cls}: {sel.sum() * CELL ** 2 / 1e6:.1f} km² (before the land, water and roads cut)")
        del wc, bare
    # no trees on sports fields and the like ([trees] none: Pier 40's turf, the ballfields) nor on the
    # parks' paths (05_ground's cache of them)
    if NONE:
        s, w, n, e = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
        cache = RAW / "osm_treeless.json"
        if cache.exists():
            res = json.loads(cache.read_text())
        else:
            sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in (t.split("=", 1) for t in NONE))
            res = overpass(f"[out:json][timeout:600][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];({sel});out geom;")
            cache.write_text(json.dumps(res))
        bare = [g for t, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")]
        if bare:
            burn(r, tr, gpd.GeoSeries(bare, crs="EPSG:4326").to_crs(UTM).make_valid(), 0)
        print(f"treeless areas: {len(bare):,}")
    paths = CFG["ground"].get("paths", {})
    if paths and (RAW / "osm_paths.json").exists():
        res = json.loads((RAW / "osm_paths.json").read_text())
        lines = [(g, paths[t["highway"]]) for t, g in element_geoms(res)
                 if g.geom_type == "LineString" and t.get("highway") in paths
                 and t.get("footway") not in ("sidewalk", "crossing")]
        if lines:
            gs = gpd.GeoSeries([g for g, _ in lines], crs="EPSG:4326").to_crs(UTM)
            burn(r, tr, gs.buffer(np.array([w for _, w in lines]) / 2 + 0.5, cap_style="flat"), 0)
    if NONE_EXTRA:
        burn(r, tr, [none_extra_areas()], 0)
    if NONE_PAVED or NONE_LAYERS:
        import pyogrio
        have = {n for n, _ in pyogrio.list_layers(DATA / "ground.gpkg")}
        for name in (("paved", "asphalt") if NONE_PAVED else ()) + tuple(NONE_LAYERS):
            if name in have:
                burn(r, tr, gpd.read_file(DATA / "ground.gpkg", layer=name).geometry, 0)
    # nothing on the sea (green areas and land use can reach past the coastline), water or runways
    sea = np.zeros_like(r)
    burn(sea, tr, [land], 1)
    r[sea == 0] = 0
    # ...except mangroves, which grow in the tide beyond the coastline (Futian's reserve)
    mangrove = green[green.cls == "mangrove"].geometry
    burn(r, tr, mangrove, C["mangrove"])
    burn(r, tr, gpd.read_file(DATA / "ground.gpkg", layer="water").geometry, 0)
    burn(r, tr, gpd.read_file(DATA / "ground.gpkg", layer="aeroway").geometry, 0)
    ground, elevated = ways[~ways.elevated], ways[ways.elevated]
    burn(r, tr, ground.geometry.buffer(ground.width / 2 + ROAD_GAP, cap_style="flat"), ROAD)
    burn(r, tr, buildings.buffer(BUILDING_GAP), BUILDING)
    # under bridge decks: nothing, not even street trees (they would grow through the deck)
    burn(r, tr, elevated.geometry.buffer(elevated.width / 2 + 3, cap_style="flat"), 0)
    return r, tr


def offset_rows(line, dist, sides=(1, -1)):
    """Both parallel lines at dist from a way (or only those of `sides`: 1 its left, -1 its right), as coordinate
    arrays (possibly several pieces each)."""
    out = []
    for side in (dist * s for s in sides):
        o = line.offset_curve(side, join_style="mitre", mitre_limit=2.0)
        out += [np.asarray(p.coords) for p in getattr(o, "geoms", [o]) if not p.is_empty and p.length > STREET_STEP]
    return out


def named_colour(colour: int, nm: dict) -> int:
    """A named planting's colour seed (0-63): first = true keeps it in the viewer's first broadleaf slot (seed % 5 < 3:
    the rain trees), second = true (opt-in, Tokyo M6) in the second (seed % 5 of 3 or 4: Omotesando's zelkovas where
    the first slot is the ginkgo), kept under 64, the seed's range; neither: unchanged."""
    if nm.get("first"):
        return (colour // 5) * 5 + colour % 3
    if nm.get("second"):
        c = (colour // 5) * 5 + 3 + colour % 2
        return c - 5 if c >= 64 else c
    return colour


def street_trees(ways, raster, tr, buildings):
    """Points along both sides of the ground-level roads with a species, height and colour per road."""
    rng = np.random.default_rng(8)
    all_ways = ways
    ground = ways[~ways.elevated]
    ways = ways[~ways.elevated & ways.kind.isin(["major", "minor"]) & ~ways.highway.isin(NO_STREET_TREES)]
    xs, ys, hs, kinds = [], [], [], []
    # (named plantings with side = "kerb": one-way ways' tags, for their kerb side)
    tags = {}
    if any(nm.get("side") == "kerb" for nm in NAMED.values()):
        from .markings import osm_tags
        tags = osm_tags()
    for row in ways.itertuples():
        line = row.geometry
        if line.length < STREET_STEP * 1.5:
            continue
        seed = int(row.osm_id) * 2654435761 % 2**32
        wr = np.random.default_rng(seed)
        u = wr.random()
        # Shenzhen: boulevards are sometimes lined with royal palms, a few streets with flowering Bauhinia
        # or flame trees; most with banyans and other evergreen broadleaves. The odds are cumulative shares
        # per road kind, the last species takes the rest
        road = "major" if row.kind == "major" else "minor"
        # some roads have no trees at all (Midtown's avenues): [trees.street] planted, per road kind (a draw of
        # its own, so cities without it keep their trees)
        planted = ST.get("planted", {}).get(road, 1.0)
        # (a named planting is always planted)
        if planted < 1.0 and np.random.default_rng(seed + 1).random() >= planted and not NAMED.get(getattr(row, "name", None) or ""):
            continue
        species = next((sp for sp, upto in ST["odds"][road] if u < upto), ST["default"])
        # a height is drawn for every species in turn, whichever is picked, so the random sequence stays put
        drawn = {sp: wr.uniform(*(hr[road] if isinstance(hr, dict) else hr)) for sp, hr in ST["height"].items()}
        height = drawn[species]
        colour = int(wr.integers(0, 64))
        step = STREET_STEP * (1.25 if species == "palm" else 1.0) * wr.uniform(0.9, 1.1)
        rows = [(row.width / 2 + ROW_OFFSET + wr.uniform(-0.3, 0.6), 1.0)]
        # [trees.street.named] (opt-in, Singapore M6): named roads with a planting of their own: {species, height
        # [lo, hi], step (m), rows (m beyond the carriageway edge, one per row: a double canopy), first (true: the
        # viewer's first broadleaf slot, colour seed % 5 < 3: the rain trees)}
        nm = NAMED.get(getattr(row, "name", None) or "")
        if nm:
            species = nm.get("species", species)
            height = np.random.default_rng(seed + 2).uniform(*nm["height"]) if "height" in nm else height
            step = nm.get("step", step) * wr.uniform(0.95, 1.05)
            colour = named_colour(colour, nm)
            # (a row is an offset, or [offset, height factor]: a lower second row under the avenue's canopy)
            rows = [(row.width / 2 + (r[0] if isinstance(r, list) else r), r[1] if isinstance(r, list) else 1.0)
                    for r in nm.get("rows", [ROW_OFFSET])]
        # (named, side = "kerb", opt-in, Hong Kong M6: a one-way carriageway of a dual road is planted along its kerb
        # only, not along the median: Nathan Road's banyans by Kowloon Park, the railing median bare)
        sides = (1, -1)
        if nm and nm.get("side") == "kerb" and tags.get(int(row.osm_id), {}).get("oneway") in ("yes", "1", "-1"):
            ow = tags[int(row.osm_id)]["oneway"]
            sides = ((1 if CFG["drive"] == "left" else -1) * (-1 if ow == "-1" else 1),)
        for c, hk in ((c, hk) for r, hk in rows for c in offset_rows(line, r, sides)):
            seg = np.hypot(*np.diff(c, axis=0).T)
            s = np.concatenate([[0], np.cumsum(seg)])
            t = np.arange(step / 2, s[-1] - step / 3, step) + rng.uniform(-0.6, 0.6)
            t = t[(t > 0) & (t < s[-1])]
            if not len(t):
                continue
            px, py = np.interp(t, s, c[:, 0]), np.interp(t, s, c[:, 1])
            n = len(t)
            ph = height * rng.uniform(0.85, 1.12, n) * hk
            if nm and "within" in nm:
                # (named, within = [[lon, lat], ...], opt-in: the planting only along this stretch of the road, none
                # elsewhere on it: Nathan Road's banyans by Kowloon Park, Mong Kok's stretch bare)
                if nm["within"] is not None and not isinstance(nm["within"], Polygon):
                    nm["within"] = gpd.GeoSeries([Polygon(nm["within"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
                inn = shapely.contains_xy(nm["within"], px, py)
                px, py, ph = px[inn], py[inn], ph[inn]
                n = len(px)
            xs.append(px)
            ys.append(py)
            hs.append(ph)
            kinds.append(np.full(n, SPECIES[species] | (colour % (256 >> BITS)) << BITS, np.uint8))
    x, y, h, k = map(np.concatenate, (xs, ys, hs, kinds))
    print(f"street tree candidates {len(x):,}")
    if CENSUS:
        # the census stands for the districts: invented trees only outside them, the census's inside
        # (census.districts: the districts it covers, by name; all by default)
        from ..common import districts as all_districts
        d = all_districts()
        srcs = census_sources()
        within = None if any(not s.get("districts") for s in srcs) else {n for s in srcs for n in s["districts"]}
        districts = (d[d.name.isin(within)] if within else d).geometry.union_all()
        out = ~shapely.contains_xy(districts, x, y)
        cx, cy, ch, ck, ccr = census_trees(ground, buildings, districts, all_ways)
        x, y, h, k = (np.concatenate([a[out], b]) for a, b in ((x, cx), (y, cy), (h, ch), (k, ck)))
        cr = np.concatenate([np.full(int(out.sum()), 99.0), ccr])
        # the census's own trees are kept where they stand (the tests below would drop real trees on
        # the guessed road widths); only the invented ones are tested
        real = np.zeros(len(x), bool)
        real[int(out.sum()):] = True
    else:
        real = np.zeros(len(x), bool)
        cr = np.full(len(x), 99.0)
    # places without street trees ([trees.street] none_in: Times Square)
    for name, ring in ST.get("none_in", {}).items():
        poly = gpd.GeoSeries([Polygon(ring)], crs="EPSG:4326").to_crs(UTM).iloc[0]
        out = ~shapely.contains_xy(poly, x, y) | real
        print(f"no street trees in {name}: {int((~out).sum())} dropped")
        x, y, h, k, real, cr = x[out], y[out], h[out], k[out], real[out], cr[out]
    if CENSUS and SQUARES:
        qx, qy, qh, qk = square_trees(x[real], y[real], buildings, districts)
        x, y, h, k = (np.concatenate([a, b]) for a, b in ((x, qx), (y, qy), (h, qh), (k, qk)))
        real = np.concatenate([real, np.ones(len(qx), bool)])
        cr = np.concatenate([cr, np.full(len(qx), 99.0)])
    if NONE_EXTRA:
        bare = none_extra_areas()
        out = ~shapely.contains_xy(bare, x, y)
        print(f"no trees on {NONE_EXTRA}: {int((~out).sum())} street and census trees dropped")
        x, y, h, k, real, cr = x[out], y[out], h[out], k[out], real[out], cr[out]
    # the raster rules out water, the sea, runways and bridge decks; exact tests against buildings and
    # other roads follow (the raster's 4 m cells are too coarse right at a kerb)
    col = ((x - tr.c) / CELL).astype(int)
    rowi = ((tr.f - y) / CELL).astype(int)
    inside = (col >= 0) & (col < raster.shape[1]) & (rowi >= 0) & (rowi < raster.shape[0])
    ok = inside.copy()
    ok[inside] = raster[rowi[inside], col[inside]] != 0
    ok |= real & inside
    pts = gpd.GeoSeries(gpd.points_from_xy(x, y), crs=UTM)
    for obstacles in (buildings.buffer(1.5), ground.geometry.buffer(ground.width / 2 + 0.8, cap_style="flat")):
        test = ok & ~real
        hit = gpd.GeoSeries(obstacles.values, crs=UTM).sindex.query(pts[test].values, predicate="intersects")[0]
        idx = np.flatnonzero(test)
        ok[idx[np.unique(hit)]] = False
    # rows of two ways meeting (junctions, dual carriageways): drop trees closer than 4 m to a kept one
    keep = np.flatnonzero(ok & ~real)
    q = np.round(np.stack([x[keep], y[keep]], 1) / 4).astype(np.int64)
    _, first = np.unique(q[:, 0] * 100003 + q[:, 1], return_index=True)
    keep = np.concatenate([keep[np.sort(first)], np.flatnonzero(ok & real)])
    print(f"street trees {len(keep):,} ({int((ok & real).sum()):,} from the census)")
    x, y, h, k, real, cr = x[keep], y[keep], h[keep], k[keep], real[keep], cr[keep]
    if LIFT_FLAG:
        k = k & np.uint8(127) | (on_street(x, y, ground, (k & 128) > 0) << 7).astype(np.uint8)
    return x, y, h, k, real, cr


def on_street(x, y, ground, street):
    """[trees] lift_flag: 1 where a tree stands on the drawn street surface: inside a ground road's carriageway,
    sidewalks and median as 06b_markings draws them, or a street tree (a census source with street = true: bit 7
    of its kind byte, `street`) not on 05_ground's green layer; else 0."""
    from . import markings as mk
    tags = mk.osm_tags()
    g = ground[ground.kind.isin(["major", "minor", "service"])]
    reach = [w / 2 + max(mk.sidewalks(tags.get(o, {}), hw, tags.get(o, {}).get("oneway") in ("yes", "1", "-1"), False)) + 0.5
             for o, hw, w in zip(g.osm_id, g.highway, g.width)]
    cover = gpd.GeoSeries(g.geometry.values, crs=UTM).buffer(np.array(reach), cap_style="flat")
    pts = gpd.points_from_xy(x, y)
    pi, _ = gpd.GeoSeries(cover.values, crs=UTM).sindex.query(pts, predicate="within")
    near = np.zeros(len(x), bool)
    near[np.unique(pi)] = True
    green = gpd.read_file(DATA / "ground.gpkg", layer="green").geometry.values
    gi, _ = shapely.STRtree(green).query(shapely.points(x, y), predicate="within")
    on_green = np.zeros(len(x), bool)
    on_green[np.unique(gi)] = True
    on = (near | (street & ~on_green)).astype(np.uint8)
    print(f"lift_flag: {int(on.sum()):,} of {len(x):,} street and census trees on the street surface")
    return on


def census_sources():
    """The census's sources: [trees.street.census] itself (New York), or each of its `sources` over the
    census table's own keys (groups, species_bits, cover, ...), in order."""
    base = {k: v for k, v in CENSUS.items() if k != "sources"}
    return [{**base, **s} for s in CENSUS.get("sources", [base])]


def read_census(s):
    """One census source as (lon, lat, table): a CSV (columns lon / lat, or latlon = one "lat, lon" column,
    sep) or anything geopandas reads (GeoJSON points)."""
    f = DATA / s["file"]
    if f.suffix.lower() == ".csv":
        df = pd.read_csv(f, sep=s.get("sep", ","), encoding="utf-8-sig", low_memory=False)
        if "latlon" in s:
            ll = df[s["latlon"]].astype(str).str.split(",", expand=True)
            lat, lon = pd.to_numeric(ll[0], errors="coerce"), pd.to_numeric(ll[1], errors="coerce")
        else:
            lon, lat = df[s["lon"]], df[s["lat"]]
    else:
        g = gpd.read_file(f)
        g = g[g.geometry.notna() & ~g.geometry.is_empty].to_crs("EPSG:4326")
        lon, lat = g.geometry.x, g.geometry.y
        df = pd.DataFrame(g.drop(columns="geometry"))
    return lon.to_numpy(float), lat.to_numpy(float), df.reset_index(drop=True)


def none_extra_areas():
    """[trees] none_extra's OSM areas (UTM, one geometry), cached in the data folder."""
    cache = DATA / "osm_treeless_extra.json"
    if cache.exists():
        res = json.loads(cache.read_text())
    else:
        area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
        s, w, n, e = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
        sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in (t.split("=", 1) for t in NONE_EXTRA))
        res = overpass(f"[out:json][timeout:600][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];({sel});out geom;")
        cache.write_text(json.dumps(res))
    bare = [g for t, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")]
    print(f"none_extra areas: {len(bare):,}")
    return gpd.GeoSeries(bare, crs="EPSG:4326").to_crs(UTM).make_valid().union_all()


def square_trees(cx, cy, buildings, districts):
    """[trees.squares]: rings of tall trees in the garden squares the census leaves bare (see SQUARES)."""
    from scipy.spatial import cKDTree
    q = SQUARES
    tags = [tuple(t.split("=", 1)) for t in q.get("tags", ["leisure=garden"])]
    res = json.loads(CACHE.read_text())
    polys = [g for t, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")
             and any(t.get(k) == v for k, v in tags) and (t.get("name") or not q.get("named", True))]
    g = gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(UTM).make_valid()
    lo, hi = q.get("area", [1500, 40000])
    g = g[(g.area >= lo) & (g.area <= hi) & g.within(districts)]   # (outside, invented park trees fill them)
    kd = cKDTree(np.column_stack([cx, cy]))
    rng = np.random.default_rng(21)
    groups = [n for n, _ in CENSUS["groups"]]
    gi = groups.index(q.get("group", groups[0]))
    gi2 = groups.index(q.get("inner_group", q.get("group", groups[0])))
    walls = gpd.GeoSeries(buildings.values, crs=UTM).buffer(q.get("wall_gap", 3.0))
    wall_idx = walls.sindex
    xs, ys, hs, ks = [], [], [], []
    n_sq = 0
    for poly in g:
        c = poly.representative_point()
        near = kd.query_ball_point([c.x, c.y], np.sqrt(poly.area) * 0.8)
        inside = int(shapely.contains_xy(poly, cx[near], cy[near]).sum()) if near else 0
        if inside >= q.get("per_ha", 15) * poly.area / 1e4:
            continue
        n_sq += 1
        ring = poly.buffer(-q.get("inset", 4.0))
        pts = []
        for part in getattr(ring.boundary, "geoms", [ring.boundary]):
            L = part.length
            if L < q.get("step", 11.0) * 2:
                continue
            t = np.arange(rng.uniform(0, q.get("step", 11.0)), L, q.get("step", 11.0)) + rng.uniform(-1.2, 1.2)
            pts += [(part.interpolate(v).x, part.interpolate(v).y, gi) for v in np.clip(t, 0, L)]
        inner = poly.buffer(-q.get("inset", 4.0) - 9)
        if not inner.is_empty:
            ix0, iy0, ix1, iy1 = inner.bounds
            m = rng.poisson(q.get("inner", 8) * inner.area / 1e4)
            px, py = rng.uniform(ix0, ix1, m * 3), rng.uniform(iy0, iy1, m * 3)
            ok = shapely.contains_xy(inner, px, py)
            pts += [(a, b, gi2) for a, b in list(zip(px[ok], py[ok]))[:m]]
        for a, b, grp in pts:
            if len(wall_idx.query(shapely.Point(a, b), predicate="intersects")):
                continue
            xs.append(a); ys.append(b)
            hs.append(rng.uniform(*q.get("height", [18.0, 27.0])))
            ks.append(grp | int(rng.integers(0, 256 >> BITS)) << BITS)
    print(f"squares: {n_sq} bare garden squares of {len(g)}, {len(xs):,} trees invented")
    return np.array(xs), np.array(ys), np.array(hs), np.array(ks, np.uint8)


def crown_caps(x, y, buildings):
    """[trees] clip_walls: each tree's largest crown radius (m), its distance to the nearest footprint + gap."""
    tree = shapely.STRtree(buildings.values)
    pts = shapely.points(x, y)
    idx, d = tree.query_nearest(pts, max_distance=40, return_distance=True, all_matches=False)
    dist = np.full(len(x), 99.0)
    dist[idx[0]] = d
    return np.maximum(dist + CLIP.get("gap", 0.5), CLIP.get("min", 2.0))


def census_heights(s, df, g, rng):
    """Height per tree from height = [a, b, min, max]: a + b * the size field (dbh: trunk diameter or
    circumference, or a crown diameter), clamped. With a height_field (0 = unknown) the census's own height
    where it has one, else the formula where the size is known, else its group's median height."""
    a, b, lo, hi = s["height"]
    n = len(df)
    size = df[s["dbh"]].fillna(0).to_numpy(float) if s.get("dbh") else np.zeros(n)
    if not s.get("height_field"):
        return np.clip(a + b * size, lo, hi)
    h = np.where(size > 0, a + b * size, np.nan)
    own = pd.to_numeric(df[s["height_field"]], errors="coerce").fillna(0).to_numpy(float)
    known = (own > 0) & (own <= hi * 1.5)          # outliers (a 112 m plane) fall back on the trunk
    h = np.where(known, own, h)
    for gi in np.unique(g):
        miss = np.isnan(h) & (g == gi)
        if miss.any():
            ref = h[(g == gi) & ~np.isnan(h)]
            h[miss] = np.median(ref) if len(ref) else a + b * (np.median(size[size > 0]) if (size > 0).any() else 0)
    if s.get("jitter"):                                # class heights (5, 6, 8, 10 m): a little spread
        h = h * rng.uniform(1 - s["jitter"], 1 + s["jitter"], n)
    return np.clip(h, lo, hi)


def census_trees(ground, buildings, districts, ways=None):
    """The census's trees inside the districts: position, height, species group. Trees the guessed
    carriageways cover are moved out to their kerb (the census stands them in pits on the kerb; our road
    widths are estimates); trees inside a footprint are dropped. Several sources (census.sources) are read
    in turn, each over its own districts; `dedupe` drops a source's trees this close to an earlier one's."""
    from scipy.spatial import cKDTree
    from ..common import districts as all_districts
    groups = CENSUS["groups"]
    bits = CENSUS.get("species_bits", 2)
    assert len(groups) <= 1 << bits, f"census: {len(groups)} groups need species_bits > {bits}"
    dall = all_districts()
    xs, ys, hs, ks, crs = [], [], [], [], []
    rng = np.random.default_rng(15)
    for s in census_sources():
        lon, lat, df = read_census(s)
        pts = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(UTM)
        x, y = pts.x.to_numpy().copy(), pts.y.to_numpy().copy()
        within = s.get("districts")
        area = (dall[dall.name.isin(within)] if within else dall).geometry.union_all()
        keep = shapely.contains_xy(area, x, y)
        g = np.full(len(df), len(groups) - 1)
        if s.get("species"):
            names = df[s["species"]].fillna("").astype(str).str.lower().to_numpy()
            for i, (_, members) in reversed(list(enumerate(groups))):
                g[np.isin(names, [m.lower() for m in members])] = i
        h = census_heights(s, df, g, rng)
        if s.get("dedupe") and xs:
            d, _ = cKDTree(np.column_stack([np.concatenate(xs), np.concatenate(ys)])).query(
                np.column_stack([x, y]), distance_upper_bound=s["dedupe"])
            keep &= ~np.isfinite(d)
        k = (g | rng.integers(0, 256 >> bits, len(df)) << bits).astype(np.uint8)
        if LIFT_FLAG:                  # bit 7: a street tree (source street = true), for on_street
            k = k & np.uint8(127) | np.uint8(128 if s.get("street") else 0)
        # crown_field: the census's crown diameter (m, 0 = unknown) caps the crown's radius at its half x crown_k
        cr = np.full(len(df), 99.0)
        if s.get("crown_field"):
            d_ = pd.to_numeric(df[s["crown_field"]], errors="coerce").fillna(0).to_numpy(float)
            cr = np.where(d_ > 0, np.maximum(d_ / 2 * s.get("crown_k", 1.15), 1.0), 99.0)
        print(f"census {s['file']}: {len(df):,} trees, {int(keep.sum()):,} inside its districts, "
              f"groups {np.bincount(g[keep], minlength=len(groups)).tolist()}")
        xs.append(x[keep]); ys.append(y[keep]); hs.append(h[keep]); ks.append(k[keep]); crs.append(cr[keep])
    x, y, h, k, cr = map(np.concatenate, (xs, ys, hs, ks, crs))
    ok = np.ones(len(x), bool)
    # out of the carriageways: push each covered tree away from its way's centre line to the kerb + 1 m
    roads = ground[ground.kind.isin(["major", "minor", "service"])]
    lines = gpd.GeoSeries(roads.geometry.values, crs=UTM)
    half = roads.width.to_numpy() / 2
    moved = 0
    for _ in range(2):                     # a push can land a tree in a crossing street: once more
        cover = lines.buffer(half, cap_style="flat")
        pi, wi = gpd.GeoSeries(cover.values, crs=UTM).sindex.query(
            gpd.points_from_xy(x, y), predicate="within")
        seen = set()
        for p, w in zip(pi, wi):
            if p in seen or not ok[p]:
                continue
            seen.add(p)
            line = lines.iloc[w]
            q = line.interpolate(line.project(shapely.Point(x[p], y[p])))
            dx, dy = x[p] - q.x, y[p] - q.y
            d = np.hypot(dx, dy)
            if d < 0.05:                   # on the centre line: out to either side
                t = np.asarray(line.interpolate(line.project(q) + 1).coords[0]) - np.asarray(q.coords[0])
                dx, dy, d = -t[1], t[0], max(np.hypot(*t), 1e-6)
            x[p], y[p] = q.x + dx / d * (half[w] + 1.0), q.y + dy / d * (half[w] + 1.0)
            moved += 1
    inb = gpd.GeoSeries(buildings.values, crs=UTM).sindex.query(gpd.points_from_xy(x, y), predicate="within")[0]
    ok[np.unique(inb)] = False
    if OFF_DECKS and ways is not None:
        el = ways[ways.elevated]
        under = gpd.GeoSeries(el.geometry.buffer(el.width / 2 + 1.0, cap_style="flat").values, crs=UTM).sindex.query(
            gpd.points_from_xy(x, y), predicate="within")[0]
        print(f"census_off_decks: {len(np.unique(under)):,} census trees under bridge decks and viaducts dropped")
        ok[np.unique(under)] = False
    print(f"census: {len(x):,} trees, {int(ok.sum()):,} kept, {moved:,} moved to the kerb, "
          f"groups {np.bincount((k[ok] & ((1 << bits) - 1)), minlength=len(groups)).tolist()}")
    return x[ok], y[ok], h[ok], k[ok], cr[ok]


def census_cover(mask, tr, cx, cy):
    """[trees.street.census] cover: where the census already stands for the area trees, the class raster
    (as stored, MASK_CELL) gets none: green areas inside the census's districts holding at least `per_ha`
    census trees a hectare (a city's parks and cemeteries, whose trees it lists; not the gardens it misses nor
    woods it only lists along the drives), and the cells round each census tree (`cells`: 1 = the 3 x 3
    cells) so no invented tree stands beside a real one."""
    cov = CENSUS["cover"]
    from ..common import districts as all_districts
    dall = all_districts()
    names = sorted({n for s in census_sources() for n in (s.get("districts") or dall.name)})
    area = dall[dall.name.isin(names)].geometry.union_all()
    mtr = Affine(MASK_CELL, 0, tr.c, 0, -MASK_CELL, tr.f)
    before = int((mask > 0).sum())
    green = fetch_green(gpd.GeoSeries([area], crs=UTM).buffer(10).iloc[0])
    green = green[green.cls.isin(cov.get("classes", ["forest", "park", "orchard", "scrub", "grass"]))]
    green = green.assign(geometry=green.geometry.intersection(area))
    green = green[~green.geometry.is_empty & (green.area > 400)]
    pts = gpd.points_from_xy(cx, cy)
    _, gi = gpd.GeoSeries(green.geometry.values, crs=UTM).sindex.query(pts, predicate="within")
    cnt = np.bincount(gi, minlength=len(green))
    dens = cnt / (green.area.to_numpy() / 1e4)
    full = green[dens >= cov.get("per_ha", 20)]
    # keep_woods (m, off by default): the woods (forest cells) inside a park the census stands for keep their invented
    # trees wherever no census tree stands within this distance (Berlin M6 critic: the Baumkataster lists the
    # south-east Tiergarten's woods only in part; burning the whole park left a bare lawn with the carpet's stains)
    keep = cov.get("keep_woods", 0)
    wood = (mask == C["forest"]) if keep else None
    burn(mask, mtr, full.geometry, 0)
    if keep:
        mask[wood] = C["forest"]
    print(f"census cover: {len(full):,} of {len(green):,} green areas ({full.area.sum() / 1e6:.2f} km²) have the "
          f"census's trees only" + (f" (their woods kept {keep:.0f} m from a census tree)" if keep else ""))
    col = np.floor((cx - mtr.c) / MASK_CELL).astype(int)
    row = np.floor((mtr.f - cy) / MASK_CELL).astype(int)

    def clear(r, only=None):
        for dr in range(-r, r + 1):
            for dc in range(-r, r + 1):
                if (dr * dr + dc * dc) * MASK_CELL ** 2 > (r + 0.5) ** 2 * MASK_CELL ** 2:
                    continue
                rr, cc = row + dr, col + dc
                ins = (rr >= 0) & (rr < mask.shape[0]) & (cc >= 0) & (cc < mask.shape[1])
                rr, cc = rr[ins], cc[ins]
                if only is not None:
                    hit = mask[rr, cc] == only
                    rr, cc = rr[hit], cc[hit]
                mask[rr, cc] = 0
    r = cov.get("cells", 1)
    if keep:
        clear(max(r, int(np.ceil(keep / MASK_CELL))), C["forest"])
    for dr in range(-r, r + 1):
        for dc in range(-r, r + 1):
            rr, cc = row + dr, col + dc
            ins = (rr >= 0) & (rr < mask.shape[0]) & (cc >= 0) & (cc < mask.shape[1])
            mask[rr[ins], cc[ins]] = 0
    print(f"census cover: {before - int((mask > 0).sum()):,} cells ({(before - int((mask > 0).sum())) * MASK_CELL ** 2 / 1e6:.2f} km²) "
          "left to the census")


def split16(a) -> bytes:
    """int16 array -> its low bytes, then its high bytes (compresses better than interleaved)."""
    b = np.ascontiguousarray(a, np.int16).view(np.uint8).reshape(-1, 2)
    return b[:, 0].tobytes() + b[:, 1].tobytes()


def downsample(raster):
    """CELL -> MASK_CELL raster: a cell takes its first finer cell's class if none of them is empty."""
    f = int(MASK_CELL / CELL)
    h, w = raster.shape[0] // f, raster.shape[1] // f
    r = raster[:h * f, :w * f].reshape(h, f, w, f)
    out = r[:, 0, :, 0].copy()
    out[(r == 0).any((1, 3))] = 0
    return out


def smooth_classes(mask, sigma):
    """[trees] carpet.smooth: the carpet classes (and none: the rest) by largest blurred share."""
    from scipy import ndimage
    lab = np.where(np.isin(mask, [C[c] for c in CARPET_CLASSES]), mask, 0)
    best, share = np.zeros(lab.shape, np.uint8), np.full(lab.shape, -1.0, np.float32)
    for v in np.unique(lab):
        s = ndimage.gaussian_filter((lab == v).astype(np.float32), sigma / MASK_CELL, mode="nearest")
        take = s > share
        best[take], share[take] = v, s[take]
    print(f"carpet smooth {sigma:g} m: {int((best != lab).sum()):,} of {int((lab > 0).sum()):,} carpet cells changed")
    return best


def carpet(mask, tr, origin, terrain: Terrain):
    """Wooded classes as triangles (scene x, z quantized) on the ground, with a class per vertex."""
    if CARPET_OPTS.get("smooth"):
        mask = smooth_classes(mask, float(CARPET_OPTS["smooth"]))
    wooded = np.isin(mask, [C[c] for c in CARPET_CLASSES])
    mtr = Affine(MASK_CELL, 0, tr.c, 0, -MASK_CELL, tr.f)
    verts, ys, cls, idx, nv = [], [], [], [], 0
    for geom, v in rasterio.features.shapes(np.where(wooded, mask, 0), mask=wooded, transform=mtr,
                                           connectivity=4):
        poly = shape(geom).simplify(MASK_CELL * 0.75, preserve_topology=True)
        if poly.is_empty or poly.area < 400:
            continue
        # scene x, z (to_scene mirrors z: earcut doesn't mind)
        poly = shapely.transform(poly, lambda c: np.column_stack([c[:, 0] - origin[0], origin[1] - c[:, 1]]))
        for vv, y, _, tri in terrain.drape(poly):
            a, b, c = vv[tri[:, 0]], vv[tri[:, 1]], vv[tri[:, 2]]
            down = (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]) - (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) < 0
            tri[down] = tri[down][:, [0, 2, 1]]                  # front faces up
            verts.append(vv)
            ys.append(y)
            cls.append(np.full(len(vv), int(v), np.uint8))
            idx.append(tri.reshape(-1).astype(np.uint32) + nv)
            nv += len(vv)
    # the pieces the TIN cut share their vertices again
    xz = np.concatenate(verts)
    m = weld({"pos": np.column_stack([xz[:, 0], np.concatenate(ys), xz[:, 1]]), "cls": np.concatenate(cls),
              "idx": np.concatenate(idx)})
    # vertices in order of first use (neighbours follow each other: the differences stay small)
    order = pd.unique(m["idx"].reshape(-1))
    remap = np.empty(len(m["pos"]), np.int64)
    remap[order] = np.arange(len(order))
    m = {"pos": m["pos"][order], "cls": m["cls"][order], "idx": remap[m["idx"]]}
    q = np.round(m["pos"][:, [0, 2]] / CARPET_Q).astype(np.int16)
    qy = np.clip(np.round(m["pos"][:, 1] / CARPET_YQ), 0, 65535).astype(np.uint16)
    cl, ix = m["cls"], m["idx"].reshape(-1).astype(np.uint32)
    pad = (-(8 + 7 * len(cl))) % 4                          # the indices start on 4 bytes
    d = np.diff(q.astype(np.int32), axis=0, prepend=0).astype(np.int16)
    body = struct.pack("<II", len(q), len(ix)) + split16(d[:, 0]) + split16(d[:, 1]) + \
        split16(qy.view(np.int16)) + cl.tobytes() + bytes(pad) + ix.tobytes()
    (OUT / "carpet.bin").write_bytes(gzip.compress(body, 9))
    print(f"carpet {len(q):,} vertices, {len(ix) // 3:,} triangles")


def worldcover_grid(tr, shape):
    """ESA WorldCover 2021's class on the class raster's grid ([trees] worldcover): read at about 10 m, taken to
    WORLDCOVER_CELL by majority, then to the raster's cells."""
    import rasterio
    from rasterio.transform import from_bounds as tr_bounds
    from rasterio.warp import Resampling, reproject
    from rasterio.windows import from_bounds
    h, w = shape
    x0, y1 = tr.c, tr.f
    x1, y0 = x0 + w * CELL, y1 - h * CELL
    lon, lat = gpd.GeoSeries(gpd.points_from_xy([x0, x1, x0, x1], [y0, y0, y1, y1]), crs=UTM).to_crs("EPSG:4326").pipe(
        lambda g: (g.x.values, g.y.values))
    W_, E_, S_, N_ = lon.min() - 0.01, lon.max() + 0.01, lat.min() - 0.01, lat.max() + 0.01
    d = 1 / 12000                                  # WorldCover's own pixel (0.3 arc seconds)
    WW, HH = int((E_ - W_) / d), int((N_ - S_) / d)
    cls = np.zeros((HH, WW), np.uint8)
    for tlat in range(int(np.floor(S_ / 3) * 3), int(np.floor(N_ / 3) * 3) + 1, 3):
        for tlon in range(int(np.floor(W_ / 3) * 3), int(np.floor(E_ / 3) * 3) + 1, 3):
            tname = f"{'N' if tlat >= 0 else 'S'}{abs(tlat):02d}{'E' if tlon >= 0 else 'W'}{abs(tlon):03d}"
            with rasterio.open(WC_URL.format(tname)) as src:
                bw, be, bs, bn = max(W_, tlon), min(E_, tlon + 3), max(S_, tlat), min(N_, tlat + 3)
                c0, c1 = int(round((bw - W_) / d)), min(int(round((be - W_) / d)), WW)
                r0, r1 = int(round((N_ - bn) / d)), min(int(round((N_ - bs) / d)), HH)
                if c1 <= c0 or r1 <= r0:
                    continue
                cls[r0:r1, c0:c1] = src.read(1, window=from_bounds(bw, bs, be, bn, src.transform), out_shape=(r1 - r0, c1 - c0))
            print(f"  WorldCover {tname}", flush=True)
    src_tr = tr_bounds(W_, S_, E_, N_, WW, HH)
    k = WORLDCOVER_CELL
    mid_tr = Affine(k, 0, x0, 0, -k, y1)
    mid = np.zeros((int(np.ceil(h * CELL / k)), int(np.ceil(w * CELL / k))), np.uint8)
    reproject(cls, mid, src_transform=src_tr, src_crs="EPSG:4326", dst_transform=mid_tr, dst_crs=UTM,
              resampling=Resampling.mode)
    out = np.zeros(shape, np.uint8)
    reproject(mid, out, src_transform=mid_tr, src_crs=UTM, dst_transform=tr, dst_crs=UTM, resampling=Resampling.nearest)
    return out


def zone_classes(mask, tr):
    """[trees.zones] on the stored (MASK_CELL) raster, in place: cells of each zone's `from` classes inside its named
    green areas (osm_green.json) or ring take the zone's class."""
    mtr = Affine(MASK_CELL, 0, tr.c, 0, -MASK_CELL, tr.f)
    res = json.loads(CACHE.read_text()) if CACHE.exists() else {"elements": []}
    for name, z in ZONES.items():
        names = set(z.get("parks", []))
        polys = [g for t, g in element_geoms(res) if t.get("name") in names and g.geom_type in ("Polygon", "MultiPolygon")]
        if z.get("ring"):
            polys.append(Polygon(z["ring"]))
        if not polys:
            print(f"zone {name}: no area found")
            continue
        geoms = gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(UTM).make_valid()
        inside = rasterio.features.rasterize([(g, 1) for g in geoms if not g.is_empty], out_shape=mask.shape,
                                             transform=mtr).astype(bool)
        sel = inside & np.isin(mask, [C[c] for c in z.get("from", ["park", "grass"])])
        mask[sel] = C[name]
        print(f"zone {name}: {len(polys)} areas, {int(sel.sum()) * MASK_CELL ** 2 / 1e4:.1f} ha of tree cells")


def feather(mask, tr, area):
    """[trees] feather on the stored (MASK_CELL) raster, in place."""
    from scipy import ndimage
    rng = np.random.default_rng(31)
    mtr = Affine(MASK_CELL, 0, tr.c, 0, -MASK_CELL, tr.f)
    before = int((mask > 0).sum())
    fringe = FEATHER.get("fringe", 0.0)
    if fringe > 0:
        into = np.isin(mask, [C[c] for c in FEATHER.get("into", ["scrub", "grass", "open"])])
        d = ndimage.distance_transform_edt(mask != C["forest"]) * MASK_CELL
        p = FEATHER.get("share", 0.6) * np.clip(1 - d / fringe, 0, 1) ** 1.5
        sel = into & (rng.random(mask.shape) < p)
        mask[sel] = C["forest"]
        print(f"feather: {int(sel.sum()):,} cells along the forest's edge made forest")
    edge = FEATHER.get("edge", 0.0)
    if edge > 0:
        inside = rasterio.features.rasterize([(area, 1)], out_shape=mask.shape, transform=mtr).astype(bool)
        d = ndimage.distance_transform_edt(inside) * MASK_CELL
        keep = rng.random(mask.shape) < np.clip(d / edge, 0, 1) ** 1.2
        drop = (mask > 0) & ~keep
        mask[drop] = 0
        print(f"feather: {int(drop.sum()):,} cells thinned within {edge:.0f} m of the ground area's edge")
    print(f"feather: {before:,} -> {int((mask > 0).sum()):,} tree cells")


def run(argv):
    if "--green-only" in argv:
        area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
        print(f"green areas: {len(fetch_green(area)):,} (cached in {CACHE})")
    else:
        main()


def main():
    OUT.mkdir(exist_ok=True)
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)              # the scene origin, as in 06_tiles.py
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    ax0, ay0, ax1, ay1 = area.bounds
    tx0, tx1 = int(np.floor((ax0 - origin[0]) / TILE)), int(np.floor((ax1 - origin[0]) / TILE))
    ty0, ty1 = int(np.floor((ay0 - origin[1]) / TILE)), int(np.floor((ay1 - origin[1]) / TILE))

    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    buildings = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM).geometry.make_valid()
    raster, tr = class_raster(area, origin, tx0, tx1, ty0, ty1, ways, buildings)
    sx, sy, sh, sk, sreal, scr = street_trees(ways, raster, tr, buildings)
    raster[raster >= BUILDING] = 0
    mask = downsample(raster)
    del raster
    carpet_mask = mask
    if CENSUS.get("cover"):       # no invented area trees where the census's stand (the carpet keeps them all)
        carpet_mask = mask.copy()
        census_cover(mask, tr, sx[sreal], sy[sreal])
    if FEATHER:
        if carpet_mask is mask:
            carpet_mask = mask.copy()
        feather(mask, tr, area)
    if ZONES:                     # (the carpet keeps the zones' own classes: it has no colour for a zone)
        if carpet_mask is mask:
            carpet_mask = mask.copy()
        zone_classes(mask, tr)
    M = int(TILE / MASK_CELL)

    scap = crown_caps(sx, sy, buildings) if CLIP else np.full(len(sx), 99.0)
    if CLIP:
        print(f"clip_walls: {int((scap < 0.5 * sh * 0.45).sum()):,} crowns capped under 0.45 x half their height")
    crowns = bool((scr < 99).any())        # a census's crown_field: caps written as for clip_walls
    if crowns:
        print(f"crown_field: {int((scr < 99).sum()):,} trees with the census's crown, "
              f"{int(((scr < 99) & (scr < scap)).sum()):,} capped by it")
        scap = np.minimum(scap, scr)
    CAPS = CLIP or crowns
    stx = np.floor((sx - origin[0]) / TILE).astype(int)
    sty = np.floor((sy - origin[1]) / TILE).astype(int)
    order = np.lexsort((sty, stx))
    sx, sy, sh, sk, stx, sty, scap = (a[order] for a in (sx, sy, sh, sk, stx, sty, scap))
    for f in OUT.glob("t_*.bin"):
        f.unlink()
    tiles, size = [], 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            block = mask[(ty1 - ty) * M:(ty1 - ty + 1) * M, (tx - tx0) * M:(tx - tx0 + 1) * M]
            sel = (stx == tx) & (sty == ty)
            n, has = int(sel.sum()), bool(block.any())
            if not n and not has:
                continue
            e0, n0 = origin[0] + tx * TILE, origin[1] + (ty + 1) * TILE      # north-west corner
            qx = np.clip(np.round((sx[sel] - e0) * 10), 0, TILE * 10 - 1).astype(np.int32)
            qz = np.clip(np.round((n0 - sy[sel]) * 10), 0, TILE * 10 - 1).astype(np.int32)
            qh = np.clip(np.round(sh[sel] * HEIGHT_Q), 1, 255).astype(np.uint8)
            body = struct.pack("<II", n, int(has)) + (block.tobytes() if has else b"") + \
                split16(np.diff(qx, prepend=0)) + split16(np.diff(qz, prepend=0)) + qh.tobytes() + \
                sk[sel].tobytes()
            if CAPS:                  # u8[n] crown radius cap in 0.2 m (255: none)
                body += np.clip(np.round(scap[sel] / 0.2), 1, 255).astype(np.uint8).tobytes()
            name = f"t_{tx}_{ty}.bin"
            (OUT / name).write_bytes(gzip.compress(body, 9))
            size += (OUT / name).stat().st_size
            counts = np.bincount(block.ravel(), minlength=len(CLASSES)) if has else np.zeros(len(CLASSES))
            tiles.append({"file": name, "x": tx * TILE, "z": -(ty + 1) * TILE, "street": n,
                          "cover": {c: round(float(counts[i]) * MASK_CELL ** 2 / 1e6, 3)
                                    for i, c in enumerate(CLASSES) if i and counts[i]}})
    carpet(carpet_mask, tr, origin, Terrain())
    index = {"origin": {"utm_epsg": UTM_EPSG, "easting": origin[0], "northing": origin[1]},
             "tileSize": TILE, "cell": MASK_CELL, "classes": CLASSES, "carpet": "carpet.bin",
             "carpetQuant": CARPET_Q, "carpetYQuant": CARPET_YQ, "tiles": tiles}
    if CENSUS:                    # street trees' species bits: a group, drawn as this viewer species
        index["streetSpecies"] = [g[0] for g in CENSUS["groups"]]
        if BITS != 2:
            index["speciesBits"] = BITS
    if HEIGHT_Q != 10:
        index["heightQ"] = HEIGHT_Q
    if CAPS:
        index["caps"] = True
    if LIFT_FLAG:
        index["liftBit"] = 7
    (OUT / "trees.json").write_text(json.dumps(index))
    link_web("trees")
    km2 = {c: round(sum(t["cover"].get(c, 0) for t in tiles), 1) for c in CLASSES[1:]}
    print(f"{len(tiles)} tiles, {len(sx):,} street trees, {size / 1e6:.1f} MB + carpet "
          f"{(OUT / 'carpet.bin').stat().st_size / 1e6:.1f} MB; km² by class {km2}")

