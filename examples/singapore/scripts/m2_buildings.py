"""M2 checks after 04_buildings: Singapore's own checks of the building table → checks/m2_buildings.md and the height
map checks/buildings_heights.png (plus a CBD close-up, checks/buildings_heights_cbd.png).

- the landmark list (data/landmarks.csv) against the table: the top of the building each row names (its pieces and
  parts), the height source, and the piece under the row's point;
- blobs: pieces of 5,000 m² or more at 30 m or more, and of 2,000 m² or more at 100 m or more (a podium raised to a
  tower's height is the classic failure);
- underground: OSM outlines with layer < 0 or location=underground still in the table;
- HDB: storeys against the table's height on the blocks' footprints.
Run from demos/singapore after 04_buildings: uv run python scripts/m2_buildings.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

from city3d.common import DATA, UTM

HERE = Path(__file__).resolve().parent.parent
CHECKS = HERE / "checks"


def main():
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    lm = pd.read_csv(HERE / "data" / "landmarks.csv")
    o = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    L = ["# Singapore M2: building checks", "", "Made by `scripts/m2_buildings.py` after 04_buildings "
         f"({len(b):,} pieces, {b.area.sum() / 1e6:.2f} km² footprint).", ""]

    # 1. landmarks
    L += ["## 1. Landmarks (data/landmarks.csv) in the table", "",
          "Top: the highest piece named after the row (a building of parts: its highest part), else the piece under "
          "the point. use_height rows should match their listed height (a part-built tower within a few metres: its "
          "parts are capped at the listed height, [buildings.landmarks] cap).", "",
          "| Landmark | listed (m) | use_height | top in the table (m) | h_src | pieces | footprint under the point (m², h) |",
          "|---|---|---|---|---|---|---|"]
    pts = gpd.GeoDataFrame(lm, geometry=gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
    bad = []
    for _, r in pts.iterrows():
        named = b[(b["name"] == r.name_zh) | (b["landmark"] == r.name_zh if "landmark" in b else False)]
        under = b[b.contains(r.geometry)]
        under_s = ", ".join(f"{u.area:,.0f} m² {u.h:.0f} m" for u in under.itertuples()) or "(none)"
        if len(named):
            top = named.h.max()
            src = ",".join(sorted(named.h_src.dropna().unique()))
        elif len(under):
            top, src = under.h.max(), ",".join(sorted(under.h_src.dropna().unique()))
        else:
            top, src = np.nan, ""
        listed = r.height_m
        flag = ""
        if r.use_height and pd.notna(listed) and (pd.isna(top) or abs(top - listed) > 5):
            flag = " **!**"
            bad.append(r.name_zh)
        L.append(f"| {r.name_zh}{flag} | {listed if pd.notna(listed) else ''} | {bool(r.use_height)} | "
                 f"{top:.1f} | {src} | {len(named)} | {under_s} |" if pd.notna(top) else
                 f"| {r.name_zh}{flag} | {listed if pd.notna(listed) else ''} | {bool(r.use_height)} | (none) | | 0 | {under_s} |")
    L += ["", f"use_height rows more than 5 m off: {len(bad)}" + (f" ({', '.join(bad)})" if bad else "") + ".", ""]

    # 2. blobs
    whole = b.copy()
    whole["a"] = whole.area
    blob1 = whole[(whole.a >= 5000) & (whole.h >= 30)].sort_values("a", ascending=False)
    blob2 = whole[(whole.a >= 2000) & (whole.h >= 100)].sort_values("h", ascending=False)
    L += ["## 2. Big footprints at height (merged blobs?)", "",
          f"Pieces of 5,000 m² or more at 30 m or more: {len(blob1)}; of 2,000 m² or more at 100 m or more: {len(blob2)}.",
          "", "| piece | m² | h (m) | h_src | source | osm_id | kind |", "|---|---|---|---|---|---|---|"]
    for r in pd.concat([blob1, blob2]).drop_duplicates(subset=["a", "h"]).itertuples():
        L.append(f"| {r.name if isinstance(r.name, str) else '(unnamed)'} | {r.a:,.0f} | {r.h:.0f} | {r.h_src} | "
                 f"{r.source} | {r.osm_id if isinstance(r.osm_id, str) else ''} | {r.kind} |")

    # 3. underground
    layer = pd.to_numeric(o["layer"], errors="coerce").fillna(0)
    low = o[(layer < 0) | (o["location"] == "underground")]
    inside = b[b["osm_id"].isin(low["osm_id"])] if "osm_id" in b else b.iloc[:0]
    L += ["", "## 3. Underground", "",
          f"OSM outlines with layer < 0 or location=underground: {len(low)}; in the table: {inside.osm_id.nunique()} "
          f"({', '.join(f'{r.name} {r.h:.0f} m' for r in inside.drop_duplicates('osm_id').itertuples())}); left out: "
          + ", ".join(f"{r.name if isinstance(r.name, str) else r.osm_id} (layer {r.layer}, {r.location or '-'})"
                      for r in low[~low.osm_id.isin(inside.osm_id)].itertuples()) + ".",
          f"train_station outlines in the table: {(b.get('osm_building') == 'train_station').sum()} "
          f"(median {b[b.get('osm_building') == 'train_station'].area.median():.0f} m², "
          f"median h {b[b.get('osm_building') == 'train_station'].h.median():.1f} m)."]

    # 3a. the station gate: train_station / transportation pieces of 300 m² or more, or over 6 m (entrances are 4.5 m)
    st = b[b.get("osm_building").isin(["train_station", "transportation"])] if "osm_building" in b else b.iloc[:0]
    bad_st = st[(st.area >= 300) | (st.h > 6)]
    L += ["", f"**Station gate**: train_station / transportation pieces {len(st)} ({st.area.sum():,.0f} m²); of 300 m² or "
          f"more or over 6 m: {len(bad_st)} ("
          + ", ".join(f"{r.osm_id} {r.name if isinstance(r.name, str) else ''} {r.geometry.area:,.0f} m² {r.h:.0f} m"
                      for r in bad_st.itertuples()) + ")."]
    # 3c. pieces overlapping by > 10 % of the smaller (outside a building's own parts)
    import shapely
    j = gpd.sjoin(b[["geometry"]], b[["geometry"]], predicate="intersects")
    j = j[j.index < j.index_right]
    ga, gb = b.geometry.loc[j.index].values, b.geometry.loc[j.index_right].values
    inter = shapely.area(shapely.intersection(ga, gb))
    hh, mm = b["h"].astype(float), b["min_h"].fillna(0).astype(float)
    vert = (np.minimum(hh.loc[j.index].values, hh.loc[j.index_right].values)
            - np.maximum(mm.loc[j.index].values, mm.loc[j.index_right].values))
    ov = j[(inter > 0.1 * np.minimum(shapely.area(ga), shapely.area(gb))) & (vert > 1.0)]
    if "part_of" in b:
        pa, pb = b.part_of.reindex(ov.index).values, b.part_of.reindex(ov.index_right).values
        ov = ov[~(pd.notna(pa) & (pa == pb))]
    L += ["", f"Pieces drawn twice: overlapping another by more than 10 % of the smaller on the map and by over 1 m in height (a building's own parts aside): {len(ov)}"
          + (":" if len(ov) else "."), ""]
    for i, k in zip(ov.index, ov.index_right):
        ra, rk = b.loc[i], b.loc[k]
        f = lambda r: f"{r.osm_id if isinstance(r.osm_id, str) else r.source} {r['name'] if isinstance(r['name'], str) else ''} {r.h:.0f} m"
        L.append(f"- {f(ra)} / {f(rk)}")

    # 3d. recent OSM ids (over 1.2e9: mapped since 2023) at 40 m or more: building sites mapped as finished towers?
    if "osm_id" in b:
        num = pd.to_numeric(b["osm_id"].str[1:], errors="coerce")
        rec = b[(num > 1.2e9) & (b.h >= 40)].sort_values("h", ascending=False).drop_duplicates("osm_id")
        L += ["", f"Recent OSM ids (over 1.2e9) at 40 m or more, for review against TOP dates (Berlayar, One Marina "
              f"Gardens, Tanjong Rhu Riverfront and Crawford Heights left out as under construction): {len(rec)}", ""]
        L += [f"- {r.osm_id} {r.name if isinstance(r.name, str) else ''} {r.osm_building} {r.h:.0f} m ({r.h_src})"
              for r in rec.itertuples()]
    # 3e. estimates of 50 m or more
    if "h_src" in b:
        e50 = b[(b.h_src == "est") & (b.h >= 50)]
        L += ["", f"Estimated pieces at 50 m or more: {len(e50)} (by tag: {e50.osm_building.value_counts().to_dict()}); "
              f"at 80 m or more: " + ", ".join(f"{r.osm_id} {r.osm_building} {r.h:.0f} m"
                                               for r in e50[e50.h >= 80].itertuples())]

    # 3b. OSM outlines lost: in the districts, not skipped or left out by id, above ground, under half covered
    import tomllib
    cfg = tomllib.load(open(HERE / "city.toml", "rb"))["buildings"]
    d0 = gpd.read_file(DATA / "boundary.gpkg").to_crs(UTM).union_all()
    cand = o[o.geometry.representative_point().within(d0) & ~o["building"].isin(cfg.get("osm_skip", []))
             & ~o["osm_id"].isin(cfg.get("exclude", {}).get("osm", [])) & ~o["osm_id"].isin(low["osm_id"])].copy()
    cand["geometry"] = cand.geometry.make_valid()
    u = b.geometry.make_valid().union_all()
    cov = cand.geometry.intersection(u).area / cand.area
    lost = cand[cov < 0.5].assign(cov=cov[cov < 0.5], a=cand.area)
    L += ["", f"OSM outlines (in the districts, not skipped, not left out by id, above ground) under half covered by the "
          f"table: {len(lost)} of {len(cand):,} ({lost.a.sum():,.0f} m²); the largest:", "",
          "| osm_id | building | name | height | levels | m² | covered |", "|---|---|---|---|---|---|---|"]
    for r in lost.sort_values("a", ascending=False).head(15).itertuples():
        L.append(f"| {r.osm_id} | {r.building} | {r.name if isinstance(r.name, str) else ''} | {r.height or ''} | "
                 f"{r.levels if isinstance(r.levels, str) else ''} | {r.a:,.0f} | {r.cov:.0%} |")

    # 4. HDB
    if "max_floor_lvl" in b:
        hb = b[b.max_floor_lvl.notna()]
        L += ["", "## 4. HDB blocks", "",
              f"Pieces with HDB storeys (own or lent): {len(hb):,}; h_src: {hb.h_src.value_counts().to_dict()}; "
              f"metres per storey (h / storeys) median {(hb.h / hb.max_floor_lvl).median():.2f}."]

    # 5. heights by source and district
    d = gpd.read_file(DATA / "boundary.gpkg").to_crs(UTM)
    j = gpd.sjoin(b.assign(geometry=b.representative_point())[["h", "h_src", "geometry"]], d[["name", "geometry"]],
                  predicate="within")
    t = j.groupby(["name", "h_src"]).size().unstack(fill_value=0)
    t["median h"] = j.groupby("name").h.median().round(1)
    cols = list(t.columns)
    L += ["", "## 5. Height sources by district (pieces)", "", "| district | " + " | ".join(map(str, cols)) + " |",
          "|---" * (len(cols) + 1) + "|"]
    L += [f"| {k} | " + " | ".join(str(v) for v in r) + " |" for k, r in zip(t.index, t.values)]
    (CHECKS / "m2_buildings.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

    # height map
    bins = [0, 10, 20, 40, 60, 100, 150, 200, 300]
    cmap = ListedColormap(["#d9d9d9", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#8c2d04", "#4a1486"])
    norm = BoundaryNorm(bins, cmap.N)
    for name, box, fn in [("all", None, "buildings_heights.png"),
                          ("CBD", (103.838, 1.270, 103.866, 1.296), "buildings_heights_cbd.png")]:
        fig, ax = plt.subplots(figsize=(16, 12) if box is None else (12, 11), dpi=110)
        d.boundary.plot(ax=ax, color="#4477aa", lw=0.6)
        bb = b.sort_values("h")
        if box:
            bx = gpd.GeoSeries.from_xy([box[0], box[2]], [box[1], box[3]], crs=4326).to_crs(UTM)
            ax.set_xlim(bx.x.min(), bx.x.max())
            ax.set_ylim(bx.y.min(), bx.y.max())
        bb.plot(ax=ax, column="h", cmap=cmap, norm=norm, linewidth=0.1, edgecolor="#555555")
        if box:
            for r in pts[pts.use_height].itertuples():
                if box[0] <= r.lon <= box[2] and box[1] <= r.lat <= box[3]:
                    ax.plot(r.geometry.x, r.geometry.y, "k+", ms=6)
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        fig.colorbar(sm, ax=ax, shrink=0.6, label="height (m)", ticks=bins)
        ax.set_title(f"Singapore M2: building heights ({name}); + landmark points (use_height)")
        ax.set_aspect("equal")
        ax.set_axis_off()
        fig.savefig(CHECKS / fn, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    main()
