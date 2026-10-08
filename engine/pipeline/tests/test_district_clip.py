"""[districts] clip (stages/osm.py district_spec): the inline ring list (unchanged: same box, same Overpass query
text, so the cached answers of every existing city still match) and the opt-in GeoJSON file form
(clip = "<file>.geojson": the Feature whose properties.name is the district's key; Polygon and MultiPolygon).
The stage reads the city's settings at import, so each case runs in a fresh interpreter on a throwaway city.toml.
Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

CITY_TOML = """
name = "clipfile"
utm_epsg = 32618
[districts]
"Heights" = {{ relation = 1234, clip = {inline} }}
"Bare" = 99
"Filed" = {{ relation = 1234, clip = "data/clips.geojson" }}
[paths]
data = "data"
"""

# an inline ring with awkward coordinates (more digits than the .5f of the query, negative longitudes)
RING = [[-74.0753123456, 40.7121987], [-74.0301, 40.7121987], [-74.0301, 40.7522], [-74.0753123456, 40.7522],
        [-74.0753123456, 40.7121987]]
POLY = {"type": "Polygon", "coordinates": [[[103.80, 1.30], [103.81, 1.30], [103.81, 1.31], [103.80, 1.31],
                                            [103.80, 1.30]]]}
HOLE = {"type": "Polygon", "coordinates": [POLY["coordinates"][0],
                                           [[103.802, 1.302], [103.804, 1.302], [103.804, 1.304], [103.802, 1.304],
                                            [103.802, 1.302]]]}
MULTI = {"type": "MultiPolygon", "coordinates": [
    [[[103.90, 1.40], [103.91, 1.40], [103.91, 1.41], [103.90, 1.41], [103.90, 1.40]]],
    [[[103.95, 1.35], [103.96, 1.35], [103.96, 1.36], [103.95, 1.36], [103.95, 1.35]]]]}


def fc(*features):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": n}, "geometry": g} for n, g in features]}


def run(tmp_path, body, features=None, inline=RING):
    """Run `body` (python, with `osm` imported) in a throwaway city whose data/clips.geojson holds `features`."""
    (tmp_path / "city.toml").write_text(CITY_TOML.format(inline=json.dumps(inline)))
    (tmp_path / "data").mkdir(exist_ok=True)
    if features is not None:
        (tmp_path / "data" / "clips.geojson").write_text(json.dumps(features))
    code = textwrap.dedent("""
        import json
        from shapely.geometry import Polygon, shape
        from city3d.stages import osm
    """) + textwrap.dedent(body)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=tmp_path)


def test_inline_list_box_and_query_unchanged(tmp_path):
    """The Overpass query text for an inline ring is what it was before the geometry form (the engine caches
    answers by query text): the bbox string built from min/max of the ring, written out the old way."""
    r = run(tmp_path, f"""
        RING = {RING!r}
        calls = []
        osm.overpass = lambda q, *a, **k: calls.append(q) or {{"elements": []}}
        rel, clip = osm.district_spec(osm.DISTRICTS["Heights"], "Heights")
        assert rel == 1234 and clip.equals(Polygon(RING))
        osm.buildings(rel, clip=clip, poly=clip)
        osm.buildings(rel, "building:part", clip, clip)
        lo, la = zip(*RING)                       # the pre-geometry code, verbatim
        bb = f"({{min(la):.5f}},{{min(lo):.5f}},{{max(la):.5f}},{{max(lo):.5f}})"
        assert bb == "(40.71220,-74.07531,40.75220,-74.03010)", bb
        old = f'''
            [out:json][timeout:600];
            area({{3600000000 + 1234}})->.a;
            (way["building"](area.a){{bb}}; rel["building"]["type"="multipolygon"](area.a){{bb}};);
            out geom;
        '''
        assert " ".join(calls[0].split()) == " ".join(old.split()), calls[0]
        assert bb in calls[1] and 'way["building:part"](area.a)' in calls[1]
        print("ok")
    """)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"


def test_plain_relation_has_no_clip_and_no_box(tmp_path):
    r = run(tmp_path, """
        calls = []
        osm.overpass = lambda q, *a, **k: calls.append(q) or {"elements": []}
        assert osm.district_spec(osm.DISTRICTS["Bare"], "Bare") == (99, None)
        osm.buildings(99)
        assert "(area.a);" in calls[0] and "(area.a)(" not in calls[0], calls[0]
        assert osm.district_spec({"relation": 5, "clip": []}, "x") == (5, None)
        print("ok")
    """)
    assert r.returncode == 0, r.stderr


def test_file_clip_polygon(tmp_path):
    r = run(tmp_path, """
        rel, g = osm.district_spec(osm.DISTRICTS["Filed"], "Filed")
        assert rel == 1234 and g.geom_type == "Polygon"
        assert abs(g.area - (0.0001 - 0.000004)) < 1e-12 and g.bounds == (103.80, 1.30, 103.81, 1.31), g.bounds
        assert not g.contains(Polygon([(103.8025, 1.3025), (103.8035, 1.3025), (103.8035, 1.3035)]))  # the hole
        print("ok")
    """, features=fc(("Other", MULTI), ("Filed", HOLE)))
    assert r.returncode == 0, r.stderr


def test_file_clip_multipolygon_and_box(tmp_path):
    r = run(tmp_path, """
        calls = []
        osm.overpass = lambda q, *a, **k: calls.append(q) or {"elements": []}
        rel, g = osm.district_spec(osm.DISTRICTS["Filed"], "Filed")
        assert g.geom_type == "MultiPolygon" and len(g.geoms) == 2
        assert g.bounds == (103.90, 1.35, 103.96, 1.41), g.bounds
        osm.buildings(rel, clip=g, poly=g)
        assert "(1.35000,103.90000,1.41000,103.96000)" in calls[0], calls[0]
        print("ok")
    """, features=fc(("Other", POLY), ("Filed", MULTI)))
    assert r.returncode == 0, r.stderr


def test_file_clip_absolute_path_and_same_name_united(tmp_path):
    f = tmp_path / "elsewhere.geojson"
    f.write_text(json.dumps(fc(("Filed", POLY), ("Filed", MULTI))))
    (tmp_path / "city.toml").write_text("")           # run() rewrites it; only the file matters here
    r = run(tmp_path, f"""
        g = osm.file_clip("Filed", {str(f)!r})
        assert g.geom_type == "MultiPolygon" and len(g.geoms) == 3, g.geom_type
        print("ok")
    """, features=fc())
    assert r.returncode == 0, r.stderr


def test_missing_name_is_a_clear_error(tmp_path):
    r = run(tmp_path, """
        osm.district_spec(osm.DISTRICTS["Filed"], "Filed")
    """, features=fc(("Alpha", POLY), ("Beta", MULTI)))
    assert r.returncode != 0
    err = r.stderr
    assert "ValueError" in err and "'Filed'" in err and "clips.geojson" in err and "Alpha, Beta" in err, err


def test_missing_file_and_wrong_geometry_errors(tmp_path):
    r = run(tmp_path, "osm.district_spec(osm.DISTRICTS['Filed'], 'Filed')")           # no file written
    assert r.returncode != 0 and "FileNotFoundError" in r.stderr and "clips.geojson" in r.stderr, r.stderr
    r = run(tmp_path, "osm.district_spec(osm.DISTRICTS['Filed'], 'Filed')",
            features=fc(("Filed", {"type": "Point", "coordinates": [103.8, 1.3]})))
    assert r.returncode != 0 and "Point" in r.stderr and "Polygon or MultiPolygon" in r.stderr, r.stderr
