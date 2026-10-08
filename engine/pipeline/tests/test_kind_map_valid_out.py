"""[buildings] kind_map and valid_out (Hong Kong M2 fix round). Off (the defaults) they change nothing; on, a kind is
renamed after every other kind rule, and the table's invalid geometries are repaired as written. Run:
`uv run pytest tests`.
"""
from test_osm_tags import BUILDINGS, run

BODY = BUILDINGS + """
import pandas as pd
from shapely.geometry import Polygon
k = pd.Series(["village", "tower", "house", "village"])
bow = Polygon([(103.85, 1.30), (103.851, 1.301), (103.851, 1.30), (103.85, 1.301)])     # a self-touching bow tie
ok = box(103.852, 1.30, 103.853, 1.301)
g = gpd.GeoDataFrame({"i": [0, 1]}, geometry=[bow, ok], crs="EPSG:4326")
v = bd.valid_out(g)
print(json.dumps([bd.remap_kinds(k).tolist(), int(v.geometry.is_valid.sum()), len(v), v.geometry.iloc[1].equals(ok)]))
"""


def test_off_changes_nothing(tmp_path):
    kinds, valid, n, same = run(tmp_path, BODY)
    assert kinds == ["village", "tower", "house", "village"]
    assert valid == 1 and n == 2 and same


def test_on(tmp_path):
    kinds, valid, n, same = run(tmp_path, BODY, '[buildings]\nkind_map = { village = "midrise" }\nvalid_out = true\n')
    assert kinds == ["midrise", "tower", "house", "midrise"]
    assert valid == 2 and n == 2 and same
