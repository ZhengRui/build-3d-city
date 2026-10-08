"""06_tiles: turn the building table and ground layers into glb tiles for the three.js viewer.

Scene frame: metres, origin at the centre of the districts' bounding box (UTM, city.toml utm_epsg),
x = east, y = up, z = south (three.js convention, so north is -z). The ground is 05a_terrain.py's TIN
(common.Terrain): 0 on the coastal plain, the hills rising from it.

Buildings are extruded flat-roofed boxes (or, where the preset's roof_shapes() says so, walls to the eaves under a
mansard's brisis or a pitched roof leaning in from the walls not shared with a neighbour: ROOF), grouped into TILE-metre square tiles (t_<ix>_<iy>.glb) by centroid,
with a plant room on the roof of taller ones. Each stands on the lowest ground under its outline (its base),
its walls reaching SKIRT further down so no gap opens under them on a slope (uphill the ground covers them).
Every building vertex carries:
  POSITION, NORMAL
  COLOR_0     wall colour (for glass facades the glass tint), from the facade style's palette
  TEXCOORD_0  walls: (distance from the start of the wall run, run length) in metres, where a run is
              the wall between two corners; roofs: (0, 0)
  TEXCOORD_1  (style id + seed, height): the facade style's index in STYLES plus a per-building seed
              in 0..1 that varies the details, and the building's height in metres (above its base)
  TEXCOORD_2  (base, roof code): the height of the ground it stands on, metres; the roof's rise (m) plus
              ROOF_MAT_STEP x its material (1 zinc or slate, 2 tile, 3 flat mineral, 0 unknown)
The shader takes heights from the vertex position less the base, tells roofs by their normal and works out the floor
height from the building height and the style's nominal floor (see STYLES). The
facade style comes from the OSM building tag, the building kind and height, and OSM land use
(05c_landuse.py), by the region preset's rules (facade_styles() in presets/<preset>/, styles and palettes in
its [facade] table; the style order is the viewer's, web/facade.js).

Roads (roads.gpkg from 05b_roads.py), in the same tiles as two more meshes, both with COLOR_0 by kind:
  road    ground-level roads and railways, buffered to their width, merged per tile and laid ROAD_Y
          above the ground (cut along the TIN's triangles where it is not level, so they follow it
          exactly); major roads drawn over minor ones, roads over railways
  bridge  elevated ways as decks DECK_T thick following their deck height, with a pillar every
          PILLAR_STEP from the ground up where the deck is high enough above it to need one

Ground, in ground.glb: land, mudflat, green, water and aeroway polygons, one mesh each (overlaps merged),
draped over the TIN like the roads (level ground costs no extra triangles) and welded, positions 16 bit per
axis on one lattice over the ground area, normals the TIN's smooth vertex normals. Plus the backdrop: 05a_terrain.py's coarse TIN of the
land beyond the ground area (float positions, vertex colours), whose inner edge is put on that lattice so
the two meet exactly. terrain.glb holds the ground TIN itself (grid indices and TERRAIN_Q steps, exact),
from which the viewer reads the ground's height (web/terrain.js).

Writes tiles_raw/ in the data folder with tiles.json, t_<ix>_<iy>.glb, ground.glb and terrain.glb;
07_pack.py compresses them into tiles/, which the viewer loads. `06_tiles --views-only` refreshes only the
camera presets ([views] areas and landmarks) in tiles.json.
"""
import json
import struct

import geopandas as gpd
import mapbox_earcut as earcut
import meshoptimizer
import numpy as np
import pandas as pd
from shapely import affinity, make_valid
import shapely
import shapely.prepared
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .. import presets
from ..common import CFG, CHECKS, CITY, DATA, UTM, UTM_EPSG, Terrain, _flat_pieces, boundary, generator

T = CFG["tiles"]
TILE = T["size"]
# camera presets for the viewer's menu. Areas: name -> (lon, lat) of the point looked at, distance (m),
# elevation angle (deg). Landmarks: menu name -> building name in buildings.gpkg; the camera looks at a
# third of its height from a distance that fits the whole building in view.
AREAS = {k: tuple(v) for k, v in CFG["views"]["areas"].items()}
LANDMARKS = CFG["views"]["landmarks"]
# the menu's groups: areas under "Areas", landmarks under "Landmarks", unless [views.groups] {group: [view names]}
# puts them elsewhere; the groups in the menu in this order: Areas, those of [views.groups], Landmarks
GROUPS = CFG["views"].get("groups", {})
OUT = DATA / "tiles_raw"
SIMPLIFY = 0.5
CORNER_DEG = 30
# building texture coordinates are stored as 0..1 of these ranges (metres unless noted); tiles.json
# passes them to the viewer. Wall runs longer than 4 km or buildings over 1 km would be clipped.
# (fac: the style id + seed must stay below its first value: 16 clipped a 17th and 18th style to the 16th,
# seed 0; 64 leaves room and still resolves the seed to 1/1000)
# base: (the ground under the building, its roof code: the roof's rise in metres + ROOF_MAT_STEP x its material)
UV_RANGE = {"uv": (4096, 4096), "fac": (64, 1024), "base": (1024, 32)}
POS_BITS = 14                 # position quantization: about 6 cm over a 1 km tile
SKIRT = 1.0                   # walls reach this far below a building's base (m)
TERRAIN_Q = 0.02              # terrain.glb's height step (m)
GROUND_SIMPLIFY = 0.5         # ground layer outlines (m)
# roofs (the preset's roof_shapes(): APUR's mansards and pitched roofs): the top storey as a steep brisis, the
# top of it flat (the terrasson, hardly sloped, reads flat); a pitched roof leaning in from the free walls. Rise
# (m) from the building's height, clamped; run (m) = rise / tan(pitch). Walls shared with a neighbour that reaches
# the eaves (party walls) stay vertical, so a row of buildings reads as one roof along the street. The rise goes
# to the shader in TEXCOORD_2.y with the material (1 zinc or slate, 2 tile, 3 flat mineral; 0 unknown) times
# ROOF_MAT_STEP, so the walls' floors, cornice and windows stop under the roof and the brisis gets dormers
# "berliner": Berlin's Altbau roof (de-berlin; region_research.md §4.2): a 60-degree front slope over the eaves to a
# flat top, built like a mansard (dormers in it), from the free walls only. [tiles] roof_eave (off by default): the
# rise is the source's own, h - eave_h (the LoD2's eaves), where it has one between ROOF_EAVE m and 0.45 h
ROOF = {"mansard": {"rise": (0.16, 2.4, 4.2), "pitch": 70.0},
        "pitched": {"rise": (0.22, 1.5, 3.5), "pitch": 38.0},
        "berliner": {"rise": (0.14, 2.4, 3.6), "pitch": 60.0}}
ROOF_EAVE = (1.0, 6.0)
ROOF_MAT_STEP = 8.0
PARTY_GAP = 0.35              # m: a wall this close to another building's outline is a party wall


def srgb(hexes: str) -> list:
    """'#rrggbb ...' -> linear RGB tuples (glTF vertex colours are linear)."""
    out = []
    for h in hexes.split():
        c = np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)]) / 255
        out.append(tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)))
    return out


# facade styles (the preset's [facade.styles]): the id is what the viewer's facade shader switches on
# (web/facade.js, same order). floor: nominal floor-to-floor height (m); the shader fits it per building so
# the height is a whole number of floors: height / max(1, round(height / floor)).
# palette: wall colour (for glass: the glass tint), one picked per building. Shenzhen's (china-south) are
# glass, residential, village, factory, commercial, civic, plain (rooftop plant rooms: no windows), and the
# landmark styles set from data/landmark_facades.csv with the tint sampled from photos: fins (glass between
# stainless fins), bands (horizontal spandrel bands), lattice (diamond steel lattice), honeycomb, panel
STYLES = {k: {"floor": v["floor"], "palette": srgb(" ".join(v["palette"]))} for k, v in CFG["facade"]["styles"].items()}
assert len(STYLES) < UV_RANGE["fac"][0], f"{len(STYLES)} facade styles: raise UV_RANGE fac above that"
LANDMARK_FACADES = CITY / CFG["paths"]["landmark_facades"]
TOWN = CFG["ground"]["town"]         # the land beyond the districts as its own "town" layer
MODULE_MAX = 12.0             # COLOR_0 alpha = module / MODULE_MAX
STYLE_ID = {k: i for i, k in enumerate(STYLES)}
OSM_STYLE = {tag: style for style, tags in CFG["facade"]["osm_style"].items() for tag in tags}
# rooftop plant room (lift machinery, tanks) on buildings at least this tall with room for one
PLANT_MIN_H, PLANT_MIN_AREA, PLANT_H = T["plant_min_h"], T["plant_min_area"], T["plant_h"]
SMALL_EXACT = bool(T.get("small_exact", False))     # h_exact pieces (a rule's "exact"/"roof") skip the 4 m² cull
C = T["clearance"]                                                       # see road_clearance()
CLEAR_MAJOR, CLEAR_MINOR, CLEAR_DECK, CLEAR_ANY = C["major"], C["minor"], C["deck"], C["any"]


def facade_styles(b: gpd.GeoDataFrame) -> np.ndarray:
    """Facade style per building from its OSM tag, kind, height and the OSM land use around it (the region
    preset's facade_styles())."""
    lu = gpd.read_file(DATA / "landuse.gpkg", layer="landuse")[["use", "geometry"]]
    lu = lu.assign(area=lu.area).sort_values("area")                 # smallest (most specific) area wins
    pts = gpd.GeoDataFrame(geometry=b.geometry.representative_point(), crs=b.crs)
    hit = gpd.sjoin(pts, lu, predicate="within").sort_values("area")
    use = hit[~hit.index.duplicated()]["use"].reindex(b.index)
    return presets.module().facade_styles(b, use, OSM_STYLE)


def building_styles(b: gpd.GeoDataFrame) -> None:
    """Facade style (facade_styles(), then [facade.zones]), per-building seed and landmark facades, in place: shared
    with 06c_rooftops, so every roof there is this stage's, in the same style with the same seed."""
    rng = np.random.default_rng(7)
    b["facade"] = facade_styles(b)
    # [facade.zones]: style = {polygon = [[lon, lat], ...]}: buildings touching it take that style (Times
    # Square's billboards), spires excepted; or name = {style = "...", polygon = ...}: buildings whose inside point
    # is in it (Paris's classical ensembles: several zones of one style, not the blocks behind them)
    zvar, ztint = [], []
    for zname, z in CFG["facade"].get("zones", {}).items():
        zstyle = z.get("style", zname)
        zone = gpd.GeoSeries([Polygon(z["polygon"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
        hit = b.geometry.representative_point().within(zone) if "style" in z else b.geometry.intersects(zone)
        inz = hit & (b["facade"] != "spire")
        b.loc[inz, "facade"] = zstyle
        if "variant" in z:                       # the style parameter for all of them (a monument's kind)
            zvar.append((inz, float(z["variant"])))
        if "tint" in z:                          # their wall colour (sRGB hex), unless a landmark row sets one
            ztint.append((inz, z["tint"]))
        print(f"zone {zname} ({zstyle}): {int(inz.sum())} buildings")
    b["seed"] = rng.random(len(b))
    # a preset's shopfronts() (London): buildings with a shopfront ground floor get a seed in [0, 0.5), the rest in
    # [0.5, 1), which the viewer reads with city.json facade.shopSeed (every other use of the seed hashes it, so
    # the halves keep their variety). Presets without it: the seeds as before
    mod = presets.module()
    if hasattr(mod, "shopfronts"):
        shop = np.asarray(mod.shopfronts(b), bool)
        b["seed"] = np.where(shop, 0.5 * b["seed"], 0.5 + 0.5 * b["seed"])
        print(f"shopfronts: {int(shop.sum()):,} buildings")
    for inz, v in zvar:
        b.loc[inz, "seed"] = v
    print(f"{landmark_facades(b)} buildings with a researched landmark facade")
    b["zone_tint"] = False                       # (a zone's tint keeps the roof shapes a landmark's tint drops)
    for inz, t in ztint:
        for i in b.index[inz.reindex(b.index, fill_value=False).values & b["tint"].isna().values]:
            b.at[i, "tint"] = srgb(t)[0]
            b.at[i, "zone_tint"] = True


def roof_shapes(b: gpd.GeoDataFrame):
    """(rise m, run m, TEXCOORD_2.y code) per building from the preset's roof_shapes() (none if it has none): the
    ROOF shapes on buildings without a massing of their own (OSM parts, landmark rows, profiles keep theirs)."""
    mod = presets.module()
    zero = np.zeros(len(b))
    if not hasattr(mod, "roof_shapes"):
        return zero, zero, zero
    r = mod.roof_shapes(b, b["facade"].values)
    own = b["profile"].notna() | (b["tint"].notna() & ~b.get("zone_tint", pd.Series(False, index=b.index)).astype(bool))
    if "part_of" in b:
        own |= b["part_of"].notna()
    rise, run = zero.copy(), zero.copy()
    eave = None
    if T.get("roof_eave", False) and "eave_h" in b:
        e = b.h.values - pd.to_numeric(b["eave_h"], errors="coerce").values
        eave = np.where((e >= ROOF_EAVE[0]) & (e <= ROOF_EAVE[1]), e, np.nan)
    for shape, p in ROOF.items():
        on = (r["shape"].values == shape) & ~own.values
        k, lo, hi = p["rise"]
        rise[on] = np.clip(k * b.h.values[on], lo, hi)
        if eave is not None:
            rise[on] = np.where(np.isnan(eave[on]), rise[on], eave[on])
        run[on] = rise[on] / np.tan(np.radians(p["pitch"])) if shape != "pitched" else 8.0
    # a pitched roof leans in until the inset_room limit (0.4 of the way across) meets its ridge
    rise = np.minimum(rise, 0.45 * b.h.values)
    code = np.where(rise > 0, rise, 0) + ROOF_MAT_STEP * r["material"].values
    print("roofs: " + ", ".join(f"{s} {int(((r['shape'].values == s) & ~own.values).sum()):,}" for s in ROOF)
          + f"; materials {dict(zip(*np.unique(r['material'].values, return_counts=True)))}")
    return rise, run, code


def party_walls(b: gpd.GeoDataFrame):
    """free(points, i, eaves): 0 for the walls of building i within PARTY_GAP of another building that reaches
    within 1 m of its eaves (a party wall), else 1."""
    geoms = b.geometry.values
    tree = shapely.STRtree(geoms)
    top = b.h.values                       # (h: the top above the ground, min_h: the bottom)
    pos = {k: i for i, k in enumerate(b.index)}

    def free(pts, i, eaves):
        i = pos[i]
        hit = tree.query(shapely.points(pts), predicate="dwithin", distance=PARTY_GAP)
        keep = (hit[1] != i) & (top[hit[1]] >= eaves - 1.0)
        w = np.ones(len(pts))
        w[hit[0][keep]] = 0.0
        return w
    return free


SPIRE_TINT = "#b8bcc0"        # crowns and spires: brushed metal unless the row's `roof` column or a crown's #hex says


def directives(text) -> tuple:
    """A landmark_facades.csv profile cell split into its massing profile (a plain profile, 'dome:', 'shell:',
    'anti:' or 'long:') and its directives on the landmark's parts ('crown@', 'tops@', 'lid@', 'h@'), which
    are separated by ';'."""
    prof, ds = None, []
    for d in (str(text).split(";") if isinstance(text, str) else []):
        d = d.strip()
        if d.startswith(("crown@", "tops@", "lid@", "h@", "wing@", "base@", "fill@", "slot@", "shape@", "roofs@")):
            ds.append(d)
        elif d:
            prof = d
    return prof, ds


def landmark_facades(b: gpd.GeoDataFrame) -> int:
    """Apply data/landmark_facades.csv (researched from photos, see data/landmark_facades.md) to the
    buildings with those names: facade style, photo-sampled tint, bay module ('bays:N' spreads N bays
    around the footprint), a style parameter in place of the random seed, a massing profile and the
    directives that reshape a landmark made of parts (see directives()). Optional columns: `whole` (true:
    its parts merged into one outline for the profile), `take` (metres: unnamed buildings and parts whose
    representative point lies that close to the landmark's outline, holes filled, or that lie 90 % inside its
    convex hull join it, with the other unnamed parts of their buildings (OSM parts of its towers mapped under
    another outline, and their stair turrets)), `roof` (the colour of its spires and crowns, #b8bcc0 when empty)."""
    b["tint"], b["module"], b["profile"] = None, 0.0, None
    if not LANDMARK_FACADES.exists():            # a new city before its landmark research
        return 0
    lf = pd.read_csv(LANDMARK_FACADES)
    hit, unknown = 0, set()
    if "part_of" not in b:
        b["part_of"] = np.nan
    for r in lf.itertuples():
        near = getattr(r, "near", np.nan)
        if isinstance(near, str) and near.strip():
            # 'lon lat m|lon lat m': unnamed buildings and parts whose representative point lies within m metres
            # of a point join the landmark (a bridge's towers OSM maps as nameless parts)
            from pyproj import Transformer
            to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
            cand = b.index[b.name.isna()]
            pts = b.loc[cand].geometry.representative_point()
            for q in near.split("|"):
                lon, lat, m = map(float, q.split())
                x, y = to.transform(lon, lat)
                b.loc[cand[(pts.distance(shapely.Point(x, y)) <= m).values], "name"] = r.name
        rows = b.index[b.name == r.name]
        take = getattr(r, "take", np.nan)
        if len(rows) and not pd.isna(take) and float(take) > 0:
            # the outline with its holes filled (a piece drawn in a ring of parts: the Opéra's flytower)
            near = shapely.union_all([Polygon(p.exterior) for g in b.loc[rows].geometry for p in polygons(g)])
            near = near.buffer(float(take))
            cand = b.index[b.name.isna()]
            pts = b.loc[cand].geometry.representative_point()
            # ...or lying 90 % inside its convex hull (a flytower between the stage walls OSM draws as a U)
            hull = b.loc[rows].geometry.union_all().convex_hull
            box_ = shapely.intersects(hull, b.loc[cand].geometry.values)
            inside = np.zeros(len(cand), bool)
            g = b.loc[cand[box_]].geometry
            inside[box_] = (g.intersection(hull).area / g.area.clip(lower=1e-9)).values >= 0.9
            joined = cand[shapely.contains(near, pts.values) | inside]
            # with the other unnamed parts of the buildings those belong to (the towers' stair turrets)
            hosts = set(b.loc[joined, "part_of"].dropna())
            joined = joined.union(cand[b.loc[cand, "part_of"].isin(hosts).values])
            b.loc[joined, "name"] = r.name
            rows = b.index[b.name == r.name]
        if len(rows) > 1 and str(getattr(r, "whole", "")).lower() == "true":
            # made of parts, but its massing is the profile's: one outline, to its main roof; its spire stays
            spire = b.loc[rows, "facade"] == "spire"
            body = rows[~spire.values]
            keep = body[0]
            b.at[keep, "geometry"] = b.loc[body].geometry.union_all().buffer(0.3, join_style=2).buffer(-0.3, join_style=2)
            b.at[keep, "h"] = float(b.loc[body, "h"].max())
            # ...from its lowest underside: the kept row may be a raised piece (the Gherkin's 70-180 m top
            # prism listed first kept min_h 70 and was dropped as FLOATING once the pieces under it were gone)
            if "min_h" in b:
                b.at[keep, "min_h"] = float(b.loc[body, "min_h"].astype(float).fillna(0.0).min())
            b.drop(index=body[1:], inplace=True)
            b.at[keep, "part_of"] = np.nan
            rows = b.index[b.name == r.name]
        if not len(rows):
            print(f"landmark facade: no building named {r.name}")
            continue
        hit += len(rows)
        roof = getattr(r, "roof", np.nan)
        roof = srgb(roof)[0] if isinstance(roof, str) and roof.startswith("#") else srgb(SPIRE_TINT)[0]
        # a style the preset doesn't have yet (landmark research ahead of the region's styles: Paris's
        # limestone, concretepanel before M4) keeps the building's own style, with the photo's tint
        if r.facade in STYLES:
            b.loc[rows[b.loc[rows, "facade"] != "spire"], "facade"] = r.facade
        elif r.facade not in unknown:
            unknown.add(r.facade)
            print(f"landmark facade: no style {r.facade} in [facade.styles] yet: the buildings keep theirs, with the tint")
        prof, ds = directives(r.profile)
        for i in rows:
            b.at[i, "tint"] = srgb(r.tint)[0]
            if b.at[i, "facade"] == "spire":
                b.at[i, "tint"] = roof
            # a profile shapes a single building; one made of OSM parts has its massing already
            if pd.isna(b.at[i, "part_of"]) and prof:
                b.at[i, "profile"] = parse_profile(prof)
                if prof.startswith("anti:"):      # an antiprism turns a square: square it up
                    b.at[i, "geometry"] = b.at[i, "geometry"].minimum_rotated_rectangle
            mod = str(r.module)
            if mod.startswith("bays:"):
                b.at[i, "module"] = b.geometry[i].exterior.length / float(mod[5:])
            elif mod not in ("", "nan"):
                b.at[i, "module"] = float(mod)
        if not pd.isna(r.variant):
            b.loc[rows, "seed"] = float(r.variant)
        # the directives in a fixed order: heights first, then the lid, the spires and the crowns cut from them
        order = ("wing@", "slot@", "h@", "base@", "fill@", "lid@", "shape@", "tops@", "crown@", "roofs@")
        for d in sorted(ds, key=lambda d: [d.startswith(o) for o in order].index(True)):
            rows = b.index[b.name == r.name]
            if d.startswith("wing@"):
                wing(b, rows, d)
            elif d.startswith("h@"):
                heights(b, rows, d)
            elif d.startswith("slot@"):
                slot(b, rows, d)
            elif d.startswith("base@"):
                bases(b, rows, d)
            elif d.startswith("fill@"):
                fill(b, rows, d)
            elif d.startswith("lid@"):
                lid(b, rows, d)
            elif d.startswith("shape@"):
                shape(b, rows, d)
            elif d.startswith("tops@"):
                tops(b, rows, d)
            elif d.startswith("roofs@"):
                roofs(b, rows, d, roof)
            else:
                crown(b, rows, d, roof)
    return hit


def wing(b: gpd.GeoDataFrame, rows, text: str):
    """'wing@<m>:<osm id>': a footprint that holds a tower and its lower wing as one outline (an official
    roof-plan footprint under the tower's landmark height) is cut to that OSM building's outline (w123 or
    r123, in osm_buildings.gpkg), and the rest becomes a wing <m> m high (Tours Duo's Duo 1)."""
    h, oid = text[len("wing@"):].split(":")
    import pyogrio
    o = pyogrio.read_dataframe(DATA / "osm_buildings.gpkg", where=f"osm_id = '{oid}'")
    if not len(o):
        print(f"landmark wing: no OSM building {oid}")
        return
    tower = o.to_crs(UTM).geometry.union_all()
    i = b.loc[rows].area.idxmax()
    g = b.at[i, "geometry"]
    rest = g.difference(tower.buffer(0.5)).buffer(-0.5).buffer(0.5)
    b.at[i, "geometry"] = g.intersection(tower)
    if rest.area > 20:
        k = b.index.max() + 1
        b.loc[k] = b.loc[i]
        b.at[k, "geometry"], b.at[k, "h"] = rest, float(h)
        b.at[k, "profile"] = None                  # (the tower's profile is the tower's)


def heights(b: gpd.GeoDataFrame, rows, text: str):
    """'h@<a>=<b>': the landmark's rows (parts) now <a> m high (to 0.6 m) become <b> m high, a lifted part
    that ends up no taller than its underside dropped: a corrected part height (the Arc de Triomphe's attic,
    a duplicate footprint over a monument's flytower, the piece that joins twin towers)."""
    a, to = map(float, text[len("h@"):].split("="))
    sel = rows[(b.loc[rows, "h"].astype(float) - a).abs().values <= 0.6]
    if not len(sel):
        print(f"landmark h@: {b.at[rows[0], 'name']} has no part {a:.1f} m high")
    b.loc[sel, "h"] = to
    gone = sel[(b.loc[sel, "min_h"].astype(float) >= to).values]
    b.drop(index=gone, inplace=True)


def slot(b: gpd.GeoDataFrame, rows, text: str):
    """'slot@<w>:<every>': twin towers on one footprint (The Link: two slender towers joined by sky bridges): the
    largest row split along its long axis by a <w> m slot, with a 4 m bridge across it every <every> m from 30 m."""
    w, every = map(float, text[len("slot@"):].split(":"))
    i = b.loc[rows].area.idxmax()
    g = b.at[i, "geometry"]
    r = g.minimum_rotated_rectangle
    p = np.array(r.exterior.coords)[:4]
    e = [p[1] - p[0], p[2] - p[1]]
    u = e[0] if np.linalg.norm(e[0]) >= np.linalg.norm(e[1]) else e[1]
    u = u / np.linalg.norm(u)
    c = np.array(g.centroid.coords[0])
    L = 2 * np.sqrt(g.area) + 50
    strip = shapely.LineString([c - u * L, c + u * L]).buffer(w / 2, cap_style=2)
    b.at[i, "geometry"] = g.difference(strip)
    top = float(b.at[i, "h"])
    link = g.intersection(strip)
    for y in np.arange(30.0, top - 10, every):
        k = b.index.max() + 1
        b.loc[k] = b.loc[i]
        b.at[k, "geometry"], b.at[k, "min_h"], b.at[k, "h"] = link, float(y), float(y) + 4.0
        b.at[k, "profile"] = None


def bases(b: gpd.GeoDataFrame, rows, text: str):
    """'base@<a>=<b>': the landmark's parts <a> m high (to 0.6 m) start <b> m up (a part OSM maps from the ground
    that belongs over a vault: the Arc de Triomphe's crossing pieces, 0-50 m in OSM, stood in its main arch)."""
    a, to = map(float, text[len("base@"):].split("="))
    sel = rows[(b.loc[rows, "h"].astype(float) - a).abs().values <= 0.6]
    if not len(sel):
        print(f"landmark base@: {b.at[rows[0], 'name']} has no part {a:.1f} m high")
    b.loc[sel, "min_h"] = to


def fill(b: gpd.GeoDataFrame, rows, text: str):
    """'fill@<m>': a solid top over the landmark's whole outline (its parts' union, holes and gaps under 1 m
    closed) from <m> m to its top: an attic over vaults and piers that OSM maps as separate pieces with gaps
    between them (the Arc de Triomphe: its attic drawn over each half, nothing over the main arch's crown,
    which read as an "H" with sky through it). Parts wholly above <m> go into it, those reaching above it
    are cut to <m>."""
    at = float(text[len("fill@"):])
    body = rows[(b.loc[rows, "facade"] != "spire").values]
    top = float(b.loc[body, "h"].max())
    outline = b.loc[body].geometry.union_all().buffer(1.0, join_style=2).buffer(-1.0, join_style=2)
    outline = shapely.union_all([Polygon(p.exterior) for p in polygons(outline)])
    k = body[0]
    new = b.index.max() + 1
    b.loc[new] = b.loc[k]
    b.at[new, "geometry"], b.at[new, "min_h"], b.at[new, "h"] = outline, at, top
    b.at[new, "part_of"] = np.nan
    above = body[(b.loc[body, "min_h"].astype(float) >= at - 0.6).values]
    b.drop(index=above, inplace=True)
    reach = [i for i in body if i not in set(above) and float(b.at[i, "h"]) > at]
    b.loc[reach, "h"] = at


def grounded(b: gpd.GeoDataFrame) -> int:
    """Every raised landmark part (min_h > 0) must stand on something: a part or building under it or beside it
    (within 0.5 m: an arch between piers) that starts lower and reaches its underside. One whose highest
    neighbour below stops short is let down onto it (the Sainte-Chapelle's 75 m flèche drawn from 47 m over its
    42 m roof; the Panthéon's portico roof, 23.8 m over its 3.5 m steps: its columns aren't modelled, so a solid
    portico rather than a slab in the air); a sliver (under 1 m2: the lightning rods 4 m over Notre-Dame's towers)
    or a part with nothing under it is dropped. Each is printed (FLOATING): a part in mid-air is a data error to
    look at. Returns how many were dropped."""
    up = b.index[(b["tint"].notna() & (b["min_h"].astype(float) > 0.5)).values]
    if not len(up):
        return 0
    geoms = b.geometry.values
    tree = shapely.STRtree(geoms)
    pos = {k: i for i, k in enumerate(b.index)}
    top, low = b["h"].astype(float).values.copy(), b["min_h"].astype(float).values.copy()
    dropped, lowered = [], 0
    for k in up:
        i = pos[k]
        g, a = geoms[i], max(geoms[i].area, 1e-6)
        near = [j for j in tree.query(g, predicate="dwithin", distance=0.5) if j != i and low[j] < low[i] - 0.1]
        if any(top[j] >= low[i] - 0.6 for j in near):
            continue
        below = [top[j] for j in near if top[j] < low[i]]
        name = b.at[k, "name"]
        if below and a >= 1.0:
            print(f"landmark part let down onto its host: {name} {low[i]:.1f}-{top[i]:.1f} m now from {max(below):.1f} m")
            low[i] = max(below)
            b.at[k, "min_h"] = low[i]
            lowered += 1
            continue
        print(f"FLOATING landmark part dropped: {name} {low[i]:.1f}-{top[i]:.1f} m, {a:.1f} m2, "
              f"{'nothing under it' if not below else f'highest part under it {max(below):.1f} m'}")
        dropped.append(k)
    b.drop(index=dropped, inplace=True)
    print(f"raised landmark parts: {len(up)}, {lowered} let down onto their host, {len(dropped)} FLOATING dropped")
    return len(dropped)


def lid(b: gpd.GeoDataFrame, rows, text: str):
    """'lid@<m>': a hollow block's lid (the Grande Arche's roof over its void): the landmark's lifted parts
    (min_h > 0), however OSM stacked them, merged into one slab from <m> m to the landmark's top, and the
    walls under it taken to the top too."""
    at = float(text[len("lid@"):])
    top = float(b.loc[rows, "h"].max())
    up = rows[(b.loc[rows, "min_h"].astype(float) > 0).values]
    if not len(up):
        print(f"landmark lid: {b.at[rows[0], 'name']} has no lifted part")
        return
    keep = up[0]
    b.at[keep, "geometry"] = b.loc[up].geometry.union_all().buffer(0.5, join_style=2).buffer(-0.5, join_style=2)
    b.at[keep, "min_h"], b.at[keep, "h"] = at, top
    b.drop(index=up[1:], inplace=True)
    # the walls: what reaches into the lid (not the podium or steps under the void)
    walls = [i for i in rows if i not in set(up) and float(b.at[i, "h"]) > at]
    b.loc[walls, "h"] = top


def shape(b: gpd.GeoDataFrame, rows, text: str):
    """'shape@<m>:<profile>': the largest of the landmark's parts whose top is <m> metres (to 0.6 m) lofted
    through the profile, from its own base (a landmark of OSM parts keeps their massing otherwise): the
    Leadenhall Building's wedge, a part OSM draws as a skillion, `shape@224.5:lean:180:0:1 1:0.15`."""
    m, prof = text[len("shape@"):].split(":", 1)
    sel = [i for i in rows if abs(float(b.at[i, "h"]) - float(m)) <= 0.6 and b.at[i, "facade"] != "spire"]
    if not sel:
        print(f"landmark facade: {text}: no part {m} m high")
        return
    k = max(sel, key=lambda i: b.geometry[i].area)
    b.at[k, "profile"] = parse_profile(prof)


def tops(b: gpd.GeoDataFrame, rows, text: str):
    """'tops@<m>:<profile>|<profile>...': the landmark's spire parts (a mast, an antenna), lowest first, stacked
    from <m> metres up, each from the previous one's top, lofted through its own profile (fractions of its own
    span): the Empire State Building's tapering mooring mast and its thin antenna, which OSM maps as prisms
    from the ground up. The tallest spire parts take the profiles (lower slivers are left as they are)."""
    at, profs = text[len("tops@"):].split(":", 1)
    profs = profs.split("|")
    sp = b.loc[rows][(b.loc[rows, "facade"] == "spire").values & (b.loc[rows].area >= 0.2).values].sort_values("h")
    sp = sp.iloc[max(0, len(sp) - len(profs)):]            # the tallest ones, one per profile: not a lower sliver
    y = float(at)
    for (i, row), prof in zip(sp.iterrows(), profs):
        g = row.geometry
        b.at[i, "geometry"] = Polygon(g.exterior) if g.geom_type == "Polygon" else g   # holes of taller parts filled
        b.at[i, "min_h"] = y
        b.at[i, "profile"] = parse_profile(prof)
        y = float(row.h)


def crown(b: gpd.GeoDataFrame, rows, text: str, tint=None):
    """'crown@<m>[-<top>]:<profile>[:#rrggbb]': a body is cut at <m> metres; the piece above becomes a crown
    (the spire style: no windows) lofted through the profile, fractions of the crown's own height (the
    Chrysler Building's stepped stainless arches over its brick shaft; a dome over its drum). Without <top>
    the cut body is the tallest (a part, or the building); with it, every body (not spire) part <top> m high
    (to 0.6 m) that reaches below <m>: a dome that isn't the tallest part (the Invalides' under its lantern,
    the Sacré-Cœur's four small domes). A part that already starts at <m> becomes the crown whole (a nave's
    roof piece). The crown takes the colour after the profile (gilt, lead, copper), else `tint`."""
    at, prof = text[len("crown@"):].split(":", 1)
    col = None
    if len(prof) > 8 and prof[-8] == ":" and prof[-7] == "#":
        prof, col = prof[:-8], prof[-7:]
    col = srgb(col)[0] if col else (tint if tint is not None else srgb(SPIRE_TINT)[0])
    top = None
    if "-" in at:
        at, top = at.split("-")
        top = float(top)
    at = float(at)
    body = rows[(b.loc[rows, "facade"] != "spire").values]
    if top is None:
        # the tallest; of equally tall parts the largest (not a sliver the landmark cap cut to the same height)
        hb = b.loc[body, "h"].astype(float)
        tall = body[(hb >= hb.max() - 0.01).values]
        cut = [b.loc[tall].area.idxmax()]
    else:
        cut = list(body[((b.loc[body, "h"].astype(float) - top).abs() <= 0.6).values])
    for k0 in cut:
        lo = float(b.at[k0, "min_h"] or 0)
        if top is not None and lo > at + 0.6:    # a piece of that height higher up (the Opéra's lantern tip)
            continue
        if not b.at[k0, "h"] > at > lo - 0.6:
            print(f"landmark crown: {b.at[k0, 'name']} is {b.at[k0, 'h']:.0f} m high, no crown from {at:.0f} m")
            continue
        if abs(lo - at) <= 0.6:                  # the part is the crown already: reshape and colour it
            k = k0
        else:
            k = b.index.max() + 1
            b.loc[k] = b.loc[k0]
            b.at[k0, "h"] = at
            b.at[k, "min_h"] = at
        b.at[k, "facade"] = "spire"
        b.at[k, "tint"] = col
        b.at[k, "profile"] = parse_profile(prof)


def roofs(b: gpd.GeoDataFrame, rows, text: str, tint=None):
    """'roofs@<d>[/<min area>]:<profile>[:#rrggbb]': every body part of the landmark at least <min area> m2 (30)
    and more than d + 2 m high has its top <d> metres cut off as a roof (the spire style, coloured), lofted
    through the profile: a palace of many OSM parts with flat tops gets its steep roofs (the Palace of
    Westminster's iron roofs, `roofs@7/60:0:1:0 1:1:5:#4a5058`: the outline moving in 5 m, a hipped roof over
    any outline, courtyards too). Runs after the crowns."""
    d, rest = text[len("roofs@"):].split(":", 1)
    d, _, min_a = d.partition("/")
    d, min_a = float(d), float(min_a or 30.0)
    col = None
    if len(rest) > 8 and rest[-8] == ":" and rest[-7] == "#":
        rest, col = rest[:-8], rest[-7:]
    col = srgb(col)[0] if col else (tint if tint is not None else srgb(SPIRE_TINT)[0])
    prof = parse_profile(rest)
    body = [i for i in rows if b.at[i, "facade"] != "spire" and b.geometry[i].area >= min_a
            and float(b.at[i, "h"]) - float(b.at[i, "min_h"] or 0) > d + 2]
    for k0 in body:
        k = b.index.max() + 1
        b.loc[k] = b.loc[k0]
        b.at[k0, "h"] = float(b.at[k0, "h"]) - d
        b.at[k, "min_h"] = float(b.at[k0, "h"])
        b.at[k, "facade"] = "spire"
        b.at[k, "tint"] = col
        b.at[k, "profile"] = prof


def road_clearance(b: gpd.GeoDataFrame, ways: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop satellite-derived footprints that stand on a carriageway or under a viaduct deck.

    The East Asia and GBA footprints come from image segmentation, which also outlines toll booths,
    parked lorries and whole interchange decks as "buildings"; extruded, they stand in the road or
    pierce the viaduct. OSM buildings are always kept (people drew them; elevated stations do span
    roads). Thresholds are shares of the footprint's area:
      CLEAR_MAJOR    on the core of a major road (the middle 80 % of its width)
      CLEAR_MINOR    on the core of a minor or service road, lenient because village alleys are mapped
                     as residential roads narrower than the default width assumed for them
      CLEAR_DECK     under an elevated deck (full width)
      CLEAR_ANY      on any mix of roads and decks at full width, for pieces that straddle a ramp, a
                     slip road and a viaduct and stay under each single threshold
    Writes the counts to checks/road_clearance.md.
    """
    # people drew OSM's footprints, and official ones are surveyed: only the others are candidates
    from .. import sources
    trusted = {"osm"} | {n for n in CFG["sources"]["footprints"]
                         if n != "osm" and sources.module(n).ROLE == "primary"}
    cand = b[~b.source.isin(trusted)]
    cand = cand.assign(area=cand.area)[["area", "geometry"]].reset_index(names="bid")

    def share(roads: gpd.GeoDataFrame, half_width: pd.Series) -> pd.Series:
        r = gpd.GeoDataFrame(geometry=roads.geometry.buffer(half_width, cap_style="flat"), crs=roads.crs)
        ov = gpd.overlay(cand, r, how="intersection", keep_geom_type=True)
        # overlapping road polygons would count twice: dissolve per building first
        ov = ov.dissolve("bid", aggfunc="first")
        return (ov.area / ov["area"]).reindex(cand.bid).fillna(0).set_axis(cand.index)

    ground = ways[~ways.elevated & (ways.kind != "rail")]
    major = ground[ground.kind == "major"]
    minor = ground[ground.kind != "major"]
    deck = ways[ways.elevated]
    rules = {
        "major road": share(major, major.width * 0.4) >= CLEAR_MAJOR,
        "minor road": share(minor, minor.width * 0.4) >= CLEAR_MINOR,
        "under a deck": share(deck, deck.width * 0.5) >= CLEAR_DECK,
        "on roads combined": share(ways[ways.kind != "rail"], ways[ways.kind != "rail"].width * 0.5) >= CLEAR_ANY,
    }
    drop = np.zeros(len(cand), bool)
    lines = ["# Road clearance (06_tiles.py)", "",
             "Satellite-derived footprints dropped because they stand on a carriageway or under a viaduct deck",
             f"(thresholds: {CLEAR_MAJOR:.0%} of the footprint on a major road core, {CLEAR_MINOR:.0%} on a minor one,",
             f"{CLEAR_DECK:.0%} under a deck, {CLEAR_ANY:.0%} on all roads and decks together). OSM buildings",
             "are never dropped.", "",
             "| Rule | footprints | of which new |", "|---|---|---|"]
    for name, hit in rules.items():
        new = hit.values & ~drop
        lines.append(f"| {name} | {int(hit.sum()):,} | {int(new.sum()):,} |")
        drop |= hit.values
    lines += ["", f"Dropped {int(drop.sum()):,} of {len(b):,} buildings."]
    # the trusted footprints on roads, for the record: buildings over a street (arcades, spans over ramps)
    # or a road drawn through a building
    t = b[b.source.isin(trusted) & b.geom_type.isin(["Polygon", "MultiPolygon"])]
    t = t.assign(area=t.area)[["area", "geometry"]].reset_index(names="bid")
    if len(t) and len(major):
        r = gpd.GeoDataFrame(geometry=major.geometry.buffer(major.width * 0.4, cap_style="flat"), crs=major.crs)
        ov = gpd.overlay(t, r, how="intersection", keep_geom_type=True).dissolve("bid", aggfunc="first")
        hit = (ov.area / ov["area"]) >= CLEAR_MAJOR
        lines += ["", f"Kept (trusted sources): {int(hit.sum()):,} of {len(t):,} footprints have {CLEAR_MAJOR:.0%} "
                  "or more on a major road's core (buildings bridging a street, or roads mapped through a "
                  "building)."]
    (CHECKS / "road_clearance.md").write_text("\n".join(lines) + "\n")
    print(f"road clearance: dropped {int(drop.sum()):,} footprints on roads or under decks")
    ids = cand.bid[drop]
    return b.drop(index=ids)


def camera_views(b: gpd.GeoDataFrame, origin, terrain: Terrain) -> list[dict]:
    """The menu's camera presets (AREAS, LANDMARKS) in scene coordinates, looking at the ground (areas) or
    part of the way up a landmark (views.landmark_frame)."""
    pts = gpd.GeoSeries(gpd.points_from_xy([v[0] for v in AREAS.values()], [v[1] for v in AREAS.values()]),
                        crs="EPSG:4326").to_crs(UTM)
    ground = terrain.height_utm(pts.x.values, pts.y.values)
    views = []
    for (n, v), p, y in zip(AREAS.items(), pts, ground):
        # [lon, lat, distance, elevation(, azimuth(, lift(, hour)))]: the direction looked from (city.json's
        # camera.azimuth when left out), the target's height over the ground (a street view's eye line) and the
        # hour the view sets (a dusk or night preset: the menu's time jumps there; none: the time is left alone)
        views.append({"group": "Areas", "name": n, "x": p.x - origin[0], "z": -(p.y - origin[1]),
                      "y": round(float(y) + (v[5] if len(v) > 5 else 0), 1), "distance": v[2], "elevation": v[3],
                      **({"azimuth": v[4]} if len(v) > 4 else {}), **({"time": v[6]} if len(v) > 6 else {})})
    far, aim, elev = CFG["views"]["landmark_frame"]
    for label, spec in LANDMARKS.items():
        # "building name" or [name, azimuth(, distance m(, elevation degrees))]
        name, az, dist, el = (spec, None, None, None) if isinstance(spec, str) else (list(spec) + [None] * 2)[:4]
        hit = b[b.name == name]
        if not len(hit):
            print(f"view: no building named {name}")
            continue
        # a building made of parts is all its rows: framed as a whole, to its main roof (not its spire)
        from .buildings import main_roof
        geom = hit.geometry.union_all()
        h = main_roof(hit) if len(hit) > 1 else float(hit.h.max())
        c = geom.centroid
        size = max(float(hit.h.max()) * 1.08, np.sqrt(geom.area))       # the whole of it in view, spire and all
        tall = h > np.sqrt(geom.area)
        base = float(terrain.bases([geom])[0])
        views.append({"group": "Landmarks", "name": label, "x": c.x - origin[0], "z": -(c.y - origin[1]),
                      "y": round(base + (h * aim if tall else 0), 1), "distance": round(dist or max(350, size * far)),
                      "elevation": el or (elev if tall else 30), **({"azimuth": az} if az is not None else {})})
    moved = {n: g for g, names in GROUPS.items() for n in names}
    for v in views:
        v["group"] = moved.get(v["name"], v["group"])
    for n in set(moved) - {v["name"] for v in views}:
        print(f"view groups: no view named {n}")
    order = list(dict.fromkeys(["Areas", *GROUPS, "Landmarks"]))
    # [views] group_order = true: the chips of a group listed in [views.groups] in that list's order (else in
    # [views.areas]' order, as before)
    rank = {n: i for names in GROUPS.values() for i, n in enumerate(names)} if CFG["views"].get("group_order") else {}
    return sorted(views, key=lambda v: (order.index(v["group"]) if v["group"] in order else len(order), rank.get(v["name"], 0)))


def plant_room(poly: Polygon):
    """A box on the roof: the footprint shrunk around its centre to about 12 % of its area."""
    c = poly.representative_point()
    room = affinity.scale(poly, 0.35, 0.35, origin=c).intersection(poly.buffer(-2))
    room = max(polygons(room), key=lambda p: p.area, default=None)
    return room if room is not None and room.area >= 12 else None
# linear RGB (glTF vertex colours are linear): asphalt reads as mid-dark grey from the air
ROAD_RGB = {"major": (0.10, 0.104, 0.112), "minor": (0.13, 0.13, 0.136), "service": (0.16, 0.16, 0.16),
            "rail": (0.19, 0.16, 0.14)}
CONCRETE = (0.42, 0.41, 0.38)
ROAD_Y = 1.5                 # above land (0) and the viewer's lifted green/water/aeroway layers
DECK_T = 1.4
PILLAR_STEP = 32
PILLAR_MIN_H = 4.5


# ---------------------------------------------------------------- geometry

def polygons(geom):
    return [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]


def triangulate(poly: Polygon):
    """Earcut a polygon with holes. Returns (vertices Nx2, triangles Mx3)."""
    rings = [np.asarray(poly.exterior.coords)[:-1]] + [np.asarray(r.coords)[:-1] for r in poly.interiors]
    rings = [r for r in rings if len(r) >= 3]
    verts = np.concatenate(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    tri = earcut.triangulate_float64(verts, ends).reshape(-1, 3)
    return verts, tri


def orient(pos, tri, normals):
    """Flip triangles whose winding disagrees with the intended normal (three.js: CCW = front)."""
    a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    bad = (np.cross(b - a, c - a) * normals[tri[:, 0]]).sum(1) < 0
    tri[bad] = tri[bad][:, [0, 2, 1]]
    return tri


def to_scene(xy, origin):
    """UTM (E, N) -> scene (x, z)."""
    return np.stack([xy[:, 0] - origin[0], -(xy[:, 1] - origin[1])], 1)


def extrude(poly: Polygon, h: float, origin, rgb, facade=(0.0, 0.0), base: float = 0.0,
            module: float = 0.0, profile=None, ground: float = 0.0, skirt: float = 0.0, free=None,
            roof_code: float = 0.0, roof_out: list | None = None):
    """Walls + flat roof of one footprint, from `base` up to `h` above `ground` (the walls reaching `skirt`
    further down). Returns dict of per-vertex arrays and indices.

    facade = (style id, seed) for the facade shader's TEXCOORD_1; module (m, 0 = the style's default) is
    the window bay width, stored in COLOR_0's alpha. Wall UVs restart at every corner sharper than
    CORNER_DEG and carry their run's length, so the shader can fit a whole number of window bays
    between corners.

    profile: optional [(height fraction, scale[, inset]), ...] from 0 to 1, lofting the footprint through
    those levels: scaled about its centroid (tapers, setbacks, domes) and/or its outline moved inward
    by `inset` metres, each vertex along its mitred normal (shells whose roof curves over following the
    building's own outline, arms and all). Wall UVs stay those of the base ring, so the bays narrow
    with the building and fins converge.

    free: optional function (wall midpoints, UTM Nx2) -> 0..1 per wall, how far that wall takes the insets
    (0: a party wall that stays vertical, its neighbours' corners sliding along it). roof_code: TEXCOORD_2.y.
    roof_out: optional list the flat top's outline (UTM polygon, at `h`) is appended to (06c_rooftops: a
    mansard's terrasson, a pitched roof's ridge strip).
    """
    levels = [(ground + base + f * (h - base), lv[0], lv[1] if len(lv) > 1 else 0.0, lv[2] if len(lv) > 2 else 0.0)
              for f, *lv in (profile or [(0, 1), (1, 1)])]
    levels[0] = (levels[0][0] - skirt, *levels[0][1:])
    top_rings = []
    cen = to_scene(np.array([poly.centroid.coords[0]]), origin)[0]
    anchor = 0.0
    lean = next((lv[1][2] for lv in levels if isinstance(lv[1], tuple) and len(lv[1]) == 3), None)
    if lean is not None:
        # 'lean:' profiles: scaled along a compass bearing about the footprint's far side opposite it, which
        # stays vertical (a wedge: the Leadenhall Building's south face leaning back to its upright north side)
        t = np.radians(lean)
        ax = np.array([np.sin(t), -np.cos(t)])                     # scene x east, z south
        ring = to_scene(np.asarray(poly.exterior.coords), origin)
        anchor = float(((ring - cen) @ ax).min())
        levels = [(y, (k[0], k[1]) if isinstance(k, tuple) else (k, k), d, r) for y, k, d, r in levels]
    elif any(isinstance(lv[1], tuple) for lv in levels):
        # scales along and across the long axis ('long:' profiles): that axis in scene xz
        rr = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)
        e = [rr[1] - rr[0], rr[2] - rr[1]]
        e = max(e, key=np.linalg.norm)
        ax = np.array([e[0], -e[1]]) / max(np.linalg.norm(e), 1e-9)
        levels = [(y, k if isinstance(k, tuple) else (k, k), d, r) for y, k, d, r in levels]
    else:
        ax = None

    def scaled(r, k):
        """offsets r from the centroid (N x 2), scaled by k: a number, or (along, across) the long axis"""
        if not isinstance(k, tuple):
            return r * k
        along = r @ ax - anchor
        return r + np.outer(along * (k[0] - 1), ax) + np.outer((r @ np.array([-ax[1], ax[0]])) * (k[1] - 1),
                                                                np.array([-ax[1], ax[0]]))
    kk = lambda k: k[0] * k[1] if isinstance(k, tuple) else k
    pos, nrm, uv, idx = [], [], [], []
    n0 = 0
    rings = [poly.exterior] + list(poly.interiors)
    for k, ring in enumerate(rings):
        c = np.asarray(ring.coords)
        # exterior counter-clockwise, holes clockwise, so (dy, -dx) always points out of the solid
        if (k == 0) != ring.is_ccw:
            c = c[::-1]
        p = to_scene(c, origin)                       # (x, z)
        a, b = p[:-1], p[1:]
        d = b - a
        length = np.linalg.norm(d, axis=1)
        keep = length > 0.05
        a, b, d, length = a[keep], b[keep], d[keep], length[keep]
        if not len(a):
            continue
        # runs of wall between corners; start the ring at a corner so no run wraps around
        u = d / length[:, None]
        corner = (u * np.roll(u, 1, axis=0)).sum(1) < np.cos(np.radians(CORNER_DEG))
        if corner.any():
            r = int(np.argmax(corner))
            a, b, d, length, corner = (np.roll(x, -r, axis=0) for x in (a, b, d, length, corner))
        else:
            corner[0] = True
        run_id = np.cumsum(corner) - 1
        start = np.concatenate([[0], np.cumsum(length)[:-1]])
        s0 = start - start[corner][run_id]
        run_len = np.bincount(run_id, length)[run_id]
        # in scene coords z = -N, which mirrors the ring, so the outward normal is (-dz, dx)
        out = np.stack([-d[:, 1] / length, np.zeros(len(a)), d[:, 0] / length], 1)
        m = len(a)
        # per-vertex inset direction: into the solid along the mitred normal (vertex i joins walls i-1, i)
        o2 = out[:, [0, 2]]
        vn = o2 + np.roll(o2, 1, axis=0)
        vn /= np.linalg.norm(vn, axis=1, keepdims=True).clip(1e-9)
        off_a = vn / np.maximum((vn * o2).sum(1), 0.35)[:, None]
        if free is not None:
            # per-wall insets: each vertex moves so that wall i-1 moves in by w[i-1] and wall i by w[i] (the
            # mitre where both are 1); nearly parallel walls take their mean along the mitre
            mid = (a + b) / 2
            w = np.clip(np.asarray(free(np.column_stack([mid[:, 0] + origin[0], origin[1] - mid[:, 1]])), float), 0, 1)
            wp = np.roll(w, 1)
            n0_, n1_ = np.roll(o2, 1, axis=0), o2
            det = n0_[:, 0] * n1_[:, 1] - n0_[:, 1] * n1_[:, 0]
            ok = np.abs(det) > 0.25
            sd = np.where(ok, det, 1.0)
            vx = (wp * n1_[:, 1] - w * n0_[:, 1]) / sd
            vz = (w * n0_[:, 0] - wp * n1_[:, 0]) / sd
            v = np.column_stack([vx, vz])
            v = np.where(ok[:, None], v, off_a * ((w + wp) / 2)[:, None])
            ln = np.linalg.norm(v, axis=1, keepdims=True)
            off_a = v * np.minimum(1.0, 2.9 / np.maximum(ln, 1e-9))
        d_max = max(lv[2] for lv in levels)
        # a level turned about the centroid (an antiprism: 1 WTC's square turning 45 degrees as it rises):
        # the turn's sign that carries each corner towards the middle of its wall, not away from it
        if any(lv[3] for lv in levels):
            mid = (a + b) / 2
            def turn(pts, deg):
                t = np.radians(deg)
                r = pts - cen
                return cen + np.stack([r[:, 0] * np.cos(t) - r[:, 1] * np.sin(t), r[:, 0] * np.sin(t) + r[:, 1] * np.cos(t)], 1)
            k_top = max(levels, key=lambda lv: abs(lv[3]))
            sign = 1.0 if np.linalg.norm(cen + (turn(a, k_top[3]) - cen) * k_top[1] - mid, axis=1).sum() <= \
                np.linalg.norm(cen + (turn(a, -k_top[3]) - cen) * k_top[1] - mid, axis=1).sum() else -1.0
        else:
            turn, sign = (lambda pts, deg: pts), 1.0
        if d_max > 0:
            # where the footprint is narrower than twice the inset, opposite sides would cross and the
            # roof fold through itself: each vertex moves in at most 40 % of the distance to the far side
            off_a = off_a * inset_room(poly, a, off_a, d_max, origin)[:, None]
        off_b = np.roll(off_a, -1, axis=0)
        at = lambda pts, off, k_, d_, r_=0.0: cen + scaled(turn(pts, sign * r_) - cen, k_) - off * d_
        for (y0, k0, d0, r0), (y1, k1, d1, r1) in zip(levels[:-1], levels[1:]):
            a0, b0 = at(a, off_a, k0, d0, r0), at(b, off_b, k0, d0, r0)
            a1, b1 = at(a, off_a, k1, d1, r1), at(b, off_b, k1, d1, r1)
            quad = np.zeros((m, 4, 3))
            quad[:, 0, [0, 2]], quad[:, 1, [0, 2]] = a0, b0
            quad[:, 2, [0, 2]], quad[:, 3, [0, 2]] = b1, a1
            quad[:, 0, 1] = quad[:, 1, 1] = y0
            quad[:, 2, 1] = quad[:, 3, 1] = y1
            # tilted walls (and flat ledges where a profile steps in) get their true normal
            along = quad[:, 1] - quad[:, 0]
            up = (quad[:, 3] + quad[:, 2] - quad[:, 0] - quad[:, 1]) / 2
            n = np.cross(up, along)
            n *= np.sign((n * out).sum(1) + 1e-9 * n[:, 1])[:, None]
            norm = np.linalg.norm(n, axis=1, keepdims=True)
            n = np.where(norm > 1e-9, n / np.maximum(norm, 1e-12), out)
            if y1 == y0:
                n = np.tile([0.0, 1.0 if (kk(k1) < kk(k0) or d1 > d0) else -1.0, 0.0], (m, 1))
            pos.append(quad.reshape(-1, 3))
            nrm.append(np.repeat(n, 4, axis=0))
            quv = np.zeros((m, 4, 2))
            quv[:, 0, 0], quv[:, 1, 0], quv[:, 2, 0], quv[:, 3, 0] = s0, s0 + length, s0 + length, s0
            quv[:, :, 1] = run_len[:, None]
            uv.append(quv.reshape(-1, 2))
            base_i = 4 * np.arange(m)[:, None]
            # turning levels split each quad along b0-a1: the wall's triangle standing on its base edge and the
            # inverted one between (an antiprism's faces), not the other diagonal's twisted pair
            tq = [0, 1, 3, 1, 2, 3] if r1 != r0 else [0, 1, 2, 0, 2, 3]
            t = (base_i + np.array(tq)).reshape(-1, 3)
            t = orient(pos[-1], t, nrm[-1])
            idx.append(n0 + t.reshape(-1))
            n0 += 4 * m
        top_rings.append(at(a, off_a, levels[-1][1], levels[-1][2], levels[-1][3]))
    top, k_top, d_top, r_top = levels[-1]
    if (d_top > 0 or r_top or isinstance(k_top, tuple)) and top_rings:
        # the inset outline, back in map coordinates; mitred insets can fold in narrow parts, so repair it
        utm = [np.column_stack([r[:, 0] + origin[0], origin[1] - r[:, 1]]) for r in top_rings]
        roof_poly = max(polygons(make_valid(Polygon(utm[0], utm[1:]))), key=lambda p: p.area, default=poly)
    else:
        roof_poly = poly if k_top == 1 else affinity.scale(poly, k_top, k_top, origin=poly.centroid)
    if roof_out is not None:
        roof_out.append(roof_poly)
    k_min = min(k_top) if isinstance(k_top, tuple) else k_top
    v2, tri = triangulate(roof_poly) if k_min > 0.03 else (None, [])
    if len(tri):
        p = to_scene(v2, origin)
        pos.append(np.column_stack([p[:, 0], np.full(len(p), top), p[:, 1]]))
        nrm.append(np.tile([0.0, 1.0, 0.0], (len(p), 1)))
        uv.append(np.zeros((len(p), 2)))
        idx.append(n0 + orient(pos[-1], tri.astype(np.int64), nrm[-1]).reshape(-1))
        n0 += len(p)
    if not pos:
        return None
    n = sum(len(x) for x in pos)
    style, seed = facade
    rgba = [*rgb[:3], min(module / MODULE_MAX, 1.0)]
    return {"pos": np.concatenate(pos), "nrm": np.concatenate(nrm), "uv": np.concatenate(uv),
            "col": np.tile(rgba, (n, 1)), "fac": np.tile([style + 0.999 * seed, h], (n, 1)),
            "base": np.tile([ground, roof_code], (n, 1)), "idx": np.concatenate(idx)}


def inset_room(poly: Polygon, pts, off, d_max: float, origin) -> np.ndarray:
    """Per vertex (scene xz `pts`, inward offsets `off` per metre): the share of an inset of d_max
    metres it can take, 0.4 x the distance to the far side of the footprint along its inset direction."""
    boundary = poly.boundary
    out = np.ones(len(pts))
    for i, (p, o) in enumerate(zip(pts, off)):
        n = np.linalg.norm(o)
        if n < 1e-9:
            continue
        u = -o / n                                            # inward, scene xz
        start = p + u * 0.05
        end = p + u * (3 * d_max * n + 1)
        utm = [(q[0] + origin[0], origin[1] - q[1]) for q in (start, end)]
        hit = boundary.intersection(LineString(utm))
        if hit.is_empty:
            continue
        dist = shapely.distance(shapely.Point(utm[0]), hit)
        out[i] = min(1.0, 0.4 * (dist + 0.05) / (d_max * n))
    return out


def parse_profile(text) -> list | None:
    """'0:1 0.9:1 1:0.8' -> [(0, 1), (0.9, 1), (1, 0.8)]; 'dome:f' -> vertical to f, then a quarter ellipse
    scaled about the centroid; 'shell:f:d' -> the same curve, but the outline moves in by up to d metres."""
    if not isinstance(text, str) or not text.strip():
        return None
    if text.startswith("anti:"):
        # vertical to f, then a square antiprism: the outline turns 45 degrees and shrinks to 1/sqrt(2), its
        # corners ending over the middles of the walls below (One World Trade Center)
        f = float(text.split(":")[1])
        return [(0.0, 1.0, 0.0, 0.0), (f, 1.0, 0.0, 0.0), (1.0, float(np.sqrt(0.5)), 0.0, 45.0)]
    if text.startswith("shell:"):
        # vertical walls to f, then the outline moves in by up to d metres along a quarter ellipse
        f, d = map(float, text.split(":")[1:3])
        th = np.linspace(0, np.pi / 2, 9)
        return [(0.0, 1.0, 0.0)] + [(f + (1 - f) * np.sin(t), 1.0, d * (1 - np.cos(t))) for t in th]
    if text.startswith("long:"):
        # 'long:f:sl:sw ...': scaled about the centroid by sl along the footprint's long axis (its minimum
        # rotated rectangle's) and sw across it: a wedge or a trapezoid in side view (Tour Triangle), a gable
        # roof ('long:0:1:1 1:1:0.02', its ridge along the long axis)
        return [(float(f), (float(sl), float(sw))) for f, sl, sw in (t.split(":") for t in text[5:].split())]
    if text.startswith("lean:"):
        # 'lean:<bearing>:f:s ...': the side facing the compass bearing (degrees) moves in towards the opposite
        # side, which stays vertical, to s of the depth along that bearing at height fraction f
        bearing, rest = text[5:].split(":", 1)
        return [(float(f), (float(k), 1.0, float(bearing))) for f, k in (t.split(":") for t in rest.split())]
    if text.startswith("dome:"):
        f = float(text.split(":")[1])
        th = np.linspace(0, np.pi / 2, 9)
        return [(0.0, 1.0)] + [(f + (1 - f) * np.sin(t), max(np.cos(t), 0.08)) for t in th]
    return [tuple(map(float, pair.split(":"))) for pair in text.split()]


def water_levels(rows, terrain: Terrain, near=None):
    """The level of each levelled water body (UTM polygons; 05a_terrain holds them flat; NaN where one was left
    on its slope): the commonest ground height over points inside it ([terrain] quay_walls drops the cells
    along its quays under it, so neither the mean nor the minimum will do)."""
    rng = np.random.default_rng(11)
    out = np.full(len(rows), np.nan)
    for i, g in enumerate(rows):
        if g is None or g.is_empty or g.area < 200 or (near is not None and not g.intersects(near)):
            continue
        x0, y0, x1, y1 = g.bounds
        n = int(min(max(g.area / 25, 200), 20000))
        pts = np.column_stack([rng.uniform(x0, x1, n * 3), rng.uniform(y0, y1, n * 3)])
        pts = pts[shapely.contains_xy(g, pts[:, 0], pts[:, 1])][:n]
        if len(pts) < 20:
            continue
        h = np.round(terrain.height_utm(pts[:, 0], pts[:, 1]), 2)
        v, c = np.unique(h, return_counts=True)
        if c.max() >= 0.3 * len(h):
            out[i] = v[np.argmax(c)]
    return out


def draped(poly: Polygon, lift: float, origin, terrain: Terrain):
    """A polygon (UTM) laid `lift` metres over the ground, cut along the TIN where the ground isn't level."""
    scene = shapely.transform(poly, lambda c: to_scene(c, origin))
    parts = []
    for v2, y, nrm, tri in terrain.drape(scene):
        pos = np.column_stack([v2[:, 0], y + lift, v2[:, 1]])
        parts.append({"pos": pos, "nrm": nrm, "idx": orient(pos, tri.copy(), nrm).reshape(-1)})
    return merge(parts) if parts else None


def weld(m: dict) -> dict:
    """Vertices at the same place (to a millimetre) merged into one, and the slivers that collapses dropped."""
    _, first, inv = np.unique(np.round(m["pos"] * 1000).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    t = inv.reshape(-1)[m["idx"]].reshape(-1, 3)
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    return {**{k: v[first] for k, v in m.items() if k != "idx"}, "idx": t.reshape(-1)}


def merge(parts):
    parts = [p for p in parts if p is not None]
    out, off = {k: [] for k in parts[0]}, 0
    for p in parts:
        for k, v in p.items():
            out[k].append(v + off if k == "idx" else v)
        off += len(p["pos"])
    return {k: np.concatenate(v) for k, v in out.items()}


# ---------------------------------------------------------------- roads

def colored(part, rgb):
    if part is not None:
        part["col"] = np.tile(rgb, (len(part["pos"]), 1))
    return part


def ground_roads(ways: gpd.GeoDataFrame, origin, terrain: Terrain) -> dict:
    """(tx, ty) -> merged mesh of the ground-level roads and railways in that tile."""
    g = ways[~ways.elevated].copy()
    g["geometry"] = g.geometry.buffer(g.width / 2, resolution=3)
    out = {}
    # a buffered way spans several tiles: find every tile its bounds touch
    b = g.bounds
    tx0 = np.floor((b.minx - origin[0]) / TILE).astype(int)
    tx1 = np.floor((b.maxx - origin[0]) / TILE).astype(int)
    ty0 = np.floor((b.miny - origin[1]) / TILE).astype(int)
    ty1 = np.floor((b.maxy - origin[1]) / TILE).astype(int)
    members = {}
    for i, a, c, d, e in zip(range(len(g)), tx0, tx1, ty0, ty1):
        for tx in range(a, c + 1):
            for ty in range(d, e + 1):
                members.setdefault((tx, ty), []).append(i)
    geoms, kinds = g.geometry.values, g.kind.values
    for (tx, ty), idx in members.items():
        cell = box(origin[0] + tx * TILE, origin[1] + ty * TILE,
                   origin[0] + (tx + 1) * TILE, origin[1] + (ty + 1) * TILE)
        taken, parts = None, []
        for kind in ("major", "minor", "service", "rail"):       # earlier kinds are drawn on top
            sel = [geoms[i] for i in idx if kinds[i] == kind]
            if not sel:
                continue
            shape = unary_union(sel).intersection(cell)
            if taken is not None:
                shape = shape.difference(taken)
            taken = shape if taken is None else taken.union(shape)
            shape = shape.simplify(0.2)
            parts += [colored(draped(p, ROAD_Y, origin, terrain), ROAD_RGB[kind]) for p in polygons(shape) if p.area > 1]
        parts = [p for p in parts if p is not None]
        if parts:
            out[(tx, ty)] = merge(parts)
    return out


def deck(coords, w: float, origin, rgb, terrain: Terrain, dry=None, forbid=None):
    """Per-segment deck pieces along a 3D line (UTM x, y, deck height): list of (midpoint xy, mesh).
    dry: for a long-span crossing ([roads] decks: a suspension or arch bridge), the land it may stand on; no
    pillars elsewhere (its towers are the landmark models' to draw)."""
    c = np.asarray(coords, dtype=float)
    keep = np.r_[True, np.linalg.norm(np.diff(c[:, :2], axis=0), axis=1) > 0.05]
    c = c[keep]
    if len(c) < 2:
        return []
    p = to_scene(c[:, :2], origin)                              # (x, z)
    top = c[:, 2] + ROAD_Y
    d = np.diff(p, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    seg_n = np.stack([-d[:, 1], d[:, 0]], 1)                    # left normal of each segment
    # mitred offset at each vertex: average of the neighbouring segment normals, capped at 2x
    vn = np.zeros_like(p)
    vn[:-1] += seg_n
    vn[1:] += seg_n
    vn /= np.linalg.norm(vn, axis=1, keepdims=True).clip(1e-9)
    cos = np.ones(len(p))
    cos[1:-1] = (vn[1:-1] * seg_n[:-1]).sum(1)
    off = vn * (w / 2 / np.clip(cos, 0.5, 1))[:, None]
    L, R = p + off, p - off
    pieces = []
    for i in range(len(p) - 1):
        j = i + 1
        l0, l1, r0, r1 = L[i], L[j], R[i], R[j]
        y0, y1 = top[i], top[j]
        pos, nrm, cols, idx = [], [], [], []

        def quad(v, n, rgb_):
            k = sum(len(x) for x in pos)
            pos.append(np.asarray(v))
            nrm.append(np.tile(n, (4, 1)))
            cols.append(np.tile(rgb_, (4, 1)))
            t = np.array([[0, 1, 2], [0, 2, 3]])
            idx.append(k + orient(pos[-1], t.copy(), nrm[-1]))

        def P(xz, y):
            return [xz[0], y, xz[1]]
        quad([P(l0, y0), P(l1, y1), P(r1, y1), P(r0, y0)], [0, 1, 0], rgb)                  # top
        quad([P(r0, y0 - DECK_T), P(r1, y1 - DECK_T), P(l1, y1 - DECK_T), P(l0, y0 - DECK_T)],
             [0, -1, 0], CONCRETE)                                                       # soffit
        n = [seg_n[i][0], 0, seg_n[i][1]]
        quad([P(l0, y0 - DECK_T), P(l1, y1 - DECK_T), P(l1, y1), P(l0, y0)], n, CONCRETE)  # sides
        quad([P(r1, y1 - DECK_T), P(r0, y0 - DECK_T), P(r0, y0), P(r1, y1)], [-n[0], 0, -n[2]], CONCRETE)
        pos = np.concatenate(pos)
        mesh = {"pos": pos, "nrm": np.concatenate(nrm), "uv": pos[:, [0, 2]] * [1, -1],
                "col": np.concatenate(cols), "idx": np.concatenate(idx).reshape(-1)}
        pieces.append(((c[i, :2] + c[j, :2]) / 2, mesh))
    # pillars
    seg_len = np.linalg.norm(np.diff(c[:, :2], axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg_len)]
    for at in np.arange(PILLAR_STEP / 2, s[-1], PILLAR_STEP):
        k = min(np.searchsorted(s, at) - 1, len(seg_len) - 1)
        f = (at - s[k]) / max(seg_len[k], 1e-9)
        xy = c[k, :2] + f * (c[k + 1, :2] - c[k, :2])
        g = float(terrain.height_utm([xy[0]], [xy[1]])[0])
        h = c[k, 2] + f * (c[k + 1, 2] - c[k, 2]) - DECK_T + ROAD_Y - g        # soffit above the ground
        pt = shapely.Point(*xy)
        if h < PILLAR_MIN_H or (dry is not None and not dry.contains(pt)) or (forbid is not None and forbid.contains(pt)):
            continue
        across = min(w * 0.45, 7.0)
        rect = box(-1.1, -across / 2, 1.1, across / 2)
        ang = np.degrees(np.arctan2(*(c[k + 1, :2] - c[k, :2])[::-1]))
        rect = affinity.translate(affinity.rotate(rect, ang, origin=(0, 0)), *xy)
        m = extrude(rect, h, origin, CONCRETE, ground=g, skirt=SKIRT)
        if m is not None:
            pieces.append((xy, {**{k_: m[k_] for k_ in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]}))
    return pieces


def bridges(ways: gpd.GeoDataFrame, origin, terrain: Terrain) -> dict:
    """(tx, ty) -> merged mesh of the bridge decks and pillars whose piece midpoints fall in that tile."""
    out = {}
    spans = set(CFG["roads"]["decks"])
    dry = None
    if (spans or not T["pillars_in_water"]) and "name" in ways:
        land = gpd.read_file(DATA / "ground.gpkg", layer="land").union_all()
        water = gpd.read_file(DATA / "ground.gpkg", layer="water").union_all()
        dry = shapely.prepared.prep(land.difference(water))
    names = ways["span"] if "span" in ways else [None] * len(ways)
    # suspended spans ([[structures]]): their decks hang from the cables, no pillars under them
    from . import structures
    z = structures.zones()
    # no stick pillars inside an arcaded bridge's outline ([roads] piers {upper, arcade}: its upper deck stands on the
    # arcade) nor inside the viaduct structures railways run on ([roads] rail_on)
    extra = []
    R_ = CFG["roads"]
    if R_.get("bridge_outlines") and any(isinstance(e, dict) and e.get("arcade") for e in R_.get("piers", {}).values()):
        import pyogrio
        if "outlines" in {l[0] for l in pyogrio.list_layers(DATA / "roads.gpkg")}:
            o = gpd.read_file(DATA / "roads.gpkg", layer="outlines")
            arc = {k for k, e in R_["piers"].items() if isinstance(e, dict) and e.get("arcade")}
            extra += [g.buffer(2.0) for g in o[o.span.isin(arc)].geometry]
    if R_.get("rail_on"):
        from .roads import arch_structures
        geoms, _ = arch_structures()
        extra += [g.buffer(1.5) for g in geoms]
        print(f"pillars: none inside {len(geoms):,} viaduct structures ([roads] rail_on)")
    if extra:
        z = unary_union(([z] if z is not None else []) + extra)
    forbid = shapely.prepared.prep(z) if z is not None else None
    for geom, w, kind, name in zip(ways.geometry, ways.width, ways.kind, names):
        wet_ok = T["pillars_in_water"] and name not in spans
        for mid, m in deck(geom.coords, w, origin, ROAD_RGB[kind], terrain, None if wet_ok else dry, forbid):
            key = (int(np.floor((mid[0] - origin[0]) / TILE)), int(np.floor((mid[1] - origin[1]) / TILE)))
            out.setdefault(key, []).append(m)
    return {k: merge(v) for k, v in out.items()}


STONE = (0.40, 0.37, 0.31)       # linear: pale limestone piers and fascias
PAVING = (0.27, 0.265, 0.25)     # a bridge's pavements round its carriageway
PIER_T, CUTWATER = 3.0, 1.8      # a pier's thickness along the bridge (m) and its cutwaters' point beyond the deck


# [roads] piers types (an entry {spans, fascia, type, ...} or [spans, fascia, type]): the bridge's elevation, an
# arcade cut from its side faces, instead of a flat slab on box piers. arch: the openings' curve ("ellipse", a
# basket-handle or, at rise 0.5, semicircular stone arch; "segment", a low circular iron or concrete arch; none:
# a girder with a flat soffit); rise: the arch's rise over its span (capped where it would spring lower than
# `spring` m over the water); pier_t: a pier's thickness as a share of the span (at least 2 m); fascia: the
# crown's depth (m, from the pavement to the arch's top); cutwater: "point" or "round" prisms beyond the faces
# at every pier in the water, to `cut_top` of the arch's rise over the springing (bastions: to the pavement,
# with a parapet round them: the Pont Neuf's demi-lunes); parapet: [height, thickness, colour]; body: the
# spandrels' and soffits' colour, piers: the piers' and cutwaters' (iron arches on masonry piers)
BRIDGE_TYPES = {
    "stone": {"arch": "ellipse", "rise": 0.3, "pier_t": 0.15, "spring": 0.8, "fascia": 1.4, "cutwater": "point",
              "cut_top": 0.35, "parapet": [1.0, 0.5, "#c3b596"], "body": "#cbbd9f", "piers": "#c4b596"},
    "iron": {"arch": "segment", "rise": 0.11, "pier_t": 0.09, "spring": 1.2, "fascia": 1.0, "cutwater": "point",
             "cut_top": 0.6, "parapet": [1.0, 0.15, "#39403d"], "body": "#4b5652", "piers": "#c4b596"},
    "concrete": {"arch": "segment", "rise": 0.1, "pier_t": 0.1, "spring": 1.2, "fascia": 1.2, "cutwater": "point",
                 "cut_top": 0.5, "parapet": [1.0, 0.3, "#b3ada2"], "body": "#bdb6a8", "piers": "#bdb6a8"},
    "girder": {"arch": None, "pier_t": 0.06, "spring": 1.0, "fascia": 2.0, "cutwater": "round", "cut_top": 0.0,
               "parapet": [1.0, 0.15, "#39403d"], "body": "#58615d", "piers": "#c4b596"},
}
ARCH_SEG = 14                    # segments along one arch's curve


def bridge_type(entry):
    """[roads] piers entry -> (spans, fascia, type settings or None: the plain slab of old)."""
    if isinstance(entry, dict):
        t = dict(BRIDGE_TYPES[entry["type"]]) if "type" in entry else None
        if t is not None:
            t.update({k: v for k, v in entry.items() if k not in ("spans", "type")})
        return entry.get("spans", 0), (t or {}).get("fascia", entry.get("fascia", DECK_T)), t
    spans, fascia = (list(entry or [0, DECK_T]) + [DECK_T])[:2]
    t = None
    if entry and len(entry) > 2:
        t = dict(BRIDGE_TYPES[entry[2]])
        t["fascia"] = fascia
        if len(entry) > 3:
            t["rise"] = entry[3]
    return spans, fascia, t


def bridge_frame(poly):
    """A bridge outline's frame: centre (UTM), unit vectors along (u) and across (v), length, and the deck's
    width and offset along v, the medians of cross-sections at 20-80 % of its length (an outline that fans out
    over its abutments or stairs would make the bounding rectangle's width wider than the deck)."""
    rect = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
    ax, wide = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
    L, W = np.linalg.norm(ax), np.linalg.norm(wide)
    u, v = ax / L, wide / W
    c = rect.mean(0)
    ws, offs = [], []
    for f in np.linspace(-0.3, 0.3, 9):
        a = c + u * f * L
        cut = shapely.LineString([a - v * W, a + v * W]).intersection(poly)
        pts = shapely.get_coordinates(cut)
        if len(pts) >= 2:
            s = (pts - a) @ v
            ws.append(s.max() - s.min())
            offs.append((s.max() + s.min()) / 2)
    if ws:
        return c, u, v, L, float(np.median(ws)), float(np.median(offs))
    return c, u, v, L, W, 0.0


def segmentize_line(line, step):
    """A 3D LineString with a point at least every `step` m (z interpolated)."""
    cc = np.asarray(line.coords, float)
    out = [cc[0]]
    for a, b in zip(cc[:-1], cc[1:]):
        k = max(int(np.ceil(np.hypot(*(b[:2] - a[:2])) / step)), 1)
        out += [a + (b - a) * (j / k) for j in range(1, k + 1)]
    return LineString(np.asarray(out))


def arch_curve(kind, s, r, n=ARCH_SEG):
    """(x, y) along an arch of span s and rise r from springing to springing."""
    x = s / 2 - s / 2 * np.cos(np.linspace(0, np.pi, n + 1))            # denser near the springings
    if kind == "segment" and r < s / 2:
        R = (s * s / 4 + r * r) / (2 * r)
        y = np.sqrt(np.maximum(R * R - (x - s / 2) ** 2, 0)) - (R - r)
    else:                                                             # a half ellipse (semicircle at r = s/2)
        y = r * np.sqrt(np.clip(1 - ((x - s / 2) / (s / 2)) ** 2, 0, 1))
    return x, y


def arch_bridge(poly, span, top, spans, t, water, terrain: Terrain, origin, upper=None, prof=None) -> tuple[list, int]:
    """One typed bridge outline (see BRIDGE_TYPES): its elevation (a rectangle along the outline's axis from
    under the water to the pavement, less an arch opening per span over the water) extruded across the deck's
    width, cutwaters at the piers in the water, parapets along both sides, pylons, and for a two-level bridge
    columns from the pavement up to the ways of `upper` (their 3D lines, UTM) over it. prof: the deck profile
    (DeckField) the pavement follows, its lowest across the deck; None: level at `top`. Returns (meshes, piers)."""
    c, u, v, L, W, voff = bridge_frame(poly)
    # the pavement at s along the axis (P), a little under the slab's top
    P = ((lambda s_: (prof.along(c, u, s_, W / 2) - 0.02).reshape(np.shape(s_))) if prof is not None
         else (lambda s_: np.full(np.shape(s_), top - 0.02)))
    c = c + v * voff
    # the water along the axis: its level (the most common ground height there) and extent
    s_all = np.linspace(-L / 2, L / 2, 161)
    pts = c + np.outer(s_all, u)
    wet = shapely.contains_xy(water, pts[:, 0], pts[:, 1])
    if wet.sum() < 3:
        return [], 0
    hw = np.round(terrain.height_utm(pts[wet, 0], pts[wet, 1]), 1)
    vals, cnt = np.unique(hw, return_counts=True)
    wl = float(vals[np.argmax(cnt)])
    bed = min(wl, float(hw.min())) - 2.0
    w0, w1 = s_all[wet].min(), s_all[wet].max()
    # the arcade spans the water and reaches over the lower quays' walls, not the abutments on the upper quays
    reach = t.get("reach", 6.0)
    a0, a1 = max(w0 - reach, -L / 2 + 1.5), min(w1 + reach, L / 2 - 1.5)
    n = max(int(spans), 1)
    step = (a1 - a0) / n
    pier_t = max(2.0, t["pier_t"] * step) if n > 1 else 0.0
    s_top = np.linspace(-L / 2, L / 2, max(int(L), 1) + 1)
    y_top = P(s_top)
    if prof is not None:                                            # the profile's corners only (2 cm)
        s_top, y_top = np.asarray(LineString(np.column_stack([s_top, y_top])).simplify(0.02).coords).T
    ptop = float(P(np.linspace(a0, a1, 33)).min())                  # the lowest pavement over the arcade
    pier_u = [a0 + i * step for i in range(1, n)]
    edges = [a0] + pier_u + [a1]
    body_rgb, pier_rgb = srgb(t["body"])[0], srgb(t["piers"])[0]
    spring_y = wl + t["spring"]
    arch = t.get("arch")
    openings = []
    for i in range(n):
        o0 = edges[i] + (pier_t / 2 if i > 0 else 0.0)
        o1 = edges[i + 1] - (pier_t / 2 if i < n - 1 else 0.0)
        s = o1 - o0
        if s < 2:
            continue
        crown = float(P(np.linspace(o0, o1, 9)).min()) - t["fascia"]       # under the opening's lowest pavement
        if arch:
            r = min(t["rise"] * s, crown - spring_y)
            if r < 0.8:
                r, sy = 0.0, crown
            else:
                sy = crown - r
            x, y = arch_curve(arch, s, r) if r > 0 else (np.array([0.0, s]), np.zeros(2))
            ring = [(o0, bed - 1)] + list(zip(o0 + x, sy + y)) + [(o1, bed - 1)]
        else:                                                         # a girder: flat soffit
            ring = [(o0, bed - 1), (o0, crown), (o1, crown), (o1, bed - 1)]
        openings.append(Polygon(ring))
    elev = Polygon([(-L / 2, bed), (L / 2, bed)] + list(zip(s_top[::-1], y_top[::-1])))
    if openings:
        elev = elev.difference(unary_union(openings).buffer(0))
    # the spandrels above the springing in the body's colour, the piers below it in the piers'
    split = spring_y if arch else ptop - t["fascia"]
    parts_e = [(elev.intersection(box(-L, bed - 5, L, split)), pier_rgb),
               (elev.intersection(box(-L, split, L, float(y_top.max()) + 5)), body_rgb)]
    meshes = []
    vs = np.array([u[0], -u[1]])                                     # scene (x, z) of u
    ws = np.array([v[0], -v[1]])

    def world(uu, yy, vv):
        xy = c + np.outer(uu, u) + np.outer(vv, v)
        sc = to_scene(xy, origin)
        return np.column_stack([sc[:, 0], yy, sc[:, 1]])

    def add(pos, nrm, rgb, tri, paving=True):
        pos = np.asarray(pos, float)
        nrm = np.asarray(nrm, float)
        tri = orient(pos, np.asarray(tri, np.int64).reshape(-1, 3).copy(), nrm)
        col = np.tile(rgb, (len(pos), 1))
        if paving:
            col[nrm[:, 1] > 0.9] = PAVING                                  # the pavement (the rest is inside)
        meshes.append({"pos": pos, "nrm": nrm, "uv": pos[:, [0, 2]] * [1, -1], "col": col, "idx": tri.reshape(-1)})

    def slab(shape, va, vb, rgb, paving=True):
        """An elevation (polygon in (u, y)) extruded across from v = va to vb (va < vb)."""
        for p in polygons(shape):
            if p.area < 0.05:
                continue
            p = shapely.geometry.polygon.orient(p, 1.0)
            v2, tri = triangulate(p)
            for side, vv in ((-1, va), (1, vb)):                          # the two faces
                nn = np.tile([ws[0] * side, 0, ws[1] * side], (len(v2), 1))
                add(world(v2[:, 0], v2[:, 1], np.full(len(v2), vv)), nn, rgb, tri, paving)
            for ring in [p.exterior] + list(p.interiors):
                q = np.asarray(ring.coords)
                for a, b in zip(q[:-1], q[1:]):
                    d = b - a
                    ln = np.hypot(*d)
                    if ln < 1e-6:
                        continue
                    nu, ny = d[1] / ln, -d[0] / ln          # outward: right of the direction (solid on the left)
                    pos = world(np.array([a[0], b[0], b[0], a[0]]), np.array([a[1], b[1], b[1], a[1]]),
                                np.array([va, va, vb, vb]))
                    nrm = np.tile([vs[0] * nu, ny, vs[1] * nu], (4, 1))
                    add(pos, nrm, rgb, [0, 1, 2, 0, 2, 3], paving)

    for shape, rgb in parts_e:
        slab(shape, -W / 2, W / 2, rgb)

    def prism(pl_uv, y0, y1, rgb):
        """A vertical prism over a polygon given in (u, v), from y0 to y1."""
        pg = Polygon(c + np.outer(pl_uv[:, 0], u) + np.outer(pl_uv[:, 1], v))
        m = extrude(pg, y1 - y0, origin, rgb, ground=y0)
        if m is not None:
            meshes.append({**{k: m[k] for k in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]})

    # cutwaters, and bastions (to the pavement, with their own parapet)
    n_p = 0
    cut = t.get("cutwater")
    for pu in pier_u:
        at = c + u * pu
        if not water.contains(shapely.Point(*(at + v * (W / 2 + 1)))) and not water.contains(shapely.Point(*(at - v * (W / 2 + 1)))):
            continue
        n_p += 1
        if not cut:
            continue
        hw_ = pier_t / 2
        # the arch's rise next to this pier: the cutwater's cap
        p_here = float(P(pu))
        r_here = min(t.get("rise", 0) * step, p_here - t["fascia"] - spring_y) if arch else 0
        ytop = (p_here if t.get("bastions") else spring_y + t["cut_top"] * max(r_here, 0)) if arch else spring_y
        if t.get("bastions"):
            hw_ = pier_t / 2 + 1.0
        for side in (-1, 1):
            if cut == "round":
                ang = np.linspace(0, np.pi, 9)
                pl = np.column_stack([pu + hw_ * np.cos(ang), side * (W / 2 - 0.3 + hw_ * np.sin(ang))])
            else:
                pl = np.array([[pu - hw_, side * (W / 2 - 0.3)], [pu, side * (W / 2 + hw_ * 1.1)], [pu + hw_, side * (W / 2 - 0.3)]])
            prism(pl, bed, ytop, pier_rgb)
            if t.get("bastions") and t.get("parapet"):
                ph, pt, _ = t["parapet"]
                ang = np.linspace(0, np.pi, 9)
                outer = np.column_stack([pu + hw_ * np.cos(ang), side * (W / 2 - 0.3 + hw_ * np.sin(ang))])
                inner = np.column_stack([pu + (hw_ - pt) * np.cos(ang[::-1]), side * (W / 2 - 0.3 + (hw_ - pt) * np.sin(ang[::-1]))])
                prism(np.vstack([outer, inner]), p_here, p_here + ph, srgb(t["parapet"][2])[0])
    # parapets along both sides (open where a bastion's parapet takes over is not worth the triangles)
    if t.get("parapet"):
        ph, pt, pc = t["parapet"]
        # an elevation along the pavement's profile, extruded across the parapet's thickness
        band = Polygon(list(zip(s_top, y_top)) + list(zip(s_top[::-1], y_top[::-1] + ph)))
        for side in (-1, 1):
            vv0, vv1 = sorted((side * (W / 2 - pt), side * W / 2))
            slab(band, vv0, vv1, srgb(pc)[0], paving=False)
    # pylons at the four corners: [height, side, colour, top height, top colour] (the Pont Alexandre III's)
    if t.get("pylons"):
        ph, ps, pc, th, tc = t["pylons"]
        for pu in (a0 - ps / 2, a1 + ps / 2):
            ptop = float(P(pu))
            for sv in (-1, 1):
                pv = sv * (W / 2 + ps / 2 - 0.5)
                sq = lambda k: np.array([[pu - k, pv - k], [pu + k, pv - k], [pu + k, pv + k], [pu - k, pv + k]])
                prism(sq(ps / 2), bed, ptop + ph - th, srgb(pc)[0])
                prism(sq(ps / 3), ptop + ph - th, ptop + ph, srgb(tc)[0])
    # an arcade up to the upper deck ({upper, arcade = {bay, pier, wall, rise, colour}}: the Oberbaumbrücke's U1 on
    # its brick cloister): the upper ways' band across the bridge, walled along both its sides from the pavement to
    # the upper deck's soffit, each wall cut by arched openings every `bay` m (piers `pier` m wide, the arch's rise a
    # share `rise` of the opening's height), with cross walls at its ends
    if upper and t.get("arcade"):
        ac = {"bay": 5.0, "pier": 1.2, "wall": 0.9, "rise": 0.3, "colour": t["body"], **t["arcade"]}
        uu, vv, yy, ww = [], [], [], []
        widths = t.get("upper_w") or [None] * len(upper)
        for line, wd in zip(upper, widths):
            cc = np.asarray(segmentize_line(line, 4.0).coords)
            inside = shapely.contains_xy(poly, cc[:, 0], cc[:, 1])
            if inside.sum() < 2:
                continue
            d = cc[inside, :2] - c
            uu.append(d @ u); vv.append(d @ v); yy.append(cc[inside, 2] + ROAD_Y - DECK_T)
            ww.append(wd or 3.2)
        if uu:
            U, V, Y = np.concatenate(uu), np.concatenate(vv), np.concatenate(yy)
            half = max(ww) / 2
            v0, v1 = V.min() - half, V.max() + half
            u0, u1 = max(U.min(), -L / 2 + 0.5), min(U.max(), L / 2 - 0.5)
            order = np.argsort(U)
            ug = np.linspace(u0, u1, max(int((u1 - u0) / 2.0), 2) + 1)
            yg = np.interp(ug, U[order], Y[order])
            pg = P(ug)
            if (yg - pg).min() > 2.0:
                rgb = srgb(ac["colour"])[0]
                elev = Polygon(list(zip(ug, yg)) + list(zip(ug[::-1], pg[::-1] - 0.05)))
                nb = max(int(round((u1 - u0) / ac["bay"])), 1)
                bay = (u1 - u0) / nb
                ops = []
                for i in range(nb):
                    o0, o1 = u0 + i * bay + ac["pier"] / 2, u0 + (i + 1) * bay - ac["pier"] / 2
                    s_ = o1 - o0
                    if s_ < 1.0:
                        continue
                    p0 = float(P(np.linspace(o0, o1, 5)).max())
                    ht = float(np.interp((o0 + o1) / 2, ug, yg)) - p0 - 0.6     # a lintel 0.6 m deep at least
                    r = min(s_ / 2, ac["rise"] * ht)
                    sy = p0 + ht - r
                    x, y = arch_curve("ellipse", s_, r)
                    ops.append(Polygon([(o0, p0 - 3)] + list(zip(o0 + x, sy + y)) + [(o1, p0 - 3)]))
                walls = elev.difference(unary_union(ops).buffer(0)) if ops else elev
                wt = min(ac["wall"], (v1 - v0) / 3)
                slab(walls, v0, v0 + wt, rgb)
                slab(walls, v1 - wt, v1, rgb)
                # the end walls, across the band, closed under the deck
                for ue in (u0, u1):
                    ye = float(np.interp(ue, ug, yg))
                    pe = float(P(ue))
                    pg_ = Polygon(c + np.outer([v0, v1, v1, v0], v) + np.outer([ue - 0.5, ue - 0.5, ue + 0.5, ue + 0.5], u))
                    m = extrude(pg_, ye - pe, origin, rgb, ground=pe)
                    if m is not None:
                        meshes.append({**{k: m[k] for k in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]})
        upper = None
    # columns up to the upper deck (Bir-Hakeim's Métro viaduct on its cast-iron colonnettes)
    if upper:
        col_step, col_r, col_c = t.get("columns", [8.0, 0.45, "#4b5652"])
        for line in upper:
            cc = np.asarray(line.coords)
            seg = np.linalg.norm(np.diff(cc[:, :2], axis=0), axis=1)
            acc = np.r_[0, np.cumsum(seg)]
            for at in np.arange(col_step / 2, acc[-1], col_step):
                k = min(np.searchsorted(acc, at) - 1, len(seg) - 1)
                f = (at - acc[k]) / max(seg[k], 1e-9)
                xy = cc[k, :2] + f * (cc[k + 1, :2] - cc[k, :2])
                if not poly.contains(shapely.Point(*xy)):
                    continue
                y1 = cc[k, 2] + f * (cc[k + 1, 2] - cc[k, 2]) + ROAD_Y - DECK_T
                p_col = float(P((xy - c) @ u))
                if y1 - p_col < 2:
                    continue
                m = extrude(shapely.Point(*xy).buffer(col_r, 2), y1 - p_col, origin, srgb(col_c)[0], ground=p_col)
                if m is not None:
                    meshes.append({**{k_: m[k_] for k_ in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]})
    return meshes, n_p


OUTLINE_GAP = 0.1      # m: an outline's pavement under the deck tops of the ways over it
FIELD_STEP = 2.0       # m: the cells an outline's slab is cut into to follow its ways' decks
FIELD_RISE = 0.15      # m per m: how fast the slab may rise from a lower way's edge towards a higher one's
FOOT = {"footway", "steps", "path", "cycleway", "pedestrian", "bridleway"}


class DeckField:
    """The deck an outline is drawn at (scene y, ROAD_Y in, OUTLINE_GAP under the ways' deck tops), from the
    elevated ways over it: road ways (a railway bridge's tracks when there are none); footways only on a footbridge
    (no road over it) and where they run along it (not a stair down to the quay, nor a riverside walk under its
    ends): a road bridge's pavements mapped as footways, pinned lower at their ends than the road, sank the slab's
    corners round them (the Pont de Sully), and under the slab they are its pavement anyway. Not the ground roads
    continuing them over the outline's ends: the ground at a quay wall's foot can read metres under the deck's
    pinned end (Pont Marie: the slab sank 6 m over half its outline). At a point it is the
    lowest of each way's deck there (its height at the nearest point of its line) rising FIELD_RISE per metre
    beyond that way's edge, and never above the nearest way's deck: under every way the slab stays below its road,
    lane lines and crossings, also where a slip road leaves the bridge lower than the main carriageway. The flat
    slab of old stood at the median deck of its span's ways and covered them wherever they sloped below it (a
    humped bridge's ends, ramps, a carriageway of another name). u: the ways' main direction over the outline."""

    def __init__(self, lines, widths, c, u):
        self.lines, self.hw, self.c, self.u = lines, np.asarray(widths, float) / 2, c, u

    @classmethod
    def of(cls, poly, el):
        cand = el[el.intersects(poly)]
        road = cand[cand.kind != "rail"]
        cand = road if len(road) else cand
        zone = poly.buffer(1.0)
        got = []
        for line, w, hw in zip(cand.geometry, cand.width, cand.highway):
            if not line.has_z:
                continue
            cc = np.asarray(segmentize_line(line, 0.5).coords)
            inside = shapely.contains_xy(zone, cc[:, 0], cc[:, 1])
            seg = np.diff(cc[:, :2], axis=0)[inside[:-1] & inside[1:]]
            if np.linalg.norm(seg, axis=1).sum() < 2:
                continue
            got.append((line, float(w), hw, seg))
        if not got:
            return None
        # the ways' main direction: the principal axis of their segments over the outline (weighted by length)
        _, _, vt = np.linalg.svd(np.concatenate([g[3] for g in got]), full_matrices=False)
        u = vt[0] / np.linalg.norm(vt[0])
        if any(hw not in FOOT for _, _, hw, _ in got):
            got = [g for g in got if g[2] not in FOOT]
        keep = [(line, w) for line, w, hw, seg in got
                if hw not in FOOT or np.abs(seg @ u).sum() >= 0.6 * np.linalg.norm(seg, axis=1).sum()]
        if not keep:
            return None
        return cls([k[0] for k in keep], [k[1] for k in keep], np.asarray(poly.centroid.coords[0]), u)

    def at(self, xy):
        """The slab's top at UTM points (N, 2)."""
        xy = np.atleast_2d(np.asarray(xy, float))
        pts = shapely.points(xy)
        f = np.full((len(self.lines), len(xy)), np.inf)
        z = np.zeros_like(f)
        d = np.zeros_like(f)
        for i, line in enumerate(self.lines):
            d[i] = shapely.distance(line, pts)
            on = shapely.line_interpolate_point(line, shapely.line_locate_point(line, pts))
            z[i] = shapely.get_coordinates(on, include_z=True)[:, 2]
            f[i] = z[i] + FIELD_RISE * np.maximum(d[i] - self.hw[i], 0)
        y = np.minimum(f.min(0), z[d.argmin(0), np.arange(len(xy))])
        return y + ROAD_Y - OUTLINE_GAP

    def along(self, c, u, s, half, n=9):
        """Its lowest across a band `half` m either side of the line c + s u (an elevation's top)."""
        s = np.atleast_1d(np.asarray(s, float))
        v = np.array([-u[1], u[0]])
        off = np.linspace(-half, half, n)
        xy = c + s[:, None, None] * u + off[None, :, None] * v
        return self.at(xy.reshape(-1, 2)).reshape(len(s), n).min(1)


def profile_slab(poly, field, depth, origin) -> list:
    """An outline's slab on its DeckField: cut into FIELD_STEP cells along and across the ways' axis so its top
    follows the field, `depth` m thick; the pavement PAVING, the rest STONE."""
    c, u = field.c, field.u
    v = np.array([-u[1], u[0]])
    meshes = []

    def add(pos, nrm, rgb, tri):
        pos = np.asarray(pos, float)
        nrm = np.asarray(nrm, float)
        tri = orient(pos, np.asarray(tri, np.int64).reshape(-1, 3).copy(), nrm)
        meshes.append({"pos": pos, "nrm": nrm, "uv": pos[:, [0, 2]] * [1, -1],
                       "col": np.tile(rgb, (len(pos), 1)), "idx": tri.reshape(-1)})

    q = np.asarray(poly.exterior.coords)[:, :2] - c
    su, sv = q @ u, q @ v
    cells = []
    rect = lambda a, b, a1, b1: Polygon([c + u * a + v * b, c + u * a1 + v * b, c + u * a1 + v * b1, c + u * a + v * b1])
    bs = np.arange(sv.min(), sv.max() + FIELD_STEP, FIELD_STEP)
    for a in np.arange(su.min(), su.max(), FIELD_STEP):
        # a strip across the bridge, cut into cells only where the field varies across it (a slip road, two decks)
        ys = field.at(np.concatenate([c + u * a + np.outer(bs, v), c + u * (a + FIELD_STEP) + np.outer(bs, v)]))
        ys = ys.reshape(2, -1)
        if (ys.max(1) - ys.min(1)).max() < 0.03:
            cells.append(rect(a, bs[0], a + FIELD_STEP, bs[-1]))
        else:
            cells += [rect(a, b, a + FIELD_STEP, b + FIELD_STEP) for b in bs[:-1]]
    pieces = [p for g in shapely.intersection(poly, np.asarray(cells, dtype=object)) for p in polygons(g) if p.area > 0.01]
    tops = []
    for p in pieces:
        v2, tri = triangulate(p)
        tops.append((v2, tri))
    if tops:
        allv = np.concatenate([t[0] for t in tops])
        ally = field.at(allv)
        k = 0
        for v2, tri in tops:
            y = ally[k:k + len(v2)]
            k += len(v2)
            sc = to_scene(v2, origin)
            add(np.column_stack([sc[:, 0], y, sc[:, 1]]), np.tile([0, 1, 0], (len(v2), 1)), PAVING, tri)
            add(np.column_stack([sc[:, 0], y - depth, sc[:, 1]]), np.tile([0, -1, 0], (len(v2), 1)), STONE, tri)
    for ring in [poly.exterior] + list(poly.interiors):
        r = np.asarray(segmentize_line(LineString(np.asarray(ring.coords)[:, :2]), FIELD_STEP / 2).coords)[:, :2]
        out = 1 if ring.is_ccw == (ring is poly.exterior) else -1
        yr = field.at(r)
        sc = to_scene(r, origin)
        for i in range(len(r) - 1):
            d = r[i + 1] - r[i]
            ln = np.hypot(*d)
            if ln < 1e-6:
                continue
            n2 = np.array([d[1], -d[0]]) / ln * out
            pos = [[sc[i, 0], yr[i] - depth, sc[i, 1]], [sc[i + 1, 0], yr[i + 1] - depth, sc[i + 1, 1]],
                   [sc[i + 1, 0], yr[i + 1], sc[i + 1, 1]], [sc[i, 0], yr[i], sc[i, 1]]]
            add(pos, np.tile([n2[0], 0, -n2[1]], (4, 1)), STONE, [0, 1, 2, 0, 2, 3])
    return meshes


def outline_decks(origin, terrain: Terrain) -> dict:
    """[roads] bridge_outlines: each named bridge's man_made=bridge outline (05b_roads' roads.gpkg "outlines")
    as a slab, its top just under the ways' own decks and its fascia [roads] piers' depth (default DECK_T), and
    its piers: [roads] piers {span: [spans, fascia m]} gives spans - 1 piers evenly along the outline's long axis,
    those standing in the water kept, each across the whole deck with pointed cutwaters, from a metre under the
    river bed to the slab's underside. (tx, ty) -> merged mesh."""
    import pyogrio
    if not CFG["roads"].get("bridge_outlines") or "outlines" not in {l[0] for l in pyogrio.list_layers(DATA / "roads.gpkg")}:
        return {}
    o = gpd.read_file(DATA / "roads.gpkg", layer="outlines")
    if not len(o):
        return {}
    piers = CFG["roads"].get("piers", {})
    water = gpd.read_file(DATA / "ground.gpkg", layer="water").union_all()
    shapely.prepare(water)
    out, n_piers, n_typed = {}, 0, 0
    # a bridge drawn as several outlines (the Pont Neuf: one over each arm) shares its spans among them by length
    axis = o.geometry.apply(lambda p: max(np.linalg.norm(np.diff(np.asarray(p.minimum_rotated_rectangle.exterior.coords)[:3], axis=0), axis=1)))
    # (the parts of one multipolygon side by side, [roads] outline_parts: each its own group with all the spans)
    grp = o["group"].fillna(o.span) if "group" in o else o.span
    share = axis / axis.groupby(grp).transform("sum")
    # spans as a list: per outline, longest first (the Pont Neuf's 7 arches over the Seine's wide arm, 5 over the other)
    rank = axis.groupby(grp).rank(ascending=False, method="first").astype(int) - 1
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    el = ways[ways.elevated]
    n_prof = 0
    for poly, span, deck_y, sh, rk in zip(o.geometry, o.span, o.deck, share, rank):
        spans, fascia, typ = bridge_type(piers.get(span))
        if isinstance(spans, list):
            spans = spans[min(rk, len(spans) - 1)]
        else:
            spans = max(int(round(spans * sh)), 1) if spans else 0
        top = deck_y + ROAD_Y - OUTLINE_GAP
        # the slab's top follows the ways' decks over it (their lowest at each point along the bridge)
        prof = DeckField.of(poly, el)
        n_prof += prof is not None
        parts = []
        if typ is not None:
            upper = None
            if typ.get("upper"):
                sel = ways[(ways.span == typ["upper"]) & ways.intersects(poly)]
                upper = list(sel.geometry)
                typ = {**typ, "upper_w": list(sel.width.astype(float))}
            parts, n = arch_bridge(poly, span, top, spans, typ, water, terrain, origin, upper, prof)
            n_piers += n
            n_typed += bool(parts)
            spans = 0
        if not parts and prof is not None:
            for p in polygons(poly.simplify(0.3)):
                parts += profile_slab(p, prof, fascia, origin)
        if not parts:
            for p in polygons(poly.simplify(0.3)):
                m = extrude(p, fascia, origin, STONE, ground=top - fascia)
                if m is not None:
                    # the top is the pavement: darker than the stone
                    up = m["nrm"][:, 1] > 0.9
                    m["col"][up, :3] = PAVING
                    parts.append({**{k: m[k] for k in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]})
        if spans and spans > 1:
            # across the deck's own width (the outline's median cross-section), not its bounding rectangle's
            # (an outline fanning out over its abutments put the piers 25 % beyond the deck: Pont du Carrousel)
            c, u, v, L, W, voff = bridge_frame(poly)
            c = c + v * voff
            half = W / 2 - 0.2
            shape = np.array([[-PIER_T / 2, -half], [PIER_T / 2, -half], [PIER_T / 2, half], [0, half + CUTWATER],
                              [-PIER_T / 2, half], [-PIER_T / 2, -half], [0, -half - CUTWATER]])[[0, 6, 1, 2, 3, 4]]
            for i in range(1, int(spans)):
                at = c + u * (i * L / spans - L / 2)
                if not water.contains(shapely.Point(*at)):
                    continue
                pts = at + shape[:, :1] * u + shape[:, 1:] * v
                g = float(terrain.height_utm([at[0]], [at[1]])[0]) - 1.0
                y_top = top if prof is None else float(prof.at(at)[0])
                h = y_top - fascia - g
                if h < 1:
                    continue
                m = extrude(Polygon(pts), h, origin, STONE, ground=g)
                if m is not None:
                    parts.append({**{k: m[k] for k in ("pos", "nrm", "uv", "idx")}, "col": m["col"][:, :3]})
                    n_piers += 1
        if parts:
            ctr = poly.centroid
            key = (int(np.floor((ctr.x - origin[0]) / TILE)), int(np.floor((ctr.y - origin[1]) / TILE)))
            out.setdefault(key, []).extend(parts)
    print(f"bridge outlines: {len(o)} ({n_typed} as arcades of their type, {n_prof} on their ways' deck profile), "
          f"{n_piers} piers in the water")
    return {k: merge(v) for k, v in out.items()}


# ---------------------------------------------------------------- glb writer

def optimize(m: dict) -> dict:
    """Reorder triangles for the GPU's vertex cache and vertices by first use: better locality, and
    meshopt compression (07_pack.py) packs the result tighter."""
    idx = m["idx"].astype(np.uint32)
    n = len(m["pos"])
    tri = np.empty_like(idx)
    meshoptimizer.optimize_vertex_cache(tri, idx, len(idx), n)
    order = pd.unique(tri)                       # vertices in order of first use
    remap = np.empty(n, np.int64)
    remap[order] = np.arange(len(order))
    return {k: (remap[tri] if k == "idx" else v[order]) for k, v in m.items()}


def write_glb(path, meshes: dict, lattice=None, floats=()):
    """meshes: name -> arrays (pos[, nrm][, col][, uv, fac, base], idx). One node per mesh.

    Attributes are quantized (KHR_mesh_quantization): positions to POS_BITS-bit steps undone by the
    node's scale and translation, normals to int8, facade texture coordinates to uint16 normalized to 0..1 of
    the fixed ranges in UV_RANGE (the viewer multiplies them back). Only buildings carry texture
    coordinates; nothing samples a texture, so roads and ground don't need them.
    lattice: (origin xyz, step xyz) for every mesh instead: 16 bit per axis on that grid (the ground, whose
    extent is kilometres wide and a few hundred metres high); normals are stored multiplied by the step,
    so the node's non-uniform scale turns them back. floats: names of meshes kept as float positions.
    """
    blob, views, accessors, gl_meshes, nodes = bytearray(), [], [], [], []

    def add(arr, comp, typ, target=None, normalized=False, minmax=None, count=None):
        data = np.ascontiguousarray(arr).tobytes()
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target == 34962:
            view["byteStride"] = arr.shape[1] * arr.itemsize
        if target:
            view["target"] = target
        views.append(view)
        blob.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": count or len(arr), "type": typ}
        if normalized:
            acc["normalized"] = True
        if minmax is not None:
            acc["min"], acc["max"] = minmax
        accessors.append(acc)
        return len(accessors) - 1

    def unorm16(values, rng):
        return np.round(np.clip(values / rng, 0, 1) * 65535).astype(np.uint16)

    for name, m in meshes.items():
        m = optimize(m)
        n = len(m["pos"])
        if name in floats:
            lo, step = np.zeros(3), np.ones(3)
            p = m["pos"].astype(np.float32)
            attrs = {"POSITION": add(p, 5126, "VEC3", 34962, minmax=(p.min(0).tolist(), p.max(0).tolist()))}
        else:
            if lattice is not None:
                lo, step = (np.asarray(v, np.float64) for v in lattice)
            else:
                lo = m["pos"].min(0)
                step = np.full(3, max(float((m["pos"].max(0) - lo).max()) / (2 ** POS_BITS - 1), 1e-6))
            q = np.zeros((n, 4), np.uint16)                              # padded to 8 bytes a vertex
            q[:, :3] = np.clip(np.round((m["pos"] - lo) / step), 0, 65535)
            attrs = {"POSITION": add(q, 5123, "VEC3", 34962, minmax=(q[:, :3].min(0).tolist(), q[:, :3].max(0).tolist()))}
        if "nrm" in m:
            # under a non-uniform node scale three.js scales normals by its inverse: store them times the step
            nv = m["nrm"] * step
            nv /= np.maximum(np.linalg.norm(nv, axis=1, keepdims=True), 1e-12)
            nrm = np.zeros((n, 4), np.int8)
            nrm[:, :3] = np.round(nv * 127)
            attrs["NORMAL"] = add(nrm, 5120, "VEC3", 34962, normalized=True)
        if "col" in m:
            # RGBA8 (glTF vertex attributes must be 4-byte aligned); buildings keep their bay module in alpha
            col = m["col"] if m["col"].shape[1] == 4 else np.column_stack([m["col"], np.ones(n)])
            rgba = (col * 255).round().clip(0, 255).astype(np.uint8)
            attrs["COLOR_0"] = add(rgba, 5121, "VEC4", 34962, normalized=True)
        if name in ("bridge", "lattice") and "uv" in m and "fac" not in m:
            # the bridges' cables: (distance along, 50000 marking a main cable) for the necklace lights
            # (road decks carry their plan position, which never reaches the marker); a lattice's pattern
            # coordinates (structures.py: lattice_tower)
            attrs["TEXCOORD_0"] = add(np.ascontiguousarray(m["uv"], np.float32), 5126, "VEC2", 34962)
        if "fac" in m:
            for k, key in enumerate(("uv", "fac", "base")):
                attrs[f"TEXCOORD_{k}"] = add(unorm16(m[key], np.asarray(UV_RANGE[key])), 5123, "VEC2", 34962,
                                             normalized=True)
        ind = add(m["idx"].astype(np.uint16 if n < 65536 else np.uint32), 5123 if n < 65536 else 5125,
                  "SCALAR", 34963)
        # the viewer picks its material by this name
        gl_meshes.append({"name": name, "primitives": [{"attributes": attrs, "indices": ind,
                                                        "material": len(gl_meshes)}]})
        nodes.append({"mesh": len(nodes), "name": name, "translation": lo.tolist(), "scale": step.tolist()})

    while len(blob) % 4:
        blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": generator("06_tiles")},
            "extensionsUsed": ["KHR_mesh_quantization"], "extensionsRequired": ["KHR_mesh_quantization"],
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes,
            "meshes": gl_meshes, "materials": [{"name": m["name"]} for m in gl_meshes],
            "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942)); f.write(bytes(blob))


# [tiles] river = {min_km2, share, land, pontoon_h, keep}: footprints over `share` inside a big water body (at least
# min_km2: the tidal Thames, not the docks with their floating restaurants) and on no deck (min_h 0): clipped to
# the land where at least `land` of them (and 15 m²) lies on it, else (a pontoon, a pier's house, a moored boat)
# kept as a plain low box of at most pontoon_h m, unless their OSM building tag is in `keep` (Blackfriars' old
# bridge columns). London M3 critic: a mansard block sunk in the river at Wapping, pale slabs out of the bank
RIVER = T.get("river", {})


def river_buildings(b: gpd.GeoDataFrame) -> np.ndarray:
    """[tiles] river: clips and pontoons in place; the pontoons' mask (their facade becomes plain)."""
    pontoon = np.zeros(len(b), bool)
    if not RIVER:
        return pontoon
    w = gpd.read_file(DATA / "ground.gpkg", layer="water")
    big = w[w.area >= float(RIVER.get("min_km2", 1.0)) * 1e6].union_all()
    hit = b.index[b.intersects(big) & (b["min_h"].fillna(0) <= 0)]
    if not len(hit):
        return pontoon
    sub = b.loc[hit]
    share = sub.intersection(big).area / sub.area
    sub = sub[share > float(RIVER.get("share", 0.2))]
    land = sub.difference(big)
    keep_tags = set(RIVER.get("keep", []))
    n_clip = n_pont = 0
    for i, g, la in zip(sub.index, sub.geometry, land):
        if la.area >= max(float(RIVER.get("land", 0.2)) * g.area, 15.0):
            pieces = [p for p in polygons(la) if p.area >= 4]
            if pieces:
                b.at[i, "geometry"] = max(pieces, key=lambda p: p.area) if len(pieces) == 1 else shapely.MultiPolygon(pieces)
                n_clip += 1
                continue
        if str(b.at[i, "osm_building"]) in keep_tags:
            continue
        b.at[i, "h"] = min(float(b.at[i, "h"]), float(RIVER.get("pontoon_h", 4.5)))
        pontoon[b.index.get_loc(i)] = True
        n_pont += 1
    print(f"river: {n_clip} footprints clipped to the bank, {n_pont} kept as low pontoons "
          f"(of {len(sub)} over {RIVER.get('share', 0.2):.0%} in the water)")
    return pontoon


def prepared_buildings(ways: gpd.GeoDataFrame, origin) -> tuple:
    """The building table as this stage builds it (simplified, cleared of roads, tile keys, styles and seeds,
    landmark parts grounded, roof shapes, the ground under each) and the Terrain: shared with 06c_rooftops."""
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    # flat footprints: a piece with Z (cut from 3D source polygons) gives earcut (N, 3) vertices and stops the stage
    b["geometry"] = shapely.force_2d(b.geometry.make_valid().values)
    big = b.area >= 20                              # (small pieces, spires, keep their shape)
    b.loc[big, "geometry"] = b.loc[big].geometry.simplify(SIMPLIFY)
    if "min_h" not in b:
        b["min_h"] = 0.0
    b["min_h"] = b["min_h"].fillna(0.0)
    pontoon = pd.Series(river_buildings(b), index=b.index)
    b = road_clearance(b, ways)
    c = b.geometry.centroid
    b["tx"] = np.floor((c.x - origin[0]) / TILE).astype(int)
    b["ty"] = np.floor((c.y - origin[1]) / TILE).astype(int)
    building_styles(b)
    if pontoon.any():
        b.loc[pontoon.reindex(b.index, fill_value=False), "facade"] = "plain"
    grounded(b)
    print(b["facade"].value_counts().to_string())
    b["roof_h"], b["roof_d"], b["roof_code"] = roof_shapes(b)
    terrain = Terrain()
    b["ground"] = terrain.bases(b.geometry.values)
    print(f"buildings on the ground: base up to {b.ground.max():.0f} m, {(b.ground > 0).mean():.0%} above 0")
    return b, terrain


# ---------------------------------------------------------------- main

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.glb"):
        if not f.name.startswith("m_"):         # 06e_masses' cells are its own
            f.unlink()
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)

    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    b, terrain = prepared_buildings(ways, origin)

    road = ground_roads(ways, origin, terrain)
    bridge = bridges(ways[ways.elevated], origin, terrain)
    for k, m in outline_decks(origin, terrain).items():
        bridge[k] = merge(([bridge[k]] if k in bridge else []) + [m])
    # [[structures]]: bridge towers and cables, statues (stages/structures.py)
    from . import structures
    key = lambda xy: (int(np.floor((xy[0] - origin[0]) / TILE)), int(np.floor((xy[1] - origin[1]) / TILE)))
    solids, cables, lattices = structures.build(origin, terrain, extrude, STYLE_ID, srgb, to_scene)
    lattice_at = {}
    for xy, m in lattices:
        lattice_at.setdefault(key(xy), []).append(m)
    lattice_at = {k: merge(ms) for k, ms in lattice_at.items()}
    solid_at = {}
    for xy, m in solids:
        if m is not None:
            m["idx"] = orient(m["pos"], m["idx"].reshape(-1, 3), m["nrm"]).reshape(-1)
            solid_at.setdefault(key(xy), []).append(m)
    cable_at = {}
    for xy, m in cables:
        m["idx"] = orient(m["pos"], m["idx"].reshape(-1, 3), m["nrm"]).reshape(-1)
        cable_at.setdefault(key(xy), []).append(m)
    for k, ms in cable_at.items():
        bridge[k] = merge(([bridge[k]] if k in bridge else []) + ms)

    party = party_walls(b)
    exact = (b["h_exact"].fillna(False).astype(bool).to_dict() if SMALL_EXACT and "h_exact" in b else {})
    by_tile = dict(iter(b.groupby(["tx", "ty"])))
    tiles, tris_b, tris_r = [], 0, 0
    for tx, ty in sorted(set(by_tile) | set(road) | set(bridge) | set(solid_at) | set(lattice_at)):
        meshes, g = {}, by_tile.get((tx, ty))
        if g is not None or (tx, ty) in solid_at:
            parts = list(solid_at.get((tx, ty), []))
        if g is not None:
            for bi, geom, h, style, seed, tint, module, profile, gy, mh, rh, rd, rc in zip(
                    g.index, g.geometry, g.h, g.facade, g.seed, g.tint, g.module, g.profile, g.ground, g.min_h,
                    g.roof_h, g.roof_d, g.roof_code):
                st = STYLES[style]
                tiny = 0.2 if (h >= 60 or (SMALL_EXACT and exact.get(bi, False))) else 4
                rgb = tint if tint is not None else st["palette"][int(seed * 997) % len(st["palette"])]
                for poly in polygons(geom):
                    if poly.area < tiny:       # a tower's spire may be a metre across, a memorial's stele 2.4 m²
                        continue
                    # a roof shape: the walls to the eaves, the roof leaning in from the free walls
                    free, prof = None, profile
                    if rh > 0 and profile is None:
                        eaves = float(h) - rh
                        prof = [(0.0, 1.0, 0.0), ((eaves - mh) / max(float(h) - mh, 0.1), 1.0, 0.0), (1.0, 1.0, float(rd))]
                        free = (lambda pts, _i=bi, _e=eaves: party(pts, _i, _e))
                    # min_h: standing on another building's roof
                    parts.append(extrude(poly, float(h), origin, rgb, (STYLE_ID[style], seed), base=float(mh),
                                         module=float(module), profile=prof, ground=float(gy), skirt=SKIRT,
                                         free=free, roof_code=float(rc)))
                    if (h >= PLANT_MIN_H and poly.area >= PLANT_MIN_AREA and tint is None
                            and style != "factory" and rh == 0):
                        room = plant_room(poly)
                        if room is not None:
                            parts.append(extrude(room, float(h) + PLANT_H, origin, STYLES["plain"]["palette"][0],
                                                 (STYLE_ID["plain"], seed), base=float(h), ground=float(gy)))
        if g is not None or (tx, ty) in solid_at:
            parts = [p for p in parts if p is not None]
            if parts:
                meshes["buildings"] = merge(parts)
                tris_b += len(meshes["buildings"]["idx"]) // 3
        for name, src in (("road", road), ("bridge", bridge), ("lattice", lattice_at)):
            if (tx, ty) in src:
                meshes[name] = src[(tx, ty)]
                tris_r += len(src[(tx, ty)]["idx"]) // 3
        if not meshes:
            continue
        name = f"t_{tx}_{ty}.glb"
        write_glb(OUT / name, meshes)
        top = max([float((g.ground + g.h).max())] if g is not None else [0.0])
        for k in ("bridge", "lattice", "buildings"):     # (structures stand over their tile's buildings)
            if k in meshes and (k != "buildings" or (tx, ty) in solid_at):
                top = max(top, float(meshes[k]["pos"][:, 1].max()))
        tiles.append({"file": name, "x": tx * TILE, "z": -(ty + 1) * TILE, "size": TILE,
                      "buildings": 0 if g is None else len(g),
                      "triangles": sum(len(m["idx"]) // 3 for m in meshes.values()), "maxHeight": top})

    # ground: the layers draped over the TIN, on one lattice; the backdrop beyond them; the TIN itself
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    ax0, ay0, ax1, ay1 = area.bounds
    lo = np.array([ax0 - origin[0] - 10, -2.0, -(ay1 - origin[1]) - 10])
    hi = np.array([ax1 - origin[0] + 10, terrain.y.max() + 2, -(ay0 - origin[1]) + 10])
    lattice = (lo, (hi - lo) / 65535)
    ground, tris_g = {}, 0
    district = boundary().geometry.union_all() if TOWN else None
    if TOWN:
        # airfields stay plain land: the grass between runways is no roofscape (05_ground's aerodrome layer)
        try:
            fields = gpd.read_file(DATA / "ground.gpkg", layer="aerodrome").geometry
            district = unary_union([district, *fields.make_valid()])
        except Exception:             # a ground.gpkg from before the layer existed
            pass
        # ...except their terminals, garages and hangars outside the districts: roofs, not lawn
        try:
            ab = gpd.read_file(DATA / "ground.gpkg", layer="aerodrome_buildings").geometry.make_valid()
            ab = unary_union(list(ab)).buffer(2).difference(boundary().geometry.union_all())
            district = district.difference(ab)
        except Exception:
            ab = None
    import pyogrio
    have = {n for n, _ in pyogrio.list_layers(DATA / "ground.gpkg")}
    for layer in ("land", "town", "mud", "green", "gravel", "paved", "asphalt", "water", "aeroway"):
        if layer == "town" and not TOWN or layer in ("gravel", "paved", "asphalt") and layer not in have:
            continue
        g = gpd.read_file(DATA / "ground.gpkg", layer="land" if layer == "town" else layer)
        if not len(g):
            continue
        # overlapping polygons merged (they would be drawn twice, and cut twice), outlines to GROUND_SIMPLIFY
        geom = unary_union([p for geom in g.geometry for p in polygons(geom) if p.area > 50]).simplify(GROUND_SIMPLIFY)
        if TOWN and layer in ("land", "town"):
            # [ground] town: the land beyond the districts is the town layer (a painted roofscape)
            geom = geom.intersection(district) if layer == "land" else geom.difference(district)
        if TOWN and layer == "green":
            # beyond the roads (cut [roads] margin outside the districts) the verges and medians of highways
            # that aren't drawn read as stray green wedges over the painted town: thin strips go, parks stay
            roads_end = boundary().geometry.union_all().buffer(CFG["roads"]["margin"])
            keep = [p for p in polygons(geom)
                    if p.intersection(roads_end).area > 0.5 * p.area or p.area / max(p.length, 1) ** 2 * 16 > 0.2
                    or p.area > 50000]
            print(f"green: {len(polygons(geom)) - len(keep)} thin strips beyond the roads left out")
            # airfields: their grass (runways, taxiways and aprons are drawn over it)
            try:
                fields = gpd.read_file(DATA / "ground.gpkg", layer="aerodrome").geometry.make_valid()
                land = unary_union(list(gpd.read_file(DATA / "ground.gpkg", layer="land").geometry))
                grass = unary_union(list(fields)).intersection(land)
                if ab is not None:
                    grass = grass.difference(ab)
                keep += polygons(grass.simplify(GROUND_SIMPLIFY))
            except Exception:
                pass
            geom = unary_union(keep)
        flat_parts = []
        if layer == "water" and CFG["terrain"].get("quay_walls"):
            # [terrain] quay_walls drops the ground along quays under the water: a levelled body is drawn flat
            # at its level (it would dip into that trench along every wall), which also saves draping it
            rows = [shapely.make_valid(r) for r in g.geometry]
            lv = water_levels(rows, terrain)
            done = []
            for r, v in zip(rows, lv):
                if not np.isfinite(v):
                    continue
                piece = geom.intersection(r)
                for q in polygons(piece) if not piece.is_empty else []:
                    sq = shapely.transform(q, lambda c: to_scene(c, origin))
                    for v2, y, nrm, tri in _flat_pieces(sq, v):
                        pos = np.column_stack([v2[:, 0], y, v2[:, 1]])
                        flat_parts.append({"pos": pos, "nrm": nrm, "idx": orient(pos, tri.copy(), nrm).reshape(-1)})
                done.append(r)
            if done:
                geom = geom.difference(unary_union(done))
            print(f"water: {len(done)} levelled bodies drawn flat at their level", flush=True)
        parts = [draped(p, 0.0, origin, terrain) for p in polygons(geom)] + flat_parts
        parts = [p for p in parts if p is not None]
        if parts:
            # pieces of one polygon cut along the TIN share their vertices again (the viewer's water finds
            # rivers and ponds as connected pieces of the mesh)
            ground[layer] = weld(merge(parts))
            tris_g += len(ground[layer]["idx"]) // 3
            print(f"ground {layer}: {len(ground[layer]['idx']) // 3:,} triangles", flush=True)
    land_all = unary_union(list(gpd.read_file(DATA / "ground.gpkg", layer="land").geometry.make_valid()))
    ground["backdrop"] = backdrop_mesh(terrain, (ax0 - origin[0], -(ay1 - origin[1]), ax1 - origin[0],
                                                 -(ay0 - origin[1])), lattice, origin, land_all)
    write_glb(OUT / "ground.glb", ground, lattice=lattice, floats=("backdrop",))
    write_glb(OUT / "terrain.glb", {"terrain": {"pos": np.column_stack([terrain.xz[:, 0], terrain.y, terrain.xz[:, 1]]),
                                                "idx": terrain.tri.reshape(-1)}},
              lattice=((terrain.xz[:, 0].min(), 0.0, terrain.xz[:, 1].min()), (terrain.cell, TERRAIN_Q, terrain.cell)))

    views = camera_views(b, origin, terrain)
    index = {
        "origin": {"utm_epsg": UTM_EPSG, "easting": origin[0], "northing": origin[1]},
        "tileSize": TILE,
        "extent": {"xmin": ax0 - origin[0], "xmax": ax1 - origin[0],
                   "zmin": -(ay1 - origin[1]), "zmax": -(ay0 - origin[1])},
        "ground": "ground.glb",
        "terrain": "terrain.glb",
        "views": views,
        **({"town": {"rgb": CFG["terrain"]["backdrop_town_rgb"]}} if TOWN else {}),
        "styles": list(STYLES),
        "uvRange": UV_RANGE,
        "floor": [v["floor"] for v in STYLES.values()],
        "moduleMax": MODULE_MAX,
        "tiles": tiles,
    }
    (OUT / "tiles.json").write_text(json.dumps(index, indent=1))
    if CFG["ground"]["masses"] or CFG["terrain"].get("backdrop_cover"):
        from .masses import add_to_index           # 06e_masses' town masses (their last build) stay in the index
        add_to_index(OUT / "tiles.json")
    size = sum(f.stat().st_size for f in OUT.glob("*.glb")) / 1e6
    print(f"{len(tiles)} tiles, {tris_b:,} building, {tris_r:,} road and {tris_g:,} ground triangles "
          f"(backdrop {len(ground['backdrop']['idx']) // 3:,}), {size:.0f} MB of glb "
          f"(ground {(OUT / 'ground.glb').stat().st_size / 1e6:.1f} MB)")


def backdrop_mesh(terrain: Terrain, rect, lattice, origin=None, land=None) -> dict:
    """05a_terrain.py's backdrop: positions, smooth normals, colours (linear); the vertices on the ground
    area's outline are put on the ground's lattice, exactly where the ground layers' edge vertices land.
    With the ground's land (UTM), triangles between the sea and edge vertices that lie on the water are left
    out: they drew a land-coloured strip over the water all along the edge."""
    d = terrain.backdrop
    pos = d["back_xyz"].astype(np.float64)
    tri = d["back_tri"].astype(np.int64)
    x0, z0, x1, z1 = rect
    lo, step = lattice
    edge = (np.isclose(pos[:, 0], x0) | np.isclose(pos[:, 0], x1)) & (pos[:, 2] >= z0 - 1e-6) & (pos[:, 2] <= z1 + 1e-6) | \
           (np.isclose(pos[:, 2], z0) | np.isclose(pos[:, 2], z1)) & (pos[:, 0] >= x0 - 1e-6) & (pos[:, 0] <= x1 + 1e-6)
    if land is not None:
        wet = pos[:, 1] < -1.0                               # under the sea plane
        on_edge = np.flatnonzero(edge)
        dry = shapely.contains_xy(land.buffer(20), pos[on_edge, 0] + origin[0], origin[1] - pos[on_edge, 2])
        wet[on_edge[~dry]] = True
        keep = ~wet[tri].all(1)
        print(f"backdrop: {int((~keep).sum()):,} triangles over the water at the edge left out")
        tri = tri[keep]
    pos[edge] = lo + np.round((pos[edge] - lo) / step) * step
    n = np.cross(pos[tri[:, 2]] - pos[tri[:, 0]], pos[tri[:, 1]] - pos[tri[:, 0]])
    n *= np.sign(n[:, 1:2] + 1e-12)
    vn = np.zeros_like(pos)
    for k in range(3):
        np.add.at(vn, tri[:, k], n)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    c = d["back_rgb"] / 255
    col = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return {"pos": pos, "nrm": vn, "col": col, "idx": orient(pos, tri, vn).reshape(-1)}


def views_only():
    """Refresh the camera presets in tiles.json (raw and packed) without rebuilding any tile."""
    x0, y0, x1, y1 = boundary().total_bounds
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    views = camera_views(b, ((x0 + x1) / 2, (y0 + y1) / 2), Terrain())
    for f in (OUT / "tiles.json", DATA / "tiles" / "tiles.json"):
        index = json.loads(f.read_text())
        index["views"] = views
        f.write_text(json.dumps(index, indent=1))
    print(f"{len(views)} views")


def run(argv):
    views_only() if "--views-only" in argv else main()
