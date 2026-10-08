"""The sg-singapore preset's code (Singapore, M4; tables in presets/sg-singapore.toml): building kinds are china-south's
(Singapore's M2 kinds: tower, slab, factory, house, village, podium, midrise and OSM's tags through [buildings.osm_kind]),
facade styles and roof shapes are Singapore's own. Rules, in order (a later rule wins):
  1. the kind: towers, slabs and midrises condo, podiums commercial, civic civic, factories factory, houses and
     villages (the shophouse rows: under 12 m on a small plot, or 12-40 m on one under 450 m²) shophouse
  2. OSM land use (05c_landuse): commercial: glass from 40 m, commercial below; industrial: glass from 40 m, factory
     below; civic: civic under 40 m; residential: condo
  3. OSM's building tag ([facade.osm_style]); offices under 25 m commercial; malls and shops from 40 m glass
  4. low pieces (kind house or village, up to 24 m) of the condo, commercial, glass or villa styles are shophouses
     outside Sentosa (OSM tags the rows residential, retail, commercial, hotel or yes); on Sentosa (URA subzone) the low
     ones (under 20 m) of those styles and the shophouses are villas
  4b. by URA subzone ([facade.singapore] office, civic, port: lists of subzone names): untagged (yes) pieces the rules
     made condos are offices in the CBD's subzones (glass from 40 m, commercial below), civic in the hospital's,
     factory on the port
  5. HDB ([sources.hdb]'s lent flags): residential blocks hdb (built before [facade.singapore] streamline_before:
     streamline, the SIT flats), multi-storey car parks carpark, commercial-only blocks commercial
  6. landmark towers (the landmark list, 60 m up) glass; then the named buildings ([facade.singapore] named in city.toml:
     style = [names or OSM ids]): granite, colonial, fins, bands... (data/landmark_facades.csv, applied after, wins)
Roof shapes: shophouses and the low colonial buildings (5-20 m, 30 m) a pitched clay-tile roof from their free walls
(the party walls of a row stay vertical, so a terrace reads as one roof along the street).
"""
import numpy as np
import pandas as pd
import geopandas as gpd

from ... import config
from ..china_south import building_kind  # noqa: F401  (04_buildings uses it)

CFG = config.get()
SG = CFG["facade"].get("singapore", {})
SENTOSA = SG.get("villa_subzones", ["SENTOSA"])


def _subzone(b) -> pd.Series:
    """The URA MP2019 subzone name at each building's inside point ("" where none; [facade.singapore] subzones: the
    layer under raw/)."""
    from ...common import DATA
    p = DATA / "raw" / SG.get("subzones", "MP2019_subzone_nosea.geojson")
    out = pd.Series("", index=b.index, dtype=object)
    if not p.exists():
        print(f"singapore: no subzone layer ({p.name}): no Sentosa villas")
        return out
    sz = gpd.read_file(p, columns=["SUBZONE_N"]).to_crs(b.crs)
    pt = gpd.GeoDataFrame(geometry=b.geometry.representative_point().values, index=b.index, crs=b.crs)
    j = gpd.sjoin(pt, sz[["SUBZONE_N", "geometry"]], predicate="within")
    j = j[~j.index.duplicated()]
    out.loc[j.index] = j["SUBZONE_N"].fillna("").astype(str)
    return out


def _flag(b, name) -> pd.Series:
    return (b[name].astype(str) == "Y") if name in b else pd.Series(False, index=b.index)


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles): the rules in this module's docstring."""
    h, kind = b.h, b.kind
    tag = b.osm_building.map(osm_style)
    low = kind.isin(["house", "village"])
    style = pd.Series("condo", index=b.index, dtype=object)
    style[kind == "podium"] = "commercial"
    style[kind == "civic"] = "civic"
    style[kind == "factory"] = "factory"
    style[low & (h <= 24)] = "shophouse"
    tall = h >= 40
    style[(use == "commercial") & tall] = "glass"
    style[(use == "commercial") & ~tall & ~low] = "commercial"
    style[(use == "industrial") & tall] = "glass"
    style[(use == "industrial") & ~tall & ~low] = "factory"
    style[(use == "civic") & ~tall] = "civic"
    style[(use == "residential") & kind.isin(["tower", "slab", "midrise"])] = "condo"
    style[tag.notna()] = tag[tag.notna()]
    style[(style == "glass") & (h < 25)] = "commercial"
    style[(style == "commercial") & tall] = "glass"
    # the rows: low pieces outside Sentosa are shophouses whatever OSM calls them; Sentosa's are villas
    sub = _subzone(b)
    sentosa = sub.isin(SENTOSA)
    row = low & (h <= 24) & style.isin(["condo", "commercial", "glass", "villa", "shophouse"])
    style[row & ~sentosa] = "shophouse"
    style[sentosa & (h < 20) & style.isin(["condo", "shophouse", "villa", "commercial"]) & ~kind.isin(["civic", "factory"])] = "villa"
    # the CBD's, the hospital's and the port's untagged pieces
    untagged = b.osm_building.isna() | (b.osm_building.astype(str) == "yes")
    loose = untagged & (style == "condo")
    office = loose & sub.isin(SG.get("office", []))
    style[office & tall] = "glass"
    style[office & ~tall] = "commercial"
    style[loose & sub.isin(SG.get("civic", []))] = "civic"
    style[loose & sub.isin(SG.get("port", []))] = "factory"
    # HDB's own flags (lent to the OSM outlines they cover)
    resi, comm, park = _flag(b, "residential"), _flag(b, "commercial"), _flag(b, "multistorey_carpark")
    style[comm & ~resi & ~park] = "commercial"
    style[resi] = "hdb"
    # (M7) the SIT's pre-war and 1950s walk-ups (Tiong Bahru: HDB's year_completed 1937-1954) cream streamline flats,
    # not the HDB towers' accent paint ([facade.singapore] streamline_before = year; absent: off)
    if SG.get("streamline_before") and "year_completed" in b:
        yr = pd.to_numeric(b["year_completed"], errors="coerce")
        style[resi & (yr < SG["streamline_before"])] = "streamline"
    style[park] = "carpark"
    # landmark towers are offices; then the named buildings
    style[(b.h_src == "landmark") & (h >= 60)] = "glass"
    names = b["name"].astype(str) if "name" in b else pd.Series("", index=b.index)
    ids = b["osm_id"].astype(str) if "osm_id" in b else pd.Series("", index=b.index)
    for s, keys in SG.get("named", {}).items():
        hit = names.isin(keys) | ids.isin(keys)
        style[hit] = s
        missing = sorted(set(keys) - set(names[hit]) - set(ids[hit]))
        print(f"singapore named {s}: {int(hit.sum())} pieces" + (f"; not found: {missing}" if missing else ""))
    print("singapore styles: " + ", ".join(f"{k} {v:,}" for k, v in style.value_counts().items()))
    return style.values


def roof_shapes(b, style) -> pd.DataFrame:
    """Per building: roof shape ("pitched" or "") and material (2 clay tile, 0 none): the shophouses' tile roofs (5-20 m)
    and the low colonial buildings' (5-30 m), from their free walls. OSM parts and landmark rows keep their own massing
    (06_tiles)."""
    idx = b.index
    style = pd.Series(style, index=idx).astype(str)
    h, a = b.h, b.geometry.area
    pitch = ((style == "shophouse") & (h <= 20)) | ((style == "colonial") & (h <= 30))
    pitch &= (h >= 5) & (a >= 40)          # (not the small boxes on roofs and in yards)
    shape = pd.Series("", index=idx, dtype=object)
    shape[pitch] = "pitched"
    mat = np.where(pitch, 2, 0)
    return pd.DataFrame({"shape": shape, "material": mat}, index=idx)
