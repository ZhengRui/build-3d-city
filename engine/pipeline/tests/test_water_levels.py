"""05a_terrain's opt-in [terrain] water_levels: the water body holding a point is held at the given level, whatever
the ground under it reads (Tokyo's tidal Sumida, read 0.5-2.5 m by the 5 m DEM); off, inland_water is unchanged.
A synthetic grid: a river (a band of ground at 1-2 m) through land at 4 m, and a pond. Run: `uv run pytest tests`.
"""
import os
import subprocess
import sys
import textwrap

import numpy as np

CITY = """
name = "waterlevels"
utm_epsg = 32654
coast = true
[districts]
"Square" = 1
[paths]
data = "data"
[terrain]
water_flat = 0.0
water_ramp = 5.0
water_all_touched = false
EXTRA
"""

PROBE = '''
import numpy as np
from affine import Affine
from pyproj import Transformer
from shapely.geometry import box
from city3d.stages import terrain
from city3d.common import UTM
x0, y0 = 380000.0, 3950000.0                       # UTM 54N, near Tokyo
tr = Affine(10.0, 0, x0, 0, -10.0, y0 + 2000)      # 200 x 200 cells at 10 m
g = np.full((200, 200), 4.0, np.float32)
rng = np.random.default_rng(3)
g[90:110, :] = 1.0 + rng.random((20, 200)).astype(np.float32)      # the river's cells read 1-2 m
g[20:40, 20:40] = 2.5                                               # a pond
river = box(x0, y0 + 2000 - 1100, x0 + 2000, y0 + 2000 - 900)
pond = box(x0 + 200, y0 + 2000 - 400, x0 + 400, y0 + 2000 - 200)
lon, lat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(x0 + 1000, y0 + 1000)
print(f"{lon:.7f} {lat:.7f}")
held, n_flat, n_slope = terrain.inland_water(g, tr, [river, pond])
np.savez(OUT, g=g, levels=np.array([l if l is not None else np.nan for _, l, _, _ in terrain.WATER_LEVELS]))
'''


def _probe(tmp_path, extra):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "city.toml").write_text(CITY.replace("EXTRA", extra))
    out = tmp_path / f"probe{len(list(tmp_path.glob('probe*')))}.npz"
    code = "OUT = %r\n" % str(out) + textwrap.dedent(PROBE)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return dict(np.load(out)), r.stdout.split("\n")[0]


def test_water_levels(tmp_path):
    base, ll = _probe(tmp_path, "")
    lon, lat = ll.split()
    d, _ = _probe(tmp_path, f'water_levels = {{ "river" = [{lon}, {lat}, 0.0] }}')
    # off: the river at its ground's median (~1.5), the pond at 2.5
    assert 1.3 < base["levels"][0] < 1.7 and abs(base["levels"][1] - 2.5) < 1e-6
    # on: the river held at 0 over all its cells, the pond and the land beyond the banks unchanged
    assert d["levels"][0] == 0.0 and abs(d["levels"][1] - 2.5) < 1e-6
    assert np.abs(d["g"][91:109, 5:195]).max() < 1e-6
    np.testing.assert_array_equal(d["g"][:60], base["g"][:60])
    np.testing.assert_array_equal(d["g"][140:], base["g"][140:])
