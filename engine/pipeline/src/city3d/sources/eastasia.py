"""Source adapter: the East Asia building footprints (stage 02b_eastasia), China, Japan, Korea and neighbours.

Source: "A first high-quality vector data of buildings in East Asian countries" (Zenodo 8174931,
CC BY 4.0), mapped from 0.5 m imagery. It separates the individual buildings of urban villages that
GBA (3 m imagery) merges into block-sized blobs. No heights.

The archive is one 23 GB zip; only the region's files ([sources.eastasia] region, e.g.
China/Guangdong/Shenzhen: about 50 MB) are read, using HTTP range requests, and kept in raw/eastasia/.
Shenzhen's western edge is 113.768 E, which cuts off about 12 km² of reclaimed land around the convention
centre; 04_buildings fills that from GBA and OSM.

Role in the building table (04_buildings): "pieces", fine footprints aligned to OSM per cell, filling
what OSM and the "blocks" source left.

Writes eastasia_buildings.gpkg (WGS84) in the data folder.
"""
import geopandas as gpd
import pyogrio
from remotezip import RemoteZip

from ..common import CFG, DATA, RAW, UTM, boundary

STAGE = "02b_eastasia"
ROLE = "pieces"
HEIGHTS = False
URL = CFG["sources"]["eastasia"]["url"]
REGION = CFG["sources"]["eastasia"]["region"]
OUT = RAW / "eastasia"
SHP = OUT / f"{REGION}.shp"


def load() -> gpd.GeoDataFrame:
    return gpd.read_file(DATA / "eastasia_buildings.gpkg").to_crs(UTM)


def main():
    if not SHP.exists():
        with RemoteZip(URL) as z:
            for i in z.infolist():
                if i.filename.startswith(f"{REGION}."):
                    z.extract(i, OUT)
    bd = boundary()
    g = pyogrio.read_dataframe(SHP, bbox=tuple(bd.to_crs(4326).total_bounds), columns=["Id"])
    g = g[g.to_crs(bd.crs).intersects(bd.geometry.iloc[0])]
    g.to_crs(4326).to_file(DATA / "eastasia_buildings.gpkg")
    print(f"East Asia footprints in the scene area: {len(g):,}")

