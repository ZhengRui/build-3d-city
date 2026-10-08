"""The hk-hongkong preset's code (Hong Kong, M4; tables in presets/hk-hongkong.toml): building kinds and facade styles.
Its rooftop clutter is china-south's programmes under Hong Kong's style names (rooftops.py).

Kinds (04_buildings) are china-south's shape rules (tower, slab, factory, house, village, podium, midrise), applied per
BUILDING, not per Lands Department row: LandsD splits a tower into blocks (a wing, a lift core, "Tower 1 (1A)" and
"(1B)"), and its narrow wings came out "slab" beside a "tower" core (M4: 8,826 rows grouped into 2,206 buildings;
slab rows 2,855 -> 2,559, the rest real slab blocks). Touching Tower rows of one height
(within 15 % or 6 m) and one name (the parenthesised block letters left out, or unnamed) are one
building: its kind comes from the union's footprint and aspect and the tallest row. Then:
  - LandsD's Podium rows (shopping and car-park podiums under the estates and towers) and named malls under 60 m are
    "podium" (they were factory, slab or midrise by size; Elements, Olympian City, Festival Walk, LOHAS Park's)
  - stadiums, sports centres, halls, markets, libraries, museums, schools, hospitals, police and fire stations,
    government offices under 60 m are "civic" (Kai Tak Stadium, the Coliseum, LegCo's complex)
  - OSM's tags as china-south's (factory, house, civic), unless the height says tower.

Facade styles (06_tiles), later rules win:
  1. by kind: podium commercial, civic civic, factory factory, house village, slab/tower apartment; midrise tonglau
     under 30 m, composite under 75 m on a plot under 900 m², else apartment
  2. names: "... Building", "... Mansion(s)" (the composite buildings) tonglau or composite by height; "... House"
     towers of 25 m+ (the Housing Authority's blocks) estate; industrial names (Industrial, Factory, Godown,
     Warehouse, Workshop) industrial
  3. land use: in industrial land, industrial under 100 m unless the name is an office's (Tower, Plaza, Square,
     Financial, Centre...: glass from 40 m); in commercial land, 40 m+ with an office's name glass; 150 m+ outside
     residential land glass unless the name is a home's (Court, Garden, Villa, Heights, Terrace...)
  4. OSM's tag (osm_style), on the buildings the rules above left in a residential style
  5. landmark towers (60 m+ with a landmark height) glass; colonial civic buildings by name colonial
"""
import re

import numpy as np
import pandas as pd

from ... import config

CFG = config.get()
OSM_KIND = CFG["buildings"]["osm_kind"]          # OSM building tag -> kind

CIVIC_NAME = re.compile(r"stadium|coliseum|sports (?:centre|center|ground)|sports hall|indoor games|arena|leisure|"
                        r"municipal|market\b|library|museum|school|college|university|polytechnic|hospital|clinic|"
                        r"police|fire station|ambulance|government|legislative council|city hall|town hall|"
                        r"community (?:centre|hall)|civic centre|exhibition|convention|cultural centre|post office|"
                        r"court of final|law courts|magistracy|church|cathedral|temple|mosque|station building", re.I)
MALL_NAME = re.compile(r"\bmall\b|shopping|elements|ocean terminal|festival walk|harbour city|olympian city|megabox|"
                       r"\bapm\b|cityplaza|telford plaza|plaza hollywood|langham place|moko|k11|ifc mall|"
                       r"pacific place|times square|landmark atrium|the one\b|\bpodium\b|car park|carpark", re.I)
ESTATE_NAME = re.compile(r"\bHouse$", re.I)
COMPOSITE_NAME = re.compile(r"\bbuilding$|\bmansions?$|\bbuilding\b.*block|commercial building", re.I)
INDUSTRIAL_NAME = re.compile(r"industrial|factory|godown|warehouse|workshop|\bdepot\b|cold storage", re.I)
OFFICE_NAME = re.compile(r"tower|plaza|square|financial|centre|center|bank|exchange|hotel|landmark|place\b|"
                         r"\bone\b|\btwo\b|millennium|quayside|harbourfront|enterprise|corporate|business|"
                         r"commercial|office|trade|international|chamber", re.I)
HOME_NAME = re.compile(r"court|garden|villa|terrace|estate|heights|lodge|residence|apartment|mansion|mount\b|"
                       r"\bblock\b|\bphase\b|tower \d|tower [a-z]\b|tower (?:one|two|three|five|six)|\bseaview\b|"
                       r"\bthe\b|\bhill\b|\bbay\b|house$", re.I)
COLONIAL_NAME = re.compile(r"court of final appeal|french mission|flagstaff house|western market|central police station|"
                           r"magistracy|marine police|kowloon british school|clock tower|murray house|government house|"
                           r"victoria prison|old .*post office|st\.? john'?s cathedral|main building", re.I)


def _names(df: pd.DataFrame) -> pd.Series:
    col = "buildingnameen" if "buildingnameen" in df else None
    n = df[col] if col else pd.Series("", index=df.index)
    if "name" in df:
        n = n.where(n.notna() & (n.astype(str) != ""), df["name"])
    return n.fillna("").astype(str).str.strip()


def _shape_kind(h, a, asp) -> np.ndarray:
    """china-south's shape rules."""
    return np.select(
        [h >= 60,
         (h >= 24) & (asp >= 2.5),
         (h < 24) & (a >= 3000),
         (h < 12) & (a < 250),
         (h >= 12) & (h < 40) & (a < 450),
         (h < 24) & (a >= 1200)],
        ["tower", "slab", "factory", "house", "village", "podium"],
        default="midrise")


def _groups(df: pd.DataFrame) -> pd.Series:
    """A building id per row: the touching LandsD Tower rows of one height and one name (a tower's wings and blocks)
    share one; every other row its own."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    import geopandas as gpd
    n = len(df)
    pos = np.arange(n)
    tower = df.get("buildingblocktype", pd.Series("", index=df.index)).fillna("").astype(str).values == "Tower"
    cand = np.flatnonzero(tower & (df["h"].values >= 12))
    if not len(cand):
        return pd.Series(pos, index=df.index)
    g = gpd.GeoDataFrame({"i": cand}, geometry=df.geometry.values[cand], crs=df.crs)
    g["geometry"] = g.buffer(0.5)
    j = gpd.sjoin(g, g, predicate="intersects")
    a, b = j["i_left"].values, j["i_right"].values
    keep = a < b
    a, b = a[keep], b[keep]
    h = df["h"].values
    nm = _names(df).str.replace(r"\s*\([^)]*\)\s*$", "", regex=True).str.lower().values
    hi, lo = np.maximum(h[a], h[b]), np.minimum(h[a], h[b])
    same_h = (hi - lo) <= np.maximum(6.0, 0.15 * hi)
    same_n = (nm[a] == nm[b]) | (nm[a] == "") | (nm[b] == "")
    ok = same_h & same_n
    m = coo_matrix((np.ones(ok.sum()), (a[ok], b[ok])), shape=(n, n))
    _, lab = connected_components(m, directed=False)
    return pd.Series(lab, index=df.index)


def building_kind(df: pd.DataFrame) -> pd.Series:
    """Kind per building (04_buildings): china-south's shape rules on each building (its LandsD rows grouped), then
    podiums, malls and civic buildings by LandsD's block type and name, and OSM's tag (see the module's notes)."""
    h, a, asp = df["h"], df["area"], df["aspect"]
    kind = pd.Series(_shape_kind(h, a, asp), index=df.index)
    if "buildingblocktype" in df and hasattr(df, "geometry"):
        from ...stages.buildings import shape_stats
        grp = _groups(df)
        multi = grp.map(grp.value_counts()) > 1
        if multi.any():
            sub = df[multi]
            whole = sub[["geometry"]].assign(grp=grp[multi].values, h=sub["h"].values).dissolve("grp", aggfunc={"h": "max"})
            whole = whole.join(shape_stats(whole))
            wk = pd.Series(_shape_kind(whole["h"], whole["area"], whole["aspect"]), index=whole.index)
            kind[multi] = grp[multi].map(wk).values
            print(f"hk kinds: {int(multi.sum()):,} LandsD rows in {len(whole):,} multi-row buildings; slab rows "
                  f"{int((pd.Series(_shape_kind(h, a, asp), index=df.index) == 'slab').sum()):,} -> {int((kind == 'slab').sum()):,}")
    names = _names(df)
    low = h < 60
    podium = df.get("buildingblocktype", pd.Series("", index=df.index)).fillna("").astype(str) == "Podium"
    mall = names.str.contains(MALL_NAME) & low
    civic = names.str.contains(CIVIC_NAME) & low & ~kind.isin(["house"])
    osm_kind = df["osm_building"].map(OSM_KIND) if "osm_building" in df else pd.Series(np.nan, index=df.index)
    use = osm_kind.notna() & (kind != "tower")
    kind[use] = osm_kind[use]
    kind[(podium | mall) & low] = "podium"
    kind[civic] = "civic"
    print(f"hk kinds: podium rows {int((podium & low).sum()):,}, malls by name {int(mall.sum()):,}, civic by name "
          f"{int(civic.sum()):,}")
    return kind


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles) from its kind, height, LandsD name, OSM tag and the OSM land use around it
    (use, 05c_landuse; NaN where none). See the module's notes."""
    h, kind, area = b.h, b.kind, b.geometry.area
    names = _names(b)
    tag = b.osm_building.map(osm_style) if "osm_building" in b else pd.Series(np.nan, index=b.index)
    style = pd.Series("apartment", index=b.index)
    style[kind == "podium"] = "commercial"
    style[kind == "civic"] = "civic"
    style[kind == "factory"] = "factory"
    style[kind.isin(["village", "house"])] = "village"
    mid = kind.isin(["midrise", "village"])
    style[mid & (h < 30)] = "tonglau"
    style[mid & (h >= 30) & (h < 75) & (area < 900)] = "composite"
    # names
    home = names.str.contains(HOME_NAME)
    office = names.str.contains(OFFICE_NAME) & ~home
    housing = ~kind.isin(["podium", "civic", "factory", "house"])
    comp = names.str.contains(COMPOSITE_NAME) & housing & (h < 75) & (h >= 9)
    style[comp & (h < 30)] = "tonglau"
    style[comp & (h >= 30)] = "composite"
    # (the Housing Authority's blocks stand on 350 m² or more; the "... House" pencil towers along Nathan Road do not)
    estate = names.str.contains(ESTATE_NAME) & (h >= 25) & (h < 160) & (area >= 350) & housing & (use != "commercial")
    style[estate] = "estate"
    ind_name = names.str.contains(INDUSTRIAL_NAME) & ~kind.isin(["house", "civic"])
    style[ind_name] = "industrial"
    # land use
    ind = (use == "industrial") & ~kind.isin(["house", "civic", "podium"])
    style[ind & (h < 100) & ~(office & (h >= 40))] = "industrial"
    style[ind & ((h >= 100) | (office & (h >= 40)))] = "glass"
    style[(use == "commercial") & (h >= 40) & office & housing] = "glass"
    style[(h >= 150) & (use != "residential") & ~home & housing] = "glass"
    # OSM's tag where the rules left a home style
    t = tag.notna() & style.isin(["apartment", "tonglau", "composite"]) & ~(names.str.contains(ESTATE_NAME) & (h >= 25))
    style[t] = tag[t]
    style[(style == "commercial") & (h >= 60)] = "glass"
    style[(style == "village") & (h >= 12)] = "tonglau"
    style[(b.h_src == "landmark") & (h >= 60)] = "glass"
    style[names.str.contains(COLONIAL_NAME) & (h < 40)] = "colonial"
    print("hk styles: " + ", ".join(f"{k} {v:,}" for k, v in style.value_counts().items()))
    return style.values
