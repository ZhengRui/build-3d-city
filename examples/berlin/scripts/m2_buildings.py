"""Berlin M2: the checks on the building table (04_buildings' buildings.gpkg) that Berlin needs beyond the engine's
checks/buildings.md: the LoD2 rules' decision table with examples, the parts and courtyards (the Blockrand), the
landmarks against the list, the largest height disagreements (LoD2 against the Umweltatlas and OSM), big blocks
and slivers, the OSM fill by tag, the kinds' fields for M4, the M4 figure list, and the height maps. It also writes
the 1-4 km ring for M3's masses (06e_masses' town_buildings.gpkg schema) from the Umweltatlas footprints.

Run from demos/berlin after 04_buildings (and 04b_quality):  uv run python scripts/m2_buildings.py [--no-ring]
Appends to checks/buildings.md (after a "## Berlin" marker, replaced on each run); writes
checks/buildings_heights.png, buildings_blockrand.png and ../data/berlin/town_buildings_umwelt.gpkg. ~1.5 GB with
the ring (the Umweltatlas GeoJSON over the boundary + 4 km): under the pipeline lock.
"""
import sys
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

from city3d.common import CFG, CHECKS, CITY, DATA, RAW, UTM, boundary, districts  # noqa: E402

T0 = time.time()
poly = boundary().geometry.iloc[0]
dd = districts()
b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
b["geometry"] = b.geometry.make_valid()       # (M4: 27 pieces invalid after the reprojection, 5 of them gen_split's)
b["a"] = b.area
lod = gpd.read_file(DATA / "lod2_buildings.gpkg").to_crs(UTM)
lod = lod[lod.geometry.representative_point().within(poly)].copy()
lod["a"] = lod.area
umw = gpd.read_file(DATA / "umwelt_buildings.gpkg", ignore_geometry=True)
FTXT = umw.groupby("funktion").funktion_txt.first().to_dict()
L = ["## Berlin", "", "Appended by `scripts/m2_buildings.py` (M2). Areas in m² unless said; heights above the ground.", ""]


def ll(g):
    p = gpd.GeoSeries([g.representative_point()], crs=UTM).to_crs(4326).iloc[0]
    return f"{p.y:.5f},{p.x:.5f}"


# 1. the LoD2 rules: what each ALKIS function became
L += ["### 1. The LoD2's solids by ALKIS function: kept, dropped, drawn as roofs", "",
      "Every LoD2 solid inside the boundary (98,686 in M1) against the [buildings] rules of city.toml (first match "
      "wins). Built: pieces in the table from that function (a part clipped by a kept OSM building, or by "
      "volume_dedupe, counts once).", "",
      "| ALKIS function | text | solids | area | median h | built pieces | built area | rule(s) |", "|---|---|---|---|---|---|---|---|"]
built = b[b.source == "lod2"]
for fn, g in lod.groupby("function"):
    if not str(fn).startswith(("51", "53")) and len(g) < 1500:
        continue
    bb = built[built.function == fn]
    rules = ", ".join(sorted(bb["rule"].dropna().unique())) if "rule" in bb else ""
    L.append(f"| {fn} | {FTXT.get(fn, '')} | {len(g):,} | {g.a.sum():,.0f} | {g.h.median():.1f} | {len(bb):,} | "
             f"{bb.a.sum():,.0f} | {rules or '—'} |")
L.append("")
low = lod[lod.function.str.startswith("31001") & (lod.h < 2)]
L += [f"Buildings (31001) under 2 m dropped: {len(low):,}, {low.a.sum():,.0f} m² (garage roofs, basements, "
      f"underground car parks' decks: Parkhaus {int((low.function == '31001_2461').sum())}, Parkdeck "
      f"{int((low.function == '31001_2462').sum())}, Garage {int((low.function == '31001_2463').sum())}). The largest: "
      + "; ".join(f"{FTXT.get(r.function, r.function)} {r.a:,.0f} m² at {r.h:.1f} m ({ll(r.geometry)})"
                  for r in low.sort_values("a", ascending=False).head(5).itertuples()) + ".", ""]
for lab in ("canopies and hall roofs (as their roof)",):
    r = b[b["rule"] == lab] if "rule" in b else b.iloc[:0]
    if len(r):
        L += [f"Canopies drawn as roofs: {len(r):,} ({r.a.sum():,.0f} m²), raised from a median {r.min_h.median():.1f} m "
              f"to {r.h.median():.1f} m; the largest: "
              + "; ".join(f"{r_.a:,.0f} m² {r_.min_h:.1f}-{r_.h:.1f} m ({ll(r_.geometry)})"
                          for r_ in r.sort_values("a", ascending=False).head(6).itertuples())
              + " (the Hauptbahnhof's halls, Alexanderplatz's and Friedrichstraße's station halls lead).", ""]

# 2. parts, stacking, courtyards
part = lod[lod.function.str.startswith("31001") & lod.part]
kept_small = built[(built.get("keep_small", False) == True) & ((built.a < 12) | False)]  # noqa: E712
ov = gpd.sjoin(b[["geometry"]], b[["geometry"]], predicate="intersects")
ov = ov[ov.index < ov.index_right]
inter = shapely.area(shapely.intersection(b.geometry.loc[ov.index].values, b.geometry.loc[ov.index_right].values))
small = np.minimum(b.a.loc[ov.index].values, b.a.loc[ov.index_right].values)
h, m = b.h.astype(float), b.min_h.fillna(0).astype(float)
vert = np.minimum(h.loc[ov.index].values, h.loc[ov.index_right].values) - np.maximum(m.loc[ov.index].values,
                                                                                     m.loc[ov.index_right].values)
dbl = (inter >= np.maximum(1.0, 0.05 * small)) & (vert > 1.0)
# courtyards: the LoD2 buildings (not canopies) merged where they touch, in the Altbau districts
solid = b[(b.min_h.fillna(0) == 0) & (b.h >= 2.5)]
blocks = gpd.GeoDataFrame(geometry=[solid.buffer(0.05).union_all()], crs=UTM).explode(index_parts=False)
blocks = blocks[blocks.area >= 200]
nh = shapely.get_num_interior_rings(blocks.geometry.values)
yard = np.array([sum(shapely.Polygon(r).area for r in g.interiors) for g in blocks.geometry])
L += ["### 2. Parts, stacking and courtyards", "",
      f"- The LoD2's buildings have {len(part):,} parts in the boundary ({int(part.parent_id.nunique()):,} buildings "
      "made of parts). Every part stands on the ground (ground_z equal within 1 mm for all 73,782 parts of the "
      "file): the parts tile their building's footprint side by side, each to its own measured height, so there "
      "is nothing to stack and no part hangs in the air.",
      f"- The engine's min_piece (12 m²) and 3 m strip rules would have dropped {int((part.a < 12).sum()):,} parts "
      f"under 12 m² and many under 3 m wide (stair towers, bays, slices of a roof): gaps in their buildings. The "
      f"`keep` rule keeps them: {int((built.a < 12).sum()):,} pieces under 12 m² are in the table.",
      f"- Double extrusion (pieces overlapping by 1 m² or 5 % of the smaller and in height by over 1 m): "
      f"{int(dbl.sum())} pairs left after volume_dedupe.",
      f"- Courtyards: the table's ground-standing pieces of 2.5 m and more, merged where they touch, make "
      f"{len(blocks):,} blocks of 200 m² or more; {int((nh > 0).sum()):,} of them hold {int(nh.sum()):,} open "
      f"courtyards ({yard.sum() / 1e6:.2f} km²; median {np.median(yard[yard > 0]) if (yard > 0).any() else 0:.0f} "
      "m²). The Hinterhöfe are open: the LoD2 draws each Vorderhaus, Seitenflügel and Hinterhaus as its own "
      "solid, and nothing fills a yard (`buildings_blockrand.png`: Kreuzberg's SO 36 and the Spandauer Vorstadt).",
      ""]

# 3. landmarks
lm = pd.read_csv(CITY / "data" / "landmarks_berlin.csv")
lc = pd.read_csv(DATA / "landmark_check.csv") if (DATA / "landmark_check.csv").exists() else pd.DataFrame()
top = b.groupby("landmark").h.max() if "landmark" in b else pd.Series(dtype=float)
srcs = b.groupby("landmark").h_src.agg(lambda v: ", ".join(sorted(set(map(str, v)))[:3])) if "landmark" in b else {}
pts = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
L += ["### 3. Landmarks against the list", "",
      "Every building row of the list of 30 m or more (and the must-haves): its listed height and type, whether the "
      "list sets it (use), the LoD2's height before (the solid the row matched; for a building of OSM parts its main "
      "roof), the table's top after, and the tallest piece within 40 m of the row's point (a row on a lower piece "
      "beside its tower shows here).", "",
      "| Landmark | listed | type | use | data before | built top | from | tallest within 40 m |",
      "|---|---|---|---|---|---|---|---|"]
sel = lm[(lm.feature.fillna("building") == "building") & ((lm.height_m >= 30) | lm.notes.fillna("").str.contains("MUST"))]
for i, r in sel.sort_values("height_m", ascending=False).iterrows():
    n = r.name_zh
    d = lc[lc.name == n] if len(lc) else lc
    L.append(f"| {n} | {r.height_m:.0f} | {str(r.height_type)[:40]} | {r.use_height} | "
             f"{d.data.iloc[0]:.0f} | " if len(d) else f"| {n} | {r.height_m:.0f} | {str(r.height_type)[:40]} | {r.use_height} | — | ")
    L[-1] += (f"{top[n]:.0f} | {srcs.get(n, '')} |" if n in top.index else "— | not matched |")
    zone = b[b.intersects(pts.geometry[i].buffer(40))]
    L[-1] += f" {zone.h.max():.0f} |" if len(zone) else " — |"
L.append("")
m4 = lm[lm.notes.fillna("").str.contains("for M4") | lm.feature.isin(["structure"])]
L += ["For M4 (figures, or tops over the bodies the table keeps): "
      + "; ".join(f"{r.name_zh} {r.height_m:.0f} m" if pd.notna(r.height_m) else r.name_zh
                  for r in m4.itertuples()) + ". Tops beyond the list's rows (fix round): the Reichstag's four corner "
      "towers (~40 m; the body 28), the Dom's four corner towers (~47-52 m; its body now 33.7 at the cornice), the "
      "Rotes Rathaus tower's top from its 74 m parapet to 94, the Nikolaikirche's twin spires (84 m; the nave 33) "
      "and the Zionskirche's spire (67 m; its tower 48), the Ostbahnhof's platform hall, Ostkreuz's and Kottbusser "
      "Tor's elevated stations and the S-Bahn viaducts OSM tags as buildings (decks, not blocks), the "
      "Oberbaumbrücke's towers.", ""]

# 4. disagreements
lod_h = b[b.source == "lod2"]
d1 = (lod_h.h - lod_h.h_umwelt).dropna() if "h_umwelt" in b else pd.Series(dtype=float)
osm = b["h_osm_tag"].where(b.get("osm_share", 1) >= 0.5) if "h_osm_tag" in b else pd.Series(np.nan, index=b.index)
d2 = (lod_h.h - osm.reindex(lod_h.index)).dropna()
L += ["### 4. The largest height disagreements", "",
      f"- LoD2 against the Umweltatlas's hoehe (same footprints, 2022 heights): n {len(d1):,}, median {d1.median():+.1f} m, "
      f"over 10 m apart {int((d1.abs() > 10).sum()):,}, over 30 m {int((d1.abs() > 30).sum()):,}.",
      f"- LoD2 against OSM's height tag (the OSM building that is mostly this one): n {len(d2):,}, median "
      f"{d2.median():+.1f} m, over 10 m apart {int((d2.abs() > 10).sum()):,}. The `height=4` of Mitte's outbuildings "
      f"sets no LoD2 height (h_src lod2 on {int((lod_h.h_src == 'lod2').sum()):,} of {len(lod_h):,} LoD2 pieces); on "
      f"OSM's fill it sets {int(((b.source == 'osm') & (b.h_src == 'osm_height') & (b.h == 4)).sum())} pieces.", "",
      "| Piece | LoD2 h | Umweltatlas | OSM tag | where |", "|---|---|---|---|---|"]
big = d1.abs().sort_values(ascending=False).head(12).index
for i in big:
    r = b.loc[i]
    L.append(f"| {r.get('name') if pd.notna(r.get('name')) else FTXT.get(r.function, r.function)} | {r.h:.0f} | "
             f"{r.h_umwelt:.0f} | {osm.get(i, np.nan):.0f} | {ll(r.geometry)} |")
L.append("")

# 5. blobs and slivers
blob = b[(b.a >= 5000) & (b.h >= 30) & (b.min_h.fillna(0) == 0)]
rect = b.geometry.minimum_rotated_rectangle()
w = rect.apply(lambda r: min(np.hypot(*np.diff(np.asarray(r.exterior.coords)[:3], axis=0).T)) if r.geom_type == "Polygon" else 0)
needle = (b.h > 8 * np.sqrt(b.a)) & b.part_of.isna() if "part_of" in b else (b.h > 8 * np.sqrt(b.a))
L += ["### 5. Merged blobs and slivers", "",
      f"- Blocks of 5,000 m² and more at 30 m and more standing on the ground: {len(blob)} — "
      + "; ".join(f"{r.name if pd.notna(r.name) else FTXT.get(r.function, r.source)} {r.a:,.0f} m² at {r.h:.0f} m "
                  f"({r.h_src})" for r in blob.sort_values("a", ascending=False).head(12).itertuples()) + ".",
      f"- Pieces under 3 m wide: {int((w < 3).sum()):,} ({b.a[w < 3].sum():,.0f} m²), {int(((w < 3) & (b.source == 'lod2')).sum()):,} "
      "of them LoD2 parts or structures the rules keep (bays, stair towers, the stelae, chimneys), the rest OSM's.",
      f"- Needles (h over 8 x the square root of the footprint) outside OSM parts: {int(needle.sum())} — "
      + "; ".join(f"{FTXT.get(r.function, r.source)} {r.a:.0f} m² {r.h:.0f} m" for r in
                  b[needle].sort_values("h", ascending=False).head(8).itertuples()) + ".", ""]

# 6. the OSM fill
fill = b[b.source == "osm"]
L += ["### 6. OSM's fill", "",
      f"{len(fill):,} OSM pieces ({fill.a.sum():,.0f} m², median {fill.a.median():.0f} m², h median {fill.h.median():.1f} m) "
      "where the LoD2 has nothing, by tag: "
      + ", ".join(f"{k} {v}" for k, v in fill.osm_building.fillna("?").value_counts().head(14).items()) + ".", ""]

# 7. kinds and the fields for M4
L += ["### 7. Kinds and the fields M4's de-berlin styles can use", "",
      "| Kind | pieces | share | area share | median h |", "|---|---|---|---|---|"]
for k, g in b.groupby("kind"):
    L.append(f"| {k} | {len(g):,} | {len(g) / len(b):.1%} | {g.a.sum() / b.a.sum():.1%} | {g.h.median():.1f} |")
fields = [c for c in ("function", "rooftype", "dachart_txt", "geschosse", "funktion_txt", "osm_building", "rule")
          if c in b]
L += ["", "Fields on the pieces (filled share): " + ", ".join(f"{c} {b[c].notna().mean():.0%}" for c in fields)
      + ". No construction year: neither the LoD2 nor the Umweltatlas carries one (the Umweltatlas's "
      "\"Gebäudealter\" is by block, for housing only; the Denkmalliste is a WFS of ~8,000 objects: M4's).",
      "LoD2 roofType (the roof's shape, for M4's roofs): "
      + ", ".join(f"{k} {v:,}" for k, v in b.rooftype.value_counts().head(8).items()) + " (1000 flat, 2100 shed, "
      "3100 gable, 3200 hip, 3300 half-hip, 3400 mansard, 3500 tent, 9999 generalised flat).", ""]

# 7b. the fix round (critic 1)
own = pd.to_numeric(b.roof_top_z, errors="coerce") - pd.to_numeric(b.ground_elevation, errors="coerce")
stack = own.notna() & (b.h > np.maximum(own, 3.5) + 1.0) & (b.h_src == b.source)
L += ["### 9. Fix round (critic 1): what changed", "",
      "Before: the M2 table of critic round 1 (89,088 pieces); after: this run.", "",
      "| Check | before | after |", "|---|---|---|",
      f"| LoD2 placeholder heights (≤ 5 m, the Umweltatlas over 2x higher) | 1,449 (145,740 m²) | "
      f"{int(((b.h <= 5) & (b.h_umwelt > 2 * b.h)).sum()):,} ({b.a[(b.h <= 5) & (b.h_umwelt > 2 * b.h)].sum():,.0f} m²) |",
      f"| roofType 9999 solids over 8 m off the Umweltatlas | 274 (100,873 m²) | "
      f"{int(((b.rooftype.astype(str) == '9999') & ((b.h - b.h_umwelt).abs() > 8)).sum()):,} |",
      f"| pieces over their own solid's top + 1 m with the LoD2's own height (stacked on a canopy or twin) | 159 | "
      f"{int(stack.sum()):,} |",
      f"| LoD2 pieces lifted off the ground other than canopy roofs | 15 | "
      f"{int(((b.source == 'lod2') & (b.min_h > 0) & ~b['rule'].astype(str).str.contains('canop')).sum()):,} |",
      f"| osm_height+ (OSM's tag over the laser) | 2 (the Nikolaikirche's and Zionskirche's naves at 84 and 67 m) | "
      f"{int((b.h_src == 'osm_height+').sum())} |",
      f"| copied_fix (a tower's height on a small piece, lowered) | 23 | {int((b.h_src == 'copied_fix').sum())} |",
      f"| OSM train_station and viaduct fills | 10 (34,000 m²) | "
      f"{int(b.osm_building.isin(['train_station', 'viaduct']).sum())} |",
      f"| OSM fills on the water (boats, pontoons) at the 10.5 m default | 4 | 0 ({int((b.h_src == 'afloat').sum())} "
      "at 3.5 m: [buildings] afloat) |", ""]
rs = b[b.h_src.astype(str).str.startswith("umwelt~")]
L += ["Heights the Umweltatlas set over the LoD2's (recheck): " + ", ".join(
      f"{k} {v:,}" for k, v in rs.h_src.value_counts().items()) + "; the largest: " + "; ".join(
      f"{r.name if pd.notna(r.name) else FTXT.get(r.function, r.function)} {r.a:,.0f} m² {r.h_lod2:.1f} → {r.h:.1f} m "
      f"({ll(r.geometry)})" for r in rs.sort_values("a", ascending=False).head(10).itertuples()) + ".", ""]
lmset = b[b.h_src == "landmark"]
L += ["Landmark heights set on whole footprints (the rule: only on a footprint about the tower's plate, or on its "
      "matched part): " + "; ".join(f"{r.landmark} {r.a:,.0f} m² at {r.h:.0f} m"
                                    for r in lmset.sort_values("a", ascending=False).itertuples()) + ".", ""]

# 8. maps
fig, ax = plt.subplots(figsize=(14, 11), dpi=110)
bounds = [0, 6, 10, 15, 20, 25, 30, 40, 60, 100, 400]
cmap = ListedColormap(plt.cm.viridis(np.linspace(0, 1, len(bounds) - 1)))
gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=ax, color="k", lw=0.6)
b.plot(ax=ax, column="h", cmap=cmap, norm=BoundaryNorm(bounds, cmap.N), linewidth=0, legend=True,
       legend_kwds={"shrink": 0.6, "label": "height (m)"})
ax.set_axis_off()
ax.set_title(f"Berlin building table (M2): {len(b):,} pieces coloured by height")
fig.savefig(CHECKS / "buildings_heights.png", bbox_inches="tight")
plt.close(fig)
fig, axs = plt.subplots(1, 2, figsize=(16, 8), dpi=110)
for ax, (lon, lat, name) in zip(axs, [(13.4230, 52.4995, "Kreuzberg (SO 36, Oranienstraße)"),
                                      (13.4000, 52.5260, "Spandauer Vorstadt (Hackesche Höfe)")]):
    c = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(UTM).iloc[0]
    box = shapely.box(c.x - 300, c.y - 300, c.x + 300, c.y + 300)
    s = b[b.intersects(box)]
    s.plot(ax=ax, column="h", cmap=cmap, norm=BoundaryNorm(bounds, cmap.N), edgecolor="k", linewidth=0.15)
    s[s.min_h > 0].plot(ax=ax, facecolor="none", edgecolor="r", linewidth=0.6)
    ax.set_xlim(box.bounds[0], box.bounds[2]); ax.set_ylim(box.bounds[1], box.bounds[3])
    ax.set_axis_off(); ax.set_title(f"{name}: pieces by height, raised roofs in red")
fig.savefig(CHECKS / "buildings_blockrand.png", bbox_inches="tight")
plt.close(fig)

# 9. the ring for M3's masses
if "--no-ring" not in sys.argv:
    src = CFG["sources"]["umwelt"]
    u = gpd.read_file(RAW / src["path"], columns=["hoehe", "geschosse", "funktion_txt"]).set_crs(src["crs"], allow_override=True).to_crs(UTM)
    u = u[~u.geometry.representative_point().within(poly) & u.geometry.notna()]
    out = gpd.GeoDataFrame({"osm": "umwelt", "building": "yes", "height": u["hoehe"].round(1).astype(str),
                            "levels": u["geschosse"].astype("Int64").astype(str).replace("<NA>", None),
                            "min_level": None, "funktion": u["funktion_txt"]}, geometry=u.geometry.make_valid(), crs=UTM)
    out = out[out.geom_type.isin(["Polygon", "MultiPolygon"])]
    out.to_file(DATA / "town_buildings_umwelt.gpkg", engine="pyogrio")
    hh = pd.to_numeric(u["hoehe"], errors="coerce")
    L += ["### 8. The ring beyond the boundary (M3's masses)", "",
          f"The Umweltatlas footprints outside the boundary (to 4 km beyond it): {len(out):,}, heights on "
          f"{hh.notna().mean():.0%} (median {hh.median():.1f} m), written in 06e_masses' town_buildings.gpkg schema "
          "(height = hoehe, levels = geschosse) to `../data/berlin/town_buildings_umwelt.gpkg`. M3: copy it to "
          "town_buildings.gpkg (06e_masses fetches OSM again when the cache is smaller than its reach: OSM beyond "
          "4 km, merged, or masses_reach kept within the Umweltatlas's box).", ""]

elif (DATA / "town_buildings_umwelt.gpkg").exists():
    import pyogrio
    n = pyogrio.read_info(DATA / "town_buildings_umwelt.gpkg")["features"]
    L += ["### 8. The ring beyond the boundary (M3's masses)", "",
          f"`../data/berlin/town_buildings_umwelt.gpkg` (written by a run without --no-ring): {n:,} Umweltatlas "
          "footprints outside the boundary (to 4 km beyond it) in 06e_masses' town_buildings.gpkg schema (height = "
          "hoehe, levels = geschosse). M3: copy it to town_buildings.gpkg (06e_masses fetches OSM again when the cache "
          "is smaller than its reach: OSM beyond 4 km, merged, or masses_reach kept within the Umweltatlas's box).", ""]

md = (CHECKS / "buildings.md").read_text()
md = md.split("## Berlin\n")[0].rstrip() + "\n\n"
(CHECKS / "buildings.md").write_text(md + "\n".join(L) + "\n")
print("\n".join(L))
print(f"m2_buildings: {time.time() - T0:.0f} s")
