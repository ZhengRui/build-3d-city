"""Berlin M6: the Baumkataster (Land Berlin, Baumbestand Berlin, gdi.berlin.de, dl-de/zero-2.0) as census sources
08_trees reads ([trees.street.census] sources): the street trees (Straßenbäume) and the park trees (Anlagenbäume)
of raw/trees/*_bbox.geojson (EPSG:25833 points, the boundary's box + 4 km; raw/trees/README.txt).

Writes trees_street.csv and trees_park.csv in the data folder (not raw/: raw is the main tree's, read-only) with
lon, lat, genus (botanical: Tilia, Acer, ...), height (m, 0 = unknown: 08_trees takes the group's median), crown
(crown diameter m, 0 = unknown), clipped to the boundary's box + 1 km:
- rows without a position or genus and without a height are kept (genus "" falls in the last group);
- heights over 45 m or under 1 m are unknown (class values; a few typing errors);
- trees listed twice (one pit in both layers, or twice in one layer) within DUP m of an earlier one are dropped:
  the street layer first.
The engine uses no OSM natural=tree nodes, so there is nothing to deduplicate against OSM.

Run from demos/berlin:  uv run python scripts/m6_trees.py   (~1 min, ~1.5 GB)
"""
import json

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from city3d.common import DATA, boundary

DUP = 1.0          # m
SRC = {"street": DATA / "raw/trees/strassenbaeume_bbox.geojson", "park": DATA / "raw/trees/anlagenbaeume_bbox.geojson"}


def read(path):
    d = json.loads(path.read_text())
    rows = []
    for f in d["features"]:
        g = f.get("geometry")
        if not g:
            continue
        p = f["properties"]
        x, y = g["coordinates"][:2]
        rows.append((x, y, p.get("gattung") or "", float(p.get("baumhoehe") or 0), float(p.get("kronedurch") or 0)))
    return pd.DataFrame(rows, columns=["x", "y", "genus", "height", "crown"])


def main():
    import geopandas as gpd
    b = boundary().to_crs(25833).total_bounds
    m = 1000
    out, seen = {}, None
    for name, path in SRC.items():
        df = read(path)
        n0 = len(df)
        df = df[(df.x > b[0] - m) & (df.x < b[2] + m) & (df.y > b[1] - m) & (df.y < b[3] + m)].reset_index(drop=True)
        df.loc[(df.height > 45) | (df.height < 1), "height"] = 0.0
        df.loc[(df.crown > 40) | (df.crown < 0.5), "crown"] = 0.0
        xy = df[["x", "y"]].to_numpy()
        drop = np.zeros(len(df), bool)
        pairs = cKDTree(xy).query_pairs(DUP, output_type="ndarray")
        for i, j in pairs[np.argsort(pairs[:, 0])]:
            if not drop[i]:
                drop[j] = True
        n_self = int(drop.sum())
        if seen is not None:
            d, _ = cKDTree(seen).query(xy, distance_upper_bound=DUP)
            drop |= np.isfinite(d)
        df = df[~drop]
        seen = df[["x", "y"]].to_numpy() if seen is None else np.vstack([seen, df[["x", "y"]].to_numpy()])
        ll = gpd.GeoSeries(gpd.points_from_xy(df.x, df.y), crs=25833).to_crs(4326)
        o = pd.DataFrame({"lon": ll.x.round(7).to_numpy(), "lat": ll.y.round(7).to_numpy(), "genus": df.genus.to_numpy(),
                          "height": df.height.round(1).to_numpy(), "crown": df.crown.round(1).to_numpy()})
        f = DATA / f"trees_{name}.csv"
        o.to_csv(f, index=False)
        out[name] = o
        print(f"{name}: {n0:,} in the file, {len(xy):,} round the boundary, {n_self:,} doubles within the layer and "
              f"{int(drop.sum()) - n_self:,} of the street layer's dropped -> {len(o):,} in {f.name}; height known "
              f"{(o.height > 0).mean():.0%} (median {o.height[o.height > 0].median():.1f} m), crown known "
              f"{(o.crown > 0).mean():.0%} (median {o.crown[o.crown > 0].median():.1f} m)")
        print("  ", o.genus.value_counts().head(14).to_dict())


# Unter den Linden's four rows of limes (two on the Mittelpromenade, one on each outer walk): the Baumkataster and OSM
# leave ~200 m of them out between Friedrichstraße and Charlottenstraße (the U5 site, replanted) and the promenade's
# second row west of Friedrichstraße (Berlin M6 critic: the Mittelpromenade empty grey slabs). Invented rows along
# both carriageways (OSM's two one-way ways): ROW_IN m inside each kerb toward the other carriageway, ROW_OUT m
# outside it, every ROW_STEP m, where no listed tree stands within ROW_NEAR m, off every other carriageway and
# footprint; written to trees_extra.csv (a third census source, dedupe 1 m)
ROWS = ["Unter den Linden"]
ROW_IN, ROW_OUT, ROW_STEP, ROW_NEAR = 2.0, 2.5, 9.0, 5.0


def rows(listed):
    import geopandas as gpd
    import shapely
    from city3d.common import UTM
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ways = ways[ways.kind.isin(["major", "minor", "service"]) & ~ways.elevated]
    carr = shapely.union_all(ways.geometry.buffer(ways.width / 2 + 0.6, cap_style="flat").values)
    out = []
    for name in ROWS:
        w = ways[(ways.name == name) & (ways.kind == "major")]
        bb = tuple(w.total_bounds + np.array([-30, -30, 30, 30]))
        blds = gpd.read_file(DATA / "buildings.gpkg", bbox=bb).to_crs(UTM).geometry.buffer(2.0).union_all()
        for i, (g, half) in enumerate(zip(w.geometry, w.width / 2)):
            others = shapely.union_all([o for j, o in enumerate(w.geometry) if j != i and g.distance(o) > 8])
            if others.is_empty:
                continue
            for d in np.arange(ROW_STEP / 2, g.length, ROW_STEP):
                p = g.interpolate(d)
                q = shapely.ops.nearest_points(p, others)[1]
                dist = p.distance(q)
                if not 14 < dist < 50:
                    continue
                ux, uy = (q.x - p.x) / dist, (q.y - p.y) / dist
                for k in (half + ROW_IN, -(half + ROW_OUT)):
                    out.append((p.x + ux * k, p.y + uy * k))
    xy = np.array(out)
    pts = shapely.points(xy)
    ok = ~shapely.contains(carr, pts) & ~shapely.contains(blds, pts)
    print(len(xy), "candidates;", int(shapely.contains(carr, pts).sum()), "on carriageways;", int(shapely.contains(blds, pts).sum()), "by footprints")
    d, _ = cKDTree(listed).query(xy, distance_upper_bound=ROW_NEAR)
    ok &= ~np.isfinite(d)
    xy = xy[ok]
    # (the two carriageways' inner rows of one promenade can meet: one tree where two stand within 4 m)
    drop = np.zeros(len(xy), bool)
    for i, j in cKDTree(xy).query_pairs(4.0):
        drop[j] = True
    xy = xy[~drop]
    ll = gpd.GeoSeries(gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=UTM).to_crs(4326)
    o = pd.DataFrame({"lon": ll.x.round(7), "lat": ll.y.round(7), "genus": "Tilia", "height": 15.0, "crown": 9.0})
    o.to_csv(DATA / "trees_extra.csv", index=False)
    print(f"rows: {len(o):,} invented limes along {', '.join(ROWS)} -> trees_extra.csv")


if __name__ == "__main__":
    import sys
    if "--rows" in sys.argv:
        import geopandas as gpd
        from city3d.common import UTM
        ls = pd.concat([pd.read_csv(DATA / f"trees_{n}.csv") for n in ("street", "park")])
        p = gpd.GeoSeries(gpd.points_from_xy(ls.lon, ls.lat), crs=4326).to_crs(UTM)
        rows(np.column_stack([p.x, p.y]))
    else:
        main()
