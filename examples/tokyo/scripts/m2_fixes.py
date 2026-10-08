"""Tokyo M2: the generated building settings -> city.toml between "# BEGIN m2_fixes" / "# END m2_fixes" ([buildings]
keep, set_h, fix_h) and "# BEGIN m2_exclude" / "# END m2_exclude" ([buildings.exclude]), with --toml. Each rule prints
what it touches (checks/m2_fixes.md). Reads plateau_buildings.gpkg (02_plateau) and osm_buildings.gpkg.

1. OSM buildings PLATEAU leaves out (M2): the government quarter (the Diet, the ministries, the Kantei, the Supreme
   Court, the palace) and a few towers: an OSM outline in D of 300 m² or more, PLATEAU covering under 30 % of it,
   not a canopy, site or ruin nor below ground; unnamed untagged outlines of 1,000 m² or more are unsure (left out).
2. Broken LOD1 solids (fix round, critic 1): storeys x 3 > 5 x height, or under 5 m on 5,000 m² or more (Hotel New
   Otani: one 28,080 m² solid at 3.0 m with 40 storeys): left out, and the OSM outlines on them kept.
3. Construction stubs (fix round): PLATEAU surveyed towers completed in 2024-26 while they were being built. A
   building with 15+ storeys under 2.6 m a storey, or under an OSM tower outline (height or levels x 3.5 of 60 m or
   more, up to 3,000 m²) reaching under half of it: the OSM tower outline is kept over it (its PLATEAU pieces are
   clipped round it); a stub with no such outline is listed for the known issues.
4. LOD1 towers over big low blocks (fix round): a LOD1 solid of 1,000 m² or more whose measuredHeight is over 1.5 x its
   block's top is capped to that top ([buildings] fix_h) only where its storeys don't carry the measuredHeight
   only in clear cases (storeys x 6 m under it, over 2 x the block's top, 10,000 m²+): NHK (8 F, 75.7 m on 23,509 m²);
   Sumida City Hall (19 F, 86.3 m), Sophia University, the Budokan keep their measuredHeight.
5. Lone roof levels (fix round): a roof level under 100 m² more than 30 m over every level of its building it touches
   (a mast or a crown's tip drawn as a prism: 163.7 m on 71 m² beside Otemachi Tower) comes down to the highest of
   them (fix_h); the Docomo Yoyogi building's stepped clock spire is kept (PLATEAU's own solid, a figure in M4).
Run from demos/tokyo: uv run python scripts/m2_fixes.py [--toml]  (whole-city footprints: under the pipeline lock)
"""
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
DATA = HERE.parent / "data" / "tokyo"
UTM = "EPSG:32654"
LEVEL_H = 3.5
SKIP = {"roof", "construction", "ruins", "no", "carport", "shelter", "bridge", "parking"}
NOT = {
    "w624764359": "東京駅一番街: the mall under Tokyo Station's Yaesu side (a B1 mall; levels=1)",
    "r8159112": "千代田区立神田橋公園: a park over the expressway, not a building",
    "w134923823": "アクアフィールド芝公園: building=no",
    "r4856155": "an untagged train_station outline at Tokyo Station (the station's own solids are PLATEAU's)",
}
# never built (left out by id): the Tokyo Station Ichibangai mall outline (mostly B1), and the structures for M4
EXCLUDE_OSM = ["w624764359"]
EXCLUDE_GML = {
    "bldg_7aff4a51-be8b-405b-abe4-ac489697cbc8": "Tokyo Tower's lattice (5,296 m² to 332 m, its roofs the decks): M4 figure",
    "bldg_58ab8c46-8369-49c4-86cf-6912bbc4efe1#r0": "the Skytree's shaft, 467 m: M4 figure",
    "bldg_58ab8c46-8369-49c4-86cf-6912bbc4efe1#r1": "the Skytree's shaft, 378 m: M4 figure",
    # (M4 landmarks, b-tk-m4l) pieces the figures of scripts/m4l_structures.py replace
    "bldg_b9141e64-a2c8-4da1-97a6-e427459a44dc": "Sensō-ji's five-storey pagoda (a 52.3 m prism): M4 figure",
    "bldg_89e579d5-6c3b-41ec-b0f4-8050d8f6e4ed#r0": "Sensō-ji's main hall (roof level): M4 figure",
    "bldg_89e579d5-6c3b-41ec-b0f4-8050d8f6e4ed#r1": "Sensō-ji's main hall (eaves level): M4 figure",
    "bldg_89e579d5-6c3b-41ec-b0f4-8050d8f6e4ed#r2": "Sensō-ji's main hall (stair hood): M4 figure",
    "bldg_8760bd58-39ef-476c-997c-773ba8e3018a#r0": "Sensō-ji's Hōzōmon (roof level): M4 figure",
    "bldg_8760bd58-39ef-476c-997c-773ba8e3018a#r1": "Sensō-ji's Hōzōmon (lower roof): M4 figure",
    "bldg_52945d0d-a897-4d55-b35c-a8bcca773e53#r0": "Docomo Yoyogi's spire (240.6 m prism): M4 figure",
    "bldg_52945d0d-a897-4d55-b35c-a8bcca773e53#r1": "Docomo Yoyogi's cap (218.2 m prism): M4 figure",
    "bldg_6af58cef-669e-4aca-bc01-355e870d1ad5#r0": "Tokyo Station's two domes as 34.6 m prisms: M4 figures",
    "bldg_fd1573b3-1981-4526-958f-b6e64f09f390#r0": "Fuji TV's sphere as a 758 m² cylinder (with two roof pieces, rebuilt as figures): M4 figure",
    "bldg_82bd69b3-99c3-4c88-850d-8e33b9b43829#r0": "TEPCO head office's rooftop mast as a 173 m² prism to 108.9 m: M4 figure",
    "bldg_39c3ea17-6632-4888-8ccb-8022c6e40cac#r0": "Nikolai-dō's dome as a 28.7 m prism: M4 figure",
    # (M4 fix round, b-tk-m4f)
    "bldg_fd1573b3-1981-4526-958f-b6e64f09f390#r2": "Fuji TV's grid between the two towers filled solid (4,453 m² to 123.8 m): M4 fix round, rebuilt as the open grid figure",
    "bldg_ecf0af31-eb0d-4cac-be67-40274365a61d#r1": "a 1,226 m² flat-roofed piece wrapped round Sensō-ji's pagoda's base (13.9 m): M4 fix round",
    "bldg_ecf0af31-eb0d-4cac-be67-40274365a61d#r2": "its 8.8 m wing east of the pagoda: M4 fix round",
    # (boundary change) a 35 m² LOD1 prism at 136.6 m without storeys beside Tomihisa Cross Comfort Tower (Shinjuku,
    # the west gap): a crane or mast surveyed as a building
    "bldg_8fb128df-7bf7-4ca6-8b38-47f6e484c97a": "a 35 m² prism at 136.6 m beside Tomihisa Cross (a crane or mast)",
    # (M7, b-tk-m7; c-tk-m456 item 3) Kachidoki Bridge's four operator houses as 29 m² LOD0 prisms from the river to 16.6 m:
    # zakkyo blocks with signs standing in the water beside the deck (the bridge figure carries the deck)
    "bldg_6e34aabb-cd4f-45b2-bc3e-b2e2f9e426df": "Kachidoki Bridge operator house prism in the river (M7)",
    "bldg_270f2c2f-d736-42fb-81fb-6381489434f9": "Kachidoki Bridge operator house prism in the river (M7)",
    "bldg_78173e70-ccf4-4072-895f-99b9f7e59f05": "Kachidoki Bridge operator house prism in the river (M7)",
    "bldg_3e0c7196-a266-4df9-adc0-d47f14e2aec5": "Kachidoki Bridge operator house prism in the river (M7)",
}
KEEP_SPIRE = {"bldg_52945d0d-a897-4d55-b35c-a8bcca773e53"}   # NTT Docomo Yoyogi: the stepped clock spire
# (round 2) OSM tower outlines that are not stubs: OSM's levels alone (no 42-F tower in Daiba), needles of 36-218 m²
STUB_NOT = {"w285211002", "w629051412", "w148788526", "w134871304",
            # (boundary change) 西麻布六本木通りビル: OSM's construction outline of the Nishi-Azabu 3-chome NE
            # redevelopment, completion FY2028 (JA Wikipedia 西麻布三丁目北東地区): not standing yet
            "w209160719"}
# ... and one that is: Deux Tours Canal & Spa East (52 F, 177.3 m, 2015) has no PLATEAU solid but a 5.5 m annex
STUB_YES = {"w454866514"}
# (round 2) PLATEAU pieces set by hand: TOFROM YAESU TOWER (249.7 m, 51 F, completed 28 Feb 2026) is three PLATEAU
# construction pieces at 11.7-12.8 m (2,900 m² together: the tower's base as surveyed) -> the tower's height
FIX_GML = {"bldg_c3d6ee36-e148-4050-9211-8b10b3fb5123#r0": 249.7, "bldg_66c4c941-74d8-4a3d-a999-f64b408efd3e": 249.7, "bldg_02423bc1-a8f5-4ce0-a5df-689c762b6f00#r0": 249.7}
# final tops of kept OSM outlines without a height (storeys from JA Wikipedia x ~4 m; [believed] where marked)
SET_H = {
    "r3361370": (20.9, "国会議事堂: the wings (20.91 m, JA Wikipedia); the 65.45 m central tower is an M4 figure"),
    "w428004852": (30.0, "Kioi Tower's podium outline (Tokyo Garden Terrace; the 180 m tower is PLATEAU's own piece) [believed]"),
    "w145495510": (48.0, "参議院議員会館: 12 storeys"),
    "w145495603": (44.0, "中央合同庁舎第8号館: 11 storeys"),
    "r4152284": (24.0, "国立国会図書館 本館: 6 storeys [believed]"),
    "r4169294": (16.0, "国立国会図書館 新館: 4 storeys above ground [believed]"),
    "r7825626": (15.0, "宮内庁庁舎: 3 storeys and its central tower [believed]"),
    "w145495637": (24.0, "衆議院第二別館: 6 storeys [believed]"),
    "w328729134": (32.0, "外務省北庁舎: 8 storeys like the south building (OSM levels 8) [believed]"),
    "w355485898": (28.0, "内閣府本府庁舎: 7 storeys [believed]"),
    "w140109074": (90.6, "中央合同庁舎第2号館: 21 F, eaves 90.6 m (top 99.6)"),
    "w1230247562": (62.1, "NHK放送センター情報棟: 11 F, 62.1 m (2024)"),
    "w136050250": (34.4, "新紀尾井町ビル: 8 F x 4.3 m"),
    "w97227325": (25.0, "サントリーホール: the hall [believed]"),
    "w44776139": (110.0, "浅草ビューホテル: 28 F, 110 m"),
}


def md(df: pd.DataFrame) -> list:
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else
                                     (f"{v:,.1f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return out


def main():
    o = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    p = gpd.read_file(DATA / "plateau_buildings.gpkg").to_crs(UTM)
    bd = gpd.read_file(DATA / "boundary.gpkg").to_crs(UTM).union_all()
    p = p[p.intersects(bd)].copy()
    p["a"] = p.area
    p["bid"] = p.gml_id.str.split("#").str[0]
    p["top"] = p.roof_top_z - p.ground_elevation
    st = pd.to_numeric(p.storeysaboveground, errors="coerce")
    ll = p.representative_point().to_crs(4326)
    p["lat"], p["lon"] = ll.y.map("{:.5f}".format), ll.x.map("{:.5f}".format)
    o = o[o.representative_point().within(bd)].copy()
    o["hh"] = pd.to_numeric(o.height.astype(str).str.extract(r"([\d.]+)")[0], errors="coerce")
    o["hh"] = o.hh.fillna(pd.to_numeric(o.levels, errors="coerce") * LEVEL_H)
    L = ["# Tokyo M2: generated building settings", "", "Made by `scripts/m2_fixes.py` (written into city.toml with "
         "--toml).", ""]
    keep, excl, fix_h, set_h = {}, dict(EXCLUDE_GML), dict(FIX_GML), dict(SET_H)

    # 1. what PLATEAU leaves out
    oo = o[(o.area >= 300) & ~o.building.isin(SKIP)]
    oo = oo[(pd.to_numeric(oo.layer, errors="coerce").fillna(0) >= 0) & (oo.location.fillna("") != "underground")]
    pu = p.geometry.union_all()
    oo = oo.assign(cov=oo.intersection(pu).area / oo.area)
    unsure = oo.name.isna() & oo.height.isna() & oo.levels.isna() & (oo.area >= 1000)
    k1 = oo[(oo["cov"] < 0.3) & ~oo.osm_id.isin(NOT) & ~unsure]
    keep.update({i: "PLATEAU leaves it out" for i in k1.osm_id})
    # (round 2) offices and ministries are 4.3 m a storey, not level_h's 3.5 (中央合同庁舎第2号館: 21 F, 90.6 m eaves)
    off = k1[k1.building.isin(["public", "office", "government", "commercial", "hotel"]) & k1.height.isna()
             & pd.to_numeric(k1.levels, errors="coerce").notna()]
    storey_h = {i: (round(float(lv) * 4.3, 1), f"{nm or i}: {lv} storeys x 4.3 m") for i, lv, nm in
                zip(off.osm_id, pd.to_numeric(off.levels, errors="coerce"), off.name)}
    big = k1[k1.height.isna() & k1.levels.isna() & (k1.area >= 2000) & ~k1.osm_id.isin(list(SET_H))]
    L_big = [f"{i} {nm or ''} {a:,.0f} m²" for i, nm, a in zip(big.osm_id, big.name, big.area)]
    for k_, v_ in storey_h.items():
        set_h.setdefault(k_, v_)
    L_storey = [f"{k_} {v_[0]} m" for k_, v_ in storey_h.items()]
    L += [f"## 1. OSM buildings PLATEAU leaves out: {len(k1)} kept ({k1.area.sum():,.0f} m²); unsure (unnamed, "
          f"untagged, ≥ 1,000 m²) left out: {int((unsure & (oo['cov'] < 0.3)).sum())}", "",
          f"Kept offices and ministries with levels but no height, at 4.3 m a storey (set_h): {len(L_storey)}: "
          + "; ".join(L_storey), "",
          f"Kept outlines of 2,000 m² or more with neither height nor levels, at the 3-storey default: {len(L_big)}: "
          + "; ".join(L_big), ""]

    # 2. broken LOD1 solids
    bad = p[(p.lod == 1) & (((st * 3) > 5 * p.h) | ((p.h < 5) & (p.a >= 5000)))]
    L += [f"## 2. Broken LOD1 solids (storeys x 3 > 5 x h, or under 5 m on 5,000 m²+): {len(bad)}", ""]
    rows = []
    for r in bad.itertuples():
        under = o[o.representative_point().within(r.geometry) & ~o.building.isin(SKIP) & (o.area >= 50)]
        share = under.intersection(r.geometry).area.sum() / r.a
        n = st[r.Index]
        if share >= 0.5:
            excl[r.gml_id] = f"broken LOD1 solid ({r.a:,.0f} m² at {r.h:.1f} m, {n:.0f} storeys): OSM's outlines on it"
            keep.update({i: "on a broken LOD1 solid" for i in under.osm_id})
            what = "OSM: " + ", ".join(f"{i} {nm or ''} {h:.0f} m" for i, nm, h in zip(under.osm_id, under.name, under.hh))
        elif r.a >= 100 and n * LEVEL_H <= 8 * np.sqrt(r.a):
            fix_h[r.gml_id] = round(float(n * LEVEL_H), 1)
            what = f"storeys x {LEVEL_H} = {n * LEVEL_H:.1f} m"
        else:
            what = "left as it is (an annex carrying its tower's storeys)"
        rows.append({"gml_id": r.gml_id[5:13], "m²": r.a, "h": r.h, "storeys": n, "lat": r.lat, "lon": r.lon, "fix": what})
    L += md(pd.DataFrame(rows)) + [""] if rows else ["(none)", ""]

    # 3. construction stubs
    g = p.groupby("bid").agg(h=("h", "max"), st=("storeysaboveground", "max"), a=("a", "sum"), lat=("lat", "first"),
                             lon=("lon", "first"), name=("name", "first"))
    stub = g[(pd.to_numeric(g.st, errors="coerce") >= 15) & (g.h < 2.6 * pd.to_numeric(g.st, errors="coerce"))
             & (g.a >= 800)]       # (annexes and canopies carry their tower's storeys: only buildings of 800 m²+)
    tw = o[(o.hh >= 60) & (o.area <= 3000) & ~o.osm_id.isin(NOT) & ~o.osm_id.isin(STUB_NOT)]
    j = gpd.sjoin(p[["geometry", "bid", "h"]].assign(geometry=p.representative_point()), tw[["geometry", "osm_id", "hh", "name"]],
                  predicate="within")
    jm = j.groupby(["osm_id"]).agg(h=("h", "max"), hh=("hh", "first"), name=("name", "first"), bids=("bid", lambda x: set(x)))
    # (round 2) never on OSM's levels alone: only where PLATEAU's own storeys disagree with its height under the
    # outline (storeys x 3 > 2 x h), or the outline is a building site in OSM or newly mapped (id over 1.1e9)
    pst = p.assign(stv=st).groupby("bid").agg(h=("h", "max"), stv=("stv", "max"))
    j["dis"] = j.bid.map((pst.stv * 3 > 2 * pst.h).fillna(False))
    jm["dis"] = j.groupby("osm_id").dis.any()
    meta = o.set_index("osm_id")
    jm["new"] = [(meta.building.get(i) == "construction") or int(i[1:]) > 1_100_000_000 for i in jm.index]
    short = jm[(jm.h < 0.5 * jm.hh) & (jm.dis | jm.new | jm.index.isin(STUB_YES))]
    rows = []
    for oid, r in short.iterrows():
        keep[oid] = f"a tower PLATEAU surveyed as a stub ({r.h:.1f} m under OSM's {r.hh:.0f})"
        # (PLATEAU's heights reach the footprints it covers before OSM's: the stub's would win without set_h)
        set_h[oid] = (round(float(r.hh), 1), f"{r['name'] or 'tower'}: OSM's height over PLATEAU's stub")
        rows.append({"OSM tower outline": oid, "name": r["name"], "OSM h": r.hh, "OSM m²": float(tw.area[tw.osm_id == oid].iloc[0]),
                     "PLATEAU max under it": r.h})
    covered = set().union(*short.bids) if len(short) else set()
    left = stub[~stub.index.isin(covered)]
    L += [f"## 3. Construction stubs: {len(short)} OSM tower outlines kept over PLATEAU stubs; PLATEAU buildings of 15+ "
          f"storeys under 2.6 m a storey without such an outline: {len(left)}", ""]
    L += md(pd.DataFrame(rows)) + [""] if rows else ["(none)", ""]
    if len(left):
        L += md(left.reset_index()[["bid", "name", "h", "st", "a", "lat", "lon"]]) + [""]

    # 4. LOD1 towers over big low blocks
    mh = pd.to_numeric(p.measuredheight, errors="coerce")
    cand = p[(p.lod == 1) & (p.a >= 1000) & (mh > 1.5 * p.top)]
    carry = st.isna() | (st * 6.0 >= mh)      # (none known, or storeys of up to 6 m carry it: Sumida City Hall 19 F, 86.3 m)
    # only the clear cases: the storeys don't carry it, it is over twice the block's top, on 10,000 m² or more (NHK);
    # halls of 2-3 storeys (the Budokan's 33.3 m roof, Meiji Jingu's treasure house) keep their measuredHeight
    clear = ~carry & (mh > 2 * p.top) & (p.a >= 10000)
    carry = ~clear
    cap = cand.iloc[:0]     # (round 2) none: the height expression takes a big LOD1 block's own top, raised to its
                            # storeys x 4.5 (NHK 36 m); listed here for the record
    fix_h.update({r.gml_id: round(float(r.top), 1) for r in cap.itertuples()})
    L += [f"## 4. LOD1 blocks with a taller measuredHeight: {len(cand)}; capped to their block's top (storeys don't "
          f"carry the measuredHeight): {len(cap)}; kept at measuredHeight: {len(cand) - len(cap)}", ""]
    L += md(cand.assign(capped=~carry.reindex(cand.index).fillna(False), measured=mh[cand.index])
            [["gml_id", "name", "a", "measured", "top", "storeysaboveground", "capped", "lat", "lon"]]
            .assign(gml_id=lambda d: d.gml_id.str[5:13]).sort_values("measured", ascending=False)) + [""]

    # 5. lone roof levels
    lv = p[p.roof_level.notna() & (p.a < 100) & ~p.bid.isin(KEEP_SPIRE)]
    rows = []
    for i, r in lv.iterrows():
        nb = p[(p.bid == r.bid) & (p.index != i)]
        nb = nb[nb.geometry.distance(r.geometry) < 0.5]
        if len(nb) and r.h > nb.h.max() + 30:
            fix_h[r.gml_id] = round(float(nb.h.max()), 1)
            rows.append({"gml_id": r.gml_id[5:], "m²": r.a, "h": r.h, "to": nb.h.max(), "name": r["name"],
                         "lat": r.lat, "lon": r.lon})
    L += [f"## 5. Lone roof levels (< 100 m², 30 m+ over every level they touch) brought down: {len(rows)}", ""]
    L += md(pd.DataFrame(rows)) + [""] if rows else ["(none)", ""]

    L += ["## Set by hand", "", "Left out (gml_id): " + "; ".join(f"{k[5:]}: {v}" for k, v in EXCLUDE_GML.items()), "",
          "set_h (kept OSM outlines without a height): " + "; ".join(f"{k} {h} m ({why})" for k, (h, why) in SET_H.items()), "",
          "OSM left out by id: " + ", ".join(EXCLUDE_OSM), ""]
    (HERE / "checks" / "m2_fixes.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

    if "--toml" in sys.argv:
        q = lambda xs: ", ".join(f'"{x}"' for x in sorted(xs))
        block = ("# BEGIN m2_fixes (scripts/m2_fixes.py --toml; the reasons in checks/m2_fixes.md)\n"
                 f"keep = {{ osm = [{q(keep)}] }}\n"
                 "set_h = { " + ", ".join(f'"{k}" = {h}' for k, (h, _) in set_h.items()) + " }\n"
                 "fix_h = { gml_id = { " + ", ".join(f'"{k}" = {v}' for k, v in sorted(fix_h.items())) + " } }\n"
                 "# END m2_fixes")
        ex = ("# BEGIN m2_exclude\n[buildings.exclude]\n"
              f"gml_id = [{q(excl)}]\nosm = [{q(EXCLUDE_OSM)}]\n# END m2_exclude")
        t = (HERE / "city.toml").read_text()
        t = re.sub(r"# BEGIN m2_fixes.*?# END m2_fixes", lambda m: block, t, flags=re.S)
        t = re.sub(r"# BEGIN m2_exclude.*?# END m2_exclude", lambda m: ex, t, flags=re.S)
        (HERE / "city.toml").write_text(t)


if __name__ == "__main__":
    main()
