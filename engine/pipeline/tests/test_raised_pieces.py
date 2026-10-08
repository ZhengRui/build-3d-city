"""Raised pieces (Singapore M2's engine wishes): [osm] min_height = "decks", decks set aside by the estate and duplicate
rules, [buildings] lift_parts = "gaps" and [buildings] parts_fill_shafts. Off (the defaults, and min_height / lift_parts
= true as before) they change nothing; on, the MBS SkyPark stays on its towers, a tower with building:min_level over
its podium ring stands on the ground, Pinnacle@Duxton's skybridges float over the podium while its blocks' roof parts
don't open the blocks, and Asia Square Tower 2's hollow core is filled. Run: `uv run pytest tests`.
"""
from test_osm_tags import BUILDINGS, run

DECK_RULE = BUILDINGS + """
from shapely.geometry import Polygon
ring = box(200, 0, 260, 60).difference(box(215, 15, 245, 45))
geoms = [box(0, 0, 100, 40),            # 0 SkyPark: min 193 over the two towers
         box(5, 5, 30, 35), box(60, 5, 95, 35),     # 1, 2 towers to 193 m
         ring, box(215, 15, 245, 45),   # 3 podium ring (14 m), 4 tower over its hole, min_level 5
         box(400, 0, 404, 30),          # 5 "Canninghill Piers Skybridge", min_level 23, over nothing
         box(500, 0, 540, 40), box(505, 5, 535, 35)]  # 6 a tower; 7 its upper storeys drawn inside, min_level 14
rows = {"osm_id": [f"w{i}" for i in range(8)], "building": ["yes"] * 8,
        "name": ["SkyPark", None, None, None, None, "Canninghill Piers Skybridge", None, None],
        "height": ["207", "193", "193", "14", None, None, "87", "75"],
        "levels": [None, None, None, None, "30", "24", None, None],
        "min_height": ["193"] + [None] * 7,
        "min_level": [None] * 4 + ["5", "23", None, "14"]}
o = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:32648")
o["h_tag"] = o["height"].map(common.height_m)
o["h_levels"] = o["levels"].map(common.height_m) * 3.2
o["h"] = o["h_tag"].fillna(o["h_levels"])
if common.MIN_HEIGHT_TAGS:
    o["min_h_tag"] = o["min_height"].map(common.height_m).fillna(o["min_level"].map(common.height_m) * 3.2)
d = bd.deck_rule(o.copy())
keep = bd.drop_osm_containers(o.iloc[:3])
aside = bd.drop_osm_containers(o.iloc[:3], aside={0})
print(json.dumps([d["min_h_tag"].fillna(-1).tolist() if "min_h_tag" in d else None, bool(d.equals(o)),
                  sorted(keep.osm_id), sorted(aside.osm_id)]))
"""


def test_min_height_true_and_off_are_unchanged(tmp_path):
    off = run(tmp_path, DECK_RULE)
    assert off[0] is None and off[1] is True
    assert off[2] == []                               # today: the deck goes as an estate outline, its towers as its duplicates
    assert off[3] == ["w0", "w1", "w2"]               # set aside, it stays and so do its towers
    on = run(tmp_path, DECK_RULE, '[osm]\nmin_height = true\n')
    assert on[1] is True and on[0][4] == 16.0         # true: every min_height raises, as in 2cce663


def test_min_height_decks(tmp_path):
    out = run(tmp_path, DECK_RULE, '[osm]\nmin_height = "decks"\n')
    mh = out[0]
    assert mh[0] == 193.0                             # over two towers reaching its underside
    assert mh[5] == 23 * 3.2                          # named a skybridge
    assert mh[4] == -1                                # a tower over its podium ring's hole: on the ground
    assert mh[7] == -1                                # upper storeys inside one tower's outline: no deck


PARTS = BUILDINGS + """
import os
from shapely.geometry import box
crs = "EPSG:32648"
parts = gpd.GeoDataFrame({
    "osm_id": ["p1", "p2", "p3"], "building": [None] * 3, "name": [None] * 3,
    "height": ["75", "156", "150"], "levels": [None] * 3, "layer": [None] * 3, "location": [None] * 3,
    "min_height": ["72", "150", None], "min_level": [None] * 3, "roof_shape": [None] * 3, "roof_height": [None] * 3,
    "colour": [None] * 3, "material": [None] * 3, "part": ["yes"] * 3, "underground": [None] * 3,
    "level": [None] * 3, "district": ["Test"] * 3},
    geometry=[box(10, 5, 90, 15),               # a skybridge 72-75 m inside a 8 m podium's outline
              box(200, 0, 212, 30),             # a block's roof part 150-156 m (40 % of it), nothing mapped under it
              box(300, 0, 340, 40)], crs=crs)   # a plain tower part (no min_height)
parts.to_crs(4326).to_file("data/osm_parts.gpkg")
b = gpd.GeoDataFrame({"source": ["osm"] * 3, "osm_id": ["w1", "w2", "w3"], "name": [None] * 3,
                      "h": [8.0, 144.0, 150.0], "h_src": ["osm_height", "hdb", "osm_height"],
                      "h_osm_tag": [8.0, 150.0, 150.0], "h_osm_levels": [None] * 3},
                     geometry=[box(0, 0, 100, 30), box(200, 0, 230, 30), box(300, 0, 340, 40)], crs=crs)
out = bd.use_parts(b.copy())
out = out.assign(a=out.area.round()).sort_values(["osm_id", "min_h", "h", "a"])
print(json.dumps([[r.osm_id, float(r.min_h), float(r.h), float(r.a)] for r in out.itertuples()]))
"""


def test_lift_parts_off_and_true_are_unchanged(tmp_path):
    off = run(tmp_path, PARTS, "[buildings]\nparts = true\n")
    # off: the skybridge and the roof part stand on the ground
    assert ["w1", 0.0, 75.0, 800.0] in off and ["w2", 0.0, 156.0, 360.0] in off
    on = run(tmp_path, PARTS, "[buildings]\nparts = true\nlift_parts = true\n")
    # true (Paris): both float, the block opens under its roof part
    assert ["w1", 72.0, 75.0, 800.0] in on and ["w2", 150.0, 156.0, 360.0] in on


def test_lift_parts_gaps(tmp_path):
    out = run(tmp_path, PARTS, '[buildings]\nparts = true\nlift_parts = "gaps"\n')
    assert ["w1", 72.0, 75.0, 800.0] in out           # the skybridge floats...
    assert ["w1", 0.0, 16.0, 2200.0] in out           # the rest of the podium (use_parts' rule: 5 storeys at most)
    assert ["w1", 0.0, 16.0, 800.0] in out            # the podium's body stays under it, at the rest's height
    assert ["w2", 0.0, 156.0, 360.0] in out           # the block's roof part stands on its (unmapped) floors
    assert ["w3", 0.0, 150.0, 1600.0] in out


SHAFTS = BUILDINGS + """
from shapely.geometry import box
walls = [box(0, 0, 42, 10), box(0, 32, 42, 42), box(0, 10, 10, 32), box(32, 10, 42, 32)]   # four towers round a core
hs = [222.0, 216.0, 183.0, 173.0]
core = box(10, 10, 32, 32)                      # 484 m2, 22 m wide
court = [(g.area, h) for g, h in bd.fill_shafts(core, 3.5, walls, hs, [0.0] * 4)]
low = [(g.area, h) for g, h in bd.fill_shafts(core, 3.5, walls, [20.0] * 4, [0.0] * 4)]
print(json.dumps([court, low]))
"""


def test_parts_fill_shafts(tmp_path):
    off = run(tmp_path, SHAFTS)
    assert off[0] == [[484.0, 3.5]]                   # off: as it was
    on = run(tmp_path, SHAFTS, "[buildings]\nparts_fill_shafts = 5.0\n")
    assert on[0] == [[484.0, 173.0]]                  # a shaft: the lowest surrounding part's height
    assert on[1] == [[484.0, 3.5]]                    # 20 m walls round 22 m: a courtyard, left open
