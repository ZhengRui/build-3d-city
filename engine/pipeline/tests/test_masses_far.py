"""[ground] masses_thin and [terrain] cover_inner_reach (Singapore M7: Johor Bahru's towers as masses 15 km out, inside a
masses_within clip, without thinning; the inner cover map kept to its old reach). Off by default: the masses thin out
towards masses_reach and the inner map reaches as far as the masses."""
from test_osm_tags import run

BODY = """
    import json
    from city3d.stages import masses
    print(json.dumps([masses.THIN, masses.INNER_REACH, masses.REACH]))"""


def test_defaults(tmp_path):
    assert run(tmp_path, BODY, "[ground]\nmasses_reach = 5000.0") == [True, 5000.0, 5000.0]


def test_far_islands(tmp_path):
    toml = "[ground]\nmasses_reach = 18000.0\nmasses_thin = false\n[terrain]\ncover_inner_reach = 0.0"
    assert run(tmp_path, BODY, toml) == [False, 0.0, 18000.0]


TALL = """
    import json
    from pathlib import Path
    import geopandas as gpd
    from shapely.geometry import box
    sq = lambda x0, y0, x1, y1: {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
    Path("main.geojson").write_text(json.dumps(sq(103.80, 1.30, 103.81, 1.31)))
    Path("tall.geojson").write_text(json.dumps(sq(103.82, 1.30, 103.83, 1.31)))
    from city3d.stages import masses
    pts = [(103.805, 10.0), (103.805, 50.0), (103.825, 10.0), (103.825, 50.0), (103.845, 50.0)]
    b = gpd.GeoDataFrame({"h": [h for _, h in pts]}, geometry=[box(x, 1.305, x + 1e-4, 1.3051) for x, _ in pts],
                         crs="EPSG:4326").to_crs(32648)
    print(json.dumps([bool(k) for k in masses.keep_clipped(b)]))"""


def test_tall_within(tmp_path):
    on = run(tmp_path, TALL, '[ground]\nmasses_within = "main.geojson"\nmasses_tall_within = { file = "tall.geojson", min_h = 30.0 }')
    off = run(tmp_path, TALL, '[ground]\nmasses_within = "main.geojson"')
    assert on == [True, True, False, True, False]       # the main clip whole; the tall clip from 30 m; outside none
    assert off == [True, True, False, False, False]
