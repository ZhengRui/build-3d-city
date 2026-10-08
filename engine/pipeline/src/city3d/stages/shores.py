"""05e_shores: shorelines for the viewer: seawalls, rock revetments, quays, beaches, mudflats, river embankments,
pond banks and swimming pools, as strips along the edges of the ground layers.

The ground layers (05_ground.py, drawn flat by 06_tiles.py) meet the water in a hard cut: land lies on
the sea like a sheet of card. Almost none of Shenzhen's coast is natural. Most of it is reclaimed land
held by sloping rock revetments (riprap) with a promenade on top (Shenzhen Bay Park, Qianhai, the
airport), the ports have vertical concrete quays (Shekou, Chiwan, Mawan, Dachan Bay), the mangroves
(Futian, Xiwan) stand on mudflats, and there are a few sand beaches. Rivers and canals run between
concrete embankments; park ponds have soft banks of stones, mud and grass. None of this is mapped as
geometry, so it is inferred:

  coast   the boundary of the visible land (land, green and aeroway layers minus inland water) where
          the sea lies beyond it, typed by what OSM has nearby: natural=beach -> beach; mangrove,
          tidal flat, mud or other wetland -> mudflat; landuse=port, man_made=quay/pier, harbour
          industry -> quay; otherwise [shores] coast_type (Shenzhen: a revetment). Where the ground's mud layer (intertidal flats,
          drawn at -0.5 m between the land and the sea) lies beyond it instead, a low muddy bank
          down onto the flat, with nothing over the water (mudbank)
  mud     the seaward edge of the mud layer: exposed mud in lobes between channels, fraying out
          into the sea (mudedge, only the blended band over the water)
  banks   the boundary of the visible land where inland water lies beyond it, typed by the water
          feature it belongs to: rivers, canals, drains and basins -> concrete embankment; ponds,
          lakes and reservoirs -> soft bank where the land beside them is green (parks), a stone
          edge where it is paved (plazas, office parks such as Wutong Island)
  pools   leisure=swimming_pool polygons (not in the ground layers at all)

Each edge becomes bands of quads across it (across = metres from the edge, positive towards the water;
along = metres along it), each band a few metres wide: the land-side band (promenade, quay apron,
dry sand, coping) flat just above the ground layers, the slope or wall down to the water line, and a
toe band over the water (submerged rocks, wet shadow, swash, mud) that the viewer draws blended.
Normals are shading normals: the revetment slope is shaded as a 1:2 slope although the geometry only
drops from the land's 0.75 m to the sea's -1 m (the viewer's sea plane).

Per vertex: POSITION (scene metres, float), NORMAL (int8, KHR_mesh_quantization), TEXCOORD_0 (across, along) in metres (along
restarts every ALONG_WRAP m to keep float precision), COLOR_0 RGBA8: r = shore type (TYPES), g = band
(0 land side, 1 slope/wall, 2 toe), b = a random value per run, a = 255.

An inland city has no coast edges (its land is the whole ground area): only banks and pools.

Writes shores_raw/shores.glb in the data folder and, meshopt-compressed with 07_pack.py's encoder,
shores/shores.glb + shores.json; the viewer's web/shores links to the latter. Tags come from Overpass once,
cached in raw/osm_shores.json.
"""
import itertools
import json
import struct
from collections import Counter

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from ..common import CFG, DATA, RAW, UTM, Terrain, boundary, element_geoms, generator, link_web, overpass, weld
from . import pack as pack07
from . import tiles as tiles06

to_scene = tiles06.to_scene

OUT_RAW = DATA / "shores_raw"
OUT = DATA / "shores"
CACHE = RAW / "osm_shores.json"

TYPES = ["revetment", "quay", "beach", "mudflat", "embankment", "pondbank", "pool", "pondedge", "quaywall"]
T = {n: i for i, n in enumerate(TYPES)}
# band sets drawn with the mudflat shading: a bank down onto the mud layer, the mud layer's sea edge
T["mudbank"] = T["mudedge"] = T["mudflat"]

# heights (metres above the ground, see Mesh; the sea side absolute): the viewer draws land at 0, green 0.6,
# inland water 0.9, aeroway 1.2, roads 1.5 over it and the sea plane at -1 (web/main.js LAYER_Y, 06_tiles.py ROAD_Y)
SEA_Y = -1.0
MUD_Y = -0.5                # the ground's mud layer (web/main.js LAYER_Y)
COAST_TOP = 0.75            # coast bands over land and green, under roads
TOE_SEA = -0.96             # blended band over the sea (drawn without depth, anything covers it)
BANK_TOP = 1.3              # bank bands over land, green and the water's edge, under roads
BANK_FOOT = 1.02            # foot of a bank, just above the inland water
POOL_Y = 1.05

# Bands per type: (across start, across end, y start, y end, shading slope in degrees towards the water).
# across < 0 is on the land. The toe band (last) is drawn blended over the water.
BANDS = {
    "revetment": [(-4.0, 0.0, COAST_TOP, COAST_TOP, 0), (0.0, 5.0, COAST_TOP, SEA_Y, 27),
                  (5.0, 13.0, TOE_SEA, TOE_SEA, 0)],
    "quay": [(-7.0, 0.0, COAST_TOP, COAST_TOP, 0), (0.0, 0.08, COAST_TOP, SEA_Y, 88),
             (0.08, 4.0, TOE_SEA, TOE_SEA, 0)],
    "beach": [(-16.0, 0.0, COAST_TOP, COAST_TOP, 0), (0.0, 14.0, COAST_TOP, SEA_Y, 5),
              (14.0, 26.0, TOE_SEA, TOE_SEA, 0)],
    "mudflat": [(-3.0, 0.0, COAST_TOP, COAST_TOP, 0), (0.0, 4.0, COAST_TOP, SEA_Y, 8),
                (4.0, 70.0, TOE_SEA, TOE_SEA, 0)],
    "embankment": [(-1.4, 0.0, BANK_TOP, BANK_TOP, 0), (0.0, 1.6, BANK_TOP, BANK_FOOT, 62),
                   (1.6, 4.5, BANK_FOOT, BANK_FOOT, 0)],
    "pondbank": [(-1.8, 0.0, BANK_TOP, BANK_TOP, 0), (0.0, 1.4, BANK_TOP, BANK_FOOT, 20),
                 (1.4, 5.0, BANK_FOOT, BANK_FOOT, 0)],
    "pondedge": [(-0.9, 0.0, BANK_TOP, BANK_TOP, 0), (0.0, 0.35, BANK_TOP, BANK_FOOT, 70),
                 (0.35, 3.0, BANK_FOOT, BANK_FOOT, 0)],
    "pool": [(-0.6, 0.0, POOL_Y + 0.05, POOL_Y + 0.05, 0)],
    # ends just above the mud layer, so nothing lies under it to show through far away
    "mudbank": [(-3.0, 0.0, COAST_TOP, COAST_TOP, 0), (0.0, 3.0, COAST_TOP, MUD_Y + 0.05, 14)],
    "mudedge": [(0.0, 60.0, TOE_SEA, TOE_SEA, 0)],
}
# [shores] bands / water_side (opt-in, default the table above byte for byte). `bands = { beach = [[a0, a1, y0, y1,
# slope(, u0, u1)], ...] }` replaces a type's bands (y: metres, or one of the names in BAND_Y; u0, u1: the across
# coordinate the shader reads, default a0, a1: web/shores.js shades the beach by across in metres, wet sand over 2-12 m,
# the swash lines at 14-26, so a band moved closer in keeps the u of the original to be shaded the same, squeezed).
# `water_side = { beach = 4.0 }` keeps a type's land side and fits everything seaward of the edge (the bands from
# across 0 on, the toe over the water included) into that many metres, the u unchanged: the sand's seaward feather of
# 14 + 12 m (Sentosa's beaches glowed 10-20 m into the water) becomes a few metres of the same shading, squeezed
BAND_Y = {"coast_top": COAST_TOP, "sea": SEA_Y, "toe_sea": TOE_SEA, "mud": MUD_Y + 0.05, "bank_top": BANK_TOP,
          "bank_foot": BANK_FOOT, "pool": POOL_Y + 0.05}
# the band number stored per band (0 land side, 1 slope or wall, 2 over the water), where not the index
BAND_IDS = {"mudedge": [2]}
MITER_MAX = 2.0             # longest offset at a sharp corner, in band widths
ALONG_WRAP = 4096.0         # along restarts here (the shader's patterns repeat within it)
SIMPLIFY = 0.6              # metres
MIN_RUN = 12.0              # shorter runs of one kind are merged into their neighbours
DETAIL_MARGIN = CFG["shores"]["detail_margin"]   # banks and pools only within the districts plus this (m); the coast everywhere
COAST_TYPE = CFG["shores"]["coast_type"]         # coast without a tagged feature nearby
# banks of rivers and canals (inland): "embankment" (concrete wall, streaked) by default; "pondedge" (granite
# coping in blocks and a short stone face) for masonry quays such as Paris's (the wall itself is the terrain's)
BANK_TYPE = CFG["shores"].get("bank_type", "embankment")
assert BANK_TYPE in ("embankment", "pondedge", "pondbank"), f"[shores] bank_type {BANK_TYPE}: embankment, pondedge or pondbank"
MUDFLAT = [tuple(kv.split("=", 1)) for kv in CFG["shores"]["mudflat"]]   # tags that make a mudflat coast
MUDFLAT_MIN = CFG["shores"].get("mudflat_min_area", 0.0)   # m²: smaller ones (a pocket marsh by a pier) don't
# river quays (05a_terrain quay_walls): a vertical masonry wall at the water's outline, from under the water to
# the quay, with a flat stone apron QUAY_APRON m inland over the TIN's step and its face QUAY_FACE m out in the water
# a closed coast loop (an islet, the tip of a breakwater drawn as land) no longer than this across (m), typed beach by the
# beach feature within 40 m of it, takes ISLET_TYPE instead: 16 m of sand land side covered the whole islet, a glowing blob
# (Singapore's breakwater islets off East Coast Park, Palawan's); 0 = off (today)
ISLET_MAX = CFG["shores"].get("islet_max", 0.0)
ISLET_TYPE = CFG["shores"].get("islet_type", "revetment")
assert ISLET_TYPE in TYPES[:4], f"[shores] islet_type {ISLET_TYPE}: revetment, quay, beach or mudflat"
SHORE_BANDS = CFG["shores"].get("bands", {})
WATER_SIDE = CFG["shores"].get("water_side", {})
QUAY_WALLS = CFG["shores"].get("quay_walls", False)
# [shores] pond_edge_area (opt-in, Singapore M5 fix round; km², 0 = off): lakes and reservoirs at least this large get the
# stone edge (granite coping and a short stone face) all round, also where a park's lawn meets them: Marina Bay (OSM's
# Marina Reservoir) is walled by granite promenades, not the park pond's boulders on mud (Merlion Park, the Esplanade)
POND_EDGE_AREA = CFG["shores"].get("pond_edge_area", 0.0)
# the apron's height: the highest ground within QUAY_TOP m of the wall (the TIN's quay cell), not across the whole
# apron (a step up to an upper quay or a bridge's abutment behind a lower quay, within the apron's width, lifted
# the apron to it and ramped it along the run: the Square du Vert-Galant's "concrete wedge"); runs are cut into
# pieces of at most QUAY_STEP m so their height follows the ground
QUAY_TOP, QUAY_STEP = CFG["shores"].get("quay_top", 5.0), CFG["shores"].get("quay_step", 4.0)
QUAY_APRON, QUAY_FACE = CFG["shores"].get("quay_apron", 8.0), CFG["shores"].get("quay_face", 1.5)
QUAY_MIN = CFG["terrain"].get("quay_min", 1.0)
WATER_Y = 0.9               # the viewer lifts inland water this far over the ground (web/main.js LAYER_Y)
# the wall from a lower quay up to the upper one (Paris's ports under the quais, 5-8 m of dressed stone): the TIN draws
# that step as a one-cell faceted slope (M5 critic: "a TIN slope with grass wedges and saw-tooth edges"). With
# step_walls on, the steep TIN triangles within STEP_REACH m of levelled water (steeper than STEP_SLOPE degrees and
# at least STEP_MIN m high, above the water's own quay wall) are merged, closed by STEP_CLOSE m so the wall's foot
# runs straight along the teeth, and covered by a stone block: a vertical ashlar face on every side down to the
# ground and a flat sett top at the step's crest (the highest ground within STEP_TOP m); off by default
STEP_WALLS = CFG["shores"].get("step_walls", False)
STEP_REACH, STEP_SLOPE = CFG["shores"].get("step_reach", 70.0), CFG["shores"].get("step_slope", 32.0)
STEP_MIN, STEP_CLOSE = CFG["shores"].get("step_min", 2.0), CFG["shores"].get("step_close", 3.0)
STEP_TOP = CFG["shores"].get("step_top", 7.0)


def resolve_bands(base, bands, water_side):
    """The bands per type as (a0, a1, y0, y1, slope, u0, u1): `base` (BANDS) with the [shores] bands and water_side
    settings applied; a type the settings don't name keeps its base bands. u0, u1 are the across coordinates
    written for the shader (the same as a0, a1 unless a setting moved the band)."""
    def y(v):
        return float(BAND_Y[v]) if isinstance(v, str) else float(v)
    def row(r):
        assert len(r) in (5, 7), f"[shores] bands: [a0, a1, y0, y1, slope] or with [.., u0, u1], got {list(r)}"
        a0, a1 = float(r[0]), float(r[1])
        return (a0, a1, y(r[2]), y(r[3]), r[4], *((float(r[5]), float(r[6])) if len(r) == 7 else (a0, a1)))
    out = {k: [row(r) for r in v] for k, v in base.items()}
    for typ, rows in bands.items():
        assert typ in base, f"[shores] bands: unknown type {typ} (one of {', '.join(base)})"
        out[typ] = [row(r) for r in rows]
    for typ, reach in water_side.items():
        assert typ in base, f"[shores] water_side: unknown type {typ} (one of {', '.join(base)})"
        end = max(r[1] for r in out[typ])
        assert end > 0 and reach > 0, f"[shores] water_side.{typ} = {reach} m, the type's bands end at {end} m"
        f = min(1.0, reach / end)
        # the bands from the edge on (across >= 0: slope, wall and the toe over the water) fitted into `reach`
        out[typ] = [(r[0] * f, r[1] * f, *r[2:]) if r[0] >= 0 else r for r in out[typ]]
    return out


def fetch_tags(area_utm) -> dict:
    """Tagged OSM features that decide the shore types, cached."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    s, w, n, e = gpd.GeoSeries([area_utm], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    res = overpass(f"""
        [out:json][timeout:900][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];
        (
          nwr["natural"~"^(beach|sand|wetland|mud|shoal)$"];
          nwr["landuse"~"^(port|harbour|basin|reservoir)$"];
          nwr["industrial"~"^(port|shipyard)$"];
          nwr["man_made"~"^(quay|pier|breakwater|groyne|dyke)$"];
          nwr["harbour"]; nwr["leisure"="marina"];
          way["natural"="water"]; rel["natural"="water"];
          way["waterway"="riverbank"]; rel["waterway"="riverbank"];
          nwr["leisure"="swimming_pool"];
        );
        out geom;
    """)
    CACHE.write_text(json.dumps(res))
    return res


def classify_features(res):
    """(kind, geometry in UTM) for the features that matter here."""
    out = []
    for t, g in element_geoms(res):
        nat, lu, mm = t.get("natural"), t.get("landuse"), t.get("man_made")
        if t.get("leisure") == "swimming_pool":
            kind = "pool" if g.geom_type in ("Polygon", "MultiPolygon") and t.get("indoor") != "yes" \
                and t.get("location") not in ("indoor", "roof", "rooftop") else None
        elif nat in ("beach", "sand"):
            kind = "beach"
        elif any(t.get(k) == v for k, v in MUDFLAT):
            kind = "mudflat"
        elif nat in ("wetland", "mud", "shoal"):
            kind = None
        elif lu in ("port", "harbour") or t.get("industrial") in ("port", "shipyard") or "harbour" in t \
                or mm in ("quay", "pier") or t.get("leisure") == "marina":
            kind = "quay"
        elif mm in ("breakwater", "groyne", "dyke"):
            kind = "breakwater"
        elif nat == "water" or t.get("waterway") == "riverbank" or lu in ("basin", "reservoir"):
            w = t.get("water", "")
            if w in ("river", "canal", "stream", "ditch", "drain", "oxbow", "lock", "wastewater", "moat") \
                    or t.get("waterway") == "riverbank" or lu == "basin" or w == "basin":
                kind = "river"
            else:
                kind = "pond"            # pond, lake, reservoir, fishpond, unset
        else:
            kind = None
        if kind:
            out.append((kind, g))
    kinds = [k for k, _ in out]
    geoms = gpd.GeoSeries([g for _, g in out], crs="EPSG:4326").to_crs(UTM).make_valid()
    f = gpd.GeoDataFrame({"kind": kinds}, geometry=geoms, crs=UTM)
    # a salt marsh bed or a scrap of tidal flat by a pier would turn the whole seawall beside it muddy
    small = (f.kind == "mudflat") & (f.area < MUDFLAT_MIN)
    return f[~small]


def edges(visible, water, area, detail, mud=None, solid=None):
    """Split the boundary of the visible land into coast and bank polylines (visible land on the left).
    Banks only within `detail` (beyond it they are far away, a fraction of a pixel wide). Coast with
    the mud layer beyond it is 'mud'. With `solid` (everything that is not sea), `visible` is the mud
    layer itself and only its edges onto the sea are kept, as 'mudedge'.

    Yields (kind, coords Nx2, closed) with kind 'coast', 'bank', 'mud' or 'mudedge'."""
    shapely.prepare(water)
    shapely.prepare(detail)
    if mud is not None:
        shapely.prepare(mud)
    if solid is not None:
        shapely.prepare(solid)
    inner = area.buffer(-3)
    shapely.prepare(inner)
    polys = [visible] if visible.geom_type == "Polygon" else list(visible.geoms)
    for poly in polys:
        poly = orient(poly.simplify(SIMPLIFY), 1.0)            # exterior CCW, holes CW: land on the left
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        for ring in [poly.exterior, *poly.interiors]:
            c = np.asarray(ring.coords)[:-1]
            if len(c) < 3:
                continue
            nxt = np.roll(c, -1, axis=0)
            d = nxt - c
            ln = np.linalg.norm(d, axis=1)
            mid = (c + nxt) / 2
            right = np.stack([d[:, 1], -d[:, 0]], 1) / np.maximum(ln, 1e-9)[:, None]
            probe = mid + right * 1.5
            in_water = shapely.contains_xy(water, probe[:, 0], probe[:, 1])
            in_area = shapely.contains_xy(inner, probe[:, 0], probe[:, 1])
            # segment kind: 0 drop (area edge), 1 coast, 2 bank, 3 onto the mud layer, 4 mud onto the sea
            in_detail = shapely.contains_xy(detail, probe[:, 0], probe[:, 1])
            if solid is not None:
                kind = np.where(in_area & ~shapely.contains_xy(solid, probe[:, 0], probe[:, 1]), 4, 0)
            else:
                on_mud = shapely.contains_xy(mud, probe[:, 0], probe[:, 1]) if mud is not None else False
                kind = np.where(~in_area, 0, np.where(in_water, np.where(in_detail, 2, 0), np.where(on_mud, 3, 1)))
            yield from runs(c, kind)


RUN_KINDS = {1: "coast", 2: "bank", 3: "mud", 4: "mudedge"}


def runs(c, kind):
    """Cut a closed ring (segments i: c[i] -> c[i+1]) into runs of one kind; whole-ring runs stay closed."""
    n = len(c)
    if (kind == kind[0]).all():
        if kind[0]:
            yield RUN_KINDS[int(kind[0])], np.vstack([c, c[:1]]), True
        return
    start = int(np.nonzero(kind != np.roll(kind, 1))[0][0])       # a segment where the kind changes
    order = (np.arange(n) + start) % n
    k0, seg = kind[order[0]], [order[0]]
    for i in order[1:]:
        if kind[i] == k0:
            seg.append(i)
            continue
        if k0:
            yield RUN_KINDS[int(k0)], np.vstack([c[seg], c[(seg[-1] + 1) % n]]), False
        k0, seg = kind[i], [i]
    if k0:
        yield RUN_KINDS[int(k0)], np.vstack([c[seg], c[(seg[-1] + 1) % n]]), False


def bank_types(kinds, soft, warea=None):
    """Bank segments' types: a pond's bank soft (pondbank) where a park's green lies inland, else a stone edge
    (pondedge); rivers' and canals' BANK_TYPE. With [shores] pond_edge_area, ponds at least that large (warea: m² of
    the water each segment belongs to) take the stone edge beside the green too."""
    soft = np.asarray(soft, bool)
    if POND_EDGE_AREA and warea is not None:
        soft = soft & (np.asarray(warea, float) < POND_EDGE_AREA * 1e6)
    return np.where(np.asarray(kinds) == "pond", np.where(soft, "pondbank", "pondedge"), BANK_TYPE).astype(object)


def smooth_types(types, seglen):
    """Merge runs of one type shorter than MIN_RUN into the longer neighbour, so types don't flicker."""
    types = list(types)
    for _ in range(3):
        i, n = 0, len(types)
        while i < n:
            j = i
            while j + 1 < n and types[j + 1] == types[i]:
                j += 1
            if sum(seglen[i:j + 1]) < MIN_RUN and (i > 0 or j < n - 1):
                repl = types[i - 1] if i > 0 else types[j + 1]
                for q in range(i, j + 1):
                    types[q] = repl
            i = j + 1
    return types


def offsets(c, closed):
    """Unit right-hand normals at each vertex, lengthened at corners (miter, limited)."""
    d = np.diff(c, axis=0)
    ln = np.linalg.norm(d, axis=1)
    ln[ln == 0] = 1e-9
    nrm = np.stack([d[:, 1], -d[:, 0]], 1) / ln[:, None]
    if closed:
        prev = np.vstack([nrm[-1:], nrm])
        nxt = np.vstack([nrm, nrm[:1]])
    else:
        prev = np.vstack([nrm[:1], nrm])
        nxt = np.vstack([nrm, nrm[-1:]])
    m = prev + nxt
    m /= np.maximum(np.linalg.norm(m, axis=1), 1e-9)[:, None]
    cos = (m * nxt).sum(1)
    scale = 1 / np.clip(cos, 1 / MITER_MAX, 1)
    return m * scale[:, None], np.concatenate([[0], np.cumsum(ln)])


# how a band's heights meet the ground (05a_terrain.py): absolute (the sea's side of the coast, pools at
# their level), over the ground under each vertex (the coast's land side: the ground is level at 0 there),
# or draped: cut along the TIN wherever it isn't level (banks of inland water, which may lie on a slope)
ABSOLUTE, OVER, DRAPED = 0, 1, 2


class Mesh:
    def __init__(self):
        self.pos, self.nrm, self.uv, self.col, self.mode, self.idx, self.n = [], [], [], [], [], [], 0

    def band(self, xz0, off, along, a0, a1, y0, y1, slope_deg, typ, band, seed, mode=ABSOLUTE, u0=None, u1=None):
        """One band: quads between across a0 and a1 along a polyline (scene x, z) with normals `off`.
        mode: DRAPED, or for coasts OVER on the land (across <= 0) and ABSOLUTE over the sea.
        u0, u1: the across coordinate written to TEXCOORD_0 (default a0, a1; [shores] bands / water_side)."""
        k = len(xz0)
        # shading normal: tilted towards the water (the offset direction) by the slope angle
        s = np.radians(slope_deg)
        dirn = off / np.maximum(np.linalg.norm(off, axis=1), 1e-9)[:, None]
        nx, nz, ny = dirn[:, 0] * np.sin(s), dirn[:, 1] * np.sin(s), np.full(k, np.cos(s))
        u0, u1 = (a0 if u0 is None else u0), (a1 if u1 is None else u1)
        for a, y, u in ((a0, y0, u0), (a1, y1, u1)):
            p = xz0 + off * a
            self.pos.append(np.column_stack([p[:, 0], np.full(k, y), p[:, 1]]))
            self.nrm.append(np.column_stack([nx, ny, nz]))
            self.uv.append(np.column_stack([np.full(k, u), along]))
            self.col.append(np.tile([typ, band, seed, 255], (k, 1)))
            self.mode.append(np.full(k, mode if mode != OVER or a <= 0 else ABSOLUTE))
        i = np.arange(k - 1) + self.n
        # rows: [n, n+k) at a0, [n+k, n+2k) at a1; front faces up (counter-clockwise seen from above)
        q = np.stack([i, i + 1, i + k, i + 1, i + k + 1, i + k], 1)
        self.idx.append(q.reshape(-1))
        self.n += 2 * k

    def strip(self, p0, p1, y0, y1, u0, u1, along, nrm, typ, band, seed):
        """Quads between two polylines (scene x, z) with heights per vertex (absolute), across coordinates
        u0, u1 (scalars or per vertex) and one shading normal per vertex (or one for all)."""
        k = len(p0)
        nrm = np.broadcast_to(np.asarray(nrm, float), (k, 3))
        for p, y, u in ((p0, y0, u0), (p1, y1, u1)):
            self.pos.append(np.column_stack([p[:, 0], np.broadcast_to(y, k), p[:, 1]]))
            self.nrm.append(nrm.copy())
            self.uv.append(np.column_stack([np.broadcast_to(u, k), along]))
            self.col.append(np.tile([typ, band, seed, 255], (k, 1)))
            self.mode.append(np.full(k, ABSOLUTE))
        i = np.arange(k - 1) + self.n
        self.idx.append(np.stack([i, i + 1, i + k, i + 1, i + k + 1, i + k], 1).reshape(-1))
        self.n += 2 * k

    def fill(self, poly: Polygon, y, typ, origin):
        """A flat polygon (pools)."""
        v2, tri = tiles06.triangulate(poly)
        if not len(tri):
            return
        p = to_scene(v2, origin)
        k = len(p)
        self.pos.append(np.column_stack([p[:, 0], np.full(k, y), p[:, 1]]))
        self.nrm.append(np.tile([0.0, 1.0, 0.0], (k, 1)))
        self.uv.append(np.zeros((k, 2)))
        self.col.append(np.tile([typ, 0, 0, 255], (k, 1)))
        self.mode.append(np.full(k, ABSOLUTE))
        pos3 = self.pos[-1]
        idx = tiles06.orient(pos3, tri.astype(np.int64), self.nrm[-1]).reshape(-1)
        self.idx.append(idx + self.n)
        self.n += k

    def arrays(self, terrain: Terrain):
        if not self.n:
            return None
        pos, idx = np.concatenate(self.pos), np.concatenate(self.idx).reshape(-1, 3)
        nrm, uv, col, mode = (np.concatenate(a) for a in (self.nrm, self.uv, self.col, self.mode))
        over = mode == OVER
        pos[over, 1] += terrain.height(pos[over, 0], pos[over, 2])
        on = (mode[idx] == DRAPED).all(1)
        d = terrain.drape_triangles(pos[:, [0, 2]], idx[on], tol=0.03) if on.any() else None
        if d is not None:
            xz, src, bary, gy, _, t2 = d
            sv = idx[on][src]
            keep = np.flatnonzero(mode != DRAPED)
            remap = np.full(len(pos), -1)
            remap[keep] = np.arange(len(keep))
            idx = np.concatenate([remap[idx[~on]], t2 + len(keep)])
            y = (bary * pos[sv, 1]).sum(1) + gy
            n2 = (bary[:, :, None] * nrm[sv]).sum(1)
            pos = np.concatenate([pos[keep], np.column_stack([xz[:, 0], y, xz[:, 1]])])
            nrm = np.concatenate([nrm[keep], n2 / np.maximum(np.linalg.norm(n2, axis=1, keepdims=True), 1e-9)])
            uv = np.concatenate([uv[keep], (bary[:, :, None] * uv[sv]).sum(1)])
            col = np.concatenate([col[keep], col[sv[:, 0]]])
        m = weld({"pos": pos, "nrm": nrm, "uv": uv, "col": col, "idx": idx})
        # front faces up; a quay wall's face (vertical) towards its shading normal, the water
        facing = np.tile([0.0, 1.0, 0.0], (len(m["pos"]), 1))
        wall = (np.round(m["col"][:, 0]) == T["quaywall"]) & (np.round(m["col"][:, 1]) == 1)
        facing[wall] = m["nrm"][wall]
        idx = tiles06.orient(m["pos"], m["idx"], facing)
        return {"pos": m["pos"].astype(np.float32), "nrm": m["nrm"].astype(np.float32), "uv": m["uv"].astype(np.float32),
                "col": m["col"].astype(np.uint8), "idx": idx.reshape(-1).astype(np.uint32)}


def write_glb(path, meshes: dict):
    """Meshes by name, float attributes (positions are scene metres), one node each."""
    blob, views, accessors, nodes, gmeshes = bytearray(), [], [], [], []

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

    names = [k for k, m in meshes.items() if m is not None]
    for mi, name in enumerate(names):
        m = meshes[name]
        attrs = {
            "POSITION": add(m["pos"], 5126, "VEC3", 34962, minmax=(m["pos"].min(0).tolist(), m["pos"].max(0).tolist())),
            "NORMAL": add(np.column_stack([np.round(m["nrm"] * 127), np.zeros(len(m["nrm"]))]).astype(np.int8),
                          5120, "VEC3", 34962, normalized=True),
            "TEXCOORD_0": add(m["uv"], 5126, "VEC2", 34962),
            "COLOR_0": add(m["col"], 5121, "VEC4", 34962, normalized=True),
        }
        ind = add(m["idx"], 5125, "SCALAR", 34963)
        gmeshes.append({"name": name, "primitives": [{"attributes": attrs, "indices": ind, "material": mi}]})
        nodes.append({"mesh": mi, "name": name})
    while len(blob) % 4:
        blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": generator("05e_shores")},
            "extensionsUsed": ["KHR_mesh_quantization"], "extensionsRequired": ["KHR_mesh_quantization"],
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": gmeshes,
            "materials": [{"name": n} for n in names], "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942)); f.write(bytes(blob))


def quay_runs(c, types, kind, rows, tree, levels, terrain: Terrain, origin):
    """Bank segments of rivers' and canals' type (BANK_TYPE) where the ground stands QUAY_MIN over the water's
    level become "quaywall" (in place); returns the level per vertex (NaN where unknown)."""
    seg = np.diff(c, axis=0)
    ln = np.maximum(np.linalg.norm(seg, axis=1), 1e-9)
    right = np.stack([seg[:, 1], -seg[:, 0]], 1) / ln[:, None]         # towards the water (UTM)
    def level_at(pts, nrm):
        probe = pts + nrm * 3.0
        idx = tree.query(shapely.points(probe[:, 0], probe[:, 1]), predicate="within")
        lv = np.full(len(pts), np.nan)
        lv[idx[0]] = levels[idx[1]]
        return lv
    mid = (c[1:] + c[:-1]) / 2
    lv = level_at(mid, right)
    top = np.max([terrain.height_utm(*(mid - right * a).T) for a in (1.0, 3.0, 5.0, 7.0)], axis=0)
    quay = np.isfinite(lv) & (top - lv >= QUAY_MIN) & (np.asarray(types) == BANK_TYPE)
    for i in np.flatnonzero(quay):
        types[i] = "quaywall"
    # per vertex: the level of either neighbouring segment
    vr = np.vstack([right[:1], right]) + np.vstack([right, right[-1:]])
    vr /= np.maximum(np.linalg.norm(vr, axis=1), 1e-9)[:, None]
    return level_at(c, vr)


def quay_wall(mesh, toe, xz, off, along, lv, terrain: Terrain, seed):
    """One run of quay wall (scene x, z along it, off: unit-ish normals towards the water; lv: water level per
    vertex): the apron from the face QUAY_FACE out in the water to QUAY_APRON inland at the quay's height (the
    highest ground under it), a chamfer down to the ground behind, the wall's face from under the water up to
    the apron, and the wall's shadow on the water in front."""
    n = off / np.maximum(np.linalg.norm(off, axis=1), 1e-9)[:, None]
    lv = np.where(np.isfinite(lv), lv, np.nanmedian(lv) if np.isfinite(lv).any() else 0.0)
    samples = [terrain.height(*(xz - n * a).T) for a in np.arange(0.0, min(QUAY_TOP, QUAY_APRON) + 0.1, 1.0)]
    top = np.maximum(np.max(samples, axis=0), lv + QUAY_MIN) + BANK_TOP
    back = terrain.height(*(xz - n * (QUAY_APRON + 1.0)).T) + 0.05
    face = xz + n * QUAY_FACE
    inner = xz - n * QUAY_APRON
    outer = xz - n * (QUAY_APRON + 1.0)
    water = lv + WATER_Y
    up = [0.0, 1.0, 0.0]
    # across on the apron: metres from the face (negative inland), the coping along its edge
    w = QUAY_APRON + QUAY_FACE
    mesh.strip(inner, face, top, top, -w, 0.0, along, up, T["quaywall"], 0, seed)                       # apron
    mesh.strip(outer, inner, back, top, -w - 1.0, -w, along, up, T["quaywall"], 0, seed)
    wn = np.column_stack([n[:, 0], np.zeros(len(n)), n[:, 1]])
    # the face: uv across = height over the water's surface (courses, the wet foot)
    mesh.strip(face, face, top, water - 0.6, top - water, -0.6, along, wn, T["quaywall"], 1, seed)
    toe.strip(face, face + n * 4.0, water + 0.03, water + 0.03, 0.08, 4.0, along, up, T["quay"], 2, seed)


def step_walls(mesh, terrain: Terrain, rows, levels, origin, stats):
    """[shores] step_walls (see STEP_WALLS): stone blocks over the TIN's steps from the lower quays to the upper."""
    wet = [r for r, v in zip(rows, levels) if np.isfinite(v)]
    if not wet:
        return
    lv_min = float(np.nanmin(levels))
    near = shapely.transform(unary_union(wet).buffer(STEP_REACH), lambda c: to_scene(c, origin))
    water = shapely.transform(unary_union(wet), lambda c: to_scene(c, origin))
    p = np.column_stack([terrain.xz[:, 0], terrain.y, terrain.xz[:, 1]])
    t = terrain.tri
    n = np.cross(p[t[:, 2]] - p[t[:, 0]], p[t[:, 1]] - p[t[:, 0]])
    ny = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    ty = terrain.y[t]
    steep = (ny < np.cos(np.radians(STEP_SLOPE))) & (ty.max(1) - ty.min(1) >= STEP_MIN) & (ty.min(1) >= lv_min + QUAY_MIN)
    cand = np.flatnonzero(steep)
    cand = cand[shapely.intersects(near, terrain.polys[cand])]
    # not the water's own quay wall: triangles over the water or touching it
    cand = cand[~shapely.intersects(water.buffer(1.0), terrain.polys[cand])]
    if not len(cand):
        return
    r = unary_union(list(terrain.polys[cand])).buffer(STEP_CLOSE, join_style="mitre").buffer(-STEP_CLOSE, join_style="mitre")
    r = r.difference(water.buffer(QUAY_FACE + 0.5)).simplify(0.4)
    blocks = [q for q in tiles06.polygons(r) if q.area >= 60]
    offs = np.array([(dx, dz) for dx in np.arange(-STEP_TOP, STEP_TOP + 0.1, 1.75) for dz in np.arange(-STEP_TOP, STEP_TOP + 0.1, 1.75)
                     if dx * dx + dz * dz <= STEP_TOP * STEP_TOP])
    def top_at(xz):
        # the crest: the highest ground within STEP_TOP m
        h = np.full(len(xz), -np.inf)
        for o in offs:
            h = np.maximum(h, terrain.height(xz[:, 0] + o[0], xz[:, 1] + o[1]))
        return h + 0.05
    up = [0.0, 1.0, 0.0]
    for q in blocks:
        q = orient(shapely.segmentize(q, 3.0), 1.0)
        v2, tri = tiles06.triangulate(q)
        if not len(tri):
            continue
        k = len(v2)
        y = top_at(v2)
        x0, z0 = v2.min(0)
        mesh.pos.append(np.column_stack([v2[:, 0], y, v2[:, 1]]))
        mesh.nrm.append(np.tile([0.0, 1.0, 0.0], (k, 1)))
        # setts on top (across below the coping's -0.7), in the block's own frame
        mesh.uv.append(np.column_stack([-(v2[:, 1] - z0) - 1.0, (v2[:, 0] - x0) % ALONG_WRAP]))
        mesh.col.append(np.tile([T["quaywall"], 0, 7, 255], (k, 1)))
        mesh.mode.append(np.full(k, ABSOLUTE))
        mesh.idx.append(tiles06.orient(mesh.pos[-1], tri.astype(np.int64), mesh.nrm[-1]).reshape(-1) + mesh.n)
        mesh.n += k
        for ring in [q.exterior, *q.interiors]:
            c = np.asarray(ring.coords)
            if len(c) < 3:
                continue
            seg = np.diff(c, axis=0)
            # outward horizontal normal per vertex: orient(q, 1.0) runs the exterior counter-clockwise and the holes
            # clockwise, so the block is left of travel on every ring and outward is right of it
            sn = np.stack([seg[:, 1], -seg[:, 0]], 1) / np.maximum(np.linalg.norm(seg, axis=1), 1e-9)[:, None]
            vn = np.vstack([sn[-1:], sn]) + np.vstack([sn, sn[:1]])
            vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-9)[:, None]
            top = top_at(c)
            foot = np.minimum(terrain.height(*(c + vn * 0.6).T), top) - 0.4
            along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(seg, axis=1))]) % ALONG_WRAP
            wn = np.column_stack([vn[:, 0], np.zeros(len(vn)), vn[:, 1]])
            # across on the face: metres over its foot, plus 2 (the shader's wet foot is at the water only)
            mesh.strip(c, c, top, foot, top - foot + 2.0, 2.0, along, wn, T["quaywall"], 1, 7)
            stats["stepwall"] += float(np.sum(np.linalg.norm(seg, axis=1)))
    print(f"step walls: {len(blocks)} blocks over {len(cand):,} steep TIN triangles", flush=True)


def main():
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)             # 06_tiles.py's scene origin
    terrain = Terrain()
    ground = DATA / "ground.gpkg"
    area = gpd.read_file(ground, layer="area").geometry.iloc[0]
    # as drawn: 06_tiles.py skips pieces under 50 m²
    def layer(name):
        g = gpd.read_file(ground, layer=name).geometry
        parts = [p for geom in g for p in tiles06.polygons(geom) if p.area > 50]
        return unary_union(parts)
    print("union of the ground layers ...", flush=True)
    green = layer("green")
    land = unary_union([layer("land"), green, layer("aeroway")]).intersection(area)
    shapely.prepare(green)
    water = layer("water").intersection(area)
    visible = land.difference(water).buffer(0)
    # intertidal mudflats (drawn at MUD_Y): the coast behind them is a bank onto the mud, and their
    # own edge onto the sea frays into it
    mud = layer("mud").intersection(area).difference(land).buffer(0)
    solid = unary_union([land, water, mud]).buffer(0.5)
    print(f"land {land.area / 1e6:.0f} km², inland water {water.area / 1e6:.1f} km², mud {mud.area / 1e6:.1f} km²",
          flush=True)

    feats = classify_features(fetch_tags(area))
    print(feats.kind.value_counts().to_string())
    near = {k: unary_union(list(feats.geometry[feats.kind == k])) for k in ("beach", "mudflat", "quay", "breakwater", "river", "pond")}
    reach = {"beach": 40, "mudflat": 70, "quay": 25, "breakwater": 10}
    zones = {k: near[k].buffer(reach[k]) for k in reach if not near[k].is_empty}
    for z in zones.values():
        shapely.prepare(z)
    waters = feats[feats.kind.isin(["river", "pond"])].reset_index(drop=True)

    bands = resolve_bands(BANDS, SHORE_BANDS, WATER_SIDE)
    opaque, toe = Mesh(), Mesh()
    rng = np.random.default_rng(5)
    stats = Counter()
    detail = boundary().to_crs(UTM).union_all().buffer(DETAIL_MARGIN)
    if QUAY_WALLS:
        rows = [g for geom in gpd.read_file(ground, layer="water").geometry for g in [geom]]
        levels = tiles06.water_levels(rows, terrain, detail)
        tree = shapely.STRtree(rows)
        print(f"quay walls: {np.isfinite(levels).sum()} levelled water bodies by the districts", flush=True)
    for kind, c, closed in itertools.chain(edges(visible, water, area, detail, mud=mud),
                                           edges(mud, water, area, detail, solid=solid)):
        if QUAY_WALLS and kind == "bank" and len(c) >= 2:
            c = shapely.get_coordinates(shapely.segmentize(shapely.LineString(c), QUAY_STEP))
        seg = np.diff(c, axis=0)
        seglen = np.linalg.norm(seg, axis=1)
        if seglen.sum() < 4:
            continue
        mid = (c[1:] + c[:-1]) / 2
        if kind in ("mud", "mudedge"):
            types = np.full(len(mid), "mudbank" if kind == "mud" else "mudedge", dtype=object)
        elif kind == "coast":
            types = np.full(len(mid), COAST_TYPE, dtype=object)
            # later rules win: quay, then beach, then mudflat (a mangrove inside a port is still mud)
            for k in ("quay", "breakwater", "beach", "mudflat"):
                if k in zones:
                    hit = shapely.contains_xy(zones[k], mid[:, 0], mid[:, 1])
                    types[hit] = COAST_TYPE if k == "breakwater" else k
        else:
            # the water feature this bank belongs to: the nearer of the tagged rivers and ponds
            probe = mid + np.stack([seg[:, 1], -seg[:, 0]], 1) / np.maximum(seglen, 1e-9)[:, None] * 3
            pts_ = gpd.GeoDataFrame(geometry=gpd.points_from_xy(probe[:, 0], probe[:, 1]), crs=UTM)
            hit = gpd.sjoin_nearest(pts_, waters, how="left", max_distance=60)
            kinds = hit[~hit.index.duplicated()].kind.reindex(range(len(mid))).fillna("river").values
            # a pond in a park gets a soft bank; one among paving (plazas, office parks) a stone edge
            inland = mid - np.stack([seg[:, 1], -seg[:, 0]], 1) / np.maximum(seglen, 1e-9)[:, None] * 2.5
            soft = shapely.contains_xy(green, inland[:, 0], inland[:, 1])
            warea = None
            if POND_EDGE_AREA:
                warea = hit[~hit.index.duplicated()].index_right.reindex(range(len(mid))).map(
                    lambda j: waters.geometry.iloc[int(j)].area if j == j else 0.0).values
            types = bank_types(kinds, soft, warea)
        if ISLET_MAX and kind == "coast" and closed and np.ptp(c, axis=0).max() <= ISLET_MAX:
            types[types == "beach"] = ISLET_TYPE
        vlev = None
        if QUAY_WALLS and kind == "bank":
            vlev = quay_runs(c, types, kind, rows, tree, levels, terrain, origin)
        types = smooth_types(types, seglen)
        # cut into runs of one type; each run gets its own bands
        i = 0
        while i < len(types):
            j = i
            while j + 1 < len(types) and types[j + 1] == types[i]:
                j += 1
            pts = c[i:j + 2]
            whole = closed and i == 0 and j == len(types) - 1
            typ = types[i]
            xz = to_scene(pts, origin)
            # scene z = -northing, which mirrors left and right: recompute the offsets in scene space
            # (to_scene flips z, so the water, right of the line in UTM, is on the left in scene x-z)
            off, s = offsets(xz, whole)
            off = -off
            along = s % ALONG_WRAP
            seed = int(rng.integers(0, 256))
            if typ == "quaywall":
                quay_wall(opaque, toe, xz, off, along, vlev[i:j + 2], terrain, seed)
                stats[typ] += s[-1]
                i = j + 1
                continue
            mode = DRAPED if kind == "bank" else OVER
            for b, (a0, a1, ya, yb, slope, u0, u1) in enumerate(bands[typ]):
                bid = BAND_IDS.get(typ, range(3))[b]
                (toe if bid == 2 else opaque).band(xz, off, along, a0, a1, ya, yb, slope, T[typ], bid, seed, mode, u0, u1)
            stats[typ] += s[-1]
            i = j + 1

    if QUAY_WALLS and STEP_WALLS:
        step_walls(opaque, terrain, rows, levels, origin, stats)

    pools = Mesh()
    for g in feats.geometry[feats.kind == "pool"]:
        for p in tiles06.polygons(g):
            if p.area < 8 or not detail.contains(p):
                continue
            p = orient(p.simplify(0.2), 1.0)
            ring = np.asarray(p.exterior.coords)
            # level, at the highest ground round it (a terrace where the ground slopes)
            level = float(terrain.height_utm(ring[:, 0], ring[:, 1]).max())
            pools.fill(p, POOL_Y + level, T["pool"], origin)
            xz = to_scene(ring, origin)
            off, s = offsets(xz, True)
            # coping around the pool, on the land side (outside the polygon)
            a0, a1, ya, yb, slope = bands["pool"][0][:5]
            opaque.band(xz, off, s, a0, a1, ya + level, yb + level, slope, T["pool"], 0, 0)
            stats["pool"] += 1

    OUT_RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    write_glb(OUT_RAW / "shores.glb", {"shore": opaque.arrays(terrain), "shallows": toe.arrays(terrain),
                                       "pools": pools.arrays(terrain)})
    pack07.RAW, pack07.OUT = OUT_RAW, OUT
    pack07.pack("shores.glb")
    index = {"file": "shores.glb", "types": TYPES, "bands": {k: [list(b[:5]) + (list(b[5:]) if b[5:] != b[:2] else []) for b in v] for k, v in bands.items()},
             "lengths_km": {k: round(v / 1000, 1) for k, v in stats.items() if k != "pool"},
             "pools": stats["pool"]}
    (OUT / "shores.json").write_text(json.dumps(index, indent=1))
    link_web("shores")
    raw_mb = (OUT_RAW / "shores.glb").stat().st_size / 1e6
    mb = (OUT / "shores.glb").stat().st_size / 1e6
    print({k: f"{v / 1000:.1f} km" for k, v in stats.items() if k != "pool"}, f"pools {stats['pool']}")
    print(f"vertices: shore {opaque.n:,}, shallows {toe.n:,}, pools {pools.n:,}; {raw_mb:.1f} MB raw, {mb:.1f} MB packed")

