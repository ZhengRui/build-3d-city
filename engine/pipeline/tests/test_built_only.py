"""05b_roads' opt-in [roads] built_only: ground ways cut a margin beyond the built area, except railways, decks and
the highway values kept. Run: `uv run pytest tests`."""
import os
import subprocess
import sys
import textwrap

CITY = """
name = "builtonly"
utm_epsg = 32654
[districts]
"Square" = 1
[paths]
data = "data"
"""

PROBE = '''
import geopandas as gpd
from shapely.geometry import LineString, box
from city3d.stages import roads
assert roads.BUILT_ONLY == {}
g = gpd.GeoDataFrame({"kind": ["minor", "major", "rail", "minor"], "highway": ["residential", "trunk", None, "service"],
                      "elevated": [False, False, False, True]},
                     geometry=[LineString([(0, 0), (1000, 0)])] * 4, crs="EPSG:32654")
out, km = roads.built_only(g, box(0, -10, 300, 10), {"margin": 50.0, "keep": ["trunk"]})
print([round(x, 3) for x in out.length], round(km, 6))
'''


def test_built_only(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "city.toml").write_text(CITY)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(PROBE)], cwd=tmp_path, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "[350.0, 1000.0, 1000.0, 1000.0] 0.65"
