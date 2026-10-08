"""Write ../data/tokyo/boundary.gpkg as 01_osm would (one row per [districts] entry: the ward relation's polygon cut by
its clip, WGS84, columns name and osm_id), from the ward polygons saved in Phase 0 (../data/tokyo/phase0/wards/,
polygons.openstreetmap.fr, 6 Oct). For running the non-OSM stages (02_plateau, 02_dem) while Overpass is down;
01_osm rewrites the file from Overpass later.

uv run python scripts/boundary_offline.py   (from demos/tokyo; light)
"""
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, shape

from city3d import config

CITY = Path(__file__).resolve().parents[1]
cfg = config.load(CITY / "city.toml")
DATA = (CITY / cfg["paths"]["data"]).resolve()
WARDS = DATA / "phase0/wards"
rows = []
for name, v in cfg["districts"].items():
    rel, clip = (v, None) if isinstance(v, int) else (v["relation"], v.get("clip"))
    g = shape(json.loads((WARDS / f"{rel}.geojson").read_text())).buffer(0)
    if clip:
        g = g.intersection(Polygon(clip))
    rows.append({"name": name, "osm_id": rel, "geometry": g})
b = gpd.GeoDataFrame(rows, crs="EPSG:4326")
b.to_file(DATA / "boundary.gpkg")
print(f"{len(b)} districts, {b.to_crs(cfg['utm_epsg']).area.sum() / 1e6:.2f} km² -> {DATA / 'boundary.gpkg'}")
