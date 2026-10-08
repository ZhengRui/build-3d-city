"""The jp-tokyo preset's code (Tokyo, M4; tables in presets/jp-tokyo.toml): building kinds and facade styles per
BUILDING, not per piece. PLATEAU cuts a building into pieces by roof level (`parent_id` holds the building's gml id,
`gml_id` its own with a #r<n> suffix); OSM's fill is one piece per outline. Each building is judged as a whole: its
top (the highest piece), its footprint (the pieces' areas summed), its storeys (PLATEAU's storeysAboveGround, the
highest), PLATEAU's usage (usage_name, detailedusage_name) and structure class (class_name: an "ordinary building"
is wooden or light steel, a "solid building" fireproof), OSM's tag where PLATEAU has no usage. Rooftop clutter:
rooftops.py.

Kinds (china-south's names, which the other stages know): tower (60 m and up), slab (24 m up and long), podium (low
and big commercial), village (the narrow 4-12 storey 雑居ビル and pencil buildings), house (low: under 12 m on a small
lot, and every wooden building), civic (government, education, culture, welfare, medical, religion), factory
(factories, warehouses, utilities under 24 m), midrise (the rest).

Styles, in order (a later rule wins):
  1. by usage: apartments mansion; detached houses and low shop houses wooden; offices, shops, hotels tiled;
     factories, warehouses factory; government government; education, welfare, medical, culture civic; religion
     temple (civic over 25 m); wooden structures (class "ordinary building") under 12 m wooden
  2. offices, shops, hotels and unknown by size: a narrow lot (zakkyo_area) of zakkyo_min_h and up zakkyo; a big
     commercial building (depato_area, under depato_max_h) depato; towers (tower_h) glass, granite on a share
     (granite_area_share in the granite areas, Nishi-Shinjuku); 30 m to tower_h glass, granite or tiled by seed;
     in the flagship areas (Ginza Chuo-dori, Omotesando) mid-size commercial fronts glass or depato
  3. a tower's low pieces (under podium_h and podium_k of its top) are its stone podium: granite (Marunouchi's 31 m
     line)
  4. OSM-only buildings (no PLATEAU usage): the [facade.osm_style] tag, else by kind; in the government areas
     (Kasumigaseki and Nagatacho, which PLATEAU leaves out) government
  5. (M4 fix round) the sign streets ([facade.tokyo] sign_zones: Akihabara's Chuo-dori, Kabukicho, Yasukuni-dori,
     Center-gai): commercial buildings under 60 m fronting the zone's streets (sign_fronts()) take the `signs` style
     (wall-sized boards and screens) on the zone's share; the projecting sign boxes on them are figures
     (demos/tokyo/scripts/m4f_signs.py reads sign_fronts() too)
"""
import numpy as np
import pandas as pd

from ... import config
from ..china_south import building_kind as cs_kind

CFG = config.get()
TK = CFG["facade"].get("tokyo", {})
OSM_KIND = CFG["buildings"]["osm_kind"]

COMMERCE = {"business", "commercial", "accommodation", "house with shop", "unknown", "other"}
CIVIC_U = {"government", "education, culture, welfare"}
CIVIC_D = {"education", "medical", "welfare", "culture", "religion", "performance venue", "sports", "public bath etc."}
FACTORY_U = {"factory", "transport and warehouse", "utility (supply, treatment)"}


def col(b, name):
    return b[name] if name in b else pd.Series(np.nan, index=b.index)


def group_key(b) -> pd.Series:
    """The building each piece belongs to: PLATEAU's parent_id, else its gml id without the roof-level suffix, else
    OSM's id, else the piece itself."""
    pid = col(b, "parent_id").fillna("").astype(str)
    gml = col(b, "gml_id").fillna("").astype(str).str.split("#").str[0]
    osm = col(b, "osm_id").fillna("").astype(str)
    key = pid.where(pid != "", gml.where(gml != "", osm.where(osm != "", "i" + b.index.astype(str))))
    return key


def whole(b) -> pd.DataFrame:
    """Per piece, its building's figures: H (top), A (footprint), S (storeys), usage, detail, cls, tag."""
    key = group_key(b)
    h = pd.to_numeric(b.get("h_bldg", b["h"]), errors="coerce").fillna(b["h"])
    df = pd.DataFrame({"key": key, "h": h, "a": b["area"],
                       "s": pd.to_numeric(col(b, "storeysaboveground"), errors="coerce"),
                       "usage": col(b, "usage_name").astype(object), "detail": col(b, "detailedusage_name").astype(object),
                       "cls": col(b, "class_name").astype(object), "tag": col(b, "osm_building").astype(object)},
                      index=b.index)
    g = df.groupby("key")
    first = lambda c: g[c].transform("first")        # (the first non-null piece's)
    out = pd.DataFrame({"H": g["h"].transform("max"), "A": g["a"].transform("sum"), "S": g["s"].transform("max"),
                        "n": g["h"].transform("size")}, index=b.index)
    for c in ("usage", "detail", "cls", "tag"):
        out[c] = first(c) if df[c].notna().any() else np.nan
    out["key"] = key
    return out


def building_kind(df: pd.DataFrame) -> pd.Series:
    """Kind per piece, the same for all the pieces of a building (module docstring)."""
    if "parent_id" not in df and "usage_name" not in df:      # (a table without PLATEAU's fields: china-south's)
        return cs_kind(df)
    w = whole(df)
    H, A, S = w.H, w.A, w.S.fillna((w.H / 3.5).round())
    u, d = w.usage.fillna("").astype(str), w.detail.fillna("").astype(str)
    wood = w.cls.fillna("").astype(str).eq("ordinary building")
    asp = df["aspect"]
    kind = pd.Series("midrise", index=df.index, dtype=object)
    kind[(H >= 24) & (asp >= 2.5)] = "slab"
    kind[(H < 24) & (A >= 1200) & u.isin(["commercial", "business"])] = "podium"
    kind[(H >= 12) & (H < 45) & (A < TK.get("zakkyo_area", 300.0)) & ~u.isin(["apartment building"])] = "village"
    kind[(H < 12) & (A < 250)] = "house"
    kind[wood & (H < 12)] = "house"
    kind[u.isin(FACTORY_U) & (H < 24)] = "factory"
    kind[u.isin(CIVIC_U) | d.isin(CIVIC_D)] = "civic"
    kind[H >= 60] = "tower"
    # OSM-only buildings (no usage): china-south's shape rules on the whole, the tag's kind
    osm = u.eq("")
    if osm.any():
        cs = cs_kind(df[osm])
        kind[osm] = cs
    tagk = w.tag.map(OSM_KIND)
    use = tagk.notna() & tagk.isin(["civic", "factory", "house"]) & (kind != "tower") & (osm | tagk.eq("civic"))
    kind[use] = tagk[use]
    return kind


def _in_boxes(b, boxes) -> pd.Series:
    if not boxes:
        return pd.Series(False, index=b.index)
    pt = b.geometry.representative_point().to_crs(4326)
    x, y = pt.x.values, pt.y.values
    hit = np.zeros(len(b), bool)
    for x0, y0, x1, y1 in boxes:
        hit |= (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return pd.Series(hit, index=b.index)


def sign_fronts(b) -> pd.DataFrame:
    """Per piece (b in the city's UTM): `zone` (the index in [facade.tokyo] sign_zones whose box holds it, -1 none) and
    `front` (True where its outline comes within the street's half width + `dist` m of one of the zone's streets: OSM
    ways named in its `roads`, or every non-rail way at ground level with `roads = "*"`). Each zone: {name, box [lon0,
    lat0, lon1, lat1], roads, dist (default 6), share (of the fronting buildings in `signs`), boxes (of them with
    projecting sign boxes)}."""
    import geopandas as gpd
    from ...common import DATA
    zones = TK.get("sign_zones", [])
    zone = pd.Series(-1, index=b.index)
    front = pd.Series(False, index=b.index)
    if not zones:
        return pd.DataFrame({"zone": zone, "front": front})
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ways = ways[(ways.kind != "rail") & ~ways.elevated.fillna(False).astype(bool)]
    for k, z in enumerate(zones):
        inz = _in_boxes(b, [z["box"]]) & zone.eq(-1)
        if not inz.any():
            continue
        zone[inz] = k
        x0, y0 = TO_UTM(z["box"][0], z["box"][1])
        x1, y1 = TO_UTM(z["box"][2], z["box"][3])
        w = ways.cx[x0 - 50:x1 + 50, y0 - 50:y1 + 50]
        if z.get("roads", "*") != "*":
            names = z["roads"] if isinstance(z["roads"], list) else [z["roads"]]
            w = w[w.name.isin(names)]
        if not len(w):
            continue
        reach = gpd.GeoSeries([g.buffer(float(wd) / 2 + z.get("dist", 6.0)) for g, wd in zip(w.geometry, w.width.fillna(6.0))],
                              crs=w.crs).union_all()
        front[inz] = b.geometry[inz].intersects(reach)
    return pd.DataFrame({"zone": zone, "front": front})


def roof_shapes(b, style) -> pd.DataFrame:
    """(M4 fix round) Per building: roof shape and material (2 tile): temples and shrines from 4 to 20 m a hipped tile
    roof leaning in from their free walls (dark kawara, facade.roofs.tile; the critic saw flat-topped vermilion boxes);
    OSM parts and landmark rows keep their own massing (06_tiles)."""
    idx = b.index
    style = pd.Series(style, index=idx).astype(str)
    h, a = b.h, b.geometry.area
    on = style.eq("temple") & (h >= 4) & (h < 20) & (a >= 30)
    shape = pd.Series("", index=idx, dtype=object)
    shape[on] = "pitched"
    return pd.DataFrame({"shape": shape, "material": np.where(on, 2, 0)}, index=idx)


def TO_UTM(lon, lat):
    from pyproj import Transformer
    return Transformer.from_crs(4326, CFG["utm_epsg"], always_xy=True).transform(lon, lat)


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles): the module docstring's rules."""
    idx = b.index
    w = whole(b)
    h = pd.to_numeric(b.get("h_bldg", b.h), errors="coerce").fillna(b.h)
    H, A = w.H, w.A
    u, d = w.usage.fillna("").astype(str), w.detail.fillna("").astype(str)
    wood = w.cls.fillna("").astype(str).eq("ordinary building")
    kind = b.kind.astype(str)
    # one random number per building (its key), so a building's pieces agree
    keys = pd.Index(w.key.unique())
    rng = np.random.default_rng(53)
    r1 = pd.Series(rng.random(len(keys)), index=keys).reindex(w.key).values
    r2 = pd.Series(rng.random(len(keys)), index=keys).reindex(w.key).values
    r1, r2 = pd.Series(r1, index=idx), pd.Series(r2, index=idx)
    granite_area = _in_boxes(b, TK.get("granite_areas", []))
    flagship = _in_boxes(b, TK.get("flagship_areas", []))

    # 1. by usage
    style = pd.Series("tiled", index=idx, dtype=object)
    style[u.eq("apartment building")] = "mansion"
    style[u.eq("house") | (u.isin(["house with shop", "house with workshop"]) & (H < 12))] = "wooden"
    style[u.isin(FACTORY_U)] = "factory"
    style[u.isin(FACTORY_U) & (H >= 24)] = "tiled"
    style[u.eq("education, culture, welfare") | d.isin(CIVIC_D - {"religion"})] = "civic"
    style[u.eq("government")] = "government"
    style[d.eq("religion")] = np.where(H[d.eq("religion")] < 25, "temple", "civic")
    style[wood & (H < 12) & ~d.eq("religion")] = "wooden"
    # 2. offices, shops, hotels by size
    com = u.isin(COMMERCE | {"house with workshop"}) & ~style.isin(["wooden"]) & ~d.eq("religion")
    zak = com & (A < TK.get("zakkyo_area", 300.0)) & (H >= TK.get("zakkyo_min_h", 8.0)) & (H < 60)
    style[zak] = "zakkyo"
    dep = com & u.eq("commercial") & (A >= TK.get("depato_area", 1500.0)) & (H < TK.get("depato_max_h", 70.0)) & (H >= 15)
    style[dep] = "depato"
    mid = com & ~zak & ~dep & (H >= 30) & (H < TK.get("tower_h", 100.0))
    style[mid] = np.where(r1[mid] < 0.4, "glass", np.where(r1[mid] < 0.65, "granite", "tiled"))
    flag = com & flagship & (H >= 15) & (H < 80) & ~zak
    style[flag] = np.where(r2[flag] < 0.4, "glass", "depato")      # (M4 fix round: more light stone flagships)
    tower = com & (H >= TK.get("tower_h", 100.0))
    gshare = np.where(granite_area[tower], TK.get("granite_area_share", 0.7), TK.get("granite_share", 0.25))
    style[tower] = np.where(r2[tower] < gshare, "granite", "glass")
    # apartments: tower mansions keep their balconies; offices of the government over 60 m are towers in stone
    style[u.eq("government") & (H >= 60)] = "granite"
    # 3. a tower's stone podium
    podium = (H >= TK.get("tower_h", 100.0)) & (h < TK.get("podium_h", 40.0)) & (h < TK.get("podium_k", 0.45) * H) \
        & style.isin(["glass"]) & (w.n > 1)
    style[podium] = "granite"
    # 4. OSM-only buildings
    osm = u.eq("")
    if osm.any():
        tag = w.tag.map(osm_style)
        by_kind = kind.map({"village": "zakkyo", "house": "wooden", "civic": "civic", "factory": "factory",
                            "tower": "glass", "slab": "mansion", "podium": "depato", "midrise": "tiled"}).fillna("tiled")
        style[osm] = tag.where(tag.notna(), by_kind)[osm]
        style[osm & kind.eq("tower") & (r2 < 0.3)] = "granite"
        # the government quarter PLATEAU leaves out (Kasumigaseki, Nagatacho: OSM's outlines stand in)
        gov = osm & _in_boxes(b, TK.get("government_areas", [])) & ~style.isin(["temple", "wooden"]) & (H >= 9)
        style[gov] = "government"
    # landmark towers are offices
    style[(b.h_src == "landmark") & (h >= 60) & ~style.isin(["mansion", "granite"])] = "glass"
    # 5. the sign streets: wall-sized boards and screens on a share of the commercial fronts
    zones = TK.get("sign_zones", [])
    if zones:
        sf = sign_fronts(b)
        r3 = pd.Series(np.random.default_rng(71).random(len(keys)), index=keys).reindex(w.key).values
        share = sf.zone.map(lambda k: zones[k].get("share", 0.4) if k >= 0 else 0.0).values
        on = sf.front.values & (r3 < share) & style.isin(["zakkyo", "tiled", "depato", "granite", "glass"]).values \
            & (H < 60).values & (b.h_src != "landmark").values
        style[on] = "signs"
        print(f"sign streets: {int(on.sum()):,} pieces signs ({int(sf.front.sum()):,} fronting the zones' streets)")
    return style.values
