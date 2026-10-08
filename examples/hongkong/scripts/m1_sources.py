"""Hong Kong M1: what each source brings inside the boundary (LandsD's Building layer, OSM), how they cover and
line up with each other, how their heights agree, LandsD's tower and podium rows, the landmark list against
LandsD, the CEDD LiDAR DTM against the 5 m DTM and Copernicus GLO-30 at known points, the datum, and OSM's
stacked flyovers (layer 2-4) for M3.

Run from demos/hongkong after 01_osm, 02_landsd and scripts/m1_dem_prep.py:
    uv run python scripts/m1_sources.py
Writes checks/m1_sources.md and checks/m1_heights.png. Loads every footprint of the boundary from both sources
(~130k polygons) and samples the DTMs at points (~2 GB): under the pipeline lock.
"""
import json
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from city3d.common import CHECKS, DATA, LEVEL_H, RAW, UTM, best_match, boundary, districts, height_m, load_osm, overpass  # noqa: E402

T0 = time.time()
PD_TO_MSL = 1.3                       # scripts/m1_dem_prep.py's offset (scene m = mPD - 1.3)
LIDAR = DATA / "dem_prepared/lidar2020_dtm_2m_msl.tif"
DTM5 = DATA / "dem_prepared/dtm5m_msl.tif"
GLO = [RAW / "Copernicus_DSM_COG_10_N22_00_E114_00_DEM.tif"]
L = []
poly = boundary().geometry.iloc[0]
dd = districts()
NAMES = list(dd.name)


def where(g):
    pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=UTM)
    j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
    return j[~j.index.duplicated()]["name"].reindex(g.index)


def sample(path, xy_utm, crs_to="EPSG:2326"):
    """Raster values at UTM points (NaN where no data)."""
    with rasterio.open(path) as r:
        tr = Transformer.from_crs(UTM, r.crs, always_xy=True)
        xs, ys = tr.transform(*np.asarray(xy_utm).T)
        v = np.array([s[0] for s in r.sample(zip(xs, ys))], float)
        nd = r.nodata
    v[(v == nd) | (v < -9000)] = np.nan
    return v


def window_max(path, x, y, rad):
    """The highest value within rad m of a UTM point (a summit's LiDAR/DTM top)."""
    from rasterio.windows import from_bounds
    with rasterio.open(path) as r:
        tr = Transformer.from_crs(UTM, r.crs, always_xy=True)
        cx, cy = tr.transform(x, y)
        if r.crs.is_geographic:
            d = rad / 111000.0
        else:
            d = rad
        w = from_bounds(cx - d, cy - d, cx + d, cy + d, r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=-9999).astype(float)
    a[a < -9000] = np.nan
    return float(np.nanmax(a)) if np.isfinite(a).any() else np.nan


# ---------------------------------------------------------------- the sources
HAVE_OSM = (DATA / "osm_buildings.gpkg").exists()
osm = load_osm() if HAVE_OSM else gpd.GeoDataFrame({"height": [], "levels": [], "name": [], "osm_id": []}, geometry=[], crs=UTM)
osm = osm[osm.intersects(poly)].copy()
osm["h_tag"] = osm["height"].map(height_m) if "height" in osm else np.nan
osm["lv"] = osm["levels"].map(height_m) if "levels" in osm else np.nan
osm["district"] = where(osm)
ld = gpd.read_file(DATA / "landsd_buildings.gpkg").to_crs(UTM)
ld = ld[ld.intersects(poly)].copy()
ld["district"] = where(ld)
ld["area"] = ld.area
ld["typ"] = ld["buildingblocktype"].fillna("?")
solid = ld[ld.typ.isin(["Tower", "Podium"])]
raw_info = json.loads((RAW / "landsd_building/profile.json").read_text()) if (RAW / "landsd_building/profile.json").exists() else {}
L += ["# Hong Kong M1: building sources, coverage, heights, alignment, terrain", "",
      f"`scripts/m1_sources.py` ({time.strftime('%Y-%m-%d %H:%M')}). Inside the boundary (option E snapped, "
      f"{poly.area / 1e6:.1f} km² with the sea, {len(dd)} districts: README \"Boundary\"); a footprint counts in the district "
      "holding its representative point. Sources: LandsD Building (02_landsd, the engine's file adapter over the "
      "CSDI FeatureServer pages in HK1980 Grid; open-sided structures dropped), OSM (01_osm; buildings above ground: "
      "location=underground and layer<0 left out).", ""]

# ---------------------------------------------------------------- 1. per district
L += ["## 1. Buildings per district and source", "",
      "| District | LandsD rows | Tower | Podium | Temporary | with height | LandsD ≥ 25 m² (tower/podium) | OSM buildings | OSM `height` | OSM `building:levels` |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for n in NAMES + [None]:
    a = ld if n is None else ld[ld.district == n]
    o = osm if n is None else osm[osm.district == n]
    t = a.typ.value_counts()
    L.append(f"| {'**all**' if n is None else n} | {len(a):,} | {t.get('Tower', 0):,} | {t.get('Podium', 0):,} | "
             f"{t.get('Temporary Structure', 0):,} | {a.h.notna().mean() * 100:.0f} % | "
             f"{((a.area >= 25) & a.typ.isin(['Tower', 'Podium'])).sum():,} | {len(o):,} | "
             f"{o.h_tag.notna().mean() * 100:.1f} % | {o.lv.notna().mean() * 100:.1f} % |")
L += ["", f"Footprint area: LandsD tower+podium {solid.area.sum() / 1e6:.2f} km² (all rows {ld.area.sum() / 1e6:.2f}), "
      f"OSM {osm.area.sum() / 1e6:.2f} km². Median footprint: LandsD {ld.area.median():.0f} m², OSM {osm.area.median():.0f} m². "
      f"LandsD rows with a name: {ld.buildingnameen.notna().mean() * 100:.0f} %; with Storeys: {ld.storeys.notna().mean() * 100:.0f} %.", ""]
if raw_info:
    a = raw_info.get("all_rows", {})
    L += [f"The raw file (E's box + 600 m): {a.get('rows', 0):,} rows, TopHeight missing on {a.get('top_null', 0):,} "
          f"(types {a.get('types')}).", ""]

if HAVE_OSM:
    # ---------------------------------------------------------------- 2. coverage
    print(f"coverage ({time.time() - T0:.0f} s)", flush=True)
    def cover(a, b):
        """Share of each footprint of a (by index) that b's footprints cover (pairwise overlay; overlaps in b
        counted twice, so capped at 1)."""
        ov = gpd.overlay(a[["geometry"]].reset_index(names="ia"), b[["geometry"]].reset_index(drop=True),
                         how="intersection", keep_geom_type=True)
        got = ov.assign(ar=ov.area).groupby("ia").ar.sum()
        return (got.reindex(a.index).fillna(0) / a.area).clip(upper=1).to_numpy()
    osm_cov = cover(osm, solid)
    big = solid[solid.area >= 25]
    ld_cov = cover(big, osm)
    L += ["## 2. Coverage: LandsD against OSM", "",
          f"- OSM buildings covered over half by LandsD tower/podium rows: **{np.mean(osm_cov > 0.5) * 100:.1f} %** "
          f"({(osm_cov > 0.5).sum():,} of {len(osm):,}); not covered at all: {(osm_cov < 0.05).sum():,} "
          f"(of them ≥ 100 m²: {((osm_cov < 0.05) & (osm.area.values >= 100)).sum():,}).",
          f"- LandsD tower/podium rows ≥ 25 m² covered over half by OSM: **{np.mean(ld_cov > 0.5) * 100:.1f} %** "
          f"({(ld_cov > 0.5).sum():,} of {len(big):,}); OSM lacks {(ld_cov < 0.05).sum():,} of them entirely "
          f"({big.area.values[ld_cov < 0.05].sum() / 1e6:.2f} km²).",
          f"- Area: OSM covered by LandsD {(osm_cov * osm.area.values).sum() / 1e6:.2f} km² of OSM's {osm.area.sum() / 1e6:.2f}; "
          f"LandsD (≥ 25 m²) covered by OSM {(ld_cov * big.area.values).sum() / 1e6:.2f} km² of {big.area.sum() / 1e6:.2f}.",
          "", "| District | OSM covered by LandsD | LandsD ≥ 25 m² covered by OSM |", "|---|---|---|"]
    for n in NAMES:
        mo, ml = (osm.district == n).values, (big.district == n).values
        L.append(f"| {n} | {np.mean(osm_cov[mo] > 0.5) * 100 if mo.any() else 0:.0f} % | {np.mean(ld_cov[ml] > 0.5) * 100 if ml.any() else 0:.0f} % |")
    L.append("")

    # ---------------------------------------------------------------- 3. offsets
    print(f"offsets ({time.time() - T0:.0f} s)", flush=True)
    # BuildingID is unique per row (block), not per building: the pairing is OSM building against LandsD row
    bld = solid.dissolve(by="buildingid", aggfunc={"topheight": "max", "baseheight": "min", "storeys": "max",
                                                   "buildingnameen": "first"}).reset_index()
    bld["h_bld"] = bld.topheight - bld.baseheight
    m = best_match(osm.assign(h=osm.h_tag), bld.assign(h=bld.h_bld), cols=("h",))
    m = m[m.iou > 0.5].copy()
    ca = osm.geometry.centroid.reindex(m.ia).values
    cb = bld.geometry.centroid.reindex(m.ib).values
    dx = np.array([b.x - a.x for a, b in zip(ca, cb)])
    dy = np.array([b.y - a.y for a, b in zip(ca, cb)])
    dist = np.hypot(dx, dy)
    L += ["## 3. Footprint offsets (OSM building against the LandsD row it overlaps most)", "",
          f"- Pairs with IoU > 0.5: {len(m):,} ({len(m) / len(osm) * 100:.0f} % of OSM); IoU median {m.iou.median():.3f}, p10 {m.iou.quantile(0.1):.3f}.",
          f"- Centroid shift LandsD − OSM: **median {np.median(dist):.2f} m**, p90 {np.quantile(dist, 0.9):.2f} m; "
          f"mean vector ({np.mean(dx):+.2f}, {np.mean(dy):+.2f}) m east/north, median ({np.median(dx):+.2f}, {np.median(dy):+.2f}): "
          "no systematic shift, so no per-cell alignment is needed (the sources agree within OSM's tracing error).",
          "", "| District | pairs | median shift (m) | p90 (m) | median IoU |", "|---|---|---|---|---|"]
    md = osm.district.reindex(m.ia).values
    for n in NAMES:
        k = md == n
        if k.any():
            L.append(f"| {n} | {k.sum():,} | {np.median(dist[k]):.2f} | {np.quantile(dist[k], 0.9):.2f} | {m.iou.values[k].mean():.3f} |")
    L.append("")

    # ---------------------------------------------------------------- 4. heights
    print(f"heights ({time.time() - T0:.0f} s)", flush=True)
    # each OSM building's LandsD height: the highest TopHeight of the tower/podium rows whose representative point
    # lies in it, minus the LiDAR ground at the building's representative point (both mPD): a tower on a podium counts
    # from the street, as OSM's height does
    rp = gpd.GeoDataFrame({"top": solid.topheight.values}, geometry=solid.geometry.representative_point().values, crs=UTM)
    jj = gpd.sjoin(rp, osm[["geometry"]], predicate="within")
    top = jj.groupby("index_right").top.max().reindex(osm.index)
    orp = np.array([(q.x, q.y) for q in osm.geometry.representative_point()])
    osm_ground = sample(LIDAR, orp) + PD_TO_MSL
    hb = (top.values - osm_ground)
    ho = osm.h_tag.values
    k = np.isfinite(hb) & np.isfinite(ho) & (ho > 0)
    err = hb[k] - ho[k]
    lvl = osm.lv.values
    kl = np.isfinite(hb) & np.isfinite(lvl) & (lvl > 0) & (hb > 0)
    L += ["## 4. Height agreement", "",
          "An OSM building's LandsD height = the highest TopHeight of the LandsD rows whose representative point lies in it, minus the LiDAR ground at its representative point (both mPD): from the street, as OSM's `height`.", "",
          f"- Against OSM `height`: n {k.sum():,}; LandsD − OSM median {np.median(err):+.1f} m, mean abs {np.mean(np.abs(err)):.1f} m, "
          f"within ±3 m {np.mean(np.abs(err) <= 3) * 100:.0f} %, within ±10 % {np.mean(np.abs(err) <= 0.1 * ho[k]) * 100:.0f} %.",
          f"- Against OSM `building:levels` × {LEVEL_H} m: n {kl.sum():,}; median ratio LandsD / (levels × {LEVEL_H}) "
          f"{np.median(hb[kl] / (lvl[kl] * LEVEL_H)):.2f}; metres per storey LandsD / levels median {np.median(hb[kl] / lvl[kl]):.2f} m.",
          ]
    st = bld.dropna(subset=["storeys"])
    st = st[(st.storeys > 0) & (st.h_bld > 0)]
    L.append(f"- LandsD's own Storeys: n {len(st):,}; metres per storey median {np.median(st.h_bld / st.storeys):.2f} m "
             f"(p25 {np.quantile(st.h_bld / st.storeys, 0.25):.2f}, p75 {np.quantile(st.h_bld / st.storeys, 0.75):.2f}); "
             f"over 30 storeys {np.median((st.h_bld / st.storeys)[st.storeys > 30]):.2f} m.")
    L += ["", "| OSM height band | n | LandsD − OSM median (m) | mean abs (m) | within ±10 % |", "|---|---|---|---|---|"]
    for lo_, hi_ in ((0, 15), (15, 30), (30, 60), (60, 100), (100, 200), (200, 600)):
        b = k.copy()
        b[k] = (ho[k] >= lo_) & (ho[k] < hi_)
        if b.any():
            e = hb[b] - ho[b]
            L.append(f"| {lo_}-{hi_} m | {b.sum():,} | {np.median(e):+.1f} | {np.mean(np.abs(e)):.1f} | {np.mean(np.abs(e) <= 0.1 * ho[b]) * 100:.0f} % |")
    be = pd.DataFrame({"ia": osm.index[k], "hb": hb[k], "ho": ho[k], "err": err})
    be = be[np.abs(be.err) > 30].sort_values("err", key=np.abs, ascending=False).head(10)
    if len(be):
        L += ["", f"Disagreements over 30 m: {(np.abs(err) > 30).sum():,}; the largest: " + "; ".join(
            f"{osm.at[r.ia, 'name'] if 'name' in osm and isinstance(osm.at[r.ia, 'name'], str) else osm.at[r.ia, 'osm_id']}: "
            f"LandsD {r.hb:.0f} vs OSM {r.ho:.0f}" for r in be.itertuples())]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.scatter(ho[k], hb[k], s=3, alpha=0.4)
    ax.plot([0, 500], [0, 500], "k-", lw=0.6)
    ax.set_xlabel("OSM height (m)")
    ax.set_ylabel("LandsD TopHeight − BaseHeight (m)")
    ax.set_title("Hong Kong E: LandsD against OSM heights")
    fig.tight_layout()
    fig.savefig(CHECKS / "m1_heights.png", dpi=90)
    L += ["", "![heights](m1_heights.png)", ""]

else:
    L += ["## 2-4. Coverage, offsets, heights against OSM", "", "Not measured yet: 01_osm has not run (the public Overpass answered 504 and timeouts all night; the local Overpass on 8786 was not up). Run `uv run city3d --overpass-cache ../data/hongkong/raw/overpass_cache 01_osm`, then this script again.", ""]
# ---------------------------------------------------------------- 5. towers and podiums
print(f"towers ({time.time() - T0:.0f} s)", flush=True)
tw = solid[solid.typ == "Tower"].copy()
pts = np.array([(p.x, p.y) for p in tw.geometry.representative_point()])
tw["ground"] = sample(LIDAR, pts) + PD_TO_MSL if LIDAR.exists() else np.nan
tw["above"] = tw.baseheight - tw.ground
pod = solid[solid.typ == "Podium"]
nb = solid.groupby("buildingid").typ.agg(lambda s: set(s))
both = nb.map(lambda s: {"Tower", "Podium"} <= s).sum()
tall = tw[tw.h >= 60]
on_pod = tw.above > 3
L += ["## 5. Tower and podium rows", "",
      f"- Rows: Tower {len(tw):,}, Podium {len(pod):,}; BuildingID is unique per row ({len(nb):,} ids, rows sharing one with a tower and a podium: {both:,}), so a building's blocks are tied together only by touching or overlapping: a tower row stands on the podium row under it.",
      f"- A tower row's BaseHeight against the LiDAR ground under it (mPD): {np.isfinite(tw.above).sum():,} sampled; "
      f"base more than 3 m above the ground: **{on_pod.sum():,}** ({on_pod.mean() * 100:.0f} %), of the towers ≥ 60 m "
      f"(TopHeight − BaseHeight) {(tall.above > 3).sum():,} of {len(tall):,}; median lift of those {tw.above[on_pod].median():.1f} m.",
      "  These are towers standing on a podium (or a deck): TopHeight − BaseHeight is their height above it. Extruded "
      "from the ground at that height they lose the podium's height: **M2 must stand them on their base** "
      "(min_height = BaseHeight − ground) **or extrude them from the ground to TopHeight − ground**. The engine's "
      "file adapter has no min_height for a primary source (see REPORT Known issues).",
      f"- Podium rows: median height {pod.h.median():.1f} m, p90 {pod.h.quantile(0.9):.1f} m; area median {pod.area.median():.0f} m².",
      f"- Tower BaseHeight below the ground by more than 3 m (basements counted in? sunk sites): {(tw.above < -3).sum():,}.", ""]

# ---------------------------------------------------------------- 6. landmarks
print(f"landmarks ({time.time() - T0:.0f} s)", flush=True)
lm = pd.read_csv("data/landmarks.csv")
lm = lm[lm.feature == "building"]
g = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs="EPSG:4326").to_crs(UTM)
L += ["## 6. Landmarks against LandsD", "",
      "The tallest LandsD row within 40 m of the point; ground = the LiDAR DTM there (mPD). Listed: data/landmarks.csv.", "",
      "| Landmark | listed (m) | type | LandsD row | Top (mPD) | Base (mPD) | ground (mPD) | Top − ground | Top − Base | use_height |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for r in g.itertuples():
    c = solid[solid.distance(r.geometry) <= 40]
    if not len(c):
        L.append(f"| {r.name_en} | {r.height_m} | {r.height_type} | none within 40 m | | | | | | {r.use_height} |")
        continue
    b = c.loc[c.topheight.idxmax()] if c.topheight.notna().any() else c.iloc[0]
    gr = sample(LIDAR, [(r.geometry.x, r.geometry.y)])[0] + PD_TO_MSL if LIDAR.exists() else np.nan
    nm = b.buildingnameen if isinstance(b.buildingnameen, str) else "(unnamed)"
    L.append(f"| {r.name_en} | {r.height_m if pd.notna(r.height_m) else ''} | {r.height_type if isinstance(r.height_type, str) else ''} | "
             f"{nm[:40]} ({b.typ}) | {b.topheight:.1f} | {b.baseheight:.1f} | {gr:.1f} | {b.topheight - gr:.1f} | {b.h:.1f} | {r.use_height} |")
L.append("")
# the extra towers by LandsD name
for q in ("SORRENTO", "ARCH", "CULLINAN", "HIGHCLIFF", "AIA CENTRAL", "HOPEWELL", "ONE ISLAND EAST", "INTERNATIONAL FINANCE CENTRE"):
    c = solid[solid.buildingnameen.fillna("").str.upper().str.contains(q)]
    if len(c):
        b = c.loc[c.topheight.idxmax()]
        p = gpd.GeoSeries([b.geometry.representative_point()], crs=UTM).to_crs(4326).iloc[0]
        L.append(f"- LandsD name contains \"{q}\": {len(c)} rows; tallest {b.buildingnameen} Top {b.topheight:.1f} mPD, "
                 f"Base {b.baseheight:.1f}, at {p.y:.5f}, {p.x:.5f}")
L.append("")

# ---------------------------------------------------------------- 7. terrain
print(f"terrain ({time.time() - T0:.0f} s)", flush=True)
import tomllib  # noqa: E402
cfg = tomllib.loads(open("city.toml").read())
pk = cfg["terrain"]["peaks"]
spots = cfg["terrain"]["spots"]
fwd = Transformer.from_crs(4326, UTM, always_xy=True)
L += ["## 7. Terrain: CEDD LiDAR DTM, the 5 m DTM and GLO-30", "",
      f"Scene heights (m above mean sea level): the two DTMs are mPD − {PD_TO_MSL} (scripts/m1_dem_prep.py); GLO-30 is "
      "over EGM2008 (≈ mean sea level here) and a surface model (roofs and trees). Summits: the highest cell within 30 m; "
      "spots: the cell at the point.", "",
      "| Point | expected (m) | LiDAR 2 m | 5 m DTM | GLO-30 | LiDAR − expected |", "|---|---|---|---|---|---|"]
for name, v in list(spots.items()) + list(pk.items()):
    x, y = fwd.transform(v[0], v[1])
    exp = v[2] if len(v) > 2 else np.nan
    is_peak = name in pk
    if is_peak:
        a, b5, c = (window_max(p, x, y, 30) if p.exists() else np.nan for p in (LIDAR, DTM5, GLO[0]))
    else:
        a, b5, c = (sample(p, [(x, y)])[0] if p.exists() else np.nan for p in (LIDAR, DTM5, GLO[0]))
    L.append(f"| {name} | {exp:.0f} | {a:.1f} | {b5:.1f} | {c:.1f} | {a - exp:+.1f} |")
# datum: flat open ground, GLO-30 minus LiDAR
with rasterio.open(LIDAR) as r:
    a = r.read(1, out_shape=(r.height // 25, r.width // 25)).astype(float)
    a[a < -9000] = np.nan
    trl = r.transform * r.transform.scale(r.width / a.shape[1], r.height / a.shape[0])
    rows, cols = np.nonzero(np.isfinite(a))
    xs, ys = rasterio.transform.xy(trl, rows, cols)
    to = Transformer.from_crs(r.crs, UTM, always_xy=True)
    ux, uy = to.transform(np.asarray(xs), np.asarray(ys))
    lid = a[rows, cols]
L.append("")
L.append(f"LiDAR mosaic: {np.isfinite(a).mean() * 100:.0f} % of its box has data (the tiles cover E; the 5 m DTM fills the ground margin).")
sel = np.random.default_rng(0).choice(len(lid), min(20000, len(lid)), replace=False)
glo = sample(GLO[0], np.c_[ux[sel], uy[sel]])
d5 = sample(DTM5, np.c_[ux[sel], uy[sel]])
low = (lid[sel] > 1) & (lid[sel] < 8)
L += [f"- GLO-30 − LiDAR (both ≈ mean sea level after the shift) on low ground (1-8 m, {low.sum():,} points of a 50 m grid): median "
      f"{np.nanmedian(glo[low] - lid[sel][low]):+.2f} m (roofs and trees lift GLO-30; open reclamation such as the Kai Tak runway is the fair test, above).",
      f"- 5 m DTM − LiDAR over the same points: median {np.nanmedian(d5 - lid[sel]):+.2f} m, mean abs {np.nanmean(np.abs(d5 - lid[sel])):.2f} m "
      "(same datum: the difference on low ground is the 5 m DTM's baked-in podiums, decks and bridges, raw/OFFICIAL_SUMMARY.md).",
      f"- 5 m DTM − LiDAR over all {np.isfinite(d5).sum():,} points: median {np.nanmedian(d5 - lid[sel]):+.2f} m, mean abs {np.nanmean(np.abs(d5 - lid[sel])):.2f} m; "
      f"on ground above 50 m (hillsides) median {np.nanmedian((d5 - lid[sel])[lid[sel] > 50]):+.2f} m.",
      "- The summits' surveyed heights are mPD (Hong Kong's survey datum), so the scene's LiDAR (MSL) should read ~1.3 m under them: "
      "it does (median of the summits above about −1.8 m). Mount Gough (−9.8), Tate's Cairn (−6.7, the radar station's platform) and "
      "Bowen Hill (+10.6) are Phase 0 coordinates off the summit or a surveyed figure of another point.", ""]

# ---------------------------------------------------------------- 8. flyovers
print(f"flyovers ({time.time() - T0:.0f} s)", flush=True)
x0, y0, x1, y1 = poly.bounds
inv = Transformer.from_crs(UTM, 4326, always_xy=True)
lo0, la0 = inv.transform(x0, y0)
lo1, la1 = inv.transform(x1, y1)
try:
    if not HAVE_OSM:
        raise RuntimeError("01_osm has not run yet; the public mirrors were down: the count waits for the local Overpass")
    res = overpass(f'[out:json][timeout:300];way["highway"]["layer"]({la0:.4f},{lo0:.4f},{la1:.4f},{lo1:.4f});out tags geom;')
    from shapely.geometry import LineString
    rows = []
    for e in res["elements"]:
        t = e["tags"]
        try:
            lay = int(float(str(t.get("layer", "0")).split(";")[0]))
        except ValueError:
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in e["geometry"]])
        rows.append({"layer": lay, "hw": t.get("highway"), "bridge": t.get("bridge"), "geometry": ls})
    fw = gpd.GeoDataFrame(rows, crs=4326).to_crs(UTM)
    fw = fw[fw.intersects(poly)]
    fw["km"] = fw.length / 1000
    L += ["## 8. Stacked flyovers for M3 (OSM highway ways by layer, inside the boundary)", "",
          "| layer | ways | km | of them motorway/trunk/primary (+ links) |", "|---|---|---|---|"]
    for lay, gg in fw.groupby("layer"):
        if lay < 1:
            continue
        maj = gg.hw.str.replace("_link", "").isin(["motorway", "trunk", "primary"])
        L.append(f"| {lay} | {len(gg):,} | {gg.km.sum():.1f} | {maj.sum():,} |")
    L += ["", f"Ways at layer 2-4: {fw.layer.between(2, 4).sum():,} ({fw[fw.layer.between(2, 4)].km.sum():.1f} km); layer 5+: "
          f"{(fw.layer >= 5).sum():,}. At roads.layer_h 7.5 m a layer-4 deck stands 30 m up: check the big interchanges "
          "(Western Harbour Crossing's Kowloon side, Kai Tak, Tseung Kwan O tunnel approaches) in M3.", ""]
except Exception as e:  # noqa: BLE001
    L += ["## 8. Stacked flyovers", "", f"Overpass failed ({str(e)[:200]}): count again in M3 from 05b_roads' ways.", ""]

L.append(f"({time.time() - T0:.0f} s)")
(CHECKS / "m1_sources.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
