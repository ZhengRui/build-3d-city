"""The OSM tag opt-ins for cities with underground malls and stations, sky bridges and elevated decks (Hong Kong,
Tokyo, Singapore): [osm] underground_drop, [osm] min_height, [buildings] station_untagged. Each is off by default
and then changes nothing (01_osm's columns, load_osm's rows and columns, the building table's pieces); on, it drops
or raises what it should. The stages read their settings at import, so each case runs in a fresh interpreter on a
throwaway city.toml. Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

CITY_TOML = """
name = "osmtags"
utm_epsg = 32648
[districts]
"Test" = 1
[paths]
data = "data"
[sources]
footprints = ["osm"]
heights = ["osm_height", "osm_levels", "default"]
{extra}
"""
ON = """
[osm]
underground_drop = true
min_height = true
"""


def run(tmp_path, body, toml=""):
    """Run `body` (python) on a throwaway city; the last line it prints is JSON, returned."""
    (tmp_path / "city.toml").write_text(CITY_TOML.format(extra=toml))
    (tmp_path / "data").mkdir(exist_ok=True)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(body)], env=env, capture_output=True, text=True,
                       cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def way(i, x0, tags):
    """A way of 30 m x 30 m near Singapore, x0 degrees... (tags as given)."""
    lon, lat = 103.85 + x0 * 1e-3, 1.30
    d = 0.0003
    pts = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    return {"type": "way", "id": i, "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in pts]}


TAGGED = [way(1, 0, {"building": "yes", "height": "20"}),
          way(2, 1, {"building": "train_station", "underground": "yes"}),
          way(3, 2, {"building": "retail", "location": "indoor"}),
          way(4, 3, {"building": "retail", "level": "-1"}),
          way(5, 4, {"building": "retail", "level": "-2;-1"}),
          way(6, 5, {"building": "retail", "level": "-1;0"}),          # reaches the ground floor: stays
          way(7, 6, {"building": "retail", "level": "B1"}),            # unreadable: stays
          way(8, 7, {"building": "retail", "layer": "-1"}),            # today's rule, on or off
          way(9, 8, {"building": "yes", "height": "207", "min_height": "193"}),
          way(10, 9, {"building": "yes", "building:min_level": "40", "building:levels": "44"})]

OLD_COLS = ["osm_id", "building", "name", "height", "levels", "layer", "location", "geometry"]


def test_01_osm_columns_off_are_unchanged(tmp_path):
    out = run(tmp_path, f"""
        import json
        from city3d.stages import osm
        osm.overpass = lambda q, *a, **k: {{"elements": {TAGGED!r}}}
        b = osm.buildings(1)
        p = osm.buildings(1, "building:part")
        print(json.dumps([list(b.columns), list(p.columns)]))
    """)
    assert out[0] == OLD_COLS
    assert out[1] == OLD_COLS[:-1] + ["min_height", "min_level", "roof_shape", "roof_height", "colour", "material",
                                      "part", "geometry"]


def test_01_osm_columns_on_keep_the_tags(tmp_path):
    out = run(tmp_path, f"""
        import json
        from city3d.stages import osm
        osm.overpass = lambda q, *a, **k: {{"elements": {TAGGED!r}}}
        b = osm.buildings(1)
        p = osm.buildings(1, "building:part")
        row = lambda i: b.set_index("osm_id").loc[i]
        print(json.dumps([list(b.columns), list(p.columns), str(row("w9").min_height), str(row("w10").min_level),
                          str(row("w2").underground), str(row("w5").level)]))
    """, ON)
    assert out[0] == OLD_COLS[:-1] + ["min_height", "min_level", "underground", "level", "geometry"]
    assert out[1][-3:-1] == ["underground", "level"] and out[1].count("min_height") == 1
    assert out[2:] == ["193", "40", "yes", "-2;-1"]


FRAME = """
import geopandas as gpd, json
from shapely.geometry import box
rows = {rows}
g = gpd.GeoDataFrame(rows, geometry=[box(500000 + 40 * i, 144000, 500030 + 40 * i, 144030) for i in range(len(rows["osm_id"]))],
                     crs="EPSG:32648").to_crs(4326)
g.to_file("data/osm_buildings.gpkg")
from city3d import common
o = common.load_osm({under})
"""
ROWS = {"osm_id": [f"w{i}" for i in range(1, 11)],
        "building": ["yes", "train_station"] + ["retail"] * 6 + ["yes", "yes"],
        "name": [None] * 10,
        "height": ["20", None, None, None, None, None, None, None, "207", None],
        "levels": [None] * 9 + ["44"],
        "layer": [None] * 7 + ["-1", None, None],
        "location": [None, None, "indoor"] + [None] * 7,
        "underground": [None, "yes"] + [None] * 8,
        "level": [None] * 3 + ["-1", "-2;-1", "-1;0", "B1"] + [None] * 3,
        "min_height": [None] * 8 + ["193", None],
        "min_level": [None] * 9 + ["40"]}


def test_load_osm_off_keeps_today_s_rules_and_columns(tmp_path):
    """Off, with a file that carries every new tag: only layer < 0 goes (and location=underground), the columns are
    the file's plus h_tag, h_levels, h: no min_h_tag."""
    out = run(tmp_path, FRAME.format(rows=ROWS, under="False") + """
print(json.dumps([sorted(o.osm_id), [c for c in o.columns if c.startswith("min_h")]]))
""")
    assert out[0] == sorted(f"w{i}" for i in (1, 2, 3, 4, 5, 6, 7, 9, 10))
    assert out[1] == ["min_height"]


def test_load_osm_underground_drop_and_min_height_on(tmp_path):
    out = run(tmp_path, FRAME.format(rows=ROWS, under="False") + """
print(json.dumps([sorted(o.osm_id), dict(zip(o.osm_id, o.min_h_tag.fillna(-1)))]))
""", ON)
    # underground=yes (w2), location=indoor (w3), level -1 (w4) and -2;-1 (w5) go; w6 (-1;0), w7 (B1) stay; w8: layer
    assert out[0] == ["w1", "w10", "w6", "w7", "w9"]
    assert out[1]["w9"] == 193 and out[1]["w10"] == 40 * 3.2 and out[1]["w1"] == -1


def test_load_osm_underground_drop_also_when_surface_layers_keep_them_all(tmp_path):
    out = run(tmp_path, FRAME.format(rows=ROWS, under="True") + """
print(json.dumps(sorted(o.osm_id)))
""", "[osm]\nunderground_drop = true\n")
    assert out == ["w1", "w10", "w6", "w7", "w8", "w9"]


BUILDINGS = """
import geopandas as gpd, json, numpy as np, pandas as pd
from shapely.geometry import box
from city3d import common
from city3d.stages import buildings as bd
def osm_frame(rows):
    n = len(rows["osm_id"])
    g = gpd.GeoDataFrame(rows, geometry=[box(500000 + 100 * i, 144000, 500030 + 100 * i, 144030) for i in range(n)],
                         crs="EPSG:32648")
    g["h_tag"] = g["height"].map(common.height_m)
    g["h_levels"] = g["levels"].map(common.height_m) * 3.2
    g["h"] = g["h_tag"].fillna(g["h_levels"])
    if "min_height" in g and common.MIN_HEIGHT_TAGS:
        g["min_h_tag"] = g["min_height"].map(common.height_m).fillna(g["min_level"].map(common.height_m) * 3.2)
    return g
"""
DECKS = {"osm_id": ["w1", "w2", "w3"], "building": ["yes", "yes", "yes"], "name": [None] * 3,
         "height": ["207", "30", None], "levels": [None, None, "10"], "min_height": ["193", None, None],
         "min_level": [None, None, "5"]}


def test_attach_osm_min_height(tmp_path):
    body = BUILDINGS + f"""
o = osm_frame({DECKS!r})
b = gpd.GeoDataFrame({{"source": ["osm"] * 3}}, geometry=list(o.geometry), crs=o.crs)
bd.attach_osm(b, o)
print(json.dumps([list(b.columns), b["min_h"].tolist() if "min_h" in b else None,
                  b["osm_deck"].tolist() if "osm_deck" in b else None]))
"""
    off = run(tmp_path, body)
    assert "min_h" not in off[0] and "osm_deck" not in off[0] and off[1] is None
    on = run(tmp_path, body, ON)
    assert on[1] == [193.0, 0.0, 16.0] and on[2] == [True, False, True]      # w3: building:min_level 5 x 3.2 m


def test_deck_is_no_duplicate_of_its_tower(tmp_path):
    """A deck outline inside its tower's (193-207 m on a 0-200 m tower) survives dedupe and volume_dedupe."""
    body = BUILDINGS + """
tower, deck = box(0, 0, 40, 40), box(10, 10, 30, 30)
mk = lambda **kw: gpd.GeoDataFrame({"source": "osm", "h": [200.0, 207.0], "min_h": [0.0, 193.0], **kw},
                                   geometry=[tower, deck], crs="EPSG:32648")
plain = mk()
flagged = mk(osm_deck=[False, True])
print(json.dumps([len(bd.dedupe(plain.copy())), len(bd.dedupe(flagged.copy())),
                  bd.volume_dedupe(plain.copy()).geometry.area.tolist(),
                  bd.volume_dedupe(flagged.copy()).geometry.area.tolist()]))
"""
    out = run(tmp_path, body, ON + "[buildings]\nvolume_dedupe = true\n")
    assert out[0] == 1 and out[1] == 2           # without the flag column: today's behaviour (the smaller goes)
    assert out[2] == [1600 - 400, 400]           # today: the tower is cut open where the deck is
    assert out[3] == [1600, 400]                 # a deck keeps the tower whole


STATIONS = {"osm_id": [f"w{i}" for i in range(1, 8)],
            "building": ["train_station", "transportation", "train_station", "train_station", "yes", "train_station",
                         "train_station"],
            "name": [None] * 7,
            "height": [None, None, None, "9", None, None, None], "levels": [None] * 7}


def stations_body(extra=""):
    return BUILDINGS + f"""
o = osm_frame({STATIONS!r})
o.loc[2, "geometry"] = box(500200, 144000, 500210, 144010)      # w3: 100 m2, an entrance: stays
o.loc[6, "levels"] = "2"; o["h_levels"] = o["levels"].map(common.height_m) * 3.2; o["h"] = o["h_tag"].fillna(o["h_levels"])
st = bd.untagged_stations(o)
b = gpd.GeoDataFrame({{"source": ["osm"] * 7, "osm_id": list(o.osm_id), "h": [11.0] * 7, "h_src": ["default"] * 7}},
                     geometry=list(o.geometry), crs=o.crs)
b0 = b.copy()
bd._STATION_IDS.update(o.osm_id[st])
c = bd.station_sheds(b.copy())
print(json.dumps([list(o.osm_id[st]), bd.STATION_DROP, bd.STATION_H, c.h.tolist(), c.h_src.tolist(),
                  bool(c.equals(b0))]))
"""


def test_station_untagged_off_changes_nothing(tmp_path):
    out = run(tmp_path, stations_body())
    assert out[1] is False and out[2] is None
    assert out[5] is True and out[3] == [11.0] * 7


def test_station_untagged_height(tmp_path):
    out = run(tmp_path, stations_body(), '[buildings]\nstation_untagged = "4.5"\n')
    # w3 is 100 m2, w4 has a height, w5 is no station, w7 has levels
    assert out[0] == ["w1", "w2", "w6"] and out[2] == 4.5
    assert out[3] == [4.5, 4.5, 11.0, 11.0, 11.0, 4.5, 11.0]
    assert out[4] == ["station", "station", "default", "default", "default", "station", "default"]


def test_station_untagged_drop_mode_is_parsed(tmp_path):
    out = run(tmp_path, stations_body(), '[buildings]\nstation_untagged = "drop"\n')
    assert out[1] is True and out[2] is None and out[0] == ["w1", "w2", "w6"]
    assert out[5] is True                          # drop acts on the OSM frame in main(), sheds leave the table alone
