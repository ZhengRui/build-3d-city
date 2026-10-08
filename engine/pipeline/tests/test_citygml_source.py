"""The "citygml" footprint adapter (sources/citygml.py) on a synthetic CityGML 1.0 LoD2 tile in a zip: a plain
building with a gabled roof and a building of two parts (the parent without geometry, its function inherited by
the parts), one feature outside the district. Run: `uv run pytest tests`.
"""
import os
import subprocess
import sys
import zipfile

import geopandas as gpd
from shapely.geometry import box

UTM = "EPSG:32633"
X0, Y0 = 390000.0, 5818000.0            # Berlin, UTM 33N (the tile says EPSG:25833)

CITY_TOML = """
name = "gmltest"
utm_epsg = 32633
[districts]
"Core" = 1
[paths]
data = "data"
[sources]
footprints = ["lod2", "osm"]
heights = ["lod2", "default"]
[sources.lod2]
adapter = "citygml"
path = "lod2/*.zip"
crs = "EPSG:25833"
keep = ["gml_id", "parent_id", "part", "function", "roofType", "eave_z", "roof_top_z"]
rename = { ground_z = "ground_elevation" }
drop = { function = ["51009_1610"] }
"""


def ring(pts):
    return " ".join(f"{x} {y} {z}" for x, y, z in pts + pts[:1])


def poly(pid, pts):
    return (f'<gml:surfaceMember><gml:Polygon gml:id="{pid}"><gml:exterior><gml:LinearRing>'
            f'<gml:posList srsDimension="3">{ring(pts)}</gml:posList></gml:LinearRing></gml:exterior>'
            f'</gml:Polygon></gml:surfaceMember>')


def surface(kind, pid, pts):
    return (f'<bldg:boundedBy><bldg:{kind}><bldg:lod2MultiSurface><gml:MultiSurface>{poly(pid, pts)}'
            f'</gml:MultiSurface></bldg:lod2MultiSurface></bldg:{kind}></bldg:boundedBy>')


def box_solid(x, y, w, d, z0, z1, ridge=None, tag="b"):
    """Ground, a wall and a roof (flat at z1, or two slopes from z1 to the ridge) of a w x d box."""
    g = [(x, y, z0), (x, y + d, z0), (x + w, y + d, z0), (x + w, y, z0)]
    s = surface("GroundSurface", f"{tag}g", g)
    s += surface("WallSurface", f"{tag}w", [(x, y, z0), (x + w, y, z0), (x + w, y, z1), (x, y, z1)])
    if ridge is None:
        s += surface("RoofSurface", f"{tag}r", [(x, y, z1), (x + w, y, z1), (x + w, y + d, z1), (x, y + d, z1)])
    else:
        m = y + d / 2
        s += surface("RoofSurface", f"{tag}r1", [(x, y, z1), (x + w, y, z1), (x + w, m, ridge), (x, m, ridge)])
        s += surface("RoofSurface", f"{tag}r2", [(x, m, ridge), (x + w, m, ridge), (x + w, y + d, z1), (x, y + d, z1)])
    return s


def tile():
    a = (f'<bldg:Building gml:id="A"><gen:stringAttribute name="DatenquelleDachhoehe"><gen:value>5000</gen:value>'
         f'</gen:stringAttribute><bldg:function>31001_1010</bldg:function><bldg:roofType>3100</bldg:roofType>'
         f'<bldg:measuredHeight uom="m">20.0</bldg:measuredHeight>'
         f'{box_solid(X0 + 100, Y0 + 100, 20, 10, 35.0, 50.0, ridge=55.0, tag="a")}</bldg:Building>')
    parts = "".join(
        f'<bldg:consistsOfBuildingPart><bldg:BuildingPart gml:id="B{i}"><bldg:roofType>1000</bldg:roofType>'
        f'<bldg:measuredHeight uom="m">{h}</bldg:measuredHeight>'
        f'{box_solid(X0 + 300 + 30 * i, Y0 + 300, 30, 30, 36.0, 36.0 + h, tag=f"b{i}")}</bldg:BuildingPart>'
        f'</bldg:consistsOfBuildingPart>' for i, h in ((0, 12.0), (1, 60.0)))
    b = f'<bldg:Building gml:id="B"><bldg:function>31001_2000</bldg:function>{parts}</bldg:Building>'
    c = (f'<bldg:Building gml:id="C"><bldg:function>51009_1610</bldg:function><bldg:measuredHeight>3</bldg:measuredHeight>'
         f'{box_solid(X0 + 500, Y0 + 500, 5, 5, 36.0, 39.0, tag="c")}</bldg:Building>')
    out = (f'<bldg:Building gml:id="D"><bldg:function>31001_1010</bldg:function><bldg:measuredHeight>9</bldg:measuredHeight>'
           f'{box_solid(X0 + 5000, Y0 + 500, 10, 10, 36.0, 45.0, tag="d")}</bldg:Building>')
    members = "".join(f"<core:cityObjectMember>{m}</core:cityObjectMember>" for m in (a, b, c, out))
    return ('<?xml version="1.0" encoding="UTF-8"?><core:CityModel xmlns:core="http://www.opengis.net/citygml/1.0" '
            'xmlns:bldg="http://www.opengis.net/citygml/building/1.0" xmlns:gml="http://www.opengis.net/gml" '
            'xmlns:gen="http://www.opengis.net/citygml/generics/1.0" xmlns:xlink="http://www.w3.org/1999/xlink">'
            f'{members}</core:CityModel>')


def test_citygml_source(tmp_path):
    (tmp_path / "city.toml").write_text(CITY_TOML)
    data = tmp_path / "data"
    (data / "raw" / "lod2").mkdir(parents=True)
    gpd.GeoDataFrame({"name": ["Core"], "relation": [1]}, geometry=[box(X0, Y0, X0 + 1000, Y0 + 1000)], crs=UTM).to_crs(
        "EPSG:4326").to_file(data / "boundary.gpkg")
    with zipfile.ZipFile(data / "raw" / "lod2" / "LoD2_390_5818.zip", "w") as z:
        z.writestr("LoD2_33_390_5818_1_BE.xml", tile())
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-m", "city3d", "02_lod2"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    g = gpd.read_file(data / "lod2_buildings.gpkg").set_index("gml_id")
    assert sorted(g.index) == ["A", "B0", "B1"]                     # C dropped by function, D outside the district
    assert g.loc["A", "h"] == 20.0 and g.loc["A", "roof_top_z"] == 55.0 and g.loc["A", "eave_z"] == 50.0
    assert g.loc["A", "ground_elevation"] == 35.0 and g.loc["A", "rooftype"] == "3100"
    assert g.loc["B1", "h"] == 60.0 and g.loc["B1", "parent_id"] == "B" and bool(g.loc["B1", "part"])
    assert g.loc["B0", "function"] == "31001_2000"                 # the parent's function, inherited
    a = g.to_crs(UTM).loc["A"].geometry
    assert abs(a.area - 200.0) < 0.5 and abs(a.bounds[0] - (X0 + 100)) < 1.0
