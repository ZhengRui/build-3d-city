"""M7 fix round 1: the town ring round the ground area's modelled districts, data/masses_ring.geojson (WGS84) for
[ground] masses_ring (engine opt-in): every OSM footprint within `--width` m of the districts (D, data/boundary_d.geojson)
stands as a block mass, so the roofscape goes on past the area's edge (north of Ueno to Yanaka and Nippori, west of
Nishi-Shinjuku, north-east of the Skytree) instead of a painted plain with 3D roads and no buildings (M7 critic 1, item 2).
The bay rim (data/masses_within.geojson) and D itself are left out; the ring is cut to the ground area's box less 100 m
(the masses' ground there is the ground TIN).

uv run python scripts/m7f_ring.py [--width 2500]   (from demos/tokyo; light)
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box, mapping
from shapely.ops import unary_union

CITY = Path(__file__).resolve().parents[1]
DATA = CITY.parents[0] / "data/tokyo"
UTM = "EPSG:32654"

ap = argparse.ArgumentParser()
ap.add_argument("--width", type=float, default=2500.0)
a = ap.parse_args()
d = gpd.read_file(CITY / "data/boundary_d.geojson").to_crs(UTM).geometry.union_all()
rim = gpd.read_file(CITY / "data/masses_within.geojson").to_crs(UTM).geometry.union_all()
area = gpd.read_file(DATA / "ground.gpkg", layer="area").to_crs(UTM).geometry.iloc[0]
x0, y0, x1, y1 = area.envelope.bounds
ring = d.buffer(a.width, join_style="round").difference(d.buffer(1)).difference(rim.buffer(1))
ring = ring.intersection(box(x0 + 100, y0 + 100, x1 - 100, y1 - 100)).simplify(5)
g = gpd.GeoSeries([ring], crs=UTM).to_crs(4326).iloc[0]
out = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": f"ring {a.width:.0f} m"},
                                                  "geometry": mapping(g)}]}
(CITY / "data/masses_ring.geojson").write_text(json.dumps(out))
# (M8: the ring's whole extent, the districts included, for masses_ring.edge: the masses lower and sparser over the last
# few hundred metres to its outer edge)
ext = d.buffer(a.width, join_style="round").intersection(box(x0 + 100, y0 + 100, x1 - 100, y1 - 100)).simplify(5)
ge = gpd.GeoSeries([ext], crs=UTM).to_crs(4326).iloc[0]
(CITY / "data/masses_ring_outer.geojson").write_text(json.dumps(
    {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": f"ring extent {a.width:.0f} m"},
                                                "geometry": mapping(ge)}]}))
print(f"ring {a.width:.0f} m: {ring.area / 1e6:.1f} km² (D {d.area / 1e6:.1f} km², ground box "
      f"{(x1 - x0) / 1000:.1f} x {(y1 - y0) / 1000:.1f} km)")
