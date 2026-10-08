"""M1 stopgap: boundary.gpkg written by 01_osm's own code (city3d.stages.osm.boundary and district_spec, the
relations replayed from the Overpass cache), without fetching the buildings, so 02_landsd and the source report can
run while the public Overpass is down. 01_osm writes the same file again when it runs.
    CITY3D_OVERPASS_CACHE=../data/hongkong/raw/overpass_cache uv run python scripts/m1_boundary_gpkg.py"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from city3d.common import DATA, DISTRICTS
from city3d.stages.osm import boundary, district_spec

bs = []
for name, v in DISTRICTS.items():
    rel_id, clip = district_spec(v)
    b = boundary(rel_id)
    if clip:
        b["geometry"] = b.geometry.intersection(Polygon(clip))
    b["name"] = name
    print(f"{name}: relation {rel_id}, {b.to_crs(32650).area.iloc[0] / 1e6:.1f} km²")
    bs.append(b)
gpd.GeoDataFrame(pd.concat(bs, ignore_index=True), crs="EPSG:4326").to_file(DATA / "boundary.gpkg")
print(f"wrote {DATA / 'boundary.gpkg'}")
