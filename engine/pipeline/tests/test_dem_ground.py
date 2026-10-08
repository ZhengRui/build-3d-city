"""04_buildings' DEM-ground opt-ins (Tokyo M2): [buildings] split_ground and [buildings.landmarks] ground = "point",
on a tiny DEM fixture: a 200 x 100 m GeoTIFF (UTM 48N, 5 m cells) rising 0.1 m per metre eastwards (z = 0.1 x
from its west edge). Off (the defaults) they change nothing; on, a roof level up the slope loses its ground's rise
over its building's lowest level, and a listed height counts from the DEM at the row's point.
Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

import numpy as np
import rasterio
from rasterio.transform import from_origin

X0, Y0 = 500000.0, 144100.0          # the DEM's north-west corner (UTM 48N)
TOML = """
name = "demground"
utm_epsg = 32648
[districts]
"Test" = 1
[sources]
footprints = ["osm"]
heights = ["landmark", "osm_height", "default"]
dem = "geotiff"
[sources.geotiff]
ground = ["dem.tif"]
[paths]
data = "data"
landmarks = "lm.csv"
{extra}
"""


def run(tmp_path, body, toml):
    """Run `body` (python) on a throwaway city; the last line it prints is JSON, returned."""
    (tmp_path / "city.toml").write_text(toml)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(body)], env=env, capture_output=True, text=True,
                       cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def dem(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    x = (np.arange(40) + 0.5) * 5.0
    z = np.tile(0.1 * x, (20, 1)).astype("float32")
    with rasterio.open(raw / "dem.tif", "w", driver="GTiff", width=40, height=20, count=1, dtype="float32",
                       crs="EPSG:32648", transform=from_origin(X0, Y0, 5.0, 5.0), nodata=-9999) as r:
        r.write(z, 1)
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(32648, 4326, always_xy=True).transform(X0 + 130.05, Y0 - 39.95)
    (tmp_path / "lm.csv").write_text("name_zh,lat,lon,height_m,height_type,use_height,feature\n"
                                     f"Tower,{lat:.8f},{lon:.8f},100.0,roof,True,building\n")


SPLIT = """
import geopandas as gpd, json, pandas as pd
from shapely.geometry import box
from city3d.stages import buildings as bd
X0, Y0 = 500000.0, 144100.0
b = gpd.GeoDataFrame({"h": [20.0, 100.0, 30.0], "roof_level": [1, 0, float("nan")],
                      "parent_id": ["T", "T", ""], "h_src": ["plateau"] * 3},
                     geometry=[box(X0 + 10, Y0 - 60, X0 + 50, Y0 - 20),       # the podium: lowest cell x 10-15 m
                               box(X0 + 110, Y0 - 60, X0 + 150, Y0 - 20),     # the tower, 100 m east: +10 m
                               box(X0 + 110, Y0 - 95, X0 + 150, Y0 - 70)],    # not split: left alone
                     crs="EPSG:32648")
lo = bd.dem_low(b.geometry.values).round(2).tolist()
at = bd.dem_low([box(X0 + 130, Y0 - 40, X0 + 130.1, Y0 - 39.9).centroid], points=True).round(2).tolist()
out = bd.split_ground(b.copy())
print(json.dumps([lo, at, out.h.round(2).tolist(), "split_rise" in out]))
"""


def test_split_ground(tmp_path):
    dem(tmp_path)
    off = run(tmp_path, SPLIT, TOML.format(extra=""))
    lo, at, h, col = off
    assert lo == [1.25, 11.25, 11.25]                 # the lowest cell centre touched (x 12.5, 112.5)
    assert at == [13.25]                              # the cell under x 130 (centre 132.5)
    assert h == [20.0, 100.0, 30.0] and col is False  # off: nothing changes
    on = run(tmp_path, SPLIT, TOML.format(extra="[buildings]\nsplit_ground = true\n"))
    assert on[2] == [20.0, 90.0, 30.0] and on[3] is True    # the tower stands 10 m up the slope


LANDMARK = """
import geopandas as gpd, json, pandas as pd
from shapely.geometry import box
from city3d.stages import buildings as bd
X0, Y0 = 500000.0, 144100.0
b = gpd.GeoDataFrame({"h": [80.0], "h_src": ["osm_height"], "name": [None]},
                     geometry=[box(X0 + 10, Y0 - 60, X0 + 150, Y0 - 20)], crs="EPSG:32648")
n = bd.apply_landmarks(b)
print(json.dumps([n, round(float(b.h[0]), 2), b.h_src[0]]))
"""


def test_landmark_ground_point(tmp_path):
    dem(tmp_path)
    off = run(tmp_path, LANDMARK, TOML.format(extra=""))
    assert off == [1, 100.0, "landmark"]              # off: the listed height as it is
    on = run(tmp_path, LANDMARK, TOML.format(extra='[buildings.landmarks]\nground = "point"\n'))
    assert on == [1, 112.0, "landmark"]               # + DEM at the point (13.25) - lowest under the outline (1.25)
