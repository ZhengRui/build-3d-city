"""Hong Kong M2: LandsD's Building rows with the ground under each, for heights from the street.

LandsD gives every block (tower, podium, temporary structure) a BaseHeight and a TopHeight in mPD. BaseHeight is
the block's own base: a tower on a podium has its base on the podium's roof (Times Square Tower One 75.6 mPD, Two
IFC 29.7), so TopHeight - BaseHeight is its height above the podium, and extruded from the ground the tower would
lose the podium (Times Square 123 m for 194). Here each row gets the ground under it from the CEDD 2020 LiDAR DTM
(2 m, scripts/m1_dem_prep.py; MSL, so + 1.30 m back to mPD to compare like with like), sampled every 2 m along its
outline: the LOWEST ground under the outline is the bottom the viewer extrudes from (06_tiles' Terrain.bases takes
the lowest ground under the outline too), so a tower on a hillside reaches its surveyed TopHeight from the foot of
its downhill wall. city.toml's height is then `top_mpd - ground_mpd`: every row from the ground, a tower drawn
through its podium (04_buildings' dedupe_keep_taller keeps it, volume_dedupe cuts it out of the podium).

Rows that stand on nothing (BaseHeight over the highest ground under them by 3 m or more, and under half of
their footprint over another row reaching up to their base): those no more than 10 m tall over their base are
enclosed footbridges, link bridges and decks over roads and slopes: raised pieces from their base (min_h =
BaseHeight - lowest ground; `elevated`), never walls from the ground. Taller ones are towers on a podium or deck the
layer does not hold (ICC and The Cullinan on Union Square's deck, estate towers on their car-park podiums;
`deck_tower`): drawn from the ground.

Pits: rows whose lowest LiDAR ground is under 1 mPD stand over an excavation of 2020 (a site built since: Kai Tak,
West Kowloon; or a pier's sea): their ground is the street around them (`pit`, `ground_lidar_mpd` keeps the
LiDAR's); M3's terrain should fill these pits to the same level.

Sunk: rows whose TopHeight is at most 0.5 m over their lowest ground (MTR Mei Foo station's box under the
park, tanks, blocks cut into slopes: ~119 in the boundary, 0.6 ha) are flagged `m2_drop = "sunk"` and left out.

Temporary structures without a TopHeight (3,021 in the boundary: market sheds, site offices, toilets; median
35 m²) are one storey: top = ground + 3.0 m (LandsD's temporary structures with a height: median 3.1 m).

Run from demos/hongkong (loads the 2 m LiDAR mosaic, 0.35 GB, and 90k footprints: under the pipeline lock):
    uv run python scripts/m2_landsd_prep.py
Writes ../data/hongkong/landsd_prepared/landsd_E600_ground.gpkg (EPSG:2326; the file adapter's path).
"""
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely

from city3d.common import CITY, DATA, RAW

T0 = time.time()
PD_TO_MSL = 1.30
SRC = RAW / "landsd_building/landsd_building_E600_2326.geojson"
OUT = DATA / "landsd_prepared/landsd_E600_ground.gpkg"
LIDAR = DATA / "dem_prepared/lidar2020_dtm_2m_msl.tif"
DTM5 = DATA / "dem_prepared/dtm5m_msl.tif"
TEMP_H = 3.0          # a temporary structure without a TopHeight: one storey
LIFT = 3.0            # m: a base this far over the highest ground under the row is off the ground
SUPPORT = 0.5         # share of the footprint over other rows reaching up to its base: it stands on them
PIT = 1.0             # mPD: a row whose lowest ground is under this stands over a pit in the 2020 LiDAR (a site dug
                      # since; Kai Tak's Monaco and The Henley, Grand Victoria, NCB Innovation Centre: down to -13 mPD)
NEAR = 150.0          # m: its ground is then the street around it: the median ground of the level rows this near
SUNK = 0.5            # m: a row topping out this little over its lowest ground stands under it (dropped)
MIN_STOREY = 2.2      # m a storey: below it LandsD's TopHeight can't be the block's (storeys_fix)
OFFICE = r"cent(re|er)|plaza|place|industrial|trade|office|factory|square|commercial|godown|tower\b"
HIGH = 40.0           # m: an unsupported row whose base is this far over the highest ground under it, and narrow (under
WIDE = (300.0, 8.0)   # 300 m² or 8 m wide), is a sky bridge between towers (Chatham Gate's, 113 mPD): raised too
COVER = 0.8           # a raised piece this much over a lower row, at most GAP m over its roof, sits on that roof
GAP = 15.0
# M2 fix round 2: one LandsD row per building where it has blocks of different heights the layer does not split (the
# Legislative Council Complex: one 7,308 m² row at 79.5 m for its 57.5 m Office Block and 33.3 m Council Block): cut
# by the parts in data/m2_splits.geojson (BuildingCSUID, height m over the ground; OSM's building:parts), tallest
# first, the last part taking the rest of the row
SPLITS = CITY / "data/m2_splits.geojson"
# storeys_fix, critic round 2: not podiums and halls carrying the whole building's storeys (Bay View Shopping Arcade
# 24.3 -> 74.4 m beside its 59.1 m tower), nor a row the fix would lift more than OVER m above a touching tower
NOT_TOWER = r"arcade|shopping|stadium|church|hall|school|car ?park|market|podium|mall"
OVER = 12.0
MIN_STOREY_RES = 2.5  # m a storey for residential blocks of 25+ storeys (Wo Fai House: 41 storeys at 95 m, 2.3 m)
NEW_AFTER = 1593561600000   # DateStamp (ms) after 1 July 2020: surveyed after the LiDAR (new platforms, Peak sites)
THIN = 10.0           # m: an unsupported row no taller than this over its base is a deck or link bridge (raised);
                      # a taller one is a tower on a podium or deck the layer lacks (ICC, The Cullinan on Union Square's
                      # deck; estate towers on their car-park podiums): drawn from the ground, through the missing podium


def sample_outline(geoms, path, step):
    """Lowest, highest and median value of the raster along each outline (every `step` m) and at an inner
    point; NaN where it has no data."""
    seg = shapely.segmentize(shapely.boundary(geoms), step)
    xy, owner = shapely.get_coordinates(seg, return_index=True)
    rp = shapely.get_coordinates(shapely.point_on_surface(geoms))
    xy = np.vstack([xy, rp])
    owner = np.concatenate([owner, np.arange(len(geoms))])
    with rasterio.open(path) as r:
        a = r.read(1, masked=True).astype(np.float32).filled(np.nan)
        rows, cols = rasterio.transform.rowcol(r.transform, xy[:, 0], xy[:, 1])
    rows, cols = np.asarray(rows), np.asarray(cols)
    ok = (rows >= 0) & (rows < a.shape[0]) & (cols >= 0) & (cols < a.shape[1])
    v = np.full(len(xy), np.nan, np.float32)
    v[ok] = a[rows[ok], cols[ok]]
    v[v < -100] = np.nan
    del a
    df = pd.DataFrame({"o": owner, "v": v}).dropna()
    gr = df.groupby("o")["v"]
    idx = np.arange(len(geoms))
    return tuple(np.array(s.reindex(idx), dtype=float) for s in (gr.min(), gr.max(), gr.median()))


def main():
    g = gpd.read_file(SRC)
    g = g.set_crs("EPSG:2326", allow_override=True)
    g["geometry"] = g.geometry.make_valid()
    print(f"{len(g):,} LandsD rows ({time.time() - T0:.0f} s)", flush=True)
    geoms = g.geometry.values
    lo, hi, med = sample_outline(geoms, LIDAR, 2.0)
    miss = np.isnan(lo)
    if miss.any():
        lo5, hi5, med5 = sample_outline(geoms[miss], DTM5, 5.0)
        lo[miss], hi[miss], med[miss] = lo5, hi5, med5
    g["ground_mpd"] = np.round(lo + PD_TO_MSL, 2)
    g["ground_lidar_mpd"] = g["ground_mpd"]
    # pits: the 2020 LiDAR's excavations under buildings finished since (and a pier's sea): the ground is the street
    # around them (the median lowest ground of the level rows, not in a pit, within NEAR m), never over the row's base
    hi_ = hi + PD_TO_MSL
    pit = g["ground_mpd"] < PIT
    lvl = g[~pit & ((hi_ - g["ground_mpd"]) < 3.0)]
    near = gpd.sjoin(gpd.GeoDataFrame(geometry=g.geometry[pit].buffer(NEAR), crs=g.crs), lvl[["ground_mpd", "geometry"]],
                     predicate="intersects")
    street = near.groupby(level=0)["ground_mpd"].median().reindex(g.index[pit])
    bh = pd.to_numeric(g["BaseHeight"], errors="coerce")
    fixed = np.fmin(street.fillna(3.0 + PD_TO_MSL), bh[pit].where(bh[pit] > PIT))
    g.loc[pit, "ground_mpd"] = np.round(fixed, 2)
    g["pit"] = pit
    print(f"pits: {int(pit.sum()):,} rows over ground under {PIT:g} mPD in the 2020 LiDAR (lowest "
          f"{g.ground_lidar_mpd.min():.1f}): ground set to the street around them (median "
          f"{float(np.nanmedian(fixed)):.1f} mPD)")
    g["ground_max_mpd"] = np.round(hi + PD_TO_MSL, 2)
    g["ground_src"] = np.where(miss, "dtm5m", "lidar")
    print(f"ground sampled: LiDAR {int((~miss).sum()):,}, 5 m DTM {int(miss.sum()):,}, none "
          f"{int(np.isnan(g.ground_mpd).sum()):,} ({time.time() - T0:.0f} s)", flush=True)

    base = pd.to_numeric(g["BaseHeight"], errors="coerce")
    top = pd.to_numeric(g["TopHeight"], errors="coerce")
    temp = g["BuildingBlockType"].eq("Temporary Structure")
    g["top_mpd"] = top.where(~(temp & top.isna()), g["ground_mpd"] + TEMP_H)
    g["top_note"] = np.where(temp & top.isna(), "temporary, no TopHeight: one storey", "")
    # storeys_fix (M2 fix round, critic finding 1): a block of 8+ storeys and 150 m²+ whose TopHeight gives it under
    # 2.2 m a storey (and no row beside it carries those storeys) cannot be that low (60 of them with DateStamp 2020-09-08: Kai Wong House 40.8 m for 38 storeys
    # beside its 107.7 m sisters, Nan Yang Plaza 43.3 m for 30): storeys x 4.0 m for offices and industrial blocks
    # (by name), 2.9 m for 30+ storey residential blocks (LandsD's own median over 30 storeys), 3.1 m otherwise
    st = pd.to_numeric(g["Storeys"], errors="coerce")
    per = (g["top_mpd"] - g["ground_mpd"]) / st
    office = g["BuildingNameEN"].fillna("").str.contains(OFFICE, case=False, regex=True)
    k = np.where(office, 4.0, np.where(st >= 30, 2.9, 3.1))
    resid = ~office & (st >= 25)
    sfix = (g["BuildingBlockType"].eq("Tower") & (st >= 8) & (g.area >= 150)
            & (per < np.where(resid, MIN_STOREY_RES, MIN_STOREY))
            & ~g["BuildingNameEN"].fillna("").str.contains(NOT_TOWER, case=False, regex=True))
    # not a lower wing of a building whose storeys another row carries: a row within 2 m of the same name (any, for an
    # unnamed row) reaching storeys x MIN_STOREY
    # (The Center's 14-17 m blocks round its tower carry its 64 storeys)
    cand_s = g[sfix]
    jj = gpd.sjoin(gpd.GeoDataFrame(geometry=cand_s.buffer(2.0), crs=g.crs),
                   g[["geometry"]].assign(reach=g["top_mpd"]), predicate="intersects")
    jj = jj[jj.index != jj.index_right]
    nm = g["BuildingNameEN"].fillna("").str.strip().str.lower()
    same = (nm.loc[jj.index].values == "") | (nm.loc[jj.index].values == nm.loc[jj.index_right].values)
    carried = jj[(jj.reach.values - g.loc[jj.index, "ground_mpd"].values >= st.loc[jj.index].values * MIN_STOREY)
                 & same].index
    sfix &= ~g.index.isin(carried)
    # nor where the raised top would stand OVER m above a touching tower of 8+ storeys that is not raised itself
    new_top = g["ground_mpd"] + st * k
    tw = g[g["BuildingBlockType"].eq("Tower") & (st >= 8) & ~sfix][["geometry"]].assign(t=g["top_mpd"])
    jo = gpd.sjoin(gpd.GeoDataFrame(geometry=g.geometry[sfix].buffer(1.0), crs=g.crs), tw, predicate="intersects")
    jo = jo[jo.index != jo.index_right]
    over = jo[new_top.loc[jo.index].values > jo.t.values + OVER].index.unique()
    sfix &= ~g.index.isin(over)
    print(f"storeys_fix: {len(over)} left as surveyed (they would stand over {OVER:g} m above a touching tower)")
    g.loc[sfix, "top_mpd"] = (g.loc[sfix, "ground_mpd"] + st[sfix] * k[sfix.to_numpy()]).round(2)
    g.loc[sfix, "top_note"] = "storeys_fix"
    g["storey_m_landsd"] = per.round(2)
    print(f"storeys_fix: {int(sfix.sum())} blocks under {MIN_STOREY:g} m a storey raised to storeys x 2.9-4.0 m")
    # splits (SPLITS): a row cut into its parts, each at its own height over the row's ground
    if SPLITS.exists():
        sp = gpd.read_file(SPLITS).to_crs(g.crs)
        add = []
        for csuid, parts in sp.groupby("BuildingCSUID"):
            hit = g.index[g["BuildingCSUID"] == csuid]
            if not len(hit):
                print(f"split: no row {csuid}")
                continue
            row = g.loc[hit[0]]
            rest = row.geometry
            parts = parts.sort_values("height", ascending=False)
            for n, (_, pt) in enumerate(parts.iterrows()):
                last = n == len(parts) - 1
                geom = rest if last else rest.intersection(pt.geometry)
                rest = rest if last else rest.difference(pt.geometry)
                r = row.copy()
                r["geometry"] = geom
                r["BuildingCSUID"] = f"{csuid}-{n}"
                r["top_mpd"] = round(row["ground_mpd"] + float(pt["height"]), 2)
                r["top_note"] = f"split: {pt['name']} {pt['height']:g} m ({pt['osm']})"
                add.append(r)
                print(f"split {csuid}: {pt['name']} {geom.area:,.0f} m² at {pt['height']:g} m")
            g = g.drop(index=hit[0])
        if add:
            g = pd.concat([g, gpd.GeoDataFrame(add, crs=g.crs)], ignore_index=True)
            base = pd.to_numeric(g["BaseHeight"], errors="coerce")
            top = pd.to_numeric(g["TopHeight"], errors="coerce")

    # sunk: a top at or under the lowest ground round the row (+ 0.5 m): a station box or tank under a park, a block
    # cut into a slope; nothing of it stands out of the ground (left out by city.toml's drop)
    sunk = (g["top_mpd"] - g["ground_mpd"]) <= SUNK
    g["m2_drop"] = np.where(sunk, "sunk", "")
    print(f"sunk: {int(sunk.sum()):,} rows whose top is at most {SUNK:g} m over their lowest ground")

    # standing on something? the share of the footprint over other rows (not open-sided) whose top reaches its base
    # (less 3 m) and whose base lies under it
    solid = g[g["BuildingBlockType"] != "Open-sided Structure"]
    cand = g.index[(base - g["ground_max_mpd"] >= LIFT) & g["BuildingBlockType"].ne("Open-sided Structure")]
    c = g.loc[cand]
    j = gpd.sjoin(c[["geometry"]], solid[["geometry"]], predicate="intersects")
    j = j[j.index != j.index_right]
    j = j[(top.reindex(j.index_right).values >= base.reindex(j.index).values - LIFT)
          & (base.reindex(j.index_right).values < base.reindex(j.index).values - 1.0)]
    sup = pd.Series(0.0, index=g.index)
    if len(j):
        under = gpd.GeoSeries(solid.geometry.loc[j.index_right].values, index=j.index).groupby(level=0).agg(
            lambda s: shapely.union_all(s.values))
        inter = shapely.area(shapely.intersection(c.geometry.loc[under.index].values, under.values))
        sup.loc[under.index] = inter / c.geometry.loc[under.index].area.values
    g["support"] = sup.round(3)
    mrr = shapely.minimum_rotated_rectangle(g.geometry.values)
    cc = [np.asarray(r.exterior.coords) for r in mrr]
    width = np.array([min(np.hypot(*(c[1] - c[0])), np.hypot(*(c[2] - c[1]))) if len(c) >= 3 else 0 for c in cc])
    narrow = (g.area < WIDE[0]).to_numpy() | (width < WIDE[1])
    sky = ((base - g["ground_max_mpd"]) >= HIGH).to_numpy() & narrow
    elev = g.index.isin(cand) & (sup < SUPPORT) & (((top - base) <= THIN).to_numpy() | sky)
    # critic round 2: rows surveyed after the 2020 LiDAR, over 150 m² and not narrow, whose base stands over the
    # LiDAR's ground stand on a platform built since (On Lai Court's podium 18 m over the 2020 slope, the Peak's
    # sites): drawn from the ground, not raised over it
    newp = (pd.to_numeric(g["DateStamp"], errors="coerce") > NEW_AFTER).to_numpy() & (g.area > 150).to_numpy() & ~narrow
    print(f"new platforms: {int((elev & newp & ~sky).sum())} rows surveyed after the LiDAR drawn from the ground, not raised")
    elev &= ~(newp & ~sky)
    g["deck_tower"] = g.index.isin(cand) & (sup < SUPPORT) & ~elev
    g["elevated"] = elev
    g["min_h"] = np.where(elev, np.round(base - g["ground_mpd"], 2), 0.0)
    # a raised piece lying COVER or more over a lower row whose roof is at most GAP m under its base sits on that roof
    # (decks over Elements' 23.5 mPD podium at 29-30 mPD, LOHAS Park's pieces over its 17 mPD deck): its underside
    # comes down to it (min_h 0: on the ground, when that roof is the ground's)
    e = g[elev]
    j = gpd.sjoin(e[["geometry"]], solid[["geometry"]], predicate="intersects")
    j = j[j.index != j.index_right]
    tu, bu = top.reindex(j.index_right).values, base.reindex(j.index).values
    j = j[(tu < bu) & (tu >= bu - GAP)]
    seated = 0
    g["seated"] = False
    for i, grp in j.groupby(level=0):
        u = solid.geometry.loc[grp.index_right.values]
        cov = shapely.area(shapely.intersection(e.geometry.loc[i], shapely.union_all(u.values))) / e.geometry.loc[i].area
        if cov >= COVER:
            roof = float(top.loc[grp.index_right.values].max())
            g.at[i, "min_h"] = max(0.0, round(roof - g.at[i, "ground_mpd"], 2))
            g.at[i, "seated"] = True
            seated += 1
    print(f"raised pieces seated on the roof under them ({COVER:.0%}+ over it, at most {GAP:g} m below): {seated}; "
          f"sky bridges (base {HIGH:g} m+ over the ground, narrow) raised: {int((elev & sky).sum())}")
    g["lift_mpd"] = np.round(base - g["ground_mpd"], 2)
    print(f"rows with a base {LIFT:g} m+ over the highest ground under them: {len(cand):,}; standing on other rows: "
          f"{int((sup.loc[cand] >= SUPPORT).sum()):,}; on nothing: {int((sup.loc[cand] < SUPPORT).sum()):,}, of them raised pieces (decks, link bridges, {THIN:g} m or less over their base) {int(elev.sum()):,}, towers drawn from the ground {int(g.deck_tower.sum()):,}")
    print(g.loc[elev].groupby("BuildingBlockType").size().to_dict())
    print(g.loc[elev, ["BuildingNameEN", "BaseHeight", "TopHeight", "ground_mpd", "ground_max_mpd", "support"]]
          .assign(a=g.loc[elev].area.round(0)).sort_values("a", ascending=False).head(30).to_string())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(OUT)
    print(f"→ {OUT} ({time.time() - T0:.0f} s)")


if __name__ == "__main__":
    main()
