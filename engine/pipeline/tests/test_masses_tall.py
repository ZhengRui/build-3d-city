"""06e_masses' opt-in [ground] masses_tall: big footprints held at a height. Run: `uv run pytest tests`."""
import os
import subprocess
import sys
import textwrap

CITY = """
name = "massestall"
utm_epsg = 32654
[districts]
"Square" = 1
[paths]
data = "data"
"""

PROBE = '''
import geopandas as gpd
from shapely.geometry import box
from city3d.stages import masses
assert masses.MASSES_TALL == {}
b = gpd.GeoDataFrame({"h": [145.0, 145.0, 30.0]}, geometry=[box(0, 0, 100, 100), box(0, 0, 40, 40), box(0, 0, 100, 100)],
                     crs="EPSG:32654")
out, n, hmax = masses.hold_tall(b, {"area": 5000, "h": 45})
print(list(out.h), n, hmax)
'''


def test_masses_tall(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "city.toml").write_text(CITY)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(PROBE)], cwd=tmp_path, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "[45.0, 145.0, 30.0] 1 145.0"
