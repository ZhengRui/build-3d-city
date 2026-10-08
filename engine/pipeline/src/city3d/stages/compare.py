"""03_compare: check a footprint source with heights (the first in [sources] footprints besides OSM: GBA in
Shenzhen, NYC's official footprints in Manhattan) against OSM, and against the CNBH-10m height raster when the
city uses it (sources cnbh).

Answers, in order:
  1. Alignment: do the source's footprints sit on OSM's, or are they shifted (e.g. GCJ-02)?
  2. Coverage: counts and footprint area, overall and per 1 km cell.
  3. Heights: the source (and CNBH-10m) against OSM-tagged heights, overall and by height band, and the source
     against CNBH on every building.

CNBH-10m (Zenodo 7923866, CC BY 4.0) is a 10 m raster; a footprint's CNBH height is the median of
the pixels it covers, or the pixel under its centroid when it covers none.

Writes figures and report.md to the city's checks/. Run it for every new city before designing the building
table.
"""
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

from .. import sources
from ..common import CFG, CHECKS, CITY as CITY_DIR, DATA, DISTRICTS, LEVEL_H, UTM, best_match, boundary, load_osm

# the source compared: the first footprint source besides OSM that carries heights
SRC = next(n for n in CFG["sources"]["footprints"] if n != "osm" and sources.module(n).HEIGHTS)
LABEL = getattr(sources.module(SRC), "LABEL", None) or {"gba": "GBA", "arcgis": "official"}.get(SRC, SRC)
# every footprint source with heights: with more than one, sources_checks() compares them all (Paris: APUR,
# BD TOPO and OSM)
OFFICIAL = [n for n in CFG["sources"]["footprints"] if n != "osm" and sources.module(n).HEIGHTS]
RASTER = "cnbh" in CFG["sources"]["heights"]
BANDS = [(0, 15), (15, 30), (30, 60), (60, 1e9)]

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = CHECKS
OUT.mkdir(exist_ok=True)
# the footprint close-up: lon, lat and name of a place to eyeball alignment at (default: the districts' centre)
DETAIL = CFG["compare"]["detail"]


def load():
    b = boundary()
    osm, gba = load_osm(), sources.module(SRC).load()
    for g in (osm, gba):
        g["h_cnbh"] = sources.module("cnbh").sample(g) if RASTER else np.nan
    return b, osm, gba


def offset(ref: gpd.GeoDataFrame, other: gpd.GeoDataFrame, n=4000, seed=0):
    """Median displacement of other relative to ref, from nearest centroids of big buildings."""
    big = ref.area > 400
    r = ref[big].sample(min(n, big.sum()), random_state=seed)
    rc = gpd.GeoDataFrame(geometry=r.centroid, crs=UTM)
    oc = gpd.GeoDataFrame(geometry=other[other.area > 400].centroid, crs=UTM)
    j = gpd.sjoin_nearest(rc, oc, max_distance=800, distance_col="d")
    o = oc.geometry.loc[j.index_right].reset_index(drop=True)
    rr = j.geometry.reset_index(drop=True)
    return (o.x - rr.x).median(), (o.y - rr.y).median(), j["d"].median()


def err_row(name, ref, est):
    ok = ref.notna() & est.notna()
    e = est[ok] - ref[ok]
    return (f"| {name} | {ok.sum():,} | {e.median():+.1f} | {e.abs().median():.1f} | "
            f"{np.sqrt((e ** 2).mean()):.1f} | {ref[ok].corr(est[ok]):.2f} |")


def grid(b, g, col, cell=1000):
    x0, y0, x1, y1 = b.total_bounds
    nx, ny = int((x1 - x0) // cell) + 1, int((y1 - y0) // cell) + 1
    c = g.centroid
    ix = ((c.x - x0) // cell).astype(int).clip(0, nx - 1)
    iy = ((c.y - y0) // cell).astype(int).clip(0, ny - 1)
    cnt = np.zeros((ny, nx))
    np.add.at(cnt, (iy, ix), 1)
    h90 = np.full((ny, nx), np.nan)
    df = pd.DataFrame({"ix": ix, "iy": iy, "h": g[col]}).dropna()
    for (yy, xx), v in df.groupby(["iy", "ix"])["h"].quantile(0.9).items():
        h90[yy, xx] = v
    return cnt, h90, (x0, x0 + nx * cell, y0, y0 + ny * cell)


def extra_checks(osm, gba, pair) -> list:
    """What an official source compared with OSM needs beyond the summary: whether OSM is an independent
    reference at all (NYC's OSM buildings are an import of the same data), the disagreements that matter,
    OSM's building:part massing against the footprints, suspicious heights, and ground elevations."""
    L = ["## 4. What the agreement means, and where they differ", ""]
    same = (pair.osm - pair.gba).abs() <= 0.1
    L += [f"{same.mean():.1%} of the {len(pair):,} matched pairs agree within 10 cm: where that share is high "
          "OSM's heights are a copy of this source (NYC's were imported from it in 2013-14), and the agreement "
          "is no evidence. On the other pairs:", ""]
    d = pair[~same]
    if len(d):
        L += ["| Estimate vs OSM, differing pairs | n | median error (m) | median abs error (m) | RMSE (m) | correlation |",
              "|---|---|---|---|---|---|", err_row(LABEL, d.osm, d.gba), ""]
    # largest disagreements
    m = best_match(osm[osm["h"].notna()], gba, cols=("h",))
    m = m[m.iou > 0.3].assign(d=lambda x: x.h_b - x.h_a)
    top = m.reindex(m.d.abs().sort_values(ascending=False).index).head(30)
    cols = ["name"] + [c for c in ("bin", "construction_year", "feature_code", "n_sq_eb", "cleabs") if c in gba]
    L += [f"The 30 largest disagreements ({LABEL} − OSM), IoU > 0.3; `reconcile` in 04_buildings takes the taller "
          "where OSM is taller by more than max(20 m, 30 %):", "",
          f"| OSM name | {' | '.join(cols[1:])} | {LABEL} h | OSM h | Δ (m) |", "|---" * (len(cols) + 3) + "|"]
    for r in top.itertuples():
        o = osm.loc[r.ia]
        gg = gba.loc[r.ib]
        L.append(f"| {o['name'] if pd.notna(o['name']) else ''} | "
                 + " | ".join(str(gg[c]) for c in cols[1:]) + f" | {r.h_b:.0f} | {r.h_a:.0f} | {r.d:+.0f} |")
    L.append("")
    # OSM parts against the footprints
    f = DATA / "osm_parts.gpkg"
    if f.exists():
        parts = gpd.read_file(f).to_crs(UTM)
        parts = parts[parts.get("part", pd.Series(index=parts.index)).ne("no")]
        from ..common import height_m
        parts["ph"] = parts["height"].map(height_m)
        ov = gpd.overlay(parts[["geometry"]].reset_index(names="ip"), gba[["geometry"]].reset_index(names="ib"),
                         how="intersection", keep_geom_type=True)
        ov["a"] = ov.area
        ov = ov.sort_values("a", ascending=False).drop_duplicates("ip")
        cover = ov.groupby("ib").a.sum() / gba.area.reindex(ov.ib.unique())
        pmax = ov.assign(ph=parts["ph"].loc[ov.ip].values).groupby("ib").ph.max()
        dh = (pmax - gba["h"].reindex(pmax.index)).dropna()
        L += ["## 5. OSM building parts against the footprints", "",
              f"{len(parts):,} building:part outlines ({parts.ph.notna().sum():,} with a height) fall on "
              f"{len(cover):,} {LABEL} footprints; they cover ≥ 30 % of {int((cover >= 0.3).sum()):,} of them "
              f"(04_buildings then builds those from their parts), ≥ 80 % of {int((cover >= 0.8).sum()):,}. "
              f"Tallest part − footprint height: median {dh.median():+.1f} m, within 5 m for {(dh.abs() <= 5).mean():.0%} "
              f"(spires and masts are parts above the roof).", ""]
        tall = gba[(gba.area > 3000) & (gba.h > 120)]
        lone = tall[~tall.index.isin(cover[cover >= 0.3].index)]
        L += [f"Footprints over 3,000 m² and 120 m (a tower and its podium drawn as one?) without parts: "
              f"{len(lone):,} of {len(tall):,}: " + ", ".join(
                  f"{r['name'] if pd.notna(r.get('name')) else r.get('bin', '')} ({r.h:.0f} m, {r.geometry.area:,.0f} m²)"
                  for _, r in lone.nlargest(15, "h").iterrows()) + ".", ""]
    # suspicious heights
    flat = gba[(gba.h < 2) & (gba.area > 300)]
    L += ["## 6. Suspicious heights", "",
          f"- under 2 m on more than 300 m²: {len(flat):,} (04_buildings takes OSM's height there, if any)",
          f"- no height: {int(gba.h.isna().sum()):,}"]
    if "feature_code" in gba:
        L.append(f"- under construction (feature code 5100): {int((gba.feature_code == 5100).sum()):,}")
    L.append("")
    if "ground_elevation" in gba:
        from . import terrain as t05
        from rasterio.warp import Resampling
        pts = gba.geometry.representative_point()
        g0 = pd.to_numeric(gba["ground_elevation"], errors="coerce") * CFG["sources"].get(SRC, {}).get("height_scale", 1.0)
        x0, y0, x1, y1 = gba.total_bounds
        _, _, nx, nz, tr = t05.scene_grid((0.0, 0.0), (x0, y0, x1, y1), 10.0)
        dtm = t05.dem_on(tr, (nz, nx), Resampling.bilinear, sources.module(CFG["sources"]["dem"]).tiles())
        c, r = ~tr * (pts.x.values, pts.y.values)
        v = dtm[np.clip(np.asarray(r, int), 0, nz - 1), np.clip(np.asarray(c, int), 0, nx - 1)]
        e = pd.Series(g0.values - v)[g0.values > 0].dropna()
        q = np.percentile(e, [10, 50, 90])
        L += ["## 7. Ground elevation", "",
              f"{LABEL}'s ground elevation at each building less the DEM ({CFG['sources']['dem']}) there, "
              f"{len(e):,} buildings: median {q[1]:+.2f} m, p10 {q[0]:+.2f}, p90 {q[2]:+.2f}: an independent check "
              "of the footprints' position and the DEM's datum.", ""]
    return L


def main():
    b, osm, gba = load()
    poly = b.geometry.iloc[0]
    osm, gba = osm[osm.intersects(poly)], gba[gba.intersects(poly)]
    ids = ", ".join(str(i if isinstance(i, int) else f"{i['relation']} (clipped)") for i in DISTRICTS.values())
    L = [f"# {CFG['title']} building data check", "",
         f"District boundary: OSM relation{'s' if len(DISTRICTS) > 1 else ''} {ids}, {poly.area / 1e6:.1f} km² "
         f"(admin boundaries may include some sea).", ""]

    # 1. alignment
    # GBA copies some footprints from OSM (source == "osm"); only a source's own ones test alignment
    dx, dy, d = offset(osm, gba[gba["source"] != "osm"])
    L += [f"## 1. Alignment of {LABEL} against OSM", "",
          f"Median shift of {LABEL}'s own (non-OSM) centroids from OSM (buildings > 400 m²): "
          f"dx {dx:+.1f} m, dy {dy:+.1f} m; "
          f"median nearest-centroid distance {d:.1f} m. A systematic offset (a wrong datum or projection, such as "
          "China's GCJ-02 at 300–500 m) would show here; where OSM copied this source (§4) agreement is expected.", ""]

    # 2. coverage
    rows = [("OSM", osm, "h"), (LABEL, gba, "h")] + ([(f"CNBH under {LABEL} footprints", gba, "h_cnbh")] if RASTER else [])
    L += ["## 2. Coverage inside the boundary", "",
          f"{LABEL} footprint sources: {gba['source'].value_counts().to_dict()}.", "",
          "| Source | buildings | footprint km² | with height | height p50 / p90 / max (m) |",
          "|---|---|---|---|---|"]
    for name, g, col in rows:
        h = g[col]
        q = h.quantile([0.5, 0.9]).round(1).tolist()
        L.append(f"| {name} | {len(g):,} | {g.area.sum() / 1e6:.1f} | "
                 f"{h.notna().sum():,} ({h.notna().mean():.0%}) | {q[0]} / {q[1]} / {h.max():.0f} |")
    m = best_match(osm, gba)
    L += ["", f"{(m.iou > 0.5).sum():,} of {len(osm):,} OSM footprints have a {LABEL} footprint with IoU > 0.5 "
          f"(median best IoU {m.iou.median():.2f}); {len(osm) - len(m):,} have no overlapping {LABEL} footprint.", ""]
    mb = best_match(gba, osm, cols=())
    L += [f"{len(gba) - len(mb):,} of {len(gba):,} {LABEL} footprints overlap no OSM footprint "
          f"({gba.area[~gba.index.isin(mb.ia)].sum() / 1e6:.2f} km²).", ""]

    # 3. heights
    ref = osm[osm["h"].notna()]
    mm = best_match(ref, gba)
    mm = mm[mm.iou > 0.3]
    pair = pd.DataFrame({"osm": mm.h_a.values, "gba": mm.h_b.values,
                         "cnbh": ref.loc[mm.ia.values, "h_cnbh"].values,
                         "tagged": ref.loc[mm.ia.values, "h_tag"].notna().values})
    L += ["## 3. Heights", "",
          f"Reference: {len(ref):,} OSM buildings with `height` ({ref.h_tag.notna().sum()}) or "
          f"`building:levels` × {LEVEL_H} m. {len(pair):,} of them match a {LABEL} footprint (IoU > 0.3).", "",
          "| Estimate vs OSM | n | median error (m) | median abs error (m) | RMSE (m) | correlation |",
          "|---|---|---|---|---|---|",
          err_row(LABEL, pair.osm, pair.gba)] + ([err_row("CNBH-10m", pair.osm, pair.cnbh)] if RASTER else [])
    for lo, hi in BANDS:
        band = pair[(pair.osm >= lo) & (pair.osm < hi)]
        tag = f"OSM {lo}–{hi:.0f} m" if hi < 1e9 else f"OSM ≥ {lo} m"
        L.append(err_row(f"{LABEL}, {tag}", band.osm, band.gba))
        if RASTER:
            L.append(err_row(f"CNBH-10m, {tag}", band.osm, band.cnbh))
    L.append("")
    both = gba[gba.h.notna() & gba.h_cnbh.notna()]
    if RASTER:
        e = both.h - both.h_cnbh
        L += [f"{LABEL} vs CNBH on all {len(both):,} {LABEL} buildings with both: median {LABEL} − CNBH "
              f"{e.median():+.1f} m, median abs difference {e.abs().median():.1f} m, correlation "
              f"{both.h.corr(both.h_cnbh):.2f}.", ""]

    panels = [(pair.osm, pair.gba, "OSM height (m)", f"{LABEL} height (m)", f"{LABEL} vs OSM")]
    if RASTER:
        panels += [(pair.osm, pair.cnbh, "OSM height (m)", "CNBH-10m height (m)", "CNBH vs OSM"),
                   (both.h_cnbh, both.h, "CNBH-10m height (m)", f"{LABEL} height (m)", f"{LABEL} vs CNBH, all buildings")]
    top = max(250, float(np.nanpercentile(pair.osm, 99.9)) if len(pair) else 250)
    fig, ax = plt.subplots(1, len(panels), figsize=(5.4 * len(panels), 5.2), squeeze=False)
    for a, (x, y, xl, yl, t) in zip(ax[0], panels):
        a.scatter(x, y, s=2 if len(x) > 5000 else 5, alpha=0.25 if len(x) > 5000 else 0.5)
        a.plot([0, top], [0, top], "k--", lw=0.8)
        a.set(xlabel=xl, ylabel=yl, title=f"{t} (n={len(x):,})", xlim=(0, top), ylim=(0, top))
    fig.tight_layout()
    fig.savefig(OUT / "heights_scatter.png", dpi=110)
    L += ["![heights](heights_scatter.png)", ""]

    # maps
    cols = [("OSM", osm, "h"), (LABEL, gba, "h")] + ([(f"CNBH under {LABEL}", gba, "h_cnbh")] if RASTER else [])
    fig, axes = plt.subplots(2, len(cols), figsize=(5.4 * len(cols), 11), squeeze=False)
    for col, (name, g, hc) in enumerate(cols):
        cnt, h90, ext = grid(b, g, hc)
        for row, (arr, title, cmap, vmax) in enumerate(
                [(np.where(cnt == 0, np.nan, cnt), "buildings per km²", "viridis", 800),
                 (h90, "90th-percentile height per km² (m)", "magma", max(120, float(np.nanmax(h90)) // 50 * 50))]):
            a = axes[row, col]
            im = a.imshow(arr, origin="lower", extent=ext, cmap=cmap, vmin=0, vmax=vmax)
            b.boundary.plot(ax=a, color="k", lw=0.6)
            a.set_title(f"{name}: {title}")
            a.set_xticks([]), a.set_yticks([])
            fig.colorbar(im, ax=a, shrink=0.7)
    fig.tight_layout()
    fig.savefig(OUT / "coverage_maps.png", dpi=100)
    L += ["![coverage](coverage_maps.png)", ""]

    # footprint close-up near DETAIL to eyeball alignment and shape quality
    if DETAIL:
        (lon, lat, place) = DETAIL
        cx, cy = gpd.GeoSeries.from_xy([lon], [lat], crs="EPSG:4326").to_crs(UTM).iloc[0].coords[0]
    else:
        place = "the districts' centre"
        cx, cy = poly.centroid.x, poly.centroid.y
    fig, a = plt.subplots(figsize=(9, 9))
    for name, g, color in (("OSM", osm, "k"), (LABEL, gba, "tab:blue")):
        g.cx[cx - 600:cx + 600, cy - 600:cy + 600].boundary.plot(ax=a, color=color, lw=0.8, label=name)
    a.set_xlim(cx - 600, cx + 600), a.set_ylim(cy - 600, cy + 600)
    a.legend(), a.set_title(f"Footprints near {place} (1.2 km square)")
    a.set_xticks([]), a.set_yticks([])
    fig.savefig(OUT / "footprints_detail.png", dpi=110)
    L += ["![detail](footprints_detail.png)", ""]

    L += extra_checks(osm, gba, pair)
    if len(OFFICIAL) > 1:
        del gba
        L += sources_checks(osm)
    (OUT / "report.md").write_text("\n".join(L))
    print("\n".join(L))



# ---------------------------------------------------------------- several official sources

def label(n: str) -> str:
    return "OSM" if n == "osm" else (getattr(sources.module(n), "LABEL", None) or n)


def pair_offset(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> dict:
    """How far b's footprints sit from a's: over pairs that are clearly the same building (IoU > 0.7, over
    100 m²), the median centroid shift and distance, and the IoU (a shift of s metres on a building of width
    w costs about 2 s / w of it)."""
    m = best_match(a[a.area > 100], b[b.area > 100], cols=())
    m = m[m.iou > 0.7]
    ca, cb = a.centroid.loc[m.ia].values, b.centroid.loc[m.ib].values
    dx, dy = np.array([p.x for p in cb]) - np.array([p.x for p in ca]), np.array([p.y for p in cb]) - np.array([p.y for p in ca])
    d = np.hypot(dx, dy)
    return {"n": len(m), "dx": np.median(dx), "dy": np.median(dy), "d50": np.median(d), "d90": np.percentile(d, 90),
            "iou": m.iou.median()}


def sources_checks(osm: gpd.GeoDataFrame) -> list:
    """With more than one official footprint source: coverage per district, alignment and height agreement
    between every pair, the landmark list against each, and what none of them has."""
    poly = boundary().geometry.iloc[0]
    srcs = {n: sources.module(n).load() for n in OFFICIAL}
    srcs = {n: g[g.intersects(poly)] for n, g in srcs.items()}
    allg = {"osm": osm, **srcs}
    names = list(allg)
    from ..common import districts
    dd = districts()
    L = ["## 8. Every source, district by district", "",
         "Footprints counted in the district holding their representative point; OSM with a height: `height` or "
         f"`building:levels` (× {LEVEL_H} m).", "",
         "| District | " + " | ".join(f"{label(n)} buildings | {label(n)} km²" for n in names) + " | OSM with height |",
         "|---" * (1 + 2 * len(names) + 1) + "|"]
    where = {}
    for n, g in allg.items():
        pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=UTM)
        j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
        where[n] = j[~j.index.duplicated()]["name"].reindex(g.index)
    tot = {n: [0, 0.0] for n in names}
    for d in dd.name:
        cells = []
        for n, g in allg.items():
            k = where[n] == d
            cells += [f"{int(k.sum()):,}", f"{g.area[k].sum() / 1e6:.2f}"]
            tot[n][0] += int(k.sum())
            tot[n][1] += g.area[k].sum() / 1e6
        ko = where["osm"] == d
        cells.append(f"{osm['h'][ko].notna().mean():.0%}" if ko.any() else "")
        L.append(f"| {d} | " + " | ".join(cells) + " |")
    L.append("| **all** | " + " | ".join(f"**{tot[n][0]:,}** | **{tot[n][1]:.2f}**" for n in names)
             + f" | **{osm['h'].notna().mean():.0%}** |")
    L.append("")

    # alignment
    L += ["## 9. Alignment between the sources", "",
          "Pairs that are clearly the same building (IoU > 0.7, both over 100 m²): median shift of the second's "
          "centroid from the first's, the median and 90th-percentile distance, and the median IoU.", "",
          "| First | second | pairs | dx (m) | dy (m) | distance p50 / p90 (m) | IoU p50 |", "|---|---|---|---|---|---|---|"]
    for i, a in enumerate(names):
        for bn in names[i + 1:]:
            o = pair_offset(allg[a], allg[bn])
            if o["n"]:
                L.append(f"| {label(a)} | {label(bn)} | {o['n']:,} | {o['dx']:+.2f} | {o['dy']:+.2f} | "
                         f"{o['d50']:.2f} / {o['d90']:.2f} | {o['iou']:.2f} |")
    L.append("")

    # heights, pair by pair and by band
    L += ["## 10. Height agreement between the sources", "",
          "Matched footprints (IoU > 0.5); bands by the first source's height. For OSM, `height` where tagged, "
          f"else levels × {LEVEL_H} m.", "",
          "| First (reference) | second | band | n | median Δ (m) | median abs Δ (m) | RMSE (m) | correlation |",
          "|---|---|---|---|---|---|---|---|"]
    pairs = []
    order = [n for n in names if n != "osm"] + ["osm"]
    for i, a in enumerate(order):
        for bn in order[i + 1:]:
            ga, gb = allg[a], allg[bn]
            ga, gb = ga[ga["h"].notna()], gb[gb["h"].notna()]
            m = best_match(ga, gb)
            m = m[m.iou > 0.5]
            pairs.append((a, bn, m))
            for lo, hi in [(0, 1e9)] + BANDS:
                k = (m.h_a >= lo) & (m.h_a < hi)
                if k.sum() < 3:
                    continue
                e = m.h_b[k] - m.h_a[k]
                band = "all" if hi >= 1e9 and lo == 0 else (f"{lo}–{hi:.0f} m" if hi < 1e9 else f"≥ {lo} m")
                L.append(f"| {label(a)} | {label(bn)} | {band} | {int(k.sum()):,} | {e.median():+.2f} | "
                         f"{e.abs().median():.2f} | {np.sqrt((e ** 2).mean()):.1f} | {m.h_a[k].corr(m.h_b[k]):.2f} |")
    fig, ax = plt.subplots(1, len(pairs), figsize=(5.2 * len(pairs), 5.2), squeeze=False)
    for axis, (a, bn, m) in zip(ax[0], pairs):
        axis.scatter(m.h_a, m.h_b, s=1.5, alpha=0.25)
        axis.plot([0, 250], [0, 250], "k--", lw=0.8)
        axis.set(xlabel=f"{label(a)} height (m)", ylabel=f"{label(bn)} height (m)", xlim=(0, 250), ylim=(0, 250),
                 title=f"{label(bn)} vs {label(a)} (n={len(m):,})")
    fig.tight_layout()
    fig.savefig(OUT / "heights_sources.png", dpi=100)
    L += ["", "![heights between sources](heights_sources.png)", ""]

    # landmarks
    import glob
    from shapely.geometry import Point
    files = sorted(glob.glob(str(CITY_DIR / CFG["paths"]["landmarks"])))
    if files:
        lm = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).dropna(subset=["lat", "lon", "height_m"])
        pts = gpd.GeoDataFrame(lm, geometry=[Point(xy) for xy in zip(lm.lon, lm.lat)], crs="EPSG:4326").to_crs(UTM)
        pts = pts[pts.within(poly.buffer(50))]
        L += [f"## 11. The landmark list against each source ({len(pts)} rows in the districts)", "",
              "The height of the footprint under the landmark's point (else the nearest within 25 m; blank: none), "
              "before 04_buildings applies the list. The list's height is its `height_type` (roof, architectural, "
              "tip); `use` false rows are structures or monuments whose height the list does not impose.", "",
              "| Landmark | list (m) | type | use | " + " | ".join(label(n) for n in names) + " |",
              "|---|---|---|---|" + "---|" * len(names)]
        got = {}
        for n, g in allg.items():
            j = gpd.sjoin_nearest(pts[["geometry"]], g[["geometry", "h"]], max_distance=25, distance_col="d")
            j = j.sort_values("d").loc[lambda x: ~x.index.duplicated()]
            got[n] = j["h"].reindex(pts.index)
            got[n + "_hit"] = pd.Series(True, index=j.index).reindex(pts.index).fillna(False)
        miss = []
        for i, r in pts.sort_values("height_m", ascending=False).iterrows():
            cells = []
            for n in names:
                v = got[n][i]
                cells.append("" if not got[n + "_hit"][i] else ("(no h)" if pd.isna(v) else f"{v:.0f}"))
            L.append(f"| {r['name_zh']} | {r['height_m']:.0f} | {r.get('height_type', '')} | "
                     f"{str(r['use_height']).lower()} | " + " | ".join(cells) + " |")
            if not any(got[n + "_hit"][i] for n in names):
                miss.append(r["name_zh"])
        use = pts[pts.use_height.astype(str).str.lower() == "true"]
        L.append("")
        for n in names:
            e = (got[n][use.index] - use.height_m).dropna()
            if len(e):
                L.append(f"- {label(n)}: {len(e)} of {len(use)} height-setting landmarks on a footprint with a "
                         f"height; data − list median {e.median():+.1f} m, median abs {e.abs().median():.1f} m, "
                         f"within 10 m {(e.abs() <= 10).mean():.0%}")
        L += ["", f"On no footprint of any source: {', '.join(miss) if miss else 'none'}.", ""]
    return L
