"""The china-south preset's code (western Shenzhen; tables in presets/china-south.toml): building kinds and
facade styles. Its rooftop clutter is in rooftops.py.
"""
import numpy as np
import pandas as pd

from ... import config

CFG = config.get()
OSM_KIND = CFG["buildings"]["osm_kind"]          # OSM building tag -> kind


def building_kind(df: pd.DataFrame) -> pd.Series:
    """Kind per building (04_buildings) from its height h, footprint area and aspect (long / short side of the
    minimum rectangle) and its OSM building tag: tower, slab, factory, house, village (the Chinese urban
    village: 12-40 m on a small plot), podium, midrise, or the tag's kind (factory, house, civic)."""
    h, a, asp = df["h"], df["area"], df["aspect"]
    kind = np.select(
        [h >= 60,
         (h >= 24) & (asp >= 2.5),
         (h < 24) & (a >= 3000),
         (h < 12) & (a < 250),
         (h >= 12) & (h < 40) & (a < 450),
         (h < 24) & (a >= 1200)],
        ["tower", "slab", "factory", "house", "village", "podium"],
        default="midrise")
    kind = pd.Series(kind, index=df.index)
    osm_kind = df["osm_building"].map(OSM_KIND)
    # OSM's tag wins for factories, houses and civic buildings, unless the height says tower
    use = osm_kind.notna() & (kind != "tower")
    kind[use] = osm_kind[use]
    return kind


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles) from its OSM tag (osm_style: tag -> style), kind, height and the
    OSM land use around it (use, 05c_landuse; NaN where none)."""
    tag = b.osm_building.map(osm_style)
    h, kind = b.h, b.kind
    style = pd.Series("residential", index=b.index)
    style[kind.isin(["podium"])] = "commercial"
    style[kind == "civic"] = "civic"
    style[kind == "factory"] = "factory"
    style[kind.isin(["village", "house"])] = "village"
    style[(kind == "tower") & (h >= 150)] = "glass"
    # land use decides for buildings the geometry alone can't place
    tall = h >= 40
    style[(use == "commercial") & tall] = "glass"
    style[(use == "commercial") & ~tall & ~kind.isin(["village", "house"])] = "commercial"
    style[(use == "industrial") & tall] = "glass"                    # R&D towers in industrial parks
    style[(use == "industrial") & ~tall & ~kind.isin(["village", "house"])] = "factory"
    style[(use == "civic") & ~tall] = "civic"
    style[(use == "residential") & kind.isin(["tower", "slab", "midrise"])] = "residential"
    # an explicit OSM tag beats everything; landmark towers are offices
    style[tag.notna()] = tag[tag.notna()]
    style[(style == "commercial") & tall] = "glass"
    style[(style == "village") & (h >= 40)] = "residential"
    style[(b.h_src == "landmark") & (h >= 60)] = "glass"
    return style.values
