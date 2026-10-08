"""Singapore M5 fix round 1 opt-ins, off by default:
1. [ground] green_tags / green_ids (05_ground): more areas drawn as green, by tag combinations and by OSM id (the
   Padang, leisure=pitch with no surface tag, fell to the land's urban lots).
2. [shores] pond_edge_area (05e_shores): lakes and reservoirs at least that large take the stone edge beside lawns too
   (Marina Bay's granite promenades read as a park pond's white boulders).
Run: `uv run pytest tests`.
"""
import tomllib
from pathlib import Path

from test_osm_tags import run

QUERY = """
    import json
    from city3d.stages import ground
    print(json.dumps([ground.GREEN_TAGS, ground.GREEN_IDS, ground.green_extra_query("1.2,103.8,1.3,103.9")]))"""


def test_green_extra_off_by_default(tmp_path):
    tags, ids, q = run(tmp_path, QUERY)
    assert tags == [] and ids == []
    assert q == "[out:json][timeout:600][bbox:1.2,103.8,1.3,103.9];();out geom;"


def test_green_extra_query(tmp_path):
    toml = '[ground]\ngreen_tags = ["leisure=pitch;surface=grass"]\ngreen_ids = ["way/21587770", "relation/42"]\n'
    tags, ids, q = run(tmp_path, QUERY, toml)
    assert tags == ["leisure=pitch;surface=grass"] and ids == ["way/21587770", "relation/42"]
    assert 'way["leisure"="pitch"]["surface"="grass"]; rel["leisure"="pitch"]["surface"="grass"];' in q
    assert "way(id:21587770);" in q and "rel(id:42);" in q


TYPES = """
    import json
    import numpy as np
    from city3d.stages import shores
    kinds = np.array(["pond", "pond", "pond", "river", "pond"])
    soft = np.array([True, True, False, True, True])
    warea = np.array([2e6, 4e5, 2e6, 2e6, 0.0])
    print(json.dumps([shores.POND_EDGE_AREA, list(shores.bank_types(kinds, soft, warea)),
                      list(shores.bank_types(kinds, soft))]))"""


def test_pond_edge_area_off_is_by_the_green(tmp_path):
    area, typed, untyped = run(tmp_path, TYPES)
    assert area == 0.0
    assert typed == untyped == ["pondbank", "pondbank", "pondedge", "embankment", "pondbank"]


def test_pond_edge_area_walls_big_lakes(tmp_path):
    area, typed, untyped = run(tmp_path, TYPES, "[shores]\npond_edge_area = 1.0\n")
    assert area == 1.0
    # the 2 km² lake walled beside the lawn too; the 0.4 km² pond and a bank with no water found (0) keep their soft bank
    assert typed == ["pondedge", "pondbank", "pondedge", "embankment", "pondbank"]
    assert untyped == ["pondbank", "pondbank", "pondedge", "embankment", "pondbank"]


def test_defaults_off():
    d = tomllib.loads((Path(__file__).resolve().parents[1] / "src" / "city3d" / "defaults.toml").read_text())
    assert d["ground"]["green_tags"] == [] and d["ground"]["green_ids"] == []
    assert d["shores"]["pond_edge_area"] == 0.0
