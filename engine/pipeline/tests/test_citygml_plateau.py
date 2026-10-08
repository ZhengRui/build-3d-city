"""The "citygml" adapter with flavour = "plateau" (sources/citygml.py) on two small PLATEAU-style CityGML 2.0 meshes in
tests/fixtures/plateau/ (lat lon h posLists in EPSG:6697, i-UR 3.2 attributes, an appearance block at the top):
  53394611_bldg_6697_op.gml     P: LoD2 building of two parts (the parent has only attributes, lod0 and lod1 of the
                                whole), the second part with LoD3 twins of its surfaces; G: an LoD2 gabled house;
                                L: LOD1-only with a roof edge and measuredHeight -9999; S: LOD1-only without lod0;
                                F: outside the district
  53394612_bldg_6697_op.gml.gz  G again (a mesh repeated by a neighbouring ward) and N, LOD1-only
Run: `uv run pytest tests`.
"""
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

UTM = "EPSG:32654"
X0, Y0 = 387000.0, 3949000.0            # Tokyo Station, UTM 54N (the fixtures' origin)
FIXTURES = Path(__file__).parent / "fixtures" / "plateau"

CITY_TOML = """
name = "plateautest"
utm_epsg = 32654
[districts]
"Core" = 1
[paths]
data = "data"
[sources]
footprints = ["plateau", "osm"]
heights = ["plateau", "default"]
[sources.plateau]
adapter = "citygml"
flavour = "plateau"
path = ["plateau/*.gml", "plateau/*.gml.gz"]
height = "where(isnan(measuredHeight), roof_top_z - ground_z, measuredHeight)"
keep = ["gml_id", "parent_id", "part", "lod", "fp_from", "usage", "usage_name", "class_name", "detailedUsage_name",
    "storeysAboveGround", "storeysBelowGround", "lod1HeightType", "buildingID", "name", "measuredHeight",
    "roof_top_z", "eave_z", "roof_area", "n_roof", "tile"]
rename = { ground_z = "ground_elevation" }
"""


def test_citygml_plateau(tmp_path):
    (tmp_path / "city.toml").write_text(CITY_TOML)
    data = tmp_path / "data"
    shutil.copytree(FIXTURES, data / "raw" / "plateau")
    gpd.GeoDataFrame({"name": ["Core"], "relation": [1]}, geometry=[box(X0 - 100, Y0 - 100, X0 + 1000, Y0 + 1000)],
                     crs=UTM).to_crs("EPSG:4326").to_file(data / "boundary.gpkg")
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-m", "city3d", "02_plateau"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "duplicates skipped 1" in r.stdout, r.stdout                  # G, repeated in the second mesh
    g = gpd.read_file(data / "plateau_buildings.gpkg").set_index("gml_id")
    assert sorted(g.index) == ["bldg_G", "bldg_L", "bldg_N", "bldg_P0", "bldg_P1", "bldg_S"]   # F outside
    u = g.to_crs(UTM)

    # parts: a row each, the parent's attributes inherited, LoD3 twins ignored
    p0, p1 = g.loc["bldg_P0"], g.loc["bldg_P1"]
    assert p1["parent_id"] == "bldg_P" and bool(p1["part"]) and p1["lod"] == 2 and p1["fp_from"] == "ground"
    assert p0["h"] == 12.0 and p1["h"] == 60.0 and p1["roof_top_z"] == 63.0 and p1["ground_elevation"] == 3.0
    assert p1["usage_name"] == "business" and p1["class_name"].startswith("solid building") and p1["buildingid"] == "13101-bldg-1"
    assert abs(p1["roof_area"] - 900.0) < 2 and p1["n_roof"] == 1               # 30 x 30, not doubled by LoD3
    assert abs(u.loc["bldg_P1"].geometry.area - 900.0) < 2
    assert abs(u.loc["bldg_P1"].geometry.bounds[0] - (X0 + 30)) < 0.05             # lat/lon order, projected to UTM

    # LoD2 gabled house: eaves 10, ridge 13, ground 4; sloped roof area 2 x 10 x hypot(4, 3)
    h = g.loc["bldg_G"]
    assert h["lod"] == 2 and h["eave_z"] == 10.0 and h["roof_top_z"] == 13.0 and h["ground_elevation"] == 4.0
    assert abs(h["roof_area"] - 100.0) < 1 and h["detailedusage_name"] == "detached house" and h["tile"] == "53394611_bldg_6697_op"

    # LOD1-only: roof edge footprint; -9999 / 9999 are unknown; the height falls back to the lod1Solid
    lo = g.loc["bldg_L"]
    assert lo["lod"] == 1 and lo["fp_from"] == "lod0RoofEdge" and math.isnan(lo["measuredheight"])
    assert math.isnan(lo["storeysaboveground"]) and lo["usage_name"] == "unknown"
    assert "storeysbelowground" not in g                                     # 9999 everywhere: no column
    assert lo["ground_elevation"] == 5.0 and lo["roof_top_z"] == 8.0 and lo["eave_z"] == 8.0 and lo["h"] == 3.0
    assert math.isnan(lo["roof_area"]) and lo["lod1heighttype"] == "0"
    assert abs(u.loc["bldg_L"].geometry.area - 72.0) < 1
    s = g.loc["bldg_S"]
    assert s["fp_from"] == "lod1" and abs(u.loc["bldg_S"].geometry.area - 20.0) < 0.5 and s["h"] == 7.5
    n = g.loc["bldg_N"]
    assert n["tile"] == "53394612_bldg_6697_op" and n["usage_name"] == "apartment building" and n["h"] == 31.2
