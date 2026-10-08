"""Tokyo M5/M6 opt-ins (7 Oct 2026), each off by default:

1. [markings] scrambles: one zebra strip per diagonal crossing over a junction box (Shibuya), across the walk.
2. [trees.zones]: area-tree cells of the `from` classes inside a named green area take a class of their own, appended
   to the class list (nothing appended without zones).
3. [trees.street.named] second: the colour seed keeps a named planting in the viewer's second broadleaf slot.
4. The viewer's opt-ins (markings.centreColour {big, small}, zebra.atSignals, giveWay 'stop') leave the default
   shader graph as it was: each is a JS-level choice whose default branch is the old expression."""
import json
import re
from pathlib import Path

from test_osm_tags import run

GROUND_JS = Path(__file__).resolve().parents[2] / "viewer" / "ground.js"

SCRAMBLE = """
[markings]
scrambles = { "Shibuya" = { lines = [[[103.8500, 1.3000], [103.8503, 1.3003]], [[103.8500, 1.3003], [103.8503, 1.3000]]], w = 4.0 } }
"""


def test_scramble_strips(tmp_path):
    out = run(tmp_path, """
        import json
        import numpy as np
        from city3d.stages.markings import scramble_strips, SCRAMBLES, ZEBRA_T
        st = scramble_strips(SCRAMBLES)
        print(json.dumps([{"n": len(st), "type": int(s["rgba"][0]) == ZEBRA_T, "g": int(s["rgba"][1]), "big": int(s["rgba"][2]),
                           "half": float(s["half"]), "along": [float(a) for a in s["along"]],
                           "w": float(np.linalg.norm(s["p"][1] - s["p"][0])), "dy": float(s["dy"])} for s in st]))""",
              toml=SCRAMBLE)
    assert len(out) == 2
    for k, s in enumerate(out):
        assert s["type"] and s["big"] == 32
        # the walk is ~47 m (0.0003 deg each way near the equator): half its length, the width code 4 x half
        assert 20 < s["half"] < 30 and s["g"] == round(s["half"] * 4)
        assert abs(s["along"][0] - 17.6) < 1e-6 and abs(s["along"][1] - 22.4) < 1e-6
        assert abs(s["w"] - 4.8) < 1e-6          # the strip runs w + 0.8 m across the walk
        assert abs(s["dy"] - 0.01 * k) < 1e-9


def test_scrambles_off_by_default(tmp_path):
    assert run(tmp_path, """
        import json
        from city3d.stages.markings import SCRAMBLES, scramble_strips
        print(json.dumps([bool(SCRAMBLES), len(scramble_strips(SCRAMBLES))]))""") == [False, 0]


ZONES = """
[trees.zones.pine]
parks = ["Gaien"]
"""


def test_tree_zones(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    # a named park and an unnamed one, each about 100 m square, side by side near Singapore (the test city's UTM 48N)
    sq = lambda lon: [{"lon": x, "lat": y} for x, y in [(lon, 1.3), (lon + 0.0009, 1.3), (lon + 0.0009, 1.3009),
                                                        (lon, 1.3009), (lon, 1.3)]]
    (raw / "osm_green.json").write_text(json.dumps({"elements": [
        {"type": "way", "id": 1, "tags": {"leisure": "park", "name": "Gaien"}, "geometry": sq(103.85)},
        {"type": "way", "id": 2, "tags": {"leisure": "park"}, "geometry": sq(103.852)}]}))
    out = run(tmp_path, """
        import json
        import numpy as np
        import geopandas as gpd
        from affine import Affine
        from city3d.stages import trees
        C, CLASSES = trees.C, trees.CLASSES
        # an 8 m mask over both parks, all park, one forest cell inside the named one
        x0, y0 = gpd.GeoSeries.from_xy([103.8495], [1.3015], crs=4326).to_crs(trees.UTM).iloc[0].coords[0]
        mask = np.full((40, 80), C["park"], np.uint8)
        mask[10, 10] = C["forest"]
        tr = Affine(trees.CELL, 0, x0, 0, -trees.CELL, y0)
        trees.zone_classes(mask, tr)
        pine = mask == C["pine"]
        cols = np.flatnonzero(pine.any(0))
        print(json.dumps([CLASSES[-1], int(pine.sum()), int(cols.min()), int(cols.max()), int(mask[10, 10] == C["forest"])]))""",
              toml=ZONES)
    name, n, c0, c1, forest_kept = out
    assert name == "pine"
    assert 120 < n < 220           # ~100 m x 100 m of 8 m cells (~156), the named park only
    assert c1 < 30                 # the unnamed park (columns from ~35 on) keeps its class
    assert forest_kept == 1        # only the `from` classes (park, grass) change


def test_tree_zones_off_by_default(tmp_path):
    out = run(tmp_path, """
        import json
        from city3d.stages import trees
        print(json.dumps(trees.CLASSES))""")
    assert out == ["none", "forest", "park", "orchard", "mangrove", "scrub", "grass", "residential", "campus",
                   "industrial", "open"]


def test_named_colour(tmp_path):
    out = run(tmp_path, """
        import json
        from city3d.stages.trees import named_colour
        print(json.dumps([[named_colour(c, {}) for c in range(64)], [named_colour(c, {"first": True}) for c in range(64)],
                          [named_colour(c, {"second": True}) for c in range(64)]]))""")
    plain, first, second = out
    assert plain == list(range(64))
    assert all(c % 5 < 3 and 0 <= c < 64 for c in first)
    assert all(c % 5 in (3, 4) and 0 <= c < 64 for c in second)
    assert len(set(c % 16 for c in second)) >= 8        # the shades (seed % 16) still vary


def test_viewer_markings_defaults_unchanged():
    src = GROUND_JS.read_text()
    # the default centre colour is the old one-colour choice; the by-size mix only for an object
    assert "let CENTRE = centreBySize ? null : colourOf(centreColour);" in src
    assert "if (centreBySize) CENTRE = mix(colourOf(centreColour.small), colourOf(centreColour.big), big);" in src
    # zebra arms, stop lines, give-way lines and studs fall back to the old factors
    assert "const zebraArms = ZB.atSignals ? jZebra.add(jSignal) : jZebra;" in src
    assert ".mul(giveWayStyle === 'stop' ? jZebra.add(jSignal).add(jGive) : jZebra.add(jSignal));" in src
    assert "const giveWay = giveWayStyle === 'stop' ? float(0) : (giveWayStyle === 'teeth'" in src
    assert re.search(r"\.mul\(ZB\.atSignals \? 0 : jSignal\);", src)
