"""M2's checks on London's building table (after `city3d 04_buildings` and `city3d 04b_quality`): what the spike
rule, the area-weighted join and the Carbon & Place fill did, the towers against the landmark list before and
after, the largest disagreements left, big footprints, slivers, kinds by OSM tag, and a height map.

Appends a "London M2 checks" section to checks/buildings.md (which 04_buildings rewrites) and writes
checks/buildings_heights.png. Run from demos/london: `uv run python scripts/m2_buildings.py` (~1 GB, 30 s).
"""
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from city3d.common import CFG, CHECKS, CITY, DATA, LEVEL_H, UTM, boundary  # noqa: E402

b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
b["a"] = b.area
poly = boundary().geometry.iloc[0]
L = ["", "## London M2 checks (scripts/m2_buildings.py)", ""]
f0 = lambda v: "" if pd.isna(v) else f"{v:.0f}"  # noqa: E731
ll = lambda g: g.representative_point().to_crs(4326).map(lambda p: f"{p.y:.5f}, {p.x:.5f}")  # noqa: E731

# ---------------------------------------------------------------- spikes
sp = b[b.h_src.astype(str).str.startswith("carbon~")]
L += ["### Carbon & Place spikes ([buildings.spikes])", "",
      f"{len(sp):,} footprints ({sp.a.sum() / 1e6:.2f} km²) had a Carbon & Place top far over what OSM says or a "
      f"touching building's top: {int((sp.h_src == 'carbon~osm').sum()):,} lowered to OSM's height or levels × "
      f"{LEVEL_H} + 3 m (carbon~osm), {int((sp.h_src == 'carbon~mean').sum()):,} to the polygon's mean × 1.35 "
      f"(carbon~mean). The top went from a median {sp.spike_carbon.median():.1f} m to {sp.h.median():.1f} m "
      f"(sum of the drops {(sp.spike_carbon - sp.h).sum() / 1000:.1f} km of height). Of them, "
      f"{int((sp.spike_carbon >= 60).sum())} had a top of 60 m or more.", "",
      "The largest:", "", "| name | OSM tag | was (m) | now (m) | rule | footprint (m²) | lat, lon |", "|---|---|---|---|---|---|---|"]
for (_, r), p in zip(sp.nlargest(25, "spike_carbon").iterrows(), ll(sp.nlargest(25, "spike_carbon").geometry)):
    L.append(f"| {r['name'] if pd.notna(r['name']) else ''} | {r.osm_building} | {r.spike_carbon:.0f} | {r.h:.0f} | "
             f"{r.h_src} | {r.a:,.0f} | {p} |")
# a spike whose footprint was later made of OSM parts keeps the parts' heights
L += ["", "Named cases from M1: " + "; ".join(
    f"{n} {f0(g.spike_carbon.max()) or f0(g.h_carbon.max())} → {g.h.max():.0f} m ({', '.join(sorted(set(g.h_src.astype(str))))})"
    for n, g in ((n, b[b["name"].fillna("").str.contains(n, regex=False)]) for n in
                 ("West Wintergarden", "East Wintergarden", "Cabot Place", "Frobisher Crescent", "Barbican Arts Centre",
                  "The O2", "Battersea Power Station")) if len(g)) + ".", ""]

# ---------------------------------------------------------------- weighted join, default heights
j = b["join_carbon"] if "join_carbon" in b else pd.Series(np.nan, index=b.index)
w = b[j.eq("weighted")]
nojoin = b[j.isna() & (b.source == "osm") & b.part_of.isna()]
d = b[b.h_src == "default"]
L += ["### Footprints no single Carbon & Place plot covers ([buildings.join] weighted = 0.5)", "",
      f"M1: 1,539 OSM footprints (1.04 km²) got no height from the largest-plot rule (no plot covers 30 % of them). "
      f"Now {len(w):,} footprints ({w.a.sum() / 1e6:.2f} km², median {w.a.median():.0f} m²) take the area-weighted "
      f"median of the plots covering them (median {w.h_carbon.median():.1f} m); with that, "
      f"{len(nojoin):,} whole OSM footprints ({nojoin.a.sum() / 1e6:.2f} km²) have no Carbon & Place height "
      f"(plots under half of them: canopies, roofs, houseboats, buildings the lidar predates), and {len(d):,} "
      f"({d.a.sum() / 1e6:.2f} km², median {d.a.median():.0f} m²) end with the default height "
      f"({CFG['buildings']['default_floors']} × {LEVEL_H} m; 3.5 m under 50 m²).", ""]

# ---------------------------------------------------------------- fill
fl = b[b.source == "carbon"]
L += ["### Carbon & Place fill ([buildings.fill])", "",
      f"{len(fl):,} Carbon & Place polygons ({fl.a.sum() / 1e6:.2f} km², median {fl.a.median():.0f} m², height median "
      f"{fl.h.median():.1f} m, max {fl.h.max():.0f} m) stand where OSM has no building: of the 3,682 in the "
      "districts (M1, 0.43 km²) those of 30 m² and 2.5 m or more, not tagged roof, ship, construction... and not on "
      "an OSM building site (landuse=construction), nor on an OSM outline the preset skips (canopies, ships, "
      "building sites) or [buildings] exclude leaves out (the London Eye).", ""]
big = fl.nlargest(8, "a")
L += ["Largest fill polygons:", "", "| h (m) | m² | lat, lon |", "|---|---|---|"]
for (_, r), p in zip(big.iterrows(), ll(big.geometry)):
    L.append(f"| {r.h:.0f} | {r.a:,.0f} | {p} |")
L.append("")

# ---------------------------------------------------------------- towers vs list
lc = pd.read_csv(DATA / "landmark_check.csv")
lm = pd.concat([pd.read_csv(f) for f in sorted(CITY.glob(CFG["paths"]["landmarks"]))], ignore_index=True)
lm = lm[lm.feature.fillna("building").eq("building") & lm.use_height.astype(str).str.lower().eq("true")
        & (lm.height_m >= 100)].dropna(subset=["lat", "lon"])
pts = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
lm = lm[pts.within(poly.buffer(50)).values]
t = lm.merge(lc, left_on="name_zh", right_on="name", how="left")
# before the spike rule: the matched building's Carbon & Place top where the rule lowered it
lmk = b[b.landmark.notna()].groupby("landmark").agg(spike=("spike_carbon", "max"), top=("h", "max"))
t["spike"] = t.name_zh.map(lmk.spike)
t["before"] = t.spike.fillna(t.data)
t["built"] = t.name_zh.map(lmk.top)
ok = lambda c: ((t[c] - t.height_m).abs() <= 0.05 * t.height_m)  # noqa: E731
L += ["### Towers of 100 m or more (use_height) against the landmark list", "",
      f"{len(t)} towers in the districts. The data's height (before the list overrides it; a building of OSM parts: "
      f"its main roof) within 5 % of the list: **{int(ok('data').sum())}** with the spike rule, "
      f"{int(ok('before').sum())} without it (within 15 %: {int(((t.data - t.height_m).abs() <= 0.15 * t.height_m).sum())}); "
      f"the rule lowered {int(t.spike.notna().sum())} of them. M1's measure (the Carbon & Place polygon at the point "
      "or the highest within 30 m, untouched by M2): 56. Built (the table's top, after the list): within 5 % on "
      f"**{int(ok('built').sum())}**, not matched: {int(t.built.isna().sum())}.", "",
      "| Tower | listed (m) | data (m) | was (spike) | built (m) | from |", "|---|---|---|---|---|---|"]
for _, r in t.sort_values("height_m", ascending=False).iterrows():
    L.append(f"| {r.name_zh} | {r.height_m:.0f} | {f0(r.data)} | {f0(r.spike)} | {f0(r.built)} | {r.src if pd.notna(r.src) else ''} |")
L.append("")

# ---------------------------------------------------------------- disagreements with OSM left
solid = b[b.part_of.isna() & b.h_src.isin(["carbon", "carbon~mean"])].copy()
tag = solid.h_osm_tag.where(solid.osm_share >= 0.5)
lev = solid.h_osm_levels.where(solid.osm_share >= 0.5)
solid["osm"] = tag.fillna(lev + 3)
solid["diff"] = solid.h - solid.osm
dd = solid.dropna(subset=["diff"])
L += ["### Largest disagreements left (table vs OSM height, else levels × 3.2 + 3 m)", "",
      f"{len(dd):,} Carbon & Place heights with an OSM value: median {dd['diff'].median():+.1f} m, "
      f"|diff| > 10 m on {int((dd['diff'].abs() > 10).sum()):,}, > 30 m on {int((dd['diff'].abs() > 30).sum()):,}. "
      "The largest (above: Carbon & Place's top kept, its mean being over half of it, i.e. a real tall roof or a "
      "wrong levels tag; below: the lidar predates the building or a low tag):", "",
      "| name | OSM | table (m) | OSM (m) | mean (m) | m² | lat, lon |", "|---|---|---|---|---|---|---|"]
top = dd.reindex(dd["diff"].abs().sort_values(ascending=False).index).head(20)
for (_, r), p in zip(top.iterrows(), ll(top.geometry)):
    L.append(f"| {r['name'] if pd.notna(r['name']) else ''} | {r.osm_building} | {r.h:.0f} | {r.osm:.0f} | "
             f"{f0(r.hmean_carbon)} | {r.a:,.0f} | {p} |")
L.append("")

# ---------------------------------------------------------------- blobs, slivers, outliers
blob = b[(b.a >= 5000) & (b.h >= 30) & b.part_of.isna()]
L += ["### Big footprints, slivers, outliers", "",
      f"- Footprints of 5,000 m² or more at 30 m or more (a merged block extruded as a wall?): {len(blob)} — "
      + "; ".join(f"{r['name'] if pd.notna(r['name']) else r.osm_building} {r.h:.0f} m, {r.a:,.0f} m² ({r.h_src})"
                  for _, r in blob.nlargest(12, "a").iterrows()) + ".",
      f"- Footprints under 12 m²: {int((b.a < 12).sum()):,} ({int(((b.a < 12) & b.part_of.notna()).sum()):,} of them OSM parts: "
      "spires, turrets, finials); non-OSM under 20 m²: "
      f"{int(((b.a < 20) & (b.source != 'osm')).sum()):,}.",
      f"- Slender (h > 8 √area) outside part-built buildings: {int(((b.h > 8 * np.sqrt(b.a)) & b.part_of.isna()).sum())}.",
      f"- Underground: OSM `location=underground` or `layer<0` are left out (load_osm; 50 in the extract, Crossrail "
      f"Place among them, which comes back as Carbon & Place fill); in the table: "
      f"{int(b.get('location', pd.Series(dtype=str)).eq('underground').sum())}.", ""]

# ---------------------------------------------------------------- kinds by OSM tag
kt = pd.crosstab(b.osm_building.fillna("(none)"), b.kind)
L += ["### Kinds against the OSM building tag (most common tags)", "",
      "The europe-west preset's kinds (Paris's names; London's own facades come in M4). Pieces, not buildings.", "",
      "| OSM tag | " + " | ".join(kt.columns) + " |", "|---|" + "---|" * len(kt.columns)]
for tg in b.osm_building.fillna("(none)").value_counts().head(14).index:
    L.append(f"| {tg} | " + " | ".join(f"{v:,}" for v in kt.loc[tg]) + " |")
L.append("")

# ---------------------------------------------------------------- map
fig, ax = plt.subplots(figsize=(14, 9))
bb = b.sort_values("h")
bb.plot(ax=ax, column=np.clip(bb.h, 0, 60), cmap="viridis", linewidth=0, legend=True,
        legend_kwds={"label": "height (m, clipped at 60)", "shrink": 0.6})
sp.plot(ax=ax, facecolor="none", edgecolor="red", linewidth=0.6)
gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=ax, color="k", linewidth=0.4)
ax.set_title("London building table: height (red outlines: Carbon & Place spikes lowered)")
ax.set_axis_off()
fig.tight_layout()
fig.savefig(CHECKS / "buildings_heights.png", dpi=110)
plt.close(fig)
L += ["![Building heights](buildings_heights.png)", ""]

with open(CHECKS / "buildings.md", "a") as fh:
    fh.write("\n".join(L) + "\n")
print("\n".join(L))
