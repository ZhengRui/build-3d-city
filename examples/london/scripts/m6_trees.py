"""London M6: the London Public Realm Trees inventory (GLA, OGL v3; raw/dl/Borough_tree_list_2025Nov.csv, 1.136 M
trees of the 33 boroughs, the Royal Parks and TfL) as a census source 08_trees reads ([trees.street.census]).

The file's sizes are text ("6 m", "10 to 15 m", "<5 m", "20+ m", "Not recorded"); 08_trees wants numbers, so this
writes trees_census.csv in the data folder (not raw/: raw is the main tree's, read-only) with lon, lat, genus,
height (m, 0 = unknown: 08_trees then takes the genus group's median), clipped to the boundary's box plus 1 km:
- ranges take their middle ("10 to 15 m" 12.5), "<5 m" 3.5, "20+ m" 22;
- stumps, vacant pits and dead trees are dropped;
- trees listed twice (a borough's and TfL's records of one pit, the Royal Parks' and a borough's along a park edge)
  are dropped within DUP m of an earlier one.

Run from demos/london:  uv run python scripts/m6_trees.py   (~1 min, ~1.5 GB)
"""
import re

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from city3d.common import DATA, UTM, boundary

DUP = 1.0          # m
SRC = DATA / "raw/dl/Borough_tree_list_2025Nov.csv"
OUT = DATA / "trees_census.csv"


def metres(s: str) -> float:
    s = str(s).strip().lower()
    nums = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return 0.0
    if "to" in s and len(nums) >= 2:
        return (nums[0] + nums[1]) / 2
    if s.startswith("<"):
        return nums[0] * 0.7
    if "+" in s:
        return nums[0] * 1.1
    return nums[0]


def main():
    df = pd.read_csv(SRC, encoding="utf-8-sig", low_memory=False)
    n0 = len(df)
    b = boundary().to_crs(4326).total_bounds
    m = 0.015      # ~1 km
    df = df[(df.lon > b[0] - m) & (df.lon < b[2] + m) & (df.lat > b[1] - m) & (df.lat < b[3] + m)]
    n1 = len(df)
    text = (df.common_name.fillna("") + " " + df.taxon_species.fillna("") + " " + df.girth_dbh.fillna("")).str.lower()
    gone = text.str.contains(r"stump|vacant|dead|empty pit|no tree|planting site")
    df = df[~gone]
    h = df.height_m.map(metres).to_numpy().copy()
    h[(h > 45) | (h < 1)] = 0.0       # a 112 m plane; "0 m"
    import geopandas as gpd
    p = gpd.GeoSeries(gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(UTM)
    xy = np.column_stack([p.x, p.y])
    # within-file duplicates: keep the first of each pair closer than DUP m
    pairs = cKDTree(xy).query_pairs(DUP, output_type="ndarray")
    drop = np.zeros(len(df), bool)
    for i, j in pairs[np.argsort(pairs[:, 0])]:
        if not drop[i]:
            drop[j] = True
    out = pd.DataFrame({"lon": df.lon.round(7), "lat": df.lat.round(7),
                        "genus": df.taxon_genus.fillna("").astype(str), "height": np.round(h, 1),
                        "maintainer": df.maintainer.fillna(""), "location": df.location.fillna("")})[~drop]
    out.to_csv(OUT, index=False)
    print(f"{n0:,} trees in the file, {n1:,} round the boundary, {int(gone.sum()):,} stumps/vacant dropped, "
          f"{int(drop.sum()):,} duplicates within {DUP} m dropped -> {len(out):,} in {OUT.name}; "
          f"height known {(out.height > 0).mean():.0%}, median {out.height[out.height > 0].median():.1f} m")
    print(out.genus.value_counts().head(20).to_dict())
    pl = out[out.genus == "Platanus"].height
    print(f"plane median {pl[pl > 0].median():.1f} m")


if __name__ == "__main__":
    main()
