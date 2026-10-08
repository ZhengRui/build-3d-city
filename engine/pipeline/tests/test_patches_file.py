"""[terrain] patches_file (opt-in): the polygons of a GeoJSON file re-filled from their outlines like inline
`patches`; off (the default) the ground is untouched. A synthetic 10 m grid on a slope with a 12 m deep pit, in
Hong Kong's UTM zone. Run: `uv run pytest tests`.
"""
import json
import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest

CITY = """
name = "patchtest"
utm_epsg = 32650
coast = true
[districts]
"Square" = 1
[paths]
data = "data"
[terrain]
EXTRA
"""

PROBE = """
import json
import numpy as np
from affine import Affine
from pyproj import Transformer
from city3d.stages import terrain as T
to = Transformer.from_crs("EPSG:4326", T.UTM, always_xy=True)
e0, n0 = to.transform(114.20, 22.30)
tr = Affine(10.0, 0, e0, 0, -10.0, n0)
j, i = np.mgrid[0:60, 0:60]
g = (5 + 0.5 * i).astype(np.float32)          # a slope, 0.5 m a cell eastward
g[25:35, 25:35] -= 12.0                       # the pit
before = g.copy()
T.patches(g, tr)
np.savez(OUT, g=g, before=before)
print(json.dumps(T.LOG))
"""


def _run(tmp_path, extra):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "city.toml").write_text(CITY.replace("EXTRA", extra))
    out = tmp_path / f"probe{len(list(tmp_path.glob('probe*')))}.npz"
    code = "OUT = %r\n" % str(out) + textwrap.dedent(PROBE)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True)
    return r, (dict(np.load(out)) if out.exists() else None)


def _pit_geojson(tmp_path, kind="FeatureCollection"):
    """The pit's outline (cells 24-36, a cell beyond it) in WGS84, written as a GeoJSON file."""
    from pyproj import Transformer
    to = Transformer.from_crs("EPSG:4326", "EPSG:32650", always_xy=True)
    back = Transformer.from_crs("EPSG:32650", "EPSG:4326", always_xy=True)
    e0, n0 = to.transform(114.20, 22.30)
    x0, x1 = e0 + 10 * 24.5, e0 + 10 * 35.5
    y0, y1 = n0 - 10 * 35.5, n0 - 10 * 24.5
    ring = [list(back.transform(x, y)) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]
    geom = {"type": "MultiPolygon", "coordinates": [[ring]]}
    data = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": geom}]}
    if kind == "geometry":
        data = geom
    (tmp_path / "data" / "pits.geojson").parent.mkdir(exist_ok=True)
    (tmp_path / "data" / "pits.geojson").write_text(json.dumps(data))


def test_off_by_default(tmp_path):
    r, d = _run(tmp_path, "")
    assert r.returncode == 0, r.stdout + r.stderr
    assert np.array_equal(d["g"], d["before"])


@pytest.mark.parametrize("kind", ["FeatureCollection", "geometry"])
def test_pit_filled(tmp_path, kind):
    (tmp_path / "data").mkdir(exist_ok=True)
    _pit_geojson(tmp_path, kind)
    r, d = _run(tmp_path, 'patches_file = "data/pits.geojson"')
    assert r.returncode == 0, r.stdout + r.stderr
    g, before = d["g"], d["before"]
    slope = (5 + 0.5 * np.mgrid[0:60, 0:60][1]).astype(np.float32)
    # the pit is back on the slope (linear from its outline), nothing outside it moved
    assert np.abs(g[26:34, 26:34] - slope[26:34, 26:34]).max() < 0.6
    out = np.ones_like(g, bool)
    out[24:36, 24:36] = False
    assert np.array_equal(g[out], before[out])
    assert "patches_file: 1 of 1 polygons" in r.stdout


def test_missing_file(tmp_path):
    r, _ = _run(tmp_path, 'patches_file = "data/none.geojson"')
    assert r.returncode != 0 and "patches_file" in r.stderr
