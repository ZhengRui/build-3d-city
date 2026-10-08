"""Tokyo M2: checks of the building table (../data/tokyo/buildings.gpkg) -> checks/m2_buildings.md,
checks/buildings_heights.png, checks/buildings_heights_core.png.

  1. the table: pieces, buildings, roof levels (the citygml adapter's roof_split), split_ground
  2. the landmark list: every row, listed against built
  3. spot check: Wikipedia's "List of tallest buildings in Tokyo" (fetched 6 Oct 2026) against the table, by name
  4. LoD2 roof or measuredHeight: both against OSM's height tags on whole (unsplit) LoD2 buildings
  5. blobs (big footprints at height), needles, long thin walls
  6. OSM fill (where PLATEAU has nothing) and OSM construction sites under PLATEAU pieces
  7. underground: PLATEAU's storeysBelowGround (above-ground volume only), pieces under 2 m
Run from demos/tokyo: uv run python scripts/m2_buildings.py (loads the whole table: under the pipeline lock).
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA = HERE.parent / "data" / "tokyo"
CHECKS = HERE / "checks"
UTM = "EPSG:32654"

# Wikipedia EN "List of tallest buildings in Tokyo" (completed, inside or near D), height m; a name token as the
# table has it (PLATEAU's gml:name or OSM's name)
WIKI = [("Azabudai Hills Residence B", 263, "レジデンスB"), ("TOFROM Yaesu Tower", 250, "TOFROM"),
        ("Tokyo Midtown Yaesu Central Tower", 240, "ミッドタウン八重洲"), ("Shinjuku Park Tower", 235, "新宿パークタワー"),
        ("Roppongi Grand Tower", 231, "六本木グランドタワー"), ("Shinjuku Mitsui Building", 225, "新宿三井ビル"),
        ("Tokyu Kabukicho Tower", 225, "歌舞伎町タワー"), ("Shinjuku Center Building", 223, "新宿センタービル"),
        ("Toranomon Hills Residential Tower", 222, "レジデンシャルタワー"), ("Saint Luke's Tower", 221, "聖路加"),
        ("Nittele Tower", 218, "日本テレビタワー"), ("Shiodome City Center", 216, "汐留シティセンター"),
        ("Mita Garden Tower", 215, "三田ガーデンタワー"), ("Shinjuku Sumitomo Building", 210, "新宿住友ビル"),
        ("Shinjuku Nomura Building", 209, "新宿野村ビル"), ("The Parkhouse Nishi-Shinjuku Tower 60", 209, "西新宿タワー60"),
        ("Akasaka Trust Tower", 209, "赤坂トラストタワー"), ("PortCity Takeshiba Office Tower", 209, "ポートシティ竹芝"),
        ("Ark Hills Sengokuyama Mori Tower", 207, "仙石山"), ("GranTokyo North Tower", 205, "ノースタワー"),
        ("GranTokyo South Tower", 205, "サウスタワー"), ("Akasaka Intercity AIR", 205, "インターシティAIR"),
        ("Izumi Garden Tower", 201, "泉ガーデンタワー"), ("Sompo Japan Building", 200, "損保ジャパン"),
        ("TEPCO Building (to its roof tower)", 200, "東京電力ホールディングス"), ("JP Tower", 200, "=JPタワー"),
        ("Yomiuri Shimbun Building", 200, "読売新聞"), ("Otemachi One Tower", 200, "大手町ワン"),
        ("Otemachi Tower", 200, "大手町タワー"), ("Shin-Marunouchi Building", 198, "新丸の内"),
        ("World Trade Center South Tower", 197, "世界貿易センタービル"), ("Shinjuku Grand Tower", 195, "新宿グランドタワー"),
        ("Harumi Triton Square Tower X", 195, "トリトン"), ("Nihonbashi Mitsui Tower", 195, "日本橋三井タワー"),
        ("Park Tower Kachidoki South", 195, "パークタワー勝どき"), ("Sanno Park Tower", 194.5, "山王パークタワー"),
        ("The Tokyo Towers", 193.5, "TOKYO TOWERS"), ("Kachidoki View Tower", 193, "勝どきビュータワー"),
        ("Tokyo Midtown Hibiya", 192, "ミッドタウン日比谷"), ("Acty Shiodome", 190.3, "アクティ汐留"),
        ("Shinjuku I-Land Tower", 189.4, "アイランドタワー"), ("Okura Prestige Tower", 188.7, "プレステージタワー"),
        ("Capital Gate Place", 187, "キャピタルゲート"), ("Atago Green Hills Mori Tower", 186.8, "愛宕グリーンヒルズ")]
# completed in 2026 (critic round 2: tatemono.com 2 Mar 2026, Mitsui Fudosan 21 Apr 2026, skyskysky.net): should stand
UNBUILT = [("TOFROM YAESU TOWER (249.7 m, completed 28 Feb 2026)", "TOFROM"),
           ("Tokyo Midtown Nihonbashi (284 m, completed Sep 2026)", "ミッドタウン日本橋"),
           ("Grand City Tower Tsukishima (197.65 m, completed May 2026)", "グランドシティタワー"),
           ("Torch Tower (385 m, due 2028: must not stand)", "トーチタワー")]


def md(df: pd.DataFrame, fmt: dict | None = None) -> list:
    fmt = fmt or {}
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join(("" if (isinstance(v, float) and np.isnan(v)) else
                                       (fmt.get(c, "{}").format(v) if not isinstance(v, str) else v))
                                      for c, v in zip(df.columns, r)) + " |")
    return out


def main():
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    b["a"] = b.area
    rp = b.representative_point()
    ll = rp.to_crs(4326)
    b["lat"], b["lon"] = ll.y.round(5), ll.x.round(5)
    b["bid"] = b["gml_id"].fillna("").str.split("#").str[0]
    b.loc[b.bid == "", "bid"] = "osm" + b["osm_id"].astype(str)
    pl = b[b.source == "plateau"]
    lvl = pd.to_numeric(b.get("roof_level"), errors="coerce")
    L = ["# Tokyo M2: building table checks", "",
         "Made by `scripts/m2_buildings.py` from `../data/tokyo/buildings.gpkg` (04_buildings).", "",
         "## 1. The table", "",
         f"- {len(b):,} pieces, {b.bid.nunique():,} buildings, {b.a.sum() / 1e6:.2f} km² of footprint: PLATEAU "
         f"{len(pl):,} pieces ({pl.bid.nunique():,} buildings), OSM fill {int((b.source == 'osm').sum()):,}.",
         f"- Cut by roof level (roof_split): {b.loc[lvl.notna(), 'bid'].nunique():,} buildings into "
         f"{int(lvl.notna().sum()):,} pieces; split_ground lowered {int((b.get('split_rise', 0) > 0.5).sum()):,} "
         f"levels standing up a slope (median {b.loc[b.split_rise > 0.5, 'split_rise'].median():.1f} m, max "
         f"{b.split_rise.max():.1f} m).",
         f"- Heights: " + ", ".join(f"{k} {v:,}" for k, v in b.h_src.value_counts().items()) + ".",
         f"- Buildings (tallest piece) ≥ 100 m: {(b.groupby('bid').h.max() >= 100).sum()}, ≥ 150 m: "
         f"{(b.groupby('bid').h.max() >= 150).sum()}, ≥ 200 m: {(b.groupby('bid').h.max() >= 200).sum()}.", ""]

    # 2. landmarks
    lm = pd.read_csv(HERE / "data" / "landmarks_tokyo.csv")
    rows = []
    for r in lm.itertuples():
        g = b[b["landmark"] == r.name_zh] if "landmark" in b else b.iloc[:0]
        built = g.h.max() if len(g) else np.nan
        note = ""
        if not len(g):
            p = gpd.GeoSeries(gpd.points_from_xy([r.lon], [r.lat]), crs=4326).to_crs(UTM).iloc[0]
            near = b[b.geometry.distance(p) <= 40]
            built = near.h.max() if len(near) else np.nan
            note = f"not set by the list; tallest piece within 40 m {built:.1f}" if len(near) else "nothing within 40 m"
            built = np.nan
        rows.append({"landmark": r.name_en, "listed": r.height_m, "use_height": r.use_height, "feature": r.feature,
                     "built": built, "d": built - r.height_m if np.isfinite(built) else np.nan, "note": note})
    t = pd.DataFrame(rows)
    L += ["## 2. Landmark list: listed against built", "",
          "Built: the tallest piece the list named (use_height rows set it; `ground = \"point\"` adds the rise from "
          "the lowest ground under the outline to the ground at the point). Rows with use_height false are figures "
          "or sites for M4 (the Skytree's and Tokyo Tower's PLATEAU solids are left out by gml_id).", ""]
    L += md(t, {"listed": "{:.1f}", "built": "{:.1f}", "d": "{:+.1f}"}) + [""]

    # 3. spot check
    named = b[b["name"].notna()]
    rows = []
    for en, h, tok in WIKI:
        g = named[named["name"] == tok[1:]] if tok.startswith("=") else named[named["name"].str.contains(tok, regex=False)]
        if not len(g):
            rows.append({"building (Wikipedia)": en, "listed": h, "table": np.nan, "d": np.nan, "src": "", "piece m²": np.nan,
                         "name in table": "(not found by name)"})
            continue
        top = b[b.bid.isin(g.bid)].sort_values("h", ascending=False).iloc[0]
        rows.append({"building (Wikipedia)": en, "listed": h, "table": top.h, "d": top.h - h, "src": top.h_src,
                     "piece m²": top.a, "name in table": str(g.iloc[0]["name"])})
    s = pd.DataFrame(rows)
    f = s.dropna(subset=["d"])
    L += ["## 3. Spot check: Wikipedia's list of tallest buildings in Tokyo", "",
          f"Matched by name {len(f)} of {len(s)}: median table − listed {f.d.median():+.1f} m, median abs "
          f"{f.d.abs().median():.1f} m, within 5 m {(f.d.abs() <= 5).mean():.0%}, within 10 m "
          f"{(f.d.abs() <= 10).mean():.0%}. The table's height is over the lowest ground under the piece "
          "(06_tiles stands it there); the published one over the entrance, so towers on a slope or over a sunken "
          "plaza (Nishi-Shinjuku) read a few metres taller.", ""]
    L += md(s, {"listed": "{:.1f}", "table": "{:.1f}", "d": "{:+.1f}", "piece m²": "{:,.0f}"}) + [""]
    L += ["Completed in 2026, and Torch Tower (by name; TOFROM is three PLATEAU pieces set by fix_h, unnamed):", ""]
    for en, tok in UNBUILT:
        g = named[named["name"].str.contains(tok, regex=False)]
        L.append(f"- {en}: " + ("absent" if not len(g) else
                                 f"{len(g)} pieces named, tallest {b[b.bid.isin(g.bid)].h.max():.1f} m"))
    L.append("")

    # 4. LoD2 roof or measuredHeight
    if "h_osm_tag" in b:
        w = b[(b.source == "plateau") & lvl.isna() & (b.lod == 2) & b.h_osm_tag.notna() & b.measuredheight.notna()
              & (b.h_osm_tag > 3)].copy()
        w["lod2"] = w.roof_top_z - w.ground_elevation
        rows = []
        for band, lo, hi in (("all", 0, 1e9), ("< 31 m", 0, 31), ("31-100 m", 31, 100), ("≥ 100 m", 100, 1e9)):
            x = w[(w.h_osm_tag >= lo) & (w.h_osm_tag < hi)]
            if len(x):
                rows.append({"OSM height band": band, "n": len(x),
                             "LoD2 roof: median d": (x.lod2 - x.h_osm_tag).median(),
                             "LoD2 roof: MAE": (x.lod2 - x.h_osm_tag).abs().mean(),
                             "measuredHeight: median d": (x.measuredheight - x.h_osm_tag).median(),
                             "measuredHeight: MAE": (x.measuredheight - x.h_osm_tag).abs().mean()})
        L += ["## 4. LoD2 roof or measuredHeight", "",
              "Whole (unsplit) LoD2 buildings with an OSM `height` tag (OSM's central Tokyo heights are largely "
              "imported from PLATEAU's measuredHeight, so this favours measuredHeight: the landmark list and section 3 "
              "are the independent checks).", ""]
        L += md(pd.DataFrame(rows), {k: "{:+.1f}" if "median" in k else "{:.1f}" for k in
                                      ["LoD2 roof: median d", "LoD2 roof: MAE", "measuredHeight: median d",
                                       "measuredHeight: MAE"]}) + [""]
        d = w[(w.lod2 - w.measuredheight).abs() > 15]
        L += [f"Whole LoD2 buildings whose roof and measuredHeight differ by over 15 m: "
              f"{int(((pl.lod == 2) & lvl[pl.index].isna() & ((pl.roof_top_z - pl.ground_elevation - pl.measuredheight).abs() > 15)).sum())}"
              f" (of which with an OSM height {len(d)}).", ""]

    # 5. blobs, needles, walls
    blob = b[((b.a >= 5000) & (b.h >= 30)) | ((b.a >= 2000) & (b.h >= 100))].sort_values("a", ascending=False)
    L += ["## 5. Blobs, needles, walls", "",
          f"Big footprints at height (≥ 5,000 m² at ≥ 30 m, or ≥ 2,000 m² at ≥ 100 m): {len(blob)}; the 30 largest:", ""]
    L += md(blob[["name", "usage_name", "a", "h", "h_src", "roof_level", "lat", "lon"]].head(30),
            {"a": "{:,.0f}", "h": "{:.1f}", "roof_level": "{:.0f}"}) + [""]
    needle = b[(b.h >= 40) & ((b.a < 80) | (b.h > 8 * np.sqrt(b.a)))]
    # a roof level beside a level of its own building at 60 % of its height or more is a tower's crown or core, not a
    # needle standing alone
    sup = []
    for i, r in needle.iterrows():
        nb = b[(b.bid == r.bid) & (b.index != i)]
        nb = nb[nb.geometry.distance(r.geometry) < 0.5]
        sup.append(bool(len(nb)) and nb.h.max() >= 0.6 * r.h)
    alone = needle[~np.array(sup, dtype=bool)].sort_values("h", ascending=False)
    L += [f"Thin tall pieces (≥ 40 m on < 80 m², or taller than 8 × √area): {len(needle)}, of which {len(needle) - len(alone)} "
          f"are roof levels against a level of their building at 60 % of their height or more (crowns, cores); "
          f"standing alone (needles): {len(alone)}:", ""]
    needle = alone
    L += md(needle[["name", "a", "h", "h_src", "roof_level", "bid", "lat", "lon"]].head(30),
            {"a": "{:,.0f}", "h": "{:.1f}", "roof_level": "{:.0f}"}) + [""]
    wall = b[(b.aspect >= 8) & (b.a >= 300) & (b.h >= 10)].sort_values("a", ascending=False)
    L += [f"Long thin pieces (aspect ≥ 8, ≥ 300 m², ≥ 10 m: viaducts, decks, station roofs drawn as walls?): {len(wall)}:", ""]
    L += md(wall[["name", "usage_name", "a", "aspect", "h", "source", "lat", "lon"]].head(25),
            {"a": "{:,.0f}", "aspect": "{:.1f}", "h": "{:.1f}"}) + [""]

    # 6. OSM fill
    o = b[b.source == "osm"]
    L += ["## 6. OSM fill (outlines PLATEAU has nothing under)", "",
          f"{len(o):,} pieces, {o.a.sum():,.0f} m² (median {o.a.median():.0f} m²); heights: "
          + ", ".join(f"{k} {v:,}" for k, v in o.h_src.value_counts().items())
          + f"; max {o.h.max():.1f} m; by area: < 50 m² {(o.a < 50).sum():,}, 50-200 {((o.a >= 50) & (o.a < 200)).sum():,}, "
          f"200-1,000 {((o.a >= 200) & (o.a < 1000)).sum():,}, ≥ 1,000 {(o.a >= 1000).sum():,}.", ""]
    L += ["The 30 largest:", ""]
    L += md(o.sort_values("a", ascending=False)[["osm_id", "osm_building", "name", "a", "h", "h_src", "lat", "lon"]].head(30),
            {"a": "{:,.0f}", "h": "{:.1f}"}) + [""]
    osm = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    con = osm[osm.building == "construction"]
    j = gpd.sjoin(b[["geometry", "h", "bid", "name", "source"]], con[["geometry", "osm_id", "name"]],
                  predicate="intersects", rsuffix="c")
    j = j[j.h >= 20]
    L += [f"OSM `building=construction` outlines: {len(con)}; table pieces ≥ 20 m meeting them: {len(j)} "
          f"({j.bid.nunique()} buildings: PLATEAU's survey saw a building there)", ""]
    if len(j):
        jj = j.sort_values("h", ascending=False).drop_duplicates("bid")
        jj = jj.assign(lat=b.loc[jj.index, "lat"], lon=b.loc[jj.index, "lon"])
        L += md(jj[["name_left", "h", "source", "osm_id", "name_c" if "name_c" in jj else "name_right", "lat", "lon"]].head(20),
                {"h": "{:.1f}"}) + [""]

    # 7. underground
    sb = pd.to_numeric(pl.get("storeysbelowground"), errors="coerce")
    L += ["## 7. Underground", "",
          f"PLATEAU pieces with storeys below ground: {int((sb > 0).sum()):,} (their solids start at the ground: only "
          f"the above-ground volume is drawn). Pieces under 2 m before the 3.5 m floor (h_plateau < 2): "
          f"{int((pl.h_plateau < 2).sum()):,} (median {pl.loc[pl.h_plateau < 2, 'a'].median():.0f} m²: walls, "
          "kiosks, low structures). OSM: underground_drop and station_untagged in 04's log.", ""]
    (CHECKS / "m2_buildings.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))

    # height maps
    for name, box in (("buildings_heights.png", None), ("buildings_heights_core.png", (385200, 3947300, 389800, 3952300))):
        fig, ax = plt.subplots(figsize=(14, 12) if box is None else (12, 13), dpi=110)
        g = b if box is None else b.cx[box[0]:box[2], box[1]:box[3]]
        g.plot(ax=ax, column=g.h.clip(upper=250), cmap="turbo", vmin=0, vmax=250, linewidth=0, legend=True,
               legend_kwds={"label": "height (m, capped at 250)", "shrink": 0.6})
        if box is not None:
            ax.set_xlim(box[0], box[2]); ax.set_ylim(box[1], box[3])
        ax.set_title(f"Tokyo M2: {len(g):,} pieces by height" + ("" if box is None else " (the core)"))
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(CHECKS / name)
        plt.close(fig)


if __name__ == "__main__":
    main()
