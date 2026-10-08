"""05_ground: fetch the ground layers for the districts and their surroundings from OSM.

Layers (ground.gpkg in the data folder, UTM):
  land     land polygons, built from natural=coastline (OSM draws land on the left of the line); for an
           inland city (city.toml coast = false, or "auto" and no coastline in the area) the whole area
  water    rivers, lakes, reservoirs, ponds
  green    parks, woods, grass, farmland, clipped to the land: reserves and parks are often drawn
           out over the bay (Futian's mangrove reserve covers 4 km² of mudflat), which would otherwise be
           painted as lawn; mangrove stands (wetland=mangrove) are kept whole, as they grow in the tide
  mud      intertidal mudflats (natural=mud, wetland=tidalflat) off the land, less the mangroves
  aeroway  runways, taxiways, aprons
  aerodrome, aerodrome_buildings   the airfields and the buildings on them (06_tiles: grass and roofs)

The area is the districts' bounding box plus MARGIN ([ground] margin), so the view from the edge isn't
empty.
"""
import numpy as np
import shapely
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import linemerge, polygonize, unary_union

from ..common import CFG, DATA, RAW, UTM, boundary, element_geoms, overpass

MARGIN = CFG["ground"]["margin"]
COAST = CFG["coast"]                  # true, false or "auto" (land from the coastline if the area has one)
GREEN = CFG["ground"]["green"]        # OSM key -> values drawn as green
AERO_W = CFG["ground"]["aeroway_width"]   # runway / taxiway widths (m) where untagged
TIDAL = CFG["ground"]["tidal"]        # km²: water bodies this large touching the sea are sea (0: off)
POOLS = CFG["ground"].get("pools", False)   # split the water at dams, weirs and locks (pools())
GRAVEL_PARKS = set(CFG["ground"].get("gravel_parks", []))   # parks by name whose ground is gravel, not lawn
PATHS = CFG["ground"].get("paths", {})   # highway -> width (m): footpaths cut out of the green (empty: none)
PAVED = CFG["ground"].get("paved", False)   # pedestrian areas as layers of their own: "paved" (stone), "asphalt"
# green pieces narrower than this (m) are left out, the land's paving shows instead: slivers of OSM grass along the
# sidewalks read as saturated lawn strips where the street has none (Paris M5 critic: Bd Saint-Germain, Quai de Conti)
GREEN_MIN_W = CFG["ground"].get("green_min_width", 0.0)
# pedestrian squares mapped as multipolygon relations (the Parvis Notre-Dame, r8726561) are areas too: paved, cut out
# of the green (off: only ways with area=yes)
PATH_RELATIONS = CFG["ground"].get("path_relations", False)
# the green less the water (OSM's park and grass polygons often run out over a lake's edge, the Serpentine's: drawn
# as lawn over the water where the bank is higher than the levelled water; off: the green is clipped to the land only)
GREEN_OFF_WATER = CFG["ground"].get("green_off_water", False)
# footpaths through the green on the layer their surface says: loose ones (fine_gravel, compacted, ...) gravel, asphalt
# ones asphalt, stone and untagged ones paved (with [ground] paved), not the land's lots (off: all on the land)
PATH_LAYERS = CFG["ground"].get("path_layers", False)
# [ground] yards (opt-in, Singapore M5): OSM "key=value" areas drawn as paved yards on the aeroway layer (kind "yard":
# the apron's concrete panels, no trees, cars parked on it lifted with it) instead of the land's lots: container
# terminals (industrial=port) read as a patchwork of beige lots and scrub. Clipped to the land, less green and water;
# cached in the data folder (osm_yards.json). [] (default): off
YARDS = CFG["ground"].get("yards", [])
# [ground] slopes (opt-in, Hong Kong M5): man-made slopes mapped as lines (natural=cliff + anthropogenic=yes, the cut
# slopes' crests; man_made=embankment) drawn as grey shotcrete strips on the aeroway layer: a strip `width` m wide on
# the way's right (OSM's convention: the lower side), clipped to the land less green and water; cached in the data
# folder (osm_slopes.json). {tags = ["key=value", ...] (a way matching all of one entry's "a=b;c=d" pairs), width}
SLOPES = CFG["ground"].get("slopes") or {}
# [ground] slopes.areas (opt-in, Hong Kong M7f; with slopes): OSM "key=value" polygons drawn the same grey on the aeroway
# layer (kind "rock"), clipped like the strips: natural=bare_rock and scree (Lion Rock's crown and its south crag, Kowloon
# Peak's Suicide Cliff, which read as smooth green domes); cached as osm_slope_areas.json. [] (default): none
SLOPE_AREAS = SLOPES.get("areas", [])
# [ground] lots_off_green (opt-in, Singapore 7 Oct): surface car parks (amenity=parking, parking=surface or untagged, at
# ground level, not a building, surface not grass or loose) inside a park's green are cut out of it and drawn on the
# asphalt layer: Gardens by the Bay's open-air Meadow car park (w171981662, 284 bays) was lawn with the cars on it. The
# lots come from 06d_cars's cache (raw/osm_parking.json) where it exists, else their own query (osm_ground_lots.json in
# the data folder). Off (default): car parks inside the green stay lawn
LOTS_OFF_GREEN = CFG["ground"].get("lots_off_green", False)
# [ground] green_tags / green_ids (opt-in, Singapore M5 fix round): more areas drawn as green, beyond [ground.green]'s
# single tags: green_tags = ["leisure=pitch;surface=grass"] (an area matching all of one entry's "a=b;c=d" pairs: grass
# sports fields), green_ids = ["way/21587770"] (OSM elements by id: the Padang, a cricket field tagged leisure=pitch with
# no surface, drawn as the land's pale lots). Fetched once into the data folder (osm_green_extra.json, refetched when
# the settings change). Empty (default): off
GREEN_TAGS = CFG["ground"].get("green_tags", [])
GREEN_IDS = CFG["ground"].get("green_ids", [])


def surface_lot(t: dict) -> bool:
    """A paved surface car park at ground level, by its OSM tags (lots_off_green)."""
    if t.get("amenity") != "parking" or "building" in t or t.get("parking", "surface") != "surface":
        return False
    try:
        layer = float(str(t.get("layer", "0")).split(";")[0])
    except ValueError:
        layer = 0.0
    return layer == 0 and t.get("surface") not in SOFT and t.get("location") not in ("underground", "indoor")


def lot_pieces(lots, greens, land, mode):
    """[ground] lots_off_green: the surface car parks' pieces (UTM polygons) to cut out of the green and those to draw
    on the asphalt layer. true: the parts inside the green, both; "all": every lot on the land on the asphalt layer."""
    gs = np.asarray(greens, dtype=object)
    tree = shapely.STRtree(gs)
    inside = []
    for g in lots:
        k = tree.query(g, predicate="intersects")
        if len(k):
            x = g.intersection(shapely.union_all(gs[k]))
            inside.append(unary_union([p for p in getattr(x, "geoms", [x]) if p.geom_type in ("Polygon", "MultiPolygon")]))
    inside = [g for g in inside if not g.is_empty and g.area > 20]
    if mode == "all":
        # (Singapore M7: the Bayfront Plaza lot w1121873001 lay on WorldCover's grass, not in a park polygon: cars on
        # a lawn)
        every = [g.intersection(land) for g in lots]
        return inside, [g for g in every if not g.is_empty and g.area > 20]
    return inside, inside


def width_m(tags: dict) -> float:
    """Runway/taxiway width from the width tag, else a typical value."""
    try:
        return float(str(tags.get("width", "")).split()[0])
    except (ValueError, IndexError):
        return AERO_W["runway"] if tags.get("aeroway") == "runway" else AERO_W["taxiway"]


def hidden(t: dict) -> bool:
    """Water out of sight: in a tunnel or culvert, covered (the Canal Saint-Martin's vaults under the Boulevard
    Richard-Lenoir, covered reservoirs), underground or indoors, or below ground (layer < 0)."""
    try:
        layer = float(str(t.get("layer", "0")).split(";")[0])
    except ValueError:
        layer = 0.0
    return (t.get("tunnel", "no") != "no" or t.get("covered", "no") != "no" or layer < 0
            or t.get("location") in ("underground", "indoor"))


def pools(water: gpd.GeoDataFrame, bb: str, area) -> gpd.GeoDataFrame:
    """The water bodies split at dams, weirs and locks ([ground] pools), so 05a_terrain levels each pool on
    its own: a river held by dams steps down at each (the Seine: 26.7 m NGF through Paris above the Suresnes
    dam, 23.4 m below it), a canal at each lock. Cuts: dam, weir and lock-gate lines (lengthened by CUT_EXT at
    both ends, to reach the banks), and lines across the waterway at both ends of every lock chamber
    (waterway=* with lock=yes) and at every lock-gate node. The water isn't cut: each piece between the cuts
    becomes a row (touching bodies merged) with its pool number, grown back over the cut."""
    CUT_EXT, CROSS = 12.0, 40.0          # m: dam lines lengthened, half-width of the lines across a waterway
    res = cached_query(f"""
        [out:json][timeout:600][bbox:{bb}];
        (
          way["waterway"~"^(dam|weir|lock_gate)$"]; node["waterway"="lock_gate"];
          way["waterway"]["lock"="yes"]; way["waterway"~"^(river|canal)$"];
        );
        out geom;""", RAW / "osm_barriers.json")
    gates = [Point(e["lon"], e["lat"]) for e in res["elements"] if e["type"] == "node"]
    lines, courses = [], []
    for t, g in element_geoms(res):
        if t.get("waterway") in ("dam", "weir", "lock_gate") and t.get("lock") != "yes":
            lines.append(g)
        elif g.geom_type == "LineString":
            courses.append((t.get("lock") == "yes", g))
    to = lambda gs: list(to_utm(gs)) if gs else []   # noqa: E731
    cuts = []
    for g in to(lines):
        if g.geom_type == "LineString":
            c = np.asarray(g.coords)
            d0, d1 = c[0] - c[1], c[-1] - c[-2]
            c[0] += d0 / max(np.hypot(*d0), 1e-9) * CUT_EXT
            c[-1] += d1 / max(np.hypot(*d1), 1e-9) * CUT_EXT
            cuts.append(LineString(c))
        else:
            cuts.append(g)

    def across(p, d):
        n = np.array([-d[1], d[0]]) / max(np.hypot(*d), 1e-9)
        return LineString([p - n * CROSS, p + n * CROSS])

    course_u = to([g for _, g in courses])
    for (lock, _), g in zip(courses, course_u):
        if lock:
            c = np.asarray(g.coords)
            cuts += [across(c[0], c[1] - c[0]), across(c[-1], c[-1] - c[-2])]
    if gates and course_u:
        from shapely import STRtree
        tree = STRtree(course_u)
        for p in to(gates):
            k = tree.nearest(p)
            g = course_u[k]
            if g.distance(p) > 5:
                continue
            s = g.project(p)
            a, b = g.interpolate(max(s - 2, 0)), g.interpolate(min(s + 2, g.length))
            cuts.append(across(np.array(p.coords[0]), np.array(b.coords[0]) - np.array(a.coords[0])))
    whole = unary_union(list(water.geometry.make_valid()))
    cut = unary_union(cuts).buffer(0.4)
    pieces = [p for p in getattr(whole.difference(cut), "geoms", [whole.difference(cut)]) if p.area > 1]
    grown = [p.buffer(0.8).intersection(whole) for p in pieces]
    out = gpd.GeoDataFrame({"pool": np.arange(len(grown))}, geometry=grown, crs=UTM)
    n_bodies = len(getattr(whole, "geoms", [whole]))
    print(f"pools: {len(cuts)} cuts (dams, weirs, locks) split {n_bodies} water bodies into {len(out)} pools")
    return out


LOOSE = {"gravel", "fine_gravel", "compacted", "sand", "dirt", "ground", "unpaved", "pebblestone"}
SOFT = LOOSE | {"grass", "grass_paver", "wood", "metal", "woodchips", "mud"}   # neither stone nor asphalt


def cut_out(geoms, pieces, within=None):
    """Each geometry less the pieces that meet it (an STRtree per piece, not one union of all: Paris's 55k
    paths over 30k green areas took 9 minutes as one difference)."""
    import shapely
    pieces = np.asarray([p for p in pieces if p is not None and not p.is_empty], dtype=object)
    if within is not None and len(pieces):
        pieces = shapely.intersection(pieces, within)
    tree = shapely.STRtree(pieces)
    out = []
    for g in geoms:
        k = tree.query(g, predicate="intersects")
        out.append(g.difference(shapely.union_all(pieces[k])) if len(k) else g)
    return gpd.GeoSeries(out, index=geoms.index, crs=UTM)


def to_utm(geoms):
    return gpd.GeoSeries(geoms, crs="EPSG:4326").to_crs(UTM)


def land_from_coastline(lines: gpd.GeoSeries, area: Polygon, coast=True) -> gpd.GeoSeries:
    """Land faces of the area cut by the coastline: those whose probes mostly fall left of the lines. Without
    a coastline in the area (coast "auto", or false: an inland city) the whole area is land."""
    lines = lines.intersection(area)
    lines = lines[~lines.is_empty]
    if coast is False or (coast == "auto" and not len(lines)):
        return gpd.GeoSeries([area], crs=UTM)
    faces = list(polygonize(unary_union(list(lines) + [area.exterior])))
    faces = gpd.GeoSeries(faces, crs=UTM)
    votes = np.zeros(len(faces))
    for line in lines:
        for part in getattr(line, "geoms", [line]):
            c = np.asarray(part.coords)
            if len(c) < 2:
                continue
            mid = (c[1:] + c[:-1]) / 2
            d = c[1:] - c[:-1]
            n = np.stack([-d[:, 1], d[:, 0]], 1) / np.linalg.norm(d, axis=1, keepdims=True).clip(1e-9)
            for sign, vote in ((1, 1), (-1, -1)):          # left of the line is land
                pts = gpd.GeoSeries([Point(p) for p in mid[::5] + sign * 2.0 * n[::5]], crs=UTM)
                hit = gpd.sjoin(gpd.GeoDataFrame(geometry=pts), gpd.GeoDataFrame(geometry=faces),
                                predicate="within")
                np.add.at(votes, hit.index_right.values, vote)
    return faces[votes > 0]


CACHE = RAW / "osm_ground.json"
PIERS = CFG["ground"]["piers"]        # man_made=pier decks join the land


def green_extra_query(bb: str) -> str:
    """The Overpass query for [ground] green_tags and green_ids over the bounding box bb ("s,w,n,e")."""
    sel = ""
    for entry in GREEN_TAGS:
        f = "".join(f'["{k}"="{v}"]' for k, v in (kv.split("=", 1) for kv in entry.split(";")))
        sel += f"way{f}; rel{f};"
    for ref in GREEN_IDS:
        kind, i = str(ref).split("/")
        sel += f"{'way' if kind == 'way' else 'rel'}(id:{int(i)});"
    return f"[out:json][timeout:600][bbox:{bb}];({sel});out geom;"


def green_extra(bb: str) -> list:
    """[ground] green_tags and green_ids: their areas (WGS84 geometries), cached in the data folder with the query."""
    import json
    q = green_extra_query(bb)
    cache = DATA / "osm_green_extra.json"
    res = json.loads(cache.read_text()) if cache.exists() else None
    if res is None or res.get("query") != q:
        res = overpass(q)
        res["query"] = q
        cache.write_text(json.dumps(res))
    out = [g for t, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")]
    print(f"green extra: {len(out)} areas ({len(GREEN_TAGS)} tag rules, {len(GREEN_IDS)} ids)")
    return out


def cached_query(q: str, cache=None) -> dict:
    """A query's answer, cached (the ground query in raw/osm_ground.json; delete it to fetch again)."""
    import json
    cache = cache or CACHE
    if cache.exists():
        return json.loads(cache.read_text())
    res = overpass(q)
    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(res))
    return res


def main():
    area_utm = box(*boundary().total_bounds).buffer(MARGIN, join_style="mitre")
    s, w, n, e = gpd.GeoSeries([area_utm], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    bb = f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"

    # [ground.green] keys beyond leisure, landuse and natural (Berlin: tourism = ["zoo"], the Zoo's wooded grounds)
    extra_green = "".join(f'way["{k}"~"^({"|".join(v)})$"]; rel["{k}"~"^({"|".join(v)})$"];'
                          for k, v in GREEN.items() if k not in ("leisure", "landuse", "natural") and v)
    res = cached_query(f"""
        [out:json][timeout:900][bbox:{bb}];
        (
          way["natural"="coastline"];
          way["natural"="water"]; rel["natural"="water"];
          way["waterway"="riverbank"]; rel["waterway"="riverbank"];
          way["landuse"="reservoir"]; rel["landuse"="reservoir"];
          way["leisure"~"^({'|'.join(GREEN['leisure'])})$"]; rel["leisure"~"^({'|'.join(GREEN['leisure'])})$"];
          way["landuse"~"^({'|'.join(GREEN['landuse'])})$"]; rel["landuse"~"^({'|'.join(GREEN['landuse'])})$"];
          way["natural"~"^({'|'.join(GREEN['natural'])})$"]; rel["natural"~"^({'|'.join(GREEN['natural'])})$"];
          {extra_green}
          way["aeroway"~"^(runway|taxiway|apron)$"];
          way["natural"="mud"]; rel["natural"="mud"];
          way["wetland"="tidalflat"]; rel["wetland"="tidalflat"];
        );
        out geom;
    """)

    coast, water, green, mangrove, mud, aero, gravel_parks = [], [], [], [], [], [], []
    for t, g in element_geoms(res):
        if t.get("natural") == "coastline":
            coast.append(g if isinstance(g, LineString) else g.exterior)
        elif t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("landuse") == "reservoir":
            if g.geom_type in ("Polygon", "MultiPolygon") and not hidden(t):
                water.append(g)
        elif "aeroway" in t:
            if t["aeroway"] in ("runway", "taxiway") and g.geom_type == "LineString":
                aero.append((t["aeroway"], g, width_m(t)))
            elif g.geom_type in ("Polygon", "MultiPolygon"):
                aero.append((t["aeroway"], g, 0))
        elif g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        elif t.get("natural") == "mud" or t.get("wetland") == "tidalflat":
            mud.append(g)
        elif t.get("wetland") == "mangrove":
            mangrove.append(g)
        elif t.get("name") in GRAVEL_PARKS and t.get("leisure") in ("park", "garden"):
            gravel_parks.append(g)
        else:
            green.append(g)

    if GREEN_TAGS or GREEN_IDS:
        green += green_extra(bb)
    coast_utm = to_utm([linemerge(c) if c.geom_type == "MultiLineString" else c for c in coast])
    land = land_from_coastline(coast_utm, area_utm, COAST)


    def layer(geoms, clip_to=area_utm):
        s = to_utm(geoms).make_valid().intersection(clip_to)
        s = s[~s.is_empty & s.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"])]
        s = s.apply(lambda g: unary_union([p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")]))
        return gpd.GeoDataFrame(geometry=s[~s.is_empty], crs=UTM)

    aero_polys = []
    for kind, g, width in aero:
        gu = to_utm([g]).iloc[0]
        aero_polys.append((kind, gu.buffer(width / 2, cap_style="flat") if width else gu))
    aero_gdf = gpd.GeoDataFrame({"kind": [k for k, _ in aero_polys]},
                                geometry=[g for _, g in aero_polys], crs=UTM)

    water_l = layer(water)
    if POOLS:
        water_l = pools(water_l, bb, area_utm)
    if TIDAL and len(land) and land.area.sum() < area_utm.area:
        # tidal rivers and estuaries OSM maps as water polygons over the land (the Hudson and the East River
        # beside Manhattan: the coastline only rings the harbour): large water touching the sea joins it
        sea = area_utm.difference(unary_union(list(land)))
        wu = unary_union(list(water_l.geometry.make_valid()))
        tidal = [w for w in getattr(wu, "geoms", [wu]) if w.area >= TIDAL * 1e6 and w.buffer(5).intersects(sea)]
        if tidal:
            t = unary_union(tidal)
            land = gpd.GeoSeries([g for g in land.difference(t).explode(index_parts=False) if g.area > 50], crs=UTM)
            water_l["geometry"] = water_l.geometry.difference(t)
            water_l = water_l[~water_l.is_empty & (water_l.area > 1)]
            print(f"tidal: {len(tidal)} water bodies ({t.area / 1e6:.1f} km²) joined the sea")
    if PIERS and len(land):
        # piers over the water (man_made=pier: Manhattan's Hudson River Park piers, Chelsea Piers, the heliport):
        # decks the buildings on them stand on, drawn as land; lines are buffered by their width
        pr = cached_query(f"""
            [out:json][timeout:600][bbox:{bb}];
            (way["man_made"="pier"]; rel["man_made"="pier"]; way["man_made"="breakwater"];);
            out geom;""", RAW / "osm_piers.json")
        decks = []
        for t, g in element_geoms(pr):
            if g.geom_type in ("Polygon", "MultiPolygon"):
                decks.append(g)
            elif t.get("man_made") == "pier" and g.geom_type == "LineString":
                w = width_m({"width": t.get("width", "")}) if t.get("width") else 4.0
                decks.append((t, g, w))
        polys = to_utm([d for d in decks if not isinstance(d, tuple)]) if decks else gpd.GeoSeries([], crs=UTM)
        lines = [to_utm([g]).iloc[0].buffer(w / 2, cap_style="flat") for t, g, w in (d for d in decks if isinstance(d, tuple))]
        dk = unary_union(list(polys.make_valid()) + lines).intersection(area_utm)
        land = gpd.GeoSeries([p for p in getattr(unary_union(list(land) + [dk]), "geoms", [unary_union(list(land) + [dk])])
                              if p.area > 20], crs=UTM)
        water_l["geometry"] = water_l.geometry.difference(dk)
        water_l = water_l[~water_l.is_empty & (water_l.area > 1)]
        print(f"piers: {len(decks)} ({dk.area / 1e6:.2f} km²) added to the land")
    # airfields (aeroway=aerodrome): open land between the runways, never drawn as the town's roofscape
    ad = cached_query(f"""
        [out:json][timeout:600][bbox:{bb}];
        (way["aeroway"="aerodrome"]; rel["aeroway"="aerodrome"];);
        out geom;""", RAW / "osm_aerodromes.json")
    fields = [g for t, g in element_geoms(ad) if g.geom_type in ("Polygon", "MultiPolygon")]
    out = DATA / "ground.gpkg"
    out.unlink(missing_ok=True)
    fields_l = layer(fields)
    fields_l.to_file(out, layer="aerodrome")
    if len(fields_l):
        # the airfields' buildings (terminals, garages, hangars): roofs among the grass, not lawn where the
        # terminals stand (06_tiles draws them as the town's roofscape)
        bb_a = gpd.GeoSeries(list(fields_l.geometry), crs=UTM).to_crs("EPSG:4326").total_bounds
        ab = cached_query(f"""
            [out:json][timeout:600][bbox:{bb_a[1]:.5f},{bb_a[0]:.5f},{bb_a[3]:.5f},{bb_a[2]:.5f}];
            (way["building"]; rel["building"];);
            out geom;""", RAW / "osm_aerodrome_buildings.json")
        blds = layer([g for t, g in element_geoms(ab) if g.geom_type in ("Polygon", "MultiPolygon")],
                     clip_to=unary_union(list(fields_l.geometry)))
        blds.to_file(out, layer="aerodrome_buildings")
        print(f"aerodromes: {len(fields_l)}, {len(blds)} buildings on them")
    gpd.GeoDataFrame(geometry=land, crs=UTM).to_file(out, layer="land")
    water_l.to_file(out, layer="water")
    land_all = unary_union(list(land.geometry if hasattr(land, "geometry") else land))
    mangroves = layer(mangrove)
    greens = layer(green)
    greens["geometry"] = greens.geometry.intersection(land_all)
    if GREEN_OFF_WATER and len(water_l):
        greens["geometry"] = cut_out(greens.geometry, list(water_l.geometry.make_valid()))
        print("green: less the water")
    greens = greens[~greens.is_empty]
    gravel, paved, asphalt = [], [], []
    if PATHS:
        # footpaths through the parks ([ground] paths: highway -> width): cut out of the lawn, so the land's
        # paving shows (Central Park's 58 miles of paths), within the roads' reach only; pedestrian and footway
        # areas (area=yes: squares, the parks' esplanades) are cut out whole
        reach = boundary().geometry.union_all().buffer(CFG["roads"]["margin"])
        rb = gpd.GeoSeries([reach], crs=UTM).to_crs("EPSG:4326").total_bounds
        pr = cached_query(f"""
            [out:json][timeout:600][bbox:{rb[1]:.5f},{rb[0]:.5f},{rb[3]:.5f},{rb[2]:.5f}];
            way["highway"~"^({'|'.join(PATHS)})$"];
            out geom;""", RAW / "osm_paths.json")
        lines, areas, line_tags = [], [], []
        for t, g in element_geoms(pr):
            if t.get("footway") in ("sidewalk", "crossing") or t.get("tunnel", "no") != "no" or \
                    t.get("bridge", "no") != "no" or t.get("covered", "no") != "no":
                continue
            if g.geom_type == "Polygon" and t.get("area") == "yes":
                areas.append((t, g))
            else:
                lines.append((g.exterior if g.geom_type == "Polygon" else g, PATHS[t["highway"]]))
                line_tags.append(t)
        if PATH_RELATIONS:
            rr = cached_query(f"""
                [out:json][timeout:600][bbox:{rb[1]:.5f},{rb[0]:.5f},{rb[3]:.5f},{rb[2]:.5f}];
                rel["highway"~"^(pedestrian|footway)$"]["type"="multipolygon"];
                out geom;""", RAW / "osm_paths_rel.json")
            rels = [(t, g) for t, g in element_geoms(rr) if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
            areas += rels
            print(f"paths: {len(rels)} pedestrian multipolygons")
        lu = to_utm([g for g, _ in lines])
        pieces = list(shapely.buffer(np.asarray(list(lu), dtype=object), np.array([w / 2 for _, w in lines]),
                                     cap_style="flat"))
        au = list(to_utm([g for _, g in areas]).make_valid()) if areas else []
        pieces += au
        gravel += [g for (t, _), g in zip(areas, au) if t.get("surface") in LOOSE]
        if PATH_LAYERS:
            # (only the parts through the green: elsewhere the path lies on the land, as before)
            # (each path against the green pieces it meets, an STRtree, not one union of all the green)
            gs = np.asarray(list(greens.geometry), dtype=object)
            gtree = shapely.STRtree(gs)
            through = []
            for t, p in zip(line_tags, pieces[:len(line_tags)]):
                if t.get("surface") is None or (t.get("surface") in SOFT and t.get("surface") not in LOOSE):
                    continue
                k = gtree.query(p, predicate="intersects")
                if len(k):
                    through.append((t, p.intersection(shapely.union_all(gs[k]))))
            loose_p = [p for t, p in through if t.get("surface") in LOOSE]
            gravel += loose_p
            if PAVED:
                asphalt += [p for t, p in through if t.get("surface") == "asphalt"]
                paved += [p for t, p in through if t.get("surface") not in LOOSE and t.get("surface") != "asphalt"]
            print(f"paths: {len(through):,} through the green on their surface's layer ({len(loose_p):,} loose)")
        if PAVED:
            # [ground] paved: the squares and parvis (Notre-Dame's, the Sacré-Cœur's) otherwise show the land's
            # lots (bare soil, weedy concrete) where they are cut out of the green: stone (paving_stones, sett,
            # concrete, untagged) and asphalt pedestrian areas each get a layer of their own
            asphalt += [g for (t, _), g in zip(areas, au) if t.get("surface") == "asphalt"]
            paved += [g for (t, _), g in zip(areas, au) if t.get("surface") not in SOFT and t.get("surface") != "asphalt"]
        greens["geometry"] = cut_out(greens.geometry, pieces, reach)
        greens = greens[~greens.is_empty]
        print(f"paths: {len(lines):,} ways and {len(areas):,} pedestrian areas cut out of the green")
    if LOTS_OFF_GREEN:
        pk = RAW / "osm_parking.json"
        pr = cached_query(f"""
            [out:json][timeout:600][bbox:{bb}];
            (way["amenity"="parking"]; rel["amenity"="parking"]["type"="multipolygon"];);
            out geom;""", pk if pk.exists() else DATA / "osm_ground_lots.json")
        lots = [g for t, g in element_geoms(pr) if g.geom_type in ("Polygon", "MultiPolygon") and surface_lot(t)]
        if lots:
            lu = [g for g in to_utm(lots).make_valid() if not g.is_empty]
            inside, lots_asphalt = lot_pieces(lu, list(greens.geometry), land_all, LOTS_OFF_GREEN)
            if inside:
                greens["geometry"] = cut_out(greens.geometry, inside)
                greens = greens[~greens.is_empty]
            asphalt += lots_asphalt
            inside = lots_asphalt
            print(f"lots off the green: {len(inside)} of {len(lu)} surface car parks, "
                  f"{sum(g.area for g in inside) / 1e4:.1f} ha on the asphalt layer")
    if GREEN_MIN_W:
        parts = greens.geometry.explode(index_parts=False)
        wide = ~shapely.is_empty(shapely.buffer(np.asarray(parts.values), -GREEN_MIN_W / 2))
        print(f"green: {int((~wide).sum()):,} pieces under {GREEN_MIN_W:.1f} m wide left out "
              f"({parts[~wide].area.sum() / 1e4:.1f} ha)")
        greens = gpd.GeoDataFrame(geometry=parts[wide].values, crs=UTM)
    gpd.GeoDataFrame(geometry=pd.concat([greens.geometry, mangroves.geometry], ignore_index=True),
                     crs=UTM).to_file(out, layer="green")
    # gravel ("stabilisé": the Tuileries' and the Luxembourg's allées, [ground] gravel_parks less their lawns and
    # beds) and loose-surfaced pedestrian areas: a layer of its own for the ground's gravel colour
    gv = layer(gravel_parks).geometry.intersection(land_all) if gravel_parks else gpd.GeoSeries([], crs=UTM)
    gv = gpd.GeoSeries(list(gv) + gravel, crs=UTM)
    if len(gv):
        gv = cut_out(gv, list(greens.geometry) + list(water_l.geometry))
    gv = gv[~gv.is_empty & gv.geom_type.isin(["Polygon", "MultiPolygon"])] if len(gv) else gv
    gpd.GeoDataFrame(geometry=gv, crs=UTM).to_file(out, layer="gravel")
    print(f"gravel: {len(gravel_parks)} parks by name, {len(gravel)} loose pedestrian areas, {gv.area.sum() / 1e4:.1f} ha")
    if PAVED or LOTS_OFF_GREEN:
        # (less the gravel, the green and the water; stone wins where a stone and an asphalt area overlap)
        taken = list(greens.geometry) + list(water_l.geometry) + list(gv)
        pv = gpd.GeoSeries(paved, crs=UTM)
        pv = cut_out(pv, taken) if len(pv) and taken else pv
        pv = pv[~pv.is_empty & pv.geom_type.isin(["Polygon", "MultiPolygon"])] if len(pv) else pv
        av = gpd.GeoSeries(asphalt, crs=UTM)
        av = cut_out(av, taken + list(pv)) if len(av) else av
        av = av[~av.is_empty & av.geom_type.isin(["Polygon", "MultiPolygon"])] if len(av) else av
        gpd.GeoDataFrame(geometry=pv, crs=UTM).to_file(out, layer="paved")
        gpd.GeoDataFrame(geometry=av, crs=UTM).to_file(out, layer="asphalt")
        print(f"paved: {len(pv)} stone pedestrian areas {pv.area.sum() / 1e4:.1f} ha, "
              f"{len(av)} asphalt {av.area.sum() / 1e4:.1f} ha")
    muds = layer(mud)
    muds["geometry"] = muds.geometry.difference(land_all).difference(unary_union(list(mangroves.geometry)))
    muds[~muds.is_empty].to_file(out, layer="mud")
    if YARDS:
        sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in (y.split("=", 1) for y in YARDS))
        yr = cached_query(f"[out:json][timeout:600][bbox:{bb}];({sel});out geom;", DATA / "osm_yards.json")
        yl = layer([g for t, g in element_geoms(yr) if g.geom_type in ("Polygon", "MultiPolygon")])
        if len(yl):
            yu = unary_union(list(yl.geometry.make_valid())).intersection(land_all)
            taken = unary_union(list(greens.geometry.make_valid()) + list(water_l.geometry.make_valid()))
            yu = yu.difference(taken)
            polys = [p for p in getattr(yu, "geoms", [yu]) if p.geom_type == "Polygon" and p.area > 100]
            aero_gdf = pd.concat([aero_gdf, gpd.GeoDataFrame({"kind": ["yard"] * len(polys)}, geometry=polys, crs=UTM)],
                                 ignore_index=True)
            print(f"yards {YARDS}: {len(polys)} pieces, {sum(p.area for p in polys) / 1e6:.2f} km² on the aeroway layer")
    if SLOPES:
        sel = "".join("way" + "".join(f'["{k}"="{v}"]' for k, v in (kv.split("=", 1) for kv in t.split(";"))) + ";"
                      for t in SLOPES["tags"])
        sr = cached_query(f"[out:json][timeout:600][bbox:{bb}];({sel});out geom;", DATA / "osm_slopes.json")
        lines = [g for t, g in element_geoms(sr) if g.geom_type == "LineString"]
        if lines:
            ls = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(UTM)
            strips = ls.buffer(-float(SLOPES.get("width", 12.0)), single_sided=True, cap_style="flat")
            su = unary_union(list(strips.make_valid())).intersection(land_all)
            taken = unary_union(list(water_l.geometry.make_valid()) + list(aero_gdf.geometry.make_valid()) +
                                (list(greens.geometry.make_valid()) if SLOPES.get("off_green", True) else []))
            su = su.difference(taken)
            polys = [p for p in getattr(su, "geoms", [su]) if p.geom_type == "Polygon" and p.area > 20]
            aero_gdf = pd.concat([aero_gdf, gpd.GeoDataFrame({"kind": ["slope"] * len(polys)}, geometry=polys, crs=UTM)],
                                 ignore_index=True)
            print(f"slopes: {len(lines):,} ways, {len(polys):,} strips, {sum(p.area for p in polys) / 1e4:.1f} ha on the aeroway layer")
    if SLOPE_AREAS:
        sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in (y.split("=", 1) for y in SLOPE_AREAS))
        rr = cached_query(f"[out:json][timeout:600][bbox:{bb}];({sel});out geom;", DATA / "osm_slope_areas.json")
        rl = layer([g for t, g in element_geoms(rr) if g.geom_type in ("Polygon", "MultiPolygon")])
        if len(rl):
            ru = unary_union(list(rl.geometry.make_valid())).intersection(land_all)
            taken = unary_union(list(water_l.geometry.make_valid()) + list(aero_gdf.geometry.make_valid()))
            ru = ru.difference(taken)
            polys = [p for p in getattr(ru, "geoms", [ru]) if p.geom_type == "Polygon" and p.area > 20]
            # the rock over OSM's grassland and woods (country parks are mapped whole): the green layer cut round it
            greens["geometry"] = cut_out(greens.geometry, polys)
            greens = greens[~greens.is_empty]
            gpd.GeoDataFrame(geometry=pd.concat([greens.geometry, mangroves.geometry], ignore_index=True),
                             crs=UTM).to_file(out, layer="green")
            aero_gdf = pd.concat([aero_gdf, gpd.GeoDataFrame({"kind": ["rock"] * len(polys)}, geometry=polys, crs=UTM)],
                                 ignore_index=True)
            print(f"slopes.areas {SLOPE_AREAS}: {len(polys):,} pieces, {sum(p.area for p in polys) / 1e4:.1f} ha on the aeroway layer")
    aero_gdf.to_file(out, layer="aeroway")
    gpd.GeoDataFrame(geometry=[area_utm], crs=UTM).to_file(out, layer="area")
    print(f"area {area_utm.area / 1e6:.0f} km²; coastline ways {len(coast)}; land {land.area.sum() / 1e6:.1f} km² "
          f"in {len(land)} pieces; water {len(water)}; green {len(green)}; mangrove {len(mangrove)}; "
          f"mudflat {len(mud)} ({muds.area.sum() / 1e6:.1f} km²); aeroway {len(aero)}")

