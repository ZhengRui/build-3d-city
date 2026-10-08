"""06e_masses' opt-in [terrain] cover_roofs and cover_inner_cell. Run: `uv run pytest tests`."""
import os
import subprocess
import sys
import textwrap

CITY = """
name = "coverroofs"
utm_epsg = 32654
[districts]
"Square" = 1
[paths]
data = "data"
"""

DEFAULTS = '''
from city3d.stages import masses
assert masses.COVER_ROOFS == {} and masses.COVER_INNER == 20.0
print("ok")
'''

PROBE = '''
import numpy as np
from shapely.geometry import box
from city3d.stages import masses
assert masses.COVER_INNER == 10.0
g = [box(400000 + i * 37.3, 3950000 + i * 11.1, 400010 + i * 37.3, 3950010 + i * 11.1) for i in range(200)]
a, b = masses.roof_index(g, 3), masses.roof_index(g[::-1], 3)
assert a.min() >= 1 and a.max() <= 3 and len(set(a.tolist())) == 3      # all colours used
assert (a == b[::-1]).all()                                             # by the footprint, not its order
out = np.full((3, 1, 2), 100.0, np.float32)
fr = np.array([[[0.5, 0.0]], [[0.25, 0.0]]], np.float32)
o = masses.paint_roofs(out, fr, [[200, 200, 200], [0, 0, 0]])
print(o[:, 0, 0].round(3).tolist(), o[:, 0, 1].tolist())
'''


def run(tmp_path, toml, probe):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "city.toml").write_text(toml)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(probe)], cwd=tmp_path, env=env, capture_output=True,
                          text=True)


def test_cover_roofs_off_by_default(tmp_path):
    r = run(tmp_path, CITY, DEFAULTS)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cover_roofs(tmp_path):
    toml = CITY + '[terrain]\ncover_inner_cell = 10.0\ncover_roofs = { rgb = [[200, 200, 200], [0, 0, 0]], gaps = [90, 90, 90] }\n'
    r = run(tmp_path, toml, PROBE)
    assert r.returncode == 0, r.stdout + r.stderr
    # 25 % of the base left, half of it a pale roof, a quarter a black one; the bare pixel untouched
    assert r.stdout.strip() == "[125.0, 125.0, 125.0] [100.0, 100.0, 100.0]"
