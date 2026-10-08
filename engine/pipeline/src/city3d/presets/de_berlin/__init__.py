"""The de-berlin preset's code (Berlin, M4): building kinds are europe-west's (Berlin's M2 kinds: haussmann,
faubourg, postwar, modern, tower, civic, factory, shed from height, the ALKIS function through [buildings.kinds]
field_kind and OSM's tags), facade styles, roof shapes and shopfronts are Berlin's own (presets/de-berlin.toml lists
the styles; the viewer's facade.js draws them).

Berlin has what London lacked: per building the LoD2's ALKIS function (`function`, every solid), roof type
(`rooftype`: 1000 flat, 2100 mono-pitch, 3100 gabled, 3200 hipped, 5000 mixed, 9999 other) and eaves (`eave_h`),
the Umweltatlas storeys (`geschosse`); per block the Umweltatlas structure type (Realnutzung 2024 `typ_klar`: the
period and form of the block, region_research.md §5.1). Rules, in order (a later rule wins), with seeded random
shares where the evidence only says "a mix":
  1. the block's structure type ([facade.berlin] structure): Gründerzeit blocks (1870er - 1918) altbau on the
     street (within front_m of a street centre line) and althof behind, low pieces (under 10 m) althof;
     Lückenschluss nach 1945 and heterogeneous infill nachkrieg; Großsiedlung und Punkthochhäuser platte; Zeilenbau
     of the 1950s-70s nachkrieg; 1920s-40s blocks nachkrieg or klinker (two in five); Geschosswohnungsbau der 1990er
     Jahre neubau; Kerngebiet and dense mixed use neubau or beton (by the storey height); administration beton;
     Altbau-Schule klinker, Neubau-Schule beton; Kirche kirche
  2. the building itself over its block: the storey height (eave over the Umweltatlas storeys) and the roof tell a
     surviving Gründerzeit house from post-war infill: in the old blocks a flat-roofed piece under new_storey m a
     storey is nachkrieg (or platte from 9 storeys), in the infill blocks a piece over old_storey m a storey with a
     pitched or mixed roof is altbau
  3. offices (ALKIS Bürogebäude, Handel; OSM office, commercial): glass from 25 m in the glass areas (glass_core
     share), neubau or beton elsewhere; towers (kind tower) glass, platte when residential in a platte block or area
  4. civic (kind civic): kirche for churches; old (storey over 4 m or a pitched roof) sandstein, or klinker for
     schools and two in five of the rest; newer beton
  5. factory and shed as their kinds, klinker for an old multi-storey factory (Gewerbehof, 12 m up, over old_storey)
  6. the hand-drawn areas ([facade.berlin.areas] in city.toml, later ones win): kma (Karl-Marx-Allee's first
     section), hansa (the Hansaviertel), platte, glass, neubau, sandstein, beton: a character for the area's
     buildings of the kinds it names
  7. a building of OSM parts takes its whole's style; its thin parts over the roof are spires (europe-west's)
"""
import numpy as np
import pandas as pd
import geopandas as gpd

from ... import config
from ..europe_west import KIND_FIELDS, building_kind, col  # noqa: F401  (04_buildings uses them)

CFG = config.get()
BER = CFG["facade"].get("berlin", {})
RELIGIOUS = {"church", "cathedral", "chapel", "basilica", "synagogue", "mosque", "temple", "religious", "monastery"}
# ALKIS functions (the LoD2's `function`, 31001_*)
CHURCH_F = {"31001_3040", "31001_3041", "31001_3042", "31001_3043", "31001_3044", "31001_3046"}
OFFICE_F = {"31001_2020", "31001_2010", "31001_2030", "31001_2040", "31001_2050", "31001_2054", "31001_2056",
            "31001_2070", "31001_2071", "31001_2080", "31001_3010"}
SCHOOL_F = {"31001_3020", "31001_3021", "31001_3022", "31001_3023"}
STONE_F = {"31001_3011", "31001_3012", "31001_3015", "31001_3030", "31001_3031", "31001_3032", "31001_3034",
           "31001_3037", "31001_3090", "31001_3091"}
HOME_F = {"31001_1000", "31001_1010", "31001_1020", "31001_1021", "31001_1022", "31001_1023", "31001_1024",
          "31001_1100", "31001_1110", "31001_1120", "31001_1130", "31001_1131", "31001_2310"}
OFFICE_TAGS = {"office", "commercial", "bank", "hotel", "retail"}
# rooftype codes: pitched (gabled, hipped, half-hipped, pyramid, shed-dormered), mixed and other
PITCHED_RT = {"3100", "3200", "3300", "3400", "3500", "4000"}
MIXED_RT = {"5000", "9999"}


def _structure(b) -> pd.Series:
    """The Umweltatlas block structure type (typ_klar) at each building's inside point ("" where none)."""
    from ...common import DATA
    p = BER.get("structure", "")
    out = pd.Series("", index=b.index, dtype=object)
    if not p or not (DATA / "raw" / p).exists():
        print(f"berlin: no structure layer ({p!r}): the styles from the buildings' own fields only")
        return out
    r = gpd.read_file(DATA / "raw" / p, columns=["typ_klar"]).to_crs(b.crs)
    pt = gpd.GeoDataFrame(geometry=b.geometry.representative_point().values, index=b.index, crs=b.crs)
    j = gpd.sjoin(pt, r[["typ_klar", "geometry"]], predicate="within")
    j = j[~j.index.duplicated()]
    out.loc[j.index] = j["typ_klar"].fillna("").astype(str)
    print(f"berlin: {int((out != '').sum()):,} of {len(b):,} buildings in a block of the structure layer")
    return out


def _areas(b) -> pd.Series:
    """The hand-drawn character areas ([facade.berlin.areas]: name = {character, polygon [[lon, lat], ...]} or
    {character, district = "<name in [districts]>"}), later ones win; "" outside."""
    from shapely.geometry import Polygon
    from ...common import districts
    pt = gpd.GeoDataFrame(geometry=b.geometry.representative_point().values, index=b.index, crs=b.crs)
    char = pd.Series("", index=b.index, dtype=object)
    for name, a in BER.get("areas", {}).items():
        if "district" in a:
            d = districts()
            zone = d[d.name == a["district"]].to_crs(b.crs).union_all()
        else:
            zone = gpd.GeoSeries([Polygon(a["polygon"])], crs=4326).to_crs(b.crs).iloc[0]
        inz = pt.within(zone).values
        char[inz] = a["character"]
        print(f"berlin area {name} ({a['character']}): {int(inz.sum()):,} buildings")
    return char


def _near_road(b, highways, depth) -> pd.Series:
    """Whether each building's inside point lies within `depth` m of the kerb of a road of the classes `highways`
    (None: any road class but footways, paths and service ways): its centre line's distance less half the road's
    width (roads.gpkg's width, kerb to kerb, plus 4 m of pavement each side). A front house is about 12 m deep
    (its point 6-10 m behind that line: the peak of the distances of Berlin's Wohnhäuser);
    its point, not its outline, since a courtyard wing touches the front house and its outline reaches the street."""
    from ...common import DATA
    rp = DATA / "roads.gpkg"
    if not rp.exists():
        return pd.Series(True, index=b.index)
    rd = gpd.read_file(rp, layer="ways", columns=["highway", "elevated", "width"])
    skip = {"footway", "path", "cycleway", "steps", "bridleway", "corridor", "elevator", "platform", "proposed",
            "construction", "track", "service", "pedestrian", "rail", "light_rail", "tram", "subway", "narrow_gauge",
            "monorail", "funicular", "miniature", "disused", "abandoned", "preserved"}
    keep = rd.highway.isin(highways) if highways else ~rd.highway.isin(skip) & rd.highway.notna()
    rd = rd[keep & ~rd.elevated.fillna(False).astype(bool)].to_crs(b.crs)
    half = pd.to_numeric(rd["width"], errors="coerce").fillna(10.0).clip(5, 60) / 2 + 4.0
    rd = gpd.GeoDataFrame({"half": half.values}, geometry=rd.geometry.values, crs=b.crs)
    pt = gpd.GeoDataFrame(geometry=b.geometry.representative_point().values, index=b.index, crs=b.crs)
    hit = gpd.sjoin_nearest(pt, rd, max_distance=depth + 40.0, how="inner", distance_col="d")
    hit = hit[hit["d"] <= hit["half"] + depth]
    return pd.Series(b.index.isin(hit.index.unique()), index=b.index)


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles): the module docstring's rules."""
    idx = b.index
    h = b.get("h_bldg", b.h).fillna(b.h)
    kind = b.kind.astype(str)
    tag = col(b, "osm_building").fillna("").astype(str)
    fn = col(b, "function").fillna("").astype(str)
    rt = col(b, "rooftype").fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    storeys = pd.to_numeric(col(b, "geschosse"), errors="coerce")
    eave = pd.to_numeric(col(b, "eave_h"), errors="coerce").fillna(h)
    sh = (eave / storeys.where(storeys >= 1)).fillna(h / np.maximum(1, np.round(h / 3.4)))
    typ = _structure(b)
    area = _areas(b)
    front = _near_road(b, None, BER.get("front_m", 12.0))
    rng = np.random.default_rng(37)
    r1 = pd.Series(rng.random(len(b)), index=idx)
    r2 = pd.Series(rng.random(len(b)), index=idx)
    old_s, new_s = BER.get("old_storey", 3.35), BER.get("new_storey", 3.15)
    flat = rt.isin(["1000", ""]) | (rt.eq("2100") & ((h - eave) < 1.2))
    sloped = rt.isin(PITCHED_RT | MIXED_RT) | (rt.eq("2100") & ((h - eave) >= 1.2))
    office = fn.isin(OFFICE_F) | tag.isin(OFFICE_TAGS)
    homes = ~kind.isin(["civic", "factory", "shed", "tower"])
    T = typ.str
    gruender = T.contains("1870er - 1918") | T.startswith("Blockbebauung der Gründerzeit")
    infill = T.contains("Lückenschluss nach 1945") | T.startswith("Heterogene")
    gross = T.startswith("Großsiedlung")
    zeile50 = T.startswith("Freie Zeilenbebauung")
    b20 = T.contains("1920er")
    neu90 = T.startswith("Geschosswohnungsbau der 1990er")
    kern = typ.eq("Kerngebiet") | T.startswith("Mischgebiet")
    gewerbe = T.startswith("Gewerbe- und Industriegebiet") | T.startswith("Ver- und Entsorgung")
    verw = typ.eq("Verwaltung") | T.startswith("Sicherheit")

    # 1. the block's type (homes; offices among them get theirs in 3.)
    style = pd.Series("nachkrieg", index=idx, dtype=object)
    style[gruender] = np.where(front[gruender] & (h[gruender] >= 10), "altbau", "althof")
    style[infill] = "nachkrieg"
    style[gross] = "platte"
    style[zeile50] = "nachkrieg"
    style[b20] = np.where(r1[b20] < 0.4, "klinker", "nachkrieg")
    style[neu90] = "neubau"
    style[kern | gewerbe] = np.where(sh[kern | gewerbe] >= old_s, "altbau", np.where(r2[kern | gewerbe] < 0.5, "neubau", "beton"))
    style[verw] = np.where(sh[verw] >= 4.0, "sandstein", "beton")
    # no block type (2 %, the Spree's banks, rail land): by storey height
    none = typ.eq("")
    style[none] = np.where(sh[none] >= old_s, "altbau", "nachkrieg")
    # 2. the building over its block: an old house among infill, infill among old houses (the Lückenschluss)
    old_house = (sh >= old_s) & sloped & (h >= 12) & (h < 32)
    new_house = (sh < new_s) & flat & (h >= 9)
    style[(infill | none | kern) & old_house & homes & ~office] = "altbau"
    style[gruender & new_house & homes] = "nachkrieg"
    style[(gruender | infill) & new_house & homes & (storeys >= 9)] = "platte"
    style[gross & homes & (sh >= old_s) & sloped] = "altbau"     # old houses kept inside a Großsiedlung block
    style[gross & homes & (storeys < 4) & (h < 12)] = "nachkrieg"
    # courtyard wings: Gründerzeit-old pieces off the street; low pieces anywhere in the old blocks
    style[style.eq("altbau") & (~front | (h < 10))] = "althof"
    # 3. offices and towers
    glass_area = area.eq("glass")
    off = office & homes & (h >= 9)
    style[off] = np.where(sh[off] >= old_s + 0.3, np.where(front[off], "altbau", "althof"),
                          np.where(r1[off] < 0.5, "neubau", "beton"))
    style[off & (h >= 25) & (glass_area | kern) & (r2 < BER.get("glass_core", 0.55))] = "glass"
    style[off & (h >= 25) & glass_area & (sh < old_s)] = "glass"
    tower = kind.eq("tower")
    resi = fn.isin(HOME_F) | tag.isin(["apartments", "residential", "dormitory"])
    style[tower] = "glass"
    style[tower & resi] = "platte"
    style[tower & resi & (glass_area | neu90)] = "glass"
    style[tower & ~resi & (sh < 3.2) & ~glass_area & (r1 < 0.5)] = "beton"
    # 4. civic
    civic = kind.eq("civic")
    old_civ = (sh >= 4.0) | sloped
    style[civic] = np.where(old_civ[civic], np.where(r2[civic] < 0.6, "sandstein", "klinker"), "beton")
    style[civic & fn.isin(SCHOOL_F) & old_civ] = np.where(r1[civic & fn.isin(SCHOOL_F) & old_civ] < 0.7, "klinker", "sandstein")
    style[civic & fn.isin(STONE_F) & old_civ] = "sandstein"
    style[civic & (T.startswith("Altbau-Schule"))] = "klinker"
    church = civic & (fn.isin(CHURCH_F) | tag.isin(RELIGIOUS) | (typ.eq("Kirche") & (h >= 12)))
    style[church] = "kirche"
    # 5. industry
    style[kind.eq("factory")] = "factory"
    loft = kind.eq("factory") & (h >= 12) & (sh >= old_s) & (gruender | gewerbe | kern | infill)
    style[loft] = "klinker"
    style[kind.eq("shed")] = "shed"
    otag = tag.map(osm_style)
    ok = otag.notna() & kind.isin(["factory", "shed"]) & ~(otag.eq("shed") & (h >= 6))
    style[ok] = otag[ok]
    style[style.eq("shed") & (h >= 8)] = "althof"
    # 6. the hand-drawn areas: their character for the kinds it applies to
    z = area.eq("kma") & homes & (h >= 18)                  # (the blocks are 7-9 storeys, 28 m)
    style[z] = "kma"
    z = area.eq("hansa") & ~kind.isin(["shed", "factory"]) & ~church & (h >= 6)
    style[z] = "hansa"
    z = area.eq("platte") & (homes | tower) & resi & (h >= 15) & (sh < old_s)
    style[z] = "platte"
    z = area.eq("neubau") & (homes | office) & ~tower & (h >= 12) & (sh < old_s + 0.3) & ~style.isin(["platte", "glass"])
    style[z] = np.where(r1[z] < 0.75, "neubau", "beton")
    z = area.eq("sandstein") & (homes | civic) & ~church & (h >= 10) & (sh >= 3.8)
    style[z] = "sandstein"
    z = area.eq("beton") & (homes | civic) & ~church & (h >= 9) & (sh < 4.2)
    style[z] = np.where(r1[z] < 0.65, "beton", "glass")
    style[(col(b, "h_src").astype(str).str.startswith("landmark")) & (h >= 150)] = "glass"
    # 7. parts: one style per building, thin parts over the roof are spires (as europe-west)
    if "part_of" in b:
        parts = b.part_of.notna()
        if parts.any():
            from ...stages.buildings import main_roof as roof_of
            a = b.geometry.area
            g = pd.DataFrame({"host": b.part_of, "h": b.h, "a": a, "style": style})[parts]
            main_roof = b[parts].groupby("part_of").apply(roof_of)
            main_style = g.sort_values("a").groupby("host")["style"].last()
            style[parts] = b.part_of[parts].map(main_style).values
            spire = parts & (a < 120) & (b.h > b.part_of.map(main_roof) + 5)
            style[spire] = "spire"
    print("berlin styles: " + ", ".join(f"{k} {v:,}" for k, v in style.value_counts().items()))
    return style.values


def roof_shapes(b, style) -> pd.DataFrame:
    """Per building: roof shape ("berliner", "pitched", "mansard" or "") and material (1 slate or zinc, 2 clay
    tile, 3 flat mineral or green, 0 unknown) from the LoD2's roof type and eaves (region_research.md §4.1-4.2):
    gabled, hipped and pyramid roofs (3100-4000) pitched; mixed and other roofs (5000, 9999) and mono-pitch roofs
    rising over 1.5 m (2100: the Berliner Dach's flat back) on the Altbau the Berliner Dach (06_tiles "berliner":
    a 60-degree front slope with dormers over a flat top), pitched on the rest; flat (1000) flat. Tile on three in
    five Altbau roofs and most pitched ones, slate and zinc on the rest and on civic, church and sandstone roofs.
    06_tiles takes the rise from the eaves ([tiles] roof_eave)."""
    idx = b.index
    style = pd.Series(style, index=idx).astype(str)
    h, a = b.h, b.geometry.area
    rt = col(b, "rooftype").fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    eave = pd.to_numeric(col(b, "eave_h"), errors="coerce")
    rise = (h - eave).where(eave.notna(), 0.0)
    r = pd.Series(np.random.default_rng(41).random(len(b)), index=idx)
    shape = pd.Series("", index=idx, dtype=object)
    old = style.isin(["altbau", "althof", "kma"])
    big = (a >= 30) & (h >= 6)
    pitched = rt.isin(PITCHED_RT) & (rise >= 1.0)
    mixed = (rt.isin(MIXED_RT) & (rise >= 1.2)) | (rt.eq("2100") & (rise >= 1.5))
    shape[big & pitched] = "pitched"
    shape[big & mixed] = "pitched"
    shape[big & mixed & old & (h >= 12)] = "berliner"
    shape[big & pitched & style.eq("altbau") & (h >= 15) & (rise <= 5)] = "berliner"
    # (the styles whose look is a flat roof: slabs, curtain walls, sheds; landmark styles keep theirs)
    shape[style.isin(["platte", "glass", "hansa", "plain", "spire", "floodlit", "shed"]) & ~pitched] = ""
    mat = pd.Series(3, index=idx)
    # ([facade.berlin] tile_old: the share of the Altbau's, the courtyard wings' and the KMA's roofs in clay tile; the
    # rest 0.6. M4 critic: from the air the Altbau roofs read slate and tar, Kreuzberg's a red-brown tile carpet)
    tile = shape.ne("") & (r < np.where(old, BER.get("tile_old", 0.6), 0.6))
    mat[shape.ne("")] = 1
    mat[tile] = 2
    mat[shape.eq("pitched") & style.isin(["nachkrieg", "althof", "shed", "factory"]) & (r < 0.85)] = 2
    mat[shape.ne("") & style.isin(["sandstein", "kirche", "klinker", "beton", "neubau", "concretepanel", "monument"])] = 1
    # (M10 fix round: concretepanel, the Kanzleramt zone's pieces kept a red tile cap; monument, the landmark rows' flat
    # tops took the tile's red by chance: the Neue Wache's portico)
    print("berlin roofs: " + ", ".join(f"{k or 'flat'} {v:,}" for k, v in shape.value_counts().items()))
    return pd.DataFrame({"shape": shape, "material": mat.astype(int)}, index=idx)


SHOP_STYLES = {"altbau", "nachkrieg", "neubau", "kma", "platte", "beton", "klinker", "althof"}


def shopfronts(b) -> np.ndarray:
    """Buildings with a shopfront ground floor (06_tiles puts their seed in [0, 0.5); facade.js reads it with
    city.json facade.shopSeed): street-front pieces of the shop styles on a main road ([facade.berlin] shop_roads
    within shop_road_m: Oranienstraße, Bergmannstraße, Kastanienallee's Altbau, the Karl-Marx-Allee's arcades),
    those of ALKIS's shop-and-flats functions, and one in eight elsewhere (the Spätis and corner pubs)."""
    style = b["facade"].astype(str)
    h = b.get("h_bldg", b.h).fillna(b.h)
    fn = col(b, "function").fillna("").astype(str)
    ok = style.isin(SHOP_STYLES) & (h < 60) & (h >= 6)
    road = _near_road(b, BER.get("shop_roads", ["primary", "secondary", "tertiary"]), BER.get("shop_road_m", 12.0))
    mixed = fn.isin({"31001_1120", "31001_2310", "31001_1100", "31001_2050", "31001_2054"})
    r = pd.Series(np.random.default_rng(31).random(len(b)), index=b.index)
    shop = (road & (r < 0.85)) | mixed | (r < 0.08)
    shop &= ~style.eq("althof") | mixed
    print(f"berlin shopfronts: {int((shop & ok & road).sum()):,} on a main road, {int((shop & ok & mixed).sum()):,} "
          f"with shops by their function")
    return (shop & ok).values
