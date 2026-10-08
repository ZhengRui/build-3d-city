"""Hong Kong M2: what the building table did with LandsD's rows and OSM's fill, the towers on podiums and slopes,
the landmarks against the list, a spot check of the tallest towers against CTBUH / Wikipedia, and a height map.

Run from demos/hongkong after scripts/m2_landsd_prep.py, 01_osm, 02_landsd and 04_buildings:
    uv run python scripts/m2_checks.py
Writes checks/m2_heights.md and checks/m2_heights.png (loads the table and both sources: ~1 GB).
"""
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm  # noqa: E402

from city3d.common import CFG, CHECKS, DATA, UTM, boundary, underground_mask  # noqa: E402

T0 = time.time()
poly = boundary().geometry.iloc[0]
L = ["# Hong Kong M2: heights from the street, the fill, the checks", "",
     f"`scripts/m2_checks.py` ({time.strftime('%Y-%m-%d %H:%M')}). Inside the boundary (a footprint counts by its "
     "representative point). Heights are m above the lowest ground under the outline (where 06_tiles stands the "
     "building).", ""]

# ---- LandsD rows -------------------------------------------------------------------------------------------------
p = gpd.read_file(DATA / "landsd_prepared/landsd_E600_ground.gpkg").to_crs(UTM)
p = p[p.geometry.representative_point().within(poly)].copy()
b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
b["a"] = b.area
own = b[b.source == "landsd"]
typ = p.BuildingBlockType.value_counts()
L += ["## 1. LandsD rows", "",
      "| | rows | note |", "|---|---|---|",
      f"| in the boundary | {len(p):,} | {', '.join(f'{k} {v:,}' for k, v in typ.items())} |",
      f"| open-sided structures | {typ.get('Open-sided Structure', 0):,} | left out (covered walkways, canopies, "
      "footbridge roofs: no walls from the ground) |",
      f"| temporary structures without a TopHeight | {int((p.top_note != '').sum()):,} | one storey (ground + 3 m); "
      f"{int(((p.top_note != '') & (p.area < 12)).sum()):,} of them under 12 m² go with min_piece |",
      f"| top at most 0.5 m over the lowest ground | {int((p.m2_drop == 'sunk').sum()):,} | left out (station boxes "
      "under parks, tanks, blocks cut into slopes) |",
      f"| towers without a TopHeight | {int((p.BuildingBlockType.eq('Tower') & p.TopHeight.isna()).sum())} | OSM's "
      "height or the default |",
      f"| over a pit in the 2020 LiDAR (lowest ground < 1 mPD) | {int(p.pit.sum()):,} | ground = the street around "
      f"them (median {p.loc[p.pit, 'ground_mpd'].median():.1f} mPD; the LiDAR's down to "
      f"{p.loc[p.pit, 'ground_lidar_mpd'].min():.1f}) |",
      f"| base 3 m+ over the highest ground under them, on other rows | "
      f"{int(((p.BaseHeight - p.ground_max_mpd >= 3) & (p.support >= 0.5)).sum()):,} | towers on podiums: from the "
      "ground, cut out of the podium |",
      f"| ... on nothing, 10 m or less over their base | {int(p.elevated.sum()):,} | raised pieces (footbridges, "
      f"link bridges, decks): {int((own.min_h > 0).sum()):,} in the table after the 3 m strip rule |",
      f"| ... on nothing, taller | {int(p.deck_tower.sum()):,} | towers whose podium deck the layer leaves out "
      "(open-sided, or a gap over the podium roof): from the ground |",
      f"| in the table | {len(own):,} | after strips < 3 m wide, duplicates inside a taller row, volume dedupe |",
      ""]

# ---- OSM -----------------------------------------------------------------------------------------------------
o_all = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)   # (load_osm already drops what underground_drop drops)
o_all = o_all[o_all.geometry.representative_point().within(poly)]
lay = pd.to_numeric(o_all["layer"], errors="coerce").fillna(0)
low = (o_all["location"] == "underground") | (lay < 0)
ug = underground_mask(o_all) & ~low
skip = o_all["building"].isin(CFG["buildings"]["osm_skip"])
fill = b[b.source == "osm"]
L += ["## 2. OSM", "",
      f"- {len(o_all):,} OSM buildings in the boundary; left out: {int(low.sum())} at layer < 0 or "
      f"location=underground, {int(ug.sum())} more tagged underground / indoor / on a level below 0 "
      f"([osm] underground_drop), {int(skip.sum()):,} by osm_skip "
      f"({', '.join(f'{k} {v}' for k, v in o_all.loc[skip, 'building'].value_counts().items())}), and the untagged "
      "station boxes (station_untagged = \"drop\": 21).",
      f"- OSM fills what LandsD lacks: {len(fill):,} pieces, {fill.a.sum() / 1e4:.1f} ha, median {fill.h.median():.1f} "
      f"m, max {fill.h.max():.1f} m (fill_max_h 20 m: a taller OSM building LandsD lacks is gone or not built; "
      f"heights {fill.h_src.value_counts().to_dict()}).", ""]
names = o_all.loc[low | ug, "name"].dropna()
if len(names):
    L += ["Underground outlines left out (named): " + ", ".join(sorted(set(names))[:40]) + ".", ""]

# ---- towers on podiums and slopes --------------------------------------------------------------------------------
CASES = ["Times Square Tower One", "Times Square Tower Two", "Hopewell Centre", "Two International Finance Centre",
         "One International Finance Centre", "International Commerce Centre", "Three Pacific Place",
         "One Pacific Place", "Island Shangri-La Hotel", "Conrad Hong Kong", "JW Marriott Hotel", "Langham Place",
         "Elements", "Sorrento Tower 1", "The Cullinan II", "K11 Atelier", "apm Millennium City 5", "Hysan Place",
         "Highcliff", "The Summit", "The Belcher's Tower 6", "The Leighton Hill Tower 2", "Champion Tower",
         "Central Plaza", "Bank of China Tower"]
L += ["## 3. Towers on podiums and on slopes", "",
      "M1's height was TopHeight − BaseHeight (the row over its own base); now TopHeight − the lowest ground under "
      "the outline (LiDAR, mPD). Podium: the LandsD podium row the tower lies in, after volume_dedupe cut the tower "
      "out of it.", "",
      "| LandsD row | base (mPD) | top (mPD) | ground low / high (mPD) | M1: top − base | M2 built (m) | from |",
      "|---|---|---|---|---|---|---|"]
for n in CASES:
    s = own[own.buildingnameen.fillna("").str.lower() == n.lower()]
    if not len(s):
        L.append(f"| {n} | | | | | (not found) | |")
        continue
    r = s.sort_values("h", ascending=False).iloc[0]
    q = p[p.BuildingCSUID == r.buildingcsuid]
    gmax = q.ground_max_mpd.iloc[0] if len(q) else np.nan
    L.append(f"| {n} | {r.baseheight:.1f} | {r.topheight:.1f} | {r.ground_elevation:.1f} / {gmax:.1f} | "
             f"{r.topheight - r.baseheight:.1f} | {r.h:.1f} | {r.h_src} |")
slope = own[(own.h >= 60)].merge(p[["BuildingCSUID", "ground_max_mpd"]], left_on="buildingcsuid",
                                 right_on="BuildingCSUID", how="left")
st = slope[(slope.ground_max_mpd - slope.ground_elevation) >= 15]
L += ["", f"Towers of 60 m or more on a slope (the ground under the outline varies by 15 m or more): {len(st):,} of "
      f"{len(slope):,}; median fall {(st.ground_max_mpd - st.ground_elevation).median():.1f} m. Their bottom is the "
      "lowest ground under the outline (the downhill foot; 06_tiles' Terrain.bases does the same), so the walls show "
      "the full drop on the downhill side and the top lands at the surveyed TopHeight.", ""]

# ---- landmarks -----------------------------------------------------------------------------------------------------
lm = pd.read_csv("data/landmarks.csv")
lm = lm[lm.height_m.notna() & lm.lat.notna()]
L += ["## 4. Landmarks: built against the list", "",
      "| Landmark | listed (m) | type | use_height | built (m) | from |", "|---|---|---|---|---|---|"]
for r in lm.itertuples():
    s = b[b.landmark == r.name_zh]
    if r.use_height and len(s):
        k = s.h.idxmax()
        L.append(f"| {r.name_en} | {r.height_m:g} | {r.height_type} | yes | {b.at[k, 'h']:.1f} | {b.at[k, 'h_src']} |")
    else:
        pt = gpd.GeoSeries(gpd.points_from_xy([r.lon], [r.lat]), crs="EPSG:4326").to_crs(UTM).iloc[0]
        near = b[b.distance(pt) <= 40]
        if len(near):
            k = near.distance(pt).idxmin()
            L.append(f"| {r.name_en} | {r.height_m:g} | {r.height_type} | no | {b.at[k, 'h']:.1f} (the piece "
                     f"nearest the point: {b.at[k, 'buildingnameen']}) | {b.at[k, 'h_src']} |")
        else:
            L.append(f"| {r.name_en} | {r.height_m:g} | {r.height_type} | no | — | |")
L.append("")

# ---- spot check ------------------------------------------------------------------------------------------------
# reference heights: Wikipedia's "List of tallest buildings in Hong Kong" (architectural top: spires and crowns, no
# masts) and the buildings' infoboxes (roof), read 6 Oct 2026 (M2 fix round); landmarks.csv's CTBUH figures where it has
# them (Hopewell 216: CTBUH; Wikipedia's list says 222)
W, I = "Wikipedia list (architectural)", "Wikipedia infobox"
REF = [("International Commerce Centre", 484, W), ("Two International Finance Centre", 412, W),
       ("Central Plaza", 309, f"{I}: roof (373.9 with the mast)"), ("Bank of China Tower", 315, f"{I}: roof (367.4 to the masts)"),
       ("One Island East", 298, W), ("Cheung Kong Center", 283, W), ("The Cullinan II", 270, W),
       ("The Masterpiece", 261, W), ("Sorrento Tower 1", 256, W), ("Langham Place", 255, W), ("Highcliff", 252, W),
       ("The Harbourside Tower 1", 251, W), ("Lee Garden One", 240, f"{W} (Manulife Plaza)"), ("Sorrento Tower 2", 236, W),
       ("The Hermitage Tower 1", 234, W), ("Harbourfront Landmark Tower 1", 233, W), ("Moontower", 231, f"{W} (The Arch)"),
       ("One Taikoo Place", 229, W), ("The Belcher's Tower 6", 227, W), ("Hopewell Centre", 216, "CTBUH (landmarks.csv)"),
       ("The Summit", 219, W), ("Sun Hung Kai Centre", 215, W), ("Sorrento Tower 3", 218, W), ("Island Shangri-La Hotel", 213, W),
       ("One International Finance Centre", 210, W), ("Four Seasons Place", 205, W), ("Times Square Tower One", 194, "CTBUH (landmarks.csv)"),
       ("One Exchange Square", 188, f"{I}: roof"), ("Two Exchange Square", 188, f"{I}: roof"), ("AIA Central", 185, I),
       ("Lippo Centre Tower 1", 186, "CTBUH (landmarks.csv)"), ("HSBC Main Building", 178.8, I), ("Jardine House", 178.5, I)]
L += ["## 5. Spot check: the tallest towers against CTBUH / Wikipedia", "",
      "Built: the table's tallest piece of that LandsD name (landmark rows apart, LandsD's own height: TopHeight − "
      "the lowest ground). More than 8 m short: crowns and spires LandsD leaves out, rows of data/landmarks.csv with use_height "
      "false for M4 (the boxes keep LandsD's surveyed roof).", "",
      "| Building | reference (m) | type | LandsD from the ground (m) | built (m) | built − ref | M1 top − base |",
      "|---|---|---|---|---|---|---|"]
d, rr = [], []
for n, ref, t in REF:
    s = own[own.buildingnameen.fillna("").str.lower() == n.lower()]
    if not len(s):
        L.append(f"| {n} | {ref:g} | {t} | — | — | | |")
        continue
    r = s.loc[s.h.idxmax()]
    data = r.roof_top_z - r.ground_elevation
    d.append(r.h - ref)
    rr.append(ref)
    L.append(f"| {n} | {ref:g} | {t} | {data:.1f} | {r.h:.1f} ({r.h_src}) | {r.h - ref:+.1f} | "
             f"{r.topheight - r.baseheight:.1f} |")
d = np.array(d)
L += ["", f"{len(d)} towers: built − reference median {np.median(d):+.1f} m, median abs {np.median(np.abs(d)):.1f} m, "
      f"within 10 m {np.mean(np.abs(d) <= 10):.0%}, within 5 % {np.mean(np.abs(d) <= 0.05 * np.array(rr)):.0%}.", ""]

# ---- storeys_fix, raised pieces -----------------------------------------------------------------------------------
sf = p[p.top_note == "storeys_fix"].copy()
sf["old"] = sf.TopHeight - sf.ground_mpd
sf["new"] = sf.top_mpd - sf.ground_mpd
ll = sf.to_crs("EPSG:4326").geometry.representative_point()
L += ["## 6. storeys_fix: TopHeight under 2.2 m a storey", "",
      f"{len(sf)} LandsD blocks of 8+ storeys and 150 m²+ whose TopHeight gave them under 2.2 m a storey (and no row of "
      "the same name beside them carries those storeys) are raised to storeys × 4.0 m (offices and industrial blocks, "
      "by name), 2.9 m (30+ storeys) or 3.1 m (column top_note = storeys_fix; LandsD's own figure in storey_m_landsd). "
      f"DateStamp 2020-09-08 on {int((pd.to_datetime(sf.DateStamp, unit='ms', errors='coerce').dt.strftime('%Y-%m-%d') == '2020-09-08').sum()) if 'DateStamp' in sf else '?'} of them.", "",
      "| LandsD row | storeys | LandsD (m) | now (m) | lat, lon |", "|---|---|---|---|---|"]
for r, q in zip(sf.sort_values("new", ascending=False).itertuples(), ll.reindex(sf.sort_values("new", ascending=False).index)):
    L.append(f"| {r.BuildingNameEN if isinstance(r.BuildingNameEN, str) else '(unnamed)'} | {r.Storeys:.0f} | {r.old:.1f} | "
             f"{r.new:.1f} | {q.y:.5f}, {q.x:.5f} |")
L += ["", f"Raised pieces: {int(p.elevated.sum())} rows on nothing ({int((p.elevated & (p.TopHeight - p.BaseHeight > 10)).sum())} "
      f"of them sky bridges over 10 m thick, base 40 m+ over the ground: "
      f"{', '.join(p.loc[p.elevated & (p.TopHeight - p.BaseHeight > 10), 'BuildingNameEN'].fillna('(unnamed)'))}); "
      f"{int(p.seated.sum())} of them lie 80 %+ over a lower row whose roof is at most 15 m under them and sit on that roof "
      "(Elements' decks, LOHAS Park's).", ""]

# ---- map ---------------------------------------------------------------------------------------------------------
fig = plt.figure(figsize=(24, 26))
axes = [fig.add_subplot(2, 1, 1), fig.add_subplot(2, 2, 3), fig.add_subplot(2, 2, 4)]
bounds = [0, 10, 20, 40, 60, 100, 150, 200, 300, 500]
cmap = plt.get_cmap("viridis", len(bounds) - 1)
norm = BoundaryNorm(bounds, cmap.N)
order = b.sort_values("h")
for ax, (title, box) in zip(axes, [("Hong Kong E: building heights (m from the lowest ground)", None),
                                   ("Central, Admiralty, Wan Chai", (114.150, 22.272, 114.185, 22.290)),
                                   ("West Kowloon, Tsim Sha Tsui, Jordan", (114.155, 22.292, 114.180, 22.312))]):
    g = order
    if box:
        bb = gpd.GeoSeries([shapely.box(*box)], crs="EPSG:4326").to_crs(UTM).iloc[0]
        g = order[order.intersects(bb)]
        ax.set_xlim(bb.bounds[0], bb.bounds[2]); ax.set_ylim(bb.bounds[1], bb.bounds[3])
    gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=ax, color="0.6", lw=0.6)
    g.plot(ax=ax, column="h", cmap=cmap, norm=norm, lw=0)
    lab = g[g.h >= (300 if not box else 200)].drop_duplicates("buildingnameen")
    for r in lab.itertuples():
        c = r.geometry.representative_point()
        nm = r.buildingnameen if isinstance(r.buildingnameen, str) else (r.name if isinstance(r.name, str) else "")
        ax.annotate(f"{nm[:22]} {r.h:.0f}", (c.x, c.y), fontsize=9,
                    color="crimson")
    ax.set_title(title); ax.set_axis_off(); ax.set_aspect("equal")
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
fig.colorbar(sm, ax=axes, shrink=0.6, ticks=bounds, label="m")
fig.savefig(CHECKS / "m2_heights.png", dpi=110, bbox_inches="tight")
L += ["![heights](m2_heights.png)", "", f"({time.time() - T0:.0f} s)"]
(CHECKS / "m2_heights.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
