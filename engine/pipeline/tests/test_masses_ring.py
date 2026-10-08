"""[ground] masses_ring (stages/masses.py, opt-in, Tokyo M7 fix round): a ring's footprints taken from
cover_buildings.gpkg into the masses, flagged, kept by keep_clipped, with the ring's own cover heights; off by default.
Each case runs in a fresh interpreter on a throwaway city.toml. Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

CITY_TOML = """
name = "ring"
utm_epsg = 32648
[districts]
"Core" = 1
[paths]
data = "data"
[ground]
masses = true
masses_reach = 2000.0
masses_within = "clip.geojson"
{ring}
"""


def box_ll(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


CLIP = box_ll(103.80, 1.30, 103.81, 1.31)
RING = box_ll(103.82, 1.30, 103.83, 1.31)


def run(tmp_path, body, ring=""):
    (tmp_path / "city.toml").write_text(CITY_TOML.format(ring=ring))
    (tmp_path / "clip.geojson").write_text(json.dumps(CLIP))
    (tmp_path / "ring.geojson").write_text(json.dumps(RING))
    (tmp_path / "data").mkdir(exist_ok=True)
    code = textwrap.dedent("""
        import json
        import numpy as np, geopandas as gpd, shapely
        from shapely.geometry import box
        from city3d.stages import masses
        from city3d.common import UTM
        def ll(lon, lat):
            return gpd.GeoSeries(shapely.points([lon], [lat]), crs=4326).to_crs(UTM).iloc[0].coords[0]
        def bld(osm, lon, lat, w=20, h=None, kind="yes"):
            x, y = ll(lon, lat)
            return {"osm": osm, "building": kind, "height": h, "levels": None, "min_level": None,
                    "geometry": box(x, y, x + w, y + w)}
    """) + textwrap.dedent(body)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=tmp_path)


def ok(r):
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_off_by_default(tmp_path):
    out = ok(run(tmp_path, """
        print(json.dumps([masses.RING, masses.clip("ring") is None]))
    """))
    assert json.loads(out) == [{}, True]


def test_ring_footprints_added_and_kept(tmp_path):
    out = ok(run(tmp_path, """
        cover = gpd.GeoDataFrame([bld("w1", 103.825, 1.305), bld("w2", 103.826, 1.305, h="30"),
                                  bld("w3", 103.85, 1.305), bld("w4", 103.805, 1.305)], geometry="geometry", crs=UTM)
        cover.to_file(masses.COVER_CACHE, engine="pyogrio")
        b = gpd.GeoDataFrame([bld("w4", 103.805, 1.305), bld("w5", 103.806, 1.306)], geometry="geometry", crs=UTM)
        r = masses.add_ring(b)
        print(json.dumps(sorted(r["osm"].tolist())))
        print(json.dumps(dict(zip(r["osm"], r["ring"].astype(bool)))))
        r["h"] = masses.heights(r, None, r["ring"].to_numpy(bool))
        print(json.dumps(dict(zip(r["osm"], masses.keep_clipped(r).tolist()))))
        print(json.dumps(dict(zip(r["osm"], r["h"].round(1)))))
    """, ring='masses_ring = { file = "ring.geojson", cover_h = [[0.0, 1.0], [4.0, 4.0]] }')).splitlines()[-4:]
    assert json.loads(out[0]) == ["w1", "w2", "w4", "w5"]           # w3 outside the ring; w4 not doubled
    assert json.loads(out[1]) == {"w4": False, "w5": False, "w1": True, "w2": True}
    assert all(json.loads(out[2]).values())                        # the clip's and the ring's all kept
    h = json.loads(out[3])
    assert h["w2"] == 30.0                                          # tagged: its own height
    assert 3.0 <= h["w1"] <= 4.0 * 1.12 + 1e-6                     # untagged in the ring: cover_h (4 m +-12 %)
    assert h["w5"] > 5.0                                            # outside the ring: the default curve (7 m and more)


def test_missing_cover_cache_is_an_error(tmp_path):
    r = run(tmp_path, """
        b = gpd.GeoDataFrame([bld("w4", 103.805, 1.305)], geometry="geometry", crs=UTM)
        masses.add_ring(b)
    """, ring='masses_ring = { file = "ring.geojson" }')
    assert r.returncode != 0 and "cover_buildings" in r.stderr


def test_under_masses(tmp_path):
    """cover_roofs.under_masses: footprints in the main clip and in the ring are the ones left unpainted."""
    out = ok(run(tmp_path, """
        g = [bld("a", 103.805, 1.305)["geometry"], bld("b", 103.825, 1.305)["geometry"], bld("c", 103.85, 1.305)["geometry"]]
        print(json.dumps(masses.under_masses(g).tolist()))
    """, ring='masses_ring = { file = "ring.geojson" }'))
    assert json.loads(out.splitlines()[-1]) == [True, True, False]
