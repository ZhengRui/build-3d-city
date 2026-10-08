"""Berlin M1: what each building source brings inside the boundary (the LoD2 CityGML solids, the Umweltatlas
Gebäudehöhen footprints, OSM), how they join and line up, how their heights agree (LoD2 measuredHeight, Umweltatlas
hoehe and geschosse, OSM height and building:levels), the towers against the landmark list, the DGM1's range, datum
and pits, and a map of the footprints coloured by the height source each would take.

Run from demos/berlin after 01_osm, 02_lod2, 02_umwelt:  uv run python scripts/m1_sources.py
Writes checks/sources.md, heights_lod2_osm.png, heights_map.png, heights_map_mitte.png, dgm1.png. Loads every
footprint of the boundary from three sources and the DGM1 at 4 m (~2 GB): under the pipeline lock.
"""
import glob
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LightSource  # noqa: E402

from city3d import sources  # noqa: E402
from city3d.common import CHECKS, DATA, LEVEL_H, RAW, UTM, best_match, boundary, districts, height_m, load_osm  # noqa: E402

T0 = time.time()
L = []
poly = boundary().geometry.iloc[0]
dd = districts()
NAMES = list(dd.name)
CANOPY = "51009_1610"           # ALKIS "Überdachung": roofs over petrol stations, platforms, bike stands


def where(g):
    pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=UTM)
    j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
    return j[~j.index.duplicated()]["name"].reindex(g.index)


def inside(g):
    return g[g.geometry.representative_point().within(poly)].copy()


def stats(err):
    err = pd.Series(err).dropna()
    return len(err), err.median(), err.abs().mean(), err.abs().median()


def row(name, a, b):
    ok = a.notna() & b.notna()
    n, med, mae, mad = stats(a[ok] - b[ok])
    r = np.corrcoef(a[ok], b[ok])[0, 1] if n > 2 else np.nan
    return f"| {name} | {n:,} | {med:+.2f} | {mae:.2f} | {mad:.2f} | {r:.3f} |"


# ------------------------------------------------------------------ sources
lod = inside(sources.module("lod2").load())
lod["district"] = where(lod)
lod["area"] = lod.area
uwa = inside(sources.module("umwelt").load())
uwa["district"] = where(uwa)
uwa["area"] = uwa.area
uwa["storeys"] = pd.to_numeric(uwa["geschosse"], errors="coerce").where(lambda s: s > 0)
osm = inside(load_osm())
osm["district"] = where(osm)
osm["area"] = osm.area
parts_path = DATA / "osm_parts.gpkg"
parts = inside(gpd.read_file(parts_path).to_crs(UTM)) if parts_path.exists() else None
if parts is not None:
    parts["h_tag"] = parts["height"].map(height_m) if "height" in parts else np.nan
print(f"loaded in {time.time() - T0:.0f} s: lod2 {len(lod):,} umwelt {len(uwa):,} osm {len(osm):,} "
      f"parts {0 if parts is None else len(parts):,}", flush=True)

# ------------------------------------------------------------------ 1. per district
L += ["# Berlin M1: building sources, coverage, heights, alignment, the DGM1", "",
      f"`scripts/m1_sources.py` ({time.strftime('%Y-%m-%d %H:%M')}). Inside the boundary ({poly.area / 1e6:.2f} km², "
      f"{len(NAMES)} districts: seven Ortsteile and the City West clip of Charlottenburg and Wilmersdorf); a footprint "
      "counts in the district holding its representative point. Sources: Berlin LoD2 CityGML 1.0 (02_lod2, the engine's "
      "citygml adapter: one row per solid, a Building without parts or each BuildingPart; footprint = its GroundSurfaces; "
      "height = `measuredHeight`, the highest roof point over the solid's ground, laser scan 2021), the Umweltatlas "
      "Gebäudehöhen layer (02_umwelt: the same ALKIS footprints in 2D with `hoehe`, `geschosse`, `dachart`, "
      "`funktion`; one row per Gebäude or Gebäudeteil), OSM (01_osm: BBBike extract of 26 Sept 2026 through the local "
      "Overpass). Canopies are ALKIS function 51009_1610 (Überdachung).", "",
      "## 1. Buildings per district and source", "",
      "| District | LoD2 solids | of them parts | canopies | LoD2 ≥ 25 m² (no canopies) | Umweltatlas | with storeys | "
      "OSM buildings | OSM `height` | OSM `building:levels` |", "|---|---|---|---|---|---|---|---|---|---|"]
for d in NAMES + [None]:
    k = (lambda g: g.district == d) if d else (lambda g: pd.Series(True, index=g.index))
    lo, u, o = lod[k(lod)], uwa[k(uwa)], osm[k(osm)]
    big = lo[(lo.area >= 25) & (lo.function != CANOPY)]
    L.append(f"| {d or '**all**'} | {len(lo):,} | {int(lo.part.astype(bool).sum()):,} | {int((lo.function == CANOPY).sum()):,} | "
             f"{len(big):,} | {len(u):,} | {u.storeys.notna().mean():.1%} | {len(o):,} | {o.h_tag.notna().mean():.1%} | "
             f"{o.h_levels.notna().mean():.1%} |")
L += ["", f"Footprint area: LoD2 {lod.area.sum() / 1e6:.2f} km² (no canopies {lod[lod.function != CANOPY].area.sum() / 1e6:.2f}), "
      f"Umweltatlas {uwa.area.sum() / 1e6:.2f} km², OSM {osm.area.sum() / 1e6:.2f} km². Median footprint: LoD2 "
      f"{lod.area.median():.0f} m², Umweltatlas {uwa.area.median():.0f} m², OSM {osm.area.median():.0f} m². "
      f"LoD2 solids under 25 m²: {(lod.area < 25).mean():.0%}. OSM building:part outlines in the boundary: "
      f"{0 if parts is None else len(parts):,}.", "",
      f"LoD2 solids with a `measuredHeight`: {lod.h.notna().mean():.2%}; footprint from the GroundSurfaces on "
      f"{(lod.fp_from == 'ground').mean():.2%} (from the roofs on {int((lod.fp_from == 'roof').sum())}). "
      f"Roof types (AdV code: 1000 flat, 2100 mono-pitch, 3100 gable, 3200 hip, 3500 pyramid, 5000 mixed, 9999 other): "
      + ", ".join(f"{k} {v:,}" for k, v in lod.rooftype.fillna("none").value_counts().items()) + ".",
      f"Umweltatlas roles: " + ", ".join(f"{k} {v:,}" for k, v in uwa.role_txt.value_counts().items()) + "; roof types: "
      + ", ".join(f"{k} {v:,}" for k, v in uwa.dachart_txt.value_counts().head(8).items()) + ".", ""]

# ------------------------------------------------------------------ 2. LoD2 <-> Umweltatlas
# the WFS's Gebäudeteil rows carry their Building's gml_id, the LoD2's BuildingParts ids of their own: join a
# solid to the rows of its key (its parent's id for a part, its own otherwise) and take the one it overlaps most
lod["key"] = np.where(lod.part.astype(bool), lod.parent_id, lod.gml_id)
cand = lod[["key", "h", "area", "geometry", "district", "function"]].reset_index(names="il").merge(
    uwa[["gml_id", "h", "storeys", "area", "funktion_txt", "geometry"]].reset_index(names="iu").rename(
        columns={"gml_id": "key", "h": "h_u", "area": "area_u", "geometry": "geom_u"}), on="key", how="inner")
ga, gb = gpd.GeoSeries(cand.geometry.values, crs=UTM), gpd.GeoSeries(cand.geom_u.values, crs=UTM)
cand["inter"] = ga.intersection(gb).area.values
cand["iou"] = cand.inter / (cand.area + cand.area_u - cand.inter)
mm = cand.sort_values("iou", ascending=False).drop_duplicates("il")
mm = mm[mm.iou > 0.5].copy()
iou = mm.iou.values
dh = mm.h - mm.h_u
lod["h_uwa"] = mm.set_index("il").h_u.reindex(lod.index)
lod["storeys"] = mm.set_index("il").storeys.reindex(lod.index)
L += ["## 2. LoD2 and the Umweltatlas: the same footprints", "",
      "The WFS's Gebäudeteil rows carry their Building's `gml_id` (the LoD2's BuildingParts have ids of their own), so "
      "a solid is joined to the rows of its Building's id and to the one it overlaps most.", "",
      f"- LoD2 solids joined to an Umweltatlas footprint (IoU > 0.5): **{len(mm) / len(lod):.2%}** ({len(mm):,} of "
      f"{len(lod):,}); with the key but no overlap over 0.5: {int(lod.index.isin(cand.il).sum() - len(mm)):,}; key not in "
      f"the WFS: {int((~lod.index.isin(cand.il)).sum()):,}. Umweltatlas rows joined by no solid: "
      f"{int((~uwa.index.isin(mm.iu)).sum()):,}.",
      f"- Footprint IoU of the joined pairs: median {np.median(iou):.4f}, p5 {np.percentile(iou, 5):.3f} "
      f"(the WFS polygons are the LoD2 GroundSurfaces).",
      f"- `hoehe` − `measuredHeight`: median {dh.median():+.3f} m, |p95| {dh.abs().quantile(0.95):.2f} m, "
      f"within 0.05 m on {(dh.abs() <= 0.05).mean():.1%}, within 0.5 m on {(dh.abs() <= 0.5).mean():.1%}; over 1 m on "
      f"{int((dh.abs() > 1).sum()):,} (max {dh.abs().max():.1f} m).", ""]
big = dh.abs() > 1
if big.any():
    L += ["Largest differences (LoD2, Umweltatlas, m):", "",
          "| gml_id | district | LoD2 | Umweltatlas | function |", "|---|---|---|---|---|"]
    for _, r in mm[big].assign(d=dh[big].abs()).sort_values("d", ascending=False).head(8).iterrows():
        L.append(f"| {r.key} | {r.district} | {r.h:.1f} | {r.h_u:.1f} | {r.funktion_txt} |")
    L.append("")

# storeys: metres per storey on the Umweltatlas (hoehe / geschosse), by storey count and by function
uu = uwa[uwa.storeys.notna() & uwa.h.notna() & (uwa.area >= 25)].copy()
uu["mps"] = uu.h / uu.storeys
L += ["## 3. Storeys and metres per storey", "",
      f"Umweltatlas footprints ≥ 25 m² with storeys (`geschosse` > 0): {len(uu):,} of "
      f"{int((uwa.area >= 25).sum()):,} ({len(uu) / max(1, int((uwa.area >= 25).sum())):.1%}). `hoehe` is the highest roof "
      "point (a ridge, a parapet, plant), so hoehe / geschosse is over the true storey height on pitched roofs.", "",
      "| Storeys | n | median hoehe (m) | median m per storey | p25 | p75 |", "|---|---|---|---|---|---|"]
for lo_, hi_ in ((1, 2), (3, 4), (5, 6), (7, 9), (10, 14), (15, 99)):
    s = uu[(uu.storeys >= lo_) & (uu.storeys <= hi_)]
    if len(s):
        L.append(f"| {lo_}–{hi_} | {len(s):,} | {s.h.median():.1f} | {s.mps.median():.2f} | {s.mps.quantile(.25):.2f} | "
                 f"{s.mps.quantile(.75):.2f} |")
L += ["", "By function (the most common, ≥ 25 m²):", "", "| Function | n | median storeys | median m per storey |",
      "|---|---|---|---|"]
for f, s in sorted(uu.groupby("funktion_txt"), key=lambda kv: -len(kv[1]))[:8]:
    L.append(f"| {f} | {len(s):,} | {s.storeys.median():.0f} | {s.mps.median():.2f} |")
ob = osm[osm.h_tag.notna() & osm.h_levels.notna()]
L += ["", f"OSM `height` / `building:levels` on the {len(ob):,} buildings tagged with both: median "
      f"{(ob.h_tag / (ob.h_levels / LEVEL_H)).median():.2f} m (p25 {(ob.h_tag / (ob.h_levels / LEVEL_H)).quantile(.25):.2f}, "
      f"p75 {(ob.h_tag / (ob.h_levels / LEVEL_H)).quantile(.75):.2f}). level_h = {LEVEL_H}.", ""]

# ------------------------------------------------------------------ 4. OSM against LoD2: coverage and offsets
bm = best_match(osm[["geometry"]], lod[["geometry"]], cols=())
bm = bm.set_index("ia")
osm["cover_lod"] = (bm.inter / bm.area_a).reindex(osm.index)
osm["iou_lod"] = bm.iou.reindex(osm.index)
osm["lod_ix"] = bm.ib.reindex(osm.index)
# LoD2 area covered by OSM, per LoD2 solid (an OSM building often holds several LoD2 solids)
cov = gpd.overlay(lod[["geometry"]].reset_index(names="il"), osm[["geometry"]], how="intersection", keep_geom_type=True)
cov["a"] = cov.area
lod_cov = (cov.groupby("il").a.sum() / lod.area.reindex(cov.groupby("il").a.sum().index)).reindex(lod.index).fillna(0)
lod["osm_cover"] = lod_cov
no_osm = lod[(lod.osm_cover < 0.05)]
no_osm_big = no_osm[(no_osm.function != CANOPY) & (no_osm.area >= 25)]
no_lod = osm[osm.cover_lod.fillna(0) < 0.05]
L += ["## 4. OSM against the LoD2: coverage and offsets", "",
      f"- OSM footprints overlapping a LoD2 solid: {(osm.cover_lod.fillna(0) > 0).mean():.1%}; covered ≥ 50 % by the "
      f"best one: {(osm.cover_lod >= .5).mean():.1%}. OSM's outlines are often whole blocks the cadastre splits: "
      f"median LoD2 solids per OSM building {cov.merge(lod[['geometry']].reset_index(names='il'), on='il').shape[0] / max(1, len(osm)):.1f} "
      "(pieces).",
      f"- LoD2 solids no OSM footprint covers (< 5 %): **{len(no_osm):,}** ({no_osm.area.sum() / 1e6:.2f} km²); of them "
      f"canopies {int((no_osm.function == CANOPY).sum()):,}, under 25 m² {int((no_osm.area < 25).sum()):,}; the rest "
      f"{len(no_osm_big):,} ({no_osm_big.area.sum() / 1e6:.2f} km², median {no_osm_big.area.median():.0f} m², height "
      f"p50/p90 {no_osm_big.h.median():.1f}/{no_osm_big.h.quantile(.9):.1f} m) are what OSM lacks.",
      f"- OSM footprints no LoD2 solid covers (< 5 %): **{len(no_lod):,}** ({no_lod.area.sum() / 1e6:.3f} km², median "
      f"{no_lod.area.median():.0f} m²); tags: " + ", ".join(f"{k} {v}" for k, v in no_lod.building.value_counts().head(8).items())
      + f"; with a name {int(no_lod.name.notna().sum())}. Over 200 m²: {int((no_lod.area > 200).sum())} "
      "(built since the cadastre's footprints, or OSM drawing a roof or a structure the cadastre does not hold).", ""]
# offsets: OSM -> LoD2 on near one-to-one pairs (IoU >= 0.7), centroid shifts
pairs = osm[osm.iou_lod >= 0.7]
ca = pairs.geometry.centroid
cb = lod.loc[pairs.lod_ix.astype(int)].geometry.centroid.values
dx = np.array([b.x for b in cb]) - ca.x.values
dy = np.array([b.y for b in cb]) - ca.y.values
L += [f"- Offsets on {len(pairs):,} near one-to-one pairs (IoU ≥ 0.7): LoD2 − OSM centroid median dx {np.median(dx):+.2f} m, "
      f"dy {np.median(dy):+.2f} m, median shift {np.median(np.hypot(dx, dy)):.2f} m (p90 {np.percentile(np.hypot(dx, dy), 90):.2f}); "
      f"IoU median {pairs.iou_lod.median():.3f}. OSM's Berlin outlines are traced from the same cadastre (ALKIS "
      "imports and the official orthophotos), so there is no shift to correct.", ""]
# per-district shift
L += ["| District | pairs | median dx | median dy | median shift |", "|---|---|---|---|---|"]
pd_ = pd.DataFrame({"d": pairs.district.values, "dx": dx, "dy": dy})
for d, s in pd_.groupby("d"):
    L.append(f"| {d} | {len(s):,} | {s.dx.median():+.2f} | {s.dy.median():+.2f} | {np.hypot(s.dx, s.dy).median():.2f} |")
L.append("")

# ------------------------------------------------------------------ 5. heights: LoD2 vs OSM tags
# LoD2 height onto OSM footprints: the tallest LoD2 solid overlapping >= 50 % of itself inside the OSM outline
# (OSM's height tag is the building's top; its building:levels the main body), and by the best match
ov = gpd.overlay(osm[["geometry"]].reset_index(names="io"), lod[["geometry", "h"]].reset_index(names="il"),
                 how="intersection", keep_geom_type=True)
ov["a"] = ov.area
ov["share_l"] = ov.a / lod.area.reindex(ov.il).values
inl = ov[ov.share_l >= 0.5]
osm["h_lod_max"] = inl.groupby("io").h.max().reindex(osm.index)
osm["h_lod_area"] = (inl.assign(ha=inl.h * inl.a).groupby("io").ha.sum() / inl.groupby("io").a.sum()).reindex(osm.index)
L += ["## 5. Height agreement: LoD2 `measuredHeight` against OSM's tags", "",
      "LoD2 on an OSM outline: the tallest LoD2 solid lying ≥ 50 % inside it (the top, as OSM's `height`), and the "
      "area-weighted mean of those solids (the body, as `building:levels`). Error = LoD2 − OSM.", "",
      "| Pair | n | median error (m) | MAE (m) | median abs error (m) | r |", "|---|---|---|---|---|---|",
      row("tallest LoD2 vs `height`", osm.h_lod_max, osm.h_tag)]
for lo_, hi_ in ((0, 10), (10, 20), (20, 50), (50, 100), (100, 999)):
    k = (osm.h_tag >= lo_) & (osm.h_tag < hi_)
    L.append(row(f"tallest LoD2 vs `height` {lo_}–{hi_} m", osm.h_lod_max[k], osm.h_tag[k]))
L.append(row(f"area-weighted LoD2 vs `building:levels` × {LEVEL_H}", osm.h_lod_area, osm.h_levels))
four = osm[osm.h_tag == 4.0]
L.append(row("tallest LoD2 vs `height` other than exactly 4", osm.h_lod_max[osm.h_tag != 4.0], osm.h_tag[osm.h_tag != 4.0]))
for lo_, hi_ in ((1, 3), (4, 5), (6, 7), (8, 12), (13, 99)):
    lv = osm.h_levels / LEVEL_H
    k = (lv >= lo_) & (lv <= hi_)
    L.append(row(f"area-weighted LoD2 vs levels {lo_}–{hi_}", osm.h_lod_area[k], osm.h_levels[k]))
L += ["", f"`height=4` is on {len(four):,} OSM buildings ({four.district.value_counts().idxmax() if len(four) else ''} "
      f"{int((four.district == (four.district.value_counts().idxmax() if len(four) else '')).sum()):,}; tags "
      + ", ".join(f"{k} {v}" for k, v in four.building.value_counts().head(4).items())
      + f"): a bulk edit of small outbuildings; the LoD2 has them at {(osm.h_lod_max[four.index]).median():.1f} m (median). "
      "It is what makes the 0–10 m row's median exactly −1.0."]
lv = osm.h_levels / LEVEL_H
k = osm.h_lod_area.notna() & lv.between(1, 30)
L += [f"LoD2 (area-weighted) / OSM levels on {int(k.sum()):,} buildings: median {(osm.h_lod_area[k] / lv[k]).median():.2f} m "
      "per storey: " + ", ".join(f"{a}–{b}: {(osm.h_lod_area[k & lv.between(a, b)] / lv[k & lv.between(a, b)]).median():.2f}"
                                 for a, b in ((1, 2), (3, 4), (5, 6), (7, 9), (10, 14))) + ".", ""]
worst = osm[osm.h_tag.notna() & osm.h_lod_max.notna()].assign(e=lambda g: g.h_lod_max - g.h_tag)
worst = worst.reindex(worst.e.abs().sort_values(ascending=False).index).head(10)
L += ["Largest disagreements with OSM's `height` (m):", "", "| OSM | name | district | OSM height | tallest LoD2 | lon, lat |",
      "|---|---|---|---|---|---|"]
for i, r in worst.iterrows():
    c = gpd.GeoSeries([r.geometry.representative_point()], crs=UTM).to_crs(4326).iloc[0]
    L.append(f"| {r.osm_id} | {r['name'] if isinstance(r['name'], str) else ''} | {r.district} | {r.h_tag:.1f} | "
             f"{r.h_lod_max:.1f} | {c.x:.5f}, {c.y:.5f} |")
L.append("")

fig, ax = plt.subplots(1, 2, figsize=(11, 5))
k = osm.h_tag.notna() & osm.h_lod_max.notna()
ax[0].scatter(osm.h_tag[k], osm.h_lod_max[k], s=4, alpha=.4)
ax[0].plot([0, 380], [0, 380], "k--", lw=.8)
ax[0].set(xlabel="OSM height (m)", ylabel="tallest LoD2 solid inside (m)", title=f"LoD2 vs OSM height (n {int(k.sum()):,})",
          xscale="log", yscale="log", xlim=(2, 400), ylim=(2, 400))
k = osm.h_levels.notna() & osm.h_lod_area.notna()
ax[1].hexbin(osm.h_levels[k] / LEVEL_H, osm.h_lod_area[k], gridsize=40, extent=(0, 20, 0, 70), mincnt=1, bins="log")
xs = np.arange(0, 21)
ax[1].plot(xs, xs * LEVEL_H, "k--", lw=.8, label=f"levels × {LEVEL_H}")
ax[1].legend()
ax[1].set(xlabel="OSM building:levels", ylabel="LoD2 area-weighted (m)", title=f"LoD2 vs OSM levels (n {int(k.sum()):,})")
fig.tight_layout()
fig.savefig(CHECKS / "heights_lod2_osm.png", dpi=110)
plt.close(fig)
L += ["![LoD2 against OSM](heights_lod2_osm.png)", ""]

# ------------------------------------------------------------------ 6. towers vs the landmark list
lm = pd.read_csv("data/landmarks_berlin.csv")
lm = lm[lm.lat.notna() & lm.height_m.notna()].copy()
lmg = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
lmg = lmg[lmg.within(poly.buffer(50))]


def near_max(g, col, p, r):
    s = g[g.distance(p) <= r]
    return s[col].max() if len(s) else np.nan


def under(g, col, p):
    s = g[g.contains(p)]
    return s[col].max() if len(s) else np.nan


rows_ = []
for _, r in lmg.iterrows():
    p = r.geometry
    rows_.append({"name": r.name_en, "listed": r.height_m, "type": str(r.height_type)[:40], "feature": r.feature,
                  "use": r.use_height, "status": r.status,
                  "lod_under": under(lod, "h", p), "lod_30": near_max(lod, "h", p, 30),
                  "uwa_30": near_max(uwa, "h", p, 30),
                  "osm_30": near_max(osm, "h_tag", p, 30),
                  "part_30": near_max(parts, "h_tag", p, 30) if parts is not None and "h_tag" in parts else np.nan,
                  "lev_30": near_max(osm, "h_levels", p, 30)})
T = pd.DataFrame(rows_)
T["osm_best"] = T[["osm_30", "part_30"]].max(axis=1)
tall = T[(T.listed >= 60) & (T.status.astype(str).str.startswith("completed"))]
L += ["## 6. The towers and landmarks against the landmark list", "",
      f"`data/landmarks_berlin.csv`: {len(T)} rows with a height in the boundary (+50 m), {len(tall)} completed of 60 m or more. "
      "Per row: the LoD2 solid under the point, the tallest LoD2 solid and Umweltatlas footprint within 30 m, OSM's "
      "`height` on outlines and `building:part`s within 30 m, `building:levels` × level_h.", "",
      "| Source (completed rows ≥ 60 m) | within 5 % | within 15 % | with a value |", "|---|---|---|---|"]
for c, lab in (("lod_30", "LoD2 tallest within 30 m"), ("lod_under", "LoD2 under the point"), ("uwa_30", "Umweltatlas within 30 m"),
               ("osm_best", "OSM height / parts within 30 m"), ("lev_30", f"OSM levels × {LEVEL_H}")):
    v = tall[c]
    e = (v - tall.listed).abs() / tall.listed
    L.append(f"| {lab} | {int((e <= .05).sum())} | {int((e <= .15).sum())} | {int(v.notna().sum())} |")
L += ["", "Every row of 60 m or more and the must-have landmarks below it (m; `use` = the list's use_height):", "",
      "| Landmark | listed | height type | use | LoD2 under | LoD2 30 m | Umweltatlas 30 m | OSM 30 m | OSM levels |",
      "|---|---|---|---|---|---|---|---|---|"]
MUST = ("Brandenburg", "Reichstag", "Rotes Rathaus", "Siegess", "Hauptbahnhof", "Oberbaum", "Gedächtnis", "Gedachtnis",
        "Memorial Church", "Berliner Dom", "Berlin Cathedral")


def f1(v):
    return "" if pd.isna(v) else f"{v:.0f}"


show = T[(T.listed >= 60) | T.name.str.contains("|".join(MUST), case=False)].sort_values("listed", ascending=False)
for _, r in show.iterrows():
    L.append(f"| {r['name']} | {r.listed:g} | {r.type} | {r.use} | {f1(r.lod_under)} | {f1(r.lod_30)} | {f1(r.uwa_30)} | "
             f"{f1(r.osm_best)} | {f1(r.lev_30)} |")
L.append("")
miss = tall[((tall.lod_30 - tall.listed).abs() / tall.listed > .15)]
L += [f"Completed rows ≥ 60 m where the LoD2 is more than 15 % off: {len(miss)}: "
      + "; ".join(f"{r['name']} {r.listed:g} (LoD2 {f1(r.lod_30)})" for _, r in miss.iterrows()) + ".", ""]
T.to_csv(DATA / "m1_landmarks_vs_sources.csv", index=False)

# ------------------------------------------------------------------ 7. the DGM1: range, datum, pits
files = sorted(glob.glob(str(RAW / "dgm1" / "dgm1_33_*_2_be_2025.tif")))
srcs = [rasterio.open(f) for f in files]
bx = gpd.GeoSeries([poly], crs=UTM).to_crs(25833).total_bounds
bx = (bx[0] - 4000, bx[1] - 4000, bx[2] + 4000, bx[3] + 4000)
RES = 4.0
arr, tr = merge(srcs, bounds=bx, res=RES, resampling=Resampling.average, nodata=-9999)
for s in srcs:
    s.close()
z = arr[0].astype(np.float32)
z[z <= -9000] = np.nan
from rasterio.features import geometry_mask  # noqa: E402
inb = ~geometry_mask([gpd.GeoSeries([poly], crs=UTM).to_crs(25833).iloc[0]], z.shape, tr)
zi = z[inb & np.isfinite(z)]
L += ["## 7. The DGM1 (1 m bare earth, m above NHN)", "",
      f"81 tiles mosaicked at {RES:g} m (cell means) over the boundary + 4 km: {len(files)} files, "
      f"{np.isfinite(z).mean():.2%} of the box has data (the DGM1 reaches ~250 m into Brandenburg; the box's corners "
      "beyond are the backdrop's).", "",
      f"- Inside the boundary: min {np.nanmin(zi):.1f}, p1 {np.percentile(zi, 1):.1f}, p5 {np.percentile(zi, 5):.1f}, "
      f"median {np.median(zi):.1f}, p95 {np.percentile(zi, 95):.1f}, p99 {np.percentile(zi, 99):.1f}, max {np.nanmax(zi):.1f} m.",
      f"- Boundary + 4 km: min {np.nanmin(z):.1f}, median {np.nanmedian(z):.1f}, max {np.nanmax(z):.1f} m.",
      "- Datum: metres above NHN (DHHN2016), the same as the LoD2's z; the Umweltatlas and LoD2 ground is the DGM10 "
      "at each building (03_compare checks it against this DEM). city.toml `terrain.datum = 30`: the Spree's lower "
      "pool at ~30.6 m comes out near 0.6 m.", ""]
# pits: cells more than 3 m under the median of a 200 m window, below 30 m
from scipy import ndimage  # noqa: E402
zf = np.where(np.isfinite(z), z, np.nanmedian(z))
med = ndimage.median_filter(zf[::4, ::4], size=13)            # 16 m cells, 208 m window
med = np.kron(med, np.ones((4, 4)))[: z.shape[0], : z.shape[1]]
pit = np.isfinite(z) & (z < 30.0) & (z < med - 3)
lab, n = ndimage.label(pit)
L += [f"- Pits (cells under 30 m and over 3 m below their 200 m surroundings' median), boundary + 4 km: {n} "
      f"patches, {pit.sum() * RES * RES / 1e4:.1f} ha. The five deepest:", "",
      "| lon, lat | lowest (m) | surroundings (m) | area (ha) |", "|---|---|---|---|"]
if n:
    mins = ndimage.minimum(z, lab, index=np.arange(1, n + 1))
    sizes = ndimage.sum(pit, lab, index=np.arange(1, n + 1))
    for i in np.argsort(mins)[:5]:
        rr, cc = np.argwhere(lab == i + 1)[np.argmin(z[lab == i + 1])]
        x, y = rasterio.transform.xy(tr, rr, cc)
        c = gpd.GeoSeries(gpd.points_from_xy([x], [y]), crs=25833).to_crs(4326).iloc[0]
        L.append(f"| {c.x:.4f}, {c.y:.4f} | {mins[i]:.1f} | {med[rr, cc]:.1f} | {sizes[i] * RES * RES / 1e4:.2f} |")
L.append("")


def sample(lon, lat):
    p = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(25833).iloc[0]
    rr, cc = rasterio.transform.rowcol(tr, p.x, p.y)
    return z[rr, cc] if 0 <= rr < z.shape[0] and 0 <= cc < z.shape[1] else np.nan


# the water levels: the DGM1 over OSM's water polygons (rivers and canals), eroded 6 m from their banks
from city3d.common import element_geoms, overpass  # noqa: E402
w_, s_, e_, n_ = gpd.GeoSeries([poly], crs=UTM).to_crs(4326).total_bounds
res = overpass(f"""[out:json][timeout:300];
    (way["natural"="water"]({s_},{w_},{n_},{e_}); rel["natural"="water"]({s_},{w_},{n_},{e_}););
    out geom;""")
wrows = []
for el in res["elements"]:
    t = el.get("tags", {})
    if el["type"] == "way":
        pts = [(p_["lon"], p_["lat"]) for p_ in el.get("geometry", [])]
        if len(pts) >= 4:
            from shapely.geometry import Polygon as _P  # noqa: E402
            wrows.append({"name": t.get("name", ""), "water": t.get("water", ""), "geometry": _P(pts)})
    else:
        from shapely.geometry import LineString as _LS  # noqa: E402
        from shapely.ops import polygonize as _pz, unary_union as _uu  # noqa: E402
        outs = [_LS([(p_["lon"], p_["lat"]) for p_ in m_["geometry"]]) for m_ in el.get("members", [])
                if m_.get("role") == "outer" and "geometry" in m_]
        if outs:
            wrows.append({"name": t.get("name", ""), "water": t.get("water", ""), "geometry": _uu(list(_pz(_uu(outs))))})
wat = gpd.GeoDataFrame(wrows, crs=4326).to_crs(25833)
wat["geometry"] = wat.geometry.make_valid()
wat = wat[wat.water.isin(["river", "canal", "basin", "lock", ""]) | wat.name.str.contains("Spree|kanal|Kanal|Hafen")]
wat = wat[wat.intersects(gpd.GeoSeries([poly], crs=UTM).to_crs(25833).iloc[0])]
L += ["Water levels (DGM1 at 4 m over OSM's `natural=water` polygons in the boundary, 6 m in from their banks; the DGM1 "
      "holds a level water surface):", "", "| Water | type | cells | median (m) | p10 | p90 |", "|---|---|---|---|---|---|"]
for nm, grp in wat.assign(nm=wat.name.replace("", "(unnamed)")).groupby("nm"):
    geom = grp.geometry.union_all().buffer(-6)
    if geom.is_empty:
        continue
    mk = ~geometry_mask([geom], z.shape, tr) & np.isfinite(z)
    if mk.sum() < 20:
        continue
    v = z[mk]
    L.append(f"| {nm} | {', '.join(sorted(set(grp.water) - {''})) or 'water'} | {mk.sum():,} | {np.median(v):.2f} | "
             f"{np.percentile(v, 10):.2f} | {np.percentile(v, 90):.2f} |")
L.append("")

# the rise from the Spree to the Barnim plateau (Prenzlauer Berg), and to the Teltow (Kreuzberg)
prof = [("Spree at Museum Island", 13.4008, 52.5153), ("Alexanderplatz", 13.4130, 52.5219),
        ("Rosa-Luxemburg-Platz", 13.4110, 52.5270), ("Senefelderplatz", 13.4123, 52.5325),
        ("Kollwitzplatz", 13.4174, 52.5360), ("Prenzlauer Allee / Danziger", 13.4240, 52.5400),
        ("Spree at Oberbaumbrücke", 13.4462, 52.5014), ("Mehringdamm (Yorckstraße)", 13.3880, 52.4920),
        ("Kreuzberg summit", 13.38152, 52.48774), ("Tempelhof airfield edge", 13.3950, 52.4800)]
L += ["Profile (DGM1 at 4 m): " + "; ".join(f"{n} {sample(lo, la):.1f}" for n, lo, la in prof) + " m. The Spree valley "
      "(Berliner Urstromtal) lies at 32–36 m; the Barnim plateau rises to ~50 m north of Senefelderplatz, the Teltow "
      "plateau ~50 m south of Kreuzberg, with the Kreuzberg's summit above it.", ""]

ls = LightSource(azdeg=315, altdeg=45)
fig, ax = plt.subplots(figsize=(10, 7.5))
zz = np.where(np.isfinite(z), z, np.nan)
rgb = ls.shade(np.nan_to_num(zz, nan=np.nanmin(zz)), cmap=plt.cm.terrain, vert_exag=6, blend_mode="soft",
               vmin=25, vmax=90)
ext = (tr.c, tr.c + tr.a * z.shape[1], tr.f + tr.e * z.shape[0], tr.f)
ax.imshow(rgb, extent=ext)
gpd.GeoSeries([poly], crs=UTM).to_crs(25833).boundary.plot(ax=ax, color="k", lw=1)
pr, pc = np.nonzero(pit)
if len(pr):
    xs_, ys_ = rasterio.transform.xy(tr, pr, pc)
    ax.scatter(xs_, ys_, s=1, c="m", label="pits (< 30 m, 3 m under the surroundings)")
    ax.legend(loc="lower right")
sm = plt.cm.ScalarMappable(cmap=plt.cm.terrain, norm=plt.Normalize(25, 90))
fig.colorbar(sm, ax=ax, label="m above NHN", shrink=.7)
ax.set(title="Berlin DGM1 (4 m means), boundary + 4 km; black: the boundary", xlabel="E (EPSG:25833)", ylabel="N")
fig.tight_layout()
fig.savefig(CHECKS / "dgm1.png", dpi=110)
plt.close(fig)
L += ["![DGM1](dgm1.png)", ""]

# ------------------------------------------------------------------ 8. the map: footprints by height source
# the source each footprint would take with city.toml's order: LoD2 solids (their own measuredHeight); OSM where no
# LoD2 solid covers it (fill): its height tag, levels, or the default
lod["src"] = np.where(lod.h.notna(), "LoD2 measuredHeight", "LoD2 without height")
nl = no_lod.copy()
nl["src"] = np.select([nl.h_tag.notna(), nl.h_levels.notna()], ["OSM height", "OSM levels"], "default")
mp = pd.concat([lod[["geometry", "src"]], nl[["geometry", "src"]]], ignore_index=True)
COL = {"LoD2 measuredHeight": "#4c78a8", "LoD2 without height": "#9ecae9", "OSM height": "#e45756",
       "OSM levels": "#f58518", "default": "#222222"}
counts = mp.src.value_counts()
L += ["## 8. Footprints by height source", "",
      "The source each footprint takes in city.toml's order (LoD2 primary; OSM where no LoD2 solid covers 5 % of it): "
      + ", ".join(f"{k} {counts.get(k, 0):,}" for k in COL) + ".", "",
      "![heights by source](heights_map.png)", "", "![Mitte detail](heights_map_mitte.png)", ""]
for fname, box_ in (("heights_map.png", None), ("heights_map_mitte.png", (13.383, 52.510, 13.418, 52.525))):
    fig, ax = plt.subplots(figsize=(14, 9) if box_ is None else (12, 8))
    dd.boundary.plot(ax=ax, color="k", lw=.6)
    sub = mp
    if box_:
        bb = gpd.GeoSeries(gpd.points_from_xy([box_[0], box_[2]], [box_[1], box_[3]]), crs=4326).to_crs(UTM)
        x0, y0, x1, y1 = bb.x.min(), bb.y.min(), bb.x.max(), bb.y.max()
        sub = mp.cx[x0:x1, y0:y1]
    for k_, c in COL.items():
        s = sub[sub.src == k_]
        if len(s):
            s.plot(ax=ax, color=c, linewidth=0, label=f"{k_} ({counts.get(k_, 0):,})")
    if box_:
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
    from matplotlib.patches import Patch  # noqa: E402
    ax.legend(handles=[Patch(color=c, label=f"{k_} ({counts.get(k_, 0):,})") for k_, c in COL.items()], loc="lower left")
    ax.set_title("Berlin M1: footprints by height source" + (" (Mitte: Museum Island to Alexanderplatz)" if box_ else
                 "; black: the districts"))
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(CHECKS / fname, dpi=130 if box_ is None else 110)
    plt.close(fig)

L.append(f"({time.time() - T0:.0f} s)")
(CHECKS / "sources.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
