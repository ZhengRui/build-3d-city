"""Source adapter: GlobalBuildingAtlas (GBA), worldwide footprints with heights from 3 m imagery (stage 02_gba).

Clips GBA buildings to the scene area and attaches their heights. GBA ships footprints and heights
separately, in 5 x 5 degree tiles (see gba_lod1_reference.py, GBA's own join script, kept for reference):
  gba_polygon_<tile>.geojson  GBA.LoD1/Polygon       footprints (CC BY-NC 4.0)
  gba_odbl_<tile>.geojson     GBA.ODbLPolygon        footprints from OSM/Microsoft (ODbL)
  gba_lod1_<tile>.json        GBA.LoD1/LoD1          {source+id+region: {height, var}}
downloaded by hand into raw/ (Hugging Face zhu-xlab/GBA.LoD1 and GBA.ODbLPolygon); the tile is
[sources.gba] tile. Polygons are EPSG:3857 even when a file claims otherwise.

Role in the building table (04_buildings): "blocks", whole buildings from coarse imagery, which merges
urban-village blocks into blobs; heights from the polygon covering most of a footprint.

Writes gba_buildings.gpkg (WGS84) in the data folder.
"""
from pathlib import Path

import geopandas as gpd
import ijson
import pandas as pd
import pyogrio

from ..common import CFG, DATA, RAW, UTM
from ..common import boundary as common_boundary

STAGE = "02_gba"
ROLE = "blocks"
HEIGHTS = True
TILE = CFG["sources"]["gba"]["tile"]


def load() -> gpd.GeoDataFrame:
    gba = gpd.read_file(DATA / "gba_buildings.gpkg").to_crs(UTM)
    gba["h"] = gba["height"]
    gba["geometry"] = gba.geometry.make_valid()
    return gba


def clip(path: Path, boundary_3857) -> gpd.GeoDataFrame:
    g = pyogrio.read_dataframe(path, bbox=tuple(boundary_3857.bounds))
    g = g.set_crs("EPSG:3857", allow_override=True)
    return g[g.intersects(boundary_3857)]


def main():
    boundary = common_boundary().to_crs("EPSG:3857").geometry.iloc[0]

    parts = []
    for name in (f"gba_polygon_{TILE}.geojson", f"gba_odbl_{TILE}.geojson"):
        g = clip(RAW / name, boundary)
        print(f"{name}: {len(g)} footprints in the scene area")
        parts.append(g)
    g = pd.concat(parts, ignore_index=True)
    g["key"] = g["source"].astype(str) + g["id"].astype(str) + g["region"].astype(str)

    wanted = set(g["key"])
    heights = {}
    with open(RAW / f"gba_lod1_{TILE}.json", "rb") as f:
        for key, v in ijson.kvitems(f, "", use_float=True):
            if key in wanted:
                heights[key] = (v.get("height"), v.get("var"))
    g["height"] = g["key"].map(lambda k: heights.get(k, (None, None))[0])
    g["var"] = g["key"].map(lambda k: heights.get(k, (None, None))[1])
    g.loc[g["height"] < 0, "height"] = None      # -999 marks "no estimate"

    g = g.to_crs("EPSG:4326")
    g.to_file(DATA / "gba_buildings.gpkg")
    print(f"gba buildings: {len(g)}  with height: {g.height.notna().sum()}  "
          f"sources: {g.source.value_counts().to_dict()}")
    print(g.height.describe().round(1).to_string())

