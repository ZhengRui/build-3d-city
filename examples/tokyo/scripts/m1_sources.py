"""M1: the coverage and alignment report, checks/m1_sources.md.

Inputs (all in ../data/tokyo/): boundary.gpkg and osm_buildings.gpkg (01_osm; the OSM sections are left out
while it has not run), plateau_buildings.gpkg (02_plateau, the citygml adapter's PLATEAU flavour), raw/gsi_dem/gsi_dem_mosaic.tif and the GLO-30 tiles in raw/ (02_dem); data/landmarks_tokyo.csv
and data/masses_within.geojson from this folder.

Sections: buildings per district and in the gaps (PLATEAU vs OSM), PLATEAU per mesh (LOD2 share, measuredHeight
coverage), footprint alignment OSM -> PLATEAU (offsets, IoU), what each source lacks, heights (OSM height and
levels vs measuredHeight, PLATEAU's storeys), the landmarks, and the two DEMs (GSI DEM5A bare earth vs GLO-30, a
surface model) at named points and over the ground area, with PLATEAU's ground z against the GSI DEM.

uv run python scripts/m1_sources.py     (from demos/tokyo; ~2 GB)
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
from shapely.geometry import shape

CITY = Path(__file__).resolve().parents[1]
DATA = CITY.parents[0] / "data/tokyo"
RAW = DATA / "raw"
UTM = "EPSG:32654"
LEVEL_H = 3.4
GSI = RAW / "gsi_dem/gsi_dem_mosaic.tif"
GLO = sorted(RAW.glob("Copernicus_DSM_COG_10_*_DEM.tif"))
L = []


def md(df: pd.DataFrame, fmt=None) -> None:
    fmt = fmt or {}
    L.append("| " + " | ".join(map(str, df.columns)) + " |")
    L.append("|" + "---|" * len(df.columns))
    for _, r in df.iterrows():
        L.append("| " + " | ".join(fmt.get(c, "{}").format(v) if pd.notna(v) else "" for c, v in r.items()) + " |")
    L.append("")


def stats(a, b):
    """b - a: n, r, median, MAE, share within 10 %."""
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 3:
        return dict(n=len(a))
    return dict(n=len(a), r=np.corrcoef(a, b)[0, 1], median=np.median(b - a), mae=np.mean(np.abs(b - a)),
                within10=np.mean(np.abs(b - a) <= 0.1 * a))


def main():
    dist = gpd.read_file(DATA / "boundary.gpkg").to_crs(UTM)
    D = dist.union_all()
    have_osm = (DATA / "osm_buildings.gpkg").exists()
    osm = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM) if have_osm else \
        gpd.GeoDataFrame({"osm_id": [], "height": [], "levels": []}, geometry=[], crs=UTM)
    if "location" in osm:
        osm = osm[~osm["location"].fillna("").eq("underground")]
    if "layer" in osm:
        lay = pd.to_numeric(osm["layer"], errors="coerce")
        osm = osm[~(lay < 0)]
    pl = gpd.read_file(DATA / "plateau_buildings.gpkg").to_crs(UTM)
    pl = pl.rename(columns={"measuredheight": "measuredHeight", "storeysaboveground": "storeys",
                            "ground_elevation": "ground_z"})
    pl["lod2"] = pl["lod"] == 2
    pl["mesh"] = pl["tile"].astype(str).str.extract(r"_(\d{8})_bldg")[0]
    pl["measuredHeight"] = pd.to_numeric(pl["measuredHeight"], errors="coerce")
    pl["storeys"] = pd.to_numeric(pl["storeys"], errors="coerce")
    for g in (osm, pl):
        g["pt"] = g.representative_point()
        g["area"] = g.area
    osm["h_osm"] = pd.to_numeric(osm.get("height"), errors="coerce")
    osm["lv"] = pd.to_numeric(osm.get("levels"), errors="coerce")

    L.extend(["# Tokyo M1: sources, coverage and alignment", "",
              "Made by `scripts/m1_sources.py`; PLATEAU as the engine's 02_plateau converted it (`plateau_buildings.gpkg`: "
              "the citygml adapter, flavour plateau; buildings meeting the districts, deduplicated by gml:id, classes 3003/3004 "
              "dropped). A building counts "
              "where its representative point lies. OSM without `location=underground` and `layer<0` (as 04_buildings). "
              f"Boundary D: {len(dist)} districts (the wards clipped by D), {D.area / 1e6:.2f} km² with water.", ""])

    # 1. per district
    def tally(poly):
        o = osm[osm.pt.within(poly)]
        p = pl[pl.pt.within(poly)]
        return o, p
    rows = []
    for _, d in dist.iterrows():
        o, p = tally(d.geometry)
        rows.append(dict(district=d["name"], km2=d.geometry.area / 1e6, osm=len(o), osm_height=o.h_osm.notna().mean(),
                         osm_levels=o.lv.notna().mean(), plateau=len(p), measured=p.measuredHeight.notna().mean(),
                         lod2=p.lod2.mean(), ratio=len(p) / max(len(o), 1)))
    t = pd.DataFrame(rows)
    inD = t[~t.district.str.startswith("gap")]
    o, p = tally(D)
    tot = dict(district="**D**", km2=D.area / 1e6, osm=len(o), osm_height=o.h_osm.notna().mean(),
               osm_levels=o.lv.notna().mean(), plateau=len(p), measured=p.measuredHeight.notna().mean(),
               lod2=p.lod2.mean(), ratio=len(p) / max(len(o), 1))
    t = pd.concat([inD, pd.DataFrame([tot])])
    pct = "{:.0%}"
    L.extend(["## 1. Buildings per district", "",
              "osm_height / osm_levels: share of OSM buildings with a `height` / `building:levels` tag; measured: share of "
              "PLATEAU buildings with `bldg:measuredHeight`; lod2: share with a `lod2Solid`; ratio: PLATEAU / OSM. "
              + ("" if have_osm else "**OSM not fetched yet** (01_osm waits for the local Overpass): its columns are empty. ")
              + "The gaps' block masses (06e_masses, M3) count their own buildings; Phase 0 counted 29.5k (Asakusa gap) and "
              "14.1k (west gap) OSM buildings.", ""])
    md(t, {"km2": "{:.2f}", "osm": "{:,}", "plateau": "{:,}", "osm_height": pct, "osm_levels": pct, "measured": pct,
           "lod2": pct, "ratio": "{:.2f}"})
    pD, oD = p, o

    # 2. per mesh
    m = pl.assign(inD=pl.pt.within(D)).groupby("mesh").agg(
        buildings=("gml_id", "size"), in_D=("inD", "sum"), lod2=("lod2", "mean"),
        measured=("measuredHeight", lambda s: s.notna().mean()), lod1_only=("lod", lambda s: int((s == 1).sum())),
        h_median=("measuredHeight", "median"), h_max=("measuredHeight", "max")).reset_index()
    L.extend(["## 2. PLATEAU per 1 km mesh", "",
              f"{len(m)} meshes, {len(pl):,} buildings meeting the districts (unique gml:id), of which {len(pD):,} in D; LOD2 {pl.lod2.mean():.1%} "
              f"of all, {pD.lod2.mean():.1%} in D; measuredHeight on {pl.measuredHeight.notna().mean():.2%}; "
              f"footprints from: {', '.join(f'{k} {v:.1%}' for k, v in pl.fp_from.value_counts(normalize=True).items())}. "
              "Building parts: none (PLATEAU 2025 has no bldg:BuildingPart here).", ""])
    md(m, {"buildings": "{:,}", "in_D": "{:,}", "lod2": pct, "measured": pct, "lod1_only": "{:,}", "h_median": "{:.1f}",
           "h_max": "{:.1f}"})

    if not have_osm or not len(oD):
        L.extend(["## 3-5. OSM against PLATEAU", "", "Not run yet: 01_osm waits for the local Overpass "
                  "(127.0.0.1:8787; the public mirrors answered 504 on 6 Oct). Run this script again after it.", ""])
        heights_plateau(pD)
    else:
        osm_sections(pD, oD, dist)
        heights_plateau(pD)
    landmarks(pl, osm)
    dem_section(pD, D)
    (CITY / "checks").mkdir(exist_ok=True)
    (CITY / "checks/m1_sources.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def osm_sections(pD, oD, dist):
    # 3. alignment OSM -> PLATEAU (in D)
    po = pD[["gml_id", "geometry", "area", "measuredHeight", "storeys"]].reset_index(drop=True)
    oo = oD[["osm_id", "geometry", "area", "h_osm", "lv"]].reset_index(drop=True)
    j = gpd.sjoin(oo, po, predicate="intersects", lsuffix="o", rsuffix="p")
    j["inter"] = [oo.geometry[a].intersection(po.geometry[b]).area for a, b in zip(j.index, j.index_p)]
    j["iou"] = j.inter / (j.area_o + j.area_p - j.inter)
    best = j.sort_values("iou", ascending=False)
    best = best[~best.index.duplicated()]
    one = best[best.iou >= 0.5].copy()
    co = oo.geometry.centroid
    cp = po.geometry.centroid
    one["dx"] = [cp[b].x - co[a].x for a, b in zip(one.index, one.index_p)]
    one["dy"] = [cp[b].y - co[a].y for a, b in zip(one.index, one.index_p)]
    one["d"] = np.hypot(one.dx, one.dy)
    dmap = gpd.sjoin(gpd.GeoDataFrame(geometry=oo.loc[one.index].representative_point(), crs=UTM),
                     dist[["name", "geometry"]], predicate="within")["name"]
    one["district"] = dmap.reindex(one.index)
    al = one.groupby("district").agg(pairs=("iou", "size"), iou=("iou", "median"), dx=("dx", "median"),
                                     dy=("dy", "median"), d50=("d", "median"),
                                     d90=("d", lambda s: s.quantile(0.9))).reset_index()
    al = pd.concat([al, pd.DataFrame([dict(district="**D**", pairs=len(one), iou=one.iou.median(), dx=one.dx.median(),
                                           dy=one.dy.median(), d50=one.d.median(), d90=one.d.quantile(0.9))])])
    L.extend(["## 3. Footprint alignment, OSM -> PLATEAU", "",
              f"Each OSM building paired with the PLATEAU footprint it overlaps most; pairs with IoU >= 0.5 "
              f"({len(one):,} of {len(oo):,} OSM buildings in D). dx, dy: PLATEAU's centroid minus OSM's (m, UTM 54N).", ""])
    md(al, {"pairs": "{:,}", "iou": "{:.3f}", "dx": "{:+.2f}", "dy": "{:+.2f}", "d50": "{:.2f}", "d90": "{:.2f}"})

    # 4. what each lacks
    hit_o = set(j.index)
    hit_p = set(j.index_p)
    lo = oo[~oo.index.isin(hit_o)]
    lp = po[~po.index.isin(hit_p)]
    L.extend(["## 4. What each lacks (in D)", "",
              f"- OSM buildings meeting no PLATEAU footprint: {len(lo):,} ({lo.area.sum() / 1e6:.3f} km², median "
              f"{lo.area.median():.0f} m²; {int((lo.area >= 200).sum()):,} of 200 m² or more).",
              f"- PLATEAU buildings meeting no OSM building: {len(lp):,} ({lp.area.sum() / 1e6:.3f} km², median "
              f"{lp.area.median():.0f} m²; {int((lp.area >= 200).sum()):,} of 200 m² or more; measuredHeight median "
              f"{lp.measuredHeight.median():.1f} m).",
              f"- Built area: PLATEAU {po.area.sum() / 1e6:.2f} km², OSM {oo.area.sum() / 1e6:.2f} km²; median footprint "
              f"PLATEAU {po.area.median():.0f} m², OSM {oo.area.median():.0f} m².",
              f"- One OSM outline over several PLATEAU footprints (blocks mapped whole): "
              f"{int((j[j.inter > 0.5 * j.area_p].groupby(level=0).size() >= 3).sum()):,} OSM outlines cover 3 or more "
              "PLATEAU footprints by more than half of each.", ""])

    # 5. heights
    pair = one.assign(mh=[po.measuredHeight[b] for b in one.index_p], st=[po.storeys[b] for b in one.index_p],
                      h_osm=oo.h_osm.reindex(one.index).values, lv=oo.lv.reindex(one.index).values)
    s1 = stats(pair.mh.values, pair.h_osm.values)
    s2 = stats(pair.mh.values, pair.lv.values * LEVEL_H)
    L.extend(["## 5. Heights", "",
              "Over the pairs of section 3 (OSM minus PLATEAU measuredHeight):", "",
              "| Comparison | n | r | median | MAE | within 10 % |", "|---|---|---|---|---|---|",
              f"| OSM `height` vs measuredHeight | {s1.get('n', 0):,} | {s1.get('r', np.nan):.3f} | {s1.get('median', np.nan):+.1f} m | {s1.get('mae', np.nan):.1f} m | {s1.get('within10', np.nan):.0%} |",
              f"| OSM levels x {LEVEL_H} vs measuredHeight | {s2.get('n', 0):,} | {s2.get('r', np.nan):.3f} | {s2.get('median', np.nan):+.1f} m | {s2.get('mae', np.nan):.1f} m | {s2.get('within10', np.nan):.0%} |",
              ""])


def heights_plateau(pD):
    st = pD[(pD.storeys > 0) & pD.measuredHeight.notna()]
    per = (st.measuredHeight / st.storeys)
    byst = st.assign(per=per, band=pd.cut(st.storeys, [0, 2, 4, 7, 12, 20, 40, 80])).groupby("band", observed=True).agg(
        n=("per", "size"), m_per_storey=("per", "median")).reset_index()
    byst["band"] = byst.band.astype(str)
    L.extend(["### PLATEAU heights", "", f"PLATEAU's own storeysAboveGround (on {len(st) / max(len(pD), 1):.0%} of D's buildings): measuredHeight / storeys, "
              f"median {per.median():.2f} m:", ""])
    md(byst, {"n": "{:,}", "m_per_storey": "{:.2f}"})
    hb = pd.cut(pD.measuredHeight, [0, 10, 20, 31, 60, 100, 150, 200, 700]).value_counts().sort_index()
    L.extend(["PLATEAU measuredHeight in D: " + ", ".join(f"{k}: {v:,}" for k, v in hb.items()) + " (m).", ""])


def landmarks(pl, osm):
    lm = pd.read_csv(CITY / "data/landmarks_tokyo.csv")
    lm = lm[lm.height_m.notna()]
    pts = gpd.GeoSeries(gpd.points_from_xy(lm.lon, lm.lat), crs="EPSG:4326").to_crs(UTM)
    rows = []
    for (_, r), q in zip(lm.iterrows(), pts):
        near = pl[pl.geometry.distance(q) <= 60]
        on = osm[osm.geometry.distance(q) <= 60]
        rows.append(dict(landmark=r.name_en, listed=r.height_m, use_height=r.use_height,
                         plateau=near.measuredHeight.max() if len(near) else np.nan,
                         osm=on.h_osm.max() if len(on) else np.nan))
    lt = pd.DataFrame(rows)
    ok = lambda c: int((np.abs(lt[c] - lt.listed) <= 0.05 * lt.listed).sum())   # noqa: E731
    L.extend(["## 6. Landmarks", "",
              "The tallest PLATEAU measuredHeight and OSM `height` within 60 m of each listed point (data/landmarks_tokyo.csv; "
              f"heights from two sources each). Within 5 %: PLATEAU {ok('plateau')} of {lt.plateau.notna().sum()}, "
              f"OSM {ok('osm')} of {lt.osm.notna().sum()}.", ""])
    md(lt, {"listed": "{:.1f}", "plateau": "{:.1f}", "osm": "{:.1f}"})



def sample(path, lon, lat, r=0.0):
    with rasterio.open(path) as src:
        x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(lon, lat)
        if not (src.bounds.left < x < src.bounds.right and src.bounds.bottom < y < src.bounds.top):
            return np.nan
        # the radius in the raster's units: degrees for a geographic raster (GLO-30), web-mercator metres (1/cos lat
        # of ground metres) for the GSI mosaic
        rk = r / 111320.0 if src.crs.is_geographic else r / np.cos(np.radians(lat))
        rr = max(rk, src.res[0])
        a = src.read(1, window=from_bounds(x - rr, y - rr, x + rr, y + rr, src.transform), masked=True)
        if a.count() == 0:
            return np.nan
        return float(a.max()) if r else float(a[a.shape[0] // 2, a.shape[1] // 2])


def glo(lon, lat, r=0.0):
    for p in GLO:
        v = sample(p, lon, lat, r)
        if np.isfinite(v):
            return v
    return np.nan


def dem_section(pD, D):
    L.extend(["## 7. Terrain: GSI DEM5A and GLO-30", ""])
    if not GSI.exists() or not GLO:
        L.extend([f"(not run: {'the GSI mosaic' if not GSI.exists() else 'the GLO-30 tiles'} missing)", ""])
        return
    with rasterio.open(GSI) as s:
        L.append(f"GSI mosaic: {s.width} x {s.height} cells of {s.res[0]:.2f} m (web mercator, {s.crs}), nodata "
                 f"{s.nodata}; GLO-30: {', '.join(p.name for p in GLO)}.")
    L.append("")
    pts = {"Imperial Palace (East Gardens)": (139.7550, 35.6880, None), "Atago-yama summit": (139.748746, 35.664768, 26),
           "Nishi-Shinjuku (TMG plaza)": (139.6917, 35.6896, 40.9), "Meiji Shrine": (139.6996, 35.6760, 37.3),
           "Shibuya Crossing": (139.7006, 35.6595, 15.2), "Tokyo Station": (139.7660, 35.6810, 3.5),
           "Asakusa": (139.7966, 35.7112, 3.6), "Daiba": (139.7745, 35.6268, 5.9),
           "Tokyo Bay, inner harbour off Daiba": (139.7700, 35.6350, 0.0), "Tokyo Bay off Shinagawa": (139.7650, 35.6320, 0.0)}
    rows = []
    for n, (lo, la, exp) in pts.items():
        r = 30.0 if "summit" in n else 0.0
        g, c = sample(GSI, lo, la, r), glo(lo, la, r)
        rows.append(dict(point=n, expected=exp, gsi=g, glo30=c, glo_minus_gsi=c - g))
    md(pd.DataFrame(rows), {"expected": "{:.1f}", "gsi": "{:.1f}", "glo30": "{:.1f}", "glo_minus_gsi": "{:+.1f}"})
    # over the boundary on a 100 m grid
    x0, y0, x1, y1 = D.bounds
    xs, ys = np.meshgrid(np.arange(x0, x1, 100), np.arange(y0, y1, 100))
    lon, lat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(xs.ravel(), ys.ravel())
    inside = gpd.GeoSeries(gpd.points_from_xy(xs.ravel(), ys.ravel()), crs=UTM).within(D).values
    lon, lat = np.asarray(lon)[inside], np.asarray(lat)[inside]
    with rasterio.open(GSI) as s:
        tx, ty = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True).transform(lon, lat)
        g = np.array([v[0] for v in s.sample(zip(tx, ty))], dtype=float)
        if s.nodata is not None:
            g[g == s.nodata] = np.nan
    c = np.full(len(lon), np.nan)
    for p in GLO:
        with rasterio.open(p) as s:
            tx, ty = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True).transform(lon, lat)
            v = np.array([q[0] for q in s.sample(zip(tx, ty))], dtype=float)
            ins = (np.asarray(tx) >= s.bounds.left) & (np.asarray(tx) < s.bounds.right) & \
                  (np.asarray(ty) >= s.bounds.bottom) & (np.asarray(ty) < s.bounds.top)
            c = np.where(np.isnan(c) & ins, v, c)
    g[(g < -50) | (g > 4000)] = np.nan
    dd = c - g
    ok = np.isfinite(dd)
    L.extend([f"Inside D on a 100 m grid ({ok.sum():,} points with both): GSI {np.nanmin(g):.1f} to {np.nanmax(g):.1f} m "
              f"(median {np.nanmedian(g):.1f}; {np.isnan(g).sum():,} points without GSI data: water); GLO-30 minus GSI "
              f"median {np.median(dd[ok]):+.1f} m, p10 {np.quantile(dd[ok], 0.1):+.1f}, p90 {np.quantile(dd[ok], 0.9):+.1f}. "
              "GLO-30 is a surface model (roofs and trees; in this tower city its 30 m cells stand on buildings), "
              "GSI DEM5A bare earth from laser survey: GLO-30 is for the backdrop only.", ""])
    # PLATEAU's ground z vs GSI
    q = pD[pD.ground_z.notna()].sample(min(5000, int(pD.ground_z.notna().sum())), random_state=1)
    ll = q.pt.to_crs("EPSG:4326")
    with rasterio.open(GSI) as s:
        tx, ty = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True).transform(ll.x.values, ll.y.values)
        gv = np.array([v[0] for v in s.sample(zip(tx, ty))], dtype=float)
        if s.nodata is not None:
            gv[gv == s.nodata] = np.nan
    d2 = q.ground_z.values - gv
    ok2 = np.isfinite(d2)
    L.extend([f"PLATEAU ground z (the lod1Solid's bottom, T.P.) minus GSI at the footprint's point, {ok2.sum():,} "
              f"buildings: median {np.median(d2[ok2]):+.2f} m, |p95| {np.quantile(np.abs(d2[ok2]), 0.95):.2f} m "
              "(the same datum: both T.P.).", ""])


if __name__ == "__main__":
    main()
