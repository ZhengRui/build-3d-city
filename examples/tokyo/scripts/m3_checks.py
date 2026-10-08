"""M3 checks: the ground under the buildings and the roads through them -> checks/m3_ground.md.

1. PLATEAU's ground_elevation (T.P., the survey's ground at each building) against the scene's ground: the terrain's
   base under the outline (06_tiles stands each piece on the lowest ground under it) and its height at the centre.
   The scene is T.P. less ~1 m ([terrain] sea_drop 0.5 + sea_knee 0.5) and smoothed over built-up ground, so the
   difference shows where buildings stand in pits or on lumps (Nishi-Shinjuku's sunken streets: M2's Known issue).
2. Ground-level road length inside building footprints, by kind (05b_roads' ways, not on bridges): "roads don't run
   through buildings".
3. Elevated ways: deck heights by name for the Shuto's junctions and the bay's bridges.

uv run python scripts/m3_checks.py   (from demos/tokyo, after 06_tiles; ~1 GB)
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from city3d import common

CITY = Path(__file__).resolve().parents[1]
DATA = CITY.parents[0] / "data/tokyo"
NISHI = (139.688, 35.684, 139.700, 35.696)
OUT = []


def p(s=""):
    print(s, flush=True)
    OUT.append(s)


def main():
    T = common.Terrain()
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(common.UTM_EPSG)
    b = b[b["source"].str.lower().str.contains("plateau") & b["ground_elevation"].notna()]
    base = T.bases(b.geometry.values)
    c = b.geometry.representative_point()
    mid = T.height_utm(c.x.values, c.y.values)
    tp = b["ground_elevation"].to_numpy(float)
    ll = gpd.GeoSeries(c, crs=b.crs).to_crs(4326)
    nishi = (ll.x > NISHI[0]) & (ll.x < NISHI[2]) & (ll.y > NISHI[1]) & (ll.y < NISHI[3])
    p("# M3 checks: ground under the buildings, roads through them\n")
    p("## 1. PLATEAU ground_elevation (T.P.) vs the scene's ground\n")
    p("Scene ground = T.P. − ~1 m by design (sea_drop 0.5, sea_knee 0.5). d = scene − (T.P. − 1).\n")
    p("| Where | pieces | base: median d | p5 | p95 | |d| > 3 m | centre: median d |")
    p("|---|---|---|---|---|---|---|")
    for name, m in (("all", np.ones(len(b), bool)), ("Nishi-Shinjuku", nishi.to_numpy())):
        db = base[m] - (tp[m] - 1.0)
        dm = mid[m] - (tp[m] - 1.0)
        p(f"| {name} | {m.sum():,} | {np.median(db):+.2f} | {np.percentile(db, 5):+.2f} | "
          f"{np.percentile(db, 95):+.2f} | {(np.abs(db) > 3).sum():,} | {np.median(dm):+.2f} |")
    db = base - (tp - 1.0)
    p(f"\nPieces whose base lies under the scene's 0 (by a quay wall's dropped water cells): {(base < -1).sum():,} "
      f"under -1 m, {(base < -3).sum():,} under -3 m\n")
    worst = np.argsort(db)[:8]
    p("\nLowest bases against the survey (sunk furthest):\n")
    p("| name | lat, lon | T.P. | scene base | d |\n|---|---|---|---|---|")
    for i in worst:
        p(f"| {b['name'].iloc[i] or ''} | {ll.y.iloc[i]:.5f}, {ll.x.iloc[i]:.5f} | {tp[i]:.1f} | {base[i]:.1f} | "
          f"{db[i]:+.1f} |")
    worst = np.argsort(-db)[:5]
    p("\nHighest bases against the survey (standing on a lump):\n")
    p("| name | lat, lon | T.P. | scene base | d |\n|---|---|---|---|---|")
    for i in worst:
        p(f"| {b['name'].iloc[i] or ''} | {ll.y.iloc[i]:.5f}, {ll.x.iloc[i]:.5f} | {tp[i]:.1f} | {base[i]:.1f} | "
          f"{db[i]:+.1f} |")

    p("\n## 2. Ground-level roads inside building footprints\n")
    r = gpd.read_file(DATA / "roads.gpkg", layer="ways").to_crs(b.crs)
    allb = gpd.read_file(DATA / "buildings.gpkg").to_crs(b.crs)
    fp = gpd.GeoDataFrame(geometry=allb.geometry.buffer(-0.5), crs=b.crs)
    elevated = r["elevated"].fillna(False).astype(bool)
    p(f"columns: {', '.join(c for c in r.columns if c != 'geometry')}\n")
    p("| kind | ground ways km | inside footprints m |\n|---|---|---|")
    ground = r[~elevated]
    pairs = gpd.sjoin(ground[["kind", "geometry"]], fp, predicate="intersects")
    seg = pd.Series(shapely.length(shapely.intersection(pairs.geometry.values,
                                                         fp.geometry.loc[pairs["index_right"]].values)), index=pairs.index)
    by = seg.groupby(pairs["kind"]).sum()
    for k, g in ground.groupby("kind"):
        inside = float(by.get(k, 0.0))
        p(f"| {k} | {g.length.sum() / 1000:,.1f} | {inside:,.0f} |")
    p(f"\nelevated ways: {int(elevated.sum()):,}, {r[elevated].length.sum() / 1000:,.1f} km")
    (CITY / "checks/m3_ground.md").write_text("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
