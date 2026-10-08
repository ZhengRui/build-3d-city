"""The citygml adapter's opt-in roof_split (sources/citygml.py roof_levels, split_rows): a LoD2 solid whose roof
stands at several levels becomes a row per level. Synthetic roofs in metres (no file, no CRS):
  T: a 60 x 60 podium roof at 20 m round a 20 x 20 tower roof at 100 m with a 4 x 4 plant room at 104 m on it
  G: a gabled house roof (eaves 6, ridge 9) over 20 x 20: one level within tol, not split
  S: a 15 x 15 footprint (225 m², under min_area): not split
Run: `uv run pytest tests`.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
from shapely.geometry import box

if not os.environ.get("CITY3D_CITY"):      # the adapter module reads a city.toml on import: a minimal one
    _d = Path(tempfile.mkdtemp())
    (_d / "city.toml").write_text('name = "rooftest"\nutm_epsg = 32654\n[districts]\n"Core" = 1\n')
    os.environ["CITY3D_CITY"] = str(_d / "city.toml")

from city3d.sources.citygml import SPLIT_DEFAULTS, roof_levels, split_rows    # noqa: E402


def rect(x0, y0, x1, y1, z0, z1=None):
    """A roof polygon ring (closed, with z); z1: the far side's z (a slope along y)."""
    z1 = z0 if z1 is None else z1
    return (np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z1], [x0, y1, z1], [x0, y0, z0]], dtype=float), [])


def podium_tower():
    roof = [rect(0, 0, 60, 20, 20), rect(0, 40, 60, 60, 20), rect(0, 20, 20, 40, 20), rect(40, 20, 60, 40, 20),
            rect(20, 20, 40, 40, 100.5), rect(28, 28, 32, 32, 104)]
    # the tower roof minus the plant room is drawn as one polygon with a hole in real data; here it overlaps the
    # plant room seen from above, which the split must handle (the higher level wins)
    return roof, box(0, 0, 60, 60)


def test_tower_on_podium():
    C = dict(SPLIT_DEFAULTS)
    roof, fp = podium_tower()
    lv = roof_levels(roof, fp, 0.0, C)
    assert lv is not None and len(lv) == 2                   # the plant room (16 m² < min_part) joins the tower
    (g0, top0, *_), (g1, top1, *_) = lv
    assert top0 == 104.0 and abs(g0.area - 400) < 1          # the tower, to its plant room's top
    assert top1 == 20.0 and abs(g1.area - 3200) < 1          # the podium ring
    assert abs(g0.union(g1).area - fp.area) < 1 and g0.intersection(g1).area < 1

    rows = split_rows([{"gml_id": "bldg_T", "parent_id": "", "part": False, "geometry": fp, "ground_z": 0.0,
                        "measuredHeight": 104.0, "roof_top_z": 104.0, "eave_z": 20.0, "_roof": roof}], C)
    assert [r["gml_id"] for r in rows] == ["bldg_T#r0", "bldg_T#r1"]
    assert all(r["parent_id"] == "bldg_T" and r["part"] and r["roof_levels"] == 2 for r in rows)
    assert rows[1]["roof_top_z"] == 20.0 and rows[1]["measuredHeight"] == 104.0 and "_roof" not in rows[1]


def test_bigger_plant_room_is_its_own_level():
    C = {**SPLIT_DEFAULTS, "min_part": 10.0, "rel_tol": 0.0}     # (8 % of 104 m would join 100.5 to 104)
    roof, fp = podium_tower()
    lv = roof_levels(roof, fp, 0.0, C)
    assert [round(t, 1) for _, t, *_ in lv] == [104.0, 100.5, 20.0]
    assert abs(sum(g.area for g, *_ in lv) - 3600) < 1


def test_not_split():
    C = dict(SPLIT_DEFAULTS)
    gable = [rect(0, 0, 20, 10, 6, 9), rect(0, 10, 20, 20, 9, 6)]
    assert roof_levels(gable, box(0, 0, 20, 20), 0.0, C) is None              # one level (within tol)
    small = [rect(0, 0, 15, 7, 10), rect(0, 7, 15, 15, 30)]
    assert roof_levels(small, box(0, 0, 15, 15), 0.0, C) is None              # under min_area
    roof, fp = podium_tower()
    assert roof_levels(roof[4:], fp, 0.0, C) is None                          # roofs cover too little of fp
    rows = split_rows([{"gml_id": "g", "geometry": box(0, 0, 20, 20), "ground_z": 0.0, "_roof": gable}], C)
    assert len(rows) == 1 and "_roof" not in rows[0] and "roof_level" not in rows[0]
