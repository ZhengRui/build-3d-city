"""Tokyo M7's backdrop opt-ins: [terrain] far_reach_sides (the reach per side), back_sea = "void" (with a bare-earth
backdrop the sea only where its first file has no data, so zero-metre lowlands stay land), curvature (the earth's drop
on the backdrop as y^2 / (y + D), with back_h the heights before it), cover_cell and snow (06e_masses: the outer cover
map's pixel and a snow cap from back_h), and [ground] masses_tall_within.tagged (the tall clip fetched with an
Overpass tag filter). All off by default, and then the code paths are the ones before the keys existed."""
from test_osm_tags import run

DEFAULTS = """
    import json
    from city3d.stages import terrain as T, masses as M
    print(json.dumps([T.FAR_SIDES, T.BACK_SEA, T.CURVATURE, T.FAR_REACH, M.COVER_CELL, M.SNOW, M.TALL_TAGGED]))"""


def test_defaults(tmp_path):
    sides, sea, curv, reach, cell, snow, tagged = run(tmp_path, DEFAULTS)
    assert sides == [reach] * 4 and sea == "level" and curv == {} and cell == 50.0 and snow == {} and tagged is False


def test_sides(tmp_path):
    toml = "[terrain]\nfar_reach_sides = [105000.0, 55000.0, 40000.0, 65000.0]\ncover_cell = 60.0"
    sides, _, _, reach, cell, _, _ = run(tmp_path, DEFAULTS, toml)
    assert sides == [105000.0, 55000.0, 40000.0, 65000.0] and reach == 36000.0 and cell == 60.0


SEA = """
    import json
    import numpy as np
    from city3d.stages import terrain as T
    # cells: the open sea (GLO-30's 0 in the bare file's void), a polder at -2.5 m (bare data), the coast at 0.1 m (bare
    # data), a tidal river at 0.05 m in the void, an inland lake 4 m up in the void, land at 12 m
    dsm = np.array([0.0, -2.5, 0.1, 0.05, 4.0, 12.0])
    zero = np.array([0.0, -2.5, 0.1, 0.05, 4.0, 12.0])
    void = np.array([True, False, False, True, True, False])
    print(json.dumps([T.back_sea_mask(dsm, zero, True).tolist(), T.back_sea_mask(dsm, zero, True, void).tolist(),
                      T.back_sea_mask(dsm, zero, False).tolist()]))"""


def test_back_sea_void(tmp_path):
    level, void, surface = run(tmp_path, SEA)
    assert level == [True, True, True, True, False, False]       # the polder and the coast's land went to the sea
    assert void == [True, False, False, True, False, False]       # only the void at sea level: the polder is land
    assert surface == [True, False, False, False, False, False]   # a surface model: the DEM about 0 only


CURVE = """
    import json
    import numpy as np
    from city3d.stages import terrain as T
    y = np.array([3776.0, 1500.0, 30.0, 0.0, -3.0, 50.0])
    x = np.array([-92000.0, -55000.0, -40000.0, -60000.0, -60000.0, 5000.0])
    z = np.array([35000.0, 20000.0, 0.0, 0.0, 0.0, 5000.0])
    c = T.curve(y, x, z)
    print(json.dumps([c.tolist(), T.uncurve(c, x, z).tolist(), float(T._drop(np.array([-92000.0]), np.array([35000.0]))[0])]))"""


def test_curvature(tmp_path):
    c, back, drop = run(tmp_path, CURVE, "[terrain]\ncurvature = { from = 12500.0, k = 0.13 }")
    # Fuji 98 km out: D = (98.4 km - 12.5 km)^2 / (2 x 6371 km / 0.87) ~ 504 m, y^2 / (y + D) ~ 3,330 m
    assert 480 < drop < 530 and 3300 < c[0] < 3360
    assert c[1] < 1500 and c[2] < 30 and c[2] > 0          # lower, never under the plain
    assert c[3] == 0.0 and c[4] == -3.0                     # the plain and the sea as they were
    assert c[5] == 50.0                                     # within `from`: unchanged
    assert all(abs(a - b) < 1e-6 * max(1, abs(b)) for a, b in zip(back, [3776.0, 1500.0, 30.0, 0.0, -3.0, 50.0]))


SNOW = """
    import json
    import numpy as np
    from city3d.stages import masses as M
    # a cone 3,800 m high, 20 km across, as a backdrop TIN (rings of vertices round the summit)
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    pts, h = [(0.0, 0.0)], [3800.0]
    for r in (2000.0, 5000.0, 10000.0):
        pts += [(r * np.cos(a), r * np.sin(a)) for a in ang]
        h += [3800.0 - 0.38 * r] * len(ang)
    pts = np.array(pts)
    import matplotlib.tri as mtri
    tri = mtri.Triangulation(pts[:, 0], pts[:, 1]).triangles
    class T:
        backdrop = {"back_xyz": np.c_[pts[:, 0], np.array(h) * 0.9, pts[:, 1]].astype(np.float32), "back_tri": tri,
                    "back_h": np.array(h, np.float32)}
    cell = 100.0
    out = np.full((3, 200, 200), 100.0, np.float32)            # x, z from -10 km, 100 m a pixel
    out = M.paint_snow(out, T, -10000.0, -10000.0, cell)
    print(json.dumps([float(out[0, 100, 100]), float(out[0, 100, 100 + 30]), float(out[0, 100, 100 + 60]),
                      float(out[0, 5, 5])]))"""


def test_snow(tmp_path):
    top, mid, foot, corner = run(tmp_path, SNOW, "[terrain]\nsnow = { from = 3000.0, full = 3400.0, rgb = [230, 232, 236] }")
    assert top > 220 and foot == 100.0 and corner == 100.0
    assert 100.0 <= mid <= 230.0                             # at 3 km from the top, 2,660 m: under the line
    off = run(tmp_path, "import json\nfrom city3d.stages import masses as M\nprint(json.dumps(M.SNOW))")
    assert off == {}


TALL = """
    import json
    from city3d.stages import masses as M
    print(json.dumps([M.TALL_TAGGED, M.tall_filter(60.0), M.tall_filter(30.0)]))"""


def test_tall_tagged(tmp_path):
    toml = ('[ground]\nmasses_within = "main.geojson"\n'
            'masses_tall_within = { file = "tall.geojson", min_h = 60.0, tagged = true }')
    tagged, f60, f30 = run(tmp_path, TALL, toml)
    assert tagged is True
    assert f60 == '(if: number(t["height"]) >= 60 || number(t["building:levels"]) >= 19)'   # (59 m / 3.2 m a storey)
    assert f30 == '(if: number(t["height"]) >= 30 || number(t["building:levels"]) >= 10)'
    off = run(tmp_path, TALL, '[ground]\nmasses_within = "main.geojson"\nmasses_tall_within = { file = "tall.geojson" }')
    assert off[0] is False
