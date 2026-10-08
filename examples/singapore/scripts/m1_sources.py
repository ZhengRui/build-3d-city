"""Singapore M1: what each source brings inside the boundary (option D, 54 URA subzones in 16 districts), how they
join and line up, and the terrain and the land/sea split.

- OSM (01_osm): buildings and building:parts per district, height and building:levels coverage, underground outlines
  (dropped in M2), metres per storey where both are tagged;
- HDB Existing Building (footprints, street *code*) + HDB Property Information (storeys, street *name*): the street
  code is resolved to the street name by the block numbers the two share (island-wide), then storeys are joined by
  block number and street. Writes the joined layer ../data/singapore/hdb_storeys.gpkg (the [sources.hdb] input).
  Then the HDB footprints are joined to OSM's (best overlap): match rate, IoU, centroid shift, OSM height vs storeys;
- URA MP2019 Building layer (indicative footprints, no attributes): coverage and offsets against OSM;
- the landmark list (data/landmarks.csv, when there) against OSM's height of the building at its point;
- Copernicus GLO-30 (02_dem): heights at named points and inside the boundary;
- the land/sea split: the districts' inland water (Phase 0's OSM water), the ground area's sea (OSM coastline), the
  500 m masses band.

Run from demos/singapore after 01_osm and 02_dem:  uv run python scripts/m1_sources.py
Writes checks/m1_sources.md and checks/m1_map.png (and the HDB join above). Small: ~10k OSM buildings, 13k HDB
blocks, the URA layer read in the scene's box; ~1 GB.
"""
import json
import re
import sys
import time
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from city3d.common import CHECKS, DATA, RAW, UTM, boundary, districts  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from m1_masses_band import osm_land  # noqa: E402

T0 = time.time()
HERE = Path(__file__).resolve().parent.parent
L = []
dd = districts()
poly = boundary().geometry.iloc[0]
X0, Y0, X1, Y1 = poly.bounds


def num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    m = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", str(v).replace(",", "."))
    return float(m[1]) if m else np.nan


def where(g):
    pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=UTM)
    j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
    return j[~j.index.duplicated()]["name"].reindex(g.index)


def inside(g):
    return g[g.geometry.representative_point().within(poly)].copy()


def match(a, b, min_iou=0.3):
    """For each footprint of a, the footprint of b overlapping it most: index, IoU, centroid shift (m)."""
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    ia, ib = b.sindex.query(a.geometry.values, predicate="intersects")
    inter = shapely.area(shapely.intersection(a.geometry.values[ia], b.geometry.values[ib]))
    uni = a.geometry.values[ia].area + b.geometry.values[ib].area - inter
    t = pd.DataFrame({"a": ia, "b": ib, "iou": inter / uni, "inter": inter})
    t = t.sort_values("inter", ascending=False).drop_duplicates("a")
    t = t[t.iou >= min_iou]
    ca, cb = a.geometry.centroid.values[t.a.values], b.geometry.centroid.values[t.b.values]
    t["dx"] = shapely.get_x(cb) - shapely.get_x(ca)
    t["dy"] = shapely.get_y(cb) - shapely.get_y(ca)
    t["shift"] = np.hypot(t.dx, t.dy)
    return t


def offsets(name, t, n):
    return (f"| {name} | {n:,} | {len(t):,} ({len(t) / max(n, 1):.0%}) | {t.iou.median():.3f} | {t['shift'].median():.2f} "
            f"| {t.dx.median():+.2f} / {t.dy.median():+.2f} | {t['shift'].quantile(0.9):.2f} |")


# ------------------------------------------------------------------ OSM
osm = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
osm["h"] = osm.height.map(num)
osm["lv"] = osm.levels.map(num)
osm["layer_n"] = osm.layer.map(num) if "layer" in osm else np.nan
osm["layer_n"] = pd.to_numeric(osm.layer, errors="coerce")
under = (osm.location == "underground") | (osm.layer_n < 0)
osm_all = osm
osm = inside(osm[~under])
osm["district"] = where(osm)
osm["area"] = osm.area
parts = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM) if (DATA / "osm_parts.gpkg").exists() else None

L += ["# Singapore M1: sources, coverage and alignment", "",
      "Made by `scripts/m1_sources.py` after 01_osm and 02_dem (Overpass answers of 6 Oct 2026, base "
      "timestamp in `../data/singapore/raw/overpass/`). Boundary: 54 URA MP2019 subzones in 16 districts "
      f"({poly.area / 1e6:.2f} km², EPSG:32648). A building counts in a district by its representative point.", "",
      "## 1. OSM buildings", "",
      f"{len(osm_all):,} outlines fetched (meeting the districts), {under.sum():,} underground "
      f"(location=underground or layer < 0: dropped in M2), {len(osm):,} above ground with their point inside.", "",
      "| District | km² | buildings | built km² | height | levels | either |",
      "|---|---|---|---|---|---|---|"]
for _, r in dd.assign(km2=dd.area / 1e6).iterrows():
    g = osm[osm.district == r["name"]]
    if not len(g):
        L.append(f"| {r['name']} | {r.km2:.2f} | 0 | | | | |")
        continue
    L.append(f"| {r['name']} | {r.km2:.2f} | {len(g):,} | {g.area.sum() / 1e6:.2f} | {g.h.notna().mean():.0%} | "
             f"{g.lv.notna().mean():.0%} | {(g.h.notna() | g.lv.notna()).mean():.0%} |")
big = osm.area >= 200
L += [f"| **all** | {poly.area / 1e6:.2f} | {len(osm):,} | {osm.area.sum() / 1e6:.2f} | {osm.h.notna().mean():.0%} | "
      f"{osm.lv.notna().mean():.0%} | {(osm.h.notna() | osm.lv.notna()).mean():.0%} |",
      f"| of them ≥ 200 m² | | {big.sum():,} | {osm[big].area.sum() / 1e6:.2f} | {osm[big].h.notna().mean():.0%} | "
      f"{osm[big].lv.notna().mean():.0%} | {(osm[big].h.notna() | osm[big].lv.notna()).mean():.0%} |", ""]
if parts is not None:
    pi = inside(parts)
    L.append(f"building:part outlines: {len(pi):,} (height on {pd.Series(pi.height.map(num)).notna().mean():.0%}, "
             f"min_height on {pd.Series(pi.min_height.map(num)).notna().mean():.0%}).")
both = osm[osm.h.notna() & osm.lv.notna() & (osm.lv > 0)]
per = both.h / both.lv
L += ["", f"Metres per storey where both are tagged (n {len(both):,}): median {per.median():.2f}, by levels: " +
      ", ".join(f"{a}-{b} storeys {per[(both.lv >= a) & (both.lv <= b)].median():.2f} (n {((both.lv >= a) & (both.lv <= b)).sum()})"
                for a, b in [(1, 4), (5, 12), (13, 30), (31, 99)]) + ".",
      "", "Building tags (top 12): " + ", ".join(f"{k} {v:,}" for k, v in osm.building.value_counts().head(12).items()) + ".", ""]
if under.any():
    u = osm_all[under]
    L.append("Underground outlines (top names): " + ", ".join(str(x) for x in u.name.dropna().head(12)) + ".")
    L.append("")

# ------------------------------------------------------------------ HDB: storeys joined to footprints
hb = gpd.read_file(RAW / "hdb_building" / "hdb_existing_building.geojson")
hp = pd.read_csv(RAW / "hdb_property" / "hdb_property_information.csv", dtype={"blk_no": str})
hb["blk"] = hb.BLK_NO.astype(str).str.strip().str.upper()
hp["blk"] = hp.blk_no.astype(str).str.strip().str.upper()
streets = hp.groupby("street").blk.apply(set)
code_street, ambiguous = {}, 0
for code, blks in hb.groupby("ST_COD").blk.apply(set).items():
    score = streets.map(lambda s: len(s & blks))
    best = score.sort_values(ascending=False)
    if best.iloc[0] == 0:
        continue
    if len(best) > 1 and best.iloc[1] == best.iloc[0]:
        ambiguous += 1          # two streets share the code's block numbers equally: left unjoined
        continue
    code_street[code] = best.index[0]
hb["street"] = hb.ST_COD.map(code_street)
j = hb.merge(hp, on=["blk", "street"], how="left", suffixes=("", "_p"))
j = j[~j.OBJECTID.duplicated()].set_index("OBJECTID")
inferred = j.max_floor_lvl.notna().sum()
# w-sg-data's join for option D (raw/hdb_D_join.csv): each footprint's street through its postal code (OneMap search),
# 403 of 403; it wins over the inferred street where both exist
dj = pd.read_csv(RAW / "hdb_D_join.csv").set_index("OBJECTID")
both_ = j.index.intersection(dj.index)
inf_ok = both_[j.loc[both_, "max_floor_lvl"].notna().values]
agree = (j.loc[inf_ok, "max_floor_lvl"].astype(float) == dj.loc[inf_ok, "max_floor_lvl"].astype(float))
j["join"] = np.where(j.max_floor_lvl.notna(), "street code", "")
for c in ["street", "max_floor_lvl", "year_completed", "residential", "commercial", "multistorey_carpark",
          "total_dwelling_units"]:
    j.loc[both_, c] = dj.loc[both_, c]
j.loc[both_, "join"] = "postal code (OneMap)"
j = j.reset_index()
out = j[["OBJECTID", "BLK_NO", "ST_COD", "POSTAL_COD", "street", "max_floor_lvl", "year_completed", "residential",
         "commercial", "multistorey_carpark", "total_dwelling_units", "join", "geometry"]].rename(columns=str.lower)
out = gpd.GeoDataFrame(out, geometry="geometry", crs=hb.crs)
out.to_file(DATA / "hdb_storeys.gpkg", driver="GPKG")
hdb = inside(out.to_crs(UTM))
hdb["district"] = where(hdb)
L += ["## 2. HDB blocks: storeys joined to footprints", "",
      f"HDB Existing Building has a street *code* (ST_COD), the Property Information the street *name*: each code "
      f"is resolved to the street sharing most of its block numbers (island-wide: {len(code_street):,} of "
      f"{hb.ST_COD.nunique():,} codes, {ambiguous} ties left out). Storeys then join by block number and street on "
      f"{inferred:,} of {len(hb):,} footprints ({inferred / len(hb):.1%}) island-wide. w-sg-data's join for option D "
      f"(`raw/hdb_D_join.csv`: each footprint's street through its postal code, OneMap's search) joins {len(dj):,} of "
      f"{len(dj):,}; the street-code inference joins {len(agree)} of them and agrees on the storeys of {agree.sum()}, and the "
      f"postal-code join wins. Written to `../data/singapore/hdb_storeys.gpkg` ([sources.hdb]; column `join` says how).",
      "",
      "HDB maps a podium and its towers as separate, nested polygons (w-sg-data: 36 overlapping pairs in Phase 0's "
      "polygon, 28 fully nested: 1 Cantonment Rd's 2-storey podium of 21,402 m² round Pinnacle@Duxton's 50-storey "
      "1A-1G; 1 Tanjong Pagar Plaza; 335 Smith St): M2 keeps both and cuts the towers out of the podiums, never a union.",
      "",
      f"Inside the boundary: {len(hdb):,} HDB footprints ({hdb.area.sum() / 1e6:.2f} km²), storeys on "
      f"{hdb.max_floor_lvl.notna().mean():.0%}; storeys median {hdb.max_floor_lvl.median():.0f}, max "
      f"{hdb.max_floor_lvl.max():.0f}. By district: " +
      ", ".join(f"{k} {v}" for k, v in hdb.district.value_counts().items()) + ".", ""]
t = match(hdb, osm)
hm = hdb.reset_index(drop=True).iloc[t.a.values].assign(osm_h=osm.reset_index(drop=True).h.values[t.b.values],
                                                       osm_lv=osm.reset_index(drop=True).lv.values[t.b.values])
L += ["Joined to OSM footprints (the OSM outline overlapping each HDB footprint most, IoU ≥ 0.3):", "",
      "| Pair | footprints | matched | IoU median | centroid shift median (m) | dx / dy median (m) | shift p90 (m) |",
      "|---|---|---|---|---|---|---|", offsets("HDB → OSM", t, len(hdb))]
ok = hm.osm_h.notna() & hm.max_floor_lvl.notna() & (hm.max_floor_lvl > 0)
okl = hm.osm_lv.notna() & hm.max_floor_lvl.notna()
L += ["", f"Of the matched HDB blocks, OSM has a height on {hm.osm_h.notna().mean():.0%} and levels on "
      f"{hm.osm_lv.notna().mean():.0%}; HDB storeys on {hm.max_floor_lvl.notna().mean():.0%}: HDB's storeys add a height "
      f"to {(hm.max_floor_lvl.notna() & hm.osm_h.isna() & hm.osm_lv.isna()).sum():,} blocks OSM has none for.",
      f"OSM levels = HDB max_floor_lvl on {(hm.osm_lv[okl] == hm.max_floor_lvl[okl]).mean():.0%} of {okl.sum()} "
      f"(within 1: {((hm.osm_lv[okl] - hm.max_floor_lvl[okl]).abs() <= 1).mean():.0%}).",
      f"OSM height / HDB storeys (n {ok.sum()}): median {(hm.osm_h[ok] / hm.max_floor_lvl[ok]).median():.2f} m; "
      f"a fit height = a × storeys + b: " + (lambda p: f"a {p[0]:.2f}, b {p[1]:+.1f} m")(
          np.polyfit(hm.max_floor_lvl[ok], hm.osm_h[ok], 1) if ok.sum() > 5 else (np.nan, np.nan)) +
      " ([sources.hdb] height uses 2.8 × storeys + 4.0 until M2 sets it).", ""]

# ------------------------------------------------------------------ URA MP2019 building layer
bb = gpd.GeoSeries([poly.buffer(600)], crs=UTM).to_crs(4326).total_bounds
ura = gpd.read_file(RAW / "ura_building" / "ura_mp2019_building.geojson", bbox=tuple(bb)).to_crs(UTM)
ura["geometry"] = ura.geometry.make_valid()
ura = inside(ura)
ura["district"] = where(ura)
t2 = match(ura, osm)
t3 = match(osm, ura)
tot = pd.read_json(json.dumps({})) if False else None
L += ["## 3. URA MP2019 Building layer (indicative footprints)", "",
      f"14,355 footprints island-wide (no type, height or name: BLDG_TYPE is empty); {len(ura):,} inside the boundary "
      f"({ura.area.sum() / 1e6:.2f} km² against OSM's {osm.area.sum() / 1e6:.2f} km²; median "
      f"{ura.area.median():.0f} m² against OSM's {osm.area.median():.0f} m²). By district: " +
      ", ".join(f"{k} {v}" for k, v in ura.district.value_counts().items()) + ".", "",
      "| Pair | footprints | matched | IoU median | centroid shift median (m) | dx / dy median (m) | shift p90 (m) |",
      "|---|---|---|---|---|---|---|", offsets("URA → OSM", t2, len(ura)), offsets("OSM → URA", t3, len(osm)), ""]
ou = osm.reset_index(drop=True)
lack_osm = ura.reset_index(drop=True).drop(index=t2.a.values)
lack_osm = lack_osm[~lack_osm.intersects(ou.union_all().buffer(1))] if len(lack_osm) else lack_osm
lack_ura = ou.drop(index=t3.a.values)
L += [f"URA footprints with no OSM building touching them: {len(lack_osm):,} ({lack_osm.area.sum() / 1e4:.1f} ha). "
      f"OSM buildings with no URA match: {len(lack_ura):,} ({lack_ura.area.sum() / 1e6:.2f} km²; "
      f"{(lack_ura.area >= 200).sum():,} of 200 m² or more): the URA layer is a planning sketch with whole blocks "
      "and estates as one polygon, not a footprint layer.", ""]

# ------------------------------------------------------------------ landmarks
lmf = HERE / "data" / "landmarks.csv"
if lmf.exists():
    lm = pd.read_csv(lmf)
    pts = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
    allb = osm_all.assign(h=osm_all.height.map(num), lv=osm_all.levels.map(num))
    pp = parts.assign(h=parts.height.map(num)) if parts is not None else None
    L += ["## 4. Landmarks (data/landmarks.csv) against OSM", "",
          "OSM's building whose outline holds the point (its height tag, levels × 3.2) and the tallest building:part "
          "within 60 m.", "",
          "| Landmark | listed m | use_height | OSM outline | OSM height | OSM levels | tallest part ≤ 60 m |", "|---|---|---|---|---|---|---|"]
    for _, r in pts.iterrows():
        hit = allb[allb.contains(r.geometry)]
        b = hit.iloc[(hit.area).argmin()] if len(hit) else None
        ph = pp[pp.distance(r.geometry) <= 60].h.max() if pp is not None else np.nan
        L.append(f"| {r.name_zh} | {"" if np.isnan(r.height_m) else f"{r.height_m:.0f}"} | {r.use_height} | {b.osm_id if b is not None else '(none)'} | "
                 f"{'' if b is None or np.isnan(b.h) else f'{b.h:.0f}'} | {'' if b is None or np.isnan(b.lv) else f'{b.lv:.0f}'} | "
                 f"{'' if np.isnan(ph) else f'{ph:.0f}'} |")
    L.append("")

# ------------------------------------------------------------------ GLO-30
tiles = sorted(RAW.glob("Copernicus_DSM_COG_10_*_DEM.tif"))
L += ["## 5. Copernicus GLO-30", ""]
if tiles:
    def sample(lon, lat):
        for p in tiles:
            with rasterio.open(p) as src:
                l, b, r, t_ = src.bounds
                if l <= lon < r and b <= lat < t_:
                    return float(next(src.sample([(lon, lat)]))[0])
        return np.nan
    spots = {"Marina Bay (water by the Float)": (103.8590, 1.2885, "0-2"),
             "Marina Bay Reservoir (mid)": (103.8640, 1.2860, "0-2"),
             "Marina South (reclaimed, Gardens by the Bay South)": (103.8640, 1.2770, "3-6"),
             "Raffles Place": (103.8513, 1.2840, "~5 (+ towers in a DSM)"), "Padang": (103.8525, 1.2905, "~4"),
             "Fort Canning Hill": (103.8466, 1.29358, "48"), "Pearl's Hill": (103.83994, 1.28455, "45"),
             "Mount Faber": (103.81767, 1.27359, "106 (OSM; 94-105 quoted)"), "Mount Imbiah": (103.81471, 1.25693, "62"),
             "Mount Serapong": (103.83326, 1.24989, "90"), "Telok Blangah Hill (outside)": (103.81045, 1.27888, "94"),
             "Bukit Timah Hill (backdrop, outside)": (103.77638, 1.35468, "164"),
             "Singapore Strait (sea)": (103.8600, 1.2400, "0")}
    L += [f"Tiles: {', '.join(p.name for p in tiles)} (EGM2008 heights; a surface model: roofs and canopy).", "",
          "| Point | GLO-30 m | expected m | inside the boundary |", "|---|---|---|---|"]
    for n_, (lo, la, e) in spots.items():
        pt = gpd.GeoSeries(gpd.points_from_xy([lo], [la]), crs=4326).to_crs(UTM).iloc[0]
        L.append(f"| {n_} | {sample(lo, la):.1f} | {e} | {'yes' if pt.within(poly) else 'no'} |")
    # inside the boundary (lon/lat grid of the tile)
    w = gpd.GeoSeries([poly], crs=UTM).to_crs(4326).iloc[0]
    from rasterio.mask import mask
    vals = []
    for p in tiles:
        with rasterio.open(p) as src:
            try:
                a, _ = mask(src, [w], crop=True, nodata=-9999)
                vals.append(a[a > -9999])
            except ValueError:
                pass
    v = np.concatenate(vals) if vals else np.array([])
    if len(v):
        L += ["", f"Inside the boundary ({len(v):,} 1\" cells): min {v.min():.1f}, p10 {np.percentile(v, 10):.1f}, median "
              f"{np.median(v):.1f}, p90 {np.percentile(v, 90):.1f}, max {v.max():.1f} m; {np.mean(v < 0.5):.1%} under 0.5 m "
              "(water held at the geoid), the towers and hills on top.", ""]
else:
    L += ["02_dem has not run: no tiles in raw/.", ""]

# ------------------------------------------------------------------ land / sea
water_f = HERE.parent / "data" / "singapore" / "phase0" / "osm_water.json"
from shapely.geometry import LineString, Polygon  # noqa: E402
from shapely.ops import polygonize, unary_union  # noqa: E402
wp = []
for e in json.loads(water_f.read_text())["elements"]:
    if e["type"] == "way" and len(e.get("geometry", [])) >= 4 and e["geometry"][0] == e["geometry"][-1]:
        wp.append(Polygon([(p["lon"], p["lat"]) for p in e["geometry"]]))
    elif e["type"] == "relation":
        ls = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in e["members"]
              if m.get("role") == "outer" and "geometry" in m]
        wp.append(unary_union(list(polygonize(unary_union(ls)))))
water = gpd.GeoSeries(wp, crs=4326).to_crs(UTM).make_valid().union_all()
land = gpd.GeoSeries([osm_land()], crs=4326).to_crs(UTM).iloc[0]
gx = shapely.box(X0 - 3000, Y0 - 3000, X1 + 3000, Y1 + 3000)
band = gpd.read_file(HERE / "data" / "masses_within.geojson").to_crs(UTM).union_all()
wi = poly.intersection(water).area
L += ["## 6. Land and sea", "",
      "| Area | km² |", "|---|---|",
      f"| the districts (54 subzones) | {poly.area / 1e6:.2f} |",
      f"| of which OSM inland water (Marina Bay and Reservoir, Kallang Basin, the river, Keppel channel) | {wi / 1e6:.2f} |",
      f"| of which seaward of OSM's coastline | {poly.difference(land).area / 1e6:.2f} |",
      f"| land in the districts | {(poly.intersection(land).area - poly.intersection(land).intersection(water).area) / 1e6:.2f} |",
      f"| the ground area (box + 3 km) | {gx.area / 1e6:.1f} |",
      f"| of which sea (beyond OSM's coastline) | {gx.difference(land).area / 1e6:.1f} |",
      f"| the 500 m masses band (land side) | {band.area / 1e6:.2f} |",
      "", "The band's buildings are fetched by 06e_masses (M3) over the chunks touching it; Phase 0 counted ~3.8k OSM "
      "buildings in a 500 m ring. The 0.56 km² seaward of OSM's coastline inside the districts: URA's No-Sea subzone "
      "lines and OSM's coastline differ along the reclaimed shores (Marina East, Tanjong Rhu, Sentosa) by a few metres to "
      "tens of metres: 05_ground takes the land from the coastline, so it is sea in the scene.", "",
      "Phase 0 gave 32.8 km² of land for option D: its polygon was simplified outward (≤ 60 vertices, up to ~150 m "
      "past the subzone lines; 3.5 km² of neighbouring subzones fell inside it: 36.1 km² of subzones), less its sea. "
      "Here the clips are the 54 subzones themselves (5 m coverage simplification), Maritime Square cut at 103.8085 E "
      "and three Sentosa beach islets (1.3 ha) left out.", ""]

# ------------------------------------------------------------------ map
fig, ax = plt.subplots(figsize=(11, 9), dpi=110)
gpd.GeoSeries([gx.difference(land)], crs=UTM).plot(ax=ax, color="#cfe3f0")
gpd.GeoSeries([band], crs=UTM).plot(ax=ax, color="#f3e1c4", edgecolor="#c9a46a", lw=0.5)
gpd.GeoSeries([water], crs=UTM).clip(gx).plot(ax=ax, color="#9cc5e0")
dd.boundary.plot(ax=ax, color="#555", lw=0.6)
src = np.where(osm.h.notna(), "#c0392b", np.where(osm.lv.notna(), "#e67e22", "#9a9a9a"))
osm.plot(ax=ax, color=src, lw=0)
hdb.plot(ax=ax, facecolor="none", edgecolor="#2471a3", lw=0.5)
gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=ax, color="k", lw=1.2)
ax.set_xlim(X0 - 1200, X1 + 1200)
ax.set_ylim(Y0 - 1200, Y1 + 1200)
ax.set_axis_off()
ax.set_title("Singapore option D (black), 500 m masses band (tan); OSM buildings: red height, orange levels, grey "
             "none; HDB blocks outlined blue", fontsize=8)
fig.tight_layout()
fig.savefig(CHECKS / "m1_map.png")
L += ["![map](m1_map.png)", "", f"({time.time() - T0:.0f} s)", ""]
(CHECKS / "m1_sources.md").write_text("\n".join(L))
print("\n".join(L))
