"""The "geotiff" DEM adapter (sources/geotiff.py: local rasters in their own CRS) through 02_dem's report, and a
file source's height expression over the footprint's `area` (a mean height from a volume field, London's Carbon &
Place). A synthetic 1 km district near London, a web-mercator DEM sloping 10 m per km eastwards. Run:
`uv run pytest tests`.
"""
import os
import subprocess
import sys

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box

UTM = "EPSG:32630"
X0, Y0 = 699000.0, 5710000.0          # near London, UTM 30N

CITY_TOML = """
name = "tifftest"
utm_epsg = 32630
coast = false
[districts]
"Square" = 1
[paths]
data = "data"
[sources]
footprints = ["osm", "c"]
heights = ["c", "default"]
dem = "geotiff"
[sources.c]
adapter = "file"
path = "c.gpkg"
role = "fill"
height = "where(volume / area >= 0.6 * hmax, hmax, volume / area)"
[sources.geotiff]
ground = ["dem/ground_3857.tif"]
note = "a synthetic slope"
[terrain.spots]
"West edge" = [LON0, LAT0]
"""


def test_geotiff_dem_and_area_expression(tmp_path):
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    lon0, lat0 = to_ll.transform(X0 + 10, Y0 + 500)
    (tmp_path / "city.toml").write_text(CITY_TOML.replace("LON0", f"{lon0:.6f}").replace("LAT0", f"{lat0:.6f}"))
    data = tmp_path / "data"
    (data / "raw" / "dem").mkdir(parents=True)
    sq = box(X0, Y0, X0 + 1000, Y0 + 1000)
    gpd.GeoDataFrame({"name": ["Square"], "relation": [1]}, geometry=[sq], crs=UTM).to_crs(
        "EPSG:4326").to_file(data / "boundary.gpkg")
    # a 400 m² block with a 100 m mast at its corner (mean 12 m: the mean wins) and a 400 m² tower (mean 90 of 100)
    c = gpd.GeoDataFrame({"hmax": [100.0, 100.0], "volume": [12.0 * 400, 90.0 * 400]},
                         geometry=[box(X0 + 100, Y0 + 100, X0 + 120, Y0 + 120), box(X0 + 500, Y0 + 500, X0 + 520, Y0 + 520)],
                         crs=UTM).to_crs("EPSG:27700")
    c.to_file(data / "raw" / "c.gpkg")
    # the DEM in web mercator, 20 m cells, 30 m at its west edge rising 10 m per km
    to_m = Transformer.from_crs(UTM, "EPSG:3857", always_xy=True)
    xs, ys = to_m.transform([X0 - 3000, X0 + 4000], [Y0 - 3000, Y0 + 4000])
    cell = 20.0
    w, h = int((xs[1] - xs[0]) / cell), int((ys[1] - ys[0]) / cell)
    z = np.tile(30.0 + np.arange(w) * cell * 0.01 * np.cos(np.radians(lat0)), (h, 1)).astype(np.float32)
    with rasterio.open(data / "raw" / "dem" / "ground_3857.tif", "w", driver="GTiff", width=w, height=h, count=1,
                       dtype="float32", crs="EPSG:3857", transform=from_origin(xs[0], ys[1], cell, cell),
                       nodata=-9999.0) as r:
        r.write(z, 1)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    (tmp_path / "checks").mkdir()
    for stage in ("02_c", "02_dem"):
        r = subprocess.run([sys.executable, "-m", "city3d", stage], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    g = gpd.read_file(data / "c_buildings.gpkg")
    assert sorted(np.round(g.h, 1)) == [12.0, 100.0], list(g.h)
    md = (tmp_path / "checks" / "dem.md").read_text()
    row = next(line for line in md.splitlines() if line.startswith("| West edge"))
    # 3 km of slope west of the point: 30 + 30 = 60 m (the raster's cells in mercator metres)
    v = float(row.split("|")[3])
    assert 58.0 < v < 62.0, row
    assert "a synthetic slope" in md and "lowest" in md
