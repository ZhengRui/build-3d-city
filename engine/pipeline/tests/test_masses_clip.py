"""[ground] masses_within (stages/masses.py): the opt-in clip of the block masses to GeoJSON polygons, on tiny
synthetic footprints; and that with the key empty (the default, every existing city) it does nothing. The stage
reads the city's settings at import, so each case runs in a fresh interpreter on a throwaway city.toml.
Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

import pytest

CITY_TOML = """
name = "clip"
utm_epsg = 32648
[districts]
"Core" = 1
[paths]
data = "data"
[ground]
masses = true
masses_reach = 2000.0
{within}
"""

# a 1 km box at 103.80 E, 1.30 N (Singapore, UTM 48N): two buildings in, one out, an L whose centroid is outside
BOX = {"type": "Polygon", "coordinates": [[[103.80, 1.30], [103.81, 1.30], [103.81, 1.31], [103.80, 1.31],
                                           [103.80, 1.30]]]}
FC = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {}, "geometry": BOX},
    {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [103.0, 1.0]}}]}


def run(tmp_path, body, within='masses_within = "clip.geojson"', files=None):
    """Run `body` (python, with `masses` imported and a helper `ll(lon, lat)` -> UTM x, y) in the throwaway city."""
    (tmp_path / "city.toml").write_text(CITY_TOML.format(within=within))
    for name, content in (files or {}).items():
        (tmp_path / name).write_text(content if isinstance(content, str) else json.dumps(content))
    code = textwrap.dedent("""
        import json, sys
        import numpy as np, geopandas as gpd, shapely
        from shapely.geometry import box, Polygon
        from city3d.stages import masses
        from city3d.common import UTM
        def ll(lon, lat):
            return gpd.GeoSeries(shapely.points([lon], [lat]), crs=4326).to_crs(UTM).iloc[0].coords[0]
    """) + textwrap.dedent(body)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=tmp_path)


def ok(r):
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_footprints_in_and_out(tmp_path):
    """Whole buildings are kept or dropped by a point inside them; the L's centroid lies outside the polygon,
    its representative point inside, and a building straddling the edge is judged by that point alone."""
    out = ok(run(tmp_path, """
        c = masses.clip()
        x0, y0 = ll(103.80, 1.30); x1, y1 = ll(103.81, 1.31)
        inside = box(x0 + 100, y0 + 100, x0 + 130, y0 + 120)
        outside = box(x1 + 500, y1 + 500, x1 + 530, y1 + 520)
        straddle_in = box(x1 - 40, y0 + 300, x1 + 20, y0 + 340)       # most of it in, the middle in
        straddle_out = box(x1 - 10, y0 + 500, x1 + 50, y0 + 540)      # mostly out
        # a thin L: arm along the bottom edge inside, a long arm out of the box; centroid out, a point of it in
        ell = Polygon([(x1 - 60, y0 + 10), (x1 + 400, y0 + 10), (x1 + 400, y0 + 30), (x1 - 40, y0 + 30),
                       (x1 - 40, y0 + 60), (x1 - 60, y0 + 60)])
        g = gpd.GeoSeries([inside, outside, straddle_in, straddle_out], crs=UTM)
        print(json.dumps(masses.within(g, c).tolist()))
        e = gpd.GeoSeries([ell], crs=UTM)
        print(json.dumps([bool(c.contains(ell.centroid)), bool(masses.within(e, c)[0])]))
    """, files={"clip.geojson": FC})).splitlines()
    assert json.loads(out[0]) == [True, False, True, False]
    assert json.loads(out[1]) == [False, True]


def test_clip_reads_collection_feature_and_bare_geometry(tmp_path):
    out = ok(run(tmp_path, """
        import tempfile, pathlib
        for name in ("a.geojson", "b.geojson", "c.geojson", "d.geojson"):
            print(round(masses.read_clip(name).area * 1e8))
    """, files={"a.geojson": FC, "b.geojson": {"type": "Feature", "properties": {}, "geometry": BOX},
                "c.geojson": BOX,
                "d.geojson": {"type": "FeatureCollection", "features": [
                    {"type": "Feature", "geometry": BOX, "properties": {}},
                    {"type": "Feature", "properties": {}, "geometry": {
                        "type": "MultiPolygon", "coordinates": [[[[103.90, 1.30], [103.91, 1.30], [103.91, 1.31],
                                                                  [103.90, 1.31], [103.90, 1.30]]]]}}]}})).split()
    assert out[:3] == ["10000"] * 3            # 0.01 x 0.01 degrees; the point is ignored
    assert out[3] == "20000"                              # a Polygon and a MultiPolygon: the union


def test_errors_are_clear(tmp_path):
    for name, content, text in [("missing.geojson", None, "no such file"),
                                ("point.geojson", {"type": "Point", "coordinates": [103.8, 1.3]},
                                 "no Polygon or MultiPolygon"),
                                ("empty.geojson", {"type": "FeatureCollection", "features": []},
                                 "no Polygon or MultiPolygon"),
                                ("bad.geojson", "{not json", "not valid JSON"),
                                ("utm.geojson", {"type": "Polygon", "coordinates": [[[366000, 143000], [367000, 143000],
                                                                                      [367000, 144000], [366000, 143000]]]},
                                 "outside lon/lat")]:
        files = {} if content is None else {name: content}
        r = run(tmp_path, f"masses.read_clip({name!r})", files=files)
        assert r.returncode != 0 and text in r.stderr and "masses_within" in r.stderr, (name, r.stderr[-800:])


def test_stage_stops_on_a_bad_file_before_fetching(tmp_path):
    """run() loads the clip first: a missing file is an error at once, not after a fetch."""
    r = run(tmp_path, "masses.run([])")
    assert r.returncode != 0 and "no such file" in r.stderr and "masses_within" in r.stderr


def test_off_is_a_no_op(tmp_path):
    """With the key empty (the default) clip() is None, reads no file, and main() takes its old branches: the
    fetch grid is the plain one (every 5 km chunk of the box), the cache is judged by its bounds as before."""
    out = ok(run(tmp_path, """
        asked = []
        def fake(q):
            asked.append(q)
            n = len(asked)
            ring = [{"lon": 103.0 + 0.001 * n + dx, "lat": 1.0 + dy} for dx, dy in
                    ((0, 0), (0.0001, 0), (0.0001, 0.0001), (0, 0.0001), (0, 0))]
            return {"elements": [{"type": "way", "id": n, "tags": {"building": "yes"}, "geometry": ring}]}
        masses.overpass = fake
        res = [masses.MASSES_WITHIN == "", masses.clip() is None]
        res.append([len(masses.fetch((103.0, 1.0, 103.13, 1.08))), len(asked)])   # 2 x 2 chunks, a building each
        asked.clear()
        masses.fetch((103.0, 1.0, 103.13, 1.08), shapely.box(103.0, 1.0, 103.05, 1.03))   # only the first chunk
        res.append(len(asked))
        print("RESULT", json.dumps(res))
    """, within=""))
    res = json.loads(out.split("RESULT")[1])
    assert res == [True, True, [4, 4], 1]         # four buildings from four queries; the clip asks for one chunk


def test_default_is_empty_and_documented():
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src" / "city3d"
    import tomllib
    d = tomllib.loads((src / "defaults.toml").read_text())
    assert d["ground"]["masses_within"] == ""
    text = (src / "stages" / "masses.py").read_text()
    # every use of the clip is behind `cut is not None` / `clip() is not None`
    assert text.count("cut is not None") >= 4 and text.count("cut is None") == 1


def test_cache_stamp_changes_with_the_clip(tmp_path):
    out = ok(run(tmp_path, """
        import shapely
        reg = box(0, 0, 5000, 5000)
        a = masses.clip_stamp(box(0, 0, 1000, 1000), reg)
        b = masses.clip_stamp(box(0, 0, 1000, 1000), reg)
        c = masses.clip_stamp(box(0, 0, 1000, 1500), reg)
        d = masses.clip_stamp(box(0, 0, 1000, 1000), box(0, 0, 7000, 5000))
        print(a == b, a == c, a == d)
    """, files={"clip.geojson": FC}))
    assert out.split() == ["True", "False", "False"]


MAIN_BODY = """
    import re, io, contextlib
    X, Y = 366000.0, 143000.0
    data = masses.DATA
    data.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"a": [1]}, geometry=[box(X - 2000, Y - 2000, X + 2000, Y + 2000)], crs=UTM).to_file(
        data / "ground.gpkg", layer="area", driver="GPKG")
    gpd.GeoDataFrame({"name": ["Core"]}, geometry=[box(X - 250, Y - 250, X + 250, Y + 250)], crs=UTM).to_file(
        data / "boundary.gpkg", driver="GPKG")
    # 10 buildings, 20 x 20 m, 20 m tall, in a row 400..1300 m east of the centre; the clip is the east half of that
    cells = [box(X + 400 + 100 * i, Y + 600, X + 420 + 100 * i, Y + 620) for i in range(10)]
    # four corner buildings at the reach's edge (thinned to none), so that the cache's bounds span the reach
    cells += [box(X + sx * 3995 - 15, Y + sy * 3995 - 15, X + sx * 3995 + 15, Y + sy * 3995 + 15)
              for sx in (-1, 1) for sy in (-1, 1)]
    calls = []
    def fake_fetch(bbox_ll, only=None):
        calls.append(only is not None)
        return gpd.GeoDataFrame({"osm": [f"w{i + 1}" for i in range(len(cells))], "building": "yes", "height": "20",
                                 "levels": None, "min_level": None}, geometry=cells, crs=UTM)
    masses.fetch = fake_fetch
    class Stop(Exception):
        pass
    def stop(*a):
        raise Stop()
    masses.Terrain = stop
    res = {}
    for label in ("run1", "run2"):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                masses.main()
        except Stop:
            pass
        m = re.search(r"([0-9,]+) buildings beyond the districts", buf.getvalue())
        res[label] = [int(m.group(1).replace(",", "")), len(calls), masses.CLIP_STAMP.exists(),
                      masses.CACHE.exists()]
    print("RESULT", json.dumps(res))
"""


def main_result(tmp_path, within, files=None):
    return json.loads(ok(run(tmp_path, MAIN_BODY, within=within, files=files)).split("RESULT")[1])


def test_main_keeps_only_buildings_in_the_clip(tmp_path):
    """The stage end to end up to the terrain, on ten footprints in a row 400..1300 m east of the centre: a clip
    over x 800..1500 m keeps the six whose point lies in it, fetches once and stamps the cache; a second run
    reuses the cache (no second fetch)."""
    (tmp_path / "city.toml").write_text(CITY_TOML.format(within=""))
    code = ("import json, geopandas as gpd; from shapely.geometry import box; "
            "g = gpd.GeoSeries([box(366800, 143500, 367500, 143700)], crs='EPSG:32648').to_crs(4326).iloc[0]; "
            "open('clip.geojson', 'w').write(json.dumps(g.__geo_interface__))")
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True)
    res = main_result(tmp_path, 'masses_within = "clip.geojson"')
    assert res["run1"] == [6, 1, True, True]
    assert res["run2"] == [6, 1, True, True]


def test_main_off_keeps_all_and_leaves_no_stamp(tmp_path):
    res = main_result(tmp_path, "")
    assert res["run1"] == [10, 1, False, True]
    assert res["run2"] == [10, 1, False, True]        # the plain cache check passes: no second fetch


def test_cache_follows_the_setting(tmp_path):
    """A cache fetched under a clip is fetched again when the key is emptied (and its stamp goes), and the other
    way round: it never feeds a run it was not fetched for."""
    (tmp_path / "city.toml").write_text(CITY_TOML.format(within=""))
    code = ("import json, geopandas as gpd; from shapely.geometry import box; "
            "g = gpd.GeoSeries([box(366800, 143500, 367500, 143700)], crs='EPSG:32648').to_crs(4326).iloc[0]; "
            "open('clip.geojson', 'w').write(json.dumps(g.__geo_interface__))")
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True)
    assert main_result(tmp_path, 'masses_within = "clip.geojson"')["run1"] == [6, 1, True, True]
    assert main_result(tmp_path, "")["run1"] == [10, 1, False, True]            # fetched again, stamp gone
    assert main_result(tmp_path, 'masses_within = "clip.geojson"')["run1"] == [6, 1, True, True]
