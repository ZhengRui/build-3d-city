"""The uk-london preset's code (London, M4): building kinds are europe-west's (Paris's M2 rules, which in London,
with no construction dates, come down to height, shape and OSM tags), facade styles and roof shapes are London's
own (presets/uk-london.toml lists the styles; the viewer's facade.js draws them).

London has no construction year in open data (OSM start_date on 0.5 % of buildings), so the style comes from
what does exist (region_research.md §5.3):
  - the kind (europe-west's building_kind: tower, civic, factory, shed; the rest by height and footprint)
  - the OSM building tag (house and terrace = terraced houses: 97 % of London's `house` share walls; office,
    commercial; apartments, residential)
  - height and footprint
  - the place: [facade.london] conservation-area names mapped to a character (Belgravia stucco, Bloomsbury
    Georgian, Wapping warehouses, Churchill Gardens estate...), hand-drawn character areas (the City's offices,
    the glass clusters, Maritime Greenwich) and the districts counted as the west (Westminster, Camden: mansion
    blocks and Georgian squares where the east and south have Victorian terraces and estates)
  - Historic England's listed buildings: a listed point on a small terrace outside the Georgian areas makes it
    Georgian more often than Victorian
Rules, in order (a later rule wins), with seeded random shares where the evidence only says "a mix":
  1. low rows (to 18 m, not offices, not civic): georgian in the west and in Georgian areas (stucco in stucco
     areas), victorian elsewhere; a listed one there georgian two in three times
  2. 5-8 storey blocks (18-32 m): mansion blocks in the west (mansion_west share), estates or modern elsewhere;
     estates in estate areas
  3. 32-50 m: estates or modern; towers (kind tower): glass in the glass areas and for offices, residential
     towers glass (tower_glass_resi share) or modern
  4. offices (office, commercial, bank tags) 12-50 m: portland / glass / modern by the office_* shares in the
     City's and Westminster's office areas, mostly modern elsewhere
  5. civic: portland in Portland-stone areas (Whitehall, the Strand, the City), civic (red brick and stone)
     elsewhere; factory, shed as their kinds; warehouses in the docks' areas (9-35 m)
  6. a building of OSM parts takes its whole's style; its thin parts over the roof are spires (europe-west's)
"""
import numpy as np
import pandas as pd
import geopandas as gpd

from ... import config
from ..europe_west import KIND_FIELDS, building_kind, col  # noqa: F401  (04_buildings uses them)

CFG = config.get()
LON = CFG["facade"].get("london", {})
RELIGIOUS = {"church", "cathedral", "chapel", "basilica", "synagogue", "mosque", "temple", "religious", "monastery"}
HOUSE_TAGS = {"house", "terrace", "semidetached_house", "detached", "residential", "yes", "apartments", "retail"}
OFFICE_TAGS = {"office", "commercial", "bank", "hotel"}


def _places(b) -> pd.DataFrame:
    """Per building (by its representative point): character from the conservation areas and the city's areas
    ("" where none), west (in one of LON["west_districts"]), listed (a listed-building point on the footprint)."""
    from ...common import districts
    idx = b.index
    pt = gpd.GeoDataFrame(geometry=b.geometry.representative_point(), crs=b.crs)
    char = pd.Series("", index=idx, dtype=object)
    ll = pt.to_crs(4326).total_bounds
    box = (ll[0] - 0.01, ll[1] - 0.01, ll[2] + 0.01, ll[3] + 0.01)
    # the city's own areas (lon/lat polygons, later ones win); the conservation areas, smaller and named, win over them
    for name, a in LON.get("areas", {}).items():
        from shapely.geometry import Polygon
        zone = gpd.GeoSeries([Polygon(a["polygon"])], crs=4326).to_crs(b.crs).iloc[0]
        inz = pt.within(zone).values
        char[inz] = a["character"]
        print(f"london area {name} ({a['character']}): {int(inz.sum()):,} buildings")
    # conservation areas: a name containing a key (case-insensitive) gives its character; the smallest area wins
    cons = LON.get("conservation", {})
    if cons.get("path"):
        p = _raw(cons["path"])
        if p.exists():
            ca = gpd.read_file(p, bbox=box)[["name", "geometry"]].to_crs(b.crs)
            keys = {k.lower(): v for k, v in cons.get("characters", {}).items()}
            ca["char"] = ca.name.fillna("").str.lower().map(
                lambda n: next((v for k, v in keys.items() if k in n), ""))
            ca = ca[ca.char != ""].assign(a=lambda d: d.area).sort_values("a", ascending=False)
            for r in ca.itertuples():          # the biggest first: smaller ones inside them win
                char[pt.within(r.geometry).values] = r.char
            print(f"london: {int((char != '').sum()):,} buildings in {len(ca)} conservation areas with a character")
    west = pd.Series(False, index=idx)
    wd = LON.get("west_districts", [])
    if wd:
        d = districts()
        d = d[d.name.isin(wd)].to_crs(b.crs)
        if len(d):
            west = pd.Series(pt.within(d.union_all()).values, index=idx)
    listed = pd.Series(False, index=idx)
    lp = LON.get("listed", "")
    if lp and _raw(lp).exists():
        li = pd.read_csv(_raw(lp), usecols=["name", "point", "listed-building-grade"])
        xy = li.point.str.extract(r"POINT \(([-\d.]+) ([-\d.]+)\)").astype(float)
        keep = xy[0].between(box[0], box[2]) & xy[1].between(box[1], box[3])
        li = gpd.GeoDataFrame(li[keep], geometry=gpd.points_from_xy(xy[0][keep], xy[1][keep]), crs=4326).to_crs(b.crs)
        hit = gpd.sjoin(li[["geometry"]], gpd.GeoDataFrame(geometry=b.geometry.values, index=idx, crs=b.crs),
                        predicate="within")
        listed[listed.index.isin(hit["index_right"].unique())] = True
        print(f"london: {int(listed.sum()):,} buildings with a listed-building point ({len(li):,} points)")
    return pd.DataFrame({"char": char, "west": west, "listed": listed}, index=idx)


def _raw(p):
    from ...common import DATA
    return DATA / "raw" / p


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles): the module docstring's rules."""
    idx = b.index
    h = b.get("h_bldg", b.h).fillna(b.h)
    kind = b.kind.astype(str)
    a = b.geometry.area
    tag = col(b, "osm_building").fillna("").astype(str)
    pl = _places(b)
    char, west, listed = pl.char, pl.west, pl.listed
    rng = np.random.default_rng(23)
    r1 = pd.Series(rng.random(len(b)), index=idx)
    r2 = pd.Series(rng.random(len(b)), index=idx)
    office = tag.isin(OFFICE_TAGS) | char.eq("offices") & ~tag.isin(["apartments", "residential", "house", "terrace"])
    homes = ~office & ~kind.isin(["civic", "factory", "shed", "tower"])
    old_area = char.isin(["georgian", "stucco", "greenwich"])
    style = pd.Series("victorian", index=idx, dtype=object)
    # 1. low rows: terraces
    low = homes & (h < 18)
    # (the west outside its Georgian areas: Georgian three in five, the rest Victorian rebuilds)
    terrace = np.where(old_area | (west & (r2 < LON.get("georgian_west", 0.6))), "georgian", "victorian")
    style[low] = pd.Series(terrace, index=idx)[low]
    style[low & ~(west | old_area) & listed & (r1 < 0.67)] = "georgian"
    style[low & char.eq("stucco")] = "stucco"
    style[low & char.eq("victorian")] = "victorian"
    # 2. 5-8 storeys
    mid = homes & (h >= 18) & (h < 32)
    mid_style = np.where(west & (r1 < LON.get("mansion_west", 0.55)), "mansion",
                         np.where(r2 < 0.5, "estate", "modern"))
    style[mid] = pd.Series(mid_style, index=idx)[mid]
    style[mid & char.eq("stucco") & (h < 30)] = "stucco"   # (Belgrave Square's are 20-28 m to the chimneys)
    style[mid & char.eq("georgian") & (h < 21)] = "georgian"
    style[mid & char.eq("mansion")] = "mansion"
    # 3. taller
    upper = homes & (h >= 32)
    style[upper] = np.where(r2[upper] < 0.5, "estate", "modern")
    style[(homes & (h >= 9)) & char.eq("estate")] = "estate"
    tower = kind.eq("tower")
    glass_area = char.isin(["glass", "offices"])
    resi = tag.isin(["apartments", "residential", "dormitory"])
    style[tower] = np.where((resi & ~glass_area & (r1 >= LON.get("tower_glass_resi", 0.35)))[tower], "modern", "glass")
    style[tower & char.eq("estate") & resi] = "estate"
    # 4. offices
    off = office & ~tower & ~kind.isin(["civic", "factory", "shed"]) & (h >= 9)
    core = char.isin(["offices", "portland"])
    pp, pg = LON.get("office_portland", 0.45), LON.get("office_glass", 0.3)
    style[off & core] = np.where(r1[off & core] < pp, "portland", np.where(r1[off & core] < pp + pg, "glass", "modern"))
    rest = off & ~core
    style[rest] = np.where(r1[rest] < 0.2, "portland", np.where(r1[rest] < 0.4, "glass", "modern"))
    # (M4 fix round, critic: the West End's low-rise all one beige stone) the west's offices outside the stone
    # areas: Edwardian red brick and terracotta (mansion) and stock brick (georgian) commercial blocks, stone
    # where listed (half of those) or one in ten, glass and modern the rest
    wrest = rest & west & (h < 40)
    stone_w = listed & (r2 < 0.5) | (r2 < LON.get("west_office_portland", 0.1))
    style[wrest] = np.where(stone_w[wrest], "portland", np.where(r1[wrest] < 0.4, "mansion",
                            np.where(r1[wrest] < 0.62, "georgian", np.where(r1[wrest] < 0.72, "glass", "modern"))))
    style[off & (h < 14) & ~core] = pd.Series(terrace, index=idx)[off & (h < 14) & ~core]   # shops and small offices in a row
    # the City and Westminster's untagged mid-rise blocks are offices too
    untagged = homes & core & tag.isin(["yes", ""]) & (h >= 14)
    style[untagged] = np.where(r1[untagged] < pp, "portland", np.where(r1[untagged] < pp + pg, "glass", "modern"))
    style[(homes | off) & char.eq("glass") & (h >= 25)] = "glass"
    # 5. civic, industry, warehouses
    civic = kind.eq("civic")
    style[civic] = "civic"
    style[civic & (core | char.eq("portland")) & (h >= 10) & ~tag.isin(RELIGIOUS)] = "portland"
    style[civic & west & (h >= 14) & ~tag.isin(RELIGIOUS) & (r2 < 0.4)] = "portland"
    # houses in the Georgian and stucco areas used as offices, colleges, embassies (Bedford Square, Belgrave
    # Square) keep their terrace's style
    house_use = (office | (civic & ~tag.isin(RELIGIOUS) & (a < 800))) & char.isin(["georgian", "stucco"]) & (h < 22) & ~tower
    style[house_use] = np.where(char[house_use].eq("stucco"), "stucco", "georgian")
    # (M4 fix round, critic: Belgrave Square's houses in red brick) the stucco areas are stucco throughout below
    # 32 m but for churches and towers: the houses used as embassies, institutes and offices included
    style[char.eq("stucco") & (h < 32) & ~tower & ~tag.isin(RELIGIOUS) & ~kind.isin(["factory", "shed"])] = "stucco"
    style[kind.eq("factory")] = "factory"
    style[kind.eq("shed")] = "shed"
    otag = tag.map(osm_style)
    ok = otag.notna() & kind.isin(["factory", "shed"] + ["haussmann", "faubourg", "house", "postwar", "modern"]) \
        & ~(otag.eq("shed") & (h >= 6)) & ~tower
    style[ok] = otag[ok]
    dock = char.eq("warehouse") & (h >= 9) & (h < 35) & ~civic & ~tower & ~office & (r1 < 0.85)
    style[dock] = "warehouse"
    style[tag.eq("warehouse") & (h >= 12) & ~tower] = "warehouse"
    style[char.eq("greenwich") & low] = "georgian"
    style[(col(b, "h_src").astype(str).str.startswith("landmark")) & (h >= 150)] = "glass"
    # parts: one style per building, thin parts over the roof are spires (as europe-west)
    if "part_of" in b:
        parts = b.part_of.notna()
        if parts.any():
            from ...stages.buildings import main_roof as roof_of
            g = pd.DataFrame({"host": b.part_of, "h": b.h, "a": a, "style": style})[parts]
            main_roof = b[parts].groupby("part_of").apply(roof_of)
            main_style = g.sort_values("a").groupby("host")["style"].last()
            style[parts] = b.part_of[parts].map(main_style).values
            spire = parts & (a < 120) & (b.h > b.part_of.map(main_roof) + 5)
            style[spire] = "spire"
    print("london styles: " + ", ".join(f"{k} {v:,}" for k, v in style.value_counts().items()))
    return style.values


def roof_shapes(b, style) -> pd.DataFrame:
    """Per building: roof shape ("mansard", "pitched" or "") and material (1 slate, 2 tile, 0 flat). London's
    roofs are mostly flat behind parapets or shallow slate pitches (region_research.md §4.2, §4.5): Victorian
    terraces pitched slate; Georgian and stucco terraces a parapet over a hidden slate roof (flat here, slate
    coloured), a slate mansard storey on a fifth (Georgian) to two fifths (stucco); mansion blocks red tile or
    slate pitches on some; Portland stone blocks flat lead, a slate mansard on some; churches pitched slate.
    No zinc, no Paris mansards on terraces."""
    idx = b.index
    style = pd.Series(style, index=idx).astype(str)
    h, a = b.h, b.geometry.area
    tag = col(b, "osm_building").fillna("").astype(str)
    r = pd.Series(np.random.default_rng(29).random(len(b)), index=idx)
    shape = pd.Series("", index=idx, dtype=object)
    mat = pd.Series(0, index=idx)
    s = style
    shape[s.eq("victorian") & (h >= 4) & (h < 15) & (a >= 15) & (a < 1500)] = "pitched"
    shape[s.eq("georgian") & (h >= 12) & (a >= 40) & (r < 0.2)] = "mansard"
    shape[s.eq("stucco") & (h >= 13) & (a >= 40) & (r < 0.4)] = "mansard"
    shape[s.eq("mansion") & (h >= 12) & (r < 0.3)] = "pitched"
    # (M4 fix round, critic: flat grey roofs everywhere) slate mansards with dormers on two in five of the stone
    # and red-brick commercial blocks under 45 m (pre-1914), one in seven of the taller ones
    shape[s.eq("portland") & (h >= 15) & (a < 4000) & (r < np.where(h < 45, 0.4, 0.15))] = "mansard"
    shape[s.eq("mansion") & (h >= 12) & (r >= 0.3) & (r < 0.6)] = "mansard"
    shape[s.eq("warehouse") & (a < 1500) & (r < 0.25)] = "pitched"
    shape[s.eq("civic") & tag.isin(RELIGIOUS) & (h >= 5)] = "pitched"
    shape[s.eq("civic") & ~tag.isin(RELIGIOUS) & (h >= 5) & (h < 20) & (a < 3000) & (r < 0.3)] = "pitched"
    shape[s.eq("shed") & (h >= 4) & (a >= 15) & (r < 0.3)] = "pitched"
    mat[shape.ne("")] = 1
    mat[s.eq("mansion") & shape.eq("pitched")] = 2
    mat[s.eq("shed") & shape.eq("pitched")] = 2
    # (flat tops of the terraces: slate, the hidden butterfly roofs seen from above)
    mat[s.isin(["georgian", "stucco"]) & shape.eq("")] = 1
    return pd.DataFrame({"shape": shape, "material": mat.astype(int)}, index=idx)


SHOP_STYLES = {"georgian", "victorian", "mansion", "portland", "modern", "stucco", "estate", "warehouse", "civic"}


def shopfronts(b) -> np.ndarray:
    """Buildings with a shopfront ground floor (06_tiles puts their seed in [0, 0.5); facade.js draws the
    shopfront with city.json facade.shopSeed): those holding an OSM shop or street-level amenity node
    (scripts/m4f_shops.py: osm_shops.json in the data folder) and, in the centre, those fronting a primary or
    secondary road (within [facade.london] shop_road_m of its centreline: the high streets' shopfronts, Ludgate Hill,
    the Strand, Oxford Street), low and mid-rise buildings of the shop styles only; a few in ten elsewhere (corner
    shops, pubs) by the seed as before. (M4 fix round, critic: Ludgate Hill's ground floors flat walls)"""
    from ...common import DATA
    style = b["facade"].astype(str)
    h = b.get("h_bldg", b.h).fillna(b.h)
    ok = style.isin(SHOP_STYLES) & (h < 60) & (h >= 6)
    shop = pd.Series(False, index=b.index)
    p = DATA / LON.get("shops", "osm_shops.json")
    if p.exists():
        import json
        xy = np.array(json.loads(p.read_text()))
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=4326).to_crs(b.crs)
        hit = gpd.sjoin(pts, gpd.GeoDataFrame(geometry=b.geometry.buffer(2.0).values, index=b.index, crs=b.crs),
                        predicate="within")
        shop[shop.index.isin(hit["index_right"].unique())] = True
        print(f"london shopfronts: {int(shop.sum()):,} buildings with a shop or amenity node ({len(pts):,} nodes)")
    rp = DATA / "roads.gpkg"
    if rp.exists():
        rd = gpd.read_file(rp, layer="ways", columns=["highway", "elevated"])
        rd = rd[rd.highway.isin(LON.get("shop_roads", ["primary", "secondary", "trunk"])) & ~rd.elevated.fillna(False).astype(bool)]
        rd = rd.to_crs(b.crs)
        front = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=b.geometry.values, index=b.index, crs=b.crs),
                                  rd[["geometry"]], max_distance=LON.get("shop_road_m", 14.0), how="inner")
        on_road = pd.Series(b.index.isin(front.index.unique()), index=b.index)
        from ...common import districts
        d = districts().to_crs(b.crs)
        d = d[d.name.isin(LON.get("west_districts", []) + ["City of London"])]
        cen = pd.Series(b.geometry.representative_point().within(d.union_all()).values, index=b.index)
        print(f"london shopfronts: {int((on_road & cen).sum()):,} buildings on a main road in the centre")
        shop |= on_road & cen
    r = pd.Series(np.random.default_rng(31).random(len(b)), index=b.index)
    shop |= r < 0.12
    return (shop & ok).values

