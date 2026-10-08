"""06e_masses: the town beyond the districts as low-poly block masses ([ground] masses, off by default).

The districts' buildings are modelled one by one (04_buildings, 06_tiles). Beyond them, over the ground area's
margin and `masses_reach` metres into the backdrop, a dense city goes on (Paris's petite couronne: Boulogne,
Levallois, Saint-Denis, Montreuil at 9,000 people per km²). Painted on the ground it read as an empty plain "like
farmland", La Défense standing alone in a field (Paris M3/M4 critics). This stage raises it as masses:

  fetch    OSM buildings over the area from Overpass, in chunks: footprint, building, height, building:levels
           -> town_buildings.gpkg (UTM; kept, delete it to fetch again)
  heights  height, else building:levels x level_h (+1 m of roof), else by kind (houses 7.5 m, sheds 3.5 m,
           apartments 17 m...), else (building=yes, most of a cadastre import) by the built cover around it:
           continuous blocks read as 5-6 storeys, scattered ones as houses; +-12 % per building
  masses   per 4 km cell (the viewer's block size) and 3 m height class: footprints merged (touching ones
           become one block), simplified 1.5 m, sheds under 25 m² left out; flat roofs, walls down to 1.5 m
           under the ground; each vertex's top is its ground plus the height, so a block on a slope follows it.
           Beyond the ground area the ground is the backdrop's surface, and the buildings thin out towards
           masses_reach (a random share kept, falling to 0; the biggest last), so there is no line where they end.
  colours  vertex RGB: walls pale render, stone, some brick and concrete; roofs zinc grey, slate, terracotta
           (houses), gravel and membrane (flat blocks); the viewer's masses material adds storeys and windows

[ground] masses_within = "<file>.geojson" (off by default) keeps only the masses whose footprint lies inside a set of
WGS84 polygons (a band on the land side, the gap between a core and an island) and fetches OSM only over the chunks
that touch them; see read_clip().

With [terrain] backdrop_cover = "worldcover" it also writes the backdrop's land cover maps: ESA WorldCover 2021
(10 m, CC BY 4.0, read from its public COGs on AWS) as colours (woods, autumn fields, grass, towns in
backdrop_town_rgb, water), tiles_raw/cover.jpg at 50 m a pixel over the backdrop and cover_inner.jpg at 20 m
over the masses' zone (the viewer's gardens and trees between the masses read it too). The
backdrop's vertices lie kilometres apart on the flats; coloured by height they made Paris's plateaus one dark
forest. `city3d 06e_masses --cover-only` makes only the map.

Writes tiles_raw/m_L<I>_<J>.glb (one mesh "masses": the blocks of a 12 km cell, a few draws for the whole
ring; Paris M7: 209 draws at the overview in 4 km cells) and m_h<i>_<j>.glb (the houses of a 4 km cell, drawn
only near) and tiles_raw/masses.json (their tile entries);
06_tiles adds those entries to tiles.json whenever it writes it, and so does this stage, so 07_pack and
07b_blocks ship them with the building tiles.
"""
import functools
import hashlib
import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy import ndimage as ndi
from shapely.ops import unary_union

from ..common import CFG, CITY, DATA, LEVEL_H, UTM, Terrain, boundary, element_geoms, height_m, overpass
from .tiles import OUT as RAW_TILES, polygons, triangulate, write_glb

G = CFG["ground"]
REACH = float(G.get("masses_reach", 0.0))       # m beyond the ground area
CELL = 4000                                      # m: the houses' cells (drawn only within a few km)
SUPER = 12000                                    # m: the blocks' cells (one draw each)
FAR_MIN = 150.0                                  # m²: beyond the ground area smaller masses are left out
# m: over the reach's last FADE m the masses sink to 30 % of their height (no confetti edge; [ground] masses_fade)
FADE = float(G.get("masses_fade", 1500.0))
# [ground] masses_thin (default true): beyond the ground area the masses thin out and sink towards the reach. false
# (Singapore M7, with masses_within): every mass inside the clip stands at its height wherever it lies, for far towns
# drawn as islands of masses well inside the reach (Johor Bahru's and Batam's skylines 15-25 km out over the water)
THIN = bool(G.get("masses_thin", True))
# [terrain] cover_inner_reach (m beyond the ground area; default: masses_reach): how far the inner cover map (and the
# OSM roads and footprints painted into it) reaches; a far masses_reach for a few far towns need not grow it
INNER_REACH = float(CFG["terrain"].get("cover_inner_reach", REACH) if CFG["terrain"].get("cover_inner_reach") is not None else REACH)
CACHE = DATA / "town_buildings.gpkg"
INDEX = RAW_TILES / "masses.json"
# [ground] masses_houses_far: houses (under 9 m) beyond the ground area kept too, thinned as the blocks are (by
# default they go: the cover map's town colour stands for them). London's outer boroughs are terraces of 2-3
# storey houses to the horizon: without them the ring past the ground area read as bare ground with scattered
# blocks (M3 critic)
HOUSES_FAR = bool(G.get("masses_houses_far", False))
# [terrain] cover_roads: highway -> width (m) painted into the inner land cover map (asphalt), so the town layer
# far out and the backdrop round the masses show their street grid; empty: off
COVER_ROADS = CFG["terrain"].get("cover_roads", {})
ROADS_CACHE = DATA / "town_roads.json"
ROAD_RGB = (84, 84, 86)
# [terrain] cover_buildings: the town's footprints (town_buildings.gpkg) painted into the inner land cover map in the
# town colour, so WorldCover's trees in back yards don't tint the ground under and round the masses as soft green
# smears (Berlin M7); false: off
COVER_BUILDINGS = bool(CFG["terrain"].get("cover_buildings", False))
# cover_buildings = "all": every OSM footprint over the inner map is painted (its own cache, cover_buildings.gpkg,
# fetched over the inner map's box), not only the masses' (with masses_within only those inside the clip were): a city
# whose masses stand only in some gaps keeps a town of painted roofs all round (Tokyo M3 critic: Ueno, Ryogoku and
# Shinagawa read as an empty tan plain)
COVER_ALL = CFG["terrain"].get("cover_buildings", False) == "all"
COVER_CACHE = DATA / "cover_buildings.gpkg"
# [terrain] cover_lines { cell, rail, yard }: a line map over the inner cover map (cover_lines.png, `cell` m a pixel,
# lossless): R the share of each pixel under a cover_roads road, G under a rail bed (OSM railway ways off tunnels,
# `rail` m wide each; landuse=railway land at `yard`), B the direction of the nearest track within ~3 pixels (0 none,
# 1..254 the angle in scene x/z over 0..pi). The town layer draws asphalt, ballast and track lines from it where the
# 20 m colour map smeared rail corridors into a mottled grey-brown band (Berlin M7 critic: the Ringbahn and the A100
# south of the Tempelhofer Feld); empty: off
COVER_LINES = CFG["terrain"].get("cover_lines", {})
# [terrain] cover_roofs { rgb = [[r, g, b], ...], gaps = [r, g, b] } (sRGB; with cover_buildings): the footprints painted
# into the inner map as roofs, each in one of `rgb` (picked by a hash of its centre: list a colour twice to weight it),
# and the built-up land no footprint or road covers (alleys, yards, car parks) in `gaps`, instead of all of it in the
# town colour: Tokyo's roofscape from 2-8 km is a pale carpet of roofs over darker streets, which a flat town colour
# drew as a bare grey plain with no footprints (Tokyo M3 critic 2). Empty: off
COVER_ROOFS = CFG["terrain"].get("cover_roofs", {})
# [terrain] cover_yards (opt-in, Singapore M5): [r, g, b] (sRGB): the [ground] yards areas (container terminals) painted
# into both land cover maps in this colour, not WorldCover's built-up town (Pasir Panjang's terminal past the ground
# area); OSM fetched over each map's box, cached as cover_yards.json. Absent: off
COVER_YARDS = CFG["terrain"].get("cover_yards")
RAILS_CACHE = DATA / "town_rails.json"
# [terrain] cover_outer_roads = { widths = { highway = m, ... }, rgb = [r, g, b] } (opt-in, Tokyo M7 fix round): the major
# roads painted into the outer cover map (cover.jpg) too, as shares of its pixels, so the plain past the inner map keeps
# a street network to the horizon (Tokyo M7 critic: from the TMG the street pattern stopped where the inner map ended,
# then a flat grey plain). OSM from Overpass over the outer map's box, cached as outer_roads.json. Empty: off
OUTER_ROADS = CFG["terrain"].get("cover_outer_roads") or {}
OUTER_ROADS_CACHE = DATA / "outer_roads.json"
# [ground] masses_skip { field: [values] }: footprints left out of the masses (towers and masts as fat windowed blocks)
MASSES_SKIP = G.get("masses_skip", {})
# [ground] masses_tall = {area, h}: footprints of `area` m² or more raised over `h` m are held at h: one OSM outline round
# a tower and its podium (Tokyo's CO·MO·RE Yotsuya, 145 m over 10,570 m²) stood as a block-wide slab at tower height;
# the podium's height reads truer from afar. Empty: off
MASSES_TALL = G.get("masses_tall", {})

# [ground] masses_within: a GeoJSON file (path from the city folder) of WGS84 Polygons / MultiPolygons; only masses whose
# footprint lies inside their union are kept (Singapore: a 500 m band on the land side; Tokyo: the gaps between its
# core and two islands). "" (the default): off, the code path is the one before the key existed
MASSES_WITHIN = str(G.get("masses_within", "") or "")
# [ground] masses_tall_within = { file = "<file>.geojson", min_h = 30.0 } (opt-in, Singapore M7; with masses_within):
# a second clip where only the masses of min_h m and more stand (the HDB towns' 12-40 storey blocks to the horizon,
# not their low shophouses and terraces); fetched with the first. Empty (default): off
TALL_WITHIN = G.get("masses_tall_within") or {}
# masses_tall_within.tagged = true (opt-in, Tokyo M7; default false): the tall clip is fetched on its own, asking Overpass
# only for buildings tagged at least min_h tall (height, or building:levels x level_h + 1), in chunks of `chunk` degrees
# (default 0.2), cached as town_buildings_tall.gpkg; the main clip alone goes into town_buildings.gpkg. Tokyo's tall clip
# is the Kanto plain within ~35 km (Ikebukuro, Shinagawa, Musashi-Kosugi, Minato Mirai, Makuhari, Saitama Shintoshin):
# millions of buildings, of which a few thousand stand over the skyline
TALL_TAGGED = bool(TALL_WITHIN.get("tagged", False))
# [ground] masses_ring = { file = "<file>.geojson", cover_h = [[c0, c1, ...], [h0, h1, ...]] } (opt-in, Tokyo M7 fix
# round; with masses_within and [terrain] cover_buildings = "all"): a ring of town round the districts raised as masses
# from the footprints the inner cover map is painted with (cover_buildings.gpkg, fetched already: no Overpass call), every
# building whose point lies in the ring's polygons (WGS84), with the masses' heights (tagged, levels, kind, else by the
# built cover round it: cover_h, optional, the cover shares and the heights between, instead of Paris's 7-17 m, for the
# ring's untagged footprints only). The roads' built_only clip ([roads], masses_within) is not widened: no streets,
# trees or cars come with it. The roofscape then goes on past the area's edge instead of a painted plain (Tokyo M7
# critic: north of Ueno, west of Nishi-Shinjuku). Empty (default): off
# (and edge = { file, width, h, thin }, opt-in, Tokyo M8: the ring's untagged masses lower and sparser over its last
# `width` m to the outer edge of `file`, the ring's whole extent: ring_edge)
RING = G.get("masses_ring") or {}
TALL_CACHE = DATA / "town_buildings_tall.gpkg"
TALL_STAMP = DATA / "town_buildings_tall.clip"
CLIP_STAMP = DATA / "town_buildings.clip"      # what the cache was fetched for, written only when masses_within is set
# [ground] masses_min_h (opt-in, Hong Kong M7f; m): only masses of at least this height stand (the margin's new towns'
# 30-40 storey estates as a wall of towers, their low villages, schools and sheds left to the painted roofscape),
# wherever they lie, with masses_within's clip or without. 0 (default): off
MIN_H = float(G.get("masses_min_h", 0.0) or 0.0)

KIND_H = {**{k: 7.5 for k in ("house", "detached", "semidetached_house", "bungalow", "terrace", "farm", "villa")},
          **{k: 3.5 for k in ("garage", "garages", "shed", "carport", "hut", "kiosk", "roof", "greenhouse", "cabin",
                              "toilets", "service", "storage_tank", "container", "allotment_house", "bunker")},
          **{k: 9.0 for k in ("industrial", "warehouse", "retail", "supermarket", "commercial", "hangar",
                              "manufacture", "factory", "sports_hall", "parking", "transportation", "train_station")},
          **{k: 17.0 for k in ("apartments", "residential", "dormitory", "hotel")},
          **{k: 13.0 for k in ("school", "university", "college", "hospital", "public", "civic", "government",
                              "kindergarten")},
          "office": 20.0, "church": 18.0, "cathedral": 25.0}
SKIP = {"construction", "no", "ruins", "demolished", "proposed", "collapsed", "destroyed"}


def read_clip(path) -> shapely.Geometry:
    """The union of the Polygons and MultiPolygons in a GeoJSON file (a FeatureCollection, a Feature or a bare
    geometry; WGS84 lon/lat) as one geometry. A path from the city folder, or absolute. A missing file, bad JSON,
    no polygon, an empty union or coordinates that are not lon/lat is an error that says which key it is."""
    p = Path(path)
    p = p if p.is_absolute() else CITY / p
    what = f"[ground] masses_within = {str(path)!r} ({p})"
    if not p.is_file():
        raise FileNotFoundError(f"{what}: no such file (a GeoJSON of WGS84 polygons, a path from the city folder)")
    try:
        data = json.loads(p.read_text())
    except ValueError as e:
        raise ValueError(f"{what}: not valid JSON ({e})") from e
    polys = []

    def walk(o):
        t = o.get("type") if isinstance(o, dict) else None
        if t == "FeatureCollection":
            for f in o.get("features") or []:
                walk(f)
        elif t == "Feature":
            walk(o.get("geometry"))
        elif t == "GeometryCollection":
            for g in o.get("geometries") or []:
                walk(g)
        elif t in ("Polygon", "MultiPolygon"):
            polys.append(shapely.geometry.shape(o))
    walk(data)
    if not polys:
        raise ValueError(f"{what}: holds no Polygon or MultiPolygon")
    g = unary_union([shapely.make_valid(q) for q in polys])
    parts = [q for q in shapely.get_parts(g) if q.geom_type == "Polygon" and not q.is_empty]
    # make_valid may leave lines and points: only the polygons count
    if not parts or sum(q.area for q in parts) <= 0:
        raise ValueError(f"{what}: the polygons are empty")
    g = unary_union(parts)
    x0, y0, x1, y1 = g.bounds
    if min(x0, x1) < -180 or max(x0, x1) > 180 or min(y0, y1) < -90 or max(y0, y1) > 90:
        raise ValueError(f"{what}: coordinates outside lon/lat ({x0:.4f} {y0:.4f} {x1:.4f} {y1:.4f}); WGS84, lon first")
    return g


@functools.lru_cache(maxsize=None)
def clip(part="all"):
    """The masses_within union in UTM, or None when the key is empty (everything below is then skipped); with
    masses_tall_within, "all" is both clips' union (what is fetched), "main" the first, "tall" the second."""
    if not MASSES_WITHIN:
        return None
    if part == "tall" and not TALL_WITHIN:
        return None
    if part == "ring":
        if not RING:
            return None
        g = gpd.GeoSeries([read_clip(RING["file"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
        shapely.prepare(g)
        return g
    if part == "all" and TALL_WITHIN:
        g = unary_union([clip("main"), clip("tall")])
    else:
        path = TALL_WITHIN["file"] if part == "tall" else MASSES_WITHIN
        g = gpd.GeoSeries([read_clip(path)], crs="EPSG:4326").to_crs(UTM).iloc[0]
    shapely.prepare(g)
    return g


def keep_clipped(b) -> np.ndarray:
    """masses_within (and masses_tall_within): which of the footprints (with heights `h`) stand."""
    keep = within(b.geometry, clip("main"))
    if RING:
        keep |= b["ring"].fillna(False).to_numpy(bool) if "ring" in b else within(b.geometry, clip("ring"))
    if TALL_WITHIN:
        keep |= within(b.geometry, clip("tall")) & (b["h"].to_numpy() >= float(TALL_WITHIN.get("min_h", 30.0)))
    return keep


def within(geoms: gpd.GeoSeries, area) -> np.ndarray:
    """Which footprints stay: the ones whose representative point (a point inside the footprint, unlike the centroid
    of an L or a courtyard block) lies in `area`. A building is kept or dropped whole: clipped at the line, a
    block would end in a cut-off slab, and the masses merge whole buildings into blocks anyway."""
    rp = geoms.representative_point()
    return shapely.contains_xy(area, rp.x.to_numpy(), rp.y.to_numpy())


def clip_stamp(area, region) -> str:
    """What a town_buildings.gpkg fetched under masses_within was fetched for: the clip and the box it was cut to."""
    h = hashlib.sha1(shapely.to_wkb(shapely.set_precision(area, 1.0))).hexdigest()
    return f"{h} {' '.join(f'{round(v / 100)}' for v in region.bounds)}"


def tall_filter(min_h) -> str:
    """masses_tall_within.tagged: the Overpass filter for buildings tagged at least min_h m tall."""
    lv = int(np.ceil((float(min_h) - 1.0) / LEVEL_H))
    return f'(if: number(t["height"]) >= {float(min_h):g} || number(t["building:levels"]) >= {lv})'


def fetch(bbox_ll, only=None, tags="", chunk=None) -> gpd.GeoDataFrame:
    """OSM buildings in (lon0, lat0, lon1, lat1), in chunks of about 5 x 5 km; with `only` (a lon/lat geometry:
    masses_within) just the chunks that touch it; `tags` an Overpass filter after the bbox (tall_filter), `chunk`
    the chunks' size in degrees of longitude."""
    lon0, lat0, lon1, lat1 = bbox_ll
    cx, cy = (chunk, chunk * 0.045 / 0.07) if chunk else (0.07, 0.045)
    nx, ny = max(1, int(np.ceil((lon1 - lon0) / cx))), max(1, int(np.ceil((lat1 - lat0) / cy)))
    rows, seen = [], set()
    for i in range(nx):
        for j in range(ny):
            b = (lat0 + (lat1 - lat0) * j / ny, lon0 + (lon1 - lon0) * i / nx,
                 lat0 + (lat1 - lat0) * (j + 1) / ny, lon0 + (lon1 - lon0) * (i + 1) / nx)
            if only is not None and not only.intersects(shapely.box(b[1], b[0], b[3], b[2])):
                continue
            bb = ",".join(f"{v:.6f}" for v in b)
            res = overpass(f"[out:json][timeout:900];(way[building]({bb}){tags};relation[building]({bb}){tags};);out geom;")
            n0 = len(rows)
            for e in res["elements"]:
                key = (e["type"], e["id"])
                if key in seen:
                    continue
                t = e.get("tags", {})
                if t.get("building", "yes") in SKIP or t.get("location") == "underground":
                    continue
                g = next(iter(element_geoms({"elements": [e]})), (None, None))[1]
                if g is None or g.geom_type not in ("Polygon", "MultiPolygon") or g.is_empty:
                    continue
                seen.add(key)
                rows.append({"osm": f"{e['type'][0]}{e['id']}", "building": t.get("building", "yes"),
                             "height": t.get("height"), "levels": t.get("building:levels"),
                             "min_level": t.get("building:min_level"), "geometry": g})
            del res
            print(f"  chunk {i},{j}: {len(rows) - n0:,} buildings ({len(rows):,} in all)", flush=True)
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(UTM)
    g["geometry"] = g.geometry.make_valid()
    return g


def heights(b: gpd.GeoDataFrame, area, cover_h=None) -> np.ndarray:
    """Metres per building: tagged, else by levels, else by kind, else by the built cover round it (cover_h: a
    boolean mask of the buildings that take masses_ring's cover_h instead of the default curve)."""
    h = b["height"].map(height_m).to_numpy(float)
    lv = b["levels"].map(height_m).to_numpy(float) * LEVEL_H + 1.0
    h = np.where(np.isfinite(h), h, lv)
    kind = b["building"].map(KIND_H).to_numpy(float)
    # the built cover within ~120 m: a 5 m raster of the footprints, box-averaged
    x0, y0, x1, y1 = b.total_bounds
    res = 5.0
    nx, ny = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
    from rasterio import features
    from rasterio.transform import from_origin
    tr = from_origin(x0, y1, res, res)
    cover = features.rasterize(((g, 1) for g in b.geometry.values), out_shape=(ny, nx), transform=tr, dtype=np.uint8)
    cover = ndi.uniform_filter(cover.astype(np.float32), int(240 / res))
    c = b.geometry.representative_point()
    ci = np.clip(((c.x - x0) / res).astype(int), 0, nx - 1)
    cj = np.clip(((y1 - c.y) / res).astype(int), 0, ny - 1)
    cov = cover[cj, ci]
    a = b.area.to_numpy()
    # building=yes: continuous blocks of 5-6 storeys where the cover is high (Levallois, Boulogne, Montreuil's
    # centre), 3-4 storeys between, houses (pavillons) where it is low; big footprints are sheds and halls
    dens = np.interp(cov, [0.15, 0.28, 0.42, 0.55], [7.0, 9.5, 14.0, 17.0])
    if cover_h is not None and RING.get("cover_h"):
        cx, hy = RING["cover_h"]
        dens = np.where(cover_h, np.interp(cov, cx, hy), dens)
    dens = np.where(a < 30, 3.5, np.where((a > 1500) & (cov < 0.35), 10.0, dens))
    h = np.where(np.isfinite(h), h, np.where(np.isfinite(kind), kind, dens))
    seed = (b["osm"].str[1:].astype(np.int64).to_numpy() * 2654435761 % 1000) / 1000
    h = np.where(np.isfinite(b["height"].map(height_m).to_numpy(float)), h, h * (0.88 + 0.24 * seed))
    return np.clip(h, 3.0, 260.0)


class Ground:
    """Heights on the ground TIN inside the ground area and on the backdrop's surface beyond it."""

    def __init__(self, terrain: Terrain, rect):
        import matplotlib.tri as mtri
        self.t, self.rect = terrain, rect
        bk = terrain.backdrop
        xyz = bk["back_xyz"].astype(np.float64)
        tri = mtri.Triangulation(xyz[:, 0], xyz[:, 2], bk["back_tri"].astype(np.int64))
        self.back = mtri.LinearTriInterpolator(tri, xyz[:, 1])

    def __call__(self, x, z):
        x0, z0, x1, z1 = self.rect
        inside = (x > x0) & (x < x1) & (z > z0) & (z < z1)
        y = np.zeros(len(x))
        if inside.any():
            y[inside] = self.t.height(x[inside], z[inside])
        if (~inside).any():
            y[~inside] = np.asarray(self.back(x[~inside], z[~inside]).filled(0.0))
        return y


# roofs (the viewer's masses.js has the colours): 0 gravel, 1 membrane, 2 pale coating, 3 zinc, 4 slate, 5 terracotta
ROOF_KINDS = 6


def palette(h, seed):
    """Per mass: sRGB (0..1) wall colour and a roof kind (ROOF_KINDS)."""
    walls = np.array([[0.62, 0.58, 0.52], [0.70, 0.66, 0.58], [0.56, 0.53, 0.50], [0.66, 0.62, 0.55],
                      [0.52, 0.36, 0.28], [0.60, 0.60, 0.58], [0.74, 0.71, 0.64]])
    wp = np.array([0.22, 0.2, 0.14, 0.16, 0.08, 0.12, 0.08])
    wall = walls[np.searchsorted(np.cumsum(wp), seed[:, 0] * 0.999)] * (0.9 + 0.2 * seed[:, 2])[:, None]
    r = seed[:, 1]
    roof = np.where(r < 0.5, 0, np.where(r < 0.8, 1, 2))                  # flat blocks and towers
    mid = (h >= 9) & (h < 24)                          # 3-7 storeys: zinc and slate mansards, some tiles, some flat
    roof[mid] = np.where(r[mid] < 0.35, 3, np.where(r[mid] < 0.55, 4, np.where(r[mid] < 0.75, 5, roof[mid])))
    low = h < 9                                        # houses: terracotta mostly, slate
    roof[low] = np.where(r[low] < 0.7, 5, 4)
    return np.clip(wall, 0, 1), roof


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def extrude_all(polys, hs, ground: Ground, origin, rng):
    """One mesh of flat-roofed masses (scene coordinates), each a closed shell whose roof and walls share their
    vertices (the viewer shades it flat, from the surface's own slope): the top ring at ground + height, the
    bottom ring 1.5 m under the ground. Colour: the wall's (linear RGB), alpha the roof's kind / 8."""
    P, C, I, E = [], [], [], []
    nv = 0
    seeds = rng.random((len(polys), 3))
    wall_rgb, roof_kind = palette(np.asarray(hs), seeds)
    wall_rgb = to_linear(wall_rgb)
    for poly, h, wc, rk in zip(polys, hs, wall_rgb, roof_kind):
        verts, tri = triangulate(poly)
        if not len(tri):
            continue
        n = len(verts)
        x, z = verts[:, 0] - origin[0], -(verts[:, 1] - origin[1])
        g = ground(x, z)
        P.append(np.column_stack([x, g + h, z])); P.append(np.column_stack([x, g - 1.5, z]))
        C.append(np.tile(np.r_[wc, rk / 8], (2 * n, 1)))
        I.append(tri + nv); E.append(np.tile([0.0, 1.0, 0.0], (len(tri), 1)))
        # walls: per ring, each edge a quad between the top ring (nv + i) and the bottom one (nv + n + i)
        start = 0
        for ring in [poly.exterior, *poly.interiors]:
            m = len(ring.coords) - 1
            if m < 3:
                continue
            i = np.arange(m) + start
            j = (np.arange(m) + 1) % m + start
            ti, tj, bi, bj = nv + i, nv + j, nv + n + i, nv + n + j
            I.append(np.column_stack([bi, bj, tj])); I.append(np.column_stack([bi, tj, ti]))
            d = np.column_stack([x[j - 0] - x[i], z[j] - z[i]])
            out = np.column_stack([d[:, 1], np.zeros(m), -d[:, 0]])           # either side: fixed by the winding
            E.append(out); E.append(out)
            start += m
        nv += 2 * n
    if not P:
        return None
    pos, col, idx, exp = np.concatenate(P), np.concatenate(C), np.concatenate(I), np.concatenate(E)
    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    # walls: outward is away from the polygon (the exterior ring counter-clockwise in UTM, holes clockwise, after
    # orient()); in scene coordinates (z south) the side 'out' above points inward for a counter-clockwise ring
    wall = exp[:, 1] == 0
    exp[wall] *= -1
    flip = (fn * exp).sum(1) < 0
    idx[flip] = idx[flip][:, [0, 2, 1]]
    return {"pos": pos, "col": col, "idx": idx.reshape(-1)}


COVER_URL = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
# Two maps (Paris M7 critic: at 100 m a pixel, bilinearly magnified, the land read as blurred camouflage and the
# Seine past the masses as a soft smudge): the whole backdrop at COVER_CELL, and the masses' zone (the ground
# area and masses_reach round it) at COVER_INNER, which the viewer also reads for the gardens and trees between
# the masses. JPEG: a tenth of a PNG of the same map.
# [terrain] cover_cell (m; default 50): the outer map's metres a pixel (Tokyo M7: its backdrop 160 x 115 km to Mount Fuji)
COVER_CELL = float(CFG["terrain"].get("cover_cell", 50.0))
# [terrain] snow = {from, full, rgb, patchy} (opt-in, Tokyo M7; default none; needs [terrain] curvature, whose back_h holds
# the backdrop's heights before it): the outer map white above a snow line, none at `from` m, all of it at `full`, in
# `rgb` (sRGB), the ramp broken by `patchy` (0-1) of a 300 m noise so the line runs in gullies and tongues rather than
# a contour (Mount Fuji's cap in mid-October)
SNOW = CFG["terrain"].get("snow") or {}
# [terrain] cover_inner_cell: the inner map's metres a pixel (default 20; Tokyo 10: its blocks and streets at 20 m
# averaged into one grey)
COVER_INNER = float(CFG["terrain"].get("cover_inner_cell", 20.0))
# WorldCover class -> sRGB as seen from afar in early October: woods, shrubs, grass, fields (stubble, ploughland
# and winter wheat), built-up (the town colour), bare, water, wetland. Water as the city's Seine seen from above
# (olive-dark, not the blue-grey that read as a pale ribbon beside it)
COVER_RGB = {10: (50, 66, 40), 20: (82, 92, 60), 30: (98, 110, 72), 40: (126, 120, 92), 60: (146, 138, 124),
             80: (40, 52, 44), 90: (74, 88, 66), 95: (50, 66, 40), 100: (98, 110, 72)}


def _cover_map(terrain: Terrain, rect, cell, dlon, dlat, name):
    """One colour map of WorldCover over rect (scene x0, z0, x1, z1), `cell` m a pixel, read at about
    dlon x dlat degrees; its entry for tiles.json."""
    import rasterio
    from PIL import Image
    from pyproj import Transformer
    from rasterio.transform import from_bounds as tr_bounds
    from rasterio.warp import Resampling, reproject
    from rasterio.windows import from_bounds
    ox, oy = terrain.origin
    x0, z0, x1, z1 = rect
    nx, nz = int(round((x1 - x0) / cell)), int(round((z1 - z0) / cell))
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform([ox + x0, ox + x1, ox + x0, ox + x1], [oy - z0, oy - z0, oy - z1, oy - z1])
    w, e, s, n = min(lon) - 0.01, max(lon) + 0.01, min(lat) - 0.01, max(lat) + 0.01
    W, H = int((e - w) / dlon), int((n - s) / dlat)
    cls = np.zeros((H, W), np.uint8)
    src_tr = tr_bounds(w, s, e, n, W, H)
    for tlat in range(int(np.floor(s / 3) * 3), int(np.floor(n / 3) * 3) + 1, 3):
        for tlon in range(int(np.floor(w / 3) * 3), int(np.floor(e / 3) * 3) + 1, 3):
            tname = f"{'N' if tlat >= 0 else 'S'}{abs(tlat):02d}{'E' if tlon >= 0 else 'W'}{abs(tlon):03d}"
            with rasterio.open(COVER_URL.format(tname)) as src:
                bw, be = max(w, tlon), min(e, tlon + 3)
                bs, bn = max(s, tlat), min(n, tlat + 3)
                c0, c1 = int(round((bw - w) / dlon)), int(round((be - w) / dlon))
                r0, r1 = int(round((n - bn) / dlat)), int(round((n - bs) / dlat))
                c1, r1 = min(c1, W), min(r1, H)
                if c1 <= c0 or r1 <= r0:
                    continue
                cls[r0:r1, c0:c1] = src.read(1, window=from_bounds(bw, bs, be, bn, src.transform),
                                             out_shape=(r1 - r0, c1 - c0))
            print(f"  WorldCover {tname} ({name})", flush=True)
    town = tuple(CFG["terrain"]["backdrop_town_rgb"])
    dst_tr = rasterio.Affine(cell, 0, ox + x0, 0, -cell, oy - z0)
    out = np.zeros((3, nz, nx), np.float32)
    lut = np.zeros((256, 3), np.float32)
    lut[:] = COVER_RGB[30]
    for k, c in {**COVER_RGB, 50: town}.items():
        lut[k] = c
    for b in range(3):
        reproject(lut[cls, b], out[b], src_transform=src_tr, src_crs="EPSG:4326", dst_transform=dst_tr, dst_crs=UTM,
                  resampling=Resampling.average)
    if COVER_ROOFS and name == "cover_inner.jpg":
        # the built-up share of each pixel in the gaps' colour instead of the town's (roofs and roads go over it)
        built = np.zeros((nz, nx), np.float32)
        reproject((cls == 50).astype(np.float32), built, src_transform=src_tr, src_crs="EPSG:4326", dst_transform=dst_tr,
                  dst_crs=UTM, resampling=Resampling.average)
        for b in range(3):
            out[b] += (float(COVER_ROOFS["gaps"][b]) - town[b]) * built
    if COVER_YARDS and CFG["ground"].get("yards"):
        frac = yard_cover(dst_tr, nz, nx, (w, s, e, n))
        for b in range(3):
            out[b] = out[b] * (1 - frac) + float(COVER_YARDS[b]) * frac
    if OUTER_ROADS and name == "cover.jpg":
        frac = road_cover(dst_tr, nz, nx, cell, (w, s, e, n), OUTER_ROADS["widths"], OUTER_ROADS_CACHE)
        rgb = OUTER_ROADS.get("rgb", ROAD_RGB)
        for b in range(3):
            out[b] = out[b] * (1 - frac) + float(rgb[b]) * frac
    if COVER_ROADS and name == "cover_inner.jpg":
        frac = road_cover(dst_tr, nz, nx, cell, (w, s, e, n))
        for b in range(3):
            out[b] = out[b] * (1 - frac) + ROAD_RGB[b] * frac
    if COVER_BUILDINGS and name == "cover_inner.jpg" and CACHE.exists():
        if COVER_ROOFS:
            fracs = building_cover(dst_tr, nz, nx, len(COVER_ROOFS["rgb"]))
            out = paint_roofs(out, fracs, COVER_ROOFS["rgb"])
        else:
            frac = building_cover(dst_tr, nz, nx)
            for b in range(3):
                out[b] = out[b] * (1 - frac) + town[b] * frac
    if SNOW and name == "cover.jpg" and "back_h" in terrain.backdrop:
        out = paint_snow(out, terrain, x0, z0, cell)
    img = np.clip(np.moveaxis(out, 0, 2), 0, 255).round().astype(np.uint8)
    Image.fromarray(img).save(RAW_TILES / name, quality=90, optimize=True)
    share = {k: float((cls == k).mean()) for k in (10, 30, 40, 50, 80)}
    print(f"{name} {nx} x {nz} ({(RAW_TILES / name).stat().st_size / 1e6:.1f} MB): "
          + ", ".join(f"{k} {v:.0%}" for k, v in share.items()), flush=True)
    return {"file": name, "x0": float(x0), "z0": float(z0), "x1": float(x1), "z1": float(z1)}


def paint_snow(out, terrain: Terrain, x0, z0, cell):
    """[terrain] snow over the outer map (3, nz, nx): white by the backdrop's height before the curvature (back_h)."""
    import matplotlib.tri as mtri
    b = terrain.backdrop
    xyz, h = b["back_xyz"], b["back_h"].astype(np.float64)
    top = h > float(SNOW["from"]) - 400            # only the triangles near the snow line and above
    t = b["back_tri"][top[b["back_tri"]].any(1)]
    if not len(t):
        return out
    nz, nx = out.shape[1:]
    # the pixels within those triangles' box
    v = np.unique(t)
    bx0, bx1 = xyz[v, 0].min(), xyz[v, 0].max()
    bz0, bz1 = xyz[v, 2].min(), xyz[v, 2].max()
    i0, i1 = max(int((bx0 - x0) / cell), 0), min(int((bx1 - x0) / cell) + 2, nx)
    j0, j1 = max(int((bz0 - z0) / cell), 0), min(int((bz1 - z0) / cell) + 2, nz)
    tri = mtri.Triangulation(xyz[:, 0].astype(np.float64), xyz[:, 2].astype(np.float64), t)
    jj, ii = np.mgrid[j0:j1, i0:i1]
    X, Z = x0 + (ii + 0.5) * cell, z0 + (jj + 0.5) * cell
    H = mtri.LinearTriInterpolator(tri, h)(X, Z).filled(-1e9)
    rng = np.random.default_rng(11)
    noise = ndi.gaussian_filter(rng.normal(0, 1, H.shape), 300 / cell / 2)
    noise /= max(noise.std(), 1e-9)
    span = float(SNOW["full"]) - float(SNOW["from"])
    k = np.clip((H - float(SNOW["from"]) + float(SNOW.get("patchy", 0.0)) * span * noise) / span, 0, 1)
    k = k * k * (3 - 2 * k)
    for c in range(3):
        out[c, j0:j1, i0:i1] = out[c, j0:j1, i0:i1] * (1 - k) + float(SNOW["rgb"][c]) * k
    print(f"  snow: {int((k > 0.5).sum()):,} pixels over half white ({(k > 0.5).sum() * cell * cell / 1e6:.1f} km²)",
          flush=True)
    return out


def yard_cover(dst_tr, nz, nx, ll):
    """The share of each map pixel in a [ground] yards area ([terrain] cover_yards), at a quarter pixel."""
    import rasterio
    from rasterio import features
    w, s, e, n = ll
    cache = DATA / "cover_yards.json"
    res = json.loads(cache.read_text()) if cache.exists() else None
    if res is None or res.get("bbox") != [w, s, e, n]:
        sel = "".join(f'way["{k}"="{v}"]; rel["{k}"="{v}"];' for k, v in (y.split("=", 1) for y in CFG["ground"]["yards"]))
        res = overpass(f"[out:json][timeout:600][bbox:{s},{w},{n},{e}];({sel});out geom;")
        res["bbox"] = [w, s, e, n]
        cache.write_text(json.dumps(res))
    polys = [g for t, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")]
    gs = gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(UTM)
    k = 4
    fine = rasterio.Affine(dst_tr.a / k, 0, dst_tr.c, 0, dst_tr.e / k, dst_tr.f)
    r = features.rasterize(((p, 1) for p in gs.values if not p.is_empty), out_shape=(nz * k, nx * k),
                           transform=fine, dtype=np.uint8) if len(gs) else np.zeros((nz * k, nx * k), np.uint8)
    frac = r.reshape(nz, k, nx, k).mean(axis=(1, 3)).astype(np.float32)
    print(f"  cover yards: {len(polys)} areas, {frac.mean():.2%} of the map", flush=True)
    return frac


def road_cover(dst_tr, nz, nx, cell, ll, widths_by_kind=None, cache=None):
    """The share of each map pixel under a road ([terrain] cover_roads: highway -> width m), rasterized at a
    quarter of the pixel and averaged. OSM highways from Overpass over the map's lon/lat box (cached as
    town_roads.json in the city's data folder; cover_outer_roads: its own widths and cache)."""
    from rasterio import features
    COVER_ROADS = widths_by_kind or globals()["COVER_ROADS"]
    cache = cache or ROADS_CACHE
    w, s, e, n = ll
    if cache.exists():
        res = json.loads(cache.read_text())
    else:
        kinds = "|".join(COVER_ROADS)
        res = overpass(f'[out:json][timeout:900];way["highway"~"^({kinds})$"]({s},{w},{n},{e});out tags geom;')
        cache.write_text(json.dumps(res))
    lines, widths = [], []
    for el in res["elements"]:
        g = el.get("geometry")
        hw = el.get("tags", {}).get("highway")
        if not g or hw not in COVER_ROADS or el.get("tags", {}).get("tunnel") in ("yes", "building_passage"):
            continue
        lines.append(shapely.LineString([(p["lon"], p["lat"]) for p in g]))
        widths.append(float(COVER_ROADS[hw]))
    gs = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(UTM)
    polys = gs.buffer(np.asarray(widths) / 2, cap_style="flat")
    k = 4
    import rasterio
    fine = rasterio.Affine(dst_tr.a / k, 0, dst_tr.c, 0, dst_tr.e / k, dst_tr.f)
    r = features.rasterize(((p, 1) for p in polys.values if not p.is_empty), out_shape=(nz * k, nx * k),
                           transform=fine, dtype=np.uint8)
    frac = r.reshape(nz, k, nx, k).mean(axis=(1, 3)).astype(np.float32)
    print(f"  cover roads ({cache.name}): {len(lines):,} ways, {frac.mean():.1%} of the map", flush=True)
    return frac


def roof_index(geoms, n):
    """[terrain] cover_roofs: each footprint's colour, 1..n, from a hash of its centre rounded to the metre (the same
    footprint the same colour in every band and every run)."""
    c = shapely.centroid(np.asarray(geoms, dtype=object))
    x = np.floor(shapely.get_x(c)).astype(np.int64)
    y = np.floor(shapely.get_y(c)).astype(np.int64)
    h = (x * 73856093) ^ (y * 19349663)
    return (np.abs(h) % n + 1).astype(np.uint8)


def paint_roofs(out, fracs, rgb):
    """out (3, nz, nx) with each roof colour laid over it by its share (fracs: n, nz, nx)."""
    total = fracs.sum(0)
    out = out * (1 - total)
    for f, c in zip(fracs, rgb):
        for b in range(3):
            out[b] += float(c[b]) * f
    return out


def under_masses(geoms) -> np.ndarray:
    """[terrain] cover_roofs.under_masses (opt-in, Tokyo M7 fix round): which footprints (UTM) stand as masses
    (masses_within's main clip, masses_ring) and are left unpainted in the inner map, the built land's gaps colour under
    them: their pale painted roofs showed round the merged, simplified masses as mismatched blobs (Ariake, M7 critic)."""
    g = gpd.GeoSeries(list(geoms), crs=UTM)
    under = within(g, clip("main"))
    if RING:
        under |= within(g, clip("ring"))
    return under


def building_cover(dst_tr, nz, nx, n_roofs=0):
    """The share of each inner map pixel under a town footprint ([terrain] cover_buildings), at a quarter pixel; with
    n_roofs ([terrain] cover_roofs) the share under each roof colour (n_roofs, nz, nx)."""
    import rasterio
    from rasterio import features
    x0, y1 = dst_tr * (0, 0)
    x1, y0 = dst_tr * (nx, nz)
    import pyogrio
    from rasterio.warp import transform_bounds
    src = CACHE
    if COVER_ALL:
        src = COVER_CACHE
        if not src.exists():
            ll = transform_bounds(UTM, "EPSG:4326", min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            print(f"  cover buildings: fetching every OSM footprint over the inner map", flush=True)
            fetch(tuple(ll)).to_file(src, engine="pyogrio")
    crs = pyogrio.read_info(src)["crs"]
    k = 4
    fine = rasterio.Affine(dst_tr.a / k, 0, dst_tr.c, 0, dst_tr.e / k, dst_tr.f)
    r = np.zeros((nz * k, nx * k), np.uint8)
    # read and burnt in bands of rows (Tokyo's "all": 0.9 M footprints at once held ~3 GB), the default in one band
    bands = 8 if COVER_ALL else 1
    edges = np.linspace(0, nz * k, bands + 1).astype(int)
    n = 0
    for r0, r1 in zip(edges[:-1], edges[1:]):
        bx0, by1 = fine * (0, r0)
        bx1, by0 = fine * (nx * k, r1)
        bb = transform_bounds(UTM, crs, min(bx0, bx1), min(by0, by1), max(bx0, bx1), max(by0, by1)) if crs else None
        b = gpd.read_file(src, engine="pyogrio", columns=[], bbox=bb).to_crs(UTM)
        if clip() is not None and not COVER_ALL:     # masses_within: the town colour only where the masses stand
            b = b[within(b.geometry, clip())]
        band = rasterio.Affine(fine.a, 0, fine.c, 0, fine.e, fine.f + fine.e * r0)
        geoms = [g for g in b.geometry.values if g is not None and not g.is_empty]
        if geoms:
            vals = roof_index(geoms, n_roofs) if n_roofs else np.ones(len(geoms), np.uint8)
            if n_roofs and COVER_ROOFS.get("under_masses") and clip() is not None:
                vals = np.where(under_masses(geoms), 0, vals).astype(np.uint8)
            r[r0:r1] = np.maximum(r[r0:r1], features.rasterize(zip(geoms, vals.tolist()), out_shape=(r1 - r0, nx * k),
                                                                transform=band, dtype=np.uint8))
        n += len(b)
        del b, geoms
    if n_roofs:
        frac = np.stack([(r == i + 1).reshape(nz, k, nx, k).mean(axis=(1, 3)).astype(np.float32) for i in range(n_roofs)])
        print(f"  cover buildings: {n:,} footprints as {n_roofs} roof colours, {frac.sum(0).mean():.1%} of the inner map",
              flush=True)
        return frac
    frac = r.reshape(nz, k, nx, k).mean(axis=(1, 3)).astype(np.float32)
    import gc
    gc.collect()
    print(f"  cover buildings: {n:,} footprints (with those of neighbouring bands twice), {frac.mean():.1%} of the inner "
          f"map", flush=True)
    return frac


def cover(terrain: Terrain):
    """tiles_raw/cover.jpg over the backdrop and cover_inner.jpg over the masses' zone; the entry for tiles.json."""
    xyz = terrain.backdrop["back_xyz"]
    x0, z0 = np.floor(xyz[:, [0, 2]].min(0) / COVER_CELL) * COVER_CELL
    x1, z1 = np.ceil(xyz[:, [0, 2]].max(0) / COVER_CELL) * COVER_CELL
    for old in RAW_TILES.glob("cover*.*"):
        old.unlink()
    entry = _cover_map(terrain, (x0, z0, x1, z1), COVER_CELL, 0.0003, 0.0002, "cover.jpg")
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    ax0, ay0, ax1, ay1 = area.envelope.buffer(INNER_REACH + 1000, join_style="mitre").bounds
    ox, oy = terrain.origin
    r = [np.floor((ax0 - ox) / COVER_INNER) * COVER_INNER, np.floor(-(ay1 - oy) / COVER_INNER) * COVER_INNER,
         np.ceil((ax1 - ox) / COVER_INNER) * COVER_INNER, np.ceil(-(ay0 - oy) / COVER_INNER) * COVER_INNER]
    # (WorldCover read finer for a finer map: about half a pixel)
    dll = (0.00013, 0.00009) if COVER_INNER == 20.0 else (0.00013 * COVER_INNER / 20.0, 0.00009 * COVER_INNER / 20.0)
    entry["inner"] = _cover_map(terrain, r, COVER_INNER, *dll, "cover_inner.jpg")
    if COVER_LINES:
        entry["inner"]["lines"] = lines_map(terrain, r)
    return entry


def lines_map(terrain: Terrain, rect):
    """tiles_raw/cover_lines.png over rect (scene x0, z0, x1, z1): roads, rail beds and the tracks' direction
    ([terrain] cover_lines); its entry (file, cell)."""
    import rasterio
    from PIL import Image
    from pyproj import Transformer
    from rasterio import features
    cell = float(COVER_LINES.get("cell", 10.0))
    ox, oy = terrain.origin
    x0, z0, x1, z1 = rect
    nx, nz = int(round((x1 - x0) / cell)), int(round((z1 - z0) / cell))
    dst_tr = rasterio.Affine(cell, 0, ox + x0, 0, -cell, oy - z0)
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform([ox + x0, ox + x1, ox + x0, ox + x1], [oy - z0, oy - z0, oy - z1, oy - z1])
    w, e, s, n = min(lon) - 0.01, max(lon) + 0.01, min(lat) - 0.01, max(lat) + 0.01
    road = road_cover(dst_tr, nz, nx, cell, (w, s, e, n)) if COVER_ROADS else np.zeros((nz, nx), np.float32)
    if RAILS_CACHE.exists():
        res = json.loads(RAILS_CACHE.read_text())
    else:
        res = overpass(f'[out:json][timeout:900];(way["railway"~"^(rail|light_rail|subway|narrow_gauge)$"]({s},{w},{n},{e});'
                       f'way["landuse"="railway"]({s},{w},{n},{e});relation["landuse"="railway"]({s},{w},{n},{e}););out geom;')
        RAILS_CACHE.write_text(json.dumps(res))
    tracks, yards = [], []
    for el in res["elements"]:
        t = el.get("tags", {})
        if t.get("landuse") == "railway":
            if el["type"] == "relation" and "members" not in el:
                continue
            g = next(iter(element_geoms({"elements": [el]})), (None, None))[1]
            if g is not None and g.geom_type in ("Polygon", "MultiPolygon"):
                yards.append(g)
            continue
        g = el.get("geometry")
        layer = t.get("layer", "0")
        if (not g or t.get("tunnel") not in (None, "no") or t.get("covered") == "yes"
                or (layer.lstrip("-").isdigit() and int(layer) < 0)):
            continue
        tracks.append(shapely.LineString([(p["lon"], p["lat"]) for p in g]))
    tr = gpd.GeoSeries(tracks, crs="EPSG:4326").to_crs(UTM)
    k = 4
    fine = rasterio.Affine(cell / k, 0, dst_tr.c, 0, -cell / k, dst_tr.f)
    beds = tr.buffer(float(COVER_LINES.get("rail", 4.0)) / 2, cap_style="flat")
    r = features.rasterize(((p, 1) for p in beds.values if not p.is_empty), out_shape=(nz * k, nx * k),
                           transform=fine, dtype=np.uint8)
    rail = r.reshape(nz, k, nx, k).mean(axis=(1, 3)).astype(np.float32)
    del r
    if yards:
        yg = gpd.GeoSeries(yards, crs="EPSG:4326").to_crs(UTM)
        r = features.rasterize(((p, 1) for p in yg.values if not p.is_empty), out_shape=(nz * 2, nx * 2),
                               transform=rasterio.Affine(cell / 2, 0, dst_tr.c, 0, -cell / 2, dst_tr.f), dtype=np.uint8)
        rail = np.maximum(rail, r.reshape(nz, 2, nx, 2).mean(axis=(1, 3)) * float(COVER_LINES.get("yard", 0.6)))
        del r
    # the tracks' direction: each segment's angle in scene x/z (z = south) over 0..pi, burnt along it, then carried
    # to the pixels round it (the nearest burnt one's) as far as 3 pixels
    shapes = []
    for line in tr.values:
        c = np.asarray(line.coords)
        for (ax, ay), (bx, by) in zip(c[:-1], c[1:]):
            if ax == bx and ay == by:
                continue
            a = np.arctan2(-(by - ay), bx - ax) % np.pi
            shapes.append((shapely.LineString([(ax, ay), (bx, by)]), int(1 + round(a / np.pi * 253))))
    code = features.rasterize(shapes, out_shape=(nz, nx), transform=dst_tr, dtype=np.uint8, all_touched=True) \
        if shapes else np.zeros((nz, nx), np.uint8)
    dist, (ii, jj) = ndi.distance_transform_edt(code == 0, return_indices=True)
    code = np.where(dist <= 3, code[ii, jj], 0).astype(np.uint8)
    img = np.stack([np.round(road * 255), np.round(np.clip(rail, 0, 1) * 255), code], axis=-1).astype(np.uint8)
    Image.fromarray(img).save(RAW_TILES / "cover_lines.png", optimize=True)
    print(f"cover_lines.png {nx} x {nz} at {cell:.0f} m ({(RAW_TILES / 'cover_lines.png').stat().st_size / 1e6:.1f} MB): "
          f"{len(tracks):,} track ways, {len(yards):,} rail yards; roads {road.mean():.1%}, rail {rail.mean():.1%}",
          flush=True)
    return {"file": "cover_lines.png", "cell": cell}


def run(argv):
    clip()                                       # masses_within: a missing or empty file stops here, before any fetch
    if RING:
        clip("ring")                             # (masses_ring's file too)
    if "--lines-only" in argv:
        # only the line map ([terrain] cover_lines) over the inner cover map's rectangle (no WorldCover read)
        cj = RAW_TILES / "cover.json"
        entry = json.loads(cj.read_text())
        i = entry["inner"]
        i["lines"] = lines_map(Terrain(), (i["x0"], i["z0"], i["x1"], i["z1"]))
        cj.write_text(json.dumps(entry))
        add_to_index(RAW_TILES / "tiles.json")
        return
    if "--cover-only" in argv:
        (RAW_TILES / "cover.json").write_text(json.dumps(cover(Terrain())))
        add_to_index(RAW_TILES / "tiles.json")
        return
    main()


def fetch_tall(reach):
    """masses_tall_within.tagged: the tall clip's tagged buildings within the reach (cached with a stamp of its own)."""
    tcut = clip("tall")
    region = reach.intersection(shapely.box(*tcut.bounds))
    stamp = clip_stamp(tcut, region) + f" {float(TALL_WITHIN.get('min_h', 30.0)):g}"
    if TALL_CACHE.exists() and (TALL_STAMP.read_text() if TALL_STAMP.exists() else "") != stamp:
        print(f"{TALL_CACHE.name} was fetched for another clip: fetched again", flush=True)
        TALL_CACHE.unlink()
    if not TALL_CACHE.exists():
        ll = gpd.GeoSeries([region], crs=UTM).to_crs(4326).total_bounds
        only = gpd.GeoSeries([tcut], crs=UTM).to_crs(4326).iloc[0]
        print(f"fetching tagged OSM buildings of {TALL_WITHIN.get('min_h', 30.0)} m and more over {region.area / 1e6:.0f} km²",
              flush=True)
        fetch(tuple(ll), only, tall_filter(TALL_WITHIN.get("min_h", 30.0)), float(TALL_WITHIN.get("chunk", 0.2))).to_file(
            TALL_CACHE, engine="pyogrio")
        TALL_STAMP.write_text(stamp)
    t = gpd.read_file(TALL_CACHE, engine="pyogrio")
    print(f"{len(t):,} tall OSM buildings in the tall clip", flush=True)
    return t


def add_ring(b):
    """masses_ring: the ring's footprints from cover_buildings.gpkg (UTM) added to the table, flagged in column "ring"
    (those already in it, by OSM id, only flagged)."""
    if not COVER_CACHE.exists():
        raise FileNotFoundError(f"[ground] masses_ring needs {COVER_CACHE.name} ([terrain] cover_buildings = \"all\", "
                                f"written by an earlier 06e_masses run)")
    ring = clip("ring")
    r = gpd.read_file(COVER_CACHE, engine="pyogrio", bbox=tuple(ring.bounds))
    r = r[r.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    r = r[within(r.geometry, ring)]
    for field, values in MASSES_SKIP.items():
        if field in r:
            r = r[~r[field].isin(values)]
    b = b.copy()
    b["ring"] = b["osm"].isin(set(r["osm"]))
    r = r[~r["osm"].isin(set(b["osm"]))].copy()
    r["ring"] = True
    print(f"masses_ring {RING['file']}: {ring.area / 1e6:.1f} km², {len(r):,} footprints added from {COVER_CACHE.name} "
          f"({int(b['ring'].sum()):,} already fetched)", flush=True)
    out = pd.concat([b, r.to_crs(b.crs)], ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=b.crs)


def ring_edge(b, E):
    """masses_ring.edge = { file, width, h, thin } (opt-in, Tokyo M8): the ring's masses lower and sparser over its last
    `width` m (default 700) to the outer edge (the boundary of `file`, WGS84: the ring's whole extent, the districts
    included): heights times h (0.55) at the edge and a `thin` share (0.5) of the footprints left out there, both eased
    in towards the inner side, so the town fades into the painted plain instead of ending on a line (M7 critic 2, west
    of the TMG). Only the ring's own footprints; tagged ones keep their heights and stand."""
    outer = gpd.GeoSeries([read_clip(E["file"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
    width, hk, thin = float(E.get("width", 700.0)), float(E.get("h", 0.55)), float(E.get("thin", 0.5))
    ring = b["ring"].fillna(False).to_numpy(bool)
    c = b.geometry.representative_point()
    d = shapely.distance(outer.boundary, shapely.points(c.x.to_numpy(), c.y.to_numpy()))
    t = np.clip(d / width, 0.0, 1.0)
    t = t * t * (3 - 2 * t)                                  # smoothstep: 0 at the edge, 1 a width inside
    tagged = np.isfinite(b["height"].map(height_m).to_numpy(float))
    seed = (b["osm"].str[1:].astype(np.int64).to_numpy() * 2246822519 % 1009) / 1009
    drop = ring & ~tagged & (seed < thin * (1 - t))
    h = b["h"].to_numpy(float)
    b = b.copy()
    b["h"] = np.where(ring & ~tagged, np.maximum(h * (hk + (1 - hk) * t), 3.0), h)
    print(f"masses_ring edge: {int((ring & (t < 1)).sum()):,} footprints within {width:g} m of the edge, "
          f"{int(drop.sum()):,} left out", flush=True)
    return b[~drop].reset_index(drop=True)


def hold_tall(b, opts):
    """[ground] masses_tall: footprints of opts['area'] m² or more over opts['h'] m held at h. Returns the table, how
    many and their highest height before."""
    tall = (b.area >= float(opts["area"])) & (b["h"] > float(opts["h"]))
    hmax = float(b.loc[tall, "h"].max()) if tall.any() else 0.0
    b = b.copy()
    b.loc[tall, "h"] = float(opts["h"])
    return b, int(tall.sum()), hmax


def main():
    t0 = time.time()
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    reach = area.envelope.buffer(REACH, join_style="mitre") if REACH > 0 else area.envelope
    cut = clip()                                  # masses_within in UTM; None: off (the default)
    if TALL_TAGGED and cut is not None:
        cut = clip("main")                        # (the tall clip is fetched on its own below)
    region, stamp = reach, ""
    if cut is not None:
        # fetched over the clip's box within the reach (and only the chunks that touch the clip), not the whole margin
        region = reach.intersection(shapely.box(*cut.bounds))
        if region.is_empty or not reach.intersects(cut):
            raise ValueError(f"[ground] masses_within = {MASSES_WITHIN!r} lies outside the masses' reach (the ground "
                             f"area plus masses_reach = {REACH:g} m): no masses would be left")
        stamp = clip_stamp(cut, region)
        print(f"masses_within {MASSES_WITHIN}: {cut.area / 1e6:.1f} km², {reach.intersection(cut).area / cut.area:.0%} "
              f"of it within the reach", flush=True)
    if CACHE.exists() and (CLIP_STAMP.read_text() if CLIP_STAMP.exists() else "") != stamp:
        print(f"{CACHE.name} was fetched for another masses_within: fetched again", flush=True)
        CACHE.unlink()
    elif CACHE.exists() and cut is None:
        # a cache fetched for a shorter reach (London M7: 3 km, then 5) is fetched again
        import pyogrio
        info = pyogrio.read_info(CACHE)
        cx0, cy0, cx1, cy1 = gpd.GeoSeries.from_xy(*np.array(info["total_bounds"]).reshape(2, 2).T,
                                                   crs=info["crs"]).to_crs(UTM).total_bounds
        rx0, ry0, rx1, ry1 = reach.bounds
        if cx0 > rx0 + 300 or cy0 > ry0 + 300 or cx1 < rx1 - 300 or cy1 < ry1 - 300:
            print(f"{CACHE.name} covers less than the reach: fetched again", flush=True)
            CACHE.unlink()
    if not CACHE.exists():
        ll = gpd.GeoSeries([region], crs=UTM).to_crs(4326).total_bounds
        print(f"fetching OSM buildings over {region.area / 1e6:.0f} km²", flush=True)
        only = gpd.GeoSeries([cut], crs=UTM).to_crs(4326).iloc[0] if cut is not None else None
        fetch(tuple(ll), only).to_file(CACHE, engine="pyogrio")
        if cut is not None:
            CLIP_STAMP.write_text(stamp)
        else:
            CLIP_STAMP.unlink(missing_ok=True)
    b = gpd.read_file(CACHE, engine="pyogrio")
    print(f"{len(b):,} OSM buildings ({time.time() - t0:.0f} s)", flush=True)
    tall = fetch_tall(reach) if TALL_TAGGED and cut is not None else None
    b = b[b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    for field, values in MASSES_SKIP.items():
        if field in b:
            skip = b[field].isin(values)
            print(f"masses_skip {field}: {int(skip.sum())} footprints left out", flush=True)
            b = b[~skip]
    b = b[b.intersects(reach)].reset_index(drop=True)
    if RING and cut is not None:
        b = add_ring(b)
    b["h"] = heights(b, reach, b["ring"].fillna(False).to_numpy(bool) if "ring" in b else None)
    if MASSES_TALL:
        b, n, hmax = hold_tall(b, MASSES_TALL)
        print(f"masses_tall: {n} footprints of {MASSES_TALL['area']:g} m² or more held at {MASSES_TALL['h']:g} m "
              f"(were up to {hmax:.0f} m)", flush=True)
    if tall is not None:
        # (their own heights: every one is tagged; the main clip's built-cover estimate is not needed out there; after
        # masses_tall, which held towers on big outlines at its podium height, under min_h, and the clip dropped them)
        tall = tall[tall.geometry.geom_type.isin(["Polygon", "MultiPolygon"]) & tall.intersects(reach)
                    & ~tall["osm"].isin(b["osm"])].reset_index(drop=True)
        h = tall["height"].map(height_m).to_numpy(float)
        tall["h"] = np.clip(np.where(np.isfinite(h), h, tall["levels"].map(height_m).to_numpy(float) * LEVEL_H + 1.0),
                            3.0, 300.0)
        b = pd.concat([b, tall], ignore_index=True)
        b = gpd.GeoDataFrame(b, geometry="geometry", crs=UTM)
    if cut is not None:
        # masses_within: whole buildings in or out (heights above still see the neighbours, as they always did)
        n0 = len(b)
        b = b[keep_clipped(b)].reset_index(drop=True)
        print(f"masses_within: {len(b):,} of {n0:,} footprints inside the clip", flush=True)
    if RING.get("edge") and "ring" in b:
        b = ring_edge(b, RING["edge"])
    if MIN_H > 0:
        n0 = len(b)
        b = b[b["h"].to_numpy() >= MIN_H].reset_index(drop=True)
        print(f"masses_min_h {MIN_H:g} m: {len(b):,} of {n0:,} footprints", flush=True)
    # not in the districts (modelled there), nor over a modelled building at their edge
    district = boundary().geometry.iloc[0]
    c = b.geometry.representative_point()
    b = b[~c.within(district)].reset_index(drop=True)
    near = b.intersects(district.buffer(150))
    if near.any():
        mod = gpd.read_file(DATA / "buildings.gpkg", engine="pyogrio", columns=[]).to_crs(UTM)
        mod = mod[mod.intersects(district.buffer(-200).boundary.buffer(400))]
        hit = gpd.sjoin(b[near], mod, predicate="intersects").index.unique()
        b = b.drop(hit).reset_index(drop=True)
    # beyond the ground area: thinned towards the reach, the big ones kept longest
    ax0, ay0, ax1, ay1 = area.envelope.bounds
    c = b.geometry.representative_point()
    out = np.hypot(np.maximum(np.maximum(ax0 - c.x, c.x - ax1), 0), np.maximum(np.maximum(ay0 - c.y, c.y - ay1), 0))
    rng = np.random.default_rng(7)
    if REACH > 0 and not THIN:
        if not HOUSES_FAR:
            b = b[~((out > 0) & (b["h"].to_numpy() < 9))].reset_index(drop=True)
    elif REACH > 0:
        keep = 1 - np.clip(out / REACH, 0, 1) ** 0.7
        keep = np.clip(keep * np.where(b.area > 400, 1.6, 1.0) * np.where(b["h"] > 30, 3.0, 1.0), 0, 1)
        if not HOUSES_FAR:
            keep = np.where((out > 0) & (b["h"].to_numpy() < 9), 0.0, keep)  # houses out there: the cover map's town
        b = b[rng.random(len(b)) < keep].reset_index(drop=True)
    b = b[b.area >= 30].reset_index(drop=True)
    print(f"{len(b):,} buildings beyond the districts; heights median {b.h.median():.1f} m, "
          f"{(b.h > 30).sum():,} over 30 m, max {b.h.max():.0f} m", flush=True)

    terrain = Terrain()
    origin = terrain.origin
    if CFG["terrain"].get("backdrop_cover"):
        (RAW_TILES / "cover.json").write_text(json.dumps(cover(terrain)))
    rect = (ax0 - origin[0], -(ay1 - origin[1]), ax1 - origin[0], -(ay0 - origin[1]))
    ground = Ground(terrain, rect)
    rp = b.geometry.representative_point()
    b["ci"] = np.floor((rp.x - origin[0]) / CELL).astype(int)
    b["cj"] = np.floor((-(rp.y - origin[1])) / CELL).astype(int)
    b["CI"] = np.floor((rp.x - origin[0]) / SUPER).astype(int)
    b["CJ"] = np.floor((-(rp.y - origin[1])) / SUPER).astype(int)
    # height classes: houses (under 9 m) one class, merged over their garden gaps into rows and clusters;
    # 4 m steps to 40 m, then 10 m (towers keep their own)
    b["cls"] = np.where(b.h < 9, 0, np.where(b.h < 40, 1 + np.round(b.h / 4), 20 + np.round(b.h / 10))).astype(int)
    for f in RAW_TILES.glob("m_*.glb"):
        f.unlink()
    global _JOB
    _JOB = (b, ground, origin, (ax0, ay0, ax1, ay1))
    import multiprocessing as mp
    keys = ([("h", int(i), int(j)) for i, j in sorted(b[b.cls == 0].groupby(["ci", "cj"]).groups)]
            + [("L", int(i), int(j)) for i, j in sorted(b[b.cls > 0].groupby(["CI", "CJ"]).groups)])
    keys.sort(key=lambda k: k[0] != "L")         # the big cells first (the longest jobs)
    with mp.get_context("fork").Pool(4) as pool:
        results = pool.map(_cell, keys, chunksize=1)
    entries = [r for r in results if r]
    tris = sum(e["triangles"] for e in entries)
    INDEX.write_text(json.dumps(entries, indent=1))
    add_to_index(RAW_TILES / "tiles.json")
    size = sum((RAW_TILES / e["file"]).stat().st_size for e in entries) / 1e6
    print(f"{len(entries)} mass cells, {tris:,} triangles, {size:.1f} MB raw ({time.time() - t0:.0f} s)")


_JOB = None
MERGE = {0: (6.0, 4.0, 2000.0)}           # class -> (gap closed, simplify, smallest courtyard kept) m, m, m²
MERGE_DEFAULT = (3.0, 3.0, 400.0)


def _cell(key):
    """One cell's masses into tiles_raw: the blocks of a 12 km cell (kind "L", mesh "masses") or the houses of a
    4 km cell (kind "h", mesh "masses_small"); its tile entry."""
    from . import tiles as tiles_mod
    tiles_mod.POS_BITS = 16                      # (12 km cells: 18 cm steps rather than 73)
    b, ground, origin, (ax0, ay0, ax1, ay1) = _JOB
    kind, ci, cj = key
    if kind == "L":
        part, size, mesh_name = b[(b.CI == ci) & (b.CJ == cj) & (b.cls > 0)], SUPER, "masses"
    else:
        part, size, mesh_name = b[(b.ci == ci) & (b.cj == cj) & (b.cls == 0)], CELL, "masses_small"
    rng = np.random.default_rng(abs(hash((kind, int(ci), int(cj)))) % 2 ** 32)
    polys, hs = [], []
    for cls, grp in part.groupby("cls"):
        gap, simp, hole = MERGE.get(cls, MERGE_DEFAULT)
        h = float(grp.h.median())
        merged = unary_union(grp.geometry.buffer(gap / 2, join_style="mitre").values).buffer(-gap / 2, join_style="mitre")
        for p in polygons(merged.simplify(simp)):
            if p.area < (60 if cls == 0 else 40):
                continue
            c = p.centroid
            out = np.hypot(max(ax0 - c.x, c.x - ax1, 0), max(ay0 - c.y, c.y - ay1, 0))
            if out > 0 and p.area < FAR_MIN:     # beyond the ground area: sub-pixel from anywhere they show
                continue
            if p.area < (600 if cls == 0 else 400):       # a house or a small block: its oriented rectangle
                p = p.minimum_rotated_rectangle
            else:
                if out > 0:
                    p = p.simplify(4.0)
                    if p.is_empty or p.geom_type != "Polygon":
                        continue
                p = shapely.Polygon(p.exterior, [r for r in p.interiors if shapely.Polygon(r).area > hole])
            polys.append(shapely.geometry.polygon.orient(p))
            # the last FADE m of the reach: lower and lower, so the town sinks into the backdrop's
            hs.append(h * (float(np.clip((REACH - out) / FADE, 0.3, 1.0)) if REACH > 0 and THIN else 1.0))
    m = extrude_all(polys, hs, ground, origin, rng)
    if m is None:
        return None
    name = f"m_{kind}{ci}_{cj}.glb"
    write_glb(RAW_TILES / name, {mesh_name: m})
    n = len(m["idx"]) // 3
    print(f"  {name}: {len(polys):,} masses, {n:,} triangles", flush=True)
    return {"file": name, "x": int(ci * size), "z": int(cj * size), "size": size, "buildings": 0,
            "masses": len(polys), "triangles": n, "smallTriangles": n if kind == "h" else 0,
            "maxHeight": float(m["pos"][:, 1].max())}


def add_to_index(path):
    """Put masses.json's entries and the cover map into a tiles.json (06_tiles writes it without them)."""
    if not path.exists():
        return
    index = json.loads(path.read_text())
    if INDEX.exists():
        entries = json.loads(INDEX.read_text())
        index["tiles"] = [t for t in index["tiles"] if not t["file"].startswith("m_")] + entries
    if "town" in index:
        index["town"]["rgb"] = CFG["terrain"]["backdrop_town_rgb"]
    cj = RAW_TILES / "cover.json"
    if CFG["terrain"].get("backdrop_cover") and cj.exists():
        index["cover"] = json.loads(cj.read_text())
    path.write_text(json.dumps(index, indent=1))
