"""04b_quality: district-wide quality checks on the building table, so fixes aren't judged from a few views.

Checks:
  strips     non-OSM footprints under 3 m wide (clipping leftovers beside real buildings)
  overlaps   footprint pairs sharing more than 10 % of the smaller one's area
  jumps      touching footprints whose heights differ by more than 1.5x (split buildings, or a
             podium beside a tower, which is fine)
  invalid    invalid geometries
  slabs      footprints of 2,000 m² or more at 100 m or more (a tower and its podium joined into a wall?)
  needles    slender pieces (height over 8 x the square root of the footprint) that are not part of a
             building made of OSM parts (whose spires and crown pieces are meant to be slender)
  raised     pieces starting above the ground (on a roof; overhangs)
  duplicates footprint pairs overlapping by 90 % of the smaller
The worst 2 km cells for strips and overlaps are listed with coordinates to inspect, and the worst of each
list with its name and position.

Writes checks/quality.md.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from ..common import CFG, CHECKS, DATA, UTM

CELL = 2000


def low_parts(b: gpd.GeoDataFrame, part: pd.Series) -> int:
    """Pieces of part-built buildings far under the height APUR measured over their building (h_med)."""
    if "h_med" not in b:
        return 0
    ref = pd.to_numeric(b["h_med"], errors="coerce")
    return int((part & (b.area >= 300) & (b.h < 0.6 * ref)).sum())


def holes(b: gpd.GeoDataFrame) -> int:
    """Footprints with at least one courtyard (interior ring)."""
    import shapely
    parts = shapely.get_parts(b.geometry.values, return_index=True)
    n = shapely.get_num_interior_rings(parts[0])
    return int(len(np.unique(parts[1][n > 0])))


def height_checks(b: gpd.GeoDataFrame) -> list:
    """Heights against the table's own columns, where it has them: a source's own measured top (roof_top_z -
    ground_elevation: nothing stacked over it), a second height source ([quality] second: h_<second>) and the
    storeys ([quality] storeys x storey_min)."""
    Q = CFG.get("quality", {})
    rows = []
    to_ll = lambda g: g.representative_point().to_crs(4326)
    if "roof_top_z" in b and "ground_elevation" in b:
        own = pd.to_numeric(b["roof_top_z"], errors="coerce") - pd.to_numeric(b["ground_elevation"], errors="coerce")
        floor = CFG["buildings"]["min_h"]
        over = own.notna() & (b.h > np.maximum(own, floor) + 1.0)
        mine = over & (b.h_src.astype(str) == b.source.astype(str))
        rows += [f"| pieces over their own solid's top (roof_top_z − ground_elevation) + 1 m: all / with their source's "
                 f"own height (stacked) | {int(over.sum()):,} / {int(mine.sum()):,} |"]
        bad = b[mine].nlargest(5, "a")
        if len(bad):
            rows += ["| ... the largest stacked: " + "; ".join(
                f"{r.a:,.0f} m² at {r.h:.1f} m (own {o:.1f}) {p.y:.5f},{p.x:.5f}"
                for r, o, p in zip(bad.itertuples(), own[bad.index], to_ll(bad.geometry))) + " | |"]
    sec = Q.get("second")
    if sec and f"h_{sec}" in b:
        v = pd.to_numeric(b[f"h_{sec}"], errors="coerce")
        low = (b.h <= 5) & (v > 2 * b.h)
        far = v.notna() & ((b.h - v).abs() > 8)
        rows += [f"| pieces at 5 m or less that {sec} puts over 2x higher (placeholder heights left) | {int(low.sum()):,} "
                 f"({b.a[low].sum():,.0f} m²) |",
                 f"| pieces over 8 m off {sec}'s height (up / down) | {int((far & (v > b.h)).sum()):,} / "
                 f"{int((far & (v < b.h)).sum()):,} |"]
    st = Q.get("storeys")
    if st and st in b:
        n = pd.to_numeric(b[st], errors="coerce")
        under = n.notna() & (n > 0) & (b.h < n * Q.get("storey_min", 2.5))
        rows += [f"| pieces under {st} x {Q.get('storey_min', 2.5):g} m (the building's storeys: a low wing or yard "
                 f"building of a taller one counts too) | {int(under.sum()):,} ({b.a[under].sum():,.0f} m²; "
                 f"{int((under & (b.a >= 300)).sum()):,} of 300 m² or more) |"]
    return (["| Height check | count |", "|---|---|"] + rows + [""]) if rows else []


def main():
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    invalid = int((~b.is_valid).sum())
    b["geometry"] = b.geometry.make_valid()
    rect = b.geometry.minimum_rotated_rectangle()
    b["width"] = rect.apply(lambda r: min(np.hypot(*np.diff(np.asarray(r.exterior.coords)[:3], axis=0).T))
                            if r.geom_type == "Polygon" else 0.0)
    part = b["part_of"].notna() if "part_of" in b else pd.Series(False, index=b.index)
    # what [buildings] rules keep whatever its size (a cadastre's building parts: bays, stair towers, roof slices;
    # memorial stelae, chimneys) is by design too, like OSM's parts; counted on its own line
    kept = b["keep_small"].fillna(False).astype(bool) if "keep_small" in b else pd.Series(False, index=b.index)
    n_kept_strip = int(((b.width < 3) & kept & ~part).sum())
    n_kept_slender = int(((b.h > 8 * np.sqrt(b.area)) & kept & ~part).sum())
    part = part | kept
    b["strip"] = (b.width < 3) & (b.source != "osm") & ~part

    ov = gpd.sjoin(b[["geometry"]], b[["geometry"]], predicate="overlaps")
    ov = ov[ov.index < ov.index_right]
    inter = np.array([a.intersection(c).area for a, c in
                      zip(b.geometry.loc[ov.index], b.geometry.loc[ov.index_right])])
    small = np.minimum(b.area.loc[ov.index].values, b.area.loc[ov.index_right].values)
    # footprints overlapping in plan but not in height (a lifted slab over a lower part) don't count
    mh = b.get("min_h", pd.Series(0.0, index=b.index)).fillna(0)
    top = np.minimum(b.h.loc[ov.index].values, b.h.loc[ov.index_right].values)
    base = np.maximum(mh.loc[ov.index].values, mh.loc[ov.index_right].values)
    small = np.where(top > base + 0.5, small, np.inf)
    real = ov[inter / small > 0.1]
    dup = ov[inter / small > 0.9]
    b["overlap"] = b.index.isin(real.index) | b.index.isin(real.index_right)

    nb = gpd.sjoin(b[["geometry", "h"]], b[["geometry", "h"]], predicate="touches")
    nb = nb[nb.index < nb.index_right]
    jumps = int(((nb.h_left - nb.h_right).abs() / nb[["h_left", "h_right"]].min(axis=1) > 0.5).sum())

    c = b.centroid
    b["cx"], b["cy"] = (c.x // CELL).astype(int), (c.y // CELL).astype(int)
    per = b.groupby(["cx", "cy"]).agg(n=("strip", "size"), strips=("strip", "sum"), overlaps=("overlap", "sum"))
    per["bad"] = (per.strips + per.overlaps) / per.n

    L = ["# Building table quality", "",
         f"{len(b):,} buildings.", "",
         "| Check | count |", "|---|---|",
         f"| strips under 3 m wide (non-OSM) | {int(b.strip.sum()):,} |",
         f"| footprints overlapping another by > 10 % | {int(b.overlap.sum()):,} |",
         f"| touching pairs with height ratio > 1.5x | {jumps:,} |",
         f"| invalid geometries (before repair) | {invalid} |",
         f"| part pieces under 3 m wide (setbacks, crowns, spires by design) | {int(((b.width < 3) & part).sum()):,} |",
         *([f"| ... of them kept by [buildings] rules (a primary's own parts and structures): under 3 m wide "
            f"{n_kept_strip:,}, slender {n_kept_slender:,} |"] if kept.any() else []),
         f"| footprints with courtyards (holes kept) | {holes(b):,} |",
         f"| part pieces of 300 m² or more under 60 % of the official layer's measured height (h_med) | {low_parts(b, part):,} |",
         f"| OSM ids left out by [buildings] exclude.osm still in the table | {int(b.get('osm_id', pd.Series(dtype=str)).isin(CFG['buildings']['exclude'].get('osm', [])).sum())} |", ""]
    b["a"] = b.area
    slabs = b[(b.a >= 2000) & (b.h >= 100)]
    needles = b[(b.h > 8 * np.sqrt(b.a)) & ~part]
    raised = b[b.get("min_h", pd.Series(0, index=b.index)).fillna(0) > 0]
    # lifted pieces: what lies under them (other buildings' roofs up to their base, or their own parts)
    unsupported = 0
    if len(raised):
        lj = gpd.sjoin(raised[["geometry"]].reset_index(names="r"), b[["geometry", "h"]].reset_index(names="u"),
                       predicate="intersects")
        lj = lj[lj.r != lj.u]
        lj["a"] = [b.geometry[r].intersection(b.geometry[u]).area for r, u in zip(lj.r, lj.u)]
        sup = lj.groupby("r").a.sum().reindex(raised.index).fillna(0)
        unsupported = int((sup < 0.5 * raised.area).sum())
    floors = pd.to_numeric(b.get("numfloors"), errors="coerce") if "numfloors" in b else pd.Series(np.nan, index=b.index)
    per_floor = b.h / floors.where(floors > 0)
    tall_floors = b[(per_floor > 6) & (b.h > 30) & ~part]
    fill = b[(b.source == "osm") & (b.h >= 20)]
    L += ["| Check | count |", "|---|---|",
          f"| footprints ≥ 2,000 m² at ≥ 100 m | {len(slabs):,} |",
          f"| lifted pieces with less than half of them over anything (overhangs, cantilevers) | {unsupported:,} |",
          f"| lifted pieces whose base is at or above their top | {int((raised.min_h >= raised.h).sum()):,} |",
          f"| over 6 m per floor of the lot (and over 30 m), outside part-built buildings | {len(tall_floors):,} |",
          f"| OSM fill at 20 m or more (the official layer lacks them) | {len(fill):,} |",
          f"| slender pieces (h > 8 √area) outside part-built buildings | {len(needles):,} |",
          f"| pieces starting above the ground (min_h > 0) | {len(raised):,} |",
          f"| pairs overlapping by ≥ 90 % of the smaller (duplicates) | {len(dup):,} |", ""]
    L += height_checks(b)
    to_ll = lambda g: g.representative_point().to_crs(4326)
    for title, t in (("Largest footprints at 100 m or more", slabs.nlargest(10, "a")),
                     ("Most slender pieces outside part-built buildings", needles.assign(r=needles.h / np.sqrt(needles.a)).nlargest(10, "r"))):
        L += [f"{title}:", "", "| name | h (m) | area (m²) | h from | lat, lon |", "|---|---|---|---|---|"]
        for (_, r), pt in zip(t.iterrows(), to_ll(t.geometry)):
            L.append(f"| {r['name'] if pd.notna(r.get('name')) else ''} | {r.h:.0f} | {r.a:,.0f} | {r.h_src} | "
                     f"{pt.y:.5f}, {pt.x:.5f} |")
        L.append("")
    L += [
         "Worst 2 km cells (≥ 300 buildings) by strips + overlaps:", "",
         "| lat, lon | buildings | strips | overlaps |", "|---|---|---|---|"]
    for (cx, cy), r in per[per.n >= 300].sort_values("bad", ascending=False).head(8).iterrows():
        ll = gpd.GeoSeries.from_xy([cx * CELL + CELL / 2], [cy * CELL + CELL / 2], crs=UTM).to_crs(4326).iloc[0]
        L.append(f"| {ll.y:.4f}, {ll.x:.4f} | {int(r.n):,} | {int(r.strips):,} | {int(r.overlaps):,} |")
    (CHECKS / "quality.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

