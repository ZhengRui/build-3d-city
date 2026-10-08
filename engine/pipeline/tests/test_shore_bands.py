"""[shores] bands / water_side (05e_shores; Singapore M3: Sentosa's beach sand glowed 10-20 m into the water). Off, the
band table is BANDS untouched (and the shores index lists the same numbers); on, a type's bands are replaced or its
seaward side is fitted into a few metres with the shader's across coordinate (TEXCOORD_0) unchanged. The stage reads
its settings at import, so each case runs in a fresh interpreter on a throwaway city.toml. Run: `uv run pytest tests`.
"""
from pytest import approx
from test_osm_tags import run

BODY = """
import json
import numpy as np
from city3d.stages import shores
b = shores.resolve_bands(shores.BANDS, shores.SHORE_BANDS, shores.WATER_SIDE)
m = shores.Mesh()
xz = np.array([[0.0, 0.0], [10.0, 0.0]])
off = np.array([[0.0, 1.0], [0.0, 1.0]])
u = []
for a0, a1, ya, yb, sl, u0, u1 in b["beach"]:
    m.band(xz, off, np.array([0.0, 10.0]), a0, a1, ya, yb, sl, 2, 1, 0, shores.ABSOLUTE, u0, u1)
pos, uv = np.concatenate(m.pos), np.concatenate(m.uv)
print(json.dumps({"beach": b["beach"], "revetment": b["revetment"], "same": all(
    [tuple(r[:5]) for r in b[k]] == [tuple(r) for r in shores.BANDS[k]] for k in shores.BANDS),
    "uv": sorted(set(uv[:, 0].tolist())), "z": sorted(set(pos[:, 2].round(3).tolist()))}))
"""


def test_off_is_the_band_table(tmp_path):
    out = run(tmp_path, BODY)
    assert out["same"] is True
    assert [r[5:] for r in out["beach"]] == [[r[0], r[1]] for r in out["beach"]]     # u = a
    assert out["uv"] == [-16.0, 0.0, 14.0, 26.0]
    assert out["z"] == [-16.0, 0.0, 14.0, 26.0]


def test_water_side_fits_the_sea_side_and_keeps_the_across_coordinate(tmp_path):
    out = run(tmp_path, BODY, '[shores]\nwater_side = { beach = 4.0 }\n')
    beach = out["beach"]
    assert [x for r in beach for x in r[:2]] == approx([-16.0, 0.0, 0.0, 14 * 4 / 26, 14 * 4 / 26, 4.0])
    assert beach[0][5:] == [-16.0, 0.0] and beach[1][5:] == [0.0, 14.0] and beach[2][5:] == [14.0, 26.0]
    assert out["uv"] == [-16.0, 0.0, 14.0, 26.0]                                     # the shader sees the same across
    assert out["z"][-1] == 4.0 and out["z"][0] == -16.0                              # the sand ends 4 m out
    assert out["revetment"][2][1] == 13.0                                            # other types untouched


def test_bands_replace_a_type_with_named_heights(tmp_path):
    toml = '[shores]\nbands = { beach = [[-6.0, 0.0, "coast_top", "coast_top", 0], [0.0, 3.0, "coast_top", "sea", 5, 0.0, 14.0]] }\n'
    out = run(tmp_path, BODY, toml)
    assert out["beach"] == [[-6.0, 0.0, 0.75, 0.75, 0, -6.0, 0.0], [0.0, 3.0, 0.75, -1.0, 5, 0.0, 14.0]]
    assert out["z"] == [-6.0, 0.0, 3.0] and out["uv"] == [-6.0, 0.0, 14.0]


def test_islet_max_is_off_by_default(tmp_path):
    out = run(tmp_path, "import json\nfrom city3d.stages import shores\nprint(json.dumps([shores.ISLET_MAX, shores.ISLET_TYPE]))")
    assert out == [0.0, "revetment"]
    on = run(tmp_path, "import json\nfrom city3d.stages import shores\nprint(json.dumps([shores.ISLET_MAX, shores.ISLET_TYPE]))",
             '[shores]\nislet_max = 40.0\nislet_type = "mudflat"\n')
    assert on == [40.0, "mudflat"]
