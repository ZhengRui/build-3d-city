"""The M2 fix round's checks (critic round 1): the same measures on the table before the round
(../data/london/buildings_m2_before.gpkg, a copy of M2's table) and after it. Appends "M2 fix round" to
checks/buildings.md. Run after scripts/m2_buildings.py from demos/london: `uv run python scripts/m2_fixes.py`
(~1 GB, 1 min). Without the before copy only the after column is filled.
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from city3d.common import CFG, CHECKS, DATA, RAW, UTM, boundary

B = CFG["buildings"]
poly = boundary().geometry.iloc[0]
after = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
f0 = DATA / "buildings_m2_before.gpkg"
before = gpd.read_file(f0).to_crs(UTM) if f0.exists() else None
osm = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
osm["geometry"] = osm.geometry.make_valid()
osm = osm[osm.geometry.representative_point().within(poly)]
water = gpd.read_file(RAW / B["water"]["path"], bbox=tuple(gpd.GeoSeries([poly], crs=UTM).to_crs(27700).total_bounds)) \
    .to_crs(UTM).geometry.make_valid().union_all() if B.get("water") else None
ll = lambda g: f"{g.representative_point().y:.5f}, {g.representative_point().x:.5f}"  # noqa: E731
wgs = lambda s: s.to_crs(4326)  # noqa: E731
RELIG = set(B["spikes"].get("body_tags", []))


def coverage(b):
    """Share of each OSM outline (not skipped by tag, not left out by id, not underground) the table covers."""
    o = osm[~osm.building.isin(B["osm_skip"]) & ~osm.osm_id.isin(B["exclude"].get("osm", []))
            & (osm["location"] != "underground")]
    ov = gpd.overlay(o[["osm_id", "geometry"]], b[["geometry"]].assign(geometry=b.geometry.make_valid()),
                     how="intersection", keep_geom_type=True)
    cov = ov.dissolve("osm_id").area / o.set_index("osm_id").area
    return o.assign(cov=o.osm_id.map(cov).fillna(0).values)


def spikes_left(b):
    s = b[b.part_of.isna() & b.h_src.eq("carbon") & b.h_osm_tag.isna() & (b.h >= 30)]
    return s[(s.h > 3.5 * s.hmean_carbon) | (s.hmean_carbon < 6)]


def podiums_left(b):
    return b[b.part_of.isna() & b.h_src.eq("carbon") & b.h_osm_tag.isna() & (b.area >= 1000)
             & (b.h > 2 * b.hmean_carbon) & (b.h > 25)]


def default_big(b):
    return b[(b.h_src == "default") & (b.area >= 2000)]


def wet_fill(b):
    if water is None:
        return b.iloc[:0]
    f = b[(b.source != "osm") & b.intersects(water)]
    wet = f.intersection(water).area
    return f[(wet >= 20) & (f.min_h.fillna(0) < B["water"]["deck"] - 0.5)]


def overlaps(b):
    g = shapely.make_valid(b.geometry.values)
    j = gpd.sjoin(b[["geometry"]].reset_index(names="i"), b[["geometry"]].reset_index(names="k"), predicate="intersects")
    j = j[j.i < j.k]
    pos = pd.Series(np.arange(len(b)), index=b.index)
    gi, gk = g[pos[j.i].values], g[pos[j.k].values]
    inter = shapely.area(shapely.intersection(gi, gk))
    small = np.minimum(shapely.area(gi), shapely.area(gk))
    h, m = b.h.astype(float), b.min_h.fillna(0).astype(float)
    vert = np.minimum(h[j.i].values, h[j.k].values) - np.maximum(m[j.i].values, m[j.k].values)
    po = b.part_of
    same = po[j.i].notna().values & (po[j.i].values == po[j.k].values)
    return int(((inter >= np.maximum(5, 0.1 * small)) & (vert > 1) & ~same).sum())


def needles(b):
    return b[b.part_of.isna() & (b.h >= 60) & (b.area < 300)]


rows = []
cov_a = coverage(after)
cov_b = coverage(before) if before is not None else None
low_a = cov_a[cov_a["cov"] < 0.5]
low_b = cov_b[cov_b["cov"] < 0.5] if cov_b is not None else None
n = lambda f: (len(f(before)) if before is not None else "")  # noqa: E731
rows += [("OSM outlines in the districts covered under 50 % by the table (not skipped by tag, not excluded)",
          f"{len(low_b):,} ({low_b.area.sum():,.0f} m²)" if low_b is not None else "",
          f"{len(low_a):,} ({low_a.area.sum():,.0f} m²)"),
         ("... of them holding building:parts or over 5,000 m²",
          "" if low_b is None else f"{int((low_b.area > 5000).sum())} over 5,000 m²",
          f"{int((low_a.area > 5000).sum())} over 5,000 m²"),
         ("spikes left: no OSM height, top ≥ 30 m over 3.5× its mean or over a mean < 6 m", n(spikes_left), len(spikes_left(after))),
         ("podium walls left: ≥ 1,000 m², top > 2× mean and > 25 m, no OSM height", n(podiums_left), len(podiums_left(after))),
         ("footprints ≥ 2,000 m² at the default height", n(default_big), len(default_big(after))),
         ("fill pieces over the tidal Thames (≥ 20 m²) not on the deck", n(wet_fill), len(wet_fill(after))),
         ("pieces of ≥ 60 m under 300 m² outside part-built buildings (needles)", n(needles), len(needles(after))),
         ("pairs overlapping on the map (10 %, 5 m²) and in height (> 1 m), not parts of one building",
          overlaps(before) if before is not None else "", overlaps(after))]
L = ["", "## M2 fix round (scripts/m2_fixes.py)", "",
     "The critic's round-1 findings against the table before the round (M2's) and after it.", "",
     "| Check | before | after |", "|---|---|---|"]
L += [f"| {a} | {b_} | {c} |" for a, b_, c in rows]

# named cases
def show(b, ids=(), names=()):
    out = []
    for i in ids:
        x = b[b.osm_id == i]
        out.append(f"{i}: " + (f"{x.h.max():.0f} m, {x.area.sum():,.0f} m² ({', '.join(sorted(set(x.h_src.astype(str))))})"
                               if len(x) else "not in the table"))
    for nm in names:
        x = b[b.name.fillna("").eq(nm) | b.landmark.fillna("").eq(nm)]
        out.append(f"{nm}: " + (f"{x.h.max():.0f} m, {x.area.sum():,.0f} m², {len(x)} pieces "
                                f"({', '.join(sorted(set(x.h_src.astype(str))))})" if len(x) else "not in the table"))
    return out
cases = [("The O2", ["r1895281"], ["The O2 (Millennium Dome)"]),
         ("Outlines with parts", ["w1387097848", "w30805750", "w568378543", "w568378548", "w1412262630", "w270499391",
                                  "w82770894", "w702815278"], []),
         ("Underground filter", ["r6036811", "w680050665"], []),
         ("Spikes", ["r19322385", "w119723635", "w41657430", "w1215655386", "w183366010", "r19612706", "w897666931",
                     "w968820138", "w101530134"], []),
         ("Churches", ["w420026096", "w79107228", "w5983916"], ["St Mary-le-Bow", "St Bride's Church (steeple)"]),
         ("Big footprints", ["w4256246", "w15694166", "w4959629", "w372841786", "w25913652", "w151744360"], []),
         ("Landmark rows", ["w791658610"], ["40 Charter Street", "100 Bishopsgate"]),
         ("Blackfriars", ["w147969007"], [])]
L += ["", "Named cases (before → after):", ""]
for title, ids, names in cases:
    bb = show(before, ids, names) if before is not None else [""] * (len(ids) + len(names))
    aa = show(after, ids, names)
    L.append(f"- **{title}**: " + "; ".join(f"{x} → {y.split(': ', 1)[1]}" for x, y in zip(bb, aa)))

# coverage exceptions
L += ["", f"OSM outlines covered under 50 % after the round ({len(low_a)}; the largest 25, with why):", "",
      "| OSM id | tag | name | m² | covered | layer | location |", "|---|---|---|---|---|---|---|"]
for _, r in low_a.sort_values("cov").assign(a=low_a.area).nlargest(25, "a").iterrows():
    L.append(f"| {r.osm_id} | {r.building} | {r['name'] if pd.notna(r['name']) else ''} | {r.a:,.0f} | "
             f"{r['cov']:.0%} | {r.layer if pd.notna(r.layer) else ''} | {r.location if pd.notna(r.location) else ''} |")
L += ["", "Tags among them: " + ", ".join(f"{k} {v}" for k, v in low_a.building.value_counts().head(10).items()) + "."]

# churches and other religious buildings lowered to their body: spires and domes for M4
rel = after[after.osm_building.isin(RELIG) & after.h_src.astype(str).str.contains("~") & after.spike_carbon.notna()]
L += ["", f"Religious and civic buildings without parts lowered to their body (mean × {B['spikes'].get('body_scale', 1.2)}, "
      f"or OSM's levels): {len(rel)}. Their spires, towers and domes are M4's landmark pass:", "",
      "| name | OSM tag | lidar top (m) | body now (m) | m² | lat, lon |", "|---|---|---|---|---|---|"]
for (_, r), g in zip(rel.sort_values("spike_carbon", ascending=False).iterrows(),
                     wgs(rel.sort_values("spike_carbon", ascending=False).geometry)):
    L.append(f"| {r['name'] if pd.notna(r['name']) else ''} | {r.osm_building} | {r.spike_carbon:.0f} | {r.h:.0f} | "
             f"{r.geometry.area:,.0f} | {ll(g)} |")
L.append("")
with open(CHECKS / "buildings.md", "a") as fh:
    fh.write("\n".join(L) + "\n")
print("\n".join(L))
