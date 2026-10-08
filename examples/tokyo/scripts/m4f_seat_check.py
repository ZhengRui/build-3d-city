"""M4 fix round (b-tk-m4f): is every [[structures]] figure seated? For each figure in the included generated files
its lowest point (prisms' y0, boxes' bottoms, sections' first y, tubes' ends; over the ground at `at` plus `base`) is
compared with what stands under it: the terrain, or the top of the building table's pieces under its foot (06_tiles
stands a piece on the lowest ground under its outline). A figure whose foot is more than 1.5 m over everything under
it floats; one more than 3 m inside a piece is sunk (fine for a mast on a roof's parapet, not for a tower).
Run from demos/tokyo: `uv run python scripts/m4f_seat_check.py`."""
import sys
import tomllib
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point

from city3d.common import Terrain

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "tokyo"
T = Transformer.from_crs(4326, 32654, always_xy=True)
TR = Terrain()
gh = lambda e, n: float(TR.height_utm([e], [n])[0])
files = sys.argv[1:] or [HERE / "generated" / "structures-m4l.toml"]
bad = 0
ALL = [s for f in files for s in tomllib.loads(Path(f).read_text()).get("structures", [])]
FIG = [s for s in ALL if s["kind"] == "figure"]
for f in [None]:
    for s in FIG:
        e, n = T.transform(*s["at"])
        g = gh(e, n) + s.get("base", 0.0)
        ys = [p[1] for p in s.get("prisms", [])] + [b[1] - b[4] / 2 for b in s.get("boxes", [])] \
            + [x[0] for x in s.get("sections", [])[:1]] + [min(t[0][1], t[1][1]) for t in s.get("tubes", [])] \
            + [sl[1][0][1] if False else min(q[1] for q in sl[0]) for sl in s.get("slabs", [])]
        foot = g + min(ys)
        d = 40 / 111000
        b = gpd.read_file(DATA / "buildings.gpkg", bbox=(s["at"][0] - d / 0.81, s["at"][1] - d, s["at"][0] + d / 0.81, s["at"][1] + d)).to_crs(32654)
        b = b[b.geometry.intersects(Point(e, n).buffer(2.0))]
        ex = set(tomllib.loads((HERE / "city.toml").read_text())["buildings"]["exclude"]["gml_id"])
        b = b[~b.gml_id.isin(ex)]
        tops = []
        for geom, h in zip(b.geometry, b.h):
            gg = max(getattr(geom, "geoms", [geom]), key=lambda q: q.area)
            lo = min(gh(*q) for q in np.array(gg.exterior.coords))
            tops.append(lo + h)
        # (another figure under it: a plug, the body it stands on; its top within 2 m under this foot)
        for o in FIG:
            if o is s:
                continue
            oe, on_ = T.transform(*o["at"])
            if np.hypot(oe - e, on_ - n) < 30:
                ot = gh(oe, on_) + o.get("base", 0.0) + o["top"]
                if ot <= foot + 2.0:
                    tops.append(ot)
        under = max([gh(e, n)] + tops)
        what = "roof" if tops and max(tops) >= gh(e, n) + 1 else "ground"
        gap = foot - under
        flag = "FLOATS" if gap > 1.5 else ("sunk" if gap < -3 else "ok")
        bad += flag == "FLOATS"
        print(f"{flag:6s} {s['name'][:44]:44s} foot {foot:7.1f}  under ({what}) {under:7.1f}  gap {gap:+6.1f}")
print(f"{bad} floating")
