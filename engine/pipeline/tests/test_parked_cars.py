"""Parked cars, 7 Oct 2026 (Singapore's Meadow car park: cars across each other in crooked rows on the lawn).

1. The viewer's parked heading round-trips through the pose packing (heading + 8 x fade level, the level read back as
   floor((w + 4) / 8)): every u8 heading of cars/c_*.bin comes back as the same direction. Before the fix a heading of
   4 rad or more (u8 >= 163) came back 8 rad short, the car turned ~98 degrees across its neighbours.
2. [ground] lots_off_green's tag filter: paved surface car parks only.
3. [cars] lot_capacity caps a lot at its tagged bays (and is off by default)."""
import math
import re
from pathlib import Path

import pytest
from test_osm_tags import run

CARS_JS = Path(__file__).resolve().parents[2] / "viewer" / "cars.js"


def js_parked_heading():
    """The parked heading decode of cars.js (the `h: Float32Array.from(qh, (v) => ...)` arrow), as a Python function."""
    src = CARS_JS.read_text()
    m = re.search(r"h: Float32Array\.from\(qh, \(v\) => (.+?)\), type: qt", src)
    assert m, "parked heading decode not found in cars.js"
    expr = m.group(1).replace("Math.PI", "math.pi")
    # (JS's % on non-negative operands is Python's)
    return lambda v: eval(expr, {"math": math, "v": v})


def test_pose_packing_is_what_the_shader_unpacks():
    src = CARS_JS.read_text()
    assert "floor(poseAttr.w.add(4).div(8))" in src          # the level as the shader reads it
    assert "const w = h + 8 * Math.round(Math.min(1, fade) * 15);" in src


@pytest.mark.parametrize("fade", [1.0, 0.5, 0.0667])
def test_parked_heading_round_trip(fade):
    dec = js_parked_heading()
    for v in range(256):
        h = dec(v)
        w = h + 8 * round(min(1, fade) * 15)
        level = math.floor((w + 4) / 8)
        drawn = w - 8 * level
        want = v / 256 * 2 * math.pi
        assert abs(math.cos(drawn) - math.cos(want)) < 1e-9 and abs(math.sin(drawn) - math.sin(want)) < 1e-9, \
            f"u8 heading {v} drawn at {drawn:.3f} rad, stored {want:.3f}"
        assert round(level) == round(min(1, fade) * 15), f"u8 heading {v} changes the fade level"


def test_surface_lot_tags(tmp_path):
    out = run(tmp_path, """
        import json
        from city3d.stages.ground import surface_lot
        print(json.dumps([surface_lot(t) for t in [
            {"amenity": "parking", "parking": "surface", "capacity": "294"},
            {"amenity": "parking"},
            {"amenity": "parking", "parking": "underground", "layer": "-1"},
            {"amenity": "parking", "parking": "multi-storey", "building": "parking"},
            {"amenity": "parking", "surface": "grass"},
            {"amenity": "parking", "layer": "1"},
            {"amenity": "bus_station"}]]))""")
    assert out == [True, True, False, False, False, False, False]


LOTS = """
    import json
    from city3d.stages import cars
    sq = lambda x, tags: {"type": "way", "id": x, "tags": tags, "geometry": [
        {"lon": 103.85 + x * 1e-3, "lat": 1.30}, {"lon": 103.8505 + x * 1e-3, "lat": 1.30},
        {"lon": 103.8505 + x * 1e-3, "lat": 1.3005}, {"lon": 103.85 + x * 1e-3, "lat": 1.3005},
        {"lon": 103.85 + x * 1e-3, "lat": 1.30}]}
    lots, _ = cars.areas({"elements": [
        sq(1, {"amenity": "parking", "capacity": "294", "capacity:motorcar": "284"}),
        sq(2, {"amenity": "parking", "parking": "underground"}),
        sq(3, {"amenity": "parking", "capacity": "40"}),
        sq(4, {"amenity": "parking"})]})
    print(json.dumps([[k, c] for k, _, c in lots]))"""


def test_lot_capacity(tmp_path):
    off = run(tmp_path, LOTS, "[cars]\nparking_margin = 100.0")
    on = run(tmp_path, LOTS, "[cars]\nparking_margin = 100.0\nlot_capacity = true")
    assert off == [["car", None], ["car", None], ["car", None]]
    assert on == [["car", 284], ["car", 40], ["car", None]]


def test_lot_options_off_by_default():
    import tomllib
    d = tomllib.loads((Path(__file__).resolve().parents[1] / "src" / "city3d" / "defaults.toml").read_text())
    assert not d.get("cars", {}).get("lot_capacity", False)
    assert not d.get("ground", {}).get("lots_off_green", False)


def test_lot_pieces_all(tmp_path):
    """lots_off_green = "all" (Singapore M7): every surface lot on the land goes on the asphalt layer; true: only the
    parts inside the green (cut out of it)."""
    out = run(tmp_path, """
        import json
        from shapely.geometry import box
        from city3d.stages.ground import lot_pieces
        lots = [box(0, 0, 40, 40), box(100, 0, 140, 40), box(200, 0, 240, 40)]   # in a park, on bare land, half on the sea
        greens = [box(-10, -10, 50, 50)]
        land = box(-50, -50, 220, 100)
        r = {}
        for mode in (True, "all"):
            cut, asphalt = lot_pieces(lots, greens, land, mode)
            r[str(mode)] = [round(sum(g.area for g in cut)), sorted(round(g.area) for g in asphalt)]
        print(json.dumps(r))""")
    assert out == {"True": [1600, [1600]], "all": [1600, [800, 1600, 1600]]}
