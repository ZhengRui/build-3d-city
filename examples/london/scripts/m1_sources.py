"""London M1: what each building source brings inside the boundary, how their heights agree, how their outlines
line up, how the Carbon & Place heights reach OSM's footprints, the tall towers against the landmark list, the DEM's
low ground, and a map of the footprints coloured by the height source each would take.

Run from demos/london after 01_osm and 02_carbon:  uv run python scripts/m1_sources.py
Writes checks/sources.md, checks/heights_map.png, checks/heights_map_city.png. Heavy-ish (all footprints of the
boundary from four sources; ~2-3 GB): under the pipeline lock.
"""
import time

import duckdb
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from city3d import sources  # noqa: E402
from city3d.common import CFG, CHECKS, CITY, DATA, LEVEL_H, RAW, UTM, best_match, boundary, districts, load_osm  # noqa: E402
from city3d.stages import buildings as B4  # noqa: E402

T0 = time.time()
L = []
poly = boundary().geometry.iloc[0]
dd = districts()
NAMES = list(dd.name)


def where(g):
    """district of each footprint by its representative point (NaN outside)."""
    pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=UTM)
    j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
    return j[~j.index.duplicated()]["name"].reindex(g.index)


def inside(g):
    return g[g.geometry.representative_point().within(poly)].copy()


# ------------------------------------------------------------------ sources
osm = inside(load_osm())
osm["district"] = where(osm)
cp = sources.module("carbon").load()
cp = cp[cp.intersects(poly)].copy()
cp["district"] = where(cp)
# the mean height over the polygon: Carbon & Place's volume (sum of DSM - DTM over its 2 m cells) / its area
cp["h_max"] = cp["h"]
cp["h_mean"] = (cp["volume"] / cp.area).where(cp["volume"] > 0)
# a hybrid as APUR's in Paris: the maximum where the polygon is a tower or a plain block (mean >= MIX x max), the
# mean where the maximum is a spike over a lower roof (a chimney, a crane, a neighbouring tower's edge)
MIX = 0.6
cp["h_mix"] = np.where(cp.h_mean >= MIX * cp.h_max, cp.h_max, cp.h_mean)

bd_bng = gpd.GeoSeries([poly], crs=UTM).to_crs("EPSG:27700")
os_ = gpd.read_file(RAW / "os_openmap_local/TQ_Building.shp", bbox=tuple(bd_bng.total_bounds))
os_ = os_.set_crs("EPSG:27700", allow_override=True).to_crs(UTM)
os_ = inside(os_)
os_["district"] = where(os_)

w, s, e, n = gpd.GeoSeries([poly], crs=UTM).to_crs("EPSG:4326").total_bounds
con = duckdb.connect()
rows = con.execute(f"""SELECT id, sources[1].dataset AS ds, height, num_floors, ST_AsWKB(geometry) AS wkb
    FROM read_parquet('{RAW / "overture/overture_buildings_2026-09-23.1_london_bbox.parquet"}')
    WHERE bbox.xmin < {e} AND bbox.xmax > {w} AND bbox.ymin < {n} AND bbox.ymax > {s}""").fetchdf()
ov = gpd.GeoDataFrame(rows.drop(columns="wkb"), geometry=shapely.from_wkb([bytes(b) for b in rows.wkb]),
                      crs="EPSG:4326").to_crs(UTM)
ov = inside(ov)
ov["district"] = where(ov)
ms = ov[ov.ds != "OpenStreetMap"]
print(f"loaded in {time.time() - T0:.0f} s: osm {len(osm):,} cp {len(cp):,} os {len(os_):,} overture {len(ov):,}")

# ------------------------------------------------------------------ how C&P heights reach OSM footprints
# the engine's rule (04_buildings source_height): the C&P polygon covering most of the footprint, if it covers
# >= needle.cover of it (tall heights onto small footprints only when they hold enough of the polygon)
osm["h_cp_rule"] = B4.source_height(osm, cp)
osm["h_cp_mean"] = B4.source_height(osm, cp.assign(h=cp.h_mean))
osm["h_cp_mix"] = B4.source_height(osm, cp.assign(h=cp.h_mix))
# by representative point: the C&P polygon under it
pts = gpd.GeoDataFrame(geometry=osm.geometry.representative_point(), crs=UTM)
j = gpd.sjoin(pts, cp[["geometry", "h"]], predicate="within", how="left")
j = j[~j.index.duplicated()]
osm["h_cp_point"] = j["h"].reindex(osm.index)
# area-weighted over every C&P polygon it overlaps (and the highest of them)
ix = gpd.overlay(osm[["geometry"]].reset_index(names="io"), cp[["geometry", "h"]], how="intersection",
                 keep_geom_type=True)
ix["a"] = ix.area
ix = ix[ix.h.notna()]
g = ix.groupby("io")
cover = (g.a.sum() / osm.area.reindex(g.a.sum().index)).reindex(osm.index)
osm["cp_cover"] = cover
osm["h_cp_area"] = (ix.assign(ha=ix.h * ix.a).groupby("io").ha.sum() / g.a.sum()).reindex(osm.index)
osm["h_cp_max"] = g.h.max().reindex(osm.index)
osm["n_cp"] = g.size().reindex(osm.index).fillna(0)

# ------------------------------------------------------------------ 1. per district
L += ["# London M1: building sources, coverage, heights, alignment", "",
      f"`scripts/m1_sources.py` ({time.strftime('%Y-%m-%d %H:%M')}). Inside the boundary ({poly.area / 1e6:.1f} km², "
      "9 districts, incl. the Thames to mid-river at the borough edges); a footprint counts in the district holding "
      "its representative point. Sources: OSM (01_osm, BBBike extract 2026-09-25, local Overpass), Carbon & Place "
      "Building Heights (02_carbon; polygons from OS OpenMap / OSM / HM Land Registry INSPIRE split per plot, heights "
      "= max of the EA lidar 2 m DSM − DTM inside each), OS OpenMap Local (TQ_Building, no heights), Overture "
      "2026-09-23.1 (OSM + Microsoft ML footprints). GBA (CC BY-NC) is not used.", "",
      "## 1. Buildings per district and source", "",
      "| District | OSM | OSM with `height` | OSM with `building:levels` | OSM with either | Carbon & Place polygons | "
      "OS OpenMap Local | Overture (of which Microsoft ML) |", "|---|---|---|---|---|---|---|---|"]
for d in NAMES + [None]:
    k = (lambda g: g.district == d) if d else (lambda g: g.district.notna() | True)
    o = osm[k(osm)]
    L.append(f"| {d or '**all**'} | {len(o):,} | {o.h_tag.notna().mean():.1%} | {o.h_levels.notna().mean():.1%} | "
             f"{o.h.notna().mean():.1%} | {int(k(cp).sum()):,} | {int(k(os_).sum()):,} | "
             f"{int(k(ov).sum()):,} ({int(k(ms).sum()):,}) |")
L += ["", f"Footprint area: OSM {osm.area.sum() / 1e6:.2f} km², Carbon & Place {cp.area.sum() / 1e6:.2f} km², "
      f"OS OpenMap Local {os_.area.sum() / 1e6:.2f} km², Overture {ov.area.sum() / 1e6:.2f} km². Median footprint: OSM "
      f"{osm.area.median():.0f} m², Carbon & Place {cp.area.median():.0f} m², OS {os_.area.median():.0f} m².", ""]

# ------------------------------------------------------------------ 2. C&P heights onto OSM
L += ["## 2. Carbon & Place heights on the OSM footprints", "",
      "Carbon & Place splits OSM's and OS's outlines at the land-registry plots (a terrace house per polygon, a "
      "block into its titles), so an OSM building is often covered by several of its polygons:", "",
      f"- OSM footprints overlapping any Carbon & Place polygon: {osm.cp_cover.notna().mean():.1%}; median share of the "
      f"footprint covered {osm.cp_cover.median():.2f}; median number of polygons per footprint "
      f"{osm.n_cp[osm.n_cp > 0].median():.0f} (p90 {osm.n_cp[osm.n_cp > 0].quantile(0.9):.0f}).",
      f"- a height by the engine's rule (04_buildings `source_height`: the polygon covering most of the footprint, if "
      f"it covers ≥ {B4.NEEDLE['cover']:.0%} of it, tall ones onto small footprints only as a large share): "
      f"**{osm.h_cp_rule.notna().mean():.1%}** of OSM footprints ({osm.h_cp_rule.notna().sum():,}).",
      f"- the polygon under the representative point: {osm.h_cp_point.notna().mean():.1%}; area-weighted over every "
      f"overlapping polygon: {osm.h_cp_area.notna().mean():.1%}.", ""]
miss = osm[osm.h_cp_rule.isna() & osm.h_cp_area.notna()]
L += [f"Footprints the engine's rule leaves without a height although polygons cover them: {len(miss):,} "
      f"({miss.area.sum() / 1e6:.2f} km², median {miss.area.median():.0f} m², median cover {miss.cp_cover.median():.2f}). "
      "Where the rule gives one, it against the area-weighted mean: median difference "
      f"{(osm.h_cp_rule - osm.h_cp_area).median():+.2f} m, |p90| "
      f"{(osm.h_cp_rule - osm.h_cp_area).abs().quantile(0.9):.1f} m.", ""]
nocp = osm[osm.cp_cover.isna()]
L += [f"OSM footprints with no Carbon & Place polygon at all: {len(nocp):,} ({nocp.area.sum() / 1e6:.3f} km²; tags: "
      f"{nocp.building.value_counts().head(6).to_dict()}); with an OSM height or levels {nocp.h.notna().mean():.0%}.", ""]

# C&P polygons that overlap no OSM footprint: the "fill" role's candidates
allosm = load_osm()
mb = best_match(cp, allosm[allosm.intersects(poly)], cols=())
share = (mb.set_index("ia").inter / cp.area.reindex(mb.ia).values).reindex(cp.index).fillna(0)
fill = cp[share < B4.DUP_SHARE]
L += [f"Carbon & Place polygons overlapping no OSM footprint (under {B4.DUP_SHARE:.0%}; what role \"fill\" would add): "
      f"**{len(fill):,}** ({fill.area.sum() / 1e6:.3f} km²; median {fill.area.median():.0f} m², "
      f"height p50/p90 {fill.h.quantile(0.5):.1f}/{fill.h.quantile(0.9):.1f} m); OSM building tags of them "
      f"(Carbon & Place's `building` column, from its OSM join): {fill.building.fillna('none').value_counts().head(6).to_dict()}. "
      f"Over 100 m² and 4 m: {int(((fill.area > 100) & (fill.h > 4)).sum()):,}.", ""]
fd = fill.district.value_counts()
L += ["Per district: " + ", ".join(f"{d} {fd.get(d, 0):,}" for d in NAMES) + ".", ""]

# ------------------------------------------------------------------ 3. height agreement
BANDS = [(0, 10), (10, 20), (20, 50), (50, 100), (100, 1e9)]


def row(name, ref, est):
    ok = ref.notna() & est.notna()
    e = (est - ref)[ok]
    if ok.sum() < 3:
        return f"| {name} | {ok.sum()} | | | | |"
    return (f"| {name} | {ok.sum():,} | {e.median():+.1f} | {e.abs().mean():.1f} | {e.abs().median():.1f} | "
            f"{ref[ok].corr(est[ok]):.3f} |")


L += ["## 3. Height agreement: Carbon & Place against OSM's tags", "",
      "Carbon & Place by the engine's rule, on OSM footprints with a `height` tag, and with `building:levels` × "
      f"{LEVEL_H} m (level_h). Error = Carbon & Place − OSM.", "",
      "| Pair | n | median error (m) | MAE (m) | median abs error (m) | r |", "|---|---|---|---|---|---|",
      row("vs `height`", osm.h_tag, osm.h_cp_rule)]
for lo, hi in BANDS:
    k = (osm.h_tag >= lo) & (osm.h_tag < hi)
    L.append(row(f"vs `height` {lo}–{hi:.0f} m" if hi < 1e9 else f"vs `height` ≥ {lo} m", osm.h_tag[k], osm.h_cp_rule[k]))
L.append(row("vs `building:levels` × level_h", osm.h_levels, osm.h_cp_rule))
for lo, hi in BANDS[:4]:
    k = (osm.h_levels >= lo) & (osm.h_levels < hi)
    L.append(row(f"vs levels {lo}–{hi:.0f} m", osm.h_levels[k], osm.h_cp_rule[k]))
for col, lab in (("h_cp_mean", "mean (volume / area)"), ("h_cp_mix", f"hybrid (max if mean ≥ {MIX} max, else mean)")):
    L.append(row(f"{lab} vs `height`", osm.h_tag, osm[col]))
    for lo, hi in BANDS:
        k = (osm.h_tag >= lo) & (osm.h_tag < hi)
        L.append(row(f"{lab} vs `height` {lo}–{hi:.0f} m" if hi < 1e9 else f"{lab} vs `height` ≥ {lo} m", osm.h_tag[k], osm[col][k]))
    L.append(row(f"{lab} vs levels × level_h", osm.h_levels, osm[col]))
L.append(row("area-weighted vs `height`", osm.h_tag, osm.h_cp_area))
L.append(row("area-weighted vs levels × level_h", osm.h_levels, osm.h_cp_area))
L.append("")
# metres per storey: OSM's own height / levels pairs, and Carbon & Place over levels
lv = pd.to_numeric(osm["levels"], errors="coerce")
both = osm[osm.h_tag.notna() & (lv > 0)]
r_tag = (both.h_tag / lv[both.index])
k = osm.h_cp_rule.notna() & (lv > 0) & (lv <= 12)
r_cp = (osm.h_cp_rule[k] / lv[k])
L += [f"Metres per storey: OSM `height` / `building:levels` on the {len(both):,} footprints tagged with both: median "
      f"{r_tag.median():.2f} (p25 {r_tag.quantile(0.25):.2f}, p75 {r_tag.quantile(0.75):.2f}); Carbon & Place / levels "
      f"on {k.sum():,} footprints of 1-12 levels: median {r_cp.median():.2f} (the lidar's maximum: ridges, parapets and "
      "plant over the top floor's ceiling). By levels: " + ", ".join(
          f"{a}-{b}: {(osm.h_cp_rule[k & lv.between(a, b)] / lv[k & lv.between(a, b)]).median():.2f}"
          for a, b in ((1, 2), (3, 4), (5, 6), (7, 9), (10, 12))) + ".", ""]

# scatter
fig, ax = plt.subplots(1, 2, figsize=(11, 5.2))
for a, (ref, lab) in zip(ax, ((osm.h_tag, "OSM height tag (m)"), (osm.h_levels, f"OSM levels × {LEVEL_H} m"))):
    ok = ref.notna() & osm.h_cp_rule.notna()
    a.scatter(ref[ok], osm.h_cp_rule[ok], s=3, alpha=0.3)
    top = 320 if "tag" in lab else 120
    a.plot([0, top], [0, top], "k--", lw=0.8)
    a.set(xlabel=lab, ylabel="Carbon & Place height_max (m)", xlim=(0, top), ylim=(0, top), title=f"n={ok.sum():,}")
fig.tight_layout()
fig.savefig(CHECKS / "heights_cp_osm.png", dpi=100)
plt.close(fig)
L += ["![Carbon & Place against OSM](heights_cp_osm.png)", ""]

# ------------------------------------------------------------------ 4. towers vs the landmark list
lm = pd.concat([pd.read_csv(f) for f in sorted(CITY.glob(CFG["paths"]["landmarks"]))], ignore_index=True)
lm = lm[lm.feature.eq("building") & lm.height_m.notna()]
lp = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs="EPSG:4326").to_crs(UTM)
lall = gpd.GeoDataFrame(pd.concat([pd.read_csv(f) for f in sorted(CITY.glob(CFG["paths"]["landmarks"]))], ignore_index=True)
                        .dropna(subset=["lat", "lon"]).pipe(lambda d: d.assign(geometry=gpd.points_from_xy(d.lon, d.lat))),
                        crs="EPSG:4326").to_crs(UTM)
outside = lall[~lall.within(poly)].assign(d=lambda d: d.distance(poly))
lp = lp[lp.within(poly.buffer(50))]
parts = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM) if (DATA / "osm_parts.gpkg").exists() else None
from city3d.common import height_m  # noqa: E402
if parts is not None:
    parts["h_tag"] = parts["height"].map(height_m)
near = gpd.sjoin_nearest(lp[["geometry"]], osm[["geometry"]], max_distance=40, distance_col="d")
near = near[~near.index.duplicated()]
cpn = gpd.sjoin_nearest(lp[["geometry"]], cp[["geometry", "h"]], max_distance=40, distance_col="d")
cp_max = {}
for i, p in lp.geometry.items():         # the highest C&P polygon within 30 m (a tower's top sits in one plot)
    c = cp[cp.intersects(p.buffer(30))]
    cp_max[i] = c.h.max() if len(c) else np.nan
rows = []
for i, r in lp.iterrows():
    k = near.index_right.get(i) if i in near.index else None
    o = osm.loc[k] if k is not None and not pd.isna(k) else None
    ptag = np.nan
    if parts is not None and o is not None:
        pp = parts[parts.intersects(o.geometry)]
        ptag = pp.h_tag.max() if len(pp) else np.nan
    rows.append(dict(name=r.name_en, listed=r.height_m, type=str(r.height_type)[:14],
                     year="" if pd.isna(pd.to_numeric(r.year, errors="coerce")) else int(pd.to_numeric(r.year, errors="coerce")), use=r.use_height,
                     cp_rule=o.h_cp_rule if o is not None else np.nan, cp_mix=o.h_cp_mix if o is not None else np.nan, cp_max30=cp_max[i],
                     osm_h=o.h_tag if o is not None else np.nan, osm_part=ptag,
                     osm_lv=o.h_levels if o is not None else np.nan))
T = pd.DataFrame(rows)
T["cp_best"] = T[["cp_rule", "cp_max30"]].max(axis=1)
T["osm_best"] = T[["osm_h", "osm_part"]].max(axis=1)
tall = T[(T.listed >= 100) & T.use.astype(str).str.lower().eq("true")].sort_values("listed", ascending=False)


def within(col, tol):
    ok = tall[col].notna()
    return int((ok & ((tall[col] - tall.listed).abs() <= tol * tall.listed)).sum()), int(ok.sum())


L += ["## 4. The tall towers against the landmark list", "",
      f"`data/landmarks_london.csv`: {len(lp)} building rows in the boundary, {len(tall)} towers of 100 m or more with "
      "use_height true. Per tower: Carbon & Place under the OSM footprint at the point (engine rule) and the highest "
      "Carbon & Place polygon within 30 m; OSM's `height` on the outline and the tallest `building:part` on it; "
      f"`building:levels` × {LEVEL_H}.", "",
      "| Source | within 5 % | within 15 % | with a value |", "|---|---|---|---|"]
for col, lab in (("cp_best", "Carbon & Place (best of rule, max 30 m)"), ("cp_mix", "Carbon & Place hybrid (engine rule)"), ("osm_best", "OSM height / tallest part"),
                 ("osm_lv", "OSM levels × level_h")):
    a5, n5 = within(col, 0.05)
    a15, _ = within(col, 0.15)
    L.append(f"| {lab} | {a5} | {a15} | {n5} |")
L += ["", "| Tower | listed (m) | type | year | C&P rule | C&P hybrid | C&P max 30 m | OSM height | OSM tallest part | OSM levels × level_h |",
      "|---|---|---|---|---|---|---|---|---|---|"]
f1 = lambda v: "" if pd.isna(v) else f"{v:.0f}"  # noqa: E731
must = ["The Shard", "22 Bishopsgate", "One Canada Square", "The Gherkin", "20 Fenchurch Street", "122 Leadenhall Street",
        "Heron Tower", "St George Wharf Tower", "BT Tower", "Tower 42", "One Nine Elms City Tower", "Landmark Pinnacle"]
show = pd.concat([T[T.name.isin(must)], tall[~tall.name.isin(must)]]).drop_duplicates("name")
for _, r in show.iterrows():
    L.append(f"| {r['name']} | {r.listed:.0f} | {r.type} | {r.year} | {f1(r.cp_rule)} | {f1(r.cp_mix)} | {f1(r.cp_max30)} | "
             f"{f1(r.osm_h)} | {f1(r.osm_part)} | {f1(r.osm_lv)} |")
L += ["", f"Landmark rows outside the boundary ({len(outside)} of {len(lall)}): " + ", ".join(
    f"{r.name_en} ({r.d:.0f} m out)" for _, r in outside.sort_values("d").iterrows()) + "."]
low = tall[tall.cp_best < 0.85 * tall.listed]
L += ["", f"Carbon & Place more than 15 % under the listed height: {len(low)} towers — "
      + ", ".join(f"{r['name']} ({r.year}, {f1(r.cp_best)} for {r.listed:.0f})" for _, r in low.iterrows())
      + ". The lidar composite predates them or their tops (built or topped out since ~2020); the landmark list "
      "(first in `heights`) and OSM's tags carry them.", ""]

# ------------------------------------------------------------------ 5. offsets
def offsets(a, b, label):
    big = a[a.area > 400]
    m = best_match(big, b, cols=())
    m = m[m.iou > 0.5]
    ca = big.centroid.reindex(m.ia).values
    cb = b.centroid.reindex(m.ib).values
    dx = np.array([q.x - p.x for p, q in zip(ca, cb)])
    dy = np.array([q.y - p.y for p, q in zip(ca, cb)])
    return (f"| {label} | {len(m):,} of {len(big):,} | {np.median(dx):+.2f} | {np.median(dy):+.2f} | "
            f"{np.median(np.hypot(dx, dy)):.2f} | {m.iou.median():.2f} |")


L += ["## 5. Offsets between the sources' outlines", "",
      "Footprints over 400 m² of the first source matched to the second by largest overlap (IoU > 0.5); "
      "centroid shift second − first in UTM metres (x east, y north).", "",
      "| Pair | matched | median dx (m) | median dy (m) | median shift (m) | median IoU |", "|---|---|---|---|---|---|",
      offsets(osm, cp, "OSM → Carbon & Place"), offsets(osm, os_, "OSM → OS OpenMap Local"),
      offsets(os_, cp, "OS OpenMap Local → Carbon & Place"), offsets(osm, ms, "OSM → Overture's Microsoft ML"), ""]
mm = best_match(ms, osm, cols=())
msx = ms[~ms.index.isin(mm[mm.inter / ms.area.reindex(mm.ia).values >= 0.05].ia)]
L += [f"Overture's Microsoft ML footprints in the boundary: {len(ms):,}; overlapping no OSM footprint: {len(msx):,} "
      f"({msx.area.sum() / 1e6:.3f} km²).", ""]

# ------------------------------------------------------------------ 6. low ground in the DEM
from city3d.stages import terrain as T5  # noqa: E402
from rasterio.warp import Resampling  # noqa: E402
x0, y0, x1, y1 = poly.bounds
gx0, gz0, nx, nz, tr = T5.scene_grid(((x0 + x1) / 2, (y0 + y1) / 2), (x0, y0, x1, y1), 10.0)
z = T5.dem_on(tr, (nz, nx), Resampling.average, sources.module("geotiff").tiles("ground"))
inb = T5.burn((nz, nx), tr, [poly]).astype(bool)
v = z[inb & np.isfinite(z)]
L += ["## 6. The DEM's low ground inside the boundary", "",
      f"Carbon & Place DTM on a 10 m grid inside the boundary ({inb.sum() * 1e-2:.0f} ha incl. the river): "
      f"p1 {np.percentile(v, 1):.1f} m, p5 {np.percentile(v, 5):.1f}, p50 {np.percentile(v, 50):.1f}, p99 "
      f"{np.percentile(v, 99):.1f}, max {v.max():.1f} m ODN; under 0 m: {(v < 0).sum() * 1e-2:.1f} ha; under 2.5 m: "
      f"{(v < 2.5).sum() * 1e-2:.0f} ha; 2.5-3.5 m (mostly the river's flat surface): {((v >= 2.5) & (v < 3.5)).sum() * 1e-2:.0f} ha.", ""]
neg = z < -2
if neg.any():
    from scipy import ndimage as ndi
    lab, nl = ndi.label(neg & inb)
    sizes = ndi.sum(np.ones_like(z), lab, range(1, nl + 1))
    L += [f"Pits under −2 m inside the boundary: {nl} regions, {neg[inb].sum() * 1e-2:.1f} ha; the largest:"]
    for k in np.argsort(sizes)[::-1][:6]:
        ii, jj = np.where(lab == k + 1)
        xx, yy = tr * (jj.mean(), ii.mean())
        from pyproj import Transformer
        lon, lat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(xx, yy)
        L.append(f"- {sizes[k] * 1e-2:.2f} ha at {lat:.4f}, {lon:.4f}, lowest {z[lab == k + 1].min():.1f} m")
    L.append("")

# ------------------------------------------------------------------ 7. map by height source
src = pd.Series("default", index=osm.index)
src[osm.h_levels.notna()] = "osm_levels"
src[osm.h_tag.notna()] = "osm_height"
src[osm.h_cp_rule.notna()] = "carbon"
lmk = {k for k, i in zip(near.index_right, near.index) if str(lp.loc[i, "use_height"]).lower() == "true"}
src[src.index.isin(lmk)] = "landmark"
osm["h_src"] = src
cnt = src.value_counts()
L += ["## 7. Which height each OSM footprint would take", "",
      "With `heights = [landmark, carbon, osm_height, osm_levels, default]` (before 04_buildings' parts, "
      "reconciliation and the Carbon & Place fill): " + ", ".join(f"{k} {v:,} ({v / len(osm):.1%})" for k, v in cnt.items())
      + ".", "", "| District | " + " | ".join(cnt.index) + " |", "|---" * (len(cnt) + 1) + "|"]
for d in NAMES:
    s_ = src[osm.district == d]
    L.append(f"| {d} | " + " | ".join(f"{(s_ == c).mean():.1%}" for c in cnt.index) + " |")
L += ["", "![map](heights_map.png)", "", "![the City and the South Bank](heights_map_city.png)", ""]
COL = {"landmark": "#d62728", "carbon": "#1f77b4", "osm_height": "#ff7f0e", "osm_levels": "#2ca02c",
       "default": "#7f7f7f", "fill": "#9467bd"}


def draw(path, box=None, size=(16, 9)):
    fig, a = plt.subplots(figsize=size)
    gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=a, color="k", lw=0.5)
    dd.boundary.plot(ax=a, color="#999", lw=0.3)
    for k, c in COL.items():
        g = fill if k == "fill" else osm[osm.h_src == k]
        if box is not None:
            g = g.cx[box[0]:box[2], box[1]:box[3]]
        if len(g):
            g.plot(ax=a, color=c, lw=0, label=f"{'Carbon & Place fill (no OSM)' if k == 'fill' else k} ({len(g):,})")
    if box is not None:
        a.set_xlim(box[0], box[2]), a.set_ylim(box[1], box[3])
    a.legend(loc="lower left", fontsize=8, markerscale=4)
    a.set_xticks([]), a.set_yticks([])
    a.set_title("OSM footprints by the height source they would take; Carbon & Place polygons OSM lacks")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


draw(CHECKS / "heights_map.png")
from pyproj import Transformer  # noqa: E402
t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
bx0, by0 = t.transform(-0.105, 51.500)
bx1, by1 = t.transform(-0.070, 51.518)
draw(CHECKS / "heights_map_city.png", (bx0, by0, bx1, by1), (12, 9))

L += [f"({time.time() - T0:.0f} s)", ""]
(CHECKS / "sources.md").write_text("\n".join(L))
print("\n".join(L))
