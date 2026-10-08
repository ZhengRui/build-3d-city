"""M2: Singapore's height inputs for 04_buildings, written as two "file" sources (city.toml [sources.hdb], [sources.est]).

1. HDB blocks (../data/singapore/hdb_m2.gpkg, from M1's hdb_storeys.gpkg): HDB maps a podium and the towers on it as
   separate, overlapping polygons (1 Cantonment Rd's 2-storey podium round Pinnacle@Duxton's 1A-1G, Tanjong Pagar
   Plaza, Waterloo Centre, Bras Basah Complex, Hong Lim, 269 Queen St, Chinatown Complex). Of two overlapping blocks
   (by 5 % of the smaller or more) the overlap is cut out of the lower one (fewer storeys; of equal ones the larger):
   towers are cut out of their podiums, never unioned. A podium whose storeys are those of its towers (HDB gives the
   complex's highest floor on the podium polygon: 1 Tanjong Pagar Plaza "24") over 3,000 m² gets PODIUM_STOREYS
   (column podium_fix says so).

2. Height estimates for OSM buildings with no height and no levels (../data/singapore/osm_est.gpkg, field est): the
   median height of the K nearest tagged OSM buildings (height tag, else levels x level_h) within R m whose footprint
   is within F x of this one's area (at least 3 of them; else no estimate and the engine's default applies), capped
   at CAP m and at SLENDER x the square root of its area (no needles). Leave-one-out on the tagged buildings, median
   absolute error against the default of 3 storeys
   (checks/m2_estimates.md has the table): 500-5,000 m² 4-10 m against 14-25 m. The polygons are copies of the OSM
   outlines: 04_buildings drops each as the OSM building's duplicate and gives its height to it by containment.
   Also copies of the OSM outlines with a layer < 0 that stand on the ground (SURFACE: Ocean Financial Centre's
   outline "Ocean Towers" layer=-1, two hotels): [buildings] surface_layers keeps an untagged layer < 0 outline that a
   fill source's polygon covers. And copies of the big OSM buildings (over osm_max_area) with a height or levels
   tag: 04_buildings takes OSM tags only from smaller outlines (est_src "big_tag"). And the podium rings (est_src
   "podium", see podiums()).

Run from demos/singapore after 01_osm: uv run python scripts/m2_heights.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from city3d.common import CFG, DATA, LEVEL_H, UTM, boundary, height_m

HERE = Path(__file__).resolve().parent.parent
PODIUM_STOREYS = 3
K, R, F, CAP = 6, 250.0, 2.5, 150.0
SLENDER = 4.0              # est <= SLENDER x sqrt(area): 142 m² 48 m, 1,000 m² 126 m (CBD towers are 5-7)
PODIUM_DEFAULT = 14.0      # m: a podium with no height of its own (4 storeys)
MIN_AREA = 50.0             # smaller ones: the engine's one storey (sheds, kiosks)
# OSM outlines with layer=-1 that are buildings on the ground (no location tag; checked on the map and by name)
SURFACE = ["w172915346", "w380512072", "w742205653"]   # Ocean Towers (OFC), Old SSVF HQ, Parkroyal Collection Marina Bay
# OSM ids left out by hand (city.toml [buildings] exclude, written with the generated ones by --toml)
HAND_EXCLUDE = {
    # (M3 fix round: the MBS SkyPark w116800998 and the Canninghill Piers Skybridge w1057491646 are drawn in the
    # air now: [osm] min_height = "decks", [buildings] lift_parts = "gaps")
    "w1395942980": "Tanjong Rhu 'Sky Deck' (a raised deck, estimated 56 m from the ground)",
    "w172596785": "Waterloo Centre (HDB draws podium and towers)", "w44414531": "Bras Basah Complex (HDB)",
    "r2304417": "Hong Lim Complex (HDB)", "w125836967": "Hong Lim Market (HDB)",
    "w172814599": "Tanjong Pagar Plaza (HDB)", "r4547546": "Tanjong Pagar Plaza (HDB)", "w48045893": "269 Queen St (HDB)",
    "r6730990": "twin of YWCA Outram Centre r2297252", "w372072215": "twin of MDIS House r6973890",
    "w1077992845": "20 m² sliver tagged 29 storeys by The Concourse",
    "w407705505": "One Raffles Place Tower 2 drawn twice (179 m; w407705559 209 m stays)",
    "w393090486": "Suntec Tower 1's 90-150 m part (its 150-181 m part lands 9.5 m² on Suntec City: a needle)",
    "w172373826": "Suntec Tower 1's 150-181 m part (Tower 1 is raised to its listed 180.8 m from its 0-90 m part)",
    "w172263111": "Outram Park station concourse (indoor=room, levels=1, 3,405 m²: under ground)",
    "w538685713": "an untitled transportation box of 5,647 m² by Outram Park (levels=1): a station concourse",
}
# M4 landmarks (scripts/m4l_structures.py draws them as figures): the MBS SkyPark (the ship), the Gardens' two
# conservatories (glass shells), the Supertrees (outlines and their ring parts), the Old Supreme Court's dome drum and
# needle, the Sultan Mosque's broken dome part (4 m on a 12 m min_height)
M4L_EXCLUDE = {
    "w116800998": "MBS SkyPark (figure)", "w171142595": "Flower Dome (figure)", "w171142597": "Cloud Forest (figure)",
    "w334127038": "Old Supreme Court dome drum (figure)", "w334127041": "Old Supreme Court dome needle (figure)",
    "w1165450368": "Sultan Mosque dome part (figure)",
}
M4L_EXCLUDE.update({k: "Supertree (figure)" for k in
                    ["w172288947", "w172288948", "w172288950", "w172288952", "w172288953", "w172288955", "w172288956",
                     "w172288958", "w172288975", "w572839870", "w572839881", "w681695788"]
                    + ["w5728398" + i for i in ("67", "68", "69", "71", "72", "74", "75", "76", "77", "78", "79", "80")]
                    + ["w6816936" + i for i in ("34", "35", "36")]
                    + ["w6816957" + i for i in ("75", "76", "77", "79", "80", "82", "83", "84", "86", "87", "89", "90", "92",
                                                "93", "94", "96", "97", "98")]
                    + ["w6816958" + i for i in ("00", "01", "02", "06", "08", "10")]
                    # the outlines round those rings (drawn whole once their parts went), and three Supertrees by the
                    # Cloud Forest (outlines only, 26-30 m)
                    + ["w572839866", "w572839873", "w681693637", "w681695778", "w681695785", "w681695795",
                       "w681695799", "w681695804", "w591619300", "w591619301", "w591619302"]})
HAND_EXCLUDE.update(M4L_EXCLUDE)
# under construction (OSM ids from 2025-26 with levels only and no construction tag; TOPs 2029-31, critic round 2):
# Berlayar Street, One Marina Gardens (towers and podium), Tanjong Rhu Riverfront I and II, Crawford Heights
UNDER_CONSTRUCTION = (["w155148738" + str(i) for i in (0, 2, 4, 5, 6)]
                      + ["w1377221328", "w1377221329", "w1377221330", "w1346343773"]
                      + [f"w13411688{i}" for i in (47, 48, 49, 50, 51, 52, 56, 57, 59, 60, 61, 62, 63, 64, 65, 66, 67)]
                      + [f"w13586229{i}" for i in (36, 37, 38, 39)])
HAND_EXCLUDE.update({k: "under construction" for k in UNDER_CONSTRUCTION})
NOT_PODIUM = set(HAND_EXCLUDE)
# railway stations: the MRT is underground here (Sentosa's monorail stations are not tagged train_station); untagged
# station outlines of STATION_DROP m² or more are the station box under the street (Dhoby Ghaut 23,500 m², HarbourFront
# 14,000 m² tagged underground=yes but layer=1, Orchard Boulevard...): 04_buildings drops them ([buildings]
# station_untagged = "drop", [osm] underground_drop); here they are only kept out of the estimates, and the rest are
# entrances at ENTRANCE_H ([buildings] set_h)
STATION_TYPES = {"train_station", "transportation"}
STATION_KEEP = {"w393439098"}       # the Former Tanjong Pagar Railway Station (a real building, 8 m)
STATION_DROP = 150.0
ENTRANCE_H = 4.5
# a building:part mapping a structure, not a building: the Singapore Flyer's 29 rim prisms (40 m², 15-165 m)
PART_STRUCTURES = ["w230082125"]    # the outlines whose parts go
# raised building:parts extruded from the ground without [buildings] lift_parts: Pinnacle@Duxton's 26th and 50th
# storey skybridges (min_height 72, 147), and the National Stadium's (w182827369) roof rings (min_height 12 m or more)
# M3 fix round: both kept and lifted ([buildings] lift_parts = "gaps"): the lists are empty
PART_DROP = []
PART_DROP_IN = {"w182827369": 12.0}   # M4: the National Stadium's roof rings (the dome is a figure)
# the National Stadium: its outline left out, the annulus under its dropped roof rings drawn as the seating bowl at
# BOWL m (the pitch open; the 83 m dome for M4)
STADIUM_BOWL = {"w182827369": 20.0}
# towers OSM draws only as a building:part on a podium outline (the part covers under 25 %, so 04_buildings ignores
# it): outline -> (parts, podium height): Hilton Singapore Orchard (outline tagged 90 m, Tower 2 152 m)
TOWER_PARTS = {"w41890074": (["w325793754"], 20.0)}
SET_H = {}                  # OSM id -> m, for [buildings] set_h besides the station entrances
# estimates capped by building tag: low types never become towers (a terrace, a school, toilets); "yes" over YES_CAP
# m only where 3 neighbours of nearly the same footprint (YES_F) agree
TYPE_CAP = {t: 20.0 for t in ("house", "terrace", "detached", "semidetached_house", "school", "kindergarten", "church",
                              "temple", "mosque", "toilets", "garage", "shed", "service", "kiosk", "civic", "public",
                              "university", "college", "sports_centre", "pavilion", "religious", "parking")}
YES_CAP, YES_F = 45.0, 1.5
# OSM height tags replaced ([buildings] osm_fix): Mandarin Gallery (untagged, estimated 110 m: a 4-storey mall),
# the Singapore Flyer's terminal (its outline, 12 m)
OSM_FIX = {"w728368561": 20.0, "w230082125": 12.0, "w1075230982": 100.4,   # + IOI East Tower part (CTBUH 100.4)
           "w116905047": 227.0,
           "r3899820": 25.0}      # Victoria Theatre and Concert Hall's halls (tagged 15; ~25 m main roof, critic round 2, est.)   # unnamed 706 m² beside Marina Bay Residences, tagged 245 like it: MBR's 227 (CTBUH)
# shophouse districts: a small (under SHOP_AREA m²) building of 1-4 levels with no height tag is a shophouse,
# 4.5 m ground floor + 4 m an upper storey (2 storeys 8.5, 3 storeys 12.5), not levels x 3.5
SHOP_DISTRICTS = {"Outram", "Rochor", "Singapore River", "Downtown Core", "Museum", "Orchard", "River Valley",
                  "Kallang (Crawford)", "Bukit Merah (Tiong Bahru to the City Terminals)"}
SHOP_AREA = 600.0
SHOP_TAGS = {"yes", "house", "terrace", "shophouse", "retail", "commercial", "residential", "apartments", "hotel"}
SURFACE_H = {"w742205653": 21 * 3.5}   # height 0 in OSM: the former Marina Mandarin, 21 storeys, on Marina Square


def hdb(poly) -> gpd.GeoDataFrame:
    bd = gpd.GeoSeries([poly], crs=UTM).to_crs(4326)
    h = gpd.read_file(DATA / "hdb_storeys.gpkg", bbox=tuple(bd.buffer(0.01).total_bounds)).to_crs(UTM)
    h["geometry"] = h.geometry.make_valid()
    h = h.reset_index(drop=True)
    h["podium_fix"] = False
    h["cut_m2"] = 0.0
    j = gpd.sjoin(h[["geometry"]], h[["geometry"]], predicate="intersects")
    j = j[j.index != j.index_right]
    # first the podiums carrying their towers' storeys (a polygon of 3,000 m² or more holding others 80 % inside it,
    # none of them with more storeys than it): PODIUM_STOREYS
    for big, g in j.groupby(level=0):
        if h.geometry[big].area < 3000:
            continue
        inner = [k for k in g.index_right
                 if h.geometry[k].intersection(h.geometry[big]).area >= 0.8 * h.geometry[k].area
                 and h.geometry[k].area < 0.5 * h.geometry[big].area]
        if inner and h.max_floor_lvl[big] >= h.max_floor_lvl[inner].max() and h.max_floor_lvl[big] > PODIUM_STOREYS + 2:
            print(f"  HDB {h.blk_no[big]} {h.street[big]}: {h.max_floor_lvl[big]:.0f} storeys on a {h.geometry[big].area:.0f} m² "
                  f"podium holding {', '.join(h.blk_no[inner])}: {PODIUM_STOREYS}")
            h.loc[big, "max_floor_lvl"] = PODIUM_STOREYS
            h.loc[big, "podium_fix"] = True
    j = j[j.index < j.index_right]
    pairs = []
    for a, c in zip(j.index, j.index_right):
        inter = h.geometry[a].intersection(h.geometry[c]).area
        if inter >= 0.05 * min(h.geometry[a].area, h.geometry[c].area):
            sa, sc = h.max_floor_lvl[a], h.max_floor_lvl[c]
            if sa == sc:
                low, high = (a, c) if h.geometry[a].area > h.geometry[c].area else (c, a)
            elif np.nan_to_num(sa) < np.nan_to_num(sc):
                low, high = a, c
            else:
                low, high = c, a
            pairs.append((low, high))
    cuts = pd.DataFrame(pairs, columns=["low", "high"])
    for low, g in cuts.groupby("low"):
        a0 = h.geometry[low].area
        inner_max = h.max_floor_lvl[g.high].max()
        cut = h.geometry[low].difference(h.geometry[g.high].union_all())
        h.loc[low, "geometry"] = cut
        h.loc[low, "cut_m2"] = round(a0 - cut.area, 1)
        print(f"  HDB {h.blk_no[low]} {h.street[low]} ({h.max_floor_lvl[low]:.0f} storeys"
              f"{', podium fixed' if h.podium_fix[low] else ''}): {a0 - cut.area:.0f} of {a0:.0f} m² cut by "
              + ", ".join(f"{h.blk_no[x]} ({h.max_floor_lvl[x]:.0f})" for x in g.high)
              + f" (inner max {inner_max:.0f})")
    h = h[~h.geometry.is_empty & (h.area >= 1)]
    return h


def podiums(o: gpd.GeoDataFrame, parts: gpd.GeoDataFrame) -> pd.DataFrame:
    """OSM podium outlines with towers mapped inside them as buildings of their own (Singapore's way: MBFC's 35 m
    podium round its three towers, One Raffles Quay, Singapore Land Tower's 14 m podium round its 213 m tower):
    04_buildings would drop the tower as the podium's smaller duplicate (or both, the podium as an estate outline).
    A podium: an outline holding (80 % inside) a tower of 100 m² or more and 30 m or more, 1.5 x its own height and
    10 m over it, with 1.5 x the tower's area. hosts_parts: the building:parts lying half or more in the podium
    outside the towers (04_buildings' use_parts then builds the ring from them)."""
    # a tower with no tag of its own: its tallest building:part (Asia Square Tower 1, height=0, parts to 221 m)
    pj = gpd.sjoin(parts[["geometry", "height"]].assign(ph=parts["height"].map(height_m)), o[["geometry"]],
                   predicate="intersects")
    pj = pj[pj.ph > 0]
    import shapely as _s
    inside = _s.area(_s.intersection(pj.geometry.values, o.geometry.values[pj.index_right.values])) >= 0.5 * pj.area.values
    hp = pj[inside].groupby("index_right").ph.max()
    h = o["h"].fillna(hp.reindex(o.index)).fillna(0)          # the inner tower's
    h_own = o["h"].fillna(0)                                     # the podium's: its own tags only
    j = gpd.sjoin(o[["geometry"]].reset_index(names="io"), o[["geometry"]].reset_index(names="ii"), predicate="intersects")
    j = j[j.io != j.ii]
    import shapely
    inter = shapely.area(shapely.intersection(o.geometry.values[j.io.values], o.geometry.values[j.ii.values]))
    ai, ao = o.area.values[j.ii.values], o.area.values[j.io.values]
    hi, ho = h.values[j.ii.values], h_own.values[j.io.values]
    t = j[(inter >= 0.8 * ai) & (ai >= 100) & (ao >= 1.5 * ai) & (hi >= 30) & (hi >= 1.5 * ho) & (hi >= ho + 10)]
    out = []
    for io, g in t.groupby("io"):
        P = o.geometry.values[io]
        # its parts: parts lying half or more in the podium outside the towers
        rest = P.difference(shapely.union_all(o.geometry.values[g.ii.values]))
        near = parts[parts.intersects(rest)]
        hosted = (near.geometry.intersection(rest).area >= 0.5 * near.area).sum() if len(near) else 0
        out.append({"io": io, "towers": list(g.ii), "hosts_parts": int(hosted)})
    return pd.DataFrame(out)


def estimates(poly):
    from city3d.stages import buildings as eb
    o = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    o["geometry"] = o.geometry.make_valid()
    o = o[o.geometry.representative_point().within(poly)].copy()
    layer = pd.to_numeric(o["layer"], errors="coerce").fillna(0)
    ground = (o["location"] != "underground") & ((layer >= 0) | o["osm_id"].isin(SURFACE)
                                                  | o["location"].isin(eb.SURFACE))
    o = o[ground & ~o["building"].isin(CFG["buildings"]["osm_skip"])].reset_index(drop=True)
    o["ht"] = o["height"].map(height_m)
    o["lv"] = o["levels"].map(height_m)
    for k, v in OSM_FIX.items():
        o.loc[o["osm_id"] == k, ["ht", "lv"]] = [v, np.nan]
    # stations: the boxes left out, the entrances at ENTRANCE_H ([buildings] set_h), neither estimated
    st = o["building"].isin(STATION_TYPES) & ~o["osm_id"].isin(STATION_KEEP) & (o["district"] != "Sentosa")
    untagged = ~(o["ht"] > 0) & ~(o["lv"] > 0)
    drop = st & ((untagged & (o.area >= STATION_DROP)) | o["osm_id"].isin(["w823789587"]))
    drop |= o["location"].isin(["indoor"])            # (underground_drop drops these in 04_buildings)
    drop |= o["osm_id"].isin(list(HAND_EXCLUDE))
    sd = drop & (st | o["location"].isin(["indoor"]) | o["osm_id"].isin(["w823789587"]))
    STATIONS["drop"] = sorted(o.loc[sd, "osm_id"])
    STATIONS["entrance"] = sorted(o.loc[st & ~drop, "osm_id"])
    STATIONS["entrance_m2"] = float(o.loc[st & ~drop].area.sum())
    STATIONS["drop_m2"] = float(o.loc[sd].area.sum())
    o = o[~drop].reset_index(drop=True)
    o["h"] = o["ht"].where(o["ht"] > 0, o["lv"].where(o["lv"] > 0) * LEVEL_H)
    shop = (o["district"].isin(SHOP_DISTRICTS) & o["building"].isin(SHOP_TAGS) & (o.area < SHOP_AREA)
            & ~(o["ht"] > 0) & (o["lv"] >= 1) & (o["lv"] <= 4))
    o.loc[shop, "h"] = 4.5 + 4.0 * (o.loc[shop, "lv"] - 1)
    o["shop"] = shop
    o["h"] = o["h"].fillna(o["osm_id"].map(SURFACE_H))
    o["a"] = o.area
    rp = o.geometry.representative_point()
    pts = np.c_[rp.x, rp.y]
    # the landmark list's buildings don't vote (a 245 m tower is no model for its neighbours)
    lm = pd.read_csv(HERE / "data" / "landmarks.csv")
    lp = gpd.GeoSeries(gpd.points_from_xy(lm.lon, lm.lat), crs=4326).to_crs(UTM)
    holds = gpd.sjoin(o[["geometry"]], gpd.GeoDataFrame(geometry=lp), predicate="contains").index.unique()
    tagged = (o["h"].notna() & ~o.index.isin(holds)).to_numpy()
    tree = cKDTree(pts[tagged])
    th, ta = o["h"].to_numpy()[tagged], o["a"].to_numpy()[tagged]

    bt = o["building"].to_numpy()

    def est(i, self_out=False):
        d, idx = tree.query(pts[i], k=60, distance_upper_bound=R)
        ok = np.isfinite(d) & ((d > 0.01) if self_out else True)
        idx = idx[ok]
        a = o["a"].to_numpy()[i]
        sim = idx[(ta[idx] >= a / F) & (ta[idx] <= a * F)][:K]
        if len(sim) < 3:
            return np.nan
        # no needles: at most SLENDER x the square root of its own footprint (a 150 m² kiosk beside towers)
        v = min(float(np.median(th[sim])), CAP, SLENDER * np.sqrt(a), TYPE_CAP.get(bt[i], np.inf))
        if bt[i] == "yes" and v > YES_CAP:
            close = idx[(ta[idx] >= a / YES_F) & (ta[idx] <= a * YES_F)][:K]
            if len(close) < 3 or np.median(th[close]) < v:
                v = YES_CAP
        return v

    # leave-one-out on the tagged ones: the estimate against the default (default_floors x level_h)
    ti = np.where(tagged)[0]
    e = np.array([est(i, True) for i in ti])
    truth = o["h"].to_numpy()[ti]
    dflt = CFG["buildings"]["default_floors"] * LEVEL_H
    rows = []
    for lo, hi in [(0, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 1e9)]:
        m = ~np.isnan(e) & (o["a"].to_numpy()[ti] >= lo) & (o["a"].to_numpy()[ti] < hi)
        rows.append((lo, hi, int(m.sum()), np.median(truth[m]), np.median(np.abs(e[m] - truth[m])),
                     np.median(np.abs(dflt - truth[m]))))

    # podiums round towers: left out by id in city.toml (PODIUM_IDS printed here), drawn as their ring instead
    parts = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM)
    excl = set(CFG["buildings"]["exclude"].get("osm", []))
    pod = podiums(o, parts)
    pod = pod[~o["osm_id"].reindex(pod.io).isin(NOT_PODIUM).values] if len(pod) else pod
    pod_ids = set(o["osm_id"].reindex(pod.io)) if len(pod) else set()
    # what city.toml should leave out: written by --toml (excl above is what it says now)
    excl = set(HAND_EXCLUDE) | pod_ids | set(TOWER_PARTS)
    # the OSM buildings 04_buildings chooses (its own rules), less the podiums and what city.toml leaves out
    sel = o[~o["osm_id"].isin(excl | pod_ids)]
    big_one = sel["building"].isin(eb.BIG_BUILDING_TAGS) | sel["name"].notna() | sel["osm_id"].isin(eb.KEEP_OSM)
    chosen = eb.drop_osm_containers(sel[(sel.area <= eb.OSM_MAX_AREA) | big_one],
                                    keep=set(sel.index[sel["osm_id"].isin(eb.KEEP_OSM)]),
                                    inner=CFG["buildings"]["container_inner"])
    want = chosen.index[chosen["h"].isna() & (chosen.area >= MIN_AREA) & ~chosen["osm_id"].isin(STATIONS["entrance"])]
    out = o.loc[want].copy()
    out["est"] = [est(i) for i in want]
    out["est_src"] = "neighbours"
    out.loc[out["osm_id"].isin(SURFACE), "est_src"] = "surface"
    sur = o[o["osm_id"].isin(SURFACE) & o["h"].notna() & o.index.isin(chosen.index)].copy()
    sur["est"], sur["est_src"] = sur["h"], "surface"
    out.loc[out["osm_id"].isin(SURFACE) & out["est"].isna(), "est"] = out["osm_id"].map(SURFACE_H)
    # big ones: 04_buildings takes OSM's height tags only from outlines of osm_max_area or less (elsewhere an estate's
    # outline); a chosen big building's own tag is its height (the Flower Dome 30 m, the Esplanade's halls, malls)
    big = chosen[(chosen.area > eb.OSM_MAX_AREA) & chosen["h"].notna()].copy()
    big["est"], big["est_src"] = big["h"], "big_tag"
    sur = pd.concat([sur, big[~big.index.isin(sur.index)]])
    rings = []
    for r in pod.itertuples():
        P = o.geometry[r.io]
        # what stands in it: the chosen buildings and the other podiums (Downtown Gallery's in OUE Downtown's)
        cand = pd.concat([chosen.geometry, o.geometry[[k for k in pod.io if k != r.io]]])
        inner = cand[cand.intersects(P)]
        inner = inner[inner.intersection(P).area >= 0.5 * inner.area]
        ring = P.difference(inner.union_all()) if len(inner) else P
        ring = ring.buffer(-0.3, join_style="mitre").buffer(0.3, join_style="mitre")
        hp = o["h"][r.io]
        rings.append({"osm_id": o["osm_id"][r.io], "building": o["building"][r.io], "name": o["name"][r.io],
                      "est": hp if pd.notna(hp) and hp >= 3.5 else PODIUM_DEFAULT, "est_src": "podium",
                      "geometry": ring})
        print(f"  podium {o['osm_id'][r.io]} {o['name'][r.io] if isinstance(o['name'][r.io], str) else ''} "
              f"({o.area[r.io]:.0f} m², {hp if pd.notna(hp) else '-'} m) round "
              + ", ".join(f"{o['osm_id'][k]} {o['h'][k]:.0f} m" for k in r.towers)
              + f": ring {ring.area:.0f} m²")
    unhosted = [(o["osm_id"][r.io], o["name"][r.io], r.hosts_parts) for r in pod.itertuples() if r.hosts_parts > 0]
    # towers drawn only as a part on a podium outline: the ring at the podium's height, the parts at theirs
    for oid, (pids, hpod) in TOWER_PARTS.items():
        P = o.geometry[o["osm_id"] == oid].iloc[0]
        tp = parts[parts["osm_id"].isin(pids)]
        rings.append({"osm_id": oid, "building": "yes", "name": None, "est": hpod, "est_src": "podium",
                      "geometry": P.difference(tp.geometry.union_all())})
        for r in tp.itertuples():
            rings.append({"osm_id": r.osm_id, "building": "yes", "name": r.name, "est": height_m(r.height),
                          "est_src": "tower_part", "geometry": r.geometry})
        pod_ids.add(oid)
    for oid, hb in STADIUM_BOWL.items():
        P = o.geometry[o["osm_id"] == oid].iloc[0]
        g = parts.geometry.make_valid()
        rr = parts[(g.intersection(P).area >= 0.5 * g.area) & (pd.to_numeric(parts["min_height"], errors="coerce") > 0)]
        rings.append({"osm_id": oid, "building": "stadium", "name": o["name"][o["osm_id"] == oid].iloc[0], "est": hb,
                      "est_src": "stadium_bowl", "geometry": rr.geometry.union_all().intersection(P)})
        pod_ids.add(oid)
    shops = o.loc[o["shop"] & o.index.isin(chosen.index)].copy()
    shops["est"], shops["est_src"] = shops["h"], "shophouse"
    STATIONS["shop"] = len(shops)
    out = pd.concat([out[out["est"].notna()], sur, shops], ignore_index=True)
    out = out[~out["osm_id"].isin(list(STADIUM_BOWL) + list(TOWER_PARTS))]     # their copies: the bowl, the ring
    out = pd.concat([out, gpd.GeoDataFrame(rings, crs=UTM)], ignore_index=True)
    print("PODIUM_IDS = " + str(sorted(pod_ids)).replace("'", '"'))
    print("podium rings hosting building:parts: " + str(unhosted))
    return (gpd.GeoDataFrame(out[["osm_id", "building", "name", "est", "est_src", "geometry"]], crs=UTM), rows,
            len(want), sorted(pod_ids), unhosted)


def eb_max():
    return CFG["buildings"]["osm_max_area"]


STATIONS = {}


def flyer_parts() -> list:
    """building:parts lying in PART_STRUCTURES' outlines (the Flyer's rim): left out by id."""
    o = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    p = gpd.read_file(DATA / "osm_parts.gpkg").to_crs(UTM)
    P = o[o["osm_id"].isin(PART_STRUCTURES)].geometry.make_valid().union_all()
    g = p.geometry.make_valid()
    out = set(p.loc[g.intersection(P).area >= 0.5 * g.area, "osm_id"]) | set(PART_DROP)
    mh = pd.to_numeric(p["min_height"], errors="coerce")
    for oid, m in PART_DROP_IN.items():
        Q = o[o["osm_id"] == oid].geometry.make_valid().union_all()
        out |= set(p.loc[(g.intersection(Q).area >= 0.5 * g.area) & (mh >= m), "osm_id"])
    return sorted(out)


def write_toml(exclude: list, set_h: dict, osm_fix: dict):
    """city.toml [buildings]: the generated exclude, set_h and osm_fix lines between the markers (read and written at
    once: another agent may be editing other tables)."""
    lines, cur = [], 'exclude = { osm = ['
    for i, t in enumerate(exclude):
        t = f'"{t}"' + (", " if i < len(exclude) - 1 else "")
        if len(cur) + len(t) > 116:
            lines.append(cur.rstrip())
            cur = "    "
        cur += t
    # (an inline table may not break across lines: set_h and osm_fix stay on one line each)
    block = ["# >>> generated by scripts/m2_heights.py --toml (edit the script, not these lines)",
             "\n".join(lines + [cur + "] }"]),
             "set_h = { " + ", ".join(f'"{k}" = {v}' for k, v in set_h.items()) + " }",
             "osm_fix = { " + ", ".join(f'"{k}" = {v}' for k, v in osm_fix.items()) + " }",
             "# <<< generated"]
    path = HERE / "city.toml"
    s = path.read_text()
    a, z = "# >>> generated by scripts/m2_heights.py", "# <<< generated"
    if a in s:
        i, j = s.index(a), s.index(z) + len(z)
    else:                                    # the first time: the hand-written exclude line
        i = s.index("exclude = { osm = [")
        j = s.index("] }", i) + 3
    path.write_text(s[:i] + "\n".join(block) + s[j:])
    print(f"city.toml: exclude {len(exclude)}, set_h {len(set_h)}, osm_fix {len(osm_fix)} written")


def main():
    poly = boundary().geometry.iloc[0]
    h = hdb(poly)
    h.to_crs(4326).to_file(DATA / "hdb_m2.gpkg")
    print(f"hdb_m2.gpkg: {len(h):,} blocks, {int(h.podium_fix.sum())} podium storeys fixed, "
          f"{int((h.cut_m2 > 0).sum())} cut")
    e, rows, n_untagged, pod_ids, unhosted = estimates(poly)
    fl = flyer_parts()
    excl = sorted(set(HAND_EXCLUDE) | set(pod_ids) | set(fl))   # station boxes: [buildings] station_untagged
    if "--toml" in sys.argv:
        write_toml(excl, {**{k: ENTRANCE_H for k in STATIONS["entrance"]}, **SET_H}, OSM_FIX)
    else:
        have = set(CFG["buildings"]["exclude"].get("osm", []))
        if have != set(excl):
            print(f"WARNING: city.toml [buildings] exclude differs: add {sorted(set(excl) - have)}, remove "
                  f"{sorted(have - set(excl))} (run with --toml)")
    e.to_crs(4326).to_file(DATA / "osm_est.gpkg")
    L = ["", "## Height estimates for untagged OSM buildings (scripts/m2_heights.py)", "",
         f"OSM buildings in the districts with no height and no levels, {MIN_AREA:.0f} m² or more, not skipped: "
         f"{n_untagged:,}; estimated {int((e.est_src == 'neighbours').sum()):,} (median of the {K} nearest tagged "
         f"buildings within {R:.0f} m with a footprint within {F}x of theirs, at least 3, capped at {CAP:.0f} m and {SLENDER:g} x the square root of its area; "
         f"the rest take the default). Leave-one-out on the tagged buildings:", "",
         "| footprint (m²) | n | median tagged h (m) | median abs error: estimate (m) | median abs error: default 10.5 m (m) |",
         "|---|---|---|---|---|"]
    L += [f"| {lo:,.0f}-{hi:,.0f} | {n:,} | {t:.1f} | {me:.1f} | {md:.1f} |".replace("-1,000,000,000", "+")
          for lo, hi, n, t, me, md in rows]
    L += ["", "Under 500 m² the tagged heights are mostly an import's round values (10 m on shophouse rows), so a "
          "neighbour's tag repeats exactly (error 0): the estimate's real test is the 500-5,000 m² bands."]
    L += ["", f"Estimates by area: " + ", ".join(
        f"{lo:,}-{hi:,} m² median {g.est.median():.0f} m (n {len(g)})"
        for (lo, hi), g in ((k, e[(e.est_src == 'neighbours') & (e.area >= k[0]) & (e.area < k[1])])
                            for k in [(50, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 10**9)])
        if len(g)).replace("-1,000,000,000", "+") + ".",
          f"Layer < 0 outlines kept on the ground: " + ", ".join(
              f"{r.name if isinstance(r.name, str) else r.osm_id} {r.est:.0f} m"
              for r in e[e.est_src == "surface"].itertuples()) + ".",
          "", f"Podium outlines round towers mapped inside them ({len(pod_ids)}, city.toml [buildings] exclude, drawn as "
          f"their ring round the towers at their own height, else {PODIUM_DEFAULT:.0f} m): "
          + ", ".join(f"{r.name if isinstance(r.name, str) else r.osm_id} {r.est:.0f} m"
                      for r in e[e.est_src == "podium"].itertuples()) + ".",
          f"Big OSM buildings (over {eb_max():,.0f} m²) given their own height or levels tag (04_buildings takes tags from "
          f"smaller ones only): {int((e.est_src == 'big_tag').sum())}.",
          f"Rings with building:parts in them (04_buildings builds the ring from them, as it would the outline): " + (", ".join(f"{n if isinstance(n, str) else i} ({i}, {k} parts)" for i, n, k in unhosted) or "none") + "."]
    L += ["", f"Railway stations (train_station / transportation outside Sentosa; the MRT is underground here): "
          f"{len(STATIONS['drop'])} outlines left out by 04_buildings (station_untagged, underground_drop; untagged, {STATION_DROP:.0f} m² or more, plus HarbourFront's "
          f"underground=yes box and location=indoor; {STATIONS['drop_m2']:,.0f} m²), {len(STATIONS['entrance'])} kept as "
          f"entrances at {ENTRANCE_H} m ({STATIONS['entrance_m2']:,.0f} m², [buildings] set_h).",
          f"Shophouses (1-4 levels, under {SHOP_AREA:.0f} m², no height tag, in the shophouse districts): "
          f"{STATIONS['shop']:,} at 4.5 m + 4 m an upper storey (est, before osm_levels).",
          f"building:parts left out (the Flyer's rim, Pinnacle's skybridges, the Stadium's roof rings): {len(fl)}. Towers drawn only as a part: "
          + ", ".join(f"{k} -> {v[0]} (podium {v[1]:.0f} m)" for k, v in TOWER_PARTS.items()) + "."]
    (HERE / "checks" / "m2_estimates.md").write_text("# Singapore M2: height inputs\n" + "\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
