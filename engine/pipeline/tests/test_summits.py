"""[terrain] summits (Singapore M7): a named hill the canopy cut and smoothing flattened lifted back to its surveyed
height less the sea drop; the ground beyond the radius, levelled water and peaks already high enough untouched; off by
default."""
import tomllib
from pathlib import Path

from test_osm_tags import run

BODY = """
    import json
    import numpy as np
    from affine import Affine
    from pyproj import Transformer
    from city3d.stages import terrain as T
    e, n = Transformer.from_crs("EPSG:4326", 32648, always_xy=True).transform(103.85, 1.30)
    tr = Affine(10.0, 0, e - 1000.0, 0, -10.0, n + 1000.0)       # 201 x 201 cells, the hill in the middle
    jj, ii = np.mgrid[0:201, 0:201]
    r = np.hypot(ii - 100, jj - 100) * 10.0
    g = (5.0 + 35.0 * np.exp(-(r / 250.0) ** 2)).astype(np.float32)
    held = np.zeros(g.shape, bool)
    held[100, 150:153] = True                                      # a levelled pond on the slope
    g0 = g.copy()
    out = T.lift_summits(g, tr, 5.0, held)
    print(json.dumps({"out": [[a, round(b, 2), round(c, 2)] for a, b, c in out], "top": round(float(g.max()), 2),
                      "far": float(np.abs(g - g0)[r > 400].max()), "pond": float(np.abs(g - g0)[held].max()),
                      "rises": bool(((g - g0) >= -1e-4).all())}))"""

TOML = """
[terrain]
summits = { radius = 400.0 }
[terrain.peaks]
"Hill" = [103.85, 1.30, 60]
"Low" = [103.85, 1.30, 30]
"Unsurveyed" = [103.85, 1.30]
"""


def test_summit_lifted(tmp_path):
    o = run(tmp_path, BODY, TOML)
    (n1, a1, b1), (n2, a2, b2) = o["out"]
    assert n1 == "Hill" and a1 == 40.0 and abs(b1 - 55.0) < 0.01          # 60 m less the 5 m drop
    assert n2 == "Low" and b2 == a2                                       # (after Hill: already over 25 m)
    assert abs(o["top"] - 55.0) < 0.01
    assert o["far"] == 0.0 and o["pond"] == 0.0 and o["rises"]


def test_summits_off_by_default():
    d = tomllib.loads((Path(__file__).resolve().parents[1] / "src" / "city3d" / "defaults.toml").read_text())
    assert not d["terrain"].get("summits")
