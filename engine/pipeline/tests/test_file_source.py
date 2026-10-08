"""The "file" footprint adapter (sources/file.py) and two primary layers ruling in their own districts
(04_buildings' choose_footprints), on a synthetic city of two 1 km districts: layer A (GeoJSON, lon/lat,
heights from an expression) covers district West, layer B (GeoPackage in a metric CRS, a height field, one
feature dropped) covers East. Run: `uv run pytest tests`.
"""
import os
import subprocess
import sys
import textwrap

import geopandas as gpd
from shapely.geometry import box

UTM = "EPSG:32630"
X0, Y0 = 440000.0, 4474000.0          # near Madrid, UTM 30N

CITY_TOML = """
name = "filetest"
utm_epsg = 32630
[districts]
"West" = 1
"East" = 2
[paths]
data = "data"
[sources]
footprints = ["a", "b", "osm"]
heights = ["a", "b", "osm_height", "default"]
[sources.a]
adapter = "file"
path = "a.geojson"
districts = ["West"]
height = "where(tall == 'O', hmax, hmed)"
keep = ["fid_a"]
rename = { ground = "ground_elevation" }
[sources.b]
adapter = "file"
path = "b.gpkg"
layer = "bat"
districts = ["East"]
height = "hauteur"
keep = ["cleabs"]
drop = { etat = ["En projet"] }
"""


def test_file_sources_and_two_primaries(tmp_path):
    (tmp_path / "city.toml").write_text(CITY_TOML)
    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    west, east = box(X0, Y0, X0 + 1000, Y0 + 1000), box(X0 + 1000, Y0, X0 + 2000, Y0 + 1000)
    gpd.GeoDataFrame({"name": ["West", "East"], "relation": [1, 2]}, geometry=[west, east], crs=UTM).to_crs(
        "EPSG:4326").to_file(data / "boundary.gpkg")
    # A: two buildings in West (one a tower read at its max), one in East (not A's district)
    a = gpd.GeoDataFrame({"fid_a": [1, 2, 3], "tall": ["N", "O", "N"], "hmed": [20.0, 80.0, 15.0],
                          "hmax": [25.0, 150.0, 18.0], "ground": [600.0, 601.0, 602.0]},
                         geometry=[box(X0 + 100, Y0 + 100, X0 + 150, Y0 + 150), box(X0 + 300, Y0 + 300, X0 + 340, Y0 + 340),
                                   box(X0 + 1500, Y0 + 500, X0 + 1540, Y0 + 540)], crs=UTM)
    a.to_crs("EPSG:4326").to_file(data / "raw" / "a.geojson", driver="GeoJSON")
    # B: two buildings in East, one planned (dropped), one in West under A's first building
    b = gpd.GeoDataFrame({"cleabs": ["B1", "B2", "B3", "B4"], "hauteur": [30.0, 12.0, 50.0, 21.0],
                          "etat": ["En service", "En service", "En projet", "En service"]},
                         geometry=[box(X0 + 1100, Y0 + 100, X0 + 1160, Y0 + 160), box(X0 + 1500, Y0 + 500, X0 + 1540, Y0 + 540),
                                   box(X0 + 1700, Y0 + 700, X0 + 1750, Y0 + 750), box(X0 + 100, Y0 + 100, X0 + 150, Y0 + 150)],
                         crs=UTM).to_crs("EPSG:2154")
    b.to_file(data / "raw" / "b.gpkg", layer="bat")
    # OSM: one small untagged building nowhere else (kept: 225 m², under the 300 m² an untagged fill may have), one duplicating A's tower (dropped)
    gpd.GeoDataFrame({"osm_id": ["way/1", "way/2"], "building": ["yes", "yes"], "height": [None, None],
                      "levels": [None, None], "name": [None, None], "location": [None, None], "layer": [None, None]},
                     geometry=[box(X0 + 600, Y0 + 600, X0 + 615, Y0 + 615), box(X0 + 300, Y0 + 300, X0 + 340, Y0 + 340)],
                     crs=UTM).to_crs("EPSG:4326").to_file(data / "osm_buildings.gpkg")
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    for stage in ("02_a", "02_b"):
        r = subprocess.run([sys.executable, "-m", "city3d", stage], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    ga, gb = gpd.read_file(data / "a_buildings.gpkg"), gpd.read_file(data / "b_buildings.gpkg")
    assert sorted(ga.h) == [15.0, 20.0, 150.0] and "ground_elevation" in ga and set(ga.source) == {"a"}
    assert sorted(gb.cleabs) == ["B1", "B2", "B4"] and gb.geometry.iloc[0].has_z is False
    code = textwrap.dedent("""
        import geopandas as gpd, pandas as pd
        from city3d.stages import buildings as B
        from city3d import sources
        from city3d.common import load_osm
        prims = [(n, B.split_merged(sources.module(n).load(), None)) for n in ("a", "b")]
        b = B.choose_footprints(load_osm(), [], [], prims)
        print(sorted(b.source.value_counts().items()))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    # West: A's two (B4 under A's first is B's, outside its districts); East: B1, B2 (A's third is outside
    # A's districts); OSM: the lone building (its duplicate of A's tower dropped)
    assert r.stdout.strip().splitlines()[-1] == "[('a', 2), ('b', 2), ('osm', 1)]", r.stdout
