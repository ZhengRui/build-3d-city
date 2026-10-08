"""The us-northeast preset's code (Manhattan; tables in presets/us-northeast.toml): building kinds and facade
styles. Its rooftop clutter is in rooftops.py.

Manhattan's building stock, by what the data can tell apart: the building class of the tax lot (NYC's
MapPLUTO bldgclass, joined onto the official footprints: A/B one- and two-family houses, C walk-ups, D
elevator apartments, O offices, K stores, E/F/G warehouses, factories and garages, H hotels, R condos, S
mixed walk-ups with stores...), its height, footprint, OSM tag and year of construction; where the class is
missing, the shape rules below:
  rowhouse   brownstones and other row houses: under 16.5 m (3-5 storeys) on a narrow lot (short side under 9 m, < 260 m²)
  tenement   walk-ups and small loft buildings: 12-32 m on a lot of under 900 m²
  tower      60 m and up
  slab       24 m and up and long (aspect 2.5+: NYCHA slabs, hospital wings)
  factory    warehouses, garages and industrial buildings (tag), or low and very large
  podium     low and large (stores, markets, piers' sheds)
  midrise    the rest: pre-war apartment houses, loft and office buildings of 8-20 storeys
  civic      schools, churches, hospitals, stations... (tag)
"""
import numpy as np
import pandas as pd

from ... import config

CFG = config.get()
OSM_KIND = CFG["buildings"]["osm_kind"]          # OSM building tag -> kind


def building_kind(df: pd.DataFrame) -> pd.Series:
    """Kind per building (04_buildings) from its height h, footprint area, aspect and width (the minimum
    rectangle's short side) and its OSM building tag."""
    h, a, asp = df["h"], df["area"], df["aspect"]
    w = df["width"] if "width" in df else np.sqrt(a / asp.clip(lower=1))
    kind = np.select(
        [h >= 60,
         (h >= 24) & (asp >= 2.5) & (a >= 600),
         (h < 18) & (a >= 4000),
         (h < 16.5) & (w < 9) & (a < 260),
         (h >= 12) & (h < 32) & (a < 900),
         (h < 24) & (a >= 1500)],
        ["tower", "slab", "factory", "rowhouse", "tenement", "podium"],
        default="midrise")
    kind = pd.Series(kind, index=df.index)
    osm_kind = df["osm_building"].map(OSM_KIND)
    # OSM's tag wins for factories, houses and civic buildings, unless the height says tower
    use = osm_kind.notna() & (kind != "tower")
    kind[use] = osm_kind[use]
    # the tax lot's building class, where known, over both: HEIGHT_ROOF counts bulkheads and parapets, so
    # height alone can't tell a 5-storey brownstone from a 5-storey walk-up
    full = df.get("bldgclass", pd.Series(np.nan, index=df.index)).fillna("").astype(str)
    # a shed or a light on a big lot isn't the lot's building: the class counts for footprints over 60 m²
    full = full.where(a >= 60, "")
    cls = full.str[:1]
    low = kind != "tower"
    kind[cls.isin(["C", "S"]) & (h < 36) & low] = "tenement"
    # houses, and houses turned into a few flats (C0 three families, C2 five or six, C3 four, C5 converted
    # dwellings): the brownstone rows of the Upper West Side and Harlem; C4 old-law tenements, C7 walk-ups
    # with stores and the S mixed classes stay walk-ups
    kind[(cls.isin(["A", "B"]) | full.isin(["C0", "C2", "C3", "C5"])) & (h < 26)] = "rowhouse"
    # walk-up condos (R2, R3 under 26 m: converted brownstones) like their walk-up kin
    kind[full.isin(["R2", "R3"]) & (h < 26)] = "rowhouse"
    # small stores are shop-front walk-ups, not houses
    kind[cls.isin(["K"]) & (kind == "rowhouse")] = "tenement"
    kind[cls.isin(["E", "F", "G"]) & (h < 40) & low] = "factory"
    # churches, schools, hospitals, theatres... stay civic however tall their steeple or wing
    kind[cls.isin(["I", "M", "P", "W", "Y", "J", "N", "Q", "T", "U"])] = "civic"
    kind[cls.isin(["K"]) & (h < 24) & (a >= 400)] = "podium"
    kind[(cls.isin(["D", "H", "O"]) | (cls.isin(["R"]) & ~full.isin(["R2", "R3"])))
         & kind.isin(["rowhouse", "tenement"])] = "midrise"
    return kind


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles) from its kind, tax-lot class (bldgclass), height, year of
    construction (the footprints' construction_year, else the lot's yearbuilt), historic district (histdist),
    OSM tag and the land use around it.

      brownstone  row houses: brown sandstone or brick, stoops, cornices
      brick       walk-ups and pre-war apartment houses: brick with punched windows, cornices
      stone       pre-war offices, lofts and hotels, and the setback towers of the 1910s-30s: limestone, buff
                  brick, terracotta, punched windows between piers
      castiron    lofts in the cast-iron districts (SoHo, NoHo, Tribeca): big windows between painted columns
      glass       post-war offices and the towers since the 1990s: curtain walls
      residential post-war apartment houses: brick or panel with window bands
      commercial  low stores and podiums; factory warehouses and garages; civic schools, churches...
    """
    tag = b.osm_building.map(osm_style)
    h, kind = b.get("h_bldg", b.h).fillna(b.h), b.kind
    year = pd.to_numeric(b.get("construction_year"), errors="coerce")
    year = year.where(year > 0, pd.to_numeric(b.get("yearbuilt"), errors="coerce")).fillna(0)
    old = (year > 0) & (year < 1940)
    postwar = (year >= 1946) & (year < 1995)
    new = year >= 1995
    cls = b.get("bldgclass", pd.Series(np.nan, index=b.index)).fillna("").astype(str).str[:1]
    hist = b.get("histdist", pd.Series(np.nan, index=b.index)).fillna("").astype(str)
    style = pd.Series("brick", index=b.index)
    style[kind == "rowhouse"] = "brownstone"
    style[kind == "podium"] = "commercial"
    style[kind == "civic"] = "civic"
    style[kind == "factory"] = "factory"
    style[kind.isin(["midrise", "tenement", "slab", "tower"]) & postwar] = "residential"
    style[kind.isin(["tower", "slab"]) & old] = "stone"
    style[kind.isin(["tower", "slab", "midrise"]) & new] = "residential"
    style[(kind == "tower") & new & (h >= 100)] = "glass"
    # offices and hotels by class; else the land use where the class is missing
    office = cls.isin(["O"]) | ((cls == "") & (use == "commercial"))
    style[office & ~kind.isin(["rowhouse", "civic"]) & old] = "stone"
    style[office & ~kind.isin(["rowhouse", "civic"]) & ~old & (h >= 30)] = "glass"
    style[office & ~kind.isin(["rowhouse", "civic"]) & ~old & (h < 30)] = "commercial"
    style[cls.isin(["H"]) & old] = "stone"
    style[cls.isin(["H"]) & ~old & (h >= 40)] = "glass"
    style[cls.isin(["K"]) & (h < 30)] = "commercial"
    style[(use == "industrial") & ~kind.isin(["rowhouse"]) & (h < 30) & (cls == "")] = "factory"
    style[(use == "civic") & (h < 40) & (cls == "")] = "civic"
    # pre-war warehouses, factories and lofts (E, F, L): brick, punched windows, whatever their bulk (DUMBO's
    # and West Chelsea's block-sized lofts read as office grids as factories or slabs)
    style[cls.isin(["E", "F", "L"]) & old & (h < 60) & ~kind.isin(["rowhouse", "civic"])] = "brick"
    # the industrial historic districts' lofts, offices and condos now (DUMBO, Vinegar Hill, Fulton Ferry): brick
    # warehouses whatever their class today
    brick_hist = hist.str.contains("DUMBO|Vinegar Hill|Fulton Ferry", case=False)
    style[brick_hist & old & (h < 60) & ~kind.isin(["rowhouse", "civic"])] = "brick"
    # the cast-iron districts: their pre-1900-ish lofts and stores
    iron = hist.str.contains("SoHo|NoHo|Tribeca|Cast Iron", case=False) & (year > 0) & (year < 1915)
    style[iron & ~kind.isin(["rowhouse", "civic"]) & (h < 40)] = "castiron"
    # an explicit OSM tag beats land use and shape
    style[tag.notna()] = tag[tag.notna()]
    style[(style == "glass") & old] = "stone"
    style[(style == "brownstone") & (h >= 26)] = "brick"
    style[(b.h_src == "landmark") & (h >= 150) & ~old] = "glass"
    # a building made of OSM parts is one style, from the whole (its kind and tallest top); its thin parts
    # rising over the main roof (04_buildings.main_roof: where the parts from the top down add up to 60 m²)
    # are masts and spires
    if "part_of" in b:
        parts = b.part_of.notna()
        if parts.any():
            from ...stages.buildings import main_roof as roof_of
            area = b.geometry.area
            ph = b.h
            g = pd.DataFrame({"host": b.part_of, "h": ph, "a": area, "style": style})[parts]
            main_roof = b[parts].groupby("part_of").apply(roof_of)
            # the style of the building's largest part
            main_style = g.sort_values("a").groupby("host")["style"].last()
            style[parts] = b.part_of[parts].map(main_style).values
            spire = parts & (area < 120) & (ph > b.part_of.map(main_roof) + 5)
            style[spire] = "spire"
    return style.values
